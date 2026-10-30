"""Trial of the Magians augment blocks and the TP Bonus they carry."""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from support import make_service

from fanxi_server.game import augment_stats, magian, modifiers as mod


class MagianBlockTest(unittest.TestCase):
    def test_centovente_tp_bonus_block(self):
        block = magian.encode([(353, 19)])
        self.assertEqual(len(block), 24)
        self.assertEqual(block[0], 0x02)
        self.assertEqual(block[1], 0x43)
        self.assertEqual(magian.decode(block)["slots"][0], {"id": 353, "value": 19})
        self.assertEqual(augment_stats.item_mods(19874, block), {mod.TP_BONUS: 1000})
        self.assertEqual(augment_stats.describe_augments(19874, block), "TP Bonus+1000")

    def test_wsd_and_store_tp_choices(self):
        wsd = magian.encode([(740, 1), (327, 9)])
        self.assertEqual(augment_stats.item_mods(19874, wsd), {mod.WSD_ALL_HITS: 10})
        store = magian.encode([(740, 1), (142, 14)])
        self.assertEqual(augment_stats.item_mods(19874, store), {mod.STORETP: 15})

    def test_a_standard_block_is_not_a_magian_block(self):
        self.assertIsNone(magian.decode(bytes.fromhex("0203191861" + "00" * 7)))


class MoonshadeTpBonusTest(unittest.TestCase):
    def test_the_standard_block_carries_250(self):
        block = bytes.fromhex("020319186121000000000000000000000000000000000000")
        self.assertEqual(augment_stats.item_mods(11697, block),
                         {mod.ATT: 4, mod.TP_BONUS: 250})


class MagianCatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character = self.service.create_character(
            account["id"], {"name": "Onedough", "race": 1})
        self.character_id = int(self.character["id"])
        self.service.add_item(self.character_id, 19332)   # Peeler

    def catalog_item(self, item_id: int) -> dict:
        catalog = magian.catalog(self.service, self.character_id)
        return next(item for item in catalog["items"] if item["item_id"] == item_id)

    def row(self, item_id: int) -> dict:
        return next(item for item in self.service.inventory(self.character_id)
                    if int(item["item_id"]) == item_id)

    def test_the_catalogue_covers_the_trial_items(self):
        catalog = magian.catalog(self.service, self.character_id)
        self.assertGreater(catalog["catalog_size"], 500)
        centovente = next(item for item in catalog["items"] if item["item_id"] == 19874)
        self.assertEqual([trial["id"] for trial in centovente["trials"]], [3200, 3201, 3202])
        self.assertEqual(centovente["trials"][1]["text"], ["TP Bonus +1000"])
        peeler = self.catalog_item(19332)
        self.assertEqual(peeler["copies"][0]["current"], "no trial")
        self.assertEqual(peeler["trials"][0]["reward"], 19333)

    def test_completing_a_trial_replaces_the_item_and_writes_the_trial(self):
        copy = self.catalog_item(19332)["copies"][0]
        result = magian.apply(self.service, self.character_id,
                              copy["container"], copy["slot"], 2)
        self.assertEqual(result["item_id"], 19333)
        renegade = self.catalog_item(19333)
        self.assertEqual(len(renegade["copies"]), 1)
        inventory = self.row(19333)
        decoded = magian.decode(inventory["extra"])
        self.assertEqual(decoded["trial"], 2)
        self.assertEqual(decoded["slots"][0], {"id": 0, "value": 0})

    def test_an_augment_trial_keeps_the_item_and_changes_the_block(self):
        copy = self.catalog_item(19332)["copies"][0]
        magian.apply(self.service, self.character_id, copy["container"], copy["slot"], 2)
        renegade = self.catalog_item(19333)["copies"][0]
        magian.apply(self.service, self.character_id, renegade["container"],
                     renegade["slot"], 3)
        inventory = self.row(19333)
        self.assertEqual(magian.decode(inventory["extra"])["trial"], 3)
        self.assertEqual(magian.describe(inventory["extra"]), "Attack+3")
        self.assertEqual(magian.item_mods(inventory["extra"]), {mod.ATT: 3})

    def test_centovente_paths_write_the_empyrean_augments(self):
        self.service.add_item(self.character_id, 19874)
        copy = self.catalog_item(19874)["copies"][0]
        magian.apply(self.service, self.character_id, copy["container"], copy["slot"], 3201)
        inventory = self.row(19874)
        self.assertEqual(magian.describe(inventory["extra"]), "TP Bonus+1000")
        self.assertEqual(magian.item_mods(inventory["extra"]), {mod.TP_BONUS: 1000})

    def test_a_trial_that_is_not_offered_is_rejected(self):
        copy = self.catalog_item(19332)["copies"][0]
        with self.assertRaises(ValueError):
            magian.apply(self.service, self.character_id, copy["container"],
                         copy["slot"], 3200)
        with self.assertRaises(LookupError):
            magian.apply(self.service, self.character_id, 99, 99, 2)


if __name__ == "__main__":
    unittest.main()
