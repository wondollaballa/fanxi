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
ACTION_CAST_MAGIC = 0x03
ACTION_ATTACK_OFF = 0x04
ACTION_CHANGE_TARGET = 0x0F
ACTION_WEAPONSKILL = 0x07
ACTION_JOBABILITY = 0x09

# 0x028 action categories and result messages.
ACTION_CATEGORY_BASIC_ATTACK = 1
ACTION_CATEGORY_SKILL_FINISH = 3    # weapon skill result
ACTION_CATEGORY_MAGIC_FINISH = 4   # result of a spell
ACTION_CATEGORY_ITEM_FINISH = 5     # item use result; its animation is the eat/drink motion
ACTION_CATEGORY_ABILITY_FINISH = 6  # job ability result
ACTION_CATEGORY_MAGIC_START = 8    # cast bar + casting animation
# result.resolution: the client reads 0 as a hit and 1 as a miss (LSB's ActionResolution).
RESOLUTION_HIT = 0
RESOLUTION_MISS = 1
BASIC_ATTACK_ID = 0x306B7461  # "atk0"

MESSAGE_ATTACK_HITS = 1
MESSAGE_MAGIC_DMG = 2
MESSAGE_DEFEATS_TARGET = 6
MESSAGE_MAGIC_RECOVERS_HP = 7
MESSAGE_ATTACK_MISSES = 15
MESSAGE_SHADOW_ABSORB = 31
MESSAGE_ATTACK_CRIT = 67
MESSAGE_MAGIC_NO_EFFECT = 75
MESSAGE_MAGIC_TELEPORT = 93
MESSAGE_USES_JOB_ABILITY = 100
MESSAGE_SKILL_RECOVERS_HP = 103  # "<user> uses <skill>. <target> recovers N HP."
MESSAGE_DAMAGE = 185        # "<user> uses <skill>. <target> takes N points of damage."
MESSAGE_SKILL_DRAIN_HP = 187  # "<user> uses <skill>. <amount> HP drained from <target>."
MESSAGE_SKILL_RECOVERS_MP = 224  # "<user> uses <skill>. <target> recovers N MP."
MESSAGE_SKILL_DRAIN_MP = 225  # "<user> uses <skill>. <amount> MP drained from <target>."
MESSAGE_TARGET_TAKES_DAMAGE = 264  # "<target> takes N points of damage." -- DoT ticks
MESSAGE_STATUS_IS = 203
MESSAGE_STATUS_WEARS_OFF = 206
MESSAGE_MAGIC_GAIN_EFFECT = 230
MESSAGE_MAGIC_ENFEEB = 237
MESSAGE_MAGIC_DRAIN_HP = 227
MESSAGE_MAGIC_DRAIN_MP = 228
MESSAGE_MAGIC_STARTS_CASTING = 327

# The four-character code in cmd_arg for a Magic Start, by spell skill.  The client uses
# it to pick the casting animation and the interrupt code; a spell id there makes the
# cast look like the wrong school (or not play at all).
MAGIC_CAST_WHITE = 0x68776163   # "cawh"
MAGIC_CAST_BLACK = 0x6B626163   # "cabk"
MAGIC_CAST_NINJUTSU = 0x6A6E6163  # "canj"
MAGIC_CAST_SONG = 0x6F736163    # "caso"
MAGIC_CAST_SUMMON = 0x6D736163  # "casm"
MAGIC_CAST_BLUE = 0x6C626163    # "cabl"
MAGIC_CAST_GEOMANCY = 0x65676163  # "cage"
MAGIC_CAST_TRUST = 0x61666163    # "cafa", the Trust magic cast 4CC

# Spell skill ids, the ones the spells table uses.
SKILL_DIVINE = 32
SKILL_HEALING = 33
SKILL_ENHANCING = 34
SKILL_ENFEEBLING = 35
SKILL_ELEMENTAL = 36
SKILL_DARK = 37
SKILL_SUMMONING = 38
SKILL_NINJUTSU = 39
SKILL_SINGING = 40
SKILL_BLUE = 43
SKILL_GEOMANCY = 44


