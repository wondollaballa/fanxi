"""The reforged item importer must keep the Bard song lines.

Migration 140 backfills the rows the old parser dropped, but the generator is the
source of truth for a future regeneration of 0092.  These checks fail if a new tooltip
spelling stops being recognised.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "import_reforged_item_data.py"
SOURCE = ROOT / "tools" / "data" / "reforged_item_stats.json"

_spec = importlib.util.spec_from_file_location("import_reforged_item_data", TOOL)
_importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_importer)

SONG_CAST, SONG_DURATION, SONG_RECAST = 455, 454, 833


def _mods(text: str) -> dict[int, int]:
    mods, _skills, _leftover = _importer.parse_description(text)
    return dict(mods)


class ReforgedSongStatsTest(unittest.TestCase):
    def test_both_cast_time_spellings(self):
        self.assertEqual(_mods("Song spellcasting time -16%")[SONG_CAST], 16)
        self.assertEqual(_mods("Song casting time -15%")[SONG_CAST], 15)

    def test_both_duration_spellings(self):
        self.assertEqual(_mods("Song effect duration +14%")[SONG_DURATION], 14)
        self.assertEqual(_mods("Song duration +15%")[SONG_DURATION], 15)

    def test_recast_delay_is_whole_seconds(self):
        self.assertEqual(_mods("Song recast delay -10")[SONG_RECAST], 10)

    def test_the_precast_pieces_keep_their_cast_time(self):
        documents = json.loads(SOURCE.read_text(encoding="utf-8"))
        for item_id, value in ((23429, 16), (23949, 15), (24107, 10)):
            description = documents[str(item_id)]["description"]
            self.assertEqual(_mods(description)[SONG_CAST], value, item_id)

    def test_the_song_duration_and_recast_pieces_keep_their_lines(self):
        documents = json.loads(SOURCE.read_text(encoding="utf-8"))
        for item_id, mod_id, value in ((23496, SONG_DURATION, 14),
                                       (24084, SONG_DURATION, 15),
                                       (23630, SONG_RECAST, 10)):
            description = documents[str(item_id)]["description"]
            self.assertEqual(_mods(description)[mod_id], value, item_id)

    def test_family_song_plus_lines(self):
        self.assertEqual(_mods('"March"+1')[443], 1)
        self.assertEqual(_mods('"Minuet"+1')[434], 1)
        self.assertEqual(_mods('"Scherzo"+1')[451], 1)

    def test_the_family_song_pieces_keep_their_bonus(self):
        documents = json.loads(SOURCE.read_text(encoding="utf-8"))
        for item_id, mod_id, value in ((23429, 438, 1),    # Madrigal
                                       (23496, 434, 1),    # Minuet
                                       (23563, 443, 1),    # March
                                       (23630, 442, 1),    # Ballad
                                       (23697, 451, 1),    # Scherzo
                                       (23904, 435, 2),    # Paeon
                                       (23994, 440, 2)):   # Lullaby
            description = documents[str(item_id)]["description"]
            self.assertEqual(_mods(description)[mod_id], value, item_id)


if __name__ == "__main__":
    unittest.main()
