"""The zone's outbound queue: real events must never sit behind the entity stream.

A crowded zone generates several kilobytes a second of mob position updates.  The client
was built for a dial-up-era pipe, so those updates used to fill its receive buffer and a
job ability pressed in the middle of them appeared a minute later.  These tests pin the
three rules that keep the queue short and the reply first:

* one pending position per entity, always the newest;
* events (actions, status, chat) are packed before any entity move;
* the ambient stream is rate-limited by a byte budget.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_huffman_dir, make_service

from fanxi_server.game import packets
from fanxi_server.game.cipher import Huffman
from fanxi_server.game.entities import ZoneEntity
from fanxi_server.game.world import World
from fanxi_server.game.zone import (
    AMBIENT_BURST_BYTES, PACKET_BYTES, ZoneSession, sub,
)


def read_body(body: bytes) -> list[tuple[int, bytes]]:
    """Split a zone packet body into (type, message) the way the client reads it."""
    out = []
    offset = 0
    while offset + 4 <= len(body):
        head = struct.unpack_from("<H", body, offset)[0]
        size = (head >> 9) * 4
        if size == 0 or offset + size > len(body):
            break
        out.append((head & 0x1FF, bytes(body[offset:offset + size])))
        offset += size
    return out


class FakeUDP:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple]] = []

    def sendto(self, data, addr) -> None:
        self.sent.append((bytes(data), addr))


class ZoneTrafficTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.huff = Huffman.from_folder(make_huffman_dir(Path(self.tmp.name) / "huff"))
        self.world = World(self.config, self.service, self.huff)
        account = self.service.register("tester", "password123").account
        character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1, "main_job": 20})
        self.session = self.make_session(character, 5001)
        self.mob = ZoneEntity(
            kind="mob", id=0x01000001, targid=0x101, zone=246, name="Enchanted Bones",
            x=1.0, y=0.0, z=2.0, level=5, hp=100, hp_max=100)

    def make_session(self, character: dict, port: int) -> ZoneSession:
        record = self.service.character_record(
            self.service.character(character["id"]), "Fanxi")
        session = ZoneSession(self.world, ("127.0.0.1", port), record)
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = 246
        session.entities_sent = True
        session.zone_loaded = True
        session.client_hdr = bytes(28)
        session.queue.clear()
        self.world.sessions[("127.0.0.1", port)] = session
        return session

    def packed(self) -> list[tuple[int, bytes]]:
        """The sub-messages pack() would put in the next packet."""
        data, bits, _zone_out = self.session.pack()
        return read_body(self.huff.decompress(data, bits))

    def test_two_positions_for_one_mob_queue_only_the_newest(self) -> None:
        self.session.pos = [0.0, 0.0, 0.0, 0]
        self.mob.x, self.mob.z = 8.0, 9.0
        self.session.queue_entity(self.mob, packets.SEND_POSITION)
        self.mob.x, self.mob.z = 18.0, 19.0
        self.session.queue_entity(self.mob, packets.SEND_POSITION)

        updates = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E]
        self.assertEqual(len(updates), 1)
        x, y, z = struct.unpack_from("<fff", updates[0], 12)
        self.assertAlmostEqual(x, 18.0, places=2)
        self.assertAlmostEqual(z, 19.0, places=2)

    def test_a_job_ability_precedes_every_mob_update(self) -> None:
        """The action result and its status timer go out before the entity stream."""
        for index in range(30):
            mob = ZoneEntity(
                kind="mob", id=0x01000100 + index, targid=0x200 + index, zone=246,
                name="Bones %d" % index, x=float(index), y=0.0, z=float(index),
                level=5, hp=100, hp_max=100)
            self.session.queue_entity(mob, packets.SEND_POSITION)
        self.session.queue.append(sub(0x028, packets.battle_action(
            1, 1, 0, animation=171, message=packets.MESSAGE_USES_JOB_ABILITY, kind=2,
            category=packets.ACTION_CATEGORY_ABILITY_FINISH, action_id=211)))
        self.session.queue.append(self.session.char_status())

        types = [ptype for ptype, _body in self.packed()]
        self.assertEqual(types[0], 0x028, "the ability result must be first")
        self.assertEqual(types[1], 0x037, "the Light Arts icon list follows it")
        self.assertEqual(types[2], 0x063, "0x037 is always paired with its timers")
        self.assertIn(0x00E, types[3:], "ambient updates still go out, after the event")

    def test_the_ambient_stream_is_rate_limited(self) -> None:
        """One packet does not carry an unbounded mob stream."""
        for index in range(40):
            mob = ZoneEntity(
                kind="mob", id=0x01000200 + index, targid=0x300 + index, zone=246,
                name="Bones %d" % index, x=float(index), y=0.0, z=float(index),
                level=5, hp=100, hp_max=100)
            self.session.queue_entity(mob, packets.SEND_POSITION)
        self.session.ambient_tokens = float(AMBIENT_BURST_BYTES)

        packet = self.packed()
        ambient_bytes = sum(len(body) for ptype, body in packet if ptype == 0x00E)
        self.assertGreater(ambient_bytes, 0)
        self.assertLessEqual(ambient_bytes, AMBIENT_BURST_BYTES)
        self.assertLessEqual(sum(len(body) for _ptype, body in packet), PACKET_BYTES)
        self.assertGreater(len(self.session.queue), 0,
                           "the rest stays queued for the next packet")

    def test_flush_serves_an_idle_session_without_a_socket_timeout(self) -> None:
        """A busy box must not starve the others of their queued packets.

        The zone loop calls flush() on a timer now; the important property is that a
        session with a queued packet is served even though it sent nothing itself.
        """
        self.session.queue.append(self.session.char_status())
        self.world.udp = FakeUDP()
        self.session.last_sent_at = 0.0

        self.world.flush(time.time())
        self.assertEqual(len(self.world.udp.sent), 1)

        # The same session is not sent a second packet until FLUSH_INTERVAL has passed.
        self.world.flush(time.time())
        self.assertEqual(len(self.world.udp.sent), 1)

        self.session.queue.append(self.session.char_status())
        self.world.flush(time.time() + 1.0)
        self.assertEqual(len(self.world.udp.sent), 2)

    def test_a_walking_mob_is_corrected_four_times_a_second(self) -> None:
        """The client interpolates from the speed byte; don't send every tick."""
        self.session.pos = [0.0, 0.0, 0.0, 0]
        self.session.sent_targids.add(int(self.mob.targid))
        self.mob.moving = True
        self.mob.speed = 12                       # walk: 2 yalms/s

        self.world._mob_sync(self.mob, [self.session], 100.0)
        first = self.mob.last_sync_at
        self.assertEqual(first, 100.0)

        self.world._mob_sync(self.mob, [self.session], 100.1)
        self.assertEqual(self.mob.last_sync_at, first,
                         "a 100 ms tick is not a new correction")

        self.world._mob_sync(self.mob, [self.session], 100.26)
        self.assertEqual(self.mob.last_sync_at, 100.26)

    def test_a_turn_is_urgent_only_inside_the_near_range(self) -> None:
        """Near the player a corner is immediate; far away it waits for the budget."""
        far = self.make_session({"id": self.session.char["id"]}, 5002)
        self.session.pos = [0.0, 0.0, 0.0, 0]
        far.pos = [0.0, 0.0, 40.0, 0]
        for session in (self.session, far):
            session.sent_targids.add(int(self.mob.targid))
        self.mob.moving = True
        self.mob.pending_turn = True

        self.world._mob_sync(self.mob, [self.session, far], time.time())

        near_updates = [m for m in self.session.queue
                        if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x00E]
        far_updates = [m for m in far.queue
                       if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x00E]
        self.assertEqual(len(near_updates), 1)
        self.assertFalse(getattr(near_updates[0], "ambient", True))
        self.assertEqual(len(far_updates), 1)
        self.assertTrue(getattr(far_updates[0], "ambient", False))

    def test_a_mob_beyond_the_streaming_range_is_not_sent(self) -> None:
        """Spawning reaches 60 yalms; steady movement stops at 45."""
        self.session.pos = [0.0, 0.0, 50.0, 0]
        self.session.sent_targids.add(int(self.mob.targid))
        self.mob.moving = True
        self.mob.speed = 12

        self.world._mob_sync(self.mob, [self.session], 200.0)
        self.assertEqual(self.session.queue, [])

        # The stop still reaches every client that has the entity spawned, so it does
        # not keep walking forever at the edge of the screen.
        self.mob.moving = False
        self.world._mob_sync(self.mob, [self.session], 201.0, force=True)
        self.assertEqual(len(self.session.queue), 1)


if __name__ == "__main__":
    unittest.main()
