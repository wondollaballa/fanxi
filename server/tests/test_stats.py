"""Gear stats: the reforged data migration and the HP/MP percentage modifiers."""
from __future__ import annotations

import random
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

from fanxi_server.db import Database  # noqa: E402
from fanxi_server.config import Config  # noqa: E402
from fanxi_server.game import (  # noqa: E402
    base_stats, effects, modifiers as mod, prime_weapons, stats)
from fanxi_server.game.entities import (  # noqa: E402
    LOCUS_DEFENSE_SCALE, LOCUS_EVASION_SCALE, ZoneEntity, mob_from_row,
    mob_hp_for_level, scaled_level_stat)
from fanxi_server.game.world import World  # noqa: E402
from fanxi_server.service import FanxiService  # noqa: E402
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

    def test_foenaria_carries_its_skill_stats_and_triple_attack(self):
        """Migration 161: without these, Origin runs at 424 scythe skill and low WSC."""
        weapon = self.db.one(
            "SELECT ilvl_skill FROM item_weapon WHERE item_id = ?", (21837,))
        self.assertEqual(int(weapon["ilvl_skill"]), 277)
        mods = self.mods(21837)
        self.assertEqual(mods[mod.STR], 35)
        self.assertEqual(mods[mod.INT], 35)
        self.assertEqual(mods[mod.ACC], 35)
        self.assertEqual(mods[mod.MACC], 35)
        self.assertEqual(mods[mod.TRIPLE_ATTACK], 6)
        parry = self.db.one(
            "SELECT amount FROM item_skill_bonus WHERE item_id = ? AND skill_id = ?",
            (21837, 31))
        self.assertIsNotNone(parry)
        self.assertEqual(int(parry["amount"]), 277)

    def test_percent_hp_modifier_is_kept(self):
        self.assertEqual(self.mods(26366)[mod.HPP], 10)  # Plat. Mog. Belt: HP+10%

    def test_regen_and_enhancing_duration_gear_has_its_mods(self):
        self.assertEqual(self.mods(23573)[mod.PERPETUANCE], 6500)   # Arbatel Bracers +3
        self.assertEqual(self.mods(26265)[mod.REGEN_DURATION], 15)  # Lugh's Cape
        self.assertEqual(self.mods(23439)[mod.REGEN_MULTIPLIER], 25)  # Arbatel Bonnet +3
        self.assertEqual(self.mods(23982)[mod.ENH_MAGIC_DURATION], 12)  # Pedagogy Gown +4

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


class MissingClientGearModsTest(unittest.TestCase):
    """Migration 183: gear the client has but LandSandBoat's item_mods dump does not."""

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

    def test_null_masque_carries_its_regen_refresh_and_regain(self):
        mods = self.mods(24270)
        self.assertEqual(mods[mod.DEF], 138)
        self.assertEqual(mods[mod.HP], 100)
        self.assertEqual(mods[mod.MP], 70)
        self.assertEqual(mods[mod.MND], 50)
        self.assertEqual(mods[mod.MACC], 50)
        self.assertEqual(mods[mod.HASTE_GEAR], 1000)  # Haste10%, no plus in the tooltip
        self.assertEqual(mods[mod.REGEN], 3)
        self.assertEqual(mods[mod.REFRESH], 1)
        self.assertEqual(mods[mod.REGAIN], 2)
        self.assertEqual(mods[mod.DMG], -1000)

    def test_null_belt_carries_its_accuracy_and_regen(self):
        mods = self.mods(26367)
        self.assertEqual(mods[mod.ACC], 30)
        self.assertEqual(mods[mod.RACC], 30)
        self.assertEqual(mods[mod.MACC], 30)
        self.assertEqual(mods[mod.REGEN], 3)

    def test_hiza_body_carries_its_regen(self):
        mods = self.mods(25792)
        self.assertEqual(mods[mod.DEF], 141)
        self.assertEqual(mods[mod.HP], 100)
        self.assertEqual(mods[mod.STR], 40)
        self.assertEqual(mods[mod.ACC], 46)
        self.assertEqual(mods[mod.ATT], 28)
        self.assertEqual(mods[mod.REGEN], 12)
        self.assertEqual(mods[mod.HASTE_GEAR], 400)

    def test_wakido_kabuto_regain_is_restored(self):
        """Migration 92's parser dropped Wakido Kabuto +4's "Regain"+4."""
        self.assertEqual(self.mods(23906)[mod.REGAIN], 4)


