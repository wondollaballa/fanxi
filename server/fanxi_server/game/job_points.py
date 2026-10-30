"""The maxed job-point layer for every job.

Every job in this build is sent rank 20 in all ten category entries and 2,100 job
points spent (``zone.job_points`` / ``zone.job_points_detail``), which unlocks every
gift.  This module turns the BG-wiki Job Points table into the static part of that
layer:

* gift totals: the flat stats, percentages and skill bonuses from every gift;
* passive category bonuses: the categories that are always on, such as WHM's Regen
  duration or RDM's Enhancing/Enfeebling duration.

Categories that only apply while a job ability is active are listed by
:func:`missing_categories`; they need an ability hook and are not silently applied.
``data/job_points.json`` is the generated source table (job -> categories + gifts).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import effects, modifiers as mod

DATA = Path(__file__).resolve().parents[3] / "data" / "job_points.json"
ABILITY_STATUS_DATA = Path(__file__).resolve().parents[3] / "data" / "job_ability_status.json"
RANK = 20

JOB_KEYS = {
    1: "war", 2: "mnk", 3: "whm", 4: "blm", 5: "rdm", 6: "thf", 7: "pld",
    8: "drk", 9: "bst", 10: "brd", 11: "rng", 12: "sam", 13: "nin", 14: "drg",
    15: "smn", 16: "blu", 17: "cor", 18: "pup", 19: "dnc", 20: "sch", 21: "geo",
    22: "run",
}
JOB_NAMES = {
    "war": "Warrior", "mnk": "Monk", "whm": "White Mage", "blm": "Black Mage",
    "rdm": "Red Mage", "thf": "Thief", "pld": "Paladin", "drk": "Dark Knight",
    "bst": "Beastmaster", "brd": "Bard", "rng": "Ranger", "sam": "Samurai",
    "nin": "Ninja", "drg": "Dragoon", "smn": "Summoner", "blu": "Blue Mage",
    "cor": "Corsair", "pup": "Puppetmaster", "dnc": "Dancer", "sch": "Scholar",
    "geo": "Geomancer", "run": "Rune Fencer",
}

# Job-point gift spells, from LandSandBoat's ``RefreshGiftMods`` (the job-point gifts
# are not ordinary level rows).  A spell listed here is castable by that job's main job
# at level 99 and is refused to every other job: the "New Spell(s)" gifts at 100, 550
# and 1200 JP are what RDM's Fire V line and Addle II / Distract III / Frazzle III /
# Refresh III / Temper II come from.  Names are the spells table's own spelling; the
# resolver ignores a name the table does not have (GEO's Fira III line is imported
# later, for example).
SPELL_GRANTS: dict[int, dict[str, int]] = {
    3: {  # White Mage
        "Reraise IV": 100,
        "Full Cure": 1200,
    },
    4: {  # Black Mage
        "Fire VI": 100, "Blizzard VI": 100, "Aero VI": 100,
        "Stone VI": 100, "Thunder VI": 100, "Water VI": 100,
        "Aspir III": 550,
        "Death": 1200,
    },
    5: {  # Red Mage
        "Fire V": 100, "Blizzard V": 100, "Aero V": 100,
        "Stone V": 100, "Thunder V": 100, "Water V": 100,
        "Addle II": 550, "Distract III": 550, "Frazzle III": 550,
        "Refresh III": 1200, "Temper II": 1200,
    },
    7: {  # Paladin
        "Enlight II": 100,
    },
    8: {  # Dark Knight
        "Endark II": 100,
        "Drain III": 550,
    },
    10: {  # Bard
        "Fire Threnody II": 100, "Ice Threnody II": 100,
        "Wind Threnody II": 100, "Earth Threnody II": 100,
        "Ltng Threnody II": 100, "Water Threnody II": 100,
        "Light Threnody II": 100, "Dark Threnody II": 100,
    },
    13: {  # Ninja
        "Utsusemi San": 100,
    },
    21: {  # Geomancer
        "Fire V": 100, "Blizzard V": 100, "Aero V": 100,
        "Stone V": 100, "Thunder V": 100, "Water V": 100,
        "Aspir III": 550,
        "Fira III": 1200, "Blizzara III": 1200, "Aera III": 1200,
        "Stonera III": 1200, "Thundara III": 1200, "Watera III": 1200,
    },
    22: {  # Rune Fencer
        "Temper": 550,
    },
}


def _spell_key(name: str) -> str:
    return "".join(str(name or "").split()).casefold()


_ALL_SPELL_GRANT_KEYS = frozenset(
    _spell_key(name) for grants in SPELL_GRANTS.values() for name in grants)


def spell_grants(job_id: int) -> dict[str, int]:
    """The job-point spells one job's main job can learn, name -> JP required."""
    return dict(SPELL_GRANTS.get(int(job_id or 0), {}))


