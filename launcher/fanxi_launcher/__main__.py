"""Entry point: ``python3 -m fanxi_launcher``."""
from __future__ import annotations

import argparse
import sys

from . import APP_NAME, __version__
from .api import FanxiApi
from .config import LauncherConfig, config_path, data_dir
from .game import find_game_dir, find_host64


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fanxi-launcher", description=APP_NAME)
    parser.add_argument("--version", action="version", version="%s %s" % (APP_NAME, __version__))
    parser.add_argument("--api", help="Fanxi server URL (saved for next time)")
    parser.add_argument("--game", help="FINAL FANTASY XI folder (saved for next time)")
    parser.add_argument("--check", action="store_true", help="print paths and server health, then stop")
    parser.add_argument("--sign-out", action="store_true", help="forget the saved session and stop")
    args = parser.parse_args(argv)

    config = LauncherConfig.load()
    if args.api:
        config.api_url = args.api.rstrip("/")
    if args.game:
        config.game_dir = args.game
    if args.api or args.game:
        config.save()

    if args.sign_out:
        config.clear_session()
        config.save()
        print("signed out")
        return 0

    if args.check:
        print("%s %s" % (APP_NAME, __version__))
        print("settings:  %s" % config_path())
        print("data:      %s" % data_dir())
        game = find_game_dir(config.game_dir)
        print("game:      %s" % (game or "not found"))
        host64 = find_host64(config)
        print("host64:    %s" % (host64 or "not built"))
        print("server:    %s" % config.api_url)
        try:
            health = FanxiApi(config.api_url).health()
            print("health:    ok, %s %s" % (health.get("name", "Fanxi"), health.get("version", "")))
        except Exception as exc:
            print("health:    %s" % exc)
        return 0

    try:
        from .app import run
    except ImportError as exc:
        print("Fanxi needs tkinter: %s" % exc, file=sys.stderr)
        return 1
    try:
        return run(config)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
