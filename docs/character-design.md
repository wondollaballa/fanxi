# Character design

A Fanxi character's appearance is four values: race (1–8), face (1–8), hair
colour (A or B) and size (small, medium, large).  The client combines face and
hair colour into one look byte:

```
look = (face - 1) * 2 + hair        hair 0 = A, 1 = B
```

Face 2 / Hair A is look 2.  Before migration `0093_character_design.sql` the
`characters.face` column held that combined byte; the migration splits it into
`face` + `hair` without changing any existing character's appearance.

## In game

```
!character model hume 8              Face 2, Hair A, Medium (the 8th of 48)
!character model mithra random       random face/hair/size inside Mithra
!character model random              random race and design
!character model elvaan face 3 hair b size l
!character                            show the current design
```

Races are `hume`, `humef`, `elvaan`, `elvaanf`, `tarutaru`, `tarutaruf`,
`mithra` and `galka`.  The 48 variants of a race are numbered with size
fastest: 1–3 are Face 1 / Hair A / small–large, 4–6 are Face 1 / Hair B,
7–9 are Face 2 / Hair A, and so on.  The command writes the row, repaints the
player's own grap/login blocks and respawns the player's 0x00D entity for the
other clients in the zone.

## Launcher

The Rust launcher has a **Design** page next to **Characters**.  It shows the
current model, race tiles, the eight faces, the two hair colours and the three
sizes, plus the variant number, the look byte and the exact in-game command.
**Apply design** calls:

```
PATCH /api/v1/characters/{id}/design   {race, face, hair, size}
```

The service updates the row and calls the game gateway's design listener, so a
running client repaints immediately.  The API response includes `hair`,
`variant` and a labelled `design` object alongside the usual character fields.

### Previews from the DATs

The launcher cannot host the game's skinned character renderer.  Instead,
`tools/capture_character_previews.py` borrows a real client:

* it snapshots a spare sub-account/character row;
* writes one design into it;
* restarts the client, which builds the real model from its own DATs;
* captures the character-select frame and crops it;
* puts the original row back.

```bash
tools/capture_character_previews.py --races 1 --resume
tools/capture_character_previews.py --races 5,6 --crop 240:440:520:190 --resume
tools/capture_character_previews.py --verify --races 1
```

Output goes to `launcher-rs/public/design/<race>-<face>-<hair>-<size>.jpg`.
The images come from the user's own Square Enix files, so the directory is
gitignored; the design page falls back to its original vector model when a
capture is missing.  One medium capture per variant is enough — the page
scales it for small/large.

## Offline edits

`tools/character_design.py` uses the same encoding without a running server:

```bash
tools/character_design.py --character Onedough --race hume --variant 8 --dry-run
tools/character_design.py --character Onedough --race mithra --random --apply
tools/character_design.py --list hume
```

It takes a backup under `data/backups/` before writing.  A saved change is read
on the next login or zone; the in-game command is the instant path.
