"""The client's merit point table: ids, category caps and upgrade costs.

The ids are the merit name-DAT indexes the client's 0x08C packet uses; the
categories, caps and cost ladders are LandSandBoat's data/merits.yaml.  A merit
is worth `value` of its stat per upgrade; `max` is the length of its cost ladder.
"""
from __future__ import annotations

# category id -> total upgrades allowed across the category
CATEGORY_MAX = {
    0x0040: 75,  # hp_mp
    0x0080: 105,  # attributes
    0x00c0: 152,  # combat_skills
    0x0100: 112,  # magic_skills
    0x0140: 10,  # others
    0x0680: 15,  # weapon_skills
    0x0180: 10,  # war_group_1
    0x0800: 10,  # war_group_2
    0x01c0: 10,  # mnk_group_1
    0x0840: 10,  # mnk_group_2
    0x0200: 10,  # whm_group_1
    0x0880: 10,  # whm_group_2
    0x0240: 10,  # blm_group_1
    0x08c0: 10,  # blm_group_2
    0x0280: 10,  # rdm_group_1
    0x0900: 10,  # rdm_group_2
    0x02c0: 10,  # thf_group_1
    0x0940: 10,  # thf_group_2
    0x0300: 10,  # pld_group_1
    0x0980: 10,  # pld_group_2
    0x0340: 10,  # drk_group_1
    0x09c0: 10,  # drk_group_2
    0x0380: 10,  # bst_group_1
    0x0a00: 10,  # bst_group_2
    0x03c0: 10,  # brd_group_1
    0x0a40: 10,  # brd_group_2
    0x0400: 10,  # rng_group_1
    0x0a80: 10,  # rng_group_2
    0x0440: 10,  # sam_group_1
    0x0ac0: 10,  # sam_group_2
    0x0480: 10,  # nin_group_1
    0x0b00: 10,  # nin_group_2
    0x04c0: 10,  # drg_group_1
    0x0b40: 10,  # drg_group_2
    0x0500: 10,  # smn_group_1
    0x0b80: 10,  # smn_group_2
    0x0540: 10,  # blu_group_1
    0x0bc0: 10,  # blu_group_2
    0x0580: 10,  # cor_group_1
    0x0c00: 10,  # cor_group_2
    0x05c0: 10,  # pup_group_1
    0x0c40: 10,  # pup_group_2
    0x0600: 10,  # dnc_group_1
    0x0c80: 10,  # dnc_group_2
    0x0640: 10,  # sch_group_1
    0x0cc0: 10,  # sch_group_2
    0x06c0: 10,  # geo_group_1
    0x0d40: 10,  # geo_group_2
    0x0700: 10,  # run_group_1
    0x0d80: 10,  # run_group_2
}

# cost of each successive upgrade
COSTS = {
    'hp_mp': (1, 2, 3, 4, 5, 5, 5, 5, 5, 7, 7, 7, 9, 9, 9),
    'attributes': (3, 6, 9, 9, 9, 12, 12, 12, 12, 15, 15, 15, 15, 18, 18),
    'combat_skills': (1, 2, 3, 3, 3, 3, 3, 3),
    'defensive_skills': (1, 2, 3, 3, 3, 3, 3, 3),
    'magic_skills': (1, 2, 3, 3, 3, 3, 3, 3),
    'others': (1, 2, 3, 4, 5),
    'job_group_1': (1, 2, 3, 4, 5),
    'job_group_2': (3, 4, 5, 5, 5),
    'weapon_skills': (20, 22, 24, 27, 30),
    'max_merits': (1, 3, 5, 7, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 51, 51, 51, 51, 51, 51, 51, 51, 51),
}

