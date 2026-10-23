# Combat damage

How Fanxi should compute physical damage, following retail. This replaces the
level-only formulas in `server/fanxi_server/game/world.py` (`player_attack`,
`mob_attack`), which read no Attack, Defense, weapon damage or gear at all.

The model below is the one **LandSandBoat** implements; it is the most complete
public reconstruction, and it is the same project Fanxi already takes `skills.yaml`,
the merit table and `item_weapon.sql` skill types from. Where the wiki and the
implementation disagree, this document follows the implementation and says so.

Sources are listed at the end.

## The pipeline

Retail physical damage is four independent stages. Attack/Defense do not act on
damage directly — they only choose the multiplier.

```
1. base damage   = weapon DMG + fSTR
2. ratio         = Attack / Defense
3. pDIF          = f(ratio, weapon type, crit, level difference)   -- a multiplier, ~0.2 .. 4
4. damage        = floor(base damage * pDIF)       -- pDIF already carries the 1.00-1.05 roll
```

Damage taken is a **fifth** stage, applied to the amount the defender receives:
`final = damage * damage-taken-multiplier`, with PDT/MDT/DT caps.

## Attack (player)

```
ATT = 8 + mod(ATT)                       -- gear "Attack+"
    + floor(STR * str_mult)              -- by weapon class
    + skill(weapon skill type)           -- the weapon in that hand
ATT = max(1, ATT + ATT * ATTP/100 + min(ATT * FOOD_ATTP/100, FOOD_ATT_CAP))
```

`str_mult` is era-dependent. Current retail (`settings/default/main.lua`):

| Weapon class | STR → Attack |
|---|---:|
| Two-handed | 1.0 |
| Hand-to-hand | 1.0 |
| One-handed main | 0.75 |
| One-handed off-hand | 0.5 |
| Ranged | 1.0 |

`skill(...)` is the *capped, merited, gear-boosted* value Fanxi already computes in
`ZoneSession.effective_skills()`, so the skill half of this is already available.

**Dual wield.** When both slots hold a one-handed weapon and the job has the Dual Wield
trait, one attack round swings both hands.  Each swing uses its own weapon DMG, skill,
weapon rank and Accuracy; the off hand takes the 0.5 STR multiplier above and the 95%
hit-rate cap.  The round delay is `(main + sub) × (1 - Dual Wield%) / 2`, and TP per hit
is calculated from that same per-hand delay, so both hands swing on the reduced timer.

## Defense (player)

```
DEF = 8 + floor(VIT * 1.5)               -- mobs and charmed pets use VIT * 0.5
    + level factor
    + mod(DEF)                           -- gear "Defense+", Protect
DEF = max(1, DEF + DEF * DEFP/100 + min(DEF * FOOD_DEFP/100, FOOD_DEF_CAP))
```

Level factor (players only):

| Level | Bonus |
|---|---|
| < 51 | `+ level` |
| 51-60 | `+ 2*level - 42` |
| 61-90 | `+ level + 18` |
| 91+ | `+ level + 18 + floor((level - 89) / 2)` |

## fSTR

The STR-versus-VIT term added to weapon damage. Players use weapon rank:

```
weapon_rank = floor(weapon_DMG / 9)       -- H2H players: floor((DMG + 3) / 9)

stat_diff = STR - target_VIT
stat_diff = clamp(stat_diff, -(7 + 2*rank) * 2, (14 + 2*rank) * 2)

raw = stat_diff >= 12  ? stat_diff + 4
    : stat_diff >= 6   ? stat_diff + 6
    : stat_diff >= 1   ? stat_diff + 7
    : stat_diff >= -2  ? stat_diff + 8
    : stat_diff >= -7  ? stat_diff + 9
    : stat_diff >= -15 ? stat_diff + 10
    : stat_diff >= -21 ? stat_diff + 12
    :                    stat_diff + 13

fSTR = clamp(raw / 4, rank == 0 ? -1 : -rank, rank + 8)
```

