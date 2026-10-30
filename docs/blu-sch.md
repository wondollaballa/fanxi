# Blue Mage and Scholar extras

## Blue Mage

- **Physical Blue Magic Effect Accuracy** is wired as a passive accuracy row.
- **Unbridled Learning** now runs for 120 s (the second job-point row).
- **Blue Magic Point Bonus** is exposed as a modifier and Unbridled Wisdom's status is
  wired, but there is no spell-set manager yet, so the client can cast the blue spells it
  already knows without a point budget.

## Scholar

- **Sublimation** is implemented and verified (see `sublimation.md`).
- **Caper Emissarius** heals for 10% + its job-point percentage of max HP.
- **Modus Veritas** adds its job-point bonus to a target's damage-over-time tick.
- **Stratagem Effect IV** and Quick Magic on Red Mage are handled separately.

## Red Mage

- **Quick Magic** has a 5% base chance.  A proc finishes the cast on the next tick with
  a `Quick Magic!` chat line and refunds its job-point row: 2% of the spell's MP cost
  per rank (40% at rank 20), matching LandSandBoat's "MP consumption -2%" comment.
