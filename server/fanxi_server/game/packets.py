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
ACTION_SHOOT = 0x10
ACTION_DISMOUNT = 0x12   # /dismount, or the Mount menu's "dismount" entry
ACTION_MOUNT = 0x1A      # /mount <name> and the Mount menu; ActionBuf[0] is the mount id

# 0x028 action categories and result messages.
ACTION_CATEGORY_BASIC_ATTACK = 1
ACTION_CATEGORY_SKILL_START = 7     # "<entity> readies <skill>": the client's WS context
ACTION_CATEGORY_SKILL_FINISH = 3    # weapon skill result
ACTION_CATEGORY_MAGIC_FINISH = 4   # result of a spell
ACTION_CATEGORY_ITEM_FINISH = 5     # item use result; its animation is the eat/drink motion
ACTION_CATEGORY_ABILITY_FINISH = 6  # job ability result
ACTION_CATEGORY_MAGIC_START = 8    # cast bar + casting animation
ACTION_CATEGORY_MOB_SKILL_FINISH = 11  # monster TP move result (skill ids 256+)
# result.resolution: the client reads 0 as a hit and 1 as a miss (LSB's ActionResolution).
RESOLUTION_HIT = 0
RESOLUTION_MISS = 1
BASIC_ATTACK_ID = 0x306B7461  # "atk0"

MESSAGE_ATTACK_HITS = 1
MESSAGE_MAGIC_DMG = 2
MESSAGE_MAGIC_BURST = 252              # "Magic Burst!" on a bursted spell
MESSAGE_DEFEATS_TARGET = 6
MESSAGE_MAGIC_RECOVERS_HP = 7
MESSAGE_ATTACK_MISSES = 15
MESSAGE_CASTING_INTERRUPTED = 16       # "The <player>'s casting is interrupted."
MESSAGE_SHADOW_ABSORB = 31
MESSAGE_ATTACK_CRIT = 67
MESSAGE_MAGIC_NO_EFFECT = 75
MESSAGE_MAGIC_TELEPORT = 93
MESSAGE_USES_JOB_ABILITY = 100
MESSAGE_NO_ELIGIBLE_ROLL = 428
MESSAGE_READIES_WEAPONSKILL = 43  # "<entity> readies <skill>." on the WS start
MESSAGE_SKILL_RECOVERS_HP = 103  # "<user> uses <skill>. <target> recovers N HP."
MESSAGE_DAMAGE = 185        # "<user> uses <skill>. <target> takes N points of damage."
MESSAGE_SKILL_DRAIN_HP = 187  # "<user> uses <skill>. <amount> HP drained from <target>."
MESSAGE_SKILL_MISSES = 188    # "<user> uses <skill>, but misses <target>."
MESSAGE_SKILL_RECOVERS_MP = 224  # "<user> uses <skill>. <target> recovers N MP."
MESSAGE_SKILL_DRAIN_MP = 225  # "<user> uses <skill>. <amount> MP drained from <target>."
MESSAGE_ADD_EFFECT_ADDITIONAL_DAMAGE = 229  # "Additional effect: <target> takes N more damage."
MESSAGE_TARGET_TAKES_DAMAGE = 264  # "<target> takes N points of damage." -- DoT ticks
MESSAGE_STATUS_IS = 203
MESSAGE_STATUS_WEARS_OFF = 206
MESSAGE_MAGIC_GAIN_EFFECT = 230
MESSAGE_MAGIC_ENFEEB = 237
MESSAGE_MAGIC_DRAIN_HP = 227
MESSAGE_MAGIC_DRAIN_MP = 228
MESSAGE_MAGIC_STARTS_CASTING = 327      # player: "<caster> starts casting <spell> on <target>."
MESSAGE_MAGIC_STARTS_CASTING_SELF = 3   # mobs and Trusts: "<caster> starts casting <spell>."
MESSAGE_EXEMPLAR_POINTS_GAINED = 809  # "<player> gains # exemplar points."
MESSAGE_MASTER_CHAIN = 810            # "Master chain #! <player> gains # exemplar points."
MESSAGE_MASTER_LEVEL_UP = 811         # "<player> attains master level #!"

