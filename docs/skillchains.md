# Skillchains and Magic Bursts

This is the verified design for the skillchain state machine and Magic Burst pipeline.
It follows LandSandBoat's implementation rather than a generic formula summary.  The
pure logic is in `server/fanxi_server/game/skillchain.py`, the weapon-skill properties
are in `data/weapon_skill_properties.json`/`data/skillchains.json`, and the runtime is
wired into `ZoneSession.weaponskill` and the magic path (see the stages at the end).

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
| Maru Kala | Detonation, Compression, Distortion |

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

### Self-chains

A skill can close its own chain because each weapon skill carries three properties and
the matcher walks them in the stored order.  Maru Kala is the clean three-step example:

1. first Maru Kala opens with `(Detonation, Compression, Distortion)`;
2. second Maru Kala matches **Compression against Detonation** → **Gravitation**;
3. third Maru Kala matches **Distortion against Gravitation** → **Darkness**.

The properties come from `data/weapon_skill_properties.json` (Maru Kala is id 231).
The chain is still subject to the runtime rules below: each close must land **more than
3 s** after the previous skill and inside the 11 s opener / 10 s Gravitation window, and
each cast spends 1,000 TP.  A planner that only checks properties (the web chain builders
people use) will show Gravitation and Darkness even when the TP cycle or the 3 s lockout
makes the sequence impossible in play.

The in-game Battle hub planner and the control HUD carry the same property table; both
are generated from `data/weapon_skill_properties.json`, and
`test_skillchain.AddonSkillchainTableTest` pins them to it.

### Scholar's Immanence: spells as weapon skills

Immanence gives the next damaging elemental spell the weapon-skill property of its
element, so a Scholar can open and close a chain with two casts.  The element map is
`skillchain.ELEMENT_TO_SC`, keyed by the server's 1-based `spells.element`:

| Element | Property | Element | Property |
|---|---|---|---|
| Fire | Liquefaction | Water | Reverberation |
| Ice | Induration | Light | Transfixion |
| Wind | Detonation | Dark | Compression |
| Earth | Scission | Thunder | Impaction |

A spell carries exactly **one** property.  The first Immanence spell goes through the
same `skillchain.advance()` as a weapon skill, so it opens the 11 s window; the next
one must land more than 3 s after it and inside the window.  Stone (Earth/Scission) then
Pyrohelix (Fire/Liquefaction) forms Liquefaction; Aero (Wind/Detonation) then
Noctohelix (Dark/Compression) forms Gravitation.  The closing spell's **own damage** is
the chain's base exactly as a closing weapon skill's is, and the chain's
additional-effect block rides that spell's finished-magic `0x028` result, so the client
plays the skillchain from the cast.

`ZoneSession._magic_skillchain()` is the entry point.  It is called from both damaging
magic paths -- a plain nuke and a Helix -- after the spell's own hit has landed, while
the target is still alive.  Immanence is spent by the spell whether or not it forms a
chain (a killing hit spends it and chains into nothing); a zero-damage or non-elemental
spell leaves it up.  Because the chain state is the same one Magic Burst reads, the
burst list the Scholar HUD runs after the closing spell bursts normally: matching the
chain's element, with the link count as the burst tier.

The HUD side of this is documented in [control-panel.md](control-panel.md): the
Scholar window's tabs, macros, strategem clock and the runner's recast- and
cast-bar-based timing.

### State and timing

From `GetSkillChainEffect`:

1. **Opening WS.** No skillchain forms.  A `Skillchain` effect is stored on the target:
   tier 0, power = packed properties, duration **11 s**, start = now.
2. **Next WS.**  The call is skipped entirely when the WS misses, the target is dead, or
   the WS's primary property is 0 (LSB gates on `primary_sc != 0`).  Otherwise:
   - If the effect is **absent or expired**, the new WS becomes the opening.
   - If the new WS lands **at or before 3.0 s** after the start, it does **not** chain;
     it replaces the opening state with its own properties and a fresh 11 s window.
   - If it lands **after 3.0 s and before expiry**, try `FormSkillchain`.
   - No match → replace the opening with the new WS's properties.
   - Match → the state becomes tier = SC tier, power = SC id,
     count = `min(count + 1, 5)`, start = now, and duration = **11 s for a level-1
     link**; a level-2/3 link gets **old duration − 1 s** (11 → 10 → 9 …).
