"""The item menu's Drop (C2S 0x028), which is how the client throws a stack away.

0x028 is also the battle-action packet the server sends, but the client sends it too --
with ``ItemNum``, ``Category`` and ``ItemIndex`` -- when the player picks Drop in the
item menu.  The server had no client-to-server case for it, so the first attempt was
logged once as an unknown packet and every later drop was ignored; the item stayed in
the bag.  These tests drive the handler and read the 0x020/0x01D the client needs to
redraw the emptied (or shortened) slot.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession, sub


def drop_packet(container: int, slot: int, quantity: int = 1) -> bytes:
    """A C2S 0x028 ITEM_DUMP: ItemNum(4), Category(1), ItemIndex(1), padding(2)."""
    return bytes(sub(0x028, struct.pack("<IBB2x", int(quantity),
                                        int(container) & 0xFF, int(slot) & 0xFF)))


def messages_of(session, ptype: int) -> list[bytes]:
    return [message for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == ptype]


def chats(session) -> list[str]:
    return [bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace")
            for message in messages_of(session, 0x017)]


class ItemDropTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()

    def slot_of(self, item_id: int, container: int = 0) -> tuple[int, int]:
        row = self.db.one(
            "SELECT container, slot FROM char_inventory "
            "WHERE character_id = ? AND container = ? AND item_id = ? "
            "ORDER BY slot LIMIT 1",
            (int(self.session.char["id"]), int(container), int(item_id)))
        self.assertIsNotNone(row, "item %d is not in container %d" % (item_id, container))
        return int(row["container"]), int(row["slot"])

    def quantity_at(self, container: int, slot: int) -> int | None:
        row = self.db.one(
            "SELECT quantity FROM char_inventory WHERE character_id = ? "
            "AND container = ? AND slot = ?",
            (int(self.session.char["id"]), int(container), int(slot)))
        return None if row is None else int(row["quantity"])

    def free_inventory_slot(self) -> int:
        taken = {int(row["slot"]) for row in self.db.all(
            "SELECT slot FROM char_inventory WHERE character_id = ? AND container = 0",
            (int(self.session.char["id"]),))}
        return next(slot for slot in range(81) if slot not in taken)

    def test_a_drop_removes_the_stack_and_repaints_the_slot(self):
        self.service.add_item(int(self.session.char["id"]), 4413, 2)  # Apple Pie x2
        container, slot = self.slot_of(4413)
        self.session.item_drop(drop_packet(container, slot, 2))
        self.assertIsNone(self.quantity_at(container, slot))
        updates = messages_of(self.session, 0x020)
        self.assertEqual(len(updates), 1)
        self.assertEqual(struct.unpack_from("<H", updates[0], 12)[0], 0)  # item id cleared
        self.assertEqual(updates[0][14], container)
        self.assertEqual(updates[0][15], slot)
        self.assertEqual(len(messages_of(self.session, 0x01D)), 1)
        self.assertIn("You throw away Apple Pie.", chats(self.session))

    def test_a_partial_drop_keeps_the_rest_of_the_stack(self):
        self.service.add_item(int(self.session.char["id"]), 4413, 5)
        container, slot = self.slot_of(4413)
        self.session.item_drop(drop_packet(container, slot, 2))
        self.assertEqual(self.quantity_at(container, slot), 3)
        update = messages_of(self.session, 0x020)[0]
        self.assertEqual(struct.unpack_from("<H", update, 12)[0], 4413)
        self.assertEqual(struct.unpack_from("<I", update, 4)[0], 3)
        self.assertIn("You throw away 2 Apple Pie.", chats(self.session))

    def test_dropping_more_than_the_stack_drops_the_stack(self):
        self.service.add_item(int(self.session.char["id"]), 4413, 3)
        container, slot = self.slot_of(4413)
        self.session.item_drop(drop_packet(container, slot, 99))
        self.assertIsNone(self.quantity_at(container, slot))

    def test_gil_is_never_dropped(self):
        self.session.item_drop(drop_packet(0, 0, 1))
        self.assertEqual(self.quantity_at(0, 0), 1000)
        self.assertIn("You cannot throw away gil.", chats(self.session))
        self.assertEqual(messages_of(self.session, 0x020), [])

    def test_a_worn_copy_has_to_come_off_first(self):
        self.service.add_item(int(self.session.char["id"]), 16534, 1)  # Onion Sword
        container, slot = self.slot_of(16534)
        self.session.equipped[0] = (container, slot, 16534)
        self.session.item_drop(drop_packet(container, slot, 1))
        self.assertEqual(self.quantity_at(container, slot), 1)
        self.assertIn("You cannot throw away something you are wearing.", chats(self.session))
        self.assertEqual(messages_of(self.session, 0x020), [])

    def test_a_drop_works_from_a_wardrobe(self):
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 8, 1, 4112, 4)",
            (int(self.session.char["id"]),))
        self.session.item_drop(drop_packet(8, 1, 4))
        self.assertIsNone(self.quantity_at(8, 1))
        update = messages_of(self.session, 0x020)[0]
        self.assertEqual(update[14], 8)
        self.assertEqual(update[15], 1)

    def test_dropping_an_empty_slot_says_so(self):
        slot = self.free_inventory_slot()
        self.session.item_drop(drop_packet(0, slot, 1))
        self.assertIn("You do not have that item.", chats(self.session))

    def test_a_drop_arriving_without_sync_is_dispatched(self):
        """The menu can send the request with sync 0; it must not be gated on the sync."""
        self.service.add_item(int(self.session.char["id"]), 4413, 1)
        container, slot = self.slot_of(4413)
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x028)
        self.session.client_id = 0
        self.session.parse(header, drop_packet(container, slot, 1))
        self.assertIsNone(self.quantity_at(container, slot))


if __name__ == "__main__":
    unittest.main()
