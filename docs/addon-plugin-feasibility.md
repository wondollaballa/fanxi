# Addons and legacy plugins: feasibility

Status: research, 2026-10-23. This is the answer to: can Fanxi run Ashita and Windower
addons, manage them from the launcher, and also honour legacy native plugins the way their
users expect?

## Verdict

| Area | Feasibility | What it means |
|---|---|---|
| Ashita v4 Lua addons | **Green, already largely built** | The host runs them; the launcher needs a manager and profiles. |
| Windower Lua addons | **Green/yellow, already largely built** | Same host, a different API layer; more API edges and harness coverage to finish. |
| Launcher-managed addons | **Green** | One Add-ons page, per-character profiles, install/enable/logs, live toggles. |
| Legacy plugin *workflow* | **Yellow** | We can honour the names, settings, commands and profiles with a compatibility catalog. |
| Legacy plugin *binaries* | **Red for now** | Arbitrary 32-bit Ashita/Windower DLLs cannot run in a 64-bit recompiled client without an x86 runtime. |
| Binary plugin runtime | **Research only, not a near-term commitment** | 6-12+ months of risky work, platform-specific, and most of its value is covered by ports. |

The recommendation is to make **Lua addons first-class and launcher-managed now**, add a
**legacy plugin compatibility catalog** next, and treat **binary plugin compatibility as a
separate, gated research project** rather than a promise. That gives users the workflow they
know — install, enable per character, configure, load, unload, see errors — without betting the
client on an emulator.

## 1. What was measured

### Corpus smoke survey

Ran `tools/addon_survey.py` against the pinned upstream corpora on 2026-10-23:

| Corpus | Addons found | Loaded | Clean (loaded, no error, no unsupported hit, no fault) |
|---|---:|---:|---:|
| Ashita v4 (`AshitaXI/Ashita-v4beta` @ `4171c74`) | 81 | 81 | 77 |
| Windower (`Windower/Lua` @ `5a35aeff`) | 126 | 126 | 93 |

The four Ashita results that are not clean are pattern/pointer or harness issues, not missing
Lua APIs:

- `config` — its memory patterns do not resolve in the survey harness for the 2026-10-05 build;
- `ime` — the same, and the process exited on a native fault while loading;
- `nomad` — its pointer checks reject the harness's blank game state;
- `blusets` — one native fault in the harness.

The Windower failures are mostly the harness invoking commands without the arguments a real
player would supply (`player` nil, `command` nil), plus one `GearSwap` stack overflow and a few
genuine API gaps (`windower.execute`, the `setkey` console command, Windower plugin loading).
That is a **smoke result, not a compatibility percentage**: the survey does not log in a
character, run a real rotation, or replay a packet capture. The 2026-10-05 build used here also
lacks the `chat_add` wrap, so `text_in` paths were not exercised. The design document already
lists recorded-session replay as the missing piece; it is also the main thing needed before
publishing a compatibility list.

### Code and upstream audit

- The client already contains [`host/addons/`](../host/addons): a LuaJIT host, Ashita and
  Windower API layers, ImGui, text/primitives/textures, gdifonts, a D3D8 COM shim, Win32 shims,
  packet hooks, input hooks, resource readers, path mapping, crash isolation, a headless harness
  and the survey tool.
- The overlay is drawn after the game's frame and before Present
  ([`host/addons/gui.cpp`](../host/addons/gui.cpp), `xi_gui_begin`; `addons_frame` in
  [`core.c`](../host/addons/core.c)). It is a real in-process layer, and addons already use it.
- The plugin manager is a stub: Ashita's `IPluginManager` reports exactly one plugin, `Addons`
  ([`ashita_core.lua`](../host/addons/lua/ashita_core.lua)); Windower's `load`/`unload` say
  plugins are not supported ([`windower.lua`](../host/addons/lua/windower.lua)).
- The launcher has **no addon surface at all**. It starts a client with `FFXI_CONTROL` only
  ([`control.py`](../launcher/fanxi_launcher/control.py), [`game.rs`](../launcher-rs/src-tauri/src/game.rs));
  the only addon control today is the in-game **Config → Addons** page, backed by
  [`manage.c`](../host/addons/manage.c) and `addons.cfg`.
- Upstream research: Ashita v4 has a public C++ plugin SDK and a small official plugin set;
  Windower 4 still documents native plugins, but Windower 5 removed them in favour of Lua, and
  the Windower 4 core/plugin ABI is not public.

