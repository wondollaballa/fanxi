"""Finding the game, building host64 and starting it.

The launcher never touches the player's game files: ``tools/prepare.py`` and
``tools/build_posix.py`` do, from the player's own install, exactly as the source installer always
has. This module only finds the folder, runs those tools and passes the launch token to host64.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import LauncherConfig, log_dir


class GameError(Exception):
    pass


def repo_root() -> Path:
    """The Fanxi checkout: this package's repository, or the one a bundle was built from."""
    override = os.environ.get("FANXI_REPO_ROOT")
    if override:
        candidate = Path(override).expanduser()
        if (candidate / "tools" / "build_posix.py").exists():
            return candidate.resolve()
    return Path(__file__).resolve().parents[2]


def is_game_dir(path: str | Path | None) -> bool:
    if not path:
        return False
    folder = Path(path).expanduser()
    return (folder / "FFXiMain.dll").exists() and (folder / "FFXi.dll").exists() and (folder / "ROM").is_dir()


def candidate_game_dirs(configured: str = "") -> list[Path]:
    home = Path.home()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if os.environ.get("FANXI_GAME_DIR"):
        candidates.append(Path(os.environ["FANXI_GAME_DIR"]).expanduser())
    candidates += [
        home / "Games" / "FINAL FANTASY XI",
        home / "SquareEnix" / "FINAL FANTASY XI",
        home / "Documents" / "FINAL FANTASY XI",
        home / "Desktop" / "FINAL FANTASY XI",
        Path("/Applications") / "FINAL FANTASY XI",
        Path("/Games") / "FINAL FANTASY XI",
    ]
    seen, result = set(), []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(candidate)
    return result


def find_game_dir(configured: str = "") -> Path | None:
    for candidate in candidate_game_dirs(configured):
        if is_game_dir(candidate):
            return candidate
    return None


def host64_candidates(config: LauncherConfig | None = None) -> list[Path]:
    root = repo_root()
    candidates = []
    env = os.environ.get("FANXI_HOST64")
    if env:
        candidates.append(Path(env).expanduser())
    if config and config.host64:
        candidates.append(Path(config.host64).expanduser())
    candidates += [
        root / "build" / ("host64.exe" if sys.platform == "win32" else "host64"),
        root / "build" / "Fanxi.app" / "Contents" / "MacOS" / "Fanxi",
        root / "build" / "Fanxi Launcher.app" / "Contents" / "MacOS" / "host64",
    ]
    return candidates


def find_host64(config: LauncherConfig | None = None) -> Path | None:
    for candidate in host64_candidates(config):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def build_launch_command(host64: str | Path, game_dir: str | Path, client: dict, login_token: str,
                         extra: list[str] | None = None) -> list[str]:
    """host64's arguments for a launcher-issued session."""
    command = [
        str(host64),
        "--game", str(game_dir),
        "--server", str(client["server"]),
        "--user", str(client["username"]),
        "--login-token", str(login_token),
        "--authport", str(int(client["auth_port"])),
        "--dataport", str(int(client["data_port"])),
        "--viewport", str(int(client["view_port"])),
    ]
    if extra:
        command += [str(item) for item in extra]
    return command


