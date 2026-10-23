"""GearSwap library helpers: job detection, flattening, Lua output and versions."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import support  # noqa: F401

from fanxi_launcher.gear import (
    GearError, apply_set, clean_items, default_file, defaults_dir, downloads_dir,
    flatten_sets, flatten_sets_detailed, job_abbr, job_from_character, job_from_state,
    lua_path, normalize_set_path,
    path_conflict, save_version, serialize_library, strip_version_suffix,
    unique_version_path, versioned_name, write_profile_snapshot,
)

WHEN = datetime(2026, 10, 21, 9, 23, 19)


class JobTest(unittest.TestCase):
    def test_state_job(self):
        info = job_from_state({"player": {"job": 13, "level": 99, "name": "Onedough"}})
        self.assertEqual((info.abbr, info.name, info.level, info.character),
                         ("NIN", "Ninja", 99, "Onedough"))
        self.assertEqual(info.label, "NIN · Ninja · Lv 99")

    def test_missing_or_unknown_job(self):
        self.assertIsNone(job_from_state(None))
        self.assertIsNone(job_from_state({}))
        self.assertIsNone(job_from_state({"player": {"job": 0}}))
        self.assertIsNone(job_from_state({"player": {"job": 99}}))

    def test_saved_character_job(self):
        info = job_from_character({"main_job": 20, "main_level": 75, "name": "Mule"})
        self.assertEqual((info.abbr, info.level, info.character), ("SCH", 75, "Mule"))
        self.assertIsNone(job_from_character(None))
        self.assertIsNone(job_from_character({"main_job": 0}))
        self.assertIsNone(job_from_character({"main_job": 50}))

    def test_job_abbr(self):
        self.assertEqual(job_abbr(7), "PLD")
        self.assertEqual(job_abbr("run"), "RUN")
        self.assertEqual(job_abbr(99), "")


class FlattenTest(unittest.TestCase):
    def test_leaves_and_aliases(self):
        tree = {
            "idle": {},
            "idle": {
                "pdt": {"head": "Nyame Helm", "left_ear": "Tuisto Earring"},
            },
            "midcast": {"Enfeebling Magic": {"body": {"name": "Nyame Mail"},
                                             "ring2": "Dingir Ring"}},
        }
        sets = flatten_sets(tree)
        self.assertEqual(sets["sets.idle.pdt"]["head"], "Nyame Helm")
        self.assertEqual(sets["sets.idle.pdt"]["ear1"], "Tuisto Earring")
        self.assertEqual(sets["sets.midcast.Enfeebling Magic"]["body"], "Nyame Mail")
        self.assertNotIn("sets.idle", sets)

    def test_augmented_item_tables_keep_name(self):
        tree = {"idle": {"pdt": {
            "back": {"name": "Cichol's Mantle",
                     "augments": ["HP+60", "Phys. dmg. taken-10%"]},
            "neck": {"name": "Unmoving Collar +1", "augments": ["DEF+30", "HP+200"]},
            "head": "Nyame Helm",
        }}}
        sets = flatten_sets(tree)
        self.assertEqual(sets["sets.idle.pdt"]["back"], "Cichol's Mantle")
        self.assertEqual(sets["sets.idle.pdt"]["neck"], "Unmoving Collar +1")
        self.assertEqual(sets["sets.idle.pdt"]["head"], "Nyame Helm")

    def test_detailed_flatten_keeps_augments(self):
        tree = {"idle": {"dt": {
            "head": {"name": "Nyame Helm",
                     "augments": ["Acc/Rng. Acc./M. Acc.+30", "Store TP+13",
                                  "Phys. dmg. limit +5%", "Crit.hit rate+10%"]},
            "back": "Aptitude Mantle",
        }}}
        details = flatten_sets_detailed(tree)
        head = details["sets.idle.dt"]["head"]
        self.assertEqual(head["name"], "Nyame Helm")
        self.assertEqual(len(head["augments"]), 4)
        self.assertEqual(details["sets.idle.dt"]["back"],
                         {"name": "Aptitude Mantle", "augments": []})
        # lupa hands back 1-based Lua arrays as dicts.
        tree["idle"]["dt"]["neck"] = {
            "name": "Unmoving Collar +1",
            "augments": {1: "DEF+30", 2: "HP+200"},
        }
        neck = flatten_sets_detailed(tree)["sets.idle.dt"]["neck"]
        self.assertEqual(neck["augments"], ["DEF+30", "HP+200"])

    def test_slot_bearing_parent_stops(self):
        tree = {"idle": {"head": "Nyame Helm", "pdt": {"head": "Sakpata's Helm"}}}
        sets = flatten_sets(tree)
        self.assertEqual(list(sets), ["sets.idle"])

    def test_empty_tables_are_ignored(self):
        self.assertEqual(flatten_sets({"idle": {}, "engaged": {}}), {})

    def test_ranged_group_is_not_a_slot(self):
        tree = {"ranged": {"tp": {"range": "Annihilator", "ammo": "Chrono Bullet"},
                           "acc": {"range": "Annihilator"}}}
        sets = flatten_sets(tree)
        self.assertEqual(sets["sets.ranged.tp"]["range"], "Annihilator")
        self.assertEqual(sets["sets.ranged.tp"]["ammo"], "Chrono Bullet")
        self.assertIn("sets.ranged.acc", sets)


class PathTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_set_path("idle.pdt"), "sets.idle.pdt")
        self.assertEqual(normalize_set_path(" sets.idle.pdt "), "sets.idle.pdt")
        self.assertEqual(normalize_set_path("WS.Savage Blade"), "sets.WS.Savage Blade")

    def test_bad_paths(self):
        for value in ("", "sets", "sets..pdt", "sets.idle.", "sets.mid[cast]", 'sets.a"b'):
            with self.assertRaises(GearError):
                normalize_set_path(value)

    def test_lua_path_quotes_non_identifiers(self):
        self.assertEqual(lua_path("sets.idle.pdt"), "sets.idle.pdt")
        self.assertEqual(lua_path("sets.midcast.Enfeebling Magic"),
                         'sets.midcast["Enfeebling Magic"]')
        self.assertEqual(lua_path("sets.WS.Blade: Hi"), 'sets.WS["Blade: Hi"]')
        self.assertEqual(lua_path("sets.JA.Song's End"), "sets.JA[\"Song's End\"]")

    def test_conflicts(self):
        existing = ["sets.idle.pdt", "sets.engaged.tp"]
        self.assertEqual(path_conflict("sets.idle", existing), "sets.idle.pdt")
        self.assertEqual(path_conflict("sets.idle.pdt.more", existing), "sets.idle.pdt")
        self.assertIsNone(path_conflict("sets.idle.mdt", existing))
        self.assertIsNone(path_conflict("sets.idle.pdt", existing))


class ItemsTest(unittest.TestCase):
    def test_clean_and_order(self):
        items = clean_items({"back": "Cichol's Mantle", "head": " Nyame Helm ",
                             "left_ring": "", "ring1": "Defending Ring"})
        self.assertEqual(list(items), ["head", "ring1", "back"])
        self.assertEqual(items["head"], "Nyame Helm")

    def test_unknown_slot(self):
        with self.assertRaises(GearError):
            clean_items({"hat": "Nyame Helm"})

    def test_line_break(self):
        with self.assertRaises(GearError):
            clean_items({"head": "Nyame\nHelm"})


class SerializeTest(unittest.TestCase):
    def test_output(self):
        sets = {
            "sets.idle.pdt": {"head": "Nyame Helm", "back": "Cichol's Mantle"},
            "sets.WS.Savage Blade": {"main": "Naegling", "sub": "Genbu's Shield"},
        }
        text = serialize_library(sets, character="Onedough", job="WAR",
                                 source="defaults", when=WHEN)
        self.assertIn("Onedough WAR", text)
        self.assertIn("2026-10-21 09:23:19", text)
        self.assertIn("sets.idle = {}", text)
        self.assertLess(text.index("sets.idle = {}"), text.index("sets.idle.pdt = {"))
        self.assertIn("sets.WS = {}", text)
        self.assertIn("sets.idle.pdt = {", text)
        self.assertIn('sets.WS["Savage Blade"] = {', text)
        self.assertIn('head = "Nyame Helm",', text)
        self.assertIn("local function combine", text)
        self.assertIn("function get_sets()", text)
        self.assertTrue(text.rstrip().endswith(
            "-- Fanxi saves a new timestamped copy; this file was never the source."))

    def test_lua_escaping_and_header_close(self):
        text = serialize_library(
            {"sets.idle.pdt": {"head": 'A "B" \\ C'}},
            character="One", job="WAR", source="x]]y", when=WHEN)
        self.assertIn('head = "A \\"B\\" \\\\ C",', text)
        self.assertIn("Source: x] ]y", text)

    def test_slot_order(self):
        text = serialize_library({"sets.idle.pdt": {"back": "Cape", "main": "Sword"}},
                                 when=WHEN)
        self.assertLess(text.index("main ="), text.index("back ="))

    def test_prefix_conflict_rejected(self):
        with self.assertRaises(GearError):
            serialize_library({"sets.idle": {"head": "A"}, "sets.idle.pdt": {"head": "B"}})


class VersionTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(versioned_name("Onedough-WAR", when=WHEN),
                         "Onedough-WAR-20261021-092319.lua")
        self.assertEqual(versioned_name("Onedough-WAR-20261021-000000", when=WHEN),
                         "Onedough-WAR-20261021-092319.lua")
        self.assertEqual(strip_version_suffix("WAR-20261021-092319"), "WAR")
        self.assertEqual(versioned_name("bad name/here", when=WHEN),
                         "bad-name-here-20261021-092319.lua")

    def test_unique_and_save(self):
        with tempfile.TemporaryDirectory() as folder:
            first = unique_version_path(folder, "WAR", when=WHEN)
            first.write_text("x")
            second = unique_version_path(folder, "WAR", when=WHEN)
            self.assertEqual(second.name, "WAR-20261021-092319-2.lua")
            path = save_version(folder, {"sets.idle.town": {"head": "Nyame Helm"}},
                                base="Onedough-WAR", character="Onedough", job="WAR",
                                source="defaults", when=WHEN)
            self.assertEqual(path.name, "Onedough-WAR-20261021-092319.lua")
            self.assertIn("sets.idle.town", path.read_text())

    def test_profile_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_profile_snapshot(folder, {"sets.idle.town": {"head": "A"}},
                                          character="Onedough", job="WAR",
                                          source="defaults",
                                          version_path="Onedough-WAR-20261021-092319.lua",
                                          when=WHEN)
            payload = json.loads(path.read_text())
            self.assertEqual(payload["job"], "WAR")
            self.assertEqual(payload["sets"]["sets.idle.town"], {"head": "A"})
            self.assertEqual(path.name, "Onedough-WAR-20261021-092319.json")


class DefaultsTest(unittest.TestCase):
    def test_override_and_lookup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "WAR.lua").write_text("return {}", encoding="utf-8")
            with mock.patch.dict(os.environ, {"FANXI_GEARSWAP_DIR": folder}):
                self.assertEqual(defaults_dir(), root.resolve())
                self.assertEqual(default_file("WAR"), (root / "WAR.lua").resolve())
                self.assertIsNone(default_file("NIN"))

    def test_downloads_override(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {"FANXI_DOWNLOADS_DIR": folder}):
                self.assertEqual(downloads_dir(), Path(folder).resolve())


class ApplyTest(unittest.TestCase):
    def test_add_rename_and_duplicate(self):
        sets = {"sets.idle.pdt": {"head": "A"}}
        apply_set(sets, "sets.idle.mdt", {"head": "B"})
        self.assertIn("sets.idle.mdt", sets)
        apply_set(sets, "sets.idle.dt", {"head": "C"}, original_path="sets.idle.mdt")
        self.assertNotIn("sets.idle.mdt", sets)
        self.assertIn("sets.idle.dt", sets)
        apply_set(sets, "sets.engaged.tp", {"head": "D"}, original_path="sets.idle.dt",
                  keep_original=True)
        self.assertIn("sets.idle.dt", sets)
        self.assertIn("sets.engaged.tp", sets)
        with self.assertRaises(GearError):
            apply_set(sets, "sets.idle.dt", {"head": "D2"}, original_path="sets.idle.dt",
                      keep_original=True)

    def test_conflicts_and_empty(self):
        sets = {"sets.idle.pdt": {"head": "A"}}
        with self.assertRaises(GearError):
            apply_set(sets, "sets.idle", {"head": "B"})
        with self.assertRaises(GearError):
            apply_set(sets, "sets.idle.other", {})


if __name__ == "__main__":
    unittest.main()