## 2. How the two ecosystems actually work

### Ashita v4

- **Layout:** `Ashita/addons/<name>/`, `Ashita/addons/libs/`, `Ashita/plugins/`,
  `Ashita/config/`, `Ashita/scripts/`.
- **Addons** are Lua, run by the native `Addons` plugin (`addons.dll`). Users load them with
  `/addon load <name>`; the plugin manages Lua states, settings and addon commands.
- **Plugins** are 32-bit Windows C++ DLLs loaded with `/load <name>` (and `/unload`, `/list`,
  `/unloadall`, `/plugins`). A plugin exports `expCreatePlugin`, `expDestroyPlugin` and
  `expGetInterfaceVersion`, and implements a C++ `IPlugin` vtable. It receives an `IAshitaCore*`
  with chat, packet, memory, resource, input, font, primitive, GUI and Direct3D managers, plus
  flags for the events it wants.
- Many plugins are small and useful; some — `hardwaremouse` is the clearest example — detour
  Win32 or game functions with Microsoft Detours. Others draw through the D3D8 device or patch
  game code.
- **Workflow users expect:** drop a folder into `plugins/` or `addons/`, choose it in a profile
  or `default.txt`, `/load` it, configure it, see it persist across characters, and get a clear
  error if it cannot load.

### Windower 4/5

- **Layout:** `Windower/addons/<name>/`, `Windower/addons/libs/`, `Windower/plugins/`,
  `Windower/res/`, `Windower/settings/`, `Windower/scripts/init.txt`.
- **Addons** are Lua, loaded with `//lua load <name>` / `//lua unload`, and the API is the
  `windower.*` one (`windower.ffxi`, `windower.packets`, `texts`, `images`, `prim`, `res`, …).
- **Plugins** are 32-bit DLLs loaded with `//load <name>`, `//unload`, `//toggle`,
  `//plugin_list`, `//reload`, `//unloadall`. The old Windower 4 "hook" that hosted them was
  closed-source; there is no public SDK.
- **Windower 5 removed native plugins.** Its own architecture notes say Lua is now powerful
  enough (FFI, memory, Win32) that C++ plugins are no longer needed. The open-source Fenestra
  core contains the Lua addon host but no native plugin subsystem.
- **Workflow users expect:** launcher profile chooses plugins/addons, `//lua` and `//load` work,
  settings live under `Windower/settings` or per-character folders, and `plugin_manager` can
  switch sets per character.

### What "work the same way" should mean

It helps to separate four promises:

1. **Same files and folder layout** — copy an addon in, it is discovered.
2. **Same commands and settings** — `/addon load`, `//lua load`, `/load`, aliases and binds,
   config paths, per-character files.
3. **Same lifecycle** — load before login, unload on exit, reload, enable/disable per character,
   errors visible.
4. **Same binary** — the original `.dll` runs untouched.

Fanxi can deliver 1–3 for Lua addons today with modest work. It can deliver 1–3 for many legacy
plugins through replacements/ports. It cannot deliver 4 for arbitrary plugins on the current
architecture.

## 3. What Fanxi already has, and the gaps

**Already built**

- LuaJIT host, one state per addon, Lua dialect patches, LuaSocket/lfs/ffi.
- Ashita v4 and Windower 4 API layers, path mapping, config/resource readers.
- Overlay: ImGui 1.92, text/primitives/textures, gdifonts, D3D8/D3DX and Win32 shims.
- Game hooks: command line, chat in/out, packets, key/mouse, Present.
- Crash guard, per-addon error reporting, profiling, headless harness.
- In-game Config → Addons and `addons.cfg`; setup fetches upstream addons/libraries.
- Launcher control port and per-client process management.

**Gaps that matter for "seamless"**

- No launcher Add-ons page, no per-character profiles, no install/update flow, no health view.
- `addons.cfg` is a flat global on/off list; the launcher cannot select a set before launch.
- No addon metadata (version, author, kind, load state) exposed to the launcher; only chat/log
  output.
- Command fidelity is partial and in places wrong for Ashita: `/load`, `/unload`, `/list` and
  `/unloadall` currently act on Lua addons, while Ashita uses them for plugins. `/addon` lacks
  `silent`, `info`, `link`, `kill`, `exec`; `/plugins` is missing. Windower plugin names are
  reported as unsupported, which is honest but not a workflow.
