"""Status effects for the spells the server can cast.

The client draws a buff icon from the effect id in ``0x037`` (the player's own status
list) and from the ``value`` field of a ``0x028`` action result (a buff that lands on a
monster).  The ids are the client's own, from LandSandBoat's ``data/status_effects.yaml``;
the durations and per-tier powers follow the spell scripts in
``scripts/actions/spells/ninjutsu`` and ``scripts/globals/spells/enfeebling_spell.lua``.

Two layers: ``spell_effects.STATUS_SPELLS`` is generated and covers every spell LandSandBoat
gives an icon to (Bar-, Boost-, the songs, the ga line, ...), then the tables below override
it with the spells whose numbers the engine actually reads (ticks, potency, modifiers).
A spell in neither still finishes; it just does not put an icon on anything.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from . import modifiers as mod
from .spell_effects import STATUS_SPELLS

# --- effect ids ----------------------------------------------------------------------------

SLEEP = 2
POISON = 3
PARALYSIS = 4
BLINDNESS = 5
SILENCE = 6
PETRIFICATION = 7
STUN = 10
BIND = 11
TRIPLE_SHOT = 467
WEIGHT = 12
SLOW = 13
PLAGUE = 31
HASTE = 33
BLINK = 36
STONESKIN = 37
AQUAVEIL = 39
PROTECT = 40
SHELL = 41
REGEN = 42
REFRESH = 43
COPY_IMAGE = 66
# The Copy Image icons carry the shadow count in the icon itself: 66 is one shadow,
# 444 is two, 445 is three and 446 is four or more.  Retail swaps the icon as the
# shadows are consumed, which is what draws the number on the buff bar.
COPY_IMAGE_2 = 444
COPY_IMAGE_3 = 445
COPY_IMAGE_4 = 446
INVISIBLE = 69
DEODORIZE = 70
SNEAK = 71
RERAISE = 113
PHALANX = 116
FOOD = 251
DIA = 134
BIO = 135
# One icon covers every Helix: the effect is the DoT, not the element.
HELIX = 186
# Long-tail spells the LandSandBoat tables stop short of; see SWEPT_EXTRAS below.
REQUIEM = 192
PAEON = 195
ENDARK = 288
KLIMAFORM = 407
ENLIGHT = 274
REGAIN = 170
ENMITY_DOWN = 291
# Song effects whose spells LandSandBoat's song table does not list (the trust songs).
HUM = 204
OPERETTA = 206
SERENADE = 208
FUGUE = 211
RHAPSODY = 212
ARIA = 213
# The debuff family weapon skills use, from LandSandBoat's status_effects.yaml ids.
CHOKE = 130
INT_DOWN = 140
ACCURACY_DOWN = 146
ATTACK_DOWN = 147
EVASION_DOWN = 148
DEFENSE_DOWN = 149
FLASH = 156
MAGIC_DEF_DOWN = 167
MAGIC_ATK_DOWN = 175
CRIT_HIT_EVASION_DOWN = 298
MAGIC_EVASION_DOWN = 404
INHIBIT_TP = 168
PAX = 171
STORE_TP = 227
ENMITY_BOOST = 289
SUBTLE_BLOW_PLUS = 290
MIGAWARI = 471
# Passive Trust auras.  Retail gives each walking-Geomancy Trust a COLURE_ACTIVE effect
# whose sub-effect is one of these ids and whose sub-icon is the matching GEO bubble.
# They stack with the player's own Haste/Refresh/Regen, which is why a Trust's Haste is
# an extra icon rather than a replacement for spell Haste.
TRUST_AURA_CHR = 807
TRUST_AURA_HASTE = 808
TRUST_AURA_EXP = 809
TRUST_AURA_ACC = 810
TRUST_AURA_REFRESH = 811
TRUST_AURA_REGEN = 812
TRUST_AURA_MAGIC_ATTACK = 813

# --- spell definitions ---------------------------------------------------------------------


@dataclass(frozen=True)
class SpellEffect:
    """What one spell puts on its target."""

    effect: int
    # "buff" lands on the caster, "debuff" on the monster, "special" is handled by name.
    kind: str = "buff"
    duration: float = 0.0
    power: int = 0          # shadows, blink count, or the tier's potency
    potency: int = 0        # percent: accuracy down, delay up, paralyze chance, ...
    tick: int = 0           # damage or healing per 3-second tick
    # Dia and Diaga do their small opening hit *and* land their debuff.  The damage comes
    # from the spell's own base (2/6/10/16/23), not the elemental nuke formula.
    damage: bool = False
    # A Helix is a nuke whose opening damage lands again every HELIX_TICK_SECONDS.  The
    # cast stores the rolled hit as the effect's tick, so the table's ``tick`` stays 0.
    helix: bool = False
    # Retail's Dia line cannot be resisted (except by Magic Shield or immunity), so its
    # duration must not be shortened by a weak caster's Magic Accuracy.
    resistible: bool = True
    icon: int = 0           # client icon when it differs from the effect id
    mods: dict[int, int] = field(default_factory=dict)


def _tier(name: str) -> int:
    """Ichi/Ni/San and I/II/III/IV/V are both worth 1, 2 and 3."""
    folded = name.casefold()
    if " san" in folded or folded.endswith("san") or " iii" in folded or folded.endswith("iii"):
        return 3
    if " ni" in folded or folded.endswith("ni") or " ii" in folded or folded.endswith("ii"):
        return 2
    return 1


def _ninjutsu() -> dict[str, SpellEffect]:
    return {
        # Utsusemi: 3/4/5 shadows.  The icon is the count: Copy Image, Copy Image (2),
        # (3) and (4).  Five shadows reuse the (4) icon, which is the highest one the
        # client has.
        "utsusemi ichi": SpellEffect(COPY_IMAGE, "buff", 900, power=3, icon=COPY_IMAGE_3),
        "utsusemi ni": SpellEffect(COPY_IMAGE, "buff", 900, power=4, icon=COPY_IMAGE_4),
        "utsusemi san": SpellEffect(COPY_IMAGE, "buff", 900, power=5, icon=COPY_IMAGE_4),
        "monomi ichi": SpellEffect(SNEAK, "buff", 420),
        "tonko ichi": SpellEffect(INVISIBLE, "buff", 420),
        "tonko ni": SpellEffect(INVISIBLE, "buff", 600),
        "gekka ichi": SpellEffect(ENMITY_BOOST, "buff", 300, potency=30),
        "kakka ichi": SpellEffect(STORE_TP, "buff", 180, potency=10),
        "migawari ichi": SpellEffect(MIGAWARI, "buff", 60),
        "myoshu ichi": SpellEffect(SUBTLE_BLOW_PLUS, "buff", 180, potency=10),
        "yain ichi": SpellEffect(PAX, "buff", 300, potency=15),
        # Enfeebles.  Potency is the client-facing percentage the spell's own data uses.
        "kurayami ichi": SpellEffect(BLINDNESS, "debuff", 180, potency=20),
        "kurayami ni": SpellEffect(BLINDNESS, "debuff", 300, potency=30),
        "kurayami san": SpellEffect(BLINDNESS, "debuff", 420, potency=40),
        "hojo ichi": SpellEffect(SLOW, "debuff", 180, potency=15),
        "hojo ni": SpellEffect(SLOW, "debuff", 300, potency=20),
        "hojo san": SpellEffect(SLOW, "debuff", 420, potency=30),
        "dokumori ichi": SpellEffect(POISON, "debuff", 60, tick=3),
        "dokumori ni": SpellEffect(POISON, "debuff", 120, tick=10),
        "dokumori san": SpellEffect(POISON, "debuff", 360, tick=20),
        "jubaku ichi": SpellEffect(PARALYSIS, "debuff", 180, potency=20),
        "jubaku ni": SpellEffect(PARALYSIS, "debuff", 300, potency=30),
        "jubaku san": SpellEffect(PARALYSIS, "debuff", 420, potency=35),
        "yurin ichi": SpellEffect(INHIBIT_TP, "debuff", 180, potency=10),
        "aisha ichi": SpellEffect(ATTACK_DOWN, "debuff", 120, potency=15),
    }


def _black_magic() -> dict[str, SpellEffect]:
    return {
        "sleep": SpellEffect(SLEEP, "debuff", 60),
        "sleep ii": SpellEffect(SLEEP, "debuff", 90),
        "sleepga": SpellEffect(SLEEP, "debuff", 60),
        "sleepga ii": SpellEffect(SLEEP, "debuff", 90),
        "blind": SpellEffect(BLINDNESS, "debuff", 180, potency=20),
        "blind ii": SpellEffect(BLINDNESS, "debuff", 180, potency=30),
        "blindga": SpellEffect(BLINDNESS, "debuff", 180, potency=25),
        "poison": SpellEffect(POISON, "debuff", 90, tick=3),
        "poison ii": SpellEffect(POISON, "debuff", 120, tick=6),
        "poison iii": SpellEffect(POISON, "debuff", 150, tick=9),
        "poisonga": SpellEffect(POISON, "debuff", 90, tick=3),
        "poisonga ii": SpellEffect(POISON, "debuff", 120, tick=6),
        "slow": SpellEffect(SLOW, "debuff", 180, potency=15),
        "slow ii": SpellEffect(SLOW, "debuff", 180, potency=25),
        "slowga": SpellEffect(SLOW, "debuff", 180, potency=15),
        "paralyze": SpellEffect(PARALYSIS, "debuff", 120, potency=20),
        "paralyze ii": SpellEffect(PARALYSIS, "debuff", 120, potency=30),
        "paralyzga": SpellEffect(PARALYSIS, "debuff", 120, potency=25),
        "gravity": SpellEffect(WEIGHT, "debuff", 120, potency=26),
        "gravity ii": SpellEffect(WEIGHT, "debuff", 180, potency=32),
        "graviga": SpellEffect(WEIGHT, "debuff", 120, potency=50),
        "bind": SpellEffect(BIND, "debuff", 60),
        "bindga": SpellEffect(BIND, "debuff", 60),
        # Break and Breakga are pure enfeebles: 30 seconds of Petrification and no direct
        # damage at all.  The old engine had no entry for them, so they fell through to
        # the direct-damage path and printed a bogus 233 damage for Breakga.
        "break": SpellEffect(PETRIFICATION, "debuff", 30),
        "breakga": SpellEffect(PETRIFICATION, "debuff", 30),
        "silence": SpellEffect(SILENCE, "debuff", 120),
        "silencega": SpellEffect(SILENCE, "debuff", 120),
        "stun": SpellEffect(STUN, "debuff", 5),
        "repose": SpellEffect(SLEEP, "debuff", 90),
        "bio": SpellEffect(BIO, "debuff", 60, tick=2),
        "bio ii": SpellEffect(BIO, "debuff", 120, tick=4),
        "bio iii": SpellEffect(BIO, "debuff", 180, tick=6),
        "bio iv": SpellEffect(BIO, "debuff", 240, tick=8),
        "bio v": SpellEffect(BIO, "debuff", 300, tick=10),
        "dispel": SpellEffect(0, "special"),
        "dispelga": SpellEffect(0, "special"),
        "drain": SpellEffect(0, "special"),
        "drain ii": SpellEffect(0, "special"),
        "drain iii": SpellEffect(0, "special"),
        "aspir": SpellEffect(0, "special"),
        "aspir ii": SpellEffect(0, "special"),
        "aspir iii": SpellEffect(0, "special"),
        "death": SpellEffect(0, "special"),
        "warp": SpellEffect(0, "special"),
        "warp ii": SpellEffect(0, "special"),
        "retrace": SpellEffect(0, "special"),
    }


def _white_magic() -> dict[str, SpellEffect]:
    return {
        # Dia: a small opening hit, then light-element damage every three seconds and a
        # Defence Down.  Retail: 1/2/3/4/5 HP per tick for 1/2/3/3/3 minutes, with the
        # -10/-15/-20/-25/-30% defence weakness.  Diaga shares the same numbers.
        "dia": SpellEffect(DIA, "debuff", 60, potency=10, tick=1,
                           damage=True, resistible=False),
        "dia ii": SpellEffect(DIA, "debuff", 120, potency=15, tick=2,
                              damage=True, resistible=False),
        "dia iii": SpellEffect(DIA, "debuff", 180, potency=20, tick=3,
                               damage=True, resistible=False),
        "dia iv": SpellEffect(DIA, "debuff", 180, potency=25, tick=4,
                              damage=True, resistible=False),
        "dia v": SpellEffect(DIA, "debuff", 180, potency=30, tick=5,
                             damage=True, resistible=False),
        "diaga": SpellEffect(DIA, "debuff", 60, potency=10, tick=1,
                             damage=True, resistible=False),
        "diaga ii": SpellEffect(DIA, "debuff", 120, potency=15, tick=2,
                                damage=True, resistible=False),
        "diaga iii": SpellEffect(DIA, "debuff", 180, potency=20, tick=3,
                                 damage=True, resistible=False),
        "diaga iv": SpellEffect(DIA, "debuff", 180, potency=25, tick=4,
                                damage=True, resistible=False),
        "diaga v": SpellEffect(DIA, "debuff", 180, potency=30, tick=5,
                               damage=True, resistible=False),
        "protect": SpellEffect(PROTECT, "buff", 1800, mods={mod.DEF_PERCENT: 10}),
        "protect ii": SpellEffect(PROTECT, "buff", 1800, mods={mod.DEF_PERCENT: 15}),
        "protect iii": SpellEffect(PROTECT, "buff", 1800, mods={mod.DEF_PERCENT: 20}),
        "protect iv": SpellEffect(PROTECT, "buff", 1800, mods={mod.DEF_PERCENT: 25}),
        "protect v": SpellEffect(PROTECT, "buff", 1800, mods={mod.DEF_PERCENT: 30}),
        "shell": SpellEffect(SHELL, "buff", 1800),
        "shell ii": SpellEffect(SHELL, "buff", 1800),
        "shell iii": SpellEffect(SHELL, "buff", 1800),
        "shell iv": SpellEffect(SHELL, "buff", 1800),
        "shell v": SpellEffect(SHELL, "buff", 1800),
        "stoneskin": SpellEffect(STONESKIN, "buff", 300, power=100),
        "blink": SpellEffect(BLINK, "buff", 300, power=2),
        "aquaveil": SpellEffect(AQUAVEIL, "buff", 600),
        "haste": SpellEffect(HASTE, "buff", 180, mods={mod.HASTE_GEAR: 1500}),
        "haste ii": SpellEffect(HASTE, "buff", 300, mods={mod.HASTE_GEAR: 3000}),
        # Regen is one minute at every tier except Regen (75 s); the old table had
        # Regen II/III at 90/120 s and 10/15 HP, which is not what retail casts.
        "regen": SpellEffect(REGEN, "buff", 75, tick=5),
        "regen ii": SpellEffect(REGEN, "buff", 60, tick=12),
        "regen iii": SpellEffect(REGEN, "buff", 60, tick=20),
        "regen iv": SpellEffect(REGEN, "buff", 60, tick=30),
        "regen v": SpellEffect(REGEN, "buff", 60, tick=40),
        "refresh": SpellEffect(REFRESH, "buff", 150, tick=3),
        "phalanx": SpellEffect(PHALANX, "buff", 180, power=20),
        "reraise": SpellEffect(RERAISE, "buff", 3600),
        "sneak": SpellEffect(SNEAK, "buff", 420),
        "invisible": SpellEffect(INVISIBLE, "buff", 420),
        "deodorize": SpellEffect(DEODORIZE, "buff", 420),
    }


def _helix() -> dict[str, SpellEffect]:
    """The Helix line: a nuke whose damage the monster takes again every ten seconds.

    LandSandBoat's enfeebling table records HELIX's ``BASE_TICK`` as 10 -- that is the
    interval in seconds, not ten damage.  The generated icon table used to read it as a
    damage tick, which is why Noctohelix turned into a flat 10 damage every three
    seconds.  The cast itself supplies the real tick (``min(damage, 9999)``); the
    duration comes from the Scholar's level (``helix_duration``).
    """
    out: dict[str, SpellEffect] = {}
    for element in ("geo", "hydro", "anemo", "pyro", "cryo", "iono", "nocto", "lumino"):
        for tier in ("", " ii"):
            out[element + "helix" + tier] = SpellEffect(
                HELIX, "debuff", 30.0, helix=True, resistible=False)
    return out


# --- helix timing ---------------------------------------------------------------------------
# The opening hit repeats every ten seconds ("tock").  Retail lands the first one 1-10
# seconds after the cast, then every ten; BG-wiki's Category:Helix and LSB's
# scripts/effects/helix.lua agree on the interval.  One tock is capped at 9,999; the
# opening hit is not.
HELIX_TICK_SECONDS = 10.0
HELIX_FIRST_TICK = (1.0, 10.0)
HELIX_TICK_CAP = 9999


def _status_spells() -> dict[str, SpellEffect]:
    """The generated icon table: what every spell puts up, before the numbers below."""
    return {name: SpellEffect(effect, kind, duration, tick=tick)
            for name, (effect, kind, duration, tick) in STATUS_SPELLS.items()}


# Spells LandSandBoat's four spell tables do not carry: the fourth and fifth Poison
# tiers, the tier-II -storm line (which has its own icons, 589-596: the client swaps the
# icon rather than just the timer), Enlight/Endark, Reraise II-IV, Adloquium and Animus,
# the -Carol II, -Threnody II and trust songs, and Klimaform.  Retail keeps the same
# effect id across most tier lines (a II spell reuses the base icon), so the base effect
# is the right icon there.
SWEPT_EXTRAS: dict[str, SpellEffect] = {
    "poison iv": SpellEffect(POISON, "debuff", 180, tick=12),
    "poison v": SpellEffect(POISON, "debuff", 210, tick=15),
    "poisonga iv": SpellEffect(POISON, "debuff", 180, tick=12),
    "poisonga v": SpellEffect(POISON, "debuff", 210, tick=15),
    "endark": SpellEffect(ENDARK, "buff", 180),
    "klimaform": SpellEffect(KLIMAFORM, "buff", 180),
    "foe requiem viii": SpellEffect(REQUIEM, "debuff", 300),
    "armys paeon vii": SpellEffect(PAEON, "buff", 120),
    "armys paeon viii": SpellEffect(PAEON, "buff", 120),
    # -storm II: retail's own effect ids 589-596, three minutes like the tier-I line.
    "firestorm ii": SpellEffect(589, "buff", 180),
    "hailstorm ii": SpellEffect(590, "buff", 180),
    "windstorm ii": SpellEffect(591, "buff", 180),
    "sandstorm ii": SpellEffect(592, "buff", 180),
    "thunderstorm ii": SpellEffect(593, "buff", 180),
    "rainstorm ii": SpellEffect(594, "buff", 180),
    "aurorastorm ii": SpellEffect(595, "buff", 180),
    "voidstorm ii": SpellEffect(596, "buff", 180),
    # Carol II reuses Carol's icon; the tier-II storms above are the only II line with
    # icons of its own.
    "fire carol ii": SpellEffect(216, "buff", 120),
    "ice carol ii": SpellEffect(216, "buff", 120),
    "wind carol ii": SpellEffect(216, "buff", 120),
    "earth carol ii": SpellEffect(216, "buff", 120),
    "lightning carol ii": SpellEffect(216, "buff", 120),
    "water carol ii": SpellEffect(216, "buff", 120),
    "light carol ii": SpellEffect(216, "buff", 120),
    "dark carol ii": SpellEffect(216, "buff", 120),
    # Enlight is Divine Magic, not Enhancing: it never gets Perpetuance, but it is still a
    # three-minute self buff with its own icon.  Endark II reuses Endark's icon.
    "enlight": SpellEffect(ENLIGHT, "buff", 180),
    "enlight ii": SpellEffect(ENLIGHT, "buff", 180),
    "endark ii": SpellEffect(ENDARK, "buff", 180),
    "reraise ii": SpellEffect(RERAISE, "buff", 3600),
    "reraise iii": SpellEffect(RERAISE, "buff", 3600),
    "reraise iv": SpellEffect(RERAISE, "buff", 3600),
    # Adloquium is Regain (TP per tick); Animus Augeo/Minuo are the enmity pair.
    "adloquium": SpellEffect(REGAIN, "buff", 180),
    "animus augeo": SpellEffect(ENMITY_BOOST, "buff", 180),
    "animus minuo": SpellEffect(ENMITY_DOWN, "buff", 180),
    # The six songs only the trust bards cast; they are still songs with icons.
    "chocobo hum": SpellEffect(HUM, "buff", 120),
    "jesters operetta": SpellEffect(OPERETTA, "buff", 120),
    "devotee serenade": SpellEffect(SERENADE, "buff", 120),
    "cactuar fugue": SpellEffect(FUGUE, "buff", 120),
    "moogle rhapsody": SpellEffect(RHAPSODY, "buff", 120),
    "protected aria": SpellEffect(ARIA, "buff", 120),
}


_ROMAN_TIERS = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
                "vii": 7, "viii": 8}


def _song_tier(name: str) -> int:
    words = str(name).casefold().split()
    if words and words[-1] in _ROMAN_TIERS:
        return _ROMAN_TIERS[words[-1]]
    return 1


def _bard_songs() -> dict[str, SpellEffect]:
    """Give the bard song families their actual stat/tick values.

    ``STATUS_SPELLS`` already supplies the icon and duration; this layer adds the
    per-tier effect the party reads.  It is deliberately small and data-driven: a song
    family with no number here still lands its icon.
    """
    out: dict[str, SpellEffect] = {}
    for name, base in STATUS_SPELLS.items():
        folded = " ".join(str(name).casefold().split())
        tier = _song_tier(folded)
        if "victory march" in folded:
            tier = 2
        elif "blade madrigal" in folded:
            tier = 2
        elif "dragonfoe mambo" in folded:
            tier = 2
        effect, kind, duration, _base_tick = base
        mods: dict[int, int] = {}
        tick = 0
        if "minne" in folded:
            mods[mod.DEF] = 10 * tier
        elif "minuet" in folded or "mambo" in folded:
            mods[mod.ATT] = 10 * tier
        elif "madrigal" in folded:
            mods[mod.ACC] = 5 * tier
        elif "march" in folded:
            mods[mod.HASTE_GEAR] = 3 * tier
        elif "ballad" in folded:
            mods[mod.REFRESH] = tier
        elif "paeon" in folded:
            mods[mod.REGEN] = tier
        elif "requiem" in folded:
            tick = tier
        elif "prelude" in folded:
            mods[mod.RACC] = 5 * tier
        elif "carol" in folded:
            mods[mod.MDEF] = 2 * tier
        elif "threnody" in folded:
            continue
        else:
            continue
        out[folded] = SpellEffect(effect, kind, duration, tick=tick, mods=mods)
    return out


SPELLS: dict[str, SpellEffect] = {}
SPELLS.update(_status_spells())     # every spell with an icon ...
SPELLS.update(SWEPT_EXTRAS)         # ... the long tail LSB does not table ...
SPELLS.update(_bard_songs())        # ... real song potency on top of the icons ...
SPELLS.update(_ninjutsu())          # ... then the curated mechanics win over both
SPELLS.update(_black_magic())
SPELLS.update(_white_magic())
SPELLS.update(_helix())


def for_spell(name: str) -> SpellEffect | None:
    """The effect a spell name applies, or None when it is damage/healing only."""
    return SPELLS.get(" ".join(str(name).casefold().split()))


def is_buff(effect: SpellEffect | None) -> bool:
    return effect is not None and effect.kind == "buff"


def is_debuff(effect: SpellEffect | None) -> bool:
    return effect is not None and effect.kind == "debuff"


def tier_of(name: str) -> int:
    return _tier(name)


def copy_image_icon(power: int) -> int:
    """The Copy Image icon for a remaining shadow count.

    The client draws the number from the icon, so the server has to move the effect
    between 66, 444, 445 and 446 as shadows are used up.  Four or more shadows all
    share the highest icon (446).
    """
    remaining = int(power)
    if remaining >= 4:
        return COPY_IMAGE_4
    if remaining == 3:
        return COPY_IMAGE_3
    if remaining == 2:
        return COPY_IMAGE_2
    return COPY_IMAGE


def icon_for(effect_id: int, icon: int = 0, power: int = 0) -> int:
    """The status icon to show for an effect, including its count.

    Most effects have a fixed icon (the effect id unless the table overrides it).
    Utsusemi is the exception: its icon *is* the remaining shadow count.
    """
    effect_id = int(effect_id)
    if effect_id == COPY_IMAGE:
        return copy_image_icon(power)
    return int(icon or effect_id)


# --- enhancing duration and Regen potency --------------------------------------------------

SCHOLAR = 20
ENFEEBLING_SKILL = 35
DARK_MAGIC_SKILL = 37
NINJUTSU_SKILL = 39
SONG_SKILLS = frozenset({40, 41, 42})
# Enfire..Enwater and their tier IIs carry the En-spell duration line.
ENSPELL_EFFECTS = frozenset(range(94, 100)) | frozenset(range(277, 283))
# Perpetuance affects white enhancing magic only.  Blaze/Ice/Shock Spikes share the
# Enhancing Magic skill but are black magic, so they keep their base duration.
BLACK_ENHANCING = frozenset({"blaze spikes", "ice spikes", "shock spikes"})


def is_white_enhancing(name: str) -> bool:
    """Whether an Enhancing Magic spell is white magic.

    The caller still checks the spell's skill; this only filters the black-magic spikes
    that share skill 34.
    """
    return " ".join(str(name).casefold().split()) not in BLACK_ENHANCING


def light_arts_regen(main_job: int, main_level: int) -> tuple[int, float]:
    """The (HP per tick, seconds) the level-based Light Arts bonus adds to Regen.

    BG-wiki: potency +floor((Level - 10) / 10) x 3, and duration twice that value in
    seconds.  Scholar main only; a subbed Scholar gets nothing.  The Light Arts Effect
    job points (+3 s/rank) are a separate term: ``buff_duration`` takes them as
    ``light_arts_jp_rank`` because this build does not store JP ranks yet -- the client's
    JP menu is filled with every category at rank 20 only to unlock gifts.
    """
    if int(main_job) != SCHOLAR:
        return 0, 0.0
    steps = max(0, (int(main_level) - 10) // 10)
    return steps * 3, float(steps * 6)


def perpetuance_multiplier(mods: Mapping[int, int]) -> float:
    """2.0x, plus the "Perpetuance"+x% on the equipped hands (Arbatel +3: +65%)."""
    return 2.0 + int(mods.get(mod.PERPETUANCE, 0)) / 10000.0


def buff_duration(
    spec: SpellEffect,
    *,
    main_job: int,
    main_level: int,
    mods: Mapping[int, int],
    skill: int = 0,
    light_arts: bool = False,
    tabula_rasa: bool = False,
    light_arts_jp_rank: int = 0,
    enhancing: bool = False,
    perpetuance: bool = False,
    white_enhancing: bool = False,
) -> float:
    """The duration retail gives one enhancing buff.

    This follows the formula on BG-wiki's Enhancing Magic page: flat bonuses (Light
    Arts/Tabula Rasa for Regen, its job points, and gear that lists seconds) are added to
    the base first.  Then the two percentage terms multiply separately -- "Duration
    listed on Gear" and "Duration Augments on Gear" are not the same factor -- and
    Perpetuance is last.  Spell-specific duration lines (Sneak, Invisible, En-spell,
    Ninjutsu, song) apply before those multipliers.
    """
    duration = float(spec.duration)
    if spec.effect == REGEN:
        duration += float(mods.get(mod.REGEN_DURATION, 0))
        if int(main_job) == SCHOLAR:
            if tabula_rasa:
                duration += 72.0
            elif light_arts:
                duration += light_arts_regen(main_job, main_level)[1]
            if light_arts or tabula_rasa:
                duration += 3.0 * max(0, min(20, int(light_arts_jp_rank)))
    elif spec.effect == SNEAK:
        duration += float(mods.get(mod.SNEAK_DURATION, 0))
    elif spec.effect == INVISIBLE:
        duration += float(mods.get(mod.INVISIBLE_DURATION, 0))
    elif spec.effect in ENSPELL_EFFECTS:
        duration += float(mods.get(mod.ENSPELL_DURATION, 0))
    if int(skill) == NINJUTSU_SKILL:
        duration += float(mods.get(mod.NINJUTSU_DURATION, 0))
    elif int(skill) in SONG_SKILLS:
        duration *= 1.0 + int(mods.get(mod.SONG_DURATION_BONUS, 0)) / 100.0
    if enhancing:
        duration += float(mods.get(mod.ENH_MAGIC_DURATION_FLAT, 0))
        duration *= 1.0 + int(mods.get(mod.ENH_MAGIC_DURATION, 0)) / 100.0
        duration *= 1.0 + int(mods.get(mod.ENH_MAGIC_DURATION_AUGMENT, 0)) / 100.0
    if perpetuance and white_enhancing:
        duration *= perpetuance_multiplier(mods)
    return max(0.0, duration)


def debuff_duration(spec: SpellEffect, *, skill: int,
                    mods: Mapping[int, int]) -> float:
    """An enfeebling/dark/ninjutsu/song spell's duration before the Magic Accuracy roll."""
    duration = float(spec.duration)
    if int(skill) == ENFEEBLING_SKILL:
        duration += float(mods.get(mod.ENF_MAG_DURATION_FLAT, 0))
        duration *= 1.0 + int(mods.get(mod.ENF_MAG_DURATION, 0)) / 100.0
    elif int(skill) == DARK_MAGIC_SKILL:
        duration *= 1.0 + int(mods.get(mod.DARK_MAGIC_DURATION, 0)) / 100.0
    elif int(skill) == NINJUTSU_SKILL:
        duration += float(mods.get(mod.NINJUTSU_DURATION, 0))
    elif int(skill) in SONG_SKILLS:
        duration *= 1.0 + int(mods.get(mod.SONG_DURATION_BONUS, 0)) / 100.0
    return max(0.0, duration)


