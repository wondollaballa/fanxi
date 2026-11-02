"""The HTTP router without a socket: requests in, JSON out."""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from support import make_service

from fanxi_server.http_api import Api, Request


class _StubZones:
    def name(self, zone):
        return {190: "King Ranperre's Tomb"}.get(int(zone), "zone %d" % int(zone))


class _StubWorld:
    """Only what search.online_characters and the roster's zone names read."""

    def __init__(self, sessions):
        self.lock = threading.RLock()
        self.sessions = sessions
        self.zones = _StubZones()


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

    def test_the_target_route_accepts_the_long_character_id(self):
        """The in-game HUD only knows the client's ServerId (0x01000000 | char_id).

        The Target Debuffs window polls /characters/<ServerId>/target.  With only the database
        row id accepted, that request 404'd and the window drew the error body (a JSON object)
        as ``Server state: table: 0x...``.
        """
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0},
                            token=token)
        self.assertEqual(created.status, 201, created.payload)
        character = json.loads(created.payload)["character"]
        for path_id in (int(character["id"]), int(character["char_id"])):
            response = self.call("GET", "/api/v1/characters/%d/target" % path_id, token=token)
            # No zone session in this test, so the character resolves and the endpoint stops
            # at "not in a zone" — never at "character not found".
            self.assertEqual(response.status, 404, response.payload)
            self.assertEqual(json.loads(response.payload)["error"]["message"],
                             "character is not in a zone")
        missing = self.call("GET", "/api/v1/characters/99999999/target", token=token)
        self.assertEqual(missing.status, 404, missing.payload)
        self.assertEqual(json.loads(missing.payload)["error"]["message"], "character not found")

    def test_world_online_needs_a_token_and_reports_an_unattached_gateway(self):
        response = self.call("GET", "/api/v1/world/online")
        self.assertEqual(response.status, 401)
        token = self.register()["token"]
        response = self.call("GET", "/api/v1/world/online", token=token)
        self.assertEqual(response.status, 200)
        payload = json.loads(response.payload)
        self.assertFalse(payload["gateway"])
        self.assertEqual(payload["characters"], [])

    def test_world_online_lists_the_live_sessions(self):
        token = self.register()["token"]
        account_id = self.service.authenticate(token)["id"]
        character = self.service.create_character(account_id, {
            "name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0,
        })
        other = self.service.register("other", "password123", ip="127.0.0.1")
        outsider = self.service.create_character(other.account["id"], {
            "name": "Outsider", "race": 1, "face": 1, "size": 1, "nation": 0,
        })
        now = time.time()

        def session(char, account, zone):
            return SimpleNamespace(
                logged_in=True, gone=False, key=b"key", zone=zone, last_packet_at=now,
                char={"id": char["id"], "char_id": char["char_id"],
                      "account_id": account, "name": char["name"]},
            )

        self.service.attach_world(_StubWorld({
            ("127.0.0.1", 1): session(character, account_id, 190),
            ("127.0.0.1", 2): session(outsider, other.account["id"], 190),
        }))
        self.addCleanup(self.service.detach_world)
        response = self.call("GET", "/api/v1/world/online", token=token)
        self.assertEqual(response.status, 200)
        payload = json.loads(response.payload)
        self.assertTrue(payload["gateway"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual([item["name"] for item in payload["characters"]],
                         ["Fanxi", "Outsider"])
        self.assertEqual(payload["characters"][0], {
            "id": character["id"], "char_id": character["char_id"], "name": "Fanxi",
            "zone": 190, "zone_name": "King Ranperre's Tomb",
        })
        status = json.loads(self.call("GET", "/api/v1/status").payload)
        self.assertEqual(status["online"], 2)

    def test_battle_team_marks_only_the_live_characters(self):
        token = self.register()["token"]
        account_id = self.service.authenticate(token)["id"]
        online = self.service.create_character(account_id, {
            "name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0,
        })
        offline = self.service.create_character(account_id, {
            "name": "Offdough", "race": 1, "face": 1, "size": 1, "nation": 0,
        })
        now = time.time()
        self.service.attach_world(_StubWorld({
            ("127.0.0.1", 1): SimpleNamespace(
                logged_in=True, gone=False, key=b"key", zone=190, last_packet_at=now,
                char={"id": online["id"], "char_id": online["char_id"],
                      "account_id": account_id, "name": online["name"]},
            ),
        }))
        self.addCleanup(self.service.detach_world)

        response = self.call("GET", "/api/v1/battle/team", token=token)
        self.assertEqual(response.status, 200)
        payload = json.loads(response.payload)
        self.assertTrue(payload["online_known"])
        rows = {row["name"]: row for row in payload["characters"]}
        self.assertEqual(set(rows), {offline["name"], online["name"]})
        self.assertTrue(rows[online["name"]]["online"])
        self.assertEqual(rows[online["name"]]["zone"], 190)
        self.assertEqual(rows[online["name"]]["zone_name"], "King Ranperre's Tomb")
        self.assertFalse(rows[offline["name"]]["online"])
        self.assertIsNone(rows[offline["name"]]["zone"])
        self.assertTrue(rows[offline["name"]]["online_known"])

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
        # The purchase response already carries the refreshed snapshot the Data
        # page feeds straight into the RP card.
        bought = json.loads(added.payload)
        self.assertIn(23761, [row["item_id"] for row in bought["data"]["augments"]])
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        item = data["augments"][0]
        capped = self.call("POST", base + "/progress", {
            "op": "augment", "container": item["container"],
            "slot": item["slot"], "path": "D",
        }, token=token)
        self.assertEqual(capped.status, 200, capped.payload)
        current = json.loads(capped.payload)["augments"][0]["current"]
        self.assertEqual((current["path"], current["rank"]), ("D", 30))

    def test_ambuscade_cape_card_and_augment(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Capes", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(len(data["capes"]["capes"]), 22)
        self.assertEqual(len(data["capes"]["materials"]), 5)
        self.assertEqual(data["capes"]["materials"][0]["key"], "thread")
        self.assertEqual(data["capes"]["slots"], 5)
        self.assertIn("max_text", data["capes"]["materials"][0]["options"][0])

        added = self.call("POST", base + "/progress",
                          {"op": "cape-add", "item_id": 26246}, token=token)
        self.assertEqual(added.status, 200, added.payload)
        payload = json.loads(added.payload)
        war = next(entry for entry in payload["capes"]["capes"]
                   if entry["job"] == "WAR")
        self.assertEqual(war["owned"], 1)
        copy = war["copies"][0]
        choices = {
            "thread": {"option": "dex", "stage": 20},
            "dust": {"option": "acc_attack", "stage": 20},
            "dye": {"option": "accuracy", "stage": 10},
            "sap": {"option": "store_tp", "stage": 10},
            "resin": {"option": "pdt", "stage": 5},
        }
        applied = self.call("POST", base + "/progress", {
            "op": "cape-augment", "container": copy["container"],
            "slot": copy["slot"], "choices": choices,
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        payload = json.loads(applied.payload)
        copy = next(entry for entry in payload["capes"]["capes"]
                    if entry["job"] == "WAR")["copies"][0]
        self.assertEqual(copy["current"]["text"],
                         "DEX+20, Accuracy+20 Attack+20, Accuracy+10, "
                         '"Store TP"+10, Phys. dmg. taken-10%')
        self.assertEqual(copy["selection"]["thread"], {"option": "dex", "stage": 20})

        # A choice the BG Wiki material does not offer is rejected.
        bad = self.call("POST", base + "/progress", {
            "op": "cape-augment", "container": copy["container"],
            "slot": copy["slot"],
            "choices": {"thread": {"option": "nope", "stage": 1}},
        }, token=token)
        self.assertEqual(bad.status, 422, bad.payload)
        # The add op only accepts an Ambuscade job cape, and a missing slot is a 404.
        not_cape = self.call("POST", base + "/progress",
                             {"op": "cape-add", "item_id": 11931}, token=token)
        self.assertEqual(not_cape.status, 422, not_cape.payload)
        missing = self.call("POST", base + "/progress", {
            "op": "cape-clear", "container": 99, "slot": 99,
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)

        cleared = self.call("POST", base + "/progress", {
            "op": "cape-clear", "container": copy["container"],
            "slot": copy["slot"],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        payload = json.loads(cleared.payload)
        copy = next(entry for entry in payload["capes"]["capes"]
                    if entry["job"] == "WAR")["copies"][0]
        self.assertEqual(copy["current"]["text"], "not augmented")

    def test_nolan_and_oseem_cards(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Escha", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.call("POST", base + "/gil", {"top_off": True}, token=token)

        empty = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(empty["nolan"]["items"], [])
        self.assertEqual(len(empty["glyptics"]["items"]), 39)
        self.assertFalse(any(item["owned"] for item in empty["glyptics"]["items"]))
        self.assertEqual(empty["nolan"]["levels"]["max_rank"], 15)
        self.assertEqual(empty["glyptics"]["slots"], 5)

        self.call("POST", base + "/armory", {"item_id": 25618}, token=token)  # Kaykaus Mitra +1
        self.call("POST", base + "/armory", {"item_id": 25642}, token=token)  # Herculean Helm
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        mitra = data["nolan"]["items"][0]
        self.assertEqual(mitra["name"], "Kaykaus Mitra +1")
        helm = next(entry for entry in data["glyptics"]["items"] if entry["owned"])
        self.assertEqual(helm["name"], "Herculean Helm")
        self.assertEqual(
            sorted(data["glyptics"]["path_sets"][helm["path_key"]]["paths"]),
            ["familiar", "magic", "melee", "ranged"])

        copy = mitra["copies"][0]
        applied = self.call("POST", base + "/progress", {
            "op": "nolan", "container": copy["container"], "slot": copy["slot"],
            "path": "B",
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        payload = json.loads(applied.payload)
        current = payload["nolan"]["items"][0]["copies"][0]["current"]
        self.assertEqual((current["path"], current["rank"]), ("B", 15))
        self.assertEqual([row["text"] for row in current["rows"]],
                         ["MP+80", "Cure spellcasting time-7%", "Enmity-6"])

        copy = helm["copies"][0]
        choices = [
            {"key": "acc", "value": 40}, {"key": "ta", "value": 4},
            {"key": "str", "value": 15}, {"key": "attack", "value": 40},
            {"key": "wsd", "value": 5},
        ]
        glyptic = self.call("POST", base + "/progress", {
            "op": "glyptics", "container": copy["container"],
            "slot": copy["slot"], "path": "melee", "choices": choices,
        }, token=token)
        self.assertEqual(glyptic.status, 200, glyptic.payload)
        payload = json.loads(glyptic.payload)
        current = next(entry for entry in payload["glyptics"]["items"]
                       if entry["name"] == "Herculean Helm")["copies"][0]
        self.assertIn("Accuracy+40", current["current"])
        self.assertEqual(current["selection"][0], {"key": "acc", "value": 40})

        bad_path = self.call("POST", base + "/progress", {
            "op": "nolan", "container": copy["container"], "slot": copy["slot"],
            "path": "E",
        }, token=token)
        self.assertEqual(bad_path.status, 422, bad_path.payload)
        bad_augment = self.call("POST", base + "/progress", {
            "op": "glyptics", "container": copy["container"], "slot": copy["slot"],
            "path": "familiar", "choices": [{"key": "wsd", "value": 5}],
        }, token=token)
        self.assertEqual(bad_augment.status, 422, bad_augment.payload)
        missing = self.call("POST", base + "/progress", {
            "op": "nolan", "container": 99, "slot": 99, "path": "A",
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)

        cleared = self.call("POST", base + "/progress", {
            "op": "glyptics-clear", "container": copy["container"],
            "slot": copy["slot"],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        payload = json.loads(cleared.payload)
        current = next(entry for entry in payload["glyptics"]["items"]
                       if entry["name"] == "Herculean Helm")["copies"][0]
        self.assertEqual(current["current"], "not augmented")

    def test_skirmish_card_and_augment(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Skirmish", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.call("POST", base + "/gil", {"top_off": True}, token=token)

        empty = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(len(empty["skirmish"]["items"]), 138)
        self.assertGreaterEqual(len(empty["skirmish"]["slot_sets"]), 36)
        self.assertFalse(any(item["owned"] for item in empty["skirmish"]["items"]))

        bought = self.call("POST", base + "/armory", {"item_id": 26733}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        barbuta = next(item for item in data["skirmish"]["items"]
                       if item["item_id"] == 26733)
        self.assertTrue(barbuta["owned"])
        slots = data["skirmish"]["slot_sets"][barbuta["slot_set"]]
        self.assertEqual([slot["key"] for slot in slots], ["snow", "leaf", "dusk"])
        picks = [
            {"key": slot["options"][0]["key"], "value": slot["options"][0]["default"]}
            for slot in slots
        ]
        copy = barbuta["copies"][0]
        applied = self.call("POST", base + "/progress", {
            "op": "skirmish", "container": copy["container"],
            "slot": copy["slot"], "picks": picks,
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        payload = json.loads(applied.payload)
        barbuta = next(item for item in payload["skirmish"]["items"]
                       if item["item_id"] == 26733)
        current = barbuta["copies"][0]
        self.assertIn("Accuracy+25", current["current"])
        self.assertEqual(current["selection"][0], picks[0])

        bad = self.call("POST", base + "/progress", {
            "op": "skirmish", "container": copy["container"], "slot": copy["slot"],
            "picks": [{"key": "acc", "value": 999}],
        }, token=token)
        self.assertEqual(bad.status, 422, bad.payload)
        missing = self.call("POST", base + "/progress", {
            "op": "skirmish-clear", "container": 99, "slot": 99,
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)

        cleared = self.call("POST", base + "/progress", {
            "op": "skirmish-clear", "container": copy["container"],
            "slot": copy["slot"],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        payload = json.loads(cleared.payload)
        barbuta = next(item for item in payload["skirmish"]["items"]
                       if item["item_id"] == 26733)
        self.assertEqual(barbuta["copies"][0]["current"], "not augmented")

    def test_sinister_reign_card_and_max_augments(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Sinister", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.call("POST", base + "/gil", {"top_off": True}, token=token)

        empty = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(len(empty["sinister"]["items"]), 37)
        self.assertEqual(empty["sinister"]["catalog_size"], 37)
        self.assertFalse(any(item["owned"] for item in empty["sinister"]["items"]))

        bought = self.call("POST", base + "/armory", {"item_id": 27295}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        tights = next(item for item in data["sinister"]["items"]
                      if item["item_id"] == 27295)
        self.assertTrue(tights["owned"])
        self.assertEqual([row["text"] for row in tights["rows"]], [
            "STR+10", "DEX+10", "Dbl.Atk.+3%", "Triple Atk.+3%",
        ])
        copy = tights["copies"][0]
        applied = self.call("POST", base + "/progress", {
            "op": "sinister", "container": copy["container"], "slot": copy["slot"],
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        payload = json.loads(applied.payload)
        tights = next(item for item in payload["sinister"]["items"]
                      if item["item_id"] == 27295)
        self.assertEqual(tights["copies"][0]["current"],
                         "STR+10 | DEX+10 | Dbl.Atk.+3% | Triple Atk.+3%")

        missing = self.call("POST", base + "/progress", {
            "op": "sinister", "container": 99, "slot": 99,
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)
        cleared = self.call("POST", base + "/progress", {
            "op": "sinister-clear", "container": copy["container"],
            "slot": copy["slot"],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        payload = json.loads(cleared.payload)
        tights = next(item for item in payload["sinister"]["items"]
                      if item["item_id"] == 27295)
        self.assertEqual(tights["copies"][0]["current"], "not augmented")

    def test_oboro_card_and_path_cap(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Oboro", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        bought = self.call("POST", base + "/armory", {"item_id": 22099}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        musa = next(item for item in data["oboro"]["items"] if item["item_id"] == 22099)
        self.assertTrue(musa["owned"])
        self.assertEqual(len(musa["paths"]), 3)
        copy = musa["copies"][0]
        capped = self.call("POST", base + "/progress", {
            "op": "augment", "container": copy["container"],
            "slot": copy["slot"], "path": "C",
        }, token=token)
        self.assertEqual(capped.status, 200, capped.payload)
        payload = json.loads(capped.payload)
        musa = next(item for item in payload["oboro"]["items"] if item["item_id"] == 22099)
        current = musa["copies"][0]["current"]
        self.assertEqual((current["path"], current["rank"], current["index"]),
                         ("C", 25, 189))

    def test_temenos_card_and_rank30_cap(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Temenos", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        bought = self.call("POST", base + "/armory", {"item_id": 26275}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        mantle = next(item for item in data["augments"] if item["item_id"] == 26275)
        self.assertEqual((mantle["kind"], mantle["set"]),
                         ("temenos", "Temenos Furnace"))
        self.assertIsNone(mantle["current"])
        self.assertEqual(mantle["paths"][0]["rank"], 30)

        capped = self.call("POST", base + "/progress", {
            "op": "augment", "container": mantle["container"],
            "slot": mantle["slot"], "path": "A",
        }, token=token)
        self.assertEqual(capped.status, 200, capped.payload)
        payload = json.loads(capped.payload)
        mantle = next(item for item in payload["augments"] if item["item_id"] == 26275)
        self.assertEqual(mantle["current"]["rank"], 30)
        self.assertIn("Accuracy+25", " ".join(mantle["paths"][0]["augments"]))

    def test_telopanos_weapon_card_and_rank30_cap(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Telopanos", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        bought = self.call("POST", base + "/armory", {"item_id": 22188}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        saber = next(item for item in data["augments"] if item["item_id"] == 22188)
        self.assertEqual((saber["kind"], saber["set"]), ("limbus", "Telopanos"))
        self.assertIsNone(saber["current"])
        self.assertEqual(saber["paths"][0]["rank"], 30)
        self.assertEqual(saber["paths"][0]["augments"],
                         ["Damage+18", "Magic Damage+25", "HP+150"])

        capped = self.call("POST", base + "/progress", {
            "op": "augment", "container": saber["container"],
            "slot": saber["slot"], "path": "A",
        }, token=token)
        self.assertEqual(capped.status, 200, capped.payload)
        payload = json.loads(capped.payload)
        saber = next(item for item in payload["augments"] if item["item_id"] == 22188)
        current = saber["current"]
        self.assertEqual(
            (current["rank"], current["tier"], current["rp"], current["curve"],
             current["index"]),
            (30, 3, 55800, 1, 500))

    def test_magian_trial_upgrades_the_item(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Magian", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        bought = self.call("POST", base + "/armory", {"item_id": 19332}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)

        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        peeler = next(item for item in data["magian"]["items"]
                      if item["item_id"] == 19332)
        self.assertGreater(data["magian"]["catalog_size"], 500)
        self.assertEqual(len(peeler["copies"]), 1)
        copy = peeler["copies"][0]
        self.assertEqual(copy["current"], "no trial")

        applied = self.call("POST", base + "/progress", {
            "op": "magian", "container": copy["container"], "slot": copy["slot"],
            "trial": 2,
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        payload = json.loads(applied.payload)
        renegade = next(item for item in payload["magian"]["items"]
                        if item["item_id"] == 19333)
        self.assertEqual(len(renegade["copies"]), 1)
        self.assertEqual(renegade["copies"][0]["current"], "no trial")

        bad = self.call("POST", base + "/progress", {
            "op": "magian", "container": copy["container"], "slot": copy["slot"],
            "trial": 3200,
        }, token=token)
        self.assertEqual(bad.status, 422, bad.payload)
        missing = self.call("POST", base + "/progress", {
            "op": "magian", "container": 99, "slot": 99, "trial": 2,
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)

    def test_moonshade_card_and_augment(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Moonshade", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]
        self.assertEqual(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).status, 200)
        bought = self.call("POST", base + "/armory", {"item_id": 11697}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)

        card = json.loads(self.call("GET", base + "/data", token=token).payload)["moonshade"]
        self.assertEqual(card["item_id"], 11697)
        self.assertEqual([len(group["options"]) for group in card["sets"]], [8, 8])
        self.assertEqual(len(card["copies"]), 1)
        copy = card["copies"][0]
        self.assertIsNone(copy["current"])

        applied = self.call("POST", base + "/progress", {
            "op": "moonshade", "container": copy["container"], "slot": copy["slot"],
            "first": "acc", "second": "tp_bonus",
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        current = json.loads(applied.payload)["moonshade"]["copies"][0]["current"]
        self.assertEqual((current["first"], current["second"]), ("acc", "tp_bonus"))
        self.assertEqual(current["text"], ["Accuracy+4", "TP Bonus+250"])

        bad = self.call("POST", base + "/progress", {
            "op": "moonshade", "container": copy["container"], "slot": copy["slot"],
            "first": "acc", "second": "nope",
        }, token=token)
        self.assertEqual(bad.status, 422, bad.payload)

        cleared = self.call("POST", base + "/progress", {
            "op": "moonshade-clear", "container": copy["container"], "slot": copy["slot"],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        self.assertIsNone(
            json.loads(cleared.payload)["moonshade"]["copies"][0]["current"])

        missing = self.call("POST", base + "/progress", {
            "op": "moonshade-clear", "container": 99, "slot": 99,
        }, token=token)
        self.assertEqual(missing.status, 404, missing.payload)

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
        self.assertFalse(found[0]["unique"])

        # Exact names sort before the other Nyame pieces.
        nyame = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["nyame helm"]}).payload)["items"]
        self.assertEqual(nyame[0]["name"], "Nyame Helm")
        self.assertEqual((nyame[0]["rare"], nyame[0]["ex"], nyame[0]["unique"]),
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

        # Ex alone is not one-per-character: Andartia's Mantle cannot be traded,
        # but the character may hold several copies.
        mantle = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Andartia's Mantle"]}).payload)["items"][0]
        self.assertEqual((mantle["rare"], mantle["ex"], mantle["unique"]), (0, 1, False))
        first_mantle = self.call("POST", base + "/armory", {"item_id": 26258}, token=token)
        self.assertEqual(first_mantle.status, 201, first_mantle.payload)
        second_mantle = self.call("POST", base + "/armory", {"item_id": 26258}, token=token)
        self.assertEqual(second_mantle.status, 201, second_mantle.payload)
        bought = json.loads(second_mantle.payload)["data"]["purchases"]
        self.assertEqual(sum(1 for row in bought if row["item_id"] == 26258), 2)

        # A fresh character with the starter wallet cannot afford an i119 purchase.
        other = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Broke", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        poor = self.call("POST", "/api/v1/characters/%d/armory" % other["id"],
                         {"item_id": 23761}, token=token)
        self.assertEqual(poor.status, 422)
        self.assertEqual(json.loads(poor.payload)["error"]["code"], "insufficient_gil")

    def test_prime_weapon_search_and_purchase_use_the_final_form(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Prime", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        # The four Foenaria stage rows collapse to the iLvl 119 III form, and the
        # stage-1 "Prime Scythe" name resolves to the same row.
        for query in ("Foenaria", "Prime Scythe"):
            with self.subTest(query=query):
                rows = json.loads(self.call(
                    "GET", base + "/items/search", token=token,
                    query={"q": [query], "scope": ["armory"]}).payload)["items"]
                self.assertEqual([row["item_id"] for row in rows], [21837])
                self.assertTrue(rows[0]["prime_final"])
                self.assertEqual((rows[0]["prime_stage"], rows[0]["prime_stages"]), (5, 5))

        self.call("POST", base + "/gil", {"top_off": True}, token=token)
        bought = self.call("POST", base + "/armory", {"item_id": 21834}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        body = json.loads(bought.payload)
        self.assertEqual((body["item"]["item_id"], body["item"]["name"]),
                         (21837, "Foenaria"))
        purchase = body["data"]["purchases"][0]
        self.assertEqual((purchase["item_id"], purchase["prime_final"]), (21837, True))

    def test_rema_weapon_search_and_purchase_use_the_final_form(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Rema", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        # Eight Masamune stages collapse to the one afterglow row.  Fudo Masamune is
        # a different weapon, so it stays in the result.
        rows = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Masamune"], "scope": ["armory"]}).payload)["items"]
        self.assertEqual([row["item_id"] for row in rows if row["name"] == "Masamune"],
                         [21956])
        self.assertTrue(next(row for row in rows if row["item_id"] == 21956)["rema_final"])
        self.assertIn(21917, [row["item_id"] for row in rows])  # Fudo Masamune

        # A final row with a 119 III suffix is found under the base name too.
        rows = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Kikoku"], "scope": ["armory"]}).payload)["items"]
        self.assertEqual([row["item_id"] for row in rows], [21906])

        self.call("POST", base + "/gil", {"top_off": True}, token=token)
        bought = self.call("POST", base + "/armory", {"item_id": 19406}, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        body = json.loads(bought.payload)
        self.assertEqual((body["item"]["item_id"], body["item"]["name"]),
                         (21956, "Masamune"))
        purchase = body["data"]["purchases"][0]
        self.assertEqual((purchase["item_id"], purchase["rema_final"]), (21956, True))

    def test_item_store_catalogue_and_stack_purchases(self):
        self.assertGreater(
            int(self.db.one(
                "SELECT COUNT(*) AS n FROM items WHERE category != '' AND price > 0")["n"]),
            4000,
        )
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Itemshop", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        categories = {row["name"]: row["count"] for row in data["item_categories"]}
        self.assertGreater(categories["Ninja Tools"], 40)
        self.assertGreater(categories["Jug Pets"], 90)
        self.assertGreater(categories["Consumables"], 50)
        self.assertGreater(categories["Ingredients"], 300)

        # The typeahead is scoped: Shihei is in the item shop, not the Armory, and
        # the Armory typeahead must not start returning general items.
        shihei = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Shihei"], "scope": ["items"]}).payload)["items"][0]
        self.assertEqual(
            (shihei["name"], shihei["category"], shihei["stack"]),
            ("Shihei", "Ninja Tools", 99),
        )
        self.assertGreater(shihei["price"], 0)
        self.assertEqual(shihei["held"], 0)
        self.assertFalse(shihei["unique"])
        armory = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Shihei"], "scope": ["armory"]}).payload)["items"]
        self.assertEqual(armory, [])

        # An empty query with a category browses that shelf, and the toolbag is a
        # separate stackable ninja-tool row.
        shelf = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"scope": ["items"], "category": ["Ninja Tools"]}).payload)["items"]
        self.assertGreaterEqual(len(shelf), 40)
        self.assertTrue(all(row["category"] == "Ninja Tools" for row in shelf))
        toolbag = next(row for row in shelf if row["item_id"] == 5314)
        self.assertEqual((toolbag["name"], toolbag["stack"]), ("Toolbag (Shihei)", 12))

        gil = json.loads(self.call("POST", base + "/gil", {"top_off": True},
                                   token=token).payload)["gil"]
        bought = self.call("POST", base + "/items", {
            "item_id": shihei["item_id"], "quantity": 99,
        }, token=token)
        self.assertEqual(bought.status, 201, bought.payload)
        body = json.loads(bought.payload)
        self.assertEqual(body["item"]["quantity"], 99)
        self.assertEqual(body["item"]["price"], shihei["price"] * 99)
        self.assertEqual(body["data"]["gil"], gil - shihei["price"] * 99)
        held = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Shihei"], "scope": ["items"]}).payload)["items"][0]
        self.assertEqual((held["held"], held["owned"]), (99, True))

        # Jugs and pet items are in the same catalogue but have their own shelves.
        jug = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Carrot Broth"], "scope": ["items"]}).payload)["items"][0]
        self.assertEqual(jug["category"], "Jug Pets")
        self.assertEqual(jug["stack"], 12)
        pet_food = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Gausebit Wildgrass"], "scope": ["items"]}).payload)["items"][0]
        self.assertEqual(pet_food["category"], "Pet Items")

        # A stack purchase records one purchase row with the total price.
        jug_buy = self.call("POST", base + "/items", {
            "item_id": jug["item_id"], "quantity": jug["stack"],
        }, token=token)
        self.assertEqual(jug_buy.status, 201, jug_buy.payload)
        history = json.loads(
            self.call("GET", base + "/data", token=token).payload)["purchases"]
        jug_row = next(row for row in history if row["item_id"] == jug["item_id"])
        self.assertEqual(jug_row["quantity"], jug["stack"])
        self.assertEqual(jug_row["price"], jug["price"] * jug["stack"])

        # Rare is one-per-character: a stack is refused before any gil is charged,
        # then the first single copy succeeds and a second one is already owned.
        rare = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Rusty Key"], "scope": ["items"]}).payload)["items"][0]
        self.assertEqual((rare["rare"], rare["ex"], rare["unique"]), (1, 1, True))
        rare_stack = self.call("POST", base + "/items", {
            "item_id": rare["item_id"], "quantity": 2,
        }, token=token)
        self.assertEqual(rare_stack.status, 422)
        self.assertEqual(json.loads(rare_stack.payload)["error"]["code"], "rare_item")
        first = self.call("POST", base + "/items", {"item_id": rare["item_id"]}, token=token)
        self.assertEqual(first.status, 201, first.payload)
        again = self.call("POST", base + "/items", {"item_id": rare["item_id"]}, token=token)
        self.assertEqual(again.status, 409)
        self.assertEqual(json.loads(again.payload)["error"]["code"], "already_owned")

        # The two scopes stay separate in both directions.
        sword = json.loads(self.call(
            "GET", base + "/items/search", token=token,
            query={"q": ["Bronze Sword"], "kind": ["weapon"]}).payload)["items"][0]
        gear = self.call("POST", base + "/items", {"item_id": sword["item_id"]}, token=token)
        self.assertEqual(gear.status, 422)
        item = self.call("POST", base + "/armory", {"item_id": shihei["item_id"]}, token=token)
        self.assertEqual(item.status, 422)

        # A fresh character has 1,000 gil: a 99-shihei stack costs more than the
        # wallet, so the purchase is refused before the inventory changes.
        broke = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Itemless", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        poor = self.call("POST", "/api/v1/characters/%d/items" % broke["id"],
                         {"item_id": shihei["item_id"], "quantity": 99}, token=token)
        self.assertEqual(poor.status, 422)
        self.assertEqual(json.loads(poor.payload)["error"]["code"], "insufficient_gil")

    def test_character_merit_layout_editor(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Merits", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        base = "/api/v1/characters/%d" % character["id"]

        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        menus = data["merits"]["categories"]
        self.assertEqual(len(menus), 50)
        self.assertEqual(sum(len(menu["merits"]) for menu in menus), 274)
        self.assertEqual(menus[0]["name"], "HP/MP")
        self.assertEqual(menus[6]["name"], "Warrior Group 1")
        self.assertEqual(menus[6]["max"], 10)
        self.assertEqual(menus[6]["merits"][0]["name"], "Berserk Recast")
        self.assertEqual(menus[6]["merits"][0]["max"], 5)
        self.assertEqual(menus[6]["merits"][0]["costs"], [1, 2, 3, 4, 5])

        # Only the rows the launcher sends are changed.  Ten upgrades fit the
        # category's cap exactly; an eleventh is refused with the menu's name.
        applied = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 5, str(0x0182): 5},
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        refreshed = json.loads(applied.payload)
        warrior = refreshed["merits"]["categories"][6]
        self.assertEqual(warrior["used"], 10)
        self.assertEqual(warrior["spent"], 30)
        self.assertEqual(refreshed["merits"]["spent"], 30)
        self.assertEqual(refreshed["merits"]["points"], 127)
        self.assertEqual([row["upgrades"] for row in warrior["merits"][:2]], [5, 5])

        full = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0184): 1},
        }, token=token)
        self.assertEqual(full.status, 422)
        self.assertEqual(json.loads(full.payload)["error"]["code"], "merit_category_full")

        unknown = self.call("POST", base + "/merits", {
            "upgrades": {"65535": 1},
        }, token=token)
        self.assertEqual(unknown.status, 422)
        too_high = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 6},
        }, token=token)
        self.assertEqual(too_high.status, 422)

        cleared = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 0, str(0x0182): 0, str(0x0184): 0,
                         str(0x0186): 0, str(0x0188): 0},
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        empty = self.call("POST", base + "/merits", {"points": 0}, token=token)
        self.assertEqual(empty.status, 200, empty.payload)

        # Game-rule mode charges the net difference and refuses a layout the pool
        # cannot cover.
        refused = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 1}, "spend": True,
        }, token=token)
        self.assertEqual(refused.status, 422)
        self.assertEqual(json.loads(refused.payload)["error"]["code"],
                         "insufficient_merit_points")
        self.assertEqual(int(self.service.character(character["id"])["merit_points"]), 0)

        self.call("POST", base + "/merits", {"points": 100}, token=token)
        charged = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 5}, "spend": True,
        }, token=token)
        self.assertEqual(charged.status, 200, charged.payload)
        self.assertEqual(json.loads(charged.payload)["merits"]["points"], 85)
        refunded = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0180): 0}, "spend": True,
        }, token=token)
        self.assertEqual(refunded.status, 200, refunded.payload)
        self.assertEqual(json.loads(refunded.payload)["merits"]["points"], 100)

        # A character assigned before the editor existed can sit above a menu's
        # cap.  Lowering it is allowed; pushing it further over is not.
        for merit_id in (0x0140, 0x0142, 0x0144, 0x0146, 0x0148):
            self.service.save_merit(int(character["id"]), merit_id, 5)
        lowered = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0140): 4},
        }, token=token)
        self.assertEqual(lowered.status, 200, lowered.payload)
        other = next(menu for menu in json.loads(lowered.payload)["merits"]["categories"]
                     if menu["id"] == 0x0140)
        self.assertGreater(other["used"], other["max"])
        again = self.call("POST", base + "/merits", {
            "upgrades": {str(0x0140): 5},
        }, token=token)
        self.assertEqual(again.status, 422)
        self.assertEqual(json.loads(again.payload)["error"]["code"], "merit_category_full")

        # The old point/top-off modes still work on the same endpoint.
        topped = self.call("POST", base + "/merits", {"top_off": True}, token=token)
        self.assertEqual(topped.status, 200)
        self.assertEqual(json.loads(topped.payload)["merits"]["points"],
                         json.loads(topped.payload)["merits"]["cap"])

    def test_shantotto_ascension_augment_card(self):
        token = self.register()["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Ascension", "race": 1, "face": 1, "size": 1, "nation": 0},
            token=token).payload)["character"]
        cid = int(character["id"])
        self.service.add_item(cid, 16370)
        copy = next(row for row in self.service.inventory(cid) if row["item_id"] == 16370)
        base = "/api/v1/characters/%d" % cid

        data = json.loads(self.call("GET", base + "/data", token=token).payload)
        self.assertEqual(len(data["ascension"]["items"]), 3)
        self.assertEqual(len(data["ascension"]["options"]), 33)
        item = next(entry for entry in data["ascension"]["items"] if entry["item_id"] == 16370)
        self.assertEqual(item["name"], "Desultor Tassets")
        self.assertEqual(item["copies"][0]["choices"], [])

        applied = self.call("POST", base + "/ascension", {
            "container": copy["container"], "slot": copy["slot"],
            "choices": ["phantom_roll_5"],
        }, token=token)
        self.assertEqual(applied.status, 200, applied.payload)
        refreshed = json.loads(applied.payload)
        item = next(entry for entry in refreshed["ascension"]["items"]
                    if entry["item_id"] == 16370)
        self.assertEqual(item["copies"][0]["choices"], ["phantom_roll_5"])
        self.assertIn("Phantom Roll", item["copies"][0]["text"])
        extra = next(row["extra"] for row in self.service.inventory(cid)
                     if row["item_id"] == 16370)
        self.assertEqual(bytes(extra)[:2], b"\x02\x03")

        duplicate = self.call("POST", base + "/ascension", {
            "container": copy["container"], "slot": copy["slot"],
            "choices": ["phantom_roll_5", "phantom_roll_5"],
        }, token=token)
        self.assertEqual(duplicate.status, 422)
        wrong_item = self.call("POST", base + "/ascension", {
            "container": 0, "slot": 0, "choices": ["phantom_roll_5"],
        }, token=token)
        self.assertEqual(wrong_item.status, 422)

        cleared = self.call("POST", base + "/ascension", {
            "container": copy["container"], "slot": copy["slot"], "choices": [],
        }, token=token)
        self.assertEqual(cleared.status, 200, cleared.payload)
        item = next(entry for entry in json.loads(cleared.payload)["ascension"]["items"]
                    if entry["item_id"] == 16370)
        self.assertEqual(item["copies"][0]["choices"], [])

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

    # --- mounts -------------------------------------------------------------------------------
    def test_mount_catalogue_needs_a_session_and_lists_every_mount(self):
        self.assertEqual(self.call("GET", "/api/v1/mounts").status, 401)
        token = self.register()["token"]
        response = self.call("GET", "/api/v1/mounts", token=token)
        self.assertEqual(response.status, 200, response.payload)
        mounts = json.loads(response.payload)["mounts"]
        self.assertGreaterEqual(len(mounts), 37)
        self.assertEqual(mounts[0]["name"], "Chocobo")
        self.assertEqual(mounts[0]["chocobo_index"], 1)
        self.assertTrue(all({"id", "name", "description", "japanese"} <= set(m) for m in mounts))

    def test_character_mount_is_remembered_while_offline(self):
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Mounter", "race": 1, "face": 1, "size": 1, "nation": 0},
                            token=token)
        self.assertEqual(created.status, 201, created.payload)
        character_id = json.loads(created.payload)["character"]["id"]
        base = "/api/v1/characters/%d/mount" % character_id

        before = self.call("GET", base, token=token)
        self.assertEqual(before.status, 200, before.payload)
        self.assertIsNone(json.loads(before.payload)["mount"])

        mounted = self.call("POST", base, {"mount": "Raptor"}, token=token)
        self.assertEqual(mounted.status, 200, mounted.payload)
        payload = json.loads(mounted.payload)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["online"])
        self.assertEqual(payload["mount"]["id"], 1)
        self.assertEqual(payload["mounted"], [])

        after = json.loads(self.call("GET", base, token=token).payload)
        self.assertIsNone(after["mount"])
        self.assertEqual(after["last_mount"], "Raptor")
        self.assertEqual(after["last_mount_id"], 1)

        family = self.call("POST", base, {"mount": "Tiger", "all": True}, token=token)
        self.assertEqual(family.status, 200, family.payload)
        self.assertEqual(json.loads(family.payload)["named"], "all")
        self.assertEqual(json.loads(self.call("GET", base, token=token).payload)["last_mount"],
                         "Tiger")

        # A dismount is live state, not a stored choice: the last called mount stays.
        off = self.call("POST", base, {"mount": "off"}, token=token)
        self.assertEqual(off.status, 200, off.payload)
        self.assertEqual(json.loads(self.call("GET", base, token=token).payload)["last_mount"],
                         "Tiger")

    def test_get_all_mounts_reissues_the_unlock(self):
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Mounter", "race": 1, "face": 1, "size": 1, "nation": 0},
                            token=token)
        character_id = json.loads(created.payload)["character"]["id"]
        response = self.call("POST", "/api/v1/characters/%d/mounts" % character_id,
                             {}, token=token)
        self.assertEqual(response.status, 200, response.payload)
        data = json.loads(response.payload)
        self.assertTrue(data["mounts"]["all_available"])
        self.assertEqual(data["mounts"]["count"], len(data["mounts"]["names"]))
        self.assertGreaterEqual(data["mounts"]["count"], 37)
        self.assertIsNone(data["mounts"]["current"])
        self.assertIn("Chocobo", data["mounts"]["names"])

    def test_unknown_mount_is_refused(self):
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Mounter", "race": 1, "face": 1, "size": 1, "nation": 0},
                            token=token)
        character_id = json.loads(created.payload)["character"]["id"]
        response = self.call("POST", "/api/v1/characters/%d/mount" % character_id,
                             {"mount": "unicorn"}, token=token)
        self.assertEqual(response.status, 422)
        self.assertIn("no mount", json.loads(response.payload)["error"]["message"])

    def test_another_accounts_character_is_not_mountable(self):
        token = self.register()["token"]
        created = self.call("POST", "/api/v1/characters",
                            {"name": "Mounter", "race": 1, "face": 1, "size": 1, "nation": 0},
                            token=token)
        character_id = json.loads(created.payload)["character"]["id"]
        other = json.loads(self.call(
            "POST", "/api/v1/auth/register",
            {"username": "other", "password": "password123"}).payload)["token"]
        response = self.call("POST", "/api/v1/characters/%d/mount" % character_id,
                             {"mount": "Raptor"}, token=other)
        self.assertEqual(response.status, 404)



if __name__ == "__main__":
    unittest.main()
