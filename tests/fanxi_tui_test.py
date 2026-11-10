#!/usr/bin/env python3
"""tools/fanxi_tui.py: the deploy it reports and the local client rebuild it runs.

The SSH calls, the compiler and the venv are scripted or stubbed, so no server, game folder or
toolchain is needed; two cases run the real remote probe against a temporary checkout.

  python3 tests/fanxi_tui_test.py [-v]
"""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
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


class CharacterSearchTest(unittest.TestCase):
    """The search block: names are data, not SQL or shell."""

    def search(self, query, rows):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            connection = sqlite3.connect(root / "data" / "fanxi.db")
            connection.execute(
                "CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, main_job INTEGER, "
                "main_level INTEGER, account_id INTEGER)"
            )
            connection.execute("CREATE TABLE game_sessions (character_id INTEGER, expires_at TEXT)")
            connection.executemany("INSERT INTO characters VALUES (?, ?, ?, ?, ?)", rows)
            connection.execute(
                "INSERT INTO game_sessions VALUES (2, '2999-01-01T00:00:00.000Z')"
            )
            connection.commit()
            connection.close()
            script = TUI.CHARACTER_SEARCH_SCRIPT.replace("__QUERY__", json.dumps(query))
            done = subprocess.run(
                ["bash", "-c", script], cwd=root,
                text=True, capture_output=True, check=True,
            )
            line = next(line for line in done.stdout.splitlines()
                        if line.startswith("CHARACTERS="))
            return json.loads(line.split("=", 1)[1])

    def test_it_finds_every_partial_match_and_marks_a_session_row(self):
        values = self.search("dough", [
            (1, "Onedough", 5, 99, 1),
            (2, "Twodough", 10, 99, 3),
            (3, "Fivedough", 8, 99, 7),
        ])
        self.assertFalse(values["truncated"])
        self.assertEqual(values["error"], "")
        by_name = {row["name"]: row for row in values["characters"]}
        self.assertEqual(set(by_name), {"Onedough", "Twodough", "Fivedough"})
        self.assertEqual(by_name["Twodough"]["session"], 1)
        self.assertEqual(by_name["Onedough"]["session"], 0)

    def test_percent_and_underscore_are_literal_in_the_query(self):
        values = self.search("50%_", [
            (1, "Onedough", 5, 99, 1),
            (2, "Twodough", 10, 99, 3),
            (3, "50%_dough", 1, 1, 4),
        ])
        self.assertEqual([row["name"] for row in values["characters"]], ["50%_dough"])


class CloneCommandTest(unittest.TestCase):
    def test_it_uses_the_clone_tool_with_its_backup_and_apply_path(self):
        command = TUI.clone_command(CONFIG, "Onedough", "Two dough")
        self.assertIn("sudo -u fanxi -H python3 tools/clone_character.py", command)
        self.assertIn("--source=Onedough", command)
        self.assertIn("--target='Two dough'", command)
        self.assertIn("--force --apply", command)

    def test_search_parses_the_marker_and_reports_a_remote_error(self):
        def fake(config, script, timeout=90):
            self.assertIn("query = \"One'dough\"", script)
            return 0, 'CHARACTERS={"characters": [], "truncated": false, "error": "locked"}'

        with mock.patch.object(TUI, "run_remote", fake):
            state = TUI.search_characters(CONFIG, "One'dough")
        self.assertFalse(state["ok"])
        self.assertEqual(state["error"], "locked")
        self.assertEqual(state["characters"], [])


