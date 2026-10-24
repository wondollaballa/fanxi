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


SPELLS: dict[str, SpellEffect] = {}
SPELLS.update(_status_spells())     # every spell with an icon ...
SPELLS.update(SWEPT_EXTRAS)         # ... the long tail LSB does not table ...
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


def helix_duration(scholar_level_value: int) -> float:
    """How long a Helix's damage-over-time lasts.

    Retail ties the length to the Scholar level: 30 s at 20-39, 60 s at 40-59 and 90 s
    from 60.  A subbed Scholar caps at level 49, so a /SCH helix is 60 s at most.  Dark
    Arts and Tabula Rasa add damage and duration in retail; this engine only draws the
    arts' icons, so those bonuses are not applied here yet.
    """
    level = int(scholar_level_value)
    if level >= 60:
        return 90.0
    if level >= 40:
        return 60.0
    return 30.0


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

    Gear multiplies the spell's base tick; the flat bonuses come after, which is what
    LandSandBoat's enhancing script does.
    """
    tick = float(spec.tick)
    tick *= 1.0 + int(mods.get(mod.REGEN_MULTIPLIER, 0)) / 100.0
    tick = math.ceil(tick)
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
# own Job Abilities menu while those bonuses are still missing.
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
}
