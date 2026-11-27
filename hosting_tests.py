#!/usr/bin/env python3
"""Regression tests for public website configuration and provider process lifecycle."""
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import plainly_host

ROOT = os.path.dirname(os.path.abspath(__file__))
PLAINLY = os.path.join(ROOT, "plainly.py")


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def request(port, path, host, timeout=3):
    """Make a direct HTTP request to loopback without consulting proxy settings."""
    payload = (
        "GET %s HTTP/1.1\r\nHost: %s:%d\r\n"
        "Connection: close\r\n\r\n" % (path, host, port)
    ).encode("ascii")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(payload)
        chunks = []
        while True:
            chunk = connection.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
    response = b"".join(chunks)
    header, separator, body = response.partition(b"\r\n\r\n")
    if not separator:
        raise RuntimeError("local HTTP server returned an incomplete response")
    status_line = header.split(b"\r\n", 1)[0].split()
    if len(status_line) < 2:
        raise RuntimeError("local HTTP server returned an invalid status line")
    return int(status_line[1]), body.decode("utf-8")


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="plainly-host-test-")
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        shutil.rmtree(self.directory, ignore_errors=True)

    def write(self, name, source):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        return path

    def test_public_host_mode_checks_allowed_hosts_and_health(self):
        port = free_port()
        path = self.write("site.plain",
            "when someone visits the path home do\n"
            "reply with the words Hosted with Plainly end words\n"
            "end when\n"
            "start the server on port 8099\n")
        child_env = dict(os.environ, PYTHONUNBUFFERED="1", PLAINLY_DEBUG_SERVER="1")
        process = subprocess.Popen(
            [sys.executable, PLAINLY, "run", path,
             "--host", "127.0.0.1", "--port", str(port), "--allow-host", "example.test"],
            cwd=self.directory, env=child_env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self.processes.append(process)
        deadline = time.monotonic() + 12
        status, body = 0, ""
        last_error = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=2)
                self.fail("Plainly website process exited before becoming ready. stdout=%r stderr=%r" %
                          (stdout, stderr))
            try:
                status, body = request(port, "/healthz", "example.test", timeout=0.75)
                if status == 200:
                    break
            except Exception as exc:
                # Connection refused is expected briefly while the HTTP
                # listener is starting. Retry briefly so slower CI runners
                # do not make this test flaky.
                last_error = exc
            time.sleep(0.05)
        if (status, body) != (200, "ok"):
            diagnostics = []
            if sys.platform == "darwin" and process.poll() is None:
                try:
                    process.send_signal(signal.SIGUSR1)
                    time.sleep(0.15)
                except (OSError, ValueError) as exc:
                    diagnostics.append("stack dump signal: %r" % exc)
                for command in (
                    ["ps", "-o", "pid=,stat=,command=", "-p", str(process.pid)],
                    ["lsof", "-nP", "-a", "-p", str(process.pid), "-iTCP"],
                ):
                    try:
                        result = subprocess.run(command, capture_output=True, text=True, timeout=3)
                        diagnostics.append(result.stdout.strip() or result.stderr.strip())
                    except (OSError, subprocess.SubprocessError) as exc:
                        diagnostics.append(repr(exc))
            if process.poll() is None:
                process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=3)
            self.fail("website did not become ready; last error: %r; stdout=%r; stderr=%r; diagnostics=%r" %
                      (last_error, stdout, stderr, diagnostics))
        self.assertEqual(request(port, "/", "example.test"), (200, "Hosted with Plainly"))
        self.assertEqual(request(port, "/", "attacker.test")[0], 403)

    def test_public_bind_requires_an_explicit_host_allowlist(self):
        port = free_port()
        path = self.write("site.plain",
            "when someone visits the path home do\n"
            "reply with the words hello end words\nend when\n"
            "start the server on port 8099\n")
        result = subprocess.run(
            [sys.executable, PLAINLY, "run", path, "--host", "0.0.0.0"],
            cwd=self.directory, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--allow-host", result.stderr)

    def test_provider_adapter_starts_stops_and_reads_logs(self):
        source = self.write("hello.plain", "say the words Process adapter works end words\n")
        manager = plainly_host.PlainlyHost()
        try:
            result = manager.start("app-one", source, self.directory)
            self.assertIn(result["state"], ("running", "exited"))
            deadline = time.time() + 5
            while time.time() < deadline and manager.status("app-one")["state"] == "running":
                time.sleep(0.05)
            self.assertEqual(manager.status("app-one")["state"], "exited")
            self.assertIn("Process adapter works", manager.logs("app-one"))
            self.assertEqual(manager.status("missing")["state"], "not_found")
        finally:
            manager.close()

    def test_provider_adapter_refuses_programs_outside_workspace(self):
        outside = tempfile.NamedTemporaryFile(delete=False, suffix=".plain")
        outside.write(b"say 1\n")
        outside.close()
        manager = plainly_host.PlainlyHost()
        try:
            with self.assertRaises(plainly_host.HostError):
                manager.start("bad-app", outside.name, self.directory)
        finally:
            manager.close()
            os.unlink(outside.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
