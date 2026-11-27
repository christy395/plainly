#!/usr/bin/env python3
"""Plainly: a plain English programming language.

Usage:
    python3 plainly.py run    program.plain   check, then run (full language)
    python3 plainly.py native program.plain   check, then compile to a fast native program
    python3 plainly.py compile program.plain  compile to a binary .pbc bytecode file
    python3 plainly.py execute program.pbc     execute a binary .pbc bytecode file
    python3 plainly.py init app|game NAME      create a cross-platform project
    python3 plainly.py project-check [FOLDER]  validate a project and its entry file
    python3 plainly.py check  program.plain   check only
    python3 plainly.py build  program.plain   show the generated Python
    python3 plainly.py c      program.plain   show the generated C
    python3 plainly.py fix    program.plain   fix common mistakes into program.fixed.plain
    python3 plainly.py core-check file.plain   check the independent Plainly core
    python3 plainly.py core-run file.plain     run with the independent Plainly core
    python3 plainly.py core-compile file.plain compile independent core bytecode
    python3 plainly.py core-execute file.core.pbc execute independent core bytecode
    python3 plainly.py version                show the version

Plainly checks types and permissions before anything runs. There is no null:
a value that may be missing is a 'maybe' and must be handled. Programs can
only use files they have asked permission for.

The native back end needs gcc and supports numbers, text, yes/no values,
lists of numbers, functions and all the control sentences. Files, records,
and 'maybe' values are in 'run' only for now.
"""
import re
import sys
import math
import difflib
import base64
import json
import os
import hashlib
import threading
import html as _html
import errno
import stat
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer


def _m(s):
    return re.sub(r"\W", "_", s.lower())


class PlainlyError(Exception):
    def __init__(self, msg, line=None):
        super().__init__(msg)
        self.msg = msg
        self.line = line


class PlainlyRuntimeError(Exception):
    pass


# ------------------------------------------------------- Python runtime
PERMS = set()


def _show(x):
    if x is None:
        return "nothing"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return str(int(x)) if x.is_integer() else "%.10g" % x
    if isinstance(x, list):
        return " and ".join(_show(i) for i in x) if x else "nothing"
    if isinstance(x, _Rec):
        parts = [f + " " + _show(getattr(x, "f_" + _m(f))) for f in x._fields]
        return x._name + " with " + " and ".join(parts)
    return str(x)


def _say(x):
    print(_show(x))


def _cat(a, b, spaced):
    return _show(a) + (" " if spaced else "") + _show(b)


class _Rec:
    _name = ""
    _fields = []

    def __init__(self, *vals):
        for f, v in zip(self._fields, vals):
            setattr(self, "f_" + _m(f), v)


def _record(name, fields):
    return type(name, (_Rec,), {"_name": name, "_fields": fields})


def _check_file(kind, name):
    if "/" in name or "\\" in name or name.startswith("."):
        raise PlainlyRuntimeError(
            "the file name %s is not allowed; programs only reach files in their own folder" % name)
    if (kind, name) not in PERMS:
        raise PlainlyRuntimeError(
            "permission denied: this program never asked to %s the file %s" % (kind, name))


