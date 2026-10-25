"""The search server: /sea all and /sea <name>.

The wire format is the one the retail client speaks to its search service.  These tests drive
the same packets a client would: a bit-packed request under the client's Blowfish, and the
packed search list that comes back.
"""
from __future__ import annotations

import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.cipher import Blowfish, md5
from fanxi_server.game.search import (
    FLAGS1,
    JOB,
    LEVEL,
    NAME,
    NATION,
    RACE,
    SEARCH_KEY,
    TCP_SEARCH,
    TCP_SEARCH_ALL,
    SearchQuery,
    SearchServer,
    _BitWriter,
    _Bits,
    _entry_body,
    decode_request,
    encode_reply,
    matching_characters,
    parse_query,
    result_packets,
)
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

NO_SORT_BITS = (0x0B, 0x0C, 0x11, 0x13, 0x14, 0x16, 0x18)


def pack_query(*entries: tuple[int, list[tuple[int, int]]]) -> bytes:
    """A request query: each entry is (SearchType, [(value, width), ...])."""
    writer = _BitWriter(bytearray())
    for kind, fields in entries:
        writer.write(kind, 5)
        if kind not in NO_SORT_BITS:
            writer.write(0, 1)  # ascending
            writer.write(1, 1)  # present
        for value, width in fields:
            writer.write(value, width)
    writer.align()
    return bytes(writer.data)


def make_request(kind: int, query: bytes, nonce: bytes = b"\x11\x22\x33\x44",
                 tail: bytes = b"\0\0\0\0") -> bytes:
    """Build the encrypted request the client sends to the search service."""
    body = bytearray(0x11)
    body[0x0B] = kind
    body[0x10] = len(query)
    body += query
    body += tail

    packet = bytearray(body)
    packet += bytes(16)
    packet += nonce
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[len(body):len(body) + 16] = md5(bytes(packet[8:len(body)]))

    cipher = Blowfish(md5(SEARCH_KEY + nonce))
    words = (len(packet) - 12) // 4
    words -= words % 2
    cipher.run(packet, 8, words, enc=True)
    return bytes(packet)


def decrypt_reply(packet: bytes, nonce: bytes, tail: bytes) -> bytes:
    """Open a reply the way the client does, returning the packed body."""
    buf = bytearray(packet)
    cipher = Blowfish(md5(SEARCH_KEY + nonce + tail))
    words = (len(buf) - 12) // 4
    words -= words % 2
    cipher.run(buf, 8, words, enc=False)
    assert md5(bytes(buf[8:len(buf) - 20])) == bytes(buf[len(buf) - 20:len(buf) - 4])
    return bytes(buf[:len(buf) - 20])