def all_spell_grants() -> frozenset[str]:
    """Every job-point spell name in the table, as casefolded keys."""
    return _ALL_SPELL_GRANT_KEYS


def is_job_point_spell(name: str) -> bool:
    """True when a spell is only learnable from a job-point gift on some job."""
    return _spell_key(name) in _ALL_SPELL_GRANT_KEYS

# Gift name -> (modifier id, multiplier).  The value is the number in the gift
# description; percentages stay in percent-integers, matching the modifier table.
GIFT_RULES: dict[str, tuple[tuple[int, int], ...]] = {
    "physical defense bonus": ((mod.DEF, 1),),
    "magic defense bonus": ((mod.MDEF, 1),),
    "physical attack bonus": ((mod.ATT, 1), (mod.RATT, 1)),
    "magic attack bonus": ((mod.MATT, 1),),
    "physical evasion bonus": ((mod.EVA, 1),),
    "magic evasion bonus": ((mod.MEVA, 1),),
    "physical accuracy bonus": ((mod.ACC, 1), (mod.RACC, 1)),
    "magic accuracy bonus": ((mod.MACC, 1),),
    "magic damage bonus": ((mod.MAGIC_DAMAGE, 1),),
    "magic burst damage bonus": ((mod.MAGIC_BURST_BONUS_CAPPED, 1),),
    "cure potency bonus": ((mod.CURE_POTENCY, 1),),
    "regen bonus": ((mod.REGEN_POTENCY, 1),),
    "fast cast effect": ((mod.FASTCAST, 1),),
    "healing magic cast time decrease": ((mod.FASTCAST, 1),),
    "healing magic cast time": ((mod.FASTCAST, 1),),
    "elemental celerity effect": ((mod.FASTCAST, 1),),
    "elemental celerity bonus": ((mod.FASTCAST, 1),),
    "song spellcasting time": ((mod.SONG_SPELLCASTING_TIME, 1),),
    "song effect duration": ((mod.SONG_DURATION_BONUS, 1),),
    "subtle blow effect": ((mod.SUBTLE_BLOW, 1),),
    "subtle blow effect bonus": ((mod.SUBTLE_BLOW, 1),),
    '"subtle blow" effect bonus': ((mod.SUBTLE_BLOW, 1),),
    "double attack effect": ((mod.DOUBLE_ATTACK, 1),),
    "triple attack chance": ((mod.TRIPLE_ATTACK, 1),),
    "martial arts effect": ((mod.MARTIAL_ARTS, 1),),
    "counter effect": ((mod.COUNTER, 1),),
    "critical damage bonus": ((mod.CRIT_DMG_INCREASE, 1),),
    "critical damage dealt bonus": ((mod.CRIT_DMG_INCREASE, 1),),
    "critical hit bonus": ((mod.CRIT_HIT_RATE, 100),),
    "critical defense bonus": ((mod.CRIT_DEF_BONUS, 1),),
    "weapon skill damage bonus": ((mod.WSD_ALL_HITS, 1),),
    "weapon skill damage": ((mod.WSD_ALL_HITS, 1),),
    "skillchain bonus": ((mod.SKILLCHAIN_BONUS, 1),),
    "fencer effect": ((mod.FENCER_TP_BONUS, 1),),
    'enhances "fencer" effect': ((mod.FENCER_TP_BONUS, 1),),
    "store tp effect": ((mod.STORETP, 1),),
    "dual wield effect": ((mod.DUAL_WIELD, 1),),
    # Red Mage's En-spell gifts.  LandSandBoat stores them on mod 432, the same
    # flat "Sword enhancement spell damage" line the Sworn R30 suit uses, and the
    # en-spell hit already reads that modifier for both hands.
    '"en"spell damage': ((mod.ENSPELL_DMG_BONUS, 1),),
    "enspell damage": ((mod.ENSPELL_DMG_BONUS, 1),),
}

SKILL_RULES: dict[str, int] = {
    "guarding skill bonus": 28,
    "parrying skill bonus": 31,
    "shield skill bonus": 30,
    "evasion skill bonus": 29,
    "archery skill bonus": 25,
    "marksmanship skill bonus": 26,
    "throwing skill bonus": 27,
    "healing magic skill bonus": 33,
    "divine magic skill bonus": 32,
    "enhancing magic skill bonus": 34,
    "enfeebling magic skill bonus": 35,
    "enfeebling magic bonus": 35,
    "elemental magic skill bonus": 36,
    "elemental skill bonus": 36,
    "dark magic skill bonus": 37,
    "summoning magic skill bonus": 38,
    "ninjutsu skill bonus": 39,
    "singing skill bonus": 40,
    "string instrument skill bonus": 41,
    "wind instrument skill bonus": 42,
    "blue magic skill bonus": 43,
    "geomancy skill bonus": 44,
    "handbell skill bonus": 45,
}

