# Bard songs

Fanxi has a playable bard-song layer with the retail song-slot, instrument and
Nitro/Soul Voice rules.

## What exists

- Songs land on the caster and nearby party members (10-yalm party radius), each with
  its own action and status packet.
- Song values:
  - Minne: Defense, per tier
  - Minuet / Mambo: Attack, per tier
  - Madrigal: Accuracy
  - March: magic Haste
  - Ballad: Refresh
  - Paeon: Regen
  - Requiem: damage-over-time
  - Prelude: Ranged Accuracy
  - Carol: Magic Defense
  - Etude: the named stat
- Song plus gear: `All songs +N` (mod 452) adds to every song, the family Song+ rows
  (mods 433-451) add to that line, and each Song+ point also lengthens the song by
  10% (see the timer bullet below); the explicit Song duration lines (454) are
  additive with that.  Song spellcasting time (455) shortens the song cast, and the
  reforged +3/+4 pieces now carry their tooltip values (migration 138) instead of
  losing them in the item importer; Oboro path C's `Song spellcasting time` is parsed
  from the augment block.
  Song recast delay (833) is stored, but the client still owns the recast bar.  The Bard
  job-point **Song Effect Duration** gift adds another +5%, and **Song Spellcasting
  Time** adds -5% cast time to songs only.  Job-point Minne/Minuet/Requiem/Lullaby rows
  are applied as before.
