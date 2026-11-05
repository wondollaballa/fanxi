"""The `/checkparam`-style stat report for the launcher.

The game already builds one authoritative stat sheet for combat.  This module turns the same
source modifiers into a report the launcher can show: the final Attack, Accuracy, Defense,
Evasion, HP/MP and the combat modifiers, each with the pieces that contributed to it.

Sources are kept apart so a player can see where a number came from:

* gear (per equipped piece, augments included),
* food (the item and its percentage caps),
* job traits (JT),
* job abilities (JA, including the job-point categories they switch on),
* job points/gifts,
* buffs (spells, songs, rolls and the en-light/endark power rows),
* merits.

Derived stats are attributed in the same order the combat formula uses: base values and skill,
then every flat source, then the food percentages and Attack/Defense percentages.  The last row
is the sheet's own value, so the source rows add up to exactly what the server swings with.
"""
from __future__ import annotations

from functools import lru_cache

from . import combat, effects, modifiers as mod, rolls, stats, traits

#: The order sources are shown in; job abilities and traits sit next to the buffs they grant.
SOURCE_ORDER = ("base", "gear", "food", "traits", "job_abilities", "job_points", "buffs",
                "merits", "other")

@lru_cache(maxsize=1)
def _effect_names() -> dict[int, str]:
    """Status id -> the first spell name that puts it up, for the buff source rows."""
    names: dict[int, str] = {}
    for name, row in effects.STATUS_SPELLS.items():
        try:
            effect_id = int(row[0])
        except (TypeError, ValueError, IndexError):
            continue
        names.setdefault(effect_id, str(name).title())
    return names


@lru_cache(maxsize=1)
def _roll_names() -> dict[int, str]:
    """Status id -> roll name, so a roll is not reported as "Effect 330"."""
    return {int(spec.status): spec.name for spec in rolls.ROLLS.values()}


def effect_label(effect_id: int, state: dict | None = None) -> str:
    if state and state.get("song_name"):
        return str(state["song_name"])
    if int(effect_id) == effects.BUST:
        return "Bust"
    roll_name = _roll_names().get(int(effect_id))
    if roll_name:
        return roll_name
    return _effect_names().get(int(effect_id), "Effect %d" % int(effect_id))

SOURCE_LABELS = {
    "base": "Base & skill",
    "gear": "Gear",
    "food": "Food",
    "traits": "Job traits (JT)",
    "job_abilities": "Job abilities (JA)",
    "job_points": "Job points & gifts",
    "buffs": "Buffs",
    "merits": "Merits",
    "other": "Other",
}

#: The client's equip kind -> the label the launcher's EquipViewer uses.
EQUIP_KIND_LABELS = {
    0: "Main", 1: "Sub", 2: "Range", 3: "Ammo",
    4: "Head", 5: "Body", 6: "Hands", 7: "Legs", 8: "Feet",
    9: "Neck", 10: "Waist", 11: "Left ear", 12: "Right ear",
    13: "Left ring", 14: "Right ring", 15: "Back",
}

ATTRIBUTE_LABELS = (("str", "STR", mod.STR), ("dex", "DEX", mod.DEX),
                    ("vit", "VIT", mod.VIT), ("agi", "AGI", mod.AGI),
                    ("int", "INT", mod.INT), ("mnd", "MND", mod.MND),
                    ("chr", "CHR", mod.CHR))

#: Modifiers the derived rows already contain.  Showing them again as a raw row would
#: double-print the same number (Attack appears both in the formula and as +ATT gear).
FOLDED_MODS = frozenset({
    mod.DEF, mod.HP, mod.HPP, mod.MP, mod.MPP,
    mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR,
    mod.ATT, mod.ACC, mod.EVA, mod.ATT_PERCENT, mod.DEF_PERCENT,
    # Smite is folded into Attack and Desperate Blows into Haste (ability); Stalwart
    # Soul only changes Souleater's HP cost, so none of them is a raw row.
    mod.SMITE, mod.DESPERATE_BLOWS, mod.STALWART_SOUL,
    mod.MAX_HP_BOOST, mod.MAX_MP_BOOST,
    mod.FOOD_HP, mod.FOOD_MP, mod.FOOD_HP_CAP, mod.FOOD_MP_CAP,
    mod.FOOD_ATT_PERCENT, mod.FOOD_ATT_CAP, mod.FOOD_ACC_PERCENT, mod.FOOD_ACC_CAP,
    mod.FOOD_DEF_PERCENT, mod.FOOD_DEF_CAP, mod.FOOD_RATT_PERCENT, mod.FOOD_RATT_CAP,
    mod.FOOD_RACC_PERCENT, mod.FOOD_RACC_CAP,
    # Internal tuning values, not player-facing stats.
    mod.WALTZ_COST, mod.MAIN_DMG_RANK, mod.ADDS_WEAPONSKILL, mod.DMG_RATING,
    mod.SONG_RECAST_DELAY, mod.MINNE_EFFECT, mod.MINUET_EFFECT, mod.PAEON_EFFECT,
    mod.REQUIEM_EFFECT, mod.THRENODY_EFFECT, mod.MADRIGAL_EFFECT, mod.MAMBO_EFFECT,
    mod.LULLABY_EFFECT, mod.ETUDE_EFFECT, mod.BALLAD_EFFECT, mod.MARCH_EFFECT,
    mod.FINALE_EFFECT, mod.CAROL_EFFECT, mod.MAZURKA_EFFECT, mod.ELEGY_EFFECT,
    mod.PRELUDE_EFFECT, mod.HYMNUS_EFFECT, mod.VIRELAI_EFFECT, mod.SCHERZO_EFFECT,
    mod.ALL_SONGS_EFFECT, mod.MAXIMUM_SONGS_BONUS,
})

