"""Samurai: the Hasso/Seigan stances and Meditate's ticking TP."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, modifiers as mod, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

def chats(session) -> list[str]:
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        out.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return out


GREAT_KATANA = 16960   # Uchigatana, skill 10 (two-handed)
DAGGER = 16400          # a one-handed weapon


class SamuraiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.fresh_login = False
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True
        self.session.char["main_job"] = 12
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 0
        self.session.char["sub_level"] = 0

    def equip(self, item_id: int, kind: int = 0) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, 0, ?)",
            (int(self.character["id"]), int(kind), int(item_id)))
        self.session.equipped[kind] = (0, 0, int(item_id))

    def ability(self, ability_id: int) -> None:
        p = bytearray(16)
        struct.pack_into("<IHH", p, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", p, 12, int(ability_id))
        self.session.job_ability(bytes(p), 0)
        self.session.queue.clear()

    def test_hasso_grants_str_accuracy_and_job_haste_with_a_two_handed_weapon(self):
        self.equip(GREAT_KATANA)
        base = self.session.combat_mods()
        self.ability(173)   # Hasso
        self.assertTrue(self.session.has_effect(effects.HASSO))
        state = self.session.effect(effects.HASSO)
        self.assertAlmostEqual(300.0, float(state["until"]) - time.time(), delta=3.0)
        mods = self.session.combat_mods()
        # 14 STR from the stance (99 // 7) plus 20 from the 20/20 Hasso Effect job
        # points, 10 Accuracy, and 10% job-ability haste.
        self.assertEqual(34, mods.get(mod.STR, 0) - base.get(mod.STR, 0))
        self.assertEqual(10, mods.get(mod.ACC, 0) - base.get(mod.ACC, 0))
        self.assertEqual(1000, mods.get(mod.HASTE_ABILITY, 0))

    def test_hasso_needs_a_two_handed_weapon(self):
        self.equip(DAGGER)
        base = self.session.combat_mods()
        self.ability(173)
        mods = self.session.combat_mods()
        self.assertEqual(0, mods.get(mod.HASTE_ABILITY, 0))
        self.assertEqual(base.get(mod.ACC, 0), mods.get(mod.ACC, 0))

    def test_seigan_overwrites_hasso(self):
        self.equip(GREAT_KATANA)
        self.ability(173)
        self.ability(174)   # Seigan
        self.assertFalse(self.session.has_effect(effects.HASSO))
        self.assertTrue(self.session.has_effect(effects.SEIGAN))
        self.assertEqual(0, self.session.combat_mods().get(mod.HASTE_ABILITY, 0))

    def mob(self, level: int = 75):
        from fanxi_server.game.entities import ZoneEntity
        mob = ZoneEntity(kind="mob", id=0x7FFF0001, targid=0x300, zone=self.session.zone,
                         name="Testmob", level=level)
        mob.alive = True
        mob.hp_max = 5000
        mob.hp = 5000
        return mob

    def test_third_eye_anticipates_the_next_swing(self):
        self.equip(GREAT_KATANA)
        self.ability(62)   # Third Eye
        self.assertEqual(1, int(self.session.third_eye["charges"]))
        mob = self.mob()
        missed, damage, _critical, _defended = self.world.mob_attack(mob, self.session)
        self.assertTrue(missed)
        self.assertEqual(0, damage)
        self.assertIsNone(self.session.third_eye)

    def test_seigan_gives_third_eye_three_charges(self):
        self.equip(GREAT_KATANA)
        self.ability(174)   # Seigan
        self.ability(62)    # Third Eye
        self.assertEqual(3, int(self.session.third_eye["charges"]))

    def test_blade_bash_stuns_the_target(self):
        mob = self.mob()
        mob.x, mob.y, mob.z = self.session.pos[0], self.session.pos[1], self.session.pos[2]
        self.session.engaged_id = int(mob.id)
        self.session.engaged_targid = int(mob.targid)
        self.world.entity_by_id = lambda zone, entity_id: mob
        self.ability(168)   # Blade Bash
        self.assertIn(effects.STUN, mob.effect_state)
        self.assertIn(effects.STUN, mob.status_effects)

    def test_shikikoyo_refuses_to_share_with_itself(self):
        self.session.char["tp"] = 3000
        self.session._shikikoyo(0, {"name": "Shikikoyo", "range": 20}, time.time())
        self.assertEqual(3000, int(self.session.char["tp"]))
        self.assertIn("cannot share TP with yourself", " ".join(chats(self.session)))

    def test_konzen_ittai_makes_one_weapon_skill_chain_by_itself(self):
        mob = self.mob()
        now = time.time()
        self.session._seed_konzen_chain(mob, {"id": 32}, now)   # Fast Blade: Scission
        self.assertIsNotNone(mob.skillchain)
        chain = self.session._advance_skillchain(mob, {"id": 32}, 800, now)
        self.assertIsNotNone(chain)
        self.assertGreater(mob.skillchain.tier, 0)

    def test_sengikori_adds_a_quarter_to_the_chain(self):
        now = time.time()
        plain_mob = self.mob()
        self.session._advance_skillchain(plain_mob, {"id": 32}, 800, now)
        plain = self.session._advance_skillchain(plain_mob, {"id": 33}, 800, now + 5)
        self.assertIsNotNone(plain)
        mob = self.mob()
        self.session._sengikori_until = now + 60.0
        self.session._advance_skillchain(mob, {"id": 32}, 800, now)
        boosted = self.session._advance_skillchain(mob, {"id": 33}, 800, now + 5)
        self.assertEqual(int(plain["damage"] * 1.25), boosted["damage"])
        self.assertEqual(0.0, self.session._sengikori_until)

    def test_zanshin_swings_again_after_a_miss(self):
        mob = self.mob()
        mob.x, mob.y, mob.z = self.session.pos[0], self.session.pos[1], self.session.pos[2]
        self.session.engaged_id = int(mob.id)
        self.session.engaged_targid = int(mob.targid)
        self.session.next_attack_at = 0.0
        self.world.entity_by_id = lambda zone, entity_id: mob
        self.session.char["main_job"] = 12
        self.session.char["main_level"] = 99
        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(True, 0, False)) as attack, \
                mock.patch.object(self.world.rng, "random", return_value=0.0):
            self.session.tick(time.time())
        # The miss and Zanshin's extra swing.
        self.assertEqual(2, attack.call_count)

    def test_seigan_turns_an_anticipation_into_a_counter(self):
        self.equip(GREAT_KATANA)
        self.ability(174)   # Seigan
        self.ability(62)    # Third Eye
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 123, False)), \
                mock.patch.object(self.world.rng, "random", return_value=0.0):
            missed, damage, _critical, _defended = self.world.mob_attack(mob, self.session)
        self.assertTrue(missed)
        self.assertEqual(0, damage)
        self.assertEqual(5000 - 123, mob.hp)
        self.assertIn("counter", " ".join(chats(self.session)))

    def test_warding_circle_and_yaegasumi_use_the_retail_timers(self):
        self.assertEqual(180.0, effects.ABILITY_EFFECTS[64].duration)
        self.assertEqual(45.0, effects.ABILITY_EFFECTS[334].duration)

    def test_meikyo_grants_3000_tp(self):
        self.session.char["tp"] = 0
        self.ability(27)   # Meikyo Shisui
        self.assertEqual(3000, int(self.session.char["tp"]))
        self.assertGreater(float(self.session._meikyo_until), time.time())

    def test_sekkanoki_caps_the_next_weapon_skill_at_1000(self):
        self.ability(230)  # Sekkanoki
        now = time.time()
        self.assertEqual(1000, self.session._weaponskill_effective_tp(2500, {}, now))

    def test_hagakure_adds_1000_tp_bonus(self):
        self.ability(288)  # Hagakure
        now = time.time()
        self.assertGreater(float(self.session._hagakure_until), now)
        self.assertEqual(1000, int(self.session._hagakure_tp_bonus))
        self.assertEqual(2000, self.session._weaponskill_effective_tp(1000, {}, now))

    def test_meditate_ticks_two_hundred_tp_to_one_thousand(self):
        self.session.char["tp"] = 0
        self.ability(63)    # Meditate
        now = time.time()
        seen = []
        for step in range(1, 6):
            self.session.tick(now + 3.0 * step)
            seen.append(int(self.session.char["tp"]))
        # 200 a tick plus the +100 job-point row (5 x 20), capped at 1000.
        self.assertEqual([300, 600, 900, 1000, 1000], seen)
        self.assertIsNone(self.session.meditate)

    def test_sub_job_meditate_is_slower_and_capped_at_six_hundred(self):
        self.session.char["main_job"] = 1
        self.session.char["tp"] = 0
        self.ability(63)
        now = time.time()
        seen = []
        for step in range(1, 6):
            self.session.tick(now + 3.0 * step)
            seen.append(int(self.session.char["tp"]))
        self.assertEqual([120, 240, 360, 480, 600], seen)
        self.assertIsNone(self.session.meditate)


if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