# Category name -> (modifier id, multiplier).  Only categories whose description is a
# permanent player stat belong here.  A category that says "while under the effects of"
# or "when ... activates" belongs to an ability hook, not this table.
CATEGORY_RULES: dict[str, tuple[tuple[int, int], ...]] = {
    "magic accuracy bonus": ((mod.MACC, 1),),
    "magic atk. bonus": ((mod.MATT, 1),),
    "magic attack bonus": ((mod.MATT, 1),),
    "magic damage bonus": ((mod.MAGIC_DAMAGE, 1),),
    "magic burst damage bonus": ((mod.MAGIC_BURST_BONUS_CAPPED, 1),),
    "magic burst enmity decrease": ((mod.ENMITY, -1),),
    "regen duration": ((mod.REGEN_DURATION, 1),),
    "enhancing magic duration": ((mod.ENH_MAGIC_DURATION_FLAT, 1),),
    "enfeebling magic duration": ((mod.ENF_MAG_DURATION_FLAT, 1),),
    "martial arts effect": ((mod.MARTIAL_ARTS, 1),),
    "ranged accuracy bonus": ((mod.RACC, 1),),
    "ninjutsu accuracy bonus": ((mod.MACC, 1),),
    # "song accuracy bonus" is not here: it is applied to songs only, by
    # zone._cast_numbers, so a Bard's nukes do not inherit it.
    "double attack effect": ((mod.ATT, 1),),
    "triple attack effect": ((mod.ATT, 1),),
    "kick attacks effect": ((mod.ATT, 1),),
    "zanshin effect": ((mod.ATT, 2),),
    "physical blue magic effect accuracy": ((mod.ACC, 1),),
    "blue magic point bonus": ((mod.BLUE_MAGIC_POINTS, 1),),
    "bar spell effect": ((mod.MDEF, 1),),
    "tactical parry effect": ((mod.COUNTER, 1),),
    "rune enchantment effect": ((mod.RUNE_ENCHANTMENT, 1),),
    "ninjutsu cast time": ((mod.NINJUTSU_FASTCAST, 1),),
    "elemental ninjutsu effect": ((mod.NINJUTSU_MAGIC_DAMAGE, 1),),
}

