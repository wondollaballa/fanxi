"""Kill-chain state for the end-of-combat point rewards.

Retail's EXP, capacity-point and exemplar-point rewards all chain when a qualifying
monster is defeated again inside a short window.  The first kill only arms the window;
the next one is chain #1, then #2, and so on.  A monster that is too weak for the
reward does not advance or break the chain (the window simply runs out).

This module is pure.  The caller keeps one :class:`ChainState` per character and feeds
the current time into :meth:`ChainState.advance` after a reward has been calculated.
"""
from __future__ import annotations

from dataclasses import dataclass

# Retail's Master chain timer is not a flat 30 s: players report a first window long
# enough for a ~35-40 s solo kill and the window shrinking with every link until it
# reaches the 30 s floor around chain #25 (a 2024 solo Locus log chained 27 kills at a
# 34 s average and read the timer reaching 30 s at the 26th kill; the 2024 FFXIAH
# thread agrees the timer is "definitely 30 seconds when it matters").  A flat 30 s
# window from chain #0 was why a normal solo kill pace never showed a Master chain #1.
EXEMPLAR_CHAIN_START_SECONDS = 60.0
EXEMPLAR_CHAIN_SECONDS = 30.0
EXEMPLAR_CHAIN_FLOOR_LINK = 25
# A Master chain is +2% exemplar points per link, capped at chain #50 (+100%).
EXEMPLAR_CHAIN_MAX = 50
EXEMPLAR_CHAIN_BONUS_PER_LINK = 0.02


def window_for(chain_number: int) -> float:
    """The window this kill arms for the next one, by the chain it just became.

    Chain #0 (a lone kill or a broken chain) gets the full 60 s; the window loses the
    difference over ``EXEMPLAR_CHAIN_FLOOR_LINK`` links and then stays at 30 s.
    """
    span = EXEMPLAR_CHAIN_START_SECONDS - EXEMPLAR_CHAIN_SECONDS
    step = span / EXEMPLAR_CHAIN_FLOOR_LINK
    return max(EXEMPLAR_CHAIN_SECONDS,
               EXEMPLAR_CHAIN_START_SECONDS - step * max(0, int(chain_number)))



@dataclass
class ChainState:
    """One character's chain counter and the moment its window closes.

    ``number`` is 0 while the first kill's window is armed, and becomes 1, 2, ... on
    each kill that lands inside it.  ``until`` is an absolute timestamp; 0 means no
    window has been armed yet.
    """

    number: int = 0
    until: float = 0.0

    def advance(self, now: float, *, window: float, cap: int | None = None) -> int:
        """Feed one qualifying kill at ``now`` and return the chain number.

        A kill inside the window increments the chain (starting at 1 on the second
        kill); a kill outside it restarts from 0.  The window is always refreshed.
        ``cap`` limits the stored chain number (the Master chain caps at 50) while
        still refreshing the window, so a capped chain stays alive.
        """
        now = float(now)
        inside = bool(self.until) and now <= float(self.until)
        if inside:
            self.number = int(self.number) + 1
        else:
            self.number = 0
        if cap is not None:
            self.number = min(self.number, max(0, int(cap)))
        self.until = now + max(0.0, float(window))
        return self.number

    def bonus(self, per_link: float) -> float:
        """A multiplier for the current chain (1.0 at chain 0)."""
        return 1.0 + max(0.0, float(per_link)) * max(0, int(self.number))

    def active(self, now: float) -> bool:
        return bool(self.until) and float(now) <= float(self.until)
