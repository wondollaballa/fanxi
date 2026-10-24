"""Weapon skills: the extra effects, drains and damage modifiers beyond the hit.

The regression that started this file: Myrkr was resolved as a plain damage skill, so it
restored no MP and removed no status ailments.  These tests pin the table lookup, the
self-targeted path (no monster and no melee range required), the TP scaling, the drains
and the status effects the combat engine now reads.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import make_service

from fanxi_server.game import (
    combat, effects, modifiers as mod, packets, weapon_skill_effects, weapon_skills,
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


class WeaponSkillTableTest(unittest.TestCase):
    def test_myrkr_is_a_self_skill_that_restores_mp_and_cures(self):
        row = weapon_skill_effects.for_weaponskill("Myrkr")
        self.assertIsNotNone(row)
        self.assertTrue(row.self_targeted)
        self.assertTrue(row.no_damage)
        self.assertEqual(row.mp_percent, (0.2, 0.4, 0.6))
        self.assertEqual(row.cures, 3)
        self.assertEqual(row.statuses, ())

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

    def test_unknown_weapon_skill_has_no_row(self):
        self.assertIsNone(weapon_skills.for_id(99999))


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
        results = action_messages(self.session)
        self.assertTrue(results)
        self.assertEqual(result_message(results[0]), packets.MESSAGE_SKILL_RECOVERS_MP)
        self.assertEqual(result_value(results[0]), mp_max * 2 // 10)

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
        """`!ws Myrkr` must work with no monster selected, like the menu packet does."""
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
        self.assertIn("Zesho Meppo strikes", "\n".join(chat_lines(self.session)))

        # Kikoku is the same katana skill type, but it carries no Prime skill.
        self.session.equipped = {0: (0, 4, 21906)}
        self.session.store_equipment()
        self.session.char["tp"] = 1000
        self.session.queue.clear()
        self.session.weaponskill(self.packet(142), int(mob.targid))
        self.assertIn("You cannot use Zesho Meppo with your equipped weapon.",
                      "\n".join(chat_lines(self.session)))

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
        self.assertIn("Shell Crusher strikes", "\n".join(chat_lines(self.session)))

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

    def test_multi_hit_weapon_skill_rolls_each_hit(self):
        """Shattersoul is three hits; the action carries all three results."""
        mob = self.mob()
        calls: list[float] = []

        def capture(session, entity, **kwargs):
            calls.append(float(kwargs["ftp"]))
            return False, 10, False

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Shattersoul", tp=1000, target=mob)
        self.assertEqual(len(calls), 3)
        # Shattersoul does not carry fTP across its extra hits.
        self.assertAlmostEqual(calls[0], 1.375)
        self.assertAlmostEqual(calls[1], 1.0)
        self.assertAlmostEqual(calls[2], 1.0)
        results = action_messages(self.session)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(action_result_count(results[0]), 3)
        self.assertIn("Shattersoul strikes", "\n".join(chat_lines(self.session)))

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

        with mock.patch.object(self.world, "player_attack", side_effect=capture):
            self.use("Vorpal Blade", tp=1000, target=mob)
        self.assertEqual(len(calls), 4)
        for ftp in calls:
            self.assertAlmostEqual(ftp, 1.375)

    def test_weaponskill_damage_bonus_sums_the_three_lines(self):
        row = self.service.weaponskill_by_name("Combo")
        mods = {mod.WSD_ALL_HITS: 10, mod.WSD_FIRST_HIT: 5,
                mod.WEAPONSKILL_DAMAGE_BASE + int(row["id"]): 7}
        self.assertEqual(self.session.weaponskill_damage_bonus(row, mods), 22)

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
