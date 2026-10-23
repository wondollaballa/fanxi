# Custom jobs: scope, the DAT boundary, and a delivery plan

Status: proposal · 2026-10-22

This note answers two questions together:

1. What does adding a new playable job (a 23rd job) actually require in Fanxi?
2. Should we leave the retail DAT system at the same time, to get full control?

The short answer to (2) is **decouple, don't delete**. Own the gameplay/content schema and the
loader boundary now; keep DAT as a read-only asset transport and overlay target. A full DAT
removal is a different, much larger product: an owned asset pipeline and eventually an owned
client. It is not a prerequisite for a job, and doing both at once would put the job behind an
unbounded rewrite.

## What is already ours

Most of a job is not DAT at all. The parts that decide what a job *does* are already in this
repository and already data-driven:

| Layer | Where | State |
|---|---|---|
| Job HP/MP/attributes | `server/fanxi_server/game/base_stats.py` | per-job grades, generated |
| Skill caps | `server/fanxi_server/game/skills.py` + `data/skills.json` | per-job ranks |
| Job abilities | `job_abilities` (migration `0074`) | ids, gates, recast, animation |
| Job traits | `server/fanxi_server/game/traits_data.py` | ids, gates, modifiers |
| Spells and weapon skills | `spells`, `weapon_skills` | full rows |
| Gear requirements | `items.jobs` 32-bit mask | one bit per job |
| Job change / levels | `0x0100`, `0x01B`, `zone.py` | 24-entry level array (job 0–23) |
| Character creation | HTTP API + launcher | job id 1–22 today |
| Combat, rewards, quests | `world.py`, `content.py`, SQLite | our code and rows |

The zone protocol already has room past the retail 22. `ZoneSession.dancer()` packs 24 job
levels (`job_lev2` is 0x18 bytes, job 0–23), `job_points()` fills the 24-slot JP table, and the
addon host's job level functions accept ids below `0x18`. **Job 23 is the last slot the current
`0x01B` layout can carry**; a 24th playable job would mean extending the client's arrays and
packet layout, which is a separate and much larger change. Master levels use `0x68 + job` and
also end exactly at job 23 inside the 0x80-byte packet.

### The retail tables already reserve job 23

Resolving the client's file ids through `VTABLE.DAT`/`FTABLE.DAT` (the way `host/addons/res.c`
does) shows the data model already has a slot past RUN:

- `jobs.names` (file id 55467): 32 entries. 1–22 are the retail jobs; **23 is `???`**; 24–31 are
  debug placeholders (`888`, `999`, `AAA` …). `jobs.names_abbr` (55468) mirrors it (`???` at 23).
- `jobpoints` (55694): jobs 1–22 are real; 23 and up are Japanese placeholders
  (`カテゴリー名` / `ヘルプ文`).
- `merits` (55686): jobs 1–22 are real; 23 and up are `MeripoName29` / `Meripo 29 help text.`

So job 23 is not an impossible id: it is the **reserved but unlocalized slot** in the retail
client's own tables. What is missing is content — a name, an icon, menu rows — not a container to
put it in. A small string-table overlay can replace `???` with the job's name; the rest is UI work.
The spike still has to confirm that nothing else claims id 23 (Monstrosity, a system job, or a
menu-only record); the placeholder rows are evidence that it is unused, not proof.
(The file ids are much more stable than the `ROM/<dir>/<file>.DAT` paths that resolve them, which
is exactly why the content pack should address files by id, not by path.)

## What DAT still owns

DAT is the client's asset and table container, not the server's source of truth:

| Thing | Used by | Fanxi today |
|---|---|---|
| Zone geometry, models, textures, animations, audio | client | read from the player's install |
| UI layouts, sprites and fonts | client menus, `host/datui.c`, `host/modern.c` | read from the player's install |
| Job names/abbreviations | client string tables; addon `res.c` table `jobs.names` (55467) | retail values |
| Item records, icons and job masks | client equip/inventory/menus | retail values |
| Ability/spell records and menu tables | client menus, `ROM/118/114.DAT` | retail values |
| File tables and gear model ids | client resource loader | retail values |
| Huffman table | zone protocol | `res/compress.dat` |

Only the last row touches the server. Everything else is the client's presentation layer.

## The escape hatches that already exist

This is why a DAT rewrite is not the next step. Fanxi already has four independent ways to put
new content in front of the retail client:

- **Whole-file DAT overlays** — `--dats <folder>` replaces files by their `ROM*`/`sound*` paths
  (`host/host64.c`, `vfs_add_overlay`). A small generated overlay is enough for a string table,
  an icon sheet or an enlarged menu DAT.
