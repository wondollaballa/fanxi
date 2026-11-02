#!/usr/bin/env python3
"""tools/fanxi_tui.py's deploy: the migration step it reports and verifies.

The SSH calls are scripted, so no server is needed; two cases run the real remote probe against a
temporary checkout.

  python3 tests/fanxi_tui_test.py [-v]
"""
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_tui():
    spec = importlib.util.spec_from_file_location("fanxi_tui", ROOT / "tools" / "fanxi_tui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TUI = load_tui()
CONFIG = {"host": "root@example", "remote_dir": "/srv/fanxi", "key": "", "url": "https://example"}


def state(*pending, total=4):
    return {
        "ok": True,
        "total": total,
        "applied": total - len(pending),
        "pending": [{"version": int(name.split("_", 1)[0]), "name": name} for name in pending],
        "error": "",
    }


class FakeServer:
    """Answers the dashboard's ssh scripts, recording what ran and in what order."""

    def __init__(self, previous, after, states):
        self.previous = previous
        self.after = after
        self.states = list(states)
        self.head_reads = 0
        self.restarts = 0
        self.scripts = []
        self.health = '{"status":"ok","version":"0.2.91"}'

    def __call__(self, config, script, timeout=90):
        self.scripts.append(script)
        if "rev-parse HEAD" in script:
            self.head_reads += 1
            value = self.previous if self.head_reads == 1 else self.after
            return 0, value + "\n"
        if "db-backup.sh" in script:
            return 0, "/srv/fanxi/data/backups/fanxi-20260101-000000.db\n"
        if "pull --ff-only" in script:
            return 0, "Already up to date.\n"
        if "MIGRATIONS=" in script:
            current = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return 0, "MIGRATIONS=" + json.dumps(current) + "\n"
        if "systemctl restart fanxi" in script:
            self.restarts += 1
            return 0, ""
        if "/api/v1/health" in script:
            return 0, self.health
        return 0, ""


class DeployTest(unittest.TestCase):
    def deploy(self, server):
        lines = []
        with mock.patch.object(TUI, "run_remote", server), \
                mock.patch.object(TUI.time, "sleep", lambda seconds: None):
            ok, previous = TUI.deploy(CONFIG, lines.append)
        return ok, previous, "\n".join(lines)

    def test_a_new_commit_applies_its_new_migrations(self):
        server = FakeServer("a" * 40, "b" * 40,
                            [state("0176_limbus_weapon_models.sql"), state()])
        ok, previous, output = self.deploy(server)
        self.assertTrue(ok, output)
        self.assertEqual(previous, "a" * 40)
        self.assertEqual(server.restarts, 1)
        self.assertIn("0176_limbus_weapon_models.sql", output)
        self.assertIn("applied 1 migration: 0176_limbus_weapon_models.sql", output)

    def test_the_same_commit_still_runs_a_pending_migration(self):
        server = FakeServer("a" * 40, "a" * 40,
                            [state("0176_limbus_weapon_models.sql"), state()])
        ok, _, output = self.deploy(server)
        self.assertTrue(ok, output)
        self.assertEqual(server.restarts, 1)
        self.assertIn("no new commit", output)

    def test_nothing_new_does_not_restart_the_service(self):
        server = FakeServer("a" * 40, "a" * 40, [state()])
        ok, _, output = self.deploy(server)
        self.assertTrue(ok, output)
        self.assertEqual(server.restarts, 0)
        self.assertIn("nothing to deploy", output)

    def test_health_does_not_hide_an_unapplied_migration(self):
        pending = state("0176_limbus_weapon_models.sql")
        server = FakeServer("a" * 40, "b" * 40, [pending, pending])
        ok, _, output = self.deploy(server)
        self.assertFalse(ok, output)
        self.assertEqual(server.restarts, 1)
        self.assertIn("a migration was not applied", output)
        self.assertIn("0176_limbus_weapon_models.sql", output)

    def test_an_unhealthy_service_reports_the_migration_state(self):
        server = FakeServer("a" * 40, "b" * 40, [state(), state()])
        server.health = ""
        ok, _, output = self.deploy(server)
        self.assertFalse(ok, output)
        self.assertIn("all 4 migrations applied", output)
        self.assertIn("health check did not come back", output)


class MigrationProbeTest(unittest.TestCase):
    """The block deploy sends to the server, run against a throwaway checkout."""

    def test_it_lists_only_the_versions_the_database_has_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            migrations = root / "database" / "migrations"
            migrations.mkdir(parents=True)
            for name in ("0001_initial.sql", "0002_world_content.sql", "not_a_migration.sql"):
                (migrations / name).write_text("")
            (root / "data").mkdir()
            connection = sqlite3.connect(root / "data" / "fanxi.db")
            connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO schema_migrations (version) VALUES (1)")
            connection.commit()
            connection.close()

            done = subprocess.run(
                ["bash", "-c", TUI.MIGRATION_SCRIPT], cwd=root,
                text=True, capture_output=True, check=True,
            )
            line = next(line for line in done.stdout.splitlines()
                        if line.startswith("MIGRATIONS="))
            self.assertEqual(
                json.loads(line.split("=", 1)[1]),
                {"total": 2, "applied": 1, "pending": [
                    {"version": 2, "name": "0002_world_content.sql"}], "error": ""},
            )

    def test_a_missing_database_makes_every_migration_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "database" / "migrations").mkdir(parents=True)
            (root / "database" / "migrations" / "0001_initial.sql").write_text("")
            done = subprocess.run(
                ["bash", "-c", TUI.MIGRATION_SCRIPT], cwd=root,
                text=True, capture_output=True, check=True,
            )
            line = next(line for line in done.stdout.splitlines()
                        if line.startswith("MIGRATIONS="))
            values = json.loads(line.split("=", 1)[1])
            self.assertEqual(values["total"], 1)
            self.assertEqual(values["pending"][0]["name"], "0001_initial.sql")
            self.assertEqual(values["error"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