def magic_cast_arg(skill: int) -> int:
    """The 4CC a Magic Start carries for a spell of this skill."""
    skill = int(skill)
    if skill == SKILL_NINJUTSU:
        return MAGIC_CAST_NINJUTSU
    if skill == SKILL_SUMMONING:
        return MAGIC_CAST_SUMMON
    if skill in (SKILL_SINGING, 41, 42):
        return MAGIC_CAST_SONG
    if skill == SKILL_BLUE:
        return MAGIC_CAST_BLUE
    if skill == SKILL_GEOMANCY:
        return MAGIC_CAST_GEOMANCY
    if skill in (SKILL_ELEMENTAL, SKILL_DARK):
        return MAGIC_CAST_BLACK
    return MAGIC_CAST_WHITE

SEND_POSITION = 0x01
SEND_STATUS = 0x02
SEND_HP = 0x04
SEND_NAME = 0x08
SEND_MODEL = 0x10
SEND_SPAWN = SEND_POSITION | SEND_STATUS | SEND_HP | SEND_NAME
# 0x00D is the player entity: a full spawn must also carry the model section (0x1F).
SEND_CHAR_SPAWN = SEND_SPAWN | SEND_MODEL
SEND_DESPAWN = 0x30
# 0x00D has its own SendFlg bitfield: Despawn is bit 5. The 0x00E mask (0x30) is not
# the same field, and a player sent with it stays on the client's entity list.
SEND_PLAYER_DESPAWN = 0x20

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


