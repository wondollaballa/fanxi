"""Accounts, characters, sessions and admin operations.

The HTTP layer and the game gateway both call this module; it is the only place that writes
account data. Every method is synchronous and opens its own SQLite connection, so the threaded
HTTP server and the game sockets can use it without sharing a connection.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import __version__
from .config import Config
from .db import Database
from .security import (
    ValidationError,
    expired,
    hash_password,
    iso,
    iso_after,
    new_session_hash,
    new_token,
    now_iso,
    token_hash,
    utcnow,
    validate_character_name,
    validate_email,
    validate_int,
    validate_password,
    validate_username,
    verify_password,
)

CHAR_ID_BASE = 0x01000000
DEFAULT_ZONE = 246
FAILED_LOGIN_LIMIT = 5
LOCK_MINUTES = 15
STARTER_GIL = 1000
STARTER_ITEMS = ((1, 4112, 2), (2, 16534, 1))  # slot, item id, quantity


def exp_for_level(level: int) -> int:
    """Experience needed to reach the next level. Fanxi's own curve, not retail's table."""
    return max(100, int(100 * (max(1, int(level)) ** 1.5)))


class ApiError(Exception):
    """An error the HTTP layer or game gateway knows how to present."""

    def __init__(self, status: int, code: str, message: str, *, game_result: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.game_result = game_result


@dataclass
class AuthResult:
    account: dict
    token: str
    expires_at: str


def _row(row: sqlite3.Row | None) -> dict | None:
    return None if row is None else dict(row)


class FanxiService:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.started_at = now_iso()
        self._login_failures: dict[str, list[float]] = {}

    # --- accounts ------------------------------------------------------------------------------
    def account(self, account_id: int) -> dict:
        row = self.db.one("SELECT * FROM accounts WHERE id = ?", (account_id,))
        if row is None:
            raise ApiError(404, "not_found", "account not found")
        return dict(row)

    def public_account(self, row) -> dict:
        row = dict(row)
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row.get("email"),
            "role": row["role"],
            "status": row["status"],
            "created_at": row["created_at"],
            "last_login_at": row.get("last_login_at"),
        }

    def register(self, username: str, password: str, email: str | None = None,
                 ip: str | None = None) -> AuthResult:
        if not self.registration_open():
            raise ApiError(403, "registration_closed", "registration is closed on this server")
        try:
            username = validate_username(username)
            password = validate_password(password)
            email = validate_email(email)
        except ValidationError as exc:
            raise ApiError(422, "validation_error", str(exc))
        password_hash = hash_password(password)
        created = now_iso()
        try:
            with self.db.transaction() as conn:
                cur = conn.execute(
                    "INSERT INTO accounts (username, email, password_hash, status, role, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'active', 'player', ?, ?)",
                    (username, email, password_hash, created, created),
                )
                account_id = int(cur.lastrowid)
                self._audit_conn(conn, account_id, "account.register", "from %s" % (ip or "?"))
        except sqlite3.IntegrityError:
            raise ApiError(409, "username_taken", "that username is already taken")
        token, expires = self._new_api_session(account_id, ip=ip)
        return AuthResult(self.public_account(self.account(account_id)), token, expires)

    def login(self, username: str, password: str, ip: str | None = None) -> AuthResult:
        self._rate_limit(ip)
        row = self.db.one("SELECT * FROM accounts WHERE username = ?", ((username or "").strip(),))
        if row is None:
            # Spend the same work as a real check, so a missing name is not faster than a wrong password.
            verify_password(password or "", hash_password("fanxi-dummy-password", iterations=1000))
            self._login_failure(ip)
            raise ApiError(401, "invalid_credentials", "invalid username or password")
        account = dict(row)
        if account["locked_until"] and not expired(account["locked_until"]):
            raise ApiError(423, "account_locked", "too many failed attempts; try again later")
        if account["status"] != "active":
            raise ApiError(403, "account_" + account["status"], "this account may not sign in")
        if not verify_password(password or "", account["password_hash"]):
            self._record_failed_login(account["id"], ip)
            self._login_failure(ip)
            raise ApiError(401, "invalid_credentials", "invalid username or password")
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE accounts SET failed_attempts = 0, locked_until = NULL, last_login_at = ?, updated_at = ? "
                "WHERE id = ?",
                (now_iso(), now_iso(), account["id"]),
            )
            self._audit_conn(conn, account["id"], "account.login", "from %s" % (ip or "?"))
        token, expires = self._new_api_session(account["id"], ip=ip)
        account = self.account(account["id"])
        return AuthResult(self.public_account(account), token, expires)

    def authenticate(self, token: str | None) -> dict:
        if not token or len(token) < 20:
            raise ApiError(401, "unauthorized", "sign in first")
        row = self.db.one(
            "SELECT a.* FROM api_sessions s JOIN accounts a ON a.id = s.account_id "
            "WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?",
            (token_hash(token), now_iso()),
        )
        if row is None:
            raise ApiError(401, "unauthorized", "the session is invalid or has expired")
        account = dict(row)
        if account["status"] != "active":
            raise ApiError(403, "account_" + account["status"], "this account may not sign in")
        return account

    def logout(self, token: str, ip: str | None = None) -> None:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT account_id FROM api_sessions WHERE token_hash = ? AND revoked_at IS NULL",
                (token_hash(token),),
            ).fetchone()
            conn.execute(
                "UPDATE api_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (now_iso(), token_hash(token)),
            )
            if row:
                self._audit_conn(conn, row["account_id"], "account.logout", "")

    def _new_api_session(self, account_id: int, *, ip: str | None = None) -> tuple[str, str]:
        token = new_token(48)
        expires = iso_after(days=self.config.api_session_days)
        self.db.execute(
            "INSERT INTO api_sessions (account_id, token_hash, created_at, expires_at, ip) VALUES (?, ?, ?, ?, ?)",
            (account_id, token_hash(token), now_iso(), expires, ip),
        )
        return token, expires

    def _record_failed_login(self, account_id: int, ip: str | None) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT failed_attempts FROM accounts WHERE id = ?", (account_id,)).fetchone()
            count = (row["failed_attempts"] if row else 0) + 1
            locked = iso_after(minutes=LOCK_MINUTES) if count >= FAILED_LOGIN_LIMIT else None
            conn.execute(
                "UPDATE accounts SET failed_attempts = ?, locked_until = ?, updated_at = ? WHERE id = ?",
                (count, locked if count >= FAILED_LOGIN_LIMIT else None, now_iso(), account_id),
            )
            self._audit_conn(conn, account_id, "account.login_failed", "from %s" % (ip or "?"))

    def _rate_limit(self, ip: str | None) -> None:
        """A light in-memory guard against password guessing from one address."""
        if not ip:
            return
        now = time.time()
        recent = [t for t in self._login_failures.get(ip, []) if now - t < 60]
        if len(recent) >= 20:
            self._login_failures[ip] = recent
            raise ApiError(429, "rate_limited", "too many sign-in attempts; wait a minute")
        self._login_failures[ip] = recent

    def _login_failure(self, ip: str | None) -> None:
        if not ip:
            return
        self._login_failures.setdefault(ip, []).append(time.time())

    def set_account_status(self, account_id: int, status: str) -> dict:
        if status not in ("active", "suspended", "banned"):
            raise ApiError(422, "validation_error", "status must be active, suspended or banned")
        row = self.db.one("SELECT id FROM accounts WHERE id = ?", (account_id,))
        if row is None:
            raise ApiError(404, "not_found", "account not found")
        self.db.execute("UPDATE accounts SET status = ?, updated_at = ? WHERE id = ?", (status, now_iso(), account_id))
        self.db.execute("UPDATE api_sessions SET revoked_at = ? WHERE account_id = ? AND revoked_at IS NULL",
                        (now_iso(), account_id))
        self.audit(account_id, "admin.account_status", status)
        return self.public_account(self.account(account_id))

    # --- characters ----------------------------------------------------------------------------
    def character(self, character_id: int) -> dict:
        row = self.db.one("SELECT * FROM characters WHERE id = ?", (character_id,))
        if row is None:
            raise ApiError(404, "not_found", "character not found")
        return dict(row)

    def character_for_account(self, account_id: int, character_id: int | None = None) -> dict:
        if character_id is None:
            row = self.db.one(
                "SELECT * FROM characters WHERE account_id = ? ORDER BY slot, id LIMIT 1", (account_id,)
            )
        else:
            row = self.db.one(
                "SELECT * FROM characters WHERE account_id = ? AND id = ?", (account_id, character_id)
            )
        if row is None:
            raise ApiError(409, "no_character", "create a character in the launcher first")
        return dict(row)

    def public_character(self, row) -> dict:
        row = dict(row)
        return {
            "id": row["id"],
            "char_id": row["char_id"],
            "name": row["name"],
            "race": row["race"],
            "face": row["face"],
            "size": row["size"],
            "nation": row["nation"],
            "main_job": row["main_job"],
            "sub_job": row["sub_job"],
            "main_level": row["main_level"],
            "sub_level": row["sub_level"],
            "hp": row["hp"],
            "mp": row["mp"],
            "hp_current": row.get("hp_current", row["hp"]),
            "mp_current": row.get("mp_current", row["mp"]),
            "exp": row.get("exp", 0),
            "exp_next": exp_for_level(row["main_level"]),
            "gil": row.get("gil", 0),
            "zone": row["zone"],
            "position": {"x": row["pos_x"], "y": row["pos_y"], "z": row["pos_z"], "rot": row["rot"]},
            "created_at": row["created_at"],
            "last_played_at": row.get("last_played_at"),
        }

    def list_characters(self, account_id: int) -> list[dict]:
        rows = self.db.all("SELECT * FROM characters WHERE account_id = ? ORDER BY slot, id", (account_id,))
        return [self.public_character(r) for r in rows]

    def max_characters(self) -> int:
        return max(1, int(self.config.max_characters))

    def create_character(self, account_id: int, data: dict) -> dict:
        try:
            name = validate_character_name(data.get("name", ""))
            race = validate_int(data.get("race", 1), "race", 1, 8)
            face = validate_int(data.get("face", 1), "face", 1, 8)
            size = validate_int(data.get("size", 1), "size", 0, 2)
            nation = validate_int(data.get("nation", 0), "nation", 0, 2)
            main_job = validate_int(data.get("main_job", 1), "main_job", 1, 22)
            sub_job = validate_int(data.get("sub_job", 0), "sub_job", 0, 22)
        except ValidationError as exc:
            raise ApiError(422, "validation_error", str(exc))
        with self.db.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM characters WHERE account_id = ?", (account_id,)).fetchone()[0]
            if count >= self.max_characters():
                raise ApiError(409, "character_limit", "this account already has its character")
            zone = conn.execute("SELECT * FROM zones WHERE id = ?", (DEFAULT_ZONE,)).fetchone()
            if zone is None:
                zone = conn.execute("SELECT * FROM zones ORDER BY id LIMIT 1").fetchone()
            next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM characters").fetchone()[0]
            char_id = CHAR_ID_BASE + int(next_id)
            created = now_iso()
            try:
                conn.execute(
                    "INSERT INTO characters (id, account_id, slot, char_id, name, race, face, size, nation, "
                    "main_job, sub_job, main_level, sub_level, hp, mp, hp_current, mp_current, exp, gil, "
                    "speed, zone, pos_x, pos_y, pos_z, rot, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1500, 0, 1500, 0, 0, ?, 50, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        next_id, account_id, count + 1, char_id, name, race, face, size, nation,
                        main_job, sub_job, STARTER_GIL,
                        int(zone["id"]) if zone else DEFAULT_ZONE,
                        float(zone["pos_x"]) if zone else 0.0,
                        float(zone["pos_y"]) if zone else 0.0,
                        float(zone["pos_z"]) if zone else 0.0,
                        int(zone["rot"]) if zone else 0,
                        created, created,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ApiError(409, "name_taken", "that character name is already taken")
            conn.execute(
                "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity) "
                "VALUES (?, 0, 0, 65535, ?)", (next_id, STARTER_GIL))
            for slot, item_id, quantity in STARTER_ITEMS:
                conn.execute(
                    "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity) "
                    "VALUES (?, 0, ?, ?, ?)", (next_id, slot, item_id, quantity))
            self._audit_conn(conn, account_id, "character.create", name)
        return self.public_character(self.character_for_account(account_id))

    def rename_character(self, account_id: int, character_id: int, name: str) -> dict:
        try:
            name = validate_character_name(name)
        except ValidationError as exc:
            raise ApiError(422, "validation_error", str(exc))
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT id FROM characters WHERE id = ? AND account_id = ?", (character_id, account_id)
            ).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "character not found")
            try:
                conn.execute("UPDATE characters SET name = ?, updated_at = ? WHERE id = ?", (name, now_iso(), character_id))
            except sqlite3.IntegrityError:
                raise ApiError(409, "name_taken", "that character name is already taken")
            self._audit_conn(conn, account_id, "character.rename", name)
        return self.public_character(self.character_for_account(account_id, character_id))

    def save_position(self, character_id: int, zone: int, pos) -> None:
        x, y, z, rot = pos
        self.db.execute(
            "UPDATE characters SET zone = ?, pos_x = ?, pos_y = ?, pos_z = ?, rot = ?, updated_at = ?, "
            "last_played_at = ? WHERE id = ?",
            (int(zone), float(x), float(y), float(z), int(rot), now_iso(), now_iso(), int(character_id)),
        )

    def character_record(self, row, server_name: str) -> dict:
        """The character as the game gateway wants it (staticserver's DEFAULT_CHAR shape)."""
        row = dict(row)
        return {
            "id": row["id"],
            "name": row["name"],
            "char_id": row["char_id"],
            "account_id": row["account_id"],
            "race": row["race"],
            "face": row["face"],
            "size": row["size"],
            "nation": row["nation"],
            "main_job": row["main_job"],
            "main_level": row["main_level"],
            "sub_job": row["sub_job"],
            "sub_level": row["sub_level"],
            "hp": row["hp"],
            "mp": row["mp"],
            "hp_current": row.get("hp_current", row["hp"]),
            "mp_current": row.get("mp_current", row["mp"]),
            "exp": row.get("exp", 0),
            "exp_next": exp_for_level(row["main_level"]),
            "gil": row.get("gil", 0),
            "zone": row["zone"],
            "pos": [row["pos_x"], row["pos_y"], row["pos_z"], row["rot"]],
            "head": row["head"],
            "body": row["body"],
            "hands": row["hands"],
            "legs": row["legs"],
            "feet": row["feet"],
            "main": row["main"],
            "sub": row["sub"],
            "ranged": row["ranged"],
            "speed": row["speed"],
            "server_name": server_name,
            "server_id": 1,
            "targid": 0x400,
            "content_id": row["char_id"],
        }

    # --- launch hand-off -----------------------------------------------------------------------
    def launch(self, account: dict, character_id: int | None, ip: str | None = None) -> dict:
        character = self.character_for_account(account["id"], character_id)
        token = new_token(32)
        expires = iso_after(seconds=self.config.login_token_seconds)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE login_tokens SET used_at = ? WHERE account_id = ? AND used_at IS NULL",
                (now_iso(), account["id"]),
            )
            conn.execute(
                "INSERT INTO login_tokens (account_id, token_hash, created_at, expires_at, ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (account["id"], token_hash(token), now_iso(), expires, ip),
            )
            self._audit_conn(conn, account["id"], "launch.token", character["name"])
        world = self.world()
        return {
            "login_token": token,
            "expires_at": expires,
            "account": self.public_account(account),
            "character": self.public_character(character),
            "world": world,
            # host64's arguments, ready to use
            "client": {
                "server": world["host"],
                "auth_port": world["auth_port"],
                "data_port": world["data_port"],
                "view_port": world["view_port"],
                "username": account["username"],
            },
        }

    # --- game gateway --------------------------------------------------------------------------
    def game_login(self, payload: dict, ip: str | None = None) -> tuple[dict, bytes]:
        username = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        login_token = str(payload.get("login_token") or "")
        if login_token:
            account = self.consume_login_token(login_token, ip)
        else:
            self._rate_limit(ip)
            account = self._password_account(username, password, ip)
        session_hash = new_session_hash()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM game_sessions WHERE account_id = ?", (account["id"],))
            conn.execute(
                "INSERT INTO game_sessions (account_id, session_hash, created_at, expires_at, ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (account["id"], session_hash, now_iso(),
                 iso(self._game_session_expiry()), ip),
            )
            conn.execute("UPDATE accounts SET last_login_at = ?, updated_at = ? WHERE id = ?",
                         (now_iso(), now_iso(), account["id"]))
            self._audit_conn(conn, account["id"], "game.login", "from %s" % (ip or "?"))
        return account, session_hash

    def _game_session_expiry(self):
        return utcnow() + timedelta(hours=self.config.game_session_hours)

    def consume_login_token(self, token: str, ip: str | None = None) -> dict:
        digest = token_hash(token)
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM login_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                (digest, now_iso()),
            ).fetchone()
            if row is None:
                raise ApiError(401, "invalid_login_token", "the launch token is invalid or has expired", game_result=0x14)
            conn.execute("UPDATE login_tokens SET used_at = ? WHERE id = ?", (now_iso(), row["id"]))
            account = conn.execute("SELECT * FROM accounts WHERE id = ?", (row["account_id"],)).fetchone()
            if account is None or account["status"] != "active":
                raise ApiError(403, "account_suspended", "this account may not sign in", game_result=0)
            self._audit_conn(conn, account["id"], "game.token_login", "from %s" % (ip or "?"))
            return dict(account)

    def _password_account(self, username: str, password: str, ip: str | None) -> dict:
        row = self.db.one("SELECT * FROM accounts WHERE username = ?", (username.strip(),))
        if row is None:
            verify_password(password, hash_password("fanxi-dummy-password", iterations=1000))
            raise ApiError(401, "invalid_credentials", "invalid username or password", game_result=2)
        account = dict(row)
        if account["status"] != "active":
            raise ApiError(403, "account_suspended", "this account may not sign in", game_result=0)
        if account["locked_until"] and not expired(account["locked_until"]):
            raise ApiError(423, "account_locked", "too many failed attempts; try again later", game_result=0)
        if not verify_password(password, account["password_hash"]):
            self._record_failed_login(account["id"], ip)
            raise ApiError(401, "invalid_credentials", "invalid username or password", game_result=2)
        self.db.execute(
            "UPDATE accounts SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (account["id"],)
        )
        return account

    def game_account_by_hash(self, session_hash: bytes) -> dict | None:
        row = self.db.one(
            "SELECT a.* FROM game_sessions g JOIN accounts a ON a.id = g.account_id "
            "WHERE g.session_hash = ? AND g.expires_at > ? AND a.status = 'active'",
            (session_hash, now_iso()),
        )
        if row is None:
            return None
        self.db.execute("UPDATE game_sessions SET last_seen_at = ? WHERE session_hash = ?",
                        (now_iso(), session_hash))
        return dict(row)

    def characters_for_account(self, account_id: int) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM characters WHERE account_id = ? ORDER BY slot, id", (account_id,)
        )]

    def character_by_char_id(self, char_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM characters WHERE char_id = ?", (int(char_id),))
        return dict(row) if row else None

    def active_game_session(self, account_id: int) -> dict | None:
        row = self.db.one(
            "SELECT * FROM game_sessions WHERE account_id = ? AND expires_at > ? "
            "ORDER BY id DESC LIMIT 1",
            (account_id, now_iso()),
        )
        return dict(row) if row else None

    def online_count(self) -> int:
        return int(self.db.scalar(
            "SELECT COUNT(*) FROM game_sessions WHERE expires_at > ?", (now_iso(),), 0
        ))

    # --- world content -------------------------------------------------------------------------
    def npcs_for_zone(self, zone: int) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM world_npcs WHERE zone = ? ORDER BY id", (int(zone),))]

    def npc_lines(self, npc_id: int) -> list[str]:
        return [r["text"] for r in self.db.all(
            "SELECT text FROM npc_lines WHERE npc_id = ? ORDER BY line_no", (int(npc_id),))]

    def monster_spawns_for_zone(self, zone: int) -> list[dict]:
        rows = self.db.all(
            "SELECT s.*, t.name AS template_name, t.model, t.size, t.level_min, t.level_max, "
            "t.hp AS template_hp, t.mp AS template_mp, t.attack, t.defense, t.accuracy, t.evasion, "
            "t.attack_delay_ms, t.aggro, t.links, t.roam_radius, t.respawn_seconds AS template_respawn, "
            "t.name_prefix, t.behavior, t.content_tag "
            "FROM monster_spawns s JOIN monster_templates t ON t.id = s.template_id "
            "WHERE s.zone = ? AND s.enabled = 1 ORDER BY s.id", (int(zone),))
        return [dict(r) for r in rows]

    def inventory(self, character_id: int) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
            "CASE WHEN ci.item_id = 65535 THEN 'Gil' ELSE COALESCE(i.name, 'Item') END AS name, "
            "COALESCE(i.stack, 1) AS stack, COALESCE(i.usable, 0) AS usable "
            "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
            "WHERE ci.character_id = ? ORDER BY ci.container, ci.slot", (int(character_id),))]

    def item(self, item_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM items WHERE item_id = ?", (int(item_id),))
        return dict(row) if row else None

    def save_vitals(self, character_id: int, hp: int, mp: int) -> None:
        self.db.execute(
            "UPDATE characters SET hp_current = ?, mp_current = ?, updated_at = ? WHERE id = ?",
            (max(0, int(hp)), max(0, int(mp)), now_iso(), int(character_id)),
        )

    def record_death(self, character_id: int) -> None:
        self.db.execute(
            "UPDATE characters SET hp_current = 0, mp_current = 0, death_count = death_count + 1, "
            "updated_at = ? WHERE id = ?", (now_iso(), int(character_id)))

    def set_gil(self, character_id: int, amount: int) -> int:
        amount = max(0, int(amount))
        with self.db.transaction() as conn:
            conn.execute("UPDATE characters SET gil = ?, updated_at = ? WHERE id = ?",
                         (amount, now_iso(), int(character_id)))
            conn.execute(
                "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
                "VALUES (?, 0, 0, 65535, ?) ON CONFLICT(character_id, container, slot) "
                "DO UPDATE SET item_id = 65535, quantity = excluded.quantity",
                (int(character_id), amount),
            )
        return amount

    def add_item(self, character_id: int, item_id: int, quantity: int = 1) -> dict:
        if quantity <= 0:
            raise ApiError(422, "validation_error", "quantity must be positive")
        item = self.item(item_id)
        stack = int(item["stack"]) if item else 1
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT slot, quantity FROM char_inventory WHERE character_id = ? AND container = 0 "
                "AND item_id = ? ORDER BY slot", (int(character_id), int(item_id))).fetchall()
            for row in rows:
                if int(row["quantity"]) < stack:
                    take = min(stack - int(row["quantity"]), quantity)
                    conn.execute(
                        "UPDATE char_inventory SET quantity = quantity + ? WHERE character_id = ? "
                        "AND container = 0 AND slot = ?",
                        (take, int(character_id), int(row["slot"])))
                    quantity -= take
                    if quantity <= 0:
                        break
            while quantity > 0:
                used = {int(r["slot"]) for r in conn.execute(
                    "SELECT slot FROM char_inventory WHERE character_id = ? AND container = 0",
                    (int(character_id),))}
                slot = next((s for s in range(1, 81) if s not in used), None)
                if slot is None:
                    raise ApiError(409, "inventory_full", "the inventory is full")
                put = min(stack, quantity)
                conn.execute(
                    "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
                    "VALUES (?, 0, ?, ?, ?)",
                    (int(character_id), slot, int(item_id), put))
                quantity -= put
        return {"item_id": int(item_id), "name": item["name"] if item else str(item_id)}

    def award_exp_gil(self, character_id: int, exp: int, gil: int) -> dict:
        """Add experience and gil, level up while the experience covers the next level."""
        exp, gil = max(0, int(exp)), max(0, int(gil))
        levels = 0
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM characters WHERE id = ?", (int(character_id),)).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "character not found")
            level = int(row["main_level"])
            total_exp = int(row["exp"]) + exp
            hp, mp = int(row["hp"]), int(row["mp"])
            while level < 99 and total_exp >= exp_for_level(level):
                total_exp -= exp_for_level(level)
                level += 1
                hp += 20
                mp += 10
                levels += 1
            current_hp = hp if levels else int(row["hp_current"])
            current_mp = mp if levels else int(row["mp_current"])
            total_gil = int(row["gil"]) + gil
            conn.execute(
                "UPDATE characters SET main_level = ?, exp = ?, hp = ?, mp = ?, hp_current = ?, "
                "mp_current = ?, gil = ?, updated_at = ? WHERE id = ?",
                (level, total_exp, hp, mp, current_hp, current_mp,
                 total_gil, now_iso(), int(character_id)),
            )
            conn.execute(
                "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
                "VALUES (?, 0, 0, 65535, ?) ON CONFLICT(character_id, container, slot) "
                "DO UPDATE SET item_id = 65535, quantity = excluded.quantity",
                (int(character_id), total_gil),
            )
        character = self.character(int(character_id))
        character["levels_gained"] = levels
        return character

    def quest_by_key(self, key: str) -> dict | None:
        row = self.db.one("SELECT * FROM quests WHERE quest_key = ?", (key,))
        return dict(row) if row else None

    def quest_for_template(self, template_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM quests WHERE required_template_id = ? LIMIT 1", (int(template_id),))
        return dict(row) if row else None

    def quest_state(self, character_id: int, quest_id: int) -> dict | None:
        row = self.db.one(
            "SELECT q.*, cq.state, cq.progress FROM quests q JOIN char_quests cq ON cq.quest_id = q.id "
            "WHERE cq.character_id = ? AND q.id = ?", (int(character_id), int(quest_id)))
        return dict(row) if row else None

    def start_quest(self, character_id: int, quest_id: int) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO char_quests (character_id, quest_id, state, progress, updated_at) "
                "VALUES (?, ?, 'active', 0, ?)", (int(character_id), int(quest_id), now_iso()))
        return self.quest_state(character_id, quest_id) or {}

    def advance_quest(self, character_id: int, quest_id: int, amount: int = 1) -> dict:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE char_quests SET progress = progress + ?, updated_at = ? "
                "WHERE character_id = ? AND quest_id = ? AND state = 'active'",
                (max(1, int(amount)), now_iso(), int(character_id), int(quest_id)))
        return self.quest_state(character_id, quest_id) or {}

    def complete_quest(self, character_id: int, quest_id: int) -> dict:
        quest = self.db.one("SELECT * FROM quests WHERE id = ?", (int(quest_id),))
        if quest is None:
            raise ApiError(404, "not_found", "quest not found")
        rewarded = False
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT state FROM char_quests WHERE character_id = ? AND quest_id = ?",
                (int(character_id), int(quest_id))).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "quest is not active for this character")
            if row["state"] != "complete":
                conn.execute(
                    "UPDATE char_quests SET state = 'complete', updated_at = ? "
                    "WHERE character_id = ? AND quest_id = ?",
                    (now_iso(), int(character_id), int(quest_id)))
                conn.execute("UPDATE characters SET gil = gil + ? WHERE id = ?",
                             (int(quest["reward_gil"]), int(character_id)))
                gil = conn.execute("SELECT gil FROM characters WHERE id = ?",
                                   (int(character_id),)).fetchone()["gil"]
                conn.execute(
                    "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
                    "VALUES (?, 0, 0, 65535, ?) ON CONFLICT(character_id, container, slot) "
                    "DO UPDATE SET item_id = 65535, quantity = excluded.quantity",
                    (int(character_id), int(gil)))
                rewarded = True
        if rewarded and quest["reward_item_id"] and quest["reward_item_qty"]:
            self.add_item(character_id, int(quest["reward_item_id"]), int(quest["reward_item_qty"]))
        return self.quest_state(character_id, int(quest_id)) or {}

    # --- content -------------------------------------------------------------------------------
    def news(self, limit: int = 10) -> list[dict]:
        rows = self.db.all("SELECT * FROM news ORDER BY published_at DESC, id DESC LIMIT ?", (max(1, min(limit, 50)),))
        return [dict(r) for r in rows]

    def releases(self, platform: str | None = None, channel: str = "stable") -> list[dict]:
        if platform:
            rows = self.db.all(
                "SELECT * FROM releases WHERE platform = ? AND channel = ? ORDER BY published_at DESC",
                (platform, channel),
            )
        else:
            rows = self.db.all(
                "SELECT * FROM releases WHERE channel = ? ORDER BY published_at DESC", (channel,)
            )
        return [dict(r) for r in rows]

    def create_news(self, slug: str, title: str, body: str) -> dict:
        slug = (slug or "").strip().lower()
        if not slug or not title.strip():
            raise ApiError(422, "validation_error", "slug and title are required")
        try:
            self.db.execute(
                "INSERT INTO news (slug, title, body, published_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (slug, title.strip(), body, now_iso(), now_iso()),
            )
        except sqlite3.IntegrityError:
            raise ApiError(409, "slug_taken", "a news post with that slug already exists")
        return dict(self.db.one("SELECT * FROM news WHERE slug = ?", (slug,)))

    def create_release(self, data: dict) -> dict:
        required = ("platform", "version", "url", "sha256")
        missing = [k for k in required if not str(data.get(k) or "").strip()]
        if missing:
            raise ApiError(422, "validation_error", "missing: " + ", ".join(missing))
        sha = str(data["sha256"]).strip().lower()
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ApiError(422, "validation_error", "sha256 must be 64 hexadecimal characters")
        try:
            self.db.execute(
                "INSERT INTO releases (channel, platform, version, url, sha256, size, notes, mandatory, published_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(data.get("channel") or "stable"), str(data["platform"]), str(data["version"]),
                    str(data["url"]), sha, int(data.get("size") or 0), str(data.get("notes") or ""),
                    1 if data.get("mandatory") else 0, now_iso(),
                ),
            )
        except (sqlite3.IntegrityError, ValueError):
            raise ApiError(409, "release_exists", "that release already exists")
        return dict(self.db.one(
            "SELECT * FROM releases WHERE channel = ? AND platform = ? AND version = ?",
            (str(data.get("channel") or "stable"), str(data["platform"]), str(data["version"])),
        ))

    # --- status and settings -------------------------------------------------------------------
    def registration_open(self) -> bool:
        if not self.config.registration_open:
            return False
        return (self.db.setting("registration_open", "1") or "1") != "0"

    def server_name(self) -> str:
        return self.db.setting("server_name", "Fanxi") or "Fanxi"

    def motd(self) -> str:
        return self.db.setting("motd", "Welcome to Fanxi.") or "Welcome to Fanxi."

    def world(self) -> dict:
        row = self.db.one("SELECT * FROM worlds WHERE id = ?", (self.db.setting("world_id", "1") or "1",))
        if row is None:
            row = self.db.one("SELECT * FROM worlds ORDER BY id LIMIT 1")
        base = dict(row) if row else {"id": 1, "name": self.server_name(), "status": "online"}
        server_name = self.server_name()
        return {
            "id": int(base["id"]),
            "name": base.get("name") or server_name,
            "host": self.config.public_host,
            "auth_port": self.config.ports["auth_port"],
            "data_port": self.config.ports["data_port"],
            "view_port": self.config.ports["view_port"],
            "zone_port": self.config.ports["zone_port"],
            "search_port": self.config.ports["search_port"],
            "status": base.get("status", "online"),
        }

    def status(self) -> dict:
        return {
            "name": self.server_name(),
            "version": __version__,
            "time": now_iso(),
            "uptime_seconds": int((utcnow() - datetime.fromisoformat(
                self.started_at.replace("Z", "+00:00"))).total_seconds()),
            "online": self.online_count(),
            "accounts": int(self.db.scalar("SELECT COUNT(*) FROM accounts", (), 0)),
            "characters": int(self.db.scalar("SELECT COUNT(*) FROM characters", (), 0)),
            "registration_open": self.registration_open(),
            "world": self.world(),
            "features": {"game_gateway": bool(self.config.find_huffman_dir())},
        }

    def zones(self) -> dict[int, dict]:
        return {int(r["id"]): dict(r) for r in self.db.all("SELECT * FROM zones")}

    def zone_lines(self) -> dict[int, tuple]:
        result = {}
        for row in self.db.all("SELECT * FROM zone_lines"):
            result[int(row["rect"])] = (int(row["to_zone"]), row["x"], row["y"], row["z"], int(row["rot"]))
        return result

    # --- audit ---------------------------------------------------------------------------------
    def audit(self, account_id: int | None, action: str, detail: str = "", ip: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO audit_log (account_id, action, detail, ip, created_at) VALUES (?, ?, ?, ?, ?)",
            (account_id, action, detail, ip, now_iso()),
        )

    @staticmethod
    def _audit_conn(conn: sqlite3.Connection, account_id: int | None, action: str, detail: str) -> None:
        conn.execute(
            "INSERT INTO audit_log (account_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (account_id, action, detail, now_iso()),
        )
