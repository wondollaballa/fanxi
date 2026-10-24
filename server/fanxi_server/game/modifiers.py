"""Modifier ids, as LandSandBoat numbers them.

`item_mods` rows are ``(item id, modifier id, value)`` and job traits use the same ids.
The ids are LandSandBoat's ``xi::Mod`` values from ``data/enums/mod.yaml``; only the ones
the engine reads are named here, so a typo shows up as a name error rather than a silent
zero.  ``PERPETUANCE`` and ``ENH_MAGIC_DURATION_AUGMENT`` use LSB's spare range because
LandSandBoat has no row for those client lines.

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
ENMITY = 27                # flat enmity added on a swing (gear's "Enmity+x")
SUBTLE_BLOW = 289          # percent less enmity generated per hit
SUBTLE_BLOW_II = 290
COUNTER = 291              # percent chance to counter an incoming hit
SKILLCHAIN_BONUS = 174     # percent added to a skillchain's damage
DUAL_WIELD = 259           # percent delay reduction while dual wielding
DOUBLE_ATTACK = 288        # percent chance per hand, checked after Triple and Quad
TRIPLE_ATTACK = 302        # percent chance per hand
QUADRUPLE_ATTACK = 430     # percent chance per hand
MARTIAL_ARTS = 173         # flat delay reduction for hand-to-hand
CLEAR_MIND = 295           # resting MP recovery bonus
REFRESH = 369              # MP restored per 3-second tick
REGEN = 370                # HP restored per 3-second tick
REFRESH_DOWN = 405         # plague and similar
REGEN_DOWN = 404           # poison and similar
MAX_HP_BOOST = 1095        # flat maximum HP from the Max HP Boost trait
MAX_MP_BOOST = 1096        # flat maximum MP from the Max MP Boost trait

# Spell duration and potency.  The first three are LandSandBoat's ids; PERPETUANCE and
# ENH_MAGIC_DURATION_AUGMENT use spare ids because LSB does not table those lines.
# Values are percent-integers unless noted: 890=10 is +10%, 339 is flat seconds.
ENH_MAGIC_DURATION = 890   # "Enhancing magic duration"+x% listed on the item
ENH_MAGIC_DURATION_AUGMENT = 1222  # the same line as an augment; a separate multiplier
REGEN_DURATION = 339       # flat seconds of Regen duration ("Regen" effect duration +15)
REGEN_MULTIPLIER = 838     # "Regen" potency +x% (applies to the base tick before flats)
PERPETUANCE = 1221         # "Perpetuance"+x%, hundredths over the 2.0x base (6500=+65%)

# Spell potency and school-specific duration.
CURE_POTENCY = 374         # "Cure" potency +x% (gear cap 50)
CURE_POTENCY_II = 260      # "Cure" potency II +x% (gear cap 30)
CURE_POTENCY_RCVD = 375    # "Cure" potency received +x%
CURE_POTENCY_BONUS = 1051  # flat HP added to a Cure
ENF_MAG_POTENCY = 290      # Enfeebling magic potency +x%
ENF_MAG_DURATION = 1151    # Enfeebling magic duration +x%
DARK_MAGIC_DURATION = 1072  # Dark Magic spell duration +x%
NINJUTSU_DURATION = 1000   # Ninjutsu duration +x seconds
SONG_DURATION_BONUS = 454  # song duration +x%
ENSPELL_DURATION = 938     # En-spell duration +x seconds
SNEAK_DURATION = 946       # Sneak duration +x seconds
INVISIBLE_DURATION = 947   # Invisible duration +x seconds
STONESKIN_BONUS_HP = 539   # extra Stoneskin HP
ENHANCES_REFRESH = 529     # "Enhances Refresh": +N MP per tick

# Food percentages, capped by their matching *_CAP.
FOOD_HP = 176
FOOD_HP_CAP = 177
FOOD_MP = 178
FOOD_MP_CAP = 179
FOOD_ATT_PERCENT = 180
FOOD_ATT_CAP = 181
FOOD_DEF_PERCENT = 182
FOOD_DEF_CAP = 183
FOOD_ACC_PERCENT = 184
FOOD_ACC_CAP = 185
FOOD_RATT_PERCENT = 186
FOOD_RATT_CAP = 187
FOOD_RACC_PERCENT = 188
FOOD_RACC_CAP = 189

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

# Weapon skills.  LandSandBoat's ids: 570 + ws_id is that weapon skill's own damage
# bonus (571 Combo, 580 Final Heaven, ...), 840 is "Weapon skill damage" on every hit,
# 841 the same line on the first hit only, 48 is "Weapon skill accuracy", and 345 is
# the generic "TP Bonus" (the TP used for fTP and effect scaling, not the TP spent).
WEAPONSKILL_DAMAGE_BASE = 570
WSD_ALL_HITS = 840
WSD_FIRST_HIT = 841
WS_ACCURACY = 48
TP_BONUS = 345
# "fTP +x" gear (Fotia Gorget/Belt).  LandSandBoat stores this in 1/256 fTP units:
# 25 is +0.0977, 256 is +1.0.
ANY_FTP_BONUS = 1144
# Fencer: TP Bonus for the weapon-skill calculation and its critical-hit rate, both
# only while single-wielding a one-handed weapon.
FENCER_TP_BONUS = 903
FENCER_CRIT_RATE = 904

# Equipment haste, hundredths of a percent: 1500 is 15%.
HASTE_GEAR = 384


def percent(value: int) -> float:
    """10000 -> 1.0, -1000 -> -0.1.  The unit every damage-taken modifier uses."""
    return int(value) / 10000.0