def debuff_potency(spec: SpellEffect, *, skill: int,
                   mods: Mapping[int, int]) -> int:
    """The percentage potency an enfeebling spell applies after gear."""
    potency = int(spec.potency)
    if potency and int(skill) == ENFEEBLING_SKILL:
        potency = potency * (100 + int(mods.get(mod.ENF_MAG_POTENCY, 0))) // 100
    return max(0, potency)


def scholar_level(main_job: int, main_level: int, sub_job: int,
                  sub_level: int) -> int:
    """The caster's Scholar level, whether it is the main job or the support job."""
    if int(main_job) == SCHOLAR:
        return int(main_level)
    if int(sub_job) == SCHOLAR:
        return int(sub_level)
    return 0


def helix_duration(scholar_level_value: int, *, dark_arts: bool = False,
                   jp_rank: int = 0) -> float:
    """How long a Helix's damage-over-time lasts.

    Retail ties the length to the Scholar level: 30 s at 20-39, 60 s at 40-59 and 90 s
    from 60.  A subbed Scholar caps at level 49, so a /SCH helix is 60 s at most.  Dark
    Arts adds its job-point duration (+3 s per rank) while it is active.  Tabula Rasa's
    Helix bonus is not modelled yet.
    """
    level = int(scholar_level_value)
    if level >= 60:
        duration = 90.0
    elif level >= 40:
        duration = 60.0
    else:
        duration = 30.0
    if dark_arts:
        duration += 3.0 * max(0, min(20, int(jp_rank)))
    return duration


