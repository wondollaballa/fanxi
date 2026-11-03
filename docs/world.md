# The world: NPCs, monsters, combat and quests

Fanxi's game gateway is no longer just a place to stand. It now has a small, original world:

- three NPCs in Port Jeuno;
- six monsters in West Ronfaure (two family camps);
- click-to-talk dialogue and a one-quest story;
- a working Moogle shop;
- basic melee combat with hit/miss/critical results, HP updates, EXP, gil and level-ups;
- a persistent inventory (gil, potions and starter swords);
- monster aggro, roaming, death and respawn.

The world is intentionally data-light. It is a vertical slice of the real client protocol, not a
recreation of a retail zone.

## Where it lives

| Piece | File |
|---|---|
| Wire packets | `server/fanxi_server/game/packets.py` |
| Live NPC/mob instances | `server/fanxi_server/game/entities.py` |
| NPC behaviour and the quest | `server/fanxi_server/game/content.py` |
| AI, combat, rewards and respawn | `server/fanxi_server/game/world.py` |
| Zone session and packet dispatch | `server/fanxi_server/game/zone.py` |
| Content tables and starter rows | `database/migrations/0002_world_content.sql`, `0003_world_content.sql` |

Content is split the same way a larger world would split it: rows say **where** an NPC stands and
**which script** it uses; Python functions say **what it does**.

## Entering the world

The client does not receive NPCs and monsters during zone-in. The sequence is:

1. `C2S 0x00A` — the zone login. Fanxi replies with the 260-byte `0x00A` login packet.
2. `C2S 0x00C` — the client has the zone. Fanxi sends the UI/state packets and inventory.
3. `C2S 0x015` — the client's first position update. **This is the trigger**: Fanxi sends one
   `0x00E` spawn for every NPC and monster in the zone, then `0x00E` updates as they move or
   take damage.

`C2S 0x01A SendResRdy` does the same if the client asks that way. The server never sends NPCs on
its own timer before the client is ready.

Entity identity follows the client's rules:

- NPC/mob long id: `0x01000000 | (zone << 12) | targid`;
- static NPC targids: `0x100`–`0x1FF`; monsters: `0x200`–`0x2FF`;
- the player's targid: `0x400`;
- pets and Trust alter egos: `0x700`–`0x8FF`;
- NPC/mob/pet/Trust packets use `0x00E`; the player uses `0x00D`.

Spawn packets are 88 bytes (`0x58`), with type/size packed into the first 16-bit header word
(9-bit type, 7-bit size in 32-bit units) and a 16-bit sequence. The payload carries the long id,
targid, send flags, rotation, x/y/z, speed, HP percentage, animation, status, triggerable flag,
model/size and a null-terminated name.

## Other players

Other characters arrive as `0x00D` packets. The local player is `0x400` in its own client; every
other player gets a targid from `0x401`–`0x6FF`, assigned once per online character and kept
across a zone change. A character is spawned when it comes within 45 yalms and despawned at 50.
Each client remembers which characters it currently draws in `seen_players`, keyed by character
id.

Movement is the only thing that normally sends another player's position, so a player who stops
sends nothing. A client that finishes loading after the last step — a box warped in while its
leader walked — would keep the copy it spawned with at the warp anchor and a follower would
stand still, thinking it was already `close`, until the leader moved again. A stationary,
zone-loaded session therefore refreshes its `0x00D` position once a second to the clients that
have it spawned. The hand-off is still a full client zone-in (about 4–5 s same-zone); the rest
of the delay after `//warp all me` is the box client drawing the zone, and the refresh makes the
followers converge as soon as that finishes rather than waiting for another leader move.

A session ends in one of three ways:

- **Logout** (`C2S 0x0E7`): the character is despawned, its targid freed, its position saved and
  `0x00B` sent.
- **Zone change**: the session is parked in `World.by_char` with the zone key it was using,
  despawned from the old zone, and picked up again by the next `0x00A` within thirty seconds of
  the change being queued. The 2026-10-05 client keeps the same key across `0x00B`; the server
  follows whichever key the client actually uses. A same-zone `//warp` is still a `0x00B`
  hand-off: the client ignores a server `0x00D` position update for its own character, so it
  zones in again at the destination instead of being left where it stood.
- **Silence**: a zone session has no TCP connection, so a force-quit, crash or dead network is
  only visible as missing packets. After three minutes the session is treated as logged out and
  despawned from everyone. This is what stops a force-quit character from staying in another
  client's world as a frozen ghost.

A fourth state is **sleeping**: `//sleep` despawns the character from every other client, clears
its combat/cast state, skips its world tick and saves its position, but keeps the process, UDP
session, targid and zone. While sleeping the server reads only chat so `//wake` can arrive, and
sends a status heartbeat every ten seconds to keep the client connection alive. `//wake` rebuilds
the client's zone state in place; there is no new login, launch token or zone change.

A login only continues a session handed to it by the lobby or a recent zone change. It never
takes over the session at the same UDP address: the OS recycles local ports, and doing so gave
the new character the old occupant's name, looks, gear and database id — two different clients
drew the same character after a multi-box relog.

## Recovering a dropped client

The retail client does not retry a lost zone connection. After about ninety seconds without
a server packet it shows `FFXI-4001 No response from the FINAL FANTASY XI server` and exits.
It keeps sending its own `0x015` position updates the whole time, so a server that has
nothing to say looks exactly like a dead one: standing still in a quiet city was enough to
lose the connection about ninety seconds after the last zone packet. Three layers keep the
team up:

- **A quiet session still answers.** A logged-in session that has sent nothing for five
  seconds gets a General-only `0x00D` (HP, MP and TP; no model or name block), the same
  packet the sleeping heartbeat uses. It resets the client's receive timer and acknowledges
  the client's packet stream. Measured before the fix: last server packet at 22:58:14, error
  dialog at 22:59:44; after it, the same idle client stays in the world for the full soak.
- **`scripts/watchdog.py` brings a client back.** It polls the main on control port 54300
  and the boxes from `~/.fanxi-linux-boxes.json` through their tunnels. A client that was
  in the world and now shows the error dialog is dismissed, relaunched with a fresh launch
  token, signed in, and then the party is re-invited and follow re-applied. A missing main
  is restarted too. Per-client cooldowns (three minutes) stop a network that is still down
  from turning into a relaunch loop.
  ```
  python3 scripts/watchdog.py --once --dry-run   # report only
  python3 scripts/watchdog.py --once             # recover now, then exit
  python3 scripts/watchdog.py                    # supervise
  ```
  `--relaunch-exit` also restarts a box whose control port died after it was in the world;
  without it a deliberate Stop is left alone. The watchdog logs to `data/watchdog.log`.
- **The server waits three minutes before reaping a silent session** (`SESSION_IDLE_TIMEOUT`),
  so a short stall does not remove the character and its party slot while the client is
  still able to resume.

**A reconnect keeps your buffs and cooldowns.** Retail holds a character's status effects and
job-ability recasts on the server, so a dropped link and a relaunch come back with the same song
list ticking and the same abilities still recharging; only a deliberate `/logout` takes the
buffs with it (the cooldowns survive that too). Fanxi builds a fresh session for every fresh
login, so the session writes a small snapshot to `char_live_state` (migration 0145) while it is
in the world, coalesced to one write of a few hundred bytes per change, and again on the way out
(reaping, a login replacing a ghost, or a hand-off that was never acknowledged). The next login
reads it back and drops whatever expired while the client was gone, because every time in the
snapshot is an absolute timestamp.

What comes back is what the client can draw: `0x037` and `0x063` carry the same icons, in the
same slot order, with the remaining time; `0x119` carries the ability cooldowns. `0x119` is in
the zone-in burst itself as well as in the reply to the client's `0x061` stats request, and the
HUD reads the whole table on every poll, so a restored cooldown is dark before the client has
asked for its stats. The first
things to expire are listed in a chat line a couple of seconds after the zone-in, never inside
the burst itself:

```
Welcome back. The server held 5 song(s), 2 buff(s) and 3 ability recast(s) while you were away.
Valor Minuet V has 2:31 left.
```

A Mog House login and a log-in after a K.O. are rests in retail: the buffs are gone but the
ability cooldowns still come back. A Trust aura is not restored either — the alter ego that put
it up is released with the old session, so the aura would have no source. Food survives with its
modifiers, and its Food icon is reconciled with the timers on the way in so the bar cannot show
food the stat sheet has already dropped. The snapshot is one row per character and does not
grow; see [database](database.md) for the table.

## Trust alter egos

Trust magic is its own spell group (spell ids 896 and up).  A client casts one exactly
like any other spell (`C2S 0x01A` action `0x03`), but `cast_trust()` does not spend MP
and `finish_trust_cast()` spawns an NPC instead of resolving an effect.  The old path
fell through to `resolve_self_spell()`, which printed "Shantotto takes hold." and left
the zone empty.

Each call creates a `ZoneEntity(kind="trust")`:

- targid from `0x700`–`0x8FF`, long id `0x01000000 | (zone << 12) | targid`;
- a normal `0x00E` spawn whose Flags3 carries TrustFlag (`0x01`), PetNewFlag (`0x04`)
  and PetFlag (`0x40`), with allegiance 1 and the Trust's look block from
  `trusts.look_hex`;
- a `0x067` to the owner with the Trust id, targid and the owner's `0x400` targid, which
  is what makes the client offer the Release sub-menu.

Trusts are part of the party page, not only the world.  `party_packets()` injects a
`0x0C8` entry and one `0x0DD` row per alter ego after its owner's row, exactly as
LandSandBoat appends the leader's Trusts.  A solo player with Trusts gets the same
one-player synthetic party page and a non-zero `0x0E1` group id (the character id);
a plain solo player still gets no `0x0E1`, because the retail client cannot read id 0.
`sync_parties()` sends a `0x0DF` whenever a Trust's HP/MP/TP changes, so the party bars
follow the entity.

