# Skillchains and Magic Bursts

This is the verified design for the skillchain state machine and Magic Burst pipeline.
It follows LandSandBoat's implementation rather than a generic formula summary.  The
pure logic is in `server/fanxi_server/game/skillchain.py`, the weapon-skill properties
are in `data/skillchains.json`, and the runtime is **not wired yet** (see the stages at
the end).

## What the reference actually does

### Properties and ids

`data/enums/skillchain_type.yaml` assigns **sequential** ids, not bit flags:

| Id | Chain | Tier | Element(s) |
|---:|---|---:|---|
| 0 | none | 0 | — |
| 1 | Transfixion | 1 | Light |
| 2 | Compression | 1 | Dark |
| 3 | Liquefaction | 1 | Fire |
| 4 | Scission | 1 | Earth |
| 5 | Reverberation | 1 | Water |
| 6 | Detonation | 1 | Wind |
| 7 | Induration | 1 | Ice |
| 8 | Impaction | 1 | Thunder |
| 9 | Gravitation | 2 | Dark, Earth |
| 10 | Distortion | 2 | Water, Ice |
| 11 | Fusion | 2 | Light, Fire |
| 12 | Fragmentation | 2 | Wind, Thunder |
| 13 | Light | 3 | Light, Fire, Wind, Thunder |
| 14 | Darkness | 3 | Dark, Earth, Water, Ice |
| 15 | Light II | 4 | Same as Light |
| 16 | Darkness II | 4 | Same as Darkness |

A weapon skill carries three properties.  The opening WS packs them as
`primary | (secondary << 4) | (tertiary << 8)` into the `Skillchain` status effect's
power; a formed chain stores the single `SC_*` id instead.  **Do not use `auto()` bit
flags** for the ids: 1/2/4/8 do not match the client, the SQL columns, or the proc ids.

The properties come from `weapon_skills.sql` (`primary_sc`, `secondary_sc`,
`tertiary_sc`).  This tree has 216 weapon skills, not 34.  The reference SQL comments out
several Prime skills; their properties are taken from their BG-wiki pages.  Exudation is
also absent from the reference SQL and comes from BG-wiki.  Examples:

| WS | Properties |
|---|---|
| Tachi: Gekko | Distortion, Reverberation, none |
| Tachi: Kasha | Fusion, Compression, none |
| Vorpal Blade | Scission, Impaction, none |
| Zesho Meppo | Induration, Reverberation, Fusion |

### Transition map

