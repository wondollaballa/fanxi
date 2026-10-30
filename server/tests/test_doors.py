"""Doors: retail's manual door, the optional automatic mode, and the drawbridge.

Port Bastok's drawbridge is a moving structure, not a door the player opens.  Its three
entities spawn lowered and stay lowered: the airship arrival that raises them is not
implemented, so raising them on a blind timer only trapped players under a bridge with no
ship to explain it.  The automatic-door mode must never touch it either.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

DRAWBRIDGE = ("_6ke", "_6ks", "_6kt")
DRAWBRIDGE_SPAN = "_6ke"
OPEN_DOOR = 8    # lowered / walkable
CLOSE_DOOR = 9   # raised / closed


class DoorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(
            account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.zone(236)

    def zone(self, zone_id: int):
        self.session.zone = zone_id
        self.session.pos = list(self.world.zones.position(zone_id))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def door(self, name: str):
        return next(entity for entity in self.session.entities
                    if str(entity.name) == name)

    def chats(self) -> list[str]:
        return [bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace")
                for message in self.session.queue
                if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x017]

    def msg_types(self) -> list[int]:
        return [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                for message in self.session.queue]

    def test_only_city_and_outdoor_zones_allow_automatic_doors(self):
        self.assertTrue(self.world.zones.allows_auto_doors(236))   # Port Bastok
        self.assertTrue(self.world.zones.allows_auto_doors(246))   # Port Jeuno
        self.assertFalse(self.world.zones.allows_auto_doors(56))   # Hanging Bridge
        self.assertFalse(self.world.zones.allows_auto_doors(258))  # Rala Waterways

    def test_a_normal_door_stays_shut_unless_the_mode_is_on(self):
        door = self.door('Door:"Steaming Sheep"')
        self.session.pos = [door.x, door.y, door.z, 0]
        self.session.auto_open_doors = False
        self.session.open_nearby_doors()
        self.assertNotEqual(int(door.animation), 8)
        self.assertEqual(self.session.door_close_at, 0.0)

        self.session.auto_open_doors = True
        self.session.open_nearby_doors()
        self.assertEqual(int(door.animation), 8)
        self.assertGreater(self.session.door_close_at, 0.0)
        self.assertIn(int(door.targid), self.session.opened_doors)

    def test_automatic_doors_skip_dungeon_zones(self):
        # The mode follows the character, but a dungeon's zone flag keeps its doors
        # manual even with the option on.
        self.session.auto_open_doors = True
        self.session.zone = 56
        self.assertFalse(self.world.zones.allows_auto_doors(self.session.zone))

    def test_the_drawbridge_spawns_lowered_and_does_not_open(self):
        for name in DRAWBRIDGE:
            door = self.door(name)
            self.assertEqual(door.door_kind, "drawbridge")
            self.assertEqual(int(door.animation), OPEN_DOOR)

        span = self.door(DRAWBRIDGE_SPAN)
        self.session.pos = [span.x, span.y, span.z, 0]
        self.session.auto_open_doors = True
        self.session.open_nearby_doors()
        self.assertEqual(int(span.animation), OPEN_DOOR)

        self.session.queue.clear()
        self.session.talk_to_door(span)
        self.assertEqual(int(span.animation), OPEN_DOOR)
        self.assertIn("The drawbridge is down and cannot be raised by hand.",
                      self.chats())

        span.animation = CLOSE_DOOR
        self.session.queue.clear()
        self.session.talk_to_door(span)
        self.assertIn("The drawbridge is up. Wait for it to lower.", self.chats())
        self.assertEqual(int(span.animation), CLOSE_DOOR)

    def test_the_drawbridge_never_raises_on_its_own(self):
        """No airship arrival exists, so there is no timer to catch a player on it.

        The old six-minute raise also started client event 70 on anyone on the deck;
        when that event did not finish, the client kept the cutscene camera and the
        character appeared stuck.  The bridge must stay down until a real arrival drives
        it, and nothing may start event 70 from the world tick.
        """
        for now in (4.0, 5.0, 9.0, 13.0, 80.0, 85.0, 89.0, 360.0):
            self.world.advance(now)
            for name in DRAWBRIDGE:
                self.assertEqual(int(self.door(name).animation), OPEN_DOOR)
        self.session.queue.clear()
        self.world.advance(5.0)
        self.assertNotIn(0x034, self.msg_types())

    def test_the_automatic_door_setting_is_saved_per_character(self):
        self.session.queue.clear()
        self.session.command("doors auto on".split())
        self.assertTrue(self.session.auto_open_doors)
        self.assertEqual(
            self.service.character_setting(int(self.character["id"]), "auto_open_doors"),
            "1")

        other = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.assertTrue(other.auto_open_doors)

        self.session.command("doors auto off".split())
        self.assertFalse(self.session.auto_open_doors)
        self.assertEqual(
            self.service.character_setting(int(self.character["id"]), "auto_open_doors"),
            "0")


if __name__ == "__main__":
    unittest.main()
