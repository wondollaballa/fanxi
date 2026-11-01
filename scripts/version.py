#!/usr/bin/env python3
"""One version, written in four places.

    scripts/version.py                    print the current version
    scripts/version.py set 0.3.0          write it everywhere
    scripts/version.py check v0.3.0       fail unless the tag matches (used by CI)
    scripts/version.py tag                print the tag for the current version

The launcher version lives in launcher-rs/package.json, launcher-rs/src-tauri/tauri.conf.json,
the [package] table of launcher-rs/src-tauri/Cargo.toml and the launcher's entry in Cargo.lock.
Tauri reads tauri.conf.json, npm and the tag read package.json, and Cargo reads the other two; a
release tagged vX.Y.Z whose tauri.conf.json still says Y is how a release gets built with the
wrong number on it.  `set` keeps them together, `check` refuses to build when they drifted.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "launcher-rs" / "package.json"
TAURI = ROOT / "launcher-rs" / "src-tauri" / "tauri.conf.json"
CARGO = ROOT / "launcher-rs" / "src-tauri" / "Cargo.toml"
LOCK = ROOT / "launcher-rs" / "src-tauri" / "Cargo.lock"

# Cargo's version for this crate, but not the futures-* crates that share the prefix.
CRATE = "fanxi-launcher"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class Drift(Exception):
    """The version strings disagree, or a file no longer looks the way this script expects."""


def read_json_version(path: pathlib.Path) -> str:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    version = document.get("version")
    if not isinstance(version, str):
        raise Drift(f"{path} has no top-level version")
    return version


def write_json_version(path: pathlib.Path, version: str) -> None:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    document["version"] = version
    with path.open("w", encoding="utf-8") as handle:
        # ensure_ascii keeps the existing \u2014 escapes, so a bump is a one-line diff.
        json.dump(document, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def read_cargo_version(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'(?m)^\[package\]\s*$(.*?)(?=^\[|\Z)', text, re.S)
    if not match:
        raise Drift(f"{path} has no [package] table")
    version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', match.group(1))
    if not version:
        raise Drift(f"{path} has no version in [package]")
    return version.group(1)


def write_cargo_version(path: pathlib.Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'(?m)^\[package\]\s*$(.*?)(?=^\[|\Z)', text, re.S)
    if not match:
        raise Drift(f"{path} has no [package] table")
    section, count = re.subn(
        r'(?m)^(version\s*=\s*)"[^"]+"',
        lambda m: f'{m.group(1)}"{version}"',
        match.group(1),
        count=1,
    )
    if count != 1:
        raise Drift(f"{path} has no version in [package]")
    path.write_text(text[: match.start(1)] + section + text[match.end(1) :], encoding="utf-8")


def read_lock_version(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(?m)^\[\[package\]\]\s*$\s*^name = "' + re.escape(CRATE) + r'"\s*$\s*^version = "([^"]+)"',
        re.M,
    )
    match = pattern.search(text)
    if not match:
        raise Drift(f"{path} has no {CRATE} package")
    return match.group(1)


def write_lock_version(path: pathlib.Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(?m)^(\[\[package\]\]\s*$\s*^name = "' + re.escape(CRATE) + r'"\s*$\s*^version = ")[^"]+"',
        re.M,
    )
    updated, count = pattern.subn(lambda m: m.group(1) + version + '"', text)
    if count != 1:
        raise Drift(f"{path} has {count} {CRATE} packages, expected one")
    path.write_text(updated, encoding="utf-8")


def locations() -> list[tuple[pathlib.Path, callable, callable]]:
    return [
        (PACKAGE, read_json_version, write_json_version),
        (TAURI, read_json_version, write_json_version),
        (CARGO, read_cargo_version, write_cargo_version),
        (LOCK, read_lock_version, write_lock_version),
    ]


def versions() -> dict[pathlib.Path, str]:
    found = {}
    for path, read, _ in locations():
        if not path.is_file():
            raise Drift(f"{path} is missing")
        found[path] = read(path)
    return found


def current() -> str:
    found = versions()
    unique = set(found.values())
    if len(unique) != 1:
        detail = "\n".join(f"  {path.relative_to(ROOT)}: {version}" for path, version in found.items())
        raise Drift("the version strings disagree:\n" + detail + "\nRun scripts/version.py set X.Y.Z.")
    return unique.pop()


def check(tag: str) -> None:
    version = current()
    expected = tag[1:] if tag.startswith("v") else tag
    if expected != version:
        raise Drift(f"tag {tag} does not match the launcher version {version}")
    print(f"tag {tag} matches the launcher version {version}")


def set_version(version: str) -> None:
    if not SEMVER.match(version):
        raise Drift(f"{version} is not a version like 1.2.3 (or 1.2.3-rc.1)")
    for path, _, write in locations():
        write(path, version)
        print(f"{path.relative_to(ROOT)}: {version}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command")

    setter = commands.add_parser("set", help="write the version into every file")
    setter.add_argument("version", help="1.2.3, or 1.2.3-rc.1")

    checker = commands.add_parser("check", help="fail unless a tag matches the version")
    checker.add_argument("tag", help="v1.2.3 or 1.2.3")

    commands.add_parser("tag", help="print v<version>")
    commands.add_parser("show", help="print the version (the default)")

    args = parser.parse_args(argv)
    try:
        if args.command == "set":
            set_version(args.version)
        elif args.command == "check":
            check(args.tag)
        elif args.command == "tag":
            print(f"v{current()}")
        else:
            print(current())
    except Drift as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
