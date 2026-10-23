"""Job trait lookup: level gates, ranks, support jobs and modifier merging."""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import modifiers as mod, traits  # noqa: E402


class TraitTest(unittest.TestCase):
    def test_auto_refresh_levels(self):
        # The game's table: Paladin 35; Summoner 25 (I) and 90 (II).  Red Mage has
        # the Refresh spell, not the trait, so it must stay out of this list.
        self.assertEqual(traits.modifiers_for(7, 34).get(mod.REFRESH), None)
        self.assertEqual(traits.modifiers_for(7, 35).get(mod.REFRESH), 1)
        self.assertEqual(traits.modifiers_for(15, 24).get(mod.REFRESH), None)
        self.assertEqual(traits.modifiers_for(15, 25).get(mod.REFRESH), 1)
        self.assertEqual(traits.modifiers_for(15, 90).get(mod.REFRESH), 2)
        self.assertEqual(traits.modifiers_for(5, 99).get(mod.REFRESH), None)

    def test_auto_regen_levels(self):
        # White Mage 25/76; Rune Fencer 35/65/95.
        self.assertEqual(traits.modifiers_for(3, 24).get(mod.REGEN), None)
        self.assertEqual(traits.modifiers_for(3, 25).get(mod.REGEN), 1)
        self.assertEqual(traits.modifiers_for(3, 76).get(mod.REGEN), 2)
        self.assertEqual(traits.modifiers_for(22, 35).get(mod.REGEN), 1)
        self.assertEqual(traits.modifiers_for(22, 65).get(mod.REGEN), 2)
        self.assertEqual(traits.modifiers_for(22, 95).get(mod.REGEN), 3)

    def test_support_job_uses_its_own_level(self):
        # Warrior 60 / White Mage 24 gets nothing; at 25 the support job's Auto Regen
        # becomes active.  The support level is already capped at half the main level
        # before it reaches this module.
        self.assertIsNone(traits.modifiers_for(1, 60, 3, 24).get(mod.REGEN))
        self.assertEqual(traits.modifiers_for(1, 60, 3, 25).get(mod.REGEN), 1)

    def test_same_trait_does_not_stack_across_jobs(self):
        # Warrior 30 and Dragoon 30 both have Attack Bonus I: it is applied once.
        solo = traits.modifiers_for(1, 30)
        both = traits.modifiers_for(1, 30, 14, 30)
        self.assertEqual(both.get(mod.ATT), solo.get(mod.ATT))
        # A higher support rank replaces the main job's rank instead of adding to it.
        higher = traits.modifiers_for(1, 30, 14, 99)
        self.assertEqual(higher.get(mod.ATT), 22)

    def test_only_the_highest_rank_is_applied(self):
        # Dragoon's Accuracy Bonus is 10 at 30, 22 at 60 and 35 at 76.
        self.assertEqual(traits.modifiers_for(14, 30).get(mod.ACC), 10)
        self.assertEqual(traits.modifiers_for(14, 60).get(mod.ACC), 22)
        self.assertEqual(traits.modifiers_for(14, 76).get(mod.ACC), 35)
        # The ranged half of the same trait is included, not dropped.
        self.assertEqual(traits.modifiers_for(14, 76).get(26), 35)

    def test_blue_mage_and_merit_traits_are_not_granted_for_free(self):
        merit_only = {71, 72, 73, 74, 75, 76, 77, 78, 79, 81, 82, 83, 85, 86,
                      87, 88, 90, 91, 92, 93, 94, 95, 96, 97, 119, 120}
        self.assertFalse(any(row[2] == 16 for row in traits.ROWS))
        self.assertFalse(any(row[0] in merit_only for row in traits.ROWS))
        self.assertFalse(any(row[3] <= 0 or row[2] <= 0 for row in traits.ROWS))

    def test_max_hp_and_mp_boost_values(self):
        self.assertEqual(traits.modifiers_for(1, 30).get(mod.MAX_HP_BOOST), 30)
        self.assertEqual(traits.modifiers_for(2, 55).get(mod.MAX_HP_BOOST), 240)
        self.assertEqual(traits.modifiers_for(15, 50).get(mod.MAX_MP_BOOST), 40)
        self.assertEqual(traits.modifiers_for(20, 88).get(mod.MAX_MP_BOOST), 20)

    def test_ids_for_matches_active_traits(self):
        active = traits.active(7, 35)
        self.assertEqual(traits.ids_for(7, 35), [trait.id for trait in active])
        self.assertIn(traits.AUTO_REFRESH, traits.ids_for(7, 35))
        self.assertNotIn(traits.AUTO_REGEN, traits.ids_for(7, 35))
        self.assertIn(traits.AUTO_REGEN, traits.ids_for(3, 25))

    def test_describe_names_the_tick_bonus(self):
        auto = [trait for trait in traits.active(7, 35)
                if trait.id == traits.AUTO_REFRESH]
        self.assertEqual(len(auto), 1)
        self.assertIn("Auto Refresh", auto[0].describe())
        self.assertIn("Refresh+1", auto[0].describe())


if __name__ == "__main__":
    unittest.main()
