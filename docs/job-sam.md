# SAM audit — retail vs Fanxi

First dive of the job programme. Sources: the BG-wiki pages for each ability
(`Hasso`, `Seigan`, `Meditate`, `Third Eye`, `Sekkanoki`, `Konzen-ittai`, `Hagakure`,
`Shikikoyo`, `Blade Bash`, `Warding Circle`, `Yaegasumi`, `Sengikori`), the Samurai job
page for traits and merits, and our `job_abilities` / `effects.ABILITY_EFFECTS` /
`zone.job_ability` / `combat_mods`.

## The state before this pass

Samurai has 14 job abilities. One (`Konzen-ittai`) had an icon spec, seven only had the
job-point status fallback (`Meikyo Shisui`, `Warding Circle`, `Hasso`, `Seigan`,
`Hamanoha`, `Hagakure`, `Yaegasumi`), and six had **nothing** (`Third Eye`, `Meditate`,
`Sekkanoki`, `Shikikoyo`, `Blade Bash`, `Sengikori`). Only Meditate had a handler, and
it paid 1,100 TP at once instead of ticking.

## Findings

| Ability | Retail | Ours before | State after this pass |
|---|---|---|---|
| **Hasso** | +STR `floor(SAM/7)` (max 14), +10 Accuracy, +10% job-ability haste with a **two-handed** weapon; +50% casting/recast time; Seigan overwrites it; Zanshin can proc as an extra attack (rate = Zanshin/4, main job) | icon only (60 s), no stats, no cast penalty, no exclusivity | stance modifiers in `combat_mods` (2H only), 300 s, cancels Seigan, +50% cast time; Zanshin's extra attack lands at a quarter of the rate |
| **Seigan** | cancels Hasso, 300 s; Third Eye recast 30 s, Third Eye anticipates multiple hits and counters 25% | icon only (60 s), no Third Eye link | 300 s, cancels Hasso; Third Eye gets three charges and the 25% counter (the 30 s recast is client-side) |
| **Meditate** | 200 TP a tick × 5 (1000) as SAM main, 120 × 5 (600) as sub; +5 a tick from job points | +1,100 TP instantly | ticking state: 300 a tick (200 + 100 JP) to 1000, sub 120 to 600 |
| **Third Eye** | dodge the next attack, 30 s, 1:00 recast (0:30 under Seigan); with Seigan multiple hits + 25% counter | nothing | one charge (three under Seigan) spent before the damage roll, and the Seigan counter hits back; **the status icon id is the one open item** |
| **Sekkanoki** | next WS costs 1000 TP and rolls at 1000 TP potency | nothing | **done**: spends 1000, keeps the rest, caps potency at 1000, suppresses Hagakure for that skill |
| **Hagakure** | next WS gets +1000 TP bonus and 400 Save TP | icon only | **done**: `job_ability` sets both for the next WS |
| **Konzen-ittai** | readies the target for a skillchain (the wiki's Light→Darkness→Gravitation→… order) | icon only | **done**: seeds a resonating property so the skill forms the chain by itself |
| **Sengikori** | next WS: skillchain damage +25% and magic burst damage +25%, separate steps | nothing | **done**: +25% on the chain, then +25% on the burst that follows |
| **Shikikoyo** | shares TP above 1000 with a party member, +12% a merit rank (2,960 at 5/5) | nothing | **done**: keeps 1000, the merit rows raise what the target receives |
| **Blade Bash** | stun (and plague); no damage, no TP | nothing | **done**: 3-second stun (plague not modelled) |
| **Warding Circle** | 15% damage up / damage taken down vs demons, +15% demon killer (5% as sub), 3 min | icon only | 3-minute icon; **the demon damage/killer part is blocked** — `monster_templates` has no family column, so nothing can identify a demon |
| **Yaegasumi** | evades abilities, +500 TP per evade, +20% WSD per evade (60% cap), 45 s | icon only | the 45-second icon; the evade mechanic is not wired to the monster TP-move path yet |
| **Meikyo Shisui** | weapon skills cost 1000 TP; damage uses current TP; TP return suppressed; grants 3000 TP | icon only | **done** for the TP/cost rules (no status icon yet) |
| **Hamanoha** | lowers a demon's Accuracy, Evasion, Magic Accuracy, Magic Evasion and Store TP by a flat 20 for 3 min | icon only | **blocked**: needs the demon family check (same missing data as Warding Circle) |
| **Zanshin / Store TP / Ikishoten / Overwhelm** | traits | Store TP, Zanshin, Skillchain Bonus and Damage Limit+ are the rows SAM has; the Demon Killer row needs family data | Store TP, Zanshin (extra swing), Skillchain Bonus and Damage Limit+ are read; Demon Killer is blocked |

## What changed

- `effects.HASSO` (353) and `effects.SEIGAN` (354) now have real specs: 300 s, each
  cancelling the other. `Hasso`'s stance modifiers are read in `combat_mods` only while
  a two-handed weapon (`combat.TWO_HANDED_SKILLS`) is equipped: `+floor(level/7)` STR
  (plus the job-point row that `job_points.conditional_mods` already adds), +10
  Accuracy, +1,000 job-ability haste (10%). Hasso also multiplies casting time by 1.5.
- **Meditate** is a real tick: five beats three seconds apart, 200 TP a tick as a
  Samurai main (plus the +5-a-rank job points), 120 a tick to 600 as a sub job, capped
  at 1,000. It no longer pays the whole bar at once.
- `test_sam.py` pins the stance stats and the two-handed requirement, the
  Hasso/Seigan overwrite, and both Meditate tick tables.

## What is closed, and what is blocked on data

Closed: Hasso, Seigan, Meditate, Third Eye's anticipate + Seigan counter, Sekkanoki,
Hagakure, Konzen-ittai, Sengikori, Shikikoyo, Blade Bash, Meikyo Shisui, Zanshin, and
the SAM trait rows that have a consumer (Store TP, Skillchain Bonus, Damage Limit+).

Blocked on missing data or systems, not on effort:

1. **Third Eye's status icon** — the effect id for the bar. The anticipate works without
   it; everything else is done.
2. **Warding Circle and Hamanoha** — both need a monster family, and
   `monster_templates` has no family column. The fix is an import of LandSandBoat's
   `mob_pools` family ids into the template table, then a `demon` family check in the
   damage path and the debuff.
3. **Yaegasumi** — needs a monster TP-move system to evade; Fanxi's monsters only melee.
4. **Demon Killer's damage bonus** — same family data as Warding Circle.
