"""The character state that survives a dropped link: buffs, food and ability recasts.

Retail keeps all three on the server.  A client that loses its connection and signs back
in gets the same song list ticking down and the same job abilities still on cooldown; only
a deliberate logout takes the buffs with it (the cooldowns survive that too).  Fanxi builds
a fresh ``ZoneSession`` for every fresh login, so the session exports this state to
``char_live_state`` while it is in the world and on the way out, and the next login imports
it.

Every time here is an absolute Unix timestamp.  The minutes spent offline therefore count
against an effect instead of pausing it, which is what retail does: a song that had a
minute left when the link dropped has a minute left when the client is back (and none if
the player was away longer than that).  Effects whose time ran out while the client was
gone are pruned on the way in, and the food's ``Food`` icon is reconciled with the food
modifiers so the bar and the stat sheet cannot disagree.

The payload is JSON with one entry per effect, ordered exactly like ``status_effects``
because that order is the icon bar the client draws.  ``trust_source`` effects are left
out: an alter ego does not survive the relog that released it, so neither does its aura.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import effects

#: Bumped only if the payload's shape changes in a way older rows cannot be read under.
SNAPSHOT_VERSION = 1

#: The run of ``effect_state`` a snapshot entry carries.  ``next_tick`` is deliberately
#: not one of them: it is scheduling, not the effect, and it restarts on login anyway.
_STATE_FIELDS = ("until", "power", "potency", "tick", "icon", "mods")


def empty_food() -> dict:
    """The "nothing eaten" food row the session starts with."""
    return {"item_id": 0, "name": "", "until": 0.0, "mods": {}}


@dataclass
class Restored:
    """What a login gets back; the zone session copies it over its own state."""

    status_effects: list[int] = field(default_factory=list)
    effect_state: dict[int, dict] = field(default_factory=dict)
    food: dict = field(default_factory=empty_food)
    recasts: dict[int, float] = field(default_factory=dict)

    @property
    def effect_count(self) -> int:
        return len(self.status_effects)

    @property
    def song_count(self) -> int:
        return sum(1 for effect_id in self.status_effects
                   if self.effect_state.get(effect_id, {}).get("song"))

    def next_expiry(self) -> tuple[int, float] | None:
        """The effect id that wears off first and its ready time.

        The caller names it: the zone already has the status-id labels
        (``stat_report.effect_label``), and a song carries its own name.
        """
        soonest: tuple[int, float] | None = None
        for effect_id in self.status_effects:
            state = self.effect_state.get(effect_id) or {}
            until = float(state.get("until") or 0.0)
            if until <= 0.0:
                continue
            if soonest is None or until < soonest[1]:
                soonest = (int(effect_id), until)
        return soonest


# --- export ---------------------------------------------------------------------------------

def _persistent(state: dict) -> bool:
    """Whether one effect belongs in the snapshot.

    A Trust's aura is keyed to the entity that put it up, and that entity is released on
    logout like any other alter ego; restoring the aura would leave a buff with no source.
    """
    return not state.get("trust_source")


def _entry(effect_id: int, state: dict, now: float) -> dict | None:
    until = float(state.get("until") or 0.0)
    if until and until <= now:
        return None
    if not _persistent(state):
        return None
    entry: dict = {"id": int(effect_id)}
    for key in _STATE_FIELDS:
        if key == "mods":
            entry["mods"] = {str(int(mod_id)): int(mod_value)
                             for mod_id, mod_value in dict(state.get("mods") or {}).items()}
        elif key == "until":
            entry["until"] = until
        else:
            entry[key] = int(state.get(key) or 0)
    if state.get("song"):
        entry["song"] = True
        entry["song_base"] = float(state.get("song_base") or 0.0)
        entry["song_name"] = str(state.get("song_name") or "")
        entry["song_cast_at"] = float(state.get("song_cast_at") or 0.0)
        entry["song_effect"] = int(state.get("song_effect") or 0)
    if state.get("rolled_at"):
        # Keep the 45-second Double-Up window and the caster's ownership across a
        # reconnect; without these a restored roll would be double-uppable forever.
        entry["rolled_at"] = float(state.get("rolled_at") or 0.0)
        entry["double_up_until"] = float(state.get("double_up_until") or 0.0)
        entry["roll_owner"] = int(state.get("roll_owner") or 0)
    return entry


def snapshot(effect_state: dict[int, dict], status_effects: list[int], food: dict | None,
             recasts: dict[int, float], now: float) -> dict:
    """The JSON payload for ``char_live_state``.

    Expired effects and expired food are left out, so a save that lands before the next
    expiry tick cannot put a dead timer in the row.  Recasts keep only the ids whose
    ready time is still in the future; a spent cooldown is not worth a row.
    """
    effects_out: list[dict] = []
    seen: set[int] = set()
    for effect_id in status_effects:
        effect_id = int(effect_id)
        if effect_id in seen:
            continue
        state = effect_state.get(effect_id)
        if state is None:
            continue
        entry = _entry(effect_id, state, now)
        if entry is not None:
            effects_out.append(entry)
            seen.add(effect_id)
    # A state the icon list forgot must still keep its timer: losing a buff because of a
    # book-keeping slip is worse than one icon appearing in a different slot.
    for effect_id in sorted(effect_state):
        if int(effect_id) in seen:
            continue
        entry = _entry(int(effect_id), effect_state[int(effect_id)], now)
        if entry is not None:
            effects_out.append(entry)
            seen.add(int(effect_id))
    saved_food = empty_food()
    if food and float(food.get("until") or 0.0) > now:
        saved_food = {
            "item_id": int(food.get("item_id") or 0),
            "name": str(food.get("name") or ""),
            "until": float(food.get("until") or 0.0),
            "mods": {str(int(mod_id)): int(value)
                     for mod_id, value in dict(food.get("mods") or {}).items()},
        }
    return {
        "version": SNAPSHOT_VERSION,
        "effects": effects_out,
        "food": saved_food,
        "recasts": {str(int(recast_id)): float(ready_at)
                    for recast_id, ready_at in recasts.items()
                    if float(ready_at) > now},
    }


def signature(payload: dict) -> str:
    """A stable string for the "did anything change?" comparison the tick makes.

    ``sort_keys`` makes the dict order irrelevant; the effects list keeps its own order on
    purpose, because that order is the client's icon bar.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# --- import ---------------------------------------------------------------------------------

