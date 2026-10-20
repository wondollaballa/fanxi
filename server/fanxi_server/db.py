"""SQLite storage for Fanxi: connections, migrations and small query helpers.

The schema lives in database/migrations/*.sql at the repository root, and the starter data in
database/seed.sql. A database is just a file, so a server is one folder to back up: data/fanxi.db
(and its -wal/-shm companions while it runs).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .security import now_iso


class Database:
    def __init__(self, path: Path, root: Path):
        self.path = Path(path)
        self.root = Path(root)
        self.migrations_dir = self.root / "database" / "migrations"
        self.seed_file = self.root / "database" / "seed.sql"

    # --- connections ---------------------------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def connection(self):
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # --- schema --------------------------------------------------------------------------------
    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            conn.commit()
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(self.migrations_dir.glob("*.sql")):
                try:
                    version = int(path.name.split("_", 1)[0])
                except ValueError:
                    continue
                if version in applied:
                    continue
                self._apply_script(conn, path)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, path.name, now_iso()),
                )
                conn.commit()
            seeded = conn.execute("SELECT 1 FROM settings WHERE key = 'seed_version'").fetchone()
            if not seeded and self.seed_file.exists():
                self._apply_script(conn, self.seed_file)

    @staticmethod
    def _apply_script(conn: sqlite3.Connection, path: Path) -> None:
        """Run a .sql file one complete statement at a time, inside a transaction."""
        sql = path.read_text(encoding="utf-8")
        conn.execute("BEGIN IMMEDIATE")
        try:
            buffer = ""
            for line in sql.splitlines(keepends=True):
                buffer += line
                if sqlite3.complete_statement(buffer):
                    statement = buffer.strip()
                    buffer = ""
                    if statement:
                        conn.execute(statement)
            if buffer.strip():
                conn.execute(buffer.strip())
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # --- helpers -------------------------------------------------------------------------------
    def one(self, sql: str, params=()):
        with self.connection() as conn:
            return conn.execute(sql, params).fetchone()

    def all(self, sql: str, params=()):
        with self.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params=(), default=None):
        row = self.one(sql, params)
        return default if row is None else row[0]

    def execute(self, sql: str, params=()) -> int:
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid

    def setting(self, key: str, default: str | None = None) -> str | None:
        return self.scalar("SELECT value FROM settings WHERE key = ?", (key,), default)

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