def recv_exact(sock: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise AssertionError("connection closed after %d of %d bytes" % (len(data), count))
        data += chunk
    return data


class SearchQueryTest(unittest.TestCase):
    def decode(self, packet: bytes) -> SearchQuery:
        decoded = decode_request(packet)
        self.assertIsNotNone(decoded)
        plain, _nonce, _tail = decoded
        return parse_query(plain)

    def test_name_request_round_trips_through_the_cipher(self):
        query = pack_query((NAME, [(4, 5)] + [(ord(ch), 7) for ch in "Fanx"]))
        packet = make_request(TCP_SEARCH, query)
        decoded = decode_request(packet)
        self.assertIsNotNone(decoded)
        plain, nonce, tail = decoded
        self.assertEqual(nonce, b"\x11\x22\x33\x44")
        self.assertEqual(tail, b"\0\0\0\0")
        parsed = parse_query(plain)
        self.assertEqual(parsed.kind, TCP_SEARCH)
        self.assertEqual(parsed.name, "Fanx")

    def test_query_filters_and_sort_are_read(self):
        query = pack_query(
            (JOB, [(6, 5)]),
            (LEVEL, [(10, 8), (75, 8)]),
            (NATION, [(2, 2)]),
            (RACE, [(3, 4)]),
            (FLAGS1, [(0x20, 16)]),
        )
        parsed = self.decode(make_request(TCP_SEARCH_ALL, query))
        self.assertEqual(parsed.kind, TCP_SEARCH_ALL)
        self.assertEqual(parsed.job, 6)
        self.assertEqual((parsed.min_level, parsed.max_level), (10, 75))
        self.assertEqual(parsed.nation, 2)
        self.assertEqual(parsed.race, 3)
        self.assertEqual(parsed.flags, 0x20)
        self.assertEqual([kind for kind, _desc in parsed.sort], [JOB, LEVEL, NATION, RACE, FLAGS1])

    def test_short_query_is_not_an_error(self):
        parsed = self.decode(make_request(TCP_SEARCH_ALL, b""))
        self.assertEqual(parsed.name, "")
        self.assertEqual(parsed.zones, [])

    def test_bad_request_is_rejected(self):
        packet = bytearray(make_request(TCP_SEARCH, b""))
        packet[-1] ^= 0xFF  # break the unencrypted nonce
        self.assertIsNone(decode_request(bytes(packet)))


class SearchReplyTest(unittest.TestCase):
    def character(self, **overrides):
        character = {
            "name": "Fanxi", "char_id": 1, "id": 1, "main_job": 20, "main_level": 99,
            "sub_job": 0, "sub_level": 0, "nation": 0, "race": 1, "zone": 246,
            "rank_sandoria": 1, "rank_bastok": 1, "rank_windurst": 1,
        }
        character.update(overrides)
        return character

    def test_entry_layout_matches_the_reference_bytes(self):
        # The same entity packed by LandSandBoat's CSearchListPacket.
        self.assertEqual(
            _entry_body(self.character()).hex(),
            "02c6c3bbc6909ec20740118c00a3001300002000005c00000001600000000b800080",
        )

    def test_reply_encrypts_and_stays_readable(self):
        entry = _entry_body(self.character(char_id=0x01000001))
        body = bytearray(0x18)
        body += bytes([len(entry)]) + entry
        struct.pack_into("<H", body, 0x08, len(body))
        struct.pack_into("<H", body, 0x0E, 1)
        struct.pack_into("<B", body, 0x0A, 0x80)
        struct.pack_into("<B", body, 0x0B, 0x80)
        nonce, tail = b"\x01\x02\x03\x04", b"\x05\x06\x07\x08"
        packet = encode_reply(bytes(body), nonce, tail)
        opened = decrypt_reply(packet, nonce, tail)
        # The size and "IXFF" fields are written by encode_reply, outside the cipher.
        self.assertEqual(opened[8:], bytes(body)[8:])
        self.assertEqual(struct.unpack_from("<H", opened, 0)[0], len(packet))
        self.assertEqual(opened[4:8], b"IXFF")
        self.assertEqual(struct.unpack_from("<H", packet, 0)[0], len(packet))

    def test_results_are_split_into_packets_with_one_final_flag(self):
        characters = [{
            "name": "P%02d" % index, "char_id": 0x01000001 + index, "id": index + 1,
            "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0, "nation": 0,
            "race": 1, "zone": 100, "rank_sandoria": 1,
        } for index in range(25)]
        nonce, tail = b"\x01\x02\x03\x04", b"\0\0\0\0"
        packets = result_packets(characters, len(characters), nonce, tail)
        self.assertEqual(len(packets), 2)
        finals, counts = [], []
        for packet in packets:
            body = decrypt_reply(packet, nonce, tail)
            self.assertEqual(struct.unpack_from("<H", body, 0x0E)[0], 25)
            finals.append(body[0x0A])
            end = struct.unpack_from("<H", body, 0x08)[0]
            position, count = 0x18, 0
            while position < end:
                position += 1 + body[position]
                count += 1
            counts.append(count)
        self.assertEqual(finals, [0x00, 0x80])
        self.assertEqual(counts, [20, 5])

    def test_no_matches_still_send_one_final_packet(self):
        nonce, tail = b"\x01\x02\x03\x04", b"\0\0\0\0"
        packets = result_packets([], 0, nonce, tail)
        self.assertEqual(len(packets), 1)
        body = decrypt_reply(packets[0], nonce, tail)
        self.assertEqual(struct.unpack_from("<H", body, 0x0E)[0], 0)
        self.assertEqual(body[0x0A], 0x80)


class SearchWorldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.world = World(self.config, self.service, None)

    def character(self, name, zone, port, logged_in=True, sleeping=False):
        account = self.service.register("acct%d" % port, "password123").account
        created = self.service.create_character(account["id"], {
            "name": name, "race": 1, "face": 1, "size": 1, "nation": 0, "main_job": 1,
        })
        record = self.service.character_record(self.service.character(created["id"]), "Fanxi")
        session = ZoneSession(self.world, ("127.0.0.1", port), record)
        session.set_key(bytes(20))
        session.logged_in = logged_in
        session.sleeping = sleeping
        session.zone = zone
        self.world.sessions[("127.0.0.1", port)] = session
        return session

    def test_all_lists_online_characters_with_their_live_zone(self):
        self.character("Alpha", 246, 5001)
        self.character("Beta", 100, 5002)
        self.character("Sleepy", 230, 5003, sleeping=True)
        self.character("Offline", 246, 5004, logged_in=False)

        found = matching_characters(self.world, SearchQuery(kind=TCP_SEARCH_ALL))
        self.assertEqual([c["name"] for c in found], ["Alpha", "Beta", "Sleepy"])
        self.assertEqual({c["name"]: c["zone"] for c in found},
                         {"Alpha": 246, "Beta": 100, "Sleepy": 230})

    def test_name_search_is_a_case_insensitive_prefix(self):
        self.character("Twodough", 100, 5001)
        self.character("Onedough", 246, 5002)
        found = matching_characters(self.world, SearchQuery(name="two"))
        self.assertEqual([c["name"] for c in found], ["Twodough"])
        found = matching_characters(self.world, SearchQuery(name="DOUGH"))
        self.assertEqual(found, [])
        # `/sea twodough` also sends the searcher's current area as an implicit condition.
        # A name search must still find the character in another zone.
        found = matching_characters(self.world, SearchQuery(name="two", zones=[246]))
        self.assertEqual([c["name"] for c in found], ["Twodough"])

    def test_filters_narrow_the_online_list(self):
        self.character("Alpha", 246, 5001)
        self.character("Beta", 100, 5002)
        query = SearchQuery(zones=[100], job=1, min_level=1, max_level=99, nation=0, race=0)
        found = matching_characters(self.world, query)
        self.assertEqual([c["name"] for c in found], ["Beta"])


class SearchSocketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.world = World(self.config, self.service, None)
        self.server = SearchServer(self.world)
        account = self.service.register("socketa", "password123").account
        created = self.service.create_character(account["id"], {
            "name": "Twodough", "race": 1, "face": 1, "size": 1, "nation": 0, "main_job": 1,
        })
        self.record = self.service.character_record(
            self.service.character(created["id"]), "Fanxi")
        session = ZoneSession(self.world, ("127.0.0.1", 5999), self.record)
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = 100
        self.world.sessions[("127.0.0.1", 5999)] = session
        self.entry = dict(self.record, zone=100)

    def test_search_over_tcp_returns_the_zone(self):
        server_sock, client_sock = socket.socketpair()
        thread = threading.Thread(target=self.server.serve,
                                  args=(server_sock, ("127.0.0.1", 0)), daemon=True)
        thread.start()
        try:
            query = pack_query((NAME, [(8, 5)] + [(ord(ch), 7) for ch in "Twodough"]))
            nonce, tail = b"\xA1\xB2\xC3\xD4", b"\0\0\0\0"
            client_sock.sendall(make_request(TCP_SEARCH, query, nonce=nonce, tail=tail))
            client_sock.settimeout(5)
            header = recv_exact(client_sock, 2)
            size = struct.unpack("<H", header)[0]
            body = decrypt_reply(header + recv_exact(client_sock, size - 2), nonce, tail)
            self.assertEqual(struct.unpack_from("<H", body, 0x0E)[0], 1)
            entry = _entry_body(self.entry)
            self.assertEqual(body[0x18 + 1:0x18 + 1 + len(entry)], entry)
        finally:
            client_sock.close()
            server_sock.close()

    def test_two_framed_requests_are_both_answered(self):
        server_sock, client_sock = socket.socketpair()
        thread = threading.Thread(target=self.server.serve,
                                  args=(server_sock, ("127.0.0.1", 0)), daemon=True)
        thread.start()
        try:
            nonce, tail = b"\x01\x02\x03\x04", b"\0\0\0\0"
            first = make_request(TCP_SEARCH_ALL, b"", nonce=nonce, tail=tail)
            second = make_request(TCP_SEARCH_ALL, b"", nonce=nonce, tail=tail)
            client_sock.sendall(first + second)
            client_sock.settimeout(5)
            for _ in range(2):
                header = recv_exact(client_sock, 2)
                size = struct.unpack("<H", header)[0]
                body = decrypt_reply(header + recv_exact(client_sock, size - 2), nonce, tail)
                self.assertEqual(struct.unpack_from("<H", body, 0x0E)[0], 1)
        finally:
            client_sock.close()
            server_sock.close()

    def test_all_returns_an_empty_final_list_when_nothing_is_online(self):
        self.world.sessions.clear()
        nonce, tail = b"\x01\x02\x03\x04", b"\0\0\0\0"
        replies = self.server.handle(make_request(TCP_SEARCH_ALL, b"", nonce=nonce, tail=tail),
                                     ("127.0.0.1", 0))
        self.assertEqual(len(replies), 1)
        body = decrypt_reply(replies[0], nonce, tail)
        self.assertEqual(struct.unpack_from("<H", body, 0x0E)[0], 0)
        self.assertEqual(struct.unpack_from("<H", body, 0x08)[0], 0)  # no entries
        self.assertEqual(body[0x0A], 0x80)  # final


if __name__ == "__main__":
    unittest.main()
