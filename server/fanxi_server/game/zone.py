"""The zone protocol: login, entities, movement, chat, inventory, shops and basic combat.

The server is intentionally small but speaks the real client protocol: 0x00A/0x00C zone-in,
0x00E NPC/mob spawns on the client's first 0x015, 0x028 battle actions, 0x020/0x01D inventory,
0x03C/0x03E/0x03F shops, and the status/job packets the client waits on.
"""
from __future__ import annotations

import logging
import math
import os
import random
import socket
import struct
import time

from . import combat, design as character_design, effects, merits, modifiers as mod, packets, skills, stats, traits
from .cipher import md5
from .entities import ZoneEntity
from .world import (
    DISENGAGE_DISTANCE,
    ENGAGE_RANGE,
    MELEE_RANGE,
    PLAYER_DESPAWN_RANGE,
    PLAYER_SPAWN_RANGE,
    heading_to_rot,
)

log = logging.getLogger("fanxi.zone")
DEBUG = bool(os.environ.get("FANXI_ZONE_DEBUG"))

HDR = 28
TARGID = 0x400
VANA_EPOCH = 1009810800
VANA_HOUR, VANA_DAY = 144, 3456

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

# 0x009 system-message ids from the client's ROM/27/76.DAT table.
MSG_STYLE_LOCK_ON = 267
MSG_STYLE_LOCK_OFF = 268
MSG_STYLE_LOCK_IS_ON = 269
MSG_STYLE_LOCK_IS_OFF = 270

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

# !locker selectors.  Slots use the item catalogue's equip_slot names; ear/ring cover
# both copies, and capes/mantles are the back slot.
LOCKER_SLOTS = {
    "main": "main", "weapon": "main", "sub": "sub", "shield": "sub",
    "ranged": "ranged", "ammo": "ammo", "head": "head", "body": "body",
    "hands": "hands", "legs": "legs", "feet": "feet", "neck": "neck",
    "waist": "waist", "ear": "ear", "earring": "ear", "ring": "ring",
    "back": "back", "cape": "back", "capes": "back", "mantle": "back",
}


def locker_selector(text: str) -> tuple[dict, str]:
    """Turn the words after !locker store/grab into a selector and a chat label."""
    wanted = " ".join(str(text or "").split())
    key = wanted.casefold()
    if key in ("all", "everything", "*"):
        return {"kind": "all"}, "all"
    if key in ("materials", "material", "crafting", "craft"):
        return {"kind": "materials"}, "materials"
    if key in LOCKER_SLOTS:
        return {"kind": "slot", "slot": LOCKER_SLOTS[key]}, key
    return {"kind": "name", "text": wanted}, wanted


def vana_offset(hour: float) -> int:
    """Earth seconds to add to the clock so that it is this Vana'diel hour (0-23, fractions too)."""
    return int(hour * VANA_HOUR - (time.time() - VANA_EPOCH)) % VANA_DAY


