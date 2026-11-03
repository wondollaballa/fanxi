# Job audit — how to find the discrepancies across every job

> Current generated reports: [job-ability-status.md](job-ability-status.md) (static
> classification of every row) and [job-ability-smoke.md](job-ability-smoke.md)
> (live-session smoke test).  Regenerate with `tools/job_ability_audit.py` and
> `tools/job_ability_smoke.py`.

The Bard pass showed the shape of the problem: the tables were close, but the *mechanics*
were not. This is the map for doing the same for every job, and the decisions that need
to be made before the work starts.

## Method

For each job, four layers, in this order:

1. **Availability** — can the job use what retail lets it use? (spells and abilities by
   job and level.)
2. **Mechanics** — does each ability/spell do what the wiki says? (the formula, the
   status, the duration, the recast.)
3. **Passives** — traits, job-point categories, merits.
4. **Engine dependencies** — the few effects that need a subsystem that does not exist
   yet. These are only built when the wiki fully specifies the retail behaviour, so the
   subsystem is not invented.

Every claim gets a source: the BG-wiki page for the ability/spell, the job's page for
the trait and merit list, and the code path that implements it.

## Layer 1 — availability

| Kind | State | Where |
|---|---|---|
| Job abilities | **filtered by job/level** for the client's menu (`0x0AB`/`0x0AC`) via `service.job_ability_ids(main, level, sub, sublevel)` | `zone.char_feats`, `zone.char_abilities` |
| Job abilities (re-check) | `zone.job_ability()` does **not** re-check the job/level, so a hand-built packet could use an unlearned ability | `zone.job_ability` |
| Spells | **gated by job and level**: `data/spell_levels.json` holds the (job, level) rows from LandSandBoat's `spell_list.sql`, `zone.spell_bits()` clears the bits the character's main/sub job has not learned, and `cast_magic` refuses a gated spell with "You cannot cast that spell."  **Job-point gift spells** are the exception: `job_points.SPELL_GRANTS` grants them to the level-99 main job and refuses them everywhere else, including the row-less ones (Death, Addle II, Refresh III, …).  Spells with no row and no gift (Trusts, merit spells) stay open | `data/spell_levels.json`, `job_points.SPELL_GRANTS`, `service.spell_levels`, `zone.spell_bits`, `zone.cast_magic` |
| Traits | modelled in `traits.py` + `traits_data.py` (rows, level, job); the RDM pass wired Mag. Burst Bonus, Shield Mastery and Clear Mind into their mechanics | `traits_data.ROWS` |
| Merits | group 1/2 rows read from `char_merits`, values in `merits.MERITS`; per-job application is partial (only the rows with a handler are read).  Scholar's four group-1 and six group-2 rows now have handlers; its group-2 abilities are merit-locked | `merits.py` |
| Job points | 10 categories a job; `job_points.CATEGORY_RULES` implements 24 categories total, so most jobs have rows that are read for their number but not applied to a mechanic | `job_points.py` |

