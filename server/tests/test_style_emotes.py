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
    MSG_STYLE_LOCK_OFF,
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

    def test_a_weapon_swap_shows_the_new_weapons_while_locked(self):
        """Main and sub always follow the equipped gear, even with the lock on.

        The reported case: a two-handed main (and no shield) locked, then a one-handed
        main plus a shield.  The shield used to appear on its own because its locked
        model was zero, while the main kept the old two-hander.
        """
        self.session.char["head"] = 88
        self.session.char["main"] = 914
        self.session.char["sub"] = 0
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["main"] = 500
        self.session.char["sub"] = 600
        looks = struct.unpack_from("<9H", self.session.grap_list(), 4)
        self.assertEqual(looks[1], 0x1000 + 88)      # armour stays locked
        self.assertEqual(looks[6], 0x6000 + 500)     # new main hand
        self.assertEqual(looks[7], 0x7000 + 600)     # new shield

    def test_switching_back_to_a_two_hander_removes_the_shield(self):
        self.session.char["main"] = 500
        self.session.char["sub"] = 600
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["main"] = 914
        self.session.char["sub"] = 0
        looks = struct.unpack_from("<9H", self.session.grap_list(), 4)
        self.assertEqual(looks[6], 0x6000 + 914)
        self.assertEqual(looks[7], 0x7000)           # the shield model is gone

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

    def test_keepalive_locks_the_worn_appearance_when_the_server_has_none(self):
        # Mode 1 is the client's "continue": the client only sends it while its own lock
        # is on, and it sends it instead of mode 4 when /lockstyle on is typed in that
        # state.  The server has to honour it, or the command never takes effect again:
        # the client believes the lock is already on and never sends the enable.
        self.session.char["head"] = 88
        self.session.char["body"] = 99
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_KEEPALIVE))
        self.assertTrue(self.session.style_locked())
        self.assertEqual(self.session._style_models()[4], 88)
        self.assertEqual(self.session._style_models()[5], 99)
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["style_lock"]), 1)
        self.assertEqual(int(saved["style_head"]), 88)
        self.assertIn(0x051, message_types(self.session))
        self.assertIn(0x067, message_types(self.session))
        self.assertEqual(struct.unpack_from("<H", message_of(self.session, 0x051), 4 + 2)[0],
                         0x1000 + 88)
        self.assertEqual(
            struct.unpack_from("<H", message_of(self.session, 0x009), 10)[0], 267)

    def test_style_lock_survives_a_new_session(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        record = self.service.character_record(
            self.service.character(self.character["id"]), "Fanxi")
        fresh = ZoneSession(self.world, None, record)
        self.assertTrue(fresh.style_locked())
        self.assertEqual(struct.unpack_from("<H", fresh.grap_list(), 4 + 2)[0], 0x1000 + 88)

    def test_a_job_change_clears_the_lock(self):
        self.session.char["head"] = 88
        self.session.char["body"] = 99
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["jobs"] = {19: (99, 0), 20: (99, 0)}
        packet = bytearray(6)
        packet[4] = 19  # Dancer
        self.session.queue.clear()
        self.session.myroom_job(bytes(packet))
        self.assertFalse(self.session.style_locked())
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["style_lock"]), 0)
        # The stored look is cleared too, so it cannot come back later.
        for column in ("style_head", "style_body", "style_hands", "style_legs",
                       "style_feet", "style_main", "style_sub", "style_ranged"):
            self.assertEqual(int(saved[column]), 0, column)
        system = message_of(self.session, 0x009)
        self.assertEqual(struct.unpack_from("<H", system, 10)[0], MSG_STYLE_LOCK_OFF)

    def test_job_command_relocks_the_new_outfit(self):
        # //job clears the old locked look and then locks the outfit it just dressed, so
        # the command does not leave the previous job's appearance on the character (the
        # Moogles' menu keeps retail's lock-off behavior; see the test above).
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        # What the swap dresses.  There is no inventory in this test, so move the model
        # fields directly and check the locked ids follow them.
        self.session.char["head"] = 12
        self.session.char["body"] = 55
        self.session.char["jobs"] = {19: (99, 0), 20: (99, 0)}
        self.session.char["main_job"] = 20
        self.session.char["main_level"] = 99
        self.session.job_command(["job", "dnc"])
        self.assertEqual(int(self.session.char["main_job"]), 19)
        self.assertTrue(self.session.style_locked())
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["style_lock"]), 1)
        self.assertEqual(int(saved["style_head"]), 12)
        self.assertEqual(int(saved["style_body"]), 55)

    def test_a_keepalive_after_a_job_change_locks_the_new_outfit_not_the_old(self):
        # The reported bug was a Dancer wearing the Scholar's clothing after a job change.
        # The job change clears the models, so the continue that follows locks what the
        # Dancer is wearing now -- it cannot paint the Scholar's set back on.
        self.session.char["head"] = 88
        self.session.char["body"] = 99
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.char["jobs"] = {19: (99, 0), 20: (99, 0)}
        packet = bytearray(6)
        packet[4] = 19
        self.session.myroom_job(bytes(packet))
        # Dancer gear is worn now.
        self.session.char["head"] = 12
        self.session.char["body"] = 55
        self.session.queue.clear()
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_KEEPALIVE))
        self.assertTrue(self.session.style_locked())
        models = self.session._style_models()
        self.assertEqual(models[4], 12)
        self.assertEqual(models[5], 55)
        looks = struct.unpack_from("<9H", message_of(self.session, 0x051), 4)
        self.assertEqual(looks[1], 0x1000 + 12)
        self.assertEqual(looks[2], 0x2000 + 55)

    def test_disable_clears_the_stored_look(self):
        self.session.char["head"] = 88
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_ENABLE))
        self.session.handle(0x053, lockstyle_packet(LOCKSTYLE_DISABLE))
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["style_lock"]), 0)
        self.assertEqual(int(saved["style_head"]), 0)

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
