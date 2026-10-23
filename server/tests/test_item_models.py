"""Grap models for visible gear: migration 95, its triggers and the clone repair."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

from support import make_service  # noqa: E402

import item_models  # noqa: E402

ARMOR = ("head", "body", "hands", "legs", "feet")

# Limbus Rank 30, item ids 24122-24194 every third id: the only armour the item model lookup
# deliberately leaves at model 0 (see CHANGELOG.md and docs/limbus-r30.md).
LIMBUS_R30 = {24122 + 3 * index for index in range(25)}


class ItemModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        _config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.character_id = int(self.character["id"])

    def test_known_sets_carry_their_grap_models(self):
        expected = {
            23899: 4168,   # Atrophy Chapeau +4  (Warlock's look)
            23922: 4169,   # Vitiation Chapeau +4 (Duelist's look)
            23424: 4382,   # Lethargy Chappel +3 (Estoqueur's look)
            23907: 4184,   # Hachiya Hatsuburi +4 (Ninja look)
            23761: 4566,   # Nyame Helm
            27410: 20499,  # Hippomenes Socks +1
        }
        for item_id, model in expected.items():
            row = self.db.one("SELECT model FROM items WHERE item_id = ?", (item_id,))
            self.assertIsNotNone(row, item_id)
            self.assertEqual(int(row["model"]), model, item_id)

    def test_every_armour_slot_has_a_model(self):
        """Only the Limbus Rank 30 pieces may be model-less, and only until a model pass.

        That set is written down in CHANGELOG.md and docs/limbus-r30.md; any other armour
        item with no Grap model is a hole in migration 95's lookup.
        """
        rows = self.db.all(
            "SELECT item_id FROM items WHERE equip_slot IN (%s) AND model = 0 ORDER BY item_id"
            % ",".join("?" for _ in ARMOR), ARMOR)
        missing = [int(row["item_id"]) for row in rows]
        self.assertEqual(missing, sorted(LIMBUS_R30))

    def test_a_new_item_is_stamped_from_the_lookup(self):
        self.db.execute("INSERT OR REPLACE INTO item_models (item_id, model) VALUES (99999, 4321)")
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99999, 'Test Helm', 1, 0, 'head', 1, '', 0, 16, 1, 0)")
        row = self.db.one("SELECT model FROM items WHERE item_id = 99999")
        self.assertEqual(int(row["model"]), 4321)

    def test_adding_gear_to_a_bag_or_slot_stamps_its_model(self):
        self.db.execute("INSERT OR REPLACE INTO item_models (item_id, model) VALUES (99998, 4322)")
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99998, 'Test Mail', 1, 0, 'body', 1, '', 0, 32, 1, 0)")
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 99998")
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 0, 79, 99998, 1)", (self.character_id,))
        row = self.db.one("SELECT model FROM items WHERE item_id = 99998")
        self.assertEqual(int(row["model"]), 4322)
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 99998")
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 5, 0, 79, 99998)", (self.character_id,))
        row = self.db.one("SELECT model FROM items WHERE item_id = 99998")
        self.assertEqual(int(row["model"]), 4322)

    def test_repair_fixes_a_broken_row(self):
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 23761")
        with self.db.connection() as conn:
            repaired = item_models.repair(conn)
            conn.commit()
        self.assertEqual(repaired, 1)
        row = self.db.one("SELECT model FROM items WHERE item_id = 23761")
        self.assertEqual(int(row["model"]), 4566)

    def test_missing_reports_worn_gear_without_a_model(self):
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99997, 'Mystery Hat', 1, 0, 'head', 1, '', 0, 16, 1, 0)")
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 4, 0, 78, 99997)", (self.character_id,))
        with self.db.connection() as conn:
            missing = item_models.missing(conn, self.character_id, equipped=True)
        self.assertEqual([item["name"] for item in missing], ["Mystery Hat"])


if __name__ == "__main__":
    unittest.main()
