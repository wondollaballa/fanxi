"""Oseem Arcane Glyptics augments (the standard 5-slot Reisenjima block)."""

import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from server.fanxi_server.game import augment_stats, capes, glyptics  # noqa: E402


def herculean_helm() -> dict:
    return next(item for item in glyptics.entries()
                if item["name"] == "Herculean Helm")


class GlypticsCatalogTest(unittest.TestCase):
    def test_armor_and_weapons_are_both_there(self):
        entries = glyptics.entries()
        self.assertEqual(len(entries), 39)
        self.assertEqual(sum(1 for item in entries if item["kind"] == "armor"), 25)
        self.assertEqual(sum(1 for item in entries if item["kind"] == "weapon"), 14)
        names = {item["name"] for item in entries}
        for name in ("Chironic Hat", "Herculean Helm", "Merlinic Hood",
                     "Odyssean Helm", "Valorous Mask", "Aganoshe", "Zulfiqar"):
            self.assertIn(name, names, name)

    def test_the_five_armor_sets_and_their_paths(self):
        paths = {item["name"]: sorted(item["paths"]) for item in glyptics.entries()
                 if item["kind"] == "armor"}
        self.assertEqual(paths["Chironic Hat"], ["healing", "melee"])
        self.assertEqual(paths["Herculean Helm"], ["familiar", "magic", "melee", "ranged"])
        self.assertEqual(paths["Merlinic Hood"], ["familiar", "magic"])
        self.assertEqual(paths["Odyssean Helm"], ["magic", "melee"])
        self.assertEqual(paths["Valorous Mask"], ["familiar", "melee"])

    def test_every_offered_stat_is_encodable(self):
        for item in glyptics.entries():
            for path_key, path in item["paths"].items():
                for row in path["stats"]:
                    self.assertIn(row["key"], glyptics.STATS, (item["name"], path_key, row))
                    limit = glyptics.max_value(row["key"])
                    value = max(-limit, min(limit, int(row["max"])))
                    if value == 0:
                        continue
                    word = glyptics.slot_word(row["key"], value)
                    self.assertLessEqual(word[0], 0x7FF, (item["name"], path_key, row))
                    self.assertLessEqual(word[1], 0x1F, (item["name"], path_key, row))

    def test_herculean_magic_row_matches_the_wiki(self):
        helm = herculean_helm()
        magic = {row["key"]: row["max"] for row in helm["paths"]["magic"]["stats"]}
        self.assertEqual(magic["macc"], 35)
        self.assertEqual(magic["mab"], 35)
        self.assertEqual(magic["wsd"], 5)
        self.assertEqual(magic["str"], 15)  # Taupe maximum

    def test_unavailable_stats_are_not_offered(self):
        helm = herculean_helm()
        melee = {row["key"] for row in helm["paths"]["melee"]["stats"]}
        familiar = {row["key"] for row in helm["paths"]["familiar"]["stats"]}
        self.assertIn("ta", melee)          # Melee Triple Attack
        self.assertNotIn("ta", familiar)    # Familiar has its own table
        self.assertNotIn("wsd", familiar)
        merlinic = next(item for item in glyptics.entries()
                        if item["name"] == "Merlinic Hood")
        pets = {row["key"] for row in merlinic["paths"]["familiar"]["stats"]}
        self.assertIn("pet_mab", pets)
        self.assertNotIn("pet_mab", melee)