def entity_update(entity, mask: int = SEND_SPAWN, despawn: bool = False,
                  equipped: bool = False, name_only: bool = False) -> bytes:
    """Body of a 0x00E NPC/mob entity update.

    A standard NPC/mob spawn is 0x48 bytes including the sub-message header, so the body is
    0x44.  Sending the larger "equipped model" shape makes the client read the look block in
    the wrong place and the entity never renders.
    """
    body = bytearray(0x44)
    struct.pack_into("<I", body, 0, int(entity.id))
    struct.pack_into("<H", body, 4, int(entity.targid))
    body[6] = SEND_DESPAWN if despawn else mask
    body[7] = int(getattr(entity, "rot", 0)) & 0xFF
    struct.pack_into("<f", body, 8, float(entity.x))
    struct.pack_into("<f", body, 12, float(entity.y))
    struct.pack_into("<f", body, 16, float(entity.z))
    # 0x18: "moving".  Left at zero, the client plays the idle animation (which for most
    # mobs is a look-around) while the server slides them along the ground.
    struct.pack_into("<H", body, 20, 1 if getattr(entity, "moving", False) else 0)
    struct.pack_into("<H", body, 22, (int(entity.targid) << 1) & 0xFFFF)
    body[24] = int(getattr(entity, "speed", 50)) & 0xFF   # 0x1C: how fast it travels
    # 0x1D animationSpeed drives the walk cycle, not the ground speed.  Tying it to the
    # (slow) travel speed made every mob waddle along with barely-moving legs.
    body[25] = 40
    body[26] = 100 if despawn else int(entity.hpp())
    body[27] = 2 if despawn else (int(getattr(entity, "animation", 0)) & 0xFF)
    body[28] = 1 if getattr(entity, "kind", "") == "mob" and entity.alive else 0
    body[29] = 0
    is_trust = getattr(entity, "kind", "") == "trust"
    body[33] = (0x08 if (getattr(entity, "kind", "") == "mob" or is_trust)
                and entity.alive else 0)  # health flag
    body[35] = int(getattr(entity, "name_prefix", 0)) & 0xFF
    trigger = bool(getattr(entity, "triggerable", False)) and entity.alive
    body[36] = 0x40 if trigger else 0
    body[37] = 0  # allegiance: neutral
    body[39] = int(getattr(entity, "namevis", 0)) & 0xFF
    # The claiming player's character id.  The client colours the target name red and
    # keeps the claim shield from this field; left at 0 the mob stays "unclaimed" even
    # while it is swinging at the player who pulled it.  ``engaged_char_id`` is the
    # session the monster has hate on, so it is exactly the claim owner.
    if is_trust:
        # TrustFlag (0x01) gives the client the "Release" sub-menu, PetFlag (0x40)
        # treats the alter ego as an ally and PetNewFlag (0x04) plays the spawn-in
        # animation.  Allegiance 1 is the player side.  The flags ride every update,
        # not just the spawn, because that is what also lets a Trust be despawned.
        body[36] = (body[36] | 0x45) & 0xFF
        body[37] = 1
    claim = 0
    if getattr(entity, "kind", "") == "mob":
        # claim_char_id survives the monster's death, so the corpse keeps its red name
        # until it despawns; the hate target is cleared when the fight ends.
        claim = int(getattr(entity, "claim_char_id", 0)
                    or getattr(entity, "engaged_char_id", 0) or 0)
    struct.pack_into("<I", body, 40, claim)  # owner (packet 0x2C)
    # ClaimStatus (0x02) is the flag that tells the client to read the owner.  LSB only
    # writes 0x2C under UPDATE_STATUS, and without the bit every position update made the
    # client forget the claim (the name went red -> yellow -> red while the fight went on).
    if not despawn:
        body[6] = (body[6] | 0x02) & 0xFF
    if name_only:
        # A name-only update after the equipped look: mask has no look bits, so the
        # client keeps the appearance while setting the target name.
        body[6] = (SEND_NAME | 0x02) & 0xFF
        if is_trust:
            # Spawnables (targid 0x700-0x8FF) have no literal-name marker: the client
            # reads the name at 0x38, not 0x35.
            body[52:68] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
        else:
            body[48] = 0x01
            body[49:65] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
        return bytes(body)

    size = int(getattr(entity, "size", 0)) & 0xFFFF
    model = int(getattr(entity, "model", 0)) & 0xFFFF
    if equipped:
        look = bytes(getattr(entity, "look", b"") or b"")
        if len(look) >= 20:
            # Equipped NPC (SubKind 1): SendFlg.Model must be set or the client
            # ignores the GrapIDTbl data entirely.  Field layout is SubKind at
            # 0x2C, then GrapIDTbl[9] (look offset 2..20) at 0x2E.
            body[6] = (body[6] | 0x10) & 0xFF
            body[44:64] = look[:20]
            return bytes(body)

    if size == 2 and getattr(entity, "kind", "") == "npc" and not is_trust:
        # door: the client's static door mesh binds to this look/door id.  NPCs only -- a mob
        # carrying LSB's model_size 2 is a large monster, not a door.
        # Field-for-field match of a captured LandSandBoat door spawn.  Doors have
        # no name marker and no trigger flag; the four bytes at 0x30 are the door id.
        struct.pack_into("<I", body, 20, 1)          # flags0
        struct.pack_into("<H", body, 22, 0)          # no sub-target
        body[25] = 50                                # animation speed
        body[27] = int(getattr(entity, "animation", 0)) or 9  # 9 = closed door
        body[29] = 3
        body[30] = 0x10
        body[33] = 0
        body[36] = 0                                 # doors are not NPC triggers
        struct.pack_into("<H", body, 44, 2)
        struct.pack_into("<H", body, 46, 0)
        door = int(getattr(entity, "door_id", 0) or 0)
        if not door:
            door = int.from_bytes(entity.name.encode("ascii", "replace")[:4].ljust(4, b"\0"), "little")
        struct.pack_into("<I", body, 48, door)
    else:
        render_model = int(getattr(entity, "model", 0) or 0)
        if render_model:
            # The client's standard NPC path takes a race/specific model id.  Race
            # ids: Hume 32/37, Elvaan 42/47, Tarutaru 109, Moogle 82, Goblin 85.
            struct.pack_into("<I", body, 44, render_model << 16)
        else:
            look = bytes(getattr(entity, "look", b"") or b"")
            look_model = int.from_bytes(look[2:4], "little") if len(look) >= 4 else model
            struct.pack_into("<I", body, 44, look_model << 16)
        if is_trust:
            # A Trust is a spawnable (targid >= 0x700), so its name lives at 0x38
            # and 0x34 stays part of the model block.  0x067 also carries the name
            # and tells the client this entity is a Trust of the master.
            body[48:52] = bytes(4)
            body[52:68] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
        else:
            # Static NPCs/mobs carry a literal name.  The client's NPC path reads a one-byte
            # name-type marker at 0x34 before the string; without it the client falls back to
            # the model's DAT name ("NPC").
            body[48] = 0x01
            # The client reads the full 16-byte field; cstr() reserves a terminator and would
            # truncate "Wandering Moogle" to "Wandering Moogl".
            body[49:65] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
    return bytes(body)


def entity_despawn(entity) -> bytes:
    return entity_update(entity, SEND_DESPAWN, despawn=True)


