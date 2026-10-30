"""The Check menu: C2S 0x00DD and the client's own check line.

The client sends ``0x00DD`` with Kind 0 for ``/check``.  For a monster it prints a
BtlMess line itself; the server's only job is to choose message 170..178 and pass the
monster's level in Data and ``64 + difficulty`` in Data2.  Before this handler existed
the packet was logged once and ignored, which is the "Check does nothing" report.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import check
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession, sub


def check_packet(unique_no: int, targid: int, kind: int = 0) -> bytes:
    """A C2S 0x00DD body, as the client lays it out (XiPackets 0x00DD)."""
    return bytes(sub(0x00DD, struct.pack("<IIB3x", int(unique_no), int(targid), int(kind))))


def battle_messages(session) -> list[dict]:
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x029:
            continue
        sender, target, data, data2, starg, ttarg, message_id, kind = struct.unpack_from(
            "<IIIIHHHB", message, 4)
        out.append({"sender": sender, "target": target, "data": data, "data2": data2,
                    "sender_targid": starg, "target_targid": ttarg,
                    "message": message_id, "kind": kind})
    return out


def chats(session) -> list[str]:
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


class DifficultyTest(unittest.TestCase):
    """The base-EXP curve behind the difficulty word."""

    def test_base_exp_reads_the_retail_table(self):
        self.assertEqual(check.base_exp(1, 1), 200)
        self.assertEqual(check.base_exp(10, 10), 200)
        self.assertEqual(check.base_exp(75, 55), 60)
        self.assertEqual(check.base_exp(99, 110), 1300)
        self.assertEqual(check.base_exp(50, 1), 0)

    def test_difficulty_names(self):
        self.assertIs(check.difficulty(1, 1), check.Difficulty.EVEN_MATCH)
        self.assertIs(check.difficulty(1, 2), check.Difficulty.TOUGH)
        self.assertIs(check.difficulty(1, 8), check.Difficulty.INCREDIBLY_TOUGH)
        self.assertIs(check.difficulty(10, 10), check.Difficulty.EVEN_MATCH)
        self.assertIs(check.difficulty(75, 55), check.Difficulty.EASY_PREY)
        self.assertIs(check.difficulty(50, 1), check.Difficulty.TOO_WEAK)

    def test_level_56_plus_tail_is_incredibly_easy_prey(self):
        # 99 vs 75 is a 48 EXP row: too little for Easy Prey, but not zero.
        self.assertGreater(check.base_exp(99, 75), 0)
        self.assertLess(check.base_exp(99, 75), 60)
        self.assertIs(check.difficulty(99, 75), check.Difficulty.INCREDIBLY_EASY_PREY)

    def test_check_message_follows_defense_and_evasion(self):
        even = (100, 100, 100, 100)
        self.assertEqual(check.message_id(*even), check.CHECK_MESSAGE)
        # Defense is one message either way, Evasion three.
        self.assertEqual(check.message_id(100, 100, 101, 100), check.CHECK_MESSAGE - 1)
        self.assertEqual(check.message_id(100, 100, 80, 100), check.CHECK_MESSAGE + 1)
        self.assertEqual(check.message_id(100, 100, 100, 131), check.CHECK_MESSAGE - 3)
        self.assertEqual(check.message_id(100, 100, 100, 90), check.CHECK_MESSAGE + 3)
        # The two are independent, so both high is 170 and both low is 178.
        self.assertEqual(check.message_id(100, 100, 150, 150), 170)
        self.assertEqual(check.message_id(100, 100, 50, 50), 178)
        self.assertEqual(check.message_id(100, 100, 50, 200), 172)
        self.assertEqual(check.message_id(100, 100, 150, 50), 176)


class CheckTest(unittest.TestCase):
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
        self.session.targid = 0x400
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.mob = next(entity for entity in self.session.entities
                        if entity.kind == "mob")

    def check_target(self, unique_no: int, targid: int, kind: int = 0) -> None:
        self.session.queue.clear()
        self.session.handle(0x00DD, check_packet(unique_no, targid, kind))

    def test_mob_check_queues_the_clients_check_line(self):
        self.mob.level = 10
        self.session.char["main_level"] = 10
        self.check_target(self.mob.id, self.mob.targid)
        messages = battle_messages(self.session)
        self.assertEqual(len(messages), 1)
        line = messages[0]
        self.assertEqual(line["sender"], int(self.session.char["char_id"]))
        self.assertEqual(line["target"], int(self.mob.id))
        self.assertEqual(line["sender_targid"], 0x400)
        self.assertEqual(line["target_targid"], int(self.mob.targid))
        self.assertEqual(line["data"], 10)
        self.assertEqual(line["data2"], check.CHECK_DATA_BASE + check.Difficulty.EVEN_MATCH)
        self.assertGreaterEqual(line["message"], 170)
        self.assertLessEqual(line["message"], 178)
        self.assertEqual(line["kind"], 0)

    def test_too_weak_mob_gets_the_too_weak_code(self):
        self.mob.level = 1
        self.session.char["main_level"] = 60
        self.check_target(self.mob.id, self.mob.targid)
        line = battle_messages(self.session)[0]
        self.assertEqual(line["data"], 1)
        self.assertEqual(line["data2"], 64)

    def test_check_is_dispatched_even_with_sync_zero(self):
        """A menu request may arrive with sync 0; it still has to answer."""
        self.mob.level = 10
        self.session.char["main_level"] = 10
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x00DD)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x00DD, struct.pack(
            "<IIB3x", int(self.mob.id), int(self.mob.targid), 0))))
        self.assertEqual(len(battle_messages(self.session)), 1)

    def test_stale_server_id_is_not_answered(self):
        # The targid still names this monster, but the client's own id does not; the
        # menu target is stale and must not show another monster's level.
        self.check_target(int(self.mob.id) ^ 0x1000, self.mob.targid)
        self.assertEqual(battle_messages(self.session), [])

    def test_checkparam_kind_is_not_a_mob_check(self):
        self.check_target(self.mob.id, self.mob.targid, kind=2)
        self.assertEqual(battle_messages(self.session), [])

    def test_unknown_target_is_silent(self):
        self.check_target(0x12345678, 0x3FF)
        self.assertEqual(battle_messages(self.session), [])
        self.assertEqual(chats(self.session), [])

    def test_player_check_notifies_the_checked_player(self):
        # The checker's own client calls itself 0x400, but every other client knows it
        # by the targid the server assigned (0x401 here).  The examine notice must name
        # the checker with the latter.
        self.session.targid = 0x401
        other_account = self.service.register("other", "password123").account
        other_char = self.service.create_character(other_account["id"],
                                                   {"name": "Other", "race": 1})
        other = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(other_char["id"]), "Other"))
        other.set_key(bytes(20))
        other.logged_in = True
        other.targid = 0x402
        other.zone = self.session.zone
        self.world.sessions[("127.0.0.1", 1235)] = other
        other.queue.clear()

        self.check_target(int(other.char["char_id"]), 0x402)
        self.assertIn("You examine Other.", chats(self.session))
        notices = [message for message in other.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x009]
        self.assertEqual(len(notices), 1)
        body = bytes(notices[0][4:])
        self.assertEqual(struct.unpack_from("<I", body, 0)[0],
                         int(self.session.char["char_id"]))
        self.assertEqual(struct.unpack_from("<H", body, 4)[0], 0x401)
        self.assertEqual(struct.unpack_from("<H", body, 6)[0], 89)
        self.assertEqual(body[8], 0x10)
        self.assertIn(b"string2 Fanxi", body)


if __name__ == "__main__":
    unittest.main()
