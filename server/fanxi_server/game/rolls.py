"""Corsair rolls, Double-Up, Fold and Bust.

Every roll has one client status icon, one value from I to XI, and the exact table
BG-wiki publishes for that value.  A table is stored in the units the rest of the
engine reads (percent-integers for Attack/Defense/Fast Cast/Crit, hundredths for
haste, flat points for Accuracy/Evasion/Save TP, and so on), so a roll needs no
translation at the call site.

Retail rules this module keeps:

* a Corsair main may have two rolls up, a Corsair sub job only one;
* Double-Up is available for 45 seconds after the roll that started it;
* a roll over XI busts unless another XI is on the bar (that XI nullifies the Bust
  status) or the Corsair job-point ``Bust Evasion`` roll saves it;
* a bust puts the ``Bust`` status (309) on the player, which blocks new rolls until
  Fold, zoning or death removes it;
* reaching XI resets the Phantom Roll recast.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from . import effects, job_points, modifiers as mod

BUST_EFFECT = effects.BUST
DOUBLE_UP_SECONDS = 45.0
ROLL_DURATION = 300.0          # retail's five-minute base, before merits and gear
MAX_ROLL_DURATION = 660.0      # retail's 11:00 cap
PHANTOM_ROLL_RECAST_ID = 193
WINNING_STREAK = 0x0C04        # group 2 merit: +20 s per rank
BUST_MERIT = 0x0588            # group 1 merit: -10 s of Bust per rank
BUST_DURATION = 300.0
# Commodore/Lanun Tricorne (all reforged stages): +6 s of Winning Streak per merit.
WINNING_STREAK_TRICORNES = frozenset({
    10666, 11468, 11469, 23079, 23414, 23934, 26656, 26657,
})


@dataclass(frozen=True)
class RollSpec:
    key: str
    name: str
    status: int
    #: modifier id -> the exact amount at roll totals 1..11.  A table always has
    #: eleven entries; ``mods`` clamps the total so a hand-written packet cannot
    #: index past it.
    table: tuple[tuple[int, tuple[int, ...]], ...] = ()
    #: ``player`` rolls write the player's combat modifiers.  ``pet`` rolls write the
    #: owner's pet fields (and are re-applied when the pet is called), and ``exp``
    #: rolls are read by the kill reward.
    kind: str = "player"

    @property
    def lucky(self) -> int:
        return int(LUCKY_NUMBERS.get(self.status, (0, 0))[0])

    @property
    def unlucky(self) -> int:
        return int(LUCKY_NUMBERS.get(self.status, (0, 0))[1])

    def mods(self, value: int) -> dict[int, int]:
        total = max(1, min(11, int(value)))
        return {int(modifier): int(values[total - 1]) for modifier, values in self.table}


def _row(*values: int) -> tuple[int, ...]:
    assert len(values) == 11
    return tuple(int(value) for value in values)


# The values below are BG-wiki's Roll Total tables.  Lucky/unlucky numbers are why a
# per-point scale is wrong for almost every roll.
ROLLS: dict[int, RollSpec] = {
    98: RollSpec("fighters", "Fighter's Roll", 310,
                 table=((mod.DOUBLE_ATTACK, _row(1, 2, 3, 4, 10, 5, 6, 6, 1, 7, 15)),)),
    99: RollSpec("monks", "Monk's Roll", 311,
                 table=((mod.SUBTLE_BLOW, _row(8, 10, 32, 12, 14, 16, 4, 20, 22, 24, 40)),)),
    100: RollSpec("healers", "Healer's Roll", 312,
                  table=((mod.CURE_POTENCY_RCVD,
                          _row(3, 4, 12, 5, 6, 7, 1, 8, 9, 10, 16)),)),
    101: RollSpec("wizards", "Wizard's Roll", 313,
                  table=((mod.MATT, _row(4, 6, 8, 10, 25, 12, 14, 17, 2, 20, 30)),)),
    102: RollSpec("warlocks", "Warlock's Roll", 314,
                  table=((mod.MACC, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)),)),
    103: RollSpec("rogues", "Rogue's Roll", 315,
                  table=((mod.CRIT_HIT_RATE,
                          _row(100, 200, 300, 400, 1000, 500, 600, 700, 100, 800, 1400)),)),
    104: RollSpec("gallants", "Gallant's Roll", 316,
                  table=((mod.DEF_PERCENT, _row(5, 6, 20, 7, 9, 10, 3, 12, 14, 16, 23)),)),
    105: RollSpec("chaos", "Chaos Roll", 317,
                  table=((mod.ATT_PERCENT, _row(6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)),
                         (mod.RATT_PERCENT,
                          _row(6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)))),
    106: RollSpec("beasts", "Beast Roll", 318, kind="pet",
                  table=((mod.ATT_PERCENT,
                          _row(6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)),
                         (mod.RATT_PERCENT,
                          _row(6, 8, 9, 25, 11, 12, 16, 3, 17, 19, 31)))),
    107: RollSpec("chorals", "Choral Roll", 319,
                  table=((mod.SPELL_INTERRUPT,
                          _row(-8, -42, -11, -15, -19, -4, -23, -27, -31, -35, -50)),)),
    108: RollSpec("hunters", "Hunter's Roll", 320,
                  table=((mod.ACC, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)),
                         (mod.RACC, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)))),
    109: RollSpec("samurai", "Samurai Roll", 321,
                  table=((mod.STORETP, _row(8, 32, 10, 12, 14, 4, 16, 20, 22, 24, 40)),)),
    110: RollSpec("ninja", "Ninja Roll", 322,
                  table=((mod.EVA, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)),)),
    111: RollSpec("drachens", "Drachen Roll", 323, kind="pet",
                  table=((mod.ACC, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)),
                         (mod.RACC, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)))),
    112: RollSpec("evokers", "Evoker's Roll", 324,
                  table=((mod.REFRESH, _row(1, 1, 1, 1, 3, 2, 2, 2, 1, 3, 4)),)),
    113: RollSpec("maguss", "Magus's Roll", 325,
                  table=((mod.MDEF, _row(5, 20, 6, 8, 9, 3, 10, 13, 14, 15, 25)),)),
    114: RollSpec("corsairs", "Corsair's Roll", 326, kind="exp",
                  table=((mod.EXP_BONUS,
                          _row(10, 11, 11, 12, 20, 13, 15, 16, 8, 17, 24)),
                         (mod.CAPACITY_BONUS,
                          _row(10, 11, 11, 12, 20, 13, 15, 16, 8, 17, 24)))),
    115: RollSpec("puppets", "Puppet Roll", 327, kind="pet",
                  table=((mod.MACC, _row(5, 8, 35, 11, 14, 18, 2, 22, 26, 30, 40)),
                         (mod.MATT, _row(5, 8, 35, 11, 14, 18, 2, 22, 26, 30, 40)))),
    116: RollSpec("dancers", "Dancer's Roll", 328,
                  table=((mod.REGEN, _row(3, 4, 12, 5, 6, 7, 1, 8, 9, 10, 16)),)),
    117: RollSpec("scholars", "Scholar's Roll", 329,
                  table=((mod.CONSERVE_MP, _row(2, 10, 3, 4, 4, 1, 5, 6, 7, 7, 12)),)),
    118: RollSpec("bolters", "Bolter's Roll", 330,
                  table=((mod.MOVE_SPEED_BOLTERS_ROLL,
                          _row(6, 6, 16, 8, 8, 10, 10, 12, 4, 14, 20)),)),
    119: RollSpec("casters", "Caster's Roll", 331,
                  table=((mod.FASTCAST, _row(6, 15, 7, 8, 9, 10, 5, 11, 12, 13, 20)),)),
    120: RollSpec("coursers", "Courser's Roll", 332,
                  table=((mod.SNAPSHOT, _row(2, 3, 11, 4, 5, 6, 7, 8, 1, 10, 12)),)),
    121: RollSpec("blitzers", "Blitzer's Roll", 333,
                  table=((mod.HASTE_ABILITY,
                          _row(200, 300, 400, 1100, 500, 600, 700, 800, 100, 1000, 1200)),)),
    122: RollSpec("tacticians", "Tactician's Roll", 334,
                  table=((mod.REGAIN, _row(10, 10, 10, 10, 30, 10, 10, 0, 20, 20, 40)),)),
    302: RollSpec("allies", "Allies' Roll", 335,
                  table=((mod.SKILLCHAIN_BONUS,
                          _row(2, 3, 20, 5, 7, 9, 11, 13, 15, 1, 25)),)),
    303: RollSpec("misers", "Miser's Roll", 336,
                  table=((mod.SAVETP,
                          _row(30, 50, 70, 90, 200, 110, 20, 130, 150, 170, 250)),)),
    304: RollSpec("companions", "Companion's Roll", 337, kind="pet",
                  table=((mod.REGAIN, _row(20, 50, 20, 20, 30, 30, 30, 40, 40, 10, 60)),
                         (mod.REGEN, _row(4, 20, 6, 8, 10, 12, 14, 16, 18, 3, 25)))),
    305: RollSpec("avengers", "Avenger's Roll", 338,
                  table=((mod.COUNTER, _row(3, 4, 5, 14, 6, 7, 8, 1, 9, 10, 16)),)),
    390: RollSpec("naturalists", "Naturalist's Roll", 339,
                  table=((mod.ENH_MAGIC_DURATION,
                          _row(6, 7, 15, 8, 9, 10, 5, 11, 12, 13, 20)),)),
    391: RollSpec("runeists", "Runeist's Roll", 600,
                  table=((mod.MEVA, _row(10, 13, 15, 40, 18, 20, 25, 5, 28, 30, 50)),)),
}

#: status id -> (lucky number, unlucky number).  The HUD's picker and the chat line
#: both read these so a roll's special totals stay next to its table.
LUCKY_NUMBERS: dict[int, tuple[int, int]] = {
    310: (5, 9), 311: (3, 7), 312: (3, 7), 313: (5, 9), 314: (4, 8),
    315: (5, 9), 316: (3, 7), 317: (4, 8), 318: (4, 8), 319: (2, 6),
    320: (4, 8), 321: (2, 6), 322: (4, 8), 323: (4, 8), 324: (5, 9),
    325: (2, 6), 326: (5, 9), 327: (3, 7), 328: (3, 7), 329: (2, 6),
    330: (3, 9), 331: (2, 7), 332: (3, 9), 333: (4, 9), 334: (5, 8),
    335: (3, 10), 336: (5, 7), 337: (2, 10), 338: (4, 8),
    339: (3, 7), 600: (4, 8),
}

PHANTOM_ROLL = 97
DOUBLE_UP = 123
SNAKE_EYE = 177
FOLD = 178
ROLL_STATUSES = {spec.status for spec in ROLLS.values()}


def spec(ability_id: int) -> RollSpec | None:
    return ROLLS.get(int(ability_id))


def duration(owner_job: int) -> float:
    """One roll's base duration: retail's 5:00 plus 2 s per Phantom Roll Duration rank."""
    return ROLL_DURATION + job_points.category_total(owner_job, "Phantom Roll Duration")


def duration_for(session) -> float:
    """The caster's real roll duration, with merits and Phantom Roll Duration gear.

    Retail adds all of these before the 11:00 cap: 5:00 base, +2 s per Phantom Roll
    Duration job point, +20 s per Winning Streak merit, and every equipped
    ``PHANTOM_DURATION`` row (Chasseur's Gants, Camulus's Mantle, Regal Necklace,
    Commodore's/Lanun Knife, Rostam, ...).
    """
    owner_job = int(session.char.get("main_job", 0) or 0)
    total = duration(owner_job)
    try:
        merits = session.merit_counts()
        streak = int(merits.get(WINNING_STREAK, 0) or 0)
        total += 20.0 * streak
        if streak:
            world = getattr(session, "world", None)
            head = {int(row.get("item_id", 0) or 0)
                    for row in world.service.equipped_slot_mods(int(session.char["id"]))}
            if head & WINNING_STREAK_TRICORNES:
                total += 6.0 * streak
    except Exception:
        pass
    try:
        total += float(session.combat_mods().get(mod.PHANTOM_DURATION, 0) or 0)
    except Exception:
        pass
    return min(MAX_ROLL_DURATION, total)


def value(rng, snake_eye: bool = False) -> int:
    return 11 if snake_eye else int(rng.randint(1, 6))


def outcome(roll: RollSpec, number: int) -> str:
    """The chat suffix for a lucky or unlucky total."""
    if int(number) == roll.lucky:
        return " (Lucky!)"
    if int(number) == roll.unlucky:
        return " (Unlucky!)"
    return ""


def active(session) -> list[RollSpec]:
    return [roll for roll in ROLLS.values() if session.effect(roll.status) is not None]


def owned(session) -> list[RollSpec]:
    """The rolls this session rolled itself, not a Trust's party roll."""
    char_id = int(session.char.get("char_id", 0) or 0)
    out = []
    for roll in ROLLS.values():
        state = session.effect(roll.status)
        if state is None:
            continue
        if int(state.get("roll_owner", char_id) or char_id) == char_id:
            out.append(roll)
    return out


def newest(session) -> RollSpec | None:
    """The roll a Double-Up acts on: the most recently rolled, as retail does."""
    current = owned(session)
    if not current:
        return None
    return max(current, key=lambda roll: float(
        (session.effect(roll.status) or {}).get("rolled_at") or 0.0))


def max_rolls(session) -> int:
    """Two rolls for a Corsair main, one for a Corsair support job."""
    return 2 if int(session.char.get("main_job", 0) or 0) == 17 else 1


def bust_duration(session) -> float:
    """5:00 minus 10 s per rank of the Bust Duration group-1 merit."""
    try:
        ranks = int(session.merit_counts().get(BUST_MERIT, 0))
    except Exception:
        ranks = 0
    return max(30.0, BUST_DURATION - 10.0 * ranks)


def _party_recipients(session) -> list:
    """The caster and party members inside the roll's 7.9-yalm radius."""
    out = [session]
    world = getattr(session, "world", None)
    if world is None:
        return out
    try:
        for other in world._trust_party_sessions(session):
            if other is None or other is session:
                continue
            # A ZoneSession has no distance_to(); compare the two positions directly.
            # The old call raised AttributeError and the except returned only the caster,
            # which is why party members never received the roll.
            try:
                dx = float(other.pos[0]) - float(session.pos[0])
                dz = float(other.pos[2]) - float(session.pos[2])
            except (IndexError, TypeError, ValueError):
                dx = dz = 0.0
            if math.hypot(dx, dz) > 8.5:
                continue
            out.append(other)
    except Exception:
        pass
    return out


def _queue_party_buffs(session) -> None:
    """Tell the party's clients which icons the other members now hold."""
    world = getattr(session, "world", None)
    try:
        if world is not None and hasattr(world, "queue_party_buffs"):
            world.queue_party_buffs(session)
    except Exception:
        pass


def _tick_value(mods: dict[int, int]) -> int:
    """Refresh, Regen and Regain tick for the effect row; 0 for every other roll."""
    return max(0, int(mods.get(mod.REFRESH, 0) or 0),
               int(mods.get(mod.REGEN, 0) or 0),
               int(mods.get(mod.REGAIN, 0) or 0))


def _refresh_pet(session) -> None:
    """Recompute a pet's roll fields from every pet roll the owner still has up."""
    pet = getattr(session, "pet_entity", None)
    if pet is None:
        return
    totals: dict[int, int] = {}
    statuses = []
    for status, mods in dict(getattr(session, "roll_pet_mods", {}) or {}).items():
        statuses.append(int(status))
        for mod_id, value in (mods or {}).items():
            totals[int(mod_id)] = totals.get(int(mod_id), 0) + int(value)
    pet.roll_accuracy = int(totals.get(mod.ACC, 0))
    pet.roll_ranged_accuracy = int(totals.get(mod.RACC, 0))
    pet.roll_attack_pct = int(totals.get(mod.ATT_PERCENT, 0))
    pet.roll_ranged_attack_pct = int(totals.get(mod.RATT_PERCENT, 0))
    pet.roll_macc = int(totals.get(mod.MACC, 0))
    pet.roll_matt = int(totals.get(mod.MATT, 0))
    pet.roll_regain = int(totals.get(mod.REGAIN, 0))
    pet.roll_regen = int(totals.get(mod.REGEN, 0))
    pet.roll_regain_status = statuses[-1] if statuses else 0


def _apply_pet(session, roll: RollSpec, number: int) -> None:
    """Remember a pet roll and put it on the current pet, if one is out."""
    try:
        store = session.__dict__.setdefault("roll_pet_mods", {})
        store[int(roll.status)] = roll.mods(number)
    except Exception:
        pass
    pet = getattr(session, "pet_entity", None)
    if pet is not None and getattr(pet, "alive", True):
        _refresh_pet(session)


def _clear_pet(session, status: int) -> None:
    try:
        session.roll_pet_mods.pop(int(status), None)
    except Exception:
        pass
    _refresh_pet(session)


def _roll_owner(session, roll: RollSpec) -> int:
    state = session.effect(roll.status) or {}
    fallback = int(session.char.get("char_id", 0) or 0)
    return int(state.get("roll_owner", fallback) or fallback)


def _drop_oldest(session, keep: int, owner: int, cap: int) -> RollSpec | None:
    """Remove the oldest of one caster's rolls when a new one would exceed the cap."""
    current = [roll for roll in active(session)
               if int(roll.status) != int(keep) and _roll_owner(session, roll) == owner]
    if len([roll for roll in active(session)
            if _roll_owner(session, roll) == owner]) < cap:
        return None
    if not current:
        return None
    oldest = min(current, key=lambda roll: float(
        (session.effect(roll.status) or {}).get("rolled_at") or 0.0))
    session.remove_effect(oldest.status, quiet=True)
    _clear_pet(session, oldest.status)
    session.say("%s wears off." % oldest.name)
    return oldest


def _set_roll_value(member, roll: RollSpec, number: int) -> None:
    """Write a new total on one party member's copy and refresh their client."""
    state = member.effect(roll.status)
    if state is None:
        return
    mods = roll.mods(number)
    state["power"] = int(number)
    state["mods"] = mods
    state["roll_value"] = int(number)
    state["regain"] = int(mods.get(mod.REGAIN, 0) or 0)
    state["tick"] = _tick_value(mods)
    if roll.kind == "pet":
        _apply_pet(member, roll, number)
    member.queue += [member.char_status(), member.char_stats(), member.party_member()]


def _queue_action(session, ability_id: int, animation: int, info: int,
                  *, value: int | None = None, bust: bool = False,
                  double_up: bool = False, message: int | None = None) -> None:
    """Hand the 0x028 the zone must send back to ``job_ability``.

    The result's 17-bit value is what the client prints as the dice number: the roll
    total for a new roll and the *increase* for Double-Up (LSB's ``action:info``).
    A bust uses animation 98 so the client plays the bust shape.
    """
    if message is None:
        message = 426 if bust else (424 if double_up else 420)
    session.roll_action = {
        "ability_id": int(ability_id),
        "animation": 98 if bust else int(animation),
        # The client prints the 17-bit result value in the roll message ("The total
        # comes to ...") and uses the 5-bit info for the dice number.
        "info": max(0, min(31, int(info))),
        "value": max(0, int(info if value is None else value)),
        "message": int(message),
    }


def _remove_roll_from_party(session, roll: RollSpec) -> None:
    """Take one caster's copy of a roll off every party member who has it."""
    owner = int(session.char["char_id"])
    for member in _party_recipients(session):
        state = member.effect(roll.status)
        if state is None or _roll_owner(member, roll) != owner:
            continue
        member.remove_effect(roll.status, quiet=True)
        _clear_pet(member, roll.status)
        member.queue += [member.char_status(), member.char_stats(),
                         member.party_member()]
        if member is not session:
            member.say("You lose the effect of %s." % roll.name)
    _queue_party_buffs(session)


def _bust(session, roll: RollSpec, now: float) -> None:
    _remove_roll_from_party(session, roll)
    session.add_effect(BUST_EFFECT, duration=bust_duration(session), power=1,
                       icon=effects.BUST)
    session.queue += [session.char_status(), session.char_stats(), session.party_member()]
    session.say("%s busts!" % roll.name)


def apply(session, ability_id: int, rng, now: float, animation: int = 0) -> bool:
    roll = ROLLS.get(int(ability_id))
    if roll is None:
        return False
    if session.effect(BUST_EFFECT) is not None:
        session.say("You cannot roll while busted.")
        return False
    snake_eye = bool(getattr(session, "snake_eye", False))
    number = value(rng, snake_eye)
    if snake_eye:
        session.snake_eye = False
    if getattr(session, "crooked_cards", False):
        number = min(11, number + 1)
        session.crooked_cards = False
    mods = roll.mods(number)
    duration_seconds = duration_for(session)
    owner = int(session.char["char_id"])
    cap = max_rolls(session)
    for member in _party_recipients(session):
        # A re-roll replaces the number; the old add_effect path merged with max() and
        # kept a higher previous value, which made a low re-roll look like a no-op.
        member.remove_effect(roll.status, quiet=True)
        _drop_oldest(member, roll.status, owner, cap)
        member.add_effect(roll.status, duration=duration_seconds, power=number,
                          mods=mods, tick=_tick_value(mods))
        state = member.effect(roll.status)
        if state is not None:
            state["rolled_at"] = float(now)
            state["double_up_until"] = float(now) + DOUBLE_UP_SECONDS
            state["roll_value"] = int(number)
            state["roll_owner"] = int(owner)
            state["regain"] = int(mods.get(mod.REGAIN, 0) or 0)
        if roll.kind == "pet":
            _apply_pet(member, roll, number)
        member.queue += [member.char_status(), member.char_stats(), member.party_member()]
        if member is not session:
            member.say("You receive the effect of %s." % roll.name)
    _queue_party_buffs(session)
    _queue_action(session, ability_id, animation, number, value=number,
                  message=420)
    session.say("%s: %d%s" % (roll.name, number, outcome(roll, number)))
    if number >= 11:
        # An XI gives the Corsair something back immediately: Phantom Roll is ready
        # again.  The bust immunity belongs to the XI while it stays on the bar; the
        # next Double-Up consumes it (see double_up).
        try:
            session.ability_recasts.pop(PHANTOM_ROLL_RECAST_ID, None)
        except Exception:
            pass
        session.say("XI! Phantom Roll is ready again.")
    return True


def double_up(session, rng, now: float | None = None, animation: int = 0,
              ability_id: int = 0) -> bool:
    current = owned(session)
    if not current:
        session.say("You have no active roll to double up.")
        return False
    roll = newest(session)
    if roll is None:
        return False
    state = session.effect(roll.status)
    now = time.time() if now is None else float(now)
    until = float(state.get("double_up_until") or 0.0)
    if until <= 0.0 or now > until:
        session.say("Too much time has passed to double up.")
        return False
    previous = int(state.get("power") or 0)
    # Snake Eye is the next roll *or* Double-Up, not just the next fresh roll.  Consume
    # it here too; otherwise a Snake Eye spent on Double-Up stayed set and the following
    # Phantom Roll was forced to 11 as well.
    snake_eye = bool(getattr(session, "snake_eye", False))
    if snake_eye:
        session.snake_eye = False
    # Double-Up adds another die roll (1-6), not a flat +1.  The client prints the
    # increase in the action result's value; the roll total itself is in the chat line.
    delta = int(rng.randint(1, 6))
    number = previous + delta
    if snake_eye:
        number = 11
        delta = number - previous
    if number > 11:
        # A *different* XI on the bar makes the player immune to the Bust status.  The
        # roll being doubled still leaves the bar, so Double-Up cannot be repeated on an
        # XI forever; the XI itself is what protects the next roll.
        other_eleven = any(
            int(item.status) != int(roll.status)
            and int((session.effect(item.status) or {}).get("power") or 0) >= 11
            for item in current)
        if other_eleven:
            _remove_roll_from_party(session, roll)
            _queue_action(session, ability_id, animation, number - previous,
                          value=number, bust=True, message=426)
            session.say("Your XI roll nullifies the bust; %s wears off." % roll.name)
            return True
        evasion = job_points.category_total(17, "Bust Evasion")
        if int(rng.randint(1, 100)) <= evasion:
            number = 11
            delta = number - previous
            session.say("Bust Evasion keeps the roll alive.")
        else:
            _bust(session, roll, now)
            _queue_action(session, ability_id, animation, number - previous,
                          value=number, bust=True, message=426)
            return True
    for member in _party_recipients(session):
        state = member.effect(roll.status)
        if state is not None and _roll_owner(member, roll) == int(
                session.char["char_id"]):
            _set_roll_value(member, roll, number)
            if member is not session:
                member.say("The total for %s increases to %d!" % (roll.name, number))
    _queue_party_buffs(session)
    _queue_action(session, ability_id, animation, delta, value=number,
                  double_up=True, message=424)
    session.say("%s: %d%s" % (roll.name, number, outcome(roll, number)))
    if number >= 11:
        try:
            session.ability_recasts.pop(PHANTOM_ROLL_RECAST_ID, None)
        except Exception:
            pass
    return True


def fold(session) -> bool:
    current = owned(session)
    if not current and session.effect(BUST_EFFECT) is None:
        session.say("You have no roll to fold.")
        return False
    for roll in current:
        _remove_roll_from_party(session, roll)
    _queue_party_buffs(session)
    session.remove_effect(BUST_EFFECT, quiet=True)
    session.queue += [session.char_status(), session.char_stats(), session.party_member()]
    session.say("You fold your roll.")
    return True
