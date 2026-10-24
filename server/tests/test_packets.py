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
        # A standard NPC/mob spawn is 0x48 bytes including the sub-message header, so the body
        # is 0x44; the larger "equipped model" shape (0x54) pushes the look block out of place.
        self.assertEqual(len(body), 0x44)
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
        self.assertEqual(struct.unpack_from("<I", body, 44)[0], 612 << 16)
        self.assertEqual(body[48], 0x01)    # literal-name marker
        self.assertEqual(body[49:61], b"Orcish Grunt")

    def test_trust_spawn_flags_and_master_packet(self):
        look = bytes.fromhex("0000b80b" + "00" * 16)
        entity = self.entity(
            kind="trust", targid=0x700, name="Shantotto", model=3000,
            look=look, hp=3170, hp_max=3170, triggerable=False,
            owner_char_id=1, trust_spell=896)
        body = packets.entity_update(entity)
        self.assertEqual(body[36] & 0x45, 0x45)   # Trust + PetNew + Pet
        self.assertEqual(body[37], 1)              # player allegiance
        self.assertEqual(struct.unpack_from("<I", body, 44)[0], 3000 << 16)
        # Spawnables (targid >= 0x700) carry their name at 0x38, not the static 0x35.
        self.assertEqual(body[52:61], b"Shantotto")
        self.assertEqual(body[48:52], bytes(4))

        set_name = packets.entity_set_name(entity, 0x400)
        self.assertEqual(len(set_name), 0x14)
        self.assertEqual(set_name[0:2], b"\x03\x05")
        self.assertEqual(struct.unpack_from("<H", set_name, 2)[0], 0x700)
        self.assertEqual(struct.unpack_from("<I", set_name, 4)[0], entity.id)
        self.assertEqual(struct.unpack_from("<H", set_name, 8)[0], 0x400)
        self.assertEqual(set_name[12], 0x04)

    def test_despawn_and_hp_layout(self):
        entity = self.entity(hp=0, alive=False)
        body = packets.entity_update(entity, packets.SEND_HP)
        # ClaimStatus (0x02) rides on every non-despawn update so the client keeps the
        # owner it reads for the claim; the HP mask is still part of the byte.
        self.assertEqual(body[6], packets.SEND_HP | 0x02)
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


def decode_battle_results(body):
    """Every result of the single target, in packet order."""
    read = read_bits(body)
    for _ in range(32 + 6 + 4 + 4 + 32 + 32 + 32):
        read(1)
    results = []
    for _ in range(read(4)):
        entry = {
            "resolution": read(3), "kind": read(2), "animation": read(12), "info": read(5),
            "distortion": read(2), "knockback": read(3), "damage": read(17),
            "message": read(10), "modifier": read(31), "add_effect": read(1),
        }
        if entry["add_effect"]:
            entry.update(add_kind=read(6), add_info=read(4), add_value=read(17),
                         add_message=read(10))
        entry["reaction"] = read(1)
        results.append(entry)
    return results


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

    def test_a_dual_wield_round_packs_both_hands_in_order(self):
        body = packets.battle_action(1, 2, results=[
            {"damage": 120, "animation": 0},
            {"damage": 80, "animation": 1, "critical": True},
        ])
        self.assertEqual(decode_battle(body)["results"], 2)
        first, second = decode_battle_results(body)
        self.assertEqual((first["animation"], first["damage"]), (0, 120))
        self.assertEqual(first["message"], packets.MESSAGE_ATTACK_HITS)
        self.assertEqual((second["animation"], second["damage"]), (1, 80))
        self.assertEqual(second["message"], packets.MESSAGE_ATTACK_CRIT)
        # The byte count at 0x04 covers the whole round, and the body is one byte longer.
        self.assertEqual(body[0], len(body) - 1)

    def test_a_full_eight_hit_round_fits_the_packet(self):
        results = [{"damage": 10 + index, "animation": index // 4} for index in range(8)]
        body = packets.battle_action(1, 2, results=results)
        decoded = decode_battle_results(body)
        self.assertEqual(len(decoded), 8)
        self.assertEqual([entry["animation"] for entry in decoded], [0] * 4 + [1] * 4)
        self.assertEqual(body[0], len(body) - 1)

    def test_skillchain_additional_effect_block_roundtrips(self):
        body = packets.battle_action(1, 2, results=[{
            "damage": 1000, "animation": 160, "message": packets.MESSAGE_DAMAGE,
            # Fusion proc 6, 600 resonance damage, message 287 + 6.
            "add_effect": 6, "add_value": 600, "add_message": 293,
        }])
        result = decode_battle_results(body)[0]
        self.assertEqual(result["add_effect"], 1)
        self.assertEqual(result["add_kind"], 6)
        self.assertEqual(result["add_info"], 0)
        self.assertEqual(result["add_value"], 600)
        self.assertEqual(result["add_message"], 293)
        self.assertEqual(result["reaction"], 0)
        self.assertEqual(body[0], len(body) - 1)

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