class CloneFlowTest(unittest.TestCase):
    def dashboard(self, answers):
        dashboard = TUI.Dashboard.__new__(TUI.Dashboard)
        dashboard.config = CONFIG
        dashboard.message = ""
        dashboard.lines = []
        dashboard.draw = lambda: None
        dashboard.say = lambda text: dashboard.lines.extend(str(text).splitlines())
        pending = list(answers)
        dashboard.prompt = lambda label, default="": pending.pop(0) if pending else ""
        dashboard.confirm = lambda action: True
        dashboard.choose = lambda title, options: 0
        return dashboard

    def matched(self, *characters):
        return {
            "ok": True,
            "error": "",
            "truncated": False,
            "characters": [
                {"id": index + 1, "name": name, "main_level": 99, "account_id": index + 1,
                 "session": 0}
                for index, name in enumerate(characters)
            ],
        }

    def test_one_match_clones_it_after_the_confirmation(self):
        dashboard = self.dashboard(["Onedough", "two"])
        commands = []

        def fake(config, script, timeout=90):
            commands.append(script)
            return 0, "copied Onedough -> Twodough\n"

        with mock.patch.object(TUI, "search_characters",
                               lambda config, query: self.matched("Twodough")), \
                mock.patch.object(TUI, "run_remote", fake):
            dashboard.do_clone()
        self.assertEqual(len(commands), 1)
        self.assertIn("--source=Onedough", commands[0])
        self.assertIn("--target=Twodough", commands[0])
        self.assertIn("clone_character.py", commands[0])
        self.assertEqual(dashboard.message, "clone ok — relog Twodough")
        self.assertTrue(any("copied Onedough -> Twodough" in line for line in dashboard.lines))

    def test_a_single_match_equal_to_the_source_is_refused(self):
        dashboard = self.dashboard(["Onedough", "one"])
        commands = []
        with mock.patch.object(TUI, "search_characters",
                               lambda config, query: self.matched("Onedough")), \
                mock.patch.object(TUI, "run_remote",
                                  lambda *args, **kwargs: commands.append(args) or (0, "")):
            dashboard.do_clone()
        self.assertEqual(commands, [])
        self.assertEqual(dashboard.message, "clone cancelled")
        self.assertTrue(any("same character" in line for line in dashboard.lines))

    def test_multiple_matches_use_the_chosen_row(self):
        dashboard = self.dashboard(["Onedough", "dough"])
        dashboard.choose = lambda title, options: 1
        commands = []

        def fake(config, script, timeout=90):
            commands.append(script)
            return 1, "error: no character named Twodough\n"

        with mock.patch.object(TUI, "search_characters",
                               lambda config, query: self.matched("Twodough", "Fivedough")), \
                mock.patch.object(TUI, "run_remote", fake):
            dashboard.do_clone()
        self.assertIn("--target=Fivedough", commands[0])
        self.assertEqual(dashboard.message, "CLONE FAILED — see the log")


def make_repo(root: Path, *, version="0.2.1", stamp_version=None, binary=True, stamp=True) -> Path:
    """A scratch checkout: only the files the dashboard's local checks look at."""
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "build_posix.py").write_text("")
    (root / "host").mkdir()
    (root / "runtime" / "portable").mkdir(parents=True)
    (root / "runtime.json").write_text(json.dumps({"version": version}))
    (root / "build").mkdir(exist_ok=True)
    if binary:
        (root / "build" / TUI.CLIENT_BIN).write_text("")
    if stamp:
        (root / "build" / "runtime.json").write_text(json.dumps({
            "format": "xi-runtime-stamp/1",
            "version": stamp_version or version,
            "commit": "0123456789abcdef",
            "build": "2026-10-05",
        }))
    return root


def make_game_dir(root: Path) -> Path:
    (root / "ROM").mkdir(parents=True)
    (root / "FFXiMain.dll").write_bytes(b"")
    (root / "FFXi.dll").write_bytes(b"")
    return root.resolve()  # candidates come back resolved (macOS /var -> /private/var)


