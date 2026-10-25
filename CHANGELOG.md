# Changelog

## Unreleased — orphaned sessions and one-click reconcile

- **`//warp all me` moves the team instead of only reporting success.** A same-zone warp used a
  self `0x00D` position update; the client treats its own position as authoritative and ignored
  it, so every box stayed put while the server said "Warped N characters". Warps now always use
  the `0x00B` hand-off, including inside one zone, and the boxes zone in at the leader.
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
