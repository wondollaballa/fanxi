"""Launcher configuration: one JSON file, private to the player."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401

from fanxi_launcher.config import LauncherConfig, config_path, data_dir


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = mock.patch.dict(os.environ, {"FANXI_LAUNCHER_DIR": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_defaults(self):
        config = LauncherConfig.load()
        self.assertEqual(config.api_url, "http://127.0.0.1:8080")
        self.assertEqual(config.token, "")
        self.assertTrue(config.auto_login)

    def test_round_trip_and_permissions(self):
        config = LauncherConfig(api_url="http://fanxi.test:9000", token="abc", username="tester",
                                character_id=7, game_dir="/games/ffxi")
        config.save()
        loaded = LauncherConfig.load()
        self.assertEqual(loaded.api_url, "http://fanxi.test:9000")
        self.assertEqual(loaded.token, "abc")
        self.assertEqual(loaded.username, "tester")
        self.assertEqual(loaded.character_id, 7)
        self.assertEqual(loaded.game_dir, "/games/ffxi")
        mode = stat.S_IMODE(config_path().stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_bad_file_falls_back_to_defaults(self):
        config_path().parent.mkdir(parents=True, exist_ok=True)
        config_path().write_text("{not json", encoding="utf-8")
        config = LauncherConfig.load()
        self.assertEqual(config.api_url, "http://127.0.0.1:8080")

    def test_unknown_fields_are_ignored(self):
        config_path().parent.mkdir(parents=True, exist_ok=True)
        config_path().write_text(json.dumps({"api_url": "http://x", "future": 1}), encoding="utf-8")
        self.assertEqual(LauncherConfig.load().api_url, "http://x")

    def test_clear_session(self):
        config = LauncherConfig(token="abc", username="tester", character_id=1)
        config.clear_session()
        self.assertEqual(config.token, "")
        self.assertEqual(config.username, "")
        self.assertIsNone(config.character_id)

    def test_data_dir_override(self):
        self.assertEqual(data_dir(), Path(self.tmp.name).resolve())


if __name__ == "__main__":
    unittest.main()