# merit id -> (category id, cost key, max upgrades, value)
MERITS = {
    0x0040: (0x0040, 'hp_mp', 15, 10),  # hp_mp / max_hp
    0x0042: (0x0040, 'hp_mp', 15, 10),  # hp_mp / max_mp
    0x0044: (0x0040, 'max_merits', 45, 1),  # hp_mp / max_merit
    0x0080: (0x0080, 'attributes', 15, 1),  # attributes / str
    0x0082: (0x0080, 'attributes', 15, 1),  # attributes / dex
    0x0084: (0x0080, 'attributes', 15, 1),  # attributes / vit
    0x0086: (0x0080, 'attributes', 15, 1),  # attributes / agi
    0x0088: (0x0080, 'attributes', 15, 1),  # attributes / int
    0x008a: (0x0080, 'attributes', 15, 1),  # attributes / mnd
    0x008c: (0x0080, 'attributes', 15, 1),  # attributes / chr
    0x00c0: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / hand_to_hand_skill
    0x00c2: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / dagger_skill
    0x00c4: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / sword_skill
    0x00c6: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / great_sword_skill
    0x00c8: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / axe_skill
    0x00ca: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / great_axe_skill
    0x00cc: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / scythe_skill
    0x00ce: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / polearm_skill
    0x00d0: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / katana_skill
    0x00d2: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / great_katana_skill
    0x00d4: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / club_skill
    0x00d6: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / staff_skill
    0x00d8: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / archery_skill
    0x00da: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / marksmanship_skill
    0x00dc: (0x00c0, 'combat_skills', 8, 2),  # combat_skills / throwing_skill
    0x00de: (0x00c0, 'defensive_skills', 8, 2),  # combat_skills / guarding_skill
    0x00e0: (0x00c0, 'defensive_skills', 8, 2),  # combat_skills / evasion_skill
    0x00e2: (0x00c0, 'defensive_skills', 8, 2),  # combat_skills / shield_skill
    0x00e4: (0x00c0, 'defensive_skills', 8, 2),  # combat_skills / parrying_skill
    0x0100: (0x0100, 'magic_skills', 8, 2),  # magic_skills / divine_magic_skill
    0x0102: (0x0100, 'magic_skills', 8, 2),  # magic_skills / healing_magic_skill
    0x0104: (0x0100, 'magic_skills', 8, 2),  # magic_skills / enhancing_magic_skill
    0x0106: (0x0100, 'magic_skills', 8, 2),  # magic_skills / enfeebling_magic_skill
    0x0108: (0x0100, 'magic_skills', 8, 2),  # magic_skills / elemental_magic_skill
    0x010a: (0x0100, 'magic_skills', 8, 2),  # magic_skills / dark_magic_skill
    0x010c: (0x0100, 'magic_skills', 8, 2),  # magic_skills / summoning_magic_skill
    0x010e: (0x0100, 'magic_skills', 8, 2),  # magic_skills / ninjutsu_skill
    0x0110: (0x0100, 'magic_skills', 8, 2),  # magic_skills / singing_skill
    0x0112: (0x0100, 'magic_skills', 8, 2),  # magic_skills / string_instrument_skill
    0x0114: (0x0100, 'magic_skills', 8, 2),  # magic_skills / wind_instrument_skill
    0x0116: (0x0100, 'magic_skills', 8, 2),  # magic_skills / blue_magic_skill
    0x0118: (0x0100, 'magic_skills', 8, 2),  # magic_skills / geomancy_skill
    0x011a: (0x0100, 'magic_skills', 8, 2),  # magic_skills / handbell_skill
    0x0140: (0x0140, 'others', 5, 1),  # others / enmity_increase
    0x0142: (0x0140, 'others', 5, 1),  # others / enmity_decrease
    0x0144: (0x0140, 'others', 5, 1),  # others / crit_hit_rate
    0x0146: (0x0140, 'others', 5, 1),  # others / enemy_crit_rate
    0x0148: (0x0140, 'others', 5, 2),  # others / spell_interruption_rate
    0x0680: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / shijin_spiral
    0x0682: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / exenterator
    0x0684: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / requiescat
    0x0686: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / resolution
    0x0688: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / ruinator
    0x068a: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / upheaval
    0x068c: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / entropy
    0x068e: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / stardiver
    0x0690: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / blade_shun
    0x0692: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / tachi_shoha
    0x0694: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / realmrazer
    0x0696: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / shattersoul
    0x0698: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / apex_arrow
    0x069a: (0x0680, 'weapon_skills', 5, 3),  # weapon_skills / last_stand
    0x0180: (0x0180, 'job_group_1', 5, 10),  # war_group_1 / berserk_recast
    0x0182: (0x0180, 'job_group_1', 5, 6),  # war_group_1 / defender_recast
    0x0184: (0x0180, 'job_group_1', 5, 10),  # war_group_1 / warcry_recast
    0x0186: (0x0180, 'job_group_1', 5, 10),  # war_group_1 / aggressor_recast
    0x0188: (0x0180, 'job_group_1', 5, 1),  # war_group_1 / double_attack_rate
    0x0800: (0x0800, 'job_group_2', 5, 5),  # war_group_2 / warriors_charge
    0x0802: (0x0800, 'job_group_2', 5, 15),  # war_group_2 / tomahawk
    0x0804: (0x0800, 'job_group_2', 5, 100),  # war_group_2 / savagery
    0x0806: (0x0800, 'job_group_2', 5, 4),  # war_group_2 / aggressive_aim
    0x01c0: (0x01c0, 'job_group_1', 5, 4),  # mnk_group_1 / focus_recast
    0x01c2: (0x01c0, 'job_group_1', 5, 4),  # mnk_group_1 / dodge_recast
    0x01c4: (0x01c0, 'job_group_1', 5, 6),  # mnk_group_1 / chakra_recast
    0x01c6: (0x01c0, 'job_group_1', 5, 1),  # mnk_group_1 / counter_rate
    0x01c8: (0x01c0, 'job_group_1', 5, 1),  # mnk_group_1 / kick_attack_rate
    0x0840: (0x0840, 'job_group_2', 5, 4),  # mnk_group_2 / mantra
    0x0842: (0x0840, 'job_group_2', 5, 5),  # mnk_group_2 / formless_strikes
    0x0844: (0x0840, 'job_group_2', 5, 24),  # mnk_group_2 / invigorate
    0x0846: (0x0840, 'job_group_2', 5, 20),  # mnk_group_2 / penance
    0x0200: (0x0200, 'job_group_1', 5, 20),  # whm_group_1 / divine_seal_recast
    0x0202: (0x0200, 'job_group_1', 5, 4),  # whm_group_1 / cure_cast_time
    0x0204: (0x0200, 'job_group_1', 5, 2),  # whm_group_1 / bar_spell_effect
    0x0206: (0x0200, 'job_group_1', 5, 2),  # whm_group_1 / banish_effect
    0x0208: (0x0200, 'job_group_1', 5, 1),  # whm_group_1 / regen_effect
    0x0880: (0x0880, 'job_group_2', 5, 5),  # whm_group_2 / martyr
    0x0882: (0x0880, 'job_group_2', 5, 5),  # whm_group_2 / devotion
    0x0888: (0x0880, 'job_group_2', 5, 2),  # whm_group_2 / animus_solace
    0x088a: (0x0880, 'job_group_2', 5, 5),  # whm_group_2 / animus_misery
    0x0240: (0x0240, 'job_group_1', 5, 20),  # blm_group_1 / elemental_seal_recast
    0x0242: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / fire_magic_potency
    0x0244: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / ice_magic_potency
    0x0246: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / wind_magic_potency
    0x0248: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / earth_magic_potency
    0x024a: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / lightning_magic_potency
    0x024c: (0x0240, 'job_group_1', 5, 2),  # blm_group_1 / water_magic_potency
    0x08cc: (0x08c0, 'job_group_2', 5, 3),  # blm_group_2 / ancient_magic_atk_bonus
    0x08ce: (0x08c0, 'job_group_2', 5, 3),  # blm_group_2 / ancient_magic_burst_dmg
    0x08d0: (0x08c0, 'job_group_2', 5, 5),  # blm_group_2 / elemental_magic_accuracy
    0x08d2: (0x08c0, 'job_group_2', 5, 12),  # blm_group_2 / elemental_debuff_duration
    0x08d4: (0x08c0, 'job_group_2', 5, 1),  # blm_group_2 / elemental_debuff_effect
    0x08d6: (0x08c0, 'job_group_2', 5, 4),  # blm_group_2 / aspir_absorption_amount
    0x0280: (0x0280, 'job_group_1', 5, 20),  # rdm_group_1 / convert_recast
    0x0282: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / fire_magic_accuracy
    0x0284: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / ice_magic_accuracy
    0x0286: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / wind_magic_accuracy
    0x0288: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / earth_magic_accuracy
    0x028a: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / lightning_magic_accuracy
    0x028c: (0x0280, 'job_group_1', 5, 2),  # rdm_group_1 / water_magic_accuracy
    0x090c: (0x0900, 'job_group_2', 5, 6),  # rdm_group_2 / enfeebling_magic_duration
    0x090e: (0x0900, 'job_group_2', 5, 5),  # rdm_group_2 / magic_accuracy
    0x0910: (0x0900, 'job_group_2', 5, 6),  # rdm_group_2 / enhancing_magic_duration
    0x0912: (0x0900, 'job_group_2', 5, 3),  # rdm_group_2 / immunobreak_chance
    0x0914: (0x0900, 'job_group_2', 5, 3),  # rdm_group_2 / enspell_damage
    0x0916: (0x0900, 'job_group_2', 5, 5),  # rdm_group_2 / accuracy
    0x02c0: (0x02c0, 'job_group_1', 5, 10),  # thf_group_1 / flee_recast
    0x02c2: (0x02c0, 'job_group_1', 5, 10),  # thf_group_1 / hide_recast
    0x02c4: (0x02c0, 'job_group_1', 5, 2),  # thf_group_1 / sneak_attack_recast
    0x02c6: (0x02c0, 'job_group_1', 5, 2),  # thf_group_1 / trick_attack_recast
    0x02c8: (0x02c0, 'job_group_1', 5, 1),  # thf_group_1 / triple_attack_rate
    0x0940: (0x0940, 'job_group_2', 5, 5),  # thf_group_2 / assassins_charge
    0x0942: (0x0940, 'job_group_2', 5, 25),  # thf_group_2 / feint
    0x0944: (0x0940, 'job_group_2', 5, 20),  # thf_group_2 / aura_steal
    0x0946: (0x0940, 'job_group_2', 5, 3),  # thf_group_2 / ambush
    0x0300: (0x0300, 'job_group_1', 5, 2),  # pld_group_1 / shield_bash_recast
    0x0302: (0x0300, 'job_group_1', 5, 10),  # pld_group_1 / holy_circle_recast
    0x0304: (0x0300, 'job_group_1', 5, 10),  # pld_group_1 / sentinel_recast
    0x0306: (0x0300, 'job_group_1', 5, 4),  # pld_group_1 / cover_effect_length
    0x0308: (0x0300, 'job_group_1', 5, 10),  # pld_group_1 / rampart_recast
    0x0980: (0x0980, 'job_group_2', 5, 5),  # pld_group_2 / fealty
    0x0982: (0x0980, 'job_group_2', 5, 5),  # pld_group_2 / chivalry
    0x0984: (0x0980, 'job_group_2', 5, 19),  # pld_group_2 / iron_will
    0x0986: (0x0980, 'job_group_2', 5, 19),  # pld_group_2 / guardian
    0x0340: (0x0340, 'job_group_1', 5, 12),  # drk_group_1 / souleater_recast
    0x0342: (0x0340, 'job_group_1', 5, 10),  # drk_group_1 / arcane_circle_recast
    0x0344: (0x0340, 'job_group_1', 5, 10),  # drk_group_1 / last_resort_recast
    0x0346: (0x0340, 'job_group_1', 5, 2),  # drk_group_1 / last_resort_effect
    0x0348: (0x0340, 'job_group_1', 5, 6),  # drk_group_1 / weapon_bash_effect
    0x09c0: (0x09c0, 'job_group_2', 5, 10),  # drk_group_2 / dark_seal
    0x09c2: (0x09c0, 'job_group_2', 5, 1),  # drk_group_2 / diabolic_eye
    0x09c4: (0x09c0, 'job_group_2', 5, 10),  # drk_group_2 / muted_soul
    0x09c6: (0x09c0, 'job_group_2', 5, 200),  # drk_group_2 / desperate_blows
    0x0380: (0x0380, 'job_group_1', 5, 1),  # bst_group_1 / killer_effects
    0x0382: (0x0380, 'job_group_1', 5, 3),  # bst_group_1 / reward_recast
    0x0384: (0x0380, 'job_group_1', 5, 10),  # bst_group_1 / call_beast_recast
    0x0386: (0x0380, 'job_group_1', 5, 2),  # bst_group_1 / sic_recast
    0x0388: (0x0380, 'job_group_1', 5, 20),  # bst_group_1 / tame_recast
    0x0a00: (0x0a00, 'job_group_2', 5, 5),  # bst_group_2 / feral_howl
    0x0a02: (0x0a00, 'job_group_2', 5, 10),  # bst_group_2 / killer_instinct
    0x0a04: (0x0a00, 'job_group_2', 5, 2),  # bst_group_2 / beast_affinity
    0x0a06: (0x0a00, 'job_group_2', 5, 1),  # bst_group_2 / beast_healer
    0x03c0: (0x03c0, 'job_group_1', 5, 1),  # brd_group_1 / lullaby_recast
    0x03c2: (0x03c0, 'job_group_1', 5, 1),  # brd_group_1 / finale_recast
    0x03c4: (0x03c0, 'job_group_1', 5, 2),  # brd_group_1 / minne_effect
    0x03c6: (0x03c0, 'job_group_1', 5, 1),  # brd_group_1 / minuet_effect
    0x03c8: (0x03c0, 'job_group_1', 5, 1),  # brd_group_1 / madrigal_effect
    0x0a40: (0x0a40, 'job_group_2', 5, 25),  # brd_group_2 / nightingale
    0x0a42: (0x0a40, 'job_group_2', 5, 25),  # brd_group_2 / troubadour
    0x0a48: (0x0a40, 'job_group_2', 5, 1),  # brd_group_2 / con_anima
    0x0a4a: (0x0a40, 'job_group_2', 5, 1),  # brd_group_2 / con_brio
    0x0400: (0x0400, 'job_group_1', 5, 5),  # rng_group_1 / scavenge_effect
    0x0402: (0x0400, 'job_group_1', 5, 10),  # rng_group_1 / camouflage_recast
    0x0404: (0x0400, 'job_group_1', 5, 10),  # rng_group_1 / sharpshot_recast
    0x0406: (0x0400, 'job_group_1', 5, 6),  # rng_group_1 / unlimited_shot_recast
    0x0408: (0x0400, 'job_group_1', 5, 1),  # rng_group_1 / rapid_shot_rate
    0x0a80: (0x0a80, 'job_group_2', 5, 10),  # rng_group_2 / stealth_shot
    0x0a82: (0x0a80, 'job_group_2', 5, 5),  # rng_group_2 / flashy_shot
    0x0a84: (0x0a80, 'job_group_2', 5, 2),  # rng_group_2 / snapshot
    0x0a86: (0x0a80, 'job_group_2', 5, 5),  # rng_group_2 / recycle
    0x0440: (0x0440, 'job_group_1', 5, 2),  # sam_group_1 / third_eye_recast
    0x0442: (0x0440, 'job_group_1', 5, 10),  # sam_group_1 / warding_circle_recast
    0x0444: (0x0440, 'job_group_1', 5, 2),  # sam_group_1 / store_tp_effect
    0x0446: (0x0440, 'job_group_1', 5, 6),  # sam_group_1 / meditate_recast
    0x0448: (0x0440, 'job_group_1', 5, 1),  # sam_group_1 / zanshin_attack_rate
    0x0ac0: (0x0ac0, 'job_group_2', 5, 12),  # sam_group_2 / shikikoyo
    0x0ac2: (0x0ac0, 'job_group_2', 5, 15),  # sam_group_2 / blade_bash
    0x0ac4: (0x0ac0, 'job_group_2', 5, 30),  # sam_group_2 / ikishoten
    0x0ac6: (0x0ac0, 'job_group_2', 5, 1),  # sam_group_2 / overwhelm
    0x0480: (0x0480, 'job_group_1', 5, 1),  # nin_group_1 / subtle_blow_effect
    0x0482: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / katon_effect
    0x0484: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / hyoton_effect
    0x0486: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / huton_effect
    0x0488: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / doton_effect
    0x048a: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / raiton_effect
    0x048c: (0x0480, 'job_group_1', 5, 2),  # nin_group_1 / suiton_effect
    0x0b00: (0x0b00, 'job_group_2', 5, 1),  # nin_group_2 / sange
    0x0b02: (0x0b00, 'job_group_2', 5, 5),  # nin_group_2 / ninja_tool_expertise
    0x0b10: (0x0b00, 'job_group_2', 5, 50),  # nin_group_2 / yonin_effect
    0x0b12: (0x0b00, 'job_group_2', 5, 1),  # nin_group_2 / innin_effect
    0x0b14: (0x0b00, 'job_group_2', 5, 5),  # nin_group_2 / nin_magic_accuracy
    0x0b16: (0x0b00, 'job_group_2', 5, 4),  # nin_group_2 / nin_magic_bonus
    0x04c0: (0x04c0, 'job_group_1', 5, 10),  # drg_group_1 / ancient_circle_recast
    0x04c2: (0x04c0, 'job_group_1', 5, 2),  # drg_group_1 / jump_recast
    0x04c4: (0x04c0, 'job_group_1', 5, 4),  # drg_group_1 / high_jump_recast
    0x04c6: (0x04c0, 'job_group_1', 5, 6),  # drg_group_1 / super_jump_recast
    0x04c8: (0x04c0, 'job_group_1', 5, 3),  # drg_group_1 / spirit_link_recast
    0x0b40: (0x0b40, 'job_group_2', 5, 1),  # drg_group_2 / deep_breathing
    0x0b42: (0x0b40, 'job_group_2', 5, 15),  # drg_group_2 / angon
    0x0b44: (0x0b40, 'job_group_2', 5, 1),  # drg_group_2 / empathy
    0x0b46: (0x0b40, 'job_group_2', 5, 10),  # drg_group_2 / strafe_effect
    0x0500: (0x0500, 'job_group_1', 5, 3),  # smn_group_1 / avatar_physical_accuracy
    0x0502: (0x0500, 'job_group_1', 5, 2),  # smn_group_1 / avatar_physical_attack
    0x0504: (0x0500, 'job_group_1', 5, 3),  # smn_group_1 / avatar_magical_accuracy
    0x0506: (0x0500, 'job_group_1', 5, 2),  # smn_group_1 / avatar_magical_attack
    0x0508: (0x0500, 'job_group_1', 5, 5),  # smn_group_1 / summoning_magic_cast_time
    0x0b80: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / meteor_strike
    0x0b82: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / heavenly_strike
    0x0b84: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / wind_blade
    0x0b86: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / geocrush
    0x0b88: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / thunderstorm
    0x0b8a: (0x0b80, 'job_group_2', 5, 400),  # smn_group_2 / grandfall
    0x0540: (0x0540, 'job_group_1', 5, 4),  # blu_group_1 / chain_affinity_recast
    0x0542: (0x0540, 'job_group_1', 5, 4),  # blu_group_1 / burst_affinity_recast
    0x0544: (0x0540, 'job_group_1', 5, 4),  # blu_group_1 / monster_correlation
    0x0546: (0x0540, 'job_group_1', 5, 2),  # blu_group_1 / physical_potency
    0x0548: (0x0540, 'job_group_1', 5, 2),  # blu_group_1 / magical_accuracy
    0x0bc0: (0x0bc0, 'job_group_2', 5, 5),  # blu_group_2 / convergence
    0x0bc2: (0x0bc0, 'job_group_2', 5, 5),  # blu_group_2 / diffusion
    0x0bc4: (0x0bc0, 'job_group_2', 5, 100),  # blu_group_2 / enchainment
    0x0bc6: (0x0bc0, 'job_group_2', 5, 1),  # blu_group_2 / assimilation
    0x0580: (0x0580, 'job_group_1', 5, 2),  # cor_group_1 / phantom_roll_recast
    0x0582: (0x0580, 'job_group_1', 5, 2),  # cor_group_1 / quick_draw_recast
    0x0584: (0x0580, 'job_group_1', 5, 2),  # cor_group_1 / quick_draw_accuracy
    0x0586: (0x0580, 'job_group_1', 5, 40),  # cor_group_1 / random_deal_recast
    0x0588: (0x0580, 'job_group_1', 5, 10),  # cor_group_1 / bust_duration
    0x0c00: (0x0c00, 'job_group_2', 5, 10),  # cor_group_2 / snake_eye
    0x0c02: (0x0c00, 'job_group_2', 5, 10),  # cor_group_2 / fold
    0x0c04: (0x0c00, 'job_group_2', 5, 20),  # cor_group_2 / winning_streak
    0x0c06: (0x0c00, 'job_group_2', 5, 10),  # cor_group_2 / loaded_deck
    0x05c0: (0x05c0, 'job_group_1', 5, 2),  # pup_group_1 / automaton_skills
    0x05c2: (0x05c0, 'job_group_1', 5, 3),  # pup_group_1 / maintenance_recast
    0x05c4: (0x05c0, 'job_group_1', 5, 2),  # pup_group_1 / repair_effect
    0x05c6: (0x05c0, 'job_group_1', 5, 40),  # pup_group_1 / activate_recast
    0x05c8: (0x05c0, 'job_group_1', 5, 3),  # pup_group_1 / repair_recast
    0x0c40: (0x0c40, 'job_group_2', 5, 5),  # pup_group_2 / role_reversal
    0x0c42: (0x0c40, 'job_group_2', 5, 5),  # pup_group_2 / ventriloquy
    0x0c44: (0x0c40, 'job_group_2', 5, 5),  # pup_group_2 / fine_tuning
    0x0c46: (0x0c40, 'job_group_2', 5, 5),  # pup_group_2 / optimization
    0x0600: (0x0600, 'job_group_1', 5, 3),  # dnc_group_1 / step_accuracy
    0x0602: (0x0600, 'job_group_1', 5, 100),  # dnc_group_1 / haste_samba_effect
    0x0604: (0x0600, 'job_group_1', 5, 3),  # dnc_group_1 / reverse_flourish_effect
    0x0606: (0x0600, 'job_group_1', 5, 1),  # dnc_group_1 / building_flourish_effect
    0x0c80: (0x0c80, 'job_group_2', 5, 5),  # dnc_group_2 / saber_dance
    0x0c82: (0x0c80, 'job_group_2', 5, 5),  # dnc_group_2 / fan_dance
    0x0c84: (0x0c80, 'job_group_2', 5, 1),  # dnc_group_2 / no_foot_rise
    0x0c86: (0x0c80, 'job_group_2', 5, 3),  # dnc_group_2 / closed_position
    0x0640: (0x0640, 'job_group_1', 5, 2),  # sch_group_1 / grimoire_recast
    0x0642: (0x0640, 'job_group_1', 5, 1),  # sch_group_1 / modus_veritas_duration
    0x0644: (0x0640, 'job_group_1', 5, 1),  # sch_group_1 / helix_magic_acc_att
    0x0646: (0x0640, 'job_group_1', 5, 10),  # sch_group_1 / max_sublimation
    0x0cc0: (0x0cc0, 'job_group_2', 5, 5),  # sch_group_2 / altruism
    0x0cc2: (0x0cc0, 'job_group_2', 5, 5),  # sch_group_2 / focalization
    0x0cc4: (0x0cc0, 'job_group_2', 5, 10),  # sch_group_2 / tranquility
    0x0cc6: (0x0cc0, 'job_group_2', 5, 10),  # sch_group_2 / equanimity
    0x0cc8: (0x0cc0, 'job_group_2', 5, 5),  # sch_group_2 / enlightenment
    0x0cca: (0x0cc0, 'job_group_2', 5, 1),  # sch_group_2 / stormsurge
    0x06c0: (0x06c0, 'job_group_1', 5, 1),  # geo_group_1 / full_circle_effect
    0x06c2: (0x06c0, 'job_group_1', 5, 10),  # geo_group_1 / ecliptic_att_recast
    0x06c4: (0x06c0, 'job_group_1', 5, 20),  # geo_group_1 / life_cycle_recast
    0x06c6: (0x06c0, 'job_group_1', 5, 20),  # geo_group_1 / blaze_of_glory_recast
    0x06c8: (0x06c0, 'job_group_1', 5, 20),  # geo_group_1 / dematerialize_recast
    0x0d40: (0x0d40, 'job_group_2', 5, 1),  # geo_group_2 / mending_halation
    0x0d42: (0x0d40, 'job_group_2', 5, 1),  # geo_group_2 / radial_arcana
    0x0d44: (0x0d40, 'job_group_2', 5, 1),  # geo_group_2 / curative_recantation
    0x0d46: (0x0d40, 'job_group_2', 5, 10),  # geo_group_2 / primeval_zeal
    0x0700: (0x0700, 'job_group_1', 5, 2),  # run_group_1 / rune_enhance
    0x0702: (0x0700, 'job_group_1', 5, 1),  # run_group_1 / vallation_effect
    0x0704: (0x0700, 'job_group_1', 5, 3),  # run_group_1 / lunge_effect
    0x0706: (0x0700, 'job_group_1', 5, 1),  # run_group_1 / pflug_effect
    0x0708: (0x0700, 'job_group_1', 5, 10),  # run_group_1 / gambit_effect
    0x0d80: (0x0d80, 'job_group_2', 5, 4),  # run_group_2 / battuta
    0x0d82: (0x0d80, 'job_group_2', 5, 3),  # run_group_2 / rayke
    0x0d84: (0x0d80, 'job_group_2', 5, 10),  # run_group_2 / inspiration
    0x0d86: (0x0d80, 'job_group_2', 5, 5),  # run_group_2 / sleight_of_sword
}


