"""Grap models for visible gear: migration 95, its triggers and the clone repair."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tools"))

from support import make_service  # noqa: E402

import item_models  # noqa: E402

ARMOR = ("head", "body", "hands", "legs", "feet")

# Prime weapon families: (stages 2-4 item ids, Non AG model), (iLvl 119 III id, Stage 5
# model).  The Stage 5 DAT is the Non AG weapon plus the client's afterglow `aura` block;
# it is the same "AG" look the Relic/Mythic/Empyrean iLvl 119 forms already use.
PRIME_FAMILIES = {
    "Varga Purnikawa": ((21532, 21533, 21534), 475, 21535, 474),
    "Mpu Gandring": ((21587, 21588, 21589), 907, 21590, 918),
    "Caliburnus": ((21643, 21644, 21645), 908, 21646, 919),
    "Helheim": ((21649, 21651, 21652), 909, 21653, 920),
    "Spalirisos": ((21727, 21728, 21729), 910, 21730, 921),
    "Laphria": ((21782, 21783, 21784), 911, 21785, 922),
    "Foenaria": ((21834, 21835, 21836), 913, 21837, 924),
    "Gae Buide": ((21888, 21889, 21890), 912, 21891, 923),
    "Dokoku": ((21929, 21930, 21931), 914, 21932, 925),
    "Kusanagi": ((21983, 21984, 21985), 915, 21986, 926),
    "Lorg Mor": ((21998, 22000, 22001), 916, 22002, 927),
    "Opashoro": ((22103, 22104, 22105), 917, 22106, 928),
    "Pinaka": ((22156, 22157, 22158), 148, 22163, 151),
    "Earp": ((22160, 22161, 22162), 149, 22164, 152),
    "Loughnashade": ((22304, 22305, 22306), 150, 22307, 153),
    "Duban": ((26492, 26493, 26494), 675, 26495, 676),
}


class ItemModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        _config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.character_id = int(self.character["id"])

    def test_known_sets_carry_their_grap_models(self):
        expected = {
            23899: 4168,   # Atrophy Chapeau +4  (Warlock's look)
            23922: 4169,   # Vitiation Chapeau +4 (Duelist's look)
            23424: 4382,   # Lethargy Chappel +3 (Estoqueur's look)
            23907: 4184,   # Hachiya Hatsuburi +4 (Ninja look)
            23761: 4566,   # Nyame Helm
            27410: 20499,  # Hippomenes Socks +1
            24152: 4611,   # Indom. Petasos       (MId 515)
            24155: 8707,   # Indomitable Coat     (MId 515)
            24158: 12803,  # Indom. Gloves        (MId 515)
            24161: 16899,  # Indom. Tonban        (MId 515)
            24164: 20995,  # Indom. Sabots        (MId 515)
        }
        for item_id, model in expected.items():
            row = self.db.one("SELECT model FROM items WHERE item_id = ?", (item_id,))
            self.assertIsNotNone(row, item_id)
            self.assertEqual(int(row["model"]), model, item_id)

    def test_null_masque_uses_the_masque_not_the_rogue_bonnet(self):
        """Migration 184: 4170 is Rogue's Bonnet (head 74); the masque is head 522."""
        row = self.db.one("SELECT model FROM items WHERE item_id = 24270")
        self.assertIsNotNone(row)
        self.assertEqual(int(row["model"]), 4618)
        lookup = self.db.one("SELECT model FROM item_models WHERE item_id = 24270")
        self.assertIsNotNone(lookup)
        self.assertEqual(int(lookup["model"]), 4618)
        self.assertEqual(item_models.catalog()[24270], 4618)

    def test_gleti_knife_uses_its_own_dagger_model(self):
        """Migration 121: 513 is Kannagi's katana; the client's knife is 877."""
        row = self.db.one("SELECT model FROM items WHERE item_id = 21567")
        self.assertEqual(int(row["model"]), 877)
        lookup = self.db.one("SELECT model FROM item_models WHERE item_id = 21567")
        self.assertEqual(int(lookup["model"]), 877)
        self.assertEqual(item_models.catalog()[21567], 877)

    def test_prime_weapons_use_their_stage_five_afterglow_model(self):
        """Migration 125: the 119 III forms carry the model with the afterglow aura.

        Retail keeps two looks per Prime weapon.  The Non AG model (907-917, 475, 148-150,
        675) is the black relic-style weapon; the Stage 5 model is that weapon plus the
        client's `aura` particle block, the purple glow every other ultimate weapon's
        "119 AG" model has.  The server sends whichever model `items.model` holds, so the
        item and the lookup must agree on the Stage 5 id for iLvl 119 III.
        """
        for name, (earlier, non_ag, final, afterglow) in PRIME_FAMILIES.items():
            for item_id in earlier:
                item = self.db.one("SELECT model FROM items WHERE item_id = ?", (item_id,))
                self.assertIsNotNone(item, (name, item_id))
                self.assertEqual(int(item["model"]), non_ag, (name, item_id))
                self.assertEqual(item_models.catalog()[item_id], non_ag, (name, item_id))
            item = self.db.one("SELECT model FROM items WHERE item_id = ?", (final,))
            self.assertIsNotNone(item, (name, final))
            self.assertEqual(int(item["model"]), afterglow, (name, final))
            lookup = self.db.one("SELECT model FROM item_models WHERE item_id = ?", (final,))
            self.assertIsNotNone(lookup, (name, final))
            self.assertEqual(int(lookup["model"]), afterglow, (name, final))
            self.assertEqual(item_models.catalog()[final], afterglow, (name, final))

    def test_every_armour_slot_has_a_model(self):
        """Every armour item has a Grap model, the Limbus Rank 30 pieces included.

        Migration 107 gives the 25 Limbus pieces their client models (MIds 513-517); any
        armour item with no Grap model is a hole in migration 95's lookup or a new import.
        """
        rows = self.db.all(
            "SELECT item_id FROM items WHERE equip_slot IN (%s) AND model = 0 ORDER BY item_id"
            % ",".join("?" for _ in ARMOR), ARMOR)
        missing = [int(row["item_id"]) for row in rows]
        self.assertEqual(missing, [])

    def test_a_new_item_is_stamped_from_the_lookup(self):
        self.db.execute("INSERT OR REPLACE INTO item_models (item_id, model) VALUES (99999, 4321)")
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99999, 'Test Helm', 1, 0, 'head', 1, '', 0, 16, 1, 0)")
        row = self.db.one("SELECT model FROM items WHERE item_id = 99999")
        self.assertEqual(int(row["model"]), 4321)

    def test_adding_gear_to_a_bag_or_slot_stamps_its_model(self):
        self.db.execute("INSERT OR REPLACE INTO item_models (item_id, model) VALUES (99998, 4322)")
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99998, 'Test Mail', 1, 0, 'body', 1, '', 0, 32, 1, 0)")
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 99998")
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 0, 79, 99998, 1)", (self.character_id,))
        row = self.db.one("SELECT model FROM items WHERE item_id = 99998")
        self.assertEqual(int(row["model"]), 4322)
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 99998")
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 5, 0, 79, 99998)", (self.character_id,))
        row = self.db.one("SELECT model FROM items WHERE item_id = 99998")
        self.assertEqual(int(row["model"]), 4322)

    def test_repair_fixes_a_broken_row(self):
        self.db.execute("UPDATE items SET model = 0 WHERE item_id = 23761")
        with self.db.connection() as conn:
            repaired = item_models.repair(conn)
            conn.commit()
        self.assertEqual(repaired, 1)
        row = self.db.one("SELECT model FROM items WHERE item_id = 23761")
        self.assertEqual(int(row["model"]), 4566)

    def test_missing_reports_worn_gear_without_a_model(self):
        self.db.execute(
            "INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description, "
            "model, slot_mask, jobs, skill) VALUES (99997, 'Mystery Hat', 1, 0, 'head', 1, '', 0, 16, 1, 0)")
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 4, 0, 78, 99997)", (self.character_id,))
        with self.db.connection() as conn:
            missing = item_models.missing(conn, self.character_id, equipped=True)
        self.assertEqual([item["name"] for item in missing], ["Mystery Hat"])


if __name__ == "__main__":
    unittest.main()
