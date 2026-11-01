"""The Odyssey Rank 30 dataset and the //r30 lookup."""

import unittest

from server.fanxi_server.game import odyssey


class OdysseyTest(unittest.TestCase):
    def test_every_dataset_file_is_present(self):
        """Both datasets ship in the checkout; a missing EXTRA hides the accessories."""
        self.assertEqual(odyssey.missing(), [])
        self.assertEqual(len(odyssey.data()["accessories"]), 10)

    def test_every_odyssey_item_is_present(self):
        entries = odyssey.entries()
        self.assertEqual(len(entries), 60)
        armour = [e for e in entries
                  if e["set"] not in ("Odyssey weapon", "Odyssey accessory")]
        weapons = [e for e in entries if e["set"] == "Odyssey weapon"]
        accessories = [e for e in entries if e["set"] == "Odyssey accessory"]
        self.assertEqual(len(armour), 35)
        self.assertEqual(len(weapons), 15)
        self.assertEqual(len(accessories), 10)

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

    def test_bunzi_set_is_present(self):
        hat = odyssey.find("bunzi's hat")[0]
        self.assertEqual(hat["id"], 23760)
        self.assertEqual(hat["set"], "Bunzi's Attire Set")
        self.assertEqual(hat["bundle"], 433)
        self.assertEqual(hat["paths"]["Rank 30"], [
            "Attack+30 Magic Damage+30", '"Store TP"+8',
            "Accuracy+15 Mag. Acc.+15", "Quadruple Attack +3%",
        ])
        self.assertEqual(odyssey.bundle_for("Bunzi's Hat"), 433)
        self.assertEqual(odyssey.bundle_for("Bunzi's Chopper"), 399)

    def test_odyssey_accessories(self):
        sash = odyssey.find("obstin")[0]
        self.assertEqual(sash["id"], 26363)
        self.assertEqual(sash["set"], "Odyssey accessory")
        self.assertEqual(sash["bundle"], 467)
        self.assertEqual(sash["paths"]["Rank 30"], [
            "Magic Accuracy+15", "Enfb. mag. skill+15", "Enmity-5"])
        self.assertEqual(odyssey.bundle_for("Schere Earring"), 464)

    def test_bundles_are_known_for_every_item(self):
        entries = odyssey.entries()
        for entry in entries:
            if entry["bundles"]:
                self.assertEqual(sorted(entry["bundles"]), ["A", "B", "C", "D"])
                self.assertTrue(all(390 <= int(i) <= 467 for i in entry["bundles"].values()))
            else:
                self.assertTrue(390 <= int(entry["bundle"]) <= 467, entry["name"])

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
