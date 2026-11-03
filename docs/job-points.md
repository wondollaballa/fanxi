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
- **Gift spells are real spells for their job.** `job_points.SPELL_GRANTS` maps each job's
  "New Spell(s)" rows to the spells table.  A level-99 main job can cast and see them in
  `0x0AA`; no other job can.  For Red Mage that is the Fire V line (100 JP), Addle II /
  Distract III / Frazzle III (550 JP) and Refresh III / Temper II (1200 JP) — the Fire V
  line is also a Black Mage/Scholar level row, so those jobs keep it by level instead.
  Scholar's 100-JP Storm II line and 1200-JP Helix IIs are in the same table; the Storm IIs
  have no ordinary level row, so the gift is what opens them.
- **The "En"-spell gift is flat En-spell damage.**  Red Mage's four rows total +23 and are
  applied to every landed en-spell hit on both hands (`mod.ENSPELL_DMG_BONUS`).
- **Red Mage Quick Magic** is a 5% instant-cast proc; its "Quick Magic Effect" ranks
  refund 2% of the spell's MP cost each (40% at rank 20) when the proc fires.
- **The ★Master! gift shortens the two-hour recast.**  Its 15 minutes are stored as
  `mod.ONE_HOUR_RECAST` and taken off the per-ability cooldown sent in `0x119` slot 0
  for the current main job.
- **The Scholar "Stratagem Recast Time" gift is applied.**  Its 15 seconds come off every
  charge in the HUD's clock (`job_points.stratagem_recharge_seconds`, mirrored in
  `host/addons/lua/sch.lua`), so a level-99 Scholar recharges a charge every 33 seconds.
- **The Scholar group-1 merits are applied** through `zone._sch_merit`: Grimoire Recast
  (2 s a rank off Light/Dark Arts), Max Sublimation (+10 MP a rank), Helix Magic Acc./Atk.
  (+3 M.Acc / +2 MAB a rank on Helix spells) and Modus Veritas Duration (5% less duration
  penalty a rank).

## Not yet applied

These remaining rows need pet/avatar command models, song potency systems, chance/rate
systems, or unique job mechanics that are not built yet.

### White Mage

Bar Spell Effect

### Beastmaster

Charm Success Rate, Run Wild Duration

The **player-facing** BST gifts are applied: Attack/Ranged Attack +70, Accuracy/Ranged
Accuracy +70, Defence +70, Evasion +36, Magic Evasion +36, Magic Accuracy +36, and
Fencer TP Bonus +230 (on top of the 400-point trait).  The only BST gift rows still
missing are the pet-only rows listed below.  Fencer's TP bonus is conditional: it needs
a one-handed main weapon and an empty sub, grip or shield.  A dual-wielded sub weapon
turns Fencer off, and the weapon-skill TP term is capped at 3000 anyway, so a WS at full
TP does not gain from it.  BST has no player Weapon Skill Damage gift.

### Ninja

Tactical Parry Effect

### Dragoon

Wyvern Breath Effect

### Corsair

Bust Evasion, Ammo Consumption, Optimal Range

### Puppetmaster

Heady Artifice Effect, Activate Effect, Cooldown Effect, Deactivate Effect

### Scholar

Stratagem Effect IV (the client owns spell recast, so the server has no hook for the
2%-a-rank spell-recast reduction)

### Geomancer

Life Cycle Effect, Concentric Pulse Effect, Indicolure Spell Effect Dur.

### Rune Fencer

Rune Enchantment Effect

Remaining category rows: **1** (Scholar's Stratagem Effect IV, above).

## Gift rows not modelled as stats

Capacity Point bonuses, Superior levels, new songs/ninjutsu, pet/automaton/avatar bonuses,
Treasure Hunter, ammunition and similar remain in the table and are listed here for the
next pass.

- **Warrior**: double rate attack
- **Monk**: counter damage
- **Thief**: "treasure hunter" bonus, maximum treasure hunter value
- **Paladin**: protect effect
- **Dark Knight**: dread spikes effect
- **Beastmaster**: familiar phys. acc. and eva. bonus, familiar phys. atk. and def. bonus, familiar tp bonus, pet attribute bonus, sic and ready recast time
- **Bard**: song effect duration is applied as a +5% song-duration gift; the song spellcasting time gift is applied to songs only (it no longer shortens Cure or other spells).
- **Ranger**: "conserve tp" effect bonus, barrage effect, conserve tp effect bonus, dead aim effect, true shot effect, velocity shot effect
- **Samurai**: "zanshin" chance bonus, hasso and seigan effect, third eye effect, zanshin chance bonus, zanshin effect bonus
- **Ninja**: daken effect, ninjutsu effect duration
- **Dragoon**: restoring/smiting breath delay, wyvern attribute increase effect, wyvern mag. acc. and eva. bonus, wyvern phys. acc. and eva. bonus
- **Summoner**: avatar's favor effect, avatar/spirit mag. acc. & eva. bonus, avatar/spirit mag. atk. & def. bonus, avatar/spirit phys. acc. & eva. bonus, avatar/spirit phys. atk. & def. bonus, blood pact recast time, spirit and avatar magic attack and defense bonus, spirit and avatar physical attack and defense bonus, spirit and avatar's physical accuracy and physical evasion bonus, spirit/avatar mag. acc. & eva. bonus
- **Blue Mage**: blue magic effect, job trait bonus, jobs trait bonus
- **Corsair**: quick draw delay, reduced ammunition consumption, snapshot effect, true shot effect
- **Puppetmaster**: automaton elemental capacity bonus, automaton mag. acc. and eva. bonus, automaton mag. atk. and def. bonus, automaton phys. acc. and eva. bonus, automaton phys. atk. and def. bonus, automaton physical accuracy and physical evasion bonus, automaton physical attack and defense bonus
- **Dancer**: maximum finishing moves bonus
- **Rune Fencer**: enh. magic received duration, enhancing magic received duration, inquartata effect
