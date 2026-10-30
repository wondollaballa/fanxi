"""Monster TP moves: the data row, its TP costs and the status it lands.

LandSandBoat keeps one row per monster ability in ``sql/mob_skills.sql`` and the
family lists in ``sql/mob_skill_lists.sql``.  Migration 0148 imports both, and
``monster_templates.skill_list_id`` joins a spawn to its list.  This module holds
the pure parts -- the row shape, TP thresholds and the name-to-status map -- while
``world.py`` owns the packets, target selection and damage.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import effects

# TARGETTYPE bits (LandSandBoat's entities/battle_entity.h).
TARGET_SELF = 0x0001
TARGET_PARTY = 0x0002
TARGET_ENEMY = 0x0004
TARGET_PLAYER = 0x0010
TARGET_NPC = 0x0040

# SKILLFLAG bits.  Astral Flow and Blood Pacts belong to pets, not to a normal
# monster's own TP bar, so the world skips them.
SKILLFLAG_ASTRAL_FLOW = 2
SKILLFLAG_NO_TP_COST = 4
SKILLFLAG_BLOODPACT_RAGE = 64
SKILLFLAG_BLOODPACT_WARD = 128
SKILLFLAG_ALWAYS_ANIMATE = 256

# AOE values: 1 is centred on the monster, 2 on the primary target, 4/8 are cones.
AOE_ATTACKER = 1
AOE_TARGET = 2
AOE_CONE = 4
AOE_CONE_TARGET = 8

# A monster uses a TP move at 1000-3000 TP; 3000 always fires, and retail also fires
# below 25% HP once the bar reaches 1000.
TP_MIN = 1000
TP_MAX = 3000
TP_LOW_HP = 25


@dataclass(frozen=True)
class MobSkill:
    id: int
    name: str
    animation: int
    aoe: int
    aoe_radius: float
    distance: float
    animation_time: int
    prepare_time: int
    valid_targets: int
    flag: int
    param: int
    knockback: int = 0
    primary_sc: int = 0
    secondary_sc: int = 0
    tertiary_sc: int = 0

    @property
    def is_enemy_target(self) -> bool:
        return bool(self.valid_targets & TARGET_ENEMY)

    @property
    def is_self_target(self) -> bool:
        return bool(self.valid_targets & TARGET_SELF) or not self.is_enemy_target

    @property
    def is_aoe(self) -> bool:
        return self.aoe in (AOE_ATTACKER, AOE_TARGET)

    @property
    def is_conal(self) -> bool:
        return self.aoe in (AOE_CONE, AOE_CONE_TARGET)

    @property
    def is_tp_free(self) -> bool:
        return bool(self.flag & SKILLFLAG_NO_TP_COST)

    @property
    def is_pet_only(self) -> bool:
        return bool(self.flag & (SKILLFLAG_ASTRAL_FLOW | SKILLFLAG_BLOODPACT_RAGE
                                 | SKILLFLAG_BLOODPACT_WARD))

    @property
    def always_animates(self) -> bool:
        return bool(self.flag & SKILLFLAG_ALWAYS_ANIMATE)

    def in_range(self, distance: float) -> bool:
        if self.aoe == AOE_ATTACKER or not self.is_enemy_target:
            return True
        return float(distance) <= max(0.0, float(self.distance))


def from_row(row: dict) -> MobSkill:
    return MobSkill(
        id=int(row["id"]),
        name=str(row["name"] or ""),
        animation=int(row["animation"] or 0),
        aoe=int(row["aoe"] or 0),
        aoe_radius=float(row["aoe_radius"] or 0.0),
        distance=float(row["distance"] or 0.0),
        animation_time=int(row["animation_time"] or 2000),
        prepare_time=int(row["prepare_time"] or 0),
        valid_targets=int(row["valid_targets"] or 0),
        flag=int(row["flag"] or 0),
        param=int(row["param"] or 0),
        knockback=int(row["knockback"] or 0),
        primary_sc=int(row["primary_sc"] or 0),
        secondary_sc=int(row["secondary_sc"] or 0),
        tertiary_sc=int(row["tertiary_sc"] or 0),
    )


def next_threshold(rng) -> int:
    """The TP value at which this monster decides to use its next move."""
    return int(rng.randint(TP_MIN, TP_MAX))


def should_use(tp: int, threshold: int, hp_percent: int) -> bool:
    """Whether a monster's bar is ready for a TP move.

    Retail checks 3000 first, then the low-HP emergency band, then the random
    threshold the controller picked after the previous move.
    """
    tp = max(0, int(tp))
    if tp < TP_MIN:
        return False
    if tp >= TP_MAX or int(hp_percent) < TP_LOW_HP:
        return True
    return tp >= max(TP_MIN, int(threshold))


def usable(skills: list[MobSkill], distance: float) -> list[MobSkill]:
    """The list entries usable at this distance (pet-only moves are dropped)."""
    return [skill for skill in skills
            if not skill.is_pet_only and skill.in_range(distance)]


def damage_ftp(skill: MobSkill) -> float:
    """A generic fTP for a TP move, from its shape and name.

    LandSandBoat's scripts each roll their own damage; Fanxi does not port 2,700
    scripts, so a TP move is a heavier swing than an auto-attack.  AoE moves pay a
    little less per target, and "rush"/"volley"-style multi-hit names pay more.
    """
    name = skill.name.lower()
    if not skill.is_enemy_target:
        return 0.0
    ftp = 2.0
    if skill.is_aoe or skill.is_conal:
        ftp = 1.5
    if any(word in name for word in ("rush", "volley", "barrage", "combo", "fists",
                                     "flurry", "salvo", "burst")):
        ftp = max(ftp, 2.5)
    elif "breath" in name:
        ftp = 1.75
    return ftp


# The status a TP move lands, when its name says so.  Retail's scripts use the same
# handful of effects repeatedly; the server applies them with a duration and potency
# that match the spell family rather than the exact script.
_STATUS_RULES: tuple[tuple[tuple[str, ...], int, float, int], ...] = (
    (("sleep", "lullaby", "soporific", "slumber", "dream", "yawn"), effects.SLEEP, 30.0, 0),
    (("petrif", "breakga", "break gaze"), effects.PETRIFICATION, 30.0, 0),
    (("paraly", "paralysis", "curare"), effects.PARALYSIS, 60.0, 20),
    (("stun", "shock", "thunder"), effects.STUN, 3.0, 0),
    (("silence", "mute"), effects.SILENCE, 60.0, 0),
    (("blind", "flash"), effects.BLINDNESS, 60.0, 20),
    (("poison", "venom", "toxin"), effects.POISON, 60.0, 10),
    (("disease", "blight"), effects.DISEASE, 60.0, 0),
    (("plague", "pestilence"), effects.PLAGUE, 60.0, 0),
    (("bind", "entangle", "root"), effects.BIND, 30.0, 0),
    (("weight", "gravity"), effects.WEIGHT, 60.0, 25),
    (("slow", "torpor"), effects.SLOW, 60.0, 20),
    (("defense down", "armor break", "shell break", "frightful roar", "howl",
      "war cry", "demoralize"), effects.DEFENSE_DOWN, 60.0, 20),
    (("attack down", "power break", "meltdown"), effects.ATTACK_DOWN, 60.0, 20),
    (("evasion down", "shadow break"), effects.EVASION_DOWN, 60.0, 20),
    (("accuracy down", "gloom", "blind"), effects.ACCURACY_DOWN, 60.0, 20),
    (("magic def down", "magic defense down"), effects.MAGIC_DEF_DOWN, 60.0, 20),
    (("magic atk down", "magic attack down"), effects.MAGIC_ATK_DOWN, 60.0, 20),
    (("magic evasion down", "meva down"), effects.MAGIC_EVASION_DOWN, 60.0, 20),
)


def status_effect(skill: MobSkill) -> tuple[int, float, int] | None:
    """(effect id, duration, potency) for a TP move's enfeeble, or None."""
    name = skill.name.lower().replace("_", " ")
    for words, effect_id, duration, potency in _STATUS_RULES:
        if any(word in name for word in words):
            return int(effect_id), float(duration), int(potency)
    return None


# TP moves that clearly restore the monster rather than hurt a player.
_SELF_HEAL = ("cure", "heal", "regen", "drain", "aspir", "absorb")
_SELF_BUFF = ("haste", "protect", "shell", "stoneskin", "blink", "cocoon",
              "metallic body", "bubble", "guard", "stance", "mighty", "familiar")


def self_effect(skill: MobSkill) -> tuple[str, int, int] | None:
    """('heal'|'buff', effect id, amount) for a self-target TP move, or None.

    A monster's own buffs are icons only: the engine has no mob stat sheet for a
    temporary modifier, and the client draws the animation/status from the action.
    """
    name = skill.name.lower().replace("_", " ")
    if any(word in name for word in _SELF_HEAL):
        return "heal", 0, 300
    if any(word in name for word in _SELF_BUFF):
        effect = effects.HASTE if "haste" in name else effects.PROTECT
        return "buff", int(effect), 60
    return None
