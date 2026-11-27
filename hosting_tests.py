#!/usr/bin/env python3
"""Regression tests for public website configuration and provider process lifecycle."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

import plainly_host

ROOT = os.path.dirname(os.path.abspath(__file__))
PLAINLY = os.path.join(ROOT, "plainly.py")


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def request(port, path, host):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        headers={"Host": "%s:%d" % (host, port)},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


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
        process = subprocess.Popen(
            [sys.executable, PLAINLY, "run", path,
             "--host", "127.0.0.1", "--port", str(port), "--allow-host", "example.test"],
            cwd=self.directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        deadline = time.time() + 5
        status, body = 0, ""
        while time.time() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=2)
                self.fail("Plainly website process exited before becoming ready. stdout=%r stderr=%r" %
                          (stdout, stderr))
            try:
                status, body = request(port, "/healthz", "example.test")
                if status == 200:
                    break
            except Exception as exc:
                # Connection refused is expected briefly while the HTTP
                # listener is starting; any other error is retried until
                # the deadline so the failure below remains deterministic.
                last_error = exc
            time.sleep(0.05)
        self.assertEqual((status, body), (200, "ok"),
                         "website did not become ready; last error: %r" % locals().get("last_error"))
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
