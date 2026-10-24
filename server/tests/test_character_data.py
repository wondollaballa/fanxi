"""The Data page: the 0x01B mastery byte, the snapshot and !reload."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from support import make_service

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
        self.session.queue.clear()
        self.session.reload_character()
        self.assertEqual(self.session.char["mastery_rank"], 4)
        self.assertEqual(self.session.char["gil"], 987654)
        kinds = {packet_kind(message) for message in self.session.queue}
        self.assertIn(0x01B, kinds)   # the Profile byte
        self.assertIn(0x063, kinds)   # merits / job points
        self.assertIn(0x055, kinds)   # key-item bitmaps
        self.assertIn(0x020, kinds)   # the inventory, including the gil row

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
        self.assertEqual(self.service.trust(896)["model"], 3000)
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

    def test_register_all_home_points_is_idempotent(self):
        self.service.register_all_home_points(self.character["id"])
        first = self.service.character_data(self.character["id"])["home_points"]
        self.assertEqual(first["registered"], first["total"])
        self.service.register_all_home_points(self.character["id"])
        second = self.service.character_data(self.character["id"])["home_points"]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
