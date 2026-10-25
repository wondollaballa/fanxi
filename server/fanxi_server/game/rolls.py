"""Corsair rolls: one status icon and one set of modifiers per roll value."""
from __future__ import annotations

from dataclasses import dataclass

from . import effects, job_points, modifiers as mod


@dataclass(frozen=True)
class RollSpec:
    key: str
    name: str
    status: int
    # modifier id -> points per roll value
    per_point: tuple[tuple[int, int], ...]

    def mods(self, value: int) -> dict[int, int]:
        out: dict[int, int] = {}
        for mod_id, scale in self.per_point:
            out[int(mod_id)] = int(value) * int(scale)
        return out


ROLLS: dict[int, RollSpec] = {
    98: RollSpec("fighters", "Fighter's Roll", 310, ((mod.DOUBLE_ATTACK, 1),)),
    99: RollSpec("monks", "Monk's Roll", 311, ((mod.HP, 10),)),
    100: RollSpec("healers", "Healer's Roll", 312, ((mod.CURE_POTENCY, 1),)),
    101: RollSpec("wizards", "Wizard's Roll", 313, ((mod.MATT, 2),)),
    102: RollSpec("warlocks", "Warlock's Roll", 314, ((mod.MACC, 2),)),
    103: RollSpec("rogues", "Rogue's Roll", 315, ((mod.CRIT_HIT_RATE, 100),)),
    104: RollSpec("gallants", "Gallant's Roll", 316, ((mod.DEF, 2),)),
    105: RollSpec("chaos", "Chaos Roll", 317, ((mod.ATT, 3),)),
    108: RollSpec("hunters", "Hunter's Roll", 320, ((mod.RACC, 2),)),
    109: RollSpec("samurai", "Samurai Roll", 321, ((mod.STORETP, 1),)),
    110: RollSpec("ninja", "Ninja Roll", 322, ((mod.EVA, 2),)),
    113: RollSpec("maguss", "Magus's Roll", 325, ((mod.MATT, 2),)),
    118: RollSpec("bolters", "Bolter's Roll", 330, ((mod.RACC, 2),)),
    119: RollSpec("casters", "Caster's Roll", 331, ((mod.MACC, 2),)),
}

PHANTOM_ROLL = 97
DOUBLE_UP = 123
SNAKE_EYE = 177
FOLD = 178
ROLL_STATUSES = {spec.status for spec in ROLLS.values()}


def spec(ability_id: int) -> RollSpec | None:
    return ROLLS.get(int(ability_id))


def duration(owner_job: int) -> float:
    """One roll's duration; the COR job-point row adds two seconds per rank."""
    return 60.0 + job_points.category_total(owner_job, "Phantom Roll Duration")


def value(rng, snake_eye: bool = False) -> int:
    return 11 if snake_eye else int(rng.randint(1, 6))


def apply(session, ability_id: int, rng, now: float) -> bool:
    spec = ROLLS.get(int(ability_id))
    if spec is None:
        return False
    snake_eye = bool(getattr(session, "snake_eye", False))
    number = value(rng, snake_eye)
    if snake_eye:
        session.snake_eye = False
    session.add_effect(spec.status, duration=duration(session.char.get("main_job", 0)),
                       power=number, mods=spec.mods(number))
    session.say("%s: %d" % (spec.name, number))
    return True


def active(session) -> list[RollSpec]:
    return [spec for spec in ROLLS.values() if session.effect(spec.status) is not None]


def double_up(session, rng) -> bool:
    current = active(session)
    if not current:
        session.say("You have no active roll to double up.")
        return False
    spec = current[0]
    state = session.effect(spec.status)
    number = int(state.get("power") or 0) + 1
    if number > 11:
        evasion = job_points.category_total(17, "Bust Evasion")
        if int(rng.randint(1, 100)) <= evasion:
            number = 11
            session.say("Bust Evasion keeps the roll alive.")
        else:
            session.remove_effect(spec.status, quiet=True)
            session.say("%s busts!" % spec.name)
            return True
    state["power"] = number
    state["mods"] = spec.mods(number)
    session.queue += [session.char_status(), session.char_stats(), session.party_member()]
    session.say("%s: %d" % (spec.name, number))
    return True


def fold(session) -> bool:
    current = active(session)
    if not current:
        session.say("You have no roll to fold.")
        return False
    for spec in current:
        session.remove_effect(spec.status, quiet=True)
    session.queue += [session.char_status(), session.char_stats(), session.party_member()]
    session.say("You fold your roll.")
    return True