class ClientStateTest(unittest.TestCase):
    """build/fanxi against the sources: the launcher's version rule plus a mtime hint."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_checkout_and_a_game_folder_are_recognised(self):
        repo = make_repo(self.root / "repo")
        self.assertTrue(TUI.is_repo(repo))
        self.assertFalse(TUI.is_repo(self.root / "elsewhere"))
        game = make_game_dir(self.root / "game")
        self.assertTrue(TUI.is_game_dir(game))
        (game / "ROM").rmdir()
        self.assertFalse(TUI.is_game_dir(game))

    def test_missing_binary_is_reported_as_not_built(self):
        repo = make_repo(self.root / "repo", binary=False)
        state = TUI.client_state(repo)
        self.assertFalse(state["exists"])
        self.assertTrue(state["stale"])
        self.assertEqual(state["reason"], "not built")
        self.assertEqual(TUI.client_summary(state), "not built")

    def test_a_fresh_build_is_current(self):
        repo = make_repo(self.root / "repo")
        state = TUI.client_state(repo)
        self.assertTrue(state["exists"])
        self.assertFalse(state["stale"], state)
        self.assertEqual(state["version"], "0.2.1")
        self.assertEqual(TUI.client_summary(state), "0.2.1 @ 0123456")
        self.assertEqual(TUI.client_badge(state), ("0.2.1 @0123456", 2))

    def test_a_changed_runtime_version_makes_the_client_stale(self):
        repo = make_repo(self.root / "repo", version="0.2.2", stamp_version="0.2.1")
        state = TUI.client_state(repo)
        self.assertTrue(state["stale"])
        self.assertEqual(state["reason"], "the version changed")
        self.assertIn("stale", TUI.client_summary(state))

    def test_a_missing_stamp_is_unverified(self):
        repo = make_repo(self.root / "repo", stamp=False)
        state = TUI.client_state(repo)
        self.assertTrue(state["stale"])
        self.assertEqual(state["reason"], "no build stamp")

    def test_newer_sources_make_the_client_stale(self):
        repo = make_repo(self.root / "repo")
        source = repo / "host" / "host64.c"
        source.write_text("/* changed */")
        later = (repo / "build" / TUI.CLIENT_BIN).stat().st_mtime + 60
        os.utime(source, (later, later))
        state = TUI.client_state(repo)
        self.assertTrue(state["stale"])
        self.assertEqual(state["reason"], "sources are newer")

    def test_embedded_addon_lua_counts_as_a_source(self):
        repo = make_repo(self.root / "repo")
        lua = repo / "host" / "addons" / "lua" / "control.lua"
        lua.parent.mkdir(parents=True)
        lua.write_text("-- changed")
        later = (repo / "build" / TUI.CLIENT_BIN).stat().st_mtime + 60
        os.utime(lua, (later, later))
        self.assertEqual(TUI.client_state(repo)["reason"], "sources are newer")

    def test_the_legacy_binary_is_still_found(self):
        repo = make_repo(self.root / "repo", binary=False)
        (repo / "build" / TUI.LEGACY_CLIENT_BIN).write_text("")
        self.assertTrue(TUI.client_state(repo)["exists"])

    def test_no_checkout_is_not_a_client(self):
        self.assertEqual(TUI.client_summary({}), "no checkout")
        self.assertEqual(TUI.client_badge({}), ("no checkout", 4))


class GameDirTest(unittest.TestCase):
    """Which game folder the rebuild would use, and where it came from."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.repo = make_repo(self.root / "repo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_needs_prepare_when_the_recorded_folder_differs(self):
        game = make_game_dir(self.root / "game")
        other = make_game_dir(self.root / "other")
        self.assertTrue(TUI.needs_prepare(self.repo, game))
        (self.repo / "generated").mkdir()
        (self.repo / "generated" / "build.json").write_text(
            json.dumps({"build": "2026-10-05", "game": str(game)})
        )
        self.assertFalse(TUI.needs_prepare(self.repo, game))
        self.assertTrue(TUI.needs_prepare(self.repo, other))
        self.assertEqual(TUI.stamped_game_dir(self.repo), str(game))

    def test_candidates_prefer_the_setting_then_the_launcher(self):
        game = make_game_dir(self.root / "game")
        other = make_game_dir(self.home / "Games" / "OTHER")
        made = make_game_dir(self.home / "Games" / "FFXI")
        rows = TUI.game_dir_candidates(
            {"game_dir": str(game)}, self.repo,
            launcher={"game_dir": str(other)}, home=self.home,
        )
        self.assertEqual(
            rows,
            [(game, "game_dir setting"), (other, "the launcher"), (made, "~/Games")],
        )

    def test_candidates_keep_one_entry_per_folder(self):
        game = make_game_dir(self.root / "game")
        rows = TUI.game_dir_candidates(
            {"game_dir": str(game)}, self.repo,
            launcher={"game_dir": str(game)}, home=self.home,
        )
        self.assertEqual(rows, [(game, "game_dir setting")])

    def test_a_folder_without_the_game_files_is_not_a_candidate(self):
        (self.home / "Games" / "EMPTY").mkdir(parents=True)
        self.assertEqual(
            TUI.game_dir_candidates({}, self.repo, launcher={}, home=self.home), []
        )


