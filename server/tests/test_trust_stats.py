"""Trust HP/MP follow the race, job, subjob and level in the retail base tables."""
from __future__ import annotations

import unittest

import support  # noqa: F401  (puts server/ on sys.path)

from fanxi_server.game import trust_stats
from fanxi_server.game.entities import trust_from_row


class TrustStatsTest(unittest.TestCase):
    def test_species_selects_the_player_race(self):
        self.assertEqual(trust_stats.race_for_species(293), 3)   # Elvaan
        self.assertEqual(trust_stats.race_for_species(294), 8)   # Galka
        self.assertEqual(trust_stats.race_for_species(295), 1)   # Hume
        self.assertEqual(trust_stats.race_for_species(296), 7)   # Mithra
        self.assertEqual(trust_stats.race_for_species(297), 5)   # Tarutaru
        # A Moogle, beast or unknown/imported-zero row falls back to Hume.
        self.assertEqual(trust_stats.race_for_species(138), 1)
        self.assertEqual(trust_stats.race_for_species(None), 1)
        self.assertEqual(trust_stats.race_for_species("0"), 1)

    def test_tarutaru_black_mage_has_a_caster_mp_pool(self):
        """Shantotto at 99 must not keep the old 396 MP placeholder."""
        hp, mp = trust_stats.vitals(5, 4, 0, 99)
        self.assertEqual((hp, mp), (1111, 1779))
        self.assertGreater(mp, 1000)

    def test_job_decides_hp(self):
        """A Hume WHM outlasts a Tarutaru BLM at the same level."""
        whm_hp, _ = trust_stats.vitals(1, 3, 0, 99)
        blm_hp, _ = trust_stats.vitals(5, 4, 0, 99)
        self.assertGreater(whm_hp, blm_hp)

    def test_joachim_gets_mp_from_the_half_level_subjob(self):
        """BRD has no MP grade; the /WHM half still gives him a real pool."""
        hp, mp = trust_stats.vitals(1, 10, 3, 99)
        self.assertEqual((hp, mp), (1439, 400))
        self.assertGreater(mp, 396)

    def test_a_job_without_mp_and_without_an_mp_subjob_has_zero(self):
        self.assertEqual(trust_stats.vitals(8, 1, 0, 99), (1554, 0))

    def test_level_is_clamped_and_grows(self):
        self.assertEqual(trust_stats.vitals(5, 4, 0, 0),
                         trust_stats.vitals(5, 4, 0, 1))
        low_hp, low_mp = trust_stats.vitals(5, 4, 0, 50)
        high_hp, high_mp = trust_stats.vitals(5, 4, 0, 99)
        self.assertLess(low_hp, high_hp)
        self.assertLess(low_mp, high_mp)
        self.assertEqual(high_hp, trust_stats.vitals(5, 4, 0, 120)[0])

    def test_trust_entity_reads_the_species_column(self):
        row = {
            "spell_id": 896, "name": "Shantotto", "job": 4, "sub_job": 0,
            "look_hex": "0000b80b" + "00" * 16, "model": 3000, "delay": 240,
            "damage_mult": 40, "name_prefix": 32, "passive": 0, "species": 297,
        }
        entity = trust_from_row(row, 0x700, 100, 1, 99)
        self.assertEqual(entity.race, 5)
        self.assertEqual((entity.hp_max, entity.mp_max), (1111, 1779))
        self.assertEqual((entity.hp, entity.mp), (1111, 1779))

    def test_an_old_row_without_species_still_works(self):
        row = {
            "spell_id": 896, "name": "Shantotto", "job": 4, "sub_job": 0,
            "look_hex": "0000b80b" + "00" * 16, "model": 3000, "delay": 240,
            "damage_mult": 40, "name_prefix": 32, "passive": 0,
        }
        entity = trust_from_row(row, 0x700, 100, 1, 99)
        self.assertEqual(entity.race, 1)
        self.assertGreater(entity.mp_max, 1000)


if __name__ == "__main__":
    unittest.main()
