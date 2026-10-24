"""The stat sheet: base attributes, gear modifiers, and the numbers combat reads.

Retail never reads "Attack" off the character sheet directly.  It derives three separate
numbers from level, job, skills and gear:

* ``Attack`` -- ``8 + gear Attack + STR x class multiplier + weapon skill``
* ``Defense`` -- ``8 + VIT x 1.5 + a level factor + gear Defense``
* ``Accuracy`` / ``Evasion`` -- the skill curve plus ``DEX`` / ``AGI`` plus gear

This module builds one ``Sheet`` per character (or monster) and caches nothing: the
callers hold the sheet for the duration of a swing.

The formulas are in ``docs/combat-damage.md``; the mob curves are LandSandBoat's
``mobutils::GetBaseDefEva`` / ``GetBaseToRank`` / ``GetBaseSkill``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import base_stats, combat, modifiers as mod, skills

# Equipment slot ids, matching char_equip.kind and the client's own slot order.
SLOT_MAIN = 0
SLOT_SUB = 1
SLOT_RANGED = 2
SLOT_AMMO = 3

EVASION_SKILL = 29
GUARD_SKILL = 28
SHIELD_SKILL = 30
PARRY_SKILL = 31

# Unarmed swings use the H2H delay; a weapon carries its own.
UNARMED_DELAY = 480

# The one-handed weapon skills that can be dual wielded.  Hand-to-hand is a separate
# case: both fists swing without a Dual Wield trait and without an off-hand weapon.
ONE_HANDED_SKILLS = frozenset({2, 3, 5, 9, 11})   # dagger, sword, axe, katana, club


@dataclass(frozen=True)
class Weapon:
    """The parts of an equipped item the damage engine needs."""

    item_id: int = 0
    skill: int = 0
    dmg: int = 0
    delay: int = 0
    ilvl_skill: int = 0

    @property
    def h2h(self) -> bool:
        return self.skill == combat.H2H_SKILL

    @property
    def two_handed(self) -> bool:
        return self.skill in combat.TWO_HANDED_SKILLS

    @property
    def one_handed(self) -> bool:
        return self.skill in ONE_HANDED_SKILLS


@dataclass(frozen=True)
class Sheet:
    """Everything one fighter contributes to a swing."""

    fighter: combat.Fighter
    attributes: dict[str, int] = field(default_factory=dict)   # base + gear
    base_attributes: dict[str, int] = field(default_factory=dict)  # base only
    weapon: Weapon = field(default_factory=Weapon)
    delay: int = UNARMED_DELAY
    haste: float = 0.0
    max_hp: int = 1
    max_mp: int = 0
    shield_size: int = 0
    # The off-hand half of a dual-wielded attack round.  Both are None whenever the
    # character cannot dual wield (no trait, a shield in the sub slot, a two-hander).
    sub_weapon: Weapon | None = None
    sub_fighter: combat.Fighter | None = None
    dual_wield: bool = False
    # The Dual Wield trait's percent, kept for the per-hand TP delay.
    dual_wield_percent: int = 0

    @property
    def attack_delay_ms(self) -> int:
        """Swing interval in milliseconds, after equipment haste.

        Item delay is in sixtieths of a second, which is why a 450-delay katana swings
        every 7.5 seconds at zero haste.  Equipment haste caps at 25%, and the swing
        interval itself cannot drop below a fifth of the base delay.

        ``delay`` is already the per-hand delay: for dual wield it is
        ``(main + sub) * (1 - Dual Wield%) / 2``, because both hands swing together
        once per attack round.  TP is separate: it uses each weapon's own delay (see
        ``tp_per_hit``).
        """
        base_ms = max(1, int(self.delay)) * 1000.0 / 60.0
        haste = min(0.25, max(-1.0, self.haste))
        return max(1, int(base_ms * max(0.2, 1.0 - haste)))

    def tp_per_hit(self, off_hand: bool = False) -> int:
        """TP from one landed hit by this hand, in tenths.

        Retail computes TP from *that weapon's* base delay, with Dual Wield halving the
        reduced delay for each hand, and does not give the off hand the main hand's
        number.  Store TP is applied by ``combat.tp_gain`` after this.
        """
        weapon = (self.sub_weapon if off_hand and self.sub_weapon is not None
                  else self.weapon)
        delay = max(1, int((weapon.delay if weapon is not None else 0) or UNARMED_DELAY))
        if self.dual_wield:
            delay = combat.tp_delay(delay, dual_wield=self.dual_wield_percent)
        return combat.tp_return(delay)

    @property
    def attack(self) -> int:
        return self.fighter.attack

    @property
    def defense(self) -> int:
        return self.fighter.defense

    @property
    def accuracy(self) -> int:
        return self.fighter.accuracy

    @property
    def evasion(self) -> int:
        return self.fighter.evasion


def _level_defense_factor(level: int) -> int:
    """Retail's level contribution to Defense."""
    if level < 51:
        return level
    if level < 61:
        return 2 * level - 42
    if level < 91:
        return level + 18
    return level + 18 + (level - 89) // 2


