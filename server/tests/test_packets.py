"""Zone packet layouts: headers, entity updates, battle actions and inventory."""
from __future__ import annotations

import struct
import unittest

import support  # noqa: F401

from fanxi_server.game import packets
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.zone import sub


def read_bits(body: bytes):
    position = 0

    def read(bits: int) -> int:
        nonlocal position
        value = 0
        for index in range(bits):
            value |= ((body[1 + position // 8] >> (position % 8)) & 1) << index
            position += 1
        return value

    return read


class HeaderTest(unittest.TestCase):
    def test_sub_header_packs_type_and_32bit_size(self):
        packet = sub(0x00E, bytes(0x54))
        self.assertEqual(len(packet), 0x58)
        header = struct.unpack_from("<H", packet, 0)[0]
        self.assertEqual(header & 0x1FF, 0x00E)
        self.assertEqual(header >> 9, 0x58 // 4)
        self.assertEqual(bytes(packet[4:]), bytes(0x54))

    def test_sub_rejects_oversized_messages(self):
        with self.assertRaises(ValueError):
            sub(0x0FF, bytes(600))


class EntityPacketTest(unittest.TestCase):
    def entity(self, **overrides):
        values = dict(
            kind="mob", id=0x010F6200, targid=0x200, zone=246, name="Orcish Grunt",
            x=-150.0, y=-62.0, z=250.0, rot=64, model=612, size=0, speed=50,
            alive=True, hp=80, hp_max=80, triggerable=True, name_prefix=0, namevis=0,
            animation=0,
        )
        values.update(overrides)
        return ZoneEntity(**values)

    def test_spawn_layout(self):
        entity = self.entity()
        body = packets.entity_update(entity)
        self.assertEqual(len(body), 0x54)
        self.assertEqual(struct.unpack_from("<I", body, 0)[0], entity.id)
        self.assertEqual(struct.unpack_from("<H", body, 4)[0], entity.targid)
        self.assertEqual(body[6], packets.SEND_SPAWN)
        self.assertEqual(struct.unpack_from("<f", body, 8)[0], -150.0)
        self.assertEqual(struct.unpack_from("<f", body, 12)[0], -62.0)
        self.assertEqual(struct.unpack_from("<f", body, 16)[0], 250.0)
        self.assertEqual(body[24], 50)
        self.assertEqual(body[26], 100)
        self.assertEqual(body[28], 1)       # mob status
        self.assertEqual(body[33], 0x08)    # alive
        self.assertEqual(body[36], 0x40)    # triggerable
        self.assertEqual(struct.unpack_from("<HH", body, 44), (0, 612))
        self.assertEqual(body[48:60], b"Orcish Grunt")

    def test_despawn_and_hp_layout(self):
        entity = self.entity(hp=0, alive=False)
        body = packets.entity_update(entity, packets.SEND_HP)
        self.assertEqual(body[6], packets.SEND_HP)
        self.assertEqual(body[26], 0)
        self.assertEqual(body[33], 0)
        dead = packets.entity_despawn(entity)
        self.assertEqual(dead[6], packets.SEND_DESPAWN)
        self.assertEqual(dead[27], 2)


def decode_battle(body):
    read = read_bits(body)
    result = {
        "actor": read(32), "targets": read(6), "res_sum": read(4), "category": read(4),
        "action": read(32), "recast": read(32), "target": read(32), "results": read(4),
    }
    result.update({
        "resolution": read(3), "kind": read(2), "animation": read(12), "info": read(5),
        "distortion": read(2), "knockback": read(3), "damage": read(17), "message": read(10),
    })
    return result


class BattlePacketTest(unittest.TestCase):
    def test_basic_attack_roundtrip(self):
        body = packets.battle_action(0x01000001, 0x010F6200, 37, critical=True, defeated=True)
        decoded = decode_battle(body)
        self.assertEqual(decoded["actor"], 0x01000001)
        self.assertEqual(decoded["targets"], 1)
        self.assertEqual(decoded["category"], packets.ACTION_CATEGORY_BASIC_ATTACK)
        self.assertEqual(decoded["action"], packets.BASIC_ATTACK_ID)
        self.assertEqual(decoded["target"], 0x010F6200)
        self.assertEqual(decoded["results"], 1)
        self.assertEqual(decoded["resolution"], 0)
        self.assertEqual(decoded["kind"], 1)
        self.assertEqual(decoded["info"] & 1, 1)
        self.assertEqual(decoded["info"] & 2, 2)
        self.assertEqual(decoded["damage"], 37)
        self.assertEqual(decoded["message"], packets.MESSAGE_ATTACK_CRIT)

    def test_miss_uses_miss_message(self):
        decoded = decode_battle(packets.battle_action(1, 2, 0, miss=True))
        self.assertEqual(decoded["resolution"], 1)
        self.assertEqual(decoded["damage"], 0)
        self.assertEqual(decoded["message"], packets.MESSAGE_ATTACK_MISSES)

    def test_battle_messages(self):
        msg = packets.battle_message(1, 2, 0x400, 0x200, 565, 0, 565)
        self.assertEqual(len(msg), 24)
        self.assertEqual(struct.unpack_from("<H", msg, 20)[0], 565)
        exp = packets.battle_message2(1, 1, 0x400, 0x400, 26, 0, 8)
        self.assertEqual(len(exp), 24)
        self.assertEqual(struct.unpack_from("<H", exp, 20)[0], 8)

    def test_inventory_packets(self):
        self.assertEqual(len(packets.item_list(4112, 3, 0, 1)), 12)
        self.assertEqual(len(packets.item_same(0, 0, 1)), 8)
        self.assertEqual(len(packets.item_num(1000, 0, 0)), 8)
        self.assertEqual(len(packets.item_max()), 96)
        attr = packets.item_attr(65535, 1000, 0, 0)
        self.assertEqual(len(attr), 40)
        self.assertEqual(struct.unpack_from("<I", attr, 0)[0], 1000)
        self.assertEqual(struct.unpack_from("<H", attr, 8)[0], 65535)
        self.assertEqual(attr[10], 0)
        self.assertEqual(attr[11], 0)

    def test_shop_packets(self):
        self.assertEqual(len(packets.shop_open(3)), 4)
        items = [{"item_id": 4112, "price": 50}, {"item_id": 16534, "price": 500}]
        listing = packets.shop_list(items)
        self.assertEqual(len(listing), 4 + 24)
        self.assertEqual(listing[2], 0x89)
        self.assertEqual(struct.unpack_from("<I", listing, 4)[0], 50)
        self.assertEqual(struct.unpack_from("<H", listing, 8)[0], 4112)
        self.assertEqual(len(packets.shop_buy(0, 2)), 8)


if __name__ == "__main__":
    unittest.main()
