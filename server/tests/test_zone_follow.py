"""The boxes behind a leader run the same zone line the leader crossed.

A client only asks for a zone when its own character steps on a line (``C2S 0x05E``), so a
box that is following its leader does not always produce one: the leader's client loads the
new zone and the boxes are left standing in the old one.  Fanxi moves the account family
behind the leader instead, one ``0x00B`` per client, handed out together on the next tick so
the whole team is in the new zone at the same time.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def chats(session) -> list[str]:
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


def msg_types(session) -> list[int]:
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def zone_line_packet(rect: int) -> bytes:
    packet = bytearray(0x18)
    struct.pack_into("<I", packet, 4, int(rect))
    return bytes(packet)


class ZoneFollowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Fanxi", "race": 1})
        self.sub = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Tinybox", "race": 1}})
        self.second = self.service.create_sub_account(
            self.account["id"], {"character": {"name": "Secondbox", "race": 1}})
        self.world = World(self.config, self.service, None)
        self.session = self.make_session(self.character, ("127.0.0.1", 1201), 100)
        self.sub_session = self.make_session(
            self.sub["character"], ("127.0.0.1", 1202), 100)
        self.second_session = self.make_session(
            self.second["character"], ("127.0.0.1", 1203), 100)

    def make_session(self, character, addr, zone):
        session = ZoneSession(
            self.world, addr,
            self.service.character_record(self.service.character(character["id"]), "Fanxi"))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = int(zone)
        session.pos = list(self.world.zones.position(int(zone)))
        session.load_zone_entities()
        session.zone_loaded = True
        session.last_packet_at = time.time()
        self.world.sessions[addr] = session
        session.queue.clear()
        return session

    def zone_line(self):
        """A real authored line that is not a Mog House door and changes zone."""
        for rect, line in sorted(self.world.zones.lines.items()):
            name = rect.to_bytes(4, "little")
            if name == b"zmrq" or name[:3] in (b"zmr", b"zms"):
                continue
            if int(line[0]) == 100:
                continue
            return rect, line
        self.skipTest("the test database has no ordinary zone line")

    def cross(self, session, rect):
        session.queue.clear()
        session.handle(0x05E, zone_line_packet(rect))

    def test_the_leader_zones_at_once_and_the_boxes_follow_together(self) -> None:
        rect, line = self.zone_line()
        zone, x, y, z, rot = int(line[0]), *line[1:]
        destination = [x, y, z, int(rot)]

        self.cross(self.session, rect)

        # The leader runs its own hand-off immediately.
        self.assertEqual(self.session.zone, zone)
        self.assertEqual(self.session.pos, destination)
        self.assertTrue(self.session.zoning)
        self.assertTrue(any(getattr(message, "zone_out", False)
                            for message in self.session.queue))
        # The boxes are collected while they are still standing in the old zone; the
        # queue hands them out on the next ticks, half a second apart, so one lost
        # 0x00B cannot take the rest of the team down with it.
        for follower in (self.sub_session, self.second_session):
            self.assertEqual(follower.zone, 100)
            self.assertFalse(follower.zoning)
        self.assertEqual(len(self.world.pending_warps), 2)

        self.world.advance(time.time())
        self.world.advance(time.time() + 0.6)
        self.assertEqual(self.world.pending_warps, [])
        for follower in (self.sub_session, self.second_session):
            self.assertEqual(follower.zone, zone)
            self.assertEqual(follower.pos, destination)
            self.assertTrue(follower.zoning)
            self.assertIn(0x00B, msg_types(follower))
            self.assertTrue(any(getattr(message, "zone_out", False)
                                for message in follower.queue))
            self.assertIn("Fanxi leads you into %s." % self.world.zones.name(zone),
                          chats(follower))

    def test_a_box_follows_the_line_it_was_standing_next_to(self) -> None:
        """The queue moves the exact characters that were in the leader's old zone."""
        rect, line = self.zone_line()
        zone = int(line[0])
        # A box parked in another zone is not part of this line's walk.
        self.second_session.zone = 246
        self.second_session.pos = list(self.world.zones.position(246))

        self.cross(self.session, rect)
        self.world.advance(time.time())

        self.assertEqual(self.session.zone, zone)
        self.assertEqual(self.sub_session.zone, zone)
        self.assertEqual(self.second_session.zone, 246)
        self.assertFalse(self.second_session.zoning)

    def test_a_single_box_follows_with_the_leader(self) -> None:
        rect, line = self.zone_line()
        zone = int(line[0])
        self.second_session.sleeping = True

        self.cross(self.session, rect)
        self.assertEqual(self.sub_session.zone, 100)
        self.assertFalse(self.sub_session.zoning)

        self.world.advance(time.time())
        self.assertEqual(self.sub_session.zone, zone)
        self.assertTrue(self.sub_session.zoning)
        self.assertEqual(self.second_session.zone, 100)
        self.assertEqual(self.world.pending_warps, [])

    def test_leaving_the_mog_house_does_not_zone_the_boxes(self) -> None:
        """The Mog House door is not a team zone line.

        The leader stepping out used to hand every box a 0x00B for the city they were
        already in; a box whose client missed it went silent and was reaped.  The door
        must leave the boxes where they are.
        """
        self.session.zone = 100
        self.session.char["moghouse"] = 1
        self.sub_session.zone = 100
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.queue.clear()
        self.session.leave_moghouse(100)
        self.assertFalse(self.sub_session.zoning)
        self.assertNotIn(0x00B, msg_types(self.sub_session))

    def test_a_box_that_zones_itself_is_not_handed_out_again(self) -> None:
        """The follow controller can walk a box through the line before the gate opens.

        Its own 0x05E already moved it, so the queued follow must be dropped rather than
        reloading a box that is standing at the destination.
        """
        rect, line = self.zone_line()
        zone = int(line[0])
        self.cross(self.session, rect)

        # The box reached the line itself while the leader was still loading.
        self.sub_session.handle(0x05E, zone_line_packet(rect))
        self.assertEqual(self.sub_session.zone, zone)
        self.assertTrue(self.sub_session.zoning)
        self.sub_session.zoning = False
        self.sub_session.zone_loaded = True
        self.sub_session.queue.clear()

        self.world.advance(time.time())

        self.assertFalse(self.sub_session.zoning)
        self.assertNotIn(0x00B, msg_types(self.sub_session))
        self.assertEqual(chats(self.sub_session), [])
        self.assertEqual(self.second_session.zone, zone)
        self.assertEqual(self.world.pending_warps, [])

    def test_a_sub_that_crosses_alone_does_not_drag_the_main(self) -> None:
        """Only the main account leads the family; a box zoning alone goes by itself."""
        rect, line = self.zone_line()
        zone = int(line[0])
        self.session.queue.clear()

        self.cross(self.sub_session, rect)

        self.assertEqual(self.sub_session.zone, zone)
        self.assertTrue(self.sub_session.zoning)
        self.assertEqual(self.session.zone, 100)
        self.assertFalse(self.session.zoning)
        self.assertEqual(self.second_session.zone, 100)
        self.assertEqual(self.world.pending_warps, [])

    def test_another_accounts_character_is_not_dragged_through_the_line(self) -> None:
        rect, line = self.zone_line()
        zone = int(line[0])
        other = self.service.register("other", "password123").account
        other_character = self.service.create_character(
            other["id"], {"name": "Notmine", "race": 1})
        other_session = self.make_session(other_character, ("127.0.0.1", 1204), 100)

        self.cross(self.session, rect)
        self.world.advance(time.time())

        self.assertEqual(self.session.zone, zone)
        self.assertEqual(self.sub_session.zone, zone)
        self.assertEqual(other_session.zone, 100)
        self.assertFalse(other_session.zoning)

    def test_the_leader_zones_even_with_no_boxes_online(self) -> None:
        rect, line = self.zone_line()
        zone = int(line[0])
        self.sub_session.logged_in = False
        self.second_session.zone = 246

        self.cross(self.session, rect)

        self.assertEqual(self.session.zone, zone)
        self.assertTrue(self.session.zoning)
        self.assertEqual(self.world.pending_warps, [])


if __name__ == "__main__":
    unittest.main()