def regen_tick(
    spec: SpellEffect,
    *,
    main_job: int,
    main_level: int,
    mods: Mapping[int, int],
    light_arts: bool = False,
    tabula_rasa: bool = False,
) -> int:
    """HP per Regen tick after gear potency and the Light Arts/Tabula Rasa bonus.

    Percentage potency multiplies the spell's base tick, then flat ``"Regen" potency``
    gear adds HP per tick, and the Light Arts/Tabula Rasa bonus is last.  That is the
    order BG-wiki gives for Bookworm's Cape and the Telchine Duskdim augments.
    """
    tick = float(spec.tick)
    tick *= 1.0 + int(mods.get(mod.REGEN_MULTIPLIER, 0)) / 100.0
    tick = math.ceil(tick)
    tick += int(mods.get(mod.REGEN_POTENCY, 0))
    if spec.effect == REGEN and int(main_job) == SCHOLAR:
        if tabula_rasa:
            tick += 36
        elif light_arts:
            tick += light_arts_regen(main_job, main_level)[0]
    return max(0, int(tick))


def buff_tick(spec: SpellEffect, *, main_job: int, main_level: int,
              mods: Mapping[int, int], light_arts: bool = False,
              tabula_rasa: bool = False) -> int:
    """The per-three-second value for a ticking buff (Regen, Refresh, ...)."""
    if spec.effect == REGEN:
        return regen_tick(spec, main_job=main_job, main_level=main_level, mods=mods,
                          light_arts=light_arts, tabula_rasa=tabula_rasa)
    if spec.effect == REFRESH:
        return max(0, int(spec.tick) + int(mods.get(mod.ENHANCES_REFRESH, 0)))
    return max(0, int(spec.tick))