#: (key, label, modifier id, percent, display scale, primary, group, order)
RAW_STATS = (
    ("ranged_attack", "Ranged Attack", mod.RATT, False, 1, True, "Combat", 300),
    ("ranged_accuracy", "Ranged Accuracy", mod.RACC, False, 1, True, "Combat", 301),
    ("magic_atk_bonus", "Magic Atk. Bonus", mod.MATT, False, 1, True, "Magic", 400),
    ("magic_accuracy", "Magic Accuracy", mod.MACC, False, 1, True, "Magic", 401),
    ("magic_def_bonus", "Magic Def. Bonus", mod.MDEF, False, 1, True, "Magic", 402),
    ("magic_evasion", "Magic Evasion", mod.MEVA, False, 1, True, "Magic", 403),
    ("haste_gear", "Haste (gear)", mod.HASTE_GEAR, True, 100, True, "Combat", 310),
    ("haste_magic", "Haste (magic)", mod.HASTE_MAGIC, True, 100, True, "Combat", 311),
    ("haste_ability", "Haste (ability)", mod.HASTE_ABILITY, True, 100, True, "Combat", 312),
    ("store_tp", "Store TP", mod.STORETP, False, 1, True, "Combat", 320),
    ("dual_wield", "Dual Wield", mod.DUAL_WIELD, False, 1, True, "Combat", 321),
    ("double_attack", "Double Attack", mod.DOUBLE_ATTACK, False, 1, True, "Combat", 322),
    ("triple_attack", "Triple Attack", mod.TRIPLE_ATTACK, False, 1, True, "Combat", 323),
    ("quadruple_attack", "Quadruple Attack", mod.QUADRUPLE_ATTACK, False, 1, True, "Combat", 324),
    ("subtle_blow", "Subtle Blow", mod.SUBTLE_BLOW, False, 1, True, "Combat", 325),
    ("fast_cast", "Fast Cast", mod.FASTCAST, True, 1, True, "Magic", 410),
    ("cure_potency", "Cure potency", mod.CURE_POTENCY, True, 1, True, "Magic", 411),
    ("refresh", "Refresh", mod.REFRESH, False, 1, True, "Magic", 412),
    ("regen", "Regen", mod.REGEN, False, 1, True, "Magic", 413),
    # Regain is the TP sibling of the other two passive ticks (Karieyh Ring +1,
    # Null Masque).  Without a row here it fell through to the generic "Other"
    # modifier list as "mod:368".
    ("regain", "Regain", mod.REGAIN, False, 1, True, "Combat", 414),
    ("enmity", "Enmity", mod.ENMITY, False, 1, True, "Defense", 500),
    ("tp_bonus", "TP Bonus", mod.TP_BONUS, False, 1, True, "Combat", 330),
    ("weapon_skill_damage", "Weapon skill damage", mod.WSD_ALL_HITS, True, 1, True, "Combat", 331),
    ("skillchain_bonus", "Skillchain Bonus", mod.SKILLCHAIN_BONUS, True, 1, True, "Combat", 332),
    ("conserve_tp", "Conserve TP", mod.CONSERVE_TP, True, 1, True, "Combat", 333),
    ("save_tp", "Save TP", mod.SAVETP, False, 1, True, "Combat", 334),
    ("magic_burst_damage", "Magic burst damage", mod.MAGIC_BURST_BONUS_UNCAPPED, True, 1, True, "Magic", 415),
    ("critical_hit_rate", "Critical hit rate", mod.CRIT_HIT_RATE, True, 100, True, "Combat", 333),
    ("critical_hit_damage", "Critical hit damage", mod.CRIT_DMG_INCREASE, True, 1, True, "Combat", 334),
    ("magic_damage", "Magic Damage", mod.MAGIC_DAMAGE, False, 1, True, "Magic", 416),
    ("damage_taken", "Damage taken", mod.DMG, True, 100, True, "Defense", 510),
    ("physical_damage_taken", "Physical damage taken", mod.DMGPHYS, True, 100, True, "Defense", 511),
    ("magic_damage_taken", "Magic damage taken", mod.DMGMAGIC, True, 100, True, "Defense", 512),
    ("breath_damage_taken", "Breath damage taken", mod.DMGBREATH, True, 100, True, "Defense", 513),
    ("ranged_damage_taken", "Ranged damage taken", mod.DMGRANGE, True, 100, True, "Defense", 514),
    # Less common, still worth a row in the full sheet.
    ("physical_damage_taken_ii", "Physical damage taken II", mod.DMGPHYS_II, True, 100, False, "Defense", 515),
    ("magic_damage_taken_ii", "Magic damage taken II", mod.DMGMAGIC_II, True, 100, False, "Defense", 516),
    ("physical_damage_limit", "Physical damage limit", mod.DAMAGE_LIMIT, False, 1, False, "Defense", 517),
    ("critical_hit_evasion", "Critical hit evasion", mod.CRITICAL_HIT_EVASION, True, 100, False, "Defense", 518),
    ("critical_hit_defence", "Critical defense", mod.CRIT_DEF_BONUS, True, 1, False, "Defense", 519),
    ("magic_burst_damage_capped", "Magic burst damage (capped)", mod.MAGIC_BURST_BONUS_CAPPED, True, 1, False, "Magic", 417),
    ("weapon_skill_damage_first", "Weapon skill damage (first hit)", mod.WSD_FIRST_HIT, True, 1, False, "Combat", 335),
    ("weapon_skill_accuracy", "Weapon skill accuracy", mod.WS_ACCURACY, False, 1, False, "Combat", 336),
    ("subtle_blow_ii", "Subtle Blow II", mod.SUBTLE_BLOW_II, False, 1, False, "Combat", 326),
    ("martial_arts", "Martial Arts", mod.MARTIAL_ARTS, False, 1, False, "Combat", 327),
    ("fencer_tp_bonus", "Fencer TP Bonus", mod.FENCER_TP_BONUS, False, 1, False, "Combat", 337),
    ("fencer_crit_rate", "Fencer critical rate", mod.FENCER_CRIT_RATE, True, 1, False, "Combat", 338),
    ("daken", "Daken", 911, False, 1, False, "Combat", 339),
    ("counter", "Counter", mod.COUNTER, False, 1, False, "Combat", 340),
    ("song_duration", "Song duration", mod.SONG_DURATION_BONUS, True, 1, False, "Magic", 420),
    ("enhancing_magic_duration", "Enhancing magic duration", mod.ENH_MAGIC_DURATION, True, 1, False, "Magic", 421),
    ("enfeebling_magic_duration", "Enfeebling magic duration", mod.ENF_MAG_DURATION_FLAT, False, 1, False, "Magic", 422),
    # The JSE necks' "Enf. Mag. eff. dur.+25%" row is a percentage, not seconds;
    # the flat job-point seconds stay on their own row above.
    ("enfeebling_magic_duration_pct", "Enfeebling magic duration +%", mod.ENF_MAG_DURATION, True, 1, False, "Magic", 427),
    ("cure_potency_ii", "Cure potency II", mod.CURE_POTENCY_II, True, 1, False, "Magic", 423),
    ("cure_potency_received", "Cure potency received", mod.CURE_POTENCY_RCVD, True, 1, False, "Magic", 424),
    ("regen_potency", "Regen potency", mod.REGEN_POTENCY, True, 1, False, "Magic", 425),
    ("drain_aspir", "Drain and Aspir potency", mod.DRAIN_ASPIR, False, 1, False, "Magic", 426),
    ("elemental_fire", "Fire resistance", mod.FIRE_MEVA, False, 1, False, "Resistance", 600),
    ("elemental_ice", "Ice resistance", mod.ICE_MEVA, False, 1, False, "Resistance", 601),
    ("elemental_wind", "Wind resistance", mod.WIND_MEVA, False, 1, False, "Resistance", 602),
    ("elemental_earth", "Earth resistance", mod.EARTH_MEVA, False, 1, False, "Resistance", 603),
    ("elemental_thunder", "Thunder resistance", mod.THUNDER_MEVA, False, 1, False, "Resistance", 604),
    ("elemental_water", "Water resistance", mod.WATER_MEVA, False, 1, False, "Resistance", 605),
    ("elemental_light", "Light resistance", mod.LIGHT_MEVA, False, 1, False, "Resistance", 606),
    ("elemental_dark", "Dark resistance", mod.DARK_MEVA, False, 1, False, "Resistance", 607),
)