class BuildEnvironmentTest(unittest.TestCase):
    """The compiler target is pinned when the launch would build the wrong architecture."""

    def test_native_machine_is_reported(self):
        self.assertTrue(TUI.native_machine())

    @unittest.skipUnless(sys.platform == "darwin", "the Rosetta trap is macOS-only")
    def test_a_rosetta_launch_pins_the_compiler_target(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ("XI_CC", "XI_CXX"):
                os.environ.pop(key, None)
            with mock.patch.object(TUI, "running_translated", return_value=True), \
                    mock.patch.object(TUI, "native_machine", return_value="arm64"):
                env = TUI.build_environment("/venv/python", progress=True)
        self.assertEqual(env["XI_CC"], "clang -arch arm64")
        self.assertEqual(env["XI_CXX"], "clang++ -arch arm64")
        self.assertEqual(env["FFXI_PROGRESS"], "1")

    @unittest.skipUnless(sys.platform == "darwin", "the Rosetta trap is macOS-only")
    def test_a_native_launch_leaves_the_compiler_alone(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ("XI_CC", "XI_CXX"):
                os.environ.pop(key, None)
            with mock.patch.object(TUI, "running_translated", return_value=False), \
                    mock.patch.object(TUI, "python_machine", return_value="arm64"), \
                    mock.patch.object(TUI, "native_machine", return_value="arm64"):
                env = TUI.build_environment("/venv/python", progress=False)
        self.assertEqual(env, {})

    @unittest.skipUnless(sys.platform == "darwin", "the Rosetta trap is macOS-only")
    def test_an_explicit_compiler_wins(self):
        with mock.patch.dict(os.environ, {"XI_CC": "zig cc"}, clear=False):
            with mock.patch.object(TUI, "running_translated", return_value=True), \
                    mock.patch.object(TUI, "native_machine", return_value="arm64"):
                env = TUI.build_environment("/venv/python", progress=False)
        self.assertNotIn("XI_CC", env)


class RebuildFlowTest(unittest.TestCase):
    """The dashboard action: which folder it picks, and what it hands the build."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root / "repo")
        self.game = make_game_dir(self.root / "game")

    def tearDown(self):
        self.tmp.cleanup()

    def dashboard(self, typed=""):
        dashboard = TUI.Dashboard.__new__(TUI.Dashboard)
        dashboard.config = {"game_dir": "", "repo": ""}
        dashboard.message = ""
        dashboard.lines = []
        dashboard.building = False
        dashboard.last_progress = 0.0
        dashboard.draw = lambda: None
        dashboard.say = lambda text: dashboard.lines.extend(str(text).splitlines())
        dashboard.choose = lambda title, options: 0
        dashboard.prompt = lambda label, default="": typed
        dashboard.screen = types.SimpleNamespace(timeout=lambda seconds: None)
        return dashboard

    def run_action(self, dashboard, candidates, result=True):
        calls = {}

        def build(config, emit, **kwargs):
            calls.update(kwargs)
            return result

        with mock.patch.object(TUI, "resolve_repo", return_value=self.repo), \
                mock.patch.object(TUI, "game_dir_candidates", return_value=candidates), \
                mock.patch.object(TUI, "build_client", side_effect=build), \
                mock.patch.object(TUI, "save_config") as save:
            dashboard.do_rebuild()
        return calls, save

    def test_a_launcher_folder_is_used_without_asking(self):
        dashboard = self.dashboard()
        calls, save = self.run_action(dashboard, [(self.game, "the launcher")])
        self.assertEqual(calls["game"], self.game)
        self.assertTrue(calls["progress"])
        self.assertEqual(dashboard.message, "client rebuilt — restart clients to use it")
        save.assert_not_called()

    def test_a_hand_typed_folder_is_remembered(self):
        dashboard = self.dashboard(typed=str(self.game))
        calls, save = self.run_action(dashboard, [])
        self.assertEqual(calls["game"], self.game)
        save.assert_called_once()
        self.assertEqual(dashboard.config["game_dir"], str(self.game))

    def test_a_cancelled_prompt_builds_nothing(self):
        dashboard = self.dashboard(typed="")
        calls, _ = self.run_action(dashboard, [])
        self.assertEqual(calls, {})
        self.assertEqual(dashboard.message, "cancelled")

    def test_a_single_scanned_folder_is_used_and_remembered(self):
        dashboard = self.dashboard()
        calls, save = self.run_action(dashboard, [(self.game, "~/Games")])
        self.assertEqual(calls["game"], self.game)
        save.assert_called_once()

    def test_a_failed_build_says_so(self):
        dashboard = self.dashboard()
        self.run_action(dashboard, [(self.game, "the launcher")], result=False)
        self.assertTrue(dashboard.message.startswith("REBUILD FAILED"))


class LocalBuildTest(unittest.TestCase):
    """build_client's sequence, with the compiler and the venv stubbed out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root / "repo")
        self.game = make_game_dir(self.root / "game")
        self.lines = []
        self.commands = []

    def tearDown(self):
        self.tmp.cleanup()

    def emit(self, line):
        self.lines.append(str(line))

    def fake_run(self, command, cwd, emit, **kwargs):
        self.commands.append([str(part) for part in command])
        return 0

    def build(self, **kwargs):
        with mock.patch.object(TUI, "local_run", side_effect=self.fake_run), \
                mock.patch.object(TUI, "ensure_build_tools", return_value="/venv/python"):
            return TUI.build_client(
                {"game_dir": str(self.game)}, self.emit, repo=self.repo,
                game=kwargs.get("game", self.game),
            )

    def test_prepare_then_host64(self):
        self.assertTrue(self.build())
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(self.commands[0][1:],
                         ["tools/prepare.py", "--game", str(self.game)])
        self.assertEqual(self.commands[1][1:],
                         ["tools/build_posix.py", "host64", "--game", str(self.game)])
        self.assertTrue(any("built" in line for line in self.lines))

    def test_prepare_is_skipped_when_the_recorded_folder_matches(self):
        (self.repo / "generated").mkdir()
        (self.repo / "generated" / "build.json").write_text(
            json.dumps({"build": "2026-10-05", "game": str(self.game)})
        )
        self.assertTrue(self.build())
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.commands[0][1:3], ["tools/build_posix.py", "host64"])

    def test_a_failed_compile_reports_the_log(self):
        (self.repo / "generated").mkdir()
        (self.repo / "generated" / "build.json").write_text(
            json.dumps({"build": "2026-10-05", "game": str(self.game)})
        )
        with mock.patch.object(TUI, "local_run", side_effect=lambda *a, **k: 2), \
                mock.patch.object(TUI, "ensure_build_tools", return_value="/venv/python"):
            ok = TUI.build_client(
                {"game_dir": str(self.game)}, self.emit, repo=self.repo, game=self.game
            )
        self.assertFalse(ok)
        self.assertTrue(any("build failed" in line for line in self.lines))

    def test_a_failed_link_restores_the_previous_client(self):
        (self.repo / "generated").mkdir()
        (self.repo / "generated" / "build.json").write_text(
            json.dumps({"build": "2026-10-05", "game": str(self.game)})
        )
        binary = self.repo / "build" / TUI.CLIENT_BIN
        binary.write_text("old client")
        binary.chmod(0o755)

        def failing_link(command, cwd, emit, **kwargs):
            binary.unlink()  # clang removes its output when the link fails
            return 1

        with mock.patch.object(TUI, "local_run", side_effect=failing_link), \
                mock.patch.object(TUI, "ensure_build_tools", return_value="/venv/python"):
            ok = TUI.build_client(
                {"game_dir": str(self.game)}, self.emit, repo=self.repo, game=self.game
            )
        self.assertFalse(ok)
        self.assertEqual(binary.read_text(), "old client")
        self.assertTrue(os.access(binary, os.X_OK), "the restored client must still be runnable")
        self.assertTrue(any("back at" in line for line in self.lines))

    def test_a_successful_build_keeps_a_copy_to_fall_back_to(self):
        self.assertTrue(self.build())
        previous = self.repo / "build" / (TUI.CLIENT_BIN + ".previous")
        self.assertTrue(previous.is_file())
        self.assertTrue((self.repo / "build" / "runtime.previous.json").is_file())

    def test_a_cancelled_build_says_so(self):
        with mock.patch.object(TUI, "local_run", side_effect=lambda *a, **k: 130), \
                mock.patch.object(TUI, "ensure_build_tools", return_value="/venv/python"):
            ok = TUI.build_client(
                {"game_dir": str(self.game)}, self.emit, repo=self.repo, game=self.game
            )
        self.assertFalse(ok)
        self.assertIn("rebuild cancelled", self.lines)

    def test_a_directory_that_is_not_a_checkout_is_refused(self):
        ok = TUI.build_client({}, self.emit, repo=self.root / "not-a-checkout", game=self.game)
        self.assertFalse(ok)
        self.assertTrue(any("not a Fanxi checkout" in line for line in self.lines))

    def test_no_game_folder_is_an_error(self):
        with mock.patch.object(TUI, "game_dir_candidates", return_value=[]):
            ok = TUI.build_client({}, self.emit, repo=self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("no FINAL FANTASY XI folder" in line for line in self.lines))

    def test_local_run_streams_and_cancels(self):
        lines = []
        code = TUI.local_run(
            [sys.executable, "-c", "print('one'); print('two')"], self.root, lines.append
        )
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["one", "two"])

        seen = []
        code = TUI.local_run(
            [sys.executable, "-c", "import time; print('go', flush=True); time.sleep(60)"],
            self.root, seen.append, should_stop=lambda: bool(seen),
        )
        self.assertEqual(code, 130)
        self.assertEqual(seen, ["go", "cancelled"])

    def test_the_build_log_keeps_the_output(self):
        code = TUI.local_run(
            [sys.executable, "-c", "print('kept')"], self.root, self.emit,
            log_path=self.repo / "build" / TUI.BUILD_LOG,
        )
        self.assertEqual(code, 0)
        log = (self.repo / "build" / TUI.BUILD_LOG).read_text()
        self.assertIn("kept", log)
        self.assertIn(sys.executable, log.splitlines()[0])


