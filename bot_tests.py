#!/usr/bin/env python3
"""Integration tests for Plainly's local Discord and Telegram test adapters."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
PLAINLY = os.path.join(ROOT, "plainly.py")


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_until(predicate, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return bool(predicate())


class BotIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="plainly-bot-test-")
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        shutil.rmtree(self.directory, ignore_errors=True)

    def write_program(self, name, content):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def start_program(self, path, env):
        process = subprocess.Popen(
            [sys.executable, PLAINLY, "run", path],
            cwd=self.directory, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        self.processes.append(process)
        return process

    def test_telegram_message_handler_and_secret(self):
        import mock_bots

        port = free_port()
        mock = mock_bots.TelegramMock(port)
        mock.updates = [
            {"update_id": 10, "message": {"text": "Hello there",
             "from": {"first_name": "Ann"}, "chat": {"id": 111}}},
            {"update_id": 11, "message": {"text": "what is this",
             "from": {"first_name": "Ann"}, "chat": {"id": 111}}},
            {"update_id": 12, "message": {"photo": []}},
        ]
        path = self.write_program("telegram.plain",
            "allow running a Telegram bot\n"
            "when a Telegram message arrives do\n"
            "let said be the message text\n"
            "if said contains the words hello end words then\n"
            "reply with the words Hello followed by the message author\n"
            "otherwise\n"
            "reply with the words You said followed by said\n"
            "end if\n"
            "end when\n"
            "start the Telegram bot\n")
        env = dict(os.environ, PLAINLY_SECRET_TELEGRAM_TOKEN="TESTTOKEN",
                   PLAINLY_TELEGRAM_API="http://127.0.0.1:%d" % port)
        process = self.start_program(path, env)
        try:
            self.assertTrue(wait_until(lambda: len(mock.sent) >= 2), "Telegram bot did not send replies")
            self.assertEqual([item["text"] for item in mock.sent[:2]],
                             ["Hello Ann", "You said what is this"])
            self.assertTrue(all(str(item["chat_id"]) == "111" for item in mock.sent[:2]))
            self.assertTrue(wait_until(lambda: 13 in mock.offsets), "Telegram bot did not advance its update offset")
        finally:
            process.terminate()
            process.wait(timeout=4)
            mock.srv.shutdown()
            mock.srv.server_close()

    def test_telegram_requires_secret_and_reports_invalid_token(self):
        path = self.write_program("telegram.plain",
            "allow running a Telegram bot\n"
            "when a Telegram message arrives do\n"
            "reply with the words hi end words\n"
            "end when\n"
            "start the Telegram bot\n")
        env = dict(os.environ)
        env.pop("PLAINLY_SECRET_TELEGRAM_TOKEN", None)
        missing = subprocess.run([sys.executable, PLAINLY, "run", path],
                                 cwd=self.directory, env=env, capture_output=True,
                                 text=True, timeout=5)
        self.assertIn("PLAINLY_SECRET_TELEGRAM_TOKEN", missing.stderr)
        port = free_port()
        mock = __import__("mock_bots").TelegramMock(port)
        env["PLAINLY_SECRET_TELEGRAM_TOKEN"] = "WRONG"
        env["PLAINLY_TELEGRAM_API"] = "http://127.0.0.1:%d" % port
        invalid = subprocess.run([sys.executable, PLAINLY, "run", path],
                                 cwd=self.directory, env=env, capture_output=True,
                                 text=True, timeout=5)
        self.assertIn("token is not valid", invalid.stderr)
        mock.srv.shutdown()
        mock.srv.server_close()

    def test_discord_gateway_filters_bot_and_self_messages(self):
        try:
            import websockets.sync.client  # noqa: F401
        except ImportError:
            self.skipTest("optional websockets dependency is not installed")
        import mock_bots

        rest_port, gateway_port = free_port(), free_port()
        mock = mock_bots.DiscordMock(rest_port, gateway_port)
        path = self.write_program("discord.plain",
            "allow running a Discord bot\n"
            "when a Discord message arrives do\n"
            "let said be the message text\n"
            "if said contains the words hello end words then\n"
            "reply with the words Hello followed by the message author\n"
            "end if\n"
            "end when\n"
            "start the Discord bot\n")
        env = dict(os.environ, PLAINLY_SECRET_DISCORD_TOKEN="TESTTOKEN",
                   PLAINLY_DISCORD_API="http://127.0.0.1:%d" % rest_port,
                   PLAINLY_DISCORD_GATEWAY="ws://127.0.0.1:%d/" % gateway_port)
        process = self.start_program(path, env)
        try:
            connected = wait_until(lambda: len(mock.posts) >= 1 and mock.heartbeats >= 1)
            if not connected:
                process.terminate()
                stdout, stderr = process.communicate(timeout=4)
                self.fail("Discord bot did not connect and respond. stdout=%r stderr=%r" % (stdout, stderr))
            self.assertEqual(len(mock.posts), 1)
            self.assertEqual(mock.posts[0][0], "/channels/999/messages")
            self.assertEqual(mock.posts[0][1], {"content": "Hello Bob", "allowed_mentions": {"parse": []}})
            self.assertEqual(mock.posts[0][2], "Bot TESTTOKEN")
            self.assertTrue(mock.posts[0][3].startswith("DiscordBot ("))
            self.assertEqual(mock.identify[0]["intents"], 37376)
        finally:
            process.terminate()
            process.wait(timeout=4)

    def test_bot_commands_require_explicit_permissions_and_handlers(self):
        no_permission = subprocess.run(
            [sys.executable, PLAINLY, "check", self.write_program(
                "no_permission.plain",
                "when a Telegram message arrives do\nend when\n")],
            cwd=self.directory, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(no_permission.returncode, 0)
        self.assertIn("ask permission first", no_permission.stderr)
        no_handler = subprocess.run(
            [sys.executable, PLAINLY, "check", self.write_program(
                "no_handler.plain", "allow running a Discord bot\nstart the Discord bot\n")],
            cwd=self.directory, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(no_handler.returncode, 0)
        self.assertIn("before starting", no_handler.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