# Ability-conditional categories.  The tuple is the effect ids that switch the row on;
# the modifiers are per rank, multiplied by RANK when the ability is active.
CONDITIONAL_RULES: dict[str, tuple[tuple[int, ...], tuple[tuple[int, int], ...]]] = {
    "stratagem effect i": (
        (effects.PENURY, effects.PARSIMONY), ((mod.MACC, 1),)),
    "stratagem effect ii": (
        (effects.CELERITY, effects.ALACRITY), ((mod.FASTCAST, 1),)),
    "stratagem effect iii": (
        (effects.RAPTURE, effects.EBULLIENCE), ((mod.MAGIC_DAMAGE, 1),)),
    "mighty strikes effect": (
        (effects.MIGHTY_STRIKES,), ((mod.ACC, 1), (mod.RACC, 1))),
    "brazen rush effect": (
        (effects.BRAZEN_RUSH,), ((mod.ATT, 1), (mod.RATT, 1))),
    "berserk effect": (
        (effects.BERSERK,), ((mod.ATT, 1), (mod.RATT, 1))),
    "defender effect": (
        (effects.DEFENDER,), ((mod.DEF, 1),)),
    "warcry effect": (
        (effects.WARCRY,), ((mod.ATT, 1), (mod.RATT, 1))),
    "aggressor effect": (
        (effects.AGGRESSOR,), ((mod.ACC, 1), (mod.RACC, 1))),
    "hundred fists effect": (
        (effects.HUNDRED_FISTS,), ((mod.ACC, 1), (mod.RACC, 1))),
    "dodge effect": (
        (effects.DODGE,), ((mod.EVA, 1),)),
    "focus effect": (
        (effects.FOCUS,), ((mod.ACC, 1),)),
    "impetus effect": (
        (effects.IMPETUS,), ((mod.ATT, 1),)),
    "asylum effect": (
        (effects.ASYLUM,), ((mod.MEVA, 1),)),
    "divine seal effect": (
        (effects.DIVINE_SEAL,), ((mod.ENMITY, -1),)),
    "afflatus solace effect": (
        (effects.AFFLATUS_SOLACE,), ((mod.CURE_POTENCY, 1),)),
    "afflatus misery effect": (
        (effects.AFFLATUS_MISERY,), ((mod.MAGIC_DAMAGE, 1),)),
    "sacrosanctity effect": (
        (effects.SACROSANCTITY,), ((mod.MDEF, 1),)),
    "chainspell effect": (
        (effects.CHAINSPELL,), ((mod.MAGIC_DAMAGE, 1),)),
    "stymie effect": (
        (effects.STYMIE,), ((mod.ENF_MAG_DURATION_FLAT, 1),)),
    "composure effect": (
        (effects.COMPOSURE,), ((mod.ACC, 1),)),
    "saboteur effect": (
        (effects.SABOTEUR,), ((mod.MACC, 1),)),
    "manafont effect": (
        (effects.MANAFONT,), ((mod.MAGIC_DAMAGE, 1),)),
    "subtle sorcery effect": (
        (effects.SUBTLE_SORCERY,), ((mod.FASTCAST, 1),)),
    "elemental seal effect": (
        (effects.ELEMENTAL_SEAL,), ((mod.ENMITY, -1),)),
    "manawell effect": (
        (effects.MANAWELL,), ((mod.MAGIC_DAMAGE, 1),)),
    "enlight effect": (
        (effects.ENLIGHT,), ((mod.ACC, 1),)),
    "endark effect": (
        (effects.ENDARK,), ((mod.ATT, 1), (mod.RATT, 1), (mod.ACC, 1))),
    "azure lore effect": (
        (effects.AZURE_LORE,), ((mod.MAGIC_DAMAGE, 1),)),
    "burst affinity bonus": (
        (effects.BURST_AFFINITY,), ((mod.MAGIC_DAMAGE, 1),)),
    "unbridled learning effect": (
        (effects.UNBRIDLED_LEARNING,), ((mod.MAGIC_DAMAGE, 1),)),
    "spirit surge effect": (
        (effects.SPIRIT_SURGE,), ((mod.DMG_RATING, 1),)),
    "perfect counter effect": (
        (effects.PERFECT_COUNTER,), ((mod.VIT, 1),)),
    "footwork effect": (
        (effects.FOOTWORK,), ((mod.ATT, 1),)),
    "counterstance effect": (
        (effects.COUNTERSTANCE,), ((mod.DEX, 1),)),
    "sneak attack effect": (
        (effects.SNEAK_ATTACK,), ((mod.DEX, 1),)),
    "trick attack effect": (
        (effects.TRICK_ATTACK,), ((mod.AGI, 1),)),
    "konzen-ittai effect": (
        (effects.KONZEN_ITTAI,), ((mod.SKILLCHAIN_BONUS, 1),)),
    "soul voice effect": (
        (effects.SOUL_VOICE,), ((mod.FASTCAST, 1),)),
    "pianissimo effect": (
        (effects.PIANISSIMO,), ((mod.FASTCAST, 1),)),
}

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _number(text: str) -> int:
    """The first number in a description, rounded to a whole modifier value."""
    match = _NUMBER.search(str(text or "").replace(",", ""))
    return int(round(abs(float(match.group(0))))) if match else 0


def _name(record: dict, key: str) -> str:
    return " ".join(str(record.get(key) or "").split()).casefold()


def _description(record: dict) -> str:
    return " ".join(str(record.get("description") or "").split())


def _value_text(record: dict) -> str:
    """The field that carries the per-tier number: effect, then description."""
    return " ".join(str(record.get("effect") or record.get("description") or "").split())


@lru_cache(maxsize=1)
def _table() -> dict:
    try:
        return json.loads(DATA.read_text(encoding="utf-8")).get("jobs", {})
    except Exception:
        return {}


@lru_cache(maxsize=256)
def _job(job_id: int) -> dict:
    return _table().get(JOB_KEYS.get(int(job_id), ""), {})


@lru_cache(maxsize=1)
def _ability_status_table() -> dict:
    try:
        return json.loads(ABILITY_STATUS_DATA.read_text(encoding="utf-8"))
    except Exception:
        return {"abilities": {}, "categories": {}}


def ability_status(ability_id: int) -> int | None:
    """The client status id for an ability that has one, or None."""
    entry = _ability_status_table().get("abilities", {}).get(str(int(ability_id)))
    return int(entry["status"]) if entry else None


