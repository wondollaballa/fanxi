"""Retail physical damage.

Four stages, the way retail does it:

1. base damage = weapon damage rating + fSTR
2. ratio      = Attack / Defense
3. pDIF       = a multiplier from the ratio, weapon type, crit and level difference
4. damage     = floor(base damage * pDIF), then the target's damage-taken gear

Attack and Defense never touch damage directly -- they only choose the multiplier, which
is why a gear swap that adds Attack can move damage by more than the Attack it added (or
by nothing at all, once the ratio is past the weapon's pDIF cap).

The formulas follow LandSandBoat's ``scripts/combat/physical_utilities.lua`` and
``physical_hit_rate.lua``; the numbers and sources are in ``docs/combat-damage.md``.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import modifiers as mod

# --- constants ------------------------------------------------------------------------------

# Pre-randomizer pDIF caps by weapon skill id (docs/combat-damage.md, "pDIF").
PDIF_WEAPON_CAP = {
    1: 3.5,    # hand-to-hand
    2: 3.25,   # dagger
    3: 3.25,   # sword
    4: 3.75,   # great sword
    5: 3.25,   # axe
    6: 3.75,   # great axe
    7: 4.0,    # scythe
    8: 3.75,   # polearm
    9: 3.25,   # katana
    10: 3.5,   # great katana
    11: 3.25,  # club
    12: 3.75,  # staff
    25: 3.25,  # archery
    26: 3.5,   # marksmanship
    27: 3.25,  # throwing
}
DEFAULT_PDIF_CAP = 3.0

# Weapon classes that use the two-handed STR/DEX multipliers.
TWO_HANDED_SKILLS = frozenset({4, 6, 7, 8, 10, 12})
H2H_SKILL = 1

# STR -> Attack and DEX -> Accuracy, current retail (settings/default/main.lua).
STR_TO_ATT_TWO_HANDED = 1.0
STR_TO_ATT_H2H = 1.0
STR_TO_ATT_MAIN = 0.75
STR_TO_ATT_OFF_HAND = 0.5
DEX_TO_ACC = 0.75

# LandSandBoat's scripts/data/level_correction.lua: the zones where the level-correction
# term still applies.  Every other zone (Adoulin, Escha, Ambuscade, anything holding a
# mob over 99) ignores the level difference.
LEVEL_CORRECTION_ZONES = frozenset({
    1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 19, 21, 23, 24, 25, 26, 27, 28, 29,
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 51, 54, 55,
    56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74, 75, 76, 77, 78, 79,
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100,
    101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117,
    118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 132, 134, 135, 136,
    137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153,
    154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170,
    172, 173, 174, 175, 176, 177, 178, 180, 181, 182, 183, 184, 185, 186, 187, 188, 191,
    192, 193, 194, 195, 196, 197, 198, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209,
    211, 212, 213, 215, 216, 217, 218, 220, 221, 222, 223, 224, 225, 226, 227, 228, 253,
    254, 255, 279, 294, 295, 296, 297, 298,
})

# Hit-rate caps: 1H main hand, H2H and pets reach 99%, two-handed and off-hand 95%.
HIT_RATE_CAP_ONE_HANDED = 0.99
HIT_RATE_CAP_TWO_HANDED = 0.95
HIT_RATE_CAP_MOB = 0.95
HIT_RATE_FLOOR_PC = 0.20

# Shield size -> base block rate, and how much of a blocked hit the shield eats.
# The rate table is retail's; the absorption table is an approximation (retail's own
# reference server leaves shield absorption at zero and only flags the block).
SHIELD_BLOCK_RATE = {1: 55, 2: 40, 3: 45, 4: 30, 5: 50, 6: 100}
SHIELD_ABSORB = {1: 0.28, 2: 0.36, 3: 0.44, 4: 0.50, 5: 0.60, 6: 0.60}
PARRY_REDUCTION = 0.5
GUARD_REDUCTION = 0.5
PARRY_CAP = 25
GUARD_CAP = 25


def level_corrected(zone: int) -> bool:
    """True in the zones where the attacker/target level difference moves the ratio."""
    return int(zone) in LEVEL_CORRECTION_ZONES


# --- stat helpers ---------------------------------------------------------------------------

def acc_from_skill(skill: int) -> int:
    """Skill value -> accuracy, with the game's compression past 200.

    A+ skill is 424, which is worth 399 accuracy, not 424: the curve gives 0.9 per point
    from 200 to 400 and 0.8 from 400 up.
    """
    skill = max(0, int(skill))
    if skill > 600:
        return int((skill - 600) * 0.9) + 540
    if skill > 400:
        return int((skill - 400) * 0.8) + 380
    if skill > 200:
        return int((skill - 200) * 0.9) + 200
    return skill


def weapon_rank(weapon_dmg: int, *, h2h: bool = False) -> int:
    """Weapon damage rating -> weapon rank, which caps fSTR."""
    damage = max(0, int(weapon_dmg)) + (3 if h2h else 0)
    return damage // 9


def fstr(attacker_str: int, target_vit: int, rank: int, *, is_mob: bool = False,
         level: int = 99) -> int:
    """The STR versus VIT term added to weapon damage."""
    diff = int(attacker_str) - int(target_vit)

    if is_mob:
        # Mobs and pets use a coarser table and a level-scaled clamp.
        if diff >= 36:
            raw = (diff - 4) / 4
        elif diff >= 26:
            raw = (diff - 3) / 4
        elif diff >= 17:
            raw = (diff - 2) / 4
        elif diff >= 4:
            raw = (diff - 1) / 4
        elif diff >= -8:
            raw = diff / 4
        elif diff >= -13:
            raw = (diff + 1) / 4
        elif diff >= -19:
            raw = (diff + 3) / 4
        elif diff >= -32:
            raw = (diff + 4) / 4
        elif diff >= -42:
            raw = (diff + 5) / 4
        elif diff >= -54:
            raw = (diff + 6) / 4
        elif diff >= -67:
            raw = (diff + 7) / 4
        elif diff >= -76:
            raw = (diff + 8) / 4
        else:
            raw = (diff + 9) / 4
        value = int(raw)
        low = -1 - int(level / 5)
        high = int(level / 5) + 5
        return max(low, min(high, value))

    lower_cap = (7 + rank * 2) * -2
    upper_cap = (14 + rank * 2) * 2
    diff = max(lower_cap, min(upper_cap, diff))

    if diff >= 12:
        raw = diff + 4
    elif diff >= 6:
        raw = diff + 6
    elif diff >= 1:
        raw = diff + 7
    elif diff >= -2:
        raw = diff + 8
    elif diff >= -7:
        raw = diff + 9
    elif diff >= -15:
        raw = diff + 10
    elif diff >= -21:
        raw = diff + 12
    else:
        raw = diff + 13

    value = raw / 4
    low = -1 if rank == 0 else -rank
    return int(max(low, min(rank + 8, value)))


# --- pDIF -----------------------------------------------------------------------------------

def _wratio_caps_pc(wratio: float, final_cap: float) -> tuple[float, float]:
    """Lower and upper pDIF bounds for a player attacker."""
    if wratio < 0.5:
        upper = wratio + 0.5
    elif wratio < 0.7:
        upper = 1.0
    elif wratio < 1.2:
        upper = wratio + 0.3
    elif wratio < 1.5:
        upper = wratio + wratio * 0.25
    else:
        upper = min(wratio + 0.375, final_cap)

    if wratio < 0.38:
        lower = 0.0
    elif wratio < 1.25:
        lower = wratio * 1176 / 1024 - 448 / 1024
    elif wratio < 1.51:
        lower = 1.0
    elif wratio < 2.44:
        lower = wratio * 1176 / 1024 - 775 / 1024
    else:
        lower = min(wratio - 0.375, final_cap)

    return lower, min(upper, final_cap)


def _wratio_caps_mob(wratio: float, final_cap: float) -> tuple[float, float]:
    """Lower and upper pDIF bounds for a monster or pet attacker."""
    if wratio < 0.55:
        upper = 0.6 + 760 / 1024 * wratio
    elif wratio <= 0.8:
        upper = 1.0
    elif wratio < 1.2:
        upper = 1 + 1127 / 1024 * (wratio - 0.8)
    elif wratio < 1.5:
        upper = 1474 / 1024 + 1105 / 1024 * (wratio - 1235 / 1024)
    else:
        upper = 1803 / 1024 + 1070 / 1024 * (wratio - 1.5)

    if wratio <= 0.4:
        lower = 0.25
    elif wratio < 1.35:
        lower = 0.25 + (827 / 1024) * (wratio - 0.4)
    elif wratio <= 1.60:
        lower = 1.0
    else:
        lower = 1 + (1120 / 1024) * (wratio - 1.59)

    return min(lower, final_cap), min(upper, final_cap)


def _spike_ratio(wratio: float, *, is_pc: bool) -> float:
    """Chance of the pDIF=1 'spike' that makes a mid-ratio hit land exactly at 1.0."""
    if is_pc:
        if 0.5 < wratio < 1.5:
            return max(0.0, min(1 / 3, (0.5 - abs(wratio - 1)) * 1.2))
        return 0.0
    if 0.0 < wratio < 0.75:
        value = -5 / 9 + (10 / 9) * wratio
    elif wratio <= 1.3:
        value = 0.3
    else:
        value = 5 / 3 - (270 / 256) * wratio
    return max(0.0, min(0.3, value))


def level_term(attacker_level: int, target_level: int, *, is_pc: bool,
               corrected: bool) -> float:
    """The level-correction term added to wRatio.

    Players only ever lose from it, monsters only ever gain, and neither happens in a
    zone without level correction.
    """
    if not corrected:
        return 0.0
    difference = max(-38, min(38, int(attacker_level) - int(target_level)))
    term = difference * 3 / 64
    if not is_pc and term < 0:
        return 0.0
    if is_pc and term > 0:
        return 0.0
    return term


def pdif(*, attack: int, defense: int, weapon_skill: int, is_critical: bool,
         attacker_level: int, target_level: int, is_pc: bool,
         corrected: bool, damage_limit: int = 0, damage_limitp: int = 0,
         rng: random.Random | None = None) -> float:
    """The multiplier that turns base damage into damage."""
    rng = rng or random
    defense = max(1, int(defense))
    ratio = max(1, int(attack)) / defense
    term = level_term(attacker_level, target_level, is_pc=is_pc, corrected=corrected)
    wratio = ratio + (1.0 if is_critical else 0.0) + term

    limit_plus = int(damage_limit) / 100
    limit_percent = 1 + int(damage_limitp) / 100

    if is_pc:
        final_cap = (PDIF_WEAPON_CAP.get(int(weapon_skill), DEFAULT_PDIF_CAP)
                     + limit_plus) * limit_percent
        final_cap += (1.0 if is_critical else 0.0) + term
    else:
        base = 2.0 if corrected else 4.0
        final_cap = (base + limit_plus) * limit_percent
        final_cap += (1.0 if (corrected and is_critical) else 0.0) + term

    if rng.random() <= _spike_ratio(wratio, is_pc=is_pc):
        return max(0.0, 1.0 + term)

    if is_pc:
        lower, upper = _wratio_caps_pc(wratio, final_cap)
    else:
        lower, upper = _wratio_caps_mob(wratio, final_cap)

    # Retail picks one of two lower bounds half the time; it only bites below ratio 1.
    upper = max(upper, 0.5 if rng.randint(0, 1) == 0 else 0.0)
    lower = max(lower, 0.0)
    if upper <= 0:
        return 0.0

    low_thousandths = int(lower * 1000)
    high_thousandths = int(upper * 1000)
    if high_thousandths <= low_thousandths:
        value = low_thousandths / 1000
    else:
        value = rng.randint(low_thousandths, high_thousandths) / 1000

    value *= 1 + rng.randint(0, 5) * 0.01
    return value


# --- parry, guard and shield block ----------------------------------------------------------

def parry_rate(defender_skill: int, attacker_skill: int) -> int:
    """Chance in percent that a player parries, clamped to retail's 5-25% band."""
    delta = int(defender_skill) - int(attacker_skill)
    if delta <= 5:
        rate = 10 + (delta - 6) / (36 / 9)
    else:
        rate = 10 + (delta - 6) / (60 / 9)
    return max(5, min(PARRY_CAP, int(rate)))


