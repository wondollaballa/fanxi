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
STR_TO_ATT_RANGED = 1.0
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

# One attack round -- both hands and every multi-attack proc -- is capped at 8 hits.
MAX_ATTACKS_PER_ROUND = 8

# The most damage one action result can carry.  Retail's client prints at most 99,999
# for a hit, a weapon skill's summed hits, a spell or a skillchain, and the server applies
# the same ceiling before it spends the target's HP: a 120,000 weapon skill takes 99,999,
# not the full amount.  Every damage path clamps where it builds its number, so the HP
# loss, the hate and the drains stay consistent with what the client is told.
DAMAGE_CAP = 99999

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


def cap_damage(damage: int) -> int:
    """Clip one damage event to the game's 99,999 ceiling.

    Call this where the number is *built*, before it is applied: a caller that subtracts
    the uncapped value from HP would still lose more than the client is told.
    """
    return max(0, min(DAMAGE_CAP, int(damage)))


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


def block_rate(shield_size: int, block_skill: int, attacker_skill: int,
               *, mastery: int = 0) -> int:
    """Chance in percent that a shield blocks, from shield size and the skill gap.

    ``mastery`` is the Shield Mastery trait's percentage (PLD/WAR/RDM), added to the
    roll so the trait's 10/20/... is not just a row in the trait list.
    """
    base = SHIELD_BLOCK_RATE.get(int(shield_size), 0)
    rate = base + (int(block_skill) - int(attacker_skill)) * 0.2325
    rate += max(0, int(mastery))
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

    # A shield blocks on its own skill, whatever the weapon is doing.  Shield Mastery
    # is a flat addition to that rate (RDM's rank 2 at 97 is +20%).
    if target.shield_size and target.shield_skill > 0:
        if rng.randint(1, 100) <= block_rate(
                target.shield_size, target.shield_skill, attacker.skill_value,
                mastery=int(target.mods.get(mod.SHIELD_MASTERY, 0))):
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
              crit_mod: int = 0, target_crit_evasion: int = 0,
              crit_bonus: float = 0.0) -> float:
    """Chance that a swing crits.  PCs get the dDEX table; mobs a flat 5%.

    ``crit_bonus`` is a fraction for effects the caller has already resolved, such as
    Fencer's critical-hit rate on a weapon skill; it is added before the 5% floor.
    """
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

    rate = (base + bonus + int(crit_mod) / 10000
            - int(target_crit_evasion) / 10000 + float(crit_bonus))
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


def _magic_finish(raw: float, *, skill: int, caster_int: int, mods: dict[int, int],
                  target_mods: dict[int, int], target_level: int) -> int:
    """The tail every magic-damage formula shares.

    ``Magic Damage`` is added to the spell's base before Magic Atk. Bonus, and the bonus
    is the reference server's ratio ``(100 + MAB) / (100 + MDB)`` -- not a multiply by
    MAB followed by a subtract of MDB.  Elemental affinity (``Fire MAB`` and friends) is
    not loaded for the reforged sets, so only the generic bonus is read.  The Magic
    Accuracy resist multiplier is still Fanxi's deterministic approximation.
    """
    base = float(raw) + int(mods.get(mod.MAGIC_DAMAGE, 0))
    mab = max(-100, int(mods.get(mod.MATT, 0)))
    mdb = max(-100, int(target_mods.get(mod.MDEF, 0)))
    adjusted = base * (100 + mab) / max(1, 100 + mdb)
    resist = magic_resist(skill=skill, caster_int=caster_int, mods=mods,
                          target_level=target_level, target_mods=target_mods)
    return max(1, cap_damage(int(adjusted * resist)))