class Msg(bytearray):
    zone_out = False  # 0x00B: build() moves the key on after sending it


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
        self.queue: list[Msg] = []
        self.last = None
        self.logged_in = False
        self.zoning = False
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
        # A slot changed in this packet batch. Its follow-up (looks, spells, abilities, stats)
        # and the outfit save go out once, after the whole batch has been read: one copy per
        # slot queued about a kilobyte each and the client is served one packet per ack, so a
        # sixteen-slot swap used to show up a second late, slot by slot.
        self.equipment_changed = False
        self.client_hdr = b""
        self.entities: list = []
        self.engaged_id: int | None = None
        self.casting: dict | None = None
        # recast id -> unix time it becomes usable again (0x119 sends the remainder).
        self.ability_recasts: dict[int, float] = {}
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
        self.position_seen = False
        self.target_targid = 0
        self.engaged_targid = 0
        # The client sends its own /attack off when the target leaves auto-attack reach.
        # The first one that merely reflects distance is ignored so the engagement can
        # continue while kiting; a second within a moment is the player asking to break it.
        self.range_disengage_at = 0.0
        self.range_disengage_hinted = False
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
        # effect id -> {until, power, potency, tick, icon, mods}; status_effects is the
        # client's icon order and this dict is the server-side timer and payload.
        self.effect_state: dict[int, dict] = {}
        self.resting = False
        self.next_rest_tick = 0.0
        self.stats_refresh_at = 0.0
        self.door_close_at = 0.0
        self.door_entity = None
        self.opened_doors: set[int] = set()
        self.last_packet_at = time.time()
        self.last_release_at = 0.0
        # When the next Auto Refresh/Auto Regen (or gear Refresh/Regen) tick lands.
        # Retail ticks these every three seconds, not once per server frame.
        self.next_regen_tick = time.time() + traits.TICK_SECONDS
        self._trait_cache: tuple[tuple[int, int, int, int], list[traits.Trait]] | None = None

    def save_position(self, force: bool = False) -> None:
        """Movement arrives many times a second; the database gets it every few seconds."""
        now = time.time()
        if force or now - self.last_save >= 5:
            self.last_save = now
            self.world.save_position(self.char, self.zone, self.pos)

    def set_key(self, key: bytes) -> None:
        self.key = bytearray(key)
        self.cipher = self.world.zone_cipher_for(self.key)

    def bump_key(self) -> None:
        """After 0x00B the client moves its key on by 2 (the last word, as a number)."""
        self.prev_cipher = self.cipher
        value = (struct.unpack_from("<I", self.key, 16)[0] + 2) & 0xFFFFFFFF
        struct.pack_into("<I", self.key, 16, value)
        self.cipher = self.world.zone_cipher_for(self.key)

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
            s, continuing = world.take_login(addr, char, cid)
            # 0x400 is "self" in every client; other players get a targid from World.
            s.targid = world.assign_player_targid(cid)
            s.zone = int(char["zone"])
            s.pos = list(char["pos"])
            s.gone = False
            s.seen_players.clear()
            s.moving = False
            s.move_time = 0
            s.last_player_update = 0.0
            s.next_player_sync = 0.0
            if not continuing:
                # A zone change advanced the client's cipher by 2 and it reconnects with
                # that key; every other login starts from the account's sign-in key.
                s.set_key(world.keys.get(account) or
                          world.key_from_hash(game_session["session_hash"]))
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
            sync = struct.unpack_from("<H", buf, HDR + 2)[0]
            if sync > 1:
                s.server_id = sync
                return s.build(buf, next_id=False)
            s.server_id = 0
            return s.build(buf)
        if session is None:
            return None
        body = session.decrypt(buf)
        if body is None:
            return None
        session.client_hdr = bytes(buf[:HDR])
        session.parse(buf, body)
        # Run due timers in the same exchange so swings, rewards and roaming are not starved
        # while a client is sending position packets continuously.
        world.advance(time.time())
        # Delivery is one packet at a time: until the client acknowledges the last one, it is sent again.
        if session.last is not None and struct.unpack_from("<H", buf, 2)[0] != session.server_id:
            return session.resend()
        return session.build(buf)

    def decrypt(self, buf: bytearray):
        n = len(buf)
        words = ((n - HDR) // 4) & ~1
        for cipher in (self.cipher, self.prev_cipher):
            if cipher is None:
                continue
            b = bytearray(buf)
            cipher.run(b, HDR, words, False)
            if md5(bytes(b[HDR:n - 16])) == bytes(b[n - 16:]):
                nbits = struct.unpack_from("<I", b, n - 20)[0]
                body = self.world.huff.decompress(bytes(b[HDR:n - 20]), nbits)
                if body is None:
                    log.warning("%s: a packet that does not decompress", self.addr)
                return body
        log.warning("%s: a packet neither key opens", self.addr)
        return None

    def parse(self, hdr: bytearray, body: bytes) -> None:
        self.last_packet_at = time.time()
        code = struct.unpack_from("<H", hdr, 0)[0]
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
            # windows waiting forever.
            if ptype in (0x050, 0x051, 0x052, 0x053, 0x05D, 0x061, 0x0B5) or \
                    self.client_id < sync <= code:
                self.handle(ptype, body[offset:offset + size])
            offset += size
        if self.equipment_changed:
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
            if not self.zone_loaded:
                self.after_zone_in()
        elif t == 0x050:  # equipment change
            self.equip(p)
        elif t == 0x052:  # the client asks whether the set it is assembling is legal
            self.equipset_check(p)
        elif t == 0x037:  # item use
            self.item_use(p)
        elif t == 0x03A:  # after sorting a bag, merge its partial stacks
            self.item_stack(p)
        elif t == 0x01A:  # target action: talk, engage, disengage
            self.action(p)
        elif t == 0x0E8:  # /heal
            self.heal_command(p)
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
            # ~10 Hz; always send the one packet that says "stopped" so followers do not
            # keep walking after the key is released.
            if self.entities_sent:
                now = time.time()
                if moved and now - self.last_player_update >= 0.1:
                    self.last_player_update = now
                    self.world.broadcast_player(self, packets.SEND_POSITION, moving=True)
                elif (not moved and was_moving) or (turned and now - self.last_player_update >= 0.1):
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
                self.change_zone(line[0], list(line[1:]))
            else:
                # Never leave the client on the black zone-transition screen: reload this
                # zone at its spawn, which also moves the player off the trigger.
                log.info("%s zone line %#x (%r) is not authored", self.addr, rect, name)
                self.say("That passage is not open in this build.")
                self.change_zone(self.zone, list(self.world.zones.position(self.zone)))
        elif t == 0x0B5:  # chat
            kind = int(p[4]) if len(p) > 4 else 0
            text = bytes(p[6:]).split(b"\0")[0].decode("ascii", "replace")
            # "/" opens the client's chat line already holding a slash, so "/!cmd" is how a
            # typed command actually arrives when it was started with that key.
            text = text.lstrip("/")
            if text.startswith("!"):
                self.command(text[1:].split())
            elif kind in (0, 8) and text:
                # Say and emote both need the server to echo them; the client does not
                # draw its own outgoing line.  Kind 8 is the emote animation.
                self.queue.append(sub(0x017, packets.chat_std(
                    self.char["name"], text, self.zone, kind)))
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
        elif t == 0x03C:  # the blacklist
            self.queue.append(self.blacklist())
        elif t == 0x0E7:  # /logout, /shutdown
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

    def command(self, words: list[str]) -> None:
        commands = (
            "commands: !zone <id> [x y z [rot]], !pos <x> <y> <z> [rot], !where, !door <id>, "
            "!time <hour>, /heal rests, !heal refills, !entities, !moghouse, !home, "
            "!disengage (break a kept range engagement), "
            "!hp [menu number|zone] (alias !warp), !sg [n]",
            "!locker store|grab|list <all|ammo|back|materials|name>, "
            "!storage store|grab <job|all>",
            "!ws <name>, !ja <name>, !abilities, !traits, !job <job> [sub] (slips the old "
            "job's gear and tidies the bags), !cast <spell>, "
            "!equip <name>, !unequip <slot>, !model <item> <id>, !event <id> [p1..p8], "
            "!character model <race> <1-48|random>, "
            "!merits [n], !stock, !r30 [item], !augment <A-D|index|off|list> <item>, "
            "!cape <build|list|off> <item>",
        )
        try:
            if words and words[0] == "zone" and len(words) >= 2:
                zone = int(words[1], 0)
                pos = [float(v) for v in words[2:5]] + [int(words[5]) if len(words) > 5 else 0] \
                    if len(words) >= 5 else None
                if pos is None:
                    spawn = self.world.zones.position(zone)
                    if not spawn or all(float(v) == 0.0 for v in spawn[:3]):
                        self.say("Zone %d has no spawn here. Try !zone 100 (West Ronfaure)." % zone)
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
                        self.say("Usage: !merits [points] (0-%d)" % cap)
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
            elif words and words[0] == "moghouse":
                self.toggle_moghouse()
            elif words and words[0].casefold() == "storage":
                self.storage_command(words[1:])
            elif words and words[0].casefold() == "locker":
                self.locker_command(words[1:])
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
                    self.say("!sg <number> travels to that survival guide.")
                    return
                try:
                    want = int(words[1], 0)
                except ValueError:
                    self.say("!sg <number>, or !sg for the list.")
                    return
                guide = next((g for g in guides if int(g["idx"]) == want), None)
                if guide is None:
                    self.say("No survival guide with that number.")
                    return
                self.say("The survival guide sends you to %s." %
                         self.world.zones.name(int(guide["zone"])))
                self.change_zone(int(guide["zone"]), [float(guide["x"]), float(guide["y"]),
                                                      float(guide["z"]), int(guide["rot"])])
            elif words and words[0] in ("hp", "homepoint", "warp"):
                points = self.world.service.home_points()
                if len(words) == 1:
                    # Number them by hp_index, the same number the client's Home Point
                    # menu uses.  home_points.idx is a different sequence and made
                    # "!hp 10" go somewhere other than menu entry 10.
                    cells = []
                    for point in points:
                        tag = str(point["name"]).replace("Home Point ", "HP")
                        cells.append("%d %s %s" % (int(point["hp_index"]),
                                                   self.world.zones.name(int(point["zone"])), tag))
                    for offset in range(0, len(cells), 3):
                        self.say(", ".join(cells[offset:offset + 3]))
                    self.say("!hp <menu number|zone name> warps there; !hp lists the points.")
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
                    self.say("Usage: !event <id> [p1..p8]")
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
                    self.say("Usage: !model <item name> <model id>")
                    return
                match = next((i for i in self.world.service.inventory(self.char["id"])
                              if int(i["container"]) == 0
                              and want in str(i.get("name") or "").casefold()), None)
                if match is None:
                    self.say("No inventory item matching that name.")
                    return
                self.world.service.set_item_model(int(match["item_id"]), model)
                self.refresh_character()
                for kind, (container, slot, item_id) in list(self.equipped.items()):
                    if int(item_id) == int(match["item_id"]):
                        self._apply_equip_model(kind, {"model": model})
                self.queue.append(self.grap_list())
                self.say("%s now uses model %d." % (match["name"], model))
            elif words and words[0] in ("r30", "odyssey"):
                from . import limbus, odyssey
                query = " ".join(words[1:]).strip()
                if not query:
                    names = [entry["name"] for entry in odyssey.entries()]
                    names += [entry["name"] for entry in limbus.entries()]
                    for offset in range(0, len(names), 3):
                        self.say(", ".join(names[offset:offset + 3]))
                    self.say("!r30 <item> prints its Rank 30 rows (Odyssey or Limbus).")
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
            elif words and words[0] == "augment":
                from . import unity
                from .augments import bundle as augment_bundle, describe
                from .odyssey import bundle_for
                if len(words) < 2 or words[1].lower() in ("list", "unity"):
                    for item_id, entry in unity.ITEMS.items():
                        self.say("%s (item %d, bundle %d): %s" % (
                            entry["name"], item_id, entry["bundle"],
                            " / ".join(entry["augments"])))
                    self.say("!augment A <item> rewrites a Unity or Odyssey bundle; "
                             "!augment <index|off> <item> sets or clears one.")
                    return
                if len(words) < 3:
                    self.say("Usage: !augment <A-D|index|off> <item>")
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
                        self.say("%s has one Unity path (A); use !augment A <item>."
                                 % unity_entry["name"])
                        return
                elif mode.isdigit():
                    extra = augment_bundle("A", 30, 3, int(mode))
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
                    self.say("!cape <build|off> <item> re-encodes a cape.")
                    return
                if len(words) < 3:
                    self.say("Usage: !cape <build|off> <item>")
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
                    self.say("Unknown %s cape build %r; try !cape list." % (job, words[1]))
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
                    self.char_stats(), self.char_status(),
                ]
                self.refresh_vitals()
                log.info("%s !equip %s slot=%d kind=%d", self.addr, match["name"], slot, kind)
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
                    sub(0x0AA, SPELL_BITS),
                    self.char_abilities(),
                ]
                log.info("%s !unequip kind=%d", self.addr, kind)
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
                    regen = self.trait_mods().get(mod.REGEN, 0)
                    refresh = self.trait_mods().get(mod.REFRESH, 0)
                    if regen or refresh:
                        self.say("Passive tick: Regen %d HP, Refresh %d MP every 3s."
                                 % (regen, refresh))
                self.queue += [self.char_abilities(), self.char_commands()]
            elif words and words[0] == "job" and len(words) >= 2:
                self.job_command(words)
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

    def character_command(self, words: list[str]) -> None:
        """!character model: change race, face, hair colour and size.

        The 48 designs of a race are numbered with size fastest, so Hume 8 is
        Face 2 / Hair A / Medium.  ``random`` picks face, hair and size (and the
        race too when no race is named); ``face 2 hair a size m`` is the detailed
        form the launcher also uses.
        """
        usage = ("Usage: !character model <race> <1-%d|random>  "
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
        """!storage store <job> / !storage grab <job|all>: slip storage from anywhere.

        Retail stores these items on a Storage Slip at a Porter Moogle.  Fanxi keeps the
        same server-side record in ``char_storage`` and deletes the item from every bag,
        so it never appears in the client's inventory or Storage container.  Store only
        takes job-exclusive gear that a slip accepts; gear with no slip stays in the bags.
        """
        usage = "Usage: !storage store <job> (nin, Ninja, 13) or !storage grab <job|all>"
        if not words:
            self._storage_status()
            return
        action = words[0].casefold()
        if action == "store":
            if len(words) < 2:
                self.say(usage)
                return
            wanted = " ".join(words[1:])
            job = job_id(wanted)
            if job is None:
                self.say("Unknown job %r. Try NIN, Ninja or 13." % wanted)
                return
            result = self.world.service.store_job_in_storage(int(self.char["id"]), job)
            self._queue_storage_removals(result["moved"])
            label = JOB_ABBREVIATIONS[job]
            count = sum(int(move["quantity"]) for move in result["moved"])
            if count:
                self.say("Stored %d %s item%s on storage slips (%d total)." % (
                    count, label, "" if count == 1 else "s", result["storage_count"]))
                parts = ["%d:%d" % (slip, quantity) for slip, quantity
                         in sorted(result["slips"].items()) if slip]
                if parts:
                    self.say("Slips: " + ", ".join(parts)[:130] + ".")
            else:
                self.say("No storable %s gear left in your bags." % label)
            if result["unstoreable"]:
                names = result["unstoreable_items"]
                if len(names) <= 3:
                    self.say("No slip for: " + ", ".join(names) + ".")
                else:
                    self.say("No slip for: %s and %d more." % (
                        ", ".join(names[:3]), len(names) - 3))
            if result["equipped"]:
                self.say("Left %d equipped %s piece%s on." % (
                    result["equipped"], label, "" if result["equipped"] == 1 else "s"))
            log.info("%s !storage store %s -> %d items, %d unstoreable", self.addr,
                     label, count, result["unstoreable"])
            return
        if action == "grab":
            job = None
            label = "all"
            wanted = " ".join(words[1:]).strip()
            if wanted and wanted.casefold() not in ("all", "everything", "*"):
                job = job_id(wanted)
                if job is None:
                    self.say("Unknown job %r. Try NIN, Ninja, 13 or all." % wanted)
                    return
                label = JOB_ABBREVIATIONS[job]
            result = self.world.service.take_from_storage(int(self.char["id"]), job)
            self._queue_storage_returns(result["moved"])
            count = sum(int(move["quantity"]) for move in result["moved"])
            if count:
                self.say("Took %d item%s off the storage slips (%d left)." % (
                    count, "" if count == 1 else "s", result["storage_count"]))
            elif result["storage_count"] == 0:
                self.say("The storage slips are empty.")
            elif result["remaining"]:
                self.say("Your bags are full; nothing could be taken off the storage slips.")
            elif result["skipped_job"]:
                self.say("No %s gear on the storage slips." % label)
            else:
                self.say("Nothing came off the storage slips.")
            if count and result["skipped_job"]:
                if result["skipped_job"] == 1:
                    self.say("1 other job item remains on the slips.")
                else:
                    self.say("%d other job items remain on the slips." % result["skipped_job"])
            if count and result["remaining"]:
                self.say("%d item%s stayed: your bags are full." % (
                    result["remaining"], "" if result["remaining"] == 1 else "s"))
            log.info("%s !storage grab %s -> %d items, %d left", self.addr, label, count,
                     result["storage_count"])
            return
        self.say(usage)

    def locker_command(self, words: list[str]) -> None:
        """!locker store|grab|list: the hidden 9999-item locker, not a client bag.

        Store removes the item from every bag; grab puts it back in the inventory first,
        then the wardrobes.  Selectors are ``all``, a slot (``ammo``, ``back``, ``head``,
        ``ear``, ``ring`` and so on), ``materials`` for non-wearable items, or a name
        substring.
        """
        usage = ("Usage: !locker store|grab <all|ammo|back|materials|name> [n] or "
                 "!locker list")
        if not words:
            summary = self.world.service.locker_summary(int(self.char["id"]))
            self.say("Locker: %d/%d items (%d kinds)." % (
                summary["items"], summary["capacity"], summary["kinds"]))
            self.say(usage)
            return
        action = words[0].casefold()
        if action == "list":
            items = self.world.service.locker_items(int(self.char["id"]))
            if not items:
                self.say("The locker is empty.")
                return
            cells = ["%s x%d" % (item["name"], int(item["quantity"])) for item in items]
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
                self.say("Stored %d item%s in the locker (%d/%d)." % (
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
            log.info("%s !locker store %s -> %d items, %d left", self.addr, label, count,
                     result["remaining"])
            return
        result = self.world.service.take_from_locker(int(self.char["id"]), selector, limit)
        self._queue_storage_returns(result["moved"])
        count = sum(int(move["quantity"]) for move in result["moved"])
        if count:
            self.say("Took %d item%s out of the locker (%d left)." % (
                count, "" if count == 1 else "s", result["locker_count"]))
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
        log.info("%s !locker grab %s -> %d items, %d left", self.addr, label, count,
                 result["locker_count"])

    def stock_command(self) -> None:
        """!stock: top the visible consumables back up from the hidden locker."""
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
        """!storage with no verb: what is on the slips, without opening a bag."""
        stored = self.world.service.storage_summary(int(self.char["id"]))
        if not stored:
            self.say("The storage slips are empty. Use !storage store <job>.")
            return
        total = sum(int(quantity) for quantity in stored.values())
        parts = ["%d:%d" % (slip, quantity) for slip, quantity in sorted(stored.items())]
        self.say("Storage slips: %d item%s (%s)." % (
            total, "" if total == 1 else "s", ", ".join(parts)[:100]))
        self.say("Use !storage grab <job|all> to take them back.")

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
                target_container, int(move["to_slot"]))))
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

    def change_zone(self, zone: int, pos, logout_state: int = 2) -> None:
        # The old zone's clients must lose this character before it reappears elsewhere.
        self.world.despawn_player(self)
        self.zone = int(zone)
        self.pos = list(pos) if pos else list(self.world.zones.position(self.zone))
        self.zoning = True
        self.moving = False
        self.move_time = 0
        self.char["zone"] = self.zone
        self.char["pos"] = list(self.pos)
        self.save_position(force=True)
        log.info("%s -> %s (%d) at %s", self.addr, self.world.zones.name(self.zone), self.zone, self.pos)
        self.queue.append(self.logout_packet(logout_state, zone_change=True))

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
        """
        self.char["style_lock"] = 1 if locked else 0
        if models is not None:
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
        """C2S 0x053: /lockstyle on|off, /lockstyleset # and the zone-in keepalive."""
        if len(p) < 8:
            log.info("%s lockstyle short (%d bytes): %s", self.addr, len(p), bytes(p).hex())
            return
        count, mode, flags = int(p[4]), int(p[5]), int(p[6])
        log.info("%s lockstyle mode=%d count=%d flags=%d", self.addr, mode, count, flags)
        if mode == LOCKSTYLE_QUERY:
            self.queue.append(self.system_message(
                MSG_STYLE_LOCK_IS_ON if self.style_locked() else MSG_STYLE_LOCK_IS_OFF))
            return
        if mode == LOCKSTYLE_KEEPALIVE:
            # Sent while zoning with style lock enabled.  Keep the stored appearance;
            # only snapshot when an older save has no models yet.
            if not self.style_locked():
                models = self._style_models()
                if not any(models.values()):
                    models = self._current_models()
                self._apply_style(True, models)
                self.queue += self.style_packets()
            return
        if mode == LOCKSTYLE_DISABLE:
            if not self.style_locked():
                return
            self._apply_style(False)
            self.queue += self.style_packets()
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
        self.zone_loaded = False
        self.entities_sent = False
        self.sent_targids: set[int] = set()
        self.next_entity_sync = 0.0
        self.casting = None
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
        elif int(self.char.get("hp_current", 1)) <= 0:
            self.char["hp_current"] = max(1, int(self.char["hp"]) // 2)
            self.char["mp_current"] = int(self.char.get("mp", 0)) // 2
            try:
                self.world.service.save_vitals(
                    self.char["id"], self.char["hp_current"], self.char["mp_current"])
            except Exception:
                pass
        self.equip_initial()
        self.queue += [sub(0x04F, bytes(4)), self.grap_list(), self.item_max(), self.login_packet()]
        # Send the command data before the client asks for stats (0x061) and builds its
        # menus, but after the login packet has defined the character.
        self.queue += [self.char_feats(), self.char_abilities(), self.char_commands()]
        self.queue += self.equipment_packets()
        self.stats_refresh_at = time.time() + 2.0

    def after_zone_in(self) -> None:
        # Order matters: the client builds the Weapon Skills list when it processes the
        # 0x062 skill packet, from whatever 0x0AC bits it has at that moment.  Sending
        # 0x062 first leaves a fresh client with an empty list; the command data must
        # precede it.
        # The client needs the equipped weapon before it can select a weapon-skill type;
        # the zone-in burst re-asserts the equipment so the 0x062 list build sees Aymur
        # rather than an empty hand.
        self.refresh_vitals()
        q = [sub(0x008, b"\xff" * 48),  # every zone visited: every map viewable
             self.grap_list(), *self.equipment_packets(),
             self.job_info(), self.char_status(), self.char_stats(),
             self.char_feats(), self.char_abilities(), self.char_commands(),
             self.char_skills(), self.party_member(), self.char_update()]
        # Every permanent key item, in both GetItemFlag and LookItemFlag bitmaps.
        q += [sub(0x055, KEY_ITEM_BITS[table] + KEY_ITEM_BITS[table] +
                   struct.pack("<HH", table, 0)) for table in range(7)]
        offered = (0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x88)
        logs = offered + tuple(x + 0x40 for x in offered) + (
            0xD0, 0xD8, 0x30, 0x38, 0xE0, 0xE8, 0xF0, 0xF8, 0x100, 0x108)
        q += [sub(0x056, bytes(32) + struct.pack("<HH", port, 0)) for port in logs]
        q.append(sub(0x056, bytes(36) + struct.pack("<HH", 0xFFFF, 0)))
        q += [sub(0x0AA, SPELL_BITS),         # every spell id in spell_list
              self.job_points(), self.job_points_detail(),
              sub(0x0AE, bytes(8)),            # no mounts
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
        # self.say("%s (%d). Say !help for commands." % (self.world.zones.name(self.zone), self.zone))

    # --- entities, inventory and actions -------------------------------------------------------
    def load_zone_entities(self) -> None:
        if self.char.get("moghouse"):
            # The interior is part of the city zone, so its resident Moogle is already one
            # of the zone's NPCs (at the interior spawn point).  Spawning that exact row,
            # rather than an invented entity, keeps the id the client's own NPC table uses,
            # which is what the target name and the Moogle's menu are keyed on.
            self.entities = [self.moghouse_moogle()]
        else:
            self.entities = list(self.world.entities_for_zone(self.zone))
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

    def queue_entity(self, entity, mask: int = packets.SEND_SPAWN, equipped: bool = False) -> None:
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
            for item in items:
                if int(item["container"]) != container:
                    continue
                out.append(self.item_packet(item))
            flags |= 1 << container
            out.append(sub(0x01D, packets.item_same(0, container, flags)))
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
        """One 0x020 for an inventory row, carrying its augment ``extdata``."""
        return sub(0x020, packets.item_attr(
            int(item["item_id"]), int(item["quantity"]),
            int(item["container"] if container is None else container),
            int(item["slot"] if slot is None else slot),
            extra=bytes(item.get("extra") or b"")))

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
        for key, slot in (("main", 0), ("sub", 1), ("ranged", 2), ("head", 4), ("body", 5),
                          ("hands", 6), ("legs", 7), ("feet", 8)):
            if slot == kind:
                self.char[key] = 0

    @staticmethod
    def _is_grip(item: dict | None) -> bool:
        """A grip is the only sub item that can share hands with a two-handed weapon."""
        return bool(item) and str(item.get("name") or "").strip().casefold().endswith("grip")

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
        self.equipment_changed = True
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
            self.equipment_changed = True
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

    def flush_equipment(self) -> None:
        """Save the outfit and send its follow-up once, after a whole packet batch."""
        if not self.equipment_changed:
            return
        self.equipment_changed = False
        self.store_equipment()
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
        """
        if not self.engaged_id:
            return
        target = self.world.entity_by_id(self.zone, int(self.engaged_id))
        if target is not None:
            self.queue.append(sub(0x058, struct.pack(
                "<IIHH", int(self.char["char_id"]), int(target.id),
                int(self.char.get("targid", 0x400)), 0)))
        self.queue.append(self.char_update(packets.SEND_HP))
        self.stance_at = time.time()

    def disengage(self, message: str | None = None) -> None:
        """Break the engagement and sheathe.

        This is the deliberate path: !disengage, a second /attack off at range, a target
        that died, going beyond ENGAGE_RANGE, healing, death and a zone change all come
        here.  The automatic /attack off the client sends at auto-attack range does not,
        because the server keeps that engagement alive (see ACTION_ATTACK_OFF).
        """
        if self.engaged_id and message:
            self.say(message)
        self.engaged_id = None
        self.engaged_targid = 0
        self.range_disengage_at = 0.0
        self.range_disengage_hinted = False
        self.queue.append(self.char_update(packets.SEND_HP))

    def engaged_target(self):
        """The live entity this session is engaged to, or None."""
        if not self.engaged_id:
            return None
        return self.world.entity_by_id(self.zone, int(self.engaged_id))

    def equipment_sync(self) -> list[Msg]:
        """What the client needs after gear changed, once for the whole packet batch.

        Looks, spell bits, the ability tables and the stat sheet are all derived from the
        final outfit, and the client shows each slot as its own 0x050 echo arrives.  Sending
        this block per slot put about a kilobyte per slot in front of the later echoes in a
        stop-and-wait queue, which is what made a full swap arrive in waves.
        """
        return [
            self.grap_list(),                # the models of everything now worn
            sub(0x0AA, SPELL_BITS),          # magic data, as retail re-sends on a gear change
            self.char_feats(),               # the 160-bit job ability table
            self.char_abilities(),           # command data
            self.char_commands(),            # and the incremental 0x1A5 update
            self.char_stats(), self.char_status(),
        ]

    def equip(self, p: bytes) -> None:
        """C2S 0x050: the client changed one equipment slot."""
        log.info("%s equip raw (%d bytes): %s", self.addr, len(p), bytes(p).hex())
        # 4-byte sub-message header + 3 bytes (PropertyItemIndex, EquipKind, Category).
        if len(p) < 7:
            return
        slot, kind, category = int(p[4]), int(p[5]), int(p[6])
        log.info("%s equip request len=%d slot=%d kind=%d cat=%d", self.addr, len(p), slot, kind, category)
        if slot == 0:  # the client's "remove from this slot" form
            self.equipped.pop(kind, None)
            self._clear_equip_model(kind)
            # The grap list has to lose the model too: a reply that still says the old
            # weapon is in the slot makes the client treat the unequip as failed and it
            # never sends the follow-up 0x050 that puts the new item on.
            self.queue.append(sub(0x050, struct.pack("<BBBx", 0, kind, category)))
            self.equipment_changed = True
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
            self.equipment_changed = True
            if kind == 0:
                self._enforce_weapon_pair(items)
            return
        item_id, quantity = int(item["item_id"]), int(item["quantity"])
        problem = (self._equip_blocked_reason(item, kind)
                   or self._weapon_pair_error(item, kind, items))
        if problem:
            log.info("%s refused equip slot=%d kind=%d item=%d: %s", self.addr, slot, kind,
                     item_id, problem)
            self.say(problem)
            self._resend_slot(kind)
            return
        log.info("%s equip slot=%d kind=%d cat=%d item=%d %s", self.addr, slot, kind,
                 category, item_id, item.get("name"))
        self.equipped[kind] = (category, slot, item_id)
        self._apply_equip_model(kind, item)
        self.queue += [
            sub(0x050, struct.pack("<BBBx", slot, kind, category)),
            self.item_packet(item, container=category, slot=slot),
        ]
        self.equipment_changed = True
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

    def queue_action(self, target_id: int, damage: int, *, miss: bool = False,
                     critical: bool = False, defeated: bool = False,
                     actor_id: int | None = None, animation: int = 0,
                     message: int | None = None, kind: int = 1,
                     category: int = packets.ACTION_CATEGORY_BASIC_ATTACK,
                     info: int | None = None) -> None:
        distortion = 0
        if not miss and damage and message is None:
            max_hp = max(1, int(getattr(self, "_last_target_hp", 100)))
            percent = damage * 100 // max_hp
            distortion = 3 if percent >= 20 else 2 if percent >= 10 else 1
        actor = int(actor_id if actor_id is not None else self.char["char_id"])
        log.info("%s action out: actor=%d target=%#x damage=%d miss=%s anim=%d msg=%s",
                 self.addr, actor, int(target_id), int(damage), miss, int(animation), message)
        self.queue.append(sub(0x028, packets.battle_action(
            actor, int(target_id), int(damage), miss=miss,
            critical=critical, defeated=defeated, hit_distortion=distortion,
            animation=int(animation), message=message, kind=kind,
            category=category, info=info)))

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
        new_hp = min(hp_max, hp + max(1, hp_max // 20))
        new_mp = min(mp_max, mp + (max(1, mp_max // 20) if mp_max else 0))
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
        if not self.effect_state:
            return
        changed = False
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
            if effect_id == effects.REGEN:
                hp = int(self.char.get("hp_current", 0))
                healed = min(int(self.char.get("hp", hp)), hp + tick)
                if healed != hp:
                    self.char["hp_current"] = healed
                    changed = True
            elif effect_id == effects.REFRESH:
                mp = int(self.char.get("mp_current", 0))
                restored = min(int(self.char.get("mp", 0)), mp + tick)
                if restored != mp:
                    self.char["mp_current"] = restored
                    changed = True
            elif effect_id in (effects.POISON, effects.BIO, effects.PLAGUE):
                hp = int(self.char.get("hp_current", 0))
                self.char["hp_current"] = max(0, hp - tick)
                changed = True
                self.queue_action(int(self.char["char_id"]), tick, message=185,
                                  kind=0, category=4, info=0)
                if int(self.char["hp_current"]) <= 0:
                    self.dead_until = now + 6.0
                    self.engaged_id = None
                    self.engaged_targid = 0
                    self.queue.append(self.char_update(packets.SEND_HP))
                    self.say("You have been defeated. You recover in a moment.")
                    try:
                        self.world.service.record_death(int(self.char["id"]))
                    except Exception:
                        pass
                    break
        if changed:
            self.queue += [self.char_status(), self.char_stats(), self.party_member()]
            try:
                self.world.service.save_vitals(
                    int(self.char["id"]), int(self.char.get("hp_current", 0)),
                    int(self.char.get("mp_current", 0)))
            except Exception:
                pass

    def restore_vitals(self, refresh: bool = True) -> None:
        """Fill HP and MP to their maxima and persist them, as rest does.

        Used by !heal and by the Mog House; ``refresh`` queues the packets that redraw the
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
                   mods: dict[int, int] | None = None) -> None:
        """Record a player effect and put its icon in the next 0x037.

        The caller queues ``char_status()``; this only mutates the state so two effects
        landing in the same packet do not each send the client a partial list.
        """
        effect_id = int(effect_id)
        if effect_id <= 0:
            return
        now = time.time()
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
            if mods:
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
        self.change_zone(destination, self.moghouse_door(destination), logout_state=2)

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
        self._change_job(int(p[4]), int(p[5]))

    def _job_level(self, job: int) -> int:
        return int((self.char.get("jobs") or {}).get(int(job), (0, 0))[0])

    def _change_job(self, main_job: int, sub_job: int, *, auto_equip: bool = True) -> bool:
        """Apply a job change and refresh every packet that depends on it."""
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
        # Retail clears style lock on a job change, and so does the client when it sends
        # 0x053 mode 0; doing it here also covers the server-side !job command.
        if self.style_locked():
            self._apply_style(False)
        self._unequip_invalid()
        if auto_equip:
            # Dress the new job before the bundle, so the grap list carries the new models.
            self.queue += self.equipment_packets()
        # Job traits change the maxima too (Max HP/MP Boost), and the packets in the
        # bundle report both the sheet maximum and the stored current value.
        self._trait_cache = None
        self.refresh_vitals()
        self.queue += self.job_bundle()
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
        """!job: slip the old job's gear, pull the new set and tidy the inventory.

        A job change on this server used to leave the old outfit in the bag and the
        new one split between slips and wardrobes.  The command makes the swap
        self-contained: everything worn comes off, the old job's slipped gear is
        stored, the new job's slips are emptied into a cleared inventory, and the
        leftovers go into the wardrobes.  Working stock stays visible.
        """
        main_job = job_id(words[1])
        sub_job = job_id(words[2]) if len(words) > 2 else 0
        if main_job is None:
            self.say("Unknown job %r. Try NIN, Ninja or 13." % words[1])
            return
        if self._job_level(main_job) <= 0:
            self.say("That job is not available yet.")
            return
        if sub_job and self._job_level(sub_job) <= 0:
            self.say("That support job is not available yet.")
            return
        previous = int(self.char.get("main_job") or 1)
        previous_label = JOB_ABBREVIATIONS.get(previous, str(previous))
        new_label = JOB_ABBREVIATIONS.get(main_job, str(main_job))

        # The slips only accept loose gear, so take the old outfit off first.
        self._unequip_all("job change to %s" % new_label)
        stored = {"moved": [], "unstoreable": 0, "unstoreable_items": []}
        try:
            stored = self.world.service.store_job_in_storage(
                int(self.char["id"]), previous)
        except Exception as exc:
            log.warning("%s could not store %s gear: %s", self.addr, previous_label, exc)
            self.say("Could not store the old gear: %s" % exc)
        else:
            self._queue_storage_removals(stored["moved"])
            count = sum(int(move["quantity"]) for move in stored["moved"])
            if count:
                self.say("Stored %d %s item%s on the storage slips." % (
                    count, previous_label, "" if count == 1 else "s"))
            else:
                self.say("No storable %s gear was in the bags." % previous_label)
            if stored["unstoreable"]:
                names = stored["unstoreable_items"]
                self.say("No slip for: %s%s." % (
                    ", ".join(names[:3]), "" if len(names) <= 3 else " and %d more" % (
                        len(names) - 3)))

        # Free inventory space for the incoming set, but keep gear the new job can
        # wear (and all-job pieces) where auto-equip can see it.
        try:
            tidy = self.world.service.sort_inventory_into_wardrobes(
                int(self.char["id"]), keep_jobs=1 << (main_job - 1))
            self._queue_inventory_moves(tidy["moved"])
        except Exception as exc:
            log.warning("%s could not tidy the inventory before the pull: %s", self.addr, exc)

        if not self._change_job(main_job, sub_job, auto_equip=False):
            return

        try:
            pulled = self.world.service.take_from_storage(int(self.char["id"]), main_job)
        except Exception as exc:
            log.warning("%s could not pull %s gear: %s", self.addr, new_label, exc)
            pulled = {"moved": [], "skipped_job": 0, "remaining": 0, "storage_count": 0}
        self._queue_storage_returns(pulled["moved"])
        count = sum(int(move["quantity"]) for move in pulled["moved"])
        if count:
            self.say("Pulled %d %s item%s from the storage slips." % (
                count, new_label, "" if count == 1 else "s"))
        elif pulled["skipped_job"]:
            self.say("No %s gear was on the storage slips." % new_label)
        if pulled["remaining"]:
            self.say("%d item%s stayed on the slips: the bags are full." % (
                pulled["remaining"], "" if pulled["remaining"] == 1 else "s"))

        # Wear what was just pulled, then put the unused pieces away.
        self.equipped.clear()
        self.equip_initial(bags=AUTO_EQUIP_BAGS)
        self.queue += self.equipment_packets()
        self.refresh_vitals()
        try:
            leftovers = self.world.service.sort_inventory_into_wardrobes(
                int(self.char["id"]))
            self._queue_inventory_moves(leftovers["moved"])
        except Exception as exc:
            log.warning("%s could not tidy the inventory after the pull: %s", self.addr, exc)
            leftovers = {"moved": [], "remaining": 0}
        if leftovers["moved"]:
            self.say("Moved %d leftover item%s into the wardrobes." % (
                len(leftovers["moved"]), "" if len(leftovers["moved"]) == 1 else "s"))
        if leftovers["remaining"]:
            self.say("%d item%s stayed in the inventory: the wardrobes are full." % (
                leftovers["remaining"], "" if leftovers["remaining"] == 1 else "s"))
        # The unequip/auto-equip pair changed the stat sheet, so send the final
        # appearance and stats once even when nothing was originally worn.
        self.equipment_changed = True
        self.flush_equipment()
        log.info("%s !job %s -> %s: stored %d, pulled %d, tidied %d", self.addr,
                 previous_label, new_label,
                 sum(int(move["quantity"]) for move in stored["moved"]),
                 count, len(leftovers["moved"]))

    def job_bundle(self) -> list[Msg]:
        """Every packet the client re-reads after the job (or support job) changes."""
        return [self.grap_list(), self.job_info(), self.char_status(), self.char_stats(),
                self.char_feats(), self.char_abilities(), self.char_commands(),
                self.char_skills(), self.abil_recast(),
                self.job_points(), self.job_points_detail(), self.merits(),
                self.monstrosity(), *self.merit_list(),
                sub(0x0AA, SPELL_BITS), self.char_sync(), self.party_member(),
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

    def open_nearby_doors(self) -> None:
        """Open only the nearest door, once per approach: no packet bursts."""
        nearest = None
        best = 5.0
        for entity in self.entities:
            if int(getattr(entity, "size", 0)) != 2:
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
        elif action_id == packets.ACTION_TALK:
            if target is None and self.char.get("moghouse"):
                # The Mog House's "Back to Town" door is drawn by the client from the zone
                # file, not sent as an entity, so its talk arrives with an unknown target.
                self.toggle_moghouse()
                return
            if target is not None and target.kind == "npc":
                if target.distance_to(*self.pos[:3]) > 6.0:
                    self.say("You are too far away.")
                    return
                if int(getattr(target, "size", 0)) == 2:
                    self.open_door(target)
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
                gap = target.distance_to(*self.pos[:3])
                if gap > ENGAGE_RANGE:
                    # The client can only draw within spell range.  Keep any old target
                    # rather than silently switching the engagement to an unreachable one.
                    self.say("You are too far away.")
                    if self.engaged_id:
                        self.assert_stance()
                    else:
                        self.queue.append(self.char_update(packets.SEND_HP))
                    return
                # Retail accepts /attack at any range inside draw range: the character
                # draws and walks in.  Engaging on its own is not enmity, though -- the mob
                # does not fight back until you actually hit it or provoke it, so
                # engaged_char_id is left alone here and set by the first swing.
                # The client also re-sends /attack when it picks the target back up after
                # its own range disengage; that is the same engagement, not a new one, so
                # it must not repeat the chat line or delay the next swing.
                same_target = self.engaged_id == int(target.id)
                self.engaged_id = int(target.id)
                self.engaged_targid = int(target.targid)
                # Any /attack ends the "second press" window: the client re-sends it when
                # it picks the target back up, and the next out-of-range packet is then a
                # fresh automatic disengage, not a player double-tapping /attackoff.
                self.range_disengage_at = 0.0
                if not same_target:
                    self.range_disengage_hinted = False
                    self.next_attack_at = time.time() + 0.5
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
            now = time.time()
            target = self.engaged_target()
            gap = (target.distance_to(*self.pos[:3])
                   if target is not None and target.alive else None)
            # The client sheathes by itself as soon as the target leaves auto-attack
            # reach (four yalms).  That is not a request to end the fight: retail keeps
            # the engagement out to draw range, and this is what lets a melee player kite
            # with the weapon out.  Ignore the first distance-driven packet and re-assert
            # the stance; a second one within a moment, or !disengage, still breaks it.
            # The half-yalm of slack covers the client's own rounding at the boundary.
            if (gap is not None and MELEE_RANGE - 0.5 < gap <= ENGAGE_RANGE
                    and now - self.range_disengage_at > 1.5):
                self.range_disengage_at = now
                self.next_attack_at = now + 0.5
                self.assert_stance()
                if not self.range_disengage_hinted:
                    self.range_disengage_hinted = True
                    self.say("You stay engaged at range; use !disengage to break it.")
                return
            self.range_disengage_at = 0.0
            self.disengage("You disengage." if self.engaged_id else None)
        elif action_id == packets.ACTION_CHANGE_TARGET:
            self.target_targid = int(act_index)

    def item_use(self, p: bytes) -> None:
        """C2S 0x037: use a working-stock medicine.

        Dawn Mulsum is a pet medicine: it restores 25-50% of the pet's maximum HP and
        does not touch GEO Luopans.  The server has no pet HP model yet, so without a
        ``pet_hp_max`` on the character it reports that there is no pet to heal; the
        item is still consumed and refilled from the locker.
        """
        if len(p) < 12:
            return
        item_id = struct.unpack_from("<I", p, 8)[0]
        if item_id != 5411:
            return
        consumed = self.world.service.consume_inventory_item(
            int(self.char["id"]), item_id)
        if consumed is None:
            self.say("You do not have that item.")
            return
        quantity = int(consumed["quantity"])
        self.queue.append(sub(0x020, packets.item_attr(
            item_id if quantity else 0, quantity, 0, int(consumed["slot"]))))

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
        now = time.time()
        if self.casting and now < self.casting["finish"]:
            return
        ninjutsu = int(spell["skill"]) == NINJUTSU_SKILL
        cost = 0 if ninjutsu else int(spell["mp"])
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
        level = int(self.char.get("main_level", 1))
        sheet = self.stat_sheet()
        skill_values, _base_caps = self.effective_skills()
        spell_skill = int(skill_values.get(int(spell["skill"]), 0))
        target_sheet = self.world.monster_sheet(target) if target is not None else None
        if healing:
            amount = int(cost * 3 + level)
        elif int(spell["base"]) > 0 and target_sheet is not None:
            amount = combat.magic_damage(
                base=int(spell["base"]), multiplier=float(spell["multiplier"]),
                caster_int=int(sheet.attributes.get("int", 0)),
                target_int=int(target_sheet.attributes.get("int", 0)),
                skill=spell_skill, mods=sheet.fighter.mods,
                target_mods=target_sheet.fighter.mods,
                target_level=int(target_sheet.fighter.level))
        elif int(spell["base"]) > 0:
            # No enemy target (a self-targeted spell with a damage base): keep the old
            # fallback, there is nothing to resist or apply Magic Defence against.
            amount = int(int(spell["base"]) * float(spell["multiplier"]) + level // 2)
        else:
            amount = int(cost * 2 + level // 3)
        if not ninjutsu:
            self.char["mp_current"] = int(self.char.get("mp_current", 0)) - cost
        fast_cast = int(sheet.fighter.mods.get(mod.FASTCAST, 0))
        # Enfeebles share the Magic Accuracy roll: an under-geared caster keeps the
        # effect for less time instead of the spell always landing at full duration.
        resist = 1.0
        if target_sheet is not None:
            resist = combat.magic_resist(
                skill=spell_skill, caster_int=int(sheet.attributes.get("int", 0)),
                mods=sheet.fighter.mods,
                target_level=int(target_sheet.fighter.level),
                target_mods=target_sheet.fighter.mods)
        self.casting = {"spell": spell, "target": int(target.id) if target else 0,
                        "finish": now + combat.cast_time(
                            int(spell["cast_time"]), fast_cast) / 1000.0,
                        "amount": max(1, amount), "healing": healing,
                        "self": self_cast, "effect": spec,
                        "skill": int(spell["skill"]), "resist": resist}
        self.stop_resting()
        self.queue += [self.char_stats(), self.char_status()]
        try:
            self.world.service.save_vitals(self.char["id"], int(self.char.get("hp_current", 0)),
                                           int(self.char.get("mp_current")))
        except Exception:
            pass
        # 0x028 MagicStart: this is what puts the cast bar and the casting animation on the
        # client.  The value is the spell id; cmd_arg is the school's four-character code
        # (canj for ninjutsu, cawh for white magic, ...), not the spell id.
        actor = int(self.char["char_id"])
        start_target = int(target.id) if target is not None else actor
        self.queue.append(sub(0x028, packets.battle_action(
            actor, start_target, int(spell["id"]), animation=0,
            message=packets.MESSAGE_MAGIC_STARTS_CASTING, kind=0,
            category=packets.ACTION_CATEGORY_MAGIC_START,
            action_id=packets.magic_cast_arg(int(spell["skill"])), info=0)))
        self.say("You start casting %s." % spell["name"])

    def resolve_casting(self, now: float) -> None:
        """Apply a finished cast: a buff, a debuff, damage, or a heal."""
        if not self.casting or now < self.casting["finish"]:
            return
        cast = self.casting
        self.casting = None
        spell = cast["spell"]
        spec = cast.get("effect")
        me = int(self.char["char_id"])
        if cast["healing"]:
            hp = int(self.char.get("hp_current", 0))
            healed = min(int(self.char.get("hp", hp)), hp + int(cast["amount"]))
            self.char["hp_current"] = healed
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, healed - hp, animation=int(spell["id"]), kind=0,
                message=packets.MESSAGE_MAGIC_RECOVERS_HP, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.queue += [self.char_status(), self.party_member()]
            try:
                self.world.service.save_vitals(self.char["id"], healed,
                                               int(self.char.get("mp_current", 0)))
            except Exception:
                pass
            self.assert_stance()
            return
        if cast.get("self"):
            self.resolve_self_spell(spell, now, spec)
            if self.engaged_id and not self.zoning:
                self.assert_stance()
            return
        entity = self.world.entity_by_id(self.zone, int(cast["target"]))
        if entity is None or not entity.alive:
            self.say("The spell fizzles.")
            self.assert_stance()
            return
        self._last_target_hp = entity.hp_max
        if effects.is_debuff(spec):
            remaining = self.world.apply_mob_effect(
                entity, spec, self, now, duration_scale=float(cast.get("resist", 1.0)))
            if remaining:
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(entity.id), int(spec.effect), animation=int(spell["id"]),
                    kind=0, message=packets.MESSAGE_MAGIC_ENFEEB, info=0,
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
            else:
                self.queue.append(sub(0x028, packets.battle_action(
                    me, int(entity.id), 0, animation=int(spell["id"]), kind=0,
                    message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
                    category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                    action_id=int(spell["id"]))))
            self.assert_stance()
            return
        if spec is not None and spec.kind == "special":
            self.resolve_special_spell(spell, entity, cast)
            self.assert_stance()
            return
        damage = int(cast["amount"])
        defeated = entity.hp - damage <= 0
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(entity.id), damage, defeated=defeated,
            animation=int(spell["id"]), kind=0,
            message=packets.MESSAGE_MAGIC_DMG, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=int(spell["id"]))))
        entity.hp = max(0, entity.hp - damage)
        self.queue_entity(entity, packets.SEND_HP)
        self.world.wake_mob(entity)
        if defeated:
            self.world.kill_mob(self, entity, now)
        self.assert_stance()

    def resolve_special_spell(self, spell: dict, entity, cast: dict) -> None:
        """Drain, Aspir and Dispel: the spells whose result is not a plain damage hit."""
        me = int(self.char["char_id"])
        name = str(spell["name"])
        folded = name.casefold()
        if folded.startswith("dispel"):
            removed = self.world.dispel_mob(entity)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), removed, animation=int(spell["id"]), kind=0,
                message=(packets.MESSAGE_MAGIC_ENFEEB if removed
                         else packets.MESSAGE_MAGIC_NO_EFFECT), info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=int(spell["id"]))))
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
                me, int(entity.id), amount, animation=int(spell["id"]), kind=0,
                message=packets.MESSAGE_MAGIC_DRAIN_MP,
                info=0, category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            return
        if folded.startswith("drain"):
            amount = max(1, int(cast["amount"]))
            mp = int(self.char.get("mp_current", 0))
            hp = int(self.char.get("hp_current", 0))
            healed = min(int(self.char.get("hp", hp)), hp + amount)
            self.char["hp_current"] = healed
            entity.hp = max(0, entity.hp - amount)
            self.queue.append(sub(0x028, packets.battle_action(
                me, int(entity.id), amount, animation=int(spell["id"]), kind=0,
                message=packets.MESSAGE_MAGIC_DRAIN_HP,
                info=0, category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.queue_entity(entity, packets.SEND_HP)
            self.queue += [self.char_status(), self.party_member()]
            if entity.hp <= 0:
                self.world.kill_mob(self, entity, time.time())
            return
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(entity.id), 0, animation=int(spell["id"]), kind=0,
            message=packets.MESSAGE_MAGIC_NO_EFFECT, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=int(spell["id"]))))

    def weaponskill(self, p: bytes, act_index: int = 0) -> None:
        """C2S 0x01A action 0x07: a weapon skill.

        The body carries the skill id after UniqueNo/ActIndex/ActionId.  The server only
        accepts a skill that is on the character's current list, which is the equipped
        weapon's type at or below the character's skill value; that is the same list
        sent to the client in char_abilities() (packet 0x0AC).
        """
        if len(p) < 16:
            return
        ws_id = struct.unpack_from("<I", p, 12)[0]
        try:
            ws = self.world.service.weaponskill(ws_id)
        except Exception as exc:
            log.warning("%s weapon skill lookup failed: %s", self.addr, exc)
            return
        if ws is None:
            self.say("That weapon skill does not exist.")
            return
        try:
            available = set(self.equipped_weapon_skills())
        except Exception as exc:
            log.warning("%s weapon skill availability failed: %s", self.addr, exc)
            available = set()
        if int(ws_id) not in available:
            self.say("You cannot use %s with your equipped weapon." % ws["name"])
            return
        entity = None
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
        # Weapon skills spend every point of TP and scale with what you spent.  The
        # scale rides on the same engine, so crit, fSTR and pDIF all still apply.
        ftp = 1.5 + 1.5 * tp / TP_MAX
        miss, damage, critical = self.world.player_attack(self, entity, ftp=ftp)
        defeated = (not miss) and entity.hp - damage <= 0
        self._last_target_hp = entity.hp_max
        self.char["tp"] = 0
        self.queue.append(self.party_member())
        me = int(self.char["char_id"])
        self.queue.append(sub(0x028, packets.battle_action(
            me, int(entity.id), damage, miss=miss, critical=critical, defeated=defeated,
            animation=int(ws["animation"]), kind=3,
            category=packets.ACTION_CATEGORY_SKILL_FINISH, action_id=int(ws["id"]))))
        self.say("%s strikes %s for %d points of damage." % (ws["name"], entity.name, damage))
        if not miss:
            entity.hp = max(0, entity.hp - damage)
            self.queue_entity(entity, packets.SEND_HP)
            if defeated:
                self.world.kill_mob(self, entity, now=time.time())
        self.next_attack_at = time.time() + 2.0

    def job_ability(self, p: bytes, act_index: int = 0) -> None:
        """C2S 0x01A action 0x09: a job ability.

        The body carries the ability id after UniqueNo/ActIndex/ActionId, exactly like a
        weapon skill.  The 0x028 reply is cmd_no 6 (Ability Finish), whose result kind is
        2 and whose sub-kind is the ability's animation id; message 100 prints
        "<player> uses <ability>."

        Effects are intentionally small: Provoke claims the mob, Meditate and Chakra move
        TP/HP, Convert swaps HP and MP, and the healing waltzes heal.  Everything else
        plays its animation and reports the use, so none of the menu entries is a dead
        end.  Recasts are tracked by recast id and sent in 0x119.
        """
        if len(p) < 16:
            return
        ability_id = struct.unpack_from("<I", p, 12)[0]
        try:
            ability = self.world.service.job_ability(ability_id)
        except Exception as exc:
            log.warning("%s job ability lookup failed: %s", self.addr, exc)
            return
        if ability is None:
            self.say("That job ability does not exist.")
            return
        name = str(ability["name"])
        now = time.time()
        recast_id = int(ability.get("recast_id") or 0)
        if recast_id and self.ability_recasts.get(recast_id, 0.0) > now:
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
        me = int(self.char["char_id"])
        target_id = int(target.id) if target is not None else me
        self.queue.append(sub(0x028, packets.battle_action(
            me, target_id, 0, animation=int(ability.get("animation") or 0),
            message=packets.MESSAGE_USES_JOB_ABILITY, kind=2,
            category=packets.ACTION_CATEGORY_ABILITY_FINISH,
            action_id=int(ability_id))))

        # The handful of abilities with a visible state change.
        if ability_id == 35 and target is not None:          # Provoke
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
            self.char["hp_current"] = int(self.char["hp"])
            self.char["mp_current"] = int(self.char.get("mp", 0))
            self.queue += [self.char_status(), self.party_member()]
        elif ability_id == 38:                               # Chakra
            self._heal_job_ability(max(1, int(self.char["hp"]) // 4))
        elif ability_id == 63:                               # Meditate
            self.gain_tp(1000)
            self.queue.append(self.party_member())
        elif ability_id == 83:                               # Convert
            hp = int(self.char.get("hp_current", 0))
            mp = int(self.char.get("mp_current", 0))
            self.char["hp_current"] = min(int(self.char["hp"]), mp)
            self.char["mp_current"] = min(int(self.char.get("mp", 0)), hp)
            self.queue += [self.char_stats(), self.char_status(), self.party_member()]
        elif ability_id in (190, 191, 192, 193, 311):        # Curing Waltz I..V
            self._heal_job_ability(max(1, int(self.char["hp"]) * (8 + ability_id % 10) // 100))
        elif ability_id in (194, 195, 262):                  # Healing/Divine Waltz
            self._heal_job_ability(max(1, int(self.char["hp"]) // 10))
        elif ability_id in (24, 72, 78, 85, 225, 281, 282):
            # Familiar, Sic, Reward, Call Beast, Snarl, Spur, Run Wild: these act on a
            # pet, and Fanxi has no pet model yet.  The use still plays so the menu is not
            # a dead end, and the line says why nothing else happened.
            self.say("You have no pet for %s." % name)
        else:
            self.say("You use %s." % name)

        if recast_id:
            self.ability_recasts[recast_id] = now + max(0, int(ability.get("recast") or 0))
            self.queue.append(self.abil_recast())
        try:
            self.world.service.save_vitals(
                self.char["id"], int(self.char.get("hp_current", 0)),
                int(self.char.get("mp_current", 0)))
        except Exception:
            pass

    def _heal_job_ability(self, amount: int) -> None:
        """Add HP (capped at the maximum) and keep the client's gauges in step."""
        hp = int(self.char.get("hp_current", 0))
        healed = min(int(self.char["hp"]), hp + max(0, int(amount)))
        self.char["hp_current"] = healed
        self.queue += [self.char_status(), self.party_member()]
        self.say("You recover %d HP." % (healed - hp))

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
                me, me, 0, animation=int(spell["id"]), kind=0, info=0,
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
                me, me, 0, animation=int(spell["id"]), kind=0, info=0,
                message=packets.MESSAGE_MAGIC_NO_EFFECT,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.say("%s finds no fallen player to target." % name)
            return
        if spec is not None and spec.kind == "buff":
            self.add_effect(spec.effect, duration=spec.duration, power=spec.power,
                            potency=spec.potency, tick=spec.tick, icon=spec.icon,
                            mods=spec.mods)
            self.queue.append(sub(0x028, packets.battle_action(
                me, me, int(spec.effect), animation=int(spell["id"]), kind=0,
                message=packets.MESSAGE_MAGIC_GAIN_EFFECT, info=0,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))))
            self.queue.append(self.char_status())
            if self.resting:
                self.stop_resting()
            return
        # A support spell with no tracked effect: finish it without a damage result.
        self.queue.append(sub(0x028, packets.battle_action(
            me, me, 0, animation=int(spell["id"]), kind=0,
            message=0, info=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))))
        self.say("%s takes hold." % name)

    def request_entity(self, p: bytes) -> None:
        if len(p) < 8:
            return
        act = struct.unpack_from("<H", p, 4)[0]
        if act == TARGID:
            self.queue += [self.char_update(), self.char_status()]
            return
        entity = self.world.entity_by_targid(self.zone, act)
        if entity is not None:
            self.queue_spawn(entity)

    def gain_tp(self, tenths: int) -> None:
        """Add TP and refresh the bar.  TP is kept in tenths, the client's own unit."""
        current = int(self.char.get("tp", 0))
        tp = min(TP_MAX, current + max(0, int(tenths)))
        if tp == current:
            return
        self.char["tp"] = tp
        self.queue.append(self.party_member())

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
        self.char["hp_current"] = max(0, int(self.char.get("hp_current", self.char["hp"])) - int(amount))
        self.queue += [self.char_status(), self.party_member()]
        # Retail also pays TP for damage taken, scaled to how much of your HP the hit took.
        self.gain_tp(1000 * int(amount) // max(1, int(self.char["hp"])))
        try:
            self.world.service.save_vitals(self.char["id"], self.char["hp_current"], self.char.get("mp_current", 0))
        except Exception:
            pass
        if int(self.char["hp_current"]) <= 0:
            self.dead_until = time.time() + 6.0
            self.engaged_id = None
            self.engaged_targid = 0
            self.queue.append(self.char_update(packets.SEND_HP))
            self.say("You have been defeated. You recover in a moment.")
            try:
                self.world.service.record_death(self.char["id"])
            except Exception:
                pass

    def tick_regen(self, now: float) -> None:
        """Apply Auto Refresh/Auto Regen (and gear Refresh/Regen) once per 3 seconds.

        These are passive modifiers, not status effects: the client draws no icon for
        them.  The tick uses the same merged modifier dict as the stat sheet, so the
        traits and gear both feed it.  ``REGEN_DOWN``/``REFRESH_DOWN`` come first, and a
        negative total never drains the character.
        """
        if now < self.next_regen_tick:
            return
        self.next_regen_tick = now + traits.TICK_SECONDS
        if (self.zoning or not self.zone_loaded or self.dead_until
                or int(self.char.get("hp_current", 0)) <= 0):
            return
        mods = self.combat_mods()
        regen = max(0, int(mods.get(mod.REGEN, 0)) - int(mods.get(mod.REGEN_DOWN, 0)))
        refresh = max(0, int(mods.get(mod.REFRESH, 0))
                      - int(mods.get(mod.REFRESH_DOWN, 0)))
        if regen <= 0 and refresh <= 0:
            return
        changed = False
        hp = int(self.char.get("hp_current", 0))
        hp_max = max(1, int(self.char.get("hp", 1)))
        if regen > 0 and hp < hp_max:
            hp = min(hp_max, hp + regen)
            self.char["hp_current"] = hp
            changed = True
        mp = int(self.char.get("mp_current", 0))
        mp_max = max(0, int(self.char.get("mp", 0)))
        if refresh > 0 and mp < mp_max:
            mp = min(mp_max, mp + refresh)
            self.char["mp_current"] = mp
            changed = True
        if not changed:
            return
        self.queue += [self.char_status(), self.party_member()]
        try:
            self.world.service.save_vitals(int(self.char["id"]), hp, mp)
        except Exception as exc:
            log.warning("%s regen tick save failed: %s", self.addr, exc)

    def tick(self, now: float) -> None:
        if (self.logged_in and not self.zoning and self.entities_sent
                and now >= self.next_entity_sync):
            self.next_entity_sync = now + 1.0
            self.sync_nearby_entities()
        if (self.logged_in and not self.zoning and self.zone_loaded and self.entities_sent
                and now >= self.next_player_sync):
            self.next_player_sync = now + 1.0
            self.sync_players()
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
            self.queue += [sub(0x0AA, SPELL_BITS), self.job_info(),
                           self.char_feats(), self.char_abilities(), self.char_commands(),
                           self.char_skills(), self.abil_recast()]
            log.info("%s re-sent equipment and command data (%d retries left)", self.addr,
                     len(self.abilities_retries))
        self.resolve_casting(now)
        self.tick_player_effects(now)
        self.tick_rest(now)
        self.tick_regen(now)
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
        if (self.logged_in and self.zone_loaded and now - self.last_packet_at > 8.0
                and now - self.last_release_at > 8.0):
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
        # The client can drop the battle stance on its own (a target change, a refused
        # action).  Two small packets every ten seconds keep the weapon drawn; the host's
        # 0x00D hook then follows the real state instead of guessing.
        if not self.casting and now - getattr(self, "stance_at", 0.0) >= 10.0:
            self.assert_stance()
        entity = self.world.entity_by_id(self.zone, int(self.engaged_id))
        # Diagnostic: one line a second while engaged, showing which branch would run.
        if now - getattr(self, "engage_log_at", 0.0) >= 1.0:
            self.engage_log_at = now
            log.info("%s engage: id=%#x found=%s alive=%s gap=%s next_in=%.2f hp=%s",
                     self.addr, int(self.engaged_id), entity is not None,
                     getattr(entity, "alive", None),
                     "n/a" if entity is None else "%.1f" % entity.distance_to(*self.pos[:3]),
                     -1.0 if entity is None else self.next_attack_at - now,
                     "n/a" if entity is None else getattr(entity, "hp", None))
        if entity is None or not entity.alive:
            # The target died or left: drop the stance, or the character keeps its weapon
            # out (and the client keeps the attack animation) forever.
            self.disengage()
            return
        gap = entity.distance_to(*self.pos[:3])
        if gap > ENGAGE_RANGE:
            # Past draw range the fight is over.  The client would have dropped its own
            # attack at the old four-yalm reach; this leash is the one the server keeps.
            self.disengage("You lose your target.")
            return
        if gap > MELEE_RANGE:
            # Engaged but out of reach: keep the target, swing once we are close enough.
            # Retail does not drop the engagement just because the mob is far away -- you
            # stay in battle stance and walk to it.  The client's own /attack off at this
            # range was ignored already (ACTION_ATTACK_OFF), so it is still in TP gear.
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
        # A dual-wield round is two swings: main hand first, then the off hand, each
        # with its own weapon, Accuracy and damage.  The client animates them from the
        # result's sub-kind (0 main, 1 off hand).
        self._swing(entity, sheet, now)
        if sheet.sub_fighter is not None and entity.alive:
            self._swing(entity, sheet, now, off_hand=True)
        self.next_attack_at = now + sheet.attack_delay_ms / 1000.0

    def _swing(self, entity, sheet, now: float, *, off_hand: bool = False) -> None:
        """Resolve one hand of an attack round and queue its client-visible result."""
        miss, damage, critical = self.world.player_attack(self, entity, off_hand=off_hand)
        defeated = (not miss) and entity.hp - damage <= 0
        self.queue_action(entity.id, damage, miss=miss, critical=critical,
                          defeated=defeated, animation=1 if off_hand else 0)
        # Swinging is the enmity that makes a mob fight back -- including a miss.
        if entity.engaged_char_id != int(self.char["char_id"]):
            entity.engaged_char_id = int(self.char["char_id"])
            entity.next_attack_at = now + 1.5
        if miss:
            return
        # Attacking breaks Sneak and Invisible, as it does in retail.
        for stealth in (effects.SNEAK, effects.INVISIBLE):
            if self.remove_effect(stealth):
                self.queue.append(self.char_status())
        self.world.wake_mob(entity)
        entity.hp = max(0, entity.hp - damage)
        self.queue_entity(entity, packets.SEND_HP)
        store_tp = int(sheet.fighter.mods.get(mod.STORETP, 0))
        self.gain_tp(combat.tp_gain(sheet.tp_per_hit, store_tp))
        if defeated:
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
        total = int(stock["price"]) * quantity
        if int(self.char.get("gil", 0)) < total:
            self.say("You do not have enough gil.")
            return
        try:
            self.world.service.set_gil(self.char["id"], int(self.char["gil"]) - total)
            self.world.service.add_item(self.char["id"], int(stock["item_id"]), quantity)
        except Exception as exc:
            self.say("The purchase could not be completed: %s" % exc)
            return
        self.char["gil"] = int(self.char.get("gil", 0)) - total
        self.queue.append(sub(0x03F, packets.shop_buy(index, quantity)))
        self.refresh_inventory()
        item = self.world.service.item(int(stock["item_id"]))
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
            # A zero model would draw the naked default for that slot; fall back to the
            # real gear so a character saved before a slot was locked still looks whole.
            for kind in STYLE_SLOTS:
                if not model[kind]:
                    model[kind] = self._current_models()[kind]
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
        return sub(0x01C, packets.item_max())

    def login_packet(self) -> Msg:
        c = self.char
        now = int(time.time())
        x, y, z, rot = self.pos
        b = bytearray(0x100)
        struct.pack_into("<IHBbfff", b, 0x00, c["char_id"], TARGID, 0, (int(rot) + 128) % 256 - 128, x, y, z)
        hpp = gauge_percent(c.get("hp_current", c["hp"]), c["hp"])
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, hpp, 0)
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
        b[0x64:0x68] = b"\xff\xff\xff\xff"  # mastery flags
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
            value = (index & 0x1F) | (job << 5) | (0 << 16) | (20 << 26)
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
        struct.pack_into("<iiBBBBhh", b, 0, int(sheet.max_hp), int(sheet.max_mp),
                         c["main_job"], c["main_level"], c["sub_job"],
                         c["sub_level"], int(c.get("exp", 0)) & 0x7FFF,
                         int(c.get("exp_next", 1000)) & 0x7FFF)
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
        struct.pack_into("<HHHH", b, 0x40, 0, 1, 0, self.zone)
        b[0x4C] = c["nation"]
        # iLvl display and master-level info for the current job.
        b[0x50] = b[0x51] = b[0x52] = b[0x53] = 119
        b[0x60] = c["main_job"] & 0xFF
        b[0x61] = 50
        b[0x62] = 1
        struct.pack_into("<I", b, 0x64, 0)
        struct.pack_into("<I", b, 0x68, 0xFFFFFFFF)
        return sub(0x061, b)

    def effective_skills(self) -> tuple[dict[int, int], dict[int, int]]:
        """(skill value after merits and gear, the job's own cap before them).

        Both the 0x062 skill menu and the Weapon Skills filter read this, so a WS
        requirement is checked against the same number the character sees.
        """
        c = self.char
        caps = dict(skills.caps_for(int(c["main_job"]), int(c["main_level"]),
                                    int(c.get("sub_job", 0)), int(c.get("sub_level", 0))))
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

    def refresh_vitals(self) -> None:
        """Recompute max HP/MP from the sheet and keep the stored row in step.

        HP and MP maxima are not a stored truth: they follow race, job, level, subjob and
        the HP/MP on the equipped gear.  Every path that can change any of those calls
        this, so ``char["hp"]`` stays the number the client is told.
        """
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

    def combat_mods(self) -> dict[int, int]:
        """Gear, job-trait and HP/MP-merit modifiers, merged.

        Traits use the same modifier ids as gear, so adding them here means every stat
        the sheet already derives (Attack, Defense, Accuracy, Evasion, maximum HP/MP and
        the damage-taken family) sees them.  If the equipment query fails the traits are
        still applied rather than losing the passives as well.
        """
        mods: dict[int, int] = {}
        try:
            mods = dict(self.world.service.equipped_mods(int(self.char["id"])))
        except Exception as exc:
            log.warning("%s equipment stats unavailable: %s", self.addr, exc)
        for mod_id, value in self.trait_mods().items():
            mods[int(mod_id)] = int(mods.get(int(mod_id), 0)) + int(value)
        # Temporary buffs such as Protect and Haste use the same modifier ids.
        for state in self.effect_state.values():
            for mod_id, value in (state.get("mods") or {}).items():
                mods[int(mod_id)] = int(mods.get(int(mod_id), 0)) + int(value)
        # Bought HP/MP merits are part of the maximum too.  Without this, a zone-in,
        # gear change or job change recomputes the sheet and silently drops them.
        counts = self.merit_counts()
        for merit_id, mod_id in ((0x0040, mod.HP), (0x0042, mod.MP)):
            count = int(counts.get(merit_id, 0))
            entry = merits.MERITS.get(merit_id)
            if count > 0 and entry is not None:
                mods[mod_id] = int(mods.get(mod_id, 0)) + count * int(entry[3])
        return mods

    def stat_sheet(self):
        """The character's combat stats: base attributes, gear, Attack, Defense, Acc, Eva.

        Built fresh on every call.  It is two indexed queries over the equipped set plus
        some arithmetic, and building it beats caching it: the cache would have to be
        invalidated by equipment, level, merits and gear skill bonuses, and a stale stat
        sheet is a bug that shows up as mysterious damage.
        """
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
                                ilvl_skill=int(row.get("ilvl_skill") or 0))

        skill_values, _base = self.effective_skills()
        sub_row = weapons.get(stats.SLOT_SUB) or {}
        return stats.build_character(
            self.char, mods, skill_values,
            weapon_of(stats.SLOT_MAIN), weapon_of(stats.SLOT_SUB),
            shield_size=int(sub_row.get("shield_size") or 0),
            # Only the job trait lets the off hand swing; gear "Dual Wield +" just
            # lowers the delay once the trait is there.
            dual_wield=self.trait_mods().get(mod.DUAL_WIELD, 0) > 0)

    def char_skills(self) -> Msg:
        # 0x062 CLISTATUS2: 31 command recasts (uint32), then 64 skill values (uint16).
        # 0x8000 is the client's "capped" bit: it draws a capped skill in blue.  The
        # same bit on a slot with no name hidden (the automaton skills) keeps its row
        # out of the menu.  The low 15 bits are the value.
        c = self.char
        body = bytearray(252)
        for skill_id in range(64):
            struct.pack_into("<H", body, 124 + skill_id * 2, 0x8000)
        # Crafting and the other non-menu skills are real zeroes, not hidden.
        for skill_id in range(48, 60):
            struct.pack_into("<H", body, 124 + skill_id * 2, 0)
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
        try:
            ja_ids = self.world.service.job_ability_ids(
                int(self.char.get("main_job", 0)), int(self.char.get("main_level", 1)),
                int(self.char.get("sub_job", 0)), int(self.char.get("sub_level", 0)))
        except Exception as exc:
            log.warning("%s job feat list unavailable: %s", self.addr, exc)
            ja_ids = ()
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
        try:
            ja_ids = self.world.service.job_ability_ids(
                int(self.char.get("main_job", 0)), int(self.char.get("main_level", 1)),
                int(self.char.get("sub_job", 0)), int(self.char.get("sub_level", 0)))
        except Exception as exc:
            log.warning("%s job command update unavailable: %s", self.addr, exc)
            ja_ids = ()
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
        out of the menu.
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
        return sorted(ids)

    def char_abilities(self) -> Msg:
        """0x0AC COMMAND_DATA: the weapon skills and job abilities the client may list.

        The first block carries only the equipped weapon's skills that the character's
        skill value qualifies for (``equipped_weapon_skills``); the second carries the
        main and sub job's abilities from ``job_abilities``.  The 2025-07-03 client's menu
        is not built from this bitmap directly: it keeps a saved command-id list.  host64
        rebuilds that list from each 0x0AC packet (``host/addons/hooks.c``), so the packet
        is also re-sent after the 0x061 "stats please" reply, on short timers, after
        equipment changes and from ``!abilities``.
        """
        try:
            ws_ids = self.equipped_weapon_skills()
        except Exception as exc:
            log.warning("%s weapon skill list unavailable: %s", self.addr, exc)
            ws_ids = ()
        try:
            ja_ids = self.world.service.job_ability_ids(
                int(self.char.get("main_job", 0)), int(self.char.get("main_level", 1)),
                int(self.char.get("sub_job", 0)), int(self.char.get("sub_level", 0)))
        except Exception as exc:
            log.warning("%s job ability list unavailable: %s", self.addr, exc)
            ja_ids = ()
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

    def char_status(self) -> Msg:
        c = self.char
        b = bytearray(0x5C)
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
        flags0 = (self.female() << 8) | ((c["size"] & 3) << 11) | (hpp << 16)
        flags1 = (c["speed"] & 0xFFF) | (40 << 17)
        struct.pack_into("<III", b, 0x20, c["char_id"], flags0, flags1)
        struct.pack_into("<II", b, 0x38, 60 * 360, int(time.time()) - VANA_EPOCH + self.world.clock + 360)
        b[0x54] = 0x10
        return sub(0x037, b)

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
        # 0x1B is the entity animation: 1 is the drawn-weapon battle stance, 0 is idle.
        animation = 1 if self.engaged_id else 0
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, hpp, animation)
        struct.pack_into("<I", b, 0x1C, ((c["size"] & 3) << 9) | (self.female() << 15))
        b[0x3F] = 10
        struct.pack_into("<9H", b, 0x44, *self.looks())
        b[0x56:0x66] = cstr(c["name"], 16)
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
        if next_id:
            self.server_id = (self.server_id + 1) & 0xFFFF
        h = bytearray(client_hdr[:HDR])
        struct.pack_into("<HH", h, 0, self.server_id, self.client_id)
        if os.environ.get("FANXI_ZONE_ECHO_TIME") != "1":
            struct.pack_into("<I", h, 8, int(time.time()))
        data, nbits, zone_out = self.pack()
        data += struct.pack("<I", nbits)
        data += md5(data)
        out = h + data
        self.cipher.run(out, HDR, (len(data) // 4) & ~1, True)
        if DEBUG:
            log.info("%s out #%d %d bytes (client #%d) hdr %s", self.addr, self.server_id,
                     len(out), self.client_id, bytes(out[:HDR]).hex())
        self.last = out
        if zone_out:
            self.bump_key()
            with self.world.lock:
                # Database id: the next 0x00A may name the character by either id.
                self.world.by_char[int(self.char["id"])] = self
            self.queue.clear()
        return bytes(out)

    def pack(self) -> tuple[bytes, int, bool]:
        body = bytearray()
        zone_out = False
        while self.queue:
            p = self.queue[0]
            if len(body) + len(p) > 700 and body:
                break
            self.queue.pop(0)
            struct.pack_into("<H", p, 2, self.server_id)
            if DEBUG:
                log.info("%s out %03X %d bytes", self.addr,
                         struct.unpack_from("<H", p, 0)[0] & 0x1FF, len(p))
            body += p
            zone_out = zone_out or p.zone_out
        data, nbits = self.world.huff.compress(bytes(body))
        return data, nbits, zone_out

    def resend(self) -> bytes:
        struct.pack_into("<H", self.last, 2, self.client_id)
        struct.pack_into("<I", self.last, 8, int(time.time()))
        return bytes(self.last)
