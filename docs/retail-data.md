# Retail client data

Fanxi boots from Square Enix's own client data: `VTABLE.DAT`, `FTABLE.DAT`, the `ROM*` folders and
the two programs the recompiler translates (`FFXiMain.dll`, `FFXi.dll`). None of it is in this
repository (see [LICENSE](../LICENSE)), and none of it can be rebuilt from the sources here.

## Where it comes from

Square Enix publishes the *client* for free — the Ultimate Collection installer, no login needed —
at <https://www.playonline.com/ff11us/download/media/install_win.html>. It ships no registration
code: a code, from the Square Enix Store, is still what entitles you to play on retail. Running
your own server does not change that; it changes who you connect to, not what you are licensed to
have.

The installer is a 2019 snapshot. The current data comes from patching that snapshot forward.

## Patching, and why it is not scripted here

`PlayOnline Check Files → FINAL FANTASY XI → Repair` compares an installed tree with the live patch
manifest and fetches only what differs. It is not a downloader: with no installation to compare
against, FINAL FANTASY XI does not even appear in its drop-down.

Getting it to run on a headless box has been tried and does not work, for one reason:

**PlayOnline's viewer needs a working graphics adapter.** Its own System Information panel reports
`Graphics Card:` blank and `Type of Chip: UnknownVideoChip` on a machine without one, and then:

| Environment | Result |
| --- | --- |
| Wine 9 or 11, 32-bit prefix, hand-built or official install | `pol.exe` page fault at `004137F1`, during teardown |
| Windows 10 22H2 in QEMU/KVM, no GPU | `pol.exe` fault in `d3d10warp.dll` at `0x2c1c41`, every launch |
| Windows 11 in QEMU/KVM, no GPU | `pol.exe` exits silently |

`polcfg.exe` (the configuration tool) runs fine in all of them — it is the viewer's render path
that fails. So the patch step belongs on a desktop with a real GPU: any Windows PC, or Wine and
CrossOver on macOS.

## Bringing the result here

Once the tree is patched somewhere else:

```sh
# copy it over and check it
scripts/fetch-retail.sh you@desktop:"/path/to/FINAL FANTASY XI" ~/ffxi-current

# and, if you kept the pre-patch copy, what the patch actually did
scripts/fetch-retail.sh you@desktop:"/path/to/FINAL FANTASY XI" ~/ffxi-current \
    --baseline ~/ffxi-2019
```

`rsync` resumes a cut transfer (`--partial`), so a dropped connection costs only the file in
flight. The folder defaults to `$FANXI_GAME_DIR` when that is set.

## Checking a tree

```sh
python3 tools/verify_install.py "<FINAL FANTASY XI folder>" [--baseline <folder>] [--json out.json]
```

It reads the tree and reports:

- the ROM sets and DAT count, `VTABLE.DAT` / `FTABLE.DAT` sizes, total bytes;
- the SHA-256 and PE timestamp of each program, and which build of `meta/builds.json` it is —
  `tools/prepare.py` picks a build by exactly that hash;
- with `--baseline`, how many files the patch left alone, added, removed or rewrote, with examples.

Exit codes: `0` complete and a build `meta/builds.json` knows; `3` complete but an unknown build;
`2` structurally incomplete.

A `3` is not a failure — it means the live client moved ahead of this checkout. Bring the build in:

```sh
python3 tools/newbuild.py identify --game "<FINAL FANTASY XI folder>"
```

That hashes the programs, reads the client version from `patch.ver`, and says whether each program
is a known build or a byte-identical `.text` of one whose metadata then carries over
([newbuild.py](../tools/newbuild.py)); `carry` maps the addresses a build needs onto the new image.

## What it costs

A patched tree is ~14 GB (49k DATs) for the 2019 snapshot, and grows with each expansion. The
verifier's structural pass hashes only the two programs and stats the ROM files, so it finishes in
under a second; `--baseline` hashes both trees in full and takes a minute or two on a fast disk.
