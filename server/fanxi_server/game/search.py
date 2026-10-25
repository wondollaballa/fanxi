"""The client's search server: ``/sea all`` and ``/sea <name>``.

The lobby's 0x0B reply advertises a second address beside the zone address.  That is the
search server, and it is a plain TCP service; the game opens a connection there for the
``/sea`` window instead of sending anything to the zone.  Fanxi used to advertise the port
without binding it, so every search failed at connect time.

A search packet starts with an eight-byte header: a 16-bit size, two zero bytes and ``IXFF``.
The encrypted body follows, then a 20-byte trailer (16 bytes of MD5 and a 4-byte nonce).  The
body is encrypted with the client's Blowfish variant.  Requests use a fixed 16-byte search key
plus the nonce; replies also fold in the last four bytes of the request body, which the client
itself puts there.  The layout mirrors LandSandBoat's search service because that is the layout
the retail client expects.

Fanxi has no separate search process: the search server lists the zone sessions that are
online in this process, so a name search answers with the character's current zone and
``/sea all`` is the online roster.  Offline characters do not appear, which is the same
behaviour as retail's search server.
"""
from __future__ import annotations

import functools
import logging
import struct
from dataclasses import dataclass, field

from .cipher import Blowfish, md5

log = logging.getLogger("fanxi.game")

# The fixed key the client's search cipher starts from.  This is a protocol constant (it is
# in LandSandBoat's search_handler.h), not a secret: the nonce protects a packet, not a login.
SEARCH_KEY = b"0s=m<1IZ2zBCc8{~"

HEADER_SIZE = 0x18
TRAILER_SIZE = 20          # 16-byte MD5 + 4-byte nonce
REQUEST_MAX = 4096         # LandSandBoat's search read buffer; replies are capped at 1024
RESULTS_PER_PACKET = 20
MAX_RESULTS = 40

# Request types the client sends to this service.  The rest belong to the auction house and
# the friend/party list, which Fanxi does not provide.
TCP_SEARCH_ALL = 0x00
TCP_SEARCH = 0x03
SEARCH_TYPES = {TCP_SEARCH_ALL: "all", TCP_SEARCH: "name"}

# SearchType values from the client's packed query.  The widths live in parse_query().
NAME = 0x00
AREA = 0x01
NATION = 0x02
JOB = 0x03
LEVEL = 0x04
RACE = 0x05
FLAGS1 = 0x06
MASTER_LEVEL = 0x07
RANK = 0x10
COMMENT = 0x11
LINKSHELL = 0x0B
LINKSHELL2 = 0x13
LINKSHELL3 = 0x14
FLAGS2 = 0x16
FRIEND = 0x0C
REQUEST_LIST = 0x18
LANGUAGE = 0x17

# Entries that carry no present/sort bit pair of their own.
_NO_SORT_BITS = {COMMENT, LINKSHELL, LINKSHELL2, LINKSHELL3, FLAGS2, FRIEND, REQUEST_LIST}


def _cipher(key: bytes) -> Blowfish:
    """Blowfish keyed by an MD5 digest, without the zone cipher's zero truncation."""
    return Blowfish(md5(key))


def decode_request(packet: bytes) -> tuple[bytes, bytes, bytes] | None:
    """Validate and decrypt one search packet.

    Returns ``(plaintext, nonce, tail4)``.  ``nonce`` is the unencrypted four bytes at the
    end of the packet; ``tail4`` is the four bytes before the trailer that the client also
    uses when it decrypts the reply.  None means the packet was too short, the length field
    disagreed, or the MD5 did not check out.
    """
    if len(packet) < 28:
        return None
    if struct.unpack_from("<H", packet, 0)[0] != len(packet):
        return None

    nonce = bytes(packet[-4:])
    buf = bytearray(packet)
    cipher = _cipher(SEARCH_KEY + nonce)
    words = (len(buf) - 12) // 4
    words -= words % 2
    cipher.run(buf, 8, words, enc=False)

    if md5(bytes(buf[8:len(buf) - TRAILER_SIZE])) != bytes(buf[len(buf) - 20:len(buf) - 4]):
        return None
    tail4 = bytes(buf[len(buf) - 24:len(buf) - 20])
    return bytes(buf), nonce, tail4


def encode_reply(body: bytes, nonce: bytes, tail4: bytes) -> bytes:
    """Encrypt a search list packet for the client that sent ``nonce`` and ``tail4``."""
    data_end = len(body)
    packet = bytearray(body)
    packet += bytes(TRAILER_SIZE)
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"

    packet[data_end:data_end + 16] = md5(bytes(packet[8:data_end]))
    cipher = _cipher(SEARCH_KEY + nonce + tail4)
    words = (len(packet) - 12) // 4
    words -= words % 2
    cipher.run(packet, 8, words, enc=True)
    packet[-4:] = nonce
    return bytes(packet)


