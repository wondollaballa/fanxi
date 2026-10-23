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

from . import combat, effects, stats
from .cipher import M32, VIEW_KEY, Huffman, md5, zone_cipher
from .entities import ZoneEntity, mob_from_row, npc_from_row
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
# You can draw on a target at about the range a spell reaches (retail: roughly 1.5x magic
# range).  The client drops its own attack when the target leaves auto-attack reach (near
# MELEE_RANGE); the server keeps the engagement out to here so a player can kite without
# sheathing and losing TP gear.
ENGAGE_RANGE = 30.0
# Entities are streamed in as the player walks, the way retail does it: sending a zone's
# whole population at once floods the client's entity table.
SYNC_RANGE = 60.0
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
# A zone session has no TCP connection to watch: silence is the disconnect.  The client
# sends position packets continuously, so a force-quit or a dead network is visible as a
# long gap.  Without this the character stayed in every other client's world forever.
SESSION_IDLE_TIMEOUT = 60.0
# The one legitimate silence is a zone change: the client loads the next zone and comes
# back with its advanced cipher.  A hand-off older than this is a dead zone change.
ZONE_CHANGE_TIMEOUT = 30.0


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


class World:
    def __init__(self, config: Config, service: FanxiService, huffman: Huffman | None,
                 bind: str | None = None):
        self.config = config
        self.service = service
        self.huff = huffman
        # Monster combat stats depend only on level, so one sheet serves every spawn.
        self._monster_sheets: dict[int, stats.Sheet] = {}
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
        # character id -> the targid the other clients see it as (0x400 is "self" in each client)
        self.player_targids: dict[int, int] = {}
        self.content: dict[int, list[ZoneEntity]] = {}
        self.lock = threading.RLock()
        self.sockets: list = []
        self.udp = None
        self.rng = random.Random()
        self.last_tick = 0.0
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
        with self.lock:
            # Key the hand-off by the database id: that is the id every lookup can name,
            # while the wire id differs between client builds (content id vs database id).
            self.by_char[int(character["id"])] = session
        return session

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
        return entities

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
            if not session.logged_in or session.zoning or getattr(session, "gone", False):
                continue
            if int(session.char["char_id"]) == int(char_id):
                return session
        return None

    def sessions_in_zone(self, zone: int) -> list:
        return [s for s in self.sessions.values()
                if s.logged_in and not s.zoning and not getattr(s, "gone", False)
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
            # loading the next zone.
            continuing = bool(prepared.key is not None and
                              time.time() - prepared.last_packet_at <= ZONE_CHANGE_TIMEOUT)
            if not continuing:
                self.evict_session(prepared, reason="stale zone change")
                prepared = None
        elif prepared is not None:
            # A fresh session the lobby prepared for this login: no live state to keep.
            prepared.char = character
            prepared.zoning = False

        # Every other session claiming this character is a force-quit ghost.  Every session
        # at this address is the previous occupant of a recycled UDP port.  Both must be
        # despawned from the clients that still draw them before the new login appears.
        for other_addr, other in list(self.sessions.items()):
            if other is prepared:
                continue
            same_character = int(getattr(other, "char", {}).get("id", -1)) == db_id
            if same_character or other_addr == addr:
                # Save the last position the dead client reported: the new login already
                # read its own row, and the next one should start where it stopped.
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
            timeout = ZONE_CHANGE_TIMEOUT if session.zoning else SESSION_IDLE_TIMEOUT
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

    def broadcast_player(self, session, mask: int, moving: bool | None = None) -> None:
        """Send one player's entity update to every nearby client that has it spawned."""
        from .zone import sub

        char_id = int(session.char["char_id"])
        for observer in self.sessions_in_zone(session.zone):
            if observer is session or not getattr(observer, "entities_sent", False):
                continue
            if char_id not in observer.seen_players:
                continue
            observer.queue.append(sub(0x00D, session.player_body(mask, moving=moving)))

    def despawn_player(self, session) -> None:
        """Remove a player from the clients that can see it (zone change, logout)."""
        from .zone import sub

        char_id = int(session.char["char_id"])
        for observer in self.sessions_in_zone(session.zone):
            if observer is session:
                continue
            seen = observer.seen_players.pop(char_id, None)
            if seen is None:
                continue
            # The client knows this character under the targid it was spawned with.  A
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
    def advance(self, now: float | None = None) -> None:
        """Run timers, AI and combat without sending; the caller decides when to flush."""
        now = time.time() if now is None else now
        self.last_tick = now
        self.reap_sessions(now)
        for session in list(self.sessions.values()):
            if session.logged_in and not session.zoning and not getattr(session, "gone", False):
                session.tick(now)
        for zone, entities in list(self.content.items()):
            sessions = self.sessions_in_zone(zone)
            if not sessions:
                continue
            for entity in entities:
                if entity.is_mob():
                    self._tick_mob(entity, sessions, now)
        # A logged-out session stays long enough for flush() to send its 0x00B, then goes.
        for addr, session in list(self.sessions.items()):
            if getattr(session, "gone", False) and not session.queue:
                self.sessions.pop(addr, None)
                self.release_player_targid(int(session.char.get("char_id", 0)))
                with self.lock:
                    for key, value in list(self.by_char.items()):
                        if value is session:
                            self.by_char.pop(key, None)

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
                entity.reset_mob(now)
                for session in sessions:
                    session.queue_entity(entity, SEND_SPAWN)
                log.info("%s respawned in zone %d", entity.name, entity.zone)
            return

        self.tick_mob_effects(entity, sessions, now)
        if not entity.alive:
            return

        target = self.session_by_char(entity.engaged_char_id) if entity.engaged_char_id else None
        if entity.engaged_char_id and (target is None or target.zone != entity.zone
                                       or target.dead_until or int(target.char.get("hp_current", 0)) <= 0
                                       or entity.distance_to(*target.pos[:3]) > DISENGAGE_DISTANCE):
            entity.engaged_char_id = None
            entity.aggro_announced = False
            self.set_animation(entity, 0, sessions)
            target = None

        if target is not None:
            # Sleep and Stun stop the mob where it stands.  Damage wakes it (wake_mob).
            if effects.SLEEP in entity.effect_state or effects.STUN in entity.effect_state:
                entity.next_attack_at = now + 1.0
                return
            # The mob is fighting: draw its weapon and put it in the attack stance.
            self.set_animation(entity, 1, sessions)
            reach = entity.distance_to(*target.pos[:3])
            if reach > MOB_REACH:
                if effects.BIND in entity.effect_state:
                    entity.next_attack_at = now + 1.0
                    return
                # Walk into range before swinging: a mob used to hit from across the zone.
                dx = target.pos[0] - entity.x
                dz = target.pos[2] - entity.z
                step = MOB_CHASE_SPEED * max(0.0, min(0.5, now - entity.last_move_at))
                weight = entity.effect_state.get(effects.WEIGHT)
                if weight is not None:
                    step *= max(0.1, 1.0 - int(weight.get("potency", 0)) / 100.0)
                entity.last_move_at = now
                span = math.hypot(dx, dz) or 1.0
                if step > 0 and span > 0.01:
                    entity.x += dx / span * min(step, span - MOB_REACH * 0.8)
                    entity.z += dz / span * min(step, span - MOB_REACH * 0.8)
                    entity.moving = True
                    entity.rot = heading_to_rot(dx, dz)
                    if now - entity.last_sync_at >= 0.3:
                        entity.last_sync_at = now
                        for session in sessions:
                            if entity.targid in getattr(session, "sent_targids", ()):
                                session.queue_entity(entity, SEND_POSITION)
                return
            entity.moving = False
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
            for session in sessions:
                if session.dead_until or int(session.char.get("hp_current", 0)) <= 0:
                    continue
                # Sneak and Invisible keep a mob from noticing you at all.
                if session.has_effect(effects.SNEAK) or session.has_effect(effects.INVISIBLE):
                    continue
                if int(session.char.get("main_level", 1)) - entity.level > AGGRO_LEVEL_SPREAD:
                    continue
                if entity.distance_to(*session.pos[:3]) <= AGGRO_DISTANCE:
                    entity.engaged_char_id = int(session.char["char_id"])
                    entity.next_attack_at = now + 1.5
                    self.set_animation(entity, 1, sessions)
                    if not entity.aggro_announced:
                        session.say("%s notices you." % entity.name)
                        entity.aggro_announced = True
                    return

        # Roam: walk a few yalms, stand still for a few seconds, then pick a new heading.
        # A mob that picks a fresh random direction the instant it arrives jitters in place.
        if entity.roam_radius <= 0:
            return
        watchers = [s for s in sessions if entity.distance_to(*s.pos[:3]) <= SYNC_RANGE]
        if not watchers:
            # Nobody is close enough to draw it; leave the mob where it is instead of
            # burning a position update on every spawn point in the zone.
            entity.last_move_at = now
            return

        if entity.roam_target is None:
            if now < entity.roam_pause_until:
                return
            distance = self.rng.uniform(3.0, max(4.0, min(7.0, entity.roam_radius)))
            target_x = entity.x
            target_z = entity.z
            # Turn gently: a fresh heading within ~60 degrees of the last one.  Reversing on
            # the spot each leg is what made the walk look like it was swaying.
            first_angle = entity.roam_heading + self.rng.uniform(-1.0, 1.0)
            for attempt in range(6):
                angle = first_angle if attempt == 0 else self.rng.uniform(0.0, 6.283185)
                try_x = entity.x + distance * math.cos(angle)
                try_z = entity.z + distance * math.sin(angle)
                # Keep the destination inside the spawn area; a clamp to the boundary
                # turns a long walk into a shuffle, so try another heading first.
                if math.hypot(try_x - entity.spawn_x, try_z - entity.spawn_z) <= entity.roam_radius:
                    target_x, target_z = try_x, try_z
                    break
            else:
                off_x = target_x - entity.spawn_x
                off_z = target_z - entity.spawn_z
                reach = math.hypot(off_x, off_z)
                if reach > entity.roam_radius:
                    scale = entity.roam_radius / reach
                    target_x = entity.spawn_x + off_x * scale
                    target_z = entity.spawn_z + off_z * scale
            entity.roam_target = (target_x, target_z)
            entity.roam_heading = math.atan2(target_x - entity.x, target_z - entity.z)
            entity.moving = True
            entity.rot = heading_to_rot(target_x - entity.x, target_z - entity.z)
            entity.last_move_at = now
            return

        target_x, target_z = entity.roam_target
        dx, dz = target_x - entity.x, target_z - entity.z
        # Cap the step: a mob that has not been ticked for a while (nobody in the zone)
        # must not leap across its spawn area in a single update.
        step = MOB_WALK_SPEED * max(0.0, min(0.5, now - entity.last_move_at))
        entity.last_move_at = now
        if step <= 0.0:
            return
        remaining = math.hypot(dx, dz)
        arrived = remaining <= max(0.3, step)
        if arrived:
            entity.x, entity.z = target_x, target_z
            entity.roam_target = None
            entity.moving = False
            entity.roam_pause_until = now + self.rng.uniform(3.0, 8.0)
        else:
            entity.x += dx / remaining * step
            entity.z += dz / remaining * step
            # Keep the facing in step with the leg we are walking, on every update: a stale
            # rotation byte next to a moving position makes the client swing the model.
            entity.rot = heading_to_rot(dx, dz)
        entity.y = entity.spawn_y
        # Always send the resting position, so the client does not leave the mob stranded
        # between two waypoints while it stands still.
        if not arrived and now - entity.last_sync_at < 0.3:
            return
        entity.last_sync_at = now
        for session in watchers:
            if entity.targid in getattr(session, "sent_targids", ()) or entity.kind == "npc":
                session.queue_entity(entity, SEND_POSITION)

    def monster_sheet(self, entity: ZoneEntity):
        """A monster's combat stats, cached per level: they depend on nothing else."""
        sheet = self._monster_sheets.get(int(entity.level))
        if sheet is None:
            sheet = stats.build_monster(int(entity.level))
            self._monster_sheets[int(entity.level)] = sheet
        return sheet

    def player_attack(self, session, entity: ZoneEntity, *, ftp: float = 1.0,
                      attack_multiplier: float = 1.0, off_hand: bool = False):
        """One player swing at a monster: (missed, damage, critical).

        ``off_hand`` picks the sheet's second Fighter (the dual-wielded sub weapon).
        It has its own damage rating, skill and Accuracy, and retail caps its hit rate
        at 95% instead of 99%.
        """
        target = self.monster_sheet(entity).fighter
        evasion_down = entity.effect_state.get(effects.EVASION_DOWN)
        if evasion_down is not None:
            target = replace(target, evasion=max(
                1, int(target.evasion * (1.0 - int(evasion_down.get("potency", 0)) / 100.0))))
        sheet = session.stat_sheet()
        attacker = sheet.sub_fighter if off_hand else sheet.fighter
        if attacker is None:
            # Only callers that saw a dual-wield sheet ask for the off hand; a missing
            # fighter would otherwise silently swing the main hand twice.
            return True, 0, False
        hit = combat.melee(
            attacker, target, zone=int(entity.zone), rng=self.rng, ftp=ftp,
            attack_multiplier=attack_multiplier)
        return hit.missed, hit.damage, hit.critical

    def mob_attack(self, entity: ZoneEntity, session):
        """One monster swing at a player: (missed, damage, critical).

        The player's damage-taken gear is applied inside the engine, so the number that
        comes back is what the client should print -- PDT and DT already taken off.
        Blind and Attack Down are applied to the monster's fighter copy here; the
        monster sheet itself is cached per level and must stay clean.
        """
        attacker = self.monster_sheet(entity).fighter
        blind = entity.effect_state.get(effects.BLINDNESS)
        if blind is not None:
            attacker = replace(attacker, accuracy=max(
                1, int(attacker.accuracy * (1.0 - int(blind.get("potency", 0)) / 100.0))))
        attack_down = entity.effect_state.get(effects.ATTACK_DOWN)
        if attack_down is not None:
            attacker = replace(attacker, attack=max(
                1, int(attacker.attack * (1.0 - int(attack_down.get("potency", 0)) / 100.0))))
        hit = combat.melee(
            attacker, session.stat_sheet().fighter,
            zone=int(entity.zone), rng=self.rng)
        return hit.missed, hit.damage, hit.critical

    # --- status effects on monsters -----------------------------------------------------

    def mob_effect(self, entity: ZoneEntity, effect_id: int) -> dict | None:
        return entity.effect_state.get(int(effect_id))

    def apply_mob_effect(self, entity: ZoneEntity, spec, session, now: float,
                         duration_scale: float = 1.0) -> bool:
        """Land an enfeebling spell.  Returns False when there is no effect to apply.

        ``duration_scale`` comes from the caster's Magic Accuracy against the target's
        Magic Evasion (``combat.magic_resist``): a weak caster keeps the effect for less
        time.  The numbers the AI reads are kept on the entity: potency is a percentage
        (accuracy down, delay up, paralyze chance), tick is the damage the poison/bio
        family deals every three seconds.
        """
        if spec is None or int(spec.effect) <= 0:
            return False
        effect_id = int(spec.effect)
        if effect_id not in entity.status_effects:
            entity.status_effects.append(effect_id)
        entity.effect_state[effect_id] = {
            "until": (now + float(spec.duration) * max(0.5, min(1.0, float(duration_scale)))
                      if spec.duration else 0.0),
            "power": int(spec.power),
            "potency": int(spec.potency),
            "tick": int(spec.tick),
            "icon": int(spec.icon or effect_id),
            "next_tick": now + 3.0,
            "source": int(session.char["char_id"]) if session is not None else 0,
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
        """Remove one effect and return its icon, or 0 when the mob has none."""
        for effect_id in reversed(list(entity.status_effects)):
            state = entity.effect_state.pop(effect_id, None)
            try:
                entity.status_effects.remove(effect_id)
            except ValueError:
                pass
            if state is not None:
                return int(state.get("icon", effect_id))
        return 0

    def tick_mob_effects(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        """Expire debuffs and apply poison/bio damage once every three seconds."""
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
                icon = int(state.get("icon", effect_id))
                for session in sessions:
                    session.queue_action(int(entity.id), icon, actor_id=int(entity.id),
                                         message=206, kind=0,
                                         category=4, info=0)
                continue
            tick = int(state.get("tick") or 0)
            if tick <= 0 or now < float(state.get("next_tick") or 0.0):
                continue
            state["next_tick"] = now + 3.0
            actor = int(state.get("source") or 0)
            entity.hp = max(0, int(entity.hp) - tick)
            for session in sessions:
                session.queue_action(int(entity.id), tick,
                                     actor_id=actor or int(entity.id),
                                     message=185, kind=0, category=4, info=0)
                session.queue_entity(entity, SEND_HP)
            if entity.hp <= 0:
                source = self.session_by_char(actor) if actor else (sessions[0] if sessions else None)
                if source is not None:
                    self.kill_mob(source, entity, now)
                break

    def kill_mob(self, session, entity: ZoneEntity, now: float) -> None:
        from .zone import sub

        entity.alive = False
        entity.hp = 0
        entity.engaged_char_id = None
        entity.respawn_at = now + max(5, entity.respawn_seconds)
        # Leave the body on the ground for a moment instead of blinking it out: the client
        # plays the death animation from the entity update's animation byte.
        entity.animation = 3
        entity.corpse_until = now + 12.0
        for other in self.sessions_in_zone(entity.zone):
            other.queue_entity(entity, SEND_HP)
        player_level = int(session.char.get("main_level", 1))
        too_weak = player_level - entity.level > EXP_LEVEL_SPREAD
        exp = 0 if too_weak else max(1, entity.level * 8 + self.rng.randint(0, 4))
        gil = 0 if too_weak else max(1, entity.level * 2 + self.rng.randint(0, 3))
        try:
            updated = self.service.award_exp_gil(session.char["id"], exp, gil)
            levels = int(updated.pop("levels_gained", 0))
            for key in ("main_level", "exp", "exp_next", "hp", "mp", "hp_current", "mp_current", "gil"):
                if key in updated:
                    session.char[key] = updated[key]
            cid = int(session.char["char_id"])
            targid = int(session.char.get("targid", 0x400))
            session.queue.append(sub(0x029, battle_message(
                cid, int(entity.id), targid, int(entity.targid), 0, 0, 6)))
            if exp:
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
        udp = self.udp
        if udp is None:
            return
        for session in list(self.sessions.values()):
            if not session.queue or not session.logged_in or not session.key:
                continue
            try:
                packet = session.build(session.client_hdr or bytes(28))
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