def entity_set_name(entity, master_targid: int) -> bytes:
    """Body of a 0x067: tell the client this spawnable is a Trust and who owns it.

    The client uses this to show the Trust sub-menu ("Release") and to attach the
    alter ego to its master.  It is sent to the owner only; every other client draws
    the Trust from the ordinary 0x00E spawn.  0x067 is shared with the player level
    block (``char_sync``), which starts 0x02/0x09; this one starts 0x03/0x05.
    """
    body = bytearray(0x14)
    body[0] = 0x03
    body[1] = 0x05
    struct.pack_into("<H", body, 2, int(entity.targid) & 0xFFFF)
    struct.pack_into("<I", body, 4, int(entity.id) & 0xFFFFFFFF)
    struct.pack_into("<H", body, 8, int(master_targid) & 0xFFFF)
    body[12] = 0x04
    return bytes(body)


def battle_action(actor_id: int, target_id: int, damage: int = 0, *, miss: bool = False,
                  critical: bool = False, defeated: bool = False, animation: int = 0,
                  message: int | None = None, kind: int = 1,
                  category: int = ACTION_CATEGORY_BASIC_ATTACK,
                  action_id: int = BASIC_ATTACK_ID, hit_distortion: int = 0,
                  info: int | None = None, results: list[dict] | None = None) -> bytes:
    """Body of a 0x028 action packet (one target, one or more results).

    ``results`` is the target's result list; a melee round passes one entry per hand,
    main hand first.  The client plays the swings in that order from this count
    (Windower's ``action_count``), which is what makes a dual-wield round look right.
    Without ``results`` the single-result keywords describe the one hit.

    Per result, ``animation`` is the result's sub_kind: the swing hand (0 main, 1 off),
    a weapon skill's animation, or -- for a finished spell -- the spell id the client
    animates from.  ``damage`` is the result's 17-bit value: damage, HP healed, or the
    status effect id a spell lands.  ``info`` is the 5-bit result info; attacks use the
    defeated/critical flags, while a finished spell carries its recast there.
    """
    results = results or []
    if not results:
        results = [dict(damage=damage, miss=miss, critical=critical, defeated=defeated,
                        animation=animation, message=message, info=info,
                        hit_distortion=hit_distortion, kind=kind)]
    writer = BitWriter()
    writer.write(actor_id, 32)
    writer.write(1, 6)                 # target count
    writer.write(0, 4)                 # res_sum is always 0
    writer.write(category, 4)
    writer.write(action_id, 32)
    writer.write(0, 32)                # recast
    writer.write(target_id, 32)
    writer.write(len(results), 4)      # results for this target (a round has one per hand)
    for entry in results:
        hit_miss = bool(entry.get("miss", False))
        hit_critical = bool(entry.get("critical", False))
        hit_defeated = bool(entry.get("defeated", False))
        hit_message = entry.get("message", message)
        if hit_message is None:
            hit_message = (MESSAGE_ATTACK_MISSES if hit_miss
                           else MESSAGE_ATTACK_CRIT if hit_critical else MESSAGE_ATTACK_HITS)
        hit_info = entry.get("info", info)
        if hit_info is None:
            hit_info = (1 if hit_defeated else 0) | (2 if hit_critical else 0)
        writer.write(RESOLUTION_MISS if hit_miss else RESOLUTION_HIT, 3)
        writer.write(entry.get("kind", kind), 2)
        writer.write(entry.get("animation", animation), 12)
        writer.write(hit_info & 0x1F, 5)
        writer.write(entry.get("hit_distortion", hit_distortion), 2)
        writer.write(0, 3)             # knockback
        writer.write(max(0, int(entry.get("damage", damage))) & 0x1FFFF, 17)
        writer.write(hit_message, 10)
        writer.write(0, 31)            # modifier
        # Optional additional-effect block.  A skillchain uses this on the closing
        # weapon-skill result: proc_kind is ActionProcSkillChain, value is the
        # resonance damage, and the message is 287 + proc (384 + proc when absorbed).
        add_kind = max(0, min(63, int(entry.get("add_effect", 0) or 0)))
        if add_kind:
            writer.write(1, 1)
            writer.write(add_kind, 6)
            writer.write(max(0, int(entry.get("add_info", 0) or 0)) & 0xF, 4)
            writer.write(max(0, int(entry.get("add_value", 0) or 0)) & 0x1FFFF, 17)
            writer.write(max(0, int(entry.get("add_message", 0) or 0)) & 0x3FF, 10)
        else:
            writer.write(0, 1)         # no additional effect
        writer.write(0, 1)             # no reaction effect
    bits = writer.bytes()
    # Byte 0x04 of the packet is the packed byte count (LSB's workSize); the packet's own
    # length is one more than it.  Writing count+1 here made the client drop the action.
    return bytes([min(255, len(bits))]) + bits


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


