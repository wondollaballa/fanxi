"""Weapon skills that are more than a damage number.

Retail weapon skills split into three groups the damage engine alone cannot express:

* **Self-targeted skills** with no damage at all.  Myrkr restores MP and removes up to
  three status ailments, Dagan restores HP and MP, and both are used without a monster.
* **Drain skills** that convert the damage they dealt into MP or HP for the user
  (Spirit Taker, Mystic Boon, Entropy, Catastrophe, Sanguine Blade, Energy Drain/Steal).
* **Status-effect skills** that enfeeble the target after a landed hit: Poison, Stun,
  Silence, Blind, Bind, Sleep, Weight, Plague, Accuracy/Attack/Defense/Evasion Down,
  Magic Atk./Def./Eva. Down, INT Down and Critical Hit Evasion Down.

The numbers come from LandSandBoat's ``scripts/actions/weaponskills/*.lua``.  Durations
that retail scales with TP are stored at 1000/2000/3000 TP and interpolated linearly,
the same way the scripts' ``fTP`` helper does.  A ``chance`` effect is the scripts'
``math.randomInt(1, 100) <= tp / 30 * resist`` roll, i.e. ``tp / 3000`` at full
resistance.

The engine only reads the debuffs it can act on: Poison/Bio/Plague/Choke tick, Sleep,
Stun, Petrify and Bind stop the monster, Slow and Weight move its timer, and Accuracy,
Attack, Defense, Evasion, Magic Def., Magic Evasion, INT and Critical Hit Evasion Down
feed the hit-rate and damage paths.  Magic Atk. Down is stored but inert because
monsters never cast, and Silence is inert because they have no spells.  A skill whose
only effect is an aftermath (Empyrean/Relic/Mythic) still lands its damage; aftermath
is not modelled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import effects

TP_MAX = 3000
TP_FLOOR = 1000


@dataclass(frozen=True)
class Status:
    """One debuff a weaponskill can leave on its target."""

    effect: int
    # Seconds at 1000 / 2000 / 3000 TP.  A single value is a flat duration.
    duration: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Percentage the engine reads (Accuracy Down, Defense Down, Slow, ...).
    potency: float = 0.0
    # Flat power for effects that take a stat value (INT Down, Magic Evasion Down).
    power: int = 0
    # Damage every three seconds for the Poison / Plague / Choke family.
    tick: int = 0
    # True for the skills retail rolls for: tp / 3000 at full resistance.
    chance: bool = False


@dataclass(frozen=True)
class WeaponSkillEffect:
    """What a weapon skill does besides its damage."""

    # Myrkr and Dagan are self-targeted and usable with no claim.
    self_targeted: bool = False
    # The skill deals no damage at all (Myrkr, Dagan).
    no_damage: bool = False
    # Fraction of maximum MP restored at 1000 / 2000 / 3000 TP.
    mp_percent: tuple[float, float, float] = (0.0, 0.0, 0.0)
    hp_percent: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Fraction of the damage dealt restored as MP / HP at 1000 / 2000 / 3000 TP.
    mp_from_damage: float = 0.0
    hp_from_damage: tuple[float, float, float] = (0.0, 0.0, 0.0)
    # "energy_drain" / "energy_steal": the dagger formula, which does not use the hit.
    mp_formula: str = ""
    # Myrkr removes up to three status ailments.
    cures: int = 0
    statuses: tuple[Status, ...] = ()


@dataclass(frozen=True)
class AppliedEffect:
    """An effect ready for ``World.apply_mob_effect``.

    That method only needs these attributes, so this is the bridge between a
    weaponskill's table row and the monster status store.
    """

    effect: int
    duration: float = 0.0
    power: int = 0
    potency: int = 0
    tick: int = 0
    icon: int = 0
    kind: str = "debuff"
    mods: dict[int, int] = field(default_factory=dict)
    damage: bool = False
    resistible: bool = True


# --- TP scaling ------------------------------------------------------------------------------

def at_tp(tp: int, values: tuple[float, ...]) -> float:
    """Interpolate a 1000/2000/3000 TP line, clamped at both ends.

    This is LandSandBoat's ``xi.weaponskills.fTP(tp, {...})``: 1250 TP is a quarter of
    the way from the 1000 value to the 2000 value, and anything below 1000 is treated
    as 1000 levels of scaling rather than extrapolating below the floor.
    """
    if not values:
        return 0.0
    tp = max(TP_FLOOR, min(TP_MAX, int(tp)))
    if tp >= TP_MAX:
        return float(values[min(2, len(values) - 1)])
    if tp <= TP_FLOOR:
        return float(values[0])
    if tp <= 2000:
        span = float(values[0]) + (float(values[1]) - float(values[0])) * (tp - TP_FLOOR) / 1000.0
        return span
    span = float(values[1]) + (float(values[2]) - float(values[1])) * (tp - 2000) / 1000.0
    return span


def chance_at_tp(tp: int, resist: float = 1.0) -> float:
    """The roll a ``chance`` status gets: ``tp / 3000`` scaled by magic resistance."""
    return max(0.0, min(1.0, max(TP_FLOOR, min(TP_MAX, int(tp))) / TP_MAX * float(resist)))


# --- ailment list ----------------------------------------------------------------------------

# The effects Myrkr can take off.  Buffs, food and the enspell/enhancement icons are
# deliberately absent: a weapon skill cures ailments, not buffs.
AILMENTS = frozenset({
    effects.SLEEP, effects.POISON, effects.PARALYSIS, effects.BLINDNESS,
    effects.SILENCE, effects.PETRIFICATION, effects.STUN, effects.BIND, effects.WEIGHT,
    effects.SLOW, effects.PLAGUE, effects.DIA, effects.BIO, effects.CHOKE,
    effects.INT_DOWN, effects.ACCURACY_DOWN, effects.ATTACK_DOWN, effects.EVASION_DOWN,
    effects.DEFENSE_DOWN, effects.FLASH, effects.MAGIC_DEF_DOWN, effects.MAGIC_ATK_DOWN,
    effects.CRIT_HIT_EVASION_DOWN, effects.MAGIC_EVASION_DOWN, effects.INHIBIT_TP,
})

# Campaign-only weapon skills.  They need a Campaign Battle and a Campaign weapon, so
# they are not part of the normal 0x0AC list.  Tartarus Torpor is the odd one: the data
# import stores it with staff skill 12 and no requirement, where it would otherwise be
# advertised to every staff user at 350 skill.
CAMPAIGN_ONLY = frozenset({"uriel blade", "glory slash", "tartarus torpor"})


def _statuses(*items: Status) -> tuple[Status, ...]:
    return tuple(items)


# --- the table -------------------------------------------------------------------------------

def _table() -> dict[str, WeaponSkillEffect]:
    """Weapon-skill name -> its extra behaviour.

    Names are the ``weapon_skills`` display names folded with ``casefold``; a skill that
    is not here is a pure damage skill (or only an aftermath, which is not modelled).
    """
    return {
        # --- hand-to-hand ---------------------------------------------------------------
        "shoulder tackle": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (4, 4, 4), power=1, chance=True))),
        "shijin spiral": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PLAGUE, (18, 21, 24), power=5, tick=5))),

        # --- dagger ---------------------------------------------------------------------
        "wasp sting": WeaponSkillEffect(
            statuses=_statuses(Status(effects.POISON, (90, 105, 120), power=1, tick=1))),
        "viper bite": WeaponSkillEffect(
            statuses=_statuses(Status(effects.POISON, (90, 150, 210), power=3, tick=3))),
        "shadowstitch": WeaponSkillEffect(
            statuses=_statuses(Status(effects.BIND, (10, 15, 20), power=1, chance=True))),
        "energy steal": WeaponSkillEffect(no_damage=True, mp_formula="energy_steal"),
        "energy drain": WeaponSkillEffect(no_damage=True, mp_formula="energy_drain"),
        "mordant rime": WeaponSkillEffect(
            statuses=_statuses(Status(effects.WEIGHT, (60, 60, 60), potency=25,
                                     chance=True))),
        "pyrrhic kleos": WeaponSkillEffect(
            statuses=_statuses(Status(effects.EVASION_DOWN, (60, 120, 180), potency=10))),
        "rudras storm": WeaponSkillEffect(
            statuses=_statuses(Status(effects.WEIGHT, (60, 60, 60), potency=25))),
        "exenterator": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ACCURACY_DOWN, (90, 135, 180), potency=20))),

        # --- sword ----------------------------------------------------------------------
        "flat blade": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (4, 4, 4), power=1, chance=True))),
        "death blossom": WeaponSkillEffect(
            statuses=_statuses(Status(effects.MAGIC_EVASION_DOWN, (60, 60, 60),
                                     power=10))),
        "sanguine blade": WeaponSkillEffect(hp_from_damage=(0.5, 0.75, 1.0)),
        "uriel blade": WeaponSkillEffect(
            statuses=_statuses(Status(effects.FLASH, (15, 15, 15), potency=20))),
        "glory slash": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (2, 4, 6), power=1))),

        # --- great sword ----------------------------------------------------------------
        "shockwave": WeaponSkillEffect(
            statuses=_statuses(Status(effects.SLEEP, (60, 120, 180), power=1))),
        "herculean slash": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PARALYSIS, (60, 120, 180), potency=30))),

        # --- great axe ------------------------------------------------------------------
        "shield break": WeaponSkillEffect(
            statuses=_statuses(Status(effects.EVASION_DOWN, (180, 240, 300),
                                     potency=40))),
        "armor break": WeaponSkillEffect(
            statuses=_statuses(Status(effects.DEFENSE_DOWN, (180, 240, 300),
                                     potency=25))),
        "weapon break": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ATTACK_DOWN, (180, 240, 300), potency=25))),
        "smash axe": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (2, 4, 6), power=1))),
        "gale axe": WeaponSkillEffect(
            statuses=_statuses(Status(effects.CHOKE, (60, 60, 60), power=5, tick=5))),
        "full break": WeaponSkillEffect(
            statuses=_statuses(
                Status(effects.ATTACK_DOWN, (90, 120, 150), potency=12.5),
                Status(effects.DEFENSE_DOWN, (90, 120, 150), potency=12.5),
                Status(effects.ACCURACY_DOWN, (90, 120, 150), potency=20),
                Status(effects.EVASION_DOWN, (90, 120, 150), potency=20),
            )),
        "metatron torment": WeaponSkillEffect(
            statuses=_statuses(Status(effects.DEFENSE_DOWN, (120, 120, 120),
                                     potency=19))),
        "ukkos fury": WeaponSkillEffect(
            statuses=_statuses(Status(effects.SLOW, (60, 60, 60), potency=15))),
        "bora axe": WeaponSkillEffect(
            statuses=_statuses(Status(effects.BIND, (20, 20, 20), power=1, chance=True))),
        "onslaught": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ACCURACY_DOWN, (120, 120, 120),
                                     potency=30))),

        # --- scythe ---------------------------------------------------------------------
        "nightmare scythe": WeaponSkillEffect(
            statuses=_statuses(Status(effects.BLINDNESS, (60, 120, 180), potency=20))),
        "guillotine": WeaponSkillEffect(
            statuses=_statuses(Status(effects.SILENCE, (60, 90, 120)))),
        "catastrophe": WeaponSkillEffect(hp_from_damage=(0.5, 0.5, 0.5)),
        "infernal scythe": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ATTACK_DOWN, (180, 360, 540), potency=25))),
        "entropy": WeaponSkillEffect(mp_from_damage=0.2),

        # --- polearm --------------------------------------------------------------------
        "leg sweep": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (4, 4, 4), power=1, chance=True))),
        "stardiver": WeaponSkillEffect(
            statuses=_statuses(Status(effects.CRIT_HIT_EVASION_DOWN, (60, 60, 60),
                                     potency=5))),

        # --- katana ---------------------------------------------------------------------
        "blade retsu": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PARALYSIS, (30, 60, 120), potency=30))),
        "blade metsu": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PARALYSIS, (60, 60, 60), potency=10))),
        "blade kamu": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ACCURACY_DOWN, (60, 120, 180), potency=10))),
        "blade yu": WeaponSkillEffect(
            statuses=_statuses(Status(effects.POISON, (90, 105, 120), power=10, tick=10))),

        # --- great katana ---------------------------------------------------------------
        "tachi hobaku": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (3, 3, 3), power=1, chance=True))),
        "tachi yukikaze": WeaponSkillEffect(
            statuses=_statuses(Status(effects.BLINDNESS, (60, 60, 60), potency=25))),
        "tachi gekko": WeaponSkillEffect(
            statuses=_statuses(Status(effects.SILENCE, (45, 45, 45)))),
        "tachi kasha": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PARALYSIS, (60, 60, 60), potency=25))),
        "tachi ageha": WeaponSkillEffect(
            statuses=_statuses(Status(effects.DEFENSE_DOWN, (60, 120, 180), potency=25))),

        # --- club -----------------------------------------------------------------------
        "brainshaker": WeaponSkillEffect(
            statuses=_statuses(Status(effects.STUN, (2, 4, 6), power=1))),
        "skullbreaker": WeaponSkillEffect(
            statuses=_statuses(Status(effects.INT_DOWN, (140, 140, 140), power=10))),
        "randgrith": WeaponSkillEffect(
            statuses=_statuses(Status(effects.EVASION_DOWN, (120, 120, 120),
                                     potency=32))),
        "mystic boon": WeaponSkillEffect(mp_from_damage=1.0),
        "dagan": WeaponSkillEffect(self_targeted=True, no_damage=True,
                                   hp_percent=(0.22, 0.33, 0.52),
                                   mp_percent=(0.15, 0.22, 0.35)),

        # --- staff ----------------------------------------------------------------------
        "shell crusher": WeaponSkillEffect(
            statuses=_statuses(Status(effects.DEFENSE_DOWN, (180, 240, 300),
                                     potency=25))),
        "spirit taker": WeaponSkillEffect(mp_from_damage=1.0),
        "gate of tartarus": WeaponSkillEffect(
            statuses=_statuses(Status(effects.ATTACK_DOWN, (120, 120, 120),
                                     potency=18.75))),
        "vidohunir": WeaponSkillEffect(
            statuses=_statuses(Status(effects.MAGIC_DEF_DOWN, (60, 120, 180),
                                     power=10, potency=10))),
        "garland of bliss": WeaponSkillEffect(
            statuses=_statuses(Status(effects.DEFENSE_DOWN, (60, 120, 180),
                                     potency=12.5))),
        "omniscience": WeaponSkillEffect(
            statuses=_statuses(Status(effects.MAGIC_ATK_DOWN, (60, 120, 180),
                                     power=10, potency=10))),
        "myrkr": WeaponSkillEffect(self_targeted=True, no_damage=True,
                                   mp_percent=(0.2, 0.4, 0.6), cures=3),
        "shattersoul": WeaponSkillEffect(
            statuses=_statuses(Status(effects.MAGIC_DEF_DOWN, (120, 120, 120),
                                     power=10, potency=10))),

        # --- marksmanship ---------------------------------------------------------------
        "sniper shot": WeaponSkillEffect(
            statuses=_statuses(Status(effects.INT_DOWN, (140, 140, 140), power=10))),
        "numbing shot": WeaponSkillEffect(
            statuses=_statuses(Status(effects.PARALYSIS, (60, 120, 180), potency=30))),
    }


EFFECTS: dict[str, WeaponSkillEffect] = _table()


def for_weaponskill(name: str) -> WeaponSkillEffect | None:
    """The extra behaviour of a weapon skill name, or None when it is damage only."""
    return EFFECTS.get(" ".join(str(name).casefold().split()))


def is_campaign_only(name: str) -> bool:
    """True for the Campaign Battle weapon skills, which Fanxi cannot offer."""
    return " ".join(str(name).casefold().split()) in CAMPAIGN_ONLY


# --- the effect the drain skills restore -----------------------------------------------------

DAGGER_SKILL = 2


def drain_amount(name: str, *, tp: int, skill: int, mnd: int) -> int:
    """MP restored by Energy Drain/Energy Steal (their formula ignores the hit).

    LandSandBoat: ``(floor(dagger_skill * 0.11) + MND) * fTP`` with fTP anchors
    (1.25, 2.5, 4.125) for Energy Drain and (1.0, 2.1, 3.4) for Energy Steal.
    """
    folded = " ".join(str(name).casefold().split())
    if folded == "energy drain":
        ftp = at_tp(tp, (1.25, 2.5, 4.125))
    elif folded == "energy steal":
        ftp = at_tp(tp, (1.0, 2.1, 3.4))
    else:
        return 0
    base = int(int(skill) * 0.11) + int(mnd)
    return max(0, int(base * ftp))


def applied_status(status: Status, *, tp: int) -> AppliedEffect:
    """Flatten a table row into the object ``World.apply_mob_effect`` reads."""
    duration = at_tp(tp, status.duration)
    potency = int(status.potency)
    return AppliedEffect(
        effect=int(status.effect),
        duration=float(duration),
        power=int(status.power or potency),
        potency=potency,
        tick=int(status.tick),
        icon=int(status.effect),
    )
