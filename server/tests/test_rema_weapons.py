"""REMA weapons in the Armory: one row per family, and always the final form.

The catalogue stores every Relic, Empyrean, Mythic and Aeonic stage as a separate
row with the same name, so searching Masamune listed nine rows.  These tests pin
the family table to the item data, the typeahead to the final afterglow row, and
the purchase path to the final item id.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import prime_weapons, rema_weapons
from fanxi_server.service import ApiError

ROOT = Path(__file__).resolve().parents[2]


class RemaArmoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register(
            "remauser", "password123", ip="127.0.0.1").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Rema", "race": 1})["id"]

    def test_the_family_table_matches_the_item_database(self):
        self.assertEqual(len(rema_weapons.REMA_FAMILIES), 56)
        seen: set[int] = set()
        no_item_level = {"Aegis", "Ochain", "Gjallarhorn", "Daurdabla"}
        for family, final_id, item_ids in rema_weapons.REMA_FAMILIES:
            self.assertEqual(final_id, item_ids[-1], family)
            self.assertNotIn(final_id, seen, family)
            final = self.db.one(
                "SELECT i.name, i.level, i.item_level, i.model, w.ilvl_skill "
                "FROM items i LEFT JOIN item_weapon w ON w.item_id = i.item_id "
                "WHERE i.item_id = ?", (final_id,))
            self.assertIsNotNone(final, family)
            self.assertTrue(str(final["name"]).startswith(family), family)
            # The four shields/horns have no iLvl 119 row in this catalogue; every
            # weapon family ends on the 269 skill form with an afterglow model.
            if family in no_item_level:
                self.assertEqual((int(final["level"]), int(final["item_level"])),
                                 (99, 0), family)
            else:
                self.assertEqual(int(final["item_level"]), 119, family)
                self.assertEqual(int(final["ilvl_skill"] or 0), 269, family)
                base = self.db.one(
                    "SELECT model FROM items WHERE item_id = ?", (item_ids[0],))
                self.assertIsNotNone(base, (family, item_ids[0]))
                # The final form wears the afterglow model.  Fail-Not is Aeonic and
                # has only one look, so it is the one exception.
                if family != "Fail-Not":
                    self.assertNotEqual(int(final["model"]), int(base["model"]), family)
            for item_id in item_ids:
                self.assertNotIn(item_id, seen, item_id)
                row = self.db.one("SELECT name FROM items WHERE item_id = ?", (item_id,))
                self.assertIsNotNone(row, item_id)
                self.assertTrue(str(row["name"]).startswith(family), (family, item_id))
                entry = rema_weapons.form(item_id)
                self.assertIsNotNone(entry, item_id)
                self.assertEqual((entry.family, entry.final_id), (family, final_id))
                # A Prime id never belongs to a REMA family.
                self.assertIsNone(prime_weapons.form(item_id), item_id)
                seen.add(item_id)

    def test_armory_search_returns_one_row_per_rema_family(self):
        cases = {
            "Masamune": 21956,
            "Excalibur": 20685,
            "Kikoku": 21906,
            "Kikoku 119 III": 21906,
            "Kannagi": 21908,
            "Tupsimati": 22061,
            "Hvergelmir": 22064,
            "Amanomurakumo": 21954,
            "Aegis": 16200,
            "Gjallarhorn": 18840,
            "Daurdabla": 18839,
        }
        for query, final_id in cases.items():
            with self.subTest(query=query):
                rows = self.service.search_items(self.character_id, query)
                self.assertEqual(rows[0]["item_id"], final_id)
                self.assertTrue(rows[0]["rema_final"])
                self.assertFalse(rows[0].get("prime_final", False))
                self.assertEqual(
                    [row["item_id"] for row in rows
                     if row.get("rema_final") and row["name"] == rows[0]["name"]],
                    [final_id])

        # Fudo Masamune is a different weapon (Aeonic great katana), not a stage of
        # Masamune, so the search still offers it as its own row.
        rows = self.service.search_items(self.character_id, "Masamune")
        self.assertEqual([row["item_id"] for row in rows
                          if row["name"] == "Masamune"], [21956])
        self.assertIn(21917, [row["item_id"] for row in rows])  # Fudo Masamune

        # The paperdoll filter must not bring the hidden stages back.
        rows = self.service.search_items(self.character_id, "Masamune", kind="weapon")
        self.assertEqual([row["item_id"] for row in rows
                          if row["name"] == "Masamune"], [21956])

        # Prime handling is untouched, and a normal item has no REMA fields.
        rows = self.service.search_items(self.character_id, "Foenaria")
        self.assertEqual(rows[0]["item_id"], 21837)
        self.assertTrue(rows[0]["prime_final"])
        self.assertFalse(rows[0].get("rema_final", False))

        rows = self.service.search_items(self.character_id, "Bronze Sword")
        self.assertEqual(rows[0]["item_id"], 16535)
        self.assertFalse(any("rema_final" in row for row in rows))

    def test_a_rema_purchase_is_always_the_final_form(self):
        self.service.top_off_gil(self.character_id)
        before = int(self.service.character(self.character_id)["gil"])

        added = self.service.armory_add(self.character_id, 19406)  # Masamune 80
        self.assertEqual(added["item_id"], 21956)
        self.assertEqual(added["name"], "Masamune")
        self.assertEqual(added["price"], 283220)
        self.assertEqual(int(self.service.character(self.character_id)["gil"]),
                         before - 283220)

        held = self.db.all(
            "SELECT item_id FROM char_inventory WHERE character_id = ? "
            "AND item_id IN (19406, 21956)", (self.character_id,))
        self.assertEqual([int(row["item_id"]) for row in held], [21956])
        purchase = self.db.one(
            "SELECT item_id FROM char_purchases WHERE character_id = ? "
            "ORDER BY id DESC LIMIT 1", (self.character_id,))
        self.assertEqual(int(purchase["item_id"]), 21956)

        rows = self.service.search_items(self.character_id, "Masamune")
        self.assertTrue(rows[0]["owned"])
        self.assertEqual(rows[0]["held"], 1)

        # Holding an earlier stage blocks the final until the copy is removed.
        self.service.add_item(self.character_id, 21019)  # Masamune iLvl 119
        with self.assertRaises(ApiError) as ctx:
            self.service.armory_add(self.character_id, 21956)
        self.assertEqual(ctx.exception.code, "already_owned")

    def test_a_rema_purchase_records_the_final_in_history(self):
        self.service.top_off_gil(self.character_id)
        self.service.armory_add(self.character_id, 18312)  # Kikoku 75
        data = self.service.character_data(self.character_id)
        purchase = data["purchases"][0]
        self.assertEqual(purchase["item_id"], 21906)
        self.assertTrue(purchase["rema_final"])
        self.assertEqual(purchase["rema_family"], "Kikoku")


if __name__ == "__main__":
    unittest.main()
