# BRD audit — Onedough

Checked against the old Windower file (`BRD (1).lua`), the server's own timer
(`server/fanxi_server/game/effects.py`, `song_duration`) and real casts in a
headless session.

## The real cause: Song+ was not counting toward duration

Retail's rule (BG-wiki, [Song § Song Effect Duration](https://www.bg-wiki.com/ffxi/Song)):

> Song+ potency gear increases duration by 10% per 1 Song+. All gear song effect
> duration bonuses are additive with each other, as well as additive with the
> duration increase from song+ potency effects.

Fanxi was applying only the literal "Song duration +N%" lines (mod 454) and
ignoring the Song+ part. That is exactly why your old file is full of numbers like
`Loughnashade → mult + 0.4`, `Mnbw. Whistle +1 → +0.3` and `Brioso Cuffs +3 →
+0.2`: those pieces have no duration line, they have **All songs +4**, **All songs
+3** and **Lullaby +2**. Ten percent per point, and the engine was dropping 70% of
your song timer.

The old set (`sets.midcast.SongEnhancing`) was:

| Piece | 454 | Song+ | Effective |
|---|---:|---:|---:|
| Carnwenhan | +50 | — | +50 |
| Loughnashade | — | All songs +4 | +40 |
| Mnbw. Whistle +1 | — | All songs +3 | +30 |
| Fili Hongreline +3 | +14 | Minuet +1 | +14 (Minuet: +24) |
| Inyanga Shalwar +2 | +17 | — | +17 |
| Brioso Slippers +4 | +15 | — | +15 |
| job-point gift | +5 | — | +5 |
| **total** | **101** | **7** | **171–181%** |

Fanxi was using the 101. At 101% and Troubadour that is `120 × 2.01 × 2 = 482 s =
8:02` — the eight minutes you kept hitting. At 171–181% it is **10:50–11:14 under
Troubadour alone**, which is your retail number.

The fix is in the server, not the library:

- `effects.song_duration_percent` now returns `454 + 10 × Song+`, where Song+ is
  All Songs plus that song's family row.
- `song_duration`, `buff_duration` and `debuff_duration` all use it, so party
  songs, Lullaby/Requiem and Trust songs agree.
- `battle_song_catalog` passes the whole modifier block instead of just 454, so the
  Battle hub's per-song timers are the real ones.

The item data was right all along: Loughnashade and Mnbw. Whistle +1 genuinely have
no 454 line. Nothing needed adding to the database.

## Cause 2: the midcast set came off before the song landed

The phase engine put the return (idle) set back **6 seconds** after an action that
had not produced a result packet yet. A bard song is 8 s on its own and 12 s under
Troubadour's 1.5x cast, so the song landed *after* the engine had already swapped
to `idle.dt` and its duration rolled off the idle gear. Fixed in
`host/addons/phase.c`: `PHASE_STALE_MS` is 30 s now.

That is why the old eight minutes matched `idle.dt` exactly: 79 from 454, no Song+
from the retired Loughnashade line, +5 gift = 84%, `120 × 1.84 × 2` = 7:22, +40
Tenuto = 8:02.

## The formula now

```
duration = 120 s
         × (1 + (454 + 10 × Song+ + 5 job-point gift) / 100)
         × 2       while Troubadour is up
         × 2 / 1.5 while Soul Voice / Marcato is up (Scherzo, Hymnus, Mazurka only)
         + 40      Clarion Call         (3 min status, 1 h recast)
         + 40      Tenuto               (5 s recast, spent by the next song)
         + 20      Marcato              (10 min recast, spent by the next song)
```

## What changed in the library

| Set | Before | Now |
|---|---|---|
| `midcast.SongDuration` | Loughnashade · 105% | **Loughnashade · 96 + 8 Song+ = 181%** for a March |
| `midcast.Song` | Loughnashade · 106% | same loadout |
| `midcast.SongAria` | Loughnashade · 63% | same loadout |
| `midcast.SongHonor` | Marsyas · 155% | **Marsyas · 146 + 4 Song+ = 191%** |
| `midcast.SongPotency` | lost 32% of duration | same loadout (see below) |
| neck | Aoidos' Matinee (+10) | **Mnbw. Whistle +1 (+30)** |
| hands | Bihu Cuffs / Brioso Cuffs | **Fili Manchettes +3** ("March"+1 = +10% on every March) |

- **Loughnashade is back in the range slot.** All songs +4 beats Daurdabla's +30%
  and both carry Maximum songs +2, so five songs still fit.
- **Potency and duration are the same loadout now.** The old potency set swapped
  Inyanga (17%) and Brioso Slippers (15%) for `"Ballad"+1` and `"Scherzo"+1`
  (10% each, one family only), so it was strictly worse once Song+ counts.
