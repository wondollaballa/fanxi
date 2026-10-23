"""Unity Wanted +1 gear: single-path Rank 15 augment bundles."""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import augments, unity  # noqa: E402


class UnityTest(unittest.TestCase):
    def test_items_are_the_five_the_ninja_library_defines(self):
        self.assertEqual(
            {entry["name"] for entry in unity.ITEMS.values()},
            {"Unmoving Collar +1", "Odnowa Earring +1", "Gelatinous Ring +1",
             "Ghastly Tathlum +1", "Loess Barbuta +1"})

    def test_blocks_are_rank_15_single_path_bundles(self):
        indices = set()
        for item_id, entry in unity.ITEMS.items():
            block = unity.encode(item_id)
            self.assertEqual(len(block), 24, item_id)
            self.assertEqual(block[0], 0x03, item_id)
            self.assertEqual(block[1], 0x83, item_id)
            build = augments.decode(block)
            self.assertEqual(build["path"], "A", item_id)
            self.assertEqual(build["rank"], 15, item_id)
            self.assertEqual(build["tier"], 0, item_id)   # 0 = the 15-rank unlock
            self.assertEqual(build["curve"], 0, item_id)  # Unity uses RP curve A
            self.assertEqual(build["index"], entry["bundle"], item_id)
            self.assertIn("Rank 15 (tier 0, path A), bundle %d" % entry["bundle"],
                          unity.describe(block), item_id)
            indices.add(entry["bundle"])
        self.assertEqual(len(indices), len(unity.ITEMS))

    def test_known_bundle_indices(self):
        self.assertEqual(unity.index_for(27509), 305)   # Unmoving Collar +1
        self.assertEqual(unity.index_for(27549), 367)   # Odnowa Earring +1
        self.assertEqual(unity.index_for(10769), 316)   # Gelatinous Ring +1
        self.assertEqual(unity.index_for(21344), 343)   # Ghastly Tathlum +1
        self.assertEqual(unity.index_for(25636), 376)   # Loess Barbuta +1

    def test_name_lookup_and_unknown_items(self):
        self.assertEqual(unity.find("unmoving")["item_id"], 27509)
        self.assertIsNone(unity.find(""))
        self.assertIsNone(unity.find("not a unity item"))
        with self.assertRaises(ValueError):
            unity.encode(1)

    def test_matches_the_gearswap_library(self):
        lua = (ROOT / "gearswap" / "NIN.lua").read_text().splitlines()
        start = next(i for i, line in enumerate(lua) if line.startswith("local unity = {"))
        block = []
        for line in lua[start + 1:]:
            if line.strip() == "}":
                break
            block.append(line)
        text = "\n".join(block)
        for entry in unity.ITEMS.values():
            self.assertIn('"%s"' % entry["name"], text)
            for augment in entry["augments"]:
                self.assertIn('"%s"' % augment, text)

    def test_migration_and_docs_are_in_sync(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import importlib

        gen = importlib.import_module("gen_unity")
        self.assertEqual(gen.sql(), gen.MIGRATION.read_text())
        self.assertEqual(gen.doc(), gen.DOC.read_text())
        sql = gen.MIGRATION.read_text()
        for item_id, entry in unity.ITEMS.items():
            self.assertIn("item_id = %d" % item_id, sql)
            self.assertIn(unity.encode(item_id).hex().upper(), sql)


if __name__ == "__main__":
    unittest.main()
