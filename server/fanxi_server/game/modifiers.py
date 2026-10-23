"""Modifier ids, as LandSandBoat numbers them.

`item_mods` rows are ``(item id, modifier id, value)`` and job traits use the same ids.
The ids are LandSandBoat's ``xi::Mod`` values from ``data/enums/mod.yaml``; only the ones
the engine reads are named here, so a typo shows up as a name error rather than a silent
zero.

Most modifiers are **hundredths of a percent**: a value of ``-1000`` is -10%, and the
engine divides by 10000.  Flat modifiers (STR, Attack, HP) are used as-is.  The two
percent-integer ones (``ATT_PERCENT``, ``DEF_PERCENT``) are noted below.
"""
from __future__ import annotations

# Flat attributes.
DEF = 1
HP = 2
HPP = 3                 # percent of maximum HP
MP = 5
MPP = 6                 # percent of maximum MP
STR = 8
DEX = 9
VIT = 10
AGI = 11
INT = 12
MND = 13
CHR = 14

# Flat combat stats.
ATT = 23
RATT = 24
ACC = 25
RACC = 26
MATT = 28
MDEF = 29
MACC = 30
MEVA = 31
EVA = 68
MAGIC_DAMAGE = 311       # flat magic damage, added after Magic Atk. Bonus
DRAIN_ASPIR = 315        # "Drain" and "Aspir" potency

# Percent-integer combat stats: 25 means +25%.
ATT_PERCENT = 62
DEF_PERCENT = 63

# Job-trait modifiers.  They use the same ids as gear, which is why trait bonuses can
# be merged into the equipment dict without a second stat path.
FASTCAST = 170             # percent, from the Fast Cast trait
STORETP = 73               # percent TP gained per landed hit
DUAL_WIELD = 259           # percent delay reduction while dual wielding
MARTIAL_ARTS = 173         # flat delay reduction for hand-to-hand
CLEAR_MIND = 295           # resting MP recovery bonus
REFRESH = 369              # MP restored per 3-second tick
REGEN = 370                # HP restored per 3-second tick
REFRESH_DOWN = 405         # plague and similar
REGEN_DOWN = 404           # poison and similar
MAX_HP_BOOST = 1095        # flat maximum HP from the Max HP Boost trait
MAX_MP_BOOST = 1096        # flat maximum MP from the Max MP Boost trait

# Food percentages, capped by their matching *_CAP.
FOOD_ATT_PERCENT = 180
FOOD_ATT_CAP = 181
FOOD_DEF_PERCENT = 182
FOOD_DEF_CAP = 183

# Damage taken family.  Values are hundredths of a percent (-1000 = -10%).
DMG = 160                 # "Damage taken -x%", physical and magical
DMGPHYS = 161             # "Physical damage taken -x%"
DMGBREATH = 162
DMGMAGIC = 163
DMGRANGE = 164
DMGPHYS_II = 190          # "Physical damage taken II" -- bypasses the 50% cap
DMGMAGIC_II = 831         # "Magic damage taken II" -- bypasses the 50% cap
UDMGPHYS = 387            # uncapped damage multipliers (Sentinel, Invincible, ...)
UDMGBREATH = 388
UDMGMAGIC = 389
UDMGRANGE = 390

# Critical hits.
CRIT_HIT_RATE = 165       # hundredths of a percent
CRITICAL_HIT_EVASION = 166
CRIT_DMG_INCREASE = 421
CRIT_DEF_BONUS = 908

# Damage limit: raises the attacker's pDIF cap.  DAMAGE_LIMIT is flat (added /100 to
# the cap), DAMAGE_LIMITP is a percentage applied after it.
DAMAGE_LIMIT = 1080
DAMAGE_LIMITP = 1081

# Weapon damage rating adjusters.  These move the damage rating without moving the
# weapon rank, which is why fSTR caps do not change with them.
DMG_RATING = 287
MAIN_DMG_RANK = 377

# Equipment haste, hundredths of a percent: 1500 is 15%.
HASTE_GEAR = 384


def percent(value: int) -> float:
    """10000 -> 1.0, -1000 -> -0.1.  The unit every damage-taken modifier uses."""
    return int(value) / 10000.0
