# Paladin spells, abilities and the gear sets behind them

This page records why `gearswap/PLD.lua` carries one set per spell kind instead of one
"Divine Magic" and one "Healing Magic" set, and how the Gear page and the phase engine pick
between them. The source is the
[Community Paladin Guide](https://www.bg-wiki.com/ffxi/Community_Paladin_Guide) on BG Wiki,
sections **Magic Casting Sets**, **Sets by Alimere** and **New and/or Returning Players Sets**.

## The distinction

Paladin casts three schools. None of them is one build:

| Spell | What the value reads | Set |
|---|---|---|
| Banish, Banishga, Banish II, Holy, Holy II | Magic Attack, MND | `midcast.Divine Magic` |
| Flash | Enmity (180 CE / 1,280 VE) and Fast Cast | `midcast.Flash` |
| Flash, when the cast must finish under fire | Spell interruption rate down | `midcast["Flash SIRD"]` |
| Repose (via /WHM) | Divine Magic skill / Magic Accuracy | `midcast.Divine Magic` |
| Enlight, Enlight II | Divine Magic skill (extra accuracy) and Enlight damage | `midcast.Enspell` |
| Cure III, Cure IV, Curaga | Cure Potency and Cure Received | `midcast["Healing Magic"]` |
| Cure, when the cast must finish under fire | Spell interruption rate down | `midcast["Cure SIRD"]` |
| Protect, Shell, Crusade | Enhancing Magic duration | `midcast["Enhancing Magic"]` |
| Phalanx | Enhancing Magic skill, then the Phalanx+ pieces | `midcast.Phalanx` |
| Phalanx (SIRD) | Spell interruption rate down | `midcast["Phalanx SIRD"]` |
| Reprisal | Enmity and duration (the block-rate boost is on the shield) | `midcast.Reprisal` |
| Reprisal (SIRD) | Spell interruption rate down | `midcast["Reprisal SIRD"]` |
| Stoneskin (via /SCH) | Stoneskin+ pieces and Enhancing skill | `midcast["Enhancing Magic Stoneskin"]` |
| Aquaveil (via /SCH) | Spell interruption rate down | `midcast["Enhancing Magic SIRD"]` |

A few consequences worth remembering:

- **Flash is not a nuke.** Its enmity is fixed, so the guide's build is Enmity and Fast Cast
  with HP and DT; Magic Attack does nothing for it. The SIRD variant is the same frame with
  the interruption pieces swapped in.
- **Phalanx has two halves.** Enhancing Magic skill moves the base value (-33 at the 443
  skill tier a Master Level 50 Paladin passes) and the Phalanx+ pieces add a flat amount on
  top. The guide's *Max Self Phalanx* set totals -71; the *Phalanx (Ideal)* set in the
  guide's Magic Casting Sets is the same idea with the Sworn pieces. `PLD.lua` uses the
  Max Self build for the row and carries the SIRD variant next to it.
- **Reprisal wants Enmity and duration, not block gear.** The block-rate multiplier is a
  property of the shield (Priwen triples it); the cast itself wants to be cheap to hold and
  hard to interrupt.
- **Enlight is an Enspell.** Fanxi's classifier keeps Enlight and Endark in **Enspells**
  because they are cast from the Enhancing Magic skill even though their own skill is
  Divine Magic; the Paladin build is the guide's Enlight set (Divine Magic skill plus
  Brilliance).
- **Cures are two things.** The potency build maximizes the heal and the cure received
  bonus; the SIRD build keeps the potency that matters while making the cast survive.
- **Protect, Shell and Crusade are duration casts.** The guide's Enhancing duration pieces
  (Colada, Ajax +1, Shab. Cuirass +1, Regal Gauntlets) are the core; the rest of the set
  keeps the tank's enmity and DT while the cast runs.

## How Fanxi uses the split

- `host/addons/lua/control.lua` classifies each Divine Magic spell into a kind
  (`divine_mab`, `divine_flash`, `divine_macc`) and reports it in `job_spells` as a second
  category next to the `divine` group. Enhancing Magic gained `enhancing_phalanx` and
  `enhancing_reprisal` the same way.
- The **Gear page → Spells → Divine Magic** card has one row per kind, exactly like
  Enfeebles and Enhancing. `Auto — by spell type` is the default: Flash wears the row's
  `midcast.Flash`, Banish and Holy wear `midcast.Divine Magic`, Repose lands in the same
  set. Picking another mode forces every Divine Magic spell through that set
  (`//modes divine auto|mab|flash|macc`).
- The **Enhancing / buffs** card now lists Phalanx and Reprisal as rows for the jobs that
  learn the spell (RDM/PLD/RUN and PLD respectively). A row's dropdown lists every
  `midcast.*` set, so the SIRD variant is one pick away: repoint the Flash row at
  `midcast.Flash SIRD` for a fight where the cast must not be interrupted.
- **Enspells** is shown for Paladin so the Enlight set binds: `midcast.Enspell` is the
  damage build and `midcast.EnspellNoDmg` the no-damage one, if the library adds it.
