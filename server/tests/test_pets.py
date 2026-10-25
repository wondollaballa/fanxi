"""The pet foundation: specs, models and owner job-point stats."""
from __future__ import annotations

import unittest

from fanxi_server.game import pets
from fanxi_server.game import packets
from fanxi_server.game.entities import ZoneEntity


class PetSpecTest(unittest.TestCase):
    def test_three_launchable_pets_have_models(self):
        for key in ("beast", "wyvern", "automaton"):
            spec = pets.spec(key)
            self.assertIsNotNone(spec, key)
            look = pets.look(spec)
            self.assertEqual(len(look), 20)
            self.assertEqual(int.from_bytes(look[2:4], "little"), spec.model)

    def test_beastmaster_accuracy_row_reaches_the_pet(self):
        spec = pets.spec("beast")
        base = pets.pet_stats(1, 99, spec)["accuracy"]
        bst = pets.pet_stats(9, 99, spec)["accuracy"]
        self.assertEqual(bst, base + 80)

    def test_dragoon_wyvern_hp_row_reaches_the_pet(self):
        spec = pets.spec("wyvern")
        self.assertGreater(pets.pet_stats(14, 99, spec)["hp"],
                           pets.pet_stats(1, 99, spec)["hp"])

    def test_summon_names_map_to_avatars(self):
        for name in ("Carbuncle", "Ifrit", "Shiva", "Fenrir", "Diabolos"):
            key = pets.summon_key(name)
            self.assertIsNotNone(key, name)
            self.assertIsNotNone(pets.spec(key), name)

    def test_summoner_accuracy_row_reaches_the_avatar(self):
        spec = pets.spec("ifrit")
        base = pets.pet_stats(1, 99, spec)["accuracy"]
        smn = pets.pet_stats(15, 99, spec)["accuracy"]
        self.assertEqual(smn, base + 40)

    def test_entity_kind(self):
        self.assertTrue(ZoneEntity(kind="pet", id=1, targid=1, zone=1, name="X").is_pet())

    def test_pet_spawn_uses_the_spawnable_name_and_model(self):
        spec = pets.spec("beast")
        entity = ZoneEntity(kind="pet", id=1, targid=0x700, zone=1, name=spec.name,
                            model=spec.model, look=pets.look(spec), level=99,
                            hp_max=3000, hp=3000, owner_char_id=1, damage_mult=100)
        body = packets.entity_update(entity)
        self.assertEqual(int.from_bytes(body[44:48], "little"), spec.model << 16)
        self.assertEqual(body[52:68].split(b"\0", 1)[0], spec.name.encode("ascii"))
        self.assertEqual(body[36] & 0x44, 0x44)


if __name__ == "__main__":
    unittest.main()
