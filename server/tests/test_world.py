"""The populated world: content loading, spawn triggers, NPC talk, combat and quests."""
from __future__ import annotations

import json
import math
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import (
    augments, base_stats, capes, combat, content, effects, geomancy, merits,
    modifiers as mod, packets, rolls, skillchain, trust_ai,
)
from fanxi_server.game.world import SYNC_RANGE, World
from fanxi_server.game.zone import (
    ALL_CONTAINERS, TWO_HOUR_RECAST_BASE, ZoneSession, job_id, sub,
)


def msg_types(session):
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def action_animations(message: bytes) -> list[int]:
    """Every 0x028 result's animation, in order: 0 main hand, 1 off hand.

    A melee round is one action with one result per hand (Windower's ``action_count``),
    which is the order the client plays the swings in.
    """
    data = message[5:]

    def read(bit: int, width: int) -> int:
        value = 0
        for index in range(width):
            value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
        return value

    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32          # header and target id
    count = read(bit, 4)
    bit += 4
    animations = []
    for _ in range(count):
        bit += 3 + 2                              # resolution and kind
        animations.append(read(bit, 12))
        bit += 12 + 5 + 2 + 3 + 17 + 10 + 31 + 1 + 1
    return animations


def action_results(message: bytes) -> list[dict]:
    """The 0x028 results' animation, info, value and message id, in order."""
    data = message[5:]

    def read(bit: int, width: int) -> int:
        value = 0
        for index in range(width):
            value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
        return value

    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32          # header and target id
    count = read(bit, 4)
    bit += 4
    out = []
    for _ in range(count):
        out.append({"animation": read(bit + 5, 12),
                    "info": read(bit + 17, 5),
                    "value": read(bit + 27, 17),
                    "message": read(bit + 44, 10)})
        # 3 + 2 + 12 + 5 + 2 + 3 + 17 + 10 + 31, then the added-effect and
        # reaction flags (neither is set for a cast start).
        bit += 3 + 2 + 12 + 5 + 2 + 3 + 17 + 10 + 31 + 2
    return out


def action_additional_effects(message: bytes) -> list[dict | None]:
    """Each 0x028 result's additional-effect block, or None when the flag is clear.

    An en-spell rides on the melee result: ``proc`` is the element (1 fire .. 8 dark),
    ``value`` the extra damage and ``message`` 229 ("additional points of damage").
    """
    data = message[5:]

    def read(bit: int, width: int) -> int:
        value = 0
        for index in range(width):
            value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
        return value

    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32          # header and target id
    count = read(bit, 4)
    bit += 4
    out: list[dict | None] = []
    for _ in range(count):
        bit += 3 + 2 + 12 + 5 + 2 + 3 + 17 + 10 + 31
        if read(bit, 1):
            bit += 1
            out.append({"proc": read(bit, 6), "info": read(bit + 6, 4),
                        "value": read(bit + 10, 17), "message": read(bit + 27, 10)})
            bit += 6 + 4 + 17 + 10
        else:
            bit += 1
            out.append(None)
        if read(bit, 1):
            bit += 1 + 6 + 4 + 14 + 10
        else:
            bit += 1
    return out


def last_sync(session):
    """(state, container, flags) from the newest 0x01D, or None if none was queued."""
    for message in reversed(session.queue):
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01D:
            return struct.unpack_from("<BB2xI", message, 4)
    return None


def zone_line_packet(rect: bytes, mode: int = 0, exit_bit: int = 0) -> bytes:
    """A C2S 0x05E zone-line request, with the Mog House exit fields filled in."""
    packet = bytearray(0x18)
    struct.pack_into("<I", packet, 4, int.from_bytes(rect, "little"))
    packet[0x16] = exit_bit
    packet[0x17] = mode
    return bytes(packet)


def item_use_packet(slot: int, container: int = 0, item_num: int = 0) -> bytes:
    """A C2S 0x037 item-use request, with the client's real field layout."""
    body = struct.pack("<IIHBBI", 0, int(item_num), 0x400,
                       int(slot) & 0xFF, 0, int(container))
    return bytes(sub(0x037, body))


class WorldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.zone(246)

    def zone(self, zone_id):
        self.session.zone = zone_id
        self.session.pos = list(self.world.zones.position(zone_id))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def give(self, container, slot, item_id, quantity=1):
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, ?, ?, ?, ?)",
            (int(self.character["id"]), int(container), int(slot), int(item_id), int(quantity)))

    def chats(self):
        lines = []
        for message in self.session.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
                continue
            lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
        return lines

    def stored(self):
        return {int(row["item_id"]): (int(row["quantity"]), int(row["slip"]))
                for row in self.db.all(
                    "SELECT item_id, quantity, slip FROM char_storage WHERE character_id = ?",
                    (int(self.character["id"]),))}

    def locker_stored(self):
        return {int(row["item_id"]): int(row["quantity"])
                for row in self.db.all(
                    "SELECT item_id, quantity FROM char_locker WHERE character_id = ?",
                    (int(self.character["id"]),))}

    def talk(self, entity):
        self.session.pos = [entity.x, entity.y, entity.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, entity.id, entity.targid, packets.ACTION_TALK)
        self.session.queue.clear()
        self.session.action(bytes(packet))

    def attack(self, entity):
        self.session.pos = [entity.x, entity.y, entity.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, entity.id, entity.targid, packets.ACTION_ATTACK)
        self.session.action(bytes(packet))

    def test_content_is_seeded(self):
        npcs = self.service.npcs_for_zone(246)
        self.assertGreaterEqual(len(npcs), 100)
        self.assertTrue(any(npc["script"] == content.GUIDE_NPC for npc in npcs))
        self.assertGreaterEqual(len(self.service.monster_spawns_for_zone(100)), 6)
        self.assertEqual(self.service.quest_by_key("pest_control")["required_kills"], 3)
        inventory = self.service.inventory(self.character["id"])
        self.assertEqual(inventory[0]["quantity"], 1000)
        self.assertTrue(any(item["item_id"] == 16534 for item in inventory))

    def test_level_99_kill_sends_exemplar_points_message(self):
        """A Locus kill at 99 pays (20 + 4*dLVL) x 7 and prints message 809."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.char["jobs"] = {1: (99, 0)}
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.level = 130
        mob.name = "Locus Test Rarab"
        before_exp = int(self.session.char["exp"])
        self.session.queue.clear()
        self.world.kill_mob(self.session, mob, time.time())
        reward = None
        for message in self.session.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x02D:
                continue
            if struct.unpack_from("<H", message, 4 + 20)[0] == \
                    packets.MESSAGE_EXEMPLAR_POINTS_GAINED:
                reward = struct.unpack_from("<I", message, 4 + 12)[0]
        # effective level 119, dLVL 11: (20 + 44) x Locus 7 = 448.
        self.assertEqual(reward, 448)
        self.assertEqual(int(self.session.char["exemplar_points"]), 448)
        self.assertEqual(int(self.session.char["exp"]), before_exp)

    def test_a_second_exemplar_kill_inside_the_window_is_a_master_chain(self):
        """The second kill pays +2% and prints Master chain #1 (message 810)."""
        self.zone(100)
        self.db.execute("UPDATE characters SET main_level = 99 WHERE id = ?",
                        (int(self.character["id"]),))
        self.session.char["main_level"] = 99
        self.session.char["jobs"] = {1: (99, 0)}
        first, second = [entity for entity in self.session.entities
                         if entity.kind == "mob" and entity.alive][:2]
        for mob in (first, second):
            mob.level = 130
            mob.name = "Locus Test Rarab"
        self.session.queue.clear()
        self.world.kill_mob(self.session, first, 1000.0)
        self.session.queue.clear()
        self.world.kill_mob(self.session, second, 1010.0)
        reward = chain = None
        for message in self.session.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x02D:
                continue
            if struct.unpack_from("<H", message, 4 + 20)[0] == packets.MESSAGE_MASTER_CHAIN:
                reward = struct.unpack_from("<I", message, 4 + 12)[0]
                chain = struct.unpack_from("<I", message, 4 + 16)[0]
        # 448 x (1 + 0.02 x chain #1) = 456.96, floored to 456.
        self.assertEqual(reward, 456)
        self.assertEqual(chain, 1)
        self.assertEqual(int(self.session.char["exemplar_points"]), 448 + 456)

    def test_a_forty_five_second_gap_still_starts_the_master_chain(self):
        """A normal solo kill pace must chain: the first window is 60 s, not 30 s.

        The live 2026-10-29 session killed a Locus every 31-39 s and never saw chain #1.
        Retail's Master chain timer starts longer than its 30 s floor; only the floor
        was implemented, so the second kill fell outside the window every time.
        """
        self.zone(100)
        self.db.execute("UPDATE characters SET main_level = 99 WHERE id = ?",
                        (int(self.character["id"]),))
        self.session.char["main_level"] = 99
        self.session.char["jobs"] = {1: (99, 0)}
        first, second = [entity for entity in self.session.entities
                         if entity.kind == "mob" and entity.alive][:2]
        for mob in (first, second):
            mob.level = 130
            mob.name = "Locus Test Rarab"
        self.session.queue.clear()
        self.world.kill_mob(self.session, first, 1000.0)
        self.session.queue.clear()
        self.world.kill_mob(self.session, second, 1045.0)
        reward = chain = None
        for message in self.session.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x02D:
                continue
            if struct.unpack_from("<H", message, 4 + 20)[0] == packets.MESSAGE_MASTER_CHAIN:
                reward = struct.unpack_from("<I", message, 4 + 12)[0]
                chain = struct.unpack_from("<I", message, 4 + 16)[0]
        self.assertEqual(reward, 456)
        self.assertEqual(chain, 1)

    def test_a_kill_past_the_first_window_restarts_at_chain_zero(self):
        """The 60 s first window is not a free pass: 61 s later is a fresh chain #0."""
        self.zone(100)
        self.db.execute("UPDATE characters SET main_level = 99 WHERE id = ?",
                        (int(self.character["id"]),))
        self.session.char["main_level"] = 99
        self.session.char["jobs"] = {1: (99, 0)}
        first, second = [entity for entity in self.session.entities
                         if entity.kind == "mob" and entity.alive][:2]
        for mob in (first, second):
            mob.level = 130
            mob.name = "Locus Test Rarab"
        self.session.queue.clear()
        self.world.kill_mob(self.session, first, 1000.0)
        self.session.queue.clear()
        self.world.kill_mob(self.session, second, 1061.0)
        messages = [struct.unpack_from("<H", message, 4 + 20)[0]
                    for message in self.session.queue
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x02D]
        self.assertIn(packets.MESSAGE_EXEMPLAR_POINTS_GAINED, messages)
        self.assertNotIn(packets.MESSAGE_MASTER_CHAIN, messages)

    def test_character_model_command_changes_and_repaints(self):
        self.session.queue.clear()
        self.session.command("character model hume 8".split())
        row = self.db.one(
            "SELECT race, face, hair, size FROM characters WHERE id = ?",
            (int(self.character["id"]),))
        self.assertEqual(tuple(row), (1, 2, 0, 1))
        self.assertEqual((self.session.char["face"], self.session.char["hair"]), (2, 0))
        kinds = msg_types(self.session)
        self.assertIn(0x051, kinds)   # grap list
        self.assertIn(0x067, kinds)   # self level block
        self.assertIn(0x01B, kinds)   # general information
        self.assertTrue(any("Hume male, Face 2, Hair A, Medium" in line
                            for line in self.chats()))

        # Random within a named race keeps that race.
        self.session.command("character model mithra random".split())
        row = self.db.one(
            "SELECT race, face, hair, size FROM characters WHERE id = ?",
            (int(self.character["id"]),))
        self.assertEqual(row["race"], 7)
        self.assertIn(row["face"], range(1, 9))
        self.assertIn(row["hair"], (0, 1))
        self.assertIn(row["size"], (0, 1, 2))

        # The detailed form names each part.
        self.session.queue.clear()
        self.session.command("character model elvaan face 3 hair b size l".split())
        row = self.db.one(
            "SELECT race, face, hair, size FROM characters WHERE id = ?",
            (int(self.character["id"]),))
        self.assertEqual(tuple(row), (3, 3, 1, 2))
        self.assertTrue(any("Elvaan male, Face 3, Hair B, Large" in line
                            for line in self.chats()))

        # Bad input leaves the row alone.
        self.session.command("character model hume face 99".split())
        row = self.db.one(
            "SELECT race, face, hair, size FROM characters WHERE id = ?",
            (int(self.character["id"]),))
        self.assertEqual(tuple(row), (3, 3, 1, 2))
        self.assertTrue(self.chats())

    def test_zone_in_packet_sizes(self):
        self.assertEqual(len(self.session.login_packet()), 260)
        self.assertEqual(len(self.session.job_info()), 132)
        self.assertEqual(len(self.session.char_status()), 120)
        self.assertEqual(len(self.session.char_update()), 108)
        self.assertEqual(len(self.session.char_stats()), 112)
        self.assertEqual(len(self.session.party_member()), 40)
        self.assertEqual(len(self.session.item_max()), 100)

    def test_status_packet_advertises_mog_wardrobes_three_to_eight(self):
        """The 0x037 status byte 0x5C enables Wardrobes 3-8; 0x01C does not.

        The client only offers (and only lists) the paid Mog Wardrobes whose bit is set
        in the status packet.  With the byte zero, their item lists drew blank in the
        equipment window although the bag held the items; Wardrobes 1-2 are not gated.
        Bits: Wardrobe 3 = 0x01, 4 = 0x02, 5 = 0x08, 6 = 0x10, 7 = 0x20, 8 = 0x40.
        """
        self.assertEqual(self.session.char_status()[4 + 0x5C], 0x7B)

    def test_entering_the_mog_house_rests_the_character(self):
        """The Mog House refills HP/MP, drops every status effect and persists both."""
        session = self.session
        session.char["hp_current"] = 12
        session.char["mp_current"] = 3
        session.status_effects[:] = [33, 300]
        # 0x037 is what tells the client about them, so make sure it could see them first.
        before = session.char_status()
        self.assertEqual(before[4], 33)
        self.assertEqual(before[4 + 1], 300 & 0xFF)
        self.assertEqual(before[4 + 0x48], 1 << 2)  # slot 1's high two bits
        session.queue.clear()
        session.toggle_moghouse()
        self.assertEqual(int(session.char["moghouse"]), 1)
        self.assertEqual(int(session.char["hp_current"]), int(session.char["hp"]))
        self.assertEqual(int(session.char["mp_current"]), int(session.char.get("mp", 0)))
        self.assertEqual(session.status_effects, [])
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["hp_current"]), int(session.char["hp"]))
        self.assertEqual(int(saved["mp_current"]), int(session.char.get("mp", 0)))
        status = next(message for message in session.queue
                      if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x037)
        self.assertEqual(bytes(status[4:36]), b"\xff" * 32)
        self.assertEqual(bytes(status[4 + 0x48:4 + 0x50]), bytes(8))
        # A zone change can build a fresh session from this row; it must come back rested.
        fresh = ZoneSession(self.world, None, self.service.character_record(saved, "Fanxi"))
        fresh.on_login()
        self.assertEqual(int(fresh.char["hp_current"]), int(fresh.char["hp"]))
        self.assertEqual(int(fresh.char["mp_current"]), int(fresh.char.get("mp", 0)))
        self.assertEqual(fresh.status_effects, [])

    def test_hp_mp_gauges_use_the_current_maximum(self):
        """Every bar divides by the real max: 7240/10149 is 71%, not full."""
        session = self.session
        session.char["hp"], session.char["hp_current"] = 10149, 7240
        session.char["mp"], session.char["mp_current"] = 10149, 271
        self.assertEqual(session.char_status()[4 + 0x26], 71)   # 0x037 flags0 HPP
        self.assertEqual(session.char_update()[4 + 0x1A], 71)   # 0x00D HPP
        self.assertEqual(session.login_packet()[4 + 0x1A], 71)  # 0x00A HPP
        party = session.party_member()
        self.assertEqual(struct.unpack_from("<II", party, 4 + 4), (7240, 271))
        self.assertEqual((party[4 + 18], party[4 + 19]), (71, 2))
        # At the cap the bars are full; a job with no MP keeps its bar full as before.
        session.char["hp_current"] = 10149
        session.char["mp_current"] = 10149
        party = session.party_member()
        self.assertEqual((party[4 + 18], party[4 + 19]), (100, 100))
        session.char["mp"], session.char["mp_current"] = 0, 0
        self.assertEqual(session.party_member()[4 + 19], 100)

    def test_a_warp_out_of_the_mog_house_clears_the_inside_flag(self):
        """A box pulled out while inside its Mog House must not land back at (0, 0, 0).

        The flag makes the login packet select the interior and after_zone_in restores the
        origin, so a //warp call that left it set kept the box in its own Mog House and the
        launcher pulled it again -- the re-zone loop.
        """
        session = self.session
        session.char["moghouse"] = 1
        session.zoning = False
        session.zone_loaded = True
        session.queue.clear()
        session.change_zone(100, [10.0, 20.0, 30.0, 0])
        self.assertEqual(int(session.char["moghouse"]), 0)
        self.assertEqual(session.pos, [10.0, 20.0, 30.0, 0])
        self.assertEqual(int(self.service.character(self.character["id"])["moghouse"]), 0)
        # Inside the interior itself the flag stays (entering is a zone change too).
        session.zoning = False
        session.zone_loaded = True
        session.char["moghouse"] = 1
        session.change_zone(session.zone, [0.0, 0.0, 0.0, 192])
        self.assertEqual(int(session.char["moghouse"]), 1)

    def test_leaving_the_mog_house_does_not_heal(self):
        """Only entering rests; walking out leaves the vitals and effects alone."""
        session = self.session
        session.char["moghouse"] = 1
        session.char["hp_current"] = 17
        session.char["mp_current"] = 5
        session.status_effects[:] = [40]
        session.toggle_moghouse()
        self.assertEqual(int(session.char["moghouse"]), 0)
        self.assertEqual(int(session.char["hp_current"]), 17)
        self.assertEqual(int(session.char["mp_current"]), 5)
        self.assertEqual(session.status_effects, [40])

    def test_login_inside_the_mog_house_rests(self):
        """Logging back in inside the Mog House leaves the character rested too."""
        session = self.session
        session.char["moghouse"] = 1
        session.char["hp_current"] = 1
        session.char["mp_current"] = 0
        session.status_effects[:] = [33]
        session.on_login()
        self.assertEqual(int(session.char["hp_current"]), int(session.char["hp"]))
        self.assertEqual(int(session.char["mp_current"]), int(session.char.get("mp", 0)))
        self.assertEqual(session.status_effects, [])
        saved = self.service.character(self.character["id"])
        self.assertEqual(int(saved["hp_current"]), int(session.char["hp"]))
        self.assertEqual(int(saved["mp_current"]), int(session.char.get("mp", 0)))
        # The zone-in bundle carries the rested values and no effect slot.
        session.queue.clear()
        session.after_zone_in()
        by_type = {struct.unpack_from("<H", message, 0)[0] & 0x1FF: message
                   for message in session.queue}
        self.assertEqual(bytes(by_type[0x037][4:36]), b"\xff" * 32)
        self.assertEqual(struct.unpack_from("<ii", by_type[0x061], 4),
                         (int(session.char["hp"]), int(session.char.get("mp", 0))))
        self.assertEqual(struct.unpack_from("<II", by_type[0x0DF], 8),
                         (int(session.char["hp"]), int(session.char.get("mp", 0))))

    def test_mog_house_door_ids_with_digits_are_entrances(self):
        """San d'Oria's door is ``zmr0``; a digit must enter, not be read as a zone line."""
        session = self.session
        self.zone(230)
        session.char["moghouse"] = 0
        session.queue.clear()
        session.handle(0x05E, zone_line_packet(b"zmr0"))
        self.assertEqual(int(session.char["moghouse"]), 1)
        self.assertTrue(session.queue[-1].zone_out)
        packet = session.login_packet()
        self.assertEqual(struct.unpack_from("<H", packet, 4 + 0xA6)[0], 0x0121)
        self.assertEqual(packet[4 + 0xAA], 1)

    def test_mog_house_exit_menu_names_the_city_you_are_in(self):
        """The login model/exit bit must follow the city, not always say Jeuno."""
        session = self.session
        session.char["moghouse"] = 1
        cases = (
            (230, 0, 0x0121, 1),  # home San d'Oria
            (236, 1, 0x0122, 2),  # home Bastok
            (240, 2, 0x0123, 3),  # home Windurst
            (246, 3, 0x0100, 4),  # Jeuno, whichever nation the character is
            (235, 0, 0x0102, 2),  # a San d'Orian visiting Bastok
            (243, 1, 0x0100, 4),  # Ru'Lude Gardens
        )
        for zone, nation, model, exit_bit in cases:
            with self.subTest(zone=zone, nation=nation):
                session.zone = zone
                session.char["nation"] = nation
                packet = session.login_packet()
                self.assertEqual(struct.unpack_from("<H", packet, 4 + 0xA6)[0], model)
                self.assertEqual(packet[4 + 0xAA], exit_bit)
        # Outside the Mog House the model stays disabled and no exit menu is offered.
        session.char["moghouse"] = 0
        packet = session.login_packet()
        self.assertEqual(struct.unpack_from("<H", packet, 4 + 0xA6)[0], 0x01FF)
        self.assertEqual(packet[4 + 0xAA], 0)

    def test_mog_house_exit_menu_travels_to_the_chosen_city_area(self):
        """0x05E zmrq mode N exits the Bastok Mog House into Bastok area N."""
        session = self.session
        session.char["nation"] = 1
        for mode, destination in ((1, 234), (2, 235), (3, 236)):
            with self.subTest(mode=mode):
                session.zone = 234
                session.char["moghouse"] = 1
                # The client finishes each hand-off before the next menu opens; the test
                # drives them back to back, so settle the previous one first.
                session.zoning = False
                session.zone_loaded = True
                session.pending_zone = None
                session.queue.clear()
                session.handle(0x05E, zone_line_packet(b"zmrq", mode, 2))
                self.assertEqual(session.zone, destination)
                self.assertEqual(int(session.char["moghouse"]), 0)
                self.assertEqual(
                    int(self.service.character(self.character["id"])["moghouse"]), 0)
                self.assertIn(0x00B, msg_types(session))
                door = next(
                    list(line[1:]) for rect, line in self.world.zones.lines.items()
                    if int(line[0]) == destination
                    and rect.to_bytes(4, "little")[:3] in (b"zmr", b"zms")
                    and rect.to_bytes(4, "little")[3] != ord("q"))
                self.assertEqual(session.pos, door)
        # Mode 0 is "the area you entered from": it stays in this city.
        session.zone = 236
        session.char["moghouse"] = 1
        session.zoning = False
        session.zone_loaded = True
        session.pending_zone = None
        session.queue.clear()
        session.handle(0x05E, zone_line_packet(b"zmrq", 0, 2))
        self.assertEqual(session.zone, 236)
        self.assertEqual(int(session.char["moghouse"]), 0)

    def test_mog_house_exit_menu_covers_every_city(self):
        """Each MyRoomExitMode reaches the area the client's menu named."""
        session = self.session
        cities = {
            230: (230, 231, 232),
            234: (234, 235, 236),
            238: (238, 239, 240, 241),
            246: (243, 244, 245, 246),
        }
        for start, destinations in cities.items():
            for mode, destination in enumerate(destinations, 1):
                with self.subTest(start=start, mode=mode):
                    session.zone = start
                    session.char["moghouse"] = 1
                    # One menu exit per hand-off in the real client; settle the previous
                    # one before driving the next.
                    session.zoning = False
                    session.zone_loaded = True
                    session.pending_zone = None
                    session.queue.clear()
                    session.handle(0x05E, zone_line_packet(b"zmrq", mode, 0))
                    self.assertEqual(session.zone, destination)
                    self.assertEqual(int(session.char["moghouse"]), 0)

    def equip_axe(self):
        """Give the test character a real axe so the weapon-skill filter has a type."""
        self.session.char["main_job"] = 9        # BST
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 4         # BLM
        self.session.char["sub_level"] = 49
        row = self.db.one("SELECT item_id FROM items WHERE skill = 5 LIMIT 1")
        self.assertIsNotNone(row, "no axe item in the test database")
        self.session.equipped = {0: (0, 4, int(row["item_id"]))}
        return int(row["item_id"])

    def test_zone_in_advertises_only_the_equipped_weapons_skills(self):
        """0x0AC lists the equipped weapon's type, not every weapon skill in the table."""
        self.equip_axe()
        self.session.queue.clear()
        self.session.after_zone_in()
        messages = [message for message in self.session.queue
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x0AC]
        self.assertEqual(len(messages), 1)
        bits = bytes(messages[0][4:])
        self.assertEqual(len(bits), 224)
        caps, _base = self.session.effective_skills()
        expected = set(self.service.weapon_skill_ids_for(5, caps[5]))
        self.assertGreater(len(expected), 0)
        for ws_id in expected:
            self.assertTrue(bits[ws_id >> 3] & (1 << (ws_id & 7)),
                            "axe weapon skill %d is not advertised" % ws_id)
        # Skills for other weapon types must not leak into the menu.
        for ws_id in (1, 16, 32, 48, 96, 112, 128, 144, 160, 176, 192, 208):
            self.assertFalse(bits[ws_id >> 3] & (1 << (ws_id & 7)),
                             "weapon skill %d belongs to another weapon" % ws_id)
        # No pet commands for a player.  The fourth block carries the current job pair's
        # client trait ids, so it is no longer an always-empty tail.
        self.assertEqual(bits[128:192], bytes(64))
        advertised = {trait_id for trait_id in range(256)
                      if bits[192 + (trait_id >> 3)] & (1 << (trait_id & 7))}
        self.assertEqual(advertised, {trait.id for trait in self.session.job_traits()})

    def test_prime_weapon_grants_its_weaponskill(self):
        """Dokoku's "Adds weapon skill" line puts Zesho Meppo on the katana menu.

        The skill is not learned from a katana skill value: it is item-granted, so it
        must not appear with Kikoku (or any other katana), only with the Prime weapon
        that carries the 355 modifier.
        """
        self.session.char["main_job"] = 13          # NIN
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 1            # WAR
        self.session.char["sub_level"] = 49
        self.session.equipped = {0: (0, 4, 21932)}  # Dokoku 119 III
        self.session.store_equipment()
        skills = self.session.equipped_weapon_skills()
        self.assertIn(142, skills)                  # Zesho Meppo
        self.assertNotIn(159, skills)               # Tachi: Mumei is Kusanagi's
        # The ordinary skill-value filter must not offer it to every katana.
        self.assertNotIn(142, self.service.weapon_skill_ids_for(9, 350))
        body = bytes(self.session.char_abilities()[4:])
        self.assertTrue(body[142 >> 3] & (1 << (142 & 7)))

        # Kikoku is also a katana, but it carries no Prime skill.
        self.session.equipped = {0: (0, 4, 21906)}
        self.session.store_equipment()
        self.assertNotIn(142, self.session.equipped_weapon_skills())
        body = bytes(self.session.char_abilities()[4:])
        self.assertFalse(body[142 >> 3] & (1 << (142 & 7)))

    def test_weapon_skills_follow_the_characters_skill_value(self):
        """A level-10 axe user sees the low skills; a level-99 one sees the rest."""
        self.equip_axe()
        self.session.char["main_level"] = 10
        low_caps, _base = self.session.effective_skills()
        low = set(self.service.weapon_skill_ids_for(5, low_caps[5]))
        self.assertIn(64, low)        # Raging Axe (skill 5)
        self.assertNotIn(72, low)     # Decimation (240)
        self.assertNotIn(77, low)     # Ruinator (357)
        self.session.char["main_level"] = 99
        high_caps, _base = self.session.effective_skills()
        high = set(self.service.weapon_skill_ids_for(5, high_caps[5]))
        self.assertIn(77, high)       # Ruinator is in reach at 99
        self.assertIn(73, high)       # Onslaught (skill_level 0) once axe is mastered
        self.assertNotIn(32, high)    # Fast Blade is a sword skill
        self.assertNotIn(1, high)     # Combo is hand-to-hand

    def test_weaponskill_rejects_another_weapon_type(self):
        """The server enforces the same list it advertises in 0x0AC."""
        self.equip_axe()
        self.session.char["tp"] = 3000
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_WEAPONSKILL)
        struct.pack_into("<I", packet, 12, 1)   # Combo, hand-to-hand
        self.session.queue.clear()
        self.session.weaponskill(bytes(packet), 0)
        self.assertIn("You cannot use Combo with your equipped weapon.",
                      "\n".join(self.chats()))
        # An axe skill passes the filter and then fails only on the missing target.
        struct.pack_into("<I", packet, 12, 64)  # Raging Axe
        self.session.queue.clear()
        self.session.weaponskill(bytes(packet), 0)
        self.assertIn("There is no valid target for Raging Axe.",
                      "\n".join(self.chats()))

    def equip_cor_sword_and_armageddon(self):
        """A level-99 COR with a sword in the main hand and Armageddon in the ranged slot.

        This is the live loadout behind the Wildfire report: the phase engine's
        sets.WS.Wildfire wears Armageddon, and the item table's placeholder row for
        item 21269 used to say skill 0, so 0x0AC dropped the whole Marksmanship block.
        """
        self.session.char["main_job"] = 17          # COR
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 11           # RNG
        self.session.char["sub_level"] = 49
        self.session.equipped = {0: (0, 4, 21621),  # Naegling, sword 3
                                 2: (0, 4, 21269)}  # Armageddon, marksmanship 26
        self.session.store_equipment()

    def test_armageddon_keeps_marksmanship_in_the_weapon_skill_list(self):
        """The GearSwap placeholder row must not make a real gun look like no weapon.

        Migration 66 gave 21269 skill 0 and migration 111's upsert only refreshes
        price/flags, so equipping Armageddon emptied the 0x0AC Marksmanship block and
        the HUD's Marksmanship tab disappeared until a Sword skill set equipped a
        skill-26 ranged weapon again.
        """
        self.assertEqual(self.service.item_skill(21269), 26)
        # Migration 170 repairs the catalogue itself, not only the lookup fallback.
        for item_id, expected in ((18839, 41), (21267, 26), (21269, 26),
                                  (21296, 26), (22150, 26), (22307, 42)):
            row = self.db.one("SELECT skill FROM items WHERE item_id = ?", (item_id,))
            self.assertEqual(int(row["skill"]), expected,
                             "items.skill for %d was not synced" % item_id)
        self.equip_cor_sword_and_armageddon()
        ids = set(self.session.equipped_weapon_skills())
        self.assertIn(220, ids)                     # Wildfire
        self.assertIn(218, ids)                     # Leaden Salute
        for ws_id in (208, 209, 210, 212, 213, 214, 215):
            self.assertIn(ws_id, ids, "marksmanship skill %d disappeared" % ws_id)
        bits = bytes(self.session.char_abilities()[4:])
        self.assertTrue(bits[220 >> 3] & (1 << (220 & 7)),
                        "0x0AC no longer advertises Wildfire")

    def test_job_specific_weapon_skills_follow_the_main_job(self):
        """Relic/mythic/empyrean and merit skills belong to their weapon's jobs.

        A COR with Sword 350 used to see Atonement, Knights of Round, Coronach and every
        other skill whose skill_level is 0.  The ordinary skill-value skills stay.
        """
        self.equip_cor_sword_and_armageddon()
        cor = set(self.session.equipped_weapon_skills())
        self.assertIn(42, cor)                      # Savage Blade, ordinary Sword
        self.assertIn(220, cor)                     # Wildfire is COR/RNG
        self.assertIn(221, cor)                     # Last Stand is THF/RNG/COR
        self.assertNotIn(43, cor)                   # Knights of Round is PLD/RDM/BLU
        self.assertNotIn(45, cor)                   # Atonement is PLD
        self.assertNotIn(216, cor)                  # Coronach is RNG
        self.assertNotIn(217, cor)                  # Trueflight is RNG
        self.assertIn(226, cor)                     # Requiescat lists COR as a main job
        self.assertNotIn(60, cor)                   # Resolution is not a COR skill

        # The action handler uses the same list, not only the 0x0AC bitmap.
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_WEAPONSKILL)
        struct.pack_into("<I", packet, 12, 45)      # Atonement, PLD only
        self.session.queue.clear()
        self.session.weaponskill(bytes(packet), 0)
        self.assertIn("You cannot use Atonement with your equipped weapon.",
                      "\n".join(self.chats()))

        # A PALADIN with the same sword may use the Paladin sword skills.  It does not
        # get a gun, so its only weapon type is Sword.
        self.session.char["main_job"] = 7
        self.session.equipped = {0: (0, 4, 21621)}
        pld = set(self.session.equipped_weapon_skills())
        self.assertIn(43, pld)
        self.assertIn(45, pld)
        self.assertIn(226, pld)                     # Requiescat, PLD merit
        self.assertNotIn(220, pld)

        # A RANGER with Annihilator (item 21267 has the same placeholder skill row as
        # Armageddon) gets the RNG-only marksmanship skills and not the COR ones.
        self.session.char["main_job"] = 11
        self.session.equipped = {2: (0, 4, 21267)}
        rng = set(self.session.equipped_weapon_skills())
        self.assertIn(216, rng)                     # Coronach
        self.assertIn(217, rng)                     # Trueflight
        self.assertIn(220, rng)                     # Wildfire is also RNG
        self.assertIn(221, rng)                     # Last Stand is also RNG
        self.assertNotIn(218, rng)                  # Leaden Salute is COR only

    def test_zone_in_advertises_the_jobs_abilities(self):
        """The Job Abilities block of 0x0AC is bits 512..1023, i.e. bytes 64..127."""
        self.session.queue.clear()
        self.session.after_zone_in()
        message = next(message for message in self.session.queue
                       if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x0AC)
        bits = bytes(message[4:])
        main_job = int(self.session.char["main_job"])
        main_level = int(self.session.char["main_level"])
        ja_ids = self.service.job_ability_ids(
            main_job, main_level, int(self.session.char.get("sub_job", 0)),
            int(self.session.char.get("sub_level", 0)))
        self.assertGreater(len(ja_ids), 0)
        for ja_id in ja_ids:
            self.assertTrue(bits[64 + (ja_id >> 3)] & (1 << (ja_id & 7)),
                            "job ability %d is not advertised" % ja_id)
        # Nothing outside the character's main/sub job may leak into the block.
        self.assertNotIn(391, ja_ids)   # Chakra is Monk-only; a fresh character is WAR.
        self.assertNotIn(190, ja_ids)   # Curing Waltz is Dancer-only.

    def test_every_job_has_its_abilities_and_traits_in_the_command_data(self):
        """Every playable job, at 99, reaches both 0x0AC blocks.

        The menu was empty for every job when the host hook that rebuilds the client's
        saved command list was compiled out, so this checks the server half of that path
        across the whole job table rather than one hand-picked pair.  Blue Mage traits
        depend on set spells and job 23 is the custom-job slot; neither has a trait table
        yet, but both must still carry their job abilities.
        """
        self.session.equipped = {}
        no_traits = {16, 23}
        for job in range(1, 24):
            with self.subTest(job=job):
                self.session.char.update(main_job=job, main_level=99,
                                         sub_job=0, sub_level=0)
                self.session._trait_cache = None
                ja_ids = self.service.job_ability_ids(job, 99)
                self.assertGreater(len(ja_ids), 0,
                                   "job %d has no abilities at 99" % job)
                traits = self.session.job_traits()
                if job not in no_traits:
                    self.assertGreater(len(traits), 0,
                                       "job %d has no traits at 99" % job)
                bits = bytes(self.session.char_abilities()[4:])
                self.assertEqual(len(bits), 224)
                for ja_id in ja_ids:
                    self.assertTrue(bits[64 + (ja_id >> 3)] & (1 << (ja_id & 7)),
                                    "job %d ability %d is not in 0x0AC" % (job, ja_id))
                for trait in traits:
                    self.assertTrue(bits[192 + (trait.id >> 3)] & (1 << (trait.id & 7)),
                                    "job %d trait %d is not in 0x0AC" % (job, trait.id))

    def test_auto_refresh_ticks_mp_and_reaches_the_trait_block(self):
        """A Paladin 35 has Auto Refresh I: 1 MP every three seconds, and bit 10 in 0x0AC."""
        self.session.char.update(main_job=7, main_level=35, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.assertEqual(self.session.trait_mods().get(mod.REFRESH), 1)
        self.session.char["mp_current"] = max(0, int(self.session.char["mp"]) - 10)
        before = int(self.session.char["mp_current"])
        self.session.queue.clear()
        self.session.next_regen_tick = 0.0
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["mp_current"]), before + 1)
        self.assertIn(0x037, msg_types(self.session))
        self.assertIn(0x0DF, msg_types(self.session))
        bits = bytes(self.session.char_abilities()[4:])
        self.assertTrue(bits[192 + (10 >> 3)] & (1 << (10 & 7)),
                        "Auto Refresh (trait 10) is missing from 0x0AC")

    def test_auto_regen_ticks_hp(self):
        """A White Mage 25 has Auto Regen I: 1 HP every three seconds."""
        self.session.char.update(main_job=3, main_level=25, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.assertEqual(self.session.trait_mods().get(mod.REGEN), 1)
        self.session.char["hp_current"] = max(1, int(self.session.char["hp"]) - 10)
        before = int(self.session.char["hp_current"])
        self.session.next_regen_tick = 0.0
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["hp_current"]), before + 1)

    def test_clear_mind_raises_resting_mp(self):
        """RDM 99 has Clear Mind IV: +12 MP on every /heal tick."""
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        bonus = int(self.session.trait_mods().get(mod.MP_WHILE_HEALING, 0))
        self.assertEqual(bonus, 12)
        self.session.char["mp_current"] = 100
        self.session.resting = True
        self.session.casting = None
        self.session.engaged_id = None
        self.session.next_rest_tick = 0.0
        self.session.tick_rest(time.time())
        self.assertEqual(int(self.session.char["mp_current"]),
                         100 + max(1, int(self.session.char["mp"]) // 20 + bonus))

    def test_gear_refresh_mod_ticks_mp(self):
        """Refresh on equipment uses the same tick as the Auto Refresh trait."""
        row = self.db.one("SELECT item_id, value FROM item_mods WHERE mod_id = ?"
                          " AND value > 0 LIMIT 1", (mod.REFRESH,))
        self.assertIsNotNone(row, "no Refresh gear in the item modifier table")
        # Body slot (kind 5), and a job/level with MP but no Auto Refresh trait.
        self.service.save_equipment(int(self.character["id"]),
                                    {5: (0, 0, int(row["item_id"]))})
        self.session.char.update(main_job=3, main_level=1, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.session.char["mp_current"] = max(0, int(self.session.char["mp"]) - 10)
        before = int(self.session.char["mp_current"])
        self.session.next_regen_tick = 0.0
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["mp_current"]),
                         min(int(self.session.char["mp"]), before + int(row["value"])))

    def test_gear_regain_ticks_tp(self):
        """Karieyh Ring +1's Regain+5 adds TP on the same three-second tick."""
        self.service.save_equipment(int(self.character["id"]),
                                    {13: (0, 0, 26199)})  # Karieyh Ring +1
        self.session.char.update(main_job=1, main_level=1, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.session.char["tp"] = 0
        self.session.queue.clear()
        self.session.next_regen_tick = 0.0
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["tp"]), 5)
        # One 0x0DF covers the HP/MP/TP refresh; gain_tp(queue=False) must not queue a
        # second party copy behind it.
        self.assertEqual(msg_types(self.session).count(0x0DF), 1)

    def test_idle_field_set_keeps_its_regen_refresh_and_regain(self):
        """The real MNK idle set: 19 Regen, 1 Refresh and 7 Regain while worn.

        Null Masque and Null Belt had no item_mods rows, so the live sheet showed
        Regen 13 / Regain 5 and no Refresh row at all while the client tooltip totals
        (and the player) expected 19 / 7 / 1.
        """
        self.service.save_equipment(int(self.character["id"]), {
            3: (0, 0, 22279),   # ammo  Staunch Tathlum +1
            4: (0, 0, 24270),   # head  Null Masque
            5: (0, 0, 23941),   # body  Anchorite's Cyclas +4
            6: (0, 0, 27027),   # hands Rao Kote +1
            7: (0, 0, 27203),   # legs  Rao Haidate +1
            8: (0, 0, 27379),   # feet  Rao Sune-Ate +1
            9: (0, 0, 27518),   # neck  Bathy Choker +1
            10: (0, 0, 26367),  # waist Null Belt
            11: (0, 0, 28475),  # ear1  Infused Earring
            12: (0, 0, 28512),  # ear2  Dawn Earring
            13: (0, 0, 26182),  # ring1 Chirich Ring +1
            14: (0, 0, 26199),  # ring2 Karieyh Ring +1
            15: (0, 0, 26269),  # back  Moonlight Cape
        })
        self.session.char.update(main_job=1, main_level=1, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        mods = self.session.combat_mods()
        self.assertEqual(mods.get(mod.REGEN), 19)
        self.assertEqual(mods.get(mod.REFRESH), 1)
        self.assertEqual(mods.get(mod.REGAIN), 7)

    def test_gear_swap_refreshes_the_maximum_the_tick_reads(self):
        """Chirich/Stikini only tick when the stored maxima follow the outfit.

        The passive tick compares HP/MP against ``char["hp"]``/``char["mp"]``.  A 0x050
        batch used to save the outfit without recomputing them, so after a swap that
        raised a maximum the character sat at the old cap and the tick saw "already
        full" -- Chirich Ring +1's Regen and Stikini Ring +1's Refresh looked dead.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.session.equipped.clear()
        self.session.refresh_vitals()
        old_hp = int(self.session.char["hp"])
        old_mp = int(self.session.char["mp"])
        # Nyame Mail is HP+136/MP+88 and lifts both maxima above the bare values; the
        # two rings carry the passive ticks (+2 HP and +1 MP every three seconds).
        self.session.equipped.update({5: (0, 0, 23768),
                                      13: (0, 0, 26182),   # Chirich Ring +1, Regen+2
                                      14: (0, 0, 26184)})  # Stikini Ring +1, Refresh+1
        self.session.char["hp_current"] = old_hp
        self.session.char["mp_current"] = old_mp
        self.session.equipment_changed = True
        self.session.queue.clear()
        self.session.flush_equipment()
        sheet = self.session.stat_sheet()
        self.assertGreater(int(sheet.max_hp), old_hp)
        self.assertGreater(int(sheet.max_mp), old_mp)
        self.assertEqual(int(self.session.char["hp"]), int(sheet.max_hp))
        self.assertEqual(int(self.session.char["mp"]), int(sheet.max_mp))
        self.session.next_regen_tick = 0.0
        self.session.tick(time.time())
        self.assertEqual(int(self.session.char["hp_current"]), old_hp + 2)
        self.assertEqual(int(self.session.char["mp_current"]), old_mp + 1)

    def test_support_job_traits_use_the_support_level(self):
        """A support White Mage at 25 still has Auto Regen I from the sub-job."""
        self.session.char.update(main_job=1, main_level=60, sub_job=3, sub_level=25)
        self.session._trait_cache = None
        self.assertEqual(self.session.trait_mods().get(mod.REGEN), 1)
        self.session.char.update(sub_job=3, sub_level=24)
        self.session._trait_cache = None
        self.assertIsNone(self.session.trait_mods().get(mod.REGEN))

    def test_trait_tick_waits_for_the_three_second_interval(self):
        """Two server exchanges inside one second must not tick twice."""
        self.session.char.update(main_job=7, main_level=35, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.session.char["mp_current"] = max(0, int(self.session.char["mp"]) - 10)
        before = int(self.session.char["mp_current"])
        now = time.time()
        self.session.next_regen_tick = now + 1.0
        self.session.tick(now)
        self.assertEqual(int(self.session.char["mp_current"]), before)
        self.session.tick(now + 1.0)
        self.assertEqual(int(self.session.char["mp_current"]), before + 1)

    def test_max_hp_boost_trait_raises_the_maximum(self):
        """Warrior 30's Max HP Boost I is a real +30 maximum, not a menu-only number."""
        self.session.char.update(main_job=1, main_level=30, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.refresh_vitals()
        self.assertEqual(int(self.session.char["hp"]),
                         base_stats.base_hp(1, 1, 30) + 30)
        sheet = self.session.stat_sheet()
        self.assertEqual(int(sheet.fighter.mods.get(mod.ATT, 0)), 10)
        self.assertEqual(int(sheet.fighter.mods.get(mod.DEF, 0)), 10)

    def test_traits_command_lists_the_passive_traits(self):
        self.session.char.update(main_job=7, main_level=35, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.queue.clear()
        self.session.command(["traits"])
        joined = "\n".join(self.chats())
        self.assertIn("Auto Refresh", joined)
        self.assertIn("Passive tick", joined)
        self.assertIn(0x0AC, msg_types(self.session))

    def test_traits_command_shows_a_gear_only_tick(self):
        """The diagnostic must include gear, not only the Auto Regen/Refresh traits."""
        self.session.char.update(main_job=10, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.service.save_equipment(int(self.character["id"]),
                                    {13: (0, 0, 26182),    # Chirich Ring +1
                                     14: (0, 0, 26184)})   # Stikini Ring +1
        self.session.refresh_vitals()
        self.session.queue.clear()
        self.session.command(["traits"])
        joined = "\n".join(self.chats())
        self.assertIn("Regen 2 HP", joined)
        self.assertIn("Refresh 1 MP", joined)

        # Karieyh Ring +1 is the Regain half of the same diagnostic.
        self.service.save_equipment(int(self.character["id"]),
                                    {13: (0, 0, 26199)})   # Karieyh Ring +1
        self.session.refresh_vitals()
        self.session.queue.clear()
        self.session.command(["traits"])
        joined = "\n".join(self.chats())
        self.assertIn("Regain 5 TP", joined)

    def test_stats_request_resends_command_data(self):
        """The client builds the Abilities menu after 0x061, so 0x0AC belongs in its reply."""
        self.session.queue.clear()
        self.session.handle(0x061, bytes(8))
        types = msg_types(self.session)
        self.assertIn(0x0AB, types)   # the first 160 job abilities
        self.assertIn(0x0AC, types)
        self.assertIn(0x1A5, types)   # the same job block as an incremental update
        self.assertIn(0x119, types)
        # The client builds its Weapon Skills list on 0x062, so the command data must
        # come first or a fresh client draws an empty list.
        self.assertLess(types.index(0x0AC), types.index(0x062))

    def test_zone_in_sends_command_data_before_skills(self):
        """Same ordering rule for the zone-in burst, not just the 0x061 reply."""
        self.session.queue.clear()
        self.session.after_zone_in()
        types = msg_types(self.session)
        self.assertLess(types.index(0x0AC), types.index(0x062))

    def test_incremental_command_packet_carries_the_job_block(self):
        """0x1A5 kind 1 updates the command table; offset 64 is the Job Abilities block."""
        self.session.char["main_job"] = 9
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 4
        self.session.char["sub_level"] = 49
        message = self.session.char_commands()
        body = bytes(message[4:])
        action, kind, offset, length = struct.unpack_from("<BBHH", body, 0)
        self.assertEqual((action, kind, offset, length), (1, 1, 64, 64))
        bits = body[6:6 + length]
        self.assertEqual(len(bits), 64)
        ja_ids = self.service.job_ability_ids(9, 99, 4, 49)
        for ja_id in ja_ids:
            self.assertTrue(bits[ja_id >> 3] & (1 << (ja_id & 7)),
                            "job ability %d missing from 0x1A5" % ja_id)

    def test_ability_recast_lists_every_known_ability(self):
        """0x119 is the table the Job Abilities menu reads; ready abilities need a slot too."""
        self.session.char["main_job"] = 9        # BST
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 4         # BLM
        self.session.char["sub_level"] = 49
        message = self.session.abil_recast()
        body = bytes(message[4:])
        self.assertEqual(len(body), 256)
        slots = [struct.unpack_from("<HBB", body, slot * 8) for slot in range(1, 31)]
        listed = {timer_id for _timer, _calc, timer_id in slots if timer_id}
        abilities = self.service.job_abilities(
            int(self.session.char["main_job"]), int(self.session.char["main_level"]),
            int(self.session.char.get("sub_job", 0)), int(self.session.char.get("sub_level", 0)))
        expected = {int(row["recast_id"]) for row in abilities
                    if 0 < int(row["recast_id"]) <= 0xFF}
        self.assertGreater(len(expected), 0)
        self.assertEqual(expected, listed)
        # Ready abilities are listed with a zero timer, not omitted.
        ready = {timer_id for timer, _calc, timer_id in slots if timer_id and timer == 0}
        self.assertGreater(len(ready), 0)

    def test_job_ability_provokes_the_target(self):
        """C2S 0x01A action 0x09 runs a job ability; Provoke claims the monster."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.session.queue.clear()
        packet = bytearray(28)
        struct.pack_into("<IHH", packet, 4, int(self.session.char["char_id"]),
                         int(mob.targid), packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 35)     # Provoke
        self.session.job_ability(bytes(packet), int(mob.targid))
        self.assertIn(0x028, msg_types(self.session))
        self.assertEqual(mob.engaged_char_id, int(self.session.char["char_id"]))
        self.assertGreater(self.session.ability_recasts.get(5, 0), time.time())

    def test_killer_instinct_puts_up_its_icon_and_bonuses(self):
        """Killer Instinct: icon 349, 5:00 with helm/Aspis, 15% damage, 15% DT."""
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        self.session._merit_counts = {merits.KILLER_INSTINCT: 5}
        # Ankusa Helm +4 and the Diamond Aspis: 220 s merit base + 20 s helm,
        # then the Aspis's 25%.  This server gives the whole party the same value.
        self.session.equipped[4] = (0, 50, 23926)
        self.session.equipped[1] = (0, 51, 26488)
        self.assertEqual(self.session.killer_instinct_duration(5), (300.0, 300.0))
        self.session.equipped.pop(1)
        self.assertEqual(self.session.killer_instinct_duration(5), (240.0, 240.0))
        self.session.equipped.pop(4)
        self.assertEqual(self.session.killer_instinct_duration(5), (220.0, 220.0))
        # Restore the full set for the actual use.
        self.session.equipped[4] = (0, 50, 23926)
        self.session.equipped[1] = (0, 51, 26488)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        before = int(self.session.combat_mods().get(mod.DMG, 0))
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 162)     # Killer Instinct
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)

        self.assertTrue(self.session.has_effect(effects.KILLER_INSTINCT))
        state = self.session.effect(effects.KILLER_INSTINCT)
        self.assertEqual(int(state["power"]), 1500)
        # Rank 5 is 180 s + 4 x 10 s + 20 s of helm, then +25% from the Aspis:
        # exactly 300 s, matching the 5:00 recast.
        self.assertAlmostEqual(float(state["until"]) - time.time(), 300.0, delta=3.0)
        self.assertEqual(
            int(self.session.combat_mods().get(mod.DMG, 0)), before - 1500)
        self.assertIn(0x037, msg_types(self.session))

        # +15% on every physical hit, including each swing of a weapon skill.
        with mock.patch(
                "fanxi_server.game.combat.melee",
                return_value=combat.Hit(100, False, False)):
            miss, damage, critical = self.world.player_attack(self.session, mob)
        self.assertFalse(miss)
        self.assertFalse(critical)
        self.assertEqual(damage, 115)

    def test_boost_cannot_push_a_hit_past_the_damage_cap(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session._boost_until = time.time() + 30.0
        with mock.patch(
                "fanxi_server.game.combat.melee",
                return_value=combat.Hit(combat.DAMAGE_CAP, False, False)):
            miss, damage, _critical = self.world.player_attack(self.session, mob)
        self.assertFalse(miss)
        self.assertEqual(damage, combat.DAMAGE_CAP)

    def test_a_multi_hit_weapon_skill_is_capped_at_99999(self):
        """A weapon skill is one client line, so its summed hits share the ceiling."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = 500000
        mob.hp = 500000
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 40000, False)):
            result = self.session._roll_weaponskill_round(
                mob, ftp_base=1.0, hits=3, multi_hit_ftp=False,
                attack_multiplier=1.0, ignored_defense=0.0, crit_bonus=0.0,
                crit_capable=False, ws_accuracy=0, wsc=0,
                wsd_all=0, wsd_first=0)
        # Three landing hits of 40,000 are 120,000 raw, clipped to one 99,999 line.
        self.assertGreaterEqual(result["landed"], 3)
        self.assertEqual(result["damage"], combat.DAMAGE_CAP)
        self.assertFalse(result["defeated"])

    def test_the_cap_stops_a_weapon_skill_killing_above_99999_hp(self):
        """Only the clipped number is applied, so a 150K monster survives a 160K roll."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = 150000
        mob.hp = 150000
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 40000, False)):
            result = self.session._roll_weaponskill_round(
                mob, ftp_base=1.0, hits=4, multi_hit_ftp=False,
                attack_multiplier=1.0, ignored_defense=0.0, crit_bonus=0.0,
                crit_capable=False, ws_accuracy=0, wsc=0,
                wsd_all=0, wsd_first=0)
        self.assertEqual(result["damage"], combat.DAMAGE_CAP)
        self.assertFalse(result["defeated"])

    def test_the_wire_clips_a_six_digit_result_as_a_last_resort(self):
        """queue_action is the backstop; no 0x028 result may carry more than 99,999."""
        self.zone(100)
        self.session.queue.clear()
        self.session.queue_action(0x1234, damage=120000)
        message = next(message for message in self.session.queue
                       if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028)
        self.assertEqual(combat.DAMAGE_CAP, action_results(message)[0]["value"])

    def test_killer_instinct_covers_the_whole_party_for_the_full_time(self):
        """The custom BST KI change: the whole party gets 5:00 and the full effect."""
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        self.session._merit_counts = {merits.KILLER_INSTINCT: 5}
        self.session.equipped[4] = (0, 50, 23926)   # Ankusa Helm +4
        self.session.equipped[1] = (0, 51, 26488)   # Diamond Aspis

        account = self.service.register("partytester", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Buddy", "race": 1})
        other = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Buddy"))
        other.set_key(bytes(20))
        other.logged_in = True
        other.zone = 100
        # Deliberately far outside retail's 7.9-yalm radius.
        other.pos = [self.session.pos[0] + 40.0, self.session.pos[1],
                     self.session.pos[2], 0]
        other.char["hp_current"] = int(other.char["hp"])
        self.world.sessions[("127.0.0.1", 1235)] = other
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, other))

        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 162)     # Killer Instinct
        self.session.queue.clear()
        other.queue.clear()
        self.session.job_ability(bytes(packet), 0)

        for target in (self.session, other):
            state = target.effect(effects.KILLER_INSTINCT)
            self.assertIsNotNone(state)
            self.assertEqual(int(state["power"]), 1500)
            self.assertEqual(int(state["mods"].get(mod.DMG, 0)), -1500)
            self.assertAlmostEqual(
                float(state["until"]) - time.time(), 300.0, delta=3.0)
        self.assertIn(0x028, msg_types(other))
        self.assertIn(0x037, msg_types(other))

    def _use_bst_ability(self, ability_id, act_index=0):
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, int(ability_id))
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), int(act_index))

    def test_tame_marks_a_mob_and_boosts_the_next_charm(self):
        """Tame leaves a docile mob for Charm; the next Charm gets its +10% chance."""
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = None
        mob.enmity.clear()
        mob.enmity_ve.clear()
        mob.engaged_char_id = None
        mob.claim_char_id = None
        with mock.patch.object(self.world.rng, "random", return_value=0.5):
            self._use_bst_ability(54, mob.targid)       # Tame
        self.assertEqual(int(self.session.tamed_mob_id), int(mob.id))
        self.assertIn("seems friendlier", " ".join(self.chats()))
        with mock.patch.object(self.world.rng, "random", return_value=0.0):
            self._use_bst_ability(52, mob.targid)       # Charm
        self.assertIsNotNone(self.session.pet_entity)
        self.assertEqual(int(self.session.tamed_mob_id), 0)

    def test_tame_uses_the_live_head_success_rate(self):
        """Totemic Helm +4's +31 makes a 99% roll succeed even though the base is 75%."""
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        self.session.equipped[4] = (0, 24, 23903)       # Totemic Helm +4
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = None
        mob.enmity.clear()
        mob.enmity_ve.clear()
        mob.engaged_char_id = None
        with mock.patch.object(self.world.rng, "random", return_value=0.99):
            self._use_bst_ability(54, mob.targid)
        self.assertEqual(int(self.session.tamed_mob_id), int(mob.id))

    def test_tame_disengages_a_solo_claimed_mob(self):
        """Tame only disengages when the Beastmaster is the sole claimant."""
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        me = int(self.session.char["char_id"])
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = None
        mob.enmity = {me: 500}
        mob.enmity_ve = {me: 500}
        mob.engaged_char_id = me
        mob.claim_char_id = me
        mob.aggro_announced = True
        mob.next_attack_at = time.time() + 3.0
        with mock.patch.object(self.world.rng, "random", return_value=0.5):
            self._use_bst_ability(54, mob.targid)
        self.assertEqual(mob.enmity, {})
        self.assertEqual(mob.enmity_ve, {})
        self.assertIsNone(mob.engaged_char_id)
        self.assertFalse(mob.aggro_announced)
        self.assertIn("seems friendlier", " ".join(self.chats()))

    def test_gauge_reports_hp_and_charmability(self):
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = None
        mob.hp = 50
        mob.hp_max = 100
        self._use_bst_ability(53, mob.targid)
        chats = " ".join(self.chats())
        self.assertIn("50% HP", chats)
        self.assertIn("charmed", chats)

    def test_leave_releases_the_pet_and_tame_needs_no_pet(self):
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = None
        self.world.spawn_pet(self.session, "wyvern", time.time())
        self.assertIsNotNone(self.session.pet_entity)
        self._use_bst_ability(54, mob.targid)
        self.assertIn("already have a pet", " ".join(self.chats()))
        self._use_bst_ability(71)                       # Leave
        self.assertIsNone(self.session.pet_entity)
        self.assertIn("Your pet leaves.", self.chats())

    def _use_war_ability(self, ability_id, act_index=0):
        # The client's 0x01A is a 28-byte action packet: UniqueNo at 4, ActIndex at 8,
        # action id at 10 and the ability id in ActionBuf at 12.
        packet = bytearray(28)
        struct.pack_into("<IHH", packet, 4, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, int(ability_id))
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), int(act_index))

    def test_warrior_stat_abilities_apply_their_retail_modifiers(self):
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(31)                    # Berserk
        berserk = self.session.effect(effects.BERSERK)["mods"]
        self.assertEqual(35, berserk.get(mod.ATT_PERCENT))
        self.assertEqual(-25, berserk.get(mod.DEF_PERCENT))
        self._use_war_ability(33)                    # Defender
        defender = self.session.effect(effects.DEFENDER)["mods"]
        self.assertEqual(35, defender.get(mod.DEF_PERCENT))
        self.assertEqual(-25, defender.get(mod.ATT_PERCENT))
        self._use_war_ability(34)                    # Aggressor
        aggressor = self.session.effect(effects.AGGRESSOR)["mods"]
        self.assertEqual(25, aggressor.get(mod.ACC))
        self.assertEqual(-25, aggressor.get(mod.EVA))

    def test_warcry_and_blood_rage_overwrite_each_other(self):
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(32)                    # Warcry
        warcry = self.session.effect(effects.WARCRY)["mods"]
        self.assertEqual(11, warcry.get(mod.ATT_PERCENT))
        self._use_war_ability(267)                   # Blood Rage
        self.assertIsNone(self.session.effect(effects.WARCRY))
        blood = self.session.effect(effects.BLOOD_RAGE)["mods"]
        self.assertEqual(2000, blood.get(mod.CRIT_HIT_RATE))

    def test_mighty_strikes_forces_critical_hits(self):
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(16)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, True, False)) as melee:
            self.world.player_attack(self.session, mob)
        self.assertEqual(1.0, melee.call_args.kwargs["crit_bonus"])
        self.assertTrue(melee.call_args.kwargs["allow_critical"])

    def test_retaliation_counters_and_restraint_builds(self):
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp = mob.hp_max = 1000
        self._use_war_ability(226)                   # Retaliation
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(10, False, False)), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 50, False)), \
                mock.patch.object(self.world.rng, "random", return_value=0.0):
            self.world.mob_attack(mob, self.session)
        self.assertEqual(950, int(mob.hp))
        self.assertIn("retaliate", " ".join(self.chats()))
        self._use_war_ability(252)                   # Restraint
        self.session._restraint_bonus = 0
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, False, False)):
            self.world.player_attack(self.session, mob)
        self.assertGreater(int(self.session._restraint_bonus), 0)
        before_da = int(self.session.combat_mods().get(mod.DOUBLE_ATTACK, 0))
        self._use_war_ability(323)                   # Brazen Rush
        self.assertEqual(before_da + 100,
                         self.session.combat_mods().get(mod.DOUBLE_ATTACK))

    def _cast_spell(self, spell_id, act_index=0):
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_CAST_MAGIC)
        struct.pack_into("<I", packet, 12, int(spell_id))
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), int(act_index))

    def test_composure_extends_enhancing_magic(self):
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(247)                   # Composure
        state = self.session.effect(effects.COMPOSURE)
        self.assertIsNotNone(state)
        self.assertEqual(50, state["mods"].get(mod.ENH_MAGIC_DURATION))

    def test_chainspell_makes_cure_instant(self):
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp_current"] = 500
        self._use_war_ability(20)                    # Chainspell
        now = time.time()
        self._cast_spell(1)                          # Cure
        self.assertIsNotNone(self.session.casting)
        self.assertLess(self.session.casting["finish"] - now, 0.1)

    def test_quick_magic_proc_refunds_its_job_point_mp(self):
        """Quick Magic is a 5% proc; its job-point row is the 40% MP reduction."""
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["mp_current"] = 500
        cost = int(self.service.spell(1)["mp"])
        with mock.patch.object(self.session.world, "rng",
                               mock.Mock(random=lambda: 0.0)):
            self._cast_spell(1)                      # Cure
        self.assertIsNotNone(self.session.casting)
        # 2% x 20 ranks off the MP that was already paid when the cast started.
        refund = cost * 40 // 100
        self.assertEqual(int(self.session.char["mp_current"]), 500 - cost + refund)
        self.assertIn("Quick Magic!", self.chats())

    def test_master_gift_shortens_the_two_hour_recast(self):
        """The ★Master! gift takes 15 minutes off the one-hour (two-hour) recast."""
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.ability_recasts.clear()
        self._use_war_ability(20)                    # Chainspell
        ready = float(self.session.ability_recasts.get(TWO_HOUR_RECAST_BASE + 20, 0.0))
        # 3600 s base less the gift's 900 s, not the full hour.
        self.assertAlmostEqual(ready - time.time(), 45 * 60, delta=3.0)
        body = bytes(self.session.abil_recast()[4:])
        self.assertGreater(struct.unpack_from("<H", body, 0)[0], 44 * 60)
        # The two-hour cooldown refuses a second use until it is ready.
        self._use_war_ability(20)
        self.assertIn("Chainspell is not ready yet.", self.chats())
        # Another job's one-hour is its own timer: a job change is not blocked by the
        # last job's Chainspell (the client slot 0 then shows the new job's timer).
        self.session.char.update(main_job=3, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self._use_war_ability(18)                     # Benediction
        self.assertIn(TWO_HOUR_RECAST_BASE + 18, self.session.ability_recasts)
        self.assertNotIn("Benediction is not ready yet.", self.chats())

    def test_manafont_makes_cure_free(self):
        self.zone(100)
        self.session.char.update(main_job=4, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(19)                    # Manafont
        before = int(self.session.char["mp_current"])
        self._cast_spell(1)                          # Cure
        self.assertEqual(before, int(self.session.char["mp_current"]))

    def test_convert_swaps_hp_and_mp(self):
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 200
        self.session.char["mp"] = 500
        self.session.char["mp_current"] = 400
        self._use_war_ability(83)                    # Convert
        # The RDM job-point Convert row adds 20% of maximum HP after the swap.
        self.assertEqual(600, int(self.session.char["hp_current"]))
        self.assertEqual(200, int(self.session.char["mp_current"]))

    def test_martyr_and_devotion_use_party_targets(self):
        self.zone(100)
        self.session.char.update(main_job=3, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 1000
        account = self.service.register("healally", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Healally", "race": 1})
        ally = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Healally"))
        ally.set_key(bytes(20))
        ally.logged_in = True
        ally.zone = 100
        ally.targid = 0x401
        ally.pos = list(self.session.pos[:3]) + [0]
        ally.char["hp"] = 1000
        ally.char["hp_current"] = 100
        ally.char["mp"] = 500
        ally.char["mp_current"] = 0
        self.world.sessions[("127.0.0.1", 1235)] = ally
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, ally))
        self._use_war_ability(153, ally.targid)      # Martyr
        self.assertEqual(750, int(self.session.char["hp_current"]))
        self.assertEqual(600, int(ally.char["hp_current"]))
        self._use_war_ability(154, ally.targid)      # Devotion
        self.assertGreater(int(ally.char["mp_current"]), 0)
        self.assertLess(int(self.session.char["hp_current"]), 750)

    def test_feint_weakens_evasion_on_the_next_hit(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(156)                   # Feint
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, False, False)):
            self.world.player_attack(self.session, mob)
        self.assertIn(effects.EVASION_DOWN, mob.effect_state)
        self.assertEqual(0.0, self.session._feint_until)

    def test_bully_applies_evasion_down(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(321)                   # Bully
        self.assertIn(effects.EVASION_DOWN, mob.effect_state)

    def test_monk_boost_chi_blast_and_formless(self):
        self.zone(100)
        self.session.char.update(main_job=2, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(39)                    # Boost
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, False, False)):
            _missed, damage, _critical = self.world.player_attack(self.session, mob)
        self.assertEqual(125, int(damage))
        mob.hp = mob.hp_max = 5000
        self._use_war_ability(82)                    # Chi Blast
        self.assertLess(int(mob.hp), 5000)
        self._use_war_ability(152)                   # Formless Strikes
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, False, False)) as melee:
            self.world.player_attack(self.session, mob)
        self.assertEqual(1.0, melee.call_args.kwargs["ignored_defense"])
        self.assertEqual(0.0, self.session._formless_until)

    def test_puppetmaster_maneuvers_and_automaton_commands(self):
        self.zone(100)
        self.session.char.update(main_job=18, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(136)                   # Activate
        pet = self.session.pet_entity
        self.assertIsNotNone(pet)
        self._use_war_ability(141)                   # Fire Maneuver
        self.session.ability_recasts.clear()
        self._use_war_ability(142)                   # Ice Maneuver
        self.assertEqual(2, len(self.session.maneuvers))
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(138)                   # Deploy
        self.assertEqual(int(mob.id), int(pet.engaged_id))
        self._use_war_ability(140)                   # Retrieve
        self.assertEqual(0, int(pet.engaged_id))
        self.session.char["tp"] = 1000
        pet.tp = 3000
        self._use_war_ability(266)                   # Tactical Switch
        self.assertEqual(3000, int(self.session.char["tp"]))
        self.assertEqual(1000, int(pet.tp))
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 800
        pet.hp = 200
        self._use_war_ability(179)                   # Role Reversal
        self.assertEqual(200, int(self.session.char["hp_current"]))
        self.assertEqual(800, int(pet.hp))
        pet.hp = 100
        self._use_war_ability(322)                   # Maintenance
        self.assertGreater(int(pet.hp), 100)
        mob.enmity = {int(self.session.char["char_id"]): 1000}
        mob.enmity_ve = {}
        self._use_war_ability(180)                   # Ventriloquy
        self.assertEqual(500, int(mob.enmity[int(self.session.char["char_id"])]))
        self.assertEqual(500, int(mob.enmity[int(pet.id)]))

    def test_overdrive_and_astral_flow(self):
        self.zone(100)
        self.session.char.update(main_job=18, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(136)                   # Activate
        pet = self.session.pet_entity
        self._use_war_ability(135)                   # Overdrive
        self.assertGreater(float(pet.overdrive_until), time.time())
        self.session.char.update(main_job=15, main_level=99, sub_job=0, sub_level=0)
        self.world.spawn_pet(self.session, "ifrit", time.time())
        pet = self.session.pet_entity
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 5000
        self._use_war_ability(30)                    # Astral Flow
        before = int(mob.hp)
        self._use_war_ability(91)                    # Blood Pact Rage
        self.assertGreaterEqual(before - int(mob.hp), 600)

    def test_fly_high_resets_jump_recasts(self):
        self.zone(100)
        self.session.char.update(main_job=14, main_level=99, sub_job=0, sub_level=0)
        self.session.ability_recasts[158] = time.time() + 60
        self._use_war_ability(336)                   # Fly High
        self.assertIsNotNone(self.session.effect(effects.FLY_HIGH))
        self.assertNotIn(158, self.session.ability_recasts)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(66)                    # Jump
        self.assertGreater(self.session.ability_recasts.get(158, 0), time.time())
        self.assertLessEqual(self.session.ability_recasts[158] - time.time(), 11)

    def test_fealty_and_spirit_bond(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(157)                   # Fealty
        self.session.add_effect(effects.POISON, duration=60, tick=3)
        self.assertFalse(self.session.has_effect(effects.POISON))
        self.session.char.update(main_job=14, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 1000
        self.world.spawn_pet(self.session, "wyvern", time.time())
        pet = self.session.pet_entity
        pet.hp = 500
        self._use_war_ability(393)                   # Spirit Bond
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.take_damage(100, mob)
        self.assertEqual(950, int(self.session.char["hp_current"]))
        self.assertEqual(450, int(pet.hp))

    def test_larceny_steals_a_target_effect(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.effect_state[effects.REFRESH] = {
            "until": time.time() + 60, "power": 0, "mods": {}}
        self._use_war_ability(328)                   # Larceny
        self.assertIsNotNone(self.session.effect(effects.REFRESH))
        self.assertNotIn(effects.REFRESH, mob.effect_state)

    def test_diabolic_eye_marks_a_window(self):
        self.zone(100)
        self.session.char.update(main_job=8, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(160)                   # Diabolic Eye
        self.assertGreater(float(self.session._diabolic_until), time.time())
        self.assertIn("dark magic is empowered", " ".join(self.chats()))

    def test_feral_howl_terrifies(self):
        self.zone(100)
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(161)                   # Feral Howl
        self.assertIn(effects.STUN, mob.effect_state)

    def test_cascade_converts_tp_to_spell_damage(self):
        self.zone(100)
        self.session.char.update(main_job=4, main_level=99, sub_job=0, sub_level=0)
        self.session.char["tp"] = 3000
        self.session.char["mp_current"] = 500
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(388)                   # Cascade
        self.assertEqual(0, int(self.session.char["tp"]))
        self._cast_spell(159, mob.targid)            # Stone
        self.assertIsNotNone(self.session.casting)
        self.assertEqual(300, int(self.session.casting["cascade_bonus"]))

    def test_dark_seal_marks_the_next_dark_spell(self):
        self.zone(100)
        self.session.char.update(main_job=8, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp_current"] = 500
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(159)                   # Dark Seal
        self._cast_spell(230, mob.targid)            # Bio
        self.assertIsNotNone(self.session.casting)
        self.assertTrue(self.session.casting["dark_seal"])
        self.assertFalse(getattr(self.session, "_dark_seal", False))

    def test_chivalry_and_deep_breathing(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        self.session.char["tp"] = 3000
        self.session.char["mp"] = 1000
        self.session.char["mp_current"] = 100
        self._use_war_ability(158)                   # Chivalry
        self.assertGreater(int(self.session.char["mp_current"]), 100)
        self.assertEqual(0, int(self.session.char["tp"]))
        self.session.char.update(main_job=14, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 5000
        self.world.spawn_pet(self.session, "wyvern", time.time())
        self._use_war_ability(169)                   # Deep Breathing
        before = int(mob.hp)
        self._use_war_ability(318)                   # Smiting Breath
        self.assertGreaterEqual(before - int(mob.hp), 600)

    def test_spontaneity_and_enmity_douse(self):
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp_current"] = 500
        self._use_war_ability(275)                   # Spontaneity
        now = time.time()
        self._cast_spell(1)                         # Cure
        self.assertLess(self.session.casting["finish"] - now, 0.1)
        self.session.casting = None
        self.session.ability_recasts.clear()
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.enmity = {int(self.session.char["char_id"]): 1000}
        mob.enmity_ve = {}
        self._use_war_ability(272)                  # Enmity Douse
        self.assertEqual(500, int(mob.enmity[int(self.session.char["char_id"])]))

    def test_corsair_missing_rolls_apply_their_statuses(self):
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        cases = {106: 318, 107: 319, 111: 323, 114: 326,
                 390: 339, 391: 600, 302: 335, 305: 338}
        for ability_id, status in cases.items():
            self.session.ability_recasts.clear()
            self._use_war_ability(ability_id)
            self.assertIsNotNone(self.session.effect(status),
                                 "roll %d did not apply status %d" % (ability_id, status))

    def test_every_corsair_roll_registers_through_the_action_packet(self):
        """All 31 rolls arrive as 0x01A action 0x09 and put their icon and mods up."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        for ability_id, spec in rolls.ROLLS.items():
            self.session.effect_state.clear()
            self.session.status_effects.clear()
            self.session.ability_recasts.clear()
            self._use_war_ability(ability_id)
            state = self.session.effect(spec.status)
            self.assertIsNotNone(state, "%s did not apply" % spec.name)
            self.assertEqual(spec.mods(int(state["power"])), state["mods"], spec.name)
            self.assertTrue(any(spec.name in line for line in self.chats()), spec.name)
            self.assertIn(0x028, msg_types(self.session), spec.name)
            self.assertGreater(self.session.ability_recasts.get(193, 0), time.time(),
                               spec.name)

    def test_roll_and_double_up_action_carry_the_dice_number(self):
        """The 0x028 result's info is the roll total or the Double-Up increase."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        with mock.patch.object(self.world.rng, "randint", side_effect=[4, 5]):
            self._use_war_ability(109)                   # Samurai Roll -> 4
            message = next(m for m in reversed(self.session.queue)
                           if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x028)
            result = action_results(message)[0]
            self.assertEqual(4, result["info"])
            self.assertEqual(420, result["message"])     # RollMain
            self.assertEqual(109, result["animation"])   # the roll's own animation
            self.assertEqual(4, result["value"])         # "total comes to 4"
            self.session.ability_recasts.clear()
            self._use_war_ability(123)                   # Double-Up adds 5
            message = next(m for m in reversed(self.session.queue)
                           if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x028)
            result = action_results(message)[0]
            self.assertEqual(5, result["info"])
            self.assertEqual(424, result["message"])     # DoubleUp
            self.assertEqual(109, result["animation"])
            self.assertEqual(9, result["value"])         # "increases to 9"
            self.assertEqual(9, int(self.session.effect(321)["power"]))

    def test_double_up_without_an_eligible_roll_returns_no_eligible_roll(self):
        """An expired window is an ability check failure, not a fake Double-Up."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.ability_recasts.clear()
        self._use_war_ability(123)                   # nothing rolled yet
        message = next(m for m in reversed(self.session.queue)
                       if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x028)
        result = action_results(message)[0]
        self.assertEqual(428, result["message"])     # NoEligibleRoll
        self.assertNotIn(194, self.session.ability_recasts)

        with mock.patch.object(self.world.rng, "randint", return_value=4):
            self._use_war_ability(109)               # Samurai Roll 4
        self.session.effect(321)["double_up_until"] = time.time() - 1.0
        self.session.ability_recasts.clear()
        self._use_war_ability(123)                   # window is over
        message = next(m for m in reversed(self.session.queue)
                       if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x028)
        self.assertEqual(428, action_results(message)[0]["message"])
        self.assertNotIn(194, self.session.ability_recasts)

    def test_roll_duration_counts_phantom_roll_gear(self):
        """Chasseur's Gants +3 adds 60 s before the roll is applied."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.give(8, 30, 23570)
        self.session.equipped[6] = (8, 30, 23570)     # hands
        self.session.store_equipment()
        self.assertGreaterEqual(
            int(self.session.combat_mods().get(mod.PHANTOM_DURATION, 0)), 60)
        self.assertGreaterEqual(rolls.duration_for(self.session), 400.0)
        with mock.patch.object(self.world.rng, "randint", return_value=1):
            self._use_war_ability(109)
        state = self.session.effect(321)
        self.assertAlmostEqual(float(state["until"]) - time.time(),
                               rolls.duration_for(self.session), delta=3.0)

    def test_bolters_roll_raises_the_speed_byte(self):
        """Bolter's Roll is movement speed, not the old Ranged Accuracy line."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0,
                                 speed=50)
        self._use_war_ability(118)
        self.assertGreater(self.session.own_speed(), 50)
        self.assertLessEqual(self.session.own_speed(), 80)   # +60% retail cap
        mods = self.session.effect(rolls.ROLLS[118].status)["mods"]
        self.assertIn(mod.MOVE_SPEED_BOLTERS_ROLL, mods)
        self.assertNotIn(mod.RACC, mods)

    def test_corsair_rolls_land_on_party_members(self):
        """A roll is a party buff, not a self buff: everyone in range gets the status."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        account = self.service.register("rollmate", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Rollmate", "race": 1})
        other = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Rollmate"))
        other.set_key(bytes(20))
        other.logged_in = True
        other.zone = 100
        other.pos = list(self.session.pos)
        other.char["hp_current"] = int(other.char["hp"])
        self.world.sessions[("127.0.0.1", 1236)] = other
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, other))
        with mock.patch.object(self.world.rng, "randint", return_value=2):
            self._use_war_ability(109)               # Samurai Roll: lucky II
        for target in (self.session, other):
            state = target.effect(321)
            self.assertIsNotNone(state)
            self.assertEqual(2, int(state["power"]))
            self.assertEqual(rolls.ROLLS[109].mods(2), state["mods"])
        self.assertIn(0x037, msg_types(other))
        other_lines = []
        for message in other.queue:
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
                continue
            other_lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode(
                "ascii", "replace"))
        self.assertIn("You receive the effect of Samurai Roll.", other_lines)

        def party_buff_rows(target):
            rows = {}
            for message in target.queue:
                if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x076:
                    continue
                body = message[4:]
                for index in range(5):
                    offset = index * 48
                    uid = struct.unpack_from("<I", body, offset)[0]
                    if uid:
                        rows[uid] = body[offset + 16:offset + 48]
            return rows

        # The other client's 0x076 carries Onedough's Samurai Roll icon; Onedough's
        # packet carries the other member's copy.
        other_rows = party_buff_rows(other)
        self.assertIn(int(self.session.char["char_id"]), other_rows)
        self.assertIn(321 & 0xFF, other_rows[int(self.session.char["char_id"])])
        self_rows = party_buff_rows(self.session)
        self.assertIn(int(other.char["char_id"]), self_rows)
        self.assertIn(321 & 0xFF, self_rows[int(other.char["char_id"])])
        # A member outside the 7.9-yalm radius is not caught by the same roll.
        other.pos = [self.session.pos[0] + 40.0, self.session.pos[1],
                     self.session.pos[2], 0]
        self.session.ability_recasts.clear()
        with mock.patch.object(self.world.rng, "randint", return_value=3):
            self._use_war_ability(105)               # Chaos Roll
        self.assertIsNotNone(self.session.effect(317))
        self.assertIsNone(other.effect(317))

    def test_corsair_quick_draw_and_crooked_cards(self):
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 1000
        self._use_war_ability(125)                   # Fire Shot
        self.assertLess(int(mob.hp), 1000)
        self._use_war_ability(392)                   # Crooked Cards
        with mock.patch.object(self.world.rng, "randint", return_value=3):
            self._use_war_ability(98)                # Fighter's Roll
        self.assertEqual(4, int(self.session.effect(310)["power"]))

    def test_stealth_and_flashy_shot_statuses(self):
        self.zone(100)
        self.session.char.update(main_job=11, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(165)                   # Stealth Shot
        self.assertEqual(-5, self.session.effect(effects.STEALTH_SHOT)["mods"].get(mod.ENMITY))
        self._use_war_ability(166)                   # Flashy Shot
        state = self.session.effect(effects.FLASHY_SHOT)
        self.assertEqual(10, state["mods"].get(mod.RATT))
        self.assertEqual(50, state["mods"].get(mod.ENMITY))

    def test_convergence_marks_the_next_blue_spell(self):
        self.zone(100)
        self.session.char.update(main_job=16, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp_current"] = 500
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(175)                   # Convergence
        self.assertIsNotNone(self.session.effect(effects.CONVERGENCE))
        self._cast_spell(577, mob.targid)            # Foot Kick
        self.assertIsNotNone(self.session.casting)
        self.assertTrue(self.session.casting["convergence"])
        self.assertIsNone(self.session.effect(effects.CONVERGENCE))

    def test_steal_takes_from_the_monster_table(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        before = {int(row["item_id"]) for row in
                  self.service.inventory(int(self.session.char["id"]))}
        with mock.patch.object(self.world.rng, "random", return_value=0.0):
            self._use_war_ability(41)                # Steal
        after = {int(row["item_id"]) for row in
                 self.service.inventory(int(self.session.char["id"]))}
        self.assertGreater(len(after - before), 0)

    def test_bounty_shot_uses_ranged_weapon(self):
        self.zone(100)
        self.session.char.update(main_job=11, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 1000
        weapons = {2: {"item_id": 1, "skill": 26, "dmg": 20},
                   3: {"item_id": 2, "skill": 26, "dmg": 5}}
        # The mock weapons carry no Ranged Accuracy, so a real roll is at the 95%
        # ranged hit cap.  Pin the roll so this test is about the ranged weapon being
        # used, not about a one-in-twenty miss.
        with mock.patch.object(self.service, "equipped_weapons", return_value=weapons), \
                mock.patch.object(self.world.rng, "random", return_value=0.0):
            self._use_war_ability(285)               # Bounty Shot
        self.assertLess(int(mob.hp), 1000)

    def test_scavenge_adds_ammunition(self):
        self.zone(100)
        self.session.char.update(main_job=11, main_level=99, sub_job=0, sub_level=0)
        before = {int(row["item_id"]) for row in
                  self.service.inventory(int(self.session.char["id"]))}
        with mock.patch.object(self.world.rng, "random", return_value=0.0), \
                mock.patch.object(self.world.rng, "randrange", return_value=0):
            self._use_war_ability(56)                 # Scavenge
        after = {int(row["item_id"]) for row in
                 self.service.inventory(int(self.session.char["id"]))}
        self.assertGreater(len(after - before), 0)

    def test_rayke_and_tomahawk_mark_the_target(self):
        self.zone(100)
        self.session.char.update(main_job=22, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(375)                   # Rayke
        self.assertIn(effects.RAYKE, mob.effect_state)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(150)                   # Tomahawk
        self.assertIn(effects.TOMAHAWK, mob.effect_state)

    def test_mantra_sange_and_steady_wing(self):
        self.zone(100)
        self.session.char.update(main_job=2, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(151)                   # Mantra
        self.assertEqual(20, self.session.effect(88)["mods"].get(mod.HPP))
        self.session.char.update(main_job=13, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(171)                   # Sange
        self.assertEqual(20, self.session.effect(effects.SANGE)["mods"].get(mod.RACC))
        self.session.char.update(main_job=14, main_level=99, sub_job=0, sub_level=0)
        self.world.spawn_pet(self.session, "wyvern", time.time())
        pet = self.session.pet_entity
        self._use_war_ability(295)                   # Steady Wing
        self.assertIn(effects.STONESKIN, pet.effect_state)

    def test_pld_and_run_remaining_statuses(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(92)                    # Rampart
        self.assertEqual(-10, self.session.effect(effects.RAMPART)["mods"].get(mod.DMG))
        self._use_war_ability(394)                   # Majesty
        self.assertEqual(20, self.session.effect(effects.MAJESTY)["mods"].get(mod.CURE_POTENCY_II))
        self.session.char.update(main_job=22, main_level=99, sub_job=0, sub_level=0)
        for ability_id, effect_id in ((369, effects.PFLUG), (371, effects.VALIANCE),
                                       (376, effects.BATTUTA), (373, effects.LIEMENT)):
            self.session.ability_recasts.clear()
            self._use_war_ability(ability_id)
            self.assertIsNotNone(self.session.effect(effect_id))

    def test_rune_fencer_runes_and_lunge(self):
        self.zone(100)
        self.session.char.update(main_job=22, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(357)                   # Rune Enchantment
        self._use_war_ability(358)                   # Ignis
        # The elemental runes share a recast id; clear it for this unit-level check.
        self.session.ability_recasts.clear()
        self._use_war_ability(359)                   # Gelus
        self.assertEqual(2, len(self.session.runes))
        self._use_war_ability(379)                   # Ward
        self.assertTrue(self.session.rune_ward)
        self._use_war_ability(380)                   # Effusion
        self.assertTrue(self.session.rune_effusion)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 1000
        self._use_war_ability(368)                   # Lunge
        self.assertLess(int(mob.hp), 1000)
        self.assertEqual([], self.session.runes)

    def test_libra_reports_the_target(self):
        self.zone(100)
        self.session.char.update(main_job=20, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(265)                   # Libra
        self.assertIn("Libra:", " ".join(self.chats()))

    def test_consume_mana_adds_mp_to_the_next_hit(self):
        self.zone(100)
        self.session.char.update(main_job=8, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp"] = 500
        self.session.char["mp_current"] = 500
        self._use_war_ability(389)                   # Consume Mana
        self.assertEqual(0, int(self.session.char["mp_current"]))
        self.assertEqual(500, int(self.session._consume_mana_bonus))
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, False, False)):
            missed, damage, _critical = self.world.player_attack(self.session, mob)
        self.assertFalse(missed)
        self.assertEqual(600, int(damage))

    def test_summoner_avatar_commands(self):
        self.zone(100)
        self.session.char.update(main_job=15, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp"] = 1000
        self.session.char["mp_current"] = 100
        self.world.spawn_pet(self.session, "ifrit", time.time())
        pet = self.session.pet_entity
        self.assertIsNotNone(pet)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(88)                    # Assault
        self.assertEqual(int(mob.id), int(pet.engaged_id))
        self._use_war_ability(89)                    # Retreat
        self.assertEqual(0, int(pet.engaged_id))
        self._use_war_ability(232)                   # Elemental Siphon
        self.assertGreater(int(self.session.char["mp_current"]), 100)
        pet.hp = 500
        self.session.char["mp_current"] = 100
        self._use_war_ability(296)                   # Mana Cede
        self.assertGreater(int(self.session.char["mp_current"]), 100)
        mob.hp = mob.hp_max = 5000
        self._use_war_ability(385)                   # Apogee
        before = int(mob.hp)
        self._use_war_ability(91)                    # Blood Pact Rage
        self.assertGreaterEqual(before - int(mob.hp), 600)

    def test_dragoon_jumps_and_breaths(self):
        self.zone(100)
        self.session.char.update(main_job=14, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 1000
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 2000
        mob.enmity = {int(self.session.char["char_id"]): 1000}
        mob.enmity_ve = {}
        self._use_war_ability(68)                    # Super Jump
        self.assertLess(int(mob.hp), 2000)
        self.assertEqual(8500, int(mob.enmity[int(self.session.char["char_id"])]))
        self.session.char["tp"] = 1000
        self._use_war_ability(293)                   # Soul Jump
        self.assertEqual(1100, int(self.session.char["tp"]))
        self._use_war_ability(170)                   # Angon
        self.assertIn(effects.DEFENSE_DOWN, mob.effect_state)
        self.world.spawn_pet(self.session, "wyvern", time.time())
        pet = self.session.pet_entity
        self.assertIsNotNone(pet)
        before = int(mob.hp)
        self._use_war_ability(318)                   # Smiting Breath
        self.assertLess(int(mob.hp), before)
        self.session.char["hp_current"] = 100
        self._use_war_ability(319)                   # Restoring Breath
        self.assertGreater(int(self.session.char["hp_current"]), 100)

    def test_perfect_dodge_negates_physical_swings(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(21)                    # Perfect Dodge
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        missed, damage, _critical = self.world.mob_attack(mob, self.session)
        self.assertTrue(missed)
        self.assertEqual(0, damage)

    def test_flee_and_hide_apply_their_effects(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(42)                    # Flee
        self.assertIsNotNone(self.session.effect(effects.QUICKENING))
        self._use_war_ability(43)                    # Hide
        self.assertIsNotNone(self.session.effect(effects.INVISIBLE))

    def test_assassins_charge_forces_the_next_critical(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(155)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        with mock.patch("fanxi_server.game.world.combat.melee",
                        return_value=combat.Hit(100, True, False)) as melee:
            self.world.player_attack(self.session, mob)
        self.assertEqual(1.0, melee.call_args.kwargs["crit_bonus"])
        self.assertTrue(melee.call_args.kwargs["allow_critical"])
        self.assertFalse(self.session._assassin_charge)

    def test_accomplice_and_collaborator_transfer_enmity(self):
        self.zone(100)
        self.session.char.update(main_job=6, main_level=99, sub_job=0, sub_level=0)
        account = self.service.register("thfally", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Thfally", "race": 1})
        ally = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Thfally"))
        ally.set_key(bytes(20))
        ally.logged_in = True
        ally.zone = 100
        ally.targid = 0x401
        ally.pos = list(self.session.pos[:3]) + [0]
        self.world.sessions[("127.0.0.1", 1235)] = ally
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, ally))
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.engaged_id = int(mob.id)
        mob.enmity = {int(self.session.char["char_id"]): 1000,
                      int(ally.char["char_id"]): 400}
        mob.enmity_ve = {}
        self._use_war_ability(84, ally.targid)       # Accomplice
        self.assertEqual(750, int(mob.enmity[int(self.session.char["char_id"])]))
        self.assertEqual(650, int(mob.enmity[int(ally.char["char_id"])]))
        # Accomplice and Collaborator share a recast id in retail; clear it for this
        # unit-level check of the second transfer.
        self.session.ability_recasts.clear()
        self._use_war_ability(236, ally.targid)      # Collaborator
        self.assertEqual(912, int(mob.enmity[int(self.session.char["char_id"])]))
        self.assertEqual(488, int(mob.enmity[int(ally.char["char_id"])]))

    def test_indi_aura_and_entrust(self):
        self.zone(100)
        self.session.char.update(main_job=21, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp_current"] = 500
        self._cast_spell(768)                        # Indi-regen
        self.session.resolve_casting(time.time() + 10)
        self.assertIsNotNone(self.session.effect(539))
        account = self.service.register("geally", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Geally", "race": 1})
        ally = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Geally"))
        ally.set_key(bytes(20)); ally.logged_in = True; ally.zone = 100
        ally.targid = 0x401; ally.pos = list(self.session.pos[:3]) + [0]
        self.world.sessions[("127.0.0.1", 1235)] = ally
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, ally))
        self._use_war_ability(386)                   # Entrust
        self._cast_spell(768, ally.targid)           # Indi-regen on ally
        self.session.resolve_casting(time.time() + 10)
        self.assertIsNotNone(ally.effect(539))
        self.assertIsNone(self.session.effect(effects.ENTRUST))

    def test_a_geo_keeps_one_aura_at_a_time(self):
        """A second Indi- replaces the first, and the Geo- bubble is its own aura."""
        self.zone(100)
        self.session.char.update(main_job=21, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["mp_current"] = 5000
        account = self.service.register("geally", "password123").account
        buddy = self.service.create_character(
            account["id"], {"name": "Geally", "race": 1})
        ally = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(buddy["id"]), "Geally"))
        ally.set_key(bytes(20)); ally.logged_in = True; ally.zone = 100
        ally.targid = 0x401; ally.pos = list(self.session.pos[:3]) + [0]
        self.world.sessions[("127.0.0.1", 1235)] = ally
        group = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(group, ally))

        self._cast_spell(771)                        # Indi-haste
        self.session.resolve_casting(time.time() + 10)
        self.assertIn(geomancy.GEO_HASTE, self.session.effect_state)
        self.assertIn(geomancy.GEO_HASTE, ally.effect_state)

        # The next Indi- takes the last one off both bars, not just the caster's.
        self._cast_spell(770)                        # Indi-refresh
        self.session.resolve_casting(time.time() + 10)
        self.assertIn(geomancy.GEO_REFRESH, self.session.effect_state)
        self.assertIn(geomancy.GEO_REFRESH, ally.effect_state)
        self.assertNotIn(geomancy.GEO_HASTE, self.session.effect_state)
        self.assertNotIn(geomancy.GEO_HASTE, ally.effect_state)

        # The other bubble: a Geo- hex lands on the monster and leaves Indi- alone.
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.engaged_id = int(mob.id)
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        self._cast_spell(818, mob.targid)            # Geo-frailty
        self.session.resolve_casting(time.time() + 10)
        self.assertIn(geomancy.GEO_DEFENSE_DOWN, mob.effect_state)
        self.assertIn(geomancy.GEO_REFRESH, self.session.effect_state)

        # A new Geo- replaces only the Geo- bubble.  Slip is Accuracy down.
        self._cast_spell(821, mob.targid)            # Geo-slip
        self.session.resolve_casting(time.time() + 10)
        self.assertIn(geomancy.GEO_ACCURACY_DOWN, mob.effect_state)
        self.assertNotIn(geomancy.GEO_DEFENSE_DOWN, mob.effect_state)
        self.assertIn(geomancy.GEO_REFRESH, self.session.effect_state)

    def test_geo_luopan_modifier_abilities(self):
        self.zone(100)
        self.session.char.update(main_job=21, main_level=99, sub_job=0, sub_level=0)
        self.session.char["mp"] = 1000
        self.session.char["mp_current"] = 100
        self.world.spawn_pet(self.session, "luopan", time.time())
        pet = self.session.pet_entity
        pet.geo_mp_cost = 100
        pet.hp = pet.hp_max = 1000
        self._use_war_ability(346)                   # Lasting Emanation
        self.assertLess(int(pet.geo_drain), 24)
        self.session.ability_recasts.clear()         # shared recast with Ecliptic
        self._use_war_ability(347)                   # Ecliptic Attrition
        self.assertGreater(int(pet.geo_potency), 100)
        self._use_war_ability(345)                   # Full Circle
        self.assertIsNone(self.session.pet_entity)
        self.assertGreater(int(self.session.char["mp_current"]), 100)
        self.world.spawn_pet(self.session, "luopan", time.time())
        pet = self.session.pet_entity
        self.session.char["mp_current"] = 100
        self._use_war_ability(355)                   # Radial Arcana
        self.assertIsNone(self.session.pet_entity)
        self.assertGreater(int(self.session.char["mp_current"]), 100)
        self._use_war_ability(348)                   # Collimated Fervor
        self.assertIsNotNone(self.session.effect(effects.COLLIMATED_FERVOR))
        self._use_war_ability(386)                   # Entrust
        self.assertIsNotNone(self.session.effect(effects.ENTRUST))

    def test_grand_pas_makes_flourishes_free(self):
        self.zone(100)
        self.session.char.update(main_job=19, main_level=99, sub_job=0, sub_level=0)
        self.session.char["tp"] = 3000
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        self._use_war_ability(341)                   # Grand Pas
        self.session._set_finishing_moves(0)
        self._use_war_ability(204)                   # Animated Flourish, no moves
        self.assertEqual(2, int(self.session._grand_pas_uses))
        self._use_war_ability(205)                   # Desperate Flourish
        self._use_war_ability(207)                   # Violent Flourish
        self.assertIsNone(self.session.effect(effects.GRAND_PAS))

    def test_geo_luopan_abilities(self):
        self.zone(100)
        self.session.char.update(main_job=21, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp"] = 1000
        self.session.char["hp_current"] = 1000
        self._use_war_ability(349)                   # Life Cycle: first use summons
        pet = self.session.pet_entity
        self.assertIsNotNone(pet)
        pet.hp = 100
        pet.hp_max = 500
        self.session._life_cycle(time.time())
        self.assertEqual(750, int(self.session.char["hp_current"]))
        self.assertGreater(int(pet.hp), 100)
        # Mending Halation consumes the Luopan and heals the GEO.
        self.session.char["hp_current"] = 100
        self._use_war_ability(354)
        self.assertIsNone(self.session.pet_entity)
        self.assertGreater(int(self.session.char["hp_current"]), 100)
        # Concentric Pulse consumes a fresh Luopan and deals its HP.
        self.world.spawn_pet(self.session, "luopan", time.time())
        pet = self.session.pet_entity
        pet.hp = 200
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        mob.hp = mob.hp_max = 1000
        before = int(mob.hp)
        self._use_war_ability(353)
        self.assertIsNone(self.session.pet_entity)
        self.assertEqual(before - 200, int(mob.hp))

    def test_benediction_restores_hp_and_removes_ailments(self):
        self.zone(100)
        self.session.char.update(main_job=3, main_level=99, sub_job=0, sub_level=0)
        self.session.char["hp_current"] = 10
        self.session.add_effect(effects.POISON, duration=60, tick=3)
        self._use_war_ability(18)                    # Benediction
        self.assertEqual(int(self.session.char["hp"]),
                         int(self.session.char["hp_current"]))
        self.assertFalse(self.session.has_effect(effects.POISON))

    def test_shield_bash_damages_and_stuns(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = int(mob.id)
        with mock.patch.object(self.world.rng, "random", return_value=0.0):
            self._use_war_ability(46)                # Shield Bash
        self.assertIn(effects.STUN, mob.effect_state)

    def test_invincible_negates_physical_swings(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(22)                    # Invincible
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        missed, damage, _critical = self.world.mob_attack(mob, self.session)
        self.assertTrue(missed)
        self.assertEqual(0, damage)

    def test_sentinel_applies_the_retail_defense_modifier(self):
        self.zone(100)
        self.session.char.update(main_job=7, main_level=99, sub_job=0, sub_level=0)
        self._use_war_ability(48)                    # Sentinel
        state = self.session.effect(effects.SENTINEL)
        self.assertIsNotNone(state)
        self.assertEqual(25, state["mods"].get(mod.DEF_PERCENT))

    def test_warriors_charge_adds_1000_to_the_next_weapon_skill(self):
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 149)     # Warrior's Charge
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)
        now = time.time()
        self.assertGreater(float(self.session._warriors_charge_until), now)
        self.assertIn("1000 TP Bonus", " ".join(self.chats()))
        self.assertEqual(self.session._weaponskill_effective_tp(1000, {}, now), 2000)
        self.session._sekkanoki_until = now + 60.0
        self.assertEqual(self.session._weaponskill_effective_tp(2500, {}, now), 1000)

    def test_bestial_loyalty_and_call_beast_use_the_ammo_jug(self):
        """Bestial Loyalty keeps the jug; Call Beast spends one and still names its pet."""
        self.zone(100)
        self.session.char["main_job"] = 9          # BST
        self.session.char["main_level"] = 99
        self.give(0, 41, 17870, 3)                 # Meat Broth
        self.session.equipped[3] = (0, 41, 17870)
        character_id = int(self.session.char["id"])

        def use(ability_id):
            packet = bytearray(16)
            struct.pack_into("<IHH", packet, 0, character_id, 0,
                             packets.ACTION_JOBABILITY)
            struct.pack_into("<I", packet, 12, ability_id)
            self.session.queue.clear()
            self.session.job_ability(bytes(packet), 0)

        use(387)                                   # Bestial Loyalty
        pet = self.session.pet_entity
        self.assertIsNotNone(pet)
        self.assertEqual(pet.name, "Tiger Familiar")
        self.assertEqual(pet.model, 0x0134)
        self.assertEqual(self.session.pet_jug_item, 17870)
        left = self.db.all(
            "SELECT quantity FROM char_inventory WHERE character_id = ? AND item_id = ?",
            (character_id, 17870))
        self.assertEqual(sum(int(row["quantity"]) for row in left), 3)
        self.assertIn(0x028, msg_types(self.session))
        # Bestial Loyalty has its own 20-minute recast id (94), not Call Beast's (104).
        # The live state writer stores this map, so a relogin can put the timer back.
        self.assertAlmostEqual(
            self.session.ability_recasts.get(94, 0.0), time.time() + 1200, delta=3)

        use(85)                                    # Call Beast
        self.assertIsNotNone(self.session.pet_entity)
        self.assertEqual(self.session.pet_entity.name, "Tiger Familiar")
        left = self.db.all(
            "SELECT quantity FROM char_inventory WHERE character_id = ? AND item_id = ?",
            (character_id, 17870))
        self.assertEqual(sum(int(row["quantity"]) for row in left), 2)
        # The stack survives, so the equipped slot still names the same jug.
        self.assertEqual(self.session.equipped.get(3), (0, 41, 17870))

    def test_call_beast_without_a_jug_reports_it(self):
        self.zone(100)
        self.session.char["main_job"] = 9
        self.session.char["main_level"] = 99
        self.session.equipped.pop(3, None)
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 85)     # Call Beast
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)
        self.assertIsNone(self.session.pet_entity)
        self.assertIn("You must equip a Call Beast jug in your ammo slot.",
                      self.chats())

    def test_call_beast_emptying_the_stack_clears_the_ammo_slot(self):
        self.zone(100)
        self.session.char["main_job"] = 9
        self.session.char["main_level"] = 99
        self.give(0, 42, 17870, 1)
        self.session.equipped[3] = (0, 42, 17870)
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 85)     # Call Beast
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)
        self.assertNotIn(3, self.session.equipped)
        self.assertNotIn(17870, [
            int(row["item_id"]) for row in self.db.all(
                "SELECT item_id FROM char_inventory WHERE character_id = ?",
                (int(self.session.char["id"]),))])
        # The server tells the client the slot is empty, not just that the stack is gone.
        clears = [message for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x050
                  and bytes(message[4:7]) == b"\x00\x03\x00"]
        self.assertTrue(clears)

    def test_home_point_crystal_opens_its_menu(self):
        """Southern San d'Oria #1 is HP index 0: it must open event 8700, not just set the home point."""
        self.zone(230)
        entity = self.world.entity_by_targid(230, 135)
        self.assertIsNotNone(entity)
        self.assertEqual(entity.hp_index, 0)
        self.session.pos = [entity.x, entity.y, entity.z, entity.rot]
        self.session.queue.clear()
        content.npc_talk(self.session, entity)
        events = [m for m in self.session.queue
                  if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x034]
        self.assertEqual(len(events), 1)
        body = events[0][4:]
        self.assertEqual(struct.unpack_from("<H", body, 40)[0], 8700)
        params = struct.unpack_from("<8I", body, 4)
        self.assertEqual(params[0], 1)          # the menu is open
        self.assertEqual(params[7] & 0xFF, 0)   # Southern San d'Oria #1
        self.assertNotIn(0x017, msg_types(self.session))

    def test_home_point_event_number_follows_the_crystal(self):
        """#2 is event 8701 and index 1, so the client gets the right destination page."""
        self.zone(230)
        entity = self.world.entity_by_targid(230, 136)
        self.assertIsNotNone(entity)
        self.assertEqual(entity.hp_index, 1)
        self.session.pos = [entity.x, entity.y, entity.z, entity.rot]
        self.session.queue.clear()
        content.npc_talk(self.session, entity)
        event = next(m for m in self.session.queue
                     if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x034)
        body = event[4:]
        self.assertEqual(struct.unpack_from("<H", body, 40)[0], 8701)
        self.assertEqual(struct.unpack_from("<8I", body, 4)[7] & 0xFF, 1)

    def test_merit_spend_and_refund(self):
        """0x0BE kind 3 raises a merit, spends the points and sends the 0x08C update."""
        self.zone(234)
        self.session.char["merit_points"] = 127
        self.session.char["merit_mode"] = 1
        self.session._merit_counts = {}
        base_hp = int(self.session.char["hp"])
        packet = bytearray(12)
        struct.pack_into("<BBHI", packet, 4, 3, 1, 0x0040 >> 1, 0)
        self.session.queue.clear()
        self.session.merit_edit(bytes(packet))
        self.assertEqual(self.session.char["merit_points"], 126)
        self.assertEqual(self.session.merit_counts()[0x0040], 1)
        self.assertEqual(int(self.session.char["hp"]), base_hp + 10)
        # A recompute (zone-in, gear change or job change) keeps the bought maximum.
        self.session.refresh_vitals()
        self.assertEqual(int(self.session.char["hp"]), base_hp + 10)
        update = next(m for m in self.session.queue
                      if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x08C)
        body = update[4:]
        self.assertEqual(struct.unpack_from("<H", body, 0)[0], 1)
        self.assertEqual(struct.unpack_from("<HBB", body, 4), (0x0040, 2, 1))

        packet = bytearray(12)
        struct.pack_into("<BBHI", packet, 4, 3, 0, 0x0040 >> 1, 0)
        self.session.queue.clear()
        self.session.merit_edit(bytes(packet))
        self.assertEqual(self.session.char["merit_points"], 127)
        self.assertEqual(self.session.merit_counts()[0x0040], 0)
        self.assertEqual(int(self.session.char["hp"]), base_hp)
        self.session.refresh_vitals()
        self.assertEqual(int(self.session.char["hp"]), base_hp)
        update = next(m for m in self.session.queue
                      if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x08C)
        self.assertEqual(struct.unpack_from("<HBB", update[4:], 4), (0x0041, 1, 0))

    def test_zone_in_sends_every_merit_entry(self):
        """Every merit carries its current count and next cost, so rows are selectable."""
        self.session._merit_counts = {}
        self.session.queue.clear()
        self.session.after_zone_in()
        updates = [m for m in self.session.queue
                   if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x08C]
        self.assertEqual(len(updates), (len(merits.MERITS) + 60) // 61)
        total = sum(struct.unpack_from("<H", m[4:], 0)[0] for m in updates)
        self.assertEqual(total, len(merits.MERITS))
        first = updates[0][4:]
        self.assertEqual(struct.unpack_from("<HBB", first, 4), (0x0040, 1, 0))

    def test_zone_in_does_not_spawn_and_first_position_does(self):
        self.assertGreater(len(self.session.entities), 0)
        self.assertNotIn(0x00E, msg_types(self.session))
        self.session.sync_entities()
        spawned = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E]
        # Only the entities inside the sync range are streamed, and all of them are.
        nearby = [entity for entity in self.session.entities
                  if entity.distance_to(*self.session.pos[:3]) <= SYNC_RANGE]
        self.assertEqual(len(spawned), len(nearby))
        self.assertGreater(len(spawned), 0)
        guide = next(entity for entity in self.session.entities
                     if entity.script == content.GUIDE_NPC)
        self.assertIn(guide.targid, self.session.sent_targids)
        spawn = next(message for message in spawned
                     if struct.unpack_from("<I", message, 4)[0] == guide.id)
        header = struct.unpack_from("<H", spawn, 0)[0]
        self.assertEqual(header & 0x1FF, 0x00E)
        self.assertEqual(header >> 9, 0x48 // 4)   # 4-byte sub header + the 0x44 body
        body = spawn[4:]
        self.assertEqual(struct.unpack_from("<H", body, 4)[0], guide.targid)
        self.assertEqual(body[36], 0x40)           # triggerable

    def test_talk_starts_the_guide_quest(self):
        guide = next(entity for entity in self.session.entities
                     if entity.script == content.GUIDE_NPC)
        self.talk(guide)
        self.assertIn(0x017, msg_types(self.session))
        quest = self.service.quest_by_key("pest_control")
        state = self.service.quest_state(self.character["id"], quest["id"])
        self.assertEqual(state["state"], "active")

    def test_talk_requires_range(self):
        guide = next(entity for entity in self.session.entities
                     if entity.script == content.GUIDE_NPC)
        self.session.pos = [guide.x + 50, guide.y, guide.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, guide.id, guide.targid, packets.ACTION_TALK)
        self.session.queue.clear()
        self.session.action(bytes(packet))
        self.assertIn(0x017, msg_types(self.session))
        self.assertIsNone(self.service.quest_state(
            self.character["id"], self.service.quest_by_key("pest_control")["id"]))

    def test_a_merchant_opens_a_shop_and_sells_potions(self):
        merchant = next(entity for entity in self.session.entities if entity.script == "Gekko")
        self.talk(merchant)
        types = msg_types(self.session)
        self.assertIn(0x03E, types)
        self.assertIn(0x03C, types)
        self.assertTrue(self.session.shop_items)
        potion = next(index for index, item in enumerate(self.session.shop_items)
                      if item["item_id"] == 4112)
        price = int(self.session.shop_items[potion]["price"])
        before = next(item["quantity"] for item in self.service.inventory(self.character["id"])
                      if item["item_id"] == 4112)
        # Buy one potion: the gil and the inventory both move by exactly its price.
        packet = bytearray(16)
        struct.pack_into("<IHHB", packet, 4, 1, 0, potion, 0)
        self.session.queue.clear()
        self.session.buy(bytes(packet))
        self.assertIn(0x03F, msg_types(self.session))
        self.assertEqual(self.service.character(self.character["id"])["gil"], 1000 - price)
        inventory = self.service.inventory(self.character["id"])
        bought = next(item for item in inventory if item["item_id"] == 4112)
        self.assertEqual(bought["quantity"], before + 1)

    def test_attack_kill_awards_exp_gil_and_quest_progress(self):
        quest = self.service.quest_by_key("pest_control")
        self.service.start_quest(self.character["id"], quest["id"])
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.name == "Orcish Fodder")
        self.attack(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        # Engaging is not enmity: a mob only fights back once a swing lands (or it is provoked).
        self.assertIsNone(mob.engaged_char_id)
        self.world.player_attack = lambda session, entity, **kwargs: (False, 999, False)
        mob.hp = 1
        self.session.next_attack_at = 0
        self.session.tick(time.time())
        self.assertFalse(mob.alive)
        self.assertGreater(self.service.character(self.character["id"])["exp"], 0)
        self.assertGreater(self.service.character(self.character["id"])["gil"], 1000)
        self.assertEqual(self.service.quest_state(self.character["id"], quest["id"])["progress"], 1)
        types = msg_types(self.session)
        self.assertIn(0x028, types)
        self.assertIn(0x029, types)
        self.assertIn(0x02D, types)
        self.assertIn(0x00E, types)
        self.assertIn(0x061, types)

    def player_animation(self):
        """The newest self-update (0x00D) animation byte, or None if none was queued."""
        for message in reversed(self.session.queue):
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00D:
                return message[4 + 0x1B]
        return None

    def test_engage_draws_the_weapon(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        # 1 is the drawn-weapon battle stance; 0 left the client idle.
        self.assertEqual(self.player_animation(), 1)
        # The engage acknowledgement still names the player and the mob.
        self.assertIn(0x058, msg_types(self.session))
        assist = next(m for m in reversed(self.session.queue)
                      if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x058)
        self.assertEqual(struct.unpack_from("<IIHH", assist, 4),
                         (self.session.char["char_id"], mob.id,
                          self.session.char.get("targid", 0x400), 0))
        update = next(m for m in reversed(self.session.queue)
                      if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x00D)
        # A General-only update carries the animation without re-spawning the entity.
        self.assertEqual(update[4 + 6], packets.SEND_HP)
        # The full self update still carries every section, model included.
        self.assertEqual(self.session.char_update()[4 + 6], 0x1F)

    def test_disengage_sheathes_the_weapon(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        # In melee reach there is nothing to absorb: this press is the player's own.
        self.session.pos = [mob.x + 1.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK_OFF)
        self.session.action(bytes(packet))
        self.assertEqual(self.player_animation(), 0)
        self.assertIsNone(self.session.engaged_id)

    def test_the_status_packet_carries_the_stance(self):
        """0x037's server_status is the same animation byte 0x00D carries at 0x1B.

        It used to be 0 on foot even while engaged.  Every gear batch ends with this
        status block, so each swap told the client to sheathe and the stance refresh that
        followed drew the weapon again: the disengage/re-engage flap.
        """
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.assertEqual(self.session.char_status()[4 + 0x2C], 0)
        self.attack(mob)
        self.assertEqual(self.session.char_status()[4 + 0x2C], 1)
        self.session.disengage()
        self.assertEqual(self.session.char_status()[4 + 0x2C], 0)

    def test_a_gear_batch_keeps_the_weapon_drawn(self):
        """The follow-up to a swap must not contradict the stance the swap keeps.

        ``equipment_sync`` (0x037 among it) and ``assert_stance`` (0x00D = 1) go out in the
        same batch; when the status block said 0 the client sheathed between them, so every
        GearSwap swap looked like a disengage and an engage.
        """
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.queue.clear()
        self.session.equipment_changed = True
        self.session.flush_equipment()
        status = next(message for message in self.session.queue
                      if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x037)
        self.assertEqual(status[4 + 0x2C], 1)
        self.assertEqual(self.player_animation(), 1)

    def attack_off(self, mob):
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK_OFF)
        self.session.action(bytes(packet))

    def test_the_stance_is_drawn_again_after_the_client_sheathes(self):
        """The client lowers the weapon about a second after a draw; the tick redraws it.

        A cast or an equipment batch sheathes the client after the packet that drew it, so
        the stance is refreshed twice a second while the player is engaged.
        """
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.queue.clear()
        self.session.assert_stance()
        self.assertEqual(self.player_animation(), 1)
        self.session.queue.clear()
        # One second later the follow-up draws the weapon without the player pressing
        # /attack again.
        self.session.tick(time.time() + 0.6)
        self.assertEqual(self.player_animation(), 1)
        self.assertIn(0x00D, msg_types(self.session))
        # A disengage cancels the refresh.
        self.session.disengage()
        self.session.queue.clear()
        self.session.tick(time.time() + 3.0)
        self.assertNotIn(0x00D, msg_types(self.session))

    def test_a_dead_mob_keeps_its_claim_until_it_despawns(self):
        """The corpse stays red: the claim owner survives the fight, the hate target does not."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        char_id = int(self.character["char_id"])
        mob.claim_char_id = char_id
        body = packets.entity_update(mob, packets.SEND_HP)
        self.assertTrue(body[6] & 0x02)  # ClaimStatus, so the client reads the owner
        self.assertEqual(struct.unpack_from("<I", body, 40)[0], char_id)
        mob.alive = False
        mob.corpse_until = time.time() + 12.0
        body = packets.entity_update(mob, packets.SEND_HP)
        self.assertEqual(struct.unpack_from("<I", body, 40)[0], char_id)
        mob.reset_mob(time.time())
        body = packets.entity_update(mob, packets.SEND_HP)
        self.assertEqual(struct.unpack_from("<I", body, 40)[0], 0)

    def test_the_client_range_drop_is_absorbed_once_per_engagement(self):
        """The client's own /attack off at four yalms is not a request to stop fighting.

        It sends that packet by itself when its first swing finds the target out of
        reach.  Exactly one per engagement is absorbed and the stance re-asserted; the
        client never repeats it, so this cannot trap the player.
        """
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.attack_off(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertFalse(self.session.client_range_drop)
        self.assertEqual(self.player_animation(), 1)
        self.assertIn(0x058, msg_types(self.session))
        # Retail has no chat line for a kept engagement.
        self.assertEqual(self.chats(), [])

    def test_reengaging_the_same_target_is_quiet(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.queue.clear()
        self.attack(mob)
        self.assertEqual(self.chats().count("You engage %s." % mob.name), 0)
        self.assertEqual(self.session.engaged_id, mob.id)

    def test_reengaging_the_same_target_does_not_rearm_the_client_drop(self):
        """The client re-picks a target it dropped; that is one engagement, not a new one."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.attack_off(mob)                 # the client's own drop, absorbed
        self.attack(mob)                     # the client picks the target back up
        self.attack_off(mob)                 # the player: must break the engagement
        self.assertIsNone(self.session.engaged_id)

    def test_a_second_attack_off_at_range_breaks_the_engagement(self):
        """The 01:26 trap: every press out of range used to be swallowed."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.attack_off(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.attack_off(mob)
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        # Retail says nothing on /attack off; the sheathe is the only feedback.
        self.assertEqual(self.chats(), [])

    def test_attack_beyond_engage_range_draws_then_loses_sight(self):
        """Retail draws on any target; the 30-yalm leash ends it on the next tick."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.session.pos = [mob.x + 31.0, mob.y, mob.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK)
        self.session.queue.clear()
        self.session.action(bytes(packet))
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertEqual(self.player_animation(), 1)
        self.session.queue.clear()
        self.session.tick(time.time())
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You lose sight of the target.", self.chats())

    def test_engaged_target_past_draw_range_is_dropped(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 31.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.session.tick(time.time())
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You lose sight of the target.", self.chats())

    def test_disengage_command_breaks_a_range_engagement(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.session.command(["disengage"])
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You disengage.", self.chats())

    def test_a_dead_target_clears_the_attack_stance(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.queue.clear()
        mob.alive = False
        self.session.tick(time.time())
        self.assertEqual(self.player_animation(), 0)

    def test_mob_draws_its_weapon_when_it_engages(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.session.pos[0:3] = [mob.x, mob.y, mob.z]
        mob.x += 3.0
        mob.level = int(self.session.char["main_level"])
        mob.engaged_char_id = None
        mob.aggro = True
        mob.next_attack_at = time.time() + 100
        self.session.sent_targids.add(mob.targid)
        self.session.queue.clear()
        self.world.advance(time.time())
        self.assertEqual(mob.engaged_char_id, self.character["char_id"])
        self.assertEqual(mob.animation, 1)
        updates = [message[4:] for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E]
        self.assertTrue(any(len(body) > 0x1B and struct.unpack_from("<I", body, 0)[0] == mob.id
                            and body[0x1B] == 1 for body in updates))

    def test_quest_turn_in_pays_once(self):
        quest = self.service.quest_by_key("pest_control")
        self.service.start_quest(self.character["id"], quest["id"])
        self.service.advance_quest(self.character["id"], quest["id"], 3)
        guide = next(entity for entity in self.session.entities
                     if entity.script == content.GUIDE_NPC)
        self.talk(guide)
        state = self.service.quest_state(self.character["id"], quest["id"])
        self.assertEqual(state["state"], "complete")
        character = self.service.character(self.character["id"])
        self.assertEqual(character["gil"], 1300)
        inventory = self.service.inventory(self.character["id"])
        potion = next(item for item in inventory if item["item_id"] == 4112)
        self.assertEqual(potion["quantity"], 4)
        # Talking again must not pay a second time.
        self.talk(guide)
        self.assertEqual(self.service.character(self.character["id"])["gil"], 1300)

    def test_dead_mob_respawns(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        mob.alive = False
        mob.respawn_at = time.time() - 1
        self.session.queue.clear()
        self.world.tick(time.time())
        self.assertTrue(mob.alive)
        self.assertIn(0x00E, msg_types(self.session))

    def test_respawn_forgets_the_previous_skillchain(self):
        """A fresh pop must not inherit the chain the previous life was in.

        Without this, the first weapon skill on a respawned monster can close a chain
        that nobody in this fight opened (the reported "first WS skillchained").
        """
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        now = time.time()
        mob.skillchain = skillchain.SkillchainState(
            props=(4, 0, 0), started=now, until=now + 11.0)
        mob.alive = False
        mob.respawn_at = now - 1
        self.world.tick(now)
        self.assertEqual(mob.hp, mob.hp_max)
        self.assertIsNone(mob.skillchain)

    def test_inventory_packets_include_gil_potion_and_sword(self):
        self.session.queue.clear()
        self.session.queue += self.session.inventory_packets()
        types = msg_types(self.session)
        self.assertIn(0x01C, types)
        self.assertIn(0x01D, types)
        items = [message for message in self.session.queue
                 if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020]
        item_ids = {struct.unpack_from("<H", message, 4 + 8)[0] for message in items}
        self.assertEqual(item_ids, {65535, 4112, 16534})

    def test_empty_wardrobe_eight_is_not_offered_as_storage(self):
        """An empty Wardrobe 8 must not become the equipment window's remembered bag.

        The equipment window keeps the last storage picked and opens on it.  Advertising
        an empty Wardrobe 8 therefore left every item row blank.  Usable size 0 makes the
        client skip the bag; once it holds a piece it is advertised again.
        """
        message = self.session.item_max()
        self.assertEqual(len(message), 100)
        self.assertEqual(struct.unpack_from("<H", message, 4 + 32 + 2 * 16)[0], 0)

        self.give(16, 1, 4112)
        message = self.session.item_max()
        self.assertEqual(struct.unpack_from("<H", message, 4 + 32 + 2 * 16)[0], 81)

    def test_zone_in_marks_every_container_ready(self):
        """The final 0x01D names every bag zone-in streamed, so no bag starts blank."""
        self.session.queue.clear()
        self.session.queue += self.session.inventory_packets()
        state, container, flags = last_sync(self.session)
        self.assertEqual((state, container), (1, 18))
        self.assertEqual(flags, ALL_CONTAINERS)

    def test_container_load_marker_precedes_its_items(self):
        """Each bag's 0x020 rows follow its state-0 0x01D marker, not precede it.

        The client files items into a storage's item list only while that container's
        load window is open.  An item sent before its marker still fills the bag, so
        GearSwap sees it, but the equipment window then lists the Mog Wardrobe as empty.
        Replaying state 0 -> 0x020 -> state 1 to a running client made an open wardrobe's
        list appear; the old item-then-marker order left it blank.
        """
        self.give(13, 1, 26120)
        self.session.queue.clear()
        self.session.queue += self.session.inventory_packets()
        opened = first_item = None
        for index, message in enumerate(self.session.queue):
            kind = struct.unpack_from("<H", message, 0)[0] & 0x1FF
            body = message[4:]
            if kind == 0x01D and body[0] == 0 and body[1] == 13:
                opened = index
            elif kind == 0x020 and body[0x0A] == 13:
                first_item = index
                break
        self.assertIsNotNone(opened)
        self.assertIsNotNone(first_item)
        self.assertLess(opened, first_item)

    def test_item_move_keeps_every_container_ready(self):
        """A move updates two bags; its 0x01D must not clear the other sixteen."""
        self.give(0, 50, 4112)
        self.session.queue.clear()
        packet = bytearray(12)
        struct.pack_into("<IBBBB", packet, 4, 1, 0, 8, 50, 1)
        self.session.item_move(bytes(packet))
        state, _container, flags = last_sync(self.session)
        self.assertEqual(state, 1)
        self.assertEqual(flags, ALL_CONTAINERS)
        placed = {(int(row["container"]), int(row["slot"]))
                  for row in self.service.inventory(self.character["id"])
                  if int(row["item_id"]) == 4112}
        self.assertIn((8, 1), placed)
        self.assertNotIn((0, 50), placed)

    def test_sort_packet_merges_partial_stacks(self):
        """The client's sort (0x03A) combines ammo stacks and reports the new quantities."""
        self.give(0, 20, 21296, 60)  # Chrono Bullet, stack 99
        self.give(0, 30, 21296, 50)
        self.give(0, 31, 21296, 30)
        self.give(0, 40, 17860, 2)  # a different item is left alone
        self.session.queue.clear()
        packet = bytearray(8)
        struct.pack_into("<I", packet, 4, 0)
        self.session.handle(0x03A, bytes(packet))
        rows = {(int(row["slot"])): (int(row["item_id"]), int(row["quantity"]))
                for row in self.db.all(
                    "SELECT slot, item_id, quantity FROM char_inventory "
                    "WHERE character_id = ? AND container = 0",
                    (int(self.character["id"]),))}
        self.assertEqual(rows[20], (21296, 99))
        self.assertEqual(rows[30], (21296, 41))
        self.assertNotIn(31, rows)
        self.assertEqual(rows[40], (17860, 2))
        attrs = [(struct.unpack_from("<H", message, 4 + 8)[0],
                  struct.unpack_from("<I", message, 4)[0],
                  message[4 + 11])
                 for message in self.session.queue
                 if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020]
        self.assertIn((21296, 99, 20), attrs)
        self.assertIn((21296, 41, 30), attrs)
        self.assertIn((0, 0, 31), attrs)
        state, _container, flags = last_sync(self.session)
        self.assertEqual((state, flags), (1, ALL_CONTAINERS))

    def test_sort_packet_does_not_cross_bags_or_overfill(self):
        """A full stack stays full and a sort never reaches into another container."""
        self.give(0, 20, 21296, 99)
        self.give(0, 21, 21296, 1)
        self.give(8, 22, 21296, 5)
        self.session.queue.clear()
        packet = bytearray(8)
        struct.pack_into("<I", packet, 4, 0)
        self.session.handle(0x03A, bytes(packet))
        rows = {(int(row["container"]), int(row["slot"])): int(row["quantity"])
                for row in self.db.all(
                    "SELECT container, slot, quantity FROM char_inventory "
                    "WHERE character_id = ? AND item_id = 21296",
                    (int(self.character["id"]),))}
        self.assertEqual(rows[(0, 20)], 99)
        self.assertEqual(rows[(0, 21)], 1)
        self.assertEqual(rows[(8, 22)], 5)

    def test_inventory_refresh_keeps_every_container_ready(self):
        """A shop refresh clears no bag either."""
        self.session.queue.clear()
        self.session.refresh_inventory()
        state, _container, flags = last_sync(self.session)
        self.assertEqual(state, 1)
        self.assertEqual(flags, ALL_CONTAINERS)

    def test_job_command_swaps_sets_and_tidies_the_bags(self):
        """//job stores the old job, pulls the new one and leaves a clean inventory."""
        self.session.char["jobs"] = {4: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 4   # BLM
        self.session.char["main_level"] = 99
        self.db.execute("DELETE FROM char_inventory WHERE character_id = ? AND container = 0",
                        (int(self.character["id"]),))
        old_set = {4: 23898, 5: 23943, 6: 23988, 7: 24033}  # BLM AF/reforged
        for offset, (kind, item_id) in enumerate(sorted(old_set.items())):
            self.give(0, 10 + offset, item_id)
        self.session.equipped = {
            kind: (0, 10 + offset, item_id)
            for offset, (kind, item_id) in enumerate(sorted(old_set.items()))}
        self.service.save_equipment(int(self.character["id"]), self.session.equipped)
        self.give(0, 50, 2971, 99)   # working stock stays visible
        self.give(8, 60, 21685)      # RUN great sword lives in a wardrobe
        self.give(0, 52, 23895)      # WAR head, no slip, should be tidied away
        for item_id in (23917, 23962, 24007, 24052, 24097):  # RUN set on slips
            self.db.execute(
                "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                "VALUES (?, ?, 1, 32)", (int(self.character["id"]), item_id))
        self.session.queue.clear()

        self.session.command("job run".split())

        self.assertEqual(self.session.char["main_job"], 22)
        stored = self.stored()
        for item_id in old_set.values():
            self.assertIn(item_id, stored)
        for item_id in (23917, 23962, 24007, 24052, 24097):
            self.assertNotIn(item_id, stored)
        rows = self.service.inventory(int(self.character["id"]))
        bag_ids = {int(row["item_id"]) for row in rows}
        self.assertTrue(set(old_set.values()).isdisjoint(bag_ids))
        self.assertIn(21685, bag_ids)
        self.assertEqual(self.session.equipped[0], (8, 60, 21685))
        self.assertEqual(self.session.equipped[4][2], 23917)
        self.assertEqual(self.session.equipped[5][2], 23962)
        inventory = {int(row["item_id"]) for row in rows if int(row["container"]) == 0}
        self.assertIn(2971, inventory)
        self.assertNotIn(23895, inventory)
        self.assertIn(23895, stored)
        self.assertTrue(any("Stored 5 items RUN cannot equip" in line for line in self.chats()))
        self.assertTrue(any("Pulled 5 RUN items into the wardrobes" in line
                            for line in self.chats()))

    def test_job_command_pulls_jse_capes_from_the_locker(self):
        """Capes with distinct augment blocks come out together and keep their block."""
        self.session.char["jobs"] = {1: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 1
        self.session.char["main_level"] = 99
        self.db.execute("DELETE FROM char_inventory WHERE character_id = ?",
                        (int(self.character["id"]),))
        blocks = {
            26267: capes.encode("dd", "RUN"),
            26246: capes.encode("tp", "WAR"),
        }
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 26267, ?, 1)", (int(self.character["id"]), blocks[26267]))
        # The old job's cape starts loose in a wardrobe; the job change must put it
        # into the locker, not leave it in a bag for the new job.
        self.give(10, 5, 26246)
        self.db.execute(
            "UPDATE char_inventory SET extra = ? WHERE character_id = ? "
            "AND container = 10 AND slot = 5",
            (blocks[26246], int(self.character["id"])))
        self.session.queue.clear()

        self.session.command("job run".split())

        rows = {int(row["item_id"]): row for row in self.service.inventory(
            int(self.character["id"])) if int(row["item_id"]) in blocks}
        self.assertEqual(set(rows), {26267})
        self.assertEqual(bytes(rows[26267]["extra"]), blocks[26267])
        old_cape = self.db.one(
            "SELECT quantity, extra FROM char_locker WHERE character_id = ? "
            "AND item_id = 26246", (int(self.character["id"]),))
        self.assertEqual(int(old_cape["quantity"]), 1)
        self.assertEqual(bytes(old_cape["extra"]), blocks[26246])
        self.assertTrue(any("Pulled 1 RUN item into the wardrobes (1 in the locker)." in line
                            for line in self.chats()))

    def test_job_command_resends_command_data_after_the_new_gear(self):
        """The final 0x0AC follows the new outfit, so the HUD can rebuild on it.

        The HUD's weapon-skill and ability windows are built from the client's 0x0AC
        command-list update.  `//job` has to send that update again after the storage pull
        and auto-equip; sending only the job bundle's early copy leaves the window on the
        old weapon's skills.
        """
        self.session.char["jobs"] = {4: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 4
        self.session.char["main_level"] = 99
        self.give(8, 60, 21685)   # RUN great sword in a wardrobe
        self.session.queue.clear()

        self.session.command("job run".split())

        types = msg_types(self.session)
        self.assertIn(0x01B, types)
        self.assertIn(0x0AC, types)
        last_equip = max(index for index, kind in enumerate(types) if kind == 0x050)
        last_commands = max(index for index, kind in enumerate(types) if kind == 0x0AC)
        self.assertLess(last_equip, last_commands)
        info = next(message for message in self.session.queue
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01B)
        self.assertEqual(int(info[4 + 4]), 22)

    def test_moogle_job_change_resends_command_data_after_the_gear(self):
        """The Moogles' Change Job path sends the same gear-then-commands order."""
        self.session.char["jobs"] = {19: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 19
        self.session.char["main_level"] = 99
        self.session.equipped = {}
        self.give(0, 10, 21685)   # RUN great sword, in the inventory
        self.session.queue.clear()

        self.session.myroom_job(bytes((0x00, 0x10, 0, 0, 22, 0)))

        types = msg_types(self.session)
        self.assertIn(0x01B, types)
        self.assertIn(0x0AC, types)
        last_equip = max(index for index, kind in enumerate(types) if kind == 0x050)
        last_commands = max(index for index, kind in enumerate(types) if kind == 0x0AC)
        self.assertLess(last_equip, last_commands)
        info = next(message for message in self.session.queue
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01B)
        self.assertEqual(int(info[4 + 4]), 22)

    def test_locker_keeps_distinct_cape_builds_apart(self):
        """Two copies of one item id survive store/grab with their own extdata."""
        tank = capes.encode("tank", "RUN")
        dd = capes.encode("dd", "RUN")
        self.give(0, 50, 26267)
        self.give(0, 51, 26267)
        self.db.execute(
            "UPDATE char_inventory SET extra = ? WHERE character_id = ? "
            "AND container = 0 AND slot = 50",
            (tank, int(self.character["id"])))
        self.db.execute(
            "UPDATE char_inventory SET extra = ? WHERE character_id = ? "
            "AND container = 0 AND slot = 51",
            (dd, int(self.character["id"])))
        self.session.queue.clear()

        self.session.command("locker store jsecapes".split())
        locker = [(bytes(row["extra"]), int(row["quantity"])) for row in self.db.all(
            "SELECT extra, quantity FROM char_locker WHERE character_id = ? "
            "AND item_id = 26267", (int(self.character["id"]),))]
        self.assertEqual(sorted(locker), sorted([(tank, 1), (dd, 1)]))

        self.session.command("locker grab jsecapes".split())
        rows = [(bytes(row["extra"]), int(row["quantity"])) for row in self.service.inventory(
            int(self.character["id"])) if int(row["item_id"]) == 26267]
        self.assertEqual(sorted(rows), sorted([(tank, 1), (dd, 1)]))

    def test_storage_stores_job_gear_and_lockers_the_pieces_without_a_slip(self):
        """//storage store nin slips what it can and lockers the NIN pieces that cannot."""
        for container, slot, item_id in ((0, 50, 23907), (1, 5, 23975), (8, 9, 23566)):
            self.give(container, slot, item_id)
        self.give(0, 51, 21906)  # Kikoku: NIN, but no storage slip
        self.give(0, 52, 25491)  # Ninja Nodowa: NIN, but no storage slip
        self.give(0, 53, 23895)  # WAR-only: not NIN gear
        self.give(0, 54, 21602)  # all jobs: NIN can wear it, but it is not NIN gear
        self.session.queue.clear()
        self.session.command("storage store nin".split())
        self.assertEqual(self.stored(), {23907: (1, 32), 23975: (1, 33), 23566: (1, 30)})
        self.assertEqual(self.locker_stored(), {21906: 1, 25491: 1})
        rows = self.service.inventory(self.character["id"])
        bag = {(int(row["container"]), int(row["slot"])) for row in rows}
        for source in ((0, 50), (1, 5), (8, 9), (0, 51), (0, 52)):
            self.assertNotIn(source, bag)
        for left in ((0, 53), (0, 54)):
            self.assertIn(left, bag)
        self.assertFalse(any(int(row["container"]) == 2 for row in rows))

        parsed = [struct.unpack_from("<IIHBB", message, 4) for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020]
        cleared = {(p[3], p[4]) for p in parsed if not p[2]}
        self.assertEqual(cleared, {(0, 50), (1, 5), (8, 9), (0, 51), (0, 52)})
        self.assertEqual([p for p in parsed if p[2]], [])
        sync = next(struct.unpack_from("<BB2xI", message, 4)
                    for message in reversed(self.session.queue)
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01D)
        self.assertEqual(sync[0], 1)
        self.assertEqual(sync[2], ALL_CONTAINERS)
        self.assertIn("Stored 5 NIN items (3 on slips, 2 in the locker).", self.chats())

    def test_storage_slip_table_matches_the_known_sets(self):
        """The reforged NIN sets are on slips 32/33/30; RMEA weapons are not on any slip."""
        for item_id, slip in ((23907, 32), (23975, 33), (23566, 30)):
            row = self.db.one("SELECT slip FROM item_storage WHERE item_id = ?", (item_id,))
            self.assertIsNotNone(row, "item %d has no slip" % item_id)
            self.assertEqual(int(row["slip"]), slip)
        for item_id in (21906, 25491):
            self.assertIsNone(self.db.one(
                "SELECT 1 FROM item_storage WHERE item_id = ?", (item_id,)))

    def test_storage_leaves_equipped_gear_on(self):
        """A worn NIN piece is not teleported onto a slip behind the player's back."""
        self.give(0, 50, 23907)
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, 4, 0, 50, 23907)",
            (int(self.character["id"]),))
        self.session.queue.clear()
        self.session.command("storage store nin".split())
        rows = self.service.inventory(self.character["id"])
        self.assertIn((0, 50, 23907),
                      {(int(r["container"]), int(r["slot"]), int(r["item_id"])) for r in rows})
        self.assertEqual(self.stored(), {})
        self.assertIn("No NIN gear left in your bags.", self.chats())
        self.assertIn("Left 1 equipped piece on.", self.chats())

    def test_storage_grab_returns_gear_to_the_bags(self):
        """//storage grab nin puts the set back in the inventory, ready to wear."""
        self.give(0, 50, 23907)
        self.give(8, 5, 23975)
        self.session.command("storage store nin".split())
        self.session.queue.clear()
        self.session.command("storage grab nin".split())
        self.assertEqual(self.stored(), {})
        rows = self.service.inventory(self.character["id"])
        carried = {int(row["item_id"]) for row in rows}
        self.assertTrue({23907, 23975} <= carried)
        self.assertTrue(any(line.startswith("Pulled 2 NIN items into the wardrobes")
                            for line in self.chats()))

    def test_storage_grab_can_filter_or_empty_storage(self):
        """grab nin is selective; grab all is the way to empty every slip."""
        for item_id in (23907, 23895):
            self.db.execute(
                "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                "VALUES (?, ?, 1, 32)", (int(self.character["id"]), item_id))
        self.session.queue.clear()
        self.session.command("storage grab nin".split())
        self.assertEqual(self.stored(), {23895: (1, 32)})
        self.assertTrue(any(line.startswith("Pulled 1 NIN item into the wardrobes")
                            for line in self.chats()))

        self.session.queue.clear()
        self.session.command("storage grab all".split())
        self.assertEqual(self.stored(), {})
        rows = self.service.inventory(self.character["id"])
        carried = {int(row["item_id"]) for row in rows}
        self.assertTrue({23907, 23895} <= carried)

    def test_storage_grab_uses_a_wardrobe_when_inventory_is_full(self):
        """A full inventory pushes the grab into wardrobe 1 instead of failing."""
        for slot in range(0, 81):
            self.give(0, slot, 4112)
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 23907, 1, 32)", (int(self.character["id"]),))
        self.session.queue.clear()
        self.session.command("storage grab nin".split())
        rows = self.service.inventory(self.character["id"])
        placed = [(int(row["container"]), int(row["slot"])) for row in rows
                  if int(row["item_id"]) == 23907]
        self.assertEqual(placed, [(8, 1)])

    def test_storage_status_lists_the_slips(self):
        self.give(0, 50, 23907)
        self.session.command("storage store nin".split())
        self.session.queue.clear()
        self.session.command("storage".split())
        self.assertIn("Storage: 1 item on slips; locker 0/9999 slots.", self.chats())
        self.assertIn("WAR: 0 stored, 0 items in your bags for other jobs.", self.chats())
        self.assertIn("Use //storage organize to put the other jobs away and bring WAR out.",
                      self.chats())

    def test_storage_accepts_the_double_slash_chat_form(self):
        """//storage reaches the same command as the host's "!storage" say form."""
        self.give(0, 50, 23907)
        text = "//storage store nin"
        payload = bytearray(2 + len(text) + 1)
        payload[2:2 + len(text)] = text.encode("ascii")
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x0B5)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x0B5, bytes(payload))))
        self.assertEqual(self.stored(), {23907: (1, 32)})
        self.assertIn("Stored 1 NIN item (1 on slips).", self.chats())

    def test_storage_accepts_the_host_wire_form(self):
        """The host forwards //commands as "!command" say lines, which must still run."""
        self.give(0, 50, 23907)
        text = "!storage store nin"
        payload = bytearray(2 + len(text) + 1)
        payload[2:2 + len(text)] = text.encode("ascii")
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x0B5)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x0B5, bytes(payload))))
        self.assertEqual(self.stored(), {23907: (1, 32)})
        self.assertIn("Stored 1 NIN item (1 on slips).", self.chats())

    def test_storage_organize_keeps_only_the_current_jobs_gear_out(self):
        """organize stores every other job and pulls the current job's set into wardrobes."""
        self.session.char["jobs"] = {1: (99, 0), 4: (99, 0), 13: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 13   # NIN
        self.session.char["main_level"] = 99
        for slot, item_id in enumerate((23907, 23975, 23566), start=50):
            self.give(0, slot, item_id)
        self.give(0, 60, 21757)      # WAR-only, no slip: goes to the locker
        self.give(0, 61, 21602)      # all jobs: every job can wear it, so it stays
        self.give(0, 62, 2971, 99)   # working stock stays visible
        for item_id in (23917, 23962):   # RUN set already on its slips
            self.db.execute(
                "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                "VALUES (?, ?, 1, 32)", (int(self.character["id"]), item_id))
        nin_cape = capes.encode("tp", "NIN")
        run_cape = capes.encode("dd", "RUN")
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 26258, ?, 1)", (int(self.character["id"]), nin_cape))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 26267, ?, 1)", (int(self.character["id"]), run_cape))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 17860, 99)",
            (int(self.character["id"]),))   # BST jug stack: never auto-pulled
        self.session.queue.clear()

        self.session.command("storage organize".split())

        rows = self.service.inventory(int(self.character["id"]))
        carried = {int(row["item_id"]): row for row in rows}
        self.assertTrue({23907, 23975, 23566, 26258} <= set(carried))
        self.assertEqual(bytes(carried[26258]["extra"]), nin_cape)
        self.assertNotIn(17860, carried)
        self.assertIn(21602, carried)
        self.assertIn(2971, carried)
        # The RUN set and cape stay stored; the WAR head has no slip and went to the locker.
        self.assertEqual(self.stored(), {23917: (1, 32), 23962: (1, 32)})
        self.assertEqual(self.locker_stored(), {26267: 1, 21757: 1, 17860: 99})
        self.assertIn("Stored 1 item NIN cannot equip (1 in the locker).", self.chats())
        self.assertIn("Pulled 1 NIN item into the wardrobes (1 in the locker).", self.chats())
        self.assertIn("Tidied 4 NIN items into the wardrobes.", self.chats())

    def test_storage_list_reports_both_stores(self):
        """//storage list <job> names slip and locker contents; all groups by job."""
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 23907, 1, 32)", (int(self.character["id"]),))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
            "VALUES (?, 26258, ?, 1)",
            (int(self.character["id"]), capes.encode("tp", "NIN")))
        self.session.queue.clear()

        self.session.command("storage list nin".split())

        text = "\n".join(self.chats())
        self.assertIn("Hachiya Hatsuburi +4 x1 [slip]", text)
        self.assertIn("Andartia's Mantle x1 [locker]", text)
        self.session.queue.clear()
        self.session.command("storage list all".split())
        self.assertIn("NIN 2", "\n".join(self.chats()))

    def test_recycle_bin_holds_and_restores_a_drop(self):
        """Dropping moves the stack to container 17; restore puts it back."""
        self.give(0, 50, 4112, 3)
        self.session.queue.clear()
        self.session.command("recycle drop inventory 50 2".split())
        rows = self.service.inventory(int(self.character["id"]))
        source = [row for row in rows if int(row["container"]) == 0
                  and int(row["slot"]) == 50]
        self.assertEqual([int(row["quantity"]) for row in source], [1])
        recycled = [row for row in rows if int(row["container"]) == 17]
        self.assertEqual([(int(row["slot"]), int(row["item_id"]), int(row["quantity"]))
                          for row in recycled], [(1, 4112, 2)])
        self.assertTrue(recycled[0]["dropped_at"])
        self.assertTrue(any("Recycle Bin for 30 days" in line for line in self.chats()))

        self.session.queue.clear()
        self.session.command("recycle restore 1".split())
        rows = self.service.inventory(int(self.character["id"]))
        self.assertFalse(any(int(row["container"]) == 17 for row in rows))
        potions = [int(row["quantity"]) for row in rows
                   if int(row["container"]) == 0 and int(row["item_id"]) == 4112]
        self.assertEqual(sum(potions), 5)   # 3 dropped stack + the starter 2
        self.assertIn("Restored 2 items from the Recycle Bin.", self.chats())

    def test_magic_bag_lists_bags_slips_and_locker(self):
        self.give(0, 50, 4112, 2)
        self.db.execute(
            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
            "VALUES (?, 23907, 1, 32)", (int(self.character["id"]),))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) "
            "VALUES (?, 26258, 3)", (int(self.character["id"]),))
        rows = self.service.character_all_items(int(self.character["id"]))
        sources = {row["source"] for row in rows}
        self.assertEqual(sources, {"bag", "slip", "locker"})
        self.assertTrue(any(row["source"] == "slip" and row["item_id"] == 23907
                            for row in rows))
        self.assertTrue(any(row["source"] == "locker" and row["item_id"] == 26258
                            and row["quantity"] == 3 for row in rows))

    def test_item_move_command_moves_one_bag_slot(self):
        self.give(0, 50, 4112, 2)
        self.session.queue.clear()
        self.session.command("item move inventory 50 safe 1".split())
        rows = self.service.inventory(int(self.character["id"]))
        safe = [row for row in rows if int(row["container"]) == 1]
        self.assertEqual([(int(row["item_id"]), int(row["quantity"])) for row in safe],
                         [(4112, 1)])
        inventory = [row for row in rows if int(row["container"]) == 0
                     and int(row["slot"]) == 50]
        self.assertEqual([int(row["quantity"]) for row in inventory], [1])

    def test_recycle_blocks_equip_and_use(self):
        """A recycled item is inert until it is restored."""
        self.give(17, 1, 4112, 2)
        self.session.queue.clear()
        self.session.item_use(item_use_packet(1, 17))
        self.assertIn("Take that item out of the Recycle Bin before using it.", self.chats())
        self.assertTrue(any(int(row["quantity"]) == 2 for row in self.service.inventory(
            int(self.character["id"])) if int(row["container"]) == 17))

        packet = bytearray(12)
        packet[4], packet[5], packet[6] = 1, 15, 17
        self.session.queue.clear()
        self.session.equip(bytes(packet))
        self.assertIn("Take that item out of the Recycle Bin before wearing it.", self.chats())

    def test_recycle_purges_only_expired_rows(self):
        self.db.execute(
            "INSERT INTO char_inventory "
            "(character_id, container, slot, item_id, quantity, dropped_at) "
            "VALUES (?, 17, 1, 4112, 1, '2000-01-01T00:00:00+00:00'), "
            "(?, 17, 2, 4113, 1, '2999-01-01T00:00:00+00:00')",
            (int(self.character["id"]), int(self.character["id"])))
        removed = self.service.purge_recycle(int(self.character["id"]))
        self.assertEqual(removed, 1)
        rows = [row for row in self.service.inventory(int(self.character["id"]))
                if int(row["container"]) == 17]
        self.assertEqual([int(row["slot"]) for row in rows], [2])

    def test_storage_moves_reopen_a_wardrobe_before_its_rows(self):
        """A wardrobe list is only filled while its state-0 0x01D window is open.

        Without the marker the client keeps the previous wardrobe's list and the
        equipment window looks empty even though the server moved the item.
        """
        self.give(8, 9, 23566)    # NIN piece to store
        self.give(8, 10, 23895)   # WAR piece that stays in the wardrobe
        self.session.queue.clear()

        self.session.command("storage store nin".split())

        state_zero = None
        first_row = None
        for index, message in enumerate(self.session.queue):
            kind = struct.unpack_from("<H", message, 0)[0] & 0x1FF
            if kind == 0x01D:
                state, container, _flags = struct.unpack_from("<BB2xI", message, 4)
                if state == 0 and container == 8:
                    state_zero = index
            elif kind == 0x020 and first_row is None:
                _quantity, _price, item_id, container, _slot = struct.unpack_from(
                    "<IIHBB", message, 4)
                if container == 8 and item_id:
                    first_row = index
        self.assertIsNotNone(state_zero, "wardrobe 8 was not reopened")
        self.assertIsNotNone(first_row, "wardrobe 8 rows were not sent")
        self.assertLess(state_zero, first_row)
        self.assertIn("Stored 1 NIN item (1 on slips).", self.chats())

    def test_storage_organize_tidies_job_gear_out_of_the_mog_safe(self):
        """The tidy searches the Safe/Satchel/Sack/Case too, not just the inventory."""
        self.session.char["jobs"] = {13: (99, 0)}
        self.session.char["main_job"] = 13
        self.session.char["main_level"] = 99
        self.give(1, 5, 23907)   # NIN head sitting in the Mog Safe
        self.session.queue.clear()

        self.session.command("storage organize".split())

        rows = [(int(row["container"]), int(row["slot"])) for row in self.service.inventory(
            int(self.character["id"])) if int(row["item_id"]) == 23907]
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0][0], (8, 10, 11, 12, 13, 14, 15, 16))
        self.assertIn("Tidied 1 NIN item into the wardrobes.", self.chats())

    def test_storage_store_all_puts_every_other_jobs_gear_away(self):
        """//storage store all is the store half of organize for the current job."""
        self.session.char["jobs"] = {1: (99, 0), 13: (99, 0)}
        self.session.char["main_job"] = 1   # WAR
        self.session.char["main_level"] = 99
        self.give(0, 50, 23907)   # NIN head, has a slip
        self.give(0, 51, 26258)   # NIN cape, no slip
        self.give(0, 52, 23895)   # WAR head, stays
        self.give(0, 53, 21602)   # all jobs, stays
        self.session.queue.clear()

        self.session.command("storage store all".split())

        self.assertEqual(self.stored(), {23907: (1, 32)})
        self.assertEqual(self.locker_stored(), {26258: 1})
        rows = self.service.inventory(int(self.character["id"]))
        bag = {(int(row["container"]), int(row["slot"]))
               for row in rows if int(row["container"]) == 0}
        self.assertIn((0, 52), bag)
        self.assertIn((0, 53), bag)
        self.assertIn("Stored 2 items you cannot equip as WAR (1 on slips, 1 in the locker).",
                      self.chats())

    def test_working_stock_refills_and_merges_stacks(self):
        """Utsusemi tools and medicines are topped up from the hidden locker."""
        self.give(0, 50, 2971, 98)
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 2971, 5)",
            (int(self.character["id"]),))
        moved = self.service.refill_working_stock(int(self.character["id"]))
        self.assertEqual(sum(int(move["added"]) for move in moved), 1)
        rows = [row for row in self.service.inventory(self.character["id"])
                if int(row["item_id"]) == 2971]
        self.assertEqual([(int(row["slot"]), int(row["quantity"])) for row in rows], [(50, 99)])
        self.assertEqual(self.locker_stored(), {2971: 4})

    def test_utsusemi_tool_is_consumed_and_refilled(self):
        self.give(0, 50, 2971, 99)
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 2971, 33)",
            (int(self.character["id"]),))
        self.session.char["main_job"] = 13
        # Ninjutsu costs no MP: a 99 NIN with an empty MP pool can still cast it.
        self.session.char["mp"] = 404
        self.session.char["mp_current"] = 0
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 338)
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        rows = [row for row in self.service.inventory(self.character["id"])
                if int(row["item_id"]) == 2971]
        self.assertEqual(sum(int(row["quantity"]) for row in rows), 99)
        self.assertEqual(self.locker_stored(), {2971: 32})
        start = next(message for message in self.session.queue
                     if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028)
        result = action_results(start)[0]
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_STARTS_CASTING)
        self.assertEqual(result["animation"], 338)  # Utsusemi Ichi's own cast motion
        self.assertEqual(int(self.session.char["mp_current"]), 0)

    def test_ninjutsu_casts_without_mp(self):
        """Monomi: Ichi needs no MP and no tool; the old spell row cost 2553 MP."""
        self.session.char["main_job"] = 13
        self.session.char["mp"] = 404
        self.session.char["mp_current"] = 0
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 318)
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        start = next(message for message in self.session.queue
                     if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028)
        result = action_results(start)[0]
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_STARTS_CASTING)
        self.assertEqual(result["animation"], 356)  # Monomi's own cast motion
        self.assertEqual(int(self.session.char["mp_current"]), 0)

    def test_cure_potency_reads_the_gear_worn_at_the_finish(self):
        """The midcast set lands after the action packet, so the heal reads it at finish.

        GearSwap (and the Fanxi host) sends the action first and the midcast 0x050 burst
        right behind it.  Freezing the amount in cast_magic would roll the Cure with the
        fast-cast set's 0% potency, which is why a RDM's Daybreak/Telchine cure set did
        nothing.  40% potency turns Cure III's 237 into 331.
        """
        self.session.char["main_job"] = 5      # RDM
        self.session.char["main_level"] = 99
        self.session.char["mp"] = 999
        self.session.char["mp_current"] = 999
        self.session.refresh_vitals()
        self.session.char["hp_current"] = 100
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 3)
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        self.assertEqual(self.session.casting["amount"], 237)   # no cure potency yet
        # The midcast set arrives before the cast bar finishes, the way the host sends it.
        self.give(0, 10, 22040)   # Daybreak: "Cure" potency +30%
        self.give(0, 11, 27048)   # Telchine Gloves: "Cure" potency +10%
        self.session.equip(bytes((0x50, 4, 0, 0, 10, 0, 0, 0)))
        self.session.equip(bytes((0x50, 4, 0, 0, 11, 6, 0, 0)))
        self.session.flush_equipment()
        self.session.resolve_casting(time.time() + 10)
        self.assertEqual(int(self.session.char["hp_current"]), 431)
        results = [result for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028
                   for result in action_results(message)]
        healed = next(result for result in results
                      if result["message"] == packets.MESSAGE_MAGIC_RECOVERS_HP)
        self.assertEqual(healed["value"], 331)

    def test_trust_magic_calls_an_alter_ego(self):
        """A Trust spell spends no MP and spawns a Trust-flagged 0x00E plus 0x067."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, 896)
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        start = next(message for message in self.session.queue
                     if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028)
        result = action_results(start)[0]
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_STARTS_CASTING)
        # Every Trust spell's client animation is 939; the start must not fall back to
        # Cure's pose (1) and then switch at the finish.
        self.assertEqual(result["animation"], 939)
        self.assertEqual(int(self.session.char["mp_current"]), int(self.session.char["mp"]))

        self.session.resolve_casting(time.time() + 3)
        self.assertEqual(len(self.session.trust_entities), 1)
        trust = self.session.trust_entities[0]
        self.assertEqual(trust.name, "Shantotto")
        self.assertEqual(trust.kind, "trust")
        self.assertEqual(trust.targid, 0x700)
        self.assertEqual(trust.model, 3000)
        self.assertEqual(trust.job, 4)
        self.assertEqual(trust.race, 5)              # Tarutaru, from the LSB species
        self.assertEqual(trust.level, 99)
        self.assertEqual(trust.hp_max, 1111)
        self.assertGreater(trust.mp_max, 1000)
        self.assertIn(trust, self.world.entities_for_zone(100))
        self.assertIn("Shantotto joins you.", self.chats())

        spawned = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E
                   and struct.unpack_from("<I", message, 4)[0] == trust.id]
        self.assertTrue(spawned)
        body = spawned[-1][4:]
        self.assertEqual(body[36] & 0x45, 0x45)      # Trust + PetNew + Pet
        self.assertEqual(body[37], 1)                 # player allegiance
        self.assertEqual(struct.unpack_from("<I", body, 44)[0], 3000 << 16)
        self.assertEqual(body[52:61], b"Shantotto")
        self.assertIn(0x067, msg_types(self.session))

        # Calling the same alter ego again is refused, and five is the party cap.
        self.session.queue.clear()
        self.session.cast_magic(bytes(packet), 0)
        self.assertIsNone(self.session.casting)
        self.assertEqual(len(self.session.trust_entities), 1)
        self.assertIn("Shantotto is already called.", self.chats())

    def test_trust_follows_and_attacks_the_owners_target(self):
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.assertIsNotNone(trust)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = 50000
        mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)
        self.session.queue.clear()
        now = time.time() + 5
        with mock.patch.object(self.world.rng, "random", return_value=0.0):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now)
        self.assertLess(int(mob.hp), 50000)
        actions = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028
                   and struct.unpack_from("<I", message, 5)[0] == trust.id]
        self.assertTrue(actions)
        self.assertEqual(trust.animation, 1)

    def test_a_trust_steps_out_of_the_players_collision_bubble(self):
        """The client collides the player with its own Trusts, so a follower standing on the
        character blocks every step.  Inside TRUST_PERSONAL_SPACE the Trust yields instead."""
        self.zone(100)
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.assertIsNotNone(trust)
        self.session.pos = [10.0, 0.0, 10.0, 0]
        trust.x, trust.y, trust.z = 10.4, 0.0, 10.0     # 0.4 yalms away: inside the bubble
        trust.moving = False
        self.session.queue.clear()
        now = time.time() + 5
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now)
        self.assertGreater(math.hypot(trust.x - 10.0, trust.z - 10.0), 0.4)
        self.assertTrue(trust.moving)
        positions = [message for message in self.session.queue
                     if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E]
        self.assertTrue(positions, "the step has to be streamed to the client")

    def test_trust_command_lists_and_releases_by_spell_id(self):
        """The HUD sends //trust release <spell id> when an active Trust tile is clicked."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.assertIsNotNone(trust)
        self.session.queue.clear()
        self.session.command("trust".split())
        self.assertIn("Active alter egos: Shantotto (896)", self.chats())

        self.session.queue.clear()
        self.session.command("trust release 896".split())
        self.assertIn("Shantotto leaves your party.", self.chats())
        self.assertNotIn(trust, self.world.entities_for_zone(100))
        self.assertEqual(self.session.trust_entities, [])
        self.assertIn(0x00E, msg_types(self.session))

    def test_release_menu_despawns_a_trust(self):
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.session.queue.clear()
        self.talk(trust)
        self.assertIn("Shantotto leaves your party.", self.chats())
        self.assertNotIn(trust, self.world.entities_for_zone(100))
        self.assertEqual(self.session.trust_entities, [])

    def test_trusts_despawn_when_the_owner_zones(self):
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.assertIn(trust, self.world.entities_for_zone(100))
        self.session.change_zone(246, list(self.world.zones.position(246)))
        self.assertEqual(self.session.trust_entities, [])
        self.assertNotIn(trust, self.world.entities_for_zone(100))
        self.assertNotIn(trust, self.session.entities)
        self.assertTrue(any((struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x00E
                            for message in self.session.queue))

    def test_trust_casts_a_buff_the_owner_can_see(self):
        """Kupipi's spell list is real: she starts Protectra and the icon reaches 0x037."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        self.session.char["hp_current"] = int(self.session.char["hp"])
        self.session.char["mp_current"] = int(self.session.char.get("mp", 0))
        trust = self.world.spawn_trust(self.session, self.service.trust(898))
        self.assertIsNotNone(trust)
        self.assertEqual(len(trust.spells), 27)
        self.session.queue.clear()

        now = time.time()
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + 1)
        self.assertIsNotNone(trust.casting)
        self.assertEqual(trust.casting["kind"], "buff")
        starts = [message for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028
                  and struct.unpack_from("<I", message, 5)[0] == trust.id]
        self.assertTrue(starts)
        result = action_results(starts[0])[0]
        self.assertEqual(result["message"], packets.MESSAGE_MAGIC_STARTS_CASTING_SELF)
        self.assertEqual(result["animation"], int(trust.casting["spell"]["animation"]))

        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + 10)
        self.assertIn(effects.PROTECT, self.session.effect_state)
        status = self.session.char_status()
        icons = []
        for slot in range(32):
            if status[4 + slot] == 0xFF:
                continue
            high = (status[4 + 0x48 + slot // 4] >> (2 * (slot % 4))) & 3
            icons.append(status[4 + slot] | (high << 8))
        self.assertIn(effects.PROTECT, icons)

    def test_koru_moru_keeps_haste_ii_and_never_flurries(self):
        """Flurry only speeds ranged attacks; Koru-Moru's kit keeps Haste II instead."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(952))
        self.assertIsNotNone(trust)
        self.assertEqual(trust.name, "Koru-moru")
        buffs = {str(spell["name"]).casefold() for spell in trust.kit["buff"]}
        self.assertIn("haste ii", buffs)
        self.assertNotIn("flurry", buffs)
        self.assertNotIn("flurry ii", buffs)

        # Every other buff already up: Haste II is the next cast, and once it is up
        # there is no Flurry left in the rotation to fall back to.
        for name in ("Protect V", "Shell V", "Refresh II", "Phalanx II"):
            spec = effects.for_spell(name)
            self.session.add_effect(spec.effect, duration=600, mods=spec.mods)
        now = time.time()
        self.assertEqual(trust_ai.buff_for(trust.kit, self.session.effect_state, now)["name"],
                         "Haste II")
        haste = effects.for_spell("Haste II")
        self.session.add_effect(haste.effect, duration=600, mods=haste.mods)
        self.assertIsNone(trust_ai.buff_for(trust.kit, self.session.effect_state, now))

    def test_trust_aura_picks_one_by_need(self):
        """Sylvie's geomancy is a decision, not a buff list: one aura per situation."""
        kit = {"aura": [
            {"id": 768, "name": "Indi-regen"}, {"id": 770, "name": "Indi-refresh"},
            {"id": 771, "name": "Indi-haste"}, {"id": 779, "name": "Indi-fury"},
            {"id": 781, "name": "Indi-acumen"}, {"id": 783, "name": "Indi-precision"},
            {"id": 788, "name": "Indi-frailty"},
        ]}

        def chosen(**need):
            need.setdefault("target", True)
            spell = trust_ai.choose_aura(kit, trust_ai.AuraNeed(**need))
            return spell["name"] if spell is not None else None

        # An empty MP pool comes first, whether it is the owner's or a teammate's.
        self.assertEqual(chosen(mp_percent=30.0), "Indi-refresh")
        self.assertEqual(chosen(party_mp_percent=25.0), "Indi-refresh")
        # A caster wants Magic Attack; a physical owner wants the stat that is short.
        self.assertEqual(chosen(caster=True), "Indi-acumen")
        self.assertEqual(chosen(hit_rate=0.60), "Indi-precision")
        self.assertEqual(chosen(hit_rate=0.99, attack_ratio=1.0), "Indi-fury")
        # Accuracy and Attack are fine: Frailty is the group's damage, and a ready
        # weapon skill makes it the play even before Attack is the bottleneck.
        self.assertEqual(chosen(hit_rate=0.99, attack_ratio=2.0), "Indi-frailty")
        self.assertEqual(chosen(hit_rate=0.99, attack_ratio=1.0, tp_ready=True,
                                party_melee=3), "Indi-frailty")
        # Out of combat there is nothing to measure, so Accuracy is the default upkeep.
        self.assertEqual(chosen(target=False), "Indi-precision")

    def test_sylvie_uc_keeps_one_aura_and_swaps_by_need(self):
        """The geomancy Trust puts up exactly one aura, and swaps it when the need moves."""
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["hp_current"] = int(self.session.char["hp"])
        trust = self.world.spawn_trust(self.session, self.service.trust(981))
        self.assertIsNotNone(trust)
        self.assertEqual(trust.name, "Sylvie Uc")
        self.assertEqual([str(spell["name"]) for spell in trust.kit["aura"]],
                         ["Indi-regen", "Indi-refresh", "Indi-haste", "Indi-fury",
                          "Indi-acumen", "Indi-precision", "Indi-frailty"])
        self.assertEqual([str(spell["name"]) for spell in trust.kit["buff"]],
                         ["Haste"])                       # geomancy left the buff rotation

        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)

        def tick(beats, start, step=3.0):
            for beat in range(beats):
                self.world._tick_trust(
                    trust, self.world.sessions_in_zone(100), start + beat * step)

        # A healthy melee owner with nothing short: one hex, and no aura on the owner.
        start = time.time()
        tick(8, start)
        self.assertEqual([status for status in self.session.effect_state
                          if status in geomancy.STATUSES], [])
        self.assertIn(geomancy.GEO_DEFENSE_DOWN, mob.effect_state)
        # Idris: her Frailty is the 27% Defense cut, not the plain 10%.
        self.assertEqual(int(mob.effect_state[geomancy.GEO_DEFENSE_DOWN]["potency"]), 27)

        # The owner runs dry: the hex comes off and Indi-refresh takes its place.
        self.session.char["mp"] = 600
        self.session.char["mp_current"] = 120
        tick(8, start + 30)
        self.assertEqual([status for status in self.session.effect_state
                          if status in geomancy.STATUSES], [geomancy.GEO_REFRESH])
        self.assertNotIn(geomancy.GEO_DEFENSE_DOWN, mob.effect_state)

        # A Geomancer owner maintains their own bubble, so the Trust leaves it alone.
        self.session.char["main_job"] = 21
        self.assertIsNone(self.world._trust_aura_choice(
            trust, self.session, mob, start + 120))

    def test_a_trust_grows_with_its_master_gear(self):
        """A well-geared Master lends the Trust a share of the gear's stats."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(898))
        self.assertIsNotNone(trust)
        base_hp = int(trust.hp_max)
        self.assertEqual(dict(getattr(trust, "shared_mods", {}) or {}), {})

        pieces = self.db.all(
            "SELECT item_id FROM items WHERE item_level = 119 "
            "GROUP BY equip_slot ORDER BY item_id LIMIT 5")
        for kind, row in enumerate(pieces):
            self.db.execute(
                "INSERT OR REPLACE INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, ?, 0, ?, ?)",
                (int(self.character["id"]), 4 + kind, kind, int(row["item_id"])))
        self.world._trust_share_cache.clear()
        trust.next_gear_sync = 0.0
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), time.time() + 5)

        self.assertGreater(int(trust.hp_max), base_hp)
        self.assertGreater(int((trust.shared_mods or {}).get(mod.HP, 0)), 0)

    def test_joachim_songs_use_his_instruments(self):
        """The Loughnashade's Song+4 reaches the song he lands."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(911))
        self.assertIsNotNone(trust)
        self.assertEqual(trust.gear.items, (22307,))
        song = next(spell for spell in trust.spells if spell["name"] == "Victory March")
        spec = effects.for_spell("Victory March")
        before = time.time()
        self.world._land_trust_buff(trust, self.session, song, spec)

        state = self.session.effect(effects.song_key(int(song["id"])))
        self.assertIsNotNone(state)
        boosted, _tick = effects.song_potency_values(
            "Victory March", spec, trust.gear_mods)
        self.assertEqual(state["mods"], boosted)
        self.assertGreater(state["mods"][mod.HASTE_MAGIC],
                           int(spec.mods.get(mod.HASTE_MAGIC, 0)))
        self.assertGreater(state["until"] - before, spec.duration * 1.3)

    def test_joachim_sings_no_paeons_or_ballads(self):
        """The Bard trust sings the plan, not the spell list.

        March, Minuet or Aria, and Madrigal only when the owner's swing is landing under
        95%.  The filler families -- Paeon and Ballad -- are what the plan refuses: they
        were the songs that made a four-song bar feel like a buff dump.
        """
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(911))
        self.assertIsNotNone(trust)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)

        now = time.time()
        for beat in range(16):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + beat * 4)
        # Songs are keyed by spell, not by their shared icon, so read their names.
        songs = [state.get("song_name") for state in self.session.effect_state.values()
                 if state.get("song") and float(state.get("until", 0.0)) > now]
        self.assertIn("Victory March", songs)
        self.assertTrue({"Valor Minuet V", "Aria of Passion"} & set(songs))
        self.assertFalse([name for name in songs
                          if "Paeon" in name or "Ballad" in name])
        self.assertLessEqual(len(songs), 4)                       # Song+4 is the ceiling

    def test_joachim_sings_the_owners_explicit_four_song_set(self):
        """The command's set replaces the role plan, in order, Minuet V and IV together."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(911))
        self.assertIsNotNone(trust)
        self.session.joachim_songs = [418, 398, 397, 417]  # Aria, Minuet V/IV, Honor
        now = time.time()
        chosen = []
        for _ in range(4):
            song = self.world._trust_song_choice(trust, self.session, None, now)
            self.assertIsNotNone(song)
            chosen.append(song["name"])
            self.world._land_trust_buff(
                trust, self.session, song, effects.for_spell(song["name"]))
        self.assertEqual(chosen, [
            "Aria of Passion", "Valor Minuet V", "Valor Minuet IV", "Honor March"])
        # Both Minuets are on the bar: they share icon 434 but not their state key.
        for spell_id in (418, 398, 397, 417):
            self.assertIsNotNone(self.session.effect(effects.song_key(spell_id)))
        minuet_icon = effects.for_spell("Valor Minuet V").effect
        self.assertEqual(self.session.effect(effects.song_key(398))["icon"], minuet_icon)
        self.assertEqual(self.session.effect(effects.song_key(397))["icon"], minuet_icon)
        # All four are running, so the next beat has nothing to sing.
        self.assertIsNone(self.world._trust_song_choice(trust, self.session, None, now))
        # Both Minuets feed the stat sheet: dropping IV lowers Attack.
        both = self.session.stat_sheet().fighter.attack
        self.session.remove_effect(effects.song_key(397), quiet=True)
        self.assertGreater(both, self.session.stat_sheet().fighter.attack)

    def test_a_corsair_gets_the_melee_plan_not_archers_prelude(self):
        """COR is ranged for rolls, but its default songs are the melee set now."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(911))
        self.assertIsNotNone(trust)
        need = self.world._trust_song_need(self.session, None)
        self.assertFalse(need.ranged)
        names = [spell["name"] for spell in
                 trust_ai.choose_songs(trust.kit, need)]
        self.assertNotIn("Archers Prelude", names)
        self.assertIn("Victory March", names)

    def test_trust_joachim_set_songs_persists_and_answers_the_hud(self):
        """The chat command stores the set, the HUD query gets the data line, auto resets it."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.queue.clear()
        # The chat parser has already split on spaces; quotes survive on the tokens.
        self.session.command(["trust", "joachim", "set", "songs",
                              '"Aria', 'of', 'Passion"', '"Valor', 'Minuet', 'V"',
                              '"Valor', 'Minuet', 'IV"', '"Honor', 'March"'])
        self.assertIn("Joachim songs: Aria of Passion, Valor Minuet V, "
                      "Valor Minuet IV, Honor March", self.chats())
        self.assertEqual(self.session.joachim_songs, [418, 398, 397, 417])
        stored = self.service.character_setting(self.character["id"], "joachim_songs")
        self.assertEqual(json.loads(stored), [418, 398, 397, 417])

        self.session.queue.clear()
        self.session.command(["trust", "911", "ui", "hud"])
        lines = self.chats()
        self.assertIn("TrustData|911|B|Joachim|song|4|0|418,398,397,417", lines)
        self.assertIn("TrustData|911|A|418|99|song|Aria of Passion", lines)
        self.assertIn("TrustData|911|E", lines)

        # More than the horn's four slots is refused, and leaving a name out of the set
        # does not rewrite it.
        self.session.queue.clear()
        self.session.command(["trust", "joachim", "set", "songs",
                              '"Aria', 'of', 'Passion"', '"Valor', 'Minuet', 'V"',
                              '"Valor', 'Minuet', 'IV"', '"Honor', 'March"',
                              '"Victory', 'March"'])
        self.assertIn("four or fewer", " ".join(self.chats()))
        self.assertEqual(self.session.joachim_songs, [418, 398, 397, 417])

        # An unquoted name is matched by its longest known run of words, too.
        self.session.queue.clear()
        self.session.command(["trust", "joachim", "set", "songs",
                              "Archer's", "Prelude", "Valor", "Minuet", "V"])
        self.assertIn("Joachim songs: Archers Prelude, Valor Minuet V", self.chats())

        self.session.queue.clear()
        self.session.command(["trust", "joachim", "set", "auto"])
        self.assertEqual(self.session.joachim_songs, [])
        self.assertTrue(any("Joachim chooses his songs by role" in line
                            for line in self.chats()))
        self.assertEqual(
            self.service.character_setting(self.character["id"], "joachim_songs"), "")

    def test_support_trust_action_sets_persist_and_send_the_hud_catalogue(self):
        """Koru-Moru, Ygnas and Luzaf store ordered sets and answer the hidden UI query."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()

        self.session.queue.clear()
        self.session.command(["trust", "952", "set", "spells",
                              '"Haste', 'II"', '"Refresh', 'II"'])
        self.assertIn("Koru-moru spells: Haste II, Refresh II", self.chats())
        self.assertEqual(self.session.trust_actions[952], [511, 473])
        stored = json.loads(self.service.character_setting(
            self.character["id"], "trust_actions"))
        self.assertEqual(stored["952"], [511, 473])

        self.session.queue.clear()
        self.session.command(["trust", "952", "ui", "hud"])
        lines = self.chats()
        self.assertIn("TrustData|952|B|Koru-moru|spell|12|0|511,473", lines)
        self.assertIn("TrustData|952|A|511|96|buff|Haste II", lines)
        self.assertIn("TrustData|952|E", lines)

        self.session.command(["trust", "ygnas", "set", "spells",
                              '"Cure', 'VI"', '"Haste"'])
        self.assertEqual(self.session.trust_actions[998], [6, 57])
        self.assertIn("Ygnas spells: Cure VI, Haste", self.chats())

        self.session.command(["trust", "luzaf", "set", "rolls",
                              '"Chaos', 'Roll"', '"Samurai', 'Roll"'])
        self.assertEqual(self.session.trust_actions[928], [105, 109])
        self.assertIn("Luzaf rolls: Chaos Roll, Samurai Roll", self.chats())

        self.session.queue.clear()
        self.session.command(["trust", "952", "set", "default"])
        self.assertNotIn(952, self.session.trust_actions)
        self.assertTrue(any("Koru-moru uses the default logic" in line
                            for line in self.chats()))

        # More than a Trust's own limit is refused without touching the saved set.
        self.session.command(["trust", "952", "set", "spells",
                              '"Haste', 'II"', '"Refresh', 'II"', '"Cure', 'IV"',
                              '"Cure', 'III"', '"Cure', 'II"', '"Cure"',
                              '"Protect', 'V"', '"Shell', 'V"', '"Phalanx', 'II"',
                              '"Dia', 'III"', '"Slow', 'II"', '"Flurry', 'II"',
                              '"Distract', 'II"'])
        self.assertIn("at most 12 spells", " ".join(self.chats()))
        self.assertNotIn(952, self.session.trust_actions)

    def test_koru_moru_casts_only_the_owners_spell_pool(self):
        """An explicit spell pool replaces the whole rotation, including its cures."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.trust_actions[952] = [511, 473]   # Haste II, Refresh II
        trust = self.world.spawn_trust(self.session, self.service.trust(952))
        self.assertIsNotNone(trust)
        sessions = self.world.sessions_in_zone(100)
        now = time.time() + 5
        trust.next_cast_at = 0
        self.assertTrue(self.world._try_trust_cast(
            trust, self.session, sessions, None, now))
        self.assertEqual(trust.casting["spell"]["name"], "Haste II")
        trust.casting["finish"] = now
        self.world._finish_trust_cast(trust, self.session, now)
        trust.next_cast_at = 0
        self.assertTrue(self.world._try_trust_cast(
            trust, self.session, sessions, None, now + 5))
        self.assertEqual(trust.casting["spell"]["name"], "Refresh II")
        trust.casting["finish"] = now + 5
        self.world._finish_trust_cast(trust, self.session, now + 5)
        trust.next_cast_at = 0
        # Protect V, Shell V and Dia III are still in his kit but not in the owner's pool.
        self.assertFalse(self.world._try_trust_cast(
            trust, self.session, sessions, None, now + 10))

    def test_luzaf_uses_the_owner_roll_priority(self):
        """A selected roll list is a priority order, not the party-need default."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.trust_actions[928] = [109, 105]   # Samurai before Chaos
        trust = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(trust)
        now = time.time() + 5
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now))
        self.assertEqual(trust.roll_keys, ["samurai"])
        self.assertIsNotNone(self.session.effect(trust_ai.ROLL_STATUS["samurai"]))

        # Changing the list while the Trust keeps the old roll re-chooses on the next beat.
        self.session.trust_actions[928] = [105]
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now + 20))
        self.assertEqual(trust.roll_keys, ["chaos"])
        self.assertIsNotNone(self.session.effect(trust_ai.ROLL_STATUS["chaos"]))
        self.assertIsNone(self.session.effect(trust_ai.ROLL_STATUS["samurai"]))

    def test_a_corsair_trust_keeps_two_rolls(self):
        """A Trust Corsair fills both roll slots: retail Qultada holds Chaos and Fighter's.

        The first beat takes the party's biggest need, the second the next useful line.
        """
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(967))
        self.assertIsNotNone(trust)
        now = time.time()
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now))
        self.assertEqual(trust.roll_keys, ["chaos"])
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now + 8))
        self.assertEqual(trust.roll_keys, ["chaos", "fighters"])
        for key in trust.roll_keys:
            self.assertIsNotNone(
                self.session.effect(trust_ai.ROLL_STATUS[key]), key)

    def test_a_corsair_trust_uses_both_slots_from_the_owner_list(self):
        """Two selected rolls are two simultaneous slots, not one replacement."""
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.trust_actions[967] = [105, 109]      # Chaos, Samurai
        trust = self.world.spawn_trust(self.session, self.service.trust(967))
        self.assertIsNotNone(trust)
        now = time.time()
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now))
        trust.next_roll_at = 0
        self.assertTrue(self.world._try_trust_roll(
            trust, self.session, None, now + 8))
        self.assertEqual(trust.roll_keys, ["chaos", "samurai"])
        self.assertIsNotNone(self.session.effect(trust_ai.ROLL_STATUS["chaos"]))
        self.assertIsNotNone(self.session.effect(trust_ai.ROLL_STATUS["samurai"]))

    def test_two_corsairs_can_hold_four_selected_rolls(self):
        """Each Corsair fills two slots; two of them put four different rolls up."""
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.trust_actions[967] = [105, 109]      # Chaos, Samurai
        self.session.trust_actions[928] = [108, 112]      # Hunter's, Evoker's
        qultada = self.world.spawn_trust(self.session, self.service.trust(967))
        luzaf = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(qultada)
        self.assertIsNotNone(luzaf)
        now = time.time()
        for beat in range(4):
            for trust in (qultada, luzaf):
                trust.next_roll_at = 0
                self.world._try_trust_roll(
                    trust, self.session, None, now + beat * 8)
        self.assertEqual(set(qultada.roll_keys), {"chaos", "samurai"})
        self.assertEqual(set(luzaf.roll_keys), {"hunters", "evokers"})
        for key in ("chaos", "samurai", "hunters", "evokers"):
            self.assertIsNotNone(
                self.session.effect(trust_ai.ROLL_STATUS[key]), key)

    def test_a_solo_red_mage_gets_both_roll_lines(self):
        """A melee RDM counts as caster and melee, so two Corsairs fill four slots."""
        self.zone(100)
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["mp_current"] = int(self.session.char["mp"])
        need = self.world._trust_roll_need(self.session, None)
        self.assertEqual((need.melee, need.mages, need.ranged), (1, 1, 0))
        self.assertEqual(trust_ai.roll_options(need),
                         ["chaos", "fighters", "samurai", "wizards"])
        qultada = self.world.spawn_trust(self.session, self.service.trust(967))
        luzaf = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(qultada)
        self.assertIsNotNone(luzaf)
        now = time.time()
        for beat in range(4):
            for trust in (qultada, luzaf):
                trust.next_roll_at = 0
                self.world._try_trust_roll(
                    trust, self.session, None, now + beat * 8)
        self.assertEqual(len(qultada.roll_keys), 2)
        self.assertEqual(len(luzaf.roll_keys), 2)
        for key in ("wizards", "chaos", "fighters", "samurai"):
            self.assertIsNotNone(
                self.session.effect(trust_ai.ROLL_STATUS[key]), key)

    def test_sylvie_casts_geo_malaise_from_the_owners_spell_pool(self):
        """Sylvie's custom list can hold the enemy-targeted Malaise hex, not only Indi-."""
        self.zone(100)
        self.session.char.update(main_job=17, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["hp_current"] = int(self.session.char["hp"])
        self.session.trust_actions[981] = [820]   # Geo-malaise
        trust = self.world.spawn_trust(self.session, self.service.trust(981))
        self.assertIsNotNone(trust)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        sessions = self.world.sessions_in_zone(100)
        now = time.time() + 5
        trust.next_cast_at = 0
        self.assertTrue(self.world._try_trust_cast(
            trust, self.session, sessions, mob, now))
        self.assertEqual(trust.casting["spell"]["name"], "Geo-malaise")
        self.assertEqual(trust.casting["kind"], "debuff")
        trust.casting["finish"] = now
        self.world._finish_trust_cast(trust, self.session, now)
        self.assertIn(geomancy.GEO_MAGIC_DEF_DOWN, mob.effect_state)
        self.assertEqual(
            mob.effect_state[geomancy.GEO_MAGIC_DEF_DOWN]["potency"], 30)  # Idris +10
        self.assertEqual(int(trust.geo_mob_id), int(mob.id))

        # Between fights the same selected hex has nothing to land on and must not crash
        # or be cast on the owner.
        trust.next_cast_at = 0
        self.assertFalse(self.world._try_trust_cast(
            trust, self.session, sessions, None, now + 10))

    def test_joachim_measures_haste_without_his_march(self):
        """The March plan must not count the March on the bar, or it would flip forever.

        Victory March pushes a Haste II owner over the 43.75% cap; counting that would ask
        for Honor March next, which drops the Haste and asks for Victory again.  Measuring
        the owner's own magic haste keeps the choice stable.
        """
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.add_effect(effects.HASTE, duration=300,
                                mods={mod.HASTE_MAGIC: 3000})
        self.session.add_effect(effects.MARCH, duration=200,
                                mods={mod.HASTE_MAGIC: 2227})
        need = self.world._trust_song_need(self.session, None)
        self.assertAlmostEqual(need.haste_percent, 0.30, places=2)   # Haste II alone

    def test_qultada_rolls_chaos_and_never_swings(self):
        """A Corsair support Trust rolls for the party instead of fighting.

        The owner is the only melee, so the party's need is Attack and the roll is
        Chaos.  The monster's HP must not move: a roll Trust has no auto-attack and no
        weapon skill.
        """
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(967))
        self.assertIsNotNone(trust)
        self.assertTrue(trust.roll_support)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)

        now = time.time()
        # The plan is measured from the party, so pin the need here instead of letting a
        # level-1 rabbit's Defense decide whether the owner is attack-capped.
        with mock.patch.object(self.world, "_trust_roll_need",
                               return_value=trust_ai.RollNeed(melee=1)):
            for beat in range(12):
                self.world._tick_trust(trust, self.world.sessions_in_zone(100),
                                       now + beat * 4)

        self.assertEqual(int(mob.hp), 50000)                 # never swung
        state = self.session.effect(rolls.ROLLS[105].status)
        self.assertIsNotNone(state)                          # Chaos Roll
        self.assertGreaterEqual(int(state["power"]), 1)
        self.assertLessEqual(int(state["power"]), 6)
        self.assertEqual(state["mods"], rolls.ROLLS[105].mods(int(state["power"])))


    def test_a_corsair_trust_rolls_for_the_casters(self):
        """A caster owner gets the magic roll, not the melee one, on the same Trust."""
        self.zone(100)
        self.session.char.update(main_job=4, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["mp_current"] = int(self.session.char["mp"])
        trust = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(trust)
        now = time.time()
        for beat in range(6):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + beat * 4)
        wizard = self.session.effect(rolls.ROLLS[101].status)
        self.assertIsNotNone(wizard)                         # Wizard's Roll
        self.assertEqual(wizard["mods"], rolls.ROLLS[101].mods(int(wizard["power"])))
        self.assertIsNone(self.session.effect(rolls.ROLLS[105].status))

    def test_a_corsair_trust_gives_the_dry_caster_a_refresh_roll(self):
        """MP under half a bar turns the same party into Evoker's Roll territory."""
        self.zone(100)
        self.session.char.update(main_job=4, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["mp_current"] = int(self.session.char["mp"]) // 10
        trust = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(trust)
        now = time.time()
        for beat in range(6):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + beat * 4)
        evoker = self.session.effect(rolls.ROLLS[112].status)
        self.assertIsNotNone(evoker)                         # Evoker's Roll
        self.assertEqual(evoker["mods"], rolls.ROLLS[112].mods(int(evoker["power"])))

    def test_the_roll_plan_follows_the_party(self):
        """The roll is a party decision: melee, casters, ranged and their MP."""
        need = trust_ai.RollNeed
        self.assertEqual(trust_ai.choose_roll(need(melee=3)), 105)          # Chaos
        self.assertEqual(trust_ai.choose_roll(need(melee=3, attack_capped=True)), 109)
        self.assertEqual(trust_ai.choose_roll(need(melee=2, mages=1)), 105)  # melee still wins
        self.assertEqual(trust_ai.choose_roll(need(mages=2)), 101)          # Wizard's
        self.assertEqual(trust_ai.choose_roll(need(mages=2, mp_percent=30)), 112)  # Evoker's
        self.assertEqual(trust_ai.choose_roll(need(ranged=2)), 108)         # Hunter's
        self.assertEqual(trust_ai.choose_roll(need()), 105)                 # lone owner
        # A second Corsair takes the roll the first one is not already keeping up.
        chaos = frozenset({trust_ai.ROLL_STATUS["chaos"]})
        self.assertEqual(trust_ai.choose_roll(need(melee=2, active=chaos)), 98)   # Fighter's
        chaos_fighters = frozenset({trust_ai.ROLL_STATUS["chaos"],
                                    trust_ai.ROLL_STATUS["fighters"]})
        self.assertEqual(trust_ai.choose_roll(need(melee=2, active=chaos_fighters)), 109)

    def test_a_corsair_trust_rolls_last_the_job_point_maximum(self):
        """A Trust is a maxed Corsair: a roll runs 5:00 plus the 40 s job-point row."""
        self.assertEqual(rolls.duration(17), 340.0)     # 300s base + 2s x 20 ranks
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        trust = self.world.spawn_trust(self.session, self.service.trust(967))
        now = time.time()
        for beat in range(4):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + beat * 4)
        state = (self.session.effect(rolls.ROLLS[105].status)
                 or self.session.effect(rolls.ROLLS[109].status))
        self.assertIsNotNone(state)
        self.assertAlmostEqual(float(state["until"]) - time.time(),
                               rolls.duration(17), delta=2.0)

    def test_roll_values_follow_the_wiki(self):
        """Lucky and unlucky totals jump, so the table is not a per-point line."""
        chaos = rolls.ROLLS[105]
        self.assertEqual(chaos.mods(1)[mod.ATT_PERCENT], 6)     # 6.25%
        self.assertEqual(chaos.mods(4)[mod.ATT_PERCENT], 25)    # lucky 4
        self.assertEqual(chaos.mods(8)[mod.ATT_PERCENT], 3)     # unlucky 8
        self.assertEqual(chaos.mods(11)[mod.ATT_PERCENT], 31)   # 31.25%
        samurai = rolls.ROLLS[109]
        self.assertEqual(samurai.mods(2)[mod.STORETP], 32)      # lucky 2
        self.assertEqual(samurai.mods(6)[mod.STORETP], 4)       # unlucky 6
        self.assertEqual(rolls.ROLLS[101].mods(5)[mod.MATT], 25)       # lucky 5
        self.assertEqual(rolls.ROLLS[112].mods(11)[mod.REFRESH], 4)
        hunter = rolls.ROLLS[108].mods(4)
        self.assertEqual(hunter[mod.ACC], 40)
        self.assertEqual(hunter[mod.RACC], 40)

    def test_two_corsairs_hold_three_different_rolls(self):
        """Qultada and Luzaf split the melee plan instead of duplicating a roll."""
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        qultada = self.world.spawn_trust(self.session, self.service.trust(967))
        luzaf = self.world.spawn_trust(self.session, self.service.trust(928))
        self.assertIsNotNone(qultada)
        self.assertIsNotNone(luzaf)
        now = time.time()
        for beat in range(4):
            for trust in (qultada, luzaf):
                self.world._tick_trust(
                    trust, self.world.sessions_in_zone(100), now + beat * 4)
        for key in ("chaos", "fighters", "samurai"):
            self.assertIsNotNone(
                self.session.effect(trust_ai.ROLL_STATUS[key]), key)

    def test_a_hurt_owner_still_gets_the_aura(self):
        """The heal rule must not starve the bubble: a 60% owner gets both."""
        self.zone(100)
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session.refresh_vitals()
        self.session.char["hp_current"] = int(self.session.char["hp"]) * 60 // 100
        hurt = int(self.session.char["hp_current"])
        trust = self.world.spawn_trust(self.session, self.service.trust(981))
        self.assertIsNotNone(trust)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)

        now = time.time()
        for beat in range(10):
            self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + beat * 3)
        geo = [status for status in mob.effect_state if status in geomancy.STATUSES]
        self.assertEqual(geo, [geomancy.GEO_DEFENSE_DOWN])   # the bubble still went up
        self.assertGreater(int(self.session.char["hp_current"]), hurt)   # and she healed

    def test_geo_hexes_cut_the_monsters_stats(self):
        """Frailty lowers Defense and Torpor Evasion for the owner's own swings."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        before = self.world.debuffed_monster(mob)
        for status in (geomancy.GEO_DEFENSE_DOWN, geomancy.GEO_EVASION_DOWN):
            self.world.apply_mob_effect(
                mob, effects.SpellEffect(status, "debuff", 180, potency=10),
                self.session, time.time(), duration=180)
        after = self.world.debuffed_monster(mob)
        self.assertEqual(int(after.defense), max(1, int(int(before.defense) * 90 / 100.0)))
        self.assertEqual(int(after.evasion), max(1, int(int(before.evasion) * 90 / 100.0)))

    def test_geo_malaise_cuts_magic_defense_and_languor_magic_evasion(self):
        """BG-wiki: Malaise is MDEF down; Languor is Magic Evasion down.

        The server had these two status ids reversed, which made Malaise a no-op and
        made Languor the magic-damage bubble.  Malaise is the one Hot Shot's hybrid
        magic half reads.
        """
        self.assertEqual(geomancy.INDI_EFFECTS["malaise"][0],
                         geomancy.GEO_MAGIC_DEF_DOWN)
        self.assertEqual(geomancy.INDI_EFFECTS["languor"][0],
                         geomancy.GEO_MAGIC_EVASION_DOWN)
        self.assertEqual(geomancy.INDI_EFFECTS["slip"][0],
                         geomancy.GEO_ACCURACY_DOWN)
        self.zone(100)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        before = self.world.monster_debuff_mods(mob)
        now = time.time()
        for status, potency in ((geomancy.GEO_MAGIC_DEF_DOWN, 15),
                                (geomancy.GEO_MAGIC_EVASION_DOWN, 20)):
            self.world.apply_mob_effect(
                mob, effects.SpellEffect(status, "debuff", 180, potency=potency),
                self.session, now, duration=180)
        after = self.world.monster_debuff_mods(mob)
        self.assertEqual(int(after.get(mod.MDEF, 0)),
                         int(before.get(mod.MDEF, 0)) - 15)
        self.assertEqual(int(after.get(mod.MEVA, 0)),
                         int(before.get(mod.MEVA, 0)) - 20)

    def test_indi_slip_is_its_own_status(self):
        """LandSandBoat numbers GEO Slip 564; 540 is GEO Poison, not a second poison."""
        self.assertEqual(geomancy.INDI_EFFECTS["slip"][0], 564)
        self.assertNotEqual(geomancy.INDI_EFFECTS["slip"][0],
                            geomancy.INDI_EFFECTS["poison"][0])

    def test_cornelia_aura_is_a_separate_haste_icon(self):
        """Cornelia's GEO Haste stacks with Haste, and a passive Trust never swings."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        self.session.add_effect(effects.HASTE, duration=120,
                                mods={mod.HASTE_MAGIC: 1500})
        trust = self.world.spawn_trust(self.session, self.service.trust(1002))
        self.assertIsNotNone(trust)
        state = self.session.effect(effects.TRUST_AURA_HASTE)
        self.assertIsNotNone(state)
        self.assertEqual(state["icon"], 580)
        icons = []
        status = self.session.char_status()
        for slot in range(32):
            if status[4 + slot] == 0xFF:
                continue
            high = (status[4 + 0x48 + slot // 4] >> (2 * (slot % 4))) & 3
            icons.append(status[4 + slot] | (high << 8))
        self.assertIn(effects.HASTE, icons)
        self.assertIn(580, icons)                    # GEO Haste, beside normal Haste
        self.assertGreaterEqual(self.session.combat_mods().get(mod.HASTE_MAGIC, 0), 3500)

        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = 50000
        mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)
        self.session.queue.clear()
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), time.time() + 5)
        self.assertEqual(int(mob.hp), 50000)
        self.assertFalse(any((struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028
                             for message in self.session.queue))

        self.world.despawn_trust(trust, time.time() + 6, "test")
        self.assertFalse(self.session.has_effect(effects.TRUST_AURA_HASTE))
        self.assertTrue(self.session.has_effect(effects.HASTE))

    def test_trust_nukes_the_owners_target(self):
        """After the opening swing a caster Trust starts and resolves a real spell."""
        self.zone(100)
        self.session.char["main_level"] = 99
        self.session.refresh_vitals()
        self.session.char["hp_current"] = int(self.session.char["hp"])
        trust = self.world.spawn_trust(self.session, self.service.trust(896))
        self.assertIsNotNone(trust)
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp_max = 50000
        mob.hp = 50000
        self.session.pos = [mob.x + 2.0, mob.y, mob.z, 0]
        trust.x, trust.y, trust.z = self.session.pos[0], mob.y, self.session.pos[2]
        self.session.engaged_id = int(mob.id)
        now = time.time() + 5
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now)
        after_swing = int(mob.hp)
        self.assertLess(after_swing, 50000)

        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + 1)
        self.assertIsNotNone(trust.casting)
        self.assertEqual(trust.casting["kind"], "nuke")
        self.session.queue.clear()
        self.world._tick_trust(trust, self.world.sessions_in_zone(100), now + 30)
        self.assertLess(int(mob.hp), after_swing)
        self.assertTrue(any(
            (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028
            and struct.unpack_from("<I", message, 5)[0] == trust.id
            for message in self.session.queue))

    def test_dawn_mulsum_heals_pet_percentage_and_refills(self):
        self.give(0, 50, 5411, 3)
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 5411, 33)",
            (int(self.character["id"]),))
        self.session.char["hp_current"] = 1
        self.session.char["pet_hp_max"] = 1000
        self.session.char["pet_hp"] = 100
        packet = item_use_packet(50, 0)
        self.session.queue.clear()
        self.session.item_use(packet)
        restored = int(self.session.char["pet_hp"]) - 100
        self.assertGreaterEqual(restored, 250)
        self.assertLessEqual(restored, 500)
        self.assertEqual(int(self.session.char["hp_current"]), 1)  # pet-only medicine
        rows = [row for row in self.service.inventory(self.character["id"])
                if int(row["item_id"]) == 5411]
        self.assertEqual(sum(int(row["quantity"]) for row in rows), 3)
        self.assertEqual(self.locker_stored(), {5411: 32})
        self.assertTrue(any("Dawn Mulsum restores" in line for line in self.chats()))

    def test_dawn_mulsum_without_pet_does_not_heal_the_player(self):
        self.give(0, 50, 5411, 3)
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 5411, 33)",
            (int(self.character["id"]),))
        self.session.char["hp_current"] = 1
        packet = item_use_packet(50, 0)
        self.session.queue.clear()
        self.session.item_use(packet)
        self.assertEqual(int(self.session.char["hp_current"]), 1)
        self.assertIn("You do not have a pet to heal.", self.chats())
        rows = [row for row in self.service.inventory(self.character["id"])
                if int(row["item_id"]) == 5411]
        self.assertEqual(sum(int(row["quantity"]) for row in rows), 3)

    def test_dawn_mulsum_does_not_affect_a_luopan(self):
        self.give(0, 50, 5411, 3)
        self.session.char["pet_hp_max"] = 1000
        self.session.char["pet_hp"] = 100
        self.session.char["pet_type"] = "luopan"
        packet = item_use_packet(50, 0)
        self.session.queue.clear()
        self.session.item_use(packet)
        self.assertEqual(int(self.session.char["pet_hp"]), 100)
        self.assertIn("The Dawn Mulsum has no effect on the Luopan.", self.chats())

    def test_stock_command_refills_visible_consumables(self):
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 2972, 10)",
            (int(self.character["id"]),))
        self.session.queue.clear()
        self.session.command("stock".split())
        rows = [row for row in self.service.inventory(self.character["id"])
                if int(row["item_id"]) == 2972]
        self.assertEqual(sum(int(row["quantity"]) for row in rows), 10)
        self.assertIn("Refilled 10 items from the locker.", self.chats())
        self.assertTrue(any("Shikanofuda 10/99" in line for line in self.chats()))

    def test_locker_stores_ammo_back_and_names(self):
        """//locker store moves ammo/capes out of every bag and into the 9999-item locker."""
        self.give(0, 50, 22279)  # Staunch Tathlum +1: ammo
        self.give(0, 51, 26258)  # Andartia's Mantle: back
        self.give(0, 52, 26254)  # Artio's Mantle: back
        self.session.queue.clear()
        self.session.command("locker store ammo".split())
        self.assertEqual(self.locker_stored(), {22279: 1})
        rows = self.service.inventory(self.character["id"])
        bag = {(int(row["container"]), int(row["slot"])) for row in rows}
        self.assertNotIn((0, 50), bag)
        self.assertIn((0, 51), bag)
        self.assertIn((0, 52), bag)

        self.session.command("locker store back".split())
        self.assertEqual(self.locker_stored(), {22279: 1, 26258: 1, 26254: 1})
        rows = self.service.inventory(self.character["id"])
        self.assertFalse(any(int(row["item_id"]) in (22279, 26258, 26254) for row in rows))
        self.assertIn("Stored 2 items in the locker (3/9999 slots).", self.chats())

    def test_locker_stores_materials_and_matches_names(self):
        """materials covers non-wearables; any other word is a name substring."""
        self.give(0, 50, 4112)  # Potion: no equip slot
        self.session.command("locker store materials".split())
        self.assertEqual(self.locker_stored(), {4112: 3})  # starter stack of 2 + the extra 1
        self.give(0, 51, 26254)  # Artio's Mantle
        self.session.command("locker store Artio".split())
        self.assertEqual(self.locker_stored(), {4112: 3, 26254: 1})

    def test_locker_grab_returns_filtered_or_all(self):
        self.give(0, 50, 22279)
        self.give(0, 51, 26258)
        self.session.command("locker store ammo".split())
        self.session.command("locker store back".split())
        self.session.queue.clear()
        self.session.command("locker grab ammo".split())
        self.assertEqual(self.locker_stored(), {26258: 1})
        rows = self.service.inventory(self.character["id"])
        self.assertIn(22279, {int(row["item_id"]) for row in rows})
        self.assertIn("Took 1 item out of the locker (1 left).", self.chats())

        self.session.queue.clear()
        self.session.command("locker grab all".split())
        self.assertEqual(self.locker_stored(), {})
        rows = self.service.inventory(self.character["id"])
        self.assertIn(26258, {int(row["item_id"]) for row in rows})
        self.assertIn("Took 1 item out of the locker (0 left).", self.chats())

    def test_locker_grab_quantity_limit(self):
        """A 99-jug entry can be taken one stack at a time with //locker grab <name> 12."""
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 17860, 99)",
            (int(self.character["id"]),))
        self.session.queue.clear()
        self.session.command("locker grab carrot broth 12".split())
        self.assertEqual(self.locker_stored(), {17860: 87})
        rows = self.service.inventory(self.character["id"])
        taken = [(int(row["slot"]), int(row["quantity"])) for row in rows
                 if int(row["item_id"]) == 17860]
        self.assertEqual(taken, [(taken[0][0], 12)])
        self.assertIn("Took 12 items out of the locker (87 left).", self.chats())

    def test_locker_leaves_equipped_gear_on(self):
        self.give(0, 50, 22279)
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, 3, 0, 50, 22279)",
            (int(self.character["id"]),))
        self.session.queue.clear()
        self.session.command("locker store ammo".split())
        self.assertEqual(self.locker_stored(), {})
        self.assertIn("Nothing in your bags matched ammo.", self.chats())
        self.assertIn("Left 1 equipped piece on.", self.chats())

    def test_locker_capacity_counts_storage_slots(self):
        """A 99-item stack is one slot; the cap is 9,999 entries, not 9,999 units."""
        self.db.execute("DELETE FROM char_inventory WHERE character_id = ?",
                        (int(self.character["id"]),))
        # Two existing slots: a 99 Potion stack and one cape.
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 4112, 99)",
            (int(self.character["id"]),))
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 26258, 1)",
            (int(self.character["id"]),))
        self.give(0, 50, 4112)    # merges into the existing Potion slot
        self.give(0, 51, 22279)   # would be a third slot
        self.session.queue.clear()
        with mock.patch("fanxi_server.service.LOCKER_CAPACITY", 2):
            self.session.command("locker store all".split())
        self.assertEqual(self.locker_stored(), {4112: 100, 26258: 1})
        self.assertIn("The locker is full; 1 item stayed in your bags.", self.chats())

        self.session.queue.clear()
        with mock.patch("fanxi_server.service.LOCKER_CAPACITY", 3):
            self.session.command("locker store all".split())
        self.assertEqual(self.locker_stored(), {4112: 100, 26258: 1, 22279: 1})

    def test_locker_status_and_list(self):
        self.give(0, 50, 22279)
        self.give(0, 51, 26258)
        self.session.command("locker store ammo".split())
        self.session.command("locker store back".split())
        self.session.queue.clear()
        self.session.command("locker".split())
        self.assertIn("Locker: 2/9999 slots.", self.chats())
        self.session.queue.clear()
        self.session.command("locker list".split())
        lines = self.chats()
        self.assertTrue(any("Staunch Tathlum +1" in line for line in lines))
        self.assertTrue(any("Andartia's Mantle" in line for line in lines))

    def test_locker_accepts_the_double_slash_chat_form(self):
        self.give(0, 50, 22279)
        text = "//locker store ammo"
        payload = bytearray(2 + len(text) + 1)
        payload[2:2 + len(text)] = text.encode("ascii")
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x0B5)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x0B5, bytes(payload))))
        self.assertEqual(self.locker_stored(), {22279: 1})
        self.assertIn("Stored 1 item in the locker (1/9999 slots).", self.chats())

    def test_storage_job_names(self):
        for word in ("nin", "NIN", "Ninja", "13"):
            self.assertEqual(job_id(word), 13)
        self.assertEqual(job_id("white mage"), 3)
        self.assertIsNone(job_id("nope"))
        self.assertIsNone(job_id("23"))
        self.session.queue.clear()
        self.session.command("storage store nope".split())
        self.assertTrue(any("Unknown job" in line for line in self.chats()))


