"""Reive and Incursion JSE capes (Detrovio's Refractive Crystal augments)."""

import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from support import make_service  # noqa: E402

from fanxi_server.game import augment_stats, capes, modifiers as mod, reive  # noqa: E402

# The client tooltip text at each cape's strongest value, in the order the
# four rows appear on BG Wiki's Reive and Incursion table.
EXPECTED = {
    "WAR": ["STR+5", "DEX+5", "Accuracy+7", "Crit. hit damage+3%"],
    "MNK": ["STR+5", "DEX+5", '"Counter"+5', "Subtle Blow+5"],
    "WHM": ["Mag. Acc.+10", "Healing magic skill+10",
            "Enhancing magic skill+10", '"Cure Potency"+5%'],
    "BLM": ["Mag.Atk.Bns.+5", "Elemental magic skill+10",
            "Dark magic skill+10", "Fast Cast+5"],
    "RDM": ["Mag. Acc.+10", "Enfeebling magic skill+10",
            "Enhancing magic skill+10", "Enh. Mag. eff. dur.+20%"],
    "THF": ["DEX+5", "AGI+5", "Dual Wield+5", "Crit. hit damage+3%"],
    "PLD": ["DEX+5", "VIT+5", "Enmity+7", "Phalanx+5"],
    "DRK": ["Attack+15", "Dark magic skill+10",
            '"Drain" and "Aspir" potency+25', "Weapon skill damage+5%"],
    "BST": ["STR+5 DEX+5", "Accuracy+5",
            "Pet: Damage taken-5%", "Pet: Accuracy+20 Pet: Rng. Acc.+20"],
    "BRD": ["HP+30", "Mag. Acc.+7", "Enmity-10", "Damage taken-3%"],
    "RNG": ["STR+5", "AGI+5", '"Store TP"+3', '"Snapshot"+3'],
    "SAM": ["STR+5", '"Store TP"+3', "Zanshin+5", "Meditate effect duration+8"],
    "NIN": ["STR+5", "DEX+5", "Skillchain dmg.+5%", "Weapon skill damage+5%"],
    "DRG": ["STR+5", "Weapon skill damage+5%",
            "Pet: Damage taken-5%", "Pet: Breath+10"],
    "SMN": ["Summoning magic skill+5", "Blood Pact Dmg.+5",
            "Blood Pact recast time II-3", "Pet: Enmity+15"],
    "BLU": ["MP+30", "DEX+5", "Accuracy+7", "Blue Magic skill+10"],
    "COR": ["Mag.Atk.Bns.+5", "Enmity-5",
            '"Phantom Roll" ability delay-5', "Weapon skill damage+5%"],
    "PUP": ["STR+5", "DEX+5", "Martial Arts+20", "Pet: TP Bonus+500"],
    "DNC": ['"Store TP"+5', "Dual Wield+5", "Reverse Flourish+30",
            "Weapon skill damage+5%"],
    "SCH": ["INT+5", "MND+5", "Helix effect duration+20",
            '"Regen" potency+10'],
    "GEO": ["Geomancy skill+10", "Indi Effect Duration+20",
            "Damage taken-5%", "Pet: Damage taken-5%"],
    "RUN": ['"Dbl.Atk."+5', "Enmity+7", "Embolden+15%", "Damage taken-5%"],
}


