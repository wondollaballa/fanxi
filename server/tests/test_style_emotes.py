"""Style lock (0x053) and emotes (0x05D): the two client requests that used to be dropped."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import (
    LOCKSTYLE_DISABLE,
    LOCKSTYLE_ENABLE,
    LOCKSTYLE_KEEPALIVE,
    LOCKSTYLE_QUERY,
    LOCKSTYLE_SET,
    ZoneSession,
)


def message_types(session):
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def message_of(session, kind):
    return next(message for message in session.queue
                if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == kind)


def lockstyle_packet(mode: int, items=(), count: int | None = None, flags: int = 0) -> bytes:
    """A C2S 0x053 in the client's 0x88-byte layout."""
    packet = bytearray(0x88)
    struct.pack_into("<H", packet, 0, 0x53 | (0x22 << 9))
    packet[4] = len(items) if count is None else count
    packet[5] = mode & 0xFF
    packet[6] = flags & 0xFF
    for index, (kind, item_no) in enumerate(items[:16]):
        offset = 8 + index * 8
        packet[offset + 1] = kind
        struct.pack_into("<H", packet, offset + 4, item_no)
    return bytes(packet)


def motion_packet(emote: int, mode: int = 0, param: int = 0,
                  target_id: int = 0, target_index: int = 0) -> bytes:
    packet = bytearray(16)
    struct.pack_into("<H", packet, 0, 0x5D | (4 << 9))
    struct.pack_into("<IHBBH", packet, 4, target_id, target_index, emote, mode, param)
    return bytes(packet)


class StyleAndEmoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()

    # --- style lock ----------------------------------------------------------------------------
    def test_enable_snapshots_the_worn_appearance(self):
        self.session.char["head"] = 88
        self.session.char["main"] = 914
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        kinds = message_types(self.session)
        self.assertIn(0x051, kinds)
        self.assertIn(0x067, kinds)
        # The 0x009 message is the client's "Style lock mode enabled." line.
        system = message_of(self.session, 0x009)
        self.assertEqual(struct.unpack_from("<H", system, 10)[0], 267)
        grap = message_of(self.session, 0x051)
        looks = struct.unpack_from("<9H", grap, 4)
        self.assertEqual(looks[1], 0x1000 + 88)
        self.assertEqual(looks[6], 0x6000 + 914)
        self.assertEqual(self.session.char["style_lock"], 1)
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["style_lock"]), 1)
        self.assertEqual(int(saved["style_head"]), 88)

    def test_a_gear_swap_does_not_change_a_locked_look(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.queue.clear()
        # A gear swap changes the real models.  The grap list must keep the locked head.
        self.session.char["head"] = 12
        self.session.char["body"] = 55
        looks = struct.unpack_from("<9H", self.session.grap_list(), 4)
        self.assertEqual(looks[1], 0x1000 + 88)
        # The zone-in bundle and the entity update also read looks().
        login = self.session.login_packet()
        self.assertEqual(struct.unpack_from("<9H", login, 0x3C + 8)[1], 0x1000 + 88)
        update = self.session.char_update()
        self.assertEqual(struct.unpack_from("<9H", update, 0x44 + 4)[1], 0x1000 + 88)

    def test_set_uses_the_item_models(self):
        # Hachiya Hatsuburi +4 has grap model 4184 (Ninja Hatsuburi's look) and is a head item.
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_SET, [(4, 23907)]))
        looks = struct.unpack_from("<9H", message_of(self.session, 0x051), 4)
        self.assertEqual(looks[1], 0x1000 + 4184)
        # Slots the set did not name keep what was worn.
        self.assertEqual(looks[2], 0x2000 + int(self.session.char["body"]))
        self.assertEqual(int(self.service.character(self.character["id"])["style_head"]), 4184)

    def test_red_mage_reforged_armour_renders_its_original_look(self):
        # Migration 94 gives Atrophy +4 (AF) the Warlock's models.  With model 0 the
        # server skipped the slot and the equipped armour was invisible on the grap list.
        items = [(4, 23899), (5, 23944), (6, 23989), (7, 24034), (8, 24079)]
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_SET, items, count=len(items)))
        looks = struct.unpack_from("<9H", message_of(self.session, 0x051), 4)
        self.assertEqual(looks[1], 0x1000 + 4168)   # Atrophy Chapeau +4
        self.assertEqual(looks[2], 0x2000 + 8264)   # Atrophy Tabard +4
        self.assertEqual(looks[3], 0x3000 + 12360)  # Atrophy Gloves +4
        self.assertEqual(looks[4], 0x4000 + 16456)  # Atrophy Tights +4
        self.assertEqual(looks[5], 0x5000 + 20552)  # Atrophy Boots +4

    def test_set_keeps_slots_it_does_not_name(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.queue.clear()
        # A set that names only the body keeps the locked head.
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_SET, [(5, 23952)]))
        looks = struct.unpack_from("<9H", message_of(self.session, 0x051), 4)
        self.assertEqual(looks[1], 0x1000 + 88)
        self.assertEqual(looks[2], 0x2000 + 8280)  # Hachiya Chainmail +4 grap model 8280

    def test_disable_returns_the_real_look(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.queue.clear()
        self.session.char["head"] = 42
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_DISABLE))
        self.assertEqual(int(self.service.character(self.character["id"])["style_lock"]), 0)
        self.assertEqual(struct.unpack_from("<H", message_of(self.session, 0x051), 4 + 2)[0],
                         0x1000 + 42)
        system = message_of(self.session, 0x009)
        self.assertEqual(struct.unpack_from("<H", system, 10)[0], 268)

    def test_query_reports_the_state(self):
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_QUERY))
        self.assertEqual(struct.unpack_from("<H", message_of(self.session, 0x009), 10)[0], 270)
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.queue.clear()
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_QUERY))
        self.assertEqual(struct.unpack_from("<H", message_of(self.session, 0x009), 10)[0], 269)

    def test_keepalive_keeps_the_stored_style(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["head"] = 12
        self.session.queue.clear()
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_KEEPALIVE))
        looks = struct.unpack_from("<9H", self.session.grap_list(), 4)
        self.assertEqual(looks[1], 0x1000 + 88)

    def test_keepalive_repaints_when_the_server_had_no_lock(self):
        # The client only sends KeepAlive when its own style lock is on; if the server
        # was reset, take the request and repaint the character.
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_KEEPALIVE))
        self.assertIn(0x051, message_types(self.session))
        self.assertIn(0x067, message_types(self.session))
        self.assertTrue(self.session.style_locked())
        self.assertEqual(struct.unpack_from("<H", message_of(self.session, 0x051), 4 + 2)[0],
                         0x1000 + 88)

    def test_style_lock_survives_a_new_session(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        record = self.service.character_record(
            self.service.character(self.character["id"]), "Fanxi")
        fresh = ZoneSession(self.world, None, record)
        self.assertTrue(fresh.style_locked())
        self.assertEqual(struct.unpack_from("<H", fresh.grap_list(), 4 + 2)[0], 0x1000 + 88)

    def test_a_job_change_clears_the_lock(self):
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["jobs"] = {1: (99, 0), 13: (99, 0)}
        packet = bytearray(6)
        packet[4] = 13
        self.session.myroom_job(bytes(packet))
        self.assertFalse(self.session.style_locked())
        self.assertEqual(int(self.service.character(self.character["id"])["style_lock"]), 0)

    # --- emotes --------------------------------------------------------------------------------
    def test_wave_is_echoed(self):
        self.session.handle(0x05D, motion_packet(8, target_id=0x0106B039, target_index=57))
        motion = message_of(self.session, 0x05A)
        cas, tar, casidx, taridx, mes, param, _unknown, mode, _padding = struct.unpack_from(
            "<IIHHHHHBB", motion, 4)
        self.assertEqual(cas, self.session.char["char_id"])
        self.assertEqual(tar, 0x0106B039)
        self.assertEqual(casidx, 0x400)
        self.assertEqual(taridx, 57)
        self.assertEqual(mes, 8)
        self.assertEqual(mode, 0)

    def test_all_emote_modes_and_job_param(self):
        self.session.handle(0x05D, motion_packet(8, mode=1))
        motion = message_of(self.session, 0x05A)
        self.assertEqual(struct.unpack_from("<H", motion, 4 + 12)[0], 8)
        self.assertEqual(motion[4 + 18], 1)
        self.session.queue.clear()
        self.session.handle(0x05D, motion_packet(74, param=31))
        motion = message_of(self.session, 0x05A)
        self.assertEqual(struct.unpack_from("<H", motion, 4 + 12)[0], 74)  # job emote WAR
        self.assertEqual(struct.unpack_from("<H", motion, 4 + 14)[0], 0)

    def test_unknown_emote_is_dropped(self):
        self.session.handle(0x05D, motion_packet(200))
        self.assertEqual(self.session.queue, [])

    def test_other_players_in_the_zone_see_the_emote(self):
        other = ZoneSession(self.world, ("127.0.0.1", 4321),
                            self.service.character_record(
                                self.service.character(self.character["id"]), "Fanxi"))
        other.set_key(bytes(20))
        other.logged_in = True
        other.zone = 246
        other.queue.clear()
        self.world.sessions[("127.0.0.1", 4321)] = other
        self.session.handle(0x05D, motion_packet(8))
        self.assertIn(0x05A, message_types(self.session))
        self.assertIn(0x05A, message_types(other))


if __name__ == "__main__":
    unittest.main()
