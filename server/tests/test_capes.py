"""Ambuscade JSE cape augments (standard five-slot extdata)."""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.fanxi_server.game import capes  # noqa: E402


class CapeTest(unittest.TestCase):
    def test_every_build_is_a_five_slot_standard_block(self):
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                block = capes.encode(build, job)
                self.assertEqual(len(block), 24, (job, build))
                self.assertEqual(block[0], 0x02, (job, build))
                self.assertEqual(block[1], 0x03, (job, build))
                self.assertEqual(block[12:], b"\0" * 12, (job, build))

    def test_block_round_trips(self):
        block = capes.encode("tp")
        slots = capes.decode(block)
        self.assertEqual(slots[0], {"id": 0x201, "value": 19})   # DEX+20
        self.assertEqual(slots[1], {"id": 0x044, "value": 19})   # Accuracy+20 Attack+20
        self.assertEqual(slots[2], {"id": 0x017, "value": 9})    # Accuracy+10
        self.assertEqual(slots[3], {"id": 0x08E, "value": 9})    # Store TP+10
        self.assertEqual(slots[4], {"id": 0x036, "value": 9})    # Phys. dmg. taken-10%

    def test_ninja_build_only_ids(self):
        # The NIN-only stats resolve to the same client augment ids the
        # community extdata table uses.
        block = capes.encode("ninjutsu", "NIN")
        slots = capes.decode(block)
        self.assertEqual(slots[0], {"id": 0x204, "value": 19})   # INT+20
        self.assertEqual(slots[2], {"id": 0x204, "value": 9})    # INT+10
        self.assertEqual(slots[3], {"id": 0x085, "value": 9})    # Mag.Atk.Bns.+10
        self.assertEqual(capes.decode(capes.encode("dw", "NIN"))[3],
                         {"id": 0x092, "value": 9})              # Dual Wield+10
        self.assertEqual(capes.decode(capes.encode("fc", "NIN"))[3],
                         {"id": 0x08C, "value": 9})              # Fast Cast+10

    def test_hp_uses_the_offset_block_not_a_wide_value(self):
        # HP+60 is id 2 (offset 33) + value 27, because the value field is 5 bits.
        block = capes.encode("pdt")
        self.assertEqual(block[2:4], (0x002 | (27 << 11)).to_bytes(2, "little"))
        self.assertEqual(capes.decode(block)[0], {"id": 0x002, "value": 27})

    def test_describe_rebuilds_the_gearswap_strings(self):
        for job, entry in capes.JOBS.items():
            for build, names in entry["builds"].items():
                shown = capes.describe(capes.encode(build, job)).split(", ")
                self.assertEqual(len(shown), len(names), (job, build))
                for name, text in zip(names, shown):
                    self.assertEqual(_norm(name), _norm(text), (job, build))

    def test_every_augment_resolves_through_the_display_table(self):
        for name, (augment_id, value) in capes.AUGMENTS.items():
            self.assertIn(augment_id, capes.TABLE, name)
            self.assertNotIn("id ", capes._text(augment_id, value), name)

    def test_all_jobs_and_builds_are_present(self):
        self.assertEqual(len(capes.JOBS), 22)
        self.assertEqual(sum(len(entry["builds"]) for entry in capes.JOBS.values()), 198)
        self.assertEqual(capes.JOBS["WAR"]["cape_name"], "Cichol's Mantle")
        self.assertEqual(capes.JOBS["RUN"]["cape_name"], "Ogma's Cape")
        self.assertEqual(len(capes.CAPE_IDS), 22)

    def test_job_lookup(self):
        self.assertEqual(capes.job_for_item(26254), "BST")
        self.assertEqual(capes.job_for_item(26258), "NIN")
        self.assertEqual(capes.job_for_item(26253), "DRK")
        self.assertEqual(capes.job_for_item(26249), "BLM")
        self.assertEqual(capes.job_for_item(26246), "WAR")
        self.assertEqual(capes.job_for_item(26267), "RUN")
        self.assertIsNone(capes.job_for_item(1))
        self.assertEqual(capes.job_for_name("Andartia's Mantle"), "NIN")
        self.assertEqual(capes.job_for_name("Artio's Mantle"), "BST")
        self.assertEqual(capes.job_for_name("Ankou's Mantle"), "DRK")
        self.assertEqual(capes.job_for_name("Taranus's Cape"), "BLM")
        self.assertEqual(capes.job_for_name("Ogma's Cape"), "RUN")

    def test_black_mage_has_every_cape_build_the_library_uses(self):
        self.assertEqual(sorted(capes.JOBS["BLM"]["builds"]),
                         ["dt", "fcmp", "mabws", "macc", "maxhp", "mdt",
                          "nuke", "pdt", "tp"])

    def test_unknown_build_is_rejected(self):
        with self.assertRaises(ValueError):
            capes.encode("nope")
        with self.assertRaises(ValueError):
            capes.encode("tp", "XXX")

    def test_only_five_bits_of_value(self):
        # All values stay inside the 5-bit field, so the high byte keeps its id bits.
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                for slot in capes.decode(capes.encode(build, job)):
                    self.assertLessEqual(slot["value"], 0x1F)
                    self.assertLessEqual(slot["id"], 0x7FF)

    def test_migration_and_docs_are_in_sync(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import importlib

        gen = importlib.import_module("gen_capes")
        migration = gen.MIGRATION.read_text()
        self.assertEqual(gen.sql(), migration)
        self.assertEqual(gen.doc(), gen.DOC.read_text())
        # Every build is stored as its own copy with its own block.
        blocks = set(re.findall(r"X'([0-9A-F]{48})'", migration))
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                self.assertIn(capes.encode(build, job).hex().upper(), blocks, (job, build))


def _norm(text: str) -> str:
    """Compare augment text ignoring quoting and spacing."""
    return re.sub(r"[\s\"]", "", text)


if __name__ == "__main__":
    unittest.main()


class CapePickerTest(unittest.TestCase):
    """The Data page's BG Wiki material picker (not the 198 fixed builds)."""

    THREAD = [
        "HP+60", "MP+60", "STR+20", "DEX+20", "VIT+20", "AGI+20", "INT+20",
        "MND+20", "CHR+20",
        "Pet: Acc.+20 Pet: R.Acc.+20 Pet: Atk.+20 Pet: R.Atk.+20",
        "Pet: M.Acc.+20 Pet: M.Dmg.+20",
    ]
    DUST = [
        "Accuracy+20 Attack+20", "Rng.Acc.+20 Rng.Atk.+20",
        "Mag. Acc+20 /Mag. Dmg.+20", "Eva.+20 /Mag. Eva.+20",
    ]
    DYE = [
        "HP+20", "MP+20", "STR+10", "DEX+10", "VIT+10", "AGI+10", "INT+10",
        "MND+10", "CHR+10", "Accuracy+10", "Attack+10", "Rng.Acc.+10",
        "Rng.Atk.+10", "Mag. Acc.+10", "Magic Damage+10", "Evasion+10",
        "Mag. Evasion+10", "Pet: Accuracy+10 Pet: Rng. Acc.+10",
        "Pet: Attack+10 Pet: Rng.Atk.+10", "Pet: Mag. Acc.+10",
        "Pet: Magic Damage+10",
    ]
    SAP = [
        "Weapon skill damage+10%", "Crit.hit rate+10", '"Store TP"+10',
        '"Dbl.Atk."+10', "Haste+10", "Dual Wield+10", "Enmity+10",
        "Enmity-10", '"Snapshot"+10', "Mag.Atk.Bns.+10", "Fast Cast+10",
        '"Cure Potency"+10%', '"Waltz" potency+10%', 'Pet: "Regen"+10',
        "Pet: Haste+10",
    ]
    RESIN = [
        "DEF+50", "Evasion+15", "Mag. Evasion+15", "Phys. dmg. taken-10%",
        "Magic dmg. taken-10%", "Damage taken-5%", '"Regen"+5', '"Counter"+10',
        "Chance of successful block+5", "Parrying rate+5%",
        "Occ. inc. resist. to stat. ailments+10",
        "Spell interruption rate down-10%", "Pet: Phys. dmg. taken-10%",
        "Pet: Magic dmg. taken-10%", "Pet: Damage taken-5%",
        'Pet: "Regen"+5',
    ]
    EXPECTED = {"thread": THREAD, "dust": DUST, "dye": DYE, "sap": SAP,
                "resin": RESIN}

    def test_five_materials_in_the_client_slot_order(self):
        self.assertEqual([material["key"] for material in capes.MATERIALS],
                         ["thread", "dust", "dye", "sap", "resin"])
        self.assertEqual([material["slot"] for material in capes.MATERIALS],
                         [0, 1, 2, 3, 4])
        self.assertEqual([material["items_to_max"] for material in capes.MATERIALS],
                         [20, 20, 10, 10, 5])
        for material in capes.MATERIALS:
            self.assertEqual(material["max_stage"], material["items_to_max"])

    def test_option_keys_are_unique_per_material(self):
        for material in capes.MATERIALS:
            keys = [option["key"] for option in material["options"]]
            self.assertEqual(len(keys), len(set(keys)), material["key"])
            self.assertEqual(capes.MATERIAL_BY_KEY[material["key"]], material)

    def test_every_option_maximum_is_the_bgwiki_text(self):
        for material in capes.MATERIALS:
            shown = [capes.option_text(option, option["max_stage"])
                     for option in material["options"]]
            self.assertEqual(shown, self.EXPECTED[material["key"]],
                             material["key"])

    def test_every_stage_fits_the_five_bit_field(self):
        for material in capes.MATERIALS:
            for option in material["options"]:
                for stage in range(1, option["max_stage"] + 1):
                    augment_id, value = capes.option_slot(option, stage)
                    self.assertLessEqual(augment_id, 0x7FF)
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 0x1F)
                    self.assertEqual(capes.option_text(option, stage),
                                     capes.describe(capes._encode_slots(
                                         [(augment_id, value)])))
                self.assertEqual(capes.option_slot(option, 1)[1],
                                 0 if option.get("raw_mode") == "stage" else
                                 option["step"] - 1)

    def test_hp_and_mp_cross_into_the_second_offset_block(self):
        hp = next(option for option in capes.MATERIALS[0]["options"]
                  if option["key"] == "hp")
        self.assertEqual(capes.option_slot(hp, 10), (0x001, 29))  # HP+30
        self.assertEqual(capes.option_slot(hp, 11), (0x002, 0))   # HP+33
        self.assertEqual(capes.option_slot(hp, 20), (0x002, 27))  # HP+60

    def test_known_resin_words(self):
        def slot(option_key, stage):
            material = capes.MATERIAL_BY_KEY["resin"]
            option = next(o for o in material["options"] if o["key"] == option_key)
            return capes.option_slot(option, stage)

        self.assertEqual(slot("def", 5), (0x480, 4))
        self.assertEqual(slot("evasion", 5), (0x01F, 14))
        self.assertEqual(slot("pdt", 5), (0x036, 9))
        self.assertEqual(slot("dt", 5), (0x047, 4))
        self.assertEqual(slot("counter", 5), (0x091, 9))
        self.assertEqual(slot("status_resist", 5), (0x03D, 9))
        # A retail copy that used the dedicated Resin id is recognised too.
        material = capes.MATERIAL_BY_KEY["resin"]
        self.assertEqual(
            capes.selection_for_slot(material, {"id": 0x483, "value": 4}),
            {"option": "pdt", "stage": 5})

    def test_selecting_every_recognised_build_reproduces_its_block(self):
        """All non-pet builds round-trip through the picker unchanged."""
        pet_builds = {
            ("BST", "pet_dt"), ("BST", "pet_tp"),
            ("DRG", "pet_dt"),
            ("SMN", "pet_dt"), ("SMN", "pet_tp"),
            ("PUP", "pet_dt"), ("PUP", "pet_tp"),
        }
        for job, entry in capes.JOBS.items():
            for build in entry["builds"]:
                if (job, build) in pet_builds:
                    continue
                slots = capes.decode(capes.encode(build, job))
                choices = {}
                for material in capes.MATERIALS:
                    found = capes.selection_for_slot(material, slots[material["slot"]])
                    self.assertIsNotNone(found, (job, build, material["key"]))
                    choices[material["key"]] = found
                self.assertEqual(capes.encode_choices(choices),
                                 capes.encode(build, job), (job, build))

    def test_pet_builds_keep_the_slots_the_picker_cannot_name(self):
        slots = capes.decode(capes.encode("pet_tp", "BST"))
        material = capes.MATERIAL_BY_KEY["dust"]
        self.assertIsNone(capes.selection_for_slot(material, slots[1]))
        # A partial edit preserves that word rather than zeroing it.
        merged = capes.merge_choices(
            {"thread": {"option": "hp", "stage": 20}},
            [(slot["id"], slot["value"]) for slot in slots])
        self.assertEqual(merged[1], (slots[1]["id"], slots[1]["value"]))
        self.assertEqual(merged[0], (0x002, 27))

    def test_null_choice_clears_only_that_material(self):
        block = capes.encode("tp", "WAR")
        slots = [(slot["id"], slot["value"]) for slot in capes.decode(block)]
        merged = capes.merge_choices({"sap": None}, slots)
        self.assertEqual(merged[3], (0, 0))
        self.assertEqual(merged[0], (0x201, 19))

    def test_bad_choices_are_rejected(self):
        with self.assertRaises(ValueError):
            capes.encode_choices({})
        with self.assertRaises(ValueError):
            capes.encode_choices({"thread": {"option": "nope", "stage": 1}})
        with self.assertRaises(ValueError):
            capes.encode_choices({"thread": {"option": "dex", "stage": 21}})
        with self.assertRaises(ValueError):
            capes.encode_choices({"nope": {"option": "dex", "stage": 1}})


class CapeServiceTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        sys.path.insert(0, str(ROOT / "server" / "tests"))
        from support import make_service

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]

    def _cape_copy(self, job):
        data = self.service.character_data(self.character_id)
        cape = next(entry for entry in data["capes"]["capes"]
                    if entry["job"] == job)
        return cape

    def test_add_catalog_and_apply(self):
        self.assertEqual(self._cape_copy("WAR")["owned"], 0)
        capes.add(self.service, self.character_id, 26246)
        cape = self._cape_copy("WAR")
        self.assertEqual(cape["owned"], 1)
        copy = cape["copies"][0]
        capes.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {
                        "thread": {"option": "hp", "stage": 20},
                        "dust": {"option": "acc_attack", "stage": 20},
                        "dye": {"option": "accuracy", "stage": 10},
                        "sap": {"option": "store_tp", "stage": 10},
                        "resin": {"option": "pdt", "stage": 5},
                    })
        copy = self._cape_copy("WAR")["copies"][0]
        self.assertEqual(copy["current"]["text"],
                         "HP+60, Accuracy+20 Attack+20, Accuracy+10, "
                         '"Store TP"+10, Phys. dmg. taken-10%')
        self.assertEqual(copy["selection"]["thread"],
                         {"option": "hp", "stage": 20})
        self.assertEqual(copy["selection"]["resin"],
                         {"option": "pdt", "stage": 5})
        self.assertEqual(len(copy["current"]["slots"]), 5)

        capes.clear(self.service, self.character_id, copy["container"], copy["slot"])
        copy = self._cape_copy("WAR")["copies"][0]
        self.assertEqual(copy["current"]["text"], "not augmented")
        self.assertEqual(copy["current"]["slots"][0]["text"], "")

    def test_apply_preserves_a_pet_builds_unmatched_slots(self):
        capes.add(self.service, self.character_id, 26254)  # Artio's Mantle
        copy = self._cape_copy("BST")["copies"][0]
        block = capes.encode("pet_tp", "BST")
        self.service.set_item_extra(self.character_id, copy["container"],
                                    copy["slot"], block)
        before = capes.decode(block)
        capes.apply(self.service, self.character_id, copy["container"],
                    copy["slot"], {"thread": {"option": "hp", "stage": 20}})
        after = self._cape_copy("BST")["copies"][0]
        self.assertEqual(after["current"]["slots"][0]["id"], 0x002)
        for index in range(1, 5):
            self.assertEqual(after["current"]["slots"][index]["id"], before[index]["id"])
            self.assertEqual(after["current"]["slots"][index]["value"],
                             before[index]["value"])

    def test_apply_rejects_another_item_and_a_bad_slot(self):
        capes.add(self.service, self.character_id, 26246)
        copy = self._cape_copy("WAR")["copies"][0]
        with self.assertRaises(ValueError):
            capes.apply(self.service, self.character_id, copy["container"],
                        copy["slot"], {"thread": {"option": "dex", "stage": 99}})
        with self.assertRaises(LookupError):
            capes.apply(self.service, self.character_id, 99, 99, {})
        other = self.service.add_item(self.character_id, 11931)
        self.assertEqual(other["item_id"], 11931)
        with self.assertRaises(ValueError):
            capes.add(self.service, self.character_id, 11931)
