"""Job-point gifts, passive category stats and the flat duration layer."""
from __future__ import annotations

import unittest

from fanxi_server.game import effects, job_points, modifiers as mod, skills


class JobPointDataTest(unittest.TestCase):
    def test_every_job_has_the_full_table(self):
        for job_id in range(1, 23):
            job = job_points._job(job_id)
            self.assertEqual(len(job["categories"]), 10, job_points.JOB_KEYS[job_id])
            self.assertEqual(len(job["gifts"]), 61, job_points.JOB_KEYS[job_id])

    def test_audit_covers_all_jobs(self):
        audit = job_points.audit()
        self.assertEqual(len(audit), 22)
        self.assertEqual(audit["sch"]["categories"], 10)
        self.assertEqual(audit["sch"]["gift_rows"], 61)


class JobPointGiftTest(unittest.TestCase):
    def test_scholar_gift_totals(self):
        totals = job_points.gift_totals(20)
        self.assertEqual(totals["mods"], {
            mod.MDEF: 22,
            mod.MATT: 36,
            mod.MEVA: 42,
            mod.MACC: 42,
            mod.MAGIC_BURST_BONUS_CAPPED: 13,
            # Every job's ★Master! gift cuts the one-hour recast by 15 minutes.
            mod.ONE_HOUR_RECAST: 15,
        })
        self.assertEqual(totals["skills"], {
            33: 36,  # Healing Magic
            34: 36,  # Enhancing Magic
            36: 36,  # Elemental Magic
            37: 36,  # Dark Magic
        })

    def test_warrior_gift_totals(self):
        totals = job_points.gift_totals(1)
        self.assertEqual(totals["mods"][mod.ATT], 70)
        self.assertEqual(totals["mods"][mod.RATT], 70)
        self.assertEqual(totals["mods"][mod.DEF], 70)
        self.assertEqual(totals["mods"][mod.ACC], 36)
        self.assertEqual(totals["mods"][mod.RACC], 36)
        self.assertEqual(totals["mods"][mod.EVA], 36)
        self.assertEqual(totals["mods"][mod.MACC], 36)
        self.assertEqual(totals["mods"][mod.MEVA], 36)
        self.assertEqual(totals["mods"][mod.DOUBLE_ATTACK], 7)
        self.assertEqual(totals["mods"][mod.CRIT_HIT_RATE], 1000)  # 10% in hundredths
        self.assertEqual(totals["mods"][mod.CRIT_DMG_INCREASE], 10)

    def test_white_mage_regen_gift_is_flat_potency(self):
        totals = job_points.gift_totals(3)
        self.assertEqual(totals["mods"][mod.REGEN_POTENCY], 5)
        self.assertEqual(totals["mods"][mod.CURE_POTENCY], 23)
        self.assertEqual(totals["mods"][mod.FASTCAST], 8)

    def test_bard_song_cast_gift_is_song_only(self):
        totals = job_points.gift_totals(10)["mods"]
        self.assertEqual(totals[mod.SONG_SPELLCASTING_TIME], 5)
        self.assertNotIn(mod.FASTCAST, totals)

    def test_red_mage_enspell_and_master_gifts(self):
        """RDM's En-spell gifts are flat damage per hit, not a stat row to ignore."""
        totals = job_points.gift_totals(5)
        # 5 + 5 + 6 + 7 from the four "En"-spell gifts.
        self.assertEqual(totals["mods"][mod.ENSPELL_DMG_BONUS], 23)
        self.assertEqual(totals["mods"][mod.ONE_HOUR_RECAST], 15)
        # Every RDM gift row is now either a modifier, a skill or a known flag.
        self.assertEqual(totals["unclassified"], [])
        self.assertEqual(totals["flags"] & {"new_spells", "master"},
                         {"new_spells", "master"})
        self.assertEqual(totals["skills"], {34: 36, 35: 36})
        # Fanxi has no per-character spell table: the gift table itself is the
        # authority for which job learns the spell.
        grants = job_points.spell_grants(5)
        self.assertEqual(grants["Fire V"], 100)
        self.assertEqual(grants["Addle II"], 550)
        self.assertEqual(grants["Refresh III"], 1200)
        self.assertTrue(job_points.is_job_point_spell("Temper II"))
        self.assertFalse(job_points.is_job_point_spell("Cure"))

    def test_combat_mods_merge_gifts_and_passive_categories(self):
        self.assertEqual(job_points.combat_mods(20), job_points.gift_totals(20)["mods"])
        white_mage = dict(job_points.gift_totals(3)["mods"])
        white_mage[mod.MACC] += 20
        white_mage[mod.MDEF] += 40
        white_mage[mod.REGEN_DURATION] = 60
        self.assertEqual(job_points.combat_mods(3), white_mage)

    def test_skill_bonus_is_main_job_only(self):
        bonus = job_points.skill_bonus(20)
        self.assertEqual(bonus[34], 36)
        caps = skills.caps_for(20, 99, 0, 0, bonus)
        self.assertEqual(caps[34], (skills.cap_for(34, 20, 99) or 0) + 36)
        # No bonus argument keeps the old job-cap result.
        self.assertEqual(skills.caps_for(20, 99, 0, 0)[34], caps[34] - 36)