def buff_power(spec: SpellEffect, mods: Mapping[int, int]) -> int:
    """A buff's stored power (shadows, Stoneskin HP, Phalanx) after gear."""
    power = int(spec.power)
    if spec.effect == STONESKIN:
        power += int(mods.get(mod.STONESKIN_BONUS_HP, 0))
    return max(0, power)


def healing_amount(base: int, mods: Mapping[int, int],
                   target_mods: Mapping[int, int] | None = None) -> int:
    """A Cure's HP after ``"Cure" potency`` gear and the received-potency line."""
    potency = min(50, max(0, int(mods.get(mod.CURE_POTENCY, 0))))
    potency_ii = min(30, max(0, int(mods.get(mod.CURE_POTENCY_II, 0))))
    amount = float(base) * (100 + potency + potency_ii) / 100.0
    amount += int(mods.get(mod.CURE_POTENCY_BONUS, 0))
    if target_mods:
        amount *= 1.0 + max(0, int(target_mods.get(mod.CURE_POTENCY_RCVD, 0))) / 100.0
    return max(0, int(amount))


def drain_amount(base: int, mods: Mapping[int, int]) -> int:
    """Drain/Aspir's opening value after ``"Drain" and "Aspir"`` potency gear."""
    return max(0, int(base * (1.0 + int(mods.get(mod.DRAIN_ASPIR, 0)) / 100.0)))


