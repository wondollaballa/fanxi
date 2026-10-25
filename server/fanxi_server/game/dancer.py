"""Dancer's job abilities: TP costs, waltz potency, Daze steps and finishing moves.

Dancer is a TP job.  A step, waltz or samba spends TP up front, and a flourish spends
the Finishing Moves earned by steps.  The old layer treated every dance as free and
made Curing Waltz a percentage of the caster's maximum HP, which is why a waltz looked
like a second Benediction.  The numbers here are retail's:

* Curing Waltz I-V cost 200/350/500/650/800 TP and restore
  ``floor((caster CHR + target VIT) * M + B + 2 * Waltz Potency ranks)`` HP, with M
  halved for a subbed Dancer (BG-wiki "Category:Waltz" and LandSandBoat's
  ``scripts/globals/job_utils/dancer.lua``).
* Steps cost 100 TP, apply one of the four Daze families at a level from 1 to 10
  (5 for a subbed Dancer) and grant Finishing Moves.
* Flourishes consume Finishing Moves; Reverse Flourish converts them back into TP.

The module holds data and pure arithmetic only.  ``zone.py`` owns the packets, the
character state and the party targeting.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import effects

# Dancer is job 19 in the client's job table, the same id ``characters.main_job`` uses.
DANCER_JOB = 19
# TP is stored in the client's 0..3000 units (1000 is the 100% shown on the bar).
TP_MAX = 3000
STEP_TP_COST = 100

# Base finishing moves, plus 2 per "Maximum Finishing Moves Bonus" job-point gift.  The
# server applies every job-point gift, so a Dancer main can hold 5 + 2 + 2 = 9.
BASE_FINISHING_MOVES = 5
FINISHING_MOVE_GIFTS = 2
FINISHING_MOVE_GIFT_BONUS = 2

# Merit ids (from LandSandBoat's data/merits.yaml; see merits.MERITS).
MERIT_STEP_ACCURACY = 0x0600
MERIT_HASTE_SAMBA = 0x0602
MERIT_REVERSE_FLOURISH = 0x0604
MERIT_BUILDING_FLOURISH = 0x0606
MERIT_FAN_DANCE = 0x0C82
MERIT_NO_FOOT_RISE = 0x0C84


@dataclass(frozen=True)
class WaltzSpec:
    ability_id: int
    name: str
    tp_cost: int
    slope: float
    base: int
    # Divine Waltzes heal the caster's party in a small radius around them.
    aoe: bool = False
    radius: float = 20.6
    # Healing Waltz removes one ailment instead of restoring HP.
    cleanse: bool = False


WALTZES: dict[int, WaltzSpec] = {
    190: WaltzSpec(190, "Curing Waltz", 200, 0.25, 60),
    191: WaltzSpec(191, "Curing Waltz II", 350, 0.50, 130),
    192: WaltzSpec(192, "Curing Waltz III", 500, 0.75, 270),
    193: WaltzSpec(193, "Curing Waltz IV", 650, 1.00, 450),
    311: WaltzSpec(311, "Curing Waltz V", 800, 1.25, 600),
    195: WaltzSpec(195, "Divine Waltz", 400, 0.25, 60, aoe=True, radius=10.0),
    262: WaltzSpec(262, "Divine Waltz II", 800, 0.50, 280, aoe=True, radius=10.0),
    194: WaltzSpec(194, "Healing Waltz", 200, 0.0, 0, radius=24.9, cleanse=True),
}

# The status ids a Healing Waltz may remove; these are the effects LandSandBoat flags
# with ``waltzable`` in data/status_effects.yaml (not every negative effect is magic).
WALTZABLE_EFFECTS = frozenset({
    effects.POISON, effects.PARALYSIS, effects.BLINDNESS, effects.SILENCE,
    effects.DISEASE, 9, effects.BIND, effects.WEIGHT, effects.SLOW, 21, 30,
    effects.PLAGUE,
    128, 129, 130, 131, 132, 133,          # Burn/Frost/Choke/Rasp/Shock/Drown
    effects.DIA, effects.BIO,
    136, 137, 138, 139, 140, 141, 142,     # STR..CHR Down
    144, 145,                              # Max HP/MP Down
    effects.ACCURACY_DOWN, effects.ATTACK_DOWN, effects.EVASION_DOWN,
    effects.DEFENSE_DOWN, effects.FLASH,
    effects.MAGIC_DEF_DOWN, 174, effects.MAGIC_ATK_DOWN,
    189, effects.ENMITY_DOWN, effects.CRIT_HIT_EVASION_DOWN,
    effects.MAGIC_EVASION_DOWN,
})


def waltz(ability_id: int) -> WaltzSpec | None:
    return WALTZES.get(int(ability_id))


def waltz_tp_cost(spec: WaltzSpec, *, contradance: bool = False,
                  contradance_jp: int = 0) -> int:
    """TP a waltz costs.  Contradance's job-point row cuts it by 3% per rank."""
    cost = int(spec.tp_cost)
    if contradance:
        cost = cost * max(10, 100 - min(90, int(contradance_jp))) // 100
    return max(0, cost)


