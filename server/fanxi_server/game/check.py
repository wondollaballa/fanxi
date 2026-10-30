"""The /check answer for a monster: which line the client prints and what it says.

``C2S 0x00DD`` (``GP_CLI_COMMAND_EQUIP_INSPECT``) with Kind 0 is ``/check``.  The
client owns the text: for a monster it prints a BtlMess line from its own dialog
table, message 174 being "The <mob> seems <difficulty>.", and messages 170..178 add a
second sentence about Defense and Evasion.  The server only picks one of those nine
messages and passes the monster's level in ``Data`` and ``64 + difficulty`` in
``Data2``.

The difficulty is retail's base-experience curve: the row is ``mob level - player
level`` and the column the player's five-level bracket, ``(level - 1) // 5``.  The
numbers live in ``data/exp_table.json`` (imported from LandSandBoat's published table
by ``tools/import_lsb_exp_table.py``; the schema and this code are Fanxi's).  A
monster that pays no experience checks as too weak; a level 56+ monster that still
pays a little checks as incredibly easy prey.

The Defense/Evasion sentence follows the same rule LandSandBoat's
``0x0dd_equip_inspect.cpp`` uses: Attack below the monster's Defense is high defense,
Attack at least 25% above it is low defense; Accuracy below Evasion - 30 is high
evasion, and at least Evasion + 10 is low evasion.  The two adjustments are
independent, so the messages run from 170 (both high) through 174 (even) to 178
(both low).

This module is pure data and arithmetic.  ``zone.py`` finds the target, reads the
player's and monster's combat stats, and sends the 0x029 packet.
"""

from __future__ import annotations

import json
import logging
from enum import IntEnum
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("fanxi.check")

# The source dataset, tracked with the other tables the server reads.
_DATA = Path(__file__).resolve().parents[3] / "data" / "exp_table.json"
_BRACKETS = 20


# The client's mob-difficulty enum, in the order Data2 uses (LandSandBoat's
# ``EMobDifficulty``).  The client's message is selected by ``64 + value``.
class Difficulty(IntEnum):
    TOO_WEAK = 0
    INCREDIBLY_EASY_PREY = 1
    EASY_PREY = 2
    DECENT_CHALLENGE = 3
    EVEN_MATCH = 4
    TOUGH = 5
    VERY_TOUGH = 6
    INCREDIBLY_TOUGH = 7


# BtlMess ids (``action.messages``) the client prints for a check.
CHECK_MESSAGE = 174
CHECK_IMPOSSIBLE_MESSAGE = 249       # "<mob>'s strength is impossible to gauge!"
CHECK_DATA_BASE = 64                 # Data2 = this + Difficulty
CHECK_IEP_MIN_LEVEL = 56             # a level-56+ monster can still be IEP at low EXP

DIFFICULTY_NAMES = {
    Difficulty.TOO_WEAK: "too weak",
    Difficulty.INCREDIBLY_EASY_PREY: "incredibly easy prey",
    Difficulty.EASY_PREY: "easy prey",
    Difficulty.DECENT_CHALLENGE: "decent challenge",
    Difficulty.EVEN_MATCH: "even match",
    Difficulty.TOUGH: "tough",
    Difficulty.VERY_TOUGH: "very tough",
    Difficulty.INCREDIBLY_TOUGH: "incredibly tough",
}


@lru_cache(maxsize=1)
def _table():
    """``(first_difference, last_difference, rows)`` from ``data/exp_table.json``.

    ``rows[0]`` is the lowest level difference and ``len(rows[0])`` the number of
    five-level player brackets.  A malformed or missing file logs once and turns on
    the fallback below; the tracked JSON is what the server normally reads.
    """
    try:
        document = json.loads(_DATA.read_text(encoding="utf-8"))["base_exp"]
        first = int(document["first_difference"])
        last = int(document["last_difference"])
        rows = tuple(tuple(int(value) for value in row) for row in document["rows"])
        if len(rows) != last - first + 1 or any(len(row) != _BRACKETS for row in rows):
            raise ValueError("expected %d rows of %d brackets"
                             % (last - first + 1, _BRACKETS))
        return first, last, rows
    except Exception as exc:  # missing file, bad JSON, wrong shape
        log.warning("check EXP table unavailable (%s); using the level-difference fallback",
                    exc)
        return None


def _fallback_exp(player_level: int, mob_level: int) -> int:
    """A coarse level-difference curve for a checkout without ``data/exp_table.json``.

    These are Fanxi's own bands, not retail's table; they keep /check answering with a
    plausible word instead of failing when the source dataset is missing.
    """
    difference = int(mob_level) - int(player_level)
    if difference >= 8:
        return 400
    if difference >= 5:
        return 350
    if difference >= 2:
        return 220
    if difference >= 0:
        return 200
    if difference >= -2:
        return 160
    if difference >= -6:
        return 60
    return 0


def base_exp(player_level: int, mob_level: int) -> int:
    """Unmodified EXP a player of ``player_level`` earns from ``mob_level``.

    The player is clamped at 99, the level difference to the table's range, and the
    column is ``(level - 1) // 5``; past level 99 the last column stands in.
    """
    player = max(1, int(player_level))
    table = _table()
    if table is None:
        return _fallback_exp(player, mob_level)
    first, last, rows = table
    bracket = (min(player, 99) - 1) // 5
    difference = max(first, min(last, int(mob_level) - player))
    return int(rows[difference - first][bracket])


def difficulty(player_level: int, mob_level: int) -> Difficulty:
    """The ``EMobDifficulty`` retail would print for this pair of levels."""
    exp = base_exp(player_level, mob_level)
    if exp >= 400:
        return Difficulty.INCREDIBLY_TOUGH
    if exp >= 350:
        return Difficulty.VERY_TOUGH
    if exp >= 220:
        return Difficulty.TOUGH
    if exp >= 200:
        return Difficulty.EVEN_MATCH
    if exp >= 160:
        return Difficulty.DECENT_CHALLENGE
    if exp >= 60:
        return Difficulty.EASY_PREY
    # The small tail of EXP: only high-level monsters still pay it, and those check as
    # incredibly easy prey rather than too weak (LandSandBoat's IncrediblyEasyPreyCheck).
    if exp > 0 and int(mob_level) >= CHECK_IEP_MIN_LEVEL:
        return Difficulty.INCREDIBLY_EASY_PREY
    return Difficulty.TOO_WEAK


def message_id(player_attack: int, player_accuracy: int,
               mob_defense: int, mob_evasion: int) -> int:
    """Which of the nine check messages the client should print (170..178).

    Defense moves the id by one and Evasion by three, exactly as the reference
    implementation does.  ``CHECK_MESSAGE`` (174) is the even/even line, which prints
    only the difficulty sentence.
    """
    message = CHECK_MESSAGE
    if int(mob_defense) > int(player_attack):
        message -= 1
    elif int(mob_defense) * 5 <= int(player_attack) * 4:   # 25% below Attack
        message += 1
    if int(mob_evasion) - 30 > int(player_accuracy):
        message -= 3
    elif int(mob_evasion) + 10 <= int(player_accuracy):
        message += 3
    return message
