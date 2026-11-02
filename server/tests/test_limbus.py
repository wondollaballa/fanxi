"""The Limbus Rank 30 dataset, its exdata and the migration that stamps it."""

import tempfile
import unittest
from pathlib import Path

from server.fanxi_server.game import augment_gear, augments, limbus

from support import ROOT, make_service
from fanxi_server.db import Database

# The client bundle each piece carries; 472-496 are the five families, in
# head/body/hands/legs/feet order.  Matched to the Rank 30 rows by content.
BUNDLES = {
    24122: 472, 24125: 473, 24128: 474, 24131: 475, 24134: 476,
    24137: 487, 24140: 488, 24143: 489, 24146: 490, 24149: 491,
    24152: 482, 24155: 483, 24158: 484, 24161: 485, 24164: 486,
    24167: 477, 24170: 478, 24173: 479, 24176: 480, 24179: 481,
    24182: 492, 24185: 493, 24188: 494, 24191: 495, 24194: 496,
}


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

    def test_every_piece_carries_its_client_bundle(self):
        for entry in limbus.entries():
            self.assertEqual(entry["bundle"], BUNDLES[entry["id"]], entry["name"])

    def test_exdata_is_rank_30_with_the_curve_b_total(self):
        for entry in limbus.entries():
            build = augments.decode(limbus.extra(entry))
            self.assertIsNotNone(build)
            self.assertEqual(build["rank"], 30, entry["name"])
            self.assertEqual(build["tier"], 3, entry["name"])
            self.assertEqual(build["rp"], 55800, entry["name"])
            self.assertEqual(build["curve"], 1, entry["name"])
            self.assertEqual(build["index"], BUNDLES[entry["id"]], entry["name"])
        self.assertEqual(len(limbus.blocks()), 41)  # 25 armour pieces + 16 weapons


# The client bundle each Telopanos weapon carries.  The augment table's 497-512
# are this family; every one was matched to its Rank 30 rows by content.
WEAPON_BUNDLES = {
    18800: 511, 21549: 497, 21599: 498, 21738: 502, 21795: 503, 21848: 504,
    21899: 505, 21942: 506, 21948: 507, 22176: 510, 22182: 499, 22188: 500,
    22225: 508, 22231: 509, 22237: 501, 26503: 512,
}


class LimbusWeaponTest(unittest.TestCase):
    """The sixteen Telopanos weapons share the armour's Rank 30 block rules."""

    def test_every_weapon_is_listed(self):
        entries = limbus.weapon_entries()
        self.assertEqual(len(entries), 16)
        self.assertEqual({entry["set"] for entry in entries}, {"Telopanos"})
        self.assertEqual(len(limbus.all_entries()), 41)

    def test_ids_are_unique_and_bundles_are_the_client_table(self):
        entries = limbus.weapon_entries()
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in entries:
            self.assertEqual(entry["bundle"], WEAPON_BUNDLES[entry["id"]], entry["name"])

    def test_every_weapon_has_three_or_four_rank_30_rows(self):
        for entry in limbus.weapon_entries():
            rows = entry["paths"]["Rank 30"]
            self.assertGreaterEqual(len(rows), 3, entry["name"])
            self.assertLessEqual(len(rows), 4, entry["name"])

    def test_saber_rows_and_bundle(self):
        saber = limbus.find("telopanos saber")[0]
        self.assertEqual(saber["id"], 22188)
        self.assertEqual(saber["slot"], "main")
        self.assertEqual(saber["bundle"], 500)
        self.assertEqual(saber["paths"]["Rank 30"],
                         ["Damage+18", "Magic Damage+25", "HP+150"])

    def test_shield_grip_and_abbreviated_name(self):
        shield = limbus.find("telopanos shield")[0]
        self.assertEqual((shield["id"], shield["slot"], shield["bundle"]),
                         (26503, "sub", 512))
        self.assertEqual(shield["paths"]["Rank 30"], ["Attack+50", "HP+150", "VIT+30"])
        self.assertEqual(limbus.find("telopanos grip")[0]["id"], 18800)
        self.assertEqual(limbus.find("telopanos shin")[0]["id"], 21942)

    def test_set_search_covers_the_weapons(self):
        self.assertEqual(len(limbus.find("telopanos")), 16)
        self.assertEqual(limbus.get(22188)["name"], "Telopanos Saber")
        self.assertIsNone(limbus.get(999999))

    def test_each_weapon_block_is_rank_30_curve_b(self):
        for entry in limbus.weapon_entries():
            build = augments.decode(limbus.extra(entry))
            self.assertIsNotNone(build)
            self.assertEqual(build["rank"], 30, entry["name"])
            self.assertEqual(build["tier"], 3, entry["name"])
            self.assertEqual(build["rp"], 55800, entry["name"])
            self.assertEqual(build["curve"], 1, entry["name"])
            self.assertEqual(build["index"], WEAPON_BUNDLES[entry["id"]], entry["name"])

    def test_blocks_cover_both_datasets(self):
        blocks = limbus.blocks()
        self.assertEqual(len(blocks), 41)
        self.assertEqual(len(blocks[22188]), 24)
        self.assertEqual(augments.decode(blocks[22188])["index"], 500)

    def test_the_rp_card_registry_lists_them(self):
        registry = augment_gear.entries()
        for item_id, bundle in WEAPON_BUNDLES.items():
            entry = registry[item_id]
            self.assertEqual(entry["kind"], "limbus", item_id)
            self.assertEqual(entry["set"], "Telopanos", item_id)
            self.assertEqual(len(entry["paths"]), 1, item_id)
            path = entry["paths"][0]
            self.assertEqual((path["key"], path["bundle"], path["rank"], path["rp"],
                              path["curve"]), ("A", bundle, 30, 55800, 1), item_id)