def _str_multiplier(weapon: Weapon) -> float:
    if weapon.two_handed:
        return combat.STR_TO_ATT_TWO_HANDED
    if weapon.h2h:
        return combat.STR_TO_ATT_H2H
    return combat.STR_TO_ATT_MAIN


def _natural_h2h_damage(skill: int) -> int:
    """Bare fists: the H2H skill turns into a small damage rating."""
    return int(skill * 0.11) + 3


def _weapon_skill_value(weapon: Weapon, skill_values: dict[int, int]) -> int:
    return int(skill_values.get(weapon.skill, 0)) + int(weapon.ilvl_skill)


def _damage_rating(weapon: Weapon, skill_value: int) -> int:
    if weapon.dmg > 0:
        return int(weapon.dmg)
    if weapon.skill == combat.H2H_SKILL:
        return _natural_h2h_damage(skill_value)
    return 0


def _food_percent(base: int, mods: dict[int, int], percent_id: int,
                  cap_id: int) -> int:
    """A food percentage bonus, capped at the flat cap the food carries."""
    percent = int(mods.get(percent_id, 0))
    if percent <= 0:
        return 0
    bonus = int(base) * percent // 100
    cap = int(mods.get(cap_id, 0))
    return min(bonus, cap) if cap > 0 else bonus


