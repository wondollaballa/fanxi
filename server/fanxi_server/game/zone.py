"""The zone protocol: what the client needs to stand in a zone and move around.

This is a small, deliberately data-light world. It speaks enough of the zone protocol to log the
character in, place it, keep its position and change zones, and answers the packets the client
waits on. There are no NPCs, monsters, items or combat.
"""
from __future__ import annotations

import logging
import os
import socket
import struct
import time

from .cipher import md5

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
    """One message inside a zone packet: 9-bit type, size in 4-byte units, sync (set when sent)."""
    body = bytes(body)
    n = (4 + len(body) + 3) & ~3
    p = Msg(n)
    struct.pack_into("<HH", p, 0, ptype & 0x1FF, n // 2)
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
            world.sessions[addr] = s
            s.client_id = struct.unpack_from("<H", buf, 0)[0]
            s.queue.clear()
            s.last = None
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
        session.parse(buf, body)
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
            self.after_zone_in()
        elif t == 0x015 and not self.zoning:  # position (the old zone's, while changing zones)
            x, y, z = struct.unpack_from("<fff", p, 4)
            self.pos = [x, y, z, struct.unpack_from("<b", p, 20)[0] & 255]
            self.save_position()
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
        elif t == 0x016 and struct.unpack_from("<H", p, 4)[0] == TARGID:  # the character asks about itself
            self.queue += [self.char_update(), self.char_status()]
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
            elif words and words[0] == "help":
                self.say("commands: !zone <id> [x y z [rot]], !pos <x> <y> <z> [rot], !where, !time <hour>")
            else:
                self.say("commands: !zone <id> [x y z [rot]], !pos <x> <y> <z> [rot], !where, !time <hour>")
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
        self.queue += [sub(0x04F, bytes(4)), self.grap_list(), self.item_max(), self.login_packet()]

    def after_zone_in(self) -> None:
        q = [sub(0x008, b"\xff" * 48),  # every zone visited: every map viewable
             self.item_max(), self.grap_list(), self.job_info(), self.char_status(), self.char_stats(),
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
        flags = 0
        for container in (0, 1, 9, 2, 17, 8, 10, 11, 12, 13, 14, 15, 16, 3, 4, 5, 6, 7):
            flags |= 1 << container
            q.append(sub(0x01D, struct.pack("<BB2xI", 0, container, flags)))
        q.append(sub(0x01D, struct.pack("<BB2xI", 1, 18, flags)))
        self.queue += q
        self.say("%s (%d). Say !help for commands." % (self.world.zones.name(self.zone), self.zone))

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
        b = bytearray(96)
        for i in range(18):
            b[i] = 81
            struct.pack_into("<H", b, 32 + 2 * i, 81)
        return sub(0x01C, b)

    def login_packet(self) -> Msg:
        c = self.char
        now = int(time.time())
        x, y, z, rot = self.pos
        b = bytearray(0x100)
        struct.pack_into("<IHBbfff", b, 0x00, c["char_id"], TARGID, 0, (int(rot) + 128) % 256 - 128, x, y, z)
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, 100, 0)
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
        b[0xAC:0xF0] = self.dancer()
        struct.pack_into("<I", b, 0xFC, 1)
        return sub(0x00A, b)

    def dancer(self) -> bytearray:
        c = self.char
        b = bytearray(0x44)
        struct.pack_into("<HHBBBBI", b, 0, c["race"], c["face"], c["main_job"], c["face"], c["size"],
                         c["sub_job"], 0xFFFFFFFE)
        b[0x0C + c["main_job"]] = c["main_level"]
        struct.pack_into("<7H", b, 0x1C, *([50] * 7))
        struct.pack_into("<ii", b, 0x38, c["hp"], c["mp"])
        b[0x40] = 1
        return b

    def job_info(self) -> Msg:
        return sub(0x01B, self.dancer() + bytes(0x68 - 0x44))

    def party_member(self) -> Msg:
        c = self.char
        b = bytearray(0x24)
        struct.pack_into("<IIIIHBBBBH", b, 0, c["char_id"], c["hp"], c["mp"], 0, TARGID, 100, 100, 0, 0, self.zone)
        struct.pack_into("<BBBB", b, 0x1C, c["main_job"], c["main_level"], c["sub_job"], c["sub_level"])
        return sub(0x0DF, b)

    def char_stats(self) -> Msg:
        c = self.char
        b = bytearray(0x6C)
        struct.pack_into("<iiBBBBhh", b, 0, c["hp"], c["mp"], c["main_job"], c["main_level"], c["sub_job"],
                         c["sub_level"], 0, 1000)
        struct.pack_into("<7H", b, 0x10, *([50] * 7))
        struct.pack_into("<hh", b, 0x2C, 100, 100)
        struct.pack_into("<HHHH", b, 0x40, 0, 1, 0, self.zone)
        b[0x4C] = c["nation"]
        return sub(0x061, b)

    def char_status(self) -> Msg:
        c = self.char
        b = bytearray(0x5C)
        b[0:32] = b"\xff" * 32
        flags0 = (self.female() << 8) | ((c["size"] & 3) << 11) | (100 << 16)
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
        struct.pack_into("<BBBB", b, 0x18, c["speed"], 40, 100, 0)
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
