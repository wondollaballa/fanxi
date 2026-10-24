"""Saved /!warp places: storage, the HTTP snapshot and the in-game command."""
from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession
from fanxi_server.http_api import Api, Request
from fanxi_server.service import ApiError, WARP_SLOT_MAX


def chats(session):
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


class WarpServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Fanxi", "race": 1})
        self.cid = int(self.character["id"])

    def test_mark_list_rename_and_delete(self):
        warp = self.service.mark_warp(
            self.cid, "Fishing Camp", 100, [-376.0, -50.0, 311.0, 64])
        self.assertEqual(warp["slot"], 1)
        self.assertEqual(warp["alias"], "Fishing Camp")
        self.assertEqual(warp["zone_name"], "West Ronfaure")
        self.assertAlmostEqual(warp["x"], -376.0)

        second = self.service.mark_warp(self.cid, "", 246, [1.0, 2.0, 3.0, 0])
        self.assertEqual(second["slot"], 2)
        payload = self.service.warp_payload(self.cid)
        self.assertEqual(payload["limit"], WARP_SLOT_MAX)
        self.assertEqual(payload["next_slot"], 3)
        self.assertEqual([item["slot"] for item in payload["warps"]], [1, 2])

        renamed = self.service.rename_warp(self.cid, 2, "Mog House")
        self.assertEqual(renamed["alias"], "Mog House")
        self.assertEqual(self.service.find_warps(self.cid, "fishing")[0]["slot"], 1)
        self.assertEqual(self.service.find_warps(self.cid, "MOG")[0]["slot"], 2)
        self.assertEqual(self.service.find_warps(self.cid, "2")[0]["slot"], 2)

        deleted = self.service.delete_warp(self.cid, 1)
        self.assertEqual(deleted["alias"], "Fishing Camp")
        self.assertEqual([item["slot"] for item in self.service.warps_for_character(self.cid)], [2])
        with self.assertRaises(ApiError):
            self.service.warp(self.cid, 1)

    def test_aliases_are_unique_and_printable_ascii(self):
        self.service.mark_warp(self.cid, "Camp", 100, [0, 0, 0, 0])
        with self.assertRaises(ApiError) as taken:
            self.service.mark_warp(self.cid, "camp", 101, [0, 0, 0, 0])
        self.assertEqual(taken.exception.code, "alias_taken")
        with self.assertRaises(ApiError):
            self.service.mark_warp(self.cid, "Caf\u00e9", 100, [0, 0, 0, 0])
        # An unnamed warp is still legal, and several can share the empty alias.
        self.service.mark_warp(self.cid, "", 100, [0, 0, 0, 0])
        self.service.mark_warp(self.cid, "", 101, [0, 0, 0, 0])
        self.assertEqual(len(self.service.warps_for_character(self.cid)), 3)

    def test_auto_increment_uses_one_past_the_highest_slot(self):
        first = self.service.mark_warp(self.cid, "", 100, [0, 0, 0, 0])
        second = self.service.mark_warp(self.cid, "", 100, [0, 0, 0, 0])
        self.service.delete_warp(self.cid, second["slot"])
        third = self.service.mark_warp(self.cid, "", 100, [0, 0, 0, 0])
        self.assertEqual(third["slot"], second["slot"])
        self.assertNotEqual(third["slot"], first["slot"])
        self.assertEqual(len(self.service.warps_for_character(self.cid)), 2)

    def test_marks_are_per_character_and_family_owned(self):
        sub = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Tinybox", "race": 1}})
        sub_cid = int(sub["character"]["id"])
        self.service.mark_warp(self.cid, "Main camp", 100, [0, 0, 0, 0])
        self.service.mark_warp(sub_cid, "Box camp", 101, [0, 0, 0, 0])
        self.assertEqual(self.service.warps_for_character(self.cid)[0]["alias"], "Main camp")
        self.assertEqual(self.service.warps_for_character(sub_cid)[0]["alias"], "Box camp")
        self.assertEqual(self.service.account_family_ids(self.account["id"]),
                         {self.account["id"], sub["id"]})
        self.assertTrue(self.service.account_can_manage_character(
            self.account["id"], sub_cid))
        other = self.service.register("other", "password123").account
        self.assertFalse(self.service.account_can_manage_character(
            other["id"], sub_cid))


class WarpApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.api = Api(self.config, self.service)

    def call(self, method, path, body=None, token=None):
        headers = {}
        if token:
            headers["authorization"] = "Bearer " + token
        raw = b"" if body is None else json.dumps(body).encode()
        return self.api.handle(Request(method=method, path=path, body=raw, headers=headers,
                                       remote="127.0.0.1"))

    def register(self, username="tester"):
        response = self.call("POST", "/api/v1/auth/register",
                             {"username": username, "password": "password123"})
        self.assertEqual(response.status, 201, response.payload)
        return json.loads(response.payload)

    def test_warp_crud_and_family_access(self):
        main = self.register()
        token = main["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Fanxi", "race": 1}, token=token).payload)["character"]
        cid = int(character["id"])

        empty = self.call("GET", "/api/v1/characters/%d/warps" % cid, token=token)
        self.assertEqual(empty.status, 200, empty.payload)
        self.assertEqual(json.loads(empty.payload)["warps"], [])
        self.assertEqual(json.loads(empty.payload)["next_slot"], 1)

        marked = self.call(
            "POST", "/api/v1/characters/%d/warps" % cid,
            {"alias": "Camp", "zone": 100, "x": -376, "y": -50, "z": 311, "rot": 64},
            token=token)
        self.assertEqual(marked.status, 201, marked.payload)
        data = json.loads(marked.payload)
        self.assertEqual(data["warp"]["slot"], 1)
        self.assertEqual(data["data"]["warps"][0]["zone_name"], "West Ronfaure")

        renamed = self.call(
            "PATCH", "/api/v1/characters/%d/warps/1" % cid,
            {"alias": "Ronfaure camp"}, token=token)
        self.assertEqual(renamed.status, 200, renamed.payload)
        self.assertEqual(json.loads(renamed.payload)["warp"]["alias"], "Ronfaure camp")

        deleted = self.call(
            "DELETE", "/api/v1/characters/%d/warps/1" % cid, token=token)
        self.assertEqual(deleted.status, 200, deleted.payload)
        self.assertEqual(json.loads(deleted.payload)["data"]["warps"], [])

        # A sub-account character is part of the main account's family.
        sub = self.service.create_sub_account(
            main["account"]["id"], {"character": {"name": "Tinybox", "race": 1}})
        sub_cid = int(sub["character"]["id"])
        allowed = self.call("GET", "/api/v1/characters/%d/warps" % sub_cid, token=token)
        self.assertEqual(allowed.status, 200, allowed.payload)

        # A different account's character stays invisible.
        other = self.register("other")
        other_char = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Notmine", "race": 1}, token=other["token"]).payload)["character"]
        denied = self.call(
            "GET", "/api/v1/characters/%d/warps" % int(other_char["id"]), token=token)
        self.assertEqual(denied.status, 404)

    def test_mark_uses_the_saved_position_when_none_is_sent(self):
        main = self.register()
        token = main["token"]
        character = json.loads(self.call(
            "POST", "/api/v1/characters",
            {"name": "Saver", "race": 1}, token=token).payload)["character"]
        cid = int(character["id"])
        self.service.save_position(cid, 101, [10.5, 20.5, 30.5, 12])
        response = self.call(
            "POST", "/api/v1/characters/%d/warps" % cid, {"alias": "Saved"}, token=token)
        self.assertEqual(response.status, 201, response.payload)
        warp = json.loads(response.payload)["warp"]
        self.assertEqual(warp["zone"], 101)
        self.assertAlmostEqual(warp["x"], 10.5)
        self.assertEqual(warp["rot"], 12)


class WarpCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Fanxi", "race": 1})
        self.sub = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Tinybox", "race": 1}})
        self.world = World(self.config, self.service, None)
        self.session = self.make_session(self.character, ("127.0.0.1", 1201), 100)
        self.sub_session = self.make_session(
            self.sub["character"], ("127.0.0.1", 1202), 246)
        self.session.queue.clear()
        self.sub_session.queue.clear()

    def make_session(self, character, addr, zone):
        session = ZoneSession(
            self.world, addr,
            self.service.character_record(self.service.character(character["id"]), "Fanxi"))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = int(zone)
        session.pos = list(self.world.zones.position(int(zone)))
        session.load_zone_entities()
        session.zone_loaded = True
        self.world.sessions[addr] = session
        return session

    def test_mark_list_me_all_and_delete(self):
        self.session.command(["warp", "mark", "Fishing", "Camp"])
        lines = "\n".join(chats(self.session))
        self.assertIn("Warp 1 marked: Fishing Camp", lines)
        warp = self.service.warps_for_character(int(self.character["id"]))[0]
        self.assertEqual(warp["alias"], "Fishing Camp")
        self.assertEqual(warp["zone"], 100)

        self.session.queue.clear()
        self.session.command(["warp", "list"])
        lines = "\n".join(chats(self.session))
        self.assertIn("Warps 1-1 of 1", lines)
        self.assertIn("1. Fishing Camp - West Ronfaure", lines)

        # Warp me by alias.
        start = list(self.session.pos)
        self.session.pos = [start[0] + 10.0, start[1], start[2] + 10.0, 0]
        self.session.queue.clear()
        self.session.command(["warp", "me", "fish"])
        self.assertIn("Warping to Fishing Camp (West Ronfaure).", chats(self.session))
        self.assertAlmostEqual(self.session.pos[0], warp["x"])
        self.assertAlmostEqual(self.session.pos[2], warp["z"])

        # Warp the family; the sub-account session is moved too.
        self.session.command(["warp", "all", "1"])
        self.assertEqual(self.sub_session.zone, 100)
        self.assertAlmostEqual(self.sub_session.pos[0], warp["x"])
        self.assertTrue(any("warps the group to Fishing Camp" in line
                            for line in chats(self.sub_session)))
        self.assertTrue(any(line.startswith("Warped 2 characters to Fishing Camp")
                            for line in chats(self.session)))

        self.session.queue.clear()
        self.session.command(["warp", "delete", "Fishing", "Camp"])
        self.assertIn("Warp 1 (Fishing Camp) deleted.", chats(self.session))
        self.assertEqual(self.service.warps_for_character(int(self.character["id"])), [])

    def test_rename_and_ambiguous_alias(self):
        self.session.command(["warp", "mark", "Camp"])
        self.session.command(["warp", "mark", "Campfire"])
        self.session.queue.clear()
        self.session.command(["warp", "me", "cam"])
        self.assertIn("Several warps match 'cam'", "\n".join(chats(self.session)))
        self.session.queue.clear()
        self.session.command(["warp", "rename", "2", "Evening", "Camp"])
        self.assertIn("Warp 2 renamed to Evening Camp.", chats(self.session))
        self.assertEqual(self.service.find_warps(int(self.character["id"]), "evening")[0]["slot"], 2)


if __name__ == "__main__":
    unittest.main()
