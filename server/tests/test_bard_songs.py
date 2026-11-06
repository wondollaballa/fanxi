"""Bard song rules: slots, overwrites, instrument gates and Nitro/Soul Voice."""
from __future__ import annotations

import struct
import tempfile
import time
import types
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import combat, effects, modifiers as mod, packets
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def chats(session) -> list[str]:
    out = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        out.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return out


class BardSongTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.fresh_login = False
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True
        self.session.char["main_job"] = 10
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 0
        self.session.char["sub_level"] = 0

    def equip(self, kind: int, item_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, 0, ?)",
            (int(self.character["id"]), int(kind), int(item_id)))
        # Tests write char_equip directly; mirror it into the session's outfit so a
        # cast's store_equipment() does not delete the row again.
        self.session.equipped[int(kind)] = (0, 0, int(item_id))

    def equip_range(self, item_id: int) -> None:
        self.equip(2, item_id)

    def clear(self) -> None:
        self.session.effect_state.clear()
        self.session.status_effects.clear()
        self.session.ability_recasts.clear()
        self.session.casting = None
        self.session.queue.clear()

    def cast(self, name: str, wait: float = 30.0):
        spell = self.service.spell_by_name(name)
        self.assertIsNotNone(spell, name)
        spec = effects.for_spell(name)
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0,
                         packets.ACTION_CAST_MAGIC, int(spell["id"]))
        self.session.casting = None
        self.session.cast_magic(bytes(packet), 0)
        if self.session.casting is None:
            return None
        self.session.queue.clear()
        self.session.tick(time.time() + wait)
        song = self.song_state(name)
        if song is not None:
            return song
        return self.session.effect(int(spec.effect)) if spec is not None else None

    def cast_seconds(self, name: str) -> float:
        """The server-side cast duration a fresh cast of *name* schedules."""
        spell = self.service.spell_by_name(name)
        self.assertIsNotNone(spell, name)
        self.session.char["mp_current"] = 9999
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0,
                         packets.ACTION_CAST_MAGIC, int(spell["id"]))
        self.session.casting = None
        started = time.time()
        self.session.cast_magic(bytes(packet), 0)
        self.assertIsNotNone(self.session.casting, name)
        return float(self.session.casting["finish"]) - started

    def ability(self, ability_id: int) -> None:
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]),
                         0, packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, ability_id)
        self.session.job_ability(bytes(packet), 0)
        self.session.queue.clear()

    def song_state(self, name: str):
        wanted = " ".join(str(name).casefold().split())
        for state in self.session.effect_state.values():
            if (state.get("song")
                    and " ".join(str(state.get("song_name", "")).casefold().split()) == wanted):
                return state
        return None

    def has_song(self, name: str) -> bool:
        return self.song_state(name) is not None

    def active_songs(self) -> list[str]:
        return [str(state.get("song_name")) for state in self.session.effect_state.values()
                if state.get("song")]

    def test_no_instrument_allows_one_song(self):
        self.cast("Victory March")
        self.cast("Valor Minuet V")
        self.assertEqual(len(self.active_songs()), 1)
        self.assertEqual(self.session._song_limit(), 1)

    def test_marches_stack_even_though_they_share_an_icon(self):
        self.equip_range(22307)
        self.cast("Victory March")
        self.cast("Advancing March")
        self.assertEqual(self.active_songs(), ["Victory March", "Advancing March"])
        hastes = [int(self.song_state(name)["mods"][mod.HASTE_MAGIC])
                  for name in ("Victory March", "Advancing March")]
        self.assertTrue(all(value > 0 for value in hastes))
        self.assertGreater(sum(hastes), max(hastes))

    def test_paeon_versions_stack_and_tick_together(self):
        self.equip_range(22307)
        for name in ("Armys Paeon", "Armys Paeon II", "Armys Paeon III"):
            self.cast(name)
        self.assertEqual(self.active_songs(),
                         ["Armys Paeon", "Armys Paeon II", "Armys Paeon III"])
        # BG-wiki's Paeon table at Song+4 (Loughnashade's All songs +4).
        self.assertEqual([int(self.song_state(name)["tick"])
                          for name in ("Armys Paeon", "Armys Paeon II", "Armys Paeon III")],
                         [6, 7, 8])
        self.session.char["hp_current"] = int(self.session.char["hp"]) - 100
        for state in self.session.effect_state.values():
            if state.get("song"):
                state["next_tick"] = 0.0
        before = int(self.session.char["hp_current"])
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["hp_current"]) - before, 21)

    def test_minne_versions_stack(self):
        self.equip_range(22307)
        self.cast("Knights Minne")
        first = int(self.session.combat_mods().get(mod.DEF, 0))
        self.cast("Knights Minne II")
        self.assertEqual(self.active_songs(), ["Knights Minne", "Knights Minne II"])
        self.assertGreater(int(self.session.combat_mods().get(mod.DEF, 0)), first)

    def test_loughnashade_allows_four_and_overwrites_oldest(self):
        self.equip_range(22307)
        self.assertEqual(self.session._song_limit(), 4)
        for name in ("Victory March", "Valor Minuet V", "Blade Madrigal",
                     "Mages Ballad III", "Armys Paeon III"):
            self.cast(name)
        self.assertEqual(len(self.active_songs()), 4)
        self.assertFalse(self.has_song("Victory March"))
        self.assertIn("Armys Paeon III", self.active_songs())

    def test_clarion_call_allows_five(self):
        self.equip_range(22307)
        self.ability(332)  # Clarion Call
        self.assertEqual(self.session._song_limit(), 5)
        for name in ("Victory March", "Valor Minuet V", "Blade Madrigal",
                     "Mages Ballad III", "Armys Paeon III"):
            self.cast(name)
        self.assertEqual(len(self.active_songs()), 5)

    def test_same_song_does_not_refresh_above_base(self):
        self.equip_range(22307)
        self.cast("Victory March")
        first = float(self.song_state("Victory March")["until"])
        time.sleep(0.02)
        self.cast("Victory March")
        self.assertAlmostEqual(float(self.song_state("Victory March")["until"]),
                               first, delta=0.5)
        # Once it has less than the unenhanced 120 s left it may be refreshed.
        self.song_state("Victory March")["until"] = time.time() + 60.0
        self.cast("Victory March")
        self.assertGreater(float(self.song_state("Victory March")["until"]),
                           time.time() + 100.0)

    def test_troubadour_doubles_duration(self):
        self.ability(164)  # Troubadour
        state = self.cast("Valor Minuet V")
        self.assertIsNotNone(state)
        self.assertGreater(float(state["until"]) - time.time(), 240.0)
        self.assertLess(float(state["until"]) - time.time(), 260.0)

    def test_the_songs_command_lists_every_tier(self):
        """//songs is how a bard tells the tiers apart: they share one icon.

        Valor Minuet III, IV and V all carry effect 198, so the client's icon row
        shows three icons with the same name.  The server keys each song by spell
        id, and the command reads that.
        """
        self.equip_range(22307)  # Loughnashade: Maximum songs +2, so four fit
        for name in ("Valor Minuet III", "Valor Minuet IV", "Valor Minuet V"):
            self.assertIsNotNone(self.cast(name), name)
        self.session.queue.clear()
        self.session.command(["songs"])
        lines = chats(self.session)
        for name in ("Valor Minuet III", "Valor Minuet IV", "Valor Minuet V"):
            self.assertTrue(any(line.startswith(name) for line in lines), lines)
        self.assertIn("3 song(s) on you", lines[-1])

    def test_soul_voice_doubles_potency_but_not_normal_song_duration(self):
        self.ability(25)  # Soul Voice
        state = self.cast("Valor Minuet V")
        self.assertIsNotNone(state)
        self.assertLess(float(state["until"]) - time.time(), 130.0)
        # No instrument: Minuet V's 124, plus the 20-point job-point row, doubled by
        # Soul Voice (retail doubles after merit and job-point bonuses).
        self.assertEqual(int(state["mods"][mod.ATT]), 288)

    def test_soul_voice_and_troubadour_double_scherzo_duration(self):
        self.ability(25)
        self.ability(164)
        state = self.cast("Sentinels Scherzo")
        self.assertIsNotNone(state)
        self.assertGreater(float(state["until"]) - time.time(), 490.0)
        self.assertLess(float(state["until"]) - time.time(), 520.0)

    def test_honor_march_requires_marsyas(self):
        self.equip_range(22307)
        self.cast("Honor March")
        self.assertFalse(self.has_song("Victory March"))
        self.assertTrue(any("instrument" in line.lower() for line in chats(self.session)))
        self.equip_range(21398)
        state = self.cast("Honor March")
        self.assertIsNotNone(state)
        self.assertEqual(state["mods"][mod.HASTE_MAGIC], 1230)   # 12.30%
        self.assertEqual(state["mods"][mod.ATT], 168)

    def test_aria_of_passion_requires_loughnashade(self):
        self.equip_range(21398)
        self.cast("Aria of Passion")
        self.assertFalse(self.has_song("Aria of Passion"))
        self.equip_range(22307)
        state = self.cast("Aria of Passion")
        self.assertIsNotNone(state)
        self.assertEqual(state["mods"][mod.DAMAGE_LIMITP], 1820)

    def test_minuet_merits_and_job_points_are_added_after_the_percentage(self):
        """Bard group-1 Minuet Effect (5/5 = +5) plus the +20 job-point row."""
        self.db.execute(
            "INSERT OR REPLACE INTO char_merits (character_id, merit_id, upgrades)"
            " VALUES (?, ?, ?)", (int(self.character["id"]), 0x03C6, 5))
        self.session._merit_counts = None
        self.equip_range(22307)
        state = self.cast("Valor Minuet V")
        self.assertIsNotNone(state)
        # 173 at Song+4, +5 merit, +20 job points.
        self.assertEqual(int(state["mods"][mod.ATT]), 198)

    def test_scherzo_reduces_damage_taken(self):
        """Scherzo's -45% a rank-0 row lands on the party's damage-taken modifiers."""
        self.equip_range(22307)   # Loughnashade: All songs +4 => 49%
        state = self.cast("Sentinels Scherzo")
        self.assertIsNotNone(state)
        self.assertEqual(-4900, int(state["mods"][mod.UDMGPHYS]))
        self.assertEqual(-4900, int(state["mods"][mod.UDMGMAGIC]))
        self.assertNotIn(mod.DMG, state["mods"])
        sheet = self.session.stat_sheet()
        self.assertAlmostEqual(0.51, combat.damage_taken(sheet.fighter.mods), places=3)

    def test_threnody_lowers_the_mobs_magic_evasion(self):
        self.equip_range(22307)   # Fire Threnody at +4 is 70
        mob = self.mob()
        spell = self.service.spell_by_name("Fire Threnody")
        spec = effects.for_spell("Fire Threnody")
        before = self.world.monster_debuff_mods(mob).get(mod.MEVA, 0)
        self.session._song_extra_debuff(mob, spell, spec, time.time(), 60.0)
        after = self.world.monster_debuff_mods(mob).get(mod.MEVA, 0)
        self.assertEqual(70, before - after)

    def test_elegy_slows_the_mob(self):
        self.equip_range(22307)   # Battlefield Elegy at +4 is 34.96% -> 35
        mob = self.mob()
        spell = self.service.spell_by_name("Battlefield Elegy")
        spec = effects.for_spell("Battlefield Elegy")
        self.session._song_extra_debuff(mob, spell, spec, time.time(), 60.0)
        self.assertEqual(35, int(mob.effect_state[effects.SLOW]["potency"]))

    def test_carol_raises_the_elemental_resistance(self):
        self.equip_range(22307)   # Fire Carol at +4 is 112; Carol II is flat 100
        state = self.cast("Fire Carol")
        self.assertIsNotNone(state)
        self.assertEqual(112, int(state["mods"][mod.FIRE_MEVA]))
        self.assertNotIn(mod.MDEF, state["mods"])
        state = self.cast("Fire Carol II")
        self.assertIsNotNone(state)
        self.assertEqual(100, int(state["mods"][mod.FIRE_MEVA]))

    def test_mambo_preserve_and_nocturne_use_their_own_stats(self):
        self.equip_range(22307)
        state = self.cast("Dragonfoe Mambo")
        self.assertEqual(100, int(state["mods"][mod.EVA]))
        self.assertNotIn(mod.ATT, state["mods"])
        state = self.cast("Archers Prelude")
        self.assertEqual(84, int(state["mods"][mod.RACC]))
        self.assertNotIn(mod.ACC, state["mods"])
        # Nocturne is a debuff, so it lands on the mob rather than on this buff list.
        nocturne = effects.for_spell("Pining Nocturne")
        mods_4, _tick = effects.song_potency_values(
            "Pining Nocturne", nocturne, {mod.ALL_SONGS_EFFECT: 4})
        self.assertEqual({mod.MACC: -21}, mods_4)

    def test_pianissimo_narrows_the_song_to_one_member(self):
        """Pianissimo's next song lands on the chosen party member only."""
        member = types.SimpleNamespace(char={"char_id": 2}, zone=self.session.zone)
        self.session._accession_targets = lambda now: [self.session, member]
        self.assertEqual([self.session, member], self.session.song_targets(0.0, None))
        # Without the status the cast's target does not narrow anything.
        self.assertEqual([self.session, member],
                         self.session.song_targets(0.0, {"party_target": 2}))
        self.session.add_effect(effects.PIANISSIMO, duration=60)
        self.assertEqual([member], self.session.song_targets(0.0, {"party_target": 2}))
        self.assertEqual([self.session, member],
                         self.session.song_targets(0.0, {"party_target": 99}))

    def test_magic_finale_dispels_one_effect(self):
        mob = self.mob()
        mob.status_effects.append(190)
        mob.effect_state[190] = {"icon": 190, "until": time.time() + 60}
        spell = self.service.spell_by_name("Magic Finale")
        self.session.resolve_special_spell(spell, mob, {"amount": 0})
        self.assertNotIn(190, mob.effect_state)
        self.assertFalse(mob.status_effects)

    def test_goddess_hymnus_grants_reraise(self):
        self.equip_range(22307)
        state = self.cast("Goddesss Hymnus")
        self.assertIsNotNone(state)
        self.assertIn(effects.RERAISE, self.session.effect_state)
        # The song keeps the Hymnus icon (218); Reraise is its own effect on top.
        self.assertEqual(218, int(state["icon"]))
        self.session.char["hp_current"] = 0
        self.session.hit_zero_hp(time.time())
        self.assertEqual(int(self.session.char["hp"]) // 10,
                         int(self.session.char["hp_current"]))
        self.assertNotIn(effects.RERAISE, self.session.effect_state)
        self.assertEqual(0.0, self.session.dead_until)

    def mob(self):
        """A bare monster for the effects that are stored on the mob, not the caster."""
        mob = ZoneEntity(kind="mob", id=0x7FFF0001, targid=0x300, zone=self.session.zone,
                         name="Testmob", level=99)
        mob.alive = True
        return mob

    def test_requiem_job_points_land_after_marcato(self):
        """Requiem VII at Song+7 under Marcato: 14 x 1.5, then the +60 row = 81."""
        self.equip(2, 22307)   # Loughnashade: All songs +4
        self.equip(9, 26033)   # Mnbw. Whistle +1: All songs +3
        self.ability(284)      # Marcato
        spell = self.service.spell_by_name("Foe Requiem VII")
        spec = effects.for_spell("Foe Requiem VII")
        self.assertEqual(81, self.session._song_debuff_tick(spell, spec))

    def test_song_potency_gear(self):
        self.equip_range(22307)
        self.assertEqual(self.session.combat_mods().get(mod.ALL_SONGS_EFFECT), 4)
        state = self.cast("Valor Minuet V")
        self.assertIsNotNone(state)
        # Minuet V at Song+4 is 173 on the wiki table, plus the 20-point job-point row.
        self.assertEqual(state["mods"][mod.ATT], 193)

    def test_soul_voice_has_a_recast(self):
        self.ability(25)
        # The Master job-point gift takes 15 minutes off every one-hour ability, so the
        # 3600 s recast lands at 2700 s for a character with the 2,100 JP.
        self.assertGreater(self.session.ability_recasts.get(111, 0.0), time.time() + 2600)

    def test_reforged_song_stats_are_in_the_database(self):
        """The +3/+4 pieces the library swaps in carry their song lines."""
        expected = {
            (23429, 455): 16,   # Fili Calot +3, Song spellcasting time
            (23429, 438): 1,    # Fili Calot +3, "Madrigal"+1
            (23496, 454): 14,   # Fili Hongreline +3, Song effect duration
            (23496, 434): 1,    # Fili Hongreline +3, "Minuet"+1
            (23563, 443): 1,    # Fili Manchettes +3, "March"+1
            (23630, 833): 10,   # Fili Rhingrave +3, Song recast delay
            (23630, 442): 1,    # Fili Rhingrave +3, "Ballad"+1
            (23697, 451): 1,    # Fili Cothurnes +3, "Scherzo"+1
            (23904, 435): 2,    # Brioso Roundlet +4, "Paeon"+2
            (23949, 455): 15,   # Brioso Justaucorps +4, Song casting time
            (23994, 440): 2,    # Brioso Cuffs +4, "Lullaby"+2
            (24084, 454): 15,   # Brioso Slippers +4, Song duration
            (24107, 455): 10,   # Bihu Slippers +4, Song casting time
        }
        for (item_id, mod_id), value in expected.items():
            row = self.db.one(
                "SELECT value FROM item_mods WHERE item_id = ? AND mod_id = ?",
                (item_id, mod_id))
            self.assertIsNotNone(row, (item_id, mod_id))
            self.assertEqual(int(row["value"]), value)

    def test_song_precast_pieces_apply_their_cast_time(self):
        for kind, item_id in ((4, 23429), (5, 23949), (8, 24107)):
            self.equip(kind, item_id)
        self.assertEqual(
            self.session.combat_mods().get(mod.SONG_SPELLCASTING_TIME), 46)
        # 8.0 s base, -41% from the three pieces and -5% from the Bard gift.
        self.assertAlmostEqual(self.cast_seconds("Valor Minuet V"), 4.32, delta=0.03)

    def test_song_cast_time_gift_does_not_speed_cure(self):
        # Cure is not a Bard spell; a White Mage sub job supplies it while the main job
        # (and its song cast-time gift) stays Bard.
        self.session.char["sub_job"] = 3
        self.session.char["sub_level"] = 99
        self.assertAlmostEqual(self.cast_seconds("Cure"), 2.0, delta=0.02)

    def test_nightingale_halves_the_geared_song_cast(self):
        for kind, item_id in ((4, 23429), (5, 23949), (8, 24107)):
            self.equip(kind, item_id)
        self.ability(163)  # Nightingale
        self.assertAlmostEqual(self.cast_seconds("Valor Minuet V"), 2.16, delta=0.03)

    def test_nightingale_and_troubadour_cast_time(self):
        self.ability(163)
        self.cast("Valor Minuet V")
        # The helper resolves the cast; measure a fresh cast before ticking it.
        self.session.casting = None
        packet = bytearray(16)
        spell = self.service.spell_by_name("Valor Minuet V")
        struct.pack_into("<IHHI", packet, 4, 0, 0,
                         packets.ACTION_CAST_MAGIC, int(spell["id"]))
        started = time.time()
        self.session.cast_magic(bytes(packet), 0)
        self.assertLess(self.session.casting["finish"] - started, 6.0)


if __name__ == "__main__":
    unittest.main()
