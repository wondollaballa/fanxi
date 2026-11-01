"""Weapon skills: the extra effects, drains and damage modifiers beyond the hit.

The regression that started this file: Myrkr was resolved as a plain damage skill, so it
restored no MP and removed no status ailments.  These tests pin the table lookup, the
self-targeted path (no monster and no melee range required), the TP scaling, the drains
and the status effects the combat engine now reads.
"""
from __future__ import annotations

import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import (
    augments, combat, effects, modifiers as mod, packets, prime_weapons, skillchain,
    stats, weapon_skill_effects, weapon_skills,
)
from fanxi_server.game.world import World
from fanxi_server.game.zone import ZoneSession

STAFF = 22063        # Nirvana, staff skill 12, present in the reduced test item table


def chat_lines(session) -> list[str]:
    lines = []
    for message in session.queue:
        if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) != 0x017:
            continue
        lines.append(bytes(message[4:])[19:].split(b"\0")[0].decode("ascii", "replace"))
    return lines


def action_messages(session) -> list[bytes]:
    return [message for message in session.queue
            if (struct.unpack_from("<H", message, 0)[0] & 0x1FF) == 0x028]


def action_result_count(message: bytes) -> int:
    """The target's result count in one 0x028 body (a multi-hit skill carries them all)."""
    data = message[5:]
    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32
    value = 0
    for index in range(4):
        value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
    return value


def result_value(message: bytes) -> int:
    """Read the 17-bit result value (damage / MP / effect id) from a 0x028 body."""
    data = message[5:]
    bit = 173
    value = 0
    for index in range(17):
        value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
    return value


def result_message(message: bytes) -> int:
    """Read the 10-bit message id from a 0x028 body."""
    data = message[5:]
    bit = 190
    value = 0
    for index in range(10):
        value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
    return value


def action_category(message: bytes) -> int:
    """Read the 4-bit action category from one 0x028 body."""
    data = message[5:]
    bit = 42
    value = 0
    for index in range(4):
        value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
    return value


def finish_action(session) -> bytes:
    """The weapon-skill finish (category 3), skipping the SkillStart and effect lines.

    A weapon skill can queue more category-3 actions after its damage: its own status
    effect (message 237) and a skillchain proc (287+).  The damage/restore result is the
    first of them and is what the total/hit assertions mean.
    """
    wanted = {
        packets.MESSAGE_DAMAGE, packets.MESSAGE_SKILL_MISSES,
        packets.MESSAGE_SKILL_RECOVERS_MP, packets.MESSAGE_SKILL_RECOVERS_HP,
        packets.MESSAGE_MAGIC_NO_EFFECT, packets.MESSAGE_SKILL_DRAIN_MP,
    }
    for message in action_messages(session):
        if action_category(message) != packets.ACTION_CATEGORY_SKILL_FINISH:
            continue
        if result_message(message) in wanted:
            return message
    raise AssertionError("no weapon-skill finish in the queue")


def result_add_effect(message: bytes) -> dict | None:
    """The result's 0x028 additional-effect block (skillchain/en-spell), or None."""
    data = message[5:]

    def read(bit: int, width: int) -> int:
        value = 0
        for index in range(width):
            value |= ((data[(bit + index) >> 3] >> ((bit + index) & 7)) & 1) << index
        return value

    bit = 32 + 6 + 4 + 4 + 32 + 32 + 32          # header and target id
    count = read(bit, 4)
    bit += 4
    for _ in range(count):
        bit += 3 + 2 + 12 + 5 + 2 + 3 + 17 + 10 + 31
        if read(bit, 1):
            bit += 1
            block = {"kind": read(bit, 6), "info": read(bit + 6, 4),
                     "value": read(bit + 10, 17),
                     "message": read(bit + 27, 10)}
            bit += 37
        else:
            bit += 1
            block = None
        if read(bit, 1):
            bit += 1 + 34
        else:
            bit += 1
        if block is not None:
            return block
    return None


