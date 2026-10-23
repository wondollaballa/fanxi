"""Where the launcher keeps its settings and logs.

One JSON file, written atomically and readable only by the player (0600), holds the API URL, a
token for each saved account, the game folder and the last character per account. No password is
ever stored.
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
    # Every account the player has signed in with, so multiboxing does not mean typing the
    # same password over and over.  Each entry keeps only the API token (never a password):
    # username, token, token_expires_at, character_id, characters.
    accounts: list = field(default_factory=list)

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
        config._load_legacy_account()
        return config

    # --- saved accounts ------------------------------------------------------------------------
    def _load_legacy_account(self) -> None:
        """A settings file from before the account vault held one token: fold it in."""
        if not isinstance(self.accounts, list):
            self.accounts = []
        self.accounts = [a for a in self.accounts if isinstance(a, dict) and a.get("username")]
        if self.username and self.token and self.account_entry(self.username) is None:
            self.accounts.append({
                "username": self.username,
                "token": self.token,
                "token_expires_at": self.token_expires_at,
                "character_id": self.character_id,
                "characters": [],
            })
        if self.username:
            entry = self.account_entry(self.username)
            if entry is not None:
                entry["token"] = self.token or entry.get("token", "")
                entry["token_expires_at"] = self.token_expires_at or entry.get("token_expires_at", "")
                if self.character_id is not None:
                    entry["character_id"] = self.character_id
        elif self.accounts:
            self.activate_account(self.accounts[0]["username"], save=False)

    def account_entry(self, username: str | None = None) -> dict | None:
        wanted = (username if username is not None else self.username or "").strip().lower()
        if not wanted:
            return None
        for entry in self.accounts:
            if str(entry.get("username", "")).strip().lower() == wanted:
                return entry
        return None

    def saved_accounts(self) -> list[dict]:
        return [a for a in self.accounts if a.get("username")]

    def remember_account(self, account: dict, token: str, expires_at: str = "",
                         characters: list | None = None) -> dict:
        """Store or refresh one account's token and make it the active account."""
        self._load_legacy_account()
        username = str(account.get("username") or "").strip()
        if not username or not token:
            return {}
        for entry in self.accounts:
            if str(entry.get("username", "")).strip().lower() == username.lower():
                break
        else:
            entry = {"username": username, "characters": []}
            self.accounts.append(entry)
        entry["token"] = token
        entry["token_expires_at"] = expires_at or entry.get("token_expires_at", "")
        if characters is not None:
            entry["characters"] = list(characters)
        chosen = entry.get("character_id")
        if characters:
            ids = [c.get("id") for c in characters if isinstance(c, dict)]
            if chosen not in ids:
                chosen = ids[0] if ids else None
        entry["character_id"] = chosen
        self.username = username
        self.token = token
        self.token_expires_at = entry.get("token_expires_at", "")
        self.character_id = chosen
        return entry

    def activate_account(self, username: str, *, save: bool = True) -> bool:
        entry = self.account_entry(username)
        if entry is None:
            return False
        self.username = str(entry.get("username") or "")
        self.token = str(entry.get("token") or "")
        self.token_expires_at = str(entry.get("token_expires_at") or "")
        self.character_id = entry.get("character_id")
        if save:
            self.save()
        return True

    def forget_account(self, username: str | None = None) -> None:
        """Forget an account's token; the active account falls back to the next saved one."""
        entry = self.account_entry(username)
        was_active = entry is not None and self.account_entry() is entry
        if entry is not None:
            self.accounts.remove(entry)
        if was_active:
            self.token = ""
            self.token_expires_at = ""
            self.username = ""
            self.character_id = None
            if self.accounts:
                self.activate_account(self.accounts[0]["username"], save=False)

    def sync_active_account(self) -> None:
        entry = self.account_entry()
        if entry is None:
            return
        entry["token"] = self.token
        entry["token_expires_at"] = self.token_expires_at
        entry["character_id"] = self.character_id

    def save(self, path: Path | None = None) -> None:
        self.sync_active_account()
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
        """Forget the active account's token, keeping any other saved accounts."""
        if self.username:
            if self.account_entry(self.username) is not None:
                self.forget_account(self.username)
            else:
                self.token = ""
                self.token_expires_at = ""
                self.username = ""
                self.character_id = None
        if not self.token:
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
