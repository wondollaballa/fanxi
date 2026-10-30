"""Divainy-Gamainy's Skirmish augments (the standard five-slot block)."""

import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server" / "tests"))

from support import make_service  # noqa: E402

from fanxi_server.game import augment_stats, capes, modifiers as mod, skirmish  # noqa: E402


def item_named(name: str) -> dict:
    return next(entry for entry in skirmish.entries() if entry["name"] == name)


def slots_of(name: str, *, ranged: bool | None = None) -> list[dict]:
    entry = item_named(name)
    if ranged is not None:
        entry = {**entry, "ranged": ranged}
    return skirmish.resolved_slots(entry)


def option(slot: dict, key: str) -> dict:
    return next(candidate for candidate in slot["options"] if candidate["key"] == key)


class SkirmishCatalogTest(unittest.TestCase):
    def test_every_family_is_there(self):
        entries = skirmish.entries()
        self.assertEqual(len(entries), 138)
        families = {}
        for entry in entries:
            families[entry["family"]] = families.get(entry["family"], 0) + 1
        self.assertEqual(families, {"alluvion": 41, "skirmish": 97})
        weapons = [entry for entry in entries if entry["kind"] == "weapon"]
        armor = [entry for entry in entries if entry["kind"] == "armor"]
        self.assertEqual((len(weapons), len(armor)), (61, 77))
        names = {entry["name"] for entry in entries}
        for name in ("Ohrmazd", "Svalinn", "Linos", "Yorium Barbuta", "Helios Band",
                     "Ninzas +2", "Hgafircian", "Cizin Helm", "Beatific Shield +1"):
            self.assertIn(name, names)

    def test_every_item_points_at_a_table(self):
        tables = skirmish.tables()
        self.assertEqual(len(tables), 36)
        for entry in skirmish.entries():
            self.assertIn(entry["table"], tables, entry["name"])
            slots = skirmish.resolved_slots(entry)
            self.assertTrue(slots, entry["name"])
            for slot in slots:
                self.assertTrue(slot["options"], (entry["name"], slot["label"]))
                for candidate in slot["options"]:
                    self.assertIn(candidate["key"], skirmish.STATS, entry["name"])
                    self.assertLessEqual(candidate["minimum"], candidate["maximum"])

    def test_the_alluvion_tables_offer_three_stones(self):
        entry = item_named("Yorium Barbuta")
        slots = skirmish.resolved_slots(entry)
        self.assertEqual([slot["key"] for slot in slots], ["snow", "leaf", "dusk"])
        self.assertFalse(any(slot["required"] for slot in slots))
        self.assertTrue(all(slot["default_on"] for slot in slots))
        snow = option(slots[0], "acc")
        self.assertEqual((snow["minimum"], snow["maximum"]), (1, 25))
        leaf = option(slots[1], "enmity")
        self.assertEqual((leaf["minimum"], leaf["maximum"]), (-5, 10))
        dusk = option(slots[2], "str")
        self.assertEqual((dusk["minimum"], dusk["maximum"]), (1, 10))

    def test_the_wiki_maxima_are_kept(self):
        one_hand = slots_of("Ohrmazd")
        self.assertEqual(option(one_hand[0], "acc")["maximum"], 20)
        self.assertEqual(option(one_hand[1], "stp")["maximum"], 6)
        self.assertEqual(option(one_hand[2], "save_tp")["maximum"], 100)
        self.assertEqual(option(one_hand[2], "pet_tp_bonus")["maximum"], 200)
        two_hand = slots_of("Inanna")
        self.assertEqual(option(two_hand[2], "save_tp")["maximum"], 150)
        self.assertEqual(option(two_hand[1], "elemental_siphon")["maximum"], 25)

    def test_the_dmg_cap_comes_from_the_weapon(self):
        for name, cap in (("Ohrmazd", 29), ("Inanna", 39), ("Phaosphaelia", 32)):
            entry = item_named(name)
            dusk = skirmish.resolved_slots(entry)[2]
            self.assertEqual(option(dusk, "dmg")["maximum"], cap, name)
            self.assertEqual(entry["dmg_max"], cap, name)
        old = item_named("Bocluamni")
        self.assertEqual(option(skirmish.resolved_slots(old)[0], "dmg")["maximum"], 11)

    def test_ranged_weapons_swap_delay_for_snapshot(self):
        melee = slots_of("Macbain")
        ranged = slots_of("Phaosphaelia")
        self.assertIn("delay", [candidate["key"] for candidate in melee[2]["options"]])
        self.assertNotIn("delay", [candidate["key"] for candidate in ranged[2]["options"]])
        self.assertIn("snapshot", [candidate["key"] for candidate in ranged[2]["options"]])

    def test_old_skirmish_weapons_have_dmg_and_two_pools(self):
        entry = item_named("Ninzas +2")
        slots = skirmish.resolved_slots(entry)
        self.assertEqual([slot["key"] for slot in slots], ["dmg", "pool0", "pool1"])
        self.assertTrue(slots[0]["required"])
        self.assertFalse(slots[1]["required"])
        self.assertEqual(option(slots[0], "dmg")["maximum"], 10)
        self.assertEqual({candidate["key"] for candidate in slots[1]["options"]},
                         {"str", "dex", "vit", "agi"})
        self.assertEqual({candidate["key"] for candidate in slots[2]["options"]},
                         {"acc", "attack", "da", "crit_rate", "mdef"})

    def test_trailing_hyphen_rows_keep_their_direction(self):
        gende = slots_of("Gendewitha Caubeen")
        self.assertIn("cure_cast_time",
                      {candidate["key"] for candidate in gende[1]["options"]})
        cure = option(gende[1], "cure_cast_time")
        self.assertEqual((cure["minimum"], cure["maximum"]), (-5, -1))
        hagondes = slots_of("Hagondes Hat")
        enmity = option(hagondes[1], "enmity")
        self.assertEqual((enmity["minimum"], enmity["maximum"]), (-6, -1))

    def test_old_skirmish_armor_keeps_pdt_and_bonus_rows(self):
        nq = skirmish.resolved_slots(item_named("Cizin Helm"))
        hq = skirmish.resolved_slots(item_named("Cizin Helm +1"))
        self.assertEqual(len(nq), 2)   # PDT + one bonus
        self.assertEqual(len(hq), 3)   # PDT + two bonuses
        self.assertEqual(option(nq[0], "pdt")["default"], -4)
        self.assertEqual(option(nq[0], "pdt")["minimum"], -4)
        self.assertIn("mdt", [candidate["key"] for candidate in hq[1]["options"]])
        self.assertNotIn("mdt", [candidate["key"] for candidate in nq[1]["options"]])


