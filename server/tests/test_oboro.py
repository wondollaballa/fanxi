"""Oboro Dynamis-Divergence weapon augments and the Data page catalog."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import augment_gear, augment_stats, augments, modifiers as mod, oboro


class OboroDatasetTest(unittest.TestCase):
    def test_every_family_has_three_qualities_and_three_paths(self):
        entries = oboro.entries()
        self.assertEqual(len(entries), 66)
        for entry in entries:
            self.assertEqual([path["key"] for path in entry["paths"]], ["A", "B", "C"])
            self.assertEqual(entry["kind"], "oboro")
            self.assertIn(entry["quality"], ("NQ", "HQ1", "HQ2"))
            self.assertTrue(entry["job"])
            self.assertTrue(entry["weapon"])

    def test_musa_is_the_sch_hq2_staff(self):
        entry = oboro.get(22099)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Musa")
        self.assertEqual(entry["job"], "SCH")
        self.assertEqual(entry["quality"], "HQ2")
        self.assertEqual((entry["rank"], entry["tier"]), (25, 2))
        self.assertEqual([path["bundle"] for path in entry["paths"]], [187, 188, 189])
        self.assertEqual(entry["paths"][2]["augments"], [
            '"Regen" potency +25', '"Cure" potency +25%', '"Fast Cast"+10%',
        ])

    def test_bundles_are_unique_and_rp_uses_curve_a(self):
        bundles = [path["bundle"] for entry in oboro.entries() for path in entry["paths"]]
        self.assertEqual(len(bundles), len(set(bundles)))
        self.assertEqual(set(bundles), set(range(1, 199)))
        for entry in oboro.entries():
            for path in entry["paths"]:
                self.assertEqual(path["curve"], 0)
                self.assertEqual(path["rank"], entry["rank"])


class OboroAugmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]

    def add_musa(self) -> dict:
        self.service.add_item(self.character_id, 22099, 1)
        return next(row for row in self.service.inventory(self.character_id)
                    if int(row["item_id"]) == 22099)

    def test_the_old_static_musa_path_c_rows_are_gone(self):
        rows = self.db.all(
            "SELECT mod_id FROM item_mods WHERE item_id = 22099 "
            "AND mod_id IN (170, 374, 838, 1223)")
        self.assertEqual(rows, [])

    def test_cap_path_c_writes_the_r25_bundle_and_stats(self):
        row = self.add_musa()
        result = augment_gear.cap(
            self.service, self.character_id, row["container"], row["slot"], "C")
        self.assertEqual(result["path"]["bundle"], 189)
        capped = next(row for row in self.service.inventory(self.character_id)
                      if int(row["item_id"]) == 22099)
        decoded = augments.decode(capped["extra"])
        self.assertEqual((decoded["path"], decoded["rank"], decoded["tier"],
                          decoded["index"]), ("C", 25, 2, 189))
        self.assertEqual(augment_stats.item_mods(22099, capped["extra"]), {
            mod.REGEN_POTENCY: 25,
            mod.CURE_POTENCY: 25,
            mod.FASTCAST: 10,
        })

    def test_equipped_musa_path_c_reaches_the_sheet(self):
        row = self.add_musa()
        augment_gear.cap(self.service, self.character_id, row["container"],
                         row["slot"], "C")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
                "VALUES (?, 0, ?, ?, ?)",
                (self.character_id, row["container"], row["slot"], 22099))
        mods = self.service.equipped_mods(self.character_id)
        self.assertEqual(mods.get(mod.REGEN_POTENCY), 25)
        self.assertEqual(mods.get(mod.CURE_POTENCY), 25)
        self.assertEqual(mods.get(mod.FASTCAST), 10)

    def test_path_a_and_b_switch_the_stat_lines(self):
        row = self.add_musa()
        augment_gear.cap(self.service, self.character_id, row["container"], row["slot"], "A")
        capped = next(row for row in self.service.inventory(self.character_id)
                      if int(row["item_id"]) == 22099)
        self.assertEqual(augment_stats.item_mods(22099, capped["extra"]),
                         {mod.STORETP: 25})
        augment_gear.cap(self.service, self.character_id, row["container"], row["slot"], "B")
        capped = next(row for row in self.service.inventory(self.character_id)
                      if int(row["item_id"]) == 22099)
        self.assertEqual(augment_stats.item_mods(22099, capped["extra"]),
                         {mod.SUBTLE_BLOW_II: 25})

    def test_catalog_puts_owned_copies_first_and_prices_the_rest(self):
        self.add_musa()
        catalog = oboro.catalog(self.service, self.character_id)
        self.assertEqual(len(catalog["items"]), 66)
        first = catalog["items"][0]
        self.assertEqual(first["name"], "Musa")
        self.assertTrue(first["owned"])
        self.assertEqual(len(first["copies"]), 1)
        self.assertGreater(first["price"], 0)
        rest = [item for item in catalog["items"][1:] if not item["owned"]]
        self.assertTrue(rest)
        self.assertTrue(all(item["price"] > 0 for item in rest))

    def test_cap_unknown_slot_and_path_are_errors(self):
        row = self.add_musa()
        with self.assertRaises(LookupError):
            augment_gear.cap(self.service, self.character_id, 0, 80, "C")
        with self.assertRaises(ValueError):
            augment_gear.cap(self.service, self.character_id, row["container"],
                             row["slot"], "Z")

    def test_character_data_carries_the_oboro_card(self):
        self.add_musa()
        data = self.service.character_data(self.character_id)
        self.assertEqual(len(data["oboro"]["items"]), 66)
        musa = next(item for item in data["oboro"]["items"] if item["item_id"] == 22099)
        self.assertTrue(musa["owned"])
        self.assertIsNone(musa["copies"][0]["current"])
        self.assertIn(22099, [item["item_id"] for item in data["augments"]])
        self.assertEqual(
            next(item for item in data["augments"] if item["item_id"] == 22099)["kind"],
            "oboro")


if __name__ == "__main__":
    unittest.main()
