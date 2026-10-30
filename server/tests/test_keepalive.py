"""An idle zone session must not go silent: the client calls that FFXI-4001.

The client sends 0x015 while it stands still and treats a server that never answers as
a dead link.  A city with nothing moving is exactly that quiet, so every live session
gets a General-only 0x00D keepalive when nothing else has gone out.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import IDLE_HEARTBEAT, ZoneSession


def message_type(message) -> int:
    return struct.unpack_from("<H", message, 0)[0] & 0x1FF


def general_updates(session) -> list[bytes]:
    """0x00D messages whose mask is the General-only (0x04) keepalive."""
    found = []
    for message in session.queue:
        if message_type(message) != 0x00D:
            continue
        body = message[4:]
        if len(body) >= 7 and body[6] == packets.SEND_HP:
            found.append(message)
    return found


class KeepaliveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config, db, service = make_service(Path(self.tmp.name))
        self.world = World(config, service, None)
        account = service.register("idle", "password123").account
        character = service.create_character(
            account["id"], {"name": "Idle", "race": 1, "face": 1, "size": 1,
                            "nation": 0, "main_job": 1})
        record = service.character_record(service.character(character["id"]), "Fanxi")
        self.session = ZoneSession(self.world, ("127.0.0.1", 5001), record)
        self.session.set_key(bytes(20))
        self.session.char["char_id"] = int(record["char_id"])
        self.session.targid = self.world.assign_player_targid(int(record["char_id"]))
        self.session.logged_in = True
        self.session.zone = 234
        self.session.pos = [116.0, 1.0, -60.0, 0]
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        self.session.entities_sent = True
        self.session.queue.clear()
        self.world.sessions[("127.0.0.1", 5001)] = self.session

    def quiet(self, now: float) -> None:
        """No entity or player sweep, so only the keepalive can add a 0x00D."""
        self.session.next_entity_sync = now + 100.0
        self.session.next_player_sync = now + 100.0

    def test_idle_session_gets_a_general_update(self):
        now = time.time()
        self.session.last_sent_at = now - (IDLE_HEARTBEAT + 1.0)
        self.quiet(now)
        self.session.tick(now)
        updates = general_updates(self.session)
        self.assertEqual(len(updates), 1)
        body = updates[0][4:]
        # 0x44 is the General-only body: the model and name blocks are not re-sent, so
        # the client does not reset the entity or drop the drawn-weapon pose.
        self.assertEqual(len(body), 0x44)
        self.assertEqual(struct.unpack_from("<H", body, 4)[0], 0x400)
        self.assertEqual(self.session.idle_heartbeat_at, now)

    def test_recent_traffic_suppresses_the_heartbeat(self):
        now = time.time()
        self.session.last_sent_at = now - 1.0
        self.quiet(now)
        self.session.tick(now)
        self.assertEqual(general_updates(self.session), [])

    def test_a_session_out_of_the_world_gets_no_heartbeat(self):
        now = time.time()
        self.session.last_sent_at = now - (IDLE_HEARTBEAT + 1.0)
        self.session.logged_in = False
        self.quiet(now)
        self.session.tick(now)
        self.assertEqual(general_updates(self.session), [])

    def test_a_zoning_session_gets_no_heartbeat(self):
        now = time.time()
        self.session.last_sent_at = now - (IDLE_HEARTBEAT + 1.0)
        self.session.zoning = True
        self.quiet(now)
        self.session.tick(now)
        self.assertEqual(general_updates(self.session), [])

    def test_the_heartbeat_repeats_only_after_the_interval(self):
        now = time.time()
        self.session.last_sent_at = now - (IDLE_HEARTBEAT + 1.0)
        self.quiet(now)
        self.session.tick(now)
        self.session.tick(now + 1.0)
        self.assertEqual(len(general_updates(self.session)), 1)
        self.session.next_entity_sync = now + 100.0
        self.session.next_player_sync = now + 100.0
        self.session.tick(now + IDLE_HEARTBEAT + 1.0)
        self.assertEqual(len(general_updates(self.session)), 2)


if __name__ == "__main__":
    unittest.main()
