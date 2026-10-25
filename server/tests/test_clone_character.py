"""The character clone must keep the locker's per-copy augment block."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

_spec = importlib.util.spec_from_file_location("clone_character", TOOLS / "clone_character.py")
clone_character = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clone_character)


class CloneLockerTest(unittest.TestCase):
    def test_locker_columns_include_the_augment_block(self):
        self.assertIn("extra", clone_character.CHARACTER_TABLES["char_locker"])

    def test_two_capes_with_different_blocks_both_survive(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute(
            "CREATE TABLE char_locker ("
            " character_id INTEGER NOT NULL, item_id INTEGER NOT NULL,"
            " extra BLOB NOT NULL DEFAULT X'', quantity INTEGER NOT NULL DEFAULT 1,"
            " stored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " PRIMARY KEY (character_id, item_id, extra))")
        # The source has two copies of the same cape, told apart by the 24-byte
        # augment block.  A copy that drops ``extra`` collapses them into one.
        conn.executemany(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity, stored_at)"
            " VALUES (1, 26265, ?, 1, '2026-10-24')",
            [(b"\x02\x03" + bytes(22),), (b"\x02\x03" + b"\x01" + bytes(21),)])
        conn.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity, stored_at)"
            " VALUES (2, 5411, X'', 1, '2026-10-24')")

        columns = clone_character.CHARACTER_TABLES["char_locker"]
        clone_character.copy_table_rows(conn, "char_locker", columns, 1, 2)
        clone_character.verify(conn, "char_locker", columns, 1, 2)
        rows = conn.execute(
            "SELECT item_id, hex(extra) FROM char_locker WHERE character_id = 2"
            " ORDER BY hex(extra)").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[0] for row in rows}, {26265})
        self.assertNotEqual(rows[0][1], rows[1][1])


if __name__ == "__main__":
    unittest.main()
