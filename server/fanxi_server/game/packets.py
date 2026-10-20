"""Zone packet builders for the world features Fanxi now speaks.

The layouts are the client's wire formats; the values and the implementation are Fanxi's own.
Each function returns the *body* of a zone sub-message; ``zone.sub(type, body)`` adds the
4-byte message header.
"""
from __future__ import annotations

import struct

from .cipher import cstr

# Player actions, from the client's action packet.
ACTION_TALK = 0x00
ACTION_ATTACK = 0x02
ACTION_ATTACK_OFF = 0x04
ACTION_CHANGE_TARGET = 0x0F

# 0x028 action categories and result messages.
ACTION_CATEGORY_BASIC_ATTACK = 1
BASIC_ATTACK_ID = 0x306B7461  # "atk0"

MESSAGE_ATTACK_HITS = 1
MESSAGE_ATTACK_MISSES = 15
MESSAGE_ATTACK_CRIT = 67
MESSAGE_DEFEATS_TARGET = 6

SEND_POSITION = 0x01
SEND_STATUS = 0x02
SEND_HP = 0x04
SEND_NAME = 0x08
SEND_SPAWN = SEND_POSITION | SEND_STATUS | SEND_HP | SEND_NAME
SEND_DESPAWN = 0x30

DEFAULT_NAME_PREFIX = 0

# Inventory locations used by the client.
CONTAINER_INVENTORY = 0


