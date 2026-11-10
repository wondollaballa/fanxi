"""Chemist (CHM): bag, Toss/Mix, Catalyst/Amplify/Volatile and Chemistry.

These drive the real job-ability packet and the real cast resolver, so the level gates,
the Alchemy scaling and the stacking rules are tested where the game uses them.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server import service as service_module
from fanxi_server.game import base_stats, chemist, effects, modifiers as mod, packets, skills
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession


class ChemistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("chm", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Chemist", "race": 1, "main_job": 23})
        self.world = World(self.config, self.service, None)
        # Toss rolls physical hit chance.  Keep the tests deterministic: a zero roll
        # always lands unless the test deliberately patches the chance to zero.
        self.world.rng = mock.Mock()
        self.world.rng.random.return_value = 0.0
        self.session = self.make_session(self.character, "Chemist")
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.char.update({
            "main_job": 23, "main_level": 99,
            "sub_job": 3, "sub_level": 99,
            "hp": 2000, "hp_current": 2000,
            "mp": 800, "mp_current": 800,
            "tp": 0,
        })
        self.db.execute(
            "INSERT OR REPLACE INTO character_jobs "
            "(character_id, job, level, master_level) VALUES (?, ?, 99, 0)",
            (int(self.character["id"]), 23))
        self.set_alchemy(55)
        self.session.queue.clear()

    def make_session(self, character, name: str, *, targid: int = 0):
        session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(character["id"]), name))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = 100
        session.targid = targid
        session.pos = list(self.world.zones.position(100))
        session.load_zone_entities()
        session.after_zone_in()
        session.zone_loaded = True
        session.queue.clear()
        return session

    def party_with(self, name: str = "Ally") -> ZoneSession:
        account = self.service.register(name.casefold(), "password123").account
        row = self.service.create_character(account["id"], {"name": name, "race": 1})
        other = self.make_session(row, name, targid=0x401)
        other.pos = list(self.session.pos)
        other.char.update({
            "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0,
            "hp": 2000, "hp_current": 1000, "mp": 500, "mp_current": 500,
        })
        self.world.sessions[("127.0.0.1", 4321)] = other
        party = self.world.party_of(int(self.session.char["char_id"]))
        if party is None:
            party = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(party, other))
        other.queue.clear()
        return other

    def enter(self, zone: int = 100) -> None:
        self.session.zone = int(zone)
        self.session.pos = list(self.world.zones.position(int(zone)))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def mob(self):
        mob = next(entity for entity in self.session.entities
                   if entity.kind == "mob" and entity.alive)
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        return mob

    def use(self, ability_id: int, targid: int = 0, *, clear_recasts: bool = False) -> None:
        self.session.queue.clear()
        if clear_recasts:
            self.session.ability_recasts.clear()
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, int(ability_id))
        self.session.job_ability(bytes(packet), int(targid))

    def give_bag(self, item_id: int, quantity: int, slot: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO char_chemist_bag "
                "(character_id, slot, item_id, quantity) VALUES (?, ?, ?, ?)",
                (int(self.character["id"]), int(slot), int(item_id), int(quantity)))

    def bag_quantity(self, item_id: int) -> int:
        row = next((row for row in chemist.bag(self.service, int(self.character["id"]))
                    if int(row.item_id) == int(item_id)), None)
        return int(row.quantity) if row is not None else 0

    def set_alchemy(self, value: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO char_craft (character_id, skill_id, value) "
            "VALUES (?, 55, ?)", (int(self.character["id"]), int(value)))

    def test_creation_has_job_23_and_kit(self):
        rows = self.service.jobs_for_character(int(self.character["id"]))
        self.assertEqual(rows.get(23), (99, 0))
        abilities = [row["name"] for row in self.service.job_abilities(23, 99)]
        self.assertEqual(abilities, [
            "Toss", "Mix", "Catalyst", "Amplify", "Volatile Synthesis"])

    def test_the_hud_report_carries_the_bag_stances_and_recasts(self):
        """GET /characters/<id>/chemist is the Chemist HUD's data source."""
        self.give_bag(4112, 5, 1)
        self.give_bag(30000, 3, 2)
        self.session.chemist_selected_item = 30000
        now = time.time()
        self.session._chemist_catalyst_until = now + 30
        self.session.ability_recasts[chemist.RECAST_IDS[chemist.CATALYST]] = now + 45
        report = self.session.chemist_report()
        self.assertEqual(report["main_job"], 23)
        self.assertEqual(report["capacity"], 20)
        self.assertEqual(report["used"], 2)
        self.assertEqual(report["selected"], 30000)
        rows = {int(row["item_id"]): row for row in report["bag"]}
        self.assertTrue(rows[30000]["selected"])
        self.assertEqual(rows[4112]["quantity"], 5)
        self.assertEqual(rows[4112]["kind"], "heal")
        self.assertAlmostEqual(report["stances"]["catalyst"], 30, delta=2)
        self.assertAlmostEqual(report["recasts"]["catalyst"], 45, delta=2)
        self.assertEqual(report["alchemy"], 55)

    def test_the_chm_command_fires_catalyst_through_the_ability_gate(self):
        self.enter()
        self.session.ability_recasts.clear()
        self.session.chemist_command(["catalyst"])
        self.assertGreater(self.session._chemist_catalyst_until, time.time())
        self.assertGreater(
            self.session.ability_recasts.get(chemist.RECAST_IDS[chemist.CATALYST], 0),
            time.time())

    def test_the_chm_use_command_selects_and_tosses_a_hostile_item(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        self.session.target_targid = mob.targid
        self.session.chemist_command(["use", "30000"])
        self.assertEqual(self.session.chemist_selected_item, 30000)
        self.assertIsNotNone(mob.effect_state.get(chemist.AQUA_REGIA))

    def test_job_23_stats_skills_and_packet_slot(self):
        stats = base_stats.base_stats(1, 23, 99, 0, 0)
        self.assertGreater(int(stats["dex"]), 0)
        self.assertGreater(int(skills.cap_for(27, 23, 99) or 0), 0)
        self.session.char.setdefault("jobs", {})[23] = (99, 0)
        body = self.session.dancer()
        self.assertEqual(int(body[0x44 + 23]), 99)
        self.assertEqual(int(body[0x68 + 23]), 0)

    def test_mix_uses_the_entity_synthesis_pose_not_a_spell_animation(self):
        # 0x028's animation field is a spell animation id (44 is Protect); the
        # synth pose rides the entity animation, not the ability row.
        self.assertEqual(int(self.service.job_ability(chemist.MIX)["animation"]), 0)
        self.assertEqual(chemist.CRAFT_ANIMATION, 44)

    def test_all_recipes_are_learned(self):
        learned = chemist.learned_recipes(self.service, int(self.character["id"]))
        self.assertEqual(len(learned), 8)
        self.assertEqual({int(row["item_id"]) for row in learned},
                         set(range(30000, 30008)))

    def test_toolkit_pays_a_recipe_and_is_consumed(self):
        self.give_bag(30000, 0, 2)
        self.service.add_item(int(self.character["id"]), chemist.TOOLKIT_ITEM_ID, 99)
        result = chemist.craft(self.service, int(self.character["id"]), 30000)
        self.assertTrue(result["ok"])
        self.assertTrue(result["toolkit_used"])
        self.assertEqual(self.bag_quantity(30000), 3)
        self.assertEqual(chemist.toolkit_count(
            self.service, int(self.character["id"])), 98)

    def test_old_custom_toolkit_stack_still_pays(self):
        self.give_bag(30000, 0, 2)
        self.service.add_item(int(self.character["id"]), 30008, 1)
        result = chemist.craft(self.service, int(self.character["id"]), 30000)
        self.assertTrue(result["ok"])
        self.assertTrue(result["toolkit_used"])
        self.assertEqual(self.bag_quantity(30000), 3)
        self.assertEqual(chemist.toolkit_count(
            self.service, int(self.character["id"])), 0)

    def test_craft_creates_the_bag_slot(self):
        result = chemist.ensure_bag_slot(self.service, self.session.char, 30000)
        self.assertTrue(result["ok"])
        self.assertEqual(self.bag_quantity(30000), 0)
        self.assertEqual(self.session.chemist_report()["toolkits"], 0)

    def test_brewer_shield_equips_cleanly(self):
        self.service.add_item(int(self.character["id"]), 26457, 1)
        row = next(row for row in self.service.inventory(int(self.character["id"]))
                   if int(row["item_id"]) == 26457 and int(row["container"]) == 0)
        packet = bytes([0, 0, 0, 0, int(row["slot"]), 1, 0])
        self.session.equip(packet)
        self.assertEqual(self.session.equipped.get(1), (0, int(row["slot"]), 26457))

    def test_chm_gearswap_library_and_sch_test_gear(self):
        self.assertIn("CHM", service_module.GEARSWAP_JOBS)
        library = self.service.gearswap_library(int(self.account["id"]), "CHM")
        self.assertIn("sets.JA.Mix", library["source"])
        self.assertIn("Br. Escutcheon", library["source"])
        kaykaus = self.service.item(25618)  # Kaykaus Mitra +1, SCH JSE
        self.assertTrue(int(kaykaus["jobs"]) & (1 << 22))

    def test_wizard_rod_and_shield_can_be_worn_together(self):
        self.assertGreaterEqual(
            int(self.service.item(21991)["jobs"]) & (1 << 22), 1)
        self.assertGreater(skills.cap_for(11, 23, 99) or 0, 0)
        self.service.add_item(int(self.character["id"]), 21991, 1)
        rod = next(row for row in self.service.inventory(int(self.character["id"]))
                   if int(row["item_id"]) == 21991 and int(row["container"]) == 0)
        self.session.equip(bytes([0, 0, 0, 0, int(rod["slot"]), 0, 0]))
        self.assertEqual(self.session.equipped.get(0), (0, int(rod["slot"]), 21991))
        self.service.add_item(int(self.character["id"]), 26457, 1)
        shield = next(row for row in self.service.inventory(int(self.character["id"]))
                      if int(row["item_id"]) == 26457 and int(row["container"]) == 0)
        self.session.equip(bytes([0, 0, 0, 0, int(shield["slot"]), 1, 0]))
        self.assertEqual(self.session.equipped.get(1), (0, int(shield["slot"]), 26457))

    def test_carried_shield_keeps_synthesis_fast(self):
        self.service.add_item(int(self.character["id"]), 26457, 1)
        self.assertEqual(chemist.craft_cast_ms(
            self.service, int(self.character["id"]), 30000), 2000)

    def test_brewer_shield_grants_all_craft_skills(self):
        self.service.add_item(int(self.character["id"]), 26457, 1)
        row = next(row for row in self.service.inventory(int(self.character["id"]))
                   if int(row["item_id"]) == 26457 and int(row["container"]) == 0)
        self.db.execute(
            "INSERT OR REPLACE INTO char_equip "
            "(character_id, kind, container, slot, item_id) VALUES (?, 1, 0, ?, 26457)",
            (int(self.character["id"]), int(row["slot"])))
        crafts = self.service.crafts_for_character(int(self.character["id"]))
        self.assertTrue(all(int(row["value"]) == 100 for row in crafts))
        self.assertEqual(chemist.alchemy_skill(
            self.service, int(self.character["id"])), 100)
        self.assertEqual(
            chemist.craft_cast_ms(self.service, int(self.character["id"]), 30000), 2000)

    def test_chm_craft_holds_the_synth_pose(self):
        self.service.add_item(int(self.character["id"]), chemist.TOOLKIT_ITEM_ID, 1)
        self.session.queue.clear()
        self.session.chemist_command(["craft", "Aqua Regia"])
        self.assertIsNotNone(self.session.casting)
        self.assertGreater(self.session.synth_until, time.time())
        self.assertEqual(self.session.own_animation(), chemist.CRAFT_ANIMATION)
        self.session.casting["finish"] = time.time() - 1
        self.session.resolve_casting(time.time())
        self.assertEqual(self.session.synth_until, 0.0)
        self.assertNotEqual(self.session.own_animation(), chemist.CRAFT_ANIMATION)

    def test_chm_craft_starts_the_mix_synthesis_and_uses_a_toolkit(self):
        self.service.add_item(int(self.character["id"]), chemist.TOOLKIT_ITEM_ID, 1)
        self.session.queue.clear()
        self.session.chemist_command(["craft", "Aqua Regia"])
        self.assertIsNotNone(self.session.casting)
        self.assertEqual(self.session.casting["chemist"], 30000)
        self.session.casting["finish"] = time.time() - 1
        self.session.resolve_casting(time.time())
        self.assertEqual(self.bag_quantity(30000), 3)
        self.assertEqual(chemist.toolkit_count(
            self.service, int(self.character["id"])), 0)

    def test_recipes_reach_the_hud_report(self):
        report = self.session.chemist_report()
        self.assertEqual(report["toolkits"], 0)
        self.assertEqual(len(report["recipes"]), 8)
        self.assertTrue(all(row["craftable"] is False for row in report["recipes"]))

    def test_command_data_carries_the_custom_ability_ids(self):
        self.session.char.setdefault("jobs", {})[23] = (99, 0)
        bits = bytes(self.session.char_abilities()[4:])
        for ability_id in (chemist.TOSS, chemist.MIX, chemist.CATALYST,
                           chemist.AMPLIFY, chemist.VOLATILE):
            self.assertTrue(bits[64 + (ability_id >> 3)] & (1 << (ability_id & 7)))

    def test_capacity_bands(self):
        self.assertEqual(chemist.capacity_for_level(1), 5)
        self.assertEqual(chemist.capacity_for_level(25), 7)
        self.assertEqual(chemist.capacity_for_level(50), 10)
        self.assertEqual(chemist.capacity_for_level(75), 15)
        self.assertEqual(chemist.capacity_for_level(99), 20)

    def test_load_moves_item_and_caps_at_bag_stack(self):
        self.service.add_item(int(self.character["id"]), 4112, 150)
        before = chemist.inventory_quantity(self.service, int(self.character["id"]), 4112)
        result = chemist.load_item(self.service, self.session.char, 4112, 150)
        self.assertTrue(result["ok"])
        self.assertEqual(int(result["quantity"]), 99)
        self.assertEqual(self.bag_quantity(4112), 99)
        self.assertEqual(chemist.inventory_quantity(
            self.service, int(self.character["id"]), 4112), before - 99)

    def test_item_values_scale_to_cap(self):
        spec = chemist.item_spec(self.service, 30000)
        self.assertEqual(chemist.item_values(spec, 0)["potency"], 10)
        self.assertEqual(chemist.item_values(spec, 50)["potency"], 12)
        self.assertEqual(chemist.item_values(spec, 100)["potency"], 15)
        self.assertEqual(chemist.item_values(spec, 200)["potency"], 15)
        self.assertEqual(chemist.item_values(spec, 55)["duration"], 60.0)
        vitriol = chemist.item_spec(self.service, 30003)
        values = chemist.item_values(vitriol, 100)
        self.assertEqual(values["tick"], 15)
        self.assertEqual(values["duration"], 30.0)
        self.assertEqual(values["tick_interval"], 3.0)

    def test_chemistry_potency_gear_pushes_past_the_native_cap(self):
        spec = chemist.item_spec(self.service, 30000)
        self.assertEqual(
            chemist.item_values(spec, 0, potency_bonus=100)["potency"], 11)
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        with mock.patch.object(
                self.service, "equipped_mods",
                return_value={mod.CHEMISTRY_POTENCY: 100}):
            self.use(chemist.TOSS, mob.targid)
        state = mob.effect_state.get(chemist.AQUA_REGIA)
        self.assertIsNotNone(state)
        # Alchemy 55 gives 12; +100 hundredths (1 point) gives 13.
        self.assertEqual(int(state["potency"]), 13)

    def test_shield_reduces_synthesis_cast_time(self):
        normal = chemist.craft_cast_ms(self.service, int(self.character["id"]), 30000)
        self.assertEqual(normal, 12000)
        with mock.patch.object(
                self.service, "equipped_mods",
                return_value={mod.CHEMISTRY_CAST: -10000}):
            self.assertEqual(
                chemist.craft_cast_ms(self.service, int(self.character["id"]), 30000),
                2000)

    def test_hi_potion_requires_alchemy(self):
        self.set_alchemy(0)
        self.service.add_item(int(self.character["id"]), 4116, 1)
        result = chemist.load_item(self.service, self.session.char, 4116, 1)
        self.assertFalse(result["ok"])
        self.assertIn("Alchemy 20", result["message"])
        self.set_alchemy(20)
        result = chemist.load_item(self.service, self.session.char, 4116, 1)
        self.assertTrue(result["ok"])

    def test_toss_applies_scaled_potency(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        self.use(chemist.TOSS, mob.targid)
        state = mob.effect_state.get(chemist.AQUA_REGIA)
        self.assertIsNotNone(state)
        # Alchemy 55: 10 + (15 - 10) * 55 // 100 = 12.
        self.assertEqual(int(state["potency"]), 12)
        self.assertEqual(self.bag_quantity(30000), 2)

    def test_aqua_regia_stacks_with_dia_and_armor_break(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        now = time.time()
        mob.effect_state[effects.DIA] = {
            "until": now + 60, "potency": 10, "power": 0}
        mob.effect_state[effects.DEFENSE_DOWN] = {
            "until": now + 60, "potency": 15, "power": 0}
        before = int(self.world.debuffed_monster(mob).defense)
        self.use(chemist.TOSS, mob.targid)
        self.assertIn(effects.DIA, mob.effect_state)
        self.assertIn(effects.DEFENSE_DOWN, mob.effect_state)
        self.assertIn(chemist.AQUA_REGIA, mob.effect_state)
        after = int(self.world.debuffed_monster(mob).defense)
        self.assertLess(after, before)

    def test_toss_is_effectively_certain_and_resistance_shortens_it(self):
        self.enter()
        mob = self.mob()
        self.assertEqual(chemist.toss_accuracy(self.session, mob), 1.0)
        scale = chemist.toss_resistance(self.session, mob)
        self.assertGreaterEqual(scale, 0.5)
        self.assertLessEqual(scale, 1.0)

    def test_toss_miss_consumes_a_charge(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        with mock.patch.object(chemist, "toss_accuracy", return_value=0.0):
            self.use(chemist.TOSS, mob.targid)
        self.assertIsNone(mob.effect_state.get(chemist.AQUA_REGIA))
        self.assertEqual(self.bag_quantity(30000), 2)

    def test_catalyst_makes_toss_hit_nearby_mobs_once(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        others = [entity for entity in self.session.entities
                  if entity.kind == "mob" and entity.alive and entity is not mob]
        self.assertTrue(others)
        other = others[0]
        other.x, other.y, other.z = mob.x + 1.0, mob.y, mob.z
        self.use(chemist.CATALYST, clear_recasts=True)
        self.assertGreater(self.session._chemist_catalyst_until, time.time())
        self.use(chemist.TOSS, mob.targid)
        self.assertIsNotNone(mob.effect_state.get(chemist.AQUA_REGIA))
        self.assertIsNotNone(other.effect_state.get(chemist.AQUA_REGIA))
        self.assertEqual(self.bag_quantity(30000), 2)
        self.assertEqual(self.session._chemist_catalyst_until, 0.0)

    def test_catalyst_level_gate(self):
        self.session.char["main_level"] = 34
        self.use(chemist.CATALYST, clear_recasts=True)
        self.assertEqual(self.session._chemist_catalyst_until, 0.0)
        self.session.char["main_level"] = 35
        self.use(chemist.CATALYST, clear_recasts=True)
        self.assertGreater(self.session._chemist_catalyst_until, time.time())
        self.assertGreater(self.session.ability_recasts[202], time.time())

    def test_volatile_forces_max_potency_and_auto_hit(self):
        self.enter()
        self.set_alchemy(100)
        self.give_bag(30000, 3, 2)
        mob = self.mob()
        self.use(chemist.VOLATILE, clear_recasts=True)
        with mock.patch.object(chemist, "toss_accuracy", return_value=0.0):
            self.use(chemist.TOSS, mob.targid)
        state = mob.effect_state.get(chemist.AQUA_REGIA)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["potency"]), 15)
        self.assertEqual(self.session._chemist_volatile_until, 0.0)

    def test_toss_on_self_uses_a_potion(self):
        self.session.char["hp_current"] = 1000
        self.give_bag(4112, 10, 1)
        self.use(chemist.TOSS, 0x400)
        self.assertEqual(int(self.session.char["hp_current"]), 1105)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_toss_on_a_party_member_uses_a_potion(self):
        other = self.party_with()
        other.char["hp_current"] = 1000
        other.pos = list(self.session.pos)
        self.give_bag(4112, 10, 1)
        self.use(chemist.TOSS, other.targid)
        self.assertEqual(int(other.char["hp_current"]), 1105)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_toss_on_a_trust_uses_a_potion(self):
        self.enter()
        trust = self.world.spawn_trust(self.session, self.service.trust(981))
        self.assertIsNotNone(trust)
        trust.hp = 100
        self.give_bag(4112, 10, 1)
        self.use(chemist.TOSS, trust.targid)
        self.assertGreater(int(trust.hp), 100)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_catalyst_toss_heals_the_whole_alliance(self):
        first = self.party_with("Ally")
        first.char["hp_current"] = 1000
        first.pos = list(self.session.pos)
        account = self.service.register("otherally", "password123").account
        row = self.service.create_character(account["id"], {"name": "Otherally", "race": 1})
        second = self.make_session(row, "Otherally", targid=0x402)
        second.char.update({"hp": 2000, "hp_current": 1000, "mp": 500, "mp_current": 500})
        second.pos = list(self.session.pos)
        self.world.sessions[("127.0.0.1", 4322)] = second
        second_party = self.world.create_party(second)
        self.assertIsNotNone(self.world.form_alliance(
            self.world.party_of(int(self.session.char["char_id"])), second_party))
        self.session.char["hp_current"] = 1000
        self.give_bag(4112, 10, 1)
        self.session._chemist_catalyst_until = time.time() + 60
        self.use(chemist.TOSS, 0x400)
        self.assertGreater(int(self.session.char["hp_current"]), 1000)
        self.assertGreater(int(first.char["hp_current"]), 1000)
        self.assertGreater(int(second.char["hp_current"]), 1000)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_toss_refuses_a_non_party_player(self):
        account = self.service.register("stranger", "password123").account
        row = self.service.create_character(account["id"], {"name": "Stranger", "race": 1})
        other = self.make_session(row, "Stranger", targid=0x401)
        other.char["hp_current"] = 1000
        other.pos = list(self.session.pos)
        self.world.sessions[("127.0.0.1", 4321)] = other
        self.give_bag(4112, 10, 1)
        self.use(chemist.TOSS, other.targid)
        self.assertEqual(int(other.char["hp_current"]), 1000)
        self.assertEqual(self.bag_quantity(4112), 10)

    def test_mix_heals_and_consumes_one_charge(self):
        self.session.char["hp_current"] = 1000
        self.give_bag(4112, 10, 1)
        self.use(chemist.MIX, clear_recasts=True)
        # Potion: 50 + 1 per Alchemy point.  Alchemy 55 -> 105.
        self.assertEqual(int(self.session.char["hp_current"]), 1105)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_mix_removes_a_status(self):
        self.enter()
        self.session.add_effect(effects.SILENCE, duration=60)
        self.assertTrue(self.session.has_effect(effects.SILENCE))
        self.give_bag(4151, 3, 1)
        self.use(chemist.MIX, clear_recasts=True)
        self.assertFalse(self.session.has_effect(effects.SILENCE))
        self.assertEqual(self.bag_quantity(4151), 2)

    def test_catalyst_mix_heals_the_party_for_one_charge(self):
        self.enter()
        other = self.party_with()
        self.session.char["hp_current"] = 1000
        other.char["hp_current"] = 1000
        other.pos = list(self.session.pos)
        self.give_bag(4112, 10, 1)
        self.use(chemist.CATALYST, clear_recasts=True)
        self.use(chemist.MIX, clear_recasts=True)
        self.assertGreater(int(self.session.char["hp_current"]), 1000)
        self.assertGreater(int(other.char["hp_current"]), 1000)
        self.assertEqual(self.bag_quantity(4112), 9)

    def test_mix_level_gate(self):
        self.session.char["main_level"] = 14
        self.give_bag(4112, 10, 1)
        self.session.char["hp_current"] = 1000
        self.use(chemist.MIX, clear_recasts=True)
        self.assertEqual(int(self.session.char["hp_current"]), 1000)
        self.assertEqual(self.bag_quantity(4112), 10)

    def test_synthesis_consumes_reagents_and_refills_to_yield(self):
        self.enter()
        self.give_bag(30000, 0, 2)
        self.service.add_item(int(self.character["id"]), 4096, 2)
        self.service.add_item(int(self.character["id"]), 4101, 1)
        self.session._chemist_start_synthesis(30000, time.time())
        self.assertIsNotNone(self.session.casting)
        self.session.casting["finish"] = time.time() - 1
        self.session.resolve_casting(time.time())
        self.assertEqual(self.bag_quantity(30000), 3)
        self.assertEqual(chemist.inventory_quantity(
            self.service, int(self.character["id"]), 4096), 0)
        self.assertEqual(chemist.inventory_quantity(
            self.service, int(self.character["id"]), 4101), 0)

    def test_synthesis_refuses_missing_reagents(self):
        self.enter()
        self.give_bag(30000, 0, 2)
        self.session._chemist_start_synthesis(30000, time.time())
        self.assertIsNone(self.session.casting)

    def test_synthesis_alchemy_gate(self):
        self.enter()
        self.set_alchemy(0)
        self.give_bag(30000, 0, 2)
        self.service.add_item(int(self.character["id"]), 4096, 2)
        self.service.add_item(int(self.character["id"]), 4101, 1)
        self.session._chemist_start_synthesis(30000, time.time())
        self.assertIsNone(self.session.casting)

    def test_ko_shows_the_body_and_auto_homes_after_an_hour(self):
        now = time.time()
        self.session.char["hp_current"] = 0
        self.session.hit_zero_hp(now)
        self.assertEqual(self.session.dead_until, float("inf"))
        self.assertGreater(self.session.ko_home_at, now + 3599)
        self.assertEqual(self.session.own_animation(), 3)
        # Let the one-hour deadline pass; the tick returns the body to the Home Point.
        self.session.ko_home_at = now - 1
        self.session.tick(time.time())
        self.assertEqual(self.session.dead_until, 0.0)
        self.assertGreater(int(self.session.char["hp_current"]), 0)

    def test_sludge_bomb_lowers_evasion(self):
        self.enter()
        self.give_bag(30001, 3, 2)
        mob = self.mob()
        before = int(self.world.debuffed_monster(mob).evasion)
        self.use(chemist.TOSS, mob.targid)
        after = int(self.world.debuffed_monster(mob).evasion)
        self.assertLess(after, before)

    def test_vitriol_ticks_separately_from_poison(self):
        self.enter()
        self.give_bag(30003, 3, 2)
        mob = self.mob()
        mob.hp = mob.hp_max = 5000
        self.use(chemist.TOSS, mob.targid)
        state = mob.effect_state.get(chemist.VITRIOL)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["tick"]), 12)
        self.assertEqual(float(state["tick_interval"]), 3.0)
        self.assertNotIn(effects.POISON, mob.effect_state)
        before = int(mob.hp)
        self.world.tick_mob_effects(mob, [self.session], time.time() + 3.1)
        self.assertEqual(int(mob.hp), before - 12)

    def test_aether_spore_affects_both_magic_stats(self):
        self.enter()
        self.give_bag(30002, 3, 2)
        mob = self.mob()
        self.use(chemist.TOSS, mob.targid)
        state = mob.effect_state.get(chemist.AETHER_SPORE)
        self.assertIsNotNone(state)
        mods = self.world.monster_debuff_mods(mob)
        self.assertLess(int(mods.get(mod.MDEF, 0)), 0)
        self.assertLess(int(mods.get(mod.MEVA, 0)), 0)

    def test_non_chemist_cannot_use_toss(self):
        self.enter()
        self.give_bag(30000, 3, 2)
        self.session.char["main_job"] = 1
        mob = self.mob()
        self.use(chemist.TOSS, mob.targid)
        self.assertIsNone(mob.effect_state.get(chemist.AQUA_REGIA))
        self.assertEqual(self.bag_quantity(30000), 3)

    def test_amplify_upgrades_protect_and_keeps_lower_cost(self):
        protect3 = self.service.spell_by_name("Protect III")
        protect4 = self.service.spell_by_name("Protect IV")
        self.assertIsNotNone(protect3)
        self.assertIsNotNone(protect4)
        self.session.add_effect(effects.ACCESSION, duration=60)
        self.session._chemist_amplify_until = time.time() + 60
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0,
                         packets.ACTION_CAST_MAGIC, int(protect3["id"]))
        self.session.cast_magic(bytes(packet), 0)
        self.assertIsNotNone(self.session.casting)
        self.assertEqual(self.session.casting["spell"]["name"], "Protect IV")
        self.assertEqual(int(self.session.casting["spell"]["mp"]), int(protect3["mp"]))
        self.assertTrue(self.session.casting["accession"])
        self.assertEqual(self.session._chemist_amplify_until, 0.0)

    def test_amplify_without_a_higher_tier_stays_active(self):
        cure = self.service.spell_by_name("Cure")
        self.assertIsNotNone(cure)
        self.session._chemist_amplify_until = time.time() + 60
        packet = bytearray(16)
        struct.pack_into("<IHHI", packet, 4, 0, 0,
                         packets.ACTION_CAST_MAGIC, int(cure["id"]))
        self.session.cast_magic(bytes(packet), 0)
        self.assertIsNotNone(self.session.casting)
        self.assertEqual(self.session.casting["spell"]["name"], "Cure")
        self.assertGreater(self.session._chemist_amplify_until, time.time())


if __name__ == "__main__":
    unittest.main()
