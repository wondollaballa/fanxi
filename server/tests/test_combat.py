"""The combat engine: fSTR, pDIF, hit rate, crit rate and damage-taken caps."""
from __future__ import annotations

import random
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.game import base_stats, combat, modifiers as mod, stats  # noqa: E402


class SkillCurveTest(unittest.TestCase):
    def test_accuracy_curve_compresses_past_200(self):
        self.assertEqual(combat.acc_from_skill(100), 100)
        self.assertEqual(combat.acc_from_skill(200), 200)
        self.assertEqual(combat.acc_from_skill(400), 380)
        self.assertEqual(combat.acc_from_skill(600), 540)
        # A+ skill at 99 is 424, worth 399 accuracy: 380 + 24 * 0.8.
        self.assertEqual(combat.acc_from_skill(424), 399)
        self.assertEqual(combat.acc_from_skill(0), 0)

    def test_weapon_rank_is_damage_over_nine(self):
        self.assertEqual(combat.weapon_rank(150), 16)
        self.assertEqual(combat.weapon_rank(5), 0)
        # Hand-to-hand adds three to the rating before dividing.
        self.assertEqual(combat.weapon_rank(5, h2h=True), 0)
        self.assertEqual(combat.weapon_rank(9, h2h=True), 1)


class FstrTest(unittest.TestCase):
    def test_player_branches(self):
        rank = 10
        self.assertEqual(combat.fstr(100, 80, rank), (20 + 4) // 4)   # diff >= 12
        self.assertEqual(combat.fstr(100, 92, rank), (8 + 6) // 4)    # diff  6..11
        self.assertEqual(combat.fstr(100, 98, rank), (2 + 7) // 4)    # diff  1..5

    def test_player_caps_are_weapon_rank(self):
        rank = 4
        # Huge STR advantage is clamped to rank + 8.
        self.assertEqual(combat.fstr(999, 0, rank), rank + 8)
        # Huge deficit is clamped to -rank.
        self.assertEqual(combat.fstr(0, 999, rank), -rank)

    def test_monsters_use_the_coarse_table(self):
        self.assertEqual(combat.fstr(100, 64, 0, is_mob=True, level=99), (36 - 4) // 4)
        self.assertEqual(combat.fstr(10, 10, 0, is_mob=True, level=99), 0)


class DamageTakenTest(unittest.TestCase):
    def test_uncapped(self):
        self.assertAlmostEqual(combat.damage_taken({}), 1.0)
        self.assertAlmostEqual(combat.damage_taken({mod.DMGPHYS: -1000}), 0.9)

    def test_generic_dt_and_pdt_are_additive(self):
        # 25% PDT + 10% "Damage taken" is 35% off, not 32.5%.
        self.assertAlmostEqual(combat.damage_taken({mod.DMG: -1000, mod.DMGPHYS: -2500}), 0.65)

    def test_fifty_percent_cap(self):
        self.assertAlmostEqual(combat.damage_taken({mod.DMG: -3000, mod.DMGPHYS: -3000}), 0.5)

    def test_pdt_two_bypasses_the_cap(self):
        # Burtgang at 50% PDT: the game takes 32% of normal damage.
        self.assertAlmostEqual(
            combat.damage_taken({mod.DMG: -3000, mod.DMGPHYS: -3000, mod.DMGPHYS_II: -1800}), 0.32)

    def test_hard_floor_is_87_5_percent(self):
        self.assertAlmostEqual(combat.damage_taken({mod.DMGPHYS: -5000, mod.DMGPHYS_II: -5000}), 0.125)

    def test_magic_does_not_use_pdt(self):
        self.assertAlmostEqual(combat.damage_taken({mod.DMGPHYS: -5000}, physical=False), 1.0)
        self.assertAlmostEqual(combat.damage_taken({mod.DMGMAGIC: -5000}, physical=False), 0.5)


class MagicTest(unittest.TestCase):
    def damage(self, **overrides):
        values = dict(base=100, multiplier=1.0, caster_int=150, target_int=50, skill=400,
                      mods={}, target_mods={}, target_level=99)
        values.update(overrides)
        return combat.magic_damage(**values)

    def test_magic_attack_bonus_multiplies(self):
        self.assertEqual(self.damage(), 300)
        self.assertEqual(self.damage(mods={mod.MATT: 50}), 450)

    def test_flat_magic_damage_is_added_before_mab(self):
        self.assertEqual(self.damage(mods={mod.MAGIC_DAMAGE: 100}), 400)
        # Magic Damage joins the base, then the whole thing takes the MAB multiplier.
        self.assertEqual(self.damage(mods={mod.MATT: 50, mod.MAGIC_DAMAGE: 100}), 600)

    def test_magic_defence_bonus_uses_the_mab_over_mdb_ratio(self):
        # 300 * 100 / (100 + 10) = 272.7
        self.assertEqual(self.damage(target_mods={mod.MDEF: 10}), 272)

    def test_skill_and_magic_accuracy_push_resist_to_full(self):
        self.assertEqual(combat.magic_resist(
            skill=400, caster_int=150, mods={mod.MACC: 50}, target_level=99,
            target_mods={}), 1.0)
        self.assertLess(combat.magic_resist(
            skill=0, caster_int=30, mods={}, target_level=125,
            target_mods={mod.MEVA: 200}), 0.75)

    def test_dia_opening_hit_stays_small(self):
        """Dia's base is 2..23 and MND adds only a little; gear Magic Damage is ignored."""
        self.assertEqual(combat.dia_damage(base=2, caster_mnd=300, target_mnd=10), 38)
        self.assertEqual(combat.dia_damage(base=2, caster_mnd=5, target_mnd=12), 2)
        # Even an impossible MND gap cannot turn the enfeebling into a nuke.
        self.assertLess(combat.dia_damage(base=23, caster_mnd=999, target_mnd=0), 80)

    def test_helix_uses_its_own_stat_curve(self):
        """BG-wiki's test: 25 + dINT, halving after 100 (not the nuke's dINT x 2)."""
        def helix(caster_int: int, **overrides) -> int:
            values = dict(base=25, multiplier=1.0, caster_int=caster_int, target_int=100,
                          skill=400, mods={}, target_mods={}, target_level=99)
            values.update(overrides)
            return combat.helix_damage(**values)

        self.assertEqual(helix(138), 63)     # the wiki's 99 SCH vs dINT 38
        self.assertEqual(helix(200), 125)    # dINT 100: 25 + 100
        self.assertEqual(helix(300), 175)    # dINT 200: 25 + 100 + 50
        self.assertEqual(helix(200, mods={mod.MATT: 50}), 187)
        self.assertEqual(helix(200, target_mods={mod.MDEF: 10}), 113)

    def test_fast_cast_halves_at_fifty_percent(self):
        self.assertEqual(combat.cast_time(3000, 0), 3000)
        self.assertEqual(combat.cast_time(3000, 25), 2250)
        self.assertEqual(combat.cast_time(3000, 50), 1500)
        self.assertEqual(combat.cast_time(3000, 99), 1500)   # 50% cap
        self.assertEqual(combat.cast_time(1000, 99), 500)    # floor

    def test_store_tp_scales_tp(self):
        self.assertEqual(combat.tp_gain(100, 0), 100)
        self.assertEqual(combat.tp_gain(100, 10), 110)


class PDifTest(unittest.TestCase):
    def rng(self, seed: int = 7) -> random.Random:
        return random.Random(seed)

    def test_ratio_is_capped_by_weapon_type(self):
        for _ in range(200):
            value = combat.pdif(attack=5000, defense=100, weapon_skill=3, is_critical=False,
                                attacker_level=99, target_level=99, is_pc=True,
                                corrected=False, rng=self.rng())
            self.assertLessEqual(value, 3.25 * 1.05 + 0.001)

    def test_scythe_caps_higher_than_a_sword(self):
        sword = max(combat.pdif(attack=5000, defense=100, weapon_skill=3, is_critical=False,
                                attacker_level=99, target_level=99, is_pc=True,
                                corrected=False, rng=self.rng(seed)) for seed in range(40))
        scythe = max(combat.pdif(attack=5000, defense=100, weapon_skill=7, is_critical=False,
                                 attacker_level=99, target_level=99, is_pc=True,
                                 corrected=False, rng=self.rng(seed)) for seed in range(40))
        self.assertGreater(scythe, sword)

    def test_level_correction_only_penalises_players(self):
        self.assertAlmostEqual(combat.level_term(99, 119, is_pc=True, corrected=True), -0.9375)
        # A player never gains from being higher level than the target.
        self.assertEqual(combat.level_term(119, 99, is_pc=True, corrected=True), 0.0)
        # A monster never loses from being lower level.
        self.assertEqual(combat.level_term(99, 119, is_pc=False, corrected=True), 0.0)
        self.assertAlmostEqual(combat.level_term(119, 99, is_pc=False, corrected=True), 0.9375)
        # And nothing happens outside a level-corrected zone.
        self.assertEqual(combat.level_term(99, 119, is_pc=True, corrected=False), 0.0)

    def test_low_ratio_has_a_low_multiplier(self):
        value = combat.pdif(attack=100, defense=1000, weapon_skill=3, is_critical=False,
                            attacker_level=99, target_level=99, is_pc=True,
                            corrected=False, rng=self.rng())
        self.assertLess(value, 0.5)


class HitRateTest(unittest.TestCase):
    def test_equal_accuracy_and_evasion_is_75_percent(self):
        self.assertAlmostEqual(
            combat.hit_rate(accuracy=400, evasion=400, attacker_level=99, target_level=99,
                            is_pc=True), 0.75)

    def test_caps(self):
        self.assertAlmostEqual(
            combat.hit_rate(accuracy=9999, evasion=0, attacker_level=99, target_level=99,
                            is_pc=True), 0.99)
        self.assertAlmostEqual(
            combat.hit_rate(accuracy=9999, evasion=0, attacker_level=99, target_level=99,
                            is_pc=True, two_handed=True), 0.95)
        self.assertAlmostEqual(
            combat.hit_rate(accuracy=9999, evasion=0, attacker_level=99, target_level=99,
                            is_pc=True, off_hand=True), 0.95)

    def test_floor(self):
        self.assertAlmostEqual(
            combat.hit_rate(accuracy=0, evasion=9999, attacker_level=99, target_level=99,
                            is_pc=True), 0.20)

    def test_level_penalty_applies_to_players(self):
        lower = combat.hit_rate(accuracy=400, evasion=400, attacker_level=99, target_level=119,
                                is_pc=True, corrected=True)
        self.assertLess(lower, 0.75)

    def test_monsters_get_the_mirror_bonus(self):
        higher = combat.hit_rate(accuracy=400, evasion=400, attacker_level=119, target_level=99,
                                 is_pc=False, corrected=True)
        self.assertGreater(higher, 0.75)
        # ...but it is still one-way: a monster below the player gains nothing.
        low = combat.hit_rate(accuracy=400, evasion=400, attacker_level=50, target_level=99,
                              is_pc=False, corrected=True)
        self.assertAlmostEqual(low, 0.75)


class CritRateTest(unittest.TestCase):
    def test_base_is_five_percent(self):
        self.assertAlmostEqual(combat.crit_rate(attacker_dex=50, target_agi=50, is_pc=True), 0.05)

    def test_ddex_table(self):
        self.assertAlmostEqual(combat.crit_rate(attacker_dex=57, target_agi=50, is_pc=True), 0.06)
        self.assertAlmostEqual(combat.crit_rate(attacker_dex=70, target_agi=50, is_pc=True), 0.08)
        self.assertAlmostEqual(combat.crit_rate(attacker_dex=50, target_agi=0, is_pc=True), 0.20)

    def test_gear_and_target_evasion(self):
        self.assertAlmostEqual(
            combat.crit_rate(attacker_dex=50, target_agi=50, is_pc=True, crit_mod=500), 0.10)
        self.assertAlmostEqual(
            combat.crit_rate(attacker_dex=50, target_agi=50, is_pc=True,
                             target_crit_evasion=1000), 0.05)


class DefenceTest(unittest.TestCase):
    """Parry, guard and shield block: rates are retail, reductions are documented."""

    def test_parry_rate_band(self):
        self.assertEqual(combat.parry_rate(424, 300), 25)      # capped
        self.assertEqual(combat.parry_rate(300, 424), 5)      # floored
        self.assertGreater(combat.parry_rate(424, 424), combat.parry_rate(424, 500))

    def test_guard_rate_band(self):
        self.assertEqual(combat.guard_rate(424, 300), 25)
        self.assertEqual(combat.guard_rate(300, 424), 5)

    def test_block_rate_uses_shield_size_and_skill(self):
        # Kite shield (3) has a 45% base, plus 0.2325 per point of skill lead.
        self.assertEqual(combat.block_rate(3, 424, 300), int(45 + 124 * 0.2325))
        self.assertGreater(combat.block_rate(5, 424, 300), combat.block_rate(4, 424, 300))
        self.assertEqual(combat.block_rate(3, 0, 999), 5)

    def defender(self, **kwargs) -> combat.Fighter:
        base = dict(level=99, attack=500, defense=500, accuracy=500, evasion=400,
                    strength=80, dexterity=80, vitality=80, agility=80, is_pc=True,
                    weapon_skill=5, weapon_dmg=150, weapon_rank=16)
        base.update(kwargs)
        return combat.Fighter(**base)

    def test_a_shield_reduces_damage(self):
        # A monster far below the defender's shield skill caps the block rate at 100%,
        # which is the cleanest way to compare the two damage totals.
        attacker = stats.build_monster(99).fighter
        attacker.skill_value = 100
        bare = self.defender()
        shielded = self.defender(shield_skill=424, shield_size=3)
        rng = random.Random(11)
        plain = [combat.melee(attacker, bare, zone=246, rng=rng) for _ in range(400)]
        rng = random.Random(11)
        blocked = [combat.melee(attacker, shielded, zone=246, rng=rng) for _ in range(400)]
        landed = [hit for hit in blocked if not hit.missed]
        self.assertGreater(len(landed), 200)
        self.assertTrue(all(hit.defended == "block" for hit in landed))
        self.assertLess(sum(hit.damage for hit in blocked),
                        sum(hit.damage for hit in plain) * 0.7)

    def test_parry_reduces_damage(self):
        attacker = stats.build_monster(99).fighter
        attacker.skill_value = 100   # caps parry at 25%
        plain = self.defender()
        parrying = self.defender(parry_skill=424)
        rng = random.Random(5)
        a = [combat.melee(attacker, plain, zone=246, rng=rng).damage for _ in range(1000)]
        rng = random.Random(5)
        b = [combat.melee(attacker, parrying, zone=246, rng=rng) for _ in range(1000)]
        parries = sum(1 for hit in b if hit.defended == "parry")
        self.assertGreater(parries, 150)   # ~25%
        self.assertLess(sum(hit.damage for hit in b), sum(a) * 0.9)

    def test_guard_needs_fists(self):
        attacker = stats.build_monster(99).fighter
        attacker.skill_value = 100
        unarmed = self.defender(guard_skill=424, weapon_dmg=0, h2h=True)
        armed = self.defender(guard_skill=424, weapon_dmg=150)
        rng = random.Random(7)
        guarded = [combat.melee(attacker, unarmed, zone=246, rng=rng) for _ in range(200)]
        rng = random.Random(7)
        armed_hits = [combat.melee(attacker, armed, zone=246, rng=rng) for _ in range(200)]
        self.assertTrue(any(hit.defended == "guard" for hit in guarded))
        self.assertFalse(any(hit.defended == "guard" for hit in armed_hits))

    def test_monsters_do_not_parry(self):
        attacker = self.defender()
        mob = stats.build_monster(99).fighter
        rng = random.Random(3)
        for _ in range(50):
            self.assertIsNone(combat.melee(attacker, mob, zone=246, rng=rng).defended)


class BaseStatsTest(unittest.TestCase):
    def test_hume_warrior_sixty_nine(self):
        values = base_stats.base_stats(1, 1, 99)
        self.assertEqual(values["str"], 82)
        self.assertGreater(values["str"], values["mnd"])

    def test_subjob_adds(self):
        without = base_stats.base_stats(1, 1, 99, 0, 0)
        with_sub = base_stats.base_stats(1, 1, 99, 6, 49)
        self.assertGreaterEqual(with_sub["str"], without["str"])
        self.assertGreater(with_sub["dex"], without["dex"])

    def test_base_hp_and_mp(self):
        # A level 1 Hume Warrior has 34 HP and no MP; Tarutaru Black Mages have the most MP.
        self.assertEqual(base_stats.base_hp(1, 1, 1), 34)
        self.assertEqual(base_stats.base_mp(1, 1, 1), 0)
        self.assertGreater(base_stats.base_mp(5, 4, 99), 900)
        self.assertEqual(base_stats.base_mp(1, 1, 99), 0)

    def test_a_subjob_brings_mp_to_a_job_without_one(self):
        # Beastmaster has no MP of its own; /BLM gives it a share at the subjob's level.
        self.assertEqual(base_stats.base_mp(1, 9, 99), 0)
        self.assertGreater(base_stats.base_mp(1, 9, 99, 4, 49), 0)

    def test_races_differ(self):
        hume = base_stats.base_stats(1, 1, 99)
        elvaan = base_stats.base_stats(3, 1, 99)
        taru = base_stats.base_stats(5, 1, 99)
        self.assertGreater(elvaan["str"], hume["str"])
        self.assertGreater(taru["int"], hume["int"])


class SheetTest(unittest.TestCase):
    def test_attack_sums_gear_str_and_skill(self):
        char = {"race": 1, "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0}
        weapon = stats.Weapon(skill=9, dmg=150, delay=450)
        sheet = stats.build_character(char, {mod.ATT: 100}, {9: 424}, weapon)
        expected = 8 + 100 + int(sheet.attributes["str"] * 0.75) + 424
        self.assertEqual(sheet.attack, expected)

    def test_two_handed_uses_full_strength(self):
        char = {"race": 1, "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0}
        one_hand = stats.build_character(char, {}, {3: 424}, stats.Weapon(skill=3, dmg=150))
        two_hand = stats.build_character(char, {}, {4: 424}, stats.Weapon(skill=4, dmg=150))
        self.assertGreater(two_hand.attack, one_hand.attack)

    def test_defense_uses_vit_and_level(self):
        char = {"race": 1, "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0}
        sheet = stats.build_character(char, {}, {})
        expected = 8 + int(sheet.attributes["vit"] * 1.5) + 99 + 18 + (99 - 89) // 2
        self.assertEqual(sheet.defense, expected)

    def test_max_hp_adds_gear(self):
        char = {"race": 1, "main_job": 1, "main_level": 99, "sub_job": 0, "sub_level": 0}
        bare = stats.build_character(char, {}, {})
        geared = stats.build_character(char, {mod.HP: 250, mod.MP: 40}, {})
        self.assertEqual(bare.max_hp, base_stats.base_hp(1, 1, 99))
        self.assertEqual(geared.max_hp, bare.max_hp + 250)
        self.assertEqual(geared.max_mp, bare.max_mp + 40)

    def test_weapon_delay_becomes_milliseconds(self):
        sheet = stats.Sheet(fighter=stats.build_monster(1).fighter, delay=450)
        self.assertEqual(sheet.attack_delay_ms, 7500)

    def test_haste_speeds_the_swing(self):
        slow = stats.Sheet(fighter=stats.build_monster(1).fighter, delay=450)
        fast = stats.Sheet(fighter=stats.build_monster(1).fighter, delay=450, haste=0.25)
        self.assertEqual(fast.attack_delay_ms, int(450 * 1000 / 60 * 0.75))

    def test_monster_stats_grow_with_level(self):
        low = stats.build_monster(10).fighter
        high = stats.build_monster(99).fighter
        self.assertGreater(high.attack, low.attack)
        self.assertGreater(high.defense, low.defense)
        self.assertGreater(high.weapon_dmg, low.weapon_dmg)


class DualWieldTest(unittest.TestCase):
    """Two one-handed weapons plus the trait make an off-hand swing and a faster round."""

    char = {"race": 1, "main_job": 13, "main_level": 99, "sub_job": 0, "sub_level": 0}
    main = stats.Weapon(skill=9, dmg=150, delay=227)
    sub = stats.Weapon(skill=9, dmg=120, delay=190)

    def test_dual_wield_builds_an_off_hand_fighter(self):
        sheet = stats.build_character(
            self.char, {mod.DUAL_WIELD: 35}, {9: 424}, self.main, self.sub)
        self.assertTrue(sheet.dual_wield)
        self.assertEqual(sheet.sub_weapon, self.sub)
        self.assertIsNotNone(sheet.sub_fighter)
        self.assertTrue(sheet.sub_fighter.off_hand)
        self.assertEqual(sheet.sub_fighter.weapon_dmg, 120)
        # (227 + 190) * 65% / 2, the per-hand delay of a dual-wielded attack round.
        self.assertEqual(sheet.delay, int((227 + 190) * 0.65 / 2))
        self.assertEqual(sheet.attack_delay_ms, int(sheet.delay * 1000 / 60))
        # TP is per weapon, not the round's averaged delay: 227 -> 73 and 190 -> 61.
        self.assertEqual(sheet.tp_per_hit(), 42)
        self.assertEqual(sheet.tp_per_hit(off_hand=True), 40)

    def test_off_hand_uses_the_half_strength_multiplier_and_its_own_skill(self):
        dagger = stats.Weapon(skill=2, dmg=120, delay=190)
        sheet = stats.build_character(
            self.char, {mod.DUAL_WIELD: 35}, {9: 424, 2: 200}, self.main, dagger)
        expected = 8 + int(sheet.attributes["str"] * 0.5) + 200
        self.assertEqual(sheet.sub_fighter.attack, expected)
        self.assertEqual(sheet.sub_fighter.weapon_skill, 2)
        # The off hand uses the dagger's skill, so its Accuracy is lower than the katana's.
        self.assertLess(sheet.sub_fighter.accuracy, sheet.fighter.accuracy)

    def test_no_off_hand_without_the_dual_wield_trait(self):
        sheet = stats.build_character(
            self.char, {}, {9: 424}, self.main, self.sub)
        self.assertFalse(sheet.dual_wield)
        self.assertIsNone(sheet.sub_fighter)
        self.assertEqual(sheet.delay, 227)

    def test_a_shield_is_not_an_off_hand_weapon(self):
        shield = stats.Weapon(item_id=12345)
        sheet = stats.build_character(
            self.char, {mod.DUAL_WIELD: 35}, {9: 424}, self.main, shield)
        self.assertFalse(sheet.dual_wield)
        self.assertIsNone(sheet.sub_fighter)
        self.assertEqual(sheet.delay, 227)

    def test_a_two_handed_main_weapon_never_dual_wields(self):
        great_sword = stats.Weapon(skill=4, dmg=300, delay=450)
        sheet = stats.build_character(
            self.char, {mod.DUAL_WIELD: 35}, {4: 424, 9: 424}, great_sword, self.sub)
        self.assertFalse(sheet.dual_wield)
        self.assertIsNone(sheet.sub_fighter)
        self.assertEqual(sheet.delay, 450)

    def test_gear_dual_wield_without_the_trait_does_not_enable_the_off_hand(self):
        sheet = stats.build_character(
            self.char, {mod.DUAL_WIELD: 10}, {9: 424}, self.main, self.sub,
            dual_wield=False)
        self.assertFalse(sheet.dual_wield)
        self.assertIsNone(sheet.sub_fighter)
        self.assertEqual(sheet.delay, 227)


class TpReturnTest(unittest.TestCase):
    """The current retail TP curve and Dual Wield's per-hand delay."""

    def test_curve_breakpoints(self):
        self.assertEqual(combat.tp_return(180), 61)
        self.assertEqual(combat.tp_return(540), 149)
        self.assertEqual(combat.tp_return(720), 161)
        self.assertEqual(combat.tp_return(900), 173)

    def test_dual_wield_halves_each_weapons_own_delay(self):
        self.assertEqual(combat.tp_delay(227, dual_wield=35), 73)
        self.assertEqual(combat.tp_delay(190, dual_wield=35), 61)
        self.assertEqual(combat.tp_delay(227), 227)

    def test_store_tp_applies_after_the_curve(self):
        self.assertEqual(combat.tp_return(227), 72)
        self.assertEqual(combat.tp_gain(combat.tp_return(227), 20), 86)


class MultiAttackTest(unittest.TestCase):
    """Double, Triple and Quadruple Attack: one roll per hand, highest tier wins."""

    def test_quadruple_beats_triple_and_double(self):
        rng = random.Random(1)
        self.assertEqual(combat.multi_attack_hits(
            rng, double=100, triple=100, quadruple=100), 4)

    def test_triple_is_checked_before_double(self):
        rng = random.Random(1)
        # Quadruple at 0 is skipped, Triple at 100 always procs, Double never rolls.
        self.assertEqual(combat.multi_attack_hits(
            rng, double=100, triple=100, quadruple=0), 3)

    def test_double_is_the_last_tier(self):
        rng = random.Random(1)
        self.assertEqual(combat.multi_attack_hits(
            rng, double=100, triple=0, quadruple=0), 2)
        self.assertEqual(combat.multi_attack_hits(
            rng, double=0, triple=0, quadruple=0), 1)

    def test_rates_clamp_and_negative_gear_never_procs(self):
        rng = random.Random(1)
        self.assertEqual(combat.multi_attack_hits(
            rng, double=250, triple=0, quadruple=0), 2)
        self.assertEqual(combat.multi_attack_hits(
            rng, double=-25, triple=0, quadruple=0), 1)

    def test_a_failed_higher_tier_falls_through_to_double(self):
        class Rolls:
            """QA 50% and TA 50% both fail, then DA 100% procs."""

            def __init__(self):
                self.values = [0.99, 0.99, 0.0]

            def random(self):
                return self.values.pop(0)

        self.assertEqual(combat.multi_attack_hits(
            Rolls(), double=100, triple=50, quadruple=50), 2)

    def test_round_cap_is_eight_hits(self):
        self.assertEqual(combat.MAX_ATTACKS_PER_ROUND, 8)


class MeleeTest(unittest.TestCase):
    def test_damage_taken_gear_reduces_incoming_damage(self):
        mob = stats.build_monster(99).fighter
        bare = stats.build_character(
            {"race": 1, "main_job": 1, "main_level": 99}, {}, {}, stats.Weapon(skill=9, dmg=150))
        tanky = stats.build_character(
            {"race": 1, "main_job": 1, "main_level": 99}, {mod.DMGPHYS: -5000}, {},
            stats.Weapon(skill=9, dmg=150))

        def average(defender, seed=11):
            rng = random.Random(seed)
            hits = [combat.melee(mob, defender.fighter, zone=246, rng=rng) for _ in range(300)]
            landed = [h.damage for h in hits if not h.missed]
            return sum(landed) / max(1, len(landed))

        self.assertLess(average(tanky), average(bare) * 0.6)

    def test_a_miss_does_no_damage(self):
        weak = stats.build_character(
            {"race": 1, "main_job": 1, "main_level": 1}, {}, {},
            stats.Weapon(skill=3, dmg=1))
        strong = stats.build_monster(99).fighter
        rng = random.Random(3)
        for _ in range(50):
            hit = combat.melee(weak.fighter, strong, zone=246, rng=rng)
            if hit.missed:
                self.assertEqual(hit.damage, 0)

    def test_ftp_scales_a_weapon_skill(self):
        char = {"race": 1, "main_job": 1, "main_level": 99}
        attacker = stats.build_character(char, {}, {9: 424}, stats.Weapon(skill=9, dmg=150))
        mob = stats.build_monster(90).fighter
        rng = random.Random(5)
        plain = combat.melee(attacker.fighter, mob, zone=246, rng=random.Random(5))
        rng = random.Random(5)
        scaled = combat.melee(attacker.fighter, mob, zone=246, rng=rng, ftp=2.0)
        if not plain.missed and not scaled.missed:
            self.assertGreater(scaled.damage, plain.damage)


if __name__ == "__main__":
    unittest.main()
