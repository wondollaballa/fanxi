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

# Elemental defence: what an item's "Fire+20" line is.  LandSandBoat calls these
# ``*_MEVA`` rather than ``*_RES``; the ids sit right after CHR, in the client's own
# element order.  The equipment menu's eight element orbs read the totals from the
# ``0x061`` status packet, so these are the ids that make the orbs non-zero.
FIRE_MEVA = 15
ICE_MEVA = 16
WIND_MEVA = 17
EARTH_MEVA = 18
THUNDER_MEVA = 19
WATER_MEVA = 20
LIGHT_MEVA = 21
DARK_MEVA = 22
# Fire, ice, wind, earth, thunder, water, light, dark: the packet's own order.
ELEMENTAL_MEVA = (FIRE_MEVA, ICE_MEVA, WIND_MEVA, EARTH_MEVA,
                  THUNDER_MEVA, WATER_MEVA, LIGHT_MEVA, DARK_MEVA)

# Elemental "Magic Atk. Bonus" -- what the wiki calls elemental affinity.  It is a
# separate multiplier from the generic MATT and only applies to the matching element
# (Daybreak's "Light elemental damage +50" is LIGHT_MAB 50).
FIRE_MAB = 32
ICE_MAB = 33
WIND_MAB = 34
EARTH_MAB = 35
THUNDER_MAB = 36
WATER_MAB = 37
LIGHT_MAB = 38
DARK_MAB = 39
ELEMENTAL_MAB = (FIRE_MAB, ICE_MAB, WIND_MAB, EARTH_MAB,
                 THUNDER_MAB, WATER_MAB, LIGHT_MAB, DARK_MAB)
ELEMENTAL_NAMES = ("fire", "ice", "wind", "earth", "thunder", "water", "light", "dark")


def elemental_mod(element: str) -> int | None:
    """The affinity modifier id for an element name, or None when it is not one."""
    try:
        return ELEMENTAL_MAB[ELEMENTAL_NAMES.index(str(element or "").strip().casefold())]
    except ValueError:
        return None

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
MAGIC_BURST_BONUS_CAPPED = 487   # % added to a magic burst, capped at +40%
MAGIC_BURST_BONUS_UNCAPPED = 274  # % added to a magic burst, uncapped
DRAIN_ASPIR = 315        # "Drain" and "Aspir" potency

# Percent-integer combat stats: 25 means +25%.
ATT_PERCENT = 62
DEF_PERCENT = 63
RATT_PERCENT = 66        # ranged attack percentage, LandSandBoat's ``rattp``

# Corsair rolls.  These ids are LandSandBoat's own so a roll and the same line on
# equipment/effects read the stat through one id.
MOVE_SPEED_BOLTERS_ROLL = 1086  # additive movement-speed percentage (Bolter's Roll)
PHANTOM_ROLL = 1076             # seconds taken off Phantom Roll's recast
PHANTOM_DURATION = 882          # seconds added to a roll's duration (Gants, Mantle, ...)
SNAPSHOT = 365                  # ranged-attack delay reduction percentage
REGAIN = 368                    # TP regained per tick
CONSERVE_MP = 296               # percent chance to spend less MP
SPELL_INTERRUPT = 168           # spell-interruption rate percentage (negative is better)
EXP_BONUS = 382                 # experience points earned percentage
CAPACITY_BONUS = 915            # capacity points earned percentage