MOD_LABELS = {
    row[2]: row[1] for row in RAW_STATS
}
MOD_LABELS.update({
    mod.DEF: "Defense", mod.HP: "HP", mod.MP: "MP",
    mod.STR: "STR", mod.DEX: "DEX", mod.VIT: "VIT", mod.AGI: "AGI",
    mod.INT: "INT", mod.MND: "MND", mod.CHR: "CHR",
    mod.ATT: "Attack", mod.ACC: "Accuracy", mod.EVA: "Evasion",
    mod.RATT: "Ranged Attack", mod.RACC: "Ranged Accuracy",
    mod.MATT: "Magic Atk. Bonus", mod.MDEF: "Magic Def. Bonus",
    mod.MACC: "Magic Accuracy", mod.MEVA: "Magic Evasion",
    mod.HASTE_GEAR: "Haste (gear)", mod.HASTE_MAGIC: "Haste (magic)",
    mod.HASTE_ABILITY: "Haste (ability)",
    mod.STORETP: "Store TP", mod.DUAL_WIELD: "Dual Wield",
    mod.DOUBLE_ATTACK: "Double Attack", mod.TRIPLE_ATTACK: "Triple Attack",
    mod.QUADRUPLE_ATTACK: "Quadruple Attack", mod.SUBTLE_BLOW: "Subtle Blow",
    mod.FASTCAST: "Fast Cast", mod.CURE_POTENCY: "Cure potency",
    mod.REFRESH: "Refresh", mod.REGEN: "Regen", mod.ENMITY: "Enmity",
    mod.TP_BONUS: "TP Bonus", mod.WSD_ALL_HITS: "Weapon skill damage",
    mod.SKILLCHAIN_BONUS: "Skillchain Bonus",
    mod.MAGIC_BURST_BONUS_CAPPED: "Magic burst damage (capped)",
    mod.MAGIC_BURST_BONUS_UNCAPPED: "Magic burst damage",
    mod.CRIT_HIT_RATE: "Critical hit rate", mod.CRIT_DMG_INCREASE: "Critical hit damage",
    mod.MAGIC_DAMAGE: "Magic Damage", mod.DMG: "Damage taken",
    mod.DMGPHYS: "Physical damage taken", mod.DMGMAGIC: "Magic damage taken",
    mod.DMGBREATH: "Breath damage taken", mod.DMGRANGE: "Ranged damage taken",
    mod.DMGPHYS_II: "Physical damage taken II", mod.DMGMAGIC_II: "Magic damage taken II",
    mod.CRITICAL_HIT_EVASION: "Critical hit evasion", mod.CRIT_DEF_BONUS: "Critical defense",
    mod.DAMAGE_LIMIT: "Physical damage limit", mod.DAMAGE_LIMITP: "Physical damage limit (%)",
    mod.WS_ACCURACY: "Weapon skill accuracy", mod.SUBTLE_BLOW_II: "Subtle Blow II",
    mod.MARTIAL_ARTS: "Martial Arts", mod.FENCER_TP_BONUS: "Fencer TP Bonus",
    mod.FENCER_CRIT_RATE: "Fencer critical rate", mod.COUNTER: "Counter",
    mod.SONG_DURATION_BONUS: "Song duration", mod.ENH_MAGIC_DURATION: "Enhancing magic duration",
    mod.ENF_MAG_DURATION_FLAT: "Enfeebling magic duration",
    mod.ENF_MAG_DURATION: "Enfeebling magic duration +%",
    mod.CURE_POTENCY_II: "Cure potency II", mod.CURE_POTENCY_RCVD: "Cure potency received",
    mod.BLOOD_PACT_DAMAGE: "Blood Pact damage",
    mod.REGEN_POTENCY: "Regen potency", mod.DRAIN_ASPIR: "Drain and Aspir potency",
    mod.FIRE_MEVA: "Fire resistance", mod.ICE_MEVA: "Ice resistance",
    mod.WIND_MEVA: "Wind resistance", mod.EARTH_MEVA: "Earth resistance",
    mod.THUNDER_MEVA: "Thunder resistance", mod.WATER_MEVA: "Water resistance",
    mod.LIGHT_MEVA: "Light resistance", mod.DARK_MEVA: "Dark resistance",
    mod.ENSPELL_DMG_BONUS: "Enspell damage bonus", mod.ENSPELL_DURATION: "Enspell duration",
    mod.REGEN_DURATION: "Regen duration", mod.REFRESH_DOWN: "Refresh down",
    mod.REGEN_DOWN: "Regen down", mod.CLEAR_MIND: "Clear Mind",
    mod.STONESKIN_BONUS_HP: "Stoneskin HP", mod.ENF_MAG_POTENCY: "Enfeebling magic potency",
    mod.ENHANCES_REFRESH: "Enhances Refresh", mod.ANY_FTP_BONUS: "fTP bonus",
    mod.RATT_PERCENT: "Ranged Attack (%)",
    mod.MOVE_SPEED_BOLTERS_ROLL: "Movement speed (Bolter's Roll)",
    mod.ONE_HOUR_RECAST: "One-hour recast (minutes)",
    mod.STRATAGEM_RECAST: "Strategem recast (seconds)",
    mod.PHANTOM_DURATION: "Phantom Roll duration",
    mod.SNAPSHOT: "Snapshot", mod.REGAIN: "Regain",
    mod.CONSERVE_MP: "Conserve MP",
    mod.EXP_BONUS: "Experience bonus", mod.CAPACITY_BONUS: "Capacity point bonus",
    mod.ELEMENTAL_WS_DAMAGE: "Elemental WS damage",
    mod.FIRE_MAB: "Fire affinity", mod.ICE_MAB: "Ice affinity",
    mod.WIND_MAB: "Wind affinity", mod.EARTH_MAB: "Earth affinity",
    mod.THUNDER_MAB: "Thunder affinity", mod.WATER_MAB: "Water affinity",
    mod.LIGHT_MAB: "Light affinity", mod.DARK_MAB: "Dark affinity",
    911: "Daken",
    # LSB modifier ids that real gear/augments use but modifiers.py does not name.
    4: "MP → HP",                    # Cassie/Odnowa conversion
    168: "Spell interruption rate",
    256: "Aftermath",
    455: "Song spellcasting time",
    491: "Waltz potency",
    598: "Weapon skill damage (Mordant Rime)",
    958: "Resistance to all status ailments",
})
# Resistance/killer families and a few other player-facing names already live in traits.
MOD_LABELS.update(traits.MOD_LABELS)