Mobs and pets use a different, larger table (`calculateMeleeStatFactor`, mob branch)
and clamp to `[-1 - floor(level/5), floor(level/5) + 5]`.

## pDIF

### 1. Ratio and level correction

```
ratio = ATT / target_DEF                       (target_DEF = max(1, DEF))
```

Level correction applies **only in pre-2013 zones** (Ronfaure, Gustaberg, Sarutabuta,
etc.). Fanxi's starter zones are all in that set, so it applies.

```
level_dif = clamp(attacker_level - target_level, -38, 38) * 3/64
level_dif = 0 if attacker is a mob and level_dif < 0     -- mobs never lose ratio
level_dif = 0 if attacker is a PC  and level_dif > 0     -- PCs never gain ratio
```

> The wiki states `0.05` per level. LandSandBoat uses `3/64 = 0.046875`, taken from
> the JP model, and notes the wiki figure fits less well. Use `3/64`; it is one
> constant if it ever needs revisiting.

### 2. wRatio

```
wRatio = ratio + (crit ? 1 : 0) + level_dif
```

### 3. Lower and upper bounds

**Players** (`wRatioCapPC`):

| wRatio | upper | lower |
|---|---|---|
| < 0.38 | — | 0 |
| 0.38 .. 0.5 | `wRatio + 0.5` | `wRatio * 1176/1024 - 448/1024` |
| 0.5 .. 0.7 | `1` | `wRatio * 1176/1024 - 448/1024` |
| 0.7 .. 1.2 | `wRatio + 0.3` | `wRatio * 1176/1024 - 448/1024` |
| 1.2 .. 1.25 | `wRatio + wRatio*0.25` | `wRatio * 1176/1024 - 448/1024` |
| 1.25 .. 1.5 | `wRatio + wRatio*0.25` | `1` |
| 1.5 .. 1.51 | `wRatio + 0.375` (capped) | `1` |
| 1.51 .. 2.44 | `wRatio + 0.375` (capped) | `wRatio * 1176/1024 - 775/1024` |
| >= 2.44 | `wRatio + 0.375` (capped) | `wRatio - 0.375` (capped) |

Both are clamped to the weapon's **final pDIF cap**:

```
cap = (weapon_cap + DAMAGE_LIMIT/100) * (1 + DAMAGE_LIMITP/100)
        + (crit ? 1 : 0) + level_dif
```

**Mobs and pets** (`wRatioCapOthers`) use a different curve, with a base cap of
`2.0` in level-corrected zones and `4.0` outside them:

| wRatio | upper | lower |
|---|---|---|
| <= 0.4 | — | `0.25` |
| 0.4 .. 0.55 | `0.6 + 760/1024 * wRatio` | `0.25 + 827/1024 * (wRatio - 0.4)` |
| 0.55 .. 0.8 | `1` | `0.25 + 827/1024 * (wRatio - 0.4)` |
| 0.8 .. 1.2 | `1 + 1127/1024 * (wRatio - 0.8)` | `0.25 + 827/1024 * (wRatio - 0.4)` |
| 1.2 .. 1.35 | `1474/1024 + 1105/1024 * (wRatio - 1235/1024)` | `0.25 + 827/1024 * (wRatio - 0.4)` |
| 1.35 .. 1.5 | same upper | `1` |
| 1.5 .. 1.6 | `1803/1024 + 1070/1024 * (wRatio - 1.5)` (capped) | `1` |
| > 1.6 | same upper (capped) | `1 + 1120/1024 * (wRatio - 1.59)` (capped) |

### 4. The spike

Between wRatio 0.5 and 1.5 there is a chance the hit lands with pDIF exactly 1:

```
sRatio = clamp((0.5 - abs(wRatio - 1)) * 1.2, 0, 1/3)   -- PCs
if uniform(0, 1) < sRatio: return 1 + level_dif
```

### 5. Final pDIF

```
upper = max(upper_cap, uniform({0, 0.5}))     -- the 50/50 lower-bound quirk
pDIF  = uniform_3dp(lower_cap, upper)
pDIF *= 1 + randint(0, 5) * 0.01              -- 1.00 .. 1.05 randomizer
if crit:
    bonus = clamp(CRIT_DMG_INCREASE - target_CRIT_DEF_BONUS, 0, 100)
    pDIF *= (100 + bonus) / 100
```