class JobPointCategoryTest(unittest.TestCase):
    def test_white_mage_passive_categories(self):
        self.assertEqual(job_points.category_mods(3), {
            mod.MACC: 20,
            mod.REGEN_DURATION: 60,
            mod.MDEF: 40,
        })

    def test_red_mage_passive_categories(self):
        self.assertEqual(job_points.category_mods(5), {
            mod.MACC: 20,
            mod.MATT: 20,
            mod.ENF_MAG_DURATION_FLAT: 20,
            mod.ENH_MAGIC_DURATION_FLAT: 20,
        })

    def test_black_mage_passive_categories(self):
        self.assertEqual(job_points.category_mods(4), {
            mod.MACC: 20,
            mod.MAGIC_DAMAGE: 20,
            mod.MAGIC_BURST_BONUS_CAPPED: 20,
            mod.ENMITY: -20,
        })

    def test_geomancer_passive_categories(self):
        self.assertEqual(job_points.category_mods(21), {
            mod.MATT: 20,
            mod.MACC: 20,
        })

    def test_ninja_passive_categories(self):
        self.assertEqual(job_points.category_mods(13), {
            mod.MACC: 20,
            mod.NINJUTSU_FASTCAST: 20,
            mod.NINJUTSU_MAGIC_DAMAGE: 40,
            mod.COUNTER: 20,
        })

    def test_puppetmaster_martial_arts(self):
        self.assertEqual(job_points.category_mods(18), {mod.MARTIAL_ARTS: 40})

    def test_conditional_categories_are_not_applied_silently(self):
        # Scholar's Light Arts is handled by the duration formula, not as a permanent
        # stat; the audit must still list it as needing an ability hook.
        self.assertEqual(job_points.category_mods(20), {})
        names = [row["category"] for row in job_points.missing_categories(20)]
        self.assertNotIn("Light Arts Effect", names)
        self.assertNotIn("Dark Arts Effect", names)
        self.assertNotIn("Stratagem Effect IV", names)


