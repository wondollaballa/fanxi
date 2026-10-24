# Combat and progression coverage

An audit of Fanxi's combat engine against the retail pipeline, using LandSandBoat as the
reference implementation (the same source the stat, item and weapon-skill data come from).
`docs/combat-damage.md` remains the formula reference; this page is the status map and the
ordered backlog.

Status: **Done** means the path is implemented and covered by tests; **Partial** means the
main path exists but a retail mechanic is missing or approximated; **Missing** means no
combat path reads the data yet.

## Status map

| Area | Status | Where | What is still missing |
|---|---|---|---|
| Base attributes, HP/MP, Attack, Defense, Accuracy, Evasion | Done | `stats.py`, `base_stats.py`, `augment_stats.py` | Family ranks for monsters; some food sources |
| fSTR, pDIF, level correction, wRatio caps, spike, 1.00–1.05 roll, crit | Done | `combat.py` (`fstr`, `pdif`, `crit_rate`) | — |
| Hit rate | Done | `combat.py` (`hit_rate`) | Flash/Innin/Yonin/Closed Position and other situational accuracy terms |
| Multi-attack (DA/TA/QA) | Done | `combat.py` (`multi_attack_hits`), `zone.py` attack round | Virtue/Raetic follow-ups, "Occasionally Attacks X Times", Mythic aftermath, Zanshin/Hasso, WAR job-point gifts, Fighter's Roll/Temper/food |
| TP | Done | `combat.py` (`tp_delay`, `tp_return`), `stats.py` (`tp_per_hit`) | Monster TP gain and Subtle Blow (monsters have no TP moves); Ikishoten |
| Weapon skills | Partial | `zone.py` (`weaponskill`), `weapon_skill_effects.py`, `data/weapon_skills.json` | Multi-attack procs on WS, TP return, Relic/Mythic/Empyrean/Prime aftermath, magic-WS and ranged-WS paths, Spirits Within/Atonement/Moonlight/Starlight formulas, per-skill fTP/WSC for skills LSB only scripts as mob skills |
| Magic damage | Partial | `combat.py` (`_magic_finish`, `magic_damage`, `helix_damage`) | Resist tiers (1/1, 1/2, 1/4, 1/8, 0), elemental affinity/day/weather/staff/bar-spell terms, magic criticals, full per-spell multiplier tables |
| Magic burst / skillchains | Partial | `skillchain.py`, `data/skillchains.json`, `weapon_skills.sc` | Data and pure transition/state/damage core are done; runtime wiring, 0x028 add-effect block and MB are pending. MB also needs the magic hit-rate/resist-tier port. See [skillchains.md](skillchains.md) |
| Enmity | Done | `world.py` (`add_mob_hate`, `add_damage_hate`, `decay_mob_enmity`) | Claim lock (a second player cannot attack a claimed mob), linking, cure/cover/merit enmity terms, Enmity+/- gear |
| Parry / guard / shield block | Partial | `combat.py` (`_defence_roll`), `stats.py` | The proc rates are retail; the damage reductions are approximations, and the 0x028 result's 3-bit resolution still says hit/miss instead of parry/guard/block |
| Damage taken (PDT/MDT/DT/PDT-II) | Done | `combat.py` (`damage_taken`) | — |
| Ranged attacks / ammo / sweet spot | Missing | — | No ranged attack round, no ammunition, no distance accuracy penalty or damage curve |
| Hand-to-hand two fists, Kick Attacks, Daken, Zanshin | Missing | — | H2H is one swing per round; the extra swing types are not generated |
| Pets (avatars, wyverns, automatons, jug pets) | Missing | — | No pet entities, pet stat inheritance, Blood Pacts, attachments, pet TP or pet enmity pool |
| Skillchain state machine | Partial | `skillchain.py` (`SkillchainState`, `advance`, `TRANSITIONS`) | Pure state/timing/transition core and all 216 WS properties are imported; not yet called from `weaponskill` |
| Claim / linking | Partial | `world.py`, `packets.py` | First-attacker claim is shown; a second player is not blocked, and nearby family linking is not modelled |
| Packet layer | Partial | `packets.py`, `zone.py` | 0x028 supports multiple results and 0x00E carries claim/HP/animation; reaction flags (parry/block/guard) are not encoded |