Decided in this pass: **spells are gated like retail**. `data/spell_levels.json` (837
spells with a (job, level) row, from LandSandBoat's `spell_list.sql`) drives both the
client's spell bitmap and the cast check. 91 spells have no level row: they are the
job-point and merit spells (Dia IV/V, the -ga IV/V line, Utsusemi San, Fire VI, the
Threnody II line, Honor March, Aria of Passion, …) plus a few monster-only rows; they
stay open until each job's dive assigns them. The song ones are protected by the
instrument gate in the meantime.

Still open: **`job_ability()` does not re-check the menu filter** (the client's menu is
job/level filtered, but a hand-built packet could use an unlearned ability). Cheap to
add once the ability availability table is read at cast time.

## Layer 2 — mechanics coverage today

366 job abilities in `job_abilities`. A static pass classifies each as:

- **status** — an `effects.ABILITY_EFFECTS` entry (icon + duration, sometimes cancels),
- **jpf** — a `job_points.ability_effect` fallback row (status + duration from the
  job-point table),
- **system** — an id the code compares explicitly (Dancer, Rune Fencer, Puppetmaster,
  Beastmaster, Summoner, Trust, …),
- **inert** — none of the above: the ability plays its animation and does nothing.

| Job | abilities | status | jpf | system | inert |
|---|---:|---:|---:|---:|---:|
| WAR | 12 | 8 | 1 | 1 | 2 |
| MNK | 13 | 8 | 0 | 1 | 4 |
| WHM | 9 | 6 | 0 | 1 | 2 |
| BLM | 7 | 5 | 0 | 0 | 2 |
| RDM | 6 | 4 | 0 | 1 | 1 |
| THF | 15 | 2 | 2 | 0 | 11 |
| PLD | 13 | 2 | 6 | 0 | 5 |
| DRK | 12 | 3 | 5 | 0 | 4 |
| BST | 20 | 2 | 0 | 10 | 8 |
| BRD | 7 | 7 | 0 | 0 | 0 |
| RNG | 14 | 2 | 6 | 0 | 6 |
| SAM | 14 | 1 | 7 | 1 | 5 |
| NIN | 7 | 0 | 5 | 0 | 2 |
| DRG | 18 | 1 | 3 | 2 | 12 |
| SMN | 11 | 3 | 0 | 1 | 7 |
| BLU | 8 | 4 | 2 | 0 | 2 |
| COR | 49 | 1 | 0 | 1 | 47 |
| PUP | 21 | 1 | 0 | 2 | 18 |
| DNC | 44 | 11 | 0 | 9 | 24 |
| SCH | 25 | 21 | 0 | 0 | 4 |
| GEO | 14 | 2 | 3 | 0 | 9 |
| RUN | 26 | 4 | 3 | 0 | 19 |
| **total** | **366** | **98** | **43** | **30** | **195** |

The `inert` column is an **upper bound**: COR's rolls and cards, Dancer's steps and
flourishes, Puppetmaster's maneuvers and Rune Fencer's runes are handled inside
`rolls.py`, `dancer.py`, `pets.py` and the rune branch, and the static scan does not see
every id those tables hold. Each job's deep dive replaces the estimate with the real
list.

The first inert names, as a sample of what the deep dives will hit: Warrior's Charge,
Tomahawk, Boost, Chi Blast, Mantra, Martyr, Devotion, Cascade, Enmity Douse,
Spontaneity, Steal, Flee, Mug, Hide, Accomplice, Collaborator, Despoil, Bully, Larceny,
Shield Bash, Rampart, Majesty, Fealty, Chivalry, Weapon Bash, Consume Mana, Dark Seal.

## Layer 3 — the deep dives

Order by what the party actually plays (`characters` table):

1. **SAM** (Twodough) — Five Stars, Hasso/Seigan, Meditate, Third Eye, Sekkanoki,
   Konzen-ittai, Warding Circle, Shikikoyo, Hagakure.
2. **WAR** (Twodough/Fivedough sub, and the job's own kit) — Berserk, Defender,
   Aggressor, Warcry, Mighty Strikes, Retaliation, Savagery, Warrior's Charge, Tomahawk.
3. **PLD** (Fivedough) — Shield Bash, Holy Circle, Sentinel, Cover, Rampart, Fealty,
   Chivalry, Majesty, Reprisal.
4. **WHM** (Fourdough) — Devotion, Martyr, Benediction, Asylum, Afflatus, the bar- spells.
5. **RDM / BLM** (Threedough) — Chainspell, Convert, Composure, Spontaneity, Manafont,
   Elemental Seal, Cascade, Enmity Douse.
6. **GEO** (Sixdough) — the geomancy bubbles and their potency/duration.
7. **DNC** (Onedough's sub, already partly implemented) — steps, waltzes, flourishes.
8. Then the rest of the roster (COR, PUP, RUN, DRG, THF, BST, SMN, NIN, DRK, RNG, MNK,
   SCH, BLU) in that order.

Each dive produces: the wiki formula, our current value/path, the delta, a test, and the
fix. Engine subsystems are only added when a dive needs one **and** the wiki fully
specifies it (the Bard pass's rule: Threnody reused an existing effect; Mazurka and
Virelai were left alone because the engine has no movement or charm model).

## Decisions before starting

1. **Spell availability**: keep "every job can cast every spell" (QoL) or gate spells by
   job/level like retail? This is the one item that changes every character.
2. **Ability re-check**: add the job/level check inside `job_ability()` even if the menu
   already filters? (Recommended, it is a few lines and closes a packet-level hole.)
3. **Scope of the residue**: for abilities whose retail behaviour is cosmetic or
   unmodelled (Flee, Hide, Steal), do we implement a stub effect, or leave them inert and
   list them as known gaps? (Recommended: known gaps with a line in the job's section,
   not stubs that pretend.)