def guard_rate(defender_skill: int, attacker_skill: int) -> int:
    """Chance in percent that a hand-to-hand player guards."""
    delta = int(defender_skill) - int(attacker_skill)
    if delta <= 6:
        rate = 10 + delta / (36 / 9)
    else:
        rate = 10 + delta / (60 / 9)
    return max(5, min(GUARD_CAP, int(rate)))


def block_rate(shield_size: int, block_skill: int, attacker_skill: int) -> int:
    """Chance in percent that a shield blocks, from shield size and the skill gap."""
    base = SHIELD_BLOCK_RATE.get(int(shield_size), 0)
    rate = base + (int(block_skill) - int(attacker_skill)) * 0.2325
    return max(5, min(100, int(rate)))


def _defence_roll(attacker: Fighter, target: Fighter,
                  rng: random.Random | None) -> tuple[str | None, float]:
    """Roll parry, then guard, then shield block.  At most one procs per swing."""
    rng = rng or random
    if not target.is_pc:
        return None, 1.0

    # Parry needs the parry skill and a weapon that is not hand-to-hand.
    if target.parry_skill > 0 and not target.h2h:
        if rng.randint(1, 100) <= parry_rate(target.parry_skill, attacker.skill_value):
            return "parry", PARRY_REDUCTION

    # Guard needs the guard skill and fists.
    if target.guard_skill > 0 and (target.h2h or target.weapon_dmg == 0):
        if rng.randint(1, 100) <= guard_rate(target.guard_skill, attacker.skill_value):
            return "guard", GUARD_REDUCTION

    # A shield blocks on its own skill, whatever the weapon is doing.
    if target.shield_size and target.shield_skill > 0:
        if rng.randint(1, 100) <= block_rate(target.shield_size, target.shield_skill,
                                             attacker.skill_value):
            return "block", SHIELD_ABSORB.get(int(target.shield_size), 0.4)

    return None, 1.0


