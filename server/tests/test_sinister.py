"""Sinister Reign's standard five-slot max-augment card."""

import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from support import make_service  # noqa: E402

from fanxi_server.game import augment_stats, capes, modifiers as mod, sinister, skirmish  # noqa: E402

SAMNUHA = 27295


def item_named(name: str) -> dict:
    return next(entry for entry in sinister.entries() if entry["name"] == name)


class SinisterCatalogTest(unittest.TestCase):
    def test_every_sinister_piece_is_there(self):
        entries = sinister.entries()
        self.assertEqual(len(entries), 37)
        names = {entry["name"] for entry in entries}
        for name in ("Samnuha Tights", "Samnuha Coat", "Amm Greaves", "Lengo Pants",
                     "Taming Sari", "Enticer's Pants", "Founder's Breastplate"):
            self.assertIn(name, names)
        self.assertEqual(len({entry["item_id"] for entry in entries}), 37)

    def test_samnuha_tights_has_the_wiki_maxima(self):
        entry = item_named("Samnuha Tights")
        self.assertEqual(entry["item_id"], SAMNUHA)
        self.assertEqual([(row["key"], row["value"]) for row in entry["rows"]], [
            ("str", 10), ("dex", 10), ("da", 3), ("ta", 3),
        ])

    def test_enticers_pants_merges_the_combined_pet_row(self):
        entry = item_named("Enticer's Pants")
        rows = [(row["key"], row["value"]) for row in entry["rows"]]
        self.assertEqual(rows, [
            ("mp", 50), ("pet_acc_racc", 15), ("pet_macc", 15), ("pet_dt", -5),
        ])
        # 0x06A prints Pet: Accuracy and Pet: Rng. Acc. from the one slot; the
        # wiki lists them as two cells but retail holds them in one word.
        self.assertEqual(skirmish.label_of("pet_acc_racc"),
                         "Pet: Accuracy / Pet: Rng. Acc.")

    def test_every_row_is_encodable_and_round_trips(self):
        for entry in sinister.entries():
            self.assertLessEqual(len(entry["rows"]), capes.SLOTS, entry["name"])
            picks = [{"key": row["key"], "value": int(row["value"])}
                     for row in entry["rows"]]
            block = skirmish.encode(picks)
            self.assertEqual(len(block), 24)
            self.assertEqual((block[0], block[1]),
                             (capes.AUGMENT_KIND, capes.AUGMENT_SUBKIND))
            decoded = [pick for pick in skirmish.decode_picks(block) if pick]
            self.assertEqual(
                [(pick["key"], pick["value"]) for pick in picks],
                [(pick["key"], pick["value"]) for pick in decoded],
                entry["name"])
            for row in entry["rows"]:
                self.assertIn(row["key"], skirmish.STATS, entry["name"])
                self.assertTrue(sinister.row_text(row), entry["name"])

    def test_the_samnuha_block_matches_the_client_ids(self):
        entry = item_named("Samnuha Tights")
        block = skirmish.encode([{"key": row["key"], "value": row["value"]}
                                 for row in entry["rows"]])
        self.assertEqual(capes.decode(block), [
            {"id": 0x200, "value": 9},   # STR+10 (1 + 9)
            {"id": 0x201, "value": 9},   # DEX+10
            {"id": 0x08F, "value": 2},   # "Dbl.Atk."+3%
            {"id": 0x090, "value": 2},   # "Triple Atk."+3%
            {"id": 0, "value": 0},
        ])
        self.assertEqual(skirmish.describe(block),
                         "STR+10 | DEX+10 | Dbl.Atk.+3% | Triple Atk.+3%")
        self.assertEqual(augment_stats.item_mods(SAMNUHA, block), {
            mod.STR: 10,
            mod.DEX: 10,
            mod.DOUBLE_ATTACK: 3,
            mod.TRIPLE_ATTACK: 3,
        })

    def test_each_group_is_present(self):
        groups = {}
        for entry in sinister.entries():
            groups[entry["group"]] = groups.get(entry["group"], 0) + 1
        self.assertEqual(groups, {
            "Head": 4, "Body": 4, "Hands": 4, "Legs": 5, "Feet": 4, "Weapons": 16,
        })

    def test_the_less_common_rows_use_the_client_ids(self):
        block = skirmish.encode([
            {"key": "divine_skill", "value": 15},
            {"key": "enhancing_skill", "value": 10},
            {"key": "ninjutsu_skill", "value": 10},
            {"key": "th", "value": 1},
            {"key": "pet_racc", "value": 15},
        ])
        self.assertEqual(capes.decode(block), [
            {"id": 0x120, "value": 14},
            {"id": 0x122, "value": 9},
            {"id": 0x127, "value": 9},
            {"id": 0x093, "value": 0},
            {"id": 0x071, "value": 14},
        ])
        self.assertEqual(skirmish.describe(block),
                         "Divine magic skill+15 | Enhancing magic skill+10 | "
                         "Ninjutsu skill+10 | Treasure Hunter+1 | Pet: Rng. Acc.+15")


class SinisterServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]
        self.service.top_off_gil(self.character_id)

    def add(self, item_id: int) -> dict:
        self.service.armory_add(self.character_id, item_id)
        return next(row for row in self.service.inventory(self.character_id)
                    if int(row["item_id"]) == int(item_id))

    def extra(self, row: dict) -> bytes:
        return self.db.one(
            "SELECT extra FROM char_inventory WHERE character_id = ? "
            "AND container = ? AND slot = ?",
            (self.character_id, int(row["container"]), int(row["slot"])))["extra"]

    def test_catalog_lists_the_owned_copy_and_its_max_rows(self):
        row = self.add(SAMNUHA)
        catalog = sinister.catalog(self.service, self.character_id)
        self.assertEqual(catalog["catalog_size"], 37)
        entry = next(item for item in catalog["items"] if item["item_id"] == SAMNUHA)
        self.assertTrue(entry["owned"])
        self.assertEqual(entry["slot_name"], "Legs")
        self.assertEqual([row["text"] for row in entry["rows"]], [
            "STR+10", "DEX+10", "Dbl.Atk.+3%", "Triple Atk.+3%",
        ])
        copy = entry["copies"][0]
        self.assertEqual(copy["container"], row["container"])
        self.assertEqual(copy["slot"], row["slot"])
        self.assertEqual(copy["current"], "not augmented")

    def test_apply_max_and_clear(self):
        row = self.add(SAMNUHA)
        applied = sinister.apply_max(self.service, self.character_id,
                                     row["container"], row["slot"])
        self.assertEqual(applied["augments"], [
            "STR+10", "DEX+10", "Dbl.Atk.+3%", "Triple Atk.+3%",
        ])
        current = self.extra(row)
        self.assertEqual(skirmish.describe(current),
                         "STR+10 | DEX+10 | Dbl.Atk.+3% | Triple Atk.+3%")
        self.assertEqual(augment_stats.item_mods(SAMNUHA, current), {
            mod.STR: 10,
            mod.DEX: 10,
            mod.DOUBLE_ATTACK: 3,
            mod.TRIPLE_ATTACK: 3,
        })

        catalog = sinister.catalog(self.service, self.character_id)
        entry = next(item for item in catalog["items"] if item["item_id"] == SAMNUHA)
        self.assertEqual(entry["copies"][0]["selection"][0], {"key": "str", "value": 10})
        self.assertIn("STR+10", entry["copies"][0]["current"])

        sinister.clear(self.service, self.character_id, row["container"], row["slot"])
        self.assertEqual(skirmish.describe(self.extra(row)), "not augmented")

    def test_apply_rejects_a_piece_without_sinister_rows(self):
        row = self.add(26733)  # Yorium Barbuta, Skirmish only
        with self.assertRaises(ValueError):
            sinister.apply_max(self.service, self.character_id,
                               row["container"], row["slot"])

    def test_apply_rejects_a_missing_slot(self):
        with self.assertRaises(LookupError):
            sinister.apply_max(self.service, self.character_id, 99, 99)


if __name__ == "__main__":
    unittest.main()
