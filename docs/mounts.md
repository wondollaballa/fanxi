# Mounts

FINAL FANTASY XI's mounts are client-side art with a server-side id. The client owns the
models, the Mount menu and the riding animation; the server unlocks the table, says which id a
character is riding, and keeps the state for everyone else. Fanxi speaks that protocol, so a
character can call any of the mounts the installed client knows — and so can its whole sub team
at once.

The catalogue is the client's own `mounts.names` table (NA file id 55681, JP 55561,
descriptions 55682/55562). Its index **is** the mount id every packet carries. The current
install has 39 of them, `0 Chocobo` through `38 Bubble Crab`; the list lives in
[`mounts.py`](../server/fanxi_server/game/mounts.py), generated from
[`tools/client_mount_names.tsv`](../tools/client_mount_names.tsv) by
[`tools/dump_client_mounts.c`](../tools/dump_client_mounts.c) and checked against it by the
test suite, so a client update that adds a mount fails a test instead of going unnoticed.

## Commands

| Command | What it does |
|---|---|
| `//mount` | The Mount HUD (the client-side window; see below). On a box without the HUD it lists the mounts. |
| `//mounts [on\|off\|toggle]` | The Mount HUD, explicitly (the client-side command; never reaches the server). |
| `//mount <name\|id>` | Call one mount for this character. `//mount rap`, `//mount 5` and `//mount "Magic Pot"` all work; an ambiguous prefix (`red`) names the candidates. |
| `//mount party` | Mount the whole party: this character **and every online sub-account box**, each with a **different random mount**. `//mount all` is the old name and still works. |
| `//mount party <name\|id>` | Everyone in the party rides that one mount. `//mount party random` asks for the random draw explicitly. |
| `//mount party off` (or `//mount all off`) | Dismount the whole party. |
| `//mount off` (or `dismount`) | Back on foot, this character only. |
| `//mount list` | Every mount with its id, four to a line. |

The client's own **Mount** menu (Abilities → Mount) and its `/mount <name>` command work too:
the client sends the mount action (0x01A, action 0x1A, the id in ActionBuf[0]), and the server
answers exactly the same way it answers `//mount`.

## What the wire carries

