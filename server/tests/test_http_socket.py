"""The HTTP server over a real socket (not just Api.handle)."""
from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

from support import make_service

from fanxi_server.http_api import Api, serve


class HttpSocketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config, self.db, self.service = make_service(Path(self.tmp.name))
        config = replace(config, http_port=0)
        self.server, _thread = serve(config, self.service, Api(config, self.service))
        self.port = self.server.server_address[1]
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=data, method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_health_over_socket(self):
        status, headers, body = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["name"], "Fanxi")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_register_and_me_over_socket(self):
        status, _headers, body = self.request("POST", "/api/v1/auth/register",
                                              {"username": "socketuser", "password": "password123"})
        self.assertEqual(status, 201, body)
        token = json.loads(body)["token"]
        status, _headers, body = self.request("GET", "/api/v1/me", headers={"Authorization": "Bearer " + token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["account"]["username"], "socketuser")

    def test_unauthorized_json_error(self):
        status, _headers, body = self.request("GET", "/api/v1/me")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["error"]["code"], "unauthorized")

    def test_options(self):
        request = urllib.request.Request("http://127.0.0.1:%d/api/v1/health" % self.port, method="OPTIONS")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Methods"].split(",")[0].strip(), "GET")


if __name__ == "__main__":
    unittest.main()
