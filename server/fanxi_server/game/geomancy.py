"""Indi-/Geo- geomancy spell data and aura helpers.

The client data names the Colure effects GEO_* even when the aura comes from an Indi-
spell.  The server stores the same status ids, so one table drives both the party buff
and the enemy debuff halves.

A Geomancer keeps **one** aura up: the next Indi-/Geo- cast replaces the last.  The
friendly half carries stat modifiers; the hex half is read by the combat engine as a
percentage cut of the monster's own stat (the ids the engine reads are named below).
"""
from __future__ import annotations

from . import modifiers as mod

# The status ids, from LandSandBoat's ``data/status_effects.yaml`` (539-567/580).
GEO_REGEN = 539
GEO_POISON = 540
GEO_REFRESH = 541
GEO_HASTE = 580
# Hexes: each one cuts a monster stat by its aura's potency (10% here).
GEO_ATTACK_DOWN = 557       # wilt
GEO_DEFENSE_DOWN = 558      # frailty
GEO_MAGIC_DEF_DOWN = 559    # malaise: lowers the target's Magic Defense Bonus
GEO_MAGIC_EVASION_DOWN = 560  # languor: lowers the target's Magic Evasion
GEO_MAGIC_ACC_DOWN = 561    # vex: lowers the target's Magic Accuracy
GEO_EVASION_DOWN = 562      # torpor
GEO_MAGIC_ATK_DOWN = 563    # fade: lowers the target's Magic Attack Bonus
GEO_ACCURACY_DOWN = 564     # slip: lowers Accuracy and Ranged Accuracy
GEO_SLOW = 565
GEO_PARALYSIS = 566
GEO_WEIGHT = 567

# status id, modifier deltas, and whether the aura targets enemies.
INDI_EFFECTS: dict[str, tuple[int, dict[int, int], bool]] = {
    "regen": (GEO_REGEN, {mod.REGEN: 5}, False),
    "poison": (GEO_POISON, {}, True),
    "refresh": (GEO_REFRESH, {mod.REFRESH: 3}, False),
    "haste": (GEO_HASTE, {mod.HASTE_ABILITY: 1000}, False),
    "str": (542, {mod.STR: 10}, False),
    "dex": (543, {mod.DEX: 10}, False),
    "vit": (544, {mod.VIT: 10}, False),
    "agi": (545, {mod.AGI: 10}, False),
    "int": (546, {mod.INT: 10}, False),
    "mnd": (547, {mod.MND: 10}, False),
    "chr": (548, {mod.CHR: 10}, False),
    "fury": (549, {mod.ATT_PERCENT: 10, mod.RATT: 10}, False),
    "barrier": (550, {mod.DEF_PERCENT: 10}, False),
    "acumen": (551, {mod.MATT: 10}, False),
    "fend": (552, {mod.MDEF: 10}, False),
    "precision": (553, {mod.ACC: 10}, False),
    "voidance": (554, {mod.EVA: 10}, False),
    "focus": (555, {mod.MACC: 10}, False),
    "attunement": (556, {mod.MEVA: 10}, False),
    "wilt": (GEO_ATTACK_DOWN, {}, True),
    "frailty": (GEO_DEFENSE_DOWN, {}, True),
    "fade": (GEO_MAGIC_ATK_DOWN, {}, True),
    "malaise": (GEO_MAGIC_DEF_DOWN, {}, True),
    "slip": (GEO_ACCURACY_DOWN, {}, True),
    "torpor": (GEO_EVASION_DOWN, {}, True),
    "vex": (GEO_MAGIC_ACC_DOWN, {}, True),
    "languor": (GEO_MAGIC_EVASION_DOWN, {}, True),
    "slow": (GEO_SLOW, {}, True),
    "paralysis": (GEO_PARALYSIS, {}, True),
    "gravity": (GEO_WEIGHT, {}, True),
}


# BGWiki's Geomancy table, "Additional Potency from Geomancy+" -> the **Idris** column:
# the values a Geomancer holding the mythic reaches.  Idris is Geomancy +10 (one potency
# tier per point); the server has no skill tiers, so a wielder gets that column as-is.
# The second value is the hex potency -- the percentage the combat engine cuts -- and 0
# for a party aura.
IDRIS_GEOMANCY_PLUS = 10
IDRIS_EFFECTS: dict[str, tuple[dict[int, int], int]] = {
    "regen": ({mod.REGEN: 20}, 0),
    "refresh": ({mod.REFRESH: 10}, 0),
    "haste": ({mod.HASTE_ABILITY: 1100}, 0),
    "str": ({mod.STR: 20}, 0),
    "dex": ({mod.DEX: 20}, 0),
    "vit": ({mod.VIT: 20}, 0),
    "agi": ({mod.AGI: 20}, 0),
    "int": ({mod.INT: 20}, 0),
    "mnd": ({mod.MND: 20}, 0),
    "chr": ({mod.CHR: 20}, 0),
    "fury": ({mod.ATT_PERCENT: 27, mod.RATT: 27}, 0),
    "barrier": ({mod.DEF_PERCENT: 46}, 0),
    "acumen": ({mod.MATT: 30}, 0),
    "fend": ({mod.MDEF: 40}, 0),
    "precision": ({mod.ACC: 50}, 0),
    "voidance": ({mod.EVA: 60}, 0),
    "focus": ({mod.MACC: 50}, 0),
    "attunement": ({mod.MEVA: 60}, 0),
    "poison": ({}, 30),
    "wilt": ({}, 46),
    "frailty": ({}, 27),
    "malaise": ({}, 30),
    "languor": ({}, 50),
    "vex": ({}, 60),
    "torpor": ({}, 50),
    "fade": ({}, 40),
    "slip": ({}, 60),
    "slow": ({}, 5),
    "paralysis": ({}, 10),
    "gravity": ({}, 11),
}

# Every status a Geomancer can put up, for a caller that has to clear the last aura.
STATUSES = frozenset(effect for effect, _mods, _hostile in INDI_EFFECTS.values())


def family(name: str) -> str:
    """``Indi-haste`` -> ``haste``; an empty string for a non-geomancy spell."""
    key = " ".join(str(name or "").casefold().split())
    for prefix in ("indi-", "geo-"):
        if key.startswith(prefix):
            return key[len(prefix):]
    return ""


def bubble(name: str) -> str:
    """``Indi-haste`` -> ``indi``, ``Geo-frailty`` -> ``geo``; empty otherwise.

    A Geomancer runs two bubbles -- the Indi- aura around themself and the Geo- aura
    around the Luopan -- and each one replaces only itself, which is why Indi-haste and
    Geo-frailty are up together but a second Indi- cast takes the first one down.
    """
    key = " ".join(str(name or "").casefold().split())
    for prefix in ("indi-", "geo-"):
        if key.startswith(prefix):
            return prefix[:-1]
    return ""


def indi_effect(name: str):
    """Return (status, mods, hostile) for an Indi-/Geo- spell, or None."""
    aura = family(name)
    if not aura:
        return None
    return INDI_EFFECTS.get(aura)


def idris_effect(name: str):
    """(mods, hex potency) for an Idris wielder, or None when the spell is not geomancy."""
    aura = family(name)
    if not aura:
        return None
    return IDRIS_EFFECTS.get(aura)