| Packet | Field | Use |
|---|---|---|
| `0x0AE` | 8-byte `MountDataTbl` | One bit per **unlocked** mount id. Fanxi sets every bit the client's table has, at zone-in and again for a client that re-zones. |
| `0x037` | `BufStatus` | The **Mounted** status effect (252, *not* a real buff: no timer and nothing to wear off) goes in the first free icon slot while a character is riding. |
| `0x037` | `server_status` (body `0x2C`) | The player's **animation**: `5` for a chocobo, `85` for every other mount (this is what makes the client draw a mount at all), and on foot the stance — `1` while engaged, `0` otherwise. It is the same field `0x00D` carries at `0x1B`; the rider's own client reads it as the local player's pose, so a status packet sent mid-fight must not say `0`. |
| `0x037` | `mount_id` (body `0x6F`) | The mount id. The packet grew to 0x78 bytes in later clients; the field sits after the older 0x60-byte body, so a short packet cannot carry it. |
| `0x037` | `Flags0` bits 13-15 | `Chocobo_Index`: 1 for the personal chocobo, 4 for the Noble Chocobo, 0 for everything else (the client's chocobo-seat selector). |
| `0x00D` | body `0x1B` | The same animation, for every other client that draws the rider. |
| `0x00D` | `Flags6` bits 4-11 (body `0x40`) | `MountIndex`, the mount id. Retail sends it even after a dismount so a client that missed the dismount does not draw an invisible player. |
| `0x00D` | `Flags1` bits 5-7 | `Chocobo_Index` again, for the same reason as 0x037. |
| `0x00D` | `CustomProperties` (body `0x30`) | The Noble Chocobo needs `1` in the second word, or the client draws a plain chocobo. |

The rider's own client is told with `0x037` (and the entity update), every other client with
`0x00D`. A zone line or a logout puts the character back on foot: the zone-in `0x037` carries
`mount_id 0` and animation 0.

### Switching mounts

The client builds the mount model when a ride starts and does **not** rebuild it while one is
out. Changing the id in place leaves the old model on screen. `set_mount` therefore puts the
character on foot first, waits `MOUNT_SWITCH_DELAY` (1.2 s) on the game's tick, and then calls
the new mount — the same path a player takes by dismounting and mounting again, with no
one-minute recast. A mount called from the game's own menu goes through the same code.

## The Mount HUD

`//mounts` (or plain `//mount`) opens a window with every mount the client knows:

- a picture per mount, a grid of cards, the selected card outlined and the one being ridden
  marked green;
- the name and description of the selection, and a hint with its `//mount` line;
- **Mount**, **Mount party**, **Dismount** and **Close** buttons. *Mount* calls the selected
  mount for this character; *Mount party* sends `//mount party`, the random draw for the whole
  team. The buttons and the chat commands cannot drift apart because the buttons send the same
  `//mount …` lines a player would type;
- a picture the player drops in `<data>/mounts/<id>.jpg` (or `.png`) wins over the built-in one,
  so a player can restyle the gallery without a build.

The window's position, picture size, column count and selection are saved with the rest of the
HUD (`//hud save`, or the same fields through the control port's `hud` command:
`show_mounts`, `mounts: {selected, columns, size, x, y}`).

The pictures in `assets/mounts/` come from the [FFXI Wiki](https://www.bg-wiki.com/ffxi/Category:Mounts)
mount pages — a front or side view of each mount with its rider — fetched by
[`tools/fetch_mount_art.py`](../tools/fetch_mount_art.py).  They are FINAL FANTASY XI artwork,
© SQUARE ENIX, used as reference art by a fan project; the surface pages credit it in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).  A few mounts only have their item icon on
the wiki; those icons are keyed onto the card's dark background instead of a white box.

The build embeds the set ([`tools/embed_lua.py`](../tools/embed_lua.py) as `mountart/<id>`), so
every client carries the gallery and no install step is needed.  A player's own
`<data>/mounts/<id>.jpg` wins over the built-in picture.

Prefer a picture of your own character?  [`tools/capture_mount_previews.py`](../tools/capture_mount_previews.py)
records them from the client itself: it asks the control port to call each mount, turns the
camera, waits for the riding animation and crops the frame (`--how inject` sends the `0x037` by
hand for a client whose server does not know mounts yet).  Put its output in
`assets/mounts/` and rebuild, or run it with `--no-install` and copy the ones you like into
`<data>/mounts/`.

## The launcher API

| Endpoint | What it does |
|---|---|
| `GET /api/v1/mounts` | The catalogue: id, name, description, Japanese name. |
| `GET /api/v1/characters/<id>/mount` | Whether the character is online, the mount it is riding, and the last one it called. |
| `POST /api/v1/characters/<id>/mount` | `{"mount": "<name or id>"}`, or `{"mount": "...", "all": true}` for the sub team, or `{"mount": "off"}`. An offline character simply remembers the choice. |
| `POST /api/v1/characters/<id>/mounts` | The Data page's **Get all mounts**: re-sends the `0x0AE` unlock table to a live client (and returns the usual `character_data` snapshot, whose `mounts` block lists the client's table and the character's last/current mount). |

`characters.mount` (migration 0135) is the last mount a character called, so a relog or the
launcher can preselect it. Being mounted is live state on the zone session, never a column.

## Not implemented

- Retail's one-minute recast between mounts and its thirty-minute ride are not enforced;
  mounts are a convenience here. Switching is a dismount + call, with the model-rebuild delay.
- Retail only allows mounts where chocobos may be ridden. Fanxi does not gate the call by zone;
  the client draws the mount wherever the model loads.
- Mount speed, music (`0x05F`) and the mount's whistle/key-item registration are not sent.