class GlypticsEncodingTest(unittest.TestCase):
    def test_block_is_the_standard_five_slot_layout(self):
        block = glyptics.encode([
            {"key": "acc", "value": 40},
            {"key": "mab", "value": 40},
            {"key": "str", "value": 15},
            {"key": "pdt", "value": -5},
            {"key": "wsd", "value": 4},
        ])
        self.assertEqual(len(block), 24)
        self.assertEqual(block[0], capes.AUGMENT_KIND)
        self.assertEqual(block[1], capes.AUGMENT_SUBKIND)
        slots = capes.decode(block)
        self.assertEqual(slots[0], {"id": 0x03E, "value": 7})   # Accuracy +33 + 7
        self.assertEqual(slots[1], {"id": 0x046, "value": 7})   # MAB + MAcc 40
        self.assertEqual(slots[2], {"id": 0x200, "value": 14})  # STR 1 + 14
        self.assertEqual(slots[3], {"id": 0x036, "value": 4})   # PDT -1..-32
        self.assertEqual(slots[4], {"id": 0x147, "value": 3})   # WSD +4%

    def test_describe_shows_the_combined_magic_row(self):
        block = glyptics.encode([
            {"key": "mab", "value": 40}, {"key": "acc", "value": 40},
            {"key": "pdt", "value": -5}, {"key": "enmity", "value": -8},
            {"key": "stp", "value": 10},
        ])
        self.assertEqual(
            glyptics.describe(block),
            "Magic Attack Bonus+40 Magic Accuracy+40 | Accuracy+40 | "
            "Physical Damage Taken-5% | Enmity-8 | Store TP+10")

    def test_round_trip_of_every_path_and_stat(self):
        for item in glyptics.entries():
            for path_key, path in item["paths"].items():
                picks = []
                for row in path["stats"][:5]:
                    limit = glyptics.max_value(row["key"])
                    picks.append({"key": row["key"],
                                  "value": max(-limit, min(limit, row["max"]))})
                block = glyptics.encode(picks)
                decoded = glyptics.decode(block)
                self.assertEqual(len(decoded), 5, (item["name"], path_key))
                for pick, slot in zip(picks, decoded):
                    self.assertEqual(slot["rows"][0]["key"], pick["key"],
                                     (item["name"], path_key, pick))
                    self.assertEqual(slot["rows"][0]["value"], pick["value"],
                                     (item["name"], path_key, pick))

    def test_empty_slots_are_written_as_zero(self):
        block = glyptics.encode([{"key": "acc", "value": 25}])
        self.assertEqual(capes.decode(block),
                         [{"id": 0x017, "value": 24}, {"id": 0, "value": 0},
                          {"id": 0, "value": 0}, {"id": 0, "value": 0},
                          {"id": 0, "value": 0}])

    def test_stat_sheet_reads_the_block(self):
        block = glyptics.encode([
            {"key": "mab", "value": 40}, {"key": "acc", "value": 40},
            {"key": "pdt", "value": -5}, {"key": "da", "value": 5},
            {"key": "wsd", "value": 5},
        ])
        mods = augment_stats.item_mods(25642, block)
        self.assertEqual(mods[28], 40)    # MAB
        self.assertEqual(mods[30], 40)    # MAcc from the combined id
        self.assertEqual(mods[25], 40)    # Accuracy
        self.assertEqual(mods[161], -500)  # PDT in hundredths
        self.assertEqual(mods[288], 5)    # Double Attack
        self.assertEqual(mods[840], 5)    # Weapon Skill Damage

    def test_value_limits(self):
        with self.assertRaises(ValueError):
            glyptics.slot_word("acc", 65)
        with self.assertRaises(ValueError):
            glyptics.slot_word("pet_mab", 40)  # no offset-33 id for pet MAB
        self.assertEqual(glyptics.max_value("pet_mab"), 32)
        self.assertEqual(glyptics.max_value("acc"), 64)


class GlypticsServiceTest(unittest.TestCase):
    def setUp(self):
        from support import make_service

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]
        self.service.top_off_gil(self.character_id)

    def _buy(self, item_id: int) -> dict:
        self.service.armory_add(self.character_id, item_id, 1)
        return self.service.character_data(self.character_id)

    def test_catalog_lists_the_whole_page_and_marks_the_owned_copy(self):
        empty = self.service.character_data(self.character_id)["glyptics"]
        self.assertEqual(len(empty["items"]), 39)
        self.assertFalse(any(item["owned"] for item in empty["items"]))
        data = self._buy(25642)
        card = data["glyptics"]
        item = next(entry for entry in card["items"] if entry["owned"])
        self.assertEqual(item["name"], "Herculean Helm")
        self.assertTrue(item["owned"])
        self.assertEqual(len(item["copies"]), 1)
        paths = card["path_sets"][item["path_key"]]["paths"]
        self.assertTrue(paths["melee"]["defaults"])

    def test_apply_and_clear(self):
        self._buy(25642)
        helm = next(entry for entry in self.service.character_data(self.character_id)["glyptics"]["items"]
                    if entry["name"] == "Herculean Helm")
        copy = helm["copies"][0]
        choices = [
            {"key": "acc", "value": 40}, {"key": "ta", "value": 4},
            {"key": "str", "value": 15}, {"key": "attack", "value": 40},
            {"key": "wsd", "value": 5},
        ]
        glyptics.apply(self.service, self.character_id, copy["container"], copy["slot"],
                       "melee", choices)
        data = self.service.character_data(self.character_id)
        current = next(entry for entry in data["glyptics"]["items"]
                       if entry["name"] == "Herculean Helm")["copies"][0]
        self.assertIn("Accuracy+40", current["current"])
        self.assertEqual(len([text for text in current["slots"] if text]), 5)
        self.assertEqual(current["selection"][0], {"key": "acc", "value": 40})

        glyptics.clear(self.service, self.character_id, copy["container"], copy["slot"])
        data = self.service.character_data(self.character_id)
        current = next(entry for entry in data["glyptics"]["items"]
                       if entry["name"] == "Herculean Helm")["copies"][0]
        self.assertEqual(current["current"], "not augmented")

    def test_apply_rejects_a_stat_outside_the_path(self):
        self._buy(25642)
        helm = next(entry for entry in self.service.character_data(self.character_id)["glyptics"]["items"]
                    if entry["name"] == "Herculean Helm")
        copy = helm["copies"][0]
        with self.assertRaises(ValueError):
            glyptics.apply(self.service, self.character_id, copy["container"], copy["slot"],
                           "familiar", [{"key": "wsd", "value": 5}])
        with self.assertRaises(ValueError):
            glyptics.apply(self.service, self.character_id, copy["container"], copy["slot"],
                           "melee", [])


if __name__ == "__main__":
    unittest.main()
