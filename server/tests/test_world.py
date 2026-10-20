"""The populated world: content loading, spawn triggers, NPC talk, combat and quests."""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def msg_types(session):
    return [struct.unpack_from("<H", message, 0)[0] & 0x1FF for message in session.queue]


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
        self.assertEqual(len(self.service.npcs_for_zone(246)), 3)
        self.assertEqual(len(self.service.monster_spawns_for_zone(100)), 6)
        self.assertEqual(self.service.quest_by_key("pest_control")["required_kills"], 3)
        inventory = self.service.inventory(self.character["id"])
        self.assertEqual(inventory[0]["quantity"], 1000)
        self.assertTrue(any(item["item_id"] == 16534 for item in inventory))

    def test_zone_in_packet_sizes(self):
        self.assertEqual(len(self.session.login_packet()), 260)
        self.assertEqual(len(self.session.job_info()), 132)
        self.assertEqual(len(self.session.char_status()), 100)
        self.assertEqual(len(self.session.char_update()), 108)
        self.assertEqual(len(self.session.char_stats()), 112)
        self.assertEqual(len(self.session.party_member()), 40)
        self.assertEqual(len(self.session.item_max()), 100)

    def test_zone_in_does_not_spawn_and_first_position_does(self):
        self.assertEqual(len(self.session.entities), 3)
        self.assertNotIn(0x00E, msg_types(self.session))
        self.session.sync_entities()
        types = msg_types(self.session)
        self.assertEqual(types.count(0x00E), 3)
        spawn = next(m for m in self.session.queue
                     if (struct.unpack_from("<H", m, 0)[0] & 0x1FF) == 0x00E)
        header = struct.unpack_from("<H", spawn, 0)[0]
        self.assertEqual(header & 0x1FF, 0x00E)
        self.assertEqual(header >> 9, 0x58 // 4)
        body = spawn[4:]
        self.assertEqual(struct.unpack_from("<I", body, 0)[0], 0x01000000 | (246 << 12) | 0x100)
        self.assertEqual(struct.unpack_from("<H", body, 4)[0], 0x100)
        self.assertEqual(body[48:59], b"Fanxi Guide")
        self.assertEqual(body[36], 0x40)
        self.assertEqual(body[33], 0x08)

    def test_talk_starts_the_guide_quest(self):
        guide = next(entity for entity in self.session.entities if entity.script == "guide")
        self.talk(guide)
        self.assertIn(0x017, msg_types(self.session))
        quest = self.service.quest_by_key("pest_control")
        state = self.service.quest_state(self.character["id"], quest["id"])
        self.assertEqual(state["state"], "active")

    def test_talk_requires_range(self):
        guide = next(entity for entity in self.session.entities if entity.script == "guide")
        self.session.pos = [guide.x + 50, guide.y, guide.z, 0]
        packet = bytearray(12)
        struct.pack_into("<IHH", packet, 4, guide.id, guide.targid, packets.ACTION_TALK)
        self.session.queue.clear()
        self.session.action(bytes(packet))
        self.assertIn(0x017, msg_types(self.session))
        self.assertIsNone(self.service.quest_state(
            self.character["id"], self.service.quest_by_key("pest_control")["id"]))

    def test_moogle_opens_a_shop_and_sells_potions(self):
        moogle = next(entity for entity in self.session.entities if entity.script == "moogle")
        self.talk(moogle)
        types = msg_types(self.session)
        self.assertIn(0x03E, types)
        self.assertIn(0x03C, types)
        self.assertEqual(len(self.session.shop_items), 3)
        # Buy two potions at 50 gil each.
        packet = bytearray(16)
        struct.pack_into("<IHHB", packet, 4, 2, 0, 0, 0)
        self.session.queue.clear()
        self.session.buy(bytes(packet))
        self.assertIn(0x03F, msg_types(self.session))
        self.assertEqual(self.service.character(self.character["id"])["gil"], 900)
        inventory = self.service.inventory(self.character["id"])
        potion = next(item for item in inventory if item["item_id"] == 4112)
        self.assertEqual(potion["quantity"], 4)

    def test_attack_kill_awards_exp_gil_and_quest_progress(self):
        quest = self.service.quest_by_key("pest_control")
        self.service.start_quest(self.character["id"], quest["id"])
        self.zone(100)
        mob = self.session.entities[0]
        self.attack(mob)
        self.assertEqual(self.session.engaged_id, mob.id)
        self.assertEqual(mob.engaged_char_id, self.character["char_id"])
        self.world.player_attack = lambda char, entity: (False, 999, False)
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

    def test_quest_turn_in_pays_once(self):
        quest = self.service.quest_by_key("pest_control")
        self.service.start_quest(self.character["id"], quest["id"])
        self.service.advance_quest(self.character["id"], quest["id"], 3)
        guide = next(entity for entity in self.session.entities if entity.script == "guide")
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
        mob = self.session.entities[0]
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


if __name__ == "__main__":
    unittest.main()