#: Additional modifiers that need the display treatment the curated table gives:
#: (percent, display scale, negate the raw value).  LSB stores several defensive
#: reductions as positive numbers and some percentages in hundredths.
_EXTRA_DISPLAY = {
    168: (True, 1, False),   # Spell interruption rate: raw negative is a reduction
    455: (True, 1, True),    # Song spellcasting time is a reduction
    491: (True, 1, False),   # Waltz potency
    598: (True, 1, False),   # Weapon-skill-specific damage
}
# Every 570-825 modifier is a weapon-skill damage percentage.  A future weapon must
# not turn one into a naked multiplier in the sheet.
for _wsdmg_id in range(570, 826):
    _EXTRA_DISPLAY.setdefault(_wsdmg_id, (True, 1, False))

#: Modifiers that are already internal/folded and should not become an extra row.
_HIDDEN = set(FOLDED_MODS) | {
    mod.FOOD_HP, mod.FOOD_MP, mod.FOOD_ATT_PERCENT, mod.FOOD_ACC_PERCENT,
    mod.FOOD_DEF_PERCENT, mod.FOOD_RATT_PERCENT, mod.FOOD_RACC_PERCENT,
    mod.HPP, mod.MPP,
}


def _scaled(value, scale: float):
    if not scale or scale == 1:
        return int(value)
    return round(float(value) / float(scale), 4)