class PrimeAfterglowItemDataTest(unittest.TestCase):
    """Migration 165 gives every 119 III Prime its afterglow stat block."""

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

    def skill(self, item_id: int, skill_id: int) -> int:
        row = self.db.one(
            "SELECT amount FROM item_skill_bonus WHERE item_id = ? AND skill_id = ?",
            (item_id, skill_id))
        return int(row["amount"]) if row is not None else 0

    def test_every_final_weapon_has_its_own_skill_at_277(self):
        for family, stages in prime_weapons.PRIME_FAMILIES:
            if family in ("Loughnashade", "Duban"):   # horn and shield, not a weapon
                continue
            final_id = stages[-1][1]
            weapon = self.db.one(
                "SELECT skill, ilvl_skill FROM item_weapon WHERE item_id = ?", (final_id,))
            self.assertIsNotNone(weapon, family)
            skill = int(weapon["skill"])
            total = int(weapon["ilvl_skill"]) + self.skill(final_id, skill)
            self.assertEqual(total, 277, (family, final_id, skill))

    def test_helheim_and_lorg_mor_use_the_119iii_damage_rating(self):
        helheim = self.db.one(
            "SELECT dmg, ilvl_skill FROM item_weapon WHERE item_id = 21653")
        self.assertEqual(int(helheim["dmg"]), 336)      # was 318, the 119 II value
        self.assertEqual(int(helheim["ilvl_skill"]), 277)
        lorg = self.db.one("SELECT dmg, ilvl_skill FROM item_weapon WHERE item_id = 22002")
        self.assertEqual(int(lorg["dmg"]), 240)         # was 227, the 119 II value
        self.assertEqual(int(lorg["ilvl_skill"]), 277)

    def test_mpu_gandring_skill_is_the_119iii_value(self):
        row = self.db.one("SELECT ilvl_skill FROM item_weapon WHERE item_id = 21590")
        self.assertEqual(int(row["ilvl_skill"]), 277)   # was 269, the 119 II value

    def test_varga_and_earp_crit_rate_is_in_hundredths(self):
        self.assertEqual(self.mods(21535)[mod.CRIT_HIT_RATE], 1500)  # +15%
        self.assertEqual(self.mods(22164)[mod.CRIT_HIT_RATE], 1500)
        self.assertEqual(self.skill(21535, 28), 277)    # Guarding skill

    def test_secondary_weapon_traits_are_present(self):
        self.assertEqual(self.mods(21653)[mod.STORETP], 10)          # Helheim
        self.assertEqual(self.mods(21785)[mod.DOUBLE_ATTACK], 10)    # Laphria
        self.assertEqual(self.mods(21891)[mod.DOUBLE_ATTACK], 10)    # Gae Buide
        self.assertEqual(self.mods(21986)[mod.DOUBLE_ATTACK], 10)    # Kusanagi
        self.assertEqual(self.mods(22106)[mod.MATT], 80)             # Opashoro
        self.assertEqual(self.mods(22106)[mod.MAGIC_DAMAGE], 325)
        self.assertEqual(self.mods(22002)[mod.REGEN], 7)             # Lorg Mor
        self.assertNotIn(mod.DMGMAGIC_II, self.mods(22002))          # that is Duban
        self.assertEqual(self.mods(22002)[mod.DMG], -1000)           # Damage taken -10%

    def test_duban_carries_its_shield_skill_and_mdt(self):
        self.assertEqual(self.mods(26495)[mod.DEF], 155)
        self.assertEqual(self.mods(26495)[mod.DMGMAGIC_II], -2500)   # -25%
        self.assertEqual(self.skill(26495, 30), 134)                 # Shield skill

    def test_loughnashade_has_an_item_level(self):
        row = self.db.one("SELECT item_level FROM items WHERE item_id = 22307")
        self.assertEqual(int(row["item_level"]), 119)


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

    def test_food_percent_bonus_is_capped(self):
        mods = {mod.FOOD_ATT_PERCENT: 23, mod.FOOD_ATT_CAP: 150}
        self.assertEqual(
            stats._food_percent(100, mods, mod.FOOD_ATT_PERCENT, mod.FOOD_ATT_CAP), 23)
        self.assertEqual(
            stats._food_percent(1000, mods, mod.FOOD_ATT_PERCENT, mod.FOOD_ATT_CAP), 150)


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

    def test_regen_duration_and_perpetuance_lines(self):
        text = ('[Hands] All Races DEF:112 "Perpetuance"+65% '
                '"Regen" effect duration +15 Enhancing magic duration +20% LV 99 SCH')
        mods, _skills, leftover = reforged.parse_description(text)
        table = dict(mods)
        self.assertEqual(table[mod.PERPETUANCE], 6500)
        self.assertEqual(table[mod.REGEN_DURATION], 15)
        self.assertEqual(table[mod.ENH_MAGIC_DURATION], 20)
        self.assertFalse(reforged.looks_like_stat(leftover))

    def test_regen_potency_and_short_duration_lines(self):
        text = ('[Head] All Races DEF:100 "Regen" potency +25% '
                '"Regen" duration +27 LV 99 SCH')
        mods, _skills, leftover = reforged.parse_description(text)
        table = dict(mods)
        self.assertEqual(table[mod.REGEN_MULTIPLIER], 25)
        self.assertEqual(table[mod.REGEN_DURATION], 27)
        self.assertFalse(reforged.looks_like_stat(leftover))

