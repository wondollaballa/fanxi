"""Mounts on the wire: who is told, with which id, and what the client reads.

A mount is one client-side model choice with three server-side mirrors: 0x0AE unlocks the
table, 0x037 tells the rider's own client (mount_id plus Chocobo_Index), and the General
block of 0x00D tells everyone else (Flags6).  These tests pin all three, the chat command
that drives them, and the client's own Mount menu action.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import mounts, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def message_types(session) -> list[int]:
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def body_of(session, ptype: int) -> bytes | None:
    """The newest body of that type: an observer can have two 0x00D updates queued."""
    for message in reversed(session.queue):
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == ptype:
            return bytes(message[4:])
    return None


class MountSessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = support_service = make_service(Path(self.tmp.name))
        self.world = World(self.config, self.service, None)
        self.owner = self.service.register("owner", "password123").account
        self.main = self.make_session(self.service.create_character(
            self.owner["id"], {"name": "Mainchar", "race": 1}), 0x401)
        self.box = self.make_session(self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxone", "race": 1}})["character"], 0x402)
        self.other_account = self.service.register("other", "password123").account
        self.other = self.make_session(self.service.create_character(
            self.other_account["id"], {"name": "Otherchar", "race": 1}), 0x403)
        # Every session draws every other one, so a mount update has somewhere to go.
        for watcher in (self.main, self.box, self.other):
            for target in (self.main, self.box, self.other):
                if target is not watcher:
                    watcher.seen_players[int(target.char["char_id"])] = target
            watcher.entities_sent = True

    def make_session(self, character, targid):
        row = self.service.character(int(character["id"]))
        session = ZoneSession(
            self.world, ("127.0.0.1", 9000 + targid),
            self.service.character_record(row, "Fanxi"))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = int(session.char["zone"])
        session.targid = targid
        self.world.sessions[session.addr] = session
        return session

    # --- 0x0AE -----------------------------------------------------------------------------------

    def test_zone_in_unlocks_every_mount(self):
        self.main.load_zone_entities()
        self.main.after_zone_in()
        body = body_of(self.main, 0x0AE)
        self.assertIsNotNone(body, "the zone-in does not send the mount table")
        self.assertEqual(len(body), 8)
        self.assertEqual(body, mounts.bitfield())
        for mount in mounts.all_mounts():
            self.assertTrue(body[mount.id // 8] >> (mount.id % 8) & 1, mount.name)

    # --- 0x037 (the rider's own client) ----------------------------------------------------------

    def test_mount_writes_the_local_status_packet(self):
        self.main.set_mount(1)
        body = body_of(self.main, 0x037)
        self.assertIsNotNone(body)
        self.assertEqual(len(body), 0x74)
        self.assertEqual(body[0x6F], 1)
        flags0 = struct.unpack_from("<I", body, 0x24)[0]
        self.assertEqual((flags0 >> 13) & 7, 0)  # a raptor is not a chocobo seat
        # The riding animation is what makes the client draw the mount at all.
        self.assertEqual(body[0x2C], mounts.MOUNT_ANIMATION)
        # ... and the Mounted status effect is what the client's mount system keys on.
        self.assertIn(mounts.MOUNTED_EFFECT, list(body[0:32]))
        self.assertEqual(self.main.mount_id, 1)

    def test_chocobo_is_told_apart_by_chocobo_index(self):
        self.main.set_mount(mounts.CHOCOBO_ID)
        body = body_of(self.main, 0x037)
        self.assertEqual(body[0x6F], 0)
        self.assertEqual(body[0x2C], mounts.CHOCOBO_ANIMATION)
        flags0 = struct.unpack_from("<I", body, 0x24)[0]
        self.assertEqual((flags0 >> 13) & 7, 1)

    def test_dismount_clears_the_status_packet(self):
        self.main.set_mount(mounts.CHOCOBO_ID)
        self.main.queue.clear()
        self.assertTrue(self.main.dismount())
        body = body_of(self.main, 0x037)
        self.assertEqual(body[0x6F], 0)
        flags0 = struct.unpack_from("<I", body, 0x24)[0]
        self.assertEqual((flags0 >> 13) & 7, 0)
        self.assertEqual(self.main.mount_id, -1)

    def test_dismount_when_not_mounted_says_so(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.assertFalse(self.main.dismount())
        self.assertIn("not mounted", chats[0])

    # --- 0x00D (everyone else) -------------------------------------------------------------------

    def test_other_clients_read_the_mount_in_flags6(self):
        self.box.queue.clear()
        self.main.set_mount(23)
        body = body_of(self.box, 0x00D)
        self.assertIsNotNone(body, "the mount was not broadcast")
        self.assertEqual(len(body), 0x44)  # a General-only update ends at Flags6
        self.assertEqual(struct.unpack_from("<I", body, 0x40)[0], 23 << 4)
        self.assertEqual(body[0x1B], mounts.MOUNT_ANIMATION)  # the animation byte
        # The rider gets the entity update too (the same Flags6), so its own client hears
        # the animation from the packet that draws everyone else.
        own = body_of(self.main, 0x00D)
        self.assertIsNotNone(own)
        self.assertEqual(struct.unpack_from("<I", own, 0x40)[0], 23 << 4)

    def test_a_chocobo_ride_is_marked_in_flags1(self):
        self.box.queue.clear()
        self.main.set_mount(mounts.CHOCOBO_ID)
        body = body_of(self.box, 0x00D)
        flags1 = struct.unpack_from("<I", body, 0x1C)[0]
        self.assertEqual((flags1 >> 5) & 7, 1)

    def test_on_foot_sends_no_mount_id(self):
        self.box.queue.clear()
        self.main.set_mount(4)
        self.main.dismount()
        body = body_of(self.box, 0x00D)
        self.assertEqual(struct.unpack_from("<I", body, 0x40)[0], 0)

    # --- the commands ----------------------------------------------------------------------------

    def test_mount_by_name_and_by_id(self):
        self.main.mount_command(["Raptor"])
        self.assertEqual(self.main.mount_id, 1)
        self.main.mount_command(["5"])
        # A switch stands on foot for the model rebuild, then the tick calls the new mount.
        self.assertEqual(self.main.mount_id, -1)
        self.main.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, 5)
        self.main.mount_command(["Golden", "Bomb"])
        self.main.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, 27)

    def test_mount_list_names_every_mount(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main.mount_command([])
        joined = " ".join(chats)
        for mount in mounts.all_mounts():
            self.assertIn(mount.name, joined)
        self.assertIn("//mount off", chats[-1])

    def test_ambiguous_name_is_refused(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main.mount_command(["Red"])
        self.assertEqual(self.main.mount_id, -1)
        self.assertIn("Red Crab", chats[0])
        self.assertIn("Red Raptor", chats[0])

    def test_unknown_name_is_refused(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main.mount_command(["unicorn"])
        self.assertEqual(self.main.mount_id, -1)
        self.assertIn("no mount", chats[0])

    def test_mount_all_reaches_the_family_and_nobody_else(self):
        self.main.mount_command(["all", "Tiger"])
        # Each box's tick applies its own switch after the model-rebuild pause.
        self.main.tick(time.time() + 5.0)
        self.box.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, 2)
        self.assertEqual(self.box.mount_id, 2)
        self.assertEqual(self.other.mount_id, -1)

    def test_mount_party_draws_a_different_mount_for_each_box(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main.mount_command(["party"])
        self.assertGreaterEqual(self.main.mount_id, 0)
        self.assertGreaterEqual(self.box.mount_id, 0)
        self.assertNotEqual(self.main.mount_id, self.box.mount_id)
        self.assertEqual(self.other.mount_id, -1)
        self.assertTrue(any("Mount party:" in line for line in chats), chats)

    def test_mount_party_named_mount_reaches_the_whole_team(self):
        self.main.mount_command(["party", "Tiger"])
        self.assertEqual(self.main.mount_id, 2)
        self.assertEqual(self.box.mount_id, 2)

    def test_mount_party_random_keyword_and_all_alias(self):
        self.main.mount_command(["party", "random"])
        self.assertGreaterEqual(self.main.mount_id, 0)
        self.assertGreaterEqual(self.box.mount_id, 0)
        self.main.mount_command(["all", "Tiger"])
        # Each box's tick applies its own switch after the model-rebuild pause.
        self.main.tick(time.time() + 5.0)
        self.box.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, 2)
        self.assertEqual(self.box.mount_id, 2)

    def test_mount_all_off_dismounts_the_family(self):
        self.main.mount_command(["all", "Tiger"])
        self.main.mount_command(["all", "off"])
        self.assertEqual(self.main.mount_id, -1)
        self.assertEqual(self.box.mount_id, -1)

    def test_mount_off_dismounts_only_me(self):
        self.main.mount_command(["all", "Tiger"])
        self.main.mount_command(["off"])
        self.assertEqual(self.main.mount_id, -1)
        self.assertEqual(self.box.mount_id, 2)

    def test_subs_offline_are_counted(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main._family_sessions = lambda: [self.main]
        # Give the family a second, offline character so the count has something to say.
        self.service.create_sub_account(
            self.owner["id"], {"character": {"name": "Boxoff", "race": 1}})
        self.main.mount_command(["all", "Crab"])
        self.assertTrue(any("offline" in line for line in chats), chats)

    def test_last_mount_is_saved(self):
        self.main.set_mount(9)
        row = self.db.one("SELECT mount FROM characters WHERE id = ?",
                          (int(self.main.char["id"]),))
        self.assertEqual(int(row["mount"]), 9)

    def test_switching_mounts_stands_on_foot_first(self):
        self.main.set_mount(1)
        self.main.queue.clear()
        self.main.set_mount(5)
        # Still on foot, with the new call waiting for the client's model rebuild.
        self.assertEqual(self.main.mount_id, -1)
        self.assertIsNotNone(self.main.pending_mount)
        body = body_of(self.main, 0x037)
        self.assertEqual(body[0x6F], 0)
        self.assertEqual(body[0x2C], 0)
        self.main.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, 5)
        self.assertIsNone(self.main.pending_mount)
        body = body_of(self.main, 0x037)
        self.assertEqual(body[0x2C], mounts.MOUNT_ANIMATION)

    def test_dismount_cancels_a_pending_switch(self):
        self.main.set_mount(1)
        self.main.set_mount(5)
        self.assertEqual(self.main.mount_id, -1)  # already standing, waiting for the call
        self.assertFalse(self.main.dismount())     # nothing to dismount yet ...
        self.assertIsNone(self.main.pending_mount)  # ... and the pending call is dropped
        self.main.tick(time.time() + 5.0)
        self.assertEqual(self.main.mount_id, -1)

    # --- the client's own Mount menu --------------------------------------------------------------

    def action(self, action_id: int, mount_id: int = 0) -> bytes:
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 4, 0, 0x400, action_id)
        struct.pack_into("<I", packet, 12, mount_id)
        return bytes(packet)

    def test_the_clients_mount_action_mounts(self):
        self.main.action(self.action(packets.ACTION_MOUNT, 12))
        self.assertEqual(self.main.mount_id, 12)
        self.assertIsNotNone(body_of(self.main, 0x037))

    def test_the_clients_dismount_action(self):
        self.main.set_mount(12)
        self.main.action(self.action(packets.ACTION_DISMOUNT))
        self.assertEqual(self.main.mount_id, -1)

    def test_a_locked_mount_id_is_refused(self):
        chats = []
        self.main.say = lambda text: chats.append(text)
        self.main.action(self.action(packets.ACTION_MOUNT, mounts.count()))
        self.assertEqual(self.main.mount_id, -1)
        self.assertIn("not available", chats[0])

    # --- zone changes -----------------------------------------------------------------------------

    def test_a_zone_line_puts_the_character_back_on_foot(self):
        self.main.mount_command(["Raptor"])
        self.assertEqual(self.main.mount_id, 1)
        self.main.zone_loaded = True
        self.assertTrue(self.main.change_zone(100, list(self.world.zones.position(100))))
        self.assertEqual(self.main.mount_id, -1)


if __name__ == "__main__":
    unittest.main()