def _attack_value(mods: dict[int, int], strength: int, skill_value: int,
                  str_multiplier: float) -> int:
    attack = 8 + int(mods.get(mod.ATT, 0))
    attack += int(strength * str_multiplier)
    attack += skill_value
    attack += _food_percent(attack, mods, mod.FOOD_ATT_PERCENT, mod.FOOD_ATT_CAP)
    return max(1, attack + attack * int(mods.get(mod.ATT_PERCENT, 0)) // 100)


def _accuracy_value(mods: dict[int, int], dexterity: int, skill_value: int) -> int:
    accuracy = combat.acc_from_skill(skill_value)
    accuracy += int(dexterity * combat.DEX_TO_ACC)
    accuracy += int(mods.get(mod.ACC, 0))
    accuracy += _food_percent(accuracy, mods, mod.FOOD_ACC_PERCENT, mod.FOOD_ACC_CAP)
    return accuracy


def _with_percent(value: int, percent: int, *, floor: int) -> int:
    """Apply an HP/MP percentage modifier to a maximum, clamped to *floor*.

    ``HP+10%`` (mod.HPP) multiplies the maximum after the flat HP bonus, which is
    how the client's own status screen treats it; the same rule covers MP.
    """
    value = int(value) + int(value) * int(percent) // 100
    return max(int(floor), value)


def build_character(char: dict, mods: dict[int, int], skill_values: dict[int, int],
                    main_weapon: Weapon | None = None,
                    sub_weapon: Weapon | None = None,
                    shield_size: int = 0,
                    dual_wield: bool | None = None) -> Sheet:
    """The sheet for a player character.

    Dual wield is a job trait, not just two weapons: with both one-handed hands filled
    and the trait active, the sheet carries a second ``Fighter`` for the off hand and
    an attack-round delay built from both weapons.  ``dual_wield`` is the trait gate;
    it defaults to "the modifier is present" so direct callers and tests can build a
    sheet from a modifier dict alone.
    """
    level = max(1, int(char.get("main_level", 1)))
    job = int(char.get("main_job", 1))
    sub_job = int(char.get("sub_job", 0))
    sub_level = int(char.get("sub_level", 0))

    base = base_stats.base_stats(int(char.get("race", 1)), job, level, sub_job, sub_level)
    attributes = {name: int(base.get(name, 0)) + int(mods.get(key, 0))
                  for name, key in (("str", mod.STR), ("dex", mod.DEX), ("vit", mod.VIT),
                                    ("agi", mod.AGI), ("int", mod.INT), ("mnd", mod.MND),
                                    ("chr", mod.CHR))}

    weapon = main_weapon or Weapon()
    weapon_skill = weapon.skill
    skill_value = _weapon_skill_value(weapon, skill_values)
    damage_rating = _damage_rating(weapon, skill_value)

    attack = _attack_value(mods, attributes["str"], skill_value, _str_multiplier(weapon))

    defense = 8 + int(attributes["vit"] * 1.5)
    defense += _level_defense_factor(level)
    defense += int(mods.get(mod.DEF, 0))
    defense += _food_percent(defense, mods, mod.FOOD_DEF_PERCENT, mod.FOOD_DEF_CAP)
    defense = max(1, defense + defense * int(mods.get(mod.DEF_PERCENT, 0)) // 100)

    accuracy = _accuracy_value(mods, attributes["dex"], skill_value)

    evasion_skill = int(skill_values.get(EVASION_SKILL, 0))
    if evasion_skill > 200:
        evasion_skill = int(200 + (evasion_skill - 200) * 0.9)
    evasion = evasion_skill + int(mods.get(mod.EVA, 0)) + attributes["agi"] // 2

    parry_skill = int(skill_values.get(PARRY_SKILL, 0))
    guard_skill = int(skill_values.get(GUARD_SKILL, 0))
    shield_skill = int(skill_values.get(SHIELD_SKILL, 0))

    fighter = combat.Fighter(
        level=level, attack=attack, defense=defense, accuracy=accuracy, evasion=evasion,
        strength=attributes["str"], dexterity=attributes["dex"],
        vitality=attributes["vit"], agility=attributes["agi"], is_pc=True,
        weapon_skill=weapon_skill, weapon_dmg=damage_rating,
        weapon_rank=combat.weapon_rank(damage_rating, h2h=weapon.h2h),
        two_handed=weapon.two_handed, h2h=weapon.h2h, mods=dict(mods),
        skill_value=skill_value,
        parry_skill=parry_skill, guard_skill=guard_skill,
        shield_skill=shield_skill, shield_size=int(shield_size))

    dual_wield_percent = int(mods.get(mod.DUAL_WIELD, 0))
    if dual_wield is None:
        # Direct callers with only a modifier dict: treat the modifier as the trait.
        dual_wield = dual_wield_percent > 0
    dual_wield = bool(
        dual_wield and sub_weapon is not None and sub_weapon.one_handed
        and weapon.one_handed and dual_wield_percent > 0)

    sub_fighter = None
    if dual_wield:
        sub_skill_value = _weapon_skill_value(sub_weapon, skill_values)
        sub_damage = _damage_rating(sub_weapon, sub_skill_value)
        sub_attack = _attack_value(
            mods, attributes["str"], sub_skill_value, combat.STR_TO_ATT_OFF_HAND)
        sub_accuracy = _accuracy_value(mods, attributes["dex"], sub_skill_value)
        sub_fighter = combat.Fighter(
            level=level, attack=sub_attack, defense=defense,
            accuracy=sub_accuracy, evasion=evasion,
            strength=attributes["str"], dexterity=attributes["dex"],
            vitality=attributes["vit"], agility=attributes["agi"], is_pc=True,
            weapon_skill=sub_weapon.skill, weapon_dmg=sub_damage,
            weapon_rank=combat.weapon_rank(sub_damage, h2h=sub_weapon.h2h),
            two_handed=False, h2h=sub_weapon.h2h, off_hand=True, mods=dict(mods),
            skill_value=sub_skill_value,
            parry_skill=parry_skill, guard_skill=guard_skill,
            shield_skill=shield_skill, shield_size=0)

    delay = max(1, int(weapon.delay or UNARMED_DELAY))
    if dual_wield:
        # (main + sub) x (1 - Dual Wield%) / 2: both hands swing once per round, so
        # the round interval is the average of the two reduced delays.
        sub_delay = max(1, int(sub_weapon.delay or UNARMED_DELAY))
        reduction = min(100, max(0, dual_wield_percent)) / 100.0
        delay = max(1, int((delay + sub_delay) * (1.0 - reduction) / 2.0))

    return Sheet(
        fighter=fighter, attributes=attributes, base_attributes=base,
        weapon=weapon, delay=delay,
        haste=mod.percent(mods.get(mod.HASTE_GEAR, 0)),
        max_hp=_with_percent(
            base_stats.base_hp(int(char.get("race", 1)), job, level, sub_job, sub_level)
            + int(mods.get(mod.HP, 0)) + int(mods.get(mod.MAX_HP_BOOST, 0))
            + int(mods.get(mod.FOOD_HP, 0)),
            mods.get(mod.HPP, 0), floor=1),
        max_mp=_with_percent(
            base_stats.base_mp(int(char.get("race", 1)), job, level, sub_job, sub_level)
            + int(mods.get(mod.MP, 0)) + int(mods.get(mod.MAX_MP_BOOST, 0))
            + int(mods.get(mod.FOOD_MP, 0)),
            mods.get(mod.MPP, 0), floor=0),
        shield_size=int(shield_size),
        sub_weapon=sub_weapon if dual_wield else None,
        sub_fighter=sub_fighter, dual_wield=dual_wield,
        dual_wield_percent=dual_wield_percent if dual_wield else 0)


# --- monsters -------------------------------------------------------------------------------

# The family rank a monster's stat comes from.  LandSandBoat reads it per family from
# data/ecosystems.yaml; Fanxi has no family data yet, so every monster uses rank A for its
# family contribution and Warrior's job grades, which reproduces the shape of the curve.
_MOB_FAMILY_RANK = 1
_MOB_JOB_GRADES = base_stats.JOB_GRADES["war"]

# Rank letter -> the number mobutils::GetBaseToRank switches on.
_RANK_NUMBER = {"a_plus": 1, "a": 1, "b_plus": 2, "b": 2, "b_minus": 2,
                "c_plus": 3, "c": 3, "c_minus": 3, "d": 4, "e": 5, "f": 6, "g": 7}


def _base_to_rank(rank: int, level: int) -> int:
    """mobutils::GetBaseToRank: what a family or job grade is worth at a level."""
    level = max(1, int(level))
    table = {1: (5, 50), 2: (4, 45), 3: (4, 40), 4: (3, 35),
             5: (3, 30), 6: (2, 25), 7: (2, 20)}
    start, slope = table.get(int(rank), (0, 0))
    return start + ((level - 1) * slope) // 100


def _base_def_eva(rank: int, level: int) -> int:
    """mobutils::GetBaseDefEva: the level curve behind monster Defense and Evasion."""
    level = int(level)
    if level > 50:
        table = {1: (153, 5.0), 2: (147, 4.9), 3: (142, 4.8), 4: (136, 4.7), 5: (126, 4.5)}
        start, slope = table.get(int(rank), (0, 0.0))
        return int(start + (level - 50) * slope)
    table = {1: (6, 3.0), 2: (5, 2.9), 3: (5, 2.8), 4: (4, 2.7), 5: (4, 2.5)}
    start, slope = table.get(int(rank), (0, 0.0))
    return int(start + (level - 1) * slope)


def mob_attributes(level: int) -> dict[str, int]:
    """STR/DEX/VIT/AGI/INT/MND/CHR for a monster, from its level."""
    attributes = {}
    for name in ("str", "dex", "vit", "agi", "int", "mnd", "chr"):
        job_rank = _RANK_NUMBER.get(_MOB_JOB_GRADES[name], 1)
        family = _base_to_rank(_MOB_FAMILY_RANK, level)
        job = _base_to_rank(job_rank, level)
        sub = _base_to_rank(job_rank, level) // 2
        attributes[name] = family + job + sub
    return attributes


def build_monster(level: int, *, mods: dict[int, int] | None = None) -> Sheet:
    """The sheet for a monster.

    Monster Attack and Accuracy are their skill rank at their level, Defense and Evasion
    are ``mobutils::GetBaseDefEva``, and base damage is the level itself -- the curve
    ``mobutils::GetBaseWeaponDamage`` starts from before its per-region offset.
    """
    level = max(1, int(level))
    attributes = mob_attributes(level)
    mods = dict(mods or {})

    skill_value = skills.rank_cap("a_plus", level)
    attack = 8 + int(mods.get(mod.ATT, 0)) + skill_value + attributes["str"] // 2
    accuracy = skill_value + int(mods.get(mod.ACC, 0))

    defense = _base_def_eva(_MOB_FAMILY_RANK, level) + 8 + attributes["vit"] // 2
    defense += int(mods.get(mod.DEF, 0))
    evasion = _base_def_eva(_MOB_FAMILY_RANK, level) + attributes["agi"] // 2
    evasion += int(mods.get(mod.EVA, 0))

    damage_rating = level
    fighter = combat.Fighter(
        level=level, attack=max(1, attack), defense=max(1, defense),
        accuracy=accuracy, evasion=evasion,
        strength=attributes["str"], dexterity=attributes["dex"],
        vitality=attributes["vit"], agility=attributes["agi"], is_pc=False,
        weapon_skill=0, weapon_dmg=damage_rating,
        weapon_rank=combat.weapon_rank(damage_rating), mods=mods,
        skill_value=skill_value)

    return Sheet(fighter=fighter, attributes=attributes, base_attributes=attributes,
                 weapon=Weapon(), delay=UNARMED_DELAY, haste=0.0)
