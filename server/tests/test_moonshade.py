"""The Moonshade Earring's two augment choices."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import augment_stats, capes, moonshade
from fanxi_server.game import modifiers as mod


class MoonshadeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character = self.service.create_character(
            account["id"], {"name": "Onedough", "race": 1})
        self.character_id = int(self.character["id"])
        self.service.add_item(self.character_id, 11697)

    def copy(self) -> dict:
        card = moonshade.catalog(self.service, self.character_id)
        self.assertEqual(len(card["copies"]), 1)
        return card["copies"][0]

    def test_the_two_sets_hold_the_sixteen_choices(self):
        sets = moonshade.sets()
        self.assertEqual([group["key"] for group in sets], ["first", "second"])
        self.assertEqual([len(group["options"]) for group in sets], [8, 8])
        first = {option["key"]: option["text"] for option in sets[0]["options"]}
        second = {option["key"]: option["text"] for option in sets[1]["options"]}
        self.assertEqual(first["acc"], "Accuracy+4")
        self.assertEqual(first["hp"], "HP+25")
        self.assertEqual(first["mab"], "Mag.Atk.Bns.+4")
        self.assertEqual(second["regain"], 'Latent effect: "Regain"+10')
        self.assertEqual(second["tp_bonus"], "TP Bonus+250")
        self.assertEqual(second["quick_magic"], "Occ. quickens spellcasting+3%")
        self.assertEqual(second["resist"], "Occ. inc. resist. to stat. ailments+5")

    def test_apply_writes_both_choices_and_the_stat_sheet_reads_them(self):
        copy = self.copy()
        result = moonshade.apply(self.service, self.character_id,
                                 copy["container"], copy["slot"], "acc", "tp_bonus")
        self.assertEqual(result["current"]["first"], "acc")
        self.assertEqual(result["current"]["second"], "tp_bonus")
        self.assertEqual(result["current"]["text"], ["Accuracy+4", "TP Bonus+250"])
        block = capes._encode_slots([(23, 3), (353, 4)])
        self.assertEqual(capes.describe(block), "Accuracy+4, TP Bonus+250")
        self.assertEqual(augment_stats.item_mods(11697, block),
                         {mod.ACC: 4, mod.TP_BONUS: 250})

    def test_reapplying_replaces_the_pair(self):
        copy = self.copy()
        moonshade.apply(self.service, self.character_id, copy["container"], copy["slot"],
                        "hp", "refresh")
        current = self.copy()["current"]
        self.assertEqual((current["first"], current["second"]), ("hp", "refresh"))
        self.assertEqual(current["text"], ["HP+25", 'Latent effect: "Refresh"+1'])
        moonshade.apply(self.service, self.character_id, copy["container"], copy["slot"],
                        "mp", "counter")
        current = self.copy()["current"]
        self.assertEqual((current["first"], current["second"]), ("mp", "counter"))

    def test_an_unknown_choice_is_rejected(self):
        copy = self.copy()
        with self.assertRaises(ValueError):
            moonshade.apply(self.service, self.character_id, copy["container"],
                            copy["slot"], "acc", "nope")
        with self.assertRaises(ValueError):
            moonshade.apply(self.service, self.character_id, copy["container"],
                            copy["slot"], "nope", "tp_bonus")

    def test_a_different_item_is_rejected(self):
        self.service.add_item(self.character_id, 26258)   # Andartia's Mantle
        row = next(item for item in self.service.inventory(self.character_id)
                   if int(item["item_id"]) == 26258)
        with self.assertRaises(ValueError):
            moonshade.apply(self.service, self.character_id, row["container"],
                            row["slot"], "acc", "tp_bonus")

    def test_clear_empties_the_block(self):
        copy = self.copy()
        moonshade.apply(self.service, self.character_id, copy["container"], copy["slot"],
                        "acc", "tp_bonus")
        moonshade.clear(self.service, self.character_id, copy["container"], copy["slot"])
        self.assertIsNone(self.copy()["current"])
        row = next(item for item in self.service.inventory(self.character_id)
                   if int(item["item_id"]) == 11697)
        self.assertEqual(bytes(row["extra"]), capes._encode_slots([]))

    def test_a_stored_copy_can_be_augmented(self):
        self.db.execute(
            "DELETE FROM char_inventory WHERE character_id = ? AND item_id = 11697",
            (self.character_id,))
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 8, 9, 11697, 1)", (self.character_id,))
        copy = self.copy()
        self.assertEqual(copy["container_name"], "Wardrobe 1")
        moonshade.apply(self.service, self.character_id, 8, 9, "racc", "dmg_bonus")
        current = self.copy()["current"]
        self.assertEqual(current["text"], ["Rng.Acc.+4", "Occ. grants dmg. bonus based on TP+5%"])
