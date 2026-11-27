#!/usr/bin/env python3
"""Plainly test suite. Run from the project folder: python3 tests/run_tests.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PL = os.path.join(ROOT, "plainly.py")
EX = os.path.join(ROOT, "examples")
passed = failed = 0


def plainly(*args, cwd=None):
    r = subprocess.run([sys.executable, PL, *args], capture_output=True, text=True, cwd=cwd, timeout=60)
    return r.returncode, r.stdout, r.stderr


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("  pass  " + name)
    else:
        failed += 1
        print("  FAIL  " + name + ("\n        " + detail if detail else ""))


def program(d, name, text):
    path = os.path.join(d, name)
    with open(path, "w") as f:
        f.write(text)
    return path


def main():
    d = tempfile.mkdtemp()
    try:
        print("Examples")
        code, out, _ = plainly("run", os.path.join(EX, "hello.plain"))
        check("hello", out == "Hello, world.\n")
        code, out, _ = plainly("run", os.path.join(EX, "shop.plain"))
        check("shop (records, functions, loops)", out.splitlines()[:2] == ["Total is 26", "That is a big order"], out)
        code, out, _ = plainly("run", os.path.join(EX, "fizz.plain"))
        check("fizz", out.startswith("FizzBuzz\nFizz\nBuzz\n7"), out)
        code, out, _ = plainly("run", os.path.join(EX, "maybe.plain"))
        check("maybe values", "I found 43" in out and "second is not a number" in out, out)
        code, out, _ = plainly("run", os.path.join(EX, "speed.plain"))
        check("speed (python)", "17984" in out, out)
        code, out, _ = plainly("run", os.path.join(EX, "files.plain"), cwd=EX) if False else (0, "", "")

        print("Lessons and easier text")
        want = ["Hello! I am your first program.\nYou can say numbers too\n42\n", "Sam is 12\nNext year Sam is 14\n",
                "Great score!\nBetween 5 and 9.\n",
                "Hip hip hooray!\nHip hip hooray!\nHip hip hooray!\nCounting 1\nCounting 2\nCounting 3\n",
                "I like cat\nI like dog\nI like fish\nI like bird\nI have 4 pets\ncat\n", "42\n9\n"]
        for i, w in enumerate(want, 1):
            code, out, err = plainly("run", os.path.join(EX, "lessons", "lesson%d.plain" % i))
            check("lesson %d" % i, out == w, out + err)
        p = program(d, "ez.plain", "say the words Total followed by 5\nsay the words Hello end words contains the words ELL end words\n")
        check("text ends by itself, contains ignores capitals", plainly("run", p)[1] == "Total 5\nyes\n")

        print("Errors are caught and explained")
        for f, word in (("bad_types.plain", "followed by"), ("bad_permission.plain", "asked permission"),
                        ("bad_return.plain", "never gives back")):
            code, out, err = plainly("run", os.path.join(EX, f))
            check(f, code == 1 and word in err, err)

        print("Names and text (the words bug)")
        p = program(d, "names.plain", "let end be 5\nlet from be 3\nlet the cat be 2\nsay end plus from plus the cat\n")
        check("keywords and 'the' inside names", plainly("run", p)[1] == "10\n", plainly("run", p)[2])
        p = program(d, "shadow.plain", "let length be 4\nsay length\nsay length of a list of 1 and 2 and 3\n")
        check("a name can match a built-in", plainly("run", p)[1] == "4\n3\n", plainly("run", p)[2])
        p = program(d, "symbols.plain", "say the words Note: it costs (5) dollars; ok end words\n")
        check("symbols allowed inside text", plainly("run", p)[1] == "Note: it costs (5) dollars; ok\n", plainly("run", p)[2])
        p = program(d, "sym2.plain", "let x be 5:\n")
        check("symbols outside text are refused", plainly("run", p)[0] == 1)

        print("Autofix")
        cases = [
            ("habits", 'print "Hello"\nvar x = 5\nif x is 5\nsay "five"\nendif\n', "Hello\nfive\n"),
            ("missing end", "for each n in a list of 1 and 2 do\nsay n\n", "1\n2\n"),
            ("typo keyword", "sya the words hi end words\n", "hi\n"),
            ("plus on text", "let a be 5\nsay the words Total end words plus a\n", "Total 5\n"),
            ("typo name", "let total be 5\nsay totl\n", "5\n"),
            ("wrong end", "let n be 1\nwhile n is less than 3 do\nadd 1 to n\nend if\nsay n\n", "3\n"),
        ]
        for name, src, want in cases:
            p = program(d, name.replace(" ", "_") + ".plain", src)
            code, out, err = plainly("fix", p)
            fixed = p[:-6] + ".fixed.plain"
            got = plainly("run", fixed)[1] if os.path.exists(fixed) else ""
            check("fix: " + name, got == want, out + err + got)
        p = program(d, "perm.plain", "let s be the contents of the file secret.txt\nsay s\n")
        code, out, err = plainly("fix", p)
        check("fix never adds permissions", not os.path.exists(p[:-6] + ".fixed.plain") or
              "allow" not in open(p[:-6] + ".fixed.plain").read())

        print("Memory")
        p = program(d, "mem.plain", "allow remembering in the file mem.json\n"
                    "let n be what I remember called n as a number or else 0\n"
                    "remember n plus 1 as n\nsay n plus 1\n")
        first = plainly("run", p, cwd=d)[1]
        second = plainly("run", p, cwd=d)[1]
        check("remembers between runs", (first, second) == ("1\n", "2\n"), first + second)

        print("Server")
        p = program(d, "srv.plain", "when someone visits the path hi do\n"
                    "reply with the words Hello end words followed by the visitor sent name\nend when\n"
                    "when someone visits the path home do\nshow a heading with the words Hi end words\n"
                    "show a box called who\nshow a paragraph called answer with the words ready end words\n"
                    "show a button with the words Go end words that asks the path hi and shows the reply in the paragraph called answer\n"
                    "reply with the page\nend when\nstart the server on port 8095\n")
        proc = subprocess.Popen([sys.executable, PL, "run", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        try:
            body = urllib.request.urlopen("http://127.0.0.1:8095/hi?name=Ann").read().decode()
            page = urllib.request.urlopen("http://127.0.0.1:8095/").read().decode()
            check("server reply", body == "Hello Ann", body)
            check("server page has box and button", 'name="who"' in page and "data-path=" in page)
            try:
                urllib.request.urlopen("http://127.0.0.1:8095/nope")
                check("404", False)
            except urllib.error.HTTPError as e:
                check("404 for unknown page", e.code == 404)
            req = urllib.request.Request("http://127.0.0.1:8095/", headers={"Host": "evil.example"})
            try:
                urllib.request.urlopen(req)
                check("wrong host refused", False)
            except urllib.error.HTTPError as e:
                check("wrong host refused", e.code == 403)
        finally:
            proc.terminate()
            proc.wait()

        print("Hosting mode")
        p = program(d, "host.plain", "when someone visits the path hi do\nreply with the words Hello\nend when\n"
                    "when someone visits the path spin do\nlet n be 0\nwhile true do\nadd 1 to n\nend while\n"
                    "reply with the words never\nend when\nstart the server on port 8095\n")
        code, out, err = plainly("run", p, "--host", "0.0.0.0")
        check("public address needs allowed hosts", code == 1 and "allow-host" in err, err)
        env = dict(os.environ, PORT="8092")
        proc = subprocess.Popen([sys.executable, PL, "run", p, "--host", "127.0.0.1", "--allow-host", "example.test"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        time.sleep(1.5)

        def fetch(path, host=None):
            req = urllib.request.Request("http://127.0.0.1:8092" + path, headers={"Host": host} if host else {})
            try:
                r = urllib.request.urlopen(req, timeout=40)
                return r.status, r.read().decode(), r.headers.get("Server", "")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode(), ""
        try:
            check("PORT setting is used", fetch("/hi")[:2] == (200, "Hello"))
            check("allowed host accepted", fetch("/hi", "example.test")[:2] == (200, "Hello"))
            check("other host refused", fetch("/hi", "evil.example")[0] == 403)
            check("health check", fetch("/healthz")[:2] == (200, "ok"))
            check("server does not reveal Python", "Python" not in fetch("/hi")[2])
            st, body, _ = fetch("/spin")
            check("endless page is stopped", st == 500 and "took too long" in body, body)
            check("server still works afterwards", fetch("/hi")[:2] == (200, "Hello"))
        finally:
            proc.terminate()
            proc.wait()

        print("Bots (against local imitations of Telegram and Discord)")
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import mock_bots

        def wait_for(cond, secs=10):
            end = time.time() + secs
            while time.time() < end and not cond():
                time.sleep(0.1)
            return cond()
        p = program(d, "perm.plain", "when a Telegram message arrives do\nreply with the words hi\nend when\n")
        check("bot handler needs permission", plainly("run", p)[0] == 1 and "asked permission" in plainly("run", p)[2])
        p = program(d, "early.plain", "allow running a Discord bot\nstart the Discord bot\n")
        check("bot cannot start without a handler", "before starting" in plainly("run", p)[2])
        code, out, err = plainly("run", os.path.join(EX, "telegram_bot.plain"))
        check("missing token explains what to do", code == 1 and "PLAINLY_SECRET_TELEGRAM_TOKEN" in err, err)
        tg = mock_bots.TelegramMock(8101)
        tg.updates = [{"update_id": 10, "message": {"text": "Hello there", "from": {"first_name": "Ann"}, "chat": {"id": 111}}},
                      {"update_id": 11, "message": {"text": "what is this", "from": {"first_name": "Ann"}, "chat": {"id": 111}}},
                      {"update_id": 12, "message": {"photo": []}}]
        env = dict(os.environ, PLAINLY_SECRET_TELEGRAM_TOKEN="TESTTOKEN", PLAINLY_TELEGRAM_API="http://127.0.0.1:8101")
        proc = subprocess.Popen([sys.executable, PL, "run", os.path.join(EX, "telegram_bot.plain")], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_for(lambda: len(tg.sent) >= 2)
            time.sleep(1)
            check("telegram: replies", [m["text"] for m in tg.sent] == ["Hello Ann", "You said what is this"], str(tg.sent))
            check("telegram: sent to the right chat", all(str(m["chat_id"]) == "111" for m in tg.sent))
            check("telegram: moves past handled updates", 13 in tg.offsets, str(tg.offsets))
        finally:
            proc.terminate()
            proc.wait()
        env["PLAINLY_SECRET_TELEGRAM_TOKEN"] = "WRONG"
        r = subprocess.run([sys.executable, PL, "run", os.path.join(EX, "telegram_bot.plain")], env=env,
                           capture_output=True, text=True, timeout=20)
        check("telegram: wrong token is reported", "token is not valid" in r.stdout, r.stdout + r.stderr)
        dc = mock_bots.DiscordMock(8102, 8103)
        env = dict(os.environ, PLAINLY_SECRET_DISCORD_TOKEN="TESTTOKEN", PLAINLY_DISCORD_API="http://127.0.0.1:8102",
                   PLAINLY_DISCORD_GATEWAY="ws://127.0.0.1:8103/")
        proc = subprocess.Popen([sys.executable, PL, "run", os.path.join(EX, "discord_bot.plain")], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            wait_for(lambda: len(dc.posts) >= 1 and dc.heartbeats >= 1)
            time.sleep(1.5)
            check("discord: replies once, ignoring bots and itself", len(dc.posts) == 1 and dc.posts[0][1] == {"content": "Hello Bob"}, str(dc.posts))
            check("discord: sent to the right channel with the token", dc.posts and dc.posts[0][0] == "/channels/999/messages" and dc.posts[0][2] == "Bot TESTTOKEN")
            check("discord: identifies with token and intents", dc.identify and dc.identify[0]["token"] == "TESTTOKEN" and dc.identify[0]["intents"] == 37376, str(dc.identify))
            check("discord: keeps the connection alive", dc.heartbeats >= 1)
            check("discord: user agent", dc.posts and dc.posts[0][3].startswith("DiscordBot ("))
        finally:
            proc.terminate()
            proc.wait()

        print("Native")
        gcc = shutil.which("gcc") or shutil.which("cc")
        if gcc:
            code, out, err = plainly("c", os.path.join(EX, "fizz.plain"))
            c = os.path.join(d, "t.c")
            open(c, "w").write(out)
            r = subprocess.run([gcc, "-fsyntax-only", c], capture_output=True, text=True)
            check("generated C is valid", r.returncode == 0, r.stderr)
        else:
            print("  skip  no C compiler found")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
