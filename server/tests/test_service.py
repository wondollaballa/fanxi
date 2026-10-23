"""Account, character and launch-token behaviour."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from support import make_service

from fanxi_server.game import base_stats

from fanxi_server.security import hash_password
from fanxi_server.service import ApiError, FanxiService


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))

    def register(self, username="tester", password="password123"):
        return self.service.register(username, password, ip="127.0.0.1")

    def test_register_and_authenticate(self):
        result = self.register()
        self.assertEqual(result.account["username"], "tester")
        self.assertEqual(result.account["role"], "player")
        account = self.service.authenticate(result.token)
        self.assertEqual(account["id"], result.account["id"])
        self.assertNotIn("password_hash", result.account)

    def test_duplicate_username(self):
        self.register()
        with self.assertRaises(ApiError) as ctx:
            self.register()
        self.assertEqual(ctx.exception.status, 409)

    def test_short_password_rejected(self):
        with self.assertRaises(ApiError) as ctx:
            self.service.register("tester", "short")
        self.assertEqual(ctx.exception.status, 422)

    def test_bad_username_rejected(self):
        with self.assertRaises(ApiError) as ctx:
            self.service.register("no spaces", "password123")
        self.assertEqual(ctx.exception.status, 422)

    def test_login_and_wrong_password(self):
        self.register()
        result = self.service.login("tester", "password123", ip="127.0.0.1")
        self.assertTrue(result.token)
        with self.assertRaises(ApiError) as ctx:
            self.service.login("tester", "wrong-password", ip="127.0.0.1")
        self.assertEqual(ctx.exception.status, 401)

    def test_account_locks_after_failures(self):
        self.register()
        for _ in range(5):
            with self.assertRaises(ApiError):
                self.service.login("tester", "wrong", ip="127.0.0.1")
        with self.assertRaises(ApiError) as ctx:
            self.service.login("tester", "password123", ip="127.0.0.1")
        self.assertEqual(ctx.exception.status, 423)

    def test_logout_revokes_token(self):
        result = self.register()
        self.service.logout(result.token)
        with self.assertRaises(ApiError):
            self.service.authenticate(result.token)

    def test_character_creation_and_unlimited_mules(self):
        account = self.register().account
        character = self.service.create_character(account["id"], {
            "name": "Fanxi", "race": 1, "face": 1, "size": 1, "nation": 0, "main_job": 1,
        })
        self.assertEqual(character["name"], "Fanxi")
        self.assertEqual(character["zone"], 230)
        for name in ("Muleone", "Muletwo", "Mulethree"):
            created = self.service.create_character(account["id"], {"name": name, "race": 1})
            self.assertEqual(created["name"], name)
        self.assertEqual(len(self.service.list_characters(account["id"])), 4)

    def test_character_limit_when_configured(self):
        limited = FanxiService(replace(self.config, max_characters=1), self.db)
        account = self.register().account
        limited.create_character(account["id"], {"name": "Onlyone", "race": 1})
        with self.assertRaises(ApiError) as ctx:
            limited.create_character(account["id"], {"name": "Second", "race": 1})
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "character_limit")

    def test_character_name_validation(self):
        account = self.register().account
        for name in ("ab", "has space", "12345", "x" * 16):
            with self.assertRaises(ApiError):
                self.service.create_character(account["id"], {"name": name, "race": 1})

    def test_launch_token_is_single_use(self):
        result = self.register()
        character = self.service.create_character(result.account["id"], {"name": "Fanxi", "race": 1})
        character_id = character["id"]
        launch = self.service.launch(result.account, character_id, ip="127.0.0.1")
        self.assertTrue(launch["login_token"])
        account, session_hash = self.service.game_login({"login_token": launch["login_token"]}, "127.0.0.1")
        self.assertEqual(account["username"], "tester")
        self.assertEqual(len(session_hash), 16)
        self.assertEqual(self.service.game_session_character(session_hash), character_id)
        self.assertEqual(self.service.online_count(), 1)
        with self.assertRaises(ApiError) as ctx:
            self.service.game_login({"login_token": launch["login_token"]}, "127.0.0.1")
        self.assertEqual(ctx.exception.game_result, 0x14)

    def test_game_login_with_password(self):
        self.register()
        account, session_hash = self.service.game_login(
            {"username": "tester", "password": "password123"}, "127.0.0.1")
        self.assertEqual(account["username"], "tester")
        found = self.service.game_account_by_hash(session_hash)
        self.assertEqual(found["id"], account["id"])
        self.assertIsNone(self.service.game_account_by_hash(b"\0" * 16))

    def test_launch_needs_character(self):
        result = self.register()
        with self.assertRaises(ApiError) as ctx:
            self.service.launch(result.account, None)
        self.assertEqual(ctx.exception.code, "no_character")

    def test_status_and_news_seeded(self):
        status = self.service.status()
        self.assertEqual(status["name"], "Fanxi")
        self.assertEqual(status["accounts"], 0)
        self.assertGreaterEqual(len(self.service.news()), 1)
        self.assertEqual(self.service.world()["name"], "Fanxi")

    def test_registration_can_close(self):
        self.db.set_setting("registration_open", "0")
        with self.assertRaises(ApiError) as ctx:
            self.register()
        self.assertEqual(ctx.exception.status, 403)

    def test_starter_inventory_and_gil(self):
        account = self.register().account
        character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        inventory = {item["item_id"]: item["quantity"] for item in self.service.inventory(character["id"])}
        self.assertEqual(inventory[65535], 1000)
        self.assertEqual(inventory[4112], 2)
        self.assertEqual(inventory[16534], 1)
        self.assertEqual(character["gil"], 1000)

    def test_experience_levels_up(self):
        account = self.register().account
        character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        updated = self.service.award_exp_gil(character["id"], 120, 25)
        self.assertEqual(updated["levels_gained"], 1)
        self.assertEqual(updated["main_level"], 2)
        self.assertEqual(updated["exp"], 20)
        self.assertEqual(updated["gil"], 1025)
        # Max HP follows the retail grade tables, not a flat +20 per level.
        self.assertEqual(updated["hp"], base_stats.base_hp(1, 1, 2))
        self.assertEqual(updated["mp"], base_stats.base_mp(1, 1, 2))

    def test_quest_rewards_once(self):
        account = self.register().account
        character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        quest = self.service.quest_by_key("pest_control")
        self.service.start_quest(character["id"], quest["id"])
        self.service.advance_quest(character["id"], quest["id"], 3)
        state = self.service.complete_quest(character["id"], quest["id"])
        self.assertEqual(state["state"], "complete")
        self.assertEqual(self.service.character(character["id"])["gil"], 1300)
        potion = next(item for item in self.service.inventory(character["id"]) if item["item_id"] == 4112)
        self.assertEqual(potion["quantity"], 4)
        # Completing again must not pay twice.
        self.service.complete_quest(character["id"], quest["id"])
        self.assertEqual(self.service.character(character["id"])["gil"], 1300)
        potion = next(item for item in self.service.inventory(character["id"]) if item["item_id"] == 4112)
        self.assertEqual(potion["quantity"], 4)

    def test_admin_account(self):
        account_id = self.db.execute(
            "INSERT INTO accounts (username, password_hash, status, role, created_at, updated_at) "
            "VALUES ('root', ?, 'active', 'admin', 'now', 'now')",
            (hash_password("password123"),),
        )
        result = self.service.login("root", "password123")
        self.assertEqual(result.account["role"], "admin")
        self.service.create_news("patch-notes", "Patch notes", "Hello")
        post = self.service.news()[0]
        self.assertEqual(post["slug"], "patch-notes")
        suspended = self.service.set_account_status(account_id, "suspended")
        self.assertEqual(suspended["status"], "suspended")


if __name__ == "__main__":
    unittest.main()