class ReiveTableTest(unittest.TestCase):
    def test_all_22_job_capes(self):
        self.assertEqual(len(reive.JOBS), 22)
        self.assertEqual(list(reive.JOBS), [
            "WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK", "BST",
            "BRD", "RNG", "SAM", "NIN", "DRG", "SMN", "BLU", "COR", "PUP",
            "DNC", "SCH", "GEO", "RUN"])
        self.assertEqual(reive.JOBS["WAR"]["name"], "Mauler's Mantle")
        self.assertEqual(reive.JOBS["RUN"]["name"], "Evasionist's Cape")
        self.assertEqual(len(reive.CAPE_IDS), 22)
        self.assertEqual(reive.CAPE_IDS, frozenset(range(28617, 28639)))
        self.assertEqual(reive.SLOTS, 4)

    def test_lookup_by_item_and_name(self):
        self.assertEqual(reive.entry_for_item(28617)[0], "WAR")
        self.assertEqual(reive.entry_for_item(28638)[0], "RUN")
        self.assertIsNone(reive.entry_for_item(26246))  # an Ambuscade cape
        self.assertEqual(reive.entry_for_name("Bane Cape")[0], "BLM")
        self.assertIsNone(reive.entry_for_name("Cichol's Mantle"))

    def test_every_cape_has_four_rows(self):
        for job, entry in reive.JOBS.items():
            self.assertEqual(len(entry["rows"]), 4, job)
            keys = [row["key"] for row in entry["rows"]]
            self.assertEqual(len(keys), len(set(keys)), job)
            self.assertEqual([i for i, _row in enumerate(entry["rows"])], [0, 1, 2, 3])

    def test_every_value_fits_the_standard_five_bit_word(self):
        for job, entry in reive.JOBS.items():
            for row in entry["rows"]:
                values = reive.row_values(row)
                self.assertTrue(values, (job, row["key"]))
                for value in values:
                    augment_id, stored = reive.row_slot(row, value)
                    self.assertLessEqual(augment_id, 0x7FF, (job, row["key"]))
                    self.assertGreaterEqual(stored, 0, (job, row["key"]))
                    self.assertLessEqual(stored, 0x1F, (job, row["key"]))
                    self.assertFalse(reive.row_text(row, value).startswith("id "),
                                     (job, row["key"], value))

    def test_maximum_tooltips_match_the_wiki_rows(self):
        for job, entry in reive.JOBS.items():
            shown = []
            for row in entry["rows"]:
                values = reive.row_values(row)
                best = values[0] if values[-1] < 0 else values[-1]
                shown.append(reive.row_text(row, best))
            self.assertEqual(shown, EXPECTED[job], job)

    def test_a_full_block_fills_the_first_four_slots(self):
        for job, entry in reive.JOBS.items():
            choices = {row["key"]: reive.row_values(row)[-1] for row in entry["rows"]}
            block = reive.encode(entry, choices)
            self.assertEqual(len(block), 24, job)
            self.assertEqual(block[0:2], b"\x02\x03", job)
            self.assertEqual(block[12:], b"\0" * 12, job)
            words = reive.current_slots(block)
            self.assertEqual(len(words), 5, job)
            self.assertEqual(words[4], (0, 0), job)
            for index, row in enumerate(entry["rows"]):
                self.assertEqual(words[index], reive.row_slot(
                    row, choices[row["key"]]), (job, row["key"]))

    def test_a_full_block_round_trips_every_row(self):
        for job, entry in reive.JOBS.items():
            choices = {row["key"]: reive.row_values(row)[0] for row in entry["rows"]}
            words = reive.current_slots(reive.encode(entry, choices))
            for index, row in enumerate(entry["rows"]):
                slot = {"id": words[index][0], "value": words[index][1]}
                self.assertEqual(reive.selection_for_row(row, slot),
                                 choices[row["key"]], (job, row["key"]))

    def test_a_subset_keeps_the_rows_it_does_not_name(self):
        war = reive.JOBS["WAR"]
        current = [(0x200, 4), (0x201, 4), (0x017, 6), (0x148, 2), (0, 0)]
        merged = reive.merge_choices(war, {"accuracy": 3}, current)
        self.assertEqual(merged[0], (0x200, 4))
        self.assertEqual(merged[1], (0x201, 4))
        self.assertEqual(merged[2], (0x017, 2))   # Accuracy+3
        self.assertEqual(merged[3], (0x148, 2))
        self.assertEqual(merged[4], (0, 0))

    def test_an_explicit_null_clears_one_row(self):
        war = reive.JOBS["WAR"]
        current = [(0x200, 4), (0x201, 4), (0x017, 6), (0x148, 2), (0, 0)]
        merged = reive.merge_choices(war, {"dex": None}, current)
        self.assertEqual(merged[1], (0, 0))
        self.assertEqual(merged[0], (0x200, 4))

    def test_the_fifth_slot_is_preserved(self):
        war = reive.JOBS["WAR"]
        current = [(0, 0), (0, 0), (0, 0), (0, 0), (0x170, 4)]
        block = reive.encode(war, {"str": 5}, current)
        words = reive.current_slots(block)
        self.assertEqual(words[0], (0x200, 4))
        self.assertEqual(words[4], (0x170, 4))

    def test_reduction_rows_are_marked_as_reductions(self):
        for job, entry in reive.JOBS.items():
            for row in entry["rows"]:
                if int(row["minimum"]) < 0:
                    self.assertEqual(int(row["multiplier"]), -1, (job, row["key"]))
                    with self.assertRaises(ValueError):
                        reive.row_slot(row, abs(int(row["minimum"])))
                else:
                    with self.assertRaises(ValueError):
                        reive.row_slot(row, -1)

    def test_negative_rows_use_the_reduction_id(self):
        brd = reive.JOBS["BRD"]
        enmity = reive.row_by_key(brd, "enmity")
        self.assertEqual(reive.row_slot(enmity, -10), (0x028, 9))
        self.assertEqual(reive.row_slot(enmity, -1), (0x028, 0))
        run = reive.JOBS["RUN"]
        positive = reive.row_by_key(run, "enmity")
        self.assertEqual(reive.row_slot(positive, 7), (0x027, 6))
        self.assertEqual(reive.row_text(enmity, -10), "Enmity-10")

    def test_bst_uses_the_combined_str_dex_word(self):
        row = reive.row_by_key(reive.JOBS["BST"], "str_dex")
        self.assertEqual(reive.row_slot(row, 1), (0x226, 0))
        self.assertEqual(reive.row_text(row, 1), "STR+1 DEX+1")
        self.assertEqual(reive.row_text(row, 5), "STR+5 DEX+5")

    def test_pet_tp_bonus_uses_the_twenty_point_step(self):
        row = reive.row_by_key(reive.JOBS["PUP"], "pet_tp_bonus")
        self.assertEqual(reive.row_values(row),
                         [100, 120, 140, 160, 180, 200, 220, 240, 260, 280,
                          300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500])
        self.assertEqual(reive.row_slot(row, 100), (0x07A, 4))
        self.assertEqual(reive.row_text(row, 500), "Pet: TP Bonus+500")

    def test_bad_rows_and_values_are_rejected(self):
        war = reive.JOBS["WAR"]
        with self.assertRaises(ValueError):
            reive.row_slot(reive.row_by_key(war, "accuracy"), 8)
        with self.assertRaises(ValueError):
            reive.row_slot(reive.row_by_key(war, "accuracy"), 4.5)
        self.assertIsNone(reive.row_by_key(war, "nope"))
        with self.assertRaises(ValueError):
            reive.merge_choices(war, {"nope": 1})
        with self.assertRaises(ValueError):
            reive.encode(war, {"str": None, "dex": None,
                               "accuracy": None, "crit_damage": None})


class ReiveServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]

    def _cape(self, job):
        data = self.service.character_data(self.character_id)
        return next(entry for entry in data["reive"]["capes"] if entry["job"] == job)

    def _copy(self, job):
        return self._cape(job)["copies"][0]

    def test_catalog_lists_every_cape_before_anything_is_owned(self):
        war = self._cape("WAR")
        self.assertEqual(war["owned"], 0)
        self.assertEqual(len(war["rows"]), 4)
        self.assertEqual(war["rows"][2]["best"], 7)
        self.assertEqual(self._cape("BRD")["rows"][2]["best"], -10)

    def test_augment_all_four_rows_and_clear(self):
        self.service.add_item(self.character_id, 28617)  # Mauler's Mantle
        copy = self._copy("WAR")
        result = reive.apply(self.service, self.character_id, copy["container"],
                             copy["slot"], {
                                 "str": 5, "dex": 5, "accuracy": 7,
                                 "crit_damage": 3,
                             })
        self.assertEqual(result["text"],
                         "STR+5, DEX+5, Accuracy+7, Crit. hit damage+3%")

        copy = self._copy("WAR")
        self.assertEqual(copy["current"]["text"],
                         "STR+5, DEX+5, Accuracy+7, Crit. hit damage+3%")
        self.assertEqual(copy["current"]["selection"],
                         {"str": 5, "dex": 5, "accuracy": 7, "crit_damage": 3})
        self.assertEqual(copy["current"]["slots"][0]["id"], 0x200)
        self.assertEqual(copy["current"]["slots"][3]["id"], 0x148)
        self.assertEqual(copy["current"]["slots"][4]["id"], 0)

        reive.clear(self.service, self.character_id, copy["container"], copy["slot"])
        copy = self._copy("WAR")
        self.assertEqual(copy["current"]["text"], "not augmented")
        self.assertEqual(copy["current"]["selection"],
                         {"str": None, "dex": None, "accuracy": None,
                          "crit_damage": None})

    def test_a_subset_edit_keeps_the_other_rows(self):
        self.service.add_item(self.character_id, 28617)
        copy = self._copy("WAR")
        reive.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {"str": 5, "accuracy": 7})
        copy = self._copy("WAR")
        self.assertEqual(copy["current"]["selection"],
                         {"str": 5, "dex": None, "accuracy": 7,
                          "crit_damage": None})

        reive.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {"dex": 3, "accuracy": None})
        copy = self._copy("WAR")
        self.assertEqual(copy["current"]["selection"],
                         {"str": 5, "dex": 3, "accuracy": None,
                          "crit_damage": None})
        self.assertEqual(copy["current"]["text"],
                         "STR+5, DEX+3")

    def test_negative_and_step_values_round_trip(self):
        self.service.add_item(self.character_id, 28626)  # Rhapsode's Cape
        copy = self._copy("BRD")
        reive.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {"dt": -3, "enmity": -10})
        self.assertEqual(self._copy("BRD")["current"]["text"],
                         "Enmity-10, Damage taken-3%")

        self.service.add_item(self.character_id, 28634)  # Dispersal Mantle
        copy = self._copy("PUP")
        reive.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {"pet_tp_bonus": 500})
        self.assertEqual(self._copy("PUP")["current"]["text"],
                         "Pet: TP Bonus+500")

    def test_apply_rejects_the_wrong_item_and_bad_choices(self):
        self.service.add_item(self.character_id, 26246)  # Ambuscade WAR cape
        wrong = next(item for item in self.service.inventory(self.character_id)
                     if int(item["item_id"]) == 26246)
        with self.assertRaises(ValueError):
            reive.apply(self.service, self.character_id, wrong["container"],
                        wrong["slot"], {"str": 5})

        self.service.add_item(self.character_id, 28617)
        copy = self._copy("WAR")
        with self.assertRaises(ValueError):
            reive.apply(self.service, self.character_id, copy["container"],
                        copy["slot"], {"nope": 5})
        with self.assertRaises(ValueError):
            reive.apply(self.service, self.character_id, copy["container"],
                        copy["slot"], {"accuracy": 8})
        with self.assertRaises(ValueError):
            reive.apply(self.service, self.character_id, copy["container"],
                        copy["slot"], {"str": None, "dex": None,
                                       "accuracy": None, "crit_damage": None})
        with self.assertRaises(ValueError):
            reive.apply(self.service, self.character_id, copy["container"],
                        copy["slot"], {})
        with self.assertRaises(LookupError):
            reive.clear(self.service, self.character_id, 99, 99)

    def test_the_stat_sheet_reads_the_block(self):
        self.service.add_item(self.character_id, 28617)
        copy = self._copy("WAR")
        block = reive.encode(reive.JOBS["WAR"], {
            "str": 5, "dex": 5, "accuracy": 7, "crit_damage": 3,
        })
        self.service.set_item_extra(self.character_id, copy["container"],
                                    copy["slot"], block)
        mods = augment_stats.item_mods(28617, block)
        self.assertEqual(mods[mod.STR], 5)
        self.assertEqual(mods[mod.DEX], 5)
        self.assertEqual(mods[mod.ACC], 7)
        self.assertEqual(mods[mod.CRIT_DMG_INCREASE], 3)
        self.assertEqual(augment_stats.describe_augments(28617, block),
                         "STR+5, DEX+5, Accuracy+7, Crit. hit damage+3%")


if __name__ == "__main__":
    unittest.main()
