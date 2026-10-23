"""Status effects for the spells the server can cast.

The client draws a buff icon from the effect id in ``0x037`` (the player's own status
list) and from the ``value`` field of a ``0x028`` action result (a buff that lands on a
monster).  The ids are the client's own, from LandSandBoat's ``data/status_effects.yaml``;
the durations and per-tier powers follow the spell scripts in
``scripts/actions/spells/ninjutsu`` and ``scripts/globals/spells/enfeebling_spell.lua``.

Only the effects the engine can actually act on are listed.  A spell with no entry is
still allowed to finish; it just does not put an icon on anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import modifiers as mod

# --- effect ids ----------------------------------------------------------------------------

SLEEP = 2
POISON = 3
PARALYSIS = 4
BLINDNESS = 5
SILENCE = 6
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
BIO = 135
ATTACK_DOWN = 147
EVASION_DOWN = 148
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
        "regen": SpellEffect(REGEN, "buff", 60, tick=5),
        "regen ii": SpellEffect(REGEN, "buff", 90, tick=10),
        "regen iii": SpellEffect(REGEN, "buff", 120, tick=15),
        "refresh": SpellEffect(REFRESH, "buff", 150, tick=3),
        "phalanx": SpellEffect(PHALANX, "buff", 180, power=20),
        "reraise": SpellEffect(RERAISE, "buff", 3600),
        "sneak": SpellEffect(SNEAK, "buff", 420),
        "invisible": SpellEffect(INVISIBLE, "buff", 420),
        "deodorize": SpellEffect(DEODORIZE, "buff", 420),
    }


SPELLS: dict[str, SpellEffect] = {}
SPELLS.update(_ninjutsu())
SPELLS.update(_black_magic())
SPELLS.update(_white_magic())


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