def _open_user_file(name, mode):
    """Open a permitted local file without following a symbolic link.

    Plainly only accepts a simple file name. O_NOFOLLOW closes the final-
    component symlink race on systems that provide it. On other systems we
    reject an already-present symlink before opening; deployments must still
    use a private working directory owned by the Plainly process.
    """
    if mode not in ("r", "w"):
        raise ValueError("unsupported file mode")
    # Do not use O_TRUNC here: opening a hard link with O_TRUNC would
    # modify its target before the link-count check below can reject it.
    flags = os.O_RDONLY if mode == "r" else (os.O_WRONLY | os.O_CREAT)
    flags |= getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow and os.path.islink(name):
        raise PlainlyRuntimeError("symbolic links are not allowed for Plainly files")
    flags |= nofollow
    try:
        fd = os.open(name, flags, 0o600)
    except OSError as e:
        if getattr(e, "errno", None) == errno.ELOOP:
            raise PlainlyRuntimeError("symbolic links are not allowed for Plainly files")
        raise
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PlainlyRuntimeError("Plainly can only use regular files")
        if info.st_nlink != 1:
            raise PlainlyRuntimeError("hard-linked files are not allowed for Plainly file access")
        if mode == "w":
            os.ftruncate(fd, 0)
        return os.fdopen(fd, mode, encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise


def _read(name):
    _check_file("read", name)
    try:
        with _open_user_file(name, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise PlainlyRuntimeError("the file %s does not exist" % name)
    except PlainlyRuntimeError:
        raise
    except OSError:
        raise PlainlyRuntimeError("Plainly could not read the file %s" % name)


def _read_numbers(name):
    out = []
    for w in _read(name).replace(",", " ").split():
        try:
            out.append(float(w) if "." in w else int(w))
        except ValueError:
            raise PlainlyRuntimeError("the file %s has something that is not a number: %s" % (name, w))
    return out


def _read_lines(name):
    return _read(name).splitlines()


def _write(name, x):
    _check_file("write", name)
    try:
        with _open_user_file(name, "w") as f:
            f.write(_show(x) + "\n")
    except PlainlyRuntimeError:
        raise
    except OSError:
        raise PlainlyRuntimeError("Plainly could not write the file %s" % name)


def _count(n):
    if n < 0 or int(n) != n:
        raise PlainlyRuntimeError("repeat needs a whole number that is not negative")
    return int(n)


def _at(lst, i):
    if int(i) != i or i < 1 or i > len(lst):
        raise PlainlyRuntimeError("entry %s does not exist; the list has %d entries" % (_show(i), len(lst)))
    return lst[int(i) - 1]


def _length(x):
    return len(x)


def _sqrt(x):
    if x < 0:
        raise PlainlyRuntimeError("cannot take the square root of a negative number")
    return math.sqrt(x)


def _abs(x):
    return abs(x)


def _largest(l):
    if not l:
        raise PlainlyRuntimeError("largest of an empty list")
    return max(l)


def _smallest(l):
    if not l:
        raise PlainlyRuntimeError("smallest of an empty list")
    return min(l)


def _rounded(x):
    return int(math.floor(x + 0.5))


def _parsed(s):
    s = s.strip()
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    return None


def _ask():
    try:
        return input()
    except EOFError:
        return ""


def _orelse(a, b):
    return b if a is None else a


_LOCK = threading.RLock()
_MEM = {"file": None}


def _use_memory(name):
    if "/" in name or "\\" in name or name.startswith("."):
        raise PlainlyRuntimeError("the file name %s is not allowed; use a plain file name" % name)
    _MEM["file"] = name


def _mem_load():
    path = _MEM["file"]
    if not path:
        raise PlainlyRuntimeError("this program never asked to remember things")
    try:
        with _open_user_file(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        data = None
    if not isinstance(data, dict):
        raise PlainlyRuntimeError("the memory file %s is damaged, so I stopped instead of overwriting it" % path)
    return data


def _remember(name, value):
    with _LOCK:
        data = _mem_load()
        data[name] = value
        text = json.dumps(data)
        if len(text) > 1000000:
            raise PlainlyRuntimeError("the memory file is full")
        tmp = _MEM["file"] + ".tmp"
        with _open_user_file(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, _MEM["file"])


def _recall(name, spec):
    with _LOCK:
        v = _mem_load().get(name)
    base = spec.split()[-1]
    chk = {"number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
           "text": lambda x: isinstance(x, str), "truth": lambda x: isinstance(x, bool)}[base]
    if spec.startswith("list "):
        return v if isinstance(v, list) and all(chk(x) for x in v) else None
    return v if chk(v) else None


_ROUTES = {}
_TL = threading.local()
_BOT_HANDLERS = {}
_BOT_LOCAL = threading.local()
_SERVER_CONFIG = {"host": None, "port": None, "allowed_hosts": []}


def _set_bot_handler(platform, handler):
    _BOT_HANDLERS[platform] = handler


def _bot_field(name):
    event = getattr(_BOT_LOCAL, "event", None)
    if event is None or name not in event:
        raise PlainlyRuntimeError("that message detail is not available here")
    return event[name]


def _bot_reply(value):
    reply = getattr(_BOT_LOCAL, "reply", None)
    if reply is None:
        raise PlainlyRuntimeError("'reply with' only works while handling a bot message")
    reply(_show(value))


def _start_bot(platform):
    handler = _BOT_HANDLERS.get(platform)
    if handler is None:
        raise PlainlyRuntimeError("add a 'when a %s message arrives' handler before starting the bot" % platform.title())
    secret_name = "PLAINLY_SECRET_%s_TOKEN" % platform.upper()
    token = os.environ.get(secret_name, "")
    if not token:
        raise PlainlyRuntimeError("set %s in your hosting provider's app secrets before starting the bot" % secret_name)

    def dispatch(event, reply):
        _BOT_LOCAL.event = event
        _BOT_LOCAL.reply = reply
        try:
            handler()
        except (PlainlyRuntimeError, ZeroDivisionError) as exc:
            print("Plainly bot handler stopped: %s" % exc, file=sys.stderr)
        finally:
            for attr in ("event", "reply"):
                try:
                    delattr(_BOT_LOCAL, attr)
                except AttributeError:
                    pass

    try:
        import plainly_bots
        runner = plainly_bots.run_discord_bot if platform == "discord" else plainly_bots.run_telegram_bot
        runner(token, dispatch)
    except ImportError:
        raise PlainlyRuntimeError("the optional Plainly bot runtime is not installed") from None
    except plainly_bots.BotRuntimeError as exc:
        raise PlainlyRuntimeError(str(exc)) from None


def _normalise_host(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    try:
        return urlparse("//" + raw).hostname or ""
    except ValueError:
        return ""




def _route(path, fn):
    _ROUTES[path] = fn


def _reply(x):
    return ("text", _show(x))


_JS = ('document.addEventListener("click",async e=>{const b=e.target.closest("button[data-path]");'
       'if(!b)return;const q=new URLSearchParams();'
       'document.querySelectorAll("input[name]").forEach(i=>q.set(i.name,i.value));'
       'const t=document.getElementById(b.dataset.target);t.textContent="Asking the server...";'
       'try{const r=await fetch(b.dataset.path+"?"+q);t.textContent=await r.text()}'
       'catch(x){t.textContent="The server could not be reached."}});')
_JS_HASH = base64.b64encode(hashlib.sha256(_JS.encode("utf-8")).digest()).decode()


def _el(tag, text, ident=""):
    attr = ' id="e-%s"' % ident if ident else ""
    _TL.page.append("<%s%s>%s</%s>" % (tag, attr, _html.escape(_show(text)), tag))


def _box(name):
    _TL.page.append('<input name="%s" aria-label="%s" placeholder="%s">' % (name, name, name))


def _btn(text, path, target):
    _TL.page.append('<button data-path="%s" data-target="e-%s">%s</button>'
                    % (path, target, _html.escape(_show(text))))


def _page():
    head = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
            "<style>input,button{font:inherit;padding:.5rem .7rem;margin:.3rem .3rem .3rem 0}</style>"
            "<body style='font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.5'>")
    return ("html", head + "".join(_TL.page) + "<script>" + _JS + "</script>")


def _visitor(name):
    return _TL.query.get(name, [""])[0]


def _server_debug(message):
    if os.environ.get("PLAINLY_DEBUG_SERVER") == "1":
        print("Plainly server debug: " + message, file=sys.stderr, flush=True)


def _serve(port):
    config = _SERVER_CONFIG
    configured_port = config.get("port") or os.environ.get("PORT") or port
    if os.environ.get("PLAINLY_DEBUG_SERVER") == "1":
        import faulthandler
        import signal
        if hasattr(signal, "SIGUSR1") and hasattr(faulthandler, "register"):
            faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)
    try:
        port = int(configured_port)
    except (TypeError, ValueError):
        raise PlainlyRuntimeError("PORT must be a valid TCP port number")
    if not 1 <= port <= 65535:
        raise PlainlyRuntimeError("the configured port must be from 1 to 65535")

    host = config.get("host") or os.environ.get("PLAINLY_HOST") or "127.0.0.1"
    _server_debug("configuration resolved to %s:%d" % (host, port))
    allowed = set()
    for item in config.get("allowed_hosts", []):
        name = _normalise_host(item)
        if name:
            allowed.add(name)
    for item in os.environ.get("PLAINLY_ALLOWED_HOSTS", "").split(","):
        name = _normalise_host(item)
        if name:
            allowed.add(name)
    if host in ("127.0.0.1", "localhost", "::1"):
        allowed.update(("127.0.0.1", "localhost", "::1"))
    elif not allowed:
        raise PlainlyRuntimeError(
            "public website hosting requires at least one allowed domain; pass --allow-host YOUR_DOMAIN")

    class PlainlyHTTPServer(ThreadingHTTPServer):
        def server_bind(self):
            # HTTPServer.server_bind() calls socket.getfqdn(), which can block
            # on reverse DNS. The TCP layer already knows the bound address;
            # use it directly and keep startup independent of DNS availability.
            TCPServer.server_bind(self)
            self.server_name = str(self.server_address[0])
            self.server_port = self.server_address[1]

    class Handler(BaseHTTPRequestHandler):
        server_version = "Plainly"
        sys_version = ""

        def do_GET(self):
            request_host = _normalise_host(self.headers.get("Host", ""))
            if not request_host or request_host not in allowed:
                self.send_error(403, "Host not allowed")
                return
            u = urlparse(self.path)
            if u.path.rstrip("/") == "/healthz":
                code, kind, body = 200, "text", "ok"
            else:
                _TL.page = []
                _TL.query = parse_qs(u.query)
                fn = _ROUTES.get((u.path.rstrip("/") or "/").lower())
                if fn is None:
                    code, kind, body = 404, "text", "That page does not exist."
                else:
                    try:
                        with _LOCK:
                            code, (kind, body) = 200, (fn() or ("text", ""))
                    except PlainlyRuntimeError as e:
                        code, kind, body = 500, "text", "Plainly stopped this page: %s" % e
                    except ZeroDivisionError:
                        code, kind, body = 500, "text", "Plainly stopped this page: cannot divide by zero"
                    except Exception:
                        code, kind, body = 500, "text", "Plainly stopped this page: something went wrong."
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ("text/html" if kind == "html" else "text/plain") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            csp = "default-src 'none'; style-src 'unsafe-inline'"
            if kind == "html":
                csp += "; script-src 'sha256-%s'; connect-src 'self'" % _JS_HASH
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            print("  %s %s" % (getattr(self, "command", "-"), getattr(self, "path", "-")))

    _server_debug("creating HTTP listener")
    try:
        srv = PlainlyHTTPServer((host, port), Handler)
    except OSError:
        raise PlainlyRuntimeError("could not start on %s:%d; check the host and port" % (host, port))
    _server_debug("HTTP listener created and bound")
    srv.daemon_threads = True
    print("Serving Plainly on %s:%d (Ctrl+C to stop)" % (host, port), flush=True)
    _server_debug("entering serve_forever")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        srv.server_close()


RUNTIME = {n: globals()[n] for n in (
    "_show _say _cat _record _read _read_numbers _read_lines _write _count _at "
    "_length _sqrt _abs _largest _smallest _rounded _parsed _ask _orelse "
    "_route _reply _el _box _btn _page _visitor _serve _use_memory _remember _recall "
    "_set_bot_handler _bot_field _bot_reply _start_bot").split()}
SAFE_BUILTINS = {"range": range, "len": len, "int": int}

# ------------------------------------------------------------ C runtime
C_PRELUDE = r"""/* generated by Plainly */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
typedef struct { double *d; long n, cap; } List;
static void die(const char *m) { fprintf(stderr, "Plainly stopped the program: %s\n", m); exit(1); }
static List *p_list_new(void) { List *l = malloc(sizeof(List)); if (!l) die("out of memory"); l->d = NULL; l->n = 0; l->cap = 0; return l; }
static void p_push(List *l, double x) {
    if (l->n == l->cap) { l->cap = l->cap ? l->cap * 2 : 8; l->d = realloc(l->d, l->cap * sizeof(double)); if (!l->d) die("out of memory"); }
    l->d[l->n++] = x;
}
static List *p_list_of(long n, const double *v) { List *l = p_list_new(); for (long i = 0; i < n; i++) p_push(l, v[i]); return l; }
static double p_at(List *l, double i) { if (i != floor(i) || i < 1 || i > l->n) die("that entry does not exist"); return l->d[(long)i - 1]; }
static const char *p_str_num(double x) { char *b = malloc(48); if (x == floor(x) && fabs(x) < 1e15) snprintf(b, 48, "%.0f", x); else snprintf(b, 48, "%.10g", x); return b; }
static const char *p_str_bool(int x) { return x ? "yes" : "no"; }
static const char *p_str_list(List *l) {
    if (!l->n) return "nothing";
    char *b = malloc((size_t)l->n * 64 + 8); b[0] = 0;
    for (long i = 0; i < l->n; i++) { if (i) strcat(b, " and "); strcat(b, p_str_num(l->d[i])); }
    return b;
}
static const char *p_cat(const char *a, const char *b, int sp) { char *r = malloc(strlen(a) + strlen(b) + 2); strcpy(r, a); if (sp) strcat(r, " "); strcat(r, b); return r; }
static void p_say_text(const char *s) { puts(s); }
static void p_say_num(double x) { puts(p_str_num(x)); }
static void p_say_bool(int x) { puts(p_str_bool(x)); }
static void p_say_list(List *l) { puts(p_str_list(l)); }
static double p_div(double a, double b) { if (b == 0) die("cannot divide by zero"); return a / b; }
static double p_mod(double a, double b) { if (b == 0) die("cannot divide by zero"); return fmod(a, b); }
static long p_count(double n) { if (n < 0 || n != floor(n)) die("repeat needs a whole number that is not negative"); return (long)n; }
static double p_len_text(const char *s) { return (double)strlen(s); }
static double p_len_list(List *l) { return (double)l->n; }
static double p_sqrt(double x) { if (x < 0) die("cannot take the square root of a negative number"); return sqrt(x); }
static double p_abs(double x) { return fabs(x); }
static double p_rounded(double x) { return floor(x + 0.5); }
static double p_largest(List *l) { if (!l->n) die("largest of an empty list"); double m = l->d[0]; for (long i = 1; i < l->n; i++) if (l->d[i] > m) m = l->d[i]; return m; }
static double p_smallest(List *l) { if (!l->n) die("smallest of an empty list"); double m = l->d[0]; for (long i = 1; i < l->n; i++) if (l->d[i] < m) m = l->d[i]; return m; }
static const char *p_ask(void) { char *b = malloc(4096); if (!fgets(b, 4096, stdin)) b[0] = 0; size_t n = strlen(b); if (n && b[n - 1] == '\n') b[n - 1] = 0; return b; }
"""

# --------------------------------------------------------------- compiler
NUM = re.compile(r"^\d+(\.\d+)?$")
VERSION = "1.5.0"
TEXT_SPAN = re.compile(r"\bthe\s+words\b.*?(?:\bend\s+words\b|$)", re.I)
FORBIDDEN = set('_:"()[]{};')
RESERVED = set("""be to of is and or not then do end plus minus times divided by modulo
followed joined in as with giving from true false the a an called has new let set say add
subtract define allow write give run note if otherwise while repeat for each entry
maybe some no""".split())
CMPS = [(("is", "greater", "than"), ">"), (("is", "less", "than"), "<"),
        (("is", "at", "least"), ">="), (("is", "at", "most"), "<="),
        (("is", "not"), "!="), (("is",), "==")]


def tname(t):
    if t == "nothing":
        return "nothing"
    if isinstance(t, tuple):
        if t[0] == "list":
            return "a list of " + tname(t[1])
        if t[0] == "maybe":
            return "maybe " + tname(t[1])
        return t[1]
    return t


BUILTINS = {
    "length": dict(params=[("thing", "any")], ret="number", py="_length"),
    "square root": dict(params=[("value", "number")], ret="number", py="_sqrt", c="p_sqrt"),
    "absolute value": dict(params=[("value", "number")], ret="number", py="_abs", c="p_abs"),
    "rounded": dict(params=[("value", "number")], ret="number", py="_rounded", c="p_rounded"),
    "largest": dict(params=[("values", ("list", "number"))], ret="number", py="_largest", c="p_largest"),
    "smallest": dict(params=[("values", ("list", "number"))], ret="number", py="_smallest", c="p_smallest"),
    "parsed number": dict(params=[("text", "text")], ret=("maybe", "number"), py="_parsed", c=None),
}


def c_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Compiler:
    def __init__(self, native=False):
        self.native = native
        self.out = []
        self.fout = []
        self.protos = []
        self.indent = 0
        self.scopes = [({}, True)]
        self.blocks = []
        self.funcs = {}
        self.records = {}
        self.fieldnames = set()
        self.perms = set()
        self.route = False
        self.bot_context = None
        self.bot_permissions = set()
        self.bot_handlers = {}
        self.memory = None
        self.routes = set()
        self.page_names = {}
        self.pending = []
        self.fn = None
        self.line = 0
        self.t = []
        self.i = 0

    # ---- small helpers
    def err(self, msg):
        return PlainlyError(msg, self.line)

    def emit(self, s):
        text = "    " * self.indent + s
        if self.native and self.fn is not None:
            self.fout.append(text)
        else:
            self.out.append(text)

    def stmt(self, s):
        self.emit(s + (";" if self.native else ""))

    def head(self, py, c):
        self.emit(c if self.native else py)

    def ctype(self, t):
        if t == "number":
            return "double"
        if t == "truth":
            return "int"
        if t == "text":
            return "const char *"
        if t == ("list", "number"):
            return "List *"
        if t == "nothing":
            return "void"
        raise self.err("the native back end does not support %s yet; use 'run' instead" % tname(t))

    def cdecl(self, t):
        c = self.ctype(t)
        return c if c.endswith("*") else c + " "

    def cshow(self, code, t):
        if t == "number":
            return "p_str_num(%s)" % code
        if t == "truth":
            return "p_str_bool(%s)" % code
        if t == "text":
            return code
        if t == ("list", "number"):
            return "p_str_list(%s)" % code
        self.ctype(t)

    def no_native(self, what):
        if self.native:
            raise self.err("%s is not in the native back end yet; use 'run' instead" % what)

    def peek(self, k=0):
        j = self.i + k
        return self.t[j].lower() if j < len(self.t) else None

    def at_end(self):
        return self.i >= len(self.t)

    def take(self):
        if self.at_end():
            raise self.err("the sentence ended too early")
        tok = self.t[self.i]
        self.i += 1
        return tok

    def match(self, *ws):
        for k, w in enumerate(ws):
            if self.peek(k) != w:
                return False
        self.i += len(ws)
        return True

    def expect(self, *ws):
        if not self.match(*ws):
            got = self.t[self.i] if not self.at_end() else "the end of the sentence"
            raise self.err("I expected the word '%s' here but found %s" % (" ".join(ws), got))

    def finish(self):
        if not self.at_end():
            raise self.err("I did not expect '%s' here" % " ".join(self.t[self.i:]))

    def words_until(self, *stops):
        out = []
        while not self.at_end() and self.peek() not in stops:
            out.append(self.take())
        return out

    def longest(self, cands, need_of=False, off=0):
        rest = len(self.t) - self.i - off
        for n in range(min(6, rest), 0, -1):
            cand = " ".join(self.t[self.i + off:self.i + off + n]).lower()
            if cand in cands:
                if need_of and self.peek(off + n) != "of":
                    continue
                return n
        return 0

    # ---- scopes
    def visible(self):
        out = {}
        for d, boundary in reversed(self.scopes):
            for k, v in d.items():
                out.setdefault(k, v)
            if boundary:
                break
        return out

    def all_funcs(self):
        d = dict(BUILTINS)
        d.update(self.funcs)
        return d

    def new_name(self, words, func=False):
        if not words:
            raise self.err("I expected a name here")
        name = " ".join(words).lower()
        if len(words) > 6:
            raise self.err("a name can be at most 6 words long")
        if NUM.match(words[0]) or name in ("true", "false"):
            raise self.err("'%s' cannot be used as a name; a name cannot start with a number" % name)
        funcs = self.all_funcs()
        if name in self.visible() or (name in funcs and (func or not funcs[name]["params"])):
            raise self.err("the name '%s' is already used" % name)
        return name

    def declare(self, name, t):
        py = "v_" + _m(name)
        self.scopes[-1][0][name] = (t, py)
        return py

    def open_block(self, kind, boundary=False, **kw):
        self.indent += 1
        if not self.native:
            self.emit("pass")
        self.blocks.append(dict(kind=kind, line=self.line, term=False, **kw))
        self.scopes.append(({}, boundary))

    # ---- program
    def compile(self, src):
        for no, raw in enumerate(src.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            self.line = no
            bad = [c for c in TEXT_SPAN.sub("", line) if c in FORBIDDEN]
            if bad and not line.lower().startswith("note"):
                raise self.err("Plainly does not use the symbol %s outside text; write it in words, "
                               "or put it inside: the words ... end words" % bad[0])
            self.t = line.split()
            self.i = 0
            self.statement()
        if self.blocks:
            b = self.blocks[-1]
            raise PlainlyError("this block is never closed; it needs 'end %s'" % b["kind"], b["line"])
        for path, ln in self.pending:
            if path not in self.routes:
                raise PlainlyError("a button asks the path %s, but no 'when someone visits the path' block handles it"
                                   % path, ln)
        if self.native:
            return (C_PRELUDE + "\n".join(self.protos) + "\n" + "\n".join(self.fout)
                    + "\nint main(void) {\n" + "\n".join(self.out) + "\n    return 0;\n}\n")
        return "\n".join(self.out) + "\n"

    def statement(self):
        w = self.peek()
        if w == "note":
            return
        if w == "end":
            return self.s_end()
        if w == "otherwise":
            return self.s_otherwise()
        if self.blocks:
            self.blocks[-1]["term"] = False
        if w in ("a", "an") and self.peek(1) == "record":
            return self.s_record()
        if w == "give" and self.peek(1) == "back":
            return self.s_give()
        table = {"say": self.s_say, "let": self.s_let, "set": self.s_set, "add": self.s_add,
                 "subtract": self.s_subtract, "if": self.s_if, "while": self.s_while,
                 "repeat": self.s_repeat, "for": self.s_for, "define": self.s_define,
                 "allow": self.s_allow, "write": self.s_write, "run": self.s_run,
                 "remember": self.s_remember, "when": self.s_when, "reply": self.s_reply, "show": self.s_show, "start": self.s_start}
        if w in table:
            return table[w]()
        raise self.err("I do not know how to start a sentence with '%s'" % self.t[self.i])

    # ---- statements
    def not_nothing(self, t):
        if t == "nothing":
            raise self.err("that gives back nothing, so there is no value to use")

    def s_say(self):
        self.take()
        e, t = self.parse_or()
        self.finish()
        self.not_nothing(t)
        if self.native:
            kind = {"number": "num", "truth": "bool", "text": "text"}.get(t) \
                if not isinstance(t, tuple) else "list"
            self.ctype(t)
            self.stmt("p_say_%s(%s)" % (kind, e))
        else:
            self.stmt("_say(%s)" % e)

    def s_let(self):
        self.take()
        words = self.words_until("be")
        if not self.match("be"):
            raise self.err("a let sentence needs the word 'be', like: let total be 0")
        name = self.new_name(words)
        e, t = self.parse_or()
        self.finish()
        self.not_nothing(t)
        py = self.declare(name, t)
        if self.native:
            self.stmt("%s%s = %s" % (self.cdecl(t), py, e))
        else:
            self.stmt("%s = %s" % (py, e))

    def find_var(self):
        vis = self.visible()
        n = self.longest(vis)
        if not n:
            word = self.t[self.i] if not self.at_end() else ""
            close = difflib.get_close_matches(word.lower(), list(vis), 1)
            hint = "; did you mean '%s'?" % close[0] if close else ""
            raise self.err("I do not know a name called '%s'%s" % (word, hint))
        name = " ".join(self.t[self.i:self.i + n]).lower()
        self.i += n
        return name, vis[name]

    def s_set(self):
        self.take()
        name, (vt, py) = self.find_var()
        self.expect("to")
        e, t = self.parse_or()
        self.finish()
        if t != vt:
            raise self.err("'%s' holds %s, so it cannot be set to %s" % (name, tname(vt), tname(t)))
        self.stmt("%s = %s" % (py, e))

    def s_add(self):
        self.take()
        e, t = self.parse_or()
        self.expect("to")
        name, (vt, py) = self.find_var()
        self.finish()
        if vt == "number" and t == "number":
            self.stmt("%s += %s" % (py, e))
        elif isinstance(vt, tuple) and vt[0] == "list" and t == vt[1]:
            self.stmt(("p_push(%s, %s)" if self.native else "%s.append(%s)") % (py, e))
        else:
            raise self.err("cannot add %s to '%s', which holds %s" % (tname(t), name, tname(vt)))

    def s_subtract(self):
        self.take()
        e, t = self.parse_or()
        self.expect("from")
        name, (vt, py) = self.find_var()
        self.finish()
        if vt != "number" or t != "number":
            raise self.err("subtract works on numbers only")
        self.stmt("%s -= %s" % (py, e))

    def cond(self, stop):
        c, t = self.parse_or()
        self.expect(stop)
        self.finish()
        if t != "truth":
            raise self.err("a condition must be a yes or no value, but this is %s" % tname(t))
        return c

    def s_if(self):
        self.take()
        e, t = self.parse_or()
        if self.match("has", "a", "value"):
            self.no_native("'has a value'")
            if not (isinstance(t, tuple) and t[0] == "maybe"):
                raise self.err("'has a value' only works on a maybe, but this is %s" % tname(t))
            self.expect("as")
            words = self.words_until("then")
            self.expect("then")
            self.finish()
            name = self.new_name(words)
            self.emit("if (v_%s := %s) is not None:" % (_m(name), e))
            self.open_block("if", branches=[], has_else=False)
            self.declare(name, t[1])
            return
        self.expect("then")
        self.finish()
        if t != "truth":
            raise self.err("a condition must be a yes or no value, but this is %s" % tname(t))
        self.head("if %s:" % e, "if (%s) {" % e)
        self.open_block("if", branches=[], has_else=False)

    def s_otherwise(self):
        if not self.blocks or self.blocks[-1]["kind"] != "if" or self.blocks[-1]["has_else"]:
            raise self.err("'otherwise' must come inside an 'if' block")
        b = self.blocks[-1]
        b["branches"].append(b["term"])
        b["term"] = False
        self.scopes.pop()
        self.scopes.append(({}, False))
        self.take()
        self.indent -= 1
        if self.match("if"):
            c = self.cond("then")
            self.head("elif %s:" % c, "} else if (%s) {" % c)
        else:
            self.finish()
            self.head("else:", "} else {")
            b["has_else"] = True
        self.indent += 1
        if not self.native:
            self.emit("pass")

    def s_while(self):
        self.take()
        c = self.cond("do")
        self.head("while %s:" % c, "while (%s) {" % c)
        self.open_block("while")

    def s_repeat(self):
        self.take()
        e, t = self.parse_or()
        self.expect("times")
        self.expect("do")
        self.finish()
        if t != "number":
            raise self.err("repeat needs a number of times")
        n = self.line
        self.head("for _ in range(_count(%s)):" % e,
                  "for (long _r%d = 0, _n%d = p_count(%s); _r%d < _n%d; _r%d++) {" % (n, n, e, n, n, n))
        self.open_block("repeat")

    def s_for(self):
        self.take()
        self.expect("each")
        words = self.words_until("in")
        self.expect("in")
        e, t = self.parse_or()
        self.expect("do")
        self.finish()
        if not (isinstance(t, tuple) and t[0] == "list"):
            raise self.err("'for each' needs a list, but this is %s" % tname(t))
        name = self.new_name(words)
        py = "v_" + _m(name)
        n = self.line
        if self.native:
            self.ctype(t)
            self.emit("{")
            self.emit("    List *_l%d = %s;" % (n, e))
            self.emit("    for (long _i%d = 0; _i%d < _l%d->n; _i%d++) {" % (n, n, n, n))
            self.open_block("for", close=2)
            self.emit("double %s = _l%d->d[_i%d];" % (py, n, n))
        else:
            self.emit("for %s in %s:" % (py, e))
            self.open_block("for")
        self.declare(name, t[1])

    def s_record(self):
        self.no_native("records")
        if self.blocks:
            raise self.err("a record must be defined at the top of the program, not inside a block")
        self.take()
        self.expect("record")
        self.expect("called")
        words = self.words_until("has")
        self.expect("has")
        name = self.new_name(words)
        if name in self.records:
            raise self.err("the record '%s' is already defined" % name)
        fields = {}
        while True:
            fw = self.words_until("as")
            self.expect("as")
            fname = " ".join(fw).lower()
            if not fname or fname in fields:
                raise self.err("each field needs its own name")
            fields[fname] = self.parse_type()
            if not self.match("and"):
                break
        self.finish()
        self.records[name] = fields
        self.fieldnames.update(fields)
        self.emit("R_%s = _record(%r, %r)" % (_m(name), name, list(fields)))

    def parse_type(self):
        if self.match("maybe"):
            return ("maybe", self.parse_type())
        self.match("a") or self.match("an") or self.match("the")
        if self.match("list", "of"):
            return ("list", self.parse_type())
        for base in ("number", "text", "truth"):
            if self.match(base):
                return base
        n = self.longest(self.records)
        if n:
            name = " ".join(self.t[self.i:self.i + n]).lower()
            self.i += n
            return ("rec", name)
        raise self.err("I expected a type here: number, text, truth, a list of ..., maybe ..., or a record name")

    def s_define(self):
        if self.blocks:
            raise self.err("'define' must be at the top level of the program")
        self.take()
        words = self.words_until("of", "giving")
        name = self.new_name(words, func=True)
        params = []
        if self.match("of"):
            while True:
                pw = self.words_until("as")
                self.expect("as")
                pname = " ".join(pw).lower()
                if not pname:
                    raise self.err("each input needs a name")
                params.append((pname, self.parse_type()))
                if not self.match("with"):
                    break
        ret = None
        if self.match("giving"):
            ret = self.parse_type()
        self.finish()
        py = "f_" + _m(name)
        self.funcs[name] = dict(params=params, ret=ret or "nothing", py=py)
        self.fn = self.funcs[name]
        if self.native:
            plist = ", ".join("%sv_%s" % (self.cdecl(pt), _m(p)) for p, pt in params) or "void"
            sig = "%s%s(%s)" % (self.cdecl(self.fn["ret"]), py, plist)
            self.protos.append(sig + ";")
            self.emit(sig + " {")
        else:
            self.emit("def %s(%s):" % (py, ", ".join("v_" + _m(p) for p, _ in params)))
        self.open_block("define", boundary=True)
        for p, pt in params:
            self.declare(p, pt)

    def s_give(self):
        if not self.fn:
            raise self.err("'give back' only works inside a define")
        self.take()
        self.take()
        e, t = self.parse_or()
        self.finish()
        if self.fn["ret"] == "nothing":
            raise self.err("this define has no 'giving' type, so it cannot give anything back")
        if t != self.fn["ret"]:
            raise self.err("this define promises %s but gives back %s" % (tname(self.fn["ret"]), tname(t)))
        self.stmt("return %s" % e)
        self.blocks[-1]["term"] = True

    def s_end(self):
        self.take()
        kind = self.peek()
        if not self.blocks:
            raise self.err("this 'end' has nothing to close")
        b = self.blocks[-1]
        if kind != b["kind"]:
            raise self.err("this closes '%s', but the open block from line %d needs 'end %s'"
                           % (kind, b["line"], b["kind"]))
        self.take()
        self.finish()
        if kind == "define" and self.fn["ret"] != "nothing" and not b["term"]:
            raise self.err("this define promises %s, but some path through it never gives back a value"
                           % tname(self.fn["ret"]))
        self.blocks.pop()
        self.scopes.pop()
        self.indent -= 1
        if self.native:
            for k in range(b.get("close", 1)):
                self.emit("}")
                if k < b.get("close", 1) - 1:
                    self.indent -= 1
            self.indent += b.get("close", 1) - 1
        if kind == "define":
            self.fn = None
        if kind == "when":
            if b.get("bot_platform"):
                self.emit("_set_bot_handler(%r, %s)" % (b["bot_platform"], b["py"]))
                self.bot_context = None
            else:
                self.emit("_route(%r, %s)" % (b["path"], b["py"]))
                self.route = False
        if self.blocks:
            term = False
            if kind == "if":
                branches = b["branches"] + [b["term"]]
                term = b["has_else"] and all(branches)
            self.blocks[-1]["term"] = term

    def need_perm(self, kind, name):
        if "/" in name or "\\" in name or name.startswith("."):
            raise self.err("the file name '%s' is not allowed; use a plain file name" % name)
        if (kind, name) not in self.perms:
            verb = "reading" if kind == "read" else "writing"
            raise self.err("this program has not asked permission yet; add 'allow %s the file %s' first"
                           % (verb, name))

    def s_allow(self):
        self.take()
        if self.match("running", "a", "discord", "bot"):
            self.no_native("Discord bots")
            self.finish()
            self.bot_permissions.add("discord")
            return
        if self.match("running", "a", "telegram", "bot"):
            self.no_native("Telegram bots")
            self.finish()
            self.bot_permissions.add("telegram")
            return
        self.no_native("files")
        if self.match("reading"):
            kind = "read"
        elif self.match("writing"):
            kind = "write"
        elif self.match("remembering", "in", "the", "file"):
            name = self.take()
            self.finish()
            if "/" in name or "\\" in name or name.startswith("."):
                raise self.err("the file name '%s' is not allowed; use a plain file name" % name)
            if self.memory:
                raise self.err("a program can remember things in only one file")
            self.memory = name
            self.emit("_use_memory(%r)" % name)
            return
        else:
            raise self.err("use 'allow reading the file NAME', 'allow writing the file NAME', "
                           "or 'allow remembering in the file NAME'")
        self.expect("the", "file")
        name = self.take()
        self.finish()
        if "/" in name or "\\" in name or name.startswith("."):
            raise self.err("the file name '%s' is not allowed; use a plain file name" % name)
        self.perms.add((kind, name))
        self.emit("# permission: %s the file %s" % (kind, name))

    def s_write(self):
        self.no_native("files")
        self.take()
        e, t = self.parse_or()
        self.expect("to", "the", "file")
        name = self.take()
        self.finish()
        self.need_perm("write", name)
        self.stmt("_write(%r, %s)" % (name, e))

    def s_run(self):
        self.take()
        e, t = self.parse_primary()
        self.finish()
        self.stmt(e)

    # ---- websites: routes, replies, pages
    def s_when(self):
        self.no_native("servers and bots")
        if self.blocks:
            raise self.err("'when' blocks must be at the top level of the program")
        self.take()
        platform = None
        if self.match("a", "discord", "message", "arrives"):
            platform = "discord"
        elif self.match("a", "telegram", "message", "arrives"):
            platform = "telegram"
        if platform:
            if platform not in self.bot_permissions:
                raise self.err("ask permission first with 'allow running a %s bot'" % platform.title())
            if platform in self.bot_handlers:
                raise self.err("this program already has a %s message handler" % platform.title())
            self.expect("do")
            self.finish()
            py = "_plainly_%s_message_handler" % platform
            self.bot_handlers[platform] = py
            self.emit("def %s():" % py)
            self.open_block("when", boundary=True, bot_platform=platform, py=py)
            self.bot_context = platform
            return
        self.expect("someone", "visits", "the", "path")
        words = self.words_until("do")
        self.expect("do")
        self.finish()
        if not words or not all(re.fullmatch(r"[A-Za-z0-9.\-]+", w) for w in words):
            raise self.err("a path is made of plain words, like: the path about, or the path home")
        path = "/" if [w.lower() for w in words] == ["home"] else "/" + "/".join(w.lower() for w in words)
        if path in self.routes:
            raise self.err("the path %s already has a handler" % path)
        self.routes.add(path)
        py = "route_%d" % len(self.routes)
        self.emit("def %s():" % py)
        self.open_block("when", boundary=True, path=path, py=py)
        self.route = True
        self.page_names = {}

    def s_reply(self):
        if self.bot_context:
            self.no_native("bots")
            self.take()
            self.expect("with")
            e, t = self.parse_or()
            self.finish()
            self.not_nothing(t)
            self.emit("_bot_reply(%s)" % e)
            return
        self.no_native("servers")
        if not self.route:
            raise self.err("'reply' only works inside a website or bot message handler")
        self.take()
        self.expect("with")
        if self.match("the", "page"):
            self.finish()
            self.emit("return _page()")
            return
        e, t = self.parse_or()
        self.finish()
        self.not_nothing(t)
        self.emit("return _reply(%s)" % e)

    def mem_spec(self, t):
        if t in ("number", "text", "truth"):
            return t
        if isinstance(t, tuple) and t[0] == "list" and t[1] in ("number", "text", "truth"):
            return "list " + t[1]
        raise self.err("I can only remember numbers, text, yes or no values, and lists of those, but this is %s"
                       % tname(t))

    def mem_name(self):
        name = self.take().lower()
        if not re.fullmatch(r"[a-z0-9]+", name):
            raise self.err("a remembered name is one plain word, like: visits")
        return name

    def need_memory(self):
        if not self.memory:
            raise self.err("this program has not asked permission yet; "
                           "add 'allow remembering in the file NAME' first")

    def s_remember(self):
        self.no_native("remembering")
        self.need_memory()
        self.take()
        e, t = self.parse_or()
        self.expect("as")
        name = self.mem_name()
        self.finish()
        self.mem_spec(t)
        self.emit("_remember(%r, %s)" % (name, e))

    def make_path(self, words):
        if not words or not all(re.fullmatch(r"[A-Za-z0-9.\-]+", w) for w in words):
            raise self.err("a path is made of plain words, like: the path about, or the path home")
        return "/" if [w.lower() for w in words] == ["home"] else "/" + "/".join(w.lower() for w in words)

    def s_show(self):
        self.no_native("pages")
        if not self.route:
            raise self.err("page sentences work inside 'when someone visits the path' here; "
                           "the browser version builds live pages")
        self.take()
        self.match("a") or self.match("an")
        kind = self.peek()
        if kind not in ("heading", "paragraph", "box", "button"):
            raise self.err("use: show a heading, a paragraph, a box or a button")
        self.take()
        name = ""
        if kind in ("paragraph", "box") and self.match("called"):
            name = self.take().lower()
            if not re.fullmatch(r"[a-z0-9]+", name):
                raise self.err("a name on a page is one plain word, like: called answer")
            if name in self.page_names:
                raise self.err("the name '%s' is already used on this page" % name)
            self.page_names[name] = kind
        elif kind == "box":
            raise self.err("a box needs a name, like: show a box called name")
        if kind == "box":
            self.finish()
            self.emit("_box(%r)" % name)
            return
        self.expect("with")
        e, t = self.parse_concat()
        if t != "text":
            raise self.err("the words to show must be text, but this is %s" % tname(t))
        if kind == "button":
            self.expect("that", "asks", "the", "path")
            pw = self.words_until("and")
            self.expect("and", "shows", "the", "reply", "in", "the", "paragraph", "called")
            target = self.take().lower()
            self.finish()
            path = self.make_path(pw)
            if self.page_names.get(target) != "paragraph":
                raise self.err("show a paragraph called %s above this button, to hold the reply" % target)
            self.pending.append((path, self.line))
            self.emit("_btn(%s, %r, %r)" % (e, path, target))
            return
        self.finish()
        self.emit("_el(%r, %s, %r)" % ({"heading": "h2", "paragraph": "p"}[kind], e, name))

    def s_start(self):
        self.no_native("servers and bots")
        if self.blocks:
            raise self.err("'start' must be at the top level of the program")
        self.take()
        if self.match("the", "discord", "bot"):
            self.finish()
            if "discord" not in self.bot_permissions:
                raise self.err("ask permission first with 'allow running a Discord bot'")
            if "discord" not in self.bot_handlers:
                raise self.err("add a 'when a Discord message arrives' handler before starting the bot")
            self.emit("_start_bot('discord')")
            return
        if self.match("the", "telegram", "bot"):
            self.finish()
            if "telegram" not in self.bot_permissions:
                raise self.err("ask permission first with 'allow running a Telegram bot'")
            if "telegram" not in self.bot_handlers:
                raise self.err("add a 'when a Telegram message arrives' handler before starting the bot")
            self.emit("_start_bot('telegram')")
            return
        self.expect("the", "server", "on", "port")
        tok = self.take()
        self.finish()
        if not tok.isdigit() or not 1024 <= int(tok) <= 65535:
            raise self.err("the port must be a whole number from 1024 to 65535")
        if not self.routes:
            raise self.err("add at least one 'when someone visits the path' block before starting the server")
        self.emit("_serve(%s)" % tok)

    # ---- expressions
    def parse_or(self):
        l, lt = self.parse_or_core()
        while self.peek() == "or" and self.peek(1) == "else":
            self.i += 2
            r, rt = self.parse_or_core()
            if lt != ("maybe", rt):
                raise self.err("'or else' needs a maybe on the left and a matching value on the right, "
                               "but got %s and %s" % (tname(lt), tname(rt)))
            l, lt = "_orelse(%s, %s)" % (l, r), rt
        return l, lt

    def parse_or_core(self):
        l, lt = self.parse_and()
        while self.peek() == "or" and self.peek(1) != "else":
            self.i += 1
            r, rt = self.parse_and()
            self.need_truth("or", lt, rt)
            l, lt = "(%s %s %s)" % (l, "||" if self.native else "or", r), "truth"
        return l, lt

    def parse_and(self):
        l, lt = self.parse_not()
        while self.match("and"):
            r, rt = self.parse_not()
            self.need_truth("and", lt, rt)
            l, lt = "(%s %s %s)" % (l, "&&" if self.native else "and", r), "truth"
        return l, lt

    def parse_not(self):
        if self.match("not"):
            e, t = self.parse_not()
            self.need_truth("not", t, t)
            return "(%s%s)" % ("!" if self.native else "not ", e), "truth"
        return self.parse_cmp()

    def need_truth(self, op, a, b):
        if a != "truth" or b != "truth":
            raise self.err("'%s' works on yes or no values, but got %s and %s" % (op, tname(a), tname(b)))

    def parse_cmp(self):
        l, lt = self.parse_concat()
        if self.peek() == "contains":
            self.no_native("'contains'")
            self.i += 1
            r, rt = self.parse_concat()
            if lt != "text" or rt != "text":
                raise self.err("'contains' works on text, like: message contains the words hello")
            return "((%s).lower() in (%s).lower())" % (r, l), "truth"
        for words, op in CMPS:
            if self.match(*words):
                r, rt = self.parse_concat()
                if lt != rt:
                    raise self.err("cannot compare %s with %s" % (tname(lt), tname(rt)))
                if op not in ("==", "!=") and lt not in ("number", "text"):
                    raise self.err("only numbers and text can be put in order")
                if self.native and lt == "text":
                    return "(strcmp(%s, %s) %s 0)" % (l, r, op), "truth"
                if self.native and lt not in ("number", "truth"):
                    raise self.err("the native back end cannot compare %s yet; use 'run' instead" % tname(lt))
                return "(%s %s %s)" % (l, op, r), "truth"
        return l, lt

    def parse_concat(self):
        l, lt = self.parse_add()
        while True:
            if self.match("followed", "by"):
                sp = True
            elif self.match("joined", "to"):
                sp = False
            else:
                return l, lt
            r, rt = self.parse_add()
            self.not_nothing(lt)
            self.not_nothing(rt)
            if self.native:
                l = "p_cat(%s, %s, %d)" % (self.cshow(l, lt), self.cshow(r, rt), 1 if sp else 0)
            else:
                l = "_cat(%s, %s, %s)" % (l, r, sp)
            lt = "text"

    def need_nums(self, op, a, b):
        if a != "number" or b != "number":
            extra = " To join text, use 'followed by'." if "text" in (a, b) else ""
            raise self.err("'%s' needs two numbers but got %s and %s.%s" % (op, tname(a), tname(b), extra))

    def parse_add(self):
        l, lt = self.parse_mul()
        while True:
            if self.match("plus"):
                op, sym = "plus", "+"
            elif self.match("minus"):
                op, sym = "minus", "-"
            else:
                return l, lt
            r, rt = self.parse_mul()
            self.need_nums(op, lt, rt)
            l, lt = "(%s %s %s)" % (l, sym, r), "number"

    def parse_mul(self):
        l, lt = self.parse_primary()
        while True:
            if self.peek() == "times" and self.peek(1) != "do":
                self.i += 1
                op, sym = "times", "*"
            elif self.match("divided", "by"):
                op, sym = "divided by", "/"
            elif self.match("modulo"):
                op, sym = "modulo", "%"
            else:
                return l, lt
            r, rt = self.parse_primary()
            self.need_nums(op, lt, rt)
            if self.native and sym == "/":
                l = "p_div(%s, %s)" % (l, r)
            elif self.native and sym == "%":
                l = "p_mod(%s, %s)" % (l, r)
            else:
                l = "(%s %s %s)" % (l, sym, r)
            lt = "number"

    def parse_primary(self):
        if self.at_end():
            raise self.err("I expected a value here but the sentence ended")
        tok = self.t[self.i]
        w = tok.lower()
        if NUM.match(tok):
            self.i += 1
            return (tok + ".0" if self.native and "." not in tok else tok), "number"
        if w in ("true", "false"):
            self.i += 1
            if self.native:
                return ("1" if w == "true" else "0"), "truth"
            return ("True" if w == "true" else "False"), "truth"
        if self.match("the", "words"):
            ws = []
            while not self.at_end():
                if self.peek() == "end" and self.peek(1) == "words":
                    self.i += 2
                    break
                if (self.peek(), self.peek(1)) in (("followed", "by"), ("joined", "to"), ("that", "asks")) or \
                        (self.peek(), self.peek(1), self.peek(2)) == ("and", "the", "words"):
                    break
                ws.append(self.take())
            s = " ".join(ws)
            return (c_str(s) if self.native else repr(s)), "text"
        if self.match("what", "i", "remember", "called"):
            self.no_native("remembering")
            self.need_memory()
            name = self.mem_name()
            self.expect("as")
            t = self.parse_type()
            return "_recall(%r, %r)" % (name, self.mem_spec(t)), ("maybe", t)
        if self.match("the", "visitor", "sent"):
            self.no_native("servers")
            if not self.route:
                raise self.err("'the visitor sent' only works inside 'when someone visits the path'")
            return "_visitor(%r)" % self.take().lower(), "text"
        if self.match("the", "message", "text"):
            self.no_native("bots")
            if not self.bot_context:
                raise self.err("'the message text' only works inside a bot message handler")
            return "_bot_field('text')", "text"
        if self.match("the", "message", "author"):
            self.no_native("bots")
            if not self.bot_context:
                raise self.err("'the message author' only works inside a bot message handler")
            return "_bot_field('author')", "text"
        if self.match("the", "message", "channel"):
            self.no_native("bots")
            if not self.bot_context:
                raise self.err("'the message channel' only works inside a bot message handler")
            return "_bot_field('channel')", "text"
        if self.match("the", "message", "is", "from", "a", "bot"):
            self.no_native("bots")
            if not self.bot_context:
                raise self.err("message details only work inside a bot message handler")
            return "_bot_field('is_bot')", "truth"
        if self.match("what", "the", "user", "types"):
            return ("p_ask()" if self.native else "_ask()"), "text"
        for phrase, fn, rt in ((("the", "contents", "of", "the", "file"), "_read", "text"),
                               (("the", "numbers", "in", "the", "file"), "_read_numbers", ("list", "number")),
                               (("the", "lines", "of", "the", "file"), "_read_lines", ("list", "text"))):
            if self.match(*phrase):
                self.no_native("files")
                name = self.take()
                self.need_perm("read", name)
                return "%s(%r)" % (fn, name), rt
        if self.match("an", "empty", "list", "of"):
            lt = ("list", self.parse_type())
            if self.native:
                self.ctype(lt)
                return "p_list_new()", lt
            return "[]", lt
        if self.match("a", "list", "of"):
            items = [self.parse_concat()]
            while self.peek() == "and":
                self.i += 1
                items.append(self.parse_concat())
            t0 = items[0][1]
            for _, it in items:
                if it != t0:
                    raise self.err("everything in a list must be the same kind, but I see %s and %s"
                                   % (tname(t0), tname(it)))
            codes = ", ".join(c for c, _ in items)
            if self.native:
                self.ctype(("list", t0))
                return "p_list_of(%d, (double[]){%s})" % (len(items), codes), ("list", t0)
            return "[%s]" % codes, ("list", t0)
        if self.match("a", "new"):
            self.no_native("records")
            return self.new_record()
        if self.match("no"):
            self.no_native("'maybe' values")
            return "None", ("maybe", self.parse_type())
        if self.match("some"):
            self.no_native("'maybe' values")
            e, t = self.parse_primary()
            return e, ("maybe", t)
        if self.match("entry"):
            idx, it = self.parse_primary()
            self.expect("of")
            lst, lt = self.parse_primary()
            if it != "number" or not (isinstance(lt, tuple) and lt[0] == "list"):
                raise self.err("use: entry NUMBER of LIST")
            return "_at(%s, %s)" % (lst, idx) if not self.native else "p_at(%s, %s)" % (lst, idx), lt[1]
        funcs = self.all_funcs()
        if not self.longest(self.visible()) and not self.longest(funcs):
            self.match("the")
        fpar = {k: v for k, v in funcs.items() if v["params"]}
        fzero = {k: v for k, v in funcs.items() if not v["params"]}
        n = self.longest(fpar, need_of=True) or self.longest(fzero)
        if n:
            return self.call(n, funcs)
        n = self.longest(self.fieldnames, need_of=True)
        if n:
            fname = " ".join(self.t[self.i:self.i + n]).lower()
            self.i += n + 1
            obj, ot = self.parse_primary()
            if not (isinstance(ot, tuple) and ot[0] == "rec") or fname not in self.records[ot[1]]:
                raise self.err("%s does not have a field called '%s'" % (tname(ot), fname))
            return "%s.f_%s" % (obj, _m(fname)), self.records[ot[1]][fname]
        vis = self.visible()
        n = self.longest(vis)
        if n:
            name = " ".join(self.t[self.i:self.i + n]).lower()
            self.i += n
            t, py = vis[name]
            return py, t
        n = self.longest(fpar)
        if n:
            return self.call(n, funcs)
        close = difflib.get_close_matches(w, list(vis) + list(funcs), 1)
        hint = "; did you mean '%s'?" % close[0] if close else ""
        raise self.err("I do not know what '%s' means here%s" % (tok, hint))

    def call(self, n, funcs):
        name = " ".join(self.t[self.i:self.i + n]).lower()
        self.i += n
        fn = funcs[name]
        args = []
        types = []
        if fn["params"]:
            if not self.match("of"):
                names = " with ".join(p for p, _ in fn["params"])
                raise self.err("'%s' needs input: %s of %s" % (name, name, names))
            for k, (pn, pt) in enumerate(fn["params"]):
                if k > 0:
                    self.expect("with")
                a, at = self.parse_primary()
                if pt == "any":
                    if at != "text" and not (isinstance(at, tuple) and at[0] == "list"):
                        raise self.err("'%s' needs text or a list, but got %s" % (name, tname(at)))
                elif at != pt:
                    raise self.err("'%s' needs %s for '%s' but got %s" % (name, tname(pt), pn, tname(at)))
                args.append(a)
                types.append(at)
        py = fn["py"]
        if self.native:
            if name == "length":
                if types[0] == "text":
                    py = "p_len_text"
                elif types[0] == ("list", "number"):
                    py = "p_len_list"
                else:
                    self.ctype(types[0])
            elif name in BUILTINS:
                if BUILTINS[name]["c"] is None:
                    self.no_native("'%s'" % name)
                py = BUILTINS[name]["c"]
        return "%s(%s)" % (py, ", ".join(args)), fn["ret"]

    def new_record(self):
        n = self.longest(self.records)
        if not n:
            raise self.err("I do not know that kind of record; define it with 'a record called ... has ...'")
        rname = " ".join(self.t[self.i:self.i + n]).lower()
        self.i += n
        self.expect("with")
        fields = self.records[rname]
        vals = {}
        while True:
            fn = self.longest(set(fields))
            if not fn:
                raise self.err("%s has these fields: %s" % (rname, ", ".join(fields)))
            fname = " ".join(self.t[self.i:self.i + fn]).lower()
            self.i += fn
            if fname in vals:
                raise self.err("the field '%s' is given twice" % fname)
            v, vt = self.parse_concat()
            if vt != fields[fname]:
                raise self.err("field '%s' is %s but got %s" % (fname, tname(fields[fname]), tname(vt)))
            vals[fname] = v
            if self.peek() == "and" and self.longest(set(fields), off=1):
                self.i += 1
                continue
            break
        missing = [f for f in fields if f not in vals]
        if missing:
            raise self.err("a new %s also needs: %s" % (rname, ", ".join(missing)))
        return "R_%s(%s)" % (_m(rname), ", ".join(vals[f] for f in fields)), ("rec", rname)


# -------------------------------------------------------------------- cli
def compile_source(src, native=False):
    c = Compiler(native=native)
    code = c.compile(src)
    return code, c.perms


def run_source(src, filename="program"):
    py, perms = compile_source(src)
    PERMS.clear()
    PERMS.update(perms)
    _ROUTES.clear()
    _BOT_HANDLERS.clear()
    _MEM["file"] = None
    ns = dict(RUNTIME)
    ns["__builtins__"] = SAFE_BUILTINS
    exec(compile(py, filename, "exec"), ns)


def _native_executable_path(path, windows=None):
    """Return a target-appropriate executable filename for the current OS."""
    if windows is None:
        windows = os.name == "nt"
    executable = os.path.splitext(path)[0]
    if windows and not executable.lower().endswith(".exe"):
        executable += ".exe"
    return executable


def build_native(src, path):
    import os
    import shutil
    import subprocess
    import tempfile
    code, _ = compile_source(src, native=True)
    cc = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
    if not cc:
        raise PlainlyRuntimeError("native needs a C compiler (gcc, cc or clang); none was found")
    exe = _native_executable_path(path)
    with tempfile.TemporaryDirectory() as d:
        cfile = os.path.join(d, "program.c")
        with open(cfile, "w") as f:
            f.write(code)
        r = subprocess.run([cc, "-O2", "-o", exe, cfile, "-lm"], capture_output=True, text=True)
        if r.returncode != 0:
            raise PlainlyRuntimeError("the C compiler failed:\n" + r.stderr)
    return exe


FIX_ALIASES = {"print": "say", "echo": "say", "display": "say", "println": "say", "else": "otherwise",
               "elif": "otherwise if", "elseif": "otherwise if", "return": "give back", "var": "let",
               "const": "let", "endif": "end if", "endwhile": "end while", "endfor": "end for",
               "enddefine": "end define", "endrepeat": "end repeat", "endwhen": "end when"}
FIX_KEYWORDS = ["note", "say", "let", "set", "add", "subtract", "if", "otherwise", "while", "repeat", "for",
                "define", "give", "allow", "write", "run", "when", "reply", "show", "start", "remember",
                "end", "a", "an"]
FIX_ENDS = ["if", "while", "repeat", "for", "define", "when"]


def _fix_symbols(line):
    line = re.sub(r'"([^"]*)"', lambda m: "the words %s end words" % m.group(1).strip(), line)

    def clean(seg):
        return re.sub(r"[:;()\[\]{}]", " ", seg.replace("_", " "))
    out, pos = [], 0
    for m in TEXT_SPAN.finditer(line):
        out += [clean(line[pos:m.start()]), m.group(0)]
        pos = m.end()
    out.append(clean(line[pos:]))
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


def _fix_line(raw):
    line = raw.strip()
    if not line or line.lower().startswith("note"):
        return line
    t = _fix_symbols(line).split(" ")
    w = t[0].lower()
    if w in FIX_ALIASES:
        if w in ("var", "const") and "=" in t:
            t[t.index("=")] = "be"
        t[0] = FIX_ALIASES[w]
    elif w not in FIX_KEYWORDS:
        c = difflib.get_close_matches(w, [k for k in FIX_KEYWORDS if len(k) > 2], 1, 0.6)
        if c:
            t[0] = c[0]
    if t[0].lower() == "end" and len(t) > 1 and t[1].lower() not in FIX_ENDS:
        c = difflib.get_close_matches(t[1].lower(), FIX_ENDS, 1, 0.6)
        if c:
            t[1] = c[0]
    line = " ".join(t)
    f, f2, last = t[0].lower(), (t[1].lower() if len(t) > 1 else ""), t[-1].lower()
    if (f == "if" or (f == "otherwise" and f2 == "if")) and last != "then":
        line += " then"
    elif (f == "while" or (f == "for" and f2 == "each") or f == "repeat") and last != "do":
        line += " do"
    return line


def _replace_outside_text(line, old, new):
    parts, pos = [], 0
    for m in TEXT_SPAN.finditer(line):
        parts += [(line[pos:m.start()], False), (m.group(0), True)]
        pos = m.end()
    parts.append((line[pos:], False))
    done = False
    out = []
    for seg, is_text in parts:
        if not is_text and not done:
            seg2 = re.sub(r"(?i)\b" + re.escape(old) + r"\b", new, seg, count=1)
            done = seg2 != seg
            seg = seg2
        out.append(seg)
    return "".join(out)


def autofix(src):
    """Repair common mistakes. Never adds permissions: those are the programmer's decision.
    Returns (fixed text, list of notes, whether the fixed program has no problems)."""
    lines = src.split("\n")
    notes = []
    for i, raw in enumerate(lines):
        if raw.strip():
            new = _fix_line(raw)
            if new != raw.strip():
                notes.append("line %d: %s  ->  %s" % (i + 1, raw.strip(), new))
            lines[i] = new
    ok = False
    for _ in range(40):
        try:
            compile_source("\n".join(lines))
            ok = True
            break
        except PlainlyError as e:
            m, n = e.msg, (e.line or 0) - 1
            g = re.search(r"needs 'end (\w+)'", m)
            h = re.search(r"closes '(\w+)', but .*needs 'end (\w+)'", m)
            k = re.search(r"'([^']+)'.*did you mean '([^']+)'", m)
            if "never closed" in m and g:
                lines.append("end " + g.group(1))
                notes.append("added 'end %s' at the end" % g.group(1))
            elif h and n >= 0:
                lines[n] = re.sub(r"(?i)^end\s+\w+", "end " + h.group(2), lines[n])
                notes.append("line %d: end %s  ->  end %s" % (n + 1, h.group(1), h.group(2)))
            elif "'plus' needs two numbers" in m and "followed by" in m and n >= 0:
                lines[n] = _replace_outside_text(lines[n], "plus", "followed by")
                notes.append("line %d: plus  ->  followed by (to join text)" % (n + 1))
            elif k and n >= 0 and difflib.SequenceMatcher(None, k.group(1).lower(), k.group(2)).ratio() >= 0.75:
                lines[n] = _replace_outside_text(lines[n], k.group(1), k.group(2))
                notes.append("line %d: %s  ->  %s" % (n + 1, k.group(1), k.group(2)))
            else:
                break
        except Exception:
            break
    return "\n".join(lines), notes, ok


def fix_file(path, src):
    import os
    text, notes, ok = autofix(src)
    if not notes:
        print("I found nothing I know how to fix.")
        return 0 if ok else 1
    out = os.path.splitext(path)[0] + ".fixed.plain"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")
    print("I made %d fix%s:" % (len(notes), "" if len(notes) == 1 else "es"))
    for n in notes:
        print("  " + n)
    print("Saved as %s. Your original is unchanged." % out)
    if ok:
        print("The fixed program has no problems. Run it with: python3 plainly.py run %s" % out)
        return 0
    try:
        compile_source(text)
    except PlainlyError as e:
        print("One problem is left, and it needs you.\nline %d: %s" % (e.line or 0, e.msg))
    return 1


def main(argv):
    if len(argv) == 3 and argv[1] in ("core-compile", "core-execute"):
        try:
            from plainly_core_bytecode import CoreBytecodeError, compile_file as core_compile_file, run_file as core_execute_file
            if argv[1] == "core-compile":
                output = core_compile_file(argv[2])
                print("Compiled %s to %s (independent Plainly core bytecode v1)." % (argv[2], output))
            else:
                sys.stdout.write(core_execute_file(argv[2]))
            return 0
        except (CoreBytecodeError, PlainlyRuntimeError, OSError) as exc:
            print("Plainly core bytecode error: %s" % exc, file=sys.stderr)
            return 1
    if len(argv) >= 2 and argv[1] in ("core-check", "core-run"):
        if len(argv) != 3:
            print("Usage: plainly %s FILE.plain" % argv[1], file=sys.stderr)
            return 2
        try:
            from plainly_core import PlainlyCoreError, check_file, run_file
            if argv[1] == "core-check":
                check_file(argv[2])
                print("Plainly Core: source is syntactically valid.")
            else:
                sys.stdout.write(run_file(argv[2]))
            return 0
        except (PlainlyCoreError, OSError) as exc:
            print("Plainly Core error: %s" % exc, file=sys.stderr)
            return 1
    if len(argv) >= 2 and argv[1] == "init":
        if len(argv) not in (4, 5):
            print("Usage: plainly init app|game NAME [PARENT_FOLDER]", file=sys.stderr)
            return 2
        try:
            from plainly_project import ProjectError, create_project
            folder = create_project(argv[3], argv[2], argv[4] if len(argv) == 5 else ".")
            print("Created Plainly %s project: %s" % (argv[2], folder))
            print("Next: plainly project-check %s" % folder)
            print("Native platform packaging is not implemented yet; see PLATFORM_SUPPORT.md.")
            return 0
        except (ProjectError, OSError) as exc:
            print("Plainly project error: %s" % exc, file=sys.stderr)
            return 1
    if len(argv) in (2, 3) and argv[1] == "project-check":
        try:
            from plainly_project import ProjectError, check_project
            manifest = check_project(argv[2] if len(argv) == 3 else ".")
            print("Project is valid: %s (%s)" % (manifest["name"], manifest["kind"]))
            print("Targets: %s" % ", ".join(manifest["targets"]))
            print("Security defaults: capabilities=%s, network=%s, filesystem=%s, native_extensions=%s" % (
                ", ".join(manifest["security"]["capabilities"]) or "none",
                manifest["security"]["network"],
                manifest["security"]["filesystem"],
                manifest["security"]["native_extensions"],
            ))
            return 0
        except (ProjectError, OSError) as exc:
            print("Plainly project error: %s" % exc, file=sys.stderr)
            return 1
    if len(argv) == 2 and argv[1] in ("--version", "version"):
        print("Plainly " + VERSION)
        return 0
    if len(argv) == 2:
        argv = [argv[0], "run", argv[1]]
    if len(argv) < 3 or argv[1] not in ("run", "check", "build", "c", "native", "fix", "compile", "execute"):
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    options = argv[3:]
    config = {"host": None, "port": None, "allowed_hosts": []}
    index = 0
    while index < len(options):
        option = options[index]
        if option not in ("--host", "--port", "--allow-host") or index + 1 >= len(options):
            print("Plainly run options: --host ADDRESS --port PORT --allow-host DOMAIN (repeatable)", file=sys.stderr)
            return 2
        value = options[index + 1]
        if not value or value.startswith("--"):
            print("Plainly run option %s needs a value" % option, file=sys.stderr)
            return 2
        if option == "--host":
            config["host"] = value
        elif option == "--port":
            try:
                port_value = int(value)
            except ValueError:
                print("--port must be a whole number from 1 to 65535", file=sys.stderr)
                return 2
            if not 1 <= port_value <= 65535:
                print("--port must be a whole number from 1 to 65535", file=sys.stderr)
                return 2
            config["port"] = port_value
        else:
            if not re.fullmatch(r"[A-Za-z0-9.:-]+", value):
                print("--allow-host must be a host name or IP address", file=sys.stderr)
                return 2
            config["allowed_hosts"].append(value)
        index += 2
    if cmd != "run" and options:
        print("run options can only be used with the run command", file=sys.stderr)
        return 2
    _SERVER_CONFIG.clear()
    _SERVER_CONFIG.update(config)
    if cmd in ("compile", "execute"):
        from plainly_bytecode import BytecodeError, compile_file, run_file
        try:
            if cmd == "compile":
                output = compile_file(path)
                print("Compiled %s to %s (Plainly bytecode v1)." % (path, output))
            else:
                run_file(path)
        except PlainlyError as e:
            where = "line %d: " % e.line if e.line else ""
            print("Plainly found a problem.\\n%s%s" % (where, e.msg), file=sys.stderr)
            return 1
        except (BytecodeError, OSError) as e:
            print("Plainly bytecode error: %s" % e, file=sys.stderr)
            return 1
        return 0
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        if cmd == "build":
            print(compile_source(src)[0])
        elif cmd == "c":
            print(compile_source(src, native=True)[0])
        elif cmd == "check":
            compile_source(src)
            print("No problems found.")
        elif cmd == "fix":
            return fix_file(path, src)
        elif cmd == "native":
            exe = build_native(src, path)
            if os.name == "nt":
                run_target = os.path.relpath(os.path.abspath(exe), os.getcwd()).replace("/", "\\")
                print('Built %s. Run it from PowerShell with: & ".\\%s"' % (exe, run_target))
            else:
                print("Built %s. Run it with: ./%s" % (exe, exe))
        else:
            run_source(src, path)
    except PlainlyError as e:
        lines = src.splitlines()
        where = "line %d: " % e.line if e.line else ""
        print("Plainly found a problem.\n%s%s" % (where, e.msg), file=sys.stderr)
        if e.line and e.line <= len(lines):
            print("    " + lines[e.line - 1].strip(), file=sys.stderr)
        fx = autofix(src)
        if fx[2]:
            if cmd == "run" and sys.stdin.isatty() and sys.stdout.isatty():
                print("I can fix this:", file=sys.stderr)
                for n in fx[1]:
                    print("  " + n, file=sys.stderr)
                if input("Fix it and run? [y/N] ").strip().lower() in ("y", "yes"):
                    fixed = os.path.splitext(path)[0] + ".fixed.plain"
                    with open(fixed, "w", encoding="utf-8") as f:
                        f.write(fx[0] + "\n")
                    print("Saved as %s. Running it now." % fixed)
                    return main([argv[0], "run", fixed])
            else:
                print("Tip: Plainly can probably fix this. Run: python3 plainly.py fix %s" % path, file=sys.stderr)
        return 1
    except PlainlyRuntimeError as e:
        print("Plainly stopped the program: %s" % e, file=sys.stderr)
        return 1
    except ZeroDivisionError:
        print("Plainly stopped the program: cannot divide by zero", file=sys.stderr)
        return 1
    return 0


def cli():
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    cli()