def _venv_python(root: Path) -> Path:
    if sys.platform == "win32":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _run_streamed(command: list[str], cwd: Path, progress, env: dict | None = None,
                  log_path: Path | None = None) -> None:
    tail: list[str] = []
    log = open(log_path, "a", encoding="utf-8", errors="replace") if log_path else None
    if log:
        log.write("\n$ %s\n" % " ".join(command))
        log.flush()
    try:
        process = subprocess.Popen(
            command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            tail = (tail + [line])[-25:]
            if log:
                log.write(line + "\n")
                log.flush()
            if progress:
                progress(_humanize(line))
        code = process.wait()
    finally:
        if log:
            log.close()
    if code:
        raise GameError("the build failed (exit %d).\n\n%s" % (code, "\n".join(tail[-15:])))


def _humanize(line: str) -> str:
    if line.startswith("@phase "):
        return "— %s —" % line[7:].strip()
    if line.startswith("@progress "):
        parts = line.split()
        if len(parts) == 3:
            try:
                done, total = int(parts[1]), int(parts[2])
            except ValueError:
                return line
            percent = (done * 100 // total) if total else 100
            return "  %d%%  (%d/%d)" % (percent, done, total)
    return line


class GameManager:
    def __init__(self, config: LauncherConfig):
        self.config = config
        self.root = repo_root()
        self.build_log_path = log_dir() / "build.log"

    # --- build ---------------------------------------------------------------------------------
    def venv_python(self) -> Path | None:
        path = _venv_python(self.root)
        return path if path.exists() else None

    def ensure_build_tools(self, progress=None) -> Path:
        python = self.venv_python()
        if python is None:
            if progress:
                progress("Creating the Python environment for the recompiler…")
            _run_streamed([sys.executable, "-m", "venv", str(self.root / ".venv")], self.root, progress,
                          log_path=self.build_log_path)
            python = self.venv_python()
            if python is None:
                raise GameError("could not create .venv in %s" % self.root)
        check = subprocess.run([str(python), "-c", "import capstone, pefile"],
                               cwd=str(self.root), capture_output=True, text=True)
        if check.returncode:
            if progress:
                progress("Installing the recompiler's Python packages (capstone, pefile)…")
            _run_streamed([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                           "capstone>=5,<6", "pefile>=2023"], self.root, progress,
                          log_path=self.build_log_path)
            check = subprocess.run([str(python), "-c", "import capstone, pefile"],
                                   cwd=str(self.root), capture_output=True, text=True)
            if check.returncode:
                raise GameError("the recompiler's Python packages could not be installed:\n%s"
                                % (check.stderr or check.stdout))
        return python

    def build(self, game_dir: str | Path, progress=None) -> Path:
        game = Path(game_dir).expanduser()
        if not is_game_dir(game):
            raise GameError("%s is not a FINAL FANTASY XI folder: FFXiMain.dll, FFXi.dll and ROM are needed"
                            % game)
        python = self.ensure_build_tools(progress)
        if progress:
            progress("Translating and compiling host64 from %s…" % game)
        env = dict(os.environ, FFXI_PROGRESS="1")
        _run_streamed([str(python), "tools/build_posix.py", "host64", "--game", str(game)],
                      self.root, progress, env, self.build_log_path)
        host64 = self.root / "build" / ("host64.exe" if sys.platform == "win32" else "host64")
        if not host64.exists():
            raise GameError("the build finished but %s is missing" % host64)
        self.config.host64 = str(host64)
        self.config.game_dir = str(game.resolve())
        return host64

    def build_needed(self) -> bool:
        return find_host64(self.config) is None

    # --- launch --------------------------------------------------------------------------------
    def launch(self, game_dir: str | Path, client: dict, login_token: str,
               extra: list[str] | None = None) -> subprocess.Popen:
        host64 = find_host64(self.config)
        if host64 is None:
            raise GameError("host64 is not built yet. Open Settings and press Build game.")
        if not is_game_dir(game_dir):
            raise GameError("the game folder is missing or incomplete: %s" % game_dir)
        command = build_launch_command(host64, game_dir, client, login_token, extra)
        log_path = log_dir() / "game.log"
        log = open(log_path, "ab")
        options = {
            "cwd": str(self.root),
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
            "env": dict(os.environ),
        }
        if os.name != "nt":
            options["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **options)
        finally:
            log.close()
        return process

    # --- little helpers for the UI -------------------------------------------------------------
    def log_tail(self, lines: int = 40) -> str:
        return self._tail(log_dir() / "game.log", lines)

    def build_log_tail(self, lines: int = 40) -> str:
        return self._tail(self.build_log_path, lines)

    @staticmethod
    def _tail(path: Path, lines: int) -> str:
        try:
            data = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        return "\n".join(data[-lines:])

    def open_data_dir(self) -> None:
        path = log_dir().parent
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