# --- hit rate and critical rate -------------------------------------------------------------

def hit_rate(*, accuracy: int, evasion: int, attacker_level: int, target_level: int,
             is_pc: bool, two_handed: bool = False, off_hand: bool = False,
             corrected: bool = False) -> float:
    """Chance that a swing connects."""
    acc = int(accuracy)
    if corrected:
        # Players are penalised for being below the target, monsters are rewarded for
        # being above it -- the same one-way rule the damage ratio uses.
        if is_pc and attacker_level < target_level:
            acc += (attacker_level - target_level) * 4
        elif not is_pc and attacker_level > target_level:
            acc += (attacker_level - target_level) * 4

    if is_pc:
        if two_handed or off_hand:
            cap = HIT_RATE_CAP_TWO_HANDED
        else:
            cap = HIT_RATE_CAP_ONE_HANDED
        minimum = HIT_RATE_FLOOR_PC
    else:
        cap = HIT_RATE_CAP_MOB
        minimum = HIT_RATE_FLOOR_PC

    difference = (acc - int(evasion)) / 2
    return max(minimum, min(cap, (75 + difference) / 100))


def crit_rate(*, attacker_dex: int, target_agi: int, is_pc: bool,
              crit_mod: int = 0, target_crit_evasion: int = 0) -> float:
    """Chance that a swing crits.  PCs get the dDEX table; mobs a flat 5%."""
    base = 0.05
    if not is_pc:
        return base

    ddex = int(attacker_dex) - int(target_agi)
    if ddex > 50:
        bonus = 0.15
    elif ddex >= 40:
        bonus = (ddex - 35) / 100
    elif ddex >= 30:
        bonus = 0.04
    elif ddex >= 20:
        bonus = 0.03
    elif ddex >= 14:
        bonus = 0.02
    elif ddex >= 7:
        bonus = 0.01
    else:
        bonus = 0.0

    rate = base + bonus + int(crit_mod) / 10000 - int(target_crit_evasion) / 10000
    return max(0.05, min(1.0, rate))