@lru_cache(maxsize=1)
def _status_ability_names() -> dict[int, str]:
    """Status effect id -> the job ability that puts it up."""
    out: dict[int, str] = {}
    for entry in _ability_status_table().get("abilities", {}).values():
        try:
            status = int(entry.get("status") or 0)
        except (TypeError, ValueError):
            continue
        if status:
            out[status] = str(entry.get("name") or "Ability")
    return out


def ability_name_for_status(status_id: int) -> str | None:
    """The ability behind one active status effect, or None for a spell/song buff."""
    return _status_ability_names().get(int(status_id))


def ability_name(ability_id: int) -> str | None:
    entry = _ability_status_table().get("abilities", {}).get(str(int(ability_id)))
    return str(entry.get("name")) if entry else None


def _category_ability(job_id: int, category_name: str) -> int | None:
    return _ability_status_table().get("categories", {}).get(
        f"{JOB_KEYS.get(int(job_id), '')}|{category_name}")


def _category_label(job_id: int, category_name: str) -> str:
    ability_id = _category_ability(job_id, category_name)
    if ability_id is None:
        # The category table is hand-written with its own capitalisation; match it
        # case-insensitively so a lower-cased data row still names its ability.
        wanted = category_name.casefold()
        prefix = JOB_KEYS.get(int(job_id), "") + "|"
        for key, value in _ability_status_table().get("categories", {}).items():
            if key.startswith(prefix) and key[len(prefix):].casefold() == wanted:
                ability_id = value
                break
    name = ability_name(int(ability_id)) if ability_id is not None else None
    return name or category_name


def _ability_categories(ability_id: int) -> list[tuple[int, str, dict]]:
    """(job id, category name, category record) rows for one ability."""
    out = []
    for key, aid in _ability_status_table().get("categories", {}).items():
        if int(aid) != int(ability_id):
            continue
        job_key, _, category_name = key.partition("|")
        job_id = next((jid for jid, key2 in JOB_KEYS.items() if key2 == job_key), 0)
        for category in _job(job_id).get("categories", ()):
            if category.get("category") == category_name:
                out.append((job_id, category_name, category))
                break
    return out


def _duration_bonus(effect_text: str) -> int:
    match = re.search(r"duration by (\d+)", effect_text.casefold())
    return int(match.group(1)) * RANK if match else 0


def _recast_bonus(effect_text: str) -> int:
    match = re.search(r"recast (?:time )?by (\d+)", effect_text.casefold())
    return int(match.group(1)) * RANK if match else 0


_SKIP_GENERIC = (
    "pet", "wyvern", "automaton", "avatar", "spirit", "familiar", "charm",
    "reward", "ready", "sic", "snarl", "spur", "run wild", "blood pact",
    "healing breath", "phantom roll", "roll ", "quick draw",
)
_GENERIC_PATTERNS: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = (
    (r"physical accuracy(?: bonus)? by (\d+)", ((mod.ACC, 1), (mod.RACC, 1))),
    (r"physical attack by (\d+)", ((mod.ATT, 1), (mod.RATT, 1))),
    (r"physical defense by (\d+)", ((mod.DEF, 1),)),
    (r"physical evasion by (\d+)", ((mod.EVA, 1),)),
    (r"magic accuracy by (\d+)", ((mod.MACC, 1),)),
    (r"(?<!magic )accuracy by (\d+)", ((mod.ACC, 1),)),
    (r"magic attack by (\d+)", ((mod.MATT, 1),)),
    (r"magic defense by (\d+)", ((mod.MDEF, 1),)),
    (r"magic evasion by (\d+)", ((mod.MEVA, 1),)),
    (r"ranged attack (?:power )?by (\d+)", ((mod.RATT, 1),)),
    (r"cast(?:ing)? time by (\d+)", ((mod.FASTCAST, 1),)),
    (r"damage taken by (\d+)", ((mod.DMG, -100),)),
    (r"ranged accuracy by (\d+)", ((mod.RACC, 1),)),
    (r"(?:magic damage|elemental magic damage|damage dealt) by (\d+)", ((mod.MAGIC_DAMAGE, 1),)),
    (r"critical hit rate by (\d+)", ((mod.CRIT_HIT_RATE, 100),)),
    (r"critical damage.*? by (\d+)", ((mod.CRIT_DMG_INCREASE, 1),)),
    (r"skillchain damage by (\d+)", ((mod.SKILLCHAIN_BONUS, 1),)),
    (r"tp bonus by (\d+)", ((mod.TP_BONUS, 1),)),
    (r"reduce enmity by (\d+)", ((mod.ENMITY, -1),)),
    (r"(?:increase )?(?:static )?enmity by (\d+)", ((mod.ENMITY, 1),)),
    (r"(?:increase )?str by (\d+)", ((mod.STR, 1),)),
    (r"(?:increase )?dex by (\d+)", ((mod.DEX, 1),)),
    (r"(?:increase )?vit by (\d+)", ((mod.VIT, 1),)),
    (r"(?:increase )?agi by (\d+)", ((mod.AGI, 1),)),
    (r"(?:increase )?int by (\d+)", ((mod.INT, 1),)),
    (r"(?:increase )?mnd by (\d+)", ((mod.MND, 1),)),
    (r"(?:increase )?chr by (\d+)", ((mod.CHR, 1),)),
    (r"cure power by (\d+)", ((mod.CURE_POTENCY, 1),)),
)


