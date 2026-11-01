# Releases

A Fanxi release is a GitHub Release on a `vX.Y.Z` tag. That tag versions the **launcher**; the
server has its own version ([below](#the-server)). Pushing the tag builds the launcher on macOS and
Linux, attaches the bundles to a **draft** release, and stops. You read the draft, write the notes,
and publish.

```sh
scripts/version.py set 0.3.0
git commit -am "release 0.3.0"
git tag v0.3.0
git push origin main v0.3.0
```

[`.github/workflows/release.yml`](../.github/workflows/release.yml) does the rest.

## What a release may contain

Fanxi is MIT-licensed and public; FINAL FANTASY XI is not. The repository's own rule is that
nothing derived from Square Enix binaries is ever committed (`.gitignore`, and the last paragraph
of the [README](../README.md#license-and-legal)): the launcher reads your `FFXiMain.dll`,
`FFXi.dll` and `ROM` at build time and never redistributes them. A release is bound by the same
rule.

| Ship it | Never ship it |
| --- | --- |
| `Fanxi-Launcher-*.dmg`, `.AppImage`, `.deb` | any `*.DAT`, `VTABLE.DAT`, `FTABLE.DAT`, `ROM*` |
| the bundled `gearswap/` job libraries | `FFXiMain.dll`, `FFXi.dll` |
| the auto-generated source archive | `host64` / `host64-headless` / `Fanxi.app` |
| `SHA256SUMS.txt` | `generated/` (the unpacked and translated Square Enix code) |

The last row surprises people, so it is worth being precise: `host64` is not a clean-room client.
`tools/build_posix.py` translates the player's own DLLs into C and links them into `host64`, so the
binary embeds Square Enix's code. That makes it a derivative work, in the same bucket as the DATs,
and the reason the build has to happen on the player's machine.

There is a technical ceiling as well. GitHub caps a release asset at **2 GiB**, and a patched retail
tree is ~14 GB across ~49k files ([retail-data.md](retail-data.md)), so "one file with the game in
it" is not a thing GitHub Releases can host even if the licence allowed it. Uploading it split into
seven parts does not change the licence, and using Releases as a CDN for content unrelated to the
repository is against GitHub's terms.

## Cutting a release

1. **Pick the version.** `scripts/version.py` writes it to `launcher-rs/package.json`,
   `launcher-rs/src-tauri/tauri.conf.json`, `launcher-rs/src-tauri/Cargo.toml` and `Cargo.lock`,
   and `check` refuses a tag that disagrees with them:

   ```sh
   scripts/version.py                  # 0.2.0
   scripts/version.py set 0.3.0        # 0.3.0 everywhere
   scripts/version.py check v0.3.0     # what CI runs, before it spends a runner
   ```

   Tags already used: `v0.1.0`, `v0.2.0`, `kit-linux`. Do not move a published tag; the release is
   keyed to it.

2. **Commit the bump and tag the commit**, not a later one:

   ```sh
   git commit -am "release 0.3.0"
   git tag -a v0.3.0 -m "Fanxi 0.3.0"
   git push origin main v0.3.0
   ```

3. **Watch the run** in the repository's Actions tab. The first build of a version takes ~10–15
   minutes; `Swatinem/rust-cache` keeps later ones near 5.

4. **Edit the draft.** The workflow generates commit notes and prepends a download table and the
   "you need your own FINAL FANTASY XI" section. Add the player-facing highlights — the
   `CHANGELOG.md` "Unreleased" entries are the raw material — then **Publish release**.

`workflow_dispatch` runs the same workflow against an existing tag, for a re-run after a flaky
runner or a fixed signing secret. It updates the draft it finds; delete the asset first if you need
to replace one.

If `publish` fails with `Resource not accessible by integration`, the repository is still on the
read-only default for `GITHUB_TOKEN`: **Settings → Actions → General → Workflow permissions →
Read and write permissions**. The workflow asks for `contents: write`, but the repository setting
can take it away.

## What the workflow builds

| Job | Runner | Produces |
| --- | --- | --- |
| `version` | ubuntu | fails unless the tag is the version in all four files |
| `build` | `macos-latest` | `Fanxi-Launcher-<v>-macos-universal.dmg` — one disk image, Apple silicon and Intel |
| `build` | `ubuntu-22.04` | `Fanxi-Launcher-<v>-linux-x86_64.AppImage` and `-linux-amd64.deb` |
| `build` | `windows-latest` | `Fanxi-Launcher-<v>-windows-x64-setup.exe` — the NSIS installer |
| `publish` | ubuntu | the draft release, the assets and `SHA256SUMS.txt` |

The macOS job builds `--target universal-apple-darwin`, which needs both Rust targets installed;
the Linux job runs on 22.04 on purpose, so the AppImage's glibc floor stays at 2.35 for Steam Deck
and older distributions.

Windows is the player platform, so the installer is the primary asset. The launcher builds the
client there with `tools/build.py` (MSVC, Direct3D 12) or [`tools/build_mingw.py`](../tools/build_mingw.py)
(llvm-mingw, no Visual Studio), and runs `tools/prepare.py` itself before either one. The player
flow is not finished: today a player still has to supply a compiler, SDL3 and Python. The
[player kit](onboarding.md) closes that gap — llvm-mingw, SDL3, Python and the sources in one
first-run download — and is the next milestone. Shipping `Fanxi.exe` prebuilt is not on the table
either way: like the DATs, it embeds Square Enix's translated code.

There is no Windows ARM64 asset and no `.msi`; NSIS covers 10 and 11 on x64.

## The server

The server is a separate program with a separate version. It is `server/fanxi_server/__init__.py`'s
`__version__` — `0.2.0` today, while the launcher's files say `0.1.0` — and nothing ties the two
together except the `/api/v1` HTTP contract the launcher speaks.

That is deliberate. A server operator updates `server/` and restarts; a player updates the launcher
and never touches the server. One can move a week ahead of the other, and usually will:

- the launcher calls `/status` and shows the server's version beside its own in the sidebar, so
  skew is visible in a screenshot;
- a new server endpoint is additive, so an old launcher keeps working;
- a launcher that needs a new endpoint fails visibly at request time, not at install time.

Releasing the server is therefore not a `tauri build` job. There is nothing to compile: Python 3.9+
standard library and SQLite, no packages to install. A server kit is a tarball of the tracked tree
— `server/`, `database/` (migrations and seed) and the JSON tables in `data/` — opened by the
operator and started with `python3 -m fanxi_server run`. Every command that opens the database
applies the pending migrations (`init`, `run`, `doctor`), so an old `data/fanxi.db` upgrades in
place.

What a server kit still cannot contain is the same thing the launcher cannot: the operator needs
their own `res/compress.dat` and zone meshes (`FANXI_GAME_DIR`) for the gateway to enter a zone.
Without them the HTTP API runs fine and nobody can play, which is exactly the failure `doctor`
reports.

The server already carries the data model for telling launchers about a new build: a `releases`
table (`channel`, `platform`, `version`, `url`, `sha256`, `size`, `notes`, `mandatory`), read at
`GET /api/v1/releases` and written at `POST /api/v1/admin/releases`. The launcher does not read it
yet, so it is a rollout channel with no consumer. When you want updates without a store, it is the
alternative to pointing the launcher at the GitHub API: the operator controls which channel their
server advertises and can mark a build `mandatory`, which a public release page cannot do.

## Code signing

Unsigned macOS downloads are the main support burden. On Apple silicon, Gatekeeper reports an
unsigned, unnotarized app as **damaged** rather than offering the usual "Open anyway".

- **No secrets configured** — the workflow signs ad hoc (`APPLE_SIGNING_IDENTITY=-`). The app runs,
  but the first launch needs Finder → right-click → **Open**, or
  `xattr -dr com.apple.quarantine "/Applications/Fanxi Launcher.app"`. Every download gets this
  warning, and it looks like a virus to a player.
- **With an Apple Developer ID** — add these repository secrets. The workflow imports the
  certificate, and Tauri notarizes the `.dmg` automatically when `APPLE_ID`, `APPLE_PASSWORD` and
  `APPLE_TEAM_ID` are also present:

  | Secret | Value |
  | --- | --- |
  | `APPLE_CERTIFICATE` | base64 of the exported `.p12`: `base64 -i cert.p12 \| pbcopy` |
  | `APPLE_CERTIFICATE_PASSWORD` | the `.p12` password |
  | `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Your Name (TEAMID)` |
  | `APPLE_ID` | the Apple ID that owns the certificate |
  | `APPLE_PASSWORD` | an app-specific password for that Apple ID |
  | `APPLE_TEAM_ID` | the ten-character team id |
  | `KEYCHAIN_PASSWORD` | any random string; the temporary keychain's password |

  Notarization adds a few minutes to the macOS job. It is the difference between a download that
  opens and one that gets emailed to you as "it says damaged".

Windows has the same problem in a different costume: an unsigned NSIS installer gets SmartScreen's
"Windows protected your PC" until the binary has enough reputation. The fix is an Authenticode
certificate and Tauri's `bundle.windows.certificateThumbprint` with a `timestampUrl`; an EV
certificate skips the reputation wait. Until then the release note has to say **More info → Run
anyway**, and players will still be nervous.

## The "one download" question

The honest answer is that Fanxi can be one download; FINAL FANTASY XI cannot be part of it. Three
shapes, in increasing order of convenience:

**A. Launcher-only release (what the workflow does today).** The release page hands out a `.dmg`,
an AppImage or a Windows `-setup.exe` with a checksum. On Windows the installer is the whole
install path: Start menu entry, uninstaller, WebView2. On macOS and Linux it is not yet one click —
`install.sh` predates the workflow and still builds the app from source, so a player who runs it
gets a fresh build rather than the asset. Pointing `install.sh` at the latest `.dmg`/`.AppImage` is
a small change to that script and the next step that makes the release the install path there. The
game still comes from Square Enix; the ~14 GB is the player's own either way.

**B. Bundle the build tools into the app (the real fix).** The only thing standing between a
downloaded `.app` and a playable client is the checkout: `tools/build_posix.py` plus the Python and
clang it drives. Ship the POSIX sources as part of the app (a few MB, all MIT), and on first run
the launcher copies them to `~/Library/Application Support/Fanxi/source` and builds there. That is
one download from you and one free client install from Square Enix — the same shape as every other
private server, and legal. It needs a small amount of Rust: unpack resources on first run, set
`repo_root` to the copy, keep the build in the writable folder (the build writes `generated/` and
`build/` under its root, so it cannot run inside the signed bundle), and surface a progress page
that already exists.

**C. A game-data download.** Not shippable from this repository. If you ever hold written
permission from Square Enix, host the archive on object storage (R2, B2, S3) behind a link, not in
GitHub Releases: 2 GiB per asset, a public repo, and a DMCA queue are the wrong tools for it.

## After publishing

- The **latest** release is whatever you publish last, so a hotfix published out of order hides the
  newer feature release — publish in version order, or mark the older one pre-release.
- Auto-update is not wired up yet. `tauri-plugin-updater` reads a `latest.json` published beside the
  bundles, and `tauri-action` can generate it; that needs a signing keypair and a settings toggle in
  the launcher. Until then, players re-run `install.sh` or download the new bundle.
- To withdraw a bad release: delete it (and the tag, if the tag itself is wrong) and cut a new
  patch version. Do not re-upload a fixed asset under the same version — players who already
  downloaded it keep the broken one, and the checksum manifest no longer describes the release.

## Checklist

- [ ] `scripts/version.py check v<version>` passes
- [ ] the tag is on the commit you mean to release (`git show v<version>`)
- [ ] the draft's download table names the files actually attached
- [ ] notes say what a player gets, not what changed internally
- [ ] "You need your own FINAL FANTASY XI" is still in the body
- [ ] macOS signing is either configured or the ad-hoc warning is in the notes