`FormSkillchain(resonance, skill)` loops over the **existing resonance** first and the
**closing skill's properties** second, and looks up `(skill_property,
resonance_property)`.  There is **no tier-precedence pass**; the first pair found in the
reference map wins.  The map is directional.  Examples that are easy to get backwards:

| Existing resonance | Closing WS property | Result |
|---|---|---|
| Liquefaction | Impaction | Fusion |
| Impaction | Liquefaction | Liquefaction |
| Transfixion | Scission | Distortion |
| Scission | Transfixion | none |
| Detonation | Compression | Gravitation |
| Induration | Reverberation | Fragmentation |
| Distortion | Fusion | Fusion (Gekko → Kasha) |
| Fusion | Distortion | none |
| Fusion | Fragmentation | Light |
| Gravitation | Distortion | Darkness |
| Light | Light | Light II |
| Darkness | Darkness | Darkness II |

The full 29-pair table is in `skillchain.TRANSITIONS`, transcribed from
`battleutils.cpp`'s `skillchain_map`.

### State and timing

From `GetSkillChainEffect`:

1. **Opening WS.** No skillchain forms.  A `Skillchain` effect is stored on the target:
   tier 0, power = packed properties, duration **10 s**, start = now.
2. **Next WS.**  The call is skipped entirely when the WS misses, the target is dead, or
   the WS's primary property is 0 (LSB gates on `primary_sc != 0`).  Otherwise:
   - If the effect is **absent or expired**, the new WS becomes the opening.
   - If the new WS lands **at or before 3.0 s** after the start, it does **not** chain;
     it replaces the opening state with its own properties and a fresh 10 s window.
   - If it lands **after 3.0 s and before expiry**, try `FormSkillchain`.
   - No match → replace the opening with the new WS's properties.
   - Match → the state becomes tier = SC tier, power = SC id,
     count = `min(count + 1, 5)`, start = now, and duration = **old duration − 1 s**
     (10 → 9 → 8 …).
3. Every successful link counts as one step; the first link is count 1.  The maximum
   count is 5.
4. A weapon skill with no properties does not touch the state.  A miss or a dead target
   does not touch it either (the LSB gate is inside the landed-hit/HP>0 branch).

The often-quoted "3.0 to 9.5 s" window is wrong: the closing WS must be **strictly more
than 3 s** after the opening/last link, and the effect expires 10 s after it was created
(9 s after the first link, 8 s after the second, …).

### Skillchain damage

The base is the **closing weapon skill's total damage**, not a separate roll.  The
reference table is:

| Tier | Count 1 | 2 | 3 | 4 | 5 |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
| 2 | 0.60 | 0.75 | 1.00 | 1.25 | 1.50 |
| 3 | 1.00 | 1.50 | 1.75 | 2.00 | 2.25 |
| 4 | 1.50 | 1.80 | 2.10 | 2.40 | 2.70 |

The order in `scripts/combat/skillchain.lua` is (floor after each step):

```
damage = abs(closing_ws_damage) * tier_count_multiplier
damage = damage * (1 + SKILLCHAINBONUS/100) + MAGIC_DAMAGE
damage = damage * (1 + SKILLCHAINDMG/10000)
damage = damage * day/weather * staff * affinity * resistance_rank * magic_taken
damage = clamp(damage, 0, 99999)
```

Only the skillchain bonus/damage, flat Magic Damage, resistance rank and damage-taken
terms are implemented in `skillchain.skillchain_damage`; day/weather/staff/affinity are
deferred.  `MAGIC_DAMAGE` is added after the bonus multiplier, before Skillchain Damage.
The resistance rank defaults to 0 (multiplier 1.0) because Fanxi's monsters do not carry
elemental resistance ranks yet.

### The action packet

The skillchain is **not a separate 0x028 action**.  It is the closing WS result's
**additional-effect block**:

- `has_add_effect = 1`
- `proc_kind` (6 bits) = `ActionProcSkillChain`, which is a **permutation** of the
  `SC_*` ids:
  Light 1, Darkness 2, Gravitation 3, Fragmentation 4, Distortion 5, Fusion 6,
  Compression 7, Liquefaction 8, Induration 9, Reverberation 10, Transfixion 11,
  Scission 12, Detonation 13, Impaction 14.
  Light II uses Light (1) and Darkness II uses Darkness (2).
- `proc_info = 0`
- `proc_value` (17 bits) = skillchain damage
- `proc_message` (10 bits) = `287 + proc_kind` for damage, `384 + proc_kind` for absorb.

Fusion therefore uses proc 6 and message 293; Light II uses proc 1 and message 288.
The existing 0x028 builder must learn this block; it currently writes two zero flags for
"no additional effect" and "no reaction effect" per result.

### Magic Burst

Magic Burst is tracked on the same target state.  A spell can burst when:

1. the SC state is formed (`tier > 0`) and has not expired;
2. the spell is elemental (Fire–Darkness); and
3. the spell's element is one of the SC's elements (the element table above).

The **burst tier is the chain count**, 1–5, not the SC tier.

The reference's base multiplier is:

```
rankTable = {1.50, 1.15, 0.85, 0.60, 0.50, 0.40, 0.15, 0.05, 0, ...}
rank      = clamp(target elemental resistance rank, -3, 11) + 4
multiplier = 1.25 + rankTable[rank] + 0.10 * burst_tier     -- PC
```

For a neutral target that is **1.85× at the first link**, rising to **2.25× at the
fifth** — not the 1.35/1.45/1.55 table in the draft.  Gear/traits add:

```
bonus = 1 + min(0.40, MAGIC_BURST_BONUS_CAPPED / 100)
          + MAGIC_BURST_BONUS_UNCAPPED / 100