# The four-character code in cmd_arg for a Magic Start, by spell skill.  The client uses
# it to pick the casting animation and the interrupt code; a spell id there makes the
# cast look like the wrong school (or not play at all).
MAGIC_CAST_WHITE = 0x68776163   # "cawh"
MAGIC_CAST_BLACK = 0x6B626163   # "cabk"
MAGIC_CAST_NINJUTSU = 0x6A6E6163  # "canj"
MAGIC_CAST_SONG = 0x6F736163    # "caso"
MAGIC_CAST_SUMMON = 0x6D736163  # "casm"
MAGIC_CAST_BLUE = 0x6C626163    # "cabl"
# The action id on a weapon skill's start packet (LandSandBoat's FourCC::SkillUse).
ACTION_SKILL_USE = 0x65746163    # "cate"
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


def magic_interrupt_arg(skill: int) -> int:
    """The 4CC a Magic Interrupt carries for a spell of this skill.

    The interrupt keeps the Magic Start's category (8) but swaps "ca" for "sp", so the
    client stops the cast bar instead of starting one: "spwh", "spbk", "spnj", ...  The
    packet's own message is blank; the client prints the interruption line from the 0x029
    basic message 16 that follows it.
    """
    return (magic_cast_arg(skill) & 0xFFFF0000) | 0x7073

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
    is_pet = getattr(entity, "kind", "") == "pet"
    body[33] = (0x08 if (getattr(entity, "kind", "") == "mob" or is_trust or is_pet)
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
    if is_trust or is_pet:
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
        if is_trust or is_pet:
            # Spawnables (targid 0x700-0x8FF) have no literal-name marker: the client
            # reads the name at packet 0x34, which is body 0x30.  The four zero bytes
            # fanxi used to put there made the client read an empty name, so an alter
            # ego had no nameplate and its action lines had no caster.
            body[48:64] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
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
        if is_trust or is_pet:
            # A Trust/pet is a spawnable (targid >= 0x700), so its name lives at packet
            # 0x34 (body 0x30); the four bytes at packet 0x34 are the name's first four
            # characters, not a model/padding block.  LandSandBoat writes this name with
            # the same memcpy at buffer offset 0x34, which includes the 4-byte sub-header.
            body[48:64] = entity.name.encode("ascii", "replace")[:16].ljust(16, b"\0")
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


def battle_action(actor_id: int, target_id: int = 0, damage: int = 0, *, miss: bool = False,
                  critical: bool = False, defeated: bool = False, animation: int = 0,
                  message: int | None = None, kind: int = 1,
                  category: int = ACTION_CATEGORY_BASIC_ATTACK,
                  action_id: int = BASIC_ATTACK_ID, hit_distortion: int = 0,
                  info: int | None = None, results: list[dict] | None = None,
                  targets: list[dict] | None = None) -> bytes:
    """Body of a 0x028 action packet (one or more targets, one or more results).

    ``results`` is the target's result list; a melee round passes one entry per hand,
    main hand first.  The client plays the swings in that order from this count
    (Windower's ``action_count``), which is what makes a dual-wield round look right.
    Without ``results`` the single-result keywords describe the one hit.

    ``targets`` carries a whole AoE action instead: one dict per target with
    ``target_id`` and either its own ``results`` list or the same single-result
    keywords.  The client reads the target count first and then each target's result
    count, so a mob TP move that hits three players is one packet and one animation.

    Per result, ``animation`` is the result's sub_kind: the swing hand (0 main, 1 off),
    a weapon skill's animation, or -- for a finished spell -- the spell id the client
    animates from.  ``damage`` is the result's 17-bit value: damage, HP healed, or the
    status effect id a spell lands.  ``info`` is the 5-bit result info; attacks use the
    defeated/critical flags, while a finished spell carries its recast there.
    """
    if targets is None:
        results = results or []
        if not results:
            results = [dict(damage=damage, miss=miss, critical=critical, defeated=defeated,
                            animation=animation, message=message, info=info,
                            hit_distortion=hit_distortion, kind=kind)]
        targets = [{"target_id": target_id, "results": results}]
    else:
        normalized = []
        for target in targets:
            target_results = target.get("results")
            if not target_results:
                target_results = [dict(
                    damage=target.get("damage", 0), miss=target.get("miss", False),
                    critical=target.get("critical", False),
                    defeated=target.get("defeated", False),
                    animation=target.get("animation", animation),
                    message=target.get("message", message), info=target.get("info", info),
                    hit_distortion=target.get("hit_distortion", hit_distortion),
                    kind=target.get("kind", kind))]
            normalized.append({
                "target_id": target.get("target_id", target.get("id", 0)),
                "results": target_results,
            })
        targets = normalized
    writer = BitWriter()
    writer.write(actor_id, 32)
    writer.write(min(len(targets), 15), 6)   # target count (the client caps at 15)
    writer.write(0, 4)                 # res_sum is always 0
    writer.write(category, 4)
    writer.write(action_id, 32)
    writer.write(0, 32)                # recast
    for target in targets[:15]:
        target_results = target.get("results") or []
        writer.write(int(target.get("target_id", 0)) & 0xFFFFFFFF, 32)
        # results for this target (a round has one per hand; the client caps at 8)
        writer.write(min(len(target_results), 8), 4)
        for entry in target_results[:8]:
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
            writer.write(max(0, int(entry.get("knockback", 0)) or 0) & 0x7, 3)
            writer.write(max(0, int(entry.get("damage", damage))) & 0x1FFFF, 17)
            writer.write(hit_message, 10)
            writer.write(0, 31)            # modifier
            # Optional additional-effect block.  An en-spell uses it on every melee result:
            # proc_kind is the element (ActionProcAddEffect FireDamage=1 .. DarkDamage=8),
            # value is the extra damage, and the message is
            # MESSAGE_ADD_EFFECT_ADDITIONAL_DAMAGE.  A skillchain uses the same block on the
            # closing weapon-skill result: proc_kind is ActionProcSkillChain, value is the
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
                   attr: int = 0, name: str = "") -> bytes:
    """Body of a 0x009 message: draw a line from the client's own system-message DAT.

    Style lock replies use this (Message IDs 267..270), so the player sees the same
    "Style lock mode enabled." line retail shows without Fanxi shipping the text.
    ``name`` fills the client's ``string2`` argument, which message 89 ("<name> examines
    you.") reads; the client's other messages leave Data empty.
    """
    body = struct.pack("<IHHB", int(unique_no) & 0xFFFFFFFF, int(act_index) & 0xFFFF,
                       int(message_id) & 0xFFFF, int(attr) & 0xFF)
    if name:
        body += ("string2 " + str(name)).encode("ascii", "replace")[:120] + b"\0"
    return body


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


