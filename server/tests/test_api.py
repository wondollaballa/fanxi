"""The HTTP router without a socket: requests in, JSON out."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.http_api import Api, Request


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.api = Api(self.config, self.service)

    def call(self, method, path, body=None, token=None, admin_key=None, query=None):
        headers = {}
        if token:
            headers["authorization"] = "Bearer " + token
        if admin_key:
            headers["x-admin-key"] = admin_key
        raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        return self.api.handle(Request(method=method, path=path, body=raw, headers=headers,
                                       remote="127.0.0.1", query=query or {}))

    def register(self, username="tester", password="password123"):
        response = self.call("POST", "/api/v1/auth/register",
                             {"username": username, "password": password})
        self.assertEqual(response.status, 201, response.payload)
        return json.loads(response.payload)

    def test_health_status_and_news_are_public(self):
        for path in ("/api/v1/health", "/api/v1/status", "/api/v1/news", "/api/v1/releases"):
            response = self.call("GET", path)
            self.assertEqual(response.status, 200, path)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_register_login_me(self):
        data = self.register()
        token = data["token"]
        me = self.call("GET", "/api/v1/me", token=token)
        self.assertEqual(me.status, 200)
        self.assertEqual(json.loads(me.payload)["account"]["username"], "tester")
        login = self.call("POST", "/api/v1/auth/login", {"username": "tester", "password": "password123"})
        self.assertEqual(login.status, 200)
        self.assertTrue(json.loads(login.payload)["token"])

    def test_protected_route_needs_token(self):
        response = self.call("GET", "/api/v1/me")
        self.assertEqual(response.status, 401)
        self.assertEqual(json.loads(response.payload)["error"]["code"], "unauthorized")

    def test_character_and_launch_flow(self):
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0}, token=token)
        self.assertEqual(created.status, 201, created.payload)
        character = json.loads(created.payload)["character"]
        self.assertEqual(character["name"], "Fanxi")
        launch = self.call("POST", "/api/v1/launch", {"character_id": character["id"]}, token=token)
        self.assertEqual(launch.status, 200, launch.payload)
        payload = json.loads(launch.payload)
        self.assertTrue(payload["login_token"])
        self.assertEqual(payload["world"]["name"], "Fanxi")
        self.assertEqual(payload["client"]["username"], "tester")

    def test_bad_json(self):
        response = self.call("POST", "/api/v1/auth/login", b"{not json")
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.payload)["error"]["code"], "bad_json")

    def test_unknown_route(self):
        response = self.call("GET", "/api/v1/nope", token=self.register()["token"])
        self.assertEqual(response.status, 404)

    def test_trailing_slash(self):
        self.assertEqual(self.call("GET", "/api/v1/health/").status, 200)

    def test_admin_key(self):
        response = self.call("POST", "/api/v1/admin/news",
                             {"slug": "maintenance", "title": "Maintenance", "body": "Tonight"},
                             admin_key="test-admin-key")
        self.assertEqual(response.status, 201, response.payload)
        self.assertEqual(json.loads(response.payload)["news"]["slug"], "maintenance")
        denied = self.call("POST", "/api/v1/admin/news",
                           {"slug": "x", "title": "x", "body": "x"}, admin_key="wrong")
        self.assertEqual(denied.status, 403)
        player = self.call("POST", "/api/v1/admin/news",
                           {"slug": "x", "title": "x", "body": "x"}, token=self.register("other")["token"])
        self.assertEqual(player.status, 403)

    def test_admin_role(self):
        self.register()
        self.db.execute("UPDATE accounts SET role = 'admin' WHERE username = 'tester'")
        token = self.call("POST", "/api/v1/auth/login",
                          {"username": "tester", "password": "password123"})
        token = json.loads(token.payload)["token"]
        response = self.call("GET", "/api/v1/admin/stats", token=token)
        self.assertEqual(response.status, 200, response.payload)
        self.assertIn("audit", json.loads(response.payload))

    def test_logout(self):
        token = self.register()["token"]
        self.assertEqual(self.call("POST", "/api/v1/auth/logout", token=token).status, 204)
        self.assertEqual(self.call("GET", "/api/v1/me", token=token).status, 401)

    def test_character_rename(self):
        token = self.register()["token"]
        character = json.loads(self.call("POST", "/api/v1/characters",
                                         {"name": "Fanxi", "race": 1}, token=token).payload)["character"]
        renamed = self.call("PATCH", "/api/v1/characters/%d" % character["id"], {"name": "Renamed"},
                            token=token)
        self.assertEqual(renamed.status, 200, renamed.payload)
        self.assertEqual(json.loads(renamed.payload)["character"]["name"], "Renamed")


if __name__ == "__main__":
    unittest.main()
