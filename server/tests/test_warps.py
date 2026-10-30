"""Saved //warp places: storage, the HTTP snapshot and the in-game command."""
from __future__ import annotations

import json
import struct
import tempfile
import time
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
        session.last_packet_at = time.time()
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

    def test_warp_all_me_calls_the_team_to_the_sender(self):
        # An alias named "me" must not shadow the built-in target.
        self.session.command(["warp", "mark", "me"])
        self.assertEqual(
            self.service.warps_for_character(int(self.character["id"]))[0]["alias"], "me")

        # The leader moves; the team follows to that exact zone, position and heading.
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        other = self.service.register("other", "password123").account
        other_character = self.service.create_character(
            other["id"], {"name": "Notmine", "race": 1})
        other_session = self.make_session(
            other_character, ("127.0.0.1", 1203), 100)
        other_pos = list(other_session.pos)
        self.session.queue.clear()
        self.sub_session.queue.clear()
        other_session.queue.clear()

        self.session.command(["warp", "all", "me"])

        self.assertEqual(self.sub_session.zone, 100)
        self.assertEqual(self.sub_session.pos, [10.0, 20.0, 30.0, 128])
        self.assertTrue(self.sub_session.zoning)
        self.assertIn("warps you to their side in West Ronfaure.",
                      "\n".join(chats(self.sub_session)))
        self.assertIn("Warped 1 character to you in West Ronfaure.", chats(self.session))
        # The leader is already there and must not be reloaded by its own call.
        self.assertEqual(self.session.pos, [10.0, 20.0, 30.0, 128])
        self.assertFalse(self.session.zoning)
        # A different account's character is not part of the family.
        self.assertEqual(other_session.pos, other_pos)
        self.assertFalse(other_session.zoning)

    def test_warp_all_me_in_the_same_zone_hands_the_box_in_again(self):
        # Same zone still needs 0x00B: the client ignores its own 0x00D position update,
        # so the old "no reload" shortcut left every box standing where it was.
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 100
        self.sub_session.pos = [1.0, 2.0, 3.0, 4]
        self.sub_session.zoning = False
        self.sub_session.queue.clear()

        self.session.command(["warp", "all", "me"])

        self.assertEqual(self.sub_session.pos, [10.0, 20.0, 30.0, 128])
        self.assertTrue(self.sub_session.zoning)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.sub_session.queue]
        self.assertIn(0x00B, types)
        self.assertNotIn(0x00D, types)

    def test_a_warp_is_handed_off_even_when_the_server_thinks_the_box_is_there(self):
        """The server's position can be the anchor while the client is at the zone spawn.

        The old same-spot shortcut skipped the warp exactly then, so the box stayed yards
        away and only a moving anchor (spamming the command while walking) got it moved.
        """
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 100
        self.sub_session.pos = [10.0, 20.0, 30.0, 128]  # server already believes this
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.queue.clear()

        self.session.command(["warp", "all", "me"])

        self.assertTrue(self.sub_session.zoning)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.sub_session.queue]
        self.assertIn(0x00B, types)

    def test_a_box_still_logging_in_joins_the_team_anchor_when_it_arrives(self):
        """A relaunching box is not in the session list yet; it joins on its zone-in.

        Without the anchor the box landed at its saved spot and only a second
        ``//warp all me`` moved it — the 45-second "it finally clicked" report.
        """
        third = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Thirdbox", "race": 1}})
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.session.queue.clear()

        self.session.command(["warp", "all", "me"])
        self.assertIsNotNone(self.world.team_anchor)

        # The box finishes logging in in another zone, after the command.
        late = self.make_session(third["character"], ("127.0.0.1", 1210), 246)
        late.pos = [1.0, 2.0, 3.0, 4]
        late.zoning = False
        late.zone_loaded = True
        self.assertTrue(self.world.join_team_anchor(late))
        self.assertEqual(int(late.zone), 100)
        self.assertEqual(late.pos, [10.0, 20.0, 30.0, 128])
        self.assertTrue(late.zoning)

    def test_a_main_teleport_brings_the_family_boxes(self):
        """A survival guide, home point or warp spell moves the boxes with the leader."""
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 100
        self.sub_session.pos = [1.0, 2.0, 3.0, 4]
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True

        self.session.change_zone(101, [7.0, 8.0, 9.0, 64])
        self.world.advance(time.time())

        self.assertEqual(int(self.sub_session.zone), 101)
        self.assertEqual(self.sub_session.pos, [7.0, 8.0, 9.0, 64])
        self.assertTrue(self.sub_session.zoning)

    def test_a_sub_teleport_does_not_move_the_main(self):
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 100
        self.sub_session.pos = [1.0, 2.0, 3.0, 4]
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.session.zoning = False

        self.sub_session.change_zone(101, [7.0, 8.0, 9.0, 64])

        self.assertEqual(int(self.session.zone), 100)
        self.assertFalse(self.session.zoning)

    def test_a_no_op_warp_is_skipped_only_after_the_client_reports_its_position(self):
        """Before the first position packet the server only knows where it sent the box."""
        self.sub_session.zone = 100
        self.sub_session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.position_seen = True
        self.assertFalse(self.sub_session.change_zone(100, [10.0, 20.0, 30.0, 128]))
        self.assertFalse(self.sub_session.zoning)

        self.sub_session.position_seen = False
        self.assertTrue(self.sub_session.change_zone(100, [10.0, 20.0, 30.0, 128]))
        self.assertTrue(self.sub_session.zoning)

    def test_warp_all_me_zones_the_whole_team_in_one_tick(self):
        """Every box gets its own 0x00B in the same tick.

        Measured live: five boxes from command to all-in-world in 4.5 s.  The old queue
        spaced them three seconds apart, and a first-load gate measured 11.8 s because it
        serialized a load the clients can overlap.
        """
        second = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Secondbox", "race": 1}})
        second_session = self.make_session(
            second["character"], ("127.0.0.1", 1203), 246)
        targets = [self.sub_session, second_session]
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        for target in targets:
            target.zone = 100
            target.pos = [1.0, 2.0, 3.0, 4]
            target.zoning = False
            target.zone_loaded = True
            target.queue.clear()

        self.session.command(["warp", "all", "me"])
        self.assertIn("Warped 2 characters to you in West Ronfaure.", chats(self.session))
        self.assertEqual([target.pos for target in targets],
                         [[1.0, 2.0, 3.0, 4], [1.0, 2.0, 3.0, 4]])

        self.world.advance(time.time())
        self.assertEqual([target.pos for target in targets],
                         [[10.0, 20.0, 30.0, 128], [10.0, 20.0, 30.0, 128]])
        self.assertTrue(all(target.zoning for target in targets))

    def test_warp_call_brings_one_family_character(self):
        # The single-target form the launcher fires when a box comes back from a relog.
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 246
        self.sub_session.zoning = False
        self.session.queue.clear()
        self.sub_session.queue.clear()

        self.session.command(["warp", "call", "tinybox"])

        self.assertEqual(self.sub_session.zone, 100)
        self.assertEqual(self.sub_session.pos, [10.0, 20.0, 30.0, 128])
        self.assertTrue(self.sub_session.zoning)
        self.assertIn("calls you to their side in West Ronfaure.",
                      "\n".join(chats(self.sub_session)))
        self.assertIn("Called Tinybox to you in West Ronfaure.", chats(self.session))

        # Same zone: the hand-off is still required; a self position update is ignored.
        self.sub_session.zoning = False
        self.sub_session.zone = 100
        self.sub_session.pos = [1.0, 2.0, 3.0, 4]
        self.sub_session.queue.clear()
        self.session.command(["warp", "call", "Tinybox"])
        self.assertEqual(self.sub_session.pos, [10.0, 20.0, 30.0, 128])
        self.assertTrue(self.sub_session.zoning)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.sub_session.queue]
        self.assertIn(0x00B, types)
        self.assertNotIn(0x00D, types)
        # Let the simulated client finish the zone-in before the whole-team call.
        self.sub_session.zoning = False

        # "all" is the whole-team call, and an unknown name is reported, not silently dropped.
        self.session.queue.clear()
        self.session.command(["warp", "call", "all"])
        self.assertIn("Warped 1 character to you in West Ronfaure.", chats(self.session))
        self.session.queue.clear()
        self.session.command(["warp", "call", "Nobody"])
        self.assertIn("No character called Nobody is online.", chats(self.session))
        self.session.queue.clear()
        self.session.command(["warp", "call", "Fanxi"])
        self.assertIn("That is you.", chats(self.session))

    def test_a_repeated_pull_to_the_same_anchor_does_not_zone_again(self):
        # The launcher's auto-pull can arrive just after the box has been handed back to
        # the leader's spot.  A second 0x00B there is the re-zone loop that kept a box out
        # of the world, and advanced its zone key every fifteen seconds.
        self.session.zone = 100
        self.session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.zone = 100
        self.sub_session.pos = [1.0, 2.0, 3.0, 4]
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.queue.clear()

        self.session.command(["warp", "call", "Tinybox"])
        self.assertTrue(self.sub_session.zoning)

        # The box finishes the hand-off on the anchor; the next poll calls it again
        # before its first position packet can prove where the client really is.
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.pos = [10.0, 20.0, 30.0, 128]
        self.sub_session.queue.clear()
        self.session.queue.clear()

        self.session.command(["warp", "call", "Tinybox"])

        self.assertFalse(self.sub_session.zoning)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.sub_session.queue]
        self.assertNotIn(0x00B, types)
        self.assertIn("Tinybox is already with you in West Ronfaure.", chats(self.session))

        # The guard is not permanent: a call after the window still hands the box off.
        self.sub_session.warped_to = (100, [10.0, 20.0, 30.0, 128], time.time() - 200.0)
        self.sub_session.queue.clear()
        self.session.queue.clear()
        self.session.command(["warp", "call", "Tinybox"])
        self.assertTrue(self.sub_session.zoning)

    def test_mh_out_brings_a_family_box_outside(self):
        # A headless box has no Mog House menu: //mh out does what the menu would, from
        # the server, using the box's own city door.
        self.sub_session.char["moghouse"] = 1
        self.sub_session.zone = 100
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.queue.clear()

        self.session.command(["mh", "out"])

        self.assertEqual(int(self.sub_session.char["moghouse"]), 0)
        self.assertTrue(self.sub_session.zoning)
        types = [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                 for message in self.sub_session.queue]
        self.assertIn(0x00B, types)
        self.assertEqual(self.sub_session.pos, self.sub_session.moghouse_door(100))

    def test_warp_all_me_inside_the_mog_house_is_refused(self):
        # The leader's anchor inside is the interior origin, not a place to hand a box.
        self.session.char["moghouse"] = 1
        self.sub_session.zoning = False
        self.sub_session.queue.clear()
        self.session.queue.clear()

        self.session.command(["warp", "all", "me"])

        self.assertFalse(self.sub_session.zoning)
        self.assertIn("Mog House", " ".join(chats(self.session)))

    def test_warp_call_refuses_another_account(self):
        other = self.service.register("other", "password123").account
        other_character = self.service.create_character(
            other["id"], {"name": "Notmine", "race": 1})
        other_session = self.make_session(other_character, ("127.0.0.1", 1203), 246)
        other_pos = list(other_session.pos)
        self.session.zone = 100
        self.session.queue.clear()

        self.session.command(["warp", "call", "Notmine"])

        self.assertIn("Notmine is not on your account or a sub-account.", chats(self.session))
        self.assertEqual(other_session.pos, other_pos)
        self.assertFalse(other_session.zoning)

    def test_warp_skips_parked_boxes(self):
        # //sleep leaves the client only reading chat, so a zone-in sent to it is dropped
        # and the box would stay "zoning" forever.  Parked boxes are out of the warp group.
        self.sub_session.sleeping = True
        self.sub_session.zone = 246
        self.session.zone = 100
        self.session.queue.clear()

        self.session.command(["warp", "call", "Tinybox"])
        self.assertIn("Tinybox is asleep; //wake it first.", chats(self.session))
        self.assertEqual(self.sub_session.zone, 246)

        self.session.queue.clear()
        self.session.command(["warp", "all", "me"])
        self.assertTrue(any("No other characters in your team are online" in line
                            for line in chats(self.session)))
        self.assertEqual(self.sub_session.zone, 246)

        self.sub_session.sleeping = False
        self.session.queue.clear()
        self.session.command(["warp", "call", "Tinybox"])
        self.assertEqual(self.sub_session.zone, 100)

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
