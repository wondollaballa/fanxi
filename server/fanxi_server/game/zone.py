"""The zone protocol: login, entities, movement, chat, inventory, shops and basic combat.

The server is intentionally small but speaks the real client protocol: 0x00A/0x00C zone-in,
0x00E NPC/mob spawns on the client's first 0x015, 0x028 battle actions, 0x020/0x01D inventory,
0x03C/0x03E/0x03F shops, and the status/job packets the client waits on.
"""
from __future__ import annotations

import logging
import os
import socket
import struct
import time

from . import packets
from .cipher import md5
from .world import MELEE_RANGE, PLAYER_ATTACK_DELAY

log = logging.getLogger("fanxi.zone")
DEBUG = bool(os.environ.get("FANXI_ZONE_DEBUG"))

HDR = 28
TARGID = 0x400
VANA_EPOCH = 1009810800
VANA_HOUR, VANA_DAY = 144, 3456


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
        self.seen: set[int] = set()
        self.last_save = 0.0
        self.client_hdr = b""
        self.entities: list = []
        self.engaged_id: int | None = None
        self.next_attack_at = 0.0
        self.dead_until = 0.0
        self.zone_loaded = False
        self.entities_sent = False
        self.position_seen = False
        self.target_targid = 0
        self.shop_key = ""
        self.shop_items: list[dict] = []

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
            s = world.by_char.pop(cid, None) or (session if session and session.key else None)
            if s is None:
                char = world.character_by_char_id(cid)
                account = char.get("account_id") if char else None
                game_session = world.service.active_game_session(account) if account else None
                if not char or not game_session:
                    log.warning("%s: login for %#x without an active session", addr, cid)
                    return None
                key = world.keys.get(account) or world.key_from_hash(game_session["session_hash"])
                s = ZoneSession(world, addr, char)
                s.zone = int(char["zone"])
                s.pos = list(char["pos"])
                s.set_key(key)
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
        code = struct.unpack_from("<H", hdr, 0)[0]
        if DEBUG:
            types = []
            offset = 0
            while offset + 4 <= len(body) and body[offset + 1] & 0xFE:
                types.append("%03X@%d" % (struct.unpack_from("<H", body, offset)[0] & 0x1FF,
                                          struct.unpack_from("<H", body, offset + 2)[0]))
                offset += (body[offset + 1] & 0xFE) * 2
            log.debug("in #%d ack %d (sent #%d): %s", code, struct.unpack_from("<H", hdr, 2)[0],
                      self.server_id, " ".join(types))
        offset = 0
        while offset + 4 <= len(body):
            size = (body[offset + 1] & 0xFE) * 2
            if size == 0 or offset + size > len(body):
                break
            ptype = struct.unpack_from("<H", body, offset)[0] & 0x1FF
            sync = struct.unpack_from("<H", body, offset + 2)[0]
            if self.client_id < sync <= code:
                self.handle(ptype, body[offset:offset + size])
            offset += size
        self.client_id = code

    def handle(self, t: int, p: bytes) -> None:
        handled = t in self.seen
        self.seen.add(t)
        if t == 0x00C:  # the client has the zone: send it everything else
            if not self.zone_loaded:
                self.after_zone_in()
        elif t == 0x01A:  # target action: talk, engage, disengage
            self.action(p)
        elif t == 0x083:  # shop purchase
            self.buy(p)
        elif t in (0x016, 0x017):  # the client asks for an entity it lacks
            self.request_entity(p)
        elif t == 0x015 and not self.zoning:  # position (the old zone's, while changing zones)
            x, y, z = struct.unpack_from("<fff", p, 4)
            self.pos = [x, y, z, struct.unpack_from("<b", p, 20)[0] & 255]
            self.position_seen = True
            self.save_position()
            self.sync_entities()
        elif t == 0x05E:  # a zone line
            rect = struct.unpack_from("<I", p, 4)[0]
            line = self.world.zones.lines.get(rect)
            if line:
                self.change_zone(line[0], list(line[1:]))
            else:
                self.say("zone line %#x: unknown (add it to the zone_lines table)" % rect)
                self.queue.append(sub(0x052, bytes(4)))  # release the client's controls
        elif t == 0x0B5:  # chat
            text = bytes(p[6:]).split(b"\0")[0].decode("ascii", "replace")
            if text.startswith("!"):
                self.command(text[1:].split())
        elif t == 0x04B:  # the server message, which the client asks for until it has all of it
            kind, lang = p[6], p[7]
            stamp, offset = struct.unpack_from("<i", p, 8)[0], struct.unpack_from("<i", p, 16)[0]
            if kind == 1:
                self.queue.append(self.server_message(lang, stamp, offset))
        elif t == 0x061:  # its stats
            self.queue += [self.char_stats(), self.party_member()]
        elif t == 0x05A:  # conquest standings: none
            self.queue.append(sub(0x05E, bytes(0xB0)))
        elif t == 0x03C:  # the blacklist
            self.queue.append(self.blacklist())
        elif t == 0x0E7:  # /logout, /shutdown
            self.save_position(force=True)
            self.queue.append(self.logout_packet(1))
            log.info("%s logs out", self.addr)
        elif not handled:  # the rest needs no answer here; each is logged once
            log.debug("0x%03X (%d bytes) ignored", t, len(p))

    def command(self, words: list[str]) -> None:
        commands = ("commands: !zone <id> [x y z [rot]], !pos <x> <y> <z> [rot], "
                    "!where, !time <hour>, !heal, !entities")
        try:
            if words and words[0] == "zone" and len(words) >= 2:
                zone = int(words[1], 0)
                pos = [float(v) for v in words[2:5]] + [int(words[5]) if len(words) > 5 else 0] \
                    if len(words) >= 5 else None
                self.change_zone(zone, pos)
            elif words and words[0] == "pos" and len(words) >= 4:
                self.change_zone(self.zone, [float(v) for v in words[1:4]] +
                                 [int(words[4]) if len(words) > 4 else self.pos[3]])
            elif words and words[0] == "where":
                self.say("%s (%d): %.2f %.2f %.2f rot %d" % (
                    self.world.zones.name(self.zone), self.zone, self.pos[0], self.pos[1], self.pos[2], self.pos[3]))
            elif words and words[0] == "time" and len(words) >= 2:
                self.world.clock = vana_offset(float(words[1]))
                self.change_zone(self.zone, list(self.pos))
            elif words and words[0] == "heal":
                self.char["hp_current"] = int(self.char["hp"])
                self.char["mp_current"] = int(self.char["mp"])
                self.world.service.save_vitals(self.char["id"], self.char["hp_current"], self.char["mp_current"])
                self.queue += [self.char_status(), self.char_stats(), self.party_member()]
                self.say("HP and MP restored.")
            elif words and words[0] == "entities":
                names = ", ".join("%s (%#x)" % (e.name, e.targid) for e in self.entities) or "none"
                self.say("Entities here: " + names)
            elif words and words[0] == "help":
                self.say(commands)
            else:
                self.say(commands)
        except ValueError:
            self.say("numbers, please")

    def change_zone(self, zone: int, pos) -> None:
        self.zone = int(zone)
        self.pos = list(pos) if pos else list(self.world.zones.position(self.zone))
        self.zoning = True
        self.char["zone"] = self.zone
        self.char["pos"] = list(self.pos)
        self.save_position(force=True)
        log.info("%s -> %s (%d) at %s", self.addr, self.world.zones.name(self.zone), self.zone, self.pos)
        self.queue.append(self.logout_packet(2, zone_change=True))

    def logout_packet(self, state: int, zone_change: bool = False) -> Msg:
        ip = socket.inet_aton(self.world.host_ip) if zone_change else bytes(4)
        port = self.world.ports["zone_port"] if zone_change else 0
        p = sub(0x00B, struct.pack("<B3x4sI8xI", state, ip, port, 0))
        p.zone_out = True
        return p

    def say(self, text: str) -> None:
        msg = text.encode("ascii", "replace")[:150]
        self.queue.append(sub(0x017, struct.pack("<BBH", 6, 0, self.zone) + bytes(15) + msg + b"\0"))

    # --- what the client is sent ---
    def on_login(self) -> None:
        self.logged_in = True
        self.zoning = False
        self.zone_loaded = False
        self.entities_sent = False
        self.position_seen = False
        self.dead_until = 0.0
        self.engaged_id = None
        if int(self.char.get("hp_current", 1)) <= 0:
            self.char["hp_current"] = max(1, int(self.char["hp"]) // 2)
            self.char["mp_current"] = int(self.char.get("mp", 0)) // 2
            try:
                self.world.service.save_vitals(
                    self.char["id"], self.char["hp_current"], self.char["mp_current"])
            except Exception:
                pass
        self.queue += [sub(0x04F, bytes(4)), self.grap_list(), self.item_max(), self.login_packet()]

    def after_zone_in(self) -> None:
        q = [sub(0x008, b"\xff" * 48),  # every zone visited: every map viewable
             self.grap_list(), self.job_info(), self.char_status(), self.char_stats(),
             self.party_member(), self.char_update()]
        q += [sub(0x055, bytes(128) + struct.pack("<HH", table, 0)) for table in range(7)]  # no key items
        offered = (0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x88)
        logs = offered + tuple(x + 0x40 for x in offered) + (
            0xD0, 0xD8, 0x30, 0x38, 0xE0, 0xE8, 0xF0, 0xF8, 0x100, 0x108)
        q += [sub(0x056, bytes(32) + struct.pack("<HH", port, 0)) for port in logs]
        q.append(sub(0x056, bytes(36) + struct.pack("<HH", 0xFFFF, 0)))
        q += [sub(0x0AA, bytes(128)),          # no spells
              sub(0x0AE, bytes(8)),            # no mounts
              sub(0x0AC, bytes(224)),          # no abilities or weapon skills
              self.char_sync(),
              sub(0x08C, bytes(8)),            # no merits
              self.blacklist()]
        q += self.inventory_packets()
        self.queue += q
        self.zone_loaded = True
        if self.position_seen:
            self.sync_entities()
        self.say("%s (%d). Say !help for commands." % (self.world.zones.name(self.zone), self.zone))

    # --- entities, inventory and actions -------------------------------------------------------
    def load_zone_entities(self) -> None:
        self.entities = list(self.world.entities_for_zone(self.zone))
        self.entities_sent = False
        self.engaged_id = None
        self.target_targid = 0

    def sync_entities(self) -> None:
        """The client asks for nearby entities with its first 0x015, not at zone-in."""
        if self.entities_sent or not self.zone_loaded:
            return
        self.entities_sent = True
        for entity in self.entities:
            self.queue_entity(entity, packets.SEND_SPAWN)

    def entity_packet(self, entity, mask: int = packets.SEND_SPAWN) -> Msg:
        return sub(0x00E, packets.entity_update(entity, mask))

    def queue_entity(self, entity, mask: int = packets.SEND_SPAWN) -> None:
        self.queue.append(self.entity_packet(entity, mask))

    def inventory_packets(self) -> list[Msg]:
        out = [self.item_max()]
        flags = 0
        items = self.world.service.inventory(self.char["id"])
        for item in items:
            if int(item["container"]) != 0:
                continue
            out.append(sub(0x020, packets.item_attr(
                int(item["item_id"]), int(item["quantity"]), 0, int(item["slot"]))))
        flags |= 1  # container 0
        out.append(sub(0x01D, packets.item_same(0, 0, flags)))
        for container in (1, 9, 2, 17, 8, 10, 11, 12, 13, 14, 15, 16, 3, 4, 5, 6, 7):
            flags |= 1 << container
            out.append(sub(0x01D, packets.item_same(0, container, flags)))
        out.append(sub(0x01D, packets.item_same(1, 18, flags)))
        return out

    def refresh_inventory(self) -> None:
        for item in self.world.service.inventory(self.char["id"]):
            if int(item["container"]) == 0:
                self.queue.append(sub(0x020, packets.item_attr(
                    int(item["item_id"]), int(item["quantity"]), 0, int(item["slot"]))))
        self.queue.append(sub(0x01D, packets.item_same(1, 18, 1)))

    def refresh_character(self) -> None:
        row = self.world.service.character(self.char["id"])
        if row:
            for key, value in row.items():
                self.char[key] = value
            self.queue += [self.char_stats(), self.char_status(), self.party_member()]

    def queue_action(self, target_id: int, damage: int, *, miss: bool = False,
                     critical: bool = False, defeated: bool = False,
                     actor_id: int | None = None) -> None:
        distortion = 0
        if not miss and damage:
            max_hp = max(1, int(getattr(self, "_last_target_hp", 100)))
            percent = damage * 100 // max_hp
            distortion = 3 if percent >= 20 else 2 if percent >= 10 else 1
        actor = int(actor_id if actor_id is not None else self.char["char_id"])
        self.queue.append(sub(0x028, packets.battle_action(
            actor, int(target_id), int(damage), miss=miss,
            critical=critical, defeated=defeated, hit_distortion=distortion)))

    def action(self, p: bytes) -> None:
        if len(p) < 12:
            return
        _unique, act_index, action_id = struct.unpack_from("<IHH", p, 4)
        target = self.world.entity_by_targid(self.zone, int(act_index))
        if target is None:
            target = next((e for e in self.entities if e.id == int(_unique)), None)
        if action_id == 0x14:  # SendResRdy: the client is ready for nearby entities
            self.sync_entities()
        elif action_id == packets.ACTION_TALK:
            if target is not None and target.kind == "npc":
                if target.distance_to(*self.pos[:3]) > 6.0:
                    self.say("You are too far away.")
                    return
                from . import content
                content.npc_talk(self, target)
            elif target is not None and target.kind == "mob":
                self.say("%s has no time for conversation." % target.name)
            else:
                self.say("There is nothing to talk to there.")
        elif action_id == packets.ACTION_ATTACK:
            if target is not None and target.kind == "mob" and target.alive:
                if target.distance_to(*self.pos[:3]) > MELEE_RANGE:
                    self.say("You are too far away.")
                    return
                self.engaged_id = int(target.id)
                target.engaged_char_id = int(self.char["char_id"])
                target.next_attack_at = time.time() + 1.5
                self.next_attack_at = time.time() + 0.5
                self.say("You engage %s." % target.name)
            else:
                self.say("You cannot attack that.")
        elif action_id == packets.ACTION_ATTACK_OFF:
            if self.engaged_id:
                self.say("You disengage.")
            self.engaged_id = None
        elif action_id == packets.ACTION_CHANGE_TARGET:
            self.target_targid = int(act_index)

    def request_entity(self, p: bytes) -> None:
        if len(p) < 8:
            return
        act = struct.unpack_from("<H", p, 4)[0]
        if act == TARGID:
            self.queue += [self.char_update(), self.char_status()]
            return
        entity = self.world.entity_by_targid(self.zone, act)
        if entity is not None:
            self.queue_entity(entity, packets.SEND_SPAWN)

    def take_damage(self, amount: int, entity) -> None:
        self.char["hp_current"] = max(0, int(self.char.get("hp_current", self.char["hp"])) - int(amount))
        self.queue += [self.char_status(), self.party_member()]
        try:
            self.world.service.save_vitals(self.char["id"], self.char["hp_current"], self.char.get("mp_current", 0))
        except Exception:
            pass
        if int(self.char["hp_current"]) <= 0:
            self.dead_until = time.time() + 6.0
            self.engaged_id = None
            self.say("You have been defeated. You recover in a moment.")
            try:
                self.world.service.record_death(self.char["id"])
            except Exception:
                pass

    def tick(self, now: float) -> None:
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
            self.queue += [self.char_status(), self.char_stats(), self.party_member()]
            self.say("You recover from your wounds.")
            return
        if not self.engaged_id:
            return
        entity = self.world.entity_by_id(self.zone, int(self.engaged_id))
        if entity is None or not entity.alive:
            self.engaged_id = None
            return
        if entity.distance_to(*self.pos[:3]) > MELEE_RANGE:
            self.say("You disengage from %s." % entity.name)
            self.engaged_id = None
            return
        if now < self.next_attack_at:
            return
        miss, damage, critical = self.world.player_attack(self.char, entity)
        defeated = (not miss) and entity.hp - damage <= 0
        self._last_target_hp = entity.hp_max
        self.queue_action(entity.id, damage, miss=miss, critical=critical, defeated=defeated)
        if not miss:
            entity.hp = max(0, entity.hp - damage)
            self.queue_entity(entity, packets.SEND_HP)
            if defeated:
                self.world.kill_mob(self, entity, now)
        self.next_attack_at = now + PLAYER_ATTACK_DELAY

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
        return [c["face"] | (c["race"] << 8), c["head"] + 0x1000, c["body"] + 0x2000,
                c["hands"] + 0x3000, c["legs"] + 0x4000, c["feet"] + 0x5000,
                c["main"] + 0x6000, c["sub"] + 0x7000, c["ranged"] + 0x8000]

    def grap_list(self) -> Msg:
        return sub(0x051, struct.pack("<9H2x", *self.looks()))

    def item_max(self) -> Msg:
        return sub(0x01C, packets.item_max())

    def login_packet(self) -> Msg:
        c = self.char
        now = int(time.time())
        x, y, z, rot = self.pos
        b = bytearray(0x100)
        struct.pack_into("<IHBbfff", b, 0x00, c["char_id"], TARGID, 0, (int(rot) + 128) % 256 - 128, x, y, z)
        hpp = 100 if int(c["hp"]) <= 0 else max(0, min(100, int(c.get("hp_current", c["hp"])) * 100 // int(c["hp"])))
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, hpp, 0)
        struct.pack_into("<I", b, 0x1C, (self.female() * 128 + (1 << c["size"])) << 8)
        struct.pack_into("<I", b, 0x24, 0x0100)
        struct.pack_into("<IIII", b, 0x2C, self.zone, 0, now, now - VANA_EPOCH + self.world.clock)
        struct.pack_into("<HH9H", b, 0x3C, 0, self.zone, *self.looks())
        music = self.world.zones.music_for(self.zone)
        struct.pack_into("<5H", b, 0x52, *music, 0xD4)
        struct.pack_into("<I", b, 0x7C, 2)
        b[0x80:0x90] = cstr(c["name"], 16)
        struct.pack_into("<II", b, 0x9C, 3600, 60 * 360)
        struct.pack_into("<H", b, 0xA6, 0x01FF)
        b[0xAC:0xF0] = self.dancer()[:0x44]
        struct.pack_into("<I", b, 0xFC, 1)
        return sub(0x00A, b)

    def dancer(self) -> bytearray:
        c = self.char
        b = bytearray(0x60)
        struct.pack_into("<HHBBBBI", b, 0, c["race"], c["face"], c["main_job"], 0, c["size"],
                         c["sub_job"], 0xFFFFFFFE)
        b[0x10 + c["main_job"]] = c["main_level"]
        b[0x48 + c["main_job"]] = c["main_level"]
        struct.pack_into("<7H", b, 0x20, *([50] * 7))
        struct.pack_into("<ii", b, 0x3C, c["hp"], c["mp"])
        b[0x44] = 1
        return b

    def job_info(self) -> Msg:
        # 0x01B carries the GP_MYROOM_DANCER block plus mastery/encumbrance fields.
        return sub(0x01B, self.dancer() + bytes(0x80 - 0x60))

    def party_member(self) -> Msg:
        c = self.char
        b = bytearray(0x24)
        struct.pack_into("<IIIIHBBBBH", b, 0, c["char_id"], c.get("hp_current", c["hp"]), c.get("mp_current", c["mp"]),
                         0, TARGID, 100, 100, 0, 0, self.zone)
        struct.pack_into("<BBBB", b, 0x1C, c["main_job"], c["main_level"], c["sub_job"], c["sub_level"])
        return sub(0x0DF, b)

    def char_stats(self) -> Msg:
        c = self.char
        b = bytearray(0x6C)
        struct.pack_into("<iiBBBBhh", b, 0, c["hp"], c["mp"], c["main_job"], c["main_level"], c["sub_job"],
                         c["sub_level"], int(c.get("exp", 0)) & 0x7FFF,
                         int(c.get("exp_next", 1000)) & 0x7FFF)
        struct.pack_into("<7H", b, 0x10, *([50] * 7))
        struct.pack_into("<hh", b, 0x2C, 100, 100)
        struct.pack_into("<HHHH", b, 0x40, 0, 1, 0, self.zone)
        b[0x4C] = c["nation"]
        return sub(0x061, b)

    def char_status(self) -> Msg:
        c = self.char
        b = bytearray(0x60)
        hp = max(1, int(c["hp"]))
        hpp = max(0, min(100, int(c.get("hp_current", hp)) * 100 // hp))
        flags0 = (self.female() << 8) | ((c["size"] & 3) << 11) | (hpp << 16)
        flags1 = (c["speed"] & 0xFFF) | (40 << 17)
        struct.pack_into("<III", b, 0x20, c["char_id"], flags0, flags1)
        struct.pack_into("<II", b, 0x38, 60 * 360, int(time.time()) - VANA_EPOCH + self.world.clock + 360)
        b[0x54] = 0x10
        return sub(0x037, b)

    def char_update(self) -> Msg:
        c = self.char
        x, y, z, rot = self.pos
        b = bytearray(0x68)
        struct.pack_into("<IHBBfff", b, 0, c["char_id"], TARGID, 0x1F, int(rot) & 255, x, y, z)
        hpp = 100 if int(c["hp"]) <= 0 else max(0, min(100, int(c.get("hp_current", c["hp"])) * 100 // int(c["hp"])))
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, hpp, 0)
        struct.pack_into("<I", b, 0x1C, ((c["size"] & 3) << 9) | (self.female() << 15))
        b[0x3F] = 10
        struct.pack_into("<9H", b, 0x44, *self.looks())
        b[0x56:0x66] = cstr(c["name"], 16)
        return sub(0x00D, b)

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
        struct.pack_into("<I", h, 8, int(time.time()))
        data, nbits, zone_out = self.pack()
        data += struct.pack("<I", nbits)
        data += md5(data)
        out = h + data
        self.cipher.run(out, HDR, (len(data) // 4) & ~1, True)
        self.last = out
        if zone_out:
            self.bump_key()
            with self.world.lock:
                self.world.by_char[self.char["char_id"]] = self
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
            body += p
            zone_out = zone_out or p.zone_out
        data, nbits = self.world.huff.compress(bytes(body))
        return data, nbits, zone_out

    def resend(self) -> bytes:
        struct.pack_into("<H", self.last, 2, self.client_id)
        struct.pack_into("<I", self.last, 8, int(time.time()))
        return bytes(self.last)
