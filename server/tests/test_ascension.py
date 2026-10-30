"""Shantotto's Ascension: the shared option table and the Phantom Roll block."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

import support  # noqa: F401  (puts server/ on sys.path)

from support import make_service

from fanxi_server.game import ascension, augment_stats, capes, modifiers as mod
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


class AscensionTest(unittest.TestCase):
    def test_catalogue_has_all_three_items_and_33_rows(self):
        self.assertEqual(len(ascension.ITEMS), 3)
        self.assertEqual({item["item_id"] for item in ascension.ITEMS},
                         {16369, 16370, 16371})
        self.assertEqual(len(ascension.OPTIONS), 33)
        keys = [option["key"] for option in ascension.OPTIONS]
        self.assertEqual(len(keys), len(set(keys)))
        for option in ascension.OPTIONS:
            self.assertTrue(option["label"])
            self.assertTrue(capes.slot_text({"id": option["slots"][0][0],
                                             "value": option["slots"][0][1]}))

    def test_phantom_roll_is_a_five_second_recast_reduction(self):
        block = ascension.block_for(["phantom_roll_5"])
        self.assertEqual(len(block), 24)
        self.assertEqual(ascension.current_keys(block), ["phantom_roll_5"])
        self.assertIn("Phantom Roll", capes.describe(block))
        self.assertEqual(augment_stats.item_mods(16370, block),
                         {mod.PHANTOM_ROLL: 5})

    def test_the_same_row_cannot_be_chosen_twice(self):
        with self.assertRaises(ValueError):
            ascension.block_for(["phantom_roll_5", "phantom_roll_5"])
        with self.assertRaises(ValueError):
            ascension.block_for(["not-a-row"])

    def test_a_clear_block_has_no_augments(self):
        self.assertEqual(ascension.block_for([]), b"")
        self.assertEqual(ascension.current_keys(b""), [])

    def test_phantom_roll_recast_drops_from_sixty_to_fifty_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _db, service = make_service(Path(tmp))
            account = service.register("tester", "password123").account
            character = service.create_character(
                account["id"], {"name": "Corsair", "race": 1, "main_job": 17,
                                "main_level": 99})
            cid = int(character["id"])
            service.add_item(cid, 16370)
            copy = next(row for row in service.inventory(cid) if row["item_id"] == 16370)
            service.apply_ascension(cid, copy["container"], copy["slot"],
                                    ["phantom_roll_5"])
            service.save_equipment(cid, {7: (copy["container"], copy["slot"], 16370)})
            self.assertEqual(service.equipped_mods(cid).get(mod.PHANTOM_ROLL), 5)

            world = World(config, service, None)
            session = ZoneSession(
                world, None,
                service.character_record(service.character(cid), "Fanxi"))
            session.set_key(bytes(20))
            session.logged_in = True
            session.zone = 246
            session.pos = list(world.zones.position(246))
            session.load_zone_entities()
            session.zone_loaded = True
            session.queue.clear()
            packet = bytearray(16)
            struct.pack_into("<I", packet, 12, 97)   # Phantom Roll
            session.job_ability(bytes(packet))
            self.assertAlmostEqual(session.ability_recasts[193] - time.time(), 55.0,
                                   delta=2.0)


if __name__ == "__main__":
    unittest.main()