def item_max(disabled=()) -> bytes:
    """Body of a 0x01C container-size packet: 18 containers plus their usable sizes.

    ``disabled`` names containers the client must not offer as storage.  ItemNum stays
    at the physical size; ItemNum2 (the usable size) goes to zero, which is the client's
    "this bag is not available" value.  An empty bag advertised as usable is what let the
    equipment window remember it and draw a blank item list.
    """
    body = bytearray(96)
    unavailable = {int(container) for container in disabled}
    for index in range(18):
        body[index] = 81
        struct.pack_into("<H", body, 32 + 2 * index,
                         0 if index in unavailable else 81)
    return bytes(body)


# --- party and alliance group packets ------------------------------------------------------
# The client's group pages read three packets: 0x0C8 (who is in which party), 0x0DD
# (one member's row) and 0x0DF (a member's vitals, also used for the local player in
# zone.party_member).  0x0DC is the invite prompt, 0x0E1 the server-side group id.
GROUP_TBL_SLOTS = 20


def _packed_name(name, size: int = 16) -> bytes:
    """A fixed-width, NUL-padded ASCII name, the shape the client's name fields use."""
    text = str(name or "").encode("ascii", "replace")[:size - 1]
    return text + bytes(size - len(text))


def group_invite(inviter_id: int, inviter_targid: int, name: str,
                 kind: int = 0, race: int = 0) -> bytes:
    """Body of S2C 0x0DC: ``<name>`` has invited the client to a party or alliance."""
    body = bytearray(0x1C)
    struct.pack_into("<IHBB", body, 0, int(inviter_id) & 0xFFFFFFFF,
                     int(inviter_targid) & 0xFFFF, 0, int(kind) & 0xFF)
    body[0x08:0x18] = _packed_name(name)
    struct.pack_into("<H", body, 0x18, int(race) & 0xFFFF)
    return bytes(body)