3. Every successful link counts as one step; the first link is count 1.  The maximum
   count is 5.
4. A weapon skill with no properties does not touch the state.  A miss or a dead target
   does not touch it either (the LSB gate is inside the landed-hit/HP>0 branch).

The closing WS must be **strictly more than 3 s** after the opening/last link.  Fanxi's
window is one second longer than AutoSkillchains' (`delay 3 + 8 − step`): the opener is
**11 s**, a level-1 link keeps **11 s**, and a level-2/3 link shrinks by one second per
step (10/9/8… for the wide chains).  That makes the Fusion-to-Light window 10 s (3 s
lockout + 7 s to close) and the 4th step 9 s (6 s after the lockout).  The server accepts
a close up to **0.5 s after** that boundary, which is the status-effect container's tick;
without it a close at exactly the 10.0 s or 9.0 s mark loses the chain even though the
same close works in retail.

**Level-1 loops are deliberately infinite on Fanxi.**  In retail every link shrinks the
window, so `Savage Blade → Hot Shot → Savage Blade` dies once the window falls below the
player's WS cadence unless the closer wears the **Diamond Aspis** (item `26488`).  COR,
the job that owns both of those skills, cannot equip the Aspis (WAR/WHM/RDM/THF/PLD/BST
only), which made the classic loop impossible here.  A level-1 link therefore keeps the
full 11 s window; the level-2/3 chains still shrink exactly as retail does.  The Aspis
remains the exception for those wider chains: when the closing weapon skill's owner wears
it, the next window is **11 s at every step** (the Battle hub planner has the same
per-closer checkbox).

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

The final clamp is `combat.DAMAGE_CAP` (99,999), the same ceiling every other damage
event uses: a capped 99,999 closing weapon skill times a tier-3 link still prints at
most 99,999, not 149,998.  The closing weapon skill's own total is capped before it is
used as this base, so the two lines of a 99,999 WS + 99,999 SC chain are each the most
the client can show.

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
`packets.battle_action` writes the block, and `ZoneSession.weaponskill` puts it on the
closing weapon skill's result.  A separate 0x028 with the same message prints a chat line
but carries no add-effect, so the client does not play the skillchain animation.

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
| Opening window `now+3` to `now+9.5` | Opening is 11 s; the close must be **strictly >3 s**; a level-1 link keeps 11 s, a level-2/3 link drops 1 s per link.  A close up to 0.5 s past the boundary is accepted (status-tick grace); Diamond Aspis keeps the next window at 11 s at every tier |
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
  `skillchain.py` (ids, map, state, damage, MB helpers), the tests in
  `server/tests/test_skillchain.py`.
- **B. Runtime skillchains — done.** `SkillchainState` lives on the monster;
  `ZoneSession._advance_skillchain` runs from `weaponskill` on a landed, non-lethal hit
  with properties, and `ZoneSession._magic_skillchain` runs from the two damaging spell
  paths when Immanence is up.  Both go through `_advance_chain`, compute the closing hit's
  damage, apply it, and return the add-effect block that rides that closing result (the
  weapon skill's result or the finished spell's result).  The state is cleared by
  `kill_mob`/`reset_mob`, so a respawn cannot inherit the previous life's chain (which
  let the first WS of a new fight close a chain nobody opened).  `SkillchainState.opener`
  records who opened it, and the log line names the `via` action, `closer`, `opener` and
  `target`.
- **C. Magic hit rate and resist tiers — partial.** `combat.magic_resist` is still the
  deterministic 0.5–1.0 approximation; the full three-roll 1/2^tier model is pending.
- **D. Magic Burst — wired to the deterministic model.** `spell.element` reaches the
  state, the burst tier/multiplier, the `MAGIC_BURST_BONUS_CAPPED` / `..._UNCAPPED`
  bonus (the Red Mage trait is 274; SCH/BLM job points and gear are 487) and message
  252 are applied; the +100 MAcc rides the deterministic resist roll, and the exact
  resist tier waits on stage C.
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
