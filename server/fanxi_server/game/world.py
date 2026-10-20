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
from .cipher import M32, VIEW_KEY, Huffman, md5, zone_cipher
from .entities import ZoneEntity, mob_from_row, npc_from_row
from .packets import SEND_HP, SEND_POSITION, SEND_SPAWN, battle_message, battle_message2, item_num

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

AGGRO_DISTANCE = 8.0
DISENGAGE_DISTANCE = 30.0
MELEE_RANGE = 12.0
PLAYER_ATTACK_DELAY = 3.0


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
        self.by_char: dict[int, object] = {}      # char id -> ZoneSession waiting for its 0x00A
        self.keys: dict[int, bytes] = {}          # account id -> the 20-byte zone key the client sent
        self.content: dict[int, list[ZoneEntity]] = {}
        self.lock = threading.RLock()
        self.sockets: list = []
        self.udp = None
        self.rng = random.Random()
        self.last_tick = 0.0

    # --- data helpers --------------------------------------------------------------------------
    def character_record(self, row: dict) -> dict:
        return self.service.character_record(row, self.server_name)

    def characters_for(self, account_id: int) -> list[dict]:
        return [self.character_record(row) for row in self.service.characters_for_account(account_id)]

    def character_by_char_id(self, char_id: int) -> dict | None:
        row = self.service.character_by_char_id(char_id)
        return self.character_record(row) if row else None

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
            self.by_char[int(character["char_id"])] = session
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
        for index, row in enumerate(npcs[:0x100]):
            targid = 0x100 + index
            dialogue = self.service.npc_lines(row["id"])
            entities.append(npc_from_row(row, targid, dialogue))
        for index, row in enumerate(mobs[:0x100]):
            targid = 0x200 + index
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
            if int(session.char["char_id"]) == int(char_id):
                return session
        return None

    def sessions_in_zone(self, zone: int) -> list:
        return [s for s in self.sessions.values()
                if s.logged_in and not s.zoning and int(s.zone) == int(zone) and s.key]

    # --- the tick ------------------------------------------------------------------------------
    def advance(self, now: float | None = None) -> None:
        """Run timers, AI and combat without sending; the caller decides when to flush."""
        now = time.time() if now is None else now
        self.last_tick = now
        for session in list(self.sessions.values()):
            if session.logged_in and not session.zoning:
                session.tick(now)
        for zone, entities in list(self.content.items()):
            sessions = self.sessions_in_zone(zone)
            if not sessions:
                continue
            for entity in entities:
                if entity.is_mob():
                    self._tick_mob(entity, sessions, now)

    def tick(self, now: float | None = None) -> None:
        self.advance(now)
        self.flush(now)

    def _tick_mob(self, entity: ZoneEntity, sessions: list, now: float) -> None:
        if not entity.alive:
            if entity.respawn_at and now >= entity.respawn_at:
                entity.reset_mob(now)
                for session in sessions:
                    session.queue_entity(entity, SEND_SPAWN)
                log.info("%s respawned in zone %d", entity.name, entity.zone)
            return

        target = self.session_by_char(entity.engaged_char_id) if entity.engaged_char_id else None
        if entity.engaged_char_id and (target is None or target.zone != entity.zone
                                       or target.dead_until or int(target.char.get("hp_current", 0)) <= 0
                                       or entity.distance_to(*target.pos[:3]) > DISENGAGE_DISTANCE):
            entity.engaged_char_id = None
            entity.aggro_announced = False
            target = None

        if target is not None:
            if now >= entity.next_attack_at:
                miss, damage, critical = self.mob_attack(entity, target.char)
                if not miss:
                    target.take_damage(damage, entity)
                defeated = int(target.char.get("hp_current", 0)) <= 0
                target.queue_action(int(target.char["char_id"]), damage, miss=miss,
                                    critical=critical, defeated=defeated, actor_id=int(entity.id))
                entity.next_attack_at = now + max(1.0, entity.attack_delay_ms / 1000.0)
            return

        # Aggro a nearby player.
        if entity.aggro:
            for session in sessions:
                if session.dead_until or int(session.char.get("hp_current", 0)) <= 0:
                    continue
                if entity.distance_to(*session.pos[:3]) <= AGGRO_DISTANCE:
                    entity.engaged_char_id = int(session.char["char_id"])
                    entity.next_attack_at = now + 1.5
                    if not entity.aggro_announced:
                        session.say("%s notices you." % entity.name)
                        entity.aggro_announced = True
                    return

        # Roam around the spawn point.
        if entity.roam_radius > 0 and now - entity.last_move_at >= 4.0:
            angle = self.rng.uniform(0, 6.283185)
            distance = self.rng.uniform(0.5, entity.roam_radius)
            entity.x = entity.spawn_x + distance * math.cos(angle)
            entity.z = entity.spawn_z + distance * math.sin(angle)
            entity.y = entity.spawn_y
            entity.rot = self.rng.randint(0, 255)
            entity.last_move_at = now
            for session in sessions:
                session.queue_entity(entity, SEND_POSITION)

    def player_attack(self, char: dict, entity: ZoneEntity):
        level = int(char.get("main_level", 1))
        hit = 0.88 - max(0, entity.evasion - level * 2) / 250.0
        if self.rng.random() > max(0.35, hit):
            return True, 0, False
        critical = self.rng.random() < 0.08
        damage = int(level * 2 + self.rng.randint(1, 6) - entity.defense * 0.5)
        if critical:
            damage *= 2
        return False, max(1, damage), critical

    def mob_attack(self, entity: ZoneEntity, char: dict):
        level = int(char.get("main_level", 1))
        hit = 0.82 - max(0, level * 2 - entity.accuracy) / 300.0
        if self.rng.random() > max(0.35, hit):
            return True, 0, False
        critical = self.rng.random() < 0.05
        damage = int(entity.level + self.rng.randint(0, 3) - level * 0.4)
        if critical:
            damage = int(damage * 1.5)
        return False, max(1, damage), critical

    def kill_mob(self, session, entity: ZoneEntity, now: float) -> None:
        from .zone import sub

        entity.alive = False
        entity.hp = 0
        entity.engaged_char_id = None
        entity.respawn_at = now + max(5, entity.respawn_seconds)
        for other in self.sessions_in_zone(entity.zone):
            other.queue_entity(entity, SEND_HP)
        exp = max(1, entity.level * 8 + self.rng.randint(0, 4))
        gil = max(1, entity.level * 2 + self.rng.randint(0, 3))
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
            session.queue.append(sub(0x02D, battle_message2(
                cid, cid, targid, targid, exp, 0, 8)))
            if gil:
                session.queue.append(sub(0x029, battle_message(
                    cid, cid, targid, targid, gil, 0, 565)))
            if levels:
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