def waltz_amount(spec: WaltzSpec, caster_chr: int, target_vit: int, *,
                 main_job: int = DANCER_JOB, jp_bonus: int = 0,
                 potency: int = 0, received: int = 0,
                 contradance: bool = False) -> int:
    """HP a Curing/Divine Waltz restores, before the missing-HP cap.

    BG-wiki's formula is
    ``floor((Waltz Potency + Waltz Potency Received) * floor(M*(CHR+VIT) + B + 2*rank))``.
    The job-point "Waltz Potency" row adds a flat 2 HP per rank, not 2%, so it belongs
    inside the inner floor.  A subbed Dancer's slope is halved, which is retail's rule.
    """
    if spec.cleanse:
        return 0
    slope = float(spec.slope) if int(main_job) == DANCER_JOB else float(spec.slope) / 2.0
    inner = math.floor((int(caster_chr) + int(target_vit)) * slope + int(spec.base))
    inner += max(0, int(jp_bonus))
    potency = max(0, min(50, int(potency)))
    received = max(0, min(30, int(received)))
    amount = math.floor(inner * (100 + potency + received) / 100.0)
    if contradance:
        amount *= 2
    return max(0, int(amount))


@dataclass(frozen=True)
class StepSpec:
    ability_id: int
    name: str
    family: tuple[int, ...]
    stat: str


STEPS: dict[int, StepSpec] = {
    201: StepSpec(201, "Quickstep", effects.LETHARGIC_DAZE, "evasion"),
    202: StepSpec(202, "Box Step", effects.SLUGGISH_DAZE, "defense"),
    203: StepSpec(203, "Stutter Step", effects.WEAKENED_DAZE, "magic_evasion"),
    312: StepSpec(312, "Feather Step", effects.BEWILDERED_DAZE, "crit_evasion"),
}


def step(ability_id: int) -> StepSpec | None:
    return STEPS.get(int(ability_id))


# 0x028 result ``info`` values the client turns into the step/flourish result line
# (LandSandBoat's actionInfo table): (miss, hit).
STEP_RESULT_INFO = {201: (1, 5), 202: (2, 6), 203: (3, 7), 312: (4, 8)}
FLOURISH_RESULT_INFO = {209: (1, 5), 205: (2, 6), 207: (3, 7)}


def result_info(ability_id: int, hit: bool) -> int:
    pair = STEP_RESULT_INFO.get(int(ability_id)) or FLOURISH_RESULT_INFO.get(
        int(ability_id))
    if pair is None:
        return 0
    return int(pair[1] if hit else pair[0])


def max_daze(main_job: int) -> int:
    """Daze caps at 10 for a Dancer main and 5 for a subjob Dancer."""
    return 10 if int(main_job) == DANCER_JOB else 5


def daze_status(spec: StepSpec, level: int) -> int:
    """The client status for a Daze level.  Levels 6-10 keep the level-5 icon."""
    level = max(1, min(5, int(level)))
    return int(spec.family[level - 1])


def daze_value(spec: StepSpec, level: int) -> int:
    """One Daze level's debuff value: flat for evasion/MEVA, percent for the rest."""
    level = max(1, int(level))
    if spec.stat == "evasion":
        # Quickstep: -8 at level 1 and another -4 per level (BG-wiki).
        return (level + 1) * 4
    if spec.stat == "defense":
        # Box Step: -5% at level 1 and another -2% per level.
        return 5 + 2 * (level - 1)
    if spec.stat == "magic_evasion":
        return 3 * level
    # Feather Step: +1% critical hit rate per level, stored as crit-evasion down.
    return level


def active_daze(effect_state, spec: StepSpec) -> tuple[int, int]:
    """(level, status id) of the target's active Daze for one step, or (0, 0)."""
    for index, status in enumerate(spec.family, start=1):
        state = effect_state.get(int(status))
        if state is not None:
            return max(1, int(state.get("power") or index)), int(status)
    return 0, 0


def step_duration(job_point_rank: int, previous_remaining: float = 0.0) -> float:
    """Daze duration: 60s first, +30s per step up to 120s, plus Step Duration JP."""
    bonus = max(0, int(job_point_rank))
    if previous_remaining > 0:
        return float(min(float(previous_remaining) + 30.0 + bonus, 120.0 + bonus))
    return 60.0 + bonus


def step_finishing_moves(main_job: int, *, presto: bool = False,
                         daze_at_max: bool = False) -> int:
    """Finishing Moves one landed step awards.

    Base 1, +1 for a Dancer main whose target's Daze was not already capped, and +4
    from Presto under the same condition.  A capped Daze still gives the base 1.
    """
    moves = 1
    if int(main_job) == DANCER_JOB and not daze_at_max:
        moves += 1
    if presto and not daze_at_max:
        moves += 4
    return moves


def max_finishing_moves(main_job: int) -> int:
    if int(main_job) != DANCER_JOB:
        return BASE_FINISHING_MOVES
    return BASE_FINISHING_MOVES + FINISHING_MOVE_GIFTS * FINISHING_MOVE_GIFT_BONUS


