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

    def test_character_design_patch(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Designer", "race": 1, "face": 2, "hair": 0, "size": 1},
            token=token).payload)["character"]
        self.assertEqual(character["variant"], 8)
        response = self.call(
            "PATCH", "/api/v1/characters/%d/design" % character["id"],
            {"race": 7, "face": 5, "hair": 1, "size": 2}, token=token)
        self.assertEqual(response.status, 200, response.payload)
        updated = json.loads(response.payload)["character"]
        self.assertEqual((updated["race"], updated["face"], updated["hair"], updated["size"]),
                         (7, 5, 1, 2))
        self.assertEqual(updated["variant"], 30)
        self.assertEqual(updated["design"]["label"], "Mithra, Face 5, Hair B, Large")

        bad = self.call(
            "PATCH", "/api/v1/characters/%d/design" % character["id"],
            {"face": 9}, token=token)
        self.assertEqual(bad.status, 422)
        self.assertEqual(json.loads(bad.payload)["error"]["code"], "validation_error")

    def test_character_rename(self):
        token = self.register()["token"]
        character = json.loads(self.call("POST", "/api/v1/characters",
                                         {"name": "Fanxi", "race": 1}, token=token).payload)["character"]
        renamed = self.call("PATCH", "/api/v1/characters/%d" % character["id"], {"name": "Renamed"},
                            token=token)
        self.assertEqual(renamed.status, 200, renamed.payload)
        self.assertEqual(json.loads(renamed.payload)["character"]["name"], "Renamed")


    def test_character_progress_page(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Progress", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        for body in (
            {"op": "rank", "nation": 1, "rank": 7, "points": 99},
            {"op": "mog-garden", "rank": 4},
            {"op": "fame", "all": True},
            {"op": "jobs", "all": True, "level": 99},
            {"op": "master-level", "all": True, "level": 50},
            {"op": "exemplar", "points": 50000},
            {"op": "crafts", "max_all": True},
            {"op": "trusts"},
        ):
            response = self.call("POST", base + "/progress", body, token=token)
            self.assertEqual(response.status, 200, (body, response.payload))
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(data["ranks"]["bastok"], 7)
        self.assertEqual(data["ranks"]["points"], 99)
        self.assertEqual(data["jobs"][0]["level"], 99)
        self.assertEqual(data["jobs"][0]["master_level"], 50)
        self.assertEqual(data["exemplar"]["points"], 50000)
        self.assertEqual(data["crafts"][0]["value"], 100)
        self.assertTrue(all(entry["value"] == 255 for entry in data["fame"]))

        # The Armory puts an augmentable piece in the bag; the RP card then caps a path.
        # Nyame Helm is an endgame purchase, so give the character a wallet first.
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        added = self.call("POST", base + "/armory", {"item_id": 23761}, token=token)
        self.assertEqual(added.status, 201, added.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        item = data["augments"][0]
        capped = self.call("POST", base + "/progress", {
            "op": "augment", "container": item["container"],
            "slot": item["slot"], "path": "D",
        }, token=token)
        self.assertEqual(capped.status, 200, capped.payload)
        current = json.loads(capped.payload)["augments"][0]["current"]
        self.assertEqual((current["path"], current["rank"]), ("D", 30))

    def test_armory_full_catalogue_and_purchases(self):
        self.assertGreater(
            int(self.db.one("SELECT COUNT(*) AS n FROM items WHERE equip_slot != ''")["n"]),
            15000,
        )
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Catalogue", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        # A piece the hand-curated catalogue never had.  It is in LSB's equipment
        # table, so the migration and the typeahead must find it.
        found = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Hexed Haubert"], "kind": ["armor"]}).payload)["items"]
        self.assertEqual(found[0]["name"], "Hexed Haubert")
        self.assertEqual(found[0]["item_id"], 10240)
        self.assertEqual(found[0]["equip_slot"], "body")
        self.assertGreater(found[0]["price"], 0)
        self.assertFalse(found[0]["exclusive"])

        # Exact names sort before the other Nyame pieces.
        nyame = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["nyame helm"]}).payload)["items"]
        self.assertEqual(nyame[0]["name"], "Nyame Helm")
        self.assertEqual((nyame[0]["rare"], nyame[0]["ex"], nyame[0]["exclusive"]),
                         (1, 1, True))

        # A non-Rare/non-Ex item can be bought again; the price comes off the wallet.
        bronze = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Bronze Sword"], "kind": ["weapon"]}).payload)["items"][0]
        price = bronze["price"]
        self.assertGreater(price, 0)
        gil = json.loads(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).payload)["gil"]
        first = self.call("POST", base + "/armory", {"item_id": 16535}, token=token)
        self.assertEqual(first.status, 201, first.payload)
        body = json.loads(first.payload)
        self.assertEqual(body["item"]["price"], price)
        self.assertEqual(body["data"]["gil"], gil - price)
        self.assertEqual(body["data"]["purchases"][0]["price"], price)
        second = self.call("POST", base + "/armory", {"item_id": 16535}, token=token)
        self.assertEqual(second.status, 201, second.payload)
        self.assertEqual(json.loads(second.payload)["data"]["gil"], gil - 2 * price)

        # Ex alone is one per character, even though it is not Rare.
        mantle = self.call("POST", base + "/armory", {"item_id": 26258}, token=token)
        self.assertEqual(mantle.status, 201, mantle.payload)
        again = self.call("POST", base + "/armory", {"item_id": 26258}, token=token)
        self.assertEqual(again.status, 409)
        self.assertEqual(json.loads(again.payload)["error"]["code"], "already_owned")

        # A fresh character with the starter wallet cannot afford an i119 purchase.
        other = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Broke", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        poor = self.call("POST", "/api/v1/characters/%d/armory" % other["id"],
                         {"item_id": 23761}, token=token)
        self.assertEqual(poor.status, 422)
        self.assertEqual(json.loads(poor.payload)["error"]["code"], "insufficient_gil")

    def test_character_data_page(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Data", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(data["merits"]["points"], data["merits"]["cap"])
        self.assertEqual(data["mastery_rank"], 0)
        self.assertEqual(data["job_points"]["jobs"], 22)
        self.assertTrue(data["job_points"]["all_capped"])
        self.assertEqual(data["home_points"]["registered"], 0)
        self.assertTrue(data["key_items"]["all_granted"])

        merits = json.loads(self.call("POST", base + "/merits", {"top_off": True},
                                      token=token).payload)
        self.assertEqual(merits["merits"]["points"], merits["merits"]["cap"])

        mastery = json.loads(self.call("POST", base + "/mastery-rank", {"rank": 6},
                                       token=token).payload)
        self.assertEqual(mastery["mastery_rank"], 6)
        self.assertEqual(self.service.character(character["id"])["mastery_rank"], 6)
        self.assertEqual(self.call("POST", base + "/mastery-rank", {"rank": 11},
                                   token=token).status, 422)

        gil = json.loads(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).payload)
        self.assertEqual(gil["gil"], gil["gil_max"])

        home = json.loads(self.call("POST", base + "/home-points",
                                    token=token).payload)["home_points"]
        self.assertEqual(home["registered"], home["total"])

        currency = json.loads(self.call(
            "POST", base + "/currencies",
            {"name": "Sparks of Eminence", "amount": 250}, token=token).payload)
        self.assertEqual(currency["currencies"][0]["amount"], 250)

        found = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Adoulin Ring +1"], "kind": ["accessory"]}).payload)["items"]
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["owned"])
        item_id = found[0]["item_id"]
        added = self.call("POST", base + "/armory", {"item_id": item_id}, token=token)
        self.assertEqual(added.status, 201, added.payload)
        purchase = json.loads(added.payload)["data"]["purchases"][0]
        self.assertEqual(purchase["item_id"], item_id)
        self.assertTrue(purchase["owned"])
        again = self.call("POST", base + "/armory", {"item_id": item_id}, token=token)
        self.assertEqual(again.status, 409)
        self.assertEqual(json.loads(again.payload)["error"]["code"], "already_owned")

        other = json.loads(self.call(
            "POST", "/api/v1/auth/register",
            {"username": "other", "password": "password123"}).payload)["token"]
        self.assertEqual(self.call("GET", base + "/data", token=other).status, 404)


if __name__ == "__main__":
    unittest.main()
