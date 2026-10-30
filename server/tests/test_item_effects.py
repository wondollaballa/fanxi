"""The Hoxne Earring's All BP is read from the character's Mastery Rank.

The item has no ``item_mods`` rows: its seven attribute bonuses come from the Profile
Mastery Rank byte and have to reach both the aggregate outfit query (combat) and the
per-slot query (the launcher's checkparam report).
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import item_effects, modifiers as mod
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

EAR_KIND = 11
ALL_STATS = (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR)


class HoxneRankTableTest(unittest.TestCase):
    def test_all_ten_ranks_match_the_item_table(self):
        expected = {1: -30, 2: -20, 3: -10, 4: 0, 5: 5, 6: 10, 7: 15, 8: 20,
                    9: 25, 10: 30}
        for rank, value in expected.items():
            self.assertEqual(item_effects.hoxne_all_stats(rank), value, rank)

    def test_out_of_range_ranks_use_the_item_floor_and_cap(self):
        self.assertEqual(item_effects.hoxne_all_stats(0), -30)
        self.assertEqual(item_effects.hoxne_all_stats(11), 30)
        self.assertEqual(item_effects.hoxne_all_stats(99), 30)
        self.assertEqual(item_effects.hoxne_all_stats(-4), -30)

    def test_only_the_earring_has_a_dynamic_effect(self):
        self.assertEqual(item_effects.item_mods(26120, 10),
                         {mod_id: 30 for mod_id in ALL_STATS})
        self.assertEqual(item_effects.item_mods(26120, 4), {})
        self.assertEqual(item_effects.item_mods(26119, 10), {})


class HoxneEarringEquipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("earring", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Wearer", "race": 1})
        self.service.add_item(int(self.character["id"]), item_effects.HOXNE_EARRING)
        held = self.db.one(
            "SELECT container, slot FROM char_inventory "
            "WHERE character_id = ? AND item_id = ? ORDER BY slot LIMIT 1",
            (int(self.character["id"]), item_effects.HOXNE_EARRING))
        self.assertIsNotNone(held)
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, ?, ?, ?, ?)",
                (int(self.character["id"]), EAR_KIND, int(held["container"]),
                 int(held["slot"]), item_effects.HOXNE_EARRING))

    def set_rank(self, rank: int) -> None:
        self.service.set_mastery_rank(int(self.character["id"]), rank)

    def assert_all_stats(self, mods: dict[int, int], value: int) -> None:
        for mod_id in ALL_STATS:
            self.assertEqual(mods.get(mod_id, 0), value, mod_id)

    def test_rank_ten_adds_thirty_to_every_attribute(self):
        self.set_rank(10)
        character_id = int(self.character["id"])
        self.assert_all_stats(self.service.equipped_mods(character_id), 30)
        self.assert_all_stats(
            self.service.equipped_item_mods(character_id, item_effects.HOXNE_EARRING), 30)
        rows = self.service.equipped_slot_mods(character_id)
        ear = next(row for row in rows if row["kind"] == EAR_KIND)
        self.assert_all_stats(ear["mods"], 30)

    def test_rank_four_is_neutral_and_rank_one_is_the_penalty(self):
        character_id = int(self.character["id"])
        self.set_rank(4)
        self.assert_all_stats(self.service.equipped_mods(character_id), 0)
        self.set_rank(1)
        self.assert_all_stats(self.service.equipped_mods(character_id), -30)
        self.set_rank(5)
        self.assert_all_stats(self.service.equipped_mods(character_id), 5)

    def test_inventory_copy_alone_does_not_grant_the_bonus(self):
        self.set_rank(10)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM char_equip WHERE character_id = ?",
                         (int(self.character["id"]),))
        mods = self.service.equipped_mods(int(self.character["id"]))
        self.assertTrue(all(mods.get(mod_id, 0) == 0 for mod_id in ALL_STATS))

    def test_gear_rows_and_aggregate_query_agree(self):
        self.set_rank(10)
        character_id = int(self.character["id"])
        merged: dict[int, int] = {}
        for row in self.service.equipped_slot_mods(character_id):
            for mod_id, value in row["mods"].items():
                merged[int(mod_id)] = merged.get(int(mod_id), 0) + int(value)
        self.assertEqual(merged, self.service.equipped_mods(character_id))

    def test_char_stats_sends_the_adjustment_to_the_client(self):
        self.set_rank(10)
        self.world = World(self.config, self.service, None)
        self.service.attach_world(self.world)
        session = ZoneSession(
            self.world, ("127.0.0.1", 41234),
            self.service.character_record(self.service.character(self.character["id"]),
                                          "Fanxi"))
        session.set_key(bytes(20))
        session.logged_in = True
        session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        packet = session.char_stats()
        base = struct.unpack_from("<7H", packet, 4 + 0x10)
        adjustment = struct.unpack_from("<7h", packet, 4 + 0x1E)
        self.assertEqual(base, tuple(session.stat_sheet().base_attributes[name]
                                     for name in ("str", "dex", "vit", "agi",
                                                  "int", "mnd", "chr")))
        self.assertEqual(adjustment, (30, 30, 30, 30, 30, 30, 30))


if __name__ == "__main__":
    unittest.main()
