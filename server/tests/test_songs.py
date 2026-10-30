"""Bard song data: family icons plus the per-tier stat/tick values."""
from __future__ import annotations

import unittest

from fanxi_server.game import effects, modifiers as mod


class SongTest(unittest.TestCase):
    def test_minuet_grants_attack(self):
        """BG-wiki's Minuet table: Valor Minuet V is +124 Attack at Song+ 0."""
        song = effects.for_spell("Valor Minuet V")
        self.assertEqual(song.effect, 198)
        self.assertEqual(song.mods, {mod.ATT: 124, mod.RATT: 124})

    def test_minne_grants_defense(self):
        self.assertEqual(effects.for_spell("Knights Minne").mods, {mod.DEF: 30})
        self.assertEqual(effects.for_spell("Knights Minne V").mods, {mod.DEF: 204})

    def test_march_grants_magic_haste(self):
        # Victory March is 15.92% at Song+ 0 (hundredths, as the engine stores haste).
        self.assertEqual(effects.for_spell("Victory March").mods, {mod.HASTE_MAGIC: 1592})

    def test_march_song_plus_scales_by_the_table(self):
        spec = effects.for_spell("Victory March")
        mods, _tick = effects.song_potency_values(
            "Victory March", spec, {mod.MARCH_EFFECT: 4})
        self.assertEqual(mods[mod.HASTE_MAGIC], 2227)     # BG-wiki +4 column: 22.27%
        mods, _tick = effects.song_potency_values(
            "Victory March", spec, {mod.MARCH_EFFECT: 1})
        self.assertEqual(mods[mod.HASTE_MAGIC], 1748)     # +1 column: 17.48%

    def test_paeon_and_ballad_tick(self):
        self.assertEqual(effects.for_spell("Armys Paeon III").tick, 4)
        self.assertEqual(effects.for_spell("Mages Ballad II").tick, 2)

    def test_requiem_is_a_dot(self):
        self.assertEqual(effects.for_spell("Foe Requiem IV").tick, 5)
        self.assertEqual(effects.for_spell("Foe Requiem IV").kind, "debuff")

    def test_lullaby_job_points_are_part_of_the_base_timer(self):
        """Lullaby's +1 a rank is sleep duration, so Troubadour doubles it."""
        spec = effects.for_spell("Foe Lullaby")
        gear = {mod.ALL_SONGS_EFFECT: 7}
        self.assertEqual(51.0, effects.song_duration(spec, name="Foe Lullaby", mods=gear))
        self.assertEqual(71.0, effects.song_duration(
            spec, name="Foe Lullaby", mods=gear, flat_seconds=20))
        self.assertEqual(142.0, effects.song_duration(
            spec, name="Foe Lullaby", mods=gear, flat_seconds=20, troubadour=True))

    def test_requiem_job_points_are_added_after_the_multiplier(self):
        """BG-wiki's Requiem examples: (14 x 1.5) + 60 = 81 and (14 x 2) + 60 = 88."""
        spec = effects.for_spell("Foe Requiem VII")
        gear = {mod.ALL_SONGS_EFFECT: 7}
        _m, base = effects.song_potency_values("Foe Requiem VII", spec, gear)
        _m, marcato = effects.song_potency_values("Foe Requiem VII", spec, gear, marcato=True)
        _m, soul = effects.song_potency_values("Foe Requiem VII", spec, gear, soul_voice=True)
        self.assertEqual(14, base)
        self.assertEqual(21, marcato)
        self.assertEqual(28, soul)
        self.assertEqual(81, marcato + 60)
        self.assertEqual(88, soul + 60)

    def test_the_support_families_use_their_own_stats(self):
        """Carol, Mambo, Prelude, Nocturne and Scherzo write what retail writes."""
        self.assertEqual({mod.EVA: 48}, effects.for_spell("Sheepfoe Mambo").mods)
        self.assertEqual({mod.EVA: 72}, effects.for_spell("Dragonfoe Mambo").mods)
        self.assertEqual({mod.RACC: 45}, effects.for_spell("Hunters Prelude").mods)
        self.assertEqual({mod.RACC: 60}, effects.for_spell("Archers Prelude").mods)
        self.assertEqual({mod.MACC: -15}, effects.for_spell("Pining Nocturne").mods)
        self.assertEqual({mod.FIRE_MEVA: 80}, effects.for_spell("Fire Carol").mods)
        self.assertEqual({mod.FIRE_MEVA: 100}, effects.for_spell("Fire Carol II").mods)
        self.assertEqual({mod.THUNDER_MEVA: 80},
                         effects.for_spell("Lightning Carol").mods)
        self.assertEqual({mod.UDMGPHYS: -4500, mod.UDMGMAGIC: -4500},
                         effects.for_spell("Sentinels Scherzo").mods)

    def test_the_monster_side_song_values(self):
        """Threnody and Elegy store their number on the mob, not on the caster."""
        self.assertEqual(50, effects.song_table_value("Fire Threnody", "meva", {}))
        self.assertEqual(70, effects.song_table_value(
            "Fire Threnody", "meva", {mod.ALL_SONGS_EFFECT: 4}))
        self.assertEqual(160, effects.song_table_value("Fire Threnody II", "meva", {}))
        self.assertEqual(95, effects.song_table_value(
            "Fire Threnody", "meva", {mod.ALL_SONGS_EFFECT: 9}))   # clamped to the table
        self.assertEqual(25, effects.song_table_value("Battlefield Elegy", "slow", {}))
        self.assertEqual(50, effects.song_table_value("Carnage Elegy", "slow", {}))
        spec = effects.for_spell("Sentinels Scherzo")
        mods, _tick = effects.song_potency_values(
            "Sentinels Scherzo", spec, {mod.ALL_SONGS_EFFECT: 8})
        self.assertEqual(-5300, mods[mod.UDMGPHYS])

    def test_the_wiki_minuet_example(self):
        """Minuet V, +8 Song+, 5/5 merit, 20/20 job points, Marcato: +372 Attack.

        BG-wiki's worked example on the Minuet page: the +Song percentage applies
        first, the merit and job-point points are added after it, and Soul Voice or
        Marcato multiply the lot.
        """
        spec = effects.for_spell("Valor Minuet V")
        with_gear, _tick = effects.song_potency_values(
            "Valor Minuet V", spec,
            {mod.ALL_SONGS_EFFECT: 7, mod.MINUET_EFFECT: 1})
        self.assertEqual(with_gear[mod.ATT], 223)
        with_points, _tick = effects.song_potency_values(
            "Valor Minuet V", spec,
            {mod.ALL_SONGS_EFFECT: 7, mod.MINUET_EFFECT: 1}, flat_bonus=25)
        self.assertEqual(with_points[mod.ATT], 248)
        with_marcato, _tick = effects.song_potency_values(
            "Valor Minuet V", spec,
            {mod.ALL_SONGS_EFFECT: 7, mod.MINUET_EFFECT: 1}, flat_bonus=25,
            marcato=True)
        self.assertEqual(with_marcato[mod.ATT], 372)

    def test_the_song_tables_cover_the_families_the_library_sings(self):
        for name in ("Valor Minuet V", "Knights Minne V", "Sword Madrigal",
                     "Victory March", "Honor March", "Mages Ballad III",
                     "Armys Paeon V", "Foe Requiem VII", "Aria of Passion"):
            with self.subTest(song=name):
                self.assertIn(effects._song_key(name), effects.SONG_POTENCY)

    def test_song_skill_set(self):
        self.assertIn(40, effects.SONG_SKILLS)


if __name__ == "__main__":
    unittest.main()
