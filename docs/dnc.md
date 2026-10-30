# Dancer

Dancer's abilities are built on two resources: TP for waltzes and sambas, and Finishing
Moves for flourishes.  Steps and jigs are recast-only.  The layer was rebuilt around
those costs; a waltz is no longer a percentage of the caster's maximum HP.

Retail's ability table also carries menu headers — `Sambas`, `Waltzes`, `Jigs`, `Steps`
and `Flourishes I`/`II`/`III`.  They have no animation or effect, and this build's
Abilities list is flat, so migration 0147 removes them from `job_abilities`; the HUD
skips the same ids when a client still has an old 0x0AC command list cached.  Every real
Dancer ability keeps its own row and level.

## TP costs

| Ability | TP |
| --- | ---: |
| Step (Quickstep/Box Step/Stutter Step/Feather Step) | none (recast only) |
| Jigs (Spectral, Chocobo, Chocobo II) | none (recast only) |
| Curing Waltz / II / III / IV / V | 200 / 350 / 500 / 650 / 800 |
| Healing Waltz | 200 |
| Divine Waltz / Divine Waltz II | 400 / 800 |
| Drain Samba / Aspir Samba | 100 |
| Haste Samba | 350 |

A dance with too little TP is refused before the use animation plays.  **Trance** waives
the TP cost for 60 seconds and grants the Trance Effect job-point TP (2,000 at rank 20).
**Contradance** uses the Contradance Effect rows to cut waltz TP costs and doubles the
next waltz's healing; it is spent by that waltz.

"Waltz TP Cost" gear is read through LandSandBoat's `waltz_cost` modifier (id 139, in
5-TP units).  Migration 130 adds Desultor Tassets' -50 TP; the HUD checks the same item
before enabling the waltz icon.

## Waltzes

Curing Waltz I-V restore:

```
floor((caster CHR + target VIT) * M + B + 2 * Waltz Potency ranks)
```

with `M`/`B` = 0.25/60, 0.50/130, 0.75/270, 1.00/450 and 1.25/600.  A subbed Dancer
halves `M`; the job-point Waltz Potency row is a flat +2 HP per rank (40 at 20/20), not
a percentage.  The result is capped at the target's missing HP.

- Curing and Healing Waltz take a party member from the client's act index (self when it
  sends no target), within the ability's range.
- Divine Waltz and Divine Waltz II heal the caster's party in a 10-yalm radius.
- Healing Waltz removes one `waltzable` status effect instead of restoring HP.
- Saber Dance blocks every waltz while it is active.

The Battle hub's Healing page detects these abilities on a Dancer main **or sub job** and can use
Curing Waltz as a TP fallback when the character has no Cure spells, and Healing Waltz for status
effects when it has no -na spells.  See [battle.md](battle.md#dancer-waltzes) for the TP reserve,
HP threshold and waltzable-status list.

The heal is sent as a job-ability result (`MESSAGE_SKILL_RECOVERS_HP`), so the target's
client prints the amount and updates its HP bar immediately.

## Steps

Each step is recast-only (no TP cost) and rolls physical accuracy (plus Step Accuracy
merits and +50 from Presto), then puts up its own Daze family:

| Step | Daze | Effect per level |
| --- | --- | --- |
| Quickstep | Lethargic Daze | Evasion `-((level + 1) * 4)`, flat |
| Box Step | Sluggish Daze | Defense `-(5 + 2 * (level - 1))`% |
| Stutter Step | Weakened Daze | Magic Evasion `-3 * level`, flat |
| Feather Step | Bewildered Daze | Critical Hit Evasion `-level`% |

Daze stacks to 10 (5 for a subbed Dancer); levels 6-10 share the level-5 client icon but
keep their real level in the effect power.  The first step lasts 60 s plus Step Duration;
later steps extend the current timer by 30 s plus Step Duration, capped at 120 s plus
Step Duration.

A landed step grants 1 Finishing Move, +1 for a Dancer main (unless the target's Daze is
already capped) and +4 more from Presto.  Presto is spent on that step and also adds four
Daze levels.  Quickstep/Box Step/Stutter Step/Feather Step use the client's step result
info (5/6/7/8) so the log line says which Daze landed.

## Finishing Moves

The count lives in the power of Finishing Move 1, with the 1-5 and 6+ icons.  A Dancer
main can hold 9 (5 + two Maximum Finishing Moves job-point gifts of 2); a subbed Dancer
holds 5.  The 2-hour duration is refreshed whenever a move is earned or spent.

## Flourishes

| Ability | Moves | Effect |
| --- | ---: | --- |
| Animated Flourish | 1-2 | 1,000 VE with one move, 1,500 with two, +200 from Flourish I JP |
| Desperate Flourish | 1 | Weight (26% movement slow) on a physical accuracy roll |
| Violent Flourish | 1 | Physical hit and a 25% Stun chance |
| Reverse Flourish | 1-5 | TP = `(95 + Flourish II JP) * moves + 5 * moves^2 + 30 * merit` |
| Building Flourish | 1-3 | Stores the moves; the next weapon skill gets Acc+40, then Attack+25%, then Crit+10% |
| Wild Flourish | 2 | Applies Chainbound for 10 s |
| Climactic Flourish | 1-5 | Stores the moves (status icon) |
| Striking Flourish | 2 | Twofold attack status |
| Ternary Flourish | 3 | Threefold attack status |

Building Flourish also adds the Flourish II job-point Weapon Skill Damage (1% per rank)
to every hit of the weapon skill that consumes it.

## Sambas and jigs

Sambas spend TP and cancel the previous samba.  Drain, Aspir and Haste Samba last a 120 s
/ 120 s / 90 s base plus the Samba Duration rows (160/160/130 s at 20/20).  Haste Samba
applies 5% Haste (+1% per Haste Samba merit); Drain and Aspir Samba restore 10% / 5% of
each landed melee hit as HP / MP.  Fan Dance blocks all sambas.

Spectral Jig grants Sneak and Invisible for 180 s plus Jig Duration; Chocobo Jig and
Chocobo Jig II grant Quickening (+20% movement speed) for 120/180 s plus Jig Duration and
remove Weight.

## Still approximated

- Samba on-hit effects currently apply to the Dancer, not to every engaged party member.
- Wild Flourish's Chainbound icon does not yet make the skillchain engine treat the next
  weapon skill as a skillchain opener.
- Climactic, Striking and Ternary Flourish put up their statuses, but the forced
  critical/Double Attack/Triple Attack on the next attack round is not wired into the
  melee round.
- Waltz potency/recast gear, Closed Position and the full merit table are not modelled;
  the job-point rows that the server does apply are listed above.  The TP-cost line is
  modelled for waltzes only (no samba/step TP-cost gear).
- The HUD's ability window disables TP-costed waltzes/sambas when the current TP is
  short and shows the timer for recast-only abilities.  It mirrors the server's costs
  and the Desultor Tassets entry; a future TP-cost item needs both tables updated.
- Category headers (`Jigs`, `Steps`, `Waltzes`, `Sambas`, `Flourishes I`-`III`) are
  intentionally absent from the menu.  Selecting a real jig (Spectral/Chocobo/
  Chocobo II) affects that ability; the old header only printed "You use Jigs" and
  played the default animation.