def _detail(label: str, value: int, note: str = ""):
    row = {"label": str(label), "value": int(value)}
    if note:
        row["note"] = str(note)
    return row


def _finish_source(row: dict):
    """Make the detail rows add up to the source value (never hide a rounding line)."""
    value = row["value"]
    total = sum(item["value"] for item in row.get("details", ()))
    if total != value:
        residual = value - total
        if isinstance(residual, float):
            residual = round(residual, 4)
        row.setdefault("details", []).append({"label": "Rounding", "value": residual})
    return row


def _entry_details(sources, key: str, direct) -> tuple[int, list[dict]]:
    """A source's direct amount and one detail per item/trait/ability that supplied it."""
    source = sources.get(key) or {}
    value = int(direct(source.get("mods") or {}))
    details = []
    for entry in source.get("entries", ()):
        amount = int(direct(entry.get("mods") or {}))
        if amount:
            details.append(_detail(entry.get("label") or source.get("label") or key, amount,
                                   str(entry.get("augments") or "")))
    if not details and value:
        details = [_detail(source.get("label") or key, value)]
    return value, details


def _source_rows(sources, direct) -> dict[str, dict]:
    rows = {}
    for key in SOURCE_ORDER:
        if key == "base":
            continue
        source = sources.get(key)
        if not source:
            continue
        value, details = _entry_details(sources, key, direct)
        if value or details:
            rows[key] = {"key": key, "label": source.get("label") or SOURCE_LABELS[key],
                         "value": value, "details": details}
    return rows


def _ordered_sources(rows: list[dict]) -> list[dict]:
    by_key = {row["key"]: row for row in rows}
    out = []
    for key in SOURCE_ORDER:
        row = by_key.get(key)
        if row is None:
            continue
        out.append(_finish_source(row))
    return out


def _add_bonus(rows: dict[str, dict], sources, mod_id: int, amount: int, label: str):
    """Put a percentage bonus on the source that owns the percentage, else on Other."""
    if not amount:
        return
    owners = [key for key in SOURCE_ORDER
              if key not in ("base",) and (sources.get(key) or {}).get("mods", {}).get(mod_id)]
    if not owners:
        owners = ["other"]
    # Split the bonus proportionally when more than one source carries the percentage.
    total = sum(abs(int((sources.get(key) or {}).get("mods", {}).get(mod_id, 0)))
                for key in owners) or len(owners)
    remaining = amount
    for index, key in enumerate(owners):
        share = remaining if index == len(owners) - 1 else int(amount * abs(
            int((sources.get(key) or {}).get("mods", {}).get(mod_id, 0))) / total)
        if not share:
            continue
        source = sources.get(key) or {}
        row = rows.setdefault(key, {
            "key": key,
            "label": source.get("label") or SOURCE_LABELS.get(key, "Other"),
            "value": 0,
            "details": [],
        })
        row["value"] = int(row.get("value", 0)) + int(share)
        row.setdefault("details", []).append(_detail(label, int(share)))
        remaining -= int(share)


def _base_row(value: int, details: list[dict]) -> dict:
    row = {"key": "base", "label": SOURCE_LABELS["base"], "value": int(value),
           "details": details}
    return _finish_source(row)