class JobPointDurationTest(unittest.TestCase):
    def test_enhancing_flat_job_point_seconds(self):
        spec = effects.for_spell("Regen V")
        self.assertEqual(
            effects.buff_duration(
                spec, main_job=20, main_level=99, mods={mod.ENH_MAGIC_DURATION_FLAT: 20},
                light_arts=True, enhancing=True),
            128.0)  # 60 + 48 + 20

    def test_scholar_stratagem_conditionals(self):
        self.assertEqual(
            job_points.conditional_mods(20, {effects.PENURY}),
            {mod.MACC: 20})
        self.assertEqual(
            job_points.conditional_mods(20, {effects.PARSIMONY}),
            {mod.MACC: 20})
        self.assertEqual(
            job_points.conditional_mods(20, {effects.CELERITY}),
            {mod.FASTCAST: 20})
        self.assertEqual(
            job_points.conditional_mods(20, {effects.RAPTURE}),
            {mod.MAGIC_DAMAGE: 40})
        self.assertEqual(job_points.conditional_mods(20, set()), {})
        self.assertEqual(job_points.conditional_mods(1, {effects.PENURY}), {})

    def test_non_scholar_ability_conditionals(self):
        self.assertEqual(job_points.conditional_mods(1, {effects.MIGHTY_STRIKES}),
                         {mod.ACC: 40, mod.RACC: 40})
        self.assertEqual(job_points.conditional_mods(1, {effects.BERSERK}),
                         {mod.ATT: 40, mod.RATT: 40})
        self.assertEqual(job_points.conditional_mods(2, {effects.DODGE}), {mod.EVA: 40})
        self.assertEqual(job_points.conditional_mods(3, {effects.ASYLUM}), {mod.MEVA: 80})
        self.assertEqual(job_points.conditional_mods(3, {effects.AFFLATUS_SOLACE}),
                         {mod.CURE_POTENCY: 40})
        self.assertEqual(job_points.conditional_mods(4, {effects.MANAFONT}),
                         {mod.MAGIC_DAMAGE: 60})
        self.assertEqual(job_points.conditional_mods(5, {effects.STYMIE}),
                         {mod.ENF_MAG_DURATION_FLAT: 20})
        self.assertEqual(job_points.conditional_mods(5, {effects.SABOTEUR}),
                         {mod.MACC: 40})

    def test_generic_ability_rules(self):
        rng = job_points.category_generic_rule(11, "Sharpshot Effect")
        self.assertEqual(rng["status"], effects.SHARPSHOT)
        self.assertEqual(rng["mods"], {mod.RATT: 40})
        sam = job_points.category_generic_rule(12, "Hasso Effect")
        self.assertEqual(sam["mods"], {mod.STR: 20})
        nin = job_points.category_generic_rule(13, "Innin Effect")
        self.assertEqual(nin["mods"], {mod.ACC: 20})
        brd = job_points.category_generic_rule(10, "Pianissimo Effect")
        self.assertEqual(brd["mods"], {mod.FASTCAST: 40})
        pld = job_points.category_generic_rule(7, "Holy Circle Effect")
        self.assertEqual(pld["mods"], {mod.DMG: -2000})
        run = job_points.ability_effect(366)  # Vallation
        self.assertEqual(run["status"], effects.VALLATION)
        self.assertGreater(run["duration"], 60.0)

    def test_more_ability_conditionals(self):
        self.assertEqual(job_points.conditional_mods(7, {effects.ENLIGHT}), {mod.ACC: 20})
        self.assertEqual(job_points.conditional_mods(8, {effects.ENDARK}),
                         {mod.ATT: 20, mod.RATT: 20, mod.ACC: 20})
        self.assertEqual(job_points.conditional_mods(16, {effects.AZURE_LORE}),
                         {mod.MAGIC_DAMAGE: 20})
        self.assertEqual(job_points.conditional_mods(14, {effects.SPIRIT_SURGE}),
                         {mod.DMG_RATING: 20})
        self.assertEqual(job_points.gift_totals(20)["mods"][mod.MAGIC_BURST_BONUS_CAPPED], 13)

    def test_more_melee_conditionals(self):
        self.assertEqual(job_points.conditional_mods(2, {effects.PERFECT_COUNTER}),
                         {mod.VIT: 20})
        self.assertEqual(job_points.conditional_mods(2, {effects.FOOTWORK}), {mod.ATT: 20})
        self.assertEqual(job_points.conditional_mods(2, {effects.COUNTERSTANCE}),
                         {mod.DEX: 40})
        self.assertEqual(job_points.conditional_mods(12, {effects.KONZEN_ITTAI}),
                         {mod.SKILLCHAIN_BONUS: 20})

    def test_bard_support_conditionals(self):
        self.assertEqual(job_points.conditional_mods(10, {effects.SOUL_VOICE}),
                         {mod.FASTCAST: 40})
        self.assertEqual(job_points.conditional_mods(10, {effects.PIANISSIMO}),
                         {mod.FASTCAST: 40})
        # Song Accuracy Bonus is song-only (zone._cast_numbers adds it to the singing
        # skill), so the generic category modifier stays empty.
        self.assertEqual(job_points.category_mods(10), {})
        self.assertEqual(job_points.ability_effect(25)["status"], effects.SOUL_VOICE)

    def test_dancer_samba_duration(self):
        effect = effects.ABILITY_EFFECTS[189]
        self.assertEqual(effect.effect, effects.HASTE_SAMBA)
        # 90 s base + the Samba Duration row's +2 s x 20 ranks.  Drain/Aspir are 120 s
        # base and therefore 160 s at rank 20.
        self.assertEqual(effect.duration, 130.0)
        self.assertEqual(effects.ABILITY_EFFECTS[184].duration, 160.0)

    def test_special_category_totals(self):
        self.assertEqual(job_points.category_total(5, "Convert Effect"), 20)
        self.assertEqual(job_points.category_total(2, "Chakra Effect"), 200)
        self.assertEqual(job_points.category_total(19, "Waltz Potency"), 40)
        self.assertEqual(job_points.category_total(12, "Meditate Effect"), 100)
        self.assertEqual(job_points.category_total(20, "Tabula Rasa Effect"), 40)
        self.assertEqual(job_points.category_total(20, "Missing"), 0)

    def test_dark_arts_helix_duration(self):
        self.assertEqual(effects.helix_duration(99, dark_arts=False, jp_rank=20), 90.0)
        self.assertEqual(effects.helix_duration(99, dark_arts=True, jp_rank=20), 150.0)
        self.assertEqual(effects.helix_duration(99, dark_arts=True, jp_rank=0), 90.0)

    def test_enfeebling_flat_job_point_seconds(self):
        spec = effects.for_spell("Slow")
        base = effects.debuff_duration(spec, skill=35, mods={})
        self.assertEqual(
            effects.debuff_duration(
                spec, skill=35, mods={mod.ENF_MAG_DURATION_FLAT: 20}),
            base + 20)


if __name__ == "__main__":
    unittest.main()
