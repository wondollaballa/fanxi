"""The Odyssey Rank 30 dataset and the !r30 lookup."""

import unittest

from server.fanxi_server.game import odyssey


class OdysseyTest(unittest.TestCase):
    def test_every_odyssey_item_is_present(self):
        entries = odyssey.entries()
        self.assertEqual(len(entries), 27)
        armour = [e for e in entries if e["set"] != "Odyssey weapon"]
        weapons = [e for e in entries if e["set"] == "Odyssey weapon"]
        self.assertEqual(len(armour), 20)
        self.assertEqual(len(weapons), 7)

    def test_nyame_has_four_paths(self):
        helm = odyssey.find("nyame helm")[0]
        self.assertEqual(helm["id"], 23761)
        self.assertEqual(sorted(helm["paths"]), ["A", "B", "C", "D"])
        self.assertIn("Store TP+13", helm["paths"]["A"])
        self.assertIn('"Mag.Atk.Bns."+35', helm["paths"]["C"])

    def test_single_path_sets(self):
        sword = odyssey.find("sakpata's sword")[0]
        self.assertEqual(sword["id"], 21637)
        self.assertEqual(list(sword["paths"]), ["Rank 30"])
        self.assertIn("DMG:+13", sword["paths"]["Rank 30"])
        mask = odyssey.find("gleti's mask")[0]
        self.assertEqual(mask["id"], 23756)

    def test_weapons_are_found_by_name_and_set(self):
        self.assertEqual(odyssey.find("agwu's scythe")[0]["id"], 21832)
        self.assertTrue(all(e["set"] == "Odyssey weapon" for e in odyssey.find("weapon")))
        self.assertEqual(odyssey.find("nope"), [])

    def test_bundles_are_known_for_every_item(self):
        entries = odyssey.entries()
        for entry in entries:
            if entry["bundles"]:
                self.assertEqual(sorted(entry["bundles"]), ["A", "B", "C", "D"])
                self.assertTrue(all(390 <= int(i) <= 460 for i in entry["bundles"].values()))
            else:
                self.assertTrue(390 <= int(entry["bundle"]) <= 460, entry["name"])

    def test_bundle_lookup(self):
        self.assertEqual(odyssey.bundle_for("Nyame Helm", "A"), 438)
        self.assertEqual(odyssey.bundle_for("Nyame Helm", "D"), 453)
        self.assertEqual(odyssey.bundle_for("Sakpata's Helm"), 418)
        self.assertEqual(odyssey.bundle_for("Gleti's Cuirass"), 414)
        self.assertEqual(odyssey.bundle_for("Agwu's Scythe"), 400)
        self.assertEqual(odyssey.bundle_for("Gleti's Crossbow"), 406)

    def test_ids_are_unique(self):
        ids = [entry["id"] for entry in odyssey.entries()]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
