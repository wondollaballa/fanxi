"""Dispense pouches: charged equipment that hands out ammo on a reuse timer."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import item_usable
from fanxi_server.game.world import World
from fanxi_server.game.zone import VANA_EPOCH, ZoneSession

POUCH = 26348
LIVING_BULLET = 21326


def packet_kind(message: bytes) -> int:
    return struct.unpack_from("<H", message, 0)[0] & 0x1FF


def use_packet(container: int, slot: int) -> bytes:
    """The 20-byte C2S 0x037 the client sends for an inventory/wardrobe item."""
    body = bytearray(20)
    struct.pack_into("<HHH", body, 0, 0x037, 0x05, 0)
    body[0x0E] = slot
    struct.pack_into("<I", body, 0x10, container)
    return bytes(body)


class DispenseItemTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.queue.clear()
        self.service.add_item(int(self.character["id"]), POUCH, 1)
        self.pouch = next(
            row for row in self.service.inventory(int(self.character["id"]))
            if int(row["item_id"]) == POUCH)

    def bullets(self) -> int:
        return sum(int(row["quantity"]) for row in self.service.inventory(
            int(self.character["id"])) if int(row["item_id"]) == LIVING_BULLET)

    def item_packets(self, item_id: int) -> list[bytes]:
        out = []
        for message in self.session.queue:
            if packet_kind(message) != 0x020:
                continue
            body = message[4:]
            if struct.unpack_from("<H", body, 8)[0] == item_id:
                out.append(body)
        return out

    def test_catalogue_maps_the_pouches_to_their_ammo(self):
        mapping = {int(row["item_id"]): int(row["ammo_id"])
                   for row in self.service.dispense_items()}
        self.assertEqual(mapping[26347], 21327)   # Eradicating Bullet
        self.assertEqual(mapping[26348], 21326)   # Living Bullet
        self.assertEqual(mapping[26349], 21325)   # Devastating Bullet
        self.assertEqual(mapping[26350], 21296)   # Chrono Bullet
        self.assertEqual(mapping[26343], 21299)   # Yoichi's Arrow
        self.assertEqual(mapping[26344], 21298)   # Artemis's Arrow
        self.assertEqual(mapping[26345], 21297)   # Chrono Arrow
        self.assertEqual(mapping[26346], 21311)   # Quelling Bolt
        pouch = self.service.item(POUCH)
        self.assertEqual(int(pouch["usable"]), 1)
        row = next(item for item in self.service.dispense_items()
                   if int(item["item_id"]) == POUCH)
        self.assertEqual(int(row["max_charges"]), 1)
        self.assertEqual(int(row["use_delay"]), 10)
        self.assertEqual(int(row["reuse_delay"]), 3600)

    def test_ready_pouch_packet_has_one_charge_and_no_timer(self):
        packet = self.session.item_packet(self.pouch)
        attr = packet[4 + 13:4 + 37]
        self.assertEqual(attr[0], 1)
        self.assertEqual(attr[1], 1)
        self.assertEqual(attr[3] & 0x80, 0x80)
        self.assertEqual(attr[3] & 0x40, 0x40)   # ready
        self.assertEqual(attr[3] & 0x20, 0)      # not empty
        self.assertEqual(struct.unpack_from("<I", attr, 4)[0], 0)
        self.assertEqual(struct.unpack_from("<I", attr, 8)[0], 0)

    def test_using_the_pouch_grants_99_bullets_and_starts_a_reuse_timer(self):
        self.session.queue.clear()
        self.session.item_use(use_packet(int(self.pouch["container"]),
                                         int(self.pouch["slot"])))
        self.assertEqual(self.bullets(), 99)
        after = self.service.inventory_slot(
            int(self.character["id"]), int(self.pouch["container"]),
            int(self.pouch["slot"]))
        self.assertIsNotNone(after)
        self.assertEqual(int(after["quantity"]), 1)
        timer = item_usable.read_timer(after["extra"])
        self.assertIsNotNone(timer)
        self.assertEqual(timer[0], 1)             # one-charge items keep their charge
        self.assertGreater(timer[1], 0)           # the last-use timestamp started

        pouch_packets = self.item_packets(POUCH)
        self.assertEqual(len(pouch_packets), 1)
        attr = pouch_packets[0][13:37]
        self.assertEqual(attr[0], 1)
        self.assertEqual(attr[1], 1)
        self.assertEqual(attr[3] & 0x40, 0)       # no longer ready
        self.assertGreater(struct.unpack_from("<I", attr, 4)[0], 0)

        bullet_packets = self.item_packets(LIVING_BULLET)
        self.assertEqual(len(bullet_packets), 1)
        self.assertEqual(struct.unpack_from("<I", bullet_packets[0], 0)[0], 99)

    def test_second_use_before_the_hour_does_not_dispense_again(self):
        self.session.item_use(use_packet(int(self.pouch["container"]),
                                         int(self.pouch["slot"])))
        self.assertEqual(self.bullets(), 99)
        self.session.queue.clear()
        self.session.item_use(use_packet(int(self.pouch["container"]),
                                         int(self.pouch["slot"])))
        self.assertEqual(self.bullets(), 99)
        self.assertTrue(any(b"wait longer" in message
                            for message in self.session.queue))

    def test_expired_timer_dispenses_again(self):
        self.session.item_use(use_packet(int(self.pouch["container"]),
                                         int(self.pouch["slot"])))
        expired = item_usable.encode_timer(
            1, int(time.time()) - VANA_EPOCH - 3601)
        self.service.set_item_extra(
            int(self.character["id"]), int(self.pouch["container"]),
            int(self.pouch["slot"]), expired)
        self.session.queue.clear()
        self.session.item_use(use_packet(int(self.pouch["container"]),
                                         int(self.pouch["slot"])))
        self.assertEqual(self.bullets(), 198)

    def test_timer_block_round_trip_and_expiry(self):
        now = 1_800_000_000.0
        ready = item_usable.charged_attr(
            None, now=now, max_charges=1, reuse_delay=3600, use_delay=10,
            vana_epoch=VANA_EPOCH)
        self.assertEqual(ready[3], 0xC0)
        used = item_usable.record_use(
            None, now=now, max_charges=1, vana_epoch=VANA_EPOCH)
        self.assertEqual(item_usable.read_timer(used), (1, int(now) - VANA_EPOCH))
        attr = item_usable.charged_attr(
            used, now=now + 10, max_charges=1, reuse_delay=3600, use_delay=10,
            vana_epoch=VANA_EPOCH)
        self.assertEqual(attr[3], 0x80)
        self.assertGreater(struct.unpack_from("<I", attr, 4)[0], 0)
        self.assertEqual(item_usable.cooldown_remaining(
            used, now=now + 10, reuse_delay=3600, vana_epoch=VANA_EPOCH), 3590)
        self.assertEqual(item_usable.cooldown_remaining(
            used, now=now + 3600, reuse_delay=3600, vana_epoch=VANA_EPOCH), 0)
        expired = item_usable.charged_attr(
            used, now=now + 3600, max_charges=1, reuse_delay=3600, use_delay=10,
            vana_epoch=VANA_EPOCH)
        self.assertEqual(expired[3], 0xC0)


if __name__ == "__main__":
    unittest.main()