def make_launcher(root: Path, *, version="0.1.0", built=True):
    """A scratch checkout with launcher-rs, and the launcher directory in it."""
    launcher = root / "launcher-rs"
    (launcher / "src").mkdir(parents=True)
    (launcher / "src-tauri" / "src").mkdir(parents=True)
    (launcher / "src" / "main.tsx").write_text("")
    (launcher / "src-tauri" / "src" / "main.rs").write_text("")
    (launcher / "package.json").write_text(json.dumps({"name": "fanxi-launcher", "version": version}))
    (launcher / "package-lock.json").write_text("{}")
    (launcher / "src-tauri" / "Cargo.toml").write_text("")
    (launcher / "src-tauri" / "tauri.conf.json").write_text(json.dumps({"version": version}))
    (launcher / "node_modules" / ".bin").mkdir(parents=True)
    (launcher / "node_modules" / ".bin" / "tauri").write_text("")
    stamp = launcher / "node_modules" / ".package-lock.json"
    stamp.write_text("{}")
    now = time.time()
    os.utime(stamp, (now + 1, now + 1))
    if built:
        artifact, kind = TUI.launcher_artifact(launcher)
        executable = TUI.launcher_executable(launcher, artifact, kind)
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("")
        os.utime(executable, (now + 5, now + 5))
    return root, launcher