# Job-trait modifiers.  They use the same ids as gear, which is why trait bonuses can
# be merged into the equipment dict without a second stat path.
# Smite: "physical attacks" with a two-handed or hand-to-hand weapon, in 1/256 of
# Attack (76 is +29.6%).  Desperate Blows: job-ability haste (in 1/100 percent, the
# same unit as HASTE_ABILITY) while Last Resort is up.  Stalwart Soul: percent less
# HP consumed by Souleater.
SMITE = 898
DESPERATE_BLOWS = 906
STALWART_SOUL = 907
FASTCAST = 170             # percent, from the Fast Cast trait
STORETP = 73               # percent TP gained per landed hit
CONSERVE_TP = 944          # percent chance a weapon skill saves 10-200 TP
SAVETP = 945               # TP kept after a weapon skill; the larger of it and the return
ENMITY = 27                # flat enmity added on a swing (gear's "Enmity+x")
SUBTLE_BLOW = 289          # percent less enmity generated per hit
SUBTLE_BLOW_II = 290
COUNTER = 291              # percent chance to counter an incoming hit
SHIELD_MASTERY = 485       # shield block rate +N percent (PLD/WAR/RDM trait)
SKILLCHAIN_BONUS = 174     # percent added to a skillchain's damage
ZANSHIN = 306              # percent chance of an extra swing after a miss (Samurai)
SKILLCHAIN_DAMAGE = 175    # percent added to a skillchain's damage (gear line)
DUAL_WIELD = 259           # percent delay reduction while dual wielding
DOUBLE_ATTACK = 288        # percent chance per hand, checked after Triple and Quad
TRIPLE_ATTACK = 302        # percent chance per hand
QUADRUPLE_ATTACK = 430     # percent chance per hand
MARTIAL_ARTS = 173         # flat delay reduction for hand-to-hand
CLEAR_MIND = 295           # Clear Mind rank from the trait
MP_WHILE_HEALING = 71      # flat resting MP recovery the Clear Mind trait raises
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
ENH_MAGIC_DURATION_FLAT = 1224  # flat seconds from job points / ability effects
ENF_MAG_DURATION_FLAT = 1225  # flat seconds of enfeebling duration from job points
NINJUTSU_FASTCAST = 1226      # percent cast-time reduction for Ninjutsu only
NINJUTSU_MAGIC_DAMAGE = 1227  # flat magic damage for elemental Ninjutsu only
BLUE_MAGIC_POINTS = 1228      # Blue Magic Point pool bonus from job points
RUNE_ENCHANTMENT = 1229       # Rune Enchantment effect bonus from job points
REGEN_DURATION = 339       # flat seconds of Regen duration ("Regen" effect duration +15)
REGEN_MULTIPLIER = 838     # "Regen" potency +x% (applies to the base tick before flats)
REGEN_POTENCY = 1223       # flat HP/tick from "Regen" potency gear (Bookworm's +10, Telchine +3)
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
# Bard songs.  The family ids add +N potency to that song line; 452 is every song,
# 453 adds active-song slots, 454 is duration, 455 is cast time and 833 is recast seconds.
MINNE_EFFECT = 433
MINUET_EFFECT = 434
PAEON_EFFECT = 435
REQUIEM_EFFECT = 436
THRENODY_EFFECT = 437
MADRIGAL_EFFECT = 438
MAMBO_EFFECT = 439
LULLABY_EFFECT = 440
ETUDE_EFFECT = 441
BALLAD_EFFECT = 442
MARCH_EFFECT = 443
FINALE_EFFECT = 444
CAROL_EFFECT = 445
MAZURKA_EFFECT = 446
ELEGY_EFFECT = 447
PRELUDE_EFFECT = 448
HYMNUS_EFFECT = 449
VIRELAI_EFFECT = 450
SCHERZO_EFFECT = 451
ALL_SONGS_EFFECT = 452    # "All songs"+N potency
MAXIMUM_SONGS_BONUS = 453  # additional active song slots
SONG_DURATION_BONUS = 454  # song duration +x%
SONG_SPELLCASTING_TIME = 455  # song cast time -x%
SONG_RECAST_DELAY = 833   # song recast -N seconds
ONE_HOUR_RECAST = 996      # one-hour ability recast -N minutes (the Master job-point gift)
STRATAGEM_RECAST = 997     # one strategem charge recast -N seconds (SCH's 550-JP gift)
ENSPELL_DURATION = 938     # En-spell duration +x seconds
ENSPELL_DMG_BONUS = 432    # "Sword enhancement spell damage"+n, flat per hit
ENSPELL_DMG_PCT = 1195     # "Sword enhancement spell damage"+x%, the weapon-only line
SNEAK_DURATION = 946       # Sneak duration +x seconds
INVISIBLE_DURATION = 947   # Invisible duration +x seconds
STONESKIN_BONUS_HP = 539   # extra Stoneskin HP
ENHANCES_REFRESH = 529     # "Enhances Refresh": +N MP per tick
# Dancer.  ``WALTZ_COST`` is LandSandBoat's 5-TP unit: value 5 is -50 TP.
WALTZ_COST = 139

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

# Blood Pact damage from set bonuses (Apogee Attire Set +1).  LandSandBoat has no
# named id for this; the BP formula adds it flat after the job-point bonus.
BLOOD_PACT_DAMAGE = 1241

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
# "Adds weapon skill": the item grants the weapon-skill id in the value (355 for the
# Prime, relic, mythic and empyrean weapons' own skills).
ADDS_WEAPONSKILL = 355
# "fTP +x" gear (Fotia Gorget/Belt).  LandSandBoat stores this in 1/256 fTP units:
# 25 is +0.0977, 256 is +1.0.
ANY_FTP_BONUS = 1144
# Fencer: TP Bonus for the weapon-skill calculation and its critical-hit rate, both
# only while single-wielding a one-handed weapon.
FENCER_TP_BONUS = 903
FENCER_CRIT_RATE = 904

# "Elemental weapon skill damage"+x% -- the Crocea Mors / Vitiation Sword / Duelist's
# Sword path-C augment.  It is a multiplier on the magical weapon-skill base before
# dSTAT/Magic Damage is added, which is why a Rank 25 +100% nearly doubles Seraph
# Blade and Sanguine Blade.  LSB has no id for it; this is a spare id.
ELEMENTAL_WS_DAMAGE = 1240

# Haste pools, hundredths of a percent: 1500 is 15%.  Retail keeps the three
# sources separate -- equipment caps at 25%, magic at 43.75% and job abilities at
# 25% -- and adds them before the 80% overall delay floor, so a capped gear set
# still benefits from Haste or a March.  LSB has no magic/ability haste modifier
# (its spell effects carry the power), so these use spare ids.
HASTE_GEAR = 384
HASTE_MAGIC = 1230
HASTE_ABILITY = 1231
TAME = 304


def percent(value: int) -> float:
    """10000 -> 1.0, -1000 -> -0.1.  The unit every damage-taken modifier uses."""
    return int(value) / 10000.0
