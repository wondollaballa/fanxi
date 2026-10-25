"""Bard song data: family icons plus the per-tier stat/tick values."""
from __future__ import annotations

import unittest

from fanxi_server.game import effects, modifiers as mod


class SongTest(unittest.TestCase):
    def test_minuet_grants_attack(self):
        song = effects.for_spell("Valor Minuet V")
        self.assertEqual(song.effect, 198)
        self.assertEqual(song.mods, {mod.ATT: 50})

    def test_minne_grants_defense(self):
        song = effects.for_spell("Knights Minne")
        self.assertEqual(song.effect, 197)
        self.assertEqual(song.mods, {mod.DEF: 10})

    def test_march_grants_magic_haste(self):
        self.assertEqual(effects.for_spell("Victory March").mods, {mod.HASTE_GEAR: 6})

    def test_paeon_and_ballad_tick(self):
        self.assertEqual(effects.for_spell("Armys Paeon III").mods, {mod.REGEN: 3})
        self.assertEqual(effects.for_spell("Mages Ballad II").mods, {mod.REFRESH: 2})

    def test_requiem_is_a_dot(self):
        self.assertEqual(effects.for_spell("Foe Requiem IV").tick, 4)
        self.assertEqual(effects.for_spell("Foe Requiem IV").kind, "debuff")

    def test_song_skill_set(self):
        self.assertIn(40, effects.SONG_SKILLS)


if __name__ == "__main__":
    unittest.main()