- **Song potency follows BG-wiki's tables.**  `data/song_potency.json` carries the
  per-Song+ values for each song (Attack, Defense, Accuracy, magic haste, the
  refresh/regen/Requiem ticks and Aria's damage limit), from
  [BGWiki:SongPotency](https://www.bg-wiki.com/ffxi/BGWiki:SongPotency); they assume
  capped song skill.  `All songs` plus the song's family row index the table, so
  Minuet V is 124 at +0 and 223 at +8, and Victory March is 15.92% / 28.61%.
  After the percentage the family's Bard group-1 merit and job-point row are added
  flat (Minuet +5 merit and +20 JP, Minne +10 and +20, Madrigal +5, Requiem +60 on
  its DoT), and only then do Soul Voice and Marcato multiply the lot: the wiki's
  worked example, Minuet V at +8 with 5/5 and 20/20 under Marcato, is +372 Attack.
  `//songs` prints each song's remaining time and the value it is applying.
- **The song timer.**  One timestamp, built as
  `120 × (1 + (454 + 10 × Song+ + 5) / 100)`, doubled while Troubadour is up, then
  `+40` for Clarion Call, `+40` for Tenuto and `+20` for Marcato.  Song+ is
  `All songs` plus the family row for that song, and each point is worth 10%
  duration, so Loughnashade's `All songs +4` is +40% and `Mnbw. Whistle +1`'s +3 is
  +30% even though neither carries a "Song duration" line.  Those two terms are
  additive; Clarion Call is a flat number, not a multiplier.  Tenuto (5 s recast),
  Marcato (10 min) and Pianissimo are spent by the next song whether or not it
  lands; Troubadour (60 s) and Clarion Call (180 s) stay up.  The best five-song
  loadout is 96 from the 454 lines plus 7-8 Song+ points (Carnwenhan, Loughnashade,
  Fili Hongreline +3, Inyanga Shalwar +2, Brioso Slippers +4, Mnbw. Whistle +1 and
  a family piece), for 171-181%; Marsyas trades Loughnashade's +40% for +50% and
  gives 191% at the cost of the two Maximum-songs slots.
- **Song slots follow retail.**  A Bard main with an instrument keeps two songs; the
  Bard support job or an empty ranged slot keeps one.  Daurdabla and Loughnashade add
  two (`Maximum songs bonus`, mod 453), and Clarion Call adds the fifth.  A new song
  replaces the active song with the least time left; the same song cannot refresh while
  more than its unenhanced 120 s remains.
- **The song list survives a dropped link.**  A disconnect is a relog to the client, so
  the server writes the active songs, their timers and their values to `char_live_state`
  and the next login puts them back on the bar in the same slot order.  Time spent offline
  counts against the timer, and the "Welcome back" line names the song with the least time
  left.  A deliberate `/logout` is the exception: it takes the songs with it, the way retail
  does.  See [world](world.md#recovering-a-dropped-client).
- **Different songs stack even when they share an icon.**  Victory March, Advancing
  March and Honor March all use the March icon (214), and the Paeon/Minne tiers share
  195/197, but each spell is tracked separately.  They each take a song slot and their
  modifiers add; the same counts for every Paeon or Minne version until the song cap is
  reached.  Paeon and Ballad ticks from every active version also add.
- **Nitro** is Nightingale + Troubadour.  Nightingale halves the song cast, Troubadour
  casts at 150% and doubles the final duration.  Soul Voice doubles a song's potency,
  and doubles the duration of Hymnus, Mazurka and Sentinels Scherzo.  Marcato is a 1.5x
  effect (and 1.5x duration for those three songs) and does not stack with Soul Voice.
  The Clarion Call / Tenuto / Marcato job-point seconds are added after Troubadour.
- **Instrument songs.**  Honor March requires Marsyas and Aria of Passion requires
  Loughnashade.  The server refuses the cast without the instrument, and it reads the
  ranged slot when the **cast packet arrives** -- not when the song resolves.  So the
  instrument can come back off mid-cast: `precast.Song` holds Loughnashade for Aria of
  Passion and `precast.FCHonor` holds Marsyas for Honor March, and the midcast set then
  swaps in whichever instrument the timer wants (Marsyas for Honor March, Loughnashade
  for everything else).  The control addon also equips the required instrument itself
  before replaying a `/ma` for either song.
- The two instrument-granted songs are covered by the HUD's song map: **Honor March**
  (Marsyas, Aeonic) groups with March and **Aria of Passion** (Loughnashade, Prime)
  groups with Attack.  They read `HONOR` and `PASSION` on the tiles.

## Per-song maximum sets

The phase engine now selects a family set automatically for every Bard song,
so the +7 common baseline from Loughnashade (+4) and Mnbw. Whistle +1 (+3) is
extended by the family pieces the character owns:

| Songs | Song+ | Set | Notes |
|---|---:|---|---|
| Paeon | +9 | `midcast.SongPaeon` | Brioso Roundlet +4 head; 96% raw duration retained |
| Lullaby | +9 | `midcast.SongLullaby` | Brioso Cuffs +4 hands; Pemphredo/Rhapsode for Macc |
| Etude | +9 | `midcast.SongEtude` | Mousai Turban +1 head |
| Carol | +9 | `midcast.SongCarol` | Mousai Gages +1 hands |
| Threnody | +9 | `midcast.SongThrenody` | Mou. Manteel +1 body; 82% raw + Song+ net |
| Minne | +9 | `midcast.SongMinne` | Mou. Seraweels +1 legs; 79% raw + Song+ net |
| Mambo | +9 | `midcast.SongMambo` | Mou. Crackows +1 feet; 81% raw + Song+ net |
| Madrigal, Minuet, March | +8 | `SongMadrigal`, `SongMinuet`, `SongMarch` | the family piece is already in the all-duration set |
| Ballad, Scherzo | +7 | `SongDuration` | their only family pieces are legs/feet; +1 Song+ there costs 17/15 raw duration, so the +8 version would be shorter |
| all others | +7 | `SongDuration`/`Song` | maximum duration baseline |

For the body/legs/feet swaps, one Song+ point is worth 10% duration, so the +9
Threnody/Minne/Mambo sets still last longer than the +7 all-duration set despite
giving up 14/17/15 raw 454 points.

The launcher's Gear page must be reloaded after the library changes, and the
host's `control.lua` must be reloaded (relaunch the client) for the automatic
family routing to take effect.

## Spells HUD modes

The Spells HUD has a **Bard songs** group with two modes:

- **Song duration** — `sets.midcast.SongDuration` (Loughnashade + every 454 piece and
  Song+ point, 171-181%).
- **Song potency** — `sets.midcast.SongPotency`.  Song+ is duration as well, so the
  duration loadout also maximises the song values and the two modes now use the same
  set.

`midcast.SongHonor` is the Marsyas loadout for Honor March (191%), and `midcast.SongAria`
is the Loughnashade set, which is both what Aria of Passion requires and the best
duration instrument.  `BRD-review.md` next to the library carries the full timer table.

`//modes songs duration` and `//modes songs potency` switch the armed mode.  The
**Song overrides** card in the launcher (and the spell override section) lists only
Bard songs and lets each song pick its own precast and midcast set.  Spell precast and
song precast are separate: `precast.Spell` is worn before every spell, and
`precast.Song` only for songs.  Honor March and Aria of Passion ignore the armed mode
and use `SongHonor` / `SongAria`; keep the Honor March override pointing at
`precast.FCHonor` / `midcast.SongHonor` so Marsyas is on for the cast check.

## Still missing

- The full song-accuracy/instrument-skill model.
- Party/alliance targeting nuances beyond the 10-yalm party radius.
- Song recast enforcement (the client still owns the 24 s recast bar).
