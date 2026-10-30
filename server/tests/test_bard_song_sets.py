"""The BRD library's song sets, against the server's song-duration formula.

Fanxi computes a song's timer as

    120 * (1 + (454 lines + 10 per Song+ point + the 5% job-point gift) / 100)
        * 2 while Troubadour is up
        + 40 Clarion Call, + 40 Tenuto, + 20 Marcato (added after the doubling)

Song+ is All Songs plus the family row for that song, and each point is worth 10%
duration, so Loughnashade's All songs +4 is +40% and Mnbw. Whistle +1's +3 is
+30%.  These checks keep ``gearswap/BRD.lua`` on the loadouts that
``BRD-review.md`` documents:

* the five-song set is Loughnashade (96 from the 454 lines, 7-8 Song+ points,
  Maximum songs +2),
* Honor March is Marsyas (146 from the 454 lines, 4 Song+ points, no Maximum
  songs bonus),
* ``precast.Song`` carries the Loughnashade that Aria of Passion's cast-time
  instrument check reads.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import effects, modifiers as mod

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "gearswap" / "BRD.lua"

SET_START = re.compile(r"^\s*sets\.([A-Za-z0-9_.]+)\s*=\s*\{", re.M)
SLOT_LINE = re.compile(r'(\w+)\s*=\s*"([^"]+)"')


def parse_sets(text: str) -> dict[str, dict[str, str]]:
    """Every ``sets.<path> = { slot = "Item", ... }`` in one GearSwap library."""
    out: dict[str, dict[str, str]] = {}
    for match in SET_START.finditer(text):
        index, depth = match.end(), 1
        while depth:
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            index += 1
        out[match.group(1)] = dict(SLOT_LINE.findall(text[match.end():index - 1]))
    return out


class BardSongSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.config, cls.db, cls.service = make_service(Path(cls.tmp.name))
        cls.sets = parse_sets(LIBRARY.read_text(encoding="utf-8"))

    def item_mods(self, name: str) -> dict[int, int]:
        """The mods of the best copy of *name*.

        Several items share a name across their upgrade paths (five Carnwenhan
        rows, four Loughnashade including the Incomplete stage), and the test
        database has no character to say which copy a set means.  The finished
        level-99 copy is the one a 99 bard wears, so take the row worth the most
        song duration -- 454 plus 10% for every All Songs point.
        """
        rows = self.db.all(
            "SELECT i.item_id, "
            "  COALESCE((SELECT value FROM item_mods m "
            "    WHERE m.item_id = i.item_id AND m.mod_id = ?), 0) "
            "  + 10 * COALESCE((SELECT value FROM item_mods m "
            "    WHERE m.item_id = i.item_id AND m.mod_id = ?), 0) AS value "
            "FROM items i WHERE i.name = ? COLLATE NOCASE ORDER BY value DESC, i.item_id",
            (mod.SONG_DURATION_BONUS, mod.ALL_SONGS_EFFECT, name))
        self.assertTrue(rows, "%s is not an item name" % name)
        return {int(entry["mod_id"]): int(entry["value"]) for entry in self.db.all(
            "SELECT mod_id, value FROM item_mods WHERE item_id = ?", (int(rows[0]["item_id"]),))}

    def set_mods(self, path: str) -> dict[int, int]:
        """The worn mods of one set, with the 5% job-point gift folded into 454."""
        mods: dict[int, int] = {}
        for item in self.sets[path].values():
            for mod_id, value in self.item_mods(item).items():
                mods[mod_id] = mods.get(mod_id, 0) + value
        mods[mod.SONG_DURATION_BONUS] = mods.get(mod.SONG_DURATION_BONUS, 0) + 5
        return mods

    def seconds(self, path: str, song: str, **abilities) -> float:
        spec = effects.for_spell(song)
        self.assertIsNotNone(spec, song)
        return effects.song_duration(spec, name=song, mods=self.set_mods(path), **abilities)

    def test_every_song_set_item_exists(self):
        song_sets = [path for path in self.sets
                     if path.startswith("midcast.Song") or path in {
                         "precast.Song", "precast.FCBardSong", "precast.FCHonor"}]
        self.assertTrue(song_sets)
        for path in song_sets:
            for slot, item in self.sets[path].items():
                with self.subTest(set=path, slot=slot):
                    self.item_mods(item)

    def test_family_song_sets_reach_their_potency_cap_and_outlast_the_baseline(self):
        cases = {
            "midcast.SongPaeon": ("Armys Paeon III", 9),
            "midcast.SongLullaby": ("Foe Lullaby II", 9),
            "midcast.SongEtude": ("Sinewy Etude", 9),
            "midcast.SongCarol": ("Fire Carol II", 9),
            "midcast.SongThrenody": ("Fire Threnody II", 9),
            "midcast.SongMinne": ("Knights Minne V", 9),
            "midcast.SongMambo": ("Dragonfoe Mambo", 9),
            "midcast.SongMadrigal": ("Blade Madrigal", 8),
            "midcast.SongMinuet": ("Valor Minuet V", 8),
            "midcast.SongMarch": ("Victory March", 8),
        }
        for path, (song, expected) in cases.items():
            with self.subTest(set=path, song=song):
                mods = self.set_mods(path)
                family = effects.song_family(song)
                self.assertIsNotNone(family)
                family_mod = effects.SONG_FAMILY_MOD[family]
                self.assertEqual(
                    int(mods.get(mod.ALL_SONGS_EFFECT, 0)) + int(mods.get(family_mod, 0)),
                    expected,
                )
                self.assertEqual(self.sets[path]["range"], "Loughnashade")
                self.assertEqual(self.sets[path]["neck"], "Mnbw. Whistle +1")
                # A Song+ point is 10% duration, so even the body/legs/feet swaps
                # (Threnody/Minne/Mambo) beat the +7 all-duration baseline.
                self.assertGreaterEqual(
                    self.seconds(path, song, troubadour=True),
                    self.seconds("midcast.SongDuration", song, troubadour=True),
                )

    def test_mousai_family_rows_are_in_the_database(self):
        expected = {
            25989: (mod.CAROL_EFFECT, 2),
            26538: (mod.THRENODY_EFFECT, 2),
            25902: (mod.MINNE_EFFECT, 2),
            25969: (mod.MAMBO_EFFECT, 2),
        }
        for item_id, (mod_id, value) in expected.items():
            with self.subTest(item_id=item_id):
                self.assertEqual(
                    int(self.db.scalar(
                        "SELECT value FROM item_mods WHERE item_id = ? AND mod_id = ?",
                        (item_id, mod_id), 0)),
                    value,
                )

    def test_the_five_song_set_carries_every_duration_piece(self):
        # 454: Carnwenhan 50 + Fili Hongreline +3 14 + Inyanga Shalwar +2 17
        #      + Brioso Slippers +4 15 = 96.
        # Song+: Loughnashade 4 + Mnbw. Whistle +1 3 = 7.
        for path in ("midcast.SongDuration", "midcast.Song", "midcast.SongAria"):
            with self.subTest(set=path):
                mods = self.set_mods(path)
                self.assertEqual(mods.get(mod.SONG_DURATION_BONUS), 101)  # 96 + gift
                self.assertEqual(mods.get(mod.ALL_SONGS_EFFECT), 7)
                self.assertEqual(self.sets[path]["range"], "Loughnashade")
                self.assertEqual(self.sets[path]["neck"], "Mnbw. Whistle +1")

    def test_honor_march_keeps_marsyas(self):
        # Marsyas is +50 instead of All songs +4, which is the single-song cap:
        # 146 from the 454 lines plus 4 Song+ points (Mnbw + March+1).
        mods = self.set_mods("midcast.SongHonor")
        self.assertEqual(mods.get(mod.SONG_DURATION_BONUS), 151)  # 146 + gift
        self.assertEqual(mods.get(mod.ALL_SONGS_EFFECT), 3)
        self.assertEqual(self.sets["midcast.SongHonor"]["range"], "Marsyas")

    def test_the_cast_time_sets_hold_the_instrument_the_check_reads(self):
        # The server checks the instrument when the cast packet arrives, not when
        # the song lands, so these must stay on the required instrument.
        for path in ("precast.Song", "precast.FCBardSong"):
            with self.subTest(set=path):
                self.assertEqual(self.sets[path]["range"], "Loughnashade")
        self.assertEqual(self.sets["precast.FCHonor"]["range"], "Marsyas")

    def test_the_documented_timers(self):
        # 181% for a March (96 + 80 Song+ + 5), 171% for a song with no family row.
        self.assertAlmostEqual(714.4, self.seconds(
            "midcast.SongDuration", "Victory March", troubadour=True, tenuto=True), places=1)
        self.assertAlmostEqual(774.4, self.seconds(
            "midcast.SongDuration", "Victory March", troubadour=True, tenuto=True,
            marcato=True, clarion=True), places=1)
        self.assertAlmostEqual(650.4, self.seconds(
            "midcast.SongDuration", "Knights Minne V", troubadour=True), places=1)
        # Honor March: 191% with Marsyas, 13:18 with the full ability set.
        self.assertAlmostEqual(798.4, self.seconds(
            "midcast.SongHonor", "Honor March", troubadour=True, tenuto=True,
            marcato=True, clarion=True), places=1)

    def test_loughnashade_is_what_allows_five_songs(self):
        # Loughnashade and Daurdabla carry Maximum songs +2; Marsyas carries none.
        self.assertEqual(effects.song_slots(10, 42, {mod.MAXIMUM_SONGS_BONUS: 2}, clarion=True), 5)
        self.assertEqual(effects.song_slots(10, 42, {}, clarion=True), 3)


if __name__ == "__main__":
    unittest.main()
