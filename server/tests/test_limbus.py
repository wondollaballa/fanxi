"""The Limbus Rank 30 dataset and the !r30 lookup."""

import unittest

from server.fanxi_server.game import limbus


class LimbusTest(unittest.TestCase):
    def test_only_the_top_tier_is_listed(self):
        entries = limbus.entries()
        self.assertEqual(len(entries), 25)
        self.assertEqual({entry["set"] for entry in entries}, {
            "Duty Armor Set", "Revelation Armor Set", "Sworn Armor Set",
            "Indomitable Attire Set", "Clemency Armor Set"})

    def test_ids_are_unique(self):
        ids = [entry["id"] for entry in limbus.entries()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_piece_has_at_least_three_rank_30_rows(self):
        for entry in limbus.entries():
            rows = entry["paths"]["Rank 30"]
            self.assertGreaterEqual(len(rows), 3, entry["name"])
            self.assertLessEqual(len(rows), 4, entry["name"])

    def test_duty_crown(self):
        crown = limbus.find("duty crown")[0]
        self.assertEqual(crown["id"], 24167)
        self.assertEqual(crown["slot"], "head")
        self.assertEqual(crown["set"], "Duty Armor Set")
        self.assertEqual(crown["paths"]["Rank 30"][0], "Accuracy+30 Mag. Acc+30")
        self.assertEqual(crown["paths"]["Rank 30"][2], '"Triple Attack"+4%')

    def test_abbreviated_in_game_names(self):
        self.assertEqual(limbus.find("revelation plate")[0]["id"], 24125)
        self.assertEqual(limbus.find("clemen. hara")[0]["id"], 24185)
        self.assertEqual(limbus.find("indom. petasos")[0]["id"], 24152)

    def test_set_search_and_misses(self):
        self.assertEqual(len(limbus.find("duty armor")), 5)
        self.assertEqual(len(limbus.find("clemency armor")), 5)
        self.assertEqual(limbus.find("nope"), [])


if __name__ == "__main__":
    unittest.main()
