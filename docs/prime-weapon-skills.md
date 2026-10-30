# Prime weapon skills

Research note and implementation, 2026-10-25.  It answers why the Prime dagger skill
looked weak in the 2026-10-25 session, lists the retail mechanics Fanxi did not model, and
documents the physical Prime Aftermath added in this pass.

## Update, 2026-10-27

The weapon-skill path now resolves the whole round — the skill's native hits, Double/Triple/
Quadruple Attack procs, the off-hand swing while dual wielding, and its own multi-attacks —
sums it, and sends **one** action result capped at 99,999 and at the target's remaining HP.
The `action out` line is therefore the total the client shows, and a multi-hit skill no
longer writes one line per hit.  The historical numbers below were read before that change:
a logged total above the target's HP meant overkill was being sent raw, and a multi-hit
skill that killed on its first hit still stopped rolling.  The "truncated total" reading is
still correct for those older lines.

## Update, 2026-10-28 — why DRK Origin was low

The 2026-10-28 session fired Origin on a level-135 Locus Camelopard and read 17–23K at
1,000–1,300 TP (40.5K at 3,000 TP).  The skill's fTP, WSC, hit count and Prime Aftermath
were already correct; the shortfall was in the **attacker**, not the skill:

- **Foenaria had no stat block.**  Migration 87 gave the new Prime weapons only the
  `Adds weapon skill` (355) row.  Foenaria was therefore missing `Scythe skill +277`
  (`item_weapon.ilvl_skill`), `STR+35`, `INT+35`, `Accuracy+35`, `Magic Accuracy+35`,
  `"Triple Attack"+6%` and `Parrying skill +277`.  A DRK was swinging at skill 424
  instead of 701, so Attack was about 277 lower and Origin's WSC (60% STR + 60% INT)
  lost 42 base damage.  Migration 161 adds the block from BG-wiki's iLvl 119 III entry.
- **The other final forms had the same gap.**  Migration 165 gives the remaining 119 III
  Primes their full stat/trait blocks as well, and fixes the rows that were still the
  119 II numbers: Helheim DMG 318 → **336**, Lorg Mor 227 → **240**, Mpu Gandring's
  Dagger skill 269 → **277**, and Varga Purnikawa's `Critical hit rate +15%` had been
  stored as 15 hundredths (0.15%) instead of 1500.  Migration 164 retargets every
  earlier-stage Prime a character already holds (bags, slips, locker, equipped set and
  purchase history) to the final iLvl 119 III id, so the afterglow form is the one the
  DB hands out and the one the Armory sells.
- **Smite was never applied.**  DRK 95's Smite trait (mod 898, value 76) is +76/256 =
  **+29.6% Attack** with a two-handed weapon, but no code read it.  It is now part of
  `stats._attack_value`, only for a two-handed main hand or hand-to-hand.
- **Last Resort and Souleater were icons only.**  They now put up their retail effects:
  Last Resort +25% Attack / −25% Defense for 180 s, Desperate Blows 15% job-ability
  haste (+2% per merit) while it is up, and Souleater's `Accuracy+25` plus its 10%
  current-HP flat damage and HP cost on each landed hit.
- On the live gear sheet (no buffs, 1,256 TP, same Locus Camelopard) the combined fix
  moves Origin's single-hit mean from about **4.8K to 10.9K** with Last Resort up —
  the item/skill block and Smite are most of it; the actual live parse also carries
  Minuet/roll/food Attack, which is why the log's numbers were higher than the bare
  sheet.

The remaining Origin gaps are the HP/MP absorb (below) and the skillchain's own damage;
neither changes the printed weapon-skill number.

## Update, 2026-10-30 — Imperator and the Knights of Rotund tile

Imperator (233) is set up end to end: Caliburnus 21646 carries `Adds weapon skill`
355 = 233, the `weapon_skills` row is `skill_level -1` (item-granted), and
`data/weapon_skills.json` has the published 6.6/13.35/20.1 fTP and 27% DEX / 27% MND
WSC.  A direct server-side use with Caliburnus equipped lands the action, the Prime
aftermath and the skillchain.

The confusing part of the HUD was **Knights of Rotund (227)**.  Its row kept
`skill_level 0`, which Fanxi treats as "quested, offered at 350 sword skill", so a
Caliburnus wearer saw both Imperator and Excalipoor II's joke skill.  Knights of Rotund
is item-granted by Excalipoor II's own 355 row; migration 0173 changes it to
`skill_level -1`, so it only appears with that weapon.  Weapon-skill rejections now log
the id and the equipped main/sub item ids, which makes an equip-swap race visible in
`server.log` instead of silently doing nothing.

