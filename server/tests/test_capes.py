"""Ambuscade JSE cape augments (standard five-slot extdata)."""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import capes  # noqa: E402


class CapeTest(unittest.TestCase):
    def test_every_build_is_a_five_slot_standard_block(self):
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                block = capes.encode(build, job)
                self.assertEqual(len(block), 24, (job, build))
                self.assertEqual(block[0], 0x02, (job, build))
                self.assertEqual(block[1], 0x03, (job, build))
                self.assertEqual(block[12:], b"\0" * 12, (job, build))

    def test_block_round_trips(self):
        block = capes.encode("tp")
        slots = capes.decode(block)
        self.assertEqual(slots[0], {"id": 0x201, "value": 19})   # DEX+20
        self.assertEqual(slots[1], {"id": 0x044, "value": 19})   # Accuracy+20 Attack+20
        self.assertEqual(slots[2], {"id": 0x017, "value": 9})    # Accuracy+10
        self.assertEqual(slots[3], {"id": 0x08E, "value": 9})    # Store TP+10
        self.assertEqual(slots[4], {"id": 0x036, "value": 9})    # Phys. dmg. taken-10%

    def test_ninja_build_only_ids(self):
        # The NIN-only stats resolve to the same client augment ids the
        # community extdata table uses.
        block = capes.encode("ninjutsu", "NIN")
        slots = capes.decode(block)
        self.assertEqual(slots[0], {"id": 0x204, "value": 19})   # INT+20
        self.assertEqual(slots[2], {"id": 0x204, "value": 9})    # INT+10
        self.assertEqual(slots[3], {"id": 0x085, "value": 9})    # Mag.Atk.Bns.+10
        self.assertEqual(capes.decode(capes.encode("dw", "NIN"))[3],
                         {"id": 0x092, "value": 9})              # Dual Wield+10
        self.assertEqual(capes.decode(capes.encode("fc", "NIN"))[3],
                         {"id": 0x08C, "value": 9})              # Fast Cast+10

    def test_hp_uses_the_offset_block_not_a_wide_value(self):
        # HP+60 is id 2 (offset 33) + value 27, because the value field is 5 bits.
        block = capes.encode("pdt")
        self.assertEqual(block[2:4], (0x002 | (27 << 11)).to_bytes(2, "little"))
        self.assertEqual(capes.decode(block)[0], {"id": 0x002, "value": 27})

    def test_describe_rebuilds_the_gearswap_strings(self):
        for job, entry in capes.JOBS.items():
            for build, names in entry["builds"].items():
                shown = capes.describe(capes.encode(build, job)).split(", ")
                self.assertEqual(len(shown), len(names), (job, build))
                for name, text in zip(names, shown):
                    self.assertEqual(_norm(name), _norm(text), (job, build))

    def test_every_augment_resolves_through_the_display_table(self):
        for name, (augment_id, value) in capes.AUGMENTS.items():
            self.assertIn(augment_id, capes.TABLE, name)
            self.assertNotIn("id ", capes._text(augment_id, value), name)

    def test_job_lookup(self):
        self.assertEqual(capes.job_for_item(26254), "BST")
        self.assertEqual(capes.job_for_item(26258), "NIN")
        self.assertEqual(capes.job_for_item(26253), "DRK")
        self.assertIsNone(capes.job_for_item(1))
        self.assertEqual(capes.job_for_name("Andartia's Mantle"), "NIN")
        self.assertEqual(capes.job_for_name("Artio's Mantle"), "BST")
        self.assertEqual(capes.job_for_name("Ankou's Mantle"), "DRK")

    def test_unknown_build_is_rejected(self):
        with self.assertRaises(ValueError):
            capes.encode("nope")
        with self.assertRaises(ValueError):
            capes.encode("tp", "DRG")

    def test_only_five_bits_of_value(self):
        # All values stay inside the 5-bit field, so the high byte keeps its id bits.
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                for slot in capes.decode(capes.encode(build, job)):
                    self.assertLessEqual(slot["value"], 0x1F)
                    self.assertLessEqual(slot["id"], 0x7FF)

    def test_migrations_and_docs_are_in_sync(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import importlib

        gen = importlib.import_module("gen_capes")
        for job, path in gen.MIGRATIONS.items():
            migration = path.read_text()
            self.assertEqual(gen.sql(job), migration, job)
            # Every build in the migration carries its own block.
            hexes = re.findall(r"X'([0-9A-F]{48})'", migration)
            self.assertEqual(len(hexes), len(capes.JOBS[job]["builds"]), job)
        self.assertEqual(gen.doc(), (ROOT / "docs/capes.md").read_text())


def _norm(text: str) -> str:
    """Compare augment text ignoring quoting and spacing."""
    return re.sub(r"[\s\"]", "", text)


if __name__ == "__main__":
    unittest.main()