class _Bits:
    """MSB-first bit reader, the order the client's search bitstream uses."""

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def remaining(self) -> int:
        return len(self.data) * 8 - self.offset

    def read(self, count: int) -> int | None:
        if count < 0 or self.offset + count > len(self.data) * 8:
            return None
        value = 0
        for _ in range(count):
            index = self.offset >> 3
            bit = (self.data[index] >> (7 - (self.offset & 7))) & 1
            value = (value << 1) | bit
            self.offset += 1
        return value


class _BitWriter:
    """MSB-first bit writer, the inverse of _Bits."""

    def __init__(self, data: bytearray, offset: int = 0):
        self.data = data
        self.offset = offset

    def write(self, value: int, count: int) -> None:
        for index in range(count - 1, -1, -1):
            at = self.offset >> 3
            if at >= len(self.data):
                self.data.append(0)
            if (value >> index) & 1:
                self.data[at] |= 1 << (7 - (self.offset & 7))
            self.offset += 1

    def align(self) -> None:
        if self.offset & 7:
            self.offset += 8 - (self.offset & 7)


@dataclass
class SearchQuery:
    kind: int = TCP_SEARCH_ALL
    name: str = ""
    zones: list[int] = field(default_factory=list)
    nation: int = 255
    job: int = 0
    min_level: int = 0
    max_level: int = 0
    min_master_level: int = 0
    max_master_level: int = 0
    race: int = 255
    min_rank: int = 0
    max_rank: int = 0
    flags: int = 0
    comment: int = 0
    sort: list[tuple[int, bool]] = field(default_factory=list)


def parse_query(packet: bytes) -> SearchQuery:
    """Read the packed query at 0x10 of a decrypted search request.

    The widths are the client's own: each entry starts with a five-bit SearchType, most are
    followed by a descending bit and an "is present" bit, then the value.  A short or
    malformed packet stops the parse at the last complete entry rather than raising.
    """
    query = SearchQuery(kind=packet[0x0B] if len(packet) > 0x0B else TCP_SEARCH_ALL)
    if len(packet) < 0x12:
        return query

    size = int(packet[0x10])
    data_end = min(0x11 + size, max(0x11, len(packet) - TRAILER_SIZE))
    bits = _Bits(packet[0x11:data_end])
    present = 0

    while bits.remaining() >= 5:
        entry = bits.read(5)
        if entry is None:
            break
        descending = False
        if entry not in _NO_SORT_BITS:
            if bits.remaining() < 2:
                break
            descending = bool(bits.read(1))
            present = int(bits.read(1))
            if not any(kind == entry for kind, _ in query.sort):
                query.sort.append((entry, descending))

        if entry == NAME:
            if present:
                raw_len = bits.read(5)
                if raw_len is None:
                    break
                chars = []
                # The client writes every character it declared; the window only shows the
                # first fifteen, but the parser must consume the whole field to stay in sync.
                for index in range(raw_len):
                    char = bits.read(7)
                    if char is None:
                        break
                    if index < 15:
                        chars.append(chr(char))
                query.name = "".join(chars)
        elif entry == AREA:
            if present:
                zone = bits.read(10)
                if zone is None:
                    break
                query.zones.append(zone)
        elif entry == NATION:
            if present:
                value = bits.read(2)
                if value is None:
                    break
                query.nation = value
        elif entry == JOB:
            if present:
                value = bits.read(5)
                if value is None:
                    break
                query.job = value
        elif entry == LEVEL:
            if present:
                low, high = bits.read(8), bits.read(8)
                if low is None or high is None:
                    break
                query.min_level, query.max_level = low, high
        elif entry == MASTER_LEVEL:
            if present:
                low, high = bits.read(8), bits.read(8)
                if low is None or high is None:
                    break
                query.min_master_level, query.max_master_level = low, high
        elif entry == RACE:
            if present:
                value = bits.read(4)
                if value is None:
                    break
                query.race = value
        elif entry == RANK:
            if present:
                low, high = bits.read(8), bits.read(8)
                if low is None or high is None:
                    break
                query.min_rank, query.max_rank = low, high
        elif entry == FLAGS1:
            if present:
                value = bits.read(16)
                if value is None:
                    break
                query.flags = value
        elif entry == COMMENT:
            value = bits.read(32)
            if value is None:
                break
            query.comment = value
        elif entry in (LINKSHELL, LINKSHELL2, LINKSHELL3):
            if bits.read(32) is None:
                break
        elif entry == FLAGS2:
            value = bits.read(32)
            if value is None:
                break
            query.flags = value

    return query


