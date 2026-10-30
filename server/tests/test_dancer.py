"""Dancer job abilities: waltz TP/potency, Daze steps and Finishing Moves.

These drive the real C2S 0x01A action-9 handler and read the 0x028 replies, so a
regression back to "Curing Waltz heals a percentage of max HP" or a flat
Evasion Down step fails here rather than in game.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import dancer, effects, modifiers as mod, packets
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

ACTOR = 0x400


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.bit = 0

    def read(self, count: int) -> int:
        value = 0
        for index in range(count):
            value |= ((self.data[self.bit >> 3] >> (self.bit & 7)) & 1) << index
            self.bit += 1
        return value


def action_result(message: bytes) -> dict:
    reader = BitReader(message[5:])
    return {
        "actor": reader.read(32), "targets": reader.read(6), "results": reader.read(4),
        "category": reader.read(4), "action": reader.read(32), "recast": reader.read(32),
        "target": reader.read(32), "n": reader.read(4), "resolution": reader.read(3),
        "kind": reader.read(2), "sub": reader.read(12), "info": reader.read(5),
        "distortion": reader.read(2), "knockback": reader.read(3), "value": reader.read(17),
        "message": reader.read(10),
    }


def messages(session) -> list[dict]:
    return [action_result(message) for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]


class DancerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config, self.db, self.service = make_service(Path(self.tmp.name))
        self.account = self.service.register("dnc", "password123").account
        self.character = self.service.create_character(
            self.account["id"], {"name": "Dancer", "race": 1})
        self.world = World(self.config, self.service, None)
        self.session = self.make_session(self.character, "Dancer")
        self.world.sessions[("127.0.0.1", 1234)] = self.session
        self.session.char.update({
            "main_job": dancer.DANCER_JOB, "main_level": 99,
            "sub_job": 5, "sub_level": 49,
            "hp": 3000, "hp_current": 1000,
            "mp": 500, "mp_current": 500,
            "tp": 3000,
        })
        self.session.queue.clear()

    def make_session(self, character, name: str, *, targid: int = 0):
        session = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(character["id"]), name))
        session.set_key(bytes(20))
        session.logged_in = True
        session.zone = 246
        session.targid = targid
        session.pos = list(self.world.zones.position(246))
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
            "main_job": 1, "main_level": 99,
            "hp": 3000, "hp_current": 1000,
            "mp": 500, "mp_current": 500, "tp": 1000,
        })
        self.world.sessions[("127.0.0.1", 4321)] = other
        party = self.world.party_of(int(self.session.char["char_id"]))
        if party is None:
            party = self.world.create_party(self.session)
        self.assertTrue(self.world.join_party(party, other))
        other.queue.clear()
        return other

    def enter(self, zone: int) -> None:
        self.session.zone = int(zone)
        self.session.pos = list(self.world.zones.position(int(zone)))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def mob(self):
        return next(entity for entity in self.session.entities
                    if entity.kind == "mob" and entity.alive)

    def use(self, ability_id: int, targid: int = 0) -> None:
        self.session.queue.clear()
        self.session.ability_recasts.clear()
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, int(ability_id))
        self.session.job_ability(bytes(packet), int(targid))

    def in_melee(self):
        self.enter(100)
        mob = self.mob()
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.session.engaged_id = int(mob.id)
        self.session.char["tp"] = 3000
        return mob

    def heal_message(self, session, message: int = packets.MESSAGE_SKILL_RECOVERS_HP):
        return next((entry for entry in messages(session)
                     if entry["message"] == message), None)

    # --- waltzes -----------------------------------------------------------------------

    def test_curing_waltz_v_costs_tp_and_uses_chr_vit(self):
        self.session.char["hp_current"] = 100
        caster_chr = int(self.session.stat_sheet().attributes["chr"])
        target_vit = int(self.session.stat_sheet().attributes["vit"])
        expected = dancer.waltz_amount(
            dancer.WALTZES[311], caster_chr, target_vit, jp_bonus=40)
        self.use(311)
        self.assertEqual(int(self.session.char["tp"]), 2200)
        self.assertEqual(int(self.session.char["hp_current"]), 100 + expected)
        result = self.heal_message(self.session)
        self.assertIsNotNone(result)
        self.assertEqual(int(result["value"]), expected)
        self.assertEqual(int(result["action"]), 311)
        # The old bug healed 9% of max HP for free; prove the formula is not that.
        self.assertNotEqual(expected, 3000 * 9 // 100)

    def test_curing_waltz_refuses_without_tp(self):
        self.session.char["hp_current"] = 100
        self.session.char["tp"] = 199
        self.use(311)
        self.assertEqual(int(self.session.char["hp_current"]), 100)
        self.assertEqual(int(self.session.char["tp"]), 199)
        self.assertIsNone(self.heal_message(self.session))

    def test_curing_waltz_heals_a_party_member(self):
        other = self.party_with()
        other.char["hp_current"] = 250
        caster_chr = int(self.session.stat_sheet().attributes["chr"])
        target_vit = int(other.stat_sheet().attributes["vit"])
        expected = dancer.waltz_amount(
            dancer.WALTZES[192], caster_chr, target_vit, jp_bonus=40)
        self.use(192, other.targid)
        self.assertEqual(int(self.session.char["tp"]), 2500)
        self.assertEqual(int(other.char["hp_current"]), 250 + expected)
        self.assertEqual(int(self.session.char["hp_current"]), 1000)
        result = self.heal_message(other)
        self.assertIsNotNone(result)
        self.assertEqual(int(result["value"]), expected)
        self.assertEqual(int(result["target"]), int(other.char["char_id"]))

    def test_healing_waltz_removes_one_ailment_and_costs_200_tp(self):
        self.session.add_effect(effects.PARALYSIS, duration=60)
        self.use(194)
        self.assertNotIn(effects.PARALYSIS, self.session.status_effects)
        self.assertEqual(int(self.session.char["tp"]), 2800)

    def test_desultor_tassets_carries_the_waltz_tp_cost_mod(self):
        row = self.db.one(
            "SELECT value FROM item_mods WHERE item_id = 16370 AND mod_id = 139")
        self.assertIsNotNone(row)
        self.assertEqual(int(row["value"]), 5)

    def test_waltz_tp_cost_gear_reduces_the_requirement(self):
        """Desultor Tassets is mod 139 value 5: -50 TP off Curing Waltz V."""
        self.session.char["hp_current"] = 100
        self.session.char["tp"] = 750
        with mock.patch.object(self.session, "combat_mods",
                               return_value={mod.WALTZ_COST: 5}):
            self.use(311)
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertGreater(int(self.session.char["hp_current"]), 100)

    def test_saber_dance_blocks_waltzes(self):
        self.session.char["hp_current"] = 100
        self.session.add_effect(effects.SABER_DANCE, duration=300)
        self.use(190)
        self.assertEqual(int(self.session.char["hp_current"]), 100)
        self.assertEqual(int(self.session.char["tp"]), 3000)
        self.assertIsNone(self.heal_message(self.session))

    def test_trance_waives_the_waltz_cost_and_grants_tp(self):
        self.session.add_effect(effects.TRANCE, duration=60)
        self.use(311)
        self.assertEqual(int(self.session.char["tp"]), 3000)  # no waltz cost
        self.assertGreater(int(self.session.char["hp_current"]), 1000)
        # Using Trance itself feeds the job-point TP row (100 TP per rank).
        self.session.queue.clear()
        self.session.remove_effect(effects.TRANCE, quiet=True)
        self.session.char["tp"] = 0
        self.use(181)
        self.assertEqual(int(self.session.char["tp"]), 2000)

    # --- steps -------------------------------------------------------------------------

    def test_quickstep_applies_lethargic_daze_and_awards_moves_without_tp(self):
        mob = self.in_melee()
        base_evasion = int(self.world.debuffed_monster(mob).evasion)
        with mock.patch.object(self.session, "_dnc_physical_hit", return_value=True):
            self.use(201, mob.targid)
        self.assertEqual(int(self.session.char["tp"]), 3000)
        self.assertEqual(self.session._finishing_moves(), 2)
        self.assertIn(386, mob.effect_state)          # Lethargic Daze 1
        self.assertNotIn(effects.EVASION_DOWN, mob.effect_state)
        self.assertEqual(int(mob.effect_state[386]["power"]), 1)
        self.assertEqual(
            int(self.world.debuffed_monster(mob).evasion), max(1, base_evasion - 8))

    def test_second_quickstep_stacks_daze_and_extends_its_timer(self):
        mob = self.in_melee()
        base_evasion = int(self.world.debuffed_monster(mob).evasion)
        with mock.patch.object(self.session, "_dnc_physical_hit", return_value=True):
            self.use(201, mob.targid)
            first_until = float(mob.effect_state[386]["until"])
            self.use(201, mob.targid)
        self.assertIn(387, mob.effect_state)          # Lethargic Daze 2
        self.assertNotIn(386, mob.effect_state)
        self.assertEqual(int(mob.effect_state[387]["power"]), 2)
        self.assertEqual(
            int(self.world.debuffed_monster(mob).evasion), max(1, base_evasion - 12))
        self.assertGreater(float(mob.effect_state[387]["until"]), first_until + 20)
        self.assertEqual(self.session._finishing_moves(), 4)
        self.assertEqual(int(self.session.char["tp"]), 3000)

    def test_feather_step_is_crit_evasion_down_not_accuracy_down(self):
        mob = self.in_melee()
        base_crit_eva = int(
            self.world.debuffed_monster(mob).mods.get(mod.CRITICAL_HIT_EVASION, 0))
        with mock.patch.object(self.session, "_dnc_physical_hit", return_value=True):
            self.use(312, mob.targid)
        self.assertIn(448, mob.effect_state)          # Bewildered Daze 1
        self.assertNotIn(effects.ACCURACY_DOWN, mob.effect_state)
        self.assertNotIn(effects.CRIT_HIT_EVASION_DOWN, mob.effect_state)
        self.assertEqual(
            int(self.world.debuffed_monster(mob).mods.get(mod.CRITICAL_HIT_EVASION, 0)),
            base_crit_eva - 100)

    def test_presto_turns_one_step_into_five_daze_levels_and_six_moves(self):
        mob = self.in_melee()
        self.use(261)                                  # Presto
        self.assertIn(effects.PRESTO, self.session.status_effects)
        with mock.patch.object(self.session, "_dnc_physical_hit", return_value=True):
            self.use(201, mob.targid)
        self.assertNotIn(effects.PRESTO, self.session.status_effects)
        self.assertIn(390, mob.effect_state)           # level 5 icon
        self.assertEqual(int(mob.effect_state[390]["power"]), 5)
        self.assertEqual(self.session._finishing_moves(), 6)
        self.assertEqual(int(self.session.char["tp"]), 3000)

    def test_step_works_without_tp_or_engagement(self):
        """Steps are recast-only, so the HUD leaves them on the timer."""
        self.enter(100)
        mob = self.mob()
        self.session.pos = [mob.x, mob.y, mob.z, self.session.pos[3]]
        self.session.engaged_id = None
        self.session.char["tp"] = 0
        with mock.patch.object(self.session, "_dnc_physical_hit", return_value=True):
            self.use(201, mob.targid)
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertIn(386, mob.effect_state)
        self.assertEqual(self.session._finishing_moves(), 2)

    # --- flourishes --------------------------------------------------------------------

    def test_reverse_flourish_converts_moves_to_tp(self):
        self.session._set_finishing_moves(3)
        self.session.char["tp"] = 0
        self.use(206)
        self.assertEqual(self.session._finishing_moves(), 0)
        self.assertEqual(int(self.session.char["tp"]), 450)

    def test_animated_flourish_gives_volatile_enmity_not_damage(self):
        mob = self.in_melee()
        self.session._set_finishing_moves(2)
        hp = int(mob.hp)
        self.use(204, mob.targid)
        self.assertEqual(int(mob.hp), hp)
        self.assertEqual(self.session._finishing_moves(), 0)
        self.assertGreaterEqual(int(mob.enmity_ve.get(int(self.session.char["char_id"]), 0)),
                                1500)

    def test_building_flourish_consumes_up_to_three_moves(self):
        self.session._set_finishing_moves(5)
        self.use(208)
        self.assertEqual(self.session._finishing_moves(), 2)
        state = self.session.effect(effects.BUILDING_FLOURISH)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["power"]), 3)

    def test_no_foot_rise_grants_finishing_moves(self):
        self.session._set_finishing_moves(0)
        self.use(239)
        self.assertEqual(self.session._finishing_moves(), 1)

    def test_finishing_moves_can_hold_more_than_six(self):
        self.session._set_finishing_moves(9)
        self.assertEqual(self.session._finishing_moves(), 9)
        self.assertEqual(int(self.session.effect(effects.FINISHING_MOVE)["icon"]), 588)
        self.session._spend_finishing_moves(5)
        self.assertEqual(self.session._finishing_moves(), 4)

    # --- sambas and jigs ---------------------------------------------------------------

    def test_haste_samba_costs_350_tp_and_adds_haste(self):
        self.use(189)
        self.assertEqual(int(self.session.char["tp"]), 2650)
        state = self.session.effect(effects.HASTE_SAMBA)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["mods"][mod.HASTE_ABILITY]), 500)
        self.assertGreater(float(state["until"]) - time.time(), 120)

    def test_fan_dance_blocks_sambas(self):
        self.session.add_effect(effects.FAN_DANCE, duration=300)
        self.use(184)
        self.assertEqual(int(self.session.char["tp"]), 3000)
        self.assertIsNone(self.session.effect(effects.DRAIN_SAMBA))

    def test_drain_samba_heals_on_a_landed_hit(self):
        self.use(184)
        self.session.char["hp_current"] = 1000
        self.session._samba_on_hit(100)
        self.assertEqual(int(self.session.char["hp_current"]), 1010)

    def test_contradance_doubles_the_next_waltz_and_is_spent(self):
        self.session.char["hp_current"] = 100
        self.session.add_effect(effects.CONTRADANCE, duration=60)
        caster_chr = int(self.session.stat_sheet().attributes["chr"])
        target_vit = int(self.session.stat_sheet().attributes["vit"])
        base = dancer.waltz_amount(
            dancer.WALTZES[190], caster_chr, target_vit, jp_bonus=40)
        self.use(190)
        self.assertEqual(int(self.session.char["hp_current"]), 100 + base * 2)
        # 200 TP less the 60% Contradance job-point reduction -> 80 TP.
        self.assertEqual(int(self.session.char["tp"]), 2920)
        self.assertIsNone(self.session.effect(effects.CONTRADANCE))

    def test_spectral_jig_sets_sneak_and_invisible(self):
        self.use(196)
        self.assertIn(effects.SNEAK, self.session.status_effects)
        self.assertIn(effects.INVISIBLE, self.session.status_effects)
        self.assertGreater(
            float(self.session.effect(effects.SNEAK)["until"]) - time.time(), 190)

    def test_chocobo_jig_sets_movement_speed(self):
        self.session.add_effect(effects.WEIGHT, duration=60, potency=30)
        self.use(197)
        self.assertIn(effects.QUICKENING, self.session.status_effects)
        self.assertNotIn(effects.WEIGHT, self.session.status_effects)

    def test_aspir_samba_restores_mp_on_a_hit(self):
        self.use(187)
        self.session.char["mp_current"] = 100
        self.session._samba_on_hit(100)
        self.assertEqual(105, int(self.session.char["mp_current"]))

    def test_divine_waltz_heals_the_caster(self):
        self.session.char["hp_current"] = 100
        self.use(195)
        self.assertGreater(int(self.session.char["hp_current"]), 100)

    def test_violent_flourish_spends_a_move_and_hits(self):
        mob = self.in_melee()
        self.session._set_finishing_moves(1)
        self.use(207, mob.targid)
        self.assertEqual(0, self.session._finishing_moves())

    def test_wild_flourish_spends_two_moves(self):
        mob = self.in_melee()
        self.session._set_finishing_moves(2)
        self.use(209, mob.targid)
        self.assertEqual(0, self.session._finishing_moves())

    def test_flourish_three_icons_store_the_spent_moves(self):
        for ability_id, effect_id in ((264, effects.CLIMACTIC_FLOURISH),
                                       (313, effects.STRIKING_FLOURISH),
                                       (314, effects.TERNARY_FLOURISH)):
            self.session._set_finishing_moves(3)
            self.use(ability_id)
            state = self.session.effect(effect_id)
            self.assertIsNotNone(state)
            self.assertGreater(int(state["power"]), 0)

    def test_grand_pas_puts_up_its_icon(self):
        self.use(341)
        self.assertIsNotNone(self.session.effect(effects.GRAND_PAS))

    def test_the_menu_does_not_advertise_category_headers(self):
        """Jigs/Steps/Waltzes/Sambas/Flourishes I-III are headers, not abilities.

        Migration 0147 removes them from job_abilities; the 0x0AC block the HUD
        rebuilds its flat Abilities list from must not carry them either.
        """
        categories = {182, 183, 198, 199, 200, 213, 263}
        self.session.char.update(main_job=dancer.DANCER_JOB, main_level=99,
                                 sub_job=0, sub_level=0)
        advertised = set(self.service.job_ability_ids(dancer.DANCER_JOB, 99))
        self.assertFalse(categories & advertised)
        for real in (190, 194, 196, 197, 201, 204):
            self.assertIn(real, advertised)
            self.assertIsNotNone(self.service.job_ability(real))
        bits = bytes(self.session.char_abilities()[4:])
        for category in categories:
            self.assertFalse(bits[64 + (category >> 3)] & (1 << (category & 7)),
                             "category %d is still in 0x0AC" % category)


if __name__ == "__main__":
    unittest.main()
