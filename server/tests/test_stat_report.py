"""The live checkparam-style report the launcher shows.

The report is only useful if its rows add up to the sheet combat actually uses.  These
tests build a real zone session, wear a weapon and body piece, turn on a job ability,
haste and food, then check every derived total against ``stat_sheet`` and every source
row against the total above it.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, modifiers as mod, stat_report, unity
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


class StatReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("reporter", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Reporter", "race": 1})
        self.world = World(self.config, self.service, None)
        self.service.attach_world(self.world)
        self.session = ZoneSession(
            self.world, ("127.0.0.1", 4321),
            self.service.character_record(self.service.character(self.character["id"]),
                                          "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 4321)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)

    def equip(self, item_id: int, kind: int) -> bool:
        if self.db.one("SELECT 1 FROM items WHERE item_id = ?", (item_id,)) is None:
            return False
        self.service.add_item(int(self.character["id"]), item_id)
        held = self.db.one(
            "SELECT container, slot FROM char_inventory "
            "WHERE character_id = ? AND item_id = ? ORDER BY slot LIMIT 1",
            (int(self.character["id"]), int(item_id)))
        if held is None:
            return False
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, ?, ?, ?, ?)",
                (int(self.character["id"]), int(kind), int(held["container"]),
                 int(held["slot"]), int(item_id)))
        return True

    def report(self) -> dict:
        return self.session.stat_report()

    def test_report_totals_match_the_combat_sheet(self):
        self.equip(20737, 0)   # Mpu Gandring
        self.equip(23947, 5)   # Ignominy Cuirass +4
        self.session.add_effect(effects.BERSERK, mods={mod.ATT: 25})
        self.session.status_effects.append(effects.BERSERK)
        self.session.add_effect(effects.HASTE, mods={mod.HASTE_MAGIC: 1500})
        self.session.status_effects.append(effects.HASTE)
        self.session.apply_food(4333, self.service.food_effect(4333))

        sheet = self.session.stat_sheet()
        by_key = {stat["key"]: stat for stat in self.report()["stats"]}
        for key, value in (("attack", sheet.attack), ("accuracy", sheet.accuracy),
                           ("defense", sheet.defense), ("evasion", sheet.evasion),
                           ("hp", sheet.max_hp), ("mp", sheet.max_mp)):
            self.assertEqual(by_key[key]["value"], value, key)

    def test_report_shows_effective_haste_interval_and_tp(self):
        """Hasso's ability haste must reach the report's sheet, not only combat_mods."""
        self.equip(16960, 0)   # Uchigatana, two-handed
        self.session.char.update(main_job=12, main_level=99, sub_job=0, sub_level=0)
        self.session.add_effect(effects.HASSO, duration=300)
        self.session.add_effect(effects.HASTE, duration=300,
                                mods={mod.HASTE_MAGIC: 1500})
        self.session.status_effects += [effects.HASSO, effects.HASTE]

        combat_mods = self.session.combat_mods()
        self.assertEqual(combat_mods.get(mod.HASTE_ABILITY, 0), 1000)
        sheet = self.session.stat_sheet()
        by_key = {stat["key"]: stat for stat in self.report()["stats"]}

        self.assertAlmostEqual(by_key["haste_total"]["value"],
                               sheet.total_haste * 100.0, places=2)
        self.assertAlmostEqual(by_key["attack_interval"]["value"],
                               sheet.attack_delay_ms / 1000.0, places=3)
        self.assertEqual(by_key["tp_per_hit"]["value"],
                         sheet.tp_per_hit_with_store_tp())
        ability = next(source for source in by_key["haste_total"]["sources"]
                       if source["key"] == "job_abilities")
        self.assertAlmostEqual(ability["value"], 10.0)
        # Every row's own source rows still add up to the row they describe, with the
        # stance's STR/Accuracy folded in as well.
        for stat in self.report()["stats"]:
            self.assertAlmostEqual(
                sum(source["value"] for source in stat["sources"]),
                stat["value"], places=3, msg=stat["key"])

    def test_every_source_and_detail_adds_to_its_total(self):
        self.equip(20737, 0)
        self.equip(23947, 5)
        self.session.add_effect(effects.BERSERK, mods={mod.ATT: 25})
        self.session.status_effects.append(effects.BERSERK)
        self.session.add_effect(effects.HASTE, mods={mod.HASTE_MAGIC: 1500})
        self.session.status_effects.append(effects.HASTE)
        self.session.apply_food(4333, self.service.food_effect(4333))

        report = self.report()
        for stat in report["stats"]:
            source_sum = sum(source["value"] for source in stat["sources"])
            self.assertAlmostEqual(source_sum, stat["value"], places=4,
                                   msg="%s source rows" % stat["key"])
            for source in stat["sources"]:
                detail_sum = sum(detail["value"] for detail in source["details"])
                self.assertAlmostEqual(detail_sum, source["value"], places=4,
                                       msg="%s %s details" % (stat["key"], source["key"]))
        json.dumps(report)  # the HTTP response has to be JSON-serializable

    def test_sources_name_gear_jt_ja_buffs_and_food(self):
        self.equip(20737, 0)
        self.session.add_effect(effects.BERSERK, mods={mod.ATT: 25})
        self.session.status_effects.append(effects.BERSERK)
        self.session.add_effect(effects.HASTE, mods={mod.HASTE_MAGIC: 1500})
        self.session.status_effects.append(effects.HASTE)
        self.session.apply_food(4333, self.service.food_effect(4333))
        report = self.report()
        by_key = {stat["key"]: stat for stat in report["stats"]}
        attack = {source["key"] for source in by_key["attack"]["sources"]}
        accuracy = {source["key"] for source in by_key["accuracy"]["sources"]}
        defense = {source["key"] for source in by_key["defense"]["sources"]}
        self.assertIn("gear", attack)
        self.assertIn("job_abilities", attack)
        self.assertIn("job_points", attack)
        self.assertIn("gear", accuracy)
        self.assertIn("traits", defense)
        haste = {source["key"] for source in by_key["haste_magic"]["sources"]}
        self.assertIn("buffs", haste)
        # Witch Soup's MP+25 is a food row; the source name is the item.
        mp = {source["key"] for source in by_key["mp"]["sources"]}
        self.assertIn("food", mp)
        food = next(source for source in by_key["mp"]["sources"] if source["key"] == "food")
        self.assertEqual(food["label"], "Food")

    def test_gear_rows_sum_to_the_aggregate_equipment_query(self):
        self.equip(20737, 0)
        self.equip(23947, 5)
        rows = self.service.equipped_slot_mods(int(self.character["id"]))
        merged = {}
        for row in rows:
            for mod_id, value in row["mods"].items():
                merged[int(mod_id)] = merged.get(int(mod_id), 0) + int(value)
        self.assertEqual(merged, self.service.equipped_mods(int(self.character["id"])))

    def test_augmented_copy_reaches_the_report_gear_rows(self):
        item_id = 27509   # Unity Rank 15 neck
        block = unity.encode(item_id)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO char_inventory "
                "(character_id, container, slot, item_id, quantity, extra) "
                "VALUES (?, 0, 20, ?, 1, ?)",
                (int(self.character["id"]), int(item_id), bytes(block)))
            conn.execute(
                "INSERT INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, 9, 0, 20, ?)",
                (int(self.character["id"]), int(item_id)))
        rows = self.service.equipped_slot_mods(int(self.character["id"]))
        neck = next(row for row in rows if row["kind"] == 9)
        self.assertTrue(neck["augments"])
        self.assertEqual(neck["mods"].get(mod.HP, 0) >= 200, True)
        self.assertEqual(neck["mods"].get(mod.DEF, 0) >= 30, True)
        merged = {}
        for row in rows:
            for mod_id, value in row["mods"].items():
                merged[int(mod_id)] = merged.get(int(mod_id), 0) + int(value)
        self.assertEqual(merged, self.service.equipped_mods(int(self.character["id"])))
        report = self.session.stat_report()
        hp = next(stat for stat in report["stats"] if stat["key"] == "hp")
        gear = next(source for source in hp["sources"] if source["key"] == "gear")
        neck_detail = next(detail for detail in gear["details"]
                           if "neck" in detail["label"].lower() or "neck" in detail["label"])
        self.assertEqual(neck_detail["note"], neck["augments"])

    def test_unknown_modifier_rows_use_real_stat_names(self):
        expected = {
            4: "MP → HP",
            168: "Spell interruption rate",
            244: "Resist Silence",
            250: "Resist Slow",
            256: "Aftermath",
            455: "Song spellcasting time",
            491: "Waltz potency",
            598: "Weapon skill damage (Mordant Rime)",
            958: "Resistance to all status ailments",
        }
        for mod_id, label in expected.items():
            self.assertEqual(stat_report.MOD_LABELS.get(mod_id), label)

    def test_extra_stat_percentages_and_reductions_are_displayed_correctly(self):
        sources = {
            "gear": {
                "label": "Gear",
                "mods": {168: 11},
                "entries": [
                    {"label": "Item with interrupts", "mods": {168: 11}},
                ],
            },
        }
        interrupts = stat_report._raw_entry(
            "mod:168", "Spell interruption rate", 168, True, 1, False, "Other", 2068,
            sources, {168: 11}, None, negate=True)
        self.assertEqual(interrupts["value"], -11)
        self.assertTrue(interrupts["percent"])
        self.assertEqual(interrupts["sources"][0]["details"][0]["value"], -11)


    def test_service_wrapper_returns_the_live_report(self):
        self.equip(20737, 0)
        report = self.service.character_stat_report(int(self.character["id"]))
        self.assertEqual(report["character_id"], int(self.character["id"]))
        self.assertTrue(report["stats"])
        # A character with no live session cannot answer this endpoint's data.
        self.world.sessions.clear()
        with self.assertRaises(Exception):
            self.service.character_stat_report(int(self.character["id"]))

    def test_service_matches_a_client_that_uses_the_db_id_as_its_wire_id(self):
        """Some client builds put the DB id in 0x00A; the stored char_id stays a content id."""
        self.equip(20737, 0)
        wire_id = int(self.character["id"])
        self.session.char["char_id"] = wire_id
        self.assertNotEqual(int(self.character["char_id"]), wire_id)
        report = self.service.character_stat_report(wire_id)
        self.assertEqual(report["character_id"], wire_id)
        self.assertTrue(report["stats"])


if __name__ == "__main__":
    unittest.main()