Weapon caps (`pDifWeaponCapTable`; the wiki's crit column is `cap + 1`, which the
formula adds itself):

| Skill | Cap | Skill | Cap |
|---|---:|---|---:|
| H2H | 3.5 | Great katana | 3.5 |
| Dagger | 3.25 | Club | 3.25 |
| Sword | 3.25 | Staff | 3.75 |
| Great sword | 3.75 | Archery | 3.25 |
| Axe | 3.25 | Marksmanship | 3.5 |
| Great axe | 3.75 | Throwing | 3.25 |
| Scythe | 4.0 | Blue magic | 3.0 |
| Polearm | 3.75 | Katana | 3.25 |

## Final damage

```
damage = floor(max(weapon_DMG + fSTR, 0) * pDIF)
```

The `max(..., 0)` is real: negative fSTR can zero out a hit. Damage is floored once,
at the end.

## Hit rate

```
acc = acc_from_skill(skill) + floor(DEX * dex_mult) + mod(ACC)
eva = evasion_skill_capped + mod(EVA) + floor(AGI / 2)
eva += floor(eva * EVA_PERCENT / 100)
```

`acc_from_skill` is piecewise (`GetAccFromSkill`):

```
skill <= 200 : skill
skill <= 400 : 200 + (skill - 200) * 0.9
skill <= 600 : 380 + (skill - 400) * 0.8
skill  > 600 : 540 + (skill - 600) * 0.9
```

Evasion skill above 200 is compressed: `200 + (skill - 200) * 0.9`.

```
if attacker_level < target_level: acc += (attacker_level - target_level) * 4   -- PCs only
hitdiff = (acc - eva) / 2
hitrate = clamp((75 + hitdiff) / 100, 0.2, cap)
```

| Attacker | Cap |
|---|---:|
| 1H main / H2H / pet | 0.99 |
| Two-handed / off-hand | 0.95 |
| Mob | 0.95 |

The floor is 0.20 for melee, which is also retail's: BG-wiki states plainly that "for
melee attacks, hit rate cannot fall below 20%".  A level 1 monster attacking a level 99
player therefore still connects one swing in five -- it just does zero damage, because
fSTR drives its base damage below zero.  Parry, guard and block then eat most of the
20% that get through.

## Crit rate

```
rate = (5 + dDEX bonus + merit + mod(CRITHITRATE) - target crit evasion) / 100
```

dDEX bonus (attacker DEX − target AGI):

| dDEX | bonus |
|---|---:|
| >= 50 | 15% |
| 40-49 | `(dDEX - 35)%` |
| 30-39 | 4% |
| 20-29 | 3% |
| 14-19 | 2% |
| 7-13 | 1% |
| < 7 | 0 |

Clamped to `[0.05, 1.0]`.

## Base HP and MP

HP and MP are not stored truths: they follow race, job, level and subjob, plus whatever
HP/MP the equipped gear carries.

```
HP = RaceHP[race][level] + JobHP[jobGrade][level] + JobHP[subGrade][subLevel] / 2
MP = RaceMP[race][level] + JobMP[jobGrade][level] + JobMP[subGrade][subLevel] / 2
```

