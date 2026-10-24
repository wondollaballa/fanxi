"""Skillchain data, transition table, state machine and Magic Burst rules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.game import skillchain, weapon_skills  # noqa: E402
from fanxi_server.game.skillchain import SC  # noqa: E402


class SkillchainDataTest(unittest.TestCase):
    def test_kasha_has_fusion_and_compression(self):
        data = weapon_skills.for_id(152)
        self.assertIsNotNone(data)
        self.assertEqual(data.sc, (SC.FUSION, SC.COMPRESSION, SC.NONE))
        self.assertEqual(data.primary_sc, SC.FUSION)

    def test_vorpal_blade_keeps_both_properties(self):
        # The reference has Scission primary and Impaction secondary; the summary in
        # the design draft listed only Scission.
        self.assertEqual(weapon_skills.for_id(40).sc, (SC.SCISSION, SC.IMPACTION, SC.NONE))

    def test_prime_skill_has_its_bg_wiki_properties(self):
        self.assertEqual(weapon_skills.for_id(142).sc, (SC.INDURATION, SC.REVERBERATION,
                                                          SC.FUSION))

    def test_the_whole_table_has_properties(self):
        table = weapon_skills._table()
        self.assertGreater(len(table), 200)
        missing = [row.name for row in table.values() if not any(row.sc)]
        # A handful of skills legitimately have no resonance (non-elemental), but the
        # data file should still carry a row for every skill.
        self.assertGreaterEqual(len(table) - len(missing), 180)


class TransitionTest(unittest.TestCase):
    def form(self, resonance, skill):
        return int(skillchain.form_skillchain(resonance, skill))

    def test_level_one_to_two_pairs_follow_the_reference_direction(self):
        # FormSkillchain looks up (closing skill property, existing resonance), so the
        # argument order here is (resonance, closing skill).
        self.assertEqual(self.form((SC.LIQUEFACTION,), (SC.IMPACTION,)), SC.FUSION)
        self.assertEqual(self.form((SC.IMPACTION,), (SC.LIQUEFACTION,)), SC.LIQUEFACTION)
        self.assertEqual(self.form((SC.TRANSFIXION,), (SC.SCISSION,)), SC.DISTORTION)
        self.assertEqual(self.form((SC.SCISSION,), (SC.TRANSFIXION,)), SC.NONE)
        self.assertEqual(self.form((SC.DETONATION,), (SC.COMPRESSION,)), SC.GRAVITATION)
        self.assertEqual(self.form((SC.REVERBERATION,), (SC.INDURATION,)),
                         SC.INDURATION)
        self.assertEqual(self.form((SC.INDURATION,), (SC.REVERBERATION,)),
                         SC.FRAGMENTATION)

    def test_level_two_pairs_form_light_and_darkness(self):
        self.assertEqual(self.form((SC.FUSION,), (SC.FRAGMENTATION,)), SC.LIGHT)
        self.assertEqual(self.form((SC.GRAVITATION,), (SC.DISTORTION,)), SC.DARKNESS)
        self.assertEqual(self.form((SC.FRAGMENTATION,), (SC.FUSION,)), SC.LIGHT)
        self.assertEqual(self.form((SC.DISTORTION,), (SC.GRAVITATION,)), SC.DARKNESS)

    def test_level_three_pairs_form_the_level_four_chains(self):
        self.assertEqual(self.form((SC.LIGHT,), (SC.LIGHT,)), SC.LIGHT_II)
        self.assertEqual(self.form((SC.DARKNESS,), (SC.DARKNESS,)), SC.DARKNESS_II)

    def test_property_order_is_the_opening_order(self):
        # Gekko opens Distortion/Reverberation; Kasha closes Fusion/Compression.
        self.assertEqual(self.form((SC.DISTORTION, SC.REVERBERATION, SC.NONE),
                                   (SC.FUSION, SC.COMPRESSION, SC.NONE)),
                         SC.FUSION)

    def test_a_pair_with_no_transition_returns_none(self):
        self.assertEqual(self.form((SC.FUSION,), (SC.FUSION,)), SC.NONE)
        self.assertEqual(self.form((SC.NONE,), (SC.FUSION,)), SC.NONE)


class StateTest(unittest.TestCase):
    def test_the_first_weapon_skill_only_opens_the_state(self):
        state, formed = skillchain.advance(None, (SC.FUSION, SC.COMPRESSION, SC.NONE), 0.0)
        self.assertEqual(formed, SC.NONE)
        self.assertIsNotNone(state)
        self.assertEqual(state.tier, 0)
        self.assertEqual(state.props, (SC.FUSION, SC.COMPRESSION, SC.NONE))
        self.assertEqual(state.until, 10.0)

    def test_a_second_skill_inside_three_seconds_does_not_chain(self):
        state, _ = skillchain.advance(None, (SC.FUSION,), 0.0)
        state, formed = skillchain.advance(state, (SC.DISTORTION,), 2.0)
        self.assertEqual(formed, SC.NONE)
        self.assertEqual(state.tier, 0)
        self.assertEqual(state.props, (SC.DISTORTION, SC.NONE, SC.NONE))
        self.assertEqual(state.started, 2.0)
        self.assertEqual(state.until, 12.0)

    def test_a_link_forms_and_counters(self):
        state, _ = skillchain.advance(None, (SC.DISTORTION,), 0.0)
        state, formed = skillchain.advance(state, (SC.FUSION,), 3.5)
        self.assertEqual(formed, SC.FUSION)
        self.assertEqual((state.tier, state.sc, state.count), (2, SC.FUSION, 1))
        self.assertEqual(state.started, 3.5)
        self.assertEqual(state.until, 12.5)   # 10 s duration, minus 1 on the link

    def test_a_three_step_chain_counts_up_and_shortens_the_window(self):
        state, _ = skillchain.advance(None, (SC.DISTORTION,), 0.0)
        state, _ = skillchain.advance(state, (SC.FUSION,), 3.5)
        state, formed = skillchain.advance(state, (SC.FRAGMENTATION,), 6.6)
        self.assertEqual(formed, SC.LIGHT)
        self.assertEqual((state.tier, state.count), (3, 2))
        self.assertEqual(state.until, 14.6)   # 9 s remaining, minus 1

    def test_a_weapon_skill_without_properties_leaves_the_state_alone(self):
        state, _ = skillchain.advance(None, (SC.FUSION,), 0.0)
        same, formed = skillchain.advance(state, (SC.NONE, SC.NONE, SC.NONE), 4.0)
        self.assertEqual(formed, SC.NONE)
        self.assertIs(same, state)

    def test_an_expired_state_is_replaced(self):
        state, _ = skillchain.advance(None, (SC.FUSION,), 0.0)
        state, formed = skillchain.advance(state, (SC.DISTORTION,), 10.1)
        self.assertEqual(formed, SC.NONE)
        self.assertEqual(state.started, 10.1)
        self.assertEqual(state.until, 20.1)


class DamageTest(unittest.TestCase):
    def test_chain_multipliers(self):
        self.assertEqual(skillchain.chain_multiplier(1, 1), 0.50)
        self.assertEqual(skillchain.chain_multiplier(2, 1), 0.60)
        self.assertEqual(skillchain.chain_multiplier(3, 1), 1.00)
        self.assertEqual(skillchain.chain_multiplier(4, 1), 1.50)
        self.assertEqual(skillchain.chain_multiplier(2, 5), 1.50)

    def test_damage_uses_the_closing_ws_and_floors_each_step(self):
        self.assertEqual(skillchain.skillchain_damage(1000, 2, 1), 600)
        self.assertEqual(skillchain.skillchain_damage(1000, 3, 1), 1000)
        self.assertEqual(
            skillchain.skillchain_damage(
                1000, 2, 1, skillchain_bonus=10, magic_damage=50,
                skillchain_damage=1000),
            781)

    def test_resistance_rank_and_cap(self):
        self.assertEqual(skillchain.skillchain_damage(1000, 2, 1, resistance_rank=-3), 900)
        self.assertEqual(skillchain.skillchain_damage(99999, 4, 6), 99999)

    def test_proc_ids_and_messages(self):
        self.assertEqual(skillchain.proc_kind(SC.FUSION), 6)
        self.assertEqual(skillchain.proc_message(SC.FUSION), 293)
        self.assertEqual(skillchain.proc_kind(SC.LIGHT_II), 1)
        self.assertEqual(skillchain.proc_message(SC.LIGHT_II), 288)
        self.assertEqual(skillchain.proc_message(SC.NONE), 0)


class MagicBurstTest(unittest.TestCase):
    def state(self, now: float = 3.5):
        state, _ = skillchain.advance(None, (SC.DISTORTION,), 0.0)
        state, _ = skillchain.advance(state, (SC.FUSION,), now)
        return state

    def test_only_the_matching_elements_burst(self):
        state = self.state()
        self.assertEqual(skillchain.magic_burst_tier(
            state, skillchain.ELEMENT_FIRE, 4.0), 1)
        self.assertEqual(skillchain.magic_burst_tier(
            state, skillchain.ELEMENT_LIGHT, 4.0), 1)
        self.assertEqual(skillchain.magic_burst_tier(
            state, skillchain.ELEMENT_WATER, 4.0), 0)
        self.assertEqual(skillchain.magic_burst_tier(
            state, skillchain.ELEMENT_FIRE, 13.0), 0)

    def test_a_level_three_chain_matches_four_elements(self):
        state, _ = skillchain.advance(None, (SC.DISTORTION,), 0.0)
        state, _ = skillchain.advance(state, (SC.FUSION,), 3.5)
        state, _ = skillchain.advance(state, (SC.FRAGMENTATION,), 6.6)
        for element in (skillchain.ELEMENT_LIGHT, skillchain.ELEMENT_FIRE,
                        skillchain.ELEMENT_WIND, skillchain.ELEMENT_THUNDER):
            self.assertEqual(skillchain.magic_burst_tier(state, element, 7.0), 2)

    def test_burst_multiplier_is_not_the_mythical_1_35(self):
        self.assertAlmostEqual(skillchain.magic_burst_multiplier(1), 1.85)
        self.assertAlmostEqual(skillchain.magic_burst_multiplier(5), 2.25)
        # rank -3 is table index 1 (1.15): 1.25 + 1.15 + 0.10.
        self.assertAlmostEqual(skillchain.magic_burst_multiplier(1, resistance_rank=-3),
                               2.50)

    def test_gear_bonus_caps_at_forty_and_uncapped_is_not_capped(self):
        self.assertAlmostEqual(skillchain.magic_burst_bonus(100, 30), 1.70)
        self.assertAlmostEqual(skillchain.magic_burst_bonus(1000, 0), 1.40)
        self.assertAlmostEqual(skillchain.magic_burst_bonus(0, 30), 1.30)

    def test_magic_burst_grants_one_hundred_magic_accuracy(self):
        self.assertEqual(skillchain.magic_burst_macc_bonus(1), 100)
        self.assertEqual(skillchain.magic_burst_macc_bonus(0), 0)


if __name__ == "__main__":
    unittest.main()
