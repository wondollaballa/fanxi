"""Where the launcher keeps its settings and logs.

One JSON file, written atomically and readable only by the player (0600), holds the API URL, the
last session token, the game folder and the last character. No password is ever stored.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_API = "http://127.0.0.1:8080"


def data_dir() -> Path:
    override = os.environ.get("FANXI_LAUNCHER_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Fanxi"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Fanxi"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "fanxi"


def config_path() -> Path:
    return data_dir() / "launcher.json"


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class LauncherConfig:
    api_url: str = DEFAULT_API
    token: str = ""
    token_expires_at: str = ""
    username: str = ""
    character_id: int | None = None
    game_dir: str = ""
    host64: str = ""
    auto_login: bool = True
    last_page: str = "home"

    @classmethod
    def load(cls, path: Path | None = None) -> "LauncherConfig":
        path = path or config_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        config = cls(**{k: v for k, v in raw.items() if k in known})
        if not config.api_url:
            config.api_url = DEFAULT_API
        return config

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    def api_base(self) -> str:
        return self.api_url.rstrip("/")

    def clear_session(self) -> None:
        self.token = ""
        self.token_expires_at = ""
        self.username = ""
        self.character_id = None


@dataclass
class UiState:
    """A tiny in-memory model the UI can be rebuilt from (also useful to tests)."""
    signed_in: bool = False
    account: dict | None = None
    characters: list = field(default_factory=list)
    status: dict | None = None
    news: list = field(default_factory=list)

    @property
    def character(self):
        if not self.characters:
            return None
        if self.account:
            for character in self.characters:
                if character.get("id") == self.account.get("character_id"):
                    return character
        return self.characters[0]
