"""Server-owned sub-accounts: main-only ownership, no sub passwords or tokens."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.http_api import Api, Request


class SubAccountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name), max_subs=2)
        self.api = Api(self.config, self.service)

    def call(self, method, path, body=None, token=None, query=None):
        headers = {}
        if token:
            headers["authorization"] = "Bearer " + token
        raw = b"" if body is None else json.dumps(body).encode()
        return self.api.handle(Request(method=method, path=path, body=raw, headers=headers,
                                       remote="127.0.0.1", query=query or {}))

    def register(self, username="tester"):
        response = self.call("POST", "/api/v1/auth/register",
                             {"username": username, "password": "password123"})
        self.assertEqual(response.status, 201, response.payload)
        return json.loads(response.payload)

    def create_sub(self, token, character=None):
        body = {"character": character} if character else {}
        return self.call("POST", "/api/v1/accounts/sub", body, token=token)

    def test_create_list_and_launch_without_a_sub_token(self):
        main = self.register()
        token = main["token"]
        self.assertEqual(main["account"]["kind"], "main")
        created = self.create_sub(token, {"name": "Tinybox", "race": 1, "face": 1})
        self.assertEqual(created.status, 201, created.payload)
        sub = json.loads(created.payload)["sub"]
        self.assertEqual(sub["character"]["name"], "Tinybox")
        self.assertNotIn("token", sub)
        self.assertEqual(sub["parent_id"], main["account"]["id"])
        # The sub has no password and no API session: a login is just invalid credentials.
        denied = self.call("POST", "/api/v1/auth/login",
                           {"username": sub["username"], "password": "password123"})
        self.assertEqual(denied.status, 401)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM api_sessions WHERE account_id = ?",
                                        (sub["id"],), 0), 0)
        listed = self.call("GET", "/api/v1/accounts/sub", token=token)
        self.assertEqual(listed.status, 200)
        payload = json.loads(listed.payload)
        self.assertEqual(payload["limit"], 2)
        self.assertEqual([item["id"] for item in payload["subs"]], [sub["id"]])
        launch = self.call("POST", "/api/v1/accounts/sub/%d/launch" % sub["id"],
                           {"character_id": sub["character"]["id"]}, token=token)
        self.assertEqual(launch.status, 200, launch.payload)
        data = json.loads(launch.payload)
        self.assertEqual(data["client"]["username"], sub["username"])
        self.assertEqual(data["account"]["kind"], "sub")
        self.assertTrue(data["login_token"])

    def test_generated_character_name_and_custom_character(self):
        token = self.register()["token"]
        generated = json.loads(self.create_sub(token).payload)["sub"]
        self.assertRegex(generated["character"]["name"], r"^Box[A-Z]{4}$")
        custom = json.loads(self.create_sub(token, {"name": "Custombox", "main_job": 3}).payload)["sub"]
        self.assertEqual(custom["character"]["name"], "Custombox")
        self.assertEqual(custom["character"]["main_job"], 3)

    def test_cap_and_purge_frees_a_slot(self):
        token = self.register()["token"]
        first = json.loads(self.create_sub(token, {"name": "Boxone"}).payload)["sub"]
        second = json.loads(self.create_sub(token, {"name": "Boxtwo"}).payload)["sub"]
        third = self.create_sub(token, {"name": "Boxthree"})
        self.assertEqual(third.status, 409)
        self.assertEqual(json.loads(third.payload)["error"]["code"], "sub_account_limit")
        purged = self.call("DELETE", "/api/v1/accounts/sub/%d" % first["id"],
                           token=token, query={"purge": ["1"]})
        self.assertEqual(purged.status, 200, purged.payload)
        self.assertTrue(json.loads(purged.payload)["sub"]["purged"])
        replacement = self.create_sub(token, {"name": "Boxthree"})
        self.assertEqual(replacement.status, 201, replacement.payload)
        self.assertNotEqual(json.loads(replacement.payload)["sub"]["id"], first["id"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM characters WHERE account_id = ?",
                                        (first["id"],), 0), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounts WHERE id = ?",
                                        (second["id"],), 0), 1)

    def test_suspend_blocks_launch_and_can_be_purged(self):
        token = self.register()["token"]
        sub = json.loads(self.create_sub(token, {"name": "Sleeper"}).payload)["sub"]
        suspended = self.call("DELETE", "/api/v1/accounts/sub/%d" % sub["id"], token=token)
        self.assertEqual(suspended.status, 200, suspended.payload)
        self.assertEqual(json.loads(suspended.payload)["sub"]["status"], "suspended")
        launch = self.call("POST", "/api/v1/accounts/sub/%d/launch" % sub["id"],
                           {}, token=token)
        self.assertEqual(launch.status, 403)
        active = self.call("PATCH", "/api/v1/accounts/sub/%d" % sub["id"],
                           {"status": "active"}, token=token)
        self.assertEqual(active.status, 200, active.payload)
        self.assertEqual(json.loads(active.payload)["sub"]["status"], "active")
        launch = self.call("POST", "/api/v1/accounts/sub/%d/launch" % sub["id"],
                           {"character_id": sub["character"]["id"]}, token=token)
        self.assertEqual(launch.status, 200, launch.payload)

    def test_another_main_cannot_touch_this_teams_sub(self):
        token = self.register("owner")["token"]
        sub = json.loads(self.create_sub(token, {"name": "Ownedbox"}).payload)["sub"]
        other = self.register("otherplayer")["token"]
        self.assertEqual(self.call("POST", "/api/v1/accounts/sub/%d/launch" % sub["id"],
                                   {}, token=other).status, 404)
        self.assertEqual(self.call("DELETE", "/api/v1/accounts/sub/%d" % sub["id"],
                                   token=other).status, 404)
        self.assertEqual(json.loads(self.call("GET", "/api/v1/accounts/sub", token=other).payload)["subs"], [])

    def test_sub_account_routes_require_a_main_token(self):
        response = self.call("GET", "/api/v1/accounts/sub")
        self.assertEqual(response.status, 401)
        self.assertEqual(self.call("POST", "/api/v1/accounts/sub", {}).status, 401)

    def test_character_can_be_recreated_after_removal(self):
        token = self.register()["token"]
        sub = json.loads(self.create_sub(token, {"name": "Remakebox"}).payload)["sub"]
        self.db.execute("DELETE FROM characters WHERE account_id = ?", (sub["id"],))
        recreated = self.call("POST", "/api/v1/accounts/sub/%d/characters" % sub["id"],
                              {"character": {"name": "Remakeboxtwo"}}, token=token)
        self.assertEqual(recreated.status, 201, recreated.payload)
        self.assertEqual(json.loads(recreated.payload)["character"]["name"], "Remakeboxtwo")
        again = self.call("POST", "/api/v1/accounts/sub/%d/characters" % sub["id"], token=token)
        self.assertEqual(again.status, 409)


if __name__ == "__main__":
    unittest.main()
