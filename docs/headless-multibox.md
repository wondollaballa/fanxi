# Headless multiboxing: six clients on one Mac

Research note, 2026-10-23. The machine this checkout runs on is an **M2 Max, 32 GB, macOS 15.6.1**,
not the M5 the request named. The conclusions hold for any Apple-silicon Mac, but do not read "M5"
as automatically more headroom: a base M5 has fewer GPU cores than this M2 Max, even though its CPU
is faster. Measure the GPU before assuming either way. Every number marked *measured* below comes
from this machine while one client was live.

## The short answer

- **The control half is already built.** Every client has a loopback JSON control port; the launcher
  can already command, key, follow, gear and inspect all of them. Headless needs no new control path.
- **"Headless" on macOS means no visible window, not no GUI session.** A hidden window that renders
  into its own back buffer, with the Metal layer created only while it is on screen, is the stable
  shape. Showing it later is a one-call screen swap with no streaming latency.
- **Do not leave a hidden or covered Metal layer presenting.** Core Animation stops vending
  drawables for an occluded layer; `nextDrawable` then blocks for about a second and returns nil, on
  every frame. That is the single macOS behaviour that decides this design.
- **The current build is x86_64 under Rosetta**, because `.venv` was made by an Intel Python and
  clang therefore targets x86_64. Rebuilding native arm64 is the first, free win.
- **Six boxes fit CPU-wise; memory and GPU are the limits** on a 32 GB machine. Run boxes at
  30 fps, 1280×720, `FFXI_FX=0`, and expect roughly 0.5 GB each.
- If the machine still struggles, the fallback is the **null renderer** (no GPU at all) for boxes
  that only follow and act, and a second machine for the rest.
- **Yes, video can be streamed from a headless box, but on one Mac you should not need to.** Showing
  the hidden window is the lowest-latency "swap screen". When boxes move to another machine, the
  right stream is IOSurface + VideoToolbox, not ScreenCaptureKit (see below).

### Build order

1. Native arm64 build (P0).
2. Hidden-at-rest launch, `window {show}` and `fps {divisor}`, panel Show/Hide (P1).
3. Measure six boxes before adding anything else (measurement plan below).
4. Thumbnails (P2), then a real stream only if boxes move off the Mac (P3).

## What the project already has

The multibox control panel is described in [control-panel.md](control-panel.md). The parts that
matter here:

| Piece | Where | What it gives us |
|---|---|---|
| One process per online character | launcher `control.rs`, `game.rs` | `host64` per account/sub, each with its own `FFXI_CONTROL` port (54300+) |
| Control protocol | `host/addons/lua/control.lua` | `state`, `metrics`, `command`, `keys`, `target`, `entities`, `capture`, `follow`, `gear`, `equip_set`, `phase`, `hud`, … |
| Key injection | `host/addons/lua/control.lua` (`keys`) | Actions reach the game's input queue without the window being focused |
| Screen capture | `capture` → `runtime/portable/d3d8.c` `capture_frame` | The next frame as an `XIF1` file (raw BGRA + 16-byte header), read from the back buffer |
| Sub-accounts | `server/fanxi_server/config.py` (`FANXI_MAX_SUBS`, default 5) | Server-owned boxes; main + five is the supported shape. Separate saved accounts are not capped this way |
| Frame control | `--fps-divisor`, `--fps-limit`, `FFXI_FPS_LIMIT` | 60 / 30 fps now; low uncapped rates only on builds with frame sites |
| A null renderer | `runtime/portable/gfx_null.c`, `host64-headless` on Windows | Game logic with no GPU at all |
| Offscreen Metal | `tests/gfx_test.c` (`gfx_init(NULL)`) | The Metal backend already renders with no window and no drawable |
| Panel | `launcher-rs/` (Tauri 2 + React) | Live party, commands, follow, gear, HUD, warps, Team page; subs are launched from Team |