- **Texture packs** — `--textures`, keyed by the renderer's hash and size
  (`tools/make_texpack.py`, `runtime/portable/d3d8.c`). Recolors and high-resolution art need no
  DAT edit at all.
- **Runtime table patches** — `host/cexi.c` already extends item ids, gear model ids and
  spell/job-ability ids to 0xFFF for a custom-content server, with the patch sites found per
  build by `tools/cexi_sites.py` and recorded in `meta/builds.json`.
- **Runtime menu/UI injection** — `host/modern.c` adds pages to the game's own Config menu;
  `host/addons/hooks.c` rebuilds the ability menu's command list from `0x0AC`; the addon overlay
  can draw arbitrary UI. A custom job menu or job HUD can be built here without touching DAT.

The existing CatsEyeXI-style path is the proof: custom ids and abilities are supported by
*overlaying a few DATs plus patching the client's ceilings*, not by removing the DAT system.

## What a new job actually touches

| Area | Change | DAT work |
|---|---|---|
| Job id/level slot | server + client 24-slot arrays | none |
| Name/abbreviation | server maps, launcher maps; client table already has a `???` slot at 23 | small string overlay or runtime patch |
| Job icon | client menu icon sheet | small overlay, or custom overlay UI |
| Job-change menu | client Mog House menu has 22 rows | patch/DAT, or a Fanxi overlay that sends `0x0100` |
| Abilities/traits | `job_abilities`, `traits_data`, `0x0AC`/`0x0AB`/`0x1A5` | reuse an unused id below the retail ceiling first; ids past it need `--cexi full` and the enlarged menu DAT |
| Job points/merits labels | client tables have placeholder rows at 23 | tiny overlay if those menus show them |
| Skill caps/stats | `skills.py`, `base_stats.py` | none |
| Gear equip gate | `items.jobs`, client item record job mask | item record edit/overlay, or a runtime mask patch |
| Gear models | client gear file ids + FTABLE/VTABLE | DAT overlay for new models; reuse + recolor first |
| Animations | client DAT | reuse existing first; new anims are a later problem |
| Status/party display | `0x01B`, `0x0DF`, client job tables | runtime patch or overlay fallback |
| Character creation | API/launcher (and possibly client) | none |
| GearSwap libraries | launcher `JOB_NAMES`, `gearswap/<JOB>.lua` | none |
| Quests/AF/relic | server content | event text/UI only if using client events |

The hard part is the **client's hardcoded job tables and menus**, not the DAT container. Removing
DAT would not remove that work; it would add an asset-format rewrite on top of it.

## Options

| Option | Control | Effort | Risk | Verdict |
|---|---|---|---|---|
| A. Keep DAT, server-side content only | low for client visuals | low | job is blank/invisible in native UI | not enough alone |
| B. DAT overlays + runtime patches | medium–high | medium | per-build patch maintenance | **recommended for v1** |
| C. Content pack over DAT backends | high | medium–high | pipeline work, but one source of truth | **recommended target** |
| D. Remove DAT entirely | total | very high | reimplements asset loaders and assets; changes the product/legal model | defer; not part of the job |

B and C are not alternatives. Use B to ship the first job, and grow C so the next job, item, zone
or ability is authored once and compiled into both the server and the client overlay.

## Recommended architecture: a content pack over DAT

```
content/                         Fanxi-owned source of truth
  jobs/<job>.toml                id, name, abbr, grades, skill ranks
  abilities/<job>.toml           ids, gates, recast, animation id
  traits/<job>.toml              ids, gates, modifiers
  items/<set>.toml               ids, slots, job masks, model/texture refs
  art/manifest.json              icons, textures, meshes, source (ArtCraft exports)
        │
        ▼
tools/build_content.py
  ├─ database seed / migration   server reads the same ids
  ├─ build/content/dats/ROM/...  --dats overlay (strings, icons, menu tables)
  ├─ build/content/textures/...  texture packs (recolors, hi-res art)
  └─ build/content/client.json   job sites, id ranges, patch manifest
        │
        ▼
server (SQLite)  ◄── same ids ──►  host64 (runtime injection + overlay)
```

Rules that keep it honest:

1. **One id space.** The server, launcher, content pack and client patch manifest use the same
   ability/item/job ids. No silent remapping at a layer boundary.
2. **DAT is a backend, not the schema.** The host reads through one content source: retail DAT,
   overlay DAT, or a Fanxi pack. A subsystem can migrate to a native format later without
   changing the authored content.
3. **Patch by finder, not by address.** Every client edit gets a finder in `tools/` and a record
   in `meta/builds.json`, the way `cexi_sites.py` does. A new retail build is a re-run, not a
   rewrite.