def finishing_move_icon(count: int) -> int:
    count = max(1, int(count))
    return int(effects.FINISHING_MOVES[min(count, len(effects.FINISHING_MOVES)) - 1])


@dataclass(frozen=True)
class FlourishSpec:
    ability_id: int
    name: str
    min_moves: int
    max_moves: int


FLOURISHES: dict[int, FlourishSpec] = {
    204: FlourishSpec(204, "Animated Flourish", 1, 2),
    205: FlourishSpec(205, "Desperate Flourish", 1, 1),
    207: FlourishSpec(207, "Violent Flourish", 1, 1),
    206: FlourishSpec(206, "Reverse Flourish", 1, 5),
    208: FlourishSpec(208, "Building Flourish", 1, 3),
    209: FlourishSpec(209, "Wild Flourish", 2, 2),
    264: FlourishSpec(264, "Climactic Flourish", 1, 5),
    313: FlourishSpec(313, "Striking Flourish", 2, 2),
    314: FlourishSpec(314, "Ternary Flourish", 3, 3),
}


def flourish(ability_id: int) -> FlourishSpec | None:
    return FLOURISHES.get(int(ability_id))


def reverse_flourish_tp(moves: int, *, jp_bonus: int = 0, merit_rank: int = 0,
                        square_mod: int = 5) -> int:
    """TP returned by Reverse Flourish.

    ``(95 + Flourish II JP + bonus) * moves + 5 * moves^2 + 30 * merit`` from
    BG-wiki; the job-point row is +2 per rank, so ``jp_bonus`` is 40 at rank 20.
    """
    moves = max(0, min(5, int(moves)))
    return int((95 + int(jp_bonus)) * moves + int(square_mod) * moves ** 2
               + 30 * int(merit_rank))


@dataclass(frozen=True)
class SambaSpec:
    ability_id: int
    name: str
    tp_cost: int
    status: int
    base_duration: float
    # HP/MP drained as a percentage of the damage the samba-augmented hit deals.
    on_hit_percent: int = 0
    haste: int = 0       # HASTE_GEAR units: 500 is 5%


SAMBAS: dict[int, SambaSpec] = {
    184: SambaSpec(184, "Drain Samba", 100, effects.DRAIN_SAMBA, 120.0, on_hit_percent=10),
    185: SambaSpec(185, "Drain Samba II", 100, effects.DRAIN_SAMBA, 120.0,
                  on_hit_percent=10),
    186: SambaSpec(186, "Drain Samba III", 100, effects.DRAIN_SAMBA, 120.0,
                  on_hit_percent=10),
    187: SambaSpec(187, "Aspir Samba", 100, effects.ASPIR_SAMBA, 120.0,
                  on_hit_percent=5),
    188: SambaSpec(188, "Aspir Samba II", 100, effects.ASPIR_SAMBA, 120.0,
                  on_hit_percent=5),
    189: SambaSpec(189, "Haste Samba", 350, effects.HASTE_SAMBA, 90.0, haste=500),
}


def samba(ability_id: int) -> SambaSpec | None:
    return SAMBAS.get(int(ability_id))


def samba_duration(spec: SambaSpec, job_point_bonus: int) -> float:
    return float(spec.base_duration) + max(0, int(job_point_bonus))


# Jigs.
SPECTRAL_JIG = 196
CHOCOBO_JIG = 197
CHOCOBO_JIG_II = 381


def jig_duration(base: float, job_point_bonus: int) -> float:
    return float(base) + max(0, int(job_point_bonus))


def jig_base(ability_id: int) -> float:
    if int(ability_id) == SPECTRAL_JIG:
        return 180.0
    if int(ability_id) == CHOCOBO_JIG:
        return 120.0
    if int(ability_id) == CHOCOBO_JIG_II:
        return 180.0
    return 0.0


# Self abilities.
TRANCE = 181
SABER_DANCE = 237
FAN_DANCE = 238
NO_FOOT_RISE = 239
PRESTO = 261
CONTRADANCE = 384
GRAND_PAS = 341


def is_waltz(ability_id: int) -> bool:
    return int(ability_id) in WALTZES


def is_step(ability_id: int) -> bool:
    return int(ability_id) in STEPS


def is_flourish(ability_id: int) -> bool:
    return int(ability_id) in FLOURISHES


def is_samba(ability_id: int) -> bool:
    return int(ability_id) in SAMBAS


def is_jig(ability_id: int) -> bool:
    return int(ability_id) in (SPECTRAL_JIG, CHOCOBO_JIG, CHOCOBO_JIG_II)


def is_dancer_ability(ability_id: int) -> bool:
    ability_id = int(ability_id)
    return (ability_id in WALTZES or ability_id in STEPS
            or ability_id in FLOURISHES or ability_id in SAMBAS
            or ability_id in (TRANCE, SABER_DANCE, FAN_DANCE, NO_FOOT_RISE,
                              PRESTO, CONTRADANCE, GRAND_PAS)
            or is_jig(ability_id))