def _generic_mods(category: dict) -> dict[int, int]:
    """Best-effort stat rows for an ability category that has a status icon.

    This intentionally only maps plain stat phrases.  Duration, recast, chance,
    potency, pet and system rows are left to their dedicated hooks.
    """
    text = _value_text(category).casefold()
    description = _description(category).casefold()
    combined = description + " " + text
    if any(re.search(r"\b" + re.escape(word) + r"\b", combined) for word in _SKIP_GENERIC):
        return {}
    mods: dict[int, int] = {}
    for pattern, mapping in _GENERIC_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        value = int(match.group(1)) * RANK
        for mod_id, scale in mapping:
            mods[int(mod_id)] = mods.get(int(mod_id), 0) + value * scale
    return mods


def category_generic_rule(job_id: int, category_name: str) -> dict | None:
    """The status trigger and parsed effects for one category, if it has an icon."""
    ability = _ability_status_table().get("categories", {}).get(
        f"{JOB_KEYS.get(int(job_id), '')}|{category_name}")
    if ability is None:
        return None
    status = ability_status(int(ability))
    if status is None:
        return None
    for category in _job(job_id).get("categories", ()):
        if category.get("category") != category_name:
            continue
        return {
            "ability": int(ability),
            "status": status,
            "mods": _generic_mods(category),
            "duration_bonus": _duration_bonus(_value_text(category)),
            "recast_bonus": _recast_bonus(_value_text(category)),
        }
    return None


def ability_effect(ability_id: int) -> dict | None:
    """Fallback status/duration for an ability that has no static AbilityEffect."""
    status = ability_status(ability_id)
    if status is None:
        return None
    rows = _ability_categories(ability_id)
    if not rows:
        return None
    duration = 60.0
    duration_bonus = 0
    recast_bonus = 0
    has_effect = False
    for _job_id, _name, category in rows:
        rule = category_generic_rule(_job_id, category["category"])
        if rule is None:
            continue
        duration_bonus += rule["duration_bonus"]
        recast_bonus += rule["recast_bonus"]
        if rule["mods"]:
            has_effect = True
    if not has_effect and not duration_bonus and not recast_bonus:
        return None
    return {
        "status": int(status),
        "duration": duration + duration_bonus,
        "recast_bonus": recast_bonus,
    }


@lru_cache(maxsize=256)
def gift_totals(job_id: int) -> dict:
    """The cumulative static gift totals for one job at 2,100 JP spent."""
    job = _job(job_id)
    mods: dict[int, int] = {}
    skills: dict[int, int] = {}
    flags: set[str] = set()
    unclassified: list[str] = []
    for gift in job.get("gifts", ()):
        name = _name(gift, "gift")
        description = _value_text(gift)
        value = _number(description)
        if name in GIFT_RULES:
            for mod_id, scale in GIFT_RULES[name]:
                mods[int(mod_id)] = mods.get(int(mod_id), 0) + value * scale
        elif name in SKILL_RULES:
            skill = SKILL_RULES[name]
            skills[skill] = skills.get(skill, 0) + value
        elif name.startswith("superior "):
            flags.add(name)
        elif "master" in name:
            flags.add("master")
            # The Master gift ("★Master!") cuts the one-hour abilities' recast by
            # 15 minutes.  It is a real modifier, not just the Master stars.
            if "one-hour" in description.casefold() and value:
                mods[mod.ONE_HOUR_RECAST] = (
                    mods.get(mod.ONE_HOUR_RECAST, 0) + value)
        elif name.startswith("new "):
            flags.add("new_spells")
        elif name in {"capacity point bonus", "capacity points bonus"}:
            flags.add("capacity_points")
        else:
            unclassified.append(name)
    return {
        "mods": mods,
        "skills": skills,
        "flags": flags,
        "unclassified": sorted(set(unclassified)),
    }


