"""The generated Call Beast jug catalogue.

The zone server and the in-game HUD read the same data (``data/jug_pets.json`` and
``host/addons/lua/jugpets.lua``), so a mapping error would either spawn the wrong pet
or offer the wrong Ready moves.  The source is LandSandBoat's item_weapon.subskill
(pet id) joined through pet_list/mob_pools/pet_skills.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.game import jugpets  # noqa: E402

LUA = ROOT / "host" / "addons" / "lua" / "jugpets.lua"
MIGRATION = ROOT / "database" / "migrations" / "0070_bst_consumables.sql"


class JugCatalogueTest(unittest.TestCase):
    def test_every_fanxi_jug_has_a_pet_and_a_model(self):
        rows = jugpets.catalogue()
        self.assertGreaterEqual(len(rows), 90)
        for item_id, row in rows.items():
            self.assertGreater(int(row["model"]), 0, row)
            self.assertTrue(row["pet"], row)
            self.assertGreater(int(row["level"]), 0, row)
            self.assertIsInstance(row["moves"], list, row)

    def test_meat_broth_is_the_tiger_familiar_with_its_ready_moves(self):
        row = jugpets.for_item(17870)
        self.assertIsNotNone(row)
        self.assertEqual(row["item"], "Meat Broth")
        self.assertEqual(row["pet"], "Tiger Familiar")
        self.assertEqual(row["model"], 0x0134)
        self.assertEqual(jugpets.spec(row).name, "Tiger Familiar")
        self.assertEqual(jugpets.spec(row).model, 0x0134)
        self.assertEqual(
            jugpets.ready_moves(17870),
            ["Roar", "Razor Fang", "Claw Cyclone", "Crossthrash", "Predatory Glare"])

    def test_pet_name_lookup_is_case_and_space_insensitive(self):
        self.assertEqual(jugpets.for_pet_name("  tiger   familiar ")["item"], "Meat Broth")
        self.assertIsNone(jugpets.for_pet_name("Tiger"))

    def test_the_lua_copy_matches_the_json(self):
        """The HUD's generated module must list the same item ids as the JSON."""
        lua_ids = {int(value) for value in re.findall(r"^\s*\[(\d+)\] =", LUA.read_text(),
                                                      re.MULTILINE)}
        data = json.loads((ROOT / "data" / "jug_pets.json").read_text())
        self.assertEqual(lua_ids, {int(key) for key in data["jugs"]})
        # And every jug the server sells in migration 0070 that has a pet mapping is in it.
        migration = MIGRATION.read_text()
        listed = {int(match) for match in re.findall(
            r"VALUES \((\d+),'[^']*',[^)]*'Call Beast jug\.'", migration)}
        self.assertTrue(listed)
        self.assertEqual(listed, lua_ids)


if __name__ == "__main__":
    unittest.main()