class WeaponSkillTableTest(unittest.TestCase):
    def test_myrkr_is_a_self_skill_that_restores_mp_and_cures(self):
        row = weapon_skill_effects.for_weaponskill("Myrkr")
        self.assertIsNotNone(row)
        self.assertTrue(row.self_targeted)
        self.assertTrue(row.no_damage)
        self.assertEqual(row.mp_percent, (0.2, 0.4, 0.6))
        self.assertEqual(row.cures, 3)
        self.assertEqual(row.statuses, ())

    def test_blitz_scales_from_the_first_hit_at_three_thousand_tp(self):
        row = weapon_skills.for_id(78)
        self.assertEqual(row.name, "Blitz")
        self.assertEqual(row.hits, 5)
        self.assertFalse(row.multi_hit_ftp)
        self.assertAlmostEqual(row.ftp_at(3000), 12.5)
        self.assertAlmostEqual(row.ftp_at(2000), 7.0)

    def test_tp_interpolation_matches_the_retail_anchors(self):
        values = (0.2, 0.4, 0.6)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(1000, values), 0.2)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(1500, values), 0.3)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(2000, values), 0.4)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(2500, values), 0.5)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(3000, values), 0.6)
        # Clamped at both ends: TP below 1000 still scales like 1000.
        self.assertAlmostEqual(weapon_skill_effects.at_tp(0, values), 0.2)
        self.assertAlmostEqual(weapon_skill_effects.at_tp(4000, values), 0.6)

    def test_status_skills_carry_their_retail_effect(self):
        shell = weapon_skill_effects.for_weaponskill("Shell Crusher")
        self.assertIsNotNone(shell)
        status = shell.statuses[0]
        self.assertEqual(status.effect, effects.DEFENSE_DOWN)
        self.assertEqual(status.potency, 25)
        self.assertEqual(weapon_skill_effects.at_tp(1000, status.duration), 180)
        self.assertEqual(weapon_skill_effects.at_tp(3000, status.duration), 300)

        full = weapon_skill_effects.for_weaponskill("Full Break")
        self.assertEqual(len(full.statuses), 4)
        self.assertEqual({row.effect for row in full.statuses},
                         {effects.ATTACK_DOWN, effects.DEFENSE_DOWN,
                          effects.ACCURACY_DOWN, effects.EVASION_DOWN})

    def test_campaign_only_skills_are_not_player_weapon_skills(self):
        for name in ("Uriel Blade", "Glory Slash", "Tartarus Torpor"):
            self.assertTrue(weapon_skill_effects.is_campaign_only(name))
        self.assertFalse(weapon_skill_effects.is_campaign_only("Myrkr"))

    def test_ailments_are_debuffs_not_buffs_or_food(self):
        self.assertIn(effects.POISON, weapon_skill_effects.AILMENTS)
        self.assertIn(effects.DEFENSE_DOWN, weapon_skill_effects.AILMENTS)
        self.assertNotIn(effects.PROTECT, weapon_skill_effects.AILMENTS)
        self.assertNotIn(effects.REFRESH, weapon_skill_effects.AILMENTS)
        self.assertNotIn(effects.FOOD, weapon_skill_effects.AILMENTS)

    def test_pure_damage_skills_have_no_row(self):
        for name in ("Savage Blade", "Tachi Fudo", "Vorpal Blade"):
            self.assertIsNone(weapon_skill_effects.for_weaponskill(name))

    def test_blade_metsu_uses_the_retail_adoulin_values(self):
        # The regression behind this: every skill used the old 2.0 fTP curve and no
        # WSC, so Blade: Metsu did about twice an auto-attack instead of five times
        # the base with 80% DEX.
        row = weapon_skills.for_id(137)
        self.assertIsNotNone(row)
        self.assertEqual(row.name, "Blade Metsu")
        self.assertEqual(row.ftp, (5.0, 5.0, 5.0))
        self.assertAlmostEqual(row.wsc["dex"], 0.8)
        self.assertEqual(row.hits, 1)
        self.assertFalse(row.multi_hit_ftp)

    def test_savage_blade_scales_hard_with_tp(self):
        row = weapon_skills.for_id(42)
        self.assertIsNotNone(row)
        self.assertEqual(row.ftp, (4.0, 10.3, 13.6))
        self.assertEqual(row.hits, 2)

    def test_blade_shun_is_five_hits_and_carries_ftp_on_each(self):
        row = weapon_skills.for_id(141)
        self.assertIsNotNone(row)
        self.assertEqual(row.hits, 5)
        self.assertTrue(row.multi_hit_ftp)
        self.assertEqual(row.attack_varies, (1.0, 2.0, 3.0))

    def test_split_shot_keeps_the_ignore_defense_line_after_the_adoulin_branch(self):
        row = weapon_skills.for_id(209)
        self.assertIsNotNone(row)
        self.assertEqual(row.ignored_defense, (0.0, 0.35, 0.5))

    def test_zesho_meppo_has_a_row_despite_having_only_a_mob_script(self):
        row = weapon_skills.for_id(142)
        self.assertIsNotNone(row)
        self.assertEqual(row.hits, 4)
        self.assertEqual(row.ftp[0], 4.0)
        self.assertAlmostEqual(row.wsc["dex"], 0.25)
        self.assertAlmostEqual(row.wsc["agi"], 0.25)

    def test_magical_skills_carry_their_element_and_dstat(self):
        """Seraph Blade is light; Sanguine Blade is dark with an INT dSTAT term.

        These fields drive the magical formula's affinity and ``dSTAT`` terms.  Black
        Halo is physical and must not be moved onto the magical path.
        """
        seraph = weapon_skills.for_id(37)
        self.assertTrue(seraph.magic)
        self.assertEqual(seraph.element, "light")
        self.assertEqual(seraph.dstat, ())

        sanguine = weapon_skills.for_id(47)
        self.assertTrue(sanguine.magic)
        self.assertEqual(sanguine.element, "dark")
        self.assertEqual(sanguine.dstat, ("int", 2.0, 0))
        self.assertEqual(sanguine.dstat_for({"int": 200}, {"int": 50}), 300)

        black = weapon_skills.for_id(169)
        self.assertFalse(black.magic)
        self.assertEqual(black.hits, 2)

    def test_sanguine_blade_drains_fifty_one_hundred_one_sixty(self):
        row = weapon_skill_effects.for_weaponskill("Sanguine Blade")
        self.assertIsNotNone(row)
        self.assertEqual(row.hp_from_damage, (0.5, 1.0, 1.6))
        self.assertAlmostEqual(
            weapon_skill_effects.at_tp(3000, row.hp_from_damage), 1.6)

    def test_ranged_sheet_combines_weapon_and_ammo_damage(self):
        """Marksmanship WS base is ranged DMG + ammo DMG, with the ranged skill."""
        sheet = stats.build_character(
            {"race": 1, "main_job": 17, "main_level": 99, "sub_job": 19, "sub_level": 49},
            {mod.RATT: 200, mod.RACC: 300}, {26: 414},
            ranged_weapon=stats.Weapon(item_id=22143, skill=26, dmg=167,
                                       delay=600, ilvl_skill=269),
            ammo=stats.Weapon(item_id=21326, skill=26, dmg=245, delay=240))
        self.assertIsNotNone(sheet.ranged_fighter)
        self.assertEqual(sheet.ranged_fighter.weapon_skill, 26)
        self.assertEqual(sheet.ranged_fighter.weapon_dmg, 412)
        self.assertEqual(sheet.ranged_fighter.skill_value, 683)
        self.assertGreater(sheet.ranged_fighter.attack, 900)
        self.assertGreater(sheet.ranged_fighter.accuracy, 300)

    def test_unknown_weapon_skill_has_no_row(self):
        self.assertIsNone(weapon_skills.for_id(99999))

    def test_prime_aftermath_potency_is_linear_over_spent_tp(self):
        """The FFXIAH 1,611-TP sample read 3% on stage 3, so the percent is floored."""
        self.assertEqual(prime_weapons.potency_at(3, 1000), 2)
        self.assertEqual(prime_weapons.potency_at(3, 1611), 3)
        self.assertEqual(prime_weapons.potency_at(3, 2000), 5)
        self.assertEqual(prime_weapons.potency_at(3, 3000), 8)
        self.assertEqual(prime_weapons.potency_at(4, 3000), 10)
        self.assertEqual(prime_weapons.potency_at(5, 3000), 12)
        # The bar can carry more than 3,000; the skill only spends the cap.
        self.assertEqual(prime_weapons.potency_at(5, 4000), 12)
        self.assertEqual(prime_weapons.potency_at(5, 500), 6)
        # Duration/tier are banded, not linear: 1,999 TP is still tier 1.
        self.assertEqual(prime_weapons.tier_at(1999), 1)
        self.assertEqual(prime_weapons.tier_at(2000), 2)
        self.assertEqual(prime_weapons.tier_at(2999), 2)
        self.assertEqual(prime_weapons.tier_at(3000), 3)
        self.assertEqual(prime_weapons.tier_at(3500), 3)

    def test_prime_aftermath_overwrite_ladder(self):
        self.assertTrue(prime_weapons.can_overwrite(1, 1))
        self.assertTrue(prime_weapons.can_overwrite(1, 2))
        self.assertTrue(prime_weapons.can_overwrite(1, 3))
        self.assertTrue(prime_weapons.can_overwrite(2, 3))
        self.assertFalse(prime_weapons.can_overwrite(2, 1))
        self.assertFalse(prime_weapons.can_overwrite(2, 2))
        self.assertFalse(prime_weapons.can_overwrite(3, 1))
        self.assertFalse(prime_weapons.can_overwrite(3, 2))
        self.assertFalse(prime_weapons.can_overwrite(3, 3))


