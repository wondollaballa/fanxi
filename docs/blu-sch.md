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
- **Modus Veritas** doubles a Helix's damage-over-time tick, adds its job-point bonus and
  halves the remaining duration; each **Modus Veritas Duration** merit rank gives 5% of
  that penalty back (25% at 5/5).
- **Immanence** gives the next damaging elemental spell the skillchain property of its
  element, so two casts can open and close a chain; the closing spell's damage is the
  chain's base and the chain plays from the spell's own result (see
  [skillchains.md](skillchains.md)).  Magic Burst reads the same state, so a Scholar's
  burst list works after the chain closes.
- **The Scholar HUD** tracks the strategem charges and the recharge clock and runs the
  player's own self-skillchain macros and magic bursts; see
  [control-panel.md](control-panel.md).  Its clock uses retail's rate: the four-minute
  pool is split across the level's charges, and the 550-JP **Stratagem Recast Time** gift
  takes 15 seconds off each (48 s → **33 s** at 99).  Each spent charge has its own
  return time, so two stratagems used back to back come back together after 33 s rather
  than 33 s apart.
- The **group-1 Scholar merits** are applied: **Grimoire Recast** takes 2 s a rank off
  Light/Dark Arts, **Max Sublimation** adds 10 MP a rank to its storage, **Helix Magic
  Acc./Atk.** adds +3 Magic Accuracy and +2 Magic Atk. Bonus a rank to Helix spells, and
  **Modus Veritas Duration** softens that ability's duration penalty.
- The **100-JP Storm II line** and the **1200-JP Helix IIs** are registered gift spells:
  only a level-99 Scholar main can cast them (the Storm IIs have no ordinary level row, so
  before this they were open to every job).
- The **group-2 Scholar merits** are applied: **Altruism** / **Focalization** add +10
  Magic Accuracy at rank 1 and +5 a rank after that to the next matching white/black
  spell; **Tranquility** / **Equanimity** take 10 enmity a rank off it; **Enlightenment**
  gives +5 INT/MND a rank to the first spell and counts as both arts for the duration
  formulas; **Stormsurge** adds +3 at 1/5 and +1 a rank after that (Voidstorm gives half,
  floored) to the stat its storm spell grants.  The four stratagems are merit-locked: a
  rank of 0 drops them from the Abilities menu and refuses a hand-built use.
- **Stratagem Effect IV** is not applied yet: the client owns spell recast, so the ranks'
  recast reduction cannot be sent from the server the way an ability recast can.

## Red Mage

- **Quick Magic** has a 5% base chance.  A proc finishes the cast on the next tick with
  a `Quick Magic!` chat line and refunds its job-point row: 2% of the spell's MP cost
  per rank (40% at rank 20), matching LandSandBoat's "MP consumption -2%" comment.