@lru_cache(maxsize=256)
def category_mods(job_id: int) -> dict[int, int]:
    """Permanent stat bonuses from a job's category entries at rank 20."""
    mods: dict[int, int] = {}
    for category in _job(job_id).get("categories", ()):
        name = _name(category, "category")
        if name not in CATEGORY_RULES:
            continue
        value = _number(_value_text(category)) * RANK
        if not value:
            continue
        for mod_id, scale in CATEGORY_RULES[name]:
            mods[int(mod_id)] = mods.get(int(mod_id), 0) + value * scale
    return mods


def conditional_sources(job_id: int, active_effects) -> list[dict]:
    """Per-ability modifiers from the job-point categories that are live right now.

    The stat sheet merges these; the launcher's checkparam-style sheet keeps the ability
    name beside each row so a buffed Attack total can say which job ability supplied it.
    A category is only counted once, even when several of its trigger effects are up.
    """
    active = {int(effect) for effect in active_effects or ()}
    out: list[dict] = []
    for category in _job(job_id).get("categories", ()):
        name = _name(category, "category")
        rule = CONDITIONAL_RULES.get(name)
        if rule is None:
            continue
        triggers, per_rank = rule
        if not active.intersection(triggers):
            continue
        value = _number(_value_text(category)) * RANK
        if not value:
            continue
        mods = {int(mod_id): value * int(scale) for mod_id, scale in per_rank if scale}
        if mods:
            out.append({"name": _category_label(job_id, str(name)), "mods": mods})
    for category in _job(job_id).get("categories", ()):
        name = str(category.get("category") or "")
        key = name.casefold()
        if key in CONDITIONAL_RULES or key in CATEGORY_RULES:
            continue
        rule = category_generic_rule(job_id, name)
        if rule is None or rule["status"] not in active:
            continue
        if rule["mods"]:
            out.append({"name": _category_label(job_id, name), "mods": dict(rule["mods"])})
    return out


def conditional_mods(job_id: int, active_effects) -> dict[int, int]:
    """Modifiers from ability-conditional categories for the effects that are active."""
    mods: dict[int, int] = {}
    for source in conditional_sources(job_id, active_effects):
        for mod_id, value in source["mods"].items():
            mods[int(mod_id)] = mods.get(int(mod_id), 0) + int(value)
    return mods


def category_total(job_id: int, category_name: str) -> int:
    """The total value of one category at rank 20 (0 when it is not on the job)."""
    wanted = " ".join(str(category_name or "").split()).casefold()
    for category in _job(job_id).get("categories", ()):
        if _name(category, "category") == wanted:
            return _number(_value_text(category)) * RANK
    return 0


@lru_cache(maxsize=256)
def combat_mods(job_id: int) -> dict[int, int]:
    """Gift + passive category modifiers merged into ``combat_mods()``."""
    out = dict(gift_totals(job_id)["mods"])
    for mod_id, value in category_mods(job_id).items():
        out[int(mod_id)] = out.get(int(mod_id), 0) + int(value)
    return out


def skill_bonus(job_id: int) -> dict[int, int]:
    """Skill id -> gift skill bonus for the current main job."""
    return dict(gift_totals(job_id)["skills"])


def implemented_categories() -> set[str]:
    """Category names that are now applied by :func:`category_mods`."""
    return {name for name in CATEGORY_RULES}


