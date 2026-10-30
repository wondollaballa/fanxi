"""Skillchains and Magic Bursts: the window, the chain hit and the burst bonus."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import effects, modifiers as mod, packets, skillchain
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def action_messages(session) -> list[int]:
    """The 0x028 message ids the session queued (the chain/burst lines)."""
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x028:
            continue
        # The message is the last 10 bits of the result block; decode the family
        # loosely: the chain message sits in 287..303, the burst at 252.
        out.append(bytes(message))
    return out


class SkillchainTest(unittest.TestCase):
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
        self.session.char["main_job"] = 1
        self.session.char["main_level"] = 99

    def mob(self):
        mob = ZoneEntity(kind="mob", id=0x7FFF0001, targid=0x300, zone=self.session.zone,
                         name="Testmob", level=75)
        mob.alive = True
        mob.hp_max = 5000
        mob.hp = 5000
        return mob

    def test_fast_blade_opens_and_burning_blade_forms_liquefaction(self):
        now = time.time()
        state, formed = skillchain.advance(None, (4, 0, 0), now)   # Fast Blade: Scission
        self.assertEqual(int(skillchain.SC.NONE), int(formed))
        self.assertTrue(state.is_opening(now))
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5)  # Burning Blade
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertEqual(1, state.count)
        self.assertEqual(1, int(skillchain.TIER[formed]))
        # A level-1 link keeps the full 11 s window (Fanxi rule).
        self.assertAlmostEqual(now + 5 + skillchain.OPEN_SECONDS, state.until, delta=0.1)

    def test_the_level_one_loop_keeps_the_full_window(self):
        """Savage Blade > Hot Shot > Savage Blade ... stays level 1 and never times out.

        This is the loop COR players expect: 4 = Fragmentation/Scission on Savage Blade,
        3 = Liquefaction/Transfixion on Hot Shot.  A 10 s cadence breaks it under the
        retail one-second shrink (the third link only has 9 s), so a level-1 link has to
        keep the full 11 s window.
        """
        now = time.time()
        state = None
        opened = 0
        for index in range(8):
            props = (12, 4, 0) if index % 2 == 0 else (3, 1, 0)
            state, formed = skillchain.advance(state, props, now + index * 10.0)
            if index == 0:
                self.assertEqual(int(skillchain.SC.NONE), int(formed))
                continue
            opened += 1
            expected = (skillchain.SC.LIQUEFACTION if index % 2
                        else skillchain.SC.SCISSION)
            self.assertEqual(int(expected), int(formed), index)
            self.assertEqual(1, int(skillchain.TIER[formed]))
            self.assertAlmostEqual(now + index * 10.0 + skillchain.OPEN_SECONDS,
                                   state.until, delta=0.1)
        self.assertEqual(7, opened)
        self.assertEqual(skillchain.MAX_CHAIN_COUNT, state.count)

    def test_a_level_two_link_still_shrinks_the_window(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)      # Scission
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5)  # Liquefaction
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertAlmostEqual(now + 5 + skillchain.OPEN_SECONDS,
                               state.until, delta=0.1)
        # Impaction closes the level-1 Liquefaction into Fusion (tier 2); that wider
        # chain still loses one second per link as in retail.
        state, formed = skillchain.advance(state, (8, 0, 0), now + 15)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))
        self.assertEqual(2, int(skillchain.TIER[formed]))
        self.assertAlmostEqual(now + 15 + skillchain.OPEN_SECONDS - 1.0,
                               state.until, delta=0.1)
        state, formed = skillchain.advance(state, (12, 0, 0), now + 25)
        self.assertEqual(int(skillchain.SC.LIGHT), int(formed))
        self.assertAlmostEqual(now + 25 + skillchain.OPEN_SECONDS - 2.0,
                               state.until, delta=0.1)

    def test_a_skill_inside_the_delay_does_not_chain(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        _state, formed = skillchain.advance(state, (3, 0, 0), now + 1.0)
        self.assertEqual(int(skillchain.SC.NONE), int(formed))

    def test_a_close_just_after_the_exact_window_still_lands(self):
        """The half-second tick grace keeps an 11.3 s close from losing the chain."""
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0),
                                           now + 11.0 + 0.3)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))

    def test_the_second_link_accepts_a_close_at_the_exact_ten_second_mark(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5.0)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        # The first link's state is 11 s long and starts at now+5; a Fusion close
        # arriving at now+15 (the ten-second mark) must still chain.
        state, formed = skillchain.advance(state, (8, 0, 0), now + 5.0 + 10.0)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))

    def test_a_close_beyond_the_grace_opens_a_new_window(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0),
                                           now + 11.0 + 0.6)
        self.assertEqual(int(skillchain.SC.NONE), int(formed))
        self.assertEqual(0, state.tier)

    def test_diamond_aspis_keeps_the_full_window_at_every_step(self):
        now = time.time()
        state, _formed = skillchain.advance(None, (4, 0, 0), now)
        state, formed = skillchain.advance(state, (3, 0, 0), now + 5,
                                           diamond=True)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), int(formed))
        self.assertAlmostEqual(now + 5 + skillchain.DIAMOND_ASPIS_SECONDS,
                               state.until, delta=0.1)
        state, formed = skillchain.advance(state, (8, 0, 0), now + 10,
                                           diamond=True)
        self.assertEqual(int(skillchain.SC.FUSION), int(formed))
        self.assertAlmostEqual(now + 10 + skillchain.DIAMOND_ASPIS_SECONDS,
                               state.until, delta=0.1)

    def test_diamond_aspis_detection_reads_the_sub_slot(self):
        self.assertFalse(self.session.has_diamond_aspis())
        self.session.equipped[1] = (0, 0, skillchain.DIAMOND_ASPIS_ITEM_ID)
        self.assertTrue(self.session.has_diamond_aspis())
        self.session.equipped[1] = (0, 0, 12345)
        self.assertFalse(self.session.has_diamond_aspis())

    def test_the_chain_hit_uses_the_closing_damage_and_the_multiplier(self):
        self.assertAlmostEqual(0.50, skillchain.chain_multiplier(1, 1))
        self.assertAlmostEqual(0.60, skillchain.chain_multiplier(2, 1))
        self.assertEqual(500, skillchain.skillchain_damage(1000, 1, 1))
        self.assertEqual(600, skillchain.skillchain_damage(1000, 2, 1))
        self.assertEqual(750, skillchain.skillchain_damage(1000, 2, 2))

    def test_the_chain_hit_stops_at_99999(self):
        # A capped 99,999 closing WS times a tier-3 link would print six digits; the
        # chain hit shares the weapon skill's ceiling.
        self.assertEqual(99999, skillchain.DAMAGE_CAP)
        self.assertEqual(99999, skillchain.skillchain_damage(99999, 3, 3))
        self.assertEqual(99999, skillchain.skillchain_damage(10 ** 6, 4, 5))

    def test_sengikori_cannot_lift_a_chain_past_the_cap(self):
        now = time.time()
        mob = self.mob()
        mob.hp_max = 500000
        mob.hp = 500000
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 32}, 800, now))
        self.session._sengikori_until = now + 60.0
        # The chain formula returns its own 99,999 ceiling; Sengikori's +25% is applied
        # afterwards and must be clipped again before the HP is spent.
        with mock.patch.object(skillchain, "skillchain_damage", return_value=99999):
            chain = self.session._advance_skillchain(mob, {"id": 33}, 99999, now + 5)
        self.assertIsNotNone(chain)
        self.assertEqual(99999, chain["damage"])
        self.assertEqual(500000 - 99999, mob.hp)

    def test_a_landed_pair_forms_the_chain_and_damages_the_mob(self):
        now = time.time()
        mob = self.mob()
        # Fast Blade (32) opens, Burning Blade (33) closes five seconds later.  The
        # closing skill returns the additional-effect block its action carries: the
        # client plays the skillchain from that block, not from a second action.
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 32}, 800, now))
        self.assertEqual(0, mob.skillchain.tier)
        chain = self.session._advance_skillchain(mob, {"id": 33}, 800, now + 5)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        # Tier 1, link 1: 800 x 0.50 = 400 off the monster.
        self.assertEqual(5000 - 400, mob.hp)
        self.assertEqual(400, chain["damage"])
        self.assertEqual(int(skillchain.proc_kind(mob.skillchain.sc)), chain["proc"])
        self.assertEqual(skillchain.proc_message(mob.skillchain.sc), chain["message"])

    def test_savage_blade_and_hot_shot_keep_chaining_at_ten_seconds(self):
        """The real handler keeps the level-1 loop alive past the old window.

        Savage Blade (42) opens; Hot Shot (208) ten seconds later forms Liquefaction.
        That link must leave the full 11 s window, so the next Savage Blade at +20 s
        forms Scission instead of opening a new chain.
        """
        now = time.time()
        mob = self.mob()
        self.assertIsNone(self.session._advance_skillchain(mob, {"id": 42}, 800, now))
        chain = self.session._advance_skillchain(mob, {"id": 208}, 800, now + 10)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        self.assertAlmostEqual(now + 10 + skillchain.OPEN_SECONDS,
                               mob.skillchain.until, delta=0.1)
        chain = self.session._advance_skillchain(mob, {"id": 42}, 800, now + 20)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.SCISSION), mob.skillchain.sc)
        self.assertEqual(2, mob.skillchain.count)
        self.assertAlmostEqual(now + 20 + skillchain.OPEN_SECONDS,
                               mob.skillchain.until, delta=0.1)
        chain = self.session._advance_skillchain(mob, {"id": 208}, 800, now + 30)
        self.assertIsNotNone(chain)
        self.assertEqual(int(skillchain.SC.LIQUEFACTION), mob.skillchain.sc)
        self.assertEqual(3, mob.skillchain.count)

    def test_a_matching_spell_inside_the_window_is_a_magic_burst(self):
        now = time.time()
        mob = self.mob()
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now, until=now + 8.0)
        spell = self.service.spell_by_name("Fire")
        spec = effects.for_spell("Fire")
        burst = self.session._cast_numbers(spell, spec, mob, healing=False)
        self.assertEqual(1, burst["magic_burst"])
        mob.skillchain = None
        plain = self.session._cast_numbers(spell, spec, mob, healing=False)
        self.assertEqual(0, plain["magic_burst"])
        self.assertGreater(burst["amount"], plain["amount"])
        self.assertAlmostEqual(1.85, skillchain.magic_burst_multiplier(1), places=3)

    def test_red_mage_mag_burst_bonus_trait_scales_the_burst(self):
        """The RDM Mag. Burst Bonus trait (274) belongs in the burst multiplier.

        The trait is 5 at 85 and 7 at 95.  It was in the trait table but no damage path
        read it, so a Red Mage's bursts were only the base multiplier.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        now = time.time()
        mob = self.mob()
        mob.level = 1
        spell = self.service.spell_by_name("Fire")
        spec = effects.for_spell("Fire")
        plain = self.session._cast_numbers(spell, spec, mob, healing=False)["amount"]
        self.assertGreater(plain, 0)
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now, until=now + 8.0)
        burst = self.session._cast_numbers(spell, spec, mob, healing=False)["amount"]
        # Base 1.85 x (1 + 0.07).  A level-1 target caps the resist roll at 1.0 in
        # both calls, so the extra +100 Magic Accuracy does not change the ratio.
        self.assertAlmostEqual(
            burst, int(plain * skillchain.magic_burst_multiplier(1) * 1.07), delta=1)

    def test_a_spell_outside_the_window_is_not_a_burst(self):
        mob = self.mob()
        now = time.time()
        mob.skillchain = skillchain.SkillchainState(
            props=(3, 0, 0), tier=1, sc=int(skillchain.SC.LIQUEFACTION), count=1,
            started=now - 20, until=now - 10)
        spell = self.service.spell_by_name("Fire")
        numbers = self.session._cast_numbers(spell, effects.for_spell("Fire"), mob,
                                             healing=False)
        self.assertEqual(0, numbers["magic_burst"])


if __name__ == "__main__":
    unittest.main()