def _rank(character: dict) -> int:
    nation = int(character.get("nation") or 0)
    key = {0: "rank_sandoria", 1: "rank_bastok", 2: "rank_windurst"}.get(nation)
    return int(character.get(key) or 0) if key else 0


def _race_matches(wanted: int, race: int) -> bool:
    groups = {0: (1, 2), 1: (3, 4), 2: (5, 6), 3: (7,), 4: (8,)}
    if wanted not in groups:
        return True
    return race in groups[wanted]


def _compare(left: dict, right: dict, kind: int) -> int:
    if kind == NAME:
        a, b = str(left.get("name") or "").casefold(), str(right.get("name") or "").casefold()
    elif kind == AREA:
        a, b = int(left.get("zone") or 0), int(right.get("zone") or 0)
    elif kind == NATION:
        a, b = int(left.get("nation") or 0), int(right.get("nation") or 0)
    elif kind == JOB:
        a, b = int(left.get("main_job") or 0), int(right.get("main_job") or 0)
    elif kind == LEVEL:
        a, b = int(left.get("main_level") or 0), int(right.get("main_level") or 0)
    elif kind == RACE:
        a, b = int(left.get("race") or 0), int(right.get("race") or 0)
    elif kind == RANK:
        a, b = _rank(left), _rank(right)
    else:
        return 0
    return (a > b) - (a < b)


def online_characters(world) -> list[dict]:
    """The characters that are logged in right now, one entry per character.

    A zone session is authoritative while its owner is online: the live zone (which changes
    during a zone transition) and the in-memory job/level/rank fields are fresher than the
    row the character logged in from.  A session without the zone key has not finished its
    login and is not playing yet.
    """
    with world.lock:
        sessions = list(world.sessions.values())

    by_character: dict[int, tuple[float, dict]] = {}
    for session in sessions:
        if not getattr(session, "logged_in", False):
            continue
        if getattr(session, "gone", False) or not getattr(session, "key", None):
            continue
        char = dict(getattr(session, "char", {}) or {})
        if not char.get("name"):
            continue
        char["zone"] = int(getattr(session, "zone", char.get("zone") or 0) or 0)
        identifier = int(char.get("id") or char.get("char_id") or 0)
        seen_at = float(getattr(session, "last_packet_at", 0.0) or 0.0)
        if identifier not in by_character or seen_at >= by_character[identifier][0]:
            by_character[identifier] = (seen_at, char)
    return [char for _seen, char in by_character.values()]


def matching_characters(world, query: SearchQuery) -> list[dict]:
    """The online characters that satisfy the query, in the client's sort order."""
    wanted_name = query.name.casefold()
    found = []
    for char in online_characters(world):
        name = str(char.get("name") or "")
        if wanted_name and not name.casefold().startswith(wanted_name):
            continue
        zone = int(char.get("zone") or 0)
        # `/sea <name>` carries the client's current area as an implicit condition.  A direct
        # name search should still find the character when it has moved elsewhere, which is
        # the whole point of asking where somebody is; an unnamed area search (`/sea all`
        # with an area condition) keeps its filter.
        if not query.name and query.zones and query.zones[0] != 0 and zone not in query.zones:
            continue
        job = int(char.get("main_job") or 0)
        if query.job and query.job != job:
            continue
        level = int(char.get("main_level") or 0)
        if query.min_level and query.max_level >= query.min_level:
            if level < query.min_level or level > query.max_level:
                continue
        nation = int(char.get("nation") or 0)
        if query.nation != 255 and query.nation != nation:
            continue
        if query.race != 255 and not _race_matches(query.race, int(char.get("race") or 0)):
            continue
        rank = _rank(char)
        if query.min_rank and query.max_rank >= query.min_rank:
            if rank < query.min_rank or rank > query.max_rank:
                continue
        found.append(char)

    if query.sort:
        def compare(left, right):
            for kind, descending in query.sort:
                order = _compare(left, right, kind)
                if order:
                    return -order if descending else order
            return 0

        found.sort(key=functools.cmp_to_key(compare))
    else:
        found.sort(key=lambda char: str(char.get("name") or "").casefold())
    return found