def group_table(entries, kind: int = 0) -> bytes:
    """Body of S2C 0x0C8: up to twenty ``(char_id, targid, flags, zone)`` rows.

    Kind 0 is a party and 5 an alliance.  A member's flags carry the party number,
    leader and alliance-leader bits; the client draws the whole roster from this plus
    one 0x0DD per row.
    """
    body = bytearray(4 + GROUP_TBL_SLOTS * 12)
    body[0] = int(kind) & 0xFF
    for index, entry in enumerate(list(entries)[:GROUP_TBL_SLOTS]):
        char_id, targid, flags, zone = entry
        offset = 4 + index * 12
        struct.pack_into("<IHBBHH", body, offset, int(char_id) & 0xFFFFFFFF,
                         int(targid) & 0xFFFF, int(flags) & 0xFF, 0,
                         int(zone) & 0xFFFF, 0)
    return bytes(body)


def group_list(member, number: int, flags: int, receiver_zone: int,
               targid: int | None = None) -> bytes:
    """Body of S2C 0x0DD: one party row, with vitals only while it is in our zone.

    ``member`` is a ``party.PartyMember``.  A member in another zone is sent its zone
    number alone; the client prints the zone instead of HP/MP/TP.
    """
    body = bytearray(0x38)
    struct.pack_into("<I", body, 0x00, int(member.char_id) & 0xFFFFFFFF)
    same_zone = int(member.zone) == int(receiver_zone)
    if same_zone:
        struct.pack_into("<III", body, 0x04, int(member.hp) & 0xFFFFFFFF,
                         int(member.mp) & 0xFFFFFFFF, int(member.tp) & 0xFFFFFFFF)
    # GP_GROUP_ATTR: party number (2 bits), leader/alliance-leader and recruiter bits,
    # then level-sync at bit 8.
    attributes = (int(flags) & 0x1FF)
    struct.pack_into("<I", body, 0x10, attributes)
    if same_zone:
        struct.pack_into("<H", body, 0x14,
                         int(member.targid if targid is None else targid) & 0xFFFF)
        body[0x16] = int(number) & 0xFF
        body[0x18] = 0                       # Kind
        body[0x19] = int(member.hpp) & 0xFF
        body[0x1A] = int(member.mpp) & 0xFF
        body[0x1E] = int(member.main_job) & 0xFF
        body[0x1F] = int(member.main_level) & 0xFF
        body[0x20] = int(member.sub_job) & 0xFF
        body[0x21] = int(member.sub_level) & 0xFF
    else:
        body[0x16] = int(number) & 0xFF
        struct.pack_into("<H", body, 0x1C, int(member.zone) & 0xFFFF)
    body[0x17] = 1 if int(flags) & 0x0200 else 0  # MoghouseFlg
    body[0x24:0x34] = _packed_name(member.name)
    return bytes(body)


def group_attr(member, targid: int | None = None) -> bytes:
    """Body of S2C 0x0DF: a party member's HP/MP/TP and job levels.

    This is the same packet the local player already receives from
    ``ZoneSession.party_member``; sending it for other members is what moves their bars.
    """
    body = bytearray(0x24)
    struct.pack_into("<IIIIH", body, 0x00, int(member.char_id) & 0xFFFFFFFF,
                     int(member.hp) & 0xFFFFFFFF, int(member.mp) & 0xFFFFFFFF,
                     int(member.tp) & 0xFFFFFFFF,
                     int(member.targid if targid is None else targid) & 0xFFFF)
    body[0x12] = int(member.hpp) & 0xFF
    body[0x13] = int(member.mpp) & 0xFF
    body[0x14] = 0                              # Kind
    body[0x15] = 0                              # MoghouseFlg
    struct.pack_into("<H", body, 0x16, int(member.zone) & 0xFFFF)
    body[0x1C] = int(member.main_job) & 0xFF
    body[0x1D] = int(member.main_level) & 0xFF
    body[0x1E] = int(member.sub_job) & 0xFF
    body[0x1F] = int(member.sub_level) & 0xFF
    return bytes(body)


def group_checkid(group_id: int) -> bytes:
    """Body of S2C 0x0E1: the party id the client asks for with C2S 0x078."""
    return struct.pack("<I", int(group_id) & 0xFFFFFFFF)


def group_solicit_no(reason: int = 0) -> bytes:
    """Body of S2C 0x0DE: clears the client's pending-invite state."""
    return struct.pack("<B3x", int(reason) & 0xFF)
