# Red Mage enfeebles, enhancing and the gear sets behind them

This page records why `gearswap/RDM.lua` carries several Enfeebling and Enhancing Magic sets
instead of one each, and how the Gear page and the phase engine pick between them. The source is the
[Community Red Mage Guide](https://www.bg-wiki.com/ffxi/Community_Red_Mage_Guide) on BG
Wiki, section **Gear Sets → Enfeebling Magic Sets**, plus the guide's Enhancing Magic sets.

## The distinction

Every Enfeebling Magic spell looks at one thing when the game works out how strong it is
or whether it lands. The guide splits the spells by that thing, and the gear follows:

| Kind | What the spell reads | Spells | Set |
|---|---|---|---|
| **Skill** | Enfeebling Magic Skill (potency + the skill's own accuracy bonus) | Frazzle III, Distract III, Poison, Poison II | `midcast.Enfeebling Magic Skill` |
| **Macc** | Magic Accuracy; the effect is all-or-nothing | Frazzle II, Distract II, Dia / II / III, Sleep, Bind, Break, Silence, Virus | `midcast.Enfeebling Magic Macc` |
| **Duration** | the timer, not the potency | Sleep, Sleep II, Bind, Break, Silence (and their -ga forms) | `midcast.Enfeebling Magic Duration` |
| **Macc + potency** | both landing and potency | Gravity, Gravity II | `midcast.Enfeebling Magic Hybrid` |
| **MND** | dMND (your MND minus the target's) | Slow II, Paralyze II, Addle II | `midcast.Enfeebling Magic MND` |
| **INT** | dINT (your INT minus the target's) | Blind II | `midcast.Enfeebling Magic INT` |
| **General** | nothing: no accuracy, no skill, no dStat | Dispel, Dispelga, Inundation | `midcast.Enfeebling Magic General` |

A few consequences worth remembering:

- **Frazzle II is a Macc spell, Frazzle III is a Skill spell.** Frazzle III's potency scales
  with skill up to 625, but it cannot immunobreak; casting Frazzle II in full Magic Accuracy
  first helps it land at full power. Distract follows the same split.
- **Sleep, Bind, Break and Silence are crowd control.** Landing them is life-or-death, so the
  guide's "MAcc. & Duration" set is the default; switch to the Duration build when the timer
  is what the fight needs (`Silence` in particular is either an accuracy or a duration
  problem depending on the target).
- **Gravity is a hybrid.** Its movement-speed value is potency (and Saboteur); landing it is
  accuracy. The guide's "MAcc + Pot. Hybrid" set carries both.
- **Slow II, Paralyze II and Addle II want MND.** Their base rate is small, and the dMND term
  is the rest of the value (Slow caps at ±75 dMND, Paralyze at ±40, Addle at ±100).
- **Blind II wants INT**, and the dINT term is the whole effect.
- **Dispel, Dispelga and Inundation cannot be resisted**, so accuracy and skill are wasted
  slots. The guide's "Full Duration & TH" build uses Volte for duration and `Per. Lucky Egg`
  (or another +4 TH piece) to apply Treasure Hunter with Inundation.
- **Hands under Saboteur:** the guide swaps the hands to `Lethargy Gantherots +1` on every
  enfeebling cast while Saboteur is up. Fanxi does this automatically: Saboteur is status
  **454**, the engine already tracks the player's live buff ids, and the Enfeebles card's
  **Saboteur** row is a one-piece overlay (`midcast.Enfeebling Magic Saboteur`,
  `hands = "Lethargy Gantherots +3"` — this server has the +3 tier). While the status is up the
  plan registers a conditional rule for every enfeebling spell that *merges* the overlay over
  the spell's kind set; after the result the kind set's hands return. One overlay covers all
  seven kinds, and if the character does not own the Gantherots nothing binds (no swap).

## How Fanxi uses the split

- `host/addons/lua/control.lua` classifies each Enfeebling Magic spell into one kind and
  reports it in `job_spells` as a second category (`enfeebles_skill`, `enfeebles_mnd`, ...)
  next to the `enfeebles` group.
- The **Gear page → Spells → Enfeebles** card has one row per kind. Each row picks a set
  (the launcher fills the row from the matching `RDM.lua` path when the library has it) and
  lists the spells that kind applies to. Click a kind's name to see that set's pieces.
- The **Mode** dropdown stays for the forced case: `Auto — by spell type` is the default and
  wears each spell's own kind; picking Skill, Macc, Duration, MND, INT, Macc + potency or
  General forces *every* enfeebling spell through that one set (the old behaviour, also
  available in game with `//modes enfeebles macc` and friends).
- The phase engine resolves the plan in the order: per-spell card → the spell's kind set →
  the midcast default → the library's `midcast.Enfeebling Magic`. A kind with no set falls
  back to the generic enfeebling set, so a library that has only `midcast.Enfeebling Magic`
  behaves exactly as before.
- Duration falls back to Macc when no Duration set is configured: a slept target that was
  never slept has no timer to extend.
- **Saboteur** is an automatic row, not a mode: while status 454 is in the player's buff list
  the host adds a higher-priority rule for every enfeebling spell that merges the one-piece
  overlay `midcast.Enfeebling Magic Saboteur` (the hands) over the spell's kind set. The row
  shows `Sab on buff`, and the kind's gear preview lists the overlay's piece under the set.

## The sets

All seven are the guide's tables, with the item names the server's item table uses.

| Set | Guide name | Core pieces |
|---|---|---|
| `midcast.Enfeebling Magic Skill` | Skill Potency Hybrid | Contemplator +1, Enki Strap, Regal Gem, Vitiation Chapeau +4, Atrophy Tabard +4, Kaykaus Cuffs +1, Psycloth Lappas, Vitiation Boots +4, Duelist's Torque +2, Vor Earring, Snotra Earring, Stikini Ring +1 ×2, Obstin. Sash, Sucellos's Cape (MND+20 / Macc+30 / FC+10 / PDT−10%) |
| `midcast.Enfeebling Magic Macc` | MAcc. & Duration | Contemplator +1, Enki Strap, Ullr, Vitiation Chapeau +4, Lethargy Sayon +3, Regal Cuffs, Psycloth Lappas, Vitiation Boots +4, Duelist's Torque +2, Regal Earring, Snotra Earring, Kishar Ring, Stikini Ring +1, Luminary Sash, Sucellos's Cape (INT+20 / Macc+30 / FC+10 / PDT−10%) |
| `midcast.Enfeebling Magic Duration` | MAcc. & Duration (Silence/CC variant) | As above with Atrophy Tabard +4, Kaykaus Cuffs +1 and Stikini Ring +1 ×2 |
| `midcast.Enfeebling Magic Hybrid` | MAcc + Pot. Hybrid | As Skill with Lethargy Sayon +3 body, Kaykaus Cuffs +1, Kishar Ring / Stikini Ring +1 |
| `midcast.Enfeebling Magic MND` | Full Mind+ Potency | As Skill with Lethargy Sayon +3 body, Chironic Hose (MND+15 / Macc+40), Metamorph Ring +1, Sucellos's Cape (MND+30 / Macc+20 / FC+10 / PDT−10%) |
| `midcast.Enfeebling Magic INT` | Full INT+ Potency | Marin Staff +1 (main), Enki Strap, Regal Gem, Vitiation Chapeau +4, Lethargy Sayon +3, Regal Cuffs, Psycloth Lappas, Vitiation Boots +4, Duelist's Torque +2, Regal Earring, Snotra Earring, Metamorph Ring +1, Kishar Ring, Acuity Belt +1, Sucellos's Cape (INT+30 / Macc+20 / FC+10 / PDT−10%) |
| `midcast.Enfeebling Magic General` | Full Duration & TH | Per. Lucky Egg, Volte Cap, Volte Jupon, Regal Cuffs, Volte Hose, Volte Boots, Duelist's Torque +2, Snotra Earring, Kishar Ring, Obstin. Sash |
| `midcast.Enfeebling Magic Saboteur` | hands override (all enfeebles) | Lethargy Gantherots +3 — a merge overlay, not a full set |

The enfeebling sets all wear `Duelist's Torque +2`, which Oboro now augments:
R25 is INT/MND +15 plus enhancing and enfeebling magic duration +25% (see
[oboro-r25.md](oboro-r25.md)). The launcher's set preview falls back to the bag
copy's decoded augments, so the torque shows its real rows in the Gear page.

## Enhancing Magic is split by spell too

The guide's **Skill Based Enhancing Sets** and **Enhancing Duration Sets** give the
enhancing spells the same treatment as the enfeebles:

| Kind | Spells | Set |
|---|---|---|
| **Skill (Aquaveil)** | Aquaveil | `midcast.Enhancing Magic SIRD` (spell-interruption rate down, so the cast survives) |
| **Stoneskin** | Stoneskin | `midcast.Enhancing Magic Stoneskin` (Enhancing skill + MND push the absorb past its base cap) |
| **Duration** | Barspell (every Bar- and Bar-ra spell), Blink, Haste, Hastega, Haste II, Flurry, Flurry II | `midcast.EnhancingDurationOthers` for party casts; `midcast.EnhancingDuration` while Composure is up |
| **General** | Protect, Shell, Regen, Refresh, Temper, the storms/spikes/travel spells and the rest | `midcast.Enhancing Magic` |

The guide's **Duration (Self)** and **Duration (Others)** tables are the two duration
builds; the self build is the one that leans on Composure's triple-duration bonus:

| | Duration (Self) | Duration (Others) |
|---|---|---|
| Main / sub | Colada (Enhancing Duration +4%), Ammurapi Shield | same |
| Head | Telchine Cap (+10% enhancing duration) | Lethargy Chappel +3 |
| Body | Vitiation Tabard +4 | Lethargy Sayon +3 |
| Hands / legs | Atrophy Gloves +4 / Telchine Braconi (+10%) | Atrophy Gloves +4 / Lethargy Fuseau +3 |
| Feet | Lethargy Houseaux +3 | Lethargy Houseaux +3 |
| Neck / ear | Duelist's Torque +2 / Leth. Earring +2 | same |
| Waist / back | Embla Sash / Sucellos's Cape | same |

**Composure** (status 419) is the switch between them, the same live-status mechanism
Saboteur uses for the enfeebles: while it is up the duration spells wear the self build,
otherwise the party build. `spell_modes` keeps the old forced choices as modes (`Skill`,
`Stoneskin`, `Duration`, `General`), so `//modes enhancing duration` still forces one set
for every enhancing spell. Protect V, Shell V and Reraise scale with nothing once capped
(the guide suggests Conserve MP for them); Fanxi leaves them on the General set.

`gearswap/RDM.lua` keeps `midcast.Enhancing Magic SIRD`, `midcast.Enhancing Magic
Stoneskin`, `midcast.EnhancingDuration`, `midcast.EnhancingDurationOthers` and the plain
`midcast.Enhancing Magic` for these rows, plus the guide's TP, enspell-damage and magic-WS
builds.

The guide prints Oseem augments as `Type:A/Rank:15` and similar. The library names those
pieces without their rolled augment lines; the Gear page's hover card falls back to the bag
copy's decoded augments when it can. The capes use the launcher's normal
`{ name = ..., augments = {...} }` builds, so the selected cape shows its augment list.

## Links

- [Community Red Mage Guide](https://www.bg-wiki.com/ffxi/Community_Red_Mage_Guide)
- [GearSwap README](../gearswap/README.md) — the library layout rules
- [Launcher guide](launcher.md) — the Spells panel and the phase engine