class LimbusMigrationTest(unittest.TestCase):
    """Migration 104 re-stamps existing gear and grants the jewel pairs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        _config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.one = int(self.service.create_character(
            account["id"], {"name": "Onedough", "race": 1})["id"])
        self.two = int(self.service.create_character(
            account["id"], {"name": "Twodough", "race": 1})["id"])
        # Migration 99 ran before these characters existed; run it now for the grant.
        self.apply("0099_limbus_r30.sql")
        self.apply("0104_limbus_rp30.sql")

    def apply(self, name: str) -> None:
        with self.db.connection() as conn:
            Database._apply_script(conn, ROOT / "database" / "migrations" / name)
            conn.commit()

    def test_gear_carries_the_rank_30_block(self):
        for character_id in (self.one, self.two):
            for item_id, bundle in BUNDLES.items():
                row = self.db.one(
                    "SELECT extra FROM char_inventory WHERE character_id = ? AND item_id = ?",
                    (character_id, item_id))
                self.assertIsNotNone(row, (character_id, item_id))
                build = augments.decode(bytes(row["extra"]))
                self.assertEqual(build["rank"], 30, item_id)
                self.assertEqual(build["rp"], 55800, item_id)
                self.assertEqual(build["curve"], 1, item_id)
                self.assertEqual(build["index"], bundle, item_id)

    def test_both_characters_get_a_stack_of_each_furnace_item(self):
        for character_id in (self.one, self.two):
            for item_id in range(10001, 10011):
                row = self.db.one(
                    "SELECT quantity FROM char_inventory "
                    "WHERE character_id = ? AND item_id = ?", (character_id, item_id))
                self.assertIsNotNone(row, (character_id, item_id))
                self.assertEqual(int(row["quantity"]), 99, (character_id, item_id))

    def test_jewels_are_ex_and_shards_are_not(self):
        for item_id in range(10001, 10006):
            row = self.db.one("SELECT ex, rare FROM items WHERE item_id = ?", (item_id,))
            self.assertEqual((int(row["ex"]), int(row["rare"])), (1, 0), item_id)
        for item_id in range(10006, 10011):
            row = self.db.one("SELECT ex, rare FROM items WHERE item_id = ?", (item_id,))
            self.assertEqual((int(row["ex"]), int(row["rare"])), (0, 0), item_id)


if __name__ == "__main__":
    unittest.main()
