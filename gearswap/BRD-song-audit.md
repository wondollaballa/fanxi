# Bard song audit — retail vs Fanxi

Deep dive into every song family against BG-wiki, compared with
`server/fanxi_server/game/effects.py`, `data/song_potency.json` and the song paths in
`zone.py`. Minuet and March are the reference (they were the two already fixed) and
are only listed where they still matter.

Sources:

- [BGWiki:SongPotency](https://www.bg-wiki.com/ffxi/BGWiki:SongPotency) — the per-Song+
  table for all 105 song spells, and the notes under each family.
- The individual spell pages (`Foe Lullaby`, `Sentinel's Scherzo`, `Fire Threnody`,
  `Fire Carol II`, `Pining Nocturne`, `Foe Sirvente`, `Adventurer's Dirge`,
  `Goddess's Hymnus`, `Chocobo Mazurka`, `Maiden's Virelai`, `Magic Finale`,
  `Battlefield/Carnage Elegy`, `Sinewy Etude`, `Aria of Passion`, …) for duration,
  recast and the effect itself.
- [Category:Requiem](https://www.bg-wiki.com/ffxi/Category:Requiem) for the Requiem
  job-point ordering and worked examples.

## How retail computes a song

1. **Base per tier** from the family's table at Song+ 0 (assumes capped song skill).
2. **+10% of base per Song+ point** — All Songs plus the family row, clamped at the
   table's last column.
3. **Bard group-1 merit** (+1 a rank for Minuet/Madrigal, +2 for Minne) and the
   **job-point row** (+20 Minuet/Minne, +60 Requiem DoT), added flat.
4. **Soul Voice ×2 / Marcato ×1.5** last — except Requiem, whose job points are added
   *after* the multiplier (worked examples: `(14 × 1.5) + 60 = 81`, `(14 × 2) + 60 = 88`).
5. **Song+ also lengthens the song** by 10% a point (this part we already do).
6. **Skill**: every table is "skill cap X" — below the cap the value is lower. Dirge and
   Mazurka ignore Song+ for potency. Hymnus/Mazurka/Scherzo get *duration* from Soul
   Voice/Marcato, not potency.

Our implementation now does 1-2 for the 69 songs the JSON covers, 3 for
Minuet/Minne/Madrigal and Requiem, 4 with the Requiem exception wrong (see below), and
5. It does not model 6 at all (song skill is a documented gap).

## Where we are right

| Family | State |
|---|---|
| Minuet, Minne, Madrigal | base, Song+ scaling, merit + job-point order — matches the wiki worked example (+372) |
| March (Advancing/Victory/Honor) | haste table, Song+ scaling |
| Ballad II/III | refresh tick table (Ballad I has no row, but the fallback lands on the same numbers) |
| Paeon I–VI | HP tick table |
| Etude | stat table (9 at +0 → 18 at +9) |
| Aria of Passion | physical damage limit table, 2 min |
| Durations | 2-minute buffs, Lullaby 0:30 / 1:00, Threnody 1:00 / 1:30, Elegy 2:00 / 3:00, Carol 2:00 all match the pages |

## Fixed in this pass

| Family | Retail | Now |
|---|---|---|
| **Sentinel's Scherzo** | damage taken **−45%** at +0, −53% at +8 (skill cap 800) | the row is written to the uncapped pair `UDMGPHYS`/`UDMGMAGIC` (−4500…−5300): retail treats Scherzo as its own multiplier, not part of the 50%-capped PDT/DT family, so `damage_taken` is 55%…47%. In game `//songs` shows "Damage taken −52%" with the SongPotency set |
| **Threnody** (18 spells) | elemental **Magic Evasion down** 50 (I) / 160 (II) | the value is stored on the mob as the hidden `MAGIC_EVASION_DOWN` effect, which `world.monster_debuff_mods` already reads; the Threnody icon still shows |
| **Elegy** | **Attack Speed down** 25% (Battlefield) / 42.48% / 50% (Carnage) | stored on the mob as `SLOW` with that potency; the existing swing-delay code multiplies the mob's delay by 1 + potency/100 |
| **Carol** | elemental **resistance** +80 (I) / +100 (II) on the matching element, plus 15% damage nullification at II | mapped to the element's `*_MEVA` id (Fire Carol → `FIRE_MEVA`), and the eight **Carol II** spells are now built from the table even though they are missing from the generated status list |
| **Mambo** | **Evasion** +48 (Sheepfoe) / +72 (Dragonfoe) | the table row is used; the old Attack heuristic is gone |
| **Prelude** | **Ranged Accuracy** only | only `racc` — the table generator no longer double-maps "Ranged Accuracy" to melee |
| **Nocturne** | enemy **Magic Accuracy** down, 2–4 min | `macc` row (not melee accuracy) |
| **Ballad I** | 1 MP a tick at +0 | its own row is in the data now |
| **Magic Finale** | dispels one buff | a `special` spec routes it through `world.dispel_mob`, the same path Dispel uses |
| **Pianissimo** | the next song lands on the chosen party member only | `song_targets` narrows the party radius to that member while the status is up; a unit test pins it |
| **Song Accuracy Bonus** (JP) | +1 song accuracy a rank, +20 at 20/20 | was feeding generic Magic Accuracy to every spell; now it is added to the singing skill for songs only |
| **Goddess's Hymnus** | Reraise, 2 min | the song lands with its own icon (218) and grants the Reraise effect; `hit_zero_hp` consumes it and revives at 10% HP (also fixes the White Mage Reraise spell, which had never been consumed) |

## Still off

| Family | Retail | Ours |
|---|---|---|
| **Nocturne's debuff** | lowers the mob's Magic Accuracy | the value is right, but this server's monsters do not cast through a magic-accuracy check yet, so there is nothing to lower |
| **Mazurka** | movement speed, 2 min, recast **60 s** | no movement modifier exists in the engine; the spell lands with no effect (recast is client-side anyway) |
| **Virelai** | Charm 30 s, recast 60 s | no charm/pet model for a charmed monster |
| **Sirvente / Dirge** | enmity loss −35% / enmity −32, 2 min | `song_family` doesn't know either name and the hate model has no enmity modifier to write |
| **Aubade / Pastoral / Fantasia / Operetta / Capriccio / Round / Gavotte** | status resistance (sleep, poison, blind, curse, silence) | the wiki lists **no potency** for them ("unknown potency"), and the modifier pool has elemental `*_MEVA` but no status-resistance ids — blocked on both data and engine |
| **Song skill (potency caps)** | every table's value assumes the song's skill cap (Minuet V 871-874, Scherzo 800, Etude ≥450 …); below it the song is weaker | not modelled: the wiki publishes the caps but no below-cap values, so our songs always use the capped column |
| **Song accuracy** | singing skill + Song Accuracy gear/JP vs the target's Magic Evasion | modelled by the shared magic-accuracy roll (singing skill + the +20 JP row, now song-only) |

## Off — values, ordering and data

1. ~~**Requiem's job points are on the wrong side of Soul Voice/Marcato.**~~ Fixed:
   the +60 DoT row is added after the multiplier again, so Marcato Requiem VII is
   `(14 × 1.5) + 60 = 81` and Soul Voice is `(14 × 2) + 60 = 88`, matching the wiki
   examples. `test_bard_songs.py` asserts the 81.
2. ~~**Lullaby's +20 job-point seconds never applied.**~~ It was worse than ordering:
   the row was gated on `spec.effect == 193`, but our Lullaby's effect is 2 (Sleep),
   so the +20 was dead code. It now goes through `song_duration(flat_seconds=...)`:
   gear first, then the seconds, then Troubadour's doubling — Foe Lullaby is 51 s
   without the row, 71 s with it, 142 s under Troubadour.
3. **Carol II** has a table (100 resistance, 15% nullify) but the spells are not in
   `spell_effects.STATUS_SPELLS`, so they get no mods.
4. **Mambo, Threnody, Elegy, Sirvente, Dirge, Hymnus, Mazurka, Virelai, Finale and the
   seven utility songs** are among the 36 of 105 wiki songs with no row in
   `data/song_potency.json` — the generator only keeps songs whose stats map to a
   modifier we have.
5. **Phantom spells.** `Army's Paeon VII/VIII` and `Foe Requiem VIII` are in our spell
   table but not on the wiki (Paeon stops at VI, Requiem at VII); they do nothing
   (`tick=0`). Either they are private-server additions or bad rows.
6. **Label mapping bugs** in the song-table generator: "Ranged Accuracy" matched the
   generic accuracy rule (Prelude), "Magic Accuracy" matched it too (Nocturne), and
   "Elemental Resistance" was mapped to MDEF (Carol).
7. **Song skill is not modelled.** Every table is "skill cap X" (Minuet V 871-874,
   Carol ≥900, Scherzo 800, Etude ≥450 …); a bard under the cap sings weaker songs.
   The docs list this as a known gap, but it also means the caps in our tables are
   ceilings, not what a mid-geared bard gets.
8. **Song accuracy / instrument skill** is not modelled either (wiki: song accuracy
   from skill and gear).

## Priority

Done: Scherzo, Threnody, Elegy, Carol (+Carol II), Mambo/Prelude/Nocturne stats,
Requiem and Lullaby job-point order, Ballad I, Finale, Hymnus (and the Reraise death
hook that the White Mage spell was missing).

Blocked on engine features rather than song data:

1. **Nocturne's Magic Accuracy** — monsters do not resolve spells through a magic
   accuracy check yet.
2. **Mazurka** — no movement-speed modifier.
3. **Virelai** — no charm/pet model for a charmed monster.
4. **Sirvente/Dirge** — no enmity modifier in the hate model.

Left:

5. **Aubade / Pastoral / Fantasia / Operetta / Capriccio / Round / Gavotte**.
6. Song skill (potency caps) and song accuracy, then re-check every table's cap.
7. Data hygiene: drop or justify Paeon VII/VIII and Requiem VIII.

## How to re-check

`//songs` prints each active song with its value, and `server/tests/test_songs.py`
pins the tables and the wiki's Minuet example. A family is "verified" when the wiki
row, the merit/JP note and the ordering all have a test.