# --- job abilities --------------------------------------------------------------------------

# The Scholar kit is almost all status icons, so it is the one line modelled here.  The
# ids are the client's own, from LandSandBoat's ``data/status_effects.yaml``.
SUBLIMATION = 187
TRANCE = 376
# Finishing Move 1-5 and the 6+ icon.  The server stores the real count in the power
# of FINISHING_MOVE and picks the icon from this tuple.
FINISHING_MOVE = 381
FINISHING_MOVES = (381, 382, 383, 384, 385, 588)
GRAND_PAS = 507
CONTRADANCE = 582
SABER_DANCE = 410
FAN_DANCE = 411
BUILDING_FLOURISH = 375
CLIMACTIC_FLOURISH = 443
STRIKING_FLOURISH = 468
TERNARY_FLOURISH = 472
# Dancer step Daze families.  Each family has one client icon per level, capped at 5
# on the bar; levels 6-10 share the level-5 icon but keep their real level in power.
LETHARGIC_DAZE = (386, 387, 388, 389, 390)      # Quickstep: Evasion Down
SLUGGISH_DAZE = (391, 392, 393, 394, 395)       # Box Step: Defense Down
WEAKENED_DAZE = (396, 397, 398, 399, 400)       # Stutter Step: Magic Evasion Down
BEWILDERED_DAZE = (448, 449, 450, 451, 452)     # Feather Step: Crit. Hit Evasion Down
PRESTO = 442
QUICKENING = 176                               # Chocobo Jig movement speed
CHAINBOUND = 798                               # Wild Flourish skillchain window
SNEAK_ATTACK = 65
TRICK_ATTACK = 87
ASTRAL_FLOW = 55
ASTRAL_CONDUIT = 504
AVATARS_FAVOR = 431
UNLEASH = 498
SPUR = 456
OVERDRIVE = 166
BOLSTER = 513
BLAZE_OF_GLORY = 569
ELEMENTAL_SFORZO = 522
SWORDPLAY = 532
EMBOLDEN = 534
ODYLLIC_SUBTERFUGE = 509
RETALIATION = 405
RESTRAINT = 435
INNER_STRENGTH = 491
MANA_WALL = 437
SENTINEL = 62
PALISADE = 478
BLOOD_WEAPON = 51
SOUL_ENSLAVEMENT = 497
NETHER_VOID = 439
DOUBLE_SHOT = 433
BIND = 11
TRIPLE_SHOT = 467
DECOY_SHOT = 482
SUBLIMATION_COMPLETE = 188
LIGHT_ARTS = 358
DARK_ARTS = 359
PENURY = 360
PARSIMONY = 361
CELERITY = 362
ALACRITY = 363
RAPTURE = 364
EBULLIENCE = 365
ACCESSION = 366
MANIFESTATION = 367
TABULA_RASA = 377
ADDENDUM_WHITE = 401
ADDENDUM_BLACK = 402
ALTRUISM = 412
FOCALIZATION = 413
TRANQUILITY = 414
EQUANIMITY = 415
ENLIGHTENMENT = 416
PERPETUANCE = 469
IMMANENCE = 470
# Non-Scholar ability statuses used by the job-point conditional layer.
MIGHTY_STRIKES = 44
HUNDRED_FISTS = 46
MANAFONT = 47
CHAINSPELL = 48
BERSERK = 56
DEFENDER = 57
AGGRESSOR = 58
FOCUS = 59
DODGE = 60
WARCRY = 68
DIVINE_SEAL = 78
ELEMENTAL_SEAL = 79
MANAWELL = 229
AFFLATUS_SOLACE = 417
AFFLATUS_MISERY = 418
COMPOSURE = 419
MANA_WALL = 437
SABOTEUR = 454
DIVINE_CARESS = 453
IMPETUS = 461
SACROSANCTITY = 477
BRAZEN_RUSH = 490
ASYLUM = 492
SUBTLE_SORCERY = 493
STYMIE = 494
VALLATION = 531
SHARPSHOT = 72
AZURE_LORE = 163
BURST_AFFINITY = 165
UNBRIDLED_LEARNING = 485
SPIRIT_SURGE = 126
SOUL_VOICE = 52
PIANISSIMO = 409
TENUTO = 455
MARCATO = 231
CLARION_CALL = 499
NIGHTINGALE = 347
TROUBADOUR = 348
DRAIN_SAMBA = 368
ASPIR_SAMBA = 369
HASTE_SAMBA = 370
SUBLIMATION = 187
TRANCE = 376
# Finishing Move 1-5 and the 6+ icon.  The server stores the real count in the power
# of FINISHING_MOVE and picks the icon from this tuple.
FINISHING_MOVE = 381
FINISHING_MOVES = (381, 382, 383, 384, 385, 588)
GRAND_PAS = 507
CONTRADANCE = 582
SABER_DANCE = 410
FAN_DANCE = 411
BUILDING_FLOURISH = 375
CLIMACTIC_FLOURISH = 443
STRIKING_FLOURISH = 468
TERNARY_FLOURISH = 472
# Dancer step Daze families.  Each family has one client icon per level, capped at 5
# on the bar; levels 6-10 share the level-5 icon but keep their real level in power.
LETHARGIC_DAZE = (386, 387, 388, 389, 390)      # Quickstep: Evasion Down
SLUGGISH_DAZE = (391, 392, 393, 394, 395)       # Box Step: Defense Down
WEAKENED_DAZE = (396, 397, 398, 399, 400)       # Stutter Step: Magic Evasion Down
BEWILDERED_DAZE = (448, 449, 450, 451, 452)     # Feather Step: Crit. Hit Evasion Down
PRESTO = 442
QUICKENING = 176                               # Chocobo Jig movement speed
CHAINBOUND = 798                               # Wild Flourish skillchain window
SNEAK_ATTACK = 65
TRICK_ATTACK = 87
ASTRAL_FLOW = 55
ASTRAL_CONDUIT = 504
AVATARS_FAVOR = 431
UNLEASH = 498
SPUR = 456
OVERDRIVE = 166
BOLSTER = 513
BLAZE_OF_GLORY = 569
ELEMENTAL_SFORZO = 522
SWORDPLAY = 532
EMBOLDEN = 534
ODYLLIC_SUBTERFUGE = 509
RETALIATION = 405
RESTRAINT = 435
INNER_STRENGTH = 491
MANA_WALL = 437
SENTINEL = 62
PALISADE = 478
BLOOD_WEAPON = 51
SOUL_ENSLAVEMENT = 497
NETHER_VOID = 439
DOUBLE_SHOT = 433
BIND = 11
TRIPLE_SHOT = 467
DECOY_SHOT = 482
PERFECT_COUNTER = 436
FOOTWORK = 406
COUNTERSTANCE = 61
KONZEN_ITTAI = 320