- No compatibility catalog or status badges; users cannot tell whether an addon is expected to
  work before installing it.
- The survey has no logged-in character or packet replay, so it under-reports real compatibility
  and over-reports command/player errors.

## 4. Native plugin binaries: why this is the hard part

The blocker is not the Ashita API surface, although that is large — the public SDK header has
36 interface structs and hundreds of virtual methods. The blocker is the execution model:

- **Architecture.** Plugins are 32-bit x86 PE DLLs. `host64` is a 64-bit ARM/x86-64 process. A
  64-bit process cannot `LoadLibrary` a 32-bit DLL, and macOS on Apple silicon has no 32-bit
  execution path. This is true on Windows too: a 64-bit client cannot load 32-bit plugins
  in-process.
- **C++ ABI.** Plugins are MSVC C++ objects with vtables, `thiscall`, static constructors,
  exceptions, RTTI and CRT state. Calling them from a 64-bit host is not a matter of adding a few
  `extern "C"` thunks; the objects, vtables and call frames have to live in a 32-bit address
  space with the right layout.
- **Win32 and Direct3D.** Plugins import kernel32/user32/d3d8/d3dx8/dinput/XInput/Detours and
  expect real handles, HWNDs, COM vtables and a device they can draw with. The host has shims for
  Lua's FFI, but that is a different contract from a native DLL's import table.
- **Game pointers.** The game is recompiled C, not x86 code running in place. A plugin that
  calls a game function through a raw pointer, installs a Detour, or patches a prologue expects
  the original bytes to execute. Fanxi has translated variants for a known patch list
  (XIUI, macrofix, etc. in [`meta/builds.json`](../meta/builds.json)), but that is a whitelist,
  not general dynamic code support.
- **Threads and lifetime.** Plugins create threads, hook window procedures, and own D3D
  resources. The Lua host deliberately confines addon code to the game thread and one guest
  lock; native plugins would need a broader threading and lifetime model.
- **Windower specifically.** The Windower 4 plugin ABI is closed and its plugin set is small and
  largely superseded; Windower 5 has no native plugins. Reverse-engineering it would be high
  risk for low value.

### Options, honestly

| Option | What users get | Effort | Risk | Recommendation |
|---|---|---|---|---|
| **A. Lua addons + launcher manager** | Ashita/Windower Lua addons, profiles, install, logs | **S/M** | Low | Do first |
| **B. Legacy plugin compatibility catalog** | Pick a plugin name, get a native feature/addon replacement, same commands/settings where possible | **M** | Low/medium | Do second |
| **C. Source-compatible plugin ports** | Open-source plugins recompiled/ported to a host-native plugin API; not the original DLL | **L** | Medium | Per plugin, on demand |
| **D. Static recompilation of plugin DLLs** | Original DLL translated like FFXiMain | **XL** | High | Only for a curated, simple plugin if proven |
| **E. 32-bit x86 runtime / emulator** | Arbitrary plugin binaries | **XL+** | Very high | Research gate, not roadmap |
| **F. Windows-only 32-bit client build** | Native plugin loading on Windows only | **L/XL** | High, splits platform | Not recommended |

Option D sounds closest to "work the same way", but it is not a general solution: translating a
DLL is only the start. The plugin's imports, CRT, exceptions, Detours and calls back into the
game still have to work, and a plugin that patches code at runtime defeats a static translation.
Option E is the only general answer, and it is effectively a small Wine/emulator project with a
performance and security cost that conflicts with Fanxi's native-client premise.

## 5. Recommended product: a compatibility catalog, not a binary promise

Treat addons and legacy plugins as two tiers in one launcher page:

### Tier 1 — Lua addons (Ashita, Windower, xi)

- Discovered from the three folders; kind auto-detected as today.
- Installed from a folder, a zip, or the pinned upstream corpus.
- Enabled globally and per character; loaded by the host at launch.
- Metadata, load state, errors and unsupported-API counts shown in the launcher.
- Commands follow each ecosystem's semantics.

### Tier 2 — Legacy plugins, through a catalog

Each known plugin gets a catalog entry:

