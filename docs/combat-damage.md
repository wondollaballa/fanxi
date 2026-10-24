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
hit-rate cap.  The round delay is `(main + sub) × (1 - Dual Wield%) / 2`, but TP is not
taken from that average: each hand keeps its own weapon delay for TP (see "Tactical
Points"), so the two hits do not pay the same amount.

**Multi-attack.** Each hand independently rolls Double, Triple and Quadruple Attack once
per round, in descending order.  The first proc wins and replaces the lower checks for
that hand:

| Proc | Modifier | Hits for that hand |
|---|---|---:|
| Quadruple Attack | 430 | 4 |
| Triple Attack | 302 | 3 |
| Double Attack | 288 | 2 |
| none | — | 1 |

Rates are percent-integers: gear `"Double Attack"+3` adds 3, the Warrior Double Attack
trait adds 10/12/14/16/18% by tier (the Thief Triple Attack trait adds 5/6%), and the
job's bought rate merit adds 1% per rank while that job is the main (a Warrior's Double
Attack Rate follows the Warrior main, not a Ninja main; the trait itself still comes from
a support job).  Extra hits use that hand's own weapon, Accuracy, damage and animation
(0 main, 1 off), and each hit lands, crits, pays TP and adds hate on its own.  The whole
round -- both hands and every proc -- is capped at 8 results.  Weapon skills are a
separate path and do not roll multi-attack here.

Virtue/Raetic follow-up swings, "Occasionally Attacks X Times" weapons, Mythic aftermath,
Zanshin/Hasso, the Warrior job-point gifts and buff-side rates (Fighter's Roll, Temper,
food) are not modelled yet.

## Tactical Points

TP is paid **per landed hit**, not per round, and each hand uses its own weapon's delay.
Dual Wield halves the reduced delay for the hand that is swinging:

```
delay = weapon base delay
if dual wielding: delay = floor(delay * (100 - Dual Wield%) / 100 / 2)
TP    = floor of the curve below (tenths)
TP    = floor(TP * (100 + Store TP) / 100)
```

| Delay | TP at the breakpoint |
|---:|---:|
| 180 | 6.1 |
| 540 | 14.9 |
| 630 | 15.4 |
| 720 | 16.1 |
| 900 | 17.3 |
| > 900 | `17.3 + (delay - 900) × 28/360` |

Within a band the curve is `start + (delay - bandStart) × slope/360`; the exact
coefficients are in `combat.tp_return`.  A 227-delay katana pays 7.2 TP; dual wielded at
35% its hand's delay is 73.8 → 73, worth 4.2 TP, while a 190-delay off hand at 35% is 61,
worth 4.0 TP.  So the two halves of a dual-wield round are **not** equal, and a
Double/Triple/Quadruple extra hit pays the same as a normal hit with that hand.

The old `(delay + 480) × 0.0085` formula is gone: it overpaid slow weapons and underpaid
fast ones.  There is no "first hit full TP, later hits 10 TP" rule in retail; each hit is
computed independently.  Monster TP gain from being hit (with Subtle Blow and the dAGI
term) is not modelled because monsters have no TP moves here.

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

## Weapon skills

Every weapon skill has its own three fTP anchors and its own secondary-attribute
modifiers (WSC); `data/weapon_skills.json` holds them.  The values are LandSandBoat's
`scripts/actions/weaponskills/*.lua` table, taking the **Adoulin** branch
(`USE_ADOULIN_WEAPON_SKILL_CHANGES`), which is the one a level 119 character uses.

```
effective_tp = min(3000, TP + mod(TP_BONUS) + Fencer TP Bonus)
fTP          = interpolate(skill fTP, effective_tp)     -- 1000 / 2000 / 3000 anchors
fTP         += mod(ANY_FTP_BONUS) / 256                 -- Fotia Gorget/Belt
WSC          = sum(floor(stat * skill coef))            -- no alpha at level 99+
base         = weapon DMG + fSTR + WSC
damage/hit   = base * fTP * pDIF
TP after     = TP - min(TP, 3000)                        -- the bar keeps any excess above 3000
```

Each hit is rolled separately (hit, critical, pDIF) and packed into one action.  The
first hit uses the full fTP; later hits use `1.0` unless the skill carries fTP across
its hits (`multiHitfTP`: Blade: Shun, Resolution, Vorpal Blade, ...).  Multi-hit skills
also stop rolling once the target's HP is spent, as retail does.

A skill may also carry:

