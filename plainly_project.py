"""Secure project scaffolding and manifest validation for Plainly.

This module does not compile native mobile/desktop packages. It defines a
portable project format and validates project inputs before future platform
toolchains are invoked.
"""
import json
import os
import re
import stat

PROJECT_FILE = "plainly.project.json"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 1024 * 1024
PROJECT_FORMAT = 1
TARGETS = ("android", "ios", "windows", "linux", "macos")
CAPABILITIES = (
    "audio", "camera", "files-read", "files-write", "graphics",
    "location", "microphone", "network-client", "notifications",
)
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")


class ProjectError(Exception):
    """A project manifest or project layout is invalid."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProjectError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def _read_regular_file(path, limit):
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ProjectError("cannot access %s: %s" % (os.path.basename(path), exc)) from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProjectError("%s must be a regular file, not a link or special file" % os.path.basename(path))
    if info.st_size > limit:
        raise ProjectError("%s is larger than the %d-byte project limit" % (os.path.basename(path), limit))
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise ProjectError("could not safely open %s" % os.path.basename(path)) from None
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ProjectError("%s must be a regular file with one hard link" % os.path.basename(path))
        if opened.st_size > limit:
            raise ProjectError("%s exceeds the project size limit" % os.path.basename(path))
        with os.fdopen(fd, "rb") as stream:
            fd = None
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ProjectError("%s exceeds the project size limit" % os.path.basename(path))
        return data
    finally:
        if fd is not None:
            os.close(fd)


def default_manifest(name, kind):
    return {
        "format": PROJECT_FORMAT,
        "name": name,
        "kind": kind,
        "entry": "main.plain",
        "targets": list(TARGETS),
        "security": {
            "capabilities": [],
            "network": "deny",
            "filesystem": "project-only",
            "native_extensions": False,
        },
    }


def validate_manifest(data):
    if not isinstance(data, dict):
        raise ProjectError("project manifest must be a JSON object")
    allowed = {"format", "name", "kind", "entry", "targets", "security"}
    extra = set(data) - allowed
    missing = allowed - set(data)
    if extra:
        raise ProjectError("unknown manifest field(s): %s" % ", ".join(sorted(extra)))
    if missing:
        raise ProjectError("missing manifest field(s): %s" % ", ".join(sorted(missing)))
    if type(data["format"]) is not int or data["format"] != PROJECT_FORMAT:
        raise ProjectError("unsupported project format; expected %d" % PROJECT_FORMAT)
    if not isinstance(data["name"], str) or not NAME_RE.fullmatch(data["name"]):
        raise ProjectError("name must start with a letter and contain only letters, numbers, _ or - (max 48)")
    if data["kind"] not in ("app", "game"):
        raise ProjectError("kind must be app or game")
    entry = data["entry"]
    if not isinstance(entry, str) or not entry.endswith(".plain") or entry in ("", ".", ".."):
        raise ProjectError("entry must be a simple .plain filename")
    if "/" in entry or "\\" in entry or entry.startswith("."):
        raise ProjectError("entry must stay inside the project folder")
    targets = data["targets"]
    if not isinstance(targets, list) or not targets:
        raise ProjectError("targets must be a non-empty list")
    if any(not isinstance(target, str) or target not in TARGETS for target in targets):
        raise ProjectError("targets may only contain: %s" % ", ".join(TARGETS))
    if len(set(targets)) != len(targets):
        raise ProjectError("targets must not contain duplicates")
    security = data["security"]
    if not isinstance(security, dict):
        raise ProjectError("security must be an object")
    required_security = {"capabilities", "network", "filesystem", "native_extensions"}
    if set(security) != required_security:
        raise ProjectError("security must contain exactly: %s" % ", ".join(sorted(required_security)))
    capabilities = security["capabilities"]
    if not isinstance(capabilities, list) or any(not isinstance(x, str) or x not in CAPABILITIES for x in capabilities):
        raise ProjectError("security.capabilities contains an unknown capability")
    if len(set(capabilities)) != len(capabilities):
        raise ProjectError("security.capabilities must not contain duplicates")
    if security["network"] not in ("deny", "allow-listed"):
        raise ProjectError("security.network must be deny or allow-listed")
    if security["filesystem"] not in ("none", "project-only"):
        raise ProjectError("security.filesystem must be none or project-only")
    if type(security["native_extensions"]) is not bool:
        raise ProjectError("security.native_extensions must be yes/no (JSON true/false)")
    if security["network"] == "allow-listed" and "network-client" not in capabilities:
        raise ProjectError("allow-listed network access requires the network-client capability")
    if security["filesystem"] == "project-only" and not ({"files-read", "files-write"} & set(capabilities)):
        # Project-only is the boundary; no access is granted unless a file capability is listed.
        pass
    return data


def load_project(directory="."):
    root = os.path.abspath(directory)
    if not os.path.isdir(root) or os.path.islink(root):
        raise ProjectError("project path must be a real directory")
    manifest_path = os.path.join(root, PROJECT_FILE)
    raw = _read_regular_file(manifest_path, MAX_MANIFEST_BYTES)
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, ProjectError):
            raise
        raise ProjectError("project manifest is not valid UTF-8 JSON: %s" % exc) from None
    validate_manifest(data)
    entry_path = os.path.join(root, data["entry"])
    source = _read_regular_file(entry_path, MAX_SOURCE_BYTES)
    try:
        source_text = source.decode("utf-8")
    except UnicodeDecodeError:
        raise ProjectError("entry source must be UTF-8 text") from None
    return data, source_text


def create_project(name, kind, directory="."):
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ProjectError("project name must start with a letter and contain only letters, numbers, _ or - (max 48)")
    if kind not in ("app", "game"):
        raise ProjectError("project type must be app or game")
    root = os.path.abspath(os.path.join(directory, name))
    if os.path.exists(root):
        raise ProjectError("destination already exists: %s" % root)
    os.makedirs(root, mode=0o700)
    if kind == "game":
        source = (
            "note a starter game loop; graphics and input APIs are a future feature\n"
            "say the words Your Plainly game is ready to build. end words\n"
        )
    else:
        source = (
            "note a starter app; native user interface APIs are a future feature\n"
            "say the words Your Plainly app is ready to build. end words\n"
        )
    manifest = default_manifest(name, kind)
    try:
        with open(os.path.join(root, PROJECT_FILE), "x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
        with open(os.path.join(root, "main.plain"), "x", encoding="utf-8") as stream:
            stream.write(source)
        os.chmod(os.path.join(root, PROJECT_FILE), 0o600)
        os.chmod(os.path.join(root, "main.plain"), 0o600)
    except BaseException:
        # Remove only files created by this operation; never overwrite existing content.
        for filename in (PROJECT_FILE, "main.plain"):
            try:
                os.unlink(os.path.join(root, filename))
            except OSError:
                pass
        try:
            os.rmdir(root)
        except OSError:
            pass
        raise
    return root


def check_project(directory="."):
    manifest, source = load_project(directory)
    try:
        from plainly import compile_source, PlainlyError
        compile_source(source)
    except ImportError:
        raise ProjectError("Plainly compiler is unavailable") from None
    except PlainlyError as exc:
        raise ProjectError("entry program is invalid: %s" % exc) from None
    return manifest