class EquipBatchTest(unittest.TestCase):
    """A whole set is one batch: every slot's echo now, one stat block for all of them.

    The follow-up is about a kilobyte, and the client is served one packet per ack, so a
    copy per slot used to bury the later 0x050 echoes and made a swap arrive in waves.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))

    def equip(self, slot: int, kind: int, category: int = 0) -> None:
        self.session.equip(bytes((0x50, 4, 0, 0, slot, kind, category, 0)))

    def give(self, container: int, slot: int, item_id: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, ?, ?, ?, 1)",
            (int(self.character["id"]), int(container), int(slot), int(item_id)))

    def test_a_gear_batch_sends_one_follow_up(self):
        self.session.queue.clear()
        for slot, kind in ((8, 4), (9, 5), (75, 6)):
            self.equip(slot, kind)
        types = msg_types(self.session)
        self.assertEqual(types.count(0x050), 3)
        self.assertNotIn(0x0AA, types)
        self.assertTrue(self.session.equipment_changed)

        self.session.flush_equipment()
        types = msg_types(self.session)
        self.assertEqual(types.count(0x050), 3)
        self.assertEqual(types.count(0x0AA), 1)
        self.assertFalse(self.session.equipment_changed)
        # A second flush with nothing new owed sends nothing.
        before = len(self.session.queue)
        self.session.flush_equipment()
        self.assertEqual(len(self.session.queue), before)

    def test_the_follow_up_only_carries_the_parts_that_changed(self):
        """An armour swap must not rewrite the ability list.

        host64 rebuilds its whole command list from every 0x0AC that arrives, and every
        client freeze in the 2026-10-27/28 logs ends on one of those rebuilds.  Armour
        cannot change the weapon skills or the job abilities, so the command data goes
        out only when its payload really differs: another weapon skill type, a Prime
        weapon's granted skill, or a job change.
        """
        self.session.char.update(main_job=1, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.session.equipped = {0: (8, 7, 21751)}      # Aymur, axe
        self.session.store_equipment()
        # The first follow-up has to carry everything: the client holds no copy yet.
        self.assertEqual(set(self.sync_types()),
                         {0x051, 0x0AA, 0x0AB, 0x0AC, 0x1A5, 0x061, 0x037})

        self.session.equipped[5] = (8, 3, 23768)        # Nyame Mail
        self.session.char["body"] = 910                 # the model _apply_equip_model sets
        self.session.store_equipment()
        types = self.sync_types()
        self.assertIn(0x051, types)                     # the look did change
        for unchanged in (0x0AA, 0x0AB, 0x1A5, 0x0AC):
            self.assertNotIn(unchanged, types)

        self.session.equipped[0] = (8, 4, 21685)        # Epeolatry, great sword
        self.session.char["main"] = 921
        self.session.store_equipment()
        self.assertIn(0x0AC, self.sync_types())          # another weapon skill block

    def test_a_burst_waits_for_the_settle_window_then_sends_one_follow_up(self):
        """A set split over datagrams shares one follow-up, not one per datagram."""
        self.session.queue.clear()
        self.equip(8, 4)
        self.equip(9, 5)
        now = time.time()
        self.session.tick(now)                    # inside the settle window: nothing yet
        self.assertNotIn(0x051, msg_types(self.session))
        self.session.tick(now + 1.0)              # settled: one follow-up for both
        types = msg_types(self.session)
        self.assertEqual(types.count(0x051), 1)
        self.assertEqual(types.count(0x061), 1)
        self.assertEqual(types.count(0x037), 1)

    def sync_types(self) -> list[int]:
        return [struct.unpack_from("<H", message, 0)[0] & 0x1FF
                for message in self.session.equipment_sync()]

    def test_a_two_handed_main_clears_a_stale_off_hand(self):
        self.session.char["main_job"] = 22  # RUN
        self.session.char["main_level"] = 99
        # Vajra is a THF dagger in the catalogue; let this RUN wear it so the test is
        # about the two-handed rule, not the job mask.
        self.db.execute("UPDATE items SET jobs = jobs | ? WHERE item_id = ?",
                        (1 << 21, 20585))
        self.give(0, 10, 21685)  # Epeolatry, great sword
        self.give(0, 11, 20585)  # Vajra, dagger
        self.give(0, 12, 22212)  # Utu Grip
        self.equip(11, 1)
        self.assertEqual(self.session.char["sub"], 559)
        self.session.queue.clear()

        self.equip(10, 0)
        self.assertNotIn(1, self.session.equipped)
        self.assertEqual(self.session.char["sub"], 0)
        self.assertEqual(self.session.char["main"], 833)
        clears = [message for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x050
                  and message[4] == 0 and message[5] == 1]
        self.assertTrue(clears, "the client was not told to drop the old sub model")

        # With the two-hander on, the off-hand dagger is refused outright.
        self.session.queue.clear()
        self.equip(11, 1)
        self.assertNotIn(1, self.session.equipped)
        self.assertTrue(any((struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x017
                            for message in self.session.queue))

        # The grip is legal with the two-hander, and has no model of its own, so the
        # dagger model must stay cleared instead of being resurrected by the grip.
        self.equip(12, 1)
        self.assertEqual(self.session.equipped[1], (0, 12, 22212))
        self.assertEqual(self.session.char["sub"], 0)

    def test_hand_to_hand_can_still_use_a_shield(self):
        self.session.char["main_job"] = 2  # MNK
        self.session.char["main_level"] = 99
        # Genbu's Shield is not MNK gear in the catalogue; the point here is the hand
        # rule, so make it wearable and check the sub slot is not treated as two-handed.
        self.db.execute("UPDATE items SET jobs = jobs | 2 WHERE item_id = 12296")
        self.give(0, 10, 21527)  # Sakpata's Fists, H2H
        self.give(0, 11, 12296)  # Genbu's Shield
        self.equip(10, 0)
        self.equip(11, 1)
        self.assertEqual(self.session.equipped[1], (0, 11, 12296))
        self.assertEqual(self.session.char["sub"], 31)

    def test_a_grip_tracks_the_main_weapon(self):
        self.session.char["main_job"] = 22  # RUN
        self.session.char["main_level"] = 99
        self.give(0, 10, 16534)  # Onion Sword, one-handed
        self.give(0, 11, 21685)  # Epeolatry, great sword
        self.give(0, 12, 19025)  # Pole Grip
        self.equip(10, 0)
        self.equip(12, 1)
        self.assertNotIn(1, self.session.equipped)

        self.equip(11, 0)
        self.equip(12, 1)
        self.assertEqual(self.session.equipped[1], (0, 12, 19025))
        self.assertEqual(self.session.char["sub"], 0)

        # Going back to a one-hander drops the grip that no longer fits.
        self.equip(10, 0)
        self.assertNotIn(1, self.session.equipped)
        self.assertEqual(self.session.char["sub"], 0)

    def test_khonsu_is_a_grip(self):
        self.assertTrue(self.session._is_grip({"name": "Khonsu"}))
        self.assertTrue(self.session._is_grip({"name": "Pole Grip"}))
        self.assertFalse(self.session._is_grip({"name": "Genbu's Shield"}))

    def test_auto_equip_pairs_the_hands(self):
        self.session.char["main_job"] = 22  # RUN
        self.session.char["main_level"] = 99
        # Start from an empty bag so the auto-pick is exactly what this test provides.
        self.db.execute("DELETE FROM char_inventory WHERE character_id = ? AND container = 0",
                        (int(self.character["id"]),))
        self.db.execute("UPDATE items SET jobs = jobs | ? WHERE item_id = 12296",
                        (1 << 21,))
        self.give(0, 10, 21685)  # Epeolatry, great sword
        self.give(0, 11, 22212)  # Utu Grip
        self.give(0, 12, 12296)  # Genbu's Shield
        self.session.equipped = {}
        self.session.equip_initial()
        self.assertEqual(self.session.equipped[0][2], 21685)
        self.assertEqual(self.session.equipped[1][2], 22212)

        self.session.equipped = {}
        self.db.execute("DELETE FROM char_inventory WHERE character_id = ? AND container = 0",
                        (int(self.character["id"]),))
        self.give(0, 10, 16534)  # Onion Sword, one-handed
        self.give(0, 11, 19025)  # Pole Grip
        self.session.equip_initial()
        self.assertEqual(self.session.equipped[0][2], 16534)
        self.assertNotIn(1, self.session.equipped)

    def test_a_job_change_unequips_wardrobe_gear(self):
        self.session.char["jobs"] = {19: (99, 0), 22: (99, 0)}
        self.session.char["main_job"] = 19  # DNC
        self.session.char["main_level"] = 99
        self.give(8, 26, 20584)  # Terpsichore, DNC dagger
        self.give(8, 28, 20585)  # Vajra, THF dagger
        self.session.equipped = {0: (8, 26, 20584), 1: (8, 28, 20585)}
        self.session.char["main"] = 569
        self.session.char["sub"] = 559

        self.session.myroom_job(bytes((0x00, 0x10, 0, 0, 22, 0)))
        self.assertEqual(self.session.char["main_job"], 22)  # RUN
        self.assertNotEqual(self.session.char["main"], 569)
        self.assertEqual(self.session.char["sub"], 0)
        rows = self.service.equipment(int(self.character["id"]))
        self.assertNotIn(20584, [int(row["item_id"]) for row in rows])
        self.assertNotIn(20585, [int(row["item_id"]) for row in rows])

    def test_hand_to_hand_wears_its_model_on_both_hands(self):
        """H2H is one item in the main slot but the client draws a fist on each hand.

        Retail carries the model a second time in the sub look with the +0x1000 tag
        (LandSandBoat's charutils.cpp); with an empty sub slot Fanxi sent 0 there, so
        the client drew only the main-hand knuckle.
        """
        self.session.char.update(main_job=2, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.give(0, 10, 21535)  # Varga Purnikawa
        self.equip(10, 0)
        self.assertEqual(int(self.session.char["main"]), 474)
        self.assertEqual(int(self.session.char["sub"]), 474 + 0x1000)
        looks = self.session.looks()
        self.assertEqual(looks[6], 474 + 0x6000)     # main hand
        self.assertEqual(looks[7], 474 + 0x8000)     # left fist

        # A different H2H weapon replaces the mirrored model on both hands.
        self.give(0, 11, 21527)  # Sakpata's Fists, model 477
        self.equip(11, 0)
        self.assertEqual(int(self.session.char["main"]), 477)
        self.assertEqual(int(self.session.char["sub"]), 477 + 0x1000)

        # A non-H2H main hand clears the left-fist copy.  (Varga is MNK/PUP only, so
        # switch the job before putting a Warrior sword on.)
        self.session.char.update(main_job=1, main_level=99)
        self.give(0, 12, 16534)  # Onion Sword, model 264
        self.equip(12, 0)
        self.assertEqual(int(self.session.char["main"]), 264)
        self.assertEqual(int(self.session.char["sub"]), 0)

        # And taking the weapon off clears both hands.
        self.equip(0, 0)  # slot 0 is the client's "remove from this slot" form
        self.assertEqual(int(self.session.char["main"]), 0)
        self.assertEqual(int(self.session.char["sub"]), 0)


class CombatStatsTest(unittest.TestCase):
    """The retail damage engine as the server actually calls it.

    Its own setUp rather than WorldTest's: these only need a session and a world, and
    inheriting WorldTest would run every other world test a second time.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))

    def equip(self, outfit: dict) -> None:
        """outfit: equip kind -> item id, e.g. {0: katana, 15: cape}."""
        self.service.save_equipment(
            int(self.character["id"]),
            {kind: (0, 1 + index, item_id)
             for index, (kind, item_id) in enumerate(outfit.items())})

    def monster(self, level: int = 60):
        from fanxi_server.game.entities import ZoneEntity
        return ZoneEntity(kind="mob", id=0x01000000 | (self.session.zone << 12) | 0x200,
                          targid=0x200, zone=self.session.zone, name="Test Mob",
                          level=level, hp=10000, hp_max=10000, alive=True)

    def average(self, swings) -> float:
        """Mean damage of the swings that landed.  A swing is (missed, damage, critical)."""
        landed = [damage for missed, damage, _critical in swings if not missed]
        return sum(landed) / max(1, len(landed))

    def test_status_packet_reports_su5_and_the_level_119_item_level(self):
        message = self.session.char_stats()
        # 0x4E is the Superior equipment level; the 2,100-JP gift unlocks Su5 and
        # every job here has its points maxed.
        self.assertEqual(message[4 + 0x4E], 5)
        # 0x51 is the item level *over 99*: the client draws 99 + 20 = iLv 119.
        # 0x50 is the highest equipped item level (stored, not drawn).
        self.assertEqual(message[4 + 0x51], 20)
        self.assertEqual(message[4 + 0x50], 119)

    def test_status_packet_reports_real_attack_and_defense(self):
        message = self.session.char_stats()
        base = struct.unpack_from("<7H", message, 4 + 0x10)
        adjust = struct.unpack_from("<7h", message, 4 + 0x1E)
        attack, defense = struct.unpack_from("<hh", message, 4 + 0x2C)
        # No more placeholders: the character menu now shows what combat uses.
        self.assertNotEqual((attack, defense), (999, 999))
        self.assertGreater(attack, 0)
        self.assertGreater(defense, 0)
        self.assertTrue(all(0 < value < 999 for value in base))
        self.assertEqual(len(adjust), 7)

    def elemental_defence(self):
        """The 0x061 def_elem block: fire, ice, wind, earth, thunder, water, light, dark."""
        return struct.unpack_from("<8h", self.session.char_stats(), 4 + 0x30)

    def test_status_packet_reports_the_element_orbs(self):
        """The equipment menu's eight element orbs read the 0x061 def_elem block.

        The client draws those orbs from the packet, not from its own item data, so a
        server that leaves 0x30 zero shows every element as 0 while the tooltips list
        Fire+20 and friends.  Fire Belt is Ice+20 Water-20 and Demon's Ring +1 is
        Light-20 Dark+13.
        """
        self.equip({})
        self.assertEqual(self.elemental_defence(), (0,) * 8)
        self.equip({10: 13241, 13: 13545})  # waist, ring1
        values = self.elemental_defence()
        self.assertEqual(values[0], 0)     # Fire Belt is not Fire+
        self.assertEqual(values[1], 20)    # Ice+20
        self.assertEqual(values[5], -20)   # Water-20
        self.assertEqual(values[6], -20)   # Light-20
        self.assertEqual(values[7], 13)    # Dark+13

    def test_element_orbs_sum_every_slot(self):
        """Two rings on the same element add up, and a negative piece subtracts."""
        self.equip({13: 14600, 14: 14600})  # two Alacrity Ring +1, Wind+7 each
        self.assertEqual(self.elemental_defence()[2], 14)
        self.equip({13: 13545, 14: 13545})  # two Demon's Ring +1, Light-20 each
        self.assertEqual(self.elemental_defence()[6], -40)

    def test_a_better_weapon_hits_harder(self):
        entity = self.monster(50)
        self.world.rng.seed(1234)
        self.equip({0: 16534})  # Onion Sword, damage 5
        weak = [self.world.player_attack(self.session, entity) for _ in range(200)]
        self.world.rng.seed(1234)
        self.equip({0: 20687})  # Burtgang, damage 165
        strong = [self.world.player_attack(self.session, entity) for _ in range(200)]
        self.assertGreater(self.average(strong), self.average(weak) * 3)

    def test_dt_gear_reduces_incoming_damage(self):
        entity = self.monster(60)
        self.equip({})
        self.world.rng.seed(99)
        bare = [self.world.mob_attack(entity, self.session) for _ in range(300)]
        # Nyame legs are -10% "Damage taken" and the feet are -10% PDT.
        self.equip({7: 23764, 8: 23765})
        self.world.rng.seed(99)
        armoured = [self.world.mob_attack(entity, self.session) for _ in range(300)]
        self.assertLess(self.average(armoured), self.average(bare) * 0.85)

    def test_gear_attack_raises_player_damage(self):
        entity = self.monster(60)
        self.equip({0: 20687})
        self.world.rng.seed(77)
        bare = [self.world.player_attack(self.session, entity) for _ in range(300)]
        # Nyame's five pieces carry Attack+40 each and enough damage taken to matter.
        self.equip({0: 20687, 4: 23761, 5: 23762, 6: 23763})
        self.world.rng.seed(77)
        geared = [self.world.player_attack(self.session, entity) for _ in range(300)]
        self.assertGreater(self.average(geared), self.average(bare))

    def test_max_hp_and_mp_come_from_the_grade_tables(self):
        self.session.refresh_vitals()
        message = self.session.char_stats()
        hp, mp = struct.unpack_from("<ii", message, 4)
        self.assertEqual(hp, base_stats.base_hp(1, 1, 1))
        self.assertEqual(mp, base_stats.base_mp(1, 1, 1))
        self.assertGreater(hp, 0)
        # ...and the session's own copy agrees, so gauges and damage see the same number.
        self.assertEqual(int(self.session.char["hp"]), hp)

    def test_equipping_hp_gear_raises_the_maximum(self):
        self.session.refresh_vitals()
        before = int(self.session.char["hp"])
        self.equip({5: 26532})  # body piece with HP +533
        self.session.refresh_vitals()
        self.assertEqual(int(self.session.char["hp"]), before + 533)
        hp, _mp = struct.unpack_from("<ii", self.session.char_stats(), 4)
        self.assertEqual(hp, before + 533)

    def test_a_shield_in_the_sub_slot_can_block(self):
        # The Diamond Aspis is a round shield (size 2) in LandSandBoat's shield table.
        self.equip({1: 26488})
        sheet = self.session.stat_sheet()
        self.assertEqual(sheet.shield_size, 2)
        # The shield skill comes from the job's rank, so a Warrior has it.
        self.assertGreater(sheet.fighter.shield_skill, 0)

    def test_swing_timer_uses_weapon_delay(self):
        self.equip({0: 16534})  # Onion Sword, delay 228, no haste
        sword = self.session.stat_sheet()
        self.assertAlmostEqual(sword.haste, 0.0)
        self.assertEqual(sword.attack_delay_ms, int(228 * 1000 / 60))
        self.equip({0: 21527})  # Sakpata's Fists, delay 576
        fists = self.session.stat_sheet()
        self.assertEqual(fists.attack_delay_ms, int(576 * 1000 / 60 * (1 - fists.haste)))

    def test_ninja_dual_wield_swings_main_then_off_hand(self):
        """A NIN with two katanas packs both hands into one 0x028, main hand first."""
        self.session.char.update(main_job=13, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        # Two katanas from LSB's item table: delay 227/damage 127 and delay 190/damage 123.
        self.equip({0: 21904, 1: 21905})
        sheet = self.session.stat_sheet()
        self.assertTrue(sheet.dual_wield)
        self.assertEqual(sheet.sub_fighter.weapon_dmg, 123)
        # (227 + 190) * (1 - 0.35) / 2 = 135 delay per hand.
        self.assertEqual(sheet.delay, 135)

        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        # Keep it alive through the main-hand hit so the off hand gets its swing.
        mob.hp = mob.hp_max = 10000
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid
        self.session.next_attack_at = 0.0
        self.session.queue.clear()

        seen = []
        original = self.world.player_attack

        def attack(session, entity, **kwargs):
            seen.append(bool(kwargs.get("off_hand")))
            return original(session, entity, **kwargs)

        with mock.patch.object(self.world, "player_attack", side_effect=attack):
            self.session.tick(time.time())
        self.assertEqual(seen, [False, True])
        actions = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]
        # One action for the round, two results: the client plays the main-hand swing
        # and then the off-hand one from the result count.  Two separate packets in
        # the same update made it drop the main hand entirely.
        self.assertEqual(len(actions), 1)
        self.assertEqual(action_animations(actions[0]), [0, 1])

    def test_hand_to_hand_swings_both_fists(self):
        """A MNK throws a right and a left punch every round, from one weapon.

        Both fists use the main-hand fighter (unlike a dual-wield off hand, which is a
        second weapon with half-STR Attack), and the second result's animation 1 is
        what the client plays as the left-hand punch.
        """
        self.session.char.update(main_job=2, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({0: 21535})  # Varga Purnikawa, H2H
        sheet = self.session.stat_sheet()
        self.assertTrue(sheet.fighter.h2h)
        self.assertIsNone(sheet.sub_fighter)
        # The base is the item's DMG plus the natural H2H damage, not the DMG alone.
        natural = int(sheet.fighter.skill_value * 0.11) + 3
        self.assertGreaterEqual(natural, 80)
        self.assertEqual(sheet.fighter.weapon_dmg, 213 + natural)

        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp = mob.hp_max = 20000
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid
        self.session.next_attack_at = 0.0
        self.session.queue.clear()

        seen = []
        original = self.world.player_attack

        def attack(session, entity, **kwargs):
            seen.append(bool(kwargs.get("off_hand")))
            return original(session, entity, **kwargs)

        with mock.patch.object(self.world, "player_attack", side_effect=attack):
            self.session.tick(time.time())
        # Both fists come from the main hand; the second is not an off-hand weapon.
        self.assertEqual(seen, [False, False])
        actions = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]
        self.assertEqual(len(actions), 1)
        self.assertEqual(action_animations(actions[0]), [0, 1])

    def test_red_mage_off_hand_swings_without_the_dual_wield_trait(self):
        """RDM/SCH may wear two one-handers; both have to appear in the 0x028.

        The equip rules already allow the off-hand weapon (the client sends the 0x050
        and the server accepts it), so the old Dual Wield trait gate made the second
        weapon visible but inert.  The trait now only lowers the round's delay.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=20, sub_level=49)
        self.session._trait_cache = None
        self.equip({0: 21627, 1: 22040})         # Crocea Mors / Daybreak
        sheet = self.session.stat_sheet()
        self.assertTrue(sheet.dual_wield)
        self.assertIsNotNone(sheet.sub_fighter)
        self.assertEqual(sheet.dual_wield_percent, 0)

        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp = mob.hp_max = 10000
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid
        self.session.next_attack_at = 0.0
        self.session.queue.clear()

        seen = []
        original = self.world.player_attack

        def attack(session, entity, **kwargs):
            seen.append(bool(kwargs.get("off_hand")))
            return original(session, entity, **kwargs)

        with mock.patch.object(self.world, "player_attack", side_effect=attack):
            self.session.tick(time.time())
        self.assertEqual(seen, [False, True])
        actions = [message for message in self.session.queue
                   if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]
        self.assertEqual(len(actions), 1)
        self.assertEqual(action_animations(actions[0]), [0, 1])

    def test_dual_wield_kill_uses_the_hp_the_main_hand_left(self):
        """Neither hand kills alone, but the round does; the off hand must see main's HP."""
        self.session.char.update(main_job=13, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({0: 21904, 1: 21905})
        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp = mob.hp_max = 1000
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid
        self.session.next_attack_at = 0.0
        self.session.queue.clear()
        hits = iter([(False, 600, False), (False, 500, False)])
        with mock.patch.object(self.world, "player_attack",
                               side_effect=lambda *args, **kwargs: next(hits)):
            self.session.tick(time.time())
        self.assertFalse(mob.alive)
        self.assertEqual(mob.hp, 0)
        types = msg_types(self.session)
        # The swinging action goes out before the defeat line, as it did when each hand
        # was its own packet.
        self.assertLess(types.index(0x028), types.index(0x029))

    def test_multi_attack_rounds_carry_every_swing_in_one_action(self):
        """Double/Triple/Quadruple add results to the same 0x028, hand by hand."""
        self.session.char.update(main_job=13, main_level=99, sub_job=1, sub_level=49)
        self.session._trait_cache = None
        self.equip({0: 21904, 1: 21905})
        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid

        for hits, expected in ((2, [0, 0, 1, 1]),
                               (3, [0, 0, 0, 1, 1, 1]),
                               (4, [0, 0, 0, 0, 1, 1, 1, 1])):
            with self.subTest(hits=hits):
                mob.alive = True
                mob.hp = mob.hp_max = 10000
                self.session.next_attack_at = 0.0
                self.session.queue.clear()
                calls = []

                def attack(session, entity, **kwargs):
                    calls.append(bool(kwargs.get("off_hand")))
                    return False, 100, False

                with mock.patch.object(combat, "multi_attack_hits", return_value=hits):
                    with mock.patch.object(self.world, "player_attack", side_effect=attack):
                        self.session.tick(time.time())
                actions = [message for message in self.session.queue
                           if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]
                self.assertEqual(len(actions), 1)
                self.assertEqual(action_animations(actions[0]), expected)
                # Every extra hit belongs to the hand that rolled it: main first.
                self.assertEqual(calls, [False] * hits + [True] * hits)

    def test_double_attack_comes_from_the_trait_and_its_merit(self):
        """NIN/WAR has the trait at 10%; a Warrior main also adds its bought merit."""
        self.session.char.update(main_job=13, main_level=99, sub_job=1, sub_level=49)
        self.session._trait_cache = None
        sheet = self.session.stat_sheet()
        self.assertEqual(int(sheet.fighter.mods.get(mod.DOUBLE_ATTACK, 0)), 10)
        self.session.world.rng = mock.Mock(random=lambda: 0.0)
        self.assertEqual(self.session._multi_attack_hits(sheet), 2)

        self.service.save_merit(int(self.character["id"]), 0x0188, 5)
        self.session._merit_counts = None
        self.session.char.update(main_job=1, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        warrior = self.session.stat_sheet()
        # WAR 99's Double Attack trait is 18%, plus five 1% merit ranks.
        self.assertEqual(int(warrior.fighter.mods.get(mod.DOUBLE_ATTACK, 0)), 23)

        # The merit is the Warrior's: the Ninja main only gets the sub-job trait.
        self.session.char.update(main_job=13, sub_job=1, sub_level=49)
        self.session._trait_cache = None
        self.assertEqual(int(self.session.combat_mods().get(mod.DOUBLE_ATTACK, 0)), 10)

    def test_quadruple_attack_gear_reaches_the_round(self):
        """Twilight Knife is Quadruple Attack +10; no job trait is involved."""
        self.equip({0: 19132})
        sheet = self.session.stat_sheet()
        self.assertEqual(int(sheet.fighter.mods.get(mod.QUADRUPLE_ATTACK, 0)), 10)
        self.session.world.rng = mock.Mock(random=lambda: 0.0)
        self.assertEqual(self.session._multi_attack_hits(sheet), 4)

    def test_damage_keeps_cumulative_and_volatile_enmity_separate(self):
        mob = self.monster(level=60)
        self.world.add_damage_hate(mob, 99, 100, now=1.0)
        # level 60: 60*31//50 + 6 = 43.  First hate also claims 200 CE + 900 VE.
        self.assertEqual(mob.enmity_ve[99], 900 + 240 * 100 // 43)
        self.assertEqual(mob.enmity[99] - mob.enmity_ve[99], 200 + 80 * 100 // 43)

    def test_volatile_enmity_decays_but_cumulative_does_not(self):
        mob = self.monster(level=60)
        self.world.add_mob_hate(mob, 99, now=1.0, ce=1000, ve=1000)
        # First hate claims 200 CE + 900 VE; then two seconds drain 120 VE.
        self.world.decay_mob_enmity(mob, 3.0)
        self.assertEqual(mob.enmity_ve[99], 1780)
        self.assertEqual(mob.enmity[99] - mob.enmity_ve[99], 1200)
        self.assertEqual(mob.enmity[99], 2980)

    def test_provoke_is_cumulative_enmity(self):
        mob = self.monster(level=60)
        self.world.add_mob_hate(mob, 99, now=1.0, ce=1800, ve=0)
        self.world.decay_mob_enmity(mob, 6.0)
        # Claim (200/900) rides on the first hate; the 900 VE drains 300 over 5 s,
        # but Provoke's 1,800 CE and the 200 claim CE stay.
        self.assertEqual(mob.enmity[99] - mob.enmity_ve[99], 2000)
        self.assertEqual(mob.enmity_ve[99], 600)

    def test_each_enmity_meter_is_capped_at_thirty_thousand(self):
        mob = self.monster(level=60)
        self.world.add_mob_hate(mob, 99, now=1.0, ce=40000, ve=40000)
        self.assertEqual(mob.enmity_ve[99], 30000)
        self.assertEqual(mob.enmity[99], 60000)

    def test_volatile_decay_can_flip_the_highest_hate(self):
        mob = self.monster(level=60)
        # Player 1 claims the mob, so player 2 starts without the claim bonus.
        self.world.add_mob_hate(mob, 1, now=1.0, ce=1000, ve=2000)
        self.world.add_mob_hate(mob, 2, now=1.0, ce=2500, ve=0)
        self.assertEqual(mob.enmity[1], 4100)          # 1200 CE + 2900 VE
        self.assertEqual(mob.enmity[2], 2500)
        self.world.decay_mob_enmity(mob, 31.0)         # 30 s -> -1800 VE
        self.assertEqual(mob.enmity[1], 2300)
        self.assertLess(mob.enmity[1], mob.enmity[2])

    # --- en-spells ---------------------------------------------------------------------

    def engaged_mob(self, hp: int = 10000):
        """Load zone 100, stand on a live monster and engage it."""
        self.session.zone = 100
        self.session.pos = list(self.world.zones.position(100))
        self.session.load_zone_entities()
        self.session.zone_loaded = True
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.hp = mob.hp_max = hp
        self.session.pos = [mob.x, mob.y, mob.z, 0]
        self.session.engaged_id = mob.id
        self.session.engaged_targid = mob.targid
        self.session.next_attack_at = 0.0
        self.session.queue.clear()
        return mob

    def round_actions(self):
        return [message for message in self.session.queue
                if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]

    def test_enspell_damage_rides_the_melee_action(self):
        """A landed swing carries the en-spell in the 0x028 additional-effect block."""
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({0: 16534})
        mob = self.engaged_mob()
        potency = combat.enspell_potency(
            int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0)))
        self.session.add_effect(effects.ENFIRE, duration=600, power=potency)
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 100, False)):
            self.session.tick(time.time())

        actions = self.round_actions()
        self.assertEqual(len(actions), 1)
        # The RDM job-point "En"-spell gifts add 23 to the tier-I base.
        expected = potency + 23
        self.assertEqual(action_additional_effects(actions[0]),
                         [{"proc": 1, "info": 0, "value": expected,
                           "message": packets.MESSAGE_ADD_EFFECT_ADDITIONAL_DAMAGE}])
        # The physical hit and the en-spell both come off the monster's HP.
        self.assertEqual(mob.hp, 10000 - 100 - expected)

    def test_tier_one_enspell_rides_both_hands(self):
        self.session.char.update(main_job=5, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.equip({0: 21904, 1: 21905})
        mob = self.engaged_mob(hp=20000)
        potency = combat.enspell_potency(
            int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0)))
        self.session.add_effect(effects.ENFIRE, duration=600, power=potency)
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 10, False)):
            self.session.tick(time.time())

        adds = action_additional_effects(self.round_actions()[0])
        self.assertEqual([add["proc"] for add in adds], [1, 1])
        expected = potency + 23
        self.assertEqual([add["value"] for add in adds], [expected, expected])
        self.assertEqual(mob.hp, 20000 - 20 - 2 * expected)

    def test_tier_two_enspell_procs_on_the_first_swing_only_and_ramps(self):
        self.session.char.update(main_job=5, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.equip({0: 21904, 1: 21905})
        mob = self.engaged_mob(hp=20000)
        base = combat.enspell_potency(
            int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0)))
        self.session.add_effect(effects.ENFIRE_II, duration=600, power=0)

        for round_no in range(2):
            self.session.next_attack_at = 0.0
            self.session.queue.clear()
            with mock.patch.object(self.world, "player_attack",
                                   return_value=(False, 10, False)):
                self.session.tick(time.time())
            adds = action_additional_effects(self.round_actions()[0])
            self.assertEqual(len(adds), 2)                 # main hand and off hand
            self.assertEqual(adds[0]["proc"], 1)
            self.assertEqual(adds[0]["value"], base + 23 + round_no)
            self.assertIsNone(adds[1])                      # off hand never procs tier II
            self.assertEqual(self.session.effect_state[effects.ENFIRE_II]["power"],
                             round_no + 1)
        self.assertEqual(mob.hp,
                         20000 - 4 * 10 - (base + 23) - (base + 1 + 23))

    def test_casting_an_enspell_replaces_the_old_one_and_resets_tier_two(self):
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        now = time.time()
        fire = self.service.spell(312)                      # Enfire II
        self.session.resolve_self_spell(fire, now, effects.for_spell(fire["name"]))
        self.assertEqual(self.session.effect_power(effects.ENFIRE_II), 0)
        self.session.effect_state[effects.ENFIRE_II]["power"] = 20

        blizzard = self.service.spell(101)                  # Enblizzard (tier I)
        self.session.resolve_self_spell(blizzard, now, effects.for_spell(blizzard["name"]))
        self.assertFalse(self.session.has_effect(effects.ENFIRE_II))
        self.assertEqual(
            self.session.effect_power(effects.ENBLIZZARD),
            combat.enspell_potency(
                int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0))))

    def test_the_en_spell_can_finish_the_target(self):
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({0: 16534})
        mob = self.engaged_mob(hp=150)
        potency = combat.enspell_potency(
            int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0)))
        self.assertGreater(potency, 50)
        self.session.add_effect(effects.ENFIRE, duration=600, power=potency)
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 100, False)):
            self.session.tick(time.time())
        self.assertFalse(mob.alive)
        self.assertEqual(mob.hp, 0)

    def test_enspell_weapon_bonus_applies_only_to_its_own_hand(self):
        """Enriching Sword +30 must not add +30 to the Pukulatmuj's swing as well."""
        self.session.char.update(main_job=5, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.equip({0: 21606, 1: 20614})
        self.engaged_mob()
        sheet = self.session.stat_sheet()
        main_bonus, _percent = self.session._enspell_gear_bonus(sheet, off_hand=False)
        off_bonus, _percent = self.session._enspell_gear_bonus(sheet, off_hand=True)
        # The RDM job-point "En"-spell gifts (+23 total) still apply to both hands.
        self.assertEqual(main_bonus, 30 + 23)
        self.assertEqual(off_bonus, 11 + 23)

    def test_augmented_enspell_multiplier_stays_on_its_own_hand(self):
        """Crocea Mors path C is +500% on that sword, not on the off-hand dagger."""
        self.session.char.update(main_job=5, main_level=99, sub_job=13, sub_level=49)
        self.session._trait_cache = None
        self.service.save_equipment(
            int(self.character["id"]), {0: (0, 30, 21627), 1: (0, 31, 20614)})
        block = augments.bundle("C", 25, 2, 63)
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity, extra) "
            "VALUES (?, 0, 30, 21627, 1, ?)", (int(self.character["id"]), block))
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity, extra) "
            "VALUES (?, 0, 31, 20614, 1, X'')", (int(self.character["id"]),))
        self.engaged_mob()
        sheet = self.session.stat_sheet()
        self.assertEqual(self.session._enspell_gear_bonus(sheet, off_hand=False),
                         (23, 500))
        self.assertEqual(self.session._enspell_gear_bonus(sheet, off_hand=True),
                         (34, 0))

    def test_the_sworn_r30_set_carries_its_enspell_damage(self):
        """The set is the RDM en-spell suit: +8/+10/+7/+9/+7 across its five pieces."""
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({4: 24137, 5: 24140, 6: 24143, 7: 24146, 8: 24149})
        # +41 from the suit and +23 from the RDM job-point "En"-spell gifts.
        self.assertEqual(
            int(self.session.combat_mods().get(mod.ENSPELL_DMG_BONUS, 0)), 41 + 23)

    def test_composure_and_the_enspell_merit_raise_the_hit(self):
        self.session.char.update(main_job=5, main_level=99, sub_job=0, sub_level=0)
        self.session._trait_cache = None
        self.equip({0: 16534})
        mob = self.engaged_mob()
        sheet = self.session.stat_sheet()
        potency = combat.enspell_potency(
            int(self.session.effective_skills()[0].get(packets.SKILL_ENHANCING, 0)))
        self.session.add_effect(effects.ENFIRE, duration=600, power=potency)
        # The RDM gift's +23 rides every en-spell hit, like the Sworn suit's line.
        self.assertEqual(self.session._enspell_hit(mob, sheet)["damage"], potency + 23)

        self.session.add_effect(effects.COMPOSURE, duration=600)
        self.assertEqual(self.session._enspell_hit(mob, sheet)["damage"],
                         (potency + 23) * 3)
        self.session.remove_effect(effects.COMPOSURE, quiet=True)

        self.service.save_merit(int(self.character["id"]), 0x0914, 5)
        self.session._merit_counts = None
        self.assertEqual(self.session._enspell_hit(mob, sheet)["damage"],
                         potency + 23 + 15)


if __name__ == "__main__":
    unittest.main()
