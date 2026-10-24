"""Augment blocks feed the stat sheet, not only the client tooltip."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from support import make_service  # noqa: E402

from fanxi_server.game import (  # noqa: E402
    augment_stats, augments, capes, limbus, modifiers as mod, odyssey, unity,
)

REVELATION = (24122, 24125, 24128, 24131, 24134)  # head, body, hands, legs, feet
REVELATION_KINDS = (4, 5, 6, 7, 8)


class AugmentParserTest(unittest.TestCase):
    def test_revelation_double_attack_row(self):
        self.assertEqual(augment_stats.parse_line('"Double Attack"+7%'),
                         {mod.DOUBLE_ATTACK: 7})

    def test_one_line_can_name_several_stats(self):
        self.assertEqual(
            augment_stats.parse_line("Accuracy+30 Ranged Accuracy+30 Mag. Acc+30"),
            {mod.ACC: 30, mod.RACC: 30, mod.MACC: 30})

    def test_slash_shares_the_value(self):
        self.assertEqual(augment_stats.parse_line("DEX/AGI+10"),
                         {mod.DEX: 10, mod.AGI: 10})
        self.assertEqual(augment_stats.parse_line("Acc/Rng. Acc./M. Acc.+30"),
                         {mod.ACC: 30, mod.RACC: 30, mod.MACC: 30})

    def test_damage_taken_is_stored_in_hundredths(self):
        self.assertEqual(augment_stats.parse_line("Damage taken-10%"), {mod.DMG: -1000})
        self.assertEqual(augment_stats.parse_line("Phys. dmg. taken-10%"),
                         {mod.DMGPHYS: -1000})

    def test_physical_damage_limit_is_a_percent(self):
        self.assertEqual(augment_stats.parse_line("Physical Damage Limit+6%"),
                         {mod.DAMAGE_LIMITP: 6})
        self.assertEqual(augment_stats.parse_line("Phys. dmg. limit +5%"),
                         {mod.DAMAGE_LIMITP: 5})

    def test_cape_slot_lines(self):
        self.assertEqual(augment_stats.parse_line("Eva.+20 /Mag. Eva.+20"),
                         {mod.EVA: 20, mod.MEVA: 20})
        self.assertEqual(augment_stats.parse_line("Mag. Acc+20 /Mag. Dmg.+20"),
                         {mod.MACC: 20, mod.MAGIC_DAMAGE: 20})
        self.assertEqual(augment_stats.parse_line("Accuracy+20 Attack+20"),
                         {mod.ACC: 20, mod.ATT: 20})

    def test_all_attributes(self):
        self.assertEqual(augment_stats.parse_line("All Attr.+10"), {
            mod.STR: 10, mod.DEX: 10, mod.VIT: 10, mod.AGI: 10,
            mod.INT: 10, mod.MND: 10, mod.CHR: 10,
        })

    def test_pet_lines_are_not_the_player(self):
        self.assertEqual(augment_stats.parse_line("Pet: Acc./Mag. Acc.+30"), {})

    def test_every_dataset_row_is_modelled_or_listed(self):
        """A new augment line must either parse or be added to UNMODELLED."""
        rows = set()
        for entry in limbus.entries():
            rows.update(entry["paths"]["Rank 30"])
        for entry in odyssey.entries():
            for path_rows in entry["paths"].values():
                rows.update(path_rows or [])
        for entry in unity.ITEMS.values():
            rows.update(entry["augments"])
        for entry in capes.JOBS.values():
            for build in entry["builds"].values():
                rows.update(build)
        for augment_id in capes.TABLE:
            for value in range(0, 32):
                rows.add(capes.slot_text({"id": augment_id, "value": value}))
        rows.update(augment_stats.UNMODELLED_LINES)
        for line in rows:
            if line in augment_stats.UNMODELLED_LINES:
                continue
            for key in augment_stats.keys_in(line):
                self.assertTrue(
                    not key or key in augment_stats.MAPPED or key in augment_stats.UNMODELLED,
                    "unhandled augment line %r (key %r)" % (line, key))


class EquippedAugmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]

    def equip(self, rows):
        """rows: (equip kind, item id, augment block); one inventory copy each."""
        with self.db.transaction() as conn:
            for index, (kind, item_id, block) in enumerate(rows):
                slot = 10 + index
                conn.execute(
                    "INSERT INTO char_inventory "
                    "(character_id, container, slot, item_id, quantity, extra) "
                    "VALUES (?, 0, ?, ?, 1, ?)",
                    (self.character_id, slot, int(item_id), bytes(block or b"")))
                conn.execute(
                    "INSERT INTO char_equip "
                    "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, ?, ?)",
                    (self.character_id, int(kind), slot, int(item_id)))

    def augment_diff(self, rows):
        """The modifiers the blocks add: sheet with blocks minus sheet without."""
        self.equip(rows)
        with_blocks = self.service.equipped_mods(self.character_id)
        with self.db.transaction() as conn:
            conn.execute("UPDATE char_inventory SET extra = X'' WHERE character_id = ?",
                         (self.character_id,))
        without = self.service.equipped_mods(self.character_id)
        return {mod_id: value - without.get(mod_id, 0)
                for mod_id, value in with_blocks.items()
                if value != without.get(mod_id, 0)}

    def test_revelation_rank_30_set_reaches_the_sheet(self):
        rows = [(kind, item_id, limbus.extra(limbus.get(item_id)))
                for kind, item_id in zip(REVELATION_KINDS, REVELATION)]
        diff = self.augment_diff(rows)
        # The five [2] rows are 7/8/6/7/6.
        self.assertEqual(diff[mod.DOUBLE_ATTACK], 34)
        # The five [3] rows are 6/7/5/6/5.
        self.assertEqual(diff[mod.DAMAGE_LIMITP], 29)
        # Every piece carries Accuracy+30 / Ranged Accuracy+30 / Magic Accuracy+30.
        self.assertEqual(diff[mod.ACC], 150)
        self.assertEqual(diff[mod.RACC], 150)
        self.assertEqual(diff[mod.MACC], 150)

    def test_the_equipped_copy_is_the_one_that_counts(self):
        block = limbus.extra(limbus.get(24122))
        with self.db.transaction() as conn:
            # The copy in slot 10 carries the block; the equipped copy in slot 11 does not.
            conn.execute("INSERT INTO char_inventory (character_id, container, slot, item_id, "
                         "quantity, extra) VALUES (?, 0, 10, 24122, 1, ?)",
                         (self.character_id, bytes(block)))
            conn.execute("INSERT INTO char_inventory (character_id, container, slot, item_id, "
                         "quantity, extra) VALUES (?, 0, 11, 24122, 1, X'')",
                         (self.character_id,))
            conn.execute("INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
                         "VALUES (?, 4, 0, 11, 24122)", (self.character_id,))
        mods = self.service.equipped_mods(self.character_id)
        self.assertNotIn(mod.DOUBLE_ATTACK, mods)

    def test_partial_rank_block_adds_nothing(self):
        partial = augments.bundle("A", 25, 2, 472)  # a rank-25 Revelation piece
        self.assertEqual(self.augment_diff([(4, 24122, partial)]), {})

    def test_unity_rank_15_piece(self):
        diff = self.augment_diff([(9, 27509, unity.encode(27509))])
        self.assertEqual(diff, {mod.DEF: 30, mod.HP: 200})

    def test_odyssey_path_picks_its_own_rows(self):
        # Nyame Helm path C: Mag.Atk.Bns.+35, Magic Damage+30, Mag. Acc.+10
        # (the "Magic burst damage II" row is not modelled yet).
        block = augments.bundle("C", 30, 3, 448)
        diff = self.augment_diff([(4, 23761, block)])
        self.assertEqual(diff, {mod.MATT: 35, mod.MAGIC_DAMAGE: 30, mod.MACC: 10})

    def test_cape_build_reaches_the_sheet(self):
        diff = self.augment_diff([(15, 26258, capes.encode("tp", "NIN"))])
        self.assertEqual(diff, {
            mod.DEX: 20, mod.ACC: 30, mod.ATT: 20,
            mod.STORETP: 10, mod.DMGPHYS: -1000,
        })

    def test_item_without_a_block_adds_nothing(self):
        self.assertEqual(self.augment_diff([(4, 24122, b"")]), {})


if __name__ == "__main__":
    unittest.main()