# Categories handled somewhere other than category_mods(): SCH Light Arts feeds the
# Regen duration formula through the job-point rank, so it is accounted for.
HANDLED = {
    1: {"Mighty Strikes Effect", "Brazen Rush Effect", "Berserk Effect", "Defender Effect",
        "Warcry Effect", "Aggressor Effect", "Retaliation Effect", "Restraint Effect",
        "Double Attack effect"},
    2: {"Hundred Fists Effect", "Dodge Effect", "Focus Effect", "Impetus Effect",
        "Chakra Effect", "Perfect Counter Effect", "Footwork Effect",
        "Counterstance Effect", "Inner Strength Effect", "Kick Attacks Effect"},
    3: {"Asylum Effect", "Divine Seal Effect", "Afflatus Solace Effect",
        "Afflatus Misery Effect", "Sacrosanctity Effect", "Benediction Effect",
        "Bar Spell Effect"},
    4: {"Manafont Effect", "Subtle Sorcery Effect", "Elemental Seal Effect",
        "Manawell Effect", "Mana Wall Effect", "Enmity Douse Recast"},
    5: {"Chainspell Effect", "Stymie Effect", "Composure Effect", "Saboteur Effect",
        "Convert Effect", "Quick Magic Effect"},
    6: {"Sneak Attack Effect", "Trick Attack Effect", "Triple Attack Effect",
        "Steal Recast", "Mug Effect", "Despoil Effect", "Larceny Effect", "Bully Effect"},
    7: {"Enlight Effect", "Shield Bash Effect", "Sentinel Effect.", "Palisade Effect"},
    9: {"Pet Accuracy Bonus", "Reward Effect", "Unleash Effect", "Spur Effect",
         "Familiar Effect", "Pet Attack Speed", "Ready Effect", "Pet Enmity",
         "Charm Success Rate", "Run Wild Duration"},
    10: {"Soul Voice Effect", "Pianissimo Effect", "Song Accuracy Bonus",
         "Minne Effect", "Minuet Effect", "Lullaby Duration", "Requiem Effect"},
    12: {"Meditate Effect", "Konzen-ittai Effect", "Zanshin Effect"},
    8: {"Endark effect", "Weapon Bash Effect", "Blood Weapon Effect",
        "Soul Enslavement Effect", "Nether Void Effect"},
    11: {"Eagle Eye Shot Effect", "Double Shot Effect", "Decoy Shot Effect",
         "Shadowbind Duration"},
    14: {"Spirit Surge Effect", "Wyvern Max HP Bonus", "Jump Effect", "High Jump Effect",
         "Wyvern Attr. Increase Effect", "Spirit Link Effect", "Wyvern Breath Effect"},
    15: {"Avatar/Spirit Accuracy Bonus", "Avatar/Spirit Physical Attack",
         "Astral Flow Effect", "Astral Conduit Effect", "Avatar's Favor Effect",
         "Blood Pact Damage", "Elemental Siphon Effect", "Mana Cede Effect",
         "Avatar/Spirit Magic Accuracy Bonus", "Avatar/Spirit Mag. Damage"},
    16: {"Azure Lore Effect", "Burst Affinity Bonus", "Unbridled Learning Effect",
         "Unbridled Learning Effect II", "Physical Blue Magic Effect Accuracy",
         "Blue Magic Point Bonus", "Unbridled Wisdom Effect"},
    17: {"Phantom Roll Duration", "Quick Draw Effect", "Wild Card Effect",
         "Cutting Cards Effect", "Random Deal Effect", "Triple Shot Effect",
         "Bust Evasion", "Optimal Range", "Ammo Consumption"},
    13: {"Ninjutsu Cast Time", "Elemental Ninjutsu Effect", "Mijin Gakure Effect",
         "Tactical Parry Effect"},
    18: {"Automaton Max HP and Automaton Max MP Bonus", "Overdrive Effect",
         "Repair Effect", "Tactical Switch", "Deus Ex Automata Recast",
         "Activate Effect", "Cooldown Effect", "Deactivate Effect",
         "Heady Artifice Effect"},
    19: {"Waltz Potency", "Samba Duration", "Trance Effect", "Grand Pas Effect",
         "Step Duration", "Contradance Effect", "Jig Duration", "Flourish I Effect",
         "Flourish II Effect", "Flourishes III Effect"},
    20: {"Light Arts Effect", "Dark Arts Effect", "Stratagem Effect I",
         "Stratagem Effect II", "Stratagem Effect III", "Stratagem Effect IV",
         "Tabula Rasa Effect", "Sublimation Effect", "Caper Emissarius Effect",
         "Modus Veritas Effect"},
    21: {"Bolster Effect", "Blaze of Glory Effect", "Concentric Pulse Effect",
         "Life Cycle Effect", "Indicolure Spell Effect Dur."},
    22: {"Elemental Sforzo Effect", "Odyllic Subterfuge Effect", "Swordplay Effect",
         "Swipe Effect", "Embolden Effect", "Vivacious Pulse",
         "Rune Enchantment Effect"},
}


def missing_categories(job_id: int) -> list[dict]:
    """The category rows that still need an ability hook for one job."""
    out = []
    handled = HANDLED.get(int(job_id), set())
    for category in _job(job_id).get("categories", ()):
        name = str(category.get("category") or "")
        if name.casefold() in CATEGORY_RULES or name in handled:
            continue
        rule = category_generic_rule(job_id, name)
        if rule and (rule["mods"] or rule["duration_bonus"] or rule["recast_bonus"]):
            continue
        out.append(category)
    return out


def audit() -> dict:
    """What is accounted for and what still needs an ability hook."""
    rows = {}
    for job_id, key in JOB_KEYS.items():
        rows[key] = {
            "name": JOB_NAMES[key],
            "gifts": gift_totals(job_id),
            "category_mods": category_mods(job_id),
            "missing": missing_categories(job_id),
            "categories": len(_job(job_id).get("categories", ())),
            "gift_rows": len(_job(job_id).get("gifts", ())),
        }
    return rows