def motion_message(caster_id: int, target_id: int, caster_targid: int, target_targid: int,
                   emote_id: int, mode: int = 0, param: int = 0) -> bytes:
    """Body of a 0x05A MOTIONMES: play an emote for the client and write its text line.

    The client does not draw its own outgoing emote, so the server has to echo it back
    (and send it to every other player in range).  The 52-byte body reserves five
    Trust ids even when none are out; the client always reads the full layout.
    """
    body = bytearray(52)
    struct.pack_into("<IIHHHHHBB", body, 0, int(caster_id) & 0xFFFFFFFF,
                     int(target_id) & 0xFFFFFFFF, int(caster_targid) & 0xFFFF,
                     int(target_targid) & 0xFFFF, int(emote_id) & 0xFFFF,
                     int(param) & 0xFFFF, 0, int(mode) & 0xFF, 0)
    return bytes(body)


def lockstyle_error(item_ids) -> bytes:
    """Body of a 0x11C: the style-lock items the server refused to apply."""
    ids = [int(item_id) for item_id in item_ids][:16]
    body = bytearray(36)
    body[0] = len(ids)
    for index, item_id in enumerate(ids):
        struct.pack_into("<H", body, 4 + index * 2, item_id & 0xFFFF)
    return bytes(body)


def system_message(message_id: int, unique_no: int = 0, act_index: int = 0,
                   attr: int = 0) -> bytes:
    """Body of a 0x009 message: draw a line from the client's own system-message DAT.

    Style lock replies use this (Message IDs 267..270), so the player sees the same
    "Style lock mode enabled." line retail shows without Fanxi shipping the text.
    """
    return struct.pack("<IHHB", int(unique_no) & 0xFFFFFFFF, int(act_index) & 0xFFFF,
                       int(message_id) & 0xFFFF, int(attr) & 0xFF)


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
    """Body of a 0x01D container sync packet.

    ``flags`` is the client's complete container-ready mask, not a delta: the client replaces
    its mask with it.  A state-1 packet must therefore carry every loaded container, or the bags
    it leaves out draw empty.  ``container`` is informational.
    """
    return struct.pack("<BB2xI", int(state) & 0xFF, int(container) & 0xFF, int(flags) & 0xFFFFFFFF)


def event_num(entity, zone: int, event_id: int, params, mode: int = 8,
              text_table: int | None = None) -> bytes:
    """Body of a 0x034 EVENTNUM: start (or restart) an event with eight numbers."""
    body = bytearray(48)
    struct.pack_into("<I", body, 0, int(entity.id))
    for index, value in enumerate(list(params)[:8]):
        struct.pack_into("<I", body, 4 + index * 4, int(value) & 0xFFFFFFFF)
    table = int(zone) if text_table is None else int(text_table)
    struct.pack_into("<HHHHHH", body, 36, int(entity.targid) & 0xFFFF, int(zone) & 0xFFFF,
                     int(event_id) & 0xFFFF, int(mode) & 0xFFFF, table & 0xFFFF, 0)
    return bytes(body)


def pending_num(values) -> bytes:
    """Body of a 0x05C event-parameter update (eight numbers)."""
    body = bytearray(32)
    for index, value in enumerate(list(values)[:8]):
        struct.pack_into("<i", body, index * 4, int(value))
    return bytes(body)


def talk_num_work(entity, text_id: int, params=(), show_name: bool = False) -> bytes:
    """Body of a 0x02A TALKNUMWORK: a formatted message from the client's zone text."""
    body = bytearray(60)
    struct.pack_into("<I", body, 0, int(entity.id))
    for index, value in enumerate(list(params)[:4]):
        struct.pack_into("<i", body, 4 + index * 4, int(value))
    struct.pack_into("<HH", body, 20, int(entity.targid) & 0xFFFF, int(text_id) & 0xFFFF)
    body[24] = 0  # Type
    body[25] = 0  # Flag
    if show_name:
        name = str(entity.name).encode("ascii", "replace")[:31]
        body[26:26 + len(name)] = name
    return bytes(body)


def item_max() -> bytes:
    """Body of a 0x01C container-size packet: 18 containers plus their usable sizes."""
    body = bytearray(96)
    for index in range(18):
        body[index] = 81
        struct.pack_into("<H", body, 32 + 2 * index, 81)
    return bytes(body)