def _attack_entry(character, sources, mods, sheet, base_attributes) -> dict:
    mult = stats._str_multiplier(sheet.weapon)
    direct = lambda source_mods: int(source_mods.get(mod.ATT, 0)) + int(
        source_mods.get(mod.STR, 0) * mult)
    rows = _source_rows(sources, direct)
    flat = (8 + int(sheet.attributes["str"] * mult) + int(sheet.fighter.skill_value)
            + int(mods.get(mod.ATT, 0)))
    food_percent = int(mods.get(mod.FOOD_ATT_PERCENT, 0))
    food_cap = int(mods.get(mod.FOOD_ATT_CAP, 0))
    food_bonus = min(flat * food_percent // 100, food_cap) if food_percent > 0 else 0
    attack_percent = int(mods.get(mod.ATT_PERCENT, 0))
    percent_bonus = (flat + food_bonus) * attack_percent // 100
    _add_bonus(rows, sources, mod.FOOD_ATT_PERCENT, food_bonus, "Food Attack %")
    _add_bonus(rows, sources, mod.ATT_PERCENT, percent_bonus, "Attack %")
    total = int(sheet.attack)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    base_details = [
        _detail("Base attack (level, race, job)", 8 + int(base_attributes["str"] * mult)),
        _detail("Weapon skill (job, job points, merits and gear)", int(sheet.fighter.skill_value)),
    ]
    base = _base_row(base_value, base_details)
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("attack", "Attack", total, out, primary=True, group="Derived",
                 formula=("8 + Attack + STR×%.2f + weapon skill, then food Attack%% "
                          "and Attack%%" % mult), order=0)


def _accuracy_entry(character, sources, mods, sheet, base_attributes) -> dict:
    direct = lambda source_mods: int(source_mods.get(mod.ACC, 0)) + int(
        source_mods.get(mod.DEX, 0) * combat.DEX_TO_ACC)
    rows = _source_rows(sources, direct)
    flat = (combat.acc_from_skill(sheet.fighter.skill_value)
            + int(sheet.attributes["dex"] * combat.DEX_TO_ACC)
            + int(mods.get(mod.ACC, 0)))
    food_percent = int(mods.get(mod.FOOD_ACC_PERCENT, 0))
    food_cap = int(mods.get(mod.FOOD_ACC_CAP, 0))
    food_bonus = min(flat * food_percent // 100, food_cap) if food_percent > 0 else 0
    _add_bonus(rows, sources, mod.FOOD_ACC_PERCENT, food_bonus, "Food Accuracy %")
    total = int(sheet.accuracy)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    base_details = [
        _detail("Accuracy from weapon skill", combat.acc_from_skill(sheet.fighter.skill_value)),
        _detail("Base DEX × %.2f" % combat.DEX_TO_ACC,
                int(base_attributes["dex"] * combat.DEX_TO_ACC)),
    ]
    base = _base_row(base_value, base_details)
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("accuracy", "Accuracy", total, out, primary=True, group="Derived",
                 formula=("accuracy from skill + DEX×%.2f + Accuracy, then food Accuracy%%"
                          % combat.DEX_TO_ACC), order=1)


def _defense_entry(character, sources, mods, sheet, base_attributes) -> dict:
    direct = lambda source_mods: int(source_mods.get(mod.DEF, 0)) + int(
        source_mods.get(mod.VIT, 0) * 1.5)
    rows = _source_rows(sources, direct)
    level = max(1, int(character.get("main_level", 1)))
    level_factor = stats._level_defense_factor(level)
    flat = (8 + int(sheet.attributes["vit"] * 1.5) + level_factor
            + int(mods.get(mod.DEF, 0)))
    food_percent = int(mods.get(mod.FOOD_DEF_PERCENT, 0))
    food_cap = int(mods.get(mod.FOOD_DEF_CAP, 0))
    food_bonus = min(flat * food_percent // 100, food_cap) if food_percent > 0 else 0
    defense_percent = int(mods.get(mod.DEF_PERCENT, 0))
    percent_bonus = (flat + food_bonus) * defense_percent // 100
    _add_bonus(rows, sources, mod.FOOD_DEF_PERCENT, food_bonus, "Food Defense %")
    _add_bonus(rows, sources, mod.DEF_PERCENT, percent_bonus, "Defense %")
    total = int(sheet.defense)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    base_details = [
        _detail("Base defense (VIT × 1.5 and level)",
                8 + int(base_attributes["vit"] * 1.5) + level_factor),
    ]
    base = _base_row(base_value, base_details)
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("defense", "Defense", total, out, primary=True, group="Derived",
                 formula="8 + VIT×1.5 + level factor + Defense, then food Defense% and Defense%",
                 order=2)


def _evasion_entry(character, sources, mods, sheet, base_attributes) -> dict:
    direct = lambda source_mods: int(source_mods.get(mod.EVA, 0)) + int(
        source_mods.get(mod.AGI, 0) // 2)
    rows = _source_rows(sources, direct)
    total = int(sheet.evasion)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    skill_component = int(sheet.evasion) - int(sheet.attributes["agi"] // 2) - int(
        mods.get(mod.EVA, 0))
    base_details = [
        _detail("Evasion skill (with merits and gear)", skill_component),
        _detail("Base AGI ÷ 2", int(base_attributes["agi"] // 2)),
    ]
    base = _base_row(base_value, base_details)
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("evasion", "Evasion", total, out, primary=True, group="Derived",
                 formula="evasion skill + AGI÷2 + Evasion", order=3)


def _hp_entry(character, sources, mods, sheet, base_attributes, base_hp) -> dict:
    def direct(source_mods):
        return (int(source_mods.get(mod.HP, 0)) + int(source_mods.get(mod.MAX_HP_BOOST, 0))
                + int(source_mods.get(mod.FOOD_HP, 0)))
    rows = _source_rows(sources, direct)
    flat = (base_hp + int(mods.get(mod.HP, 0)) + int(mods.get(mod.MAX_HP_BOOST, 0))
            + int(mods.get(mod.FOOD_HP, 0)))
    percent = int(mods.get(mod.HPP, 0))
    bonus = flat * percent // 100
    _add_bonus(rows, sources, mod.HPP, bonus, "HP %")
    total = int(sheet.max_hp)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    base = _base_row(base_hp, [_detail("Base HP (race, job, level)", base_hp)])
    if base_value != base["value"]:
        base["details"].append(_detail("HP % and rounding", base_value - base["value"]))
        base["value"] = base_value
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("hp", "HP", total, out, primary=True, group="Derived",
                 formula="base HP + flat HP, then HP%", order=4)


def _mp_entry(character, sources, mods, sheet, base_attributes, base_mp) -> dict:
    def direct(source_mods):
        return (int(source_mods.get(mod.MP, 0)) + int(source_mods.get(mod.MAX_MP_BOOST, 0))
                + int(source_mods.get(mod.FOOD_MP, 0)))
    rows = _source_rows(sources, direct)
    flat = (base_mp + int(mods.get(mod.MP, 0)) + int(mods.get(mod.MAX_MP_BOOST, 0))
            + int(mods.get(mod.FOOD_MP, 0)))
    percent = int(mods.get(mod.MPP, 0))
    bonus = flat * percent // 100
    _add_bonus(rows, sources, mod.MPP, bonus, "MP %")
    total = int(sheet.max_mp)
    base_value = total - sum(int(row["value"]) for row in rows.values())
    base = _base_row(base_mp, [_detail("Base MP (race, job, level)", base_mp)])
    if base_value != base["value"]:
        base["details"].append(_detail("MP % and rounding", base_value - base["value"]))
        base["value"] = base_value
    out = [base] + _ordered_sources(list(rows.values()))
    return _stat("mp", "MP", total, out, primary=True, group="Derived",
                 formula="base MP + flat MP, then MP%", order=5)


def _attribute_entry(source_key, label, mod_id, source_mods, sheet, base_attributes) -> dict:
    base_value = int(base_attributes[source_key])
    rows = _source_rows(source_mods, lambda mods: int(mods.get(mod_id, 0)))
    total = int(sheet.attributes[source_key])
    base = _base_row(base_value, [_detail("Base %s" % label, base_value)])
    out = [base] + _ordered_sources(list(rows.values()))
    if sum(int(row["value"]) for row in out) != total:
        base["value"] = total - sum(int(row["value"]) for row in rows.values())
        base["details"] = [_detail("Base %s and rounding" % label, base["value"])]
    return _stat(source_key, label, total, out, primary=True, group="Attributes",
                 formula="base %s + gear/trait/JA/buff/food %s" % (label, label),
                 order=20 + len(sheet.attributes))


def _raw_entry(key, label, mod_id, percent, scale, primary, group, order, sources, mods,
               sheet, negate=False) -> dict:
    raw_total = int(mods.get(mod_id, 0))
    rows = _source_rows(sources, lambda source_mods: int(source_mods.get(mod_id, 0)))
    missing = raw_total - sum(int(row["value"]) for row in rows.values())
    if missing:
        rows["other"] = {"key": "other", "label": SOURCE_LABELS["other"],
                         "value": missing,
                         "details": [_detail(SOURCE_LABELS["other"], missing)]}
    total = _scaled(raw_total, scale)
    for row in rows.values():
        row["value"] = _scaled(row["value"], scale)
        for detail in row.get("details", ()):
            detail["value"] = _scaled(detail["value"], scale)
    if negate:
        total = -total
        for row in rows.values():
            row["value"] = -row["value"]
            for detail in row.get("details", ()):
                detail["value"] = -detail["value"]
    out = _ordered_sources(list(rows.values()))
    return _stat(key, label, total, out, percent=percent, primary=primary, group=group,
                 formula="", order=order)


def _stat(key, label, value, sources, *, percent=False, primary=False, group="Other",
          formula="", order=0) -> dict:
    return {
        "key": key,
        "label": label,
        "value": value,
        "percent": bool(percent),
        "primary": bool(primary),
        "group": group,
        "formula": formula,
        "sources": sources,
        "order": int(order),
    }


def _timing_detail(label: str, value: float) -> dict:
    """A detail row that keeps its fraction (unlike ``_detail``, which is for mods)."""
    return {"label": str(label), "value": round(float(value), 3)}


def _timing_sources(rows: list[dict]) -> list[dict]:
    """Keep a timing row's own order: delay, then reductions, then the floor.

    ``_ordered_sources`` sorts by the report's global source order, which would put
    gear haste ahead of a Dual Wield reduction.  Here the arithmetic order is the
    readable one, and these rows already know every piece.
    """
    return [_finish_source(row) for row in rows]


def _haste_total_entry(sheet) -> dict:
    """The three capped haste pools and their effective sum.

    The raw ``haste_magic`` row is the *sum of the buffs* and can read above its cap
    (Haste, a March and a GEO bubble together).  This row is what the swing actually
    uses, so a player can see 66.99% of buffs become 43.75% of magic haste and that
    the 80% total needs the job-ability pool (Last Resort/Hasso/Haste Samba).
    """
    gear, magic, ability = sheet.haste_pools
    pools = (
        ("gear", "Haste (gear, capped)", gear),
        ("buffs", "Haste (magic, capped)", magic),
        ("job_abilities", "Haste (ability, capped)", ability),
    )
    rows = []
    for key, label, value in pools:
        percent = round(value * 100.0, 2)
        rows.append({"key": key, "label": label, "value": percent,
                     "details": [_timing_detail(label, percent)]})
    total = round(sum(row["value"] for row in rows), 2)
    return _stat(
        "haste_total", "Haste (capped pools)", total,
        _timing_sources(rows), percent=True, primary=True, group="Combat",
        formula=("gear (cap 25%) + magic (cap 43.75%) + ability (cap 25%); "
                 "the delay reduction itself is capped at 80%"),
        order=309)


def _attack_interval_entry(sheet) -> dict:
    """The swing interval the server actually uses, with its delay pieces.

    ``Weapon delay`` is the round's delay before Dual Wield / Martial Arts; those two
    are their own reduction row because they happen outside the haste pools and TP
    (not the round) uses their result.  The three haste rows are taken from the
    post-reduction delay.  When the 80% floor binds, the leftover row names it so the
    rows still add up to the displayed value.
    """
    gear, magic, ability = sheet.haste_pools
    before = int(sheet.base_delay or sheet.delay)
    after = max(1, int(sheet.delay))
    actual = sheet.attack_delay_ms / 1000.0
    rows = [{"key": "base", "label": "Weapon delay", "value": round(before / 60.0, 3),
             "details": [_timing_detail("Weapon delay", round(before / 60.0, 3))]}]
    if after != before:
        label = "Dual Wield" if sheet.dual_wield else "Martial Arts"
        reduction = -round((before - after) / 60.0, 3)
        rows.append({"key": "traits", "label": label, "value": reduction,
                     "details": [_timing_detail(label, reduction)]})
    swing = after / 60.0
    for key, label, value in (("gear", "Haste (gear)", gear),
                              ("buffs", "Haste (magic)", magic),
                              ("job_abilities", "Haste (ability)", ability)):
        reduction = -round(swing * value, 3)
        if reduction:
            rows.append({"key": key, "label": label, "value": reduction,
                         "details": [_timing_detail(label, reduction)]})
    measured = round(sum(row["value"] for row in rows), 3)
    leftover = round(actual - measured, 3)
    if leftover:
        rows.append({"key": "other", "label": "80% delay floor", "value": leftover,
                     "details": [_timing_detail("80% delay floor", leftover)]})
    return _stat(
        "attack_interval", "Attack interval", round(actual, 3),
        _timing_sources(rows), primary=True, group="Combat",
        formula="delay / 60 x (1 - effective haste), floored at 20% of the base delay",
        order=313)


def _tp_per_hit_entry(sheet, *, off_hand: bool = False) -> dict:
    """TP one landed hit pays, after Store TP, in the client's 0-3000 units."""
    base = sheet.tp_per_hit(off_hand=off_hand)
    total = sheet.tp_per_hit_with_store_tp(off_hand=off_hand)
    store = int(sheet.fighter.mods.get(mod.STORETP, 0))
    rows = [{"key": "base", "label": "TP at weapon delay", "value": base,
             "details": [_timing_detail("TP at weapon delay", base)]}]
    if total != base:
        bonus = total - base
        rows.append({"key": "other", "label": "Store TP", "value": bonus,
                     "details": [_timing_detail("Store TP +%d%%" % store, bonus)]})
    key = "tp_per_hit_off" if off_hand else "tp_per_hit"
    label = "TP per hit (off hand)" if off_hand else "TP per hit"
    return _stat(
        key, label, total, _timing_sources(rows), primary=not off_hand,
        group="Combat",
        formula=("weapon delay after Dual Wield / Martial Arts through the TP curve, "
                 "then Store TP"),
        order=315 if off_hand else 314)


def build_report(*, character: dict, sources: dict, mods: dict[int, int], sheet,
                 base_attributes: dict[str, int], base_hp: int, base_mp: int,
                 food: dict, updated: float) -> dict:
    """Build the full stat sheet with a source breakdown for every stat."""
    out = []
    out.append(_attack_entry(character, sources, mods, sheet, base_attributes))
    out.append(_accuracy_entry(character, sources, mods, sheet, base_attributes))
    out.append(_defense_entry(character, sources, mods, sheet, base_attributes))
    out.append(_evasion_entry(character, sources, mods, sheet, base_attributes))
    out.append(_hp_entry(character, sources, mods, sheet, base_attributes, base_hp))
    out.append(_mp_entry(character, sources, mods, sheet, base_attributes, base_mp))
    for index, (key, label, mod_id) in enumerate(ATTRIBUTE_LABELS):
        entry = _attribute_entry(key, label, mod_id, sources, sheet, base_attributes)
        entry["order"] = 20 + index
        out.append(entry)
    out.append(_haste_total_entry(sheet))
    out.append(_attack_interval_entry(sheet))
    out.append(_tp_per_hit_entry(sheet))
    if sheet.dual_wield:
        out.append(_tp_per_hit_entry(sheet, off_hand=True))
    seen = set()
    for key, label, mod_id, percent, scale, primary, group, order in RAW_STATS:
        if mod_id in seen:
            continue
        seen.add(mod_id)
        out.append(_raw_entry(key, label, mod_id, percent, scale, primary, group, order,
                              sources, mods, sheet))
    # Anything the curated table does not name still appears in the full sheet, so a
    # mod a future item grants cannot silently disappear from the report.
    for mod_id, value in sorted(mods.items()):
        mod_id = int(mod_id)
        if mod_id in seen or mod_id in _HIDDEN or not int(value):
            continue
        seen.add(mod_id)
        percent, scale, negate = _EXTRA_DISPLAY.get(mod_id, (False, 1, False))
        out.append(_raw_entry(
            "mod:%d" % mod_id, MOD_LABELS.get(mod_id, "Modifier %d" % mod_id),
            mod_id, percent, scale, False, "Other", 2000 + mod_id,
            sources, mods, sheet, negate=negate))
    out.sort(key=lambda entry: (entry["order"], entry["label"].casefold()))
    # Only rows that actually have a value (or are required derived rows) are useful.
    out = [entry for entry in out
           if entry["value"] or entry["key"] in ("hp", "mp")]
    return {
        "character_id": int(character.get("id", 0)),
        "name": str(character.get("name") or ""),
        "job": {
            "main_job": int(character.get("main_job") or 0),
            "main_level": int(character.get("main_level") or 0),
            "sub_job": int(character.get("sub_job") or 0),
            "sub_level": int(character.get("sub_level") or 0),
        },
        "food": {
            "item_id": int(food.get("item_id") or 0),
            "name": str(food.get("name") or ""),
            "until": float(food.get("until") or 0.0),
        },
        "updated": float(updated),
        "stats": out,
    }