4. **Reuse before author.** The first job reuses existing animations, ability effects and gear
   models. Unique art is added where it changes the fantasy, not as a gate on the job working.

## Delivery plan

### Phase 0 — Job 23 spike (prove the loop)

Goal: one playable custom job, one ability, one weapon, one zone, no new art pipeline.

- Pick a job fantasy that can reuse an existing animation set and weapon type.
- Server: add job 23 to `base_stats`, `skills`, `JOB_NAMES`; seed `character_jobs`,
  `job_abilities`, one trait and one weapon skill; allow 23 in the API and launcher.
- Client: `!job 23`, 24-slot `0x01B`, name/icon fallback, ability list, equip mask for one
  existing weapon.
- UI: a Fanxi job-change page (overlay) for v1; leave the retail Moogle menu alone.
- Art: one icon and one texture recolor, delivered as a texture pack.

Exit criteria: create a job-23 character, change job, zone, relog, equip the weapon, use the
ability, see it in the party/status UI, and switch back to a retail job with no regression.

### Phase 1 — Content pipeline

- Define `content/` schemas and `tools/build_content.py`.
- Generate migrations/seed and the DAT/texture overlay from the same source.
- Add a `job_sites` finder for the name/icon/menu/equip-mask sites, per client build.
- Make the launcher read the job list from the server/content pack.

Exit criteria: a second job is added by editing `content/` and running one build command, with no
new Python literals in the server or launcher.

### Phase 2 — Art pipeline

- ArtCraft for concept sheets, icons, UI motifs and texture sources.
- Texture packs for recolors and hi-res replacements.
- A model/retarget converter only for pieces that must be unique; until then, reuse and recolor.
- Keep generated source art in `content/`; never commit retail-derived assets.

Exit criteria: a full AF-style set (five pieces + weapon) authored and visible on job 23, with at
least one unique model.

### Phase 3 — Native UI (optional)

- Move the job-change/status presentation into the client's own menus if the overlay is not
  enough.
- Extend the menu DAT or patch the job table, whichever is cheaper and more stable per build.

### Phase 4 — DAT-free subsystems (only if they pay)

Replace a DAT subsystem only when it blocks content, portability or maintenance. Candidates, in
order: job/ability/string tables → item metadata → UI layouts → models/animations → zones/audio.
A full asset-pipeline replacement is a separate product decision, not a job milestone.

## Job 23 checklist

- [ ] Job identity, weapon type, role and one-sentence fantasy.
- [ ] Reused animation set and ability effect chosen.
- [ ] `base_stats` grades, HP/MP and skill ranks.
- [ ] `JOB_NAMES` / abbreviations in server, launcher and GearSwap defaults.
- [ ] `character_jobs` seed and job-change validation.
- [ ] One ability, one trait, one weapon skill.
- [ ] One existing weapon with the job-23 mask (server + client).
- [ ] 24-slot `0x01B`, `0x063`, `0x0AC`/`0x0AB`/`0x1A5` verified in the client.
- [ ] Name/icon fallback (overlay or small DAT overlay).
- [ ] Job-change entry point (overlay first).
- [ ] Relog, zone change and party display tested.
- [ ] Every client edit recorded as a finder in `tools/` and `meta/builds.json`.

## Risks and guardrails

- **Client build drift.** Patch sites are per build. A finder plus `meta/builds.json` is the
  guardrail; hardcoded addresses are not.
- **Client-side validation.** Equip job masks and menu bounds are enforced by the client, not
  just the server. Test the actual client, not only the server tests.
- **Profile caches.** `aix.dat` can keep an old command list; the host already rebuilds it from
  `0x0AC`, but a stale profile is a real failure mode.
- **UI assumptions.** The native job menu and status pages may assume 22 rows. An overlay is the
  safe v1; native UI is Phase 3.
- **Legal boundary.** DAT overlays are generated from the player's own install. Do not commit
  retail-derived assets or extracted DAT content. ArtCraft output must be original.
- **Scope creep.** The DAT rewrite is larger than the job. Keep it behind a separate decision.

## Decision

Adopt **B now, C as the target**. Reject **D** for this job. Revisit D only if Fanxi stops
requiring a retail install, at which point an owned asset pipeline becomes a product requirement
rather than an optimization.

## Open questions

1. What is the job's fantasy and mechanical hook?
2. Must it appear in the client's native menus for v1, or is a Fanxi overlay acceptable?
3. Which retail client builds must support it (the build matrix in `meta/builds.json`)?
4. Is party/other-player display required from day one?
5. Which art is generated (ArtCraft) versus hand-authored, and who owns the conversion step?