# --- magic ----------------------------------------------------------------------------------

def magic_resist(*, skill: int, caster_int: int, mods: dict[int, int],
                 target_level: int, target_mods: dict[int, int]) -> float:
    """The damage/duration multiplier from Magic Accuracy against Magic Evasion.

    Retail rolls a resist tier; this is the deterministic middle of that roll.  Skill,
    ``Magic Accuracy`` and INT push it up, the target's level and ``Magic Evasion`` push
    it down, and it never falls below half or rises above full.
    """
    accuracy = 200 + int(skill) + int(mods.get(mod.MACC, 0)) + int(caster_int) // 2
    evasion = 200 + int(target_level) * 2 + int(target_mods.get(mod.MEVA, 0))
    return max(0.5, min(1.0, 0.75 + (accuracy - evasion) / 1000.0))


def magic_damage(*, base: int, multiplier: float, caster_int: int, target_int: int,
                 skill: int, mods: dict[int, int], target_mods: dict[int, int],
                 target_level: int) -> int:
    """Damage of one direct-damage spell.

    ``(base x multiplier + dINT x 2) x (1 + Magic Atk. Bonus) + Magic Damage``, then the
    Magic Accuracy resist multiplier and the target's ``Magic Def. Bonus``.  A spell with
    no base (Drain, Aspir) is handled by its own path before this is called.

    Elemental affinity (``Fire MAB`` and friends) is not loaded for the reforged sets, so
    only the generic ``Magic Atk. Bonus`` is read here.
    """
    dint = max(-100, min(200, int(caster_int) - int(target_int)))
    raw = int(base) * float(multiplier) + max(0, dint) * 2
    mab = max(-100, int(mods.get(mod.MATT, 0)))
    raw = raw * (1.0 + mab / 100.0) + int(mods.get(mod.MAGIC_DAMAGE, 0))
    resist = magic_resist(skill=skill, caster_int=caster_int, mods=mods,
                          target_level=target_level, target_mods=target_mods)
    mdef = max(0, min(80, int(target_mods.get(mod.MDEF, 0))))
    return max(1, int(raw * resist * (1.0 - mdef / 100.0)))


