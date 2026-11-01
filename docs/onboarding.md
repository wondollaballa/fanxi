# Getting a player from download to Play

The player supplies the FINAL FANTASY XI files; Fanxi supplies everything else. The only piece in
between is the client build — `host64` is translated from the player's own DLLs, so it cannot be
shipped and has to be produced on their machine. This is the plan that makes that invisible.

The pieces already exist. [`tools/build_mingw.py`](../tools/build_mingw.py) builds `Fanxi.exe` with
llvm-mingw and says in its own header why: *"a player's PC needs no Visual Studio: the launcher can
carry this toolchain (it may be redistributed; MSVC may not)."* Nothing new has to be invented; it
has to be packaged, downloaded, and driven by the launcher.

## The flow

**Windows — the player platform**

1. Download `Fanxi-Launcher-<v>-windows-x64-setup.exe` and run it. Start menu entry, uninstaller,
   WebView2. No Visual Studio, no Python, no SDL3.
2. First launch opens **Set up**:
   - it finds `C:\Program Files (x86)\PlayOnline\SquareEnix\FINAL FANTASY XI` on its own, or asks
     for the folder;
   - if the folder is missing, a short page: the client is free from Square Enix, and here is what
     a valid folder contains (`FFXiMain.dll`, `FFXi.dll`, `ROM\`, ~14 GB);
   - **Install tools** downloads the player kit (~235 MB, once) with a progress bar and a checksum;
   - **Build** runs prepare and the mingw compile (~5–10 minutes), streaming the log it already
     streams.
3. Play. Every later launch skips all of it.

**macOS**

Same flow, one extra gate: the compiler is Apple's clang, which lives in the Command Line Tools.
If `xcode-select -p` fails, the page offers one button that runs `xcode-select --install`; the rest
is identical. The FFXI folder is normally copied from a Windows machine (the same thing done by
hand today) — the page says exactly which folder and how big it is.

**Linux**

Same flow with the existing `kit-linux` artifact, plus the system clang or the kit's own compiler.

## What the player kit contains (Windows)

| Piece | Why | Size |
| --- | --- | --- |
| llvm-mingw `ucrt-x86_64` (clang, lld, llvm-windres, mingw headers and libs) | compiles and links `Fanxi.exe` without MSVC | 190 MB zip |
| SDL3 development package (headers, `SDL3.lib`, `SDL3.dll`) | `build_mingw.py` links it; zlib licence | ~2 MB |
| Python 3.12 embeddable + `capstone` and `pefile` wheels | `tools/prepare.py` and `recomp/` are Python | ~14 MB |
| prebuilt `libluajit.a` | removes `mingw32-make` from the kit | ~1 MB |
| Fanxi sources: `tools/`, `host/`, `runtime/`, `recomp/`, `third_party/{sdl3,luajit,lfs,luasocket,sqlite,imgui,stb,vma,volk}`, `meta/builds.json` | what the drivers read and compile | ~30 MB |

About **235 MB compressed, ~1.2 GB unpacked**, into `%APPDATA%\Fanxi\kit\`. The build writes
`generated/` and `build/` inside that folder, which is why the kit is per-user and not inside the
signed app bundle.

Trimming is possible later: only the x86_64 target, clang and lld are needed, which should take the
compiler from 190 MB to roughly 60–80 MB. That is an optimisation, not a prerequisite.

## Launcher changes

1. **Kit manager** (new): download to a temp file, verify the `sha256` from a `kit.json` published
   with the release, unpack into the data folder, mark it ready. Resume across restarts; delete the
   archive after a successful unpack.
2. **Build driver**: on Windows use `tools/build_mingw.py host64 --out build` when the kit (or
   `LLVM_MINGW`) is present, `tools/build.py` when it is not. Pass `LLVM_MINGW` and `SDL3_DIR` into
   the child. `--out build` matters: `find_host64` looks in `build\Fanxi.exe`, and the driver's
   default is `build\mingw\`.
3. **Toolchain preflight**: replace the MSVC-only check with "llvm-mingw present, else MSVC present,
   else offer Install tools". On macOS, check `xcode-select -p` and offer the install button.
4. **Onboarding page**: game folder, tools, build — three states on one screen, with the existing
   build log reused.
5. **`repo_root`**: point at `<data>/kit` instead of a git checkout when the kit is installed. The
   existing `FANXI_*` overrides still win, so a developer checkout keeps working.

## Release and CI changes

- A `kit` job in the release workflow assembles `fanxi-kit-<v>-windows-x64.zip` and
  `fanxi-kit-<v>-linux-x86_64.tar.xz`, plus `kit.json` with `url`, `sha256`, `size` and `version`
  per platform. The launcher reads the manifest, never a hard-coded URL.
- A Windows CI job downloads llvm-mingw and compiles the runtime and the D3D12 back end. It cannot
  compile the translated game code — there are no game files in CI, and there never can be — but it
  proves the toolchain, the headers, SDL3 and the linker, which is most of the risk.
- The installer stays small (the app only). The kit is a first-run download, so a launcher update
  does not re-download a compiler.

## What is deliberately not in the kit

- **The FFXI files.** Square Enix's, and the player's own copy is the licence.
- **`Fanxi.exe`.** Translated from those files; shipping it is shipping Square Enix's code.
- **The game's DATs.** Same reason, and 14 GB does not fit a GitHub release anyway.

## Risks

| Risk | Why it matters | Check |
| --- | --- | --- |
| `build_mingw.py` has never been driven by the launcher | the whole plan rests on it | run it by hand on a clean Windows VM, no VS installed |
| LuaJIT's makefile needs `mingw32-make` | llvm-mingw may not ship one | prebuild `libluajit.a` in the kit job if it does not |
| embeddable Python + `capstone` wheel | pip is not in the embeddable build | unpack the wheel into `site-packages`; or freeze `prepare.py` and `recomp` with PyInstaller |
| SmartScreen on a 200 MB compiler download | players will not run it | sign the launcher; the kit comes from the release over HTTPS |
| first build takes 5–10 minutes | feels broken without feedback | the build log already streams; add a phase bar and "this happens once" |

## Order of work

1. **Prove it by hand on a clean Windows machine**: unpack llvm-mingw, SDL3 and Python, run
   `prepare.py` and `build_mingw.py`, launch the exe. Record every step — that list is the kit.
2. Turn that list into `tools/player_kit.py` and a release asset with `kit.json`.
3. Add the kit manager and the onboarding page to the launcher.
4. Wire the Windows build to `build_mingw.py` and keep MSVC as the developer fallback.
5. macOS polish: the Command Line Tools prompt, and a page that explains copying the game folder
   from a Windows PC.

Step 1 needs a Windows machine with the game files — a friend's PC is enough, and it is the only
step that cannot be done from this Mac.
