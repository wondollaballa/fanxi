#!/usr/bin/env python3
"""Bundle the launcher for this machine.

  python3 launcher/build_app.py            # macOS: build/Fanxi Launcher.app
  python3 launcher/build_app.py --desktop  # Linux: a .desktop file in build/
  python3 launcher/build_app.py --check    # only report what would be built

The macOS bundle is a tiny shell stub around the Python package: no PyInstaller, no downloaded
runtime. It needs Python 3.9+ with tkinter (macOS's Command Line Tools provide both).
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launcher"
APP_NAME = "Fanxi Launcher"
BUNDLE_ID = "com.fanxi.launcher"
VERSION = "0.2.0"

STUB = """#!/bin/sh
# Fanxi Launcher: runs the Python package inside this bundle.
set -e
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$HERE/../Resources/app"
export PYTHONPATH="$APP${PYTHONPATH:+:$PYTHONPATH}"
export FANXI_REPO_ROOT="@SOURCE@"
exec /usr/bin/env python3 -m fanxi_launcher "$@"
"""


def build_macos() -> Path:
    bundle = ROOT / "build" / (APP_NAME + ".app")
    contents = bundle / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    if bundle.exists():
        shutil.rmtree(bundle)
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    shutil.copytree(LAUNCHER / "fanxi_launcher", resources / "app" / "fanxi_launcher",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    icon = ROOT / "assets" / "icon.icns"
    if icon.exists():
        shutil.copyfile(icon, resources / "icon.icns")
    stub = macos / APP_NAME
    stub.write_text(STUB.replace("@SOURCE@", str(ROOT)), encoding="utf-8")
    stub.chmod(0o755)
    info = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": "icon.icns",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": "1",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.role-playing-games",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Fanxi contributors",
    }
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump(info, f)
    if shutil.which("codesign"):
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)],
                       capture_output=True, check=False)
    return bundle


def build_desktop() -> Path:
    entry = ROOT / "build" / (APP_NAME + ".desktop")
    entry.parent.mkdir(parents=True, exist_ok=True)
    icon = ROOT / "assets" / "icon.png"
    command = ROOT / "launcher" / "fanxi-launcher"
    entry.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=%s\n"
        "Comment=Sign in and play FINAL FANTASY XI on Fanxi\n"
        'Exec="%s"\n'
        "Icon=%s\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        "StartupWMClass=fanxi\n" % (APP_NAME, command, icon),
        encoding="utf-8",
    )
    entry.chmod(0o755)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--desktop", action="store_true", help="build a Linux .desktop entry instead")
    parser.add_argument("--check", action="store_true", help="report paths and tool availability")
    args = parser.parse_args()
    if args.check:
        print("repository: %s" % ROOT)
        print("python:     %s" % sys.version.split()[0])
        try:
            import tkinter  # noqa: F401
            print("tkinter:    yes")
        except ImportError as exc:
            print("tkinter:    no (%s)" % exc)
        print("icon:       %s" % ((ROOT / "assets" / "icon.icns") if sys.platform == "darwin"
                                  else (ROOT / "assets" / "icon.png")))
        return 0
    if args.desktop:
        print("wrote %s" % build_desktop())
        return 0
    if sys.platform != "darwin":
        print("the .app bundle is for macOS; use --desktop for a Linux entry", file=sys.stderr)
        return 1
    print("wrote %s" % build_macos())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