Two pieces of the design are already exercised in-tree: **the control port works without input
focus** (the panel injects keys into the game's queue), and **the Metal backend renders with no
window** (`tests/gfx_test.c` calls `gfx_init(NULL)`). The missing piece is a launch mode that keeps
the window hidden and creates the layer only when asked.

## The measurement

One live client, `build/host64`, game build `2025-07-03` (16:9, 1280×720, 60 fps, Metal, modern
effects on):

| Metric | Value |
|---|---|
| CPU | 0.55–0.68 of one core (`ps %cpu` 54–68) |
| Memory | 528–546 MB RSS |
| Behaviour | steady in West Ronfaure with combat; no stalls |
| Server | 3.4 % of a core, 43 MB |
| Launcher | 0.1 % of a core, 92 MB |
| System | 29 GB used of 32 GB, 7.5 GB compressor, 1.7 GB unused |

Two conclusions: **CPU is not the problem** (six at 30 fps should be under two cores even under
Rosetta), and **memory is** on this machine as it is currently loaded. The client is also running
under Rosetta: `file build/host64` says `x86_64`, `oahd` is running, and:

```text
.venv/bin/python -c 'import platform; print(platform.machine())'   -> x86_64
.venv/bin/python -c 'import subprocess; print(subprocess.check_output(["clang","-dumpmachine"]))'
                                                                   -> x86_64-apple-darwin24.6.0
clang -dumpmachine                                                 -> arm64-apple-darwin24.6.0
```

The launcher creates `.venv` with `python3` from `PATH` (`system_python()` in
`launcher-rs/src-tauri/src/game.rs`), and this shell's `python3` is Anaconda's x86_64 build. Clang
inherits the architecture of the process that starts it, so the whole client is built x86_64.
Rosetta is also on its way out: macOS 27 is the last release with full Rosetta support
([Apple, Sept 2026](https://developer.apple.com/news/?id=w5ngl9k2)), so the native build is not
optional long-term.

**Step zero:** remove `.venv`, rebuild with `/usr/bin/python3` (universal, arm64) or
`/opt/homebrew/bin/python3`, and confirm `file build/host64` says `arm64`. `tools/setup.py` already
prefers `/usr/bin/python3` when it creates the environment; the launcher does not. Rosetta 2 measured
78–79 % of native on Geekbench 5 on an M1
([MacRumors](https://www.macrumors.com/2020/11/15/m1-chip-emulating-x86-benchmark/)), so expect a
real CPU drop here too; measure it rather than assuming a figure.

## What “headless” can mean

| Mode | Visible window | Metal layer | GPU cost | Screen swap | Control | Notes |
|---|---|---|---|---|---|---|
| A. Visible windows (today) | 6 | 6 | full | click / Cmd-Tab | yes | WindowServer composites all six and each holds a drawable pool |
| B. Hidden window, rendered | 0 | 0 at rest | medium | instant show | yes | **Recommended**; no layer until shown |
| C. Windowless offscreen | 0 | 0 | medium | stream only | yes | `gfx_init(NULL)`, needs a flag or `SDL_VIDEO_DRIVER=dummy` for the game's window |
| D. Null renderer | 0 | 0 | none | none (data only) | yes | Cheapest; no pixels, `capture` fails |

Mode B is the one that satisfies both halves of the request: no visible windows, and a screen you
can bring up when you want it.

### What is actually missing in the code

Three gaps, all in the launch/visibility path rather than the game:

1. **A launch mode that keeps the window hidden and does not create the Metal layer.** Nothing
   passes `FFXI_HEADLESS` today, and `gfx_init` always creates a view when it is given a window.
2. **A way to show a box on demand** and to put its frame rate back up while it is visible.
3. **A native arm64 build** (an environment fix, not a feature).

The control protocol, key injection, follow, gear, HUD, capture, sub-accounts, launch tokens and
the panel's polling all exist and work without a visible window.

### What not to do

- **Do not run six clients in one process.** The recompiled client is a Windows-style process with
  global state (one D3D8 device, one Win32 window, one 4 GB guest address space); multiplexing game
  sessions would be a different project. One process per box is the model, and six processes are
  cheap.
- **Do not keep six Metal layers alive behind hidden windows.** That is the case that stalls for a
  second per frame once a window has been shown and covered.
- **Do not use fullscreen for boxes.** A macOS fullscreen window gets its own Space; showing and
  hiding it is slow and disruptive. Windowed 1280×720, or borderless at most.
- **Do not use ScreenCaptureKit for the hidden boxes.** It needs TCC and returns blank frames for
  non-composited Metal content.
- **Do not put macOS VMs on a 32 GB Mac** to avoid one process per box. Virtualization.framework
  caps a Mac at **two macOS guests** (a third fails with `VZErrorDomain Code 6`, and Parallels/UTM
  inherit the same limit), and the guest GPU is a **paravirtual** device, not passthrough: no Metal 3,
  a reduced feature set, and 3D applications are reported as unreliable. More here than the
  hypervisor cost alone.

Also prevent display sleep while boxes are running (`caffeinate -d` or `pmset noidle`); App Nap
prevention does not keep the display awake, and a sleeping display is fine for rendering but a
sleeping *system* is not.


## The macOS behaviour that decides the design

`CAMetalLayer.nextDrawable()` waits for a drawable; `allowsNextDrawableTimeout` defaults to true,
so it returns nil after about a second. For a window that is **covered or minimized**, Core
Animation stops vending drawables: presented frames never complete, the pool (typically three)
exhausts, and `nextDrawable` blocks for about a second on every frame. Godot measured
1.009–1.056 s on macOS 26.6.2 / M1 Max, sampled in `CAMetalLayerPrivateNextDrawableLocked`
([godot#124667](https://github.com/godotengine/godot/issues/124667)). wgpu-hal documents the same
and checks `-[NSWindow occlusionState]` before acquiring
([wgpu surface.rs](https://github.com/gfx-rs/wgpu/blob/trunk/wgpu-hal/src/metal/surface.rs)); the
Ship of Harkinian engine hit it with SDL3 + Metal and now skips rendering while
`SDL_WINDOW_OCCLUDED` ([libultraship#1260](https://github.com/Kenix3/libultraship/pull/1260)).
`sokol` stops its display link and stops calling `nextDrawable` when obscured
([sokol#1446](https://github.com/floooh/sokol/issues/1446)). A closed translation layer can hang
present permanently, not just for a second (Apple forum thread, title only:
[852816](https://developer.apple.com/forums/thread/852816)).

The nuance that makes a hidden window usable: **before the window has ever been visible,
`nextDrawable` returns immediately**; the stall begins only after the window has been shown and then
hidden or covered. That is undocumented behaviour and not something to design around.

The design that avoids the question entirely is to **not have a layer while the box is hidden**.
This backend already renders the scene into its own back-buffer texture (`bb`) and uses the layer
only to blit that texture to the screen (`gfx_present` in `runtime/portable/gfx_metal.m`). Keep
`bb`, skip the layer, and the game keeps running exactly as it does today. This is also what
`tests/gfx_test.c` exercises with `gfx_init(NULL)`: offscreen rendering, no window, no drawable.

Two more macOS facts to handle:

- **App Nap.** A process with no visible window that has not updated visible content is exactly
  what App Nap throttles; a hidden game loop can be deprioritised and its timers coalesced. Opt out
  for the life of the process with `ProcessInfo.beginActivity(options: .userInitiated /
  .latencyCritical, reason:)` (documented:
  [beginActivity](https://developer.apple.com/documentation/foundation/processinfo/beginactivity(options:reason:)),
  [App Nap](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/power_efficiency_guidelines_osx/AppNap.html)).
  `NSAppSleepDisabled` is widely cited but not in current Apple documentation; prefer
  `beginActivity`. For a belt-and-braces setup also use `caffeinate -dimsu` or the per-app Get Info
  "Prevent App Nap" checkbox, and watch Activity Monitor's Energy tab for "App Nap".
- **Session.** Anything that creates an `NSWindow`/`CAMetalLayer` needs an Aqua session; a
  LaunchAgent with `LimitLoadToSessionType = Aqua` is the supported way to start boxes at login
  ([TN2083](https://developer.apple.com/library/archive/technotes/tn2083/_index.html),
  [LSUIElement](https://developer.apple.com/documentation/bundleresources/information-property-list/lsuielement)).
  A Mac with no display is fine as long as a user is logged in; a box driven over SSH with nobody
  logged in is not a supported Metal path.

## Recommended shape: hidden at rest, layer on demand

1. **At launch** (`FFXI_HEADLESS=1`): create the game window hidden and **do not create the Metal
   view/layer**. `gfx_init` records the window and the device but leaves `g_layer` nil, so
   `gfx_present` submits the frame (`flush_pass`, `frame_end`) and skips the blit. No
   `nextDrawable`, no drawable pool, no stall, no compositor cost.
2. **While hidden** the game renders at its capped rate (30 fps for boxes), the control port works,
   and `capture` still works because `capture_frame` runs before `gfx_present` and reads `bb`
   (`runtime/portable/d3d8.c`, `IDirect3DDevice8_Present`).
3. **Show a box** (`window {show: true}`): create the Metal view/layer on the hidden window, set
   `device`, `pixelFormat`, `drawableSize`, then `SDL_ShowWindow`/`SDL_RaiseWindow`. The next frame
   blits the current `bb`; this is the screen swap, with no encoder and no network.
4. **Hide it** (`window {show: false}`): wait for the GPU (`gfx_finish`), destroy the view/layer,
   hide the window, and put the frame cap back to 30. Destroying the layer is what guarantees the
   occluded-drawable bug cannot happen at rest.
5. **Safety net:** while a shown window is occluded (the panel is in front of it), skip
   `nextDrawable` when `SDL_GetWindowFlags` reports `SDL_WINDOW_HIDDEN`, `SDL_WINDOW_MINIMIZED` or
   `SDL_WINDOW_OCCLUDED`; render into `bb` and present on the first frame after it is visible again.
6. **Frame cap:** `--fps-divisor 2` (30 fps) for boxes and `1` (60) for the shown one. Low uncapped
   rates such as 15 fps need `--fps-divisor 0` plus `FFXI_FPS_LIMIT=15`, which only works on builds
   with frame sites (`2025-11-12` and `2026-09-03` in `meta/builds.json`); the installed
   `2025-07-03` build has none, and 15 fps there may slow the world rather than only the renderer.
7. **Memory and GPU:** 1280×720, `FFXI_FX=0`, windowed (never fullscreen), and on the current
   machine close other applications or use a 64 GB machine. The measured client is 0.53 GB; allow
   up to 1 GB each for headroom, so six boxes are 3–6 GB before macOS.

Audio is not needed on a box nobody is listening to: `SDL_AUDIO_DRIVER=dummy` keeps six clients
from opening six output devices and takes the mixer out of each frame.

This changes only the present path and the window lifecycle; the game, the control addon and the
panel remain as they are.

## Showing and swapping screens

On one Mac there is no reason to stream: **show the hidden window**. The game window appears with
the latest back buffer, the panel stays behind it, and switching back is Cmd-Tab or a Hide button.
Latency is one frame plus the compositor, and there is no TCC prompt, encoder, decoder or socket.

The panel work is small, but there is one gap beyond headless itself: **there is no "launch party"
yet**. `launch_all` walks the saved accounts; sub-account boxes are launched one at a time from the
Team page (`launch_sub`). For six-box play the panel should:

- have a **Launch party** button that launches the main character and every active sub in sequence,
  reusing `launch_sub` and the existing 700 ms spacing `launch_all` already uses;
- show one **box grid** (main + subs) instead of an account roster, with per-box status, Show/Hide,
  follow, and the existing command/gear/HUD selection;
- keep the **Headless** switch per box and a `headless` badge in the live party;
- send `window {show}` / `fps {divisor}` through `control.lua`, backed by two host calls
  (`gfx_window_show`; `xi_fps_request` exists for addons and needs a small Lua binding);
- on Show, raise the frame cap to 60; on Hide, drop it back to 30.

This is the same "window placement/focus per client" already listed under **Next steps** in
[control-panel.md](control-panel.md).

## Seeing a box: show the window, or stream it

For boxes on another machine, or for a grid of live thumbnails, the options in order of fit:

| # | Path | Latency (same Mac) | Cost | Verdict |
|---|---|---|---|---|
| 1 | **Native window show/hide** | ~1 frame | tiny | Best on one Mac, though it is a window rather than a panel tile |
| 2 | **`capture` → panel thumbnail** | 100–500 ms | tiny | Already in-tree: `capture` writes `XIF1`, Rust decodes and scales. 1 fps per tile is plenty |
| 3 | **IOSurface → panel's own Metal view** | ~1 frame | medium | No encoder, no TCC; needs a native view in the Tauri window and mach-port sharing |
| 4 | **IOSurface → VideoToolbox → WebCodecs** | ~2–3 frames (35–50 ms) | medium–high | The right remote/headless answer; hardware encode/decode on both ends |
| 5 | **ScreenCaptureKit** | 2–4 frames + TCC | medium | Wrong tool here: blank frames for non-composited Metal content, monthly re-auth |
| 6 | **WebRTC** | 50–150 ms typical | high | NAT traversal is useless on localhost; only worth it across machines |

The building blocks for 3–4 are documented: `makeTexture(descriptor:iosurface:plane:)`,
`CVPixelBufferCreateWithIOSurface`, `IOSurfaceCreateMachPort` / `IOSurfaceLookupFromMachPort`, and
VideoToolbox's low-latency rate control
([`kVTVideoEncoderSpecification_EnableLowLatencyRateControl`](https://developer.apple.com/documentation/videotoolbox/kvtvideoencoderspecification_enablelowlatencyratecontrol),
[WWDC21 low-latency VideoToolbox](https://developer.apple.com/videos/play/wwdc2021/10158/)).
WebCodecs has shipped since Safari 16.4 ([WebKit](https://webkit.org/blog/13966/webcodecs-comes-to-safari-16-4/)).

ScreenCaptureKit is the one to avoid: it needs Screen Recording permission, and a window that is
not composited can deliver **black frames while still reporting `.complete`**
([SO 79949880](https://stackoverflow.com/questions/79949880)). A virtual display is worse: it is a
display, not a renderer; you still create a window on it, and it uses private API
([DeskPad](https://github.com/Stengo/DeskPad), [BetterDisplay FAQ](https://betterdisplay.pro/guide/faq/general/mac-app-store/)).

## If one Mac is not enough

- **A second Mac (a Mac mini is enough) is the only realistic scale-out.** Two to three clients per
  machine, native build, one Moonlight/Sunshine stream for the box you want to see (10–30 ms on a
  wired LAN). A stream shows one desktop: to look at a different box on that Mac, hide the first and
  show the second there, then the same stream follows. The panel stays local; the remote machine only
  runs `host64`.
- **Remote launch does not exist yet.** The launcher starts local `host64` only, and the control
  ports are loopback-only. A second machine needs a small launch agent on it (the same `host64`
  command line), a tunnel for `127.0.0.1:54300+` (SSH `-L` or a VPN), and a way for the panel to
  address instances by host. Do not expose those ports to the LAN: they are unauthenticated.
- **macOS VMs are not the answer.** Virtualization.framework allows two macOS guests and gives them
  a paravirtual GPU, not passthrough: reports show a reduced Metal feature set (no Metal 3) and a
  small share of the host's working set, and the Tart maintainers' own conclusion is that decent
  Metal performance in a guest is not something to count on
  ([Apple VZMacGraphicsDeviceConfiguration](https://developer.apple.com/documentation/virtualization/vzmacgraphicsdeviceconfiguration),
  [tart#1032](https://github.com/openai/tart/issues/1032)). A third macOS VM refuses to start
  ([macosvm#14](https://github.com/s-u/macosvm/issues/14)); Parallels documents the same two-VM
  limit ([KB 128867](https://kb.parallels.com/en/128867)). Apple's macOS 27 license also caps it at
  two guests ([SLA](https://www.apple.com/legal/sla/docs/macOS27.pdf)). Six guests is neither
  technically nor contractually available.
- **Linux/ARM is not a shortcut.** The macOS client is Metal/AppKit; Linux has no Metal. The
  project does have a Vulkan renderer used on Linux x86-64, but no supported Linux ARM build, and
  Asahi does not support the M5 yet ([Asahi M5](https://asahilinux.org/docs/platform/feature-support/m5/)).
- **A Windows PC** is only an option if you are prepared to use the Windows build of the client
  (`tools/build.py`); the documented end-user client is the macOS one.

Community practice for FFXI multiboxing independently arrives at the same frame-rate split: main at
60 fps, alts at 30 fps, smaller windows, shadows and weather off
([FFXIAH 54610](https://www.ffxiah.com/forum/topic/54610/fps-question-while-multiboxing/)). Windower
and Ashita have no supported headless mode; their clients need a window and a GPU context, and
minimized or covered windows are exactly when App Nap is eligible. Fanxi's backend is different in
one respect: it already renders the world into its own texture and treats the Metal layer as a final
blit, so a box can keep a hidden window and a Metal device while having **no drawable at all**. That
is the path this document proposes, and because no existing FFXI tool does it, it is the part that
needs the spike (P1) rather than a setting to switch on.

## Implementation plan

### P0 — native build (half a day)

1. `rm -rf .venv` and rebuild with `/usr/bin/python3` (or set `FANXI_PYTHON=/usr/bin/python3` for
   the launcher), e.g. `python3 tools/setup.py --game ~/Games/FFXI2026 --no-install`.
2. `file build/host64` must say `arm64`; `lipo -info` for confirmation.
3. Re-measure one client (CPU, RSS, frame time) as the new baseline.

### P1 — hidden-window mode (1–2 days)

| File | Change |
|---|---|
| `host/host64.c` | read `FFXI_HEADLESS`; pass it to the window/graphics setup; keep the App Nap activity token |
| `runtime/portable/user32.c` | in `show_window`, skip the SDL calls when headless but still set `w->visible` and send `WM_SHOWWINDOW`/`WM_ACTIVATEAPP`; `sh_IsWindowVisible` reads `w->visible`, not SDL's flags. A later show must not early-return just because `w->visible` is already 1: also test SDL's `SDL_WINDOW_HIDDEN` |
| `runtime/portable/gfx_metal.m` | do not create the view/layer when headless; add `gfx_window_show(int)`; skip `nextDrawable` while hidden/minimized/occluded; wait before destroying the layer; `beginActivity` |
| `runtime/portable/gfx.h`, `gfx_null.c` | declare/no-op the new window call |
| `host/addons/lua_xi.c`, `lua/control.lua` | `window {show}` and `fps {divisor}` commands |
| `launcher-rs/src-tauri/src/config.rs`, `game.rs`, `control.rs` | per-account `headless`, env/flags at spawn, `headless` in `InstanceView`, Show/Hide commands |
| `launcher-rs/src/components/ControlPage.tsx`, `TeamPage.tsx` | toggle, badge, Show/Hide, frame cap |

The control addon's tasks run on the game thread, which is the thread that owns the SDL window, so
`window`/`fps` do not need a dispatch to another queue. Keep the SDL and Metal view calls there.

Launch flags for a box: `--fps-divisor 2` (or `FFXI_FPS_LIMIT=15` on a frame-site build),
`--data-dir <data>/clients/<account>` and `--reg-overlay <data>/clients/<account>/saved.reg` (so one
box's settings and addon data do not overwrite another's), `FFXI_HEADLESS=1`, `FFXI_FX=0`,
`SDL_AUDIO_DRIVER=dummy`. `create_dir_all` the per-client folder before spawn; the game writes its
overlay on exit. A per-client data dir also moves the addon's `hud/<character>.json`; copy the
existing files over or keep the shared data dir for the main character, which is the one whose HUD
matters.

### P2 — thumbnails (half a day)

The panel calls `capture` into `<data>/frames/<port>.xif` once a second for the tiles it shows,
decodes the 16-byte header + BGRA rows in Rust, scales, and caches. No new C code; `capture` already
works offscreen. Add JPEG encoding only if the readback/file traffic matters.

### P3 — streaming (only if boxes move off the Mac)

IOSurface-backed back buffer → mach port → VideoToolbox low-latency H.264/HEVC → WebSocket →
WebCodecs in the panel, or a native `AVSampleBufferDisplayLayer`. This is the piece that makes a
remote box feel local; it is not needed for the one-Mac case.

## Measurement plan and acceptance

Run 1, 3 and 6 boxes, each at 60 / 30 fps (and 15 fps only on a frame-site build), at 1280×720 and
960×540, with `FFXI_FX` on and off:

- CPU: `ps -o %cpu,rss` sampled over 30 s; `top -l 5`.
- GPU: `sudo powermetrics --samplers gpu_power -i 1000` (the user can run this; it needs root).
- Frame time: `FFXI_PROFILE=1` in each box's log, which splits game code, API calls and present.
- Latency: timestamp a `command` round trip; a `window show` should present within one frame.
- Memory: watch `vm_stat` compressor growth over ten minutes; swap means six boxes do not fit.

Suggested acceptance for the six-box setup on a 32 GB M-series Mac: all six online at 30 fps with
no visible windows, CPU under 50 %, GPU under 70 %, compressor stable, `window show` under 200 ms,
and no `nextDrawable` stall in the logs after a show/hide/show cycle.

## Risks and open questions

- **Lazy layer creation is untested in this client.** `SDL_Metal_CreateView` on an existing hidden
  window should work, but the spike must show and hide a real box ten times and watch for stalls.
- **`IsWindowVisible` semantics.** If the game pauses or changes behaviour when its window is not
  visible, the headless shim must report it as visible while never ordering it in.
- **App Nap** may still throttle a hidden process; the `beginActivity` token must be held for the
  process lifetime, not just around a frame.
- **Memory** is the binding constraint on this 32 GB machine as it is currently loaded: six boxes
  plus other apps will swap. A 64 GB machine, or the null renderer for some boxes, is the fix.
- **GPU at six × 30 fps** is unmeasured. The 2025-07-03 build has no frame sites, so 15 fps is not
  a safe knob there; use 30 fps, or update the game build.
- **`gfx_null` is not a drop-in for the control addon's HUD:** ImGui textures are null, `capture`
  fails, and addon drawing is untested. It is the fallback for boxes that only follow and act.
- **Control ports are unauthenticated loopback ports.** That is fine on one Mac; a second machine
  needs a tunnel (SSH/VPN) or a token before the ports leave `127.0.0.1`.
- **The server supports five sub-accounts** (`FANXI_MAX_SUBS`), so main + five is six boxes if the
  boxes are server-owned subs. Six separate saved accounts also work and are not subject to that
  cap. More than six needs either a configuration change or more accounts, plus more headroom.

## Sources

- Project: [control-panel.md](control-panel.md), [launcher.md](launcher.md), [architecture.md](architecture.md),
  [options.md](options.md), `host/addons/lua/control.lua`, `runtime/portable/gfx_metal.m`,
  `runtime/portable/d3d8.c`, `tests/gfx_test.c`, `tools/build_posix.py`, `tools/build.py`.
- Metal drawables: [nextDrawable()](https://developer.apple.com/documentation/quartzcore/cametallayer/nextdrawable()),
  [allowsNextDrawableTimeout](https://developer.apple.com/documentation/quartzcore/cametallayer/allowsnextdrawabletimeout),
  [CAMetalLayer](https://developer.apple.com/documentation/quartzcore/cametallayer),
  [godot#124667](https://github.com/godotengine/godot/issues/124667),
  [wgpu surface.rs](https://github.com/gfx-rs/wgpu/blob/trunk/wgpu-hal/src/metal/surface.rs),
  [libultraship#1260](https://github.com/Kenix3/libultraship/pull/1260),
  [sokol#1446](https://github.com/floooh/sokol/issues/1446).
- Sessions and App Nap: [TN2083](https://developer.apple.com/library/archive/technotes/tn2083/_index.html),
  [beginActivity](https://developer.apple.com/documentation/foundation/processinfo/beginactivity(options:reason:)),
  [App Nap](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/power_efficiency_guidelines_osx/AppNap.html).
- Capture and encode: [ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit),
  [SO 79949880](https://stackoverflow.com/questions/79949880),
  [VideoToolbox low latency](https://developer.apple.com/documentation/videotoolbox/kvtvideoencoderspecification_enablelowlatencyratecontrol),
  [WebCodecs](https://www.w3.org/TR/webcodecs/),
  [WebKit 16.4](https://webkit.org/blog/13966/webcodecs-comes-to-safari-16-4/),
  [IOSurface](https://developer.apple.com/documentation/iosurface/iosurfacecreatemachport(_:)).
- Virtual displays (why not): [DeskPad](https://github.com/Stengo/DeskPad),
  [BetterDisplay FAQ](https://betterdisplay.pro/guide/faq/general/mac-app-store/).
- VMs and scale-out: [VZMacGraphicsDeviceConfiguration](https://developer.apple.com/documentation/virtualization/vzmacgraphicsdeviceconfiguration),
  [macosvm#14](https://github.com/s-u/macosvm/issues/14),
  [Parallels KB 128867](https://kb.parallels.com/en/128867),
  [macOS 27 SLA](https://www.apple.com/legal/sla/docs/macOS27.pdf),
  [tart#1032](https://github.com/openai/tart/issues/1032),
  [Asahi M5](https://asahilinux.org/docs/platform/feature-support/m5/),
  [Sunshine](https://docs.lizardbyte.dev/projects/sunshine/v0.23.1/about/advanced_usage.html).
- Rosetta sunset: [Apple developer news](https://developer.apple.com/news/?id=w5ngl9k2).