def cast_time(milliseconds: int, fast_cast: int) -> int:
    """Spell cast time after Fast Cast, capped at half the base and a 0.5s floor."""
    percent = max(0, min(50, int(fast_cast)))
    return max(500, int(milliseconds) * (100 - percent) // 100)


def tp_gain(tenths: int, store_tp: int) -> int:
    """TP from a landed hit after Store TP, in tenths."""
    return max(0, int(tenths) * (100 + max(0, int(store_tp))) // 100)


# --- damage taken ---------------------------------------------------------------------------

def damage_taken(mods: dict[int, int], *, physical: bool = True, ranged: bool = False,
                 breath: bool = False) -> float:
    """The multiplier applied to damage the defender receives.

    Two clamps, in this order:

    * ``DMG`` + ``DMGPHYS`` (or ``DMGMAGIC``) share one 50% cap;
    * ``DMGPHYS_II`` (Burtgang, Epeolatry) adds after that cap and bypasses it.

    The hard floor is 12.5%, the game's 87.5% overall damage reduction cap.
    """
    def get(key: int) -> int:
        return int(mods.get(key, 0))

    if physical:
        capped = get(mod.DMG) + get(mod.DMGPHYS)
        bypass = get(mod.DMGPHYS_II)
        uncapped = get(mod.UDMGPHYS)
    else:
        capped = get(mod.DMG) + get(mod.DMGMAGIC)
        bypass = get(mod.DMGMAGIC_II)
        uncapped = get(mod.UDMGMAGIC)
    if ranged:
        capped += get(mod.DMGRANGE)
        uncapped += get(mod.UDMGRANGE)
    if breath:
        capped += get(mod.DMGBREATH)
        uncapped += get(mod.UDMGBREATH)

    # Uncapped modifiers apply first, on their own.
    result = max(0.0, 1.0 + uncapped / 10000)
    # Then the capped family, floored at 50%, and PDT-II after the cap.
    resist = max(1.0 + capped / 10000, 0.5) + bypass / 10000
    return result * max(resist, 0.125)


# --- the whole swing ------------------------------------------------------------------------

@dataclass
class Fighter:
    """Everything the engine needs about one side of a swing."""

    level: int
    attack: int
    defense: int
    accuracy: int
    evasion: int
    strength: int
    dexterity: int
    vitality: int
    agility: int
    is_pc: bool
    weapon_skill: int = 0
    weapon_dmg: int = 0
    weapon_rank: int = 0
    two_handed: bool = False
    h2h: bool = False
    # True for the off-hand half of a dual-wielded attack round (95% hit-rate cap).
    off_hand: bool = False
    mods: dict[int, int] = field(default_factory=dict)
    # Weapon skill value, the number parry/guard/block are measured against.
    skill_value: int = 0
    # Defensive skills (0 when the job has no rank in them, which disables the proc).
    parry_skill: int = 0
    guard_skill: int = 0
    shield_skill: int = 0
    shield_size: int = 0


@dataclass
class Hit:
    damage: int
    critical: bool
    missed: bool
    defended: str | None = None   # "parry", "guard" or "block", when the defender procced

    def __bool__(self) -> bool:
        return not self.missed


def melee(attacker: Fighter, target: Fighter, *, zone: int = 0,
          rng: random.Random | None = None, attack_multiplier: float = 1.0,
          ftp: float = 1.0) -> Hit:
    """Resolve one physical swing, from hit check to damage-taken gear."""
    rng = rng or random
    corrected = level_corrected(zone)

    hit_chance = hit_rate(
        accuracy=attacker.accuracy, evasion=target.evasion,
        attacker_level=attacker.level, target_level=target.level,
        is_pc=attacker.is_pc, two_handed=attacker.two_handed,
        off_hand=attacker.off_hand, corrected=corrected)
    if rng.random() >= hit_chance:
        return Hit(0, False, True)

    critical = rng.random() < crit_rate(
        attacker_dex=attacker.dexterity, target_agi=target.agility,
        is_pc=attacker.is_pc,
        crit_mod=attacker.mods.get(mod.CRIT_HIT_RATE, 0),
        target_crit_evasion=target.mods.get(mod.CRITICAL_HIT_EVASION, 0))

    multiplier = pdif(
        attack=int(attacker.attack * attack_multiplier), defense=target.defense,
        weapon_skill=attacker.weapon_skill, is_critical=critical,
        attacker_level=attacker.level, target_level=target.level,
        is_pc=attacker.is_pc, corrected=corrected,
        damage_limit=attacker.mods.get(mod.DAMAGE_LIMIT, 0),
        damage_limitp=attacker.mods.get(mod.DAMAGE_LIMITP, 0),
        rng=rng)

    strength_term = fstr(attacker.strength, target.vitality, attacker.weapon_rank,
                         is_mob=not attacker.is_pc, level=attacker.level)
    base = max(0, attacker.weapon_dmg + strength_term)
    raw = int(base * multiplier * ftp)

    if critical:
        bonus = max(0, min(100, attacker.mods.get(mod.CRIT_DMG_INCREASE, 0)
                            - target.mods.get(mod.CRIT_DEF_BONUS, 0)))
        raw = raw * (100 + bonus) // 100

    raw = max(0, raw)

    defended, absorb = _defence_roll(attacker, target, rng)
    if defended is not None:
        raw = int(raw * (1.0 - absorb))

    raw = int(raw * damage_taken(target.mods, physical=True))

    return Hit(raw, critical, False, defended)
