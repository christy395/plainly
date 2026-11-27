"""Local imitations of Telegram and Discord, used only by the tests (the real services are not contacted)."""
import base64
import hashlib
import json
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _serve(port, handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class TelegramMock:
    def __init__(self, port, token="TESTTOKEN"):
        self.updates, self.sent, self.offsets = [], [], []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                u = urlparse(self.path)
                if not u.path.startswith("/bot%s/" % token):
                    return self._json(401, {"ok": False})
                off = int(parse_qs(u.query).get("offset", ["0"])[0])
                outer.offsets.append(off)
                res = [x for x in outer.updates if x["update_id"] >= off]
                if not res:
                    time.sleep(0.4)
                self._json(200, {"ok": True, "result": res})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.sent.append(body)
                self._json(200, {"ok": True})
        self.srv = _serve(port, H)


class DiscordMock:
    def __init__(self, rest_port, gw_port, token="TESTTOKEN"):
        self.posts, self.identify, self.heartbeats = [], [], 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.posts.append((self.path, body, self.headers.get("Authorization"), self.headers.get("User-Agent")))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
        self.rest = _serve(rest_port, H)
        gw = socket.socket()
        gw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        gw.bind(("127.0.0.1", gw_port))
        gw.listen(5)

        def accept():
            while True:
                conn, _ = gw.accept()
                threading.Thread(target=self.session, args=(conn,), daemon=True).start()
        threading.Thread(target=accept, daemon=True).start()

    @staticmethod
    def _send(conn, obj):
        data = json.dumps(obj).encode()
        head = bytes([0x81, len(data)]) if len(data) < 126 else bytes([0x81, 126]) + struct.pack(">H", len(data))
        conn.sendall(head + data)

    def session(self, conn):
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += conn.recv(4096)
        head, rest = buf.split(b"\r\n\r\n", 1)
        key = [l.split(":", 1)[1].strip() for l in head.decode().split("\r\n") if l.lower().startswith("sec-websocket-key")][0]
        acc = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      "Sec-WebSocket-Accept: %s\r\n\r\n" % acc).encode())
        self._send(conn, {"op": 10, "d": {"heartbeat_interval": 300}})

        def read(n):
            nonlocal rest
            while len(rest) < n:
                chunk = conn.recv(4096)
                if not chunk:
                    raise OSError
                rest += chunk
            out, rest = rest[:n], rest[n:]
            return out
        try:
            while True:
                b1, b2 = read(2)
                n = b2 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", read(2))[0]
                mask = read(4)
                payload = bytes(c ^ mask[i % 4] for i, c in enumerate(read(n)))
                ev = json.loads(payload)
                if ev["op"] == 2:
                    self.identify.append(ev["d"])
                    self._send(conn, {"op": 0, "t": "READY", "s": 1, "d": {"user": {"id": "42"}}})
                    for i, (author, bot) in enumerate((({"id": "7", "username": "Bob"}, False),
                                                       ({"id": "8", "username": "Robo", "bot": True}, True),
                                                       ({"id": "42", "username": "Me"}, False))):
                        self._send(conn, {"op": 0, "t": "MESSAGE_CREATE", "s": 2 + i,
                                          "d": {"content": "hello", "channel_id": "999", "author": author}})
                elif ev["op"] == 1:
                    self.heartbeats += 1
                    self._send(conn, {"op": 11})
        except OSError:
            pass