def _entry_body(character: dict) -> bytes:
    """One packed search-result entry, without its leading size byte."""
    body = bytearray()
    writer = _BitWriter(body)
    name = str(character.get("name") or "")[:15]
    zone = int(character.get("zone") or 0) & 0x3FF
    nation = int(character.get("nation") or 0) & 0x3
    main_job = int(character.get("main_job") or 0) & 0x1F
    sub_job = int(character.get("sub_job") or 0) & 0x1F
    main_level = int(character.get("main_level") or 0) & 0xFF
    sub_level = int(character.get("sub_level") or 0) & 0xFF
    race = int(character.get("race") or 0) & 0xF
    rank = _rank(character) & 0xFF
    # The client's Id field is 20 bits.  Fanxi's content ids are 0x01000000 + the database
    # id, so the low 20 bits are the per-character number the client knows it by.
    identifier = int(character.get("char_id") or character.get("id") or 0) & 0xFFFFF
    flags1 = 0
    flags2 = 0
    languages = 1

    writer.write(NAME, 5)
    writer.write(len(name), 4)
    for char in name:
        writer.write(ord(char) & 0x7F, 7)

    writer.write(AREA, 5)
    writer.write(zone, 10)

    writer.write(NATION, 5)
    writer.write(nation, 2)

    writer.write(JOB, 5)
    writer.write(main_job, 5)
    writer.write(sub_job, 5)

    writer.write(LEVEL, 5)
    writer.write(main_level, 8)
    writer.write(sub_level, 8)

    writer.write(RACE, 5)
    writer.write(race, 4)

    writer.write(RANK, 5)
    writer.write(rank, 8)

    writer.write(FLAGS1, 5)
    writer.write(flags1, 16)

    writer.write(0x08, 5)  # SearchType::Id
    writer.write(identifier, 20)

    # Retail puts the three linkshell ranks and ids here for /sea all; LandSandBoat sends
    # this zero word instead, and the client accepts it.
    writer.write(0x0E, 5)  # SearchType::Unknown0E
    writer.write(0, 32)

    writer.write(FLAGS2, 5)
    writer.write(flags2, 32)

    writer.write(LANGUAGE, 5)
    writer.write(languages, 16)

    writer.align()
    return bytes(body)


def _result_packet(characters: list[dict], total: int, final: bool) -> bytes:
    body = bytearray(HEADER_SIZE)
    struct.pack_into("<B", body, 0x0B, 0x80)
    struct.pack_into("<H", body, 0x0E, total & 0xFFFF)

    for character in characters:
        entry = _entry_body(character)
        # The first byte of an entry is its size: the packed bytes that follow it.
        body.append(len(entry))
        body += entry

    # LandSandBoat leaves this at zero when there are no entries; the client reads zero as
    # "nothing to list" rather than as a header-only body.
    if characters:
        struct.pack_into("<H", body, 0x08, len(body))
    struct.pack_into("<B", body, 0x0A, 0x80 if final else 0x00)
    return bytes(body)


def result_packets(characters: list[dict], total: int, nonce: bytes, tail4: bytes) -> list[bytes]:
    """Split the matching characters into at most 40 visible results and encrypt them."""
    visible = characters[:MAX_RESULTS]
    packets = []
    offset = 0
    while True:
        chunk = visible[offset:offset + RESULTS_PER_PACKET]
        offset += len(chunk)
        final = offset >= len(visible)
        packets.append(encode_reply(_result_packet(chunk, total, final), nonce, tail4))
        if final:
            break
    return packets


class SearchServer:
    """One TCP connection handler for the search port."""

    def __init__(self, world):
        self.world = world

    def serve(self, conn, addr) -> None:
        log.info("search: %s connected", addr[0])
        buffer = bytearray()
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while len(buffer) >= 2:
                    size = struct.unpack_from("<H", buffer, 0)[0]
                    if size < 28 or size > REQUEST_MAX:
                        log.warning("search: %s sent a %d-byte packet", addr[0], size)
                        return
                    if len(buffer) < size:
                        break
                    packet = bytes(buffer[:size])
                    del buffer[:size]
                    try:
                        replies = self.handle(packet, addr)
                    except Exception:  # one bad search must not drop the whole connection
                        log.exception("search: %s could not answer a request", addr[0])
                        continue
                    for reply in replies:
                        conn.sendall(reply)
        except OSError as exc:
            log.debug("search: %s: %s", addr[0], exc)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def handle(self, packet: bytes, addr=None) -> list[bytes]:
        decoded = decode_request(packet)
        if decoded is None:
            log.warning("search: %s sent an invalid packet", addr[0] if addr else "?")
            return []
        plain, nonce, tail4 = decoded
        kind = plain[0x0B] if len(plain) > 0x0B else -1
        if kind not in SEARCH_TYPES:
            log.debug("search: ignoring request type 0x%02X", kind)
            return []

        query = parse_query(plain)
        characters = matching_characters(self.world, query)
        total = len(characters)
        log.info("search: %s: %s -> %d online match%s", addr[0] if addr else "?",
                 SEARCH_TYPES[kind], total, "" if total == 1 else "es")
        return result_packets(characters, total, nonce, tail4)
