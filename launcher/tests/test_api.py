"""The HTTP client against a tiny local stand-in server."""
from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import support  # noqa: F401

from fanxi_launcher.api import ApiError, FanxiApi, NetworkError


class FakeHandler(BaseHTTPRequestHandler):
    server_version = "FanxiTest"

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.requests.append({
            "method": self.command,
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": json.loads(body) if body else None,
        })
        path = self.path.split("?")[0]
        if path == "/api/v1/status":
            self._send(200, {"name": "Fanxi", "online": 3})
        elif path == "/api/v1/news":
            self._send(200, {"news": [{"title": "Hello"}]})
        elif path == "/api/v1/auth/login":
            payload = json.loads(body) if body else {}
            if payload.get("username") == "tester" and payload.get("password") == "password123":
                self._send(200, {"token": "tok", "expires_at": "soon", "account": {"username": "tester"},
                                 "characters": []})
            else:
                self._send(401, {"error": {"code": "invalid_credentials", "message": "invalid username or password"}})
        elif path == "/api/v1/me":
            if self.headers.get("Authorization") == "Bearer tok":
                self._send(200, {"account": {"username": "tester"}, "characters": []})
            else:
                self._send(401, {"error": {"code": "unauthorized", "message": "sign in first"}})
        elif path == "/api/v1/auth/logout":
            self._send(204, None)
        elif path == "/api/v1/characters":
            self._send(201, {"character": {"name": "Fanxi"}})
        elif path.startswith("/api/v1/characters/"):
            self._send(200, {"character": {"name": "Renamed"}})
        else:
            self._send(404, {"error": {"code": "not_found", "message": "no such endpoint"}})

    def _send(self, status, payload):
        data = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    do_GET = _handle
    do_POST = _handle
    do_PATCH = _handle

    def log_message(self, *args):
        pass


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        cls.server.requests = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.server.requests.clear()
        self.api = FanxiApi("http://127.0.0.1:%d" % self.port)

    def test_base_url_trailing_api_v1(self):
        api = FanxiApi("http://127.0.0.1:%d/api/v1/" % self.port)
        self.assertEqual(api.api_root, "http://127.0.0.1:%d/api/v1" % self.port)
        self.assertEqual(api.status()["name"], "Fanxi")

    def test_status_news(self):
        self.assertEqual(self.api.status()["online"], 3)
        self.assertEqual(self.api.news(3)[0]["title"], "Hello")
        self.assertIn("/api/v1/news?limit=3", self.server.requests[-1]["path"])

    def test_login_success_and_failure(self):
        data = self.api.login("tester", "password123")
        self.assertEqual(data["token"], "tok")
        with self.assertRaises(ApiError) as ctx:
            self.api.login("tester", "wrong")
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.code, "invalid_credentials")

    def test_auth_header_and_me(self):
        self.assertEqual(self.api.me("tok")["account"]["username"], "tester")
        self.assertEqual(self.server.requests[-1]["headers"]["authorization"], "Bearer tok")
        with self.assertRaises(ApiError) as ctx:
            self.api.me("bad")
        self.assertTrue(ctx.exception.unauthorized)

    def test_logout_204(self):
        self.assertIsNone(self.api.logout("tok"))

    def test_character_calls(self):
        self.assertEqual(self.api.create_character("tok", {"name": "Fanxi"}), {"name": "Fanxi"})
        self.assertEqual(self.api.rename_character("tok", 1, "Renamed"), {"name": "Renamed"})
        self.assertEqual(self.server.requests[-1]["method"], "PATCH")

    def test_bad_json_error_body(self):
        # A 401 without a JSON body still gives a clean ApiError rather than a crash.
        api = FanxiApi("http://127.0.0.1:%d" % self.port)
        with self.assertRaises(ApiError):
            api.me("bad")

    def test_network_error(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        api = FanxiApi("http://127.0.0.1:%d" % port, timeout=1)
        with self.assertRaises(NetworkError) as ctx:
            api.status()
        self.assertIn("is the Fanxi server running", str(ctx.exception))

    def test_missing_scheme_is_added(self):
        api = FanxiApi("127.0.0.1:%d" % self.port)
        self.assertTrue(api.base.startswith("http://"))
        self.assertEqual(api.status()["name"], "Fanxi")


if __name__ == "__main__":
    unittest.main()