The RDM set library had the Caliburnus weaponsets but no `sets.WS["Imperator"]`; PLD
already had one.  RDM and BLU now carry an Imperator WS set (Caliburnus in the main
hand), pinned by `server/tests/test_gearswap_prime_sets.py`.

## Short version

- The 7,854 `Ruthless Stroke` was **not a full weapon skill**.  The target had 3,980 HP
  when the skill started, so the game stopped rolling hits once that HP was spent.  The
  number in the log/chat is the sum of the hits that actually rolled, not the four-hit
  total.
- In the same gear, a full four-hit `Ruthless Stroke` at 1,000 TP is about **15–20%
  stronger** than `Rudra's Storm` at 1,000 TP in Fanxi's own engine (11.0K vs 9.5K in the
  TP set; 13.4K vs 11.1K in the WS set, against the same level-67 Marauder).  The Prime
  dagger WS is not weaker like-for-like.
- The 19,389 `Rudra's Storm` was made in a **Nyame/Fotia weapon-skill set**; the 7,854
  Ruthless was made in a **TP set** (Duty body/legs, Windbuffet Belt).  The two tests were
  not the same gear.  The log also does not record TP, so "same TP" cannot be verified
  from it; a 19K Rudra's is closer to the 2,000-TP range than the 1,000-TP range in that
  set.
- The real retail gap was **Prime Aftermath**: a physical-damage-limit buff of
  2–8% (stage 3), 4–10% (stage 4) or 6–12% (stage 5) by TP, for 60/120/180 seconds.  It is
  applied **on the activating weapon skill**.  It is now implemented for melee and ranged
  Prime weapons; staff/club use different effects whose full 1,000/2,000-TP scaling is not
  published.
- A few smaller gaps matter for specific Prime weapons: Dagda has no data row and rolls
  one hit instead of two, Origin has no HP/MP absorb, and the 3,000-TP anchor for
  Disaster is wrong (too high, not too low).  Sarv and Terminus now use the bow/gun and
  ammo through the ranged WS path.

## What the log actually shows

Relevant lines in `data/server.log` for character `Onedough` (Mpu Gandring, stage 5):

| Time | Skill | Logged damage | Target HP before | Gear just equipped | Reading |
|---|---|---:|---:|---|---|
| 10:50:24 | Rudra's Storm | 18,885 | 11,515 | Nyame + Fotia + Moonshade WS set | one hit, full damage |
| 11:00:02 | Rudra's Storm | 19,389 | 5,751 | Nyame + Fotia + Moonshade WS set | one hit, full damage |
| 11:06:00 | Ruthless Stroke | 7,854 | 3,980 | Duty TP set, no Fotia / no Nyame PDL | first hit (or first two); later hits skipped |
| 14:40:36 | Zesho Meppo | 4,759 | 3,700 | Ninja TP/WS set | first hit (or first two); later hits skipped |

The hit loop in `server/fanxi_server/game/zone.py` (around line 5227) breaks as soon as
the target's remaining HP reaches zero:

```python
for index in range(hits):
    if index and hp_left <= 0:
        break
    ...
    hp_left = max(0, hp_left - int(hit_damage))
```

That matches retail: a multi-hit WS stops once the target dies.  It also means a
multi-hit skill tested on a mob that is already at 25% HP shows one or two hits' worth of
damage.  `Ruthless Stroke` has four hits; the 7,854 is a truncated total.

The log line itself only carries the action total (`action out: ... damage=7854`), not
the per-hit results, so it is easy to read it as the whole WS.

## Same-gear simulation

I rebuilt two outfits from the log on a copy of the live database and resolved the same
skills through `combat.melee` (the same pDIF/fSTR/crit/damage-cap code the server uses),
800 samples per cell, no food, rolls, songs or trusts.  Target: Marauder Dvogzog, level
67, DEF 293.  "First" is the first hit only; "full" is all four hits of Ruthless.

**Duty TP set (the set used for the 7,854 Ruthless test), DEX 359 / AGI 309, +10% WSD
from the cape, no PDL:**

