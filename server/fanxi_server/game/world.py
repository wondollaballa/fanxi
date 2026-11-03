"""The Fanxi world: zone content, live entities and the game tick.

One World is created per server process. It owns the cipher key each account's client agreed to,
the lobby-to-zone hand-off map, the content loaded from SQLite, and the timer-driven behaviour of
mobs. It never wraps a second server's code: the entity model is Fanxi's own.
"""
from __future__ import annotations

import logging
import math
import random
import socket
import struct
import threading
import time
from pathlib import Path

from ..config import Config
from ..service import FanxiService
from dataclasses import replace

from . import (
    chain, combat, dancer, effects, geomancy, job_points, modifiers as mod, mobskills,
    packets, pets, rolls, stats, trust_ai, trust_gear, trust_stats,
)
from .nav import NavCache
from .cipher import M32, VIEW_KEY, Huffman, md5, zone_cipher
from .entities import ZoneEntity, mob_from_row, npc_from_row
from .party import (
    ALLIANCE_MAX_PARTIES,
    PARTY_KIND_ALLIANCE,
    PARTY_KIND_PARTY,
    SELF_TARGID,
    Alliance,
    Party,
    PartyMember,
    PendingInvite,
)
from .packets import (
    SEND_CHAR_SPAWN,
    SEND_DESPAWN,
    SEND_HP,
    SEND_PLAYER_DESPAWN,
    SEND_POSITION,
    SEND_SPAWN,
    battle_message,
    battle_message2,
    item_num,
)

log = logging.getLogger("fanxi.world")

# Fallback positions for zones that are not in the database yet.
KNOWN_POSITIONS = {
    50: (-11.0, 2.0, -142.0, 192),   # Aht Urhgan Whitegate
    100: (-126.0, -62.0, 273.0, 99),  # West Ronfaure
    231: (0.0, 0.0, -13.0, 192),     # Northern San d'Oria
    232: (-1.0, 0.0, 44.0, 128),     # Port San d'Oria
    236: (-36.0, 7.0, -58.0, 194),   # Port Bastok
    246: (-87.0, 12.0, 116.0, 128),  # Port Jeuno
}

def heading_to_rot(dx: float, dz: float) -> int:
    """The client's rotation byte for a movement direction.

    Measured from the player's own 0x015 packets: walking with dx=+1.66, dz=+1.05 (a heading
    of 57.7 degrees by atan2(dx, dz)) the client reports rotation 233, i.e. 327.7 degrees --
    its zero is a quarter turn away from ours.  Sending atan2 directly made the client turn
    the model back every update, which is the side-to-side sway.
    """
    angle = math.atan2(dx, dz) - math.pi / 2
    return int((angle % (2 * math.pi)) / (2 * math.pi) * 256) & 0xFF


AGGRO_DISTANCE = 8.0
# Retail does not let a monster notice a player who has out-levelled it by a wide margin;
# without this every level 1 rabbit in the zone jumped a level 99 character.
AGGRO_LEVEL_SPREAD = 10
# A monster this far below the player cons "too weak" and pays no experience.
EXP_LEVEL_SPREAD = 10
DISENGAGE_DISTANCE = 30.0  # a mob drops its target this far away
MELEE_RANGE = 4.0  # retail melee reach, not a bow shot
# Retail loses the target past 30 yalms ("You lose sight of the target.") and keeps the
# engagement at any shorter distance, so a player can kite without sheathing and losing TP
# gear.  The client's own reach is only MELEE_RANGE, which is why it drops its swing out
# here; the server owns the engagement, not the client.
ENGAGE_RANGE = 30.0
# /attack to the first swing.  Retail holds the character in the draw for three seconds
# before the weapon comes down, which is what makes an engage on a distant mob readable.
ENGAGE_DELAY = 3.0
# Entities are streamed in as the player walks, the way retail does it: sending a zone's
# whole population at once floods the client's entity table.
SYNC_RANGE = 60.0
# Pets and Trusts use the client's spawnable range (0x700-0x8FF).  Every client can hold
# up to five alter egos beside its own character.
TRUST_TARGID_FIRST = 0x700
TRUST_TARGID_LAST = 0x8FF
TRUST_MAX = 5
TRUST_SPAWN_DISTANCE = 2.0
TRUST_FOLLOW_DISTANCE = 2.5
TRUST_WARP_DISTANCE = 25.0
TRUST_REACH = 3.5
TRUST_CHASE_SPEED = 6.2
TRUST_LEASH = 40.0
# The client collides the player with its own pets and alter egos, and one standing on the
# character blocks every step: the player cannot walk out because the blocker is inside the
# collision radius.  A Trust or pet this close to a player steps out of the bubble instead
# of standing in it (slower than the chase step: this is a nudge, not a sprint).  The client
# has no "walk through party" switch this server can set, so the way to get the same feel is
# to keep the team out of the player's feet.
TRUST_PERSONAL_SPACE = 1.2
TRUST_SIDE_STEP_SPEED = 3.0
# How often a live Trust re-reads its owner's gear rating, so a mid-fight set
# change moves its bars without a query every beat.
TRUST_GEAR_SYNC_SECONDS = 20.0
# Below this HP percentage the Trust heals first and puts the aura up afterwards.
TRUST_CURE_DANGER_PERCENT = 40
# Player characters use the client's PC targid range (0x400-0x6FF). 0x400 is the local
# player in its own view; every other character gets one of these from World.
PLAYER_TARGID_FIRST = 0x401
PLAYER_TARGID_LAST = 0x6FF
# The reference spawns other players at 45 yalms and despawns them at 50.
PLAYER_SPAWN_RANGE = 45.0
PLAYER_DESPAWN_RANGE = 50.0
MOB_WALK_SPEED = 2.0  # yalms per second, matched to the client's walk cycle
MOB_REACH = 3.5  # how close a mob must be before its swing can land
MOB_CHASE_SPEED = 6.0  # a mob closing on its target runs, it does not amble
# The client interpolates an NPC between 0x00E position updates using the speed byte, so
# the packet is a correction, not the animation.  The speed byte must be the server's
# actual speed (12 is 2 yalms/s walking, 36 is 6 yalms/s running), and the gap between
# packets has to keep the straight line the client draws away from walls:
#
# * a walking roamer is corrected every 250 ms (0.5 yalm of interpolation);
# * a chasing mob is corrected every 100 ms (0.6 yalm) because it is running and may
#   turn a corner -- and there are only one or two of those, not a zone full;
# * `_mob_follow` flags a real corner (not every 1.5-yalm nav-grid kink), and that one
#   packet goes out immediately so the client never draws a straight line across it.
#
# Position updates are also a separate budget from spawning: a mob beyond
# MOB_SYNC_RANGE is a few pixels tall and does not need the full rate.  Within
# MOB_URGENT_RANGE a turn or a stop is sent immediately; farther out it waits for the
# ambient budget, because that is not where the player is looking.  A stop still reaches
# every client that has the entity spawned (SYNC_RANGE), so nothing freezes mid-stride.
MOB_SYNC_RANGE = 35.0
MOB_URGENT_RANGE = 25.0
MOB_SYNC_INTERVAL = 0.25      # walking roamer
MOB_SYNC_INTERVAL_RUN = 0.1   # chasing mob
MOB_WALK_SPEED_BYTE = 12
MOB_RUN_SPEED_BYTE = 36
# A target this far above or below a monster is on another level: a wall, a ledge or a
# bridge deck.  Retail does not let a monster aggro or swing through that gap.
MOB_VERTICAL_REACH = 4.0
# A target more than this far above or below the monster is not in melee reach even if
# the three-dimensional distance is small (standing under a low bridge, on a rock).
MOB_MELEE_VERTICAL = 2.0
# A roaming monster stays on the level it spawned on.  The nav grid knows the walkable
# surfaces, but a tomb or a cliff can have a ramp that leads from a spawn point down a
# shaft: the mob can walk it without ever crossing a wall triangle, yet the player
# cannot follow and only sees a skeleton standing on a ledge.  Four yalms is the same
# vertical reach used for aggro, so this does not stop a mob following a player up a
# gentle hill; it stops a walk into a different storey.
MOB_VERTICAL_LEASH = 4.0
# A chase is not tied to the spawn floor the way a roam leg is.  A player can pull a
# monster up a slope or down a ramp, and the monster has to follow: the old
# per-waypoint four-yalm check refused the whole route as soon as the player stood on a
# hill above or below the camp, so the pull left a red name standing still.  The chase
# is leashed to a generous sphere around the spawn instead.  Walls, cliffs and floor
# edges are still refused by the nav grid's own step and barrier tests.
MOB_CHASE_LEASH = 60.0
# The base MZB collision does not cover every cliff top in the tomb zones.  Roaming is
# capped close to the spawn so a monster cannot cross one of those visual cliffs while
# the server still thinks the floor is flat.
MOB_ROAM_RADIUS_CAP = 3.0
# Path planning.  A chase is at most DISENGAGE_DISTANCE long; this budget covers a
# detour around a rock without letting an unreachable target eat the whole tick.
MOB_NAV_NODES = 1500  # a 30-yalm chase with a detour; keeps a failed search bounded
MOB_NAV_ROAM_NODES = 800  # a roam leg is a few cells; do not search the zone for it
MOB_NAV_REPLAN = 0.5  # seconds between A* searches while a target is moving
MOB_NAV_COOLDOWN = 3.0  # after a failed search, wait this long before trying again
MOB_NAV_GOAL_MOVE = 1.0  # a target that moved this far invalidates the current path
# Enmity.  Retail keeps two meters: cumulative enmity (CE) never decays on its own,
# while volatile enmity (VE) drains 60 points a second and is what lets a tank lose the
# monster again.  Both are capped at 30,000; the target is the highest CE + VE.
ENMITY_CAP = 30000
VE_DECAY_PER_SECOND = 60.0
# The first player to generate hate on an idle monster also gets 200 CE + 900 VE.
CLAIM_CE = 200
CLAIM_VE = 900
# A zone session has no TCP connection to watch: silence is the disconnect.  The client
# sends position packets continuously, so a force-quit or a dead network is visible as a
# long gap.  Without this the character stayed in every other client's world forever.
SESSION_IDLE_TIMEOUT = 180.0
# The one legitimate silence is a zone change: the client loads the next zone and comes
# back with its zone key.  A hand-off older than this is a dead zone change.
ZONE_CHANGE_TIMEOUT = 30.0
# How long a dropped hand-off's cipher sequence is remembered.  The client keeps the key
# it advanced to until its process exits, so a relog seconds (or minutes) later must still
# be answered under that key, not the account's sign-in key.
HANDOFF_KEY_TTL = 600.0
# How many keys of that sequence to keep; matches zone.KEY_HISTORY.
HANDOFF_KEYS_KEPT = 8
# A box that was still logging in when the team was called joins the anchor when its
# zone-in completes, but only for this long: a later zone change of its own must stand.
TEAM_ANCHOR_TTL = 60.0
# `incoming` calls advance() on every client packet.  Six clients at 30 fps is ~180 calls
# a second, and each one used to run every mob/trust/party timer.  Thirty full ticks a
# second is above the client's frame rate and leaves the per-packet path to movement.
TICK_INTERVAL = 0.033
# The zone loop also flushes queues on a timer, not only when the UDP socket goes quiet.
# This is the gap between two server-initiated packets to one session, so a box whose
# owner is not typing still receives mob movement and queued results.
FLUSH_INTERVAL = 0.2


