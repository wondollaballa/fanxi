"""Temenos Furnace Rank 30 pieces in the RP card and the stat sheet."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import augment_gear, augment_stats, augments, temenos
from fanxi_server.game import modifiers as mod


class TemenosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character = self.service.create_character(
            account["id"], {"name": "Onedough", "race": 1})
        self.character_id = int(self.character["id"])
        self.service.set_gil(self.character_id, 1_000_000)

    def rows(self) -> list[dict]:
        return augment_gear.inventory_items(self.service, self.character_id)

    def test_dataset_covers_the_furnace_pieces(self):
        entries = {entry["item_id"]: entry for entry in temenos.entries()}
        self.assertEqual(set(entries), {26275, 26276, 26234, 26119})
        for entry in entries.values():
            self.assertEqual(entry["kind"], "temenos")
            self.assertEqual(entry["set"], "Temenos Furnace")
            prefix = b"\x03\x83" if entry["bundle"] else b"\x02\x03"
            self.assertEqual(entry["block"][:2], prefix)
            self.assertEqual(len(entry["block"]), 24)
            path = entry["paths"][0]
            self.assertEqual((path["key"], path["rank"], path["rp"]), ("A", 30, 55800))
            self.assertEqual(path["bundle"], entry["bundle"])
            self.assertTrue(path["augments"])

    def test_alabaster_mantle_rows_and_mods(self):
        mantle = temenos.get(26275)
        self.assertEqual(mantle["rows"], [
            "Accuracy+25 Attack+25",
            "Rng.Acc.+25 Rng.Atk.+25",
            "STR+15 DEX+15",
            "Enmity-10",
        ])
        self.assertEqual(augment_stats.item_mods(26275, mantle["block"]), {
            mod.ACC: 25, mod.ATT: 25, mod.RACC: 25, mod.RATT: 25,
            mod.STR: 15, mod.DEX: 15, mod.ENMITY: -10,
        })

    def test_murky_mantle_rows_and_mods(self):
        mantle = temenos.get(26276)
        self.assertEqual(mantle["rows"], [
            "Mag. Acc+25 /Mag. Dmg.+25", "INT+15", "Enmity-10"])
        self.assertEqual(augment_stats.item_mods(26276, mantle["block"]), {
            mod.MACC: 25, mod.MAGIC_DAMAGE: 25, mod.INT: 15, mod.ENMITY: -10,
        })

    def test_murky_ring_rows_and_mods(self):
        ring = temenos.get(26234)
        self.assertEqual(ring["rows"], [
            "Accuracy+15", "Rng.Acc.+15", "Mag. Acc.+15",
            "Eva.+10 /Mag. Eva.+10", "Crit.hit rate+5",
        ])
        self.assertEqual(augment_stats.item_mods(26234, ring["block"]), {
            mod.ACC: 15, mod.RACC: 15, mod.MACC: 15,
            mod.EVA: 10, mod.MEVA: 10, mod.CRIT_HIT_RATE: 500,
        })

    def test_alabaster_earring_rows_and_mods(self):
        earring = temenos.get(26119)
        self.assertEqual(earring["bundle"], 468)
        self.assertEqual(earring["rows"], [
            "Accuracy+15 Rng. Acc.+15 Mag. Acc.+15",
            "All Attr.+10",
            '"Store TP"+5',
        ])
        self.assertEqual(augment_stats.item_mods(26119, earring["block"]), {
            mod.ACC: 15, mod.RACC: 15, mod.MACC: 15,
            mod.STR: 10, mod.DEX: 10, mod.VIT: 10, mod.AGI: 10,
            mod.INT: 10, mod.MND: 10, mod.CHR: 10, mod.STORETP: 5,
        })

    def test_an_owned_mantle_appears_in_the_rp_list(self):
        self.service.armory_add(self.character_id, 26275)
        row = next(item for item in self.rows() if item["item_id"] == 26275)
        self.assertEqual((row["kind"], row["name"]), ("temenos", "Alabaster Mantle"))
        self.assertIsNone(row["current"])
        self.assertEqual(row["paths"][0]["label"], "Rank 30")

        capped = augment_gear.cap(self.service, self.character_id,
                                  row["container"], row["slot"], "A")
        self.assertEqual(capped["path"]["key"], "A")
        row = next(item for item in self.rows() if item["item_id"] == 26275)
        self.assertEqual(row["current"]["path"], "A")
        self.assertEqual(row["current"]["rank"], 30)
        self.assertEqual(row["current"]["rp"], 55800)
        inventory = next(item for item in self.service.inventory(self.character_id)
                         if int(item["item_id"]) == 26275)
        self.assertEqual(bytes(inventory["extra"]), temenos.get(26275)["block"])

    def test_an_owned_earring_appears_and_caps_as_a_bundle(self):
        self.service.armory_add(self.character_id, 26119)
        row = next(item for item in self.rows() if item["item_id"] == 26119)
        self.assertEqual((row["kind"], row["name"]), ("temenos", "Alabaster Earring"))
        self.assertIsNone(row["current"])
        self.assertEqual(row["paths"][0]["bundle"], 468)

        augment_gear.cap(self.service, self.character_id,
                         row["container"], row["slot"], "A")
        row = next(item for item in self.rows() if item["item_id"] == 26119)
        self.assertEqual(row["current"]["rank"], 30)
        self.assertEqual(row["current"]["bundle"], 468)
        inventory = next(item for item in self.service.inventory(self.character_id)
                         if int(item["item_id"]) == 26119)
        build = augments.decode(inventory["extra"])
        self.assertEqual(build["index"], 468)
        self.assertEqual(build["rank"], 30)
        self.assertEqual(build["rp"], 55800)

    def test_capping_rejects_an_unknown_path(self):
        self.service.armory_add(self.character_id, 26275)
        row = next(item for item in self.rows() if item["item_id"] == 26275)
        with self.assertRaises(ValueError):
            augment_gear.cap(self.service, self.character_id,
                             row["container"], row["slot"], "D")

    def test_a_piece_outside_the_dataset_is_ignored(self):
        self.service.add_item(self.character_id, 26258)   # Andartia's Mantle
        self.assertFalse(any(item["item_id"] == 26258 for item in self.rows()))
