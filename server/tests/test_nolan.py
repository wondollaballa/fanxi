"""Nolan mezzotint augments (the 3-row Escha block)."""

import pathlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from server.fanxi_server.game import augment_stats, mezzotint  # noqa: E402


def kaykaus_mitra() -> dict:
    return next(item for item in mezzotint.entries()
                if item["name"] == "Kaykaus Mitra +1")


class MezzotintCatalogTest(unittest.TestCase):
    def test_the_whole_nolan_page_is_there(self):
        entries = mezzotint.entries()
        self.assertEqual(len(entries), 183)
        names = {item["name"] for item in entries}
        for name in ("Kaykaus Mitra +1", "Mijin", "Despair Helm",
                     "Souveran Schaller +1", "Kali"):
            self.assertIn(name, names, name)
        for item in entries:
            self.assertEqual(sorted(item["paths"]), ["A", "B", "C", "D"], item["name"])
            for path, rows in item["paths"].items():
                self.assertEqual(len(rows), 3, (item["name"], path))
                for row in rows:
                    self.assertIn(row["key"], mezzotint.STATS, (item["name"], row))

    def test_every_row_has_a_text(self):
        for item in mezzotint.entries():
            for rows in item["paths"].values():
                for row in rows:
                    text = mezzotint.stat_text(row["key"], row["value"])
                    self.assertTrue(text, row)
                    self.assertNotIn("None", text)

    def test_kaykaus_path_values_match_the_wiki(self):
        mitra = kaykaus_mitra()
        self.assertEqual(mitra["item_id"], 25618)
        self.assertEqual(mitra["paths"]["A"], [
            {"key": "mp", "value": 80},
            {"key": "mnd", "value": 12},
            {"key": "macc", "value": 20},
        ])
        self.assertEqual(mitra["paths"]["B"], [
            {"key": "mp", "value": 80},
            {"key": "cure_cast_time", "value": -7},
            {"key": "enmity", "value": -6},
        ])
        self.assertEqual([mezzotint.stat_text(row["key"], row["value"])
                          for row in mitra["paths"]["A"]],
                         ["MP+80", "MND+12", "Mag. Acc.+20"])

    def test_shared_set_paths_repeat_on_every_piece(self):
        mitra = kaykaus_mitra()
        bliaut = next(item for item in mezzotint.entries()
                      if item["name"] == "Kaykaus Bliaut +1")
        for path in "ABC":
            self.assertEqual(mitra["paths"][path], bliaut["paths"][path], path)
        self.assertNotEqual(mitra["paths"]["D"], bliaut["paths"]["D"])


class MezzotintEncodingTest(unittest.TestCase):
    def test_block_layout(self):
        rows = kaykaus_mitra()["paths"]["A"]
        block = mezzotint.encode("A", rows)
        self.assertEqual(len(block), 24)
        self.assertEqual(block[0], 0x02)
        self.assertEqual(block[1], 0x20)
        self.assertEqual(block[2] & 0x03, 0)          # path A
        self.assertEqual((block[2] >> 2) & 0x1F, 15)  # rank 15
        self.assertEqual(struct.unpack_from("<H", block, 4)[0], 0)
        self.assertEqual(block[6], 0x04)              # MP
        self.assertEqual(block[7], 79)                # 80 - 1

    def test_every_catalog_path_round_trips(self):
        for item in mezzotint.entries():
            for path, rows in item["paths"].items():
                decoded = mezzotint.decode(mezzotint.encode(path, rows))
                self.assertIsNotNone(decoded, (item["name"], path))
                self.assertEqual(decoded["path"], path)
                self.assertEqual(decoded["rank"], 15)
                self.assertEqual([(row["key"], row["value"]) for row in decoded["rows"]],
                                 [(row["key"], row["value"]) for row in rows],
                                 (item["name"], path))

    def test_reductions_stay_negative(self):
        block = mezzotint.encode("B", [
            {"key": "mp", "value": 80},
            {"key": "pdt", "value": -4},
            {"key": "enmity", "value": -6},
        ])
        rows = mezzotint.decode(block)["rows"]
        self.assertEqual([(row["key"], row["value"]) for row in rows],
                         [("mp", 80), ("pdt", -4), ("enmity", -6)])
        self.assertEqual(mezzotint.describe(block),
                         "Type B/Rank 15 · MP+80 | Phys. dmg. taken-4% | Enmity-6")

    def test_stat_sheet_reads_the_block(self):
        block = mezzotint.encode("A", kaykaus_mitra()["paths"]["A"])
        mods = augment_stats.item_mods(25618, block)
        self.assertEqual(mods[5], 80)    # MP
        self.assertEqual(mods[13], 12)   # MND
        self.assertEqual(mods[30], 20)   # Magic Accuracy
        self.assertNotEqual(augment_stats.describe_augments(25618, block), "")

    def test_wrong_block_kind_is_not_mezzotint(self):
        self.assertIsNone(mezzotint.decode(bytes.fromhex("0203" + "00" * 22)))
        self.assertIsNone(mezzotint.decode(b""))


class MezzotintServiceTest(unittest.TestCase):
    def setUp(self):
        from support import make_service

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]
        self.service.top_off_gil(self.character_id)

    def _buy(self, item_id: int) -> dict:
        self.service.armory_add(self.character_id, item_id, 1)
        return self.service.character_data(self.character_id)

    def test_catalog_only_lists_owned_copies(self):
        self.assertEqual(self.service.character_data(self.character_id)["nolan"]["items"], [])
        data = self._buy(25618)
        card = data["nolan"]
        self.assertEqual(len(card["items"]), 1)
        item = card["items"][0]
        self.assertEqual(item["name"], "Kaykaus Mitra +1")
        self.assertEqual(len(item["copies"]), 1)
        self.assertIsNone(item["copies"][0]["current"])

    def test_apply_writes_the_rank_fifteen_block(self):
        self._buy(25618)
        data = self.service.character_data(self.character_id)
        copy = data["nolan"]["items"][0]["copies"][0]
        mezzotint.apply(self.service, self.character_id, copy["container"], copy["slot"], "B")
        data = self.service.character_data(self.character_id)
        current = data["nolan"]["items"][0]["copies"][0]["current"]
        self.assertEqual(current["path"], "B")
        self.assertEqual(current["rank"], 15)
        self.assertEqual([(row["key"], row["value"]) for row in current["rows"]],
                         [("mp", 80), ("cure_cast_time", -7), ("enmity", -6)])

    def test_apply_rejects_a_bad_path_and_a_missing_item(self):
        self._buy(25618)
        copy = self.service.character_data(self.character_id)["nolan"]["items"][0]["copies"][0]
        with self.assertRaises(ValueError):
            mezzotint.apply(self.service, self.character_id,
                            copy["container"], copy["slot"], "E")
        with self.assertRaises(LookupError):
            mezzotint.apply(self.service, self.character_id, 0, 250, "A")


if __name__ == "__main__":
    unittest.main()