- **Marsyas stays for Honor March** because Honor needs it at cast start, and +50
  beats +40. It has no song slots, so sing Honor first; it reaches 12:18 with
  Troubadour + Tenuto and 13:18 with the full kit.
- The song precast sets still hold the cast-time instrument (`precast.Song` →
  Loughnashade for Aria, `precast.FCHonor` → Marsyas), because the server checks
  the instrument when the cast packet arrives.

## Timers these sets produce

Measured through the server with the new formula, not hand-computed:

| Set | Troubadour | + Tenuto | + Clarion Call | + Marcato |
|---|---:|---:|---:|---:|
| Loughnashade, March/Minuet/Madrigal (181%) | **11:14** | 11:54 | 12:34 | **12:54** |
| Loughnashade, other songs (171%) | 10:50 | 11:30 | 12:10 | 12:30 |
| Marsyas, Honor March (191%) | 11:38 | 12:18 | 12:58 | **13:18** |
| Aria of Passion (171%) | 10:50 | 11:30 | 12:10 | 12:30 |

**Verified in game** (server restarted on this code, client on the rebuilt
`host64`, plan pushed with your saved modes): Victory March with Troubadour +
Tenuto landed with the `SongDuration` set on and the buff icon dropped
**722.4 s after the cast command** — 8 s of cast bar plus **714.4 s (11:54)** of
song, which is the 181% row above to the second.

## What the songs give

Duration was only half the story. Song **potency** was a hand-written `10 x tier`
model, so the numbers were roughly a third of retail's. It now comes from BG-wiki's
per-Song+ tables (`data/song_potency.json`) with the Bard group-1 merit and the
job-point row added after the percentage and before Soul Voice/Marcato:

| Song (SongDuration set, Song+ 7-8) | before | now |
|---|---:|---:|
| Valor Minuet V | +58 Attack | **+248** |
| Valor Minuet IV | +48 | **+226** |
| Valor Minuet III | +38 | **+197** |
| Knights Minne V | +58 Defense | **+366** |
| Sword Madrigal | +13 Accuracy | **+86** |
| Victory March | 14.00% haste | **28.61%** |
| Honor March (Song+ 4) | 16.00% / +232 Attack | **16.99% / +232** |
| Mage's Ballad III | 10 MP/tick | 10 MP/tick |
| Army's Paeon V | 10 HP/tick | **14 HP/tick** |
| Aria of Passion | 22.1% damage limit | 22.1% |

The three Minuets alone are +671 Attack now (they were +144), and Minuet V at +8
with 5/5 merits, 20/20 job points and Marcato is +372 — the worked example on the
wiki's Minuet page. `//songs` prints the list with each song's remaining time and
the value it is applying.

- Sentinels Scherzo, Hymnus and Mazurka also take Marcato's 1.5× duration:
  **17:55** for Scherzo with Clarion + Troubadour + Tenuto + Marcato, and **21:40**
  with Soul Voice + Troubadour (**23:00** with Clarion and Tenuto as well).
- 96 from the 454 lines plus 8 Song+ points is the ceiling while keeping five
  songs. Marsyas (191%) is the single-song ceiling and costs three of the slots.

## Job points — what Fanxi applies

- **Song Effect Duration** gift: +5%, folded into the 454 total. ✔
- **Clarion Call Effect** 2 s × 20 ranks = +40 s while Clarion Call is up. ✔
- **Tenuto Effect** 2 s × 20 = +40 s, **Marcato Effect** 1 s × 20 = +20 s. ✔
- Those three rows are added **after** Troubadour here. Your old file doubled them
  under Troubadour (it adds `clarion_call_effect * 2 * 2`), which would make a
  Clarion song +80 instead of +40. That only matters in the one hour a Clarion is
  up, and it is not what was capping you, so it is left alone; say the word if you
  want the seconds moved inside the doubling.
- The JP categories only fire while their ability is up, so no-JA songs are pure
  gear — which is the 11:14 above.

## Rotation

1. **Honor March first** with Marsyas: 11:38 plain, 12:18 with Tenuto, 13:18 with
   everything. Recasting an active Honor is a refresh and does not evict.
2. **Troubadour** (60 s, 10 min recast); **Clarion Call** when it is up (3 min).
3. **Tenuto before every song** (5 s recast, +40 s each).
4. The rest with `SongDuration` (Loughnashade): 11:14 for marches/minuets, 10:50
   for the others.
5. Marcato is worth most on Scherzo (17:55) or on whichever song you cannot fit
   into a re-sing.

Five songs still fit in Troubadour's 60-second window at 44% song cast time.

## Set review

- 42 sets, no paths added or renamed; the saved Bard songs mode and the
  `SongHonor` / `SongAria` category picks still resolve.