def magic_damage(*, base: int, multiplier: float, caster_int: int, target_int: int,
                 skill: int, mods: dict[int, int], target_mods: dict[int, int],
                 target_level: int) -> int:
    """Damage of one direct-damage spell.

    ``(base x multiplier + dINT x 2) x (1 + Magic Atk. Bonus) + Magic Damage``, then the
    Magic Accuracy resist multiplier and the target's ``Magic Def. Bonus``.  A spell with
    no base (Drain, Aspir) is handled by its own path before this is called.
    """
    dint = max(-100, min(200, int(caster_int) - int(target_int)))
    raw = int(base) * float(multiplier) + max(0, dint) * 2
    return _magic_finish(raw, skill=skill, caster_int=caster_int, mods=mods,
                         target_mods=target_mods, target_level=target_level)


def magic_weaponskill(*, wsc: int, weapon_level: int, level: int, ftp: float,
                      dstat: int = 0, magic_damage: int = 0, wsd: int = 0,
                      elemental_ws: int = 0, affinity: int = 0,
                      mab: int = 0, mdb: int = 0, resist: float = 1.0,
                      damage_multiplier: float = 1.0) -> int:
    """Damage of one magical weapon skill (Seraph Blade, Sanguine Blade, ...).

    BG-wiki's current formula::

        base = (152 + floor((WeaponLevel - 99) * 2.45) + WSC) * fTP
        base = floor(base * (1 + Elemental WS Damage)) + dSTAT + Magic Damage
        damage = base * affinity * resist * MAB/MDB * MDT * WSD

    The ``152 + ...`` base uses the equipped weapon's item level, which is 201 for an
    iLvl 119 weapon; a sub-100 weapon (or no item level) uses the player-level form
    ``5 + floor((Level - 1) * 1.5)``, which is 152 at level 99.  The elemental WS
    damage augment (Oboro path C) multiplies only the fTP part, before dSTAT and flat
    Magic Damage are added.  Target MDB is floored at -50% as retail does.

    This function is pure so the formula can be pinned without a live session; the
    caller supplies the already-resolved WSC, MAB, resist and damage-taken terms.
    """
    level = max(1, int(level))
    if int(weapon_level) >= 100:
        base = 152 + int((int(weapon_level) - 99) * 2.45)
    else:
        base = 5 + int((level - 1) * 1.5)
    base += int(wsc)

    raw = int(float(base) * float(ftp) * (1.0 + max(0, int(elemental_ws)) / 100.0))
    raw += int(dstat) + max(0, int(magic_damage))
    raw = int(raw * (1.0 + max(0, int(wsd)) / 100.0))
    raw = int(raw * (1.0 + int(affinity) / 100.0))
    raw = int(raw * (100 + int(mab)) / max(50, 100 + int(mdb)))
    raw = int(raw * float(resist) * float(damage_multiplier))
    return cap_damage(max(0, raw))


def helix_damage(*, base: int, multiplier: float, caster_int: int, target_int: int,
                 skill: int, mods: dict[int, int], target_mods: dict[int, int],
                 target_level: int) -> int:
    """The opening hit of a Helix spell.

    A Helix is a nuke with its own stat curve: BG-wiki's tests put it at ``base + dINT``
    (25 + 38 = 63 at level 99), with the slope halving after 100 dINT (LandSandBoat's
    ``M100 = 0.5``).  The generic ``dINT x 2`` term would nearly double every Helix.
    Magic Atk. Bonus, flat Magic Damage, Magic Accuracy and Magic Def. Bonus apply as
    they do to any other nuke.  The spell's data already carries base 25/75 and
    multiplier 1.0, which is the helix V/M from retail.
    """
    dint = max(0, min(200, int(caster_int) - int(target_int)))
    stat = float(dint) if dint <= 100 else 100.0 + (dint - 100) / 2.0
    raw = int(base) * float(multiplier) + stat
    return _magic_finish(raw, skill=skill, caster_int=caster_int, mods=mods,
                         target_mods=target_mods, target_level=target_level)


