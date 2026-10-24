# Third-party notices

Fanxi is MIT-licensed (see [LICENSE](LICENSE)). It contains code derived from an earlier
MIT-licensed project. That project's copyright notice and license are reproduced below, as the
license requires.

## Upstream MIT notice

```
MIT License

Copyright (c) 2026 Joshua Tyree

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Vendored libraries

The client vendors the libraries it builds against. They keep their own licenses and copyright
notices in their folders under `third_party/`:

| Library | License | Folder |
|---|---|---|
| SDL 3 | zlib | `third_party/sdl3/` |
| mbedTLS | Apache-2.0 | `third_party/mbedtls/` |
| LuaJIT | MIT | `third_party/luajit/` |
| SQLite | public domain | `third_party/sqlite/` |
| Dear ImGui | MIT | `third_party/imgui/` |
| Font Awesome Free | CC BY 4.0 (icons), SIL OFL 1.1 (fonts), MIT (code) | `third_party/` / `assets/fonts/` |
| Capstone (build-time, not vendored) | BSD-3-Clause | installed into `.venv` |
| pefile (build-time, not vendored) | MIT | installed into `.venv` |

If a license file is missing from a vendored folder, the upstream project's license applies; see
that project's distribution.

## Research references

[LandSandBoat/server](https://github.com/LandSandBoat/server) is a GPL-3.0 FINAL FANTASY XI server
emulator. It was studied read-only to understand zone, entity, combat and content flows. No
LandSandBoat code, SQL text, Lua, YAML, schema definitions, comments or transcribed game
dialogue is included in Fanxi. Factual item metadata (item ids, names, equip-slot masks, job
masks and model ids) was cross-checked against public item databases; see **Game data**. The clean-room notes and license boundary are in
[docs/landsandboat-study.md](docs/landsandboat-study.md).

## EquipViewer layout

The launcher's EquipViewer grid follows the slot order, 4×4 arrangement and defaults (32 px,
alpha 230, background alpha 72) of the [EquipViewer addon](https://github.com/Windower/Lua/tree/live/addons/equipviewer)
by Tako and Rubenator, distributed under the BSD-3-Clause license. No EquipViewer source code is
included: Fanxi decodes item icons with its own resource reader (`host/addons/res.c`) and draws
its own React grid.

## Game data

Fanxi ships no FINAL FANTASY XI data, binaries or assets extracted from the game. The client is
built on the player's machine from the player's own `FFXiMain.dll`, `FFXi.dll` and `ROM` folder.
`assets/` contains only Fanxi's own icons and UI art created for this project.

The Storage Slip item ids in `database/migrations/0065_storage_slips.sql` are game data,
cross-checked against the [BG-Wiki Storage Slip category](https://www.bg-wiki.com/ffxi/Category:Storage_Slip)
and the public Windower resources slip table (BSD-3-Clause). Only item ids and slip numbers are
stored; no Windower code is included.

`database/migrations/0066_gearswap_grant.sql` grants the gear named in `gearswap/`. Its item ids,
equip-slot masks, job masks and model ids are factual game data cross-checked against the FFXI
Wiki and the public LandSandBoat item tables (`item_basic` / `item_equipment`). The migration SQL
and the gear names are Fanxi's own; no LandSandBoat SQL text, schema or code is copied.

`database/migrations/0080_item_combat_data.sql` carries factual combat data for every item:
damage rating, delay, weapon skill type and the (item, modifier, value) triples whose modifier
ids LandSandBoat names. `server/fanxi_server/game/base_stats.py` carries the numeric per-level
grade tables behind the base attributes. Both are produced by `tools/import_lsb_item_data.py`
and `tools/gen_base_stats.py` from LandSandBoat's published tables and datasets, and both hold
numbers only: item ids, levels and values that come from the game itself. The schema, column
names, generator code and the code that reads them are Fanxi's own; no LandSandBoat source,
comments, Lua, or SQL statements are copied.

`data/weapon_skills.json` carries the factual per-skill combat numbers behind a weapon skill:
its three fTP anchors, stat-modifier fractions, hit count and "varies with TP" tables. It is
produced by `tools/import_lsb_weapon_skills.py` from LandSandBoat's published weapon-skill
scripts and the BG-Wiki Prime weapon-skill pages. The file holds numbers only; the schema,
field names, importer and the code that reads it are Fanxi's own, and no LandSandBoat Lua or
comments are copied.

`database/migrations/0115_trusts.sql` carries the factual appearance and combat data behind
the 122 Trust alter egos: the client's 20-byte look block, model id, main/sub job, attack delay
and damage multiplier. It is produced by `tools/import_lsb_trusts.py` from LandSandBoat's
`mob_pools` table (rows at `poolid = spellid + 5000`) and Fanxi's own spell names. The table
schema, importer and comments are Fanxi's own, and no LandSandBoat SQL text, comments or code is
copied.

The trust portrait atlas in `host/addons/trust_faces.c` is cropped from the BGWiki trust cards
(`bg-wiki.com/ffxi/BGWiki:Trusts`) and the skillchain element atlas in `host/addons/sc_icons.c`
from the BGWiki skillchain icons; the artwork is FINAL FANTASY XI game art and remains the
property of Square Enix. Both are bundled only to draw the local HUD buttons.

FINAL FANTASY XI and SQUARE ENIX are trademarks of Square Enix Holdings Co., Ltd. Fanxi is not
affiliated with or endorsed by Square Enix.
