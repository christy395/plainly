#!/usr/bin/env python3
"""Small process adapter for hosting providers integrating Plainly.

This module manages one child process per app. It deliberately does not claim
to provide container, filesystem, network, CPU, or memory isolation.
"""
import os
import re
import signal
import stat
import subprocess
import sys
import threading
import time


class HostError(RuntimeError):
    """Invalid or unavailable hosting operation."""


_APP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")


class PlainlyHost:
    """In-memory process manager that a provider can wrap in its own control plane.

    Give every app a private working directory. Apply container/cgroup limits
    and network/filesystem policy outside this adapter before accepting
    untrusted customer programs.
    """

    def __init__(self):
        self._jobs = {}
        self._lock = threading.RLock()

    @staticmethod
    def _validate_workspace(program, workdir):
        workspace_input = os.path.abspath(workdir)
        if os.path.islink(workspace_input):
            raise HostError("the app workspace must not be a symbolic link")
        workspace = os.path.realpath(workspace_input)
        if not os.path.isdir(workspace):
            raise HostError("the app workspace must be an existing private directory")
        source_input = os.path.abspath(program if os.path.isabs(program)
                                       else os.path.join(workspace, program))
        if os.path.islink(source_input):
            raise HostError("the Plainly program must not be a symbolic link")
        source = os.path.realpath(source_input)
        try:
            inside = os.path.commonpath([workspace, source]) == workspace
        except ValueError:
            inside = False
        if not inside or not os.path.isfile(source):
            raise HostError("the Plainly program must be a regular .plain file inside its workspace")
        if not source.lower().endswith(".plain"):
            raise HostError("hosting currently accepts Plainly .plain source files")
        return workspace, source

    @staticmethod
    def _child_environment(extra):
        # Do not pass the host control-plane's entire environment to tenants.
        allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        for key, value in (extra or {}).items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", key):
                raise HostError("environment variable names must use uppercase letters, digits and underscores")
            if not isinstance(value, str) or "\x00" in value:
                raise HostError("environment variable values must be text without null characters")
            env[key] = value
        return env

    def start(self, app_id, program, workdir, env=None):
        """Start one Plainly program in its own process and private workspace."""
        if not isinstance(app_id, str) or not _APP_ID.fullmatch(app_id):
            raise HostError("app_id must be 1 to 63 safe letters, digits, dots, underscores or hyphens")
        workspace, source = self._validate_workspace(program, workdir)
        child_env = self._child_environment(env)
        with self._lock:
            existing = self._jobs.get(app_id)
            if existing and existing["process"].poll() is None:
                raise HostError("this app is already running")
            log_path = os.path.join(workspace, "plainly-runtime.log")
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(log_path, flags, 0o600)
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    os.close(fd)
                    raise HostError("the app log must be a regular file without hard links")
                log_handle = os.fdopen(fd, "ab", buffering=0)
            except OSError:
                raise HostError("could not open the app log safely") from None
            runtime = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plainly.py")
            command = [sys.executable, runtime, "run", os.path.basename(source)]
            try:
                process = subprocess.Popen(
                    command,
                    cwd=workspace,
                    env=child_env,
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                    start_new_session=(os.name != "nt"),
                )
            except OSError:
                log_handle.close()
                raise HostError("could not start the Plainly process") from None
            self._jobs[app_id] = {
                "process": process,
                "log": log_handle,
                "started": time.time(),
                "program": os.path.basename(source),
                "workdir": workspace,
                "log_path": log_path,
            }
            return self.status(app_id)

    def status(self, app_id):
        with self._lock:
            job = self._jobs.get(app_id)
            if not job:
                return {"app_id": app_id, "state": "not_found"}
            process = job["process"]
            code = process.poll()
            return {
                "app_id": app_id,
                "state": "running" if code is None else "exited",
                "pid": process.pid,
                "return_code": code,
                "uptime_seconds": max(0, int(time.time() - job["started"])),
                "program": job["program"],
            }

    def stop(self, app_id, timeout=10):
        with self._lock:
            job = self._jobs.get(app_id)
            if not job:
                return {"app_id": app_id, "state": "not_found"}
            process = job["process"]
            if process.poll() is None:
                try:
                    if os.name == "nt":
                        process.terminate()
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=max(0, float(timeout)))
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
            try:
                job["log"].close()
            except Exception:
                pass
            return self.status(app_id)

    def logs(self, app_id, max_bytes=65536):
        """Return the most recent UTF-8 log text for one app."""
        if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 262144:
            raise HostError("max_bytes must be from 1 to 262144")
        with self._lock:
            job = self._jobs.get(app_id)
            if not job:
                raise HostError("the app is not known to this host adapter")
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(job["log_path"], flags)
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    os.close(fd)
                    raise HostError("the app log is not a safe regular file")
                with os.fdopen(fd, "rb") as handle:
                    handle.seek(max(0, info.st_size - max_bytes))
                    return handle.read(max_bytes).decode("utf-8", "replace")
            except OSError:
                raise HostError("could not read the app log safely") from None

    def close(self):
        """Stop all processes owned by this adapter."""
        with self._lock:
            app_ids = list(self._jobs)
        for app_id in app_ids:
            self.stop(app_id)
