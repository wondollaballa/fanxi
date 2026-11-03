"""The shared modern +1 armor set-bonus table and its live-stat integration."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.db import Database  # noqa: E402
from fanxi_server.game import modifiers as mod, set_bonuses  # noqa: E402
from support import make_service  # noqa: E402


KAYKAUS_PLUS = (25618, 25691, 27122, 27307, 27478)  # head, body, hands, legs, feet
KAYKAUS_NQ = (25617, 25690, 27121, 27306, 27477)


class SetBonusDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Database(Path(cls.tmp.name) / "fanxi.db", ROOT)
        cls.db.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_table_has_every_modern_plus_one_set(self):
        names = {armor_set.name for armor_set in set_bonuses.sets()}
        self.assertEqual(len(names), 11)
        for name in (
            "Adhemar Attire Set +1", "Amalric Attire Set +1", "Apogee Attire Set +1",
            "Argosy Armor Set +1", "Carmine Armor Set +1", "Emicho Armor Set +1",
            "Kaykaus Attire Set +1", "Lustratio Armor Set +1", "Rao Armor Set +1",
            "Ryuo Armor Set +1", "Souveran Armor Set +1",
        ):
            self.assertIn(name, names)
        for armor_set in set_bonuses.sets():
            self.assertEqual(len(armor_set.piece_ids), 5, armor_set.name)
            self.assertEqual([tier.pieces for tier in armor_set.tiers], [2, 3, 4, 5])
            for tier in armor_set.tiers:
                for key, _value in tier.mods:
                    self.assertIn(key, set_bonuses.MODIFIERS, (armor_set.name, key))

    def test_every_piece_has_a_client_name_for_the_launcher(self):
        document = json.loads(
            (ROOT / "data" / "armor_set_bonuses.json").read_text(encoding="utf-8"))
        for armor_set in document["sets"]:
            for piece in armor_set["pieces"]:
                self.assertTrue(piece.get("client_name"), (armor_set["name"], piece))

    def test_every_piece_id_names_the_expected_catalogue_row(self):
        for armor_set in set_bonuses.sets():
            for piece_id in armor_set.piece_ids:
                row = self.db.one(
                    "SELECT name FROM items WHERE item_id = ?", (piece_id,))
                self.assertIsNotNone(row, piece_id)
                self.assertTrue(str(row["name"]).endswith("+1"), (piece_id, row["name"]))

    def test_kaykaus_tiers(self):
        for count, amount in ((2, 4), (3, 6), (4, 8), (5, 10)):
            bonuses = set_bonuses.for_item_ids(KAYKAUS_PLUS[:count])
            self.assertEqual(len(bonuses), 1, count)
            self.assertEqual(bonuses[0].pieces, count)
            self.assertIn((mod.CURE_POTENCY_II, amount), bonuses[0].mods)
        self.assertEqual(set_bonuses.for_item_ids(KAYKAUS_PLUS[:1]), [])

    def test_nq_pieces_do_not_count(self):
        self.assertEqual(set_bonuses.for_item_ids(KAYKAUS_NQ), [])

    def test_units_and_other_sets(self):
        adhemar = set_bonuses.for_item_ids((25614, 25687, 27118, 27303, 27474))[0]
        self.assertIn((mod.CRIT_HIT_RATE, 1000), adhemar.mods)  # 10% in hundredths
        souveran = set_bonuses.for_item_ids((26671, 26847, 27023, 27199, 27375))[0]
        self.assertIn((mod.DMG, -1000), souveran.mods)  # -10% in hundredths
        amalric = set_bonuses.for_item_ids((25616, 25689))[0]
        self.assertIn((mod.MATT, 20), amalric.mods)


class SetBonusServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.character_id = int(self.character["id"])

    def equip(self, kind: int, item_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, 0, ?)",
            (self.character_id, int(kind), int(item_id)))

    def test_kaykaus_four_piece_bonus_reaches_equipped_mods(self):
        for kind, item_id in ((4, 25618), (6, 27122)):
            self.equip(kind, item_id)
        mods = self.service.equipped_mods(self.character_id)
        self.assertEqual(mods[mod.CURE_POTENCY_II], 4)

        self.equip(5, 25691)  # Bliaut +1 also carries its own Cure Potency II row
        self.equip(7, 27307)
        mods = self.service.equipped_mods(self.character_id)
        self.assertEqual(mods[mod.CURE_POTENCY_II], 4 + 8)  # item row + four-piece bonus

    def test_nq_set_adds_no_bonus(self):
        for kind, item_id in ((4, 25617), (5, 25690), (6, 27121), (7, 27306)):
            self.equip(kind, item_id)
        mods = self.service.equipped_mods(self.character_id)
        self.assertEqual(mods.get(mod.CURE_POTENCY_II, 0), 3)  # NQ Bliaut row only


if __name__ == "__main__":
    unittest.main()
