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
  takes 15 seconds off each (48 s → **33 s** at 99).
- The **group-1 Scholar merits** are applied: **Grimoire Recast** takes 2 s a rank off
  Light/Dark Arts, **Max Sublimation** adds 10 MP a rank to its storage, **Helix Magic
  Acc./Atk.** adds +3 Magic Accuracy and +2 Magic Atk. Bonus a rank to Helix spells, and
  **Modus Veritas Duration** softens that ability's duration penalty.
- The **100-JP Storm II line** and the **1200-JP Helix IIs** are registered gift spells:
  only a level-99 Scholar main can cast them (the Storm IIs have no ordinary level row, so
  before this they were open to every job).
- **Stratagem Effect IV** is not applied yet: the client owns spell recast, so the ranks'
  recast reduction cannot be sent from the server the way an ability recast can.
- The group-2 merit abilities (**Altruism**, **Focalization**, **Tranquility**,
  **Equanimity**, **Enlightenment**) put their status icons up and **Stormsurge** is not
  in the ability table, but their next-spell accuracy/enmity, dual-Addendum and storm-stat
  effects are not modelled yet.

## Red Mage

- **Quick Magic** has a 5% base chance.  A proc finishes the cast on the next tick with
  a `Quick Magic!` chat line and refunds its job-point row: 2% of the spell's MP cost
  per rank (40% at rank 20), matching LandSandBoat's "MP consumption -2%" comment.
