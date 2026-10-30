"""The mount catalog: every mount the client knows, and how a typed name finds it."""
from __future__ import annotations

import unittest
from pathlib import Path

from fanxi_server.game import mounts

ROOT = Path(__file__).resolve().parents[2]
TSV = ROOT / "tools" / "client_mount_names.tsv"


class MountTableTest(unittest.TestCase):
    def test_matches_the_client_snapshot(self):
        rows = [line.split("\t") for line in TSV.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(len(rows), mounts.count())
        for row in rows:
            mount_id, name, description, japanese = int(row[0]), row[1], row[2], row[3]
            mount = mounts.by_id(mount_id)
            self.assertIsNotNone(mount, "missing mount %d" % mount_id)
            self.assertEqual(mount.id, mount_id)
            self.assertEqual(mount.name, name)
            self.assertEqual(mount.description, description)
            self.assertEqual(mount.japanese, japanese)

    def test_ids_are_dense_and_in_order(self):
        self.assertEqual([m.id for m in mounts.all_mounts()], list(range(mounts.count())))
        self.assertTrue(all(m.name for m in mounts.all_mounts()))
        self.assertGreaterEqual(mounts.count(), 30)

    def test_the_first_and_last(self):
        self.assertEqual(mounts.by_id(0).name, "Chocobo")
        self.assertEqual(mounts.by_id(mounts.count() - 1).name, "Bubble Crab")
        self.assertIsNone(mounts.by_id(mounts.count()))
        self.assertIsNone(mounts.by_id(-1))


class BitfieldTest(unittest.TestCase):
    def test_every_mount_unlocked(self):
        bits = mounts.bitfield()
        self.assertEqual(len(bits), 8)
        for mount in mounts.all_mounts():
            self.assertTrue(bits[mount.id // 8] >> (mount.id % 8) & 1, mount.name)
        # 37 mounts: four full bytes and the low five bits of the fifth.
        self.assertEqual(bits, b"\xff\xff\xff\xff\x7f\x00\x00\x00")

    def test_a_subset(self):
        self.assertEqual(mounts.bitfield([]), bytes(8))
        self.assertEqual(mounts.bitfield([0]), b"\x01" + bytes(7))
        self.assertEqual(mounts.bitfield([1, 9]), b"\x02\x02" + bytes(6))
        # A stray id is dropped rather than shifting another mount's bit.
        self.assertEqual(mounts.bitfield([99, -2]), bytes(8))


class FindTest(unittest.TestCase):
    def test_by_name_in_any_case(self):
        self.assertEqual(mounts.find("raptor")[0].id, 1)
        self.assertEqual(mounts.find("RAPTOR")[0].id, 1)
        self.assertEqual(mounts.find("  Red   Crab ")[0].id, 4)
        self.assertEqual(mounts.find("magic pot")[0].id, 12)
        self.assertEqual(mounts.find("magic_pot")[0].id, 12)

    def test_by_id(self):
        self.assertEqual(mounts.find("0")[0].id, 0)
        self.assertEqual(mounts.find("1")[0].id, 1)
        self.assertEqual(mounts.find("0x24")[0].id, 0x24)
        self.assertEqual(mounts.find("36")[0].id, 36)
        self.assertEqual(mounts.find("38")[0].id, 38)
        mount, error = mounts.find("39")
        self.assertIsNone(mount)
        self.assertIn("0-%d" % (mounts.count() - 1), error)

    def test_aliases_and_item_spellings(self):
        self.assertEqual(mounts.find("choco")[0].id, 0)
        self.assertEqual(mounts.find("pot")[0].id, 12)
        self.assertEqual(mounts.find("chair")[0].id, 17)
        self.assertEqual(mounts.find("craklaw")[0].id, 36)
        self.assertEqual(mounts.find("Cracklaw")[0].id, 36)
        # The key items are named "<Name> Mount".
        self.assertEqual(mounts.find("Raptor Mount")[0].id, 1)
        self.assertEqual(mounts.find("\u266a Raptor")[0].id, 1)

    def test_prefixes(self):
        self.assertEqual(mounts.find("hip")[0].id, 16)
        self.assertEqual(mounts.find("spectral")[0].id, 17)

    def test_ambiguous_prefix_names_them(self):
        mount, error = mounts.find("red")
        self.assertIsNone(mount)
        self.assertIn("Red Crab", error)
        self.assertIn("Red Raptor", error)

    def test_unknown(self):
        mount, error = mounts.find("unicorn")
        self.assertIsNone(mount)
        self.assertIn("no mount", error)
        self.assertIsNone(mounts.find("")[0])

    def test_chocobo_index(self):
        self.assertEqual(mounts.by_id(0).chocobo_index(), 1)
        self.assertEqual(mounts.by_id(33).chocobo_index(), 4)  # Noble Chocobo
        for mount in mounts.all_mounts():
            if mount.id not in (0, 33):
                self.assertEqual(mount.chocobo_index(), 0, mount.name)
        self.assertTrue(mounts.is_chocobo(0))
        self.assertFalse(mounts.is_chocobo(33))


if __name__ == "__main__":
    unittest.main()
