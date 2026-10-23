"""Character designs: the look byte, variants and the service around them."""
from __future__ import annotations

import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import design
from fanxi_server.game.gateway import character_record
from fanxi_server.service import ApiError


class DesignValuesTest(unittest.TestCase):
    def test_face_and_hair_pack_into_the_client_look_byte(self):
        self.assertEqual(design.encode_face(2, 0), 2)   # Face 2, Hair A
        self.assertEqual(design.encode_face(2, 1), 3)   # Face 2, Hair B
        self.assertEqual(design.encode_face(8, 1), 15)  # Face 8, Hair B
        self.assertEqual(design.decode_face(2), (2, 0))
        self.assertEqual(design.decode_face(3), (2, 1))
        self.assertEqual(design.decode_face(0), (1, 0))

    def test_variants_number_face_then_hair_then_size(self):
        self.assertEqual(design.variant_index(1, 0, 0), 1)
        self.assertEqual(design.variant_index(1, 0, 2), 3)
        self.assertEqual(design.variant_index(1, 1, 0), 4)
        self.assertEqual(design.variant_index(2, 0, 1), 8)   # Face 2 / Hair A / Medium
        self.assertEqual(design.variant_index(8, 1, 2), 48)
        blue = design.design_from_variant("hume", 8)
        self.assertEqual((blue["face"], blue["hair"], blue["size"]), (2, 0, 1))
        self.assertEqual(blue["raw_face"], 2)
        self.assertEqual(design.design_from_variant("mithra", 48)["label"],
                         "Mithra, Face 8, Hair B, Large")

    def test_race_aliases(self):
        self.assertEqual(design.race("hume").id, 1)
        self.assertEqual(design.race("Hume Female").id, 2)
        self.assertEqual(design.race("humef").id, 2)
        self.assertEqual(design.race("taru").id, 5)
        self.assertEqual(design.race("mithra").id, 7)
        self.assertEqual(design.race(8).label, "Galka")
        with self.assertRaises(design.DesignError):
            design.race("moogle")

    def test_legacy_rows_keep_their_appearance(self):
        # Before migration 0093 `face` was the combined look byte: 1 was Face 1
        # Hair B, 2 was Face 2 Hair A.
        legacy_one = design.from_row({"race": 1, "face": 1, "size": 1})
        self.assertEqual((legacy_one["face"], legacy_one["hair"]), (1, 1))
        legacy_two = design.from_row({"race": 1, "face": 2, "size": 1})
        self.assertEqual((legacy_two["face"], legacy_two["hair"]), (2, 0))
        self.assertEqual(legacy_two["raw_face"], 2)

    def test_random_stays_inside_the_named_race(self):
        import random
        blueprint = design.random_design("galka", random.Random(4))
        self.assertEqual(blueprint["race"], 8)
        self.assertIn(blueprint["variant"], range(1, 49))


class DesignMigrationTest(unittest.TestCase):
    def test_migration_splits_the_old_face_column(self):
        path = Path(tempfile.mkdtemp()) / "old.db"
        conn = sqlite3.connect(str(path))
        try:
            conn.execute(
                "CREATE TABLE characters (id INTEGER PRIMARY KEY, race INTEGER, "
                "face INTEGER CHECK (face BETWEEN 1 AND 8), size INTEGER)")
            conn.executemany("INSERT INTO characters (id, race, face, size) VALUES (?, 1, ?, 1)",
                             [(1, 1), (2, 2), (3, 3), (4, 8)])
            script = (Path(__file__).resolve().parents[2]
                      / "database" / "migrations" / "0093_character_design.sql").read_text()
            script = "\n".join(line for line in script.splitlines()
                               if not line.strip().startswith("--"))
            for statement in script.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.commit()
            rows = conn.execute("SELECT id, face, hair FROM characters ORDER BY id").fetchall()
            self.assertEqual(rows, [(1, 1, 1), (2, 2, 0), (3, 2, 1), (4, 5, 0)])
        finally:
            conn.close()


class DesignServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("designer", "correct-horse-battery-9").account
        self.character = self.service.create_character(account["id"], {
            "name": "Designer", "race": 1, "face": 2, "hair": 0, "size": 1,
            "nation": 0, "main_job": 1,
        })

    def test_created_character_reports_face_hair_and_variant(self):
        self.assertEqual(self.character["face"], 2)
        self.assertEqual(self.character["hair"], 0)
        self.assertEqual(self.character["variant"], 8)
        self.assertEqual(self.character["design"]["raw_face"], 2)
        self.assertEqual(self.character["design"]["label"],
                         "Hume male, Face 2, Hair A, Medium")

    def test_save_design_updates_the_row_and_notifies_the_gateway(self):
        calls = []
        self.service.design_listener = lambda character_id, blueprint: calls.append(
            (character_id, blueprint))
        updated = self.service.save_design(self.character["id"], {
            "race": 7, "face": 5, "hair": 1, "size": 2})
        self.assertEqual((updated["race"], updated["face"], updated["hair"], updated["size"]),
                         (7, 5, 1, 2))
        self.assertEqual(updated["variant"], 30)
        self.assertEqual(calls[0][0], self.character["id"])
        self.assertEqual(calls[0][1]["label"], "Mithra, Face 5, Hair B, Large")
        row = self.db.one("SELECT race, face, hair, size FROM characters WHERE id = ?",
                          (self.character["id"],))
        self.assertEqual(tuple(row), (7, 5, 1, 2))

    def test_save_design_can_change_one_field(self):
        updated = self.service.save_design(self.character["id"], {"size": 0})
        self.assertEqual((updated["race"], updated["face"], updated["hair"], updated["size"]),
                         (1, 2, 0, 0))
        self.assertEqual(updated["variant"], 7)

    def test_out_of_range_design_is_rejected(self):
        with self.assertRaises(ApiError) as caught:
            self.service.save_design(self.character["id"], {"face": 9})
        self.assertEqual(caught.exception.status, 422)
        self.assertIn("face", caught.exception.message)

    def test_account_cannot_change_someone_elses_character(self):
        other = self.service.register("other", "another-password-9").account
        with self.assertRaises(ApiError) as caught:
            self.service.save_design_for_account(other["id"], self.character["id"], {"face": 3})
        self.assertEqual(caught.exception.status, 404)

    def test_lobby_record_carries_the_combined_look_byte(self):
        record = character_record({
            **self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"),
            "head": 0, "body": 8, "hands": 8, "legs": 8, "feet": 8,
            "main": 0, "sub": 0, "ranged": 0,
        })
        # 44-byte header + race/main_job/sub_job, then the u16 face field.
        self.assertEqual(struct.unpack_from("<H", record, 48)[0], 2)
        self.assertEqual(record[52], 2)
        self.assertEqual(struct.unpack_from("<H", record, 56)[0], 2)


if __name__ == "__main__":
    unittest.main()