`database/migrations/0115_trusts.sql` carries the factual appearance and combat data
for all 122 Trust spells (model, main/sub job, attack delay, damage multiplier and the
passive-Geomancy flag).  `0117_trust_spells.sql` carries each Trust's own
`mob_spell_lists` rows, so Kupipi's kit is the White Mage list rather than a generic
caster table.  The level tracks the owner's main job.

`0151_trust_species.sql` adds the LandSandBoat species id to each row, and
`game/trust_stats.py` turns that into HP/MP with the same race/job/subjob base tables the
player sheet uses.  A Trust's subjob is half its main level, as in LandSandBoat, and its
MP sits 75% above the player curve: retail alter egos run about 31% above a player's
base racial MP and commonly carry further MP+ traits ([BGWiki trust measurements](https://www.bg-wiki.com/ffxi/User:Shynoe/trust)), which is why a level-99 healer or
nuker shows a pool larger than an ungeared player's instead of the old flat
`level * 4` placeholder.  HP follows the same race/job/subjob curve without the MP bonus.

The client collides the player with its own pets and alter egos, and one that has stopped on
the character blocks every step: the blocker is inside the collision radius, so walking out of
it is impossible and the player appears stuck.  The client exposes no "walk through party"
flag, so the follower yields instead: a Trust or pet inside `TRUST_PERSONAL_SPACE` (1.2 yalms)
of any player steps away from them at `TRUST_SIDE_STEP_SPEED` and streams the new position, and
the player's next step is free.  That is the practical half of BlinkMeNot's "get the team out of
my way" — it does not change collision itself, it keeps the team out of the bubble.

A Trust follows its owner and fights the monster the owner is fighting.  Its opening
action at melee reach is a weapon swing (the client's stance tell); after that the AI
casts from its kit: a Cure when the owner is below 85% HP, then the damage-first
enfeebles (Koru-Moru's Dia, Sylvie's entrusted Indi-Frailty), a missing or expiring
buff, the rest of the monster debuffs, then a nuke.  Dia is deliberately before the buff
rotation: a Red Mage with Protect/Shell/Haste/Refresh/Phalanx to maintain otherwise
spends every cast refreshing one of them and never lands the 20% Defense cut.  Buffs
land on the owner with the normal `0x037`/`0x063` status icons and a `0x028` gain-effect
result; a cast shows the client's magic-start bar.  Koru-Moru's Red Mage list carries
Flurry and Flurry II, but those only speed up ranged attacks, so his tactics drop that
family and Haste II is the attack-speed buff he keeps up.  The Geomancy family is not in
the spell table the AI classifies by, so `trust_ai.effect_of()` resolves an Indi-/Geo-
spell through `geomancy.INDI_EFFECTS`.
Geomancy is not a buff the rotation puts up, though: a Geomancer keeps one aura per bubble
and the next cast in a bubble replaces it -- Sylvie's list is all Indi-, so she holds a
single aura -- and `trust_ai.choose_aura()` picks the one the moment needs, from
the situation the zone tick measures into `trust_ai.AuraNeed`.  The order is
Indi-refresh when the owner or a teammate is below half a mana bar, Indi-acumen for a
caster owner, Indi-precision when the owner's hit rate is under 80% (and as the default
before a pull, when there is no monster to measure), Indi-fury when the
Attack/Defense ratio is under 1.3, and otherwise Indi-frailty, whose Defense cut helps
every physical attacker and is the play when a weapon skill is ready.  A swap waits eight
seconds, and the old aura is taken down when the new one lands.  Sylvie (UC) is the only
Trust whose `mob_spell_list` carries Geomancy.  On top of her own aura she **Entrusts
Indi-Frailty** whenever the fight's 12.5% Defense cut is missing or expiring.  The
Entrust bubble itself is on the party, not the monster, so the server lands the cut as
an ordinary **Defense Down** on the monster -- putting the Indi-Frailty aura on the mob
would make the mob the aura's caster and debuff the players inside it.
`trust_ai.entrust_debuff_for()` is the second half of her kit.

Every Trust carries the weapons its design gives it (`trust_gear`, migration 159).
**Sylvie (UC) has Idris**, but her Trust kit uses the published level-99 alter-ego
values rather than the player's Geomancy+10 column: Indi-Fury **Attack +37.5%**,
Indi-Precision **Accuracy +56**, Indi-Haste **+28.8%**, and the entrusted
**-12.5% Defense** cut.  `trust_ai.TRUST_AURA_EFFECTS` holds that row.  **Joachim has the
Prime Loughnashade** (the final iLvl 119 III horn, item 22307), so his songs are Song+4
and four of them fit.  He sings
the plan rather than his spell list: **Victory March** while the owner's magic haste is
short -- and **Honor March** once that Haste would be redundant, since the two share the
March status and Honor trades it for Attack, Accuracy and the ranged lines -- **Valor
Minuet V** to cap Attack, and **Aria of Passion** -- whose Damage Limit is
the only thing left once Attack caps -- when the Attack/Defense ratio is already at the
weapon's pDIF cap.  A mage owner gets **Mage's Ballad III** instead, and a Ranger gets
the ranged set: March for speed, **Archer's Prelude** for Ranged Accuracy and Minuet for
Ranged Attack.  A Corsair gets the melee plan by default — Prelude's Ranged Accuracy is a
wasted slot for the front line — and asks for it by name if it is shooting.  The spare
fourth slot goes to **Blade Madrigal** while the owner's swings land under 95%
(`combat.hit_rate()`, the same reading the Geomancer uses for Indi-precision); an owner
who already lands 95% gets no fourth song rather than filler, and Paeons and Elegies are
never sung.  Migration 160 adds Minuet V, Archer's Prelude and Aria of Passion, and
migration 167 adds Honor March plus the lower Minuet tiers (IV at 63, III at 43), so a
Master below V's level 75 still gets an Attack song.

The owner can replace the plan with an exact set.
`//trust joachim set songs "Aria of Passion" "Valor Minuet V" "Valor Minuet IV" "Honor
March"` stores up to four spell ids on the character (`char_settings`); Joachim sings them
in the order given and stops choosing by role.  Both Minuets fit because each song keeps
its own effect state rather than sharing the Minuet icon.  `//trust joachim songs` shows
the set and `//trust joachim set default` returns to the plan.  The Trust window's **Set
songs** dialog offers the same 21 songs as checkboxes, with the level each unlocks at,
and saves the order they were clicked in (see [control panel](control-panel.md#combat-hud)).

The same per-character mechanism covers the other support Trusts.  A **Set spells** dialog
for Koru-Moru (952), Ygnas (998) and Sylvie (UC) (981) lists their cures, buffs, debuffs
and Sylvie's Indi- auras, with the level of each; only the ticked spells are used, and the
default AI still decides *when* each one is worth casting (cure when hurt, buff when
missing, and so on).  A **Set rolls** dialog for Luzaf (928) and Qultada (967) lists the
31 Corsair rolls; the list is a priority order, so the first selected roll that is not
already on the party wins; a second selected roll fills the Trust's other slot.  Sylvie's
list also carries **Geo-malaise**, the enemy-targeted
Magic Defense Down hex, so she can keep the Idris 30% Malaise on a monster instead of an
Indi- aura; it is migration 0172.  An empty set means the built-in logic.  Chat uses
`//trust <id|name> set spells|rolls "..." ...`, `//trust <id|name> songs`, and
`//trust <id|name> set default`; the HUD's **Use default logic** checkbox is the same
switch.  The selection is stored in `char_settings.trust_actions` (JSON keyed by Trust
spell id), except Joachim's legacy `joachim_songs` key.

A Trust also grows
with its owner: it inherits half of the owner's gear modifiers at item level 119, scaled
by the owner's average item level, so a well-geared Master lifts its Attack, Accuracy,
HP/MP and attributes with the set.  All damage is credited to the owner, and
half of a melee hit becomes the owner's enmity.

A claimed monster stays with the party that claimed it.  The client draws a monster
another party has claimed pink and will not attack it, so a hit from outside the claiming
party is ignored for the claim and for the monster's hate target.  If an engagement's
target moves to another party's claim, the engagement ends: the client could not swing at
it, and leaving the loop running landed hits the player never saw themselves make.

**Qultada and Luzaf roll for the party and never swing.**  `trust_ai.choose_roll()` reads
what the party is short of rather than the owner's job — Evoker's Roll when a caster is
under half MP, Wizard's for a caster-heavy group, Hunter's for a ranged-heavy one, and for
melee **Chaos Roll** while Attack is short of the pDIF cap, **Fighter's Roll** (Double
Attack) as the general second line, and **Samurai Roll** (Store TP) once it is capped.
The amounts are BG-wiki's per-total tables, not a per-point line: the lucky and unlucky
numbers jump, so a Chaos IV is +25% Attack while a Chaos VIII is +3%.
**A Trust Corsair fills both of a Corsair's roll slots**, as retail Qultada does with his
standard Chaos + Fighter's pair.  A roll lands on every party member in the zone for
**340 seconds** -- the COR job-point maximum for Phantom Roll Duration (300s base + 2s per
rank over 20 ranks), because an alter ego is a maxed-out Corsair.  The first slot takes the
party's biggest need and the second takes the next useful line, so a second Corsair adds
another roll instead of duplicating one; Qultada and Luzaf together can hold Chaos,
Fighter's and Samurai.  A held roll is refreshed when its party copy is about to fall off,
and is kept for the whole fight — re-deciding every refresh made Chaos and Samurai trade
the slot as the ratio crossed the cap.  An explicit roll set from the HUD or
`//trust <id> set rolls` fills the two slots in the order given: the first selected roll
whose status is not already on the party wins, then the next, and so on.  Changing the
list removes a held roll that is no longer in it.  An empty set restores the role plan.

The seven passive Trusts do not swing.  They radiate the retail COLURE aura, and the
aura is a separate effect from the player's own buff: Cornelia applies
`TRUST_AURA_HASTE` (808) with the GEO Haste icon (580), so her Haste sits beside a White
Mage's Haste (33) instead of replacing it.  Sakura, Moogle, Star Sibyl, Kuyin Hathdenna,
Brygid and Kupofried carry their Regen, Refresh, Magic Attack, Accuracy, CHR and
Dedication auras; the effect is removed when the Trust leaves.

A duplicate spell is refused, five active Trusts is the cap, and a zone change, logout,
K.O., or the client's Release menu despawns them.  Every other player in the zone sees
the same `0x00E` spawn.  The HUD reads the client's TrustFlag and the `0x067` master
targid, highlights a called Trust's button, and turns a second click into
`//trust release <spell id>`; a configurable support Trust (Joachim, Luzaf, Qultada,
Koru-Moru, Sylvie (UC), Ygnas) opens **Call** / **Dismiss** and **Set songs/spells/rolls**
instead.  `//trust` lists what is out and `//trust release all` clears the group.

Limits: Trusts do not use job abilities or ranged attacks, and monsters cannot select one
as their hate target.  Their spells heal and buff the owner only, not other party
members.  They are also not persisted; a server restart clears them.

## NPCs and the quest

| NPC | Zone | Script | What it does |
|---|---|---|---|
| Cumetouflaix | Port Jeuno (246) | `Cumetouflaix` | starts, tracks and completes **Pest Control** |
| Gekko | Port Jeuno | `Gekko` | opens a shop |
| the imported NPCs | every zone | the NPC's own name | retail dialogue events, shops and Home Points |

Talking is `C2S 0x01A` with action id `0x00` and the NPC's targid. Fanxi checks the target is an
NPC and that the player is within 6 yalms, then calls the script.

**Pest Control** is stored in `quests` and `char_quests`:

1. Talk to Cumetouflaix, the NPC nearest the Port Jeuno arrival point. The quest becomes `active`.
2. Go to West Ronfaure with `//zone 100`; `//pos -376 -50 311` puts you at an Orcish Fodder camp.
3. Defeat three Orcish Fodder. Each kill increments `char_quests.progress`.
4. Return to Cumetouflaix. The server marks the quest `complete`, adds 300 gil and two Potions,
   and refuses to pay a second time.

Dialogue is sent as `0x017` chat lines rather than a client event. FINAL FANTASY XI event bodies
and menus live in the client's DAT files; a server can choose an event id but cannot author its
text. Using chat keeps Fanxi's dialogue original and avoids shipping or relying on retail DAT
content. The quest state machine is real and persists; only the presentation is modest.

## The Moogle shop

Talk to the Wandering Moogle to open a real shop window:

| Item | Price |
|---|---:|
| Potion | 50 gil |
| Onion Sword | 500 gil |
| Bronze Sword | 800 gil |

Packet flow:

```
C2S 0x01A Talk
S2C 0x03E shop open (item count)
S2C 0x03C shop list (price, item id, index; final flag 0x89)
C2S 0x083 buy (quantity, shop no, item index)
S2C 0x03F purchase result
S2C 0x020 item attributes + 0x01D container loaded
S2C 0x017 confirmation
```

The server charges gil, stacks the item into the first free inventory slot, updates the gil item
(row 0 of container 0, item id `65535`), and returns the client's inventory to a consistent state.

## The Mog House

The city Mog House doors (`zmr?`/`zms?` zone lines) toggle the character's `moghouse` flag and
move it into the client's Mog House interior, where the resident Moogle stands. Entering is a
rest, as in retail:

- current HP and MP become their maxima and are written to `characters`;
- every status effect is dropped: the `0x037` status packet carries `0xFF` in all 32 buff slots,
  which is what removes the client's icons;
- the login packet's `0x7C` field flips the client into its Mog House state.

Logging back in inside the Mog House rests the character as well. Walking out does not heal.

The login packet's `MyroomMapNumber` chooses the city interior and its exit menu, and
`MyRoomExitBit` names the same city: San d'Oria `0x0121`/`1`, Bastok `0x0122`/`2`, Windurst
`0x0123`/`3` and Jeuno `0x0100`/`4`. A character visiting another nation's Mog House gets the
foreign interior (`0x0101`, `0x0102`, `0x0120`), but the exit menu still follows the city the
Mog House is in. Choosing an area sends `0x05E` with the universal `zmrq` rect; its
`MyRoomExitMode` picks that city's Southern/Northern/Port areas (and Windurst Woods or the four
Jeuno areas where they exist), and the character zones in at the chosen area's outdoor Mog House
door.

## Monsters and combat

West Ronfaure carries the imported spawn table — 480 spawns across 37 templates, from level-1
Wild Rabbits to the 94–95 Notorious Monster Lancing Lamorak. The quest targets the Orcish Fodder
that camp around the zone:

| Monster | Model | Level | HP | Behaviour |
|---|---:|---:|---:|---|
| Orcish Fodder | imported | 3–7 | imported | aggro, roam |
| Orcish Grappler | imported | 3–8 | imported | aggro, roam |
| Wild Rabbit | imported | 1 | imported | roam |

The gateway tick runs on the UDP receive timeout (about every 250 ms) and the zone loop also
flushes queued replies every 200 ms, so a box that is not sending anything still receives its
mob movement while another box keeps the socket busy. Monsters walk the zone instead of floating
through it: the server reads the zone's collision mesh from the player's own game folder, turns
its upward faces into a floor grid and its walls into barriers, and plans every roam leg and
chase on that grid. The details are under [Zone navigation](#zone-navigation).

Entity movement is **ambient** traffic: only the newest `0x00E`/`0x00D` position per entity is
kept in the session queue, action/status/chat/equipment messages are packed ahead of it, and the
stream is capped by a 900 B/s token bucket (`AMBIENT_BYTES_PER_SECOND` in `game/zone.py`). The
client's receive pipe was built for roughly 3 kB/s; without the cap a crowded zone could fill it
and delay the answer to a job ability or a macro click by minutes.

The client walks an NPC forward between `0x00E` packets using the `moving` flag and the speed
byte, so a position packet is a correction rather than the animation. A walking roamer carries
speed byte 12 and is corrected four times a second (`MOB_SYNC_INTERVAL`); a chasing runner
carries 36 and is corrected every 100 ms (`MOB_SYNC_INTERVAL_RUN`). A real corner or a stop is
sent immediately within 30 yalms (`MOB_URGENT_RANGE`), and steady movement beyond 45 yalms
(`MOB_SYNC_RANGE`) is not streamed at all — spawning still reaches 60. That is what keeps a
dense roam zone smooth without printing every mob's position every tick.

- idle monsters roam within 5 yalms of their spawn point every few seconds, stay on a walkable
  surface, route around walls and send `0x00E` position updates;
- a monster within 8 yalms of a living player engages, announces itself, and attacks every few
  seconds. It needs a walkable line to the player: a cliff, a wall or a bridge deck between them
  hides the player from aggro exactly the way it should;
- a chasing monster follows a path around the obstacle and keeps its feet on the floor height
  under it. The chase is leashed to a 60-yalm sphere around the spawn, not to the spawn
  *floor*: a pull up a slope or down a ramp is followed. If no route exists -- a floor seam, a
  search budget, or a player on top of a wall, across a chasm or on a surface the mesh does
  not connect -- the monster still walks the direct line toward the player, using the same
  floor and barrier samples, and stops at the cliff or wall edge instead of standing at the
  pull spot. Melee swings also require that walkable line, so nothing hits through a wall;
- a player attacks with `C2S 0x01A` action `0x02` while the target is within draw range
  (`ENGAGE_RANGE`, 30 yalms); `0x04` disengages. The client sends its own `0x04` as soon as the
  target leaves auto-attack reach (about four yalms); the server ignores that first
  distance-driven packet and re-asserts the stance, so the engagement survives out to 30 yalms.
  A second `0x04` within 1.5 seconds, `//disengage`, or the target going beyond 30 yalms ends it;
- engaging sends the `0x058` target acknowledgement and then re-sends the self `0x00D` with
  animation `0x1B = 1` (battle stance, weapon drawn); disengaging, target death or player death
  sets it back to 0 (sheathe). Without that byte the client stays in its idle pose and never
  plays the draw or swing animations. The same animation byte is set on a monster while it has
  a target. The client lowers the pose within about a second of any animation (a swing, a
  flinch, a cast), so while the player is engaged the server re-sends just the General animation
  every half second; that is what keeps the weapon out. Engaging, a cast result and an equipment
  batch also send the `0x058` assist target with the first draw. `0x037`'s `server_status` (body
  `0x2C`) carries the same animation, and the client reads it as the local player's pose: a
  follow-up to an equipment batch (`equipment_sync`) that includes a `0x037` must say `1` while
  engaged. Hard-coding `0` there sheathed the weapon on every gear swap and the stance refresh
  drew it again — the disengage/re-engage flap that looked like GearSwap fighting the engage
  packet. The follow-up is now a delta ([the equipment follow-up](#the-equipment-follow-up)), so
  the `0x037` leaves only when the status payload really changed; a swap that leaves HP, buffs
  and animation alone does not poke the pose at all (the stance re-assert still goes out);
- hit chance, damage and critical chance are server-side and follow retail's physical damage
  model (Attack/Defense ratio, fSTR, per-weapon pDIF caps, level correction);
  [combat-damage.md](combat-damage.md) is the reference;
- each attack round sends one bit-packed `0x028` battle action: actor, target, basic-attack
  category, `atk0`, then a result per swing -- each hand's base hit plus its Double/Triple/
  Quadruple Attack extras, main hand first -- with each result's hit/miss, critical/defeated
  flags, animation, damage and hit/critical/miss message;
- HP changes broadcast `0x00E` with the HP mask and refresh `0x037`/`0x061`/`0x0DF`.
- The gauges carry percentages (`0x037` HPP, `0x0DF` HPP/MPP, `0x00A` HPP), and every one divides
  by the character's current maximum HP/MP. A character at 7240/10149 shows a 71% bar, not a full
  one; only the Mog House rest fills it.

When a monster reaches 0 HP:

- it is marked dead and stops attacking;
- the killer receives EXP and gil (stored on `characters` and in the gil inventory row);
- at level 99 the kill instead pays Exemplar Points. A qualifying kill arms a Master
  chain window of **60 s**, which shortens by 1.2 s per link and reaches its **30 s**
  floor at chain #25; the next kill inside the window is chain #1 (message `810`) and
  pays +2% per link, capped at chain #50. A kill outside the window is a fresh chain #0
  (message `809`). The counter is `game/chain.py`, one `ChainState` per zone session;
- `0x029` reports the defeat and gil, `0x02D` reports EXP, and `0x029` reports a level-up;
- EXP-to-next is `max(100, 100 × level^1.5)`; each level adds 20 max HP and 10 max MP and heals;
- the quest hook advances if the monster belongs to the quest's template;
- after the spawn's respawn time the monster returns at full HP with a fresh `0x00E` spawn.

Player death is temporary: Fanxi records the death, disengages, and restores the player at half HP
and MP after six seconds. There is no home-point teleport or EXP loss yet.

### Zone navigation

A zone model (the client's `MZB` block) contains the same collision triangles the player walks
on. `server/fanxi_server/game/zonemesh.py` reads that block through the client's own
`VTABLE`/`FTABLE` pair; `server/fanxi_server/game/nav.py` rasterises floors into a 1.5-yalm grid
and keeps non-floor triangles as barriers. Each cell holds up to four floor heights, so a bridge
deck, the ground under it and their ramps are separate layers.

The grid is built from the **player's** FINAL FANTASY XI folder, the same `FANXI_GAME_DIR` the
gateway uses for `compress.dat`; no zone geometry is shipped with Fanxi or committed to the
repository. The first zone-in starts a background build (a few seconds for most outdoor zones, up to
about fifteen for the largest caverns), and the result is cached under

```
data/nav/<zone>.nav
```

with the source file's size and mtime in the header. A changed zone model rebuilds its cache. To
prebuild every zone that has monster spawns, or just the ones being played:

```bash
cd server
FANXI_GAME_DIR=/path/to/FINAL\ FANTASY\ XI \
  python3 -m fanxi_server nav --zone 100 --zone 101
python3 -m fanxi_server nav --all          # or: make nav, from the repository root
```

Set `FANXI_NAV=0` to switch the whole layer off, or `FANXI_NAV_DIR` to move the cache.

The step rule allows 0.35 yalms of kerb plus 0.9 yalms of rise per yalm walked (a 42-degree
grade), which is at most 1.7 yalms over one 1.5-yalm cell; crossing a barrier triangle also has
to clear the monster's 1.5-yalm body. This is what stops a monster walking up a cliff face,
through a wall standing on flat ground, or off the edge of the mesh. A* is limited to a small node budget on the chase path, so an unreachable player
costs a short failed search, not a zone-wide one. `NAV_VERSION` (in `nav.py`) is the cache format
version; bump it when the rasteriser changes.

A server without the game folder can still use grids already in `data/nav`, but it cannot build
new ones. A zone with no readable model keeps the older straight-line movement with one safety
rule: a monster will not chase a target more than four yalms above or below it. City interiors
and some zones keep their geometry in separate sub-region files, which this reader does not
follow yet; those zones take the fallback.

## Inventory

Inventory is one row per slot in `char_inventory`:

- container 0 is the normal inventory;
- container 2 is the client's Storage bag. The `//storage` command no longer uses it; migration
  `0067` moved its contents onto the server-side slips;
- container 4 is the Mog Locker. No command uses it, and migration `0067` emptied it too;
- containers 8 and 10–16 are Mog Wardrobes 1–8;
- containers 1, 5, 6, 7 and 9 are the Mog Safe, Satchel, Sack, Case and Safe 2;
- slot 0 is gil, stored as item id `65535`;
- slots 1–80 hold items;
- potions stack to 12; swords stack to 1.

The server sends `0x01C` capacities, one `0x020` per item (with the 24-byte attribute block),
per-container `0x01D` "loading" markers, an all-container `0x01D`, and `0x01E` when only a
quantity or gil total changed. `0x01F` is available for lighter updates.

`0x01D`'s `Flags` field is the client's whole container-ready mask, and the client replaces its
mask with whatever the packet carries. Item moves, shop refreshes and storage/locker changes send
all 18 container bits, not just the bags they touched; a partial mask would make every other bag
draw empty (a wardrobe would stay blank until an item was moved into it).

Sorting a bag sends `C2S 0x03A` with the container. The client arranges the slots; the server
merges any partial stacks of the same item in that bag (ammo, food, ninjutsu tools and so on),
filling the lowest-numbered slot first up to the item's stack limit. Emptied slots are cleared
with an `0x020` carrying item id `0`, and the update ends with the usual all-bag `0x01D`.
Different items, different bags, full stacks and rows with different augment extdata are left
alone.

Starter characters receive 1,000 gil, two Potions and an Onion Sword. Existing characters are
backfilled by migration `0003_world_content.sql`.

### The 30-day Recycle Bin

Dropping an item (`C2S 0x028`) no longer deletes it.  The stack moves to the client's Recycle
Bin, container 17, and `char_inventory.dropped_at` records the drop (migration `0146`).  The bin
holds 80 slots, merges matching stacks, and refuses a drop when it is full.  A recycled item
cannot be equipped or used and cannot be moved into another bag until it is restored.

Expired rows (30 days) are purged on zone-in.  In chat:

```
//recycle                        list the bin
//recycle restore <slot> [n]     put an item back in the inventory
//recycle drop <bag> <slot> [n]  move one bag slot to the bin
//recycle purge                  delete anything already past 30 days
```

The in-game **Magic Bag** HUD (`//bags` or `//magicbag`) lists every client bag, the Recycle
Bin, the Storage Slips, the 9,999 locker, and the Armory purchase history as Claim Storage, with search, sorting, move and recycle actions (equipping stays with GearSwap).  `//item move <bag> <slot>
<to-bag> [n]` is the HUD's move path (the server still applies the normal slot/job rules).

### Weapons and the sub slot

Equipping a two-handed main weapon (`skill` 4, 6, 7, 8, 10 or 12) clears any shield or off-hand
weapon in the sub slot; after that only a grip fits there. A grip is refused while the main
weapon is one-handed or empty. Hand-to-hand is neither one- nor two-handed for this rule, so a
shield can still share it.

A job change checks gear in **every** bag, not only the normal inventory, so a piece worn out of
a Mog Wardrobe is unequipped when the new job cannot use it. A weapon with no grap model clears
its slot's look instead of leaving the previous weapon on the character; without that, equipping
a model-less grip after a dagger left the dagger drawn on the hip.

The model id also decides the client's attached effect, not just the mesh. Prime weapons have two
looks: the `Non AG` model for stages 2-4 and the `Stage 5` model for the 119 III form, which is
the same weapon DAT followed by the client's `aura` particle block — the afterglow that the
Relic/Mythic/Empyrean/Aeonic `119 AG` models carry. `items.model` therefore has to name the
stage's model, not only the family; `0125_prime_afterglow_models.sql` maps all sixteen Prime
families.

### The equipment follow-up

A gear set arrives as one `0x050` per slot, usually split over several datagrams. The server
echoes each slot as it is read and settles the outfit (save + `refresh_vitals`) at the end of
every datagram, because a weaponskill can share the datagram with its precast gear and has to
roll against that outfit. The packets derived from the outfit wait `EQUIP_SYNC_DELAY` (150 ms)
after the last slot — capped at `EQUIP_SYNC_MAX_DELAY` (600 ms) while the phase engine keeps
swapping — so one burst owes one follow-up instead of one per datagram.

That follow-up (`equipment_sync`) is a delta. The server remembers the payload of each derived
packet as it leaves (from `pack()`, so the zone-in bundle, the `0x061` reply and `//abilities`
seed the same baseline) and sends a packet only when its payload changed:

| Packet | Changes when |
|---|---|
| `0x051` grap list | a worn model changed |
| `0x0AA` magic data | the job pair (or a spell grant) changed |
| `0x0AB` job abilities, `0x1A5` command update | the job pair changed |
| `0x0AC` command data | the weapon skill type, a skill bonus or a granted skill changed |
| `0x061` stat sheet, `0x037` status | the outfit's stats, HP/MP or buffs changed |

Before this, every batch re-sent all seven (about 700 bytes, one packet per ack). The `0x0AC`
copy is the expensive one: host64 rewrites its whole ability list from each one, and every
client freeze in the 2026-10-27/28 logs ends on that rebuild, so an armour-only swap must not
send it. The `0x037` carries the Vana'diel clock and the unix stamp, so its signature ignores
those bytes; everything else in it is state.

## Storage, from anywhere

Fanxi has two server-side stores and needs no mule:

- **Storage Slips** (`char_storage`), keyed by the slip in `item_storage`, for the pieces a
  [Porter Moogle](https://www.bg-wiki.com/ffxi/Porter_Moogle) accepts;
- **the 9,999-slot locker** (`char_locker`), for the pieces no slip accepts -- Ambuscade job
  capes, relic/mythic/empyrean weapons, job accessories -- and for any copy carrying an augment
  block.

Neither is a client bag. Storing deletes the `char_inventory` row, so the item disappears from
every bag until it is grabbed. The client's own Storage container is 80 slots and is deliberately
not used: the two server-side stores are presented to the player as one storage, and the 9,999
limit is the locker's real capacity. That limit counts storage slots, not units: a 99-item jug
stack is one slot, exactly as it would be in a client storage bag. The Porter Moogles are placed
in the world, but their trade menu is not implemented yet; `//storage` is the current interface.

The rule is the current job:

- an item the job **can** equip stays out (inventory or a Mog Wardrobe);
- an item it **cannot** equip goes to its Storage Slip when the item has one, otherwise to the
  9,999 locker.

`//storage organize` runs that rule over every permanent bag, pulls the job's stored set back into
the Mog Wardrobes (in equip-slot order, then the inventory), and tidies the job's loose
inventory/Safe gear into the wardrobes. `//storage store all` is the store half alone. `//job` runs
the same organizer for the new job, so a job change leaves only the new job's gear out:

```
//storage organize          store every other job's gear, pull this job's set into the wardrobes
//storage store all         the store half only: everything this job cannot equip
//storage store nin         store NIN's own gear (slip where possible, locker otherwise)
//storage grab nin          pull NIN's own gear back into the wardrobes
//storage grab all          empty both stores into the bags
//storage list [job|all]    what is stored, by job (default: this job)
//storage                   both totals, and how much of this job is waiting
```

A job name, abbreviation or number is accepted (`nin`, `NIN`, `Ninja`, `13`). "Job-exclusive"
means the item's job mask is exactly that job's bit for `store <job>`: all-jobs gear and pieces
shared with another job stay where they are (the starter Onion Sword is NIN-usable, but it is not
NIN gear). `store all` and `organize` use the broader rule above: the current job's mask decides.
"Storable" means the item id is listed on one of the 33 Storage Slips in `item_storage`, seeded by
migration `0065_storage_slips.sql`.

`//storage` sweeps equipment only: a non-empty equip slot and a stack size of one. Consumables,
ammo stacks and crafting materials are not job gear, stay where they are, and are the manual
`//locker` tool's job. Worn pieces stay equipped; temporary items and the recycle bin are never
swept. For the NIN reforged sets, Hachiya +4 is Storage Slip 32, Mochizuki +4 is Slip 33 and
Hattori +3 is Slip 30; Kikoku/Nagi/Kannagi/Dokoku, Yagyu Darkblade, Ninja Nodowa and Hattori
Earring are not on any slip, so they go to the locker rather than staying in the bags.

Pulling fills the eight Mog Wardrobes first -- main, sub, ranged/range, ammo, head, body, hands,
legs, feet, neck, waist, ear, ring, back -- then the normal inventory. The tidy then moves the
job's loose inventory and Safe/Satchel/Sack/Case pieces into the wardrobes, so the active set is
in one place instead of scattered. If the bags fill, the rest stays in storage and the chat line
reports it. Neither direction cares where the character is standing, and `0x020`/`0x01D` keep the
client in step.

Every move is one transaction: the destination row is written before the source row is deleted.
A slip item with a non-empty augment block goes to the locker instead, because `char_storage` has
no `extra` column; the 24-byte block survives there. That is also why several builds of one cape
can coexist without losing their augments.

Migration `0067_slip_storage.sql` moves anything left in the old visible Storage/Locker containers
into `char_storage`, so the transition leaves no gear stranded in a bag the client shows.

## The 9,999-slot locker, from anywhere

The client's visible bag capacity is one byte, so a 9,999-slot bag cannot be drawn. Fanxi's
`//locker` is a hidden server-side locker with room for 9,999 storage slots: storing deletes the item from
every permanent bag and keeps it in `char_locker`, so it disappears from the client until grabbed:

```
//locker store ammo       store every ammo-slot item
//locker store back       store capes and mantles
//locker store jsecapes   store only the 22 Ambuscade job capes
//locker store materials  store non-wearables: potions, crafting materials, etc.
//locker store Artio      store items whose name contains "Artio"
//locker store all        store every unequipped item
//locker grab ammo        return ammo (same selectors as store)
//locker grab all         return everything
//locker grab broth 12    return at most 12 of the matching item (one stack)
//locker grab jsecapes    return every Ambuscade job-cape build
//locker list             list the locker's contents in chat
//locker                  show used/capacity and the selector list
```

Selectors are `all`, a slot (`main`, `sub`, `ranged`, `ammo`, `head`, `body`, `hands`, `legs`,
`feet`, `neck`, `waist`, `ear`, `ring`, `back`), `materials`, `jsecapes` for the 22 Ambuscade
job capes, or any other word as a name substring. `cape`, `capes` and `mantle` are aliases for
`back`; `ear` covers both ear slots and `ring` both ring slots. Grab accepts an optional
trailing count, which is how a 99-item entry can be taken one stack at a time. Worn pieces
stay equipped, temporary items and the recycle bin are never swept, and the 9999 limit counts
stored slots (one per item id + augment block, so a 99-item stack is one slot). `//storage`
uses the same locker automatically for the no-slip gear that a job cannot equip, and `//locker`
remains the manual catch-all for ammo, jugs and crafting materials.

## Working stock (auto-refill)

The client refuses to use an item it cannot see, so a hidden-only consumable can never be
auto-pulled at the moment of use: ninjutsu tools and medicines must be in the inventory, and a
jug must be equipped. Fanxi keeps a small working stack visible and refills it from the hidden
locker:

- **Inoshishinofuda / Shikanofuda / Chonofuda** — Utsusemi Ichi/San/Ni consume one tool and the
  stack is topped back up from the locker, so a cast never leaves the client without the tool.
- **Pet Food Theta** — one stack stays visible for Reward (the server still needs the Reward
  ability itself).
- **Dawn Mulsum** — three stay visible; a use restores 25–50% of the pet's maximum HP and
  pulls another from the locker. It has no effect on GEO Luopans. The server has no pet HP model
  yet, so it reports "no pet to heal" until Call Beast/pet logic exists.

```
//stock                    refill the visible working stacks and show current/target
```

Zone-in also runs the refill automatically. Call Beast jugs are the exception: they are bulk
stored in the locker and `//locker grab <jug> 12` is the current way to bring one out. Call Beast
spends the equipped jug, Bestial Loyalty keeps it, and the HUD's Call Beast tile lists whatever
jug stacks are visible. The pet's Ready moves are shown by the HUD; resolving their damage is
still on the pet to-do list (`docs/pets.md`).

## Commands

Chat commands remain the fastest way to exercise the world:

```
//zone 100                 West Ronfaure (the monster camps)
//zone 246                 Port Jeuno (NPCs and the shop)
//pos <x> <y> <z> [rot]    reposition
//where                    zone and position
//warp mark [alias]        save the spot you are standing on as 1-1000
//warp me <n|alias>        return to one of your saved places
//warp all <n|alias>       return with every online character on your account and subs
//warp all me              call every other online character on your account and subs to you
//warp call <name>         call one of them to you (the launcher's post-relog pull)
//warp list [page]         print the saved places (8 per page)
//warp delete <n|alias>    forget a saved place
//warp rename <n> <alias>  name or clear a saved place from chat
//entities                 list live NPCs/monsters and their targids
//trust [list]             list the alter egos currently out
//trust release <id|name|all>  release one or every alter ego
//trust joachim [songs]    show Joachim's saved song set
//trust joachim set songs "<name>" ...  up to four, in singing order
//trust <id|name> [list]   show a support Trust's saved action set
//trust <id|name> set songs|spells|rolls "<name>" ...  ordered, up to its limit
//trust <id|name> set default  return that Trust to the built-in logic
//makeparty                drop every online sub from its party, then invite it
//invite [subs|all|<name>] party every online sub-account, or invite one player by name
//heal                     restore HP/MP
//time <hour>              set Vana'diel hour
//storage organize         store every other job's gear, pull this job's set into the wardrobes
//storage store <job|all>  store a job's gear, or everything this job cannot equip
//storage grab <job|all>   pull a job's gear, or everything, back into the bags
//storage list [job|all]   what is stored, by job
//locker store|grab <sel>  use the hidden 9,999-slot locker manually (all, ammo, back, materials, name)
//locker list              list the locker's contents
//stock                    refill the visible working consumables from the locker
//ws <name>                use a weapon skill (needs 1000 TP; self skills need no target)
//ja <name>                use a job ability; quotes around multi-word names are optional
//job <job> [sub]          change job (bags, buffs and TP); a city also refills HP/MP
//job <name> <job> <sub>   the same swap on another character on the account (main + subs)
//character model <race> <1-48|random>
                          change race/face/hair colour/size; `face 2 hair a size m` and
                          `random` are accepted, and the live model repaints
//doors auto [on|off]     automatic doors, city/outdoor zones only (off by default)
//abilities                re-send the command data that fills the Abilities menu
//traits                   list the current job pair's job traits and their modifiers
//help                     list commands
```

**Doors are manual by default.** A normal door stays shut until the player targets it and
presses action, or the optional automatic mode is on. `//doors auto on` makes the server open
the nearest door within five yalms as the player walks up; it is stored per character in
`char_settings` (migration 133) and only runs in city and outdoor zones, so dungeons keep
retail doors. `//doors auto off` returns to retail behaviour. The command reports the mode and
`//doors auto` alone toggles it.

Port Bastok's drawbridge is not one of those doors. Its three moving entities (`_6ke` span,
`_6ks` and `_6kt` gate ends) spawn lowered and stay lowered. The airship arrival that raises
them is not implemented, and the old blind six-minute cycle raised the bridge with no ship to
explain it; when it also started the client's drawbridge event (70) on a player standing on the
deck, that player's camera stayed in the cutscene after the event did not finish. The timer and
event are gone. The bridge never opens when a player targets it, and the automatic-door mode
never touches it. A real arrival can raise and lower the same three entities when the transport
is added.

`//warp` stores a row in `char_warps` (migration 110) with the zone and position, so the list
survives a relog. The next number is one past the highest existing one; an alias is optional and
must be unique per character. `me` and `all` accept either the number or a case-insensitive alias
(prefixes are accepted when exactly one warp matches). `all` selects the online sessions whose
account is the sender's main account or one of its sub-accounts; it is the multibox group, not the
whole zone. `all me` (also `all here` and `all self`) is the reverse call: the sender stays put and
every other online family session zones in at the sender's current zone, position and heading. A
saved alias named "me" does not shadow it (the same holds for "all", "here" and "call"). `call
<name>` is the same move for one character: the
name is resolved on the server, so a box in another zone still answers, and the launcher sends it
by itself when a box comes back from a relog. Parked (`//sleep`) boxes are left out of all three —
their client only reads chat, so a zone-in sent to one would never be acknowledged and the session
would stay `zoning` for good; wake it first. The launcher's **Warps** page reads and edits the same
rows and has a **Warp team to me** button for the same call, so a mark made in game can be renamed
there and vice versa. Home Points keep their own `//hp` command; `//warp` is the custom list.

**A zone line takes the boxes with the leader.** The client only asks for a zone when its own
character steps on a line (`C2S 0x05E`). The follow controller drives a box through the leader's
last point, so it sometimes reaches the line and zones itself — but not always (a wall, a long
gap, or a headless box with follow off leaves it short), and then it would stand in the old zone
while the leader loads the new one. Fanxi collects the online main-family sessions that are
standing in the leader's old zone and hands each of them the same `0x00B` the leader got, so every
client runs the zone-in script for the destination. The leader zones at once and every box is
handed its own `0x00B` on the next tick, so the team arrives together; the clients overlap their
zone loads, which is why a batch is faster than spacing the hand-offs (a dropped hand-off no
longer loses a box — see [protocol](protocol.md#4-zone-udp)). A box that did walk through
the line itself has already arrived, so its queued move is dropped instead of reloading it. Parked
(`//sleep`) boxes are left where they are, as with `//warp`, and only the main account leads: a sub
that crosses a line alone zones by itself and drags nobody.

In chat, a `//` command can be completed with **Tab** (see
[docs/control-panel.md](control-panel.md#command-completion)). `//wa` + Tab becomes `//warp `;
`//warp ma` + Tab becomes `//warp mark `. An ambiguous prefix is left as typed — `//w` and
`//warp ` do nothing, and `//wh` + Tab becomes `//where ` — so add a letter and press Tab again.

`//job` is a self-contained swap. It takes the old outfit off and runs `//storage organize` for
the new job: every piece the new job cannot equip leaves the bags (a slip when the item has one,
the 9,999 locker when it does not) and every stored piece the new job can equip comes back into
the Mog Wardrobes in equip-slot order. That includes the job's Ambuscade cape builds, which stay
in the locker while another job is active. It then wears the best gear it can find (including
pieces in the Mog Wardrobes), and the organizer's tidy moves the job's loose inventory/Safe gear
into the wardrobes so the set is in one place. Working stock (ninjutsu tools, pet food, Dawn
Mulsum) stays visible so the client can still use it; equipped pieces stay on. The other 21
jobs' gear and capes stay in storage; `//storage list all` shows the counts and
`//locker grab jsecapes` remains the manual way to pull every cape out.

A job change also replaces the character's state, not just their gear. Every status effect
wears off, including food, songs, rolls and job-ability buffs; the conquest family (**Signet**,
**Sanction**, **Sigil**, **Ionis**) belongs to the region rather than the job and stays on. TP
is earned with the old weapon and is always cleared. In a city or town (and in a Mog House) the
change is a rest: HP and MP refill to the new job's maxima. Anywhere else — a field, a dungeon or
an instance — the maxima are recomputed but the current bars are left alone, so the player has to
heal or rest before the next fight. A change is refused outright while an event menu or cutscene
is open, while the character is in combat (engaged, or a living monster's hate target/claim), or
while knocked out, and in the Dynamis instances, including **Dynamis - Divergence** (zones
294–297), where the error is `You cannot change jobs in this area.` The Moogles' Change Job menu
runs the same buff, TP, HP/MP and event/fight checks.

The three-word form, `//job <character> <job> <sub>`, runs that same swap on another online
character in the account family (the main account or one of its sub-accounts), so the leader can
change a box without typing into its client. The word count is the rule: `//job sam war` changes
you, `//job Threedough sam war` changes Threedough. The name is resolved on the server and the
target's own unlocked jobs, slips and lockers are used; the caller gets one confirmation line
(`Threedough is now SAM/WAR.`) while the target's chat shows the store, pull and tidy detail. The
party roster is re-sent to every member, so the leader's party window shows the new job pair right
away. A parked (`//sleep`) box is refused — its client is not reading job packets, so wake it
first, as with `//warp call`.

A `//job` change also moves the style lock with the job. The old locked appearance is cleared
before the swap, and after the new gear is on the command locks that outfit (message 267 and a
fresh `0x051`) and respawns the character for the clients that are drawing it, so a box does not
keep wearing the previous job's clothing in anyone's window. The Moogles' Change Job menu keeps
retail's behavior: it clears the lock and leaves it off.

The 22 capes all share one item id per job, so each copy's augment build lives in its 24-byte
extdata block. The locker keeps that block alongside the item (`char_locker.extra`), and a
grab writes it back, which is why 198 named copies can exist without losing their augments.

### Slash commands

The client parses its own slash commands; the server only has to answer the ones that need
world state. The commands that used to disappear are now covered:

```
/lockstyle on|off         lock the current appearance; armour swaps keep the look, weapons still
                          show the equipped main/sub models
/lockstyleset [n]         lock an equipment set's appearance (no argument: what is worn now)
/lockstyle                ask whether style lock is on
/wave /nod /bow /goodbye  emotes: animation and text, for the player and everyone in the zone
/bye                      host alias for /goodbye (the client's table has /goodbye and /farewell)
/dance /cheer /clap ...   the full emote list, including /dance1-4, /jobemote and /bell
```

An emote is the client's `C2S 0x05D`; Fanxi echoes `S2C 0x05A` back. Style lock is `C2S 0x053`
and is stored per character (the `style_*` columns from migration 0085), so it survives a
relog and a zone change. Locking a new appearance has the client's usual ~10-second cooldown;
a command typed sooner is ignored by the client, not by the server. The client has its own
copy of the flag, so `/lockstyle on` sends mode 1 ("continue") rather than mode 4 while it
believes the lock is already on; Fanxi honours it by locking what is worn, otherwise the
command would do nothing after the two sides ever disagreed. A job change turns style lock
off and forgets the locked models, so the previous job's outfit cannot come back on the
next zone. `/heal`, `/attack`, `/ma`, `/ja`, `/ws`, `/item` and `/equip` were already answered
through their own packets. The party commands (`/pcmd add|leave|kick|leader|breakup`), the
alliance ones (`/acmd add|leave|kick|leader|breakup`) and the party menu's invite/accept actions
are answered by `C2S 0x06E`/`0x074` and the group packets below. `/shout`, `/tell`, party chat
(`/p`) and linkshell commands still have no channel in this world.

### Parties and alliances

The client's group menu is a view of server state, not a local list. A `/pcmd add` or a menu
invite sends `C2S 0x06E` with the target's character id (or its targid), and the server answers
with `S2C 0x0DC`; the invitee's Accept sends `C2S 0x074`. On acceptance the server sends `0x0C8`
with up to twenty `char id, targid, party/leader flags, zone` rows and one `0x0DD` per member
(HP/MP/TP, job/sub-job, level, member number, name). A member outside the receiver's zone is sent
their zone number instead of vitals, so the client prints the zone. HP/MP/TP changes ride the same
`0x0DF` packet the player gets for themselves.

An invitation to a **server-owned sub-account in the inviter's own account family** skips that
prompt: the server accepts it on the sub's behalf and sends the roster straight away. This is what
lets a headless box join from `/pcmd add` when there is no window to click. A main account, or
another player's character, still receives `0x0DC` and answers with `C2S 0x074`. Set
`FANXI_AUTO_ACCEPT_SUB_INVITES=0` to require the prompt for every invitee.

`//invite subs` (also `//invite all` or `//invite team`) resolves the account family's online
sub-accounts on the server and invites them all in one command; `//invite <name>` invites one
player. Because the server resolves the name, these work even when a box is outside the client's
45-yalm player range or in another zone, where the client's own `/pcmd add <name>` may have
nothing to resolve. The Control room's **Live party** header has an **Invite** button for the same
choices.

**A returning main gets the team back.** A main that logs out, freezes past the session timeout or
is force-relaunched is removed from the party, and one of the subs becomes leader. The subs remain
grouped, so a fresh `/pcmd add` to them is refused. On the main's next fresh login the server finds
the party whose members all belong to that account family, joins the main to it and moves the lead
back. Only a fresh login does this; a zone line after a deliberate `/pcmd leave` is left alone.
The same recovery runs first in `//invite subs`, which then invites any online sub that is still
missing. A party containing a character outside the family is never taken over.

`//makeparty` is the destructive form: every online sub that is in another party leaves it first,
then accepts the invite into the caller's party. The Party Info window's **Make party** button runs
the same command, so a team scattered across old parties becomes one group in a click. The caller
must be the party leader (or solo).

A party holds six players; an alliance holds three parties and is led by the main party's leader.
`C2S 0x06F`, `0x070`, `0x071`, `0x076`, `0x077` and `0x078` cover leave, disband, kick, roster
reload, leader change and the group id. Invitations expire after thirty seconds. The roster is
in-memory: a server restart or a character's logout ends the group, and party/alliance chat is
still not implemented.

`//abilities` is the manual form of the automatic refresh: the client builds the Weapon Skills
menu before the zone-in `0x0AC` copy is read, so the server also sends the command data after
the `0x061` stats request and on two short timers, with `0x0AC` before the `0x062` skill packet.

The `0x0AC` Weapon Skills block follows the equipped weapon, not the whole table: it carries the
main-hand weapon's skill type (hand-to-hand when unarmed) plus archery/marksmanship for the
ranged slot, and only skills at or below the character's value for that weapon. Merit and gear
skill bonuses count. Quested/relic/empyrean/aeonic skills have no `skill_level`; they are offered
once that weapon skill is mastered (350+, the level-99 band). The list also applies retail's
main-job restrictions (`game/weapon_skill_jobs.py`): a COR with a gun sees Wildfire and Leaden
Salute but not Coronach or Trueflight, a COR with a sword does not get Atonement or Knights of
Round, and the merit skills use the wider main-job lists BGWiki publishes (Requiescat includes
COR, Resolution does not). The server rejects a weapon skill outside that list, so `//ws` and the
advertised bitmap agree. Campaign Battle skills (Uriel Blade, Glory Slash, Tartarus Torpor) need
a Campaign weapon and a Campaign zone, so they are left out of the list and refused by name.

Prime weapons are the exception to the skill-value rule. Each one carries its own skill through
the item's `ADDS_WEAPONSKILL` (`item_mods` 355), so the skill is usable only while that weapon is
equipped: Dokoku grants Zesho Meppo, Kusanagi grants Tachi: Mumei, and so on. The `weapon_skills`
table stores these rows with a negative `skill_level`, which the normal type/value filter skips;
`ZoneSession.equipped_weapon_skills()` adds the ids the current outfit grants through 355. An
ordinary katana, even at 350+ skill, therefore never advertises Zesho Meppo. Migration 114 adds
the fourteen Prime skills and the 355 rows for the 119 III Prime weapons (Loughnashade's Prime
song is not a weapon skill and Duban is a shield).

A weapon skill is more than its damage roll. `server/fanxi_server/game/weapon_skill_effects.py`
carries the rows LandSandBoat's `scripts/actions/weaponskills/*.lua` give an extra behaviour:

- **Self skills need no target.** Myrkr (Hvergelmir/Tupsimati) restores 20/40/60% of maximum MP at
  1000/2000/3000 TP and removes up to three status ailments; Dagan restores 22/33/52% HP and
  15/22/35% MP. Both play their animation against the player and never need a claim or melee range.
- **Drains convert the hit.** Spirit Taker and Mystic Boon restore MP equal to the damage, Entropy
  20% of it, Catastrophe 50% as HP, and Sanguine Blade 50/100/160% as HP. Energy Drain and Energy
  Steal have no HP damage at all: their formula uses dagger skill and MND and prints the MP drained.
- **Debuffs land after a hit that did damage.** Poison, Plague, Stun, Silence, Blind, Bind, Sleep,
  Weight, Slow, Attack/Accuracy/Defense/Evasion Down, Magic Atk./Def./Eva. Down, INT Down and
  Critical Hit Evasion Down are applied to the monster with their retail durations (interpolated
  from 1000/2000/3000 TP) and the same Magic Accuracy resist term spells use. The skills retail
  rolls for use its TP/3000 chance.

The TP spend is the usual one: the skill consumes all TP up to 3000 and the bar keeps the excess.
Gear and traits that change how that TP is used are read from the merged modifier pool:
"Weapon skill damage" (`ALL_WSDMG_ALL_HITS` 840 and `ALL_WSDMG_FIRST_HIT` 841), the per-skill
`WEAPONSKILL_DAMAGE_BASE + id` block (571 Combo, 580 Final Heaven, 707 Blade Metsu, ...),
generic "TP Bonus" (345), "fTP +x" gear (`ANY_FTP_BONUS` 1144, in 1/256 units), "Weapon skill
accuracy" (48), and Fencer's TP Bonus (903) and critical-hit rate (904) while single-wielding a
one-handed weapon. The skill's own fTP anchors, WSC, hit count, critical rate, Attack multiplier
and Defense-ignore fraction come from `data/weapon_skills.json`; every hit is rolled and packed
into one action, and the first-hit damage line applies only to the first hit. See
[combat-damage.md](combat-damage.md#weapon-skills) for the formula.

The client does not read the bitmap directly. It keeps a command-id list at
`[ability_list] + 0x160` (count at `+0x1760`) that it saves in `aix.dat`; old profiles kept the
all-weapon-skill list, and a fresh profile had an empty one. `host/addons/hooks.c` rebuilds that
list from every `0x0AC` packet on the game thread, so the Weapon Skills menu (in the field and
while engaged) shows exactly the advertised skills. The list is rebuilt at zone-in, after
`//abilities`, and after a weapon change. A client started before this patch keeps its old list
until it is restarted once. `//ws` still enforces the filtered list.

The list's command array and count are struct offsets, not per-build addresses: they are
`+0x160` and `+0x1760` in both the 2025-07-03 and 2026-10-05 clients (checked against the menu
code that reads them). `host/addons/hooks.c` supplies those two offsets itself whenever
`meta/builds.json` maps `ability_list`, instead of requiring every build entry to repeat them.
`tools/newbuild.py` carries addresses only, so a new build that kept `ability_list` but not the
offsets used to compile the whole hook out, leaving every job's Abilities menu with "No
abilities available." If a future client changes the object's layout, update the two defaults in
`host/addons/hooks.c`; do not put them in `meta/builds.json`, where the new-build tool would try
to relocate them as addresses.

### Job traits

`0x0AC`'s fourth block (bytes 192..223) is the client's job-trait bitmap. The server serves the
game's trait ids, job/level gates and modifier values in
`server/fanxi_server/game/traits_data.py`, takes the highest rank reached by the main job and the
support job (an equal rank does not stack), and advertises every active id in that block.
`//traits` prints the same list, with the modifier values, and re-sends `0x0AC`.

The Abilities menu itself is built from the client's saved command-id list, not from the bitmap.
`host/addons/hooks.c` rebuilds that list from `0x0AC`; it now appends traits as `0x600 + trait
id` (the client's known-bit encoding) as well as weapon skills and job abilities. Without that
host hook the server's trait block is correct but the "Job Traits" page stays empty, so
`host64` has to be rebuilt after changing the hook. The log line reports both totals, e.g.
`command list rebuilt from 0x0AC: 53 entries (18 job traits)`.

Trait modifiers use the gear modifier ids, so they are merged into the equipment dict before
`stats.build_character()`. Attack, Defense, Accuracy, Evasion, maximum HP/MP, critical damage and
the damage limit therefore read traits and gear through the same path. `Max HP Boost` and
`Max MP Boost` are added to the sheet maximum, and a job change recomputes the stored maxima.

The eight element icons under Attack/Defense in the equipment menu are server data, not item
data. They are the `def_elem[8]` block at body `0x30` of the `0x061` status packet, and the
client draws exactly what that block carries. `char_stats()` fills it from the same merged
modifier dict: `FIRE_MEVA` through `DARK_MEVA` (`item_mods` ids 15-22, the `Fire+20` tooltip
line, in the client's fire/ice/wind/earth/thunder/water/light/dark order). Because the dict
already includes augments, traits, job points, buffs and food, a Fire Belt's `Ice+20 Water-20`
and a Demon's Ring +1's `Light-20 Dark+13` add up like any other stat. The values are signed
int16s, so a piece that lowers an element shows a negative orb instead of being clamped to 0.

`//traits` lists every active trait.  Fast Cast, Dual Wield, Store TP, Mag. Burst Bonus,
Shield Mastery (a shield-block addition), Clear Mind (a resting MP addition), Damage Limit+
and the stat boosts change behaviour today; the killer/resist families are kept for the
client's trait list and future combat work until the monster family and status-resist models
exist.  The closing "Passive tick" line adds the worn gear's Regen, Refresh and Regain to the
traits, so `Chirich Ring +1`, `Stikini Ring +1` and `Karieyh Ring +1` report their tick even on
a job pair with no Auto Regen/Auto Refresh trait.

`Auto Regen` (White Mage 25/76, Rune Fencer 35/65/95) and `Auto Refresh` (Paladin 35, Summoner
25/90) are passive modifiers (`REGEN`/`REFRESH`), not status effects: they put no icon in the
client's status bar. The zone tick restores their value once every three seconds while the
character is alive, and gear with `Regen`/`Refresh`/`Regain` adds to the same modifiers. The
tick re-derives the HP/MP maxima from the stat sheet and an equipment batch calls
`refresh_vitals`, so a set that raises max HP/MP -- or the reforged body with `"Refresh"+4` --
cannot leave the character stuck below its own maximum. Regain pays 5 TP to Karieyh Ring +1's
wearer on that same tick, up to the 3000 TP cap. `Auto Refresh` is not a Red Mage trait; Red
Mage has the Refresh spell instead. Blue Mage gets both from its set spells, which Fanxi does
not track yet.

## Spells, buffs and debuffs

A cast is resolved by `cast_magic()` and `resolve_casting()` in `game/zone.py`.  The
effect table in `game/effects.py` maps a spell name to the client's status-effect id,
its duration and the numbers the engine reads:

- **Self buffs** (Utsusemi, Monomi, Tonko, Protect, Shell, Haste, Regen, Refresh,
  Stoneskin, Blink, Phalanx, ...) land on the caster.  The finished action carries the
  effect id in its value and message 230, and the `0x037` status packet puts the icon in
  the client's buff bar.
- **Debuffs** (Kurayami, Hojo, Dokumori, Jubaku, Sleep, Blind, Poison, Slow, Paralyze,
  Gravity, Bind, ...) land on the monster.  The action carries the effect id and message
  237; the server keeps the timer and the potency in the entity's `effect_state`.
- Utsusemi stores a shadow count (3/4/5 for Ichi/Ni/San).  A monster hit consumes one
  shadow and sends message 31 instead of damaging the player; at zero the icon goes away.
  The buff icon is the count itself (66, 444, 445, 446 for one to four or more), so it
  steps down as each shadow is used.
- Blind lowers the monster's accuracy, Slow lengthens its swing interval, Paralyze can
  skip a swing, Sleep/Stun stop it, Bind stops movement and Weight slows it, Attack Down
  lowers its damage, and Poison/Bio tick damage every three seconds.
- Dia and the Helix line are the two debuffs whose action carries the opening damage
  instead of message 237.  Dia's small hit and 1-5 HP tick are table values.  A Helix's
  opening nuke (`combat.helix_damage`) is stored as that effect's tick, so the monster
  takes the same number again every ten seconds (`tick_interval`) for 30/60/90 s by
  Scholar level; the first tock lands 1-10 s after the cast.
- Sneak and Invisible keep a monster from aggroing.  Regen/Refresh and Poison tick on the
  player through the same three-second timer as the passive Auto Regen/Auto Refresh.
- **Geomancy** is two bubbles: the Indi- aura around the Geomancer and the Geo- one around
  the Luopan (a Geo- cast also drops the Luopan and sets its drain, potency and MP cost).
  A cast replaces that bubble's previous aura — Indi-haste and Geo-frailty are up together,
  but a second Indi- takes the first one off the whole party.  `_indi_aura` remembers each
  bubble's status and the monster its hex landed on, so a new hex clears the old one and
  switching to a party aura clears a hex.  The friendly half carries the stat modifiers in
  `geomancy.INDI_EFFECTS`; the hex half cuts the monster's own Defense, Evasion, Accuracy,
  Attack, Magic Defense or Magic Evasion by its 10% potency.
- **Accession** widens the next white enhancing spell to every party member within ten
  yalms of the caster (the caster included).  Each recipient gets the caster's rolled
  duration, tick and power, its own gain-effect result and its own `0x037` icon list, so
  a boxed client draws the buff immediately.  Haste and Reraise are retail's exceptions
  and keep the stratagem up; the icon is spent when the spell lands.
- `game/spell_effects.py` is generated by `tools/import_lsb_spell_effects.py` from
  LandSandBoat's enhancing, enfeebling, ninjutsu and song tables, and gives every spell an
  icon even where the engine has no numbers for it (the Bar- and Boost- lines, Protectra
  and Shellra, the songs, the -ga line).  The hand-written tables above override it, so a
  spell with ticks, potency or modifiers keeps them.  Spells LandSandBoat's tables stop
  short of --- the -storm II line (whose icons are 589-596, not the tier-I ids), the
  -Carol II songs, Enlight, Endark II, Reraise II-IV, Adloquium, Animus and the trust
  songs --- live in `effects.SWEPT_EXTRAS`.  Blue magic (its durations are script
  variables, not table columns) and Geomancy's Indi-/Geo- bubbles are not in the sweep.
- A support spell with no entry in either table still finishes; it just does not put an
  icon on anything.  A spell's target flags decide whether it is aimed at the caster or a
  monster; enfeebles always require a live monster.

Buff durations are not just the table's `duration`.  `effects.buff_duration` adds flat
seconds first (Light Arts/Tabula Rasa on the Regen line, gear such as Lugh's Cape or
Telchine's Regen seconds), then multiplies the gear's listed Enhancing Magic Duration and
its augment Enhancing Magic Duration as two separate terms, then applies Perpetuance
(2.0x, or 2.25-2.65x with the Savant's/Arbatel hands).  The Regen tick goes through
`effects.regen_tick`, where `"Regen"` potency multiplies the base and Light Arts/Tabula
Rasa add flat HP.  `buff_duration` also accepts `light_arts_jp_rank` (+3 s per rank, 20
max); the zone passes 0 because this build does not store JP ranks -- the client's JP
menu is maxed only to unlock the job gifts.

The same merged modifier dict is the only spell-modifier source.  `combat_mods()` merges
equipped gear, job traits, active buff modifiers, food and HP/MP merits; magic damage,
Magic Accuracy, Fast Cast, the stat sheet, `buff_duration`/`debuff_duration`, healing and
the enfeebling potency all read it.  Enfeebling and dark spells add `ENF_MAG_DURATION` /
`DARK_MAGIC_DURATION`; enfeebling potency reads `ENF_MAG_POTENCY`; Cures read
`"Cure" potency` (and II/received/bonus); Refresh reads `"Enhances Refresh"`; Stoneskin
reads its bonus HP; Drain/Aspir read their potency line.  Gear the engine does not model
(augments stored only as client extdata, most food, another player's buffs) still does not
appear.

Food lives in `food_effects` (`item_id`, duration, modifier dict, animation).  The client's
`C2S 0x037` carries the container (`Category`, 0x10) and the slot (`PropertyItemIndex`,
0x0E), not the item id: the four bytes at 0x08 are `ItemNum`, which is always zero.
`item_use` resolves that slot, consumes exactly that stack, stores the dict on the session,
puts the Food icon up and sends the item finish action (`0x028` category 5) with the food's
animation so the character plays the eat/drink motion; `combat_mods()` adds it to the same
pool and the three-second tick removes it when the timer expires.  The starter table has
Apple Pie, Witch Soup, Chocolate Cake, Miso Ramen and Red Curry Bun; adding a food is one
row in `food_effects` plus its `items` row.  The attack, defence and accuracy percentage
lines apply through their flat caps; HP/MP percentage food caps are not applied yet.

Dispense pouches and quivers are charged waist equipment, not consumables.  The four RMEA
bullet pouches and four quivers live in `item_dispense` (`item_id`, `ammo_id`, quantity,
charges, use delay, reuse) and share the same `C2S 0x037` path.  Using one leaves the piece
in place, adds its 99 arrows/bolts/bullets, and writes the 24-byte `ItemTimerInfo` block
(charges plus the last-use Vana'diel timestamp) into `char_inventory.extra` on that exact
bag copy.  `0x020` turns it into the client's charged extdata, so the item menu shows
`1/1` and the hour-long reuse countdown across logout; a second use before the timer is
ready is refused, and a full inventory refuses without spending the charge.  The timer
helpers are in `game/item_usable.py`.

Rest is `C2S 0x0E8` (`/heal`).  While resting, the player recovers 5% of maximum HP and
MP every three seconds; taking damage, casting, attacking or moving stops it.

Warp, Warp II and Retrace send the character to the **one Home Point set in Profile**
(`characters.home_*`, updated by the crystal's "Set Home Point" choice), not to a crystal
registered in the current zone.  South Gustaberg has no Home Point crystal, so the old
current-zone lookup refused Warp there even though the character's set Home Point existed.
A K.O. without a Raise returns to the same set Home Point instead of reviving in place.
Home Point teleportation from a crystal uses the registered `char_home_points` list and
the client menu index (`home_points.hp_index`); opening the crystal menu requires the
`world_npcs.hp_index` column, which migration 0084 fills.

## Content tables

| Table | Meaning |
|---|---|
| `world_npcs` | NPC instance: zone, script, display name, position, model, flags |
| `npc_lines` | ordered ambient lines per NPC |
| `monster_templates` | reusable monster template: name, model, level range, HP, combat stats |
| `monster_spawns` | placed monster: template, zone, position, respawn seconds |
| `trusts` | factual alter-ego appearance and combat data, one row per Trust spell |
| `trust_spells` | the spells one alter ego can cast, with each spell's unlock level |
| `items` | item id, name, stack size, usable flag, equip slot, level, Rare/Ex flags |
| `char_inventory` | per-character slots; slot 0 is gil (`65535`) |
| `quests` | quest key, reward, required template and kill count |
| `char_quests` | accepted/completed state and progress |

Original content is authored directly in `database/migrations/0003_world_content.sql`. A larger
world can move it to JSON/pack files and keep SQLite for state; the packet and entity layers do
not care where the rows came from.

## Limits

This slice deliberately omits:

- client event cutscenes and DAT-driven menus (NPC text uses chat);
- ranged attacks and skillchains (spells, weapon skills, job abilities and monster TP
  moves are implemented, and the Abilities menu lists the weapon skills and job abilities the server
  advertises);
- linkshells, parties beyond the local player line, auctions, bazaars and mail;
- raise, and the status effects outside the spell and weapon-skill tables (the engine tracks
  the ninjutsu, enfeebling, enhancing and weapon-skill families);
- skillchains and magic bursts, and the Relic/Mythic/Empyrean weapon-skill aftermath
  (Prime aftermath is modeled for melee/ranged weapons; the per-skill damage and status
  rows above still apply);
- collision data for zones whose model is a shell plus separate interior sub-regions (the
  outdoor mesh is read, the interiors are not);
- dynamic obstacles: only the static zone mesh blocks a monster, not a door that opens or
  another player;
- loot tables beyond the quest reward and shop stock;
- anti-cheat or client-position validation.

The client protocol details and the LandSandBoat study that informed the architecture are in
[protocol.md](protocol.md) and [landsandboat-study.md](landsandboat-study.md).
