"""The Data page: the 0x01B mastery byte, the snapshot and //reload."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

from fanxi_server.game import packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


def packet_kind(message: bytes) -> int:
    return struct.unpack_from("<H", message, 0)[0] & 0x1FF


class CharacterDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        account = self.service.register("tester", "password123").account
        self.character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = ZoneSession(
            self.world, None,
            self.service.character_record(
                self.service.character(self.character["id"]), "Fanxi"))
        self.session.set_key(bytes(20))
        self.session.logged_in = True
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.zone = 246
        self.session.pos = list(self.world.zones.position(246))
        self.session.load_zone_entities()
        self.session.queue.clear()

    def test_mastery_rank_lands_in_the_0x01b_byte(self):
        self.service.set_mastery_rank(self.character["id"], 7)
        self.session.reload_character()
        self.assertEqual(self.session.dancer()[0x62], 7)
        # The byte is clamped to retail's 0..10 window, not just validated on write.
        self.service.db.execute("UPDATE characters SET mastery_rank = 42 WHERE id = ?",
                                (self.character["id"],))
        self.session.reload_character()
        self.assertEqual(self.session.dancer()[0x62], 10)

    def test_reload_rereads_merits_gil_and_mastery(self):
        self.service.set_mastery_rank(self.character["id"], 4)
        self.service.set_gil(self.character["id"], 987654)
        self.service.top_off_merits(self.character["id"])
        self.service.save_merit_layout(self.character["id"], {0x0180: 5})
        self.session.queue.clear()
        self.session.reload_character()
        self.assertEqual(self.session.merit_counts()[0x0180], 5)
        self.assertEqual(self.session.char["mastery_rank"], 4)
        self.assertEqual(self.session.char["gil"], 987654)
        kinds = {packet_kind(message) for message in self.session.queue}
        self.assertIn(0x01B, kinds)   # the Profile byte
        self.assertIn(0x063, kinds)   # merits / job points
        self.assertIn(0x055, kinds)   # key-item bitmaps
        self.assertIn(0x020, kinds)   # the inventory, including the gil row

    def test_reload_sends_no_self_entity_update(self):
        """A reload must not queue any self 0x00D.

        The client asks for its own entity after a reload (C2S 0x016/0x017 for targid
        0x400), and the full-spawn reply to that request carries the name and model
        blocks that reset the player entity (green name, no menus until a relog).  The
        vitals the Data page can change already ride 0x061, 0x037 and 0x0DF; the reload
        has no reason to poke the entity at all.
        """
        self.session.queue.clear()
        self.session.reload_character()
        kinds = [packet_kind(message) for message in self.session.queue]
        self.assertIn(0x061, kinds)   # stats / max HP and MP
        self.assertIn(0x037, kinds)   # status/HP
        self.assertIn(0x0DF, kinds)   # party member HP/MP/TP
        self.assertNotIn(0x00D, kinds)

    def test_mid_session_self_entity_request_does_not_respawn(self):
        """The post-reload self request gets the General block, never the full spawn."""
        self.session.zone_loaded = True
        request = bytearray(20)
        struct.pack_into("<HHH", request, 0, 0x017, 0x0A, 0)
        struct.pack_into("<H", request, 4, 0x400)
        self.session.queue.clear()
        self.session.request_entity(bytes(request))
        kinds = [packet_kind(message) for message in self.session.queue]
        self.assertIn(0x037, kinds)
        updates = [message for message in self.session.queue
                   if packet_kind(message) == 0x00D]
        self.assertEqual(len(updates), 1)
        body = updates[0][4:]
        self.assertEqual(len(body), 0x44)
        self.assertEqual(body[6], packets.SEND_HP)
        self.assertFalse(body[6] & packets.SEND_NAME)
        self.assertFalse(body[6] & packets.SEND_MODEL)

    def test_zone_in_self_entity_request_still_spawns_the_player(self):
        """Before the zone-in finishes the full spawn is what creates the self entity."""
        request = bytearray(8)
        struct.pack_into("<HHH", request, 0, 0x016, 0x04, 0)
        struct.pack_into("<H", request, 4, 0x400)
        self.session.zone_loaded = False
        self.session.queue.clear()
        self.session.request_entity(bytes(request))
        updates = [message for message in self.session.queue
                   if packet_kind(message) == 0x00D]
        self.assertEqual(len(updates), 1)
        body = updates[0][4:]
        self.assertEqual(len(body), 0x68)
        self.assertTrue(body[6] & packets.SEND_NAME)
        self.assertTrue(body[6] & packets.SEND_MODEL)

    def test_snapshot_reports_the_same_values(self):
        self.service.set_mastery_rank(self.character["id"], 3)
        self.service.top_off_merits(self.character["id"])
        data = self.service.character_data(self.character["id"])
        self.assertEqual(data["mastery_rank"], 3)
        self.assertEqual(data["merits"]["points"], data["merits"]["cap"])
        self.assertEqual(data["job_points"]["jobs"], 22)
        self.assertTrue(data["job_points"]["all_capped"])

    def test_progress_snapshot_and_writes(self):
        data = self.service.character_data(self.character["id"])
        self.assertEqual(len(data["jobs"]), 22)
        self.assertEqual(len(data["crafts"]), 10)
        self.assertEqual(data["trusts"]["spells"], 122)
        self.assertTrue(data["trusts"]["summoning"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM trusts"), 122)
        self.assertEqual(self.service.trust(896)["job"], 4)
        self.assertEqual(self.service.trust(896)["species"], 297)   # Tarutaru
        self.assertEqual(self.service.trust(896)["model"], 3000)
        self.assertEqual(len(self.service.trust_spells(896, 99)), 30)
        self.assertEqual(len(self.service.trust_spells(898, 1)), 1)
        self.assertEqual(self.service.trust_spells(1002, 99), [])
        self.assertEqual(data["ranks"]["sandoria"], 1)

        self.service.set_all_jobs(self.character["id"], 99)
        self.service.set_all_master_levels(self.character["id"], 50)
        self.service.set_exemplar_points(self.character["id"], 123456)
        self.service.set_mission_rank(self.character["id"], 1, 6, 4321)
        self.service.max_fame(self.character["id"])
        self.service.max_crafts(self.character["id"])
        data = self.service.character_data(self.character["id"])
        self.assertEqual(data["jobs"][0]["level"], 99)
        self.assertEqual(data["jobs"][0]["master_level"], 50)
        self.assertEqual(data["ranks"]["bastok"], 6)
        self.assertEqual(data["ranks"]["points"], 4321)
        self.assertTrue(all(entry["value"] == 255 for entry in data["fame"]))
        self.assertTrue(all(craft["value"] == 100 for craft in data["crafts"]))
        self.assertEqual(data["exemplar"]["points"], 123456)

    def test_rank_mastery_and_crafts_reach_the_packets(self):
        self.service.set_all_jobs(self.character["id"], 99)
        self.service.set_all_master_levels(self.character["id"], 12)
        self.service.set_exemplar_points(self.character["id"], 90000)
        self.service.set_mission_rank(self.character["id"], 0, 5, 123)
        self.service.set_craft_skills(self.character["id"], {"48": 100, "49": 42})
        self.session.reload_character()

        stats = self.session.char_stats()
        self.assertEqual(struct.unpack_from("<H", stats, 4 + 0x42)[0], 5)
        self.assertEqual(struct.unpack_from("<H", stats, 4 + 0x44)[0], 123)
        self.assertEqual(stats[4 + 0x61], 12)
        self.assertEqual(struct.unpack_from("<I", stats, 4 + 0x64)[0], 90000)
        self.assertEqual(struct.unpack_from("<I", stats, 4 + 0x68)[0], 30000)

        skills = self.session.char_skills()
        fishing = struct.unpack_from("<H", skills, 4 + 124 + 48 * 2)[0]
        woodworking = struct.unpack_from("<H", skills, 4 + 124 + 49 * 2)[0]
        self.assertEqual(fishing & 0x7FFF, 100)
        self.assertEqual(woodworking & 0x7FFF, 42)

    def test_augment_path_cap_writes_the_bundle(self):
        self.service.add_item(self.character["id"], 23761, 1)
        data = self.service.character_data(self.character["id"])
        self.assertEqual(len(data["augments"]), 1)
        item = data["augments"][0]
        self.assertEqual(len(item["paths"]), 4)
        from fanxi_server.game import augment_gear, augments
        result = augment_gear.cap(
            self.service, self.character["id"], item["container"], item["slot"], "C")
        self.assertEqual(result["path"]["key"], "C")
        row = next(row for row in self.service.inventory(self.character["id"])
                   if int(row["item_id"]) == 23761)
        decoded = augments.decode(row["extra"])
        self.assertEqual(decoded["path"], "C")
        self.assertEqual(decoded["rank"], 30)
        self.assertEqual(decoded["index"], 448)

    def test_unity_belt_is_offered_in_the_rp_card(self):
        """A purchased Unity +1 piece must reach the Data page's RP list."""
        self.service.add_item(self.character["id"], 28413, 1)
        data = self.service.character_data(self.character["id"])
        item = next(row for row in data["augments"] if row["item_id"] == 28413)
        self.assertEqual(item["name"], "Kentarch Belt +1")
        self.assertEqual(item["kind"], "unity")
        self.assertEqual(item["set"], "Unity +1")
        self.assertEqual(item["slot_name"], "waist")
        self.assertIsNone(item["current"])
        self.assertEqual(len(item["paths"]), 1)
        path = item["paths"][0]
        self.assertEqual(path["key"], "A")
        self.assertEqual(path["rank"], 15)
        self.assertEqual(path["bundle"], 355)
        self.assertEqual(path["augments"], ["STR+10", "DEX+10"])

        from fanxi_server.game import augment_gear, augments
        augment_gear.cap(self.service, self.character["id"],
                         item["container"], item["slot"], "A")
        row = next(row for row in self.service.inventory(self.character["id"])
                   if int(row["item_id"]) == 28413)
        decoded = augments.decode(row["extra"])
        self.assertEqual(decoded["rank"], 15)
        self.assertEqual(decoded["index"], 355)

    def test_unity_armour_piece_is_offered_in_the_rp_card(self):
        """Tatena. Gote +1 was reported missing from the RP list.

        The registry only carried accessories (plus Loess Barbuta +1) and the grip,
        so a Unity armour piece in a bag never reached the card at all.
        """
        self.service.add_item(self.character["id"], 27149, 1)
        data = self.service.character_data(self.character["id"])
        item = next(row for row in data["augments"] if row["item_id"] == 27149)
        self.assertEqual(item["name"], "Tatena. Gote +1")
        self.assertEqual(item["kind"], "unity")
        self.assertEqual(item["set"], "Unity +1")
        self.assertEqual(item["slot_name"], "hands")
        self.assertIsNone(item["current"])
        path = item["paths"][0]
        self.assertEqual(path["key"], "A")
        self.assertEqual(path["rank"], 15)
        self.assertEqual(path["bundle"], 389)
        self.assertEqual(path["augments"], [
            "Accuracy+40", "All Attr.+10", '"Triple Attack" +4%'])

        from fanxi_server.game import augment_gear, augments
        augment_gear.cap(self.service, self.character["id"],
                         item["container"], item["slot"], "A")
        row = next(row for row in self.service.inventory(self.character["id"])
                   if int(row["item_id"]) == 27149)
        decoded = augments.decode(row["extra"])
        self.assertEqual(decoded["rank"], 15)
        self.assertEqual(decoded["index"], 389)

    def test_armory_purchase_refreshes_the_rp_card(self):
        """The Armory snapshot must already carry the new Unity belt."""
        self.service.top_off_gil(self.character["id"])
        for item_id, name, bundle, augments in (
                (28413, "Kentarch Belt +1", 355, ["STR+10", "DEX+10"]),
                (28428, "Sailfi Belt +1", 292, ["STR +15", "Double Attack +5%"])):
            added = self.service.armory_add(self.character["id"], item_id, 1)
            self.assertEqual(added["item_id"], item_id)
            data = self.service.character_data(self.character["id"])
            item = next(row for row in data["augments"] if row["item_id"] == item_id)
            self.assertEqual(item["name"], name)
            self.assertEqual(item["kind"], "unity")
            self.assertEqual(item["paths"][0]["bundle"], bundle)
            self.assertEqual(item["paths"][0]["augments"], augments)
            self.assertTrue(next(row for row in data["purchases"]
                                 if row["item_id"] == item_id)["owned"])

    def test_bunzi_hat_purchase_reaches_the_rp_card(self):
        self.service.top_off_gil(self.character["id"])
        self.service.armory_add(self.character["id"], 23760, 1)
        data = self.service.character_data(self.character["id"])
        item = next(row for row in data["augments"] if row["item_id"] == 23760)
        self.assertEqual(item["name"], "Bunzi's Hat")
        self.assertEqual(item["set"], "Bunzi's Attire Set")
        self.assertEqual(item["kind"], "odyssey")
        self.assertIsNone(item["current"])
        self.assertEqual(item["paths"][0]["bundle"], 433)
        self.assertIn('"Store TP"+8', item["paths"][0]["augments"])

    def test_register_all_home_points_is_idempotent(self):
        self.service.register_all_home_points(self.character["id"])
        first = self.service.character_data(self.character["id"])["home_points"]
        self.assertEqual(first["registered"], first["total"])
        self.service.register_all_home_points(self.character["id"])
        second = self.service.character_data(self.character["id"])["home_points"]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