class LauncherStateTest(unittest.TestCase):
    """The launcher artifact against the sources: is the built app still current?"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_built_launcher_is_current(self):
        repo, launcher = make_launcher(self.root / "repo")
        state = TUI.launcher_state(repo)
        self.assertTrue(state["exists"])
        self.assertFalse(state["stale"], state)
        self.assertEqual(state["version"], "0.1.0")
        self.assertEqual(state["kind"], "app" if sys.platform == "darwin" else "binary")
        self.assertEqual(TUI.launcher_summary(state), "0.1.0 · built")

    def test_a_missing_artifact_is_not_built(self):
        repo, launcher = make_launcher(self.root / "repo", built=False)
        state = TUI.launcher_state(repo)
        self.assertFalse(state["exists"])
        self.assertTrue(state["stale"])
        self.assertEqual(TUI.launcher_summary(state), "not built")

    def test_newer_sources_make_it_stale(self):
        repo, launcher = make_launcher(self.root / "repo")
        source = launcher / "src-tauri" / "src" / "main.rs"
        source.write_text("// changed")
        later = time.time() + 60
        os.utime(source, (later, later))
        state = TUI.launcher_state(repo)
        self.assertTrue(state["stale"])
        self.assertEqual(state["reason"], "sources are newer")
        self.assertIn("stale", TUI.launcher_summary(state))

    def test_a_checkout_without_launcher_rs(self):
        self.assertEqual(TUI.launcher_state(self.root / "empty"), {})
        self.assertEqual(TUI.launcher_summary({}), "no launcher-rs")


class LauncherBuildTest(unittest.TestCase):
    """build_launcher's sequence, with npm, cargo and the build stubbed out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo, self.launcher = make_launcher(self.root / "repo")
        self.lines = []
        self.commands = []

    def tearDown(self):
        self.tmp.cleanup()

    def emit(self, line):
        self.lines.append(str(line))

    def tool(self, command, **kwargs):
        if str(command[0]).endswith("node"):
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if str(command[0]).endswith("cargo"):
            return types.SimpleNamespace(returncode=0, stdout="cargo 1.97.1 (x)\n", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_run(self, command, cwd, emit, **kwargs):
        self.commands.append([str(part) for part in command])
        if [str(part) for part in command[1:3]] == ["ci"]:
            (self.launcher / "node_modules" / ".bin" / "tauri").write_text("")
        return 0

    def build(self, result=0):
        with mock.patch.object(TUI.shutil, "which",
                               side_effect=lambda name: f"/fake/{name}"
                               if name in ("node", "npm", "cargo") else None), \
                mock.patch.object(TUI.subprocess, "run", side_effect=self.tool), \
                mock.patch.object(TUI, "local_run", side_effect=self.fake_run):
            return TUI.build_launcher({}, self.emit, repo=self.repo)

    def expected_tauri(self):
        return ["run", "tauri", "build", "--"] + (
            ["--bundles", "app"] if sys.platform == "darwin" else ["--no-bundle"])

    def test_builds_the_launcher_with_the_platform_bundles(self):
        self.assertTrue(self.build())
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.commands[0][1:], self.expected_tauri())
        self.assertTrue(any("built" in line for line in self.lines))
        self.assertTrue(any("0.1.0" in line for line in self.lines))

    def test_missing_packages_run_npm_ci_first(self):
        (self.launcher / "node_modules" / ".bin" / "tauri").unlink()
        self.assertTrue(self.build())
        self.assertEqual(self.commands[0][1:], ["ci"])
        self.assertEqual(self.commands[1][1:], self.expected_tauri())

    def test_a_stale_package_lock_runs_npm_ci(self):
        lock = self.launcher / "package-lock.json"
        stamp = self.launcher / "node_modules" / ".package-lock.json"
        later = time.time() + 60
        os.utime(lock, (later, later))
        self.assertTrue(lock.stat().st_mtime > stamp.stat().st_mtime)
        self.assertTrue(self.build())
        self.assertEqual(self.commands[0][1:], ["ci"])

    def test_a_missing_toolchain_is_explained(self):
        with mock.patch.object(TUI.shutil, "which",
                               side_effect=lambda name: None if name == "cargo"
                               else f"/fake/{name}"):
            ok = TUI.build_launcher({}, self.emit, repo=self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("missing cargo" in line for line in self.lines))

    def test_a_failed_build_reports_the_log(self):
        with mock.patch.object(TUI.shutil, "which",
                               side_effect=lambda name: f"/fake/{name}"), \
                mock.patch.object(TUI.subprocess, "run", side_effect=self.tool), \
                mock.patch.object(TUI, "local_run", side_effect=lambda *a, **k: 2):
            ok = TUI.build_launcher({}, self.emit, repo=self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("launcher build failed" in line for line in self.lines))

    def test_a_cancelled_build_says_so(self):
        with mock.patch.object(TUI.shutil, "which",
                               side_effect=lambda name: f"/fake/{name}"), \
                mock.patch.object(TUI.subprocess, "run", side_effect=self.tool), \
                mock.patch.object(TUI, "local_run", side_effect=lambda *a, **k: 130):
            ok = TUI.build_launcher({}, self.emit, repo=self.repo)
        self.assertFalse(ok)
        self.assertIn("rebuild cancelled", self.lines)

    def test_a_checkout_without_launcher_rs_is_an_error(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertFalse(TUI.build_launcher({}, self.emit, repo=empty))
        self.assertTrue(any("no launcher-rs checkout" in line for line in self.lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