class SkirmishEncodingTest(unittest.TestCase):
    def test_the_standard_three_slot_block(self):
        block = skirmish.encode([
            {"key": "acc", "value": 20},
            {"key": "stp", "value": 6},
            {"key": "hp", "value": 40},
        ])
        self.assertEqual(len(block), 24)
        self.assertEqual(block[0], capes.AUGMENT_KIND)
        self.assertEqual(block[1], capes.AUGMENT_SUBKIND)
        self.assertEqual(capes.decode(block)[:3], [
            {"id": 0x017, "value": 19},   # Accuracy 1 + 19
            {"id": 0x08E, "value": 5},    # Store TP 1 + 5
            {"id": 0x002, "value": 7},    # HP 33 + 7
        ])

    def test_combined_rows_use_the_combined_ids(self):
        block = skirmish.encode([
            {"key": "macc_mab", "value": 10},
            {"key": "str_vit", "value": 15},
            {"key": "hp_mp", "value": 60},
        ])
        self.assertEqual(capes.decode(block)[:3], [
            {"id": 0x083, "value": 9},
            {"id": 0x227, "value": 14},
            {"id": 0x012, "value": 27},
        ])
        self.assertEqual(skirmish.describe(block),
                         "Mag. Acc.+10 Mag.Atk.Bns.+10 | STR+15 VIT+15 | HP+60 MP+60")

    def test_the_dmg_row_is_augmented_on_the_weapon(self):
        block = skirmish.encode([{"key": "dmg", "value": 39}])
        self.assertEqual(capes.decode(block)[0], {"id": 0x04C, "value": 6})
        ranged = skirmish.encode([{"key": "dmg", "value": 13}], ranged=True)
        self.assertEqual(capes.decode(ranged)[0], {"id": 0x2EA, "value": 12})

    def test_save_tp_and_pet_tp_bonus_scale(self):
        block = skirmish.encode([
            {"key": "save_tp", "value": 150},
            {"key": "pet_tp_bonus", "value": 200},
            {"key": "elemental_siphon", "value": 25},
        ])
        self.assertEqual(capes.decode(block)[:3], [
            {"id": 0x168, "value": 14},   # (14 + 1) * 10
            {"id": 0x07A, "value": 9},    # (9 + 1) * 20
            {"id": 0x153, "value": 4},    # (4 + 1) * 5
        ])
        self.assertIn("Save TP+150", skirmish.describe(block))
        self.assertIn("Pet: TP Bonus+200", skirmish.describe(block))
        self.assertIn('"Elemental Siphon"+25', skirmish.describe(block))

    def test_old_skirmish_block_has_three_rows(self):
        block = skirmish.encode([
            {"key": "dmg", "value": 10},
            {"key": "str", "value": 7},
            {"key": "acc", "value": 9},
        ])
        self.assertEqual(capes.decode(block)[:3], [
            {"id": 0x02D, "value": 9},
            {"id": 0x200, "value": 6},
            {"id": 0x017, "value": 8},
        ])

    def test_reductions_are_written_negative(self):
        block = skirmish.encode([
            {"key": "pdt", "value": -4},
            {"key": "mdt", "value": -3},
            {"key": "enmity", "value": -5},
        ])
        self.assertEqual(capes.decode(block)[:3], [
            {"id": 0x036, "value": 3},
            {"id": 0x037, "value": 2},
            {"id": 0x028, "value": 4},
        ])
        self.assertEqual(skirmish.describe(block),
                         "Phys. dmg. taken-4% | Magic dmg. taken-3% | Enmity-5")

    def test_empty_rows_are_zero(self):
        block = skirmish.encode([{"key": "da", "value": 2}])
        self.assertEqual(capes.decode(block),
                         [{"id": 0x08F, "value": 1}, {"id": 0, "value": 0},
                          {"id": 0, "value": 0}, {"id": 0, "value": 0},
                          {"id": 0, "value": 0}])

    def test_round_trip_of_every_item(self):
        for entry in skirmish.entries():
            slots = skirmish.resolved_slots(entry)
            picks = []
            for slot in slots:
                if not slot["options"]:
                    continue
                first = slot["options"][0]
                picks.append({"key": first["key"], "value": first["default"]})
            block = skirmish.encode(picks, bool(entry.get("ranged")))
            decoded = [pick for pick in skirmish.decode_picks(block) if pick]
            self.assertEqual([(pick["key"], pick["value"]) for pick in picks],
                             [(pick["key"], pick["value"]) for pick in decoded],
                             entry["name"])

    def test_stat_sheet_reads_the_block(self):
        block = skirmish.encode([
            {"key": "acc", "value": 20},
            {"key": "attack", "value": 20},
            {"key": "da", "value": 3},
            {"key": "pdt", "value": -4},
            {"key": "hp", "value": 40},
        ])
        mods = augment_stats.item_mods(20530, block)
        self.assertEqual(mods[mod.ACC], 20)
        self.assertEqual(mods[mod.ATT], 20)
        self.assertEqual(mods[mod.DOUBLE_ATTACK], 3)
        self.assertEqual(mods[mod.DMGPHYS], -400)
        self.assertEqual(mods[mod.HP], 40)

    def test_bad_picks_are_rejected(self):
        with self.assertRaises(ValueError):
            skirmish.slot_word("acc", 0)
        with self.assertRaises(ValueError):
            skirmish.slot_word("save_tp", 25)
        with self.assertRaises(ValueError):
            skirmish.slot_word("nope", 1)


class SkirmishServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character_id = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})["id"]
        self.service.top_off_gil(self.character_id)

    def add(self, item_id: int) -> dict:
        self.service.armory_add(self.character_id, item_id)
        return next(row for row in self.service.inventory(self.character_id)
                    if int(row["item_id"]) == int(item_id))

    def test_catalog_lists_owned_copies(self):
        row = self.add(26733)  # Yorium Barbuta
        catalog = skirmish.catalog(self.service, self.character_id)
        self.assertEqual(len(catalog["items"]), 138)
        self.assertGreaterEqual(len(catalog["slot_sets"]), 36)
        entry = next(item for item in catalog["items"] if item["item_id"] == 26733)
        self.assertTrue(entry["owned"])
        self.assertEqual(entry["copies"][0]["container"], row["container"])
        self.assertEqual(entry["copies"][0]["current"], "not augmented")
        self.assertEqual(len(catalog["slot_sets"][entry["slot_set"]]), 3)

    def test_apply_and_clear(self):
        row = self.add(26733)
        applied = skirmish.apply(self.service, self.character_id, row["container"],
                                 row["slot"], [
                                     {"key": "acc", "value": 25},
                                     {"key": "stp", "value": 6},
                                     {"key": "str", "value": 10},
                                 ])
        self.assertEqual(applied["augments"], ["Accuracy+25", "Store TP+6", "STR+10"])
        current = self.db.one(
            "SELECT extra FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
            (self.character_id, int(row["container"]), int(row["slot"])))["extra"]
        self.assertEqual(skirmish.describe(current), "Accuracy+25 | Store TP+6 | STR+10")
        catalog = skirmish.catalog(self.service, self.character_id)
        entry = next(item for item in catalog["items"] if item["item_id"] == 26733)
        self.assertEqual(entry["copies"][0]["selection"][0], {"key": "acc", "value": 25})

        skirmish.clear(self.service, self.character_id, row["container"], row["slot"])
        current = self.db.one(
            "SELECT extra FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
            (self.character_id, int(row["container"]), int(row["slot"])))["extra"]
        self.assertEqual(skirmish.describe(current), "not augmented")

    def test_apply_validates_the_picks(self):
        row = self.add(26733)
        with self.assertRaises(ValueError):
            skirmish.apply(self.service, self.character_id, row["container"], row["slot"],
                           [{"key": "acc", "value": 40}])
        with self.assertRaises(ValueError):
            skirmish.apply(self.service, self.character_id, row["container"], row["slot"],
                           [{"key": "nope", "value": 1}])
        with self.assertRaises(ValueError):
            skirmish.apply(self.service, self.character_id, row["container"], row["slot"],
                           [None, {"key": "stp", "value": 6},
                            {"key": "hp", "value": 40}])
        with self.assertRaises(ValueError):
            skirmish.apply(self.service, self.character_id, row["container"], row["slot"],
                           [None, None, None])
        with self.assertRaises(LookupError):
            skirmish.apply(self.service, self.character_id, 99, 99,
                           [{"key": "acc", "value": 1}])

    def test_a_non_skirmish_item_is_rejected(self):
        row = self.add(28636)  # an Ambuscade cape
        with self.assertRaises(ValueError):
            skirmish.apply(self.service, self.character_id, row["container"], row["slot"],
                           [{"key": "acc", "value": 1}])

    def test_ranged_weapon_apply_uses_its_dmg_row(self):
        row = self.add(21279)  # Hgafircian +2
        applied = skirmish.apply(self.service, self.character_id, row["container"],
                                 row["slot"], [
                                     {"key": "dmg", "value": 13},
                                     {"key": "str", "value": 4},
                                     {"key": "racc", "value": 9},
                                 ])
        self.assertEqual(applied["augments"], ["DMG:+13", "STR+4", "Rng.Acc.+9"])
        current = self.db.one(
            "SELECT extra FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
            (self.character_id, int(row["container"]), int(row["slot"])))["extra"]
        self.assertEqual(capes.decode(current)[0], {"id": 0x2EA, "value": 12})