| TP | Rudra's Storm | Ruthless first hit | Ruthless full four hits |
|---:|---:|---:|---:|
| 1,000 | 9,548 | 7,159 | 10,977 |
| 2,000 | 19,459 | 18,050 | 22,001 |
| 3,000 | 24,826 | 28,946 | 33,030 |

**Nyame/Fotia WS set (the set used for the 19K Rudra's), DEX 319 / AGI 315, +28% PDL from
Nyame augments, Fotia +0.195 fTP:**

| TP | Rudra's Storm | Ruthless first hit | Ruthless full four hits |
|---:|---:|---:|---:|
| 1,000 | 11,120 | 8,995 | 13,350 |
| 2,000 | 22,230 | 22,230 | 26,432 |
| 3,000 | 28,246 | 35,472 | 39,519 |

The 7,854 sits above the 7,159 first-hit mean because it was a high pDIF roll and/or a
critical; the point is that it is a **first-hit number**, not the 11.0K–13.4K full total.
At 1,000 TP in the same set, Ruthless's full four hits beat Rudra's by 15–20%.  These
numbers are before Prime Aftermath; the +6% PDL at 1,000 TP adds about 6% on top.

The 19,389 is above the 1,000-TP Nyame-set mean (11,120) and near the 2,000-TP mean
(22,230).  TP is not in the log.  Either the Rudra's was fired with more than 1,000 TP, or
buffs/food/rolls were up that were not recorded in the gear lines.  A true 1K-to-1K
comparison needs both skills in the same set at the same TP on a full-HP target.

## Retail Prime WS data

The retail values below are the ones the wiki/FFXIAH tests publish.  "Fanxi" is
`data/weapon_skills.json`; "JP" is the FF11用語辞典 page for the skill.  Where the two
sources disagree, the disagreement is marked.

| Skill | Weapon | Fanxi fTP (1k/2k/3k) | Retail fTP (1k/2k/3k) | Fanxi WSC | Retail WSC | Hits | Note |
|---|---|---|---:|---|---|---:|---|
| Maru Kala | H2H | 3.128 / 7.273 / 11.414 | 3.1 / 7.2 / 11.4 | STR 41.75 / DEX 41.75 | same | 2 | matches |
| Ruthless Stroke | Dagger | 5.7578 / 14.5156 / 23.2773 | 5.7578 / 14.5156 / 23.2773 | DEX 20 / AGI 20 | DEX 20 / AGI 20 | 4 | matches JP; BG-wiki lists 5.375 (verification needed) and 25/25, which conflicts with JP |
| Imperator | Sword | 6.6 / 13.35 / 20.1 | 6.6 / 13.35 / 20.1 (BG) | DEX 27 / MND 27 | same (BG) | 1 | BG only; unverified |
| Dagda | Club | generic 1.5 / 2.0 / 3.0 | unknown | none | STR ? / MND ? | **2** | no row; Fanxi rolls **1** hit |
| Oshala | Staff | 3.95 / 7.89 / 11.84 | 3.95 / 7.89 / 11.84 | MND 45 / INT 45 | INT 45 / MND 45 | 1 | matches |
| Fimbulvetr | Great sword | 3.3 / 6.6 / 9.9 | 3.57 / 7.13 / 10.71 | STR 60 / VIT 60 | STR 50 / VIT 50 | 1 | fTP ~8% low, WSC 20% high; net depends on stats |
| Blitz | Axe | 1.5 / 7.0 / 12.5 | 1.5 / 7.0 / 12.5 (BG) | STR 32 / DEX 32 | same (BG) | 5 | first-hit-only fTP (later native hits 1.0); Spalirisos itself must carry Axe skill +277 and its stat block (migration 0155) or the 12.5 anchor is built from a much weaker base |
| Disaster | Great axe | 3.05 / 9.15 / **15.25** | 3.235 / 6.47 / **9.705** | STR 60 / VIT 60 | STR 53 / VIT 53 | 1 | **wrong 3,000 anchor**; 15.25 is an extrapolation from a misread 9.15 |
| Origin | Scythe | 3.0 / 6.0 / 9.0 | 3.0 / 6.0 / 9.0 | STR 60 / INT 60 | same | 1 | values match; HP/MP absorb missing |
| Diarmuid | Polearm | 2.17 / 5.36 / 8.55 | 2.0 / 5.0 / 8.0 | STR 55 / VIT 55 | STR 63 / VIT 63 | 2 | fTP ~8% high, WSC ~13% low; net depends on stats |
| Zesho Meppo | Katana | 4.0 / 11.3575 / 18.715 | 4.36 / 11.73 / 19.08 | DEX 25 / AGI 25 | DEX 24 / AGI 24 | 4 | `multi_hit_ftp` is set in Fanxi but not stated by either wiki |
| Tachi: Mumei | Great katana | 3.66 / 7.33 / 11.0 | 3.527 / 7.059 / 10.586 | STR 50 / DEX 50 | STR 51 / DEX 51 | 1 | ~4% high |
| Sarv | Archery | 2.75 / 5.5 / 8.25 | 2.727 / 5.453 / 8.18 | STR 65 / AGI 65 | STR 66 / AGI 66 | 1 | values close; ranged path implemented |
| Terminus | Marksmanship | 2.5 / 5.0 / 7.5 | 2.516 / 5.031 / 7.547 | DEX 70 / AGI 70 | DEX 71 / AGI 71 | 1 | values close; ranged path implemented |

The `Disaster` row is the only large numeric error.  `tools/import_lsb_weapon_skills.py`
says it best in its own comment:

```python
94: {"name": "Disaster", "ftp": [3.05, 9.15, 15.25], ...
# The 2000 TP anchor of Disasters is not published; 15.25 continues its 1000 -> 2000 step.
```

Both sources put the **3,000** anchor at about 9.15–9.705, not 15.25; 9.15 is the
3,000-TP value, so the list was shifted one anchor too far.  This makes Disaster too
strong at high TP, not too weak.

## Prime Aftermath: retail mechanics and implementation

Retail Prime weapons grant an aftermath when their own WS is used:

| Stage | PDL at 1,000 TP | at 2,000 TP | at 3,000 TP | Duration |
|---|---:|---:|---:|---:|
| 3 (iL119) | 2% | 5% | 8% | 60 s |
| 4 (iL119 II) | 4% | 7% | 10% | 120 s |
| 5 (iL119 III) | 6% | 9% | 12% | 180 s |

- Potency scales linearly with the TP spent from 1,000 to 3,000.  Duration and tier are
  banded, not linear: 1,000–1,999 TP is tier 1/60 s, 2,000–2,999 is tier 2/120 s, and
  3,000 is tier 3/180 s.
- It is **Physical Damage Limit+** (`DAMAGE_LIMITP` in Fanxi terms), i.e. it raises the
  attacker's pDIF cap.  Against a capped-ratio target it is a direct damage multiplier.
- FFXIAH testing found that it **applies on the activating WS** ("AM applies on the
  activating WS"), so the WS that grants it already gets the bonus.
- Stage 5 Mpu Gandring (the user's weapon) at 1,000 TP therefore gets +6% PDL for 60 s;
  at 3,000 TP it gets +12% for 180 s.  On the Nyame set, which already has +28% PDL, the
  aftermath is a substantial additional multiplier.
- TP Bonus and Fencer do **not** change the tier, duration or potency: retail uses the TP
  actually spent.
- The three tiers have Mythic/Empyrean's lock rule: level 1 can overwrite itself, level 2
  overwrites level 1 but not itself, and level 3 overwrites levels 1 and 2 but not
  itself.
- Changing a main/sub/ranged weapon removes the buff, as in retail.
- Staff and club have different aftermaths: Opashoro gives MAB/Magic Damage, Lorg Mor
  gives Cure potency/Magic Damage.  Their full TP scaling is not published, so the
  physical table does not guess them.

Fanxi implements the physical table in `server/fanxi_server/game/prime_weapons.py` and
wires it into `ZoneSession.weaponskill`:

- the equipped item's `355` modifier names the skill, and the item's damage rank inside
  that family determines the stage (highest = 5, next = 4, third = 3);
- `_grant_prime_aftermath` runs before the hit loop, so the activating WS sees the raised
  cap; the effect then merges through `combat_mods()` for auto-attacks and later skills;
- `_drop_aftermath` removes the buff when a main/sub/ranged weapon is replaced or taken
  off.  A gear burst that re-sends the copy already worn (the phase engine sends the whole
  TP/WS set after every skill) is not a weapon change and leaves it alone;
- the buff is effect 273 with the client's tier icons 270/271/272.

The same-copy check is what makes Blitz usable in normal play.  The phase engine sends a
whole equipment set as one 0x050 per slot, and the Spalirisos/Ikenga's Axe pair is in both
the TP and the WS sets.  Comparing the packet's bag slot and item against the worn copy
keeps the aftermath through that burst; an actual swap or unequip still clears it, the
same way retail removes it only when the worn weapon itself changes.

The table covers stages 3–5.  In the current item data only Mpu Gandring and Varga
Purnikawa carry `355` on their stage-4 form, and no stage-3 form carries it, so those are
the only stage-4 aftermaths reachable right now; adding the missing `355` rows later
needs no change to the aftermath code.

The tests are in `server/tests/test_weapon_skills.py`
(`WeaponSkillSessionTest.test_prime_aftermath_*`, plus
`test_blitz_aftermath_survives_a_gear_burst_that_re_wears_the_weapon` for the same-copy
case).

## Other gaps that affect specific Prime skills

| Area | What happens now | Effect |
|---|---|---|
| Ranged WS path | `World.player_attack` always uses `sheet.fighter` (main hand); there is no ranged attack round | Sarv (Pinaka) and Terminus (Earp) use the melee weapon's DMG/skill.  A RNG with a dagger main hand gets dagger damage. |
| Hand-to-hand | One swing per attack round | Maru Kala's owner loses half auto-attack DPS; the WS itself is two hits and is fine. |
| Origin | No `weapon_skill_effects` row | HP/MP absorb missing.  Retail is roughly 5–10% of damage as HP and 0.5–1% as MP, and undead are immune. |
| Prime item stat blocks | Migration 165 gives every iLvl 119 III Prime its skill cap, STR/DEX/VIT/INT/MND, Accuracy, Magic Accuracy, weapon traits and Parrying/Guarding/Shield rows.  Two non-physical lines are not modelled: `Magic Accuracy skill +277` (no magic-accuracy skill stat in this engine) and Duban's `All status ailment resistance +20`. | The physical numbers are retail's.  Only those two non-physical lines are absent. |
| Earlier Prime forms | Migration 164 retargets stage 1–4 items in bags, slips, locker, equipped set and purchase history to the final iLvl 119 III id; the Armory sells only that id. | A character cannot end up fighting with a Non AG Prime by buying or holding an earlier stage. |
| Dagda | `weapon_skills.for_id(234)` is `None`; generic curve, `hits=1` | Retail is a twofold attack.  Only the first hit rolls, and the generic fTP is not retail's. |
| Zesho `multi_hit_ftp` | `True` in `data/weapon_skills.json` | If true, all four hits get the full fTP (very strong); if false, only the first does.  Neither wiki states it.  A ~49K parse at ~1K TP with AM3 supports "true", but it needs a controlled test. |
| WS TP return | `zone.py` spends TP and returns it from the landed hits (main/off-hand delay + 10 TP per extra hit, after Store TP, Save TP and Conserve TP) | Implemented; multi-hit Prime WSs now refund their extra hits |
| Skillchains | `_advance_skillchain` runs from the weapon-skill result | Implemented for the opening/closing chain damage; the client plays it from the closing WS's additional-effect block. |

## Is the damage formula wrong?

No.  The physical skill path is doing what it says:

- WSC is summed per stat and floored (`weapon_skills.py`, `wsc_for`).
- fTP is interpolated at the effective TP and applied to the first hit; later hits use
  1.0 unless `multi_hit_ftp` (`zone.py` around line 5232).
- The base is `weapon DMG + fSTR + WSC`, then `× fTP × pDIF`
  (`combat.py` around line 712).
- WSD gear, Fotia fTP, Fencer, critical rate and `DAMAGE_LIMIT(P)` all reach the roll.
- The target's HP cutoff is intentional.

The apparent "low damage" comes from the test setup (truncated multi-hit, different
sets/TP) and from the previously missing Prime Aftermath, not from a broken WSC/fTP
formula.

## How to test a Prime WS properly

1. Use a **full-HP** target with enough HP to survive the whole WS.  Marauder Dvogzog has
   16,000 HP; a 100,000-HP test dummy is better.
2. Use the **same weapon-skill set** for both skills.  Do not compare a Nyame/Fotia WS set
   against a TP set.
3. Use the **same TP** for both.  The log does not record TP; read the TP bar, not the
   damage.  If possible, fire at exactly 1,000 and then exactly 3,000.
4. Take 20+ samples.  Multi-hit WSs have high variance from hit/crit/pDIF rolls.
5. Compare the **full total**, not the first number.  If the target dies during the WS,
   the number is truncated.
6. Test at 1,000, 2,000 and 3,000 TP.  Prime WSs are designed to scale; the 1,000-TP
   anchor is not where most of them beat the relic WS.

## Recommended fixes, in order

1. **Prime Aftermath** — **done** for melee/ranged in `prime_weapons.py` and
   `ZoneSession.weaponskill`.  Stage mapping comes from the `355` modifier plus the
   item's damage rank; potency is linear over the TP spent; duration/tier are 60/120/180 s
   at 1,000/2,000/3,000; the tier lock and the weapon-change removal match retail; the
   activating WS gets the bonus.  Staff/club remain a data gap (their effect is not PDL).
2. **Ranged WS path** for Sarv/Terminus.  Use the ranged slot's weapon, ammo and
   Archery/Marksmanship skill; this is the same missing feature as the ranged attack
   round, so it may be worth doing together.
3. **Origin** effect row: HP 5–10% and MP 0.5–1% of damage, undead immune.
4. **Dagda**: at minimum make it two hits; add fTP/WSC only when a tested source exists.
5. **Disaster** data: replace `15.25` with the 3,000-TP value (9.705 per JP wiki, 9.15 per
   BG-wiki) and decide between 60/60 and 53/53 WSC.  This makes Disaster weaker, not
   stronger.
6. **WS TP return and skillchain wiring** — **done** in `zone.py` (the chain is the
   closing WS result's additional-effect block).

The physical Prime aftermath is live; the remaining high-value gaps are the ranged WS
path and the staff/club aftermath data.

## Sources

- [FFXIAH: Aftermath Priority](https://www.ffxiah.com/forum/topic/57554/aftermath-priority/1/)
  — confirms the aftermath drops when the weapon changes and stays while the same one is
  worn.
- [LandSandBoat: charutils.cpp](https://raw.githubusercontent.com/LandSandBoat/server/base/src/map/utils/charutils.cpp)
  — `UnequipItem` deletes `StatusEffect::Aftermath` on the main, sub and ranged slots.
- [BG-wiki: Prime Aftermath](https://www.bg-wiki.com/ffxi/Prime_Aftermath) — stage 3/4/5
  potency ranges, staff/club exceptions.
- [FFXIAH: Prime WS Information, Testing, Discussion](https://www.ffxiah.com/forum/topic/57318/prime-ws-information-testing-discussion/)
  — 2%/5%/8% at 1k/2k/3k, 60/120/180 s, "AM applies on the activating WS", Maru Kala and
  Mumei field results.
- [BG-wiki: Ruthless Stroke](https://www.bg-wiki.com/ffxi/Ruthless_Stroke),
  [Maru Kala](https://www.bg-wiki.com/ffxi/Maru_Kala),
  [Disaster](https://www.bg-wiki.com/ffxi/Disaster),
  [Zesho Meppo](https://www.bg-wiki.com/ffxi/Zesho_Meppo) — the pages the importer's
  `EXTRA` block cites.
- [FF11用語辞典: プライムWS](https://wiki.ffo.jp/html/39090.html) and the per-skill pages
  (39091–39104) — the JP fTP/WSC/hit table used above.
- [Sovereign Behemoth: プライムウェポンDPSのまとめ](https://sovereignbehemoth.blogspot.com/2024/12/dps.html)
  — stage-4/5 Prime DPS vs relic/mythic at 1,000 TP; not every Prime weapon is stronger.
- LandSandBoat scripts:
  [ruthless_stroke.lua](https://raw.githubusercontent.com/LandSandBoat/server/base/scripts/actions/weaponskills/ruthless_stroke.lua),
  [maru_kala.lua](https://raw.githubusercontent.com/LandSandBoat/server/base/scripts/actions/weaponskills/maru_kala.lua),
  [dagda.lua (mob)](https://raw.githubusercontent.com/LandSandBoat/server/base/scripts/actions/mobskills/dagda.lua).
- Local: `server/fanxi_server/game/zone.py` (`weaponskill`), `combat.py` (`melee`),
  `weapon_skills.py`, `weapon_skill_effects.py`, `data/weapon_skills.json`,
  `tools/import_lsb_weapon_skills.py`, `docs/combat-coverage.md`,
  `docs/combat-damage.md`.