@dataclass(frozen=True)
class AbilityEffect:
    """The icon one job ability puts on the bar, and the ones it takes down."""

    effect: int
    duration: float = 60.0
    cancels: tuple[int, ...] = ()


# Keyed by the ``job_abilities`` row id.  Durations are the retail ones: the arts and the
# addenda last two hours, the stratagems a minute or until the next spell, and Tabula
# Rasa three minutes.  The arts also carry magic-cost and magic-accuracy bonuses in
# retail; this engine only draws their icons for now, so the bar matches the client's
# own Job Abilities menu while those bonuses are still missing.  Two stratagems are not
# icons only: Accession spreads the next white enhancing spell over the party
# (``ZoneSession.resolve_party_spell``) and Perpetuance doubles its duration.
ABILITY_EFFECTS: dict[int, AbilityEffect] = {
    210: AbilityEffect(TABULA_RASA, 180.0),
    # Light Arts takes down everything Dark Arts and its stratagems put up, and the other
    # way round, which is why the two cancel lists are mirror images.
    211: AbilityEffect(LIGHT_ARTS, 7200.0, (
        DARK_ARTS, ADDENDUM_BLACK, PARSIMONY, ALACRITY, MANIFESTATION, EBULLIENCE,
        FOCALIZATION, EQUANIMITY, IMMANENCE)),
    212: AbilityEffect(DARK_ARTS, 7200.0, (
        LIGHT_ARTS, ADDENDUM_WHITE, PENURY, CELERITY, ACCESSION, RAPTURE,
        ALTRUISM, TRANQUILITY, PERPETUANCE)),
    215: AbilityEffect(PENURY),
    216: AbilityEffect(CELERITY),
    217: AbilityEffect(RAPTURE),
    218: AbilityEffect(ACCESSION),
    219: AbilityEffect(PARSIMONY),
    220: AbilityEffect(ALACRITY),
    221: AbilityEffect(EBULLIENCE),
    222: AbilityEffect(MANIFESTATION),
    233: AbilityEffect(SUBLIMATION, 7200.0),
    234: AbilityEffect(ADDENDUM_WHITE, 7200.0, (DARK_ARTS, ADDENDUM_BLACK, LIGHT_ARTS)),
    235: AbilityEffect(ADDENDUM_BLACK, 7200.0, (LIGHT_ARTS, ADDENDUM_WHITE, DARK_ARTS)),
    240: AbilityEffect(ALTRUISM),
    241: AbilityEffect(FOCALIZATION),
    242: AbilityEffect(TRANQUILITY),
    243: AbilityEffect(EQUANIMITY),
    244: AbilityEffect(ENLIGHTENMENT),
    316: AbilityEffect(PERPETUANCE),
    317: AbilityEffect(IMMANENCE),
    # The job-point conditional layer needs the ability icon on the bar.  The base
    # ability's own stat mods are still modelled by the ability's own handler; these
    # entries exist so the matching category bonus can be active for their duration.
    16: AbilityEffect(MIGHTY_STRIKES, 30.0),
    17: AbilityEffect(HUNDRED_FISTS, 30.0),
    19: AbilityEffect(MANAFONT, 30.0),
    20: AbilityEffect(CHAINSPELL, 30.0),
    31: AbilityEffect(BERSERK, 180.0),
    32: AbilityEffect(WARCRY, 60.0),
    33: AbilityEffect(DEFENDER, 180.0),
    34: AbilityEffect(AGGRESSOR, 180.0),
    36: AbilityEffect(FOCUS, 60.0),
    37: AbilityEffect(DODGE, 60.0),
    74: AbilityEffect(DIVINE_SEAL, 60.0),
    75: AbilityEffect(ELEMENTAL_SEAL, 60.0),
    245: AbilityEffect(AFFLATUS_SOLACE, 7200.0, (AFFLATUS_MISERY,)),
    246: AbilityEffect(AFFLATUS_MISERY, 7200.0, (AFFLATUS_SOLACE,)),
    247: AbilityEffect(COMPOSURE, 7200.0),
    254: AbilityEffect(MANA_WALL, 30.0),
    269: AbilityEffect(IMPETUS, 60.0),
    270: AbilityEffect(DIVINE_CARESS, 60.0),
    271: AbilityEffect(SACROSANCTITY, 60.0),
    273: AbilityEffect(MANAWELL, 60.0),
    274: AbilityEffect(SABOTEUR, 60.0),
    323: AbilityEffect(BRAZEN_RUSH, 60.0),
    325: AbilityEffect(ASYLUM, 30.0),
    326: AbilityEffect(SUBTLE_SORCERY, 60.0),
    327: AbilityEffect(STYMIE, 60.0),
    93: AbilityEffect(AZURE_LORE, 60.0),
    95: AbilityEffect(BURST_AFFINITY, 60.0),
    298: AbilityEffect(UNBRIDLED_LEARNING, 120.0),
    338: AbilityEffect(UNBRIDLED_LEARNING, 60.0),
    29: AbilityEffect(SPIRIT_SURGE, 60.0),
    40: AbilityEffect(COUNTERSTANCE, 180.0),
    227: AbilityEffect(FOOTWORK, 60.0),
    253: AbilityEffect(PERFECT_COUNTER, 60.0),
    320: AbilityEffect(KONZEN_ITTAI, 60.0),
    25: AbilityEffect(SOUL_VOICE, 30.0),
    163: AbilityEffect(NIGHTINGALE, 60.0),
    164: AbilityEffect(TROUBADOUR, 60.0),
    229: AbilityEffect(PIANISSIMO, 60.0),
    283: AbilityEffect(TENUTO, 60.0),
    284: AbilityEffect(MARCATO, 60.0),
    332: AbilityEffect(CLARION_CALL, 60.0),
    # 120 s base plus the 20 Samba Duration ranks (+2 s each); Haste Samba is 90 s.
    184: AbilityEffect(DRAIN_SAMBA, 160.0),
    185: AbilityEffect(DRAIN_SAMBA, 160.0),
    186: AbilityEffect(DRAIN_SAMBA, 160.0),
    187: AbilityEffect(ASPIR_SAMBA, 160.0),
    188: AbilityEffect(ASPIR_SAMBA, 160.0),
    189: AbilityEffect(HASTE_SAMBA, 130.0),
    181: AbilityEffect(TRANCE, 60.0),
    237: AbilityEffect(SABER_DANCE, 300.0),
    238: AbilityEffect(FAN_DANCE, 300.0),
    341: AbilityEffect(GRAND_PAS, 60.0),
    384: AbilityEffect(CONTRADANCE, 60.0),
    44: AbilityEffect(SNEAK_ATTACK, 60.0),
    76: AbilityEffect(TRICK_ATTACK, 60.0),
    30: AbilityEffect(ASTRAL_FLOW, 60.0),
    250: AbilityEffect(AVATARS_FAVOR, 60.0),
    337: AbilityEffect(ASTRAL_CONDUIT, 60.0),
    135: AbilityEffect(OVERDRIVE, 60.0),
    281: AbilityEffect(SPUR, 60.0),
    331: AbilityEffect(UNLEASH, 60.0),
    343: AbilityEffect(BOLSTER, 60.0),
    350: AbilityEffect(BLAZE_OF_GLORY, 60.0),
    356: AbilityEffect(ELEMENTAL_SFORZO, 60.0),
    367: AbilityEffect(SWORDPLAY, 60.0),
    370: AbilityEffect(EMBOLDEN, 60.0),
    378: AbilityEffect(ODYLLIC_SUBTERFUGE, 60.0),
    226: AbilityEffect(RETALIATION, 60.0),
    252: AbilityEffect(RESTRAINT, 60.0),
    324: AbilityEffect(INNER_STRENGTH, 60.0),
    254: AbilityEffect(MANA_WALL, 60.0),
    48: AbilityEffect(SENTINEL, 60.0),
    278: AbilityEffect(PALISADE, 60.0),
    23: AbilityEffect(BLOOD_WEAPON, 60.0),
    330: AbilityEffect(SOUL_ENSLAVEMENT, 60.0),
    256: AbilityEffect(NETHER_VOID, 60.0),
    257: AbilityEffect(DOUBLE_SHOT, 60.0),
    286: AbilityEffect(DECOY_SHOT, 60.0),
    301: AbilityEffect(TRIPLE_SHOT, 60.0),
}
