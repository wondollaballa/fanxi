"""Monster TP moves: the bar, the family list and the 0x028 action.

The data comes from the LSB import (migration 0148) and the behaviour is
``World._tick_mob``.  The tests use a hand-written skill so the animation, AoE
radius and damage are independent of whichever family a starter-zone rabbit
happens to use.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import combat, mobskills, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

ZONE = 100  # West Ronfaure: the seeded starter zone has live mobs


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.bit = 0

    def read(self, count: int) -> int:
        value = 0
        for index in range(count):
            value |= ((self.data[self.bit >> 3] >> (self.bit & 7)) & 1) << index
            self.bit += 1
        return value


def action_packets(session) -> list[dict]:
    """Decode every 0x028 in the session's queue into targets and results."""
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x028:
            continue
        reader = BitReader(message[5:])
        action = {
            "actor": reader.read(32), "target_count": reader.read(6),
            "res_sum": reader.read(4), "category": reader.read(4),
            "action": reader.read(32), "recast": reader.read(32), "targets": [],
        }
        for _ in range(action["target_count"]):
            target = {"id": reader.read(32), "results": []}
            for _ in range(reader.read(4)):
                result = {
                    "resolution": reader.read(3), "kind": reader.read(2),
                    "animation": reader.read(12), "info": reader.read(5),
                    "distortion": reader.read(2), "knockback": reader.read(3),
                    "value": reader.read(17), "message": reader.read(10),
                    "modifier": reader.read(31),
                }
                if reader.read(1):
                    result["add_effect"] = reader.read(6)
                    reader.read(4 + 17 + 10)
                if reader.read(1):
                    reader.read(6 + 4 + 14 + 10)
                target["results"].append(result)
            action["targets"].append(target)
        out.append(action)
    return out


class MobSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("mobtester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Tester", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = self.make_session(self.character, "Tester", 0, 1234)
        self.session.char.update({
            "main_job": 1, "main_level": 99,
            "hp": 5000, "hp_current": 5000,
            "mp": 500, "mp_current": 500,
            "tp": 0,
        })
        self.mob = next(entity for entity in self.session.entities
                        if entity.kind == "mob" and entity.alive)

    def make_session(self, character, name: str, targid: int, port: int) -> ZoneSession:
        session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(character["id"]), name))
        session.set_key(bytes(20))
        session.logged_in = True
        session.targid = targid
        session.zone = ZONE
        session.pos = list(self.world.zones.position(ZONE))
        session.load_zone_entities()
        session.after_zone_in()
        session.zone_loaded = True
        session.queue.clear()
        self.world.sessions[("127.0.0.1", port)] = session
        return session

    def add_skill(self, skill_id: int, name: str, *, aoe: int = 0, radius: float = 0.0,
                  animation: int = 321, valid_targets: int = 4,
                  prepare_time: int = 0, distance: float = 20.0) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO mob_skills "
            "(id,name,animation,aoe,aoe_radius,distance,animation_time,prepare_time,"
            "valid_targets,flag,param,knockback,primary_sc,secondary_sc,tertiary_sc) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(skill_id), name, int(animation), int(aoe), float(radius),
             float(distance), 1000, int(prepare_time), int(valid_targets),
             0, 0, 0, 0, 0, 0))
        self.db.execute(
            "INSERT OR REPLACE INTO mob_skill_lists "
            "(skill_list_id,mob_skill_id,skill_list_name) VALUES (?,?,?)",
            (int(skill_id), int(skill_id), "Test"))

    def engage(self) -> None:
        self.mob.skill_list_id = 9999
        self.mob.tp = 3000
        self.mob.tp_threshold = 1000
        self.mob.engaged_char_id = int(self.session.char["char_id"])
        self.mob.claim_char_id = int(self.session.char["char_id"])
        self.mob.x = float(self.session.pos[0])
        self.mob.y = float(self.session.pos[1])
        self.mob.z = float(self.session.pos[2])
        self.mob.next_attack_at = 0.0
        self.mob.pending_skill = None
        self.session.sent_targids.add(self.mob.targid)
        self.session.queue.clear()

    def test_a_full_tp_monster_uses_its_tp_move(self):
        self.add_skill(9999, "test_smash", animation=321)
        self.engage()
        hit = combat.Hit(150, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 1.0)
        actions = action_packets(self.session)
        self.assertTrue(actions)
        # Skill ids >= 256 are the client's MobSkillFinish category (11).
        self.assertEqual(actions[0]["category"], packets.ACTION_CATEGORY_MOB_SKILL_FINISH)
        self.assertEqual(actions[0]["action"], 9999)
        self.assertEqual(actions[0]["target_count"], 1)
        self.assertEqual(actions[0]["targets"][0]["id"], int(self.session.char["char_id"]))
        result = actions[0]["targets"][0]["results"][0]
        self.assertEqual(result["animation"], 321)
        self.assertGreater(result["value"], 0)
        self.assertEqual(self.mob.tp, 0)
        self.assertLess(int(self.session.char["hp_current"]), 5000)
        # The TP move replaced the auto-attack: no BasicAttack action in the queue.
        self.assertNotIn(packets.ACTION_CATEGORY_BASIC_ATTACK,
                         [action["category"] for action in actions])

    def test_a_prepared_tp_move_sends_start_then_finish(self):
        self.add_skill(9997, "test_windup", animation=323, prepare_time=1000)
        self.engage()
        self.mob.skill_list_id = 9997
        hit = combat.Hit(140, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 1.0)
        starts = action_packets(self.session)
        self.assertTrue(starts)
        self.assertEqual(starts[0]["category"], packets.ACTION_CATEGORY_SKILL_START)
        self.assertEqual(starts[0]["action"], packets.ACTION_SKILL_USE)
        self.assertEqual(starts[0]["targets"][0]["results"][0]["value"], 9997)
        self.assertIsNotNone(self.mob.pending_skill)
        self.assertEqual(self.mob.tp, 3000)
        self.session.queue.clear()
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 2.0)
        finishes = action_packets(self.session)
        self.assertTrue(finishes)
        self.assertEqual(finishes[0]["category"],
                         packets.ACTION_CATEGORY_MOB_SKILL_FINISH)
        self.assertEqual(finishes[0]["action"], 9997)
        self.assertEqual(finishes[0]["targets"][0]["results"][0]["animation"], 323)
        self.assertIsNone(self.mob.pending_skill)
        self.assertEqual(self.mob.tp, 0)

    def test_a_long_range_tp_move_fires_before_the_mob_closes(self):
        self.add_skill(9996, "test_sonic_boom", animation=324, distance=20.0)
        self.engage()
        self.mob.skill_list_id = 9996
        self.mob.x = float(self.session.pos[0]) + 10.0
        hit = combat.Hit(110, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 1.0)
        actions = action_packets(self.session)
        self.assertTrue(actions)
        self.assertEqual(actions[0]["action"], 9996)
        self.assertEqual(actions[0]["category"], packets.ACTION_CATEGORY_MOB_SKILL_FINISH)
        self.assertLess(int(self.session.char["hp_current"]), 5000)

    def test_an_aoe_tp_move_hits_and_animates_for_every_player(self):
        self.add_skill(9998, "test_whirl", aoe=1, radius=10.0, animation=322)
        account = self.service.register("second", "password123").account
        other_row = self.service.create_character(
            account["id"], {"name": "Second", "race": 1})
        other = self.make_session(other_row, "Second", 0x401, 1235)
        other.char.update({"main_level": 99, "hp": 5000, "hp_current": 5000})
        other.pos = list(self.session.pos)
        other.sent_targids.add(self.mob.targid)
        other.queue.clear()
        self.mob.skill_list_id = 9998
        self.mob.tp = 3000
        self.mob.tp_threshold = 1000
        self.mob.engaged_char_id = int(self.session.char["char_id"])
        self.mob.claim_char_id = int(self.session.char["char_id"])
        self.mob.x = float(self.session.pos[0])
        self.mob.y = float(self.session.pos[1])
        self.mob.z = float(self.session.pos[2])
        self.mob.next_attack_at = 0.0
        self.session.sent_targids.add(self.mob.targid)
        self.session.queue.clear()
        other.queue.clear()
        hit = combat.Hit(120, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 1.0)
        for session in (self.session, other):
            actions = action_packets(session)
            self.assertTrue(actions, "no TP move for %s" % session.char["name"])
            self.assertEqual(actions[0]["category"],
                             packets.ACTION_CATEGORY_MOB_SKILL_FINISH)
            self.assertEqual(actions[0]["target_count"], 2)
            for target in actions[0]["targets"]:
                self.assertGreater(target["results"][0]["value"], 0)
                self.assertEqual(target["results"][0]["animation"], 322)
            self.assertLess(int(session.char["hp_current"]), 5000)

    def test_a_landed_player_hit_feeds_the_monsters_tp(self):
        self.mob.tp = 0
        hit = combat.Hit(100, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.player_attack(self.session, self.mob)
        self.assertGreater(self.mob.tp, 0)
        self.assertLessEqual(self.mob.tp, mobskills.TP_MAX)

    def test_a_monsters_own_hit_feeds_its_tp(self):
        self.mob.tp = 0
        hit = combat.Hit(30, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.mob_attack(self.mob, self.session)
        self.assertGreater(self.mob.tp, 0)
        self.assertLessEqual(self.mob.tp, mobskills.TP_MAX)

    def test_a_monster_without_a_skill_list_still_auto_attacks(self):
        self.mob.skill_list_id = 0
        self.mob.tp = 3000
        self.mob.engaged_char_id = int(self.session.char["char_id"])
        self.mob.x = float(self.session.pos[0])
        self.mob.y = float(self.session.pos[1])
        self.mob.z = float(self.session.pos[2])
        self.mob.next_attack_at = 0.0
        self.session.sent_targids.add(self.mob.targid)
        self.session.queue.clear()
        hit = combat.Hit(50, False, False)
        with mock.patch("fanxi_server.game.combat.melee", return_value=hit):
            self.world.advance(time.time() + 1.0)
        actions = action_packets(self.session)
        self.assertTrue(actions)
        self.assertEqual(actions[0]["category"], packets.ACTION_CATEGORY_BASIC_ATTACK)
        self.assertNotIn(packets.ACTION_CATEGORY_MOB_SKILL_FINISH,
                         [action["category"] for action in actions])

    def test_the_imported_lists_reach_a_starter_zone_monster(self):
        spawn = next(row for row in self.service.monster_spawns_for_zone(ZONE)
                     if int(row.get("skill_list_id") or 0) > 0)
        moves = self.service.mob_skills(int(spawn["skill_list_id"]))
        self.assertTrue(moves)
        self.assertTrue(all(move["name"] for move in moves))
        self.assertTrue(all(int(move["animation"]) >= 0 for move in moves))
        self.assertEqual(len(self.world.mob_skill_list(int(spawn["skill_list_id"]))),
                         len(moves))

    def test_tp_thresholds_follow_the_retail_bands(self):
        self.assertFalse(mobskills.should_use(999, 1000, 100))
        self.assertTrue(mobskills.should_use(3000, 3000, 100))
        self.assertTrue(mobskills.should_use(1000, 3000, 24))
        self.assertTrue(mobskills.should_use(2000, 2000, 100))
        self.assertFalse(mobskills.should_use(1999, 2000, 100))


if __name__ == "__main__":
    unittest.main()