def _food(food, now: float) -> dict:
    if not isinstance(food, dict):
        return empty_food()
    try:
        until = float(food.get("until") or 0.0)
        if until <= now:
            return empty_food()
        mods = {int(mod_id): int(value)
                for mod_id, value in dict(food.get("mods") or {}).items()}
        return {"item_id": int(food.get("item_id") or 0),
                "name": str(food.get("name") or ""), "until": until, "mods": mods}
    except (TypeError, ValueError, AttributeError):
        return empty_food()


def _mods(raw) -> dict[int, int]:
    try:
        return {int(mod_id): int(value) for mod_id, value in dict(raw or {}).items()}
    except (TypeError, ValueError, AttributeError):
        return {}


def _restore_entry(raw, now: float) -> tuple[int, dict] | None:
    if not isinstance(raw, dict):
        return None
    try:
        effect_id = int(raw.get("id") or 0)
        until = float(raw.get("until") or 0.0)
        if effect_id <= 0 or (until and until <= now):
            return None
        state = {
            "until": until,
            "power": int(raw.get("power") or 0),
            "potency": int(raw.get("potency") or 0),
            "tick": int(raw.get("tick") or 0),
            "icon": int(raw.get("icon") or 0),
            "mods": _mods(raw.get("mods")),
            # The three-second timer restarts; nothing ticks while the client is away.
            "next_tick": now + 3.0,
        }
        if raw.get("song"):
            state.update({
                "song": True,
                "song_base": float(raw.get("song_base") or 0.0),
                "song_name": str(raw.get("song_name") or ""),
                "song_cast_at": float(raw.get("song_cast_at") or 0.0),
                "song_effect": int(raw.get("song_effect") or 0),
            })
        if raw.get("rolled_at"):
            state["rolled_at"] = float(raw.get("rolled_at") or 0.0)
            state["double_up_until"] = float(raw.get("double_up_until") or 0.0)
            state["roll_owner"] = int(raw.get("roll_owner") or 0)
    except (TypeError, ValueError):
        return None
    return effect_id, state


def restore(row: dict | None, now: float) -> Restored:
    """Turn a ``char_live_state`` row into the session's effect and recast state.

    A malformed entry is skipped rather than poisoning the whole login: the row is a
    cache of a running session, and one bad number must not cost the player every buff.
    """
    restored = Restored()
    if not isinstance(row, dict):
        return restored
    version = row.get("version")
    if isinstance(version, int) and version > SNAPSHOT_VERSION:
        # A newer server wrote a shape this build does not know; keeping the abilities
        # (whose block has not changed) is better than replaying a misread effect list.
        return _restore_recasts(restored, row.get("recasts"), now)
    entries = row.get("effects")
    if isinstance(entries, list):
        for raw in entries:
            parsed = _restore_entry(raw, now)
            if parsed is None:
                continue
            effect_id, state = parsed
            if effect_id in restored.effect_state:
                continue
            restored.status_effects.append(effect_id)
            restored.effect_state[effect_id] = state
    restored.food = _food(row.get("food"), now)
    _reconcile_food(restored, now)
    return _restore_recasts(restored, row.get("recasts"), now)


def _restore_recasts(restored: Restored, recasts, now: float) -> Restored:
    if isinstance(recasts, dict):
        for recast_id, ready_at in recasts.items():
            try:
                key = int(recast_id)
                ready = float(ready_at)
            except (TypeError, ValueError):
                continue
            # Key 0 is the shared two-hour ("Special") recast, not a missing id.
            if key >= 0 and ready > now:
                restored.recasts[key] = ready
    return restored


def _reconcile_food(restored: Restored, now: float) -> None:
    """Keep the Food icon and the food modifiers in step.

    They are stored apart (the icon is an effect, the modifiers are the session's
    ``food`` dict), so one can outlive the other after a partial save or an older row.
    The modifiers are the thing that matters: no food means no icon.
    """
    food_until = float(restored.food.get("until") or 0.0)
    has_icon = effects.FOOD in restored.effect_state
    if food_until > now and not has_icon:
        restored.status_effects.append(effects.FOOD)
        restored.effect_state[effects.FOOD] = {
            "until": food_until, "power": 0, "potency": 0, "tick": 0,
            "icon": effects.FOOD, "mods": {}, "next_tick": now + 3.0,
        }
    elif food_until <= now and has_icon:
        restored.effect_state.pop(effects.FOOD, None)
        try:
            restored.status_effects.remove(effects.FOOD)
        except ValueError:
            pass