class BitWriter:
    """LSB-first bit writer, the order the FFXI client unpacks action packets in."""

    def __init__(self):
        self.data = bytearray()
        self.bit = 0

    def write(self, value: int, bits: int) -> None:
        value = int(value)
        for index in range(bits):
            if self.bit % 8 == 0:
                self.data.append(0)
            if (value >> index) & 1:
                self.data[self.bit // 8] |= 1 << (self.bit % 8)
            self.bit += 1

    def bytes(self) -> bytes:
        return bytes(self.data)


def entity_update(entity, mask: int = SEND_SPAWN, despawn: bool = False) -> bytes:
    """Body of a 0x00E NPC/mob entity update (0x58 total, 0x54 body)."""
    body = bytearray(0x54)
    struct.pack_into("<I", body, 0, int(entity.id))
    struct.pack_into("<H", body, 4, int(entity.targid))
    body[6] = SEND_DESPAWN if despawn else mask
    body[7] = int(getattr(entity, "rot", 0)) & 0xFF
    # Raw wire order is x, y, z (the client's DAT coordinates).
    struct.pack_into("<f", body, 8, float(entity.x))
    struct.pack_into("<f", body, 12, float(entity.y))
    struct.pack_into("<f", body, 16, float(entity.z))
    struct.pack_into("<I", body, 20, 0)  # flags0: still
    struct.pack_into("<H", body, 22, (int(entity.targid) << 1) & 0xFFFF)
    body[24] = int(getattr(entity, "speed", 50)) & 0xFF
    body[25] = 40  # animation/base speed
    body[26] = 100 if despawn else int(entity.hpp())
    body[27] = 2 if despawn else (int(getattr(entity, "animation", 0)) & 0xFF)
    body[28] = 1 if getattr(entity, "kind", "") == "mob" and entity.alive else 0
    body[29] = 0
    body[33] = 0x08 if entity.alive else 0  # health flag
    body[35] = int(getattr(entity, "name_prefix", 0)) & 0xFF
    trigger = bool(getattr(entity, "triggerable", False)) and entity.alive
    body[36] = 0x40 if trigger else 0
    body[37] = 0  # allegiance: neutral
    body[38] = 0  # animation sub
    body[39] = int(getattr(entity, "namevis", 0)) & 0xFF
    struct.pack_into("<I", body, 40, 0)  # owner
    struct.pack_into("<HH", body, 44, int(getattr(entity, "size", 0)), int(getattr(entity, "model", 0)))
    body[48:64] = cstr(entity.name, 16)
    return bytes(body)


def entity_despawn(entity) -> bytes:
    return entity_update(entity, SEND_DESPAWN, despawn=True)


def battle_action(actor_id: int, target_id: int, damage: int = 0, *, miss: bool = False,
                  critical: bool = False, defeated: bool = False, animation: int = 0,
                  message: int | None = None, kind: int = 1,
                  category: int = ACTION_CATEGORY_BASIC_ATTACK,
                  action_id: int = BASIC_ATTACK_ID, hit_distortion: int = 0) -> bytes:
    """Body of a 0x028 action packet (one target, one result)."""
    if message is None:
        message = MESSAGE_ATTACK_MISSES if miss else (MESSAGE_ATTACK_CRIT if critical else MESSAGE_ATTACK_HITS)
    info = (1 if defeated else 0) | (2 if critical else 0)
    writer = BitWriter()
    writer.write(actor_id, 32)
    writer.write(1, 6)                 # target count
    writer.write(0, 4)                 # result count (unused; targets carry their own)
    writer.write(category, 4)
    writer.write(action_id, 32)
    writer.write(0, 32)                # recast
    writer.write(target_id, 32)
    writer.write(1, 4)                 # one result
    writer.write(1 if miss else 0, 3)  # resolution
    writer.write(kind, 2)
    writer.write(animation, 12)
    writer.write(info, 5)
    writer.write(hit_distortion, 2)
    writer.write(0, 3)                 # knockback
    writer.write(max(0, int(damage)) & 0x1FFFF, 17)
    writer.write(message, 10)
    writer.write(0, 31)                # modifier
    writer.write(0, 1)                 # no additional effect
    writer.write(0, 1)                 # no reaction effect
    bits = writer.bytes()
    return bytes([min(255, 1 + len(bits))]) + bits


def battle_message(sender_id: int, target_id: int, sender_targid: int, target_targid: int,
                   param: int = 0, value: int = 0, message: int = 0, kind: int = 0) -> bytes:
    """Body of a 0x029 combat message (24 bytes; 28 total)."""
    body = bytearray(24)
    struct.pack_into("<IIIIHHHBB", body, 0, int(sender_id), int(target_id), int(param) & 0xFFFFFFFF,
                     int(value) & 0xFFFFFFFF, int(sender_targid) & 0xFFFF, int(target_targid) & 0xFFFF,
                     int(message) & 0xFFFF, int(kind) & 0xFF, 0)
    return bytes(body)


def battle_message2(sender_id: int, target_id: int, sender_targid: int, target_targid: int,
                    param: int = 0, value: int = 0, message: int = 0, kind: int = 0) -> bytes:
    """Body of a 0x02D end-of-combat message (EXP, chains, level ups)."""
    body = bytearray(24)
    struct.pack_into("<IIHHIIHBB", body, 0, int(sender_id), int(target_id),
                     int(sender_targid) & 0xFFFF, int(target_targid) & 0xFFFF,
                     int(param) & 0xFFFFFFFF, int(value) & 0xFFFFFFFF,
                     int(message) & 0xFFFF, int(kind) & 0xFF, 0)
    return bytes(body)


def chat_std(name: str, text: str, zone: int, kind: int = 0) -> bytes:
    """Body of a 0x017 chat message. kind 0 is say; 6 is a system line."""
    message = text.encode("ascii", "replace")[:150]
    return struct.pack("<BBH", int(kind) & 0xFF, 0, int(zone) & 0xFFFF) + cstr(name, 15) + message + b"\0"


def shop_open(count: int) -> bytes:
    """Body of a 0x03E shop-open packet."""
    return struct.pack("<H2x", max(0, int(count)) & 0xFFFF)


def shop_list(items: list[dict], offset: int = 0) -> bytes:
    """Body of a 0x03C shop list. items: [{item_id, price}], at most 19 per packet."""
    entries = items[:19]
    body = bytearray(4 + 12 * len(entries))
    struct.pack_into("<HBx", body, 0, int(offset) & 0xFFFF, 0x89 if len(items) <= 19 else 0)
    for index, item in enumerate(entries):
        struct.pack_into("<IHBBHH", body, 4 + 12 * index, int(item["price"]) & 0xFFFFFFFF,
                         int(item["item_id"]) & 0xFFFF, int(offset) + index, 0, 0, 0)
    return bytes(body)


def shop_buy(index: int, quantity: int, state: int = 0) -> bytes:
    """Body of a 0x03F shop-purchase result."""
    return struct.pack("<HBxI", int(index) & 0xFFFF, int(state) & 0xFF, int(quantity) & 0xFFFFFFFF)


def item_attr(item_id: int, quantity: int, container: int = 0, slot: int = 0, lock: int = 0,
              price: int = 0, extra: bytes = b"") -> bytes:
    """Body of a 0x020 item-attribute packet (40 bytes; 44 total)."""
    body = bytearray(40)
    struct.pack_into("<II", body, 0, max(0, int(quantity)) & 0xFFFFFFFF, max(0, int(price)) & 0xFFFFFFFF)
    struct.pack_into("<H", body, 8, int(item_id) & 0xFFFF)
    body[10] = int(container) & 0xFF
    body[11] = int(slot) & 0xFF
    body[12] = int(lock) & 0xFF
    body[13:37] = bytes(extra[:24]).ljust(24, b"\0")
    return bytes(body)


def item_num(quantity: int, container: int = 0, slot: int = 0, lock: int = 0) -> bytes:
    """Body of a 0x01E item-quantity packet (8 bytes; 12 total)."""
    return struct.pack("<IBBBx", max(0, int(quantity)) & 0xFFFFFFFF, int(container) & 0xFF,
                       int(slot) & 0xFF, int(lock) & 0xFF)


def item_list(item_id: int, quantity: int, container: int = 0, slot: int = 0, lock: int = 0) -> bytes:
    """Body of a 0x01F item entry."""
    return struct.pack("<IHBBB3x", max(0, int(quantity)), int(item_id) & 0xFFFF,
                       int(container) & 0xFF, int(slot) & 0xFF, int(lock) & 0xFF)


def item_same(state: int, container: int, flags: int) -> bytes:
    """Body of a 0x01D container sync packet."""
    return struct.pack("<BB2xI", int(state) & 0xFF, int(container) & 0xFF, int(flags) & 0xFFFFFFFF)


def item_max() -> bytes:
    """Body of a 0x01C container-size packet: 18 containers plus their usable sizes."""
    body = bytearray(96)
    for index in range(18):
        body[index] = 81
        struct.pack_into("<H", body, 32 + 2 * index, 81)
    return bytes(body)