A job with no MP grade (WAR, BST, DRK's is F, ...) brings no racial MP with it.  It only
gets MP from a subjob that has one, and then the racial part enters at the *subjob's*
level, shared down like the subjob itself:

```
MP (job has no MP grade, subjob does)
   = (RaceMP[race][subLevel] + JobMP[subGrade][subLevel]) / 2
```

Gear HP/MP (modifier ids 2 and 5) is added on top, as are bought HP/MP merits and the Max
HP/MP Boost job traits (modifier ids 1095 and 1096).  The computed maximum is what the
`0x061` packet reports, what the HP/MP bars divide by, and what a level-up or job change
recomputes.

## Parry, guard and shield block

Three defensive procs, checked after a hit lands and before damage-taken gear.  At most
one procs per swing, in this order:

**Parry** needs the parry skill, and a main weapon that is not hand-to-hand.

```
delta = parrySkill - attackerWeaponSkill
rate  = delta <= 5 ? 10 + (delta - 6) / 4   : 10 + (delta - 6) / 6.67
rate  = clamp(rate, 5, 25)                  -- percent
```

**Guard** is the hand-to-hand twin, needing the guard skill and fists:

```
rate = delta <= 6 ? 10 + delta / 4 : 10 + delta / 6.67
rate = clamp(rate, 5, 25)
```

**Shield block** needs a shield in the sub slot and the shield skill:

```
rate = (shieldBaseRate + (shieldSkill - attackerWeaponSkill) * 0.2325), clamped 5..100
```

Shield base rates by size (retail): buckler 55, round 40, kite 45, tower 30,
Aegis/Srivatsa 50, Ochain 100.

The reduction is the part retail's reference server does not model -- it only flags the
block -- so Fanxi uses a documented approximation: parry and guard halve the hit, and a
block removes `SHIELD_ABSORB` of it by size (28-60%).  The **rates** are retail-accurate;
the reductions are the tunable part, all in `combat.py`.

Monsters never parry, guard or block: LandSandBoat gates those on a mob mod Fanxi's
monster data does not carry.

## Damage taken — the DT gear stage

This is the part that makes wearing DT gear matter. Applied after damage is rolled:

```
combined = clamp(DMG + DMGPHYS + DMGMAGIC + DMGRANGE + DMGBREATH, -0.5, 0.5)
taken    = clamp(1 + combined + DMGPHYS_II + DMGMAGIC_II, 0.125, 1.875)
taken    = clamp(taken + UDMGPHYS + UDMGMAGIC + UDMGRANGE + UDMGBREATH, 0, 2)
final    = floor(damage * taken)
```

| Modifier | Gear line | Cap |
|---|---|---|
| `DMG` | "Damage taken -X%" (Defending Ring) | shares the 50% cap |
| `DMGPHYS` | "Physical damage taken -X%" (PDT) | shares the 50% cap |
| `DMGMAGIC` | "Magic damage taken -X%" (MDT) | shares the 50% cap |
| `DMGBREATH` | "Breath damage taken -X%" | shares the 50% cap |
| `DMGPHYS_II` | "Physical damage taken II -X%" (Burtgang, Epeolatry) | bypasses 50%, hard stop 87.5% |
| `DMGMAGIC_II` | "Magic damage taken II -X%" (Aegis) | bypasses 50%, hard stop 87.5% |
| `UDMGPHYS` etc. | uncapped damage taken | none |

Three things follow from this shape:

- Generic DT and PDT are **additive inside the same 50% cap**. 25% PDT + 10% DT is
  35% reduction, not 32.5%.
- PDT-II does not multiply — it adds, after the cap, and the whole thing stops at
  87.5% total reduction.
- The "Phys. dmg. limit +5%" on the Nyame augments is **not** this: it is
  `DAMAGE_LIMIT` on the *attacker* side, raising the pDIF cap, not the PDT cap.

The wiki's `Corrected Damage = Uncorrected * (100% - PDT - DT)` with a 50% floor and
the 87.5% overall cap matches these clamps exactly.

## Magic

Direct-damage spells use the caster's INT, the spell's own base and multiplier, and the
gear modifiers the status screen shows:

```
dINT    = clamp(caster INT - target INT, -100, 200)
raw     = (spell.base x spell.multiplier + max(0, dINT) x 2)
damage  = (raw x (1 + MATT/100) + MAGIC_DAMAGE)
          x magic_resist x (1 - target MDEF/100)
```

`magic_resist` is the deterministic middle of the retail resist roll:

```
macc  = 200 + skill + MACC + caster INT/2
meva  = 200 + 2 x target level + MEVA
resist = clamp(0.75 + (macc - meva)/1000, 0.5, 1.0)
```

`MATT` is "Magic Atk. Bonus", `MAGIC_DAMAGE` is "Magic Damage", `MDEF` is "Magic Def.
Bonus" (capped at 80%), and the skill is the spell's own school (Elemental Magic 36 for
Fire/Blizzard/Thunder, Dark Magic 37 for Drain, and so on). The same resist multiplies an
enfeeble's duration, so a caster with too little Magic Accuracy keeps Slow/Paralyze for
less time rather than the spell always landing at full duration.