```json
{
  "name": "Timers",
  "ecosystem": "windower",
  "kind": "plugin",
  "status": "replacement",
  "provides": "addon:recast",
  "command": "timers",
  "notes": "Recast addon provides the timer display; the Windower timers plugin is not loaded."
}
```

Statuses: `native` (none initially), `replacement` (an addon or host feature provides it),
`partial` (some features), `unsupported` (with a reason). Selecting a legacy plugin in the
launcher installs/enables its replacement and keeps the familiar name and command working via an
alias. This is how we can "honour" plugins without pretending to run their DLLs.

Start with the official sets, which are finite and mostly replaceable:

- **Ashita:** `addons` (already replaced by the host), `screenshot`, `hardwaremouse`,
  `thirdparty`, `minimap`, `toon`, `winefix`; POL plugins are launcher/login features.
- **Windower:** AutoExec, Binder, ChatMon, Config, DelayMeNot, FFXIDB, FishingCrashFix,
  Guildwork, IME, InfoBar, Run, Sandbox, SSOrganizer, Tickle, Timers, WeatherMon, WinControl.
  Several already have Windower/Ashita Lua counterparts (`chatmon`, `infobar`, `tickle`,
  `recast`, `recast`-style timers, window control, screenshot organisation).

Then curate a top-20 third-party list from the Ashita/Windower plugin repositories, with a
compatibility note and an owner. Reimplementing a small plugin as a host feature is often cheaper
and safer than loading a binary: screenshot, hardware mouse, nameplate fixes, chat history,
draw distance/LoD/fog controls and timer overlays are all close to things the host already does.

### Launcher UX

Add **Add-ons** to the launcher sidebar (Rust launcher first; mirror in the Python launcher only
if it remains supported):

- Filter: All / Ashita / Windower / Fanxi / Legacy plugins.
- Row: enable checkbox, name, kind badge, version, source, status
  (Ready / Needs setup / Partial / Unsupported), profile selector, "Details".
- **Profiles:** Global, plus one per character. Copy/duplicate, "use for this character", and a
  "Safe mode" that disables everything.
- **Install:** "Add from folder", "Add from .zip", "Browse catalog"; never auto-run an addon
  from a URL without showing what it is. Fetch the pinned libraries once, as setup does now.
- **Health:** last launch's errors and `unsupported` counts, "disable the last addon that
  failed", link to `host64.log`, open the addon folder, open its config folder.
- **Launch summary:** before Play, show "12 addons will load for Onedough"; apply the profile at
  process start so addons are present before login.
- **In-game parity:** Config → Addons stays, but edits the active profile and shows its name;
  the launcher and the game write the same profile files.

### Host/API work

1. **Addon inventory API.** Expose name, kind, path, version/author if available, enabled,
   loaded, last error and unsupported count. Prefer a native `xi.addons` table over parsing chat;
   then the control addon can answer `addons` requests.
2. **Profiles.** `FANXI_ADDON_PROFILE=<character>` from the launcher selects
   `addons.<profile>.cfg`; no profile means the global `addons.cfg`. The host loads that file on
   the first frame and the Config page edits the active profile.
3. **Command fidelity.** Give each process a compatibility mode (`ashita`, `windower`, `mixed`):
   - Ashita mode: `/addon ...` for Lua, `/load`/`/unload`/`/list`/`/unloadall`/`/plugins ...` for
     plugins (catalog-backed), with the old plugin names as aliases.
   - Windower mode: `//lua ...` for Lua, `//load`/`//unload`/`//toggle`/`//plugin_list` for
     plugins.
   - Mixed mode: explicit `/addon` and `//lua`; `/load` resolves a catalog name, otherwise prints
     a clear "addons use /addon load" message. This avoids silently changing what `/load` means.
   Do not keep the current behaviour where `/load` loads a Lua addon: it is the one command both
   ecosystems agree means a native plugin.
4. **Catalog resolution.** Ship a small JSON catalog (name, ecosystem, status, replacement,
   command, notes). The host resolves `/load <legacy name>` to the replacement when one exists;
   otherwise it reports "not supported" once and points at the launcher. The launcher reads the
   same file.
5. **Health and safe mode.** Write a compact per-addon health record on exit (loaded, errors,
   unsupported, faults) next to the log; the launcher reads it. A crash loop disables the last
   addon automatically.
6. **Load order.** Ashita addons have no priority field, but libraries and `init.txt`/`default.txt`
   order matter. Respect config order and add an optional `load_after` in the catalog for
   replacements.

