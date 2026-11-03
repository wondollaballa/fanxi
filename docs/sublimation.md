# Scholar Sublimation

Sublimation is implemented as a toggle:

- First use puts up the **Sublimation** status (icon 187) and starts storing 1 MP per
  3-second tick, draining 1 HP per tick while HP is above 1.
- The store is capped at **300 + the Sublimation Effect job-point row + 10 a Max
  Sublimation merit rank** (360 at rank 20, 410 at 20 JP and 5/5 merits).
- Using Sublimation again releases the stored MP even while the ability is still on
  recast, then removes the status.
- Verified in game: `Sublimation releases 3 MP.` after a short activation.

Stratagem Effect IV is the remaining Scholar row without a hook: it reduces spell recast,
which the client owns.