Two smaller gear paths share the same merged modifier dict:

- **Fast Cast** reduces the cast timer by its percent, capped at 50% and a 0.5 s floor.
- **Store TP** scales the TP from a landed hit: `tp = base x (100 + STOREP/100)`.

**Refresh** and **Regen** are passive three-second ticks from `tick_regen`; the same dict
carries the Auto Refresh/Auto Regen traits and the gear lines, so a reforged body with
`"Refresh"+4` restores 4 MP per tick.

## Worked example

Level 99 katana, skill 424, STR 120, gear Attack +200 (so `ATT = 8 + 200 + 424 + 90 = 722`),
weapon DMG 150, fighting a level 119 Mamool Ja with DEF 59 in a level-corrected zone:

```
ratio      = 722 / 59 = 12.24
level_dif  = clamp(99 - 119, -38, 38) * 3/64 = -0.9375
wRatio     = 12.24 - 0.9375 = 11.30
cap        = 3.25 (katana) - 0.9375 = 2.3125
pDIF       = 2.3125 * ~1.02 = 2.36
fSTR       = rank 16, stat_diff 20 >= 12 -> (20 + 4) / 4 = 6.0
damage     = floor((150 + 6.0) * 2.36) = 368
```

Today the same swing does `99*2 + rand(1..6) - 59*0.5` ≈ **169**, and the number does
not move when Attack, weapon damage or STR change. That is the whole complaint.

## Where this lives in the code

| Piece | File |
|---|---|
| fSTR, pDIF, hit rate, crit rate, damage taken, parry/guard/block, the swing | `server/fanxi_server/game/combat.py` |
| Base attributes, HP/MP, Attack, Defense, Accuracy, Evasion | `server/fanxi_server/game/stats.py` |
| Race/job/level grade tables | `server/fanxi_server/game/base_stats.py` (generated) |
| Item modifier ids | `server/fanxi_server/game/modifiers.py` |
| Weapon and item data | `item_weapon` / `item_mods` tables (migrations `0080`, `0092`) |
| The package of the above | `World.player_attack`, `World.mob_attack`, `ZoneSession.stat_sheet` |

Regenerate the data with:

```bash
tools/gen_base_stats.py --source /tmp/lsb
tools/import_lsb_item_data.py --source /tmp/lsb
```

Both are deterministic, so a source update produces a reviewable diff.

## Deliberate approximations

These are the places Fanxi is retail-shaped rather than retail-exact, all in one place so
they are easy to revisit:

- **Monster families.** LandSandBoat reads a monster's stat ranks per family from
  `data/ecosystems.yaml`. Fanxi has no family data, so every monster uses family rank A
  plus Warrior's job grades. The level curve is LandSandBoat's `GetBaseToRank`, so the
  shape is right and only the family variation is missing.
- **Monster base damage** is the level itself, which is where
  `mobutils::GetBaseWeaponDamage` starts before its per-region offset and multipliers.
  This is the one knob that decides how hard monsters hit; it is a single function in
  `stats.build_monster`.
- **`monster_templates.attack` / `defense` / `accuracy` / `evasion` are not read.** They
  are on a different (pre-scaling) scale from the derived numbers, so mixing the two
  produced monsters that could not land a hit. The columns stay for future family data.
- **Hand-to-hand** is one hit per attack round. Retail lands two (one per fist), so H2H
  currently swings at half the real rate.
- **Parry, guard and block reductions.** The proc rates are retail; how much damage each
  one removes is not modelled by the reference server, so the numbers in `combat.py` are
  documented approximations.  A block is worth more than a parry, and both are worth more
  than nothing.