## 6. Roadmap

| Phase | Deliverable | Proof | Rough effort |
|---|---|---|---|
| 0 | Freeze the survey method; add a logged-in/replay fixture | Survey errors drop; a published baseline | 1-2 weeks |
| 1 | Launcher Add-ons page + inventory + install from folder/zip + logs | Install, enable, launch, see it load; disable and relaunch | 3-4 weeks |
| 2 | Profiles (`FANXI_ADDON_PROFILE`, per-character cfg) + control API | Two characters with different sets; toggles apply live | 2-3 weeks |
| 3 | Command fidelity + metadata + health/safe mode | Ashita `/load` and Windower `//load` semantics; no silent addon load | 2-3 weeks |
| 4 | Legacy plugin catalog for official Ashita/Windower sets | Every official plugin has a status; replacements load | 3-4 weeks |
| 5 | Top-20 third-party audit and ports | Compatibility table with statuses and known limits | 4-8 weeks, ongoing |
| 6 (optional) | Source-compatible plugin ports for a few demanded plugins | A ported plugin runs natively, not the DLL | 1-3 weeks each |
| R (optional) | Timeboxed binary-plugin spike (one simple DLL) | Go/no-go on a 32-bit runtime | 2-3 weeks, then stop |

Phases 1-3 are the actual "seamless" product. Phase 4 is how legacy plugin users get a familiar
experience without a binary runtime. Phase R should only start if user demand is strong enough to
justify a project measured in months.

## 7. Acceptance criteria

- A user can install an Ashita addon and a Windower addon from the launcher, see both in one
  list, enable them for one character, launch, and see them load.
- Two characters can have different addon sets without editing files by hand.
- `/addon load`, `//lua load`, `/load`, `/unload`, `/list` and `/unloadall` behave as their
  ecosystem documents; a legacy plugin name resolves to a replacement or a clear refusal.
- A failing addon is reported with its error; a crash is contained where the host guard can catch
  it, and the launcher offers to disable the addon before the next launch.
- The launcher reports what will load before launch and what did load after.
- The survey baseline is published and does not regress; a real-session replay replaces the
  current blank-state smoke test.

## 8. Risks and open decisions

**Risks**

- **Expectation risk:** users may read "legacy plugin support" as "my DLL runs". The launcher must
  say clearly which plugins are replacements and which are unsupported.
- **Security:** Lua addons have full FFI/memory access; a catalog and a trust prompt are not a
  sandbox. Do not auto-install arbitrary URLs.
- **Licensing:** Ashita's SDK/core carry GPL/LGPL terms and Windower's open-source core is MIT;
  keep fetching third-party code at install time, retain notices, and do not bundle plugin
  binaries without permission.
- **Upstream drift:** addon APIs and game builds change. Pin commits (already done) and keep the
  survey in CI.
- **Two launchers:** Python and Rust sharing `launcher.json`; addon UI should not diverge. Prefer
  one implementation with a shared profile/catalog format.
- **Platform:** a binary plugin story would be different on Windows; do not let it distort the
  macOS-native design.

**Open decisions**

1. Is the launcher target the Rust app, the Python app, or both? This affects UI effort, not the
   host API.
2. Which legacy plugins do actual users ask for? The catalog should be demand-led, not exhaustive.
3. Do we ship the full upstream addon corpus by default, or a curated list? Today setup fetches
   all of it; that is convenient but a large trust surface.
4. Is a source-compatible plugin SDK worth it, or are addon/host replacements enough?
5. What is the security policy for third-party addons (checksums, signed catalog, review)?

## Appendix: reproducing the survey

```bash
python3 tools/addons_fetch.py --data-dir /tmp/fanxi-addons --only ashita
python3 tools/addons_fetch.py --data-dir /tmp/fanxi-addons --only windower
python3 tools/addon_survey.py --kind ashita --data-dir /tmp/fanxi-addons \
    --game "/path/to/FINAL FANTASY XI" --markdown /tmp/ashita.md
python3 tools/addon_survey.py --kind windower --data-dir /tmp/fanxi-addons \
    --game "/path/to/FINAL FANTASY XI" --markdown /tmp/windower.md
```

The next improvement is a seeded character (player, party, inventory, target) or a recorded
packet replay; without it, command errors and `player` nil results dominate the Windower totals.