class WeaponSkillSessionTest(unittest.TestCase):
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
        # Scholar 99: staff 378, so the skill_level 0 staff weapon skills are advertised.
        self.session.char["main_job"] = 20
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 5
        self.session.char["sub_level"] = 49
        self.zone(100)
        self.session.equipped = {0: (0, 4, STAFF)}

    def zone(self, zone_id):
        self.session.zone = zone_id
        self.session.pos = list(self.world.zones.position(zone_id))
        self.session.load_zone_entities()
        self.session.after_zone_in()
        self.session.queue.clear()
        self.session.zone_loaded = True

    def mob(self):
        entity = next(entity for entity in self.session.entities
                      if entity.kind == "mob" and entity.alive)
        entity.hp = entity.hp_max = 100_000
        self.session.pos = [entity.x, entity.y, entity.z, 0]
        self.session.engaged_id = entity.id
        self.session.engaged_targid = entity.targid
        return entity

    def packet(self, ws_id: int) -> bytes:
        buf = bytearray(16)
        struct.pack_into("<IHH", buf, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_WEAPONSKILL)
        struct.pack_into("<I", buf, 12, int(ws_id))
        return bytes(buf)

    def use(self, name: str, *, tp: int, target=None):
        row = self.service.weaponskill_by_name(name)
        self.assertIsNotNone(row, name)
        self.session.char["tp"] = tp
        self.session.queue.clear()
        self.session.weaponskill(self.packet(int(row["id"])),
                                 int(target.targid) if target is not None else 0)
        return row

    def test_party_member_sees_the_closing_weapon_skill_and_its_skillchain(self):
        """A box's WS action is broadcast; the main needs the add-effect to animate it."""
        other = ZoneSession(
            self.world, None,
            self.service.character_record(self.service.character(self.character["id"]),
                                          "Fanxi"))
        other.set_key(bytes(20))
        other.logged_in = True
        other.zone = self.session.zone
        other.pos = list(self.session.pos)
        self.world.sessions[("127.0.0.1", 4321)] = other
        mob = self.mob()
        other.sent_targids = {int(self.session.char.get("targid", 0x400)),
                              int(mob.targid)}
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 500, False)), \
                mock.patch.object(self.session, "_magic_weaponskill",
                                  return_value=500):
            self.use("Heavy Swing", tp=1000, target=mob)
            mob.skillchain.started -= 5.0
            mob.skillchain.until = mob.skillchain.started + skillchain.OPEN_SECONDS
            other.queue.clear()
            self.use("Earth Crusher", tp=1000, target=mob)
        starts = [m for m in action_messages(other)
                  if action_category(m) == packets.ACTION_CATEGORY_SKILL_START]
        self.assertTrue(starts)
        self.assertEqual(result_value(starts[-1]), int(self.service.weaponskill_by_name(
            "Earth Crusher")["id"]))
        finishes = [m for m in action_messages(other)
                    if action_category(m) == packets.ACTION_CATEGORY_SKILL_FINISH]
        self.assertTrue(finishes)
        self.assertEqual(result_value(finishes[-1]), 500)
        effect = result_add_effect(finishes[-1])
        self.assertIsNotNone(effect)
        self.assertEqual(250, effect["value"])

    def ability(self, ability_id: int) -> None:
        p = bytearray(16)
        struct.pack_into("<IHH", p, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", p, 12, int(ability_id))
        self.session.job_ability(bytes(p), 0)
        self.session.queue.clear()

    def test_sekkanoki_spends_one_thousand_and_keeps_the_rest(self):
        mob = self.mob()
        self.ability(230)   # Sekkanoki
        self.use("Heavy Swing", tp=3000, target=mob)
        # The skill cost 1000 TP, and the hit return may add some back on top.
        self.assertGreaterEqual(int(self.session.char["tp"]), 2000)

    def test_blitz_scales_its_first_hit_and_keeps_later_hits_at_one_ftp(self):
        """Blitz is a five-hit Prime skill with first-hit-only fTP.

        The 3,000-TP anchor of 12.5 applies to the opening hit; the four later native
        hits use 1.0.  This is the documented Prime WS shape (the same as Ruthless
        Stroke) and is why a missed opening hit hurts Blitz so much.  Ikenga's Axe in
        the off hand adds Weapon Skill Damage +5%, which the engine folds into every
        hit's fTP, so the shape arrives as 13.125/1.05 -- and the off-hand axe itself
        adds a sixth swing at 1.05, because two one-handed weapons always swing here.
        """
        self.session.equipped = {0: (8, 19, 21730), 1: (0, 2, 21723)}
        self.session.store_equipment()
        mob = self.mob()
        calls = []

        def attack(*_args, **kwargs):
            calls.append(float(kwargs.get("ftp", 0.0)))
            return False, 100, False

        with mock.patch.object(self.world, "player_attack", side_effect=attack), \
                mock.patch.object(self.session, "_multi_attack_hits", return_value=1):
            self.use("Blitz", tp=3000, target=mob)
        self.assertEqual(len(calls), 6)
        self.assertEqual(calls, [12.5 * 1.05, 1.05, 1.05, 1.05, 1.05, 1.05])
        self.assertEqual(result_value(finish_action(self.session)), 600)

    def equip_ranged(self):
        """COR with a sword main and a gun + bullet in the ranged/ammo slots."""
        self.session.char.update(main_job=17, main_level=99, sub_job=19, sub_level=49)
        self.session.equipped = {
            0: (8, 7, 21621),    # Naegling, sword skill
            2: (0, 10, 22143),   # Fomalhaut, marksmanship 269
            3: (0, 11, 21326),   # Living Bullet, DMG 245
        }
        self.session.store_equipment()

    def test_hot_shot_uses_the_ranged_weapon_and_adds_hybrid_magic(self):
        """A gun WS must not swing Naegling, and Hot Shot is physical + magic.

        Regression: Hot Shot resolved through the main-hand Fighter, so a 3,000-TP
        COR with Fomalhaut + Living Bullet used the sword's 166 DMG and then stopped
        at the physical number.  The magic half of a hybrid skill is what puts the
        skill into the tens of thousands.
        """
        self.equip_ranged()
        sheet = self.session.stat_sheet()
        self.assertEqual(sheet.ranged_fighter.weapon_dmg, 412)
        self.assertEqual(sheet.ranged_fighter.weapon_skill, 26)
        mob = self.mob()
        captured = {}

        def attack(*_args, **kwargs):
            captured.update(kwargs)
            return False, 1000, False

        with mock.patch.object(self.world, "player_attack", side_effect=attack):
            self.use("Hot Shot", tp=3000, target=mob)
        self.assertTrue(captured.get("ranged"))
        self.assertGreater(result_value(finish_action(self.session)), 1000)

    def test_a_weapon_skill_uses_the_gear_equipped_in_this_batch(self):
        """The phase engine's precast 0x050s and the action can share one datagram.

        ``stat_sheet`` reads ``char_equip``; without a flush first, a weapon swapped in
        the same batch as the weapon skill would not be the one the damage roll sees.
        """
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        self.session.equipped = {0: (8, 7, 21751)}   # Aymur
        self.session.store_equipment()
        self.session.equipped = {0: (8, 19, 21730)}  # Spalirisos, swapped in this batch
        self.session.equipment_changed = True
        mob = self.mob()
        captured = {}

        def roll(_entity, **kwargs):
            captured["sheet"] = kwargs["sheet"]
            return {"damage": 100, "landed": 1, "swings": 1, "critical": False,
                    "defeated": False, "first_main_landed": True,
                    "offhand_tp_hit": False, "extra_landed": 0}

        with mock.patch.object(self.session, "_roll_weaponskill_round", side_effect=roll):
            self.use("Decimation", tp=3000, target=mob)
        self.assertEqual(captured["sheet"].weapon.item_id, 21730)

    def test_knights_of_rotund_is_item_granted_only(self):
        """The Excalipoor II joke WS must not sit in every sword user's menu.

        Id 227 carried skill_level 0, which made the normal 350-skill sword list
        advertise it to a Caliburnus Paladin alongside Imperator.  It belongs to
        Excalipoor II's 355 row and should only appear while that weapon is worn.
        """
        self.session.char.update(main_job=7, main_level=99, sub_job=20, sub_level=49)
        self.session.equipped = {0: (0, 7, 21621)}   # Naegling, an ordinary sword
        self.session.store_equipment()
        ordinary = self.session.equipped_weapon_skills()
        self.assertNotIn(227, ordinary)

        self.session.equipped = {0: (0, 7, 20714)}   # Excalipoor II, 355 = 227
        self.session.store_equipment()
        self.assertIn(227, self.session.equipped_weapon_skills())

        self.session.equipped = {0: (0, 7, 21646)}   # Caliburnus, 355 = 233
        self.session.store_equipment()
        caliburnus = self.session.equipped_weapon_skills()
        self.assertIn(233, caliburnus)
        self.assertNotIn(227, caliburnus)

    def test_imperator_lands_from_caliburnus(self):
        """Caliburnus grants Imperator and the action resolves with its aftermath."""
        self.session.char.update(main_job=7, main_level=99, sub_job=20, sub_level=49)
        self.session.equipped = {0: (0, 7, 21646)}   # Caliburnus
        self.session.store_equipment()
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 500, False)), \
                mock.patch.object(self.session, "_multi_attack_hits", return_value=1):
            self.use("Imperator", tp=3000, target=mob)
        self.assertEqual(result_value(finish_action(self.session)), 500)
        self.assertGreater(int(self.session.char["tp"]), 0)
        self.assertTrue(self.session.has_effect(effects.AFTERMATH))
        self.assertEqual(int(self.session.effect_power(effects.AFTERMATH)), 3)

    def test_seraph_blade_takes_the_magical_path_and_returns_tp(self):
        """A ``magic: true`` row must not roll pDIF or a physical hit.

        Seraph Blade is a light-elemental magical WS.  The session gathers the magic
        terms and hands them to ``combat.magic_weaponskill``; ``_roll_weaponskill_round``
        (the physical/my-hit path) must not run at all.  With a Rank 25 Crocea Mors in
        the main hand and Daybreak in the sub, the gathered terms carry the +100%
        elemental WS augment, Daybreak's +50 light affinity, both weapons' Magic Damage
        and the iLvl 119 weapon-level base.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=20, sub_level=49)
        char_id = int(self.session.char["id"])
        self.service.add_item(char_id, 21627)   # Crocea Mors
        crocea = self.service.db.one(
            "SELECT container, slot FROM char_inventory WHERE character_id = ? "
            "AND item_id = 21627 ORDER BY slot LIMIT 1", (char_id,))
        self.service.set_item_extra(
            char_id, int(crocea["container"]), int(crocea["slot"]),
            augments.bundle("C", 25, 2, 63))
        self.service.add_item(char_id, 22040)   # Daybreak
        daybreak = self.service.db.one(
            "SELECT container, slot FROM char_inventory WHERE character_id = ? "
            "AND item_id = 22040 ORDER BY slot LIMIT 1", (char_id,))
        self.session.equipped = {
            0: (int(crocea["container"]), int(crocea["slot"]), 21627),
            1: (int(daybreak["container"]), int(daybreak["slot"]), 22040),
        }
        self.session.store_equipment()
        mob = self.mob()
        with mock.patch.object(combat, "magic_weaponskill",
                               return_value=4321) as formula, \
                mock.patch.object(self.session, "_roll_weaponskill_round",
                                  side_effect=AssertionError("physical path used")):
            self.use("Seraph Blade", tp=3000, target=mob)
        kwargs = formula.call_args.kwargs
        self.assertEqual(kwargs["weapon_level"], 119)
        self.assertEqual(kwargs["elemental_ws"], 100)
        self.assertEqual(kwargs["affinity"], 50)
        self.assertGreaterEqual(kwargs["magic_damage"], 217 + 241)
        self.assertEqual(result_value(finish_action(self.session)), 4321)
        self.assertEqual(mob.hp, 100_000 - 4321)
        # A magical WS still pays the main-hand delay back to the TP bar.
        self.assertGreater(int(self.session.char["tp"]), 0)

    def test_black_halo_stays_physical_and_keeps_first_hit_only_ftp(self):
        """Black Halo is a two-hit club skill, not a magical one.

        Maxentius's "+50% Black Halo" line is its per-skill WSD row (739), and only the
        opening native hit gets the full 9.6 fTP; the second hit uses 1.0.  A regression
        that put every ``doMagicWeaponskill`` row on the magic path must not drag the
        physical club skill with it.
        """
        self.session.char.update(main_job=5, main_level=99, sub_job=20, sub_level=49)
        self.session.equipped = {0: (0, 7, 22031)}   # Maxentius, no off-hand weapon
        self.session.store_equipment()
        mob = self.mob()
        calls = []

        def attack(*_args, **kwargs):
            calls.append(float(kwargs.get("ftp", 0.0)))
            return False, 100, False

        with mock.patch.object(self.world, "player_attack", side_effect=attack), \
                mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.session, "_magic_weaponskill",
                                  side_effect=AssertionError("magical path used")):
            self.use("Black Halo", tp=3000, target=mob)
        mods = self.session.combat_mods()
        wsd = (mods.get(mod.WSD_ALL_HITS, 0)
               + mods.get(mod.WEAPONSKILL_DAMAGE_BASE + 169, 0))
        scale = 1.0 + wsd / 100.0
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(calls[0], 9.6 * scale, places=3)
        self.assertAlmostEqual(calls[1], 1.0 * scale, places=3)

    def test_two_staff_skills_form_a_skillchain(self):
        """The chain is an additional effect on the closing WS, not a second action."""
        mob = self.mob()
        with mock.patch.object(self.session.world, "player_attack",
                               return_value=(False, 500, False)), \
                mock.patch.object(self.session, "_magic_weaponskill",
                                  return_value=500):
            self.use("Heavy Swing", tp=1000, target=mob)
            self.assertIsNotNone(mob.skillchain)
            self.assertEqual(0, mob.skillchain.tier)
            self.assertAlmostEqual(skillchain.OPEN_SECONDS,
                                   mob.skillchain.until - mob.skillchain.started, places=1)
            # The closing skill has to land more than three seconds after the opening.
            mob.skillchain.started -= 5.0
            mob.skillchain.until = mob.skillchain.started + skillchain.OPEN_SECONDS
            hp_before = mob.hp
            self.use("Earth Crusher", tp=1000, target=mob)
        self.assertEqual(int(skillchain.SC.DETONATION), int(mob.skillchain.sc))
        self.assertEqual(1, mob.skillchain.count)
        # 500 (the closing hit) x 0.50 for a tier-1 first link.
        self.assertEqual(hp_before - 500 - 250, mob.hp)
        finish = finish_action(self.session)
        self.assertEqual(result_value(finish), 500)
        effect = result_add_effect(finish)
        self.assertIsNotNone(effect)
        self.assertEqual(skillchain.proc_kind(mob.skillchain.sc), effect["kind"])
        self.assertEqual(250, effect["value"])
        self.assertEqual(skillchain.proc_message(mob.skillchain.sc),
                         effect["message"])
        # No extra 0x028 for the chain: the animation and damage ride the WS result.
        self.assertNotIn(skillchain.proc_message(mob.skillchain.sc),
                         [result_message(m) for m in action_messages(self.session)])

    def test_skillchain_bonus_gear_scales_the_closing_damage(self):
        mob = self.mob()
        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.SKILLCHAIN_BONUS] = 20
            return mods

        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 500, False)), \
                mock.patch.object(self.session, "_magic_weaponskill",
                                  return_value=500):
            self.use("Heavy Swing", tp=1000, target=mob)
            mob.skillchain.started -= 5.0
            mob.skillchain.until = mob.skillchain.started + skillchain.OPEN_SECONDS
            hp_before = mob.hp
            self.use("Earth Crusher", tp=1000, target=mob)
        # 500 closing hit x 0.50 x 1.20 Skillchain Bonus.
        self.assertEqual(hp_before - 500 - 300, mob.hp)
        effect = result_add_effect(finish_action(self.session))
        self.assertIsNotNone(effect)
        self.assertEqual(300, effect["value"])

    def test_myrkr_restores_mp_and_cures_without_a_target(self):
        self.session.char["mp_current"] = 0
        self.session.add_effect(effects.POISON, duration=300, tick=3)
        self.session.add_effect(effects.SILENCE, duration=300)
        self.use("Myrkr", tp=1000)   # no engaged monster at all
        mp_max = int(self.session.char["mp"])
        self.assertEqual(int(self.session.char["mp_current"]), mp_max * 2 // 10)
        self.assertFalse(self.session.has_effect(effects.POISON))
        self.assertFalse(self.session.has_effect(effects.SILENCE))
        self.assertEqual(int(self.session.char["tp"]), 0)
        self.assertIn("You recover %d MP." % (mp_max * 2 // 10), chat_lines(self.session))
        # The client's own result says "recovers MP", not "takes damage".
        finish = finish_action(self.session)
        self.assertEqual(result_message(finish), packets.MESSAGE_SKILL_RECOVERS_MP)
        self.assertEqual(result_value(finish), mp_max * 2 // 10)
        starts = [message for message in action_messages(self.session)
                  if action_category(message) == packets.ACTION_CATEGORY_SKILL_START]
        self.assertEqual(len(starts), 1)
        self.assertEqual(result_message(starts[0]), packets.MESSAGE_READIES_WEAPONSKILL)

    def test_myrkr_scales_with_tp_and_keeps_tp_above_the_cap(self):
        self.session.char["mp_current"] = 0
        self.use("Myrkr", tp=3000)
        mp_max = int(self.session.char["mp"])
        self.assertEqual(int(self.session.char["mp_current"]), mp_max * 6 // 10)
        self.assertEqual(int(self.session.char["tp"]), 0)

        self.session.char["mp_current"] = 0
        self.use("Myrkr", tp=3500)
        self.assertEqual(int(self.session.char["tp"]), 500)

    def test_bang_ws_uses_the_same_self_skill_path(self):
        """`//ws Myrkr` must work with no monster selected, like the menu packet does."""
        self.session.char["tp"] = 1000
        self.session.char["mp_current"] = 0
        self.session.queue.clear()
        self.session.command(["ws", "Myrkr"])
        mp_max = int(self.session.char["mp"])
        self.assertEqual(int(self.session.char["mp_current"]), mp_max * 2 // 10)
        self.assertEqual(int(self.session.char["tp"]), 0)

    def test_myrkr_removes_at_most_three_ailments(self):
        for effect_id in (effects.POISON, effects.SILENCE, effects.BLINDNESS,
                          effects.PARALYSIS, effects.WEIGHT):
            self.session.add_effect(effect_id, duration=300)
        self.use("Myrkr", tp=1000)
        remaining = [effect_id for effect_id in
                     (effects.POISON, effects.SILENCE, effects.BLINDNESS,
                      effects.PARALYSIS, effects.WEIGHT)
                     if self.session.has_effect(effect_id)]
        self.assertEqual(len(remaining), 2)
        self.assertIn("Myrkr removes 3 status ailments.", chat_lines(self.session))

    def test_myrkr_does_not_damage_a_monster(self):
        mob = self.mob()
        self.use("Myrkr", tp=1000, target=mob)
        self.assertEqual(mob.hp, mob.hp_max)
        self.assertIn("You recover", "\n".join(chat_lines(self.session)))

    def test_prime_weapon_skill_is_only_usable_with_its_weapon(self):
        """Zesho Meppo comes from Dokoku's 355 modifier, not from katana skill."""
        self.session.char["main_job"] = 13          # NIN
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 1
        self.session.char["sub_level"] = 49
        self.session.equipped = {0: (0, 4, 21932)}  # Dokoku 119 III
        self.session.store_equipment()
        self.assertIn(142, self.session.equipped_weapon_skills())
        mob = self.mob()
        row = self.use("Zesho Meppo", tp=1000, target=mob)
        self.assertEqual(int(row["id"]), 142)
        self.assertEqual(result_message(finish_action(self.session)), packets.MESSAGE_DAMAGE)
        self.assertEqual(result_value(finish_action(self.session)), mob.hp_max - mob.hp)

        # Kikoku is the same katana skill type, but it carries no Prime skill.
        self.session.equipped = {0: (0, 4, 21906)}
        self.session.store_equipment()
        self.session.char["tp"] = 1000
        self.session.queue.clear()
        self.session.weaponskill(self.packet(142), int(mob.targid))
        self.assertIn("You cannot use Zesho Meppo with your equipped weapon.",
                      "\n".join(chat_lines(self.session)))

    def equip_prime_dagger(self, item_id: int = 21590) -> None:
        """DNC 99 with Mpu Gandring stage 4/5, whose 355 grants Ruthless Stroke."""
        self.session.char["main_job"] = 19          # DNC
        self.session.char["main_level"] = 99
        self.session.char["sub_job"] = 13
        self.session.char["sub_level"] = 49
        self.session.equipped = {0: (0, 4, int(item_id))}
        self.session.store_equipment()
        self.session.queue.clear()

    def test_prime_aftermath_is_up_for_the_activating_weapon_skill(self):
        """The PDL bonus is already on the sheet when Ruthless's first hit rolls."""
        self.equip_prime_dagger(21590)              # stage 5
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        seen: list[int] = []

        def capture(session, entity, **kwargs):
            seen.append(int(session.combat_mods().get(mod.DAMAGE_LIMITP, 0)))
            return False, 1, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Ruthless Stroke", tp=1000, target=mob)
        self.assertEqual(seen, [6, 6, 6, 6])
        state = self.session.effect(effects.AFTERMATH)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["power"]), 1)
        self.assertEqual(int(state["potency"]), 6)
        self.assertEqual(int(state["icon"]), effects.AFTERMATH_LV1)
        self.assertAlmostEqual(float(state["until"]) - time.time(), 60.0, delta=2.0)
        # The buff reaches the fighter's modifier pool, so auto-attacks and later
        # weapon skills keep the raised pDIF cap for its duration.
        self.assertEqual(
            self.session.stat_sheet().fighter.mods.get(mod.DAMAGE_LIMITP), 6)

    def test_prime_aftermath_tiers_follow_the_tp_spent(self):
        for item_id, expected in ((21590, {1000: 6, 2000: 9, 3000: 12}),
                                  (21589, {1000: 4, 2000: 7, 3000: 10})):
            self.equip_prime_dagger(item_id)
            self.session.remove_effect(effects.AFTERMATH, quiet=True)
            for tp, potency in expected.items():
                mob = self.mob()
                mob.hp = mob.hp_max = 10_000_000
                self.use("Ruthless Stroke", tp=tp, target=mob)
                state = self.session.effect(effects.AFTERMATH)
                self.assertIsNotNone(state, (item_id, tp))
                tier = tp // 1000
                self.assertEqual(int(state["power"]), tier)
                self.assertEqual(int(state["potency"]), potency)
                self.assertEqual(int(state["icon"]), effects.AFTERMATH_LV1 + tier - 1)
                self.assertAlmostEqual(float(state["until"]) - time.time(),
                                       60.0 * tier, delta=2.0)

    def test_prime_aftermath_ignores_tp_bonus(self):
        """Retail uses the TP spent; TP Bonus only moves the fTP/WSC scaling."""
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.TP_BONUS] = 1000
            return mods

        with mock.patch.object(self.session, "combat_mods", side_effect=boosted):
            self.use("Ruthless Stroke", tp=1000, target=mob)
        state = self.session.effect(effects.AFTERMATH)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["power"]), 1)
        self.assertEqual(int(state["potency"]), 6)
        self.assertAlmostEqual(float(state["until"]) - time.time(), 60.0, delta=2.0)

    def test_prime_aftermath_overwrite_rules(self):
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000

        def cast(tp: int) -> dict:
            self.use("Ruthless Stroke", tp=tp, target=mob)
            state = self.session.effect(effects.AFTERMATH)
            self.assertIsNotNone(state)
            return state

        first = cast(1000)
        first_until = float(first["until"])
        # Level 1 can and will overwrite itself.
        second = cast(1000)
        self.assertGreater(float(second["until"]), first_until)

        # Level 3 replaces level 1 and then locks itself.
        third = cast(3000)
        self.assertEqual(int(third["power"]), 3)
        self.assertEqual(int(third["potency"]), 12)
        third_until = float(third["until"])
        fourth = cast(2000)
        self.assertEqual(float(fourth["until"]), third_until)
        self.assertEqual(int(fourth["power"]), 3)
        fifth = cast(3000)
        self.assertEqual(float(fifth["until"]), third_until)

        # Level 2 overwrites level 1 but neither refreshes itself nor replaces level 3.
        self.session.remove_effect(effects.AFTERMATH, quiet=True)
        level_two = cast(2000)
        level_two_until = float(level_two["until"])
        self.assertEqual(int(level_two["power"]), 2)
        self.assertEqual(float(cast(2000)["until"]), level_two_until)
        self.assertEqual(float(cast(1000)["until"]), level_two_until)
        self.assertEqual(int(cast(3000)["power"]), 3)

    def test_prime_aftermath_is_only_for_the_weapons_own_skill(self):
        """Ruthless with Mpu Gandring grants aftermath; Rudra's with the same dagger does not."""
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        self.use("Rudras Storm", tp=1000, target=mob)
        self.assertFalse(self.session.has_effect(effects.AFTERMATH))

    def test_blitz_aftermath_survives_a_gear_burst_that_re_wears_the_weapon(self):
        """The phase engine re-sends main and sub after every WS, the weapons included.

        Retail removes the aftermath when the worn weapon is replaced or taken off, not
        when the same bag copy is put on again.  Blitz's Spalirisos and its off-hand axe
        stay in their slots across the TP/WS sets, so the re-sent 0x050s must leave the
        buff alone (before the fix the burst a second after the skill cleared it).
        """
        self.session.char.update(main_job=9, main_level=99, sub_job=0, sub_level=0)
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 0, 70, ?, 1)",
            (int(self.session.char["id"]), 21730))          # Spalirisos
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 0, 71, ?, 1)",
            (int(self.session.char["id"]), 21723))          # Ikenga's Axe
        self.session.equipped = {0: (0, 70, 21730), 1: (0, 71, 21723)}
        self.session.store_equipment()
        self.session.queue.clear()
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 100, False)):
            self.use("Blitz", tp=1000, target=mob)
        self.assertTrue(self.session.has_effect(effects.AFTERMATH))

        self.session.equip(bytes((0x50, 4, 0, 0, 70, 0, 0, 0)))  # main: same copy
        self.session.equip(bytes((0x50, 4, 0, 0, 71, 1, 0, 0)))  # sub: same copy
        self.session.flush_equipment()      # the burst settles on the next tick
        state = self.session.effect(effects.AFTERMATH)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["power"]), 1)
        self.assertAlmostEqual(float(state["until"]) - time.time(), 60.0, delta=2.0)
        self.assertEqual(
            self.session.stat_sheet().fighter.mods.get(mod.DAMAGE_LIMITP),
            int(state["potency"]))

    def test_unequipping_a_weapon_drops_prime_aftermath(self):
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        self.use("Ruthless Stroke", tp=1000, target=mob)
        self.assertTrue(self.session.has_effect(effects.AFTERMATH))
        self.session.queue.clear()
        self.session.equip(bytes((0x50, 4, 0, 0, 0, 0, 0, 0)))  # remove main
        self.assertFalse(self.session.has_effect(effects.AFTERMATH))

    def test_prime_aftermath_applies_even_when_the_skill_misses(self):
        """Retail grants the buff from the use, not from the hit (Oshala's note says so)."""
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        with mock.patch.object(self.world, "player_attack", return_value=(True, 0, False)):
            self.use("Ruthless Stroke", tp=1000, target=mob)
        state = self.session.effect(effects.AFTERMATH)
        self.assertIsNotNone(state)
        self.assertEqual(int(state["potency"]), 6)

    def test_prime_aftermath_wears_off(self):
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        self.use("Ruthless Stroke", tp=1000, target=mob)
        self.assertTrue(self.session.has_effect(effects.AFTERMATH))
        self.session.tick_player_effects(time.time() + 61.0)
        self.assertFalse(self.session.has_effect(effects.AFTERMATH))
        self.assertEqual(
            self.session.stat_sheet().fighter.mods.get(mod.DAMAGE_LIMITP), None)

    def test_swapping_a_weapon_drops_prime_aftermath(self):
        self.equip_prime_dagger(21590)
        mob = self.mob()
        mob.hp = mob.hp_max = 10_000_000
        self.use("Ruthless Stroke", tp=1000, target=mob)
        self.assertTrue(self.session.has_effect(effects.AFTERMATH))
        # Twashtar is a legal DNC dagger; swapping it into the main hand is a weapon
        # change, so retail removes the aftermath even though the WS stays available.
        self.db.execute(
            "INSERT OR REPLACE INTO char_inventory "
            "(character_id, container, slot, item_id, quantity) VALUES (?, 0, 70, ?, 1)",
            (int(self.session.char["id"]), 20563))
        self.session.equip(bytes((0x50, 4, 0, 0, 70, 0, 0, 0)))
        self.assertEqual(int(self.session.equipped[0][2]), 20563)
        self.assertFalse(self.session.has_effect(effects.AFTERMATH))

    def test_shell_crusher_lands_defense_down_on_a_hit(self):
        mob = self.mob()
        self.use("Shell Crusher", tp=1000, target=mob)
        self.assertIn(effects.DEFENSE_DOWN, mob.effect_state)
        state = mob.effect_state[effects.DEFENSE_DOWN]
        self.assertEqual(int(state["potency"]), 25)
        self.assertGreater(float(state["until"]), 0.0)
        # Duration is retail's 180 s at 1000 TP, scaled down at most by the resist roll.
        remaining = float(state["until"]) - __import__("time").time()
        self.assertGreater(remaining, 90.0)
        self.assertEqual(result_message(finish_action(self.session)), packets.MESSAGE_DAMAGE)

    def test_no_additional_effect_when_the_skill_misses(self):
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack", return_value=(True, 0, False)):
            self.use("Shell Crusher", tp=1000, target=mob)
        self.assertNotIn(effects.DEFENSE_DOWN, mob.effect_state)

    def test_spirit_taker_restores_mp_equal_to_damage(self):
        mob = self.mob()
        self.session.char["mp_current"] = 0
        with mock.patch.object(self.world, "player_attack", return_value=(False, 137, False)):
            self.use("Spirit Taker", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["mp_current"]), 137)

    def test_energy_drain_deals_no_hp_damage_and_drains_mp(self):
        self.session.equipped = {0: (0, 4, self.dagger_item())}
        mob = self.mob()
        self.session.char["mp_current"] = 0
        self.use("Energy Drain", tp=1000, target=mob)
        self.assertEqual(mob.hp, mob.hp_max)
        self.assertGreater(int(self.session.char["mp_current"]), 0)
        results = action_messages(self.session)
        self.assertIn(packets.MESSAGE_SKILL_DRAIN_MP,
                      [result_message(message) for message in results])

    def dagger_item(self) -> int:
        row = self.db.one("SELECT item_id FROM items WHERE skill = 2 LIMIT 1")
        self.assertIsNotNone(row, "no dagger in the test item table")
        return int(row["item_id"])

    def test_ws_damage_gear_is_folded_into_the_scaling(self):
        mob = self.mob()
        seen: list[float] = []

        def capture(session, entity, **kwargs):
            seen.append(float(kwargs["ftp"]))
            return False, 1, False

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertAlmostEqual(seen[-1], 1.0)   # Heavy Swing's own fTP at 1000 TP

        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.WSD_ALL_HITS] = 50
            return mods

        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertAlmostEqual(seen[-1], 1.5)   # 1.0 x 1.5

    def test_fotia_ftp_bonus_is_added_in_256ths(self):
        mob = self.mob()
        seen: list[float] = []

        def capture(session, entity, **kwargs):
            seen.append(float(kwargs["ftp"]))
            return False, 1, False

        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.ANY_FTP_BONUS] = 256      # +1.0 fTP
            return mods

        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertAlmostEqual(seen[-1], 2.0)

    def test_weapon_skill_passes_wsc_and_the_skill_ftp(self):
        """A skill's own fTP and WSC reach the swing, not the old generic 2.0."""
        mob = self.mob()
        seen: list[dict] = []

        def capture(session, entity, **kwargs):
            seen.append(dict(kwargs))
            return False, 1, False

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        # Heavy Swing's WSC is 100% STR, so the base damage grows by the session's STR.
        self.assertGreater(int(seen[-1]["wsc"]), 0)
        self.assertAlmostEqual(float(seen[-1]["ftp"]), 1.0)

    def test_multi_hit_weapon_skill_rolls_each_hit_and_sends_one_total(self):
        """Shattersoul is three hits; the action carries their summed damage once."""
        mob = self.mob()
        calls: list[float] = []

        def capture(session, entity, **kwargs):
            calls.append(float(kwargs["ftp"]))
            return False, 10, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Shattersoul", tp=1000, target=mob)
        self.assertEqual(len(calls), 3)
        # Shattersoul does not carry fTP across its extra hits.
        self.assertAlmostEqual(calls[0], 1.375)
        self.assertAlmostEqual(calls[1], 1.0)
        self.assertAlmostEqual(calls[2], 1.0)
        finish = finish_action(self.session)
        self.assertEqual(action_result_count(finish), 1)
        self.assertEqual(result_value(finish), 30)
        self.assertEqual(result_message(finish), packets.MESSAGE_DAMAGE)
        # One client line, not one per hit.
        self.assertNotIn("Shattersoul strikes", "\n".join(chat_lines(self.session)))

    def test_multi_hit_ftp_applies_to_every_hit(self):
        """Vorpal Blade is a multiHitfTP skill: every hit uses the full fTP."""
        sword = self.db.one("SELECT item_id FROM items WHERE skill = 3 LIMIT 1")
        self.assertIsNotNone(sword)
        self.session.char["main_job"] = 1     # WAR has sword skill for Vorpal Blade
        self.session.char["main_level"] = 99
        self.session.equipped = {0: (0, 4, int(sword["item_id"]))}
        self.session.store_equipment()
        mob = self.mob()
        calls: list[float] = []

        def capture(session, entity, **kwargs):
            calls.append(float(kwargs["ftp"]))
            return False, 10, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.session, "combat_mods", return_value={}), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Vorpal Blade", tp=1000, target=mob)
        self.assertEqual(len(calls), 4)
        for ftp in calls:
            self.assertAlmostEqual(ftp, 1.375)

    def test_weapon_skill_start_packet_precedes_the_finish(self):
        """Retail sends SkillStart (category 7) before SkillFinish (category 3)."""
        mob = self.mob()
        row = self.use("Heavy Swing", tp=1000, target=mob)
        messages = action_messages(self.session)
        self.assertGreaterEqual(len(messages), 2)
        start, finish = messages[0], messages[-1]
        self.assertEqual(action_category(start), packets.ACTION_CATEGORY_SKILL_START)
        self.assertEqual(result_message(start), packets.MESSAGE_READIES_WEAPONSKILL)
        self.assertEqual(result_value(start), int(row["id"]))
        # The finish is held for the next flush: start and finish in one datagram let the
        # client read animation 6/237 against the spell table (Cure VI / Choke).
        self.assertEqual(float(getattr(start, "not_before", 0.0)), 0.0)
        self.assertGreater(float(getattr(finish, "not_before", 0.0)), 0.0)
        self.assertEqual(action_category(finish), packets.ACTION_CATEGORY_SKILL_FINISH)
        self.assertEqual(action_result_count(finish), 1)

    def test_a_delayed_weapon_skill_finish_waits_for_the_next_flush(self):
        """pack() holds the finish until its deadline, so the start goes out alone."""
        mob = self.mob()
        self.use("Heavy Swing", tp=1000, target=mob)
        finish = finish_action(self.session)
        self.assertGreater(float(finish.not_before), time.time())
        original = self.world.huff
        huff = mock.Mock()
        huff.compress.return_value = (b"\0\0\0\0", 32)
        self.world.huff = huff
        self.addCleanup(setattr, self.world, "huff", original)
        self.session.queue = [finish]
        data, _bits, _zone_out = self.session.pack()
        self.assertEqual(data, b"")               # nothing else is due
        self.assertIn(finish, self.session.queue)
        finish.not_before = 0.0
        self.session.server_id += 1          # the SkillStart packet has gone out
        data, _bits, _zone_out = self.session.pack()
        self.assertNotEqual(data, b"")
        self.assertNotIn(finish, self.session.queue)

    def test_double_attack_adds_an_extra_weapon_skill_swing(self):
        """A DA proc rolls a second main-hand hit; both land in the single total."""
        self.equip_prime_dagger()
        mob = self.mob()
        calls: list[dict] = []

        def capture(session, entity, **kwargs):
            calls.append(dict(kwargs))
            return False, 10, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=2), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Rudras Storm", tp=1000, target=mob)
        self.assertEqual(len(calls), 2)
        self.assertEqual({call["off_hand"] for call in calls}, {False})
        self.assertEqual(result_value(finish_action(self.session)), 20)

    def test_dual_wield_adds_the_offhand_swing(self):
        """Dual wield gives a weapon skill one off-hand hit even when it lists one hit."""
        self.equip_prime_dagger()
        self.session.equipped = {0: (0, 4, 21590), 1: (0, 4, 20586)}
        self.session.store_equipment()
        self.assertIsNotNone(self.session.stat_sheet().sub_fighter)
        mob = self.mob()
        calls: list[bool] = []

        def capture(session, entity, **kwargs):
            calls.append(bool(kwargs.get("off_hand")))
            return False, 10, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Rudras Storm", tp=1000, target=mob)
        self.assertEqual(calls, [False, True])
        self.assertEqual(result_value(finish_action(self.session)), 20)

    def test_normal_weapon_skill_cannot_crit_but_crit_varies_can(self):
        """BG-wiki: only "critical hit rate varies with TP" skills may critical hit."""
        mob = self.mob()
        seen: list[bool] = []

        def capture(session, entity, **kwargs):
            seen.append(bool(kwargs.get("allow_critical")))
            return False, 10, False

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(seen, [False])

        self.equip_prime_dagger()
        seen.clear()
        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Evisceration", tp=1000, target=mob)
        self.assertTrue(seen)
        self.assertTrue(all(seen))

    def test_overkill_is_capped_to_the_targets_remaining_hp(self):
        """Retail shows what the target had left, not the raw 18K a low-HP mob cannot take."""
        mob = self.mob()
        mob.hp = 500
        with mock.patch.object(self.world, "player_attack", return_value=(False, 1000, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(result_value(finish_action(self.session)), 500)
        self.assertEqual(mob.hp, 0)

    def test_all_misses_send_the_skill_miss_message(self):
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack", return_value=(True, 0, False)):
            self.use("Shattersoul", tp=1000, target=mob)
        finish = finish_action(self.session)
        self.assertEqual(result_value(finish), 0)
        self.assertEqual(result_message(finish), packets.MESSAGE_SKILL_MISSES)

    def test_first_hit_gets_the_hidden_accuracy_bonus(self):
        """LSB passes bonusAcc + 100 for the first main-hand hit only."""
        mob = self.mob()
        accuracy: list[int] = []

        def capture(session, entity, **kwargs):
            accuracy.append(int(kwargs["accuracy_bonus"]))
            return False, 10, False

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(accuracy, [100])

        accuracy.clear()
        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Shattersoul", tp=1000, target=mob)
        self.assertEqual(accuracy[0], 100)
        self.assertEqual(accuracy[1:], [0, 0])

    def test_one_weapon_skill_round_stops_at_eight_swings(self):
        self.equip_prime_dagger()
        mob = self.mob()
        calls: list[dict] = []

        def capture(session, entity, **kwargs):
            calls.append(dict(kwargs))
            return False, 1, False

        with mock.patch.object(self.session, "_multi_attack_hits", return_value=4), \
                mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Ruthless Stroke", tp=1000, target=mob)
        self.assertEqual(len(calls), combat.MAX_ATTACKS_PER_ROUND)

    def test_samurai_store_tp_merit_adds_two_per_rank(self):
        self.session.char.update(main_job=12, main_level=99, sub_job=1, sub_level=49)
        self.session._trait_cache = None
        self.session._merit_counts = None
        base = int(self.session.combat_mods().get(mod.STORETP, 0))
        self.service.save_merit(int(self.character["id"]), 0x0444, 5)
        self.session._merit_counts = None
        self.assertEqual(int(self.session.combat_mods().get(mod.STORETP, 0)), base + 10)

    def test_first_hit_returns_the_main_hand_delay_in_tp(self):
        mob = self.mob()
        sheet = self.session.stat_sheet()
        stp = int(sheet.fighter.mods.get(mod.STORETP, 0))
        expected = combat.tp_gain(sheet.tp_per_hit(off_hand=False), stp)
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), expected)

    def test_store_tp_multiplies_the_weapon_skill_tp_return(self):
        mob = self.mob()
        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.STORETP] = 50
            return mods

        sheet = self.session.stat_sheet()
        base = sheet.tp_per_hit(off_hand=False)
        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), combat.tp_gain(base, 50))

    def test_every_extra_hit_returns_ten_tp_after_store_tp(self):
        mob = self.mob()
        sheet = self.session.stat_sheet()
        stp = int(sheet.fighter.mods.get(mod.STORETP, 0))
        expected = (combat.tp_gain(sheet.tp_per_hit(off_hand=False), stp)
                    + 2 * combat.tp_gain(10, stp))
        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 10, False)):
            self.use("Shattersoul", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), expected)

    def test_one_hit_dual_wield_returns_both_hands_delays(self):
        self.equip_prime_dagger()
        self.session.equipped = {0: (0, 4, 21590), 1: (0, 4, 20586)}
        self.session.store_equipment()
        mob = self.mob()
        sheet = self.session.stat_sheet()
        stp = int(sheet.fighter.mods.get(mod.STORETP, 0))
        expected = (combat.tp_gain(sheet.tp_per_hit(off_hand=False), stp)
                    + combat.tp_gain(sheet.tp_per_hit(off_hand=True), stp))
        with mock.patch.object(self.session, "_multi_attack_hits", return_value=1), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 10, False)):
            self.use("Rudras Storm", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), expected)

    def test_conserve_tp_adds_a_saved_amount(self):
        mob = self.mob()
        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.CONSERVE_TP] = 100
            return mods

        sheet = self.session.stat_sheet()
        base = combat.tp_gain(
            sheet.tp_per_hit(off_hand=False),
            int(sheet.fighter.mods.get(mod.STORETP, 0)))
        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "rng",
                                  mock.Mock(random=lambda: 0.0,
                                            randint=lambda a, b: 50)), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), base + 50)

    def test_save_tp_replaces_a_smaller_return(self):
        mob = self.mob()
        original = self.session.combat_mods

        def boosted():
            mods = original()
            mods[mod.SAVETP] = 500
            return mods

        with mock.patch.object(self.session, "combat_mods", side_effect=boosted), \
                mock.patch.object(self.world, "player_attack",
                                  return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), 500)

    def test_an_all_miss_weapon_skill_returns_no_tp(self):
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack",
                               return_value=(True, 0, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), 0)

    def test_hagakure_grants_save_tp_and_tp_bonus_to_the_next_ws(self):
        row = self.service.job_ability(288)
        self.assertIsNotNone(row)
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 288)
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)
        self.assertGreater(float(getattr(self.session, "_hagakure_until", 0)), 0)
        mob = self.mob()
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=1000, target=mob)
        # The 400 Save TP beats the staff's normal delay return.
        self.assertEqual(int(self.session.char["tp"]), 400)
        self.assertEqual(float(getattr(self.session, "_hagakure_until", 0)), 0.0)

    def test_meikyo_spends_1000_and_returns_no_tp(self):
        packet = bytearray(16)
        struct.pack_into("<IHH", packet, 0, int(self.session.char["char_id"]), 0,
                         packets.ACTION_JOBABILITY)
        struct.pack_into("<I", packet, 12, 27)
        self.session.queue.clear()
        self.session.job_ability(bytes(packet), 0)
        self.assertEqual(int(self.session.char["tp"]), 3000)
        mob = self.mob()
        self.session.char["tp"] = 3000
        with mock.patch.object(self.world, "player_attack",
                               return_value=(False, 10, False)):
            self.use("Heavy Swing", tp=3000, target=mob)
        self.assertEqual(int(self.session.char["tp"]), 2000)

    def test_weaponskill_damage_bonus_sums_the_three_lines(self):
        row = self.service.weaponskill_by_name("Combo")
        mods = {mod.WSD_ALL_HITS: 10, mod.WSD_FIRST_HIT: 5,
                mod.WEAPONSKILL_DAMAGE_BASE + int(row["id"]): 7}
        self.assertEqual(self.session.weaponskill_damage_bonus(row, mods), 22)

    def test_naegling_and_kaja_sword_add_savage_blade_damage(self):
        savage = self.service.weaponskill_by_name("Savage Blade")
        key = mod.WEAPONSKILL_DAMAGE_BASE + int(savage["id"])
        for item_id in (21620, 21621):
            mods = self.service.item_mods(item_id)
            self.assertEqual(mods.get(key), 15, item_id)
            self.assertEqual(self.session.weaponskill_damage_bonus(savage, mods), 15)

    def test_every_damaging_skill_has_a_row(self):
        """A new weapon_skills migration must not silently leave a skill on the old curve."""
        exempt = {
            "Dagan", "Energy Drain", "Energy Steal", "Moonlight", "Myrkr", "Starlight",
            "Tartarus Torpor", "Dagda",     # self/campaign, or no published fTP
        }
        missing = []
        for row in self.db.all("SELECT id, name FROM weapon_skills"):
            if row["name"] in exempt:
                continue
            if weapon_skills.for_id(int(row["id"])) is None:
                missing.append(row["name"])
        self.assertEqual(missing, [])

    def test_tp_bonus_raises_the_scaling_tp_without_being_spent(self):
        # A staff is two-handed, so Fencer is off and only the generic TP Bonus applies.
        self.assertEqual(self.session.weaponskill_tp(1000, {mod.TP_BONUS: 500}), 1500)
        self.assertEqual(self.session.weaponskill_tp(2800, {mod.TP_BONUS: 500}), 3000)
        # The bonus changes Myrkr's 30%-at-1500-TP restore but not the TP the bar loses.
        self.session.char["mp_current"] = 0
        with mock.patch.object(self.session, "combat_mods",
                               return_value={mod.TP_BONUS: 500}):
            self.use("Myrkr", tp=1000)
        mp_max = int(self.session.char["mp"])
        self.assertEqual(int(self.session.char["mp_current"]), mp_max * 3 // 10)
        self.assertEqual(int(self.session.char["tp"]), 0)

    def test_fencer_needs_a_single_wielded_one_handed_weapon(self):
        sword = self.db.one("SELECT item_id FROM items WHERE skill = 3 LIMIT 1")
        dagger = self.db.one("SELECT item_id FROM items WHERE skill = 2 LIMIT 1")
        shield = self.db.one("SELECT item_id FROM item_shield LIMIT 1")
        self.assertIsNotNone(sword)
        self.assertIsNotNone(dagger)

        self.session.equipped = {0: (0, 4, int(sword["item_id"]))}
        self.session.store_equipment()
        self.assertTrue(self.session.fencer_active())

        # A second weapon in the sub slot is dual wield, not Fencer.
        self.session.equipped = {0: (0, 4, int(sword["item_id"])),
                                 1: (0, 4, int(dagger["item_id"]))}
        self.session.store_equipment()
        self.assertFalse(self.session.fencer_active())

        # A shield is not a weapon and keeps Fencer active.
        if shield is not None:
            self.session.equipped = {0: (0, 4, int(sword["item_id"])),
                                     1: (0, 4, int(shield["item_id"]))}
            self.session.store_equipment()
            self.assertTrue(self.session.fencer_active())

        # A two-handed staff never gets Fencer.
        self.session.equipped = {0: (0, 4, STAFF)}
        self.session.store_equipment()
        self.assertFalse(self.session.fencer_active())

    def test_campaign_skills_are_not_advertised_or_usable(self):
        ids = set(self.session.equipped_weapon_skills())
        for name in ("Uriel Blade", "Glory Slash", "Tartarus Torpor"):
            row = self.service.weaponskill_by_name(name)
            self.assertNotIn(int(row["id"]), ids)
        row = self.service.weaponskill_by_name("Tartarus Torpor")
        self.session.queue.clear()
        self.session.weaponskill(self.packet(int(row["id"])), 0)
        self.assertIn("Campaign Battle", "\n".join(chat_lines(self.session)))


class MonsterDebuffTest(unittest.TestCase):
    def test_defense_down_raises_player_damage(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        config, db, service = make_service(Path(temporary.name))
        account = service.register("tester", "password123").account
        character = service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        world = World(config, service, None)
        session = ZoneSession(world, None, service.character_record(
            service.character(character["id"]), "Fanxi"))
        session.zone = 100
        session.pos = list(world.zones.position(100))
        session.load_zone_entities()
        session.zone_loaded = True
        mob = next(entity for entity in session.entities
                   if entity.kind == "mob" and entity.alive)
        plain = world.monster_sheet(mob).fighter.defense
        mob.effect_state[effects.DEFENSE_DOWN] = {
            "until": 0.0, "power": 25, "potency": 25, "tick": 0, "icon": 149}
        self.assertEqual(world.debuffed_monster(mob).defense,
                         max(1, int(plain * 75 / 100)))

    def test_magic_debuffs_become_negative_modifiers(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        config, db, service = make_service(Path(temporary.name))
        account = service.register("tester", "password123").account
        character = service.create_character(account["id"], {"name": "Fanxi", "race": 1})
        world = World(config, service, None)
        session = ZoneSession(world, None, service.character_record(
            service.character(character["id"]), "Fanxi"))
        session.zone = 100
        session.pos = list(world.zones.position(100))
        session.load_zone_entities()
        session.zone_loaded = True
        mob = next(entity for entity in session.entities
                   if entity.kind == "mob" and entity.alive)
        mob.effect_state[effects.MAGIC_DEF_DOWN] = {
            "until": 0.0, "power": 10, "potency": 10, "tick": 0, "icon": 167}
        mob.effect_state[effects.MAGIC_EVASION_DOWN] = {
            "until": 0.0, "power": 10, "potency": 0, "tick": 0, "icon": 404}
        mods = world.monster_debuff_mods(mob)
        self.assertEqual(mods.get(mod.MDEF), -10)
        self.assertEqual(mods.get(mod.MEVA), -10)
        # A negative MDEF must raise magic damage rather than being clamped at zero.
        with_debuff = combat.magic_damage(
            base=100, multiplier=1.0, caster_int=100, target_int=50, skill=300,
            mods={}, target_mods=mods, target_level=int(mob.level))
        without = combat.magic_damage(
            base=100, multiplier=1.0, caster_int=100, target_int=50, skill=300,
            mods={}, target_mods={}, target_level=int(mob.level))
        self.assertGreater(with_debuff, without)


if __name__ == "__main__":
    unittest.main()