def dia_damage(*, base: int, caster_mnd: int, target_mnd: int) -> int:
    """The opening hit of a Dia or Diaga spell.

    Dia is not an elemental nuke: its data says base 2..23 with a zero stat multiplier, and
    retail gives it only 1-5 HP per three-second tick afterwards.  MND adds a little to the
    opening hit; Magic Attack Bonus and "Magic Damage" deliberately do not, or a level 99
    mage in Hvergelmir gear turns a 2-base enfeebling into a 1,400-damage nuke.
    """
    bonus = min(50, max(0, int(caster_mnd) - int(target_mnd)) // 8)
    return max(1, int(base) + bonus)


# --- en-spells ------------------------------------------------------------------------------

def enspell_potency(skill: int) -> int:
    """The base damage of an elemental en-spell, from Enhancing Magic skill.

    BG-wiki's current curve, kept continuous where the two pieces meet::

        skill < 180:  skill / 9 + 5
        skill >= 180: (skill - 180) / 8 + 25

    A 500-skill Red Mage gets 65, which is the number the wiki's own tier II example
    starts from.  (LandSandBoat's older ``enhancing_spell.lua`` uses a different
    low-skill branch and is discontinuous at 400; the two agree from 401 up.)
    """
    skill = max(0, int(skill))
    if skill >= 180:
        return (skill - 180) // 8 + 25
    return skill // 9 + 5


def enspell_cap(skill: int) -> int:
    """Tier II's ceiling: twice the base the same Enhancing Magic skill gives."""
    return 2 * enspell_potency(skill)


def enlight_potency(skill: int, *, tier: int = 1) -> int:
    """Enlight/Endark's starting charge, from Divine (Enlight) or Dark (Endark) skill.

    Both decay by one point per landed hit, so this is also the effect's total damage
    before resist.  Tier I is ``12 + 3 * (skill / 20) - skill / 40``; tier II is the
    higher Job-Point Gift curve.
    """
    skill = max(0, int(skill))
    if int(tier) >= 2:
        if skill >= 501:
            value = skill + 400
            return 2 * (value // 20) + value // 40
        value = skill + 85
        return 2 * (value // 13) + value // 26
    return 12 + 3 * (skill // 20) - skill // 40


def enspell_resist(element_meva: int) -> float:
    """The damage multiplier from the defender's resistance to this element.

    The reference server rolls one of five tiers against the defender's elemental
    Magic Evasion: full damage, then 1/2, 1/4, 1/8 and 1/16 at thresholds of
    ``m/100``, ``(m/100)^2`` and so on.  Fanxi's magic model is deterministic, so this
    is the expectation of that roll.  Zero resistance is 1.0 and 100 is 1/16.
    """
    half = min(1.0, max(0.0, int(element_meva) / 100.0))
    quarter = half * half
    eighth = quarter * half
    sixteenth = eighth * half
    return ((1.0 - half) + (half - quarter) * 0.5 + (quarter - eighth) * 0.25
            + (eighth - sixteenth) * 0.125 + sixteenth * 0.0625)


def enspell_hit(*, tier: int, skill: int, element: int, potency: int = 0,
                counter: int = 0, bonus: int = 0, percent: int = 0, merit: int = 0,
                composure: bool = False,
                target_mods: dict[int, int] | None = None) -> tuple[int, int]:
    """One en-spell additional hit: ``(damage, the value the effect stores next)``.

    The three tiers apply differently, and the stored value means a different thing for
    each, which is why the second half of the tuple exists:

    * tier I: the base is fixed at cast time (``potency``), and every landed swing in
      the round carries it;
    * tier II: the base is recalculated from the current skill plus a hidden counter
      that starts at 0 on the cast, rises by one per successful round and caps at
      twice the base (``enspell_cap``); the counter keeps rising past the cap so a
      later skill change can raise the damage again;
    * tier III (Enlight/Endark): ``potency`` is a charge that decays by one per hit.

    The tail follows BG-wiki's en-spell damage page: flat "Sword enhancement spell
    damage" and the merit line join the base, the percentage line and Composure are one
    multiplier, then the elemental resistance and the target's magic damage taken
    apply.  Magic Attack Bonus, Magic Defense Bonus and the Magic Damage statistic
    deliberately do not: retail excludes all three from en-spell damage.
    """
    target_mods = target_mods or {}
    tier = int(tier)
    if tier == 1:
        base = int(potency)
        stored = int(potency)
    elif tier == 2:
        value = enspell_potency(skill)
        base = min(value + int(counter), 2 * value)
        stored = int(counter) + 1
    else:
        base = int(potency)
        stored = max(0, int(potency) - 1)

    raw = base + int(bonus) + int(merit)
    if raw <= 0:
        return 0, stored
    multiplier = 1.0 + int(percent) / 100.0
    if composure:
        # RDM's Composure triples the elemental en-spells; LandSandBoat adds +200%.
        multiplier += 2.0
    damage = int(raw * multiplier)
    resistance = 0
    if 1 <= int(element) <= 8:
        resistance = int(target_mods.get(mod.ELEMENTAL_MEVA[int(element) - 1], 0))
    damage = int(damage * enspell_resist(resistance))
    damage = int(damage * damage_taken(target_mods, physical=False))
    return max(0, damage), stored


def cast_time(milliseconds: int, fast_cast: int) -> int:
    """Spell cast time after Fast Cast.

    A zero base stays zero: Chainspell and Spontaneity make a cast instant, and the
    0.5 s floor is for a spell that still has a cast bar left.  Applying the floor to
    zero turned both abilities into a half-second cast.
    """
    if int(milliseconds) <= 0:
        return 0
    percent = max(0, min(50, int(fast_cast)))
    return max(500, int(milliseconds) * (100 - percent) // 100)


def tp_gain(tenths: int, store_tp: int) -> int:
    """TP from a landed hit after Store TP, in tenths."""
    return max(0, int(tenths) * (100 + max(0, int(store_tp))) // 100)


def tp_delay(delay: int, *, dual_wield: int = 0) -> int:
    """The delay one hit's TP return is calculated from.

    Dual Wield halves each hand's own base delay after its reduction, not the round's
    averaged delay: the main hand and the off hand keep their separate TP returns.
    """
    delay = max(1, int(delay))
    if dual_wield:
        reduction = max(0, min(100, int(dual_wield)))
        delay = max(1, int(delay * (100 - reduction) / 100 / 2))
    return max(1, delay)


def tp_return(delay: int) -> int:
    """TP from one landed hit, in tenths, on retail's current curve.

    This is LandSandBoat's ``xi.combat.tp.calculateTPReturn`` (PC branch), not the old
    ``(delay + 480) * 0.0085`` approximation: the curve is piecewise and flattens at
    higher delays, which is why a dual-wielded pair does not lose as much TP as halving
    the old formula suggests.
    """
    delay = int(delay)
    if delay > 900:
        tp = 173 + (delay - 900) * 28 / 360
    elif delay > 720:
        tp = 161 + (delay - 720) * 24 / 360
    elif delay > 630:
        tp = 154 + (delay - 630) * 28 / 360
    elif delay > 540:
        tp = 149 + (delay - 540) * 20 / 360
    elif delay > 180:
        tp = 61 + (delay - 180) * 88 / 360
    else:
        tp = 61 + (delay - 180) * 63 / 360
    return max(0, int(tp))


def tp_return_mob(delay: int) -> int:
    """TP a monster gets from one landed swing, in tenths.

    Monsters do not use the player curve: LandSandBoat's
    ``xi.combat.tp.calculateTPReturn`` has a separate mob branch (from the JP wiki),
    whose low-delay leg is much flatter.  A 240-delay mob gets 64 TP a hit instead of
    the player formula's 75, which is why a monster's TP bar fills on its own schedule.
    """
    delay = int(delay)
    if delay > 530:
        tp = 145 + (delay - 530) * 35 / 470
    elif delay > 480:
        tp = 130 + (delay - 480) * 15 / 50
    elif delay > 450:
        tp = 115 + (delay - 450) * 15 / 30
    elif delay > 180:
        tp = 50 + (delay - 180) * 65 / 270
    else:
        tp = 50 + (delay - 180) * 15 / 180
    return max(0, int(tp))


def multi_attack_hits(rng: random.Random | None = None, *, double: int = 0,
                      triple: int = 0, quadruple: int = 0) -> int:
    """How many hits one hand gets before its accuracy rolls.

    Retail checks the multi-attacks in descending order and stops at the first proc:
    Quadruple (4 hits) > Triple (3) > Double (2).  The winning proc replaces the lower
    checks for that hand, which is why a Double Attack proc "overwrites" a Mythic
    aftermath's Triple Attack chance.  No proc is the single base hit.
    """
    rng = rng or random
    for chance, hits in ((quadruple, 4), (triple, 3), (double, 2)):
        chance = max(0, min(100, int(chance or 0)))
        if chance and rng.random() * 100.0 < chance:
            return hits
    return 1


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
          ftp: float = 1.0, crit_bonus: float = 0.0, wsc: int = 0,
          ignored_defense: float = 0.0, allow_critical: bool = True,
          flat_damage: int = 0, ranged: bool = False) -> Hit:
    """Resolve one physical swing, from hit check to damage-taken gear.

    ``crit_bonus`` is an extra critical-hit rate (a fraction) for the caller's own
    effects; a weapon skill passes Fencer's rate and its own "critical hit rate varies
    with TP" here.  ``wsc`` is a weapon skill's secondary-attribute bonus, added to the
    weapon damage and fSTR before pDIF.  ``ignored_defense`` is the fraction of the
    target's Defense the skill ignores (Blade: Kamu's 25%, for example).
    ``allow_critical`` is False for weapon skills whose description does not say their
    critical-hit rate varies with TP: retail only lets those skills crit, so a normal
    weapon skill must not take the base/dDEX/gear critical roll that an auto-attack does.
    ``flat_damage`` is added after pDIF and critical damage but before the target's
    damage-taken gear, which is where retail applies Souleater's HP conversion.
    """
    rng = rng or random
    corrected = level_corrected(zone)

    hit_chance = hit_rate(
        accuracy=attacker.accuracy, evasion=target.evasion,
        attacker_level=attacker.level, target_level=target.level,
        is_pc=attacker.is_pc, two_handed=attacker.two_handed,
        off_hand=attacker.off_hand, corrected=corrected)
    if rng.random() >= hit_chance:
        return Hit(0, False, True)

    critical = allow_critical and rng.random() < crit_rate(
        attacker_dex=attacker.dexterity, target_agi=target.agility,
        is_pc=attacker.is_pc,
        crit_mod=attacker.mods.get(mod.CRIT_HIT_RATE, 0),
        target_crit_evasion=target.mods.get(mod.CRITICAL_HIT_EVASION, 0),
        crit_bonus=crit_bonus)

    defense = int(target.defense)
    if ignored_defense:
        defense = max(1, int(defense * (1.0 - max(0.0, min(1.0, float(ignored_defense))))))
    multiplier = pdif(
        attack=int(attacker.attack * attack_multiplier), defense=defense,
        weapon_skill=attacker.weapon_skill, is_critical=critical,
        attacker_level=attacker.level, target_level=target.level,
        is_pc=attacker.is_pc, corrected=corrected,
        damage_limit=attacker.mods.get(mod.DAMAGE_LIMIT, 0),
        damage_limitp=attacker.mods.get(mod.DAMAGE_LIMITP, 0),
        rng=rng)

    strength_term = fstr(attacker.strength, target.vitality, attacker.weapon_rank,
                         is_mob=not attacker.is_pc, level=attacker.level)
    base = max(0, attacker.weapon_dmg + strength_term + int(wsc))
    raw = int(base * multiplier * ftp)

    if critical:
        bonus = max(0, min(100, attacker.mods.get(mod.CRIT_DMG_INCREASE, 0)
                            - target.mods.get(mod.CRIT_DEF_BONUS, 0)))
        raw = raw * (100 + bonus) // 100

    raw = max(0, raw)

    defended, absorb = _defence_roll(attacker, target, rng)
    if defended is not None:
        raw = int(raw * (1.0 - absorb))

    raw += max(0, int(flat_damage))

    raw = int(raw * damage_taken(target.mods, physical=True, ranged=ranged))

    return Hit(cap_damage(raw), critical, False, defended)
