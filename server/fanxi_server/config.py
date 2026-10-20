"""Configuration for the Fanxi server, read from FANXI_* environment variables.

Every path is absolute after Config.from_env(). All defaults are for a local development
server: HTTP on 127.0.0.1:8080, the game gateway on the usual FINAL FANTASY XI ports.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GAME_PORTS = {
    "auth_port": 54231,
    "data_port": 54230,
    "view_port": 54001,
    "zone_port": 54230,
    "search_port": 54002,
}


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        raise SystemExit("%s must be a number, not %r" % (name, os.environ.get(name)))


def _bool(name: str, default: bool) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value not in ("0", "false", "no", "off")


def _path(root: Path, name: str, default: str) -> Path:
    value = os.path.expanduser(_env(name, default))
    p = Path(value)
    return p if p.is_absolute() else (root / p).resolve()


@dataclass(frozen=True)
class Config:
    root: Path
    bind: str = "127.0.0.1"
    http_port: int = 8080
    public_host: str = "127.0.0.1"
    db_path: Path = field(default_factory=lambda: Path("data/fanxi.db"))
    tls_cert: Path = field(default_factory=lambda: Path("data/tls/auth-cert.pem"))
    tls_key: Path = field(default_factory=lambda: Path("data/tls/auth-key.pem"))
    game_dir: Path | None = None
    huffman_dir: Path | None = None
    admin_key: str = ""
    registration_open: bool = True
    max_characters: int = 1
    api_session_days: int = 30
    game_session_hours: int = 12
    login_token_seconds: int = 120
    cors_origin: str = "*"
    log_level: str = "info"
    ports: dict = field(default_factory=lambda: dict(DEFAULT_GAME_PORTS))

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Config":
        root = (root or Path(__file__).resolve().parents[2]).resolve()
        game_dir = _env("FANXI_GAME_DIR", "")
        huffman = _env("FANXI_HUFFMAN", "")
        return cls(
            root=root,
            bind=_env("FANXI_BIND", "127.0.0.1"),
            http_port=_int("FANXI_HTTP_PORT", 8080),
            public_host=_env("FANXI_PUBLIC_HOST", "127.0.0.1"),
            db_path=_path(root, "FANXI_DB", "data/fanxi.db"),
            tls_cert=_path(root, "FANXI_TLS_CERT", "data/tls/auth-cert.pem"),
            tls_key=_path(root, "FANXI_TLS_KEY", "data/tls/auth-key.pem"),
            game_dir=Path(os.path.expanduser(game_dir)).resolve() if game_dir else None,
            huffman_dir=Path(os.path.expanduser(huffman)).resolve() if huffman else None,
            admin_key=_env("FANXI_ADMIN_KEY", ""),
            registration_open=_bool("FANXI_REGISTRATION", True),
            max_characters=_int("FANXI_MAX_CHARACTERS", 1),
            api_session_days=_int("FANXI_SESSION_DAYS", 30),
            game_session_hours=_int("FANXI_GAME_SESSION_HOURS", 12),
            login_token_seconds=_int("FANXI_LOGIN_TOKEN_SECONDS", 120),
            cors_origin=_env("FANXI_CORS_ORIGIN", "*"),
            log_level=_env("FANXI_LOG_LEVEL", "info").lower(),
            ports={
                "auth_port": _int("FANXI_AUTH_PORT", DEFAULT_GAME_PORTS["auth_port"]),
                "data_port": _int("FANXI_DATA_PORT", DEFAULT_GAME_PORTS["data_port"]),
                "view_port": _int("FANXI_VIEW_PORT", DEFAULT_GAME_PORTS["view_port"]),
                "zone_port": _int("FANXI_ZONE_PORT", DEFAULT_GAME_PORTS["zone_port"]),
                "search_port": _int("FANXI_SEARCH_PORT", DEFAULT_GAME_PORTS["search_port"]),
            },
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tls_cert.parent.mkdir(parents=True, exist_ok=True)

    def find_game_dir(self) -> Path | None:
        if self.game_dir and (self.game_dir / "FFXiMain.dll").exists():
            return self.game_dir
        home = Path.home()
        candidates = [
            self.game_dir,
            home / "Games" / "FINAL FANTASY XI",
            home / "SquareEnix" / "FINAL FANTASY XI",
            home / "Documents" / "FINAL FANTASY XI",
            Path("/Applications") / "FINAL FANTASY XI",
        ]
        for candidate in candidates:
            if candidate and (candidate / "FFXiMain.dll").exists():
                return candidate
        return None

    def find_huffman_dir(self) -> Path | None:
        """The folder holding compress.dat, which the zone protocol needs."""
        if self.huffman_dir:
            if (self.huffman_dir / "compress.dat").exists():
                return self.huffman_dir
            if self.huffman_dir.name == "compress.dat" and self.huffman_dir.exists():
                return self.huffman_dir.parent
        game = self.find_game_dir()
        if game:
            for rel in ("res", "RES", "rom", "ROM", "."):
                if (game / rel / "compress.dat").exists():
                    return game / rel
        for base in (Path.home() / "SquareEnix" / "FINAL FANTASY XI",
                     Path.home() / "Games" / "FINAL FANTASY XI"):
            if (base / "res" / "compress.dat").exists():
                return base / "res"
        return None
