"""Prime weapons in the Armory: one row per family, and always the final form.

The catalogue has four identically named upgraded rows per Prime weapon.  The
Armory used to show all of them, so what looked like a duplicate list was really
stage 2, 3, 4 and 5.  These tests pin the family table to the item data, the
typeahead to the final row, and the purchase path to the final item id.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.db import Database
from fanxi_server.game import prime_weapons
from fanxi_server.service import ApiError

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "0164_prime_weapon_final_forms.sql"
MIGRATION_DEDUPE = ROOT / "database" / "migrations" / "0166_prime_opashoro_single_copy.sql"


class PrimeArmoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register(
            "primeuser", "password123", ip="127.0.0.1").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Prime", "race": 1})["id"]

    def test_the_family_table_matches_the_item_database(self):
        self.assertEqual(len(prime_weapons.PRIME_FAMILIES), 16)
        for family, stages in prime_weapons.PRIME_FAMILIES:
            final_stage, final_id = stages[-1]
            self.assertEqual(final_stage, prime_weapons.PRIME_STAGE_COUNT)
            self.assertEqual(final_id, max(item_id for _stage, item_id in stages))
            final = self.db.one("SELECT name, model FROM items WHERE item_id = ?",
                                (final_id,))
            self.assertIsNotNone(final, family)
            self.assertIn(family, str(final["name"]))
            second = self.db.one("SELECT model FROM items WHERE item_id = ?",
                                 (stages[0][1],))
            self.assertIsNotNone(second, family)
            # The final row is the afterglow model from migration 125.
            self.assertNotEqual(int(final["model"]), int(second["model"]), family)
            for stage, item_id in stages:
                entry = prime_weapons.form(item_id)
                self.assertIsNotNone(entry, item_id)
                self.assertEqual((entry.family, entry.stage, entry.final_id),
                                 (family, stage, final_id))
                row = self.db.one("SELECT name FROM items WHERE item_id = ?",
                                  (item_id,))
                self.assertIsNotNone(row, item_id)
                name = str(row["name"])
                if stage == 1:
                    self.assertTrue(name.startswith("Prime "), (family, name))
                else:
                    self.assertIn(family, name)

    def test_armory_search_returns_one_row_per_prime_family(self):
        cases = {
            "Foenaria": 21837,
            "Prime Scythe": 21837,
            "Prime Fists": 21535,
            "Mpu Gandring": 21590,
            "Caliburnus": 21646,
            "Helheim": 21653,
            "Spalirisos": 21730,
            "Laphria": 21785,
            "Gae Buide": 21891,
            "Dokoku": 21932,
            "Kusanagi": 21986,
            "Lorg Mor": 22002,
            "Opashoro": 22106,
            "Pinaka": 22163,
            "Earp": 22164,
            "Loughnashade": 22307,
            "Duban": 26495,
        }
        for query, final_id in cases.items():
            with self.subTest(query=query):
                rows = self.service.search_items(self.character_id, query)
                self.assertEqual(rows[0]["item_id"], final_id)
                self.assertEqual(
                    [row["item_id"] for row in rows if row.get("prime_final")],
                    [final_id])
                self.assertTrue(rows[0]["prime_final"])
                self.assertEqual(rows[0]["prime_stage"], prime_weapons.PRIME_STAGE_COUNT)
                self.assertEqual(rows[0]["prime_stages"], prime_weapons.PRIME_STAGE_COUNT)

        # The paperdoll filter must not bring the hidden stages back.
        rows = self.service.search_items(self.character_id, "Foenaria", kind="weapon")
        self.assertEqual([row["item_id"] for row in rows], [21837])

        # A normal item is untouched and carries no Prime fields.
        rows = self.service.search_items(self.character_id, "Bronze Sword")
        self.assertEqual(rows[0]["item_id"], 16535)
        self.assertFalse(any("prime_final" in row for row in rows))

    def test_a_prime_purchase_is_always_the_final_form(self):
        # A stage the character already holds blocks buying the family's final, the
        # same way a Rare item blocks a second copy.
        self.service.add_item(self.character_id, 21532)  # Varga stage 2
        rows = self.service.search_items(self.character_id, "Varga Purnikawa")
        self.assertTrue(rows[0]["owned"])
        self.assertEqual(rows[0]["held"], 1)
        with self.assertRaises(ApiError) as ctx:
            self.service.armory_add(self.character_id, 21531)
        self.assertEqual(ctx.exception.code, "already_owned")

        self.service.top_off_gil(self.character_id)
        before = int(self.service.character(self.character_id)["gil"])

        added = self.service.armory_add(self.character_id, 21834)  # stage 2
        self.assertEqual(added["item_id"], 21837)
        self.assertEqual(added["name"], "Foenaria")
        self.assertEqual(added["price"], 283220)
        self.assertEqual(int(self.service.character(self.character_id)["gil"]),
                         before - 283220)

        held = self.db.all(
            "SELECT item_id FROM char_inventory WHERE character_id = ? "
            "AND item_id IN (21834, 21837)", (self.character_id,))
        self.assertEqual([int(row["item_id"]) for row in held], [21837])
        purchase = self.db.one(
            "SELECT item_id FROM char_purchases WHERE character_id = ? "
            "ORDER BY id DESC LIMIT 1", (self.character_id,))
        self.assertEqual(int(purchase["item_id"]), 21837)

        # The stage-1 "Prime ..." row maps to the same family final.
        base = self.service.armory_add(self.character_id, 21781)
        self.assertEqual(base["item_id"], 21785)
        self.assertEqual(base["name"], "Laphria")

        rows = self.service.search_items(self.character_id, "Foenaria")
        self.assertTrue(rows[0]["owned"])
        self.assertEqual(rows[0]["held"], 1)

    def test_the_migration_repairs_existing_stage_copies(self):
        character_id = self.character_id
        # The equipped stage wins over a plain final copy in another bag slot.
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 14, 70, 21834, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 14, 71, 21837, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 0, 14, 70, 21834)", (character_id,))
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 21834, 1, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 21837, 2, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 21834, X'', 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 21837, X'', 4)", (character_id,))
        self.db.execute(
            "INSERT INTO char_purchases (character_id, item_id, quantity, price, created_at) "
            "VALUES (?, 21834, 1, 283220, '2026-01-01T00:00:00Z')", (character_id,))

        with self.db.connection() as conn:
            Database._apply_script(conn, MIGRATION)
            # A second run must be a no-op: the migration stays safe on a database
            # that already applied it.
            Database._apply_script(conn, MIGRATION)

        inventory = [(int(row["slot"]), int(row["item_id"]), int(row["quantity"]))
                     for row in self.db.all(
                         "SELECT slot, item_id, quantity FROM char_inventory "
                         "WHERE character_id = ? AND container = 14 ORDER BY slot",
                         (character_id,))]
        self.assertEqual(inventory, [(70, 21837, 1)])
        equip = self.db.one(
            "SELECT slot, item_id FROM char_equip WHERE character_id = ?",
            (character_id,))
        self.assertEqual((int(equip["slot"]), int(equip["item_id"])), (70, 21837))
        # Storage and the locker yield to the bag copy, as in migration 103.
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_storage WHERE character_id = ?", (character_id,)))
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_locker WHERE character_id = ?", (character_id,)))
        purchases = [int(row["item_id"]) for row in self.db.all(
            "SELECT item_id FROM char_purchases WHERE character_id = ?",
            (character_id,))]
        self.assertEqual(purchases, [21837])

    def test_the_migration_converts_lone_stage_copies(self):
        character_id = self.character_id
        # Two stages in the bags: the higher stage is the one kept.
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 14, 80, 21834, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 14, 81, 21835, 1)", (character_id,))
        # Two stages on a storage slip: the stage-4 Lorg Mor is the one kept.
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 21998, 1, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 22001, 1, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 22103, X'', 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_purchases (character_id, item_id, quantity, price, created_at) "
            "VALUES (?, 21833, 1, 283220, '2026-01-01T00:00:00Z')", (character_id,))

        with self.db.connection() as conn:
            Database._apply_script(conn, MIGRATION)

        inventory = [(int(row["slot"]), int(row["item_id"])) for row in self.db.all(
            "SELECT slot, item_id FROM char_inventory WHERE character_id = ? "
            "AND container = 14 ORDER BY slot", (character_id,))]
        self.assertEqual(inventory, [(81, 21837)])
        self.assertEqual(
            int(self.db.one(
                "SELECT item_id FROM char_storage WHERE character_id = ?",
                (character_id,))["item_id"]),
            22002)
        self.assertEqual(
            int(self.db.one(
                "SELECT item_id FROM char_locker WHERE character_id = ?",
                (character_id,))["item_id"]),
            22106)
        self.assertEqual(
            int(self.db.one(
                "SELECT item_id FROM char_purchases WHERE character_id = ?",
                (character_id,))["item_id"]),
            21837)

    def test_a_converted_opashoro_dup_is_collapsed_to_the_original(self):
        character_id = self.character_id
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 8, 46, 22106, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 10, 21, 22106, 1)", (character_id,))
        with self.db.connection() as conn:
            Database._apply_script(conn, MIGRATION_DEDUPE)
        rows = self.db.all(
            "SELECT container, slot FROM char_inventory WHERE character_id = ? "
            "AND item_id = 22106", (character_id,))
        self.assertEqual([(int(r["container"]), int(r["slot"])) for r in rows], [(10, 21)])

    def test_the_opashoro_bag_copy_wins_over_the_locker_copy(self):
        character_id = self.character_id
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 8, 46, 22106, 1)", (character_id,))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 22106, X'', 1)", (character_id,))
        with self.db.connection() as conn:
            Database._apply_script(conn, MIGRATION_DEDUPE)
        rows = self.db.all(
            "SELECT container, slot FROM char_inventory WHERE character_id = ? "
            "AND item_id = 22106", (character_id,))
        self.assertEqual([(int(r["container"]), int(r["slot"])) for r in rows], [(8, 46)])
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_locker WHERE character_id = ? AND item_id = 22106",
            (character_id,)))


if __name__ == "__main__":
    unittest.main()