```

`MAGIC_BURST_BONUS_CAPPED` (mod 487) caps at +40%; `MAGIC_BURST_BONUS_UNCAPPED` (mod
274) is **not** capped at +30%.  Magic Burst also adds a flat **+100 Magic Accuracy**;
the client is told with message **252** (`274` for HP drains), not a separate flag.

**Prerequisite:** Fanxi's current `combat.magic_resist` is a deterministic 0.5–1.0
multiplier, not LSB's Magic Accuracy hit rate and 1/1 → 1/2 → 1/4 → 1/8 resist tiers.
Until that is ported, a "+100 MAcc" or a "1.85× MB" cannot be applied on the same scale
the reference uses.  Magic Bursts should therefore land in a stage after the magic
hit-rate/resist work, not in the same change as the skillchain state machine.

## Corrections to the proposed architecture

| Proposed | Actual |
|---|---|
| `IntFlag` bitmask with `auto()` for SC properties | Sequential ids 1–16; store a 3-tuple per WS |
| Transition table with `(A, B)` tier precedence | Directional 29-pair `skillchain_map`, first match in resonance/property order |
| E.g. `(Liquefaction, Impaction) -> Fusion` | Correct only when Liquefaction is the **resonance** and Impaction the **closing** property; reversed gives Liquefaction |
| `(Detonation, Scission) -> Gravitation`, `(Transfixion, Scission) -> Fragmentation` | Both wrong; Gravitation is Detonation→Compression, Fragmentation is Induration→Reverberation |
| Opening window `now+3` to `now+9.5` | Opening is 10 s; the close must be **strictly >3 s**; after a link the duration is 9 s and drops 1 s per link |
| SC damage "Level 1 50%, Level 2 60%, Level 3 100%, scaling per step" | Correct for the first link; the full `chainMultipliers[tier][count]` table applies and count caps at 5 |
| SC emitted as its own action/animation | Additional-effect block on the closing WS result, with a proc id and `287+proc` message |
| Magic Burst sets a flag | Set message 252 (274 for drain); the damage is the normal result value |
| MB base 1.35/1.45/1.55/1.65 | 1.85/1.95/2.05/… for a neutral target with five chain steps max |
| MB II capped at +30% | Capped mod 487 at 40%, uncapped mod 274 has no cap |
| MB grants +100 to +150 MAcc | Exactly +100 |
| Add SC to 34 WS | 216 WS; Prime and Exudation properties come from BG-wiki |
| Magic Burst can be wired into `_magic_finish` now | It needs `spell.element` and the magic hit-rate/resist-tier port first |

## Implementation stages

- **A. Data and pure logic — done.** `data/skillchains.json`, `weapon_skills.sc`,
  `skillchain.py` (ids, map, state, damage, MB helpers), 24 tests in
  `server/tests/test_skillchain.py`.
- **B. Runtime skillchains.** Add `SkillchainState` to the monster, call
  `skillchain.advance` from `ZoneSession.weaponskill` only on a landed, non-lethal hit
  with `primary_sc != 0`, compute the closing-WS-based damage, apply it, and attach the
  add-effect block to the last WS result.  Extend the 0x028 builder for the optional
  additional-effect block.
- **C. Magic hit rate and resist tiers.** Port the relevant parts of
  `scripts/combat/basic/magic_hit_rate.lua`: `macc - meva + 25`, `(50 + hit)/100`
  clamped 5–95%, three successive resist rolls, 1/2^tier.  Add RNG injection and update
  the spell tests.  This is the prerequisite for a correct MB.
- **D. Magic Burst.** Pass `spell.element` into the magic path, compute the burst tier
  from the target state, apply `magic_burst_multiplier` and `magic_burst_bonus`, add the
  +100 MAcc, and set message 252.
- **E. Verification.** Packet decode tests (add-effect block), multi-step chain tests,
  a LSB cross-check table, and live log lines for each SC/MB event.

## Sources

- [LandSandBoat `battleutils.cpp`](https://github.com/LandSandBoat/server/blob/base/src/map/utils/battleutils.cpp) — `FormSkillchain`, `GetSkillChainEffect`, `GetSkillchainTier`, `skillchain_map`.
- [`scripts/combat/skillchain.lua`](https://github.com/LandSandBoat/server/blob/base/scripts/combat/skillchain.lua) — damage multipliers, resistance ranks, element choice.
- [`scripts/combat/basic/magic_burst.lua`](https://github.com/LandSandBoat/server/blob/base/scripts/combat/basic/magic_burst.lua) — element match and tier.
- [`scripts/globals/spells/damage_spell.lua`](https://github.com/LandSandBoat/server/blob/base/scripts/globals/spells/damage_spell.lua) — MB multiplier, bonus cap, +100 MAcc.
- [`scripts/combat/basic/magic_hit_rate.lua`](https://github.com/LandSandBoat/server/blob/base/scripts/combat/basic/magic_hit_rate.lua) — hit-rate and resist tiers.
- [`data/enums/skillchain_type.yaml`](https://github.com/LandSandBoat/server/blob/base/data/enums/skillchain_type.yaml) — SC ids.
- [`data/enums/action/proc_kind.h`](https://github.com/LandSandBoat/server/blob/base/src/map/enums/action/proc_kind.h) — 0x028 proc ids.
- [`sql/weapon_skills.sql`](https://github.com/LandSandBoat/server/blob/base/sql/weapon_skills.sql) — `primary_sc`/`secondary_sc`/`tertiary_sc`.
- BG-wiki Skillchain/WS pages for the Prime skill properties missing from the SQL.
