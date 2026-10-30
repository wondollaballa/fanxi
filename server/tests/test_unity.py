"""Unity Wanted +1 gear: single-path Rank 15 augment bundles."""

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import augments, unity  # noqa: E402

# The five Unity pieces the shared GearSwap table carries (see gearswap/MNK.lua).
NIN_ITEMS = {27509, 27549, 10769, 21344, 25636}

# Every Unity accessory, including the four waist pieces.
UNITY_ACCESSORIES = {
    "Acuity Belt +1", "Apeile Ring +1", "Arete del Luna +1", "Aurist's Cape +1",
    "Bathy Choker +1", "Cacoethic Ring +1", "Canto Necklace +1", "Domin. Earring +1",
    "Fi Follet Cape +1", "Gelatinous Ring +1", "Ghastly Tathlum +1",
    "Ground. Mantle +1", "Handler's Earring +1", "Kentarch Belt +1",
    "Loricate Torque +1", "Lugra Earring +1", "Mephitas's Ring +1",
    "Metamorph Ring +1", "Nourishing Earring +1", "Odnowa Earring +1",
    "Sailfi Belt +1", "Seeth. Bomblet +1", "Shinjutsu-no-Obi +1",
    "Unmoving Collar +1", "Vim Torque +1", "Warder's Charm +1", "Zwazo Earring +1",
}


class UnityTest(unittest.TestCase):
    def test_items_include_the_original_ninja_unity_pieces(self):
        names = {entry["name"] for entry in unity.ITEMS.values()}
        self.assertTrue(
            {"Unmoving Collar +1", "Odnowa Earring +1", "Gelatinous Ring +1",
             "Ghastly Tathlum +1", "Loess Barbuta +1"} <= names)

    def test_unity_accessory_catalogue_is_registered(self):
        """An accessory missing from this registry never reaches the RP card."""
        names = {entry["name"] for entry in unity.ITEMS.values()}
        self.assertTrue(UNITY_ACCESSORIES <= names)

    def test_unity_armour_piece_is_registered(self):
        """Blistering Sallet +1 is Unity armour, not an accessory, and was missing from the
        RP card because the registry only carried accessories (plus Loess Barbuta +1)."""
        entry = unity.get(25602)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Blistering Sallet +1")
        self.assertEqual(entry["slot"], "head")
        self.assertEqual(entry["bundle"], 359)
        self.assertEqual(entry["augments"], [
            "Accuracy/Magic Accuracy +45",
            "Critical Hit Rate +10%",
            "STR/DEX +25",
        ])
        self.assertEqual(unity.index_for(25602), 359)
        self.assertEqual(unity.find("blistering")["item_id"], 25602)

    def test_unity_grip_piece_is_registered(self):
        """Rigorous Grip +1 is Unity gear too; grips take the same Rank 15 path."""
        entry = unity.get(21419)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Rigorous Grip +1")
        self.assertEqual(entry["slot"], "sub")
        self.assertEqual(entry["bundle"], 327)
        self.assertEqual(entry["augments"], ["Attack +30", "STR +15"])
        self.assertEqual(unity.index_for(21419), 327)
        self.assertEqual(unity.find("rigorous")["item_id"], 21419)

    def test_kentarch_belt_is_the_unity_waist_piece(self):
        entry = unity.get(28413)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Kentarch Belt +1")
        self.assertEqual(entry["slot"], "waist")
        self.assertEqual(entry["bundle"], 355)
        self.assertEqual(entry["augments"], ["STR+10", "DEX+10"])
        self.assertEqual(unity.index_for(28413), 355)
        self.assertEqual(unity.find("kentarch")["item_id"], 28413)

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

    def test_every_unity_belt_has_its_bundle(self):
        belts = {
            28430: ("Acuity Belt +1", 295),
            28413: ("Kentarch Belt +1", 355),
            28428: ("Sailfi Belt +1", 292),
            28424: ("Shinjutsu-no-Obi +1", 294),
        }
        for item_id, (name, bundle) in belts.items():
            entry = unity.get(item_id)
            self.assertIsNotNone(entry, item_id)
            self.assertEqual(entry["name"], name)
            self.assertEqual(entry["bundle"], bundle)

    def test_known_bundle_indices(self):
        self.assertEqual(unity.index_for(27509), 305)   # Unmoving Collar +1
        self.assertEqual(unity.index_for(27549), 367)   # Odnowa Earring +1
        self.assertEqual(unity.index_for(10769), 316)   # Gelatinous Ring +1
        self.assertEqual(unity.index_for(21344), 343)   # Ghastly Tathlum +1
        self.assertEqual(unity.index_for(25636), 376)   # Loess Barbuta +1
        self.assertEqual(unity.index_for(25602), 359)   # Blistering Sallet +1
        self.assertEqual(unity.index_for(21419), 327)   # Rigorous Grip +1
        self.assertEqual(unity.index_for(28413), 355)   # Kentarch Belt +1
        self.assertEqual(unity.index_for(28428), 292)   # Sailfi Belt +1
        self.assertEqual(unity.index_for(27561), 310)   # Apeile Ring +1
        self.assertEqual(unity.index_for(10771), 358)   # Cacoethic Ring +1
        self.assertEqual(unity.index_for(27559), 337)   # Mephitas's Ring +1

    def test_name_lookup_and_unknown_items(self):
        self.assertEqual(unity.find("unmoving")["item_id"], 27509)
        self.assertIsNone(unity.find(""))
        self.assertIsNone(unity.find("not a unity item"))
        with self.assertRaises(ValueError):
            unity.encode(1)

    def test_matches_the_shared_gearswap_unity_table(self):
        # NIN.lua no longer carries the shared `local unity` block; MNK.lua is a
        # pristine library that still does, so check the registry against it.
        lua = (ROOT / "gearswap" / "MNK.lua").read_text().splitlines()
        start = next(i for i, line in enumerate(lua) if line.startswith("local unity = {"))
        block = []
        for line in lua[start + 1:]:
            if line.strip() == "}":
                break
            block.append(line)
        text = "\n".join(block)
        for item_id in NIN_ITEMS:
            entry = unity.get(item_id)
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