def next_cost(merit_id: int, count: int) -> int:
    """Merit points the next upgrade costs, or 0 when the merit is maxed."""
    entry = MERITS.get(int(merit_id))
    if entry is None:
        return 0
    ladder = COSTS[entry[1]]
    count = int(count)
    return 0 if count >= len(ladder) else int(ladder[count])


def max_upgrades(merit_id: int) -> int:
    entry = MERITS.get(int(merit_id))
    return 0 if entry is None else entry[2]


def category_of(merit_id: int) -> int | None:
    entry = MERITS.get(int(merit_id))
    return None if entry is None else entry[0]


# merit id -> client skill id the merit raises by `value` per rank
SKILL_MERITS = {
    0x00c0: 1,  # hand_to_hand_skill / hand_to_hand
    0x00c2: 2,  # dagger_skill / dagger
    0x00c4: 3,  # sword_skill / sword
    0x00c6: 4,  # great_sword_skill / great_sword
    0x00c8: 5,  # axe_skill / axe
    0x00ca: 6,  # great_axe_skill / great_axe
    0x00cc: 7,  # scythe_skill / scythe
    0x00ce: 8,  # polearm_skill / polearm
    0x00d0: 9,  # katana_skill / katana
    0x00d2: 10,  # great_katana_skill / great_katana
    0x00d4: 11,  # club_skill / club
    0x00d6: 12,  # staff_skill / staff
    0x00d8: 25,  # archery_skill / archery
    0x00da: 26,  # marksmanship_skill / marksmanship
    0x00dc: 27,  # throwing_skill / throwing
    0x00de: 28,  # guarding_skill / guard
    0x00e0: 29,  # evasion_skill / evasion
    0x00e2: 30,  # shield_skill / shield
    0x00e4: 31,  # parrying_skill / parry
    0x0100: 32,  # divine_magic_skill / divine_magic
    0x0102: 33,  # healing_magic_skill / healing_magic
    0x0104: 34,  # enhancing_magic_skill / enhancing_magic
    0x0106: 35,  # enfeebling_magic_skill / enfeebling_magic
    0x0108: 36,  # elemental_magic_skill / elemental_magic
    0x010a: 37,  # dark_magic_skill / dark_magic
    0x010c: 38,  # summoning_magic_skill / summoning_magic
    0x010e: 39,  # ninjutsu_skill / ninjutsu
    0x0110: 40,  # singing_skill / singing
    0x0112: 41,  # string_instrument_skill / string_instrument
    0x0114: 42,  # wind_instrument_skill / wind_instrument
    0x0116: 43,  # blue_magic_skill / blue_magic
    0x0118: 44,  # geomancy_skill / geomancy
    0x011a: 45,  # handbell_skill / handbell
}
