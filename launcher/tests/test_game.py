"""Finding a game folder, finding host64 and building its command line."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401

from fanxi_launcher.config import LauncherConfig
from fanxi_launcher.game import (
    GameManager,
    build_launch_command,
    find_game_dir,
    find_host64,
    is_game_dir,
    _humanize,
)


def fake_game(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "FFXiMain.dll").write_bytes(b"MZ fake")
    (folder / "FFXi.dll").write_bytes(b"MZ fake")
    (folder / "ROM").mkdir(exist_ok=True)
    return folder


class GameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"FANXI_LAUNCHER_DIR": str(self.root / "launcher")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_is_game_dir(self):
        folder = fake_game(self.root / "FINAL FANTASY XI")
        self.assertTrue(is_game_dir(folder))
        self.assertFalse(is_game_dir(self.root / "empty"))
        (folder / "FFXi.dll").unlink()
        self.assertFalse(is_game_dir(folder))

    def test_find_configured_game(self):
        folder = fake_game(self.root / "custom" / "FINAL FANTASY XI")
        self.assertEqual(find_game_dir(str(folder)), folder)

    def test_launch_command(self):
        client = {"server": "127.0.0.1", "auth_port": 54231, "data_port": 54230,
                  "view_port": 54001, "username": "tester"}
        command = build_launch_command("/tmp/host64", "/games/ffxi", client, "token123")
        self.assertEqual(command, [
            "/tmp/host64", "--game", "/games/ffxi", "--server", "127.0.0.1", "--user", "tester",
            "--login-token", "token123", "--authport", "54231", "--dataport", "54230",
            "--viewport", "54001",
        ])
        self.assertEqual(command[-2:], ["--viewport", "54001"])

    def test_find_host64_from_config(self):
        host64 = self.root / "host64"
        host64.write_text("#!/bin/sh\n")
        host64.chmod(0o755)
        config = LauncherConfig(host64=str(host64))
        self.assertEqual(find_host64(config), host64)
        self.assertFalse(GameManager(config).build_needed())

    def test_build_needed(self):
        config = LauncherConfig(host64=str(self.root / "missing"))
        with mock.patch("fanxi_launcher.game.find_host64", return_value=None):
            self.assertTrue(GameManager(config).build_needed())

    def test_humanize_progress(self):
        self.assertEqual(_humanize("@phase compile"), "— compile —")
        self.assertEqual(_humanize("@progress 5 10"), "  50%  (5/10)")
        self.assertEqual(_humanize("cc something"), "cc something")

    def test_log_tail_missing(self):
        manager = GameManager(LauncherConfig())
        self.assertEqual(manager.log_tail(3), "")


if __name__ == "__main__":
    unittest.main()
