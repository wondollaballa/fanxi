# Corsair rolls

Fanxi implements all 31 Phantom Rolls on the normal status-effect path, with the
values from BG-wiki's Roll Total tables rather than a per-point approximation.
Lucky and unlucky numbers are why the table matters: Fighter's Roll V is +10%
Double Attack while VI is only +5%, and Chaos Roll IV is +25% Attack while VIII is
+3%.

## What exists

- The in-game Abilities HUD keeps **Phantom Roll** as one button; clicking it opens
  a searchable picker of the learned rolls, sortable by name or by the level the roll
  is learned at, and the pick runs that roll's `/ja` directly. **Quick Draw** opens
  its eight elemental shots in element order. This keeps a 99 Corsair's Abilities
  page to the two menus plus Double-Up, Snake Eye, Random Deal, Wild Card, Triple
  Shot, Fold, Cutting Cards and Crooked Cards instead of 39 roll/shot tiles.
- The 31 rolls below get a client status icon (310-339 and 600), the rolled value
  in the chat line (`Fighter's Roll: 6`), and the matching modifiers.
- The Phantom Roll picker prints each roll's **Lucky** and **Unlucky** totals on its
  row (and in the tooltip). The chat line adds `(Lucky!)` or `(Unlucky!)` when a roll
  or Double-Up lands on one of those totals.
- A GearSwap set named `sets.JA["Phantom Roll"]` is a family set: the phase plan
  expands it to all 31 individual roll action ids, so rolling with Corsair's,
  Samurai, Bolter's, etc. wears the same +duration gear. A roll is also allowed to
  override a full gear lock or pinned weapon/range/ammo slots for the length of the
  action, then the phase engine puts the locked pieces back and keeps the lock armed.
  If the roll is refused (recast, range, no target) the restore happens after the
  short job-ability timeout instead of waiting for a 0x028. Without that expansion the
  client sent the individual roll id, the "Phantom Roll" door set never matched, and
  the timer stayed at the base 340 s.
- Roll total is 1-6 on the initial use. **Snake Eye** makes the next roll **or**
  Double-Up an XI and is consumed by whichever comes first; **Crooked Cards** adds one
  to the next roll.
- **Double-Up** adds another die roll (1-6) to the most recently applied roll for 45
  seconds after that roll. Outside that window the ability check fails with the retail
  **NoEligibleRoll** message (428) and no fake Double-Up animation or recast. The number
  the client shows in the dice animation is the increase; the chat line shows the new
  total.
- An XI roll on the bar protects the **other** roll from a bust; the doubled roll is
  removed instead. A real bust applies status **309 (Bust)** with its own icon and
  blocks every new roll until Fold, zoning or death.
- A Corsair main may keep **two** rolls; a Corsair support job keeps one. A third
  roll replaces the oldest one.
- Exceeding XI busts the roll and applies the **Bust** status (309), which blocks
  every new roll until **Fold**, zoning or death removes it. Bust duration is 5:00
  minus 10 s per rank of the Bust Duration group-1 merit.
- **Bust Evasion** (20% at rank 20 on this server) keeps an over-XI roll at XI.
  A *different* XI already on the bar makes the bust effect immune; the doubled
  roll still leaves the bar, so Double-Up cannot run forever on an XI.
- Reaching XI clears the Phantom Roll recast.
- **Fold** removes the active rolls and the Bust effect.
- **Roll duration** is 5:00 plus +2 s per Phantom Roll Duration job point, +20 s per
  Winning Streak merit (+6 s more per rank while a Commodore/Lanun Tricorne is worn),
  and every equipped Phantom Roll duration row (Chasseur's Gants, Camulus's Mantle,
  Regal Necklace, Compensator, Lanun Knife, Rostam), capped at retail's 11:00. The
  item rows for the missing final stages are migration 0168.
- A re-roll replaces the previous value, including a lower one.
- Rolls land on the caster and on party members inside the 7.9-yalm radius. The
  server sends the party-status-icons packet (S2C `0x076`) after every roll change,
  so the Party Info window shows the same buff icon on every member instead of
  "status effects are not sent for this party".