- **Shield absorption** comes from the size table above rather than per-item data, because
  LandSandBoat leaves every shield's absorption at zero.
- **Augments stored only as client extdata do not contribute.** `item_mods` covers base
  gear, which is where Nyame's and Burtgang's damage-taken numbers live. Job-cape
  augments are encoded for the client in `char_inventory.extra`; the server cannot read
  those numbers back yet, so `!cape pdt` changes what the tooltip says and not what the
  damage engine sees.
- **Magic is a deterministic resist, not a tier roll.** The retail resist tiers are
  replaced by one multiplier in `combat.magic_resist`; there is no random full/half/quarter
  resist. Monsters do not cast yet, so a player's own MEVA/MDEF is only read when a
  monster-targeted spell is resolved against them.
- **Elemental affinity and elemental resistances are not read.** `Fire MAB`, `Fire SDT`
  and the bar-spell family have no rows for the reforged sets, so only the generic
  `MATT`/`MDEF` are used.
- **Magic burst, skillchains and casting-time gear** are not modelled. `MAGIC_BURST` and
  `"Elemental magic casting time -x%"` are stored in `item_mods` but nothing reads them.
- **Status-effect potency/duration gear** (`"Refresh" potency`, `"Regen" potency`,
  `Enhancing magic duration`, `Enfeebling magic effect`) is not read; the base spell
  duration/potency is used. **Subtle Blow** and **Regain** are stored but inert: monsters
  do not accumulate TP, and the tick has no Regain path yet.
- **Merits** are not added to base attributes; they are added to skills, which does flow
  into Attack and Accuracy.

## Open questions

1. **Monster families.** Importing `data/ecosystems.yaml` ranks would remove the biggest
   approximation above. It is a bigger import than the item tables and only matters once
   many families share a level.
2. **Hand-to-hand double hits.** One line in the attack loop once the animation and TP
   accounting for two fists is settled.
3. **Cape augments as real stats.** `capes.py` already knows each build's stat list, so a
   build the server itself encoded could contribute mods without needing the client's
   augment index. That would make `!cape pdt` mean something.

## Sources

- [BG-wiki: PDIF](https://www.bg-wiki.com/ffxi/PDIF) — ratio, level correction, the
  UL/LL tables, the spike, per-weapon caps, the 1.00–1.05 randomizer.
- [BG-wiki: Damage Taken](https://www.bg-wiki.com/ffxi/Damage_Taken) — PDT/MDT/BDT
  formulas, the 50% cap, Burtgang/Epeolatry, the 87.5% overall cap.
- [BG-wiki: Hit Rate](https://www.bg-wiki.com/ffxi/Hit_Rate) and
  [BG-wiki: FSTR](https://www.bg-wiki.com/ffxi/FSTR) — referenced by the code below.
- [FF11用語辞典: 被物理ダメージ](https://wiki.ffo.jp/html/12470.html) — 50% PDT cap,
  PDT-II removing it, DT affecting both physical and magic.
- LandSandBoat (reference implementation, local checkout `/tmp/lsb`):
  - `scripts/combat/physical_utilities.lua` — `calculateMeleePDIF`, `wRatioCapPC`,
    `wRatioCapOthers`, `calculateMeleeStatFactor`, `calculateSwingCriticalRate`.
  - `scripts/combat/physical_hit_rate.lua` — `getPhysicalHitRate`, caps, skill curves.
  - `scripts/combat/basic/damage_multipliers.lua` — `calculateDamageAdjustment`, the
    DT clamps.
  - `src/map/entities/battle_entity.cpp` — `ATT()`, `DEF()`, `ACC()`, `EVA()`,
    `GetMainWeaponRank()`.
  - `src/map/attack.cpp` — `ProcessDamage()`: `floor(max(DMG + fSTR, 0) * pDIF)`.
  - `src/map/utils/charutils.cpp` + `src/map/grades.cpp` — base stats from
    `data/stats.yaml` and `data/grades.yaml`.
