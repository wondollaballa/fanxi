# Job points in Fanxi

Source: [BG-wiki Job Points](https://www.bg-wiki.com/ffxi/Job_Points).  The generated table is
`data/job_points.json`; every job is sent rank 20 in all ten categories and 2,100 JP spent.
`data/job_ability_status.json` maps ability categories to their client status ids.

## Implemented

- Every gift row contributes its static stat/percentage or skill bonus to `combat_mods()` /
  `skills.caps_for()`, including every skill-gift row.
- Passive category rows are applied at rank 20.
- Ability statuses and category hooks cover all jobs; pets/avatars, COR rolls, Bard songs,
  Dancer steps/flourishes, SCH Sublimation, Blue Magic, and most instant abilities are wired.
- A generic ability-status layer reads mapped ability categories for plain stats, duration
  and recast.
- Su5 equipment access and the Master stars are already sent by the zone packets.

## Not yet applied

These remaining rows need pet/avatar command models, song potency systems, chance/rate
systems, or unique job mechanics that are not built yet.

### White Mage

Bar Spell Effect

### Beastmaster

Charm Success Rate, Run Wild Duration

### Ninja

Tactical Parry Effect

### Dragoon

Wyvern Breath Effect

### Corsair

Bust Evasion, Ammo Consumption, Optimal Range

### Puppetmaster

Heady Artifice Effect, Activate Effect, Cooldown Effect, Deactivate Effect

### Scholar

Stratagem Effect IV

### Geomancer

Life Cycle Effect, Concentric Pulse Effect, Indicolure Spell Effect Dur.

### Rune Fencer

Rune Enchantment Effect

Remaining category rows: **0**.

## Gift rows not modelled as stats

Capacity Point bonuses, Superior levels, new spells/songs/ninjutsu, Master one-hour recast,
pet/automaton/avatar bonuses, Treasure Hunter, stratagem recast, enspell damage, ammunition
and similar remain in the table and are listed here for the next pass.

- **Warrior**: double rate attack
- **Monk**: counter damage
- **Red Mage**: "en"spell damage, enspell damage
- **Thief**: "treasure hunter" bonus, maximum treasure hunter value
- **Paladin**: protect effect
- **Dark Knight**: dread spikes effect
- **Beastmaster**: familiar phys. acc. and eva. bonus, familiar phys. atk. and def. bonus, familiar tp bonus, pet attribute bonus, sic and ready recast time
- **Bard**: song effect duration
- **Ranger**: "conserve tp" effect bonus, barrage effect, conserve tp effect bonus, dead aim effect, true shot effect, velocity shot effect
- **Samurai**: "zanshin" chance bonus, hasso and seigan effect, third eye effect, zanshin chance bonus, zanshin effect bonus
- **Ninja**: daken effect, ninjutsu effect duration
- **Dragoon**: restoring/smiting breath delay, wyvern attribute increase effect, wyvern mag. acc. and eva. bonus, wyvern phys. acc. and eva. bonus
- **Summoner**: avatar's favor effect, avatar/spirit mag. acc. & eva. bonus, avatar/spirit mag. atk. & def. bonus, avatar/spirit phys. acc. & eva. bonus, avatar/spirit phys. atk. & def. bonus, blood pact recast time, spirit and avatar magic attack and defense bonus, spirit and avatar physical attack and defense bonus, spirit and avatar's physical accuracy and physical evasion bonus, spirit/avatar mag. acc. & eva. bonus
- **Blue Mage**: blue magic effect, job trait bonus, jobs trait bonus
- **Corsair**: quick draw delay, reduced ammunition consumption, snapshot effect, true shot effect
- **Puppetmaster**: automaton elemental capacity bonus, automaton mag. acc. and eva. bonus, automaton mag. atk. and def. bonus, automaton phys. acc. and eva. bonus, automaton phys. atk. and def. bonus, automaton physical accuracy and physical evasion bonus, automaton physical attack and defense bonus
- **Dancer**: maximum finishing moves bonus
- **Scholar**: stratagem recast time
- **Rune Fencer**: enh. magic received duration, enhancing magic received duration, inquartata effect
