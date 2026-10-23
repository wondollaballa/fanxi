# Changelog

## Unreleased — Limbus R30, all five families, both characters

- **Every Limbus family now ends at its top tier, at Rank 30.** Justice → Magnificent → Duty,
  Hope → Perfection → Revelation, Trust → Prestige → Sworn, Bravery → Intrepid → Indomitable,
  Mercy → Grace → Clemency: 25 pieces (items 24122–24194) in migration 99, with the base
  modifiers parsed from each piece's stat line, granted to Onedough and Twodough carrying the
  rank-30 / tier-3 augment block — the same exdata shape Odyssey uses.
- **`!r30` answers for Limbus as well as Odyssey.** `data/limbus_r30.json` holds the top tier and
  every Rank 30 row; the server lookup, `docs/limbus-r30.md` and the migration are rendered from
  it by `tools/gen_limbus_r30.py`, whose `--check` fails when they drift.
- **The libraries now carry the suits where the community actually wears them.** Every
  `gearswap/*.lua` gains a `local limbus` build table (one copy per augment choice a set needs)
  and a `sets.Limbus` container; `--lua` also puts Duty into the MNK/THF/DNC/BST/PUP TP sets,
  Revelation into BRD's 3/5 and NIN's TP/hybrid, Sworn's Phalanx-received build into PLD/RUN fast
  cast (Triple Attack into RDM's, head and feet into DRK's TP/hybrid and Resolution/Torcleaver),
  and Clemency's head and feet into SAM/DRG. Nyame Path B and the Malignance Subtle Blow slots are
  deliberately left alone — single-hit WSD and TP-feed control still belong to them.
- **Two limits are written down, not hidden.** The per-item augment bundle index is still
  unknown (LandSandBoat has no Limbus augment table), so the client draws no augment lines on
  the tooltip and `!r30` is the in-game view; the pieces carry model 0 until a model pass gives
  them their real appearance.

## Unreleased — kiting keeps the engagement

- **A target leaving melee range no longer sheathes the player.** The client sends its own
  `/attack off` (0x01A category 4) as soon as the target leaves roughly four-yalm auto-attack
  reach, even though retail keeps the engagement out to draw range. The server now ignores that
  first distance-driven packet, re-sends the `0x058` target and the `0x00D` battle stance, and
  keeps swinging whenever the target comes back. A second `/attack off` within 1.5 seconds, the
  new `!disengage` command, a dead target, or the target going beyond 30 yalms still ends the
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

## Unreleased — `/!job` cleans up after itself

- **A `/!job` change now slips the old outfit, pulls the new job's set and tidies the bags.**
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

- **`!character model` changes a character's race, face, hair colour and size, live.** The 48
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
  hidden `!locker` is not a client bag.
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
  "set your home point here".  Migration 0084 restores the menu indexes, and `!hp` now
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
  both (`xi.phase.kiting`, `xi.phase.resting`) and the UI/`/!gs` drive them.
- **Weaponsets and per-slot pins.** A weapon set is main/sub/ranged/ammo, written with a new
  weapon-only editor form, worn with **Wear**, and pinned with **Wear & lock**. Pinned slots are
  filtered out of every set the engine sends (precast, midcast, engaged, idle, kiting, resting,
  focus); the EquipViewer draws a red border on each pinned cell. The same is available in game:
  `/!gs lock main, sub, ranged, ammo`, `/!gs unlock …`, `/!gs rest on|off`, `/!gs kite on|off`,
  `/!gs focus auto|dt|pdt|mdt|eva|meva`. The control addon blocks the line before the server sees
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
  first free bag slots; `!cape` reads the item's job, so `!cape dw Andartia` works.
  [docs/capes.md](docs/capes.md) lists every build.
- Unity gear is augmented too. The five Unity items in the default libraries (Unmoving Collar +1,
  Odnowa Earring +1, Gelatinous Ring +1, Ghastly Tathlum +1, Loess Barbuta +1) carry the client's
  Rank 15 single-path `AugmentBundle` block in `char_inventory.extra`; `0083_unity_augments.sql`
  writes them, `!augment A <item>` rewrites one, and
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
  always being zero, and a new `!traits` command prints the current pair's traits, their ranks
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
  and a command console for `!zone`, `!merits`, `!heal`, `!where`, `!help`.
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
  differ. `!augment <index|A-D|off> <item>` rewrites a copy in game.
