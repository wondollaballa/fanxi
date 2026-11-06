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

    def test_gearswap_settings_round_trip(self):
        result = self.register()
        account_id = int(result.account["id"])
        self.assertIsNone(self.service.gearswap_settings(account_id))
        config = {
            "engaged": "engaged.tp",
            "spellModes": {"enhancing": "duration", "enspells": "damage"},
            "spellCategoryOverrides": {"enspells": "midcast.Enspell"},
        }
        self.assertEqual(self.service.save_gearswap_settings(account_id, config), config)
        self.assertEqual(self.service.gearswap_settings(account_id), config)
        with self.assertRaises(ApiError) as ctx:
            self.service.save_gearswap_settings(account_id, ["not", "an", "object"])
        self.assertEqual(ctx.exception.status, 422)

    def test_gearswap_library_is_seeded_and_isolated_per_account(self):
        first = self.register("first")
        first_id = int(first.account["id"])
        self.service.create_character(first_id, {"name": "Firstone", "race": 1})
        seeded = self.service.gearswap_library(first_id, "WAR")
        self.assertIn("function get_sets()", seeded["source"])
        self.assertEqual(seeded["name"], "WAR.lua")

        custom = seeded["source"] + "\n-- first account only\n"
        saved = self.service.save_gearswap_library(first_id, "WAR", custom, "custom-war.lua")
        self.assertEqual(saved["source"], custom)
        self.assertEqual(saved["name"], "custom-war.lua")

        second = self.register("second")
        second_id = int(second.account["id"])
        self.service.create_character(second_id, {"name": "Secondone", "race": 1})
        other = self.service.gearswap_library(second_id, "WAR")
        self.assertNotEqual(other["source"], custom)
        self.assertIn("function get_sets()", other["source"])

        self.service.save_gearswap_library(second_id, "WAR", "-- second account\n", "second.lua")
        self.assertEqual(self.service.gearswap_library(first_id, "WAR")["source"], custom)

        reset = self.service.reset_gearswap_library(first_id, "WAR")
        self.assertEqual(reset["source"], seeded["source"])
        self.assertEqual(reset["name"], "WAR.lua")

    def test_new_account_copies_the_template_account_current_library(self):
        template = self.register("onedough")
        template_id = int(template.account["id"])
        self.service.create_character(template_id, {"name": "Onew", "race": 1})
        current = "-- Onedough's current RDM library\nfunction get_sets() end\n"
        self.service.save_gearswap_library(template_id, "RDM", current, "RDM.lua")

        late = self.register("late")
        late_id = int(late.account["id"])
        self.service.create_character(late_id, {"name": "Latecomer", "race": 1})
        copied = self.service.gearswap_library(late_id, "RDM")
        self.assertEqual(copied["source"], current)
        self.assertEqual(copied["name"], "RDM.lua")

        # The copy is independent: changing it does not touch the template account.
        self.service.save_gearswap_library(late_id, "RDM", "-- late only\n", "late-rdm.lua")
        self.assertEqual(self.service.gearswap_library(template_id, "RDM")["source"], current)

    def test_gearswap_library_rejects_bad_input(self):
        account_id = int(self.register().account["id"])
        for job, source in (("XYZ", "sets = {}"), ("WAR", "   "), ("WAR", 42)):
            with self.assertRaises(ApiError) as ctx:
                self.service.save_gearswap_library(account_id, job, source)
            self.assertEqual(ctx.exception.status, 422)
        with self.assertRaises(ApiError) as ctx:
            self.service.save_gearswap_library(account_id, "WAR", "x" * (512 * 1024 + 1))
        self.assertEqual(ctx.exception.status, 422)

    def test_reset_keeps_the_account_library_when_the_template_is_missing(self):
        account_id = int(self.register().account["id"])
        self.service.save_gearswap_library(account_id, "WAR", "-- keep me\n", "keep.lua")
        broken_config = replace(
            self.config, gearswap_dir=Path(self.tmp.name) / "no-gearswap-here")
        broken = FanxiService(broken_config, self.db)
        with self.assertRaises(ApiError) as ctx:
            broken.reset_gearswap_library(account_id, "WAR")
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(
            self.service.gearswap_library(account_id, "WAR")["source"], "-- keep me\n")

    def test_battle_catalogs_cover_weapon_skills_and_spells(self):
        skills = self.service.battle_weapon_skills()
        self.assertTrue(any(row["name"] == "Savage Blade" for row in skills))
        self.assertTrue(all(row["id"] and row["name"] for row in skills))
        spells = self.service.battle_spells()
        self.assertTrue(any(row["name"] == "Thunder V" for row in spells))

    def test_battle_mob_catalog_describes_selected_spawn(self):
        row = self.db.one(
            "SELECT s.zone, COALESCE(s.name, t.name) AS name "
            "FROM monster_spawns s JOIN monster_templates t ON t.id = s.template_id "
            "WHERE t.skill_list_id > 0 AND s.name IS NOT NULL LIMIT 1")
        self.assertIsNotNone(row)
        catalog = self.service.battle_mob_moves([row["name"]], int(row["zone"]))
        self.assertGreater(len(catalog["moves"]), 0)
        self.assertEqual(catalog["unmatched"], [])
        self.assertTrue(all(move["description"] for move in catalog["moves"]))

    def test_battle_team_profile_round_trip(self):
        result = self.register()
        account_id = int(result.account["id"])
        character = self.service.create_character(account_id, {"name": "Testerone", "race": 1})
        profile = {"name": "Team rules", "buffs": {"rows": [{"spell": "Haste", "target": "party"}]}}
        saved = self.service.save_battle_profile(account_id, int(character["id"]), profile)
        self.assertGreater(saved["updated"], 0)
        team = self.service.battle_team_profiles(account_id)
        self.assertEqual(len(team), 1)
        self.assertEqual(team[0]["name"], "Testerone")
        self.assertEqual(team[0]["profile"]["name"], "Team rules")
        self.assertEqual(team[0]["updated"], saved["updated"])
        # Without a game gateway there is no live roster; the hub must be able to tell the
        # difference and keep showing the team instead of treating everyone as offline.
        self.assertFalse(team[0]["online"])
        self.assertFalse(team[0]["online_known"])

    def test_battle_engine_publish_preserves_profile(self):
        result = self.register()
        account_id = int(result.account["id"])
        character = self.service.create_character(account_id, {"name": "Testertwo", "race": 1})
        profile = {"name": "Keep me", "buffs": {"rows": [{"spell": "Haste"}]}}
        saved = self.service.save_battle_profile(account_id, int(character["id"]), profile)
        state = self.service.save_battle_engine(account_id, int(character["id"]), {
            "running": True, "ready": True, "run_id": "run-123",
        })
        self.assertTrue(state["engine"]["running"])
        self.assertTrue(state["engine"]["ready"])
        self.assertEqual(state["engine"]["run_id"], "run-123")
        team = self.service.battle_team_profiles(account_id)
        self.assertEqual(team[0]["profile"]["name"], "Keep me")
        self.assertEqual(team[0]["profile"]["buffs"]["rows"][0]["spell"], "Haste")
        self.assertTrue(team[0]["profile"]["engine"]["ready"])
        self.assertEqual(team[0]["profile"]["engine"]["run_id"], "run-123")
        # A state publish must not make the client re-apply its own server copy over an
        # unsaved edit; only an actual profile save bumps the updated stamp.
        self.assertEqual(team[0]["updated"], saved["updated"])

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

    def test_armory_search_matches_full_and_abbreviated_item_names(self):
        account = self.register().account
        character = self.service.create_character(
            account["id"], {"name": "Aliases", "race": 1})
        character_id = character["id"]
        cases = {
            "Mousai Crackows +1": 25969,
            "Mou. Crackows +1": 25969,
            "Mousai Seraweels +1": 25902,
            "Mou. Seraweels +1": 25902,
            "Mousai Manteel +1": 26538,
            "Mou. Manteel +1": 26538,
            "Mou. Gages +1": 25989,
            "Mou. Turban +1": 25562,
            "Marduk's Crackows +1": 28211,
            "Abyss Burgeonet +1": 15252,
            "Academic's Bracers +1": 27984,
            "Pahluwan Crackows": 15695,
            "Inyanga Dastanas +1": 25807,
            "Ayanmo Cosciales +1": 25870,
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                rows = self.service.search_items(character_id, query)
                self.assertEqual([row["item_id"] for row in rows], [expected])

    def test_item_store_search_ignores_apostrophes_and_filters_the_shelf(self):
        account = self.register().account
        character = self.service.create_character(
            account["id"], {"name": "General", "race": 1})
        character_id = character["id"]
        for query in ("nobles bed", "noble's bed", "Noble's Bed"):
            with self.subTest(query=query):
                rows = self.service.search_items(
                    character_id, query, scope="items")
                self.assertEqual(rows[0]["name"], "Noble's Bed")
                self.assertEqual(rows[0]["category"], "Furnishings")

        ninja = self.service.search_items(
            character_id, "", scope="items", category="Ninja Tools", limit=100)
        self.assertGreaterEqual(len(ninja), 40)
        self.assertTrue(all(row["category"] == "Ninja Tools" for row in ninja))
        # The category parameter is exact: a query's text cannot smuggle another
        # shelf into the result.
        self.assertEqual(
            self.service.search_items(
                character_id, "", scope="items", category="No Such Shelf"),
            [],
        )
        categories = [row["name"] for row in self.service.item_categories()]
        self.assertLess(categories.index("Ninja Tools"), categories.index("Materials"))
        self.assertLess(categories.index("Jug Pets"), categories.index("Consumables"))

        for query, shelf in (("jug pets", "Jug Pets"), ("ninja tools", "Ninja Tools")):
            with self.subTest(query=query):
                rows = self.service.search_items(
                    character_id, query, scope="items", limit=100)
                self.assertTrue(rows)
                self.assertTrue(all(row["category"] == shelf for row in rows))

    def test_spalirisos_has_its_item_level_skill_and_stat_block(self):
        item = self.service.item(21730)
        self.assertIsNotNone(item)
        weapon = self.db.one(
            "SELECT ilvl_skill FROM item_weapon WHERE item_id = 21730")
        self.assertEqual(int(weapon["ilvl_skill"]), 277)
        mods = self.service.item_mods(21730)
        self.assertEqual(int(mods.get(8, 0)), 35)    # STR
        self.assertEqual(int(mods.get(9, 0)), 35)    # DEX
        self.assertEqual(int(mods.get(14, 0)), 35)   # CHR
        self.assertEqual(int(mods.get(25, 0)), 35)   # Accuracy
        self.assertEqual(int(mods.get(30, 0)), 35)   # Magic Accuracy
        self.assertEqual(int(mods.get(165, 0)), 1500)  # Critical hit rate +15%

    def test_bst_offhand_axes_carry_their_ilvl_skill_and_stats(self):
        for item_id, mods_expected in (
            (21723, {8: 15, 9: 15, 23: 30, 25: 40, 30: 40, 165: 1000, 840: 5}),
            (21724, {9: 15, 14: 15, 23: 30, 25: 40, 30: 40, 73: 10, 840: 5}),
        ):
            weapon = self.db.one(
                "SELECT ilvl_skill FROM item_weapon WHERE item_id = ?", (item_id,))
            self.assertEqual(int(weapon["ilvl_skill"]), 255)
            mods = self.service.item_mods(item_id)
            for mod_id, value in mods_expected.items():
                self.assertEqual(int(mods.get(mod_id, 0)), value)

    def test_one_handed_axes_and_katanas_can_fill_either_hand(self):
        """Farsha and the other 1H axe/katana rows must carry both weapon slot bits.

        Migration 0149 repairs the hand-curated 119 III rows; the launcher's Sub
        picker and the server's equip check both filter on ``slot_mask``.
        """
        rows = self.db.all(
            "SELECT item_id, name, slot_mask FROM items "
            "WHERE skill IN (5, 9) AND (slot_mask & 2) = 0")
        self.assertEqual([(row["item_id"], row["name"]) for row in rows], [])
        farsha = self.service.item(21752)
        self.assertIsNotNone(farsha)
        self.assertEqual(int(farsha["slot_mask"]) & 3, 3)
        self.assertEqual(int(farsha["jobs"]) & (1 << 8), 1 << 8)  # BST
        self.assertEqual(int(farsha["level"]), 99)

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

    def test_level_99_has_no_next_experience_requirement(self):
        from fanxi_server.service import exp_for_level
        self.assertGreater(exp_for_level(98), 0)
        self.assertEqual(exp_for_level(99), 0)

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

    def test_level_99_awards_exemplar_points_not_experience(self):
        account = self.register().account
        character = self.service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        self.db.execute(
            "UPDATE characters SET main_level = 99, exp = 123 WHERE id = ?",
            (int(character["id"]),))
        self.db.execute(
            "INSERT OR REPLACE INTO character_jobs (character_id, job, level, master_level) "
            "VALUES (?, 1, 99, 0)", (int(character["id"]),))
        updated = self.service.award_exp_gil(character["id"], 250, 5, exemplar=True)
        self.assertEqual(updated["exemplar_gained"], 250)
        self.assertEqual(updated["exemplar_points"], 250)
        self.assertEqual(updated["master_levels_gained"], 0)
        self.assertEqual(updated["exp"], 123)        # the EXP bar is done at 99
        self.assertEqual(updated["gil"], 1005)

        # 30,000 points buys a Master Level; the remainder stays on the bar.
        self.db.execute(
            "UPDATE characters SET exemplar_points = 29990 WHERE id = ?",
            (int(character["id"]),))
        updated = self.service.award_exp_gil(character["id"], 20, 0)
        self.assertEqual(updated["exemplar_points"], 10)
        self.assertEqual(updated["master_levels_gained"], 1)
        self.assertEqual(updated["master_level"], 1)
        row = self.db.one(
            "SELECT master_level FROM character_jobs WHERE character_id = ? AND job = 1",
            (int(character["id"]),))
        self.assertEqual(int(row["master_level"]), 1)

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