- The fallbacks in `launcher-rs/src/lib/phase.ts` keep every other job unchanged:
  `divine_flash` prefers `midcast.Flash` and falls back to `midcast.Divine Magic`;
  `enhancing_phalanx` prefers `midcast.Phalanx` and falls back to `midcast.Enhancing Magic`,
  and the same for Reprisal. A library without the new sets behaves exactly as before.
- A per-spell card still wins over the kind row.

The profile version bump to 4 moves a saved Divine Magic mode from the old default `mab`
to `auto` once, the way version 2 moved Enfeebles and version 3 moved Enhancing. A saved
`macc` pick is left alone.

## Job abilities

Paladin's job abilities follow the guide's **Noteworthy Equipment** column:
Invincible → Caballarius Breeches +4, Holy Circle → Reverence Leggings +4, Shield Bash →
Caballarius Gauntlets +4, Sentinel → Caballarius Leggings +4, Cover → Reverence Coronet +4
and Caballarius Surcoat +4, Rampart → Caballarius Coronet +4, Fealty → Caballarius Surcoat
+4, Chivalry → Caballarius Gauntlets +4, Divine Emblem → Chevalier's Sabatons +3.

Palisade, Intervene and Sepulcher have no guide gear note. Palisade (900 CE / 1,800 VE) and
Intervene (damage scaled by enmity) wear the enmity build, and Sepulcher wears the cure
build. `sets.precast.JA` is the enmity build too, so a /WAR or /RUN ability with no set of
its own still wears something sensible; the launcher's **Default JA set** row can point
elsewhere.

## Item names

The sets use the server's item names, which are the wiki's abbreviations for the +1/+2
tiers and the full names for +3/+4:

| Guide spelling | Server spelling |
|---|---|
| Rev. Surcoat +4 | Reverence Surcoat +4 |
| Cab. Gauntlets +4 / Cab. Breeches +4 | Caballarius Gauntlets +4 / Caballarius Breeches +4 |
| Chev. Armet +3 / Chev. Cuirass +3 / Chev. Sabatons +3 | Chevalier's Armet +3 / Chevalier's Cuirass +3 / Chevalier's Sabatons +3 |
| Kgt. Beads +2 | Knight's Bead Necklace +2 |
| Nourish. Earring +1 | Nourishing Earring +1 |
| Souv. Schaller +1, Souv. Cuirass +1, Souv. Handsch. +1 | the same (the +1 abjuration keeps its abbreviation) |
| Eschite Breastplate | Eschite Breast. |
| Odyssean Chestplate | Odyss. Chestplate (the body the Phalanx SIRD set wants) |

The guide's *Phalanx (Ideal)* set is not carried as a third Phalanx leaf: Max Self
Phalanx subsumes it. The docs keep the comparison above.

## Odyssean gear is Oseem work