- `sets.JA.*` are cosmetic on this server: no job ability reads gear. They stay as
  they were.
- The four `sets.WS.*` entries still share the Nyame/Fotia template and
  `sets.Odyssey.nyame_a..d` are identical because Fanxi stores item names, not
  augments.

### Old-file findings (unchanged)

- **Missing sidecar.** The uploaded file references `gear.Linos_WS`,
  `gear.Chironic_WSD_head`, `gear.Chironic_WSD_hands`, `gear.Chironic_QA_feet`,
  `gear.Telchine_ENH_*` and `gear.Telchine_STP_hands` but does not define them.
- **Nested variants cannot flatten.** `sets.idle.DT`, `sets.precast.FC.BardSong`,
  `sets.precast.WS.Evisceration`, etc. sit under tables that also contain slot
  values, so Fanxi stops descending. The library uses sibling paths instead.
- **Two invalid entries.** `Metamor. Ring +1` is not an item name (the item is
  `Metamorph Ring +1`), and `sets.midcast['Foe Sirvente']` has `head = "+"`.
- **Old Lullaby timer.** `get_lullaby_duration` checks Brioso Cuffs +1/+2/+3 but
  not +4.

## Items you are missing

Nothing for song duration — the four pieces the first pass listed (Marsyas,
Aoidos' Matinee, Inyanga Shalwar +2, Mnbw. Whistle +1) are granted by migration
`0137_bard_song_gear.sql` and all four are worn now.

### Old-file extras not owned (optional)

**Instruments and weapons (9)**
Kali · Linos · Taming Sari · Centovente · Genmei Shield · Blurred Harp +1 ·
Ammurapi Shield · Shinjutsu-no-Obi +1 · Hachirin-no-Obi

**Song / duration (9)**
Aoidos' Earring · Fili Earring (or Fili Earring +2) · Inyanga Tiara +2 ·
Inyanga Jubbah +2 · Mousai Gages +1 · Mousai Turban +1 · Mou. Crackows +1 ·
Mou. Seraweels +1 · Mou. Manteel +1

> The three `Mou.` names are the client's 15-character item names for the Mousai +1
> body/legs/feet pieces (`Mou. Crackows +1` is 25969, `Mou. Seraweels +1` is 25902,
> `Mou. Manteel +1` is 26538).

**Fast cast / idle / defense (36)**
Chironic Hat · Chironic Doublet · Chironic Gloves · Chironic Slippers ·
Kaykaus Mitra +1 · Kaykaus Bliaut +1 · Kaykaus Cuffs +1 · Kaykaus Tights +1 ·
Kaykaus Boots +1 · Bunzi's Hat · Bunzi's Sabots · Volte Tiara · Volte Tights ·
Volte Spats · Ayanmo Corazza +2 · Ashera Harness · Lebeche Ring · Medada's Ring ·
Siegel Sash · Gishdubar Sash · Grapevine Cape · Nodens Gorget · Emphatikos Rope ·
Sheltered Ring · Cohort Cloak +1 · Aurist's Cape +1 · Fi Follet Cape +1 ·
Eabani Earring · Sanare Earring · Moonlight Ring · Moonlight Cape · Bathy Choker +1 ·
Nicander's Necklace · Reiki Yotai · Acuity Belt +1 · Gazu Bracelets +1

**Cure / status — old /WHM sets only (22)**
Vanya Hood · Vanya Robe · Vanya Clogs · Aya. Cosciales +2 · Aya. Zucchetto +2 ·
Beatific Earring · Meili Earring · Menelaus's Ring · Haoma's Ring · Bishop's Sash ·
Metamorph Ring +1 · Nuna Gorget +1 · Luminary Sash · Hieros Mittens ·
Debilis Medallion · Oretan. Cape +1 · Mendi. Earring · Andoaa Earring ·
Mimir Earring · Eshmun's Ring · Evanescence Ring · Magnetic Earring ·
Rumination Sash

**Weaponskill / TP accessories (12)**
Ishvara Earring · Regal Earring · Regal Ring · Sailfi Belt +1 · Kentarch Belt +1 ·
Baetyl Pendant · Argocham. Mantle · Blistering Sallet +1 · Zoar Subligar +1 ·
Mache Earring +1 · Brutal Earring · Shukuyu Ring

**Other (3)**
Darkside Earring · Gersemi Earring · Loricate Torque +1

## Re-checking it yourself

```
python3 tools/brd_song_duration.py --character Onedough
```

reports the gear tier, the best owned loadout and the measured Nitro/Soul Voice
timers against a throwaway copy of the live database.
`server/tests/test_bard_song_sets.py` pins the library's song sets and timers, and
`server/tests/test_effects.py` pins the 10%-per-Song+ rule itself.