- Ambuscade JSE capes now carry their real augment block too, not just a label in the Lua file.
  The nine Beastmaster `Artio's Mantle` builds are standard five-slot augments (kind `02`,
  subkind `03`, `id:11 | value:5` words), so the client prints `HP+60`, `Eva.+20/Mag. Eva.+20`,
  `Accuracy+20 Attack+20`, `Weapon skill damage+10%`, the pet lines and the rest. The ids are
  the client's own augment table (the one Magian items use); `HP+60` is id 2 with value 27
  because the value field is five bits. `0078_bst_capes.sql` turns the bag copy into the TP
  build and adds eight wardrobe copies; `!cape <build|list|off> <item>` rewrites one.
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
  210 (verified in client memory as bytes `FF 3F` at the axe offset), and `!ws` refuses the rest.
  The 2025-07-03 client's Abilities menu does not read those bits directly: it keeps a separate
  command-id list (at `[0x106323a8]+0x160`, count at `+0x1760`) that it saves in `aix.dat`, so an
  existing profile kept drawing every saved weapon skill and a fresh profile drew nothing.
  `host/addons/hooks.c` now rebuilds that list from each `0x0AC` packet on the game thread, which
  makes both the field/engaged menu and the Mog House Abilities menu show exactly the advertised
  weapon skills and job abilities. The list is rebuilt at zone-in, after `!abilities`, and after
  a weapon change; a client started before this change needs one restart to load the new host64.
- Added `!ja <name>`, `!job <job> [sub]` and `!abilities`. C2S action `0x09` is handled: the
  response is a `0x028` Ability Finish (kind 2, the ability's animation, message 100), and
  Provoke, Benediction, Chakra, Meditate, Convert and the Curing/Healing/Divine Waltzes have
  effects. Recasts are tracked by recast id in `0x119`. The command-list rebuild above also
  fills the 2025-07-03 client's Job Abilities submenu: with the rebuilt list it lists the main
  and support job's abilities instead of "No abilities available." `!ja` remains a shortcut.

### Combat

- Engaging with `/attack` or Provoke now puts the character in the drawn-weapon battle stance:
  the server re-sends the self `0x00D` with animation byte `0x1B` set to 1, so the client plays
  the draw animation and the swing animations for the `0x028` actions that follow. Disengaging,
  a dead target or a dead player sends animation 0 to sheathe. Monsters switch to animation 1
  while they have a target too. The `0x058` engage acknowledgement is still sent first, as
  LandSandBoat does; the animation update is the part that was missing.

### Server

- New `!r30 [item]` chat command: with no argument it lists the 27 Odyssey items, with a name it
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
- Added `!storage store <job>` and `!storage grab <job|all>`. Store sweeps job-exclusive gear that
  is listed on a Storage Slip off the character into `char_storage`, the same server-side record a
  Porter Moogle keeps, so it never appears in a bag; grab returns it to the inventory first, then
  the wardrobes. Gear with no slip (RMEA weapons, job accessories) stays in the bags, worn pieces
  stay equipped, and `!storage` with no verb lists the slip totals. Both directions work in any
  zone and keep the client in step with `0x020`/`0x01D`. Migration `0065_storage_slips.sql` seeds
  the 33-slip item map; `0067_slip_storage.sql` moves the earlier `!locker` and visible-Storage
  rows onto the server-side slips.
- Added the hidden 9999-item `!locker` for gear and materials that slip storage does not accept.
  `!locker store|grab` takes `all`, a slot (`ammo`, `back`, `head`, `ear`, `ring`...),
  `materials` (non-wearables) or a name substring; `!locker list` and `!locker` show what is
  inside. The client cannot draw 9999 slots, so this is a server-side table and the items leave
  every bag until grabbed. Migration `0069_generic_locker.sql`.
- Added the Beastmaster consumable catalogue and all 97 Call Beast jugs (ammo, BST-only).
  Character 1 receives Pet Food Theta, a full stack of Inoshishinofuda/Shikanofuda/Chonofuda,
  and 99 of every jug in the hidden locker via migration `0070_bst_consumables.sql`.
- Added working-stock auto-refill (`!stock`) for the consumables the client must see: Utsusemi
  tools (Ichi/San/Ni), Pet Food Theta and Dawn Mulsum. Zone-in tops them up from the hidden
  locker; Utsusemi consumes its tool and refills immediately. Dawn Mulsum restores 25–50% of the
  pet's maximum HP (GEO Luopans are unaffected) and refills; without a pet HP model it reports no
  pet to heal. Migration `0071_working_stock.sql` adds Dawn Mulsum and the refill stock. Call
  Beast/Reward still need their pet logic, so jugs remain a manual `!locker grab`.
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
- Added `!entities` and `!heal`; `!zone 100` is the field camp and `!zone 246` is town.

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
