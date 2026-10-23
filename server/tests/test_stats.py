"""Gear stats: the reforged data migration and the HP/MP percentage modifiers."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

from fanxi_server.db import Database  # noqa: E402
from fanxi_server.game import base_stats, modifiers as mod, stats  # noqa: E402
import import_reforged_item_data as reforged  # noqa: E402


class ReforgedItemDataTest(unittest.TestCase):
    """Migration 92 carries the client's own stat lines for the reforged sets."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Database(Path(cls.tmp.name) / "fanxi.db", ROOT)
        cls.db.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def mods(self, item_id: int) -> dict[int, int]:
        return {int(row["mod_id"]): int(row["value"])
                for row in self.db.all(
                    "SELECT mod_id, value FROM item_mods WHERE item_id = ?", (item_id,))}

    def test_cuirass_has_the_tooltip_stats(self):
        mods = self.mods(23947)  # Ignominy Cuirass +4
        self.assertEqual(mods[mod.DEF], 171)
        self.assertEqual(mods[mod.HP], 174)
        self.assertEqual(mods[mod.STR], 46)
        self.assertEqual(mods[mod.ACC], 60)
        self.assertEqual(mods[mod.HASTE_GEAR], 300)  # 3%, in hundredths

    def test_empyrean_armour_carries_damage_taken(self):
        mods = self.mods(23494)  # Heathen's Cuirass +3
        self.assertEqual(mods[mod.DMG], -1300)  # Damage taken -13%
        self.assertEqual(mods[mod.HP], 93)

    def test_black_mage_piece_has_its_magic_stats(self):
        """The stats the magic formula reads are in the data, not only the tooltip."""
        mods = self.mods(23423)  # Wicce Petasos +3
        self.assertEqual(mods[mod.MATT], 51)
        self.assertEqual(mods[mod.MAGIC_DAMAGE], 31)
        self.assertEqual(mods[mod.MACC], 61)
        self.assertEqual(mods[mod.MEVA], 136)
        self.assertEqual(mods[mod.MDEF], 10)
        row = self.db.one(
            "SELECT amount FROM item_skill_bonus WHERE item_id = ? AND skill_id = ?",
            (23423, 36))  # Elemental Magic
        self.assertIsNotNone(row)
        self.assertEqual(int(row["amount"]), 35)

    def test_weapon_skill_bonus_is_on_the_client_skill_id(self):
        row = self.db.one(
            "SELECT amount FROM item_skill_bonus WHERE item_id = ? AND skill_id = ?",
            (21842, 7))  # Final Sickle (Reforged), Scythe
        self.assertIsNotNone(row)
        self.assertEqual(int(row["amount"]), 269)

    def test_percent_hp_modifier_is_kept(self):
        self.assertEqual(self.mods(26366)[mod.HPP], 10)  # Plat. Mog. Belt: HP+10%

    def test_placeholder_race_rows_are_gone(self):
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM item_mods WHERE item_id = ? AND mod_id = ?", (23913, 276)))

    def test_unowned_reforged_sets_are_filled_too(self):
        # One piece from a job the character does not currently wear, so the import
        # is not just the equipped set.
        mods = self.mods(23895)  # Pummeler's Mask +4
        self.assertGreaterEqual(mods[mod.DEF], 100)

    def test_red_mage_reforged_sets_have_the_original_looks(self):
        """Migration 94: a zero model left the equipped RDM JSE invisible on the grap list."""
        expected = {
            23899: 4168, 23944: 8264, 23989: 12360, 24034: 16456, 24079: 20552,  # Atrophy
            23922: 4169, 23967: 8265, 24012: 12361, 24057: 16457, 24102: 20553,  # Vitiation
            23424: 4382, 23491: 8478, 23558: 12574, 23625: 16670, 23692: 20766,  # Lethargy
        }
        for item_id, model in expected.items():
            row = self.db.one("SELECT model FROM items WHERE item_id = ?", (item_id,))
            self.assertIsNotNone(row, item_id)
            self.assertEqual(int(row["model"]), model, item_id)


class PercentMaximumTest(unittest.TestCase):
    """HP/MP percentages multiply the maximum after the flat bonus."""

    def character(self) -> dict:
        return {"race": 1, "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0}

    def test_hp_percent(self):
        base = base_stats.base_hp(1, 1, 99, 0, 0)
        sheet = stats.build_character(self.character(), {mod.HP: 100, mod.HPP: 10}, {})
        self.assertEqual(sheet.max_hp, (base + 100) * 110 // 100)

    def test_mp_percent(self):
        character = {"race": 1, "main_job": 4, "main_level": 99, "sub_job": 0, "sub_level": 0}
        base = base_stats.base_mp(1, 4, 99, 0, 0)
        sheet = stats.build_character(character, {mod.MP: 50, mod.MPP: 20}, {})
        self.assertEqual(sheet.max_mp, (base + 50) * 120 // 100)


class DescriptionParserTest(unittest.TestCase):
    """The parser reads the client's stat line, not a hand-maintained table."""

    def test_tooltip_line(self):
        text = ('[Hands] All Races DEF:127 HP+59 STR+31 DEX+39 VIT+48 INT+27 MND+41 '
                'CHR+29 Accuracy+43 Attack+87 Magic Accuracy+43 "Magic Atk. Bonus"+65 '
                'Evasion+67 Magic Evasion+86 "Magic Def. Bonus"+4 Dark magic skill +19 '
                'Haste+4% "Drain" and "Aspir" absorption +16 LV 99 DRK')
        mods, skills, leftover = reforged.parse_description(text)
        table = dict(mods)
        self.assertEqual(table[mod.DEF], 127)
        self.assertEqual(table[mod.STR], 31)
        self.assertEqual(table[mod.ATT], 87)
        self.assertEqual(table[mod.MACC], 43)
        self.assertEqual(table[mod.MATT], 65)
        self.assertEqual(table[mod.HASTE_GEAR], 400)
        self.assertEqual(table[mod.DRAIN_ASPIR], 16)
        self.assertEqual(skills, [(37, 19)])  # Dark Magic, client skill 37
        self.assertFalse(reforged.looks_like_stat(leftover))

    def test_pet_and_set_clauses_are_not_player_stats(self):
        text = ('[Body] All Races DEF:150 HP+90 Accuracy+50 Haste+3% '
                'Pet: Accuracy+60 Attack+40 Set: Attack occ. varies with pet HP LV 99 BST')
        mods, _skills, _leftover = reforged.parse_description(text)
        table = dict(mods)
        self.assertEqual(table[mod.ACC], 50)
        self.assertNotIn(mod.ATT, table)  # the pet's Attack is not the player's


if __name__ == "__main__":
    unittest.main()
