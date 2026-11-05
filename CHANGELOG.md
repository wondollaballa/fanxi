# Changelog

## Unreleased — all 22 JSE necks augment at Oboro

- **Oboro now augments the JSE necks, not just the Dynamis-Divergence weapons.** All 22 necks
  × three qualities (NQ R15, +1 R20, +2 R25) are in `data/oboro_r25.json` and the Data page's
  Oboro card, grouped under **JSE necks**. A neck has one path; its three qualities share the
  job's client bundle (199-220, FFXI job order), and the block's rank/tier prints the R15,
  R20 or R25 row. Capping writes the same 24-byte `AugmentBundle` block the weapons use and
  sends `//reload` to a live client, so the neck's tooltip shows its three augment lines.
- **The RDM neck is real gear now.** `Duelist's Torque +2` (bundle 203) at R25 is INT/MND +15,
  enhancing magic duration +25% and enfeebling magic duration +25%; `augment_stats` maps the
  last row to `ENF_MAG_DURATION`, so `debuff_duration` extends Sleep/Bind/Slow/Paralyze casts
  and the stat sheet gains an **Enfeebling magic duration +%** row alongside the job-point
  seconds. The BLU neck's `Crit Rate` maps to critical hit rate, the THF neck's `Trip. Atk.`
  to Triple Attack, and the remaining job-system rows (Daken, Kick Attacks, Helix duration,
  Magic Burst DMG/ACC, Luopan/Wyvern/Avatar/Automaton/Pet rows) are listed in `UNMODELLED` so
  the coverage test keeps walking every dataset row.
- **The launcher card is generic.** The Oboro dropdown groups **JSE weapons** and **JSE necks**,
  the info row says `Neck` instead of `Main hand`, and a one-path neck gets a full-width Cap
  row instead of the three-path grid. A missing neck can be bought from the card for its
  98,010 gil price like a missing weapon.
- `tools/gen_oboro.py` generates the dataset, `docs/oboro-r25.md` (new **JSE necks** table) and
  the unchanged migration in one pass; `--check` stays clean. Tests: `test_oboro.py` pins the
  66 necks (one path, 199-220), Duelist's Torque's R25/R15 bundles and stats, the 132-item
  catalog and the card payload; `test_augment_stats.py` covers the new rows.

## Unreleased — Red Mage enfeebles pick their set from the spell's own kind

- **`gearswap/RDM.lua` now carries the BG Wiki Community Red Mage Guide's enfeebling builds.**
  The guide splits Enfeebling Magic by what decides a spell's value, so the library has one set
  per kind: `midcast.Enfeebling Magic Skill` (Frazzle III, Distract III, Poison, Poison II),
  `… Macc` (Frazzle II, Distract II, Dia, Sleep, Bind, Break, Silence), `… Duration` (the
  crowd-control timers), `… Hybrid` (Gravity), `… MND` (Slow II, Paralyze II, Addle II),
  `… INT` (Blind II) and `… General` (Dispel, Inundation). The generic
  `midcast.Enfeebling Magic` remains as the fallback. The same pass adds the guide's Enhancing
  splits (`Enhancing Magic SIRD` for Aquaveil, `Enhancing Magic Stoneskin`,
  `EnhancingDuration`/`EnhancingDurationOthers`), its Malignance TP set, the enspell-damage
  melee set and its Seraph/Sanguine Blade builds, and puts the job back on the shared library
  layout: `local capes` (18 Sucellos's Cape builds), `unity`, the Odyssey R30 path tables and
  the five Limbus families, with the Cape augments named per set. RDM now shows 65 sets.
- **The host classifies each enfeebling spell and the plan follows it.** `control.lua` maps
  every Enfeebling Magic spell to a kind (`spell_enfeebling_kind`), reports it in
  `job_spells.categories` (`enfeebles_mnd`, ...) and resolves a cast in the order per-spell card
  → the spell's kind when Enfeebles is in **Auto** → the midcast default → `midcast.<skill>`.
  Duration falls back to Macc when no Duration set is configured; an unknown enfeebling spell
  (Virus) falls back to Macc. The Enfeebles group's modes are now `auto` plus the seven kinds,
  so `//modes enfeebles macc` (or `duration`, `mnd`, ...) still forces one set, and
  `//modes enfeebles auto` restores the per-spell behaviour.
- **The Gear page's Spells card shows the gear behind each kind.** The Enfeebles card has one
  row per kind with its set picker and spell count; clicking a kind's name opens a compact 4×4
  gear grid plus the slot → item list for that set, with the cape augment line. A forced Mode
  shows a `forced` note. The launcher's `SPELL_GROUPS` grew the seven enfeebling categories and
  their fallbacks (`midcast.Enfeebling Magic Skill / Macc / Duration / Hybrid / MND / INT /
  General`), so a job whose library only has `midcast.Enfeebling Magic` binds every kind to it
  and behaves exactly as before.
- **Saboteur is a live-status rule, the way SCH's Immanence is.** The guide's "override the
  hands on enfeebles under Saboteur" note is now real gear behaviour: the Enfeebles card has an
  automatic **Saboteur** row bound to `midcast.Enfeebling Magic Saboteur` (a one-piece overlay,
  `hands = "Lethargy Gantherots +3"`), the host registers a conditional rule for every
  enfeebling spell with status **454** in its buff list, and it *merges* the overlay over the
  spell's kind set instead of replacing it. While Saboteur is up the engine picks that rule (a
  rule naming more buffs wins); after the result the kind set's hands return. One overlay set
  covers all seven kinds, and a library or character without the Gantherots binds nothing.
- Tests: `tests/spell_groups_test.py` pins the host/launcher group, mode, kind and automatic-row
  lists, the enfeebling kind cases, the Auto/forced/duration-fallback plan rules, the Saboteur
  status id (454) and its merge overlay, the eight category fallbacks and the RDM set builds.
  Docs: `docs/rdm.md` (the guide's nuances and the sets), `docs/control-panel.md`,
  `docs/launcher.md`, `gearswap/README.md` (counts refreshed to 850 importable sets).

## Unreleased — Reive and Incursion capes augment through Detrovio

- **The Data page's Augments tab has a Reive & Incursion capes card.** It covers all 22
  level-99 job capes (Mauler's Mantle through Evasionist's Cape, items 28617-28638) and the
  four Refractive Crystal rows BG Wiki lists for each. A trade can fill several rows at once,
  so the card gives every row its own potency select (and `— none —`), preloads a clean cape
  with the four row maxima, and writes them all with **Apply augments**; **Clear augments**
  empties the block the same way Makel-Pakel does. The card uses the same cape and copy pickers
  as the Ambuscade card, so a character with several copies can target the exact bag or
  wardrobe row.
- **The server exposes it as `reive` in `character_data`, with `reive-augment` / `reive-clear`
  progress ops.** `game/reive.py` owns the 22 capes and their BG Wiki ranges, encodes the four
  rows through the shared `capes` standard block (BST's `STR/DEX` row is the client's one
  combined word), and decodes each stored word back to its row/value pair. A partial `choices`
  object keeps the rows it does not name. A wrong item, a row the cape does not offer, an
  out-of-range value or an empty selection is a 422; a missing container slot is a 404.
- **The new rows show up in the tooltip and the stat sheet.** `capes.TABLE` gained Blood Pact
  recast time II (0x16E), Reverse Flourish (0x172), Embolden (0x174), Helix effect duration
  (0x4E1) and Meditate effect duration (0x4F0), so `augment_stats` renders every Detrovio line
  and applies the modifiers the engine models. The five rows with no engine pool yet are listed
  in `UNMODELLED`.
- Tests: `test_reive.py` pins all 22 item ids, every row/range/tooltip, the negative-value and
  Pet: TP Bonus encodings, the service catalog/apply/clear round trip and the stat-sheet
  modifiers; `test_api.py` covers the card payload and both HTTP ops. Docs: `docs/reive-capes.md`.

## Unreleased — the set preview reads the bag copy's augments

- **A GearSwap set that names only the piece now shows the copy's augments on its card and Set
  totals.** The Manage tab used to read augments only from the library's own `augments` table; a
  set listing `Chironic Hat` (and the other Oseem/Ambuscade pieces) without spelling the block out
  showed base stats only, even though the bag row carried the decoded augment rows. The set
  preview now falls back to the matching bag copy the character owns, so the hover card, the set
  item rows and **Set totals** include Magic Accuracy, INT, SIRD and the rest. A set that does
  spell out its augments keeps its own values.
- **The server's `Spell Interruption Rate Down-11%` spelling totals as the canonical SIRD row.**
  `DOWN_RE` only rewrote `down 11` (with a space), so the hyphenated form the glyptic decoder
  emits became a separate `Spell Interruption Rate Down` stat and missed the SIRD cap. It now
  aliases to `Spell interruption rate`.
- Tests: `cargo test --manifest-path launcher-rs/src-tauri/Cargo.toml gear_stats` pins both SIRD
  spellings and the full Chironic block; `npm run check` and the production build pass.

## Unreleased — the launcher explains a full inventory

- **A purchase that cannot fit opens an Inventory full dialog, not just a toast.** The dialog
  names the item, confirms that no gil was charged, tells the player to free a slot in game with
  `//storage organize` (or `//bags`), and offers **Retry purchase** once they are back. The
  Items tab uses the same dialog; the other Data-page buy paths (the Oboro weapon card) show the
  same instructions in the page banner. `inventory_full` errors are recognised by their server
  code, so a different failure still reports its own message.

## Unreleased — Invisible looks like retail

- **Casting Invisible now turns your own character semi-transparent.** The client decides
  how to draw a hidden character; the server was never sending the flag it reads. `0x037`
  Flags1 **bit 15** (InvisFlag) is now set while the Invisible effect is up, and the
  retail client renders its own model translucent from it — the buff icon used to appear
  while the character stayed solid.
- **Other players stop drawing you while you are invisible.** The General block of
  `0x00D` now carries InvisFlag in Flags1 **bit 29**, so the clients around you hide the
  character instead of seeing a fully opaque player walk past.
- **Both packets go out when the effect lands or wears off.** `add_effect` / `remove_effect`
  queue the same `char_status` + General `0x00D` + `status_icons` bundle a mount swap sends
  and broadcast the entity update to the clients that draw the player, so the ghost look
  follows the buff at once instead of waiting for the next HP heartbeat. A job change or a
  Mog House trip that drops the effect clears the flag the same way. Sneak sets neither
  bit: it changes aggro, not the model.
- Tests: `test_world.py` pins the two flag bits on the self packets and that Sneak leaves
  them clear; `test_presence.py` drives two real sessions and checks the observer receives
  the invisible and the visible update on the effect's own refresh.

## Unreleased — Dark and Divine Magic get their own spell mode groups

- **The Spells panel has Dark Magic and Divine Magic cards.** Every spell of those two skills
  (Dark, skill 37: Drain, Aspir, Bio, Stun, Curse, the Absorb spells, Kaustra, Death, Tractor,
  Klimaform, ...; Divine, skill 32: Banish, Banishga, Holy, Flash, Repose, ...) used to fall
  through to the library's `sets.midcast["Dark Magic"]` / `["Divine Magic"]` with no way to arm
  a different set for it.
- **Dark Magic carries three modes.** **Potency** (`dark_potency`, the default) is the Drain /
  Aspir potency set and the Magic Attack a Kaustra or Death cast wants; **Macc / landing**
  (`dark_macc`) is the Dark Magic Skill / Magic Accuracy set for landing Stun, Bio, Curse and
  the Absorb spells; **Duration** (`dark_duration`) wears the Dark Magic duration gear that
  scales Bio and the other Dark Magic debuffs. `midcast.Dark Magic` is the conventional
  fallback for all three, so a library that only has the skill set keeps behaving as before.
- **Divine Magic carries two modes.** **Magic Attack** (`divine_mab`, the default) is the Magic
  Attack / MND set for the Banish and Holy lines; **Macc / landing** (`divine_macc`) is the
  Divine Magic Skill / Magic Accuracy set for landing Flash and Repose. `midcast.Divine Magic`
  is the conventional fallback for both, so a PLD or WHM library that only has the skill set
  keeps behaving as before, and a RUN still wears it for Flash.
- **The host classifies the spells and the in-game HUD gains `Dark` and `Divine` buttons.**
  `job_spells` now reports `dark` / `divine` in each spell's `categories`, the plan wears the
  armed mode's set, and the spell window's mode strip gains both beside `Helix`.
  `//modes dark potency|macc|duration` and `//modes divine mab|macc` switch them from chat (the
  help now lists every group straight from the table, so a future group needs no second edit).
  Endark / Endark II and Enlight / Enlight II stay in **Enspells** because they are
  self-enspells despite their Dark / Divine Magic skill.
- Tests: `spell_groups_test.py` runs the host's real group table and classifier against every
  skill-37 and skill-32 spell in the spell migration, pins the self-enspells to Enspells, and
  fails if the launcher's `phase.ts` and the host's `control.lua` ever disagree about a group,
  mode or category key.

## Unreleased — lockstyle keeps a same-type weapon from blinking

- **A weapon swap no longer repaints the character while style lock is on.** The lock
  stored only the weapon model, so the grap list changed on every main/sub swap and
  `equipment_sync` sent a fresh `0x051`; the client answered with the gear-swap blink.
  The character row now stores the locked weapon **type** beside the model
  (`style_main_type`/`style_sub_type`, migration 0188).  A same-type swap keeps the
  locked graphic, so the grap list is byte-for-byte unchanged and no `0x051` leaves.
  That is retail's rule and it makes a normal GearSwap TP/WS weapon pair blink-free.
- **A different weapon type still draws the equipped piece.** A two-hander becoming a
  one-hander plus a shield has to show both new models; switching back to the locked
  type restores its look.  This preserves the shield fix from the previous lockstyle
  change.  An old lock saved before the migration is upgraded on the next login
  keepalive: its untyped weapon slots adopt the weapon that is actually worn, which is
  what the player was already seeing.
- Tests: `test_style_emotes.py` drives a same-type sword swap (no `0x051`), a sword to
  great-axe change (new graphic), switching back, the two-hander ↔ shield case and the
  H2H left-fist mirror.

## Unreleased — a K.O. waits for a raise

- **Death no longer sends the character home on a six-second timer.** The old `tick`
  recovered the body at 50% HP/MP and warped it to the set Home Point, which cut a fight in
  an instance or event short and made a timed-out warp look like a bug.  A K.O. now stays
  down until a Raise spell lands or the player deliberately gives up and leaves the zone.
- **Raise, Raise II, Raise III and Arise revive a fallen player.** Their spell rows carry
  only the client's `player_dead` target bit (0x20), so `cast_magic` resolves the selected
  body as a session rather than a monster and `resolve_casting` restores 10/25/50/100% of
  maximum HP.  Arise also leaves a full-duration Reraise III.  The result is an ordinary
  magic-finish action (message 7, the restored HP) sent to the caster and the raised
  player, and both clients get the `0x00D`/`0x037`/`0x061`/`0x0DF` refresh.
- **A zone change is still the way out.** `//hp`, `//home`, the Home Point menu and any
  other warp revive a fallen character at half HP/MP instead of landing them at the
  destination still dead.  `hp_current = 0` survives a logout, so the next login is still
  K.O. rather than a free recovery.
- **The Battle hub raises its own.** A living box with healing enabled and a saved raise
  spell casts it on a fallen party member when the party row reads 0 HP, with a recast
  guard; `Reraise` is skipped because it is self-only.  Its **Return to home point** mode
  now honors the saved `death.wait` delay instead of firing `//hp` after one second, so a
  healer gets the configured time to raise before the player gives up.
- Tests: `test_effects.py` pins the no-timer K.O., Raise at 10%, Arise at full HP with
  Reraise, and the half-vitals Home Point return.

## Unreleased — Trust action sets survive a relog again

- **The Set dialog now restores the saved songs/spells/rolls after a logout.** The server
  already wrote `char_settings.trust_actions`/`joachim_songs` on every Save and read it back
  in the next `ZoneSession`, but the HUD asked for its catalogue as one `TrustData|A` chat
  line per action. A caster's expanded spellbook is 130-180 rows, and the zone chat pipe
  loses most of a burst that size (the client forwards the first line of a packet and drops
  the rest), so the dialog opened empty after a relog and players re-picked every spell.
- **`//trust <id> ui hud2` is the compact catalogue.** It sends the action ids as four hex
  digits and one category letter per action; the addon resolves each name and unlock level
  from the client's own spell/ability table. Koru-Moru's 130-row catalogue is seven short
  lines instead of ~130. Each line is queued as its own packet (`Msg.own_packet`) so a batch
  cannot hide all but the first. The legacy `ui hud` form is unchanged for an un-rebuilt
  client.
- **The dialog gives the compact lines time to arrive** (the load timeout moved from 5 s to
  12 s), and a long selection that will not fit beside the header travels on its own `S`
  line.
- Tests: `test_world.py` saves sets and builds a fresh `ZoneSession` to prove the next login
  reloads them, checks the compact Begin/id/kind lines and that every hidden line is its own
  packet; `tests/trust_hud_test.py` parses the compact catalogue against a client spell-table
  stub (rolls come from the ability table), checks the `S` fallback and the restored
  selection.

## Unreleased — physical hits interrupt casts, and SIRD spends

- **A landed physical hit now rolls spell interruption.** Every auto-attack and TP-move hit
  that does damage to a casting player rolls the retail ratios: `50 + attacker level - caster
  level` over 100 (floored at 0.01), the caster's skill in the spell's school against that
  school's cap, and the SIRD total. The roll is made at the hit, not at cast start, and again
  for every hit in the cast — the same reason the midcast set is pinned until the result.
- **Every SIRD source is spent.** Gear's Spell interruption rate (modifier 168, negative for a
  reduction), Choral Roll's row, and the "Spell Interruption Rate" merit (2% a rank, 10% at
  5/5) feed one total; the merit now appears in the launcher's stat sheet too. Songs,
  Manafont, Chainspell and a Shield Mastery blocked hit are immune. Aquaveil spends a charge
  instead of the cast: one base, three above 500 Enhancing Magic.
- **The client is told in retail's own shape.** The server sends the `0x028` category 8
  "sp"+school fourcc that stops the cast bar (the Magic Start's "ca"+school with the command
  swapped) and follows it with the `0x029` basic message 16, "The <player>'s casting is
  interrupted." The `0x028` keeps the spell id as its parameter, so it is a proper result.
- **The phase engine reads that fourcc as the result.** Category 8 is normally the cast start
  that pins the midcast set; the "sp" form now ends the pin and restores the aftercast state
  immediately instead of leaving the set on until the 30-second stale timeout.
- Not wired yet: Stun/Silence/Sleep/Terror/Petrify and Paralyze/Intimidate procs canceling a
  cast, and the 2-second recast the retail interrupt carries.
- Tests: `test_world.py` covers the interrupt and its packets, SIRD at the hit, the merit row,
  Aquaveil, Shield Mastery, songs/Manafont and a hit after the finish; `phase_cast_test.sh`
  adds the interrupt fourcc restoring the set.

## Unreleased — Scholar sequences on the server's action results

- **Ebullience is used in front of the magic burst, not before the opener.** It raises the next
  black-magic spell, so the old order spent it on the first opener (Water, Stone, ...) and the
  burst it was meant to raise got nothing. A macro with no burst list no longer pays a charge
  for it.
- **The runner follows action results instead of counting seconds.** A job ability is confirmed
  by the server's ABILITY_FINISH (`0x028` category 6), a spell by MAGIC_START (8) and
  MAGIC_FINISH (4). The next `/ja` or `/ma` goes out as soon as the current result lands. The
  shared stratagem recast (id 231) is still read from the recast table because no result carries
  it. If the client drops a command inside its own animation, there is no result, so it is
  retried as soon as the recast is clear; a spell is retried until the cast bar or MAGIC_START
  appears. The old 2.2 s and 1.2 s beats are gone.
- **The charge gauge uses the same proof.** A strategem spends a charge on its ABILITY_FINISH,
  not on the outgoing request: a refused use spends nothing, and a retransmit cannot spend twice.
- **An interrupted cast is reported as such.** A second category-8 result before the
  MAGIC_FINISH is the server's hit interrupt; the run stops with "was interrupted" instead of
  the old ten-second "did not finish". The client's cast-bar Count keeps the old cast after an
  interrupt, so it is no longer used to decide that a spell started.
- **The Scholar HUD draws the open Magic Burst window.** A small banner at the top of the
  screen names the skillchain and the seconds left while the window is open, read from the
  same chain action as the launcher's Nuking card. It is the in-game counterpart to the
  launcher's `open` badge.
- Tests: `sch_hud_test.sh` also checks that Ebullience without a burst list costs no strategem
  and that the burst banner draws; `sch_action_test.sh` sends real `0x028` ABILITY_FINISH,
  MAGIC_START and MAGIC_FINISH bodies and checks the action log, the charge spend and that the
  spell results spend nothing.

## Unreleased — the midcast set stays on until the spell lands

- **A cast now pins the midcast set until the server reports the result.** The engine already
  restored on the action's `0x028` result, but an automatic state change during the cast could
  still put other gear on first. The server reads a spell's numbers at the instant it lands
  (Cure potency, Magic Attack Bonus, Magic Accuracy, the magic skills, a song's duration), so a
  swap inside the cast resolves the spell in the wrong set. The same window is what retail's
  SIRD gear protects; this server does not roll cast interruption yet (`docs/rolls.md`), but the
  midcast set stays on either way. The pin starts at the server's Magic Start (`0x028` category
  8), which is the first packet that proves a cast is really under way, and ends at the result.
- **Movement, `/attack`, a zone or job settle and a plan push are deferred, not dropped.** A step
  during the cast still records the movement state; the state set goes on when the result
  arrives, through the same aftercast path (`fill_restore`). A plan push while casting keeps the
  in-flight action and does not re-wear the state set (editing a set or toggling a mode used to
  strip the midcast gear and cancel the pending action). The explicit **Wear set**, the lock and
  a slot-pin change still act at once, like a hand equip.
- **A refused cast is not pinned.** The client's action packet alone does not start the window,
  so a spell refused for MP, range or no target leaves the state free straight away. A zone, a
  job change or a different character clears the window, and the 30-second stale timeout still
  covers a result that never comes (the timeout was already 30 s; the documentation still said
  six).
- **`phase_status` names the window.** `casting` and `castSpell` are reported, `state` is
  `casting` and `set` is the midcast set while the pin is on, so the Active gear card reads
  `Casting · sets.midcast.Healing Magic` instead of the idle set underneath it.
- Tests: `tests/phase_cast_test.sh` covers the pin, a step and `/attack` during the cast, a plan
  push mid-cast, the result returning to the current state, a refused cast, another actor's
  Magic Start and a zone ending the cast; the other phase tests still pass.

## Unreleased — Scholar strategem charges recharge independently

- **Each spent charge now keeps its own return time.** The HUD used one serialized clock, so
  spending two charges made the second wait a whole interval after the first: Accession then
  Perpetuance looked 66 s away instead of both returning after 33 s about a second apart. Each
  spend stores `spent_at + 33 s` now; the next-charge pip and clock use the earliest timer, and
  a macro's readiness uses the timer of the charge it is waiting for.
- **A refused or retransmitted request no longer spends a charge.** The gauge follows the
  server's ABILITY_FINISH rather than the outgoing `0x01A`, so only a use the server accepted
  starts a timer.
- **The `.sch` file stores the timer list** as a sixth `charges` field (format version 2). A
  version-1 save only has the first timer; its missing charges are treated as back-to-back with
  it, which is the case the old serialized clock got wrong. `//sch charges <n>` gives the
  missing charges timers one interval apart.
- Tests: `sch_hud_test.sh` covers back-to-back spends, staggered `ready_at`, the version-1
  migration, the charge-timer round trip and the `//sch charges` command.

## Unreleased — Scholar skillchains wait on the real bars

- **A Scholar macro no longer drops its opener when Immanence is rejected.** Ebullience and
  Immanence share recast id 231, so one second after Ebullience the server still answered
  "Immanence is not ready yet."; the first spell then cast without Immanence and opened no
  chain. The runner finds the shared recast slot in the client's recast table and waits out a
  recast that is already running before each `/ja` (the animation wait above covers the rest).
- **The next step waits for the cast bar, not a fixed four or five seconds.** A long opener
  (or a slower cast set) used to run past that gap; the next Immanence interrupted it and the
  skillchain was lost. Each spell and burst now waits for `castbar.Count` to start and clear,
  then the aftercast beat described above.
- The same wait order covers the burst list: Thunder V and similar long casts no longer get
  cut off by the next burst.

## Unreleased — a Magic Burst set for Elemental Magic

- **The Nuking card on the Gear page has a third, automatic row: Magic Burst.** A set picked
  there is worn for Elemental Magic instead of the armed **Magic Attack** / **Magic damage**
  mode while a Magic Burst window is open on the player's target, and the armed mode is the
  fallback. The `Magic Burst` row is marked `auto`, is not in the Mode dropdown and is not armed by `//modes`;
  a per-spell card still wins over it and the precast set is unchanged. Libraries with
  `sets.midcast.Elemental Magic MB` pre-fill the row (`nuke_mb`).
- **The window is read from the action the client can see, not from a buff.** The client's status
  table has no Magic Burst or Skillchain entry and the buff block never lists one, so
  `control.lua` reads the closing action's `0x028` additional-effect block (message `287 + proc`,
  or `384 + proc` for an absorbed chain). The window lasts 11 s after a level-1 link and one
  second less per level-2/3 link, the server's `_next_window` rule (Diamond Aspis's full-window
  pin is not modelled); a landed weapon skill that forms no chain is a fresh opening and closes
  it, while a skill with no resonance properties and a miss leave it alone. It is tracked per target and only counts while the player's current
  target has one.
- **The engine wears it as a per-rule `burst` midcast set.** `xi.phase.burst(on)` (pushed by the
  watch loop) switches a rule from `mid` to `burst`; a zone, a job change and GearSwap's master
  off switch clear it. `phase_status` reports `burst`, so the launcher's Nuking card lights an
  `open` badge while the client sees the window.
- Tests: `tests/phase_burst_test.sh` covers the engine rule switch (ordinary midcast set with the
  window closed, burst set while open, a rule without a burst set unchanged) and
  `tests/phase_mb_test.sh` feeds real 0x028 bodies through the addon harness for the level-1 and
  level-2/3 window lengths, the chain-breaking weapon skill, a no-property skill and a miss.

## Unreleased — modern +1 armor set bonuses

- **The tiered Escha +1 armor set bonuses are applied on both sides.**  The client only
  prints `Set: ...` on each piece; the actual values are on the set page.  A shared table
  (`data/armor_set_bonuses.json`) now carries the eleven modern +1 sets: Adhemar (Critical
  Hit Rate 4/6/8/10), Amalric (Magic Atk. Bonus 20/30/40/50), Apogee (Blood Pact damage
  4/6/8/10), Argosy and Emicho (Double Attack 4/6/8/10), Carmine (Accuracy 20/30/40/50),
  Kaykaus (Cure Potency II 4/6/8/10), Lustratio (Weapon Skill Damage 4/6/8/10), Rao
  (Martial Arts 8/12/16/20), Ryuo (Attack 20/30/40/50) and Souveran (Damage Taken
  -4/-6/-8/-10).  Only the +1 pieces count; two pieces start the bonus and the fifth gives
  the maximum.
- **The server applies them to combat, healing and the live sheet.**  `equipped_mods`
  counts the set pieces and adds the reached tier, so the live checkparam report gets a
  `Set` gear row as well.  This is the missing 8% Cure Potency II on a four-piece Kaykaus
  Scholar set, for example.  Migration 186 also corrects Kaykaus Bliaut +1's own Cure
  Potency II row from the stale 6 to the client's 4, so the base and the set bonus add up
  to the same total in the preview and live sheet.
- **The launcher's Set totals includes the same bonus.**  The set preview counts the +1
  pieces by name and adds a green `Kaykaus Attire Set +1 (4 pieces): Cure potency II 8%`
  line above the totals; the bonus stats participate in the existing cap notes.
- Tests: `test_set_bonuses.py` covers every tier, NQ exclusion, unit conversion and the
  equipped-mod path; the catalogue test checks every piece id is a real +1 item.

## Unreleased — Set totals show stat caps

- **Known caps are marked in the Set totals.**  A capped stat now carries a note and changes
  colour when the set reaches the cap: Fast Cast 80%, equipment Haste 25%, Quick Magic 10%,
  Skillchain Bonus 50%, Cure potency 50% (II 30%), capped Magic Burst damage 40%, the
  Damage Taken family at -50%, Spell interruption rate at -102%, Snapshot 70%, Subtle Blow
  50% (II 50%), Conserve MP 100% and Casting time -80%.  A blue total means the set is at or
  past the cap; the note reads `13 excess` for Fast Cast at 93, for example.  A gold note
  reads `2 needed` while the stat is still short.  Stats with no hard cap are left plain.

## Unreleased — the Gear page remembers the set you were browsing

- **The Gear page reopens on the same GearSwap set and tab.**  The library browser is unmounted
  when the sidebar moves to Data (or any other page), so coming back reloaded the account's
  library and reset the selection to its first set — usually a state set — and the page also
  returned to **Sets**.  The tab is now kept in `fanxi.gear.tab`, and the selected set is kept per
  account and job in `fanxi.gear.selected.v1`, so a round trip to Data lands on the same set.
  Another account keeps its own set, a library that no longer carries the remembered set (after an
  import or **Restore template**) opens on its first set, and a job change still follows the live
  job's library.

## Unreleased — Reforged and final-form weapons in the viewer and the stat sheet

- **Reforged Bonanza weapons resolve in the EquipViewer and its item cards.**  The server names
  the upgraded copy `Wizard's Rod (Reforged)` (and the other nineteen similarly), but the
  client's item resource stores both copies under the base display name — and two of the
  upgrades use the other copy's spelling entirely (`Premium Hearts`, `Demonic Axe`).  A set
  naming one of them therefore drew an empty slot and its tooltip stats never loaded.  The
  host now keeps the one server-name-to-client-id table (`control.lua`) and uses it for
  `item_ids`, set-wear lookup and the launcher's stat query, so all twenty show their icon,
  card, base lines and set totals.
- **Final-stage weapons resolve to their iLvl 119 III copy.**  The client has several item rows
  under names like `Excalibur`, `Opashoro`, `Tupsimati` and `Kikoku`; `item_by_name` returns the
  lowest (weakest) stage, and the server's own rows for some of them append `119 III`.  The same
  resolver now maps all Prime and REMA family names, plus the seven `119 III` spellings and
  `(Level 119 III)` variants, to the final form, so those sets show the right icon and the
  strongest tooltip instead of an empty slot or a level-75 stage.
- **The special stage spelling stays visible.**  A set may spell a piece the server's way
  (`Opashoro 119 III`); the alias table uses that suffix only to find the final image and
  tooltip, and the card keeps the library's full name so the stage is still identifiable.
- **A rebuilt client no longer leaves the slot and card blank for the session.**  The set
  preview used to cache the zero id an unresolved name returned, and the hover card cached an
  empty result; both survived the client rebuild.  Only resolved ids and found tooltips are
  cached now, so opening the page against the new host resolves the piece.
- **The server has their real stats too.**  Migration 185 fills the nineteen reforged weapons
  that had no `item_mods` rows (and refreshes Final Sickle's), including the weapon/Parrying
  and H2H Guard skill bonuses, Haste, Magic Damage, Fast Cast, Refresh, Cure potency and the
  ranged weapons' Store TP.  The live stat sheet and combat now agree with the client tooltip
  instead of treating them as bare-damage weapons.
- Tests: `tests/reforged_items_test.py` runs the real resolver against a stub resource table,
  checks the Reforged table against migration 53, and checks the final-form table against the
  server's Prime/REMA family tables and every `119 III` spelling in the migrations;
  `test_stats.py` checks the imported tooltip stats and that the conditional `Unarmed:` block
  is not counted.

## Unreleased — Scholar charge rate, merits and gift spells

- **Strategem charges recharge at retail's rate.**  The HUD gave every charge a flat four
  minutes.  Retail splits the pool's four minutes across the level's charges (48 s at 99,
  60 s at 70, 80 s at 50, 120 s at 30, 240 s at 10), and the 550-JP **Stratagem Recast
  Time** gift takes 15 seconds off each; every Fanxi job has the 2,100 JP that unlocks it,
  so a level-99 Scholar now recharges a charge every **33 seconds**.  The footer prints
  the rate, the pip fill uses it, and a clock saved under the old four-minute constant is
  pulled in on the next draw.
- **The Scholar group-1 job-point gift is classified.**  `job_points` now carries the
  550-JP row as `mod.STRATAGEM_RECAST` (15 s) and exposes
  `stratagem_recharge_seconds()` so the server table and the HUD agree.
- **Scholar's 100/1200-JP gift spells are registered.**  The Storm II line and the eight
  Helix IIs are now in `SPELL_GRANTS`; the Storm IIs have no ordinary level row, so before
  this they were open to every job instead of being the Scholar's 100-JP gift.
- **The Scholar group-1 merits are applied.**  Grimoire Recast takes 2 s a rank off Light
  and Dark Arts, Max Sublimation adds 10 MP a rank to the storage cap, Helix Magic
  Acc./Atk. adds +3 Magic Accuracy and +2 Magic Atk. Bonus a rank to Helix spells, and
  Modus Veritas Duration gives 5% of its duration penalty back a rank.
- **The Scholar group-2 merits are applied.**  Altruism/Focalization add +10 Magic Accuracy
  at rank 1 and +5 a rank after that to the next white/black spell; Tranquility/Equanimity
  take 10 enmity a rank off it; Enlightenment gives +5 INT/MND a rank to the first spell and
  counts as both arts; Stormsurge gives the storm's stat +3 at 1/5 and +1 a rank after that
  (Voidstorm half, floored).  A group-2 ability with no rank is no longer listed or usable.
- **Modus Veritas follows retail.**  It doubles the Helix damage-over-time tick (plus the
  job-point bonus) and halves the remaining duration instead of only adding the bonus, and
  it refuses a tick of 5,000 or more.
- **Stratagem Effect IV no longer cuts the wrong recast.**  The old code took its 40% off
  Accession/Manifestation's own 1 s ability recast.  Spell recast belongs to the client,
  so the row is documented as not modelled instead of being applied to the ability.

## Unreleased — the Scholar HUD and Immanence skillchains

- **A Scholar HUD for strategems, self-skillchains and magic bursts.**  The new window
  (`host/addons/lua/sch.lua`, opened by `//hud sch`, the Control room's **Scholar** switch, or
  automatically for a Scholar main job) shows the strategem charges as pips, the count left and
  the clock to the next charge, and warns when the active art is Light.  Its left
  rail holds the twelve skillchain tabs, each with the player's named macros; a macro is a title,
  two or three spells, an optional **Use Ebullience** (the title then reads `(Ebullience)` and it
  costs one more charge) and an optional magic burst list.  The editor is a modal with a
  searchable spell picker, a live preview of the chain the spells form, and delete confirmations.
  A macro runs Immanence, the spell, then the next Immanence, then the burst list, waiting on the
  client's own stratagem recast and cast bar between steps.  When the spells cost
  more charges than are left the card is dim and shows the clock to the next time the chain is
  payable (`next 7:59` for two spells with none left) and clicking it repeats that in chat.
  Sets and the charge clock persist per character in `<data>/sch/<name>-<id>.sch`; `//sch` handles
  on/off, save, reset, position, charges and stop, and `//hud sch` is the HUD's own toggle.
- **Immanence now makes spells form skillchains.**  A damaging elemental spell cast with
  Immanence lands as a weapon skill with that element's property (Fire Liquefaction, Ice
  Induration, Wind Detonation, Earth Scission, Thunder Impaction, Water Reverberation, Light
  Transfixion, Dark Compression).  The first opens the 11 s window, the second closes it after
  the 3 s lockout, and the closing spell's damage is the chain's base.  The chain's
  additional-effect block rides the finished spell's own `0x028`, so the client plays the
  animation from the cast.  Immanence is spent by the spell whether or not it chains; a
  zero-damage or non-elemental spell leaves it up.  Magic Burst reads the same state, so a
  Scholar's burst list works after the chain closes.
- **The spell window is grouped into titled sections.**  Each type tab now draws coloured
  section bands instead of one alphabetical wall: Buff separates Protect & Shell, Regen &
  Refresh, Haste, Bars, Storms, Enspells, Songs, Ninjutsu, Blue Magic, Geomancy, Utility and
  Enhancing; Healing separates Cures, Raises and Status Removal; Debuff separates Sleep, Bind &
  Gravity, Dispel, Slow, Paralyze, Poison, Blind & Silence, Absorb and Enfeebling; Zoning
  separates Warp Marks, Warp, Teleport, Recall and Escape & Retrace.  The Nuke tab leads with a
  **Helix** block, then one block per element (Fire, Ice, Wind, Earth, Thunder, Water, Light,
  Dark) with the element's Immanence skillchain as the hint, then Blue Magic and Non-elemental.
  Because the client gives every helix the same generic icon, each helix tile now uses its
  element's tier-I nuke art (Pyrohelix/Fire, Cryohelix/Blizzard, …); the **Storms** row uses the
  same art (Firestorm/Fire, Hailstorm/Blizzard, …) so its eight shared icons become a colour-coded
  spread.  **Kaustra** carries a
  **2HR** tag, is dimmed and unclickable until **Tabula Rasa** is up, and a click while it is
  down writes the requirement to chat.
- Tests: `server/tests/test_skillchain.py` covers the element map, a Stone → Fire Liquefaction,
  a Helix closer, lethal-hit spending and a full `resolve_casting` pair whose closing result
  carries the chain block; `tests/sch_hud_test.sh --game <folder>` runs the real module against a
  mock ImGui API and pins every default tab to the chain it is named after, the saved format, the
  charge arithmetic, macro CRUD and every window; `tests/spell_sections_test.py` pins the section
  taxonomy, Nuke ordering, Bard family sections and the Tabula Rasa gate.

## Unreleased — Trust spellbooks and alter-ego upgrades

- **Support Trusts now offer their whole spellbook in Set spells.**  The old picker read
  only the imported `trust_spells` rows (Koru-Moru 29, Sylvie 20), so most of a job's
  spells could not be chosen.  `service.trust_action_spells()` merges the curated rows
  with every spell the Trust's main job can cast, its support-job spells up to the level-49
  cap, and — for Sylvie — **all 30 Indi- and all 30 Geo- spells**.  The picker now shows
  those rows and allows up to 24 selected spells per caster.
- **Custom sets use the expanded kit.**  The default AI still runs the curated rotation,
  but a player-selected set is built from the expanded catalogue, so a chosen
  `Geo-frailty`, RDM `Temper II` or non-curated Indi- aura actually casts.  Auras and
  Geo- hexes are cleared from the same expanded kit when the set swaps.
- **Launcher `Max all upgrades`.**  The Data → Progression → Trusts card now shows the
  character's alter-ego upgrade level (0-50) and has a button that maxes it.  The
  per-character setting lives in `char_settings.trust_upgrade_level`; at level 50 every
  Trust gets +250 HP, +100 MP, +50 to each base stat and +50 Attack/Accuracy, applied on
  the next spawn or gear-sync beat.  This is Fanxi's simplified form of retail's 2026
  alter-ego points system.
- Tests: `test_trust_support.py` covers the 30/30 Sylvie catalogue, job spells for
  Koru/Ygnas/Joachim, a custom non-curated Geo-frailty cast, and maxed upgrade stats;
  `test_api.py` covers the launcher endpoint; `tests/trust_hud_test.py` covers the HUD
  catalogue and new limits.

## Unreleased — Geomancy actually reaches the fight

- **The GEO anchor had no position, so the loop threw before it cast anything.**
  `B.members()` comes from the party table and carries no x/y, but `geo_tick` immediately
  passed the member to `distance()`.  `geo_anchor()` now resolves the member's entity
  position, which also lets the walk-to-range step work.
- **Support GEO cast Geo- hexes on the tank.**  `Geo-frailty` and `Geo-malaise` are
  enemy-target spells; the Battle loop sent them to the anchor by subtarget, so the client
  rejected the cast and a multibox GEO never put a hex on the monster.  The loop now reads
  the spell's target mask: Geo- buffs go on the anchor, Geo- hexes go on the claimed
  monster nearest the anchor, and the Luopan is placed at that target.
- **The Luopan was dropped at the GEO's feet.**  Even when a Geo- buff landed, the bubble
  was centered on the support camp instead of the tank/anchor.  `spawn_pet` accepts an
  explicit position and `_geo_bubble` resolves the party anchor or monster target before
  spawning it.  A Geo- hex now debuffs every monster inside the 10-yalm bubble (and drops
  the status when one leaves), instead of storing a single mob id.
- **Player GEOs were stuck at Geomancy +0.**  Idris has no `item_mods` row for its
  Geomancy +10, so a player GEO's Indi-/Geo- auras used the base column and Frailty stayed
  at 10%.  `ZoneSession.geomancy_plus()` reads the worn weapon ids and `geomancy.values()`
  applies the Idris column: party Fury +27%, Frailty -27%, Malaise -30%.  Geocolure is
  also main-job only, so /GEO can no longer cast a Geo- spell the client menu should not
  have offered.
- **Sylvie now keeps both monster debuffs.**  Her default rotation still puts Indi-Fury on
  the owner and Entrusts the 12.5% Defense Down on the monster, and now also maintains
  **Geo-Malaise** (-30% Magic Defense) as its own Geo- bubble.  Swapping the owner's Indi-
  aura no longer strips the Geo- hex, and the hex no longer strips Indi-Fury.
- **Koru-Moru skipped Haste II/Phalanx II when a tier-I was up.**  `buff_for` treated
  status 33/116 as "already up" without comparing the tier, so a Haste I or Phalanx I
  from another source blocked the stronger spell for its whole duration.  `_stronger_buff`
  now compares Haste's magic-haste modifier and Phalanx's flat absorption, and recasts the
  higher tier.  **Phalanx II also absorbed nothing** because the generated icon row had
  `power=0`; the RDM tier is 240 s and a flat -35 at 500 Enhancing Magic, so its icon now
  does what the buff says.
- Tests: `test_world.py` covers party-anchor Luopan placement, all-monsters hexes,
  Idris potency, main-job-only Geocolure and Sylvie's two monster effects;
  `test_trust_support.py` covers Geo-Malaise then entrusted Defense Down; the Battle hub
  harness still passes.

## Unreleased — the Manage set preview is clickable again

- **Clicking a slot in the Manage tab's Set preview opens the item picker.**  The hover
  card added for the item card replaced the click handler, leaving the preview read-only;
  clicking a slot now swaps that piece again and saves the account library immediately.
  Hovering still shows the piece's full card, its augments and its jobs.

## Unreleased — Trusts cast their damage debuffs and Sylvie's real aura

- **Koru-Moru never cast Dia.**  The trust tick checked `buff_for` before `debuff_for`,
  and a Red Mage with Protect/Shell/Haste/Refresh/Phalanx to maintain always had one
  expiring, so the monster stayed clean and every physical hit was missing Dia's 10–30%
  Defense cut.  A new `trust_ai.opening_debuff_for` puts Dia ahead of the buff refresh;
  cures still win, and the rest of the enfeebles run after the buffs.  Koru's recorded
  casts are now Dia → buffs, and the test asserts Dia III lands first.
- **Sylvie's Entrust was not modelled.**  Her spell table has no Geo- frailty, so she
  held Indi-Fury and nothing ever applied the **-12.5% Defense** cut.  The Entrust
  bubble is on the party, not the monster; applying the Indi-Frailty aura to the mob
  would make the mob its caster and debuff the players inside it.  The server therefore
  lands an ordinary **Defense Down** on the monster, and
  `trust_ai.entrust_debuff_for` schedules it between her own aura and the rest of the
  rotation.
- **Her aura used the player's Idris column, not the Trust's.**  A level-99 Sylvie (UC)
  is **Attack +37.5%, Accuracy +56, Haste +28.8%, frailty -12.5%**, not the player's
  Geomancy+10 row (+27% / +50 / +11% / -27%).  `trust_ai.TRUST_AURA_EFFECTS` carries the
  published alter-ego values; the player's own Indi- spells are unchanged.
- Tests: `test_trust_support.py` pins Koru's Dia-first cast, Sylvie's entrusted
  Defense Down landing on the monster with potency 12, and the 37/56/2880 trust values.

## Unreleased — H2H swings twice and uses its natural damage

- **Maru Kala was low because the H2H natural damage was dropped.**  `stats._damage_rating`
  returned the item's DMG whenever it had one, so a MNK's natural fist damage
  (`floor(H2H skill × 0.11) + 3`) only existed for an empty hand.  Retail adds the two:
  at 701 H2H skill (424 base + the Prime weapon's `Hand-to-Hand skill +277`) Varga
  Purnikawa is 213 + **80** = 293 base, not 213, for auto-attacks and every weapon-skill
  hit.  Weapon rank still uses the item's own DMG (`floor((213 + 3) / 9)` = 24), so fSTR
  does not inflate with the natural term.
- **The left fist was invisible and never swung.**  An H2H main hand now mirrors its
  model into the sub look with the `+0x1000` tag retail uses (`look.sub = model +
  0x1000`, written as `+0x8000`), and an attack round sends two results, main hand then
  animation 1, both from the main-hand fighter.  Before, `sub_fighter` was `None`, so
  the client got one punch and one hand's model.
- Tests: `test_combat.HandToHandSheetTest`, plus `test_world`'s
  `test_hand_to_hand_swings_both_fists` and
  `test_hand_to_hand_wears_its_model_on_both_hands`.  The formulas are documented in
  `docs/combat-damage.md` and `docs/prime-weapon-skills.md`.

## Unreleased — Maru Kala self-chain and the planners' property tables

- **Maru Kala already self-chains on the server.**  `(Detonation, Compression,
  Distortion)` opens, the second cast matches Compression against Detonation for
  **Gravitation**, and the third matches Distortion against Gravitation for **Darkness**.
  The server path was verified end to end (the 3 s lockout and the 11 s / 10 s windows
  still apply) and is pinned by
  `test_skillchain.SkillchainTest.test_maru_kala_self_chains_gravitation_then_darkness`.
- **The Battle hub planner's property table was stale.**  `battle.lua` carried a
  hand-copied subset (ids 1-16 and 239) with no Prime weapon skills, so Maru Kala (231)
  and the other Prime WSs were "unknown" to the in-game planner.  It also had older
  property orders for about twenty skills.  Both `battle.lua`'s `SC_WS_PROPS` and
  `control.lua`'s `HUD_WS_SC` are now generated from
  `data/weapon_skill_properties.json`; a test compares both tables to the data.
- The runtime window is unchanged: a close must land **more than 3 s** after the
  previous WS and inside the 11 s opener / 10 s Gravitation window.  A property-only
  planner (the web chain builders) does not model that or the 1,000 TP each cast needs.

## Unreleased — item cards on every EquipViewer slot

- **Hovering a slot shows the item's card, the way the game shows it.**  Every EquipViewer grid —
  the Sets tab's live read, the set preview, Manage's set editor and the Home and Control page
  grids — draws a card over the hovered cell: the client's tooltip verbatim (its `Set:` and
  `Unity Ranking:` blocks included), the augment rows that copy carries, then `iLv`, `Lv.` and
  the jobs that can wear it.  The tooltip and the job/race masks come from the client's item
  resources through `gear_item_stats`, so the card follows the running game; augments come from
  the GearSwap set, or from the equipped bag row on the live grids, so two copies of one item
  show their own rows.  The card is display-only and never blocks the pointer.
- **The Sets tab no longer edits gear.**  Clicking a cell in the live grid, a row in its legend or
  a slot in the selected set's preview used to open the bag picker — a stray click could re-equip
  the character or rewrite the library.  Those are read-only now: worn gear is changed from the
  Manage tab's new **Worn now** grid, and a set's pieces from its editor.  **Wear set** stays an
  explicit button on the Sets tab.
- Rebuild the launcher for this: the card's tooltip and `Lv.99 MNK` line come from new
  `gear_item_stats` fields (`description`, `jobs`, `races`).  An older binary still draws the
  stat lines and the augments, just without the verbatim tooltip and the job list.
- Tests: `cargo test` covers the new tooltip/job-mask fields; `npm run check` and `npm run build`
  cover the card and the tab split.

## Unreleased — Set totals stop inventing stats

- **The Gear page's Set totals no longer show a "To 30" or "All BP -30" row.**  Hoxne
  Earring's tooltip has `Mastery Rank: All BP -30 to +30`; the stat expression read the
  range as two stats, `All BP -30` and `to +30`.  `player_lines` now stops at a
  `Mastery Rank:` block like it already did at `Set:`, `Pet:` and `Unity Ranking:`.
- **`Dbl.Atk` is Double Attack.**  The Odyssey B augments and other libraries abbreviate
  the stat; without an alias the totals showed `Double Attack` and `Dbl.Atk` as separate
  rows.  `Dbl.Atk`, `Dbl. Atk`, `Dbl Atk`, `Double Atk`, `Triple Atk`, `Quad. Atk` and
  `Quad Atk` now share the canonical key.  `Guarding skill` also merges into `Guard
  skill`, and `Skillchain Bonus` is shown as a percentage.
- Tests: `gear_stats::tests` pins the Mastery Rank exclusion, the abbreviation merge and
  the Skillchain Bonus unit; the full launcher library suite stays green (78 tests).
  Rebuild the launcher to pick this up.

## Unreleased — Null Masque's own look

- **Null Masque no longer draws as the THF artifact bonnet.**  The full catalogue
  (migration 111) gave item 24270 the Rogue's Bonnet model, 4170, because LandSandBoat's
  `item_equipment` row is still `MId 0 / TODO: verify model` and the import fell back to a
  related-set guess.  Migration 184 stamps the client's 2025 head model 522 — the masque —
  as raw grap id `0x1000 + 522 = 4618`, and keeps `item_models` and
  `tools/item_models.json` in step so a grant or clone re-stamps it.  The Equip View icon
  was already the correct Null Masque icon.
- Tests: `server/tests/test_item_models.py` pins the item row, the lookup row and the
  catalogue.
- Fix a live character with `//model Null Masque 4618` (or unequip/re-equip the head); a
  relog or zone also redraws it.

## Unreleased — the whole Unity catalogue on the RP card

- **Every Unity +1 accessory, armour piece and weapon is augmentable now.**  The Data page's RP
  card takes its Unity rows from `server/fanxi_server/game/unity.py`, which carried 30 of the
  108 pieces: the accessories, plus Loess Barbuta +1, Blistering Sallet +1 and Rigorous Grip +1.
  Tatena. Gote +1 and the rest of the Unity armour and weapons were absent even when the item
  was in a bag.  The catalogue now lives in `data/unity_r15.json` — 27 accessories, 32 armour
  pieces and 49 weapons/grips from BG Wiki's three Unity categories — and every entry carries
  its client bundle: the 108 pieces are bundles 285-392 of the augment table, one each, matched
  to the Rank 15 line on the item's page.
- **The registry is generated data now.**  `tools/gen_unity.py` regenerates
  `database/migrations/0083_unity_augments.sql` and `docs/unity-augments.md` from the dataset,
  and the page's tables are grouped by category; `--check` keeps them in step.  `augment_stats`
  learned the spellings the armour rows use (`Magic Attack Bonus`, `Magic Evasion`) and lists
  the rows the engine still has no pool for (parrying skill, resist bind, avatar perpetuation
  cost, ...).
- Tests: `server/tests/test_unity.py` pins the catalogue counts, the bundle block and Tatena.
  Gote +1's row, and `server/tests/test_character_data.py` caps it through the RP card the same
  way the reported item would be.

## Unreleased — the Equip View wears the client's equip window

- **The in-game EquipViewer now looks like the game's own equip menu.**  The window paints the
  client's blue **Equip View** title bar and bevel, the pale set line under it (`no set`,
  `idle.dt`, or `WS.Blitz` in gold while a weaponskill holds its set), and the thin rule the
  client draws below the set name.  The 4×4 grid is one flush block of the game's item icons
  (they already carry the equip screen's coloured backgrounds); the cells grew to 51 px and
  the icons fill them.
- **No label row under the boxes.**  A slot's name is no longer written below its icon: the
  cells touch, and an empty cell carries its slot name as a faint watermark *inside* the box,
  exactly like the client's item picker labels an empty tile (`Range`, `L.Ear`, `R.Ring`, …).
  Tooltips still name the item, and a `//gs lock`ed slot keeps its red border.  Collapsed, the
  title bar keeps naming the set and its age.
- **The window closes its ImGui frame again.**  It had been leaving `End()` to the addon guard,
  which also left the hub's style vars pushed until the guard cleaned them up.
- Tests: `tests/equipview_hud_test.py` runs the real grid geometry and pins the flush cells,
  the in-box watermark, the item-icon cells, the painted title bar and `api.End()`.
  Added to `scripts/test.sh`.  The HUD Lua is embedded in host64, so runtime 0.2.92 makes the
  launcher rebuild a client that still carries the old window.

## Unreleased — account-owned GearSwap libraries

- **A GearSwap library belongs to the account, not the checkout.**  The Gear page used to write
  edited sets into the shared `gearswap/<JOB>.lua` files, so one character could change the
  library every account loaded.  Migration `0177_gearswap_libraries.sql` adds a
  `gearswap_libraries` row per account and job, and `GET/PUT/DELETE
  /characters/{id}/gearswap/library` reads, replaces and resets it.  The launcher loads the
  tenant account's row instead of the checkout file and sends its Lua text to the client, so a
  box on another machine uses the same account copy.
- **A new account starts from Onedough's current set.**  The first read of a job seeds the
  account from `FANXI_GEARSWAP_TEMPLATE_ACCOUNT` (default `onedough`); when that account has no
  saved row yet, the server's `FANXI_GEARSWAP_DIR/<JOB>.lua` (default `gearswap/`) is used.  The
  copy is independent afterwards, so editing or importing on one account never reaches another.
- **Imports and edits are saved to the account.**  **Import .lua** now stores the parsed file as
  the current job's account library, **Restore template** puts a fresh template copy back, and
  every set edit writes the account row instead of a shared file.  The Gear page also follows a
  live job change to that account's library for the new job, and the auto-swap plan is pushed
  from the same server copy.  A server that predates the route still falls back to the bundled
  default so the page keeps working during an upgrade.

## Unreleased — clone a character from the dashboard

- **The admin dashboard can clone a character onto another one it finds in the database.**  The
  new **Clone character** action (`m`) asks for the source (Onedough by default), searches
  character names by any part of the name, shows the matches with their level and id, and runs
  `tools/clone_character.py --force --apply` on the server after a second confirmation.  It warns
  when the target still has an unexpired game-session row, because that usually means the client
  should be logged out first.  The clone tool's own pre-clone backup and relog instructions are
  unchanged.

## Unreleased — deploy verifies migrations

- **The dashboard's deploy now proves the schema matches the code.**  The service still applies
  `database/migrations/` at startup, but the dashboard reads `schema_migrations` before and
  after the restart, prints the migrations it applied, and fails the deploy if any file is still
  pending — even when `/health` is up.  A deploy with no new commit also restarts when a
  migration is outstanding, instead of saying there is nothing to deploy.

## Unreleased — Limbus weapons on the RP card

- **All sixteen Telopanos weapons joined the Data page's RP card.**  The Limbus
  furnaces' Superior 5 weapons — one per weapon skill plus the shield and the
  grip — were missing from the card entirely: the RP registry had no paths for
  them and their item rows carried no stats, so a copy in a bag could not be
  capped and showed nothing on the stat sheet.
  `data/limbus_weapons_r30.json` now holds each weapon's client stat line and its
  Rank 30 rows, and `tools/gen_limbus_weapons.py` writes
  `database/migrations/0175_limbus_weapons_r30.sql` (base modifiers, client skill
  bonuses, the tooltip description, and one unaugmented copy of each weapon for
  characters 1 and 2) and `docs/limbus-weapons-r30.md` from it.  The card caps a
  path exactly like the Limbus suits: rank 30 / tier 3 / 55,800 RP (curve B) and
  the piece's own client bundle.
- **Each weapon carries a real client bundle.**  The client's augment table has
  512 entries; 497-512 are this family (bundle 500 is the Saber's
  `Damage+18 / Magic Damage+25 / HP+150`), and every one was matched to its wiki
  Rank 30 rows by content.  A capped copy therefore prints its rows on the
  tooltip, `//r30 telopanos saber` prints them in chat and `//rp30` re-stamps
  weapons alongside the armour.
- **`Damage+n` augments now raise the weapon's damage rating.**  Retail adds the
  row to the weapon, not to a modifier, so it was previously display-only for
  every weapon that carries one (the Telopanos weapons and Oboro's HQ2 paths).
  `augment_stats.weapon_damage` reads the row from the block and
  `FanxiService.equipped_weapons` adds it to `item_weapon.dmg`, which the attack
  round and the weaponskill formula already read.  A Rank 30 Saber swings at
  157+18.
- **The weapons render.**  A copy equipped with model 0 was silently not drawn --
  `equipped Telopanos Sword in slot 0 with no grap model: it will not show` in the
  zone log.  The 2026 wave has no MId in any server data (LandSandBoat marks the
  rows `TODO: MId`) and the client's item records carry no model at all, so
  `0176_limbus_weapon_models.sql` gives each weapon the client model of its own
  weapon type: the 2026 Ethereal block (929-938, one model per weapon group) where
  it names the type, the type's Stage 5 afterglow otherwise.  They are stand-ins,
  not the Telopanos skins -- `//model <item> <id>` overrides one copy, and the
  dataset's `model` field plus a regeneration bakes a better id in.  The grip
  stays model 0: a grip is never drawn.
- **The shared stat-line parser learned four more tooltip spellings.**  Unquoted
  `Magic Attack Bonus +n`, lower-case `Magic damage +n`, unquoted
  `Snapshot +n`, and the shield's one-line `Damage taken II -5%` (which feeds
  both uncapped pools) used to be dropped; the Telopanos data needs all four.
  `Magic Accuracy skill +n` still has no client skill id and stays un-stored.
- Tests: `test_limbus.py` walks the 16 entries, their bundles and the registry;
  `test_augment_stats.py` covers the Saber's rows and the damage rating (and
  Oboro's HQ2 `DMG:+12`); `test_api.py` buys a Saber and caps it through the RP
  card.  Docs: `docs/limbus-weapons-r30.md`, plus the launcher/control-panel
  passages that describe the card and `//r30`.

## Unreleased — Target Debuffs and Battle HUD over HTTPS

- **The HUD's API client now speaks HTTPS.** `battle.http_json` only parsed `http://`, so with
  `FANXI_API_URL=https://172.236.103.193.sslip.io` the Target Debuffs window showed
  **"Target info unavailable: no HTTP"** and the Battle HUD stopped polling. The plain-HTTP
  path is unchanged (LuaSocket); an `https://` URL goes through libcurl via LuaJIT FFI
  (Bearer header, follow redirects, body in `tmpfile()`), with a clear
  `libcurl is not available` fallback. The server API and token are unchanged.

## Unreleased — weapon-skill animation context

- **A weapon skill's finish waits one flush after its start.**  Start and finish were
  queued in the same datagram; the client processes the start's `SetAction` on its
  scheduler, so a finish that reads animation 6 or 237 could fall back to the spell
  table and play a Blue Magic casting motion (Flat Blade -> Cure VI, Requiescat ->
  Choke).  `queue_action` now accepts a `not_before` time, `pack()` holds those messages
  for a later flush, and the SkillFinish is held for 150 ms so it lands in the next
  datagram.  The start and finish packets and their order are unchanged; only the
  datagram boundary is new.

## Unreleased — Corsair Trusts keep both rolls

- **Qultada and Luzaf now fill both of a Corsair's roll slots.**  The Trust AI kept one
  `roll_key` per alter ego and treated every other roll as a replacement, so a Corsair
  Trust only ever had one roll up.  Retail Qultada keeps two at once (Chaos and Fighter's
  are his standard pair) and a Trust is a maxed-out Corsair, so each support Corsair now
  stores an ordered `roll_keys` list, fills the first slot with the party's biggest need
  and the second with the next line another Corsair has not already put up.  A held roll
  is refreshed when its party copy nears expiry; changing the owner's `set rolls` list
  removes only the rolls that left it.  Two Corsair Trusts can now hold four different
  rolls (Chaos, Fighter's, Samurai, Hunter's/Evoker's...) instead of two.
- **Fighter's Roll joined the melee plan.**  `trust_ai.roll_options` now offers Chaos,
  Fighter's and Samurai, matching Qultada's retail Chaos + Fighter's pair while keeping
  Samurai as the Store TP line at the pDIF cap.
- **A solo Red Mage now gets both roll lines.**  RDM and BLU count as caster *and* melee,
  so Qultada and Luzaf fill four slots (Chaos, Fighter's, Samurai, Wizard's) instead of
  the caster-only plan giving one roll and leaving the second Corsair idle.  The ranged
  job set also named job 7, which is Paladin; Ranger is 11.  `RANGED_SONG_JOBS` had the
  same typo.
- Tests: `test_world.py` covers two slots on one Trust, two selected rolls both staying
  up, four rolls from two Trusts, and the removed-roll cleanup when the list changes.
  Docs: `docs/world.md` (the roll section's 100-second figure was stale; a Trust roll is
  340 seconds).

## Unreleased — Locus-tier monsters hit back

- **Level 100+ monsters no longer use the level-99 offense cap.**  LandSandBoat's
  `GetMaxSkill` stops at 99, so a level-135 Locus Camelopard had 604 Accuracy against a
  level-99 player's 903 Evasion: every auto-attack and TP move sat on the 20% hit-rate
  floor.  `stats.build_monster` now adds master-level attributes (+3.6/level), Accuracy
  (+20/level) and Attack (+16/level) above 99, giving Locus 305-309 stats, 1324 Accuracy
  and 1342 Attack.  The 1324 number is the requirement BG-wiki publishes for the camp;
  the mob now reaches the 95% hit cap instead of missing everything.
- **Monster Berserk is a real buff.**  The Dhalmel TP move was an icon-only self-buff,
  so its +45% Attack / -25% Defense never reached the swing.  It is now stored in the
  monster's `effect_state` with `ATT_PERCENT`/`DEF_PERCENT`, expires after 120 seconds,
  affects auto-attacks, TP moves and damage taken, and Dispel/Finale can strip it
  (Dispel now prefers a real self-buff over the player's Dia/other enfeebles).
- **Healing Breeze is a max-HP heal.**  The old self-heal path restored a flat 300 HP.
  The LandSandBoat script uses `baseHeal = maxHP` and fTP 172/215/258 over 1024 at
  1000/2000/3000 TP, so a 308,300-HP Locus heals 51,784-77,677 instead of 300.  The
  spent TP is captured before the bar is emptied.
- **Every Locus uses the same level-100+ sheet, and three HP placeholders are fixed.**
  The builder is generic, but `monster_templates` still had three Locus rows imported
  without HP: Colibri 2,680, Wivre 2,720 and Lemures 2,740, while the rest of the family
  has 293,000-327,500.  Migration 174 restores 229,600 / 259,000 / 305,000, and
  The same migration writes retail level/HP curves for the camps that publish them:
  Colibri 133-136 / 214,600-229,600, Wivre 135-137 / 244,000-259,000, Bibiki's three
  135-137 Locus / 289,900-308,300, its crabs 137-139 / 309,100-327,500, and the King
  Ranperre's Tomb rows.  Locus spawns now roll their level in that range (and reroll
  on respawn), and `entities.mob_hp_for_level` interpolates HP between `hp_min` and
  `hp`.  A level-129
  Lugcrawler is still weaker than a 135 Camelopard; the camps are not flattened.
  `test_stats.py` walks all 23 Locus templates and pins the master-level
  Accuracy/Attack, the rolled level, and the interpolated HP.
- **Locus Defense/Evasion use the published rows, scaled to 75% for the current gear.**
  `monster_templates.level_stats` stores the retail rows verbatim, and
  `World.monster_sheet` applies the row for the rolled level.  `entities.mob_from_row`
  scales Defense and Evasion by `LOCUS_DEFENSE_SCALE` / `LOCUS_EVASION_SCALE` (0.75):
  Camelopard is 1010/918 at 135 and 1060/963 at 137, down from 1346/1224 and 1413/1284.
  At the current ~1182 Accuracy that caps the one-handed hit rate without Distract III,
  and the lower Defense restores weapon-skill damage; HP, Accuracy and Attack stay at
  the published values.  Distract III remains a flat -130 Evasion (not a percent).
  Locus with no published table keep the level-derived curve.  Setting both scales to
  1.0 restores the untouched retail rows.

## Unreleased — the Odyssey accessories ship with the checkout

- **The Beithir Ring can be augmented again.**  The ten Sheol Gaol accessories (Beithir Ring,
  Schere Earring, Tellen Belt, Obstin. Sash, Hesperiidae, Coiste Bodhar, Epitaph, Neo Animator,
  Acrontica and Tsuru), the Bunzi's/Ikenga's/Mpaca's sets, Gekkei and Kunimitsu live in
  `data/odyssey_extra_r30.json`, but the `data/*` whitelist in `.gitignore` never un-ignored it.
  A fresh clone -- including the live server -- therefore loaded only `data/odyssey_r30.json`,
  `odyssey.entries()` had no accessory rows, a carried Beithir Ring had no Rank 30 path in the
  RP card, and `//augment A Beithir Ring` answered "no known Rank 30 bundle".
- **Both source datasets are now tracked.**  `.gitignore` whitelists
  `data/odyssey_extra_r30.json` and `data/sinister_reign.json` (the Sinister Reign card's dataset
  had the same omission), and both files are added to the repository.  `odyssey.missing()` and
  `sinister.missing()` report an absent file and log a warning instead of silently serving an empty
  catalogue; `test_odyssey.py` and `test_sinister.py` pin the files, so a checkout that loses one
  fails the suite. `docs/odyssey-r30.md` describes the merge and the ring's single Rank 30 path.
- **The ring's first row reaches the sheet.**  "Weapon Skill Acc.+15" was in the unmodelled list,
  so only Attack+15 and Skillchain dmg.+5% of the ring's Rank 30 block applied.  The row now maps
  to the engine's `WS_ACCURACY` (48), which the weapon-skill accuracy path already reads, and
  `test_augment_stats.py` pins all three rows together.

## Unreleased — a nearest-actor chain no longer freezes the client

- **The freeze was a mutual-nearest cycle, not the gear.**  `f_10158ca0` follows "nearest actor
  matching these masks" from one actor to the next with no visited set.  The player's trusts stand
  together, so Luzaf's nearest match was Cornelia and Cornelia's was Luzaf; both carry mask 0x100e,
  so the chain bounced between them forever and the frame never completed.  The post-battle gear
  restore is only the moment the selector runs.  Captured live at 18:25, 19:03 and fixed at 19:54
  (`[chain] cycle 0ebf97c0 -> 0ec37df0 -> 0ebf97c0`), with the two actors read out as Luzaf
  (ServerId 16795396) and Cornelia (16795392).  See docs/freeze-actor-list.md.
- **The chain now stops on A -> B -> A.**  `recomp/x86c.py` emits a two-deep history into both of
  `f_10158ca0`'s loops; when the chain returns to the actor before last it logs `[chain] cycle`
  and ends the chain where retail would spin.  Retail's loop assumes the chain terminates; any two
  admitted actors can form the pair, so the guard is the fix, not a workaround for one pair.
- **How it was found.**  `tools/freeze_watch.py` detects a wedged client, `tools/freeze_capture.py`
  samples it and attaches `lldb` only when the stack is the actor chain, and the probe records the
  guest registers and the walk.  A diagnostic build (`FANXI_SKIP_RECOMP=1` in tools/build.py) let
  the guard be tested in generated code before the recompiler emitted it.

## Unreleased — a locked weapon holds through a weaponskill and re-arms when drawn

- **A pinned weapon is a lock, not a filter.**  The host kept only a slot mask, so a set that
  did not name the weapon could leave the last piece on (the TP set has no main/sub when a
  weaponset outside the state sets owns it).  It now keeps the exact `bag/slot` copy for each
  pinned weapon slot, re-asserts the main/sub/ranged copy when the weapon is drawn, and captures
  the live equipment from the client before a pin is taken — including right after a zone, when
  the worn table is empty.  Ammo stays a filter: the throw guard owns that slot while a ranged
  action is in flight.
- **A weaponskill no longer swaps a pinned hand.**  The old "WS is the exception, its set names
  the weapon" rule took Naegling + Thibron off for a `sets.WS` sub (Chant du Cygne names Genbu's
  Shield) and relied on the result packet to put the hand back; a TP set that names no weapon
  has no piece to fall back to, so Genbu's Shield could stay on.  The pinned hand now stays on
  through the WS, the skill is rolled with it, and only the WS armour set is worn and returned.
  That is the lock's promise: the client's weapon-skill menu and TP hand cannot change
  mid-fight.
- **Two swaps stay sanctioned, and both are temporary.**  A spell cast **while the weapon is
  sheathed** may take the casting hand for its window (no TP is at stake), and a **Bard song
  under Nitro (Nightingale + Troubadour)** may take the instrument even while engaged; the
  locked hands are restored when the action resolves.  The control addon reads Nightingale and
  Troubadour from the client's buff list and tags song rules in the plan, so nothing else opens
  a locked hand.
- **A spell whose table index falls in the Corsair roll range is not a roll.**  The Phantom Roll
  duration-set exception checked only the action id (98-122, 302-305, 390-391), so a spell with
  one of those ids could temporarily bypass a pinned hand.  It is now limited to job abilities.
- **A plan push with no job no longer releases the session locks.**  The plan's `job 0` (the
  party row is not populated yet at login/relog) used to overwrite the engine's known job, so
  the next real plan looked like a job change and cleared every lock and pin.
- Tests: `tests/phase_weapon_lock_test.sh` covers a pinned WS, an engaged cast, a disengaged
  cast with restore, a re-arm on `/attack`, the roll-id spell, and the BRD Nitro song with and
  without Nitro.  `tests/phase_lock_override_test.sh` now expects the WS to keep the pinned sub.
  Docs: `docs/control-panel.md`, `docs/launcher.md`; the Gear page hint says the same.

## Unreleased — Imperator was in the menu; Knights of Rotund should not have been

- **Imperator (233) itself is complete.**  Caliburnus 21646 carries `Adds weapon skill`
  355 = 233, the `weapon_skills` row is the item-granted `skill_level -1` form, and
  `data/weapon_skills.json` has the 6.6/13.35/20.1 fTP and 27% DEX/MND WSC.  The Prime
  aftermath, skillchain properties and TP return all resolve; a direct server-side use
  with Caliburnus equipped lands the action.
- **Knights of Rotund (227) was polluting every sword user's menu.**  Its row kept
  `skill_level 0`, which Fanxi reads as "quested, offer at 350 sword skill", so a
  Caliburnus Paladin saw both Imperator and the Excalipoor II joke skill.  It is
  item-granted by Excalipoor II's 355 row, so migration 0173 changes it to
  `skill_level -1`; only that weapon's wearer sees it now.
- **RDM and BLU set libraries now have an Imperator weapon-skill set.**  RDM had the
  `Caliburnus-DiamondAspis` / `Caliburnus-Thibron` weaponsets but no
  `sets.WS["Imperator"]`, unlike PLD, so the set picker and any GearSwap rule keyed on
  the WS name had nothing to equip.  RDM gets Caliburnus + Thibron with the physical
  WSD set; BLU gets Caliburnus + Genbu's Shield with its Odyssey B set.
- **A rejected weapon-skill action now logs the id and the equipped main/sub items.**
  The old path only sent a chat line, so a GearSwap/equip race looked like "nothing
  happened"; `server.log` now shows which weapon the handler saw and which skills were
  available.
- Tests: `test_weapon_skills.py` pins that a normal sword does not advertise 227, that
  Excalipoor II does, and that Caliburnus advertises 233; `test_gearswap_prime_sets.py`
  pins the Imperator set in RDM/PLD/BLU.

## Unreleased — magical weapon skills use the retail formula

- **Seraph Blade, Sanguine Blade and every other `doMagicWeaponskill` row now use the
  magical formula instead of the physical pDIF path.**  Retail's base is
  `152 + floor((WeaponLevel - 99) * 2.45) + WSC` (201 + WSC for an iLvl 119 weapon),
  multiplied by fTP, then `dSTAT + Magic Damage`, then WSD, elemental affinity,
  MAB/MDB and the magic resist.  The old path used weapon DMG + fSTR + WSC and pDIF,
  which ignored the MAB and Magic Damage on a Red Mage's casting set; that is why a
  well-geared Seraph Blade sat around 7-8K instead of the retail-range 30K+.
  Sanguine Blade's `dSTAT` is `(player INT - target INT) * 2`; Seraph Blade's is 0.
  Black Halo stays physical: it is a two-hit club skill with first-hit-only fTP.
- **The Oboro path-C "Elemental weapon skill damage +100%" augment is read.**  It is
  the Crocea Mors / Vitiation Sword / Duelist's Sword Rank 25 line, stored as
  `mod.ELEMENTAL_WS_DAMAGE` (1240), and it multiplies only the fTP part of a magical
  weapon skill.  A Rank 25 Crocea Mors now roughly doubles Seraph Blade and Sanguine
  Blade instead of contributing nothing.
- **Daybreak's "Light elemental damage +50" reaches the item data.**  It is the light
  affinity row (`LIGHT_MAB`, 38), so it multiplies a light magical weapon skill such
  as Seraph Blade.  The item import had kept every other Daybreak line but dropped it.
- **Sanguine Blade drains 50/100/160% at 1,000/2,000/3,000 TP, and magical weapon
  skills return the main-hand delay TP.**  Both follow the Adoulin branch and LSB's
  `doMagicWeaponskill` path; the old drain stopped at 100% and the old return was 0.
- Tests: `test_combat.py` pins the magical base/level term, the augment ordering,
  MAB/affinity/WSD and the 99,999 cap; `test_weapon_skills.py` pins the skill metadata,
  the magic-path wiring, TP return and the Sanguine drain; `test_augment_stats.py`
  pins the Crocea Mors augment row.

## Unreleased — RDM job points and the second weapon swing

- **Red Mage's En-spell gifts are applied.** The four "En"-spell rows (5 + 5 + 6 + 7 =
  **+23**) were left in the unclassified list, so a Red Mage's en-spell hit was only the
  Enhancing-Magic base plus gear.  They now map to `mod.ENSPELL_DMG_BONUS` (LandSandBoat's
  mod 432), the same flat line the Sworn R30 suit carries, and `_enspell_gear_bonus` gives
  them to both hands without charging them to the other weapon.
- **RDM's job-point spells are real spells for a Red Mage.** `job_points.SPELL_GRANTS`
  encodes LandSandBoat's `RefreshGiftMods` table: Fire/Blizzard/Aero/Stone/Thunder/Water V
  at 100 JP, Addle II / Distract III / Frazzle III at 550 and Refresh III / Temper II at
  1200.  `spell_bits()` keeps their `0x0AA` bits for a level-99 main job and clears them
  for every other job, and `can_cast_spell` follows the same rule.  Fire V's ordinary
  row belongs to BLM 86 / SCH 91, which is why the RDM gift was invisible before.
- **A job-point spell can no longer be cast by the wrong job.**  Spells with no level row
  (Death, Aspir III, Reraise IV, Full Cure, the Threnody II line, Utsusemi San, Addle II,
  …) used to stay open to everyone.  The gift table now closes them to the granting main
  job; spells with no gift and no level row (Trusts, merit spells) stay open.
- **Mag. Burst Bonus is applied to burst damage.** The RDM trait's mod 274 (5 at 85, 7 at
  95) was in the trait table but no damage path read it.  `_cast_numbers` now multiplies a
  Magic Burst by `1 + min(0.40, capped/100) + uncapped/100` after the base burst
  multiplier, so the RDM trait, SCH/BLM job points and gear all count.
- **The ★Master! gift shortens the two-hour recast.**  Its 15 minutes are stored as
  `mod.ONE_HOUR_RECAST`; the zero-id abilities now keep a per-ability cooldown, sent in
  `0x119` slot 0 for the current job and restored after a reconnect, so Chainspell and the
  other one-hours come back in 45 minutes instead of an hour.  A job change shows the new
  job's own one-hour rather than the previous job's remaining timer.
- **Shield Mastery and Clear Mind are read.**  RDM's Shield Mastery (+20 at 97) is added to
  the shield-block roll, and Clear Mind's "MP while healing" value (RDM IV = +12) is added
  to each `/heal` MP tick instead of the trait being a label in `//traits` only.
- **Quick Magic uses its job-point row correctly.**  The row is LandSandBoat's "MP
  consumption -2%", not extra proc chance: Quick Magic stays a 5% proc, and a proc refunds
  2% of the spell's MP cost per rank (40% at rank 20).  The old code turned a maxed row
  into a 45% instant-cast chance and ignored the MP bonus.
- **Chainspell and Spontaneity are instant again.**  `combat.cast_time` applied its 0.5 s
  floor to a zero base, so a spell with Chainspell (or after Spontaneity) still took half
  a second; a zero base now stays zero.
- **The off hand swings whenever a one-handed weapon is in the sub slot.**  The equip rules
  already let any job wear two one-handers (a Red Mage's Crocea Mors and Daybreak, a
  Ninja's katanas), but `stats.build_character` still required the Dual Wield trait, so the
  second weapon was visible and inert.  Two one-handers now make a `sub_fighter`; the trait
  and gear "Dual Wield +N" only reduce the round's delay (without them the round is the
  plain average of the two delays and TP is unhalved).  The attack round, weapon-skill
  off-hand swing and `action_count` animation all follow the same sheet.
- **The rejected-weapon-skill log no longer breaks the packet send.**  Its local `sub`
  item-id shadowed the module-level `sub()` helper for the whole `weaponskill()` function,
  so every weapon skill raised `UnboundLocalError` before the 0x028; the locals are now
  `main_id`/`sub_id`.
- Tests: `test_job_points` (RDM gift totals and the spell-grant table), `test_spell_levels`
  (RDM's Fire V / Addle II bits, and other jobs refused), `test_skillchain` (RDM's MB trait
  scales the burst), `test_world` (the 45-minute two-hour slot, the Quick Magic MP refund,
  the Clear Mind rest tick and an RDM/SCH off-hand round with `[0, 1]` animations),
  `test_combat` (two weapons without the trait, the zero-cast-time rule and Shield
  Mastery).  Docs: `docs/job-points.md`, `docs/combat-damage.md`, `docs/skillchains.md`,
  `docs/world.md`.

## Unreleased — lockstyle shows weapon swaps, and a respawn forgets its skillchain

- **Lockstyle no longer freezes the main/sub weapon graphics.**  Main and sub now always
  read the equipped gear, so a two-handed main becoming a one-handed main plus a shield
  (or any other weapon swap) draws the new pieces while the armour keeps the locked look.
  Before, the shield appeared only because its locked model was zero, while the main kept
  the old weapon; switching back to a two-hander now removes the shield too.
- **A monster that respawns starts without the previous fight's skillchain.**  `reset_mob`
  and `kill_mob` now clear `ZoneEntity.skillchain`; the stale state let the first weapon
  skill of a new fight close a chain nobody had opened (the "first WS skillchained" log).
  The chain log line now prints the `closer`, the `opener` and the `target`, and
  `SkillchainState.opener` records the character whose weapon skill opened the window.
- **A plain solo player gets its own group row at zone-in.**  The HUD reads the job pair from
  party row 0.  A solo login had no row at all, so the client reported `MainJob` 0 and the
  Trusts and Spells windows went empty ("No trusts for this job pair yet") — the trusts themselves
  had simply despawned with a restart.  The server now sends the empty `GROUP_TBL` plus the
  player's own `GROUP_LIST` row, the same shape a party disband uses; the Gear page's job pair
  comes back with it.
- Tests: `test_style_emotes.py` pins the two-handed ↔ one-handed + shield graphics and the
  locked armour; `test_world.py` pins the respawn clear; `test_party.py` pins the solo self row;
  `test_skillchain.py`, `test_weapon_skills.py` and the rest of the style tests stay green.

## Unreleased — Unity armour and grips reach the RP card, which marks capped paths

- **Blistering Sallet +1 and Rigorous Grip +1 are in the RP card's Unity catalogue.** The
  registry only carried Unity accessories (plus Loess Barbuta +1), so Unity armour and grips never
  appeared in the searchable list even though they have the same Rank 15 Lustreless augment.
  Blistering Sallet +1 is registered with client bundle 359 (Accuracy/Magic Accuracy +45,
  Critical Hit Rate +10%, STR/DEX +25) and Rigorous Grip +1 with bundle 327 (Attack +30,
  STR +15).
- **The RP card shows the augment a copy already carries and stops offering a redundant cap.**
  The item row has a **Capped**/**Augmented** badge, the path it is on is highlighted and labelled
  `capped` or `current (R7)`, and the button becomes **Finish path**/**Change path**;
  a fully capped path's button reads **Capped** and is disabled. Switching to another path is
  still one click and overwrites the block, as before.
- Tests: `test_unity.py` covers the armour and grip pieces, bundles 359/327 and the generated
  migration/docs; `test_augment_stats.py` still covers applying the Rank 15 rows.

## Unreleased — Wildfire keeps the Marksmanship tab, and the menu hides other jobs' skills

- **Equipping a GearSwap grant weapon no longer drops its weapon-skill tab.** Migration 66
  created the default-library rows with `items.skill` 0, and migration 111's catalogue upsert
  deliberately refreshes only price, `base_sell`, item level and the Rare/Ex bits. Armageddon
  (21269) therefore had skill 26 in `item_weapon` but skill 0 in `items`, so a COR's
  `sets.WS.Wildfire` made `equipped_weapon_skills()` treat the ranged slot as a non-weapon:
  `0x0AC` lost the whole Marksmanship block and the HUD's Marksmanship tab disappeared until the
  next Sword skill set equipped Ataktos or another skill-26 gun. Migration 170 copies the real
  type from `item_weapon`, and `service.item_skill()` falls back to that table so an existing
  database behaves before the migration runs. The same split affected Annihilator (21267),
  Gleti's Crossbow (22150), Chrono Bullet (21296), Daurdabla (18839) and Loughnashade (22307).
- **Relic, mythic, empyrean and merit weapon skills now follow the main job.** Skill value alone
  offered a COR every Sword and Marksmanship skill whose `skill_level` is 0: Atonement,
  Knights of Round, Death Blossom, Expiacion, Coronach, Trueflight and the rest. The new
  `game/weapon_skill_jobs.py` table encodes retail's main-job lists; Wildfire is RNG/COR,
  Leaden Salute COR, Atonement PLD, and the merit skills use the wider lists BGWiki publishes
  (Requiescat includes COR, Resolution does not). `equipped_weapon_skills()` filters 0x0AC and
  the `/ws` handler reads the same list, so the HUD and the server agree.
- Tests: `test_world.py` equips a COR with Naegling + Armageddon and checks that Wildfire and the
  Marksmanship skills survive the 0x0AC rebuild while Coronach, Atonement and Resolution are
  absent; it also checks a PLD and a RNG get their own skills. `test_weapon_skills.py` still
  covers the Prime/item-granted path. Docs: `docs/world.md`, `docs/control-panel.md`.

## Unreleased — support Trusts take the actions the owner picks

- **The configurable support Trusts now have a Set dialog in the Trust HUD.** Joachim, Luzaf,
  Qultada, Koru-Moru, Sylvie (UC) and Ygnas open **Call**/**Dismiss** plus **Set songs**,
  **Set spells** or **Set rolls** instead of casting at once. The catalog comes from the server
  with the level of every action, the click order is the order they are used, and each Trust has
  its own limit (4 songs, 12 spells, 8 rolls). Every other Trust keeps the one-click call and
  second-click release.
- **A `Use default logic` checkbox is the escape hatch.** Checked, the Trust runs its built-in
  rotation and the action list is read-only; unchecked, only the ticked actions are used. An
  empty set is the default logic too, so saving nothing does not leave a Trust idle.
- **`//trust <id|name> set songs|spells|rolls "..." ...`** is the chat equivalent. Koru-Moru,
  Ygnas and Sylvie get a restricted spell pool (the default AI still decides when each chosen
  spell is worth casting); Luzaf and Qultada get a roll priority list (the first selected roll
  not already on the party wins); Joachim keeps the ordered four-song bar. `//trust <id|name>
  list` shows the set and `set default` clears it. Non-Joachim sets live in
  `char_settings.trust_actions`, keyed by Trust spell id; Joachim keeps `joachim_songs`.
- **The HUD reads the catalogue through hidden `TrustData|` lines**, so a relog restores the
  checkboxes without chat spam. The old Joachim-specific `JoachimData:` line is gone.
- **Sylvie (UC) also has Geo-malaise.** The enemy-targeted Magic Defense Down hex is in her
  picker and custom list (migration 0172), with the Idris 30% potency.  When it is the only
  selected aura she puts it on the owner's current monster; between fights it is skipped
  because a hex needs a target.
- **A Corsair's default song plan is the melee set.** COR still counts as ranged for Qultada's
  Hunter's Roll, but Archer's Prelude is no longer chosen for it automatically; a shooting COR
  asks for Prelude (or any other set) by name. Ranger keeps the ranged default.
- Tests: `test_trust_gear.py` covers the restricted kit and selected-roll priority,
  `test_world.py` covers the persisted sets, the HUD data lines, Koru-Moru's spell pool and
  Luzaf's roll order, and `tests/trust_hud_test.py` runs the real picker against the six focused
  Trusts. Docs: `docs/world.md`, `docs/control-panel.md`, `docs/database.md`.

## Unreleased — level-1 skillchain loops stay open

- **`Savage Blade → Hot Shot → Savage Blade` now chains forever.** Every level-1 link keeps the
  full 11 s skillchain window instead of losing a second per link, so the classic Scission /
  Liquefaction loop no longer dies on the third weapon skill. Level-2/3 links still shrink by one
  second per step as in retail, and the Diamond Aspis still pins every step at 11 s.
- The retail loop needs the Diamond Aspis, which COR (the job that owns both Savage Blade and Hot
  Shot) cannot equip; WAR/WHM/RDM/THF/PLD/BST only. Fanxi makes the level-1 case work on every
  job. The window rule is in `skillchain._next_window`; the Battle hub planner and the HUD's
  skillchain clock use the same rule.
- Tests: `test_skillchain.py` adds the eight-step Savage Blade/Hot Shot loop and checks a level-2
  link still shrinks (16 tests pass). Docs: `docs/skillchains.md`, `docs/battle.md`.

## Unreleased — RMEA dispense pouches hand out their ammo

- **Using a Living Bullet Pouch (and the other RMEA quivers/pouches) now adds its stack of
  ammo instead of doing nothing.** These are charged waist equipment, not consumables: the
  piece stays equipped, 99 bullets/arrows/bolts land in the inventory, and the item starts the
  one-hour reuse timer from BG Wiki (1 charge, 10 s use delay, 3600 s reuse).
- The timer is stored on the pouch's own `char_inventory.extra` row and sent as the client's
  24-byte charged `ItemTimerInfo` block on `0x020`, so the item menu shows `1/1` and counts the
  hour down even after a logout. A second use before it is ready is refused by the server; a
  full inventory refuses without spending the charge.
- `item_dispense` (migration 0169) maps the eight RMEA pouches to their ammo and holds charges,
  use delay and reuse; `game/item_usable.py` builds and reads the timer block.
- Tests: `test_item_dispense.py` (catalogue, ready/used packet state, 99 bullets, cooldown
  refusal, expired timer, timer round-trip).

## Unreleased — Bard Nitro switch on the Battle hub's Buffs page

- **A BRD can check Maintain Nitro (Nightingale + Troubadour) on the Buffs page.** The engine reads
  the client's 0x119 ability recast table, waits until *both* abilities are ready, uses
  Nightingale, waits for it to land, uses Troubadour, and then hands the tick back to the song
  cycle so the set is cast under Troubadour. Songs still refresh while the pair is down; the
  Support page's Nitro set still limits the pair to the tank or support camp group.
- The status line under the checkbox shows each ability's remaining recast (or `not learned`), so
  a BRD can see why it is waiting. The Support page combo is now labelled **Nitro set** and points
  at the Buffs switch.
- Tests: the addon harness fakes the ability commands and recast table, checks that one ability
  down holds the pair, then drives Nightingale -> Troubadour -> song cycle. Docs: `docs/battle.md`.

## Unreleased — the Battle hub counts the live party, not every sub-account

- **The Roster, Party, camp, healing and buff lists now follow the characters who are actually
  logged in and grouped.** A shared profile can still name six characters; the hub marks roles
  for the ones not in the live party `(not in party)` and leaves them out of the active
  formation, support anchor and pickers. Logging the rest in and grouping them later brings the
  same saved roles back, so a three-box night and a full six-box party use one profile.
- **The header's EDITING selector lists only characters the server's live zone roster reports
  online.** `GET /api/v1/battle/team` now carries `online`/`online_known` (and the live zone) per
  character. When the gateway is off or the server is older, the selector falls back to the whole
  family instead of treating everyone as offline.
- Tests: `test_api.py` checks the live flags, and the addon harness now fakes a three-box party
  against a six-name roster to prove the counts. Docs: `docs/battle.md`.

## Unreleased — EquipViewer slots open a searchable wearable-item picker

- **Clicking a slot on the Gear page's EquipViewer, its legend or the selected-set preview now
  opens every wearable copy in the character's bags for that slot instead of a blank item-name
  box.** The list is filtered by the live main/support job pair and both levels, searches item
  names and augment rows, and shows the bag, iLv/Lv, stack count and augments. On the live
  EquipViewer and its legend a click equips the copy. On the Manage tab's set preview it replaces
  that slot in the set and writes the library immediately — the copy already in the set is marked
  **in set** and **Clear slot** removes it. **That preview used to equip the pick instead of
  saving it, so the slot looked unchanged once the dialog closed.** The set editor's picker now
  shares the same filter, so a job change in the Mog House updates both lists. Docs:
  `docs/launcher.md`, `launcher-rs/README.md`.

## Unreleased — Sinister Reign gear in the Data page, with one-click max augments

- **The Augments tab has a Sinister Reign card covering all 37 drops** from the wave bosses
  (Arciela, Darrcuiln, Ingrid, Teodor, Morimar, Rosulatia, Sajj'aka and August), grouped by slot.
  Pick an owned copy and **Give max augments** writes every row the wiki lists at the top of its
  range into the standard five-slot augment block; **Clear augments** empties it. The worked
  example is Samnuha Tights: FFXIclopedia lists STR+1~10, DEX+1~10, Double Attack+1~3% and
  Triple Attack+1~3%, and the button writes STR+10, DEX+10, `"Dbl.Atk."+3%` and
  `"Triple Atk."+3%` (ids `0x200`, `0x201`, `0x08F`, `0x090`). A live client reloads after the
  write, so the tooltip and the stat sheet both update; pieces not in the bags are preview-only
  with a pointer to the Armory.
- `data/sinister_reign.json` records every piece and its maximum rows. The ids reuse the Skirmish
  client table, with the magic-skill rows, Treasure Hunter, Pet: Ranged Accuracy and the combined
  Pet: Accuracy/Rng. Acc. word added. `augment_stats` still applies every modelled row to the
  stat sheet and lists the client-text-only skills in `UNMODELLED`.
- Tests: `server/tests/test_sinister.py` (catalogue, the exact Samnuha block, round trips,
  apply/clear and rejections), the `sinister` / `sinister-clear` ops in `test_api.py`, and the
  tooltip coverage walk in `test_augment_stats.py`. Docs: `docs/sinister-reign.md`,
  `docs/launcher.md`.

## Unreleased — Corsair rolls use their real tables, and Double-Up now busts

- **Phantom Roll overrides gear locks for its action and restores them.** The phase
  engine kept pinned weapon/ranged/ammo slots out of every job-ability set, so a locked
  COR could not wear Rostam/Compensator/Bayeux and the roll timer fell back to the short
  duration. The 31 roll actions now clear the full lock and slot pins while their set is
  built, record the pieces that were on, and restore them through the existing action
  override. The lock mask is unchanged afterwards.
- A refused job ability (recast, range, no target) never sends `0x028`; the held set used
  to stay on until another server packet. The watch loop now calls the new
  `xi.phase.stale()` and restores after 4 s for abilities (30 s for casts/skills), so a
  refused roll puts the locked gear back too.

- **Double-Up after the 45-second window is now an ability-check failure, not a fake
  action.** The old path still queued a Double-Up animation and recast even when
  `double_up()` refused with "Too much time", so the player could keep spamming it and
  never see a Bust. It now answers with the retail **NoEligibleRoll** message (428),
  sends no gear/action result and takes no recast. A missing `double_up_until` also
  counts as expired; previously a zero timestamp skipped the check entirely.
- The Bust status is now written with an explicit icon **309**, so the icon the server
  sends is the one the client's Bust entry uses. Party Info also shows the Bust icon and
  a red **BUST** label in its header (and `BUSTED` in the collapsed title), so the state
  is visible even when the native buff bar is not.

- **Snake Eye is consumed by Double-Up.** `double_up()` never looked at the flag, so a
  Snake Eye spent on Double-Up stayed armed and forced the *next* fresh roll to 11 as
  well (Magus's 11, then Corsair's 11). Double-Up now consumes it and sets the total to
  11; the following roll is ordinary again (verified live: Magus's 11, Corsair's 4).

- **Movement no longer spams "That item is already equipped."** The phase state sets
  hand back the whole set; `inject_plan` now skips a piece whose item id is already worn
  anywhere (including the other ring/ear), so the idle/movement lap only sends real
  changes. The ring swap that produced the two unique-ring refusals is gone too.

- **`sets.JA["Phantom Roll"]` now covers every roll.** The phase plan only matched the
  Phantom Roll door action id (97), but the client sends the individual roll (Fighter's,
  Samurai, Bolter's, ...), so GearSwap rolled in TP gear and the timer stayed at the base
  340 s. The plan expands the one family set to the 31 roll action ids; a live test with
  the full set now equips Rostam/Compensator/Gants +3/Regal/Camulus and saves 530 s.

- **Rolls are party buffs again.** `_party_recipients` called `ZoneSession.distance_to()`,
  which does not exist; the except branch returned only the caster, so every roll was a
  self-buff. The range check now compares positions directly. The server also sends S2C
  `0x076` (party member buffs, five 48-byte rows) after every roll/Double-Up/Bust/Fold,
  so the Party Info window shows each member's copy of the roll on all clients.

- **The roll picker shows Lucky and Unlucky totals, and chat marks them.** Each row (and
  its tooltip) now prints the roll's lucky and unlucky numbers; a roll or Double-Up that
  lands on one appends `(Lucky!)` or `(Unlucky!)` to the roll chat line. The HUD table is
  compared against the server's `rolls.LUCKY_NUMBERS` by `tests/cor_hud_test.py`.

- **Every one of the 31 rolls has its BG-wiki Roll Total table.** The old per-point lines were
  wrong at the lucky/unlucky totals and several rolls were mislabelled: Monk's rolled HP instead of
  Subtle Blow, Magus's rolled Magic Attack instead of Magic Defense, Bolter's rolled Ranged Accuracy
  instead of movement speed, Caster's rolled Magic Accuracy instead of Fast Cast, and Corsair's,
  Beast, Choral, Drachen, Puppet, Scholar, Courser, Blitzer, Tactician, Companion's and several
  others had no effect at all. See `docs/rolls.md` for the full table.
- **Bolter's Roll now visibly moves faster.** It writes LandSandBoat's
  `MOVE_SPEED_BOLTERS_ROLL` (1086) and the 0x037/0x00D speed byte is raised by the rolled
  percentage, capped at +60%. Live check: roll VI -> `MovementSpeed` 5.0 to 5.5, XI -> 6.0, bust
  -> back to 5.0.
- **Double-Up is a 45-second window from the roll that started it**, adds another die roll (1-6)
  rather than a flat +1, acts on the newest roll the player owns (not a Corsair Trust's party
  roll), and moves every party member's copy. The action result's `info` is the dice number, its
  17-bit `value` is the total (so "The total comes to ..." is no longer 0), and the message is
  RollMain/DoubleUp/Bust (420/424/426), so the client's dice number matches the roll instead of
  always showing 6. The old code let it run for the whole roll duration and always picked the
  first roll in table order.
- **Bust is a real status again.** Going over XI applies status 309, removes the roll from the
  caster and the party, and blocks new rolls until Fold, zoning or death. A different XI on the bar
  nullifies the Bust status (the doubled roll still leaves); Bust Evasion can keep the roll at XI.
  The bust status packet is sent, so the icon actually changes on the client. Reaching XI clears the
  Phantom Roll recast.
- **Roll duration stacks job points, Winning Streak merits and Phantom Roll duration gear**, up to
  retail's 11:00. The item rows for Chasseur's Gants +3, Camulus's Mantle, Lanun Knife and Rostam
  were missing modifier 882; migration 0168 adds them. A Corsair main keeps two rolls (one for a
  support job), and a lower re-roll replaces the old value instead of merging with max().
- **Tactician's Roll ticks Regain**, Evoker's/Dancer's rolls carry their Refresh/Regen tick,
  Avenger's Roll counters, Corsair's Roll multiplies EXP/Exemplar rewards, and the pet rolls write
  the pet's accuracy/attack/magic fields.
- **Job abilities log their name and id on use.** The 0x01A action packet is unchanged; the
  server now records `job ability <name> (<id>)`, which makes a refused or misrouted ability
  visible in `data/server.log` instead of only `action id=0x9`.
- Tests: `test_rolls.py` (all 31 tables, apply, re-roll, Double-Up window/newest, XI immunity,
  Bust, Fold, two-roll cap, party ownership) and the COR cases in `test_world.py` (all 31 rolls
  through a real 28-byte action packet, Bolter's speed byte). Docs: `docs/rolls.md`.

## Unreleased — a Corsair's Abilities page is two menus, not forty tiles

- **Phantom Roll opens a roll picker and Quick Draw opens a shot picker.** The client's
  `0x0AC` list advertises all 31 rolls and all eight elemental shots as individual actions, so a
  level 99 COR's Abilities window was a forty-tile scroll. The HUD now keeps **Phantom Roll** and
  **Quick Draw** on the page and moves the rest behind them: Phantom Roll opens a centered picker
  with a search box and a level-acquired/name sort, and Quick Draw opens the eight shots in
  element order as the same action tiles. A pick closes the picker and runs the normal `/ja` line;
  the roll rows and the **Phantom Roll** tile share the same 60-second recast clock, and a shot
  uses the action-tile cooldown sweep.
  A 99 COR's page is left with Phantom Roll, Quick Draw, Double-Up, Snake Eye, Random Deal, Wild
  Card, Triple Shot, Fold, Cutting Cards and Crooked Cards; a support-job Corsair sees only the
  rolls its level can use. The roll levels come from the server's `job_abilities` table.
  `//hud roll` and `//hud quickdraw` open the pickers without a tile click.
- Tests: `tests/cor_hud_test.py` (search normalisation, level/name order, element order and the
  page wiring). Docs: `docs/control-panel.md`, `docs/rolls.md`.

## Unreleased — REMA weapons are one final row in the Armory

- **A Masamune search now offers one weapon, not nine rows.** The catalogue stores
  Relic, Empyrean, Mythic and Aeonic upgrades as separate same-named rows, so the
  typeahead listed level 80 through iLvl 119 and Enter picked the weakest. The server
  now collapses each family to its final iLvl 119 III afterglow row (Masamune #21956,
  Excalibur #20685, Kikoku #21906), including the few final rows whose names carry a
  `119 III` suffix. A purchase of any earlier stage id is upgraded to the final, and
  holding any stage counts as owning the family because it is Rare.
- Tests: `test_rema_weapons.py` (family table against the item data, one-row search,
  final-form purchase and history). Docs: `docs/launcher.md` (Armory).

## Unreleased — Shantotto's Ascension augments in the Data page

- **The Augments tab now has a card for the add-on's three leg pieces.** Blitzer Poleyn,
  Desultor Tassets and Tatsumaki Sitagoromo share one 33-row augment table. Each bag copy shows
  its current rows and offers two dropdowns; applying writes the same standard 24-byte block the
  Ambuscade capes use, and clearing empties it.
- **Phantom Roll -5 is a real effect, not just a tooltip.** The Corsair row is augment id 0x154
  with block value 4. The server maps it to modifier 1076, and the Phantom Roll recast path
  subtracts it (60 s becomes 55 s). The piece must be equipped for the modifier to apply.
- **API:** `POST /characters/{id}/ascension` accepts
  `{container, slot, choices: ["phantom_roll_5"]}` or an empty `choices` to clear; the Data
  snapshot now carries `ascension.items` and `ascension.options`.
- Tests: `test_ascension.py` (option table, block round-trip, duplicate/unknown rows, the
  60→55 s recast) and `test_api.py` (catalog, apply, duplicate rejection, clear). Docs:
  `docs/launcher.md`.

## Unreleased — inventory-only mule sync

- **`tools/sync_inventory.py` makes several mules own the same items as one character.** It copies
  bags and wardrobes, storage slips and the locker in one transaction, leaving jobs, levels, exp,
  gil, merits, quests, Home Points and purchases untouched. Each target's gil row is rebuilt from
  its own wallet, and worn equipment/appearance models are cleared because the old equip
  container/slot values no longer exist in the copied inventory.
- The tool backs up the database first, verifies the three item tables match after the copy, and
  supports a dry run. Log the targets out before running and relog them afterwards; a client that
  was already in a zone still holds the old item slots.

## Unreleased — //reload no longer turns the character into an NPC

- **The reload's self entity update made the client ask for a full respawn.**
  `reload_character()` sent a self `0x00D`; after the burst the client asked for its own entity
  (`C2S 0x016`/`0x017` for targid `0x400`), and `request_entity()` answered with a full
  `SEND_CHAR_SPAWN` including the name and model blocks.  That full spawn is the green-name/NPC
  state that locks attacks, menus and item use until a relog.  The reload now sends **no** self
  `0x00D` at all (0x061/0x037/0x0DF carry the vitals), and a post-zone-in self entity request gets
  the General-only 0x00D plus 0x037; the full spawn is kept only while the zone-in is still
  loading and the entity does not exist yet.
- Tests: `test_character_data.py` pins that `//reload` queues no 0x00D, that a mid-session self
  request gets the 0x44-byte General update, and that the pre-zone-in request still full-spawns.

## Unreleased — the launcher edits every merit group

- **The Data page has a Merits tab that mirrors the game's merit menu.** The left rail lists the
  six general categories and all 22 jobs; each menu is a form group with one stepper per merit.
  The character's main job opens selected, each menu shows its upgrade cap and point cost, and
  **Clear menu** empties one menu without touching the others. The summary tracks the pending
  rows, the chosen layout's point cost and the unspent pool.
- **The server ships the whole catalogue.** `GET /characters/{id}/data` now returns
  `merits.categories`: 50 menus, 274 labelled rows in the client's order, with individual caps,
  cost ladders and current ranks. `POST /characters/{id}/merits` accepts
  `{"upgrades": {"384": 5}, "spend": false}` beside the older point/top-off forms, validates
  each row and each menu's category cap, and charges or refunds the net difference when
  `spend` is true. The default direct mode assigns ranks without moving the unspent pool, like
  the other assignment cards; a layout assigned before this editor existed can be lowered even
  when it already sits over a menu's cap.
- **A live client reloads the new ranks.** The existing `//reload` burst carries the assigned
  rows and the recomputed stats, and the Overview merits card now links to the new tab.
- Tests: `test_api.py` (catalogue shape, direct writes, cap refusal, spend/refund, legacy
  over-cap lowering, top-off) and `test_character_data.py` (`//reload` rereads a layout). Docs:
  `docs/launcher.md`, `docs/server.md`.

## Unreleased — a locked weapon stays on through a job ability

- **DRK Last Resort no longer replaces a pinned Helheim with a scythe.** The phase
  engine's locked-action override used to clear every pin and the full lock, wear the
  action's whole set, and restore it afterwards. The DRK library's
  `sets.JA["Last Resort"]` names Apocalypse, so pressing Last Resort while a great sword
  was pinned put the scythe on for the action; the server then rebuilt `0x0AC` around
  Scythe and every great-sword weapon skill disappeared from the menu until the restore.
  A job ability or spell/song now keeps **main, sub, ranged and ammo** pinned while it
  wears its armour, then restores that armour. A **weaponskill still swaps the weapon**
  it needs (its damage is rolled from that weapon) and `xi.phase.remember` puts the
  exact pinned piece back when the skill resolves. The full **Lock** follows the same
  weapon rule for actions with a set.
- Tests: `tests/phase_lock_override_test.sh` now checks that a locked/pinned main is not
  sent by a job ability, a pinned sub survives one, and a weaponskill still swaps and
  restores the sub. Docs: `docs/control-panel.md` (Idle states, Weapon pins).

## Unreleased — the Master chain window starts at 60 seconds

- **Exemplar Points chain at a normal solo kill pace again.** The first version used a
  flat 30-second window, which is the *floor* retail reaches late in a chain, not the
  first window. A live DRK killing a Locus every 31-39 seconds therefore never saw even
  Master chain #1. The window now starts at **60 s** and shortens with the chain,
  reaching the 30 s floor at chain #25 (`chain.window_for`); `kill_mob` picks the window
  from the chain the kill just became, so a broken chain gets the full 60 s again. Each
  qualifying kill also writes the points, base and chain number to `server.log`
  (`<addr> <mob>: N exemplar points, Master chain #N (base N)`).
- Tests: `test_chain.py` (window curve, 45 s still chains) and `test_world.py` (a 45 s
  gap prints message 810 chain #1; a 61 s gap is a fresh chain #0).

## Unreleased — attack speed shows its real caps, and the 80% floor uses the base delay

- **The checkparam report now shows what the swing actually does.** A live 431-delay
  Helheim DRK read `Haste (magic) 66.99` from Cornelia (20%), Haste (30%) and Advancing
  March (16.99%), which looks capped even though the sheet clamps the pool to 43.75%.
  The report gains `haste_total` ("Haste (capped pools)") with the gear/magic/ability
  values after their individual caps, `attack_interval` (the round's real seconds) and
  `tp_per_hit` (after Store TP).  The live character's effective total is 66.75%, a
  2.388 s round and 122 TP a hit before its 25% Store TP; gear + magic alone top out at
  68.75%, so a two-handed job needs the job-ability pool (Last Resort/Desperate Blows)
  to reach the 80% floor.
- **Hasso and Desperate Blows are part of the report's source sum.** Their status
  effects carry no mods, and `combat_mods()` used to add their STR/Accuracy/ability
  haste after the report had already summed its sources, so the report's sheet could
  disagree with the swing.  They are now rows in the Job abilities source, and
  `combat_mods()` is a plain sum of that source.
- **The 80% delay floor is measured from the base delay.**  `Sheet` keeps the delay
  before Dual Wield / Martial Arts; the final round is clamped to 20% of *that* value,
  not 20% of an already-reduced one.  A 35%-DW pair with every haste pool capped no
  longer reaches 13% of the base delay (retail's rule is
  `(1 - DW%) x (1 - haste%) >= 0.2`), and the same applies to Martial Arts.
- Tests: `test_combat.py` (capped pools, DW/H2H floors, Store TP), `test_stat_report.py`
  (the three new rows and Hasso in the report's sheet).  Docs: `docs/combat-damage.md`.

## Unreleased — one damage line can print at most 99,999

- **Damage is clipped at 99,999 everywhere.** The 2026-10-29 session's Fimbulvetr landed
  three hits for **114,767** in one action result. A multi-hit weapon skill is one client
  damage line, so its hits are summed and the total is clipped to 99,999. Every other
  damage event uses the same ceiling: each auto-attack/ranged swing, a spell after Magic
  Burst and Sengikori, and the skillchain hit. `combat.DAMAGE_CAP` / `combat.cap_damage`
  run where the number is built, so the monster's HP loss, the hate and the drains
  (Sanguine Blade, Spirit Taker) match what the client prints; `queue_action` repeats the
  clip as a last line of defence and warns if a path ever reaches it. A monster with more
  than 99,999 HP left therefore survives a 120K weapon skill: only the clipped number is
  applied, and the round's `defeated` flag now compares that clipped total.
- Tests: `test_combat.py` (per swing, spell and the helper), `test_skillchain.py` (the
  chain hit and Sengikori), `test_world.py` (a three-hit 120K weapon skill, a 150K monster
  surviving it, and a boosted 99,999 hit). Docs: `docs/combat-damage.md` ("The 99,999
  ceiling"), `docs/skillchains.md`, `docs/prime-weapon-skills.md`.

## Unreleased — the Armory sells the final Prime weapon

- **One row per Prime weapon.** A Sortie Prime family stores four upgraded items under one
  name, so the typeahead listed four identical `Foenaria` rows at 283,220 gil each; the
  first row — the weakest stage — was the one Enter selected. The Armory now maps every
  stage id to the family's iLvl 119 III form and returns one row, including for the stage-1
  `Prime ...` name (`Prime Scythe` finds Foenaria #21837). The row and the purchase card
  label it **Final** / **Prime final**, with **Stage 5 of 5** in the card.
- **Purchases are always final.** `armory_add` upgrades an earlier stage id before it
  charges the wallet, so another client cannot buy stage 2 by posting its item id. The
  purchase history records the final id and badges it.
- **Existing copies are repaired.** Migration 0164 retargets earlier-stage Prime weapons
  in the bags, storage slips, locker, equipped set and purchase history to the final id.
  Prime weapons are Rare, so a character that bought several stages keeps one copy: the
  equipped bag row wins, then an existing final, then the highest stage; storage and the
  locker yield to a bag copy the same way migration 103 handles other Rare gear.
- **Every final form carries its iLvl 119 III block.** Migration 0165 fills the stat and
  skill rows the other Prime weapons were missing: STR/DEX/VIT/INT/MND, Accuracy, Magic
  Accuracy, the weapon traits (`"Double Attack"+10%`, `"Store TP"+10`, `"Triple Attack"+6%`,
  `"Refresh"+4`, `Damage taken -10%`, …) and the secondary Guarding/Parrying/Shield
  skills. It also fixes the rows that were still the 119 II values: Helheim's DMG 318 →
  **336**, Lorg Mor's 227 → **240**, Mpu Gandring's Dagger skill 269 → **277**, and
  Varga Purnikawa's `Critical hit rate +15%` was stored as 15 hundredths (0.15%)
  instead of 1500. Dokoku keeps its Katana +277 in `item_skill_bonus` (migration 63)
  rather than duplicating it in `ilvl_skill`.
- **One Opashoro per box.** Migration 0166 is a safety net for the duplicate 22106 that
  an older in-place conversion could leave behind: the converted GearSwap-grant copy at
  container 8 slot 46 is dropped where the box already has the original afterglow in
  wardrobe 2, and character 1's bag copy is kept while its locker copy is dropped.
- Tests: `test_prime_weapons.py`, and the API armory test in `test_api.py`;
  `test_stats.py::PrimeAfterglowItemDataTest` pins migration 0165. Docs:
  `docs/launcher.md`, `docs/database.md`, `docs/prime-weapon-skills.md`.

## Unreleased — Dark Knight damage reaches retail

- **Smite is applied to Attack.** The trait was in the table but nothing read it. With a
  two-handed or hand-to-hand main hand it now adds its 1/256 value as a percentage
  (DRK 95's 76 is +29.6%), exactly where LandSandBoat folds it into `ATTP`. One-handed
  and off-hand swings are unchanged. For a DRK with Foenaria this is the single largest
  missing multiplier: on the live unbuffed sheet Attack goes from 1,221 to 1,575 before
  any gear or buff changes.
- **Last Resort, Desperate Blows and Souleater are no longer icons only.** Last Resort
  is +25% Attack / -25% Defense for 180 s; Desperate Blows adds its 15% (plus 2% per
  merit) to job-ability haste while Last Resort holds a two-handed weapon; Souleater
  adds Accuracy+25 and converts 10% of current HP into flat damage on each landed hit
  (half the damage on a support job, less HP paid with Stalwart Soul). The flat damage
  goes in after pDIF/fTP and before the target's damage-taken gear, so PDT still applies.
- **Foenaria carries its stat block.** Migration 87 gave the Prime weapons only the
  `Adds weapon skill` row, so Origin was being fired at 424 Scythe skill instead of 701
  and without the weapon's STR/INT/Accuracy/Triple Attack. Migration 161 restores
  `Scythe skill +277`, `STR+35`, `INT+35`, `Accuracy+35`, `Magic Accuracy+35`,
  `"Triple Attack"+6%` and `Parrying skill +277` from the iLvl 119 III item data.
- On the same unbuffed 1,256-TP test the combined fix moves Origin from about 4.8K to
  10.9K with Last Resort; the live parse's buffs sit on top. Tests: `test_combat.py`
  (Smite, flat damage before DT), `test_stats.py` (migration 161), `test_effects.py`
  (Last Resort/Souleater mods). Docs: `docs/combat-damage.md`,
  `docs/prime-weapon-skills.md`.

## Unreleased — a claimed monster stays claimed

- **A cross-party hit can no longer take the claim.** The client draws a monster claimed by
  another party pink and refuses to attack it, but `add_mob_hate` moved the claim to whoever
  held the most hate.  Another box's Trust could therefore flip a live fight pink, and the
  party that was actually fighting it could no longer swing — while the server's engagement
  loop kept landing hits for them.  A hit from outside the claiming party is now ignored for
  the claim and for the monster's hate target.
- **An engagement on a foreign claim ends.** The engage loop disengages when the target's
  claim belongs to another party, instead of swinging at a monster the client will not attack;
  this is the state that could not be dropped from the client side.
- Diagnostic: the `engage:` line now prints `tp=`, and `gain_tp` logs each change, to follow
  the report that the TP bar stayed at zero while swings landed.
- Tests: `test_effects.py` — a cross-party hit leaves the claim alone, and a party member may
  take it.  Docs: `docs/world.md` (claims, Trust enmity).

## Unreleased — the Target Debuffs window finds its character

- **The target poll uses an id the server accepts.** The in-game HUD only knows the player
  entity's ServerId (`0x01000000 | char_id`), while `/api/v1/characters/<id>/target` resolved
  database row ids only — every poll was a 404, and the window drew the JSON error body as
  `Server state: table: 0x0164b1b800`. `_data_character` now falls back to the long id (the two
  ranges never overlap), so the poll resolves the same character; the launcher's row-id routes
  are unchanged.
- **An error is readable.** The window formats an error object by its `message` (or `code`),
  under a "Target info unavailable:" label, instead of `tostring` on a table. The old label made
  the failure look like a character status.
- Tests: `test_api.py` — both the row id and the long id resolve the character (and stop at
  "not in a zone" rather than "character not found"). Docs: `docs/control-panel.md`
  (Target Debuffs).

## Unreleased — movement waits for a real yalm, and the team steps aside

- **The movement set waits for one yalm of travel.** `watch_phase` wore `idle.movement` on any
  0.01-yalm change in the position sample, and measured its stop delay with `os.clock()` —
  process CPU time, which with the render and network threads busy runs several times faster
  than wall time. A still character's sample noise therefore flipped `idle.movement` and
  `idle.dt` back and forth, each flip a whole equipment batch (and a fresh model swap for the
  client). The movement state now needs **one yalm of horizontal travel** from the spot the
  character last stood before it goes on (Y is height, not travel), a 0.02-yalm sample is the
  smallest motion that counts as a step, and the 1.2 s stop delay runs on `xi.clock()`
  (monotonic wall time). A sample over 20 yalms is a zone line or a teleport, not a step.
- **Trusts and pets step out of the player's collision bubble.** The client collides the player
  with its own team; a follower that stopped on the character blocks every step, because the
  blocker sits inside the collision radius and the player cannot walk out. A Trust or pet
  inside `TRUST_PERSONAL_SPACE` (1.2 yalms) of any player now steps away at
  `TRUST_SIDE_STEP_SPEED` (3 yalm/s) and streams the position, so the team yields instead of
  trapping the player. The client has no "walk through party" flag the server can set — this is
  the practical equivalent for getting unstuck.
- **One action, one set.** The client resends its `0x01A` until the server acknowledges it, and
  the host hook saw every copy: one weaponskill registered four times in the client log and
  queued its 15-piece set four times — sixty injected `0x050`s for a single action. The phase
  engine now ignores a repeat of the same category and action that carries the same packet
  sequence number (a retransmit is the same packet; the pending flag alone missed the copies
  that arrive after the result has cleared it) within a three-second window. In the fight that
  produced the 2026-10-28 21:55 freeze — and again in the 00:33 one, where Fimbulvetr
  registered three to five times — this is most of the harness churn.
- Tests: `test_world.py` (a Trust inside the bubble steps out and streams its position); the
  addon phase harness (`phase_state`, `phase_job`, `phase_history`, `phase_precache`,
  `phase_lock_override`, `gear_queue`) passes against the rebuilt client. Docs:
  `docs/control-panel.md` (the movement state), `docs/world.md` (Trust alter egos).

## Unreleased — Trust loadouts and the Master's gear

- **Sylvie (UC) carries Idris.** Her Geomancy is the mythic's: at Geomancy +10 the Indi-
  spells use the Idris column of BGWiki's Geomancy table — Accuracy +50, Attack +27%,
  Haste +11%, Regen +20 HP/tick, Refresh +10 MP/tick, Magic Atk. +30 — and her hexes cut
  harder (Frailty 27% Defense, Torpor 50% Evasion, Wilt 46% Attack, Vex 60% Accuracy,
  Languor/Slip 50/60 Magic Defense and Evasion).  The plain table is what every other
  Geomancer still casts.
- **Joachim carries the Prime Loughnashade.** His horn is the final iLvl 119 III
  Loughnashade (item 22307, migration 167) instead of the Daurdabla/Gjallarhorn pair: Song
  +4 and Maximum Songs +2 in one instrument, so the four-song bar and the potency column
  are unchanged, CHR +20 replaces the pair's skill lines, and the 30% Daurdabla timer is
  gone (songs last 40% past base from Song+4 alone).  Migration 167 also adds Honor March
  and the lower Minuet tiers (IV at 63, III at 43) to his list, so a Master below Valor
  Minuet V's level 75 still gets an Attack song.
- **Joachim sings what the owner needs, not his spell list.** No Paeons or Elegies:
  `trust_ai.choose_songs()` plans Victory March while the owner's magic haste is
  short -- and **Honor March** once that Haste would be redundant, since the two share the
  March status and Honor trades it for Attack, Accuracy and the ranged lines -- Valor
  Minuet V to cap Attack, and Aria of Passion (Damage Limit) once the
  Attack/Defense ratio reaches the weapon's pDIF cap -- the one thing left to buy when
  Attack is capped.  The fourth slot then goes to Blade Madrigal while the
  owner's swing lands under 95% (`ACCURACY_SONG_SHORTFALL`, the same `combat.hit_rate()`
  reading the Geomancer uses for Indi-precision, now shared through
  `World._fighter_hit_rate()`); above that the slot stays empty rather than being filled
  with a song the owner does not need.  A mage gets Mage's Ballad III, and a Ranger or
  Corsair gets March, Archer's Prelude and Minuet for speed and the ranged lines
  (Prelude is their Accuracy, so Madrigal would waste the slot).  Migration 160 adds the
  three songs his imported list was missing (Minuet V, Archer's Prelude, Aria of
  Passion); Ulmia keeps the plain rotation until she is asked for.
- **A Trust grows with its Master.** Every alter ego inherits half of the owner's gear
  modifiers — Attack, Accuracy, HP, MP, Defense, Evasion and the seven base stats — at
  item level 119, scaled by the owner's average item level, so a fully geared set lifts
  the Trust with it and an ungeared owner lends nothing.  The share is re-read on a slow
  beat, so a mid-session set change follows.
- **Qultada and Luzaf roll for the party and never swing.** `trust_ai.choose_roll()` reads
  the party the way Joachim's songs do — composition, MP and the melee's Attack cap —
  instead of rolling by the owner's job: Evoker's Roll (Refresh) when a caster is under
  half MP, Wizard's Roll for a caster-heavy party, Hunter's Roll for a ranged-heavy one,
  **Chaos Roll** while the melee are short of Attack and **Samurai Roll** (Store TP) once
  the Attack/Defense ratio reaches the weapon's pDIF cap.  The amounts are BG-wiki's
  per-total tables (`RollSpec.table`), because the lucky and unlucky totals jump — Chaos
  IV is +25% Attack where VIII is +3.12%, and a per-point line had Chaos at a flat +3
  Attack, which is why the rolls felt like they did nothing.  The roll lands on every
  party member in the zone for **100 seconds** -- `rolls.duration()` of a maxed Corsair,
  the Phantom Roll Duration job-point row at 20 ranks -- and the Trust keeps its roll for
  the whole fight (a per-refresh re-decision made Chaos and Samurai trade the slot); a
  second Corsair takes the next useful line (`RollNeed.active`) so the pair holds Chaos
  and Samurai rather than duplicating one.  Both Trusts skip the attack path entirely — no
  auto-attack and no weapon skill — and stay beside their owner.
- The weapons are factual rows in `trust_gear` (migration 159); LandSandBoat scripts
  Idris's Geomancy +10 rather than storing it as an `item_mods` line, so `trust_gear.py`
  adds it by item id.
- Tests: `test_trust_gear.py` (Idris numbers, both instruments, the rating scale, the
  song plan for each role) and `test_world.py` (Sylvie's hex lands at 27%, Joachim's song
  lands with the instrument mods and no Paeon/Ballad, a Trust's bars grow with the
  Master's set).  Docs: `docs/world.md`,
  `docs/database.md`.

## Unreleased — Sylvie picks the aura the fight needs

- **Geomancy is one aura at a time, chosen by need.** The kit builder had turned every Indi-
  spell into an ordinary buff, so Sylvie (UC) put all six on her owner and hexed the monster in
  one burst. A Geomancer keeps one aura per bubble, so `trust_ai.choose_aura()` now decides per beat
  from the measured situation (`trust_ai.AuraNeed`): **Indi-refresh** when the owner or a
  teammate is below half a mana bar, **Indi-acumen** for a caster owner, **Indi-precision** when
  the owner's hit rate against the current monster is under 80%, **Indi-fury** when the
  Attack/Defense ratio is under 1.3, and otherwise **Indi-frailty** — the Defense cut that
  helps every physical hit the team lands, and the play outright when a weapon skill is ready
  and the team fights in melee. A swap waits eight seconds so two needs either
  side of a threshold cannot make her flap, and the previous aura comes down when the new one
  lands, on the owner's bar and on the monster.
- **The player path works the same way.** `_indi_aura()` used to leave every aura it had
  cast on the party; a cast now replaces that bubble's last aura there and on the monster.
  Indi- and Geo- are separate bubbles, so Indi-haste and Geo-frailty coexist, but a second
  Indi- takes the first one down for everyone, and a new hex clears the old one off the
  monster.
- **GEO hexes are real now.** Frailty takes its 10% off the monster's Defense for melee and
  weapon skills (`debuffed_monster`), Torpor off its Evasion, Vex off the monster's Accuracy and
  Wilt off its Attack, and Languor/Slip feed the magic Defense and Magic Evasion the spell path
  reads. They are separate effects from Dia/Defense Down, so they stack the way retail's do.
- **She keeps one up out of combat, and healing no longer starves it.** Two things made
  calling her look like she never cast: with no monster to measure the chooser returned
  nothing, and in a fight the 85% heal rule fired before the aura on every beat, so a hurt
  owner stayed in cure-forever. The out-of-combat default is now Indi-precision (Accuracy
  moves every hit), falling back to Attack, Regen or Refresh; and the aura is chosen before
  the cure unless the owner is under 40% HP, which is the only case where the heal wins.
  The pick is logged as `<Trust> puts up <spell>`.
- Tests: `test_world.py` — the chooser picks each aura for its need, Sylvie keeps exactly one
  aura and swaps to Refresh when the owner's MP drops, a player's Indi- replaces the previous
  Indi- for the party while a Geo- hex lives in its own bubble, and the hexes lower the
  monster's Defense/Evasion.

## Unreleased — the gear follow-up only sends what changed

- **A gear batch no longer re-sends the whole derived block.** `flush_equipment()` used to send
  the grap list, magic data, the job ability table, command data, the incremental command update
  and the stat sheet after every batch — about 700 bytes, and the client is served one packet per
  ack, so a burst took several exchanges. Each of those packets is now remembered by payload as
  it leaves (`pack()` records it, so the zone-in bundle, the `0x061` reply and `//abilities` seed
  the same baseline) and `equipment_sync()` queues only the copies whose payload changed. An
  armour swap sends the grap list and the stat sheet; `0x0AA`/`0x0AB`/`0x1A5` are job-derived and
  stay, and `0x0AC` — the packet that makes host64 rebuild its whole ability list, and the last
  log line before every client freeze in the 2026-10-27/28 logs — is re-sent only when the
  command bitmap changed (another weapon skill type, a Prime weapon's granted skill, a job
  change).
- **One follow-up per burst, not per datagram.** A set arrives as one `0x050` per slot over
  several datagrams. The per-slot echoes are unchanged and immediate, and the outfit save and
  `refresh_vitals` still run as each datagram is read (a weaponskill can share it with its
  precast gear), but the derived packets wait `EQUIP_SYNC_DELAY` (150 ms) after the last slot —
  capped at `EQUIP_SYNC_MAX_DELAY` (600 ms) while the phase engine keeps flapping — so a burst
  owes one follow-up. The `0x037` signature ignores its Vana'diel clock and unix stamp fields,
  so a swap that leaves HP, buffs and animation alone does not poke the client's pose.
- Tests: `test_world.py` — the first follow-up carries everything, an armour swap leaves the job
  blocks and command data alone, a weapon of another skill type rewrites `0x0AC`, and a burst
  split over datagrams owes one follow-up. Docs: `docs/world.md` (The equipment follow-up).

## Unreleased — Sylvie (UC) casts her geomancy

- **Sylvie (UC), the one Trust that casts Geomancy, now uses her Indi- spells.** Her seven
  `mob_spell_list` rows under Geomancy were dropped by the kit builder: `effects.SPELLS` has
  no entry for the Indi-/Geo- family (the zone server applies those auras from
  `geomancy.INDI_EFFECTS` by spell name), so `trust_ai.effect_of()` returned `None` and she
  was left with Cure and Haste only. `effect_of()` now falls back to the geomancy table and
  turns each aura into a buff or enfeebling effect, so her Indi- spells reach the AI (the
  rotation that decides which one is cast is the next entry).
- **Indi-slip / Geo-slip carry status 564.** They were mapped to 540, which is GEO Poison, so
  a Slip aura replaced the Poison aura and drew its icon.
- Tests: `test_world.py` pins the auras in Sylvie's kit and checks one lands with its own icon;
  a second test pins Slip to 564.

## Unreleased — Koru-Moru keeps Haste II up instead of Flurry II

- **Koru-Moru no longer casts Flurry or Flurry II.** Both tiers are the same status (581)
  and only speed up ranged attacks, while his buffs land on a melee owner, so a per-Trust
  tactic drops the family from his kit and Haste II is the attack-speed buff he keeps up.
  Every character that calls him gets Haste II from its own Koru-Moru; Flurry no longer
  spends a cast or a buff slot.
- Tests: `test_world.py` pins Haste II in Koru-Moru's kit, no Flurry in the rotation, and
  no buff left to cast once Haste II is up. Docs: `docs/world.md`.

## Unreleased — Equip View, the in-game equip viewer

- **A new HUD window draws the worn gear and names the set.** **Equip View** is the in-game
  EquipViewer: the 4x4 grid (main/sub/range/ammo, head/neck/ears, body/hands/rings,
  back/waist/legs/feet) with the game's own item icons, read from the client every frame, so a
  swap draws the instant it happens — what the original addon bought with its `0x050` packet
  hook. Collapsed, the title bar carries the set the phase engine is wearing (`WS.Blitz` while
  a weaponskill holds its set, in gold), with the age of the action set.
- **Toggle it with `//equipview [on|off|toggle|reset]`** or the launcher's Control room
  (**Equip View**). Position, collapsed state and the on/off switch persist with the other HUD
  windows; pinned slots draw a red border. On by default. The window has no scrollbar:
  the 4x4 grid is laid out to fit, and ImGui's bar was only clipping the last row.
- Tests: the phase harness (`tests/phase_state_test.sh`, `tests/phase_history_test.sh`) loads
  the control addon, so a Lua error in the new window fails the suite. Runtime 0.2.77.

## Unreleased — the Gear page shows every set the engine wears

- **The live gear line names the action set while it is on.** `phase_status` now reports
  `actionSet`, `actionMs`, `actionId` and the last 16 windows (`history`), so the Gear page's
  "wearing" line shows `WS.Blitz` during a weaponskill instead of the state set, with a badge
  for how long it has been on.
- **A poll can no longer miss a swap.** A weaponskill's set is only on between the held action
  and its result (about a second), which is shorter than the gear poll. The engine records each
  window itself and the Gear page draws them as a **Recent** strip, so the sets are visible even
  when a sample landed after the restore. The page also polls `phase_status` every 400 ms and
  refreshes the EquipViewer the moment a new action set appears.
- **`//gs status` names the action set too**, with its age, while it is on.
- Tests: `tests/phase_history_test.sh` runs the engine harness and pins the action set, the
  window closing on the result, and the newest-first history; `phase_state`, `phase_job`,
  `phase_lock_override`, `phase_precache` and `gear_queue` stay green. Runtime 0.2.75 so the
  launcher rebuilds a host64 made before this change.

## Unreleased — restored cooldowns are dark in the Abilities hub

- **A job ability used before a logout now comes back on cooldown in the HUD, not just on the
  server.** The server already wrote its remaining recasts to `char_live_state`, restored them on
  the next login and sent them on `0x119`; the hub only polled `ability_recast` for timers it had
  started itself, so after a relog its cooldown map was empty and Bestial Loyalty drew as ready.
  A click then reached the server, which answered "Bestial Loyalty is not ready yet." The hub now
  reads the whole `ability_recast` table every poll and learns a cooldown it never saw start.
- **The recast table is in the zone-in burst.** `0x119` was sent when the client asked for stats
  and on the two retries; the login and zone-in bundles now carry it too, so the restored timers
  reach client memory before the HUD draws the Abilities window.
- Tests: `tests/hud_cool_test.py` runs the HUD's real cooldown rules (restored timer, shared
  recast ids, pending bar, empty table) and checks the poll is unconditional; `test_world.py`
  pins Bestial Loyalty to recast id 94 with its 20-minute timer; `test_reconnect.py` checks the
  restored 94 timer is in the login burst before `0x061`. Docs: `docs/control-panel.md`,
  `docs/world.md`. Runtime 0.2.73 so the launcher rebuilds a host64 made before this change.

## Unreleased — every hub collapses to its title bar

- **Stats, Party Info, Target Debuffs, Magic Bag and the Battle HUD now all collapse with the
  normal ImGui title-bar caret.** There is no second minimize row and no Min/Restore button: click
  the caret to collapse, click it again to expand. Stats and Party Info keep their Hide button;
  Target Debuffs, Magic Bag and the Battle HUD also keep their title-bar X.
- **The collapsed title bar carries the hub's key status.** Stats shows DPS, TP/sec and FPS;
  Party Info shows member count and lowest HP; Target Debuffs shows target HP and debuff count;
  Magic Bag shows item count and selected bag; the Battle HUD shows RUNNING/STOPPED plus the
  current target's HP.
- **All of them drag by the title bar, and both the collapsed state and position persist.** The
  four control-addon hubs store `collapsed` and their position in the character's HUD file; the
  Battle HUD stores `camp_hud.collapsed` and its position in the Battle profile. A logout/login
  reopens the same minimized bars in the same places. Magic Bag now saves its position too.
- Docs: `docs/control-panel.md`. Tests: Lua syntax/build and live collapse checks.


## Unreleased — Target Debuffs minimises, and the Control room gains the Battle HUD

- **Target Debuffs has the same window controls as the other HUD windows.** Its title-bar arrow
  now collapses it to the title, the title-bar X closes it, and a **Hide** button does the same
  from inside. `//hud target` / the Control room switch opens it again; the choice is saved in
  the character's HUD file.
- **The Control room shows Battle HUD beside the other hubs.** The new switch drives the camp
  Battle HUD (the radar/roster window) through the Battle profile's `camp_hud` setting, so it
  stays in sync with that window's title-bar X.
- **"Show battle info" is now "Stats"** in the Control room and the window title. The saved field
  (`show_battle_info`) and `//battleinfo` command keep their existing names.
- Tests: `npm run check`, Lua smoke test for the target window controls; docs updated.

## Unreleased — Target Debuffs HUD and working Frazzle/Distract

- **The mob's debuffs are now visible.** The retail client has no monster buff list, so the
  zone server exposes the selected target's live effect state at
  `GET /api/v1/characters/{id}/target?entity_id=...`; the control addon polls it every
  0.75 s and draws a **Target Debuffs** window. Rows show the effect icon, name, remaining
  time and potency/tick; the window follows target changes, hides with the other HUD
  windows, remembers its position, and is toggled with `//hud target` (on by default).
- **Frazzle was landing as a no-op.** The generated icon table gave effect 404 a 120-second
  duration and zero potency, so `monster_debuff_mods` subtracted nothing. Frazzle is now
  -35/-50/-130 Magic Evasion for 5 minutes at the tier caps and uses dMND plus the spell's
  innate +150 Magic Accuracy; Distract likewise gets -35/-50/-130 Evasion for 5 minutes.
  Dia already lowered Defence through `debuffed_monster`; the new window shows its real
  percentage and damage tick.
- Tests: `test_effects.py` (Frazzle potency/MEVA delta/target report, Dia and Distract
  report), Lua smoke test for `//hud target`, and a live API check against a selected mob.
  Docs: `docs/control-panel.md`, `docs/job-points.md`.

## Unreleased — Grand Pas

- **Grand Pas** now resets the flourish recasts, makes flourishes cost no finishing moves
  and skips their recast while active, and ends after three flourishes.
- Test covers three flourishes with zero finishing moves.
- DNC Grand Pas is no longer icon-only.

## Unreleased — Indi/Geo aura layer

- Added `geomancy.py` with the 30 Indi/Geo aura definitions (statuses 539-567/580) and
  their stat modifiers.
- **Indi spells now apply their aura to the caster and nearby party members**, and
  negative Indi/Geo auras apply to the target.
- **Entrust** now makes the next Indi spell cast on the selected party member; the
  status is consumed and the aura lands on that ally.
- Test: Indi-regen and Entrusted Indi-regen are covered end-to-end.
- **Collimated Fervor** still only carries its status: Cardinal Chant, which it modifies,
  is not implemented in this server.
- Full matrix after the aura layer: **293 mechanic / 61 chat / 5 menu / 0 no-ops**.

## Unreleased — zero no-ops in the matrix

- Full smoke matrix now reports **293 mechanic / 61 chat / 5 menu / 0 no-ops**.
- GEO's six Luaopan modifiers now manipulate real Luaopan state (drain, potency, MP cost)
  instead of empty branches.
- The Indi-/Geo- spell **aura propagation** is still the next layer: Geo spells place a
  Luaopan and set its state, but the aura's stat effect is not yet applied to every party
  or enemy in range.  Entrust/Collimated are therefore status-complete but still need that
  aura layer to have their full retail effect.
- Ranged Shoot, Bounty Shot, Scavenge, Stealth/Flashy Shot, monster steal table and Steal
  are implemented and tested.

## Unreleased — GEO Luopan modifiers

- Luopan now carries geomancy state: **HP drain** (24 HP/tick), **potency**, and the MP cost
  of the Geo spell that placed it; the tick loop drains and despawns it.
- **Full Circle** refunds MP from the Luopan's remaining HP and removes it.
- **Lasting Emanation** lowers the Luopan's HP drain.
- **Ecliptic Attrition** raises potency 25% and raises the drain.
- **Radial Arcana** removes the Luopan and restores party MP.
- **Collimated Fervor** and **Entrust** apply their exact client statuses.
- Test: all six are covered end-to-end.
- The remaining aura/Indi spell effects are still a follow-up; these JAs now manipulate a
  real Luopan state rather than being empty branches.

## Unreleased — ranged attack / Bounty Shot / Steal

- Added the C2S **Shoot** action (`0x01A` action `0x10`) and a shared `_ranged_shot` path:
  it reads the equipped ranged weapon and ammo, uses the ranged skill/damage, applies
  Ranged Accuracy/Attack, and resolves the hit through the combat engine.
- **Bounty Shot** now fires that ranged attack with +50 damage.
- Added **monster_steal_items** (migration 0158) with seeded Wild Rabbit/Tunnel Worm
  entries; **Steal** now picks a weighted item, adds it to the inventory and refreshes.
- Tests: Bounty Shot and Steal are covered end-to-end.
- Remaining real no-ops: **GEO 6** only.

## Unreleased — Stealth Shot / Flashy Shot

- **Stealth Shot** applies its Enmity -5 status.
- **Flashy Shot** applies Ranged Attack +10 and Enmity +50.
- Tests cover both.
- Remaining real no-ops: **9** — GEO 6, RNG Bounty Shot, THF Steal.

## Unreleased — Scavenge

- **Scavenge** now finds a level-appropriate ammunition item (Bronze/Bullet/Iron/Platinum)
  with a 75% success chance and adds it to the inventory.
- Test: the success path is covered end-to-end.
- Remaining real no-ops drop to **10**: GEO 6, RNG 3 (Stealth/Flashy/Bounty Shot) and
  THF Steal.

## Unreleased — smoke matrix reaches 11 real no-ops

- The smoke harness now classifies five menu/resource entries separately instead of as
  failures: Pet Commands, Phantom Roll, Quick Draw, Stratagems and Relinquish.
- Final matrix: **286 mechanic / 57 chat / 5 menu / 11 real no-ops**.
- The 11 real no-ops are exactly three missing subsystems:
  - **GEO (6)**: Full Circle, Lasting Emanation, Ecliptic Attrition, Collimated Fervor,
    Radial Arcana, Entrust.  The Indi-/Geo- spells currently have no `SpellEffect` and
    there is no bubble/aura propagation for the JAs to modify.
  - **RNG (4)**: Scavenge, Stealth Shot, Flashy Shot, Bounty Shot.  There is no
    ranged/thrown attack or ammo engine.
  - **THF (1)**: Steal.  The zone has no mob steal-item/loot table.
- No server code changed in this verification pass.

## Unreleased — Mantra / Sange / Steady Wing / Rayke / Tomahawk / Convergence

- **Mantra** applies the Max HP Boost status (+20% HPP).
- **Sange** applies its status with Ranged Accuracy +20; thrown-weapon Daken still needs the
  ranged engine.
- **Steady Wing** gives the Wyvern a Stoneskin shield for 300 seconds.
- **Rayke** applies the Rayke and Magic Evasion Down statuses to the target.
- **Tomahawk** marks the target with its client status.
- **Convergence** makes the next Blue Magic spell 50% stronger and +50 Magic Accuracy,
  and is consumed by that cast.
- Tests cover all six.
- Remeasured matrix: **287 mechanic / 56 chat / 16 no-ops**.

## Unreleased — PLD/RUN remaining statuses

- **Rampart** (PLD) now applies its 30-second damage-reduction status.
- **Majesty** (PLD) applies Cure Potency II +20 for 60 seconds.
- **Pflug**, **Valiance**, **Battuta** and **Liement** now apply their exact client
  statuses with defensive/evasion/damage-reduction modifiers (partial until the rune
  resistance/absorption model exists).
- Test: PLD and RUN statuses are covered together.
- Remeasured matrix: **279 mechanic / 57 chat / 23 no-ops**.

## Unreleased — all COR rolls

- Added the **17 missing Corsair rolls** with LandSandBoat's exact client status ids:
  Beast 318, Choral 319, Drachen 323, Evoker's 324, Corsair's 326, Puppet 327,
  Dancer's 328, Scholar's 329, Naturalist's 339, Runeist's 600, Courser's 332,
  Blitzer's 333, Tactician's 334, Allies' 335, Miser's 336, Companion's 337 and
  Avenger's 338.
- Evoker's/Refresh, Dancer's/Regen, Naturalist's/Enhancing duration, Runeist's/Magic
  Evasion, Allies'/Skillchain bonus, Miser's/Save TP and Avenger's/Counter carry stat
  modifiers.  Pet-only, movement, EXP and Conserve MP rolls are icon+message only until
  those subsystems exist.
- Test: eight representative missing rolls are covered by one COR test.
- Remeasured matrix: **274 mechanic / 56 chat / 29 no-ops**.

## Unreleased — Cascade / Feral Howl

- **Cascade** converts all TP into a Magic Damage bonus for the next spell
  (`TP / 10`) and is consumed by that cast.
- **Feral Howl** applies a 5-second terror/stun to the target.
- Tests: Cascade and Feral Howl are each covered.
- Smoke matrix after the harness fixes: 255 mechanic / 56 chat / 48 no-op; Cascade and
  Feral Howl take the live count to about 46.

## Unreleased — Diabolic Eye + smoke harness state

- **Diabolic Eye** gives dark magic +50 Magic Accuracy for 60 seconds.
- The smoke harness now damages the caster, poisons it, gives the mob enmity, spawns the
  correct job pet (beast/wyvern/avatar/automaton/luopan), lowers pet HP, sets automaton
  burden and compares HP/MP/TP.  That removes the false no-ops for Benediction, Convert,
  Repair, Spirit Link, Maintenance, Ventriloquy and Cooldown.

## Unreleased — Fly High / Overdrive / Astral Flow

- **Fly High** resets the jump recasts and pins them to 10 seconds for 30 seconds.
- **Overdrive** gives the automaton a 60-second 1.5x damage multiplier.
- **Astral Flow** doubles the next Blood Pact Rage damage.
- Tests: Fly High and Overdrive/Astral Flow are covered.
- Remaining DRG: Steady Wing, Ancient Circle.  Remaining SMN: Avatar's Favor,
  Astral Conduit.  Remaining PUP: Repair/Cooldown work only with a live automaton.

## Unreleased — Fealty / Spirit Bond

- **Fealty** nullifies the next tracked ailment that would land on the Paladin and is consumed.
- **Spirit Bond** shares half of incoming damage with the Wyvern for 60 seconds; the
  Wyvern can die from its share.
- Test: Fealty and Spirit Bond are covered together.
- Remaining PLD: Rampart, Majesty.  Remaining DRG: Steady Wing, Fly High, Ancient Circle.

## Unreleased — Dark Seal / Larceny

- **Dark Seal** now marks the next dark-magic spell with +100 Magic Accuracy and is
  consumed by that cast (including the finish-time resist recalculation).
- **Larceny** steals one non-ailment effect from the target and puts it on the Thief with
  its remaining duration.
- Tests: Dark Seal and Larceny are each covered.
- Remaining DRK: Diabolic Eye.  Remaining THF: Steal.

## Unreleased — Chivalry / Deep Breathing

- **Chivalry** converts all TP into MP with the retail
  `TP × 0.05 + TP × 0.0015 × MND` formula.
- **Deep Breathing** doubles the next Wyvern breath and is consumed by Smiting or
  Restoring Breath.
- Tests: Chivalry and Deep Breathing are covered together.
- Remaining PLD: Rampart, Majesty and Fealty still lack client status ids.
- Remaining DRG: Spirit Bond, Steady Wing, Fly High and Ancient Circle.

## Unreleased — smoke matrix + PUP/RDM cleanup

- Full smoke matrix regenerated: **65 no-ops** left (down from 116), with 230 mechanical
  and 64 chat-only results.  The largest remaining block is COR's 19, 17 of which lack
  client status ids.
- **Puppetmaster Maintenance** heals the automaton for half its maximum HP and clears its
  status effects; **Ventriloquy** transfers half the Puppetmaster's enmity to it.
- **Spontaneity** makes the next spell instant and is consumed.
- **Enmity Douse** halves the caster's enmity on the target.
- Tests: Spontaneity/Enmity Douse and the Puppetmaster additions are covered.

## Unreleased — COR audit

- **Crooked Cards** now adds +1 to the next Phantom Roll and is consumed.
- The elemental Quick Draw shots (Fire/Ice/Wind/Earth/Thunder/Water/Light/Dark Shot) were
  already implemented; **Quick Draw** itself is a self-targeted mode and remains a no-op.
- Seventeen Corsair rolls are still no-ops because `data/job_ability_status.json` has no
  client status ids for them; adding guessed ids would put wrong icons on the bar.
- Test: Fire Shot + Crooked Cards are covered together.

## Unreleased — RUN runes / PUP maneuvers

- **Rune Fencer**: Rune Enchantment, the eight elemental runes, Ward/Effusion stances and
  Lunge now have real state.  Lunge deals `100 + 100 × runes` damage and consumes the runes.
- **Puppetmaster**: Activate + the eight maneuvers, Deploy/Retrieve, Deus Ex Automata,
  Tactical Switch (TP swap) and Role Reversal (HP swap) now work.  Cooldown clears the
  shared maneuver recast.
- Tests: RUN and PUP are each covered by an end-to-end test.
- Remaining RUN: Pflug, Valiance, Gambit, Rayke, Battuta, Liement, One For All, Embolden,
  Elemental Sforzo, Odyllic Subterfuge and the rune-enhancement bonuses.
- Remaining PUP: Maintenance, Ventriloquy, Overdrive and the automaton frame/attachment
  model.

## Unreleased — SCH Libra / BLU audit

- **Libra** now reports the target's name, level and HP percentage.  The Stratagems
  ability remains the SCH charge/menu resource and still has no separate effect.
- **BLU** was audited: six of eight abilities already work.  **Convergence** and
  **Diffusion** need a Blue Magic cast-scoped spell engine, so they are still no-ops.
- Test: Libra is covered end-to-end.

## Unreleased — MNK core / RNG audit

- **Boost** makes the next main-hand hit deal 25% more damage and is consumed.
- **Chi Blast** deals MND-scaled damage to the target.
- **Formless Strikes** makes the next main-hand hit ignore defense.
- **RNG** was audited: ten of fourteen abilities already work; **Scavenge, Stealth Shot,
  Flashy Shot and Bounty Shot** still need the thrown/ranged/ammo subsystem.
- Test: Boost, Chi Blast and Formless Strikes are covered in one MNK test.

## Unreleased — DRK Consume Mana / NIN audit

- **Consume Mana** now spends all current MP and adds exactly that amount to the next
  main-hand hit, then clears the charge.  Previously it was a no-op.
- NIN was audited: six of seven abilities already work; **Sange** remains a no-op because
  the server has no thrown/ranged attack engine to enhance.
- Remaining DRK one-shot seals: **Dark Seal** and **Diabolic Eye** still need a cast-scoped
  dark-magic flag.
- Test: Consume Mana is covered end-to-end.

## Unreleased — SMN avatar commands

- **Assault** makes the avatar engage the current target; **Retreat** pulls it back.
- **Elemental Siphon** requires a live avatar and restores MP scaled by its level.
- **Mana Cede** spends 10% of the avatar's current HP and converts it to MP.
- **Apogee** empowers the next Blood Pact Rage (+300 damage) and is consumed.
- **Blood Pact Rage** now resolves the current target even though the client sends the
  ability as self-targeted; previously it printed only "You use Blood Pact Rage."
- Test: one end-to-end SMN test covers all of the above.
- Remaining SMN work: Astral Flow, Avatar's Favor and Astral Conduit are still icon-only.

## Unreleased — DRG jumps and breaths

- **Super Jump, Spirit Jump, Soul Jump and Dragon Breaker** now deal their jump damage;
  Super Jump halves the Dragoon's enmity, Soul Jump restores 100 TP and Dragon Breaker
  applies Attack Down.
- **Angon** deals damage and applies Defense Down.
- **Smiting Breath** deals Wyvern breath damage and **Restoring Breath** heals the party,
  both gated on a live Wyvern.
- Tests: one end-to-end DRG test exercises the five jumps, Angon and both breaths.
- Remaining DRG work: Spirit Bond, Deep Breathing, Steady Wing, Fly High and Ancient Circle.

## Unreleased — THF core abilities

- **Perfect Dodge** negates physical auto-attacks for 30 seconds.
- **Flee** applies the movement-speed effect for 30 seconds; **Hide** applies invisibility.
- **Assassin's Charge** forces the next melee hit to be a critical and is consumed.
- **Accomplice** transfers 25% of the THF's enmity to a party member;
  **Collaborator** transfers 25% of that party member's enmity back to the THF.
- **Feint** applies Evasion Down on the next landed hit; **Bully** applies Evasion Down
  directly to the target.
- Tests: six new THF regression tests pass.
- Remaining THF work: Steal, Despoil and Larceny need the mob-item/buff-stealing model.

## Unreleased — DNC audit and Flourish III

- **Dancer now has 31 regression tests** covering the full kit: waltzes, steps, sambas,
  jigs, Flourishes I-III, Aspir Samba, Divine Waltz, Presto, No Foot Rise, Trance,
  Contradance, Saber/Fan Dance and the menu headers.
- **Flourish III is consumed by the next weapon skill**: Climactic guarantees a critical,
  Striking adds one hit and Ternary adds two hits.
- **Grand Pas** still only puts up its icon; its retail one-hour effect is not modelled.
- Remaining DNC nuance: exact step/flourish job-point values and the full Grand Pas effect.

## Unreleased — GEO Luopan abilities

- **Life Cycle** now distributes a quarter of the GEO's current HP to the Luopan (with the
  job-point bonus).  Since geomancy spells do not summon a Luopan yet, the first use with no
  pet still spawns one so the job is playable.
- **Mending Halation** consumes the Luopan, heals party members within 10 yalms for the
  retail `7 x Luopan level + 1`, and removes the pet.
- **Concentric Pulse** consumes the Luopan and deals its current HP to the target (capped
  at the target's remaining HP).
- Test: the three Luopan abilities are covered end-to-end.
- Remaining GEO work: the actual Indi-/Geo- geomancy bubbles and their modifiers
  (Bolster, Full Circle, Lasting Emanation, Ecliptic Attrition, Collimated Fervor, Blaze of
  Glory, Dematerialize, Radial Arcana, Entrust, Theurgic Focus, Widened Compass).  These
  modify a geomancy system the zone server does not have yet.

## Unreleased — RDM/BLM core mechanics

- **Chainspell** now makes every spell cast instantly for its 30-second duration.
- **Manafont** makes every spell MP-free for its 30-second duration.
- **Convert** is regression-tested: it swaps current HP and MP and then applies the RDM
  job-point HP bonus.
- **Composure** carries its +50% Enhancing Magic duration modifier; its existing En-spell
  damage bonus remains.
- Tests: four RDM/BLM regression tests pass.
- Remaining RDM/BLM work: Elemental Seal, Saboteur, Spontaneity, Stymie, Manawall,
  Manawell, Cascade, Enmity Douse and Subtle Sorcery; several are one-shot next-spell
  effects that need a cast-scoped flag rather than a passive icon.

## Unreleased — PLD/WHM core mechanics

- **Benediction** now heals the whole party to full, removes the 25 tracked ailments and
  restores the job-point MP bonus; it is no longer a self-only HP/MP refill.
- **Martyr and Devotion** accept a party target, sacrifice 25% of the White Mage's current
  HP, and restore twice that as HP (Martyr) or the same amount as MP (Devotion).
- **Shield Bash** now rolls a 70% stun in addition to its damage.
- **Invincible** negates physical auto-attacks for its 30-second duration.
- **Sentinel** carries its +25% Defense modifier for 30 seconds.
- Tests: five new PLD/WHM regression tests, all passing.
- Remaining PLD/WHM work: Divine Seal, the Afflatus stances, Divine Caress,
  Sacrosanctity, Asylum, Cover, Rampart, Majesty, Fealty, Chivalry, Divine Emblem,
  Sepulcher, Palisade, Intervene and Holy Circle; several need the family/cover/status
  subsystems the engine still lacks.

## Unreleased — WAR core mechanics

- **Berserk / Defender / Aggressor now change the actual stats**, not just the icon:
  Berserk +35% Attack/-25% Defense at 99, Defender +35% Defense/-25% Attack, Aggressor
  +25 Accuracy/-25 Evasion.  `AbilityEffect` gained a `mods` field so any ability icon can
  carry its persistent modifiers.
- **Warcry and Blood Rage** are party buffs in a 13.9-yalm radius, overwrite each other,
  and use the retail Warcry level formula and Blood Rage's +20% critical rate.
- **Mighty Strikes** forces critical melee hits; **Retaliation** counterattacks at 40% plus
  job points; **Restraint** builds up to +30% weapon-skill damage from landed main-hand
  hits and resets on the next weapon skill; **Brazen Rush** grants +100 Double Attack for
  30 seconds.
- **Warrior's Charge** already landed in the previous pass.
- Tests: five WAR regression tests, all passing; `test_sam` and `test_effects` also pass.
- Remaining WAR gap: **Tomahawk** needs the ammo check plus the special-resistance model,
  which the engine does not have yet.

## Unreleased — SAM core mechanics covered

- **Meikyo Shisui, Sekkanoki and Hagakure are now regression-tested**: Meikyo grants 3000 TP
  and spends 1000 per weapon skill, Sekkanoki caps the next skill at 1000, and Hagakure carries
  the next skill's +1000 TP Bonus (Save TP 400 remains on its existing path).
- **Warding Circle, Hamanoha and Yaegasumi are the remaining SAM engine dependencies.**
  Warding Circle/Hamanoha need a demon-family model (the monster tables have no family column);
  Yaegasumi needs the special-attack evade/zero-damage hook and its WSD stack.  Their icons and
  timers already exist, but the smoke test only sees the icon, so they are not claimed as done.
- Tests: `server/tests/test_sam.py` (18 SAM tests, all passing).

## Unreleased — All-job ability audit and smoke tests

- **Every job ability is now classified.** `tools/job_ability_audit.py` reads all 359
  `job_abilities` rows and writes `docs/job-ability-status.md`, splitting them into explicit
  handlers, status-effect rows, job-point rows and inert rows, per job.
- **Every job ability is now smoke-tested in a live session.** `tools/job_ability_smoke.py`
  calls each one on a level-99 job against a mob (and with a pet for pet jobs), records
  whether the session/pet/target changed, only a status icon changed, only chat changed, or
  nothing happened at all.  The generated report is `docs/job-ability-smoke.md`.
- **Warrior's Charge (149) now works**: it sets a 60-second next-weapon-skill state and adds
  +1000 TP Bonus to that skill; Sekkanoki still caps the skill at 1000.  Test in
  `test_world.py`.
- The reports are the starting point for the per-job retail deep dives; the inert/chat-only
  rows are the leads, not final verdicts.

## Unreleased — BST Tame, Gauge and Leave

- **Tame now works.** It refuses while a pet is out, refuses when another player has active
  enmity, can miss, and either disengages a mob that only the Beastmaster has claimed or marks
  an unclaimed mob for the next Charm (+10 percentage points).  The chance is 75% plus the
  equipped Tame success rate.
- **Gauge now reports** the target's HP percentage and a charmability read.
- **Leave now releases the pet.**  Fight/Sic/Ready, Heel, Stay, Call Beast and Bestial Loyalty
  no longer also print the generic "You use ..." line.
- **Totemic Helm +4's missing Tame success rate** (+31, mod 304) is restored by migration 0157.
- Still missing from the BST kit: Familiar, Snarl and Feral Howl; Spur and Unleash put up
  their icons but do not change the pet's stats or TP moves; Reward is a flat 300 HP pet heal;
  Ready/Sic do not resolve pet TP-move damage yet.

## Unreleased — A pinned weaponset comes back after a locked action

- **A manually worn, pinned main/sub is now restored after a locked JA or song.** The launcher's
  **Wear** / **Wear & lock** used to forget the phase engine's whole worn table, and a pinned
  weaponset lives outside the state sets.  When KI's Diamond Aspis temporarily replaced the sub,
  the override knew the original head/body but not the pinned Ikenga, so the Aspis stayed on.
  `equip_set` now reports each manually worn piece's exact bag/slot to the engine
  (`xi.phase.remember`), and the locked-action restore puts the weapon back.  Re-wear the
  weaponset once after updating to seed the table.
- Test: `tests/phase_lock_override_test.sh` covers a remembered pinned sub that is not in the
  state set, swapped to the KI shield and restored.

## Unreleased — Recast clocks read as minutes and seconds

- **The HUD cooldown clock and its tooltip no longer print raw seconds.** A 300 s recast is
  **5m**, 299 s is **4m59s**, and 45 s is **45s**.  The clock rounds up, so it never flashes
  `4m60s`; the ability and spell hovers use the same label.

## Unreleased — Locked gear yields to a job ability, song or weaponskill

- **A full gear lock or a pinned slot no longer blocks an action's own precast/midcast set.** The
  phase engine now saves the pieces that were on, temporarily clears the full lock and the
  per-slot pins, builds and sends the action's pre/mid gear, then restores the original pieces
  and the original lock state when the action's result arrives (or after the existing stale
  timeout). This covers job abilities (including Killer Instinct), spells and bard songs, and
  weaponskills; `/attack` and the automatic idle/movement states still obey the lock. A pinned
  main/sub can now stay pinned through TP and still swap for a JA or song, and the full **Lock**
  keeps the set on outside actions.
- Tests: `tests/phase_lock_override_test.sh` covers full lock and slot pins in the addon harness;
  `phase_precache_test.sh` and `phase_state_test.sh` still pass.

## Unreleased — Killer Instinct gets its status icon and real bonuses

- **Killer Instinct was a no-op apart from the use message.** Ability 162 had no
  `effects.ABILITY_EFFECTS` entry and no `job_points.ability_effect()` row, so it played
  its animation and printed "uses Killer Instinct" without putting status 349 on the bar.
  It now applies the retail icon and duration (180 s, plus 10 s per merit rank past the
  first), gives the caster and the whole party the effect, and adds +15% physical damage
  dealt and a -15% `DMG` modifier. The damage bonus is read inside
  `World.player_attack`, so it applies to every auto-attack and every swing of a weapon
  skill; the damage-taken side is a normal combat modifier and appears in the stat report.
- **Diamond Aspis and the Ankusa/Mst. Helm augment now extend the duration.** At 5/5
  merits the base is 220 s; the helm augment adds 4 s per rank (+20 s), and the Diamond
  Aspis's "standard abilities used on self +25%" takes the caster to **300 s (5:00)**,
  matching the recast.
- **Custom BST change: the whole party gets the full Killer Instinct.** Every party
  member in the zone gets the same **300 s** duration and the full +15% damage dealt /
  -15% damage taken effect, with no 7.9-yalm range check and no reduced party copy.
  This is deliberately different from retail, where only the caster gets the Diamond
  Aspis extension and the party copy is shorter.
- **Family matching is still pending.** `monster_templates` has no family column, so the
  +15%/-15% currently applies to every target rather than only the family matching the
  pet's killer correlation. The icon, merit/helm duration, Diamond Aspis extension and
  recast are retail; the whole-party duration and range are the custom BST change.
- Tests: `test_world.py` (status icon, rank-5 duration with the helm and Aspis, `DMG`
  modifier, +15% hit). Docs: `docs/combat-damage.md`.

## Unreleased — Items tab: buy ninja tools and consumables by the piece or the stack

- **The Data page has a general-item store beside the Armory.** The new **Items** tab reads
  migration 0156's non-equipment catalogue (4,447 rows): ninja tools and toolbags, all 97 Call
  Beast jugs, pet food, potions, food and drink, ingredients, crafting materials, crystals, magic
  scrolls, ammunition, automaton attachments and furnishings. Search is scoped to that catalogue,
  ignores apostrophes (`nobles bed` finds **Noble's Bed**), and category chips browse a shelf.
- **Every row can be bought as one unit or as a full stack.** The detail card shows the unit
  price, stack size and the held count across bags, storage and the locker, with **Buy 1** and
  **Buy stack (N)** buttons that charge `unit price × quantity`. Shihei stacks to 99, jugs to 12;
  Rare items remain one-per-character and are refused before the wallet is charged.
- **Server/launcher plumbing.** `GET /characters/{id}/items/search` takes `scope=items` and
  `category`, `POST /characters/{id}/items` buys a general item, and the snapshot gains
  `item_categories`. The Tauri `search_armory` command forwards the new scope/category, and the
  Items tab is remembered with the other Data tabs. `char_purchases` is shared by both shops.
- Tests: `test_api.py` (catalogue, stack purchase, jug/pet shelves, rare refusal, scope
  separation and insufficient gil), `test_service.py` (apostrophe search, shelf filtering and
  category order), `npm run check`, `cargo check`. Docs: `docs/launcher.md`,
  `docs/database.md`.

## Unreleased — Gear swaps wait out the zone load and coalesce per slot

- **A plan push no longer cancels the zone/job settle and wears the outfit on top of the
  client's own zone-in equip.** `xi_phase_set` kept the settle flag when it published a new
  table, and `control.lua` now skips the immediate `xi.phase.apply()` while
  `xi.phase.status().settling` is true; the watch loop sends the state set through
  `xi.phase.pending()` after `PHASE_SETTLE_MS`. This is the window in which the client log
  showed `out of a Mog House` followed by a large wear batch and the `FATAL at 1015d7f0`.
- **Queued `0x050`s for one equipment slot collapse to the newest piece.** A state set queued
  while the previous set was still pending used to leave two changes for the same slot in one
  buffer; `queue_equip()` in `host/addons/hooks.c` replaces the pending packet instead. The
  before/after behaviour is `tests/gear_queue_test.sh`.
- **The client log names the gear batch behind a crash.** `[gear] plan`, `[gear] wear` and
  `[gear] action` lines report plans, state sets of six or more pieces and action sets of six or
  more pieces, so the next `FATAL` or freeze has the batch that preceded it.
- Tests: `tests/gear_queue_test.sh` (new), `tests/phase_state_test.sh` (a plan pushed during a
  settle keeps it).  Docs: `docs/development.md` (where the client, server and watchdog logs
  are).

## Unreleased — Trust nameplates and casters

- **Alter egos have their names back.** The `0x00E` spawn wrote a spawnable's name at body
  `0x34` (packet `0x38`), four bytes past the field the client reads (packet `0x34`, body
  `0x30`).  Those four bytes were zeros, so the client filed every Trust under an empty
  name: no nameplate above the alter ego, no entry in the control port's entity list (it
  skips empty names), and a chat cast line reduced to `casts Protect V.` with no caster.
  The spawnable name now goes at `0x30`, matching LandSandBoat's `entity_update.cpp`; the
  static NPC path (marker `0x34`, name `0x35`) is unchanged.  Tests: `test_packets` and
  `test_pets` pin the name bytes and the model/name boundary.  Restart the server for new
  spawns to take the new name.
- **The party page still carries the Trust rows.** The names in `0x0DD` were already
  present; the missing name was only the entity table.  The chat line and the nameplate
  both read the entity name, so the spawn fix covers both.

## Unreleased — the skillchain clock and a longer window

- **The skillchain window is one second longer.** The server now opens at 11 s, then
  10/9/8/7/6 s as links form; the 3 s action lockout and the one-second shrink per link
  are unchanged.  The Fusion-to-Light window is 10 s (7 s to close after the lockout)
  instead of 9 s (6 s), and the 4th step gets 9 s (6 s after the lockout).  This is one
  second above AutoSkillchains' 10/9/8/7/6 reference — a deliberate allowance for the
  TP cycles on this server.  Diamond Aspis now keeps the full 11 s.
- **The Battle HUD's SC clock no longer starts a new chain at the old chain's step.** It
  advanced the step whenever the next weapon skill landed within a flat 12 s of the last
  one, but the server resets to a fresh opener as soon as the previous window closes (11 s
  for the opener, 1 s less per link, plus the 0.5 s status-tick grace).  A weapon skill
  fired 11 s after a three-link chain was counted as step 4 — an 8 s window — while the
  server opened an 11 s opener; every later link then showed about 3 s less than the
  server, which looked like "less than 3 seconds to land Light".  The clock now continues
  only inside the previous step's own window plus the server's grace, and a weapon skill
  inside the 3 s action lockout is a fresh opener on both sides.

## Unreleased — Beastmaster jug picker and pet commands

- **Call Beast now summons the pet the jug names, and Bestial Loyalty works.** The zone
  server read neither the ammo slot nor the jug's pet id: every Call Beast spawned a Tiger
  and Bestial Loyalty only played its animation.  `data/jug_pets.json` (generated by
  `tools/gen_jug_pets.py` from LandSandBoat's `item_weapon.subskill` -> `pet_list` ->
  `mob_pools`/`pet_skills`) maps all 97 Fanxi jugs to the pet name, look and level.  Call
  Beast spends one jug; Bestial Loyalty keeps it; a missing jug is reported before the
  spawn.
- **The HUD's Call Beast and Bestial Loyalty tiles open a jug picker.** It lists the jugs
  actually in the character's equippable bags, with the pet each calls and the stack count, and
  refreshes while open so a spent jug disappears.  Picking one wears the jug first (the
  client validates the ammo before it sends the ability), waits for the client's equipment
  table to show it, then uses the ability.  The phase engine's one-shot precast (`xi.phase.precache`) re-asserts the jug in the held
  0x01A and puts the normal state set back when the action resolves; with the engine off
  the previous ammo is restored afterwards.
- **Pet commands opens a dialog with only the called jug's commands and Ready moves.**
  The old HUD skipped every `PetCommand`-type ability, so the only entry was the
  no-op "Pet commands" job ability.  The dialog shows the current job pair's pet commands,
  hides Leave and Sic for a jug pet, and adds a Ready section with that jug's own moves
  from the same catalogue.  Charmed pets get Leave and no jug moves.
- Tests: `test_jugpets.py` (catalogue, Tiger mapping, Lua/JSON parity), the Bestial
  Loyalty/Call Beast ammo tests in `test_world.py`, `tests/phase_precache_test.sh` for the
  one-shot precast, and the Lua compile check.  Docs: `docs/pets.md`, `docs/world.md`.

## Unreleased — Trust HP/MP follow race, job and level

- **Trust HP/MP are no longer a flat placeholder.** `trust_from_row()` and the level-up
  tick used `level * 30 + 200` HP and `level * 4` MP for every alter ego, so a level-99
  party showed 3170 HP / 396 MP on a Tarutaru Black Mage and a Hume White Mage alike.
  `game/trust_stats.py` now reads the same race/job/subjob base tables as the player
  sheet, with the Trust's half-level subjob and a 75% MP bonus (retail trusts run about
  31% above a player's base racial MP and commonly carry further MP+ traits).  A 99
  Shantotto is 1111 HP / 1779 MP; Ygnas is 1210 / 1555; Cornelia 1463 / 1555.
- **The species column arrives in migration 0151.** `trusts` already had the look and
  job data but no way to know whether the alter ego was Hume, Tarutaru, Mithra, Elvaan
  or Galka.  `tools/import_lsb_trusts.py` now also writes
  `0151_trust_species.sql` from LandSandBoat's `mob_pools.speciesid`; anything that is
  not a player race keeps the Hume fallback.
- Tests: `test_trust_stats.py` (species mapping, Shantotto/Ygnas/Joachim, no-MP jobs,
  level clamp), plus the Trust spawn assertion in `test_world.py`.  Docs:
  `docs/world.md`, `docs/database.md`.

## Unreleased — Beastmaster weapon skills: Spalirisos stats, precast and the plan push

- **Spalirisos had no item-level skill or stat block.** The hand-curated Beastmaster
  grant wrote the Prime axe with `item_weapon.ilvl_skill = 0` and no `item_mods`, so a
  99 BST had Axe skill 424 instead of 701 and lost its STR+35 / DEX+35 / CHR+35 /
  Accuracy+35 / Magic Accuracy+35 / Critical hit rate +15%.  That is the bulk of the
  low Blitz damage: migration 0155 adds the iLvl 119 III block, and Ikenga's Axe and
  Agwu's Axe get their skill 255 and stat blocks.  Blitz keeps its documented first-hit-only
  fTP (the 3,000-TP 12.5 applies to the opening hit; the later native hits use 1.0).
- **Main/sub were pinned out of every weaponskill set.** The live client reported
  `lockedSlots: [0, 1]`, so the phase engine filtered Spalirisos/Ikenga out of the
  `sets.WS.Decimation`, `sets.WS.Mistral Axe`, etc. cards: armour swapped, the weapon did
  not.  The slots are unlocked, the plan is rebuilt from the current `gearswap/BST.lua`, and
  the Weaponset hint now says a main/sub pin also blocks `sets.WS.*` weapon changes.
- **A weapon skill uses the gear the phase engine put on in that packet batch.** The
  phase engine can inject the precast 0x050s and the action into one datagram; the action
  handler now flushes that equipment before `stat_sheet` and the Prime "Adds weapon
  skill" lookup see it.  Previously the damage roll could use the previous outfit's
  weapon while the client drew the new one.
- **Editing a GearSwap set re-pushes the phase plan.** The plan was rebuilt only when
  the library *path* or job changed, so main/sub weapons added to `sets.WS.*` stayed in
  the file but not in the client; only the armour rows swapped.  The effect now depends
  on the library object as well.
- Tests: `test_service.py` (Spalirisos skill/stats), `test_weapon_skills.py` (Blitz
  first-hit fTP and same-batch gear), `npm run check`.  Docs:
  `docs/prime-weapon-skills.md`.

## Unreleased — Farsha and the other one-handed axes can fill the off hand

- **Farsha was missing from the launcher's Sub picker.** The 119 III Beastmaster axes
  (and the Ninja 119 III katanas) were inserted by the hand-curated job grants with
  `slot_mask = 1` (main hand only).  Migration 0149 repairs every one-handed axe/katana
  row whose mask lacks the Sub bit; the launcher's picker and the server's equip check
  both read that mask.  Farsha (21752) now has `slot_mask = 3`, is BST-legal and is
  offered in Sub.
- **The set editor re-reads the bags whenever the item picker opens.** The page used to
  fetch the bag list once per character and keep it, so a piece moved, granted or
  equipped after the page loaded (or an item-data fix like the one above) stayed
  invisible until a relaunch.
- Test: `test_service.py` asserts no one-handed axe/katana row is main-only and that
  Farsha still carries both the BST job bit and level 99.

## Unreleased — Dancer menu headers removed and monsters use TP moves

- **Dancer's category headers are no longer abilities.** `Jigs`, `Steps`, `Waltzes`,
  `Sambas` and `Flourishes I`/`II`/`III` are menu headings in retail's ability table with
  no animation and no effect.  The flat Abilities window showed them as broken buttons —
  clicking `Jigs` printed "You use Jigs" and played the default animation instead of a
  real jig.  Migration 0147 deletes those seven rows from `job_abilities`, so 0x0AC no
  longer advertises them; real waltzes, sambas, steps, jigs and flourishes keep their
  levels, recasts and animations.  The HUD also filters the seven ids for a client whose
  saved command list was built before the restart.
- **Monsters have TP and use their family's TP moves.** Migration 0148 imports
  LandSandBoat's `mob_skills` (2,691 moves) and `mob_skill_lists` and gives every
  `monster_templates` row its `skill_list_id`.  A monster gains TP on its own landed
  swings (the mob TP curve) and when a player hits it (+30, dAGI and Subtle Blow);
  it readies a move at 1000–3000 TP (always at 3000 or below 25% HP), spends the bar,
  and sends the 0x028 SkillStart/Finish pair with the move's animation.  The
  self-/target-centred AoE shapes, self-target moves and a name-based sleep/poison/
  paralysis/silence/blind/petrify/bind/weight/slow/stun/debuff map are wired; cone
  shapes and per-script damage/effects are still approximated.  See
  `docs/combat-coverage.md`.
- Tests: `test_dancer.py` checks the headers are gone from `job_ability_ids` and 0x0AC;
  `test_mob_skills.py` covers TP gain, the full-bar action, AoE targeting and the
  no-skill-list fallback.  `tools/import_lsb_mobskills.py` regenerates migration 0148.

## Unreleased — Magic Bag HUD and the 30-day Recycle Bin

- **A new in-game Magic Bag HUD (`//bags`, `//magicbag`).** It lists every client bag and, when
  opened from the Control room, the server-side slips/locker —
  Inventory, Mog Safe, Safe 2, Storage, Mog Locker, Satchel, Sack, Case, Wardrobes 1–8 and the
  Recycle Bin — with item icons, a search box, bag filter, sort order, single-row highlight
  selection, per-row **Move**, compact **Recycle** and **Pull** buttons, select-all and a
  **Recycle selected** action. Equipping stays with GearSwap; the HUD no longer has an Equip
  button. The window is a normal draggable HUD window and is toggled with
  `//bags [on|off|toggle]`.
- **Dropping is now the 30-day Recycle Bin, not destruction.** `0x028` moves the stack to
  container 17, stamps `char_inventory.dropped_at` (migration 146), and the client sees the
  Recycle Bin row. Expired rows are purged on zone-in. `//recycle` lists the bin,
  `//recycle restore <slot> [count]` brings an item back to the inventory, and
  `//recycle drop <bag> <slot> [count]` is the HUD's recycle path. A recycled item cannot be
  equipped or used and cannot be moved into another bag until it is restored.
- **Control room switch.** The per-character HUD strip now has a **Magic Bag** toggle beside Show
  party info; it sends `show_inventory` through the same `hud` payload and is saved with the other
  window switches.
- **Move opens a destination dialog**, not the old one-target combo: every client bag plus
  **Magic Bag (9999)**. Visible destinations use `//item move <bag> <slot> <to-bag> [count]`;
  the Magic Bag uses `//item store locker <bag> <slot> [count]`. Recycle confirms rare/ex rows
  (or everything when the HUD only has the client fallback list), and a compact `X` button with
  a tooltip replaces the cut-off Recycle label.
- **The Magic Bag shows the whole collection.** The Control room's Magic Bag switch asks the
  server for `/characters/<id>/magicbag` — every visible bag row, the Storage Slips, the
  9,999 `char_locker`, and the Armory purchase history as **Claim Storage** — and pushes the
  merged list to the HUD in the same `hud` payload. The default filter is **All bags**, so the
  first open shows every row. Rows
  carry names, quantities, rare/ex flags, augment extdata and item ids, so the HUD draws the
  real item icon and can **Pull** a slip/locker stack with
  `//item pull <slip|locker> <item-id> [extra-hex] [count]`. Opening `//bags` without the
  launcher still falls back to the 18 client bags.
- **Double-click opens a full item card.** The card reads the client's own item name and
  description, every decoded augment line, and the copy's Path/Rank/RP from the 24-byte bundle
  block, so two Ambuscade capes with different augments are distinguishable before choosing a
  row action. It is modal; **Close** (or the title-bar X) returns to the table.
- **Bag and action columns no longer overlap.** The bag label starts at a fixed x and is clipped
  to its own column, and the Pull/Move/Restore buttons start farther right. Previously
  **Magic Bag (slip)** ran underneath the blue **Pull** button, which made the bag label and the
  button text jumble together.
- **Not yet native:** the HUD is an ImGui window, not a 19th native inventory menu entry. The
  native menu uses the client's 18 fixed containers; the next step is either a client-side
  string/menu patch (Magic Bag as a visible 80-slot window) or a true 19th-container patch.

## Unreleased — job changes clear buffs, reset TP and respect events and instances

- **A job change strips the buff layer.** `//job` and the Moogles' Change Job menu now remove
  every status effect and food, keeping only the regional conquest buffs (Signet, Sanction,
  Sigil, Ionis). The kept effects keep their timers and power state.
- **TP is always reset to 0**, in a city and in the field alike, and the refreshed party row
  reports the empty bar.
- **HP/MP refill only where a job change is a rest.** A city, town or Mog House sets both bars
  to the new job/gear maxima; a field, dungeon or instance only recomputes the maxima and leaves
  the current HP/MP alone. Auto-equip runs first, so the refill fills the actual new maxima.
- **A job change is refused during an event, a fight or a K.O.**, and in the Dynamis instances
  including Dynamis - Divergence (zones 294-297). The self form answers `You cannot change jobs
  during an event.`, `You cannot change jobs while in a fight.`, `You cannot change jobs while
  knocked out.` or `You cannot change jobs in this area.`; the box form reports the target's state
  by name. The check runs before any bag move, so a refused change leaves the outfit and storage
  untouched.
- Tests: `test_job_command.py` covers the conquest-only keep list, TP in both zone classes, the
  city/field vitals split, event/fight/mob-claim refusals, Dynamis-D, the remote form and the
  Moogle menu. Docs: `docs/world.md`.

## Unreleased — Master chains, Trusts in the party page and the skillchain close grace

- **Exemplar Points now chain.** A level-99 kill arms a Master chain window (60 s at
  chain #0, shortening to the 30 s floor at chain #25 — see the entry above);
  each qualifying kill inside it is chain #1, #2, … and pays **+2%** Exemplar Points per
  link (capped at chain #50 / +100%). The client gets message **810** ("Master chain #!
  gains # exemplar points") while the chain is running and 809 on the first kill, with
  the chain number in the packet's second parameter. `game/chain.py` holds the counter;
  `World.kill_mob` applies it after the BG-wiki base amount.
- **Trusts appear in the party menu.** `party_packets()` now injects each active alter
  ego as a `0x0C8` entry plus a `0x0DD` row after its owner, exactly as LandSandBoat
  appends the leader's Trusts; a solo player with Trusts also gets the one-player
  synthetic page and a non-zero `0x0E1` group id. `sync_parties()` sends a `0x0DF`
  whenever a Trust's HP/MP/TP changes so the party bars follow it, and summoning or
  releasing one re-sends the roster.
- **Skillchain timing follows AutoSkillchains.** The normal window is the reference
  `delay 3 + 8 − step` (10/9/8/7 s); the server now accepts a close up to **0.5 s**
  after the boundary, which is the status-effect container's tick. A close at exactly
  9.0 s (the first link) or 8.0 s (the second) therefore lands instead of opening a new
  chain. **Diamond Aspis** (`26488`, closing actor's sub slot) is the exception: the
  next window stays at **10 s** at every step.
- Tests: `test_chain.py`, `test_skillchain.py` (grace + Diamond), `test_party.py`
  (solo/party Trust rows, `0x0DF` vitals, solo group id) and the new `test_world` case
  for Master chain #1. Docs: `docs/skillchains.md`, `docs/battle.md`, `docs/world.md`.

## Unreleased — job-aware storage: only the set you are wearing is out

- **The 9,999 limit now counts storage slots, not units.** A 99-item Call Beast jug stack is
  one slot, as it would be in a client storage bag. Counting quantities made the seeded 97 jug
  types consume ~9,600 of the 9,999 capacity, so the locker read `9999/9999` while it held only
  354 entries and left 98 JSE items in the bags. `//locker`, `//storage` and the organizer now
  report slots, and the same sweep stores all of them.
- **`//storage organize` makes the bags match the current job.** Everything the job cannot
  equip leaves every permanent bag: a Storage Slip where the item has one, the hidden
  9,999-slot locker where it does not (the Ambuscade JSE capes, relic/mythic/empyrean weapons,
  job accessories). Everything the job can equip comes back into the Mog Wardrobes in
  equip-slot order, then the inventory, and the job's loose inventory/Safe gear is tidied into
  the wardrobes. `//storage store all` is the store half on its own. The client's 80-slot
  Storage container is not used, so the 9,999 locker limit is the real one.
- **Wardrobe updates reopen the container first.** A Mog Wardrobe is only filled from `0x020`
  rows while its state-0 `0x01D` load window is open. The organizer sent the rows without the
  marker, so after a job change the equipment window kept the previous wardrobe's list — it
  could show capes where the body slot should be, or an empty wardrobe. Affected wardrobes now
  get the state-0 marker and their full current contents before the final all-bag sync.
- **`//job` now runs that organizer.** It stores every other job's gear, not just the previous
  job's slip pieces, and pulls the new job's full set -- capes included -- instead of only the
  slips and the job's capes. The final auto-equip reads the wardrobes the organizer just filled,
  so a job change leaves one job's gear out and every other job in storage.
- **No-slip gear goes to the locker instead of being named and left behind.**
  `//storage store <job>` still sweeps that job's exclusive gear, but now a Kikoku, Ninja Nodowa
  or job cape lands in the 9,999 locker rather than staying in the bags. A slip item with a
  non-empty augment block also goes to the locker, because `char_storage` has no `extra` column;
  the 24-byte block survives.
- **New `//storage list [job|all]`**, and `//storage` with no verb now reports both stores
  (`N on slips, M in the 9999 locker`) plus how much of the current job is waiting. Moves are
  one transaction each: the destination row is written before the source row is deleted.
- `//storage grab <job>` pulls that job's own gear into the wardrobes; `//storage grab all`
  keeps the old behaviour and empties both stores. Tab completion gained `organize` and `list`.
- Tests: `test_world` covers organize, `store all`, the locker fallback, cape augments through
  the organizer and the new `//job` sweep; `test_job_command` covers the box form and
  `chat_complete_test` the two new actions.

## Unreleased — the item menu's Drop works

- **Dropping an item now deletes it.** The client sends `C2S 0x028` (`ItemNum`, `Category`,
  `ItemIndex`) when the player picks **Drop**, and the zone had no case for it: 0x028 was only
  the battle-action packet the server sends, so the first attempt was logged once as an unknown
  packet and every later one was ignored. The server now removes the requested count from the
  named slot, keeps the rest of a partial stack, and repaints the slot with a `0x020` (item id
  `0` when it emptied) plus the usual all-bag `0x01D`, as a move or a use does.
- **Gil and worn copies are refused** with a chat line. Gil is item `65535` in container `0`,
  slot `0`; deleting the bag row an equip entry points at would leave the character wearing gear
  the server no longer has, so the item has to be taken off first.
- The request bypasses the sync gate like the other menu requests (`0x037`, `0x050`, `0x00DD`),
  because the client can send it with sync `0`.
- `docs/protocol.md` lists the packet and its reply; `server/tests/test_item_drop.py` covers a
  full drop, a partial stack, an over-count, gil, worn gear, a wardrobe slot, an empty slot and
  the sync-0 dispatch.

## Unreleased — Data page tabs and a paged Armory

- **The Data page is split into four tabs.** **Overview** keeps merits, job points, Mastery
  Rank, gil, Home Points, currencies, key items and mounts; **Progression** holds ranks and
  fame, jobs and Master Levels, skills, Trusts, augment RP paths and Oboro weapons;
  **Augments** holds the Ambuscade cape editor, Nolan mezzotints, Oseem glyptics, Skirmish,
  Moonshade and Magian trials; **Armory** holds the item search and purchase history. The
  selected tab is remembered, and the tab strip supports arrow/Home/End keys.
- **The Armory purchase history is paginated.** It defaults to 20 rows per page; the
  **Rows per page** picker offers 10, 20, 50 or 100 and stores the choice for the next visit.
  The pager is a reusable `TablePager` with a `useTablePagination` hook (one storage key per
  table) so another table can opt in without duplicating the state.
- `docs/launcher.md` describes the four tabs and the persisted page size.

## Unreleased — the phase plan holds every set

- **A plan with more than 96 sets no longer loses its state sets.** The host's set table was
  capped at 96 while the control addon adds the state sets (engaged, town, field, movement,
  kiting, resting, idle focus) after every per-WS/JA/spell set. A fully configured Bard library
  builds 102, so `idle.dt` (field), `idle.movement`, the focus sets and the forced states fell
  off the end: in a field zone the engine reported `idle.field` but wore `idle.town`, movement
  never swapped, and the DT/PDT/MDT focus buttons did nothing. The table is now 256 sets, and
  `xi.phase.set` answers with the count it kept so a plan that still does not fit is visible
  instead of silently short (`phase.sets` in the launcher is that count).
- **The Weaponskills card describes the real precedence.** A card wins, then the library's
  `sets.WS.<name>`; the default WS set (then `precast.WS`) is only the fallback for a WS the
  library has no set for. The card hint and `docs/control-panel.md` had the default ahead of the
  library set.
- Tests: `tests/phase_state_test.txt` pushes a 120-set plan and checks the field set survives,
  and a 300-set plan and checks the table reports the 256 it kept.

## Unreleased — Trial of the Magians on the Data page

- **A new Magian Moogle card runs the trial catalogue.** It lists 597 trial
  items with 809 immediate trial steps: the classic level-75 chains, the
  Relic/Mythic 90/95/99 upgrades, the Empyrean and Relic armour +1/+2 steps and
  the i119 augment weapons such as Centovente and Fusetto. Pick a trial and
  **Complete trial** replaces the bag copy with the trial's reward and writes the
  Magian block (four augment words plus the trial id) in one write; the i119
  finals keep their item id and just take the chosen block. Filters by name,
  Weapons/Armor and **Owned only**; wardrobe and storage copies work too.
- **The dataset is `data/magian.json`**, built by `tools/gen_magian.py` from
  LandSandBoat's `magian_data.lua` (759 trials / 798 items, item ids, reward
  augments and trial ids) and the BG Wiki trial pages for the i119 augment
  weapons (Centovente's three paths and the other parsed finals). The Magian
  block table gained the reward ids the trials use (DMG 0x2E4/0x02D/0x2EA,
  Delay 0x2F9/0x2FC/0x2F5, Attack 0x019) with their Magian scaling.
- The i119 augment tables on the Hand-to-Hand, Great Sword, Great Axe, Scythe,
  Polearm, Great Katana, Club, Staff, Instrument and Shield pages use a
  different wiki format and are not merged yet; their classic/Relic stages are
  present. `docs/magian.md` records the coverage.

## Unreleased — Hoxne Earring scales with Mastery Rank

- **The Hoxne Earring's "All BP -30 to +30" is now applied.** The item has no fixed
  `item_mods` rows, so wearing it did nothing. `game/item_effects.py` resolves its seven
  attributes from the character's Profile Mastery Rank (1–3: -30/-20/-10, 4: 0, then
  +5 per rank to +30 at rank 10) and the three equipment queries merge that total:
  the combat outfit, the per-slot rows behind the launcher's checkparam report, and the
  single-item query. A stored rank of 0 uses the item's -30 floor. At rank 10 the
  `0x061` status packet carries +30 as the gear adjustment for STR/DEX/VIT/AGI/INT/MND/CHR.
- **Only an equipped copy counts.** The inventory copy alone adds nothing, and changing
  the Mastery Rank on the Data page flows through `//reload` because the queries read the
  stored byte. `test_item_effects.py` pins the rank table, the equipped/inventory split,
  the report rows and the `0x061` adjustment.

## Unreleased — buffs and ability cooldowns survive a dropped link

- **A disconnect no longer wipes the song list.** Retail keeps a character's status
  effects on the server, so a client that drops its connection and signs back in finds
  the same buffs ticking; Fanxi rebuilt the session from scratch and lost them. The
  session now writes a small snapshot to `char_live_state` (migration 145) while it is in
  the world, coalesced to one write per change, and again when it is reaped, replaced by a
  new login or stuck mid-hand-off. The next login restores the effects in their original
  icon-slot order with their remaining time, so the `0x037`/`0x063` pair draws the bar
  exactly as it was. Every timestamp is absolute, so the minutes spent offline count
  against the buff instead of pausing it.
- **Job-ability recasts come back on `0x119`.** A two-hour that was on cooldown when the
  client died stays on cooldown. A deliberate `/logout` keeps the cooldowns but takes the
  buffs with it, as retail does; a Mog House login and a login after a K.O. behave the
  same way. Trust auras are not restored (the alter ego is released with the old session),
  and food comes back with its modifiers and its Food icon in step.
- **The player is told when they are back.** A couple of seconds after the zone-in burst —
  never inside it, where chat can take the client out of movement — the server says what
  it held and names the first buff to expire: *"Welcome back. The server held 5 song(s),
  2 buff(s) and 3 ability recast(s) while you were away."* `game/live_state.py` holds the
  payload, `char_live_state` the row; `docs/world.md#recovering-a-dropped-client` and
  `docs/songs.md` describe the behaviour.

## Unreleased — Trial of the Magians TP Bonus

- **Centovente's TP Bonus +1000 augment now works.** The live copy had no augment
  block at all, and the server had no Trial of the Magians decoder, so the
  `TP Bonus` modifier was never read. `server/fanxi_server/game/magian.py` now
  reads and writes the kind `0x02` / sub-kind `0x43` block, mapping id 353 value 19
  to +1000; migration 144 seeds the TP Bonus choice on empty Centovente copies.
- **Moonshade Earring's +250 was already working.** Its standard block (id 353,
  value 4) contributes `TP_BONUS` 250. With Centovente also equipped, the live
  outfit now reports **TP Bonus 1250** to `weaponskill_tp`, which raises the fTP
  used by every weapon skill without changing the TP spent.
- `test_magian.py` pins the Centovente block, the WSD/Store TP alternatives and
  Moonshade's +250; `augment_stats` routes Magian blocks through the same
  `combat_mods` path as every other gear and weapon augment.

## Unreleased — Savage Blade damage

- **Naegling and Kaja Sword's "Savage Blade" damage +15% is applied.** LandSandBoat
  stores a weapon skill's own damage bonus in the 570 + id block; Savage Blade is
  id 42, so the modifier is 612. The two swords' item rows did not carry it, which
  cost every Savage Blade 15% on all hits. `database/migrations/0143_...sql` adds
  it and `test_weapon_skills.py` pins both weapons.
- No other part of the Savage Blade formula changed: the Adoulin fTP anchors
  (4.0 / 10.3 / 13.6), 50% STR / 50% MND WSC, two native hits, TP Bonus and the
  15% weapon-skill damage from the cape/ring are already read by the damage path.

## Unreleased — full Odyssey coverage and a searchable RP picker

- **The RP card now covers the rest of Odyssey.** Bunzi's, Ikenga's and Mpaca's
  armour and weapons, Gekkei, Kunimitsu, and the Atonement 1/2 accessories are
  in `data/odyssey_extra_r30.json`; `odyssey.entries()` merges that file with
  the four GearSwap sets. A purchased Bunzi's Hat (bundle 433) now appears in
  the card, along with the rest of its set and the missing Odyssey pieces.
- **The RP gear picker is searchable.** The long native select is now a
  combobox with the Armory's typeahead behaviour: type a name, set, slot or bag,
  then use ↑/↓ and Enter to select. `test_odyssey.py` pins the expanded
  catalogue and bundle indices; `test_character_data.py` pins the Bunzi's Hat
  purchase path.

## Unreleased — Moonshade Earring augments on the Data page

- **A new Moonshade Earring card** writes the Wings of the Goddess reward's two
  augments: one choice from Set 1 (Accuracy, Attack, Ranged Accuracy/Attack,
  Magic Accuracy, "Magic Atk. Bonus", HP or MP) and one from Set 2 ("Regain",
  "Refresh", the TP damage proc, TP Bonus+250, the magic-accuracy proc, Quick
  Magic, "Counter" or ailment resistance). The ids and values are the pairs
  LandSandBoat's *Lest We Forget* mission hands to `addItem`, so the block is
  the one retail writes. **Apply augments** writes both words and **Clear
  augments** empties the block; copies in the wardrobe and storage can be
  augmented without moving them. `data/moonshade.json`,
  `server/fanxi_server/game/moonshade.py` and
  `launcher-rs/src/components/MoonshadeEarring.tsx` hold the pieces;
  `docs/moonshade.md` lists the 16 choices.
- `capes.TABLE` gained the five ids those choices use (latent Regain/Refresh,
  TP Bonus, and the two "Occ." rows), and the stat sheet applies Accuracy,
  Attack, HP, TP Bonus and "Counter" while listing the conditional rows as
  unmodelled.

## Unreleased — Temenos Furnace gear in the RP card

- **The Data page's RP card lists all four Temenos Furnace pieces.** Alabaster
  Mantle, Alabaster Earring, Murky Mantle and Murky Ring (Limbus gear upgraded
  with Alabaster and Murky Matter) now appear beside the Odyssey, Limbus and
  Unity pieces, with their fixed Rank 30 rows and a **Cap path** button that
  writes the block. The first three carry a standard five-slot block, so
  `capes.describe` renders the rows and `augment_stats` applies them; the client
  groups the Mantle's two-stat rows as Accuracy+Attack and Ranged
  Accuracy+Ranged Attack, with the same totals. The Alabaster Earring's
  `All Attr.+10` row has no standard id, but client bundle **468** encodes
  exactly its three Rank 30 rows, so the earring carries a bundle block instead.
  `data/temenos_r30.json` holds the picks and bundle, and
  `server/fanxi_server/game/temenos.py` the lookup.
- **A purchase shows up in the card automatically.** The RP list is rebuilt
  from the character's permanent bags on every character-data read, and the
  Armory's purchase response already carries the refreshed snapshot, so a
  bought Furnace piece appears (and can be capped) without a separate "add to
  card" step.

## Unreleased — Armory sells Ex-only gear in multiples

- **Only Rare is one-per-character in the Armory.** Ex alone stops trading and
  selling, not holding two, so an Ex-only piece such as Linos (the Alluvion
  Skirmish bow) can be bought as many times as the bags have room for. The card
  shows **Buy another** and a note that Ex does not limit copies; a Rare piece
  still says **Currently owned**. The equip check follows the same split: two
  copies of a non-Rare item can be worn, while a Rare one still cannot.
- The catalogue's `exclusive` flag became `unique` (Rare only), and
  `service.add_item`'s `one_per_character` parameter is gone; `armory_add` and
  the shop both enforce Rare alone.

## Unreleased — Divainy-Gamainy Skirmish augments

- **The Data page has a Skirmish augment area.** A new **Divainy-Gamainy ·
  Skirmish** card lists all 138 items from BG Wiki's four Skirmish categories:
  16 Alluvion weapons, 25 Alluvion armor pieces, 45 old Skirmish weapons (15
  families in NQ/+1/+2) and 52 old Skirmish armor pieces (five sets in NQ/+1 plus
  both Beatific Shields). Alluvion gear takes one Snow, Leaf and Dusk stone; old
  weapons always roll DMG plus one stat from each of two pools; old armor always
  rolls Physical Damage Taken plus one (NQ) or two (+1) bonus rows. Pick the stat
  for each row, lower a value or leave a bonus row empty, and **Apply augments**
  writes the standard five-slot block the capes and Oseem use. A live client sees
  it on `//reload`.
- **The dataset is `data/skirmish.json`**, generated from the four category
  pages: 36 shared tables (weapon class, armor set, or one per old family/set)
  with the highest value each wiki row lists. Alluvion DMG caps are per weapon
  (Ohrmazd +29 through Inanna +39); a two-hander's Dusk tip is Delay- on melee
  and Snapshot on Archery/Marksmanship.
- **`server/fanxi_server/game/skirmish.py`** holds the client ids: the combined
  rows (Mag. Acc./Mag. Atk. Bns., STR with DEX/VIT/AGI, ...), the scaled Save TP
  (×10), Pet: TP Bonus (×20) and Elemental Siphon (×5) rows, Enmity's two ids and
  the ranged DMG/Delay ids. `augment_stats` reads the block back, with the new
  Skirmish ids added to `capes.TABLE`, so Accuracy, Store TP, Haste, damage taken
  and the rest reach combat; weapon DMG/Delay stay client text because the engine
  reads them from the base item row.
- `docs/skirmish.md` describes the flows and the block; `server/tests/test_skirmish.py`
  pins the catalogue, the wiki maxima, every option's encodability and round trip,
  the stat-sheet read and apply/clear, and `test_api.py` pins the HTTP card and
  both progress ops.

## Unreleased — Unity accessories in the RP card

- **The Data page's RP card now lists every Unity accessory, not just the
  original five GearSwap pieces.** The 27-piece Unity accessory catalogue is in
  the registry, including Acuity Belt +1, Kentarch Belt +1, Sailfi Belt +1 and
  Shinjutsu-no-Obi +1, each with the client bundle matched to its BG Wiki
  Rank 15 row. A piece bought from the Armory appears in the card as soon as the
  purchase response lands; no separate "add to card" step is needed.
- `test_character_data.py` pins the Armory → refreshed snapshot → RP-card flow,
  `test_unity.py` pins the catalogue and the four belt bundles, and
  `test_augment_stats.py` pins the STR / Double Attack rows.
- `docs/unity-augments.md` and migration 83 are regenerated by
  `tools/gen_unity.py`.

## Unreleased — the rest of the Samurai kit

- **Sekkanoki** charges the next weapon skill: 1000 TP spent (the rest stays on the
  bar), potency capped at 1000, and Hagakure's TP bonus suppressed for that skill.
- **Third Eye** anticipates the next swing: one charge, or three under Seigan, spent
  before the damage roll. (Its status icon and the Seigan 25% counter are still open.)
- **Konzen-ittai** readies the monster: the skill that lands while it is up seeds a
  resonating property and forms a skillchain by itself.
- **Sengikori** adds +25% to the next skillchain and +25% to the magic burst that
  follows it. **Shikikoyo** shares TP above 1000 (the merit rows raise what the target
  receives). **Blade Bash** stuns for three seconds. **Hagakure** and **Meikyo Shisui**
  were already wired in the tree and are now covered by the report.
- **Zanshin** now rules the swing: a miss gets one more swing at the trait's rate, and
  under Hasso a landed hit gets the same chance at a quarter of it. **Seigan** turns an
  anticipated hit into its 25% counter. **Warding Circle** (3 min) and **Yaegasumi**
  (45 s) use their retail timers.
- Tests: `test_sam.py` now covers Third Eye/Seigan charges and the counter, Zanshin,
  Blade Bash, Shikikoyo, Konzen-ittai, Sengikori, and the Warding/Yaegasumi timers;
  `test_weapon_skills.py` covers the Sekkanoki spend.
  `docs/job-sam.md` marks what is done and what is left (Third Eye's icon/counter,
  Warding Circle, Yaegasumi, Hamanoha, Zanshin, trait parity).

## Unreleased — weapon-skill TP return, Save/Conserve TP and skillchain results

- **A weapon skill now pays TP back.** The first main-hand hit returns that weapon's
  delay TP, a one-hit skill's off-hand swing returns the sub weapon's delay TP, every
  other landed hit (later native hits, DA/TA/QA procs, off-hand multis) returns 10 TP,
  and Store TP multiplies each. A miss gives up the delay TP but later hits still pay;
  a magical or self weapon skill returns none. The bar shows the refund immediately.
- **Store TP now feeds weapon skills, not only auto-attacks.** The base comes from the
  delay curve, then `(100 + Store TP)/100`; the Samurai Store TP trait, the 0x0444
  Store TP Effect merit (2 per rank) and gear lines all reach it through `combat_mods`.
- **Save TP and Conserve TP are modelled.** Save TP (mod 945) is compared with the
  normal return and the larger is kept, capped at 500; Conserve TP (mod 944) is a
  percent chance to add 10–200 TP on top, even on a miss. Hagakure grants 400 Save TP
  and 1,000 TP Bonus to the next weapon skill; Meikyo Shisui spends exactly 1,000 TP,
  scales from the current TP, grants 3,000 TP on use and suppresses the hit TP return.
- **Skillchain damage rides the closing weapon skill.** `_advance_skillchain` now
  returns the proc kind, damage and `287 + proc` message, and the closing WS result
  carries them in its **additional-effect block**. The damage is applied server-side,
  the client draws the skillchain animation, and the old separate 0x028 action (which
  printed a line but had no add-effect) is gone. Skillchain Bonus gear (mod 174) scales
  the closing damage before it is applied.
- Tests: `test_weapon_skills.py` pins main/off-hand/extra-hit TP, Store TP, Save TP,
  Conserve TP, Hagakure, Meikyo, the SAM Store TP merit, the skillchain add-effect
  (damage, proc id, message and animation carrier) and Skillchain Bonus scaling.

## Unreleased — Samurai: Hasso, Seigan and Meditate

- **Hasso** is a real stance now. With a two-handed weapon it grants
  `floor(SAM level / 7)` STR (14 at 99, on top of the +20 from the 20/20 Hasso Effect
  job points), +10 Accuracy and +10% job-ability haste, multiplies casting time by 1.5,
  lasts five minutes and cancels Seigan. **Seigan** cancels Hasso the same way.
- **Meditate** ticks instead of paying the bar at once: 200 TP a tick for five ticks
  (1,000) as a Samurai main with the +5-a-rank job points, 120 a tick to 600 as a sub
  job.
- `test_sam.py` covers the stance stats, the two-handed requirement, the overwrite and
  both Meditate tables; `docs/job-sam.md` is the audit with the remaining SAM gaps
  (Third Eye, Sekkanoki, Hagakure, Konzen-ittai, Sengikori, Shikikoyo, Blade Bash,
  Warding Circle, Yaegasumi, Meikyo, the SAM traits).

## Unreleased — skillchains and magic bursts

- **Skillchains never formed**: `skillchain.py` had the full LandSandBoat rules (the
  transition table, the tier/link damage multipliers, the Magic Burst formulas) but
  **nothing called it** — no per-monster state, no chain resolution, no burst window.
  Weapon skills landed as plain damage and the window never opened.
- **Weapon skill properties** now come from each skill's BG-wiki infobox
  (`sc1`/`sc2`/`sc3`) into `data/weapon_skill_properties.json` — 213 skills with their
  primary/secondary/tertiary properties; self-targeted and property-less skills are
  left out.
- **The chain**: a landed weapon skill with properties opens a 10-second window on the
  monster; a later skill that lands more than 3 seconds after it forms the chain if its
  properties resonate. The closing skill's damage is multiplied by the tier/link table
  (`0.50` for a tier-1 first link) and the result is sent as its own 0x028 with the
  client's skillchain message (287 + proc kind). A chain kills the monster if the
  chain damage is the killing blow.
- **Magic Burst**: while a formed chain is up, a damaging spell of the chain's element
  gets the burst multiplier (`1.85` at the first link), +100 Magic Accuracy and the
  `Magic Burst!` message (252). Off-element or expired windows do not burst.
- Tests: `test_skillchain.py` pins the rules (Fast Blade → Burning Blade forms
  Liquefaction, the 3-second delay, the multipliers, the burst window) and
  `test_weapon_skills.py` runs two staff skills through the real handler and checks the
  chain action and its damage.

## Unreleased — Exemplar Points, summed weapon skills and the WS start action

- **At level 99 a kill pays Exemplar Points, not experience.** The zone computes the
  BG-wiki formula — effective level `119 + MasterLevel/5`, `20 + 4*dLVL` at or above it
  and `20 + 2*dLVL` below, multiplied by the mob category (Locus x7, Apex x5) — and
  `Service.award_exp_gil` keeps the points in `characters.exemplar_points` instead of
  the EXP column.  A kill now sends message **809** ("gains # exemplar points") rather
  than message 8, the 0x061 Master Level block and the launcher's Data page both read the
  new total, and every 30,000 points raises the current job's Master Level (message 811)
  up to 50.  The EXP bar no longer moves at 99.
- **A weapon skill now resolves its whole attack round and sends one total.** Retail
  rolls Double, Triple and Quadruple Attack on a weapon skill's hits (up to two procs),
  adds one off-hand swing and its own multi-attacks while dual wielding, and caps the
  round at eight results.  `ZoneSession._roll_weaponskill_round` now does the same, using
  each hand's own Accuracy and fTP rules, the first main-hand hit's hidden +100 Accuracy,
  the skill's WSC and fTP on every hit it should apply to, and the target's HP as the
  stopping point.  The action packet carries the summed damage once, so the chat log and
  the server's `action out` line show one number (the skill the player actually used)
  instead of a line per hit.
- **Only "critical hit rate varies with TP" skills can crit.** A normal weapon skill no
  longer takes the auto-attack base/dDEX/gear critical roll; the skill's own TP crit
  table and Fencer still apply to the skills that can crit.
- **Overkill is capped at the target's remaining HP.** An 18K Rudra's Storm on a 2K
  monster now prints and deals 2K, as retail does, instead of telling the client it did
  18K.
- **Rudra's Storm's animation has its weapon-skill context again.** The server now sends
  the 0x028 SkillStart action (category 7, `SkillUse`, result = skill id, message 43)
  before the finish.  Without it the client could read the finish's sub-kind against the
  spell animation table, where 236 is Frost, and play a Blue Magic casting motion.
- Tests: `test_weapon_skills.py` pins the start/finish order, DA/TA extra swings, the
  off-hand swing, the crit rule, the first-hit accuracy bonus, the eight-hit cap, the
  overkill cap, the skill-miss message and the single summed result;
  `test_service.py` pins the level-99 Exemplar award and Master Level step, and
  `test_world.py` pins the 809 message for a Locus kill.

## Unreleased — spells are gated by job and level

- **Spells now follow retail availability.** `data/spell_levels.json` carries the
  (job, level) rows from LandSandBoat's `spell_list.sql` (837 spells); `zone.spell_bits`
  clears the client's spell bitmap for the ids the main or sub job has not learned, and
  `cast_magic` refuses a gated spell with "You cannot cast that spell." Until now the
  bitmap was a constant of every valid id and any job could cast anything.
- Spells with no level row are not gated: Trusts, the job-point and merit spells
  (Dia IV/V, the -ga IV/V line, Utsusemi San, Fire VI, Threnody II, Honor March, Aria
  of Passion, …) and monster-only rows. The songs among them are still instrument-gated.
- `test_spell_levels.py` pins the table (Cure = WHM 1 / RDM 3 / PLD 5 / SCH 5), the
  bitmap bits, the refusal message and the sub-job rule (RDM 49 sub can cast Cure but
  not Fire V). The spell-mechanics tests borrow the job that learns the spell they use.

## Unreleased — the launcher opens on the chosen display

- **Settings → Game window has a Display picker.** The launcher window, the game's sign-in screen
  and every visible client open on the chosen display (the main display by default) instead of
  always on the Mac's main screen; picking one moves the launcher window immediately. Full screen
  and borderless full screen cover that display, **Fit this display** and the resolution presets
  use its usable area, and the launcher's monitor line and warning follow it too.
- **The display travels to `host64` as `FANXI_DISPLAY=x,y,w,h`** in the window API's units
  (screen points on macOS, pixels elsewhere). `host64` matches it against SDL's displays and
  centres its sign-in and game windows there, at the display's top left for the full-screen
  modes, and reports that display's mode and usable area as the desktop's. Unset, both windows
  keep opening where the platform puts them. A display that is no longer attached falls back to
  the main display.

## Unreleased — the launcher shows every support job

- **A job line now shows the support job wherever the main job appears.** Home, Characters,
  Team, Control, Warps, Data, Gear and the Battle roster read `sub_job`/`sub_level` next to the
  main job ("WAR 99 / NIN 49", or `Warrior 99 / Ninja 49` where names fit), and the tenant bar
  carries the pair for the character every page is looking at. A running client reports its live
  pair from the control addon (`state.player.job` plus the new `sub_job`/`sub_level`), so a
  `//job` change updates the launcher immediately; an offline box or an older addon falls back to
  the saved character row.
- **Team and Control list the whole team's jobs.** A shared **Team jobs** / **Party jobs** card
  shows the main account and every box, each with its main and support job, level, live/offline
  badge and a strip of the distinct jobs the team covers. The Control room's **Live party** table
  gained a **Job** column, and its party rows, selected-equipment card and KPI summary now name
  the pair too. The Gear page's **Live job** card and the Battle roster show the support job
  beside the main job.

## Unreleased — the Battle HUD draws the zone map

- **The Battle HUD is a zone minimap now.** Instead of a black box, the movable HUD draws the
  zone's own map — the map DAT the in-game map screen and the Minimap plugin read — behind the
  tank and support camps, their radii, the party, nearby mobs and the player's heading. The image
  is decoded from the player's install (`xi.res.map_rgba`, 8bpp paletted and DXT1/3/5 map DATs),
  one texture at a time, so nothing is shipped and HD 1024 map packs work.
- **Placement comes from the community map table.** `host/addons/lua/mapdata.lua` (generated by
  `tools/gen_map_data.py`) holds the zone -> map DAT id and its scale/offset; the panels line up
  with the world (checked against the imported monster spawns in West Ronfaure, Konschtat,
  Qufim and Al Zahbi). The HUD now shows a **local window centred on the player**, FFXIDB-style,
  with a mouse-wheel zoom and a yalm range on the Camp page (default 800 yalms across; the
  whole-zone view is the wide end of the range). Zones without a map keep the old camp-centred
  radar, and a multi-floor dungeon shows its lowest floor until floor switching exists.
- The HUD window is taller when the map is on (it becomes roughly square), and its saved height
  is raised to fit, so the buttons are not clipped.

## Unreleased — Bard support songs

- **Scherzo, Threnody and Elegy now do what they say.** Scherzo's damage-reduction row
  is written to `UDMGPHYS`/`UDMGMAGIC` (‑45% … ‑53%, its own multiplier rather than the
  50%-capped PDT family), Threnody's elemental Magic Evasion down is
  stored on the monster as the hidden `MAGIC_EVASION_DOWN` effect the debuff reader
  already uses, and Elegy's attack-speed slow rides the mob's `SLOW` effect, which its
  swing timer multiplies into the delay. `world.tick_mob_effects` no longer prints a
  wear-off line for those hidden entries.
- **Carol is elemental resistance, not Magic Defense.** Fire Carol raises `FIRE_MEVA`
  (and so on for the eight elements), the eight Carol II spells are built from the
  table even though the generated status list omits them, and the data gained rows for
  the Threnody (18), Elegy (2), Mambo (2) and Ballad I spells.
- **Mambo is Evasion, Prelude is Ranged Accuracy only, and Nocturne is Magic Accuracy
  down** — the data generator was matching "Ranged Accuracy"/"Magic Accuracy" to the
  melee accuracy stat and dropping the mambo rows.
- **Requiem's job-point DoT lands after Soul Voice/Marcato** (the wiki's 81/88
  examples) and **Lullaby's +20 s is part of the base timer** (it was gated on effect
  193, while Lullaby's effect is 2, so it never applied).
- **Magic Finale dispels** through the same `world.dispel_mob` path as Dispel, and
  **Goddess's Hymnus** grants a real Reraise: the song keeps icon 218 and the Reraise
  effect rides beside it, so 0 HP now revives at 10% HP and consumes it. That also
  gives the White Mage **Reraise** spell the behaviour it had never had (the effect
  was stored but nothing on death read it).
- **Pianissimo now narrows the song.** The status was only feeding the fast-cast job
  points; `song_targets` makes the next song land on the party member it was cast on and
  no one else. **Song Accuracy Bonus** likewise moved off the generic Magic Accuracy
  (which every Bard nuke was inheriting) onto the singing skill, songs only.
- Tests: `test_songs` pins every family's stat table, `test_bard_songs` casts
  Scherzo/Threnody/Elegy/Carol/Mambo/Hymnus/Finale and the Requiem example against a
  real session.

## Unreleased — a gear swap only sends the pieces that change

- **The phase engine diffs a set against what is worn, like GearSwap does.** Every state
  flip used to send the whole 15-piece set, and each `0x050` batch makes the server answer
  with its full equipment follow-up (`0x051`, `0x0AA`, `0x0AC`, `0x061`, `0x037`, the
  `0x058`/`0x00D` stance). Six boxes stutter-stepping as they follow were fielding 60-136
  equipment packets a second for four seconds at a stretch, which is the load the main
  client hung under on 27 Oct. `copy_set` in `host/addons/phase.c` now keeps a worn table
  (bag and inventory slot per equipment slot) and leaves out a piece that is already on, so
  moving between `idle.town` and `idle.movement` sends the seven pieces that actually
  differ instead of all sixteen.
- **Only the state sets diff.** Precast, midcast and the return set still go out whole:
  they are one batch per action, and diffing the midcast against the precast would need the
  server's answer before the return set is built. They update the worn table, so the state
  set after the action is compared against what the action left on.
- **The table follows the changes the engine cannot see.** The client's own `0x050` (the
  player equipping by hand) forgets that slot, as does the server's slot-`0` echo (an
  unequip, or the off hand a two-hander just cleared), and the launcher's manual **Wear
  set** forgets the table. A zone-in, a job change and a different character clear it, so
  the first set after them goes out whole and resyncs.
- **A re-pushed plan no longer re-wears the outfit.** The launcher pushes the plan after
  every edit (and once more six seconds after login), and each push used to clear the worn
  table, so `apply` sent all sixteen pieces even when only a spell mode had changed. The
  table is keyed by item, not by set index, so a push keeps it and the next set sends only
  what the edited plan actually changed.
- **A follower's stutter no longer flips the set.** The movement state comes on at the first
  step but now leaves only after 1.2 s of standing still (was 0.5 s): a box that walks,
  stops for a swing's worth of time and walks again used to toggle `idle.movement` on every
  stop, and each toggle was a batch on the wire.
- `tests/phase_state_test.txt` pins the diff: the first set sends all four pieces, a
  movement step sends only the two that differ, stopping sends the two back, an unchanged
  set sends nothing, an equip echo leaves the table alone, and the client's own equip or a
  server unequip makes exactly that slot re-send. The runtime stamp is `0.2.70` because the
  client binary changed.

## Unreleased — a pulled monster always gives chase

- **Enmity now moves the monster, not only its name colour.** A chase route used to be
  rejected whenever any waypoint stood more than four yalms above or below the spawn.
  Pulling a monster from a slope below (or above) its camp therefore found a valid A*
  route, threw it away, and left a red-named monster standing at the pull spot while the
  player cast at it. A chase now uses a 60-yalm sphere around the spawn; the nav grid's
  per-step floor and barrier tests still refuse walls, cliffs and floor edges.
- **A claim also clears the monster's stale movement.** `add_mob_hate` drops the old roam
  leg, nav path and any failed-search cooldown when the highest-hate player changes, so
  the first tick of a fight runs at the puller instead of finishing an idle walk.
- **No route still closes the gap.** When A* cannot connect the two floors (a seam, a
  search budget, a cave lip), the chase falls back to a direct step: the monster samples
  the same floor and wall tests along the straight line and stops at the first legal
  barrier, instead of standing still. It never walks through geometry to do it.
- `server/tests/test_nav.py` pins the slope chase, the no-route pull and the cliff stop.

## Unreleased — the drawn weapon survives a gear swap

- **The status packet no longer sheathes an engaged character.** `0x037`'s `server_status`
  (body `0x2C`) is the character's animation — the same field `0x00D` carries at `0x1B` — and
  the client reads it as the local player's pose. Fanxi sent `0` on foot, so every gear batch's
  follow-up (`equipment_sync`, which ends with a `0x037`) told the client "idle" while
  `assert_stance`'s `0x00D` in the same batch said "weapon drawn". The client sheathed between
  them and drew again: a gear swap looked like a disengage followed by the server re-engaging,
  and a GearSwap that swaps on movement or aftercast produced the flap continuously. Both
  packets now come from one `own_animation()` (mount, else `1` engaged, else `0`), so the
  status block can never contradict the stance block.
- `server/tests/test_world.py` pins it: `0x037` is 0 → 1 → 0 with engage and disengage, and a
  flushed equipment batch carries animation 1 in its `0x037` and its `0x00D` alike.
- `docs/world.md` and `docs/mounts.md` now say `server_status` is the stance on foot, not only
  the ride.

## Unreleased — Bard song potency follows the wiki tables

- **Song strengths were about a third of retail's.** `_bard_songs` used a hand-written
  `10 * tier` model, so Valor Minuet V was +50 Attack (retail +124), Victory March 6%
  haste (retail 15.92%) and Minne V +50 Defense (retail +204). The new
  `data/song_potency.json` carries BG-wiki's per-Song+ table for 69 songs, taken from
  [BGWiki:SongPotency](https://www.bg-wiki.com/ffxi/BGWiki:SongPotency), and
  `_bard_songs` builds each song's base from its +0 column.
- **Song+ now scales the way the wiki says.** `song_potency_values` indexes the song's
  row by All Songs plus its family row instead of adding one flat point: Minuet V is
  124 → 223 across +0..+8, Victory March 15.92% → 28.61%, Ballad III 3 → 11 MP a tick.
- **Bard group-1 merits and the job-point rows are counted, and counted in the right
  order.** Minuet Effect (+5 at 5/5, +20 JP), Minne (+10, +20), Madrigal (+5) and
  Requiem's +60 DoT are added after the +Song percentage and *before* Soul Voice or
  Marcato, which is why the wiki's example — Minuet V, +8, 5/5 merits, 20/20 JP,
  Marcato — lands on +372 Attack. `zone.song_flat_bonus` reads `char_merits` through
  the new `merits.MINUET_EFFECT` / `MINNE_EFFECT` / `MADRIGAL_EFFECT` ids; the old
  post-multiplier bump was removed so the rows are not double counted (and the
  Accession path no longer adds them a second time either).
- **`//songs`** prints the songs on you with their remaining time and the values they
  apply, since the client cannot tell three Minuet tiers apart (they share icon 198).
  The host only forwards `//` words it knows, so `songs` joins the command table in
  `host/addons/complete.c` (and `tests/chat_complete_test.c` checks it). The client
  needs a rebuild for that: the runtime stamp is `0.2.69`.
- `server/tests/test_songs.py` pins the tables, the wiki's worked example and the
  scaling; `test_bard_songs.py` pins the merit + job-point order in a live cast.

## Unreleased — Nolan mezzotints and Oseem Arcane Glyptics

- **The Data page can mezzotint Escha gear.** A new **Nolan · Escha mezzotint**
  card lists the Escha - Zi'Tah, Escha - Ru'Aun and abjuration pieces the
  character holds and shows each path's three Rank 15 rows. **Apply path**
  writes the client's mezzotint block (kind `0x02`, subkind `0x20`, path/rank,
  three `(index, value)` rows) in one step, so an owned Kaykaus piece gains the
  path's full maximum; a live client picks it up on `//reload`. The card sits
  beside the Ambuscade cape editor and uses the same Data-page apply loop.
- **The catalogue is the whole BG Wiki Nolan page** (`data/nolan_mezzotint.json`):
  38 weapons, the seven Zi'Tah sets and the eleven NQ/HQ abjuration sets — 183
  items, four paths each, three rows each. Paths A/B/C are stored on every piece
  of a set even though the wiki rowspans them, so the card never has to special-
  case the shared rows. `server/fanxi_server/game/mezzotint.py` holds the stat
  table (HP through the instrument skills), the encoder/decoder and the apply
  call; `augment_stats` reads the block back so the augments reach combat, not
  just the tooltip.
- **Oseem gets an editor instead of a reroll.** The new **Oseem · Arcane
  Glyptics** card covers the five Reisenjima armor sets and fourteen Reisenjima
  weapons. Pick the path (Melee/Ranged/Magic/Familiar/Healing/Pet), then a stat
  for each of the five slots; the value starts at the wiki's maximum and **Max
  all** restores it. **Apply augments** writes the standard five-slot block the
  capes use; **Clear augments** empties it. The table is
  `data/oseem_glyptics.json`, generated from the BG Wiki Arcane Glyptics
  category page, and `server/fanxi_server/game/glyptics.py` turns a
  `(key, value)` pick into the client id — including the offset-33 ids above 32
  and the combined Mag. Acc./Mag. Atk. Bns. row.
- **The cape decoder now knows the Oseem ids.** `capes.TABLE` gained the
  Reisenjima rows (extended Accuracy/Attack/Ranged/DMG, haste, damage taken,
  store TP, pet rows, the 0x700-range pet stats, ...), so `augment_stats` applies
  the new blocks through the same path as every other standard augment.
- `docs/nolan-mezzotint.md` and `docs/oseem-glyptics.md` describe both flows and
  their block layouts; `server/tests/test_nolan.py` and
  `server/tests/test_glyptics.py` pin the catalogues, encoders, stat-sheet
  reads and service calls.

## Unreleased — Bard song duration counts Song+ gear

- **Song+ gear now lengthens songs, as retail does.** BG-wiki's Song page is
  explicit: "Song+ potency gear increases duration by 10% per 1 Song+", additive
  with the "Song duration +N%" lines. `effects.song_duration_percent` applies
  `454 + 10 × Song+` (All Songs plus the song's own family row), and
  `song_duration`, `buff_duration` and `debuff_duration` all use it. That is what
  makes Loughnashade (All songs +4) +40% and Mnbw. Whistle +1 (+3) +30% even
  though neither has a duration line. A five-song bard goes from 8:02 to
  10:50-11:14 under Troubadour alone, 11:54 with Tenuto and 12:54 with Clarion
  Call and Marcato.
- **The Battle hub's song timers match.** `battle_song_catalog` hands the whole
  equipped-modifier block to `song_duration` instead of the 454 total, so the Song
  groups modal lists the real per-song duration.
- **The BRD library is rebuilt around it** (`gearswap/BRD.lua`): Loughnashade back
  in the range slot (All songs +4 beats Daurdabla's +30% and keeps Maximum songs
  +2), Mnbw. Whistle +1 on the neck (+30 over Aoidos' Matinee's +10) and Fili
  Manchettes +3 ("March"+1) on the hands. `SongDuration`, `Song`, `SongAria` and
  `SongPotency` share that loadout because Song+ is duration; `SongHonor` keeps
  Marsyas for Honor March at 191%, and `precast.Song` / `precast.FCHonor` keep the
  instruments the cast-time check reads.
- **`tools/brd_song_duration.py` ranks and reports the same way**, counting All
  Songs at 10% a point. `server/tests/test_effects.py` pins the rule and
  `server/tests/test_bard_song_sets.py` pins the library's loadouts and timers.
- **The midcast set now survives a slow cast.** The phase engine put the return
  set back 6 s after an action that had not produced a result packet yet, and a
  bard song takes 8 s (12 s under Troubadour's 1.5x cast), so the song resolved in
  the engine's idle gear and rolled its timer from the wrong equipment. The stale
  timeout is 30 s now (`host/addons/phase.c`) and the runtime stamp moves to
  `0.2.68`, so a client built from this checkout keeps the song set on until the
  song lands.

## Unreleased — Ambuscade cape augments in the Data page

- **The Data page builds Ambuscade cape augments from the BG Wiki rules.** A new
  **Ambuscade capes** card covers all 22 job capes. Pick a cape (or **Get this
  cape** to add a fresh copy to the inventory), then pick one row in each of the
  five Abdhaljs material panels — Thread, Dust, Dye, Sap and Resin — and a stage
  from 1 to that row's cap. The caps are the wiki's 20/20/10/10/5 items and the
  stage selector shows the resulting stat (`HP+60`, `Accuracy+20 Attack+20`,
  `Phys. dmg. taken-10%`, ...). **Finish augment** writes the five-slot block,
  **Max selected** caps every chosen row, and **Clear augments** writes the empty
  block `//cape off` uses. A live client is sent `//reload`.
- **Partial edits do not truncate custom blocks.** A material left untouched
  keeps the word already on the copy, so the seven pet-focused preset builds
  (pet stats packed into off-category slots) survive changing another slot.
  Choosing `— none —` clears just that material.
- **The client's dedicated Resin ids are understood too.** The picker writes the
  general stat ids the existing 198 builds use (DEF writes 0x480, whose value field
  holds the stage), but a copy carrying 0x481-0x486, 0x4DE or 0x4DF still maps back
  to the same Thread/Dust/Dye/Sap/Resin choice.
- Backend: `capes.MATERIALS` and the option encoder, a `capes` snapshot in
  `character_data`, and the `cape-add` / `cape-augment` / `cape-clear` progress
  ops. Tests cover every option's maximum, all 198 builds' selections, the pet
  build preservation path, the service writes and the HTTP endpoints.

## Unreleased — Haste pools and Bard song cast fixes

- **Haste is three pools again.** Equipment (25%), magic (43.75%) and job-ability
  (25%) haste are capped separately and then added, with the 80% delay floor intact.
  A Bard at the 25% gear cap now gets the full benefit of Haste and a March instead of
  watching every buff vanish into the equipment cap.
- **March haste was stored 100x too small.** Victory March wrote `6` into a
  hundredths-of-a-percent field, i.e. 0.06%, and Honor March `12` (0.12%). They are
  now 600 (6%) and 1200 (12%), and Song+ gear scales the same units. `test_songs` and
  `test_bard_songs` pinned the old values and are corrected.
- **Haste Samba and GEO Haste use their own pools.** Haste Samba writes
  `HASTE_ABILITY` and a Trust's GEO Haste writes `HASTE_MAGIC`, so neither competes
  with the equipment cap.
- **The reforged +3/+4 song pieces keep their song stats.** The item importer had no
  rule for "Song spellcasting time"/"Song casting time", "Song effect
  duration"/"Song duration" or "Song recast delay", so Fili Calot +3, Brioso
  Justaucorps +4, Bihu Slippers +4, Fili Hongreline +3, Brioso Slippers +4 and Fili
  Rhingrave +3 stored every tooltip line except the Bard ones. Migration 140 backfills
  the six rows; the Bard's song precast set now reads -41% song cast instead of 0%.
- **The reforged song pieces keep their family Song+ lines too.** The same importer
  ignored `"Madrigal"+1`, `"Minuet"+1`, `"March"+1` and friends, so those pieces added
  All Songs but none of their family bonus. Fili Manchettes +3's `"March"+1` now adds
  its 1% magic haste; migration 141 backfills the seven family rows.
- **Oboro path C song spellcasting time is read.** The augment parser listed
  `songspellcastingtime` as unmodelled, so Bard's Knife's -15/-20/-25% did nothing.
  It now parses (with the tooltip's minus sign turned into the positive reduction the
  cast code expects), and player `Haste+` augment lines are stored in hundredths.
- **The Bard Song Spellcasting Time gift is song-only.** It was merged into the
  generic Fast Cast pool, which also shortened Cure and every other spell. It now
  feeds modifier 455, so only songs benefit.

## Unreleased — per-song +9 potency sets

- **Every song now has a maximum-potency/maximum-duration loadout.** Loughnashade
  (+4) and Mnbw. Whistle +1 (+3) are the common +7; the new family sets add the
  JSE/Mousai +1/+2 for Paeon, Lullaby, Etude, Carol, Threnody, Minne, Mambo,
  Madrigal, Minuet and March. The phase engine selects them automatically by song
  family, while explicit Song overrides still win.
- **The +9 body/legs/feet swaps still last longer.** One Song+ point adds 10%
  duration, so Mousai Manteel/Seraweels/Crackows replace 14/17/15 raw 454 points
  and come out ahead. Ballad and Scherzo stay on the +7 all-duration set because
  their +1 pieces are on legs/feet and would make the song shorter.
- **Mousai's family Song+ rows are in the database.** Migration 142 adds Carol+2,
  Threnody+2, Minne+2 and Mambo+2 to the four Mousai +1 pieces; without them the
  correct item would be worn but the server would still compute only +7.

## Unreleased — Bard songs stack by song, not icon

- **Victory March and Advancing March no longer overwrite each other.** Every song in a
  family shares a status icon (marches use 214, Paeons 195, Minnes 197), and the server
  was keyed by that icon, so a second song in the same family replaced the first. Songs
  now use a per-spell state key while still sending the shared icon to the client:
  different marches, Paeon tiers and Minne tiers each take a slot and add their
  modifiers until the instrument's song cap. Recasting the **same** song still follows
  the existing refresh/overwrite rule.
- **Paeon and Ballad ticks add per active version.** Multiple Paeon songs now heal for
  the sum of their tiers each tick, and multiple Ballads add their MP refresh, instead
  of just occupying icons.

## Unreleased — Armory item aliases

- **The Armory accepts full and abbreviated item names as one result.** The client shortens
  many item names to 15 characters (`Mdk. Crackows +1`, `Pln. Crackows`, ...), so searching
  for the full set name used to miss them. Migration `0138` adds an `item_aliases` table and
  migration `0139` imports the untruncated BG Wiki name for all 2,068 abbreviated equipment
  rows; the Armory matches either spelling, and the launcher typeahead searches both while
  deduplicating by item id.

## Unreleased — BRD song follow-ups

- **Rare/Ex equipment cannot occupy two slots.** The GearSwap song sets now pin the
  offhand (`Genbu's Shield`) whenever the main hand is Carnwenhan, and the server
  refuses a second copy of the same inventory item or Rare/Ex item. The live duplicate
  Carnwenhan main/sub rows were corrected.
- **Separate spell and song precast.** `precast.Spell` is the general fast-cast set and
  `precast.Song` is the song-only set; the launcher Spells panel has a **Song precast**
  selector and the host uses it only for Bard songs.
- **Song overrides.** The launcher has a dedicated **Song overrides** card that lists
  only Bard songs and gives each one a precast and midcast set.
- **The Bard Song Effect Duration job-point gift is applied (+5%)** and is included in
  the server's song catalog; the Song Spellcasting Time gift is also applied. The
  current song-duration ceiling with the granted BiS gear is 5:12 before Nitro.
- **Instrument auto-swap before the cast.** The control addon intercepts
  `/ma`/`/song` requests for Honor March and Aria of Passion, equips Marsyas or
  Loughnashade first, and then replays the cast so the server's instrument check
  passes.
- **`Moonbow Whistle +1` is `Mnbw. Whistle +1` (item 26033)** in the client, not
  missing; it is granted and carries All Songs +3. The full name is only the wiki
  title.

## Unreleased — Bard song slots, Nitro and instrument songs

- **Songs now respect retail's slots and overwrite rules.** A Bard main with an instrument keeps
  two songs, Daurdabla/Loughnashade add two (`Maximum songs bonus`), Clarion Call adds a fifth, and
  a Bard support job or an empty ranged slot keeps one. A new song replaces the shortest remaining
  song; the same song cannot refresh while more than its unenhanced 120 s remains. That fixes the
  "every song sticks forever" behaviour.
- **Nitro and Soul Voice actually affect songs.** Nightingale halves the song cast, Troubadour
  casts at 150% and doubles the final duration, and Soul Voice doubles potency (and the duration of
  Hymnus, Mazurka and Sentinels Scherzo). Marcato is a 1.5x effect and does not stack with Soul
  Voice; Clarion Call/Tenuto/Marcato job-point seconds are added after Troubadour. Soul Voice now
  has its 3-minute status and a real 1-hour recast, and Clarion Call's status is 3 minutes.
- **Honor March and Aria of Passion are real spells.** Honor March (Marsyas) and Aria of Passion
  (Loughnashade) are in the spell table, and the server refuses them without the required
  instrument. The GearSwap library gains `SongHonor` and `SongAria`, which the phase engine uses
  automatically for those two songs.
- **Song gear and modes.** The library and HUD gain `SongDuration`/`SongPotency` sets with a
  **Bard songs** mode group (`//modes songs duration|potency`): Loughnashade, the 454 duration
  pieces, All Songs +4, Mnbw. Whistle +1 and the family Song+ pieces. `All songs +` and the
  family Song+ modifiers now affect song values.

## Unreleased — Battle healing uses Dancer waltzes

- **A BRD/DNC can heal without a Cure spell.** The Battle hub's Healing page now detects the
  client's Dancer abilities on a **main or sub job** and falls back to Curing Waltz for HP when no
  Cure spell is known or ready. It picks the highest Curing Waltz the TP can pay for after the
  configurable TP reserve, fires at or below the **Waltz below %** threshold, and ignores the
  reserve in the emergency band. The Healing page shows the detected waltzes, and **Suggest from
  job** turns both waltz options on when it finds them.
- **Healing Waltz removes waltzable status effects.** When no -na spell is known (the BRD/DNC
  case), Healing Waltz cleanses one status for 200 TP; a known -na spell is preferred when it can
  handle the same status. The waltzable list mirrors the server's Dancer status table, and the
  silenced-excluded-player exception uses Healing Waltz when Silena is not available.
- **TP is not MP.** The new **Keep TP** field defaults to 0 so the waltzes work immediately; raise it to keep TP for a weapon skill;
  Curing/Healing Waltz do not touch the MP reserve. Saber Dance blocks both, Trance makes waltzes
  free. The launcher's Battle → Healing & spells page has the same controls and docs are in
  [docs/battle.md](docs/battle.md#dancer-waltzes).

## Unreleased — Bard song pages group by colour

- **The Spells HUD splits a Bard page into coloured effect groups.** The Buff tab used to be one
  flat alphabetised wall of nearly eighty song tiles. It now reads as Haste, Attack, Defense,
  Magic Defense, Accuracy, Recovery, Etude and Support sections; the Debuff tab reads as Damage,
  Slow, Elemental and Control. Each section has a coloured heading with the song families it
  holds, and its tiles use the same colour on the note and border. The grouping stays inside the
  active Buff/Debuff page, so the existing folder tabs, targeting and mode strip are unchanged.
- **Song labels name the line instead of spelling out a fragment.** `Army's Paeon IV` now reads
  `PAEON` with a `IV` badge, `Knights Minne` reads `MINNE`, `Fire Carol II` reads `FIRE C`, and
  `Foe Requiem`/`Foe Requiem VIII` share `REQUIEM` with their rank badges. The launcher preview
  keeps the rank visible too. Song ranks no longer consume label characters; the test checks
  label + badge uniqueness.
- **Pining Nocturne and Maiden's Virelai move to the Debuff page** with the other enemy songs.
- **Honor March and Aria of Passion are in the map.** Honor March (Marsyas, Aeonic) reads
  `HONOR` and sits in Haste with the other marches; Aria of Passion (Loughnashade, Prime) reads
  `PASSION` and sits in Attack. Both used to fall into the `Other` section because they are
  granted by instruments and are not in the base spell migration.

## Unreleased — mounts, the whole stable

- **Every mount in the game.** Fanxi reads the client's own `mounts.names` table (39 mounts, ids
  0-38, from Chocobo to Bubble Crab), unlocks all of them with `0x0AE` at zone-in, and rides any
  of them: the local client is told through `0x037` (the Mounted status effect, the riding
  animation and the mount id), and every other client through `0x00D` (Flags6 MountIndex, the
  animation and the Chocobo_Index / CustomProperties the chocobo models need).
- **`//mount <name|id>`**, `//mount off`, `//mount list`, and **`//mount party [name|id]`**,
  which calls a mount for every online sub-account box — with no name, each box gets a
  **different random mount**, so the team rides out as a parade (`//mount all` remains as an
  alias). The client's own Mount menu and `/mount <name>` work too (the `0x01A` mount action is
  answered the same way).
- **A Mount HUD.** `//mounts` (or plain `//mount`) opens a window with a picture of every mount:
  select a card, then press **Mount** or **Mount party** (or **Dismount**). The pictures are the
  FFXI Wiki's mount art (`tools/fetch_mount_art.py`, credited in THIRD_PARTY_NOTICES.md) and are
  embedded in the build; a player can override any of them in `<data>/mounts/<id>.jpg`, or record
  their own with `tools/capture_mount_previews.py`.
- **Switching mounts** dismounts first and calls the new mount after the client has rebuilt its
  model; retail's one-minute recast is not enforced.
- **The launcher API**: `GET /api/v1/mounts`, `GET/POST /api/v1/characters/<id>/mount` (with
  `"all": true` for the team), the Data page's **Get all mounts** (`POST …/mounts`, which
  re-issues the unlock table), and the last mount a character called in `characters.mount`
  (migration 0135).
- Docs: [docs/mounts.md](docs/mounts.md).

## Unreleased — the Check menu answers

- **Checking a monster works.** The client's Check menu sends `C2S 0x00DD`; the zone dispatch
  had no handler, so the packet was logged once and ignored and the menu did nothing. Fanxi now
  answers with the client's own check line (`0x029` messages 170–178): the monster's level,
  retail's difficulty word (too weak through incredibly tough) and the Defense/Evasion sentence.
  The difficulty comes from the same base-EXP curve LandSandBoat checks against, and the line is
  picked from the player's Attack/Accuracy against the monster's Defense/Evasion.
- **Checking a player** tells them `<name> examines you.` with the client's own `0x009` message;
  the checker gets a chat line until the equipment-inspection window is implemented.

## Unreleased — a waiting follower can be fixed

- **Follow recovery uses the right axes.** The control addon reports the client's ground plane
  as `x`/`y` and height as `z`; `//pos`/`//zone` take `x`, height, `z`. The automatic recovery
  forwarded the block unchanged, so a box pulled from a distance landed hundreds of yalms in the
  air, saw no entities, and stayed `waiting` while the recovery repeated the same bad teleport.
- **Automatic recovery is bounded.** It stops after three hand-offs, does not run while the
  client is still logging in or zoning, and points at the new Fix button instead of looping.
- **Fix button on a waiting/stuck follower.** It kills the client, relaunches the same account
  (a remote Linux box through the same restart helper), zones it to its line leader, and
  re-applies follow.
- **Warps Mark uses the same conversion.** A mark made from the Warps page saves the live
  position in the server's `x`, height, ground order; the live coordinate row shows the same
  order as the saved rows.

## Unreleased — BRD song groups and server durations

- BRD no longer accepts typed song/ability names. Songs are selected from server-known job
  songs in a **Song groups** modal; each group is named and assigned to tank/support/mobile.
- Song durations come from the server, computed from equipped gear (`Song Duration Bonus`),
  and are shown per song. The 120 s interval input is removed.
- Pianissimo is a player + song selection, independent of camp groups.
- Mobile camp uses one song group; static split camps use the tank/support groups and move the
  BRD between them. Nitro behavior remains.

## Unreleased — clear camps keeps the Battle HUD open

- **Clear camps** only clears the two camp points. The HUD remains visible; closing it is still
  the X or the Camp page toggle. Overlay visibility now follows `camp_hud.show` rather than
  requiring a camp to be set.

## Unreleased — Battle HUD camp buttons and menu shortcut

- Added **Set tank**, **Set support** and **Clear camps** buttons directly under the HUD's
  Start/Stop/Follow row.
- Added a **Menu** button that opens the full Battle hub.
- HUD stays available when only the support camp is set or during `//hud move`; widened to 380 px
  so the button labels fit, with a 320 px minimum height for the extra row.

## Unreleased — mobile camps, tank camp optional and support pullers

- **Mobile camp mode** for Sortie/Odyssey/Dynamis. Melee follows the tank, support follows at a
  configurable distance, and static camp points are ignored.
- **Tank camp is optional but on by default.** With it off, tank/melee follow the tank and a camp
  point is not required to start.
- **Melee formation follows the tank** by default, with a toggle to return to mob-anchored slots.
- **Support pullers.** A support member can be selected as puller without losing support; the
  pull loop runs from the support camp and support abilities continue when not pulling.
- Shared-settings save propagates the mobile/tank options with the rest of the camp.

## Unreleased — person-level camps, combat style and shared-settings sync

- **Camp assignments by person.** Camp page lists every character with Camp (Auto/Tank/Support)
  and Combat (Auto/Melee/Ranged) selectors. Explicit camp choices override role; combat style is
  independent, so a RNG can melee in the tank camp or shoot from the support camp.
- **Shared settings sync.** Saving from Roster, Camp or Rules marks the profile shared and the
  server copies roster/camp/support-camp/camp_assign/combat_style/rules to every family profile.
  Player-settings saves remain per character.
- Engine uses the person assignment for return-to-camp, ranged positioning and melee/ranged combat
  behavior.

## Unreleased — job-accurate spells, support abilities, debuff logs and nav groups

- **Cure suggestions are job-accurate.** Spell lists now come from the tenant's main and sub job
  levels, with a heal-list prune; RDM no longer receives Cure V.
- **Support job abilities.** The Support page lists the tenant's main/sub job abilities with a
  Keep switch. Composure is enabled by default for RDM and is applied/reapplied by the support
  loop; GEO can select Bolster and its other abilities.
- **Debuffs are job-only and log-aware.** The list is restricted to the tenant's enfeebling
  spells. Chat text for a debuff's wear-off makes the next cast immediate; resists increment a
  counter; the page has a resist limit and Reset tries.
- **Nav groups.** Roster, Camp and Rules are under **Shared settings**; everything else is under
  **Player settings**.
- **Engage cleanup.** The unused "weapon skill (empty = none)" field is gone; weapon skills live
  on the Skillchain page.
- **Camp mapping** is shown on the Camp page: tank/puller/kiter/melee at tank camp;
  support/healers, GEO/BRD and ranged at support.
- Text/fit follow-ups: wider nav labels, split camp/debuff/formation text, larger diagrams.

## Unreleased — tenant-aware pages and text/fit fixes

- The server team payload now carries each character's main/sub job, levels and job abilities.
  The hub uses that context for the selected tenant instead of the local character.
- Roster shows the full team with jobs and levels; the selected tenant's header role comes from its
  roster assignment (Fivedough shows Tank, not the local box's Support).
- Healing, Buffs, Support and Debuffs are tenant/job specific. Buffs list only the tenant's job
  spells/abilities; Support shows only GEO for a GEO or Bard for a BRD; Debuffs list only the
  tenant's enfeebling spells.
- Text fit: Import party label/hint shortened and wrapped, formation notes split, camp hint split,
  debuff hint split, larger formation preview/full melee names, and a 14 px skillchain diagram with
  shorter MB text.

## Unreleased — server-owned team profiles and per-character instructions

- **Team rules live on the server.** New `/api/v1/battle/team` GET/PUT endpoints store one Battle
  profile per character in the account family. The server verifies family access, stamps each
  revision, and every client polls/applies its own profile.
- **Central editor.** The hub header has an EDITING selector; choose any team character to load
  their server profile into every tab. This box pauses while editing another character. Save writes
  that profile to the server; the remote box applies it on its next poll. Hide cancels.
- **Run/stop instruction.** A profile carries `engine.running`; the remote box starts or stops its
  Battle engine when it applies an updated profile. The header shows Start on box / Stop on box
  while editing remotely.
- The launcher passes the API endpoint/token to local and remote clients; `scripts/linux_boxes.py`
  does the same for the Linux boxes.

## Unreleased — movable Battle HUD and follow-me

- **Movable, closable Battle HUD.** The old fixed camp-radar drawing is now an ImGui window with
  a title bar, close X, resize and saved position. The Camp page has a show switch to reopen it.
- **`//hud move` covers it.** The global HUD move mode now includes the Battle HUD; Done or
  `//hud save` saves the layout, and `//hud move reset` centers it.
- **Battle menu on the HUD.** Start, Stop and Follow me buttons. Follow me stops Battle on the
  current box, asks the launcher to stop Battle on the other running boxes, and sends
  `//follow me all`, so the team follows without a warp.

## Unreleased — party jobs, controls, buff/heal exclusions, Geo subtarget and skillchain styles

- **Party jobs fixed.** The roster's job table was shifted by one (RDM showed as BLM, PLD as THF,
  GEO as SCH). `JOB_ABBR` now has the correct zero-based `NONE` entry.
- **Yalm controls.** Camp/support radius, pull leash and search range, formation spacing, kite
  radius and Geo cast range use a visible `-  value  +  yalms` stepper; the value box is editable.
- **Puller switch moved.** The old Engage "50% HP" field is gone; Pulling now labels its target-HP
  field "when the puller starts looking for the next mob".
- **Buff wizard and exclusions.** Buffs are chosen from known buff spells and known job abilities
  (with Search and Common buffs), then each buff gets per-member exclusions. Everyone starts
  included; checking a name excludes them from that buff only.
- **Healing exclusions.** Excluded players are skipped by the cure/status watcher. A silenced
  excluded player gets Silena so a self-curing PLD can cure again; an emergency cure still applies
  at the emergency threshold.
- **Geo without camp running.** Geo- is cast on the tank/anchor by subtarget, centering the bubble
  in the tank camp while the GEO stays at support. The Support page sets the anchor and cast range;
  the Camp page shows the camp span and Geo coverage warning.
- **Skillchain styles.** Make-a-chain, no-chain/spam, add/remove steps (up to 12), infinite/repeat
  with a link goal, and a larger diagram. `Diamond Aspis` keeps the window at 10 s.
- Five local black headless test windows were my test boxes; they were closed.

## Unreleased — skillchain planner

- **A Skillchain page in the Battle hub.** Set a focus chain, the opener and up to three closers
  with their weapon skills, and the Magic Burst casters/spells. The page validates the sequence
  with the reference transition table and shows a step diagram with each formed chain and MB
  window.
- **Diamond Aspis timing.** A closer wearing the shield keeps the skillchain/MB window at 10 s;
  the window is detected automatically for the local character and can be set manually for other
  rows. Normal windows are 9/8/7 s after each link.
- The server-side skillchain/Magic Burst runtime is still unwired; the page is a planner and
  window calculator, marked as such in the UI.

## Unreleased — tank/support camps, team rally and GEO/BRD support

- **Two camps.** Tank camp holds the mob, puller and melee formation; support camp holds healers,
  GEO/BRD, support and ranged. Role movement now sends support and ranged to the support camp and
  tank/melee/puller to the tank camp; an unset support camp falls back to the tank camp. The camp
  radar and hub map draw both rings, and the hub warns when they are more than 20 yalms apart.
- **Bring the boxes together.** `//battle rally` sends `//warp all me`, `//battle invite` sends
  `//invite subs`, and `//battle import` fills unassigned roster names by job. The Camp and Roster
  pages and the launcher's Battle page have the same buttons. The group was tested live with the
  five local sub-accounts: all six zoned to the main character, joined the party, and split into
  their tank and support camps.
- **GEO camp loop.** At support the GEO keeps the configured Indi- aura; at tank it parks the
  Luopan, casts the configured Geo- on it, and returns. Both spells and intervals are configurable
  on a new Support page.
- **BRD camp cycle.** Tank set: Victory March, Valor Minuet V, Blade Madrigal. Support set: Mages
  Ballad III, Advancing March. Pianissimo carries Sentinels Scherzo on the tank and Mages Ballad III
  on support; Nitro means Nightingale + Troubadour and defaults to the tank set. The bard moves
  between camps for each set.

## Unreleased — puller mob list and explicit healing scope

- **The puller can be limited to named mobs.** The Pulling page (and launcher Battle page) lists the
  live mobs nearby with their distance from camp; click names to allow only those, type a name to
  add one, or leave the list empty for any mob. `//battle pull mob add|remove <name>` and
  `pull mob clear` edit the list from chat.
- **Puller search distance** is a separate yalm setting measured from camp
  (`//battle pull distance <n>`); the puller will not travel past it.
- **Healing scope is explicit:** **Party only** or **Party + alliance**. Party + alliance observes
  both groups; alliance status icons still are not sent to the client, so -na/Erase remain party-only.

## Unreleased — Battle hub focus, camp radar and readable controls

- **The Battle hub clears the screen while it is open.** Action windows and Battle/Party Info step
  aside without changing their saved switches, then return when the hub closes.
- **A camp radar stays up during play.** With the hub closed and a camp set, the lower-left CAMP
  panel shows the radius, player heading, target, inside/outside state and distance. The client's
  world camera is shader-driven and not exposed by the addon host, so this replaces the unreliable
  ground-projected ring as the in-play camp view; the hub keeps the large top-down map.
- **Numbers are readable.** Camp radius, switch-at-HP, arc, spacing and the other bounded fields
  are drag boxes with the value and units in the box instead of narrow `+/-` steppers.
- **The formation rule has a picture.** The Engage page draws the mob, the tank and the numbered
  melee slots for the current style/arc/spacing, with example slots when no melee is assigned.
- `camp set there` previews through the hub's camp map; the arrow keys nudge and Enter applies.

## Unreleased — spell tiles show their line and rank

- **A ranked spell keeps its line's art and grows a corner rank badge.** The client's menu icon
  for Aero II, Cure III or Blizzaga II is only a Roman numeral, so the Spells window drew a grid
  of nearly identical numeral tiles. The addon now resolves the unranked spell (`Aero`, `Cure`,
  `Blizzaga`) with `res.spell_by_name`, draws that icon and shrinks the Roman rank into a small
  dark badge at the icon's top-right; a tier-I spell has no badge, so a rank changes only the
  badge. If the line art is missing from the DAT the original numeral tile is still the fallback.
  Trusts keep their portrait even when the name ends in `II`.
- **Duplicate spell labels are gone.** The old four-letter rule put different spells on the same
  name: Aero II and Aeroga II both read `AERO2`, Blizzard/Blizzaga both `BLIZZ`, Thunder/Thundaga
  both `THUND`, and Stone/Stonega/Stoneskin all `STONE`. Spell labels now keep the line half plus
  a one-letter suffix (`-ga` G, `-ra` R, `-ja` J) and append the Arabic rank, so the window reads
  `AERO2`/`AEROG2`, `BLIZZ`/`BLIZG`/`BLIZR`/`BLIZJ`, `THUND`/`THUNG`, `STONE`/`STONG`/`STNSK`.
  Every distinct spell name gets a unique label of at most seven characters, and the narrow-tile
  fallback keeps the line and rank too. A name the client repeats (its two Sleepga records) is
  folded into one tile because the HUD casts by name. Trust labels use the same rules but not the
  spell-line suffixes (Nashmeira stays `NASHM`), which also separates the Unity versions
  (`ALDO`/`ALDOU`).
- Tests: `tests/spell_names_test.py` extracts the marked label block from `control.lua` and checks
  all 928 spell names, the line/rank cases and the Trust exceptions, using lupa or the vendored
  LuaJIT and skipping when neither is available.

## Unreleased — the Zoning spell page

- **The spell hub has a Zoning page.** Warp, Warp II, Escape, Retrace, the Teleport-\* family and
  the Recall-\* family were sorted into Buff or Nuke by their magic skill (Divine or Enhancing);
  they now group under **Zoning** ahead of Avatar and Other. The group order and tab label are in
  `control.lua`, so a custom grouping can still move individual spells. Tile labels keep the
  destination half (`T-HOLL`, `T-DEM`, `R-PASH`, ...) instead of clipping every Teleport-\* to
  `TELEP` and every Recall-\* to `RECAL`.
- **Saved `//warp` places ride on the same page.** The launcher looks the character's marks up
  through the server API and pushes `{slot, alias, zone_name}` rows through the `hud` command;
  the addon draws them as tiles with the Warp icon. A click runs `//warp me <slot>`, and the
  launcher refreshes the list on its poll and whenever the Warps page edits a mark. Marks are not
  saved into the HUD file, so the server's table remains the only copy.
- **Docs and tests:** `docs/control-panel.md` describes the page and the new `warp_marks` field;
  the launcher's TypeScript check covers the type, and the Lua is parsed with the addon corpus.

## Unreleased — the Battle hub and automation

- **`//battle` is now the Battle hub.** It opens a per-character ImGui window with roster
  assignment (tank, puller, kiter, support, melee, ranged), camps with a ground ring and
  mouse/arrow placement, a claim-aware engage gate, a tank-anchored melee formation, pull and
  sleep/bind rules, cure/status/healing rules, buffs, enfeebles, dispel, priority ordering,
  death handling, kiting and saved profiles. It runs the same client commands a player types and
  drives the game's own auto-run, so the client keeps its cast bars, recasts, collision and
  packets. `//battleinfo` (and `//info`) still open the old statistics window.
- **Profiles save as JSON under `<data>/battle/<character>/`.** `//battle save` with no name
  creates the requested `<zone> <timestamp>` save; the hub and a new launcher **Battle** page
  edit the same file through the control port's `battle` command. Every rule is stored, including
  the loot policy; this server has no item drops or treasure pool yet, so lotting is not sent.
- **The client's camera matrices are read for the ground ring.** Reading the game's view and
  projection transforms and applying them as column vectors puts the player at the screen centre
  on a live client (the host's own addon drawing uses the row-vector form), which is what makes
  `//battle camp set there` follow the mouse and draw the circle on the floor.
- **Tests:** `tests/battle_hub_test.sh` exercises all hub tabs against a mock ImGui API;
  `tests/chat_complete_test.c` covers the new command's completion; the launcher TypeScript and
  Rust checks cover the control-port bridge.

## Unreleased — spell results read the midcast set

- **A Cure's amount is rolled when the cast finishes, not when the action packet arrives.**
  GearSwap's order is fast-cast set before the action and the midcast set immediately after
  it.  The server computed the amount in `cast_magic`, before that midcast `0x050` burst, so
  a RDM's `sets.midcast.Cure` (Daybreak + Telchine Gloves) was never in the stat sheet the
  heal read: Cure III stayed at 237 instead of 331 with 40% `"Cure" potency`.  `resolve_casting`
  now re-reads the amount from the gear worn at the finish, and the same pass updates a
  nuke's magic damage, an enfeeble's Macc / duration / potency and Drain/Aspir's amount, so
  every midcast set does what its name says.
- Regression test: `server/tests/test_world.py::WorldTest::test_cure_potency_reads_the_gear_worn_at_the_finish`.

## Unreleased — en-spells deal (and draw) their damage

- **An en-spell now adds its elemental damage to every landed swing and the client is told
  about it.** The buff icon already went up, but no melee path read it, so a Red Mage with
  Enfire did exactly the sword's damage and no second number appeared.  Each melee result now
  carries the 0x028 additional-effect block: the element as the proc kind, the extra damage
  as the value and message 229, which is the "additional points of damage" line the client
  prints and colours.  The damage also comes off the monster's HP, can finish the target, and
  counts when the round decides whether the next swing still has something to hit.
- **The base is the current Enhancing Magic curve, not a flat number.**  BG-wiki's formula:
  `skill / 9 + 5` below 180 and `(skill - 180) / 8 + 25` from 180 up, so 440 skill is 57 and
  500 is 65.  Tier I freezes that at cast; tier II recalculates it each round and adds a
  hidden counter that rises by one per proc up to double the base (65 -> 130), then keeps
  rising past the cap so a later skill change is not lost.  Recasting replaces the old
  en-spell and resets the counter.  Enlight/Endark use Divine/Dark Magic skill, decay by one
  per hit, and their remaining charge is also the Attack/Accuracy they grant.
- **The lines that do and do not apply are retail's.**  "Sword enhancement spell damage"+n
  from gear and the RDM group 2 "En-spell damage" merit join the base; the weapon-only line
  applies just to its own hand; Composure triples the six elemental en-spells; the target's
  elemental Magic Evasion and Magic Damage Taken reduce it.  Magic Attack Bonus, Magic
  Defense Bonus and the Magic Damage statistic do not, so a Sworn set's `Magic Damage+32`
  pieces do nothing for an en-spell while Enriching Sword's `+30` does.  Day/weather, staff
  and affinity, the tier II resistance debuff and the RDM job-point gift remain unmodelled.
- **The Sworn R30 suit's own en-spell rows were missing from the item data.**  Every piece
  prints "Sword enhancement spell damage" in its base stats (+8/+10/+7/+9/+7, 41 total), but
  the Limbus generator had no mapping for the phrase, so `item_mods` never got the rows and
  the suit that the RDM enspell mode wears added nothing per hit.  Migration `0134` backfills
  the five pieces and the generator now emits them for a fresh database.  The Oboro path C
  weapons' `+300%`/`+400%`/`+500%` lines are decoded from their augment blocks as well, so
  Crocea Mors, Vitiation Sword and Duelist's Sword multiply en-spell damage instead of
  silently dropping the row.

## Unreleased — typeahead in the chat line

- **`//` commands complete as they are typed, in the line itself.** `//invi` shows `te ` after the
  caret in a second colour and Tab, Enter or a typed space takes it, so `//invi subs` + Enter is
  `//invite subs` without a Tab; `//gs l` shows `ock `. A word with more than one match shows
  nothing, since there is nothing to assume. Neither does a word that can also be a free-text value
  (`//invite su`, `//warp ma`): the completion could be a player's name or a saved place, and the
  suggestion must stay something Enter is allowed to run. Tab still completes those words.
  The suggestion's colour is a chat font-colour slot: `//hint color <n>` picks it and
  `//hint colors` prints the slots with their numbers drawn in their own colours, so a quiet grey
  can be found. The typed text is untouched and stays the line's own white. The colour pair is
  kept immediately before the caret, because the input line does not apply a code that sits at
  the caret itself. The suggestion is part of the input line's text, in the chat log's
  own `0x1E`/`0x1F` colour pairs, so it is drawn with the game's font, at the game's position,
  with nothing anchored over the window. The caret stays at the end of the typed text and the
  suggestion is recomputed a frame after each key, so Backspace and the caret keys need no special
  handling; the line is only rewritten when the completion changes. `//hint off` stops it, `//hint`
  reports the state, and `tests/chat_complete_test.py` drives it against a stand-in text field.
- **`//help <command>` prints that command's syntax, arguments coloured.** The completion table now
  carries a usage line and a one-line description for every command it knows:
  `//help invite` prints `//invite [subs|all|team|<name>]: party your online sub team, or invite one
  player`, with the bracketed choice in the party colour and the `<...>` placeholders in the
  linkshell one (both are the chat font-colour slots, so the player's Menu > Font Colors decide
  the exact colours). A word the table does not know is left to the server, so `//help` alone still
  prints its full list.
- **`//hint probe` is the probe the typeahead was built on.** The input line was the one renderer
  whose handling of the chat colour pairs was unknown, so the probe parks a two-colour sample in
  the next line opened -- with the caret after `//invite `, so it also answers whether the line
  draws text past the caret at all. Two colours (orange and light blue at the time) settled the
  first; the whole sample showing settles the second. It stays for a client whose renderer
  differs.
- **`//doors` and `//mh` reach the server again.** Both were handled by `ZoneSession.command` but
  missing from the completion table, so `cmd.c` treated them as unknown commands. They are
  forwarded (and completed) now.

## Unreleased — retail doors, the drawbridge, and clean cast animations

- **The Port Bastok drawbridge stays down.** Its three moving entities (`_6ke` span,
  `_6ks`/`_6kt` gate ends) used to spawn closed (`animation 9`) and were then "opened" by the
  automatic-door helper as the player walked along the bridge, which left the whole span up.
  They now spawn lowered and the automatic mode never touches them. The old six-minute raise
  timer is gone too: it lifted the bridge with no airship to explain it, and the client drawbridge
  event (70) it started on a player standing on the deck could leave that player's camera stuck
  in the cutscene. A real airship arrival can raise and lower the three entities when the
  transport is implemented.
- **Doors are retail-manual again, with an opt-in automatic mode.** A normal door stays shut
  until the player targets it and presses action. `//doors auto on` restores the old
  walk-up-and-open behaviour, stored per character in `char_settings` and restricted to city and
  outdoor zones — dungeons keep manual doors even with the option on. `//doors` reports the mode;
  `//doors auto off` returns to retail. The zone flag is `zones.auto_open_doors` (migration 133,
  from LandSandBoat's zone type data).
- **A spell's Magic Start now carries the spell's own animation and the client's start line.**
  Every cast start was sent with animation 0 and message 0, so the client began the cast with its
  default (Cure's) pose and only switched to the right animation at the finish; Trust calls showed
  it most clearly. The start now carries the spell's client animation (939 for every Trust),
  message 327 for a player and 3 for a monster or Trust, and the server no longer writes a
  second "You start casting" line. The finish still carries the same animation id.

## Unreleased — the HUD can be moved in game

- **`//hud move` starts a drag mode without the launcher.** Every visible window grows its
  title bar (`Spells (40) - drag to move`) and the two hubs get the same accent outline, so they
  can be dragged where they belong. An opaque **Done** box is drawn in the middle of the screen
  above every window; clicking it saves all six positions and leaves the mode, and `//hud save`
  does the same from chat. The box stays on top even while another window is being dragged.
- **`//hud move reset` recovers a layout made for another resolution.** It parks all six windows
  (abilities, spells, trusts, weapon skills, Battle Info and Party Info) in the middle of the
  back buffer and then starts drag mode. A window saved at a coordinate outside the current
  resolution is brought back where it can be seen and grabbed instead of staying invisible. A
  window that is switched off at reset time keeps its pending middle position and lands there
  when it is switched on. `//hud off` (and Ctrl+H) leaves move mode because there would be no
  Done box left to click. The control port exposes the same mode as `hud {edit: true}` and the
  reset as `hud {center_positions: true}`.

## Unreleased — the team keeps up after a warp

- **A stationary character now refreshes its position for late observers.** Another client
  only learns where a player stands from the `0x00D` the movement handler broadcasts, so a
  player who stops sends nothing. A box that zoned in while the leader walked — and was
  still loading when those packets went by — kept the copy it spawned with at the warp
  anchor. `follow_status` then said `close` with the leader eight yalms away, and the box
  stood still until the leader happened to move again; that is the "10 seconds to a minute
  before they respond" after `//warp all me`. Every stationary, zone-loaded session now
  broadcasts a position refresh once a second to the clients that have it spawned.
  Measured with the leader walked during the boxes' load: all five converged and followed
  with no further leader movement, 8–15 s after the stop — the remaining time is the
  client's own zone-load tail, not the server hand-off.
- **The hand-off itself is not the delay.** A real same-zone `//warp all me` measured:
  command → `0x00B` sent at once, boxes report `login 0` 0.5–1.2 s later, and all five are
  back in world 4.0–4.6 s after the command. The rest is the client drawing the new zone;
  a cross-zone warp loads new assets and takes longer, but the refresh above means the
  followers no longer wait for a second leader move after that load.
- A regression test (`server/tests/test_presence.py`,
  `test_a_stationary_player_refreshes_its_position`) pins the refresh and its
  moving-player suppression.

## Unreleased — RDM cure, duration and enspell modes

- **RDM has dedicated midcast sets for Cure potency, Enhancing duration, and enspells.** The
  library now carries `sets.midcast.Cure` (Daybreak, Telchine Gloves, the cure cape and Jann's
  Ring), `sets.midcast.EnhancingDuration` (Telchine Alluvion augments, Vitiation Tabard, Atrophy
  Gloves, Lethargy Houseaux and Embla Sash), `sets.midcast.EnhancingSkill` (the Enhancing Magic
  Skill / MND build) and its `sets.midcast.Enspell` alias. A new `sets.engaged.Enspell` uses the
  Sworn R30 suit for on-hit enspell damage while the buff is up.
- **`sets.midcast.CureHP` is the HP-stable cure set for percentage auto-heal rules.** It uses
  the Sworn body, the max-HP neck and rings, Daybreak and Jann's Ring: 36% cure potency with a
  max HP slightly above `sets.idle.maxhp`.  The max-potency `sets.midcast.Cure` is about 190 HP
  below the max-HP idle build, so an auto-heal that swaps into it, cures to the smaller pool and
  then returns to the larger idle set can cross its threshold again and loop.  Point Curing →
  Potency at `CureHP` when idling in max HP gear; the gear sets and the auto-heal rule are both
  covered in `gearswap/README.md`.
- **Enspells are their own spell-mode group.** The Spells panel now has an **Enspells** card
  between Enhancing and Curing; the host maps Enfire/Enblizzard/Enaero/Enstone/Enthunder/Enwater
  (and their IIs) to it before the Enhancing Magic fallback, so `//modes enspells damage` works
  and the HUD gets a sixth mode button. The RDM library's cure category now points at
  `midcast.Cure`, the duration mode at `midcast.EnhancingDuration`, and the enspell mode at
  `midcast.Enspell` automatically when those sets exist. The new Enspells group needs the rebuilt
  host64/addon loaded by the client; the existing client keeps using the old addon until it is
  restarted.
- **The seven Gain-* spell tiles are distinguishable again.** They all share their first five
  letters, so the old HUD fallback clipped every one to `GAIN-`. The spell HUD now keeps the stat
  suffix (`G-STR`, `G-DEX`, `G-VIT`, `G-AGI`, `G-INT`, `G-MND`, `G-CHR`) and uses `G` + the
  suffix as the narrow 4-letter fallback.
- **RDM job-point spells reach the spell hub and HUD.** The client stores their level as a
  sentinel (100/550/1200) and names the jobs that can learn them in `job_point_mask`, so the
  level-only `job_spells` filter dropped them. A level-99 main job now includes them:
  Distract III, Frazzle III, Addle II, Refresh III, Temper II and Fire/Blizzard/Aero/Stone/
  Thunder/Water V. They also join the phase category rules (enfeebles, enhancing and nuking).
  The spell HUD, the launcher's per-spell list and the group cards all read the same command.
- **The spell HUD keeps a target mode for each tab.** Heal and Buff default to STPC, Debuff and
  Nuke default to Selected. The `Tgt:` button at the start of the spell mode strip cycles the
  active tab through Selected (`<t>`, or `<me>` when none), STNPC (`<stnpc>`) and STPC (`<stpc>`),
  and each tab's choice is saved per character. STPC opens the party sub-target cursor, where Tab
  walks the party; STNPC opens the NPC cursor. The description is a fixed caption under the
  `Tgt:` control rather than a cursor-following tooltip. The control port can set one tab with
  `hud {type: "spells", target: "stnpc", target_tab: "Debuff"}` or several with a `targets` map.
- **Party-target buffs and heals now land on the selected member.** The server used to throw
  away the 0x01A action target for every non-enemy spell and self-cast. It now resolves the
  selected party member from the sub-target targid and applies the buff or heal to that
  session. Refresh III was also seeded as a self-only 0-MP stub; it now has self/party
  targeting, 80 MP and a 5 s cast. Distract III, Frazzle III, Addle II and Temper II data were
  corrected alongside it. Temper II remains self-only by design.

- **GearSwap phase settings now live in the game database.** The launcher used to keep the whole
  phase config (spell modes, category overrides, per-spell/WS/JA overrides and state sets) only in
  the WebView's localStorage, so a fresh launcher profile lost changes made in the HUD. A
  `gearswap_settings` row per account now hydrates the localStorage cache during bootstrap, the
  Gear page writes it back after a debounce, and in-game `//modes` changes are folded back through
  `phase_status`. An existing localStorage config is migrated on the first signed-in bootstrap.

- **Self-centered `-ga`/`-ra` buffs now reach the party.** Hastega, Protectra and Shellra are
  marked target-self with an area shape in the client data, so the server used to apply them only
  to the caster; Hastega also lacked its Haste mods. The server now spreads those buffs to live
  party members inside the spell's area, with a per-recipient gain-effect action, and carries the
  Protect/Shell/Haste stat mods.

## Unreleased — a quiet zone no longer times the client out

- **FFXI-4001 was the server saying nothing, not the network dropping.** A zone session only
  sends a packet when something happens: a mob moves, a party vital changes, a player walks
  past, chat arrives. A character standing still in a quiet city therefore heard nothing from
  the server, and the client calls ninety seconds of silence a dead link and exits with
  `FFXI-4001 No response from the FINAL FANTASY XI server`. Measured on the main client: last
  zone packet at 22:58:14, error dialog at 22:59:44, while the client's own `0x015` updates
  arrived about once a second the whole time and stayed unacknowledged. It hit every client
  the same way — the five Linux boxes standing in Bastok Mines dropped within minutes of
  logging in — which is why it looked like a network problem and why a relaunch only bought
  another few minutes.
- **Every idle session now gets a keepalive.** Five seconds after the last packet to a
  logged-in session, the gateway queues a General-only `0x00D` (HP, MP and TP; no model or
  name block, so the client does not reset the entity or drop its drawn-weapon pose), and it
  acknowledges the client's stream on the way out. The sleeping heartbeat already used the
  same packet. The idle character that used to die at ninety seconds now stays in the world
  for the one-hour soak, and the Linux boxes need no special case: the keepalive is per
  session on the server.
- **A regression test covers the quiet case.** `server/tests/test_keepalive.py` checks that an
  idle in-world session gets exactly one General-only `0x00D`, that recent traffic and a
  zoning or logged-out session suppress it, and that it repeats only after the interval.
  [Protocol](docs/protocol.md#4-zone-udp) and [world](docs/world.md#recovering-a-dropped-client)
  describe the timer it resets.

## Unreleased — Gear set stats in the launcher

- **The Manage tab shows each item's real stats and the set's totals.** The set detail's slot cards
  now print the client's own item tooltip (base stats) alongside the GearSwap augment lines, and a
  new **Set totals** panel under the EquipViewer sums every numeric stat with flat and percent
  values kept separate. The descriptions come from the running client through the control port's
  `lua` command, so no server restart or host64 rebuild is needed. Conditional `Set:`/`Pet:`/`Unity
  Ranking:` lines are omitted from the cards and never total; an item the client does not know
  keeps its augment lines and their totals. See
  [the Gear section](docs/launcher.md#gear-and-gearswap).
- **The Sets tab now shows the server's checkparam sheet.** Under the EquipViewer, **Live set
  stats** is a compact **Stat | Total** table: Attack, Accuracy, Defense, Evasion, HP/MP, the seven
  attributes and the combat modifiers, with no per-item columns. The totals come from the live game
  session rather than a second tooltip sum, so they include gear and augments, food, job traits (JT),
  job abilities (JA), job points, buffs and merits — the same numbers `combat_mods()` feeds to
  `stat_sheet()`. Clicking a stat opens a full-window sheet with every source behind it: each
  equipped item, the food, each trait/ability/buff and the base/skill rows; the contributions add
  up to the exact total, and food/Attack percentages and fractional-rounding lines are explicit.
  The server's new read-only `GET /characters/<id>/stats` builds the report from the live zone
  session (it needs the server restarted, not host64 rebuilt). The Manage tab keeps the client
  tooltip/augment **Set totals** for library sets. `gear_stats` tests still pin the tooltip/augment
  split; `test_stat_report` pins the live report's totals and source rows.
- **The live sheet keeps polling while the launcher is in the background.** macOS WebKit reports
  the window as hidden as soon as another app (the game) is frontmost, so the stat poll skipped
  every tick while the player swapped gear; the table sat at "updated 5m ago" until the launcher
  was clicked, even though the server's report had already changed. The stat poll and the
  EquipViewer's gear/job poll now run every two seconds regardless of focus, and both refresh
  immediately on `focus`/`visibilitychange`.

## Unreleased — the team recovers itself after a dropped client

- **FFXI-4001 no longer needs a manual relaunch.** `scripts/watchdog.py` watches the main
  client and the sub-account boxes through their control ports. A client that had been in
  the world and is now on the error dialog (`login_status 0` with the OK menu) has the
  dialog dismissed, is relaunched with a fresh launch token, is driven back into a zone,
  and then the party is re-invited and the follow graph is re-applied. A missing main
  client is restarted the same way; per-client cooldowns keep a network that is still down
  from becoming a relaunch loop. `--once` does a single sweep, `--dry-run` reports what it
  would recover, and `--relaunch-exit` also restarts a box whose control port died after
  it was in the world.
- **Covering the game window no longer freezes the main client.** The Metal backend
  acquired a drawable with `nextDrawable` even while the window was covered, hidden or
  minimized; Core Animation then blocks for about a second per frame (or forever), which
  freezes the game loop and with it the zone connection. Covering the window while reading
  chat was enough to produce FFXI-4001 on the main while the headless boxes stayed online.
  The renderer now skips presenting while the window cannot be seen and keeps the world
  ticking at about 60 Hz; the first visible frame draws normally.
- **The zone socket heals itself.** A long-lived UDP socket can stop receiving after a
  route/interface flap while a fresh socket on the same port answers normally; the server
  then looks like every client went silent at once. When clients are online and no
  datagram has arrived for a few heartbeats, the gateway rebinds the zone socket, and a
  transient `recvfrom` error rebinds instead of killing the zone thread. The rebind is
  logged (`zone socket heard nothing ... rebinding`) so a path problem stays visible.
- **A silent zone session is kept for three minutes instead of one**, so a short network
  or scheduler stall no longer removes the character, its party slot and its follow state
  out from under the client.
- The zone server's idle grace is documented in [protocol](docs/protocol.md) and
  [world](docs/world.md); the watchdog is documented there too.

## Unreleased — the boxes copy the leader's exact path

- **Followers replay the path instead of chasing a point behind the leader.** The follow
  controller used to aim at a spot 0.8 x the spacing behind the leader's *current* position, so a
  corner sent the box diagonally across the inside of the turn and into the wall on the far side.
  It now records the leader's path at frame rate — a waypoint every 8 cm — and walks those
  waypoints in order with a cursor, so it takes every turn the leader took. A pass test covers a
  30 fps client stepping over a 15 cm waypoint between frames, a jump over eight yalms (zone
  change, warp, teleport) starts a fresh path, and the stop gap is still 0.8 x the spacing behind
  the leader's newest point.
- **Measured in a 60 fps replay of a right-angle run:** maximum deviation from the leader's path
  fell from 0.150 to 0.046 yalms, the closest approach to the corner from 0.184 to 0.083 yalms,
  and the default one-yalm spacing still settled at a 0.85-yalm gap.
- `follow_status` now also reports `points`, `cursor` and `goal` so a stalled cursor is visible
  from the launcher.
- **The clients must be rebuilt for this** (`host64` and `host64-headless`): the controller is
  embedded in the binary. The `FFXI_ADDONS_LUA=<folder>` override loads `control.lua` from disk
  for a quick trial without a rebuild.

## Unreleased — the boxes follow their leader through a zone line

- **A zone line now moves the whole box team.** A client only sends `0x05E` for its own character,
  so a following box usually never crossed a line: the leader zoned and the subs were left standing
  in the old zone. When the main account crosses an authored line, Fanxi collects the online sub
  sessions standing in the old zone and hands each one the same `0x00B` the leader got, so their
  clients run the same zone-in for the same destination. Every box is handed its `0x00B` on the
  next tick rather than one per few seconds: with the hand-off fixes below, five clients
  reconnecting together no longer cost a box its zone (measured live: the team is in the new zone
  in 4.5 s instead of 11.8 s with a first-load gate). A box that did walk through the line with the
  follow controller has already arrived, so its queued move is dropped.
- **Only the main account leads, and only boxes in the leader's zone are moved.** A sub that
  crosses a line alone zones by itself, a parked (`//sleep`) box stays parked, and another
  account's character is never dragged along. Followers get `"<leader> leads you into <zone>."`
  in their chat.
- Tests: `server/tests/test_zone_follow.py` (the destination and the batch hand-out, a box in
  another zone, a single box, a box that zoned itself, a sub crossing alone, another account, and
  the leader zoning with no boxes).

## Unreleased — Prime Weapon Aftermath

- **Melee and ranged Prime weapons now grant their retail aftermath.** Using a Prime
  weapon's own weapon skill raises the physical damage limit (PDL) by 2-8% at stage 3,
  4-10% at stage 4, or 6-12% at stage 5, scaling linearly with the TP spent. The tier and
  duration are banded: 1,000-1,999 TP gives 60 s, 2,000-2,999 gives 120 s, and 3,000 gives
  180 s. The bonus is on the sheet before the activating skill's first hit, so the skill
  that grants it already gets it; it then applies to auto-attacks and later weapon skills.
  TP Bonus and Fencer do not change the aftermath, and the buff is removed when a
  main/sub/ranged weapon actually changes or comes off, matching retail. Staff and club use
  different aftermath effects whose full 1,000/2,000-TP values are not published, so they
  keep their normal damage for now.
- **A re-sent weapon no longer clears the Prime Aftermath.** The phase engine sends every
  slot of a set, including the main and sub weapons that are already worn. Every 0x050 for
  those slots used to count as a weapon change, so the aftermath from Blitz (Spalirisos)
  or any other Prime skill vanished on the follow-up TP set about a second after it was
  granted. The equip handler now compares the packet against the copy already in the slot:
  re-wearing the same weapon is a no-op, while a real swap or unequip still clears the
  buff.
- Tests: `server/tests/test_weapon_skills.py` (`test_prime_aftermath_*`, the potency/tier
  and overwrite tables, the activating-hit check, TP Bonus, wrong-skill and weapon-swap
  cases, and `test_blitz_aftermath_survives_a_gear_burst_that_re_wears_the_weapon`).

## Unreleased — zoning and `//warp call` survive a dropped hand-off

- **A box no longer parks on "Downloading" after a warp.** Each `0x00B` moves the client's
  zone cipher on by 2. When a hand-off was dropped, the next login reset the key to the
  account's sign-in key, which the client could never open again: it re-sent `0x00A` every
  two seconds forever and only a relaunch recovered it. The server now keeps the whole key
  sequence for a character, sends the zone-in under every key in it (the client opens the
  one it holds and drops the rest), and resumes the sequence when the same client relogs.
  A restarted client (new game session) still starts from the sign-in key.
- **A second warp while one is loading is deferred, not stacked.** A `//warp call` or the
  launcher's auto-warp arriving mid-hand-off used to send another `0x00B`, advancing the
  key again. The move is kept and applied once the client acknowledges the zone; a
  duplicate call to the same spot is dropped.
- **A live session replaced by a new login keeps its key sequence.** A box that was already
  in the world and reconnected (a new `0x00A` from a fresh socket) had its sequence
  discarded because it was not mid-hand-off; the replacement login then reset to the
  sign-in key and looped. Any session now parks its sequence when it is replaced, and the
  same game session resumes it.
- **The launcher arms auto-warp only when the server roster says the box is gone.** A normal
  zone change drops the client's own status to 0 for a poll or two while the server still
  has the session; arming on that pulled the same box again every time it came back — a
  re-zone loop every 15 seconds. A pull inside the 90-second cooldown now drops the arm
  instead of holding it for a delayed surprise warp.
- **A team-wide arm is not auto-pulled at all.** A server restart or a batch relaunch arms
  every box at once; the launcher then sent five `//warp call` commands inside one second,
  and five simultaneous zone changes lost a box mid-hand-off. More than one armed box now
  clears the arms and leaves the team alone.
- **The team zones in parallel.** `//warp all me` (and a zone line's followers) sends every
  ready box its own `0x00B` in one tick instead of one every three seconds. Measured live:
  five boxes from command to all-in-world in 8.3 s, the first at 4.2 s; the same five sent
  as five direct zone commands took 4.5 s with warm assets, against ~19 s with the old
  three-second hand-out. The remaining time is each client loading its own zone data; the
  server no longer serializes it. A first-load "warm one, then release the rest" gate was
  measured at 11.8 s and not used: it serialized a load the clients can overlap.
- **A no-op warp is skipped only after the client reports its own position.** The old
  shortcut trusted the server's idea of a box's position, which can be the anchor it was
  sent to while the client actually landed on the zone's spawn point; it then skipped the
  very `//warp all me` that would have corrected it. Warps now always go out until the
  client sends a position packet, after which a warp to the spot it reports is a true
  no-op. This also stops a repeated `//warp all me` from reloading boxes already on the
  leader: two commands in Bastok Mines produced zero zone-outs. Tests:
  `test_a_no_op_warp_is_skipped_only_after_the_client_reports_its_position`.
- **A teleport brings the whole team.** Only zone lines used to move the boxes; a survival
  guide, home point, warp spell or warp item moved the leader alone. Any zone change by a
  main character now hands the online family boxes the same destination (scripted group
  warps and a sub's own moves do not cascade). Measured live: five boxes followed a
  leader's zone change in 5.1-8.4 s with no command. Tests:
  `test_a_main_teleport_brings_the_family_boxes`,
  `test_a_sub_teleport_does_not_move_the_main`.
- **A box that is still logging in joins the team's last warp by itself.** `//warp all me`
  can only move sessions that exist; a box whose client is still starting lands at its
  saved spot when it finishes, and only a second command moved it — the 45-second "it
  finally went" report. The command now leaves an anchor for 60 s and any family box that
  finishes its zone-in within that window is pulled to it automatically. Tests:
  `test_a_box_still_logging_in_joins_the_team_anchor_when_it_arrives`.
- **A relaunch waits for the old control port instead of racing it.** The helper gave the
  dead client 6 s to release its port; a slower one left the replacement with no control
  port (`opened but did not answer`) and needed another restart. It now waits up to 30 s
  and skips the box with a clear message instead of starting an uncontrollable client.
- **A parked key sequence is never shortened.** When a replacement login was dropped too,
  parking its one sign-in key overwrote the longer sequence of the hand-off it replaced. The
  server then kept sending the zone-in under a key the client had already advanced past, so
  the box retried forever. Parking now merges with the entry from the last ten minutes.
- **A box keeps its hand-off when another box takes its old UDP port.** Box clients on one
  host open sockets for the new zone from the same local port range, so one box's `0x00A`
  can arrive on the address another box just released. The old port was treated as a
  recycled address and the parked hand-off there was evicted — that box lost its advanced
  key and its party slot while it was still loading. A session that is mid-hand-off is now
  left in place (the new login simply owns the address), and its own `0x00A` continues it.
- **A fresh login still gets a dropped hand-off's keys as extra copies.** A relaunch creates
  a new game session, so the hash check cannot resume the sequence; the client the player did
  not restart still holds the advanced key. Those keys now ride along as additional sealed
  copies while the sign-in key stays primary, so whichever key the client holds opens one.
- Tests: `server/tests/test_presence.py` (zone-in copies, relog resume, live-session
  replacement, deferred change, the stolen-port hand-off, the merged sequence, the relaunch
  copies).

## Unreleased — the weapon-skill HUD tells the two RS skills apart

- **Rudra's Storm and Ruthless Stroke both read `RS`.** A two-word name whose first word is
  longer than six letters falls back to its initials, so the dagger page of the weapon-skill
  window showed the same two-letter label on two tiles. The HUD's label table now names that
  pair: `RSTRM` for Rudra's Storm and `RSTRK` for Ruthless Stroke, and the three-letter
  fallback a narrow tile uses keeps the half that differs (`STM` / `STK`). Energy Steal and
  Energy Drain still share `ENERGY`, and Final Heaven and Final Paradise share `FINAL`, for
  the same reason.

## Unreleased — `//job` changes a box's job by name

- **`//job` can target another character on the account.** `//job <character> <job> <sub>` runs
  the same gear-aware swap on that online character instead of the sender: the old outfit is
  slipped, its job store and cape pulls run against the target's own bags/slips/locker, the new
  job's bundle is sent to its client, and its bags are tidied. `//job war nin` still changes you,
  and `//job Threedough sam war` changes Threedough: the word count is the rule, so two words
  stay the self form. The name is resolved on the server and must be in the sender's account
  family (the main plus its sub-accounts). The caller gets one line (`Threedough is now
  SAM/WAR.`) while the target's chat keeps the store/pull/tidy detail; the party roster is
  re-sent to every member so the leader's party window shows the new pair, and a parked
  (`//sleep`) box is refused with "wake it first", as `//warp call` does. Tests:
  `server/tests/test_job_command.py`.
- **A `//job` change now re-locks the new outfit.** The old lock was cleared (retail) but the new
  look was never locked, and other clients only re-read a player's models when the entity spawns,
  so a box could keep wearing the previous job's clothing — Twodough still looked like a Scholar
  after a remote job change. `//job` now snapshots the gear it just dressed into the style-lock
  columns, sends message 267 with a fresh `0x051`, and respawns the character for nearby clients
  (`0x00D`) so every window draws the new look. The Moogles' Change Job menu keeps retail's
  lock-off behavior. Tests: `test_job_change_clears_the_old_lock_and_locks_the_new_outfit`,
  `test_observers_respawn_the_character_with_the_locked_outfit` in
  `server/tests/test_job_command.py`.

## Unreleased — GearSwap loads on the Linux boxes

- **The gear library was read on the client from the launcher's own path.** The Gear window sent
  `gearswap {path}` and `phase {path}` with a macOS path such as
  `/Users/wondochoung/Documents/GitHub/fanxi/gearswap/SCH.lua`, and an attached Linux box tried to
  open it on its own filesystem: **Load SCH defaults**, **Import .lua** and every auto-swap push
  failed with `cannot read /Users/...`. The launcher now reads the library itself and sends its text
  (`gearswap {path, source}`, `phase {path, source}`); `path` only names the library in errors and
  in the window. A caller on the same machine may still send the path alone, and the host parses it
  with the same sandbox either way.
- **A job change re-pushes the plan from the launcher's own poll**, not only from the Gear page, so
  a box on another machine — which cannot read the next job's file itself — gets the new job's
  library too.
- Tests: `launcher-rs/src-tauri/src/control.rs` (the request carries `source` beside `path`) and
  `launcher-rs/src-tauri/src/commands.rs` (the library is read where the launcher can see it).

## Unreleased — Prime weapons keep their afterglow

- **The final Prime weapons were drawing an auraless look.** Every Prime weapon has two
  client models: the `Non AG` weapon used by stages 2-4, and the `Stage 5` model, which is
  the same weapon DAT followed by the client's `aura` particle block. That block is the
  afterglow (the purple glow), and it is the same one the Relic/Mythic/Empyrean/Aeonic
  iLvl 119 forms already get from their `119 AG` models. The 119 III Prime rows were still
  on the Non AG ids (Mpu Gandring 907, Laphria 911, Dokoku 914, ...), on the relic MId
  LandSandBoat stores (Caliburnus 545 = Excalibur, Kusanagi 514 = Masamune, Lorg Mor 553 =
  Mjollnir), or on 0 (Pinaka, Earp, Loughnashade, Duban), so equipping them drew no glow.
  Migration 125 puts the sixteen final forms on their Stage 5 ids (918-928, 474, 151-153,
  676) and stages 2-4 on the matching Non AG ids (907-917, 475, 148-150, 675). The model
  set is pinned in `tools/gen_item_models.py` and `tools/item_models.json` so a
  regeneration keeps it.
- **A saved style lock kept the old look.** The lock stores model ids, so Onedough's main
  (907, the old auraless Mpu Gandring) is retargeted to 918; otherwise `/lockstyle` would
  keep drawing the dagger without the aura. A deliberate lock of the stage 2-4 look on any
  other character is left alone.
- The evidence is the client's own model table and DATs: the Stage 5 ROM/376 files carry
  the `aura`/`fr00`/`gp00`/`pi1`/`flmy` chunks and are the same weapon bytes as the Non AG
  files plus that block. Tests: `server/tests/test_item_models.py`
  (`test_prime_weapons_use_their_stage_five_afterglow_model`).

## Unreleased — the equipment menu shows the element orbs

- **The eight element icons under Attack/Defense read 0 no matter what was worn.** They are
  not drawn from the client's item data: they are the `def_elem[8]` block at body `0x30` of
  the `0x061` status packet, and Fanxi left it zeroed. `char_stats()` now fills it from the
  character's elemental magic evasion (`FIRE_MEVA`..`DARK_MEVA`, `item_mods` 15-22 — the
  `Fire+20` line on a tooltip), after gear, augments, traits, job points, buffs and food are
  merged into one modifier dict. Fire Belt's Ice+20 Water-20 and Demon's Ring +1's Light-20
  Dark+13 now total in the menu the way the tooltips read; values are signed, so a piece
  that lowers an element shows a negative orb.

## Unreleased — Dancer spends TP and stacks Daze

- **Curing Waltz is no longer a free max-HP heal.** The old handler restored
  `8-11%` of the Dancer's maximum HP, ignored TP and had no target; Curing Waltz V in
  particular read like a second Benediction.  Waltzes now spend their retail TP cost
  (200/350/500/650/800 for Curing I-V, 400/800 for Divine, 200 for Healing) and restore
  `floor((caster CHR + target VIT) * M + B + 2 * Waltz Potency ranks)` HP, capped at the
  target's missing HP.  A subbed Dancer halves `M`.  Curing and Healing Waltz target the
  party member the client selected; Divine Waltz heals the party in a 10-yalm radius.
  The heal goes out as a job-ability result, so both clients see the number.
- **Steps use the real Daze families and are recast-only.** Quickstep now applies
  Lethargic Daze (flat Evasion Down), Box Step Sluggish Daze (Defense Down%), Stutter
  Step Weakened Daze (Magic Evasion Down) and Feather Step Bewildered Daze (Critical Hit
  Evasion Down).  They cost no TP and need no combat stance, stack from level 1 to 10
  (5 for a subbed Dancer), extend their own timer by 30 s per step, and grant 2 Finishing
  Moves for a Dancer main.  Presto adds four levels and four moves.
- **Finishing Moves and flourishes follow retail costs.** The count now lives in the
  power of Finishing Move 1, so a fully job-pointed Dancer can hold 9.  Animated
  Flourish gives volatile enmity instead of damage, Desperate Flourish applies Weight,
  Violent Flourish hits and can Stun, Reverse Flourish converts up to five moves into
  TP, Building Flourish stores 1-3 moves and feeds the next weapon skill, and Wild
  Flourish costs two moves.  Trance waives dance TP costs and grants its job-point TP;
  Contradance doubles and discounts the next waltz; Saber Dance blocks waltzes and Fan
  Dance blocks sambas.
- **Sambas and jigs are no longer free status icons.** Drain/Aspir Samba cost 100 TP and
  restore HP/MP from landed hits, Haste Samba costs 350 TP and adds 5% Haste, and the
  samba/jig durations use their job-point rows.  Spectral Jig and Chocobo Jig put up
  Sneak/Invisible and Quickening respectively.
- **The ability HUD greys out TP-costed Dancer abilities.** A waltz or samba whose
  effective TP cost is above the current TP is drawn dim with a red border, its tooltip
  says how much TP it needs, and clicking it is ignored; once TP covers the cost the icon
  returns to normal and clicks.  Recast-only steps and jigs keep the normal icon and the
  cooldown clock.  The effective cost subtracts "Waltz TP Cost" gear (LandSandBoat
  `waltz_cost` mod 139; migration 130 adds Desultor Tassets' -50 TP), Trance's free-dance
  window and Contradance's job-point discount.  The HUD mirrors the server's cost table;
  a future TP-cost item needs both entries.
- The Dancer data and formulas live in `server/fanxi_server/game/dancer.py`; the HUD
  gating is in `host/addons/lua/control.lua`; regression tests in
  `server/tests/test_dancer.py` drive the real 0x01A handler.

## Unreleased — a job change forgets the style lock

- **A job change now clears the locked appearance, not just the flag.** Style lock was turned
  off server-side but its saved models stayed in `characters.style_*`.  The client keeps its
  own copy of the flag and re-asserts it whenever it logs in or zones (`C2S 0x053` mode 1), so
  the next zone switched the lock back on with the previous job's clothing — a Dancer wearing
  the Scholar's outfit.  The Moogles' Change Job and `//job` now zero those models, and send
  the client's "Style lock mode disabled." line (message 268) when the lock was on.
  `/lockstyle off` forgets the saved look too.  Migration 122 drops the leftover models from
  older saves.
- **`/lockstyle on` works again after the two sides disagree.** The client sends the "continue"
  packet (mode 1) rather than the enable (mode 4) once it believes the lock is on, so treating
  mode 1 as a no-op left the command doing nothing forever: the server had the lock off, the
  client kept saying it was on, and every retype sent only the packet that was ignored.  Mode 1
  now locks what the character is wearing.  It still cannot resurrect an old outfit, because
  turning the lock off (or changing job) has already cleared the stored models, so the test
  for the Dancer case now asserts the new job's models are locked instead of the old job's.
  The raw `0x053` packet is logged for any mode that is not a plain continue (and for a
  continue that carries flags), which is what showed the mismatch in the first place.
  Tests: `test_keepalive_locks_the_worn_appearance_when_the_server_has_none`,
  `test_a_keepalive_after_a_job_change_locks_the_new_outfit_not_the_old` in
  `server/tests/test_style_emotes.py`.

## Unreleased — Gleti's Knife wears its own model

- **Gleti's Knife was drawing Kannagi's katana.** LandSandBoat's item data gives the
  dagger MId 513, which is Kannagi's model — `ROM/247/27.DAT` in the main slot, a `weap`
  model with texture `weap010` — so it hung on the hip as a katana, grip and all. The
  client's own model table (`xi-tools`' `mv/lists/characters.json`, built from the
  race/slot groups and FTABLE) puts Gleti's Knife at **877** for every race: on Hume
  female that is `ROM/366/48.DAT` (main) and `ROM/368/40.DAT` (sub), both `knif` models
  with texture `knif_bs0`. Migration 121 sets `items.model` and `item_models` to 877;
  `gen_item_models.py` pins the same number so a regeneration keeps it. Mpu Gandring's
  907 was already right (the same table's "Mpu Gandring (Non AG)", `ROM/375/9.DAT`).
  Onedough's style lock had saved the old pair (907/513), so migration 123 retargets that
  locked sub to 877; a relog shows the corrected locked look. Re-equip the knife or zone
  for the live look when the lock is off.

## Unreleased — orphaned sessions and one-click reconcile

- **`//warp all me` moves the team instead of only reporting success.** A same-zone warp used a
  self `0x00D` position update; the client treats its own position as authoritative and ignored
  it, so every box stayed put while the server said "Warped N characters". Warps now always use
  the `0x00B` hand-off, including inside one zone, and a team is handed in one box at a time: five
  clients reconnecting together could leave one looping on its zone-in. The launcher sends the
  legacy `/!warp` forwarding form so an older headless client without `warp` in its completion
  table still runs the server command.
- **The launcher now checks the server's live zone roster.** A client that outlives a server
  restart keeps answering its control port and can still report `login_status` 2, so the Control
  room used to show a green row while `/sea`, invites and `//warp` saw nobody. Each poll compares
  the row with `GET /api/v1/world/online` (the same roster `/sea all` reads), marks the mismatch
  **orphaned**, and disables Invite / Warp for it.
- **Reconcile.** One row's button relaunches that client; **Reconcile N** restarts every stale box
  with a fresh launch token (remote boxes through `linux_boxes.py restart --only`, locals through
  the normal path) and pulls each back to the leader once it is in world.
- **Local clients are adopted after a launcher restart.** The launcher deliberately leaves
  `host64` running when its window closes; the next run now discovers those processes by their
  control port instead of losing their rows.
- **`/status` counts live zone sessions**, not `game_sessions` rows that survive a server restart,
  while the game gateway is attached. The new authenticated `GET /world/online` is the same
  roster and reports `gateway: false` on an API-only server.
- **The Control room has the HUD master switch.** Per-window switches keep their state while the
  master is off, so turning on Abilities/Spells alone used to change nothing visible; the new
  **Show HUD** switch is the same one `//hud` and Ctrl+H use.

## Unreleased — retail /attack off

- **`/attack off` now always ends the engagement.** The server used to swallow a single
  press while the target stood outside melee reach, and because each swallow re-armed a
  1.5-second window, pressing it again seconds later was swallowed too — an engagement
  the player could not drop.  The handler follows retail now: every press disengages, at
  any distance; only the client's own range-drop packet is absorbed, exactly once per
  engagement, and the allowance never re-arms.  `/attack` also draws at any distance
  (the 30-yalm leash ends the fight instead of refusing the engage), the first swing
  comes 3 s after the draw, and the leash message is retail's "You lose sight of the
  target."

## Unreleased — complete category coverage

- **All 220 job-point category rows are now represented.** The last RUN row
  (Rune Enchantment Effect) is a state/modifier.  Remaining limitations are simulation
  depth, not unclassified JP rows; see `docs/remaining.md`.

## Unreleased — last job rows

- Wyvern breath, COR Bust Evasion/Optimal Range/Ammo, PUP Heady Artifice, SCH
  Stratagem IV, GEO Life Cycle/Indicolure duration and pet/support rows are wired.
- One row remains: RUN Rune Enchantment, which has no rune-enchantment state to attach
  to.

## Unreleased — Charm, bar spells and parry

- Beastmaster **Charm** now converts a mob into a pet using its model/name, with the
  Charm Success Rate job-point chance; **Run Wild** boosts the active pet.
- WHM Bar Spell Effect is a passive Magic Defense row; Ninja Tactical Parry adds Counter.

## Unreleased — PUP burden and GEO pulse

- Puppetmaster Activate/Cooldown/Deactivate now maintain a pet burden value; Geomancer
  Concentric Pulse deals its job-point-scaled direct damage.

## Unreleased — remaining job statuses and utility

- WAR Retaliation/Restraint, MNK Inner Strength, BLM Mana Wall, PLD Sentinel/Palisade,
  DRK Blood Weapon/Soul Enslavement/Nether Void, RNG Double Shot/Decoy Shot and
  Shadowbind, COR Wild Card/Random Deal/Cutting Cards/Triple Shot/Quick Draw,
  PUP Tactical Switch/Deus Ex recast, GEO Bolster/Blaze of Glory, RUN Elemental
  Sforzo/Swordplay/Embolden/Odyllic Subterfuge/Swipe/Vivacious Pulse, and THF
  Mug/Despoil/Steal recast/Larceny/Bully are wired.

## Unreleased — pet support, BLU points and DNC rows

- Pet job-point rows now feed pet HP/accuracy/damage/delay; Reward/Repair/Spirit Link
  heal the pet, Elemental Siphon/Mana Cede restore MP, and Blood Pact Rage/Ward act
  through the avatar.
- Blue Magic Point Bonus and Unbridled Wisdom are wired at the data/status layer.
- Dancer Jig Duration and Flourish I/II/III rows now feed their abilities.

## Unreleased — Quick Magic, Caper and Modus

- **Blue Magic Point Bonus** and **Unbridled Wisdom** are wired at the data/status layer;
  **DNC Jig Duration and Flourish I/II/III** rows now feed their abilities.

- **Red Mage Quick Magic** procs at 5% plus the job-point row and finishes the cast
  immediately.
- **SCH Caper Emissarius** heals by its base plus job-point percentage; **Modus Veritas**
  adds its bonus to an existing damage-over-time tick.
- **BLU Unbridled Learning II** runs 120 s and Physical Blue Magic Effect Accuracy is a
  passive accuracy row.

## Unreleased — Dancer

- **Dancer steps build Finishing Moves** and apply their debuffs; Step Duration extends
  the moves.  Animated/Reverse/Building Flourish consume a move for damage, TP or a
  status; No Foot Rise grants three moves; Spectral Jig grants Sneak/Invisible.
- Trance, Grand Pas, Saber Dance, Fan Dance and Contradance put up their statuses.

## Unreleased — Sublimation and instant abilities

- **Scholar Sublimation** toggles, stores 1 MP per tick (draining 1 HP), caps at the
  job-point-extended 360 MP, and releases the stored MP on the second use even during
  recast.  Verified in the client.
- **Shield Bash, Eagle Eye Shot and Weapon Bash** now apply their job-point-scaled direct
  damage to the current target.

## Unreleased — Bard songs

- **Bard songs now apply to the party** instead of only the caster, with their family
  status icons and per-tier values: Minne (Defense), Minuet/Mambo (Attack), Madrigal
  (Accuracy), March (Haste), Ballad (Refresh), Paeon (Regen), Requiem (DoT), Prelude
  (Ranged Accuracy) and Carol (Magic Defense).
- Minne/Minuet job-point potency and Song Accuracy are wired; Valor Minuet was verified
  in the client.

## Unreleased — Bard support and DNC sambas

- Bard **Soul Voice** and **Pianissimo** now put their statuses up and add their
  job-point Fast Cast rows; Song Accuracy is a passive magic-accuracy row.
- Dancer **Drain/Aspir/Haste Samba** now show their status icons with the 100 s
  job-point duration row.  Step/jig/flourish jobs are still separate work.

## Unreleased — Corsair rolls

- **Fourteen Corsair rolls show their status icon and apply their rolled modifier.**
  Snake Eye forces an 11, Double-Up increments the active roll, Fold removes it, and the
  Phantom Roll Duration job-point row extends the roll to 100 s.  `docs/rolls.md` lists
  the implemented rolls and the remaining COR systems.

## Unreleased — pet foundation

- **BST/DRG/PUP pets can be called and rendered.** Call Beast, Call Wyvern and Activate
  spawn a Tiger familiar, wyvern or automaton using the retail pet models; Release,
  Dismiss and Deactivate remove it.  Fight/Sic/Ready, Heel and Stay set its state, and
  the pet follows its owner and attacks the owner's engaged target.
- Pets use the Trust spawnable packet path, with the pet flag set and the spawnable
  name/model block fixed so the client draws them.
- Pet HP/accuracy/attack read the relevant job-point rows for BST, DRG and PUP.
- **Summoner avatars** spawn from the Summon spells using the retail Pet_* models; they
  follow and auto-attack like the other pets.  Carbuncle and Ifrit are verified in the
  client.  Astral Flow/Blood Pact and the rest of the Summoner kit are separate work.
- Other pet systems (charm, Reward, Ready/Sic damage, wyvern breath, automaton
  frames/attachments) are not built yet; see `docs/pets.md`.

## Unreleased — a crowded zone no longer floods the client

- **Entity movement is now ambient traffic with a budget.** The server queued a position
  update for every monster in view on every tick. In a dense zone (King Ranperres Tomb
  has 55 spawns within 60 yalms of the arrival point) that was several kilobytes a
  second printed into the session's FIFO, against a client built for roughly 3 kB/s.
  The client's receive loop fell behind, which is what made a job ability pressed in the
  middle of the stream appear a minute later. Only the newest position per entity is kept
  now, real events (actions, status, chat, equipment) are packed before the entity
  stream, and the stream itself is capped by a 900 B/s token bucket
  (`AMBIENT_BYTES_PER_SECOND` in `game/zone.py`). On the King Ranperres Tomb bench the
  downlink fell from ~1.4 kB/s to ~0.4-0.8 kB/s depending on how many mobs are walking.
- **Monsters are interpolated, not re-sent every tick.** The client walks an entity from
  the `moving` flag and the speed byte in its `0x00E`, so the packet is a correction, not
  the animation. A walker now carries speed byte 12 and is corrected four times a second
  (`MOB_SYNC_INTERVAL`); a chasing runner carries 36 and is corrected every 100 ms
  (`MOB_SYNC_INTERVAL_RUN`). A real corner (about 45 degrees walking, 22 running) and
  every stop go out immediately, but only within `MOB_URGENT_RANGE` (30 yalms); a distant
  corner waits for the ambient budget. Steady movement beyond `MOB_SYNC_RANGE` (45 yalms)
  is not streamed at all, though spawns still reach 60. The nav/roam layer made all 55
  in-range spawns walk, which is why the old per-tick stream only became a problem now.
- **The zone loop flushes on a timer.** `flush()` only ran when the UDP socket timed out,
  and one busy box kept the socket readable, so the other boxes' queues never drained.
  It now also runs every `FLUSH_INTERVAL` (200 ms), one packet per session, and a packet
  with nothing to say is not sent at all.
- **A retransmit no longer holds back a fresh reply.** A GearSwap batch sends its
  equipment packets before the server's answer arrives, so the old "resend the last
  packet until it is acknowledged" path fired for every packet of the batch and the
  queue stood still. A retry is limited to once per 250 ms and is skipped while real
  events are waiting.

## Unreleased — job-point gifts and passive category stats

- **Every job's static job-point layer is live.** `data/job_points.json` now carries the
  BG-wiki table for all 22 jobs (10 categories and 61 gift rows each). Gift Attack,
  Defense, Accuracy, Evasion, Magic Attack/Defense/Accuracy/Evasion, Magic Damage, Cure
  Potency, Regen, Fast Cast, Subtle Blow, Double/Triple Attack, Martial Arts, Counter,
  Critical hit/damage, Weapon Skill Damage, Skillchain, Fencer, Store TP, Dual Wield and
  skill bonuses all feed `combat_mods()` or `skills.caps_for()` at 2,100 JP spent.
- **Passive category rows are applied at rank 20.** WHM Regen Duration and Magic
  Accuracy; BLM Magic Damage and Magic Accuracy; RDM Magic Attack, Magic Accuracy,
  Enhancing and Enfeebling Duration; BLU/GEO Magic Accuracy; GEO Magic Attack; PUP
  Martial Arts; COR Ranged Accuracy; NIN Ninjutsu Accuracy.  The two new flat-duration
  modifiers feed the enhancing and enfeebling duration formulas.
- **SCH Light Arts** remains the separately handled conditional example: its +3 s/rank
  is already in the Regen duration formula.  Dark Arts adds its Helix duration, and
  Stratagem Effects I/II/III add M.Acc, Fast Cast and Magic Damage while the matching
  stratagem icon is up.
- **Magic Burst gifts and categories** now feed the capped Magic Burst bonus (BLM/SCH),
  and Enlight/Endark, Azure Lore, Burst Affinity, Unbridled Learning and Spirit Surge
  have their conditional stat rows.
- **NIN Ninjutsu Cast Time/Elemental Ninjutsu**, **MNK Perfect Counter/Footwork/
  Counterstance**, **SAM Konzen-ittai**, and **SAM Meditate TP** are now applied.
- **A generic ability-category layer** now maps 114 category rows to their client status
  ids (`data/job_ability_status.json`) and parses their plain stat/duration/recast text.
  This covers the remaining simple rows for PLD, DRK, THF, SAM, NIN, DRG, BLU, COR, DNC,
  GEO, RUN and others.  Pet/avatar/automaton, chance/rate/potency and song rows are
  deliberately left off and counted in `docs/job-points.md` (125 rows).
- **Non-Scholar conditional rows** now have their ability statuses: WAR Mighty Strikes/
  Brazen Rush/Berserk/Defender/Warcry/Aggressor; MNK Hundred Fists/Dodge/Focus/Impetus;
  WHM Asylum/Divine Seal/Afflatus Solace/Misery/Sacrosanctity; BLM Manafont/Subtle
  Sorcery/Elemental Seal/Manawell; RDM Chainspell/Stymie/Composure/Saboteur.  Convert
  restores 20% max HP, Tabula Rasa 40% max MP, Chakra +200 HP and Curing Waltz +40 from
  their job-point rows.
- `docs/job-points.md` lists the remaining ability-conditional categories and the gift
  rows that are flags/systems rather than stats (Capacity Points, Superior, new spells,
  pet/avatar/automaton bonuses, etc.).

## Unreleased — job point Light Arts duration

- **The maxed Job Point block now feeds Regen duration.** The client already sends every
  job-point category at rank 20, but the duration formula was still passed
  `light_arts_jp_rank=0`. The Light Arts Effect rank now contributes its +3 s per rank
  (+60 s) before the enhancing-duration and Perpetuance multipliers. With the full
  Regen_Duration set, Regen V goes from 10:51 to **15:40** under Light Arts and from
  12:47 to **17:36** under Tabula Rasa.
- `job_points_detail` and the duration call now share one `JOB_POINT_RANK` constant, so the
  menu's 20/20 and the formula cannot disagree again.

## Unreleased — monsters respect walls and cliffs

- **Monsters can no longer walk through zone geometry.** The server reads the zone's collision
  mesh from the player's own FINAL FANTASY XI folder (`FANXI_GAME_DIR`), rasterises its floors
  into a walkable grid and keeps walls, cliffs and fences as barriers. Roam legs and chase paths
  are planned with A* on that grid, the monster's `y` follows the floor under it, and a step off
  the mesh or up a cliff face is refused.
- **Aggro and swings need a walkable line.** A player on a ledge, a bridge deck or the far side of
  a wall is no longer noticed or hit through the geometry. A monster with no route stops at the
  last reachable point instead of climbing the wall.
- **The grid is built once and cached** under `data/nav/<zone>.nav`, with the source model's size
  and mtime in the header. Building starts in the background on zone-in; `python3 -m fanxi_server
  nav --zone N` (or `--all`) prebuilds it. `FANXI_NAV=0` disables the layer, and zones whose
  interiors live in separate sub-region files keep the old movement with a four-yalm vertical
  guard.

## Unreleased — a stuck box is visible, relaunchable and pulled back

- **The Control room no longer calls a dead session "online".** `state.login_status` is the only
  signal that counts (0 no character block, 1 logging in or zoning, 2 in world). A box whose zone
  session died — a server restart, a silent UDP drop on a remote host — keeps its process, its
  control port and its last zone, so the green row and the **Warp team to me** button promised a
  character the server did not have. The row now reads **logged out** (or `zoning`), keeps the
  uptime badge only for the ones that are actually in world, and holds back the actions that need
  a character (**Invite**, **Warp team to me**).
- **A logged-out row has a Relaunch button.** An attached Linux box is restarted through the same
  helper that started it (`linux_boxes.py restart --only <id>`, same tunnel port, so the launcher
  adopts it again); a local client is stopped and launched again through the normal token path.
- **A box that comes back is warped to the leader by itself.** The launcher arms the warp when a
  client goes from 2 to 0, or when Relaunch is pressed, and sends `//warp call <name>` from the
  main account's in-game client once that account has reported 2 for two 3 s polls. Only the
  returning box moves; a team already in place is not teleported again. A box that was never in
  world this session is not armed, so a normal Launch still starts where the character stands.
- **`//warp call <name>` is the one-box form of `//warp all me`.** The name is resolved on the
  server (`session_by_name`), so a box in another zone — or one whose client has not drawn the
  leader yet — still answers; `call all` is the whole team. It only moves characters on your own
  account family, and a parked (`//sleep`) box is refused with "wake it first" instead of being
  sent a zone-in its client would never acknowledge.
- **`//warp all`, `//warp all me` and `//invite subs` skip parked boxes.** A sleeping client only
  parses chat, so the zone-in/position packet was dropped and the session stayed `zoning` for good,
  which is how a `//sleep` plus a team warp used to wedge a box. Wake it first.

## Unreleased — the combat HUD stays visible around the launcher

- **A menu or chat line no longer hides the HUD while the game window is out of focus.** The
  layout editor's **Done** now leaves the windows on screen, and `//hud on` shows them as soon as
  the player is back in the game. The hide applies only while the game has keyboard focus.
- **An open but empty chat line no longer counts as typing.** The HUD steps aside once text is
  entered, not merely because the game kept the input line open in the background.
- **Addons can ask `xi.ui.focused()`** whether the game window has keyboard focus; the control
  port's `state` also reports `focused` and `chat_open`.

## Unreleased — the launcher chooses the game window

- **Settings has a Game window card.** Pick Windowed, Borderless window, Full screen or
  Borderless full screen; type a width × height or use **Fit this display** and the presets that
  fit the primary monitor's usable area; and set the interface scale (menu resolution) that keeps
  the UI legible on large displays.
- **The choice is applied to every visible client.** The launcher writes the five display keys
  to `display.reg` in its data folder and passes it to `host64` as `--reg-final`, which is loaded
  after the game's saved registry. The game folder is never touched; a running client keeps its
  window until it is relaunched.

## Unreleased — `//` commands

- **Fanxi commands are now typed with two slashes.** `//warp`, `//job`, `//gs`, `//follow`,
  `//modes`, `//hud`, `//sleep` and the rest replace the old `/!` spelling and share the host's
  `//` console namespace (`//addon`, `//lua` and `//exec` are unchanged). A known `//command` is
  forwarded to the server as its `!command` say line, so the wire format and the saved-warp data
  do not change; an unknown `//` line is still a local error and never chat. The old `/!...` and
  bare `!...` spellings keep working for saved macros.
- **Docs, Tab completion, the launcher and the server's help all show `//`.** `//wa` + Tab still
  completes `//warp `, and `//w` is still left alone. `runtime.json` is bumped so the launcher
  rebuilds the client host with the new addon.

## Unreleased — /sea finds online players

- **The search port is bound.** The lobby has always advertised `54002` as the search address,
  but nothing listened there, so `/sea all` and `/sea <name>` failed before they left the
  client. The gateway now runs a TCP search service on that port using the client's own
  encrypted search packet format.
- **Results come from the live zone sessions.** `/sea twodough` matches names by
  case-insensitive prefix and `/sea all` lists the online roster; each result carries the
  character's current area, job, level, race, nation, rank and 20-bit id. A name search
  ignores the area condition the client adds from its own current location, so
  `/sea twodough` finds the character in another zone too. A character stops appearing when
  it logs out, and its area is the session's zone rather than a stale database row. Sleeping
  boxes (`//sleep`) remain listed because they are still logged in.
- **The rest of the search window is still out of scope:** search comments, linkshell ranks,
  friend-list refreshes, party search and auction-house requests are ignored, and the result
  id is the low 20 bits of Fanxi's content id.

## Unreleased — Ctrl+H hides the whole HUD

- **One key clears every Fanxi HUD window.** `//hud on|off|toggle` drives a master switch over the
  four action windows, Battle Info, Party Info and the native FPS readout; Ctrl+H does the same,
  with the chat line open or closed. The six per-window switches keep their state, so showing the
  HUD again restores exactly what was visible. The master switch is saved with the character's HUD
  file and exposed as `show_hud` on the control port and in `metrics.hud`. `runtime.json` is bumped
  so the launcher rebuilds the client host with the new addon.
- **Menus and chat now hide every HUD window, not just the right-hand ones.** The menu-hide switch
  used to skip windows on the left half, so only the abilities panel stepped aside; now all four
  action windows and both hubs hide together. The chat line is treated as a menu too. Combat still
  keeps the menu hide suppressed, but the chat line hides the HUD there as well.

## Unreleased — Oboro weapon augments on the Data page

- **The Data page has a dedicated Oboro card.** It lists every Dynamis-Divergence
  crafted JSE weapon family at NQ (R15), HQ1 (R20) and HQ2 (R25), shows whether a
  copy is in a bag and which path/rank it already carries, and caps Path A, B or C
  in one click. An item that is not in a bag can be bought into the first free
  inventory slot from the same card, then capped; a live client gets `//reload`.
- **The card uses the client's real bundle rows.** `data/oboro_r25.json` and
  `server/fanxi_server/game/oboro.py` table all 22 families (66 item/quality
  entries, bundles 1-198) with the same 24-byte `AugmentBundle` block Odyssey and
  Limbus use: rank 15/20/25, tier 0/1/2, RP curve A and the family's bundle.
  Path C is job-specific; HQ2 Paths A and B add the weapon's DMG row.
- **Oboro augments feed the stat sheet.** `augment_stats` reads the block through
  the merged registry: Musa Path C is `"Regen" potency +25`, `"Cure" potency
  +25%` and `"Fast Cast"+10%`; Path A turns on Store TP+25 and Path B Subtle
  Blow II+25. Chance-based rows (double damage, follow-up attack) are in the
  client table but not modelled yet.
- **Migration 120 retires Musa's static Path C rows.** It deletes the three
  temporary `item_mods` lines and stamps the real R25 Path C block (bundle 189)
  onto every existing Musa bag and locker copy, so the SCH Regen set keeps the
  same 25 flat HP/tick, 25% Cure potency and 10% Fast Cast.
- The generic RP card now excludes `kind = "oboro"` entries; the new card owns
  them. `tools/gen_oboro.py --check` keeps the data file, the docs page and the
  migration in step.

## Unreleased — zone changes complete the zone-in again

- **The zone key advance on `0x00B` is back.** The client does move its key on by 2 when
  it changes zones; the working tree had stopped doing it, so every zone-in was enciphered
  under a key the client had already left — it ignored the packet and retried its login
  every two seconds, which is the "Downloading" screen that never finishes. Only a fresh
  process (which starts from the account key again) got through.
- **A late packet from before the change no longer pins the old key.** A packet still in
  flight under the pre-change key used to flip the session back to it, undoing the advance
  before the zone-in went out. The server now keeps both ciphers and only follows the old
  one when the client's `0x00C` proves that is the key it is using.
- **A repeated `0x00A` before `0x00C` rebuilds the zone-in** under the next packet id and
  alternates both ciphers, instead of replaying the packet the client is already ignoring;
  after four tries the session is dropped and the next login starts fresh. Tests cover the
  advance, the in-flight packet, the `0x00C` follow, the rebuild and the give-up.

## Unreleased — spell mode groups

- **A spell group can hold both sets now.** The Gear page's Spells panel keeps a set for every
  mode in a group instead of releasing the other face when one is picked. The groups are
  Enfeebles (Macc / Duration), Enhancing (Potency / Duration), Curing (Potency / Cast time),
  Nuking (Magic Attack / Magic damage) and Helixes (Magic Attack / Duration).
- **A Mode dropdown arms the set the host wears.** The plan gives each spell one group and wears
  that group's armed mode; a missing set for the armed mode falls through to the midcast default.
  Per-spell cards still win over the group. Old configs with only category picks migrate to the
  one configured mode, or the group default when both were set.
- **The in-game spells HUD has one button per group.** Clicking cycles the armed mode and reports
  the new set in chat. `//modes` lists the armed modes, `//modes <group>` lists that group's
  modes, and `//modes <group> <mode>` arms one, e.g. `//modes enhancing duration` or
  `//modes enfeebles macc`. The host mirrors the armed modes in `phase_status`, so a `//modes`
  switch is folded back into the launcher config on the next poll.
- `job_spells` returns the group key in each spell's `categories` array; the host classifies
  Helix before Elemental Magic so a helix never takes the nuke set by accident.

## Unreleased — SCH Regen sets and mule gear clone

- **`gearswap/SCH.lua` carries the Community Scholar Guide's two Regen sets.**
  `sets.midcast.Regen_Potency` wears Musa Path C, Arbatel Bonnet +3, four
  Telchine pieces and Bookworm's Cape; `sets.midcast.Regen_Duration` wears four
  Telchine pieces, Arbatel Bracers +3 and Lugh's Cape. Every Telchine piece and
  Bookworm's carries both max lines: `"Regen" potency +10` and
  `Enh. Mag. eff. dur. +10`.
- **Migration 118 stocks Onedough's missing pieces.** It grants Musa, Khonsu,
  the five Telchine pieces, Embla Sash, Bookworm's Cape, and the Malignance and
  Mimir earrings, fills Musa Path C and Embla Sash, and skips anything already
  owned.
- **Migration 119 writes the two-line augment blocks and flat Regen math.**
  All five Telchine pieces and Bookworm's get `"Regen" potency +10` (id 0x173)
  and `Enh. Mag. eff. dur. +10%` (id 0x4E0) in the same 24-byte block. The flat
  `"Regen"` lines are now `REGEN_POTENCY` (spare id 1223), added after the
  percent multiplier and before the Light Arts bonus. With the potency set that
  is 75 flat HP/tick (Musa 25 + four Telchine 40 + Bookworm 10) plus Arbatel's
  25%, giving 149 HP/tick under Light Arts instead of a second percentage.
- **The clone tool now keeps the locker's per-copy augment block.** Migration
  116 added `char_locker.extra`, but `CHARACTER_TABLES` still copied only
  `(item_id, quantity, stored_at)`, so two capes of the same job collapsed into
  one row. The clone copies `extra` and has a regression test.
- **Twodough through Sixdough were refreshed from Onedough.** They now carry the
  same inventory, storage, locker, worn outfit and gear tables, including the new
  Regen pieces and all 282 locker cape builds.

## Unreleased — a returning main rejoins the team party

- **A main account that logs out, freezes or is force-relaunched no longer loses its team.**
  Logging out removes the main from the party and promotes a sub to leader; the subs stay grouped,
  so inviting them again was refused with "already in a party". On the main's next fresh login,
  Fanxi now finds the party made only of that account family, joins it and gives the main the lead
  back. The subs get one roster update; nothing is disbanded and nobody has to answer an invite.
- **`//invite subs` uses the same recovery first.** If the main is solo and the subs are still
  grouped, the command rejoins that party and takes the lead, then invites only the online subs
  that are missing. A second run is harmless.
- **Only family-only parties are touched.** If a friend joined the subs' party, recovery leaves it
  alone rather than demoting someone outside the team; a deliberate `/pcmd leave` followed by a
  zone line also does not re-add the main (recovery runs on a fresh login, not every zone change).
  `//invite subs` is the explicit way to take the party back.
- Tests cover rejoin-and-lead, the zoned-in roster copy, a party with an outsider, a sub login, an
  already-grouped main, and `//invite subs` rejoining and filling in a missing sub.

## Unreleased — one-click make party with your subs

- **The Party Info window has a Make party button.** It runs `//makeparty`, which takes every
  online sub-account out of whatever party it is in and invites it to the button's character.
  The subs accept automatically, so a half-broken team becomes one party in a click.
- **`//makeparty` is the chat form.** It is the destructive sibling of `//invite subs`: a sub in
  another party leaves it first instead of being skipped. The main must be the party leader.
- **Tab completion knows `//makeparty`.** `//makep` completes to `//makeparty `.

## Unreleased — Accession spreads the next white enhancing spell to the party

- **Accession + Regen V now lands on every party member in range.** The stratagem only put
  its icon on the bar; the next spell still resolved through the self-buff path, so the
  caster got Regen V and nobody else did. `cast_magic` now marks the cast, and
  `resolve_party_spell` applies the caster's rolled duration/tick/power to every live
  party member within Accession's ten-yalm radius — the whole box team when they are
  stacked. Each member gets its own gain-effect `0x028` result and `0x037`/`0x063` icon
  list, so a boxed client draws the buff without waiting for another party sync.
- **The stratagem is spent when the spell lands, not when the cast starts.** A cancelled
  cast leaves it up, and only a white enhancing spell consumes it: black enhancing spikes
  and the other spell schools leave the icon alone. Retail's Haste and Reraise exceptions
  are honoured as well.
- Tests: `test_effects` covers a two-character party, the out-of-range member, the
  no-Accession control and the Cure-does-not-spend case; all use real sessions and the
  real cast handler.

## Unreleased — persistent headless sleep/wake

- **Headless boxes are now parked, not stopped.** `//sleep` hides the character from every other
  client, despawns its Trusts, skips its world tick and stops processing movement/actions while
  keeping the process, UDP session, control port and tunnel alive. A 10-second status heartbeat
  keeps the client's connection from timing out. `//wake` restores the character in place; no new
  launch token, no process start and no zone reload.
- **Team page Sleep/Wake.** Each running box shows **Sleep**; a parked box shows **Sleeping** and
  **Wake**. The same **Launch headless** button now wakes a parked box instead of reporting it as
  already running. The sleeping flag is stored in the box registry, so it survives a launcher
  restart.
- **Stop means park for headless/remote boxes.** The Control room's Stop now sends `//sleep` for
  those instances instead of killing the process. Use **Force relaunch** when a process really
  needs to be replaced.
- Server tests cover hide/despawn, no sixty-second reap while sleeping, and wake restoring the
  same session/targid. Live test: slept Threedough for 65 seconds and woke it with no relog.

## Unreleased — force relaunch a stuck headless box

- **Force relaunch** on each Team box bypasses the in-memory "remote box operation is already
  running" guard. It kills the stuck `linux_boxes.py` helper, stops the tracked/remote/local
  session for that account, removes its registry row and tunnel, then starts a fresh client with a
  new launch token. This is the explicit escape hatch; normal launch keeps the healthy-client
  protections.
- The force path is deliberately allowed to stop a client that still answers `login_status == 2`
  for the selected account; the other accounts are untouched.

## Unreleased — conservative headless orphan cleanup

- **Every headless launch reaps orphans first, without killing a good client.** Local
  `host64`/`host64-headless` processes that are tracked by the launcher, visible (`host64`),
  alive on a control port with `login_status == 2`, or younger than 120 s are kept. Automatic
  cleanup is headless-only; a visible client is never reaped. Untracked processes that are older and
  no longer answer control are stopped, and registry entries whose tunnel has been dead or
  unanswered for 120 s are dropped so their ports are freed.
- **A launch attaches an account that is already in game** instead of stopping and restarting it.
  Per-box **Launch headless** returns the existing view; the team flow restarts only boxes that
  are not in game (`login_status == 2`), not merely boxes whose control socket answers.
- **Remote helper `reap`** protects every user in `~/.fanxi-linux-boxes.json` and stops only
  untracked `host64-headless` processes older than the grace period (120 s). It runs automatically
  at the start of `up`/`restart`; `--dry-run`, `--no-reap` and `--orphan-grace` are available for
  manual runs. A dry run against the live five boxes kept every tracked box.
- The `Stop` and targeted `restart --only` paths still stop the account the user explicitly asked
  to replace; only the automatic pre-launch cleanup is conservative.

## Unreleased — job changes refresh the combat HUD

- **The four HUD windows follow a job change without reopening them.** `//job` sends the new
  job block before the new outfit, and the client's `0x0AC` command list — the source of the
  Abilities and Weapon Skills windows — arrives only after the gear is on. The HUD rebuilt on
  the job number alone, so it kept the previous weapon's skills (after swapping back from WAR
  to SCH it still listed only `Combo`) until another job change. The rebuild signature now
  includes a fingerprint of the command list, so the lists rebuild again when the new weapon
  and its commands settle. The same path covers the Mog House Moogle's Change Job menu, which
  reaches `0x01B`/`0x0AC` through `0x0100` instead of the chat command.
- **Abilities that survive the rebuild keep their cooldown bars.** A rebuild is also a weapon
  swap, not only a job change; the timer moves to the new item key instead of being cleared.
- **The launcher sees the refreshed counts while the windows are hidden.** `metrics.hud` now
  checks the same signature on every snapshot, so a job change at the Moogle reaches the
  Control room even when no HUD frame is drawn.

## Unreleased — invite the whole team at once

- **`//invite subs` invites the whole box team in one command.** Also `//invite all` / `//invite team`.
  The server resolves the online sub-accounts in the inviter's family itself, so distance and zone
  do not matter; every sub accepts automatically. `//invite <name>` invites one online player from
  the server-side name list, and a non-family player still gets the normal prompt.
- **The Control room has an Invite button.** The **Live party** header's **Invite** opens a picker
  for the highlighted client: **Invite all online subs** runs `//invite subs`, and every other
  running character has its own **Invite** row. It uses the existing control command bridge, so no
  new backend path.
- **Tab completion knows `//invite`.** `//inv` completes to `//invite `, and `//invite su` to
  `//invite subs `.

## Unreleased — warp and zone hand-off hardening

- **Same-zone warps no longer zone.** `//warp all me` and the launcher's **Warp team to me**
  now send a position update (`0x00D`) when the team is already in the leader's zone, instead of
  `0x00B` + a full client zone-in. No reload, no login retry, and no dropped boxes: verified with
  all five remote boxes and the main, then nudged the leader and confirmed the boxes followed to
  the new position. `//warp me <slot>` and `//warp all <slot>` use the same fast path.
- **The zone-change window starts when the change is queued**, not at the client's last packet.
  An idle box that had not moved for minutes used to look like a stale hand-off and was reset to
  the base key; that was the root of the "two boxes drop after a warp" pattern.
- **A repeated `0x00A` re-sends the zone-in** instead of evicting the session that just logged in.
  This stops the two-second login-retry storm; the server also accepts `0x00C` when it arrives
  with sync 0, and follows the pre-zone key when the 2026 client keeps it. The 2025-07-03 key
  advance is no longer applied. Cross-zone warps still use the client's zone load; the launcher's
  team warp uses the no-reload path whenever the team is together.
- **Per-packet world ticks are capped at 30 Hz.** Every client packet used to run the full
  mob/trust/party/combat tick; six boxes at 30 fps meant ~180 full ticks a second during a fight.
  Movement packets still flush immediately, but the shared AI/event clock runs at most thirty
  times a second, which is above the client frame rate. This is the main combat/event headroom
  change behind the warp work.
- Tests: `test_presence` covers the idle window and the unchanged key; `test_warps` covers the
  same-zone teleport and the existing family warp.

## Unreleased — the multibox team runs on the Linux host

- **Launch headless team** on the Team page starts the main client on this Mac and restarts the
  five sub-account boxes on the configured Linux host. It stops local duplicates first, runs
  `scripts/linux_boxes.py` (mint launch tokens, start `host64-headless`, rebuild the ssh tunnels,
  wait for a zone), attaches the tunnels, and lands in the Control room with all six online.
- **Remote Linux host (SSH)** is a launcher setting. Once set, each box's **Launch headless** uses
  the same helper and leaves the Mac running only the main; with it empty the launcher keeps the
  local cleanup path.
- **Main and boxes share one game install.** `host64-headless` is rebuilt for the same
  **2026-10-05** build as the main client, and the helper points at `FFXI2026`; there is no
  2025-07-03 split. It kills the remote `host64` by account (the recorded pid was the `bash -c`
  wrapper), and a new `restart --only` action restarts just the selected boxes.
- **Optional 30 fps cap for the main client** (Settings) leaves headroom for the box pollers and
  the rest of the desktop; relaunch the main to apply. The five remote boxes measured ~0.3 core
  and ~764 MB total on the Linux host, so the Mac no longer pays for them.

## Unreleased — sub-account invitations accept themselves

- **Inviting one of your own sub-accounts no longer needs a click on the box.** When the invitee is
  a server-owned sub-account in the inviter's account family, the server applies the party or
  alliance invitation directly: the roster (`0x0C8`/`0x0DD`) arrives without a `0x0DC` prompt.
  A headless box has no UI to answer the prompt, and a windowed sub is still driven from the main
  account's launcher, so both accept the same way. A main account, or another player's character,
  keeps the normal prompt.
- **`FANXI_AUTO_ACCEPT_SUB_INVITES=0`** restores the prompt for every invitee when a server wants
  retail behaviour. The default is on.
- Tests: `test_party` covers a main inviting its sub, a sibling sub, an alliance invite, another
  player's sub, a main account, and the configuration switch.

## Unreleased — Tauri launcher becomes the launcher

- **The Python/Tkinter launcher is gone.** `launcher/` (the app, its tests and the `.app`
  packager) has been removed. `launcher-rs/` — the Rust + Tauri 2 app with a React front end — is
  the launcher, and `make launcher`, `scripts/launcher.sh`, `scripts/dev.sh`, `setup.command` and
  `install.sh` all run or build it.
- **Settings carry over.** `launcher.json` keeps its format, so accounts, characters, the game
  folder and the tenant selection survive the switch. `install.sh` records the checkout as
  `repo_root` so an installed `.app` can still find `tools/build_posix.py`.
- **CI and docs follow.** The Python workflow no longer runs launcher tests; the separate
  `launcher-rs` workflow type-checks the front end, runs the Rust tests and compiles the Tauri
  app. README, `docs/launcher.md`, `docs/development.md` and `docs/architecture.md` describe the
  Rust launcher.

## Unreleased — headless launch on every Team card

- **Each box card on the Team page has its own Launch headless button.** It starts just that
  sub-account with no visible game window, using the same headless launch path as the Control
  room's whole-party action. The launcher stays on Team so the next box can be started straight
  away, and the card's **In game** badge appends **· headless** while that client is windowless.
  A normal **Launch client** button sits beside it.
- **A launch clears the account's old processes first.** Before spawning, the launcher stops the
  instance it tracks, any local `host64`/`host64-headless` naming the account, and the remote box
  recorded by `scripts/linux_boxes.py` (including the stuck case where its ssh tunnel died). It
  then waits for the character to actually reach a zone, nudging the title screen with Enter, and
  only reports success then; a timeout stops the new client and reports its log path.
- **Headless boxes can use their own game folder.** Settings gains **Headless game folder** for
  the older hook-complete install the `host64-headless` binary was built against; leaving it empty
  keeps using the main game folder.

## Unreleased — Trusts cast their spells and passive auras

- **Alter egos now use their own spell lists.** `0117_trust_spells.sql`, generated by
  `tools/import_lsb_trusts.py`, carries the 1,259 `mob_spell_lists` rows behind the 62
  Trusts that have one.  Kupipi casts Protectra/Shellra/Cure, Shantotto nukes, Koru-Moru
  puts up Protect/Shell and enfeebles, and the melee-only Trusts keep swinging.
- **The AI casts instead of only meleeing.** A Trust cures its owner below 85% HP, keeps
  missing or expiring buffs up, lands a missing debuff on the owner's target, then nukes.
  Casts send the real Magic Start and Magic Finish actions (`0x028`) from the Trust's id,
  spend the Trust's MP and resolve on the tick after the cast time.  Melee Trusts still
  swing; pure casters hold their distance.
- **Passive Trust auras exist and have their own icons.** Cornelia applies
  `TRUST_AURA_HASTE` (808) with the GEO Haste icon (580), so the extra Haste icon sits
  beside ordinary Haste instead of being hidden by it.  Sakura, Moogle, Star Sibyl,
  Kuyin Hathdenna, Brygid and Kupofried carry their Regen, Refresh, Magic Attack,
  Accuracy, CHR and Dedication auras with the matching GEO icons.  The aura is removed
  when the Trust is released or despawns.
- Tests: `test_world` covers a Kupipi cast and status icon, Cornelia's separate Haste
  icon with no auto-attack, and Shantotto's nuke; the importer's `--check` covers both
  generated migrations.

## Unreleased — Parties and alliances

- **`/pcmd add`, the party menu's invite, `/acmd add` and alliance invites now work.** All four
  entry points send the client's `C2S 0x06E` (Kind 0 for a party, 5 for an alliance). Fanxi did
  not handle that packet, and because it arrives with sync 0 the dispatcher dropped it before the
  "first packet" log line, so the command silently did nothing. It is now answered: `0x0DC`
  prompts the invitee, `C2S 0x074` accepts or declines, and an accepted invite builds the group.
- **The roster is server-owned.** A member receives `0x0C8` (the party table: up to 20 rows with
  party number, leader/alliance-leader flags and zone) followed by one `0x0DD` per member (HP/MP/TP,
  job/sub-job, level, member number and name). Members in another zone are sent their zone number
  instead of vitals, the shape retail uses.
- **Vitals follow the party.** Each member's `0x0DF` (the packet the player already received for
  themselves) is copied to the other group members when HP/MP/TP changes, at most twice a second,
  so the native party bars and the Party Info hub stay current.
- **Leaders, leaving, kicking, disbanding and alliances.** `C2S 0x06F` (leave), `0x070` (disband),
  `0x071` (kick), `0x076` (reload), `0x077` (leader) and `0x078` (group id) are handled. A leader
  who leaves passes leadership to the next member; the last member folds the party. An alliance
  invite needs two party leaders; up to three parties form an alliance, led by the main party's
  leader, and `0x0C8` switches to Kind 5 with each row carrying its party number. `0x0E1`
  (the group id) is only sent while grouped: id 0 makes the retail client follow a null group
  pointer and crash.
- **Not in this pass:** party/alliance chat (`/p`, `/a`), party search, level sync, treasure pools,
  Trusts in the roster, and persistence across a server restart. A relog starts solo.

## Unreleased — all 198 Ambuscade JSE capes, stored in the locker

- **Every job now has its full Ambuscade cape set.** `capes.py` grows from four jobs
  (BST/NIN/DRK/BLM) to all 22 — 198 builds, one `tp`/defensive/WS/pet/fast-cast set per
  job, with the same augment block the gearswap libraries name. `tools/gen_capes.py`
  writes the `0116_all_capes_locker.sql` migration and [docs/capes.md](docs/capes.md)
  from it; the page lists every build and block.
- **The builds live in the hidden 9999-item locker, not in a bag.** 198 copies of 22
  item ids only fit there. `char_locker` gains a 24-byte `extra` block and a primary
  key that includes it (`character_id, item_id, extra`), so nine Taranus's Capes or
  eleven Andartia's Mantles can sit side by side without losing their augments.
  `//locker store|grab jsecapes` is the new selector; `//locker list` shows each cape's
  build.
- **`//job` grabs the new job's capes and the tidy puts them in the wardrobes.** After
  the new job's slips are pulled, the command takes that job's cape builds out of the
  locker and the existing tidy moves the loose copies into the Mog Wardrobes; the
  other 21 jobs' capes stay stored. `//locker grab jsecapes` takes all 198 out and
  `//locker store jsecapes` returns them. The equipped cape keeps its block through the
  move, and `equipped_mods()` still counts its augments.
- **Old bag/wardrobe cape copies are cleaned up by the migration** (an equipped cape
  stays and is re-encoded to its job's default build), so the first `//job` has room for
  all 198. The four earlier per-job migrations remain historical.
- **Gearswap libraries:** the 11 files whose `local capes` table had been flattened by
  the launcher (RDM, THF, BRD, RNG, SAM, NIN, SMN, DNC, SCH, RUN, DRK) have their build
  tables back, and every `back = "<job cape>"` now points at `capes.<build>`. The other
  11 already carried theirs.
- Tests: `test_capes` covers all 22/198 and the generated migration/docs;
  `test_world` covers two same-id capes surviving store/grab and `//job` pulling them.

## Unreleased — Warp team to me

- **`//warp all me` calls the team to the sender.** It keeps the leader where they stand and
  moves every other online character in the account family (the main account and its
  sub-accounts) to the leader's zone, position and heading. `here` and `self` are accepted too,
  and a saved warp whose alias is "me" no longer shadows the built-in target.
- **The launcher has the same button.** **Warp team to me** sits in the Warps page's current
  position card and in the Control room's **Live party** header, where it acts on the highlighted
  row. All of them send `//warp all me` through the character's control port, so the server still
  owns the zone hand-off and the position it read from the client.
- The Warps help grid and command docs list the new form; the leader is never re-zoned by its own
  call.

## Unreleased — Battle Info and Party Info hubs

- **Battle Info** is a new in-game window with Start, Pause, Stop and Reset controls. It
  measures the player's session from `0x028` action packets: DPS (session, rolling 60 s and
  peak), total/melee/WS/magic/ability/skillchain damage, max/average hit, melee and WS
  accuracy, crit rate, damage taken/DTPS, kills and EXP/hr. Auto-start on damage is optional,
  and every window switch and position is saved per character.
- **TP to 1000** times the next TP cycle from zero: seconds, hits, TP/s, TP per hit, an ETA
  while the bar fills, and the last/average completed cycles. TP polling follows the live
  party bar; a spent weapon skill starts the next cycle.
- **The FPS overlay moved into Battle Info.** The window shows FPS, frame milliseconds, a 1%
  low and a sparkline. While it is shown the renderer's top-left counter is hidden through a
  new `xi.fx('fps', 0)` binding and restored when the window closes.
- **Party Info** is the second hub: **Party** and **Alliance** tabs with HP/MP/TP bars,
  job/sub-job and level, and status-effect icons per member (hover names, optional names
  line). The player's buffs come from `player_t.Buffs`, the other party members' from
  `partystatusicons_t`; alliance members outside the player's party say the client has no
  status data for them.
- **Replace game list** makes Party Info opaque and backs it with a dark panel over the
  client's own party list. It is an overlay cover (the native list is still drawn beneath);
  moving the window uncovers it.
- Both hubs open with `//battleinfo` / `//partyinfo` (aliases `//battle` / `//party`) and are
  available to the launcher as the `battle_info` / `party_info` control commands.

## Unreleased — Trust magic calls alter egos

- **Casting a Trust spell now puts the alter ego in the zone.** Trust spells (896–1019)
  had rows and client menu entries, but `cast_magic()` treated them as ordinary self
  spells: the finish line said "Shantotto takes hold." and no NPC appeared.
  `cast_trust()`/`finish_trust_cast()` now spend no MP, keep the cast bar, and spawn the
  Trust as a `0x00E` with the Trust/Pet flags, a pet-range targid and the `0x067`
  master packet the client needs for its Release menu.
- **The data is the game's own.** `database/migrations/0115_trusts.sql`, generated by
  `tools/import_lsb_trusts.py`, carries the factual look block, job, attack delay and
  damage multiplier for all 122 Trusts. Each tracks the owner's level, follows them,
  attacks their current target and turns half its damage into the owner's enmity.
- **Lifecycle.** Duplicate calls are refused and five active Trusts is the cap; a zone
  change, logout, K.O., or the client's Release menu despawns them. Other players in
  the zone see the same spawn. `trust_summary.summoning` is now true, so the launcher
  no longer labels Trusts "menu only".
- **The Trust HUD shows who is out and toggles them.** The HUD matches the client's
  Trust-flagged spawnables against the `0x067` master targid, so another player's Trust
  with the same name does not light up your tile. An active alter ego gets a cyan border,
  a left stripe and an active dot. Clicking an active button sends the new
  `//trust release <spell id>` command, which releases that Trust immediately instead of
  trying to call it a second time. `//trust` lists active alter egos and
  `//trust release all` clears them.
- **Not in this pass:** Trust spell/job-ability AI, party-window rows, and monsters
  choosing a Trust as their hate target.

## Unreleased — combat HUD gets trusts, weapon skills and grouping

- **Trust magic is its own window.** Trust spells no longer sit in the spell list. A new
  account switch, **Show trusts**, drives a separate window grouped by each trust's main job
  (122 trusts mapped from the client's own spell table). Trust buttons now use cropped portrait
  faces from the BGWiki trust cards instead of lettered tiles. **Show weapon skills** adds a fourth
  window built from the client's `0x0AC` weapon-skill ids and clicks with `/ws`.
- **Weapon skills show their skillchain and TP data.** Every weapon-skill button now carries the
  skillchain element it can open (with an L1/L2/L3 badge) instead of a generic sword, plus the
  equipped weapon's icon beside the group title. The window header shows current TP against the
  1000 TP cost, a skillchain-window countdown (wait, then go), and a dropdown for the skillchain
  you are hunting; matching weapon skills get an accent border and the rest dim. Tiles are dim and
  non-clickable below 1000 TP, and the hover tooltip carries the interpolated fTP, hit count and
  all three skillchain properties. The face and element atlases are local, from BGWiki.
- **Layout is per type.** Abilities, spells, trusts and weapon skills each keep their own
  grid/list/bar choice, columns, tile size, label size and position. The editor has a tab for
  each type, and the Control room keeps a **Layout** button beside the four switches.
- **Folder tabs and tighter windows.** Grouped windows default to one group per page with a
  folder-tab strip (Buff/Debuff/Nuke, main/sub job, trust job, weapon type). A click flips pages
  instead of scrolling through every group, and the window chrome is down to a few pixels so a
  bar is one tab row plus one tile row. Tabs can be turned off per type if stacked groups are
  preferred.
- **Grouping.** Spells group by type (healing, buff, debuff, nuke, avatar), magic skill or
  element; abilities by main/sub job, with Scholar split into Light Arts, Dark Arts and Other;
  trusts by job; weapon skills by weapon type. Every type also offers no grouping and **custom
  groups**: create named groups in the editor and drag items from Unsorted into them. Groups
  and assignments save with the rest of the HUD state.
- **Labels are readable again.** Grid and bar tiles draw a short stock-style abbreviation under
  the icon at a configurable 7-12 px, auto-shrunk on small tiles; hovering always shows the full
  name, level and recast. Labels no longer disappear on grid/bar, and list width is measured from
  the longest line instead of a fixed 264 px.
- **The game menu no longer wins during combat.** Menu-side hiding is suppressed while the player is
  engaged or has a live target, so opening the battle/ability menu mid-fight cannot make the ability
  or trust windows vanish. Out of combat the right-hand Commands/Status stack still hides its side.
- **The game menu wins.** When a client menu is open, windows on the menu side (the right-hand
  Commands/Status stack) hide, because the client draws that menu above the overlay; a HUD moved to
  the left stays put. The behaviour is a switch in the editor.
- **Persistence covers the new state.** `<data dir>/hud/<character>.json` now stores the four
  switches, per-type layout/grouping/custom groups, label size and all four positions, and
  migrates the old two-window layout without resetting it.

## Unreleased — augment rows reach the stat sheet

- **Rank 30 augments were tooltips only.** The server wrote every augment block
  (`//r30`, `//rp30`, `//cape`, the launcher card) but never read one back: `equipped_mods()`
  summed `item_mods`, which holds only the base item. A Ninja in the full Revelation set
  therefore had DA 13 (WAR-sub trait 10 + Cessance 3) instead of DA 47, and an eight-round
  kill showed two hits a round and no `multi-attack` line. `equipped_mods()` now joins each
  equipped row back to its inventory copy and `game/augment_stats.py` decodes the block.
- **Both block families are read.** Bundled augments (`0x03/0x83`) resolve their bundle
  index against the Odyssey/Limbus/Unity datasets and apply the rows of the path the block
  names (Nyame A-D included), gated on the block's rank; standard augments (`0x02/0x03`)
  are the cape five-slot builds, rendered through `capes.slot_text` and parsed by the same
  code. One text parser covers `"Double Attack"+7%`, `Acc/Rng. Acc./M. Acc.+30`,
  `DEX/AGI+10`, `All Attr.+10`, `Damage taken-10%`, `Phys. dmg. limit +6%` and the rest,
  with hundredths-of-a-percent stats scaled (`Damage taken-10%` -> -1000) and percent-int
  stats kept whole (`Store TP"+10` -> 10).
- **Coverage is enforced by a test.** Every row in the three datasets and every cape build
  must parse or be listed in `augment_stats.UNMODELLED`; the list is pet stats, Snapshot,
  block rate, magic-burst II, spell interruption, weapon `DMG:` rating and the
  Phalanx/Blood Pact lines, which the engine has no model for yet.
- **New modifier names:** 27 Enmity, 289/290 Subtle Blow I/II, 291 Counter, 174 Skillchain
  Bonus, so augment rows keep the ids the rest of the engine uses.

## Unreleased — TP is per hand, enmity is CE/VE

- **TP used the retired flat formula and the dual-wield round's average delay.** A 227-delay
  katana paid 6.0 TP per hit because `(delay + 480) × 0.0085` was applied to the round's
  135-delay average, and the off hand paid the same even when its weapon was faster. Retail
  uses the piecewise delay curve (LSB `scripts/combat/basic/tp.lua`): 7.2 TP for 227 delay,
  and with 35% Dual Wield the main hand's 73 delay pays 4.2 while a 190-delay off hand's 61
  pays 4.0. Each landed hit, including Double/Triple/Quadruple extras, is now computed from
  its own weapon, then Store TP is applied and floored. Monster TP gain from being hit
  (Subtle Blow/dAGI) is still not modelled because monsters have no TP moves.
- **Enmity was one number per player with no decay.** It is now the real two-meter model from
  LSB's `CEnmityContainer`: cumulative enmity plus volatile enmity, 80/240 per damage scaled
  by the monster's level (`level × 31/50 + 6`), a 100-point enfeeble split, Provoke's 1,800
  CE and the first-hate 200 CE + 900 VE claim bonus. Each meter clamps at 30,000. Volatile
  enmity drains 60 points a second and the monster re-picks the highest CE + VE, so a tank
  can lose hate again; cumulative enmity never decays by itself. Claim locking and linking
  remain open.
- **Magic used a multiply-then-subtract MAB/MDB shape.** `combat._magic_finish` now uses
  LandSandBoat's ratio `(100 + MATT) / (100 + target MDEF)` and adds "Magic Damage" to the
  spell's base *before* the ratio; the old code added it after multiplying by MAB and then
  subtracted MDEF as a second percentage.  Resist tiers and elemental affinity/day/weather/
  staff bonuses are still not modelled.
- **Corrected while auditing:** the hit-rate formula is `75 + (accuracy - evasion)/2` (not
  `/3` when positive) and LSB agrees; fSTR is the tiered table in
  `docs/combat-damage.md`, not a bare `(STR - VIT + 4) / 4`; and multi-attack priority is
  Quad > Triple > Double per hand, with kicks/Daken as separate swings rather than earlier
  checks.

## Unreleased — skillchain data and transition core

- **All 216 weapon skills now carry their three skillchain properties.** `data/skillchains.json`
  is imported from LandSandBoat's `weapon_skills.sql` `primary_sc`/`secondary_sc`/`tertiary_sc`
  columns; the 13 Prime skills commented out of that file (plus Exudation) use their BG-wiki
  Skillchain lines.  `weapon_skills.WeaponSkillData.sc` exposes the tuple.
- **The transition table is LSB's real one.** `skillchain.py` carries the 29 directional
  `(closing property, existing resonance)` entries from `battleutils.cpp`, the sequential
  1–16 `SC_*` ids, the tier and element maps, the opening/3-second/link timing state
  machine, the chain damage multipliers and Magic Burst helpers.  It replaces the proposal's
  `IntFlag`/tier-precedence matrix, which had wrong pairs such as
  `(Detonation, Scission) -> Gravitation` and a `Liquefaction + Impaction` direction that
  only works one way.
- **Not wired to combat yet.** `ZoneSession.weaponskill` does not call the state machine and
  the 0x028 builder does not write the additional-effect block.  Stage B is the runtime
  wiring; Magic Burst also waits on the magic hit-rate/resist-tier port.  The full design and
  the verified MB values are in [docs/skillchains.md](docs/skillchains.md).

## Unreleased — Double, Triple and Quadruple Attack proc again

- **Multi-attack was in the trait table but no combat path read it.** A Ninja 99 with a
  Warrior 49 support job therefore never double attacked, and Windbuffet Belt +1's
  Quadruple Attack +2 did nothing. The attack round now rolls each hand separately in
  retail's order -- Quadruple (430, 4 hits) > Triple (302, 3) > Double (288, 2) -- and a
  proc replaces the lower checks for that hand. The winning hits use that hand's weapon,
  Accuracy, damage and animation, and all of them ride the same `0x028` as the base
  swings, so a dual-wielding round shows up to eight results in order.
- **Job and merit rates count.** The Warrior Double Attack trait's 10/12/14/16/18% flows
  through the existing modifier path, the Warrior's Double Attack Rate merit adds 1% per
  rank while Warrior is the main job, and gear lines are read from `item_mods` (the
  reforged import now maps "Quadruple Attack" to 430 as well). A support-job Warrior keeps
  the trait but not the merit; the merit never follows a non-Warrior main.
- **Kill ordering is preserved.** The round resolves every swing before queueing, the
  action still goes out before the defeat/EXP lines, and no later swing is rolled once an
  earlier one spends the target's HP. Weapon skills are a separate path and do not roll
  multi-attack here; Counter, Kick Attacks and Zanshin remain inert.

## Unreleased — weapon skills use their own fTP, WSC and hit count

- **Every weapon skill used the same 2.0-at-1000-TP curve and no WSC.** A Blade: Metsu with a
  119 Kikoku therefore did about twice an auto-attack; retail's Adoulin branch gives the skill
  5.0 fTP and 80% DEX. `data/weapon_skills.json` (written by
  `tools/import_lsb_weapon_skills.py` from LandSandBoat's `scripts/actions/weaponskills`) now
  carries each skill's three fTP anchors, WSC, hit count, and its "varies with TP" critical,
  Attack and Defense-ignore lines. Savage Blade is 4.0/10.3/13.6 fTP; Blade: Shun is five hits
  with fTP on each; Blade: Kamu keeps its x2.25 Attack and 25% Defense ignore.
- **Multi-hit skills roll and display every hit in one action**, and stop when the target's HP
  is spent. The first hit takes the full fTP and later hits take 1.0 unless the skill is a
  `multiHitfTP` skill.
- **Fotia gear now counts.** Mod 1144 `ANY_FTP_BONUS` is stored in 1/256 fTP units and is added
  to the skill's fTP (Fotia Gorget and Fotia Belt).
- **Prime skills with no player script got their BG-wiki rows** (Zesho Meppo, Fimbulvetr, Blitz,
  Disaster, Origin, Diarmuid, Tachi: Mumei, Sarv, Terminus, Imperator and Oshala). Dagda has no
  published fTP or stat modifiers and keeps the generic fallback.
- **Still approximate:** magic weapon skills still ride the physical pDIF path, archery and
  marksmanship skills still use the main-hand weapon, special formulas (Spirits Within,
  Atonement, Moonlight, Starlight) are not modelled, and weapon-skill TP return and aftermath
  are not implemented.

## Unreleased — Prime weapons advertise their own weapon skill

- **Equipping a Prime weapon did not put its unique skill in the Weapon Skills menu.** The
  `weapon_skills` table had no rows for the fourteen Prime skills, and only Varga Purnikawa and
  Mpu Gandring carried the retail `ADDS_WEAPONSKILL` (mod 355) line, so Dokoku never advertised
  Zesho Meppo. Migration 114 adds the client ids the menu uses (62 Fimbulvetr, 78 Blitz, 94
  Disaster, 110 Origin, 126 Diarmuid, 142 Zesho Meppo, 159 Tachi: Mumei, 204 Sarv, 222 Terminus,
  231 Maru Kala, 232 Ruthless Stroke, 233 Imperator, 234 Dagda and 235 Oshala) and the 355 row for
  the other twelve 119 III Prime weapons.
- **The grant follows the weapon, not the skill type.** A negative `skill_level` marks a skill as
  item-granted: the normal weapon-type/value filter skips it, and
  `ZoneSession.equipped_weapon_skills()` adds the ids the current outfit grants through 355. Dokoku
  now shows Zesho Meppo, while Kikoku (or any other katana) still does not, and `//ws "Zesho Meppo"`
  obeys the same check.

## Unreleased — ability and spell HUD on every account

- **Two switches on every running account.** The Control room now has **Abilities** and **Spells**
  toggles beside each account's character picker. They open in-game overlays of the current job
  pair's ability and spell lists, drawn from the client's own `0x0AC` list and spell table.
- **Real game icons, real cooldowns.** Each tile decodes the game's 32x32 menu icon from the icon
  DAT (`res.menu_icon_rgba`, file id 39551) instead of a placeholder. Clicking runs `/ja` or `/ma`
  through the client; a clock sector darkens the tile for the remaining recast, the countdown is
  drawn in the middle, and the tile becomes clickable again as `spell_recast`/`ability_recast`
  reaches zero. The overlay polls the live recast tables, so cooldowns used outside the HUD show up
  too.
- **Layout editor and in-game drag mode.** The per-account **Layout** dialog chooses Grid (3-12
  columns), List or Bar, tile size, label mode, opacity, and previews it. **Edit** adds draggable
  title bars to both windows; positions save on release and per character in
  `<data dir>/hud/<character>.json`, with a **Reset positions** action. The switches, layout and
  positions survive a restart, and `metrics` now carries the current HUD state for the launcher.
- **Resource layer:** `host/addons/res.c` gains `res_menu_icon_rgba`, decoding the `magi` sprite
  sheet and its 32x32 DXT3 icon images; the control protocol gains `hud`, and the launcher gains the
  `send_hud` Tauri command.

## Unreleased — a dual-wield round is one action again

- **Both hands swing, in order.** A dual-wield round sent one `0x028` per hand in the same
  update. The client keeps one action per actor and target, so it played only the last packet:
  the off hand swung, only its damage printed, and the main hand looked like it never attacked.
  The round is now one `0x028` with two results for the target, main hand first (animation 0)
  then off hand (animation 1), which is Windower's `action_count` and what makes the client
  play both swings.  Misses stay per hand (`server/fanxi_server/game/packets.py`,
  `ZoneSession.tick`).

## Unreleased — Myrkr works, and weapon skills keep their effects

- **Myrkr restored no MP and cured nothing because it was resolved as a damage skill.** The
  server had one weapon-skill path: require a monster in melee range, roll damage, spend TP. It
  never read anything the skill does besides damage. Myrkr is self-targeted and deals none, so
  the only thing a Scholar saw was "Myrkr strikes <mob> for N points of damage." The new
  `weapon_skill_effects.py` carries the retail rows: Myrkr restores 20/40/60% of maximum MP at
  1000/2000/3000 TP and removes up to three status ailments, needs neither a target nor melee
  range, and plays its own animation against the player. Dagan restores 22/33/52% HP and
  15/22/35% MP the same way.
- **The rest of the weapon-skill table now applies its effects.** Drains (Spirit Taker and
  Mystic Boon restore the damage as MP, Entropy 20%, Catastrophe 50% as HP, Sanguine Blade
  50/75/100%, Energy Drain/Steal their dagger-skill formula with no HP damage) and debuffs
  (Poison, Plague, Stun, Silence, Blind, Bind, Sleep, Weight, Slow, Attack/Accuracy/Defense/
  Evasion Down, Magic Atk./Def./Eva. Down, INT Down, Critical Hit Evasion Down) land after a
  hit that did damage, at their retail TP-scaled durations and through the same Magic Accuracy
  resist term spells use.  The combat engine reads the new debuffs: Defense Down (with Dia)
  lowers the monster's Defense, Accuracy Down its Accuracy, Magic Def. Down raises magic damage,
  Magic Eva. Down lowers its resist term, INT Down shrinks dINT, and Critical Hit Evasion Down
  raises the player's crit rate.
- **Weapon-skill damage gear and traits now count.** The skill's fTP is multiplied by weapon
  skill damage from `ALL_WSDMG_ALL_HITS` (840), `ALL_WSDMG_FIRST_HIT` (841) and the per-skill
  `WEAPONSKILL_DAMAGE_BASE + id` block (571 Combo, 580 Final Heaven, ...); "TP Bonus" (345) and
  Fencer's TP Bonus (903, with its crit rate 904 while single-wielding a one-hander) raise the
  TP used for scaling; "Weapon skill accuracy" (48) is added to the swing. TP is now spent the
  retail way too: everything up to 3000, keeping any excess on the bar.
- **Campaign-only skills are no longer advertised.** Uriel Blade, Glory Slash and Tartarus
  Torpor were in the staff/sword menus at 350 skill because the import leaves their requirement
  at 0; they need a Campaign Battle and a Campaign weapon, so the `0x0AC` list and `//ws` now
  refuse them.
- **Still not modelled:** weapon-skill aftermath (Empyrean/Relic/Mythic), each skill's own
  fTP/WSC table, skillchains and magic bursts, and the job traits the engine still does not
  read (Double/Triple Attack, Counter, Kick Attacks, Zanshin, Conserve MP/TP, Subtle Blow,
  Occult Acumen, Shield Mastery and the killer/resist families). These are listed in
  `docs/combat-damage.md`.

## Unreleased — Helixes are a nuke that repeats, not a flat 10 damage

- **Noctohelix and friends were ticking for a made-up number.** The generated icon table read
  LandSandBoat's `HELIX` row as "10 damage per tick" when the 10 is the interval in seconds, so a
  cast printed "receives the effect of Helix", dealt no opening hit, and then spat 10 damage every
  three seconds until it wore off. A Helix now deals its real opening nuke (`combat.helix_damage`:
  base + dINT, halving past 100 dINT) and stores that exact number as the damage-over-time, which
  lands again every ten seconds for 30/60/90 s depending on the Scholar level (a /SCH caps at 60 s).
  The first tock is 1-10 s after the cast, one tock is capped at 9,999, and a tier-1 Helix no longer
  replaces an active tier-2 Helix. Dark Arts/Tabula Rasa's Helix bonuses remain unmodelled with the
  rest of the arts.

## Unreleased — one tenant bar for the whole launcher

- **Tenant swapping is now global.** A bar above every page names the selected tenant — a main
  account character or a sub-account box — and its dropdown switches **Home**, **Design**, **Data**,
  **Gear / GearSwap** and **Warps** together. The Gear page no longer has its own client picker,
  the Warps page no longer has its own character picker, and the Design page no longer has its own
  character chips; all follow the bar. Selection stays put when you navigate and is saved as
  `tenant_character_id` in `launcher.json`, beside the active character and last page.
- **Sub-account boxes are full tenants.** The main account's token may read and write a box
  character's Data page (`GET /characters/{id}/data`, merits, gil, ranks, Armory, augment paths and
  the rest) and repaint its design (`PATCH /characters/{id}/design`), matching the Warps API's
  team-wide ownership rule. Applying a design on the Design page writes to the tenant in the bar,
  then refreshes the Team roster, so the preview and every other page show that box's new look.
  Another player's token still gets a 404, so character ids stay non-enumerable.
- **Home and Team know the tenant.** Home shows the selected tenant (including its live gear and a
  Play button that launches the right box), and Team marks the box currently being viewed with a
  **View** button on the others. Switching accounts clears the tenant and falls back to the new
  account's active character.

## Unreleased — //warp, the Warps page and // Tab completion

- **`//warp` remembers places by name instead of a zone id.** Migration 110 adds `char_warps`
  (character, slot 1-1000, optional unique alias, zone, position, rotation). `//warp mark [alias]`
  stores the sender's current in-memory position under the next number; `//warp me <n|alias>` and
  `//warp all <n|alias>` return alone or with every online character on the sender's main account
  and its sub-accounts (the multibox group). `//warp list [page]` prints eight per page,
  `//warp delete <n|alias>` removes one, and `//warp rename <n> <alias>` names one from chat.
  Numbers and case-insensitive aliases/prefixes both work, with an exact alias winning and an
  ambiguous prefix listing the candidates. `//hp` keeps the Home Point menu; `//warp` no longer
  aliases it.
- **The launcher has a Warps page.** It lists the selected character's saved places with number,
  alias, zone and coordinates; **Mark** reads the live client's current position, **Warp** sends
  `me`/`all`, and aliases can be renamed or rows deleted inline. A main-account token can manage
  the family's sub-account characters too. The page is also linked from the Control room.
- **`//` commands complete with Tab.** The host now sees Tab while the chat line starts `//` and
  rewrites the input from `host/addons/complete.c`: `//wa` -> `//warp `, `//warp ma` ->
  `//warp mark `. An ambiguous prefix never guesses: the line is left as typed and Tab is consumed,
  so `//w` does nothing and `//wh` -> `//where `. An exact command name wins over a longer one that
  shares it (`//home` -> `//home `). The table covers every server command plus `//gs` and
  `//follow`, and `tests/chat_complete_test.py` compiles and checks the pure completion source.
  `xi_chat_set_input` also moves the input caret/display counter to the new end and asks the chat
  manager to redraw its line, so the completion appears on the first Tab instead of the next key
  press and the next typed character does not land inside the completed command.
- **Migration 110** (`0110_character_warps.sql`) must run on an existing database; restart the
  server once after updating. `runtime.json` is bumped so the launcher rebuilds the client host.

## Unreleased — food and every spell read one modifier pool

- **Item use now finds the item the player clicked.** `C2S 0x037` names the container and
  the slot (`Category` at 0x10, `PropertyItemIndex` at 0x0E); the bytes at 0x08 are
  `ItemNum`, which the client always sends as zero. `item_use` read an item id from there,
  so every request looked like item 0 and returned before consuming, logging, animating or
  applying anything. It now resolves the slot, consumes exactly that stack and replies for
  that container/slot. **Migration 112** (`0112_food_animations.sql`) adds each food's
  eating animation, and the `0x028` ItemFinish action plays it; the Food icon and timer
  follow with the existing `0x037`/`0x063` pair.
- **Food is a real modifier source.** Migration 109 adds `food_effects`, five starter
  foods (Apple Pie, Witch Soup, Chocolate Cake, Miso Ramen, Red Curry Bun) and a stack of
  each for Onedough. `item_use` consumes the food, puts the Food icon and timer up, and
  stores its modifier dict on the session; `combat_mods()` merges it beside gear, traits,
  buffs and HP/MP merits, so the stat sheet, maximum HP/MP, magic damage, healing and
  every spell modifier see the same values. The food expires on the three-second tick and
  the maxima are recomputed.
- **Duration and potency now go through the merged pool, not the table alone.** Enhancing
  buffs read the generic Enhancing Magic Duration terms plus their own lines (Sneak,
  Invisible, En-spell, Ninjutsu, song); enfeebling and dark spells read
  `ENF_MAG_DURATION` / `DARK_MAGIC_DURATION`; potency reads `"Cure" potency` (and II,
  received, bonus), `ENF_MAG_POTENCY`, `"Enhances Refresh"`, `Stoneskin` bonus HP and
  `"Drain" and "Aspir"` potency. Magic damage, Magic Accuracy and Fast Cast were already
  reading the same dict, so food and self buffs now flow into them too.
- **Still not modelled.** There is no party system, so another player's buffs cannot be
  merged; the server only knows the session's own effects. Protect/Shell/Haste/Phalanx
  base potency, bar-spell resistance, food HP/MP percentage caps (the starter foods use
  flat/stat modifiers and the attack/defence/accuracy caps are applied) and most food
  items are still approximations or absent. The per-spell base formulas that were
  hardcoded remain hardcoded; what changed is that the gear/food modifiers are no longer
  ignored.

## Unreleased — Regen V counts Light Arts, gear and Perpetuance

- **A Regen spell's timer was its table duration and nothing else.** Regen V showed 1:00
  even with Light Arts up. `effects.buff_duration` now follows the retail formula: flat
  seconds first (Light Arts adds `floor((level-10)/10) x 6` seconds and 3 HP/tick per
  step at Scholar main -- +48 s/+24 HP at 99 -- Tabula Rasa replaces that with +72 s/+36,
  and gear such as Lugh's Cape adds its Regen seconds), then the gear's listed and
  augmented Enhancing Magic Duration multiply as two separate terms, then Perpetuance
  doubles the next white enhancing spell (2.25x-2.65x with the Savant's/Arbatel hands).
  The Regen tick also reads `"Regen"` potency gear.
  The line's base numbers were wrong too: Regen II/III were 90/120 s at 10/15 HP, while
  retail is 60 s for II-V (75 s for Regen) at 12/20/30/40 HP.
- **Migration 108 writes the gear lines LSB does not table.** Arbatel Bracers +3 carries
  `"Perpetuance"+65%` on LSB spare id 1221, Lugh's Cape and the Regen-duration pieces use
  `REGEN_DURATION` 339, and the reforged SCH/RDM/WHM/RUN pieces get their `"Regen"`
  potency and `Enhancing magic duration` rows. `tools/import_reforged_item_data.py`
  learned the same tooltip lines.
- **The formula can fold in the Light Arts Effect job points.** `buff_duration` takes a
  `light_arts_jp_rank` (+3 s/rank, 20 max); the zone passes 0 because this build does not
  store JP ranks -- the client's JP menu is maxed only to unlock the job gifts. With rank
  20 and the Community Scholar Guide's max-duration set (Musa, four Telchine augments,
  Lugh's Cape, Arbatel Bracers +3) the model gives 940.5 s (15:40) under Light Arts and
  1056.2 s (17:36) under Tabula Rasa. A Corsair's Naturalist's Roll adds to the listed
  gear term on top of that, so those are not the absolute ceiling either.

## Unreleased — the weapon stays drawn while engaged

- **The battle stance is refreshed twice a second while engaged.** The client drops the
  drawn-weapon pose within about a second of any animation (a swing, a flinch, a cast or
  an equipment batch); the `0x00D` General block is what puts it back. The tick now
  re-sends just that animation every 0.5 seconds instead of the old ten-second refresh,
  which left the weapon down almost all the time, while spreading the draws out enough
  that the pose never visibly flickers. `assert_stance` (the engage, a cast result, an
  equipment batch) still sends the `0x058` assist target with the first draw.
- Verified live by injecting the packet at different rates: one draw every 0.5 seconds
  held the client's `Status` at 1 continuously, while one every 1-2 seconds made it flip.
- **The claim is sent with every entity update and survives the monster's death.** The
  owner (packet `0x2C`) is now paired with the ClaimStatus flag (`0x02`) on every
  non-despawn update, and `claim_char_id` outlives the fight: the corpse stays red until
  it despawns, while the hate target and enmity clear at death. Respawn resets the claim.
  Before this the client forgot the claim between status-bearing updates, so the target
  flickered red -> yellow -> red and the battle stance dropped with it.
- `server/tests/test_world.py` covers the refresh: a tick 0.6 seconds after an assert
  queues another `0x00D` without a new `/attack`, and a disengage stops it.

## Unreleased — every spell that puts an icon up now shows it

- **The effect table only covered the spells whose numbers it modelled.** Regen IV and V,
  Protectra, Shellra, the Bar- and Boost- lines, the -ga and -ra enfeebles and every song
  fell through `effects.for_spell()` and finished with no icon — and, for Regen IV/V, no
  ticks. `game/spell_effects.py` is generated from LandSandBoat's enhancing, enfeebling,
  ninjutsu and song tables (204 spells, with effect id and duration) and merged under the
  hand-written tables in `game/effects.py`, so the curated entries keep their ticks,
  potency and modifiers. `tools/import_lsb_spell_effects.py` regenerates it and `--check`
  fails when the committed table is stale. Blue magic and Geomancy bubbles are out of the
  sweep: their durations are script variables, not table columns.
- **The tier-II and merit lines are covered too.** Windstorm II finished with only
  "Windstorm II takes hold." — no icon, no countdown — because LandSandBoat's spell tables
  stop at the tier-I -storm line; the same was true of the other seven -storm II spells,
  the eight -Carol II songs, Enlight/Enlight II, Endark II, Reraise II-IV, Adloquium,
  Animus Augeo/Minuo, Ltng Threnody II and the six trust songs. They now carry their
  effect ids in `SWEPT_EXTRAS` (and the -storm II line uses its own icons, 589-596), so
  casting one puts the icon in `0x037` and its timer in `0x063`. The importer also
  normalises the client's "Ltng" abbreviation to LandSandBoat's "Lightning", so the
  Threnody row no longer disappears from a regeneration.
- **The status icon timer needs a second packet.** `0x063` miscdata type 9 carries each
  slot's icon and Vanadiel expiry timestamp; without it the client draws the icons but
  leaves every countdown blank even with Config > Misc > Timer Display on. `status_icons()`
  builds it and `pack()` sends it directly after every `0x037`, slot for slot.
- **Job abilities put their icons up too.** The Scholar arts, addenda, stratagems and
  Sublimation were reported with a chat line only; `effects.ABILITY_EFFECTS` now carries
  their effect ids, retail durations and the cancels that swap one art for the other.

## Unreleased — a movement step no longer re-equips the whole set

- **The phase engine only sends gear when the state's set actually changes.** `state_set` in
  `host/addons/phase.c` rebuilt and returned the current state's set on every transition, so a
  step taken while engaged (the engaged set outranks movement) re-sent all fifteen pieces, and
  so did the client re-sending `/attack` for the target it was already fighting. Each piece makes
  the client drop its battle stance for the server to re-assert it, which is the sheathe/draw
  loop it looked like while fighting a mob. The engine now tracks the state index whose set is on
  (`g_worn_state`) and leaves the gear alone when a transition lands on it; a pushed plan, a
  zone or job settle, an unlock and a slot-pin change still force the set out.
- `tests/phase_state_test.sh` runs the new behaviour in the addon harness: a movement step while
  engaged returns nothing, while disengaged movement still swaps sets, and a forced apply still
  re-wears the set that is on.

## Unreleased — Limbus armour renders in its real look

- **The 25 Limbus pieces now carry the client's grap models.** Migration 99 inserted them
  with `model 0`, and `ZoneSession._apply_equip_model` deliberately keeps the slot's previous
  look when a model is missing: the gear equipped and its stats applied, but nothing changed
  on the character. The client model table (`xi-tools`' `mv/lists/characters.json`) maps the
  five families to armour MIds 513-517 — Revelation 513, Sworn 514, Indomitable 515, Duty 516
  and Clemency 517 — and the raw model is the slot base (0x1000 head, 0x2000 body, 0x3000
  hands, 0x4000 legs, 0x5000 feet) plus that MId. Migration 107 writes `items.model` and adds
  the rows to `item_models`, so migration 95's triggers stamp them on later grants and
  `tools/item_models.json` keeps them for clones. A character already wearing a piece needs
  one re-equip or zone for the new look; the SCH sets themselves are unchanged.

## Unreleased — base weapon names in the GearSwap libraries

- **The default libraries name their iLvl 119 weapons the way GearSwap and the client do.**
  `Kikoku 119 III`, `Nagi 119 III`, `Tupsimati 119 III`, `Hvergelmir 119 III` and
  `Opashoro 119 III` are now `Kikoku`, `Nagi`, `Tupsimati`, `Hvergelmir` and `Opashoro` in
  `gearswap/*.lua` (BLM, NIN, SCH and WHM) and in the `.lua.bak` copies beside them. The
  database keeps the `119 III` spellings to tell duplicate item ids apart; the set files use
  the base name the item table carries.

## Unreleased — Scholar wears Indomitable R30

- **`gearswap/SCH.lua` now wears the Bravery suit at Rank 30 where its raw stats win.**
  Free Elemental nukes and Helix take the head/body/legs (72 M.Acc, 68–72 MAB and
  22 Magic Damage a piece), Enfeebling takes body/hands/legs for the INT/MND bridge,
  fast cast takes the 10% body and 8% legs, Elemental Macc takes the full five-piece,
  and the new `sets.idle.dt_indom` is a five-piece balanced-DT build. Arbatel Loafers
  +3 stays in the nuke and helix feet for `"Klimaform"+25`, Arbatel Bracers +3 stays
  in Helix, and the Enhancing Magic and Healing Magic sets are untouched.
  `sets.midcast.Elemental Magic MB` keeps Nyame Path C for its Magic Burst Damage II
  rows, and max PDT/MDT stay on Nyame, whose per-piece DT is higher.
- **The placement is generated, not hand-copied.** `tools/gen_limbus_r30.py` gains the
  six SCH rows and can now target the bracket-named `sets.midcast[...]` tables, so
  `--docs` lists them and `--check` keeps the page honest. SCH goes from 40 to 42
  sets; the folder now lists 745.

## Unreleased — ranks, levels, skills, trusts and RP join the Data page

- **The Data page now assigns the rest of a character's progression.** New cards cover
  mission rank and rank points (per nation), the Mog Garden rank, fame in every city, all
  22 jobs at 99, per-job Master Levels 0-50, Exemplar Points, the crafting/fishing skills,
  a Trust re-issue, and an RP card that lists augmentable gear in the bags, shows each
  path's lines and caps the chosen path at the gear's maximum block.
- Migration `0106_character_progress.sql` adds the rank columns, `mog_garden_rank`,
  `exemplar_points`, `char_fame` and `char_craft`. `0x061` now carries the real rank,
  rank points, current job Master Level and Exemplar Points, and `0x062` carries the
  crafting block instead of zeroes.
- The RP registry merges Odyssey (Nyame paths A-D, the other sets/weapons single),
  Limbus (single Rank 30, curve B, 55,800 RP) and Unity (single Rank 15, curve A,
  1,110 RP). Capping writes the 24-byte bundle and `//reload` re-sends the item attribute
  so the tooltip updates.
- Trusts: all 122 Trust spell ids and the cipher key items are already in the zone-in
  bitmaps, and the card re-issues them. Trust summoning itself is not implemented yet,
  so casting a Trust still will not spawn the ally.

## Unreleased — the launcher's Data page

- **A new Data page assigns the character values Fanxi otherwise derives.** Cards cover merits
  (current/cap plus a top-off), the capped job-point block, the Profile Mastery Rank (1–10),
  gil, Home Point registration, a named currency ledger, the permanent key-item tables and an
  Armory that searches weapons, armour, accessories and ammo and adds them to the inventory,
  with a purchase history that flags what the character still holds. Values are written
  through the HTTP API; when the character is online the page sends `//reload`, which re-reads
  the row and re-sends `0x01B`, merits, job points, key items and the inventory in one burst.
- **The Armory now covers the whole equipment catalogue, with a typeahead.** Migration `0111`
  joins the retail client's item names to LandSandBoat's `item_basic` / `item_equipment` /
  `item_weapon` rows, so every named weapon, shield, armour, accessory and ammunition item is
  searchable — 15,524 rows instead of the 813 hand-curated items the table started with.
  Migration `0113_armour_models.sql` fills the few hundred armour models LandSandBoat leaves
  at MId 0, so the new catalogue pieces do not keep the previous slot's look. The Data page
  suggests matches as you type (keyboard-navigable), draws each piece's BG Wiki icon, and
  opens a purchase card with slot, level, item level, job count, Rare/Ex flags and a gil
  price. Rare **or** Ex pieces the character already holds show **Currently owned** and cannot
  be bought again; other owned pieces can be bought again. The price is charged against the
  wallet and recorded on the purchase-row, and toasts report the amount.
- Migration `0105_character_data.sql` adds `characters.mastery_rank`, `char_currency` and
  `char_purchases`. `dancer()` writes the Mastery Rank byte at payload `0x62` (packet offset
  `0x66`), the value the Profile page prints.
- Job points and key items are already capped/granted by the zone session, so those two cards
  report the state and re-issue it rather than moving a stored number.

## Unreleased — job abilities and traits reach the menu again

- **The Abilities menu lists the current job's abilities and traits for every job again.**
  The 2026-10-05 build entry named `ability_list` but not the list object's `commands`/`count`
  offsets, so `host/addons/hooks.c`'s list-rebuild hook compiled out entirely. The server still
  sent the `0x0AC` bitmap, but the client kept its saved command-id list (empty on a fresh
  profile), which is why SCH, BRD, BLM and every other job showed "No abilities available." and
  an empty Job Traits page. The offsets are part of the object's layout (`+0x160` and `+0x1760`
  in both the 2025-07-03 and 2026-10-05 clients), so the hook now supplies them itself whenever
  `meta/builds.json` maps `ability_list`; `tools/newbuild.py` cannot carry them, so a new build
  can no longer drop the hook by omission. Rebuild `host64` and restart the client once.

## Unreleased — gear changes keep the HP/MP maxima true

- **A gear swap now recomputes max HP/MP before the passive tick reads them.** `flush_equipment`
  saves the outfit and then calls `refresh_vitals`, so `char["hp"]`/`char["mp"]` follow the set
  the character is actually wearing. Previously a swap that raised a maximum left the stored one
  at the old outfit's value: the character sat at that stale cap and `tick_regen` treated it as
  full, so `Chirich Ring +1` (Regen+2) and `Stikini Ring +1` (Refresh+1) looked inert while the
  client still drew the missing HP/MP. The three-second tick also re-derives the maxima from the
  stat sheet, so an older save cannot stall it either.
- **`//traits` reports gear Regen/Refresh too.** The "Passive tick" line now uses the merged
  trait-and-gear modifiers and prints for a job pair with no Auto Regen/Auto Refresh trait, which
  is what made a gear-only tick (Chirich/Stikini) invisible to the diagnostic.

## Unreleased — the status page's item level and Superior

- **The status page now reads `iLv 119/ Su 5` instead of `iLv 218/ Su 0`.** The client
  draws `99 + 0x061.ilvl` (its byte is the item level *above* 99), so a full iLv 119 set
  sends 20, not 119. `su_lv` carries 5, the Superior level the 2,100-JP job gift
  unlocks; every job here has its points maxed. `highest_ilvl`, `ilvl_mhand` and
  `ilvl_ranged` still carry 119.

## Unreleased — Limbus Rank 30 reaches the tooltip

- **All 25 Limbus suit pieces now carry their real Rank 30 augment bundle.** The previous
  grant wrote `bundle 0`, so the client had no effects to print and the tooltip showed the
  bare suit even though the rank field said 30. The indices (472-496) are the client's own
  bundle table (`xi.data.augments.bundles`, parsed from the MNC2 data); every one was
  matched to the Rank 30 row in `docs/limbus-r30.md` by content. The block also records
  55,800 RP on curve B, the rank-30 total (rank 1 is 1,600), so the client can draw the
  rank and the four augment lines.
- **`//rp30` re-stamps the Limbus pieces a character carries**, and migration
  `0104_limbus_rp30.sql` applies the same block to every copy already in a bag. `//r30 <piece>`
  now prints the bundle beside the rows. Bundle indices 477-481 are Duty,
  472-476 Revelation, 487-491 Sworn, 482-486 Indomitable and 492-496 Clemency.
- **The five Shard → Jewel furnace pairs are granted to Onedough and Twodough.** Justice →
  Destiny, Hope → Revelation, Trust → Camaraderie, Bravery → Persistence and Mercy →
  Affection (items 10001-10010), 99 to a stack, the Jewels Ex. These are augmentation
  currency, not the equip requirement: Su5 is the 2,100-JP job gift, which the server
  already maxes for every job; the client equips the suit unchanged.

## Unreleased — Black Mage capes and augments

- **Black Mage's Taranus's Cape now has all nine builds the library uses.** `capes.py`
  gains `BLM_BUILDS` (`tp`, `pdt`, `mdt`, `maxhp`, `dt`, `fcmp`, `macc`, `nuke`, `mabws`);
  migration 101 puts the existing wardrobe copy on `tp` and adds the other eight in
  wardrobe 6 slots 66-73. `//cape` lists the job and can re-encode any copy. The cape is
  Ex-only (not Rare), so the one-copy rule does not touch the builds.
- **`gearswap/BLM.lua` is back to the augmented library.** The launcher's flatten pass had
  dropped the `capes`, `unity` and `odyssey` tables. The file again points each set at its
  Taranus's Cape build, carries the Unity and Nyame/Agwu Rank 30 augments, and uses the item
  names `Hvergelmir`, `Opashoro` and `Wizard's Rod (Reforged)`. `Spaekona's Gloves +4` is
  gone; the seven sets that used it now wear `Archmage's Gloves +4`.

## Unreleased — one copy of every Rare item

- **The item catalogue now records retail's Rare and Ex flags.** `items.rare` and `items.ex`
  are populated from LandSandBoat's `item_basic` table (migration 102), so a piece that retail
  allows only once per character can be told apart from ordinary gear. Rare means one per
  character; Ex means untradeable, and on its own does not limit copies.
- **Onedough and Twodough no longer hold duplicate Rare/Ex gear.** The repeated grants left four
  Nyame pieces, two of each Rare +1 ring, two of several reforged pieces, and several stored suits
  at quantity two. Migration 103 keeps the equipped copy when there is one, otherwise the
  augmented Path A copy, otherwise the wardrobe-first slot; storage and the locker yield to a
  visible bag. The two characters now hold exactly one of each Rare item across their bags,
  storage slips and locker.
- **`add_item` and the shop refuse a second copy.** A Rare item must be granted one at a time, and
  a character that already holds one cannot buy or receive another; the shop checks before
  taking the gil. The ownership check includes the storage slips and the hidden locker.

## Unreleased — spell category overrides

- **The Gear page's Spells panel now has category overrides.** `Enfeebles · Macc`,
  `Enfeebles · Duration`, `Buff potency`, `Buff duration` and `Helix magic` each take one set
  for every spell the host groups into it (Enfeebling Magic, Enhancing Magic, and any `helix`
  spell), from the current main/sub spell list. A per-spell override still wins, then the
  category, then the midcast default, then the library's `sets.midcast.<skill>`. The
  macc/duration and potency/duration pairs are alternatives, so picking one releases the other.
  The host classifies the spells and `job_spells` returns each spell's `categories`, so the cards
  and the plan cannot disagree.

## Unreleased — spells land, tick and pull

- **Break and Breakga now petrify instead of hitting for 233 damage.** They were absent
  from the effect table, so both fell through to the direct-damage path and used the old
  `cost x 2 + level / 3` fallback. They now apply 30 seconds of Petrification, deal no
  damage, and the monster stands frozen (no walking, no swings) until the effect ends.
  Damage does not wake a petrified monster, unlike Sleep.
- **Dia and Diaga do what their data says: a small opening hit, then 1-5 HP every three
  seconds and a 10-30% Defence Down.** They no longer use the elemental-nuke formula: the
  old path multiplied a 2-base spell by dINT, Magic Atk. Bonus and flat Magic Damage and
  printed 1,475 damage on Onedough's level 99 set. `combat.dia_damage` uses the spell's own
  base plus a small MND bonus and ignores MAB/Magic Damage; the DoT ticks through the same
  `tick_mob_effects` path as Bio and Poison, and the defence cut is read by
  `World.player_attack`. Dia is unresistable, so its duration no longer shortens with a
  weak caster's Magic Accuracy.
- **A landed spell now builds enmity and makes the monster fight back.** Monsters keep a
  CE+VE total per player (`ZoneEntity.enmity`). The first source of hate gets retail's
  200 CE + 900 VE claim bonus, so one Dia pulls an idle monster; damage adds four hate per
  point, a pure enfeeble 100 and Provoke 1,800. The highest total is the monster's target,
  and if that player dies, zones out or runs past 30 yalms the monster hands itself to the
  next name on the list instead of resetting. Melee swings, weapon skills and Drain/Aspir
  use the same list.
- **A finished spell plays the client animation id, not the spell id.** They are different
  for 674 of the 928 rows (Breakga is spell 365 and animation 271, Monomi Ichi 318/356), so
  the old packets played the wrong effect. The start-cast
  line is also printed once now: the client's 0x028 start message is left at None while the
  server's own "You start casting ..." chat line carries the self message.
- **Spells with no modelled effect no longer invent damage.** A base-0 spell with no effect
  entry (Virus, Burn, the Absorb line, ...) reports "has no effect" instead of "takes 0
  points of damage", and a base-0 enfeebling no longer becomes a fixed-cost nuke.

## Unreleased — Limbus R30, all five families, both characters

- **Every Limbus family now ends at its top tier, at Rank 30.** Justice → Magnificent → Duty,
  Hope → Perfection → Revelation, Trust → Prestige → Sworn, Bravery → Intrepid → Indomitable,
  Mercy → Grace → Clemency: 25 pieces (items 24122–24194) in migration 99, with the base
  modifiers parsed from each piece's stat line, granted to Onedough and Twodough carrying the
  rank-30 / tier-3 augment block — the same exdata shape Odyssey uses.
- **`//r30` answers for Limbus as well as Odyssey.** `data/limbus_r30.json` holds the top tier and
  every Rank 30 row; the server lookup, `docs/limbus-r30.md` and the migration are rendered from
  it by `tools/gen_limbus_r30.py`, whose `--check` fails when they drift.
- **The libraries now carry the suits where the community actually wears them.** Every
  `gearswap/*.lua` gains a `local limbus` build table (one copy per augment choice a set needs)
  and a `sets.Limbus` container; `--lua` also puts Duty into the MNK/THF/DNC/BST/PUP TP sets,
  Revelation into BRD's 3/5 and NIN's TP/hybrid, Sworn's Phalanx-received build into PLD/RUN fast
  cast (Triple Attack into RDM's, head and feet into DRK's TP/hybrid and Resolution/Torcleaver),
  and Clemency's head and feet into SAM/DRG. SCH wears Indomitable's head/body/legs in
  free nukes and helix, body/hands/legs in enfeebles, body/legs in fast cast, the full five
  in Elemental Macc and a new `sets.idle.dt_indom`; Arbatel Loafers +3 and the
  Enhancing/Healing sets stay put. Nyame Path B and the Malignance Subtle Blow slots are
  deliberately left alone — single-hit WSD and TP-feed control still belong to them.
- **Two limits were written down at first; both are now closed.** The per-item augment bundle
  index is no longer unknown — migration 104 and the top entry carry the client's own indices
  (472-496), so the tooltip draws every Rank 30 line. The pieces now carry their real grap
  models too (migration 107; MIds 513-517), so an equipped piece draws instead of keeping the
  slot's previous look.

## Unreleased — kiting keeps the engagement

- **A target leaving melee range no longer sheathes the player.** The client sends its own
  `/attack off` (0x01A category 4) as soon as the target leaves roughly four-yalm auto-attack
  reach, even though retail keeps the engagement out to draw range. The server now ignores that
  first distance-driven packet, re-sends the `0x058` target and the `0x00D` battle stance, and
  keeps swinging whenever the target comes back. A second `/attack off` within 1.5 seconds, the
  new `//disengage` command, a dead target, or the target going beyond 30 yalms still ends the
  fight. `/attack` now refuses a target beyond 30 yalms instead of engaging across the zone.
- **The phase engine no longer wears the idle set on that automatic `/attack off`.** Engagement
  is still immediate on `/attack`, but disengagement follows the server's own `0x00D` animation,
  so range kiting stays in TP gear and a real `/attack off`, target death or zone change still
  sheathes at once.

## Unreleased — Wizard's Rod wears its own model

- **Wizard's Rod (Reforged) was drawing the Kaja Rod's look.** Migration 53 copied the plain
  item's model from LandSandBoat (845, the Kaja Rod / Maxentius blue star-headed club), but the
  weapon's own picture is a gold shaft with a blue orb held by three gold claws. The Bonanza
  weapons have their own model block, 782-797, and 796 is the one number in it nothing used, so
  the rod takes 796 (a distinct model in the install, ROM/365/126.DAT).

## Unreleased — `//job` cleans up after itself

- **A `//job` change now slips the old outfit, pulls the new job's set and tidies the bags.**
  It takes every worn piece off first (the slips only accept loose gear), runs the storage store
  for the old main job, clears room while keeping gear the new job can wear, pulls every item on
  the new job's slips, auto-equips the best set it can find -- including wardrobe pieces such as
  Epeolatry and the RUN grip -- and moves the leftovers into the Mog Wardrobes. Working stock
  stays visible so ninjutsu tools and pet medicines still work.
- **Auto-equip now reads every permanent bag for a job swap** and prefers job-exclusive gear over
  all-job pieces, so a wardrobe weapon beats the starter Onion Sword. It records the real
  container and slot, so a wardrobe-equipped item is valid equipment rather than an inventory
  ghost.
- **New service helper `sort_inventory_into_wardrobes`** moves whole stacks into free wardrobe
  slots, preserves augment extdata, and has a `keep_jobs` mode for the pre-pull tidy.

## Unreleased — a two-handed weapon drops the off-hand

- **Equipping a two-handed weapon now takes the shield or off-hand weapon off, and only a grip
  can go in the sub slot afterwards.** The server enforces the pair itself instead of trusting
  the client: a 2H main clears a conflicting sub, a grip is refused without a 2H main, and
  switching back to a one-hander drops the grip. Hand-to-hand is excluded, so a shield can
  still share it.
- **Job changes validate gear in every bag.** The old check only looked in the normal inventory,
  so a dagger worn out of a Mog Wardrobe survived a job change; that is how a DNC dagger stayed
  on Onedough through SMN and RUN.
- **A model-less item in a weapon slot clears the old look.** Equipping a grip (model 0) used to
  leave the previous dagger's grap in place, so the dagger stayed drawn on the hip even after
  the slot was emptied. Weapon slots now clear; armour still keeps a previous look if its model
  is unknown.

## Unreleased — the mage rings wear their HQ versions

- **Chirich Ring, Stikini Ring and Shneddick Ring are now +1 on Onedough and Twodough.**
  `0096_hq_rings.sql` adds the two missing catalogue rows, upgrades the equipped and in-bag
  NQ rings in place (so the saved outfit keeps its slots) and tops each character up to two
  copies of each +1 ring in free wardrobe slots. The NQ copies are gone. The 22 GearSwap
  libraries now name `Chirich Ring +1`, `Stikini Ring +1` and `Shneddick Ring +1`, so a worn
  set matches what is actually in the bags.
- **Every +1 ring is now in both mains' wardrobes.** `0097_all_hq_rings.sql` adds all 94 rings
  with a +1 variant in the item data -- the Adoulin set, the avatar rings, the low-level
  HQ rings and the three GearSwap rings -- to Onedough and Twodough, two copies each.

## Unreleased — GearSwap has a real off switch

- **GearSwap can be stopped for the whole launcher, not just the client whose Gear page is
  open.** The phase header's **Turn GearSwap off** button and a new **Settings → GearSwap** switch
  share one saved preference. Turning it off sends `phase {enabled: false}` to every running
  client, which clears the rule table, pending state set, lock, pins, kiting, resting and focus,
  so no action packet is held and no automatic set goes out. Manual **Wear set** and the set
  editor still work. Turning it on pushes the saved library and plan to every running client
  again. It starts off on a fresh profile, and a client launched while it is off does not get
  auto-swapped.

## Unreleased — character designs you can change in game

- **`//character model` changes a character's race, face, hair colour and size, live.** The 48
  designs of each race are numbered with size fastest: Hume 8 is Face 2 / Hair A / Medium, and
  `mithra random` picks face/hair/size inside that race. `face 2 hair a size m` names the parts.
  The server writes `characters.race/face/hair/size` (migration 93 splits the old combined face
  byte, preserving every existing look), repaints the player's own 0x051/0x067/0x00D/0x01B
  blocks, and respawns the 0x00D entity for nearby clients.
- **A Design page in the Rust launcher** shows the character, race/face/hair/size controls, the
  variant number, the look byte and the exact in-game command. Apply calls a new
  `PATCH /characters/{id}/design`; the service's design listener updates a running client.
- **Real previews from the client's DAT renderer.** `tools/capture_character_previews.py` parks a
  spare sub-account at the character-select screen, writes one design into its row, restarts the
  client and captures the model the game builds. The page uses those images and falls back to the
  vector model where a capture is missing. `tools/character_design.py` edits the same fields
  offline.
- Tests: `test_design` covers the look byte, variants, legacy rows and the migration;
  `test_service`/`test_api` cover validation and ownership; `test_world` covers the command and
  the repaint packets.

## Unreleased — every visible item carries its look

- **`items.model` is now the grap model for every visible item, and gear added later is stamped
  automatically.** `items.model` is what the client draws; migration 66 wrote 0 and several
  imports wrote LandSandBoat's small MId, so a piece could be equipped (stats, icon, tooltip,
  EquipViewer) and still render as the previous look. Migration 95 fills all 364 visible armour
  rows and the six missing weapons from LSB's MId (armour is slot base + MId; a reforged piece
  uses its tier's MId, with DressUp as the fallback, the same rule migrations 91/94 applied by
  hand). It also creates `item_models` and triggers on `items`, `char_inventory` and `char_equip`,
  so a gear grant, a shop/migration insert or a clone stamps the real model as the row goes in.
  `tools/gen_item_models.py` regenerates the table and `tools/item_models.py` repairs/reports an
  existing database; the server logs a warning if a visible item still has no model. Four weapon
  rows have no MId source (Pole Grip, Utu Grip, Exeter, Duban); the audit names them, and grips do
  not render in the grap list anyway.
- **`clone_character.py` repairs and audits the copied outfit.** The copy runs the repair inside
  the transaction and prints the repaired count; worn/owned items that still have no model are
  named, and `--strict-models` rolls the copy back instead of leaving invisible gear behind.
- Tests: `server/tests/test_item_models.py` checks the known models, that no armour slot is left
  at 0, the item/inventory/equip triggers and the repair/audit helpers; the style and stats tests
  use the corrected grap ids (Hachiya 4184, Atrophy 4168, ...).

## Unreleased — the Red Mage JSE set renders

- **Atrophy, Vitiation and Lethargy armour now show on the character.** Migrations 66 and 92
  imported the reforged RDM sets with `model = 0`, and the server skips a zero model when it
  builds the grap list: the gear was equipped and its stats applied (icon, tooltip and EquipViewer
  all showed it), but the head, body, hands and legs stayed at the default look. This is the same
  placeholder migration 91 fixed for Dark Knight, which is why Twodough's cloned DRK gear rendered
  and the RDM set did not. Migration 94 gives each piece the look of its original tier — Warlock's
  for Atrophy +4, Duelist's for Vitiation +4, Estoqueur's for Lethargy +3; migration 95 then
  applies the same rule to every visible item.
- Tests: `test_stats` checks the fifteen model ids and `test_style_emotes` checks the five Atrophy
  slots on the grap list.

## Unreleased — a job change releases the weapon lock

- **Changing jobs releases the gear lock and the weapon pins, wherever the change happens.**
  The 0x01B job block's main and support job are compared as a pair, so a support-job-only change
  counts too; the full **Lock** holds the set that belonged to the old job and blocked the new
  job's weapon, and it now comes off with the pins, kiting, resting and focus. The new state's set
  goes out after the client settles, the same path a zone uses. A plan push that carries a new job
  or a different character releases them as well, so a relog, a mule or a launcher push that sees
  the new job first cannot leave the old weapon pinned. The docs and the Gear page's hint say so.
- Tests: `tests/phase_job_test.sh` feeds real 0x84-byte 0x01B blocks to the addon harness and
  checks the main change, the support change, a repeated block (locks kept) and the plan paths.

## Unreleased — a second character can start from the first

- **`tools/clone_character.py` copies a whole character save onto a mule.** Jobs, level, sub
  job, exp, gil, merits, Home Points, inventory, storage, locker and the worn outfit are replaced
  in one transaction, with a pre-clone database backup and a row-level check that the two
  characters now match. Twodough's first copy gave it Onedough's 22 job levels, 1,000,000,146 gil,
  33 merit rows, 122 Home Points, 313 inventory rows, 319 storage rows, 102 locker rows and the
  same 15-piece Dark Knight outfit.
- **Log the target out before copying, and relaunch the client afterwards.** A prepared lobby
  hand-off or a parked zone-change session keeps the old character dict through the next login, so
  the client would show level 1 and fail every equip check even though the database was updated; a
  fresh client launch after the copy (or a server restart) reads the new row.

## Unreleased — magic reads gear, and Fast Cast/Store TP tick

- **Elemental nukes now use Magic Atk. Bonus, Magic Damage and elemental skill.** Spell
  damage was `base x multiplier + level/2` and read no gear at all. It now adds dINT, the
  caster's `MATT`/`MAGIC_DAMAGE`, and a Magic Accuracy resist multiplier built from the
  spell's skill, `MACC`, caster INT, target level and `MEVA`; the target's `MDEF` reduces
  the result. Fire III on a geared BLM moves from a flat 344 to a number that follows the
  gear, and an under-geared caster resists for less.
- **Enfeebles use the same Magic Accuracy roll for duration**, so MACC/MEVA/skill move
  Slow and Paralyze instead of every spell always landing at full duration.
- **Fast Cast and Store TP were stored but never read.** Cast time now follows the merged
  `FASTCAST` modifier (50% cap, 0.5s floor), and TP from a landed hit follows `STORETP`.
- **Refresh/Regen from gear already ticked** through `tick_regen`; `test_world`'s
  `test_gear_refresh_mod_ticks_mp` covers the merged modifier dict.
- Still not modelled, and now listed in `docs/combat-damage.md`: elemental affinity/SDT,
  magic burst, casting-time gear, status potency/duration gear, Subtle Blow and Regain.

## Unreleased — reforged gear carries its real stats

- **Equipment now contributes Attack, Defence, HP/MP and the attributes.** `equipped_mods` always
  joined the worn items to `item_mods`, but LandSandBoat leaves the +3 empyrean and +4 artifact/
  relic armour as "Not implemented" rows with no modifiers, and the prime scythe and belt added by
  earlier migrations had none either. The client drew the real tooltip from its DAT while the
  server saw bare slots: the status screen showed `STR 89 +3`, `Attack 706`, `Defence 275`, and
  the only bonuses came from accessories. `0092_reforged_item_data.sql` imports the client's own
  stat lines for all 330 reforged pieces plus `Final Sickle (Reforged)` and `Plat. Mog. Belt`:
  5,775 `item_mods` rows and 124 `item_skill_bonus` rows. Wearing the same DRK set now reads
  `STR 89 +194`, `Attack 1444`, `Defence 1248`, HP 2519 and MP 1195.
- **Damage taken was in the damage path all along; the data was not.** `combat.damage_taken`
  applies `DMG`/`DMGPHYS`/`DMGMAGIC` and the II variants after the roll, and the reforged empyrean
  pieces now carry their `Damage taken -X%` lines (Heathen's Cuirass +3 is -13%). The belt and
  Tathlum add -6% DT, the earrings -5% MDT.
- **`HP+10%` / `MP+%` now raise the maximum.** `HPP` and `MPP` were missing from the stat sheet;
  the percentage is applied after the flat HP/MP bonus. `Plat. Mog. Belt` uses it.

## Unreleased — gear libraries save in place; the Follow refresh stops blinking

- **Weaponsets and other edited sets survive a logout.** The Gear page kept an edited library only
  in memory: **Apply set** updated the window, **Save version…** wrote a timestamped export, and a
  logout discarded the set because the job default was read from disk again. Edits to a bundled
  job library are now written back to `gearswap/<JOB>.lua` as they happen, with the first copy
  kept as `gearswap/<JOB>.lua.bak`. Imported GearSwap files stay read-only and the toast says to
  use **Save version…** for them.
- **The Gear page reloads its library after a relog on the same job.** It remembered the last
  auto-loaded job and skipped the second load, so signing back in on the same job left the page
  with no library until the job changed or the page was reopened.
- **The Follow card's Refresh no longer blinks every two seconds.** The background poll set the
  same state the Refresh button uses for its spinner, so the icon cycled into a spinner on every
  tick; it also restarted on every instances refresh. The poll is silent now, skips hidden
  windows, does not overlap itself, and the button only spins when clicked. (The Control room is
  polling loopback control ports, not the Fanxi server API.)
- **Every item the 22 GearSwap libraries reference is now in Onedough's bags, and every job's
  reforged AF/relic/empyrean set is complete.** Migration 66 was extended after this database had
  already run it, so 255 reforged AF (+4), relic (+4) and empyrean (+3) pieces plus Creed Baudrier
  never reached the character. `0089_gearswap_reforged_grant.sql` grants those library items;
  `0090_gearswap_full_sets.sql` adds the 55 set pieces the server did not know yet and grants the
  64 set pieces the libraries do not name, so all 22 jobs have their full 15-piece reforged sets.
  Dark Knight's own 12 library pieces were already owned. The set rows started as placeholder
  data: the item ids, names, slots and job masks are real; migration 92 now fills their
  `item_mods` from the client's stat lines.
- **Reforged Dark Knight armour now renders on the character.** Migration 66 stored the reforged
  sets with `model = 0`, and the server copies `items.model` into the character's grap list when a
  piece is worn, so an equipped Ignominy Cuirass stayed at the default body look. Migration 91
  sets the real grap ids from Windower's DressUp tables: Ignominy (Chaos) 4174/8270/12366/16462/
  20558, Fallen's (Abyss) 4175/8271/12367/16463/20559 and Heathen's (Bale) 4385/8481/12577/16673/
  20769. The body now draws in-game; the other jobs' reforged pieces still need the same pass.

## Unreleased — Onedough's Prime weapons and Dark Knight gear

- **The twelve Prime weapons missing from the database are in, and Onedough has all sixteen.**
  `Varga Purnikawa`, `Mpu Gandring`, `Caliburnus`, `Helheim`, `Foenaria`, `Gae Buide`,
  `Kusanagi`, `Lorg Mor`, `Pinaka`, `Earp`, `Loughnashade` and `Duban` now carry their iLvl 119
  III ids, job masks, slots, weapon stats and the two known Prime weapon skills. They join the
  four already present (`Laphria`, `Spalirisos`, `Dokoku`, `Opashoro`).
- **Dark Knight AF/relic/empyrean sets are granted.** Migration 66's list grew after this
  database had run it, so Onedough had none of `Ignominy`, `Fallen's` or `Heathen's`. The twelve
  pieces the DRK GearSwap library names are now in wardrobe 2.
- **Ankou's Mantle has all ten DRK builds.** The cape augment library gains Dark Knight (item
  26253) with the fast-cast, PDT, MDT, max-HP, DT, TP, M.Acc, STR-WS, INT-WS and enmity builds;
  the existing cape becomes `tp` and nine augmented copies sit in wardrobe 3.
- Migrations: `0087_prime_weapons_drk_gear.sql`, `0088_drk_capes.sql`; `docs/capes.md` lists the
  DRK blocks. Tests: `server/tests/test_capes.py` (10/10).

## Unreleased — no duplicate characters after a relog

- **A relog no longer inherits the previous character on a recycled UDP port.** The zone login
  reused whatever `ZoneSession` sat at the client's address. The OS recycles local ports, so when
  a multi-box mule was force-quit and another client (or the same one) relaunched onto its old
  port, the new session kept the old character record: its name, looks, gear and database id.
  A six-mule relog drew two Onedoughs and two Twodoughs. `C2S 0x00A` now only continues a real
  hand-off — the lobby's prepared session or a recent zone change — and every replaced session is
  despawned before the new one appears. Legacy hand-offs keyed by content id still resolve.
- **A force-quit character leaves the zone.** A zone session has no TCP connection to watch, so
  the server now treats sixty seconds of silence as a disconnect: the character is despawned from
  the other clients, its player targid is freed, its hand-off is forgotten and its last position
  is saved. A zone change keeps its own thirty-second window and its advanced cipher instead.
  This is what stops a killed client from remaining in everyone else's world as a frozen twin.
- **Despawns use the targid the client knows.** If a character's replacement session had a
  different targid, the old despawn could miss; presence now replaces the copy the observer
  actually holds.
- Tests: `server/tests/test_presence.py` drives the real clear `0x00A` path (content id and
  database id), the recycled-port relog, the zone-change cipher hand-off and the idle reap.

## Unreleased — dual wield and Utsusemi count

- **Dual wield attacks with both hands.** An attack round used to resolve a single main-hand
  swing, so a Ninja (or any job with the Dual Wield trait) never swung its sub weapon. The
  stat sheet now builds a second fighter for the off hand when both slots hold one-handed
  weapons and the trait is active: its own weapon damage and skill, half-STR Attack and the
  off-hand 95% hit-rate cap. A round sends a main-hand `0x028` (sub-kind 0) and an off-hand
  one (sub-kind 1), and the round delay is `(main + sub) × (1 - Dual Wield%) / 2`, so the
  swing timer and TP per hit follow the reduced per-hand delay. A shield or a two-handed
  main hand still means one swing.
- **Utsusemi's icon counts the shadows.** The status packet always carried Copy Image (66),
  whose icon is the "1" badge, so a fresh Utsusemi looked like a single shadow and stayed
  that way. The icon is now the count itself — 66 for one, 444 for two, 445 for three and 446
  for four or five — and it moves down as each shadow absorbs a hit. The effect id stays 66,
  so the action and chat result are unchanged.
- Tests: `server/tests/test_combat.py` covers the off-hand sheet, delay and 95% cap;
  `server/tests/test_world.py` drives a NIN attack round through the real tick;
  `server/tests/test_effects.py` checks the icon countdown.

## Unreleased — emotes and style lock

- **Emotes work.** `/wave`, `/nod`, `/bow`, `/goodbye`, `/dance` and the rest of the client's
  emote commands sent `C2S 0x05D` and then stopped: the zone server had no handler, so no
  animation and no text line ever came back. The server now reads the emote, its mode and its
  parameter, and broadcasts `S2C 0x05A` to the caster and every player in the zone. Job emotes,
  `/bell`, `/salute` and `/hurray` fill in the parameters the client expects. `/bye` is a
  host-side alias for `/goodbye`, which is the name the client's own command table actually has.
- **`/lockstyle on|off`, `/lockstyleset #` and `/lockstyle` work.** The client's `C2S 0x053`
  was dropped as an unknown packet, which is why gear swaps kept redrawing the character (the
  "blinking"). The server now keeps a locked appearance separate from the equipped gear: the
  `characters` row gains `style_lock` and one model column per visible slot (migration 0085),
  `0x051`/`0x067` repaint the character after a change, `0x009` messages 267-270 answer the
  command, and `0x11C` reports items that could not be locked. While locked, every `grap_list`,
  login packet and `0x00D` update uses the locked models, so a GearSwap burst changes the stats
  but not the look. The lock survives a relog / zone change (`0x053` mode 1) and a job change
  clears it, as retail does.
- Tests: `server/tests/test_style_emotes.py` drives both handlers, the packet layouts, the
  persisted style and the two-player emote broadcast.

## Unreleased — throw protection

- **Valuable ammo can no longer be thrown.** The control addon guards outgoing ranged actions
  (`0x01A` category 16). Only stackable ammo with the Throwing (27), Archery (25) or
  Marksmanship (26) weapon skill is allowed; Tathlums, orbs and stack-1 throwing weapons are
  equipment, not ammunition. A safe shuriken/stone from the bags is hot-swapped in (or
  arrows/bolts/bullets when a ranged weapon is equipped), the action is held until the equipment
  echo arrives, and the original ammo is restored about 1.2 seconds later. If no suitable ammo
  is in the bags, the action is blocked with a chat message.

## Unreleased — ability cards and weapon picks

- **Job ability cards.** The Gear page has a full-width **Job abilities** card with a default JA
  set and one row per ability the current main/sub job can use. The list comes from the client's
  0x0AC command list (`job_abilities`), so it follows the live job pair and their levels. A row's
  set wins over the library's `sets.JA.<name>`; an empty row uses the default JA set, then the
  library's `precast.JA`. The action id is the ability's low nine bits for every `0x200`+ type
  (not only `JobAbility`), which also fixes library `sets.JA` rules for sambas, waltzes, runes and similar
  non-`JobAbility` types.
- **Weapon sets pick from the character's own bags.** **New set / Edit** on the Weaponset card
  opens a weapon-only form whose Main, Sub, Ranged and Ammo pickers list the actual items the
  main job can equip. The scan covers all 18 client bags (inventory, Mog Safe, Storage,
  wardrobes, satchel/sack/case) and every slot 1-80, and it compares the client's **1-based**
  job mask (bit 13 is NIN) instead of the server item table's 0-based mask. Dokoku, Kikoku and
  Nagi now appear, while SAM-only great katanas and Utu Grip no longer do. Main and Sub share a
  copy pool: selecting a single-copy weapon in one slot disables it in the other (marked "used
  by Main/Sub"), while a second copy unlocks dual wield. Grips are offered only with a
  two-handed Main; off-hand weapons and shields only with a one-handed or empty Main, and a
  saved Sub that no longer fits is cleared. Ammo shows its stack quantity, and every picker
  includes items already worn. The list comes from the new `weapons` control command; the
  hidden `//locker` is not a client bag.
- **The Weaponskills card spans its own row**, so its per-WS set names are readable instead of
  clipped in a half-width card.

## Unreleased — Gear tabs

- **The Gear page is split into Sets and Manage.** **Sets** keeps the live gear, the live job and
  the state groups; **Manage** holds the GearSwap library browser, the set editor and the saved
  versions, plus a **Job defaults** picker for all 22 bundled libraries. The tab strip shows the
  loaded library and set count, marks Sets while auto-swap is on, and switches to Manage after a
  `.lua` import.

## Unreleased — spells and Home Points

- **Buffs and debuffs land on the right target.** A finished self spell was sent as a
  basic-attack result with message 1, which is why Monomi and Utsusemi printed
  "hits itself for 0 damage".  Self buffs now carry their status-effect id in the action
  value with message 230 and put the icon in `0x037`; enfeebles carry the effect id with
  message 237 and become a `world_npcs`-style effect on the monster.  Utsusemi keeps a
  3/4/5 shadow count and consumes one per hit (message 31), Blind lowers accuracy, Slow
  lengthens the swing interval, Paralyze can skip a swing, Sleep/Stun stop the mob,
  Bind/Weight control movement, Attack Down lowers damage, and Poison/Bio tick every
  three seconds.  Sneak and Invisible stop aggro, and the new `game/effects.py` table
  covers the ninjutsu, black-magic enfeeble and common enhancing families.
- **`/heal` works.** `C2S 0x0E8` was not handled at all, so pressing heal did nothing.
  It now toggles rest, recovers 5% HP/MP every three seconds, and stops on damage, a cast,
  an attack or movement.
- **Warp and K.O. use the set Home Point.** Warp, Warp II and Retrace looked for a crystal
  registered in the current zone; South Gustaberg has none, so Warp refused even though
  the character had a Home Point set in Bastok Markets.  All three now send the character
  to `characters.home_*`, and a K.O. without a Raise returns there too.
- **Home Point crystals open their menu on a fresh database.** Only the live database had
  `world_npcs.hp_index` filled in, so a newly initialised one treated every crystal as
  "set your home point here".  Migration 0084 restores the menu indexes, and `//hp` now
  numbers destinations by the same `hp_index` the client's menu uses (it accepted a
  different `home_points.idx` before) and also accepts a zone name.
- Tests: `server/tests/test_effects.py` drives the real handlers and decodes the `0x028`
  result for the buff, debuff, Utsusemi, poison, Warp, `/heal` and sneak-aggro cases.

## Unreleased — the state groups

- **The Gear page now groups the plan by what the player is doing**: Engaged (TP + default WS),
  Kiting, Weaponset, Weaponskills, Resting, Spells and Idle. Each group has its own set pickers;
  the header keeps the live state/set and the rule counts. The old single Precast/Midcast/Idle
  and Idle modes cards are gone.
- **Kiting and resting are forced states.** Kiting wins over engagement and movement until it is
  switched off; resting is a manual state because this server has no rest packet. The host tracks
  both (`xi.phase.kiting`, `xi.phase.resting`) and the UI/`//gs` drive them.
- **Weaponsets and per-slot pins.** A weapon set is main/sub/ranged/ammo, written with a new
  weapon-only editor form, worn with **Wear**, and pinned with **Wear & lock**. Pinned slots are
  filtered out of every set the engine sends (precast, midcast, engaged, idle, kiting, resting,
  focus); the EquipViewer draws a red border on each pinned cell. The same is available in game:
  `//gs lock main, sub, ranged, ammo`, `//gs unlock …`, `//gs rest on|off`, `//gs kite on|off`,
  `//gs focus auto|dt|pdt|mdt|eva|meva`. The control addon blocks the line before the server sees
  it and confirms in chat. Job changes answer with the pins, kiting, resting and focus cleared.
- **Per-WS cards and a default.** Every `sets.WS.*` WS gets its own set picker; empty uses the
  library's WS set, then the default card. The TP set returns on the WS result packet, whether it
  lands or misses (the existing 0x028 restore path).
- **Spell defaults and per-spell overrides.** A midcast default is worn for every spell (instead
  of the library's skill sets); per-spell overrides (picked from the current job's spell list)
  win over it, so macc/mab/magic-skill sets can be selected per spell. The host builds the rule
  with the spell-table index and tracks the action id.
- **Idle focus.** DT, PDT, MDT, Eva and Meva sets are configured under Idle and selected with the
  focus picker; focus wins over town/field but not over engaged, movement or kiting.
- New host/control API: `phase_kiting`, `phase_resting`, `phase_focus`, `phase_lock_slots`,
  `job_spells`, and the `phase` options object (`kite`, `rest`, `precast`, `midcast`,
  `default_ws`, `focus`, `ws_overrides`, `spell_overrides`).

## Unreleased — idle states, lock and job changes

- **The idle state machine has four states and a lock.** Engaged follows the server's own
  animation for the player (`0x00D`, General block byte `0x1B`) as well as `/attack` and
  `/attack off`, so a target that dies or a stance the client drops locally no longer leaves the
  engine in TP gear; movement still follows the position sampler; idle splits into **idle.town**
  and **idle.field** from the zone-in packet (`0x00A`, zone id at body `0x2C`), with the new set
  going out 1.5 s after the client has loaded the area. The Gear page's **Active gear** card has
  a **Lock/Unlock** button: locking holds the set that is on and suppresses every automatic swap
  (precast, midcast, engage, movement, zone), and the card names the state and the set that is
  active.
- **Precast · Midcast · Idle is the panel, and Idle modes is its own card.** The Gear page picks
  the engaged set in the phase card and the town, field and movement sets in **Idle modes**; the
  `now:` badge is the host's own state and set name. The launcher resolves each choice against
  the loaded library, so a library without `idle.field` (the bundled ones carry `idle.town`,
  `idle.dt`, `idle.pdt`, …) still gets a sensible field set on the first push.
- **Magic and job-ability rules now match the action the client actually sends.** Spell rules
  were keyed by the spell record's `recast_id`; the `0x01A` carries the spell-table index instead
  (Monomi: Ichi 318, not 425), so every ninjutsu, most songs and blue magic had no midcast rule.
  Job abilities were keyed by the client's resource id (Yonin 760); the action id is that minus
  `0x200` (248). Weaponskills keep their resource id. A cast made while engaged now wears the
  fast-cast set before the action, the midcast set behind it, and returns to the engaged set —
  verified with Monomi: Ichi on NIN, before and during combat.
- **A job change updates the engine and the launcher.** The host watches the `0x01B` job block,
  notices when the plan came from a job-named default (`gearswap/NIN.lua`) and rebuilds it from
  the new job's file once the bags settle; the launcher polls the live job, reloads the job's
  default library, and re-pushes the plan. The Home dashboard and Live job card use the running
  client's job, level and zone instead of the lobby snapshot, so a Mog House job change or a zone
  shows up within a few seconds.
- **The weapon stays drawn through a cast.** Casting sheathes the client's weapon; a refused cast
  (no MP, no target) had no result packet to redraw it. The server re-sends the assist target
  (`0x058`) and the General animation (`0x00D`) after a refused or finished cast and once every
  ten seconds while engaged. Ninjutsu no longer checks MP (skill 39 is forced to zero in
  `cast_magic`, matching `0081_ninjutsu_mp.sql`).

## Unreleased — ninja

- Ninjutsu no longer costs MP. The imported spell rows carried a scroll/tool id in the `mp`
  column (Monomi Ichi 2553, Katon Ichi 1161, ...), so a 99 NIN with 404 MP was refused every cast:
  "You do not have enough MP for Monomi: Ichi." Migration `0081_ninjutsu_mp.sql` zeroes the whole
  ninjutsu skill (39), and `cast_magic` no longer checks or spends MP for it; Utsusemi still
  consumes its fuda and refills from the locker.
- Ninja's eleven Andartia's Mantle builds now carry their real augment blocks.
  `0082_nin_capes.sql` turns the wardrobe copy into the TP build and adds the other ten to the
  first free bag slots; `//cape` reads the item's job, so `//cape dw Andartia` works.
  [docs/capes.md](docs/capes.md) lists every build.
- Unity gear is augmented too. The five Unity items in the default libraries (Unmoving Collar +1,
  Odnowa Earring +1, Gelatinous Ring +1, Ghastly Tathlum +1, Loess Barbuta +1) carry the client's
  Rank 15 single-path `AugmentBundle` block in `char_inventory.extra`; `0083_unity_augments.sql`
  writes them, `//augment A <item>` rewrites one, and
  [docs/unity-augments.md](docs/unity-augments.md) lists the bundle indices.

## Unreleased — equipment

- Logging back in restores the whole saved outfit again. `restore_equipment` looked the item up in
  inventory slot order only, so every piece saved from a wardrobe, satchel or case was skipped:
  a character came back from a relog with its weapon, a couple of armour pieces and empty ammo,
  ear, ring and waist slots. The lookup now uses the container and slot the outfit was saved
  with, so the wardrobe pieces come back too.
- **Precast and midcast are now timed like GearSwap.** The host holds the player's outgoing
  `0x01A` action packet out of its buffer, sends the precast `0x050`s first, then the action with
  the midcast `0x050`s right behind it, and puts the return set back when the action's result
  (`0x028`) arrives. Weaponskill and job-ability gear is therefore on before the server rolls the
  damage or resolves the ability, and a spell's fast-cast gear is on before the packet the server
  times the cast from. The rules come from the loaded GearSwap library: `sets.WS.<name>`,
  `sets.JA.<name>`, `sets.precast.FC`/`sets.precast`, `sets.midcast.<skill>` by the spell's skill,
  `sets.engaged.tp` on `/attack`, `sets.idle.town` while disengaged and standing still, and
  `sets.idle.movement` while disengaged and moving (the control addon samples the player's
  position, so an action's aftercast returns to the state you are in), plus a return set as the
  fallback. Set entries written as `{name = ..., augments = {...}}` are resolved by name now
  instead of being skipped.
- Changing gear while engaged no longer sheathes the character. The client drops its battle
  stance when the equipment block arrives (the animation byte only rides in the General block of
  `0x00D`), so the server now re-asserts the engagement (`0x058` assist target) and the animation
  after an equipment batch while engaged. The engine also stops guessing the engaged state from
  the entity's `Status` byte - that is the attack animation, not the engagement - and follows the
  `/attack` and `/attack off` packets again. New control commands `phase` and `phase_status`, a
  **Precast · Midcast** panel on the Gear page, and a new `xi.phase` addon API (`host/addons/phase.c`).
  A result that never arrives restores the return set after six seconds.
- A gear swap is now handled as one batch. The client's `0x050`s are read in one pass and the
  follow-up the client needs after an equipment change (looks, spell bits, the ability tables,
  stats and status) is sent once for the batch instead of once per slot. The old per-slot copy
  put about a kilobyte in front of the later `0x050` echoes, and the session serves one packet
  per client ack, so a full swap arrived slot by slot. The outfit is written to the database
  once per batch as well.

## Unreleased — job traits

- Job traits are now real server state. `traits_data.py` carries the game's trait ids, job/level
  gates, ranks and modifier values; the main job and support job each contribute the highest rank
  they have reached, and an equal rank from both does not stack. The trait modifiers are merged
  into the equipment modifier dict, so Attack Bonus, Defense Bonus, Accuracy/Evasion Bonus and
  Max HP/MP Boost reach the stat sheet, the status packet and combat through the existing path.
- `0x0AC`'s fourth block (bytes 192..223) now carries the client's job-trait ids instead of
  always being zero, and a new `//traits` command prints the current pair's traits, their ranks
  and modifier values and re-sends the command data.
- The client's Abilities menu is built from a saved command-id list, not the `0x0AC` bitmap.
  `host/addons/hooks.c` now appends the trait ids to that list as `0x600 + trait id`, which is
  what makes the **Job Traits** page populate. **Rebuild `host64`** (Settings → Build game, or
  `python3 tools/build_posix.py host64 --game <folder>`) and restart the client. The hook log now
  prints e.g. `command list rebuilt from 0x0AC: 53 entries (18 job traits)`.
- Auto Regen (WHM 25/76, RUN 35/65/95) and Auto Refresh (PLD 35, SMN 25/90) tick once every three
  seconds while alive: +1/+2/+3 HP and +1/+2 MP per tick. They are passive modifiers, not status
  effects, so the client draws no icon; gear with Regen/Refresh adds to the same modifiers. Auto
  Refresh is not a Red Mage trait (RDM has the Refresh spell). Blue Mage set-spell traits and
  merit-gated traits are deliberately left out until that state exists.
- A job change now recomputes the stored max HP/MP, so Max HP/MP Boost takes effect immediately
  rather than after the next zone or gear change. Bought HP/MP merits are part of that
  computation, so a recompute no longer drops them.

## Unreleased — defences and vitals

- Parry, guard and shield block now proc, using retail's rate formulas (5-25% for parry
  and guard, shield-size base plus `0.2325` per point of skill lead for block) and a
  documented damage reduction.  Hand-to-hand players guard; shield users block; anything
  but hand-to-hand can parry.
- Max HP and MP come from LandSandBoat's race/job/level grade tables plus gear HP/MP
  instead of a flat `+20 HP, +10 MP` per level.  The `0x061` packet, the bars and the
  damage code all use the computed maximum, and the stored row is refreshed at zone-in,
  on gear changes and on level-up.
- `item_shield` (migration 80) carries shield sizes, so shields are recognised by size
  rather than by slot.

## Unreleased — retail combat

- Physical damage now follows retail's model instead of `level * 2 + rand(1..6)`: base damage
  is `weapon DMG + fSTR`, multiplied by a pDIF chosen from the Attack/Defense ratio, weapon
  type, critical state and level difference.  `fSTR` uses the STR-versus-VIT table, and the
  Attack/Defense/Accuracy/Evasion numbers are derived from level, job, skills and gear.
- Damage taken is a real stage again: PDT, MDT, "Damage taken" and the PDT-II/MDT-II modifiers
  from `item_mods` apply with retail's 50% cap, the 87.5% overall floor, and Burtgang-style
  bypass.  Nyame now actually protects.
- `item_weapon` and `item_mods` are imported in full from LandSandBoat's data (migration `0080`),
  and base attributes come from its `stats.yaml`/`grades.yaml` via `tools/gen_base_stats.py`.
- The `0x061` status packet finally reports the character's real attributes, Attack and Defense
  instead of the hardcoded `999`s, and the Mog House stat panel does the same.
- Swing timing comes from weapon delay and equipment haste rather than a flat three seconds.
- Fixed migrations `0078`/`0079` so a fresh database (and therefore the test suite) no longer
  fails on the character foreign key.

## Unreleased — Rust/Tauri launcher preview

- Added `launcher-rs/`, a side-by-side native launcher built with Tauri 2, Rust and React. It
  shares the existing `launcher.json`, HTTP API, launch-token hand-off and control protocol with
  the Python launcher, so accounts and characters move between them without migration.
- The Rust core covers config/account vault, server session restore, character creation and
  selection, party launch/stop, live EXP/hr and DPS polling, command/chat console, active gear,
  GearSwap default/import/edit/wear/save-version flows, game discovery, `host64` build streaming
  and the build/game logs.
- The frontend is a dark native-style UI with a signed-out auth screen, Home, Characters,
  Accounts, Control room, Gear, News and Settings. Stored API tokens never cross the Tauri IPC
  boundary; the frontend receives a token-free config view.
- Added an **EquipViewer** grid to the Home dashboard, the Control room's selected client, the
  Gear page's active gear, the selected-set preview and the set editor. It uses Windower
  EquipViewer's 4×4 slot order and defaults (32 px, alpha 230, background alpha 72), updates
  from the live client, shows the ammo count, and draws the encumbrance X from the client's
  `0x01B` flags. Icons are decoded from the player's own DATs by the addon host
  (`res.item_icon_rgba`), fetched through the control port's new `icons` command, and cached as
  PNGs in `<data dir>/icons/`; **Settings → Clear icon cache** regenerates them. GearSwap sets
  are previewed by resolving their item names through the new `item_ids` command, so the set
  editor shows the same grid while it is typed.
- **Wear set** is now atomic. The control addon resolves a whole GearSwap set against one pass
  over the character's bags (instead of a full bag + resources scan per piece) and injects every
  `0x050` in the same frame, the way GearSwap sends its equip burst (a single `0x051` equipset
  when three or more slots change, individual `0x050`s otherwise). The old one-`sleepf`-per-slot
  loop put one piece in each frame, so a set arrived in waves over ~0.3 s and could miss the
  precast or midcast window it was meant for; a 16-piece set now completes in one frame (about
  30 ms round trip). Pieces already worn are skipped, duplicate copies of the same item are given
  out one per slot, and the Gear page reports the pieces worn plus the measured round trip.
- The Python launcher and server are unchanged. The Rust launcher still drives the existing Python
  recompiler build (`tools/build_posix.py`); porting that toolchain is a separate project.

## Unreleased — multibox control panel

### Accounts and mules

- Characters per account are unlimited by default (`FANXI_MAX_CHARACTERS=0`); the old cap is still
  available by setting a number.
- The launcher keeps a vault of signed-in accounts (one API token each, never a password). Add,
  switch, re-sign-in and remove accounts from the new **Accounts** page.
- The **Characters** page lists every mule on the active account and can create more.
- A launch token now names its character, so a multibox client opens the chosen mule rather than
  the first one on the account. Migration `0062_multibox.sql`.

### Control room

- New **Control** page: party roster, Launch / Launch all / Stop, live zone/HP/MP/EXP/hr/DPS table,
  and a command console for `//zone`, `//merits`, `//heal`, `//where`, `//help`.
- Each client starts with its own `FFXI_CONTROL` port and `game-<account>.log`; one client per
  account is enforced by the launcher.
- The built-in control addon gained `metrics`, `command`, `gear`, `equip`, `equip_set` and
  `gearswap` commands. Existing `tools/xi_mcp.py` commands are unchanged.

### Gear

- New **Gear** window: active item per slot, manual equips by name (0x050), GearSwap `.lua` import
  in a sandbox, set flattening and **Wear set**.
- The window reads the client's live main job/level and loads that job's default library from
  `gearswap/<JOB>.lua`; the **Defaults** dropdown loads any of the 22 job libraries, and
  **Import your own…** still accepts a hand-written file.
- **New set…**, **Duplicate** and **Edit set…** open a 16-slot set form, and **Delete** removes a
  set from the working library.
- **Save version…** writes `<character>-<JOB>-YYYYMMDD-HHMMSS.lua` to a folder chosen by the user
  (Downloads by default). Later edits auto-save new timestamped versions to the same folder and
  never overwrite an earlier file; a JSON copy appears in the Control room's **Saved Gear Versions**
  list.
- Migration `0066_gearswap_grant.sql` resolves the 427 item names used by the default libraries to
  real item ids and grants the missing ones to the first character's wardrobes (inventory stays
  free; other permanent bags are a fallback). It also fixes the five `Academics` server names.
  `0068_gearswap_storage_back.sql` returns gear that the storage-slip migration moved into
  `char_storage` to a free wardrobe slot.
- The 22 default job libraries now use 198 augmented JSE cape builds (Ambuscade
  Thread/Dust/Dye/Sap/Resin max augments) mapped by set role (TP, WS, PDT, MDT, DT, max HP, FC,
  Macc, cure, pet, ranged, enmity, waltz). The four Unity accessories and `Loess Barbuta +1` carry their
  fixed max Odyssey augments, and six Reive/Incursion capes carry max Refractive augments.
- Every Odyssey Rank 30 item now has its exact row in `data/odyssey_r30.json`: all four Nyame
  paths, Sakpata's, Gleti's and Agwu's armour (20 pieces) and the seven Odyssey weapons.
  `tools/gen_odyssey_r30.py` generates the `local odyssey` table and a `sets.Odyssey` container
  in all 22 job libraries, [docs/odyssey-r30.md](docs/odyssey-r30.md) and migration
  `0072_odyssey_r30.sql` from that one file, so the copies cannot drift.
- The Gear window marks imported augmented items with `*` (Odyssey armour and weapons with
  `R30`) and shows the selected item's full augment list, including the Rank 30 values and
  cape/Unity builds. Wear set still matches base names; saved versions remain flattened and drop
  the augment arrays.
- `0072_odyssey_r30.sql` adds the ten Gleti's/Agwu's pieces and seven weapons the server did not
  know, and grants them to the first character's wardrobes.
- The server now stores and sends the item `extdata` block: `char_inventory.extra` holds retail's
  `AugmentBundle` layout (kind `03 83`, Rank 30, max-rank tier 3) and, new, the real per-item
  **augment bundle index**. The indices were extracted from LandSandBoat's
  `Exdata::AugmentBundle` table and matched to the Rank 30 rows by content; the method is
  validated by Assassin's Gorget +2, whose bundle 204 decodes to DEX/AGI+15, Evasion+25,
  Triple Attack+4% (its known R25 row). Nyame bundles are 438-457 (four paths), Sakpata's
  413-422, Gleti's 413-417, Agwu's 428-432 and the weapons 393-412.
- `0077_odyssey_bundles.sql` writes those indices into every Odyssey item's exdata and adds the
  Path B/C/D copies of the five Nyame pieces (each with its own bundle), so all four tooltips
  differ. `//augment <index|A-D|off> <item>` rewrites a copy in game.
- Ambuscade JSE capes now carry their real augment block too, not just a label in the Lua file.
  The nine Beastmaster `Artio's Mantle` builds are standard five-slot augments (kind `02`,
  subkind `03`, `id:11 | value:5` words), so the client prints `HP+60`, `Eva.+20/Mag. Eva.+20`,
  `Accuracy+20 Attack+20`, `Weapon skill damage+10%`, the pet lines and the rest. The ids are
  the client's own augment table (the one Magian items use); `HP+60` is id 2 with value 27
  because the value field is five bits. `0078_bst_capes.sql` turns the bag copy into the TP
  build and adds eight wardrobe copies; `//cape <build|list|off> <item>` rewrites one.
  [docs/capes.md](docs/capes.md) lists every build and block, and `tools/gen_capes.py` writes the
  page and the migration from `server/fanxi_server/game/capes.py`.

### Abilities

- Weapon Skills and (server-side) Job Abilities now work. The Abilities menu was empty because
  `0x0AC` was sent once, inside the zone-in burst, before the client built the menu; the bitmap
  reached client memory but no menu read it. The server now re-sends the command data after the
  client's `0x061` stats request and on two short timers, together with the equipment list
  (which triggers the menu rebuild), `0x01B` job info, `0x062` skills, `0x0AB` feat data, the
  incremental `0x1A5` command update and a `0x119` recast table that lists every known ability
  with timer 0 instead of only running timers. Migration `0074_job_abilities.sql` adds the 366
  player job abilities; `0x0AC` advertises the main and support job's abilities.
- The Weapon Skills menu now shows only what the equipped weapon can use, as retail does: the
  main-hand weapon's skill type (or hand-to-hand when unarmed) plus archery/marksmanship for the
  ranged slot, and only skills whose `skill_level` is at or below the character's value for that
  weapon (merits and gear bonuses included). Quested/relic/empyrean/aeonic skills carry
  `skill_level` 0; Fanxi offers them once the weapon skill is mastered (350+, the level-99 band).
  Migration `0076_item_weapon_skill.sql` adds the item `skill` column and maps the 72 weapons in
  the item table to their skill types. The server also rejects a weapon skill that is not on the
  advertised list. A BST 99 with Aymur's `0x0AC` block now carries 14 axe skills instead of all
  210 (verified in client memory as bytes `FF 3F` at the axe offset), and `//ws` refuses the rest.
  The 2025-07-03 client's Abilities menu does not read those bits directly: it keeps a separate
  command-id list (at `[0x106323a8]+0x160`, count at `+0x1760`) that it saves in `aix.dat`, so an
  existing profile kept drawing every saved weapon skill and a fresh profile drew nothing.
  `host/addons/hooks.c` now rebuilds that list from each `0x0AC` packet on the game thread, which
  makes both the field/engaged menu and the Mog House Abilities menu show exactly the advertised
  weapon skills and job abilities. The list is rebuilt at zone-in, after `//abilities`, and after
  a weapon change; a client started before this change needs one restart to load the new host64.
- Added `//ja <name>`, `//job <job> [sub]` and `//abilities`. C2S action `0x09` is handled: the
  response is a `0x028` Ability Finish (kind 2, the ability's animation, message 100), and
  Provoke, Benediction, Chakra, Meditate, Convert and the Curing/Healing/Divine Waltzes have
  effects. Recasts are tracked by recast id in `0x119`. The command-list rebuild above also
  fills the 2025-07-03 client's Job Abilities submenu: with the rebuilt list it lists the main
  and support job's abilities instead of "No abilities available." `//ja` remains a shortcut.

### Combat

- Engaging with `/attack` or Provoke now puts the character in the drawn-weapon battle stance:
  the server re-sends the self `0x00D` with animation byte `0x1B` set to 1, so the client plays
  the draw animation and the swing animations for the `0x028` actions that follow. Disengaging,
  a dead target or a dead player sends animation 0 to sheathe. Monsters switch to animation 1
  while they have a target too. The `0x058` engage acknowledgement is still sent first, as
  LandSandBoat does; the animation update is the part that was missing.

### Server

- New `//r30 [item]` chat command: with no argument it lists the 27 Odyssey items, with a name it
  prints that item's Rank 30 rows (every Nyame path, or the single row for the other sets and
  weapons). `server/fanxi_server/game/odyssey.py` reads `data/odyssey_r30.json`.
- `create_character()` returns the character it created (important with several mules).
- Wardrobes no longer open blank. `0x01D`'s `Flags` field is the client's complete
  container-ready mask, not a delta: item moves, shop refreshes and storage/locker changes now
  send all 18 container bits. Previously they sent only the two bags that changed, so every
  other bag — including all eight Mog Wardrobes — drew empty until an item was moved into it.
- Character-specific item migrations no longer break fresh databases with no character 1.
- Entering a Mog House refills HP and MP and removes every status effect; logging back in there
  rests the character too. `docs/world.md` describes the rest.
- Mog House exits now follow the city you are in: the login packet names the right city model
  and exit bit, and the client's `0x05E` menu pick lands you at that area's Mog House door
  instead of always showing and using Jeuno's exits.
- The HP/MP gauges (party line `0x0DF`, status `0x037`, self `0x00D` and login `0x00A`) now divide
  by the character's current maximum, so a partial 7240/10149 no longer reads as a full bar.
- Added `//storage store <job>` and `//storage grab <job|all>`. Store sweeps job-exclusive gear that
  is listed on a Storage Slip off the character into `char_storage`, the same server-side record a
  Porter Moogle keeps, so it never appears in a bag; grab returns it to the inventory first, then
  the wardrobes. Gear with no slip (RMEA weapons, job accessories) stays in the bags, worn pieces
  stay equipped, and `//storage` with no verb lists the slip totals. Both directions work in any
  zone and keep the client in step with `0x020`/`0x01D`. Migration `0065_storage_slips.sql` seeds
  the 33-slip item map; `0067_slip_storage.sql` moves the earlier `//locker` and visible-Storage
  rows onto the server-side slips.
- Added the hidden 9999-item `//locker` for gear and materials that slip storage does not accept.
  `//locker store|grab` takes `all`, a slot (`ammo`, `back`, `head`, `ear`, `ring`...),
  `materials` (non-wearables) or a name substring; `//locker list` and `//locker` show what is
  inside. The client cannot draw 9999 slots, so this is a server-side table and the items leave
  every bag until grabbed. Migration `0069_generic_locker.sql`.
- Added the Beastmaster consumable catalogue and all 97 Call Beast jugs (ammo, BST-only).
  Character 1 receives Pet Food Theta, a full stack of Inoshishinofuda/Shikanofuda/Chonofuda,
  and 99 of every jug in the hidden locker via migration `0070_bst_consumables.sql`.
- Added working-stock auto-refill (`//stock`) for the consumables the client must see: Utsusemi
  tools (Ichi/San/Ni), Pet Food Theta and Dawn Mulsum. Zone-in tops them up from the hidden
  locker; Utsusemi consumes its tool and refills immediately. Dawn Mulsum restores 25–50% of the
  pet's maximum HP (GEO Luopans are unaffected) and refills; without a pet HP model it reports no
  pet to heal. Migration `0071_working_stock.sql` adds Dawn Mulsum and the refill stock. Call
  Beast/Reward still need their pet logic, so jugs remain a manual `//locker grab`.
- Sorting a bag (`C2S 0x03A`) now actually stacks duplicates instead of doing nothing. The client
  still orders the slots; the server merges partial ammo, food and tool stacks up to the item's
  stack limit, clears the emptied slots with `0x020` item id `0`, and sends the all-bag `0x01D`.
- Docs: `docs/control-panel.md`, updated launcher/server/protocol/README references.

## 0.2.0 — the world slice

LandSandBoat was studied read-only to understand real zone flow; Fanxi's implementation and all
content remain original. The license boundary is recorded in `docs/landsandboat-study.md`.

### World

- Added three Port Jeuno NPCs, a Moogle shop and the persistent **Pest Control** hunt quest.
- Added six West Ronfaure monsters with roaming, aggro, melee combat, death and respawn.
- Added EXP, gil, level-ups (max HP/MP growth and heal), starter inventory and quest rewards.
- Added `//entities` and `//heal`; `//zone 100` is the field camp and `//zone 246` is town.

### Protocol

- Added NPC/monster spawn, update and despawn packets (`0x00E`) and the player update (`0x00D`).
- Added bit-packed battle actions (`0x028`), battle messages (`0x029`) and end-of-combat
  messages (`0x02D`).
- Added inventory attributes, quantities, loaded markers and lists (`0x020`, `0x01D`, `0x01E`,
  `0x01F`) and the shop flow (`0x03E`, `0x03C`, `0x083`, `0x03F`).
- Added action handling for Talk, Attack, AttackOff, ChangeTarget and SendResRdy, plus entity
  requests (`0x016`/`0x017`).
- **Fixed the zone sub-message header**: size is a 7-bit count of 32-bit units packed with the
  9-bit type; it was previously written in the wrong field. This affects every zone packet.
- NPCs/monsters now spawn on the client's first `0x015` (or `SendResRdy`), not at `0x00C`.
- Static entity ids now follow `0x01000000 | (zone << 12) | targid`, with NPCs at `0x100+` and
  monsters at `0x200+`.
- Gil is item id `65535` in container 0 slot 0, as the client expects.

### Database

- Added `world_npcs`, `npc_lines`, `monster_templates`, `monster_spawns`, `items`, `char_inventory`, `quests`
  and `char_quests`.
- Added character `hp_current`, `mp_current`, `exp`, `gil`, home point, playtime and death count.
- Migrations `0002_world_content.sql` and `0003_world_content.sql`; existing characters are
  backfilled with the starter purse/pack.

### Docs and tests

- Added `docs/world.md` and `docs/landsandboat-study.md`.
- Updated protocol, server, database, architecture, development and README documentation.
- Added packet-layout, spawn, NPC, shop, combat, reward, respawn and quest tests; the server suite
  now covers the full first-`0x015` world flow without game files.

## 0.1.0 — first Fanxi release

- Ported the native FINAL FANTASY XI client (recompiler, runtime, host, addon host) and rebranded
  it around Fanxi: new name, icons, bundle IDs, paths, window titles and documentation.
- Removed the previous launcher/installer references, third-party presence integration and its
  application ID, old repository URLs and keys.
- Added `launcher/`: a dependency-free Python/Tkinter desktop launcher with sign-in, character
  creation, server status, news, game-folder detection, `host64` building and Play.
- Added `server/`: a standard-library HTTP API (accounts, sessions, characters, launch tokens,
  news, releases, admin) and a game gateway (TLS auth, login data, lobby, zone).
- Added `database/`: SQLite migrations and seed data for accounts, characters, zones, news and
  settings.
- Added tests for the server (including a live TLS auth/lobby/zone handshake) and launcher.
- Added packaging: macOS `.app`, Linux desktop entry, `install.sh`, `setup.command`, development
  scripts and CI.