## Corrections to the research brief

These are places a generic formula summary is easy to get wrong; the code follows LSB.

- **fSTR** is the tiered table (`stat_diff + 4/6/7/8/9/10/12/13`, then `/4`, clamped by
  weapon rank), not a bare `(STR - VIT + 4) / 4`. `combat.fstr` and
  `docs/combat-damage.md` have the exact table.
- **Hit rate** is `75 + (accuracy - evasion) / 2` on both sides of zero, then clamped to
  20–99% (20–95% for two-handed/off-hand/mobs). There is no `/3` branch when accuracy is
  higher; LSB's `physical_hit_rate.lua` confirms `/2`.
- **TP is per landed hit, from that hand's weapon delay.** There is no "first hit full TP,
  later hits 10 TP" rule. Dual Wield halves each hand's reduced delay, so a 227 main hand
  and a 190 off hand pay different amounts.
- **Multi-attack priority is per hand: Quadruple > Triple > Double.** Kick Attacks and
  Daken are separate swing types, not checks in that chain; Mythic aftermath and
  "Occasionally Attacks X Times" sit below Double. The round is capped at eight results.
- **MAB/MDB is the ratio `(100 + MATT) / (100 + target MDEF)`**, not a multiply by
  `(1 + MATT/100)` followed by a separate `(1 - MDEF/100)`. Magic Damage joins the base
  before the ratio. Fixed in `combat._magic_finish`.
- **Weapon-skill first-hit accuracy** is not a blanket +100. LSB passes per-skill accuracy
  bonuses; Fanxi already adds the `WS_ACCURACY` (48) gear line and the skill's own terms.
  Any missing bonus should be added per skill from the script, not globally.
- **Magic burst** is not the 1.35/1.45/1.55 table: for a neutral target the base is
  `1.25 + rankTable[rank+4] + 0.1 * tier` = **1.85× at the first link**, and the gear
  bonus is +40% capped / uncapped (not a +30% II cap).  It also needs the magic hit-rate
  and resist-tier port before it can add its +100 MAcc on the right scale.  See
  [skillchains.md](skillchains.md).
- **Enmity** is two meters (CE/VE), not one total: damage adds 80/240 scaled by
  `level × 31/50 + 6`, VE drains 60/s, each meter caps at 30,000, Provoke is 1,800 CE, and
  the first hitter gets 200 CE + 900 VE. Fixed this pass; claim lock/linking are still open.

## Recommended order

1. **Skillchains and Magic Bursts** — the biggest missing engagement loop.  The property
   data, 29-pair transition map and pure state/damage core are done; next is the runtime
   in `weaponskill` plus the 0x028 add-effect block, then the magic hit-rate/resist tiers,
   then MB.  See [skillchains.md](skillchains.md) for the exact stages.
2. **Pets** — avatars, wyverns, automatons and jug pets. This is a separate entity and stat
   path; the cape/augment data already carries pet modifier names, but no pet pool exists.
3. **Ranged attacks** — ammunition, delay, sweet-spot distance, RAcc/RAtt, ranged WS.
4. **Hand-to-hand two fists plus Kick Attacks, Daken and Zanshin** — the remaining auto-attack
   swing types.
5. **Magic resist tiers and elemental affinity** — replace the single deterministic resist
   multiplier with the tier roll, then add day/weather/staff/bar-spell terms.
6. **Weapon-skill multi-attack and TP return**, then aftermath.
7. **Enmity claim lock/linking and the 0x028 parry/guard/block resolution flags.**

Do not start from the formula summary alone; the reference scripts and the
`docs/combat-damage.md` sources are the tie-breakers.