The Odyssean pieces in the sets are not fixed-stat items: their value is
[Oseem's Arcane Glyptics](https://www.bg-wiki.com/ffxi/Category:Escha_Rewards/Arcane_Glyptics_Inscription)
at Norg (I-7). The base Reisenjima piece carries its own line (Odyssean Greaves already
has Fast Cast +5, Cure potency +7% and Spell interruption rate down 20%), and the rolled
augments sit on top. The guide names the rolls it wants, so `PLD.lua` carries them as the
usual GearSwap `{ name = ..., augments = {...} }` tables in a local `oseem`:

| Local build | Base piece | Roll | Set |
|---|---|---|---|
| `oseem.helm_phalanx` | Odyssean Helm | `"Phalanx"+5` | `midcast.Phalanx` (Max Self) |
| `oseem.chest_phalanx` | Odyss. Chestplate | `"Phalanx"+5` | `midcast["Phalanx SIRD"]` |
| `oseem.feet_phalanx` | Odyssean Greaves | `"Phalanx"+5` | `midcast["Phalanx SIRD"]` |
| `oseem.feet_stoneskin` | Odyssean Greaves | MND+3, Accuracy+2, Attack+2, Spell interruption rate down-11% | `midcast["Enhancing Magic Stoneskin"]` |
| `oseem.feet_cure` | Odyssean Greaves | `"Cure Potency"+5%` | `midcast["Cure SIRD"]` |
| `oseem.feet_fastcast` | Odyssean Greaves | `"Fast Cast"+6` | `midcast["Reprisal SIRD"]` |

Which stone gets which row matters:

- **Phalanx +1–5 and the SIRD-11 are Dark Matter ("technique") rolls.** They are not in
  the standard Melee/Magic path tables, so the launcher's **Oseem · Arcane Glyptics** card
  cannot inscribe them yet; the library carries the line for GearSwap and the stat sheet
  decodes `0x170` (Phalanx) and `0x035` (Spell interruption rate down) when an item does
  carry them.
- **Cure Potency +5 (Fern 6), Fast Cast +6 (Fern), MND/Accuracy/Attack** are the standard
  Magic path rows, so the Oseem card writes those.
- The gear page shows an augmented build as `*` and lists the roll under the item; **Wear
  set** matches the base name, as it does for capes and the R30 sets.
- The database has no `item_mods` rows for the five Odyssean pieces yet (Herculean and
  Merlinic do have rows), so their fixed base lines — the Greaves' 20% SIRD, Fast Cast +5
  and Cure potency +7% in particular — are in the client tooltip and therefore in the Gear
  page's Set totals, but not in the server's Live set stats. That is an item-data gap,
  separate from the rolls above.

A Wear set only finds items in bags 0–17. Most library pieces live in the Mog Locker or a
storage slip on a developed account, so run `//storage grab pld` (or `//storage organize`)
before expecting the swap to fire; the launcher reports anything it cannot find.
Migration `0190_pld_spell_gear.sql` hands the 39 new pieces to Onedough (1) and the Paladin
character Fivedough (5) into free wardrobe slots, skipping anything already owned in the
bags, the locker or a storage slip, so the sets are wearable on the next server start and
the next zone/relog after it.

## Sets at a glance

| Set | Guide name | Core pieces |
|---|---|---|
| `midcast.Flash` | Flash | Sapience Orb, Loess Barbuta +1, Rev. Surcoat +4, Cab. Gauntlets +4, Cab. Breeches +4, Chev. Sabatons +3, Kgt. Beads +2, Trux/Cryptic Earring, Vexer Ring +1, Eihwaz Ring, Creed Baudrier, Rudianos's Mantle |
| `midcast["Flash SIRD"]` | Flash SIRD | Staunch Tathlum +1, Souv. Schaller +1, Chev. Cuirass +3, Cab. Gauntlets +4, Founder's Hose, Chev. Sabatons +3, Moonlight Necklace, Alabaster/Cryptic Earring, Vexer Ring +1, Eihwaz Ring, Audumbla Sash, Rudianos's Mantle |
| `midcast["Healing Magic"]` | Cure | Egoist's Tathlum, Chev. Armet +3, Souv. Cuirass +1, Souv. Handsch. +1, Sworn Brais, Chev. Sabatons +3, Kgt. Beads +2, Alabaster Earring, Nourish. Earring +1, Moonlight Ring ×2, Sroda Belt, Rudianos's Mantle |
| `midcast["Cure SIRD"]` | Cure (SIRD) | Staunch Tathlum +1, Souv. Schaller +1, Souv. Cuirass +1, Macabre Gaunt. +1, Founder's Hose, Odyssean Greaves (Cure Potency+5), Moonlight Necklace, Alabaster Earring, Nourish. Earring +1, Moonlight Ring ×2, Audumbla Sash, Rudianos's Mantle |
| `midcast.Phalanx` | Max Self Phalanx | Sakpata's Sword, Priwen, Odyssean Helm (Phalanx+5), Sworn Platemail, Souv. Handsch. +1, Sakpata's Cuisses, Souveran Schuhs +1, Hoxne Torque, Mimir/Andoaa Earring, Olympus Sash, Weard Mantle |
| `midcast["Phalanx SIRD"]` | Phalanx SIRD | Staunch Tathlum +1, Souv. Schaller +1, Odyss. Chestplate (Phalanx+5), Souv. Handsch. +1, Founder's Hose, Odyssean Greaves (Phalanx+5), Moonlight Necklace, Mimir/Tuisto Earring, Moonlight Ring ×2, Audumbla Sash, Weard Mantle |
| `midcast.Reprisal` | Reprisal | Sapience Orb, Loess Barbuta +1, Shab. Cuirass +1, Regal Gauntlets, Cab. Breeches +4, Chev. Sabatons +3, Kgt. Beads +2, Cryptic/Alabaster Earring, Moonlight/Murky Ring, Creed Baudrier, Rudianos's Mantle |
| `midcast["Reprisal SIRD"]` | Reprisal (SIRD) | Sapience Orb, Souv. Schaller +1, Shab. Cuirass +1, Regal Gauntlets, Founder's Hose, Odyssean Greaves (Fast Cast+6), Moonlight Necklace, Cryptic/Alabaster Earring, Moonlight/Murky Ring, Audumbla Sash, Rudianos's Mantle |
| `midcast["Enhancing Magic Stoneskin"]` | Capped Stoneskin and SIRD | Staunch Tathlum +1, Souv. Schaller +1, Chev. Cuirass +3, Stone Mufflers, Haven Hose, Odyssean Greaves (MND+3/Acc+2/Atk+2/SIRD-11), Stone Gorget, Knightly/Earthcry Earring, Evanescence/Murky Ring, Siegel Sash, Rudianos's Mantle |
| `midcast.Enspell` | Enlight Set 3 | Brilliance, Jumalik Helm, Rev. Surcoat +4, Eschite Gauntlets, Incanter's Torque, Knight's/Saxnot Earring, Stikini Ring +1 ×2, Asklepian Belt, Altruistic Cape |
| `precast.FC` | High HP Capped Fast Cast | Sapience Orb, Carmine Mask +1, Rev. Surcoat +4, Leyline Gloves, Sworn Brais, Chev. Sabatons +3, Orunmila's Torque, Enchntr./Loquac. Earring, Kishar/Prolix Ring, Plat. Mog. Belt, Rudianos's Mantle |
