"""Skillchain and Magic Burst rules, following LandSandBoat.

The reference is:

* ``src/map/utils/battleutils.cpp`` -- ``GetSkillChainEffect``, ``FormSkillchain``,
  ``GetSkillchainTier`` and the ``skillchain_map`` transition table.
* ``scripts/combat/skillchain.lua`` -- the damage multiplier table and the element
  used for the resonance hit.
* ``scripts/combat/basic/magic_burst.lua`` -- the element match and burst tier.
* ``scripts/globals/spells/damage_spell.lua`` -- the Magic Burst damage multiplier,
  bonus cap and the ``+100`` Magic Accuracy term.
* ``data/enums/skillchain_type.yaml`` -- the ``SC_*`` ids used by the SQL table and
  by ``scripts/effects/skillchain.lua``.
* ``data/enums/action/proc_kind.h`` -- the 0x028 additional-effect proc ids.

The ids are **sequential** (1..16), not bit flags.  A weapon skill has three of them
(the SQL ``primary_sc``/``secondary_sc``/``tertiary_sc`` columns).  The first weaponskill
of a chain stores all three as an *opening*; the next one is matched against them.  A
successful link stores one ``SC_*`` id, not the component properties again.

This module is pure: it does not know about entities or packets.  The caller keeps one
``SkillchainState`` per monster and calls :func:`advance` after a landed weapon skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# Element ids match the client and the ``spells.element`` column.
ELEMENT_FIRE = 1
ELEMENT_ICE = 2
ELEMENT_WIND = 3
ELEMENT_EARTH = 4
ELEMENT_THUNDER = 5
ELEMENT_WATER = 6
ELEMENT_LIGHT = 7
ELEMENT_DARK = 8


class SC(IntEnum):
    """``xi.skillchainType`` from ``data/enums/skillchain_type.yaml``."""

    NONE = 0
    TRANSFIXION = 1      # Lv1 Light
    COMPRESSION = 2      # Lv1 Dark
    LIQUEFACTION = 3     # Lv1 Fire
    SCISSION = 4         # Lv1 Earth
    REVERBERATION = 5    # Lv1 Water
    DETONATION = 6       # Lv1 Wind
    INDURATION = 7       # Lv1 Ice
    IMPACTION = 8        # Lv1 Thunder
    GRAVITATION = 9      # Lv2 Dark & Earth
    DISTORTION = 10      # Lv2 Water & Ice
    FUSION = 11          # Lv2 Fire & Light
    FRAGMENTATION = 12   # Lv2 Wind & Thunder
    LIGHT = 13           # Lv3
    DARKNESS = 14        # Lv3
    LIGHT_II = 15        # Lv4 Light
    DARKNESS_II = 16      # Lv4 Darkness


TIER = {
    SC.NONE: 0,
    SC.TRANSFIXION: 1, SC.COMPRESSION: 1, SC.LIQUEFACTION: 1, SC.SCISSION: 1,
    SC.REVERBERATION: 1, SC.DETONATION: 1, SC.INDURATION: 1, SC.IMPACTION: 1,
    SC.GRAVITATION: 2, SC.DISTORTION: 2, SC.FUSION: 2, SC.FRAGMENTATION: 2,
    SC.LIGHT: 3, SC.DARKNESS: 3,
    SC.LIGHT_II: 4, SC.DARKNESS_II: 4,
}

# The element(s) a skillchain resonates with.  This is the mapping Magic Burst checks
# against the spell's element (``GetSkillchainMagicElement`` in battleutils.cpp).
SKILLCHAIN_ELEMENTS: dict[int, tuple[int, ...]] = {
    SC.NONE: (),
    SC.TRANSFIXION: (ELEMENT_LIGHT,),
    SC.COMPRESSION: (ELEMENT_DARK,),
    SC.LIQUEFACTION: (ELEMENT_FIRE,),
    SC.SCISSION: (ELEMENT_EARTH,),
    SC.REVERBERATION: (ELEMENT_WATER,),
    SC.DETONATION: (ELEMENT_WIND,),
    SC.INDURATION: (ELEMENT_ICE,),
    SC.IMPACTION: (ELEMENT_THUNDER,),
    SC.GRAVITATION: (ELEMENT_DARK, ELEMENT_EARTH),
    SC.DISTORTION: (ELEMENT_WATER, ELEMENT_ICE),
    SC.FUSION: (ELEMENT_LIGHT, ELEMENT_FIRE),
    SC.FRAGMENTATION: (ELEMENT_WIND, ELEMENT_THUNDER),
    SC.LIGHT: (ELEMENT_LIGHT, ELEMENT_FIRE, ELEMENT_WIND, ELEMENT_THUNDER),
    SC.DARKNESS: (ELEMENT_DARK, ELEMENT_EARTH, ELEMENT_WATER, ELEMENT_ICE),
    SC.LIGHT_II: (ELEMENT_LIGHT, ELEMENT_FIRE, ELEMENT_WIND, ELEMENT_THUNDER),
    SC.DARKNESS_II: (ELEMENT_DARK, ELEMENT_EARTH, ELEMENT_WATER, ELEMENT_ICE),
}

# ``skillchain_map`` from battleutils.cpp.  The key is (closing skill property,
# existing resonance), exactly as LSB's FormSkillchain looks it up.  The order of the
# key matters.  There is no "tier precedence" pass: FormSkillchain walks the opening
# properties in their stored order and the closing properties in their stored order,
# and returns the first key it finds.
TRANSITIONS: dict[tuple[int, int], int] = {
    # Level 3 pairs
    (SC.LIGHT, SC.LIGHT): SC.LIGHT_II,
    (SC.DARKNESS, SC.DARKNESS): SC.DARKNESS_II,

    # Level 2 pairs
    (SC.DISTORTION, SC.GRAVITATION): SC.DARKNESS,
    (SC.FRAGMENTATION, SC.GRAVITATION): SC.FRAGMENTATION,
    (SC.GRAVITATION, SC.DISTORTION): SC.DARKNESS,
    (SC.FUSION, SC.DISTORTION): SC.FUSION,
    (SC.GRAVITATION, SC.FUSION): SC.GRAVITATION,
    (SC.FRAGMENTATION, SC.FUSION): SC.LIGHT,
    (SC.DISTORTION, SC.FRAGMENTATION): SC.DISTORTION,
    (SC.FUSION, SC.FRAGMENTATION): SC.LIGHT,

    # Level 1 pairs -> Level 2
    (SC.SCISSION, SC.TRANSFIXION): SC.DISTORTION,
    (SC.IMPACTION, SC.LIQUEFACTION): SC.FUSION,
    (SC.COMPRESSION, SC.DETONATION): SC.GRAVITATION,
    (SC.REVERBERATION, SC.INDURATION): SC.FRAGMENTATION,

    # Level 1 pairs -> Level 1
    (SC.COMPRESSION, SC.TRANSFIXION): SC.COMPRESSION,
    (SC.REVERBERATION, SC.TRANSFIXION): SC.REVERBERATION,
    (SC.TRANSFIXION, SC.COMPRESSION): SC.TRANSFIXION,
    (SC.DETONATION, SC.COMPRESSION): SC.DETONATION,
    (SC.SCISSION, SC.LIQUEFACTION): SC.SCISSION,
    (SC.LIQUEFACTION, SC.SCISSION): SC.LIQUEFACTION,
    (SC.REVERBERATION, SC.SCISSION): SC.REVERBERATION,
    (SC.DETONATION, SC.SCISSION): SC.DETONATION,
    (SC.INDURATION, SC.REVERBERATION): SC.INDURATION,
    (SC.IMPACTION, SC.REVERBERATION): SC.IMPACTION,
    (SC.SCISSION, SC.DETONATION): SC.SCISSION,
    (SC.COMPRESSION, SC.INDURATION): SC.COMPRESSION,
    (SC.IMPACTION, SC.INDURATION): SC.IMPACTION,
    (SC.LIQUEFACTION, SC.IMPACTION): SC.LIQUEFACTION,
    (SC.DETONATION, SC.IMPACTION): SC.DETONATION,
}

# ``chainMultipliers`` from scripts/combat/skillchain.lua, indexed [tier][count - 1].
# The first link is count 1; LSB caps count at 5.
CHAIN_MULTIPLIERS = {
    1: (0.50, 0.60, 0.70, 0.80, 0.90, 1.00),
    2: (0.60, 0.75, 1.00, 1.25, 1.50, 1.75),
    3: (1.00, 1.50, 1.75, 2.00, 2.25, 2.50),
    4: (1.50, 1.80, 2.10, 2.40, 2.70, 3.00),
}

# ``resistanceRankMultiplier`` from scripts/combat/skillchain.lua.
RESISTANCE_RANK_MULTIPLIER = {
    -3: 1.50, -2: 1.30, -1: 1.15, 0: 1.00, 1: 0.85, 2: 0.70, 3: 0.60,
    4: 0.50, 5: 0.40, 6: 0.30, 7: 0.25, 8: 0.20, 9: 0.15, 10: 0.10, 11: 0.05,
}

# State timings from GetSkillChainEffect.  An opening effect lasts 10 s.  The next
# weapon skill must land *strictly more than* 3 s after the opening/last link; each
# successful link subtracts 1 s from the effect's duration and resets its start.
OPEN_SECONDS = 10.0
CHAIN_DELAY_SECONDS = 3.0
MAX_CHAIN_COUNT = 5

# 0x028 additional-effect proc ids (``ActionProcSkillChain``).  Note that this is a
# permutation of the SC_* ids and that Light II / Darkness II use the Light / Darkness
# proc ids (GetSkillchainSubeffect).
PROC_KIND = {
    SC.NONE: 0,
    SC.LIGHT: 1,
    SC.DARKNESS: 2,
    SC.GRAVITATION: 3,
    SC.FRAGMENTATION: 4,
    SC.DISTORTION: 5,
    SC.FUSION: 6,
    SC.COMPRESSION: 7,
    SC.LIQUEFACTION: 8,
    SC.INDURATION: 9,
    SC.REVERBERATION: 10,
    SC.TRANSFIXION: 11,
    SC.SCISSION: 12,
    SC.DETONATION: 13,
    SC.IMPACTION: 14,
    SC.LIGHT_II: 1,
    SC.DARKNESS_II: 2,
}

SKILLCHAIN_DAMAGE_MESSAGE = 287   # 287 + proc kind
SKILLCHAIN_ABSORB_MESSAGE = 384   # 384 + proc kind
MAGIC_BURST_MESSAGE = 252
MAGIC_BURST_DRAIN_HP_MESSAGE = 274


def _props(values) -> tuple[int, int, int]:
    """Normalise a WS property tuple to three ints, padding with none."""
    items = [int(value or 0) for value in tuple(values)[:3]]
    items.extend([0] * (3 - len(items)))
    return (items[0], items[1], items[2])


def form_skillchain(resonance, skill) -> int:
    """The SC formed by ``skill`` against ``resonance``, or ``SC.NONE``.

    ``resonance`` is the opening WS's three properties, or the single SC id of an
    already-formed chain.  ``skill`` is the closing WS's three properties.  This is
    ``FormSkillchain``: outer loop over resonance, inner loop over the closing WS,
    looking up ``(skill, resonance)``.  There is no tier ordering pass.
    """
    for resonance_element in resonance:
        resonance_element = int(resonance_element or 0)
        if not resonance_element:
            continue
        for skill_element in skill:
            skill_element = int(skill_element or 0)
            if not skill_element:
                continue
            result = TRANSITIONS.get((skill_element, resonance_element))
            if result is not None:
                return int(result)
    return int(SC.NONE)


@dataclass
class SkillchainState:
    """The ``Skillchain`` status effect on one monster.

    ``tier`` 0 is the opening state (properties in ``props``).  A formed chain has
    ``tier`` 1-4, ``sc`` set to the SC id, and ``count`` equal to the link number
    (1-based, capped at 5).  ``started``/``until`` are absolute timestamps.
    """

    props: tuple[int, int, int] = (0, 0, 0)
    tier: int = 0
    sc: int = 0
    count: int = 0
    started: float = 0.0
    until: float = 0.0

    def expired(self, now: float) -> bool:
        return now > self.until

    def is_opening(self, now: float) -> bool:
        return self.tier == 0 and now <= self.until

    def is_formed(self, now: float) -> bool:
        return self.tier > 0 and now <= self.until


def _opening(props: tuple[int, int, int], now: float) -> SkillchainState:
    return SkillchainState(props=props, started=now, until=now + OPEN_SECONDS)


def advance(state: SkillchainState | None, props, now: float
            ) -> tuple[SkillchainState | None, int]:
    """Feed one landed weapon skill's properties into the target's state.

    Returns ``(new_state, formed_sc)``; ``formed_sc`` is ``SC.NONE`` when this WS only
    opened (or reset) the state.  A WS with no properties does not alter the state at
    all, matching LSB's ``primary_sc != 0`` gate.
    """
    props = _props(props)
    if not any(props):
        return state, int(SC.NONE)
    if state is None or now > state.until:
        return _opening(props, now), int(SC.NONE)
    # A WS that lands too soon does not chain; it replaces the opening state.
    if now <= state.started + CHAIN_DELAY_SECONDS:
        return _opening(props, now), int(SC.NONE)
    resonance = (state.sc,) if state.tier > 0 else state.props
    formed = form_skillchain(resonance, props)
    if not formed:
        return _opening(props, now), int(SC.NONE)
    # LSB resets the start and reduces the duration by 1 s on every link.
    old_duration = max(0.0, state.until - state.started)
    return (SkillchainState(
        props=props, tier=int(TIER[formed]), sc=formed,
        count=min(state.count + 1, MAX_CHAIN_COUNT),
        started=now, until=now + max(0.0, old_duration - 1.0),
    ), formed)


def chain_multiplier(tier: int, count: int) -> float:
    """The skillchain damage multiplier for a tier and 1-based link count."""
    tier = int(tier)
    count = int(count)
    if tier not in CHAIN_MULTIPLIERS or count < 1:
        return 0.0
    table = CHAIN_MULTIPLIERS[tier]
    return table[min(count, len(table)) - 1]


def skillchain_damage(base_damage: int, tier: int, count: int, *,
                      skillchain_bonus: int = 0, skillchain_damage: int = 0,
                      magic_damage: int = 0, resistance_rank: int = 0,
                      damage_taken: float = 1.0) -> int:
    """Damage of one skillchain resonant hit.

    The base is the **closing weapon skill's total damage**, not the SC's own damage
    roll.  The bonuses follow LSB's order (floor after each multiplication):

    ``base * chain_multiplier * (1 + Skillchain Bonus) + Magic Damage``
    ``* (1 + Skillchain Damage / 10000) * resistance-rank * damage-taken``.

    Day/weather, elemental staff and affinity multipliers are not modelled yet; the
    default rank 0 multiplier is 1.0.  The result is capped at 99,999 as in LSB.
    """
    multiplier = chain_multiplier(tier, count)
    if multiplier <= 0:
        return 0
    damage = int(abs(int(base_damage)) * multiplier)
    damage = int(damage * (1.0 + max(0, int(skillchain_bonus)) / 100.0))
    damage += max(0, int(magic_damage))
    damage = int(damage * (1.0 + max(0, int(skillchain_damage)) / 10000.0))
    rank = max(-3, min(11, int(resistance_rank)))
    damage = int(damage * RESISTANCE_RANK_MULTIPLIER[rank])
    damage = int(damage * max(0.0, float(damage_taken)))
    return max(0, min(99999, damage))


def proc_kind(sc: int) -> int:
    """The 0x028 ``additional effect`` proc id for a skillchain."""
    return int(PROC_KIND.get(int(sc), 0))


def proc_message(sc: int, *, absorbed: bool = False) -> int:
    """The 0x028 add-effect message for a skillchain (0 when not a skillchain)."""
    kind = proc_kind(sc)
    if not kind:
        return 0
    return (SKILLCHAIN_ABSORB_MESSAGE if absorbed else SKILLCHAIN_DAMAGE_MESSAGE) + kind


# Magic Burst.  ``rankTable`` and the ``1.25 + rank + 0.1 * tier`` shape are from
# scripts/globals/spells/damage_spell.lua's calculateIfMagicBurst.  ``tier`` is the
# link count (1-5), not the SC tier.
MAGIC_BURST_RANK_TABLE = (1.50, 1.15, 0.85, 0.60, 0.50, 0.40, 0.15, 0.05,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def magic_burst_tier(state: SkillchainState | None, element: int, now: float) -> int:
    """The burst tier (link count) for a spell element, or 0 when it is not a burst."""
    if state is None or state.tier <= 0 or now > state.until:
        return 0
    if int(element) in SKILLCHAIN_ELEMENTS.get(int(state.sc), ()):
        return int(state.count)
    return 0


def magic_burst_multiplier(tier: int, resistance_rank: int = 0, *,
                           pc: bool = True) -> float:
    """The base Magic Burst damage multiplier.

    For a neutral resistance rank this is ``1.75 + 0.1 * tier``: 1.85 at the first
    link, 2.25 at the fifth.  It is *not* the 1.35/1.45 step table sometimes quoted.
    """
    if int(tier) <= 0:
        return 1.0
    rank = max(-3, min(11, int(resistance_rank)))
    return 1.25 + MAGIC_BURST_RANK_TABLE[rank + 4] + (0.10 if pc else 0.05) * int(tier)


def magic_burst_bonus(capped: int, uncapped: int = 0) -> float:
    """The gear/trait Magic Burst Bonus multiplier.

    ``MAGIC_BURST_BONUS_CAPPED`` (487) is capped at +40%; ``..._UNCAPPED`` (274) has
    no cap.  The result multiplies the base MB multiplier.
    """
    capped_bonus = max(0.0, min(0.40, int(capped) / 100.0))
    uncapped_bonus = max(0.0, int(uncapped) / 100.0)
    return 1.0 + capped_bonus + uncapped_bonus


def magic_burst_macc_bonus(tier: int) -> int:
    """The flat Magic Accuracy a Magic Burst adds (``magicAccuracyFromMagicBurst``)."""
    return 100 if int(tier) > 0 else 0
