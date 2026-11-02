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
ATTP = mod(ATTP)                         -- percent-integer buffs (Berserk 35, Last Resort 25)
ATTP += floor(mod(SMITE) * 100 / 256)    -- two-handed or hand-to-hand only
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
`ZoneSession.effective_skills()` plus the weapon's `item_weapon.ilvl_skill`, so an iLvl
weapon's own "Scythe skill +277" reaches both Attack and Accuracy.

**Smite.** The trait is stored in 1/256 units (DRK 95 = 76 = +29.6%) and is applied as a
percentage of Attack, *not* as flat Attack.  It only applies while the main hand holds a
two-handed or hand-to-hand weapon; a one-handed or off-hand swing never gets it.  At DRK
95 this is the difference between a 2H job hitting for its gear's Attack and hitting for
roughly 30% more.

**Last Resort** is `ATT_PERCENT +25` / `DEF_PERCENT -25` for 180 s.  **Desperate Blows**
adds its trait value (15% at DRK 45, +2% per merit rank) to `HASTE_ABILITY` while Last
Resort is up and a two-handed weapon is out; it is job-ability haste, so it stacks with
gear and spell haste under the separate 25% ability cap.

**Souleater** is handled per landed hit, after pDIF and critical damage: the hit gains
10% of the user's current HP as flat damage (half for a support-job DRK), and the user
pays that HP back (less Stalwart Soul's percentage).  It also adds `Accuracy+25` while
the icon is up.  Because the flat amount is added before the target's damage-taken gear,
PDT/DT still apply to it, but fTP and pDIF do not multiply it.

**Two weapons.** When both slots hold a one-handed weapon, one attack round swings both
hands: the equip rules accept the sub-slot weapon for every job, so a worn weapon has to
swing.  The Dual Wield trait is not the gate; it supplies the delay reduction (gear
"Dual Wield +N" does the same), and with no such value the round is the plain average of
the two delays.  Each swing uses its own weapon DMG, skill, weapon rank and Accuracy; the
off hand takes the 0.5 STR multiplier above and the 95% hit-rate cap.  With the value the
round delay is `(main + sub) × (1 - Dual Wield%) / 2`, but TP is not taken from that
average: each hand keeps its own weapon delay for TP (see "Tactical Points"), so the two
hits do not pay the same amount.

**Haste.** The round interval applies three separate pools: equipment (`HASTE_GEAR`,
cap 25%), magic (`HASTE_MAGIC`, cap 43.75% -- Haste/Haste II, the marches and GEO
Haste) and job abilities (`HASTE_ABILITY`, cap 25% -- Haste Samba, Hasso, Last
Resort/Desperate Blows).  The three add, and the final delay cannot fall below 20% of
the **base** delay (the 80% delay floor).  A 25%-gear set therefore still gains from a
15% Haste or a 6% Victory March; folding them into one 25% pool made every buff past
the gear cap do nothing.

The floor is measured **before** Dual Wield or Martial Arts: those two reduce delay
outside the haste pools, and retail still applies the 80% total cap to their result.
A 35% Dual Wield pair with every haste pool capped would otherwise reach
`0.65 × 0.20 = 13%` of the base delay, which is faster than retail and pays less TP
per hit.  Retail's rule is `(1 - DW%) × (1 - haste%) >= 0.2`, and the sheet now stores
the pre-reduction `base_delay` so the floor uses it.

That also means gear + magic haste alone top out at **68.75%**.  A two-handed job
cannot reach the 80% floor without the third pool: as a Dark Knight, Last Resort turns
Desperate Blows' 15% into ability haste and takes the same 431-delay great sword from
a 2.39 s round to 1.44 s.  `stat_report` now carries `haste_total` ("Haste (capped
pools)"), `attack_interval` and `tp_per_hit` rows so the launcher shows the capped
pools, the real swing interval and the TP one hit pays instead of leaving the player
to guess from a raw buff total.

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
round -- both hands and every proc -- is capped at 8 results.  Weapon skills roll the
same Double/Triple/Quadruple checks on each of their native hits (up to two procs) and,
while dual wielding, add one off-hand hit plus that hand's procs; see "Weapon skills"
below.

Virtue/Raetic follow-up swings, "Occasionally Attacks X Times" weapons, Mythic aftermath,
Zanshin/Hasso, the Warrior job-point gifts and buff-side rates (Fighter's Roll, Temper,
food) are not modelled yet.

## Tactical Points

TP is paid **per landed hit**, not per round, and each hand uses its own weapon's delay.
Dual Wield halves the reduced delay for the hand that is swinging:

```
delay = weapon base delay
if dual wielding: delay = floor(delay * (100 - Dual Wield%) / 100 / 2)
TP    = floor of the curve below (TP units; the client bar is 0-3000)
TP    = floor(TP * (100 + Store TP) / 100)
```

| Delay | TP at the breakpoint |
|---:|---:|
| 180 | 61 |
| 540 | 149 |
| 630 | 154 |
| 720 | 161 |
| 900 | 173 |
| > 900 | `173 + (delay - 900) × 28/360` |

Within a band the curve is `start + (delay - bandStart) × slope/360`; the exact
coefficients are in `combat.tp_return`.  A 227-delay katana pays 72 TP; dual wielded at
35% its hand's delay is 73.8 → 73, worth 42 TP, while a 190-delay off hand at 35% is 61,
worth 41 TP.  So the two halves of a dual-wield round are **not** equal, and a
Double/Triple/Quadruple extra hit pays the same as a normal hit with that hand.

Haste never changes TP per hit: it only changes how often the hit happens.  With the
same Store TP, the bar fills faster because the round is shorter, not because each
hit pays more.  That is why a reported 66.99% of magic haste becoming 43.75% of
effective magic haste matters: the extra 23% past the cap buys no TP at all, while
another 15% from the job-ability pool does.

The old `(delay + 480) × 0.0085` formula is gone: it overpaid slow weapons and underpaid
fast ones.  There is no "first hit full TP, later hits 10 TP" rule in retail; each hit is
computed independently.  Monster TP gain follows the separate mob curve
(`combat.tp_return_mob`); a player's landed hit feeds the monster's bar with the +30
monster bonus, dAGI and Subtle Blow terms, and the monster spends the bar on its
family's TP moves (`World._mob_try_skill`).

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

## Monsters

Up to level 99 Fanxi uses LandSandBoat's curves: Attack/Accuracy from the family's A+
skill rank (`GetBaseSkill`), Defense/Evasion from `GetBaseDefEva`, and the
family/job/subjob attribute table.  A level-99 Warrior-family monster therefore has
Attack 499, Accuracy 424, Defense 473 and Evasion 465.

Past 99 the old A+ skill table stops growing (LandSandBoat caps `GetMaxSkill` at 99, a
research TODO in its own source), but retail's Apex/Locus tier keeps going.  Fanxi adds
three master-level terms, applied only above 99:

```
master      = max(0, level - 99)
attributes  = 99-capped family/job/subjob value + floor(master * 3.6)
Accuracy    = A+ skill + mod(ACC) + master * 20
Attack      = 8 + mod(ATT) + A+ skill + floor(STR / 2) + master * 16
```

The slopes reproduce the published level-135 Locus Camelopard parse: VIT/AGI around
305/309 (the old table gives 180), **1324 Accuracy** -- the number its wiki page tells
players to reach -- and Attack 1342.  The extra STR also raises fSTR, so the same swing
hits harder on top of the Attack increase.

Every Locus template uses this builder, not just Camelopard.  Their level ranges differ
by camp and are retail's: Bibiki Bay's Bight Rarab / Camelopard / Hypnos Eft are 135-137,
its Ghost Crab / Fiddler Crab are 137-139, and the Crawler's Nest / King Ranperre's Tomb
Locus run 129-136.  A level-129 Locus Lugcrawler therefore has 1174 Accuracy rather than
1324; that is the level, not a missing scaling path.

Locus spawns also roll their level inside that range instead of always taking the low
end, and a respawn rolls it again.  The published camp tables are stored verbatim in
`monster_templates.level_stats` (JSON keyed by level).  `entities.mob_from_row` reads the
row for the rolled level and applies **75%** of its Defense and Evasion: the full rows
are tuned for an iL119 endgame party, and at the current level-99/master-gear range they
made ordinary weapon skills miss and hit for about half.  HP, Accuracy and Attack remain
the published values.  For Camelopard that is:

| Level | HP | Published Def/Eva | In play Def/Eva |
|---:|---:|---:|---:|
| 135 | 289,900 | 1346 / 1224 | 1010 / 918 |
| 136 | 299,100 | 1379 / 1254 | 1034 / 940 |
| 137 | 308,300 | 1413 / 1284 | 1060 / 963 |

`World.monster_sheet()` applies those scaled Defense/Evasion values to the level-derived
fighter, replacing the old 740/732.  The same rows exist for Bight Rarab / Hypnos Eft, the
Bibiki crabs, Bhaflau Colibri / Wivre, Caedarva Imp, and the King Ranperre's Tomb Locus.
The few Locus without a published table (the Crawler's Nest camp) keep the level-derived
`GetBaseDefEva` curve and their flat HP.  `LOCUS_DEFENSE_SCALE` and `LOCUS_EVASION_SCALE`
in `entities.py` are the tuning knobs; 1.0 restores the untouched published rows.

A level-135 Camelopard's scaled 918 Evasion is below the player's ~1182 Accuracy, so the
one-handed hit rate caps without Distract III.  Distract III is still a **flat -130
Evasion** (BG-wiki's cap), not a percent, so it remains useful against the higher-level
crabs and any future camp whose Evasion is not scaled down this far.

Without the master terms a level-135 Locus had 604 Accuracy against a level-99 player's
903 Evasion: the hit formula gave `75 + (604 - 903)/2`, which clamps to the 20% floor
for every auto-attack and every TP move.  That is why the whole family felt
"invincible" on an evasion set.  The 1324-accuracy Locus now reaches the 95% mob cap.

Monster self-buffs that change stats live in the same `effect_state` as player debuffs,
so they expire, can be Dispelled/Finale'd, and are visible to `/check`.  The Dhalmel
**Berserk** TP move is the LandSandBoat script's +45% Attack / -25% Defense for 120
seconds (`scripts/actions/mobskills/berserk.lua`); the monster version gains more Attack
than the player's +35%/-25% Berserk.  Dispel/Finale prefer a real self-buff over the
player's enfeebles, so the Berserk can actually be stripped while Dia is still on.

**Healing Breeze** is a max-HP heal, not the old flat 300.  LandSandBoat passes
`baseHeal = mob:getMaxHP()` and fTP `172/215/258` over 1024 at 1000/2000/3000 TP:

```
heal = floor(maxHP * fTP(spent TP))
     = 48,694 .. 77,677 across a 289,900-308,300-HP Locus Camelopard
```

The TP value is the bar at the moment the move finishes, before the server empties it.

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

## The 99,999 ceiling

Every damage event is then clipped to **99,999**, the most the client prints for one
line: a hit, a weapon skill, a spell, a ranged attack and a skillchain all share it.

```
damage = combat.cap_damage(damage)       # 0 .. 99,999
```

The clamp runs where the number is **built**, not where it is printed, so the target's
HP loss, the hate and the drains (Sanguine Blade, Spirit Taker) match the number the
client is told.  A monster with more than 99,999 HP left therefore survives a 120K
weapon skill, because only 99,999 is applied (the round's `defeated` flag compares the
clipped total, not the raw roll).  A multi-hit weapon skill is one damage line, so its
hits are summed first and the total is clipped: three 40,000 hits are a 99,999 weapon
skill, not a 120,000 one.  Magic Burst and Sengikori multiply after the spell formula, so
the cast's final amount is clipped again; a skillchain hit is clipped inside
`skillchain.skillchain_damage` and again after Sengikori's +25%.  `queue_action` repeats
the clip as a last line of defence and logs a warning if a path that missed its own
clamp ever reaches it.

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

`TP_BONUS` is a normal modifier: gear, weapons and augment blocks all merge through
`combat_mods()`.  The Moonshade Earring's standard block (+250) and Centovente's
Trial of the Magians block (+1000) therefore both raise `effective_tp`; nothing is
slot-specific.

The first listed hit uses the full fTP; later hits use `1.0` unless the skill carries
fTP across its hits (`multiHitfTP`: Blade: Shun, Resolution, Vorpal Blade, ...).  A
weapon skill is one attack round, not only its listed hits:

```
native hits      = the skill's hits (Ruthless Stroke 4, Rudra's Storm 1)
main-hand procs  = DA/TA/QA, up to two procs, rolled after each native hit
off-hand         = one swing while dual wielding, then its own DA/TA/QA procs
round            = native + main procs + off-hand + off-hand procs, capped at 8
first main hit   = +100 Accuracy, and the 841 first-hit line
```

The off-hand swing uses the sub weapon's DMG, Accuracy and 95% hit cap, with the same
WSC and fTP rule.  Every hit rolls hit/miss and pDIF separately.  The hits are **summed
and sent as one action result**: the client prints one damage line (the weapon-skill
animation itself draws the individual hits) and the server logs one `action out` total.
Damage is capped at 99,999 and at the target's remaining HP, so a killing blow prints
the HP left, not the overkill, and a 120K multi-hit skill prints 99,999.

Only a skill whose description says its critical-hit rate varies with TP may critical
hit.  A normal weapon skill takes no base/dDEX/gear critical roll; the skill's TP crit
table (`critVaries`) and Fencer's rate feed the roll for the skills that can crit.

Archery and marksmanship skills do not use the main-hand fighter.  Their `base` is
`ranged weapon DMG + ammo DMG + fSTR + WSC`, their Attack and Accuracy are the ranged
numbers (R.Attack/R.Accuracy and the ranged weapon's skill), their TP return uses the
ranged weapon's delay, and they get no off-hand swing or DA/TA/QA procs.

A **hybrid** skill adds a magic half after the physical hits.  The physical total is
multiplied by the same fTP, flat `Magic Damage` is added, Weapon Skill Damage applies,
then Magic Attack Bonus is weighed against the target's Magic Defense Bonus and the
Magic Accuracy resist:

```
hybrid magic = (physical damage * fTP + MAGIC_DAMAGE) * (1 + WSD/100)
             * (100 + MATT) / (100 + MDEF) * resist
total        = physical damage + hybrid magic
```

The magic half is skipped when the physical hit already killed the target.

A **magical** skill (`magic: true`: Seraph Blade, Sanguine Blade, Seraph Strike,
Wildfire, ...) does not swing and never rolls pDIF.  Its formula is the one BG-wiki
publishes for magical weapon skills:

```
weapon_level = the equipped main weapon's item level (119 for an iLvl weapon)
base = 152 + floor((weapon_level - 99) * 2.45) + WSC   -- 152 + WSC at level 99
base = floor(base * fTP * (1 + Elemental WS Damage)) + dSTAT + MAGIC_DAMAGE
damage = floor(base * (1 + WSD/100) * (1 + affinity/100)
               * (100 + MATT) / max(50, 100 + MDEF) * resist * MDT)
```

The weapon-level term is why an iLvl 119 weapon's Seraph Blade starts from 201, not
from the 101 that LSB's older `Level + 2` reading gives.  `dSTAT` is per skill:
Seraph Blade and Seraph Strike are 0; Sanguine Blade is
`(player INT - target INT) * 2`, uncapped.  `MAGIC_DAMAGE` is the flat "Magic
Damage" statistic and is added after the fTP part, not multiplied by fTP.

`Elemental WS Damage` is the Oboro path-C augment on Crocea Mors, Vitiation Sword and
Duelist's Sword ("Elemental weapon skill damage +100%" at Rank 25).  It multiplies
only the fTP part, before `dSTAT` and flat Magic Damage are added: that is why a
Rank 25 Crocea Mors roughly doubles Seraph Blade and Sanguine Blade.  `affinity` is
the matching element's `*_MAB` row (32-39); Daybreak's "Light elemental damage +50"
is `LIGHT_MAB` 50 and therefore applies to Seraph Blade.  The MAB/MDB divisor floors
the target's term at 0.5, and Magic Accuracy is the deterministic
`combat.magic_resist` approximation.  Weather/day, staff affinity, resistance-rank
reduction and magic critical hits are not modelled.  `element` and `dstat` are filled
for the rows that publish them (Seraph Blade, Sanguine Blade, Seraph Strike and the
other entries in `data/weapon_skills.json`); a magical row without them still uses the
formula but adds no dSTAT and no elemental affinity.  Orpheus's Sash's distance-based
affinity is not modelled either.

Magical skills do not get fSTR, weapon DMG, the off-hand swing, DA/TA/QA, the
physical hit roll or the critical roll.  **Black Halo is not magical**: it is a
two-hit physical club skill (fTP 3.0/7.2/9.6, WSC 70% MND / 30% STR) and only its
opening hit uses the full fTP, like every other non-FTP-replicating multi-hit skill.
Maxentius's "+50% Black Halo damage" is its per-skill WSD row (mod 739).

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
| 570 + ws id | that weapon skill's own line (571 Combo, 580 Final Heaven, 612 Savage Blade on Naegling/Kaja Sword, ...) |

The per-skill line and 840 are folded into every hit's fTP; 841 only into the first
main-hand hit.  "Weapon skill accuracy" (48) is added to every hit's Accuracy, and the
first main-hand hit also gets retail's hidden +100 Accuracy.  Fencer
(Warrior/Beastmaster/Bard, single-wielding a one-handed weapon) adds its TP Bonus (903)
to `effective_tp` and its critical-hit rate (904) to a crit-varies skill's roll.

The skill's extra effect (`weapon_skill_effects.py`) runs after the damage: drains
restore MP/HP from the hit, and debuffs land only when `damage > 0`.  The self skills
(Myrkr, Dagan) skip the swing path entirely and restore a percentage of maximum MP/HP
instead.  The monster's own debuffs feed back into the next attack: Defense Down and
Dia lower its Defense, Evasion Down its Evasion, Accuracy Down its Accuracy, Attack Down
its Attack, Magic Def./Magic Eva. Down the spell resist terms, and INT Down the `dINT`
term.  See [world.md](world.md) for the full table.

## Weapon-skill TP return

A weapon skill spends its TP, then pays TP back from the hits that landed.  The return
is **added to the bar after the spend**, which is why a weapon skill rarely leaves the
player at 0 TP:

```
first main-hand hit       = TP(main weapon delay, after Dual Wield)
one-hit WS off-hand hit   = TP(off-hand delay, after Dual Wield)
every other landed hit    = 10 TP      -- later native hits, DA/TA/QA procs, off-hand multis
each of the above         = floor(TP * (100 + Store TP) / 100)
```

So a one-hit dual-wield weapon skill returns both weapons' delay TP, while a four-hit
skill returns the main hand's delay once plus 10 TP for each of the other three native
hits and every multi-attack proc.  A miss on the first main hit gives up the delay TP
but the later hits still pay 10 each.  A weapon skill with no lands returns 0 unless one
of the saves below applies.

- **Save TP** (mod 945) is compared with the normal return: the larger of the two is
  kept, capped at 500.  Hagakure adds 400 Save TP and 1,000 TP Bonus to the next weapon
  skill; the bonus raises `effective_tp`, the Save TP replaces a smaller return.
- **Conserve TP** (mod 944) is a percent chance to add a random **10–200 TP** on top of
  the return, including on a weapon skill that missed.
- **Meikyo Shisui** spends exactly 1,000 TP while the damage still scales from the
  player's current TP, and suppresses the hit TP return.  It grants 3,000 TP on use.
- **Magical weapon skills** return the main-hand delay TP for their one hit, the same
  as any other one-hit skill; the self skills (Myrkr, Dagan) return no TP.

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

### En-spells

An en-spell is an additional effect on a physical swing, not a spell cast at the target.
The 0x028 melee result carries it in the additional-effect block: the proc kind is the
element (fire 1 .. dark 8), the value is the extra damage, and the message is 229
("additional points of damage"), which is what draws the second number.  The base follows
BG-wiki's [Enspell page](https://www.bg-wiki.com/ffxi/Category:Enspell):

```
skill < 180:   base = skill / 9 + 5
skill >= 180:  base = (skill - 180) / 8 + 25

damage = (base + merit + "Sword enhancement spell damage"+n)
         x (1 + "Sword enhancement spell damage"+x% + Composure x 2)
         x elemental resist x target MDT/DT
```

* **Tier I** (Enfire..Enwater) stores `base` when the spell lands and applies it to every
  landed swing of the round, including off-hand and multi-attack swings.
* **Tier II** (the level 50-60 IIs) applies only to the round's first swing.  Its base is
  recalculated from the current Enhancing Magic skill each round plus a hidden counter:
  the counter starts at 0 on the cast, rises by one per proc and the damage caps at
  `2 x base`.  The counter keeps rising past the cap, so raising the skill later lifts the
  damage immediately.  Recasting the en-spell resets it.
* **Enlight/Endark** use Divine/Dark Magic skill instead.  Tier I is
  `12 + 3 x (skill / 20) - skill / 40` and tier II the Job-Point Gift curve; the charge
  applies to every swing and decays by one per landed hit.  The remaining charge is also
  their Accuracy (Enlight) or Attack (Endark) bonus, which is why `combat_mods` reads it
  from the effect rather than baking it in at cast time.

Magic Attack Bonus, Magic Defense Bonus and the Magic Damage statistic do **not** apply;
BG-wiki says so explicitly, which is why a Sworn set's `Magic Damage+32` rows do nothing
for an en-spell while Enriching Sword's `Sword enhancement spell damage+30` does.  The
flat and percent gear lines are per hand: gear outside the main/sub slots applies to both
hands, a weapon's own line only to that weapon, so a dual-wielded pair is not
double-counting the other hand's line.

A worked number: a 500-skill RDM in the Sworn R30 suit (the five pieces carry +41 between
them) with the four job-point "En"-spell gifts (+23) and five En-spell merit ranks hits for
`(65 + 41 + 23 + 15) x 3 = 432` before resistance.  Crocea Mors's Path C adds its `+500%`
*inside* that bracket (`1 + 500/100 + 2`), not as a separate multiplication, so the same
hit becomes 1,152.

RDM's Composure triples the six elemental en-spells (the multiplier is 3.0, i.e. the
reference server's +200%), and the RDM group 2 "En-spell damage" merit adds 3 per rank,
five ranks at most.  Not modelled: staff/affinity multipliers, day/weather and the Obi,
the resistance-rank drop after a skillchain, and tier II's -10 elemental-resistance
debuff.  The resist term is the expected value of retail's five-tier roll against the
target's elemental Magic Evasion, with no Magic Accuracy roll of its own.

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

**Refresh**, **Regen** and **Regain** are passive three-second ticks from `tick_regen`; the same
dict carries the Auto Refresh/Auto Regen traits and the gear lines, so a reforged body with
`"Refresh"+4` restores 4 MP per tick and Karieyh Ring +1's `"Regain"+5` adds 5 TP. The tick reads
the HP/MP maxima from the stat sheet (and `flush_equipment` refreshes them after every outfit
batch), so swapping into gear that raises max HP/MP never leaves the character regenerating
against the previous set's cap. Regain stops at 3000 TP, the client's cap.

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
| Prime weapon stages, aftermath potency/tier and overwrite rule | `server/fanxi_server/game/prime_weapons.py` |
| En-spell base curve, tier II ramp, Enlight/Endark charge and resist | `server/fanxi_server/game/combat.py` |
| En-spell ids/tiers/elements and cast-time charge | `server/fanxi_server/game/effects.py`, `ZoneSession._buff_values` |
| En-spell proc on the swing and its 0x028 additional-effect block | `ZoneSession._enspell_hit`, `ZoneSession._resolve_swing`, `packets.battle_action` |
| Weapon and item data | `item_weapon` / `item_mods` tables (migrations `0080`, `0092`) |
| Item stats that depend on character state (Hoxne Earring) | `server/fanxi_server/game/item_effects.py` |
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
  The master-level STR above still raises fSTR and Attack, so a level-135 mob no longer
  hits with a level-99 damage rating *and* a level-99 Attack.
- **Level 100+ Defense/Evasion keep the 99-capped base curve.** The scaled VIT/AGI add
  to it, but LandSandBoat's `GetBaseDefEva` still uses its 5-per-level slope. The retail
  Locus values (1346 Defense / 1224 Evasion) would pin a level-99 player to the 20% hit
  floor until the player side models master-level accuracy. The offense was the reported
  bug, so it was calibrated first; this is the next knob if the tier needs to be fully
  retail-shaped.
- **`monster_templates.attack` / `defense` / `accuracy` / `evasion` are not read.** They
  are importer placeholders (`5 + 2*level`, `level/2`, `75 + level`, `10 + level`), not
  retail stats. The derived curve above is the authority; the columns stay for future
  family data.
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
  bundled rows for Odyssey (Nyame A-D), Limbus Rank 30, Unity Rank 15 and
  Oboro Dynamis-Divergence weapons (NQ/HQ1/HQ2), and the
  five-slot standard block for the Ambuscade job capes. The engine has no model only for
  pet stats, Snapshot, block rate, magic-burst II, spell interruption, the weapon `DMG:`
  rating and the Phalanx/Blood Pact lines; they are listed in
  `augment_stats.UNMODELLED` and a test walks every dataset row against that list.
- **Magic is a deterministic resist, not a tier roll.** The retail resist tiers are
  replaced by one multiplier in `combat.magic_resist`; there is no random full/half/quarter
  resist. Monsters do not cast yet, so a player's own MEVA/MDEF is only read when a
  monster-targeted spell is resolved against them.
- **En-spells keep the deterministic resist too.** The elemental-resistance term is the
  expected value of the five-tier roll (`combat.enspell_resist`), and the caster's Magic
  Accuracy is not rolled into it.
- **Elemental affinity and elemental resistances are not read by the nuke path.**
  `Fire MAB`, `Fire SDT` and the bar-spell family have no rows for the reforged sets, so
  only the generic `MATT`/`MDEF` are used.  The one exception is the en-spell resist term,
  which does read `FIRE_MEVA`..`DARK_MEVA` per hit.  The character sheet's eight element
  orbs are a different path: `0x061` `def_elem` reports the equipped
  `FIRE_MEVA`..`DARK_MEVA` totals, so the menu matches the tooltips even though no other
  damage formula has consumed them.
- **Magic burst, skillchains and casting-time gear** are not modelled. `MAGIC_BURST` and
  `"Elemental magic casting time -x%"` are stored in `item_mods` but nothing reads them.
  The per-skill damage, drain and status rows *are* implemented.
- **Weapon skills use physical, hybrid and magical paths.**  An archery/marksmanship
  row resolves through the ranged slot: the ranged weapon's DMG plus the ammo's DMG,
  Ranged Attack/Accuracy, the marksmanship/archery skill and the ranged weapon's delay
  for TP return.  A hybrid skill (`Hot Shot`, `Searing Arrow`, the elemental blade
  rows, ...) adds its magic half after the physical hits:
  `physical x fTP + Magic Damage`, then Weapon Skill Damage, Magic Attack Bonus against
  the target's Magic Defense Bonus, and the Magic Accuracy resist.  A
  `doMagicWeaponskill` row (Seraph Blade, Sanguine Blade, Aeolian Edge, Wildfire, ...)
  now uses the magical formula above: weapon-level base, WSC, fTP, dSTAT, Magic Damage,
  Weapon Skill Damage, elemental affinity, MAB/MDB, Magic Accuracy resist and MDT.  The
  Oboro path-C "Elemental weapon skill damage +100%" augment and the `*_MAB` affinity
  rows feed it; weather/day, staff affinity, resistance-rank reduction and magic
  critical hits are not modelled.  **Spirits Within** (current-HP formula),
  **Atonement** (enmity formula), **Moonlight** and **Starlight** (MP restore) do not
  use their special formulas either.  **Dagda** has no published fTP or stat modifiers,
  so it keeps the generic fallback curve.
- **Relic/Mythic/Empyrean aftermath are not modelled.**  Weapon-skill TP return, Save
  TP, Conserve TP, Hagakure and Meikyo Shisui are modelled (see "Weapon-skill TP
  return"); the Relic/Mythic/Empyrean aftermath buffs still need a weapon category and a
  second buff model.
  **Prime aftermath is modelled** for melee and ranged Prime weapons: the item's own
  weapon skill raises the physical damage limit by 2-8% (stage 3), 4-10% (stage 4) or
  6-12% (stage 5) from 1,000 to 3,000 TP, for 60/120/180 seconds by TP tier, and the
  activating skill itself gets the buff.  The tiers lock exactly like Mythic/Empyrean
  aftermath: level 1 refreshes itself, level 2 only yields to level 3, and level 3 never
  refreshes.  See [prime-weapon-skills.md](prime-weapon-skills.md) and
  `server/fanxi_server/game/prime_weapons.py`.  Staff (Oshala) and club (Dagda) have
  different aftermaths whose full TP scaling is not published, so they are not in the
  physical table yet.
- **Job traits are only read where the engine consumes their modifier.** Attack/Accuracy/
  Evasion/Defense bonus, Max HP/MP Boost, Store TP, Fast Cast, Dual Wield, Critical damage
  and the weapon-skill lines (WS Damage 840, TP Bonus 345/903, Fencer 904, WS Accuracy 48)
  flow into the sheet.  Double/Triple/Quadruple Attack are read by the attack round (see
  "Multi-attack").  Counter, Kick Attacks, Zanshin, Conserve MP, Subtle Blow, Occult
  Acumen, Shield Mastery/Tactical Parry/Guard and the killer/resist families are still
  inert: the modifier is in the trait table and the menu, but no combat path reads it.
  Store TP feeds auto-attack and weapon-skill TP; Conserve TP and Save TP are read by
  the weapon-skill return.
  **Killer Instinct** (BST merit, ability 162) is the exception, with one deliberate
  custom change: it puts status icon 349 on the bar for 180 s plus 10 s per merit
  rank past the first, and gives the **whole party in the zone** +15% physical
  damage dealt (read by `World.player_attack`, so every weapon-skill swing gets it)
  and a -15% `DMG` modifier for damage taken.  There is no 7.9-yalm check and the
  party copy is not reduced.  The Ankusa/Mst. Helm augment adds 4 s per merit rank
  (20 s at 5/5), and the **Diamond Aspis** adds 25%: with 5/5 merits the caster and
  every party member get **300 s (5:00)** and the full +15%/-15% effect.  The retail
  family check is not modelled yet because `monster_templates` has no family column,
  so the two bonuses currently apply to every target.  The icon, merit/helm
  duration, Diamond Aspis extension and recast are retail; the whole-party duration
  and range are the custom BST change.
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
  **Subtle Blow** is stored but inert because monsters do not accumulate TP.  **Regain**
  is paid by the passive tick, and a Tactician's Roll's Regain follows its own three-second
  effect tick.
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
