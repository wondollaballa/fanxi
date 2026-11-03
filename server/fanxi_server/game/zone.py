"""The zone protocol: login, entities, movement, chat, inventory, shops and basic combat.

The server is intentionally small but speaks the real client protocol: 0x00A/0x00C zone-in,
0x00E NPC/mob spawns on the client's first 0x015, 0x028 battle actions, 0x020/0x01D inventory,
0x03C/0x03E/0x03F shops, and the status/job packets the client waits on.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import shlex
import socket
import struct
import time
from dataclasses import replace

from . import base_stats, capes, geomancy, chain, check, combat, dancer, design as character_design, effects, item_usable, job_points, jugpets, live_state, merits, mounts, pets, prime_weapons, rolls, modifiers as mod, packets, skillchain, skills, stat_report, stats, traits, trust_ai, weapon_skill_effects, weapon_skill_jobs, weapon_skills
from .cipher import md5
from .entities import ZoneEntity
from .party import PARTY_KIND_PARTY
from ..service import (ApiError, CONTAINER_RECYCLE, EXEMPLAR_PER_LEVEL, MASTER_LEVEL_MAX,
                       WARDROBE_CONTAINERS, WARP_PAGE_SIZE, WARP_SLOT_MAX)
from .world import (
    DISENGAGE_DISTANCE,
    ENGAGE_DELAY,
    ENGAGE_RANGE,
    MELEE_RANGE,
    PLAYER_DESPAWN_RANGE,
    PLAYER_SPAWN_RANGE,
    TRUST_MAX,
    heading_to_rot,
)

log = logging.getLogger("fanxi.zone")
DEBUG = bool(os.environ.get("FANXI_ZONE_DEBUG"))

HDR = 28
TARGID = 0x400
VANA_EPOCH = 1009810800
# How many times a zone-in is rebuilt for a client that keeps retrying its login before
# the session is dropped and the next 0x00A starts a fresh one.
ZONE_IN_REBUILDS = 4
# Every 0x00B moves the client's zone cipher on by 2.  A client that missed one (UDP) or
# never processed one is then behind the server, and a client whose hand-off failed is
# still on whichever key it last advanced to.  Keep the sequence the hand-off has used so
# the zone-in can go out under all of them and client packets can be tried against all of
# them; one of these is always the key the client actually holds.
KEY_HISTORY = 8
# A repeated //warp call to the same anchor inside this window is the launcher's
# auto-pull racing a box that is already back; it is answered without a hand-off.
WARP_REPEAT_GUARD = 120.0
VANA_HOUR, VANA_DAY = 144, 3456
# A zone session has no keepalive of its own: the client sends 0x015 and expects the
# server to answer.  A character standing still in a quiet zone (a city, an empty field)
# makes the server send nothing for minutes, and the client's own receive timer then
# declares the link dead and shows FFXI-4001.  This is how often an otherwise silent
# session gets a General-only 0x00D, the same packet the sleeping heartbeat uses.
IDLE_HEARTBEAT = 5.0
# The client builds the mount model when a ride starts and will not rebuild it while one
# is out, so switching mounts has to pass through standing on foot first — and the client
# needs about a second on foot to tear the old model down.  A pending switch is applied by
# the tick once that second has passed.
MOUNT_SWITCH_DELAY = 1.2
# The state a buff, a bite of food or an ability cooldown leaves behind has to outlive the
# session (see game/live_state.py): the tick compares the snapshot with the last one it
# wrote every few seconds instead of on every change, because a song list is five echoes in
# a row, and the eviction path forces one last save.  A chat line in the zone-in burst can
# take the client out of movement, so the "welcome back" notice waits until the burst and
# the client's own load are done.
LIVE_STATE_SAVE_INTERVAL = 5.0
LIVE_STATE_NOTICE_DELAY = 2.0
#: Joachim's Trust spell id.  His explicit song set is per character (char_settings), the
#: same way the Trust itself belongs to the character rather than to the party or account.
JOACHIM_TRUST = 911
#: The support Trusts whose actions the HUD can set.  Names are for the chat command; the
#: numeric id is the stable key the HUD sends.
SUPPORT_TRUST_ALIASES = {
    "joachim": 911,
    "luzaf": 928,
    "qultada": 967,
    "koru-moru": 952, "korumoru": 952, "koru": 952,
    "sylvie": 981, "sylvie-uc": 981, "sylvieuc": 981,
    "ygnas": 998,
}
SUPPORT_TRUST_NAMES = {
    911: "Joachim", 928: "Luzaf", 952: "Koru-moru",
    967: "Qultada", 981: "Sylvie Uc", 998: "Ygnas",
}
TRUST_ACTION_LABEL = {"song": "songs", "spell": "spells", "roll": "rolls"}
TRUST_ACTION_ORDER = {
    "cure": 0, "buff": 1, "debuff": 2, "aura": 3, "nuke": 4, "song": 5, "roll": 6,
}
# 0x063 type 9: one u16 icon per bar slot, then one u32 timer.  0xFF is an empty slot and
# 0x7FFFFFFF is an effect that never wears off, so the client draws its icon without a
# countdown.
STATUS_ICON_NONE = 0x00FF
STATUS_ICON_NO_TIMER = 0x7FFFFFFF

# The client was built for a dial-up-era pipe: its network meter tops out around R3000,
# and above that its own receive loop falls behind (clicks feel like they take seconds or
# minutes to reach the character).  The zone's ambient entity stream is the largest thing
# a session sends, so it gets a byte budget of its own.  These sizes are the
# *uncompressed* sub-message bytes; the client sees roughly half of that after Huffman.
# 900 B/s (a dozen mob moves a second) starves a zone where twenty monsters are moving:
# the client gets one stale position every few hundred milliseconds and visibly snaps the
# model across the gap.  Raise it to the client's own ceiling (a little under R3000)
# rather than past it: the priority sort in pack() spends the first tokens on the
# closest entities, and turns/stops near the player are marked urgent and bypass the
# bucket.  Actions, chat, status packets and equipment sync are never charged here.
AMBIENT_BYTES_PER_SECOND = 2400
AMBIENT_BURST_BYTES = 1000
# The SkillStart and SkillFinish of one weapon skill must not share a datagram.  The
# client queues the start's SetAction for its scheduler; a finish in the same packet can
# still read the sub-kind against the spell table, which is why Flat Blade (6) played
# Cure VI and Requiescat (237) played Choke.  Holding the finish for one flush gives the
# client a frame to enter the weapon-skill context first.  The finish also waits for one
# packet to be sent since it was queued, so a slow flush cannot put both in one datagram.
WEAPONSKILL_FINISH_DELAY = 0.15
# One zone packet carries at most this many bytes of sub-messages.  About twelve position
# records fit here, which keeps packet overhead down without exceeding a normal MTU.
PACKET_BYTES = 900
# A client packet that does not acknowledge the last reply is re-sent at most this often,
# so a lost packet still recovers without the resend path blocking every new request.
RESEND_INTERVAL = 0.25
# A gear set arrives as one 0x050 per slot, usually split over several datagrams.  Wait
# this long after the last slot before sending the follow-up, so one burst owes one
# update instead of one per datagram.
EQUIP_SYNC_DELAY = 0.15
# A client that keeps swapping (the phase engine flapping idle/movement) must not hold
# the follow-up back forever: after this long the latest state goes out anyway.
EQUIP_SYNC_MAX_DELAY = 0.6
# The packets derived from the outfit.  Each is remembered by payload when it leaves, and
# equipment_sync() queues only the ones whose payload changed: armour swaps keep the
# job-derived blocks, and only a weapon that changes the skill type (or a granted skill)
# rewrites the command data.
EQUIP_SYNC_TYPES = (0x051, 0x0AA, 0x0AB, 0x0AC, 0x1A5, 0x061, 0x037)
# 0x0AC makes host64 rewrite its whole ability list, and every client freeze in the
# 2026-10-27/29 logs ends on that rebuild.  A phase-engine burst can change a weapon's
# skill type several times a second; send at most one command-data rewrite this often
# and let the tick send the final list once the burst settles.
EQUIP_COMMANDS_MIN_GAP = 1.5

# Every job-point category is sent at rank 20 (job_points_detail), so the Light Arts
# Effect rank that adds +3 s per rank to Regen duration is also 20.
JOB_POINT_RANK = 20

# Two-hour abilities carry recast id 0 in the ability table.  Their cooldown is kept
# per ability (so switching jobs does not block another job's one-hour) under keys
# above the byte-sized ordinary recast ids; 0x119 slot 0 carries the current job's
# two-hour timer.
TWO_HOUR_RECAST_BASE = 0x100000


def spell_animation(spell: dict) -> int:
    """The client animation id a finished spell plays (spell_list.animation).

    It is usually the spell id, but not always: Breakga is spell 365 and animation 271,
    and Monomi Ichi is spell 318 and animation 356.  A stored 0 means the spell has no
    client animation (Baramnesia), so it is kept rather than replaced by the spell id.
    Sending the spell id in the result's sub-kind makes the client play the wrong effect.
    """
    return int(spell["id"] if spell.get("animation") is None else spell["animation"])


# A pure enfeeble adds a small fixed hate chunk; damage uses World.add_damage_hate,
# which applies retail's level-scaled 80 CE / 240 VE split.
HATE_ENFEEBLE = 100

# Accession spreads the next white enhancing spell to the party around its caster.  The
# area is ten yalms, which is the radius the client draws for a party-enhancing spell.
ACCESSION_RANGE = 10.0
# Killer Instinct's helm augment (+4 s per merit rank).  This server deliberately gives
# the whole party the caster's full duration and effect instead of retail's 7.9-yalm,
# 4:00 party copy.
KILLER_INSTINCT_HEAD_ITEMS = frozenset({
    26640,  # Ankusa Helm
    26641,  # Ankusa Helm +1
    23071,  # Ankusa Helm +2
    23406,  # Ankusa Helm +3
    23926,  # Ankusa Helm +4
    10658,  # Mst. Helm +2 (augmented)
})

# C2S 0x053 lockstyle modes, in the client's order (XiPackets / LandSandBoat).
LOCKSTYLE_DISABLE = 0
LOCKSTYLE_KEEPALIVE = 1
LOCKSTYLE_QUERY = 2
LOCKSTYLE_SET = 3
LOCKSTYLE_ENABLE = 4

# Every appearance model /lockstyle can lock.  Kind is the client's equip slot.
STYLE_SLOTS = {
    0: "style_main", 1: "style_sub", 2: "style_ranged", 4: "style_head",
    5: "style_body", 6: "style_hands", 7: "style_legs", 8: "style_feet",
}

# Main and sub are never drawn from the locked models: the equipped weapon always
# shows, so swapping between a two-hander and a one-hander + shield (or between two
# weapons) updates the graphic while the armour stays locked.
WEAPON_STYLE_SLOTS = (0, 1)

# 0x009 system-message ids from the client's ROM/27/76.DAT table.
MSG_STYLE_LOCK_ON = 267
MSG_STYLE_LOCK_OFF = 268
MSG_STYLE_LOCK_IS_ON = 269
MSG_STYLE_LOCK_IS_OFF = 270
MSG_EXAMINE = 89             # "<player> examines you." (sent to the player being checked)

# C2S 0x05D emote ids.  The values with no client text are still valid motions, but this
# is the complete set the command parser sends; an id outside it is dropped.
EMOTE_SALUTE = 2
EMOTE_HURRAY = 43
EMOTE_BELL = 73
EMOTE_JOB = 74
EMOTE_AIM = 96
EMOTE_IDS = frozenset([*range(0, 39), 40, 41, 42, 43, 44, *range(65, 69), 73, 74, 96])

# 0x01D's Flags field is the client's whole "this bag is ready to draw" bitmask, not the
# set of bags named by the update.  The client replaces its mask with the packet's, so a
# sync that carries only the two bags an item moved between makes every other bag draw
# as empty (wardrobes stay blank until something is moved into them).  Zone-in streams
# all 18 containers, and every later sync carries that same full mask.
CLIENT_CONTAINERS = 18
ALL_CONTAINERS = (1 << CLIENT_CONTAINERS) - 1

# 0x0AC COMMAND_DATA, the client's "known commands" bitmap: 64 bytes of weapon-skill
# bits, then 64 of job abilities, 64 of pet commands and 32 of traits.  Bit n in a
# block is command n, lowest bit of the byte first (LandSandBoat's addBit/hasBit order).
COMMAND_BYTES = 224
WEAPON_SKILL_BYTES = 64
JOB_ABILITY_BITS = 512
TRAIT_BITS = 256
TRAIT_BASE = WEAPON_SKILL_BYTES * 3  # after weapon skills, job abilities, pet commands


def command_bits(weapon_skill_ids=(), job_ability_ids=(), trait_ids=()) -> bytes:
    """The 0x0AC payload: bit n set for every command/trait id supplied.

    The blocks are consecutive: 64 bytes of weapon skills, 64 of job abilities, 64 of
    pet commands and 32 of job traits.  Trait ids are the client's own trait numbers,
    the same ones in ``traits_data``.  With no job ability list the second block stays
    zero, which is what made the Job Abilities menu empty; the fourth block was always
    zero for the same reason, so a character's job traits never appeared.
    """
    bits = bytearray(COMMAND_BYTES)
    for ws_id in weapon_skill_ids:
        ws_id = int(ws_id)
        if 0 < ws_id < WEAPON_SKILL_BYTES * 8:
            bits[ws_id >> 3] |= 1 << (ws_id & 7)
    ja_base = WEAPON_SKILL_BYTES
    for ja_id in job_ability_ids:
        ja_id = int(ja_id)
        if 0 < ja_id < JOB_ABILITY_BITS:
            bits[ja_base + (ja_id >> 3)] |= 1 << (ja_id & 7)
    for trait_id in trait_ids:
        trait_id = int(trait_id)
        if 0 < trait_id < TRAIT_BITS:
            bits[TRAIT_BASE + (trait_id >> 3)] |= 1 << (trait_id & 7)
    return bytes(bits)


# The client's equipment slot numbers (SLOTTYPE).
# Every valid spell id (1..1019) in the client's 128-byte magic-data bitmap.
SPELL_BITS = bytes.fromhex(
    "feffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7"
    "ffffffffffffffffffffffffffffffffffffaa96feffbb2cbbf66fbbff78fdf7b477fffdffffeffff7ffff0700"
    "00ff070000ffffffffffffffffffffffff81fffffffffffffffffffffffffffffffffcff0f")

# All permanent key items from key_item.yaml, as seven 64-byte GetItemFlag bitmaps.
KEY_ITEM_BITS = (
    bytes.fromhex("fefffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffffffffffffffffffffffffff"),
    bytes.fromhex("ffffffffffffff00ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffffffffffff1ff0ffffffffffffffffffffffffffff"),
    bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"),
    bytes.fromhex("fffffffffffffffffffffffffbffffffffffffffffffffffffffffffffdfffffffffffffffffffffffffffffffffff7fffffffffffff1fffffffffffffffffff"),
    bytes.fromhex("ffffffffffffffffffffffffffffff081846f3ffff3f3ef5ffffe7ffff7f7fff3b0000c0fffffffffffffffefffffbfd7ebfffffff3ffcfeffffffffffffffff"),
    bytes.fromhex("ffffffffffdfffffff03fffffffffffffffffffffffffffffffffffffffffffffffffffdf7000000ffffffffffffffffffffffffffffffffffffffffffbfff7f"),
    bytes.fromhex("ffffffff7f000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f3f00000000000000000000000000000000000000000000000000"),
)

SKILL_CAP = 424  # the level 99 A+ skill cap

# The city each Mog House belongs to, by the zone id of any area in that city.  The
# client draws the exit menu from the login packet's MyroomMapNumber, and sends the same
# city back in the 0x05E exit request, so both sides need the same mapping.
MOGHOUSE_CITY_BY_ZONE = {
    230: 1, 231: 1, 232: 1,             # San d'Oria
    234: 2, 235: 2, 236: 2,             # Bastok
    238: 3, 239: 3, 240: 3, 241: 3,     # Windurst
    243: 4, 244: 4, 245: 4, 246: 4,     # Jeuno
}
MOGHOUSE_CITY_BY_NATION = {0: 1, 1: 2, 2: 3}
# MyroomMapNumber: the 0x01xx models are another nation's Mog House, the 0x012x ones the
# character's own (the client draws a different interior for each), and Jeuno is 0x0100.
MOGHOUSE_MODELS = {1: 0x0101, 2: 0x0102, 3: 0x0120, 4: 0x0100}
MOGHOUSE_HOME_MODELS = {1: 0x0121, 2: 0x0122, 3: 0x0123, 4: 0x0100}
# The exit menu's "Select an area to exit to" options, in the client's MyRoomExitMode
# order (1-based).  These are exactly the city areas LandSandBoat maps.
MOGHOUSE_EXITS = {
    1: (230, 231, 232),                 # Southern, Northern, Port San d'Oria
    2: (234, 235, 236),                 # Bastok Mines, Bastok Markets, Port Bastok
    3: (238, 239, 240, 241),            # Waters, Walls, Port, Woods
    4: (243, 244, 245, 246),            # Ru'Lude Gardens, Upper, Lower, Port Jeuno
}

# TP is stored in tenths, the unit the client's TP bar uses (3000 = 300 TP).
TP_MAX = 3000

# A job change is a rest in a city or town: HP and MP come back full.  Everywhere else
# (field, dungeon, instance) the change only recomputes the maxima, so the player keeps
# whatever HP/MP they brought with them and the next fight is their problem.  The list
# follows LandSandBoat's ``city`` zone type; Nashmau is a town even though its own zone
# file calls it outdoors, and a Mog House interior is handled by ``char["moghouse"]``.
SAFE_JOB_CHANGE_ZONES = frozenset({
    26, 32,                                    # Tavnazian Safehold, Sealion's Den
    48, 50, 53,                                # Al Zahbi, Whitegate, Nashmau
    80, 87, 94,                                # Southern San d'Oria [S], Bastok Markets [S],
                                               # Windurst Waters [S]
    230, 231, 232, 233,                        # San d'Oria
    234, 235, 236, 237,                        # Bastok
    238, 239, 240, 241,                        # Windurst
    243, 244, 245, 246,                        # Jeuno
    247, 248, 249, 250, 251, 252,              # Rabao, Selbina, Mhaura, Kazham,
                                               # Hall of the Gods, Norg
    256, 257,                                  # Western and Eastern Adoulin
})

# Zones that refuse a job change even out of combat.  Dynamis - Divergence is the live
# example; the original Dynamis zones are listed for when their DATs are added, so a
# later import cannot turn one into a free job-change spot.
JOB_CHANGE_BLOCKED_ZONES = frozenset({
    39, 40, 41, 42,                            # Dynamis - Valkurm, Buburimu, Qufim, Tavnazia
    134, 135,                                  # Dynamis - Beaucedine, Xarcabard
    185, 186, 187, 188,                        # Dynamis - San d'Oria, Bastok, Windurst, Jeuno
    294, 295, 296, 297,                        # Dynamis - San d'Oria/Bastok/Windurst/Jeuno [D]
})

# A job change drops the buff layer, but the conquest family belongs to the region and
# nation rather than the job: Signet, Sanction, Sigil and Ionis stay on.  Food and every
# other status effect (songs, rolls, job-ability buffs, debuffs) wears off with the job.
JOB_CHANGE_KEPT_EFFECTS = frozenset({
    effects.SIGNET, effects.SANCTION, effects.SIGIL, effects.IONIS,
})

EQUIP_SLOTS = {
    "main": 0, "sub": 1, "ranged": 2, "ammo": 3, "head": 4, "body": 5,
    "hands": 6, "legs": 7, "feet": 8, "neck": 9, "waist": 10,
    "ear1": 11, "ear2": 12, "ring1": 13, "ring2": 14, "back": 15,
}

# Main-hand weapon skills that fill both hands.  Hand-to-hand is deliberately absent:
# the game treats it as neither one- nor two-handed, so a shield may share it.
BOTH_HANDS_SKILLS = combat.TWO_HANDED_SKILLS

# Bags auto-equip may read for a job change.  The client can wear gear straight out of
# the inventory or a Mog Wardrobe; the Safe/Satchel/Sack/Case are storage, not equipment.
AUTO_EQUIP_BAGS = (0, 8, 10, 11, 12, 13, 14, 15, 16)

# The client's job ids, in the order its job list uses.
JOB_NAMES = {
    1: "Warrior", 2: "Monk", 3: "White Mage", 4: "Black Mage", 5: "Red Mage",
    6: "Thief", 7: "Paladin", 8: "Dark Knight", 9: "Beastmaster", 10: "Bard",
    11: "Ranger", 12: "Samurai", 13: "Ninja", 14: "Dragoon", 15: "Summoner",
    16: "Blue Mage", 17: "Corsair", 18: "Puppetmaster", 19: "Dancer",
    20: "Scholar", 21: "Geomancer", 22: "Rune Fencer",
}
JOB_ABBREVIATIONS = {
    1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD",
    8: "DRK", 9: "BST", 10: "BRD", 11: "RNG", 12: "SAM", 13: "NIN", 14: "DRG",
    15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH",
    21: "GEO", 22: "RUN",
}


def job_id(text: str) -> int | None:
    """A job number from its abbreviation, full name or numeric id (``nin`` -> 13)."""
    key = str(text or "").strip().casefold()
    if key.isdigit():
        number = int(key)
        return number if number in JOB_NAMES else None
    for number, name in JOB_NAMES.items():
        if key == name.casefold() or key == JOB_ABBREVIATIONS[number].casefold():
            return number
    return None


def job_pair_label(main_job: int, sub_job: int = 0) -> str:
    """``22, 13`` -> ``RUN/NIN``; a pair with no support job is just its main."""
    label = JOB_ABBREVIATIONS.get(int(main_job), str(main_job))
    if int(sub_job or 0):
        label += "/" + JOB_ABBREVIATIONS.get(int(sub_job), str(sub_job))
    return label


# Utsusemi is the ninjutsu the working-stock refill exists for: the client will not
# cast it without the matching tool in the inventory, so the server consumes one and
# immediately tops the stack back up from the hidden locker.
UTSUSEMI_TOOLS = {
    "Utsusemi Ichi": 2971,  # Inoshishinofuda
    "Utsusemi San": 2972,   # Shikanofuda
    "Utsusemi Ni": 2973,    # Chonofuda
}

# Each ninjutsu costs a tool and no MP.  The spell table's `mp` column was filled from
# the scroll item id for skill 39 (Monomi Ichi 2553, Katon Ichi 1161, ...), so without
# this exception every ninjutsu was refused unless the character had that much MP.
NINJUTSU_SKILL = 39

def dawn_mulsum_amount(pet_max_hp: int) -> int:
    """Dawn Mulsum restores approximately 25-50% of the pet's maximum HP."""
    pet_max_hp = max(0, int(pet_max_hp))
    if pet_max_hp <= 0:
        return 0
    low = max(1, pet_max_hp * 25 // 100)
    high = max(low, pet_max_hp * 50 // 100)
    return random.randint(low, high)


WORKING_STOCK_NAMES = {
    2971: "Inoshishinofuda", 2972: "Shikanofuda", 2973: "Chonofuda",
    17023: "Pet Food Theta", 5411: "Dawn Mulsum",
}

# //locker selectors.  Slots use the item catalogue's equip_slot names; ear/ring cover
# both copies, and capes/mantles are the back slot.
LOCKER_SLOTS = {
    "main": "main", "weapon": "main", "sub": "sub", "shield": "sub",
    "ranged": "ranged", "ammo": "ammo", "head": "head", "body": "body",
    "hands": "hands", "legs": "legs", "feet": "feet", "neck": "neck",
    "waist": "waist", "ear": "ear", "earring": "ear", "ring": "ring",
    "back": "back", "cape": "back", "capes": "back", "mantle": "back",
}


def locker_selector(text: str) -> tuple[dict, str]:
    """Turn the words after //locker store/grab into a selector and a chat label."""
    wanted = " ".join(str(text or "").split())
    key = wanted.casefold()
    if key in ("all", "everything", "*"):
        return {"kind": "all"}, "all"
    if key in ("materials", "material", "crafting", "craft"):
        return {"kind": "materials"}, "materials"
    if key in ("jsecapes", "jobcapes", "jse"):
        return {"kind": "capes"}, "JSE capes"
    if key in LOCKER_SLOTS:
        return {"kind": "slot", "slot": LOCKER_SLOTS[key]}, key
    return {"kind": "name", "text": wanted}, wanted


def vana_offset(hour: float) -> int:
    """Earth seconds to add to the clock so that it is this Vana'diel hour (0-23, fractions too)."""
    return int(hour * VANA_HOUR - (time.time() - VANA_EPOCH)) % VANA_DAY


class Msg(bytearray):
    zone_out = False  # 0x00B: build() moves the key on after sending it
    # Entity position updates are ambient: a newer one supersedes an older one, and
    # pack() sends them after every real event.  The rest of the fields describe the
    # entity so pack() can coalesce two updates of the same one.
    ambient = False
    ptype = 0
    targid = 0
    priority = 0.0
    queued_at = 0.0
    # A message that must not go out before this wall-clock time.  pack() leaves it in
    # the queue and the next flush after the deadline sends it; this is how a weapon
    # skill's start and finish land in separate datagrams.
    not_before = 0.0
    # The last server packet id at queue time.  A held message also waits until one
    # packet has gone out since then, which guarantees the start is not in the same
    # datagram even when the flush is late.
    after_packet = -1


def sub(ptype: int, body: bytes) -> Msg:
    """One message inside a zone packet.

    The 4-byte header packs a 9-bit type and a 7-bit size in 32-bit units into one uint16; the
    second uint16 is the sync/sequence, filled in by ``build``. The body starts at byte 4.
    """
    body = bytes(body)
    n = (4 + len(body) + 3) & ~3
    units = (n + 3) // 4
    if units > 0x7F:
        raise ValueError("zone sub-message is too large: %d bytes" % n)
    p = Msg(n)
    struct.pack_into("<H", p, 0, (ptype & 0x1FF) | ((units & 0x7F) << 9))
    p[4:4 + len(body)] = body
    return p


def cstr(s: str, n: int) -> bytes:
    b = s.encode("ascii", "replace")[:n - 1]
    return b + bytes(n - len(b))


def _name_list(names: list[str]) -> str:
    """Names as one English list: "A", "A and B", "A, B and C"."""
    names = [str(name) for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def gauge_percent(value: int, maximum: int) -> int:
    """A 0-100 fill for an HP/MP bar.  A zero maximum reads as full.

    Every packet that carries a percentage has to divide by the *current* maximum, not by
    the value being reported: the party line used to send 100/100, so its bars sat full at
    7240/10149 and the client never showed how far from the cap the character was.
    """
    maximum = int(maximum)
    if maximum <= 0:
        return 100
    return max(0, min(100, int(value) * 100 // maximum))


class ZoneSession:
    def __init__(self, world, addr, char: dict):
        self.world = world
        self.addr = addr
        self.char = char
        self.zone = int(char.get("zone", 246))
        self.pos = [0.0, 0.0, 0.0, 0]
        self.server_id = 0
        self.client_id = 0
        self.cipher = self.prev_cipher = None
        self.key = None
        # Every key this hand-off has used, oldest first.  The client moves its cipher on
        # with each 0x00B it processes; a lost or unprocessed one leaves it on an older
        # key, so the zone-in is sent under each of these and incoming packets are tried
        # against each (see decrypt()).
        self.key_history: list[bytes] = []
        # The game session this client signed in with.  A relog after a failed hand-off
        # keeps it; a restarted client gets a new one and starts over from the base key.
        self.session_hash = b""
        # Copies of the last zone-in sealed under the other keys in key_history.  The
        # gateway sends them right after the primary reply; the client drops the ones its
        # MD5 does not open.
        self.extra_packets: list[bytes] = []
        # A zone change that arrived while this one was still in flight; after_zone_in
        # applies it once the client is in the world.
        self.pending_zone = None
        # The last //warp call this box was handed: repeated launcher pulls to the same
        # anchor do not need a new 0x00B (see _warp_call).
        self.warped_to: tuple | None = None
        # Set by decrypt(): the last packet opened under the pre-zone-change cipher.
        self.opened_with_prev = False
        # The key that opened the last client packet when it was not the current one.
        self.opened_with_key = None
        # The key before a zone-change bump, and the plaintext of the last server packet.
        # A client that does not advance its key on 0x00B gets the same zone-in re-sent
        # under this key; whichever one it opens, the decrypt path follows.
        self.base_key = None
        self.last_plain = None
        self.zone_in_tries = 0
        self.queue: list[Msg] = []
        # Ambient position updates, one pending message per entity.  Replacing the
        # message in place instead of appending means a crowded zone cannot fill the
        # FIFO with thousands of stale mob moves ahead of the player's next action.
        self.pending_positions: dict[tuple[int, int], Msg] = {}
        # Token bucket for the ambient stream; actions/chat/status never wait on it.
        self.ambient_tokens = float(AMBIENT_BURST_BYTES)
        self.ambient_at = time.time()
        self.last_sent_at = 0.0
        self.last_resend_at = 0.0
        self.last = None
        self.logged_in = False
        self.zoning = False
        # True after a fresh login, false when this 0x00A continues a zone change.
        # Only a fresh login runs the family-party recovery, so a deliberate leave and
        # then a zone line does not silently re-add the main to the team.
        self.fresh_login = True
        # A sleeping character keeps its UDP session and process, but is hidden from other
        # clients and skipped by the world tick. Only a chat command is read until wake.
        self.sleeping = False
        self.sleeping_since = 0.0
        self.sleeping_heartbeat = 0.0
        # The party to rejoin on wake; sleep removes the character from the roster so the
        # other clients do not list a character that is no longer in the zone.
        self.sleep_party_id = 0
        # When this zone change was queued. The hand-off window starts here, not at the last
        # packet: an idle box can stand still for minutes and still be a fresh zone change.
        self.zone_change_at = 0.0
        # Player presence: the id other clients know this character by (0x400 is "self"),
        # the other players this client currently has spawned, and movement bookkeeping.
        self.targid = 0
        self.gone = False
        self.seen_players: dict[int, "ZoneSession"] = {}
        self.moving = False
        self.move_time = 0
        self.last_player_update = 0.0
        self.next_player_sync = 0.0
        self.in_event = False
        self.event_started_at = 0.0
        self.event_ack = False
        self.event_guard_id = 0
        self.current_event_id = 0
        self.seen: set[int] = set()
        self.last_save = 0.0
        # A slot changed in this burst.  The outfit save and the derived packets (looks,
        # stats, command data) wait until the burst settles: a set arrives as several
        # datagrams, and the client is served one packet per ack, so a copy per datagram
        # buried the later 0x050 echoes.  Each chunk still settles the outfit for the
        # server's own numbers, because an action can ride in the same datagram.
        self.equipment_changed = False
        self.equip_sync_at = 0.0
        self.equip_sync_deadline = 0.0
        self._commands_sent_at = 0.0
        self._commands_pending = False
        # The outfit whose save and vitals are current, so settle_equipment() is safe to
        # call once per datagram and again from the deferred flush.
        self._settled_outfit: dict[int, tuple[int, int, int]] = {}
        # ptype -> payload of the last copy of each derived packet the client has, so a
        # burst that changes nothing in one of them does not send it again.
        self._sync_sent: dict[int, bytes] = {}
        self.client_hdr = b""
        self.entities: list = []
        # The alter egos this player has called, in call order.  They live in the world's
        # zone list too (everyone can see them); this list is the owner's cap/duplicate
        # check and what a zone change or logout cleans up.
        self.trust_entities: list = []
        self.pet_entity = None
        # The Call Beast jug item behind the current jug pet, when one was called from ammo.
        # Bestial Loyalty keeps the jug equipped; the HUD matches the pet's name to the same
        # catalogue to choose which Ready moves to offer.
        self.pet_jug_item = 0
        # The mob Tame made docile: its next Charm gets the retail +10% charm chance.
        self.tamed_mob_id = 0
        # The Master chain window: the first level-99 kill arms it (60 s, shrinking to
        # the 30 s floor as the chain grows), and each kill inside adds +2% exemplar
        # points (capped at chain #50 / +100%).  See game/chain.py.
        self.exemplar_chain = chain.ChainState()
        # The mount this character is riding: -1 is on foot, otherwise a client mount id
        # (0 is the personal chocobo — see mounts.py).  A zone line or a logout puts the
        # character back on foot, the way retail does; the last mount called is kept in
        # characters.mount so the HUD can preselect it next time.
        self.mount_id = -1
        self.mount_called_at = 0.0
        # (mount id, when to call it): a switch waits out MOUNT_SWITCH_DELAY on foot.
        self.pending_mount: tuple[int, float] | None = None
        self.engaged_id: int | None = None
        self.casting: dict | None = None
        # recast id -> unix time it becomes usable again (0x119 sends the remainder).
        self.ability_recasts: dict[int, float] = {}
        # Samurai's Meditate ticks its TP over five beats instead of paying it at once.
        self.meditate: dict | None = None
        # Third Eye: the charges left and when the stance expires.
        self.third_eye: dict | None = None
        # Timed 0x0AC re-sends: the client builds the Abilities menu before the first
        # zone-in copy lands, and a copy that arrives later is what fills it.
        self.abilities_retries: list[float] = []
        self.next_attack_at = 0.0
        self.dead_until = 0.0
        self.zone_loaded = False
        self.entities_sent = False
        self.sent_targids: set[int] = set()
        self.next_entity_sync = 0.0
        self.casting = None
        self.trust_entities = []
        self.pet_entity = None
        # The live aura of each bubble, {"indi": (status, hexed mob id), "geo": (...)}.
        # A Geomancer runs one Indi- and one Geo- bubble, and a new cast replaces only
        # its own, so this remembers what each one put where.
        self.geo_bubble: dict[str, tuple[int, int]] = {}
        self.position_seen = False
        self.target_targid = 0
        self.engaged_targid = 0
        # Set on a new engagement.  The client sends one /attack off by itself when its
        # first swing finds the target outside its own four-yalm reach; that packet is the
        # client dropping its swing, not the player giving up the fight, so it is absorbed
        # exactly once (see attack_off).  It never re-arms.
        self.client_range_drop = False
        self.event_scan: list[int] = []
        self.scan_current = 0
        self.scan_deadline = 0.0
        self.scan_acks: list[int] = []
        self.sweep: list = []
        self.sweep_at = 0.0
        self.sweep_variant = 0
        self.event_scan_entity = None
        self.event_scan_at = 0.0
        self.shop_key = ""
        self.shop_items: list[dict] = []
        self.equipped: dict[int, tuple[int, int, int]] = {}  # equip slot -> (container, slot, item id)
        self.status_effects: list[int] = []  # buff ids the client draws from 0x037
        # effect key -> {until, power, potency, tick, icon, mods}; status_effects is the
        # client's icon order and this dict is the server-side timer and payload.  Songs
        # use effects.song_key(spell_id) as the key so two songs that share an icon can
        # be active at once; their state["icon"] keeps the canonical icon for 0x037.
        self.effect_state: dict[int, dict] = {}
        # The active food's modifiers, duration and item.  Food is a source for
        # combat_mods()/stat_sheet(), not just an icon.
        self.food: dict = {"item_id": 0, "name": "", "until": 0.0, "mods": {}}
        # The reconnect snapshot (char_live_state, migration 0145) built from the three
        # fields above and ability_recasts.  ``live_state_signature`` is the payload the
        # row last held, so the tick writes only after a real change; ``live_state_restored``
        # makes a retried zone-in restore once; ``live_state_closed`` is set by a deliberate
        # logout, whose recasts-only row no later save may overwrite.
        self.live_state_signature: str | None = None
        self.live_state_checked_at = 0.0
        self.live_state_restored = False
        self.live_state_closed = False
        # What a restored login tells the player, once the zone-in burst is over.
        self.live_state_notice: live_state.Restored | None = None
        self.live_state_notice_at = 0.0
        self.resting = False
        self.next_rest_tick = 0.0
        self.stats_refresh_at = 0.0
        self.door_close_at = 0.0
        self.door_entity = None
        self.opened_doors: set[int] = set()
        # Charged dispense pouches/quivers: item id -> item_dispense row.  Loaded once so
        # the zone-in inventory burst can include each pouch's charge/cooldown extdata
        # without a query per item.
        try:
            self.dispense_items = {
                int(row["item_id"]): row
                for row in self.world.service.dispense_items()
            }
        except Exception:
            self.dispense_items = {}
        # Automatic doors are opt-in ("//doors auto on") and never run in a dungeon.
        # Retail leaves a door shut until the player targets it or walks into it.
        self.auto_open_doors = (
            self._character_setting("auto_open_doors", "0") == "1")
        # The owner's explicit support-Trust sets (char_settings).  Joachim keeps his own
        # legacy key; the other support Trusts are one JSON map keyed by Trust spell id.
        # Loaded once so the Trust tick never queries the database.
        self.joachim_songs = self._load_joachim_songs()
        self.trust_actions = self._load_trust_actions()
        self.last_packet_at = time.time()
        self.idle_heartbeat_at = 0.0
        self.next_position_refresh = 0.0
        self.last_release_at = 0.0
        # When the next Auto Refresh/Auto Regen (or gear Refresh/Regen) tick lands.
        # Retail ticks these every three seconds, not once per server frame.
        self.next_regen_tick = time.time() + traits.TICK_SECONDS
        self._trait_cache: tuple[tuple[int, int, int, int], list[traits.Trait]] | None = None
        # (main job, main level) -> (every job-point spell id, this job's ids).  The
        # gift names are resolved through the spells table once per job pair.
        self._jp_spell_cache: tuple[tuple[int, int], frozenset[int], frozenset[int]] | None = None

    def save_position(self, force: bool = False) -> None:
        """Movement arrives many times a second; the database gets it every few seconds."""
        now = time.time()
        if force or now - self.last_save >= 5:
            self.last_save = now
            self.world.save_position(self.char, self.zone, self.pos)

    def _character_setting(self, key: str, default: str = "") -> str:
        """One persisted per-character preference, or ``default`` when unavailable."""
        try:
            value = self.world.service.character_setting(
                int(self.char.get("id") or 0), key, default)
        except Exception as exc:
            # An old database without char_settings must still let the session start.
            log.debug("%s setting %s unavailable: %s", self.addr, key, exc)
            return default
        return default if value is None else str(value)

    # --- configurable support trusts ------------------------------------------------------------
    # The support Trust follows the owner, so an explicit action set is a character setting,
    # not a party or account one.  Joachim keeps his legacy `joachim_songs` key; the other
    # support Trusts are one JSON map keyed by Trust spell id.  An absent/empty list means
    # the built-in default logic.  A query with a trailing ``hud`` prints the machine-readable
    # ``TrustData|`` lines the HUD swallows instead of showing them.

    def _load_joachim_songs(self) -> list[int]:
        """The character's saved Joachim set, or [] for the role plan."""
        raw = self._character_setting("joachim_songs", "")
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(value, list):
            return []
        out: list[int] = []
        for entry in value:
            try:
                spell_id = int(entry)
            except (TypeError, ValueError):
                continue
            if spell_id > 0 and spell_id not in out:
                out.append(spell_id)
            if len(out) >= trust_ai.TRUST_ACTION_LIMIT[911]:
                break
        return out

    def _load_trust_actions(self) -> dict[int, list[int]]:
        """The character's saved action sets for the other support Trusts."""
        raw = self._character_setting("trust_actions", "")
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(value, dict):
            return {}
        out: dict[int, list[int]] = {}
        for key, entries in value.items():
            try:
                trust_id = int(key)
            except (TypeError, ValueError):
                continue
            if (trust_id == 911 or trust_id not in trust_ai.SUPPORT_TRUST_IDS
                    or not isinstance(entries, list)):
                continue
            limit = trust_ai.TRUST_ACTION_LIMIT.get(trust_id, 12)
            selected: list[int] = []
            for entry in entries:
                try:
                    action_id = int(entry)
                except (TypeError, ValueError):
                    continue
                if action_id > 0 and action_id not in selected:
                    selected.append(action_id)
                if len(selected) >= limit:
                    break
            if selected:
                out[trust_id] = selected
        return out

    def _support_trust_id(self, token: str) -> int | None:
        """A support Trust's spell id from a numeric id or one of the chat aliases."""
        text = str(token or "").casefold()
        try:
            trust_id = int(text, 0)
        except ValueError:
            trust_id = SUPPORT_TRUST_ALIASES.get(text, 0)
        return trust_id if trust_id in trust_ai.SUPPORT_TRUST_IDS else None

    @staticmethod
    def _action_key(name: str) -> str:
        """A spell/roll name without case or punctuation, for commands and data rows."""
        return "".join(ch for ch in str(name or "").casefold() if ch.isalnum())

    def _trust_action_catalog(self, trust_id: int) -> list[dict]:
        """Every action this Trust can use right now, in display order.

        For the casters this is the kit's full action catalogue (not the default pruned
        rotation), so a lower tier or Koru-Moru's Flurry can still be chosen explicitly.
        For the Corsairs it is the Phantom Roll table.  A database error yields an empty
        picker rather than a crashed command.
        """
        trust_id = int(trust_id)
        kind = trust_ai.TRUST_ACTION_KIND.get(trust_id)
        if kind is None:
            return []
        if kind == "roll":
            rows = [
                {"id": int(ability), "name": str(spec.name),
                 "kind": "roll", "level": 0}
                for ability, spec in rolls.ROLLS.items()
            ]
            rows.sort(key=lambda row: (row["name"].casefold(), row["id"]))
            return rows
        level = max(1, int(self.char.get("main_level", 1) or 1))
        try:
            spells = self.world.service.trust_action_spells(trust_id, level)
            trust = self.world.service.trust(trust_id) or {}
        except Exception as exc:
            log.warning("%s could not read trust %d actions: %s", self.addr, trust_id, exc)
            return []
        levels = {int(spell["id"]): int(spell.get("min_level") or 0)
                  for spell in spells}
        kit = trust_ai.build_kit(
            spells, level, int(trust.get("job") or 0), str(trust.get("name") or ""))
        rows: list[dict] = []
        for spell in kit.get("actions_all", []):
            action_kind = kit.get("action_kind", {}).get(int(spell["id"]))
            if action_kind is None:
                continue
            if kind == "song" and action_kind != "song":
                continue
            if kind == "spell" and action_kind == "song":
                continue
            rows.append({
                "id": int(spell["id"]),
                "name": str(spell.get("name") or ""),
                "kind": action_kind,
                "level": levels.get(int(spell["id"]), 0),
            })
        rows.sort(key=lambda row: (
            TRUST_ACTION_ORDER.get(row["kind"], 9),
            -int(row["level"]),
            row["name"].casefold(),
            row["id"],
        ))
        return rows

    def _trust_selected_ids(self, trust_id: int) -> list[int]:
        trust_id = int(trust_id)
        if trust_id == 911:
            return list(self.joachim_songs)
        return list(self.trust_actions.get(trust_id, []))

    def _save_trust_selected(self, trust_id: int, action_ids: list[int]) -> bool:
        """Persist one set.  Empty means the built-in default logic."""
        trust_id = int(trust_id)
        if trust_id == 911:
            return self._save_joachim_songs(action_ids)
        limit = trust_ai.TRUST_ACTION_LIMIT.get(trust_id, 12)
        saved = list(dict.fromkeys(int(action_id) for action_id in action_ids))[:limit]
        if saved:
            self.trust_actions[trust_id] = saved
        else:
            self.trust_actions.pop(trust_id, None)
        payload = {str(key): list(value) for key, value in self.trust_actions.items() if value}
        try:
            self.world.service.set_character_setting(
                int(self.char["id"]), "trust_actions",
                json.dumps(payload) if payload else "")
        except Exception as exc:
            log.warning("%s could not save trust %d actions: %s", self.addr, trust_id, exc)
            self.say("The action set could not be saved.")
            return False
        return True

    def _save_joachim_songs(self, spell_ids: list[int]) -> bool:
        """Persist one Joachim song set (empty means the role plan)."""
        saved = list(dict.fromkeys(int(spell_id) for spell_id in spell_ids))
        saved = saved[:trust_ai.TRUST_ACTION_LIMIT[911]]
        try:
            self.world.service.set_character_setting(
                int(self.char["id"]), "joachim_songs",
                json.dumps(saved) if saved else "")
        except Exception as exc:
            log.warning("%s could not save Joachim's songs: %s", self.addr, exc)
            self.say("Joachim's song set could not be saved.")
            return False
        self.joachim_songs = saved
        return True

    def _parse_trust_actions(self, args: list[str],
                             options: list[dict]) -> tuple[list[int], str | None]:
        """Resolve quoted or plain action names to ids, in the order given.

        The command line has already lost its shell quoting by the time it reaches the
        zone (``words`` is whitespace-split), so the words are joined again and handed to
        ``shlex``.  A name without quotes is still accepted: the longest run of words
        that matches a known action wins.  Returns ``(ids, unknown_token)``.
        """
        text = " ".join(args)
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        by_key = {self._action_key(row["name"]): row for row in options}
        chosen: list[int] = []
        index = 0
        while index < len(tokens):
            match = None
            for count in range(min(6, len(tokens) - index), 0, -1):
                candidate = " ".join(tokens[index:index + count])
                row = by_key.get(self._action_key(candidate))
                if row is not None:
                    match = (row, count)
                    break
            if match is None:
                return [], tokens[index]
            row, count = match
            action_id = int(row["id"])
            if action_id not in chosen:
                chosen.append(action_id)
            index += count
        return chosen, None

    def _trust_action_names(self, trust_id: int,
                            action_ids: list[int] | None = None) -> list[str]:
        """The canonical names of a saved set that are still in the catalogue."""
        options = {int(row["id"]): str(row["name"])
                   for row in self._trust_action_catalog(trust_id)}
        ids = self._trust_selected_ids(trust_id) if action_ids is None else action_ids
        return [options[int(action_id)] for action_id in ids if int(action_id) in options]

    def _trust_send_ui(self, trust_id: int) -> None:
        """Send the HUD's hidden action catalogue and current selection, one line each."""
        trust_id = int(trust_id)
        rows = self._trust_action_catalog(trust_id)
        by_id = {int(row["id"]): row for row in rows}
        selected = [int(action_id) for action_id in self._trust_selected_ids(trust_id)
                    if int(action_id) in by_id]
        limit = trust_ai.TRUST_ACTION_LIMIT.get(trust_id, 12)
        kind = trust_ai.TRUST_ACTION_KIND.get(trust_id, "spell")
        name = SUPPORT_TRUST_NAMES.get(
            trust_id, str((self.world.service.trust(trust_id) or {}).get("name") or "Trust"))
        auto = 0 if selected else 1
        self.say("TrustData|%d|B|%s|%s|%d|%d|%s" % (
            trust_id, name, kind, limit, auto,
            ",".join(str(action_id) for action_id in selected)))
        for row in rows:
            self.say("TrustData|%d|A|%d|%d|%s|%s" % (
                trust_id, int(row["id"]), int(row["level"]),
                str(row["kind"]), str(row["name"])))
        self.say("TrustData|%d|E" % trust_id)

    def _trust_say_selection(self, trust_id: int, *, hud: bool = False) -> None:
        """Report the current set: hidden data lines for the HUD, prose for chat."""
        trust_id = int(trust_id)
        if hud:
            self._trust_send_ui(trust_id)
            return
        kind = trust_ai.TRUST_ACTION_KIND.get(trust_id, "spell")
        label = TRUST_ACTION_LABEL.get(kind, "actions")
        name = SUPPORT_TRUST_NAMES.get(trust_id, "The Trust")
        names = self._trust_action_names(trust_id)
        if names:
            self.say("%s %s: %s" % (name, label, ", ".join(names)))
        elif trust_id == 911:
            self.say("Joachim chooses his songs by role. "
                     'Use //trust joachim set songs "..." to pick them.')
        else:
            self.say("%s uses the default logic. Use //trust %d set %s "
                     '"..." to choose actions.' % (name, trust_id, label))

    def _trust_command(self, trust_id: int, args: list[str]) -> None:
        """Show or choose one support Trust's action set.

          //trust <id|name> [list]                  current set
          //trust <id|name> set songs|spells|rolls "..."  explicit set (ordered)
          //trust <id|name> set default                    built-in logic
          //trust <id|name> ui hud                         HUD catalogue/data line
        """
        trust_id = int(trust_id)
        args = list(args or [])
        hud = bool(args and args[-1].casefold() == "hud")
        if hud:
            args.pop()
        kind = trust_ai.TRUST_ACTION_KIND.get(trust_id, "spell")
        label = TRUST_ACTION_LABEL.get(kind, "actions")
        name = SUPPORT_TRUST_NAMES.get(trust_id, "The Trust")
        if not args or args[0].casefold() in (
                "list", "status", "show", "actions", "action",
                "song", "songs", "spell", "spells", "roll", "rolls"):
            self._trust_say_selection(trust_id, hud=hud)
            return
        action = args[0].casefold()
        if action in ("ui", "data"):
            if not hud:
                self.say("Use //trust %d ui hud from the HUD." % trust_id)
                return
            self._trust_send_ui(trust_id)
            return
        if action in ("auto", "default", "reset"):
            if self._save_trust_selected(trust_id, []):
                self._trust_say_selection(trust_id, hud=hud)
            return
        if action not in ("set", "choose"):
            self.say("Usage: //trust %d [set songs|spells|rolls \"<name>\" ... | "
                     "set default]" % trust_id)
            return
        rest = args[1:]
        if rest and rest[0].casefold() in (
                "song", "songs", "spell", "spells", "roll", "rolls",
                "action", "actions", "list"):
            rest = rest[1:]
        if not rest or (len(rest) == 1
                        and rest[0].casefold() in ("auto", "default", "reset")):
            if self._save_trust_selected(trust_id, []):
                self._trust_say_selection(trust_id, hud=hud)
            return
        options = self._trust_action_catalog(trust_id)
        if not options:
            self.say("%s has no actions available at your level." % name)
            return
        chosen, unknown = self._parse_trust_actions(rest, options)
        if unknown is not None:
            self.say('%s does not know the action "%s".' % (name, unknown))
            return
        if not chosen:
            self.say("No actions were named.")
            return
        limit = trust_ai.TRUST_ACTION_LIMIT.get(trust_id, 12)
        if len(chosen) > limit:
            if trust_id == 911:
                self.say("Joachim's horn holds four songs; pick four or fewer.")
            else:
                self.say("%s can keep at most %d %s." % (name, limit, label))
            return
        if self._save_trust_selected(trust_id, chosen):
            self._trust_say_selection(trust_id, hud=hud)

    def set_key(self, key: bytes, history: list[bytes] | None = None) -> None:
        self.key = bytearray(key)
        self.base_key = bytes(key)
        self.cipher = self.world.zone_cipher_for(self.key)
        self.prev_cipher = None
        self.key_history = [bytes(item) for item in (history or [])]
        current = bytes(self.key)
        if current not in self.key_history:
            self.key_history.append(current)
        del self.key_history[:-KEY_HISTORY]

    def bump_key(self) -> None:
        """After 0x00B the client moves its key on by 2 (the last word, as a number).

        Every build has done this; a client that does not advance keeps using the key it
        had. All of them are kept in ``key_history``: the replies go out under the new one,
        and ``decrypt`` follows whichever key the client actually used, so a client that
        missed a 0x00B (or processed one out of order) is not stranded on a key the server
        has forgotten.
        """
        self.base_key = bytes(self.key)
        self.prev_cipher = self.cipher
        value = (struct.unpack_from("<I", self.key, 16)[0] + 2) & 0xFFFFFFFF
        struct.pack_into("<I", self.key, 16, value)
        self.cipher = self.world.zone_cipher_for(self.key)
        current = bytes(self.key)
        if not self.key_history or self.key_history[-1] != current:
            self.key_history.append(current)
        del self.key_history[:-KEY_HISTORY]

    def adopt_key(self, key: bytes) -> None:
        """Follow the key the client proved it is using instead of the newest bump."""
        if self.key is not None and bytes(self.key) == bytes(key):
            return
        log.info("%s client kept zone key %s; following it", self.addr,
                 bytes(key[16:20]).hex())
        previous_key = bytes(self.key) if self.key is not None else None
        previous_cipher = self.cipher
        self.key = bytearray(key)
        self.cipher = self.world.zone_cipher_for(self.key)
        # Keep the key we were sending under as the fallback cipher, so a packet still in
        # flight from before the switch is still readable.
        self.prev_cipher = previous_cipher
        self.base_key = previous_key

    @staticmethod
    def incoming(world, session, addr, buf: bytearray):
        n = len(buf)
        if n <= HDR + 16:
            return None
        # A login (0x00A) arrives in the clear: MD5 of the body sits in the last 16 bytes.
        if md5(bytes(buf[HDR:n - 16])) == bytes(buf[n - 16:]) and \
                (struct.unpack_from("<H", buf, HDR)[0] & 0x1FF) == 0x0A:
            cid = struct.unpack_from("<I", buf, HDR + 12)[0]
            char = world.character_by_any_id(cid)
            account = char.get("account_id") if char else None
            game_session = world.service.active_game_session(account) if account else None
            if not char or not account or not game_session:
                log.warning("%s: login for %#x without an active session", addr, cid)
                return None
            # A zone change can lose the one zone-in packet (UDP, a busy client, a remote
            # tunnel). The client retries 0x00A two seconds later; without this it would
            # evict the session it just created, over and over, and never send 0x00C.
            existing = world.session_by_char(cid)
            # A session that is still zoning has not sent its first 0x00A yet: this is the
            # continuation of the 0x00B, not a retry of an unacknowledged zone-in.  A
            # same-zone warp reconnects inside the five-second retry window, so testing
            # only `last` here sent it down the replay path and left the box looping.
            if (existing is not None and existing.last is not None
                    and not getattr(existing, "zoning", False)
                    and time.time() - existing.last_packet_at <= 5.0):
                if existing.addr != addr:
                    world.sessions.pop(existing.addr, None)
                    existing.addr = addr
                existing.client_hdr = bytes(buf[:HDR])
                existing.client_id = struct.unpack_from("<H", buf, 0)[0]
                existing.last_packet_at = time.time()
                existing.zone_in_tries += 1
                world.sessions[addr] = existing
                ack = struct.unpack_from("<H", buf, 2)[0]
                sync = struct.unpack_from("<H", buf, HDR + 2)[0]
                if not existing.zone_loaded and existing.zone_in_tries <= ZONE_IN_REBUILDS:
                    # The client never acknowledged the zone-in. Replaying the same packet
                    # (same id, same body) is exactly what it is already ignoring, so
                    # rebuild the burst under the next id the client says it will open.
                    # The retries also alternate ciphers: whichever key the client kept,
                    # one of the rebuilt packets opens.
                    existing.queue.clear()
                    existing.last = None
                    existing.on_login()
                    existing.server_id = ((ack + 1) & 0xFFFF) if ack else \
                        ((existing.server_id + 1) & 0xFFFF)
                    use_base = existing.zone_in_tries % 2 == 1
                    log.info("%s char %#x retried the zone login; rebuilding the zone-in "
                             "(try %d, %s key, ack %d sync %d id %d)", addr, cid,
                             existing.zone_in_tries, "base" if use_base else "advanced",
                             ack, sync, existing.server_id)
                    out = existing.build(buf, next_id=False)
                    # The primary alternates the two newest keys; a client further behind
                    # still gets its own copy in the same tick, and so does the newest
                    # when the primary is the pre-change key.
                    primary = existing.base_key if use_base else existing.key
                    existing.extra_packets = existing.zone_in_copies(primary)
                    return existing.resend(use_base=True) if use_base else out
                if not existing.zone_loaded:
                    # It still will not take it: drop the session so the next 0x00A is a
                    # fresh login (the path a relaunch takes, and the one that works).
                    log.info("%s char %#x never acknowledged the zone-in; starting over",
                             addr, cid)
                    world.evict_session(existing, save=True,
                                        reason="zone-in never acknowledged")
                    return None
                # A duplicate after the zone is up: the client re-sent its login, so hand
                # the last packet back unchanged.
                log.info("%s duplicate login for char %#x; resending the zone-in", addr, cid)
                return existing.resend()
            s, continuing = world.take_login(addr, char, cid)
            # 0x400 is "self" in every client; other players get a targid from World.
            s.targid = world.assign_player_targid(cid)
            s.zone = int(char["zone"])
            s.pos = list(char["pos"])
            s.gone = False
            s.fresh_login = not continuing
            s.seen_players.clear()
            s.moving = False
            s.move_time = 0
            s.last_player_update = 0.0
            s.next_player_sync = 0.0
            if not continuing:
                # A client whose hand-off was dropped still holds the key it advanced to.
                # Resetting it to the account's sign-in key here is what left boxes looping
                # on "Downloading" forever: the client could never open the zone-in again,
                # and the relaunch was the only way out.
                parked = world.parked_keys(char, game_session["session_hash"])
                if parked:
                    s.set_key(parked[-1], history=parked)
                    log.info("%s resuming the hand-off key for %s (%d candidates)",
                             addr, s.char.get("name", "?"), len(parked))
                else:
                    primary = (world.keys.get(account) or
                               world.key_from_hash(game_session["session_hash"]))
                    # The client may still hold a key from a dropped hand-off whose game
                    # session cannot be matched any more (a relaunch, or a hand-off row
                    # replaced by another login).  Keep that sequence as extra copies: the
                    # sign-in key stays the primary and one readable datagram is enough.
                    stale = world.parked_history(char)
                    s.set_key(primary, history=stale)
                    if stale:
                        log.info("%s resuming %d parked hand-off key(s) for %s as copies",
                                 addr, len(stale), s.char.get("name", "?"))
            s.session_hash = bytes(game_session["session_hash"])
            if DEBUG:
                log.info("%s login key %s continuing=%s", addr, bytes(s.key).hex(), continuing)
            s.addr = addr
            s.client_hdr = bytes(buf[:HDR])
            world.sessions[addr] = s
            s.client_id = struct.unpack_from("<H", buf, 0)[0]
            s.queue.clear()
            s.last = None
            s.zone_loaded = False
            s.entities_sent = False
            s.position_seen = False
            s.engaged_id = None
            s.dead_until = 0.0
            s.load_zone_entities()
            log.info("%s char %#x logs in to %s at (%.1f, %.1f, %.1f)", addr, cid,
                     world.zones.name(s.zone), s.pos[0], s.pos[1], s.pos[2])
            s.on_login()
            # The reply's packet id follows the client's header ack + 1 when the client
            # sends one. The body sync word is the client's own retry counter (it goes
            # 1, 2, 3 ... on each repeated 0x00A), not a packet id the client is waiting
            # for; a fresh hand-off has neither and starts at 1.
            ack = struct.unpack_from("<H", buf, 2)[0]
            sync = struct.unpack_from("<H", buf, HDR + 2)[0]
            if ack and (continuing or abs(int(ack) - int(s.server_id)) <= 8):
                s.server_id = (ack + 1) & 0xFFFF
                reply = s.build(buf, next_id=False)
            elif sync > 1:
                # A fresh hand-off has no packet to ack yet; its first counter names the
                # id the zone-in has always gone out under.
                s.server_id = sync
                reply = s.build(buf, next_id=False)
            else:
                s.server_id = 0
                reply = s.build(buf)
            log.info("%s char %#x zone-in id %d (ack %d sync %d, continuing=%s, key word %s)",
                     addr, cid, s.server_id, ack, sync, continuing,
                     bytes(s.key[16:20]).hex())
            # Send the same zone-in under every key this hand-off has used; the gateway
            # sends these right after the reply.  A client that missed a 0x00B is on an
            # older key than the newest bump, and one datagram it can read is enough.
            s.extra_packets = s.zone_in_copies()
            return reply
        if session is None:
            return None
        body = session.decrypt(buf)
        if body is None:
            return None
        session.client_hdr = bytes(buf[:HDR])
        session.parse(buf, body)
        # Run due timers in the same exchange so swings, rewards and roaming are not starved
        # while a client is sending position packets continuously.
        world.advance_for_packet()
        # Delivery is normally one packet at a time: a client that has not acknowledged
        # the last one gets it again.  The retry has to be rate-limited, though.  A
        # GearSwap batch (fifteen equipment packets in one burst) sends them all before
        # the reply arrives, so every packet in the burst used to trigger the same resend
        # and the queue stood still.  One retry every RESEND_INTERVAL recovers a lost
        # packet just as well, and a newly queued action result always goes out at once.
        ack = struct.unpack_from("<H", buf, 2)[0]
        if session.last is not None and ack != session.server_id:
            now = time.time()
            if (not session.has_urgent()
                    and now - session.last_resend_at >= RESEND_INTERVAL):
                session.last_resend_at = now
                return session.resend()
        return session.build(buf)

    def decrypt(self, buf: bytearray):
        n = len(buf)
        words = ((n - HDR) // 4) & ~1
        self.opened_with_prev = False
        self.opened_with_key = None
        candidates: list[tuple[bytes, object]] = []
        seen: set[bytes] = set()
        if self.cipher is not None and self.key is not None:
            current = bytes(self.key)
            candidates.append((current, self.cipher))
            seen.add(current)
        if self.prev_cipher is not None and self.base_key is not None:
            previous = bytes(self.base_key)
            if previous not in seen:
                candidates.append((previous, self.prev_cipher))
                seen.add(previous)
        # Every bump this hand-off has made, newest first.  A client that missed a 0x00B
        # (UDP) or processed one late is on one of these, and the server no longer has to
        # guess: the packet itself says which key it is.
        for key in reversed(self.key_history):
            if len(candidates) >= KEY_HISTORY + 2:
                break
            if key in seen:
                continue
            seen.add(key)
            candidates.append((key, self.world.zone_cipher_for(key)))
        for index, (key, cipher) in enumerate(candidates):
            b = bytearray(buf)
            cipher.run(b, HDR, words, False)
            if md5(bytes(b[HDR:n - 16])) != bytes(b[n - 16:]):
                continue
            # A packet still in flight from before 0x00B carries the old key. That is
            # not the client telling us it kept its key: it just has not seen the zone
            # change yet. Remember which cipher opened it and let 0x00C decide (see
            # `handle`), otherwise one late packet pins every reply to the old key.
            # During a hand-off there is no such in-flight packet to protect: the client
            # is proving which key it will read the zone-in under, so follow it at once.
            if index > 0 and self.zone_loaded:
                self.opened_with_prev = (cipher is self.prev_cipher
                                         and self.prev_cipher is not self.cipher)
                self.opened_with_key = key
            elif index > 0:
                self.adopt_key(key)
            nbits = struct.unpack_from("<I", b, n - 20)[0]
            body = self.world.huff.decompress(bytes(b[HDR:n - 20]), nbits)
            if body is None:
                log.warning("%s: a packet that does not decompress", self.addr)
            return body
        log.warning("%s: a packet none of %d zone keys opens", self.addr, len(candidates))
        return None

    def parse(self, hdr: bytearray, body: bytes) -> None:
        self.last_packet_at = time.time()
        code = struct.unpack_from("<H", hdr, 0)[0]
        if self.sleeping:
            self._parse_sleeping(body)
            self.client_id = code
            return
        if DEBUG:
            types = []
            offset = 0
            while offset + 4 <= len(body) and body[offset + 1] & 0xFE:
                types.append("%03X@%d" % (struct.unpack_from("<H", body, offset)[0] & 0x1FF,
                                          struct.unpack_from("<H", body, offset + 2)[0]))
                offset += (body[offset + 1] & 0xFE) * 2
            log.info("in #%d ack %d (sent #%d): %s", code, struct.unpack_from("<H", hdr, 2)[0],
                     self.server_id, " ".join(types))
        offset = 0
        while offset + 4 <= len(body):
            size = (body[offset + 1] & 0xFE) * 2
            if size == 0 or offset + size > len(body):
                break
            ptype = struct.unpack_from("<H", body, offset)[0] & 0x1FF
            sync = struct.unpack_from("<H", body, offset + 2)[0]
            if DEBUG and ptype == 0x015:
                log.info("dispatch 015 sync=%d client_id=%d code=%d size=%d", sync, self.client_id, code, size)
            # Menu/inventory/chat requests can arrive with sync 0 (the client is not replying
            # to a particular server packet).  Dropping them leaves the status and equip
            # windows waiting forever, and it is why an item used from the bag did nothing.
            # 0x00C is the same case: after a zone change it can arrive with sync 0, and
            # dropping it means the rest of the zone state never goes out.  The Check menu
            # (0x00DD) is another menu request, so it must not be gated on the sync either.
            # 0x028 is the item menu's Drop and is a menu request too.
            if ptype in (0x00C, 0x028, 0x037, 0x050, 0x051, 0x052, 0x053, 0x05D, 0x061,
                         0x0B5, 0x0DD, 0x06E, 0x06F, 0x070, 0x071, 0x074, 0x076, 0x077,
                         0x078) or \
                    self.client_id < sync <= code:
                self.handle(ptype, body[offset:offset + size])
            offset += size
        # Settle the outfit for this datagram's actions, but let the derived packets wait
        # for the burst to finish (tick sends them once equip_sync_at passes).  A datagram
        # that arrives after the window still flushes here: the session may stop ticking
        # right after it (a /heal or a zone line), and the follow-up must not wait for the
        # wake-up.
        if self.equipment_changed:
            self.settle_equipment()
            if time.time() >= self.equip_sync_at:
                self.flush_equipment()
        self.client_id = code

    def handle(self, t: int, p: bytes) -> None:
        handled = t in self.seen
        if not handled:
            # One line per packet type: this is how a stuck menu shows itself when the
            # client keeps a request private until the server answers something else.
            log.info("%s first %03X (%d bytes): %s", self.addr, t, len(p), bytes(p).hex())
        self.seen.add(t)
        if t == 0x00C:  # the client has the zone: send it everything else
            if getattr(self, "opened_with_prev", False) and self.base_key is not None:
                # The client kept the key it had before 0x00B. Now that it has proved that,
                # follow it, so the zone state goes out under the key it can read.
                self.cipher, self.prev_cipher = self.prev_cipher, self.cipher
                self.key = bytearray(self.base_key)
                self.opened_with_prev = False
                log.info("%s follows the pre-zone key for %s", self.addr,
                         self.char.get("name", "?"))
            if not self.zone_loaded:
                self.after_zone_in()
        elif t == 0x050:  # equipment change
            self.equip(p)
        elif t == 0x052:  # the client asks whether the set it is assembling is legal
            self.equipset_check(p)
        elif t == 0x037:  # item use
            self.item_use(p)
        elif t == 0x028:  # the item menu's Drop: the player threw a stack away
            self.item_drop(p)
        elif t == 0x03A:  # after sorting a bag, merge its partial stacks
            self.item_stack(p)
        elif t == 0x01A:  # target action: talk, engage, disengage
            self.action(p)
        elif t == 0x0E8:  # /heal
            self.heal_command(p)
        elif t == 0x06E:  # /pcmd add, /acmd add and the party menu's invite
            self.party_invite(p)
        elif t == 0x074:  # accepted or declined an invitation
            self.party_invite_response(p)
        elif t == 0x06F:  # /pcmd leave, /acmd leave
            self.party_leave(p)
        elif t == 0x070:  # /pcmd breakup, /acmd breakup
            self.party_disband(p)
        elif t == 0x071:  # /pcmd kick, /acmd kick
            self.party_kick(p)
        elif t == 0x076:  # the client lost its roster and asks for it again
            self.party_reload(p)
        elif t == 0x077:  # /pcmd leader, /acmd leader
            self.party_change(p)
        elif t == 0x078:  # the client asks for the server-side party id
            self.party_checkid(p)
        elif t == 0x083:  # shop purchase
            self.buy(p)
        elif t in (0x016, 0x017):  # the client asks for an entity it lacks
            self.request_entity(p)
        elif t == 0x015:  # position (the old zone's, while changing zones)
            x, y, z = struct.unpack_from("<fff", p, 4)
            if DEBUG:
                log.info("%s pos %.2f %.2f %.2f zoning=%s", self.addr, x, y, z, self.zoning)
            if self.zoning:
                return
            rot = struct.unpack_from("<b", p, 20)[0] & 255
            if os.environ.get("FANXI_POS_LOG"):
                last = getattr(self, "_logged_pos", None)
                if last and (abs(x - last[0]) + abs(z - last[1])) > 0.4:
                    log.info("move dx=%.2f dz=%.2f rot=%d", x - last[0], z - last[1], rot)
                if not last or (abs(x - last[0]) + abs(z - last[1])) > 0.4:
                    self._logged_pos = (x, z)
            if abs(x) < 0.01 and abs(y) < 0.01 and abs(z) < 0.01:
                # The client reports the origin while a zone is still loading.  Taking it
                # saved 0,0,0 as the character's position and logged them back into the void.
                if any(abs(v) > 0.01 for v in self.pos[:3]):
                    return
            old_x, old_y, old_z, old_rot = self.pos
            moved = math.dist((x, y, z), (old_x, old_y, old_z)) > 0.02
            turned = 2 < abs(rot - old_rot) < 254
            was_moving = self.moving
            self.moving = moved
            # MovTime is the 13-bit walk-cycle counter in Flags0; it advances while the
            # character moves and resets when it stops.
            self.move_time = (self.move_time + 1) & 0x1FFF if moved else 0
            self.pos = [x, y, z, rot]
            if self.resting:
                self.stop_resting()
            self.last_move_at = time.time()
            self.position_seen = True
            if self.entities_sent:
                self.open_nearby_doors()
            self.save_position()
            self.sync_entities()
            # Other clients draw this character from 0x00D position updates. Throttle to
            # ~20 Hz so followers see turns and steps promptly; always send the one packet
            # that says "stopped" so they do not keep walking after the key is released.
            if self.entities_sent:
                now = time.time()
                if moved and now - self.last_player_update >= 0.05:
                    self.last_player_update = now
                    self.world.broadcast_player(self, packets.SEND_POSITION, moving=True)
                elif (not moved and was_moving) or (turned and now - self.last_player_update >= 0.05):
                    self.last_player_update = now
                    self.world.broadcast_player(self, packets.SEND_POSITION, moving=False)
        elif t == 0x05E:  # a zone line
            rect = struct.unpack_from("<I", p, 4)[0]
            name = rect.to_bytes(4, "little")
            log.info("%s zone line %#x %s", self.addr, rect,
                     "".join(chr(b) if 32 <= b < 127 else "." for b in name))
            # "zmrq" is the universal Mog House exit line.  The client sends it with the
            # menu pick in MyRoomExitMode (0 = the area entered from, 1-4 = another area
            # of this city).  The entrance doors are the city's own tags.
            if name == b"zmrq":
                self.moghouse_exit(p)
                return
            if name[:3] in (b"zmr", b"zms"):
                self.toggle_moghouse()
                return
            line = self.world.zones.lines.get(rect)
            if line:
                zone, pos = int(line[0]), list(line[1:])
                # A main account leads its boxes through the line: the followers run the
                # same zone-in their own client would have run had they stepped on it.
                self.change_zone_with_family(zone, pos)
            else:
                # Never leave the client on the black zone-transition screen: reload this
                # zone at its spawn, which also moves the player off the trigger.
                log.info("%s zone line %#x (%r) is not authored", self.addr, rect, name)
                self.say("That passage is not open in this build.")
                self.change_zone(self.zone, list(self.world.zones.position(self.zone)))
        elif t == 0x0B5:  # chat
            kind = int(p[4]) if len(p) > 4 else 0
            text = bytes(p[6:]).split(b"\0")[0].decode("ascii", "replace")
            # Fanxi commands are typed "//cmd".  The host hands the server the "!cmd" say form
            # instead (the client's own slash parser must never see the second slash), so accept
            # both spellings here, plus the old slash-bang form for macros saved before the switch.
            stripped = text.lstrip("/")
            command = text[2:] if text.startswith("//") else None
            if command is None and stripped.startswith("!"):
                command = stripped[1:]
            if command is not None:
                self.command(command.split())
            elif kind in (0, 8) and stripped:
                # Say and emote both need the server to echo them; the client does not
                # draw its own outgoing line.  Kind 8 is the emote animation.
                self.queue.append(sub(0x017, packets.chat_std(
                    self.char["name"], stripped, self.zone, kind)))
        elif t == 0x05B:  # the client picked an option in an event, or finished it
            self.event_end(p)
        elif t == 0x0BE:  # the client spent or removed a merit point, or changed mode
            self.merit_edit(p)
        elif t == 0x0100:  # the Moogle menu asked for a job change
            self.myroom_job(p)
        elif t == 0x029:  # the client moved (or split) an item between containers
            self.item_move(p)
        elif t == 0x04B:  # the server message, which the client asks for until it has all of it
            kind, lang = p[6], p[7]
            stamp, offset = struct.unpack_from("<i", p, 8)[0], struct.unpack_from("<i", p, 16)[0]
            if kind == 1:
                self.queue.append(self.server_message(lang, stamp, offset))
        elif t == 0x061:  # its stats: retail answers with the whole local-player bundle
            log.info("%s asks for stats", self.addr)
            self.last = None
            # Retail answers with the whole local-player set; the client appears to wait
            # for all of it before it lets a menu action (equip, door) go through.
            # Command data belongs here, and before 0x062: the client builds the Weapon
            # Skills list when the skill packet arrives, so the 0x0AC bits must be there
            # first.  The early zone-in copy alone leaves the list empty.
            self.queue += [self.party_member(), self.char_stats(),
                           self.char_feats(), self.char_abilities(), self.char_commands(),
                           self.char_skills(), self.abil_recast(), self.merits(),
                           self.monstrosity(), self.job_points()]
            self.queue += self.merit_list()
            self.abilities_retries = sorted(set(self.abilities_retries + [time.time() + 1.0]))
        elif t == 0x05A:  # conquest standings: none
            self.queue.append(sub(0x05E, bytes(0xB0)))
        elif t == 0x053:  # /lockstyle and /lockstyleset
            self.lockstyle(p)
        elif t == 0x05D:  # an emote (/wave, /nod, /bow, ...)
            self.motion(p)
        elif t == 0x00DD:  # /check, /checkname and /checkparam
            self.inspect(p)
        elif t == 0x03C:  # the blacklist
            self.queue.append(self.blacklist())
        elif t == 0x0E7:  # /logout, /shutdown
            # A deliberate logout is not a dropped link: retail takes the buffs with you,
            # but an ability cooldown keeps running, so the row is rewritten with the
            # recasts only and this dead session may not overwrite it again on its way out.
            self.save_live_state(include_effects=False)
            self.live_state_closed = True
            self.world.leave_party(self)
            self.world.despawn_player(self)
            self.gone = True
            self.world.release_player_targid(int(self.char["char_id"]))
            with self.world.lock:
                for key, value in list(self.world.by_char.items()):
                    if value is self:
                        self.world.by_char.pop(key, None)
            self.save_position(force=True)
            self.queue.append(self.logout_packet(1))
            log.info("%s logs out", self.addr)
        elif not handled:  # the rest needs no answer here; each is logged once
            log.debug("0x%03X (%d bytes) ignored", t, len(p))

    # --- party and alliance commands ----------------------------------------------------------
    def party_packets(self) -> list[Msg]:
        """The roster packets this client needs after a zone-in, reload or membership change."""
        return self.world.party_packets(self)

    def party_invite(self, p: bytes) -> None:
        """C2S 0x06E: /pcmd add, /acmd add, or the party menu's invite action."""
        if len(p) < 11:
            return
        unique, actindex, kind = struct.unpack_from("<IHB", p, 4)
        error = self.world.invite(self, int(unique), int(actindex), int(kind))
        if error:
            self.say(error)

    def party_invite_response(self, p: bytes) -> None:
        """C2S 0x074: the invitation prompt's Accept (1) or Decline (0)."""
        if len(p) < 5:
            return
        error = self.world.respond_invite(self, bool(p[4]))
        if error:
            self.say(error)

    def party_leave(self, p: bytes) -> None:
        """C2S 0x06F: /pcmd leave (Kind 0) or /acmd leave (Kind 5)."""
        kind = p[4] if len(p) > 4 else 0
        if int(kind) == 5:
            error = self.world.leave_alliance(self)
            if error:
                self.say(error)
            return
        self.world.leave_party(self)

    def party_disband(self, p: bytes) -> None:
        """C2S 0x070: /pcmd breakup (Kind 0) or /acmd breakup (Kind 5)."""
        kind = p[4] if len(p) > 4 else 0
        if int(kind) == 5:
            error = self.world.disband_alliance(self)
        else:
            group = self.world.party_of(int(self.char["char_id"]))
            if group is None:
                error = "You are not in a party."
            elif group.leader_id != int(self.char["char_id"]):
                error = "Only the party leader can disband the party."
            else:
                self.world.disband_party(group)
                error = ""
        if error:
            self.say(error)

    def party_kick(self, p: bytes) -> None:
        """C2S 0x071: remove a member from the party or a party from the alliance."""
        if len(p) < 12:
            return
        unique, _actindex, kind = struct.unpack_from("<IHB", p, 4)
        name = bytes(p[12:27]).split(b"\0")[0].decode("ascii", "replace")
        victim = int(unique)
        if not victim:
            group = self.world.party_of(int(self.char["char_id"]))
            if group is not None:
                match = next((member for member in group.members
                              if member.name.casefold() == name.casefold()), None)
                victim = match.char_id if match is not None else 0
        if not victim:
            return
        error = self.world.kick_member(self, victim, int(kind))
        if error:
            self.say(error)

    def party_reload(self, p: bytes) -> None:
        """C2S 0x076: the client lost its party information and asks for it again."""
        # Solo: the empty table still clears a stale roster, and the own-row GROUP_LIST
        # carries the job pair the HUD's spell/Trust lists read.
        messages = self.party_packets() or self.world.solo_roster_packets(self)
        self.queue += messages

    def party_change(self, p: bytes) -> None:
        """C2S 0x077: pass party leadership (Kind 0) or alliance leadership (Kind 5)."""
        if len(p) < 22:
            return
        name = bytes(p[4:20]).split(b"\0")[0].decode("ascii", "replace")
        kind, change = int(p[20]), int(p[21])
        if kind == 0 and change == 0:
            error = self.world.set_party_leader(self, name)
        elif kind == 5 and change == 1:
            error = self.world.set_party_leader(self, name, alliance_leader=True)
        else:
            return
        if error:
            self.say(error)

    def party_checkid(self, p: bytes) -> None:
        """C2S 0x078: reply with the server-side party id.

        A 0x0E1 carrying id 0 crashes the retail client (it follows a null group
        pointer), so a solo player gets no answer rather than a zero one.
        """
        owner = int(self.char["char_id"])
        group_id = self.world.group_id(owner)
        if group_id:
            self.queue.append(sub(0x0E1, packets.group_checkid(group_id)))

    # --- //invite -------------------------------------------------------------------------------
    def invite_command(self, words: list[str]) -> None:
        """//invite [subs|all|<name>]: party the whole sub team, or one online player.

        Unlike the client's /pcmd add, the name is resolved here, so a sub in another zone
        or outside the client's spawn range can still be invited.  A family sub accepts
        automatically; a non-family character gets the normal invitation prompt.
        """
        query = " ".join(words).strip().strip('"').strip("'")
        if not query or query.casefold() in ("subs", "all", "team"):
            self._invite_sub_accounts()
            return
        target = self.world.session_by_name(query)
        if target is None:
            self.say("No online player named %s." % query)
            return
        if target is self:
            self.say("You cannot invite yourself.")
            return
        target_id = int(target.char["char_id"])
        error = self.world.invite(self, target_id,
                                  int(getattr(target, "targid", 0) or 0),
                                  PARTY_KIND_PARTY)
        if error:
            self.say(error)
            return
        if self.world.party_of(target_id) is not None:
            self.say("%s joined your party." % target.char.get("name"))
        else:
            self.say("Invited %s to your party." % target.char.get("name"))

    def makeparty_command(self, words: list[str]) -> None:
        """//makeparty: pull every online sub out of its party and into the sender's."""
        if words:
            self.say("Usage: //makeparty")
            return
        self._invite_sub_accounts(drop_existing=True)

    def _invite_sub_accounts(self, *, drop_existing: bool = False) -> None:
        """Invite every online sub-account in this account family.

        If the main has just come back to find its subs still grouped, the first step is
        to rejoin that party and take the lead back; only then are any missing subs
        invited individually.  This is what makes ``//invite subs`` work after a logout or
        a frozen client, when a plain invite would be refused with "already in a party".
        With ``drop_existing`` (``//makeparty``), a sub that is in any other party leaves
        it before the invite, so the one button always produces one team.
        """
        owner = int(self.char["char_id"])
        try:
            recovered = self.world.recover_family_party(self)
        except Exception as exc:
            log.warning("%s party recovery failed: %s", self.addr, exc)
            recovered = ""
        if recovered:
            self.say(recovered)
        group = self.world.party_of(owner)
        if group is not None and group.leader_id != owner:
            self.say("Only the party leader can invite.")
            return
        if group is not None and group.is_full():
            self.say("Your party is full.")
            return
        targets = []
        for session in self._family_sessions():
            if session is self:
                continue
            try:
                account = self.world.service.account(
                    int(session.char.get("account_id") or 0))
            except Exception:
                continue
            if account.get("kind", "main") == "sub":
                targets.append(session)
        if not targets:
            self.say("No online sub-accounts to invite.")
            return
        joined: list[str] = []
        dropped: list[str] = []
        already: list[str] = []
        skipped: list[str] = []
        for target in targets:
            target_id = int(target.char["char_id"])
            name = str(target.char.get("name") or "?")
            existing = self.world.party_of(target_id)
            if group is not None and existing is group:
                already.append(name)
                continue
            if group is not None and group.is_full():
                # Do not pull a sub out of its party only to fail the invite.
                skipped.append("%s (your party is full)" % name)
                break
            if existing is not None:
                if not drop_existing:
                    skipped.append("%s (already in another party)" % name)
                    continue
                self.world.leave_party(target)
                dropped.append(name)
            error = self.world.invite(self, target_id,
                                      int(getattr(target, "targid", 0) or 0),
                                      PARTY_KIND_PARTY)
            if error:
                skipped.append("%s (%s)" % (name, error))
                if "full" in error.casefold():
                    break
                continue
            joined.append(name)
            group = self.world.party_of(owner)
        if dropped:
            self.say("Left their old party: %s." % ", ".join(dropped))
        if joined:
            self.say("Joined party: %s." % ", ".join(joined))
        if already and not joined and not recovered:
            self.say("Already in your party: %s." % ", ".join(already))
        if skipped:
            self.say("Not invited: %s." % "; ".join(skipped))
        if not joined and not dropped and not skipped and not already and not recovered:
            self.say("No online sub-accounts to invite.")

    def trust_command(self, args: list[str]) -> None:
        """//trust: list/release alter egos, or configure a support Trust's actions.

        The HUD calls ``//trust release <spell id>`` when an active Trust button is
        clicked.  The client's own Release menu is an entity action, not a chat command,
        so this is the server-side equivalent.  ``//trust <id|name> ...`` routes to the
        per-character action set for Joachim, Luzaf, Qultada, Koru-Moru, Sylvie (UC) and
        Ygnas.
        """
        if args:
            trust_id = self._support_trust_id(args[0])
            if trust_id is not None:
                self._trust_command(trust_id, args[1:])
                return
        active = self.active_trusts()
        if not args or args[0].casefold() in ("list", "status"):
            if not active:
                self.say("You have no alter egos.")
            else:
                self.say("Active alter egos: " + ", ".join(
                    "%s (%d)" % (entity.name, int(entity.trust_spell))
                    for entity in active))
            return
        if args[0].casefold() not in ("release", "remove", "dismiss") or len(args) < 2:
            self.say("Usage: //trust [list | release <spell id|name|all> | "
                     "<support trust> [set songs|spells|rolls \"<name>\" ... | "
                     "set default]]")
            return
        target = " ".join(args[1:]).strip().strip('"').strip("'")
        if target.casefold() == "all":
            if not active:
                self.say("You have no alter egos.")
                return
            for entity in list(active):
                self.world.despawn_trust(entity)
            self.say("All alter egos leave your party.")
            return
        try:
            spell_id = int(target, 0)
        except ValueError:
            spell_id = None
        wanted = "".join(ch for ch in target.casefold() if ch.isalnum())
        match = None
        for entity in active:
            if spell_id is not None:
                if int(entity.trust_spell) == spell_id:
                    match = entity
                    break
            else:
                name_key = "".join(ch for ch in str(entity.name).casefold()
                                   if ch.isalnum())
                if name_key == wanted:
                    match = entity
                    break
        if match is None:
            self.say("No active alter ego matches %s." % target)
            return
        self.say("%s leaves your party." % match.name)
        self.world.despawn_trust(match)

    def doors_command(self, words: list[str]) -> None:
        """//doors auto [on|off]: the opt-in automatic door mode."""
        if not words or words[0].casefold() != "auto":
            self.say("Automatic doors are %s. Use //doors auto on|off." % (
                "on" if self.auto_open_doors else "off"))
            return
        if len(words) >= 2:
            value = words[1].casefold()
            if value in ("on", "1", "yes", "true"):
                enabled = True
            elif value in ("off", "0", "no", "false"):
                enabled = False
            else:
                self.say("Use //doors auto on or //doors auto off.")
                return
        else:
            enabled = not self.auto_open_doors
        self.auto_open_doors = enabled
        try:
            self.world.service.set_character_setting(
                int(self.char["id"]), "auto_open_doors", "1" if enabled else "0")
        except Exception as exc:
            log.warning("%s could not save the door setting: %s", self.addr, exc)
            self.say("The door setting could not be saved.")
            return
        if enabled and not self.world.zones.allows_auto_doors(self.zone):
            self.say("Automatic doors are on. This area is a dungeon, so its doors stay manual.")
        else:
            self.say("Automatic doors are %s." % ("on" if enabled else "off"))

    # --- mounts --------------------------------------------------------------------------------

    def mount(self) -> mounts.Mount | None:
        """The mount this character is riding, or None while on foot."""
        return mounts.by_id(self.mount_id)

    def set_mount(self, mount_id: int, announce: bool = True) -> mounts.Mount | None:
        """Call a mount under this character; every client that draws it is told.

        The local client learns the id from 0x037 (mount_id plus Chocobo_Index, which is
        what separates the personal chocobo from standing on the ground); every other
        client gets the same id in the General block of 0x00D (Flags6).  Retail's
        one-minute recast and thirty-minute ride are not enforced — a private server's
        mounts are a convenience, and a team that has to wait a minute between calls is
        not one.
        """
        mount = mounts.by_id(mount_id)
        if mount is None:
            return None
        said = mount.description.replace("Calls forth", "You call forth", 1)
        if int(self.mount_id) == int(mount.id):
            if announce:
                self.say("%s" % said)
            return mount
        if int(self.mount_id) >= 0:
            # The client builds the mount model when the ride starts and keeps it while one
            # is out: a switch has to stand on foot for a moment first.  Dismount now, hand
            # the call to the tick, and say so at once so the command still answers.
            self.mount_id = -1
            self.pending_mount = (int(mount.id), time.time() + MOUNT_SWITCH_DELAY)
            self.queue.append(self.char_status())
            self.queue.append(self.char_update(packets.SEND_HP))
            self.queue.append(self.status_icons())
            self.world.broadcast_player(self, packets.SEND_HP)
            if announce:
                self.say("%s" % said)
            log.info("%s switches to %s (%d) in %.1fs", self.addr, mount.name, mount.id,
                     MOUNT_SWITCH_DELAY)
            return mount
        self.pending_mount = None
        self.mount_id = int(mount.id)
        self.mount_called_at = time.time()
        # 0x037 carries the animation, the Mounted effect, the Chocobo_Index and the mount
        # id — that is the packet the rider's own client acts on.  The General 0x00D puts
        # the same animation and id on the entity a second time, the way retail's entity
        # updates reach every client in the zone including the player's own.
        self.queue.append(self.char_status())
        self.queue.append(self.char_update(packets.SEND_HP))
        self.queue.append(self.status_icons())
        self.world.broadcast_player(self, packets.SEND_HP)
        try:
            self.world.service.set_character_mount(int(self.char["id"]), int(mount.id))
        except Exception as exc:
            log.warning("%s could not save the mount: %s", self.addr, exc)
        if announce:
            self.say("%s" % mount.description.replace("Calls forth", "You call forth", 1))
        log.info("%s mounts %s (%d)", self.addr, mount.name, mount.id)
        return mount

    def resend_mounts(self) -> bool:
        """Queue the mount unlock table (0x0AE) again for a live client."""
        if not self.logged_in or self.zoning or getattr(self, "gone", False):
            return False
        self.queue.append(sub(0x0AE, mounts.bitfield()))
        return True

    def dismount(self, announce: bool = True) -> bool:
        """Back on foot.  False when the character was not mounted."""
        # An explicit dismount drops a switch that was waiting for the client's rebuild.
        self.pending_mount = None
        if int(self.mount_id) < 0:
            if announce:
                self.say("You are not mounted.")
            return False
        self.mount_id = -1
        self.queue.append(self.char_status())
        self.queue.append(self.char_update(packets.SEND_HP))
        self.queue.append(self.status_icons())
        self.world.broadcast_player(self, packets.SEND_HP)
        if announce:
            self.say("You dismount.")
        log.info("%s dismounts", self.addr)
        return True

    def mount_family(self, mount: mounts.Mount) -> list["ZoneSession"]:
        """Call one mount under this character and every online sub-account box."""
        others = [session for session in self._family_sessions() if session is not self]
        self.set_mount(mount.id)
        for session in others:
            session.set_mount(mount.id)
        if others:
            self.say("The call reaches %s." % _name_list(
                [str(session.char.get("name") or "a box") for session in others]))
        else:
            self.say("No sub-account characters are online; the call reached only you.")
        # A box that is still logging in (or parked) cannot answer; say so rather than
        # letting the player wonder why the team is one short.
        try:
            family = {int(value) for value in self.world.service.account_family_ids(
                int(self.char.get("account_id") or 0))}
        except Exception:
            family = set()
        online = {int(self.char.get("account_id") or 0)}
        online.update(int(session.char.get("account_id") or 0) for session in others)
        missing = len(family - online)
        if missing > 0:
            self.say("%d sub-account character(s) are offline or asleep." % missing)
        return [self] + others

    def mount_party(self, mount: mounts.Mount | None = None) -> list["ZoneSession"]:
        """Call a mount under this character and every online sub-account box.

        With no name every box gets its own mount, drawn at random (the caller too), so
        ``//mount party`` rides out as a mixed parade; with a name everyone rides that one.
        """
        others = [session for session in self._family_sessions() if session is not self]
        targets = [self] + others
        if mount is not None:
            for session in targets:
                session.set_mount(mount.id)
            if others:
                self.say("The call reaches %s." % _name_list(
                    [str(session.char.get("name") or "a box") for session in others]))
            else:
                self.say("No sub-account characters are online; the call reached only you.")
        else:
            picks = random.sample(mounts.all_mounts(), min(len(targets), mounts.count()))
            for session, pick in zip(targets, picks):
                session.set_mount(pick.id)
            parts = []
            for session, pick in zip(targets, picks):
                who = " (you)" if session is self else ""
                parts.append(pick.name + who)
            self.say("Mount party: %s." % ", ".join(parts))
        # A box that is still logging in (or parked) cannot answer; say so rather than
        # letting the player wonder why the team is one short.
        try:
            family = {int(value) for value in self.world.service.account_family_ids(
                int(self.char.get("account_id") or 0))}
        except Exception:
            family = set()
        online = {int(self.char.get("account_id") or 0)}
        online.update(int(session.char.get("account_id") or 0) for session in others)
        missing = len(family - online)
        if missing > 0:
            self.say("%d sub-account character(s) are offline or asleep." % missing)
        return targets

    def dismount_family(self) -> list["ZoneSession"]:
        """Dismount this character and every online sub-account box."""
        targets = [self] + [session for session in self._family_sessions() if session is not self]
        changed = [session for session in targets if session.dismount(announce=session is not self)]
        if not changed:
            self.say("No one in the team is mounted.")
        elif len(changed) > 1:
            self.say("The team dismounts.")
        return changed

    def mount_list(self) -> None:
        """Every mount this client knows, as id/name cells, four to a line."""
        cells = ["%d %s" % (mount.id, mount.name) for mount in mounts.all_mounts()]
        for offset in range(0, len(cells), 4):
            self.say(", ".join(cells[offset:offset + 4]))
        self.say("//mount <name|id> calls one; //mount party [name|id] calls it for your team "
                 "(no name: a random mount for every box); //mount off dismounts.")

    def songs_command(self, words: list[str]) -> None:
        """//songs — the songs on this character, with their remaining time.

        The client draws one icon per effect id, and every Minuet tier shares icon
        198 (every March 214), so a bard cannot tell from the icon row which tiers
        are up.  The server keys each song by spell id, so it can.
        """
        now = time.time()
        active = [state for state in self.effect_state.values()
                  if state.get("song") and float(state.get("until", 0.0)) > now]
        if not active:
            self.say("No songs on you.")
            return
        active.sort(key=lambda state: -float(state.get("until", 0.0)))
        labels = (
            (mod.ATT, "Attack", 1), (mod.RATT, "R.Attack", 1),
            (mod.ACC, "Accuracy", 1), (mod.RACC, "R.Accuracy", 1),
            (mod.DEF, "Defense", 1), (mod.MDEF, "M.Defense", 1),
            (mod.MACC, "M.Accuracy", 1), (mod.EVA, "Evasion", 1),
            (mod.HASTE_MAGIC, "Haste", 100),
            (mod.DMG, "Damage taken", 100),
            (mod.UDMGPHYS, "Damage taken", 100),   # Scherzo writes the uncapped pair
            (mod.DAMAGE_LIMITP, "Damage limit", 100),
            (mod.FIRE_MEVA, "Fire res.", 1), (mod.ICE_MEVA, "Ice res.", 1),
            (mod.WIND_MEVA, "Wind res.", 1), (mod.EARTH_MEVA, "Earth res.", 1),
            (mod.THUNDER_MEVA, "Thunder res.", 1), (mod.WATER_MEVA, "Water res.", 1),
            (mod.LIGHT_MEVA, "Light res.", 1), (mod.DARK_MEVA, "Dark res.", 1),
        )
        for state in active:
            left = int(float(state["until"]) - now)
            mods = state.get("mods") or {}
            parts = []
            for mod_id, label, scale in labels:
                value = int(mods.get(mod_id, 0))
                if not value:
                    continue
                if scale == 100:
                    parts.append("%s %g%%" % (label, value / 100.0))
                else:
                    parts.append("%s %+d" % (label, value))
            if int(state.get("tick", 0)):
                parts.append("tick %d" % int(state["tick"]))
            self.say("%s (%d:%02d left)%s" % (
                state.get("song_name") or "song", left // 60, left % 60,
                "  " + ", ".join(parts) if parts else ""))
        self.say("%d song(s) on you, %d slot(s)." % (len(active), self._song_limit()))

    def mount_command(self, words: list[str]) -> None:
        """//mount [all] <name|id> | off | list — the mount system's chat command."""
        args = list(words or [])
        team = False
        if args and args[0].casefold() in ("all", "party", "team", "subs", "everyone"):
            team = True
            args = args[1:]
        if not args:
            if team:
                # No name: the whole party gets a random mount each.
                self.mount_party()
            else:
                self.mount_list()
            return
        verb = args[0].casefold()
        if verb in ("list", "ls", "?"):
            self.mount_list()
            return
        if verb in ("off", "dismount", "none", "down", "stop"):
            if team:
                self.dismount_family()
            else:
                self.dismount()
            return
        if verb in ("me", "self"):
            team = False
            args = args[1:]
            if not args:
                self.mount_list()
                return
        query = " ".join(args).strip()
        if team and query.casefold() in ("random", "any", "mix"):
            self.mount_party()
            return
        mount, error = mounts.find(query)
        if mount is None:
            self.say(error)
            return
        if team:
            self.mount_party(mount)
        else:
            self.set_mount(mount.id)

    def command(self, words: list[str]) -> None:
        commands = (
            "commands: //zone <id> [x y z [rot]], //pos <x> <y> <z> [rot], //where, //door <id>, "
            "//time <hour>, /heal rests, //heal refills, //entities, //moghouse, //mh out [name|all] (step the family out), //home, "
            "//disengage (break a kept range engagement), "
            "//warp mark [alias] | me|all <number|alias> | all me | call <name> | list [page] | "
            "delete <n|alias> | rename <n> <alias> (your saved places), "
            "//hp [menu number|zone] (Home Points), //sg [n], "
            "//trust [list|release <spell id|name|all>] (alter egos), "
            "//trust <joachim|luzaf|qultada|koru-moru|sylvie-uc|ygnas> "
            "[set songs|spells|rolls \"<name>\" ...|set default] (support trust actions), "
            "//makeparty (drop your online subs from their parties, then invite them), "
            "//invite [subs|all|<name>] (party your online sub team, or invite one player)",
            "//locker store|grab|list <all|ammo|back|jsecapes|materials|name>, "
            "//storage organize | store <job|all> | grab <job|all> | list [job|all] "
            "(keeps only this job's gear out; the 9999 locker holds the rest), "
            "//recycle [list|restore <slot>|drop <bag> <slot>|purge] (30-day recycle bin), "
            "//item move <bag> <slot> <to-bag> [count], //item store locker <bag> <slot> [count], "
            "//item pull <slip|locker> <id> [extra]",
            "//songs (the songs on you, with time left), "
            "//sleep (park this box without logging out), //wake (resume it), "
            "//ws <name>, //ja <name>, //abilities, //traits, //job <job> [sub] (stores every "
            "other job's gear, pulls this job's set and tidies the bags), "
            "//job <character> <job> <sub> (the same swap on a sub-account), //cast <spell>, "
            "//equip <name>, //unequip <slot>, //model <item> <id>, "
            "//modelnext <item>, //event <id> [p1..p8], "
            "//character model <race> <1-48|random>, //reload (re-read the launcher's Data page), "
            "//doors auto [on|off] (automatically open city/outdoor doors), "
            "//mount party [mount name|id] | off | list (mounts; no name gives every sub box "
            "a random mount), "
            "//merits [n], //stock, //r30 [item], //rp30, "
            "//augment <A-D|index|off|list> <item>, "
            "//cape <build|list|off> <item>",
        )
        try:
            if words and words[0].casefold() == "sleep":
                self.sleep()
                return
            if words and words[0].casefold() == "wake":
                self.wake()
                return
            if words and words[0].casefold() == "songs":
                self.songs_command(words[1:])
                return
            if words and words[0] == "reload":
                self.reload_character()
                self.say("Character data reloaded.")
            elif words and words[0] == "zone" and len(words) >= 2:
                zone = int(words[1], 0)
                pos = [float(v) for v in words[2:5]] + [int(words[5]) if len(words) > 5 else 0] \
                    if len(words) >= 5 else None
                if pos is None:
                    spawn = self.world.zones.position(zone)
                    if not spawn or all(float(v) == 0.0 for v in spawn[:3]):
                        self.say("Zone %d has no spawn here. Try //zone 100 (West Ronfaure)." % zone)
                        return
                self.change_zone(zone, pos)
            elif words and words[0] == "pos" and len(words) >= 4:
                self.change_zone(self.zone, [float(v) for v in words[1:4]] +
                                 [int(words[4]) if len(words) > 4 else self.pos[3]])
            elif words and words[0] == "where":
                self.say("%s (%d): %.2f %.2f %.2f rot %d" % (
                    self.world.zones.name(self.zone), self.zone, self.pos[0], self.pos[1], self.pos[2], self.pos[3]))
            elif words and words[0].casefold() == "character":
                self.character_command(words[1:])
            elif words and words[0].casefold() == "doors":
                self.doors_command(words[1:])
            elif words and words[0].casefold() == "mount":
                self.mount_command(words[1:])
            elif words and words[0].casefold() == "mounts":
                # The Mount HUD is a client addon and answers //mounts itself; a box
                # without it gets the list here instead of the whole command help.
                self.mount_list()
            elif words and words[0] == "door" and len(words) >= 2:
                name = words[1][:4].ljust(4, "\0")
                if name.rstrip("\0") not in {"_6u4", "_6u8", "_6ua", "_6ue"}:
                    self.say("Known door ids here: _6u4 _6u8 _6ua _6ue")
                    return
                door_id = int.from_bytes(name.encode("ascii", "replace"), "little")
                targid = 0x300 + sum(1 for e in self.entities if int(getattr(e, "targid", 0)) >= 0x300)
                entity = ZoneEntity(
                    kind="npc",
                    id=0x01000000 | (self.zone << 12) | (targid & 0xFFF),
                    targid=targid, zone=self.zone, name=name.rstrip("\0"),
                    x=self.pos[0], y=self.pos[1], z=self.pos[2], rot=self.pos[3],
                    model=0, size=2, door_id=door_id, animation=9,
                    triggerable=False, widescan=False, script="door")
                self.entities.append(entity)
                self.queue_entity(entity)
                self.say("Door target %s added here; target it and press action." % name.rstrip("\0"))
            elif words and words[0] == "time" and len(words) >= 2:
                self.world.clock = vana_offset(float(words[1]))
                self.change_zone(self.zone, list(self.pos))
            elif words and words[0] == "heal":
                self.restore_vitals()
                self.say("HP and MP restored.")
            elif words and words[0].casefold() == "disengage":
                if self.engaged_id:
                    self.disengage("You disengage.")
                else:
                    self.say("You are not engaged.")
            elif words and words[0] == "merits":
                max_points = self.merit_max_points()
                cap = max_points
                points = cap
                if len(words) > 1:
                    try:
                        points = int(words[1], 0)
                    except ValueError:
                        self.say("Usage: //merits [points] (0-%d)" % cap)
                        return
                points = max(0, min(cap, points))
                self.char["merit_points"] = points
                try:
                    self.world.service.set_merit_points(int(self.char["id"]), points)
                except Exception as exc:
                    log.warning("%s merit points save failed: %s", self.addr, exc)
                self.queue.append(self.merits())
                self.queue += self.merit_list()
                self.say("Merit points set to %d/%d." % (points, max_points))
                if points > 127:
                    self.say("The client's current-point field is 7-bit: it shows 127/%d, "
                             "but the extra %d points are stored and spendable." % (
                                 max_points, points - 127))
            elif words and words[0].casefold() in ("moghouse", "mh"):
                if len(words) > 1 and words[1].casefold() in ("out", "exit", "leave"):
                    self.mh_out(" ".join(words[2:]).strip())
                elif len(words) == 1 or words[1].casefold() in ("enter", "toggle"):
                    self.toggle_moghouse()
                else:
                    self.say("//mh [enter], or //mh out [name|all] to step the family out.")
                    return
            elif words and words[0].casefold() == "storage":
                self.storage_command(words[1:])
            elif words and words[0].casefold() == "locker":
                self.locker_command(words[1:])
            elif words and words[0].casefold() == "recycle":
                self.recycle_command(words[1:])
            elif words and words[0].casefold() == "item":
                self.item_command(words[1:])
            elif words and words[0].casefold() == "stock":
                self.stock_command()
            elif words and words[0] == "home":
                hz = int(self.char.get("home_zone") or 0)
                if hz <= 0:
                    self.say("You have not set a home point yet.")
                    return
                self.say("Returning to your home point in %s." % self.world.zones.name(hz))
                self.change_zone(hz, [float(self.char.get("home_x") or 0.0),
                                      float(self.char.get("home_y") or 0.0),
                                      float(self.char.get("home_z") or 0.0),
                                      int(self.char.get("home_rot") or 0)])
            elif words and words[0] == "sg":
                guides = self.world.service.survival_guides()
                if len(words) == 1:
                    cells = ["%d %s" % (int(g["idx"]), self.world.zones.name(int(g["zone"])))
                             for g in guides]
                    for offset in range(0, len(cells), 5):
                        self.say(", ".join(cells[offset:offset + 5]))
                    self.say("//sg <number> travels to that survival guide.")
                    return
                try:
                    want = int(words[1], 0)
                except ValueError:
                    self.say("//sg <number>, or //sg for the list.")
                    return
                guide = next((g for g in guides if int(g["idx"]) == want), None)
                if guide is None:
                    self.say("No survival guide with that number.")
                    return
                self.say("The survival guide sends you to %s." %
                         self.world.zones.name(int(guide["zone"])))
                self.change_zone(int(guide["zone"]), [float(guide["x"]), float(guide["y"]),
                                                      float(guide["z"]), int(guide["rot"])])
            elif words and words[0] == "warp":
                self.warp_command(words[1:])
            elif words and words[0] in ("hp", "homepoint"):
                points = self.world.service.home_points()
                if len(words) == 1:
                    # Number them by hp_index, the same number the client's Home Point
                    # menu uses.  home_points.idx is a different sequence and made
                    # "//hp 10" go somewhere other than menu entry 10.
                    cells = []
                    for point in points:
                        tag = str(point["name"]).replace("Home Point ", "HP")
                        cells.append("%d %s %s" % (int(point["hp_index"]),
                                                   self.world.zones.name(int(point["zone"])), tag))
                    for offset in range(0, len(cells), 3):
                        self.say(", ".join(cells[offset:offset + 3]))
                    self.say("//hp <menu number|zone name> warps there; //hp lists the points.")
                    return
                query = " ".join(words[1:]).strip()
                point = None
                try:
                    want = int(query, 0)
                except ValueError:
                    want = None
                if want is not None:
                    point = next((g for g in points if int(g["hp_index"]) == want), None)
                    if point is None:
                        point = next((g for g in points if int(g["idx"]) == want), None)
                else:
                    folded = query.casefold()
                    point = next((g for g in points
                                  if folded in self.world.zones.name(int(g["zone"])).casefold()), None)
                if point is None:
                    self.say("No Home Point matching %r." % query)
                    return
                # The shortcut also registers the point, like visiting the crystal does.
                if 0 <= int(point["hp_index"]) < 128:
                    self.world.service.register_home_point(self.char["id"], int(point["hp_index"]))
                self.say("Warping to %s (%s)." % (self.world.zones.name(int(point["zone"])),
                                                  point["name"]))
                self.change_zone(int(point["zone"]), [float(point["x"]), float(point["y"]),
                                                      float(point["z"]), int(point["rot"])])
            elif words and words[0] == "event" and len(words) >= 2:
                try:
                    event_id = int(words[1], 0)
                    extra = [int(w, 0) & 0xFFFFFFFF for w in words[2:10]]
                except ValueError:
                    self.say("Usage: //event <id> [p1..p8]")
                    return
                entity = self.world.entity_by_targid(self.zone, int(self.target_targid or 0))
                if entity is None or entity.kind != "npc":
                    entity = min((e for e in self.entities if e.kind == "npc"),
                                 key=lambda e: e.distance_to(*self.pos[:3]), default=None)
                if entity is None:
                    self.say("No NPC nearby.")
                    return
                params = (extra + [0] * 8)[:8]
                self.start_event(entity, event_id, params)
                self.say("Sent event %d on %s." % (event_id, entity.name))
            elif words and words[0] == "model" and len(words) >= 3:
                # Look ids are per-slot model numbers, not item ids.  The client draws the
                # main-hand and head slots straight from the look array, so this is how a
                # wrong (or missing) model gets corrected without a restart.
                want = " ".join(words[1:-1]).casefold()
                try:
                    model = int(words[-1], 0)
                except ValueError:
                    self.say("Usage: //model <item name> <model id>")
                    return
                match = self._model_item(want)
                if match is None:
                    self.say("No bag or Magic Bag item matching that name.")
                    return
                self._set_model(match["item_id"], model, match["name"])
            elif words and words[0] == "modelnext" and len(words) >= 2:
                # Sweep the look ids one call at a time: //modelnext <item> walks from the
                # current id upward (starting at 951 when the item has no model), so a
                # renamed/unknown block can be found by eye without retyping a command.
                want = " ".join(words[1:]).casefold()
                match = self._model_item(want)
                if match is None:
                    self.say("No bag or Magic Bag item matching that name.")
                    return
                item = self.world.service.item(int(match["item_id"])) or {}
                current = int(item.get("model") or 0)
                nxt = current + 1 if 900 <= current < 1200 else 951
                self._set_model(match["item_id"], nxt, match["name"])
            elif words and words[0] in ("r30", "odyssey"):
                from . import limbus, odyssey
                query = " ".join(words[1:]).strip()
                if not query:
                    names = [entry["name"] for entry in odyssey.entries()]
                    names += [entry["name"] for entry in limbus.all_entries()]
                    for offset in range(0, len(names), 3):
                        self.say(", ".join(names[offset:offset + 3]))
                    self.say("//r30 <item> prints its Rank 30 rows (Odyssey or Limbus).")
                    return
                matches = odyssey.find(query) or limbus.find(query)
                if not matches:
                    self.say("No Rank 30 item matches %r." % query)
                    return
                for entry in matches[:2]:
                    bundle = entry.get("bundles") or {}
                    extra = ""
                    if bundle:
                        extra = " | bundles A-%s" % "/".join(
                            "%d" % bundle[p] for p in "ABCD" if p in bundle)
                    elif entry.get("bundle"):
                        extra = " | bundle %d" % int(entry["bundle"])
                    self.say("%s (item %d, %s%s)" % (entry["name"], entry["id"], entry["set"], extra))
                    for path, rows in entry["paths"].items():
                        self.say("%s: %s" % (path, " | ".join(rows)))
            elif words and words[0].casefold() == "rp30":
                from . import limbus
                blocks = limbus.blocks()
                found = changed = 0
                containers = set()
                for item in self.world.service.inventory(self.char["id"]):
                    block = blocks.get(int(item["item_id"]))
                    if block is None:
                        continue
                    found += 1
                    if bytes(item.get("extra") or b"") == block:
                        continue
                    if self.world.service.set_item_extra(
                            int(self.char["id"]), int(item["container"]),
                            int(item["slot"]), block):
                        changed += 1
                        containers.add(int(item["container"]))
                for container in sorted(containers):
                    self.queue += self.container_items(container)
                if containers:
                    self.queue.append(self.container_sync())
                self.say("Limbus: %d piece(s) carried, %d re-stamped to Rank 30 "
                         "(55,800 RP, bundle indexed)." % (found, changed))
            elif words and words[0] == "augment":
                from . import limbus, unity
                from .augments import bundle as augment_bundle, describe
                from .odyssey import bundle_for
                if len(words) < 2 or words[1].lower() in ("list", "unity"):
                    # The catalogue is the whole Unity set now (108 pieces), so
                    # "//augment list <text>" narrows it instead of flooding chat.
                    needle = " ".join(words[2:]).casefold() if len(words) > 2 else ""
                    shown = 0
                    for item_id, entry in unity.ITEMS.items():
                        if needle and needle not in str(entry["name"]).casefold():
                            continue
                        shown += 1
                        self.say("%s (item %d, bundle %d): %s" % (
                            entry["name"], item_id, entry["bundle"],
                            " / ".join(entry["augments"])))
                    if not shown:
                        self.say("No Unity piece matches %r." % needle)
                    elif needle:
                        self.say("%d Unity piece(s) matching %r." % (shown, needle))
                    else:
                        self.say("%d Unity pieces; //augment list <text> filters them."
                                 % shown)
                    self.say("//augment A <item> rewrites a Unity or Odyssey bundle; "
                             "//augment <index|off> <item> sets or clears one.")
                    return
                if len(words) < 3:
                    self.say("Usage: //augment <A-D|index|off> <item>")
                    return
                mode = words[1].upper()
                want = " ".join(words[2:]).casefold()
                match = next((i for i in self.world.service.inventory(self.char["id"])
                              if want in str(i.get("name") or "").casefold()), None)
                if match is None:
                    self.say("No inventory item matching that name.")
                    return
                unity_entry = unity.get(int(match["item_id"]))
                if mode == "OFF":
                    extra = b""
                elif unity_entry is not None:
                    if mode.isdigit():
                        extra = unity.encode(index=int(mode))
                    elif mode == "A":
                        extra = unity.encode(int(match["item_id"]))
                    else:
                        self.say("%s has one Unity path (A); use //augment A <item>."
                                 % unity_entry["name"])
                        return
                elif mode.isdigit():
                    limb = limbus.get(int(match["item_id"]))
                    if (limb is not None and limb.get("bundle") is not None
                            and int(mode) == int(limb["bundle"])):
                        extra = limbus.extra(limb)
                    else:
                        extra = augment_bundle("A", 30, 3, int(mode))
                else:
                    limb = limbus.get(int(match["item_id"]))
                    if limb is not None and limb.get("bundle") is not None:
                        extra = limbus.extra(limb)
                    else:
                        index = bundle_for(str(match.get("name") or ""), mode)
                        if index is None:
                            self.say("No known Rank 30 bundle for %s." % match["name"])
                            return
                        extra = augment_bundle("A", 30, 3, index)
                self.world.service.set_item_extra(
                    int(self.char["id"]), int(match["container"]), int(match["slot"]), extra)
                self.queue += self.container_items(int(match["container"]))
                self.queue.append(self.container_sync())
                self.say("%s: %s." % (match["name"], describe(extra)))
            elif words and words[0] == "cape":
                from . import capes as cape_lib
                if len(words) < 2 or words[1].lower() == "list":
                    for job, entry in cape_lib.JOBS.items():
                        names = ", ".join(entry["builds"])
                        self.say("%s %s: %s" % (job, entry["cape_name"], names))
                    self.say("//cape <build|off> <item> re-encodes a cape.")
                    return
                if len(words) < 3:
                    self.say("Usage: //cape <build|off> <item>")
                    return
                mode = words[1].lower()
                want = " ".join(words[2:]).casefold()
                match = next((i for i in self.world.service.inventory(self.char["id"])
                              if want in str(i.get("name") or "").casefold()), None)
                if match is None:
                    self.say("No inventory item matching that name.")
                    return
                job = (cape_lib.job_for_item(int(match["item_id"]))
                       or cape_lib.job_for_name(str(match.get("name") or "")))
                if job is None:
                    self.say("%s is not an Ambuscade job cape." % match["name"])
                    return
                if mode in ("off", "none"):
                    extra = b""
                elif mode in cape_lib.JOBS[job]["builds"]:
                    extra = cape_lib.encode(mode, job)
                else:
                    self.say("Unknown %s cape build %r; try //cape list." % (job, words[1]))
                    return
                self.world.service.set_item_extra(
                    int(self.char["id"]), int(match["container"]), int(match["slot"]), extra)
                self.queue += self.container_items(int(match["container"]))
                self.queue.append(self.container_sync())
                self.say("%s: %s." % (match["name"], cape_lib.describe(extra)))
            elif words and words[0] == "equip" and len(words) >= 2:
                want = " ".join(words[1:]).casefold()
                match = None
                for item in self.world.service.inventory(self.char["id"]):
                    if int(item["container"]) != 0:
                        continue
                    if want in str(item.get("name") or "").casefold():
                        match = item
                        break
                if match is None:
                    self.say("No inventory item matching that name.")
                    return
                kind = EQUIP_SLOTS.get(str(match.get("equip_slot") or ""))
                if kind is None:
                    self.say("That item has no equipment slot.")
                    return
                problem = (self._equip_blocked_reason(match, kind)
                           or self._weapon_pair_error(match, kind))
                if problem:
                    self.say(problem)
                    return
                slot = int(match["slot"])
                item_id = int(match["item_id"])
                self.equipped[kind] = (0, slot, item_id)
                self._apply_equip_model(kind, match)
                if kind == 0:
                    self._enforce_weapon_pair()
                self.store_equipment()
                self.queue += [
                    sub(0x050, struct.pack("<BBBx", slot, kind, 0)),
                    self.grap_list(),
                    self.item_packet(match, container=0, slot=slot),
                    # The dev command skips flush_equipment(), so refresh the command
                    # bitmap itself: a Prime weapon's granted skill must appear here.
                    self.char_abilities(), self.char_commands(),
                    self.char_stats(), self.char_status(),
                ]
                self.refresh_vitals()
                log.info("%s //equip %s slot=%d kind=%d", self.addr, match["name"], slot, kind)
                self.say("Equipped %s." % match["name"])
            elif words and words[0] == "unequip" and len(words) >= 2:
                kind = EQUIP_SLOTS.get(words[1].casefold())
                if kind is None or kind not in self.equipped:
                    self.say("Nothing is equipped in that slot.")
                    return
                self.equipped.pop(kind, None)
                self._clear_equip_model(kind)
                if kind == 0:
                    self._enforce_weapon_pair()
                self.refresh_vitals()
                self.store_equipment()
                self.queue += [
                    sub(0x050, struct.pack("<BBBx", 0, kind, 0)),
                    self.grap_list(),
                    sub(0x0AA, self.spell_bits()),
                    self.char_abilities(),
                ]
                log.info("%s //unequip kind=%d", self.addr, kind)
                self.say("Unequipped that slot.")
            elif words and words[0] == "ws" and len(words) >= 2:
                wanted = " ".join(words[1:]).strip("\"'")
                ws = self.world.service.weaponskill_by_name(wanted)
                if ws is None:
                    self.say("No weapon skill called %s." % wanted)
                else:
                    buf = bytearray(16)
                    struct.pack_into("<IHH", buf, 0, int(self.char["char_id"]), 0,
                                     packets.ACTION_WEAPONSKILL)
                    struct.pack_into("<I", buf, 12, int(ws["id"]))
                    self.weaponskill(bytes(buf), int(self.engaged_targid or 0))
            elif words and words[0] == "ja" and len(words) >= 2:
                wanted = " ".join(words[1:]).strip("\"'")
                ability = self.world.service.job_ability_by_name(wanted)
                if ability is None and wanted.isdigit():
                    ability = self.world.service.job_ability(int(wanted))
                if ability is None:
                    self.say("No job ability called %s." % wanted)
                else:
                    buf = bytearray(16)
                    struct.pack_into("<IHH", buf, 0, int(self.char["char_id"]), 0,
                                     packets.ACTION_JOBABILITY)
                    struct.pack_into("<I", buf, 12, int(ability["id"]))
                    self.job_ability(bytes(buf), int(self.engaged_targid or 0))
            elif words and words[0] == "abilities":
                # Re-send the command bitmap on demand.  The Abilities menu is built from
                # 0x0AC, and a client that cached an empty one (older builds, a job change
                # while disconnected) accepts no menu entries until it sees a fresh copy.
                self.queue += [self.job_info(), self.char_feats(), self.char_abilities(),
                               self.char_commands(), self.char_skills(),
                               self.abil_recast()]
                self.say("Abilities refreshed.")
            elif words and words[0] == "traits":
                # The passive traits of the current job pair.  This is also a diagnostic
                # for the 0x0AC trait block: if a trait is listed here but the client's
                # menu does not show it, the bitmap is the part to look at.
                known = self.job_traits()
                if not known:
                    self.say("No job traits at your current job levels.")
                else:
                    for trait in known:
                        self.say(trait.describe())
                # The passive tick is trait modifiers *plus gear* (Chirich Ring +1's
                # Regen, Karieyh Ring +1's Regain, ...), so report the merged total even
                # for a job pair with no Auto Regen/Auto Refresh trait.  Reading
                # trait_mods() here used to hide every gear-only tick.
                all_mods = self.combat_mods()
                regen = max(0, int(all_mods.get(mod.REGEN, 0))
                            - int(all_mods.get(mod.REGEN_DOWN, 0)))
                refresh = max(0, int(all_mods.get(mod.REFRESH, 0))
                              - int(all_mods.get(mod.REFRESH_DOWN, 0)))
                regain = max(0, int(all_mods.get(mod.REGAIN, 0)))
                parts = []
                if regen:
                    parts.append("Regen %d HP" % regen)
                if refresh:
                    parts.append("Refresh %d MP" % refresh)
                if regain:
                    parts.append("Regain %d TP" % regain)
                if parts:
                    self.say("Passive tick: %s every 3s (traits and gear)."
                             % ", ".join(parts))
                self.queue += [self.char_abilities(), self.char_commands()]
            elif words and words[0] == "job" and len(words) >= 2:
                self.job_command(words)
            elif words and words[0] == "trust":
                self.trust_command(words[1:])
            elif words and words[0].casefold() == "makeparty":
                self.makeparty_command(words[1:])
            elif words and words[0].casefold() == "invite":
                self.invite_command(words[1:])
            elif words and words[0] == "cast" and len(words) >= 2:
                wanted = " ".join(words[1:])
                spell = self.world.service.spell_by_name(wanted)
                if spell is None and wanted.isdigit():
                    spell = self.world.service.spell(int(wanted))
                if spell is None:
                    self.say("No spell called %s." % wanted)
                else:
                    packet = bytearray(16)
                    struct.pack_into("<IHHI", packet, 4, int(self.engaged_id or 0),
                                     int(self.target_targid or 0), packets.ACTION_CAST_MAGIC,
                                     int(spell["id"]))
                    self.cast_magic(bytes(packet), int(self.target_targid or 0))
            elif words and words[0] == "entities":
                names = ", ".join("%s (%#x)" % (e.name, e.targid) for e in self.entities) or "none"
                self.say("Entities here: " + names)
            elif words and words[0] == "help":
                for line in commands:
                    self.say(line)
            else:
                for line in commands:
                    self.say(line)
        except ValueError:
            self.say("numbers, please")

    # --- //warp --------------------------------------------------------------------------------
    def warp_command(self, words: list[str]) -> None:
        """Save and return to a character's own places.

        ``//warp mark [alias]`` stores the current zone and position under the next number.
        ``me`` and ``all`` take a number or alias; ``all`` moves every online character in
        the account family (the main account plus its sub-accounts), which is the multibox
        group.  ``//warp all me`` is the other direction: it calls every other online
        character in that family to the sender's current zone and position; ``//warp call
        <name>`` calls just one of them, which is what the launcher sends when a box comes
        back from a relog.  The launcher's Warps page edits the same rows and has a button
        for the same call, so names set there work here.
        """
        service = self.world.service
        cid = int(self.char["id"])
        action = words[0].casefold() if words else "list"
        if not words or action in ("list", "ls"):
            page = 1
            if len(words) > 1:
                try:
                    page = max(1, int(words[1], 0))
                except ValueError:
                    self.say("Usage: //warp list [page]")
                    return
            self._warp_list(cid, page)
            return
        if action == "mark":
            alias = " ".join(words[1:]).strip()
            try:
                warp = service.mark_warp(cid, alias or None, self.zone, list(self.pos))
            except Exception as exc:
                self.say("Warp mark failed: %s" % exc)
                return
            label = warp["alias"] or warp["zone_name"]
            self.say("Warp %d marked: %s (%s) at %.1f, %.1f, %.1f." % (
                warp["slot"], label, warp["zone_name"], warp["x"], warp["y"], warp["z"]))
            if not warp["alias"]:
                self.say("Name it later with //warp rename %d <name> or the launcher's Warps page."
                         % warp["slot"])
            return
        if action in ("delete", "remove", "del"):
            reference = " ".join(words[1:]).strip()
            warp = self._warp_reference(cid, reference)
            if warp is None:
                return
            try:
                service.delete_warp(cid, warp["slot"])
            except Exception as exc:
                self.say("Warp delete failed: %s" % exc)
                return
            self.say("Warp %d (%s) deleted." % (
                warp["slot"], warp["alias"] or warp["zone_name"]))
            return
        if action == "rename":
            if len(words) < 3:
                self.say("Usage: //warp rename <number> <new alias>")
                return
            warp = self._warp_reference(cid, words[1])
            if warp is None:
                return
            alias = " ".join(words[2:]).strip()
            try:
                warp = service.rename_warp(cid, warp["slot"], alias)
            except Exception as exc:
                self.say("Warp rename failed: %s" % exc)
                return
            self.say("Warp %d renamed to %s." % (
                warp["slot"], warp["alias"] or "(no alias)"))
            return
        if action in ("help", "?"):
            self.say("//warp mark [alias] | me <n|alias> | all <n|alias> | all me | "
                     "call <name|all> | list [page] | delete <n|alias> | rename <n> <alias>")
            return
        if action in ("call", "bring", "summon"):
            self._warp_call(" ".join(words[1:]).strip())
            return
        if action in ("all", "everyone", "party"):
            who = "all"
            reference = " ".join(words[1:]).strip()
            if reference.casefold() in ("me", "here", "self"):
                self._warp_group_to_me()
                return
        elif action in ("me", "self"):
            who = "me"
            reference = " ".join(words[1:]).strip()
        else:
            who = "me"
            reference = " ".join(words).strip()
        warp = self._warp_reference(cid, reference)
        if warp is not None:
            self._warp_to(warp, who)

    def _warp_reference(self, character_id: int, reference: str):
        if not reference:
            self.say("Which warp? Use //warp list.")
            return None
        try:
            matches = self.world.service.find_warps(character_id, reference)
        except Exception as exc:
            self.say("Warp lookup failed: %s" % exc)
            return None
        if not matches:
            self.say("No warp matches %r. Use //warp list." % reference)
            return None
        if len(matches) > 1:
            cells = ["%d %s" % (warp["slot"], warp["alias"] or warp["zone_name"])
                     for warp in matches[:6]]
            self.say("Several warps match %r: %s. Use the number." % (
                reference, ", ".join(cells)))
            return None
        return matches[0]

    def _warp_list(self, character_id: int, page: int) -> None:
        warps = self.world.service.warps_for_character(character_id)
        if not warps:
            self.say("No warps marked. Stand where you want to return and type //warp mark [alias].")
            return
        pages = max(1, (len(warps) + WARP_PAGE_SIZE - 1) // WARP_PAGE_SIZE)
        page = max(1, min(pages, page))
        start = (page - 1) * WARP_PAGE_SIZE
        self.say("Warps %d-%d of %d (slots 1-%d):" % (
            start + 1, min(len(warps), start + WARP_PAGE_SIZE), len(warps), WARP_SLOT_MAX))
        for warp in warps[start:start + WARP_PAGE_SIZE]:
            self.say("%d. %s - %s (%.1f, %.1f, %.1f)" % (
                warp["slot"], warp["alias"] or "(no alias)", warp["zone_name"],
                warp["x"], warp["y"], warp["z"]))
        if pages > 1:
            self.say("Page %d/%d. //warp list %d for more." % (
                page, pages, min(pages, page + 1)))
        self.say("//warp me <number|alias> or //warp all <number|alias>; "
                 "//warp all me calls the team to you; "
                 "the launcher's Warps page renames them.")

    def _family_sessions(self) -> list["ZoneSession"]:
        """The sender plus every online session in the account family (main plus subs).

        Parked boxes are left out on purpose: ``//sleep`` hands the client no packets but
        chat, so a zone-in or a position update sent to one is dropped on the floor and
        would leave it ``zoning`` for good.  Wake it first, then warp.
        """
        family = self.world.service.account_family_ids(
            int(self.char.get("account_id") or 0))
        targets = []
        for session in list(self.world.sessions.values()):
            if session is self:
                targets.append(session)
                continue
            if not getattr(session, "logged_in", False) or getattr(session, "zoning", False):
                continue
            if getattr(session, "gone", False) or not getattr(session, "key", None):
                continue
            if getattr(session, "sleeping", False):
                continue
            if int(session.char.get("account_id") or 0) not in family:
                continue
            targets.append(session)
        return targets

    def _warp_anchor(self) -> tuple[int, list[float]]:
        """This character's zone and position, ready to hand to another session."""
        zone = int(self.zone)
        pos = [float(v) for v in self.pos[:3]]
        pos.append(int(self.pos[3]) if len(self.pos) > 3 else 0)
        return zone, pos

    def _warp_group_to_me(self) -> None:
        """//warp all me: call the other online family characters to this character.

        The sender already stands here, so it is left alone; reloading its own zone would
        only make the leader blink out for the rest of the group.  Every other session in
        the account family zoned in at the sender's exact zone and position.
        """
        if self.char.get("moghouse"):
            self.say("You are in your Mog House. Use //mh out to bring the family out, "
                     "then leave and warp from outside.")
            return
        zone, pos = self._warp_anchor()
        zone_label = self.world.zones.name(zone)
        # Remember the anchor before checking who is online: a box whose client is still
        # logging in is absent from _family_sessions() and must join when it finishes.
        self.world.set_team_anchor(self, zone, pos)
        targets = [session for session in self._family_sessions() if session is not self]
        if not targets:
            self.say("No other characters in your team are online; they will join you "
                     "when they finish logging in.")
            return
        name = self.char.get("name") or "A party member"
        if len(targets) == 1:
            # Always a zone hand-off, even in the same zone: the client treats its own
            # position as authoritative and ignores a server 0x00D for targid 0x400, so a
            # same-zone position update left every box standing where it was.
            target = targets[0]
            target.say("%s warps you to their side in %s." % (name, zone_label))
            target.change_zone(zone, pos, follow_family=False)
        else:
            # Every box gets its own 0x00B in the same tick.  Five boxes measured 4.5 s
            # from command to all-in-world this way; a first-load gate was slower (11.8 s)
            # because it serialized a load the clients can overlap.
            self.world.queue_warps(self, targets, zone, pos)
        moved = len(targets)
        self.say("Warped %d character%s to you in %s." % (
            moved, "" if moved == 1 else "s", zone_label))

    def _warp_call(self, name: str) -> None:
        """//warp call <name>: bring one online family character to this one.

        ``//warp all me`` is the whole team at once; this is the single-target form the
        launcher uses when a box comes back from a relog and has to be pulled to the
        leader.  The name is resolved on the server (``session_by_name``), so a box in
        another zone -- or one whose client has not drawn the leader yet -- still answers.
        """
        if not name:
            self.say("Usage: //warp call <character> (//warp call all for the whole team).")
            return
        if name.casefold() in ("all", "everyone", "team", "subs"):
            self._warp_group_to_me()
            return
        target = self.world.session_by_name(name)
        if target is None:
            self.say("No character called %s is online." % name)
            return
        if getattr(target, "sleeping", False):
            self.say("%s is asleep; //wake it first." % (target.char.get("name") or name))
            return
        if target is self:
            self.say("That is you.")
            return
        if self.char.get("moghouse"):
            self.say("You are in your Mog House. Use //mh out to bring the family out, "
                     "then leave and warp from outside.")
            return
        family = self.world.service.account_family_ids(
            int(self.char.get("account_id") or 0))
        if int(target.char.get("account_id") or 0) not in family:
            self.say("%s is not on your account or a sub-account." % (
                target.char.get("name") or name))
            return
        zone, pos = self._warp_anchor()
        zone_label = self.world.zones.name(zone)
        # The launcher's auto-pull can arrive before the box's first position packet, when
        # the ordinary "already there" test inside change_zone cannot see the client's
        # spot yet.  A second call that hands the box the same anchor it was just given
        # only reloads it -- the re-zone loop every fifteen seconds that kept a box out of
        # the world.  A deliberate call somewhere else, or to a box that was not just
        # handed this spot, still goes through.
        last = target.warped_to
        if (last is not None and int(last[0]) == int(zone)
                and time.time() - float(last[2]) < WARP_REPEAT_GUARD
                and target.already_at(zone, pos)):
            self.say("%s is already with you in %s." % (
                target.char.get("name") or name, zone_label))
            return
        target.say("%s calls you to their side in %s." % (
            self.char.get("name") or "A party member", zone_label))
        target.change_zone(zone, pos, follow_family=False)
        target.warped_to = (int(zone), list(pos), time.time())
        self.say("Called %s to you in %s." % (
            target.char.get("name") or name, zone_label))

    def _warp_to(self, warp: dict, who: str) -> None:
        zone = int(warp["zone"])
        pos = [float(warp["x"]), float(warp["y"]), float(warp["z"]), int(warp["rot"])]
        label = warp["alias"] or warp["zone_name"]
        zone_label = self.world.zones.name(zone)
        if who != "all":
            self.say("Warping to %s (%s)." % (label, zone_label))
            self.change_zone(zone, pos)
            return
        targets = self._family_sessions()
        moved = 0
        for target in targets:
            if target is not self:
                target.say("%s warps the group to %s (%s)." % (
                    self.char.get("name") or "A party member", label, zone_label))
            target.change_zone(zone, pos, follow_family=False)
            moved += 1
        if moved <= 1:
            self.say("Warped to %s (%s); no other characters in your family were online." % (
                label, zone_label))
        else:
            self.say("Warped %d characters to %s (%s)." % (moved, label, zone_label))

    def character_command(self, words: list[str]) -> None:
        """//character model: change race, face, hair colour and size.

        The 48 designs of a race are numbered with size fastest, so Hume 8 is
        Face 2 / Hair A / Medium.  ``random`` picks face, hair and size (and the
        race too when no race is named); ``face 2 hair a size m`` is the detailed
        form the launcher also uses.
        """
        usage = ("Usage: //character model <race> <1-%d|random>  "
                 "(races: hume, humef, elvaan, elvaanf, tarutaru, tarutaruf, mithra, galka)"
                 % character_design.VARIANTS_PER_RACE)
        current = character_design.from_row(self.char)
        if not words or words[0].casefold() != "model":
            self.say("Design: %s (variant %d/%d). %s" % (
                current["label"], current["variant"], current["variants"], usage))
            return
        args = words[1:]
        if not args:
            self.say("Design: %s (variant %d/%d). %s" % (
                current["label"], current["variant"], current["variants"], usage))
            return
        try:
            head = args[0].casefold()
            chosen = None
            rest = args
            if head == "random":
                rest = args[1:]
            else:
                try:
                    chosen = character_design.race(args[0])
                    rest = args[1:]
                except character_design.DesignError:
                    # No race: a variant or face/hair/size keeps the current race.
                    chosen = character_design.race(current["race"])
            if chosen is None and rest and rest[0].casefold() != "random":
                # `random` followed by explicit detail still has to name a race
                # for the detail to apply to; use the character's current one.
                chosen = character_design.race(current["race"])
            if not rest or rest[0].casefold() == "random":
                blueprint = character_design.random_design(chosen, self.world.rng)
            elif rest[0].casefold() in ("face", "hair", "size"):
                values = {"face": current["face"], "hair": current["hair"],
                          "size": current["size"]}
                index = 0
                while index < len(rest):
                    key = rest[index].casefold()
                    if key not in values or index + 1 >= len(rest):
                        raise character_design.DesignError(usage)
                    if key == "face":
                        values["face"] = character_design.parse_face(rest[index + 1])
                    elif key == "hair":
                        values["hair"] = character_design.parse_hair(rest[index + 1])
                    else:
                        values["size"] = character_design.parse_size(rest[index + 1])
                    index += 2
                blueprint = character_design.design(
                    chosen, values["face"], values["hair"], values["size"])
            else:
                variant = int(rest[0], 0)
                blueprint = character_design.design_from_variant(chosen, variant)
        except character_design.DesignError as exc:
            self.say(str(exc))
            self.say(usage)
            return
        except (ValueError, IndexError):
            self.say(usage)
            return
        try:
            self.world.service.save_design(int(self.char["id"]), blueprint)
        except Exception as exc:
            log.warning("%s design save failed: %s", self.addr, exc)
            self.say("Could not save the design: %s" % exc)
            return
        # The service's design listener normally repaints every live session.  A
        # test or a tool without the gateway gets the same update from here.
        if any(int(self.char.get(key, -1)) != blueprint[key]
               for key in ("race", "face", "hair", "size")):
            self.apply_design(blueprint)
        self.say("%s is now %s (variant %d/%d)." % (
            self.char.get("name", "This character"), blueprint["label"],
            blueprint["variant"], blueprint["variants"]))

    def storage_command(self, words: list[str]) -> None:
        """//storage organize | store <job|all> | grab <job|all> | list [job|all].

        ``organize`` is the job-aware swap: everything the current job cannot equip
        leaves the bags (a slip when the item has one, the 9,999 locker when it does
        not), and everything the job can equip comes back into the Mog Wardrobes.
        ``store all`` is the first half on its own, and ``grab <job>`` is the second
        half for one job.  To the player the slips and the locker are one storage; the
        client's 80-slot Storage bag is not used, so the 9999 limit is the real one.
        """
        usage = ("Usage: //storage organize | store <job|all> | grab <job|all> | "
                 "list [job|all]")
        if not words:
            self._storage_status()
            return
        action = words[0].casefold()
        character_id = int(self.char["id"])
        current_job = int(self.char.get("main_job") or 1)
        if action in ("organize", "tidy"):
            result = self._organize_storage(current_job)
            if result is None:
                return
            self._queue_storage_moves(result)
            self._report_organize(result, current_job)
            log.info("%s //storage organize %s -> stored %d, pulled %d, tidied %d",
                     self.addr, JOB_ABBREVIATIONS[current_job],
                     result["stored_total"], result["pulled_total"],
                     len(result["relocated"]))
            return
        if action == "store":
            wanted = " ".join(words[1:]).strip()
            if not wanted:
                self.say(usage)
                return
            if wanted.casefold() in ("all", "everything", "*"):
                result = self._organize_storage(
                    current_job, pull=False, relocate=False)
                if result is None:
                    return
                self._queue_storage_moves(result)
                self._report_store(result, current_job, everything=True)
                return
            job = job_id(wanted)
            if job is None:
                self.say("Unknown job %r. Try NIN, Ninja, 13 or all." % wanted)
                return
            result = self._organize_storage(
                job, scope="exclusive", pull=False, relocate=False)
            if result is None:
                return
            self._queue_storage_moves(result)
            self._report_store(result, job, everything=False)
            return
        if action == "grab":
            wanted = " ".join(words[1:]).strip()
            if not wanted or wanted.casefold() in ("all", "everything", "*"):
                self._grab_everything(character_id)
                return
            job = job_id(wanted)
            if job is None:
                self.say("Unknown job %r. Try NIN, Ninja, 13 or all." % wanted)
                return
            result = self._organize_storage(
                job, scope="exclusive", store=False, pull=True, relocate=True)
            if result is None:
                return
            self._queue_storage_moves(result)
            self._report_pull(result, job)
            return
        if action == "list":
            self._storage_list(words[1:])
            return
        self.say(usage)

    def _organize_storage(self, job: int, **kwargs) -> dict | None:
        """Run the organizer and report a database failure instead of dropping the command."""
        try:
            return self.world.service.organize_job_storage(
                int(self.char["id"]), int(job), **kwargs)
        except Exception as exc:
            log.warning("%s storage organize failed: %s", self.addr, exc)
            self.say("Could not organize the storage: %s" % exc)
            return None

    def _grab_everything(self, character_id: int) -> None:
        """//storage grab all: empty both stores, the old slip/locker behaviour."""
        slips = self.world.service.take_from_storage(character_id, None)
        locker = self.world.service.take_from_locker(character_id, {"kind": "all"})
        self._queue_storage_returns(list(slips["moved"]) + list(locker["moved"]))
        count = (sum(int(move["quantity"]) for move in slips["moved"])
                 + sum(int(move["quantity"]) for move in locker["moved"]))
        if count:
            self.say("Took %d item%s out of the slips and the locker (%d slip, %d locker)." % (
                count, "" if count == 1 else "s",
                int(slips["storage_count"]), int(locker["locker_items"])))
        else:
            self.say("The storage is empty.")
        log.info("%s //storage grab all -> %d items, %d slip / %d locker items left",
                 self.addr, count, int(slips["storage_count"]),
                 int(locker["locker_items"]))

    def _storage_list(self, words: list[str]) -> None:
        """//storage list [job|all]: what is in the slips and locker, grouped by job."""
        wanted = " ".join(words).strip()
        character_id = int(self.char["id"])
        if wanted.casefold() in ("all", "everything", "*"):
            counts = self.world.service.storage_job_counts(character_id)
            cells = ["%s %d" % (JOB_ABBREVIATIONS[job], counts["jobs"][job])
                     for job in range(1, 23) if counts["jobs"][job]]
            if counts["shared"]:
                cells.append("shared %d" % counts["shared"])
            if not cells:
                self.say("No equipment is stored; //locker list shows ammo, materials and jugs.")
                return
            for offset in range(0, len(cells), 6):
                self.say(", ".join(cells[offset:offset + 6]))
            return
        if wanted:
            job = job_id(wanted)
            if job is None:
                self.say("Unknown job %r. Try NIN, Ninja, 13 or all." % wanted)
                return
        else:
            job = int(self.char.get("main_job") or 1)
        entries = self.world.service.storage_contents(character_id, job)
        label = JOB_ABBREVIATIONS[job]
        if not entries:
            self.say("No %s gear in the slips or the locker." % label)
            return
        cells = []
        for entry in entries:
            item_id = int(entry["item_id"])
            text = "%s x%d [%s]" % (
                entry["name"], int(entry["quantity"]),
                "slip" if entry["source"] == "slip" else "locker")
            if entry["source"] == "locker" and capes.job_for_item(item_id):
                try:
                    text += " [%s]" % capes.describe(bytes(entry["extra"] or b""))
                except ValueError:
                    pass
            cells.append(text)
        limit = 24
        for offset in range(0, min(len(cells), limit), 2):
            self.say(", ".join(cells[offset:offset + 2]))
        if len(cells) > limit:
            self.say("... and %d more." % (len(cells) - limit))

    @staticmethod
    def _move_parts(result: dict, direction: str) -> str:
        """``12 on slips, 3 in the locker`` for one direction of a move summary."""
        slip = int(result.get(direction + "_slip") or 0)
        locker = int(result.get(direction + "_locker") or 0)
        parts = []
        if slip:
            parts.append("%d on slips" % slip)
        if locker:
            parts.append("%d in the locker" % locker)
        return ", ".join(parts)

    def _report_store(self, result: dict, job: int, *, everything: bool) -> None:
        label = JOB_ABBREVIATIONS.get(int(job), str(job))
        total = int(result["stored_total"])
        if total:
            parts = self._move_parts(result, "stored")
            if everything:
                self.say("Stored %d item%s you cannot equip as %s (%s)." % (
                    total, "" if total == 1 else "s", label, parts))
            else:
                self.say("Stored %d %s item%s (%s)." % (
                    total, label, "" if total == 1 else "s", parts))
        elif not result["locker_full"]:
            self.say("Nothing in your bags is waiting for storage." if everything
                     else "No %s gear left in your bags." % label)
        if result["locker_full"]:
            self.say("%d item%s stayed: the locker is full." % (
                result["locker_full"], "" if result["locker_full"] == 1 else "s"))
        if result["equipped"]:
            self.say("Left %d equipped piece%s on." % (
                result["equipped"], "" if result["equipped"] == 1 else "s"))

    def _report_pull(self, result: dict, job: int) -> None:
        label = JOB_ABBREVIATIONS.get(int(job), str(job))
        total = int(result["pulled_total"])
        if total:
            self.say("Pulled %d %s item%s into the wardrobes (%s)." % (
                total, label, "" if total == 1 else "s",
                self._move_parts(result, "pulled")))
        elif not result["remaining"]:
            self.say("No %s gear was in the slips or the locker." % label)
        if result["relocated"]:
            self.say("Tidied %d %s item%s from the inventory into the wardrobes." % (
                len(result["relocated"]), label,
                "" if len(result["relocated"]) == 1 else "s"))
        if result["remaining"]:
            self.say("%d item%s stayed in storage: the wardrobes and inventory are full." % (
                result["remaining"], "" if result["remaining"] == 1 else "s"))
        if total:
            self.say("Wardrobes: %d free slot%s." % (
                result["free"], "" if result["free"] == 1 else "s"))

    def _report_organize(self, result: dict, job: int) -> None:
        label = JOB_ABBREVIATIONS.get(int(job), str(job))
        if result["stored_total"]:
            self.say("Stored %d item%s %s cannot equip (%s)." % (
                result["stored_total"], "" if result["stored_total"] == 1 else "s",
                label, self._move_parts(result, "stored")))
        if result["pulled_total"]:
            self.say("Pulled %d %s item%s into the wardrobes (%s)." % (
                result["pulled_total"], label,
                "" if result["pulled_total"] == 1 else "s",
                self._move_parts(result, "pulled")))
        if result["relocated"]:
            self.say("Tidied %d %s item%s into the wardrobes." % (
                len(result["relocated"]), label,
                "" if len(result["relocated"]) == 1 else "s"))
        if not (result["stored_total"] or result["pulled_total"] or result["relocated"]):
            self.say("The bags already match %s." % label)
        if result["locker_full"]:
            self.say("%d item%s stayed: the locker is full." % (
                result["locker_full"], "" if result["locker_full"] == 1 else "s"))
        if result["remaining"]:
            self.say("%d item%s stayed in storage: the wardrobes and inventory are full." % (
                result["remaining"], "" if result["remaining"] == 1 else "s"))
        if result["equipped"]:
            self.say("Left %d equipped piece%s on." % (
                result["equipped"], "" if result["equipped"] == 1 else "s"))
        self.say("Wardrobes: %d free slot%s; locker: %d/%d slots." % (
            result["free"], "" if result["free"] == 1 else "s",
            result["locker_count"], result["locker_capacity"]))

    def _queue_storage_moves(self, result: dict) -> None:
        """Repaint every bag slot the organizer changed.

        A Mog Wardrobe cannot be updated by a bare 0x020: the client files rows into a
        storage's item list only while that container's load window is open, so without
        a state-0 0x01D first the equipment window keeps the previous wardrobe's list
        and looks empty (or shows the last bag it had).  Every affected wardrobe is
        therefore reopened and sent in full; non-wardrobe bags still use the lighter
        clear/write pair.  All clears go before the writes so a reused slot never draws
        the new item before the old one leaves.
        """
        clears: set[tuple[int, int]] = set()
        writes: list[dict] = []
        wardrobes: set[int] = set()
        for move in result.get("stored", []):
            container = int(move["from_container"])
            clears.add((container, int(move["from_slot"])))
            if container in WARDROBE_CONTAINERS:
                wardrobes.add(container)
        for move in result.get("relocated", []):
            source = int(move["from_container"])
            target = int(move["to_container"])
            clears.add((source, int(move["from_slot"])))
            if source in WARDROBE_CONTAINERS:
                wardrobes.add(source)
            if target in WARDROBE_CONTAINERS:
                wardrobes.add(target)
            else:
                writes.append(move)
        for move in result.get("pulled", []):
            target = int(move["to_container"])
            if target in WARDROBE_CONTAINERS:
                wardrobes.add(target)
            else:
                writes.append(move)
        if not clears and not writes and not wardrobes:
            return
        items = self.world.service.inventory(int(self.char["id"]))
        present = {(int(item["container"]), int(item["slot"])) for item in items}
        # Non-wardrobe sources first: a slot can be emptied here and filled by a write.
        for container, slot in sorted(clears):
            if container not in WARDROBE_CONTAINERS:
                self.queue.append(sub(0x020, packets.item_attr(0, 0, container, slot)))
        for container in sorted(wardrobes):
            self.queue.append(sub(0x01D, packets.item_same(0, container, 1 << container)))
            for item in items:
                if int(item["container"]) == container:
                    self.queue.append(self.item_packet(item))
            # The full list omits a slot that stayed empty; make the removal explicit
            # for a client that does not clear the container when it reopens.
            for source, slot in sorted(clears):
                if source == container and (source, slot) not in present:
                    self.queue.append(sub(0x020, packets.item_attr(0, 0, container, slot)))
        for move in writes:
            self.queue.append(sub(0x020, packets.item_attr(
                int(move["item_id"]), int(move["quantity"]),
                int(move["to_container"]), int(move["to_slot"]),
                extra=bytes(move.get("extra") or b""))))
        self.queue.append(self.container_sync())

    def locker_command(self, words: list[str]) -> None:
        """//locker store|grab|list: the hidden 9,999-slot locker, not a client bag.

        Store removes the item from every bag; grab puts it back in the inventory first,
        then the wardrobes.  Selectors are ``all``, a slot (``ammo``, ``back``, ``head``,
        ``ear``, ``ring`` and so on), ``materials`` for non-wearable items, or a name
        substring.
        """
        usage = ("Usage: //locker store|grab <all|ammo|back|materials|jsecapes|name> [n] or "
                 "//locker list")
        if not words:
            summary = self.world.service.locker_summary(int(self.char["id"]))
            self.say("Locker: %d/%d slots." % (
                summary["slots"], summary["capacity"]))
            self.say(usage)
            return
        action = words[0].casefold()
        if action == "list":
            items = self.world.service.locker_items(int(self.char["id"]))
            if not items:
                self.say("The locker is empty.")
                return
            cells = []
            for item in items:
                label = "%s x%d" % (item["name"], int(item["quantity"]))
                if item.get("build"):
                    label += " [%s]" % item["build"]
                cells.append(label)
            for offset in range(0, len(cells), 4):
                self.say(", ".join(cells[offset:offset + 4]))
            return
        if action not in ("store", "grab") or len(words) < 2:
            self.say(usage)
            return
        wanted = " ".join(words[1:]).strip()
        limit = None
        if action == "grab":
            parts = wanted.split()
            if len(parts) > 1 and parts[-1].isdigit() and int(parts[-1]) > 0:
                limit = int(parts[-1])
                wanted = " ".join(parts[:-1])
        selector, label = locker_selector(wanted)
        if action == "store":
            result = self.world.service.store_in_locker(int(self.char["id"]), selector)
            self._queue_storage_removals(result["moved"])
            count = sum(int(move["quantity"]) for move in result["moved"])
            if count:
                self.say("Stored %d item%s in the locker (%d/%d slots)." % (
                    count, "" if count == 1 else "s",
                    result["locker_count"], result["locker_capacity"]))
            else:
                self.say("Nothing in your bags matched %s." % label)
            if result["remaining"]:
                self.say("The locker is full; %d item%s stayed in your bags." % (
                    result["remaining"], "" if result["remaining"] == 1 else "s"))
            if result["equipped"]:
                self.say("Left %d equipped piece%s on." % (
                    result["equipped"], "" if result["equipped"] == 1 else "s"))
            log.info("%s //locker store %s -> %d items, %d left", self.addr, label, count,
                     result["remaining"])
            return
        result = self.world.service.take_from_locker(int(self.char["id"]), selector, limit)
        self._queue_storage_returns(result["moved"])
        count = sum(int(move["quantity"]) for move in result["moved"])
        if count:
            self.say("Took %d item%s out of the locker (%d left)." % (
                count, "" if count == 1 else "s", result["locker_items"]))
        elif result["locker_count"] == 0:
            self.say("The locker is empty.")
        elif result["remaining"]:
            self.say("Your bags are full; nothing could be taken out of the locker.")
        elif result["skipped"]:
            self.say("No matching items in the locker.")
        else:
            self.say("Nothing came out of the locker.")
        if count and result["remaining"]:
            self.say("%d item%s stayed: your bags are full." % (
                result["remaining"], "" if result["remaining"] == 1 else "s"))
        log.info("%s //locker grab %s -> %d items, %d left", self.addr, label, count,
                 result["locker_items"])

    def stock_command(self) -> None:
        """//stock: top the visible consumables back up from the hidden locker."""
        moved = self.world.service.refill_working_stock(int(self.char["id"]))
        self._queue_storage_returns(moved)
        count = sum(int(move.get("added", move["quantity"])) for move in moved)
        if count:
            self.say("Refilled %d item%s from the locker." % (
                count, "" if count == 1 else "s"))
        status = self.world.service.working_stock_status(int(self.char["id"]))
        cells = ["%s %d/%d" % (WORKING_STOCK_NAMES.get(item_id, item_id), current, target)
                 for item_id, (current, target) in status.items()]
        for offset in range(0, len(cells), 3):
            self.say(", ".join(cells[offset:offset + 3]))

    def _storage_status(self) -> None:
        """//storage with no verb: both stores, and what the current job is waiting on."""
        job = int(self.char.get("main_job") or 1)
        label = JOB_ABBREVIATIONS.get(job, str(job))
        overview = self.world.service.storage_overview(int(self.char["id"]), job)
        slip = int(overview["slip_total"])
        locker_items = int(overview["locker_total"])
        locker_slots = int(overview["locker_slots"])
        if not slip and not locker_items:
            self.say("The storage is empty. Use //storage organize to fill it.")
            return
        self.say("Storage: %d item%s on slips; locker %d/%d slots." % (
            slip, "" if slip == 1 else "s", locker_slots,
            int(overview["locker_capacity"])))
        self.say("%s: %d stored, %d item%s in your bags for other jobs." % (
            label, int(overview["stored_for_job"]), int(overview["away"]),
            "" if int(overview["away"]) == 1 else "s"))
        self.say("Use //storage organize to put the other jobs away and bring %s out." % label)

    def item_command(self, words: list[str]) -> None:
        """//item move ... and //item pull ...: the HUD's bag and Magic Bag actions."""
        usage = ("Usage: //item move <bag> <slot> <to-bag> [count] or "
                 "//item pull <slip|locker> <item-id> [extra-hex] [count]")
        if words and words[0].casefold() == "pull":
            if len(words) < 3:
                self.say(usage)
                return
            source = words[1].casefold()
            if source not in ("slip", "locker"):
                self.say("Pull source must be slip or locker.")
                return
            try:
                item_id = int(words[2], 0)
            except ValueError:
                self.say("Item id must be a number.")
                return
            extra = b""
            count = None
            rest = words[3:]
            if source == "locker" and rest and len(rest[0]) >= 8:
                try:
                    extra = bytes.fromhex(rest[0])
                    rest = rest[1:]
                except ValueError:
                    pass
            if rest and rest[0].isdigit():
                count = int(rest[0])
            result = self.world.service.pull_magic_item(
                int(self.char["id"]), source, item_id, extra, count)
            if result is None:
                self.say("That Magic Bag entry is gone.")
                return
            self.queue += self.container_items(0)
            self.queue.append(self.container_sync())
            if result.get("inventory_full"):
                self.say("Your inventory is full; the item stays in the Magic Bag.")
            else:
                self.say("Pulled %d item%s out of the Magic Bag." % (
                    int(result["pulled"]), "" if int(result["pulled"]) == 1 else "s"))
            return
        if words and words[0].casefold() == "store":
            if len(words) < 4 or words[1].casefold() != "locker":
                self.say("Usage: //item store locker <bag> <slot> [count]")
                return
            bag = self._recycle_bag(words[2])
            if bag is None:
                self.say("Unknown bag %r." % words[2])
                return
            if not words[3].isdigit():
                self.say("Slot must be a number.")
                return
            count = int(words[4]) if len(words) > 4 and words[4].isdigit() else None
            result = self.world.service.store_visible_in_locker(
                int(self.char["id"]), bag, int(words[3]), count)
            if result is None:
                self.say("That bag slot is empty.")
                return
            self.queue += self.container_items(bag)
            self.queue.append(self.container_sync())
            if result.get("locker_full"):
                self.say("The Magic Bag is full.")
            else:
                self.say("Moved %d item%s into the Magic Bag." % (
                    int(result["stored"]), "" if int(result["stored"]) == 1 else "s"))
            return
        if len(words) < 4 or words[0].casefold() != "move":
            self.say(usage)
            return
        source = self._recycle_bag(words[1])
        target = self._recycle_bag(words[3])
        if source is None or target is None:
            self.say("Unknown bag. Use inventory, safe, storage, safe2, satchel, sack, "
                     "case, wardrobe1..8 or a container number.")
            return
        if not words[2].isdigit():
            self.say(usage)
            return
        count = int(words[4]) if len(words) > 4 and words[4].isdigit() else 1
        slot = int(words[2])
        row = self.world.service.inventory_slot(int(self.char["id"]), source, slot)
        if row is None:
            self.say("That bag slot is empty.")
            return
        quantity = min(count, int(row["quantity"]))
        if not self.world.service.move_item(
                int(self.char["id"]), source, slot, target, 0x52, quantity):
            self.say("That move was refused.")
            return
        self.queue += self.container_items(source)
        self.queue += self.container_items(target)
        self.queue.append(self.container_sync())
        self.say("Moved %d item%s." % (
            quantity, "" if quantity == 1 else "s"))

    RECYCLE_BAGS = {
        "inventory": 0, "inv": 0, "safe": 1, "safe1": 1, "safe2": 9,
        "storage": 2, "locker": 4, "satchel": 5, "sack": 6, "case": 7,
        "wardrobe1": 8, "wardrobe2": 10, "wardrobe3": 11, "wardrobe4": 12,
        "wardrobe5": 13, "wardrobe6": 14, "wardrobe7": 15, "wardrobe8": 16,
    }

    def _recycle_bag(self, text: str) -> int | None:
        value = str(text or "").strip().casefold()
        if value.isdigit():
            return int(value) if 0 <= int(value) <= 17 else None
        return self.RECYCLE_BAGS.get(value)

    def recycle_command(self, words: list[str]) -> None:
        """//recycle: the 30-day Recycle Bin (container 17), with restore and drop."""
        usage = ("Usage: //recycle [list] | restore <slot> [count] | "
                 "drop <bag> <slot> [count] | purge")
        if not words or words[0].casefold() in ("list", "ls"):
            items = self.world.service.recycle_items(int(self.char["id"]))
            if not items:
                self.say("The Recycle Bin is empty.")
                return
            cells = ["%s x%d [slot %d]" % (item["name"], int(item["quantity"]),
                                           int(item["slot"])) for item in items]
            for offset in range(0, len(cells), 3):
                self.say(", ".join(cells[offset:offset + 3]))
            self.say("//recycle restore <slot> [count] brings one back.")
            return
        action = words[0].casefold()
        if action == "restore":
            if len(words) < 2 or not words[1].isdigit():
                self.say(usage)
                return
            count = int(words[2]) if len(words) > 2 and words[2].isdigit() else None
            result = self.world.service.restore_recycle_item(
                int(self.char["id"]), int(words[1]), count)
            if result is None:
                self.say("That Recycle Bin slot is empty.")
                return
            self.queue += self.container_items(CONTAINER_RECYCLE)
            self.queue += self.container_items(0)
            self.queue.append(self.container_sync())
            if result.get("inventory_full"):
                self.say("Your inventory is full; the item stays in the Recycle Bin.")
            else:
                self.say("Restored %d item%s from the Recycle Bin." % (
                    int(result["restored"]), "" if int(result["restored"]) == 1 else "s"))
            return
        if action == "drop":
            if len(words) < 3:
                self.say(usage)
                return
            bag = self._recycle_bag(words[1])
            if bag is None or bag == CONTAINER_RECYCLE:
                self.say("Unknown bag %r." % words[1])
                return
            if not words[2].isdigit():
                self.say(usage)
                return
            count = int(words[3]) if len(words) > 3 and words[3].isdigit() else 1
            result = self.world.service.drop_item(
                int(self.char["id"]), bag, int(words[2]), count)
            if result is None:
                self.say("That bag slot is empty.")
                return
            if result.get("recycle_full"):
                self.say("The Recycle Bin is full.")
                return
            self.queue += self.container_items(bag)
            self.queue += self.container_items(CONTAINER_RECYCLE)
            self.queue.append(self.container_sync())
            self.say("Moved %d item%s to the Recycle Bin for 30 days." % (
                int(result["recycled"]), "" if int(result["recycled"]) == 1 else "s"))
            return
        if action == "purge":
            count = self.world.service.purge_recycle(int(self.char["id"]))
            self.say("Purged %d expired Recycle Bin slot%s." % (
                count, "" if count == 1 else "s"))
            return
        self.say(usage)

    def _queue_storage_removals(self, moves: list[dict]) -> None:
        """Clear the bag slots an item left; slip contents are invisible to the client."""
        if not moves:
            return
        cleared = set()
        for move in moves:
            source = (int(move["from_container"]), int(move["from_slot"]))
            if source not in cleared:
                cleared.add(source)
                self.queue.append(sub(0x020, packets.item_attr(0, 0, source[0], source[1])))
        self.queue.append(self.container_sync())

    def _queue_storage_returns(self, moves: list[dict]) -> None:
        """Add the items back to their bag slots and mark the containers ready."""
        if not moves:
            return
        for move in moves:
            target_container = int(move["to_container"])
            self.queue.append(sub(0x020, packets.item_attr(
                int(move["item_id"]), int(move["quantity"]),
                target_container, int(move["to_slot"]),
                extra=bytes(move.get("extra") or b""))))
        self.queue.append(self.container_sync())

    def _queue_inventory_moves(self, moves: list[dict]) -> None:
        """Repaint both ends of an inventory -> wardrobe move."""
        if not moves:
            return
        for move in moves:
            self.queue.append(sub(0x020, packets.item_attr(
                0, 0, int(move["from_container"]), int(move["from_slot"]))))
            self.queue.append(sub(0x020, packets.item_attr(
                int(move["item_id"]), int(move["quantity"]),
                int(move["to_container"]), int(move["to_slot"]),
                extra=bytes(move.get("extra") or b""))))
        self.queue.append(self.container_sync())

    def _parse_sleeping(self, body: bytes) -> None:
        """Sleeping clients keep sending; read only chat so a wake command can arrive."""
        offset = 0
        while offset + 4 <= len(body):
            size = (body[offset + 1] & 0xFE) * 2
            if size == 0 or offset + size > len(body):
                break
            ptype = struct.unpack_from("<H", body, offset)[0] & 0x1FF
            if ptype == 0x0B5:
                self.handle(ptype, body[offset:offset + size])
            offset += size
        now = time.time()
        if now - self.sleeping_heartbeat >= 10.0:
            self.sleeping_heartbeat = now
            # A small status packet keeps the client's zone connection from timing out.
            self.queue.append(self.char_update(packets.SEND_HP))

    def sleep(self) -> None:
        """Park this character without logging it out or stopping its process."""
        if self.sleeping:
            self.say("Already sleeping.")
            return
        self.world.despawn_player(self)
        char_id = int(self.char["char_id"])
        group = self.world.party_of(char_id)
        self.sleep_party_id = int(group.id) if group is not None else 0
        if group is not None:
            # The roster is server-owned; leaving it visible would make the parked box
            # look awake in every party member's list.
            self.world.remove_from_party(char_id)
        self.sleeping = True
        self.sleeping_since = time.time()
        self.sleeping_heartbeat = 0.0
        self.moving = False
        self.move_time = 0
        self.engaged_id = None
        self.engaged_targid = 0
        self.casting = None
        self.save_position(force=True)
        self.queue.clear()
        log.info("%s sleeps in %s at %s", self.addr,
                 self.world.zones.name(self.zone), self.pos)

    def wake(self) -> None:
        """Resume a sleeping character in place; no zone change and no new login."""
        if not self.sleeping:
            self.say("Already awake.")
            return
        self.sleeping = False
        self.sleeping_since = 0.0
        log.info("%s wakes in %s at %s", self.addr,
                 self.world.zones.name(self.zone), self.pos)
        if self.sleep_party_id:
            group = self.world.parties.get(self.sleep_party_id)
            if group is not None and self.world.join_party(group, self):
                self.world.reload_party(group)
            self.sleep_party_id = 0
        self.after_zone_in()
        self.sync_players()
        self.say("Awake.")

    def change_zone_with_family(self, zone: int, pos, logout_state: int = 2) -> None:
        """Walk this session and its family boxes through one zone line.

        A zone line is one interaction from the player but one hand-off per client, and the
        boxes behind the leader only sometimes send a ``0x05E`` of their own: the client
        asks for the zone its own character stepped on, and the follow controller's drive
        through the leader's last point does not always reach the line.  They are moved
        here instead, so the whole team runs the same zone-in script the leader does.  Only
        the main account leads (``family_followers`` checks it); a sub that crosses alone
        still zones, but nothing follows it.

        The leader's ``0x00B`` goes out at once and the boxes' follow on the next tick, as
        one batch: the clients overlap their zone loads, and the hand-off fixes (the parked
        key sequence and the stolen-port rule) keep a simultaneous reconnect from losing a
        box.  A box that did walk through the line itself has already arrived, and its
        queued move is dropped.
        """
        # Collect before moving the leader: family_followers looks in the old zone.
        followers = self.world.family_followers(self)
        if not self.change_zone(zone, pos, logout_state, follow_family=False):
            return
        if self.world.is_family_leader(self):
            # A box that is still logging in cannot be in the list above; it joins the
            # anchor once its zone-in finishes.
            self.world.set_team_anchor(self, zone, pos)
        if not followers:
            return
        label = self.world.zones.name(int(zone))
        announce = "%s leads you into %s." % (
            self.char.get("name") or "Your leader", label)
        self.world.queue_warps(
            self, followers, zone, pos, spacing=0.5, announce=announce,
            skip_if_present=True)
        log.info("%s leads %d family box(es) into %s", self.addr, len(followers), label)

    def already_at(self, zone: int, pos) -> bool:
        """True when a move asks for the spot the character is already standing on.

        The launcher's auto-warp used to pull a box once per poll while its leader was
        barely moving, which re-zoned the whole team every few seconds for no gain.  A
        same-zone move within a few yalms is a no-op, not a new hand-off.
        """
        if pos is None or int(zone) != int(self.zone):
            return False
        try:
            return (abs(float(pos[0]) - float(self.pos[0])) <= 3.0
                    and abs(float(pos[1]) - float(self.pos[1])) <= 3.0
                    and abs(float(pos[2]) - float(self.pos[2])) <= 3.0)
        except (TypeError, ValueError, IndexError):
            return False

    def change_zone(self, zone: int, pos, logout_state: int = 2,
                    follow_family: bool = True) -> bool:
        """Queue a zone hand-off; True when a ``0x00B`` was actually queued.

        False means the move was deferred because another hand-off is already in flight,
        or dropped as a no-op the client itself reported.  ``follow_family`` makes a main
        character's move (a teleport spell, a survival guide, a home point, a warp item)
        bring the sub-account boxes to the same place; scripted group moves pass False
        because they already name every destination.
        """
        if self.zoning or (self.logged_in and not self.zone_loaded):
            # A hand-off is already in flight.  `zoning` covers the 0x00B itself; the
            # second test covers the window after 0x00A and before the client's 0x00C,
            # when the server has already cleared `zoning` but the client is still
            # loading.  Sending a 0x00B now moves the client's cipher on again under it;
            # a repeated //warp call (or the launcher's auto-warp) did exactly that and
            # left boxes looping on "Downloading".  Keep the new destination and apply
            # it after the client has acknowledged this zone-in.
            self.pending_zone = (int(zone), list(pos) if pos else None, logout_state)
            log.info("%s zone change to %d deferred: the hand-off to %d is in flight",
                     self.addr, int(zone), self.zone)
            return False
        if self.zone_loaded and self.position_seen and self.already_at(zone, pos):
            # The client itself reported standing at this spot, so this really is a
            # no-op.  position_seen matters: before the first position packet the server
            # only knows the position it *sent* the box to, which is how the old shortcut
            # skipped warps that were actually needed.  This also keeps a repeated
            # //warp all me from reloading boxes that are already on top of the leader.
            return False
        followers = []
        if follow_family and logout_state != 3 and self.world.is_family_leader(self):
            # A teleport is not a walk: bring every online box, wherever it stands, not
            # only the ones behind the leader in this zone.  Collect before moving.
            followers = [session for session in self._family_sessions()
                         if session is not self]
            # A box that is still logging in is absent from the list; it joins the anchor
            # when its zone-in finishes.
            self.world.set_team_anchor(self, zone, pos)
        if self.char.get("moghouse") and pos and any(abs(float(v)) > 1.0 for v in pos[:3]):
            # A warp or a family follow is taking the character out of the Mog House.
            # The login packet keys the interior off this flag; leaving it set made
            # after_zone_in put the character back at the interior origin (0, 0, 0) after
            # every pull, which is what kept a box re-zoning instead of joining the team.
            self._set_moghouse(False)
        # The old zone's clients must lose this character before it reappears elsewhere.
        self.world.despawn_player(self)
        # A mount does not survive a zone line: the client drops it on 0x00B, and the
        # zone-in's 0x037 carries mount_id 0.  Clearing it here keeps a late 0x00D or the
        # idle heartbeat from putting the old mount back on the newly loaded character.
        self.mount_id = -1
        self.pending_mount = None
        self.zone = int(zone)
        self.pos = list(pos) if pos else list(self.world.zones.position(self.zone))
        self.zoning = True
        self.zone_change_at = time.time()
        self.moving = False
        self.move_time = 0
        self.char["zone"] = self.zone
        self.char["pos"] = list(self.pos)
        self.save_position(force=True)
        self.world.party_zone_changed(self)
        log.info("%s -> %s (%d) at %s", self.addr, self.world.zones.name(self.zone), self.zone, self.pos)
        self.queue.append(self.logout_packet(logout_state, zone_change=True))
        if followers:
            announce = "%s leads you into %s." % (
                self.char.get("name") or "Your leader",
                self.world.zones.name(self.zone))
            self.world.queue_warps(self, followers, self.zone, self.pos,
                                   announce=announce)
        return True

    def logout_packet(self, state: int, zone_change: bool = False) -> Msg:
        ip = socket.inet_aton(self.world.host_ip) if zone_change else bytes(4)
        port = self.world.ports["zone_port"] if zone_change else 0
        p = sub(0x00B, struct.pack("<B3x4sI8xI", state, ip, port, 0))
        p.zone_out = True
        return p

    def say(self, text: str) -> None:
        msg = text.encode("ascii", "replace")[:150]
        self.queue.append(sub(0x017, struct.pack("<BBH", 6, 0, self.zone) + bytes(15) + msg + b"\0"))

    def system_message(self, message_id: int) -> Msg:
        """A line from the client's own system-message table (0x009)."""
        return sub(0x009, packets.system_message(message_id))

    # --- style lock (0x053) and emotes (0x05D) -------------------------------------------------
    def style_locked(self) -> bool:
        return bool(int(self.char.get("style_lock") or 0))

    def _current_models(self) -> dict[int, int]:
        """The visible appearance the equipped gear gives right now."""
        c = self.char
        return {0: int(c.get("main") or 0), 1: int(c.get("sub") or 0),
                2: int(c.get("ranged") or 0), 4: int(c.get("head") or 0),
                5: int(c.get("body") or 0), 6: int(c.get("hands") or 0),
                7: int(c.get("legs") or 0), 8: int(c.get("feet") or 0)}

    def _style_models(self) -> dict[int, int]:
        c = self.char
        return {kind: int(c.get(key) or 0) for kind, key in STYLE_SLOTS.items()}

    def _apply_style(self, locked: bool, models: dict[int, int] | None = None) -> None:
        """Set the style-lock flag and its models, and persist both.

        A locked appearance is kept in its own columns, so every later gear change can
        still update the stats without changing the grap list.  That is what stops the
        "blinking" the client shows when the server echoes new models.

        Turning the lock off forgets the stored look too, as retail does.  Leaving the
        models behind let an old save or a stale keepalive paint the previous job's
        clothing back on after a job change.
        """
        self.char["style_lock"] = 1 if locked else 0
        if not locked:
            for key in STYLE_SLOTS.values():
                self.char[key] = 0
        elif models is not None:
            for kind, key in STYLE_SLOTS.items():
                if kind in models:
                    self.char[key] = int(models[kind] or 0)
        saved = self._style_models()
        try:
            self.world.service.save_style_lock(int(self.char["id"]), bool(locked), saved)
        except Exception as exc:
            log.warning("%s could not save the style lock: %s", self.addr, exc)
        log.info("%s style lock %s: %s", self.addr, "on" if locked else "off", saved)

    def style_packets(self) -> list[Msg]:
        """The two packets the client needs to repaint the player after a lock change."""
        return [self.grap_list(), self.char_sync()]

    def lockstyle(self, p: bytes) -> None:
        """C2S 0x053: /lockstyle on|off, /lockstyleset # and the client's continue."""
        if len(p) < 8:
            log.info("%s lockstyle short (%d bytes): %s", self.addr, len(p), bytes(p).hex())
            return
        count, mode, flags = int(p[4]), int(p[5]), int(p[6])
        log.info("%s lockstyle mode=%d count=%d flags=%d", self.addr, mode, count, flags)
        if mode != LOCKSTYLE_KEEPALIVE or flags or DEBUG:
            # The keepalive is the only packet here that arrives unasked (login, zoning);
            # everything else is worth the whole packet in the log when a report says the
            # command "did nothing".
            log.info("%s lockstyle raw (%d bytes): %s", self.addr, len(p), bytes(p).hex())
        if mode == LOCKSTYLE_QUERY:
            self.queue.append(self.system_message(
                MSG_STYLE_LOCK_IS_ON if self.style_locked() else MSG_STYLE_LOCK_IS_OFF))
            return
        if mode == LOCKSTYLE_KEEPALIVE:
            # Mode 1 is the client's "continue": it asserts that its own style lock is
            # on.  It is what the client sends on login and zoning, and it is also what
            # /lockstyle on produces when the client already believes the lock is on --
            # it does not resend mode 4 in that state.  Ignoring the packet therefore
            # left the two sides disagreeing forever: the client kept saying "still
            # locked" while the server had it off, and every /lockstyle on typed after
            # that sent only this packet and changed nothing on screen.
            #
            # A continue cannot resurrect an old look: turning the lock off clears the
            # stored models, so this locks the appearance the character is wearing now.
            if not self.style_locked():
                self._apply_style(True, self._current_models())
                self.queue += self.style_packets()
                self.queue.append(self.system_message(MSG_STYLE_LOCK_ON))
            elif not any(self._style_models().values()):
                # A save from before the models were stored has the flag without any
                # appearance.  Fill it in silently; the client already believes it is on.
                self._apply_style(True, self._current_models())
                self.queue += self.style_packets()
            return
        if mode == LOCKSTYLE_DISABLE:
            was_locked = self.style_locked()
            if not was_locked and not any(self._style_models().values()):
                return
            self._apply_style(False)
            self.queue += self.style_packets()
            if was_locked:
                self.queue.append(self.system_message(MSG_STYLE_LOCK_OFF))
            return
        if mode not in (LOCKSTYLE_ENABLE, LOCKSTYLE_SET):
            log.info("%s lockstyle unknown mode %d", self.addr, mode)
            return
        # Enable locks what is worn; Set replaces the named slots in the packet.  A slot
        # the set does not name keeps the appearance already on screen (the locked one),
        # or the real gear when nothing has been locked yet.
        stored = self._style_models()
        models = stored if (self.style_locked() and any(stored.values())) else self._current_models()
        failed: list[int] = []
        if mode == LOCKSTYLE_SET:
            for index in range(min(count, 16)):
                offset = 8 + index * 8
                if offset + 8 > len(p):
                    break
                kind = int(p[offset + 1])
                item_no = struct.unpack_from("<H", p, offset + 4)[0]
                if kind not in STYLE_SLOTS or not item_no:
                    continue
                item = self.world.service.item(item_no)
                model = int(item.get("model") or 0) if item else 0
                if not model:
                    failed.append(int(item_no))
                    continue
                models[kind] = model
        elif self.style_locked() and any(self._style_models().values()):
            # /lockstyle on while it is already on: keep the locked look instead of
            # re-snapshotting whatever gear the swap engine last wore.
            models = self._style_models()
        self._apply_style(True, models)
        self.queue += self.style_packets()
        if failed:
            self.queue.append(sub(0x11C, packets.lockstyle_error(failed)))
            self.say("Could not lock the appearance of %d item(s)." % len(failed))
        self.queue.append(self.system_message(MSG_STYLE_LOCK_ON))

    def motion(self, p: bytes) -> None:
        """C2S 0x05D: echo an emote to its caster and the other players in the zone.

        The client plays the animation and writes the text when it receives 0x05A, so
        without this reply /wave, /nod and the rest sent the request and looked dead.
        """
        if len(p) < 16:
            return
        target_id, target_index, emote, mode, param = struct.unpack_from("<IHBBH", p, 4)
        if emote not in EMOTE_IDS or mode > 2:
            log.info("%s motion ignored: emote=%d mode=%d", self.addr, emote, mode)
            return
        message_no = int(emote)
        if emote == EMOTE_SALUTE:
            param = int(self.char.get("nation") or 0)
        elif emote == EMOTE_HURRAY:
            param = int(self.equipped.get(0, (0, 0, 0))[2] or 0)
        elif emote == EMOTE_BELL:
            # /bell has no text line; the client only needs the note as the parameter.
            mode = 2
            param = max(0, int(param) - 6)
        elif emote == EMOTE_JOB:
            if param < 0x1F:
                return
            extra = int(param) - 0x1F
            message_no = EMOTE_JOB + extra
            param = extra
        log.info("%s emote %d (mode %d, target %#x/%d)", self.addr, emote, mode,
                 int(target_id), int(target_index))
        body = packets.motion_message(int(self.char["char_id"]), int(target_id),
                                      int(self.char.get("targid", TARGID)), int(target_index),
                                      message_no, mode, param)
        sessions = self.world.sessions_in_zone(self.zone)
        for other in sessions:
            other.queue.append(sub(0x05A, body))
        if not any(other is self for other in sessions):
            self.queue.append(sub(0x05A, body))

    # --- what the client is sent ---
    def on_login(self) -> None:
        if self.char.get("moghouse"):
            # The client's Mog House interior is centered on (0,0,0); old saves may
            # still hold the exterior door coordinates.
            self.pos = [0.0, 0.0, 0.0, 192]
        self.logged_in = True
        self.zoning = False
        self.sleeping = False
        self.sleep_party_id = 0
        self.zone_loaded = False
        self.entities_sent = False
        self.sent_targids: set[int] = set()
        self.next_entity_sync = 0.0
        self.casting = None
        self.trust_entities = []
        self.pet_entity = None
        # The live aura of each bubble, {"indi": (status, hexed mob id), "geo": (...)}.
        # A Geomancer runs one Indi- and one Geo- bubble, and a new cast replaces only
        # its own, so this remembers what each one put where.
        self.geo_bubble: dict[str, tuple[int, int]] = {}
        self.position_seen = False
        self.dead_until = 0.0
        self.engaged_id = None
        self.engaged_targid = 0
        self._merit_counts = None
        self._trait_cache = None
        self.next_regen_tick = time.time() + traits.TICK_SECONDS
        if self.char.get("moghouse"):
            # A Mog House is a rest: logging in there (which is what entering it does,
            # through the zone change) fills HP and MP and leaves no status effect.
            self.clear_status_effects()
            self.restore_vitals(refresh=False)
            # The buffs are gone with the rest, but an ability cooldown is a server
            # cooldown: it survives the logout just as it survives a dropped link.
            self.restore_live_state(include_effects=False)
        elif int(self.char.get("hp_current", 1)) <= 0:
            self.char["hp_current"] = max(1, int(self.char["hp"]) // 2)
            self.char["mp_current"] = int(self.char.get("mp", 0)) // 2
            try:
                self.world.service.save_vitals(
                    self.char["id"], self.char["hp_current"], self.char["mp_current"])
            except Exception:
                pass
            # A K.O. takes the buffs in retail; the recasts still come back.
            self.restore_live_state(include_effects=False)
        else:
            # A dropped link is a relog to the client: give it back the song list and the
            # cooldowns the server was holding for it (game/live_state.py).
            self.restore_live_state()
        self.equip_initial()
        self.queue += [sub(0x04F, bytes(4)), self.grap_list(), self.item_max(), self.login_packet()]
        # Send the command data before the client asks for stats (0x061) and builds its
        # menus, but after the login packet has defined the character.  The 0x119 recast
        # table belongs in this burst: it carries what restore_live_state just read, so a
        # cooldown that survived the logout is in client memory before anything can use it.
        self.queue += [self.char_feats(), self.char_abilities(), self.char_commands(),
                       self.abil_recast()]
        self.queue += self.equipment_packets()
        self.stats_refresh_at = time.time() + 2.0

    def after_zone_in(self) -> None:
        try:
            self.world.service.purge_recycle(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s recycle purge failed: %s", self.addr, exc)
        # Order matters: the client builds the Weapon Skills list when it processes the
        # 0x062 skill packet, from whatever 0x0AC bits it has at that moment.  Sending
        # 0x062 first leaves a fresh client with an empty list; the command data must
        # precede it.
        # The client needs the equipped weapon before it can select a weapon-skill type;
        # the zone-in burst re-asserts the equipment so the 0x062 list build sees Aymur
        # rather than an empty hand.
        # A main that was away while its subs kept the party rejoins it and takes the
        # lead before the roster is built.  Only a fresh login does this: a zone line
        # after a deliberate /pcmd leave must not silently re-add the main.
        # `exclude_self` leaves this client's own GROUP_TBL/GROUP_LIST to the zone-in
        # burst below (the same packets, one copy).
        if getattr(self, "fresh_login", True):
            self.fresh_login = False
            try:
                recovered = self.world.recover_family_party(self, exclude_self=True)
            except Exception as exc:
                log.warning("%s party recovery failed: %s", self.addr, exc)
                recovered = ""
            if recovered:
                self.say(recovered)
        self.refresh_vitals()
        q = [sub(0x008, b"\xff" * 48),  # every zone visited: every map viewable
             self.grap_list(), *self.equipment_packets(),
             self.job_info(), self.char_status(), self.char_stats(),
             self.char_feats(), self.char_abilities(), self.char_commands(),
             self.abil_recast(),
             self.char_skills(), self.party_member(), self.char_update()]
        # The group page is server-owned: without this the client's Party Info window and
        # the native party list stay empty even though the server knows the roster.  A
        # solo player still needs the empty table plus its own row: the HUD reads the job
        # pair from row 0, and with no row a fresh login reports MainJob 0 (which empties
        # the spell and Trust windows) until something else repopulates it.
        q += self.party_packets() or self.world.solo_roster_packets(self)
        # Every permanent key item, in both GetItemFlag and LookItemFlag bitmaps.
        q += [sub(0x055, KEY_ITEM_BITS[table] + KEY_ITEM_BITS[table] +
                   struct.pack("<HH", table, 0)) for table in range(7)]
        offered = (0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x88)
        logs = offered + tuple(x + 0x40 for x in offered) + (
            0xD0, 0xD8, 0x30, 0x38, 0xE0, 0xE8, 0xF0, 0xF8, 0x100, 0x108)
        q += [sub(0x056, bytes(32) + struct.pack("<HH", port, 0)) for port in logs]
        q.append(sub(0x056, bytes(36) + struct.pack("<HH", 0xFFFF, 0)))
        q += [sub(0x0AA, self.spell_bits()),         # every spell id in spell_list
              self.job_points(), self.job_points_detail(),
              # 0x0AE is the client's mount table: one bit per mount id, eight bytes.
              # Setting every bit the client knows puts all of them in its Mount menu
              # and lets /mount and //mount call any of them.
              sub(0x0AE, mounts.bitfield()),
              self.char_sync(),
              *self.merit_list(),             # the merits this character has bought
              self.blacklist()]
        try:
            # Keep the consumables the client must see visible before the inventory
            # snapshot goes out; the rest stays in the hidden locker.
            self.world.service.refill_working_stock(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s working-stock refill failed: %s", self.addr, exc)
        q += self.inventory_packets()
        self.queue += q
        self.zone_loaded = True
        # This hand-off reached the world: the client is on a known key again, so the
        # parked sequence for a failed one is no longer needed.
        self.world.clear_parked_keys(int(self.char["id"]))
        # The client builds the Abilities menu from 0x0AC, but on this build the zone-in
        # copy is consumed before that menu exists.  Two later copies (after the 0x061
        # reply and a couple of seconds into the zone) make both submenus populate.
        now = time.time()
        self.abilities_retries = [now + 2.0, now + 4.0]
        if self.position_seen:
            self.sync_entities()
        # The welcome line used to be a 0x017 chat packet here.  A chat packet arriving at
        # this exact point is one of the two things that can take the client out of movement,
        # so keep the zone-in burst free of chat until that is settled.
        # self.say("%s (%d). Say //help for commands." % (self.world.zones.name(self.zone), self.zone))
        self.apply_pending_zone()
        # A box that was still logging in when the team was called joins the anchor now
        # that its zone-in has finished, without waiting for another //warp all me.
        self.world.join_team_anchor(self)
        # The reconnect line waits the same couple of seconds the command retries do:
        # chat in the burst itself can take the client out of movement, and the client may
        # still have been loading when on_login read the snapshot.
        if self.live_state_notice is not None:
            self.live_state_notice_at = now + LIVE_STATE_NOTICE_DELAY

    def apply_pending_zone(self) -> None:
        """Run a zone change that was requested while this one was still loading.

        A second //warp, a zone line, or the launcher's auto-warp used to send another
        0x00B mid-hand-off, advancing the cipher again before the client had the zone it
        was loading.  The move is kept instead and performed now, when a new hand-off is
        safe.
        """
        pending = self.pending_zone
        self.pending_zone = None
        if not pending:
            return
        zone, pos, logout_state = pending
        if self.already_at(zone, pos):
            # A duplicate call to the same spot (the usual case: a warp already in
            # progress) must not bounce the client through another zone-in.
            return
        self.change_zone(zone, pos, logout_state)

    # --- entities, inventory and actions -------------------------------------------------------
    def despawn_trusts(self) -> None:
        """Release every alter ego this character has called (zone line, logout, KO)."""
        for entity in list(getattr(self, "trust_entities", [])):
            try:
                self.world.despawn_trust(entity)
            except Exception as exc:
                log.warning("%s could not release trust %s: %s", self.addr,
                            getattr(entity, "name", "?"), exc)
        self.trust_entities = []
        pet = getattr(self, "pet_entity", None)
        if pet is not None:
            try:
                self.world.despawn_pet(pet, reason="release")
            except Exception as exc:
                log.warning("%s could not release pet %s: %s", self.addr,
                            getattr(pet, "name", "?"), exc)
            self.pet_entity = None

    def load_zone_entities(self) -> None:
        if self.char.get("moghouse"):
            # The interior is part of the city zone, so its resident Moogle is already one
            # of the zone's NPCs (at the interior spawn point).  Spawning that exact row,
            # rather than an invented entity, keeps the id the client's own NPC table uses,
            # which is what the target name and the Moogle's menu are keyed on.
            self.entities = [self.moghouse_moogle()]
        else:
            self.entities = list(self.world.entities_for_zone(self.zone))
        self.despawn_trusts()
        self.entities_sent = False
        self.sent_targids: set[int] = set()
        self.next_entity_sync = 0.0
        self.casting = None
        self.engaged_id = None
        self.engaged_targid = 0
        self.target_targid = 0

    def moghouse_moogle(self) -> ZoneEntity:
        """The resident Moogle, standing at the interior spawn point."""
        candidates = [e for e in self.world.entities_for_zone(self.zone)
                      if e.kind == "npc" and str(e.script or "").lower() == "moogle"]
        if candidates:
            source = min(candidates, key=lambda e: e.distance_to(0.0, 0.0, 1.5))
            return ZoneEntity(
                kind="npc", id=source.id, targid=source.targid, zone=self.zone,
                name=source.name or "Moogle", x=0.0, y=0.0, z=1.5, rot=source.rot or 64,
                model=source.model or 82, size=0, look=source.look,
                namevis=source.namevis, triggerable=True, widescan=True,
                script="moghouse_moogle")
        return ZoneEntity(
            kind="npc", id=0x01000000 | (self.zone << 12) | 0x72, targid=0x72,
            zone=self.zone, name="Moogle", x=0.0, y=0.0, z=1.5, rot=64,
            model=82, size=0, triggerable=True, widescan=True, script="moghouse_moogle")

    def sync_entities(self) -> None:
        """The client asks for nearby entities with its first 0x015, not at zone-in."""
        if self.entities_sent or not self.zone_loaded:
            return
        self.entities_sent = True
        self.sync_nearby_entities()
        self.sync_players()

    def sync_nearby_entities(self) -> None:
        """Spawn every entity inside SYNC_RANGE that this client has not seen yet.

        The client's zone table knows its own entities; it only needs the ones close enough
        to draw, so a zone with hundreds of spawns does not arrive in one burst.
        """
        from .world import SYNC_RANGE

        for entity in self.entities:
            if entity.targid in self.sent_targids:
                continue
            if entity.distance_to(*self.pos[:3]) > SYNC_RANGE:
                continue
            self.sent_targids.add(entity.targid)
            self.queue_spawn(entity)

    def sync_players(self) -> None:
        """Spawn/despawn the other player characters around this one.

        Players are 0x00D entities, not the 0x00E NPC/mob stream, and each client sees
        itself as targid 0x400. Everyone else gets a World-assigned targid and is streamed
        in at 45 yalms, out at 50. The sweep runs once a second from tick(), so a player
        walking into view appears without a zone change.
        """
        if not self.logged_in or self.zoning or self.gone or not self.zone_loaded:
            return
        here = [s for s in self.world.sessions_in_zone(self.zone)
                if s is not self and getattr(s, "targid", 0)
                and getattr(s, "entities_sent", False)]
        nearby: dict[int, "ZoneSession"] = {}
        for other in here:
            char_id = int(other.char["char_id"])
            distance = math.dist(self.pos[:3], other.pos[:3])
            if char_id in self.seen_players:
                if distance <= PLAYER_DESPAWN_RANGE:
                    nearby[char_id] = other
            elif distance <= PLAYER_SPAWN_RANGE:
                nearby[char_id] = other

        for char_id, other in nearby.items():
            seen = self.seen_players.get(char_id)
            if seen is other:
                continue
            if seen is not None:
                # This character reconnected into a different session, possibly with a
                # different targid.  The client still holds the copy it was spawned with,
                # so replace that one instead of leaving a frozen twin beside the new one.
                targid = int(getattr(seen, "targid", 0) or other.targid)
                self.queue.append(sub(0x00D, seen.player_body(
                    packets.SEND_PLAYER_DESPAWN, targid=targid)))
            self.seen_players[char_id] = other
            self.queue.append(sub(0x00D, other.player_body(packets.SEND_CHAR_SPAWN)))

        for char_id, other in list(self.seen_players.items()):
            if char_id in nearby:
                continue
            self.queue.append(sub(0x00D, other.player_body(packets.SEND_PLAYER_DESPAWN)))
            self.seen_players.pop(char_id, None)

    def entity_packet(self, entity, mask: int = packets.SEND_SPAWN) -> Msg:
        return sub(0x00E, packets.entity_update(entity, mask))

    def has_urgent(self) -> bool:
        """Whether anything besides ambient entity movement is waiting to go out."""
        return any(not getattr(message, "ambient", False) for message in self.queue)

    def drop_pending_position(self, ptype: int, targid: int) -> None:
        """Forget a queued position for an entity that just spawned, changed or left.

        Any other entity update already carries the position, so the older ambient
        message is redundant; sending it after a despawn would put the mob back.
        """
        message = self.pending_positions.pop((int(ptype), int(targid)), None)
        if message is None:
            return
        for index, queued in enumerate(self.queue):
            if queued is message:
                self.queue.pop(index)
                return

    def _is_queued(self, message: Msg) -> bool:
        """Whether this exact message is still waiting (queue.clear() may have dropped it)."""
        return any(queued is message for queued in self.queue)

    def queue_position(self, ptype: int, targid: int, body: bytes,
                       priority: float = 0.0, urgent: bool = False) -> None:
        """Queue an entity's latest position, replacing any older pending one.

        A crowded zone produces hundreds of these a second.  Adding every one to the
        FIFO made the queue grow without bound and put a five-minute mob stream in front
        of the player's next job ability; keeping one message per entity caps it at the
        number of entities in view.  ``urgent`` is for a start, stop, turn or speed
        change: that is the packet the client cannot interpolate its way through, so it
        is never charged against the ambient budget.
        """
        targid = int(targid)
        key = (int(ptype), targid)
        fresh = sub(ptype, body)
        if urgent:
            self.drop_pending_position(ptype, targid)
            fresh.ptype = int(ptype)
            fresh.targid = targid
            fresh.priority = float(priority)
            fresh.queued_at = time.time()
            self.queue.append(fresh)
            return
        message = self.pending_positions.get(key)
        if (message is not None and len(message) == len(fresh)
                and self._is_queued(message)):
            # Fixed-size entity record: overwrite its payload where it already sits, so
            # the newest position goes out in the order the entity first appeared.
            message[:] = fresh
            message.priority = float(priority)
            message.ambient = True
            return
        fresh.ambient = True
        fresh.ptype = int(ptype)
        fresh.targid = targid
        fresh.priority = float(priority)
        fresh.queued_at = time.time()
        self.queue.append(fresh)
        self.pending_positions[key] = fresh

    def queue_entity(self, entity, mask: int = packets.SEND_SPAWN, equipped: bool = False,
                     urgent: bool = False) -> None:
        if int(mask) == packets.SEND_POSITION:
            self.queue_position(0x00E, int(entity.targid),
                                packets.entity_update(entity, mask, equipped=equipped),
                                priority=entity.distance_to(*self.pos[:3]),
                                urgent=urgent)
            return
        # Every other mask (spawn, HP, animation, despawn) already carries the entity's
        # position and state; the pending ambient copy would only repeat it.
        self.drop_pending_position(0x00E, int(entity.targid))
        self.queue.append(sub(0x00E, packets.entity_update(entity, mask, equipped=equipped)))

    def queue_spawn(self, entity) -> None:
        look = bytes(getattr(entity, "look", b"") or b"")
        if len(look) >= 20 and look[0:2] == b"\x01\x00":
            # Equipped NPC: SubKind 1 + SendFlg.Model gives the client the real
            # GrapIDTbl (race/face/gear) instead of the default hooded model.
            self.queue_entity(entity, packets.SEND_SPAWN, equipped=True)
        else:
            self.queue_entity(entity, packets.SEND_SPAWN)

    def inventory_packets(self) -> list[Msg]:
        out = [self.item_max()]
        flags = 0
        items = self.world.service.inventory(self.char["id"])
        for container in (0, 1, 9, 2, 17, 8, 10, 11, 12, 13, 14, 15, 16, 3, 4, 5, 6, 7):
            flags |= 1 << container
            # The state-0 0x01D opens the container, and it has to come first: the client
            # files 0x020 rows into a storage's item list only while that container's load
            # window is open.  Items sent before the marker still fill the bag, so GearSwap
            # and the control addon see them, but the equipment window lists the Mog
            # Wardrobe as empty.  Replaying state 0 -> 0x020 -> state 1 against a running
            # client made an open wardrobe's list appear; the old item-then-marker order
            # left it blank.
            out.append(sub(0x01D, packets.item_same(0, container, flags)))
            for item in items:
                if int(item["container"]) != container:
                    continue
                out.append(self.item_packet(item))
        out.append(self.container_sync())
        return out

    def container_sync(self) -> Msg:
        """The 0x01D closing an inventory update, every bag left ready to draw.

        The Flags field replaces the client's container-ready mask, so it must name
        every bag zone-in loaded, not just the ones this update touched.
        """
        return sub(0x01D, packets.item_same(1, CLIENT_CONTAINERS, ALL_CONTAINERS))

    def item_packet(self, item: dict, container: int | None = None,
                    slot: int | None = None) -> Msg:
        """One 0x020 for an inventory row, carrying its augment ``extdata``.

        A charged dispense pouch instead carries the client's ItemTimerInfo block, built
        from the timer stored on that exact bag copy.  The same row therefore shows
        ``1/1`` and an hour-long reuse countdown wherever it sits.
        """
        item_id = int(item["item_id"])
        extra = bytes(item.get("extra") or b"")
        spec = self.dispense_items.get(item_id)
        if spec is not None:
            extra = item_usable.charged_attr(
                extra,
                now=time.time(),
                max_charges=int(spec["max_charges"]),
                reuse_delay=int(spec["reuse_delay"]),
                use_delay=int(spec["use_delay"]),
                vana_epoch=VANA_EPOCH,
            )
        return sub(0x020, packets.item_attr(
            item_id, int(item["quantity"]),
            int(item["container"] if container is None else container),
            int(item["slot"] if slot is None else slot),
            extra=extra))

    def item_move(self, p: bytes) -> None:
        """C2S 0x029: move or split a stack between two containers (inventory, wardrobes...)."""
        if len(p) < 12:
            return
        quantity, cat1, cat2, idx1, idx2 = struct.unpack_from("<IBBBB", p, 4)
        log.info("%s item move %d of %d:%d -> %d:%d", self.addr, quantity, cat1, idx1, cat2, idx2)
        moved = self.world.service.move_item(self.char["id"], cat1, idx1, cat2, idx2, quantity)
        if not moved:
            log.info("%s item move refused", self.addr)
        # The moved item's new slot and the emptied source slot, then one sync that keeps
        # every bag ready (not only the two that changed).
        self.queue += self.container_items(cat1, clear_slot=idx1)
        self.queue += self.container_items(cat2)
        self.queue.append(self.container_sync())

    def item_drop(self, p: bytes) -> None:
        """C2S 0x028: move a stack to the 30-day Recycle Bin.

        The packet carries ``ItemNum`` (the count to move), ``Category`` and
        ``ItemIndex``; a partial count leaves the rest in the source slot.  Gil is never
        droppable, a worn copy has to come off first, and the Recycle Bin itself cannot
        be dropped into.  The reply clears/updates the source slot, fills the bin slot,
        and sends the all-bag sync so both containers redraw.
        """
        if len(p) < 0x0C:
            return
        quantity = struct.unpack_from("<I", p, 4)[0]
        container, slot = int(p[8]), int(p[9])
        owner = int(self.char["id"])
        log.info("%s recycles %d of %d:%d", self.addr, quantity, container, slot)
        if container == 0 and slot == 0:
            self.say("You cannot throw away gil.")
            return
        if container == CONTAINER_RECYCLE:
            self.say("That item is already in the Recycle Bin.")
            return
        if any((int(c), int(s)) == (container, slot)
               for c, s, _item in self.equipped.values()):
            self.say("You cannot throw away something you are wearing.")
            return
        row = next((item for item in self.world.service.inventory(owner)
                    if int(item["container"]) == container and int(item["slot"]) == slot), None)
        if row is None:
            self.say("You do not have that item.")
            return
        name = str(row.get("name") or "item")
        have = int(row["quantity"])
        dropped = self.world.service.drop_item(owner, container, slot, quantity)
        if dropped is None:
            self.say("You do not have that item.")
            return
        if dropped.get("recycle_full"):
            self.say("The Recycle Bin is full; %s stays in your bag." % name)
            return
        left = int(dropped["quantity"])
        recycled = int(dropped.get("recycled") or 0)
        self.queue.append(sub(0x020, packets.item_attr(
            int(dropped["item_id"]) if left else 0, left, container, slot,
            extra=bytes(row.get("extra") or b"") if left else b"")))
        self.queue.append(sub(0x020, packets.item_attr(
            int(dropped["item_id"]), recycled, CONTAINER_RECYCLE,
            int(dropped["recycle_slot"]),
            extra=bytes(row.get("extra") or b""))))
        self.queue.append(self.container_sync())
        if left:
            self.say("Moved %d %s to the Recycle Bin; %d stayed in your bag." % (
                recycled, name, left))
        else:
            self.say("Moved %s to the Recycle Bin for 30 days." % name)

    def item_stack(self, p: bytes) -> None:
        """C2S 0x03A: the client sorted one bag; combine its partial stacks.

        The client handles the ordering itself but cannot merge two partial stacks, so it
        asks the server to do that.  Reply with the final quantity in every changed slot,
        an empty item for every slot the merge freed, and the usual all-bag sync.
        """
        if len(p) < 8:
            return
        container = struct.unpack_from("<I", p, 4)[0]
        if not 0 <= container <= 255:
            return
        log.info("%s sorts container %d", self.addr, container)
        for changed in self.world.service.stack_container(self.char["id"], container):
            self.queue.append(sub(0x020, packets.item_attr(
                int(changed["item_id"]), int(changed["quantity"]),
                int(container), int(changed["slot"]),
                extra=bytes(changed.get("extra") or b""))))
        self.queue.append(self.container_sync())

    def container_items(self, container: int, clear_slot: int | None = None) -> list[Msg]:
        """Every item in one container as 0x020 (plus an explicit empty slot if asked)."""
        out = []
        for item in self.world.service.inventory(self.char["id"]):
            if int(item["container"]) != int(container):
                continue
            out.append(self.item_packet(item))
        if clear_slot is not None:
            out.append(sub(0x020, packets.item_attr(0, 0, int(container), int(clear_slot))))
        return out

    def refresh_inventory(self) -> None:
        for item in self.world.service.inventory(self.char["id"]):
            if int(item["container"]) == 0:
                self.queue.append(self.item_packet(item))
        self.queue.append(self.container_sync())

    def equip_initial(self, bags: tuple[int, ...] = (0,)) -> None:
        """Equip a coherent outfit for this job, preferring one complete armour set.

        Taking the first eligible item per slot mixed sets -- the relic gown with the artifact
        sleeves -- which draws each slot from a different model group and looks broken.  Pick the
        set model that covers the most armour slots and wear that one, then fill the rest.

        Slots that already hold something are left alone, so this is safe to call again after a
        job change has stripped the old job's gear.

        The outfit the player last wore is stored per character and restored first: picking
        gear again on every login would silently undo every equipment change.  ``bags``
        limits the search; a job change passes ``AUTO_EQUIP_BAGS`` so wardrobe sets count.
        """
        items = self.world.service.inventory(self.char["id"])
        if not self.equipped and self.restore_equipment():
            # An outfit saved by an older build can hold a 2H main and an off-hand
            # weapon.  Fix it on the way in, before the grap list is built.
            if self._enforce_weapon_pair(items):
                self.store_equipment()
            return
        by_kind: dict[int, list[dict]] = {}
        for item in items:
            if int(item["container"]) not in bags:
                continue
            kind = EQUIP_SLOTS.get(str(item.get("equip_slot") or ""))
            if kind is None:
                continue
            if self._equip_blocked_reason(item, kind) is not None:
                continue
            by_kind.setdefault(kind, []).append(item)

        for options in by_kind.values():
            # Highest required level first, then exact job gear, then all-job pieces,
            # then multi-job gear.  Otherwise a starter Onion Sword in the inventory
            # beat the job's own weapon sitting in a wardrobe.
            options.sort(key=self._equip_priority)

        armour_kinds = (4, 5, 6, 7, 8)
        job_mask = 1 << (int(self.char.get("main_job") or 1) - 1)
        group_kinds: dict[str, set[int]] = {}
        group_exact: dict[str, bool] = {}
        for kind in armour_kinds:
            for item in by_kind.get(kind, []):
                group = self._armour_group(item)
                if not group:
                    continue
                group_kinds.setdefault(group, set()).add(kind)
                if int(item.get("jobs") or 0) == job_mask:
                    group_exact[group] = True
        # Most covered slots wins; a job-exclusive set beats an all-job set with the
        # same coverage, and the name makes the final tie stable.  Counting distinct
        # slots matters because a wardrobe can hold several copies of one piece.
        best_group = min(
            group_kinds,
            key=lambda name: (-len(group_kinds[name]), 0 if group_exact.get(name) else 1,
                              name)) if group_kinds else ""

        for kind in sorted(by_kind):
            if kind in self.equipped:
                continue
            options = by_kind[kind]
            if kind == 1:
                # A two-handed main leaves only a grip; a one-handed or empty main
                # leaves weapons and shields, never a grip.
                main = self._equipped_item(0, items)
                options = [item for item in options
                           if self._two_handed(main) == self._is_grip(item)]
                if not options:
                    continue
            chosen = options[0]
            if kind in armour_kinds and best_group:
                for item in options:
                    if self._armour_group(item) == best_group:
                        chosen = item
                        break
            self.equipped[kind] = (int(chosen["container"]), int(chosen["slot"]),
                                   int(chosen["item_id"]))
            self._apply_equip_model(kind, chosen)
            self.refresh_vitals()
            log.info("%s auto-equip kind=%d item=%d (%s) model=%s bag=%d", self.addr, kind,
                     int(chosen["item_id"]), chosen.get("name"), chosen.get("model"),
                     int(chosen["container"]))
        # A main picked just now can make an already-equipped sub slot illegal.
        self._enforce_weapon_pair(items)
        self.persist_equipment()

    @staticmethod
    def _armour_group(item: dict) -> str:
        """The set name an armour piece belongs to: 'Erilaz Surcoat +3' -> 'Erilaz'."""
        return str(item.get("name") or "").strip().split(" ", 1)[0]

    def _equip_priority(self, item: dict) -> tuple[int, int]:
        """Sort key for auto-equip: higher level first, then exact job gear, then all-job."""
        jobs = int(item.get("jobs") or 0)
        job = int(self.char.get("main_job") or 1)
        mask = 1 << (job - 1)
        if jobs == mask:
            tier = 0
        elif jobs == 0:
            tier = 1
        else:
            tier = 2
        return -int(item.get("level") or 1), tier

    def store_equipment(self) -> None:
        """Write the current outfit back to the database."""
        try:
            self.world.service.save_equipment(self.char["id"], self.equipped)
        except Exception as exc:
            log.warning("%s could not save the outfit: %s", self.addr, exc)

    def persist_equipment(self) -> None:
        self.store_equipment()

    def restore_equipment(self) -> bool:
        """Put the stored outfit back on, if this job can still wear it.

        Returns True when anything was restored; slots whose item moved out of the
        inventory slot we recorded fall through to the normal auto-equip pick.
        """
        try:
            rows = self.world.service.equipment(self.char["id"])
        except Exception:
            return False
        if not rows:
            return False
        bag = {(int(item["container"]), int(item["slot"])): item
               for item in self.world.service.inventory(self.char["id"])}
        restored = 0
        for row in rows:
            kind = int(row["kind"])
            container, slot = int(row["container"]), int(row["slot"])
            item = bag.get((container, slot))
            if item is None or int(item["item_id"]) != int(row["item_id"]):
                continue
            if self._equip_blocked_reason(item, kind) is not None:
                continue
            self.equipped[kind] = (container, slot, int(row["item_id"]))
            self._apply_equip_model(kind, item)
            restored += 1
            log.info("%s restored kind=%d item=%d (%s)", self.addr, kind,
                     int(row["item_id"]), item.get("name"))
        return restored > 0

    def _model_item(self, want: str) -> dict | None:
        """The inventory or Magic Bag row whose name contains *want*.

        ``//model`` used to look only at the bag (container 0); gear parked in a
        wardrobe or in the Magic Bag (the hidden 9,999-slot locker) then answered
        "no inventory item matching that name" even though the client listed it.
        The model is stored per item id, so where the copy sits does not matter.
        """
        for row in self.world.service.inventory(self.char["id"]):
            if want in str(row.get("name") or "").casefold():
                return row
        for row in self.world.service.locker_items(self.char["id"]):
            if want in str(row.get("name") or "").casefold():
                return row
        return None

    def _set_model(self, item_id: int, model: int, name: str) -> None:
        """Store a look id for an item and push it to the client for this session."""
        self.world.service.set_item_model(int(item_id), int(model))
        self.refresh_character()
        for kind, (container, slot, equipped_id) in list(self.equipped.items()):
            if int(equipped_id) == int(item_id):
                # Keep the inventory row's skill: a H2H model has to be mirrored into
                # the sub look, and a bare {"model": n} would lose that.
                look = dict(self._equipped_item(kind) or {})
                look["model"] = int(model)
                self._apply_equip_model(kind, look)
        self.queue.append(self.grap_list())
        self.say("%s now uses model %d (re-equip it to redraw; //modelnext for the "
                 "next one)." % (name, int(model)))

    def _apply_equip_model(self, kind: int, item: dict) -> None:
        """Put the item's visual model into the character's grap list."""
        model = int(item.get("model", 0) or 0)
        if not model:
            # A weapon slot must clear even when the item has no grap of its own: a grip
            # is invisible, and keeping the previous model is exactly how an old dagger
            # stayed on the hip after a two-handed sword was equipped.  Armour keeps the
            # previous look when its model is missing (an unknown piece is less wrong
            # than a naked slot), but a stale weapon is never acceptable.
            if kind in (0, 1, 2):
                self._clear_equip_model(kind)
            if 0 <= kind <= 8 and not self._is_grip(item):
                log.warning("%s equipped %s in slot %d with no grap model: it will not show",
                            self.addr, item.get("name", "?"), kind)
            return
        if kind == 0:
            self.char["main"] = model
            # Retail's H2H look carries the same model in the sub slot with the +0x1000
            # "left fist" tag (LandSandBoat's charutils.cpp).  Fanxi's looks() adds the
            # slot's 0x7000 itself, so the stored sub look is model + 0x1000 and the
            # wire value becomes model + 0x8000.  Without that entry the client draws
            # only the main-hand knuckle and plays only the right-hand punch.
            if self._is_h2h(item):
                self.char["sub"] = model + 0x1000
            elif 1 not in self.equipped:
                # A different main hand must remove the left-fist copy, but a real sub
                # item (shield, grip, off-hand weapon) keeps its own model.
                self.char["sub"] = 0
        elif kind == 1:
            self.char["sub"] = model
        elif kind == 2:
            self.char["ranged"] = model
        elif kind == 4:
            self.char["head"] = model
        elif kind == 5:
            self.char["body"] = model
        elif kind == 6:
            self.char["hands"] = model
        elif kind == 7:
            self.char["legs"] = model
        elif kind == 8:
            self.char["feet"] = model

    def _clear_equip_model(self, kind: int) -> None:
        if kind == 0:
            self.char["main"] = 0
            # The left-fist copy lives in the sub look but is not a sub item.  Leave a
            # real sub item's model alone; only clear the mirror when the hand is empty.
            if 1 not in self.equipped:
                self.char["sub"] = 0
            return
        if kind == 1:
            # Removing a shield or off-hand weapon from an H2H main hand restores the
            # mirrored left fist instead of leaving that hand bare.
            main = self._equipped_item(0)
            main_model = int(self.char.get("main") or 0)
            self.char["sub"] = (main_model + 0x1000
                                if main_model and self._is_h2h(main) else 0)
            return
        for key, slot in (("ranged", 2), ("head", 4), ("body", 5),
                          ("hands", 6), ("legs", 7), ("feet", 8)):
            if slot == kind:
                self.char[key] = 0

    @staticmethod
    def _is_h2h(item: dict | None) -> bool:
        """True when the item is a hand-to-hand weapon (skill id 1)."""
        return bool(item) and int(item.get("skill") or 0) == combat.H2H_SKILL

    @staticmethod
    def _is_grip(item: dict | None) -> bool:
        """A grip is the only sub item that can share hands with a two-handed weapon."""
        name = str(item.get("name") or "").strip().casefold() if item else ""
        # Most grips say "Grip" in the name; Khonsu is the Sortie grip that does not.
        return bool(name) and (name.endswith("grip") or name == "khonsu")

    @staticmethod
    def _two_handed(item: dict | None) -> bool:
        """True when a main weapon fills both hands (H2H is not in this set)."""
        return bool(item) and int(item.get("skill") or 0) in BOTH_HANDS_SKILLS

    def _equipped_item(self, kind: int, items: list[dict] | None = None) -> dict | None:
        """The inventory row behind an equipped slot, if the item is still in a bag."""
        entry = self.equipped.get(kind)
        if entry is None:
            return None
        container, slot, item_id = (int(value) for value in entry)
        rows = items if items is not None else self.world.service.inventory(self.char["id"])
        for item in rows:
            if (int(item["container"]) == container and int(item["slot"]) == slot
                    and int(item["item_id"]) == item_id):
                return item
        # The item may have been moved between bags since it was worn.
        return next((item for item in rows if int(item["item_id"]) == item_id), None)

    def geomancy_plus(self) -> int:
        """The character's Geomancy+ level from the worn weapons.

        Idris is Geomancy +10, but the item has no ``item_mods`` row for it: the live
        server scripts the bonus.  Read the equipped item ids so a player GEO gets the
        same Idris column the Trust path already uses for Sylvie.
        """
        items = {int(entry[2]) for entry in self.equipped.values() if entry}
        return (geomancy.IDRIS_GEOMANCY_PLUS
                if items & geomancy.IDRIS_ITEM_IDS else 0)

    def _weapon_pair_error(self, item: dict, kind: int,
                           items: list[dict] | None = None) -> str | None:
        """Why a sub item cannot share the hands with the main weapon, or None."""
        if kind != 1:
            return None
        main = self._equipped_item(0, items)
        if self._is_grip(item) and not self._two_handed(main):
            return "A grip can only be used with a two-handed weapon."
        if not self._is_grip(item) and self._two_handed(main):
            return "You cannot use an off-hand item with a two-handed weapon."
        return None

    def _clear_slot(self, kind: int, reason: str) -> None:
        """Take one slot off and tell the client to forget its model."""
        self.equipped.pop(kind, None)
        self._clear_equip_model(kind)
        self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, 0)))
        self.note_equipment_change()
        if kind in (0, 1, 2):
            self._drop_aftermath()
        log.info("%s cleared equipment slot %d: %s", self.addr, kind, reason)

    def _enforce_weapon_pair(self, items: list[dict] | None = None) -> bool:
        """Drop a sub item that cannot legally share the hands with the main weapon."""
        rows = items if items is not None else self.world.service.inventory(self.char["id"])
        sub_item = self._equipped_item(1, rows)
        if sub_item is None:
            if 1 in self.equipped:
                self._clear_slot(1, "its item is no longer in a bag")
                return True
            return False
        main = self._equipped_item(0, rows)
        if self._is_grip(sub_item) and not self._two_handed(main):
            self._clear_slot(1, "a grip needs a two-handed main")
            return True
        if not self._is_grip(sub_item) and self._two_handed(main):
            self._clear_slot(1, "the main weapon fills both hands")
            return True
        return False

    def _equip_blocked_reason(self, item: dict, kind: int) -> str | None:
        """Slot, job and level rules from LSB's item_equipment (slot_mask/jobs columns)."""
        name = str(item.get("name") or "That item")
        mask = int(item.get("slot_mask") or 0)
        if mask and not (mask & (1 << kind)):
            return "%s cannot be equipped in that slot." % name
        jobs = int(item.get("jobs") or 0)
        job = int(self.char.get("main_job") or 1)
        if jobs and not (jobs & (1 << (job - 1))):
            return "%s is not for your job." % name
        if int(item.get("level") or 1) > int(self.char.get("main_level") or 1):
            return "%s requires a higher level." % name
        return None

    def _unequip_all(self, reason: str) -> int:
        """Take every slot off so the job's worn gear can go onto its storage slips."""
        count = len(self.equipped)
        for kind in sorted(self.equipped):
            self.equipped.pop(kind, None)
            self._clear_equip_model(kind)
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, 0)))
        if count:
            self.note_equipment_change()
            log.info("%s unequipped %d slots (%s)", self.addr, count, reason)
        # An empty equipment table is what keeps equip_initial() from restoring the
        # outfit we just took off once the storage pull has run.
        self.store_equipment()
        return count

    def _unequip_invalid(self) -> None:
        """Take off the gear the new job cannot wear, as retail does on a job change.

        Gear worn out of a Mog Wardrobe is stored in that container, not the inventory,
        so every bag has to be searched: the old inventory-only lookup skipped every
        wardrobe piece and left the previous job's weapon on the character.
        """
        items = self.world.service.inventory(self.char["id"])
        bag = {(int(item["container"]), int(item["slot"])): item for item in items}
        by_id = {int(item["item_id"]): item for item in items}
        changed = False
        for kind, (container, slot, item_id) in sorted(list(self.equipped.items())):
            item = bag.get((int(container), int(slot)))
            if item is None or int(item["item_id"]) != int(item_id):
                item = by_id.get(int(item_id))
                if item is None:
                    # The item left the bags entirely; clear the slot rather than
                    # drawing a weapon that no longer exists.
                    self._clear_slot(kind, "its item is no longer in a bag")
                    changed = True
                    continue
                # Follow an item that was moved between bags while it was worn.
                self.equipped[kind] = (int(item["container"]), int(item["slot"]), int(item_id))
            if self._equip_blocked_reason(item, kind) is None:
                continue
            self.equipped.pop(kind, None)
            self._clear_equip_model(kind)
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, 0)))
            if kind in (0, 1, 2):
                self._drop_aftermath()
            log.info("%s unequipped %s (slot %d) for the new job", self.addr,
                     item.get("name"), kind)
            changed = True
        if self._enforce_weapon_pair(items):
            changed = True
        if changed:
            self.store_equipment()

    def _resend_slot(self, kind: int) -> None:
        """Send the slot's current contents back so an invalid pick snaps back."""
        current = self.equipped.get(kind)
        slot, container = (current[1], current[0]) if current else (0, 0)
        self.queue += [sub(0x050, struct.pack("<BBBx", slot, kind, container)), self.grap_list()]

    def equipment_packets(self) -> list[Msg]:
        self.equip_initial()
        return [sub(0x050, struct.pack("<BBBx", slot, kind, container))
                for kind, (container, slot, _item) in sorted(self.equipped.items())]

    def equipset_check(self, p: bytes) -> None:
        """C2S 0x052: the client is assembling an equipment set.

        Before it applies a change from the equipment window it sends the whole proposed
        16-slot set here and waits for 0x116.  With no answer the window keeps the old
        gear: the confirm key looks dead.  Echo the set back with the requested change
        applied; the client then sends 0x050 for the slots that actually differ.
        """
        if len(p) < 8:
            log.info("%s equipset check short (%d bytes): %s", self.addr, len(p), bytes(p).hex())
            return
        body = bytes(p[4:]).ljust(72, b"\0")
        kind = body[0] & 0x0F
        change = body[4:8]
        entries = [bytearray(body[8 + i * 4:12 + i * 4]) for i in range(16)]
        has = change[0] & 1
        remove = (change[0] >> 1) & 1
        category = (change[0] >> 2) & 0x3F
        item_id = struct.unpack_from("<H", change, 2)[0]
        if kind < 16:
            if remove or not has or item_id == 0:
                entries[kind] = bytearray(4)
            else:
                entries[kind] = bytearray((1 | (category << 2), change[1],
                                           item_id & 0xFF, (item_id >> 8) & 0xFF))
        out = b"".join(bytes(entry) for entry in entries) + bytes(4)
        self.queue.append(sub(0x116, out))
        log.info("%s equipset check kind=%d item=%d has=%d remove=%d -> 0x116",
                 self.addr, kind, item_id, has, remove)

    def settle_equipment(self) -> None:
        """Apply a batch's outfit to the server's numbers; send nothing yet.

        Called as each datagram is read.  An action can share that datagram with its
        precast 0x050s (the phase engine does this), and the damage roll and the Prime
        "Adds weapon skill" grant both read the saved outfit, so the state cannot wait
        for the burst to settle even though the look/stat packets can.
        """
        if not self.equipment_changed or self.equipped == self._settled_outfit:
            return
        self.store_equipment()
        # The new outfit's HP/MP are part of the maxima, and the stats packet this batch
        # ends with has to agree with them.  Refreshing here is also what lets the passive
        # Regen/Refresh tick reach a cap the swap raised: without it ``char["hp"]`` stayed
        # at the old outfit's maximum, so the tick saw "already full" and did nothing while
        # the client still drew the missing points.
        self.refresh_vitals()
        self._settled_outfit = dict(self.equipped)

    def note_equipment_change(self, now: float | None = None) -> None:
        """One slot changed: arm the follow-up for when the burst settles."""
        now = time.time() if now is None else float(now)
        if not self.equipment_changed:
            self.equip_sync_deadline = now + EQUIP_SYNC_MAX_DELAY
        self.equipment_changed = True
        self.equip_sync_at = min(now + EQUIP_SYNC_DELAY, self.equip_sync_deadline)

    def flush_equipment(self) -> None:
        """Send the follow-up now: the burst settled, or an action needs it first."""
        if not self.equipment_changed:
            return
        self.settle_equipment()
        self.equipment_changed = False
        self.queue += self.equipment_sync()
        # Changing gear while engaged makes the client drop its battle stance: the animation
        # byte rides in the General block of 0x00D, and nothing re-sends it after an equip, so
        # the character stands there with the weapon sheathed while still engaged.
        self.assert_stance()

    def assert_stance(self) -> None:
        """Draw the weapon again while the server still has the player engaged.

        The client sheathes to cast, and a refused cast (no MP, no target) sends no result
        packet to put the weapon back.  The assist target (0x058) and the General animation
        in 0x00D are what draw it, so both are re-sent; the phase engine follows the same
        0x00D, which keeps its engaged state honest when the client drops the stance.

        This is the event path (engage, a cast result, an equipment batch); the routine
        keeping the stance up is `refresh_stance`, called from the tick.
        """
        if not self.engaged_id:
            return
        target = self.world.entity_by_id(self.zone, int(self.engaged_id))
        if target is not None:
            self.queue.append(sub(0x058, struct.pack(
                "<IIHH", int(self.char["char_id"]), int(target.id),
                int(self.char.get("targid", 0x400)), 0)))
        self.refresh_stance()

    def refresh_stance(self) -> None:
        """Re-send the battle stance without the assist target.

        The client drops the drawn-weapon pose within about a second of any animation (a
        swing, a flinch, a cast), and the General block of 0x00D is what puts it back.  A
        draw every half second keeps the weapon out; the ten-second refresh left it down
        almost all the time, and two draws spaced apart made it flicker.
        """
        if not self.engaged_id:
            return
        self.queue.append(self.char_update(packets.SEND_HP))
        self.stance_at = time.time()

    def disengage(self, message: str | None = None) -> None:
        """Break the engagement and sheathe.

        Every deliberate path comes here: //disengage, /attack off, a target that died or
        left, going beyond ENGAGE_RANGE, healing, death and a zone change.  The engagement
        belongs to the server, but the client is never left holding a stance it cannot
        drop: the one packet the client emits on its own (the range drop) is absorbed in
        `attack_off`, once, and everything else disengages here.
        """
        if self.engaged_id and message:
            self.say(message)
        self.engaged_id = None
        self.engaged_targid = 0
        self.client_range_drop = False
        self.queue.append(self.char_update(packets.SEND_HP))

    def engaged_target(self):
        """The live entity this session is engaged to, or None."""
        if not self.engaged_id:
            return None
        return self.world.entity_by_id(self.zone, int(self.engaged_id))

    def target_effect_report(self, entity_id: int = 0) -> dict:
        """The current target's live debuffs, for the HUD's Target Debuffs window.

        The client has no monster buff list, so the server is the only place that knows
        what Dia/Frazzle/DoTs are actually on the mob.  ``entity_id`` is the client's
        target ServerId, which is the world entity id; when it is absent the server's
        own target targid is used.  Only effects with time left are returned, and the
        hidden secondary rows (a Threnody's Magic Evasion down beside the song icon) are
        marked so the window can show the spell instead of a duplicate icon.
        """
        entity = None
        if int(entity_id or 0):
            entity = self.world.entity_by_id(self.zone, int(entity_id))
        if entity is None:
            targid = int(self.target_targid or self.engaged_targid or 0)
            if targid:
                entity = self.world.entity_by_targid(self.zone, targid)
            if entity is None:
                entity = self.engaged_target()
        if entity is None or getattr(entity, "kind", "") != "mob" or not entity.alive:
            return {"target": None, "effects": []}
        now = time.time()
        effects = []
        for effect_id, state in list(entity.effect_state.items()):
            until = float(state.get("until") or 0.0)
            remaining = max(0.0, until - now)
            if remaining <= 0.0:
                continue
            effects.append({
                "id": int(effect_id),
                "icon": int(state.get("icon") or effect_id),
                "name": str(state.get("name") or ""),
                "remaining": round(remaining, 1),
                "power": int(state.get("power") or 0),
                "potency": int(state.get("potency") or 0),
                "tick": int(state.get("tick") or 0),
                "tick_interval": float(state.get("tick_interval") or 0.0),
                "hidden": bool(state.get("hidden")),
                "source": int(state.get("source") or 0),
            })
        effects.sort(key=lambda row: (row["name"].casefold(), row["id"]))
        hpp = 100.0 * float(entity.hp) / max(1.0, float(entity.hp_max))
        return {
            "target": {
                "id": int(entity.id),
                "name": str(entity.name),
                "hpp": round(hpp, 1),
                "distance": round(float(entity.distance_to(*self.pos[:3])), 2),
            },
            "effects": effects,
        }

    @staticmethod
    def _sync_signature(message: Msg) -> bytes:
        """The state a derived packet carries, with its clock fields taken out.

        0x037 carries the Vana'diel clock and the unix stamp, both of which move every
        packet; comparing the whole body would always look like a change.  Everything
        else is derived from the outfit, the job pair or the buff list.
        """
        body = bytes(message[4:])
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x037:
            body = body[:0x38] + body[0x40:]
        return body

    def _note_sent_sync(self, message: Msg) -> None:
        """Remember a derived packet as the copy the client holds.

        Called from pack() for every copy that actually leaves, so the zone-in bundle,
        the 0x061 reply and ``//abilities`` all seed the baseline and equipment_sync()
        compares against what the client really has rather than against a second guess.
        """
        ptype = struct.unpack_from("<H", message, 0)[0] & 0x1FF
        if ptype in EQUIP_SYNC_TYPES:
            self._sync_sent[ptype] = self._sync_signature(message)

    def equipment_sync(self) -> list[Msg]:
        """The follow-up a gear burst owes: only the parts whose payload changed.

        Looks, spell bits, the ability tables, command data and the stat sheet are all
        derived from the outfit, and the client shows each slot as its own 0x050 echo
        arrives.  Sending the whole block per batch made every swap about a kilobyte the
        client had to digest one packet per ack, and the 0x0AC copy makes host64 rewrite
        its whole ability list -- the last line it logged before each client freeze.  A
        part whose payload is unchanged from the copy the client already holds is dropped
        here: an armour swap keeps the job-derived blocks, and only a weapon whose skill
        type (or item-granted skill) changes rewrites the command data.
        """
        parts = [
            self.grap_list(),                # the models of everything now worn
            sub(0x0AA, self.spell_bits()),          # magic data, as retail re-sends on a gear change
            self.char_feats(),               # the 160-bit job ability table
            self.char_abilities(),           # command data
            self.char_commands(),            # and the incremental 0x1A5 update
            self.char_stats(), self.char_status(),
        ]
        out: list[Msg] = []
        now = time.time()
        for message in parts:
            ptype = struct.unpack_from("<H", message, 0)[0] & 0x1FF
            signature = self._sync_signature(message)
            if self._sync_sent.get(ptype) == signature:
                continue
            if ptype == 0x0AC and now - self._commands_sent_at < EQUIP_COMMANDS_MIN_GAP:
                # Coalesce a burst of weapon swaps into one ability-list rewrite.  The sent
                # signature is left alone, so the tick (or the next settle) sends the final
                # list once the gap has passed.
                self._commands_pending = True
                continue
            if ptype == 0x0AC:
                self._commands_sent_at = now
                self._commands_pending = False
            self._sync_sent[ptype] = signature
            out.append(message)
        return out

    def equip(self, p: bytes) -> None:
        """C2S 0x050: the client changed one equipment slot."""
        log.info("%s equip raw (%d bytes): %s", self.addr, len(p), bytes(p).hex())
        # 4-byte sub-message header + 3 bytes (PropertyItemIndex, EquipKind, Category).
        if len(p) < 7:
            return
        slot, kind, category = int(p[4]), int(p[5]), int(p[6])
        log.info("%s equip request len=%d slot=%d kind=%d cat=%d", self.addr, len(p), slot, kind, category)
        if category == CONTAINER_RECYCLE:
            self.say("Take that item out of the Recycle Bin before wearing it.")
            return
        if slot == 0:  # the client's "remove from this slot" form
            self.equipped.pop(kind, None)
            self._clear_equip_model(kind)
            # The grap list has to lose the model too: a reply that still says the old
            # weapon is in the slot makes the client treat the unequip as failed and it
            # never sends the follow-up 0x050 that puts the new item on.
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, category)))
            self.note_equipment_change()
            if kind in (0, 1, 2):
                self._drop_aftermath()
            if kind == 0:
                self._enforce_weapon_pair()
            return
        items = self.world.service.inventory(self.char["id"])
        item = next((i for i in items
                     if int(i["container"]) == category and int(i["slot"]) == slot), None)
        if item is None:  # unequip
            self.equipped.pop(kind, None)
            self._clear_equip_model(kind)
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, category)))
            self.note_equipment_change()
            if kind in (0, 1, 2):
                self._drop_aftermath()
            if kind == 0:
                self._enforce_weapon_pair(items)
            return
        item_id, quantity = int(item["item_id"]), int(item["quantity"])
        # One inventory copy can only occupy one slot, and a Rare item cannot be
        # worn twice even if a database somehow holds two copies.  Without this the
        # client could put the same Carnwenhan in main and sub and the server would
        # happily store both rows.  Ex alone does not stop two copies being worn:
        # it only stops them being traded.
        duplicate = None
        for other_kind, (other_container, other_slot, other_item) in self.equipped.items():
            if int(other_kind) == int(kind):
                continue
            if (int(other_container), int(other_slot)) == (int(category), int(slot)):
                duplicate = "That item is already equipped."
                break
            if int(item.get("rare") or 0) and int(other_item) == item_id:
                duplicate = "%s is Rare and is already equipped." % item.get("name", "That item")
                break
        problem = (duplicate or self._equip_blocked_reason(item, kind)
                   or self._weapon_pair_error(item, kind, items))
        if problem:
            log.info("%s refused equip slot=%d kind=%d item=%d: %s", self.addr, slot, kind,
                     item_id, problem)
            self.say(problem)
            self._resend_slot(kind)
            return
        log.info("%s equip slot=%d kind=%d cat=%d item=%d %s", self.addr, slot, kind,
                 category, item_id, item.get("name"))
        # A gear burst re-sends every slot of the set, the worn weapon included.  That is
        # not a weapon change: retail drops the aftermath when the worn weapon is replaced
        # or taken off, so compare against the copy that is already in the slot rather
        # than against the packet.  Without this the phase engine's post-WS TP set removed
        # the Prime Aftermath about a second after granting it.
        previous = self.equipped.get(kind)
        same_copy = (previous is not None
                     and tuple(int(value) for value in previous)
                     == (int(category), int(slot), int(item_id)))
        self.equipped[kind] = (category, slot, item_id)
        self._apply_equip_model(kind, item)
        self.queue += [
            sub(0x050, struct.pack("<BBBx", slot, kind, category)),
            self.item_packet(item, container=category, slot=slot),
        ]
        self.note_equipment_change()
        if kind in (0, 1, 2) and not same_copy:
            # A real main/sub/ranged weapon change drops the aftermath.  Armour and ammo
            # swaps leave it alone.
            self._drop_aftermath()
        if kind == 0:
            # A two-handed main makes the old sub item illegal; take it off now so the
            # client and the server agree on the hands.
            self._enforce_weapon_pair(items)

    def refresh_character(self) -> None:
        row = self.world.service.character(self.char["id"])
        if row:
            for key, value in row.items():
                self.char[key] = value
            # A job change swaps the whole job-ability block; re-send it with the stats.
            self.queue += [self.char_stats(), self.char_status(), self.party_member(),
                           self.char_feats(), self.char_abilities(), self.char_commands(),
                           self.char_skills(), self.abil_recast()]

    def reload_character(self) -> None:
        """Re-read the persisted row and re-send everything the Data page can change.

        The launcher writes SQLite through the HTTP API; a running client still holds
        the old merits, gil, mastery rank and inventory.  This is the live half: the
        same row the zone-in burst would have used, packed again.  It is safe to call
        when nothing changed, which is why the launcher sends it after every card action.
        """
        try:
            row = self.world.service.character(int(self.char["id"]))
            self.char.update(self.world.character_record(row))
            self._merit_counts = None
        except Exception as exc:
            log.warning("%s character reload failed: %s", self.addr, exc)
            return
        self.refresh_vitals()
        # A self 0x00D is deliberately left out.  After a reload the client asks for its
        # own entity (C2S 0x016/0x017); a full-spawn reply carries the name/model blocks
        # and resets the player entity, which is the green-name/NPC state that cannot act
        # until a relog.  0x061, 0x037 and 0x0DF already carry the max/current vitals the
        # Data page can change, so no entity update is needed here.
        packets_out = [
            self.job_info(), self.char_stats(), self.char_status(),
            self.party_member(), self.char_sync(),
            self.char_skills(), sub(0x0AA, self.spell_bits()),
            self.merits(), *self.merit_list(), self.job_points(), self.job_points_detail(),
        ]
        packets_out += [sub(0x055, KEY_ITEM_BITS[table] + KEY_ITEM_BITS[table] +
                            struct.pack("<HH", table, 0)) for table in range(7)]
        packets_out += self.inventory_packets()
        self.queue += packets_out

    def queue_action(self, target_id: int, damage: int = 0, *, miss: bool = False,
                     critical: bool = False, defeated: bool = False,
                     actor_id: int | None = None, animation: int = 0,
                     message: int | None = None, kind: int = 1,
                     category: int = packets.ACTION_CATEGORY_BASIC_ATTACK,
                     info: int | None = None, action_id: int | None = None,
                     results: list[dict] | None = None,
                     broadcast: bool = False, not_before: float = 0.0) -> None:
        """Queue one 0x028 action for ``target_id``.

        ``results`` packs several hits into that single action, which is how a melee
        round carries both hands and a multi-hit weapon skill carries its own hits: the
        client plays them in list order from the target's result count.  Without it the
        single-result keywords describe the one hit.
        """
        actor = int(actor_id if actor_id is not None else self.char["char_id"])
        if results is None:
            results = [dict(damage=damage, miss=miss, critical=critical,
                            defeated=defeated, animation=animation,
                            message=message, info=info)]
        max_hp = max(1, int(getattr(self, "_last_target_hp", 100)))
        prepared = []
        for result in results:
            hit_miss = bool(result.get("miss", False))
            hit_damage = int(result.get("damage", 0))
            if hit_damage > combat.DAMAGE_CAP:
                # Every damage path clips where it builds the number, so this should
                # never fire; keep it as the last line of defence and log the path that
                # would otherwise put a six-digit number on the wire.
                log.warning("%s action damage %d clipped to %d",
                            self.addr, hit_damage, combat.DAMAGE_CAP)
                hit_damage = combat.DAMAGE_CAP
            distortion = int(result.get("hit_distortion", 0))
            if not hit_miss and hit_damage and result.get("message") is None:
                percent = hit_damage * 100 // max_hp
                distortion = 3 if percent >= 20 else 2 if percent >= 10 else 1
            prepared.append({**result, "damage": hit_damage, "miss": hit_miss,
                             "hit_distortion": distortion})
            log.info("%s action out: actor=%d target=%#x damage=%d miss=%s anim=%d msg=%s",
                     self.addr, actor, int(target_id), hit_damage, hit_miss,
                     int(result.get("animation", 0)), result.get("message", message))
        packet = sub(0x028, packets.battle_action(
            actor, int(target_id), kind=kind, category=category,
            message=message, info=info, results=prepared,
            action_id=(packets.BASIC_ATTACK_ID if action_id is None else int(action_id))))
        packet.not_before = max(0.0, float(not_before or 0.0))
        if packet.not_before:
            packet.after_packet = int(self.server_id)
        self.queue.append(packet)
        if broadcast:
            # Every other client in the zone needs the same result: a party member's
            # weapon skill is what shows the skillchain animation on the main screen.
            for observer in self.world.sessions_in_zone(self.zone):
                if observer is self:
                    continue
                if int(self.char.get("targid", 0)) not in getattr(
                        observer, "sent_targids", set()):
                    continue
                copy = Msg(packet)
                copy.not_before = packet.not_before
                copy.after_packet = packet.after_packet
                observer.queue.append(copy)

    def start_resting(self) -> None:
        if self.resting or self.casting or self.dead_until:
            return
        if int(self.char.get("hp_current", 0)) <= 0:
            return
        # /heal drops the attack, as it does in retail; otherwise the engaged check in
        # tick_rest would stop the rest on the next frame.
        if self.engaged_id:
            self.engaged_id = None
            self.engaged_targid = 0
            self.queue.append(self.char_update(packets.SEND_HP))
        self.resting = True
        self.next_rest_tick = time.time() + 3.0
        self.say("You begin resting.")
        self.queue.append(self.char_update(packets.SEND_HP))

    def stop_resting(self) -> None:
        if not self.resting:
            return
        self.resting = False
        self.next_rest_tick = 0.0
        self.say("You stop resting.")
        self.queue.append(self.char_update(packets.SEND_HP))

    def heal_command(self, p: bytes) -> None:
        """C2S 0x0E8: /heal.  Mode 0 toggles, 1 starts and 2 stops."""
        mode = struct.unpack_from("<I", p, 4)[0] if len(p) >= 8 else 0
        if mode == 2:
            self.stop_resting()
        elif mode == 1:
            self.start_resting()
        elif self.resting:
            self.stop_resting()
        else:
            self.start_resting()

    def tick_rest(self, now: float) -> None:
        """Rest recovery: a small HP/MP tick every three seconds while /heal is on."""
        if not self.resting:
            return
        if self.dead_until or self.casting or self.engaged_id:
            self.stop_resting()
            return
        if now < self.next_rest_tick:
            return
        self.next_rest_tick = now + 3.0
        hp = int(self.char.get("hp_current", 0))
        hp_max = max(1, int(self.char.get("hp", 1)))
        mp = int(self.char.get("mp_current", 0))
        mp_max = max(0, int(self.char.get("mp", 0)))
        # Clear Mind is the resting MP trait: its "MP while healing" value (3/6/9/12
        # at the RDM tiers) is added to the flat recovery.  It was in the trait table
        # but the rest tick ignored it.
        clear_mind = max(0, int(self.combat_mods().get(mod.MP_WHILE_HEALING, 0)))
        new_hp = min(hp_max, hp + max(1, hp_max // 20))
        new_mp = min(mp_max, mp + (max(1, mp_max // 20 + clear_mind) if mp_max else 0))
        if new_hp == hp and new_mp == mp:
            return
        self.char["hp_current"] = new_hp
        self.char["mp_current"] = new_mp
        self.queue += [self.char_status(), self.char_stats(), self.party_member()]
        try:
            self.world.service.save_vitals(int(self.char["id"]), new_hp, new_mp)
        except Exception:
            pass

    def tick_player_effects(self, now: float) -> None:
        """Expire self buffs and apply Regen/Refresh/Poison ticks."""
        changed = False
        food_expired = False
        if self.food.get("until") and now >= float(self.food["until"]):
            self.food = {"item_id": 0, "name": "", "until": 0.0, "mods": {}}
            changed = True
            food_expired = True
        if not self.effect_state and not changed:
            return
        for effect_id, state in list(self.effect_state.items()):
            until = float(state.get("until") or 0.0)
            if until and now >= until:
                self.effect_state.pop(effect_id, None)
                try:
                    self.status_effects.remove(effect_id)
                except ValueError:
                    pass
                changed = True
                icon = int(state.get("icon", effect_id))
                self.queue.append(sub(0x029, packets.battle_message(
                    int(self.char["char_id"]), int(self.char["char_id"]),
                    int(self.char.get("targid", 0x400)), int(self.char.get("targid", 0x400)),
                    icon, 0, packets.MESSAGE_STATUS_WEARS_OFF)))
                continue
            tick = int(state.get("tick") or 0)
            if tick <= 0 or now < float(state.get("next_tick") or 0.0):
                continue
            state["next_tick"] = now + 3.0
            if effect_id in (effects.REGEN, effects.TRUST_AURA_REGEN):
                hp = int(self.char.get("hp_current", 0))
                healed = min(int(self.char.get("hp", hp)), hp + tick)
                if healed != hp:
                    self.char["hp_current"] = healed
                    changed = True
            elif effect_id in (effects.REFRESH, effects.TRUST_AURA_REFRESH):
                mp = int(self.char.get("mp_current", 0))
                restored = min(int(self.char.get("mp", 0)), mp + tick)
                if restored != mp:
                    self.char["mp_current"] = restored
                    changed = True
            elif int(state.get("regain") or 0) > 0:
                # Tactician's Roll is a Regain (TP per tick), not a Refresh/Regen.
                tp = int(self.char.get("tp", 0))
                gained = min(TP_MAX, tp + int(state["regain"]))
                if gained != tp:
                    self.char["tp"] = gained
                    changed = True
            elif state.get("song") and int(state.get("song_effect", 0)) == effects.PAEON:
                hp = int(self.char.get("hp_current", 0))
                healed = min(int(self.char.get("hp", hp)), hp + tick)
                if healed != hp:
                    self.char["hp_current"] = healed
                    changed = True
            elif state.get("song") and int(state.get("song_effect", 0)) == effects.BALLAD:
                mp = int(self.char.get("mp_current", 0))
                restored = min(int(self.char.get("mp", 0)), mp + tick)
                if restored != mp:
                    self.char["mp_current"] = restored
                    changed = True
            elif effect_id == effects.SUBLIMATION:
                hp = int(self.char.get("hp_current", 0))
                stored = max(0, int(state.get("power") or 0))
                # 300 base, +3 a JP rank (60 at rank 20), +10 a Max Sublimation merit.
                cap = (300 + job_points.category_total(20, "Sublimation Effect")
                       + 10 * self._sch_merit(merits.SCH_MAX_SUBLIMATION))
                if hp > 1 and stored < cap:
                    self.char["hp_current"] = hp - 1
                    state["power"] = stored + 1
                    changed = True
            elif effect_id in (effects.POISON, effects.BIO, effects.PLAGUE):
                hp = int(self.char.get("hp_current", 0))
                self.char["hp_current"] = max(0, hp - tick)
                changed = True
                # The HP bar (char_status/char_stats below) is the feedback; a chat line
                # here would render "takes 0 points of damage" from 0x029, and a 0x028
                # action would play the character's casting animation every tick.
                if int(self.char["hp_current"]) <= 0:
                    self.hit_zero_hp(now)
                    break
        if changed:
            if food_expired:
                self.refresh_vitals()
            self.queue += [self.char_status(), self.char_stats(), self.party_member()]
            try:
                self.world.service.save_vitals(
                    int(self.char["id"]), int(self.char.get("hp_current", 0)),
                    int(self.char.get("mp_current", 0)))
            except Exception:
                pass

    def restore_vitals(self, refresh: bool = True) -> None:
        """Fill HP and MP to their maxima and persist them, as rest does.

        Used by //heal and by the Mog House; ``refresh`` queues the packets that redraw the
        bars.  A zone-in (on_login) passes False because its own bundle carries them.
        """
        self.char["hp_current"] = int(self.char["hp"])
        self.char["mp_current"] = int(self.char.get("mp", 0))
        try:
            self.world.service.save_vitals(
                self.char["id"], self.char["hp_current"], self.char["mp_current"])
        except Exception as exc:
            log.warning("%s vitals save failed: %s", self.addr, exc)
        if refresh:
            self.queue += [self.char_status(), self.char_stats(), self.party_member()]

    def clear_status_effects(self) -> None:
        """Take every status effect away; the next 0x037 (its 0xFF slots) removes the icons."""
        self.status_effects.clear()
        self.effect_state.clear()
        self.food = live_state.empty_food()

    # --- the reconnect snapshot -------------------------------------------------------

    def save_live_state(self, *, include_effects: bool = True,
                        now: float | None = None) -> bool:
        """Write the state a reconnect should get back (``char_live_state``).

        The tick calls this every ``LIVE_STATE_SAVE_INTERVAL`` seconds and the row is only
        written when the payload changed; ``World.evict_session`` calls it one last time on
        the way out.  A deliberate logout passes ``include_effects=False``: retail takes the
        buffs with you, but the ability cooldowns keep running.

        Returns True when a row was written.
        """
        if self.live_state_closed or not self.logged_in:
            return False
        now = time.time() if now is None else now
        self.live_state_checked_at = now
        if include_effects:
            payload = live_state.snapshot(
                self.effect_state, self.status_effects, self.food,
                self.ability_recasts, now)
        else:
            payload = live_state.snapshot({}, [], None, self.ability_recasts, now)
        signature = live_state.signature(payload)
        if signature == self.live_state_signature:
            return False
        try:
            self.world.service.save_live_state(int(self.char["id"]), payload)
        except Exception as exc:
            log.warning("%s reconnect snapshot not saved: %s", self.addr, exc)
            return False
        self.live_state_signature = signature
        return True

    def restore_live_state(self, *, include_effects: bool = True) -> None:
        """Put back what the server held for this character while it was offline.

        Only a fresh login restores: a zone change keeps the live session object, so its
        timers are already the running ones.  ``include_effects=False`` is the Mog House and
        K.O. path, where retail takes the buffs but keeps the ability cooldowns.
        """
        if not getattr(self, "fresh_login", False) or self.live_state_restored:
            return
        self.live_state_restored = True
        try:
            row = self.world.service.live_state(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s reconnect snapshot unavailable: %s", self.addr, exc)
            return
        if not row:
            return
        restored = live_state.restore(row, time.time())
        self.ability_recasts.clear()
        self.ability_recasts.update(restored.recasts)
        if include_effects:
            self.status_effects = list(restored.status_effects)
            self.effect_state = dict(restored.effect_state)
            self.food = dict(restored.food)
        else:
            restored.status_effects = []
            restored.effect_state = {}
            restored.food = live_state.empty_food()
        # Force the next tick to rewrite the row, which prunes whatever expired offline.
        self.live_state_signature = None
        if restored.effect_count or restored.recasts:
            self.live_state_notice = restored
            self.live_state_notice_at = 0.0
        log.info("%s reconnected: held %d buff(s) (%d song(s)) and %d recast(s)",
                 self.addr, restored.effect_count, restored.song_count,
                 len(restored.recasts))

    def _announce_live_state(self) -> None:
        """Tell the player what came back, after the zone-in burst is safely over."""
        restored = self.live_state_notice
        self.live_state_notice = None
        self.live_state_notice_at = 0.0
        if restored is None:
            return
        parts: list[str] = []
        if restored.song_count:
            parts.append("%d song(s)" % restored.song_count)
        other = restored.effect_count - restored.song_count
        if other:
            parts.append("%d buff(s)" % other)
        if restored.recasts:
            parts.append("%d ability recast(s)" % len(restored.recasts))
        welcome = "Welcome back. The server held %s while you were away." % _name_list(parts)
        self.say(welcome)
        log.info("%s %s", self.addr, welcome)
        soonest = restored.next_expiry()
        if soonest is not None:
            effect_id, until = soonest
            state = restored.effect_state.get(effect_id) or {}
            left = max(0, int(until - time.time()))
            if state.get("song_name"):
                self.say("%s has %d:%02d left." % (
                    state["song_name"], left // 60, left % 60))
            elif effect_id == effects.FOOD and restored.food.get("name"):
                self.say("%s has %d:%02d left." % (
                    restored.food["name"], left // 60, left % 60))
            else:
                # The state does not carry the spell that put an ordinary buff up, and
                # stat_report's label is only the first spell to share its icon, so do
                # not name the wrong one: the countdown is what matters here.
                self.say("Your shortest buff wears off in %d:%02d." % (
                    left // 60, left % 60))

    # --- status effects ---------------------------------------------------------------

    def has_effect(self, effect_id: int) -> bool:
        return int(effect_id) in self.effect_state

    def effect(self, effect_id: int) -> dict | None:
        return self.effect_state.get(int(effect_id))

    def effect_power(self, effect_id: int) -> int:
        state = self.effect_state.get(int(effect_id))
        return int(state.get("power", 0)) if state else 0

    def add_effect(self, effect_id: int, *, duration: float = 0.0, power: int = 0,
                   potency: int = 0, tick: int = 0, icon: int = 0,
                   mods: dict[int, int] | None = None,
                   song_base: float = 0.0, song_name: str = "",
                   song_cast_at: float = 0.0, song_effect: int = 0) -> None:
        """Record a player effect and put its icon in the next 0x037.

        The caller queues ``char_status()``; this only mutates the state so two effects
        landing in the same packet do not each send the client a partial list.  A song
        carries its unenhanced base in ``song_base``: that is what the overwrite and
        recast rules compare against, and it is also how the effect list knows which
        entries count against the instrument's song slots.
        """
        effect_id = int(effect_id)
        if effect_id <= 0:
            return
        if (getattr(self, "_fealty", False)
                and effect_id in weapon_skill_effects.AILMENTS):
            self._fealty = False
            self.say("Fealty nullifies the effect.")
            return
        now = time.time()
        is_song = bool(song_base)
        existing = self.effect_state.get(effect_id)
        if existing is not None:
            # A recast refreshes the timer and never lowers a Utsusemi/Blink count.
            existing["until"] = now + float(duration) if duration else 0.0
            existing["power"] = max(int(existing.get("power", 0)), int(power))
            existing["potency"] = max(int(existing.get("potency", 0)), int(potency))
            existing["tick"] = int(tick or existing.get("tick", 0))
            existing["icon"] = effects.icon_for(
                effect_id, int(icon or existing.get("icon", effect_id)),
                int(existing["power"]))
            if is_song:
                # A song's mods belong to the new cast; merging them would keep a
                # previous tier's stat after a weaker song lands.
                existing["mods"] = {int(k): int(v) for k, v in (mods or {}).items()}
                existing["song"] = True
                existing["song_base"] = float(song_base)
                existing["song_name"] = str(song_name)
                existing["song_cast_at"] = float(song_cast_at or now)
                existing["song_effect"] = int(song_effect or existing.get("song_effect", 0))
            elif mods:
                existing.setdefault("mods", {}).update({int(k): int(v) for k, v in mods.items()})
            return
        self.status_effects.append(effect_id)
        self.effect_state[effect_id] = {
            "until": now + float(duration) if duration else 0.0,
            "power": int(power),
            "potency": int(potency),
            "tick": int(tick),
            "icon": effects.icon_for(effect_id, icon, power),
            "mods": {int(k): int(v) for k, v in (mods or {}).items()},
            "next_tick": now + 3.0,
        }
        if is_song:
            self.effect_state[effect_id].update({
                "song": True,
                "song_base": float(song_base),
                "song_name": str(song_name),
                "song_cast_at": float(song_cast_at or now),
                "song_effect": int(song_effect),
            })

    def remove_effect(self, effect_id: int, *, quiet: bool = False) -> bool:
        """Drop one effect; the caller queues 0x037 (and a wear-off line) as needed."""
        effect_id = int(effect_id)
        if effect_id not in self.effect_state:
            return False
        state = self.effect_state.pop(effect_id, None)
        try:
            self.status_effects.remove(effect_id)
        except ValueError:
            pass
        if not quiet and state is not None:
            icon = int(state.get("icon", effect_id))
            self.queue.append(sub(0x029, packets.battle_message(
                int(self.char["char_id"]), int(self.char["char_id"]),
                int(self.char.get("targid", 0x400)), int(self.char.get("targid", 0x400)),
                icon, 0, packets.MESSAGE_STATUS_WEARS_OFF)))
        return True

    def drop_shadow(self) -> int:
        """Consume one Utsusemi shadow and return how many are left."""
        state = self.effect_state.get(effects.COPY_IMAGE)
        if state is None or int(state.get("power", 0)) <= 0:
            return 0
        state["power"] = int(state["power"]) - 1
        remaining = int(state["power"])
        # Move the Copy Image (2)/(3)/(4) icon so the client's badge counts down.
        state["icon"] = effects.copy_image_icon(remaining)
        if remaining <= 0:
            self.remove_effect(effects.COPY_IMAGE, quiet=True)
        return remaining

    def moghouse_city(self) -> int:
        """The city whose Mog House this is (1 San d'Oria .. 4 Jeuno), or 0."""
        return MOGHOUSE_CITY_BY_ZONE.get(int(self.zone), 0)

    def moghouse_model(self) -> int:
        """MyroomMapNumber: the interior the client draws and the exit menu it offers."""
        city = self.moghouse_city()
        if city == 4:
            return 0x0100
        if city and MOGHOUSE_CITY_BY_NATION.get(int(self.char.get("nation", -1))) == city:
            return MOGHOUSE_HOME_MODELS[city]
        return MOGHOUSE_MODELS.get(city, 0x0100)

    def moghouse_door(self, zone: int) -> list:
        """Where to stand after leaving: the outdoor door of that city's Mog House."""
        zone = int(zone)
        for rect, line in self.world.zones.lines.items():
            name = rect.to_bytes(4, "little")
            if int(line[0]) == zone and name[:3] in (b"zmr", b"zms") and name[3] != ord("q"):
                return list(line[1:])
        return list(self.world.zones.position(zone))

    def _set_moghouse(self, inside: bool) -> None:
        self.char["moghouse"] = 1 if inside else 0
        try:
            self.world.service.set_moghouse(self.char["id"], self.char["moghouse"])
        except Exception:
            pass

    def toggle_moghouse(self) -> None:
        if self.char.get("moghouse"):
            self.leave_moghouse(self.zone)
            return
        self._set_moghouse(True)
        # Entering a Mog House rests the character: HP and MP are refilled and every
        # status effect is gone before the client is told to zone.
        self.clear_status_effects()
        self.restore_vitals()
        # interior spawn; login packet flips the client into SAVE_LOGIN_STATE_MYROOM
        self.change_zone(self.zone, [0.0, 0.0, 0.0, 192], logout_state=3)

    def leave_moghouse(self, zone: int | None = None) -> None:
        """Step out, optionally into another area of the city (the exit menu)."""
        if not self.char.get("moghouse"):
            return
        destination = int(self.zone if zone is None else zone)
        self._set_moghouse(False)
        # The door is not a party zone line: the boxes are already outside and do not need
        # a second 0x00B for the room the leader just left.  Handing them one made the
        # clients that missed it go silent and get reaped -- the "one or two lost while
        # zoning" pattern, and now a main-client drop when leaving a Mog House.
        self.change_zone(destination, self.moghouse_door(destination), logout_state=3)

    def mh_out(self, name: str = "") -> None:
        """//mh out [name|all]: step family characters out of their Mog House.

        A headless box cannot pick the Mog House exit menu.  This does what the menu does,
        on the server: clear the inside flag and hand the client a normal 0x00B to the
        door of its own city.  The door is used rather than the leader's position, so it
        works while the leader is still inside and can never put a box into someone
        else's interior.
        """
        family = self.world.service.account_family_ids(
            int(self.char.get("account_id") or 0))
        named = name and name.casefold() not in ("all", "everyone", "team", "subs")
        targets = []
        for session in list(self.world.sessions.values()):
            if int(session.char.get("account_id") or 0) not in family:
                continue
            if not session.char.get("moghouse"):
                continue
            if named and str(session.char.get("name") or "").casefold() != name.casefold():
                continue
            targets.append(session)
        if not targets:
            if named:
                self.say("%s is not in a Mog House." % name)
            else:
                self.say("No one in your family is in a Mog House.")
            return
        for target in targets:
            target.leave_moghouse(int(target.zone))
            if target is not self:
                target.say("You step out of your Mog House.")
        self.say("Stepped %d character%s out of the Mog House." % (
            len(targets), "" if len(targets) == 1 else "s"))

    def moghouse_exit(self, p: bytes) -> None:
        """C2S 0x05E with rect ``zmrq``: a pick from the Mog House exit menu."""
        if not self.char.get("moghouse"):
            log.info("%s ignored a Mog House exit while outside", self.addr)
            return
        mode = int(p[0x17]) if len(p) > 0x17 else 0
        bit = int(p[0x16]) if len(p) > 0x16 else 0
        if mode in (125, 126):  # 2F/1F changes; Fanxi has no second floor
            return
        city = self.moghouse_city()
        if not city and bit in MOGHOUSE_EXITS:
            city = bit
        destination = None
        if city and 1 <= mode <= len(MOGHOUSE_EXITS.get(city, ())):
            destination = MOGHOUSE_EXITS[city][mode - 1]
        if destination is None:
            # Mode 0 is "the area you entered from"; unknown picks (including the
            # unauthored Mog Garden) fall back to the same door.
            destination = self.zone
        log.info("%s Mog House exit bit=%d mode=%d -> %s", self.addr, bit, mode,
                 self.world.zones.name(destination))
        self.leave_moghouse(destination)

    def open_mog_menu(self) -> None:
        """0x02E: the client's own Mog House menu.

        The menu itself (Change Job, Delivery Box, Furnishings, Exit) is drawn by the
        client; the server only raises the flag.  The pick comes back as 0x0100.
        """
        self.queue.append(sub(0x02E, b""))
        log.info("%s moogle menu", self.addr)

    def myroom_job(self, p: bytes) -> None:
        """C2S 0x0100: the Change Job pick from the Moogle menu.

        Byte 4 is the main job, byte 5 the support job; the one that is not being changed
        is sent as 0 (so asking for a support job alone looks like a zero main job).
        """
        if len(p) < 6:
            return
        error = self.job_change_error()
        if error:
            self.say(error)
            return
        self._change_job(int(p[4]), int(p[5]))

    def _job_level(self, job: int) -> int:
        return int((self.char.get("jobs") or {}).get(int(job), (0, 0))[0])

    def in_safe_job_change_zone(self) -> bool:
        """Whether a job change here is a rest that refills HP and MP.

        The Mog House flag is checked as well as the zone so a character standing in
        its interior (which the client draws but the server keeps in the city zone)
        always counts as safe.
        """
        return (bool(int(self.char.get("moghouse") or 0))
                or int(self.zone) in SAFE_JOB_CHANGE_ZONES)

    def in_fight(self) -> bool:
        """True while this character is in combat, not just holding a weapon.

        ``engaged_id`` is the player's own engagement.  A monster can also aggro and
        attack before the player draws, so the zone's living mobs are checked for this
        character as their hate target or claim.
        """
        if self.engaged_id:
            return True
        char_id = int(self.char["char_id"])
        for entity in self.entities:
            if getattr(entity, "kind", "") != "mob" or not getattr(entity, "alive", True):
                continue
            if int(getattr(entity, "engaged_char_id", 0) or 0) == char_id:
                return True
            if int(getattr(entity, "claim_char_id", 0) or 0) == char_id:
                return True
        return False

    def job_change_error(self) -> str | None:
        """Why a job change is refused right now, or None when it is allowed."""
        if self.in_event:
            return "You cannot change jobs during an event."
        if self.in_fight():
            return "You cannot change jobs while in a fight."
        if self.dead_until or int(self.char.get("hp_current", 1)) <= 0:
            # A city refill would otherwise revive the character from the K.O. recovery.
            return "You cannot change jobs while knocked out."
        if int(self.zone) in JOB_CHANGE_BLOCKED_ZONES:
            return "You cannot change jobs in this area."
        return None

    def clear_job_change_effects(self) -> bool:
        """Drop the effects a job change removes, keeping the regional buffs.

        The client's buff bar is the 0x037 slot list, so clearing ``status_effects``
        makes the next status packet write 0xFF into every slot.  A kept effect stays
        in the list, in its relative order, with its timer and power state.
        """
        kept = [int(effect) for effect in self.status_effects
                if int(effect) in JOB_CHANGE_KEPT_EFFECTS]
        kept_state = {effect: self.effect_state[effect] for effect in kept
                      if effect in self.effect_state}
        changed = bool(self.status_effects or self.effect_state
                       or int(self.food.get("item_id") or 0))
        self.status_effects[:] = kept
        self.effect_state.clear()
        self.effect_state.update(kept_state)
        self.food = live_state.empty_food()
        if changed:
            # Do not let the reconnect snapshot hand the old buffs back if the client
            # drops before the next tick writes the new state.
            self.live_state_signature = None
        return changed

    def _change_job(self, main_job: int, sub_job: int, *, auto_equip: bool = True) -> bool:
        """Apply a job change and refresh every packet that depends on it."""
        # The menu and //job both check before calling, and _job_swap checks before it
        # touches a bag; this keeps a direct caller from changing jobs mid-event.
        error = self.job_change_error()
        if error:
            self.say(error)
            return False
        jobs = self.char.get("jobs") or {}
        if not main_job and not sub_job:
            return False
        if main_job:
            level = int(jobs.get(main_job, (0, 0))[0])
            if level <= 0:
                self.say("That job is not available yet.")
                return False
            self.char["main_job"] = main_job
            self.char["main_level"] = level
        if sub_job:
            level = int(jobs.get(sub_job, (0, 0))[0])
            if level <= 0:
                self.say("That support job is not available yet.")
                return False
            self.char["sub_job"] = sub_job
        # A support job never exceeds half the main job's level.
        support = int(self.char.get("sub_job") or 0)
        if support:
            self.char["sub_level"] = min(int(jobs.get(support, (0, 0))[0]),
                                         int(self.char["main_level"]) // 2)
        else:
            self.char["sub_level"] = 0
        try:
            self.world.service.save_job(self.char["id"], int(self.char["main_job"]),
                                        int(self.char["main_level"]), int(self.char["sub_job"]),
                                        int(self.char["sub_level"]))
        except Exception as exc:
            log.warning("%s could not save the job change: %s", self.addr, exc)
        # A new job carries none of the old job's buffs.  The conquest family stays
        # (see JOB_CHANGE_KEPT_EFFECTS); food and every other status effect wear off.
        # TP is earned with the weapon that was out, so it never crosses a job change.
        self.clear_job_change_effects()
        self.char["tp"] = 0
        # Retail clears style lock on a job change and forgets the locked look, and so
        # does the client when it sends 0x053 mode 0; doing it here also covers the
        # server-side //job command.  The models have to go with the flag: leaving them
        # in the character row let a stale keepalive paint the old job's clothing back
        # on (a Dancer wearing the Scholar's outfit).
        was_locked = self.style_locked()
        if was_locked or any(self._style_models().values()):
            self._apply_style(False)
        if was_locked:
            self.queue.append(self.system_message(MSG_STYLE_LOCK_OFF))
        self._unequip_invalid()
        if auto_equip:
            # Dress the new job before the bundle, so the grap list carries the new models.
            self.queue += self.equipment_packets()
        # Job traits change the maxima too (Max HP/MP Boost), and the packets in the
        # bundle report both the sheet maximum and the stored current value.
        self._trait_cache = None
        self.refresh_vitals()
        if self.in_safe_job_change_zone():
            # A city or Mog House is a rest: the bars come back full.  A field, dungeon
            # or instance only gets the recomputed maxima, so the player manages HP/MP.
            self.restore_vitals(refresh=False)
        self.queue += self.job_bundle()
        # The group list carries each member's job pair, and another client redraws a
        # party row only when it sees a fresh one.  A job change therefore has to reach
        # the whole party, not just the character whose job moved (the box leader's
        # window would otherwise keep showing the old job after a remote //job).
        self.world.reload_party(self.world.party_of(int(self.char["char_id"])))
        name = JOB_NAMES.get(int(self.char["main_job"]), "job")
        support_name = JOB_NAMES.get(int(self.char["sub_job"]), "")
        log.info("%s job change -> %s %d / %s %d", self.addr, name,
                 int(self.char["main_level"]), support_name or "none",
                 int(self.char["sub_level"]))
        if support_name:
            self.say("You are now a level %d %s with a level %d %s support job." % (
                int(self.char["main_level"]), name, int(self.char["sub_level"]), support_name))
        else:
            self.say("You are now a level %d %s." % (
                int(self.char["main_level"]), name))
        return True

    def job_command(self, words: list[str]) -> None:
        """//job: change a job pair, here or on another character on the account.

        ``//job <job> [sub]`` changes this character.  ``//job <character> <job> <sub>``
        changes one of the other online characters on this account or on one of its
        sub-accounts -- the box form, so a leader can re-gear a support character
        without typing into its client.  The count of words is the rule: three words
        name the target first, two are the sender.  The target runs the same swap as
        below: everything worn comes off, the old job's slipped gear is stored, the new
        job's slips are emptied into a cleared inventory, and the leftovers go into the
        wardrobes.  Working stock stays visible.  The old locked appearance is cleared
        before the swap and the new outfit is locked afterwards, so a box never keeps
        wearing the previous job's clothing.
        """
        args = list(words[1:])
        target = self
        if len(args) >= 3:
            # Three words is the box form: the character to change, then the job pair.
            target = self._job_target(args[0])
            if target is None:
                return
            args = args[1:]
        if not args:
            self.say("Usage: //job <job> [sub], or //job <character> <job> <sub>.")
            return
        main_job = job_id(args[0])
        if main_job is None:
            hint = ""
            if len(args) == 2 and job_id(args[1]) is not None:
                hint = " To change another character use //job <character> <job> <sub>."
            self.say("Unknown job %r. Try NIN, Ninja or 13.%s" % (args[0], hint))
            return
        sub_job = job_id(args[1]) if len(args) > 1 else 0
        if len(args) > 1 and sub_job is None:
            # An unrecognised support job used to fall through as "no change" and keep
            # the old one, which is not what a typed job pair means.
            self.say("Unknown support job %r. Try NIN, Ninja or 13." % args[1])
            return
        remote = target is not self
        target_name = str(target.char.get("name") or "That character")
        if target._job_level(main_job) <= 0:
            if remote:
                self.say("%s has not unlocked that job." % target_name)
            else:
                self.say("That job is not available yet.")
            return
        if sub_job and target._job_level(sub_job) <= 0:
            if remote:
                self.say("%s has not unlocked that support job." % target_name)
            else:
                self.say("That support job is not available yet.")
            return
        error = target.job_change_error()
        if error:
            # The box form reports the target's state, not the caller's: a leader in
            # town cannot change a sub that is in a Dynamis instance or mid-event.
            self.say(error.replace("You ", "%s " % target_name, 1) if remote else error)
            return
        if remote:
            target.say("%s changes your job to %s." % (
                self.char.get("name") or "Your leader", job_pair_label(main_job, sub_job)))
        changed = target._job_swap(main_job, sub_job)
        if remote and changed:
            self.say("%s is now %s." % (target_name, job_pair_label(
                int(target.char["main_job"]), int(target.char.get("sub_job") or 0))))

    def _job_swap(self, main_job: int, sub_job: int) -> bool:
        """Run the gear-aware job swap on this session; the caller has validated it."""
        # Keep this check before the first bag move: a refused swap must leave the
        # outfit, the storage and the job pair exactly as they were.
        error = self.job_change_error()
        if error:
            self.say(error)
            return False
        previous = int(self.char.get("main_job") or 1)
        previous_label = JOB_ABBREVIATIONS.get(previous, str(previous))
        new_label = JOB_ABBREVIATIONS.get(main_job, str(main_job))

        # The slips and the 9,999 locker are one storage to the player: everything the
        # new job cannot equip goes away (a slip when it has one, the locker when it
        # does not) and everything it can equip comes back into the Mog Wardrobes.
        # The old outfit is loose by now, so it is part of the sweep.
        self._unequip_all("job change to %s" % new_label)
        organized = {
            "stored": [], "pulled": [], "relocated": [],
            "stored_total": 0, "pulled_total": 0, "remaining": 0,
            "stored_slip": 0, "stored_locker": 0, "pulled_slip": 0,
            "pulled_locker": 0, "locker_full": 0, "equipped": 0,
            "free": 0, "locker_count": 0, "locker_capacity": 0,
        }
        organized_ok = True
        try:
            organized = self.world.service.organize_job_storage(
                int(self.char["id"]), main_job)
        except Exception as exc:
            organized_ok = False
            log.warning("%s could not organize the storage for %s: %s",
                        self.addr, new_label, exc)
            self.say("Could not organize the storage: %s" % exc)
        self._queue_storage_moves(organized)

        if not self._change_job(main_job, sub_job, auto_equip=False):
            return False

        # Wear what was just pulled.  The organizer already put the job's loose gear
        # into the wardrobes, so auto-equip sees all of it.
        self.equipped.clear()
        self.equip_initial(bags=AUTO_EQUIP_BAGS)
        self.queue += self.equipment_packets()
        self.refresh_vitals()
        if self.in_safe_job_change_zone():
            # Refill against the new outfit's maxima, not the ones the job bundle saw
            # before auto-equip.  In a field the current HP/MP stay where they were.
            self.restore_vitals(refresh=False)
        if organized_ok:
            self._report_organize(organized, main_job)
        # The unequip/auto-equip pair changed the stat sheet, so send the final
        # appearance and stats once even when nothing was originally worn.
        self.note_equipment_change()
        self.flush_equipment()
        # The old job's locked look was cleared before the swap.  Lock the outfit the
        # swap just dressed: the character keeps the new job's appearance through later
        # gear changes, and the models persisted here are the new ones.  Then repaint
        # the clients that draw this character -- an observer only re-reads another
        # player's models when it spawns the entity, so without the respawn a box
        # leader's window keeps drawing the previous job's clothing.
        self._apply_style(True, self._current_models())
        self.queue += self.style_packets()
        self.queue.append(self.system_message(MSG_STYLE_LOCK_ON))
        self.world.refresh_player_appearance(self)
        log.info("%s //job %s -> %s: stored %d, pulled %d, tidied %d",
                 self.addr, previous_label, new_label,
                 organized["stored_total"], organized["pulled_total"],
                 len(organized["relocated"]))
        return True

    def _job_target(self, query: str) -> "ZoneSession | None":
        """The online family session named by ``//job <character> <job> <sub>``.

        Only the sender's own account family is reachable: the main account plus its
        sub-accounts, which is the same multibox group ``//warp all`` and ``//invite
        subs`` use.  A parked (``//sleep``) box is refused rather than changed behind a
        client that is not reading its packet queue; wake it first.
        """
        name = str(query or "").strip().strip('"').strip("'")
        if not name:
            self.say("Which character? Use //job <character> <job> <sub>.")
            return None
        target = self.world.session_by_name(name)
        if target is None:
            # ``session_by_name`` skips a box that is mid-zone-change; say that rather
            # than claiming a character the player can see is offline.
            for session in self.world.sessions.values():
                if str(session.char.get("name") or "").casefold() != name.casefold():
                    continue
                if getattr(session, "zoning", False) and getattr(session, "logged_in", False):
                    self.say("%s is still zoning; try again in a moment." % (
                        session.char.get("name") or name))
                    return None
            self.say("No online character called %s. //job <job> [sub] changes your own job; "
                     "//job <character> <job> <sub> changes a box." % name)
            return None
        family = self.world.service.account_family_ids(
            int(self.char.get("account_id") or 0))
        if int(target.char.get("account_id") or 0) not in family:
            self.say("%s is not on your account or a sub-account." % (
                target.char.get("name") or name))
            return None
        if getattr(target, "sleeping", False):
            self.say("%s is asleep; //wake it first." % (target.char.get("name") or name))
            return None
        return target

    def job_bundle(self) -> list[Msg]:
        """Every packet the client re-reads after the job (or support job) changes."""
        return [self.grap_list(), self.job_info(), self.char_status(), self.char_stats(),
                self.char_feats(), self.char_abilities(), self.char_commands(),
                self.char_skills(), self.abil_recast(),
                self.job_points(), self.job_points_detail(), self.merits(),
                self.monstrosity(), *self.merit_list(),
                sub(0x0AA, self.spell_bits()), self.char_sync(), self.party_member(),
                self.char_update()]

    def open_door(self, entity) -> None:
        """Play the client's door-open animation; no zoning, no event."""
        if not entity.alive:
            return
        entity.animation = 8  # open_door
        self.queue.append(sub(0x00E, packets.entity_update(entity, mask=0x07)))
        # A door can start a client-side event/cutscene that waits for the server.
        # Cancel any such event and release the standard controls.
        self.queue.append(sub(0x052, struct.pack("<I", 2)))
        self.queue.append(sub(0x052, bytes(4)))
        self.door_entity = entity
        self.door_close_at = time.time() + 7.0

    def talk_to_door(self, entity) -> None:
        """The player targeted a door: normal doors open, moving structures stay put."""
        if str(getattr(entity, "door_kind", "") or "") == "drawbridge":
            if int(getattr(entity, "animation", 0)) == 9:
                self.say("The drawbridge is up. Wait for it to lower.")
            else:
                self.say("The drawbridge is down and cannot be raised by hand.")
            return
        self.open_door(entity)

    def open_nearby_doors(self) -> None:
        """Open the nearest door automatically, when the player asked for that mode.

        Retail leaves doors shut until the player targets them, so the mode is opt-in
        (``//doors auto on``) and only applies in city and outdoor zones.  Moving
        structures such as Port Bastok's drawbridge are never opened this way; their own
        arrival event drives them.
        """
        if not self.auto_open_doors or not self.world.zones.allows_auto_doors(self.zone):
            self.opened_doors.clear()
            return
        nearest = None
        best = 5.0
        for entity in self.entities:
            if entity.kind != "npc" or int(getattr(entity, "size", 0)) != 2:
                continue
            if not int(getattr(entity, "door_id", 0) or 0):
                continue
            if str(getattr(entity, "door_kind", "") or ""):
                continue
            distance = entity.distance_to(*self.pos[:3])
            if distance <= best:
                best = distance
                nearest = entity
        if nearest is None:
            self.opened_doors.clear()
            return
        targid = int(nearest.targid)
        if targid in self.opened_doors:
            return
        self.opened_doors.add(targid)
        self.open_door(nearest)

    def cancel_event(self, event_id: int = 0) -> None:
        """0x052 mode 2; the client expects the event id in the upper bits."""
        mode = 2 | ((int(event_id) & 0xFFFF) << 8)
        self.queue.append(sub(0x052, struct.pack("<I", mode)))

    def scan_events(self, entity, start: int, end: int, params=None) -> None:
        """Send a range of event ids one by one to find which ones this client knows."""
        self.event_scan_entity = entity
        self.event_scan_params = list(params or [0] * 8)
        self.scan_current = 0
        self.scan_deadline = 0.0
        self.scan_acks: list[int] = []
        self.event_scan = list(range(int(start), int(end) + 1))
        self.event_scan_at = 0.0

    def start_event(self, entity, event_id: int, params, mode: int = 8,
                    text_table: int | None = None) -> None:
        """Open one of the client's built-in event menus (0x034 EVENTNUM)."""
        log.info("%s start event %d params %s", self.addr, event_id, list(params))
        self.in_event = True
        self.event_started_at = time.time()
        self.event_ack = False
        self.event_guard_id = event_id
        table = text_table
        if table is None and os.environ.get("FANXI_EVENT_TEXT"):
            table = int(os.environ["FANXI_EVENT_TEXT"], 0)
        self.queue.append(sub(0x034, packets.event_num(entity, self.zone, event_id, params,
                                                       mode=mode, text_table=table)))

    def talk_message(self, entity, text_id: int, params=()) -> None:
        """Show one of the client's own zone text strings (0x02A TALKNUMWORK)."""
        self.queue.append(sub(0x02A, packets.talk_num_work(entity, text_id, params)))

    def event_end(self, p: bytes) -> None:
        """C2S 0x05B: an option was picked (Mode 1) or the event finished (Mode 0)."""
        if len(p) < 20:
            return
        _unique, endpara, _act, mode, _zone, event_id = struct.unpack_from("<IIHHHH", p, 4)
        option = int(endpara) & 0xFFFFFFFF
        log.info("%s event %d mode=%d option=%#x", self.addr, event_id, mode, option)
        self.event_ack = True
        self.current_event_id = int(event_id)
        if getattr(self, "sweep_started", False):
            log.info("%s SWEEP ACK event %d mode=%d option=%#x", self.addr, event_id, mode, option)
        if int(event_id) == getattr(self, "scan_current", 0):
            self.scan_acks.append(int(event_id))
            log.info("%s SCAN HIT %d mode=%d option=%#x", self.addr, event_id, mode, option)
        if mode == 1:
            # Still inside the menu: answer with the parameters the menu expects.
            if event_id == 1500:  # Hunt Registry pages
                menu = (self.world.service.hunt_menu(self.zone, option)
                        or self.world.service.hunt_menu(self.zone, option & 0xFF))
                self.queue.append(sub(0x05C, packets.pending_num(
                    [0, 1 if menu is not None else 0, menu or 0])))
            else:
                self.queue.append(sub(0x05C, packets.pending_num([0, 0, 0])))
            self.queue.append(sub(0x052, struct.pack("<I", 1)))
            return
        self.in_event = False
        choice = option & 0xFF
        index = (option >> 16) & 0xFF
        if 8700 <= event_id <= 8710:
            if choice == 1:  # set the home point at the current spot
                x, y, z, rot = self.pos
                self.world.service.set_home(self.char["id"], self.zone, x, y, z, rot)
                self.char.update({"home_zone": int(self.zone), "home_x": float(x),
                                  "home_y": float(y), "home_z": float(z),
                                  "home_rot": int(rot) & 0xFF})
                self.say("Your home point has been set here.")
            elif choice == 2:  # teleport to the chosen home point
                point = self.world.service.home_point(index)
                if point is not None:
                    self.say("Warping to %s." % self.world.zones.name(int(point["zone"])))
                    self.queue.append(sub(0x052, struct.pack("<I", 1)))
                    self.change_zone(int(point["zone"]),
                                     [float(point["x"]), float(point["y"]),
                                      float(point["z"]), int(point["rot"])])
                    return
            elif choice == 3:
                # Same-zone hop: the client positions itself; nothing to send.
                pass
        elif event_id == 8500 and choice == 1:  # Survival Guide teleport
            guide = self.world.service.survival_guide(index)
            if guide is not None:
                self.say("The survival guide sends you to %s." %
                         self.world.zones.name(int(guide["zone"])))
                self.queue.append(sub(0x052, struct.pack("<I", 1)))
                self.change_zone(int(guide["zone"]),
                                 [float(guide["x"]), float(guide["y"]),
                                  float(guide["z"]), int(guide["rot"])])
                return
        self.queue.append(sub(0x052, struct.pack("<I", 1)))

    def action(self, p: bytes) -> None:
        if len(p) < 12:
            return
        _unique, act_index, action_id = struct.unpack_from("<IHH", p, 4)
        log.info("%s action id=%#x target=%#x unique=%#x", self.addr, action_id,
                 act_index, _unique)
        target = self.world.entity_by_targid(self.zone, int(act_index))
        if target is None:
            target = next((e for e in self.entities if e.id == int(_unique)), None)
        if action_id == 0x14:  # SendResRdy: the client is ready for nearby entities
            self.sync_entities()
        elif action_id == packets.ACTION_MOUNT:
            # The client's Mount menu and its own /mount <name>: ActionBuf[0] is the id it
            # picked.  0 is the personal chocobo (and a valid call), so an out-of-range id
            # is the only thing that is refused.
            if len(p) < 16:
                return
            mount_id = int(struct.unpack_from("<I", p, 12)[0])
            if mounts.by_id(mount_id) is None:
                self.say("That mount is not available.")
                return
            self.set_mount(mount_id)
        elif action_id == packets.ACTION_DISMOUNT:
            self.dismount()
        elif action_id == packets.ACTION_TALK:
            if target is None and self.char.get("moghouse"):
                # The Mog House's "Back to Town" door is drawn by the client from the zone
                # file, not sent as an entity, so its talk arrives with an unknown target.
                self.toggle_moghouse()
                return
            if target is not None and target.kind == "trust":
                if int(getattr(target, "owner_char_id", 0)) != int(self.char["char_id"]):
                    self.say("That alter ego belongs to someone else.")
                    return
                self.say("%s leaves your party." % target.name)
                self.world.despawn_trust(target)
                self.queue.append(sub(0x052, bytes(4)))
                return
            if target is not None and target.kind == "npc":
                if target.distance_to(*self.pos[:3]) > 6.0:
                    self.say("You are too far away.")
                    return
                if int(getattr(target, "size", 0)) == 2:
                    self.talk_to_door(target)
                    return
                from . import content
                content.npc_talk(self, target)
                # An event (menu) owns the client's input until it finishes; sending the
                # standard-control release here would cancel the menu we just opened.
                if not self.in_event:
                    self.queue.append(sub(0x052, bytes(4)))
            elif target is not None and target.kind == "mob":
                self.say("%s has no time for conversation." % target.name)
            else:
                self.say("There is nothing to talk to there.")
        elif action_id == packets.ACTION_ATTACK:
            if target is not None and target.kind == "mob" and target.alive:
                # Retail draws on any target the client can target: the character draws
                # and walks in.  There is no distance gate here -- the leash that ends the
                # fight lives in the swing path (ENGAGE_RANGE).  Engaging is not enmity
                # either: the mob does not fight back until the first hit lands, so the
                # monster's own target is set by the swing and not here.
                # The client also re-sends /attack when it picks the target back up after
                # its own range disengage; that is the same engagement, not a new one, so
                # it must not repeat the chat line or delay the next swing.
                same_target = self.engaged_id == int(target.id)
                self.engaged_id = int(target.id)
                self.engaged_targid = int(target.targid)
                if not same_target:
                    # A new engagement owns one range-drop packet of the client's own.
                    self.client_range_drop = True
                    self.next_attack_at = time.time() + ENGAGE_DELAY
                # 0x058 assist: UniqueNo, AssistNo, ActIndex.  LandSandBoat sends this as
                # the engage acknowledgement, and it is what the client uses to show this
                # player's engaged target.
                self.queue.append(sub(0x058, struct.pack(
                    "<IIHH", int(self.char["char_id"]), int(target.id),
                    int(self.char.get("targid", 0x400)), 0)))
                # 0x00D byte 0x1B is the entity's animation state, and 1 is the attack
                # stance.  Without it the client never draws the weapon, so the 0x028
                # swings that follow play no swing animation.  A General-only update
                # changes the animation without re-spawning the entity.
                self.queue.append(self.char_update(packets.SEND_HP))
                if not same_target:
                    self.say("You engage %s." % target.name)
            else:
                self.say("You cannot attack that.")
        elif action_id == packets.ACTION_CAST_MAGIC:
            self.cast_magic(p, int(act_index))
        elif action_id == packets.ACTION_WEAPONSKILL:
            self.weaponskill(p, int(act_index))
        elif action_id == packets.ACTION_JOBABILITY:
            self.job_ability(p, int(act_index))
        elif action_id == packets.ACTION_ATTACK_OFF:
            self.attack_off()
        elif action_id == packets.ACTION_SHOOT:
            if target is not None and target.kind == "mob" and target.alive:
                self._ranged_shot(target)
            else:
                self.say("You cannot shoot that.")
        elif action_id == packets.ACTION_CHANGE_TARGET:
            self.target_targid = int(act_index)

    def _steal(self, entity) -> None:
        """Thief Steal: take one weighted item from the monster's steal table."""
        template_id = int(getattr(entity, "template_id", 0) or 0)
        rows = self.world.service.monster_steal_items(template_id) if template_id else []
        if not rows or self.world.rng.random() >= 0.75:
            self.say("You fail to steal anything.")
            return
        weights = [max(1, int(row.get("weight") or 1)) for row in rows]
        picked = self.world.rng.choices(rows, weights=weights, k=1)[0]
        item_id = int(picked["item_id"])
        try:
            self.world.service.add_item(int(self.char["id"]), item_id, 1)
        except Exception as exc:
            self.say("You could not steal the item: %s" % exc)
            return
        self.refresh_inventory()
        item = self.world.service.item(item_id)
        self.say("You steal %s." % (item["name"] if item else "an item"))

    def _ranged_shot(self, entity, *, bonus: int = 0) -> int:
        """One ranged attack using the equipped ranged weapon and ammo.

        The server has kept melee and ranged separate until now; this is the shared path
        used by /ra and Bounty Shot.  It uses the same hit/damage engine as melee with the
        ranged weapon's skill and damage, the ammo's damage and the ranged mods.
        """
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s equipped weapons unavailable: %s", self.addr, exc)
            weapons = {}
        ranged = weapons.get(stats.SLOT_RANGED) or {}
        ammo = weapons.get(stats.SLOT_AMMO) or {}
        if not int(ranged.get("item_id") or 0) or not int(ammo.get("item_id") or 0):
            self.say("You have no ranged weapon and ammunition equipped.")
            return 0
        sheet = self.stat_sheet()
        attacker = sheet.ranged_fighter
        if attacker is None:
            self.say("You have no usable ranged weapon and ammunition equipped.")
            return 0
        target = self.world.debuffed_monster(entity)
        hit = combat.melee(attacker, target, zone=int(self.zone),
                           rng=self.world.rng, ranged=True)
        damage = combat.cap_damage(max(0, int(hit.damage) + int(bonus)))
        if hit.missed or damage <= 0:
            self.queue.append(sub(0x028, packets.battle_action(
                int(self.char["char_id"]), int(entity.id), 0, kind=0,
                message=packets.MESSAGE_ATTACK_MISSES,
                category=packets.ACTION_CATEGORY_BASIC_ATTACK)))
            return 0
        self.world.add_damage_hate(entity, int(self.char["char_id"]), damage, time.time())
        entity.hp = max(0, int(entity.hp) - damage)
        self.world._queue_mob_hp(entity)
        self.world.wake_mob(entity)
        self.queue.append(sub(0x028, packets.battle_action(
            int(self.char["char_id"]), int(entity.id), damage, kind=2,
            message=packets.MESSAGE_DAMAGE, category=packets.ACTION_CATEGORY_BASIC_ATTACK)))
        if int(entity.hp) <= 0:
            self.world.kill_mob(self, entity, time.time())
        return damage

    def attack_off(self) -> None:
        """C2S 0x01A action 0x04: /attack off, or the client's own range drop.

        Retail ends the engagement on the first /attack off, at any distance: it is the
        player's command, and nothing re-draws the weapon behind it.  The one exception is
        the packet the client emits by itself when its first swing of a new engagement
        finds the target outside its own four-yalm reach -- that is the client dropping
        its swing, not the player giving up, so a single one per engagement is absorbed
        (the stance is re-asserted instead).  The allowance is cleared on that absorb and
        on every disengage, so a second press always breaks the engagement.
        """
        if not self.engaged_id:
            return
        target = self.engaged_target()
        gap = (target.distance_to(*self.pos[:3])
               if target is not None and target.alive else None)
        if self.client_range_drop and gap is not None and gap > MELEE_RANGE:
            self.client_range_drop = False
            self.next_attack_at = time.time() + 0.5
            self.assert_stance()
            return
        self.disengage()

    # --- /check and the inspect menu ----------------------------------------------------------
    def inspect(self, p: bytes) -> None:
        """C2S 0x00DD: /check, /checkname and /checkparam.

        The client names the entity (server id and target index) and the Kind of
        inspection.  Kind 0 is /check: a monster is answered by its own check line, a
        player by the examine notice.  Kinds 1 and 2 belong to the client's Monstrosity
        and /checkparam windows; Fanxi has neither, so they are only logged.
        """
        if len(p) < 13:
            return
        unique, act_index, kind = struct.unpack_from("<IIB", p, 4)
        targid = int(act_index) & 0xFFF
        target = self.world.entity_by_targid(self.zone, targid)
        if target is None:
            target = next((entity for entity in self.entities
                           if int(getattr(entity, "id", 0)) == int(unique)), None)
        log.info("%s inspect kind=%d target=%#x (%s)", self.addr, int(kind), targid,
                 getattr(target, "name", None) or "unknown")
        if int(kind) != 0:
            return
        if target is not None and target.kind == "mob":
            # The targid can have been reused after a respawn; do not answer with a
            # different monster's level when the client's own id no longer matches.
            if int(unique) not in (0, int(target.id)):
                return
            self.check_mob(target)
            return
        other = self.world.session_by_char(int(unique)) if int(unique) else None
        if other is not None and int(other.zone) != int(self.zone):
            other = None
        if other is None:
            other = self.player_by_targid(targid)
        if other is not None:
            self.examine_player(other)
            return
        if target is not None and target.kind in ("trust", "pet"):
            self.say("You examine %s." % target.name)
        # An NPC has nothing to check in retail; stay silent, as the client's menu does.

    def player_by_targid(self, targid: int):
        """The live session another client knows as ``targid`` in this zone.

        The local client always calls itself 0x400, so its own index resolves to this
        session before the world table is consulted.
        """
        wanted = int(targid)
        if wanted == int(self.char.get("targid", TARGID) or TARGID):
            return self
        for session in list(self.world.sessions.values()):
            if (session is self or not session.logged_in or session.zoning
                    or getattr(session, "sleeping", False) or getattr(session, "gone", False)
                    or int(session.zone) != int(self.zone)):
                continue
            if int(getattr(session, "targid", 0) or 0) == wanted:
                return session
        return None

    def check_mob(self, entity) -> None:
        """Answer /check on a monster with the client's own check line (0x029).

        The client renders the text; the packet carries the monster's level in Data and
        the difficulty in Data2 as ``64 + the client's enum``.  Messages 170..178 add
        the Defense/Evasion sentence, so this is the answer LandSandBoat sends.
        """
        level = int(entity.level)
        player_level = int(self.char.get("main_level", 1) or 1)
        player = self.stat_sheet()
        monster = self.world.debuffed_monster(entity)
        result = check.difficulty(player_level, level)
        message = check.message_id(int(player.attack), int(player.accuracy),
                                   int(monster.defense), int(monster.evasion))
        cid = int(self.char["char_id"])
        targid = int(self.char.get("targid", 0) or TARGID)
        self.queue.append(sub(0x029, packets.battle_message(
            cid, int(entity.id), targid, int(entity.targid), level,
            int(check.CHECK_DATA_BASE) + int(result), message)))
        log.info("%s checks %s (Lv.%d): %s, message %d", self.addr, entity.name, level,
                 check.DIFFICULTY_NAMES[result], message)

    def examine_player(self, other) -> None:
        """Answer /check on a player with the examine notice.

        Retail opens the equipment window from the 0x0C9/0x0CA family, which Fanxi does
        not send yet.  The checked player still gets retail's "<name> examines you."
        line, and the checker gets a chat line instead of no feedback at all.
        """
        if other is self:
            self.say("You examine yourself.")
            return
        # The checked player's client knows the checker by the targid the server
        # assigned in this zone (0x400 is only ever "self" inside the checker's own
        # client), so send that one rather than the local-player index.
        other.queue.append(sub(0x009, packets.system_message(
            MSG_EXAMINE, unique_no=int(self.char["char_id"]),
            act_index=int(self.targid or TARGID), attr=0x10,
            name=str(self.char.get("name", "")))))
        log.info("%s examines %s", self.addr, other.char.get("name", "?"))
        self.say("You examine %s." % other.char.get("name", "?"))

    def item_use(self, p: bytes) -> None:
        """C2S 0x037: use a medicine or a food item.

        The client does not send the item id.  It sends the container and the slot the
        player clicked -- ``PropertyItemIndex`` at 0x0E and ``Category`` at 0x10 -- and
        the four bytes at 0x08 are ``ItemNum``, which the client always zeroes.  Reading
        an item id from there returned 0 for every request, so food was silently ignored.
        Dawn Mulsum is a pet medicine: it restores 25-50% of the pet's maximum HP and
        does not touch GEO Luopans.  The server has no pet HP model yet, so without a
        ``pet_hp_max`` on the character it reports that there is no pet to heal; the
        item is still consumed and refilled from the locker.

        Food applies its ``food_effects`` row to the session.  The mods are merged by
        ``combat_mods()``, so the stat sheet, magic damage, healing and every spell
        modifier read the same values, and the Food icon carries the timer.  The item
        finish action carries the eat/drink animation, which is what makes the character
        move while the effect lands.
        """
        # 20-byte packet: UniqueNo(4) ItemNum(4) ActIndex(2) PropertyItemIndex(1)
        # padding(1) Category(4), after the 4-byte sub-message header.
        if len(p) < 0x14:
            return
        slot = int(p[0x0E])
        container = struct.unpack_from("<I", p, 0x10)[0]
        if container > 0xFF:
            return
        if container == CONTAINER_RECYCLE:
            self.say("Take that item out of the Recycle Bin before using it.")
            return
        stock = None
        try:
            stock = self.world.service.inventory_slot(
                int(self.char["id"]), container, slot)
        except Exception as exc:
            log.warning("%s item lookup failed: %s", self.addr, exc)
        if stock is None:
            self.say("You do not have that item.")
            return
        item_id = int(stock["item_id"])
        spec = self.dispense_items.get(item_id)
        if spec is not None:
            self.dispense_item(container, slot, stock, spec)
            return
        food = None
        try:
            food = self.world.service.food_effect(item_id)
        except Exception as exc:
            log.warning("%s food lookup failed: %s", self.addr, exc)
        if item_id != 5411 and food is None:
            return
        consumed = self.world.service.consume_inventory_slot(
            int(self.char["id"]), container, slot)
        if consumed is None:
            self.say("You do not have that item.")
            return
        quantity = int(consumed["quantity"])
        me = int(self.char["char_id"])
        # 0x028 ItemFinish: the result's sub_kind is the animation id, so this is what
        # plays the eating motion.  The chat line comes from apply_food()/the pet branch.
        animation = int(food.get("animation") or 0) if food is not None else 34
        if animation:
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, 0, animation=animation, message=0, kind=1,
                category=packets.ACTION_CATEGORY_ITEM_FINISH,
                action_id=item_id, info=0)))
        self.queue.append(sub(0x020, packets.item_attr(
            item_id if quantity else 0, quantity, container, slot)))
        # The slot update redraws one bag, but the all-bag sync is what marks every
        # container ready after a move; item use sends the same follow-up so a consumed
        # stack in a wardrobe cannot stay drawn.
        self.queue.append(self.container_sync())

        if food is not None:
            self.apply_food(item_id, food)
        else:
            pet_max = int(self.char.get("pet_hp_max", 0) or 0)
            pet_hp = int(self.char.get("pet_hp", 0) or 0)
            pet_type = str(self.char.get("pet_type") or "").casefold()
            if pet_type in ("luopan", "geo_luopan", "geoluopan"):
                self.say("The Dawn Mulsum has no effect on the Luopan.")
            elif pet_max <= 0:
                self.say("You do not have a pet to heal.")
            else:
                amount = dawn_mulsum_amount(pet_max)
                healed = min(pet_max, pet_hp + amount)
                self.char["pet_hp"] = healed
                self.say("The Dawn Mulsum restores %d HP to your pet." % (healed - pet_hp))

        try:
            self._queue_storage_returns(
                self.world.service.refill_working_stock(int(self.char["id"])))
        except Exception as exc:
            log.warning("%s item refill failed: %s", self.addr, exc)

    def dispense_item(self, container: int, slot: int, stock: dict,
                      spec: dict) -> None:
        """Use one RMEA dispense pouch: grant its ammo and start the reuse timer.

        The pouch is equipment, not a consumable, so it stays in the bag.  Its
        24-byte timer block lives on that exact char_inventory row; when the hour is up
        a fresh 0x020 reports the charge ready again.
        """
        char_id = int(self.char["id"])
        item_id = int(stock["item_id"])
        ammo_id = int(spec["ammo_id"])
        quantity = max(1, int(spec["quantity"]))
        max_charges = max(1, int(spec["max_charges"]))
        reuse = max(0, int(spec["reuse_delay"]))
        use_delay = max(0, int(spec["use_delay"]))
        now = time.time()
        extra = bytes(stock.get("extra") or b"")
        timer = item_usable.read_timer(extra)
        charges = max_charges if timer is None else max(0, min(max_charges, timer[0]))
        item = self.world.service.item(item_id) or {}
        name = str(item.get("name") or "pouch")

        remaining = item_usable.cooldown_remaining(
            extra, now=now, reuse_delay=reuse, vana_epoch=VANA_EPOCH)
        if charges <= 0:
            self.say("The %s is empty." % name)
            self.queue.append(self.item_packet(stock, container, slot))
            return
        if remaining > 0:
            self.say("You must wait longer to use that item.")
            self.queue.append(self.item_packet(stock, container, slot))
            return

        try:
            self.world.service.add_item(char_id, ammo_id, quantity)
        except ApiError as exc:
            if exc.code == "inventory_full":
                self.say("Your inventory is full.")
            else:
                self.say(exc.message)
            return
        except Exception as exc:
            log.warning("%s dispense %d failed: %s", self.addr, item_id, exc)
            self.say("That item cannot be used right now.")
            return

        new_extra = item_usable.record_use(
            extra, now=now, max_charges=max_charges, vana_epoch=VANA_EPOCH)
        if not self.world.service.set_item_extra(char_id, container, slot, new_extra):
            log.warning("%s dispense timer not saved for %d:%d", self.addr, container, slot)
        stock = {**stock, "extra": new_extra}
        me = int(self.char["char_id"])
        self.queue.append(sub(0x028, packets.battle_action(
            me, me, 0, animation=int(spec.get("animation") or 0), message=0, kind=1,
            category=packets.ACTION_CATEGORY_ITEM_FINISH,
            action_id=item_id, info=0)))
        # The pouch's charge/cooldown block, then every inventory row of the ammo so an
        # existing stack and a newly created one both redraw.
        self.queue.append(self.item_packet(stock, container, slot))
        for row in self.world.service.inventory(char_id):
            if int(row["container"]) == 0 and int(row["item_id"]) == ammo_id:
                self.queue.append(self.item_packet(row))
        self.queue.append(self.container_sync())
        ammo = self.world.service.item(ammo_id) or {}
        ammo_name = str(ammo.get("name") or "items")
        if quantity != 1 and not ammo_name.endswith("s"):
            ammo_name += "s"
        self.say("You dispense %d %s." % (quantity, ammo_name))

    def apply_food(self, item_id: int, food: dict) -> None:
        """Put one food's modifiers on the session and start its timer."""
        item = self.world.service.item(item_id) or {}
        name = str(item.get("name") or "food")
        duration = max(1, int(food.get("duration") or 0))
        self.food = {
            "item_id": int(item_id),
            "name": name,
            "until": time.time() + duration,
            "mods": dict(food.get("mods") or {}),
        }
        self.add_effect(effects.FOOD, duration=duration)
        self.refresh_vitals()
        self.queue += [self.char_status(), self.char_stats(), self.party_member()]
        self.say("You eat the %s." % name)

    def active_trusts(self) -> list:
        """The alter egos this player still has in the zone, in call order."""
        return [entity for entity in getattr(self, "trust_entities", [])
                if getattr(entity, "alive", False) and int(entity.zone) == int(self.zone)]

    def cast_trust(self, spell: dict, trust: dict, now: float) -> None:
        """Start a Trust spell: no MP, no target, and the alter ego appears when it lands.

        Retail treats Trust magic as its own cast group: the client sends the same
        C2S 0x01A action 0x03 as any spell, but the server spends no MP and spawns an
        NPC instead of resolving an effect.
        """
        if self.zoning or getattr(self, "gone", False) or self.dead_until > now:
            return
        if self.char.get("moghouse"):
            self.say("You cannot call an alter ego here.")
            return
        name = str(trust["name"])
        active = self.active_trusts()
        if any(int(getattr(entity, "trust_spell", 0)) == int(trust["spell_id"])
               for entity in active):
            self.say("%s is already called." % name)
            self.assert_stance()
            return
        if len(active) >= TRUST_MAX:
            self.say("You cannot call another alter ego right now.")
            self.assert_stance()
            return
        fast_cast = int(self.stat_sheet().fighter.mods.get(mod.FASTCAST, 0))
        if int(spell.get("skill") or 0) == 39:  # Ninjutsu
            fast_cast += int(self.combat_mods().get(mod.NINJUTSU_FASTCAST, 0))
        finish = now + combat.cast_time(int(spell["cast_time"]), fast_cast) / 1000.0
        self.casting = {
            "spell": spell, "target": 0, "finish": finish,
            "amount": 0, "healing": False, "self": True, "effect": None,
            "effect_duration": 0.0, "effect_potency": 0,
            "skill": int(spell["skill"]), "resist": 1.0, "trust": trust,
        }
        self.stop_resting()
        self.queue += [self.char_stats(), self.char_status()]
        actor = int(self.char["char_id"])
        # Retail's Magic Start carries the spell's own animation and the client's
        # "starts casting" message.  A zero animation made every cast start with the
        # client's default (Cure's) pose and the correct animation only at the finish.
        self.queue.append(sub(0x028, packets.battle_action(
            actor, actor, int(spell["id"]),
            animation=spell_animation(spell),
            message=packets.MESSAGE_MAGIC_STARTS_CASTING, kind=0,
            category=packets.ACTION_CATEGORY_MAGIC_START,
            action_id=packets.MAGIC_CAST_TRUST, info=0)))

    def finish_trust_cast(self, trust: dict) -> None:
        """Land a Trust spell: play the finish action and put the alter ego in the zone."""
        if self.zoning or getattr(self, "gone", False) or self.dead_until > time.time():
            return
        me = int(self.char["char_id"])
        spell = self.world.service.spell(int(trust["spell_id"])) or {}
        active = self.active_trusts()
        if (len(active) >= TRUST_MAX
                or any(int(getattr(entity, "trust_spell", 0)) == int(trust["spell_id"])
                       for entity in active)):
            self.say("You cannot call another alter ego right now.")
            self.assert_stance()
            return
        # The reference spawns the alter ego from the spell's onCastFinished hook and
        # pushes the finish action afterwards, so the client gets the 0x00E before the
        # action that ends the cast bar.
        self.world.spawn_trust(self, trust)
        self.queue.append(sub(0x028, packets.battle_action(
            me, me, 0, animation=spell_animation(spell) if spell else 0, message=0,
            kind=0, category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell.get("id") or trust["spell_id"]))))
        if self.engaged_id and not self.zoning:
            self.assert_stance()

    def _spell_allowed(self, entries) -> bool:
        """Whether the main or sub job has the level a spell's row asks for."""
        if not entries:
            return True
        main_job = int(self.char.get("main_job") or 0)
        main_level = int(self.char.get("main_level") or 0)
        sub_job = int(self.char.get("sub_job") or 0)
        sub_level = int(self.char.get("sub_level") or 0)
        for job, level in entries:
            if int(job) == main_job and main_level >= int(level):
                return True
            if sub_job and int(job) == sub_job and sub_level >= int(level):
                return True
        return False

    @staticmethod
    def _spell_name_key(name: str) -> str:
        return "".join(str(name or "").split()).casefold()

    def job_point_spell_ids(self) -> tuple[frozenset[int], frozenset[int]]:
        """(every job-point gift spell, the ones this character's main job grants).

        Job-point spells are not level rows: LandSandBoat adds them to the character's
        spell list from the gift table.  Fanxi has one spell bitmap rather than a
        per-character list, so a gift spell is allowed to the granting main job at level
        99 and refused to everyone else (a support job never receives a gift).  The
        result is cached per job pair; a job change invalidates it by key.
        """
        main_job = int(self.char.get("main_job") or 0)
        main_level = int(self.char.get("main_level") or 0)
        key = (main_job, main_level)
        cached = self._jp_spell_cache
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]
        try:
            by_name = self.world.service.spell_ids_by_name()
        except Exception as exc:
            log.warning("%s spell-name index unavailable: %s", self.addr, exc)
            by_name = {}
        every: set[int] = set()
        for name in job_points.all_spell_grants():
            every.update(by_name.get(name, ()))
        mine: set[int] = set()
        if main_job > 0 and main_level >= 99:
            for name in job_points.spell_grants(main_job):
                mine.update(by_name.get(self._spell_name_key(name), ()))
        self._jp_spell_cache = (key, frozenset(every), frozenset(mine))
        return self._jp_spell_cache[1], self._jp_spell_cache[2]

    def can_cast_spell(self, spell_id: int) -> bool:
        """Retail gates spells by job and level; a spell with no row is not gated.

        A job-point spell (Fire V for a Red Mage, Death for a Black Mage, Addle II for
        its gift line) is allowed to the granting main job at 99 even though its
        ordinary row belongs to another job or does not exist at all.
        """
        spell_id = int(spell_id)
        spell = self.world.service.spell(spell_id)
        # Geocolure spells are main-job only even when the support job has the level:
        # BG-wiki's Geomancer page is explicit that only main-job GEOs may cast them.
        if (spell is not None
                and str(spell.get("name") or "").casefold().startswith("geo-")
                and int(self.char.get("main_job") or 0) != 21):
            return False
        every, mine = self.job_point_spell_ids()
        if spell_id in mine:
            return True
        entries = self.world.service.spell_levels(spell_id)
        if entries:
            return self._spell_allowed(entries)
        # A job-point gift spell has no ordinary level row.  Only its granting job
        # may cast it; every other row-less spell (a Trust, a merit spell) stays open.
        return spell_id not in every

    def spell_bits(self) -> bytes:
        """0x0AA: every valid spell id, minus the ones this character's jobs cannot cast.

        The constant is the client's full valid-id set; retail greys a spell the job
        has not learned, so the bits for those are cleared here.  Spells with no level
        row (Trusts, merit and monster-only ids) stay set, except the job-point gift
        spells: those have no level row either, but only their granting job can use
        them.
        """
        bits = bytearray(SPELL_BITS)
        table = self.world.service.spell_level_table()
        every, mine = self.job_point_spell_ids()
        for spell_id, entries in table.items():
            spell_id = int(spell_id)
            if not 0 < spell_id < len(bits) * 8:
                continue
            if spell_id in mine or self._spell_allowed(entries):
                continue
            bits[spell_id // 8] &= ~(1 << (spell_id % 8)) & 0xFF
        # Gift spells with no ordinary level row (RDM's Refresh III/Temper II, BLM's
        # Death, …) are not in the table above.  Clear their bits unless this job's
        # gift grants them.  A spell that also has a level row is handled by the loop
        # above, so a Black Mage still keeps Fire V by level.
        gift_no_level = every.difference({int(sid) for sid in table})
        for spell_id in gift_no_level - mine:
            spell_id = int(spell_id)
            if 0 < spell_id < len(bits) * 8:
                bits[spell_id // 8] &= ~(1 << (spell_id % 8)) & 0xFF
        # Geocolure is main-job only; clear every Geo- bit for a support GEO so the
        # client's magic menu matches what cast_magic will accept.
        if int(self.char.get("main_job") or 0) != 21:
            try:
                by_name = self.world.service.spell_ids_by_name()
            except Exception:
                by_name = {}
            for name, ids in by_name.items():
                if not str(name).casefold().startswith("geo-"):
                    continue
                for spell_id in ids:
                    spell_id = int(spell_id)
                    if 0 < spell_id < len(bits) * 8:
                        bits[spell_id // 8] &= ~(1 << (spell_id % 8)) & 0xFF
        return bytes(bits)

    def cast_magic(self, p: bytes, act_index: int = 0) -> None:
        """C2S 0x01A action 0x03: the client is casting a spell.

        The body carries the spell id after UniqueNo/ActIndex/ActionId and the ground
        position the client picked.  MP is spent up front and the spell resolves on the
        tick after its cast time.  The result's value is the damage, the HP healed, or
        the status-effect id the spell lands; a self buff needs no monster, an enfeeble
        does.  Ninjutsu is the exception to MP: it spends a tool and never MP.
        """
        if len(p) < 16:
            return
        # UniqueNo(4) ActIndex(2) ActionId(2) then the cast buffer: SpellId, X, Z, Y.
        spell_id = struct.unpack_from("<I", p, 12)[0]
        spell = self.world.service.spell(spell_id)
        if spell is None:
            self.say("That spell does not exist.")
            return
        required = effects.required_instrument(str(spell["name"]))
        if required is not None and self.equipped_range_item() not in required:
            self.say("You do not have the instrument for %s." % spell["name"])
            return
        now = time.time()
        if self.casting and now < self.casting["finish"]:
            return
        trust = self.world.service.trust(spell_id)
        if trust is not None:
            self.cast_trust(spell, trust, now)
            return
        if not self.can_cast_spell(spell_id):
            self.say("You cannot cast that spell.")
            return
        ninjutsu = int(spell["skill"]) == NINJUTSU_SKILL
        # Manafont makes every spell free for its 30-second duration.
        cost = 0 if ninjutsu or self.has_effect(effects.MANAFONT) else int(spell["mp"])
        if not ninjutsu and int(self.char.get("mp_current", 0)) < cost:
            self.say("You do not have enough MP for %s." % spell["name"])
            self.queue += [self.char_stats(), self.char_status()]
            self.assert_stance()
            return
        if self.zoning or self.dead_until > now:
            return
        target = self.world.entity_by_targid(self.zone, int(act_index)) if act_index else None
        # Spell target flags come with the spell data (xi.targetType): 0x01 self, 0x02 party,
        # 0x04 enemy, 0x08 alliance, 0x10 player, 0x20 player_dead, 0x40 npc, 0x100 pet.
        # Warp is 0x01, Protect 0x5B, and Raise/Tractor/Arise are 0x20 -- a fallen player.
        # Demanding a live monster rejected every one of those.
        targets = int(spell.get("valid_targets") or 0)
        SELF_TARGET, ENEMY_TARGET = 0x01, 0x04
        spec = effects.for_spell(spell["name"])
        # Geo- spells are not in the ordinary effect table: their buff/hex half comes
        # from geomancy.INDI_EFFECTS.  The bubble prefix decides whether the spell is
        # aimed at a party-member anchor (Geo- buffs) or the monster (Geo- hexes).
        geo_aura = geomancy.indi_effect(str(spell["name"]))
        geo_bubble = geomancy.bubble(str(spell["name"]))
        # Accession widens the next white enhancing spell to the party.  Detect it now,
        # while the cast starts, but spend it in resolve_party_spell so the icon stays
        # up for the length of the cast bar and a cancelled cast does not eat it.  Haste
        # and Reraise are retail's exceptions: both are white enhancing magic, and
        # neither is widened.
        accession = (spec is not None and spec.kind == "buff"
                     and int(spell.get("skill") or 0) == packets.SKILL_ENHANCING
                     and effects.is_white_enhancing(str(spell["name"]))
                     and spec.effect not in (effects.HASTE, effects.RERAISE)
                     and self.has_effect(effects.ACCESSION))
        # Raise shares the healing skill but must not be treated as a heal on the caster.
        healing = (int(spell["skill"]) == packets.SKILL_HEALING
                   and not (targets & 0x20) and not effects.is_buff(spec))
        # A spell only needs a monster when it can be aimed at one and cannot be aimed at
        # you.  An enfeebling spell is always aimed at the monster even when its data also
        # carries the self bit, and so is Drain/Aspir/Dispel.
        needs_enemy = (bool(targets & ENEMY_TARGET) and not (targets & SELF_TARGET)
                       and not healing)
        if effects.is_debuff(spec) or (spec is not None and spec.kind == "special"
                                       and bool(targets & ENEMY_TARGET)):
            needs_enemy = True
        self_cast = not needs_enemy
        party_target = None
        if (self_cast and act_index and not accession
                and str(spell.get("name") or "").casefold().startswith("indi-")
                and self.has_effect(effects.ENTRUST)):
            party_target = self._party_spell_target(int(act_index))
            if party_target is not None:
                self_cast = False
                self.remove_effect(effects.ENTRUST, quiet=True)
                self.queue.append(self.char_status())
        if (self_cast and act_index and not accession
                and int(spell.get("skill") or 0) not in effects.SONG_SKILLS):
            can_party = bool(targets & 0x02) or bool(targets & 0x10)
            if can_party and (healing or (spec is not None and spec.kind == "buff")):
                party_target = self._party_spell_target(int(act_index))
                if party_target is None:
                    self.say("There is no valid target for %s." % spell["name"])
                    self.assert_stance()
                    return
                if party_target is self:
                    party_target = None
                else:
                    self_cast = False
        if (self_cast and act_index and not accession and geo_aura is not None
                and geo_bubble == "geo" and not geo_aura[2]):
            # Geo- buffs place the Luopan at a party member/self.  The generic party
            # branch above only sees effects.for_spell(), which has no Geomancy row, so
            # the anchor has to be resolved here or the bubble is put down at the GEO.
            anchor = self._party_spell_target(int(act_index))
            if anchor is not None and anchor is not self:
                party_target = anchor
                self_cast = False
        if needs_enemy:
            if target is None or target.kind != "mob" or not target.alive:
                self.say("There is no valid target for %s." % spell["name"])
                self.assert_stance()
                return
        else:
            target = None
        if target is not None and target.distance_to(*self.pos[:3]) > 25.0:
            self.say("You are too far away.")
            self.assert_stance()
            return
        tool_id = UTSUSEMI_TOOLS.get(str(spell["name"]))
        if tool_id is not None:
            consumed = self.world.service.consume_inventory_item(
                int(self.char["id"]), tool_id)
            if consumed is None:
                self.say("You do not have the tool for %s." % spell["name"])
                self.assert_stance()
                return
            quantity = int(consumed["quantity"])
            self.queue.append(sub(0x020, packets.item_attr(
                tool_id if quantity else 0, quantity, 0, int(consumed["slot"]))))
            try:
                self._queue_storage_returns(
                    self.world.service.refill_working_stock(int(self.char["id"])))
            except Exception as exc:
                log.warning("%s tool refill failed: %s", self.addr, exc)
        # Consume Altruism/Focalization/Tranquility/Equanimity/Enlightenment before the
        # sheet is built, so the spell gets their bonus exactly once and the removed
        # Enlightenment mods are not counted through the sheet as well.
        sch_bonus = self._sch_next_spell_bonuses(spell)
        sheet = self.stat_sheet()
        # The action packet starts the cast before the client has finished sending the
        # midcast set.  These are the numbers that set controls (Cure potency, MAB,
        # enfeebling duration, Macc), so they are computed again at the finish; this
        # first pass keeps the cast record complete for anything that reads it early.
        value_target = party_target or (self if healing else target)
        dark_seal = (bool(getattr(self, "_dark_seal", False))
                     and int(spell.get("skill") or 0) == packets.SKILL_DARK)
        cascade_bonus = int(getattr(self, "_cascade_bonus", 0) or 0)
        convergence = (self.has_effect(effects.CONVERGENCE)
                       and int(spell.get("skill") or 0) == packets.SKILL_BLUE)
        values = self._cast_numbers(
            spell, spec, value_target, healing=healing, sheet=sheet,
            dark_seal=dark_seal, cascade_bonus=cascade_bonus,
            convergence=convergence, macc_bonus=int(sch_bonus["macc"]),
            int_bonus=int(sch_bonus["int"]), mnd_bonus=int(sch_bonus["mnd"]))
        if convergence:
            self.remove_effect(effects.CONVERGENCE, quiet=True)
        if dark_seal:
            self._dark_seal = False
        if cascade_bonus:
            self._cascade_bonus = 0
        amount = values["amount"]
        resist = values["resist"]
        effect_duration = values["effect_duration"]
        effect_potency = values["effect_potency"]
        if not ninjutsu:
            self.char["mp_current"] = int(self.char.get("mp_current", 0)) - cost
        fast_cast = int(sheet.fighter.mods.get(mod.FASTCAST, 0))
        cast_ms = int(spell["cast_time"])
        song = int(spell["skill"]) in effects.SONG_SKILLS
        if song:
            # Nightingale halves and Troubadour raises the song cast to 150%;
            # together they are the usual 75%.  Song spellcasting-time gear (455)
            # is a further percentage reduction.  Soul Voice and Pianissimo's JP
            # rows add Fast Cast while their status is up.
            if self.has_effect(effects.NIGHTINGALE):
                cast_ms = cast_ms // 2
            if self.has_effect(effects.TROUBADOUR):
                cast_ms = cast_ms * 3 // 2
            song_fast = int(self.combat_mods().get(mod.SONG_SPELLCASTING_TIME, 0))
            cast_ms = max(500, cast_ms * max(0, 100 - song_fast) // 100)
            if self.has_effect(effects.SOUL_VOICE):
                fast_cast += job_points.category_total(10, "Soul Voice Effect")
            if self.has_effect(effects.PIANISSIMO):
                fast_cast += job_points.category_total(10, "Pianissimo Effect")
        else:
            fast_cast += (int(self.combat_mods().get(mod.NINJUTSU_FASTCAST, 0))
                          if int(spell["skill"]) == NINJUTSU_SKILL else 0)
        if self.has_effect(effects.HASSO):
            # The stance's other half: +50% casting time for all magic while it is up.
            cast_ms = int(cast_ms * 1.5)
        if self.has_effect(effects.CHAINSPELL):
            cast_ms = 0
        if getattr(self, "_spontaneity", False):
            cast_ms = 0
            self._spontaneity = False
        cast_finish = now + combat.cast_time(cast_ms, fast_cast) / 1000.0
        # Red Mage Quick Magic: a 5% trait proc makes the cast finish on the next
        # tick.  The job-point "Quick Magic Effect" row is not extra proc chance:
        # LandSandBoat's comment for it is "MP consumption -2%", so a proc refunds
        # 2% of the spell's MP cost per rank (40% at rank 20).
        if int(self.char.get("main_job") or 0) == 5 and self.world.rng.random() < 0.05:
            cast_finish = now
            percent = job_points.category_total(5, "Quick Magic Effect")
            if percent and not ninjutsu:
                paid = int(self.char.get("mp_current", 0))
                max_mp = max(0, int(self.char.get("mp", 0)))
                refund = max(0, int(cost)) * min(100, int(percent)) // 100
                self.char["mp_current"] = min(max_mp, paid + refund)
            self.say("Quick Magic!")
        self.casting = {"spell": spell, "target": int(target.id) if target else 0,
                        "party_target": int(party_target.char["char_id"]) if party_target else 0,
                        "finish": cast_finish,
                        "amount": int(amount), "healing": healing,
                        "self": self_cast, "effect": spec,
                        "accession": accession,
                        "effect_duration": effect_duration,
                        "effect_potency": effect_potency,
                        "skill": int(spell["skill"]), "resist": resist,
                        "dark_seal": dark_seal, "cascade_bonus": cascade_bonus,
                        "convergence": convergence,
                        "sch_macc": int(sch_bonus["macc"]),
                        "sch_enmity": int(sch_bonus["enmity"]),
                        "sch_int": int(sch_bonus["int"]),
                        "sch_mnd": int(sch_bonus["mnd"])}
        self.stop_resting()
        self.queue += [self.char_stats(), self.char_status()]
        try:
            self.world.service.save_vitals(self.char["id"], int(self.char.get("hp_current", 0)),
                                           int(self.char.get("mp_current")))
        except Exception:
            pass
        # 0x028 MagicStart: this is what puts the cast bar and the casting animation on the
        # client.  The value is the spell id; cmd_arg is the school's four-character code
        # (canj for ninjutsu, cawh for white magic, ...), not the spell id.  The result's
        # animation is the spell's own client animation, and the message is retail's
        # "starts casting" line: the client prints it for the caster and everyone nearby.
        actor = int(self.char["char_id"])
        if party_target is not None:
            start_target = int(party_target.char["char_id"])
        else:
            start_target = int(target.id) if target is not None else actor
        self.queue.append(sub(0x028, packets.battle_action(
            actor, start_target, int(spell["id"]),
            animation=spell_animation(spell),
            message=packets.MESSAGE_MAGIC_STARTS_CASTING, kind=0,
            category=packets.ACTION_CATEGORY_MAGIC_START,
            action_id=packets.magic_cast_arg(int(spell["skill"])), info=0)))

    def _shikikoyo(self, act_index: int, ability: dict, now: float) -> None:
        """Share TP above 1000 with the targeted party member.

        The Samurai keeps 1000 TP; the target gains what was above it, and the merit
        ranks (+12% each) raise what the target receives, which is why 5/5 hands over
        more than the Samurai gives up.
        """
        ally, error = self._waltz_target(act_index, ability)
        if error:
            self.say(error)
            return
        if ally is self:
            self.say("You cannot share TP with yourself.")
            return
        tp = int(self.char.get("tp", 0))
        share = max(0, tp - 1000)
        if share <= 0:
            self.say("You need more than 1000 TP to share.")
            return
        ranks = 0
        if int(self.char.get("main_job") or 0) == 12:
            ranks = min(5, int(self.merit_counts().get(merits.SHIKIKOYO, 0)))
        received = share * (100 + 12 * ranks) // 100
        self.char["tp"] = tp - share
        target_tp = min(3000, int(ally.char.get("tp", 0)) + received)
        ally.char["tp"] = target_tp
        self.queue.append(self.party_member())
        if ally is not self:
            ally.queue.append(ally.party_member())
            self.say("You share %d TP with %s." % (received, ally.char.get("name", "them")))

    def _blade_bash(self, target, now: float) -> None:
        """Blade Bash's stun: no damage, no TP, a short stun on the target."""
        if target is None or getattr(target, "kind", "") != "mob" or not target.alive:
            return
        target.effect_state[effects.STUN] = {"until": now + 3.0, "power": 0}
        if effects.STUN not in target.status_effects:
            target.status_effects.append(effects.STUN)
        self.say("%s is stunned." % target.name)

    def _seed_konzen_chain(self, entity, ws: dict, now: float) -> None:
        """Konzen-ittai readies the monster so the weapon skill chains by itself.

        The status "readies the enemy for a skillchain": the skill that lands while it
        is up opens and closes the chain in one action.  We seed the monster with a
        property the skill resonates with, and let the normal advance form the chain.
        """
        props = self.world.service.weaponskill_properties(int(ws["id"]))
        if not any(props):
            return
        closing = int(props[0])
        for resonance in range(1, 15):
            if skillchain.TRANSITIONS.get((closing, resonance)):
                entity.skillchain = skillchain.SkillchainState(
                    props=(resonance, 0, 0), started=now - 4.0, until=now + 10.0,
                    opener=str(self.char.get("name") or self.addr))
                return

    def _song_extra_debuff(self, entity, spell: dict, spec, now: float,
                           duration: float | None) -> None:
        """The parts of a song debuff the monster keeps as their own effect.

        Threnody's Magic Evasion down and Elegy's attack-speed slow are not modifiers on
        the caster: ``world.monster_debuff_mods`` reads the first from the mob's effect
        state, and the mob's swing timer multiplies its delay by the second's potency.
        They ride beside the song's own icon, hidden from the wear-off line.
        """
        family = effects.song_family(str(spell["name"]))
        if family not in ("threnody", "elegy"):
            return
        seconds = float(duration or 0.0)
        if seconds <= 0:
            return
        mods = self.combat_mods()
        if family == "threnody":
            value = effects.song_table_value(str(spell["name"]), "meva", mods)
            if value > 0:
                entity.effect_state[effects.MAGIC_EVASION_DOWN] = {
                    "until": now + seconds, "power": value, "potency": value,
                    "hidden": True, "icon": int(spec.effect)}
        else:
            value = effects.song_table_value(str(spell["name"]), "slow", mods)
            if value > 0:
                entity.effect_state[effects.SLOW] = {
                    "until": now + seconds, "potency": value,
                    "hidden": True, "icon": int(spec.effect)}

    def _song_debuff_tick(self, spell: dict, spec: "effects.SpellEffect") -> int:
        """Requiem's per-tick damage after Song+ gear, Soul Voice and the job-point row.

        Requiem's +3 a rank (60 at rank 20) lands *after* Soul Voice/Marcato: the
        wiki's worked examples are (14 x 1.5) + 60 = 81 and (14 x 2) + 60 = 88.
        """
        soul_voice = self.has_effect(effects.SOUL_VOICE)
        name = str(spell["name"])
        _mods, tick = effects.song_potency_values(
            name, spec, self.combat_mods(),
            soul_voice=soul_voice,
            marcato=self.has_effect(effects.MARCATO) and not soul_voice)
        if int(self.char.get("main_job") or 0) == 10:
            tick += job_points.category_total(10, "Requiem Effect")
        return max(0, int(tick))

    def song_duration_flat(self, name: str) -> float:
        """Flat seconds a song's timer gets from its job-point row (Lullaby +1s a rank)."""
        if int(self.char.get("main_job") or 0) != 10:
            return 0.0
        if effects.song_family(name) != "lullaby":
            return 0.0
        return float(job_points.category_total(10, "Lullaby Duration"))

    def _cast_numbers(self, spell: dict, spec, target, *, healing: bool,
                      sheet=None, dark_seal: bool = False,
                      cascade_bonus: int = 0, convergence: bool = False,
                      macc_bonus: int = 0, int_bonus: int = 0,
                      mnd_bonus: int = 0) -> dict:
        """The result values the midcast gear controls.

        The host wears the fast-cast set before the action and the midcast set right
        behind it, exactly like GearSwap.  The server used to freeze these numbers in
        ``cast_magic`` when the action arrived, before the midcast ``0x050`` burst, so a
        Cure was rolled with the fast-cast set's 0% ``"Cure" potency`` and a nuke with
        the fast-cast set's MAB.  They are read here from the gear on at the finish.
        ``sheet`` lets the caller reuse the stat sheet it already built.
        """
        if sheet is None:
            sheet = self.stat_sheet()
        level = int(self.char.get("main_level", 1))
        cost = 0 if int(spell.get("skill") or 0) == NINJUTSU_SKILL \
            else int(spell.get("mp") or 0)
        skill_values, _base_caps = self.effective_skills()
        spell_skill = int(skill_values.get(int(spell["skill"]), 0))
        mob = target is not None and getattr(target, "is_mob", lambda: False)()
        target_sheet = self.world.monster_sheet(target) if mob else None
        if mob:
            # Debuffs a weapon skill left on the monster are part of the magic target
            # too: Magic Defense Down / Magic Evasion Down are modifier deltas, INT Down
            # a flat stat subtraction.  The monster sheet is cached and stays clean.
            target_mods = self.world.monster_debuff_mods(target)
            target_int = int(target_sheet.attributes.get("int", 0))
            int_down = target.effect_state.get(effects.INT_DOWN)
            if int_down is not None:
                target_int = max(0, target_int - int(int_down.get("power", 0)))
        else:
            # A Cure's received-potency line belongs to the player being healed.
            target_mods = (target.combat_mods()
                           if target is not None and hasattr(target, "combat_mods")
                           else {})
            target_int = 0
        base = int(spell["base"])
        caster_int = int(sheet.attributes.get("int", 0)) + int(int_bonus)
        caster_mnd = int(sheet.attributes.get("mnd", 0)) + int(mnd_bonus)
        # Helix Magic Acc./Atk. merits add +3 Magic Accuracy and +2 Magic Atk. Bonus
        # a rank to Helix spells only; every other spell keeps the sheet's mods.
        spell_mods = sheet.fighter.mods
        if spec is not None and spec.helix:
            helix_rank = self._sch_merit(merits.SCH_HELIX_MAGIC)
            if helix_rank:
                spell_mods = dict(spell_mods)
                spell_mods[mod.MACC] = (int(spell_mods.get(mod.MACC, 0))
                                        + 3 * helix_rank)
                spell_mods[mod.MATT] = (int(spell_mods.get(mod.MATT, 0))
                                        + 2 * helix_rank)
        if macc_bonus:
            spell_mods = dict(spell_mods)
            spell_mods[mod.MACC] = (int(spell_mods.get(mod.MACC, 0))
                                    + int(macc_bonus))
        if healing:
            amount = effects.healing_amount(
                int(cost * 3 + level), sheet.fighter.mods, target_mods)
        elif spec is not None and spec.helix and target_sheet is not None:
            # A Helix's opening hit is a nuke with its own dINT curve; the same number
            # comes back every ten seconds while the effect lasts (see resolve_casting).
            amount = combat.helix_damage(
                base=base, multiplier=float(spell["multiplier"]),
                caster_int=caster_int,
                target_int=target_int,
                skill=spell_skill, mods=spell_mods,
                target_mods=target_mods,
                target_level=int(target_sheet.fighter.level))
        elif spec is not None and spec.damage:
            # Dia and Diaga: a small opening hit, then the DoT.  Their data is a zero
            # stat multiplier and 1-5 HP per tick, so the elemental nuke formula (dINT x
            # 2, Magic Atk. Bonus, flat Magic Damage) must not touch them; with this
            # character's Hvergelmir set it turned a 2-base spell into 1,475 damage.
            amount = combat.dia_damage(
                base=base,
                caster_mnd=caster_mnd,
                target_mnd=(int(target_sheet.attributes.get("mnd", 0))
                            if target_sheet is not None else 0))
        elif spec is None and base > 0 and target_sheet is not None:
            if spell_skill == NINJUTSU_SKILL:  # elemental Ninjutsu only
                spell_mods = dict(spell_mods)
                spell_mods[mod.MAGIC_DAMAGE] = (
                    int(spell_mods.get(mod.MAGIC_DAMAGE, 0))
                    + int(spell_mods.get(mod.NINJUTSU_MAGIC_DAMAGE, 0)))
            amount = combat.magic_damage(
                base=base, multiplier=float(spell["multiplier"]),
                caster_int=caster_int,
                target_int=target_int,
                skill=spell_skill, mods=spell_mods,
                target_mods=target_mods,
                target_level=int(target_sheet.fighter.level))
        elif spec is not None and spec.kind == "special":
            # Drain and Aspir keep the old flat opening value; Dispel ignores it.
            amount = effects.drain_amount(int(cost * 2 + level // 3),
                                          sheet.fighter.mods)
        else:
            # Enfeebles, buffs and the rest do not invent damage.  The old fallback here
            # is what made Breakga hit for 233 and turned every unimplemented spell into
            # a fixed nuke.
            amount = 0
        if cascade_bonus and not healing and int(amount) > 0:
            amount = int(amount) + int(cascade_bonus)
        if convergence and not healing and int(amount) > 0:
            amount = int(amount * 3 // 2)
        # Enfeebles share the Magic Accuracy roll: an under-geared caster keeps the
        # effect for less time instead of the spell always landing at full duration.
        resist = 1.0
        # A Magic Burst is a damaging spell of the chain's element launched inside the
        # window: it gets the burst multiplier and +100 Magic Accuracy.
        burst_tier = 0
        if target_sheet is not None and not healing:
            burst_tier = skillchain.magic_burst_tier(
                getattr(target, "skillchain", None), int(spell.get("element") or 0),
                time.time())
        if target_sheet is not None:
            # The Bard job-point "Song Accuracy Bonus" (+1 a rank) is song-only; it
            # adds to the singing skill here rather than to the generic Magic Accuracy.
            song_skill = spell_skill
            if (int(spell.get("skill") or 0) in effects.SONG_SKILLS
                    and int(self.char.get("main_job") or 0) == 10):
                song_skill += job_points.category_total(10, "Song Accuracy Bonus")
            # Distract and Frazzle use dMND instead of dINT and carry an innate +150
            # Magic Accuracy (BG Wiki).  Without this they resisted like a tier-I
            # enfeebling even with a RDM's capped skill.
            name_key = str(spell.get("name") or "").casefold()
            dmnd_enfeeble = (name_key.startswith("frazzle")
                             or name_key.startswith("distract"))
            diabolic = (int(spell.get("skill") or 0) == packets.SKILL_DARK
                        and float(getattr(self, "_diabolic_until", 0.0)) > time.time())
            resist = combat.magic_resist(
                skill=song_skill + (150 if dmnd_enfeeble else 0)
                      + (100 if burst_tier else 0) + (100 if dark_seal else 0)
                      + (50 if diabolic else 0) + (50 if convergence else 0),
                caster_int=caster_mnd if dmnd_enfeeble else caster_int,
                mods=spell_mods,
                target_level=int(target_sheet.fighter.level),
                target_mods=target_mods)
        debuff = effects.is_debuff(spec)
        if spec is not None and spec.helix:
            # A Helix's length comes from the Scholar level, not the enfeebling table.
            sch_level = effects.scholar_level(
                int(self.char.get("main_job") or 0), int(self.char.get("main_level") or 0),
                int(self.char.get("sub_job") or 0), int(self.char.get("sub_level") or 0))
            effect_duration = effects.helix_duration(
                sch_level,
                dark_arts=(self.has_effect(effects.DARK_ARTS)
                           or self.has_effect(effects.ENLIGHTENMENT)),
                jp_rank=JOB_POINT_RANK)
        elif (spec is not None and debuff
              and int(spell.get("skill") or 0) in effects.SONG_SKILLS):
            # Troubadour doubles a debuff song's timer; Soul Voice leaves Lullaby's
            # duration alone (it doubles its magic accuracy, which is not modelled),
            # and the Clarion/Tenuto/Marcato job-point seconds are added last.
            soul_voice = self.has_effect(effects.SOUL_VOICE)
            marcato = self.has_effect(effects.MARCATO) and not soul_voice
            effect_duration = effects.song_duration(
                spec, name=str(spell["name"]), mods=sheet.fighter.mods,
                troubadour=self.has_effect(effects.TROUBADOUR),
                soul_voice=False, marcato=marcato,
                clarion=self.has_effect(effects.CLARION_CALL),
                tenuto=self.has_effect(effects.TENUTO),
                flat_seconds=self.song_duration_flat(str(spell["name"])))
        else:
            effect_duration = (effects.debuff_duration(
                spec, skill=int(spell["skill"]), mods=sheet.fighter.mods,
                name=str(spell["name"]))
                if debuff else 0.0)
        effect_potency = (effects.debuff_potency(
            spec, skill=int(spell["skill"]), mods=sheet.fighter.mods)
            if debuff else 0)
        if (int(self.char.get("main_job") or 0) == 21
                and str(spell.get("name") or "").casefold().startswith("indi")):
            effect_duration += job_points.category_total(
                21, "Indicolure Spell Effect Dur.")
        if burst_tier and not healing and int(amount) > 0:
            # The base burst multiplier, then the "Magic Burst Bonus" family: the
            # Red Mage trait is the uncapped 274 and SCH/BLM gear and job points use
            # the +40%-capped 487.  Without this a RDM's Mag. Burst Bonus trait (5/7
            # at 85/95) did nothing at all.
            mods = sheet.fighter.mods
            amount = int(amount * skillchain.magic_burst_multiplier(burst_tier)
                         * skillchain.magic_burst_bonus(
                             capped=int(mods.get(mod.MAGIC_BURST_BONUS_CAPPED, 0)),
                             uncapped=int(mods.get(mod.MAGIC_BURST_BONUS_UNCAPPED, 0))))
            if float(getattr(self, "_sengikori_mb_until", 0.0) or 0.0) > time.time():
                amount = int(amount * 1.25)
                self._sengikori_mb_until = 0.0
        # Magic Burst and Sengikori multiply after the engine has already capped the
        # spell, so a burst nuke gets the same 99,999 ceiling as a plain one here.
        if not healing:
            amount = combat.cap_damage(amount)
        return {"amount": int(amount), "resist": resist,
                "magic_burst": int(burst_tier),
                "effect_duration": effect_duration,
                "effect_potency": effect_potency}

    def _refresh_cast_numbers(self, cast: dict, target) -> None:
        """Re-read a finished cast's numbers from the gear worn at the finish."""
        cast.update(self._cast_numbers(
            cast["spell"], cast.get("effect"), target,
            healing=bool(cast.get("healing")),
            dark_seal=bool(cast.get("dark_seal")),
            cascade_bonus=int(cast.get("cascade_bonus") or 0),
            convergence=bool(cast.get("convergence")),
            macc_bonus=int(cast.get("sch_macc") or 0),
            int_bonus=int(cast.get("sch_int") or 0),
            mnd_bonus=int(cast.get("sch_mnd") or 0)))

    def resolve_casting(self, now: float) -> None:
        """Apply a finished cast: a buff, a debuff, damage, or a heal."""
        if not self.casting or now < self.casting["finish"]:
            return
        cast = self.casting
        self.casting = None
        if cast.get("trust") is not None:
            self.finish_trust_cast(cast["trust"])
            return
        spell = cast["spell"]
        spec = cast.get("effect")
        me = int(self.char["char_id"])
        summon = pets.summon_key(str(spell.get("name") or ""))
        if summon is not None:
            self.world.spawn_pet(self, summon, now)
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, 0, animation=spell_animation(spell), kind=0, message=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            if self.engaged_id and not self.zoning:
                self.assert_stance()
            return
        if str(spell.get("name") or "").casefold().startswith(("indi-", "geo-")):
            self._indi_aura(spell, now, cast)
            self.assert_stance()
            return
        party_target_id = int(cast.get("party_target") or 0)
        if party_target_id:
            target = self.world.session_by_char(party_target_id)
            if (target is None or int(target.zone) != int(self.zone)
                    or target.dead_until
                    or int(target.char.get("hp_current", 0)) <= 0):
                self.say("The spell fizzles.")
                self.assert_stance()
                return
            if cast["healing"]:
                self._refresh_cast_numbers(cast, target)
                self._heal_target(target, spell, cast)
                self.assert_stance()
                return
            if spec is not None and spec.kind == "buff":
                self._buff_target(target, spell, now, spec)
                self.assert_stance()
                return
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), 0,
                animation=spell_animation(spell), kind=0,
                message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"])))
            self.queue.append(action)
            target.queue += [action, target.char_status()]
            return
        if str(spell.get("name") or "").casefold().startswith(("indi-", "geo-")):
            self._indi_aura(spell, now, cast)
            self.assert_stance()
            return
        if cast["healing"]:
            self._refresh_cast_numbers(cast, self)
            self._heal_target(self, spell, cast)
            self.assert_stance()
            return
        if cast.get("self"):
            if (spec is not None and int(spell.get("skill") or 0) in effects.SONG_SKILLS
                    and effects.is_buff(spec)):
                self.resolve_song_spell(spell, now, spec, cast)
            elif (self.has_effect(effects.DIFFUSION) and spec is not None
                    and int(spell.get("skill") or 0) == packets.SKILL_BLUE):
                self.remove_effect(effects.DIFFUSION, quiet=True)
                self.resolve_party_spell(spell, now, spec)
            elif (cast.get("accession") and spec is not None
                    and self.has_effect(effects.ACCESSION)):
                self.resolve_party_spell(spell, now, spec)
            elif (spec is not None and spec.kind == "buff"
                    and effects.is_area_party_buff(spell["name"])):
                self.resolve_area_buff(spell, now, spec)
            else:
                self.resolve_self_spell(spell, now, spec)
            if self.engaged_id and not self.zoning:
                self.assert_stance()
            return
        entity = self.world.entity_by_id(self.zone, int(cast["target"]))
        if entity is None or not entity.alive:
            self.say("The spell fizzles.")
            self.assert_stance()
            return
        self._refresh_cast_numbers(cast, entity)
        self._last_target_hp = entity.hp_max
        animation = spell_animation(spell)
        if effects.is_debuff(spec):
            duration_scale = (1.0 if not spec.resistible
                              else float(cast.get("resist", 1.0)))
            damage = int(cast.get("amount") or 0) if (spec.damage or spec.helix) else 0
            remaining = False
            if not spec.helix or damage > 0:
                # A Helix stores its opening hit as the DoT's power, so the monster takes
                # that same number again every ten seconds.  A nullified opening hit
                # lands no effect at all, which is the order LandSandBoat's helix script
                # checks.  A tier-1 Helix must not knock a tier-2 Helix off the monster;
                # apply_mob_effect returns False without touching the active one.
                remaining = self.world.apply_mob_effect(
                    entity, spec, self, now, duration_scale=duration_scale,
                    duration=cast.get("effect_duration"),
                    potency=cast.get("effect_potency"),
                    tick=(min(damage, effects.HELIX_TICK_CAP) if spec.helix else
                          (self._song_debuff_tick(spell, spec)
                           if int(spec.effect) == effects.REQUIEM else None)),
                    tick_interval=(effects.HELIX_TICK_SECONDS if spec.helix else 3.0),
                    first_tick_delay=(self.world.rng.uniform(*effects.HELIX_FIRST_TICK)
                                      if spec.helix else None),
                    tier=(effects.tier_of(spell["name"]) if spec.helix else 0),
                    name=str(spell.get("name") or ""))
                if remaining:
                    self._song_extra_debuff(entity, spell, spec, now,
                                            cast.get("effect_duration"))
            defeated = False
            if damage > 0:
                # Dia, Diaga and a Helix are one action in retail: the result prints the
                # opening damage and the effect is already on the monster.  A second
                # "receives the effect" line on top of the damage line would repeat the
                # cast message.
                defeated = entity.hp - damage <= 0
                # Apply the opening hit before the chain: a skillchain's damage is a
                # percentage of the closing hit that actually landed.  Immanence turns
                # this Helix into a weapon-skill-equivalent, and its additional-effect
                # block rides this same result so the client draws the chain.
                entity.hp = max(0, entity.hp - damage)
                chain = self._magic_skillchain(entity, spell, damage, now,
                                               defeated=defeated)
                if chain is not None and chain["defeated"]:
                    defeated = True
                result = dict(
                    damage=damage, defeated=defeated, animation=animation, kind=0,
                    message=(packets.MESSAGE_MAGIC_BURST if cast.get("magic_burst")
                             else packets.MESSAGE_MAGIC_DMG), info=0)
                if chain is not None and int(chain["damage"]) > 0:
                    result.update(add_effect=int(chain["proc"]),
                                  add_value=int(chain["damage"]),
                                  add_message=int(chain["message"]))
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(entity.id), results=[result],
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
                self.queue_entity(entity, packets.SEND_HP)
                self.world.wake_mob(entity)
            elif remaining:
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(entity.id), int(spec.effect), animation=animation,
                    kind=0, message=packets.MESSAGE_MAGIC_ENFEEB, info=0,
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
            else:
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(entity.id), 0, animation=animation, kind=0,
                    message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
            if damage:
                self.world.add_damage_hate(entity, me, damage, now)
            else:
                self.world.add_mob_hate(entity, me, HATE_ENFEEBLE, now)
            self._sch_relieve_hate(entity, cast)
            if defeated:
                self.world.kill_mob(self, entity, now)
            self.assert_stance()
            return
        if spec is not None and spec.kind == "special":
            self.resolve_special_spell(spell, entity, cast)
            self.assert_stance()
            return
        damage = int(cast["amount"])
        if spec is None and damage <= 0:
            # A spell the engine has no data for (Virus, Burn, the Absorb line, ...) must
            # not print "takes 0 points of damage".  Retail says it did nothing, and so
            # does this.
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), 0, animation=animation, kind=0,
                message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.world.add_mob_hate(entity, me, HATE_ENFEEBLE, now)
            self.assert_stance()
            return
        defeated = entity.hp - damage <= 0
        # The spell's own hit lands first; an Immanence chain is a percentage of it.
        # The chain's additional-effect block rides the same finished-spell result, so
        # the client plays the skillchain animation from this cast, not a second one.
        entity.hp = max(0, entity.hp - damage)
        chain = self._magic_skillchain(entity, spell, damage, now,
                                       defeated=defeated)
        if chain is not None and chain["defeated"]:
            defeated = True
        result = dict(
            damage=damage, defeated=defeated, animation=animation, kind=0,
            message=(packets.MESSAGE_MAGIC_BURST if cast.get("magic_burst")
                     else packets.MESSAGE_MAGIC_DMG), info=0)
        if chain is not None and int(chain["damage"]) > 0:
            result.update(add_effect=int(chain["proc"]),
                          add_value=int(chain["damage"]),
                          add_message=int(chain["message"]))
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(entity.id), results=[result],
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))))
        self.queue_entity(entity, packets.SEND_HP)
        self.world.wake_mob(entity)
        # Damage is the enmity that makes a monster turn around: an idle monster claims
        # to the caster, and one already fighting someone else switches when this spell
        # out-weighs the hate already on it.
        self.world.add_damage_hate(entity, me, damage, now)
        self._sch_relieve_hate(entity, cast)
        if defeated:
            self.world.kill_mob(self, entity, now)
        self.assert_stance()

    def resolve_special_spell(self, spell: dict, entity, cast: dict) -> None:
        """Drain, Aspir and Dispel: the spells whose result is not a plain damage hit."""
        me = int(self.char["char_id"])
        name = str(spell["name"])
        folded = name.casefold()
        animation = spell_animation(spell)
        if folded.startswith("dispel") or effects.song_family(name) == "finale":
            removed = self.world.dispel_mob(entity)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), removed, animation=animation, kind=0,
                message=(packets.MESSAGE_MAGIC_ENFEEB if removed
                         else packets.MESSAGE_MAGIC_NO_EFFECT), info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=int(spell["id"]))))
            self.world.add_mob_hate(entity, me, HATE_ENFEEBLE, time.time())
            self._sch_relieve_hate(entity, cast)
            return
        if folded.startswith("aspir"):
            amount = max(1, int(cast["amount"]) // 2)
            self.char["mp_current"] = min(int(self.char.get("mp", 0)),
                                          int(self.char.get("mp_current", 0)) + amount)
            self.queue += [self.char_stats(), self.char_status(), self.party_member()]
            try:
                self.world.service.save_vitals(int(self.char["id"]),
                                               int(self.char.get("hp_current", 0)),
                                               int(self.char["mp_current"]))
            except Exception:
                pass
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), amount, animation=animation, kind=0,
                message=packets.MESSAGE_MAGIC_DRAIN_MP,
                info=0, category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.world.add_damage_hate(entity, me, amount, time.time())
            self._sch_relieve_hate(entity, cast)
            return
        if folded.startswith("drain"):
            amount = max(1, int(cast["amount"]))
            hp = int(self.char.get("hp_current", 0))
            healed = min(int(self.char.get("hp", hp)), hp + amount)
            self.char["hp_current"] = healed
            entity.hp = max(0, entity.hp - amount)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), amount, animation=animation, kind=0,
                message=packets.MESSAGE_MAGIC_DRAIN_HP,
                info=0, category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.queue_entity(entity, packets.SEND_HP)
            self.queue += [self.char_status(), self.party_member()]
            self.world.add_damage_hate(entity, me, amount, time.time())
            self._sch_relieve_hate(entity, cast)
            if entity.hp <= 0:
                self.world.kill_mob(self, entity, time.time())
            return
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(entity.id), 0, animation=animation, kind=0,
            message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=int(spell["id"]))))

    def weaponskill(self, p: bytes, act_index: int = 0) -> None:
        """C2S 0x01A action 0x07: a weapon skill.

        The body carries the skill id after UniqueNo/ActIndex/ActionId.  The server only
        accepts a skill that is on the character's current list, which is the equipped
        weapon's type at or below the character's skill value; that is the same list
        sent to the client in char_abilities() (packet 0x0AC).

        A weapon skill is not only a damage roll.  ``weapon_skill_effects`` carries the
        self-restores (Myrkr, Dagan), the damage drains and the status effects the rest
        of the table applies; this method spends the TP, resolves the hit, then applies
        that row.  Self-targeted skills need neither a monster nor melee range.
        """
        if len(p) < 16:
            return
        # The phase engine can put the precast 0x050s and the action in one packet batch.
        # The action handler must see the batch's equipment, not the previous outfit:
        # stat_sheet() and the Prime "Adds weapon skill" grant both read char_equip.
        self.flush_equipment()
        ws_id = struct.unpack_from("<I", p, 12)[0]
        try:
            ws = self.world.service.weaponskill(ws_id)
        except Exception as exc:
            log.warning("%s weapon skill lookup failed: %s", self.addr, exc)
            return
        if ws is None:
            self.say("That weapon skill does not exist.")
            return
        if weapon_skill_effects.is_campaign_only(str(ws["name"])):
            self.say("%s can only be used in a Campaign Battle." % ws["name"])
            return
        try:
            available = set(self.equipped_weapon_skills())
        except Exception as exc:
            log.warning("%s weapon skill availability failed: %s", self.addr, exc)
            available = set()
        if int(ws_id) not in available:
            # A GearSwap/equip race is invisible otherwise: the HUD advertised the
            # skill from the previous outfit, but this handler sees the weapon that is
            # in char_equip when the action arrives.  Log the ids so a failed attempt
            # can be diagnosed from server.log.
            # Do not name these ``sub``: that shadows the module-level packet helper
            # for the whole function, so every later ``sub(0x028, ...)`` raises
            # UnboundLocalError instead of sending the weapon skill.
            main_id = (self.equipped.get(0) or (0, 0, 0))[2]
            sub_id = (self.equipped.get(1) or (0, 0, 0))[2]
            log.info("%s weapon skill %s (%d) rejected: main=%s sub=%s available=%s",
                     self.addr, ws["name"], int(ws_id), int(main_id or 0),
                     int(sub_id or 0), sorted(available))
            self.say("You cannot use %s with your equipped weapon." % ws["name"])
            return
        extra = weapon_skill_effects.for_weaponskill(str(ws["name"]))
        self_targeted = bool(extra is not None and extra.self_targeted)
        entity = None
        if not self_targeted:
            if self.engaged_id:
                entity = self.world.entity_by_id(self.zone, int(self.engaged_id))
            if entity is None and act_index:
                entity = self.world.entity_by_targid(self.zone, int(act_index))
            if entity is None or entity.kind != "mob" or not entity.alive:
                self.say("There is no valid target for %s." % ws["name"])
                return
            if entity.distance_to(*self.pos[:3]) > MELEE_RANGE + 1.0:
                self.say("You are too far away.")
                return
        tp = int(self.char.get("tp", 0))
        if tp < 1000:
            self.say("You do not have enough TP for %s." % ws["name"])
            return
        now = time.time()
        sheet = None
        try:
            mods = self.combat_mods()
            sheet = self.stat_sheet(mods=mods)
            effective_tp = self._weaponskill_effective_tp(tp, mods, now)
        except Exception as exc:
            log.warning("%s weapon skill modifiers unavailable: %s", self.addr, exc)
            mods, effective_tp = {}, tp
        if sheet is None:
            try:
                sheet = self.stat_sheet()
            except Exception:
                sheet = None
        # A weapon skill spends every point of TP up to the 3000 cap; the bar keeps the
        # excess.  TP Bonus gear and Fencer raise the TP used for scaling, not the spend.
        # Meikyo Shisui spends exactly 1000 but still scales from the current TP.
        meikyo = float(getattr(self, "_meikyo_until", 0.0) or 0.0) > now
        sekkanoki = float(getattr(self, "_sekkanoki_until", 0.0) or 0.0) > now
        if meikyo or sekkanoki:
            self._sekkanoki_until = 0.0
        self._warriors_charge_until = 0.0
        self.char["tp"] = tp - (1000 if (meikyo or sekkanoki) else min(tp, TP_MAX))
        self.queue.append(self.party_member())
        # Prime Aftermath goes up before the hit loop: retail applies it to the weapon
        # skill that grants it ("AM applies on the activating WS"), and the rest of the
        # duration then rides on the sheet for auto-attacks and later skills.
        try:
            self._grant_prime_aftermath(ws, tp)
        except Exception as exc:
            log.warning("%s prime aftermath unavailable: %s", self.addr, exc)
        me = int(self.char["char_id"])
        animation = int(ws["animation"])
        # Retail sends a SkillStart action before the SkillFinish: the start carries the
        # skill id in its result and message 43, which is what puts the client into a
        # weapon-skill context.  Without it the finish's sub-kind is not always read as
        # a weapon-skill animation (Rudra's Storm's 236 is also Frost's spell animation),
        # so the client can play a spell motion instead.
        self._queue_weaponskill_start(ws, me if self_targeted else int(entity.id))

        if self_targeted:
            self._self_weaponskill(ws, extra, effective_tp, animation)
            self.next_attack_at = now + 2.0
            return

        # Weapon skills spend every point of TP and scale with what you spent.  Each
        # skill carries its own fTP anchors, WSC and hit count (data/weapon_skills.json),
        # so Blade: Metsu is the 5.0-fTP, 80%-DEX skill retail has instead of the old
        # one-size-fits-all 2.0 curve.  The damage bonus is folded into the per-hit fTP
        # so it lands before the target's damage-taken, and the first-hit line is only
        # folded into the first hit.
        no_damage = bool(extra is not None and extra.no_damage)
        magic_ws = False
        if no_damage:
            # Energy Drain and Energy Steal are MP drains, not HP damage: retail prints
            # the MP taken, and the formula uses dagger skill and MND, not the hit.
            miss, damage, critical, defeated = False, 0, False, False
        else:
            try:
                ws_data = weapon_skills.for_id(int(ws["id"]))
            except Exception as exc:
                log.warning("%s weapon skill data unavailable: %s", self.addr, exc)
                ws_data = None
            magic_ws = bool(ws_data is not None and ws_data.magic)
            ranged_ws = bool(
                (ws_data is not None and int(ws_data.skill) in (25, 26))
                or int(ws.get("skill") or 0) in (25, 26))
            try:
                attributes = getattr(self.stat_sheet(), "attributes", {})
            except Exception as exc:
                log.warning("%s weapon skill stats unavailable: %s", self.addr, exc)
                attributes = {}
            wsc = ws_data.wsc_for(attributes) if ws_data is not None else 0
            wsd_all = (max(0, int(mods.get(mod.WSD_ALL_HITS, 0)))
                       + max(0, int(mods.get(mod.WEAPONSKILL_DAMAGE_BASE
                                             + int(ws["id"]), 0))))
            if self.has_effect(effects.RESTRAINT):
                wsd_all += min(30, int(getattr(self, "_restraint_bonus", 0)))
            wsd_first = max(0, int(mods.get(mod.WSD_FIRST_HIT, 0)))
            # "fTP +x" gear is stored in 1/256 units.  It raises the fTP the skill scales
            # from, not the TP the player spends.
            ftp_bonus = max(0, int(mods.get(mod.ANY_FTP_BONUS, 0))) / 256.0
            # Only a skill whose description says its critical-hit rate varies with TP
            # can crit.  A normal weapon skill takes no base/dDEX/gear critical roll;
            # that is the difference between a retail Rudra's and an auto-attack.
            crit_capable = bool(ws_data is not None and ws_data.crit_varies)
            if ws_data is not None and ws_data.ftp:
                ftp_base = ws_data.ftp_at(effective_tp) + ftp_bonus
                hits = max(1, ws_data.hits)
                multi_hit_ftp = ws_data.multi_hit_ftp
                attack_multiplier = ws_data.attack_at(effective_tp)
                crit_bonus = (self.fencer_crit_bonus(mods)
                              + ws_data.crit_at(effective_tp))
                ignored_defense = ws_data.ignored_defense_at(effective_tp)
            else:
                # No per-skill row (the self skills, Campaign-only skills and Dagda):
                # keep the old generic curve rather than dropping to a weaker default.
                ftp_base = 1.5 + 1.5 * effective_tp / TP_MAX + ftp_bonus
                hits = 1
                multi_hit_ftp = False
                attack_multiplier = 1.0
                crit_bonus = self.fencer_crit_bonus(mods)
                ignored_defense = 0.0
            ws_accuracy = int(mods.get(mod.WS_ACCURACY, 0))
            # Building Flourish is spent by the next weapon skill: 1-3 finishing
            # moves buy Accuracy+40, then Attack+25%, then Critical Hit Rate+10%, and
            # its job-point row adds 1% Weapon Skill Damage per rank to every hit.
            build = self.effect(effects.BUILDING_FLOURISH)
            if build is not None:
                build_moves = max(1, min(3, int(build.get("power") or 1)))
                build_merit = self._dnc_merit(dancer.MERIT_BUILDING_FLOURISH)
                # The Flourish II category's Building clause is 1% per rank (20 at 20/20),
                # not the category's first number (Reverse Flourish's +2 TP).
                if int(self.char.get("main_job", 0)) == dancer.DANCER_JOB:
                    wsd_all += JOB_POINT_RANK
                ws_accuracy += 40 + 2 * build_merit
                if build_moves >= 2:
                    attack_multiplier *= 1.25 + 0.01 * build_merit
                if build_moves >= 3:
                    crit_bonus += 0.10 + 0.01 * build_merit
                self.remove_effect(effects.BUILDING_FLOURISH, quiet=True)
                self.queue.append(self.char_status())
            # Flourish III: Climactic guarantees the next WS crits, while Striking
            # and Ternary add one/two guaranteed hits.  All three are one-shot.
            if self.has_effect(effects.CLIMACTIC_FLOURISH):
                crit_bonus = max(float(crit_bonus), 1.0)
                crit_capable = True
                self.remove_effect(effects.CLIMACTIC_FLOURISH, quiet=True)
                self.queue.append(self.char_status())
            if self.has_effect(effects.STRIKING_FLOURISH):
                hits += 1
                self.remove_effect(effects.STRIKING_FLOURISH, quiet=True)
                self.queue.append(self.char_status())
            if self.has_effect(effects.TERNARY_FLOURISH):
                hits += 2
                self.remove_effect(effects.TERNARY_FLOURISH, quiet=True)
                self.queue.append(self.char_status())
            if magic_ws:
                # Retail resolves a magical weapon skill through the magic formula, not
                # through pDIF.  Seraph Blade and Sanguine Blade are magical: their
                # damage is WSC plus the weapon-level base, times fTP, then dSTAT,
                # Magic Damage, MAB/MDB, elemental affinity and the magic resist.
                damage = self._magic_weaponskill(
                    ws_data, sheet, attributes, mods, entity, effective_tp,
                    wsd_all, wsd_first, ftp_bonus, ranged=ranged_ws)
                # A killing blow prints the HP the target had left, not the overkill;
                # the physical round caps the same way before it returns its total.
                damage = min(damage, max(0, int(entity.hp)))
                # Restraint builds only until the next weapon skill, magical or not.
                self._restraint_bonus = 0
                miss = False
                critical = False
                physical_damage = 0
                hybrid_magic = 0
                round_result = None
                defeated = entity.hp <= damage
                log.info("%s weapon skill %s (magical): %d damage%s",
                         self.addr, ws["name"], damage,
                         " (defeated)" if defeated else "")
            else:
                round_result = self._roll_weaponskill_round(
                    entity, sheet=sheet, ftp_base=ftp_base, hits=hits,
                    multi_hit_ftp=multi_hit_ftp,
                    attack_multiplier=attack_multiplier,
                    ignored_defense=ignored_defense, crit_bonus=crit_bonus,
                    crit_capable=crit_capable, ws_accuracy=ws_accuracy,
                    wsc=wsc, wsd_all=wsd_all, wsd_first=wsd_first,
                    ranged=ranged_ws)
                # Restraint builds only until the next weapon skill.
                self._restraint_bonus = 0
                physical_damage = int(round_result["damage"])
                miss = not round_result["landed"]
                critical = bool(round_result["critical"])
                # A hybrid skill's magic half is based on the physical damage that
                # landed.  If the physical hit already killed the target retail does
                # not add it, so the same guard is kept here.
                hybrid_magic = 0
                if not miss and entity.hp > physical_damage:
                    magic_fighter = (sheet.ranged_fighter if ranged_ws
                                     else sheet.fighter) if sheet is not None else None
                    magic_skill = int(getattr(magic_fighter, "skill_value", 0) or 0)
                    hybrid_magic = self._hybrid_weaponskill_magic(
                        ws_data, physical_damage, effective_tp, attributes,
                        mods, entity, wsd_all, magic_skill, ftp_bonus)
                damage = min(combat.DAMAGE_CAP, physical_damage + hybrid_magic)
                defeated = bool(round_result["defeated"]) or (
                    not miss and entity.hp <= damage)
                log.info("%s weapon skill %s: %d hits, %d landed, %d physical + %d "
                         "hybrid magic = %d damage%s",
                         self.addr, ws["name"], int(round_result["swings"]),
                         int(round_result["landed"]), physical_damage,
                         hybrid_magic, damage,
                         " (defeated)" if defeated else "")
        drained_mp = 0
        if no_damage and extra is not None and extra.mp_formula:
            drained_mp, _restored_hp = self._weaponskill_drain(
                ws, extra, 0, effective_tp, announce=False)
        if no_damage:
            message = (packets.MESSAGE_SKILL_DRAIN_MP if drained_mp
                       else packets.MESSAGE_MAGIC_NO_EFFECT)
        else:
            # One result carries the whole skill.  A multi-hit weapon skill is a single
            # number in retail's log and one animation: the client draws every hit from
            # the animation itself, not from one result per hit.
            message = (packets.MESSAGE_DAMAGE if not miss
                       else packets.MESSAGE_SKILL_MISSES)
        self._last_target_hp = entity.hp_max
        if no_damage:
            finish = sub(0x028, packets.battle_action(
                me, int(entity.id), drained_mp, miss=False, critical=False,
                defeated=False, animation=animation, kind=3, message=message,
                category=packets.ACTION_CATEGORY_SKILL_FINISH, action_id=int(ws["id"])))
            finish.not_before = now + WEAPONSKILL_FINISH_DELAY
            finish.after_packet = int(self.server_id)
            self.queue.append(finish)
            self.queue.append(self.party_member())
            self.say("%s drains %d MP from %s." % (ws["name"], drained_mp, entity.name)
                     if drained_mp else "%s has no effect." % ws["name"])
            self.world.add_mob_hate(entity, me, HATE_ENFEEBLE, now)
            self.next_attack_at = now + 2.0
            return
        # Apply the weapon skill's damage first: a skillchain's base is the damage that
        # actually landed, and the opening state only starts on a live target.  The
        # chain's own damage and additional-effect block then ride this same result.
        chain = None
        if not miss:
            # Damage breaks Sleep/Stun before the skill's own effect lands, so a
            # Shockwave can put the target to sleep with the hit that woke it.
            self.world.wake_mob(entity)
            entity.hp = max(0, entity.hp - damage)
            if not defeated:
                if self.has_effect(effects.KONZEN_ITTAI):
                    self._seed_konzen_chain(entity, ws, now)
                    self.remove_effect(effects.KONZEN_ITTAI, quiet=True)
                chain = self._advance_skillchain(entity, ws, damage, now)
                if chain is not None and chain["defeated"]:
                    defeated = True
        result = dict(damage=damage, miss=miss, critical=critical,
                      defeated=defeated, animation=animation, message=message)
        if chain is not None and int(chain["damage"]) > 0:
            # The client plays a skillchain from the closing weapon skill's
            # additional-effect block, not from a separate action.  The proc kind picks
            # the animation, and 287 + proc is the "Skillchain!" line.
            result.update(add_effect=int(chain["proc"]),
                          add_value=int(chain["damage"]),
                          add_message=int(chain["message"]))
        self.queue_action(int(entity.id), results=[result], kind=3,
                          category=packets.ACTION_CATEGORY_SKILL_FINISH,
                          action_id=int(ws["id"]), broadcast=True,
                          not_before=now + WEAPONSKILL_FINISH_DELAY)
        # The client prints its own "uses <skill>. <target> takes N points of damage."
        # line from the result, so there is no second chat line here: the old self.say
        # was the duplicate (and, on a multi-hit skill, the only line that was a total).
        # A weapon skill is a direct action too: it claims an idle monster and adds to
        # the hate list even on a miss.
        self.world.add_damage_hate(entity, me, damage, now)
        if not miss:
            for observer in self.world.sessions_in_zone(entity.zone):
                if int(entity.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue_entity(entity, packets.SEND_HP)
            if damage > 0 and extra is not None:
                # Drain skills first (Spirit Taker/Mystic Boon/Entropy/Catastrophe/
                # Sanguine Blade), then the debuffs land.
                self._weaponskill_drain(ws, extra, damage, effective_tp)
                if extra.statuses and not defeated:
                    self._apply_weaponskill_statuses(
                        ws, extra, entity, effective_tp, mods, now)
        if defeated:
            self.world.kill_mob(self, entity, now=now)
        # Weapon-skill hits pay TP back: first main hand delay, the one-hit off hand's
        # delay, and 10 TP for every other landed hit, all after Store TP.  Save TP and
        # Conserve TP are applied there too.  This includes a miss (Save TP still
        # applies) and a killing WS (the hits landed before the target fell).
        if sheet is not None and not no_damage:
            tp_round = round_result
            if magic_ws:
                # A magical WS has one "hit" for TP return: the main-hand delay.
                tp_round = {"first_main_landed": True, "offhand_tp_hit": False,
                            "extra_landed": 0}
            self._weaponskill_tp_return(sheet, tp_round, mods, now,
                                        ranged=ranged_ws)
        self.next_attack_at = now + 2.0

    def has_diamond_aspis(self) -> bool:
        """Whether this character is wearing the Diamond Aspis, the SC window exception."""
        return int(self.equipped.get(1, (0, 0, 0))[2] or 0) == \
            skillchain.DIAMOND_ASPIS_ITEM_ID

    def self_ability_duration(self, seconds: float) -> float:
        """Diamond Aspis extends standard abilities used on self by +25%."""
        if self.has_diamond_aspis():
            return float(seconds) * 1.25
        return float(seconds)

    def killer_instinct_duration(self, rank: int) -> tuple[float, float]:
        """(self, party) seconds for Killer Instinct at one merit rank.

        Retail: 180 s plus 10 s for every rank past the first, plus the
        Ankusa/Mst. Helm augment's 4 s per merit rank, and the Diamond Aspis adds
        25% to the caster only.  This server deliberately gives the party the same
        full duration as the caster (custom BST Killer Instinct change), so both
        entries are the same and the party keeps the full +15%/-15% effect too.
        """
        rank = max(1, min(5, int(rank)))
        base = 180.0 + 10.0 * (rank - 1)
        head = int(self.equipped.get(4, (0, 0, 0))[2] or 0)
        if head in KILLER_INSTINCT_HEAD_ITEMS:
            base += 4.0 * rank
        duration = self.self_ability_duration(base)
        return duration, duration

    def _advance_skillchain(self, entity, ws: dict, base_damage: int,
                            now: float) -> dict | None:
        """Feed a landed weapon skill into the monster's skillchain state.

        The first skill with properties opens the window (11 s); a later skill whose
        properties resonate with the opening forms the chain.  The chain damage is
        based on the closing skill's damage and is applied here.  The returned dict is
        the closing result's **additional-effect block** (proc kind, damage and client
        message); the caller puts it on the same 0x028 as the weapon skill so the client
        draws the skillchain animation.  A separate action with message 287+proc shows
        text but has no additional-effect block, which is why no animation played.
        """
        props = self.world.service.weaponskill_properties(int(ws["id"]))
        return self._advance_chain(entity, props, base_damage, now,
                                   label="ws=%d" % int(ws["id"]))

    def _magic_skillchain(self, entity, spell: dict, damage: int, now: float,
                          *, defeated: bool = False) -> dict | None:
        """Immanence: a landed elemental spell acts as a weapon skill for one chain.

        The spell's element picks its single property (Fire is Liquefaction, Ice
        Induration, ...), so a Scholar can open with one Immanence spell and close with
        another.  Immanence is spent by the spell whether or not it forms a chain --
        a spell that kills the target has nothing left to chain into, but the charge
        is still gone.
        """
        if int(damage) <= 0 or not self.has_effect(effects.IMMANENCE):
            return None
        props = skillchain.immanence_props(int(spell.get("element") or 0))
        if not any(props):
            return None
        self.remove_effect(effects.IMMANENCE, quiet=True)
        # Take the icon off the bar at the same moment the charge is gone; without this
        # the client kept showing Immanence for the rest of its minute.
        self.queue.append(self.char_status())
        if defeated:
            return None
        return self._advance_chain(
            entity, props, int(damage), now,
            label="immanence %s" % str(spell.get("name") or ""))

    def _advance_chain(self, entity, props, base_damage: int, now: float,
                       *, label: str = "") -> dict | None:
        """Shared chain step for a weapon skill or an Immanence spell."""
        if not any(props):
            return None
        # Diamond Aspis is a closer's shield: it keeps the next window at the full
        # 11 s instead of dropping one second with every link.
        diamond = self.has_diamond_aspis()
        owner = str(self.char.get("name") or self.addr)
        state, formed = skillchain.advance(
            getattr(entity, "skillchain", None), props, now, diamond=diamond,
            opener=owner)
        entity.skillchain = state
        if not formed:
            log.info("%s skillchain open %s props=%s until=%.1f%s opener=%s target=%s",
                     self.addr, label or "?", props, state.until,
                     " (Diamond Aspis)" if diamond else "", owner, entity.name)
            return None
        tier = int(skillchain.TIER[formed])
        mods = self.combat_mods()
        damage = skillchain.skillchain_damage(
            int(base_damage), tier, int(state.count),
            skillchain_bonus=int(mods.get(mod.SKILLCHAIN_BONUS, 0)),
            skillchain_damage=int(mods.get(mod.SKILLCHAIN_DAMAGE, 0)))
        if float(getattr(self, "_sengikori_until", 0.0) or 0.0) > now:
            # Sengikori: +25% chain damage and +25% burst damage for the next skill,
            # applied as its own step on top of the gear bonuses.  The spell/chain
            # formula has already clipped at 99,999, so clip again after the bonus.
            damage = combat.cap_damage(int(damage * 1.25))
            self._sengikori_until = 0.0
            self._sengikori_mb_until = now + 30.0
        if damage <= 0:
            return None
        applied = min(damage, max(0, int(entity.hp)))
        entity.hp = max(0, int(entity.hp) - damage)
        self.world.add_damage_hate(entity, int(self.char["char_id"]), applied, now)
        log.info("%s skillchain %s: base=%d tier=%d link=%d damage=%d applied=%d "
                 "via=%s closer=%s opener=%s target=%s",
                 self.addr, skillchain.SC(int(formed)).name, int(base_damage), tier,
                 int(state.count), damage, applied, label or "?", owner,
                 state.opener or "?", entity.name)
        return {"proc": int(skillchain.proc_kind(formed)),
                "damage": applied,
                "message": int(skillchain.proc_message(formed)),
                "defeated": entity.hp <= 0}

    # --- weapon-skill helpers -----------------------------------------------------------

    def _queue_weaponskill_start(self, ws: dict, target_id: int) -> None:
        """Queue the 0x028 SkillStart action that opens a weapon skill.

        LandSandBoat sends this before the finish: category 7, action id ``SkillUse``,
        one result whose value is the weapon-skill id and whose message is 43.  The
        client uses it to set up the weapon-skill animation, so the finish's sub-kind is
        not read against the spell animation table (236 is both Rudra's Storm's skill
        animation and Frost's spell animation).
        """
        packet = sub(0x028, packets.battle_action(
            int(self.char["char_id"]), int(target_id), kind=0,
            category=packets.ACTION_CATEGORY_SKILL_START,
            action_id=packets.ACTION_SKILL_USE,
            results=[dict(damage=int(ws["id"]), miss=False, critical=False,
                          defeated=False, animation=0, kind=0,
                          message=packets.MESSAGE_READIES_WEAPONSKILL, info=0)]))
        self.queue.append(packet)
        # Observers need the SkillStart too, or their client sees only the finish and
        # can read the animation id against the spell table (Rudra's Storm -> Frost).
        for observer in self.world.sessions_in_zone(self.zone):
            if observer is self:
                continue
            if int(self.char.get("targid", 0)) not in getattr(
                    observer, "sent_targids", set()):
                continue
            observer.queue.append(Msg(packet))

    def _roll_weaponskill_round(self, entity, *, sheet=None, ftp_base: float,
                                hits: int, multi_hit_ftp: bool,
                                attack_multiplier: float, ignored_defense: float,
                                crit_bonus: float, crit_capable: bool,
                                ws_accuracy: int, wsc: int, wsd_all: int,
                                wsd_first: int, ranged: bool = False) -> dict:
        """Roll every swing of one weapon skill and return its summed round.

        Retail resolves a weapon skill as one attack round, not as the skill's listed
        hits alone:

        * the listed hits are the main hand's native hits (four for Ruthless Stroke);
        * Double, Triple and Quadruple Attack roll on each of those hits, up to two
          procs, and their extra swings use the main hand's fTP rule;
        * dual wielding adds one off-hand swing plus its own multi-attack procs,
          even for a one-hit skill;
        * the whole round is capped at eight results and stops once the target's HP is
          spent;
        * only the first main-hand hit gets the hidden +100 accuracy and the
          first-hit-only weapon-skill damage line;
        * only a "critical hit rate varies with TP" skill may crit.  A normal weapon
          skill takes no critical roll at all.

        The returned ``damage`` is capped at 99,999 and at the target's remaining HP, so
        an 18K Rudra's on a 2K monster prints 2K, as retail does, instead of an overkill
        number the client would show as real damage -- and a 120K multi-hit skill prints
        99,999.
        """
        sheet = sheet if sheet is not None else self.stat_sheet()
        hp_start = max(0, int(entity.hp))
        total = 0
        landed = 0
        swings = 0
        critical = False
        first_main_landed = False
        offhand_tp_hit = False
        extra_landed = 0
        native = max(1, int(hits))
        limit = int(combat.MAX_ATTACKS_PER_ROUND)

        def ftp_for(first_main: bool) -> float:
            ftp = ftp_base if (first_main or multi_hit_ftp) else 1.0
            if wsd_all:
                ftp *= 1.0 + wsd_all / 100.0
            if first_main and wsd_first:
                ftp *= 1.0 + wsd_first / 100.0
            return ftp

        def swing(off_hand: bool, first_main: bool, tp_kind: str) -> None:
            nonlocal total, landed, swings, critical
            nonlocal first_main_landed, offhand_tp_hit, extra_landed
            if swings >= limit or total >= hp_start:
                return
            # The hidden first-hit accuracy bonus is LSB's ``bonusAcc + 100``; the
            # off hand and every later hit use only the skill's own WS Accuracy.
            accuracy = int(ws_accuracy) + (100 if first_main else 0)
            hit_miss, hit_damage, hit_critical = self.world.player_attack(
                self, entity, ftp=ftp_for(first_main), off_hand=off_hand,
                accuracy_bonus=accuracy, attack_multiplier=attack_multiplier,
                crit_bonus=crit_bonus if crit_capable else 0.0,
                wsc=wsc, ignored_defense=ignored_defense,
                allow_critical=crit_capable, ranged=ranged)
            swings += 1
            if hit_miss:
                return
            landed += 1
            total += int(hit_damage)
            critical = critical or bool(hit_critical)
            if tp_kind == "main":
                first_main_landed = True
            elif tp_kind == "offhand":
                offhand_tp_hit = True
            else:
                extra_landed += 1

        main_multis = 0
        procs = 0
        for index in range(native):
            if total >= hp_start:
                break
            swing(False, index == 0, "main" if index == 0 else "extra")
            # LandSandBoat rolls another multi-attack after each native hit and stops
            # after two procs; extra hits themselves do not roll again.  Ranged
            # weapon skills are excluded: a gun WS is its listed hit count, not a
            # Double/Triple Attack round from melee gear.
            if not ranged and procs < 2:
                extra = max(0, self._multi_attack_hits(sheet) - 1)
                if extra:
                    main_multis += extra
                    procs += 1
        for _ in range(main_multis):
            swing(False, False, "extra")
        if not ranged and sheet.sub_fighter is not None and total < hp_start:
            # A one-hit WS's off-hand swing is a TP hit from that hand's delay;
            # on a multi-hit WS it is one of the flat 10-TP extra hits.  A ranged
            # weapon skill never gets an off-hand swing from the melee set.
            swing(True, False, "offhand" if native == 1 else "extra")
            for _ in range(max(0, self._multi_attack_hits(sheet) - 1)):
                swing(True, False, "extra")
        # A miss on every hit is still one result (the SkillMisses line), and no overkill
        # number ever reaches the client.  The skill's hits are summed first, so the
        # 99,999 ceiling applies to the one number the client prints, not to each hit:
        # three 40K hits are a 99,999 weapon skill, not a 120,000 one.
        sent = min(total, hp_start, combat.DAMAGE_CAP) if hp_start else 0
        return {"damage": sent, "swings": swings, "landed": landed,
                "critical": critical,
                "first_main_landed": first_main_landed,
                "offhand_tp_hit": offhand_tp_hit,
                "extra_landed": extra_landed,
                # Compare the *clipped* total: with more than 99,999 HP left a 120K
                # roll no longer kills, because only 99,999 was actually applied.
                "defeated": bool(landed and hp_start and sent >= hp_start)}

    def _magic_weaponskill(self, ws_data, sheet, attributes: dict, mods: dict,
                           entity, effective_tp: int, wsd_all: int, wsd_first: int,
                           ftp_bonus: float = 0.0, *, ranged: bool = False) -> int:
        """Retail's magical weapon-skill damage.

        BG-wiki's current magical-WS formula (2026) is::

            base = (152 + floor((WeaponLevel - 99) * 2.45) + WSC) * fTP
            base = floor(base * (1 + Elemental WS Damage)) + dSTAT + Magic Damage
            damage = base * affinity * resist * MAB/MDB * MDT * WSD

        The level term is the **equipped weapon's** item level, not the player's level:
        a level 99 character with an iLvl 119 weapon gets 201, while the old
        ``Level + 2`` reading LSB uses gives 101 and loses about a fifth of the base
        before fTP.  Each multiplier is floored in turn, as retail does.

        This path is for ``magic: true`` rows only (Seraph Blade, Sanguine Blade,
        Seraph Strike, Wildfire, ...).  Hybrid rows keep their physical roll and add
        :meth:`_hybrid_weaponskill_magic`; physical rows (Black Halo) never come here.
        """
        if ws_data is None:
            return 0
        ftp = ws_data.ftp_at(effective_tp) + float(ftp_bonus or 0.0)
        if ftp <= 0:
            return 0
        wsc = ws_data.wsc_for(attributes)
        level = max(1, int(self.char.get("main_level", 99) or 99))
        # A ranged magical WS (Wildfire, Trueflight, ...) scales from the ranged
        # weapon's item level and Magic Accuracy skill, not the main hand's.
        if ranged:
            weapon = getattr(sheet, "ranged_weapon", None)
            fighter = getattr(sheet, "ranged_fighter", None)
        else:
            weapon = getattr(sheet, "weapon", None)
            fighter = getattr(sheet, "fighter", None)
        weapon_level = int(getattr(weapon, "item_level", 0) or 0)
        skill_value = int(getattr(fighter, "skill_value", 0) or 0)

        target = self.world.debuffed_monster(entity)
        # Magic-side debuffs (Magic Defense Down, Magic Evasion Down, Daze) are a
        # separate row set from the physical Defense/Evasion copy above.
        target_mods = self.world.monster_debuff_mods(entity)
        target_attributes: dict[str, int] = {}
        try:
            target_attributes = dict(self.world.monster_sheet(entity).attributes)
            # INT Down is a flat stat subtraction; Sanguine Blade's dSTAT is INT-based.
            int_down = entity.effect_state.get(effects.INT_DOWN)
            if int_down is not None:
                target_attributes["int"] = max(
                    0, int(target_attributes.get("int", 0))
                    - int(int_down.get("power", 0) or 0))
        except Exception as exc:
            log.debug("%s target attributes unavailable: %s", self.addr, exc)
        dstat = ws_data.dstat_for(attributes, target_attributes)
        wsd = max(0, int(wsd_all)) + max(0, int(wsd_first))
        affinity_id = mod.elemental_mod(ws_data.element)
        affinity = int(mods.get(affinity_id, 0)) if affinity_id is not None else 0
        mab = max(-100, int(mods.get(mod.MATT, 0)))
        mdb = max(-100, int(target_mods.get(mod.MDEF, 0)))
        resist = combat.magic_resist(
            skill=skill_value,
            caster_int=int(attributes.get("int", 0)),
            mods=mods, target_level=int(target.level), target_mods=target_mods)
        taken = combat.damage_taken(target_mods, physical=False)
        elemental_ws = max(0, int(mods.get(mod.ELEMENTAL_WS_DAMAGE, 0)))
        magic_damage = max(0, int(mods.get(mod.MAGIC_DAMAGE, 0)))
        damage = combat.magic_weaponskill(
            wsc=wsc, weapon_level=weapon_level, level=level, ftp=ftp,
            dstat=dstat, magic_damage=magic_damage, wsd=wsd,
            elemental_ws=elemental_ws, affinity=affinity, mab=mab, mdb=mdb,
            resist=resist, damage_multiplier=taken)
        log.info("%s magical WS %s: weapon_level=%d wsc=%d ftp=%.3f dstat=%d "
                 "mdmg=%d elemental_ws=%d wsd=%d affinity=%d mab=%d mdb=%d "
                 "resist=%.3f damage=%d",
                 self.addr, ws_data.name, weapon_level, wsc, ftp, dstat,
                 magic_damage, elemental_ws, wsd, affinity, mab, mdb,
                 resist, damage)
        return damage

    def _hybrid_weaponskill_magic(self, ws_data, damage: int, effective_tp: int,
                                  attributes: dict, mods: dict, entity,
                                  wsd_all: int, skill_value: int,
                                  ftp_bonus: float = 0.0) -> int:
        """The magic half of a hybrid weapon skill, after its physical half landed.

        LandSandBoat's ``calculateHybridMagicDamage``: take the physical damage the
        skill just did, multiply it by the same fTP, add flat ``Magic Damage``, apply
        Weapon Skill Damage again, then run it through the caster's Magic Attack Bonus
        against the target's Magic Defense Bonus and Magic Accuracy resist.  Hot Shot,
        Searing Arrow and the elemental blade skills are hybrid skills; without this
        their physical hit was the whole result, which is why a 3,000-TP Hot Shot could
        print only a few thousand damage.
        """
        if ws_data is None or damage <= 0 or not ws_data.hybrid:
            return 0
        target = self.world.debuffed_monster(entity)
        ftp = ws_data.ftp_at(effective_tp)
        if ftp <= 0:
            return 0
        raw = float(damage) * ftp
        raw += max(0, int(mods.get(mod.MAGIC_DAMAGE, 0)))
        if wsd_all:
            raw *= 1.0 + max(0, int(wsd_all)) / 100.0
        if ftp_bonus:
            raw += float(damage) * float(ftp_bonus)
        mab = max(-100, int(mods.get(mod.MATT, 0)))
        mdb = max(-100, int(target.mods.get(mod.MDEF, 0)))
        # Retail floors the target's MDB term at 0.5, the same as the magical path.
        raw = raw * (100 + mab) / max(50, 100 + mdb)
        raw *= combat.magic_resist(
            skill=max(0, int(skill_value)),
            caster_int=int(attributes.get("int", 0)),
            mods=mods, target_level=int(target.level),
            target_mods=target.mods)
        raw *= combat.damage_taken(target.mods, physical=False)
        return combat.cap_damage(max(0, int(raw)))

    def _weaponskill_tp_return(self, sheet, round_result: dict, mods: dict,
                               now: float, *, ranged: bool = False) -> int:
        """Give the weapon skill back the TP its landed hits generate.

        Retail: the first main-hand hit returns that weapon's delay TP, a one-hit
        skill's off-hand swing returns the sub weapon's delay TP, and every other
        landed hit (native later hits, DA/TA/QA procs and off-hand multi-attacks) is a
        flat 10 TP.  Store TP multiplies each hit's return.  Save TP replaces the total
        when it is larger, and Conserve TP adds 10-200 TP on a proc.  Meikyo Shisui
        suppresses the return.  TP is capped by ``gain_tp`` at 3000.
        """
        meikyo = float(getattr(self, "_meikyo_until", 0.0) or 0.0) > now
        hagakure = float(getattr(self, "_hagakure_until", 0.0) or 0.0) > now
        if meikyo:
            self._meikyo_until = 0.0
            self._hagakure_until = 0.0
            return 0
        store_tp = max(0, int(mods.get(mod.STORETP, 0)))
        tp = 0
        if round_result.get("first_main_landed"):
            tp += combat.tp_gain(sheet.tp_per_hit(off_hand=False, ranged=ranged),
                                 store_tp)
        if round_result.get("offhand_tp_hit"):
            tp += combat.tp_gain(sheet.tp_per_hit(off_hand=True), store_tp)
        extra = max(0, int(round_result.get("extra_landed") or 0))
        if extra:
            tp += combat.tp_gain(10, store_tp) * extra
        regular = tp
        # Save TP is compared with the normal return, not added to it; it caps at 500.
        save_tp = min(500, max(0, int(mods.get(mod.SAVETP, 0))))
        if hagakure:
            save_tp = max(save_tp, 400)
        if save_tp:
            tp = max(tp, save_tp)
        # Conserve TP is a straight save, added after the hit return.
        conserve = max(0, min(100, int(mods.get(mod.CONSERVE_TP, 0))))
        conserved = 0
        if conserve and self.world.rng.random() * 100.0 < conserve:
            conserved = self.world.rng.randint(10, 200)
            tp += conserved
        if tp:
            self.gain_tp(tp)
        self._hagakure_until = 0.0
        self._hagakure_tp_bonus = 0
        if tp:
            log.info("%s weapon skill TP return: hits=%d extra=%d store_tp=%d "
                     "regular=%d save_tp=%d conserve=%d total=%d",
                     self.addr, 1 if round_result.get("first_main_landed") else 0,
                     extra, store_tp, regular, save_tp, conserved, tp)
        return tp

    def _prime_aftermath_weapon(self, ws: dict) -> prime_weapons.PrimeWeapon | None:
        """The equipped Prime weapon that grants *ws*, or None.

        The item that carries the 355 modifier is the one that grants the aftermath: a
        Prime dagger in the main hand does not grant it to Rudra's Storm, only to its own
        Ruthless Stroke.  Ranged Prime skills use the ranged slot even though the ranged
        damage path itself is still missing.  Melee checks the main hand first and the
        sub slot second, matching ``equipped_weapon_skills``: when a Prime weapon is
        dual-wielded off-hand, its granted skill is still in the menu.
        """
        if int(ws.get("skill") or 0) in (25, 26):
            slots = (stats.SLOT_RANGED,)
        else:
            slots = (stats.SLOT_MAIN, stats.SLOT_SUB)
        for slot in slots:
            row = self.equipped.get(slot)
            if not row:
                continue
            try:
                item_id = int(row[2])
            except (IndexError, TypeError, ValueError):
                continue
            try:
                weapon = self.world.service.prime_weapon(item_id)
            except Exception as exc:
                log.warning("%s Prime weapon lookup failed: %s", self.addr, exc)
                continue
            if weapon is not None and int(weapon.ws_id) == int(ws["id"]):
                return weapon
        return None

    def _grant_prime_aftermath(self, ws: dict, tp: int) -> None:
        """Grant or refresh the Prime Aftermath for one weapon skill.

        *tp* is the TP the skill actually spent, not ``effective_tp``: TP Bonus and
        Fencer must not change the tier or potency.  A lower tier never replaces a
        higher one, and tiers 2/3 do not refresh themselves; tier 1 does (BG-wiki
        Aftermath, the same rule Mythic/Empyrean aftermath uses).
        """
        weapon = self._prime_aftermath_weapon(ws)
        if weapon is None:
            return
        aftermath = prime_weapons.aftermath_for(weapon, tp)
        if aftermath is None:
            return
        current = self.effect(effects.AFTERMATH)
        if current is not None and float(current.get("until") or 0.0) <= time.time():
            # The tick that clears expired buffs runs every few seconds; a skill inside
            # that window must not be blocked by a tier that has already run out.
            self.remove_effect(effects.AFTERMATH, quiet=True)
            current = None
        if current is not None:
            current_tier = int(current.get("power", 0))
            if not prime_weapons.can_overwrite(current_tier, aftermath.tier):
                return
        self.remove_effect(effects.AFTERMATH, quiet=True)
        self.add_effect(
            effects.AFTERMATH, duration=aftermath.duration, power=aftermath.tier,
            potency=aftermath.potency, icon=aftermath.icon, mods=aftermath.mods)
        # 0x037 is followed by the 0x063 timer packet by the output loop, so one status
        # packet is enough to draw the icon and its countdown.
        self.queue.append(self.char_status())
        log.info("%s prime aftermath ws=%d stage=%d tp=%d tier=%d pdl=%d%% %ds",
                 self.addr, aftermath.ws_id, aftermath.stage, aftermath.tp,
                 aftermath.tier, aftermath.potency, aftermath.duration)

    def _drop_aftermath(self) -> None:
        """Take the Prime Aftermath off when a weapon slot changes; retail does this."""
        if self.remove_effect(effects.AFTERMATH, quiet=True):
            self.queue.append(self.char_status())

    def _weaponskill_effective_tp(self, tp: int, mods: dict | None, now: float) -> int:
        """TP a weapon skill scales from after next-skill abilities.

        Sekkanoki caps at 1000 and disables the TP Bonus abilities, Hagakure adds
        1000, and Warrior's Charge adds 1000.  The abilities are consumed by the
        weapon-skill path after this call.
        """
        effective = self.weaponskill_tp(tp, mods)
        if float(getattr(self, "_sekkanoki_until", 0.0) or 0.0) > now:
            return min(effective, 1000)
        if float(getattr(self, "_hagakure_until", 0.0) or 0.0) > now:
            effective = min(TP_MAX, effective + int(
                getattr(self, "_hagakure_tp_bonus", 1000)))
        elif float(getattr(self, "_warriors_charge_until", 0.0) or 0.0) > now:
            effective = min(TP_MAX, effective + int(
                getattr(self, "_warriors_charge_tp_bonus", 1000)))
        return effective

    def weaponskill_tp(self, tp: int, mods: dict | None = None) -> int:
        """The TP a weapon skill scales from: the spent TP plus TP Bonus and Fencer.

        ``TP_BONUS`` is the generic gear line ("TP Bonus +500"); ``FENCER_TP_BONUS`` is
        the Warrior/Beastmaster/Bard trait, which only applies while single-wielding a
        one-handed weapon.  Neither is TP the player spends.
        """
        mods = self.combat_mods() if mods is None else mods
        bonus = max(0, int(mods.get(mod.TP_BONUS, 0)))
        if self.fencer_active():
            bonus += max(0, int(mods.get(mod.FENCER_TP_BONUS, 0)))
        return min(TP_MAX, int(tp) + bonus)

    def weaponskill_damage_bonus(self, ws: dict, mods: dict | None = None) -> int:
        """Percent damage a weapon skill's gear and traits add, all three lines summed.

        ``ALL_WSDMG_ALL_HITS`` (840) applies to every hit, the per-skill
        ``WEAPONSKILL_DAMAGE_BASE + id`` (LandSandBoat's 570 block: 571 Combo, 580
        Final Heaven, ...) to every hit too, and ``ALL_WSDMG_FIRST_HIT`` (841) only to
        the first.  The damage path splits them; this summed form is for callers that
        only need the total.
        """
        mods = self.combat_mods() if mods is None else mods
        return (max(0, int(mods.get(mod.WSD_ALL_HITS, 0)))
                + max(0, int(mods.get(mod.WSD_FIRST_HIT, 0)))
                + max(0, int(mods.get(mod.WEAPONSKILL_DAMAGE_BASE + int(ws["id"]), 0))))

    def fencer_active(self) -> bool:
        """True while main-handing a one-handed weapon with nothing in the sub slot.

        Fencer is a main-hand-only trait: retail checks that the main weapon is not
        two-handed or hand-to-hand and that the sub slot is empty, a shield, or an item
        with no weapon skill type (a grip).
        """
        try:
            rows = self.world.service.equipped_weapons(int(self.char["id"]))
        except Exception:
            return False
        main = rows.get(stats.SLOT_MAIN) or {}
        if int(main.get("skill") or 0) not in stats.ONE_HANDED_SKILLS:
            return False
        sub = rows.get(stats.SLOT_SUB) or {}
        return int(sub.get("skill") or 0) == 0

    def fencer_crit_bonus(self, mods: dict | None = None) -> float:
        """Fencer's critical-hit rate as a fraction, or 0 when the trait is not active."""
        if not self.fencer_active():
            return 0.0
        mods = self.combat_mods() if mods is None else mods
        return max(0, int(mods.get(mod.FENCER_CRIT_RATE, 0))) / 100.0

    def _self_weaponskill(self, ws: dict, extra, tp: int, animation: int) -> None:
        """Myrkr and Dagan: restore HP/MP and cure ailments, with no target at all."""
        me = int(self.char["char_id"])
        mp_max = max(0, int(self.char.get("mp", 0)))
        hp_max = max(1, int(self.char.get("hp", 1)))
        hp = int(self.char.get("hp_current", hp_max))
        mp = int(self.char.get("mp_current", 0))

        restored_mp = 0
        if extra.mp_percent and any(extra.mp_percent) and mp_max:
            restored_mp = int(mp_max * weapon_skill_effects.at_tp(tp, extra.mp_percent))
            restored_mp = max(0, min(restored_mp, mp_max - mp))
            if restored_mp:
                self.char["mp_current"] = mp + restored_mp
        restored_hp = 0
        if extra.hp_percent and any(extra.hp_percent):
            restored_hp = int(hp_max * weapon_skill_effects.at_tp(tp, extra.hp_percent))
            restored_hp = max(0, min(restored_hp, hp_max - hp))
            if restored_hp:
                self.char["hp_current"] = hp + restored_hp

        # The primary result is the animation carrying the skill's own line.  MP is the
        # one these skills are used for; an HP restore rides a second result at
        # animation 0 so the client does not replay Myrkr/Dagan twice.
        if extra.mp_percent and any(extra.mp_percent):
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, restored_mp, animation=animation, kind=3,
                message=packets.MESSAGE_SKILL_RECOVERS_MP, info=0,
                category=packets.ACTION_CATEGORY_SKILL_FINISH,
                action_id=int(ws["id"]))))
        elif extra.hp_percent and any(extra.hp_percent):
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, restored_hp, animation=animation, kind=3,
                message=packets.MESSAGE_SKILL_RECOVERS_HP, info=0,
                category=packets.ACTION_CATEGORY_SKILL_FINISH,
                action_id=int(ws["id"]))))
        if restored_hp and extra.mp_percent and any(extra.mp_percent):
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, restored_hp, animation=0, kind=3,
                message=packets.MESSAGE_SKILL_RECOVERS_HP, info=0,
                category=packets.ACTION_CATEGORY_SKILL_FINISH,
                action_id=int(ws["id"]))))

        # Cures follow the result, so the combat log reads "uses Myrkr" before the
        # wear-off lines; one 0x037 at the end redraws the bar.
        removed = self._cure_ailments(int(extra.cures)) if extra.cures else []
        if restored_mp:
            self.say("You recover %d MP." % restored_mp)
        if restored_hp:
            self.say("You recover %d HP." % restored_hp)
        if removed:
            self.say("%s removes %d status ailment%s." % (
                ws["name"], len(removed), "" if len(removed) == 1 else "s"))
        if not restored_mp and not restored_hp and not removed:
            self.say("%s has no effect." % ws["name"])

        self.queue.append(self.party_member())
        if removed:
            self.queue.append(self.char_status())
        # A self skill is still a weapon skill: it costs its TP (already spent) and
        # locks the next auto-attack like any other.
        try:
            self.world.service.save_vitals(
                int(self.char["id"]), int(self.char.get("hp_current", 0)),
                int(self.char.get("mp_current", 0)))
        except Exception as exc:
            log.warning("%s weapon skill vitals save failed: %s", self.addr, exc)

    def _weaponskill_drain(self, ws: dict, extra, damage: int, tp: int,
                           announce: bool = True) -> tuple[int, int]:
        """Restore MP/HP from a landed weapon skill; returns what was actually restored.

        ``announce`` is False for Energy Drain/Energy Steal, whose MP amount is the
        primary action result rather than a second line after a damage result.
        """
        restored_mp = 0
        restored_hp = 0
        if extra.mp_from_damage:
            restored_mp = int(damage * float(extra.mp_from_damage))
        if extra.hp_from_damage and any(extra.hp_from_damage):
            restored_hp = int(damage * weapon_skill_effects.at_tp(tp, extra.hp_from_damage))
        if extra.mp_formula:
            try:
                skill_values, _base = self.effective_skills()
            except Exception:
                skill_values = {}
            restored_mp = weapon_skill_effects.drain_amount(
                str(ws["name"]), tp=tp,
                skill=int(skill_values.get(weapon_skill_effects.DAGGER_SKILL, 0)),
                mnd=int(self.stat_sheet().attributes.get("mnd", 0)))
        if restored_mp <= 0 and restored_hp <= 0:
            return 0, 0

        mp_max = max(0, int(self.char.get("mp", 0)))
        mp = int(self.char.get("mp_current", 0))
        if restored_mp:
            restored_mp = max(0, min(restored_mp, mp_max - mp))
            if restored_mp:
                self.char["mp_current"] = mp + restored_mp
        hp_max = max(1, int(self.char.get("hp", 1)))
        hp = int(self.char.get("hp_current", hp_max))
        if restored_hp:
            restored_hp = max(0, min(restored_hp, hp_max - hp))
            if restored_hp:
                self.char["hp_current"] = hp + restored_hp
        if not restored_mp and not restored_hp:
            return 0, 0
        if announce:
            self.queue.append(self.party_member())
            if restored_mp:
                self.say("You recover %d MP." % restored_mp)
            if restored_hp:
                self.say("You recover %d HP." % restored_hp)
        try:
            self.world.service.save_vitals(
                int(self.char["id"]), int(self.char.get("hp_current", 0)),
                int(self.char.get("mp_current", 0)))
        except Exception as exc:
            log.warning("%s weapon skill vitals save failed: %s", self.addr, exc)
        return restored_mp, restored_hp

    def _cure_ailments(self, limit: int) -> list[int]:
        """Remove up to *limit* ailments; the wear-off lines are queued by remove_effect."""
        removed: list[int] = []
        for effect_id in list(self.status_effects):
            if len(removed) >= max(0, int(limit)):
                break
            if (int(effect_id) in weapon_skill_effects.AILMENTS
                    and self.remove_effect(int(effect_id))):
                removed.append(int(effect_id))
        return removed

    def _apply_weaponskill_statuses(self, ws: dict, extra, entity,
                                    tp: int, mods: dict, now: float) -> None:
        """Land a weapon skill's debuffs after a hit that did damage.

        Retail rolls the hit first: no damage, no additional effect.  Duration is scaled
        by the same Magic Accuracy/Magic Evasion term spells use, and the skills with a
        TP-based proc chance roll ``tp / 3000`` of it.
        """
        try:
            skill_values, _base = self.effective_skills()
        except Exception:
            skill_values = {}
        skill = int(skill_values.get(int(ws["skill"]), 0))
        target = self.world.monster_sheet(entity)
        target_mods = self.world.monster_debuff_mods(entity)
        sheet = self.stat_sheet()
        resist = combat.magic_resist(
            skill=skill, caster_int=int(sheet.attributes.get("int", 0)),
            mods=mods, target_level=int(target.fighter.level),
            target_mods=target_mods)
        me = int(self.char["char_id"])
        landed = False
        for status in extra.statuses:
            if status.chance:
                roll = self.world.rng.random()
                if roll > weapon_skill_effects.chance_at_tp(tp, resist):
                    continue
            spec = weapon_skill_effects.applied_status(status, tp=tp)
            if not self.world.apply_mob_effect(
                    entity, spec, self, now, duration_scale=resist,
                    duration=spec.duration, potency=spec.potency):
                continue
            landed = True
            status_packet = sub(0x028, packets.battle_action(
                me, int(entity.id), int(spec.effect), animation=0, kind=3,
                message=packets.MESSAGE_MAGIC_ENFEEB, info=0,
                category=packets.ACTION_CATEGORY_SKILL_FINISH,
                action_id=int(ws["id"])))
            status_packet.not_before = now + WEAPONSKILL_FINISH_DELAY
            status_packet.after_packet = int(self.server_id)
            self.queue.append(status_packet)
        if landed:
            self.world.add_mob_hate(entity, me, HATE_ENFEEBLE, now)

    def _max_finishing_moves(self) -> int:
        return dancer.max_finishing_moves(int(self.char.get("main_job", 0)))

    def _finishing_moves(self) -> int:
        """How many Finishing Moves are held.

        The count lives in the power of Finishing Move 1, the way LandSandBoat does it;
        the icon is 1-5 or the 6+ icon.  The old status-per-count scheme could not hold
        the 7-9 a fully job-pointed Dancer can store.
        """
        state = self.effect(effects.FINISHING_MOVE)
        if state is not None:
            return max(0, int(state.get("power") or 0))
        # A session that put up a legacy tier status before this model existed.
        return sum(1 for status in effects.FINISHING_MOVES
                   if self.effect(status) is not None)

    def _set_finishing_moves(self, count: int) -> None:
        for status in effects.FINISHING_MOVES:
            self.remove_effect(status, quiet=True)
        count = max(0, min(self._max_finishing_moves(), int(count)))
        if count:
            self.add_effect(
                effects.FINISHING_MOVE, duration=7200.0, power=count,
                icon=dancer.finishing_move_icon(count))
        self.queue.append(self.char_status())

    def _award_finishing_moves(self, count: int) -> int:
        current = self._finishing_moves()
        if count:
            self._set_finishing_moves(current + max(0, int(count)))
        return self._finishing_moves()

    def _spend_finishing_moves(self, count: int) -> int:
        if self.has_effect(effects.GRAND_PAS):
            return 0
        current = self._finishing_moves()
        spent = max(0, min(current, int(count)))
        if spent:
            self._set_finishing_moves(current - spent)
        return spent

    # --- Dancer ------------------------------------------------------------------------

    def _dnc_jp(self, category: str) -> int:
        """A Dancer job-point row's total at rank 20, only while Dancer is the main job."""
        if int(self.char.get("main_job", 0)) != dancer.DANCER_JOB:
            return 0
        return job_points.category_total(dancer.DANCER_JOB, category)

    def _dnc_merit(self, merit_id: int) -> int:
        """A Dancer group-1/group-2 merit's rank, only while Dancer is the main job."""
        if int(self.char.get("main_job", 0)) != dancer.DANCER_JOB:
            return 0
        return int(self.merit_counts().get(int(merit_id), 0))

    def _sch_merit(self, merit_id: int) -> int:
        """A Scholar group-1/group-2 merit's rank, only while Scholar is the main job."""
        if int(self.char.get("main_job", 0)) != effects.SCHOLAR:
            return 0
        return max(0, int(self.merit_counts().get(int(merit_id), 0)))

    def _merit_ability_allowed(self, ability_id: int) -> bool:
        """Whether a merit-locked job ability has at least one rank bought."""
        merit_id = merits.SCH_GROUP2_ABILITIES.get(int(ability_id))
        if merit_id is None:
            return True
        return self._sch_merit(merit_id) > 0

    def _job_ability_ids(self) -> list[int]:
        """The job abilities this character may list, merit locks applied."""
        try:
            ids = self.world.service.job_ability_ids(
                int(self.char.get("main_job", 0)), int(self.char.get("main_level", 1)),
                int(self.char.get("sub_job", 0)), int(self.char.get("sub_level", 0)))
        except Exception as exc:
            log.warning("%s job ability list unavailable: %s", self.addr, exc)
            return []
        return [int(ability_id) for ability_id in ids
                if self._merit_ability_allowed(int(ability_id))]

    @staticmethod
    def _sch_magic_color(spell: dict) -> str:
        """White or black magic for Altruism/Focalization and their enmity pair.

        Divine, Healing and Enhancing are white (the Blaze/Ice/Shock Spikes are black
        Enhancing spells); Elemental and Dark are black.  Enfeebling is black except
        Dia/Diaga, the white enfeebles.  Songs, Ninjutsu, Blue and Summoning are neither.
        """
        name = " ".join(str(spell.get("name") or "").casefold().split())
        skill = int(spell.get("skill") or 0)
        if skill in (packets.SKILL_DIVINE, packets.SKILL_HEALING,
                     packets.SKILL_ENHANCING):
            if skill == packets.SKILL_ENHANCING and name in effects.BLACK_ENHANCING:
                return "black"
            return "white"
        if skill == packets.SKILL_ENFEEBLING:
            return "white" if name.startswith(("dia", "diaga")) else "black"
        if skill in (packets.SKILL_ELEMENTAL, packets.SKILL_DARK):
            return "black"
        return ""

    def _sch_next_spell_bonuses(self, spell: dict) -> dict:
        """Consume the next-spell Scholar merits and return what they add to this cast.

        Altruism/Focalization add 5 magic accuracy plus 5 a rank (the ability's own 5
        and +5 for each merit; BG-wiki's note puts 1/5 at +10).  Tranquility/Equanimity
        take 10 enmity a rank off the spell.  Enlightenment gives +5 INT/MND a rank to
        the first spell and is spent by it, whatever its colour.
        """
        color = self._sch_magic_color(spell)
        macc = enmity = int_bonus = mnd_bonus = 0
        consumed: list[int] = []
        if color == "white":
            if self.has_effect(effects.ALTRUISM):
                macc += 5 + 5 * self._sch_merit(merits.SCH_ALTRUISM)
                consumed.append(effects.ALTRUISM)
            if self.has_effect(effects.TRANQUILITY):
                enmity += 10 * self._sch_merit(merits.SCH_TRANQUILITY)
                consumed.append(effects.TRANQUILITY)
        elif color == "black":
            if self.has_effect(effects.FOCALIZATION):
                macc += 5 + 5 * self._sch_merit(merits.SCH_FOCALIZATION)
                consumed.append(effects.FOCALIZATION)
            if self.has_effect(effects.EQUANIMITY):
                enmity += 10 * self._sch_merit(merits.SCH_EQUANIMITY)
                consumed.append(effects.EQUANIMITY)
        if self.has_effect(effects.ENLIGHTENMENT):
            rank = self._sch_merit(merits.SCH_ENLIGHTENMENT)
            int_bonus += 5 * rank
            mnd_bonus += 5 * rank
            consumed.append(effects.ENLIGHTENMENT)
        if consumed:
            for effect_id in consumed:
                self.remove_effect(int(effect_id), quiet=True)
            self.queue.append(self.char_status())
        return {"macc": macc, "enmity": enmity,
                "int": int_bonus, "mnd": mnd_bonus}

    def _storm_mods(self, name: str) -> dict[int, int]:
        """Stormsurge: the stat a storm spell grants, from the merit rank.

        Retail gives +3 at 1/5 and +1 a rank after that (+7 at 5/5).  Voidstorm gives
        half that to every stat, floored (+1 at 1/5, +3 at 5/5).  The bonus rides the
        buff's own modifiers, so it applies to whoever the Scholar casts the storm on.
        """
        rank = self._sch_merit(merits.SCH_STORMSURGE)
        if rank <= 0:
            return {}
        folded = " ".join(str(name or "").casefold().split())
        value = 2 + rank
        if folded.startswith("voidstorm"):
            return {stat: value // 2 for stat in
                    (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR)}
        families = (("sandstorm", mod.VIT), ("rainstorm", mod.MND),
                    ("windstorm", mod.AGI), ("firestorm", mod.STR),
                    ("hailstorm", mod.INT), ("thunderstorm", mod.DEX),
                    ("aurorastorm", mod.CHR))
        for prefix, stat in families:
            if folded.startswith(prefix):
                return {stat: value}
        return {}

    def _sch_relieve_hate(self, entity, cast: dict | None) -> None:
        """Take Tranquility/Equanimity's enmity off the monster after the spell lands."""
        amount = int((cast or {}).get("sch_enmity") or 0)
        if entity is None or amount <= 0:
            return
        self.world.relieve_mob_hate(entity, int(self.char["char_id"]), amount)

    def _waltz_tp_reduction(self) -> int:
        """TP taken off a waltz by "Waltz TP Cost" gear.

        LandSandBoat stores the modifier in 5-TP units and its Dancer script subtracts
        ``mod * 10``: Desultor Tassets' -50 TP is mod value 5.  The HUD carries the same
        item table for its pre-click check.
        """
        try:
            mods = self.combat_mods()
        except Exception as exc:
            log.warning("%s waltz cost gear unavailable: %s", self.addr, exc)
            return 0
        return max(0, int(mods.get(mod.WALTZ_COST, 0))) * 10

    def _waltz_target(self, act_index: int, ability: dict):
        """The party member the client aimed a waltz at, and an error string if not."""
        name = str(ability.get("name") or "that waltz")
        if not act_index or int(act_index) == TARGID:
            return self, None
        target = None
        for other in self.world.sessions_in_zone(self.zone):
            if int(getattr(other, "targid", 0) or 0) == int(act_index):
                target = other
                break
        if target is None:
            return None, "There is no valid target for %s." % name
        if target is self:
            return self, None
        if (getattr(target, "dead_until", 0.0) > time.time()
                or int(target.char.get("hp_current", 0)) <= 0):
            return None, "That party member is not available."
        reach = float(ability.get("range") or 20.0)
        if math.dist(self.pos[:3], target.pos[:3]) > reach + 1.0:
            return None, "You are too far away."
        return target, None

    def _dnc_precheck(self, ability_id: int, target) -> str | None:
        """Refuse a dance before its use animation when the resources are missing."""
        if dancer.is_waltz(ability_id):
            if self.has_effect(effects.SABER_DANCE):
                return "You cannot use %s while Saber Dance is active."
            spec = dancer.waltz(ability_id)
            if not self.has_effect(effects.TRANCE):
                cost = dancer.waltz_tp_cost(
                    spec, gear_reduction=self._waltz_tp_reduction(),
                    contradance=self.has_effect(effects.CONTRADANCE),
                    contradance_jp=self._dnc_jp("Contradance Effect"))
                if int(self.char.get("tp", 0)) < cost:
                    return "You do not have enough TP for %s."
            return None
        if dancer.is_step(ability_id):
            # Steps are recast-only in this server's design; no TP or engagement gate.
            return None
        if dancer.is_flourish(ability_id):
            if self.has_effect(effects.GRAND_PAS):
                return None
            spec = dancer.flourish(ability_id)
            moves = self._finishing_moves()
            if moves < spec.min_moves:
                if moves <= 0:
                    return "You have no finishing moves."
                return "You do not have enough finishing moves for %s."
            return None
        if dancer.is_samba(ability_id):
            if self.has_effect(effects.FAN_DANCE):
                return "You cannot use %s while Fan Dance is active."
            spec = dancer.samba(ability_id)
            if (not self.has_effect(effects.TRANCE)
                    and int(self.char.get("tp", 0)) < spec.tp_cost):
                return "You do not have enough TP for %s."
            return None
        if ability_id == dancer.NO_FOOT_RISE:
            if self._finishing_moves() >= self._max_finishing_moves():
                return "You already have the maximum number of finishing moves."
        return None

    def _dnc_ability(self, ability_id: int, name: str, ability: dict, target,
                     ally, now: float) -> bool:
        """Run one Dancer ability.  Returns True when the ability was consumed."""
        if dancer.is_waltz(ability_id):
            self._use_waltz(ability_id, ability, ally, now)
            return True
        if dancer.is_step(ability_id):
            self._use_step(ability_id, name, ability, target, now)
            return True
        if dancer.is_flourish(ability_id):
            self._use_flourish(ability_id, name, ability, target, now)
            return True
        if dancer.is_samba(ability_id):
            self._use_samba(ability_id, name, now)
            return True
        if dancer.is_jig(ability_id):
            self._use_jig(ability_id, name, now)
            return True
        if ability_id == dancer.PRESTO:
            self.remove_effect(effects.PRESTO, quiet=True)
            self.add_effect(effects.PRESTO, duration=30.0)
            self.queue.append(self.char_status())
            self.say("Your next step will be enhanced.")
            return True
        if ability_id == dancer.NO_FOOT_RISE:
            # One Finishing Move per merit rank.  The ability is listed at level 75
            # rather than behind a merit purchase in this server's data, so a character
            # with no merits still gets one instead of a dead menu entry.
            rank = max(1, self._dnc_merit(dancer.MERIT_NO_FOOT_RISE))
            self._award_finishing_moves(rank)
            self.say("No Foot Rise: %d finishing move%s." % (
                rank, "" if rank == 1 else "s"))
            return True
        if ability_id == dancer.GRAND_PAS:
            self._grand_pas_uses = 3
            for recast_id in (221, 222, 226):
                self.ability_recasts.pop(recast_id, None)
            self.say("Grand Pas: flourishes are free for three uses.")
            return True
        if ability_id == dancer.TRANCE:
            # The Trance Effect job-point row is 100 TP per rank (2,000 at 20/20).
            grant = self._dnc_jp("Trance Effect")
            if grant:
                self.gain_tp(grant)
            return True
        # Saber Dance, Fan Dance, Grand Pas and Contradance are status icons; the
        # generic ABILITY_EFFECTS layer above already put them up.
        return ability_id in (dancer.SABER_DANCE, dancer.FAN_DANCE,
                              dancer.GRAND_PAS, dancer.CONTRADANCE)

    def _use_waltz(self, ability_id: int, ability: dict, ally, now: float) -> None:
        spec = dancer.waltz(ability_id)
        contradance = self.has_effect(effects.CONTRADANCE)
        if not self.has_effect(effects.TRANCE):
            cost = dancer.waltz_tp_cost(
                spec, gear_reduction=self._waltz_tp_reduction(),
                contradance=contradance,
                contradance_jp=self._dnc_jp("Contradance Effect"))
            self.spend_tp(cost)
        me = int(self.char["char_id"])
        if spec.aoe:
            center = ally or self
            targets = [center]
            party = self.world.party_of(me)
            if party is not None:
                for member in party.members:
                    other = self.world.session_by_char(int(member.char_id))
                    if other is None or int(other.zone) != int(self.zone):
                        continue
                    if other is center or other is self:
                        if other not in targets:
                            targets.append(other)
                        continue
                    if math.dist(center.pos[:3], other.pos[:3]) <= spec.radius:
                        targets.append(other)
            elif self is not center:
                targets.append(self)
        else:
            targets = [ally or self]
        for target in targets:
            self._waltz_on(spec, ability, target, now, contradance)
        if contradance:
            # Contradance doubles one waltz and is spent by it.
            self.remove_effect(effects.CONTRADANCE, quiet=True)
            self.queue.append(self.char_status())

    def _waltz_on(self, spec: "dancer.WaltzSpec", ability: dict, target,
                  now: float, contradance: bool) -> None:
        me = int(self.char["char_id"])
        target_id = int(target.char["char_id"])
        if spec.cleanse:
            removed = 0
            for effect_id in list(target.status_effects):
                if int(effect_id) in dancer.WALTZABLE_EFFECTS:
                    target.remove_effect(int(effect_id), quiet=False)
                    removed = int(effect_id)
                    break
            target.queue.append(target.char_status())
            if target is self:
                if removed:
                    self.say("Healing Waltz removes one status effect.")
                else:
                    self.say("There is no status effect to remove.")
            elif removed:
                self.say("Healing Waltz removes a status effect from %s."
                         % target.char.get("name", "the target"))
            return
        try:
            caster_chr = int(self.stat_sheet().attributes.get("chr", 0))
            target_vit = int(target.stat_sheet().attributes.get("vit", 0))
        except Exception as exc:
            log.warning("%s waltz stats unavailable: %s", self.addr, exc)
            caster_chr, target_vit = 0, 0
        amount = dancer.waltz_amount(
            spec, caster_chr, target_vit,
            main_job=int(self.char.get("main_job", 0)),
            jp_bonus=self._dnc_jp("Waltz Potency"), contradance=contradance)
        hp = int(target.char.get("hp_current", 0))
        max_hp = max(1, int(target.char.get("hp", 1) or 1))
        healed = min(int(amount), max(0, max_hp - hp))
        if healed <= 0:
            if target is self:
                self.say("You are already at full health.")
            return
        target.char["hp_current"] = hp + healed
        action = sub(0x028, packets.battle_action(
            me, target_id, healed, animation=int(ability.get("animation") or 0),
            kind=2, message=packets.MESSAGE_SKILL_RECOVERS_HP,
            category=packets.ACTION_CATEGORY_ABILITY_FINISH,
            action_id=int(spec.ability_id)))
        self.queue.append(action)
        if target is not self:
            target.queue.append(action)
        target.queue += [target.char_status(), target.party_member()]
        if target is not self:
            self.queue.append(self.party_member())
        try:
            self.world.service.save_vitals(
                int(target.char["id"]), int(target.char["hp_current"]),
                int(target.char.get("mp_current", 0)))
        except Exception as exc:
            log.warning("%s waltz vitals save failed: %s", self.addr, exc)

    def _dnc_physical_hit(self, target, accuracy_bonus: int = 0) -> bool:
        """Roll a step/flourish hit against the target's (Daze-debuffed) evasion."""
        try:
            sheet = self.stat_sheet()
            enemy = self.world.debuffed_monster(target)
            rate = combat.hit_rate(
                accuracy=int(sheet.fighter.accuracy) + int(accuracy_bonus),
                evasion=int(enemy.evasion),
                attacker_level=int(sheet.fighter.level),
                target_level=int(enemy.level), is_pc=True,
                corrected=combat.level_corrected(int(self.zone)))
        except Exception as exc:
            log.warning("%s dancer hit rate unavailable: %s", self.addr, exc)
            rate = 0.95
        return float(self.world.rng.random()) < max(0.05, min(0.99, float(rate)))

    def _remove_daze(self, target, family: tuple[int, ...]) -> None:
        for status in family:
            target.effect_state.pop(int(status), None)
            try:
                target.status_effects.remove(int(status))
            except ValueError:
                pass

    def _use_step(self, ability_id: int, name: str, ability: dict, target,
                  now: float) -> None:
        spec = dancer.step(ability_id)
        me = int(self.char["char_id"])
        presto = self.has_effect(effects.PRESTO)
        accuracy = 10 + 3 * self._dnc_merit(dancer.MERIT_STEP_ACCURACY)
        if presto:
            accuracy += 50
        if not self._dnc_physical_hit(target, accuracy):
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), 0, animation=int(ability.get("animation") or 0),
                kind=2, message=0, info=dancer.result_info(ability_id, False),
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            self.say("%s misses." % name)
            return
        main_job = int(self.char.get("main_job", 0))
        max_level = dancer.max_daze(main_job)
        level, _status = dancer.active_daze(target.effect_state, spec)
        at_max = level >= max_level
        removed = 0.0
        if level:
            for status in spec.family:
                state = target.effect_state.get(int(status))
                if state is not None:
                    removed = max(removed, max(0.0, float(state.get("until", 0)) - now))
        new_level = max(1, level) if at_max else min(max_level, level + (5 if presto else 1))
        duration = dancer.step_duration(self._dnc_jp("Step Duration"), removed)
        self._remove_daze(target, spec.family)
        status = dancer.daze_status(spec, new_level)
        potency = dancer.daze_value(spec, new_level)
        effect = effects.SpellEffect(status, "debuff", duration,
                                     power=new_level, potency=potency)
        self.world.apply_mob_effect(
            target, effect, self, now, duration=duration, potency=potency)
        moves = dancer.step_finishing_moves(main_job, presto=presto, daze_at_max=at_max)
        self._award_finishing_moves(moves)
        if presto:
            self.remove_effect(effects.PRESTO, quiet=True)
            self.queue.append(self.char_status())
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(target.id), 0, animation=int(ability.get("animation") or 0),
            kind=2, message=0, info=dancer.result_info(ability_id, True),
            category=packets.ACTION_CATEGORY_ABILITY_FINISH,
            action_id=int(ability_id))))
        self.say("%s: Daze %d, %d finishing move%s." % (
            name, new_level, self._finishing_moves(),
            "" if self._finishing_moves() == 1 else "s"))

    def _use_flourish(self, ability_id: int, name: str, ability: dict, target,
                      now: float) -> None:
        spec = dancer.flourish(ability_id)
        me = int(self.char["char_id"])
        if self.has_effect(effects.GRAND_PAS):
            left = max(0, int(getattr(self, "_grand_pas_uses", 3)) - 1)
            self._grand_pas_uses = left
            if left <= 0:
                self.remove_effect(effects.GRAND_PAS, quiet=True)
                self.queue.append(self.char_status())
        moves = self._finishing_moves()
        if ability_id == 204:                       # Animated Flourish
            used = 2 if moves >= 2 else 1
            self._spend_finishing_moves(used)
            ve = (1500 if used >= 2 else 1000) + self._dnc_jp("Flourish I Effect")
            if target is not None and target.alive:
                self.world.add_mob_hate(target, me, now, ve=ve)
            self.say("Animated Flourish: %d volatile enmity." % ve)
            return
        if ability_id == 205:                       # Desperate Flourish
            self._spend_finishing_moves(1)
            if target is None or not target.alive:
                return
            # Flourish I Effect's Desperate clause is +1 physical accuracy per rank.
            flourish_rank = (JOB_POINT_RANK
                             if int(self.char.get("main_job", 0)) == dancer.DANCER_JOB
                             else 0)
            if not self._dnc_physical_hit(target, flourish_rank):
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(target.id), 0, kind=2, message=0,
                    info=dancer.result_info(ability_id, False),
                    category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id))))
                self.say("%s misses." % name)
                return
            weight = effects.SpellEffect(effects.WEIGHT, "debuff", 60.0, potency=26)
            self.world.apply_mob_effect(target, weight, self, now, duration=60.0)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), 0, kind=2, message=0,
                info=dancer.result_info(ability_id, True),
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            self.say("Desperate Flourish weighs the target down.")
            return
        if ability_id == 207:                       # Violent Flourish
            self._spend_finishing_moves(1)
            if target is None or not target.alive:
                return
            miss, damage, critical = self.world.player_attack(
                self, target, accuracy_bonus=100)
            if not miss and damage > 0:
                defeated = int(target.hp) - damage <= 0
                target.hp = max(0, int(target.hp) - damage)
                self.world.add_damage_hate(target, me, damage, now)
                self.world._queue_mob_hp(target)
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(target.id), damage, critical=critical,
                    defeated=defeated, kind=2, message=packets.MESSAGE_DAMAGE,
                    info=dancer.result_info(ability_id, True),
                    category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id))))
                if defeated:
                    self.world.kill_mob(self, target, now)
                elif float(self.world.rng.random()) < 0.25:
                    stun = effects.SpellEffect(effects.STUN, "debuff", 2.0)
                    self.world.apply_mob_effect(target, stun, self, now, duration=2.0)
            else:
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(target.id), 0, miss=True, kind=2,
                    message=packets.MESSAGE_ATTACK_MISSES,
                    info=dancer.result_info(ability_id, False),
                    category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id))))
            return
        if ability_id == 206:                       # Reverse Flourish
            used = min(5, moves, spec.max_moves)
            self._spend_finishing_moves(used)
            merit = self._dnc_merit(dancer.MERIT_REVERSE_FLOURISH)
            tp = dancer.reverse_flourish_tp(
                used, jp_bonus=self._dnc_jp("Flourish II Effect"), merit_rank=merit)
            self.gain_tp(tp)
            self.say("Reverse Flourish: %d TP from %d finishing move%s." % (
                tp, used, "" if used == 1 else "s"))
            return
        if ability_id == 208:                       # Building Flourish
            used = min(3, moves, spec.max_moves)
            self._spend_finishing_moves(used)
            self.remove_effect(effects.BUILDING_FLOURISH, quiet=True)
            self.add_effect(effects.BUILDING_FLOURISH, duration=60.0, power=used)
            self.queue.append(self.char_status())
            self.say("Building Flourish: %d finishing move%s." % (
                used, "" if used == 1 else "s"))
            return
        if ability_id == 209:                       # Wild Flourish
            self._spend_finishing_moves(2)
            if target is None or not target.alive:
                return
            hit = self._dnc_physical_hit(target, 20)
            if hit:
                bound = effects.SpellEffect(effects.CHAINBOUND, "debuff", 10.0)
                self.world.apply_mob_effect(target, bound, self, now, duration=10.0)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), 0, kind=2, message=0,
                info=dancer.result_info(ability_id, hit),
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            self.say("Wild Flourish readies the target for a skillchain."
                     if hit else "Wild Flourish misses.")
            return
        if ability_id in (264, 313, 314):           # Flourishes III
            need = spec.min_moves
            if ability_id == 264:
                used = min(moves, 5)
            else:
                used = need
            self._spend_finishing_moves(used)
            status = {264: effects.CLIMACTIC_FLOURISH,
                      313: effects.STRIKING_FLOURISH,
                      314: effects.TERNARY_FLOURISH}[ability_id]
            self.remove_effect(status, quiet=True)
            self.add_effect(status, duration=60.0, power=used)
            self.queue.append(self.char_status())
            self.say("%s: %d finishing move%s." % (
                name, used, "" if used == 1 else "s"))
            return
        # A future flourish: spend the minimum so it is not free.
        self._spend_finishing_moves(spec.min_moves)

    def _use_samba(self, ability_id: int, name: str, now: float) -> None:
        spec = dancer.samba(ability_id)
        if not self.has_effect(effects.TRANCE):
            self.spend_tp(spec.tp_cost)
        for status in (effects.DRAIN_SAMBA, effects.ASPIR_SAMBA, effects.HASTE_SAMBA):
            if int(status) != int(spec.status):
                self.remove_effect(int(status), quiet=True)
        duration = dancer.samba_duration(spec, self._dnc_jp("Samba Duration"))
        mods: dict[int, int] = {}
        if spec.status == effects.HASTE_SAMBA:
            merit = self._dnc_merit(dancer.MERIT_HASTE_SAMBA)
            mods[mod.HASTE_ABILITY] = spec.haste + 100 * merit
        self.remove_effect(int(spec.status), quiet=True)
        self.add_effect(int(spec.status), duration=duration, power=1, mods=mods)
        self.queue += [self.char_status(), self.char_stats()]
        self.say("%s takes hold." % name)

    def _use_jig(self, ability_id: int, name: str, now: float) -> None:
        jp = self._dnc_jp("Jig Duration")
        if ability_id == dancer.SPECTRAL_JIG:
            if self.has_effect(effects.SNEAK):
                self.say("You are already sneaking.")
                return
            duration = dancer.jig_duration(180.0, jp)
            self.add_effect(effects.SNEAK, duration=duration)
            self.add_effect(effects.INVISIBLE, duration=duration)
        else:
            duration = dancer.jig_duration(dancer.jig_base(ability_id), jp)
            self.remove_effect(effects.WEIGHT, quiet=True)
            self.add_effect(effects.QUICKENING, duration=duration, power=20)
        self.queue.append(self.char_status())
        self.say("You perform %s." % name)

    def _samba_on_hit(self, damage: int) -> None:
        """Drain/Aspir Samba's little heal/drain when a melee swing lands."""
        damage = max(0, int(damage))
        if damage <= 0:
            return
        if self.effect(effects.DRAIN_SAMBA) is not None:
            heal = max(1, damage * 10 // 100)
            hp = int(self.char.get("hp_current", 0))
            healed = min(int(self.char.get("hp", hp)), hp + heal)
            if healed > hp:
                self.char["hp_current"] = healed
                self.queue += [self.char_status(), self.party_member()]
        if self.effect(effects.ASPIR_SAMBA) is not None:
            mp = int(self.char.get("mp_current", 0))
            gain = max(1, damage * 5 // 100)
            restored = min(int(self.char.get("mp", mp)), mp + gain)
            if restored > mp:
                self.char["mp_current"] = restored
                self.queue += [self.char_status(), self.party_member()]

    def _killer_instinct(self, now: float) -> None:
        """Killer Instinct: the full buff on the whole party for the caster's duration.

        This server deliberately departs from retail here: every party member in the
        zone gets the caster's full duration (5:00 with 5/5 merits, the Ankusa/Mst.
        Helm augment and the Diamond Aspis) and the full +15% damage dealt / -15%
        damage taken effect, with no 7.9-yalm range check.  The monster-family check
        is still pending, so the two multipliers apply to every target.  The damage
        bonus is stored in the effect's power (1500 = +15%) and read by
        :meth:`World.player_attack`; the damage-taken side is a normal ``DMG``
        modifier so the stat report and ``damage_taken()`` see it.
        """
        rank = 1
        try:
            rank = max(1, min(5, int(self.merit_counts().get(
                merits.KILLER_INSTINCT, 0))))
        except Exception:
            rank = 1
        # Merit rank 1 is the base three minutes; each rank past the first adds 10 s.
        # The helm augment adds 4 s per rank and the Diamond Aspis adds 25%.  The
        # helper returns the same value for party on purpose (custom BST change).
        self_duration, party_duration = self.killer_instinct_duration(rank)
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                if other.dead_until or int(other.char.get("hp_current", 0)) <= 0:
                    continue
                # No range check: the whole party gets the buff (custom BST change).
                targets.append(other)
        log.info(
            "%s Killer Instinct rank %d on %d target(s): self %.0f s, party %.0f s",
            self.addr, rank, len(targets), self_duration, party_duration)
        for target in targets:
            # Every target gets the full effect and the full duration; the party copy
            # is not a reduced version.
            target.add_effect(
                effects.KILLER_INSTINCT,
                duration=self_duration if target is self else party_duration,
                power=1500, mods={mod.DMG: -1500})
            if target is self:
                target.queue.append(target.char_status())
                continue
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), int(effects.KILLER_INSTINCT),
                animation=0, kind=2, message=packets.MESSAGE_MAGIC_GAIN_EFFECT,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=162))
            target.queue += [action, target.char_status(), target.party_member()]
            self.queue.append(self.party_member())

    def _benediction(self, now: float, ability: dict) -> None:
        """Benediction: full HP, ailment removal and the job-point MP to the party."""
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                if other.dead_until or int(other.char.get("hp_current", 0)) <= 0:
                    continue
                if math.dist(self.pos[:3], other.pos[:3]) > 14.0:
                    continue
                targets.append(other)
        mp_percent = job_points.category_total(3, "Benediction Effect")
        for target in targets:
            before_hp = int(target.char.get("hp_current", 0))
            max_hp = max(1, int(target.char.get("hp", 1)))
            target.char["hp_current"] = max_hp
            healed = max_hp - before_hp
            before_mp = int(target.char.get("mp_current", 0))
            max_mp = max(0, int(target.char.get("mp", 0)))
            mp_bonus = max_mp * max(0, mp_percent) // 100
            target.char["mp_current"] = min(max_mp, before_mp + mp_bonus)
            restored_mp = int(target.char["mp_current"]) - before_mp
            for effect_id in list(weapon_skill_effects.AILMENTS):
                target.remove_effect(int(effect_id), quiet=True)
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), healed,
                animation=int(ability.get("animation") or 0), kind=2,
                message=packets.MESSAGE_SKILL_RECOVERS_HP,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=18))
            target.queue += [action, target.char_status(), target.party_member()]
            if target is not self:
                self.queue.append(action)
                if restored_mp > 0:
                    target.queue.append(sub(0x028, packets.battle_action(
                        me, int(target.char["char_id"]), restored_mp,
                        animation=0, kind=2,
                        message=packets.MESSAGE_SKILL_RECOVERS_MP,
                        category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=18)))
            try:
                self.world.service.save_vitals(
                    int(target.char["id"]), int(target.char["hp_current"]),
                    int(target.char["mp_current"]))
            except Exception:
                pass
        self.queue.append(self.party_member())

    def _martyr_devotion(self, ability_id: int, ally, now: float) -> None:
        """Martyr heals double the HP cost; Devotion grants that much MP."""
        if ally is None:
            self.say("There is no valid target for that ability.")
            return
        hp = int(self.char.get("hp_current", 0))
        if hp <= 1:
            self.say("You do not have enough HP.")
            return
        sacrifice = max(1, hp * 25 // 100)
        sacrifice = min(sacrifice, hp - 1)
        self.char["hp_current"] = hp - sacrifice
        self.queue += [self.char_status(), self.party_member()]
        if int(ability_id) == 153:                       # Martyr
            target_hp = int(ally.char.get("hp_current", 0))
            max_hp = max(1, int(ally.char.get("hp", 1)))
            healed = min(sacrifice * 2, max_hp - target_hp)
            ally.char["hp_current"] = target_hp + max(0, healed)
            action = sub(0x028, packets.battle_action(
                int(self.char["char_id"]), int(ally.char["char_id"]), max(0, healed),
                animation=0, kind=2, message=packets.MESSAGE_SKILL_RECOVERS_HP,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=153))
        else:                                           # Devotion
            target_mp = int(ally.char.get("mp_current", 0))
            max_mp = max(0, int(ally.char.get("mp", 0)))
            restored = min(sacrifice, max_mp - target_mp)
            ally.char["mp_current"] = target_mp + max(0, restored)
            action = sub(0x028, packets.battle_action(
                int(self.char["char_id"]), int(ally.char["char_id"]), max(0, restored),
                animation=0, kind=2, message=packets.MESSAGE_SKILL_RECOVERS_MP,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=int(ability_id)))
        self.queue.append(action)
        if ally is not self:
            ally.queue.append(action)
        ally.queue += [ally.char_status(), ally.party_member()]
        if ally is not self:
            self.queue.append(self.party_member())
        self.say("You sacrifice %d HP." % sacrifice)
        for target in (self, ally):
            try:
                self.world.service.save_vitals(
                    int(target.char["id"]), int(target.char["hp_current"]),
                    int(target.char.get("mp_current", 0)))
            except Exception:
                pass

    def _indi_aura(self, spell: dict, now: float, cast: dict) -> None:
        """Apply one Indi/Geo aura to its party or enemy targets.

        A Geomancer runs two bubbles -- the Indi- aura around themself and the Geo- aura
        around the Luopan -- and casting again in the same bubble replaces the last one,
        so the previous status comes off the party and the monster before the new one
        lands.  Indi-haste and Geo-frailty coexist; two Indi- auras never do.
        """
        name = str(spell.get("name") or "")
        aura = geomancy.values(name, self.geomancy_plus())
        if aura is None:
            return
        status, mods, hostile, potency = aura
        bubble = geomancy.bubble(name)
        if bubble == "geo":
            self._geo_bubble(spell, now, cast, status, mods, hostile, potency)
            return
        me = int(self.char["char_id"])
        duration = 180.0
        if hostile:
            target = self.world.entity_by_id(int(self.zone), int(cast.get("target") or 0))
            if (target is None or not target.alive) and self.engaged_id:
                target = self.world.entity_by_id(int(self.zone), int(self.engaged_id))
            self._clear_geo_aura(bubble, int(status),
                                 int(target.id) if target is not None else 0)
            if target is not None and target.alive:
                # Carry the spell's name: the Target Debuffs window prefers it over the
                # client's status label, and the shared Colure status (558 for every
                # frailty aura, Indi- or Geo-) is named for the Indi- bubble there.
                self.world.apply_mob_effect(
                    target, effects.SpellEffect(status, "debuff", duration, potency=potency),
                    self, now, duration=duration, name=name)
                self.say("%s affects %s." % (name, target.name))
            return
        self._clear_geo_aura(bubble, int(status), 0)
        entrusted = int(cast.get("party_target") or 0)
        if entrusted:
            other = self.world.session_by_char(entrusted)
            if other is not None and int(other.zone) == int(self.zone):
                other.add_effect(status, duration=duration, power=potency, mods=mods)
                other.queue += [other.char_status(), other.party_member()]
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(other.char["char_id"]), int(status), animation=0,
                    kind=2, message=packets.MESSAGE_MAGIC_GAIN_EFFECT,
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
                self.queue.append(self.party_member())
                self.say("%s grants its aura to %s." % (name, other.char.get("name", "the target")))
                return
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                if math.dist(self.pos[:3], other.pos[:3]) > 10.0:
                    continue
                targets.append(other)
        for target in targets:
            target.add_effect(status, duration=duration, power=potency, mods=mods)
            target.queue.append(target.char_status())
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), int(status), animation=0, kind=2,
                message=packets.MESSAGE_MAGIC_GAIN_EFFECT,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"])))
            target.queue.append(action)
            if target is not self:
                self.queue.append(action)
        self.queue.append(self.party_member())

    GEO_RADIUS = 10.0

    def _geo_bubble(self, spell: dict, now: float, cast: dict, status: int,
                    mods: dict, hostile: bool, potency: int = 10) -> None:
        """A Geo- spell puts its Luopan down, and the bubble is the Luopan's.

        Retail's Geo- aura radiates from the Luopan, not from the Geomancer: party
        members inside the radius keep the buff, monsters inside take the hex, and
        stepping out drops it.  The Luopan is a pet, so a recast replaces it and its
        bubble with it.  A Geo- buff is cast on a party member (the anchor), a Geo-
        hex on the monster; the Luopan is put down at that target, not at the GEO's
        feet.  On a multibox the GEO often stands in the support camp, so putting the
        bubble at the caster would cover the wrong camp entirely.
        """
        name = str(spell.get("name") or "")
        position = tuple(float(value) for value in self.pos[:3])
        anchor = None
        party_id = int(cast.get("party_target") or 0)
        if party_id:
            anchor = self.world.session_by_char(party_id)
            if anchor is None or int(anchor.zone) != int(self.zone):
                anchor = None
            else:
                position = tuple(float(value) for value in anchor.pos[:3])
        target = None
        if int(cast.get("target") or 0):
            target = self.world.entity_by_id(int(self.zone), int(cast["target"]))
        if anchor is None and target is not None:
            position = (float(target.x), float(target.y), float(target.z))
        pet = self.world.spawn_pet(self, "luopan", now, position=position)
        if pet is None:
            return
        pet.geo_name = name
        pet.geo_status = int(status)
        pet.geo_mods = dict(mods)
        pet.geo_hostile = bool(hostile)
        pet.geo_potency = int(potency)
        pet.geo_mp_cost = int(spell.get("mp") or 0)
        pet.geo_drain = 24
        pet.geo_mob_id = 0
        pet.geo_mob_ids = set()
        if hostile:
            if target is None or not target.is_mob() or not target.alive:
                target = None
            if target is None and self.engaged_id:
                candidate = self.world.entity_by_id(
                    int(self.zone), int(self.engaged_id))
                if candidate is not None and candidate.is_mob() and candidate.alive:
                    target = candidate
            if target is not None:
                pet.geo_mob_id = int(target.id)
        self._clear_geo_aura("geo", int(status), int(getattr(pet, "geo_mob_id", 0) or 0))
        self._apply_geo_bubble(pet, now)

    def _apply_geo_bubble(self, pet, now: float) -> None:
        """Put the Luopan's aura on whoever is inside its radius, take it off the rest."""
        spec = geomancy.indi_effect(str(getattr(pet, "geo_name", "") or ""))
        if spec is None:
            return
        _status, _base_mods, hostile = spec
        status = int(getattr(pet, "geo_status", 0) or _status)
        mods = dict(getattr(pet, "geo_mods", None) or _base_mods)
        potency = int(getattr(pet, "geo_potency", 10) or 10)
        duration = 180.0
        here = (float(pet.x), float(pet.y), float(pet.z))
        if hostile:
            # A Geo- hex is a bubble, not a single-target debuff: every monster inside
            # the Luopan's radius gets it (retail also requires the GEO to be on the
            # monster's hate list, which the party's tagged fight satisfies here).
            active = set()
            for entity in self.world.entities_for_zone(int(self.zone)):
                if entity.kind != "mob" or not getattr(entity, "alive", False):
                    continue
                if math.dist(here, (float(entity.x), float(entity.y), float(entity.z))) \
                        > self.GEO_RADIUS:
                    continue
                active.add(int(entity.id))
                state = entity.effect_state.get(status)
                if state is None:
                    self.say("%s affects %s." % (pet.geo_name, entity.name))
                if state is None or float(state.get("until") or 0.0) - now < 30.0:
                    self.world.apply_mob_effect(
                        entity,
                        effects.SpellEffect(status, "debuff", duration, potency=potency),
                        self, now, duration=duration, name=str(pet.geo_name))
            previous = set(getattr(pet, "geo_mob_ids", ()) or ())
            for mob_id in previous - active:
                mob = self.world.entity_by_id(int(self.zone), int(mob_id))
                if mob is not None and mob.effect_state.get(status) is not None:
                    self.world._drop_mob_effect(int(self.char["char_id"]), mob, status)
            pet.geo_mob_ids = active
            return
        for target in self._geo_party():
            inside = math.dist(here, tuple(target.pos[:3])) <= self.GEO_RADIUS
            state = target.effect_state.get(status)
            if inside:
                if state is None or float(state.get("until") or 0.0) - now < 60.0:
                    target.add_effect(status, duration=duration, power=potency,
                                      mods=dict(mods))
                    target.queue.append(target.char_status())
            elif state is not None:
                target.remove_effect(status, quiet=True)
                target.queue.append(target.char_status())

    def _geo_bubble_off(self, pet) -> None:
        """The Luopan is gone (expired, replaced, Full Circle): take its aura with it."""
        status = int(getattr(pet, "geo_status", 0) or 0)
        if not status:
            return
        for target in self._geo_party():
            if target.effect_state.get(status) is not None:
                target.remove_effect(status, quiet=True)
                target.queue.append(target.char_status())
        mob_ids = set(getattr(pet, "geo_mob_ids", ()) or ())
        mob_id = int(getattr(pet, "geo_mob_id", 0) or 0)
        if mob_id:
            mob_ids.add(mob_id)
        for mob_id in mob_ids:
            mob = self.world.entity_by_id(int(self.zone), int(mob_id))
            if mob is not None and mob.effect_state.get(status) is not None:
                self.world._drop_mob_effect(int(self.char["char_id"]), mob, status)

    def _clear_geo_aura(self, bubble: str, keep: int, mob_id: int) -> None:
        """Take this bubble's last aura down before the new cast lands.

        A Geomancer runs two bubbles -- Indi- around themself and Geo- around the Luopan
        -- and each replaces only itself: Indi-haste and Geo-frailty are up together, but
        a second Indi- takes the first one off the party.  The party sweep is every member
        in the zone, not just the ones in range: the old aura has to go even if its owner
        has walked out of the bubble.
        """
        me = int(self.char["char_id"])
        previous = self.geo_bubble.get(bubble)
        if previous is not None:
            previous_status, previous_mob = int(previous[0]), int(previous[1])
            keep_status, keep_mob = int(keep), int(mob_id or 0)
            if previous_status != keep_status:
                for target in self._geo_party():
                    if target.effect_state.get(previous_status) is not None:
                        target.remove_effect(previous_status, quiet=True)
                        target.queue.append(target.char_status())
            if previous_mob and not (previous_status == keep_status
                                     and previous_mob == keep_mob):
                mob = self.world.entity_by_id(int(self.zone), previous_mob)
                if mob is not None and mob.effect_state.get(previous_status) is not None:
                    self.world._drop_mob_effect(me, mob, previous_status)
        self.geo_bubble[bubble] = (int(keep), int(mob_id or 0))

    def _geo_party(self) -> list:
        """This Geomancer plus every party member in the zone."""
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                targets.append(other)
        return targets

    def _thf_enmity(self, ability_id: int, ally, now: float) -> None:
        """Accomplice hands hate to an ally; Collaborator pulls some of theirs."""
        if ally is None or ally is self:
            self.say("You need a party member for that.")
            return
        entity = None
        if self.engaged_id:
            entity = self.world.entity_by_id(int(self.zone), int(self.engaged_id))
        if entity is None or not entity.alive or not entity.enmity:
            self.say("You have no enmity to transfer.")
            return
        me = int(self.char["char_id"])
        other = int(ally.char["char_id"])
        hate = entity.enmity
        if int(ability_id) == 84:                       # Accomplice
            amount = int(hate.get(me, 0)) * 25 // 100
            if amount <= 0:
                self.say("You have no enmity to transfer.")
                return
            hate[me] = max(0, int(hate.get(me, 0)) - amount)
            hate[other] = int(hate.get(other, 0)) + amount
        else:                                           # Collaborator
            amount = int(hate.get(other, 0)) * 25 // 100
            if amount <= 0:
                self.say("That party member has no enmity to transfer.")
                return
            hate[other] = max(0, int(hate.get(other, 0)) - amount)
            hate[me] = int(hate.get(me, 0)) + amount
        entity.enmity_ve[me] = 0
        entity.enmity_ve[other] = 0
        self.say("You transfer %d enmity." % amount)

    def _life_cycle(self, now: float) -> None:
        """Life Cycle: feed the Luopan a quarter of the GEO's current HP.

        The server has no geomancy spell that summons a Luopan yet, so the first use
        with no pet spawns one; after that the retail HP transfer runs.
        """
        pet = getattr(self, "pet_entity", None)
        if pet is None or not pet.alive:
            self.world.spawn_pet(self, "luopan", now)
            return
        hp = int(self.char.get("hp_current", 0))
        if hp <= 1:
            self.say("You do not have enough HP.")
            return
        cost = max(1, hp // 4)
        cost = min(cost, hp - 1)
        self.char["hp_current"] = hp - cost
        bonus = 100 + job_points.category_total(21, "Life Cycle Effect")
        restored = min(int(getattr(pet, "hp_max", 1)) - int(pet.hp), cost * bonus // 100)
        pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), int(pet.hp) + max(0, restored))
        self.queue += [self.char_status(), self.party_member()]
        self.world._queue_mob_hp(pet)
        self.say("You give %d HP to %s." % (max(0, restored), pet.name))

    def _mending_halation(self, now: float) -> None:
        """Mending Halation: consume the Luopan to heal the party."""
        pet = getattr(self, "pet_entity", None)
        if pet is None or not pet.alive:
            self.say("You do not have a Luopan.")
            return
        level = max(1, min(99, int(getattr(pet, "level", 1))))
        heal = 7 * level + 1
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                if other.dead_until or int(other.char.get("hp_current", 0)) <= 0:
                    continue
                if math.dist(self.pos[:3], other.pos[:3]) > 10.0:
                    continue
                targets.append(other)
        self.world.despawn_pet(pet, now, "mending halation")
        for target in targets:
            before = int(target.char.get("hp_current", 0))
            target.char["hp_current"] = min(
                int(target.char.get("hp", 1)), before + heal)
            healed = int(target.char["hp_current"]) - before
            target.queue += [target.char_status(), target.party_member()]
            if target is not self:
                self.queue.append(target.party_member())
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), max(0, healed),
                animation=0, kind=2, message=packets.MESSAGE_SKILL_RECOVERS_HP,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=354))
            target.queue.append(action)
            if target is not self:
                self.queue.append(action)
        self.say("The Luopan vanishes and mends the party.")

    def _concentric_pulse(self, target, now: float) -> None:
        """Concentric Pulse: consume the Luopan and deal its HP as damage."""
        pet = getattr(self, "pet_entity", None)
        if pet is None or not pet.alive:
            self.say("You do not have a Luopan.")
            return
        amount = max(1, int(pet.hp))
        self.world.despawn_pet(pet, now, "concentric pulse")
        if target is None or not target.alive:
            return
        amount = min(amount, int(target.hp))
        target.hp = max(0, int(target.hp) - amount)
        self.world.add_damage_hate(target, int(self.char["char_id"]), amount, now)
        self.world._queue_mob_hp(target)
        self.queue.append(sub(0x028, packets.battle_action(
            int(self.char["char_id"]), int(target.id), amount, kind=2,
            message=packets.MESSAGE_DAMAGE,
            category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=353)))
        if target.hp <= 0:
            self.world.kill_mob(self, target, now)

    def _war_party_effect(self, effect_id: int, mods: dict[int, int],
                          duration: float, action_id: int) -> None:
        """Warcry/Blood Rage: the same buff on the Warrior's party in range."""
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is not None:
            for member in party.members:
                if int(member.char_id) == me:
                    continue
                other = self.world.session_by_char(int(member.char_id))
                if other is None or int(other.zone) != int(self.zone):
                    continue
                if other.dead_until or int(other.char.get("hp_current", 0)) <= 0:
                    continue
                if math.dist(self.pos[:3], other.pos[:3]) > 13.9:
                    continue
                targets.append(other)
        for target in targets:
            target.remove_effect(effects.WARCRY, quiet=True)
            target.remove_effect(effects.BLOOD_RAGE, quiet=True)
            target.add_effect(effect_id, duration=duration, mods=mods)
            if target is self:
                target.queue.append(target.char_status())
                continue
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), int(effect_id),
                animation=0, kind=2, message=packets.MESSAGE_MAGIC_GAIN_EFFECT,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=action_id))
            target.queue += [action, target.char_status(), target.party_member()]
            self.queue.append(self.party_member())

    def _tame(self, target, now: float) -> None:
        """Tame: make a mob docile, or set up the next Charm's +10% bonus.

        Retail Tame can miss, only works when the Beastmaster is the sole claimant,
        and either disengages the mob or leaves it "friendlier" for the next Charm.
        The server does not carry the client's charmability flag yet, so every live
        mob is a valid Tame target.
        """
        pet = getattr(self, "pet_entity", None)
        if pet is not None and pet.alive:
            self.say("You already have a pet.")
            return
        if target is None or target.kind != "mob" or not target.alive:
            self.say("There is no valid target for Tame.")
            return
        me = int(self.char["char_id"])
        others = [int(cid) for cid, hate in target.enmity.items()
                  if int(cid) != me and int(hate) > 0]
        if others or (target.engaged_char_id not in (None, me)):
            self.say("You cannot tame that target.")
            return
        # Tame can miss.  The 75% base stands in for LSB's magic-hit-rate roll; the
        # Totemic Helm's Tame success rate (mod 304) is added on top.  Read the head
        # from the live equipped map, not the saved outfit: the phase engine's temporary
        # KI/song swaps mean char_equip can lag by one action.
        head = int(self.equipped.get(4, (0, 0, 0))[2] or 0)
        tame_mod = 0
        if head:
            try:
                tame_mod = int(self.world.service.item_mods(head).get(mod.TAME, 0))
            except Exception:
                tame_mod = 0
        if not tame_mod:
            tame_mod = int(self.combat_mods().get(mod.TAME, 0))
        chance = 0.75 + tame_mod / 100.0
        if self.world.rng.random() >= min(1.0, chance):
            self.say("Tame fails.")
            return
        if target.engaged_char_id or target.enmity:
            target.enmity.clear()
            target.enmity_ve.clear()
            target.enmity_decay_at = 0.0
            target.engaged_char_id = None
            target.claim_char_id = None
            target.aggro_announced = False
            target.next_attack_at = 0.0
            target.roam_target = None
            self.world._mob_clear_nav(target)
            self.world.set_animation(target, 0)
        else:
            self.tamed_mob_id = int(target.id)
        self.say("The %s seems friendlier." % target.name)

    def _gauge(self, target) -> None:
        """Gauge: report the target's HP and roughly how charmable it is."""
        pet = getattr(self, "pet_entity", None)
        if pet is not None and pet.alive:
            self.say("You already have a pet.")
            return
        if target is None or target.kind != "mob" or not target.alive:
            self.say("There is no valid target for Gauge.")
            return
        hp_pct = max(0, min(100, int(target.hp) * 100 // max(1, int(target.hp_max))))
        chance = 0.5 + job_points.category_total(9, "Charm Success Rate") / 100.0
        if chance >= 0.75:
            read = "should be able to be charmed"
        elif chance >= 0.50:
            read = "might be able to be charmed"
        elif chance >= 0.25:
            read = "would be difficult to charm"
        elif chance > 0:
            read = "would be very difficult to charm"
        else:
            read = "cannot be charmed"
        self.say("The %s has %d%% HP and %s." % (target.name, hp_pct, read))

    def _queue_roll_action(self, actor_id: int, fallback_id: int,
                           fallback_animation: int) -> None:
        """Send the 0x028 a roll or Double-Up prepared, with its dice value in info.

        ``rolls`` fills ``self.roll_action`` because the result needs the new roll total
        (or the Double-Up increase); the generic "uses ability" result sent before the
        handler has no value and made the client's dice animation always show 6.
        """
        action = getattr(self, "roll_action", None)
        self.roll_action = None
        if action is None:
            action = {"ability_id": int(fallback_id),
                      "animation": int(fallback_animation), "info": 0, "value": 0,
                      "message": packets.MESSAGE_USES_JOB_ABILITY}
        self.queue.append(sub(0x028, packets.battle_action(
            int(actor_id), int(actor_id), int(action.get("value") or 0),
            animation=int(action.get("animation") or 0),
            message=int(action.get("message") or packets.MESSAGE_USES_JOB_ABILITY),
            kind=2, category=packets.ACTION_CATEGORY_ABILITY_FINISH,
            action_id=int(action.get("ability_id") or fallback_id),
            info=int(action.get("info") or 0))))

    def job_ability(self, p: bytes, act_index: int = 0) -> None:
        """C2S 0x01A action 0x09: a job ability.

        The body carries the ability id after UniqueNo/ActIndex/ActionId, exactly like a
        weapon skill.  The 0x028 reply is cmd_no 6 (Ability Finish), whose result kind is
        2 and whose sub-kind is the ability's animation id; message 100 prints
        "<player> uses <ability>."

        Effects are intentionally small: Provoke claims the mob, Meditate and Chakra move
        TP/HP and Convert swaps HP and MP.  The Dancer kit is delegated to
        ``_dnc_ability``: TP-costed waltzes/sambas, recast-only steps and jigs, party
        waltz targeting, Daze stack levels and the Finishing Move economy.  The Scholar arts,
        addenda, stratagems and Sublimation put their retail status icons on the bar
        (``effects.ABILITY_EFFECTS``), including the cancels that swap one art for the
        other.  Accession and Perpetuance are spent by the spell they enhance (see
        ``resolve_party_spell``); the other stratagems are icons only so far.  Everything
        else plays its animation and reports the use, so none of the menu entries is a
        dead end.  Recasts are tracked by recast id and sent in 0x119.
        """
        if len(p) < 16:
            log.warning("%s short job ability packet (%d bytes)", self.addr, len(p))
            return
        ability_id = struct.unpack_from("<I", p, 12)[0]
        try:
            ability = self.world.service.job_ability(ability_id)
        except Exception as exc:
            log.warning("%s job ability lookup failed: %s", self.addr, exc)
            return
        if ability is None:
            log.warning("%s unknown job ability id %d", self.addr, ability_id)
            self.say("That job ability does not exist.")
            return
        if not self._merit_ability_allowed(ability_id):
            self.say("You have not learned that ability.")
            return
        name = str(ability["name"])
        log.info("%s job ability %s (%d)", self.addr, name, ability_id)
        now = time.time()
        recast_id = int(ability.get("recast_id") or 0)
        # Sublimation's second use releases its stored MP; the release must work even
        # while the ability itself is still on recast.
        if ability_id == 233 and self.effect(effects.SUBLIMATION) is not None:
            state = self.effect(effects.SUBLIMATION)
            stored = max(0, int(state.get("power") or 0))
            self.remove_effect(effects.SUBLIMATION, quiet=True)
            mp = int(self.char.get("mp_current", 0))
            self.char["mp_current"] = min(int(self.char.get("mp", 0)), mp + stored)
            self.queue += [self.char_status(), self.party_member()]
            self.say("Sublimation releases %d MP." % stored)
            return
        # Two-hour abilities carry recast id 0.  Their cooldown is tracked per ability
        # (keyed above the ordinary recast ids) so changing jobs does not put the next
        # job's one-hour on cooldown; 0x119 slot 0 carries the current job's timer.
        recast_key = (recast_id if recast_id
                      else TWO_HOUR_RECAST_BASE + int(ability_id))
        if self.ability_recasts.get(recast_key, 0.0) > now:
            self.say("%s is not ready yet." % name)
            return

        target = None
        if self.engaged_id:
            target = self.world.entity_by_id(self.zone, int(self.engaged_id))
        if target is None and act_index:
            target = self.world.entity_by_targid(self.zone, int(act_index))
        wants_enemy = bool(int(ability.get("valid_targets") or 0) & 0x04)
        if wants_enemy:
            if target is None or target.kind != "mob" or not target.alive:
                self.say("There is no valid target for %s." % name)
                return
            reach = float(ability.get("range") or 0.0) or MELEE_RANGE
            if target.distance_to(*self.pos[:3]) > reach + 1.0:
                self.say("You are too far away.")
                return
        else:
            target = None
        # Waltzes are aimed at a party member, not a monster: their data has no enemy
        # bit, so the ordinary target path above drops the client's act index.  Resolve
        # it here and run the Dancer resource checks before the use animation, so a
        # waltz with no TP or a flourish with no Finishing Moves refuses cleanly.
        ally = None
        if dancer.is_waltz(int(ability_id)):
            ally, error = self._waltz_target(act_index, ability)
            if error:
                self.say(error)
                return
        elif int(ability_id) in (153, 154):             # Martyr / Devotion
            ally, error = self._waltz_target(act_index, ability)
            if error:
                self.say(error)
                return
            if ally is not self:
                group = self.world.party_of(int(self.char["char_id"]))
                if group is None or group.member(int(ally.char["char_id"])) is None:
                    self.say("That is not a party member.")
                    return
        elif int(ability_id) in (84, 236):              # Accomplice / Collaborator
            ally, error = self._waltz_target(act_index, ability)
            if error:
                self.say(error)
                return
            if ally is not self:
                group = self.world.party_of(int(self.char["char_id"]))
                if group is None or group.member(int(ally.char["char_id"])) is None:
                    self.say("That is not a party member.")
                    return
        if dancer.is_dancer_ability(int(ability_id)):
            error = self._dnc_precheck(int(ability_id), target)
            if error:
                self.say(error % name if "%s" in error else error)
                return
        me = int(self.char["char_id"])
        if ally is not None:
            target_id = int(ally.char["char_id"])
        else:
            target_id = int(target.id) if target is not None else me
        self.roll_action = None
        roll_ability = rolls.spec(int(ability_id)) is not None
        double_up = int(ability_id) == rolls.DOUBLE_UP
        if not (roll_ability or double_up):
            # Rolls and Double-Up queue their own result after the value is known.
            self.queue.append(sub(0x028, packets.battle_action(
                me, target_id, 0, animation=int(ability.get("animation") or 0),
                message=packets.MESSAGE_USES_JOB_ABILITY, kind=2,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
        # Samurai TP abilities whose only effect is on the next weapon skill.
        if int(ability_id) == 288:          # Hagakure
            self._hagakure_until = now + 60.0
            self._hagakure_tp_bonus = 1000
            self.say("You gain 400 save TP and 1000 TP Bonus.")
        elif int(ability_id) == 27:         # Meikyo Shisui
            self._meikyo_until = now + 30.0
            self.char["tp"] = TP_MAX
            self.queue.append(self.party_member())
            self.say("Your weapon skills cost 1000 TP.")
        elif int(ability_id) == 230:        # Sekkanoki
            # The next weapon skill costs 1000 TP and rolls at 1000 TP potency.
            self._sekkanoki_until = now + 60.0
        elif int(ability_id) == 149:        # Warrior's Charge
            self._warriors_charge_until = now + 60.0
            self._warriors_charge_tp_bonus = 1000
            self.say("Your next weapon skill gains 1000 TP Bonus.")
            system_handled = True
        elif int(ability_id) == 62:         # Third Eye
            # One anticipation, or three under Seigan (retail: multiple attacks).
            charges = 3 if self.has_effect(effects.SEIGAN) else 1
            self.third_eye = {"charges": charges, "until": now + 30.0}
        elif int(ability_id) == 258:        # Sengikori
            self._sengikori_until = now + 60.0
        elif int(ability_id) == 167:        # Shikikoyo
            self._shikikoyo(act_index, ability, now)
        elif int(ability_id) == 168:        # Blade Bash
            self._blade_bash(target, now)

        # The arts, the stratagems and Sublimation are status icons in retail, and the
        # client draws them from the 0x037 list.  Put the icon up before the ability's
        # own behaviour so the bar and the behaviour never disagree.
        applied = effects.ABILITY_EFFECTS.get(int(ability_id))
        fallback = None
        system_handled = False
        ability_failed = False
        if applied is not None:
            for gone in applied.cancels:
                self.remove_effect(int(gone), quiet=True)
            mods = applied.mods or None
            if int(ability_id) == 244:      # Enlightenment: +5 INT/MND a merit rank
                rank = self._sch_merit(merits.SCH_ENLIGHTENMENT)
                if rank:
                    mods = dict(mods or {})
                    mods[mod.INT] = mods.get(mod.INT, 0) + 5 * rank
                    mods[mod.MND] = mods.get(mod.MND, 0) + 5 * rank
            self.add_effect(applied.effect, duration=applied.duration, mods=mods)
            self.queue.append(self.char_status())
        else:
            fallback = job_points.ability_effect(int(ability_id))
            if fallback is not None:
                self.add_effect(int(fallback["status"]), duration=float(fallback["duration"]))
                self.queue.append(self.char_status())
        if ability_id == 233:
            state = self.effect(effects.SUBLIMATION)
            if state is not None:
                state["power"] = 0
                state["tick"] = 1
                state["next_tick"] = now + 3.0
                self.queue.append(self.char_status())

        # Dancer: steps, waltzes, flourishes, sambas, jigs and Presto/No Foot Rise.
        # The data and formulas live in ``dancer``; the packets and state are here.
        if dancer.is_dancer_ability(int(ability_id)):
            system_handled = self._dnc_ability(
                int(ability_id), name, ability, target, ally, now)

        # Rune Fencer rune state.
        if int(ability_id) == 357:
            self.rune_enchantment = True
            self.runes = list(getattr(self, "runes", []))
            self.say("Rune Enchantment is active.")
            system_handled = True
        elif int(ability_id) in range(358, 366):             # Ignis..Tenebrae
            if not getattr(self, "rune_enchantment", False):
                self.say("You must use Rune Enchantment first.")
            else:
                runes = list(getattr(self, "runes", []))
                if len(runes) >= 3:
                    self.say("You can hold at most three runes.")
                else:
                    runes.append(name)
                    self.runes = runes
                    self.say("You add the %s rune. (%d/3)" % (name, len(runes)))
            system_handled = True
        elif int(ability_id) in (379, 380):                  # Ward / Effusion
            self.rune_ward = int(ability_id) == 379
            self.rune_effusion = int(ability_id) == 380
            self.say("Your runes now favor %s." % ("Ward" if int(ability_id) == 379 else "Effusion"))
            system_handled = True
        elif int(ability_id) == 368:                         # Lunge
            runes = list(getattr(self, "runes", []))
            if not runes:
                self.say("You have no runes to lunge with.")
            elif target is not None and target.alive:
                amount = 100 + 100 * len(runes)
                defeated = int(target.hp) - amount <= 0
                target.hp = max(0, int(target.hp) - amount)
                self.world.add_damage_hate(target, me, amount, now)
                self.world._queue_mob_hp(target)
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                    category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id))))
                if defeated:
                    self.world.kill_mob(self, target, now)
                self.runes = []
                self.say("You lunge with %d runes." % len(runes))
            system_handled = True

        # Puppetmaster burden and Geomancer Concentric Pulse.
        if int(ability_id) in (136, 139, 309):
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                burden = max(0, int(getattr(pet, "burden", 0)))
                if int(ability_id) == 136:
                    pet.burden = 0
                elif int(ability_id) == 139:
                    self.world.despawn_pet(pet, now, "deactivated")
                else:
                    pet.burden = max(0, burden - job_points.category_total(
                        18, "Cooldown Effect"))
                    self.ability_recasts.pop(210, None)
            system_handled = True
        elif int(ability_id) == 353:                         # Concentric Pulse
            self._concentric_pulse(target, now)
            system_handled = True

        # Beastmaster Killer Instinct and Charm/Run Wild.
        if int(ability_id) == 162:
            self._killer_instinct(now)
            system_handled = True
        if int(ability_id) == 52 and target is not None and target.alive:
            chance = 0.5 + job_points.category_total(9, "Charm Success Rate") / 100.0
            # Tame leaves the mob friendlier: retail gives the next Charm +10%.
            if int(self.tamed_mob_id) == int(target.id):
                chance += 0.10
            self.tamed_mob_id = 0
            if self.world.rng.random() < chance:
                pet = self.world.charm_pet(self, target, now)
                if pet is not None:
                    self.say("%s is charmed." % pet.name)
            else:
                self.say("Charm fails.")
            system_handled = True
        elif int(ability_id) == 282:                         # Run Wild
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                pet.run_wild_until = now + 60.0 + job_points.category_total(
                    9, "Run Wild Duration")
                pet.damage_mult = min(300, int(getattr(pet, "damage_mult", 100)) + 30)
                self.say("%s runs wild." % pet.name)
                system_handled = True
        if int(ability_id) == 252:                           # Restraint
            self._restraint_bonus = 0
        if int(ability_id) == 54:                            # Tame
            self._tame(target, now)
            system_handled = True
        elif int(ability_id) == 53:                          # Gauge
            self._gauge(target)
            system_handled = True

        if int(ability_id) in (32, 267):                     # Warcry / Blood Rage
            if int(ability_id) == 32:
                main = int(self.char.get("main_job") or 0)
                sub_job = int(self.char.get("sub_job") or 0)
                level = int(self.char.get("main_level", 1)) if main == 1 else (
                    int(self.char.get("sub_level", 1)) if sub_job == 1 else 99)
                pct = ((level + 19) // 4) * 100 // 256
                self._war_party_effect(
                    effects.WARCRY, {mod.ATT_PERCENT: pct}, 30.0, int(ability_id))
            else:
                self._war_party_effect(
                    effects.BLOOD_RAGE, {mod.CRIT_HIT_RATE: 2000}, 30.0,
                    int(ability_id))
            system_handled = True

        if int(ability_id) in (153, 154):                    # Martyr / Devotion
            self._martyr_devotion(int(ability_id), ally, now)
            system_handled = True
        if int(ability_id) in (84, 236):                     # Accomplice / Collaborator
            self._thf_enmity(int(ability_id), ally, now)
            system_handled = True
        if int(ability_id) == 42:                            # Flee
            if self.has_effect(effects.QUICKENING):
                self.say("You are already fleeing.")
            else:
                self.add_effect(effects.QUICKENING, duration=30.0, power=20)
                self.queue.append(self.char_status())
            system_handled = True
        elif int(ability_id) == 43:                          # Hide
            self.add_effect(effects.INVISIBLE, duration=60.0)
            self.queue.append(self.char_status())
            self.say("You hide in the shadows.")
            system_handled = True
        elif int(ability_id) == 155:                         # Assassin's Charge
            self._assassin_charge = True
            self.say("Your next attack will be a critical hit.")
            system_handled = True
        elif int(ability_id) == 156:                         # Feint
            self._feint_until = now + 60.0
            self.say("Your next attack will weaken the target's evasion.")
            system_handled = True
        elif int(ability_id) == 321 and target is not None and target.alive:
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.EVASION_DOWN, "debuff", 60.0,
                                            potency=20),
                self, now, duration=60.0)
            self.say("You bully the target, lowering its evasion.")
            system_handled = True

        # Thief steals and Corsair recast resets.
        if int(ability_id) == 45 and target is not None and target.alive:  # Mug
            amount = 50 + job_points.category_total(6, "Mug Effect")
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 228:                          # Despoil
            self.say("You despoil the target.")
            system_handled = True
        elif int(ability_id) in (96, 133, 339):               # Wild Card/Random Deal/Cutting Cards
            self.ability_recasts.clear()
            self.queue.append(self.abil_recast())
            self.say("Your ability recasts are reset.")
            system_handled = True

        # Ranger Shadowbind and Corsair Quick Draw.
        if int(ability_id) == 57 and target is not None and target.alive:  # Shadowbind
            duration = 60.0 + job_points.category_total(11, "Shadowbind Duration")
            spec = effects.SpellEffect(effects.BIND, "debuff", duration)
            self.world.apply_mob_effect(target, spec, self, now, duration=duration)
            self.say("Shadowbind lands.")
            system_handled = True
        elif int(ability_id) in (125, 126, 127, 128, 129, 130, 131, 132) and target is not None and target.alive:
            amount = 200 + job_points.category_total(17, "Quick Draw Effect")
            amount += job_points.category_total(17, "Optimal Range")
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True

        if int(ability_id) in (345, 346, 347, 355):        # Full Circle / Lasting / Ecliptic / Radial
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive or getattr(pet, "pet_type", "") != "luopan":
                self.say("You have no Luopan.")
            elif int(ability_id) == 345:                    # Full Circle
                ratio = max(0.0, min(1.0, int(pet.hp) / max(1, int(pet.hp_max))))
                refund = max(0, int(getattr(pet, "geo_mp_cost", 0) or 0) * ratio // 2)
                mp = int(self.char.get("mp_current", 0))
                self.char["mp_current"] = min(int(self.char.get("mp", 0)), mp + refund)
                self.world.despawn_pet(pet, now, "full circle")
                self.queue += [self.char_status(), self.party_member()]
                self.say("Your Luopan vanishes; you recover %d MP." % refund)
            elif int(ability_id) == 346:                    # Lasting Emanation
                pet.geo_drain = max(1, int(getattr(pet, "geo_drain", 24)) - int(
                    getattr(pet, "level", 1)) // 14)
                self.say("Your Luopan consumes HP more slowly.")
            elif int(ability_id) == 347:                    # Ecliptic Attrition
                if getattr(pet, "ecliptic", False):
                    self.say("Ecliptic Attrition is already active.")
                else:
                    pet.geo_potency = int(getattr(pet, "geo_potency", 100)) * 125 // 100
                    pet.geo_drain = int(getattr(pet, "geo_drain", 24)) + int(
                        getattr(pet, "level", 1)) // 16
                    pet.ecliptic = True
                    self.say("Your Luopan's aura is empowered.")
            else:                                           # Radial Arcana
                level = int(getattr(pet, "level", 1))
                restore = 3 * level
                me = int(self.char["char_id"])
                targets = [self]
                group = self.world.party_of(me)
                if group is not None:
                    for member in group.members:
                        other = self.world.session_by_char(int(member.char_id))
                        if other is not None and int(other.zone) == int(self.zone):
                            targets.append(other)
                for target in targets:
                    mp = int(target.char.get("mp_current", 0))
                    target.char["mp_current"] = min(
                        int(target.char.get("mp", 0)), mp + restore)
                    target.queue += [target.char_status(), target.party_member()]
                self.world.despawn_pet(pet, now, "radial arcana")
                self.say("Your Luopan vanishes; the party recovers MP.")
            system_handled = True
        elif int(ability_id) == 41 and target is not None and target.alive:  # Steal
            self._steal(target)
            system_handled = True
        elif int(ability_id) == 285 and target is not None and target.alive:  # Bounty Shot
            self._ranged_shot(target, bonus=50)
            system_handled = True
        elif int(ability_id) == 56:                          # Scavenge
            ammo = (17343, 17340, 17312, 17300)             # Bronze/Bullet/Iron/Platinum
            if self.world.rng.random() < 0.75:
                item_id = ammo[int(self.world.rng.randrange(len(ammo)))]
                self.world.service.add_item(int(self.char["id"]), item_id, 1)
                self.refresh_inventory()
                item = self.world.service.item(item_id)
                self.say("You scavenge %s." % (item["name"] if item else "ammunition"))
            else:
                self.say("You find nothing.")
            system_handled = True
        elif int(ability_id) == 375 and target is not None and target.alive:  # Rayke
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.RAYKE, "debuff", 30.0),
                self, now, duration=30.0)
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.MAGIC_EVASION_DOWN, "debuff", 30.0,
                                            potency=20),
                self, now, duration=30.0)
            self.say("You lower the target's resistance.")
            system_handled = True
        elif int(ability_id) == 150 and target is not None and target.alive:  # Tomahawk
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.TOMAHAWK, "debuff", 60.0),
                self, now, duration=60.0)
            self.say("You mark the target with Tomahawk.")
            system_handled = True
        elif int(ability_id) == 295:                       # Steady Wing
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no wyvern.")
            else:
                power = max(1, int(getattr(pet, "hp_max", 1)) * 30 // 100)
                pet.effect_state[effects.STONESKIN] = {
                    "until": now + 300.0, "power": power, "mods": {}}
                self.world._queue_mob_hp(pet)
                self.say("Your wyvern gains a steady wing shield.")
            system_handled = True
        elif int(ability_id) == 135:                       # Overdrive
            pet = getattr(self, "pet_entity", None)
            if pet is not None and pet.alive:
                pet.overdrive_until = now + 60.0
                self.say("%s enters overdrive." % pet.name)
            else:
                self.say("You have no automaton.")
            system_handled = True
        elif int(ability_id) == 336:                       # Fly High
            self._fly_high_until = now + 30.0
            for recast_id in (158, 159, 160, 166, 167):
                self.ability_recasts.pop(recast_id, None)
            self.say("Your jump recasts are reset.")
            system_handled = True
        elif int(ability_id) == 157:                       # Fealty
            self._fealty = True
            self.say("Your next status effect will be nullified.")
            system_handled = True
        elif int(ability_id) == 393:                       # Spirit Bond
            self._spirit_bond_until = now + 60.0
            self.say("You bond with your wyvern.")
            system_handled = True
        if int(ability_id) == 328 and target is not None and target.alive:  # Larceny
            stolen = None
            for effect_id, state in list(getattr(target, "effect_state", {}).items()):
                if int(effect_id) in weapon_skill_effects.AILMENTS:
                    continue
                stolen = (int(effect_id), state)
                break
            if stolen is None:
                self.say("The target has no effect to steal.")
            else:
                effect_id, state = stolen
                remaining = max(1.0, float(state.get("until", now + 60.0)) - now)
                self.add_effect(effect_id, duration=remaining,
                                power=int(state.get("power") or 0),
                                mods=state.get("mods"))
                try:
                    target.effect_state.pop(effect_id, None)
                except Exception:
                    pass
                self.queue.append(self.char_status())
                self.say("You steal an effect from the target.")
            system_handled = True
        elif int(ability_id) == 161 and target is not None and target.alive:  # Feral Howl
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.STUN, "debuff", 5.0),
                self, now, duration=5.0)
            self.say("Your howl terrifies the target.")
            system_handled = True
        elif int(ability_id) == 388:                       # Cascade
            tp = int(self.char.get("tp", 0))
            bonus = max(0, tp // 10)
            self.char["tp"] = 0
            self._cascade_bonus = bonus
            self.queue.append(self.party_member())
            self.say("Your next spell gains +%d Magic Damage." % bonus)
            system_handled = True
        elif int(ability_id) == 160:                       # Diabolic Eye
            self._diabolic_until = now + 60.0
            self.say("Your dark magic is empowered.")
            system_handled = True
        elif int(ability_id) == 159:                         # Dark Seal
            self._dark_seal = True
            self.say("Your next dark magic spell will be more accurate.")
            system_handled = True
        elif int(ability_id) == 158:                       # Chivalry
            tp = int(self.char.get("tp", 0))
            mnd = int(self.stat_sheet().attributes.get("mnd", 0))
            amount = int(tp * 0.05 + tp * 0.0015 * mnd)
            if amount <= 0:
                self.say("You have no TP to convert.")
            else:
                mp = int(self.char.get("mp_current", 0))
                self.char["mp_current"] = min(int(self.char.get("mp", 0)), mp + amount)
                self.char["tp"] = 0
                self.queue += [self.char_status(), self.party_member()]
                self.say("You convert %d TP into %d MP." % (tp, amount))
            system_handled = True
        elif int(ability_id) == 169:                       # Deep Breathing
            self._deep_breathing_until = now + 180.0
            self.say("Your wyvern's next breath is empowered.")
            system_handled = True
        elif int(ability_id) == 275:                         # Spontaneity
            self._spontaneity = True
            self.say("Your next spell will be instant.")
            system_handled = True
        elif int(ability_id) == 272 and target is not None and target.alive:  # Enmity Douse
            me = int(self.char["char_id"])
            hate = target.enmity
            amount = int(hate.get(me, 0))
            if amount <= 0:
                self.say("You have no enmity to douse.")
            else:
                hate[me] = amount // 2
                target.enmity_ve[me] = 0
                self.say("You douse %d enmity." % (amount - amount // 2))
            system_handled = True

        if int(ability_id) == 392:                         # Crooked Cards
            self.crooked_cards = True
            self.say("Your next roll will be one higher.")
            system_handled = True

        if int(ability_id) == 265 and target is not None and target.alive:  # Libra
            level = int(getattr(target, "level", 0))
            hp = int(getattr(target, "hp", 0))
            hp_max = max(1, int(getattr(target, "hp_max", 1)))
            self.say("Libra: %s is level %d with %d/%d HP (%d%%)." % (
                getattr(target, "name", "the target"), level, hp, hp_max,
                hp * 100 // hp_max))
            system_handled = True

        if int(ability_id) == 389:                            # Consume Mana
            mp = int(self.char.get("mp_current", 0))
            if mp <= 0:
                self.say("You have no MP to consume.")
            else:
                self.char["mp_current"] = 0
                self._consume_mana_bonus = mp
                self.queue += [self.char_status(), self.party_member()]
                self.say("You consume %d MP; your next hit will carry it." % mp)
            system_handled = True

        if int(ability_id) == 39:                            # Boost
            self._boost_until = now + 30.0
            self.say("Your next attack will be stronger.")
            system_handled = True
        elif int(ability_id) == 82 and target is not None and target.alive:  # Chi Blast
            mnd = int(self.stat_sheet().attributes.get("mnd", 0))
            amount = 100 + mnd * 2
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 152:                         # Formless Strikes
            self._formless_until = now + 30.0
            self.say("Your next attack will ignore defense.")
            system_handled = True

        # Puppetmaster automaton commands.
        if int(ability_id) in range(141, 149):               # Fire..Dark Maneuver
            maneuvers = list(getattr(self, "maneuvers", []))
            if len(maneuvers) >= 3:
                self.say("Your automaton can hold at most three maneuvers.")
            else:
                maneuvers.append(name)
                self.maneuvers = maneuvers
                self.say("You grant the %s maneuver. (%d/3)" % (name, len(maneuvers)))
            system_handled = True
        elif int(ability_id) == 138:                         # Deploy
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            elif target is None or not target.alive:
                self.say("There is no target for your automaton.")
            else:
                pet.engaged_id = int(target.id)
                pet.next_attack_at = now + 0.5
                pet.pet_state = "engage"
                self.say("%s deploys." % pet.name)
            system_handled = True
        elif int(ability_id) == 140:                         # Retrieve
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            else:
                pet.engaged_id = 0
                pet.next_attack_at = now + 2.0
                pet.pet_state = "follow"
                self.say("%s returns." % pet.name)
            system_handled = True
        elif int(ability_id) == 310:                         # Deus Ex Automata
            pet = getattr(self, "pet_entity", None)
            if pet is not None and pet.alive:
                self.say("Your automaton is already active.")
            else:
                self.world.spawn_pet(self, "automaton", now)
                self.say("Your automaton rises again.")
            system_handled = True
        elif int(ability_id) == 266:                         # Tactical Switch
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            else:
                own = int(self.char.get("tp", 0))
                pet_tp = int(getattr(pet, "tp", 0))
                self.char["tp"] = pet_tp
                pet.tp = own
                self.queue.append(self.party_member())
                self.say("You switch TP with %s." % pet.name)
            system_handled = True
        elif int(ability_id) == 322:                         # Maintenance
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            else:
                heal = max(1, int(getattr(pet, "hp_max", 1)) // 2)
                pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), int(pet.hp) + heal)
                for effect_id in list(getattr(pet, "status_effects", [])):
                    try:
                        pet.status_effects.remove(effect_id)
                    except ValueError:
                        pass
                self.world._queue_mob_hp(pet)
                self.say("You perform maintenance on %s." % pet.name)
            system_handled = True
        elif int(ability_id) == 180:                         # Ventriloquy
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            elif target is None or not target.alive or not target.enmity:
                self.say("There is no enmity to transfer.")
            else:
                me = int(self.char["char_id"])
                amount = int(target.enmity.get(me, 0)) // 2
                target.enmity[me] = max(0, int(target.enmity.get(me, 0)) - amount)
                target.enmity[int(pet.id)] = int(target.enmity.get(int(pet.id), 0)) + amount
                self.say("You transfer %d enmity to %s." % (amount, pet.name))
            system_handled = True
        elif int(ability_id) == 179:                         # Role Reversal
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no automaton.")
            else:
                own = int(self.char.get("hp_current", 0))
                pet_hp = int(pet.hp)
                self.char["hp_current"] = min(int(self.char.get("hp", 1)), pet_hp)
                pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), own)
                self.queue += [self.char_status(), self.party_member()]
                self.world._queue_mob_hp(pet)
                self.say("You reverse roles with %s." % pet.name)
            system_handled = True

        # Puppetmaster and Rune Fencer utility.
        elif int(ability_id) == 344 and target is not None and target.alive:  # Swipe
            amount = 100 + job_points.category_total(22, "Swipe Effect")
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 383:                         # Vivacious Pulse
            heal = int(self.char.get("hp", 0)) * (
                20 + job_points.category_total(22, "Vivacious Pulse")) // 100
            self._heal_job_ability(max(1, heal))
            system_handled = True

        # Pet support abilities.
        if int(ability_id) == 349:                           # Life Cycle
            self._life_cycle(now)
            system_handled = True
        elif int(ability_id) == 354:                         # Mending Halation
            self._mending_halation(now)
            system_handled = True
        elif int(ability_id) == 340:                         # Heady Artifice
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                pet.heady_until = now + 60.0
                pet.damage_mult = min(300, int(getattr(pet, "damage_mult", 100)) + 20)
                self.say("%s's head artifice activates." % pet.name)
                system_handled = True
        if int(ability_id) == 80:                            # Spirit Link
            pet = getattr(self, "pet_entity", None)
            if pet is not None and pet.alive:
                pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), int(pet.hp) + 300)
                self.world._queue_mob_hp(pet)
                system_handled = True
        elif int(ability_id) in (78, 137):                   # Reward / Repair
            pet = getattr(self, "pet_entity", None)
            if pet is not None and pet.alive:
                pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), int(pet.hp) + 300)
                self.world._queue_mob_hp(pet)
                system_handled = True
        elif int(ability_id) == 232:                         # Elemental Siphon
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no avatar.")
            else:
                mp = int(self.char.get("mp_current", 0))
                gain = 100 + int(getattr(pet, "level", 1)) * 2
                self.char["mp_current"] = min(int(self.char.get("mp", 0)), mp + gain)
                self.queue += [self.char_status(), self.party_member()]
                self.say("You siphon %d MP from %s." % (gain, pet.name))
            system_handled = True
        elif int(ability_id) == 296:                         # Mana Cede
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no avatar.")
            else:
                cost = max(1, int(pet.hp) // 10)
                pet.hp = max(1, int(pet.hp) - cost)
                self.world._queue_mob_hp(pet)
                mp = int(self.char.get("mp_current", 0))
                gain = min(cost, max(0, int(self.char.get("mp", 0)) - mp))
                self.char["mp_current"] = mp + gain
                self.queue += [self.char_status(), self.party_member()]
                self.say("You cede %d MP through %s." % (gain, pet.name))
            system_handled = True

        # Summoner avatar commands.
        if int(ability_id) in (88, 89):
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no avatar.")
            elif int(ability_id) == 88:                  # Assault
                if target is None or not target.alive:
                    self.say("There is no target for your avatar.")
                else:
                    pet.engaged_id = int(target.id)
                    pet.next_attack_at = now + 0.5
                    pet.pet_state = "engage"
                    self.say("%s assaults the target." % pet.name)
            else:                                       # Retreat
                pet.engaged_id = 0
                pet.next_attack_at = now + 2.0
                pet.pet_state = "follow"
                self.say("%s retreats." % pet.name)
            system_handled = True
        elif int(ability_id) == 385:                     # Apogee
            self._apogee_until = now + 60.0
            self.say("Your next Blood Pact will be empowered.")
            system_handled = True

        # Summoner Blood Pacts act through the active avatar.
        if int(ability_id) in (91, 172):
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no avatar to use a Blood Pact.")
            elif int(ability_id) == 91:
                bp_target = target
                if (bp_target is None or not bp_target.alive) and self.engaged_id:
                    bp_target = self.world.entity_by_id(
                        int(self.zone), int(self.engaged_id))
                if bp_target is not None and bp_target.alive:
                    amount = 300 + job_points.category_total(15, "Blood Pact Damage")
                    if float(getattr(self, "_apogee_until", 0.0)) > now:
                        amount += 300
                        self._apogee_until = 0.0
                    if self.has_effect(effects.ASTRAL_FLOW):
                        amount *= 2
                    defeated = int(bp_target.hp) - amount <= 0
                    bp_target.hp = max(0, int(bp_target.hp) - amount)
                    self.world.add_damage_hate(
                        bp_target, int(self.char["char_id"]), amount, now)
                    self.world._queue_mob_hp(bp_target)
                    self.queue.append(sub(0x028, packets.battle_action(
                        int(pet.id), int(bp_target.id), amount, kind=2,
                        message=packets.MESSAGE_DAMAGE,
                        category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                        action_id=int(ability_id))))
                    if defeated:
                        self.world.kill_mob(self, bp_target, now)
                system_handled = True
            elif int(ability_id) == 172:
                pet.hp = min(int(getattr(pet, "hp_max", pet.hp)), int(pet.hp) + 300)
                self.world._queue_mob_hp(pet)
                system_handled = True

        # Dragoon jumps and Ninja Mijin Gakure.
        if int(ability_id) in (66, 67, 68, 260, 293, 292) and target is not None and target.alive:
            jump_base = {66: 200, 67: 200, 68: 300, 260: 300, 293: 400, 292: 500}
            category = {66: "Jump Effect", 67: "High Jump Effect",
                        68: "Super Jump Effect", 260: "Spirit Jump Effect",
                        293: "Soul Jump Effect", 292: "Dragon Breaker Effect"}
            amount = jump_base[int(ability_id)] + job_points.category_total(
                14, category[int(ability_id)])
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if int(ability_id) == 68:                     # Super Jump sheds hate
                hate = target.enmity
                hate[me] = max(0, int(hate.get(me, 0)) // 2)
                target.enmity_ve[me] = 0
            elif int(ability_id) == 293:                  # Soul Jump restores TP
                self.gain_tp(100)
            elif int(ability_id) == 292:                  # Dragon Breaker
                self.world.apply_mob_effect(
                    target, effects.SpellEffect(effects.ATTACK_DOWN, "debuff", 60.0,
                                                potency=20),
                    self, now, duration=60.0)
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 170 and target is not None and target.alive:  # Angon
            amount = 50 + job_points.category_total(14, "Angon Effect")
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.world.apply_mob_effect(
                target, effects.SpellEffect(effects.DEFENSE_DOWN, "debuff", 60.0,
                                            potency=25),
                self, now, duration=60.0)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 318 and target is not None and target.alive:  # Smiting Breath
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no wyvern.")
            else:
                amount = 300 + job_points.category_total(14, "Smiting Breath Effect")
                if float(getattr(self, "_deep_breathing_until", 0.0)) > now:
                    amount *= 2
                    self._deep_breathing_until = 0.0
                defeated = int(target.hp) - amount <= 0
                target.hp = max(0, int(target.hp) - amount)
                self.world.add_damage_hate(target, me, amount, now)
                self.world._queue_mob_hp(target)
                self.queue.append(sub(0x028, packets.battle_action(
                    int(pet.id), int(target.id), amount, kind=2,
                    message=packets.MESSAGE_DAMAGE,
                    category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id))))
                if defeated:
                    self.world.kill_mob(self, target, now)
            system_handled = True
        elif int(ability_id) == 319:                         # Restoring Breath
            pet = getattr(self, "pet_entity", None)
            if pet is None or not pet.alive:
                self.say("You have no wyvern.")
            else:
                heal = 300 + job_points.category_total(14, "Restoring Breath Effect")
                if float(getattr(self, "_deep_breathing_until", 0.0)) > now:
                    heal *= 2
                    self._deep_breathing_until = 0.0
                self._heal_job_ability(heal)
                me = int(self.char["char_id"])
                group = self.world.party_of(me)
                if group is not None:
                    for member in group.members:
                        if int(member.char_id) == me:
                            continue
                        other = self.world.session_by_char(int(member.char_id))
                        if other is None or int(other.zone) != int(self.zone):
                            continue
                        if math.dist(self.pos[:3], other.pos[:3]) > 10.0:
                            continue
                        before = int(other.char.get("hp_current", 0))
                        other.char["hp_current"] = min(
                            int(other.char.get("hp", 1)), before + heal)
                        other.queue += [other.char_status(), other.party_member()]
                self.say("Your wyvern restores the party's HP.")
            system_handled = True
        elif int(ability_id) == 28 and target is not None and target.alive:  # Mijin Gakure
            amount = 500 + job_points.category_total(13, "Mijin Gakure Effect")
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2, message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            self.char["hp_current"] = 0
            self.dead_until = now + 6.0
            self.despawn_trusts()
            system_handled = True

        # Scholar Caper Emissarius and Modus Veritas.
        if int(ability_id) == 342:                           # Caper Emissarius
            heal = int(self.char.get("hp", 0)) * (
                10 + job_points.category_total(20, "Caper Emissarius Effect")) // 100
            self._heal_job_ability(max(1, heal))
            system_handled = True
        elif int(ability_id) == 214 and target is not None:  # Modus Veritas
            # Retail doubles the Helix DoT and halves its remaining life.  Each Modus
            # Veritas Duration merit takes 5% off that penalty (25% at 5/5), and the
            # job-point row adds 3 a rank to the tick.
            bonus = job_points.category_total(20, "Modus Veritas Effect")
            scale = 0.5 + 0.05 * self._sch_merit(merits.SCH_MODUS_VERITAS_DURATION)
            changed = False
            too_strong = False
            for state in getattr(target, "effect_state", {}).values():
                tick = int(state.get("tick") or 0)
                interval = float(state.get("tick_interval") or 0.0)
                if tick <= 0 or interval != effects.HELIX_TICK_SECONDS:
                    continue
                if tick >= 5000:
                    too_strong = True
                    continue
                state["tick"] = tick * 2 + bonus
                until = float(state.get("until") or 0.0)
                if until > now:
                    state["until"] = now + (until - now) * scale
                changed = True
            if changed:
                self.say("Modus Veritas amplifies the target's damage over time.")
            elif too_strong:
                self.say("The target's damage over time is too strong to amplify.")
            else:
                self.say("The target has no damage over time to amplify.")
            system_handled = True

        # Instant weapon abilities with a direct damage component.
        instant_damage = {46: (7, "Shield Bash Effect", 100),
                          26: (11, "Eagle Eye Shot Effect", 300),
                          77: (8, "Weapon Bash Effect", 80)}
        if int(ability_id) in instant_damage and target is not None and target.alive:
            job, category, base = instant_damage[int(ability_id)]
            amount = max(1, int(base) + job_points.category_total(job, category))
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.world.add_damage_hate(target, me, amount, now)
            self.world._queue_mob_hp(target)
            self.world.wake_mob(target)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(target.id), amount, kind=2,
                message=packets.MESSAGE_DAMAGE,
                category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                action_id=int(ability_id))))
            if defeated:
                self.world.kill_mob(self, target, now)
            if int(ability_id) == 46:                    # Shield Bash
                if self.world.rng.random() < 0.70:
                    self.world.apply_mob_effect(
                        target, effects.SpellEffect(effects.STUN, "debuff", 5.0),
                        self, now, duration=5.0)
            system_handled = True

        # Corsair rolls and their commands.  They own their own refusal lines ("busted",
        # "no active roll", "too late to Double-Up"), so the generic "You use ..." fallback
        # must not add a second message when one of them refuses.
        if roll_ability:
            rolls.apply(self, int(ability_id), self.world.rng, now,
                        animation=int(ability.get("animation") or 0))
            self._queue_roll_action(me, int(ability_id),
                                    int(ability.get("animation") or 0))
            system_handled = True
        elif double_up:                                       # Double-Up
            target_roll = rolls.newest(self)
            roll_id = roll_animation = 0
            if target_roll is not None:
                roll_id = next((aid for aid, spec in rolls.ROLLS.items()
                                if int(spec.status) == int(target_roll.status)), 0)
                try:
                    roll_animation = int(
                        self.world.service.job_ability(roll_id)["animation"] or 0)
                except Exception:
                    roll_animation = 0
            success = rolls.double_up(self, self.world.rng, now,
                                      animation=roll_animation, ability_id=roll_id)
            if success:
                self._queue_roll_action(me, int(ability_id),
                                        int(ability.get("animation") or 0))
            else:
                # The client still sends the ability; answer with the retail check
                # message instead of a fake Double-Up animation and no effect.
                ability_failed = True
                self.queue.append(sub(0x028, packets.battle_action(
                    me, me, 0, message=packets.MESSAGE_NO_ELIGIBLE_ROLL,
                    kind=2, category=packets.ACTION_CATEGORY_ABILITY_FINISH,
                    action_id=int(ability_id), info=0)))
            system_handled = True
        elif ability_id == rolls.SNAKE_EYE:                   # Snake Eye
            self.snake_eye = True
            system_handled = True
            self.say("Your next roll will be an 11.")
        elif ability_id == rolls.FOLD:                        # Fold
            rolls.fold(self)
            system_handled = True

        # Pet calls and commands.  The pet itself follows and fights in World.
        if ability_id in (85, 387):                          # Call Beast / Bestial Loyalty
            self._call_jug(int(ability_id), now)
            system_handled = True
        elif ability_id == 61:                               # Call Wyvern
            self.world.spawn_pet(self, "wyvern", now)
            system_handled = True
        elif ability_id == 136:                              # Activate
            self.world.spawn_pet(self, "automaton", now)
            system_handled = True
        elif ability_id in (71, 90, 87, 139):               # Leave/Release/Dismiss/Deactivate
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                self.world.despawn_pet(pet, now, "released")
                self.say("Your pet leaves." if ability_id == 71 else "%s is released." % pet.name)
            system_handled = True
        elif ability_id in (69, 72, 251):                    # Fight/Sic/Ready
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                pet.pet_state = "fight"
                self.say("%s is ready to fight." % pet.name)
            system_handled = True
        elif ability_id == 70:                               # Heel
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                pet.pet_state = "follow"
                self.say("%s heels." % pet.name)
            system_handled = True
        elif ability_id == 73:                               # Stay
            pet = getattr(self, "pet_entity", None)
            if pet is not None:
                pet.pet_state = "stay"
                self.say("%s stays." % pet.name)
            system_handled = True

        # The handful of abilities with a visible state change.
        if ability_id == 35 and target is not None:          # Provoke
            # Provoke is a large fixed cumulative hate spike, not a teleport of the
            # monster: a tank that pulls with it keeps the target until damage
            # out-weighs 1,800 CE (plus the 200 CE claim bonus).
            self.world.add_mob_hate(target, me, now=now, ce=1800, ve=0)
            target.engaged_char_id = me
            target.next_attack_at = now + 1.5
            target.aggro_announced = True
            self.world.set_animation(target, 1)
            self.engaged_id = int(target.id)
            self.engaged_targid = int(target.targid)
            self.next_attack_at = now + 0.5
            # Provoke engages, so it sends the same target and stance packets as /attack.
            self.queue.append(sub(0x058, struct.pack(
                "<IIHH", me, int(target.id), int(self.char.get("targid", 0x400)), 0)))
            self.queue.append(self.char_update(packets.SEND_HP))
        elif ability_id == 18:                               # Benediction
            self._benediction(now, ability)
            system_handled = True
        elif ability_id == 38:                               # Chakra
            heal = max(1, int(self.char["hp"]) // 4)
            heal += job_points.category_total(2, "Chakra Effect")
            self._heal_job_ability(heal)
        elif ability_id == 63:                               # Meditate
            # Retail: 200 TP a tick for five ticks (1000 total) as a Samurai main, and
            # 120 a tick to 600 as a sub job.  The job-point row adds 5 a tick.
            main = int(self.char.get("main_job") or 0) == 12
            per = (200 if main else 120) + (
                job_points.category_total(12, "Meditate Effect") if main else 0)
            self.meditate = {"per": per, "cap": 1000 if main else 600, "total": 0,
                             "ticks": 5, "next": now + 3.0}
        elif ability_id == 83:                               # Convert
            hp = int(self.char.get("hp_current", 0))
            mp = int(self.char.get("mp_current", 0))
            self.char["hp_current"] = min(int(self.char["hp"]), mp)
            self.char["mp_current"] = min(int(self.char.get("mp", 0)), hp)
            # RDM job-point Convert restores 1% max HP per rank after the swap.
            percent = job_points.category_total(5, "Convert Effect")
            if percent:
                self.char["hp_current"] = min(
                    int(self.char["hp"]),
                    int(self.char["hp_current"]) + int(self.char["hp"]) * percent // 100)
            self.queue += [self.char_stats(), self.char_status(), self.party_member()]
        elif ability_id == 210:                              # Tabula Rasa
            # SCH job points recover 2% max MP per rank when Tabula Rasa is used.
            percent = job_points.category_total(20, "Tabula Rasa Effect")
            max_mp = int(self.char.get("mp", 0) or 0)
            if percent and max_mp > 0:
                gain = max_mp * percent // 100
                self.char["mp_current"] = min(
                    max_mp, int(self.char.get("mp_current", 0)) + gain)
                self.queue += [self.char_stats(), self.char_status()]
        elif ability_id in (24, 225, 281):
            # Familiar, Snarl and Spur still need their real pet effects.  Reward and
            # Run Wild are handled above; they must not fall through to this message.
            pet = getattr(self, "pet_entity", None)
            if pet is not None and pet.alive:
                self.say("%s is not implemented yet." % name)
            else:
                self.say("You have no pet for %s." % name)
        elif applied is None and fallback is None and not system_handled:
            # An ability that put up an icon needs no "You use ..." line: the 0x028
            # above already prints it, and retail only shows the one.
            self.say("You use %s." % name)

        recast = max(0, int(ability.get("recast") or 0))
        if (recast_id or recast) and not ability_failed:
            if fallback is not None:
                recast = max(0, recast - int(fallback.get("recast_bonus") or 0))
            # The Master job-point gift ("★Master!") shortens every one-hour
            # ability's recast by 15 minutes.  It is stored on the gift table as
            # modifier 996 and applies to the shared two-hour slot.
            master_minutes = int(job_points.gift_totals(
                int(self.char.get("main_job") or 0))["mods"].get(
                    mod.ONE_HOUR_RECAST, 0))
            if master_minutes and recast >= 3600:
                recast = max(0, recast - master_minutes * 60)
            if (dancer.is_flourish(int(ability_id))
                    and self.has_effect(effects.GRAND_PAS)):
                recast = 0
            elif int(ability_id) == 97:                       # Phantom Roll
                recast = max(0, recast - int(
                    self.combat_mods().get(mod.PHANTOM_ROLL, 0)))
            elif int(ability_id) in (66, 67, 68, 260, 293) and float(
                    getattr(self, "_fly_high_until", 0.0)) > time.time():
                recast = 10
            elif int(ability_id) == 310:                     # Deus Ex Automata
                recast = max(0, recast - job_points.category_total(
                    18, "Deus Ex Automata Recast"))
            elif int(ability_id) == 272:                     # Enmity Douse
                recast = max(0, recast - job_points.category_total(
                    4, "Enmity Douse Recast"))
            elif int(ability_id) == 41:                      # Steal
                recast = max(0, recast - job_points.category_total(6, "Steal Recast"))
            elif int(ability_id) in (211, 212):              # Light Arts / Dark Arts
                # Grimoire Recast: 2 seconds a merit rank off the arts' 60 s recast.
                recast = max(0, recast - 2 * self._sch_merit(
                    merits.SCH_GRIMOIRE_RECAST))
            if dancer.is_waltz(int(ability_id)):
                # Trance pins every waltz to 6 seconds; Fan Dance merits take 5% off
                # the recast per rank (1 merit = 5, 5/5 = 25%).
                if self.has_effect(effects.TRANCE):
                    recast = min(recast, 6)
                if self.has_effect(effects.FAN_DANCE):
                    fan_rank = self._dnc_merit(dancer.MERIT_FAN_DANCE)
                    if fan_rank:
                        recast = recast * max(0, 100 - 5 * fan_rank) // 100
            self.ability_recasts[recast_key] = now + recast
            self.queue.append(self.abil_recast())
        try:
            self.world.service.save_vitals(
                self.char["id"], int(self.char.get("hp_current", 0)),
                int(self.char.get("mp_current", 0)))
        except Exception:
            pass

    def _ammo_jug(self) -> tuple[dict, int, int, int] | None:
        """The Call Beast jug equipped in ammo: (catalogue row, container, slot, item id)."""
        entry = self.equipped.get(3)          # equip kind 3 is ammo
        if not entry:
            return None
        container, slot, item_id = (int(entry[0]), int(entry[1]), int(entry[2]))
        row = jugpets.for_item(item_id)
        if row is None:
            return None
        return row, container, slot, item_id

    def _consume_ammo_jug(self, item_id: int, container: int, slot: int) -> None:
        """Call Beast eats one jug from the equipped stack.

        The slot update is the same 0x020 item-use sends, and an emptied stack also
        clears the ammo slot so the client does not keep drawing a jug the server no
        longer has.  The phase engine's restore set can equip the normal ammo right
        after the action result.
        """
        try:
            consumed = self.world.service.consume_inventory_slot(
                int(self.char["id"]), container, slot)
        except Exception as exc:
            log.warning("%s jug consume failed: %s", self.addr, exc)
            return
        if consumed is None:
            return
        left = int(consumed["quantity"])
        self.queue.append(sub(0x020, packets.item_attr(
            item_id if left else 0, left, container, slot)))
        self.queue.append(self.container_sync())
        if left <= 0:
            self.equipped.pop(3, None)
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, 3, 0)))
            self.note_equipment_change()

    def _call_jug(self, ability_id: int, now: float) -> bool:
        """Call Beast (85) or Bestial Loyalty (387) with the ammo jug's pet.

        Retail picks the pet from the jug's subskill; the generated catalogue carries
        that mapping.  Call Beast spends the jug, Bestial Loyalty keeps it.  A missing
        jug is reported before the pet spawn so the player knows why nothing happened.
        """
        found = self._ammo_jug()
        if found is None:
            self.say("You must equip a Call Beast jug in your ammo slot.")
            return False
        row, container, slot, item_id = found
        pet = self.world.spawn_pet(self, spec=jugpets.spec(row), now=now)
        if pet is None:
            return False
        pet.pet_jug_item = item_id
        self.pet_jug_item = item_id
        if int(ability_id) == 85:             # Call Beast spends the jug
            self._consume_ammo_jug(item_id, container, slot)
        return True

    def _heal_job_ability(self, amount: int) -> None:
        """Add HP (capped at the maximum) and keep the client's gauges in step."""
        hp = int(self.char.get("hp_current", 0))
        healed = min(int(self.char["hp"]), hp + max(0, int(amount)))
        self.char["hp_current"] = healed
        self.queue += [self.char_status(), self.party_member()]
        self.say("You recover %d HP." % (healed - hp))

    def _buff_values(self, spell: dict,
                     spec: "effects.SpellEffect") -> tuple[float, int, int, bool]:
        """Duration, tick, power and Perpetuance flag for one enhancing buff.

        The caster's Light Arts/Tabula Rasa and gear feed every recipient: an Accession
        spell is one cast, so the party gets the numbers the Scholar rolled, not each
        member's own enhancing-duration gear.
        """
        char_mods = self.combat_mods()
        name = str(spell["name"])
        skill = int(spell.get("skill") or 0)
        enhancing = skill == packets.SKILL_ENHANCING
        white_enhancing = enhancing and effects.is_white_enhancing(name)
        perpetuance = white_enhancing and self.has_effect(effects.PERPETUANCE)
        main_job = int(self.char.get("main_job") or 0)
        main_level = int(self.char.get("main_level") or 0)
        # Enlightenment optimizes both arts for its one spell.
        light_arts = (self.has_effect(effects.LIGHT_ARTS)
                      or self.has_effect(effects.ENLIGHTENMENT))
        tabula_rasa = self.has_effect(effects.TABULA_RASA)
        # job_points_detail sends every category at rank 20, so the Light Arts Effect
        # rank the duration formula reads is 20 too (+60 s before Perpetuance).
        duration = effects.buff_duration(
            spec, main_job=main_job, main_level=main_level, mods=char_mods,
            skill=skill, light_arts=light_arts, tabula_rasa=tabula_rasa,
            light_arts_jp_rank=JOB_POINT_RANK, enhancing=enhancing,
            perpetuance=perpetuance, white_enhancing=white_enhancing, name=name)
        tick = effects.buff_tick(
            spec, main_job=main_job, main_level=main_level, mods=char_mods,
            light_arts=light_arts, tabula_rasa=tabula_rasa)
        if effects.is_enspell(int(spec.effect)):
            power = self._enspell_starting_charge(spec, name)
        else:
            power = effects.buff_power(spec, char_mods)
        return duration, tick, power, perpetuance

    def _enspell_starting_charge(self, spec: "effects.SpellEffect", name: str) -> int:
        """The value an en-spell stores when it lands.

        Tier I stores the base damage for the whole buff: retail freezes it at cast, so
        the midcast set's Enhancing Magic skill is what counts.  Tier II stores zero
        because its base is recalculated from the current skill every round and the
        stored number is the hidden attack-round counter.  Enlight/Endark store their
        decaying charge, which comes from Divine or Dark Magic skill instead.
        """
        tier = effects.enspell_tier(int(spec.effect))
        if tier == 2:
            return 0
        skills, _base = self.effective_skills()
        if tier == 3:
            skill_id = (packets.SKILL_DIVINE if effects.enspell_element(int(spec.effect)) == 7
                        else packets.SKILL_DARK)
            return combat.enlight_potency(
                int(skills.get(skill_id, 0)), tier=effects.tier_of(name))
        return combat.enspell_potency(int(skills.get(packets.SKILL_ENHANCING, 0)))

    def _party_spell_target(self, act_index: int):
        """The party member selected with the client's sub-target cursor.

        The 0x01A act index is the target's targid.  Players are not ZoneEntity rows,
        so ``entity_by_targid`` cannot see them; the party roster carries the targid
        the caster's client displays.  Self is always 0x400 in the caster's own view.
        """
        if not act_index:
            return None
        me = int(self.char["char_id"])
        if int(act_index) in (TARGID, int(getattr(self, "targid", 0) or 0)):
            return self
        party = self.world.party_of(me)
        if party is None:
            return None
        for member in party.members:
            if int(member.char_id) == me or int(member.targid) != int(act_index):
                continue
            other = self.world.session_by_char(int(member.char_id))
            if other is None or int(other.zone) != int(self.zone):
                return None
            if other.dead_until or int(other.char.get("hp_current", 0)) <= 0:
                return None
            if math.dist(self.pos[:3], other.pos[:3]) > 25.0:
                return None
            return other
        return None

    def _heal_target(self, target, spell: dict, cast: dict) -> None:
        """Apply a finished Cure to ``target`` and refresh both clients."""
        me = int(self.char["char_id"])
        hp = int(target.char.get("hp_current", 0))
        maximum = int(target.char.get("hp", hp))
        healed = min(maximum, hp + int(cast.get("amount") or 0))
        target.char["hp_current"] = healed
        action = sub(0x028, packets.battle_action(
            me, int(target.char["char_id"]), healed - hp,
            animation=spell_animation(spell), kind=0,
            message=packets.MESSAGE_MAGIC_RECOVERS_HP, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"])))
        self.queue.append(action)
        if target is self:
            self.queue += [self.char_status(), self.party_member()]
        else:
            target.queue += [action, target.char_status(), target.party_member()]
            self.queue.append(self.party_member())
        try:
            self.world.service.save_vitals(
                int(target.char["id"]), healed, int(target.char.get("mp_current", 0)))
        except Exception:
            pass
        if self.resting:
            self.stop_resting()

    def _buff_target(self, target, spell: dict, now: float,
                     spec: "effects.SpellEffect") -> None:
        """Apply a finished enhancing buff to one party member."""
        me = int(self.char["char_id"])
        duration, tick, power, perpetuance = self._buff_values(spell, spec)
        if effects.is_enspell(int(spec.effect)):
            # Only one en-spell is active at a time, and a recast starts the tier II
            # counter over instead of carrying the old one across.  En-spells are
            # self-targeted, so the list being cleared is the caster's own.
            for effect_id in effects.ENSPELL_IDS:
                target.remove_effect(int(effect_id), quiet=True)
        mods = dict(spec.mods)
        mods.update(self._storm_mods(str(spell.get("name") or "")))
        target.add_effect(spec.effect, duration=duration, power=power,
                          potency=spec.potency, tick=tick, icon=spec.icon,
                          mods=mods)
        if perpetuance:
            self.remove_effect(effects.PERPETUANCE, quiet=True)
        action = sub(0x028, packets.battle_action(
            me, int(target.char["char_id"]), int(spec.effect),
            animation=spell_animation(spell), kind=0,
            message=packets.MESSAGE_MAGIC_GAIN_EFFECT, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"])))
        self.queue.append(action)
        if target is self:
            self.queue.append(self.char_status())
        else:
            target.queue += [action, target.char_status()]
            if perpetuance:
                self.queue.append(self.char_status())
        if self.resting:
            self.stop_resting()

    def resolve_self_spell(self, spell: dict, now: float,
                           spec: "effects.SpellEffect | None" = None) -> None:
        """A spell aimed at you: a self buff, a teleport, or a spell with no effect yet.

        The old version always sent a result with message 1 ("hits for N damage") and
        zero damage, which is why Monomi and Utsusemi printed "hits itself for 0 damage".
        A buff now carries its effect id in the result value and message 230, so the
        client prints the gain-effect line and draws the icon.
        """
        me = int(self.char["char_id"])
        name = str(spell["name"])
        if name in ("Warp", "Warp II", "Retrace"):
            # The three teleport spells return you to the one Home Point you have set,
            # not to a crystal registered in this zone.  South Gustaberg has no Home
            # Point at all, so the old current-zone lookup refused Warp there even
            # though the character's set Home Point (the Bastok Markets crystal) exists.
            zone = int(self.char.get("home_zone") or 0)
            if zone > 0:
                dest = [float(self.char.get("home_x") or 0.0),
                        float(self.char.get("home_y") or 0.0),
                        float(self.char.get("home_z") or 0.0),
                        int(self.char.get("home_rot") or 0)]
            else:
                home = None
                try:
                    home = self.world.service.last_home_point(int(self.char["id"]))
                except Exception as exc:
                    log.warning("%s home point lookup failed: %s", self.addr, exc)
                if home is None:
                    self.say("%s finds no Home Point to return to." % name)
                    return
                zone = int(home["zone"])
                dest = [float(home["x"]), float(home["y"]), float(home["z"]),
                        int(home["rot"])]
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, 0, animation=spell_animation(spell), kind=0, info=0,
                message=packets.MESSAGE_MAGIC_TELEPORT,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.say("%s returns you to %s." % (name, self.world.zones.name(zone)))
            self.change_zone(zone, dest)
            return
        if int(spell.get("valid_targets") or 0) & 0x20:
            # Raise, Raise II/III, Arise, Tractor, Tractor II: the target is a fallen player.
            # Nobody is down, so the cast completes and says so rather than fizzling.
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, 0, animation=spell_animation(spell), kind=0, info=0,
                message=packets.MESSAGE_MAGIC_NO_EFFECT,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.say("%s finds no fallen player to target." % name)
            return
        if spec is not None and spec.kind == "buff":
            self._buff_target(self, spell, now, spec)
            return
        # A support spell with no tracked effect: finish it without a damage result.
        self.queue.append(sub(0x028, packets.battle_action(
            me, me, 0, animation=spell_animation(spell), kind=0,
            message=0, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))))
        self.say("%s takes hold." % name)

    def _accession_targets(self, now: float) -> list:
        """The caster and every live party member inside ``ACCESSION_RANGE``.

        The group roster is the party, not the whole alliance: Accession covers the six
        slots around the caster.  Members in another zone have no position here, and a
        fallen member cannot receive a buff.
        """
        me = int(self.char["char_id"])
        targets = [self]
        party = self.world.party_of(me)
        if party is None:
            return targets
        for member in party.members:
            if int(member.char_id) == me:
                continue
            other = self.world.session_by_char(int(member.char_id))
            if other is None or int(other.zone) != int(self.zone):
                continue
            if other.dead_until > now or int(other.char.get("hp_current", 0)) <= 0:
                continue
            if math.dist(self.pos[:3], other.pos[:3]) > ACCESSION_RANGE:
                continue
            targets.append(other)
        return targets

    def _song_values(self, spell: dict, spec: "effects.SpellEffect"
                     ) -> tuple[float, int, dict[int, int]]:
        """(duration, tick, mods) for one song from the caster's live state."""
        name = str(spell["name"])
        mods = self.combat_mods()
        soul_voice = self.has_effect(effects.SOUL_VOICE)
        marcato = self.has_effect(effects.MARCATO) and not soul_voice
        duration = effects.song_duration(
            spec, name=name, mods=mods,
            troubadour=self.has_effect(effects.TROUBADOUR),
            soul_voice=soul_voice, marcato=marcato,
            clarion=self.has_effect(effects.CLARION_CALL),
            tenuto=self.has_effect(effects.TENUTO),
            flat_seconds=self.song_duration_flat(name))
        effect_mods, tick = effects.song_potency_values(
            name, spec, mods, soul_voice=soul_voice, marcato=marcato,
            flat_bonus=self.song_flat_bonus(name))
        return duration, tick, effect_mods

    def song_flat_bonus(self, name: str) -> int:
        """The flat points a song gets from Bard group-1 merits and its job-point row.

        Retail adds these after the +Song percentage and before Soul Voice/Marcato:
        Minuet +1 a merit rank and +20 from the job-point row, Minne +2 a rank and
        +20, Madrigal +1 a rank, Requiem +60 on its DoT.
        """
        if int(self.char.get("main_job") or 0) != 10:
            return 0
        family = effects.song_family(name)
        if family not in ("minuet", "minne", "madrigal"):
            return 0
        counts = self.merit_counts()
        merit_id = {
            "minuet": merits.MINUET_EFFECT,
            "minne": merits.MINNE_EFFECT,
            "madrigal": merits.MADRIGAL_EFFECT,
        }.get(family)
        bonus = 0
        if merit_id is not None:
            entry = merits.MERITS.get(int(merit_id))
            if entry is not None:
                per_rank, max_ranks = int(entry[3]), int(entry[2])
                ranks = max(0, min(int(counts.get(int(merit_id), 0)), max_ranks))
                bonus += ranks * per_rank
        category = {"minuet": "Minuet Effect", "minne": "Minne Effect"}.get(family)
        if category:
            bonus += job_points.category_total(10, category)
        return bonus

    def equipped_range_item(self) -> int:
        """The item id in the ranged slot, or 0 when the query fails."""
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
            return int((weapons.get(2) or {}).get("item_id") or 0)
        except Exception:
            return 0

    def _song_limit(self) -> int:
        """The number of party songs this caster's instrument can maintain."""
        skill = 0
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
            skill = int((weapons.get(2) or {}).get("skill") or 0)
        except Exception as exc:
            log.debug("%s song instrument lookup failed: %s", self.addr, exc)
        return effects.song_slots(
            int(self.char.get("main_job", 0)), skill, self.combat_mods(),
            clarion=self.has_effect(effects.CLARION_CALL))

    def _apply_song(self, spell: dict, spec: "effects.SpellEffect", *,
                    duration: float, tick: int, mods: dict[int, int],
                    limit: int, now: float) -> bool:
        """Put one song on this target, enforcing song slots and overwrite rules.

        Songs are keyed by spell identity, not by their shared status icon.  Victory
        March and Advancing March both draw icon 214, and Paeon I/II/III all draw 195,
        but each is a different song and takes its own slot.  Only a second cast of the
        same song refreshes/replaces that song.

        Retail does not let the same song refresh while more than its **base**
        duration remains, and a new song replaces the active song with the least
        time left.  The caller has already rolled the caster's duration/potency, so
        the same numbers land on every target.
        """
        effect_id = int(spec.effect)          # icon / action-result effect id
        key = effects.song_key(int(spell["id"]))  # one state per song, not per icon
        base = float(spec.duration)
        existing = self.effect(key)
        if existing is not None and existing.get("song"):
            if float(existing.get("until", 0.0)) - now >= base:
                return False
        songs = [(int(eid), state) for eid, state in self.effect_state.items()
                 if state.get("song") and float(state.get("until", 0.0)) > now]
        if (existing is None or not existing.get("song")) and len(songs) >= int(limit):
            if not songs:
                return False
            victim_id, _state = min(
                songs, key=lambda item: (
                    float(item[1].get("until", 0.0)),
                    float(item[1].get("song_cast_at", 0.0))))
            self.remove_effect(victim_id, quiet=True)
        self.add_effect(
            key, duration=duration, tick=tick, mods=mods, icon=effect_id,
            song_base=base, song_name=str(spell["name"]), song_cast_at=now,
            song_effect=effect_id)
        return True

    def song_targets(self, now: float, cast: dict | None) -> list:
        """Who a song lands on: the party radius, or one member under Pianissimo.

        Retail's Pianissimo narrows the next song to the party member it was cast on;
        the other party songs stay a radius around the bard.
        """
        targets = self._accession_targets(now)
        if cast is None or not self.has_effect(effects.PIANISSIMO):
            return targets
        wanted = int(cast.get("party_target") or 0)
        if not wanted:
            return targets
        chosen = [t for t in targets if int(t.char["char_id"]) == wanted]
        return chosen or targets

    def resolve_song_spell(self, spell: dict, now: float,
                            spec: "effects.SpellEffect", cast: dict | None = None) -> None:
        """Land one bard song on the caster and their nearby party.

        Songs are party buffs in retail; before this they only touched the caster
        because the self-cast path had no party spread.  The range is the same ten
        yalms Accession uses, which is also the client's party-song radius.  Each
        target enforces its own song slots, and the caster's instrument (plus
        Clarion Call) decides how many those are.
        """
        me = int(self.char["char_id"])
        duration, tick, mods = self._song_values(spell, spec)
        limit = self._song_limit()
        animation = spell_animation(spell)
        self_applied = False
        for target in self.song_targets(now, cast):
            applied = target._apply_song(
                spell, spec, duration=duration, tick=tick, mods=mods,
                limit=limit, now=now)
            if applied and effects.song_family(str(spell["name"])) == "hymnus":
                # Hymnus is the party's Reraise; the song icon stays on 218 and the
                # raise rides a separate effect so death can consume it.
                target.add_effect(effects.RERAISE, duration=duration)
            if target is self:
                self_applied = applied
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]),
                int(spec.effect) if applied else 0,
                animation=animation, kind=0,
                message=(packets.MESSAGE_MAGIC_GAIN_EFFECT if applied
                         else packets.MESSAGE_MAGIC_NO_EFFECT), info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"])))
            self.queue.append(action)
            if target is not self:
                target.queue += [action, target.char_status()]
        # Tenuto, Marcato and Pianissimo are spent by the next song even when the
        # target's slots refuse it.  Soul Voice, Troubadour, Nightingale and
        # Clarion Call keep their own clocks.
        for effect_id in (effects.TENUTO, effects.MARCATO, effects.PIANISSIMO):
            if self.has_effect(effect_id):
                self.remove_effect(effect_id, quiet=True)
        self.queue.append(self.char_status())
        if not self_applied:
            self.say("Your song did not take hold.")
        if self.resting:
            self.stop_resting()

    def resolve_area_buff(self, spell: dict, now: float,
                          spec: "effects.SpellEffect") -> None:
        """Land a self-centered -ga/-ra buff on the party around the caster.

        The client data marks Hastega/Protectra/Shellra as target=self with an area
        shape, so the ordinary self-cast path would only touch the caster.  Apply the
        same rolled duration and mods to every live party member inside the spell's
        area, with a per-recipient action so each client draws its own icon.
        """
        me = int(self.char["char_id"])
        duration, tick, power, perpetuance = self._buff_values(spell, spec)
        if perpetuance:
            self.remove_effect(effects.PERPETUANCE, quiet=True)
        animation = spell_animation(spell)
        mods = dict(spec.mods)
        mods.update(self._storm_mods(str(spell.get("name") or "")))
        for target in self._accession_targets(now):
            target.add_effect(spec.effect, duration=duration, power=power,
                              potency=spec.potency, tick=tick, icon=spec.icon,
                              mods=mods)
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), int(spec.effect),
                animation=animation, kind=0,
                message=packets.MESSAGE_MAGIC_GAIN_EFFECT, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"])))
            self.queue.append(action)
            if target is not self:
                target.queue += [action, target.char_status()]
        self.queue.append(self.char_status())
        if self.resting:
            self.stop_resting()

    def resolve_party_spell(self, spell: dict, now: float,
                            spec: "effects.SpellEffect") -> None:
        """Land one Accession spell on the caster and the party around them.

        Every member gets the caster's rolled duration, tick and power, its own 0x028
        result and its own 0x037 icon list, so a boxed client draws the effect right
        away instead of waiting for its next party sync.  Accession is spent when the
        spell lands, which leaves the icon up for the length of the cast bar.
        """
        me = int(self.char["char_id"])
        duration, tick, power, perpetuance = self._buff_values(spell, spec)
        if perpetuance:
            self.remove_effect(effects.PERPETUANCE, quiet=True)
        self.remove_effect(effects.ACCESSION, quiet=True)
        animation = spell_animation(spell)
        mods = dict(spec.mods)
        mods.update(self._storm_mods(str(spell.get("name") or "")))
        for target in self._accession_targets(now):
            target.add_effect(spec.effect, duration=duration, power=power,
                              potency=spec.potency, tick=tick, icon=spec.icon,
                              mods=mods)
            action = sub(0x028, packets.battle_action(
                me, int(target.char["char_id"]), int(spec.effect),
                animation=animation, kind=0,
                message=packets.MESSAGE_MAGIC_GAIN_EFFECT, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"])))
            self.queue.append(action)
            if target is not self:
                target.queue += [action, target.char_status()]
        self.queue.append(self.char_status())
        if self.resting:
            self.stop_resting()

    def request_entity(self, p: bytes) -> None:
        if len(p) < 8:
            return
        act = struct.unpack_from("<H", p, 4)[0]
        if act == TARGID:
            if self.zone_loaded:
                # A mid-session self request follows the Data page's reload.  Answer with
                # the General block and status, never the full spawn: its name/model blocks
                # reset the client's own player entity into the green-name/NPC state that
                # cannot act until a relog.
                self.queue += [self.char_update(packets.SEND_HP), self.char_status()]
            else:
                # During the zone-in the client may not have the self entity yet; the full
                # spawn is the packet that creates it.
                self.queue += [self.char_update(), self.char_status()]
            return
        entity = self.world.entity_by_targid(self.zone, act)
        if entity is not None:
            self.queue_spawn(entity)

    def gain_tp(self, tenths: int, *, queue: bool = True) -> None:
        """Add TP and refresh the bar.  TP is kept in tenths, the client's own unit.

        ``queue=False`` lets a caller that sends its own 0x00DF (the passive tick) share
        one packet instead of queueing a second copy.
        """
        current = int(self.char.get("tp", 0))
        tp = min(TP_MAX, current + max(0, int(tenths)))
        if tp == current:
            return
        self.char["tp"] = tp
        if queue:
            self.queue.append(self.party_member())
        # Diagnostic: the client's TP bar and the party window both read this value; if
        # the bar is stuck at zero while swings land, this line says whether the server
        # gained TP at all (and how much it queued for the client).
        log.info("%s TP %d -> %d (+%d)", self.addr, current, tp, int(tenths))

    def spend_tp(self, tenths: int) -> int:
        """Pay an ability's TP cost and refresh the bar; returns what was actually paid."""
        current = int(self.char.get("tp", 0))
        paid = max(0, min(current, int(tenths)))
        if paid:
            self.char["tp"] = current - paid
            self.queue.append(self.party_member())
        return paid

    def take_damage(self, amount: int, entity) -> None:
        self.stop_resting()
        amount = max(0, int(amount))
        # Stoneskin eats a pool of damage, Phalanx takes a flat amount off every hit.
        stoneskin = self.effect_state.get(effects.STONESKIN)
        if stoneskin is not None and int(stoneskin.get("power", 0)) > 0 and amount > 0:
            absorbed = min(amount, int(stoneskin["power"]))
            stoneskin["power"] = int(stoneskin["power"]) - absorbed
            amount -= absorbed
            if int(stoneskin["power"]) <= 0:
                self.remove_effect(effects.STONESKIN, quiet=True)
            self.queue.append(self.char_status())
        phalanx = self.effect_state.get(effects.PHALANX)
        if phalanx is not None and amount > 0:
            amount = max(0, amount - int(phalanx.get("power", 0)))
        # Dragoon Spirit Bond shares half of incoming damage with the Wyvern.
        pet = getattr(self, "pet_entity", None)
        if (amount > 0 and pet is not None and pet.alive
                and float(getattr(self, "_spirit_bond_until", 0.0)) > time.time()):
            share = amount // 2
            pet.hp = max(0, int(pet.hp) - share)
            amount -= share
            self.world._queue_mob_hp(pet)
            if int(pet.hp) <= 0:
                pet.alive = False
        self.char["hp_current"] = max(0, int(self.char.get("hp_current", self.char["hp"])) - int(amount))
        self.queue += [self.char_status(), self.party_member()]
        # Retail also pays TP for damage taken, scaled to how much of your HP the hit took.
        self.gain_tp(1000 * int(amount) // max(1, int(self.char["hp"])))
        try:
            self.world.service.save_vitals(self.char["id"], self.char["hp_current"], self.char.get("mp_current", 0))
        except Exception:
            pass
        if int(self.char["hp_current"]) <= 0:
            self.hit_zero_hp(time.time())

    def hit_zero_hp(self, now: float) -> None:
        """0 HP: Reraise brings the character back, otherwise the short recovery.

        Reraise (and Goddess's Hymnus) restores 10% of max HP and half the lost
        experience the next time the character is raised; this server's death is the
        six-second recovery, so the effect is consumed here.
        """
        self.engaged_id = None
        self.engaged_targid = 0
        self.despawn_trusts()
        # A song's Reraise is keyed by spell identity (a song slot), not by the effect
        # id, so look for either shape.
        reraise_key: int | None = None
        reraise = self.effect_state.get(effects.RERAISE)
        if reraise is not None:
            reraise_key = effects.RERAISE
        else:
            for key, state in list(self.effect_state.items()):
                if int(state.get("song_effect") or 0) == effects.RERAISE:
                    reraise_key = int(key)
                    reraise = state
                    break
        if (reraise_key is not None and reraise is not None
                and float(reraise.get("until") or 0.0) > now):
            self.remove_effect(reraise_key, quiet=True)
            self.char["hp_current"] = max(1, int(self.char.get("hp", 1)) // 10)
            self.dead_until = 0.0
            self.queue += [self.char_status(), self.char_stats(),
                           self.char_update(packets.SEND_HP)]
            self.say("Reraise raises you.")
            try:
                self.world.service.save_vitals(int(self.char["id"]),
                                               int(self.char["hp_current"]),
                                               int(self.char.get("mp_current", 0)))
            except Exception:
                pass
            return
        self.dead_until = now + 6.0
        self.queue.append(self.char_update(packets.SEND_HP))
        self.say("You have been defeated. You recover in a moment.")
        try:
            self.world.service.record_death(int(self.char["id"]))
        except Exception:
            pass

    def tick_regen(self, now: float) -> None:
        """Apply Auto Refresh/Auto Regen and gear Refresh/Regen/Regain once per 3 seconds.

        These are passive modifiers, not status effects: the client draws no icon for
        them.  The tick uses the same merged modifier dict as the stat sheet, so the
        traits and gear both feed it.  ``REGEN_DOWN``/``REFRESH_DOWN`` come first, and a
        negative total never drains the character.  Regain adds TP, capped at 3000.

        The maxima are re-derived from the sheet on every tick.  A gear change can raise
        the stored maximum (or a save can carry an older one), and a maximum that is too
        low is exactly what makes Regen/Refresh stop early: the character sits at the
        stale cap while the client still draws the missing HP/MP.
        """
        if now < self.next_regen_tick:
            return
        self.next_regen_tick = now + traits.TICK_SECONDS
        if (self.zoning or not self.zone_loaded or self.dead_until
                or int(self.char.get("hp_current", 0)) <= 0):
            return
        try:
            sheet = self.stat_sheet()
        except Exception as exc:
            log.warning("%s stat sheet unavailable for the passive tick: %s", self.addr, exc)
            sheet = None
        if sheet is not None:
            # Keep the stored maxima -- and the save row -- in step before refilling.
            self.refresh_vitals(sheet)
            mods = sheet.fighter.mods
            hp_max = max(1, int(sheet.max_hp))
            mp_max = max(0, int(sheet.max_mp))
        else:
            mods = self.combat_mods()
            hp_max = max(1, int(self.char.get("hp", 1)))
            mp_max = max(0, int(self.char.get("mp", 0)))
        regen = max(0, int(mods.get(mod.REGEN, 0)) - int(mods.get(mod.REGEN_DOWN, 0)))
        refresh = max(0, int(mods.get(mod.REFRESH, 0))
                      - int(mods.get(mod.REFRESH_DOWN, 0)))
        regain = max(0, int(mods.get(mod.REGAIN, 0)))
        if regen <= 0 and refresh <= 0 and regain <= 0:
            return
        changed = False
        vitals_changed = False
        hp = int(self.char.get("hp_current", 0))
        if regen > 0 and hp < hp_max:
            hp = min(hp_max, hp + regen)
            self.char["hp_current"] = hp
            changed = vitals_changed = True
        mp = int(self.char.get("mp_current", 0))
        if refresh > 0 and mp < mp_max:
            mp = min(mp_max, mp + refresh)
            self.char["mp_current"] = mp
            changed = vitals_changed = True
        if regain > 0 and int(self.char.get("tp", 0)) < TP_MAX:
            # gain_tp logs the bar change; the packet below covers the party window.
            self.gain_tp(regain, queue=False)
            changed = True
        if not changed:
            return
        self.queue += [self.char_status(), self.party_member()]
        if not vitals_changed:
            return
        try:
            self.world.service.save_vitals(int(self.char["id"]), hp, mp)
        except Exception as exc:
            log.warning("%s regen tick save failed: %s", self.addr, exc)

    def tick(self, now: float) -> None:
        # The gear burst has settled (or waited out EQUIP_SYNC_MAX_DELAY): send what the
        # outfit changed.  This is the deferred half of note_equipment_change(); the
        # 0x050 echoes and the outfit save went out as the datagrams were read.
        if self.equipment_changed and now >= self.equip_sync_at:
            self.flush_equipment()
        if (self._commands_pending
                and now >= self._commands_sent_at + EQUIP_COMMANDS_MIN_GAP):
            # The deferred command-data rewrite: the burst has settled, send the final list.
            message = self.char_commands()
            self._sync_sent[0x0AC] = self._sync_signature(message)
            self._commands_sent_at = now
            self._commands_pending = False
            self.queue.append(message)
        if self.sleeping:
            return
        if self.meditate is not None and now >= float(self.meditate["next"]):
            state = self.meditate
            gain = min(int(state["per"]), max(0, int(state["cap"]) - int(state["total"])))
            if gain:
                self.gain_tp(gain)
                state["total"] = int(state["total"]) + gain
            state["ticks"] = int(state["ticks"]) - 1
            state["next"] = now + 3.0
            if int(state["ticks"]) <= 0 or int(state["total"]) >= int(state["cap"]):
                self.meditate = None
        if self.pending_mount is not None and now >= self.pending_mount[1]:
            mount_id, _at = self.pending_mount
            self.pending_mount = None
            self.set_mount(mount_id, announce=False)
        # A quiet zone sends nothing on its own: no mob moved, no party vital changed,
        # nobody walked past.  The client still sends its 0x015 about once a second and
        # reads the server's silence as a dead link, so a General-only 0x00D goes out as a
        # keepalive whenever nothing else has for IDLE_HEARTBEAT seconds.  It also acks
        # the client's packet stream, which is what its own window is waiting on.
        if (self.logged_in and not self.zoning and not self.gone and self.zone_loaded
                and now - max(self.last_sent_at, self.idle_heartbeat_at) >= IDLE_HEARTBEAT):
            self.idle_heartbeat_at = now
            self.queue.append(self.char_update(packets.SEND_HP))
        if (self.logged_in and not self.zoning and self.entities_sent
                and now >= self.next_entity_sync):
            self.next_entity_sync = now + 1.0
            self.sync_nearby_entities()
        if (self.logged_in and not self.zoning and self.zone_loaded and self.entities_sent
                and now >= self.next_player_sync):
            self.next_player_sync = now + 0.25
            self.sync_players()
        # Another client only learns where this character stands from the 0x00D the
        # movement handler broadcasts, so a stationary character sends nothing.  A box
        # that zoned in while the leader walked -- and was still loading when those
        # packets went by -- keeps the copy it spawned with, believes the leader is
        # still at the warp anchor, and stands still until the leader moves again.
        # One position refresh a second lets a late observer converge on its own.
        if (self.logged_in and not self.zoning and self.zone_loaded and self.entities_sent
                and not self.moving and now >= self.next_position_refresh):
            self.next_position_refresh = now + 1.0
            self.world.broadcast_player(self, packets.SEND_POSITION, moving=False)
        if self.abilities_retries and now >= self.abilities_retries[0]:
            self.abilities_retries.pop(0)
            # Re-assert the equipped set first.  The client rebuilds the Abilities menu
            # when the equipment list arrives; 0x0AC on its own fills the bitmap but does
            # not make the already-open (empty) menu re-read it.
            self.queue += self.equipment_packets()
            self.queue.append(self.grap_list())
            # The Job Abilities list is built from the job info block as well; a 0x01B
            # that arrived before the menu existed leaves it empty even when 0x0AC has
            # the bits.  Send it again with the command and recast data.
            self.queue += [sub(0x0AA, self.spell_bits()), self.job_info(),
                           self.char_feats(), self.char_abilities(), self.char_commands(),
                           self.char_skills(), self.abil_recast()]
            log.info("%s re-sent equipment and command data (%d retries left)", self.addr,
                     len(self.abilities_retries))
        if (self.live_state_notice is not None and self.zone_loaded
                and now >= self.live_state_notice_at):
            self._announce_live_state()
        self.resolve_casting(now)
        self.tick_player_effects(now)
        self.tick_rest(now)
        self.tick_regen(now)
        # The state a reconnect gets back: buffs, food and ability cooldowns.  Comparing
        # the payload catches every path that mutates it (a song, a shadow spent, a
        # Stoneskin pool, an ability's recast) without a touch call at each one, and the
        # row is only written when the payload actually changed.
        if (self.logged_in and not self.zoning and self.zone_loaded
                and (self.live_state_signature is None
                     or now >= self.live_state_checked_at + LIVE_STATE_SAVE_INTERVAL)):
            self.save_live_state(now=now)
        if (not getattr(self, "sweep_started", False) and self.logged_in and self.zone_loaded
                and os.environ.get("FANXI_SG_SWEEP")):
            self.sweep_started = True
            lsb = [0, 16385, 999999999, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 2079]
            no_tut = [0, 1, 999999999, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 2079]
            variants = [
                (676, 8, lsb, None), (676, 8, [0] * 8, None),
                (676, 0, lsb, None), (676, 0, [0] * 8, None),
                (676, 8, no_tut, None), (676, 8, [1] + lsb[1:], None),
                (676, 8, [0, 1] + [0] * 6, None), (676, 8, lsb, 0),
                (677, 8, lsb, None), (677, 8, [0] * 8, None),
                (9, 8, lsb, None), (9, 8, [0] * 8, None),
            ]
            self.sweep = variants
            self.sweep_at = 0.0
            entity = min((e for e in self.entities if e.kind == "npc"),
                         key=lambda e: e.distance_to(*self.pos[:3]), default=None)
            self.sweep_entity = entity
            log.info("%s sweep ready on %s", self.addr, entity.name if entity else None)
        if self.sweep and now >= self.sweep_at:
            self.sweep_at = now + 6.0
            event_id, mode, params, table = self.sweep.pop(0)
            self.sweep_variant += 1
            if self.sweep_entity is not None:
                log.info("%s sweep #%d event %d mode %d table %s params %s", self.addr,
                         self.sweep_variant, event_id, mode, table, params)
                self.start_event(self.sweep_entity, event_id, params, mode=mode,
                                 text_table=table)
        if (not getattr(self, "env_shot_done", False) and self.logged_in and self.zone_loaded
                and os.environ.get("FANXI_EVENT_SHOT")):
            self.env_shot_done = True
            parts = os.environ["FANXI_EVENT_SHOT"].split()
            entity = min((e for e in self.entities if e.kind == "npc"),
                         key=lambda e: e.distance_to(*self.pos[:3]), default=None)
            if entity is not None and parts:
                values = [int(v, 0) & 0xFFFFFFFF for v in parts[1:9]]
                self.start_event(entity, int(parts[0], 0), (values + [0] * 8)[:8])
                log.info("%s env shot %s on %s", self.addr, parts, entity.name)
        if (not getattr(self, "env_scan_started", False) and self.logged_in
                and self.zone_loaded and os.environ.get("FANXI_EVENT_SCAN")):
            spec = os.environ["FANXI_EVENT_SCAN"].split()
            if len(spec) == 2:
                self.env_scan_started = True
                entity = min((e for e in self.entities if e.kind == "npc"),
                             key=lambda e: e.distance_to(*self.pos[:3]), default=None)
                if entity is not None:
                    params = [0, 16385, 999999999, 0xFFFFFFFF, 0xFFFFFFFF,
                              0xFFFFFFFF, 0xFFFFFFFF, 2079]
                    self.scan_events(entity, int(spec[0]), int(spec[1]), params)
                    log.info("%s env scan %s-%s on %s", self.addr, spec[0], spec[1],
                             entity.name)
        # If the client stops sending packets mid-zone, it may be sitting in a
        # client-side event lock.  Cancel the event and release controls once.
        if (self.logged_in and self.zone_loaded and now - self.last_packet_at > 150.0
                and now - self.last_release_at > 150.0):
            self.last_release_at = now
            self.cancel_event(self.current_event_id)
            self.queue.append(sub(0x052, bytes(4)))
            log.info("%s watchdog: released client controls", self.addr)
        if (self.in_event and not self.event_ack
                and self.event_started_at and now - self.event_started_at > 30.0):
            self.in_event = False
            self.event_started_at = 0.0
            failed = self.event_guard_id
            self.event_guard_id = 0
            self.cancel_event(failed)
            self.queue.append(sub(0x052, bytes(4)))
            log.warning("%s event %d did not start; sent cancel", self.addr, failed)
        if self.scan_current and now >= self.scan_deadline:
            if self.scan_current not in self.scan_acks:
                self.cancel_event(self.scan_current)
            self.scan_current = 0
            self.event_scan_at = now + 0.15
        elif not self.scan_current and self.event_scan and now >= self.event_scan_at:
            event_id = self.event_scan.pop(0)
            self.scan_current = event_id
            self.scan_deadline = now + 0.6
            self.start_event(self.event_scan_entity, event_id,
                             getattr(self, "event_scan_params", [0] * 8))
        if self.door_close_at and now >= self.door_close_at:
            entity, self.door_entity = self.door_entity, None
            self.door_close_at = 0.0
            if entity is not None:
                entity.animation = 9  # close_door
                self.queue.append(sub(0x00E, packets.entity_update(entity, mask=0x07)))
        if self.stats_refresh_at and now >= self.stats_refresh_at:
            self.stats_refresh_at = 0.0
            self.queue += [self.char_stats(), self.char_status(), self.party_member()]
        if self.dead_until:
            if now < self.dead_until:
                return
            self.dead_until = 0.0
            self.char["hp_current"] = max(1, int(self.char["hp"]) // 2)
            self.char["mp_current"] = int(self.char.get("mp", 0)) // 2
            try:
                self.world.service.save_vitals(self.char["id"], self.char["hp_current"], self.char["mp_current"])
            except Exception:
                pass
            zone = int(self.char.get("home_zone") or 0)
            if zone > 0:
                # K.O. without a Raise sends you back to your set Home Point.
                self.say("You awaken at your Home Point in %s."
                         % self.world.zones.name(zone))
                self.change_zone(zone, [float(self.char.get("home_x") or 0.0),
                                        float(self.char.get("home_y") or 0.0),
                                        float(self.char.get("home_z") or 0.0),
                                        int(self.char.get("home_rot") or 0)])
            else:
                self.queue += [self.char_status(), self.char_stats(), self.party_member()]
                self.say("You recover from your wounds.")
            return
        if not self.engaged_id:
            return
        # The client can drop the battle stance on its own (a swing, a flinch, a cast,
        # a target change).  Re-send the General animation twice a second while engaged:
        # the pose holds roughly a second, so this is what keeps the weapon out.  The
        # 0x00D hook in the host follows the same byte.
        if not self.casting and now - getattr(self, "stance_at", 0.0) >= 0.5:
            self.refresh_stance()
        entity = self.world.entity_by_id(self.zone, int(self.engaged_id))
        # Diagnostic: one line a second while engaged, showing which branch would run.
        if now - getattr(self, "engage_log_at", 0.0) >= 1.0:
            self.engage_log_at = now
            log.info("%s engage: id=%#x found=%s alive=%s gap=%s next_in=%.2f hp=%s tp=%s",
                     self.addr, int(self.engaged_id), entity is not None,
                     getattr(entity, "alive", None),
                     "n/a" if entity is None else "%.1f" % entity.distance_to(*self.pos[:3]),
                     -1.0 if entity is None else self.next_attack_at - now,
                     "n/a" if entity is None else getattr(entity, "hp", None),
                     int(self.char.get("tp", 0)))
        if entity is None or not entity.alive:
            # The target died or left: drop the stance, or the character keeps its weapon
            # out (and the client keeps the attack animation) forever.
            self.disengage()
            return
        gap = entity.distance_to(*self.pos[:3])
        if gap > ENGAGE_RANGE:
            # Retail loses the target past 30 yalms.
            self.disengage("You lose sight of the target.")
            return
        # A monster another party has claimed cannot be attacked: the client draws it pink
        # and refuses to swing, while this loop would keep landing hits on it.  The claim
        # can move to another party mid-fight (a box's Trust pulling what this character
        # engaged), which left the player unable to attack or disengage while the server
        # kept swinging.  Once the claim is not this character or its party, the fight is
        # over for this client.
        claim = int(getattr(entity, "claim_char_id", 0)
                    or getattr(entity, "engaged_char_id", 0) or 0)
        me = int(self.char["char_id"])
        if claim and claim != me:
            mine = self.world.group_id(me)
            same_party = bool(mine) and mine == self.world.group_id(claim)
            if not same_party:
                log.info("%s disengage: %s is claimed by %#x", self.addr, entity.name, claim)
                self.disengage("That monster is claimed by another party.")
                return
        if gap > MELEE_RANGE:
            # Engaged but out of reach: keep the target, swing once we are close enough.
            # Retail does not drop the engagement just because the mob is far away -- you
            # stay in battle stance and walk to it.
            self.next_attack_at = now + 0.5
            return
        # You cannot swing at something you are facing away from.  Client rotation is in
        # 256ths of a turn, so a quarter turn is 64 units.  Only while actually moving,
        # though: retail turns a standing character to face its target, and this client
        # does not, so gating a stationary player froze combat outright.
        want = heading_to_rot(entity.x - self.pos[0], entity.z - self.pos[2])
        off = abs(((int(self.pos[3]) - int(want) + 128) & 0xFF) - 128)
        moving = now - getattr(self, "last_move_at", 0.0) < 1.0
        if moving and off > 64:
            if now - getattr(self, "facing_log_at", 0.0) >= 5.0:
                self.facing_log_at = now
                log.info("%s facing away from %s: rot=%d want=%d off=%d units",
                         self.addr, entity.name, int(self.pos[3]), int(want), off)
            return
        if now < self.next_attack_at:
            return
        sheet = self.stat_sheet()
        self._last_target_hp = entity.hp_max
        # One action carries the whole round, a result per swing, main hand first.  Each
        # hand rolls its own multi-attack (Quad > Triple > Double) and its extra swings
        # use that hand's animation; retail caps the round at eight hits.  The client
        # plays the results in order from the target's result count.  Sending one packet
        # per hand in the same update made it drop the main hand, so only the off hand
        # swung and only its damage showed.
        #
        # H2H is not a one-handed/two-handed pair: retail throws a right and a left
        # punch every round from the same weapon.  The second fist uses the main-hand
        # fighter again (so its damage and accuracy are the knuckle's, not a 0.5-STR
        # off-hand) but animation 1, which is what makes the client play the left hand.
        results: list[dict] = []
        hp_left = entity.hp
        if sheet.sub_fighter is not None:
            hands = ((False, 0), (True, 1))
        elif sheet.fighter.h2h:
            hands = ((False, 0), (False, 1))
        else:
            hands = ((False, 0),)
        for off_hand, animation in hands:
            if not entity.alive or (results and results[-1]["defeated"]):
                break
            hits = min(self._multi_attack_hits(sheet),
                       combat.MAX_ATTACKS_PER_ROUND - len(results))
            if hits > 1:
                log.info("%s %s hand multi-attack: %d swings (DA=%d TA=%d QA=%d)",
                         self.addr, "off" if off_hand else "main", hits,
                         int(sheet.fighter.mods.get(mod.DOUBLE_ATTACK, 0)),
                         int(sheet.fighter.mods.get(mod.TRIPLE_ATTACK, 0)),
                         int(sheet.fighter.mods.get(mod.QUADRUPLE_ATTACK, 0)))
            for _ in range(hits):
                result = self._resolve_swing(entity, sheet, off_hand=off_hand,
                                             hp_left=hp_left, first_swing=not results,
                                             animation=animation)
                results.append(result)
                if result["defeated"]:
                    break
                if not result["miss"]:
                    hp_left = max(0, hp_left - result["damage"]
                                  - int(result.get("enspell_damage") or 0))
            # Zanshin: a miss is followed by one more swing with that hand, and while
            # Hasso is up a landed hit gets the same chance at a quarter of the rate.
            zanshin = max(0, int(sheet.fighter.mods.get(mod.ZANSHIN, 0)))
            last = results[-1] if results else None
            if (zanshin and last is not None and not last["defeated"]
                    and len(results) < combat.MAX_ATTACKS_PER_ROUND):
                chance = zanshin / 100.0
                if not last["miss"]:
                    chance = chance / 4.0 if self.has_effect(effects.HASSO) else 0.0
                if chance and self.world.rng.random() < chance:
                    extra = self._resolve_swing(entity, sheet, off_hand=off_hand,
                                                hp_left=hp_left, first_swing=False,
                                                animation=animation)
                    results.append(extra)
                    if not extra["miss"]:
                        hp_left = max(0, hp_left - extra["damage"]
                                      - int(extra.get("enspell_damage") or 0))
        self.queue_action(entity.id, results=results, broadcast=True)
        for result in results:
            self._apply_swing(entity, sheet, now, result)
        self.next_attack_at = now + sheet.attack_delay_ms / 1000.0

    def _multi_attack_hits(self, sheet) -> int:
        """Swings this hand gets from Double/Triple/Quadruple Attack, base hit included."""
        mods = sheet.fighter.mods
        return combat.multi_attack_hits(
            self.world.rng, double=int(mods.get(mod.DOUBLE_ATTACK, 0)),
            triple=int(mods.get(mod.TRIPLE_ATTACK, 0)),
            quadruple=int(mods.get(mod.QUADRUPLE_ATTACK, 0)))

    def _enspell_hit(self, entity, sheet, *, off_hand: bool = False,
                     first_swing: bool = True) -> dict | None:
        """Roll the active en-spell for one landed swing and advance its state.

        Tier I procs on every landed swing of the round, tier II only on the round's
        first swing, and Enlight/Endark decay by one point per hit.  The stored
        ``power`` means the cast-time base for tier I, the hidden round counter for
        tier II and the remaining charge for tier III, so it is written back here.
        """
        effect_id = 0
        for candidate in self.effect_state:
            if effects.is_enspell(candidate):
                effect_id = int(candidate)
        state = self.effect_state.get(effect_id)
        if effect_id <= 0 or state is None:
            return None
        tier = effects.enspell_tier(effect_id)
        element = effects.enspell_element(effect_id)
        if tier == 2 and not first_swing:
            return None
        skills, _base = self.effective_skills()
        if tier == 3:
            skill_id = packets.SKILL_DIVINE if element == 7 else packets.SKILL_DARK
        else:
            skill_id = packets.SKILL_ENHANCING
        skill = int(skills.get(skill_id, 0))
        bonus, percent = self._enspell_gear_bonus(sheet, off_hand=off_hand)
        merit = 0
        if tier in (1, 2) and int(self.char.get("main_job") or 0) == effects.RED_MAGE:
            # Red Mage group 2 "En-spell damage": five ranks, three points each.
            merit = int(self.merit_counts().get(0x0914, 0)) * 3
        composure = (tier in (1, 2) and 1 <= element <= 6
                     and int(self.char.get("main_job") or 0) == effects.RED_MAGE
                     and self.has_effect(effects.COMPOSURE))
        stored = int(state.get("power", 0))
        damage, following = combat.enspell_hit(
            tier=tier, skill=skill, element=element, potency=stored, counter=stored,
            bonus=bonus, percent=percent, merit=merit, composure=composure,
            target_mods=self.world.monster_debuff_mods(entity))
        if tier == 3 and following <= 0:
            # The last charge was just spent: the effect wears off after this hit.
            self.remove_effect(effect_id)
            self.queue.append(self.char_status())
        else:
            state["power"] = following
        return {"damage": int(damage), "element": element, "tier": tier}

    def _enspell_gear_bonus(self, sheet, *, off_hand: bool) -> tuple[int, int]:
        """(flat, percent) "Sword enhancement spell damage" for the swinging hand.

        Non-weapon gear applies to both hands, but a weapon's own line applies only to
        that weapon.  ``combat_mods`` is the whole outfit, so subtract the *other*
        main/sub item's line from the total; that is the rule LandSandBoat implements
        per hit.  ``equipped_item_mods`` is used rather than ``item_mods`` so a
        Dynamis-Divergence percent line on the other weapon (Crocea Mors path C) is
        excluded too.
        """
        mods = sheet.fighter.mods
        bonus = int(mods.get(mod.ENSPELL_DMG_BONUS, 0))
        percent = int(mods.get(mod.ENSPELL_DMG_PCT, 0))
        other_kind = stats.SLOT_MAIN if off_hand else stats.SLOT_SUB
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s equipped weapons unavailable: %s", self.addr, exc)
            weapons = {}
        item_id = int((weapons.get(other_kind) or {}).get("item_id") or 0)
        if item_id:
            try:
                other = self.world.service.equipped_item_mods(
                    int(self.char["id"]), item_id)
            except Exception as exc:
                log.warning("%s item %d mods unavailable: %s", self.addr, item_id, exc)
                other = {}
            bonus -= int(other.get(mod.ENSPELL_DMG_BONUS, 0))
            percent -= int(other.get(mod.ENSPELL_DMG_PCT, 0))
        return max(0, bonus), max(0, percent)

    def _resolve_swing(self, entity, sheet, *, off_hand: bool = False,
                       hp_left: int | None = None, first_swing: bool = True,
                       animation: int | None = None) -> dict:
        """Roll one hand of an attack round; 0 main hand, 1 off hand.

        ``animation`` overrides the result's sub-kind when the swing is not the sub
        weapon: a H2H left fist uses the main-hand fighter (off_hand False) but still
        needs animation 1, or the client plays only the right-hand punch.

        The en-spell is part of the same result: the additional-effect block carries
        its element and damage, and its damage counts towards whether this round kills.
        A hit that already drops the target does not also roll one.
        """
        miss, damage, critical = self.world.player_attack(self, entity, off_hand=off_hand)
        remaining = entity.hp if hp_left is None else int(hp_left)
        enspell = None
        if not miss and remaining - damage > 0:
            enspell = self._enspell_hit(entity, sheet, off_hand=off_hand,
                                        first_swing=first_swing)
        enspell_damage = int(enspell["damage"]) if enspell is not None else 0
        defeated = (not miss) and remaining - damage - enspell_damage <= 0
        result = {"damage": damage, "miss": miss, "critical": critical,
                  "defeated": defeated,
                  "animation": (1 if off_hand else 0) if animation is None else int(animation),
                  "off_hand": bool(off_hand), "enspell_damage": enspell_damage}
        if enspell is not None and enspell_damage > 0:
            result.update(add_effect=int(enspell["element"]), add_value=enspell_damage,
                          add_message=packets.MESSAGE_ADD_EFFECT_ADDITIONAL_DAMAGE)
        return result

    def _apply_swing(self, entity, sheet, now: float, result: dict) -> None:
        """Apply one resolved swing: hate, HP, TP and the kill after its action."""
        damage = int(result["damage"])
        miss = bool(result["miss"])
        # Swinging is the enmity that makes a mob fight back -- including a miss.
        self.world.add_damage_hate(entity, int(self.char["char_id"]), max(1, damage), now)
        if miss:
            return
        # Attacking breaks Sneak and Invisible, as it does in retail.
        for stealth in (effects.SNEAK, effects.INVISIBLE):
            if self.remove_effect(stealth):
                self.queue.append(self.char_status())
        self.world.wake_mob(entity)
        entity.hp = max(0, entity.hp - damage)
        # En-spell damage lands on the same swing, after the physical hit.  It is not a
        # second source of hate: retail's en-spell damage adds no enmity of its own.
        entity.hp = max(0, entity.hp - int(result.get("enspell_damage") or 0))
        self.queue_entity(entity, packets.SEND_HP)
        store_tp = int(sheet.fighter.mods.get(mod.STORETP, 0))
        # Each hand pays TP from its own weapon delay; a Double/Triple/Quadruple extra
        # swing pays the same as a normal hit with that hand.
        self.gain_tp(combat.tp_gain(
            sheet.tp_per_hit(off_hand=bool(result.get("off_hand"))), store_tp))
        self._samba_on_hit(damage)
        if result["defeated"]:
            self.world.kill_mob(self, entity, now)

    def say_from(self, name: str, text: str) -> None:
        self.queue.append(sub(0x017, packets.chat_std(name, text, self.zone, 0)))

    def open_shop(self, key: str, items: list[dict]) -> None:
        self.shop_key = key
        self.shop_items = list(items)
        self.queue.append(sub(0x03E, packets.shop_open(len(self.shop_items))))
        for offset in range(0, len(self.shop_items), 19):
            self.queue.append(sub(0x03C, packets.shop_list(self.shop_items[offset:offset + 19], offset)))

    def buy(self, p: bytes) -> None:
        if len(p) < 15 or not self.shop_items:
            return
        quantity, _shop_no, index, _property = struct.unpack_from("<IHHB", p, 4)
        quantity = max(1, min(int(quantity), 99))
        if index >= len(self.shop_items):
            self.say("That item is no longer for sale.")
            return
        stock = self.shop_items[index]
        item = self.world.service.item(int(stock["item_id"]))
        if item and int(item.get("rare") or 0):
            # A Rare item is one per character, and retail's check searches the
            # wardrobes and storage slips too.  Refuse before taking the gil rather
            # than letting add_item reject the sale afterwards.
            quantity = 1
            if self.world.service.owns_item(int(self.char["id"]), int(stock["item_id"])):
                self.say("You cannot possess another %s." % item["name"])
                return
        total = int(stock["price"]) * quantity
        if int(self.char.get("gil", 0)) < total:
            self.say("You do not have enough gil.")
            return
        charged = False
        try:
            self.world.service.set_gil(self.char["id"], int(self.char["gil"]) - total)
            charged = True
            self.world.service.add_item(self.char["id"], int(stock["item_id"]), quantity)
        except Exception as exc:
            if charged:
                try:
                    self.world.service.set_gil(self.char["id"], int(self.char["gil"]))
                except Exception:
                    log.exception("%s could not refund a failed purchase of item %d",
                                  getattr(self, "addr", "?"), int(stock["item_id"]))
            self.say("The purchase could not be completed: %s" % exc)
            return
        self.char["gil"] = int(self.char.get("gil", 0)) - total
        self.queue.append(sub(0x03F, packets.shop_buy(index, quantity)))
        self.refresh_inventory()
        self.say("You buy %s x%d for %d gil." % (item["name"] if item else stock["item_id"], quantity, total))

    def server_message(self, lang: int, stamp: int, offset: int) -> Msg:
        text = self.world.motd.encode("ascii", "replace") + b"\0"
        part = text[offset:offset + 236]
        return sub(0x04D, struct.pack("<BbBBiiii", 1 if offset == 0 else 2, 1, 1, lang,
                                      stamp or int(time.time()), len(text), offset, len(part)) + part)

    def blacklist(self) -> Msg:
        return sub(0x041, bytes(240) + struct.pack("<bbH", 3, 0, 0))

    def female(self) -> bool:
        return self.char["race"] in (2, 4, 6, 7)

    def looks(self) -> list[int]:
        c = self.char
        if self.style_locked():
            model = self._style_models()
            # Weapons are the exception to the locked look: a main/sub swap has to show
            # the piece that is actually equipped.  This is what makes a two-handed main
            # becoming a one-handed main plus a shield draw both new models instead of
            # keeping the old weapon (the shield used to show only because its locked
            # model was zero and fell through to the real gear below).  Armour and the
            # ranged slot stay locked.
            current = self._current_models()
            for kind in WEAPON_STYLE_SLOTS:
                model[kind] = current[kind]
            # A zero model would draw the naked default for that slot; fall back to the
            # real gear so a character saved before a slot was locked still looks whole.
            for kind in STYLE_SLOTS:
                if not model[kind]:
                    model[kind] = current[kind]
        else:
            model = self._current_models()
        return [character_design.raw_face(c) | (c["race"] << 8), model[4] + 0x1000,
                model[5] + 0x2000, model[6] + 0x3000, model[7] + 0x4000,
                model[8] + 0x5000, model[0] + 0x6000, model[1] + 0x7000,
                model[2] + 0x8000]

    def grap_list(self) -> Msg:
        return sub(0x051, struct.pack("<9H2x", *self.looks()))

    def apply_design(self, blueprint: dict) -> None:
        """Change race/face/hair/size live and repaint self and the other clients."""
        for key in ("race", "face", "hair", "size"):
            self.char[key] = int(blueprint[key])
        # 0x051 repaints the player's own grap list; 0x067 refreshes the level block;
        # 0x00D carries the gender/size bits and the model block other updates read;
        # 0x01B is the general-information block the client keeps for the status menu.
        self.queue += [self.grap_list(), self.char_sync(), self.char_update(), self.job_info()]
        self.world.refresh_player_appearance(self)
        log.info("%s design -> %s", self.addr, blueprint.get("label", "?"))

    def item_max(self) -> Msg:
        """Container capacities, with an empty cosmetic wardrobe left unavailable.

        Wardrobe 8 (container 16) is cosmetic-only and starts empty on this server.  The
        equipment window remembers the last storage the player picked; advertising an
        empty wardrobe lets it reopen on that bag, where every item row is blank because
        there is nothing to list.  A zero usable size makes the client skip the bag and
        fall back to Inventory.  The moment the wardrobe holds an item it is advertised
        normally again.
        """
        unavailable = ()
        try:
            if not any(int(item["container"]) == 16
                       for item in self.world.service.inventory(self.char["id"])):
                unavailable = (16,)
        except Exception as exc:
            log.warning("%s wardrobe check failed: %s", self.addr, exc)
        return sub(0x01C, packets.item_max(disabled=unavailable))

    def login_packet(self) -> Msg:
        c = self.char
        now = int(time.time())
        x, y, z, rot = self.pos
        b = bytearray(0x100)
        struct.pack_into("<IHBbfff", b, 0x00, c["char_id"], TARGID, 0, (int(rot) + 128) % 256 - 128, x, y, z)
        hpp = gauge_percent(c.get("hp_current", c["hp"]), c["hp"])
        struct.pack_into("<BBBB", b, 0x18, self.own_speed(), 40, hpp, 0)
        struct.pack_into("<I", b, 0x1C, (self.female() * 128 + (1 << c["size"])) << 8)
        struct.pack_into("<I", b, 0x24, 0x0100)
        struct.pack_into("<IIII", b, 0x2C, self.zone, 0, now, now - VANA_EPOCH + self.world.clock)
        struct.pack_into("<HH9H", b, 0x3C, 0, self.zone, *self.looks())
        music = self.world.zones.music_for(self.zone)
        struct.pack_into("<5H", b, 0x52, *music, 0xD4)
        moghouse = bool(int(c.get("moghouse", 0) or 0))
        struct.pack_into("<I", b, 0x7C, 1 if moghouse else 2)
        b[0x80:0x90] = cstr(c["name"], 16)
        struct.pack_into("<II", b, 0x9C, 3600, 60 * 360)
        if moghouse:
            b[0xA4] = 0                 # MyroomSubMapNumber: first floor
            struct.pack_into("<H", b, 0xA6, self.moghouse_model())  # MyroomMapNumber
            b[0xAA] = self.moghouse_city()  # MyRoomExitBit: this city's exit menu
            b[0xAB] = 0                 # MogZoneFlag
        else:
            struct.pack_into("<H", b, 0xA6, 0x01FF)
        b[0xAC:0xF0] = self.dancer()[:0x44]
        struct.pack_into("<I", b, 0xFC, 1)
        return sub(0x00A, b)

    def dancer(self) -> bytearray:
        c = self.char
        # GP_MYROOM_DANCER is 0x5C bytes in the packet; 0x01B extends it to 0x80.
        # The job and stat arrays start at 0x0C and 0x1C, not 0x10 and 0x20.
        b = bytearray(0x80)
        struct.pack_into("<HHBBBBI", b, 0, c["race"], character_design.raw_face(c),
                         c["main_job"], 0, c["size"], c["sub_job"], 0xFFFFFFFF)
        jobs = c.get("jobs") or {}
        # job_lev[16] covers WAR..BLU.  job_lev2 is 0x18 bytes copied from the whole
        # 24-entry job array, so the advanced jobs 17..22 live at job_lev2[16..21].
        for job in range(1, 17):
            level, _master = jobs.get(job, (0, 0))
            b[0x0C + job - 1] = max(0, min(99, int(level)))
        # job_lev2 is indexed by job number (not job-1).  BLU is 16 and the
        # advanced jobs are 17..22.
        for job in range(1, 23):
            level, master = jobs.get(job, (0, 0))
            b[0x44 + job] = max(0, min(99, int(level)))
            b[0x68 + job] = max(0, min(50, int(master)))
        b[0x64:0x68] = b"\xff\xff\xff\xff"  # job mastery flags: every job mastered
        # 0x60 can_thumbs_up_mentor, 0x61 mentor_rank and 0x62 mastery_rank sit just
        # before the flags.  The Profile page prints 0x62 as "Mastery Rank"; the Data
        # page writes the characters.mastery_rank column this reads.  Retail caps it
        # at 10 and wraps above that, so the byte is clamped here.
        b[0x62] = max(0, min(10, int(c.get("mastery_rank") or 0)))
        # The seven base attributes, same order as the 0x061 block.
        sheet = self.stat_sheet()
        base = sheet.base_attributes
        struct.pack_into("<7H", b, 0x1C, *[max(0, min(999, int(base.get(name, 0))))
                                           for name in ("str", "dex", "vit", "agi", "int", "mnd", "chr")])
        struct.pack_into("<ii", b, 0x38, c["hp"], c["mp"])
        b[0x40] = 1
        return b

    def job_info(self) -> Msg:
        # 0x01B carries the full GP_MYROOM_DANCER block plus mastery/encumbrance fields.
        return sub(0x01B, self.dancer())

    def job_points(self) -> Msg:
        # 0x063 miscdata type 5: 24 job entries of capacity/current/spent JP.
        # totalJpSpent >= 2100 is what gives the three job-master stars.
        b = bytearray(152)
        struct.pack_into("<HH", b, 0, 5, 156)
        b[4] = 1  # Job breaker access
        for job in range(1, 24):
            off = 8 + job * 6
            struct.pack_into("<HHH", b, off, 30000, 500, 2100)
        return sub(0x063, b)

    def job_points_detail(self) -> Msg:
        # 0x08D: 64 job-point category entries for the current job.  Max every
        # category to rank 20 so all gifts/skills are unlocked.
        b = bytearray(256)
        job = int(self.char["main_job"]) & 0x7FF
        for index in range(32):
            value = (index & 0x1F) | (job << 5) | (0 << 16) | (JOB_POINT_RANK << 26)
            struct.pack_into("<I", b, index * 4, value)
        return sub(0x08D, b)

    def party_member(self) -> Msg:
        c = self.char
        b = bytearray(0x24)
        # 0x00DF body: UniqueNo, Hp, Mp, Tp, ActIndex, Hpp, Mpp, Kind, MoghouseFlg, ZoneNo.
        # Tp sat at zero, which is why the TP bar never moved no matter how many swings landed.
        # Hpp/Mpp must divide by the maximum: a constant 100 draws the HP and MP bars full
        # no matter how much is missing, which is exactly what "capped early" looked like.
        hp, mp = int(c.get("hp_current", c["hp"])), int(c.get("mp_current", c.get("mp", 0)))
        hpp = gauge_percent(hp, c["hp"])
        mpp = gauge_percent(mp, c.get("mp", 0))
        struct.pack_into("<IIIIHBBBBH", b, 0, c["char_id"], hp, mp, int(c.get("tp", 0)),
                         TARGID, hpp, mpp, 0, 0, self.zone)
        struct.pack_into("<BBBB", b, 0x1C, c["main_job"], c["main_level"], c["sub_job"], c["sub_level"])
        return sub(0x0DF, b)

    def char_stats(self) -> Msg:
        c = self.char
        b = bytearray(0x6C)
        sheet = self.stat_sheet()
        level = int(c["main_level"])
        # 99 is the Master Level band: no EXP bar, the 0x64/0x68 Exemplar block instead.
        exp = 0 if level >= 99 else int(c.get("exp", 0)) & 0x7FFF
        exp_next = 0 if level >= 99 else int(c.get("exp_next", 1000)) & 0x7FFF
        struct.pack_into("<iiBBBBhh", b, 0, int(sheet.max_hp), int(sheet.max_mp),
                         c["main_job"], c["main_level"], c["sub_job"],
                         c["sub_level"], exp, exp_next)
        # 0x10 is the seven base attributes and 0x1E is the gear adjustment to each, both
        # signed 16-bit.  The client draws base and adjustment as separate columns, so a
        # stat of 120 with +40 of gear is packed as 120 and 40, not as 160.
        base = sheet.base_attributes
        total = sheet.attributes
        order = ("str", "dex", "vit", "agi", "int", "mnd", "chr")
        struct.pack_into("<7H", b, 0x10, *[max(0, min(999, int(base.get(name, 0))))
                                           for name in order])
        struct.pack_into("<7h", b, 0x1E, *[
            max(-999 + int(base.get(name, 0)), min(999 - int(base.get(name, 0)),
                                                   int(total.get(name, 0)) - int(base.get(name, 0))))
            for name in order])
        # 0x2C is Attack and Defense, which is what the character menu prints.
        struct.pack_into("<hh", b, 0x2C, int(sheet.attack), int(sheet.defense))
        # 0x30 is def_elem[8], the eight element orbs under Attack/Defense in the
        # equipment menu.  They are the character's elemental magic evasion -- the
        # "Fire+20" line on a tooltip -- and the client only draws what this packet
        # carries, so an unfilled block reads as zero for every element no matter what
        # the gear says.  The mods dict already holds gear, augments, traits, job
        # points, buffs and food merged, which is the same total retail's getMod()
        # reports.  Values are signed: Demon's Ring +1 is Light-20 Dark+13.
        struct.pack_into("<8h", b, 0x30, *[
            max(-32768, min(32767, int(sheet.fighter.mods.get(mod_id, 0))))
            for mod_id in mod.ELEMENTAL_MEVA])
        nation = int(c.get("nation") or 0)
        rank_column = ("rank_sandoria", "rank_bastok", "rank_windurst")[nation % 3]
        rank = max(1, min(10, int(c.get(rank_column) or 1)))
        rank_points = max(0, min(0xFFFF, int(c.get("rank_points") or 0)))
        struct.pack_into("<HHHH", b, 0x40, 0, rank, rank_points, self.zone)
        b[0x4C] = c["nation"]
        # 0x4E is the Superior equipment level.  Su5's equip gate is the 2,100-JP job
        # gift, and this server maxes every job's points, so the status page reads
        # Su5 instead of Su0.
        b[0x4E] = 5
        # 0x50/0x52/0x53 are the highest, main-hand and ranged item levels.  0x51 is
        # not an item level: the client prints 99 + this byte (XiPackets), so a full
        # iLv 119 set sends 20 here.  Sending 119 draws "iLv 218".
        b[0x50] = 119
        b[0x51] = 20
        b[0x52] = 119
        b[0x53] = 119
        # Master-level info for the current job.
        jobs = c.get("jobs") or {}
        main_entry = jobs.get(int(c["main_job"])) or (0, 0)
        main_master = int(main_entry[1]) if len(main_entry) > 1 else 0
        b[0x60] = c["main_job"] & 0xFF
        b[0x61] = max(0, min(MASTER_LEVEL_MAX, main_master))
        b[0x62] = 1
        struct.pack_into("<I", b, 0x64, max(0, int(c.get("exemplar_points") or 0)))
        # At Master Level 50 the HUD's "Next M.Level" is zero; below the cap it is the
        # 30,000-point bar to the next level.
        struct.pack_into("<I", b, 0x68, 0 if main_master >= MASTER_LEVEL_MAX
                         else EXEMPLAR_PER_LEVEL)
        return sub(0x061, b)

    def effective_skills(self) -> tuple[dict[int, int], dict[int, int]]:
        """(skill value after merits and gear, the job's own cap before them).

        Both the 0x062 skill menu and the Weapon Skills filter read this, so a WS
        requirement is checked against the same number the character sees.
        """
        c = self.char
        caps = dict(skills.caps_for(
            int(c["main_job"]), int(c["main_level"]),
            int(c.get("sub_job", 0)), int(c.get("sub_level", 0)),
            job_points.skill_bonus(int(c["main_job"]))))
        if not caps:
            caps = {skill_id: SKILL_CAP for skill_id in skills.SKILL_IDS}
        # Keep the job's own cap: blue is decided against it, not against the value
        # after merits and gear have pushed the number higher.
        base_caps = dict(caps)
        # Combat/magic skill merits add their value (2) per rank on top of the job cap.
        # The client's skill menu is populated from these numbers, so a capped Katana
        # (424) with 8 Katana Skill merits shows 440.
        counts = self.merit_counts()
        for merit_id, skill_id in merits.SKILL_MERITS.items():
            count = int(counts.get(int(merit_id), 0))
            entry = merits.MERITS.get(int(merit_id))
            if count > 0 and entry is not None:
                caps[int(skill_id)] = int(caps.get(int(skill_id), 0)) + count * int(entry[3])
        # Equipped gear adds its own skill bonuses (both dual-wielded weapons count).
        try:
            bonuses = self.world.service.equipped_skill_bonuses(int(c["id"]))
        except Exception as exc:
            log.warning("%s equipment skill bonuses unavailable: %s", self.addr, exc)
            bonuses = {}
        for skill_id, amount in bonuses.items():
            caps[int(skill_id)] = int(caps.get(int(skill_id), 0)) + int(amount)
        return caps, base_caps

    def refresh_vitals(self, sheet=None) -> None:
        """Recompute max HP/MP from the sheet and keep the stored row in step.

        HP and MP maxima are not a stored truth: they follow race, job, level, subjob and
        the HP/MP on the equipped gear.  Every path that can change any of those calls
        this, so ``char["hp"]`` stays the number the client is told.  A caller that has
        already built the sheet (the passive three-second tick) can hand it in and skip
        the second computation.
        """
        if sheet is None:
            try:
                sheet = self.stat_sheet()
            except Exception as exc:
                log.warning("%s stat sheet unavailable: %s", self.addr, exc)
                return
        hp, mp = max(1, int(sheet.max_hp)), max(0, int(sheet.max_mp))
        if int(self.char.get("hp", 0)) == hp and int(self.char.get("mp", 0)) == mp:
            return
        current_hp = min(max(0, int(self.char.get("hp_current", hp))), hp)
        current_mp = min(max(0, int(self.char.get("mp_current", mp))), mp)
        self.char.update(hp=hp, mp=mp, hp_current=current_hp, mp_current=current_mp)
        try:
            self.world.service.set_max_vitals(
                int(self.char["id"]), hp, mp, current_hp, current_mp)
        except Exception as exc:
            log.warning("%s max vitals save failed: %s", self.addr, exc)

    def job_traits(self) -> list[traits.Trait]:
        """The trait list for the current main/support job pair, cached per job pair.

        The cache key is the four job fields, so a job change, a support-job change or
        a level change rebuilds it; gear and merits cannot change traits.
        """
        main_level = int(self.char.get("main_level", 0) or 0)
        # A support job never exceeds half the main job's level; an old save can hold a
        # higher value, and the trait gate must follow the same rule the job menu uses.
        sub_level = min(int(self.char.get("sub_level", 0) or 0), main_level // 2)
        key = (int(self.char.get("main_job", 0) or 0), main_level,
               int(self.char.get("sub_job", 0) or 0), sub_level)
        if self._trait_cache is None or self._trait_cache[0] != key:
            self._trait_cache = (key, traits.active(*key))
        return self._trait_cache[1]

    def trait_mods(self) -> dict[int, int]:
        """The summed modifiers from every active trait."""
        result: dict[int, int] = {}
        for trait in self.job_traits():
            for mod_id, value in trait.mods:
                result[mod_id] = result.get(mod_id, 0) + int(value)
        return result

    def _stance_mods(self, trait_mods: dict[int, int]) -> list[tuple[str, dict[int, int]]]:
        """The stat rows a two-handed stance adds on top of its status effect.

        Hasso's effect is an icon only, and Desperate Blows is a trait rather than a
        buff, so neither is part of ``effect_state``.  Both are job-ability haste, and
        both only apply while a two-handed weapon is out.  Returning them as labelled
        rows lets ``stat_sources`` put them under Job abilities, which is also the
        source ``combat_mods`` sums: the launcher's report and the swing can never
        disagree about the ability-haste pool again.
        """
        if not (self.has_effect(effects.HASSO) or self.has_effect(effects.LAST_RESORT)):
            return []
        if self._main_weapon_skill() not in combat.TWO_HANDED_SKILLS:
            return []
        out: list[tuple[str, dict[int, int]]] = []
        if self.has_effect(effects.HASSO):
            # +STR (SAM level / 7, cap 14), +10 Accuracy and +10% job-ability haste
            # while a two-handed weapon is out.
            level = int(self.char.get("main_level", 1))
            out.append(("Hasso", {mod.STR: min(14, level // 7), mod.ACC: 10,
                                  mod.HASTE_ABILITY: 1000}))
        if self.has_effect(effects.LAST_RESORT):
            # Desperate Blows: the trait row is 1500 (15%) at DRK45; each merit rank
            # adds 2%.  It is ability haste, not equipment haste, so it belongs here.
            haste = max(0, int(trait_mods.get(mod.DESPERATE_BLOWS, 0)))
            if int(self.char.get("main_job", 0)) == 8:      # Dark Knight
                haste += 200 * int(self.merit_counts().get(0x09C6, 0))
            if haste:
                out.append(("Desperate Blows", {mod.HASTE_ABILITY: haste}))
        return out

    def stat_sources(self, detailed: bool = False) -> dict[str, dict]:
        """The modifier layers that make up ``combat_mods``, kept apart.

        ``combat_mods`` sums these rows, so a source the launcher shows cannot be one the
        swing omits.  ``detailed`` adds the per-equipped-item rows for the launcher's
        checkparam-style report; combat uses the cheaper aggregated gear query.
        """
        char = self.char
        main_job = int(char.get("main_job") or 0)
        status = list(self.status_effects)
        effects_state = {
            int(effect_id): {
                **state,
                "mods": {int(key): int(value)
                         for key, value in (state.get("mods") or {}).items()},
            }
            for effect_id, state in list(self.effect_state.items())
        }
        food = dict(self.food)
        food["mods"] = {int(key): int(value)
                        for key, value in (food.get("mods") or {}).items()}

        def add(target: dict[int, int], values) -> None:
            for mod_id, value in values.items():
                target[int(mod_id)] = target.get(int(mod_id), 0) + int(value)

        sources: dict[str, dict] = {}

        # --- gear -------------------------------------------------------------------------
        gear_mods: dict[int, int] = {}
        gear_entries: list[dict] = []
        if detailed:
            try:
                for row in self.world.service.equipped_slot_mods(int(char["id"])):
                    mods = {int(key): int(value)
                            for key, value in (row.get("mods") or {}).items()}
                    add(gear_mods, mods)
                    gear_entries.append({
                        "label": "%s — %s" % (
                            stat_report.EQUIP_KIND_LABELS.get(int(row.get("kind", -1)),
                                                            "Slot"),
                            row.get("name") or "Item"),
                        "mods": mods,
                        "augments": str(row.get("augments") or ""),
                        "kind": int(row.get("kind", -1)),
                        "item_id": int(row.get("item_id") or 0),
                    })
            except Exception as exc:
                log.warning("%s equipment rows unavailable: %s", self.addr, exc)
        if not gear_mods:
            try:
                gear_mods = dict(self.world.service.equipped_mods(int(char["id"])))
            except Exception as exc:
                log.warning("%s equipment stats unavailable: %s", self.addr, exc)
                gear_mods = {}
        sources["gear"] = {"label": stat_report.SOURCE_LABELS["gear"],
                           "mods": gear_mods, "entries": gear_entries}

        # --- job traits (JT) --------------------------------------------------------------
        trait_mods: dict[int, int] = {}
        trait_entries: list[dict] = []
        for trait in self.job_traits():
            mods = {int(mod_id): int(value) for mod_id, value in trait.mods}
            add(trait_mods, mods)
            trait_entries.append({"label": "%s (rank %d)" % (
                str(trait.name).title(), trait.rank), "mods": mods})
        sources["traits"] = {"label": stat_report.SOURCE_LABELS["traits"],
                             "mods": trait_mods, "entries": trait_entries}

        # --- job points and gifts --------------------------------------------------------
        # Permanent gifts and passive categories are always on; the ability-conditional
        # categories (a song or a job ability switching a job-point row on) stay in this
        # source too, so the JA row below names only an ability's own status effect.
        jp_mods = {int(key): int(value)
                   for key, value in job_points.combat_mods(main_job).items()}
        jp_entries: list[dict] = []
        if jp_mods:
            jp_entries.append({"label": stat_report.SOURCE_LABELS["job_points"],
                               "mods": jp_mods})
        for source in job_points.conditional_sources(main_job, status):
            mods = {int(key): int(value) for key, value in source.get("mods", {}).items()}
            if not mods:
                continue
            add(jp_mods, mods)
            jp_entries.append({"label": "%s (job point)" % (
                str(source.get("name") or "Job point")), "mods": mods})
        sources["job_points"] = {
            "label": stat_report.SOURCE_LABELS["job_points"],
            "mods": jp_mods,
            "entries": jp_entries,
        }

        # --- job abilities (JA) ----------------------------------------------------------
        ja_mods: dict[int, int] = {}
        ja_entries: list[dict] = []
        buff_mods: dict[int, int] = {}
        buff_entries: list[dict] = []
        for effect_id, state in effects_state.items():
            if effect_id == effects.FOOD:
                continue
            mods = dict(state.get("mods") or {})
            # Enlight and Endark give Accuracy/Attack equal to the charge they have left.
            if effect_id in (effects.ENLIGHT, effects.ENDARK):
                mod_id = mod.ACC if effect_id == effects.ENLIGHT else mod.ATT
                power = max(0, int(state.get("power") or 0))
                if power:
                    mods[mod_id] = int(mods.get(mod_id, 0)) + power
            if not mods:
                continue
            ability = job_points.ability_name_for_status(effect_id)
            label = ability or stat_report.effect_label(effect_id, state)
            entry = {"label": label, "mods": mods}
            if ability:
                add(ja_mods, mods)
                ja_entries.append(entry)
            else:
                add(buff_mods, mods)
                buff_entries.append(entry)
        # Hasso and Desperate Blows are stances whose status effect carries no stat
        # mods, so they are not in the effect rows above.  Put them in the same JA
        # source the report reads, not in ``combat_mods`` after the sources are
        # summed: otherwise the report's sheet (and its attack interval) silently
        # disagrees with the swing that actually happens.
        for label, stance_mods in self._stance_mods(trait_mods):
            add(ja_mods, stance_mods)
            ja_entries.append({"label": label, "mods": stance_mods})
        sources["job_abilities"] = {"label": stat_report.SOURCE_LABELS["job_abilities"],
                                    "mods": ja_mods, "entries": ja_entries}
        sources["buffs"] = {"label": stat_report.SOURCE_LABELS["buffs"],
                            "mods": buff_mods, "entries": buff_entries}

        # --- food -------------------------------------------------------------------------
        food_mods = dict(food["mods"])
        sources["food"] = {
            "label": stat_report.SOURCE_LABELS["food"],
            "mods": food_mods,
            "entries": ([{"label": food.get("name") or "Food", "mods": food_mods}]
                        if food_mods else []),
        }

        # --- merits -----------------------------------------------------------------------
        merit_mods: dict[int, int] = {}
        counts = self.merit_counts()
        for merit_id, mod_id in ((0x0040, mod.HP), (0x0042, mod.MP)):
            count = int(counts.get(merit_id, 0))
            entry = merits.MERITS.get(merit_id)
            if count > 0 and entry is not None:
                merit_mods[mod_id] = merit_mods.get(mod_id, 0) + count * int(entry[3])
        # Multi-attack merits belong to their own job and only count while that job's
        # trait is active: a Warrior's Double Attack Rate does not follow a Ninja main,
        # and a support-job Warrior keeps only the trait itself.
        for merit_id, job, mod_id in ((0x0188, 1, mod.DOUBLE_ATTACK),
                                      (0x02c8, 6, mod.TRIPLE_ATTACK),
                                      (0x0444, 12, mod.STORETP)):
            if main_job != job or not trait_mods.get(mod_id):
                continue
            count = int(counts.get(merit_id, 0))
            entry = merits.MERITS.get(merit_id)
            if count > 0 and entry is not None:
                merit_mods[mod_id] = merit_mods.get(mod_id, 0) + count * int(entry[3])
        sources["merits"] = {
            "label": stat_report.SOURCE_LABELS["merits"],
            "mods": merit_mods,
            "entries": ([{"label": stat_report.SOURCE_LABELS["merits"],
                          "mods": merit_mods}] if merit_mods else []),
        }
        return sources

    def combat_mods(self) -> dict[int, int]:
        """Gear, job-trait, buff, food, stance and merit modifiers, merged.

        Traits use the same modifier ids as gear, so adding them here means every stat
        the sheet already derives (Attack, Defense, Accuracy, Evasion, maximum HP/MP and
        the damage-taken family) sees them.  If the equipment query fails the traits are
        still applied rather than losing the passives as well.  Every spell that reads
        ``mods`` -- damage, healing, duration, potency -- sees this same merged dict.

        This is a plain sum of :meth:`stat_sources`; Hasso and Desperate Blows are rows
        inside that source, not additions here, so the launcher's report is built from
        exactly the same modifiers.
        """
        mods: dict[int, int] = {}
        for source in self.stat_sources().values():
            for mod_id, value in (source.get("mods") or {}).items():
                mods[int(mod_id)] = mods.get(int(mod_id), 0) + int(value)
        return mods

    def _main_weapon_skill(self) -> int:
        """The equipped main weapon's skill id (0 when the query fails)."""
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
        except Exception:
            return 0
        return int((weapons.get(0) or {}).get("skill") or 0)

    def stat_sheet(self, mods: dict[int, int] | None = None):
        """The character's combat stats: base attributes, gear, Attack, Defense, Acc, Eva.

        Built fresh on every call.  It is two indexed queries over the equipped set plus
        some arithmetic, and building it beats caching it: the cache would have to be
        invalidated by equipment, level, merits and gear skill bonuses, and a stale stat
        sheet is a bug that shows up as mysterious damage.  The report passes in the
        merged source dict so its sheet is built from exactly the rows it displays.
        """
        if mods is None:
            mods = self.combat_mods()
        weapons: dict[int, dict] = {}
        try:
            weapons = self.world.service.equipped_weapons(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s equipped weapons unavailable: %s", self.addr, exc)

        def weapon_of(kind: int):
            row = weapons.get(kind)
            if not row or not int(row.get("item_id") or 0):
                return None
            return stats.Weapon(item_id=int(row["item_id"]),
                                skill=int(row.get("skill") or 0),
                                dmg=int(row.get("dmg") or 0),
                                delay=int(row.get("delay") or 0),
                                ilvl_skill=int(row.get("ilvl_skill") or 0),
                                item_level=int(row.get("item_level") or 0))

        skill_values, _base = self.effective_skills()
        sub_row = weapons.get(stats.SLOT_SUB) or {}
        return stats.build_character(
            self.char, mods, skill_values,
            weapon_of(stats.SLOT_MAIN), weapon_of(stats.SLOT_SUB),
            shield_size=int(sub_row.get("shield_size") or 0),
            # Two one-handed weapons both swing; the Dual Wield trait only lowers
            # the round's delay (mod.DUAL_WIELD is inside ``mods`` already).
            ranged_weapon=weapon_of(stats.SLOT_RANGED),
            ammo=weapon_of(stats.SLOT_AMMO))

    def stat_report(self) -> dict:
        """The live checkparam-style sheet: final stats with every source behind them.

        The launcher polls this through the HTTP API.  It uses the same source rows as
        ``combat_mods`` and builds the sheet from their merged result, so the numbers the
        player reads are the ones this session swings, casts and takes damage with.
        """
        char = dict(self.char)
        sources = self.stat_sources(detailed=True)
        mods: dict[int, int] = {}
        for source in sources.values():
            for mod_id, value in (source.get("mods") or {}).items():
                mods[int(mod_id)] = mods.get(int(mod_id), 0) + int(value)
        sheet = self.stat_sheet(mods=mods)
        race = int(char.get("race", 1) or 1)
        main_job = int(char.get("main_job", 1) or 1)
        main_level = int(char.get("main_level", 1) or 1)
        sub_job = int(char.get("sub_job", 0) or 0)
        sub_level = int(char.get("sub_level", 0) or 0)
        base_attributes = base_stats.base_stats(
            race, main_job, main_level, sub_job, sub_level)
        base_hp = base_stats.base_hp(race, main_job, main_level, sub_job, sub_level)
        base_mp = base_stats.base_mp(race, main_job, main_level, sub_job, sub_level)
        return stat_report.build_report(
            character=char,
            sources=sources,
            mods=mods,
            sheet=sheet,
            base_attributes=base_attributes,
            base_hp=base_hp,
            base_mp=base_mp,
            food=dict(self.food),
            updated=time.time(),
        )

    def char_skills(self) -> Msg:
        # 0x062 CLISTATUS2: 31 command recasts (uint32), then 64 skill values (uint16).
        # 0x8000 is the client's "capped" bit: it draws a capped skill in blue.  The
        # same bit on a slot with no name hidden (the automaton skills) keeps its row
        # out of the menu.  The low 15 bits are the value.
        c = self.char
        body = bytearray(252)
        for skill_id in range(64):
            struct.pack_into("<H", body, 124 + skill_id * 2, 0x8000)
        # Crafting and fishing travel in slots 48-59.  The stored value is the base
        # skill the trainer raises; 0x8000 is the client's capped (blue) bit.
        try:
            crafts = {int(row["skill_id"]): int(row["value"])
                      for row in self.world.service.crafts_for_character(int(self.char["id"]))}
        except Exception as exc:
            log.warning("%s crafting skills unavailable: %s", self.addr, exc)
            crafts = {}
        for skill_id in range(48, 60):
            value = max(0, min(0x7FFF, crafts.get(skill_id, 0)))
            if value >= 100:
                value |= 0x8000
            struct.pack_into("<H", body, 124 + skill_id * 2, value)
        caps, base_caps = self.effective_skills()
        # Every skill the client has a name for gets a row, even at zero -- a job with no
        # rank in Great Sword still lists Great Sword 0, it just cannot raise it.
        for skill_id in skills.SKILL_IDS:
            skill_id = int(skill_id)
            value = max(0, min(0x7FFF, int(caps.get(skill_id, 0))))
            base = int(base_caps.get(skill_id, 0))
            if base > 0 and value >= base:
                value |= 0x8000
            struct.pack_into("<H", body, 124 + skill_id * 2, value)
        return sub(0x062, body)

    def char_feats(self) -> Msg:
        """0x0AB FEAT_DATA: the first 160 job abilities as a 20-byte bitmap.

        The client keeps a second, smaller ability table behind this packet (the
        ``feat`` getter checks its own "data arrived" byte).  The Job Abilities menu uses
        it for the original jobs, so 0x0AC's 512-bit block alone is not enough.  IDs
        above 159 (merit and master-level abilities) still travel in 0x0AC.
        """
        bits = bytearray(20)
        ja_ids = self._job_ability_ids()
        for ja_id in ja_ids:
            ja_id = int(ja_id)
            if 0 < ja_id < 160:
                bits[ja_id >> 3] |= 1 << (ja_id & 7)
        return sub(0x0AB, bytes(bits))

    def char_commands(self) -> Msg:
        """0x1A5: one incremental command-bit update, kind 1 (commands).

        Body: {action 1, kind 1, byte offset LE16, byte length LE16, bits}.  Offset 64
        is the start of the Job Abilities block in the 224-byte command table.  Retail
        uses this packet for post-retail ids; Fanxi sends the current job block here too
        so a client that only refreshes a submenu on an incremental update sees it.
        """
        bits = bytearray(64)
        ja_ids = self._job_ability_ids()
        for ja_id in ja_ids:
            ja_id = int(ja_id)
            if 0 < ja_id < 512:
                bits[ja_id >> 3] |= 1 << (ja_id & 7)
        return sub(0x1A5, struct.pack("<BBHH", 1, 1, 64, len(bits)) + bytes(bits))

    def equipped_weapon_skills(self) -> list[int]:
        """The weapon skill ids the equipped weapon(s) can use right now.

        Retail's list is the equipped main weapon's skill type (or hand-to-hand when
        nothing is held) plus the ranged weapon for archery/marksmanship.  Within that
        type, a skill is listed only when its skill_level requirement is at or below the
        character's value; skill_level 0 (quested/relic/empyrean/aeonic) is offered once
        the weapon skill is mastered.  This is what keeps every weapon skill in the game
        out of the menu.  Campaign Battle skills are the exception: they need a Campaign
        weapon and a Campaign zone, so they are dropped even though the import gives
        them skill_level 0.

        The Prime weapons' own skills are not learned from a skill value: the weapon
        carries "Adds weapon skill" (item_mods 355), so the skill is usable only while
        that item is equipped.  Those rows have a negative skill_level, which the
        skill-type filter above skips; this adds the ones the current outfit grants.

        Weapon skills that retail restricts to a main job (the relic/mythic/empyrean
        rows and the merit weapon skills) are filtered by ``weapon_skill_jobs``.  The
        skill value alone would otherwise offer a Corsair every Sword and Marksmanship
        skill in the game once the weapon skill is mastered.
        """
        try:
            caps, _base = self.effective_skills()
        except Exception as exc:
            log.warning("%s skill table unavailable: %s", self.addr, exc)
            return []
        ids: set[int] = set()

        def add(skill_id: int) -> None:
            value = int(caps.get(int(skill_id), 0))
            if value <= 0:
                return
            try:
                ids.update(self.world.service.weapon_skill_ids_for(int(skill_id), value))
            except Exception as exc:
                log.warning("%s weapon skill list for skill %d unavailable: %s",
                            self.addr, int(skill_id), exc)

        main = self.equipped.get(0)
        if main:
            skill = self.world.service.item_skill(int(main[2]))
            if skill > 0:
                add(skill)
        else:
            add(1)  # unarmed: hand-to-hand
        ranged = self.equipped.get(2)
        if ranged:
            skill = self.world.service.item_skill(int(ranged[2]))
            # Throwing weapon skills are not in the client's weapon skill table.
            if skill in (25, 26):
                add(skill)
        # Item-granted skills (the Prime weapons' "Adds weapon skill").  Only rows the
        # table marks with a negative skill_level belong here: a relic weapon's 355
        # value names a skill that is also quest-unlocked, and that one is already in
        # the skill-type list above.
        try:
            granted = self.world.service.equipped_weapon_skill_grants(int(self.char["id"]))
        except Exception as exc:
            log.warning("%s equipped weapon skill grants unavailable: %s", self.addr, exc)
            granted = set()
        for ws_id in granted:
            try:
                row = self.world.service.weaponskill(int(ws_id))
            except Exception as exc:
                log.warning("%s granted weapon skill %d unavailable: %s",
                            self.addr, int(ws_id), exc)
                continue
            if row is not None and int(row.get("skill_level", 0)) < 0:
                ids.add(int(ws_id))
        # Campaign Battle skills need a Campaign weapon and a Campaign zone.  The data
        # import gives them skill_level 0 like a quested skill, which would otherwise
        # advertise Uriel Blade, Glory Slash and Tartarus Torpor at 350 skill.
        main_job = int(self.char.get("main_job") or 0)
        return sorted(
            ws_id for ws_id in ids
            if not self._is_campaign_weapon_skill(ws_id)
            and weapon_skill_jobs.allowed(ws_id, main_job))

    def _is_campaign_weapon_skill(self, ws_id: int) -> bool:
        try:
            row = self.world.service.weaponskill(int(ws_id))
        except Exception:
            return False
        return row is not None and weapon_skill_effects.is_campaign_only(str(row["name"]))

    def char_abilities(self) -> Msg:
        """0x0AC COMMAND_DATA: the weapon skills and job abilities the client may list.

        The first block carries only the equipped weapon's skills that the character's
        skill value qualifies for (``equipped_weapon_skills``); the second carries the
        main and sub job's abilities from ``job_abilities``.  The 2025-07-03 client's menu
        is not built from this bitmap directly: it keeps a saved command-id list.  host64
        rebuilds that list from each 0x0AC packet (``host/addons/hooks.c``), so the packet
        is also re-sent after the 0x061 "stats please" reply, on short timers, after
        equipment changes and from ``//abilities``.
        """
        try:
            ws_ids = self.equipped_weapon_skills()
        except Exception as exc:
            log.warning("%s weapon skill list unavailable: %s", self.addr, exc)
            ws_ids = ()
        ja_ids = self._job_ability_ids()
        trait_ids = [trait.id for trait in self.job_traits()]
        return sub(0x0AC, command_bits(ws_ids, ja_ids, trait_ids))

    def abil_recast(self) -> Msg:
        """0x119: 31 ability recast slots (8 bytes each) + the mount recast pair.

        A slot is {timer u16, calc1 u8, recastId u8, calc2 u16, pad u16}; slot 0 is the
        2-hour edge case, so ordinary abilities start at slot 1.  The client matches a
        slot to an ability by its recast id from the command table, not by ability id.

        Every ability the character knows gets a slot, even when it is ready (timer 0).
        That fills the client's ``player_t.AbilityInfo`` array (verified in client memory)
        and is what lets the recast/ability panel show entries; a packet with only the
        running timers leaves every ready ability out of the table.
        """
        body = bytearray(256)
        now = time.time()
        slot = 1
        seen: set[int] = set()
        try:
            abilities = self.world.service.job_abilities(
                int(self.char.get("main_job", 0)), int(self.char.get("main_level", 1)),
                int(self.char.get("sub_job", 0)), int(self.char.get("sub_level", 0)))
        except Exception as exc:
            log.warning("%s job ability recasts unavailable: %s", self.addr, exc)
            abilities = []
        abilities = [row for row in abilities
                     if self._merit_ability_allowed(int(row["id"]))]
        # Slot 0 is retail's two-hour ("Special") recast: the current main job's
        # one-hour ability (recast id 0).  A ready one is still a zero timer rather
        # than an absent row.  The per-ability cooldowns live above the byte-sized
        # ordinary recast ids, so changing jobs does not carry the last job's timer.
        special_id = next(
            (int(row["id"]) for row in abilities
             if int(row.get("recast_id") or 0) == 0
             and int(row.get("recast") or 0) > 0), 0)
        special_ready = float(self.ability_recasts.get(
            TWO_HOUR_RECAST_BASE + special_id, 0.0)) if special_id else 0.0
        special_left = int(special_ready - now + 0.999) if special_ready > now else 0
        struct.pack_into("<HBBHH", body, 0, max(0, special_left), 0, 0, 0, 0)
        for ability in abilities:
            recast_id = int(ability.get("recast_id") or 0)
            if recast_id <= 0 or recast_id > 0xFF or recast_id in seen:
                continue
            seen.add(recast_id)
            remaining = int(self.ability_recasts.get(recast_id, 0.0) - now + 0.999)
            struct.pack_into("<HBBHH", body, slot * 8, max(0, remaining), 0,
                             recast_id, 0, 0)
            slot += 1
            if slot > 30:
                break
        # An ability used from a job the character has since left still needs its timer.
        for recast_id, ready_at in sorted(self.ability_recasts.items()):
            remaining = int(ready_at - now + 0.999)
            if remaining <= 0 or int(recast_id) in seen or not 0 < int(recast_id) <= 0xFF:
                continue
            if slot > 30:
                break
            struct.pack_into("<HBBHH", body, slot * 8, remaining, 0,
                             int(recast_id) & 0xFF, 0, 0)
            slot += 1
        return sub(0x119, body)

    def merits(self) -> Msg:
        # 0x063 miscdata type 2 (merits), 12-byte payload:
        #   +0 type, +2 unknown, +4 limit points,
        #   +6 merit points (7 bits) | blu bonus:6 | canUseMeritMode:1 | xpCapped:1 | meritModeEnabled:1,
        #   +8 max merit points.
        # The Maximum Merit Points merit raises the byte at +8.  The client's current
        # pool is a 7-bit field, so it tops out at 127 even when the cap is higher.
        b = bytearray(12)
        level = int(self.char.get("main_level", 1))
        eligible = 1 if level >= 75 else 0
        max_points = self.merit_max_points()
        merit_points = max(0, min(127, max_points, int(self.char.get("merit_points", max_points) or 0)))
        limit_points = max(0, min(0xFFFF, int(self.char.get("limit_points", 0) or 0)))
        mode = 1 if int(self.char.get("merit_mode", 1)) else 0
        merit_mode = eligible and mode
        flags = (merit_points & 0x7F) | (eligible << 13) | (merit_mode << 14) | (merit_mode << 15)
        struct.pack_into("<HHHH", b, 0, 2, 16, limit_points, flags)
        b[8] = max_points
        return sub(0x063, b)

    def merit_max_points(self) -> int:
        """Base cap plus one per Maximum Merit Points merit (0x0044, value 1)."""
        return min(255, 127 + max(0, int(self.merit_counts().get(0x0044, 0))))

    def merit_point_cap(self) -> int:
        """The pool the server stores: the raised cap, even above the client's 7-bit display."""
        return self.merit_max_points()

    def merit_counts(self) -> dict[int, int]:
        """Merit id -> upgrades bought, cached for the session."""
        counts = getattr(self, "_merit_counts", None)
        if counts is None:
            try:
                counts = self.world.service.merits_for_character(int(self.char["id"]))
            except Exception as exc:
                log.warning("%s merit list unavailable: %s", self.addr, exc)
                counts = {}
            self._merit_counts = counts
        return counts

    def merit_list(self) -> list[Msg]:
        """0x08C: every merit entry, at most 61 per packet.

        The client needs an entry's `next` cost before it will let the row be
        selected, so unspent merits are sent with count 0 and their first cost.
        Sending an empty block (or only the spent merits) left the menu read-only.
        """
        counts = self.merit_counts()
        entries = [(int(mid), max(0, int(counts.get(int(mid), 0))))
                   for mid in sorted(merits.MERITS)]
        packets_out: list[Msg] = []
        for start in range(0, len(entries), 61):
            chunk = entries[start:start + 61]
            body = bytearray(struct.pack("<HH", len(chunk), 0))
            for merit_id, count in chunk:
                body += struct.pack("<HBB", merit_id, merits.next_cost(merit_id, count), count)
            body += bytes(4)
            packets_out.append(sub(0x08C, bytes(body)))
        return packets_out

    def merit_edit(self, p: bytes) -> None:
        """C2S 0x0BE: change EXP/limit mode, or raise/lower one merit."""
        if len(p) < 12:
            return
        kind, param1 = int(p[4]), int(p[5])
        param2 = struct.unpack_from("<H", p, 6)[0]
        param3 = struct.unpack_from("<I", p, 8)[0]
        log.info("%s merit kind=%d param1=%d param2=%#x param3=%#x",
                 self.addr, kind, param1, param2, param3)

        if kind == 2:  # EXP mode (0) / Limit Points mode (1)
            mode = 1 if param1 else 0
            self.char["merit_mode"] = mode
            try:
                self.world.service.set_merit_mode(int(self.char["id"]), mode)
            except Exception as exc:
                log.warning("%s merit mode save failed: %s", self.addr, exc)
            self.queue += [self.merits(), self.monstrosity()]
            return

        if kind != 3:  # 1 is unused
            return
        # The client sends the merit DAT index divided by two (ids are even).
        merit_id = (int(param2) << 1) & 0xFFFF
        if merit_id not in merits.MERITS:
            merit_id = int(param2)  # be liberal if a build sends the id itself
        entry = merits.MERITS.get(merit_id)
        if entry is None:
            return
        category_id, cost_key, max_upgrades, value = entry
        costs = merits.COSTS[cost_key]
        counts = dict(self.merit_counts())
        count = max(0, int(counts.get(merit_id, 0)))
        points = max(0, min(self.merit_point_cap(), int(self.char.get("merit_points", 0) or 0)))

        if param1:  # raise
            if count >= max_upgrades:
                return
            cost = int(costs[min(count, len(costs) - 1)])
            if points < cost:
                return
            total = sum(int(counts.get(mid, 0)) for mid, other in merits.MERITS.items()
                        if other[0] == category_id)
            if total >= int(merits.CATEGORY_MAX.get(category_id, 0)):
                return
            points -= cost
            count += 1
            message = 380  # MeritIncrease
            delta = int(value)
        else:  # lower
            if count <= 0:
                return
            points = min(self.merit_point_cap(), points + int(costs[max(0, count - 1)]))
            count -= 1
            message = 381  # MeritDecrease
            delta = -int(value)

        counts[merit_id] = count
        self._merit_counts = counts
        self.char["merit_points"] = points
        try:
            self.world.service.save_merit(int(self.char["id"]), merit_id, count)
            self.world.service.set_merit_points(int(self.char["id"]), points)
        except Exception as exc:
            log.warning("%s merit save failed: %s", self.addr, exc)
        self._apply_merit_vitals(merit_id, delta)

        # 0x08C acknowledges the one changed merit.  When it drops back to zero the
        # client clears it if the entry's low bit is set (the index becomes id + 1).
        index = merit_id | (1 if count == 0 else 0)
        body = bytearray(struct.pack("<HH", 1, 0))
        body += struct.pack("<HBB", index, merits.next_cost(merit_id, count), count)
        body += bytes(4)
        self.queue.append(sub(0x08C, bytes(body)))
        me = int(self.char["char_id"])
        self.queue += [self.merits(),
                       sub(0x029, packets.battle_message(
                           me, me, TARGID, TARGID, int(param2), count, message)),
                       self.char_stats(), self.char_status(), self.party_member()]
        if int(merit_id) in merits.SCH_GROUP2_ABILITIES.values():
            # A group-2 ability appears or disappears from the Abilities menu with
            # its first/last rank, so the command tables have to be rebuilt now.
            self.queue += [self.char_abilities(), self.char_commands()]

    def _apply_merit_vitals(self, merit_id: int, delta: int) -> None:
        """Max HP/MP merits change the character's own max, not just a menu number."""
        if merit_id not in (0x0040, 0x0042) or not delta:
            return
        max_key = "hp" if merit_id == 0x0040 else "mp"
        current_key = "hp_current" if merit_id == 0x0040 else "mp_current"
        old_max = max(1, int(self.char.get(max_key, 1) or 1))
        new_max = max(1, old_max + int(delta))
        current = int(self.char.get(current_key, old_max) or 0)
        if delta > 0:
            current += int(delta)
        current = max(0, min(new_max, current))
        self.char[max_key] = new_max
        self.char[current_key] = current
        try:
            self.world.service.set_max_vitals(
                int(self.char["id"]),
                new_max if merit_id == 0x0040 else int(self.char.get("hp", 1)),
                new_max if merit_id == 0x0042 else int(self.char.get("mp", 0)),
                current if merit_id == 0x0040 else int(self.char.get("hp_current", 1)),
                current if merit_id == 0x0042 else int(self.char.get("mp_current", 0)))
        except Exception as exc:
            log.warning("%s merit vitals save failed: %s", self.addr, exc)

    def monstrosity(self) -> Msg:
        # 0x063 miscdata type 3 (monstrosity part 1), 216-byte payload.
        b = bytearray(216)
        struct.pack_into("<HH", b, 0, 3, 220)
        return sub(0x063, b)

    def effect_mod_total(self, mod_id: int) -> int:
        """The summed value of one modifier across the active status effects.

        Only the roll path needs this today, and it must not build a full stat sheet:
        ``char_status`` is sent on every gear swap and every buff change.
        """
        total = 0
        for state in self.effect_state.values():
            total += int((state.get("mods") or {}).get(int(mod_id), 0) or 0)
        return total

    def own_speed(self) -> int:
        """The speed byte the client gets, with Bolter's Roll applied.

        Bolter's Roll is additive movement speed after the normal multipliers and
        caps at +60%; the client reads the byte from 0x037 Flags1 and the 0x00D
        General block, so both use this value.
        """
        base = max(1, int(self.char.get("speed", 50) or 50))
        percent = max(0, min(60, self.effect_mod_total(
            mod.MOVE_SPEED_BOLTERS_ROLL)))
        return max(1, min(255, base + base * percent // 100))

    def char_status(self) -> Msg:
        c = self.char
        # 0x78 total: the 0x60-byte packet retail has always sent, plus the fields the
        # client grew in later updates.  The mount block lives at the end of those
        # (mount_id at body 0x6F, total 0x73); a shorter packet cannot carry it, and the
        # untouched extension bytes are zeros, which every one of those fields reads as
        # its default.
        b = bytearray(0x74)
        # 0xFF means "no status effect" in every slot.  A zeroed slot is status effect 0,
        # which the client treats as an active effect (and locks the character).
        b[0:32] = b"\xff" * 32
        # Slots are the low byte of the buff id; its top two bits sit in a 2-bit mask at
        # 0x48, four slots to a byte.  The client draws one icon per slot.
        for slot, effect in enumerate(self.status_effects[:32]):
            # The icon can differ from the effect id.  Utsusemi's icon is also its
            # shadow count (66/444/445/446), so it is derived from the effect's power
            # rather than stored once when the spell lands.
            state = self.effect_state.get(int(effect))
            effect = effects.icon_for(
                int(effect),
                int(state.get("icon", 0)) if state else 0,
                int(state.get("power", 0)) if state else 0)
            effect = effect & 0x3FF
            b[slot] = effect & 0xFF
            shift = 2 * (slot % 4)
            mask = 0x48 + slot // 4
            b[mask] = (b[mask] & ~(3 << shift)) | (((effect >> 8) & 3) << shift)
        hp = int(c["hp"])
        hpp = gauge_percent(c.get("hp_current", hp), hp)
        ridden = mounts.by_id(self.mount_id)
        if ridden is not None and mounts.MOUNTED_EFFECT not in self.status_effects[:32]:
            # The client knows a rider by the Mounted status effect (252), not by the
            # mount id alone: put it in the first icon slot that is free.  It is a packet
            # effect only, not a real buff — no timer, no icon, nothing to wear off.
            for slot in range(32):
                if b[slot] == 0xFF and ((b[0x48 + slot // 4] >> (2 * (slot % 4))) & 3) == 0:
                    b[slot] = mounts.MOUNTED_EFFECT & 0xFF
                    break
        # Flags0: Gender in bit 8, GraphSize in bits 11-12, Chocobo_Index in bits 13-15
        # (1 is the ordinary chocobo seat; it is what tells mount 0 apart from on foot),
        # hpp in bits 16-23.
        chocobo_index = ridden.chocobo_index() if ridden else 0
        flags0 = ((self.female() << 8) | ((c["size"] & 3) << 11)
                  | ((chocobo_index & 7) << 13) | (hpp << 16))
        flags1 = (self.own_speed() & 0xFFF) | (40 << 17)
        struct.pack_into("<III", b, 0x20, c["char_id"], flags0, flags1)
        struct.pack_into("<II", b, 0x38, 60 * 360, int(time.time()) - VANA_EPOCH + self.world.clock + 360)
        b[0x54] = 0x10
        # Mog Wardrobes 3-8 are gated on this byte, not on the 0x01C capacities: the client
        # only offers (and only lists) a paid wardrobe whose bit is set here.  Leaving it
        # zero made the equipment window treat Wardrobes 3-8 as unavailable and draw their
        # items blank, while Wardrobes 1-2 (not gated) listed normally.  Windower reads the
        # same bits for its ...get_items().enabled.  0x01 = Wardrobe 3, 0x02 = 4, 0x08 = 5,
        # 0x10 = 6, 0x20 = 7, 0x40 = 8; 0x04 is not a wardrobe.
        b[0x5C] = 0x7B
        # server_status (0x2C) is the character's animation, the very byte 0x00D carries at
        # 0x1B: the mount when riding, 1 while the weapon is drawn, else 0.  It used to be
        # 0 on foot, which sheathed an engaged player's weapon on every packet - the gear
        # swap's own 0x037 killed the stance its 0x00D had just drawn.
        b[0x2C] = self.own_animation() & 0xFF
        # mount_id: the client's mount id, 0 while on foot.  A mount 0 (chocobo) ride is
        # told apart by Chocobo_Index above, which is why this byte alone works.
        b[0x6F] = (ridden.id if ridden else 0) & 0xFF
        return sub(0x037, b)

    def status_icons(self) -> Msg:
        """0x063 miscdata type 9: the bar's icons again, each with its timer.

        The client counts an icon down from the Vanadiel timestamp in this packet; 0x037
        only carries the ids.  Without it the icons draw but every timer stays blank, even
        with Config > Misc > Timer Display on.  The slots line up with ``char_status()``
        slot for slot, and the timestamp is Vanadiel seconds * 60, as retail sends them
        (0x7FFFFFFF means "no timer" for an effect that never expires).
        """
        b = bytearray(196)
        struct.pack_into("<HH", b, 0, 9, 196)
        for slot in range(32):
            struct.pack_into("<H", b, 4 + slot * 2, STATUS_ICON_NONE)
            struct.pack_into("<I", b, 68 + slot * 4, STATUS_ICON_NO_TIMER)
        now = time.time()
        vana = int(now) - VANA_EPOCH + int(self.world.clock)
        for slot, effect in enumerate(self.status_effects[:32]):
            state = self.effect_state.get(int(effect))
            icon = effects.icon_for(
                int(effect),
                int(state.get("icon", 0)) if state else 0,
                int(state.get("power", 0)) if state else 0) & 0x3FF
            struct.pack_into("<H", b, 4 + slot * 2, icon)
            until = float(state.get("until") or 0.0) if state else 0.0
            if until > 0:
                remaining = max(0, int(until - now))
                struct.pack_into("<I", b, 68 + slot * 4,
                                 ((vana + remaining) * 60) & 0xFFFFFFFF)
        return sub(0x063, b)

    def own_animation(self) -> int:
        """This character's own animation byte, as the client is told it.

        The same value rides two packets: the self ``0x00D`` at body ``0x1B`` and
        ``0x037``'s ``server_status`` at body ``0x2C``.  It has to be the same number in
        both, because the client reads it as the local player's pose and applies each
        packet as it arrives: a status packet that said 0 while the character was engaged
        sheathed the weapon, and the next stance refresh (``0x00D`` = 1) drew it again.
        Every gear swap sends a ``0x037`` in its follow-up (``equipment_sync``), so a 0
        there was a sheathe/draw flap per batch - the "disengage, then the packet
        re-engages me" loop.

        Mounted overrides the stance: 5 draws the chocobo and 85 the other mounts, and
        the rider's own client learns the ride from this byte (see docs/mounts.md).
        """
        ridden = mounts.by_id(self.mount_id)
        if ridden is not None:
            return ridden.animation()
        return 1 if self.engaged_id else 0

    def player_body(self, mask: int = packets.SEND_CHAR_SPAWN, *, targid: int | None = None,
                    moving: bool | None = None) -> bytes:
        """Body of a 0x00D player-entity packet.

        The local client always knows itself as targid 0x400; every other player is sent
        with the targid World assigned. The body layout is the reference 0x68-byte
        character update: position, movement/facing, HP, animation, size, looks, name.
        """
        c = self.char
        x, y, z, rot = self.pos
        if targid is None:
            targid = self.targid or TARGID
        if int(mask) & packets.SEND_PLAYER_DESPAWN:
            # LSB sends a despawn at the "nonspecific" size (0x40): UniqueNo, ActIndex,
            # SendFlg. A full 0x68 body with the despawn bit is ignored by the client.
            b = bytearray(0x40)
            struct.pack_into("<IHB", b, 0, c["char_id"], int(targid), int(mask) & 0xFF)
            return bytes(b)
        # Flags0 is a 32-bit bitfield: MovTime (13 bits), RunMode/TargetMode/GroundFlag/
        # KingFlag, then facetarget (15 bits). LSB's char_update.cpp is the reference.
        walk = 1 if (self.moving if moving is None else moving) else 0
        movetime = self.move_time if walk else 0
        face = int(self.engaged_targid or self.target_targid or 0) & 0x7FFF
        flags0 = (movetime & 0x1FFF) | (face << 17)
        b = bytearray(0x68)
        struct.pack_into("<IHBBfff", b, 0, c["char_id"], int(targid), int(mask) & 0xFF,
                         int(rot) & 255, x, y, z)
        struct.pack_into("<I", b, 0x14, flags0)
        hpp = gauge_percent(c.get("hp_current", c["hp"]), c["hp"])
        ridden = mounts.by_id(self.mount_id)
        # 0x1B is the entity animation: 1 is the drawn-weapon battle stance, 0 is idle and
        # 5/85 tell the client to draw a chocobo or a mount under the character.  It is
        # the same byte 0x037 carries at 0x2C (own_animation).
        animation = self.own_animation()
        struct.pack_into("<BBBB", b, 0x18, self.own_speed(), 40, hpp, animation)
        # Flags1: GraphSize in bits 9-10, ChocoboIndex in bits 5-7.  ChocoboIndex is how
        # other clients tell a rider from someone standing there when the mount is the
        # personal chocobo: mount id 0 has to look different from "no mount" in Flags6,
        # and index 1 is the client's ordinary chocobo seat.
        chocobo_index = ridden.chocobo_index() if ridden else 0
        struct.pack_into("<I", b, 0x1C, ((c["size"] & 3) << 9) | ((chocobo_index & 7) << 5)
                         | (self.female() << 15))
        if ridden is not None:
            # CustomProperties (body 0x30): the Noble Chocobo is told apart from a plain
            # one by the second word; every other mount leaves both clear.
            struct.pack_into("<II", b, 0x30, *ridden.custom_properties())
        b[0x3F] = 10
        # Flags6 (body 0x40, the last field of the General block): GateId in its low four
        # bits and the mount id in bits 4-11.  The client's 0x00D handler copies those
        # eight bits into the player entity's MountId, and the model under the rider is
        # whichever mount the id names.
        if ridden is not None:
            struct.pack_into("<I", b, 0x40, (ridden.id & 0xFF) << 4)
        struct.pack_into("<9H", b, 0x44, *self.looks())
        b[0x56:0x66] = cstr(c["name"], 16)
        if int(mask) == packets.SEND_HP:
            # A General-only update is 0x44 bytes in retail (LSB sizes the packet to the
            # last block the mask announces).  Sending the full 0x68 makes the client
            # re-read the model/name blocks it was not told about, which resets the
            # entity and drops the drawn-weapon pose the heartbeat just set.
            return bytes(b[:0x44])
        return bytes(b)

    def char_update(self, mask: int = packets.SEND_CHAR_SPAWN) -> Msg:
        return sub(0x00D, self.player_body(mask, targid=TARGID, moving=False))

    def char_sync(self) -> Msg:
        c = self.char
        b = bytearray(0x24)
        struct.pack_into("<BBHI", b, 0, 2, 9, TARGID, c["char_id"])
        b[0x21] = c["main_level"]
        return sub(0x067, b)

    def build(self, client_hdr: bytearray, next_id: bool = True) -> bytes:
        """The next packet: what is queued, compressed, signed and enciphered."""
        packet_id = (self.server_id + 1) & 0xFFFF if next_id else self.server_id
        data, nbits, zone_out = self.pack(packet_id)
        if not data:
            # The ambient budget is spent and nothing else is waiting.  Do not burn a
            # packet id (and a datagram of header) saying nothing: the next exchange or
            # flush carries the queued positions.
            return b""
        self.server_id = packet_id
        h = bytearray(client_hdr[:HDR])
        struct.pack_into("<HH", h, 0, self.server_id, self.client_id)
        if os.environ.get("FANXI_ZONE_ECHO_TIME") != "1":
            struct.pack_into("<I", h, 8, int(time.time()))
        data += struct.pack("<I", nbits)
        data += md5(data)
        self.last_plain = bytes(h) + data
        out = bytearray(self.last_plain)
        self.cipher.run(out, HDR, (len(data) // 4) & ~1, True)
        if DEBUG:
            log.info("%s out #%d %d bytes (client #%d) hdr %s", self.addr, self.server_id,
                     len(out), self.client_id, bytes(out[:HDR]).hex())
        self.last = out
        self.last_sent_at = time.time()
        if zone_out:
            self.bump_key()
            with self.world.lock:
                # Database id: the next 0x00A may name the character by either id.
                self.world.by_char[int(self.char["id"])] = self
            self.queue.clear()
            self.pending_positions.clear()
        return bytes(out)

    def pack(self, packet_id: int | None = None) -> tuple[bytes, int, bool]:
        """The packet's sub-messages: real events first, then the ambient entity stream.

        The client's receive pipe is small and its packet handler is a FIFO.  In a
        crowded zone the mob position stream alone is several kilobytes a second, so
        packing it ahead of an action result made a job ability appear a minute or more
        after it was pressed.  Three rules keep that from happening:

        * real events (actions, status, chat, equipment) go out before any entity move;
        * only the latest position per entity is kept (``queue_position``);
        * the ambient stream gets a token-bucket byte budget, so the client's pipe is
          never filled by scenery while a reply is waiting.

        Returns an empty body when the budget is spent and there is nothing urgent;
        ``build`` turns that into "send nothing" rather than an empty datagram.
        """
        packet_id = self.server_id if packet_id is None else int(packet_id)
        queued, self.queue = self.queue, []
        now = time.time()
        deferred: list[Msg] = []
        ready: list[Msg] = []
        for message in queued:
            due = float(getattr(message, "not_before", 0.0) or 0.0) <= now
            after = int(getattr(message, "after_packet", -1))
            if not due or (after >= 0 and int(self.server_id) <= after):
                deferred.append(message)
            else:
                ready.append(message)
        queued = ready
        urgent: list[Msg] = []
        latest: dict[tuple[int, int], Msg] = {}
        for message in queued:
            if getattr(message, "ambient", False):
                latest[(message.ptype, message.targid)] = message
            else:
                urgent.append(message)

        def rank(message: Msg) -> float:
            # Nearest first, but a message that has waited gets promoted so a distant
            # mob is not starved by the dozen closest to the player.
            waited = max(0.0, now - float(getattr(message, "queued_at", now)))
            return float(message.priority) - waited * 12.0

        ambient = sorted(latest.values(), key=rank)
        # A coalesced message that was already sent (or superseded) has no pending slot.
        for key, message in list(self.pending_positions.items()):
            if latest.get(key) is not message:
                self.pending_positions.pop(key, None)
        # An entity update that is already ordered first (spawn, despawn, HP, animation)
        # carries the same position, so the older ambient copy is redundant and must not
        # arrive after it.
        urgent_keys = set()
        for message in urgent:
            tag = struct.unpack_from("<H", message, 0)[0] & 0x1FF
            if tag in (0x00D, 0x00E) and len(message) >= 10:
                urgent_keys.add((tag, struct.unpack_from("<H", message, 8)[0]))
        if urgent_keys:
            for key in urgent_keys:
                self.pending_positions.pop(key, None)
            ambient = [message for message in ambient
                       if (message.ptype, message.targid) not in urgent_keys]

        refill = AMBIENT_BYTES_PER_SECOND * max(0.0, now - self.ambient_at)
        self.ambient_tokens = min(float(AMBIENT_BURST_BYTES),
                                  self.ambient_tokens + refill)
        self.ambient_at = now
        budget = min(float(AMBIENT_BURST_BYTES), self.ambient_tokens)

        body = bytearray()
        zone_out = False
        held: list[Msg] = []

        def take(message: Msg) -> bool:
            nonlocal zone_out
            if body and len(body) + len(message) > PACKET_BYTES:
                return False
            struct.pack_into("<H", message, 2, packet_id)
            if DEBUG:
                log.info("%s out %03X %d bytes", self.addr,
                         struct.unpack_from("<H", message, 0)[0] & 0x1FF, len(message))
            body.extend(message)
            self._note_sent_sync(message)
            zone_out = zone_out or message.zone_out
            return True

        for message in urgent:
            if not take(message):
                held.append(message)
                continue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x037:
                # The timer packet always follows the icon list.  The client pairs the two
                # slot for slot, so sending 0x037 alone draws the icons with no countdown.
                timer = self.status_icons()
                struct.pack_into("<H", timer, 2, packet_id)
                body.extend(timer)

        spent = 0
        for message in ambient:
            if spent + len(message) > budget:
                held.append(message)
                continue
            if not take(message):
                held.append(message)
                continue
            spent += len(message)
            self.pending_positions.pop((message.ptype, message.targid), None)
        self.ambient_tokens = max(0.0, self.ambient_tokens - spent)
        self.queue = held + deferred
        if not body:
            return b"", 0, False
        data, nbits = self.world.huff.compress(bytes(body))
        return data, nbits, zone_out

    def seal_last(self, key: bytes) -> bytes:
        """The last plaintext packet sealed under ``key`` (the zone-in copy)."""
        if self.last_plain is None:
            return b""
        out = bytearray(self.last_plain)
        struct.pack_into("<H", out, 2, self.client_id)
        struct.pack_into("<I", out, 8, int(time.time()))
        self.world.zone_cipher_for(key).run(out, HDR, (len(out) - HDR) // 4 & ~1, True)
        return bytes(out)

    def resend(self, use_base: bool = False) -> bytes:
        """Re-send the last packet, optionally under the pre-zone-change key."""
        if self.last_plain is None:
            return b""
        key = self.base_key if use_base and self.base_key is not None else bytes(self.key)
        out = self.seal_last(key)
        self.last_sent_at = time.time()
        return out

    def zone_in_copies(self, primary: bytes | None = None) -> list[bytes]:
        """The zone-in sealed under every key other than the one already sent.

        The client keeps whichever key it advanced to; sending the same packet under the
        whole sequence means a missed or reordered 0x00B can no longer strand it on the
        "Downloading" screen.  The packet id and body are identical, so the client acks
        the one it opens and drops the rest (their MD5 does not verify).
        """
        if self.last_plain is None or self.zone_loaded:
            return []
        primary = bytes(primary) if primary is not None else (
            bytes(self.key) if self.key is not None else b"")
        copies: list[bytes] = []
        for key in reversed(self.key_history):
            if key == primary:
                continue
            copies.append(self.seal_last(key))
            if len(copies) >= KEY_HISTORY:
                break
        return [packet for packet in copies if packet]