| Field | Effect |
|---|---|
| `critVaries` | extra critical-hit rate by TP (Blade: Hi is +15/30/60%) |
| `atkVaries` | Attack multiplier for the pDIF ratio (Blade: Kamu is x2.25) |
| `ignoredDefense` | fraction of the target's Defense removed before the ratio (Blade: Kamu is 25%) |

`WSD` is the sum of three LandSandBoat modifier families that all mean "weapon skill
damage +x%" on an item:

| Id | Meaning |
|---|---|
| 840 | `ALL_WSDMG_ALL_HITS` — the generic line on every hit |
| 841 | `ALL_WSDMG_FIRST_HIT` — the first-hit-only line |
| 570 + ws id | that weapon skill's own line (571 Combo, 580 Final Heaven, ...) |

The per-skill line and 840 are folded into every hit's fTP; 841 only into the first
hit.  "Weapon skill accuracy" (48) is added to the attacker's Accuracy for the hit, and
Fencer (Warrior/Beastmaster/Bard, single-wielding a one-handed weapon) adds its TP Bonus
(903) to `effective_tp` and its critical-hit rate (904) to the crit roll.

The skill's extra effect (`weapon_skill_effects.py`) runs after the damage: drains
restore MP/HP from the hit, and debuffs land only when `damage > 0`.  The self skills
(Myrkr, Dagan) skip the swing path entirely and restore a percentage of maximum MP/HP
instead.  The monster's own debuffs feed back into the next attack: Defense Down and
Dia lower its Defense, Evasion Down its Evasion, Accuracy Down its Accuracy, Attack Down
its Attack, Magic Def./Magic Eva. Down the spell resist terms, and INT Down the `dINT`
term.  See [world.md](world.md) for the full table.

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
dINT     = clamp(caster INT - target INT, -100, 200)
raw      = (spell.base x spell.multiplier + max(0, dINT) x 2) + MAGIC_DAMAGE
MAB/MDB  = (100 + MATT) / (100 + target MDEF)         -- LandSandBoat's ratio
damage   = raw x MAB/MDB x magic_resist
```

`magic_resist` is the deterministic middle of the retail resist roll:

```
macc  = 200 + skill + MACC + caster INT/2
meva  = 200 + 2 x target level + MEVA
resist = clamp(0.75 + (macc - meva)/1000, 0.5, 1.0)
```

`MATT` is "Magic Atk. Bonus", `MAGIC_DAMAGE` is "Magic Damage", `MDEF` is "Magic Def.
Bonus", and the skill is the spell's own school (Elemental Magic 36 for
Fire/Blizzard/Thunder, Dark Magic 37 for Drain, and so on).  Magic Damage joins the base
*before* the MAB ratio, which is why a 100-point Magic Damage line is worth 150 at +50%
MAB.  The old implementation multiplied by MAB and then subtracted MDEF as a separate
percentage, which double-counted both.  The same resist multiplies an
enfeeble's duration, so a caster with too little Magic Accuracy keeps Slow/Paralyze for
less time rather than the spell always landing at full duration.

**Dia and Diaga are not nukes.** Their data is base 2/6/10/16/23 with a zero stat
multiplier, and retail gives them only 1-5 HP per three-second tick plus a 10-30%
Defence Down. `combat.dia_damage` adds a small MND bonus and deliberately ignores Magic
Atk. Bonus and flat Magic Damage: on a level 99 set carrying Magic Damage +421, the nuke
formula turned Dia into a 1,475-damage hit. Dia is also unresistable (retail stops it only
with Magic Shield or immunity), so its duration does not shorten with Magic Accuracy.

**Helixes are one nuke, repeated.** A Helix's opening hit is a normal nuke with its own
stat curve: `base + dINT` up to 100, then half a point per dINT to 200 (BG-wiki's test:
25 + 38 = 63 at level 99), which is why `combat.helix_damage` exists beside
`magic_damage`. The monster then takes that same number again every ten seconds
("tock") for a duration that follows the Scholar level: 30 s at 20-39, 60 s at 40-59,
90 s from 60; a support-job Scholar caps at 49, so /SCH is 60 s. The first tock lands
1-10 s after the cast, one tock is capped at 9,999, and a tier-1 Helix does not replace an
active tier-2 Helix. The opening hit is uncapped and is not a fixed 10 damage: reading
LandSandBoat's `BASE_TICK` column as damage is what made Noctohelix a 10-damage nuke with
a three-second tick. Dark Arts and Tabula Rasa add Helix damage and duration in retail;
this engine only draws those abilities' icons, so the bonuses are not applied.

**Enmity** is two meters per player on every monster: cumulative enmity (CE) in
`ZoneEntity.enmity` minus `enmity_ve`, and volatile enmity (VE) in `enmity_ve`.  The
monster's target is the highest CE + VE.  Damage adds `80 / (level × 31/50 + 6)` CE and
`240 / ...` VE per point (a level-119 monster's divisor is 79, so about 1 CE + 3 VE per
damage); a pure enfeeble adds 100 split 25/75; Provoke adds 1,800 CE and no VE.  The first
source of hate gets retail's 200 CE + 900 VE claim bonus.  Both meters clamp to 30,000.

VE drains 60 points a second, so a tank can lose the monster again; CE never decays by
itself.  When a player dies, zones out, runs past 30 yalms, or if the current target is
overtaken on CE + VE, the monster re-picks the highest remaining player on its next tick.
Linking and the claim lock (a second player being unable to attack a claimed monster) are
not modelled yet.

Two smaller gear paths share the same merged modifier dict:

- **Fast Cast** reduces the cast timer by its percent, capped at 50% and a 0.5 s floor.
- **Store TP** scales the TP from a landed hit after the delay curve (see "Tactical Points").

**Refresh** and **Regen** are passive three-second ticks from `tick_regen`; the same dict
carries the Auto Refresh/Auto Regen traits and the gear lines, so a reforged body with
`"Refresh"+4` restores 4 MP per tick. The tick reads the maxima from the stat sheet (and
`flush_equipment` refreshes them after every outfit batch), so swapping into gear that raises
max HP/MP never leaves the character regenerating against the previous set's cap.

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
| Weapon-skill extra effects, drain rates and status rows | `server/fanxi_server/game/weapon_skill_effects.py` |
| Weapon and item data | `item_weapon` / `item_mods` tables (migrations `0080`, `0092`) |
| The package of the above | `World.player_attack`, `World.mob_attack`, `ZoneSession.stat_sheet`, `ZoneSession.weaponskill` |

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
- **Augments are read, with a short list of exceptions.** `equipped_mods()` joins each
  equipped row to its inventory copy and `augment_stats` decodes both block families:
  bundled rows for Odyssey (Nyame A-D), Limbus Rank 30 and Unity Rank 15, and the
  five-slot standard block for the Ambuscade job capes. The engine has no model only for
  pet stats, Snapshot, block rate, magic-burst II, spell interruption, the weapon `DMG:`
  rating and the Phalanx/Blood Pact lines; they are listed in
  `augment_stats.UNMODELLED` and a test walks every dataset row against that list.
- **Magic is a deterministic resist, not a tier roll.** The retail resist tiers are
  replaced by one multiplier in `combat.magic_resist`; there is no random full/half/quarter
  resist. Monsters do not cast yet, so a player's own MEVA/MDEF is only read when a
  monster-targeted spell is resolved against them.
- **Elemental affinity and elemental resistances are not read.** `Fire MAB`, `Fire SDT`
  and the bar-spell family have no rows for the reforged sets, so only the generic
  `MATT`/`MDEF` are used.
- **Magic burst, skillchains and casting-time gear** are not modelled. `MAGIC_BURST` and
  `"Elemental magic casting time -x%"` are stored in `item_mods` but nothing reads them.
  The per-skill damage, drain and status rows *are* implemented.
- **Weapon-skill magic and ranged paths lag the melee one.** The per-skill fTP, WSC,
  hit count, attack and critical-hit tables are imported for every skill, but a
  `doMagicWeaponskill` row (Aeolian Edge, Sanguine Blade, Wildfire, ...) still rides the
  physical pDIF path instead of the magic resist path, and an archery/marksmanship row
  still uses the main-hand weapon because the ranged attack path is not implemented.
  **Spirits Within** (current-HP formula), **Atonement** (enmity formula), **Moonlight**
  and **Starlight** (MP restore) do not use their special formulas either.  **Dagda**
  has no published fTP or stat modifiers, so it keeps the generic fallback curve.
- **Weapon-skill TP return and aftermath are not modelled.** The bar spends the TP and
  keeps the excess, but the hits do not pay TP back; the Relic/Mythic/Empyrean/Prime
  aftermath buffs need a weapon category and a second buff model.
- **Job traits are only read where the engine consumes their modifier.** Attack/Accuracy/
  Evasion/Defense bonus, Max HP/MP Boost, Store TP, Fast Cast, Dual Wield, Critical damage
  and the weapon-skill lines (WS Damage 840, TP Bonus 345/903, Fencer 904, WS Accuracy 48)
  flow into the sheet.  Double/Triple/Quadruple Attack are read by the attack round (see
  "Multi-attack").  Counter, Kick Attacks, Zanshin,
  Conserve MP/TP, Subtle Blow, Occult Acumen, Shield Mastery/Tactical Parry/Guard and the
  killer/resist families are still inert: the modifier is in the trait table and the
  menu, but no combat path reads it.
- **Status-effect potency/duration gear** is read through `combat_mods()` for the lines
  the engine models: Enhancing Magic duration (listed and augment), Regen potency and
  duration, per-school duration (`ENF_MAG_DURATION`, `DARK_MAGIC_DURATION`, Ninjutsu,
  songs, Sneak/Invisible/En-spell), Cure potency I/II/received/bonus, enfeebling
  potency, `"Enhances Refresh"`, Stoneskin bonus HP and Drain/Aspir potency, with augments
  merged through the same path.  **Not modelled:** Protect/Shell/Haste/Phalanx base
  potency, bar-spell amounts and HP/MP food percentage caps.
- **Food** is a modifier source with a starter table (`food_effects`); the full food
  catalogue is not imported.  **Another player's buffs are not modelled** because the
  server has no party system yet, so only the session's own effects merge into the pool.
  **Subtle Blow** and **Regain** are stored but inert: monsters do not accumulate TP, and
  the tick has no Regain path yet.
- **Merits** are not added to base attributes; they are added to skills, which does flow
  into Attack and Accuracy.

## Open questions

1. **Monster families.** Importing `data/ecosystems.yaml` ranks would remove the biggest
   approximation above. It is a bigger import than the item tables and only matters once
   many families share a level.
2. **Hand-to-hand double hits.** One line in the attack loop once the animation and TP
   accounting for two fists is settled.
3. **Pet stats from augments.** The cape and Odyssey rows name Pet Accuracy/Attack/Haste
   and damage taken; the engine has no pet pool yet, so `augment_stats` skips them.

## Sources

- [BG-wiki: PDIF](https://www.bg-wiki.com/ffxi/PDIF) — ratio, level correction, the
  UL/LL tables, the spike, per-weapon caps, the 1.00–1.05 randomizer.
- [BG-wiki: Damage Taken](https://www.bg-wiki.com/ffxi/Damage_Taken) — PDT/MDT/BDT
  formulas, the 50% cap, Burtgang/Epeolatry, the 87.5% overall cap.
- [BG-wiki: Hit Rate](https://www.bg-wiki.com/ffxi/Hit_Rate) and
  [BG-wiki: FSTR](https://www.bg-wiki.com/ffxi/FSTR) — referenced by the code below.
- [BG-wiki: Myrkr](https://www.bg-wiki.com/ffxi/Myrkr) — 20/40/60% MP at
  1000/2000/3000 TP, removes up to three status effects, self-targeted and no damage.
- [BG-wiki: Fencer](https://www.bg-wiki.com/ffxi/Fencer) — the one-handed main-hand
  condition, TP Bonus and critical-hit rate tiers.
- [LandSandBoat weapon-skill scripts](https://github.com/LandSandBoat/server/tree/base/scripts/actions/weaponskills)
  — the per-skill fTP anchors, WSC, hit counts and status-effect powers/durations.  The
  Adoulin branch of each script is what `tools/import_lsb_weapon_skills.py` writes to
  `data/weapon_skills.json`.
- [BG-wiki: Zesho Meppo](https://www.bg-wiki.com/ffxi/Zesho_Meppo) and the other Prime
  weapon-skill pages — the skills LandSandBoat only scripts as monster skills have their
  fTP, hit count and stat modifiers in `EXTRA` in that importer.
- [BG-wiki: Savage Blade](https://www.bg-wiki.com/ffxi/Savage_Blade) — the Adoulin-era
  fTP anchors that make the skill's 1000 -> 3000 TP jump so large.
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
  - `scripts/combat/basic/tp.lua` — `calculateTPReturn`, the per-slot delay split and
    the Store TP floor.
  - `src/map/enmity_container.cpp` — `UpdateEnmityFromDamage` (80/240 split scaled by
    `GetEnmityModDamage`), `DecayEnmity` (60 VE/s) and the 30,000 cap.
  - `src/map/utils/charutils.cpp` + `src/map/grades.cpp` — base stats from
    `data/stats.yaml` and `data/grades.yaml`.