class LocusTierTest(unittest.TestCase):
    """Every Locus template is on the same level-100+ sheet as Locus Camelopard."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Database(Path(cls.tmp.name) / "fanxi.db", ROOT)
        cls.db.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_locus_gets_the_master_level_offense(self):
        rows = self.db.all(
            "SELECT name, level_min, level_max, hp FROM monster_templates "
            "WHERE name LIKE 'Locus%' ORDER BY name")
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            name = str(row["name"])
            level_min, level_max = int(row["level_min"]), int(row["level_max"])
            self.assertGreaterEqual(int(row["hp"]), 100000, name)
            low = stats.build_monster(level_min).fighter
            high = stats.build_monster(level_max).fighter
            # The 99-capped table alone gives 424-624 Accuracy at these levels; the
            # master slope has to put every Locus above that, including the 129-131
            # Crawler's Nest camp.
            self.assertGreaterEqual(low.accuracy, 1174, name)
            self.assertGreaterEqual(high.accuracy,
                                    424 + max(0, level_max - 99) * 20, name)
            self.assertGreaterEqual(high.attack, 1200, name)

    def test_locus_placeholder_hp_is_gone(self):
        """Migration 174: these three imported as 2,680/2,720/2,740 HP."""
        expected = {
            "Locus Colibri": 229600,
            "Locus Wivre": 259000,
            "Locus Lemures": 311800,
        }
        for name, hp in expected.items():
            row = self.db.one(
                "SELECT hp FROM monster_templates WHERE name = ?", (name,))
            self.assertIsNotNone(row, name)
            self.assertEqual(int(row["hp"]), hp, name)

    def test_locus_spawns_roll_their_retail_level_range(self):
        rows = self.db.all(
            "SELECT s.level, t.name, t.level_min, t.level_max FROM monster_spawns s "
            "JOIN monster_templates t ON t.id = s.template_id "
            "WHERE t.name LIKE 'Locus%'")
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            self.assertIsNone(row["level"], row["name"])
            self.assertLessEqual(int(row["level_min"]), int(row["level_max"]))
        # The published Bhaflau table runs Colibri to 136, not the importer's 135.
        colibri = self.db.one(
            "SELECT level_min, level_max FROM monster_templates "
            "WHERE name = 'Locus Colibri'")
        self.assertEqual((int(colibri["level_min"]), int(colibri["level_max"])),
                         (133, 136))

    def test_mob_hp_interpolates_between_the_retail_ends(self):
        # Bibiki Bay Camelopard: 289,900 at 135, 308,300 at 137.
        self.assertEqual(mob_hp_for_level(135, 135, 137, 308300, 289900), 289900)
        self.assertEqual(mob_hp_for_level(136, 135, 137, 308300, 289900), 299100)
        self.assertEqual(mob_hp_for_level(137, 135, 137, 308300, 289900), 308300)
        # A template without hp_min keeps its old flat value.
        self.assertEqual(mob_hp_for_level(135, 135, 137, 305000), 305000)

    def test_locus_respawn_rerolls_level_and_hp(self):
        service = FanxiService(Config.from_env(ROOT), self.db)
        row = next(row for row in service.monster_spawns_for_zone(4)
                   if row["template_name"] == "Locus Camelopard")
        row = dict(row)
        row["level"] = None
        mob = mob_from_row(row, 124, random.Random(1))
        self.assertTrue(mob.level_rolls)
        self.assertIn(mob.level, (135, 136, 137))
        self.assertEqual(mob.hp_max, mob.level_stats[mob.level]["hp"])
        self.assertEqual(mob.defense_override, scaled_level_stat(
            mob.level_stats[mob.level]["defense"], LOCUS_DEFENSE_SCALE))
        self.assertEqual(mob.evasion_override, scaled_level_stat(
            mob.level_stats[mob.level]["evasion"], LOCUS_EVASION_SCALE))
        mob.reset_mob(0.0, random.Random(4))
        self.assertIn(mob.level, (135, 136, 137))
        self.assertEqual(mob.hp_max, mob.level_stats[mob.level]["hp"])
        self.assertEqual(mob.hp, mob.hp_max)

    def test_mob_from_row_uses_the_rolled_level_and_hp(self):
        service = FanxiService(Config.from_env(ROOT), self.db)
        row = next(row for row in service.monster_spawns_for_zone(4)
                   if row["template_name"] == "Locus Camelopard")
        row = dict(row)
        row["level"] = 136
        mob = mob_from_row(row, 123)
        self.assertEqual(mob.level, 136)
        self.assertEqual(mob.hp_max, 299100)
        self.assertEqual(mob.hp, 299100)
        self.assertEqual(mob.defense_override, 1034)     # 1379 x 0.75
        self.assertEqual(mob.evasion_override, 940)      # 1254 x 0.75

    def test_distract_iii_is_flat_evasion_down(self):
        service = FanxiService(Config.from_env(ROOT), self.db)
        world = World(Config.from_env(ROOT), service, None)
        entity = ZoneEntity(
            kind="mob", id=0x01000000, targid=2, zone=4,
            name="Locus Camelopard", level=135,
            defense_override=1346, evasion_override=1224)
        world.apply_mob_effect(
            entity, effects.for_spell("Distract III"), None, time.time(),
            name="Distract III")
        self.assertEqual(world.debuffed_monster(entity).evasion, 1094)

    def test_monster_sheet_uses_the_defense_and_evasion_override(self):
        service = FanxiService(Config.from_env(ROOT), self.db)
        world = World(Config.from_env(ROOT), service, None)
        entity = ZoneEntity(
            kind="mob", id=0x01000000, targid=1, zone=4,
            name="Locus Camelopard", level=135,
            defense_override=1346, evasion_override=1224)
        sheet = world.monster_sheet(entity)
        self.assertEqual(sheet.fighter.defense, 1346)
        self.assertEqual(sheet.fighter.evasion, 1224)


if __name__ == "__main__":
    unittest.main()