class Zones:
    def __init__(self, rows: dict[int, dict], lines: dict[int, tuple]):
        self.rows = rows
        self.lines = dict(lines)
        self.names = {int(zone): row["name"] for zone, row in rows.items()}
        self.music = {
            int(zone): (int(row["music_day"]), int(row["music_night"]),
                        int(row["music_solo"]), int(row["music_party"]))
            for zone, row in rows.items()
        }
        # Zones where the optional automatic-door mode may open a door (city and
        # outdoors).  A zone without the column or with 0 keeps retail's manual doors.
        self.auto_open_doors = {
            int(zone): bool(row.get("auto_open_doors"))
            for zone, row in rows.items()
        }

    def position(self, zone: int):
        row = self.rows.get(int(zone))
        if row is not None:
            return (float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"]), int(row["rot"]))
        if int(zone) in KNOWN_POSITIONS:
            return KNOWN_POSITIONS[int(zone)]
        for to_zone, x, y, z, rot in self.lines.values():
            if to_zone == zone:
                return (x, y, z, rot)
        return (0.0, 0.0, 0.0, 0)

    def name(self, zone: int) -> str:
        return self.names.get(int(zone), "zone %d" % int(zone))

    def music_for(self, zone: int) -> tuple:
        return self.music.get(int(zone), (0, 0, 0, 0))

    def allows_auto_doors(self, zone: int) -> bool:
        """Whether the optional automatic-door mode may run in this zone."""
        return self.auto_open_doors.get(int(zone), False)


class World:
    def __init__(self, config: Config, service: FanxiService, huffman: Huffman | None,
                 bind: str | None = None):
        self.config = config
        self.service = service
        self.huff = huffman
        # Monster combat stats depend only on level, so one sheet serves every spawn.
        self._monster_sheets: dict[int, stats.Sheet] = {}
        # character id -> (when, shared gear mods): one owner's set is read once
        # per sync beat even when several Trusts of theirs are out.
        self._trust_share_cache: dict[int, tuple[float, dict[int, int]]] = {}
        # Family TP moves, keyed by LandSandBoat's skill_list_id.  Loaded on first use:
        # most sessions never fight a monster whose list is large.
        self._mob_skill_lists: dict[int, tuple[mobskills.MobSkill, ...]] = {}
        self.bind = bind or config.bind
        self.public_name = config.public_host
        try:
            self.host_ip = socket.gethostbyname(config.public_host)
        except OSError:
            # The launcher still gets the name in /launch; the lobby needs a literal IPv4.
            self.host_ip = "127.0.0.1"
        self.ports = dict(config.ports)
        self.zones = Zones(service.zones(), service.zone_lines())
        self.server_name = service.server_name()
        self.motd = service.motd()
        self.clock = 0
        self.sessions: dict[tuple, object] = {}  # (ip, port) -> ZoneSession
        # Database character id -> the session a zone change (or the lobby) handed over
        # for the next 0x00A.  Keyed by the database id, which every client build knows.
        self.by_char: dict[int, object] = {}
        self.keys: dict[int, bytes] = {}          # account id -> the 20-byte zone key the client sent
        # Character id -> the cipher sequence a dropped hand-off was still using.  A client
        # keeps the key it advanced to, so the next 0x00A from the same game session has to
        # resume there (see parked_keys() and ZoneSession.zone_in_copies()).
        self.handoff_keys: dict[int, dict] = {}
        # character id -> the targid the other clients see it as (0x400 is "self" in each client)
        self.player_targids: dict[int, int] = {}
        self.content: dict[int, list[ZoneEntity]] = {}
        self.lock = threading.RLock()
        self.sockets: list = []
        self.udp = None
        self.rng = random.Random()
        self.last_tick = 0.0
        # Walkable grids built from the player's own zone meshes.  A missing game folder
        # or a zone without a readable collision mesh simply leaves this empty; the mob
        # tick then keeps its old ground-level behaviour.
        self.nav = NavCache(config.nav_dir, config.find_game_dir(),
                            enabled=config.nav_enabled)
        # Party and alliance membership.  The client's group pages are server-owned state:
        # it sends C2S 0x06E (invite), 0x074 (answer), 0x06F/0x070/0x071 (leave/disband/kick)
        # and expects 0x0DC/0x0C8/0x0DD/0x0DF/0x0E1 back.  Invites live for 30 seconds.
        self.parties: dict[int, Party] = {}          # party id -> Party
        self.party_by_char: dict[int, Party] = {}    # char id -> Party
        self.alliances: dict[int, Alliance] = {}
        self.pending_invites: dict[int, PendingInvite] = {}
        # Family warps are handed out on the next tick, one 0x00B per client, so the team
        # loads the destination together.  The hand-off fixes in zone.py keep a batch of
        # simultaneous reconnects from losing a box; a positive spacing still forces the
        # old one-at-a-time pace for a caller that asks for it.
        self.pending_warps: list[dict] = []
        self.next_warp_at = 0.0
        # The last //warp all me, kept for a minute: a box whose client was still logging
        # in when the command was given joins the anchor as soon as its zone-in finishes,
        # instead of landing at its saved spot and waiting for a second command.
        self.team_anchor: dict | None = None
        self.next_alliance_id = 1
        self.next_party_sync = 0.0
        # The service calls this after a design save.  It is set here (not in
        # service.py) so the HTTP launcher and the zone command share one path:
        # persist first, then repaint every live copy of that character.
        service.design_listener = self.apply_saved_design

    # --- data helpers --------------------------------------------------------------------------
    def character_record(self, row: dict) -> dict:
        return self.service.character_record(row, self.server_name)

    def characters_for(self, account_id: int) -> list[dict]:
        return [self.character_record(row) for row in self.service.characters_for_account(account_id)]

    def character_by_char_id(self, char_id: int) -> dict | None:
        row = self.service.character_by_char_id(char_id)
        return self.character_record(row) if row else None

    def character_by_any_id(self, char_id: int) -> dict | None:
        """A client's login id: the content id (retail) or the database id (older builds)."""
        character = self.character_by_char_id(char_id)
        if character is not None:
            return character
        try:
            row = self.service.character(int(char_id))
        except Exception:
            return None
        return self.character_record(row)

    def key_from_hash(self, session_hash: bytes) -> bytearray:
        """The key the client's zone cipher starts from.

        md5(session hash), then the view key with the client's own adjustment (+9).
        """
        return bytearray(md5(bytes(session_hash)) + struct.pack("<I", (VIEW_KEY + 9) & M32))

    def prepare_zone_in(self, account_id: int, session_hash: bytes, character: dict):
        from .zone import ZoneSession

        key = self.keys.get(account_id) or self.key_from_hash(session_hash)
        session = ZoneSession(self, None, character)
        session.zone = int(character["zone"])
        session.pos = list(character["pos"]) if character.get("pos") else list(self.zones.position(session.zone))
        session.set_key(key)
        session.session_hash = bytes(session_hash)
        with self.lock:
            # Key the hand-off by the database id: that is the id every lookup can name,
            # while the wire id differs between client builds (content id vs database id).
            self.by_char[int(character["id"])] = session
        return session

    def park_keys(self, session) -> None:
        """Remember the cipher sequence a session was using when it went away.

        A client keeps the key it advanced to across a relog or a re-connect, so the next
        0x00A from the same game session has to be answered under that sequence; resetting
        to the sign-in key strands it.  This applies to a live session that is replaced by
        a login, not only to a hand-off that never finished: the client was in the world
        with an advanced key when its session was dropped, and the replacement login is
        what used to loop on "Downloading".  A genuinely new sign-in gets a new game session
        hash and does not resume this entry.
        """
        history = [bytes(key) for key in (getattr(session, "key_history", None) or [])]
        if not history:
            return
        char_id = int(getattr(session, "char", {}).get("id", 0) or 0)
        if not char_id:
            return
        now = time.time()
        previous = self.handoff_keys.get(char_id)
        if previous and now - float(previous.get("saved", 0.0)) <= HANDOFF_KEY_TTL:
            # A replacement session can know fewer keys than the hand-off it replaced (a
            # fresh login starts from one key).  Overwriting the entry with the shorter
            # sequence would forget the advanced key the client is still holding, which is
            # what kept a real box retrying the same zone-in forever after one dropped
            # hand-off.  Keep the union, newest last.
            merged = [bytes(key) for key in previous.get("history") or []]
            for key in history:
                if key not in merged:
                    merged.append(key)
            history = merged
        self.handoff_keys[char_id] = {
            "saved": now,
            "session": bytes(getattr(session, "session_hash", b"") or b""),
            "history": history[-HANDOFF_KEYS_KEPT:],
        }

    def parked_history(self, character: dict) -> list[bytes]:
        """Every recently parked key for this character, even across game sessions.

        A dropped hand-off leaves the client holding an advanced key, and the game session
        that parked it may be gone by the time the client reconnects (a relaunch, or a
        hand-off whose session row was replaced).  These keys do not become the primary --
        a client that signed in again holds the sign-in key -- but the zone-in is sealed
        under each of them too, so whichever key the client actually holds opens a copy.
        """
        char_id = int(character.get("id") or 0)
        if not char_id:
            return []
        parked = self.handoff_keys.get(char_id)
        if not parked:
            return []
        if time.time() - float(parked.get("saved", 0.0)) > HANDOFF_KEY_TTL:
            self.handoff_keys.pop(char_id, None)
            return []
        return [bytes(key) for key in parked.get("history") or []]

    def parked_keys(self, character: dict, session_hash: bytes) -> list[bytes] | None:
        """The cipher sequence to resume for this client, or None for a fresh one.

        Only the same game session resumes: a restarted client starts its cipher over from
        the account's sign-in key, and handing it an advanced one would break the launch.
        """
        char_id = int(character.get("id") or 0)
        if not char_id:
            return None
        now = time.time()
        for key, parked in list(self.handoff_keys.items()):
            if now - float(parked.get("saved", 0.0)) > HANDOFF_KEY_TTL:
                self.handoff_keys.pop(key, None)
        parked = self.handoff_keys.get(char_id)
        if not parked:
            return None
        if parked.get("session") != bytes(session_hash or b""):
            return None
        history = list(parked.get("history") or [])
        return history or None

    def clear_parked_keys(self, character_id: int) -> None:
        self.handoff_keys.pop(int(character_id), None)

    def save_position(self, character: dict, zone: int, pos) -> None:
        try:
            self.service.save_position(character["id"], int(zone), pos)
        except Exception:
            pass

    def zone_cipher_for(self, key: bytes):
        return zone_cipher(key)

    # --- content -------------------------------------------------------------------------------
    def entities_for_zone(self, zone: int) -> list[ZoneEntity]:
        zone = int(zone)
        if zone in self.content:
            return self.content[zone]
        entities: list[ZoneEntity] = []
        try:
            npcs = self.service.npcs_for_zone(zone)
            mobs = self.service.monster_spawns_for_zone(zone)
        except Exception as exc:  # an old database without the content migration
            log.warning("content for zone %d unavailable: %s", zone, exc)
            npcs, mobs = [], []
        # Static NPC/mob targids live in 0x000-0x3FF. PCs use 0x400-0x6FF.
        for index, row in enumerate(npcs[:0x300]):
            # The client's static-NPC table is keyed by the original zone targid;
            # using a synthetic one makes it fall back to the default model/name.
            targid = int(row.get("targid") or 0) or (0x100 + index)
            dialogue = self.service.npc_lines(row["id"])
            entities.append(npc_from_row(row, targid, dialogue))
        for index, row in enumerate(mobs):
            # Mobs keep their retail targid too: the client's zone table is keyed by it, so a
            # synthetic number resolves to whatever NPC the table holds there and the client
            # will not treat the entity as a monster.  Fall back only for hand-made rows.
            targid = int(row.get("targid") or 0) or (0x200 + index)
            entities.append(mob_from_row(row, targid, self.rng))
        self.content[zone] = entities
        log.info("zone %d content: %d entities", zone, len(entities))
        cache = getattr(self, "nav", None)
        if cache is not None and any(entity.is_mob() for entity in entities):
            cache.prepare(zone)
        return entities

    # --- trusts --------------------------------------------------------------------------------
    def allocate_trust_targid(self, zone: int) -> int | None:
        """A free pet/trust ActIndex in this zone, or None when all 512 are in use."""
        used = {int(entity.targid) for entity in self.entities_for_zone(zone)}
        for targid in range(TRUST_TARGID_FIRST, TRUST_TARGID_LAST + 1):
            if targid not in used:
                return targid
        return None

    def spawn_trust(self, session, row: dict, now: float | None = None):
        """Call one alter ego beside its owner and show it to everyone in the zone.

        The client draws a Trust from a normal 0x00E spawn with Flags3's Trust/Pet bits
        set; 0x067 is the extra packet that tells the owner's client this spawnable is
        a Trust of that player, which is what gives it the Release sub-menu.
        """
        from . import packets
        from .zone import TARGID, sub
        from .entities import trust_from_row

        now = time.time() if now is None else now
        zone = int(session.zone)
        if getattr(session, "char", {}).get("moghouse"):
            session.say("You cannot call an alter ego here.")
            return None
        targid = self.allocate_trust_targid(zone)
        if targid is None:
            session.say("There is no room for another alter ego.")
            return None
        index = len(getattr(session, "trust_entities", []))
        level = max(1, int(session.char.get("main_level", 1)))
        entity = trust_from_row(row, targid, zone, int(session.char["char_id"]), level)
        entity.spells = self.service.trust_spells(int(row["spell_id"]), level)
        entity.kit = trust_ai.build_kit(entity.spells, level, entity.job, entity.name)
        self._set_trust_action_kit(entity, level)
        entity.gear = trust_gear.loadout(self.service, int(row["spell_id"]))
        entity.gear_mods = dict(entity.gear.mods)
        entity.geomancy_plus = int(entity.gear.geomancy_plus)
        # Qultada and Luzaf are support: they roll for the party and never swing, so the
        # AI takes the roll branch before it ever looks for a target to attack.
        entity.roll_support = trust_ai.plans_rolls(entity.name)
        entity.roll_keys = []
        entity.next_roll_at = now + 1.0
        self._apply_trust_gear_share(entity, session, full=True)
        entity.next_gear_sync = now + TRUST_GEAR_SYNC_SECONDS
        entity.next_cast_at = now + 0.8
        entity.next_mp_tick = now + 3.0
        angle = math.pi * (0.5 + index * 0.35)
        distance = TRUST_SPAWN_DISTANCE + index * 0.8
        entity.x = float(session.pos[0]) + math.sin(angle) * distance
        entity.y = float(session.pos[1])
        entity.z = float(session.pos[2]) + math.cos(angle) * distance
        entity.spawn_x, entity.spawn_y, entity.spawn_z = entity.x, entity.y, entity.z
        entity.rot = heading_to_rot(session.pos[0] - entity.x, session.pos[2] - entity.z)
        entity.last_move_at = now
        self.entities_for_zone(zone).append(entity)
        for observer in self.sessions_in_zone(zone):
            if entity not in observer.entities:
                observer.entities.append(entity)
            if observer is not session:
                if not getattr(observer, "entities_sent", False):
                    continue
                if entity.distance_to(*observer.pos[:3]) > SYNC_RANGE:
                    continue
            # The caster is ready by definition (the client just sent the cast), so the
            # owner's spawn goes out even if the first position sweep has not run yet.
            observer.sent_targids.add(int(entity.targid))
            observer.queue_spawn(entity)
            if observer is session:
                # 0x067 only goes to the master; other clients read the 0x00E spawn.
                observer.queue.append(sub(0x067, packets.entity_set_name(entity, TARGID)))
        if getattr(session, "trust_entities", None) is None:
            session.trust_entities = []
        session.trust_entities.append(entity)
        session.say("%s joins you." % entity.name)
        self.refresh_trust_roster(session)
        self._apply_trust_aura(entity, session)
        log.info("%s called trust %s (%#x) in zone %d", session.addr, entity.name,
                 int(entity.id), zone)
        return entity

    def spawn_pet(self, session, key: str | None = None, now: float | None = None,
                  spec=None, position: tuple[float, float, float] | None = None):
        """Call one job pet beside its owner and show it to everyone in the zone.

        ``position`` places the pet at an explicit point instead of beside the owner;
        a Geo- Luopan is put down at its anchor/monster, not at the GEO's feet.
        """
        from . import packets
        from .zone import TARGID, sub

        now = time.time() if now is None else now
        if spec is None:
            spec = pets.spec(key)
        if spec is None:
            return None
        zone = int(session.zone)
        if getattr(session, "char", {}).get("moghouse"):
            session.say("You cannot call a pet here.")
            return None
        existing = getattr(session, "pet_entity", None)
        if existing is not None and existing.alive:
            self.despawn_pet(existing, now, "replaced")
        targid = self.allocate_trust_targid(zone)
        if targid is None:
            session.say("There is no room for a pet.")
            return None
        level = max(1, int(session.char.get("main_level", 1)))
        owner_job = int(session.char.get("main_job", 0))
        stats = pets.pet_stats(owner_job, level, spec)
        entity = ZoneEntity(
            kind="pet", id=0x01000000 | (zone << 12) | (int(targid) & 0xFFF),
            targid=int(targid) & 0xFFF, zone=zone, name=spec.name,
            model=spec.model, look=pets.look(spec), speed=62,
            triggerable=False, widescan=True,
            level=level, hp_max=max(1, int(stats["hp"])), hp=max(1, int(stats["hp"])),
            mp_max=max(0, level * 4), mp=max(0, level * 4),
            attack_delay_ms=max(1200, int(stats["delay_ms"])),
            owner_char_id=int(session.char["char_id"]),
            damage_mult=max(50, min(300, int(stats["damage_mult"]))),
            last_move_at=now,
        )
        entity.pet_type = spec.key
        entity.pet_state = "follow"
        if spec.key == "luopan":
            entity.pet_state = "stay"        # the bubble stays where it is put down

            entity.geo_drain = 24
            entity.geo_potency = 100
            entity.geo_mp_cost = 0
            entity.next_geo_tick = now + 3.0
        entity.pet_accuracy_bonus = max(0, int(stats["accuracy"]) - (level * 2 + 20))
        entity.pet_hp_bonus = max(0, int(stats["hp"]) - (level * 30 + 200))
        entity.breath_bonus = int(stats.get("breath_bonus") or 0)
        angle = math.pi * 0.5
        distance = TRUST_SPAWN_DISTANCE
        entity.x = float(session.pos[0]) + math.sin(angle) * distance
        entity.y = float(session.pos[1])
        entity.z = float(session.pos[2]) + math.cos(angle) * distance
        if position is not None:
            entity.x, entity.y, entity.z = (float(value) for value in position[:3])
        elif spec.key == "luopan":
            entity.x, entity.y, entity.z = (float(session.pos[0]), float(session.pos[1]),
                                            float(session.pos[2]))
        entity.spawn_x, entity.spawn_y, entity.spawn_z = entity.x, entity.y, entity.z
        entity.rot = heading_to_rot(session.pos[0] - entity.x, session.pos[2] - entity.z)
        self.entities_for_zone(zone).append(entity)
        for observer in self.sessions_in_zone(zone):
            if entity not in observer.entities:
                observer.entities.append(entity)
            observer.sent_targids.add(int(entity.targid))
            observer.queue_spawn(entity)
            if observer is session:
                observer.queue.append(sub(0x067, packets.entity_set_name(entity, TARGID)))
        session.pet_entity = entity
        # A pet called after the roll still gets the owner's active Beast/Drachen/Puppet
        # or Companion's Roll.
        rolls._refresh_pet(session)
        session.say("%s joins you." % entity.name)
        log.info("%s called pet %s (%#x) in zone %d", session.addr, entity.name,
                 int(entity.id), zone)
        return entity

    def despawn_pet(self, entity, now: float | None = None, reason: str = "") -> None:
        """Remove one pet from the world and from every client that draws it."""
        from .zone import sub

        now = time.time() if now is None else now
        owner = self.session_by_char(entity.owner_char_id)
        if owner is not None and getattr(entity, "pet_type", "") == "luopan":
            try:
                owner._geo_bubble_off(entity)
            except Exception:
                log.warning("luopan aura cleanup failed", exc_info=True)
        if owner is not None and getattr(owner, "pet_entity", None) is entity:
            owner.pet_entity = None
            owner.pet_jug_item = 0
        zone = int(entity.zone)
        entities = self.entities_for_zone(zone)
        try:
            entities.remove(entity)
        except ValueError:
            return
        entity.alive = False
        body = packets.entity_despawn(entity)
        for observer in self.sessions_in_zone(zone):
            if entity in getattr(observer, "entities", []):
                observer.entities.remove(entity)
            if int(entity.targid) in getattr(observer, "sent_targids", set()):
                observer.sent_targids.discard(int(entity.targid))
                observer.queue.append(sub(0x00E, body))
        log.info("pet %s (%#x) left zone %d%s", entity.name, int(entity.id), zone,
                 (" (%s)" % reason) if reason else "")

    def charm_pet(self, session, mob, now: float | None = None):
        """Turn a claimed/charmable mob into the Beastmaster's pet.

        The mob is removed with a normal despawn and a pet entity is spawned with the
        same model and name.  This is deliberately the simple Charm result: the pet
        follows and fights through the existing pet tick.
        """
        from .zone import sub

        now = time.time() if now is None else now
        if mob is None or not mob.is_mob() or not mob.alive:
            return None
        spec = pets.PetSpec("charmed", str(mob.name), int(mob.model),
                            hp_mult=100, attack_mult=100)
        zone = int(mob.zone)
        entities = self.entities_for_zone(zone)
        try:
            entities.remove(mob)
        except ValueError:
            return None
        mob.alive = False
        body = packets.entity_despawn(mob)
        for observer in self.sessions_in_zone(zone):
            if mob in getattr(observer, "entities", []):
                observer.entities.remove(mob)
            if int(mob.targid) in getattr(observer, "sent_targids", set()):
                observer.sent_targids.discard(int(mob.targid))
                observer.queue.append(sub(0x00E, body))
        return self.spawn_pet(session, spec=spec, now=now)

    def _apply_trust_aura(self, entity, owner) -> None:
        """Put a passive Trust's aura on its owner and draw its status icon.

        The effect is separate from the ordinary spell of the same name, so Cornelia's
        ``TRUST_AURA_HASTE`` (icon 580, GEO Haste) sits beside a White Mage's Haste
        (icon 33) instead of replacing it.  Aura effects have no duration: they last
        until the Trust leaves, which ``despawn_trust`` handles.
        """
        aura = trust_ai.aura_for(entity.name)
        if aura is None or owner is None or owner.zone != entity.zone:
            return
        state = owner.effect(aura.effect)
        if state is not None and int(state.get("trust_source", 0)) == int(entity.id):
            return
        owner.add_effect(aura.effect, duration=0, power=int(entity.level),
                         tick=aura.tick, icon=aura.icon, mods=aura.mods)
        state = owner.effect(aura.effect)
        if state is not None:
            state["trust_source"] = int(entity.id)
            state["trust_name"] = entity.name
        entity.aura_effect = int(aura.effect)
        owner.queue += [owner.char_status(), owner.char_stats(), owner.party_member()]

    def _remove_trust_aura(self, entity) -> None:
        """Take back the aura this Trust put on its owner, without touching a real buff."""
        effect_id = int(getattr(entity, "aura_effect", 0) or 0)
        if not effect_id:
            return
        owner = self.session_by_char(entity.owner_char_id)
        if owner is not None:
            state = owner.effect(effect_id)
            if state is not None and int(state.get("trust_source", 0)) == int(entity.id):
                owner.remove_effect(effect_id, quiet=True)
                owner.queue += [owner.char_status(), owner.char_stats(),
                                owner.party_member()]
        entity.aura_effect = 0

    def _set_trust_action_kit(self, entity: ZoneEntity, level: int) -> None:
        """Build the wider picker kit for a support Trust, separate from its default AI.

        The default rotation stays on the curated ``trust_spells`` rows, which is what
        retail's alter ego actually casts.  A player-selected set may name any spell the
        Trust's jobs can use, so the picker and ``restrict_kit`` read this expanded kit
        instead.
        """
        entity.action_spells = entity.spells
        entity.action_kit = entity.kit
        if int(getattr(entity, "trust_spell", 0)) not in trust_ai.SUPPORT_TRUST_IDS:
            return
        try:
            entity.action_spells = self.service.trust_action_spells(
                int(entity.trust_spell), int(level))
            entity.action_kit = trust_ai.build_kit(
                entity.action_spells, int(level), entity.job, entity.name)
        except Exception as exc:
            log.debug("trust %s action catalogue unavailable: %s", entity.name, exc)

    def despawn_trust(self, entity, now: float | None = None, reason: str = "") -> None:
        """Remove one alter ego from the world and from every client that draws it."""
        from . import packets
        from .zone import sub

        zone = int(entity.zone)
        self._remove_trust_aura(entity)
        entity.casting = None
        entities = self.entities_for_zone(zone)
        try:
            entities.remove(entity)
        except ValueError:
            return
        entity.alive = False
        body = packets.entity_despawn(entity)
        for observer in self.sessions_in_zone(zone):
            if entity in getattr(observer, "entities", []):
                observer.entities.remove(entity)
            if entity in getattr(observer, "trust_entities", []):
                observer.trust_entities.remove(entity)
            if int(entity.targid) in getattr(observer, "sent_targids", set()):
                observer.sent_targids.discard(int(entity.targid))
                observer.queue.append(sub(0x00E, body))
        owner = self.session_by_char(entity.owner_char_id)
        if owner is not None:
            self.refresh_trust_roster(owner)
        log.info("trust %s (%#x) left zone %d%s", entity.name, int(entity.id), zone,
                 (" (%s)" % reason) if reason else "")

    def _apply_trust_gear_share(self, entity: ZoneEntity, owner, *,
                                full: bool = False) -> None:
        """Give a Trust its share of the owner's gear modifiers.

        The share is re-read on a slow beat; ``full`` is the first pass (or a level
        change), which also fills the bars.  A later pass only moves the maximum, so a
        Trust that has already taken damage is not healed by its owner changing gear.
        """
        key = int(owner.char["id"])
        now = time.time()
        cached = self._trust_share_cache.get(key)
        if cached is not None and now - cached[0] < TRUST_GEAR_SYNC_SECONDS:
            shared = cached[1]
        else:
            try:
                shared = trust_gear.share(self.service, key)
            except Exception as exc:
                log.debug("trust gear share failed: %s", exc)
                shared = {}
            self._trust_share_cache[key] = (now, shared)
        try:
            upgrade = self.service.trust_upgrade_level(int(owner.char["id"]))
        except Exception:
            upgrade = 0
        entity.trust_upgrade_level = int(upgrade)
        shared = dict(shared)
        if upgrade:
            # Alter-ego upgrades (the launcher's max-all action): +5 HP, +2 MP and
            # +1 to every base stat per level, applied to the same shared-modifier
            # block the combat and spell paths already read.
            for stat in (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR,
                         mod.ATT, mod.ACC):
                shared[stat] = int(shared.get(stat, 0)) + int(upgrade)
        entity.shared_mods = shared
        hp_max, mp_max = trust_stats.vitals(
            entity.race, entity.job, entity.sub_job, int(entity.level))
        hp_max = max(1, int(hp_max) + int(shared.get(mod.HP, 0)) + int(upgrade) * 5)
        mp_max = max(0, int(mp_max) + int(shared.get(mod.MP, 0)) + int(upgrade) * 2)
        if full:
            entity.hp_max, entity.mp_max = hp_max, mp_max
            entity.hp, entity.mp = hp_max, mp_max
            return
        entity.hp_max = hp_max
        entity.mp_max = mp_max
        entity.hp = min(int(entity.hp), hp_max)
        entity.mp = min(int(entity.mp), mp_max)

    def trust_attack(self, entity: ZoneEntity, mob: ZoneEntity, owner, now: float) -> None:
        """One alter-ego swing at the monster its owner is fighting."""
        from . import packets
        from .zone import sub

        sheet = stats.build_monster(int(entity.level))
        multiplier = max(0, min(300, int(entity.damage_mult))) / 100.0
        # Beast Roll and Puppet Roll put their percentages on the pet, not on its owner.
        multiplier *= (100 + max(0, int(getattr(entity, "roll_attack_pct", 0)))
                       + max(0, int(getattr(entity, "roll_matt", 0)))) / 100.0
        if (getattr(entity, "pet_type", "") == "automaton"
                and float(getattr(entity, "overdrive_until", 0.0)) > time.time()):
            multiplier *= 1.5
        weapon_dmg = max(1, int(int(entity.level) * 0.80 * multiplier))
        # What the owner's gear lends the Trust: the same share of Attack and Accuracy a
        # player would get from those pieces, so the swing tracks the Master's set.
        shared = getattr(entity, "shared_mods", None) or {}
        attacker = replace(
            sheet.fighter, weapon_dmg=weapon_dmg,
            attack=max(1, int(sheet.fighter.attack * 0.95) + int(shared.get(mod.ATT, 0))),
            accuracy=int(sheet.fighter.accuracy + 10 + int(shared.get(mod.ACC, 0))
                         + (int(getattr(entity, "pet_accuracy_bonus", 0))
                            if entity.is_pet() else 0)
                         + int(getattr(entity, "roll_accuracy", 0))
                         + int(getattr(entity, "roll_macc", 0))))
        hit = combat.melee(attacker, self.debuffed_monster(mob),
                           zone=int(mob.zone), rng=self.rng)
        defeated = (not hit.missed) and int(mob.hp) - int(hit.damage) <= 0
        body = packets.battle_action(
            int(entity.id), int(mob.id), int(hit.damage), miss=hit.missed,
            critical=hit.critical, defeated=defeated, animation=0,
            category=packets.ACTION_CATEGORY_BASIC_ATTACK,
            action_id=packets.BASIC_ATTACK_ID)
        for observer in self.sessions_in_zone(entity.zone):
            if int(entity.targid) in getattr(observer, "sent_targids", set()):
                observer.queue.append(sub(0x028, body))
        if hit.missed:
            self.add_mob_hate(mob, int(owner.char["char_id"]), 1, now)
        else:
            mob.hp = max(0, int(mob.hp) - int(hit.damage))
            for observer in self.sessions_in_zone(entity.zone):
                if int(mob.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue_entity(mob, SEND_HP)
            self.wake_mob(mob)
            # The owner is the one on the monster's hate list; half the Trust's damage
            # is passed along so an alter ego helps pull without becoming untouchable.
            hate = max(1, int(hit.damage) // 2)
            if int(owner.char.get("main_job", 0)) == 9:
                hate = max(1, hate * (100 + job_points.category_total(9, "Pet Enmity")) // 100)
            self.add_damage_hate(mob, int(owner.char["char_id"]), hate, now)
            if defeated:
                self.kill_mob(owner, mob, now)
        entity.next_attack_at = now + max(1.5, int(entity.attack_delay_ms) / 1000.0)

    def _trust_target(self, owner):
        """The monster the owner is fighting, while it is still inside the Trust's leash."""
        target = None
        if owner.engaged_id:
            candidate = self.entity_by_id(int(owner.zone), int(owner.engaged_id))
            if candidate is not None and candidate.is_mob() and candidate.alive:
                target = candidate
        if target is None:
            for candidate in self.entities_for_zone(int(owner.zone)):
                if (candidate.is_mob() and candidate.alive
                        and candidate.engaged_char_id == int(owner.char["char_id"])):
                    target = candidate
                    break
        if target is not None and target.distance_to(*owner.pos[:3]) > TRUST_LEASH:
            return None
        return target

    def _tick_trust(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        """Follow the owner, keep its aura up, then cast or fight what the owner fights."""
        if not entity.alive:
            return
        owner = self.session_by_char(entity.owner_char_id)
        if (owner is None or owner.zone != entity.zone or getattr(owner, "gone", False)
                or owner.dead_until or int(owner.char.get("hp_current", 0)) <= 0):
            self.despawn_trust(entity, now, "owner gone")
            return
        level = max(1, int(owner.char.get("main_level", 1)))
        if int(entity.level) != level:
            entity.level = level
            entity.spells = self.service.trust_spells(int(entity.trust_spell), level)
            entity.kit = trust_ai.build_kit(entity.spells, level, entity.job, entity.name)
            self._set_trust_action_kit(entity, level)
            self._apply_trust_gear_share(entity, owner, full=True)
            entity.next_cast_at = now + 0.5
        elif now >= float(getattr(entity, "next_gear_sync", 0.0) or 0.0):
            # The owner's set can change mid-fight; the bars follow it on a slow beat.
            self._apply_trust_gear_share(entity, owner)
            entity.next_gear_sync = now + TRUST_GEAR_SYNC_SECONDS

        self._apply_trust_aura(entity, owner)
        self._trust_recover_mp(entity, now)
        if entity.casting:
            if now < float(entity.casting.get("finish") or now):
                self.set_animation(entity, 1, sessions)
                return
            self._finish_trust_cast(entity, owner, now)
            return

        if entity.passive:
            self._move_trust(entity, owner, sessions, now)
            return

        if getattr(entity, "roll_support", False):
            # A Corsair support Trust rolls and never swings: no auto-attack and no
            # weapon skill, so it stays beside the owner instead of joining the fight.
            self._try_trust_roll(entity, owner, self._trust_target(owner), now)
            self._move_trust(entity, owner, sessions, now)
            return
        target = self._trust_target(owner)
        if target is None:
            self._move_trust(entity, owner, sessions, now)
            self._try_trust_cast(entity, owner, sessions, None, now)
            return

        caster = bool((entity.kit or {}).get("pure_caster"))
        reach = trust_ai.CAST_RANGE if caster else TRUST_REACH
        distance = entity.distance_to(target.x, target.y, target.z)
        if distance > reach:
            self.set_animation(entity, 1, sessions)
            dx = target.x - entity.x
            dz = target.z - entity.z
            self._move_trust_step(entity, dx, dz, TRUST_CHASE_SPEED, sessions, now)
            return
        if entity.moving:
            entity.moving = False
            for observer in sessions:
                if int(entity.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue_entity(entity, SEND_POSITION)
        entity.rot = heading_to_rot(target.x - entity.x, target.z - entity.z)
        self.set_animation(entity, 1, sessions)

        # One opening swing at melee reach: it is the client's weapon-drawn tell for the
        # engagement, and from the next beat the Trust falls into its spell rotation.
        if not entity.trust_has_acted and distance <= TRUST_REACH:
            if now < entity.next_attack_at:
                return
            self.trust_attack(entity, target, owner, now)
            entity.trust_has_acted = True
            return

        if self._try_trust_cast(entity, owner, sessions, target, now):
            return
        if caster or now < entity.next_attack_at:
            return
        self.trust_attack(entity, target, owner, now)

    def _trust_recover_mp(self, entity: ZoneEntity, now: float) -> None:
        """Out of combat a Trust recovers a little MP, the way an alter ego does."""
        if now < float(entity.next_mp_tick or 0.0):
            return
        entity.next_mp_tick = now + 3.0
        if entity.mp < entity.mp_max:
            entity.mp = min(entity.mp_max,
                            entity.mp + max(1, int(entity.mp_max) // 20))

    def _try_trust_cast(self, entity: ZoneEntity, owner, sessions: list, target,
                        now: float) -> bool:
        """Start the best spell this beat: aura, cure, missing buff, debuff, then nuke.

        Returns True when a cast started, so the caller does not also swing.  The spell
        is picked from the Trust's own mob_spell_list kit; a job with no kit (a pure
        melee Trust) never enters this path.
        """
        if entity.casting or now < float(entity.next_cast_at or 0.0):
            return False
        kit = entity.kit or {}
        selected = self._trust_action_set(owner, entity.trust_spell)
        if selected and int(entity.trust_spell) in trust_ai.SPELL_ACTION_TRUSTS:
            # An explicit spell pool replaces the whole cast rotation: the Trust still
            # decides when each chosen spell is useful, but cannot cast anything else.
            # Use the expanded action kit so a job spell outside the curated rotation
            # (or any Indi-/Geo- spell for Sylvie) is selectable.
            kit = getattr(entity, "action_kit", None) or kit
            kit = trust_ai.restrict_kit(kit, selected)
        if not kit.get("caster"):
            return False
        spell = None
        kind = ""
        hp_max = max(1, int(owner.char.get("hp", 1)))
        hp_now = max(0, int(owner.char.get("hp_current", 0)))
        missing_hp = max(0, hp_max - hp_now)
        # A Geomancer's bubble is one cast every three minutes, so it goes up before the
        # cure it would otherwise spend every beat on -- unless the owner is in real
        # danger, in which case the heal wins.  Without this the 85% heal rule kept a
        # hurt owner in cure-forever and the aura never got a turn in a real fight.
        in_danger = hp_now * 100 < hp_max * TRUST_CURE_DANGER_PERCENT
        if not in_danger:
            spell = self._trust_aura_choice(entity, owner, target, now, kit)
            if spell is not None:
                aura_spec = trust_ai.effect_of(spell, trust_name=entity.name)
                if (aura_spec is not None and aura_spec.kind == "debuff"
                        and target is None):
                    spell = None                 # a hex needs a monster to land on
            if spell is not None and int(spell.get("mp") or 0) > int(entity.mp):
                spell = None                     # cannot pay for it: fall through to a cure
            spec = (trust_ai.effect_of(spell, trust_name=entity.name)
                    if spell is not None else None)
            kind = (spec.kind if spec is not None else "buff") if spell else ""
        if spell is None and missing_hp >= max(1, hp_max * 15 // 100):
            spell = trust_ai.cure_for(kit, int(entity.level), int(entity.mp), missing_hp)
            kind = "cure" if spell is not None else ""
        if spell is None:
            spell = self._trust_song_choice(entity, owner, target, now)
            kind = "buff" if spell is not None else ""
        # Damage-first enfeebles.  A caster Trust used to check buff_for before
        # debuff_for, so Koru-Moru refreshed Protect/Shell/Haste/Refresh/Phalanx
        # forever and never cast Dia; Sylvie's Entrust Indi-Frailty was never tried at
        # all.  Dia (10-30% Defense cut) and the entrusted frailty hex (12.5%) are the
        # two debuffs that lift every physical hit, so they get the beat before the
        # next buff refresh.  Cures still win, and the rest of the enfeebles still run
        # after the buffs below.
        if spell is None and target is not None:
            spell = self._trust_hex_choice(entity, owner, target, now, kit)
            kind = "debuff" if spell is not None else ""
        entrust = False
        if spell is None and target is not None:
            spell = trust_ai.entrust_debuff_for(
                entity.name, kit, target.effect_state, now)
            kind = "debuff" if spell is not None else ""
            entrust = spell is not None
        if spell is None and target is not None:
            spell = trust_ai.opening_debuff_for(kit, target.effect_state, now)
            kind = "debuff" if spell is not None else ""
        if spell is None:
            spell = trust_ai.buff_for(kit, owner.effect_state, now)
            kind = "buff" if spell is not None else ""
        if spell is None and target is not None:
            spell = trust_ai.debuff_for(kit, target.effect_state, now)
            kind = "debuff" if spell is not None else ""
        if spell is None and target is not None:
            spell = trust_ai.nuke_for(kit, int(entity.mp))
            kind = "nuke" if spell is not None else ""
        if spell is None:
            return False
        cost = int(spell.get("mp") or 0)
        if cost > int(entity.mp):
            return False

        target_id = (int(target.id) if kind in ("debuff", "nuke")
                     else int(owner.char["char_id"]))
        finish = now + combat.cast_time(int(spell.get("cast_time") or 0), 0) / 1000.0
        entity.mp = max(0, int(entity.mp) - cost)
        if entrust:
            # An Entrust is an Indi- aura placed on a party member, not an aura whose
            # caster is the monster.  Applying the GEO_FRAILTY status to the monster
            # would say "the monster casts Indi-Frailty", which debuffs the players
            # inside its bubble; instead land the same -12.5% Defense as an ordinary
            # Defense Down on the monster.
            effect = effects.SpellEffect(
                effects.DEFENSE_DOWN, "debuff", trust_ai.GEO_AURA_SECONDS, potency=12)
        else:
            effect = trust_ai.effect_of(
                spell, int(getattr(entity, "geomancy_plus", 0) or 0), entity.name)
        entity.casting = {
            "spell": spell, "kind": kind, "target_id": target_id,
            "finish": finish, "entrust": entrust, "effect": effect,
        }
        entity.trust_has_acted = True
        entity.next_cast_at = finish + 1.0
        entity.rot = heading_to_rot(target.x - entity.x, target.z - entity.z) \
            if target is not None else entity.rot
        self.set_animation(entity, 1, sessions)
        # A Trust is not the local player, so its Magic Start carries the spell's own
        # animation and the "starts casting" form without a target (message 3).
        self._queue_trust_action(
            entity, target_id, value=int(spell["id"]),
            animation=trust_ai.spell_animation(spell),
            message=packets.MESSAGE_MAGIC_STARTS_CASTING_SELF,
            category=packets.ACTION_CATEGORY_MAGIC_START,
            action_id=trust_ai.cast_arg(spell))
        return True

    def _trust_action_set(self, owner, trust_id) -> list[int]:
        """The owner's explicit actions for one support Trust, or [] for its default logic."""
        trust_id = int(trust_id or 0)
        if trust_id == 911:
            return list(getattr(owner, "joachim_songs", ()) or ())
        return list((getattr(owner, "trust_actions", {}) or {}).get(trust_id, ()) or ())

    # --- trust songs ---------------------------------------------------------------------------
    def _trust_song_choice(self, entity: ZoneEntity, owner, target, now: float):
        """The next song this owner's role needs, or None when the set is up.

        A per-character set from ``//trust joachim set songs`` replaces the role plan
        entirely.  Songs are stored under ``effects.song_key`` (one state per song, not
        per icon), so Minuet IV and V can both be up; an older icon-keyed state still
        counts as the same song here.
        """
        kit = getattr(entity, "action_kit", None) or entity.kit or {}
        if not kit.get("song"):
            return None
        selected = list(getattr(owner, "joachim_songs", ()) or ())
        planned = trust_ai.choose_songs(
            kit, self._trust_song_need(owner, target), selected)
        for spell in planned:
            spec = trust_ai.effect_of(spell)
            if spec is None:
                continue
            state = owner.effect_state.get(effects.song_key(int(spell["id"])))
            if state is None:
                state = owner.effect_state.get(int(spec.effect))
            if (state is not None
                    and float(state.get("until") or 0.0) - now
                    > trust_ai.SONG_REFRESH_SECONDS):
                continue                       # this song is already running
            return spell
        return None

    def _trust_song_need(self, owner, target):
        """Measure the owner's role for ``trust_ai.choose_songs``."""
        char = owner.char
        job = int(char.get("main_job", 0) or 0)
        sheet = owner.stat_sheet()
        fighter = sheet.fighter
        ratio = 0.0
        hit_rate = 1.0
        if target is not None and target.is_mob():
            mob = self.debuffed_monster(target)
            ratio = float(fighter.attack) / max(1, int(mob.defense))
            hit_rate = self._fighter_hit_rate(owner, fighter, mob)
        weapon = int(getattr(fighter, "weapon_skill", 0) or 0)
        cap = combat.PDIF_WEAPON_CAP.get(weapon, combat.DEFAULT_PDIF_CAP)
        haste = float(getattr(sheet, "haste_magic", 0.0) or 0.0)
        # Measure the owner without the March line: the plan picks Victory or Honor from
        # the haste the *owner* brings, or the two would trade the slot forever (Victory
        # pushes the total over the cap, which would then ask for Honor).  Songs live
        # under ``effects.song_key``; the icon key is the legacy/plain-effect path.
        march_haste = 0.0
        for key, state in owner.effect_state.items():
            if int(key) != effects.MARCH and not state.get("song"):
                continue
            if (int(key) != effects.MARCH
                    and int(state.get("song_effect") or 0) != effects.MARCH):
                continue
            march_haste = max(
                march_haste,
                int((state.get("mods") or {}).get(mod.HASTE_MAGIC, 0)) / 10000.0)
        haste -= march_haste
        return trust_ai.SongNeed(
            caster=job in trust_ai.MAGE_JOBS,
            ranged=job in trust_ai.RANGED_SONG_JOBS,
            haste_percent=max(0.0, haste),
            attack_capped=bool(target is not None and ratio >= cap - 0.375),
            hit_rate=hit_rate)

    # --- trust corsair rolls --------------------------------------------------------------------
    def _trust_roll_members(self, owner) -> list:
        """The owner and the party members this Trust's roll lands on."""
        return [owner] + self._trust_party_sessions(owner)

    @staticmethod
    def _trust_roll_spec(key: str):
        return rolls.spec(trust_ai.ROLL_IDS.get(str(key or ""), 0))

    def _drop_trust_roll(self, entity: ZoneEntity, owner, key: str) -> None:
        """Take one of this Trust's rolls off the party, when its set changes."""
        spec = self._trust_roll_spec(key)
        if spec is None:
            return
        status = int(spec.status)
        changed = False
        for member in self._trust_roll_members(owner):
            state = member.effect(status)
            if state is None:
                continue
            if int(state.get("roll_owner") or 0) != int(entity.id):
                continue                    # another Corsair owns this copy; leave it
            member.remove_effect(status, quiet=True)
            member.queue += [member.char_status(), member.char_stats(),
                             member.party_member()]
            changed = True
        if changed:
            self.queue_party_buffs(owner)

    def _set_trust_rolls(self, entity: ZoneEntity, owner, keys) -> None:
        """Store the held list, dropping any roll that left the owner's priority set."""
        old = list(getattr(entity, "roll_keys", []) or [])
        new = list(keys)
        for key in old:
            if key not in new:
                self._drop_trust_roll(entity, owner, key)
        entity.roll_keys = new

    def _try_trust_roll(self, entity: ZoneEntity, owner, target, now: float) -> bool:
        """Keep up to two rolls on the party, one new roll per beat.

        A roll lands on every party member in the zone, so the plan is a party decision
        (``trust_ai.choose_roll``): the melee's Attack, the casters' MP, the ranged line.
        Retail Qultada holds two rolls at once (Chaos and Fighter's are his standard pair)
        and an alter ego is a maxed-out Corsair, so both support Corsairs fill two slots.
        The first slot is the party's biggest need; the second takes the next line the
        other Corsair has not already put up.
        """
        if now < float(getattr(entity, "next_roll_at", 0.0) or 0.0):
            return False
        selected = self._trust_action_set(owner, entity.trust_spell)
        signature = tuple(int(ability) for ability in selected)
        if getattr(entity, "roll_set_signature", None) != signature:
            # The owner changed the priority list (or this is the first beat).  Held
            # rolls still on the new list stay; the ones that left it are removed below.
            entity.roll_set_signature = signature
        allowed = {trust_ai.ROLL_KEYS[int(ability)]
                   for ability in selected
                   if int(ability) in trust_ai.ROLL_KEYS}
        held = list(getattr(entity, "roll_keys", []) or [])
        if allowed:
            held = [key for key in held if key in allowed]
        self._set_trust_rolls(entity, owner, held)
        held = list(getattr(entity, "roll_keys", []) or [])
        members = self._trust_roll_members(owner)
        # Refresh a held roll before adding another: a dispelled or expiring copy is the
        # more urgent job, and re-rolling the same key keeps the party's pair stable.
        for key in held:
            spec = self._trust_roll_spec(key)
            if spec is None:
                continue
            if any(self._roll_remaining(member, spec, now)
                   <= trust_ai.ROLL_REFRESH_SECONDS for member in members):
                return self._cast_trust_roll(entity, owner, members, spec, now)
        if len(held) >= trust_ai.MAX_TRUST_ROLLS:
            return False                    # both slots are up and healthy
        need = self._trust_roll_need(owner, target, entity)
        ability = trust_ai.choose_roll(need, selected)
        spec = rolls.spec(int(ability)) if ability is not None else None
        if spec is None or spec.key in held:
            return False
        if int(spec.status) in need.active:
            return False                    # the other Corsair already keeps it up
        entity.roll_keys = held + [spec.key]
        return self._cast_trust_roll(entity, owner, members, spec, now)

    def _cast_trust_roll(self, entity: ZoneEntity, owner, members, spec, now: float) -> bool:
        """Put one roll on every party member and send the Trust's roll action."""
        entity.next_roll_at = now + trust_ai.ROLL_REFRESH_SECONDS
        value = rolls.value(self.rng)
        mods = spec.mods(value)
        # An alter ego is a maxed-out Corsair: the roll runs the COR job-point maximum
        # (Phantom Roll Duration, 2 seconds per rank over the 300-second base).
        duration = rolls.duration(int(entity.job))
        for member in members:
            member.remove_effect(int(spec.status), quiet=True)
            member.add_effect(int(spec.status), duration=duration,
                              power=value, mods=mods)
            state = member.effect(int(spec.status))
            if state is not None:
                state["rolled_at"] = float(now)
                state["roll_owner"] = int(entity.id)
            member.queue += [member.char_status(), member.char_stats(),
                             member.party_member()]
        ability = int(trust_ai.ROLL_IDS[spec.key])
        self._queue_trust_action(
            entity, int(owner.char["char_id"]), value=value, animation=ability,
            message=packets.MESSAGE_USES_JOB_ABILITY,
            category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=ability)
        log.info("%s rolls %s: %d", entity.name, spec.name, value)
        return True

    def _trust_roll_need(self, owner, target, entity=None):
        """What the party is short of, for ``trust_ai.choose_roll``."""
        melee = mages = ranged = 0
        lowest_mp = 100.0
        members = [owner] + self._trust_party_sessions(owner)
        for member in members:
            job = int(member.char.get("main_job", 0) or 0)
            max_mp = max(0, int(member.char.get("mp", 0)))
            if max_mp >= 200:
                lowest_mp = min(lowest_mp, 100.0 * max(
                    0, int(member.char.get("mp_current", 0))) / max_mp)
            if job in trust_ai.MAGE_JOBS:
                mages += 1
            if job in trust_ai.HYBRID_JOBS:
                melee += 1                 # a melee RDM/BLU also joins the melee plan
            elif job in trust_ai.RANGED_JOBS:
                ranged += 1
            elif job not in trust_ai.MAGE_JOBS:
                melee += 1
        attack_capped = False
        if target is not None and target.is_mob():
            fighter = owner.stat_sheet().fighter
            mob = self.debuffed_monster(target)
            ratio = float(fighter.attack) / max(1, int(mob.defense))
            cap = combat.PDIF_WEAPON_CAP.get(
                int(getattr(fighter, "weapon_skill", 0) or 0), combat.DEFAULT_PDIF_CAP)
            attack_capped = ratio >= cap - 0.375
        # What every Corsair already keeps up, this Trust included: the next slot takes a
        # different line instead of overwriting a copy the party already has.
        active = set()
        for member in members:
            for spec in rolls.active(member):
                active.add(int(spec.status))
        return trust_ai.RollNeed(melee=melee, mages=mages, ranged=ranged,
                                 mp_percent=lowest_mp, attack_capped=attack_capped,
                                 active=frozenset(active))

    @staticmethod
    def _roll_remaining(member, spec, now: float) -> float:
        """Seconds left on this member's copy of the roll."""
        state = member.effect_state.get(int(spec.status)) or {}
        return float(state.get("until") or 0.0) - now

    # --- trust geomancy ------------------------------------------------------------------------
    def _trust_aura_choice(self, entity: ZoneEntity, owner, target, now: float,
                           kit: dict | None = None):
        """The one Indi-/Geo- aura to put up now, or None to keep the current one.

        A Geomancer keeps a single aura -- the next cast replaces the last -- so the
        geomancy family is not part of the buff rotation.  The zone tick measures the
        owner and the monster (``trust_ai.AuraNeed``) and lets ``choose_aura`` choose
        between refresh, precision, fury, acumen and the Frailty hex.  ``kit`` is the
        owner's restricted spell pool when one is configured.
        """
        kit = kit or entity.kit or {}
        if not kit.get("aura"):
            return None
        if int(owner.char.get("main_job", 0) or 0) == 21:
            return None                          # a Geomancer keeps their own aura
        selected = self._trust_action_set(owner, entity.trust_spell)
        custom_pool = bool(selected) and int(entity.trust_spell) in trust_ai.SPELL_ACTION_TRUSTS
        chosen = None
        if not custom_pool and trust_ai.is_entrust_trust(entity.name):
            # Sylvie keeps an owner aura (Indi-Fury or Precision) and Entrusts the
            # frailty hex on the monster.  The owner aura must not be the hostile hex
            # itself, or she spends the whole fight on the monster and leaves the
            # owner's Attack/Accuracy unbuffed.
            kit = dict(kit)
            kit["aura"] = [
                spell for spell in kit.get("aura", ())
                if (trust_ai.effect_of(spell).kind != "debuff"
                    if trust_ai.effect_of(spell) is not None else False)
            ]
        if custom_pool:
            # An explicit aura list is the owner's order, not the role heuristic.  A hex
            # still needs a monster; skip it between fights and try the next selected aura.
            for spell in kit.get("aura", []):
                spec = trust_ai.effect_of(spell)
                if spec is not None and spec.kind == "debuff" and target is None:
                    continue
                chosen = spell
                break
        else:
            chosen = trust_ai.choose_aura(kit, self._trust_aura_need(owner, target))
        if chosen is None:
            return None
        spec = trust_ai.effect_of(chosen)
        if spec is None:
            return None
        up = self._trust_aura_up(
            kit, owner, target, geomancy.bubble(str(chosen.get("name") or "")))
        if up == int(spec.effect):
            state = owner.effect_state.get(up)
            if state is None and target is not None:
                state = target.effect_state.get(up)
            if (state is not None
                    and float(state.get("until") or 0.0) - now
                    > trust_ai.AURA_REFRESH_SECONDS):
                return None                      # already the right aura; keep it up
        elif up and now < float(getattr(entity, "next_aura_swap", 0.0) or 0.0):
            return None                          # do not flap between two needs
        entity.next_aura_swap = now + trust_ai.AURA_SWAP_SECONDS
        log.info("%s puts up %s", entity.name, chosen.get("name") or chosen.get("id"))
        return chosen

    def _trust_aura_up(self, kit: dict, owner, target, bubble: str = "") -> int:
        """The geomancy status this Trust already has up in one bubble, or 0.

        Indi- and Geo- are separate bubbles: an active Geo-Malaise must not make the
        owner's Indi-Fury look present, or the owner aura would never be refreshed.
        """
        for spell in kit.get("aura", []):
            name = str(spell.get("name") or "")
            if bubble and geomancy.bubble(name) != bubble:
                continue
            spec = trust_ai.effect_of(spell)
            if spec is None:
                continue
            status = int(spec.effect)
            if owner.effect_state.get(status) is not None:
                return status
            if target is not None and target.effect_state.get(status) is not None:
                return status
        return 0

    def _trust_hex_choice(self, entity: ZoneEntity, owner, target, now: float,
                          kit: dict | None = None):
        """The Geo- hex on the monster that is missing or about to expire.

        Sylvie keeps Indi-Fury on the owner and a separate Geo- bubble on the fight.
        The hex is not part of the owner's aura choice: ``choose_aura`` only sees the
        friendly Indi- line, and this method puts the enemy-targeted Geo-Malaise on
        the monster so the Magic Defense cut stacks with the entrusted Frailty.
        """
        kit = kit or entity.kit or {}
        if target is None or not target.is_mob() or not target.alive:
            return None
        for spell in kit.get("aura", ()):
            name = str(spell.get("name") or "")
            if geomancy.bubble(name) != "geo":
                continue
            spec = trust_ai.effect_of(
                spell, int(getattr(entity, "geomancy_plus", 0) or 0), entity.name)
            if spec is None or spec.kind != "debuff":
                continue
            state = target.effect_state.get(int(spec.effect))
            if state is None:
                return spell
            until = float(state.get("until") or 0.0)
            if until and until - now <= trust_ai.AURA_REFRESH_SECONDS:
                return spell
        return None

    def _trust_aura_need(self, owner, target):
        """Measure the owner and the monster for ``trust_ai.choose_aura``."""
        char = owner.char
        max_mp = max(0, int(char.get("mp", 0)))
        mp_percent = 100.0
        if max_mp:
            mp_percent = 100.0 * max(0, int(char.get("mp_current", 0))) / max_mp
        party_mp, party_melee = self._trust_party_need(owner)
        hit_rate, attack_ratio = 1.0, 2.0
        if target is not None and target.is_mob():
            fighter = owner.stat_sheet().fighter
            mob = self.debuffed_monster(target)
            hit_rate = self._fighter_hit_rate(owner, fighter, mob)
            attack_ratio = float(fighter.attack) / max(1, int(mob.defense))
        return trust_ai.AuraNeed(
            mp_percent=mp_percent, party_mp_percent=party_mp,
            caster=int(char.get("main_job", 0) or 0) in trust_ai.MAGE_JOBS,
            target=target is not None, hit_rate=hit_rate,
            attack_ratio=attack_ratio, party_melee=party_melee,
            tp_ready=int(char.get("tp", 0) or 0) >= 1000)

    def _fighter_hit_rate(self, owner, fighter, mob) -> float:
        """How often this fighter's swings land on the monster, 0..1.

        One place for the measurement both the Geomancer (drop the bubble on Precision
        when it is short) and the Bard (sing Madrigal for it) read, so the two Trusts
        never disagree about whether the owner can hit.
        """
        return combat.hit_rate(
            accuracy=int(fighter.accuracy), evasion=int(mob.evasion),
            attacker_level=int(fighter.level), target_level=int(mob.level),
            is_pc=True, two_handed=bool(getattr(fighter, "two_handed", False)),
            corrected=combat.level_corrected(int(owner.zone)))

    def _trust_party_need(self, owner) -> tuple[float, int]:
        """The lowest MP percentage on the team and how many members fight physically."""
        lowest = 100.0
        melee = 0
        for other in self._trust_party_sessions(owner):
            max_mp = max(0, int(other.char.get("mp", 0)))
            if max_mp >= 200:
                lowest = min(lowest, 100.0
                             * max(0, int(other.char.get("mp_current", 0))) / max_mp)
            if int(other.char.get("main_job", 0) or 0) not in trust_ai.MAGE_JOBS:
                melee += 1
        if int(owner.char.get("main_job", 0) or 0) not in trust_ai.MAGE_JOBS:
            melee += 1
        return lowest, melee

    def _trust_party_sessions(self, owner) -> list:
        """The owner's party members in this zone; the owner itself is excluded."""
        party = self.party_of(int(owner.char["char_id"]))
        if party is None:
            return []
        members = []
        for member in party.members:
            if int(member.char_id) == int(owner.char["char_id"]):
                continue
            other = self.session_by_char(int(member.char_id))
            if (other is None or int(other.zone) != int(owner.zone)
                    or float(getattr(other, "dead_until", 0.0) or 0.0) > time.time()):
                continue
            members.append(other)
        return members

    def _clear_trust_aura(self, entity: ZoneEntity, owner, keep: int,
                          mob_id: int = 0, bubble: str = "") -> None:
        """Take the last aura down from one bubble, on the owner and the monster.

        A Geomancer runs an Indi- bubble and a Geo- bubble at once; each replaces only
        itself.  ``bubble`` is ``indi`` or ``geo`` so swapping the owner's Indi-Fury
        does not strip Sylvie's Geo-Malaise from the fight (or the reverse).
        """
        previous = int(getattr(entity, "geo_mob_id", 0) or 0)
        hexed = self.entity_by_id(entity.zone, previous) if previous else None
        kit = getattr(entity, "action_kit", None) or entity.kit or {}
        for spell in kit.get("aura", []):
            name = str(spell.get("name") or "")
            if bubble and geomancy.bubble(name) != bubble:
                continue
            spec = trust_ai.effect_of(spell)
            if spec is None or int(spec.effect) == int(keep):
                continue
            status = int(spec.effect)
            # Indi-fury and Geo-fury share status 549 (likewise every Indi-/Geo-
            # family).  Only clear the side this bubble actually owns: an Indi- buff
            # is on the owner, an Indi- hex or any Geo- hex is on the monster.  A Geo-
            # buff shares its owner status with the Indi- aura, so leave that alone.
            owner_side = bubble == "indi" and spec.kind == "buff"
            mob_side = (bubble == "indi" and spec.kind != "buff") or bubble == "geo"
            if owner_side and owner.effect_state.get(status) is not None:
                owner.remove_effect(status, quiet=True)
                owner.queue.append(owner.char_status())
            if mob_side and hexed is not None and hexed.effect_state.get(status) is not None:
                self._drop_mob_effect(int(entity.id), hexed, status)
        if bubble == "geo":
            entity.geo_mob_id = int(mob_id)

    def _drop_mob_effect(self, actor_id: int, mob, status: int) -> None:
        """Remove one status from a monster and tell the clients the icon wore off."""
        from .zone import sub

        mob.effect_state.pop(int(status), None)
        try:
            mob.status_effects.remove(int(status))
        except ValueError:
            pass
        body = packets.battle_action(
            int(actor_id), int(mob.id), int(status),
            message=packets.MESSAGE_STATUS_WEARS_OFF, kind=0,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH, action_id=0)
        for observer in self.sessions_in_zone(int(mob.zone)):
            if int(mob.targid) in getattr(observer, "sent_targids", set()):
                observer.queue.append(sub(0x028, body))

    def _finish_trust_cast(self, entity: ZoneEntity, owner, now: float) -> None:
        """Resolve a Trust's finished cast and put its result on the wire."""
        cast = entity.casting
        entity.casting = None
        if cast is None or owner is None or owner.zone != entity.zone:
            entity.next_cast_at = now + 1.0
            return
        spell = cast["spell"]
        kind = cast["kind"]
        spec = cast.get("effect")
        if kind == "buff" and spec is not None:
            self._land_trust_buff(entity, owner, spell, spec)
        elif kind == "cure":
            self._land_trust_cure(entity, owner, spell)
        elif kind == "debuff" and spec is not None:
            target = self.entity_by_id(entity.zone, int(cast.get("target_id") or 0))
            if target is not None and target.is_mob() and target.alive:
                self._land_trust_debuff(entity, owner, spell, spec, target, now,
                                        entrust=bool(cast.get("entrust")))
            else:
                self._say_trust_fizzle(owner, entity, spell)
        elif kind == "nuke":
            target = self.entity_by_id(entity.zone, int(cast.get("target_id") or 0))
            if target is not None and target.is_mob() and target.alive:
                self._land_trust_nuke(entity, owner, spell, target, now)
            else:
                self._say_trust_fizzle(owner, entity, spell)
        entity.next_cast_at = now + 1.0

    def _say_trust_fizzle(self, owner, entity: ZoneEntity, spell: dict) -> None:
        """A target died or left during the cast; finish quietly, like the real client."""
        if owner is not None and getattr(owner, "queue", None) is not None:
            owner.say("%s's %s fizzles." % (entity.name, spell.get("name") or "spell"))

    def _land_trust_buff(self, entity: ZoneEntity, owner, spell: dict, spec) -> None:
        """Put one of the Trust's enhancing spells on its owner and send the icon."""
        name = str(spell.get("name") or "")
        skill = int(spell.get("skill") or 0)
        if geomancy.indi_effect(name) is not None:
            # An entrust Trust has two independent bubbles: swapping the owner's
            # Indi-Fury/Precision must not take the Entrust Frailty off the monster.
            self._clear_trust_aura(
                entity, owner, int(spec.effect), 0, geomancy.bubble(name))
        # A Trust's weapons are part of its kit: Joachim's Loughnashade is Song+4, so the
        # song line reads the loadout's modifiers the way a player's gear would.
        gear = getattr(entity, "gear_mods", None) or {}
        if skill in effects.SONG_SKILLS:
            mods, tick = effects.song_potency_values(name, spec, gear)
            duration = effects.song_duration(spec, name=name, mods=gear)
            power = int(spec.power)
            # One state per song, not per icon: Minuet V and IV share icon 434 and both
            # fit on the Loughnashade bar.  The song metadata is what `//songs`, the
            # reconnect snapshot and the next plan check read.
            owner.add_effect(
                effects.song_key(int(spell["id"])), duration=duration, power=power,
                potency=spec.potency, tick=tick, icon=int(spec.effect), mods=mods,
                song_base=float(spec.duration), song_name=name,
                song_cast_at=time.time(), song_effect=int(spec.effect))
        else:
            mods = dict(spec.mods)
            duration = effects.buff_duration(
                spec, main_job=int(entity.job), main_level=int(entity.level), mods={},
                skill=skill, enhancing=(skill == trust_ai.SKILL_ENHANCING),
                white_enhancing=effects.is_white_enhancing(name), name=name)
            tick = effects.buff_tick(spec, main_job=int(entity.job),
                                     main_level=int(entity.level), mods={})
            power = effects.buff_power(spec, {})
            owner.add_effect(spec.effect, duration=duration, power=power,
                             potency=spec.potency, tick=tick, icon=spec.icon, mods=mods)
        self._queue_trust_action(
            entity, int(owner.char["char_id"]), value=int(spec.effect),
            animation=trust_ai.spell_animation(spell),
            message=packets.MESSAGE_MAGIC_GAIN_EFFECT,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))
        owner.queue += [owner.char_status(), owner.char_stats(), owner.party_member()]

    def _land_trust_cure(self, entity: ZoneEntity, owner, spell: dict) -> None:
        """Heal the owner with the Cure the kit selected."""
        cost = int(spell.get("mp") or 0)
        amount = effects.healing_amount(
            cost * 3 + int(entity.level), {}, None)
        hp = int(owner.char.get("hp_current", 0))
        healed = min(int(owner.char.get("hp", hp)), hp + amount)
        owner.char["hp_current"] = healed
        self._queue_trust_action(
            entity, int(owner.char["char_id"]), value=healed - hp,
            animation=trust_ai.spell_animation(spell),
            message=packets.MESSAGE_MAGIC_RECOVERS_HP,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))
        owner.queue += [owner.char_status(), owner.char_stats(), owner.party_member()]
        try:
            self.service.save_vitals(int(owner.char["id"]), healed,
                                     int(owner.char.get("mp_current", 0)))
        except Exception:
            pass

    def _trust_caster_stats(self, entity: ZoneEntity, target) -> tuple[int, int, int, dict]:
        """(caster INT, skill value, target INT, target modifiers) for a Trust spell."""
        sheet = stats.build_monster(int(entity.level))
        target_sheet = self.monster_sheet(target)
        target_int = int(target_sheet.attributes.get("int", 0))
        int_down = target.effect_state.get(effects.INT_DOWN)
        if int_down is not None:
            target_int = max(0, target_int - int(int_down.get("power", 0)))
        shared = getattr(entity, "shared_mods", None) or {}
        return (int(sheet.attributes.get("int", 0)) + int(shared.get(mod.INT, 0)),
                min(424, max(1, int(entity.level) * 4)),
                target_int, self.monster_debuff_mods(target))

    def _trust_resist(self, entity: ZoneEntity, spell: dict, target) -> float:
        caster_int, skill, _target_int, target_mods = \
            self._trust_caster_stats(entity, target)
        return combat.magic_resist(
            skill=skill, caster_int=caster_int, mods={},
            target_level=int(target.level),
            target_mods=target_mods)

    def _land_trust_debuff(self, entity: ZoneEntity, owner, spell: dict, spec,
                           target, now: float, *, entrust: bool = False) -> None:
        """Land a Trust enfeeble, including Dia's small opening hit."""
        if (geomancy.indi_effect(str(spell.get("name") or "")) is not None
                and not entrust):
            self._clear_trust_aura(
                entity, owner, int(spec.effect), int(target.id),
                geomancy.bubble(str(spell.get("name") or "")))
        target_sheet = self.monster_sheet(target)
        target_mnd = int(target_sheet.attributes.get("mnd", 0))
        caster_mnd = int(stats.build_monster(int(entity.level)).attributes.get("mnd", 0))
        damage = 0
        if spec.damage:
            damage = combat.dia_damage(
                base=int(spell.get("base") or 0), caster_mnd=caster_mnd,
                target_mnd=target_mnd)
        resist = self._trust_resist(entity, spell, target)
        duration = effects.debuff_duration(
            spec, skill=int(spell.get("skill") or 0), mods={},
            name=str(spell.get("name") or ""))
        potency = effects.debuff_potency(
            spec, skill=int(spell.get("skill") or 0), mods={})
        applied = self.apply_mob_effect(
            target, spec, owner, now, duration_scale=resist, duration=duration,
            potency=potency, tick=(min(damage, effects.HELIX_TICK_CAP)
                                   if spec.helix else None),
            tick_interval=(effects.HELIX_TICK_SECONDS if spec.helix else 3.0),
            first_tick_delay=(self.rng.uniform(*effects.HELIX_FIRST_TICK)
                              if spec.helix else None),
            tier=(effects.tier_of(spell.get("name") or "") if spec.helix else 0),
            name=("Defense Down" if entrust
                  else str(spell.get("name") or "")))
        defeated = False
        if damage > 0:
            defeated = int(target.hp) - damage <= 0
            self._queue_trust_action(
                entity, int(target.id), value=damage,
                animation=trust_ai.spell_animation(spell),
                message=packets.MESSAGE_MAGIC_DMG,
                category=packets.ACTION_CATEGORY_MAGIC_FINISH,
                action_id=int(spell["id"]))
            target.hp = max(0, int(target.hp) - damage)
            self._queue_mob_hp(target)
            self.wake_mob(target)
            self.add_damage_hate(target, int(owner.char["char_id"]), damage, now)
            if defeated:
                self.kill_mob(owner, target, now)
            return
        self._queue_trust_action(
            entity, int(target.id),
            value=(int(spec.effect) if applied else 0),
            animation=trust_ai.spell_animation(spell),
            message=(packets.MESSAGE_MAGIC_ENFEEB if applied
                     else packets.MESSAGE_MAGIC_NO_EFFECT),
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))
        self.add_mob_hate(target, int(owner.char["char_id"]), 100, now)

    def _land_trust_nuke(self, entity: ZoneEntity, owner, spell: dict,
                         target, now: float) -> None:
        """Resolve a Trust's direct-damage spell against the owner's target."""
        caster_int, skill, target_int, target_mods = \
            self._trust_caster_stats(entity, target)
        target_sheet = self.monster_sheet(target)
        damage = combat.magic_damage(
            base=int(spell.get("base") or 0),
            multiplier=float(spell.get("multiplier") or 1.0),
            caster_int=caster_int, target_int=target_int, skill=skill, mods={},
            target_mods=target_mods, target_level=int(target_sheet.fighter.level))
        defeated = int(target.hp) - damage <= 0
        self._queue_trust_action(
            entity, int(target.id), value=damage,
            animation=trust_ai.spell_animation(spell),
            message=packets.MESSAGE_MAGIC_DMG,
            category=packets.ACTION_CATEGORY_MAGIC_FINISH,
            action_id=int(spell["id"]))
        target.hp = max(0, int(target.hp) - damage)
        self._queue_mob_hp(target)
        self.wake_mob(target)
        self.add_damage_hate(target, int(owner.char["char_id"]), damage, now)
        if defeated:
            self.kill_mob(owner, target, now)

    def _queue_mob_hp(self, target) -> None:
        for observer in self.sessions_in_zone(target.zone):
            if int(target.targid) in getattr(observer, "sent_targids", set()):
                observer.queue_entity(target, SEND_HP)

    def _queue_trust_action(self, entity: ZoneEntity, target_id: int, *, value: int = 0,
                            animation: int = 0, message: int = 0,
                            category: int = packets.ACTION_CATEGORY_MAGIC_FINISH,
                            action_id: int = 0) -> None:
        """Broadcast one 0x028 from a Trust to every client that can see it."""
        from .zone import sub

        body = packets.battle_action(
            int(entity.id), int(target_id), int(value), animation=int(animation),
            message=int(message), kind=0, category=int(category),
            action_id=int(action_id), info=0)
        for observer in self.sessions_in_zone(entity.zone):
            if int(entity.targid) in getattr(observer, "sent_targids", set()):
                observer.queue.append(sub(0x028, body))

    def _move_trust(self, entity: ZoneEntity, owner, sessions: list, now: float) -> None:
        """Walk to the owner (or snap back if left far behind)."""
        from . import packets

        dx = float(owner.pos[0]) - entity.x
        dz = float(owner.pos[2]) - entity.z
        span = math.hypot(dx, dz)
        if span > TRUST_WARP_DISTANCE:
            entity.x = float(owner.pos[0]) + 1.5
            entity.y = float(owner.pos[1])
            entity.z = float(owner.pos[2]) + 1.5
            entity.moving = False
            self.set_animation(entity, 0, sessions)
            for observer in sessions:
                if int(entity.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue_entity(entity, packets.SEND_POSITION)
            return
        if span <= TRUST_FOLLOW_DISTANCE:
            # The client collides the player with its own team, and a Trust standing on the
            # character blocks every step.  Step out of the nearest player's bubble first:
            # being inside the follow distance is exactly when the old code stood still.
            away = self._personal_space_step(entity, sessions)
            if away is not None:
                self._move_trust_step(entity, away[0], away[1], TRUST_SIDE_STEP_SPEED,
                                      sessions, now)
                return
            if entity.moving:
                entity.moving = False
                for observer in sessions:
                    if int(entity.targid) in getattr(observer, "sent_targids", set()):
                        observer.queue_entity(entity, packets.SEND_POSITION)
            self.set_animation(entity, 0, sessions)
            return
        self._move_trust_step(entity, dx, dz, TRUST_CHASE_SPEED, sessions, now)

    def _personal_space_step(self, entity: ZoneEntity, sessions: list):
        """A direction out of the nearest player's bubble, or None when clear.

        The client collides a player with its own pets/Trusts, so a follower that stops on
        top of the player leaves them unable to move (the blocker is inside their collision
        radius).  There is no client flag to walk through party members, so the follower
        yields instead: it steps away and the player's next step is free.
        """
        nearest = None
        nearest_span = TRUST_PERSONAL_SPACE
        for session in sessions:
            if getattr(session, "gone", False) or session.zone != entity.zone:
                continue
            dx = entity.x - float(session.pos[0])
            dz = entity.z - float(session.pos[2])
            span = math.hypot(dx, dz)
            if span < nearest_span:
                nearest, nearest_span = (dx, dz, span), span
        if nearest is None:
            return None
        dx, dz, span = nearest
        if span > 0.05:
            return dx, dz
        # Exactly on top of the player: there is no direction in the position, so pick one
        # that cannot flip every tick.
        return (1.0, 0.0) if int(entity.targid) & 1 else (0.0, 1.0)

    def _move_trust_step(self, entity: ZoneEntity, dx: float, dz: float,
                         speed: float, sessions: list, now: float) -> None:
        """Move an alter ego toward a point and stream its position on the AI beat."""
        elapsed = max(0.0, min(0.5, now - float(entity.last_move_at or now)))
        step = speed * elapsed
        entity.last_move_at = now
        span = math.hypot(dx, dz) or 1.0
        if step <= 0 or span <= 0.01:
            return
        travel = min(step, span)
        entity.x += dx / span * travel
        entity.z += dz / span * travel
        entity.moving = True
        entity.rot = heading_to_rot(dx, dz)
        if now - float(entity.last_sync_at or 0.0) < MOB_SYNC_INTERVAL_RUN:
            return
        entity.last_sync_at = now
        for observer in sessions:
            if int(entity.targid) in getattr(observer, "sent_targids", set()):
                observer.queue_entity(entity, packets.SEND_POSITION)

    def _tick_pet(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        """Follow the owner, or close on and swing at the owner's current target."""
        if not entity.alive or int(entity.hp) <= 0:
            self.despawn_pet(entity, now, "defeated")
            return
        owner = self.session_by_char(entity.owner_char_id)
        if (owner is None or owner.zone != entity.zone or getattr(owner, "gone", False)
                or owner.dead_until or int(owner.char.get("hp_current", 0)) <= 0):
            self.despawn_pet(entity, now, "owner gone")
            return
        if getattr(entity, "pet_type", "") == "luopan":
            if now >= float(getattr(entity, "next_geo_aura", 0.0) or 0.0):
                entity.next_geo_aura = now + 1.5
                try:
                    owner._apply_geo_bubble(entity, now)
                except Exception:
                    log.warning("luopan aura refresh failed", exc_info=True)
            if now >= float(getattr(entity, "next_geo_tick", 0.0) or 0.0):
                drain = max(0, int(getattr(entity, "geo_drain", 0) or 0))
                if drain:
                    entity.hp = max(0, int(entity.hp) - drain)
                    self._queue_mob_hp(entity)
                entity.next_geo_tick = now + 3.0
                if int(entity.hp) <= 0:
                    self.despawn_pet(entity, now, "luopan expired")
                    return
        if getattr(entity, "pet_state", "follow") == "stay":
            return
        target = None
        if getattr(entity, "pet_state", "follow") in ("fight", "sic", "ready"):
            if owner.engaged_id:
                candidate = self.entity_by_id(entity.zone, int(owner.engaged_id))
                if candidate is not None and candidate.is_mob() and candidate.alive:
                    target = candidate
        if target is None:
            self._move_trust(entity, owner, sessions, now)
            return
        distance = entity.distance_to(target.x, target.y, target.z)
        if distance > TRUST_REACH:
            self.set_animation(entity, 1, sessions)
            self._move_trust_step(entity, target.x - entity.x, target.z - entity.z,
                                  TRUST_CHASE_SPEED, sessions, now)
            return
        if entity.moving:
            entity.moving = False
            for observer in sessions:
                if int(entity.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue_entity(entity, SEND_POSITION)
        entity.rot = heading_to_rot(target.x - entity.x, target.z - entity.z)
        self.set_animation(entity, 1, sessions)
        if (getattr(entity, "pet_type", "") == "wyvern"
                and now >= float(getattr(entity, "next_breath_at", 0.0) or 0.0)):
            amount = max(1, 100 + int(getattr(entity, "breath_bonus", 0)))
            defeated = int(target.hp) - amount <= 0
            target.hp = max(0, int(target.hp) - amount)
            self.add_damage_hate(target, int(owner.char["char_id"]), amount, now)
            self._queue_mob_hp(target)
            for observer in sessions:
                if int(entity.targid) in getattr(observer, "sent_targids", set()):
                    observer.queue.append(sub(0x028, packets.battle_action(
                        int(entity.id), int(target.id), amount, kind=2,
                        message=packets.MESSAGE_DAMAGE,
                        category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=1)))
            entity.next_breath_at = now + 20.0
            if defeated:
                self.kill_mob(owner, target, now)
            return
        if now >= float(entity.next_attack_at or 0.0):
            self.trust_attack(entity, target, owner, now)

    def entity_by_targid(self, zone: int, targid: int):
        for entity in self.entities_for_zone(zone):
            if entity.targid == targid:
                return entity
        return None

    def entity_by_id(self, zone: int, entity_id: int):
        for entity in self.entities_for_zone(zone):
            if entity.id == entity_id:
                return entity
        return None

    def session_by_char(self, char_id: int):
        for session in self.sessions.values():
            if (not session.logged_in or session.zoning
                    or getattr(session, "sleeping", False)
                    or getattr(session, "gone", False)):
                continue
            if int(session.char["char_id"]) == int(char_id):
                return session
        return None

    def session_by_character_ids(self, character_id: int, char_id: int | None = None):
        """A live session by either id the database row carries.

        A client controls the wire id it sends in 0x00A, and ``world.py`` writes that id
        into ``session.char["char_id"]``.  Some client builds use the database id there
        while the ``characters`` row stores a content id, so a lookup by only the stored
        ``char_id`` misses a perfectly live character.  The DB id is unchanged and always
        present in the session's ``id``.
        """
        wanted = {int(character_id)}
        if char_id is not None:
            wanted.add(int(char_id))
        for session in self.sessions.values():
            if (not session.logged_in or session.zoning
                    or getattr(session, "sleeping", False)
                    or getattr(session, "gone", False)):
                continue
            if (int(session.char.get("id") or 0) in wanted
                    or int(session.char.get("char_id") or 0) in wanted):
                return session
        return None

    def session_by_name(self, name: str):
        """The live session with this exact character name, or None.

        ``//invite <name>`` resolves the name here, on the server, rather than through the
        client's local player list: a box in another zone or out of spawn range can still
        be invited by name.
        """
        wanted = str(name or "").strip().casefold()
        if not wanted:
            return None
        for session in self.sessions.values():
            if not session.logged_in or session.zoning or getattr(session, "gone", False):
                continue
            if not getattr(session, "key", None):
                continue
            if str(session.char.get("name") or "").casefold() == wanted:
                return session
        return None

    def sessions_in_zone(self, zone: int) -> list:
        return [s for s in self.sessions.values()
                if s.logged_in and not s.zoning and not getattr(s, "sleeping", False)
                and not getattr(s, "gone", False)
                and int(s.zone) == int(zone) and s.key]

    # --- player session lifecycle --------------------------------------------------------------
    def take_login(self, addr, character: dict, cid: int):
        """The session a clear 0x00A continues, with every session it replaces removed.

        A login continues a hand-off: the lobby's prepared session, or the session a zone
        change parked in ``by_char`` with its advanced cipher.  It never picks up a session
        just because the UDP address matches.  The OS recycles local ports, so the old code
        handed a new character the previous occupant's name, looks, gear and database id --
        the duplicate character a multibox relog produced.
        """
        from .zone import ZoneSession

        cid = int(cid)
        db_id = int(character["id"])
        content_id = int(character["char_id"])
        prepared = None
        with self.lock:
            for key in (db_id, cid, content_id):
                candidate = self.by_char.pop(key, None)
                if candidate is None:
                    continue
                if int(getattr(candidate, "char", {}).get("id", -1)) == db_id:
                    prepared = candidate
                else:
                    self.evict_session(candidate, reason="wrong hand-off")
                break
            # Two hand-off keys can hold copies for the same character (one prepared by
            # the lobby, one left by an older zone change); only the one we continue is
            # kept.
            for key, value in list(self.by_char.items()):
                if value is not prepared and int(getattr(value, "char", {}).get("id", -1)) == db_id:
                    self.evict_session(value, reason="duplicate hand-off")

        continuing = False
        if prepared is not None and prepared.zoning:
            # This is the second half of a zone change.  Keep the live character state and
            # the advanced cipher, but only inside the window where the client can still be
            # loading the next zone.  The window starts when the zone change is queued; the
            # previous packet may be minutes old on a box that was standing still.
            changed_at = float(getattr(prepared, "zone_change_at", 0.0) or
                               prepared.last_packet_at)
            continuing = bool(prepared.key is not None and
                              time.time() - changed_at <= ZONE_CHANGE_TIMEOUT)
            if not continuing:
                self.evict_session(prepared, reason="stale zone change")
                prepared = None
        elif prepared is not None:
            # A fresh session the lobby prepared for this login: no live state to keep.
            prepared.char = character
            prepared.zoning = False

        # Every other session claiming this character is a force-quit ghost.  A session at
        # this address is usually the previous occupant of a recycled UDP port, but on a
        # multibox host it can also be another box still loading its zone (the sockets for
        # the new zone take each other's old ports), so that case is kept below.
        for other_addr, other in list(self.sessions.items()):
            if other is prepared:
                continue
            same_character = int(getattr(other, "char", {}).get("id", -1)) == db_id
            if same_character:
                # Save the last position the dead client reported: the new login already
                # read its own row, and the next one should start where it stopped.
                self.evict_session(other, save=True, reason="replaced by a login")
            elif other_addr == addr:
                if getattr(other, "zoning", False):
                    # Box clients share one host, and the sockets they open for the new zone
                    # can take each other's old ports.  The session parked here belongs to
                    # another character still loading its zone: its 0x00B already went out
                    # and its client is about to reconnect somewhere.  Keep the hand-off
                    # (the address mapping below replaces it, so nothing is misdelivered);
                    # evicting it dropped that box from the party and from the advanced
                    # cipher it was about to prove.
                    self.park_keys(other)
                    log.info("%s keeps %s's hand-off; another login took the address",
                             addr, other.char.get("name", "?"))
                    continue
                self.evict_session(other, save=True, reason="replaced by a login")

        if prepared is None:
            prepared = ZoneSession(self, addr, character)
        else:
            # The old connection (same or different address) is over.  The zone-change
            # hand-off shares this object, so only the address changes.
            for other_addr, other in list(self.sessions.items()):
                if other is prepared and other_addr != addr:
                    self.sessions.pop(other_addr, None)
            prepared.addr = addr
        prepared.char["char_id"] = cid
        prepared.last_packet_at = time.time()
        return prepared, continuing

    def evict_session(self, session, *, save: bool = False, reason: str = "") -> None:
        """Remove a dead session: despawn it, free its targid and forget its hand-off."""
        if session is None:
            return
        # A session dropped mid-hand-off leaves a live client holding an advanced cipher.
        # Park the sequence before forgetting it, so its next 0x00A can still be read.
        self.park_keys(session)
        # Do this before gone is set: the other members get a fresh roster without it.
        try:
            self.leave_party(session)
        except Exception as exc:
            log.warning("%s party cleanup failed: %s", getattr(session, "addr", "?"), exc)
        self.despawn_player(session)
        char_id = int(getattr(session, "char", {}).get("char_id", 0))
        self.release_player_targid(char_id)
        with self.lock:
            for key, value in list(self.by_char.items()):
                if value is session:
                    self.by_char.pop(key, None)
        for addr, value in list(self.sessions.items()):
            if value is session:
                self.sessions.pop(addr, None)
        session.gone = True
        session.queue.clear()
        session.last = None
        if save:
            try:
                session.save_position(force=True)
            except Exception as exc:
                log.debug("%s last position not saved: %s", getattr(session, "addr", "?"), exc)
        # The buffs, food and ability cooldowns this character should find again on its next
        # login are written before the session goes (game/live_state.py).  This is the
        # dropped-link path: the reaper, a login that replaced a ghost, or a hand-off that
        # was never acknowledged.  A deliberate logout already wrote its recasts-only row.
        save_state = getattr(session, "save_live_state", None)
        if save_state is not None:
            try:
                save_state()
            except Exception as exc:
                log.debug("%s reconnect snapshot not saved: %s",
                          getattr(session, "addr", "?"), exc)
        log.info("%s released %s (%s, char %#x)", getattr(session, "addr", "?"),
                 getattr(session, "char", {}).get("name", "?"),
                 reason or "session ended", char_id)

    def reap_sessions(self, now: float | None = None) -> None:
        """Forget clients that stopped talking (force-quit, crash, dropped network).

        A zone session has no TCP connection to observe, so silence is the only disconnect
        signal.  Reaping is what stops a force-quit character from remaining in everyone
        else's zone as a frozen twin.
        """
        now = time.time() if now is None else now
        for addr, session in list(self.sessions.items()):
            if not session.logged_in or getattr(session, "gone", False):
                continue
            if getattr(session, "sleeping", False):
                continue
            timeout = ZONE_CHANGE_TIMEOUT if session.zoning else SESSION_IDLE_TIMEOUT
            if session.zoning:
                last = float(getattr(session, "zone_change_at", 0.0) or
                             getattr(session, "last_packet_at", now) or now)
            else:
                last = float(getattr(session, "last_packet_at", now) or now)
            if now - last < timeout:
                continue
            log.info("%s silent for %.0fs; removing char %#x", addr, now - last,
                     int(getattr(session, "char", {}).get("char_id", 0)))
            self.evict_session(session, save=not session.zoning, reason="timed out")

    # --- player presence -----------------------------------------------------------------------
    def assign_player_targid(self, char_id: int) -> int:
        """Give a logged-in character the id other clients will know it by.

        0x400 is reserved for "the local player" in every client's own view, so other
        characters are handed ids from 0x401 up. The mapping survives a zone change and
        is released on logout.
        """
        char_id = int(char_id)
        existing = self.player_targids.get(char_id)
        if existing is not None:
            return existing
        used = set(self.player_targids.values())
        for targid in range(PLAYER_TARGID_FIRST, PLAYER_TARGID_LAST + 1):
            if targid not in used:
                self.player_targids[char_id] = targid
                return targid
        raise RuntimeError("no free player targid")

    def release_player_targid(self, char_id: int) -> None:
        self.player_targids.pop(int(char_id), None)

    # --- parties and alliances -----------------------------------------------------------------
    def party_of(self, char_id: int) -> Party | None:
        return self.party_by_char.get(int(char_id))

    def group_id(self, char_id: int) -> int:
        group = self.party_of(char_id)
        if group is not None:
            return group.id
        # A solo player with Trusts has the synthetic party page from party_packets;
        # its id is the character id, matching LandSandBoat's CParty(PMaster).  A plain
        # solo still has no group, because 0x0E1 id 0 is what the retail client cannot
        # read.
        session = self.session_by_char(char_id)
        if session is not None and self.active_trusts(session):
            return int(char_id)
        return 0

    def _party_groups(self, party: Party) -> list[Party]:
        if party is None:
            return []
        return list(party.alliance.parties) if party.alliance is not None else [party]

    def _group_sessions_list(self, groups) -> list:
        """Every live session in these parties, once, including the other alliance parties."""
        seen: set[int] = set()
        sessions = []
        for group in groups:
            for member in group.members:
                session = self.session_by_char(member.char_id)
                if session is None or id(session) in seen:
                    continue
                seen.add(id(session))
                sessions.append(session)
        return sessions

    def _group_sessions(self, party: Party) -> list:
        return self._group_sessions_list(self._party_groups(party))

    def _refresh_member(self, member: PartyMember) -> None:
        session = self.session_by_char(member.char_id)
        if session is not None:
            member.update_from_session(session)

    def active_trusts(self, session) -> list:
        """The live alter egos a session owns, in call order."""
        if session is None:
            return []
        return [entity for entity in getattr(session, "trust_entities", [])
                if getattr(entity, "alive", False)]

    def trust_party_member(self, entity) -> PartyMember:
        """A Trust's 0x0DD/0x0DF row.  It is not a PartyMember in the database sense."""
        return PartyMember(
            char_id=int(entity.id),
            name=str(entity.name or ""),
            zone=int(entity.zone),
            targid=int(entity.targid),
            hp=int(entity.hp),
            mp=int(entity.mp),
            tp=0,
            hp_max=max(1, int(entity.hp_max)),
            mp_max=max(0, int(entity.mp_max)),
            main_job=int(getattr(entity, "job", 0) or 0),
            main_level=int(getattr(entity, "level", 0) or 0),
        )

    def _trust_party_recipients(self, session) -> list:
        """The clients that draw ``session``'s Trusts: its party, or the owner alone."""
        party = self.party_of(int(session.char["char_id"]))
        if party is not None:
            return self._group_sessions(party)
        return [session]

    def _trust_rows(self, session) -> list[tuple[PartyMember, int]]:
        """(row, targid) for every Trust the session has out."""
        return [(self.trust_party_member(entity), int(entity.targid))
                for entity in self.active_trusts(session)]

    def party_packets(self, session) -> list:
        """The GROUP_TBL + one GROUP_LIST per row this client needs to draw its roster.

        The client does not keep a local roster: the whole group page comes from these
        packets.  A member in another zone is sent their zone number instead of vitals.
        Trusts are injected into the same roster as their owner (LandSandBoat appends
        them to the table and sends one GROUP_LIST after the owner's row); this is what
        makes an alter ego appear in the party menu instead of only in the world.
        """
        from .zone import sub

        party = self.party_of(session.char["char_id"])
        owner = int(session.char["char_id"])
        own_trusts = self.active_trusts(session)
        if party is None:
            if not own_trusts:
                return []
            # A solo player with Trusts still has a party page: one player row plus the
            # Trust rows.  Keep this synthetic party out of self.parties so invites and
            # "already in a party" checks still treat the character as solo.
            member = PartyMember.from_session(session)
            groups = [Party(id=member.char_id, leader_id=member.char_id,
                            members=[member])]
        else:
            groups = self._party_groups(party)
        kind = (PARTY_KIND_ALLIANCE if party is not None and party.alliance is not None
                else PARTY_KIND_PARTY)
        player_entries = []
        trust_entries = []
        rows = []
        number = 0
        for group in groups:
            for member in group.members:
                self._refresh_member(member)
                flags = group.flags(member)
                # The receiver sees itself as 0x400, never as the targid other clients use.
                targid = SELF_TARGID if member.char_id == owner else member.targid
                player_entries.append((member.char_id, targid, flags, member.zone))
                rows.append((member, flags, number, targid))
                number += 1
                member_session = self.session_by_char(member.char_id)
                for trust, trust_targid in self._trust_rows(member_session):
                    trust_entries.append((trust.char_id, trust_targid, 0, trust.zone))
                    rows.append((trust, 0, number, trust_targid))
                    number += 1
        out = [sub(0x0C8, packets.group_table(
            player_entries + trust_entries, kind))]
        for member, flags, number, targid in rows:
            out.append(sub(0x0DD, packets.group_list(member, number, flags, session.zone,
                                                    targid=targid)))
        return out

    def solo_roster_packets(self, session) -> list:
        """The empty GROUP_TBL plus the client's own GROUP_LIST row.

        A plain solo player gets no group page from ``party_packets``.  The client reads
        its own job pair from row 0 of the party table, so without this a fresh login
        reports MainJob 0 and the HUD's spell and Trust windows go empty (the "No trusts
        for this job pair yet" panel) even though the server has the job.  This is the
        same representation ``_queue_party_reset`` uses when a party is disbanded: an
        empty roster table with the player's own row, not a one-person party.
        """
        from .zone import sub

        member = PartyMember.from_session(session)
        return [
            sub(0x0C8, packets.group_table([], PARTY_KIND_PARTY)),
            sub(0x0DD, packets.group_list(member, 0, 0, session.zone,
                                         targid=SELF_TARGID)),
        ]

    def party_buff_packets(self, session) -> list:
        """S2C 0x076: the status icons of the *other* party members.

        The client keeps those icons in ``partystatusicons_t`` and the Party Info HUD
        reads them from there.  The packet has five 48-byte member rows (UniqueNo,
        ActIndex, padding, two bits per slot in ``Bits``, then the 32 low bytes).
        Sending it after a roll is what makes Twodough and Threedough show the same
        icon Onedough has instead of "status effects are not sent for this party".
        """
        from .zone import sub

        party = self.party_of(int(session.char["char_id"]))
        if party is None:
            return []
        viewer = int(session.char["char_id"])
        others = [other for other in self._group_sessions(party)
                  if int(other.char["char_id"]) != viewer
                  and int(other.zone) == int(session.zone)][:5]
        body = bytearray(0xF0)
        for index, other in enumerate(others):
            offset = index * 48
            struct.pack_into("<IHH", body, offset,
                             int(other.char["char_id"]),
                             int(getattr(other, "targid", 0) or 0), 0)
            bits = 0
            for slot, effect_id in enumerate(list(other.status_effects)[:32]):
                state = other.effect_state.get(int(effect_id)) or {}
                icon = effects.icon_for(
                    int(effect_id), int(state.get("icon", 0) or 0),
                    int(state.get("power", 0) or 0)) & 0x3FF
                body[offset + 16 + slot] = icon & 0xFF
                bits |= (icon >> 8 & 3) << (2 * slot)
            struct.pack_into("<Q", body, offset + 8, bits)
        return [sub(0x076, bytes(body))]

    def queue_party_buffs(self, session) -> None:
        """Refresh every party member's 0x076 view after a shared buff changes."""
        party = self.party_of(int(session.char["char_id"]))
        sessions = self._group_sessions(party) if party is not None else [session]
        for viewer in sessions:
            viewer.queue += self.party_buff_packets(viewer)

    def refresh_trust_roster(self, session) -> None:
        """Re-send the party page after a Trust is called or released."""
        if session is None or getattr(session, "gone", False) or getattr(session, "zoning", False):
            return
        for recipient in self._trust_party_recipients(session):
            if getattr(recipient, "zone_loaded", False):
                recipient.queue += self.party_packets(recipient)

    def _sync_trust_vitals(self) -> None:
        """Billboard a Trust's HP/MP/TP on 0x0DF when it changes.

        The client's party page reads Trust vitals from GROUP_ATTR exactly like a
        player's; without this the bars stay at the values from the spawn row forever.
        """
        from .zone import sub

        for session in list(self.sessions.values()):
            if (not session.logged_in or session.zoning
                    or getattr(session, "sleeping", False)
                    or getattr(session, "gone", False)):
                continue
            trusts = self.active_trusts(session)
            if not trusts:
                continue
            recipients = self._trust_party_recipients(session)
            for entity in trusts:
                member = self.trust_party_member(entity)
                vitals = (member.hp, member.mp, member.hp_max, member.mp_max,
                          member.targid, member.zone)
                if getattr(entity, "party_vitals", None) == vitals:
                    continue
                entity.party_vitals = vitals
                # LandSandBoat's Trust overload leaves ZoneNo zero; the same-zone
                # GROUP_LIST row does the same, so the client treats it as present.
                body = packets.group_attr(replace(member, zone=0))
                for recipient in recipients:
                    if getattr(recipient, "zone_loaded", False):
                        recipient.queue.append(sub(0x0DF, body))

    def _reload_groups(self, groups, *, exclude=None) -> None:
        for session in self._group_sessions_list(groups):
            if session is exclude:
                continue
            if getattr(session, "zone_loaded", False):
                session.queue += self.party_packets(session)

    def reload_party(self, party: Party, *, exclude=None) -> None:
        if party is not None:
            self._reload_groups(self._party_groups(party), exclude=exclude)

    def _account_family(self, account_id: int) -> set[int]:
        service = getattr(self, "service", None)
        if service is None or not account_id:
            return set()
        try:
            return {int(value) for value in service.account_family_ids(int(account_id))}
        except Exception:
            log.warning("could not read account family %s", account_id, exc_info=True)
            return set()

    def account_kind(self, account_id: int) -> str:
        service = getattr(self, "service", None)
        if service is None or not account_id:
            return ""
        try:
            return str(service.account(int(account_id)).get("kind", "main"))
        except Exception:
            return ""

    def _family_party_for(self, session) -> Party | None:
        """The one party made only of this account family, if the character is solo.

        A party with a friend in it is deliberately not a candidate: rejoining it and
        taking the lead would demote somebody outside the team.
        """
        char_id = int(session.char.get("char_id", 0) or 0)
        account_id = int(session.char.get("account_id") or 0)
        if not char_id or not account_id or self.party_of(char_id) is not None:
            return None
        family = self._account_family(account_id)
        if len(family) <= 1:
            return None
        candidates = []
        for party in self.parties.values():
            if not party.members:
                continue
            family_only = True
            for member in party.members:
                # Account ids are stored when a member joins, but refresh first for rows
                # created before this field existed or for a session that just changed.
                self._refresh_member(member)
                if int(member.account_id) not in family:
                    family_only = False
                    break
            if family_only:
                candidates.append(party)
        if not candidates:
            return None
        return max(candidates, key=lambda party: (len(party.members), -int(party.id)))

    def recover_family_party(self, session, *, exclude_self: bool = False) -> str:
        """Rejoin a returning main account to the party its subs kept for it.

        A main that logs out, freezes past the session timeout, or is replaced by a new
        login is removed from the party and one of the subs becomes leader.  The subs are
        still grouped, so inviting them again is refused: the main is no longer the
        inviter's party.  On the next zone-in, join that family-only party and take the
        lead back.  This is the non-destructive recovery; disbanding the subs and
        re-inviting them would lose their party and require them to answer again.
        """
        char_id = int(session.char.get("char_id", 0) or 0)
        if not char_id or self.party_of(char_id) is not None:
            return ""
        if self.account_kind(int(session.char.get("account_id") or 0)) != "main":
            return ""
        party = self._family_party_for(session)
        if party is None:
            return ""
        if party.is_full():
            return "Your team's party is full, so you could not rejoin it."
        if not self.join_party(party, session):
            return ""
        previous_leader = party.leader_id
        party.leader_id = char_id
        self.reload_party(party, exclude=session if exclude_self else None)
        log.info("%s rejoined the family party and took the lead from %s",
                 session.char.get("name"), previous_leader)
        return "Rejoined your team's party and took the lead."

    def _queue_party_reset(self, session) -> None:
        """Tell a client it is solo again: empty GROUP_TBL and its own row."""
        if not getattr(session, "zone_loaded", False):
            return
        # A character with Trusts still has a party page after leaving the group: the
        # synthetic solo roster keeps the alter egos visible instead of clearing them.
        messages = self.party_packets(session) if self.active_trusts(session) else []
        if not messages:
            messages = self.solo_roster_packets(session)
        # The vitals packets are a nicety; a stat-sheet failure must not stop a logout
        # or a disband from clearing the roster.
        try:
            messages += [session.char_status(), session.char_stats(), session.party_member()]
        except Exception as exc:
            log.warning("%s party reset vitals skipped: %s",
                        getattr(session, "addr", "?"), exc)
        session.queue += messages

    def create_party(self, session) -> Party:
        member = PartyMember.from_session(session)
        group = Party(id=member.char_id, leader_id=member.char_id, members=[member])
        self.parties[group.id] = group
        self.party_by_char[member.char_id] = group
        return group

    def join_party(self, group: Party, session) -> bool:
        member = PartyMember.from_session(session)
        if group is None or group.member(member.char_id) is not None or group.is_full():
            return False
        group.members.append(member)
        self.party_by_char[member.char_id] = group
        return True

    def remove_from_party(self, char_id: int, *, reset_session=None,
                          reload_groups: bool = True) -> Party | None:
        """Take one member out.  The leader passes to the next member, or the party folds."""
        char_id = int(char_id)
        group = self.party_by_char.pop(char_id, None)
        if group is None:
            return None
        member = group.member(char_id)
        if member is not None:
            group.members.remove(member)
        if reset_session is not None and not getattr(reset_session, "gone", False):
            self._queue_party_reset(reset_session)
        if group.is_empty():
            self.parties.pop(group.id, None)
            if group.alliance is not None:
                self._detach_party(group, reload_groups=reload_groups)
        else:
            if group.leader_id == char_id:
                group.promote_leader()
            if reload_groups:
                self.reload_party(group)
        return group

    def leave_party(self, session) -> None:
        char_id = int(session.char.get("char_id", 0) or 0)
        if char_id and self.party_of(char_id) is not None:
            self.remove_from_party(char_id, reset_session=session)

    def disband_party(self, group: Party) -> None:
        if group is None:
            return
        affected: list[Party] = []
        if group.alliance is not None:
            affected = self._detach_party(group, reload_groups=False)
        members = list(group.members)
        for member in members:
            self.party_by_char.pop(member.char_id, None)
        self.parties.pop(group.id, None)
        for member in members:
            session = self.session_by_char(member.char_id)
            if session is not None:
                self._queue_party_reset(session)
        for other in affected:
            if other is group or other.is_empty():
                continue
            self.reload_party(other)

    def dissolve_alliance(self, alliance: Alliance) -> None:
        if alliance is None:
            return
        groups = list(alliance.parties)
        for group in groups:
            group.alliance = None
            group.number = 0
        self.alliances.pop(alliance.id, None)
        self._reload_groups(groups)

    def leave_alliance(self, session) -> str:
        """C2S 0x06F Kind=Alliance: a party leader takes their party out of the alliance."""
        group = self.party_of(int(session.char["char_id"]))
        if group is None or group.alliance is None:
            return "Your party is not in an alliance."
        if group.leader_id != int(session.char["char_id"]):
            return "Only the party leader can leave the alliance."
        if len(group.alliance.parties) <= 1:
            self.dissolve_alliance(group.alliance)
        else:
            self._detach_party(group)
        return ""

    def disband_alliance(self, session) -> str:
        """C2S 0x070 Kind=Alliance: the alliance leader dissolves the whole alliance."""
        group = self.party_of(int(session.char["char_id"]))
        if group is None or group.alliance is None:
            return "Your party is not in an alliance."
        if group.alliance.main is not group or group.leader_id != int(session.char["char_id"]):
            return "Only the alliance leader can disband the alliance."
        self.dissolve_alliance(group.alliance)
        return ""

    def _detach_party(self, group: Party, *, reload_groups: bool = True) -> list[Party]:
        """Take a party out of its alliance; an alliance left with one party dissolves."""
        alliance = group.alliance
        if alliance is None:
            return []
        affected = list(alliance.parties)
        alliance.parties = [party for party in affected if party is not group]
        group.alliance = None
        group.number = 0
        if len(alliance.parties) <= 1:
            for party in alliance.parties:
                party.alliance = None
                party.number = 0
            self.alliances.pop(alliance.id, None)
            affected.extend(alliance.parties)
        else:
            for number, party in enumerate(alliance.parties):
                party.number = number
        if reload_groups:
            self._reload_groups([group, *affected])
        return [group, *affected]

    def form_alliance(self, main: Party, other: Party) -> Alliance | None:
        if main is None or other is None or main is other:
            return None
        if main.alliance is not None or other.alliance is not None:
            return None
        if main.is_empty() or other.is_empty():
            return None
        alliance = Alliance(id=self.next_alliance_id, parties=[main, other])
        self.next_alliance_id += 1
        self.alliances[alliance.id] = alliance
        for number, group in enumerate(alliance.parties):
            group.alliance = alliance
            group.number = number
        self._reload_groups(alliance.parties)
        return alliance

    def add_party_to_alliance(self, alliance: Alliance, group: Party) -> bool:
        if alliance is None or group is None or group.alliance is not None:
            return False
        if alliance.full or len(alliance.parties) >= ALLIANCE_MAX_PARTIES:
            return False
        used = {party.number for party in alliance.parties}
        number = next((slot for slot in range(ALLIANCE_MAX_PARTIES) if slot not in used),
                      len(alliance.parties))
        group.alliance = alliance
        group.number = number
        alliance.parties.append(group)
        self._reload_groups(alliance.parties)
        return True

    def _invite_is_auto_accepted(self, inviter, invitee) -> bool:
        """Whether a server-owned sub-account answers this invitation itself.

        A headless box has no UI for the 0x0DC prompt, and a sub-account is driven by its
        main account's launcher, so a sub in the inviter's account family joins without
        asking.  A main account, or another player's character, still gets the prompt.
        The packet-only unit fixtures have no service and fall back to the normal prompt.
        """
        config = getattr(self, "config", None)
        if config is not None and not getattr(config, "auto_accept_sub_invites", True):
            return False
        service = getattr(self, "service", None)
        if service is None:
            return False
        inviter_account = int(inviter.char.get("account_id") or 0)
        invitee_account = int(invitee.char.get("account_id") or 0)
        if not inviter_account or not invitee_account or inviter_account == invitee_account:
            return False
        try:
            account = service.account(invitee_account)
            if account.get("kind", "main") != "sub":
                return False
            return invitee_account in service.account_family_ids(inviter_account)
        except Exception:
            log.warning("could not check the account family of an invitation", exc_info=True)
            return False

    def invite(self, inviter, invitee_char_id: int, invitee_targid: int,
               kind: int) -> str:
        """Send a party/alliance invitation.  Returns an error line for the inviter, or ""."""
        from .zone import sub

        inviter_id = int(inviter.char["char_id"])
        kind = int(kind)
        if kind not in (PARTY_KIND_PARTY, PARTY_KIND_ALLIANCE):
            return "That kind of invitation is not supported."
        if int(invitee_char_id) == inviter_id:
            return "You cannot invite yourself."
        invitee = self.session_by_char(invitee_char_id)
        if invitee is None and int(invitee_targid):
            for candidate in self.sessions_in_zone(inviter.zone):
                if int(candidate.targid) == int(invitee_targid):
                    invitee = candidate
                    break
        if invitee is None:
            return "That player is not online."
        invitee_id = int(invitee.char["char_id"])
        if invitee.zoning or not invitee.zone_loaded:
            return "That player is not ready for an invitation yet."
        auto_accept = self._invite_is_auto_accepted(inviter, invitee)
        if not auto_accept and int(invitee_id) in self.pending_invites:
            return "That player already has a pending invitation."

        party = self.party_of(inviter_id)
        if party is not None and party.leader_id != inviter_id:
            return "Only the party leader can invite."
        if kind == PARTY_KIND_PARTY:
            if self.party_of(invitee_id) is not None:
                return "That player is already in a party."
            if party is not None and party.is_full():
                return "Your party is full."
        else:
            if party is None or party.leader_id != inviter_id:
                return "You must be the leader of a party to invite to an alliance."
            if party.alliance is not None:
                if party.alliance.main is not party:
                    return "Only the main party can invite to the alliance."
                if party.alliance.full:
                    return "Your alliance is full."
            target_party = self.party_of(invitee_id)
            if target_party is None or target_party.leader_id != invitee_id:
                return "That player must be the leader of a party."
            if target_party.alliance is not None:
                return "That party is already in an alliance."

        invite = PendingInvite(
            inviter_id=inviter_id,
            inviter_targid=int(getattr(inviter, "targid", 0) or 0),
            kind=kind,
            expires=time.time() + 30.0,
        )
        if auto_accept:
            # No prompt: the sub answers for itself, the way a headless box has to.
            error = self._accept_invite(invitee, invite, inviter)
            if error:
                log.warning("%s could not accept %s's invitation automatically: %s",
                            invitee.char.get("name"), inviter.char.get("name"), error)
                return "That player could not accept the invitation."
            self.pending_invites.pop(invitee_id, None)
            log.info("%s invites %s to a %s (accepted automatically)",
                     inviter.char.get("name"), invitee.char.get("name"),
                     "party" if kind == PARTY_KIND_PARTY else "alliance")
            return ""
        self.pending_invites[invitee_id] = invite
        invitee.queue.append(sub(0x0DC, packets.group_invite(
            inviter_id, int(getattr(inviter, "targid", 0) or 0),
            inviter.char.get("name") or "", kind, int(inviter.char.get("race", 0) or 0))))
        log.info("%s invites %s to a %s", inviter.char.get("name"), invitee.char.get("name"),
                 "party" if kind == PARTY_KIND_PARTY else "alliance")
        return ""

    def respond_invite(self, session, accepted: bool) -> str:
        """Answer a pending invitation.  Returns an error line for the invitee, or ""."""
        invitee_id = int(session.char["char_id"])
        invite = self.pending_invites.pop(invitee_id, None)
        if invite is None:
            return "There is no invitation to answer."
        if invite.expires < time.time():
            return "That invitation has expired."
        inviter = self.session_by_char(invite.inviter_id)
        if inviter is None:
            return "The player who invited you is no longer online."
        if not accepted:
            try:
                inviter.say("%s declined your invitation." % session.char.get("name", "The player"))
            except Exception:
                pass
            return ""
        return self._accept_invite(session, invite)

    def _accept_invite(self, session, invite: PendingInvite, inviter=None) -> str:
        """Apply an accepted invitation.  The caller owns the pending-invite bookkeeping."""
        invitee_id = int(session.char["char_id"])
        inviter = inviter or self.session_by_char(invite.inviter_id)
        if inviter is None:
            return "The player who invited you is no longer online."
        if invite.kind == PARTY_KIND_PARTY:
            if self.party_of(invitee_id) is not None:
                return "You are already in a party."
            party = self.party_of(invite.inviter_id)
            if party is None:
                party = self.create_party(inviter)
            if party.leader_id != invite.inviter_id:
                return "That player is no longer the party leader."
            if party.is_full():
                return "That party is full."
            if not self.join_party(party, session):
                return "That party could not accept you."
            self.reload_party(party)
            return ""
        inviter_party = self.party_of(invite.inviter_id)
        invitee_party = self.party_of(invitee_id)
        if inviter_party is None or inviter_party.leader_id != invite.inviter_id:
            return "That player is no longer the leader of a party."
        if invitee_party is None or invitee_party.leader_id != invitee_id:
            return "You must be the leader of a party to join an alliance."
        if invitee_party.alliance is not None:
            return "Your party is already in an alliance."
        if inviter_party.alliance is not None:
            if inviter_party.alliance.main is not inviter_party:
                return "Only the main party can add parties to the alliance."
            if not self.add_party_to_alliance(inviter_party.alliance, invitee_party):
                return "That alliance is full."
        elif self.form_alliance(inviter_party, invitee_party) is None:
            return "The alliance could not be formed."
        return ""

    def kick_member(self, leader, victim_id: int, kind: int) -> str:
        """Remove a member (party) or a party (alliance).  Only the leader may do this."""
        leader_id = int(leader.char["char_id"])
        group = self.party_of(leader_id)
        if group is None:
            return "You are not in a party."
        if kind == PARTY_KIND_ALLIANCE:
            if group.alliance is None or group.alliance.main is not group:
                return "Only the alliance leader can remove a party."
            victim_party = self.party_of(victim_id)
            if victim_party is None:
                # The client may name a member of the party instead of its leader.
                victim_party = next((party for party in group.alliance.parties
                                     if party.member(victim_id) is not None), None)
            if victim_party is None or victim_party is group:
                return "That party is not in your alliance."
            self._detach_party(victim_party)
            return ""
        if group.leader_id != leader_id:
            return "Only the party leader can remove a member."
        if int(victim_id) == leader_id:
            self.leave_party(leader)
            return ""
        if group.member(victim_id) is None:
            return "That player is not in your party."
        victim = self.session_by_char(victim_id)
        self.remove_from_party(victim_id, reset_session=victim)
        return ""

    def set_party_leader(self, session, name: str, alliance_leader: bool = False) -> str:
        group = self.party_of(int(session.char["char_id"]))
        if group is None:
            return "You are not in a party."
        wanted = str(name).casefold()
        if alliance_leader:
            alliance = group.alliance
            if alliance is None:
                return "You are not in an alliance."
            if alliance.main is not group or group.leader_id != int(session.char["char_id"]):
                return "Only the alliance leader can pass alliance leadership."
            target_party = next((party for party in alliance.parties
                                 if any(member.name.casefold() == wanted
                                        for member in party.members)), None)
            if target_party is None:
                return "That player is not in your alliance."
            member = next(member for member in target_party.members
                          if member.name.casefold() == wanted)
            # The alliance leader is the leader of the main party, so the chosen
            # member's party moves to the front and takes number 0.
            alliance.parties = [target_party] + [party for party in alliance.parties
                                                 if party is not target_party]
            for number, party in enumerate(alliance.parties):
                party.number = number
            target_party.leader_id = member.char_id
            self._reload_groups(alliance.parties)
            return ""
        member = next((entry for entry in group.members
                       if entry.name.casefold() == wanted), None)
        if member is None:
            return "That player is not in your party."
        if group.leader_id != int(session.char["char_id"]):
            return "Only the party leader can pass leadership."
        group.leader_id = member.char_id
        self.reload_party(group)
        return ""

    def party_zone_changed(self, session) -> None:
        """A member stepped through a zone line: the roster's zone column follows them."""
        char_id = int(session.char.get("char_id", 0) or 0)
        group = self.party_of(char_id)
        if group is None:
            return
        member = group.member(char_id)
        if member is None:
            return
        member.zone = int(session.zone)
        self._reload_groups([group])

    def sync_parties(self, now: float | None = None) -> None:
        """Refresh member vitals about twice a second; billboards a 0x0DF on change."""
        now = time.time() if now is None else now
        if now < self.next_party_sync:
            return
        self.next_party_sync = now + 0.5
        for char_id, invite in list(self.pending_invites.items()):
            if invite.expires <= now:
                self.pending_invites.pop(char_id, None)
        for group in list(self.parties.values()):
            if group.alliance is not None and group.alliance.main is not group:
                continue
            groups = self._party_groups(group)
            changed: list[PartyMember] = []
            reload_needed = False
            for party in groups:
                for member in party.members:
                    session = self.session_by_char(member.char_id)
                    if session is None:
                        continue
                    before = member.identity()
                    vitals = member.vitals()
                    member.update_from_session(session)
                    if member.identity() != before:
                        reload_needed = True
                    elif member.vitals() != vitals:
                        changed.append(member)
            if reload_needed:
                self._reload_groups(groups)
            elif changed:
                from .zone import sub

                recipients = self._group_sessions_list(groups)
                for member in changed:
                    body = packets.group_attr(member)
                    for session in recipients:
                        if int(session.char.get("char_id", 0) or 0) == member.char_id:
                            continue
                        if getattr(session, "zone_loaded", False):
                            session.queue.append(sub(0x0DF, body))
        # Trust bars are not in a Party object; the owner's roster injects them and this
        # keeps their HP/MP/TP in step with the live entity.
        self._sync_trust_vitals()

    def broadcast_player(self, session, mask: int, moving: bool | None = None) -> None:
        """Send one player's entity update to every nearby client that has it spawned.

        Movement is ambient, like a monster's: one message per observer per player, and
        the newest position replaces the one already waiting, so five moving boxes cannot
        fill each other's packet queues.
        """
        from .zone import sub

        char_id = int(session.char["char_id"])
        body = session.player_body(mask, moving=moving)
        for observer in self.sessions_in_zone(session.zone):
            if observer is session or not getattr(observer, "entities_sent", False):
                continue
            if char_id not in observer.seen_players:
                continue
            if int(mask) == SEND_POSITION and int(session.targid):
                observer.queue_position(
                    0x00D, int(session.targid), body,
                    priority=math.dist(observer.pos[:3], session.pos[:3]))
            else:
                observer.queue.append(sub(0x00D, body))

    def is_family_leader(self, session) -> bool:
        """True when this session's account is a main account (it leads its boxes)."""
        try:
            return self.service.account(
                int(session.char.get("account_id") or 0)).get("kind") == "main"
        except Exception:
            return False

    def family_followers(self, leader) -> list:
        """Other main-family sessions in the leader's zone, for a shared zone line.

        Only the main account leads a family zone; a sub running through a line alone
        does not drag the main or its siblings. The caller must collect this before moving
        the leader, while every follower is still in the old zone.
        """
        account_id = int(leader.char.get("account_id") or 0)
        if not account_id:
            return []
        service = getattr(self, "service", None)
        if service is None:
            return []
        try:
            if service.account(account_id).get("kind") != "main":
                return []
            family = {int(value) for value in service.account_family_ids(account_id)}
        except Exception:
            return []
        return [session for session in self.sessions_in_zone(leader.zone)
                if session is not leader
                and int(session.char.get("account_id") or 0) in family]

    def despawn_player(self, session) -> None:
        """Remove a player from the clients that can see it (zone change, logout)."""
        from .zone import sub

        # Alter egos do not survive their master's zone line, logout or death.  Do this
        # before the zone changes below, while the Trust still knows the old zone.
        try:
            session.despawn_trusts()
        except Exception as exc:
            log.warning("%s trust cleanup failed: %s", getattr(session, "addr", "?"), exc)
        char_id = int(session.char["char_id"])
        for observer in self.sessions_in_zone(session.zone):
            if observer is session:
                continue
            seen = observer.seen_players.pop(char_id, None)
            if seen is None:
                continue
            # The client knows this character under the targid it was spawned with. A
            # replacement session can carry a different one, so despawn the copy the
            # observer actually holds instead of leaving a twin behind.
            targid = int(getattr(seen, "targid", 0) or session.targid)
            observer.queue.append(sub(0x00D, seen.player_body(SEND_PLAYER_DESPAWN,
                                                              targid=targid)))
        session.seen_players.clear()

    def apply_saved_design(self, character_id: int, blueprint: dict) -> None:
        """Repaint every live copy of a character whose design was just saved.

        A character can have one connected session and, briefly, a prepared
        hand-off or zone-change session.  Both are updated so a relog cannot
        snap back to the old face.
        """
        with self.lock:
            candidates = {id(session): session
                          for session in list(self.sessions.values()) + list(self.by_char.values())}
        for session in candidates.values():
            if int(getattr(session, "char", {}).get("id", -1)) != int(character_id):
                continue
            try:
                session.apply_design(blueprint)
            except Exception as exc:
                log.warning("could not repaint character %s: %s", character_id, exc)

    def refresh_player_appearance(self, session) -> None:
        """Replace a player's 0x00D spawn for the clients that currently draw it."""
        from .zone import sub

        char_id = int(session.char["char_id"])
        with self.lock:
            observers = [s for s in self.sessions_in_zone(session.zone)]
        for observer in observers:
            if observer is session or not getattr(observer, "entities_sent", False):
                continue
            seen = observer.seen_players.pop(char_id, None)
            if seen is None:
                continue
            targid = int(getattr(seen, "targid", 0) or session.targid)
            observer.queue.append(sub(0x00D, seen.player_body(
                SEND_PLAYER_DESPAWN, targid=targid)))
            observer.seen_players[char_id] = session
            observer.queue.append(sub(0x00D, session.player_body(SEND_CHAR_SPAWN)))

    # --- the tick ------------------------------------------------------------------------------
    def set_team_anchor(self, source, zone: int, pos) -> None:
        """Remember where the team was just called, for boxes that were not up yet.

        ``//warp all me`` can only move sessions that exist.  A box whose client is still
        logging in (a relaunch, a reconnect) is absent from ``sessions`` and lands at its
        saved spot when it finishes; the anchor makes it join the team on that zone-in
        instead of waiting for the user to press the command again.
        """
        family = set(int(x) for x in self.service.account_family_ids(
            int(source.char.get("account_id") or 0)))
        live = {int(session.char.get("account_id", 0)) for session in self.sessions.values()
                if getattr(session, "logged_in", False)}
        waiting = family - live
        if not waiting:
            self.team_anchor = None
            return
        self.team_anchor = {
            "source_id": int(source.char.get("char_id") or 0),
            "family": family,
            "waiting": waiting,
            "zone": int(zone),
            "pos": list(pos),
            "at": time.time(),
        }
        log.info("%s called the team; waiting for %d account(s) to finish logging in",
                 source.addr, len(waiting))

    def join_team_anchor(self, session) -> bool:
        """Pull a box that was still logging in to the team's last warp anchor."""
        anchor = self.team_anchor
        if not anchor:
            return False
        if time.time() - float(anchor["at"]) > TEAM_ANCHOR_TTL:
            self.team_anchor = None
            return False
        account = int(session.char.get("account_id") or 0)
        if account not in anchor["waiting"]:
            return False
        if int(session.char.get("char_id") or 0) == anchor["source_id"]:
            return False
        if session.already_at(anchor["zone"], anchor["pos"]):
            anchor["waiting"].discard(account)
            if not anchor["waiting"]:
                self.team_anchor = None
            return False
        log.info("%s joins the team anchor in %s", session.addr,
                 self.zones.name(anchor["zone"]))
        moved = session.change_zone(anchor["zone"], anchor["pos"])
        if moved:
            anchor["waiting"].discard(account)
            if not anchor["waiting"]:
                self.team_anchor = None
        return moved

    def queue_warps(self, source, targets, zone: int, pos, spacing: float = 0.0,
                    announce: str = "", skip_if_present: bool = False) -> None:
        """Queue family members to be zoned to ``source``.

        The whole team is handed out on the next tick by default: box clients overlap their
        zone loads, so a batch reaches the new zone faster than spacing the hand-offs, and
        the hand-off fixes in zone.py keep simultaneous reconnects from losing a box.  A
        positive ``spacing`` falls back to one move per interval.  ``skip_if_present``
        drops a move whose target already stands at the destination (a box that walked
        through a zone line itself), and ``announce`` overrides the warp chat line.
        """
        source_id = int(source.char.get("char_id") or 0)
        self.pending_warps = [move for move in self.pending_warps
                              if move["source_id"] != source_id]
        for target in targets:
            self.pending_warps.append({
                "source_id": source_id,
                "source_name": str(source.char.get("name") or "A party member"),
                "char_id": int(target.char.get("char_id") or 0),
                "zone": int(zone),
                "pos": list(pos),
                "spacing": float(spacing),
                "announce": str(announce or ""),
                "skip_if_present": bool(skip_if_present),
                "queued": time.time(),
            })

    def _run_pending_warps(self, now: float) -> None:
        if not self.pending_warps or now < self.next_warp_at:
            return

        def drop(move) -> None:
            # By identity: a skipped move earlier in the list must not shift the entry a
            # later pop removes.
            self.pending_warps = [item for item in self.pending_warps if item is not move]

        def take(move):
            """The target if this move can go out now; drops a dead or no-op move."""
            target = next((session for session in self.sessions.values()
                           if int(getattr(session, "char", {}).get("char_id", 0))
                           == move["char_id"]), None)
            if target is None or getattr(target, "gone", False):
                drop(move)
                return None
            if (not target.logged_in or target.zoning
                    or getattr(target, "sleeping", False)
                    or not getattr(target, "zone_loaded", False)):
                return None
            if move.get("skip_if_present") and target.already_at(move["zone"], move["pos"]):
                # The box walked through the line on its own; no second reload.
                drop(move)
                return None
            return target

        def send(move, target) -> None:
            target.say(move.get("announce") or "%s warps you to their side in %s." % (
                move["source_name"], self.zones.name(move["zone"])))
            target.change_zone(move["zone"], move["pos"], follow_family=False)
            drop(move)
            log.info("queued warp: %s char %#x", target.char.get("name", "?"),
                     move["char_id"])

        for move in list(self.pending_warps):
            target = take(move)
            if target is None:
                continue
            send(move, target)
            self.next_warp_at = now + move["spacing"]
            if move["spacing"] > 0.0:
                return
        # Nothing was ready (all targets still loading): try again on the next tick.
        if any(now - move["queued"] > 60.0 for move in self.pending_warps):
            self.pending_warps = [move for move in self.pending_warps
                                  if now - move["queued"] <= 60.0]

    def advance(self, now: float | None = None) -> None:
        """Run timers, AI and combat without sending; the caller decides when to flush."""
        now = time.time() if now is None else now
        self.last_tick = now
        self.reap_sessions(now)
        self._run_pending_warps(now)
        for session in list(self.sessions.values()):
            if (session.logged_in and not session.zoning
                    and not getattr(session, "sleeping", False)
                    and not getattr(session, "gone", False)):
                session.tick(now)
        for zone, entities in list(self.content.items()):
            sessions = self.sessions_in_zone(zone)
            if not sessions:
                continue
            for entity in list(entities):
                if entity.is_mob():
                    self._tick_mob(entity, sessions, now)
                elif entity.is_trust():
                    self._tick_trust(entity, sessions, now)
                elif entity.is_pet():
                    self._tick_pet(entity, sessions, now)
        # Party bars and zone columns follow the sessions; every half second is enough
        # for the client's roster and cheap enough to run on each exchange.
        self.sync_parties(now)
        # A logged-out session stays long enough for flush() to send its 0x00B, then goes.
        for addr, session in list(self.sessions.items()):
            if getattr(session, "gone", False) and not session.queue:
                self.sessions.pop(addr, None)
                self.release_player_targid(int(session.char.get("char_id", 0)))
                with self.lock:
                    for key, value in list(self.by_char.items()):
                        if value is session:
                            self.by_char.pop(key, None)

    def advance_for_packet(self) -> None:
        """The per-packet tick: at most TICK_INTERVAL, so six clients cannot run it 180x/s."""
        now = time.time()
        if now - self.last_tick >= TICK_INTERVAL:
            self.advance(now)

    def tick(self, now: float | None = None) -> None:
        self.advance(now)
        self.flush(now)

    def set_animation(self, entity: ZoneEntity, animation: int,
                      sessions: list | None = None) -> None:
        """Change an entity's animation and tell the clients that have already seen it.

        The 0x00E HP mask is the client's "general" update section, which is where the
        animation byte lives.  Animation 1 is the drawn-weapon attack stance; without it
        a mob never draws or swings, and without clearing it a dead or disengaged mob
        keeps standing in its fighting pose.
        """
        animation = int(animation)
        if int(entity.animation) == animation:
            return
        entity.animation = animation
        sessions = self.sessions_in_zone(entity.zone) if sessions is None else sessions
        for session in sessions:
            if entity.targid in getattr(session, "sent_targids", ()):
                session.queue_entity(entity, SEND_HP)

    def nav_grid(self, zone: int):
        """The walkable grid for a zone, or None when the client's data is unavailable."""
        cache = getattr(self, "nav", None)
        if cache is None:
            return None
        current = getattr(cache, "current", None)
        return current(int(zone)) if current is not None else cache.grid(int(zone))

    def _mob_sync(self, entity: ZoneEntity, sessions: list, now: float,
                  *, force: bool = False, watchers: list | None = None) -> None:
        """Stream a mob's position on the client's update cadence.

        The client keeps walking an entity from the ``moving`` flag and the speed byte
        until the next packet, so steady movement needs a correction, not a position
        every tick.  A walker is corrected four times a second; a runner (speed byte 36,
        six yalms a second) is corrected every 100 ms while chasing.  A turn and the
        moment the mob stops are sent at once, because those are the corrections the
        client cannot interpolate; a stop also reaches the wider spawn range, so a mob
        that halts at the edge of the streaming range does not freeze mid-stride.
        """
        urgent = bool(force or getattr(entity, "pending_turn", False))
        if urgent:
            entity.pending_turn = False
        if not urgent:
            interval = (MOB_SYNC_INTERVAL_RUN
                        if int(entity.speed) >= MOB_RUN_SPEED_BYTE
                        else MOB_SYNC_INTERVAL)
            if now - float(entity.last_sync_at or 0.0) < interval:
                return
        entity.last_sync_at = now
        targets = sessions if (watchers is None or urgent) else watchers
        # A stop goes to everyone who has the entity spawned (it must not freeze at the
        # edge of the streaming range); a turn goes to the same close watchers as a walk.
        limit = SYNC_RANGE if (urgent and not entity.moving) else MOB_SYNC_RANGE
        for session in targets:
            if int(entity.targid) not in getattr(session, "sent_targids", ()):
                continue
            distance = entity.distance_to(*session.pos[:3])
            if distance > limit:
                continue
            # Only the mobs in the player's own neighbourhood are worth an urgent
            # packet; a stop or a corner 40 yalms away can wait for the ambient budget.
            session.queue_entity(entity, SEND_POSITION,
                                 urgent=urgent and distance <= MOB_URGENT_RANGE)

    def _nav_pending(self, zone: int) -> bool:
        cache = getattr(self, "nav", None)
        pending = getattr(cache, "pending", None)
        return bool(pending(int(zone))) if pending is not None else False

    def _mob_los(self, entity: ZoneEntity, point, nav=None) -> bool:
        """Whether a walkable line connects the mob to a point."""
        nav = nav if nav is not None else self.nav_grid(entity.zone)
        if nav is None:
            return True
        return nav.line_clear(entity.x, entity.y, entity.z,
                              float(point[0]), float(point[1]), float(point[2]))

    def _mob_snap_floor(self, entity: ZoneEntity, nav) -> None:
        """Stand a monster on the surface under it, not on its spawn's old height."""
        if nav is None:
            return
        floor = nav.floor_near(entity.x, entity.z, entity.y, limit=MOB_VERTICAL_REACH)
        if floor is not None:
            entity.y = floor

    def _mob_clear_nav(self, entity: ZoneEntity) -> None:
        entity.nav_path.clear()
        entity.nav_goal = None
        entity.nav_planned_at = 0.0

    def _mob_speed(self, entity: ZoneEntity, sessions: list, speed: int,
                   now: float) -> None:
        """Change the client's interpolation speed and republish the position."""
        speed = int(max(0, min(255, speed)))
        if int(entity.speed) == speed:
            return
        entity.speed = speed
        # The next position packet carries the new byte; make it immediate.
        entity.last_sync_at = 0.0
        self._mob_sync(entity, sessions, now, force=True)

    def _mob_point_allowed(self, entity: ZoneEntity, x: float, y: float, z: float,
                           leash: float | None) -> bool:
        """Whether a point is still inside this mob's allowed ground.

        A roam leg stays on the spawn floor (``leash is None``) because a roamer that
        wanders down a ramp can end up on a ledge it cannot leave.  A chase passes
        ``MOB_CHASE_LEASH`` instead: a sphere around the spawn that lets the mob follow a
        player up or down a slope while still refusing to be dragged across the zone.
        """
        if leash is None:
            return abs(float(y) - float(entity.spawn_y)) <= MOB_VERTICAL_LEASH
        return math.dist(
            (float(x), float(y), float(z)),
            (float(entity.spawn_x), float(entity.spawn_y), float(entity.spawn_z)),
        ) <= float(leash)

    def _mob_follow(self, entity: ZoneEntity, nav, goal,
                    step: float, now: float,
                    *, max_nodes: int = MOB_NAV_NODES,
                    stop_distance: float = 0.0,
                    leash: float | None = None) -> tuple[bool, bool]:
        """Walk ``step`` yalms along a route to ``goal``.

        Returns ``(moved, arrived)``.  The route is planned from the mob's actual
        position, kept on the entity between ticks, replanned when the target moves, and
        validated again at every sample of every step so a packet cannot tunnel through
        a wall.  When no route exists the mob does not move at all; a chase falls back
        to :meth:`_mob_walk_direct` so a pulled monster still closes on the player.

        ``leash`` is ``None`` for a roam leg (stay on the spawn floor) or the chase
        sphere for a fight.  The nav grid's step and barrier tests still decide whether
        the ground itself is walkable.
        """
        if step <= 0.0 or nav is None:
            return False, False
        gx, gy, gz = float(goal[0]), float(goal[1]), float(goal[2])
        if now < float(entity.nav_blocked_until or 0.0):
            return False, False
        if stop_distance and math.hypot(gx - entity.x, gz - entity.z) <= stop_distance:
            return False, False
        self._mob_snap_floor(entity, nav)
        goal_moved = (entity.nav_goal is None
                      or math.hypot(gx - entity.nav_goal[0], gz - entity.nav_goal[2])
                      > MOB_NAV_GOAL_MOVE)
        stale = (now - float(entity.nav_planned_at or 0.0) >= MOB_NAV_REPLAN)
        if goal_moved or stale or not entity.nav_path:
            path = nav.find_path((entity.x, entity.y, entity.z), (gx, gy, gz),
                                 max_nodes=max_nodes)
            entity.nav_planned_at = now
            entity.nav_goal = (gx, gy, gz)
            if path is None:
                self._mob_clear_nav(entity)
                entity.nav_blocked_until = now + MOB_NAV_COOLDOWN
                return False, False
            if not path and not nav.line_clear(entity.x, entity.y, entity.z, gx, gy, gz):
                # Same cell, but a wall or a cliff is between the two points.
                self._mob_clear_nav(entity)
                entity.nav_blocked_until = now + MOB_NAV_COOLDOWN
                return False, False
            if any(not self._mob_point_allowed(entity, float(waypoint[0]),
                                               float(waypoint[1]), float(waypoint[2]),
                                               leash)
                   for waypoint in path):
                # The route leaves the ground this monster is allowed on: a ramp down a
                # ledge, a stair into another storey, or a chase that has run past its
                # leash.  Do not take it; the caller's direct-step fallback can still
                # close some of the gap.
                self._mob_clear_nav(entity)
                entity.nav_blocked_until = now + MOB_NAV_COOLDOWN
                return False, False
            entity.nav_path = list(path)

        start_x, start_z = entity.x, entity.z
        start_rot = int(entity.rot)
        remaining = float(step)
        while remaining > 1e-4 and entity.nav_path:
            wx, wy, wz = entity.nav_path[0]
            dx, dz = wx - entity.x, wz - entity.z
            distance = math.hypot(dx, dz)
            if distance <= 0.08:
                entity.nav_path.pop(0)
                if abs(float(wy) - entity.y) <= 1.0:
                    entity.y = float(wy)
                continue
            travel = min(remaining, distance)
            if stop_distance:
                # A chasing monster stops at its swing reach rather than walking into
                # the player's model.
                gap = math.hypot(gx - entity.x, gz - entity.z)
                travel = min(travel, max(0.0, gap - stop_distance))
                if travel <= 1e-6:
                    entity.nav_path.clear()
                    break
            nx = entity.x + dx / distance * travel
            nz = entity.z + dz / distance * travel
            floor = nav.step_floor(entity.x, entity.z, entity.y, nx, nz)
            if floor is None or not self._mob_point_allowed(entity, nx, floor, nz, leash):
                # Never slide the last good point into an invalid one: stop here and
                # let the next plan look for a way around.  The ground test keeps the
                # mob on its allowed floor even when a floor layer exists further up or
                # down but the player cannot reach it.
                entity.nav_path.clear()
                entity.nav_goal = None
                entity.nav_blocked_until = now + MOB_NAV_COOLDOWN
                entity.moving = False
                break
            entity.x, entity.z, entity.y = nx, nz, floor
            remaining -= travel
            if travel >= distance - 1e-6:
                entity.nav_path.pop(0)

        moved = abs(entity.x - start_x) > 1e-6 or abs(entity.z - start_z) > 1e-6
        if moved:
            entity.rot = heading_to_rot(entity.x - start_x, entity.z - start_z)
            entity.moving = True
            # A turn is where a client drawing a straight line between two packets
            # would cut through the corner.  Send the new heading immediately.
            turn = ((int(entity.rot) - start_rot + 128) & 0xFF) - 128
            # A nav grid turns in small steps; only a real corner (about 45 degrees
            # walking, 22 running) is worth an urgent correction.  A 17-degree kink is
            # inside the 0.5-yalm interpolation window and would just add traffic.
            corner = 16 if int(entity.speed) >= MOB_RUN_SPEED_BYTE else 32
            if abs(turn) >= corner and now - float(entity.last_sync_at or 0.0) >= 0.1:
                entity.last_sync_at = 0.0
                entity.pending_turn = True
        arrived = (not entity.nav_path
                   and math.hypot(gx - entity.x, gz - entity.z)
                   <= max(0.35, nav.cell * 0.35))
        return moved, arrived

    def _mob_walk_direct(self, entity: ZoneEntity, nav, goal,
                         step: float, now: float, *,
                         stop_distance: float = 0.0,
                         leash: float = MOB_CHASE_LEASH) -> tuple[bool, bool]:
        """Walk straight at ``goal`` when the nav grid cannot plan a route.

        A pulled monster has to visibly chase even when the player stands on a floor the
        grid does not connect to the camp (a hill above it, a cave lip below it).  The
        direct step uses the same per-sample floor and barrier test as a planned route,
        so it still stops at a wall, a cliff edge or the chase leash instead of clipping
        through the geometry.  It never replaces a real route: the caller only invokes it
        after :meth:`_mob_follow` failed to move.
        """
        if nav is None or step <= 0.0:
            return False, False
        gx, gz = float(goal[0]), float(goal[2])
        dx, dz = gx - entity.x, gz - entity.z
        distance = math.hypot(dx, dz)
        if distance <= 1e-6:
            return False, False
        travel = min(float(step), distance)
        if stop_distance:
            travel = min(travel, max(0.0, distance - float(stop_distance)))
        if travel <= 1e-6:
            return False, False
        start_x, start_z = entity.x, entity.z
        start_rot = int(entity.rot)
        moved = False
        # A full step may cross a threshold the sample misses; halve it until either a
        # legal piece is found or the mob is close enough that it would only jitter.
        while travel > 0.02:
            nx = entity.x + dx / distance * travel
            nz = entity.z + dz / distance * travel
            floor = nav.step_floor(entity.x, entity.z, entity.y, nx, nz)
            if floor is not None and self._mob_point_allowed(entity, nx, floor, nz, leash):
                entity.x, entity.z, entity.y = nx, nz, floor
                moved = True
                break
            travel *= 0.5
        if not moved:
            return False, False
        entity.rot = heading_to_rot(entity.x - start_x, entity.z - start_z)
        entity.moving = True
        turn = ((int(entity.rot) - start_rot + 128) & 0xFF) - 128
        corner = 16 if int(entity.speed) >= MOB_RUN_SPEED_BYTE else 32
        if abs(turn) >= corner and now - float(entity.last_sync_at or 0.0) >= 0.1:
            entity.last_sync_at = 0.0
            entity.pending_turn = True
        arrived = math.hypot(gx - entity.x, gz - entity.z) <= max(
            0.35, nav.cell * 0.35)
        return True, arrived

    def _tick_mob(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        if not entity.alive:
            if entity.corpse_until and now >= entity.corpse_until:
                from . import packets
                from .zone import sub
                entity.corpse_until = 0.0
                entity.animation = 0
                body = packets.entity_despawn(entity)
                for session in sessions:
                    session.queue.append(sub(0x00E, body))
            if entity.respawn_at and now >= entity.respawn_at:
                entity.reset_mob(now, self.rng)
                for session in sessions:
                    session.queue_entity(entity, SEND_SPAWN)
                log.info("%s respawned in zone %d", entity.name, entity.zone)
            return

        self.tick_mob_effects(entity, sessions, now)
        if not entity.alive:
            return
        if self._nav_pending(entity.zone):
            # The zone's collision grid is being built.  Standing still for a moment is
            # better than walking through a wall and then snapping back when it arrives.
            return

        # Petrification (Break/Breakga) freezes the monster where it stands: no walking,
        # no swings and no facing changes until the 30 seconds run out.  It is not the
        # same as Sleep -- damage does not wake it (see wake_mob).
        if effects.PETRIFICATION in entity.effect_state:
            entity.next_attack_at = now + 1.0
            if entity.moving:
                entity.moving = False
                for session in sessions:
                    session.queue_entity(entity, SEND_POSITION)
            return

        self.decay_mob_enmity(entity, now)
        # VE is the half that moves a monster between players: once it drains, a player
        # with more cumulative hate can overtake the current target.
        if entity.engaged_char_id and len(entity.enmity) > 1:
            top = self.mob_hate_target(entity)
            if top is not None and int(top.char["char_id"]) != int(entity.engaged_char_id):
                entity.engaged_char_id = int(top.char["char_id"])
                entity.claim_char_id = int(top.char["char_id"])
                entity.pending_skill = None
                entity.next_attack_at = now + 1.0
                self._mob_clear_nav(entity)
                entity.nav_blocked_until = 0.0

        target = self.session_by_char(entity.engaged_char_id) if entity.engaged_char_id else None
        if entity.engaged_char_id and (target is None or target.zone != entity.zone
                                       or target.dead_until or int(target.char.get("hp_current", 0)) <= 0
                                       or entity.distance_to(*target.pos[:3]) > DISENGAGE_DISTANCE):
            entity.engaged_char_id = None
            entity.aggro_announced = False
            # A spell pull leaves hate behind: if the current target dies, zones out or
            # runs, hand the monster to the next-highest player instead of resetting it.
            target = self.mob_hate_target(entity)
            if target is None:
                entity.claim_char_id = None
                entity.pending_skill = None
                if entity.nav_path or entity.moving:
                    self._mob_clear_nav(entity)
                    entity.moving = False
                    self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
                    self._mob_sync(entity, sessions, now, force=True)
                self.set_animation(entity, 0, sessions)
            else:
                entity.engaged_char_id = int(target.char["char_id"])
                entity.claim_char_id = int(target.char["char_id"])
                entity.next_attack_at = now + 1.0
                self._mob_clear_nav(entity)
                entity.nav_blocked_until = 0.0
                self.set_animation(entity, 1, sessions)

        if target is not None:
            # Sleep and Stun stop the mob where it stands.  Damage wakes it (wake_mob).
            if effects.SLEEP in entity.effect_state or effects.STUN in entity.effect_state:
                entity.next_attack_at = now + 1.0
                return
            # A readied TP move fires on its own timer; while it is preparing the mob
            # does not also auto-attack.
            pending = entity.pending_skill
            if pending is not None:
                if now >= float(pending.get("at", 0.0)):
                    self._mob_fire_skill(entity, target, sessions, now)
                return
            # The mob is fighting: draw its weapon and put it in the attack stance.
            self.set_animation(entity, 1, sessions)
            # TP moves can reach farther than a swing, so this check happens before the
            # chase/melee-range branch.  A skill whose distance is too short is filtered
            # out and the mob keeps closing.
            if now >= entity.next_attack_at and self._mob_try_skill(
                    entity, target, sessions, now):
                return
            reach = entity.distance_to(*target.pos[:3])
            nav = self.nav_grid(entity.zone)
            # A target on the far side of a wall is not in melee range even when the
            # distance is short.  Walk around the wall instead of swinging through it.
            too_far_vertically = abs(float(target.pos[1]) - entity.y) > MOB_MELEE_VERTICAL
            blocked = too_far_vertically or (nav is not None
                                            and not self._mob_los(entity, target.pos[:3], nav))
            if reach > MOB_REACH or blocked:
                if effects.BIND in entity.effect_state:
                    entity.next_attack_at = now + 1.0
                    return
                # Walk into range before swinging: a mob used to hit from across the zone.
                step = MOB_CHASE_SPEED * max(0.0, min(0.5, now - entity.last_move_at))
                weight = entity.effect_state.get(effects.WEIGHT)
                if weight is not None:
                    step *= max(0.1, 1.0 - int(weight.get("potency", 0)) / 100.0)
                entity.last_move_at = now
                was_moving = entity.moving
                moved = False
                self._mob_speed(entity, sessions, MOB_RUN_SPEED_BYTE, now)
                if nav is not None:
                    moved, _arrived = self._mob_follow(
                        entity, nav, target.pos[:3], step, now,
                        stop_distance=MOB_REACH * 0.8, leash=MOB_CHASE_LEASH)
                    if not moved:
                        # The grid found no route (a slope it cannot connect, a floor
                        # seam, a search budget) but the monster still has hate.  Walk
                        # at the player along the direct line as far as the floor and
                        # barrier tests allow; standing at the pull spot was the bug.
                        self._mob_clear_nav(entity)
                        moved, _arrived = self._mob_walk_direct(
                            entity, nav, target.pos[:3], step, now,
                            stop_distance=MOB_REACH * 0.8, leash=MOB_CHASE_LEASH)
                elif step > 0:
                    # No collision mesh.  Keep the old straight chase, but never let a
                    # monster walk up or down a cliff to a target on another level: that
                    # is the one game rule we can enforce without the geometry.
                    if abs(float(target.pos[1]) - entity.y) <= MOB_VERTICAL_REACH:
                        dx = target.pos[0] - entity.x
                        dz = target.pos[2] - entity.z
                        span = math.hypot(dx, dz) or 1.0
                        if span > 0.01:
                            travel = min(step, span - MOB_REACH * 0.8)
                            if travel > 0:
                                entity.x += dx / span * travel
                                entity.z += dz / span * travel
                                entity.moving = True
                                entity.rot = heading_to_rot(dx, dz)
                                moved = True
                if moved:
                    self._mob_sync(entity, sessions, now)
                else:
                    self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
                    if was_moving or entity.moving:
                        entity.moving = False
                        self._mob_sync(entity, sessions, now, force=True)
                return
            self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
            if entity.moving:
                entity.moving = False
                self._mob_sync(entity, sessions, now, force=True)
            if now >= entity.next_attack_at:
                paralysis = entity.effect_state.get(effects.PARALYSIS)
                if (paralysis is not None
                        and self.rng.random() * 100.0 < int(paralysis.get("potency", 0))):
                    for session in sessions:
                        session.queue_action(int(entity.id), effects.PARALYSIS,
                                             actor_id=int(entity.id), message=203,
                                             kind=0, category=4, info=0)
                    entity.next_attack_at = now + 1.0
                    return
                blink = target.effect_state.get(effects.BLINK)
                if blink is not None and int(blink.get("power", 0)) > 0 \
                        and self.rng.random() < 0.5:
                    blink["power"] = int(blink["power"]) - 1
                    if int(blink["power"]) <= 0:
                        target.remove_effect(effects.BLINK, quiet=True)
                    target.queue.append(target.char_status())
                    target.queue_action(int(target.char["char_id"]), 0, miss=True,
                                        actor_id=int(entity.id), message=15,
                                        kind=0, category=4, info=0)
                    entity.next_attack_at = now + max(1.0, entity.attack_delay_ms / 1000.0)
                    return
                miss, damage, critical = self.mob_attack(entity, target)
                absorbed = False
                if not miss and target.has_effect(effects.COPY_IMAGE) \
                        and target.effect_power(effects.COPY_IMAGE) > 0:
                    target.drop_shadow()
                    absorbed = True
                    target.queue_action(int(target.char["char_id"]), 1,
                                        actor_id=int(entity.id),
                                        message=31, kind=0, category=4, info=0)
                    target.queue.append(target.char_status())
                if not miss and not absorbed:
                    target.take_damage(damage, entity)
                defeated = int(target.char.get("hp_current", 0)) <= 0
                if not absorbed:
                    target.queue_action(int(target.char["char_id"]), damage, miss=miss,
                                        critical=critical, defeated=defeated,
                                        actor_id=int(entity.id))
                delay = max(1.0, entity.attack_delay_ms / 1000.0)
                slow = entity.effect_state.get(effects.SLOW)
                if slow is not None:
                    delay *= 1.0 + int(slow.get("potency", 0)) / 100.0
                entity.next_attack_at = now + delay
            return

        # Aggro a nearby player.
        if entity.aggro:
            nav = self.nav_grid(entity.zone)
            for session in sessions:
                if session.dead_until or int(session.char.get("hp_current", 0)) <= 0:
                    continue
                # Sneak and Invisible keep a mob from noticing you at all.
                if session.has_effect(effects.SNEAK) or session.has_effect(effects.INVISIBLE):
                    continue
                if int(session.char.get("main_level", 1)) - entity.level > AGGRO_LEVEL_SPREAD:
                    continue
                if entity.distance_to(*session.pos[:3]) > AGGRO_DISTANCE:
                    continue
                # A player on a ledge, a bridge deck or the other side of a wall is not
                # in the monster's aggro cone.  Without the vertical test a goblin at the
                # foot of a cliff noticed -- and then chased -- everyone standing on top.
                if abs(float(session.pos[1]) - entity.y) > MOB_VERTICAL_REACH:
                    continue
                if nav is not None and not self._mob_los(entity, session.pos[:3], nav):
                    continue
                entity.engaged_char_id = int(session.char["char_id"])
                entity.claim_char_id = int(session.char["char_id"])
                entity.next_attack_at = now + 1.5
                self._mob_clear_nav(entity)
                self.set_animation(entity, 1, sessions)
                if not entity.aggro_announced:
                    session.say("%s notices you." % entity.name)
                    entity.aggro_announced = True
                return

        # Roam: walk a few yalms, stand still for a few seconds, then pick a new heading.
        # A mob that picks a fresh random direction the instant it arrives jitters in place.
        if entity.roam_radius <= 0:
            return
        if abs(float(entity.y) - float(entity.spawn_y)) > MOB_VERTICAL_LEASH:
            # A roaming monster that somehow took a ramp into another storey is put back
            # at its spawn.  This is the safety net for geometry the nav grid models as a
            # walkable connection but the client draws as a cliff.
            entity.x, entity.y, entity.z = entity.spawn_x, entity.spawn_y, entity.spawn_z
            self._mob_clear_nav(entity)
            entity.moving = False
            entity.roam_target = None
            entity.roam_pause_until = now + self.rng.uniform(2.0, 5.0)
            self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
            self._mob_sync(entity, sessions, now, force=True)
            return
        watchers = [s for s in sessions
                    if entity.distance_to(*s.pos[:3]) <= MOB_SYNC_RANGE]
        if not watchers:
            # Nobody is close enough to drive this leg, but clients that already have the
            # entity would keep extrapolating its last heading forever.  A final stop
            # packet prevents a distant mob from walking through a wall on the client.
            if entity.moving or entity.nav_path:
                self._mob_clear_nav(entity)
                entity.moving = False
                self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
                self._mob_sync(entity, sessions, now, force=True)
            entity.last_move_at = now
            return
        nav = self.nav_grid(entity.zone)

        if entity.roam_target is None:
            if now < entity.roam_pause_until:
                return
            radius = min(float(entity.roam_radius), MOB_ROAM_RADIUS_CAP)
            distance = self.rng.uniform(min(1.5, radius), max(2.0, radius))
            target_x = entity.x
            target_z = entity.z
            chosen = False
            # Turn gently: a fresh heading within ~60 degrees of the last one.  Reversing on
            # the spot each leg is what made the walk look like it was swaying.
            first_angle = entity.roam_heading + self.rng.uniform(-1.0, 1.0)
            for attempt in range(6):
                angle = first_angle if attempt == 0 else self.rng.uniform(0.0, 6.283185)
                try_x = entity.x + distance * math.cos(angle)
                try_z = entity.z + distance * math.sin(angle)
                # Keep the destination inside the spawn area; a clamp to the boundary
                # turns a long walk into a shuffle, so try another heading first.
                if math.hypot(try_x - entity.spawn_x,
                              try_z - entity.spawn_z) > radius:
                    continue
                if nav is not None:
                    floor = nav.floor_near(try_x, try_z, entity.y, limit=MOB_VERTICAL_REACH)
                    if floor is None:
                        continue
                    path = nav.find_path((entity.x, entity.y, entity.z),
                                         (try_x, floor, try_z),
                                         max_nodes=MOB_NAV_ROAM_NODES)
                    if path is None:
                        continue
                    if not path and not nav.line_clear(entity.x, entity.y, entity.z,
                                                       try_x, floor, try_z):
                        continue
                    entity.nav_path = list(path)
                    entity.nav_goal = (try_x, floor, try_z)
                    entity.nav_planned_at = now
                target_x, target_z = try_x, try_z
                chosen = True
                break
            if not chosen and nav is not None:
                # Every direction the geometry allows this leg is blocked; stand a
                # moment and try again rather than walking into the wall.
                entity.roam_pause_until = now + self.rng.uniform(1.0, 3.0)
                return
            entity.roam_target = (target_x, target_z)
            entity.roam_heading = math.atan2(target_x - entity.x, target_z - entity.z)
            self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
            entity.moving = True
            entity.rot = heading_to_rot(target_x - entity.x, target_z - entity.z)
            entity.last_move_at = now
            # Queue the moving flag now.  It stays ambient (a start is not a corner), so
            # it is distance-prioritised like the rest of the walk instead of spending
            # an urgent packet for every leg of every mob in the zone.
            entity.last_sync_at = 0.0
            self._mob_sync(entity, sessions, now)
            return

        target_x, target_z = entity.roam_target
        # Cap the step: a mob that has not been ticked for a while (nobody in the zone)
        # must not leap across its spawn area in a single update.
        step = MOB_WALK_SPEED * max(0.0, min(0.5, now - entity.last_move_at))
        entity.last_move_at = now
        if step <= 0.0:
            return
        if nav is not None:
            floor = None
            if (entity.nav_goal is not None
                    and math.hypot(entity.nav_goal[0] - target_x,
                                   entity.nav_goal[2] - target_z) < 0.25):
                floor = float(entity.nav_goal[1])
            if floor is None:
                floor = nav.floor_near(target_x, target_z, entity.y, limit=MOB_VERTICAL_REACH * 2.5)
            if floor is None:
                entity.roam_target = None
                self._mob_clear_nav(entity)
                entity.moving = False
                entity.roam_pause_until = now + self.rng.uniform(1.0, 3.0)
                self._mob_sync(entity, sessions, now, force=True)
                return
            moved, arrived = self._mob_follow(entity, nav, (target_x, floor, target_z),
                                              step, now)
            if arrived:
                entity.x, entity.z, entity.y = target_x, target_z, floor
                entity.roam_target = None
                self._mob_clear_nav(entity)
                entity.moving = False
                entity.roam_pause_until = now + self.rng.uniform(3.0, 8.0)
                self._mob_sync(entity, sessions, now, force=True)
                return
            if not moved:
                if now < float(entity.nav_blocked_until or 0.0):
                    # The route is on cooldown; keep the leg and try again shortly.
                    if entity.moving:
                        entity.moving = False
                        self._mob_sync(entity, sessions, now, force=True)
                    return
                entity.roam_target = None
                self._mob_clear_nav(entity)
                entity.moving = False
                entity.roam_pause_until = now + self.rng.uniform(1.0, 3.0)
                self._mob_sync(entity, sessions, now, force=True)
                return
            self._mob_sync(entity, sessions, now)
            return

        self._mob_speed(entity, sessions, MOB_WALK_SPEED_BYTE, now)
        dx, dz = target_x - entity.x, target_z - entity.z
        remaining = math.hypot(dx, dz)
        arrived = remaining <= max(0.3, step)
        if arrived:
            entity.x, entity.z = target_x, target_z
            entity.roam_target = None
            entity.moving = False
            entity.roam_pause_until = now + self.rng.uniform(3.0, 8.0)
        elif remaining > 1e-6:
            entity.x += dx / remaining * step
            entity.z += dz / remaining * step
            entity.moving = True
            # Keep the facing in step with the leg we are walking, on every update: a stale
            # rotation byte next to a moving position makes the client swing the model.
            entity.rot = heading_to_rot(dx, dz)
        # Always send the resting position, so the client does not leave the mob stranded
        # between two waypoints while it stands still.
        self._mob_sync(entity, sessions, now, force=arrived)

    def monster_sheet(self, entity: ZoneEntity):
        """A monster's combat stats, cached per level: they depend on nothing else.

        Locus camps whose Japanese tables publish Defense/Evasion per level carry a
        ``level_stats`` override on the entity; that row replaces the level-derived
        ``build_monster`` values so a level-135 Camelopard is the retail 1346/1224
        rather than the 99-capped curve's 740/732.  The base sheet stays cached per
        level and the override is applied to a copy.
        """
        sheet = self._monster_sheets.get(int(entity.level))
        if sheet is None:
            sheet = stats.build_monster(int(entity.level))
            self._monster_sheets[int(entity.level)] = sheet
        if entity.defense_override or entity.evasion_override:
            fighter = replace(
                sheet.fighter,
                defense=entity.defense_override or sheet.fighter.defense,
                evasion=entity.evasion_override or sheet.fighter.evasion)
            sheet = replace(sheet, fighter=fighter)
        return sheet

    def mob_skill_list(self, skill_list_id: int) -> tuple["mobskills.MobSkill", ...]:
        """A family's TP moves, loaded once from ``mob_skills`` / ``mob_skill_lists``."""
        skill_list_id = int(skill_list_id or 0)
        if skill_list_id <= 0:
            return ()
        cached = self._mob_skill_lists.get(skill_list_id)
        if cached is not None:
            return cached
        try:
            rows = self.service.mob_skills(skill_list_id)
        except Exception as exc:  # an un-migrated database has no skill tables
            log.warning("mob skill list %d unavailable: %s", skill_list_id, exc)
            rows = []
        skills = tuple(mobskills.from_row(row) for row in rows)
        self._mob_skill_lists[skill_list_id] = skills
        return skills

    def _mob_gain_tp(self, entity: ZoneEntity, amount: int) -> None:
        if not entity.is_mob() or not entity.alive:
            return
        entity.tp = max(0, min(mobskills.TP_MAX, int(entity.tp) + max(0, int(amount))))

    def _mob_gain_tp_from_player_hit(self, entity: ZoneEntity, session, damage: int,
                                     sheet, off_hand: bool = False,
                                     ranged: bool = False) -> None:
        """TP a monster gets when a player's physical hit lands.

        LandSandBoat's ``calculateTPGainOnPhysicalDamage``: the player's TP curve for
        this hand, +30 because the target is a monster, then dAGI (50% floor), Subtle
        Blow (75% cap) and the monster's own Store TP.  Magic TP gain is not wired into
        the spell path yet, so a pure nuker still feeds the bar more slowly than retail.
        """
        if int(damage) <= 0 or not entity.alive:
            return
        base = int(sheet.tp_per_hit(off_hand, ranged=ranged)) + 30
        attacker_agi = int(sheet.attributes.get("agi", 0))
        target_agi = int(self.monster_sheet(entity).attributes.get("agi", 0))
        dagi = max(-100, min(100, attacker_agi - target_agi))
        dagi_multiplier = max(0.5, min(1.0, (200 - (dagi + 30)) / 200.0))
        fighter = sheet.fighter
        subtle = (int(fighter.mods.get(mod.SUBTLE_BLOW, 0))
                  + int(fighter.mods.get(mod.SUBTLE_BLOW_II, 0)))
        subtle_multiplier = 1.0 - min(max(0, subtle) / 100.0, 0.75)
        gain = int(base * dagi_multiplier * subtle_multiplier)
        self._mob_gain_tp(entity, gain)

    def mob_self_mods(self, entity: ZoneEntity) -> dict[int, int]:
        """Modifier deltas from the monster's own buffs.

        Only buffs store ``mods`` in ``effect_state``; a player's enfeeble uses
        ``potency`` (a percentage) and is read by :meth:`debuffed_monster` and
        :meth:`mob_attack` instead.  Berserk is the first row that needs this: its
        +45% Attack / -25% Defense has to reach both the monster's own swing and the
        player's damage against it.
        """
        out: dict[int, int] = {}
        for state in entity.effect_state.values():
            for mod_id, value in (state.get("mods") or {}).items():
                out[int(mod_id)] = out.get(int(mod_id), 0) + int(value)
        return out

    def _apply_mob_self_mods(self, fighter: combat.Fighter,
                             entity: ZoneEntity) -> combat.Fighter:
        """Apply the monster's own buff modifiers to a copy of its fighter."""
        mods = self.mob_self_mods(entity)
        if not mods:
            return fighter

        def scaled(value: int, flat_id: int, percent_id: int) -> int:
            value = max(1, int(value) + int(mods.get(flat_id, 0)))
            percent = int(mods.get(percent_id, 0))
            if percent:
                value = max(1, int(value * (100 + percent) / 100.0))
            return value

        return replace(
            fighter,
            attack=scaled(fighter.attack, mod.ATT, mod.ATT_PERCENT),
            defense=scaled(fighter.defense, mod.DEF, mod.DEF_PERCENT),
            accuracy=max(1, int(fighter.accuracy) + int(mods.get(mod.ACC, 0))),
            evasion=max(1, int(fighter.evasion) + int(mods.get(mod.EVA, 0))),
        )

    def debuffed_monster(self, entity: ZoneEntity) -> combat.Fighter:
        """The cached monster fighter with the player's debuffs applied.

        The sheet itself is cached per level and must stay clean, so every debuff is a
        ``replace`` on a copy.  Evasion, Defense and Accuracy Down are percentages;
        Dia lowers Defense the same way (it and Defense Down are separate effects in
        retail, so they stack multiplicatively).  Critical Hit Evasion Down is stored
        as a negative ``CRITICAL_HIT_EVASION`` modifier, which is the same field the
        player's own crit rate already reads.
        """
        fighter = self.monster_sheet(entity).fighter
        evasion = int(fighter.evasion)
        defense = int(fighter.defense)

        state = entity.effect_state.get(effects.EVASION_DOWN)
        if state is not None:
            # Distract I/II/III are flat -35/-50/-130 Evasion (BG-wiki's formula caps
            # at -130), as are the weapon-skill Evasion Down rows.  This is not the
            # percent scale Defense Down and Attack Down use.
            flat = max(0, min(999, int(state.get("potency", 0))))
            evasion = max(1, evasion - flat)
        torpor = entity.effect_state.get(geomancy.GEO_EVASION_DOWN)
        if torpor is not None:
            cut = max(0, min(90, int(torpor.get("potency", 0))))
            evasion = max(1, int(evasion * (100 - cut) / 100.0))
        # Dia, Defense Down and GEO Frailty are separate effects in retail, so each one
        # takes its own bite out of the same Defense.
        for effect_id in (effects.DIA, effects.DEFENSE_DOWN, geomancy.GEO_DEFENSE_DOWN):
            state = entity.effect_state.get(effect_id)
            if state is None:
                continue
            cut = max(0, min(90, int(state.get("potency", 0))))
            defense = max(1, int(defense * (100 - cut) / 100.0))

        mods = dict(fighter.mods)
        crit_down = entity.effect_state.get(effects.CRIT_HIT_EVASION_DOWN)
        if crit_down is not None:
            percent = max(0.0, float(crit_down.get("potency", 0) or 0))
            mods[mod.CRITICAL_HIT_EVASION] = (
                int(mods.get(mod.CRITICAL_HIT_EVASION, 0)) - int(percent * 100))

        # Dancer step Daze.  These are not the generic Evasion Down/Defense Down line:
        # Quickstep subtracts flat evasion, Box Step cuts Defense by a percentage,
        # Stutter Step subtracts flat Magic Evasion (used by monster_debuff_mods) and
        # Feather Step lowers Critical Hit Evasion.  Level 6-10 share the level-5 icon
        # but keep their real level in ``power``.
        for spec in dancer.STEPS.values():
            level, _status = dancer.active_daze(entity.effect_state, spec)
            if level <= 0:
                continue
            value = dancer.daze_value(spec, level)
            if spec.stat == "evasion":
                evasion = max(1, evasion - value)
            elif spec.stat == "defense":
                defense = max(1, int(defense * (100 - min(90, value)) / 100.0))
            elif spec.stat == "crit_evasion":
                mods[mod.CRITICAL_HIT_EVASION] = (
                    int(mods.get(mod.CRITICAL_HIT_EVASION, 0)) - value * 100)

        result = replace(fighter, evasion=max(1, evasion), defense=max(1, defense),
                         mods=mods)
        # Self buffs (Berserk) apply last: they are the monster's own state, and the
        # player's Dia/Defense Down rows above already had their bite of the base value.
        return self._apply_mob_self_mods(result, entity)

    def monster_debuff_mods(self, entity: ZoneEntity) -> dict[int, int]:
        """The monster's magic-side debuffs as modifier deltas.

        ``combat._magic_finish`` accepts a negative ``MDEF`` (Magic Defense Down raises
        magic damage) and ``combat.magic_resist`` adds ``MEVA`` straight into the
        evasion term, so Magic Evasion Down lowers it.  INT Down is a flat stat, which
        the spell path subtracts from the target's INT itself.
        """
        mods = dict(self.monster_sheet(entity).fighter.mods)
        for effect_id in (effects.MAGIC_DEF_DOWN, geomancy.GEO_MAGIC_DEF_DOWN):
            defense_down = entity.effect_state.get(effect_id)
            if defense_down is not None:
                amount = int(defense_down.get("power") or defense_down.get("potency") or 0)
                mods[mod.MDEF] = int(mods.get(mod.MDEF, 0)) - amount
        for effect_id in (effects.MAGIC_EVASION_DOWN, geomancy.GEO_MAGIC_EVASION_DOWN):
            evasion_down = entity.effect_state.get(effect_id)
            if evasion_down is not None:
                amount = int(evasion_down.get("power") or evasion_down.get("potency") or 0)
                mods[mod.MEVA] = int(mods.get(mod.MEVA, 0)) - amount
        # Stutter Step's Weakened Daze is -3 Magic Evasion per level.
        stutter = dancer.STEPS[203]
        level, _status = dancer.active_daze(entity.effect_state, stutter)
        if level > 0:
            mods[mod.MEVA] = int(mods.get(mod.MEVA, 0)) - dancer.daze_value(stutter, level)
        return mods

    def player_attack(self, session, entity: ZoneEntity, *, ftp: float = 1.0,
                      attack_multiplier: float = 1.0, off_hand: bool = False,
                      accuracy_bonus: int = 0, crit_bonus: float = 0.0,
                      wsc: int = 0, ignored_defense: float = 0.0,
                      allow_critical: bool = True, ranged: bool = False):
        """One player swing at a monster: (missed, damage, critical).

        ``off_hand`` picks the sheet's second Fighter (the dual-wielded sub weapon).
        It has its own damage rating, skill and Accuracy, and retail caps its hit rate
        at 95% instead of 99%.  ``ranged`` picks the ranged Fighter (ranged weapon +
        ammo) instead of the main hand; an archery/marksmanship weapon skill must not
        swing the sword the player happens to hold.  ``accuracy_bonus`` and
        ``crit_bonus`` are the weapon skill's own gear/trait terms ("Weapon skill
        accuracy" and Fencer).  ``wsc`` and ``ignored_defense`` are the weapon skill's
        secondary-attribute bonus and the fraction of the target's Defense it ignores.
        ``allow_critical`` is False for weapon skills that cannot crit (only "critical
        hit rate varies with TP" skills can).
        """
        target = self.debuffed_monster(entity)
        sheet = session.stat_sheet()
        if ranged:
            attacker = sheet.ranged_fighter
        else:
            attacker = sheet.sub_fighter if off_hand else sheet.fighter
        if attacker is None:
            # Only callers that saw a dual-wield/ranged sheet ask for that fighter; a
            # missing one would otherwise silently swing the main hand instead.
            return True, 0, False
        if accuracy_bonus:
            attacker = replace(attacker, accuracy=int(attacker.accuracy) + int(accuracy_bonus))
        mighty = session.has_effect(effects.MIGHTY_STRIKES)
        assassin = bool(getattr(session, "_assassin_charge", False))
        forced_crit = mighty or assassin
        formless = (not off_hand
                    and float(getattr(session, "_formless_until", 0.0)) > time.time())
        if formless:
            ignored_defense = 1.0
            session._formless_until = 0.0
        # Souleater converts 10% of current HP into flat damage on each landed hit.
        # Retail gives a Dark Knight main the full amount and a support-job Dark Knight
        # half; the HP is still spent at 10% (less Stalwart Soul).  It is added after
        # pDIF/fTP, which is why it goes through ``flat_damage`` rather than the base.
        souleater_hp = 0
        souleater_bonus = 0
        if session.has_effect(effects.SOULEATER):
            souleater_hp = max(0, int(session.char.get("hp_current", 0)))
            souleater_bonus = int(souleater_hp * 0.10)
            if int(session.char.get("main_job", 0)) != 8:   # 8 = Dark Knight
                souleater_bonus //= 2
        hit = combat.melee(
            attacker, target, zone=int(entity.zone), rng=self.rng, ftp=ftp,
            attack_multiplier=attack_multiplier,
            crit_bonus=max(float(crit_bonus), 1.0) if forced_crit else crit_bonus,
            wsc=wsc, ignored_defense=ignored_defense,
            allow_critical=allow_critical or forced_crit,
            flat_damage=souleater_bonus, ranged=ranged)
        if souleater_bonus and not hit.missed:
            stalwart = max(0, min(100, int(attacker.mods.get(mod.STALWART_SOUL, 0))))
            cost = int(souleater_hp * 0.10) * (100 - stalwart) // 100
            # Keep at least 1 HP: the session has no self-damage death path here, and a
            # 0-HP character that is still standing would be a worse bug than retail's
            # ability to kill the user.
            session.char["hp_current"] = max(1, souleater_hp - cost)
            session.queue.append(session.char_status())
        if assassin:
            session._assassin_charge = False
        if (not hit.missed and float(getattr(session, "_feint_until", 0.0)) > time.time()):
            self.apply_mob_effect(
                entity, effects.SpellEffect(effects.EVASION_DOWN, "debuff", 60.0,
                                            potency=20),
                session, time.time(), duration=60.0)
            session._feint_until = 0.0
        if not hit.missed and hit.damage > 0:
            # The monster's TP bar is fed by the hit, not by the damage number: the
            # player's Subtle Blow and the AGI difference decide how much of it lands.
            self._mob_gain_tp_from_player_hit(
                entity, session, hit.damage, sheet, off_hand=off_hand,
                ranged=ranged)
            # Killer Instinct stores its damage bonus in the effect's power
            # (1500 = +15%).  It is applied to every hit of a weapon skill because
            # the weapon-skill round calls this method once per swing.
            power = session.effect_power(effects.KILLER_INSTINCT)
            if power > 0:
                hit = replace(hit, damage=hit.damage * (10000 + power) // 10000)
            # Dark Knight Consume Mana: the MP spent is added to the next hit.
            mana_bonus = int(getattr(session, "_consume_mana_bonus", 0) or 0)
            if mana_bonus > 0 and not off_hand:
                hit = replace(hit, damage=hit.damage + mana_bonus)
                session._consume_mana_bonus = 0
            # Monk Boost: the next main-hand hit deals 25% more damage.
            boost = float(getattr(session, "_boost_until", 0.0)) > time.time()
            if boost and not off_hand:
                hit = replace(hit, damage=hit.damage * 125 // 100)
                session._boost_until = 0.0
            # Restraint: one whole percentage of WS damage per landed main-hand round.
            if not off_hand and session.has_effect(effects.RESTRAINT):
                delay = max(1, int(sheet.delay))
                gain = max(1, delay // 385)
                session._restraint_bonus = min(
                    30, int(getattr(session, "_restraint_bonus", 0)) + gain)
        # The per-hit bonuses above (Killer Instinct, Consume Mana, Boost) are applied
        # after the engine's own roll, so the 99,999 ceiling is enforced again here.
        return hit.missed, combat.cap_damage(hit.damage), hit.critical

    def mob_attack(self, entity: ZoneEntity, session):
        """One monster swing at a player: (missed, damage, critical).

        The player's damage-taken gear is applied inside the engine, so the number that
        comes back is what the client should print -- PDT and DT already taken off.
        Blind, Accuracy Down and Attack Down are applied to the monster's fighter copy
        here; the monster sheet itself is cached per level and must stay clean.
        """
        # Invincible and Perfect Dodge negate physical damage outright.
        if session.has_effect(effects.INVINCIBLE) or session.has_effect(effects.PERFECT_DODGE):
            return True, 0, False
        # Third Eye anticipates the swing outright: the charge is spent and the
        # monster's attack is negated, before any damage roll.
        eye = getattr(session, "third_eye", None)
        if eye is not None:
            if time.time() > float(eye.get("until", 0.0)) or int(eye.get("charges", 0)) <= 0:
                session.third_eye = None
            else:
                eye["charges"] = int(eye["charges"]) - 1
                if int(eye["charges"]) <= 0:
                    session.third_eye = None
                session.say("You anticipate the attack.")
                # Seigan turns an anticipation into a 25% counter-attack.
                if session.has_effect(effects.SEIGAN) and self.rng.random() < 0.25:
                    miss, damage, critical = self.player_attack(session, entity)
                    if not miss and damage > 0:
                        defeated = entity.hp - damage <= 0
                        entity.hp = max(0, entity.hp - damage)
                        session.queue_action(int(entity.id), damage=damage,
                                             critical=critical, defeated=defeated,
                                             actor_id=int(session.char["char_id"]))
                        self.add_damage_hate(entity, int(session.char["char_id"]),
                                             damage, time.time())
                        session.say("You counter %s for %d points of damage."
                                    % (entity.name, damage))
                        if defeated:
                            self.kill_mob(session, entity, time.time())
                return True, 0, False
        attacker = self.monster_sheet(entity).fighter
        blind = entity.effect_state.get(effects.BLINDNESS)
        if blind is not None:
            attacker = replace(attacker, accuracy=max(
                1, int(attacker.accuracy * (1.0 - int(blind.get("potency", 0)) / 100.0))))
        accuracy_down = entity.effect_state.get(effects.ACCURACY_DOWN)
        if accuracy_down is not None:
            attacker = replace(attacker, accuracy=max(
                1, int(attacker.accuracy
                        * (1.0 - int(accuracy_down.get("potency", 0)) / 100.0))))
        attack_down = entity.effect_state.get(effects.ATTACK_DOWN)
        if attack_down is not None:
            attacker = replace(attacker, attack=max(
                1, int(attacker.attack * (1.0 - int(attack_down.get("potency", 0)) / 100.0))))
        # GEO Slip and GEO Wilt: the hexes that make the monster miss and hit softer.
        geo_accuracy = entity.effect_state.get(geomancy.GEO_ACCURACY_DOWN)
        if geo_accuracy is not None:
            attacker = replace(attacker, accuracy=max(
                1, int(attacker.accuracy
                        * (1.0 - int(geo_accuracy.get("potency", 0)) / 100.0))))
        geo_attack = entity.effect_state.get(geomancy.GEO_ATTACK_DOWN)
        if geo_attack is not None:
            attacker = replace(attacker, attack=max(
                1, int(attacker.attack
                       * (1.0 - int(geo_attack.get("potency", 0)) / 100.0))))
        attacker = self._apply_mob_self_mods(attacker, entity)
        hit = combat.melee(
            attacker, session.stat_sheet().fighter,
            zone=int(entity.zone), rng=self.rng)
        if not hit.missed and hit.damage > 0:
            # A monster builds TP from its own swings on the mob curve, which is
            # flatter than the player one below 450 delay.
            delay = max(1, int(entity.attack_delay_ms * 60 / 1000))
            self._mob_gain_tp(entity, combat.tp_return_mob(delay))
        if not hit.missed and session.has_effect(effects.RETALIATION):
            rate = 0.40 + job_points.category_total(1, "Retaliation Effect") / 100.0
            if self.rng.random() < rate:
                miss, damage, critical = self.player_attack(session, entity)
                if not miss and damage > 0:
                    defeated = entity.hp - damage <= 0
                    entity.hp = max(0, entity.hp - damage)
                    session.queue_action(int(entity.id), damage=damage,
                                         critical=critical, defeated=defeated,
                                         actor_id=int(session.char["char_id"]))
                    session.say("You retaliate against %s for %d points of damage."
                                % (entity.name, damage))
                    if defeated:
                        self.kill_mob(session, entity, time.time())
        # Avenger's Roll is a flat counter chance.  It is checked after the swing lands,
        # the same place as Retaliation, and the counter itself is an ordinary player
        # attack so damage-taken gear and the damage cap all still apply.
        counter = max(0, min(100, int(session.combat_mods().get(mod.COUNTER, 0))))
        if not hit.missed and counter and self.rng.randint(1, 100) <= counter:
            miss, damage, critical = self.player_attack(session, entity)
            if not miss and damage > 0:
                defeated = entity.hp - damage <= 0
                entity.hp = max(0, entity.hp - damage)
                session.queue_action(int(entity.id), damage=damage,
                                     critical=critical, defeated=defeated,
                                     actor_id=int(session.char["char_id"]))
                session.say("You counter %s for %d points of damage."
                            % (entity.name, damage))
                if defeated:
                    self.kill_mob(session, entity, time.time())
        return hit.missed, hit.damage, hit.critical

    # --- monster TP moves ----------------------------------------------------------------

    def _mob_skill_observers(self, entity: ZoneEntity, sessions: list) -> list:
        """The sessions close enough to see (and already know) the monster."""
        out = []
        for session in sessions:
            if int(entity.targid) not in getattr(session, "sent_targids", ()):
                continue
            if entity.distance_to(*session.pos[:3]) <= MOB_SYNC_RANGE:
                out.append(session)
        return out

    def _mob_skill_attacker(self, entity: ZoneEntity):
        """The monster's fighter with its own debuffs applied (mirrors mob_attack)."""
        attacker = self.monster_sheet(entity).fighter
        for effect_id, field in ((effects.BLINDNESS, "accuracy"),
                                 (effects.ACCURACY_DOWN, "accuracy"),
                                 (effects.ATTACK_DOWN, "attack")):
            state = entity.effect_state.get(effect_id)
            if state is None:
                continue
            percent = max(0, min(95, int(state.get("potency", 0))))
            value = int(getattr(attacker, field))
            attacker = replace(attacker, **{field: max(1, value * (100 - percent) // 100)})
        return self._apply_mob_self_mods(attacker, entity)

    def _mob_try_skill(self, entity: ZoneEntity, target, sessions: list,
                       now: float) -> bool:
        """Readies one TP move if the bar is full enough; True when the swing is spent."""
        if entity.pending_skill is not None or not entity.skill_list_id:
            return False
        skills = self.mob_skill_list(entity.skill_list_id)
        if not skills:
            return False
        if not mobskills.should_use(entity.tp, entity.tp_threshold, entity.hpp()):
            return False
        distance = entity.distance_to(*target.pos[:3])
        usable = mobskills.usable(list(skills), distance)
        if not usable:
            return False
        # Enemy-target moves need the player in range; a self-only list still plays its
        # buffs.  The shuffle is the retail choice: any usable move in the family list.
        skill = self.rng.choice(usable)
        prepare = max(0, int(skill.prepare_time)) / 1000.0
        entity.pending_skill = {
            "skill": skill, "at": now + prepare,
            "target_char_id": int(target.char["char_id"]),
        }
        # Do not auto-attack while the move is being readied or animated.
        entity.next_attack_at = now + prepare + max(0.8, skill.animation_time / 1000.0)
        if prepare > 0.01:
            self._queue_mob_skill_start(entity, skill, target, sessions)
            return True
        self._mob_fire_skill(entity, target, sessions, now)
        return True

    def _queue_mob_skill_start(self, entity: ZoneEntity, skill: "mobskills.MobSkill",
                               target, sessions: list) -> None:
        """The 0x028 SkillStart line: "<monster> readies <move>" and its pose."""
        from .zone import sub
        target_id = (int(target.char["char_id"]) if skill.is_enemy_target
                     else int(entity.id))
        body = packets.battle_action(
            int(entity.id), target_id, damage=int(skill.id), animation=0,
            kind=0, message=packets.MESSAGE_READIES_WEAPONSKILL,
            category=packets.ACTION_CATEGORY_SKILL_START,
            action_id=packets.ACTION_SKILL_USE)
        for observer in self._mob_skill_observers(entity, sessions):
            observer.queue.append(sub(0x028, body))

    def _mob_skill_targets(self, entity: ZoneEntity, skill: "mobskills.MobSkill",
                           primary, sessions: list) -> list:
        """The player sessions one TP move hits (AoE and cone handled here)."""
        if not skill.is_enemy_target:
            return []
        if skill.aoe == mobskills.AOE_ATTACKER:
            return [session for session in sessions
                    if not getattr(session, "dead_until", 0.0)
                    and int(session.char.get("hp_current", 0)) > 0
                    and entity.distance_to(*session.pos[:3]) <= max(1.0, skill.aoe_radius)]
        if skill.aoe == mobskills.AOE_TARGET:
            return [session for session in sessions
                    if not getattr(session, "dead_until", 0.0)
                    and int(session.char.get("hp_current", 0)) > 0
                    and math.dist(primary.pos[:3], session.pos[:3])
                    <= max(1.0, skill.aoe_radius)]
        # Cones are approximated as a single target: the client's facing byte is not
        # reliable enough to decide whether a player is inside a 45-degree wedge.
        return [primary]

    def _mob_fire_skill(self, entity: ZoneEntity, primary, sessions: list,
                        now: float) -> None:
        """Resolve the readied TP move and send its 0x028 result."""
        from .zone import sub
        pending = entity.pending_skill or {}
        entity.pending_skill = None
        skill = pending.get("skill")
        if not isinstance(skill, mobskills.MobSkill) or not entity.alive:
            return
        # Every TP move empties the bar in this implementation, including the few
        # LandSandBoat rows flagged TP-free: otherwise a no-cost move would fire every
        # attack round because the bar never drops.  Keep the spent value: Healing
        # Breeze's max-HP heal scales with the TP the move was used at.
        spent_tp = int(entity.tp)
        entity.tp = 0
        entity.tp_threshold = mobskills.next_threshold(self.rng)
        if (skill.is_enemy_target and not skill.is_aoe and primary is not None
                and entity.distance_to(*primary.pos[:3]) > max(1.0, skill.distance) + 1.0):
            # The player left the move's range while it was being readied; retail
            # interrupts the finish, the TP is already spent.
            return

        targets = []
        status = mobskills.status_effect(skill) if skill.is_enemy_target else None
        players = self._mob_skill_targets(entity, skill, primary, sessions)
        if skill.is_enemy_target and not players:
            return
        attacker = self._mob_skill_attacker(entity)
        if skill.is_enemy_target:
            attacker = replace(attacker, accuracy=int(attacker.accuracy) + 50)
        ftp = mobskills.damage_ftp(skill)
        self_target = None if players else entity
        for session in players:
            results = []
            hit = combat.melee(
                attacker, session.stat_sheet().fighter, zone=int(entity.zone),
                rng=self.rng, ftp=max(0.1, ftp), allow_critical=False)
            absorbed = False
            if not hit.missed and session.has_effect(effects.COPY_IMAGE) \
                    and session.effect_power(effects.COPY_IMAGE) > 0:
                session.drop_shadow()
                absorbed = True
                results.append({
                    "damage": 0, "miss": True, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_SHADOW_ABSORB,
                })
                session.queue.append(session.char_status())
                targets.append({"target_id": int(session.char["char_id"]),
                                "results": results})
                continue
            if hit.missed:
                results.append({
                    "damage": 0, "miss": True, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_SKILL_MISSES,
                })
            else:
                damage = max(0, int(hit.damage))
                defeated = int(session.char.get("hp_current", 0)) - damage <= 0
                session.take_damage(damage, entity)
                results.append({
                    "damage": damage, "miss": False, "defeated": defeated, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_DAMAGE,
                })
                if status is not None and not defeated:
                    effect_id, duration, potency = status
                    session.add_effect(effect_id, duration=duration, potency=potency)
                    session.queue.append(session.char_status())
                    results.append({
                        "damage": int(effect_id), "miss": False, "kind": 0,
                        "animation": int(skill.animation),
                        "message": packets.MESSAGE_MAGIC_ENFEEB,
                    })
            targets.append({"target_id": int(session.char["char_id"]),
                            "results": results})
        if self_target is not None:
            # A self-only move still has to animate.  Healing moves use the client's
            # "recovers HP" line; a buff shows its status icon and animation.
            effect = mobskills.self_effect(skill)
            buff = mobskills.self_buff_effect(skill)
            if effect is not None and effect[0] == "heal":
                # Healing Breeze is based on the monster's max HP and the TP it spent;
                # the other self-heals keep the small flat amount from self_effect().
                heal = mobskills.self_heal_amount(
                    skill, max_hp=int(entity.hp_max), tp=spent_tp)
                amount = int(effect[2]) if heal is None else int(heal)
                before = int(entity.hp)
                entity.hp = min(int(entity.hp_max), before + amount)
                self._queue_mob_hp(entity)
                targets.append({"target_id": int(entity.id), "results": [{
                    "damage": int(entity.hp) - before, "miss": False, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_SKILL_RECOVERS_HP,
                }]})
            elif buff is not None:
                # The stat-changing self buffs are real effects on the monster, so
                # their icon is dispellable and their modifiers reach the next swing
                # and every player hit against it (Berserk's -25% Defense).
                self.apply_mob_effect(entity, buff, None, now,
                                      duration=float(buff.duration),
                                      name=str(skill.name))
                targets.append({"target_id": int(entity.id), "results": [{
                    "damage": int(buff.effect), "miss": False, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_MAGIC_GAIN_EFFECT,
                }]})
            elif effect is not None:
                targets.append({"target_id": int(entity.id), "results": [{
                    "damage": int(effect[1]), "miss": False, "kind": 0,
                    "animation": int(skill.animation),
                    "message": packets.MESSAGE_MAGIC_GAIN_EFFECT,
                }]})
            else:
                targets.append({"target_id": int(entity.id), "results": [{
                    "damage": 0, "miss": False, "kind": 0,
                    "animation": int(skill.animation), "message": 0,
                }]})
        category = (packets.ACTION_CATEGORY_MOB_SKILL_FINISH if int(skill.id) >= 256
                    else packets.ACTION_CATEGORY_SKILL_FINISH)
        body = packets.battle_action(
            int(entity.id), 0, category=category, action_id=int(skill.id),
            targets=targets)
        observers = self._mob_skill_observers(entity, sessions)
        if not observers and primary is not None:
            observers = [primary]
        for observer in observers:
            observer.queue.append(sub(0x028, body))

    # --- status effects on monsters -----------------------------------------------------

    def add_mob_hate(self, entity: ZoneEntity, char_id: int, amount: int = 0,
                     now: float = 0.0, *, ce: int | None = None,
                     ve: int | None = None) -> None:
        """Add cumulative and volatile enmity, and pick the highest-hate player.

        Callers that only know one number (an enfeeble, an ability that hands over a
        fixed hate chunk) can pass ``amount``; it is split 25% CE / 75% VE.  Damage
        uses :meth:`add_damage_hate` and Provoke passes ``ce=1800, ve=0``, because
        Provoke's hate is cumulative and does not decay.

        The first player to generate hate on an idle monster receives retail's
        200 CE + 900 VE claim bonus, which is why a single spell pulls.
        """
        char_id = int(char_id)
        if char_id <= 0 or not entity.alive:
            return
        if ce is None and ve is None:
            total = max(0, int(amount))
            ce, ve = total * 25 // 100, total - total * 25 // 100
        else:
            ce = max(0, int(ce or 0))
            ve = max(0, int(ve or 0))

        hate = entity.enmity
        if not hate:
            ce += CLAIM_CE
            ve += CLAIM_VE
        previous_total = int(hate.get(char_id, 0))
        previous_ve = int(entity.enmity_ve.get(char_id, 0))
        new_ce = min(ENMITY_CAP, max(0, previous_total - previous_ve + ce))
        new_ve = min(ENMITY_CAP, previous_ve + ve)
        hate[char_id] = new_ce + new_ve
        entity.enmity_ve[char_id] = new_ve
        if entity.enmity_decay_at <= 0.0:
            entity.enmity_decay_at = now
        top = max(hate, key=hate.get)
        # A claimed monster stays the claiming party's fight.  The client blocks a
        # cross-party attack (the target is pink and unattackable); letting the hate list
        # move the claim to the other party was what flipped a live fight pink and left
        # the first player unable to swing, but the server still swung for them.
        claim = int(entity.claim_char_id or 0)
        if claim and claim != top:
            mine = self.group_id(claim)
            if not mine or mine != self.group_id(top):
                return
        if entity.engaged_char_id != top:
            entity.engaged_char_id = top
            entity.claim_char_id = top
            entity.next_attack_at = now + 1.5
            entity.aggro_announced = True
            # A pull is a new chase.  Drop whatever route the idle/roaming monster had
            # and any cooldown from a failed search, or the first seconds of the fight
            # were spent walking an old roam leg (or standing still) with a red name.
            self._mob_clear_nav(entity)
            entity.nav_blocked_until = 0.0
            entity.roam_target = None
            entity.roam_pause_until = 0.0
            self.set_animation(entity, 1)

    def add_damage_hate(self, entity: ZoneEntity, char_id: int, damage: int,
                        now: float) -> None:
        """Enmity from one landed hit or nuke.

        LandSandBoat's level-scaled split: ``80 / GetEnmityModDamage(level)`` CE and
        ``240 / ...`` VE per point of damage.  A miss still passes 1, which is how a
        whiff can claim an idle monster.
        """
        damage = max(1, int(damage))
        modifier = max(1, int(entity.level) * 31 // 50 + 6)
        self.add_mob_hate(entity, char_id, now=now,
                          ce=80 * damage // modifier,
                          ve=240 * damage // modifier)

    def decay_mob_enmity(self, entity: ZoneEntity, now: float) -> None:
        """Drain volatile enmity by 60 points a second; CE never decays by itself."""
        if not entity.enmity:
            entity.enmity_decay_at = now
            return
        last = float(entity.enmity_decay_at or 0.0)
        if last <= 0.0:
            entity.enmity_decay_at = now
            return
        elapsed = now - last
        if elapsed < 1.0:
            return
        entity.enmity_decay_at = now
        decay = int(VE_DECAY_PER_SECOND * elapsed)
        for char_id in list(entity.enmity):
            volatile = int(entity.enmity_ve.get(char_id, 0))
            if volatile <= 0:
                continue
            cumulative = max(0, int(entity.enmity.get(char_id, 0)) - volatile)
            volatile = max(0, volatile - decay)
            if cumulative <= 0 and volatile <= 0:
                entity.enmity.pop(char_id, None)
                entity.enmity_ve.pop(char_id, None)
            else:
                entity.enmity[char_id] = cumulative + volatile
                entity.enmity_ve[char_id] = volatile

    def mob_hate_target(self, entity: ZoneEntity):
        """The highest-hate player still in this zone and in range, or None.

        Entries for players who died, zoned out or ran past the disengage distance are
        dropped, so the monster falls back to the next name on its list instead of
        forgetting the fight.
        """
        while entity.enmity:
            top = max(entity.enmity, key=entity.enmity.get)
            session = self.session_by_char(top)
            if (session is not None and session.zone == entity.zone
                    and not session.dead_until
                    and int(session.char.get("hp_current", 0)) > 0
                    and entity.distance_to(*session.pos[:3]) <= DISENGAGE_DISTANCE):
                return session
            entity.enmity.pop(top, None)
            entity.enmity_ve.pop(top, None)
        entity.engaged_char_id = None
        return None

    def mob_effect(self, entity: ZoneEntity, effect_id: int) -> dict | None:
        return entity.effect_state.get(int(effect_id))

    def apply_mob_effect(self, entity: ZoneEntity, spec, session, now: float,
                         duration_scale: float = 1.0,
                         duration: float | None = None,
                         potency: int | None = None,
                         tick: int | None = None,
                         tick_interval: float = 3.0,
                         first_tick_delay: float | None = None,
                         tier: int = 0,
                         name: str = "") -> bool:
        """Land an enfeebling spell.  Returns False when there is no effect to apply.

        ``duration_scale`` comes from the caster's Magic Accuracy against the target's
        Magic Evasion (``combat.magic_resist``): a weak caster keeps the effect for less
        time.  ``duration``/``potency`` are the caster's already-modified values; when
        omitted the spell's table values are used.  The numbers the AI reads are kept on
        the entity: potency is a percentage (accuracy down, delay up, paralyze chance),
        tick is the damage the poison/bio family deals every three seconds.

        ``tick`` overrides the table's per-tick damage, which is how a Helix stores the
        opening nuke as the value it repeats.  ``tick_interval`` is the seconds between
        ticks (Helixes use ten, everything else three) and ``first_tick_delay`` shifts
        the first one.  ``tier`` is only meaningful for the Helix line: retail lets a
        tier-2 Helix replace any Helix but a tier-1 Helix only replaces tier 1.
        ``name`` is the spell name kept for the Target Debuffs window; Frazzle and a
        Threnody's secondary row share effect 404, so the id alone cannot label it.
        """
        if spec is None or int(spec.effect) <= 0:
            return False
        effect_id = int(spec.effect)
        existing = entity.effect_state.get(effect_id)
        if existing is not None and int(tier) and int(existing.get("tier", 0)) > int(tier):
            return False
        if effect_id not in entity.status_effects:
            entity.status_effects.append(effect_id)
        base_duration = float(spec.duration if duration is None else duration)
        interval = max(0.1, float(tick_interval))
        first_tick = interval if first_tick_delay is None else max(0.0, float(first_tick_delay))
        entity.effect_state[effect_id] = {
            "until": (now + base_duration * max(0.5, min(1.0, float(duration_scale)))
                      if base_duration else 0.0),
            "power": int(spec.power),
            "potency": int(spec.potency if potency is None else potency),
            "tick": int(spec.tick if tick is None else tick),
            "tick_interval": interval,
            "tier": int(tier),
            "icon": int(spec.icon or effect_id),
            # A buff's modifiers are the monster's own stat changes (Berserk's +45%
            # Attack / -25% Defense).  Debuff modifiers are expressed as potency and
            # read by debuffed_monster/mob_attack, so only a buff stores this dict.
            "mods": ({int(key): int(value)
                      for key, value in (getattr(spec, "mods", {}) or {}).items()}
                     if str(getattr(spec, "kind", "")) == "buff" else {}),
            "next_tick": now + first_tick,
            "source": int(session.char["char_id"]) if session is not None else 0,
            "name": str(name or ""),
        }
        log.info("%s gains effect %d", entity.name, effect_id)
        return True

    def wake_mob(self, entity: ZoneEntity) -> None:
        """Damage breaks Sleep (and a stun); the icon goes away with it."""
        for effect_id in (effects.SLEEP, effects.STUN):
            if effect_id in entity.effect_state:
                entity.effect_state.pop(effect_id, None)
                try:
                    entity.status_effects.remove(effect_id)
                except ValueError:
                    pass

    def dispel_mob(self, entity: ZoneEntity) -> int:
        """Remove one effect and return its icon, or 0 when the mob has none.

        A real self-buff carries ``mods`` (Berserk, Protect, ...), so those are picked
        before the player's enfeebles.  Dispel is a buff strip; letting it eat Dia
        before the Berserk the player is trying to remove made the ability look broken.
        """
        candidates = [effect_id for effect_id in entity.status_effects
                      if (entity.effect_state.get(effect_id) or {}).get("mods")]
        for effect_id in reversed(candidates or list(entity.status_effects)):
            state = entity.effect_state.pop(effect_id, None)
            try:
                entity.status_effects.remove(effect_id)
            except ValueError:
                pass
            if state is not None:
                return int(state.get("icon", effect_id))
        return 0

    def tick_mob_effects(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        """Expire debuffs and apply poison/bio damage once per effect's own interval."""
        from .zone import sub

        if not entity.effect_state:
            return
        for effect_id, state in list(entity.effect_state.items()):
            until = float(state.get("until") or 0.0)
            if until and now >= until:
                entity.effect_state.pop(effect_id, None)
                try:
                    entity.status_effects.remove(effect_id)
                except ValueError:
                    pass
                if state.get("hidden"):
                    continue
                icon = int(state.get("icon", effect_id))
                for session in sessions:
                    # A 0x029 battle message prints the wear-off line without an action,
                    # so the monster does not play a casting animation for it.
                    session.queue.append(sub(0x029, battle_message(
                        int(entity.id), int(entity.id), int(entity.targid),
                        int(entity.targid), icon, 0, 206)))
                continue
            tick = int(state.get("tick") or 0)
            if tick <= 0 or now < float(state.get("next_tick") or 0.0):
                continue
            # A Helix repeats its opening hit every ten seconds; poison/bio keep the
            # three-second cadence the rest of the effect system uses.
            state["next_tick"] = now + max(0.1, float(state.get("tick_interval") or 3.0))
            actor = int(state.get("source") or 0)
            source = self.session_by_char(actor) if actor else None
            entity.hp = max(0, int(entity.hp) - tick)
            log.info("%s takes %d from effect %d", entity.name, tick, effect_id)
            for session in sessions:
                # DoT ticks are silent: the 0x00E HP update already draws the loss, and
                # a chat line was printing "takes 0 points of damage" (the client does
                # not read the number from the 0x029 Data field).  A 0x028 action would
                # animate the caster every tick, so neither line is sent.
                session.queue_entity(entity, SEND_HP)
            if entity.hp <= 0:
                source = source or (sessions[0] if sessions else None)
                if source is not None:
                    self.kill_mob(source, entity, now)
                break

    def exemplar_points_for(self, session, entity: ZoneEntity) -> int:
        """Retail Exemplar Points for one kill at level 99 (BG-wiki's table).

        The effective level is ``119 + MasterLevel / 5``.  A mob at or above it pays
        ``20 + 4*dLVL``; below it ``20 + 2*dLVL``.  The mob category multiplies that
        (Locus x7, Apex x5).  Party size and Corsair's Roll are not modelled; the
        Master chain multiplier is applied by :meth:`kill_mob` after this base.
        """
        jobs = session.char.get("jobs") or {}
        entry = jobs.get(int(session.char.get("main_job", 0))) or (99, 0)
        master = int(entry[1]) if len(entry) > 1 else 0
        effective_level = 119 + max(0, master) // 5
        delta = int(getattr(entity, "level", 0) or 0) - effective_level
        base = 20 + (4 if delta >= 0 else 2) * delta
        if base <= 0:
            return 0
        name = str(getattr(entity, "name", "") or "")
        if name.startswith("High Apex"):
            multiplier = 8
        elif name.startswith("Apex"):
            multiplier = 5
        elif name.startswith("Locus"):
            multiplier = 7
        else:
            multiplier = 1
        return int(base * multiplier)

    def kill_mob(self, session, entity: ZoneEntity, now: float) -> None:
        from .zone import sub

        entity.alive = False
        entity.hp = 0
        entity.tp = 0
        entity.pending_skill = None
        entity.skillchain = None
        entity.engaged_char_id = None
        entity.enmity.clear()
        entity.enmity_ve.clear()
        entity.enmity_decay_at = 0.0
        entity.respawn_at = now + max(5, entity.respawn_seconds)
        # Leave the body on the ground for a moment instead of blinking it out: the client
        # plays the death animation from the entity update's animation byte.
        entity.animation = 3
        entity.corpse_until = now + 12.0
        for other in self.sessions_in_zone(entity.zone):
            other.queue_entity(entity, SEND_HP)
        player_level = int(session.char.get("main_level", 1))
        too_weak = player_level - entity.level > EXP_LEVEL_SPREAD
        # Level 99 is the Master Level band: kills pay Exemplar Points instead of EXP.
        # The client's own line (message 809, or 810 once the Master chain is running)
        # is what the player should see, and the points are what the 0x061 Master Level
        # block reads.  The first qualifying kill only arms the chain window; each kill
        # inside it is chain #1, #2, ... and pays +2% per link (caps at #50).  The window
        # starts at 60 s and shrinks to the 30 s floor at chain #25 (chain.py).
        exemplar = player_level >= 99
        master_chain = 0
        if exemplar:
            exp = 0
            base_points = 0 if too_weak else self.exemplar_points_for(session, entity)
            points = 0
            if base_points:
                state = getattr(session, "exemplar_chain", None)
                if state is None:
                    state = chain.ChainState()
                    session.exemplar_chain = state
                # The kill's own chain number picks the window it arms for the next one:
                # a broken chain restarts at #0 (60 s), an inside kill uses its new link.
                next_chain = state.number + 1 if state.active(now) else 0
                master_chain = state.advance(
                    now, window=chain.window_for(next_chain),
                    cap=chain.EXEMPLAR_CHAIN_MAX)
                points = int(base_points * state.bonus(
                    chain.EXEMPLAR_CHAIN_BONUS_PER_LINK))
                log.info("%s %s: %d exemplar points, Master chain #%d (base %d)",
                         session.addr, entity.name, points, master_chain, base_points)

        else:
            points = 0
            exp = 0 if too_weak else max(1, entity.level * 8 + self.rng.randint(0, 4))
        # Corsair's Roll raises experience, capacity and exemplar points.  The reward is
        # paid to the killer, which is the player whose roll is being read here.
        try:
            roll_bonus = max(0, int(session.combat_mods().get(mod.EXP_BONUS, 0)))
        except Exception:
            roll_bonus = 0
        if roll_bonus:
            if exemplar:
                points = points * (100 + roll_bonus) // 100
            else:
                exp = exp * (100 + roll_bonus) // 100
        gil = 0 if too_weak else max(1, entity.level * 2 + self.rng.randint(0, 3))
        try:
            updated = self.service.award_exp_gil(
                session.char["id"], points if exemplar else exp, gil, exemplar=exemplar)
            levels = int(updated.pop("levels_gained", 0))
            master_levels = int(updated.pop("master_levels_gained", 0))
            for key in ("main_level", "exp", "exp_next", "hp", "mp", "hp_current",
                        "mp_current", "gil", "exemplar_points"):
                if key in updated:
                    session.char[key] = updated[key]
            if exemplar and "master_level" in updated:
                jobs = session.char.setdefault("jobs", {})
                main_job = int(session.char.get("main_job", 0))
                entry = jobs.get(main_job) or (int(session.char.get("main_level", 99)), 0)
                jobs[main_job] = (entry[0], int(updated["master_level"]))
            cid = int(session.char["char_id"])
            targid = int(session.char.get("targid", 0x400))
            session.queue.append(sub(0x029, battle_message(
                cid, int(entity.id), targid, int(entity.targid), 0, 0, 6)))
            if exemplar and points:
                session.queue.append(sub(0x02D, battle_message2(
                    cid, cid, targid, targid, points, master_chain,
                    packets.MESSAGE_MASTER_CHAIN if master_chain
                    else packets.MESSAGE_EXEMPLAR_POINTS_GAINED)))
            elif exp:
                session.queue.append(sub(0x02D, battle_message2(
                    cid, cid, targid, targid, exp, 0, 8)))
            if gil:
                session.queue.append(sub(0x029, battle_message(
                    cid, cid, targid, targid, gil, 0, 565)))
            if levels:
                # A level changes the base HP/MP, and the client is about to be shown them.
                session.refresh_vitals()
                session.queue.append(sub(0x029, battle_message(
                    cid, cid, targid, targid, int(updated["main_level"]), 0, 9)))
                session.queue += [session.job_info(), session.char_sync()]
            if master_levels:
                session.queue.append(sub(0x02D, battle_message2(
                    cid, cid, targid, targid, int(updated["master_level"]), 0,
                    packets.MESSAGE_MASTER_LEVEL_UP)))
            session.queue.extend([session.char_stats(), session.char_status(), session.party_member()])
            session.queue.append(sub(0x01E, item_num(int(updated.get("gil", session.char.get("gil", 0))), 0, 0)))
        except Exception as exc:
            log.warning("could not award the kill: %s", exc)
        try:
            from . import content
            content.mob_killed(session, entity)
        except Exception as exc:
            log.warning("content kill hook failed: %s", exc)

    def flush(self, now: float | None = None) -> None:
        """Push one packet to every session that has something queued.

        The zone socket used to time out only when every client was quiet, and that was
        the only place this ran.  A box team with one busy character therefore starved
        every other box's queue: the busy client kept the socket readable, so the idle
        boxes' mob updates and action results never left the server.  The zone loop now
        calls this on a timer as well; the per-session gap below is what keeps it to one
        packet at a time while a client is still reading the previous one.
        """
        udp = self.udp
        if udp is None:
            return
        now = time.time() if now is None else float(now)
        for session in list(self.sessions.values()):
            if not session.queue or not session.logged_in or not session.key:
                continue
            if now - float(getattr(session, "last_sent_at", 0.0)) < FLUSH_INTERVAL:
                continue
            try:
                packet = session.build(session.client_hdr or bytes(28))
                if not packet:
                    continue
                session.last_sent_at = now
                udp.sendto(packet, session.addr)
            except (OSError, ValueError) as exc:
                log.debug("flush to %s: %s", getattr(session, "addr", "?"), exc)

    def close(self) -> None:
        for sock in self.sockets:
            try:
                sock.close()
            except OSError:
                pass
        self.sockets.clear()


def load_huffman(folder: str | Path | None) -> Huffman | None:
    if not folder:
        return None
    folder = Path(folder)
    if folder.name == "compress.dat":
        folder = folder.parent
    path = folder / "compress.dat"
    if not path.exists():
        return None
    return Huffman.from_folder(folder)
