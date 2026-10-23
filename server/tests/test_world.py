"""The populated world: content loading, spawn triggers, NPC talk, combat and quests."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import base_stats, content, merits, modifiers as mod, packets
from fanxi_server.game.world import SYNC_RANGE, World
from fanxi_server.game.zone import ALL_CONTAINERS, ZoneSession, job_id, sub


def msg_types(session):
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


def action_sub_kind(message: bytes) -> int:
    """Read a 0x028 result's sub-kind: 0 is the main hand, 1 the off hand."""
    data = message[5:]
    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32 + 4 + 3 + 2
    value = 0
    for index in range(12):
        value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
    return value


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
        self.assertEqual(len(self.session.char_status()), 96)
        self.assertEqual(len(self.session.char_update()), 108)
        self.assertEqual(len(self.session.char_stats()), 112)
        self.assertEqual(len(self.session.party_member()), 40)
        self.assertEqual(len(self.session.item_max()), 100)

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
        session.char["moghouse"] = 1
        for mode, destination in ((1, 234), (2, 235), (3, 236)):
            with self.subTest(mode=mode):
                session.zone = 234
                session.char["moghouse"] = 1
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
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]),
                         int(mob.targid), packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 35)     # Provoke
        self.session.job_ability(bytes(packet), int(mob.targid))
        self.assertIn(0x028, msg_types(self.session))
        self.assertEqual(mob.engaged_char_id, int(self.session.char["char_id"]))
        self.assertGreater(self.session.ability_recasts.get(5, 0), time.time())

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
        self.session.queue.clear()
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK_OFF)
        self.session.action(bytes(packet))
        self.assertEqual(self.player_animation(), 0)
        self.assertIsNone(self.session.engaged_id)

    def attack_off(self, mob):
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK_OFF)
        self.session.action(bytes(packet))

    def test_range_disengage_keeps_the_engagement_and_the_stance(self):
        """The client's own /attack off at four yalms is not a request to stop fighting."""
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.attack_off(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertEqual(self.player_animation(), 1)
        self.assertIn(0x058, msg_types(self.session))
        self.assertNotIn("You disengage.", self.chats())
        self.assertIn("You stay engaged at range; use !disengage to break it.", self.chats())

    def test_reengaging_the_same_target_is_quiet(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.queue.clear()
        self.attack(mob)
        self.assertEqual(self.chats().count("You engage %s." % mob.name), 0)
        self.assertEqual(self.session.engaged_id, mob.id)

    def test_the_range_hint_is_not_repeated_every_crossing(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.attack_off(mob)
        # A later crossing is still the same engagement, so the hint stays quiet.
        self.session.range_disengage_at = 0.0
        self.attack_off(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertEqual(
            self.chats().count("You stay engaged at range; use !disengage to break it."), 1)

    def test_a_quick_reengage_does_not_turn_the_next_crossing_into_a_double_tap(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.attack_off(mob)
        # The client draws again as soon as the target is back in reach; that must clear
        # the second-press window so the next automatic attack-off is ignored too.
        self.attack(mob)
        self.session.pos = [mob.x + 10.0, mob.y, mob.z, 0]
        self.attack_off(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertEqual(self.player_animation(), 1)

    def test_a_second_attack_off_at_range_breaks_the_engagement(self):
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
        self.assertIn("You disengage.", self.chats())

    def test_attack_off_beyond_engage_range_disengages(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 31.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.attack_off(mob)
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You disengage.", self.chats())

    def test_attack_beyond_engage_range_is_refused(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.session.pos = [mob.x + 31.0, mob.y, mob.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, mob.id, mob.targid, packets.ACTION_ATTACK)
        self.session.queue.clear()
        self.session.action(bytes(packet))
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You are too far away.", self.chats())

    def test_engaged_target_past_draw_range_is_dropped(self):
        self.zone(100)
        mob = next(entity for entity in self.session.entities if entity.kind == "mob")
        self.attack(mob)
        self.session.pos = [mob.x + 31.0, mob.y, mob.z, 0]
        self.session.queue.clear()
        self.session.tick(time.time())
        self.assertIsNone(self.session.engaged_id)
        self.assertEqual(self.player_animation(), 0)
        self.assertIn("You lose your target.", self.chats())

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

    def test_zone_in_marks_every_container_ready(self):
        """The final 0x01D names every bag zone-in streamed, so no bag starts blank."""
        self.session.queue.clear()
        self.session.queue += self.session.inventory_packets()
        state, container, flags = last_sync(self.session)
        self.assertEqual((state, container), (1, 18))
        self.assertEqual(flags, ALL_CONTAINERS)

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
        """!job stores the old job, pulls the new one and leaves a clean inventory."""
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
        self.assertIn(23895, bag_ids)
        self.assertTrue(any("Stored 4 BLM items" in line for line in self.chats()))
        self.assertTrue(any("Pulled 5 RUN items" in line for line in self.chats()))

    def test_storage_stores_only_slipped_job_gear(self):
        """!storage store nin moves NIN gear onto its slip and out of every bag."""
        for container, slot, item_id in ((0, 50, 23907), (1, 5, 23975), (8, 9, 23566)):
            self.give(container, slot, item_id)
        self.give(0, 51, 21906)  # Kikoku: NIN, but no storage slip
        self.give(0, 52, 25491)  # Ninja Nodowa: NIN, but no storage slip
        self.give(0, 53, 23895)  # WAR-only: not NIN gear
        self.give(0, 54, 21602)  # all jobs: NIN can wear it, but it is not NIN gear
        self.session.queue.clear()
        self.session.command("storage store nin".split())
        self.assertEqual(self.stored(), {23907: (1, 32), 23975: (1, 33), 23566: (1, 30)})
        rows = self.service.inventory(self.character["id"])
        bag = {(int(row["container"]), int(row["slot"])) for row in rows}
        for source in ((0, 50), (1, 5), (8, 9)):
            self.assertNotIn(source, bag)
        for left in ((0, 51), (0, 52), (0, 53), (0, 54)):
            self.assertIn(left, bag)
        self.assertFalse(any(int(row["container"]) == 2 for row in rows))

        parsed = [struct.unpack_from("<IIHBB", message, 4) for message in self.session.queue
                  if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x020]
        cleared = {(p[3], p[4]) for p in parsed if not p[2]}
        self.assertEqual(cleared, {(0, 50), (1, 5), (8, 9)})
        self.assertEqual([p for p in parsed if p[2]], [])
        sync = next(struct.unpack_from("<BB2xI", message, 4)
                    for message in reversed(self.session.queue)
                    if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x01D)
        self.assertEqual(sync[0], 1)
        self.assertEqual(sync[2], ALL_CONTAINERS)
        self.assertIn("Stored 3 NIN items on storage slips (3 total).", self.chats())
        self.assertIn("Slips: 30:1, 32:1, 33:1.", self.chats())
        self.assertIn("No slip for: Kikoku 119 III, Ninja Nodowa +2.", self.chats())

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
        self.assertIn("No storable NIN gear left in your bags.", self.chats())
        self.assertIn("Left 1 equipped NIN piece on.", self.chats())

    def test_storage_grab_returns_gear_to_the_bags(self):
        """!storage grab nin puts the set back in the inventory, ready to wear."""
        self.give(0, 50, 23907)
        self.give(8, 5, 23975)
        self.session.command("storage store nin".split())
        self.session.queue.clear()
        self.session.command("storage grab nin".split())
        self.assertEqual(self.stored(), {})
        rows = self.service.inventory(self.character["id"])
        inventory = {int(row["item_id"]) for row in rows if int(row["container"]) == 0}
        self.assertTrue({23907, 23975} <= inventory)
        self.assertTrue(any(line.startswith("Took 2 items off the storage slips")
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
        self.assertIn("1 other job item remains on the slips.", self.chats())

        self.session.queue.clear()
        self.session.command("storage grab all".split())
        self.assertEqual(self.stored(), {})
        rows = self.service.inventory(self.character["id"])
        inventory = {int(row["item_id"]) for row in rows if int(row["container"]) == 0}
        self.assertTrue({23907, 23895} <= inventory)

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
        self.assertIn("Storage slips: 1 item (32:1).", self.chats())
        self.assertIn("Use !storage grab <job|all> to take them back.", self.chats())

    def test_storage_accepts_the_slash_bang_chat_form(self):
        """/!storage reaches the same command as !storage (the client sends the slash)."""
        self.give(0, 50, 23907)
        text = "/!storage store nin"
        payload = bytearray(2 + len(text) + 1)
        payload[2:2 + len(text)] = text.encode("ascii")
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x0B5)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x0B5, bytes(payload))))
        self.assertEqual(self.stored(), {23907: (1, 32)})
        self.assertIn("Stored 1 NIN item on storage slips (1 total).", self.chats())

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
        self.assertTrue(any("You start casting Utsusemi Ichi" in line for line in self.chats()))
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
        self.assertIn("You start casting Monomi Ichi.", self.chats())
        self.assertEqual(int(self.session.char["mp_current"]), 0)

    def test_dawn_mulsum_heals_pet_percentage_and_refills(self):
        self.give(0, 50, 5411, 3)
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 5411, 33)",
            (int(self.character["id"]),))
        self.session.char["hp_current"] = 1
        self.session.char["pet_hp_max"] = 1000
        self.session.char["pet_hp"] = 100
        packet = bytearray(20)
        struct.pack_into("<I", packet, 8, 5411)
        self.session.queue.clear()
        self.session.item_use(bytes(packet))
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
        packet = bytearray(20)
        struct.pack_into("<I", packet, 8, 5411)
        self.session.queue.clear()
        self.session.item_use(bytes(packet))
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
        packet = bytearray(20)
        struct.pack_into("<I", packet, 8, 5411)
        self.session.queue.clear()
        self.session.item_use(bytes(packet))
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
        """!locker store moves ammo/capes out of every bag and into the 9999-item locker."""
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
        self.assertIn("Stored 2 items in the locker (3/9999).", self.chats())

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
        """A 99-jug entry can be taken one stack at a time with !locker grab <name> 12."""
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

    def test_locker_capacity_is_9999(self):
        self.db.execute(
            "INSERT INTO char_locker (character_id, item_id, quantity) VALUES (?, 4112, 9999)",
            (int(self.character["id"]),))
        self.give(0, 50, 4112)
        self.session.queue.clear()
        self.session.command("locker store materials".split())
        self.assertEqual(self.locker_stored(), {4112: 9999})
        self.assertIn("Nothing in your bags matched materials.", self.chats())
        self.assertIn("The locker is full; 3 items stayed in your bags.", self.chats())

    def test_locker_status_and_list(self):
        self.give(0, 50, 22279)
        self.give(0, 51, 26258)
        self.session.command("locker store ammo".split())
        self.session.command("locker store back".split())
        self.session.queue.clear()
        self.session.command("locker".split())
        self.assertIn("Locker: 2/9999 items (2 kinds).", self.chats())
        self.session.queue.clear()
        self.session.command("locker list".split())
        lines = self.chats()
        self.assertTrue(any("Staunch Tathlum +1" in line for line in lines))
        self.assertTrue(any("Andartia's Mantle" in line for line in lines))

    def test_locker_accepts_the_slash_bang_chat_form(self):
        self.give(0, 50, 22279)
        text = "/!locker store ammo"
        payload = bytearray(2 + len(text) + 1)
        payload[2:2 + len(text)] = text.encode("ascii")
        header = bytearray(28)
        struct.pack_into("<H", header, 0, 0x0B5)
        self.session.queue.clear()
        self.session.parse(header, bytes(sub(0x0B5, bytes(payload))))
        self.assertEqual(self.locker_stored(), {22279: 1})
        self.assertIn("Stored 1 item in the locker (1/9999).", self.chats())

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
        """A NIN with two katanas sends an off-hand 0x028 in the same attack round."""
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
        self.assertEqual([action_sub_kind(message) for message in actions], [0, 1])


if __name__ == "__main__":
    unittest.main()