## The rolls

| Ability | Icon | Effect |
|---|---:|---|
| Fighter's Roll | 310 | Double Attack rate |
| Monk's Roll | 311 | Subtle Blow |
| Healer's Roll | 312 | Cure potency received |
| Wizard's Roll | 313 | Magic Attack Bonus |
| Warlock's Roll | 314 | Magic Accuracy |
| Rogue's Roll | 315 | Critical hit rate |
| Gallant's Roll | 316 | Defense |
| Chaos Roll | 317 | Attack / Ranged Attack |
| Beast Roll | 318 | Pet Attack / Ranged Attack |
| Choral Roll | 319 | Spell interruption rate down |
| Hunter's Roll | 320 | Accuracy / Ranged Accuracy |
| Samurai Roll | 321 | Store TP |
| Ninja Roll | 322 | Evasion |
| Drachen Roll | 323 | Pet Accuracy / Ranged Accuracy |
| Evoker's Roll | 324 | MP/tick (Refresh) |
| Magus's Roll | 325 | Magic Defense Bonus |
| Corsair's Roll | 326 | EXP / Capacity / Exemplar points |
| Puppet Roll | 327 | Pet Magic Accuracy / Magic Attack |
| Dancer's Roll | 328 | Regen |
| Scholar's Roll | 329 | Conserve MP |
| Bolter's Roll | 330 | Movement speed |
| Caster's Roll | 331 | Fast Cast |
| Courser's Roll | 332 | Snapshot |
| Blitzer's Roll | 333 | Melee delay reduction |
| Tactician's Roll | 334 | Regain (TP/tick) |
| Allies' Roll | 335 | Skillchain damage / accuracy |
| Miser's Roll | 336 | Save TP |
| Companion's Roll | 337 | Pet Regain / Regen |
| Avenger's Roll | 338 | Counter rate |
| Naturalist's Roll | 339 | Enhancing magic duration |
| Runeist's Roll | 600 | Magic Evasion |

## Mechanics wired into the engine

- Attack/Defense percentages, Double Attack, Subtle Blow, critical hit rate, Magic
  Attack/Accuracy/Defense/Evasion, Accuracy/Ranged Accuracy, Evasion, Store TP,
  Save TP, Fast Cast, Haste (ability), Cure potency received, Enhancing Magic
  duration, Skillchain Bonus, Counter, Refresh, Regen, Regain, Conserve MP and
  movement speed are written as normal modifiers.
- **Bolter's Roll** is the one that was actively wrong before: it used to write
  Ranged Accuracy. It now writes LandSandBoat's `MOVE_SPEED_BOLTERS_ROLL` (1086)
  and the 0x037/0x00D speed byte is raised by the rolled percentage, capped at
  +60%.
- **Corsair's Roll** multiplies the killer's EXP or Exemplar Points by the rolled
  percentage.
- **Tactician's Roll** adds its Regain value to TP every three-second tick;
  Evoker's and Dancer's rolls tick MP/HP through the normal Refresh/Regen path.
- **Avenger's Roll** gives a flat counter chance on an incoming hit.
- **Beast/Drachen/Puppet/Companion's Roll** write the owner's pet fields and are
  re-applied when a pet is called after the roll.

## Known limits

- Conserve MP, Snapshot and spell-interruption rate are stored as modifiers and
  appear in the launcher's stat report, but the spell-cost/ranged-delay/cast-
  interruption formulas do not spend them yet.
- Pet Regain/Regen is stored on the pet; the pet tick does not restore TP/HP from
  it yet.
- Rolls do not apply the retail "job modifier" bonus from a party member of the
  matching job, nor the Phantom Roll+ potency from gear. Those are separate rows.
- Wild Card, Cutting Cards, Quick Draw, Random Deal, Triple Shot, Optimal Range,
  ammunition consumption and the remaining COR job-point rows are separate from
  this document; see `docs/job-points.md`.
