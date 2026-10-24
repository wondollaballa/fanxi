"""Retail Rare/Ex flags, and the one-copy rule for Rare gear."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from support import ROOT, make_service

from fanxi_server.db import Database
from fanxi_server.game.zone import ZoneSession
from fanxi_server.service import ApiError


class RareItemTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123", ip="127.0.0.1").account
        self.character = self.service.create_character(
            account["id"], {"name": "Onedough", "race": 1})
        self.character_id = int(self.character["id"])

    def add(self, item_id: int, quantity: int = 1) -> dict:
        return self.service.add_item(self.character_id, item_id, quantity)

    def rows(self, item_id: int) -> list[dict]:
        return [dict(row) for row in self.db.all(
            "SELECT container, slot, quantity FROM char_inventory "
            "WHERE character_id = ? AND item_id = ? ORDER BY container, slot",
            (self.character_id, int(item_id)))]

    def test_retail_flags_reach_the_catalogue(self):
        helm = self.service.item(23761)   # Nyame Helm: Rare + Ex
        cape = self.service.item(26258)   # Andartia's Mantle: Ex, not Rare
        potion = self.service.item(4112)  # Potion: neither
        self.assertEqual((int(helm["rare"]), int(helm["ex"])), (1, 1))
        self.assertEqual((int(cape["rare"]), int(cape["ex"])), (0, 1))
        self.assertEqual((int(potion["rare"]), int(potion["ex"])), (0, 0))

    def test_a_rare_item_can_be_added_once(self):
        self.add(10769)  # Gelatinous Ring +1
        with self.assertRaises(ApiError) as caught:
            self.add(10769)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.code, "already_owned")
        self.assertEqual(len(self.rows(10769)), 1)

    def test_a_rare_item_cannot_be_added_in_a_batch(self):
        with self.assertRaises(ApiError) as caught:
            self.add(10769, 2)
        self.assertEqual(caught.exception.status, 422)
        self.assertEqual(caught.exception.code, "rare_item")
        self.assertEqual(self.rows(10769), [])

    def test_storage_still_counts_as_holding_the_item(self):
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 10769, 1, 8)", (self.character_id,))
        with self.assertRaises(ApiError) as caught:
            self.add(10769)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.rows(10769), [])

    def test_a_non_rare_item_can_still_be_duplicated(self):
        self.add(10795)  # Blenmot's Ring +1 is not Rare in retail.
        self.add(10795)
        self.assertEqual(len(self.rows(10795)), 2)

    def test_the_shop_refuses_a_second_rare_copy_before_charging(self):
        self.add(10769)
        session = object.__new__(ZoneSession)
        session.shop_items = [{"item_id": 10769, "price": 100}]
        session.char = {"id": self.character_id, "gil": 1000}
        session.world = SimpleNamespace(service=self.service)
        session.queue = []
        session.refresh_inventory = lambda: None
        messages = []
        session.say = messages.append
        packet = bytearray(16)
        struct.pack_into("<IHHB", packet, 4, 1, 0, 0, 0)
        session.buy(bytes(packet))
        self.assertEqual(self.service.character(self.character_id)["gil"], 1000)
        self.assertEqual(len(self.rows(10769)), 1)
        self.assertEqual(messages, ["You cannot possess another Gelatinous Ring +1."])

    def test_a_failed_purchase_is_refunded(self):
        session = object.__new__(ZoneSession)
        session.shop_items = [{"item_id": 4112, "price": 100}]
        session.char = {"id": self.character_id, "gil": 1000}
        session.world = SimpleNamespace(service=self.service)
        session.queue = []
        session.refresh_inventory = lambda: None
        messages = []
        session.say = messages.append
        packet = bytearray(16)
        struct.pack_into("<IHHB", packet, 4, 1, 0, 0, 0)
        with mock.patch.object(self.service, "add_item", side_effect=RuntimeError("bag full")):
            session.buy(bytes(packet))
        self.assertEqual(self.service.character(self.character_id)["gil"], 1000)
        self.assertEqual(len(messages), 1)
        self.assertIn("could not be completed", messages[0])

    def test_cleanup_keeps_the_equipped_copy_and_one_of_each_item(self):
        # Two bag rows of one Rare item; the second one is the equipped copy.
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 0, 60, 23490, 1), (?, 0, 61, 23490, 1), "
            "(?, 0, 62, 23898, 1), (?, 0, 63, 23898, 1)",
            (self.character_id, self.character_id, self.character_id, self.character_id))
        self.db.execute(
            "INSERT INTO char_equip (character_id, kind, container, slot, item_id) "
            "VALUES (?, 5, 0, 61, 23490)", (self.character_id,))
        # A stored suit with quantity two, and a locker copy that yields to the bag.
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 24044, 2, 0)", (self.character_id,))
        self.db.execute(
            "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 8, 10, 24044, 1)", (self.character_id,))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 24044, 3)",
            (self.character_id,))

        with self.db.connection() as conn:
            Database._apply_script(conn, ROOT / "database/migrations/0103_rare_ex_dedupe.sql")

        self.assertEqual(self.rows(23490), [{"container": 0, "slot": 61, "quantity": 1}])
        equipped = self.db.one(
            "SELECT container, slot FROM char_equip "
            "WHERE character_id = ? AND kind = 5", (self.character_id,))
        self.assertEqual((int(equipped["container"]), int(equipped["slot"])), (0, 61))
        self.assertEqual(self.rows(23898), [{"container": 0, "slot": 62, "quantity": 1}])
        self.assertEqual(self.rows(24044), [{"container": 8, "slot": 10, "quantity": 1}])
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_storage WHERE character_id = ? AND item_id = 24044",
            (self.character_id,)))
        self.assertIsNone(self.db.one(
            "SELECT 1 FROM char_locker WHERE character_id = ? AND item_id = 24044",
            (self.character_id,)))


if __name__ == "__main__":
    unittest.main()
