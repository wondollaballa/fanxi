"""Accounts, characters, sessions and admin operations.

The HTTP layer and the game gateway both call this module; it is the only place that writes
account data. Every method is synchronous and opens its own SQLite connection, so the threaded
HTTP server and the game sockets can use it without sharing a connection.
"""
from __future__ import annotations

import json
import math
import secrets
import sqlite3
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import __version__
from .config import Config
from .db import Database
from .game import augment_gear, augment_stats, design as character_design
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

log = logging.getLogger("fanxi.service")

CHAR_ID_BASE = 0x01000000
DEFAULT_ZONE = 246
# The original starting city for each nation: San d'Oria, Bastok, Windurst.
START_ZONE_BY_NATION = {0: 230, 1: 236, 2: 240}
FAILED_LOGIN_LIMIT = 5
LOCK_MINUTES = 15
STARTER_GIL = 1000
STARTER_ITEMS = ((1, 4112, 2), (2, 16534, 1))  # slot, item id, quantity

# The client's container numbers.  Storage is 2; the wardrobes are 8 and 10-16.
CONTAINER_INVENTORY = 0
CONTAINER_STORAGE = 2
CONTAINER_SLOTS = 81           # 0-80 in the inventory, 1-80 in every storage bag
STORAGE_CAPACITY = CONTAINER_SLOTS - 1
# The hidden general-purpose locker is not a client container; the client's own bag
# capacity is one byte, so 9999 is a server-side limit, not a visible bag size.
LOCKER_CAPACITY = 9999
# Items kept visible in the inventory because the client refuses to use what it cannot
# see.  The bulk lives in char_locker; refill_working_stock() tops these up after use.
WORKING_STOCK = (
    (2971, 99),   # Inoshishinofuda (Utsusemi: Ichi)
    (2972, 99),   # Shikanofuda (Utsusemi: San)
    (2973, 99),   # Chonofuda (Utsusemi: Ni)
    (17023, 12),  # Pet Food Theta (one stack)
    (5411, 3),    # Dawn Mulsum
)
# Permanent bags a job store may sweep.  Temporary items (3) and the recycle bin (17) are
# deliberately left alone: one is about to vanish and the other is a bin, not storage.
# Storage itself (2) is the destination, and the old locker (4) is recovered by migration.
PERMANENT_BAGS = (0, 1, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
# Where a storage grab puts things back: inventory first, then the eight wardrobes, then
# the other permanent bags as a fallback.  Keeping this order means a grabbed set is
# immediately wearable and does not disappear into the Mog Safe.
STORAGE_DESTINATIONS = (0, 8, 10, 11, 12, 13, 14, 15, 16, 1, 9, 5, 6, 7)
# The eight Mog Wardrobes, in the client's order.  These are the bags a job-change tidy
# uses: they are permanent, visible in the equipment window, and can hold worn gear.
WARDROBE_CONTAINERS = (8, 10, 11, 12, 13, 14, 15, 16)
WORKING_STOCK_IDS = frozenset(item_id for item_id, _target in WORKING_STOCK)

# The Data page: values the launcher assigns instead of waiting for gameplay to derive.
GIL_MAX = 2_147_483_647
MASTERY_RANK_MAX = 10
KEY_ITEM_TABLES = 7
JOB_POINT_CAPACITY = 30000
JOB_POINT_CURRENT = 500
JOB_POINT_SPENT = 2100
JOB_COUNT = 22
# The item slots the Armory offers: weapons and ammo use the hand/range slots, armour the
# five body slots, and accessories the seven jewellery slots.
ARMORY_SLOTS = {
    "weapon": ("main", "sub", "ranged", "range"),
    "armor": ("head", "body", "hands", "legs", "feet"),
    "accessory": ("neck", "waist", "ear1", "ear2", "ring1", "ring2", "back"),
    "ammo": ("ammo",),
}


def _like_escape(text: str) -> str:
    """Escape a user's typeahead text for a SQL LIKE ... ESCAPE '\\' clause."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Suggested names for the currency card.  Any name the player types is accepted and kept;
# this list is only the picker the UI shows first.  Gil, merits and limit points have
# their own columns and are deliberately not duplicated here.
RANK_MAX = 10
MOG_GARDEN_MAX = 10
FAME_MAX = 255
EXEMPLAR_PER_LEVEL = 30000
CRAFT_MAX = 100
# /!warp: each character has slots 1-1000.  The number is the target the chat command
# takes, the alias is the friendly name the Warps page edits and the chat command also
# accepts.  Aliases are printable ASCII because the client's chat line is ASCII.
WARP_SLOT_MAX = 1000
WARP_ALIAS_MAX = 40
WARP_PAGE_SIZE = 8
# The client's skill ids 48-57, which is the part of 0x062's crafting block the
# skill menu draws.  58/59 (Rid/Dig) are server-only and stay zero.
CRAFT_SKILLS = (
    (48, "Fishing"),
    (49, "Woodworking"),
    (50, "Smithing"),
    (51, "Goldsmithing"),
    (52, "Clothcraft"),
    (53, "Leathercraft"),
    (54, "Bonecraft"),
    (55, "Alchemy"),
    (56, "Cooking"),
    (57, "Synergy"),
)
FAME_CITIES = (
    "San d'Oria", "Bastok", "Windurst", "Jeuno", "Norg", "Kazham",
    "Selbina", "Mhaura", "Rabao", "Tavnazia", "Adoulin",
)

CURRENCY_CATALOG = (
    "Sparks of Eminence",
    "Unity Accolades",
    "Gallimaufry",
    "Segments",
    "Mog Pell",
    "Bayld",
    "Cruor",
    "Resistance Credits",
    "Imperial Standing",
    "Allied Notes",
    "Conquest Points",
    "Assault Points",
    "Zeni",
    "Jettons",
    "Therion Ichor",
    "Potpourri",
    "Mweya Plasm",
    "Hallmarks",
)


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
        # Set by the game gateway.  It repaints a live character when the HTTP
        # launcher (or a tool sharing this service) changes its design.
        self.design_listener = None

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
            "kind": row.get("kind", "main"),
            "parent_id": row.get("parent_id"),
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
        if account.get("kind") == "sub":
            # Subs have no password. Spend the same work as a real check and answer the same
            # way as a wrong password, so their names cannot be used to probe for subs.
            verify_password(password or "", hash_password("fanxi-dummy-password", iterations=1000))
            self._login_failure(ip)
            raise ApiError(401, "invalid_credentials", "invalid username or password")
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
        if account.get("kind") == "sub":
            # Subs deliberately have no API session of their own; the main launches them.
            raise ApiError(401, "unauthorized", "the session is invalid or has expired")
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

    # --- sub-accounts --------------------------------------------------------------------------
    # A sub-account is owned by exactly one main account. It has no password and no API
    # session: the main's bearer token is the only key, and every route below is scoped by
    # parent_id. This is deliberately not a second kind of login.
    def max_subs(self) -> int:
        return max(0, int(self.config.max_subs))

    def _main_account(self, account_id: int) -> dict:
        account = self.account(account_id)
        if account.get("kind", "main") != "main":
            raise ApiError(404, "not_found", "account not found")
        if account["status"] != "active":
            raise ApiError(403, "account_" + account["status"], "this account may not sign in")
        return account

    def _free_sub_username(self, conn, parent_username: str, start: int) -> str:
        base = (parent_username or "box")[:20]
        for attempt in range(50):
            suffix = "-%d" % (start + attempt) if attempt < 12 else "-" + secrets.token_hex(2)
            candidate = (base[:20 - len(suffix)] + suffix).strip()
            try:
                validate_username(candidate)
            except ValidationError:
                candidate = "box-" + secrets.token_hex(3)
            if conn.execute("SELECT 1 FROM accounts WHERE username = ?", (candidate,)).fetchone() is None:
                return candidate
        raise ApiError(503, "sub_account", "could not allocate a sub-account name")

    @staticmethod
    def _free_character_name(conn) -> str:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for _ in range(100):
            name = "Box" + "".join(secrets.choice(letters) for _ in range(4))
            if conn.execute("SELECT 1 FROM characters WHERE name = ?", (name,)).fetchone() is None:
                return name
        raise ApiError(503, "sub_account", "could not allocate a character name")

    def public_sub_account(self, row) -> dict:
        row = dict(row)
        characters = self.list_characters(int(row["id"]))
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "status": row["status"],
            "parent_id": row.get("parent_id"),
            "created_at": row["created_at"],
            "character": characters[0] if characters else None,
        }

    def sub_accounts(self, parent_id: int) -> list[dict]:
        self._main_account(parent_id)
        rows = self.db.all(
            "SELECT * FROM accounts WHERE parent_id = ? AND kind = 'sub' ORDER BY id", (int(parent_id),)
        )
        return [self.public_sub_account(row) for row in rows]

    def sub_account(self, parent_id: int, sub_id: int) -> dict:
        row = self.db.one(
            "SELECT * FROM accounts WHERE id = ? AND parent_id = ? AND kind = 'sub'",
            (int(sub_id), int(parent_id)),
        )
        if row is None:
            # 404, not 403: another player's sub ids are not enumerable.
            raise ApiError(404, "not_found", "sub-account not found")
        return dict(row)

    def create_sub_account(self, parent_id: int, data: dict, ip: str | None = None) -> dict:
        parent = self._main_account(parent_id)
        limit = self.max_subs()
        if limit <= 0:
            raise ApiError(403, "sub_accounts_disabled", "sub-accounts are disabled on this server")
        source = data.get("character") if isinstance(data.get("character"), dict) else {}
        source = dict(source)
        with self.db.transaction() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE parent_id = ? AND kind = 'sub'", (int(parent["id"]),)
            ).fetchone()[0]
            if count >= limit:
                raise ApiError(409, "sub_account_limit",
                               "this account already has its %d sub-account%s" %
                               (limit, "" if limit == 1 else "s"))
            username = self._free_sub_username(conn, parent["username"], count + 2)
            if not str(source.get("name") or "").strip():
                source["name"] = self._free_character_name(conn)
            fields = self._character_fields(source)
            created = now_iso()
            try:
                cur = conn.execute(
                    "INSERT INTO accounts (username, email, password_hash, status, role, parent_id, kind, "
                    "created_at, updated_at) VALUES (?, NULL, '!sub-account', 'active', 'player', ?, 'sub', ?, ?)",
                    (username, int(parent["id"]), created, created),
                )
            except sqlite3.IntegrityError:
                raise ApiError(409, "username_taken", "that sub-account name is already taken")
            sub_id = int(cur.lastrowid)
            next_id = self._insert_character(conn, sub_id, fields, 1)
            self._audit_conn(conn, int(parent["id"]), "account.sub.create",
                             "%s/%s from %s" % (username, fields["name"], ip or "?"))
            self._audit_conn(conn, sub_id, "account.sub.create", "parent %d" % int(parent["id"]))
        return self.public_sub_account(self.account(sub_id))

    def launch_sub(self, parent_id: int, sub_id: int, character_id: int | None = None,
                   ip: str | None = None) -> dict:
        parent = self._main_account(parent_id)
        sub = self.sub_account(int(parent["id"]), sub_id)
        if sub["status"] != "active":
            raise ApiError(403, "account_" + sub["status"], "this sub-account may not sign in")
        character = self.character_for_account(int(sub["id"]), character_id)
        self.audit(int(parent["id"]), "account.sub.launch",
                   "%s/%s" % (sub["username"], character["name"]), ip)
        return self.launch(sub, int(character["id"]), ip)

    def suspend_sub_account(self, parent_id: int, sub_id: int, *, purge: bool = False) -> dict:
        parent = self._main_account(parent_id)
        sub = self.sub_account(int(parent["id"]), sub_id)
        with self.db.transaction() as conn:
            if purge:
                self._audit_conn(conn, int(parent["id"]), "account.sub.purge",
                                 "%s" % sub["username"])
                conn.execute("DELETE FROM login_tokens WHERE account_id = ?", (int(sub["id"]),))
                conn.execute("DELETE FROM game_sessions WHERE account_id = ?", (int(sub["id"]),))
                conn.execute("DELETE FROM api_sessions WHERE account_id = ?", (int(sub["id"]),))
                conn.execute("DELETE FROM accounts WHERE id = ? AND parent_id = ? AND kind = 'sub'",
                             (int(sub["id"]), int(parent["id"])))
                return {"id": int(sub["id"]), "username": sub["username"], "purged": True}
            conn.execute("UPDATE accounts SET status = 'suspended', updated_at = ? WHERE id = ?",
                         (now_iso(), int(sub["id"])))
            conn.execute("UPDATE api_sessions SET revoked_at = ? WHERE account_id = ? AND revoked_at IS NULL",
                         (now_iso(), int(sub["id"])))
            conn.execute("DELETE FROM login_tokens WHERE account_id = ? AND used_at IS NULL",
                         (int(sub["id"]),))
            conn.execute("DELETE FROM game_sessions WHERE account_id = ?", (int(sub["id"]),))
            self._audit_conn(conn, int(parent["id"]), "account.sub.suspend", sub["username"])
            self._audit_conn(conn, int(sub["id"]), "account.sub.suspend", "parent %d" % int(parent["id"]))
        return self.public_sub_account(self.account(int(sub["id"])))

    def activate_sub_account(self, parent_id: int, sub_id: int) -> dict:
        parent = self._main_account(parent_id)
        sub = self.sub_account(int(parent["id"]), sub_id)
        if sub["status"] == "active":
            return self.public_sub_account(sub)
        if sub["status"] != "suspended":
            raise ApiError(403, "account_" + sub["status"], "this sub-account cannot be reactivated here")
        with self.db.transaction() as conn:
            conn.execute("UPDATE accounts SET status = 'active', updated_at = ? WHERE id = ?",
                         (now_iso(), int(sub["id"])))
            self._audit_conn(conn, int(parent["id"]), "account.sub.activate", sub["username"])
            self._audit_conn(conn, int(sub["id"]), "account.sub.activate", "parent %d" % int(parent["id"]))
        return self.public_sub_account(self.account(int(sub["id"])))

    def create_sub_character(self, parent_id: int, sub_id: int, data: dict) -> dict:
        """Re-create the character of a sub whose character was removed out of band."""
        parent = self._main_account(parent_id)
        sub = self.sub_account(int(parent["id"]), sub_id)
        if sub["status"] != "active":
            raise ApiError(403, "account_" + sub["status"], "this sub-account may not sign in")
        with self.db.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM characters WHERE account_id = ?",
                                 (int(sub["id"]),)).fetchone()[0]
            if count:
                raise ApiError(409, "character_exists", "this sub-account already has a character")
            source = dict(data) if isinstance(data, dict) else {}
            if not str(source.get("name") or "").strip():
                source["name"] = self._free_character_name(conn)
            fields = self._character_fields(source)
            next_id = self._insert_character(conn, int(sub["id"]), fields, 1)
            self._audit_conn(conn, int(parent["id"]), "account.sub.character", fields["name"])
        return self.public_character(self.character(next_id))

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
        blueprint = character_design.from_row(row)
        return {
            "id": row["id"],
            "char_id": row["char_id"],
            "name": row["name"],
            "race": blueprint["race"],
            "face": blueprint["face"],
            "hair": blueprint["hair"],
            "size": blueprint["size"],
            "variant": blueprint["variant"],
            "design": blueprint,
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
            "mastery_rank": int(row.get("mastery_rank") or 0),
            "zone": row["zone"],
            "position": {"x": row["pos_x"], "y": row["pos_y"], "z": row["pos_z"], "rot": row["rot"]},
            "created_at": row["created_at"],
            "last_played_at": row.get("last_played_at"),
        }

    def list_characters(self, account_id: int) -> list[dict]:
        rows = self.db.all("SELECT * FROM characters WHERE account_id = ? ORDER BY slot, id", (account_id,))
        return [self.public_character(r) for r in rows]

    def max_characters(self) -> int:
        """The per-account character cap; 0 means "as many as the player wants"."""
        return max(0, int(self.config.max_characters))

    # --- /!warp --------------------------------------------------------------------------------
    # A warp is a saved zone position with a number and an optional alias.  The chat command
    # owns the rows; the Warps page reads and edits the same ones.  Keeping this here (not in
    # the zone session) means a list survives a relog and the launcher can edit it offline.
    @staticmethod
    def _clean_warp_alias(alias) -> str:
        text = " ".join(str(alias or "").split())
        if len(text) > WARP_ALIAS_MAX:
            raise ApiError(422, "validation_error",
                           "a warp alias is at most %d characters" % WARP_ALIAS_MAX)
        if any(not 32 <= ord(ch) <= 126 for ch in text):
            raise ApiError(422, "validation_error",
                           "a warp alias uses letters, numbers and standard punctuation only")
        return text

    @staticmethod
    def _next_warp_slot(slots) -> int | None:
        used = {int(slot) for slot in slots}
        if not used:
            return 1
        # Auto-increment: one past the highest existing slot, so a mark in a new place
        # does not rename an older camp.  Deleting the top number makes that number
        # available again; a hole in the middle stays a hole until the range fills.
        highest = max(used)
        if highest < WARP_SLOT_MAX:
            return highest + 1
        for slot in range(1, WARP_SLOT_MAX + 1):
            if slot not in used:
                return slot
        return None

    @staticmethod
    def _warp_from_row(row) -> dict:
        data = dict(row)
        return {
            "slot": int(data["slot"]),
            "alias": str(data.get("alias") or ""),
            "zone": int(data["zone"]),
            "zone_name": str(data.get("zone_name") or "Zone %d" % int(data["zone"])),
            "x": float(data["x"]),
            "y": float(data["y"]),
            "z": float(data["z"]),
            "rot": int(data["rot"]),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
        }

    _WARP_SELECT = (
        "SELECT w.slot, w.alias, w.zone, "
        "COALESCE(z.name, 'Zone ' || w.zone) AS zone_name, "
        "w.x, w.y, w.z, w.rot, w.created_at, w.updated_at "
        "FROM char_warps w LEFT JOIN zones z ON z.id = w.zone "
    )

    def warps_for_character(self, character_id: int) -> list[dict]:
        rows = self.db.all(
            self._WARP_SELECT + "WHERE w.character_id = ? ORDER BY w.slot",
            (int(character_id),))
        return [self._warp_from_row(row) for row in rows]

    def warp_payload(self, character_id: int) -> dict:
        """The Warps page's one-round-trip snapshot."""
        character = self.character(int(character_id))
        zone = int(character.get("zone") or 0)
        zone_name = self.db.scalar(
            "SELECT name FROM zones WHERE id = ?", (zone,), None) or "Zone %d" % zone
        warps = self.warps_for_character(int(character_id))
        return {
            "character": {
                "id": int(character["id"]),
                "name": character["name"],
                "zone": zone,
                "zone_name": zone_name,
                "position": {
                    "x": float(character.get("pos_x") or 0.0),
                    "y": float(character.get("pos_y") or 0.0),
                    "z": float(character.get("pos_z") or 0.0),
                    "rot": int(character.get("rot") or 0),
                },
            },
            "warps": warps,
            "limit": WARP_SLOT_MAX,
            "next_slot": self._next_warp_slot([warp["slot"] for warp in warps]),
        }

    def warp(self, character_id: int, slot: int) -> dict:
        row = self.db.one(
            self._WARP_SELECT + "WHERE w.character_id = ? AND w.slot = ?",
            (int(character_id), int(slot)))
        if row is None:
            raise ApiError(404, "not_found", "that warp does not exist")
        return self._warp_from_row(row)

    def find_warps(self, character_id: int, reference) -> list[dict]:
        """Warps matching a slot number, exact alias, or alias prefix (case-insensitive)."""
        text = " ".join(str(reference or "").split())
        if not text:
            return []
        warps = self.warps_for_character(int(character_id))
        if text.lstrip("#").isdigit():
            wanted = int(text.lstrip("#"))
            return [warp for warp in warps if warp["slot"] == wanted]
        folded = text.casefold()
        exact = [warp for warp in warps if warp["alias"] and warp["alias"].casefold() == folded]
        if exact:
            return exact
        return [warp for warp in warps
                if warp["alias"] and warp["alias"].casefold().startswith(folded)]

    def mark_warp(self, character_id: int, alias=None, zone=None, pos=None) -> dict:
        character = self.character(int(character_id))
        alias = self._clean_warp_alias(alias)
        if zone is None:
            zone = int(character.get("zone") or 0)
        if pos is None:
            pos = [character.get("pos_x") or 0.0, character.get("pos_y") or 0.0,
                   character.get("pos_z") or 0.0, character.get("rot") or 0]
        try:
            zone = int(zone)
            x, y, z = (float(pos[0]), float(pos[1]), float(pos[2]))
            rot = int(pos[3]) & 0xFF if len(pos) > 3 else 0
        except (TypeError, ValueError, IndexError):
            raise ApiError(422, "validation_error", "the warp position is not valid")
        if zone <= 0:
            raise ApiError(422, "validation_error", "the warp zone is not valid")
        if not all(math.isfinite(value) for value in (x, y, z)):
            raise ApiError(422, "validation_error", "the warp position is not finite")
        stamp = now_iso()
        with self.db.transaction() as conn:
            occupied = [int(row["slot"]) for row in conn.execute(
                "SELECT slot FROM char_warps WHERE character_id = ?", (int(character_id),))]
            slot = self._next_warp_slot(occupied)
            if slot is None:
                raise ApiError(409, "warp_limit",
                               "all %d warp slots are used; delete one first" % WARP_SLOT_MAX)
            if alias:
                clash = conn.execute(
                    "SELECT slot FROM char_warps WHERE character_id = ? "
                    "AND slot <> ? AND lower(alias) = lower(?)",
                    (int(character_id), slot, alias)).fetchone()
                if clash is not None:
                    raise ApiError(409, "alias_taken",
                                   "warp %d already uses that alias" % int(clash["slot"]))
            try:
                conn.execute(
                    "INSERT INTO char_warps (character_id, slot, alias, zone, x, y, z, rot, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (int(character_id), slot, alias, zone, x, y, z, rot, stamp, stamp))
            except sqlite3.IntegrityError:
                raise ApiError(409, "alias_taken", "another warp already uses that alias")
        return self.warp(int(character_id), slot)

    def rename_warp(self, character_id: int, slot: int, alias=None) -> dict:
        alias = self._clean_warp_alias(alias)
        self.warp(int(character_id), int(slot))  # 404 before touching a missing row
        if alias:
            clash = self.db.one(
                "SELECT slot FROM char_warps WHERE character_id = ? AND slot <> ? "
                "AND lower(alias) = lower(?)",
                (int(character_id), int(slot), alias))
            if clash is not None:
                raise ApiError(409, "alias_taken",
                               "warp %d already uses that alias" % int(clash["slot"]))
        try:
            self.db.execute(
                "UPDATE char_warps SET alias = ?, updated_at = ? "
                "WHERE character_id = ? AND slot = ?",
                (alias, now_iso(), int(character_id), int(slot)))
        except sqlite3.IntegrityError:
            raise ApiError(409, "alias_taken", "another warp already uses that alias")
        return self.warp(int(character_id), int(slot))

    def delete_warp(self, character_id: int, slot: int) -> dict:
        existing = self.warp(int(character_id), int(slot))
        self.db.execute(
            "DELETE FROM char_warps WHERE character_id = ? AND slot = ?",
            (int(character_id), int(slot)))
        return existing

    def account_family_ids(self, account_id: int) -> set[int]:
        """A main account plus the sub-accounts it owns (or a sub's whole family)."""
        row = self.db.one("SELECT id, kind, parent_id FROM accounts WHERE id = ?",
                          (int(account_id),))
        if row is None:
            return set()
        row = dict(row)
        root = int(row["parent_id"]) if row.get("kind") == "sub" and row.get("parent_id") \
            else int(row["id"])
        rows = self.db.all(
            "SELECT id FROM accounts WHERE id = ? OR (parent_id = ? AND kind = 'sub')",
            (root, root))
        ids = {int(item["id"]) for item in rows}
        ids.add(root)
        return ids

    def account_can_manage_character(self, account_id: int, character_id: int) -> bool:
        try:
            row = self.character(int(character_id))
        except ApiError:
            return False
        return int(row["account_id"]) in self.account_family_ids(int(account_id))

    # --- character data page -------------------------------------------------------------------
    def character_data(self, character_id: int) -> dict:
        """Everything the launcher's Data page reads in one round trip.

        Job points and key items are not stored per character in this build: the zone
        session hands every job the same 500/30000/2100 JP block and every character the
        seven permanent key-item tables.  The snapshot says so instead of pretending the
        page can move them.
        """
        character = self.character(int(character_id))
        merits = self.merits_for_character(int(character_id))
        merit_cap = min(255, 127 + max(0, int(merits.get(0x0044, 0))))
        total_home_points = self.db.one(
            "SELECT COUNT(DISTINCT hp_index) AS n FROM home_points")["n"]
        total_guides = self.db.one("SELECT COUNT(*) AS n FROM survival_guides")["n"]
        purchases = [dict(r) for r in self.db.all(
            "SELECT p.id, p.item_id, p.quantity, p.price, p.created_at, "
            "COALESCE(i.name, 'Item ' || p.item_id) AS name, "
            "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.rare, 0) AS rare, "
            "COALESCE(i.ex, 0) AS ex "
            "FROM char_purchases p LEFT JOIN items i ON i.item_id = p.item_id "
            "WHERE p.character_id = ? ORDER BY p.id DESC LIMIT 100",
            (int(character_id),))]
        owned = self.owned_item_ids(character_id, [int(row["item_id"]) for row in purchases])
        for row in purchases:
            row["owned"] = int(row["item_id"]) in owned
        currencies = [dict(r) for r in self.db.all(
            "SELECT name, amount, updated_at FROM char_currency WHERE character_id = ? "
            "ORDER BY name COLLATE NOCASE", (int(character_id),))]
        return {
            "character": {
                "id": int(character["id"]),
                "name": character["name"],
                "main_job": int(character["main_job"]),
                "main_level": int(character["main_level"]),
                "gil": int(character.get("gil") or 0),
                "mastery_rank": int(character.get("mastery_rank") or 0),
            },
            "merits": {"points": int(character.get("merit_points") or 0), "cap": int(merit_cap)},
            "job_points": {
                "all_capped": True,
                "jobs": JOB_COUNT,
                "current": JOB_POINT_CURRENT,
                "capacity": JOB_POINT_CAPACITY,
                "spent": JOB_POINT_SPENT,
            },
            "mastery_rank": int(character.get("mastery_rank") or 0),
            "mastery_rank_max": MASTERY_RANK_MAX,
            "gil": int(character.get("gil") or 0),
            "gil_max": GIL_MAX,
            "home_points": {
                # The registry is keyed by the client menu index.  A few legacy rows use
                # the event index (idx), which is not a Home Point the menu draws, so the
                # count is intersected with the rows the menu actually has.
                "registered": int(self.db.one(
                    "SELECT COUNT(*) AS n FROM char_home_points "
                    "WHERE character_id = ? AND hp_index IN "
                    "(SELECT hp_index FROM home_points)",
                    (int(character_id),))["n"]),
                "total": int(total_home_points),
            },
            "survival_guides": {"total": int(total_guides), "all_available": True},
            "key_items": {"tables": KEY_ITEM_TABLES, "all_granted": True},
            "ranks": {
                "nation": int(character.get("nation") or 0),
                "sandoria": int(character.get("rank_sandoria") or 1),
                "bastok": int(character.get("rank_bastok") or 1),
                "windurst": int(character.get("rank_windurst") or 1),
                "points": int(character.get("rank_points") or 0),
                "rank_max": RANK_MAX,
                "mog_garden_rank": int(character.get("mog_garden_rank") or 0),
                "mog_garden_max": MOG_GARDEN_MAX,
            },
            "fame": self.fame_for_character(int(character_id)),
            "fame_max": FAME_MAX,
            "jobs": self.character_jobs_progress(int(character_id)),
            "exemplar": {
                "points": int(character.get("exemplar_points") or 0),
                "next": EXEMPLAR_PER_LEVEL,
            },
            "crafts": self.crafts_for_character(int(character_id)),
            "craft_max": CRAFT_MAX,
            "trusts": self.trust_summary(),
            "augments": augment_gear.inventory_items(self, int(character_id)),
            "currencies": currencies,
            "currency_catalog": list(CURRENCY_CATALOG),
            "purchases": purchases,
        }

    def set_mastery_rank(self, character_id: int, rank: int) -> int:
        try:
            rank = int(rank)
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "mastery rank must be a number")
        if not 0 <= rank <= MASTERY_RANK_MAX:
            raise ApiError(422, "validation_error",
                           "mastery rank must be between 0 and %d" % MASTERY_RANK_MAX)
        self.db.execute(
            "UPDATE characters SET mastery_rank = ?, updated_at = ? WHERE id = ?",
            (rank, now_iso(), int(character_id)))
        return rank

    def top_off_merits(self, character_id: int) -> int:
        """Set the unspent merit pool to the character's current cap."""
        merits = self.merits_for_character(int(character_id))
        cap = min(255, 127 + max(0, int(merits.get(0x0044, 0))))
        self.set_merit_points(int(character_id), cap)
        return cap

    def top_off_gil(self, character_id: int) -> int:
        self.set_gil(int(character_id), GIL_MAX)
        return GIL_MAX

    def register_all_home_points(self, character_id: int) -> int:
        """Register every Home Point the client's menu knows about."""
        indexes = [int(row["hp_index"]) for row in self.db.all(
            "SELECT DISTINCT hp_index FROM home_points ORDER BY hp_index")]
        stamp = now_iso()
        with self.db.transaction() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO char_home_points (character_id, hp_index, registered_at) "
                "VALUES (?, ?, ?)",
                [(int(character_id), index, stamp) for index in indexes])
        return len(indexes)

    def add_currency(self, character_id: int, name: str, amount: int) -> dict:
        name = " ".join(str(name).split()).strip()
        if not name:
            raise ApiError(422, "validation_error", "currency name is required")
        if len(name) > 48:
            raise ApiError(422, "validation_error", "currency name is at most 48 characters")
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "amount must be a number")
        if amount == 0:
            raise ApiError(422, "validation_error", "amount must not be zero")
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT amount FROM char_currency WHERE character_id = ? AND name = ?",
                (int(character_id), name)).fetchone()
            total = max(0, min(GIL_MAX, int(row["amount"] if row else 0) + amount))
            if row is None:
                conn.execute(
                    "INSERT INTO char_currency (character_id, name, amount, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (int(character_id), name, total, now_iso()))
            else:
                conn.execute(
                    "UPDATE char_currency SET amount = ?, updated_at = ? "
                    "WHERE character_id = ? AND name = ?",
                    (total, now_iso(), int(character_id), name))
        return {"name": name, "amount": total}

    def owned_item_ids(self, character_id: int, item_ids) -> set[int]:
        """The subset of ``item_ids`` held in a permanent bag, storage or the locker."""
        ids = sorted({int(item) for item in item_ids if int(item) > 0})[:400]
        if not ids:
            return set()
        marks = ",".join("?" for _ in ids)
        rows = self.db.all(
            "SELECT DISTINCT item_id FROM ("
            "  SELECT item_id FROM char_inventory WHERE character_id = ? AND quantity > 0"
            "  UNION SELECT item_id FROM char_storage WHERE character_id = ? AND quantity > 0"
            "  UNION SELECT item_id FROM char_locker WHERE character_id = ? AND quantity > 0"
            ") WHERE item_id IN (%s)" % marks,
            (int(character_id), int(character_id), int(character_id), *ids))
        return {int(row["item_id"]) for row in rows}

    def search_items(self, character_id: int, query: str, kind: str | None = None,
                     limit: int = 40) -> list[dict]:
        """Armoury search: equippable items by name, narrowed to a paperdoll kind.

        The catalogue now holds every named equipment item the client knows, so this
        is also the typeahead the Data page queries on each keystroke.  Exact names
        come first, then names that start with the query, then every other substring
        match; within a group the higher-level piece wins.
        """
        slots = ARMORY_SLOTS.get(str(kind or "").strip().lower())
        where = ["equip_slot != ''"]
        args: list = []
        if slots:
            where.append("equip_slot IN (%s)" % ",".join("?" for _ in slots))
            args.extend(slots)
        text = " ".join(str(query or "").split()).strip()
        order_args: list = []
        order = "level DESC, name COLLATE NOCASE"
        if text:
            where.append("name LIKE ? ESCAPE '\\'")
            args.append("%" + _like_escape(text) + "%")
            order = ("CASE WHEN name = ? COLLATE NOCASE THEN 0 "
                     "WHEN name LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END, "
                     "level DESC, name COLLATE NOCASE")
            order_args = [text, _like_escape(text) + "%"]
        if not text and not slots:
            return []
        try:
            limit = max(1, min(100, int(limit)))
        except (TypeError, ValueError):
            limit = 40
        rows = [dict(row) for row in self.db.all(
            "SELECT item_id, name, equip_slot, level, item_level, jobs, rare, ex, "
            "stack, skill, price, base_sell, description "
            "FROM items WHERE " + " AND ".join(where) +
            " ORDER BY " + order + " LIMIT ?", (*args, *order_args, limit))]
        owned = self.owned_item_ids(character_id, [int(row["item_id"]) for row in rows])
        for row in rows:
            item_id = int(row["item_id"])
            row["owned"] = item_id in owned
            row["exclusive"] = bool(int(row.get("rare") or 0) or int(row.get("ex") or 0))
        return rows

    def armory_add(self, character_id: int, item_id: int, quantity: int = 1) -> dict:
        """Buy one catalogue item for a character.

        Rare and Ex pieces are one-per-character in the Armory even though the
        general grant helper only enforces Rare: retail's Ex flag means the item
        cannot be traded, and the Armory should not hand out a second copy by
        accident.  The price is charged before the inventory insert and refunded if
        the insert fails, so a full bag never costs the character gil.
        """
        item = self.item(int(item_id))
        if item is None:
            raise ApiError(404, "not_found", "no item with that id")
        if str(item.get("equip_slot") or "") not in {
                slot for slots in ARMORY_SLOTS.values() for slot in slots}:
            raise ApiError(422, "validation_error",
                           "%s is not armour, an accessory, ammo or a weapon" % item["name"])
        try:
            quantity = max(1, min(99, int(quantity)))
        except (TypeError, ValueError):
            quantity = 1
        unique = bool(int(item.get("rare") or 0) or int(item.get("ex") or 0))
        if unique:
            if quantity != 1:
                raise ApiError(422, "rare_item",
                               "only one copy of a Rare or Ex item can be obtained at a time")
            if self.owns_item(int(character_id), int(item_id)):
                raise ApiError(409, "already_owned",
                               "the character already possesses %s" % item["name"])
        price = max(0, int(item.get("price") or 0)) * quantity
        character = self.character(int(character_id))
        gil = int(character.get("gil") or 0)
        if price > gil:
            raise ApiError(
                422, "insufficient_gil",
                "%s costs %s gil; the character has %s" % (item["name"], f"{price:,}",
                                                           f"{gil:,}"))
        charged = False
        if price:
            self.set_gil(int(character_id), gil - price)
            charged = True
        try:
            added = self.add_item(int(character_id), int(item_id), quantity,
                                  one_per_character=True)
        except Exception:
            if charged:
                try:
                    self.set_gil(int(character_id), gil)
                except Exception:
                    log.exception(
                        "%s could not refund a failed Armory purchase of item %d",
                        character_id, int(item_id))
            raise
        try:
            self.db.execute(
                "INSERT INTO char_purchases (character_id, item_id, quantity, price, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(character_id), int(item_id), quantity, price, now_iso()))
        except Exception:
            # The item is in the bag and the gil is spent; a missing history row is
            # not worth rolling either back.  Log it and keep the purchase.
            log.exception("%s could not record the Armory purchase of item %d",
                          character_id, int(item_id))
        return {"item_id": int(item_id), "name": added["name"], "quantity": quantity,
                "price": price, "purchased": True}

    # --- ranks, fame, jobs, exemplar and crafts ------------------------------------------------
    def character_jobs_progress(self, character_id: int) -> list[dict]:
        """All 22 jobs, with the rows this build has and zeroes for the rest."""
        rows = {int(row["job"]): (int(row["level"]), int(row["master_level"]))
                for row in self.db.all(
                    "SELECT job, level, master_level FROM character_jobs WHERE character_id = ?",
                    (int(character_id),))}
        return [{"job": job,
                 "level": rows.get(job, (0, 0))[0],
                 "master_level": rows.get(job, (0, 0))[1]}
                for job in range(1, 23)]

    def set_all_jobs(self, character_id: int, level: int = 99,
                     master_level: int | None = None) -> int:
        """Unlock every job at *level* (and optionally set its Master Level)."""
        try:
            level = max(1, min(99, int(level)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "level must be a number")
        master = None
        if master_level is not None:
            try:
                master = max(0, min(50, int(master_level)))
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error", "master level must be a number")
        with self.db.transaction() as conn:
            for job in range(1, 23):
                if master is None:
                    conn.execute(
                        "INSERT INTO character_jobs (character_id, job, level, master_level) "
                        "VALUES (?, ?, ?, 0) ON CONFLICT(character_id, job) "
                        "DO UPDATE SET level = excluded.level",
                        (int(character_id), job, level))
                else:
                    conn.execute(
                        "INSERT INTO character_jobs (character_id, job, level, master_level) "
                        "VALUES (?, ?, ?, ?) ON CONFLICT(character_id, job) "
                        "DO UPDATE SET level = excluded.level, master_level = excluded.master_level",
                        (int(character_id), job, level, master))
            conn.execute("UPDATE characters SET main_level = ?, updated_at = ? WHERE id = ?",
                         (level, now_iso(), int(character_id)))
        return level

    def set_job_master_level(self, character_id: int, job: int, level: int) -> int:
        try:
            job, level = int(job), max(0, min(50, int(level)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "job and master level must be numbers")
        if not 1 <= job <= 22:
            raise ApiError(422, "validation_error", "job must be 1..22")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO character_jobs (character_id, job, level, master_level) "
                "VALUES (?, ?, 99, ?) ON CONFLICT(character_id, job) "
                "DO UPDATE SET master_level = excluded.master_level",
                (int(character_id), job, level))
        return level

    def set_all_master_levels(self, character_id: int, level: int) -> int:
        try:
            level = max(0, min(50, int(level)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "master level must be a number")
        with self.db.transaction() as conn:
            for job in range(1, 23):
                conn.execute(
                    "INSERT INTO character_jobs (character_id, job, level, master_level) "
                    "VALUES (?, ?, 99, ?) ON CONFLICT(character_id, job) "
                    "DO UPDATE SET master_level = excluded.master_level",
                    (int(character_id), job, level))
            conn.execute("UPDATE characters SET main_level = 99, updated_at = ? WHERE id = ?",
                         (now_iso(), int(character_id)))
        return level

    def set_exemplar_points(self, character_id: int, points: int) -> int:
        try:
            points = max(0, min(GIL_MAX, int(points)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "points must be a number")
        self.db.execute("UPDATE characters SET exemplar_points = ?, updated_at = ? WHERE id = ?",
                        (points, now_iso(), int(character_id)))
        return points

    def set_mission_rank(self, character_id: int, nation: int, rank: int,
                         points: int | None = None) -> dict:
        columns = {0: "rank_sandoria", 1: "rank_bastok", 2: "rank_windurst"}
        try:
            nation, rank = int(nation), int(rank)
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "nation and rank must be numbers")
        if nation not in columns:
            raise ApiError(422, "validation_error", "nation must be 0, 1 or 2")
        if not 1 <= rank <= RANK_MAX:
            raise ApiError(422, "validation_error", "rank must be 1..%d" % RANK_MAX)
        values = [rank]
        statement = "UPDATE characters SET %s = ?, updated_at = ? WHERE id = ?" % columns[nation]
        values += [now_iso(), int(character_id)]
        if points is not None:
            try:
                points = max(0, min(65535, int(points)))
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error", "points must be a number")
            statement = ("UPDATE characters SET %s = ?, rank_points = ?, updated_at = ? "
                         "WHERE id = ?") % columns[nation]
            values = [rank, points, now_iso(), int(character_id)]
        self.db.execute(statement, tuple(values))
        return {"nation": nation, "rank": rank}

    def set_mog_garden_rank(self, character_id: int, rank: int) -> int:
        try:
            rank = max(0, min(MOG_GARDEN_MAX, int(rank)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "rank must be a number")
        self.db.execute("UPDATE characters SET mog_garden_rank = ?, updated_at = ? WHERE id = ?",
                        (rank, now_iso(), int(character_id)))
        return rank

    def fame_for_character(self, character_id: int) -> list[dict]:
        values = {str(row["city"]): int(row["value"]) for row in self.db.all(
            "SELECT city, value FROM char_fame WHERE character_id = ?", (int(character_id),))}
        return [{"city": city, "value": values.get(city, 0)} for city in FAME_CITIES]

    def set_fame(self, character_id: int, city: str, value: int) -> dict:
        city = str(city or "").strip()
        if city not in FAME_CITIES:
            raise ApiError(422, "validation_error", "unknown city")
        try:
            value = max(0, min(FAME_MAX, int(value)))
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error", "value must be a number")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO char_fame (character_id, city, value) VALUES (?, ?, ?) "
                "ON CONFLICT(character_id, city) DO UPDATE SET value = excluded.value",
                (int(character_id), city, value))
        return {"city": city, "value": value}

    def max_fame(self, character_id: int) -> list[dict]:
        with self.db.transaction() as conn:
            for city in FAME_CITIES:
                conn.execute(
                    "INSERT INTO char_fame (character_id, city, value) VALUES (?, ?, ?) "
                    "ON CONFLICT(character_id, city) DO UPDATE SET value = excluded.value",
                    (int(character_id), city, FAME_MAX))
        return self.fame_for_character(character_id)

    def crafts_for_character(self, character_id: int) -> list[dict]:
        values = {int(row["skill_id"]): int(row["value"]) for row in self.db.all(
            "SELECT skill_id, value FROM char_craft WHERE character_id = ?",
            (int(character_id),))}
        return [{"skill_id": skill_id, "name": name, "value": values.get(skill_id, 0)}
                for skill_id, name in CRAFT_SKILLS]

    def set_craft_skills(self, character_id: int, values: dict) -> list[dict]:
        known = {skill_id for skill_id, _name in CRAFT_SKILLS}
        cleaned: dict[int, int] = {}
        for key, value in (values or {}).items():
            try:
                skill_id, value = int(key), max(0, min(CRAFT_MAX, int(value)))
            except (TypeError, ValueError):
                continue
            if skill_id in known:
                cleaned[skill_id] = value
        if not cleaned:
            raise ApiError(422, "validation_error", "no known crafting skills in the request")
        with self.db.transaction() as conn:
            for skill_id, value in cleaned.items():
                conn.execute(
                    "INSERT INTO char_craft (character_id, skill_id, value) VALUES (?, ?, ?) "
                    "ON CONFLICT(character_id, skill_id) DO UPDATE SET value = excluded.value",
                    (int(character_id), skill_id, value))
        return self.crafts_for_character(character_id)

    def max_crafts(self, character_id: int) -> list[dict]:
        return self.set_craft_skills(
            character_id, {skill_id: CRAFT_MAX for skill_id, _name in CRAFT_SKILLS})

    def trust_summary(self) -> dict:
        row = self.db.one("SELECT COUNT(*) AS n FROM trusts")
        return {
            "spells": int(row["n"]),
            "key_items": "all",
            "summoning": True,
        }

    def _character_fields(self, data: dict) -> dict:
        try:
            return {
                "name": validate_character_name(data.get("name", "")),
                "race": validate_int(data.get("race", 1), "race", 1, 8),
                "face": validate_int(data.get("face", 1), "face", 1, 8),
                "hair": validate_int(data.get("hair", 0), "hair", 0, 1),
                "size": validate_int(data.get("size", 1), "size", 0, 2),
                "nation": validate_int(data.get("nation", 0), "nation", 0, 2),
                "main_job": validate_int(data.get("main_job", 1), "main_job", 1, 22),
                "sub_job": validate_int(data.get("sub_job", 0), "sub_job", 0, 22),
            }
        except ValidationError as exc:
            raise ApiError(422, "validation_error", str(exc))

    def _insert_character(self, conn, account_id: int, fields: dict, slot: int) -> int:
        """Insert one character row and its starter inventory inside the caller's transaction."""
        start_zone = START_ZONE_BY_NATION.get(int(fields["nation"]), DEFAULT_ZONE)
        zone = conn.execute("SELECT * FROM zones WHERE id = ?", (start_zone,)).fetchone()
        if zone is None:
            zone = conn.execute("SELECT * FROM zones WHERE id = ?", (DEFAULT_ZONE,)).fetchone()
        if zone is None:
            zone = conn.execute("SELECT * FROM zones ORDER BY id LIMIT 1").fetchone()
        next_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM characters").fetchone()[0]
        char_id = CHAR_ID_BASE + int(next_id)
        created = now_iso()
        from .game import base_stats
        start_hp = base_stats.base_hp(fields["race"], fields["main_job"], 1, fields["sub_job"], 0)
        start_mp = base_stats.base_mp(fields["race"], fields["main_job"], 1, fields["sub_job"], 0)
        try:
            conn.execute(
                "INSERT INTO characters (id, account_id, slot, char_id, name, race, face, hair, size, nation, "
                "main_job, sub_job, main_level, sub_level, hp, mp, hp_current, mp_current, exp, gil, "
                "speed, zone, pos_x, pos_y, pos_z, rot, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, 0, ?, 50, ?, ?, ?, ?, ?, ?, ?)",
                (
                    next_id, account_id, slot, char_id, fields["name"], fields["race"], fields["face"],
                    fields["hair"], fields["size"], fields["nation"], fields["main_job"], fields["sub_job"],
                    start_hp, start_mp, start_hp, start_mp, STARTER_GIL,
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
        if zone is not None:
            conn.execute(
                "UPDATE characters SET home_zone = ?, home_x = ?, home_y = ?, home_z = ?, "
                "home_rot = ? WHERE id = ?",
                (int(zone["id"]), float(zone["pos_x"]), float(zone["pos_y"]),
                 float(zone["pos_z"]), int(zone["rot"]), next_id))
        conn.execute(
            "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity) "
            "VALUES (?, 0, 0, 65535, ?)", (next_id, STARTER_GIL))
        for item_slot, item_id, quantity in STARTER_ITEMS:
            conn.execute(
                "INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity) "
                "VALUES (?, 0, ?, ?, ?)", (next_id, item_slot, item_id, quantity))
        return next_id

    def create_character(self, account_id: int, data: dict) -> dict:
        fields = self._character_fields(data)
        with self.db.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM characters WHERE account_id = ?", (account_id,)).fetchone()[0]
            limit = self.max_characters()
            if limit and count >= limit:
                raise ApiError(409, "character_limit",
                               "this account already has its %d character%s" % (limit, "" if limit == 1 else "s"))
            next_id = self._insert_character(conn, account_id, fields, count + 1)
            self._audit_conn(conn, account_id, "character.create", fields["name"])
        return self.public_character(self.character(next_id))

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

    def save_design_for_account(self, account_id: int, character_id: int, data: dict) -> dict:
        """Change one character's race/face/hair/size, if this account owns it."""
        row = self.db.one(
            "SELECT id FROM characters WHERE id = ? AND account_id = ?",
            (int(character_id), int(account_id)),
        )
        if row is None:
            raise ApiError(404, "not_found", "character not found")
        return self.save_design(int(character_id), data)

    def save_design(self, character_id: int, data: dict) -> dict:
        """Persist a character design and let a live zone repaint it.

        ``data`` may name only the fields that changed; the rest come from the
        character's current row.  The response is the same public shape the
        character list uses, including the variant number and labels.
        """
        row = self.db.one("SELECT * FROM characters WHERE id = ?", (int(character_id),))
        if row is None:
            raise ApiError(404, "not_found", "character not found")
        current = character_design.from_row(row)

        def pick(name: str):
            value = data.get(name)
            return current[name] if value is None else value

        try:
            blueprint = character_design.design(
                pick("race"), pick("face"), pick("hair"), pick("size"))
        except character_design.DesignError as exc:
            raise ApiError(422, "validation_error", str(exc)) from None
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE characters SET race = ?, face = ?, hair = ?, size = ?, updated_at = ? "
                "WHERE id = ?",
                (blueprint["race"], blueprint["face"], blueprint["hair"],
                 blueprint["size"], now_iso(), int(character_id)),
            )
            self._audit_conn(conn, int(row["account_id"]), "character.design", blueprint["label"])
        updated = self.db.one("SELECT * FROM characters WHERE id = ?", (int(character_id),))
        self._notify_design(int(character_id), blueprint)
        return self.public_character(updated)

    def _notify_design(self, character_id: int, blueprint: dict) -> None:
        """Tell the game gateway to repaint a live character, if it has one."""
        listener = getattr(self, "design_listener", None)
        if not callable(listener):
            return
        try:
            listener(int(character_id), blueprint)
        except Exception:
            log.exception("character %s design listener failed", character_id)

    def save_position(self, character_id: int, zone: int, pos) -> None:
        x, y, z, rot = pos
        self.db.execute(
            "UPDATE characters SET zone = ?, pos_x = ?, pos_y = ?, pos_z = ?, rot = ?, updated_at = ?, "
            "last_played_at = ? WHERE id = ?",
            (int(zone), float(x), float(y), float(z), int(rot), now_iso(), now_iso(), int(character_id)),
        )

    def jobs_for_character(self, character_id: int) -> dict[int, tuple[int, int]]:
        rows = self.db.all(
            "SELECT job, level, master_level FROM character_jobs WHERE character_id = ?", (int(character_id),))
        return {int(r["job"]): (int(r["level"]), int(r["master_level"])) for r in rows}

    def set_moghouse(self, character_id: int, value: int) -> None:
        self.db.execute("UPDATE characters SET moghouse = ?, updated_at = ? WHERE id = ?",
                        (1 if value else 0, now_iso(), int(character_id)))

    def character_record(self, row, server_name: str) -> dict:
        """The character as the game gateway wants it (staticserver's DEFAULT_CHAR shape)."""
        row = dict(row)
        blueprint = character_design.from_row(row)
        return {
            "id": row["id"],
            "moghouse": int(row.get("moghouse", 0) or 0),
            "jobs": self.jobs_for_character(row["id"]),
            "name": row["name"],
            "char_id": row["char_id"],
            "account_id": row["account_id"],
            "race": blueprint["race"],
            "face": blueprint["face"],
            "hair": blueprint["hair"],
            "size": blueprint["size"],
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
            "mastery_rank": int(row.get("mastery_rank") or 0),
            "rank_sandoria": int(row.get("rank_sandoria") or 1),
            "rank_bastok": int(row.get("rank_bastok") or 1),
            "rank_windurst": int(row.get("rank_windurst") or 1),
            "rank_points": int(row.get("rank_points") or 0),
            "mog_garden_rank": int(row.get("mog_garden_rank") or 0),
            "exemplar_points": int(row.get("exemplar_points") or 0),
            "merit_points": int(row.get("merit_points") or 0),
            "limit_points": int(row.get("limit_points") or 0),
            "merit_mode": int(row.get("merit_mode") if row.get("merit_mode") is not None else 1),
            "zone": row["zone"],
            "pos": [row["pos_x"], row["pos_y"], row["pos_z"], row["rot"]],
            # The single Home Point set in Profile: Warp, Warp II, Retrace, !home and a
            # K.O. all read it.  Without these keys every one of them fell back to the
            # current zone and dropped the character at the origin.
            "home_zone": int(row.get("home_zone") or 0),
            "home_x": float(row.get("home_x") or 0.0),
            "home_y": float(row.get("home_y") or 0.0),
            "home_z": float(row.get("home_z") or 0.0),
            "home_rot": int(row.get("home_rot") or 0),
            "head": row["head"],
            "body": row["body"],
            "hands": row["hands"],
            "legs": row["legs"],
            "feet": row["feet"],
            "main": row["main"],
            "sub": row["sub"],
            "ranged": row["ranged"],
            # /lockstyle (0x053): the appearance models stay separate from the gear, so a
            # gear swap changes the stats but not the model the client draws.
            "style_lock": int(row.get("style_lock") or 0),
            "style_head": int(row.get("style_head") or 0),
            "style_body": int(row.get("style_body") or 0),
            "style_hands": int(row.get("style_hands") or 0),
            "style_legs": int(row.get("style_legs") or 0),
            "style_feet": int(row.get("style_feet") or 0),
            "style_main": int(row.get("style_main") or 0),
            "style_sub": int(row.get("style_sub") or 0),
            "style_ranged": int(row.get("style_ranged") or 0),
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
                "INSERT INTO login_tokens (account_id, character_id, token_hash, created_at, expires_at, ip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (account["id"], int(character["id"]), token_hash(token), now_iso(), expires, ip),
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
                "INSERT INTO game_sessions (account_id, character_id, session_hash, created_at, expires_at, ip) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (account["id"], account.get("_launch_character_id"), session_hash, now_iso(),
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
            account = dict(account)
            account["_launch_character_id"] = row["character_id"]
            return account

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

    def game_session_character(self, session_hash: bytes) -> int | None:
        """The character a launch chose for this game session, if it named one."""
        row = self.db.one(
            "SELECT character_id FROM game_sessions WHERE session_hash = ? AND expires_at > ?",
            (session_hash, now_iso()),
        )
        return int(row["character_id"]) if row and row["character_id"] is not None else None

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
            "COALESCE(i.stack, 1) AS stack, COALESCE(i.usable, 0) AS usable, "
            "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.level, 1) AS level, "
            "COALESCE(i.model, 0) AS model, COALESCE(i.slot_mask, 0) AS slot_mask, "
            "COALESCE(i.jobs, 0) AS jobs, COALESCE(i.skill, 0) AS skill, "
            "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex, "
            "COALESCE(st.slip, 0) AS storage_slip, "
            "COALESCE(ci.extra, X'') AS extra "
            "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
            "LEFT JOIN item_storage st ON st.item_id = ci.item_id "
            "WHERE ci.character_id = ? ORDER BY ci.container, ci.slot", (int(character_id),))]

    def set_item_extra(self, character_id: int, container: int, slot: int,
                       extra: bytes) -> bool:
        """Store an item's 24-byte attribute block (the client's augment extdata)."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE char_inventory SET extra = ? "
                "WHERE character_id = ? AND container = ? AND slot = ?",
                (sqlite3.Binary(bytes(extra)), int(character_id), int(container), int(slot)))
            return cursor.rowcount > 0

    def npc_shop(self, zone: int, script: str) -> list[dict]:
        """Merchant stock for an NPC script, from the LandSandBoat shop data."""
        row = self.db.one("SELECT stock FROM npc_shops WHERE zone = ? AND script = ?",
                          (int(zone), str(script)))
        if row is None:
            row = self.db.one("SELECT stock FROM npc_shops WHERE script = ?", (str(script),))
        if row is None:
            return []
        try:
            import json
            stock = json.loads(row["stock"])
        except Exception:
            return []
        return [{"item_id": int(entry["item_id"]), "price": int(entry["price"])}
                for entry in stock if entry.get("item_id")]

    def set_home(self, character_id: int, zone: int, x: float, y: float, z: float, rot: int) -> None:
        self.db.execute(
            "UPDATE characters SET home_zone = ?, home_x = ?, home_y = ?, home_z = ?, "
            "home_rot = ?, updated_at = ? WHERE id = ?",
            (int(zone), float(x), float(y), float(z), int(rot) & 0xFF, now_iso(),
             int(character_id)))

    def survival_guides(self) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT idx, zone, x, y, z, rot FROM survival_guides ORDER BY idx")]

    def home_points(self) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT idx, zone, name, x, y, z, rot, hp_index FROM home_points ORDER BY idx")]

    def home_point(self, index: int) -> dict | None:
        """One Home Point by its client menu index (event 8700 family)."""
        row = self.db.one(
            "SELECT idx, zone, x, y, z, rot FROM home_point_index WHERE idx = ?",
            (int(index),))
        return dict(row) if row else None

    def survival_guide(self, index: int) -> dict | None:
        row = self.db.one(
            "SELECT idx, zone, x, y, z, rot FROM survival_guides WHERE idx = ?",
            (int(index),))
        return dict(row) if row else None

    def equipment(self, character_id: int) -> list[dict]:
        """The gear this character was wearing: one row per equip kind."""
        return [dict(r) for r in self.db.all(
            "SELECT kind, container, slot, item_id FROM char_equip WHERE character_id = ?"
            " ORDER BY kind", (int(character_id),))]

    def equipped_skill_bonuses(self, character_id: int) -> dict[int, int]:
        """Skill id -> total from every equipped item (both dual-wielded weapons count)."""
        rows = self.db.all(
            "SELECT b.skill_id, SUM(b.amount) AS amount FROM char_equip e "
            "JOIN item_skill_bonus b ON b.item_id = e.item_id "
            "WHERE e.character_id = ? GROUP BY b.skill_id", (int(character_id),))
        return {int(row["skill_id"]): int(row["amount"]) for row in rows}

    def equipped_mods(self, character_id: int) -> dict[int, int]:
        """Modifier id -> total from every equipped item, augments included.

        This is where an outfit's Attack, Defense, STR and -- the reason it exists -- its
        physical/magic damage taken comes from.  ``item_mods`` holds every item's base
        modifiers; the per-copy augmentation lives in the item's 24-byte client extdata
        block, so each equipped row is joined back to its inventory copy and run through
        :mod:`augment_stats`.  That is what makes a Rank 30 set's ``"Double Attack"+7%``
        rows reach the attack round, and a cape's five-slot build reach the stat sheet.
        """
        rows = self.db.all(
            "SELECT m.mod_id, SUM(m.value) AS value FROM char_equip e "
            "JOIN item_mods m ON m.item_id = e.item_id "
            "WHERE e.character_id = ? GROUP BY m.mod_id", (int(character_id),))
        mods = {int(row["mod_id"]): int(row["value"]) for row in rows}
        equipped = self.db.all(
            "SELECT e.item_id, COALESCE(i.extra, X'') AS extra FROM char_equip e "
            "LEFT JOIN char_inventory i ON i.character_id = e.character_id "
            "AND i.container = e.container AND i.slot = e.slot "
            "WHERE e.character_id = ?", (int(character_id),))
        for row in equipped:
            try:
                augment_stats.add_item_mods(mods, int(row["item_id"]), row["extra"])
            except (KeyError, TypeError, ValueError):
                # A malformed block must never stop the outfit from loading.
                logging.getLogger("fanxi.stats").debug(
                    "augments unreadable for item %s", row["item_id"], exc_info=True)
        return mods

    def equipped_weapons(self, character_id: int) -> dict[int, dict]:
        """Equip kind -> weapon data (skill, damage, delay, item-level skill, shield size).

        A slot holding something that is not a weapon (a shield in the sub slot, say) has
        no ``item_weapon`` row and comes back with zeroed weapon fields.  A shield carries
        its size in ``shield_size``; anything else has 0 there and is not a shield.
        """
        rows = self.db.all(
            "SELECT e.kind, e.item_id, w.skill, w.dmg, w.delay, w.ilvl_skill, "
            "s.size AS shield_size "
            "FROM char_equip e "
            "LEFT JOIN item_weapon w ON w.item_id = e.item_id "
            "LEFT JOIN item_shield s ON s.item_id = e.item_id "
            "WHERE e.character_id = ?", (int(character_id),))
        return {int(row["kind"]): dict(row) for row in rows}

    def save_equipment(self, character_id: int, equipped: dict) -> None:
        """Replace the stored outfit with the current one (kind -> (container, slot, item))."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM char_equip WHERE character_id = ?", (int(character_id),))
            for kind, (container, slot, item_id) in sorted(equipped.items()):
                conn.execute(
                    "INSERT INTO char_equip (character_id, kind, container, slot, item_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (int(character_id), int(kind), int(container), int(slot), int(item_id)))

    def save_style_lock(self, character_id: int, locked: bool, models: dict[int, int]) -> None:
        """Persist /lockstyle and the appearance models it locked in.

        ``models`` uses the client's equip kinds (0 main, 1 sub, 2 ranged, 4..8 armour).
        Keeping the models on the character row means a relog does not blink back to the
        current gear, and a later /lockstyle off can simply return to the real look.
        """
        columns = {
            0: "style_main", 1: "style_sub", 2: "style_ranged", 4: "style_head",
            5: "style_body", 6: "style_hands", 7: "style_legs", 8: "style_feet",
        }
        values = {name: int(models.get(kind) or 0) for kind, name in columns.items()}
        self.db.execute(
            "UPDATE characters SET style_lock = ?, style_main = ?, style_sub = ?, "
            "style_ranged = ?, style_head = ?, style_body = ?, style_hands = ?, "
            "style_legs = ?, style_feet = ?, updated_at = ? WHERE id = ?",
            (1 if locked else 0, values["style_main"], values["style_sub"],
             values["style_ranged"], values["style_head"], values["style_body"],
             values["style_hands"], values["style_legs"], values["style_feet"],
             now_iso(), int(character_id)),
        )

    def spell_by_name(self, name: str) -> dict | None:
        """Look a spell up by display name, ignoring case and spacing."""
        wanted = "".join(str(name).split()).casefold()
        for row in self.db.all("SELECT * FROM spells ORDER BY id"):
            if "".join(str(row["name"]).split()).casefold() == wanted:
                return dict(row)
        return None

    def spell(self, spell_id: int) -> dict | None:
        """One spell row: name, MP cost, cast time and the client's animation id."""
        row = self.db.one("SELECT * FROM spells WHERE id = ?", (int(spell_id),))
        return dict(row) if row else None

    def trust(self, spell_id: int) -> dict | None:
        """The alter ego a Trust spell calls, or None for an ordinary spell."""
        row = self.db.one("SELECT * FROM trusts WHERE spell_id = ?", (int(spell_id),))
        return dict(row) if row else None

    def hunt_menu(self, zone: int, key: int) -> int | None:
        row = self.db.one("SELECT value FROM hunt_registries WHERE zone = ? AND key = ?",
                          (int(zone), int(key)))
        return int(row["value"]) if row else None

    def home_point_indexes(self, character_id: int) -> set[int]:
        """The Home Points this character has registered."""
        return {int(r[0]) for r in self.db.all(
            "SELECT hp_index FROM char_home_points WHERE character_id = ?",
            (int(character_id),))}

    def weaponskill(self, ws_id: int) -> dict | None:
        row = self.db.one("SELECT id, name, skill, skill_level, element, animation "
                          "FROM weapon_skills WHERE id = ?", (int(ws_id),))
        return dict(row) if row else None

    def weapon_skill_ids(self) -> list[int]:
        """Every weapon skill in the table (the dev/unfiltered list)."""
        return [int(row["id"]) for row in
                self.db.all("SELECT id FROM weapon_skills WHERE id > 0 ORDER BY id")]

    def item_skill(self, item_id: int) -> int:
        """The client's xi.skill type for a weapon item, or 0 for shields/grips/unknown."""
        row = self.db.one("SELECT skill FROM items WHERE item_id = ?", (int(item_id),))
        return int(row["skill"] or 0) if row else 0

    def weapon_skill_ids_for(self, skill_id: int, max_skill: int) -> list[int]:
        """The weapon skills one weapon skill type can use at this skill value.

        Mirrors retail's menu: the weapon type must match, and the skill's requirement
        must be at or below the character's value.  Relic/empyrean/aeonic and other
        quested skills carry skill_level 0; Fanxi has no quest-unlock tracking, so they
        are offered once the weapon skill itself is mastered (350+, the level-99 band).
        A negative skill_level marks a skill that only an equipped item grants (the
        Prime weapons' "Adds weapon skill" line), so the normal gate skips those rows;
        ``equipped_weapon_skill_grants`` supplies them per outfit.
        """
        rows = self.db.all(
            "SELECT id FROM weapon_skills WHERE skill = ? AND skill_level >= 0 AND "
            "((skill_level > 0 AND skill_level <= ?) OR (skill_level = 0 AND ? >= 350)) "
            "ORDER BY skill_level, id",
            (int(skill_id), int(max_skill), int(max_skill)))
        return [int(row["id"]) for row in rows]

    def equipped_weapon_skill_grants(self, character_id: int) -> set[int]:
        """Weapon skill ids the equipped items add with item_mods 355.

        This is retail's ADDS_WEAPONSKILL: a Prime weapon (and the relic/mythic/empyrean
        weapons that carry the same line) lets the character use that one skill while it
        is worn.  The caller filters these against the weapon_skills rows so only the
        item-granted skills enter the advertised menu.
        """
        rows = self.db.all(
            "SELECT DISTINCT m.value AS ws_id FROM char_equip e "
            "JOIN item_mods m ON m.item_id = e.item_id "
            "WHERE e.character_id = ? AND m.mod_id = 355",
            (int(character_id),))
        return {int(row["ws_id"]) for row in rows}

    def weaponskill_by_name(self, name: str) -> dict | None:
        row = self.db.one("SELECT id, name, skill, skill_level, element, animation "
                          "FROM weapon_skills WHERE lower(name) = lower(?) "
                          "ORDER BY id LIMIT 1", (str(name),))
        if row is None:
            row = self.db.one("SELECT id, name, skill, skill_level, element, animation "
                              "FROM weapon_skills WHERE lower(name) LIKE lower(?) "
                              "ORDER BY id LIMIT 1", ("%" + str(name) + "%",))
        return dict(row) if row else None

    def job_ability(self, ability_id: int) -> dict | None:
        """One job ability row: job/level gates, recast and the client animation id."""
        row = self.db.one("SELECT * FROM job_abilities WHERE id = ?", (int(ability_id),))
        return dict(row) if row else None

    def job_abilities(self, main_job: int, main_level: int,
                      sub_job: int = 0, sub_level: int = 0) -> list[dict]:
        """The main job's learned abilities plus the sub job's, as full rows.

        A two-hour ability has level 0, so the sub-job clause requires level > 0.  Merit
        abilities carry the job they belong to and a level, so they follow the same rule.
        Main-only abilities (add_type 4) are not inherited by a sub job.
        """
        rows = self.db.all(
            "SELECT * FROM job_abilities WHERE "
            " (job = ? AND level <= ?) OR "
            " (job = ? AND level > 0 AND level <= ? AND (add_type & 4) = 0) "
            "ORDER BY id",
            (int(main_job), int(main_level), int(sub_job or 0), int(sub_level or 0)))
        return [dict(row) for row in rows]

    def job_ability_ids(self, main_job: int, main_level: int,
                        sub_job: int = 0, sub_level: int = 0) -> list[int]:
        """The 0x0AC Job Abilities block: ids only, for the command bitmap."""
        return [int(row["id"]) for row in
                self.job_abilities(main_job, main_level, sub_job, sub_level)]

    def job_ability_by_name(self, name: str) -> dict | None:
        row = self.db.one("SELECT * FROM job_abilities WHERE lower(name) = lower(?) "
                          "ORDER BY id LIMIT 1", (str(name),))
        if row is None:
            row = self.db.one("SELECT * FROM job_abilities WHERE lower(name) LIKE lower(?) "
                              "ORDER BY id LIMIT 1", ("%" + str(name) + "%",))
        return dict(row) if row else None

    def home_point_in_zone(self, character_id: int, zone: int) -> dict | None:
        """The registered Home Point this character can warp to in a zone."""
        row = self.db.one(
            "SELECT hp.zone, hp.name, hp.x, hp.y, hp.z, hp.rot "
            "FROM char_home_points chp JOIN home_points hp ON hp.hp_index = chp.hp_index "
            "WHERE chp.character_id = ? AND hp.zone = ? ORDER BY hp.idx LIMIT 1",
            (int(character_id), int(zone)))
        return dict(row) if row else None

    def last_home_point(self, character_id: int) -> dict | None:
        """The most recently registered Home Point anywhere -- Warp II's destination."""
        row = self.db.one(
            "SELECT hp.zone, hp.name, hp.x, hp.y, hp.z, hp.rot "
            "FROM char_home_points chp JOIN home_points hp ON hp.hp_index = chp.hp_index "
            "WHERE chp.character_id = ? "
            "ORDER BY chp.registered_at DESC, chp.hp_index DESC LIMIT 1",
            (int(character_id),))
        return dict(row) if row else None

    def npc_event(self, zone: int, script: str) -> tuple[int, list[int]] | None:
        """The client dialogue event for an NPC, from the LandSandBoat scripts."""
        import json
        import re
        key = re.sub(r"[^a-z0-9]", "", str(script or "").casefold())
        if not key:
            return None
        row = self.db.one(
            "SELECT event_id, params FROM npc_events WHERE zone = ? AND script_key = ?",
            (int(zone), key))
        if row is None:
            return None
        try:
            params = [int(v) for v in json.loads(row["params"] or "[]")][:8]
        except Exception:
            params = []
        return int(row["event_id"]), params

    def npc_message(self, zone: int, script: str) -> tuple[int, list[int]] | None:
        """A zone-text message id for an NPC (the client renders the actual text)."""
        import json
        import re
        key = re.sub(r"[^a-z0-9]", "", str(script or "").casefold())
        if not key:
            return None
        row = self.db.one(
            "SELECT text_id, params FROM npc_messages WHERE zone = ? AND script_key = ?",
            (int(zone), key))
        if row is None:
            return None
        try:
            params = [int(v) for v in json.loads(row["params"] or "[]")][:4]
        except Exception:
            params = []
        return int(row["text_id"]), params

    def register_home_point(self, character_id: int, index: int) -> bool:
        """Record a Home Point; returns True when it was new."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO char_home_points (character_id, hp_index, registered_at) "
                "VALUES (?, ?, ?)", (int(character_id), int(index), now_iso()))
            return cursor.rowcount > 0

    def item(self, item_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM items WHERE item_id = ?", (int(item_id),))
        return dict(row) if row else None

    def food_effect(self, item_id: int) -> dict | None:
        """The duration, modifiers and eating animation for an edible item, or None."""
        row = self.db.one(
            "SELECT item_id, duration, mods, animation FROM food_effects WHERE item_id = ?",
            (int(item_id),))
        if row is None:
            return None
        try:
            mods = {int(key): int(value)
                    for key, value in json.loads(row["mods"]).items()}
        except (TypeError, ValueError):
            mods = {}
        return {"item_id": int(row["item_id"]), "duration": int(row["duration"]),
                "mods": mods, "animation": int(row["animation"] or 0)}

    def save_vitals(self, character_id: int, hp: int, mp: int) -> None:
        self.db.execute(
            "UPDATE characters SET hp_current = ?, mp_current = ?, updated_at = ? WHERE id = ?",
            (max(0, int(hp)), max(0, int(mp)), now_iso(), int(character_id)),
        )

    def set_max_vitals(self, character_id: int, hp: int, mp: int, hp_current: int,
                       mp_current: int) -> None:
        """Persist max HP/MP after a merit changes them, along with the current values."""
        self.db.execute(
            "UPDATE characters SET hp = ?, mp = ?, hp_current = ?, mp_current = ?, "
            "updated_at = ? WHERE id = ?",
            (max(1, int(hp)), max(0, int(mp)), max(0, int(hp_current)), max(0, int(mp_current)),
             now_iso(), int(character_id)),
        )

    def merits_for_character(self, character_id: int) -> dict[int, int]:
        """Merit id -> upgrades bought, the entries the client's 0x08C carries."""
        return {int(row["merit_id"]): int(row["upgrades"]) for row in self.db.all(
            "SELECT merit_id, upgrades FROM char_merits WHERE character_id = ?",
            (int(character_id),))}

    def save_merit(self, character_id: int, merit_id: int, upgrades: int) -> None:
        with self.db.transaction() as conn:
            if int(upgrades) <= 0:
                conn.execute(
                    "DELETE FROM char_merits WHERE character_id = ? AND merit_id = ?",
                    (int(character_id), int(merit_id)))
            else:
                conn.execute(
                    "INSERT INTO char_merits (character_id, merit_id, upgrades) VALUES (?, ?, ?) "
                    "ON CONFLICT(character_id, merit_id) DO UPDATE SET upgrades = excluded.upgrades",
                    (int(character_id), int(merit_id), int(upgrades)))

    def set_merit_points(self, character_id: int, points: int) -> None:
        self.db.execute(
            "UPDATE characters SET merit_points = ?, updated_at = ? WHERE id = ?",
            (max(0, min(255, int(points))), now_iso(), int(character_id)))

    def set_merit_mode(self, character_id: int, mode: int) -> None:
        self.db.execute(
            "UPDATE characters SET merit_mode = ?, updated_at = ? WHERE id = ?",
            (1 if int(mode) else 0, now_iso(), int(character_id)))

    def move_item(self, character_id: int, from_container: int, from_slot: int,
                  to_container: int, to_slot: int, quantity: int) -> bool:
        """Move (or split) one stack between containers; the client sends 0x029."""
        with self.db.transaction() as conn:
            src = conn.execute(
                "SELECT item_id, quantity FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), int(from_container), int(from_slot))).fetchone()
            if src is None:
                return False
            item_id, qty = int(src["item_id"]), int(src["quantity"])
            if item_id == 65535 or quantity <= 0 or quantity > qty:
                return False
            stack = int(self.db.scalar("SELECT COALESCE(stack, 1) FROM items WHERE item_id = ?",
                                       (item_id,), 1) or 1)
            dst = conn.execute(
                "SELECT item_id, quantity FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), int(to_container), int(to_slot))).fetchone()
            # The client names a slot for a specific move, but sends 82 (and up) for "whichever
            # slot is free"; 0-80 is the container's own numbering.
            target = int(to_slot) if 0 <= int(to_slot) <= 80 else -1
            if target < 0:
                taken = {int(r["slot"]) for r in conn.execute(
                    "SELECT slot FROM char_inventory WHERE character_id = ? AND container = ?",
                    (int(character_id), int(to_container)))}
                # Slot 0 of a storage container never renders in the client (only the
                # inventory uses it, for gil), so hand out slots from 1 there.
                first = 0 if int(to_container) == 0 else 1
                target = next((slot for slot in range(first, 81) if slot not in taken), -1)
                if target < 0:
                    return False
                dst = None
            if dst is not None:
                if int(dst["item_id"]) == item_id and int(dst["quantity"]) < stack:
                    room = stack - int(dst["quantity"])
                    move = min(quantity, room)
                    conn.execute(
                        "UPDATE char_inventory SET quantity = quantity + ? WHERE character_id = ? AND container = ? AND slot = ?",
                        (move, int(character_id), int(to_container), target))
                    quantity -= move
                    if quantity <= 0:
                        conn.execute(
                            "DELETE FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                            (int(character_id), int(from_container), int(from_slot)))
                        return True
                else:
                    # occupied by something else: take the first free slot instead
                    taken = {int(r["slot"]) for r in conn.execute(
                        "SELECT slot FROM char_inventory WHERE character_id = ? AND container = ?",
                        (int(character_id), int(to_container)))}
                    target = next((s for s in range(81) if s not in taken), -1)
                    if target < 0:
                        return False
            if quantity == qty:
                conn.execute(
                    "UPDATE char_inventory SET container = ?, slot = ? WHERE character_id = ? AND container = ? AND slot = ?",
                    (int(to_container), int(target), int(character_id), int(from_container), int(from_slot)))
            else:
                conn.execute(
                    "UPDATE char_inventory SET quantity = quantity - ? WHERE character_id = ? AND container = ? AND slot = ?",
                    (quantity, int(character_id), int(from_container), int(from_slot)))
                conn.execute(
                    "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(character_id, container, slot) DO UPDATE SET item_id = excluded.item_id, quantity = excluded.quantity",
                    (int(character_id), int(to_container), int(target), item_id, quantity))
            return True

    def stack_container(self, character_id: int, container: int) -> list[dict]:
        """Merge partial stacks of one item in a container (C2S 0x03A, the client's sort).

        The client decides the visual order; only the server can combine two partial stacks
        and empty a slot.  Slots merge upward into the lowest-numbered slot of the same item,
        so a 60 and a 50 stack of a 99-item become 99 and 11, not two unsorted piles.  Gil
        (container 0, slot 0, item 65535) is left alone, and rows with different augment
        extdata are not merged even when the item id matches.

        Returns the final state of every slot that changed, with item id 0 for a slot that
        the merge emptied, so the zone can send the matching 0x020 updates.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT ci.slot, ci.item_id, ci.quantity, COALESCE(i.stack, 1) AS stack, "
                "COALESCE(ci.extra, X'') AS extra "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container = ? ORDER BY ci.slot",
                (int(character_id), int(container))).fetchall()
            slots = {
                int(row["slot"]): [int(row["item_id"]), int(row["quantity"]),
                                   max(1, int(row["stack"] or 1)),
                                   bytes(row["extra"] or b"")]
                for row in rows
            }
            order = sorted(slots)
            changed: dict[int, tuple[int, int, bytes]] = {}
            for index, slot in enumerate(order):
                src = slots.get(slot)
                if src is None or src[0] == 65535 or src[1] >= src[2]:
                    continue
                for other in order[index + 1:]:
                    dst = slots.get(other)
                    if dst is None or dst[0] != src[0] or dst[3] != src[3]:
                        continue
                    room = src[2] - src[1]
                    if room <= 0:
                        break
                    move = min(room, dst[1])
                    src[1] += move
                    dst[1] -= move
                    changed[slot] = (src[0], src[1], src[3])
                    if dst[1] <= 0:
                        conn.execute(
                            "DELETE FROM char_inventory WHERE character_id = ? "
                            "AND container = ? AND slot = ?",
                            (int(character_id), int(container), int(other)))
                        del slots[other]
                        changed[other] = (0, 0, b"")
                    else:
                        conn.execute(
                            "UPDATE char_inventory SET quantity = ? WHERE character_id = ? "
                            "AND container = ? AND slot = ?",
                            (dst[1], int(character_id), int(container), int(other)))
                        changed[other] = (dst[0], dst[1], dst[3])
                    if src[1] >= src[2]:
                        break
                if slot in changed:
                    conn.execute(
                        "UPDATE char_inventory SET quantity = ? WHERE character_id = ? "
                        "AND container = ? AND slot = ?",
                        (src[1], int(character_id), int(container), int(slot)))
        return [{"slot": slot, "item_id": item_id, "quantity": quantity, "extra": extra}
                for slot, (item_id, quantity, extra) in sorted(changed.items())]

    def store_job_in_storage(self, character_id: int, job: int) -> dict:
        """Move every storable, job-exclusive item from the permanent bags onto its slip.

        The item is deleted from ``char_inventory`` and recorded in ``char_storage``, the
        same server-side record a Porter Moogle keeps.  It will not appear in any bag (not
        even the client's Storage container) until it is grabbed again.  Worn pieces stay
        equipped; job gear with no slip is counted and left in the bags.
        """
        job = int(job)
        if not 1 <= job <= 22:
            raise ValueError("job must be 1..22")
        mask = 1 << (job - 1)
        with self.db.transaction() as conn:
            placeholders = ",".join("?" for _ in PERMANENT_BAGS)
            rows = conn.execute(
                "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(st.slip, 0) AS storage_slip "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "LEFT JOIN item_storage st ON st.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container IN (%s) "
                "ORDER BY ci.container, ci.slot" % placeholders,
                (int(character_id), *PERMANENT_BAGS)).fetchall()
            equipped = {(int(row["container"]), int(row["slot"])) for row in conn.execute(
                "SELECT container, slot FROM char_equip WHERE character_id = ?",
                (int(character_id),))}
            moved: list[dict] = []
            equipped_left = 0
            unstoreable_items: list[str] = []
            for row in rows:
                if int(row["jobs"] or 0) != mask:
                    continue
                source = (int(row["container"]), int(row["slot"]))
                slip = int(row["storage_slip"] or 0)
                if not slip:
                    unstoreable_items.append(str(row["name"] or "Item"))
                    continue
                if source in equipped:
                    equipped_left += 1
                    continue
                item_id = int(row["item_id"])
                quantity = int(row["quantity"])
                conn.execute(
                    "DELETE FROM char_inventory WHERE character_id = ? "
                    "AND container = ? AND slot = ?",
                    (int(character_id), source[0], source[1]))
                conn.execute(
                    "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(character_id, item_id) "
                    "DO UPDATE SET quantity = quantity + excluded.quantity",
                    (int(character_id), item_id, quantity, slip))
                moved.append({
                    "from_container": source[0], "from_slot": source[1],
                    "item_id": item_id, "quantity": quantity,
                    "name": str(row["name"] or "Item"), "slip": slip,
                })
            stored = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM char_storage WHERE character_id = ?",
                (int(character_id),)).fetchone()[0]
            slip_counts = {int(row["slip"]): int(row["quantity"]) for row in conn.execute(
                "SELECT slip, SUM(quantity) AS quantity FROM char_storage "
                "WHERE character_id = ? GROUP BY slip ORDER BY slip",
                (int(character_id),))}
            return {"moved": moved, "equipped": equipped_left,
                    "unstoreable": len(unstoreable_items),
                    "unstoreable_items": unstoreable_items,
                    "storage_count": int(stored), "slips": slip_counts}

    def take_from_storage(self, character_id: int, job: int | None = None) -> dict:
        """Move slip-stored items back to the inventory first, then the wardrobes.

        ``job`` limits the return to that job's exclusive gear; ``None`` returns everything.
        Items are placed in the first free slot, so a grabbed set is immediately usable.
        Anything that finds no room stays on its slip and is reported.
        """
        if job is not None and not 1 <= int(job) <= 22:
            raise ValueError("job must be 1..22")
        mask = None if job is None else 1 << (int(job) - 1)
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT cs.item_id, cs.quantity, cs.slip, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(i.stack, 1) AS stack "
                "FROM char_storage cs LEFT JOIN items i ON i.item_id = cs.item_id "
                "WHERE cs.character_id = ? ORDER BY cs.slip, cs.item_id",
                (int(character_id),)).fetchall()
            placeholders = ",".join("?" for _ in STORAGE_DESTINATIONS)
            occupied = {container: set() for container in STORAGE_DESTINATIONS}
            for row in conn.execute(
                    "SELECT container, slot FROM char_inventory WHERE character_id = ? "
                    "AND container IN (%s)" % placeholders,
                    (int(character_id), *STORAGE_DESTINATIONS)):
                occupied[int(row["container"])].add(int(row["slot"]))

            def next_free(container: int) -> int | None:
                first = 0 if container == CONTAINER_INVENTORY else 1
                for slot in range(first, CONTAINER_SLOTS):
                    if slot not in occupied[container]:
                        occupied[container].add(slot)
                        return slot
                return None

            moved: list[dict] = []
            skipped_job = 0
            remaining = 0
            for row in rows:
                if mask is not None and int(row["jobs"] or 0) != mask:
                    skipped_job += 1
                    continue
                item_id = int(row["item_id"])
                left = int(row["quantity"])
                stack = max(1, int(row["stack"] or 1))
                while left > 0:
                    target_container = target_slot = None
                    for container in STORAGE_DESTINATIONS:
                        target_slot = next_free(container)
                        if target_slot is not None:
                            target_container = container
                            break
                    if target_container is None:
                        break
                    put = min(left, stack)
                    conn.execute(
                        "INSERT INTO char_inventory "
                        "(character_id, container, slot, item_id, quantity) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(character_id, container, slot) "
                        "DO UPDATE SET item_id = excluded.item_id, quantity = excluded.quantity",
                        (int(character_id), target_container, target_slot, item_id, put))
                    moved.append({
                        "to_container": target_container, "to_slot": target_slot,
                        "item_id": item_id, "quantity": put,
                        "name": str(row["name"] or "Item"),
                        "slip": int(row["slip"]),
                    })
                    left -= put
                if left:
                    conn.execute(
                        "UPDATE char_storage SET quantity = ? "
                        "WHERE character_id = ? AND item_id = ?",
                        (left, int(character_id), item_id))
                    remaining += left
                else:
                    conn.execute(
                        "DELETE FROM char_storage WHERE character_id = ? AND item_id = ?",
                        (int(character_id), item_id))
            stored = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM char_storage WHERE character_id = ?",
                (int(character_id),)).fetchone()[0]
            return {"moved": moved, "skipped_job": skipped_job,
                    "remaining": remaining, "storage_count": int(stored)}

    def sort_inventory_into_wardrobes(self, character_id: int,
                                      keep_jobs: int | None = None) -> dict:
        """Move loose inventory items into free Mog Wardrobe slots.

        ``keep_jobs`` is a job bitmask: gear whose ``jobs`` column is 0 (every job) or
        includes that job stays in the inventory, so a freshly pulled set can be worn
        before the leftovers are put away.  Working stock and equipped pieces always
        stay visible, and gil is never moved.  Whole stacks move together and keep their
        augment extdata because the row itself is relocated.
        """
        with self.db.transaction() as conn:
            placeholders = ",".join("?" for _ in WARDROBE_CONTAINERS)
            occupied = {container: set() for container in WARDROBE_CONTAINERS}
            for row in conn.execute(
                    "SELECT container, slot FROM char_inventory WHERE character_id = ? "
                    "AND container IN (%s)" % placeholders,
                    (int(character_id), *WARDROBE_CONTAINERS)):
                occupied[int(row["container"])].add(int(row["slot"]))
            equipped = {(int(row["container"]), int(row["slot"]))
                        for row in conn.execute(
                            "SELECT container, slot FROM char_equip WHERE character_id = ?",
                            (int(character_id),))}
            rows = conn.execute(
                "SELECT ci.slot, ci.item_id, ci.quantity, COALESCE(ci.extra, X'') AS extra, "
                "COALESCE(i.jobs, 0) AS jobs "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container = 0 AND ci.slot > 0 "
                "ORDER BY ci.slot", (int(character_id),)).fetchall()
            moved: list[dict] = []
            kept = 0
            remaining = 0
            for row in rows:
                slot = int(row["slot"])
                item_id = int(row["item_id"])
                quantity = int(row["quantity"])
                if item_id == 65535:
                    continue
                if (0, slot) in equipped or item_id in WORKING_STOCK_IDS:
                    kept += 1
                    continue
                if keep_jobs is not None:
                    jobs = int(row["jobs"] or 0)
                    if jobs == 0 or (jobs & int(keep_jobs)):
                        kept += 1
                        continue
                target = None
                for container in WARDROBE_CONTAINERS:
                    free = next((candidate for candidate in range(1, CONTAINER_SLOTS)
                                 if candidate not in occupied[container]), None)
                    if free is not None:
                        occupied[container].add(free)
                        target = (container, free)
                        break
                if target is None:
                    remaining += quantity
                    continue
                conn.execute(
                    "UPDATE char_inventory SET container = ?, slot = ? "
                    "WHERE character_id = ? AND container = 0 AND slot = ?",
                    (target[0], target[1], int(character_id), slot))
                moved.append({
                    "from_container": 0, "from_slot": slot,
                    "to_container": target[0], "to_slot": target[1],
                    "item_id": item_id, "quantity": quantity,
                    "extra": bytes(row["extra"] or b""),
                })
            free_slots = sum(CONTAINER_SLOTS - 1 - len(occupied[container])
                             for container in WARDROBE_CONTAINERS)
            return {"moved": moved, "kept": kept, "remaining": remaining,
                    "free": free_slots}

    def storage_summary(self, character_id: int) -> dict[int, int]:
        """Slip number -> stored quantity, for !storage with no arguments."""
        return {int(row["slip"]): int(row["quantity"]) for row in self.db.all(
            "SELECT slip, SUM(quantity) AS quantity FROM char_storage "
            "WHERE character_id = ? GROUP BY slip ORDER BY slip", (int(character_id),))}

    @staticmethod
    def _locker_matches(row, selector: dict) -> bool:
        """Does a bag/locker row match ``all``, a slot, the materials catch-all, or a name?"""
        kind = str(selector.get("kind") or "")
        if kind == "all":
            return True
        item_id = int(row["item_id"])
        slot = str(row["equip_slot"] or "")
        if kind == "slot":
            wanted = str(selector.get("slot") or "")
            if wanted == "ear":
                return slot in ("ear1", "ear2")
            if wanted == "ring":
                return slot in ("ring1", "ring2")
            return slot == wanted
        if kind == "materials":
            # Empty equip_slot is the catalogue's "not wearable": potions, ammo
            # ingredients, crafting materials and similar consumables.
            return item_id != 65535 and not slot
        if kind == "name":
            text = str(selector.get("text") or "").strip().casefold()
            return bool(text) and text in str(row["name"] or "").casefold()
        return False

    def store_in_locker(self, character_id: int, selector: dict) -> dict:
        """Move matching items from every permanent bag into the hidden 9999-item locker.

        The locker is not a client container: the item's char_inventory row is deleted, so
        it disappears from every bag until ``take_from_locker`` puts it back.  Equipped
        pieces stay on, and the 9999 limit is the sum of stored quantities.
        """
        with self.db.transaction() as conn:
            placeholders = ",".join("?" for _ in PERMANENT_BAGS)
            rows = conn.execute(
                "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.equip_slot, '') AS equip_slot "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container IN (%s) "
                "ORDER BY ci.container, ci.slot" % placeholders,
                (int(character_id), *PERMANENT_BAGS)).fetchall()
            equipped = {(int(row["container"]), int(row["slot"])) for row in conn.execute(
                "SELECT container, slot FROM char_equip WHERE character_id = ?",
                (int(character_id),))}
            current = int(conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM char_locker WHERE character_id = ?",
                (int(character_id),)).fetchone()[0])
            moved: list[dict] = []
            equipped_left = 0
            remaining = 0
            for row in rows:
                if int(row["item_id"]) == 65535:
                    continue
                if not self._locker_matches(row, selector):
                    continue
                source = (int(row["container"]), int(row["slot"]))
                if source in equipped:
                    equipped_left += 1
                    continue
                item_id = int(row["item_id"])
                quantity = int(row["quantity"])
                if current + quantity > LOCKER_CAPACITY:
                    remaining += quantity
                    continue
                conn.execute(
                    "DELETE FROM char_inventory WHERE character_id = ? "
                    "AND container = ? AND slot = ?",
                    (int(character_id), source[0], source[1]))
                conn.execute(
                    "INSERT INTO char_locker (character_id, item_id, quantity) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(character_id, item_id) "
                    "DO UPDATE SET quantity = quantity + excluded.quantity",
                    (int(character_id), item_id, quantity))
                current += quantity
                moved.append({
                    "from_container": source[0], "from_slot": source[1],
                    "item_id": item_id, "quantity": quantity,
                    "name": str(row["name"] or "Item"),
                })
            return {"moved": moved, "equipped": equipped_left, "remaining": remaining,
                    "locker_count": current, "locker_capacity": LOCKER_CAPACITY}

    def take_from_locker(self, character_id: int, selector: dict,
                         limit: int | None = None) -> dict:
        """Move matching locker items back to the inventory first, then the wardrobes.

        ``limit`` caps the total quantity returned, so a 99-jug stack can be taken one
        stack at a time instead of filling the bag.
        """
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT cl.item_id, cl.quantity, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.stack, 1) AS stack "
                "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
                "WHERE cl.character_id = ? ORDER BY cl.item_id",
                (int(character_id),)).fetchall()
            placeholders = ",".join("?" for _ in STORAGE_DESTINATIONS)
            occupied = {container: set() for container in STORAGE_DESTINATIONS}
            for row in conn.execute(
                    "SELECT container, slot FROM char_inventory WHERE character_id = ? "
                    "AND container IN (%s)" % placeholders,
                    (int(character_id), *STORAGE_DESTINATIONS)):
                occupied[int(row["container"])].add(int(row["slot"]))

            def next_free(container: int) -> int | None:
                first = 0 if container == CONTAINER_INVENTORY else 1
                for slot in range(first, CONTAINER_SLOTS):
                    if slot not in occupied[container]:
                        occupied[container].add(slot)
                        return slot
                return None

            moved: list[dict] = []
            skipped = 0
            remaining = 0
            for row in rows:
                if not self._locker_matches(row, selector):
                    skipped += 1
                    continue
                if limit is not None and limit <= 0:
                    break
                item_id = int(row["item_id"])
                left = int(row["quantity"])
                stack = max(1, int(row["stack"] or 1))
                take = left if limit is None else min(left, limit)
                moved_qty = 0
                while moved_qty < take:
                    target_container = target_slot = None
                    for container in STORAGE_DESTINATIONS:
                        target_slot = next_free(container)
                        if target_slot is not None:
                            target_container = container
                            break
                    if target_container is None:
                        break
                    put = min(take - moved_qty, stack)
                    conn.execute(
                        "INSERT INTO char_inventory "
                        "(character_id, container, slot, item_id, quantity) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(character_id, container, slot) "
                        "DO UPDATE SET item_id = excluded.item_id, quantity = excluded.quantity",
                        (int(character_id), target_container, target_slot, item_id, put))
                    moved.append({
                        "to_container": target_container, "to_slot": target_slot,
                        "item_id": item_id, "quantity": put,
                        "name": str(row["name"] or "Item"),
                    })
                    moved_qty += put
                if moved_qty < left:
                    conn.execute(
                        "UPDATE char_locker SET quantity = ? "
                        "WHERE character_id = ? AND item_id = ?",
                        (left - moved_qty, int(character_id), item_id))
                    if moved_qty < take:
                        remaining += left - moved_qty
                else:
                    conn.execute(
                        "DELETE FROM char_locker WHERE character_id = ? AND item_id = ?",
                        (int(character_id), item_id))
                if limit is not None:
                    limit -= moved_qty
            stored = int(conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM char_locker WHERE character_id = ?",
                (int(character_id),)).fetchone()[0])
            return {"moved": moved, "skipped": skipped, "remaining": remaining,
                    "locker_count": stored, "locker_capacity": LOCKER_CAPACITY}

    def locker_summary(self, character_id: int) -> dict:
        """Filled/capacity totals for !locker with no arguments."""
        row = self.db.one(
            "SELECT COUNT(*) AS kinds, COALESCE(SUM(quantity), 0) AS items "
            "FROM char_locker WHERE character_id = ?", (int(character_id),))
        return {"kinds": int(row["kinds"] or 0), "items": int(row["items"] or 0),
                "capacity": LOCKER_CAPACITY}

    def locker_items(self, character_id: int) -> list[dict]:
        """Everything in the hidden locker, for !locker list."""
        return [dict(row) for row in self.db.all(
            "SELECT cl.item_id, cl.quantity, COALESCE(i.name, 'Item') AS name "
            "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
            "WHERE cl.character_id = ? ORDER BY COALESCE(i.name, 'Item'), cl.item_id",
            (int(character_id),))]

    def inventory_slot(self, character_id: int, container: int, slot: int) -> dict | None:
        """The item in one exact bag slot, or None when the slot is empty."""
        row = self.db.one(
            "SELECT container, slot, item_id, quantity FROM char_inventory "
            "WHERE character_id = ? AND container = ? AND slot = ?",
            (int(character_id), int(container), int(slot)))
        return dict(row) if row is not None else None

    def consume_inventory_item(self, character_id: int, item_id: int,
                               quantity: int = 1) -> dict | None:
        """Take a consumable from the normal inventory; return its new slot state."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT container, slot, quantity FROM char_inventory "
                "WHERE character_id = ? AND container = 0 AND item_id = ? "
                "ORDER BY slot LIMIT 1",
                (int(character_id), int(item_id))).fetchone()
            if row is None:
                return None
            have = int(row["quantity"])
            take = min(max(1, int(quantity)), have)
            left = have - take
            if left > 0:
                conn.execute(
                    "UPDATE char_inventory SET quantity = ? "
                    "WHERE character_id = ? AND container = 0 AND slot = ?",
                    (left, int(character_id), int(row["slot"])))
            else:
                conn.execute(
                    "DELETE FROM char_inventory "
                    "WHERE character_id = ? AND container = 0 AND slot = ?",
                    (int(character_id), int(row["slot"])))
            return {"item_id": int(item_id), "container": 0, "slot": int(row["slot"]),
                    "quantity": left}

    def consume_inventory_slot(self, character_id: int, container: int, slot: int,
                               quantity: int = 1) -> dict | None:
        """Take a consumable from one exact bag slot; return the slot's new state.

        The client's 0x037 names the container and the slot, not the item id, so this is
        the only way to consume the stack the player actually clicked.  ``quantity`` in
        the result is what is left (0 when the slot emptied).
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT item_id, quantity FROM char_inventory "
                "WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), int(container), int(slot))).fetchone()
            if row is None:
                return None
            have = int(row["quantity"])
            take = min(max(1, int(quantity)), have)
            left = have - take
            if left > 0:
                conn.execute(
                    "UPDATE char_inventory SET quantity = ? "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (left, int(character_id), int(container), int(slot)))
            else:
                conn.execute(
                    "DELETE FROM char_inventory "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (int(character_id), int(container), int(slot)))
            return {"item_id": int(row["item_id"]), "container": int(container),
                    "slot": int(slot), "quantity": left}

    def refill_working_stock(self, character_id: int) -> list[dict]:
        """Top up the visible consumables from the hidden locker.

        The client will not cast ninjutsu or use a medicine it cannot see, so a working
        stack of each must stay in the inventory.  The locker keeps the bulk.
        """
        with self.db.transaction() as conn:
            current = {int(row["item_id"]): int(row["quantity"]) for row in conn.execute(
                "SELECT item_id, SUM(quantity) AS quantity FROM char_inventory "
                "WHERE character_id = ? AND container = 0 GROUP BY item_id",
                (int(character_id),))}
            occupied = {int(row["slot"]) for row in conn.execute(
                "SELECT slot FROM char_inventory WHERE character_id = ? AND container = 0",
                (int(character_id),))}
            free = [slot for slot in range(0, CONTAINER_SLOTS) if slot not in occupied]
            moved: list[dict] = []
            for item_id, target in WORKING_STOCK:
                need = int(target) - current.get(item_id, 0)
                if need <= 0:
                    continue
                source = conn.execute(
                    "SELECT quantity FROM char_locker WHERE character_id = ? AND item_id = ?",
                    (int(character_id), int(item_id))).fetchone()
                if source is None:
                    continue
                available = int(source["quantity"])
                take = min(need, available)
                if take <= 0:
                    continue
                stack_row = conn.execute(
                    "SELECT COALESCE(stack, 1) FROM items WHERE item_id = ?",
                    (int(item_id),)).fetchone()
                stack = max(1, int(stack_row[0] if stack_row else 1))
                used = 0
                # Top up an existing partial stack first; otherwise every cast leaves
                # the old 98 stack and creates a new 1 stack beside it.
                for row in conn.execute(
                        "SELECT slot, quantity FROM char_inventory "
                        "WHERE character_id = ? AND container = 0 AND item_id = ? "
                        "ORDER BY slot", (int(character_id), int(item_id))).fetchall():
                    if take <= 0:
                        break
                    have = int(row["quantity"])
                    room = stack - have
                    if room <= 0:
                        continue
                    add = min(take, room)
                    conn.execute(
                        "UPDATE char_inventory SET quantity = quantity + ? "
                        "WHERE character_id = ? AND container = 0 AND slot = ?",
                        (add, int(character_id), int(row["slot"])))
                    moved.append({"to_container": 0, "to_slot": int(row["slot"]),
                                  "item_id": int(item_id), "quantity": have + add,
                                  "added": add})
                    take -= add
                    used += add
                while take > 0 and free:
                    slot = free.pop(0)
                    put = min(take, stack)
                    conn.execute(
                        "INSERT INTO char_inventory "
                        "(character_id, container, slot, item_id, quantity) "
                        "VALUES (?, 0, ?, ?, ?) "
                        "ON CONFLICT(character_id, container, slot) "
                        "DO UPDATE SET item_id = excluded.item_id, quantity = excluded.quantity",
                        (int(character_id), slot, int(item_id), put))
                    moved.append({"to_container": 0, "to_slot": slot,
                                  "item_id": int(item_id), "quantity": put,
                                  "added": put})
                    take -= put
                    used += put
                if used:
                    left = available - used
                    if left > 0:
                        conn.execute(
                            "UPDATE char_locker SET quantity = ? "
                            "WHERE character_id = ? AND item_id = ?",
                            (left, int(character_id), int(item_id)))
                    else:
                        conn.execute(
                            "DELETE FROM char_locker "
                            "WHERE character_id = ? AND item_id = ?",
                            (int(character_id), int(item_id)))
            return moved

    def working_stock_status(self, character_id: int) -> dict[int, tuple[int, int]]:
        """Item id -> (current visible quantity, target) for !stock."""
        ids = tuple(item_id for item_id, _target in WORKING_STOCK)
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.all(
            "SELECT item_id, SUM(quantity) AS quantity FROM char_inventory "
            "WHERE character_id = ? AND container = 0 AND item_id IN (%s) "
            "GROUP BY item_id" % placeholders, (int(character_id), *ids))
        current = {int(row["item_id"]): int(row["quantity"]) for row in rows}
        return {item_id: (current.get(item_id, 0), target)
                for item_id, target in WORKING_STOCK}

    def set_item_model(self, item_id: int, model: int) -> None:
        """Set the look (model) id the client draws for an item."""
        self.db.execute("UPDATE items SET model = ? WHERE item_id = ?",
                        (int(model) & 0xFFFF, int(item_id)))

    def save_job(self, character_id: int, main_job: int, main_level: int,
                 sub_job: int, sub_level: int) -> None:
        """Persist a job change made in the Moogle's menu."""
        self.db.execute(
            "UPDATE characters SET main_job = ?, main_level = ?, sub_job = ?, sub_level = ?, "
            "updated_at = ? WHERE id = ?",
            (int(main_job), int(main_level), int(sub_job), int(sub_level), now_iso(),
             int(character_id)),
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

    @staticmethod
    def _owns_item(conn, character_id: int, item_id: int) -> bool:
        row = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM char_inventory "
            "               WHERE character_id = ? AND item_id = ? AND quantity > 0) "
            "    OR EXISTS (SELECT 1 FROM char_storage "
            "               WHERE character_id = ? AND item_id = ? AND quantity > 0) "
            "    OR EXISTS (SELECT 1 FROM char_locker "
            "               WHERE character_id = ? AND item_id = ? AND quantity > 0) AS owned",
            (int(character_id), int(item_id), int(character_id), int(item_id),
             int(character_id), int(item_id))).fetchone()
        return bool(row["owned"]) if row else False

    def owns_item(self, character_id: int, item_id: int) -> bool:
        """Whether a character holds an item in any permanent bag, storage or the locker.

        Retail's Rare check searches every container, not just the inventory; a Rare
        piece on a storage slip still stops the character from obtaining another.
        """
        with self.db.connection() as conn:
            return self._owns_item(conn, character_id, item_id)

    def add_item(self, character_id: int, item_id: int, quantity: int = 1,
                 one_per_character: bool = False) -> dict:
        if quantity <= 0:
            raise ApiError(422, "validation_error", "quantity must be positive")
        item = self.item(item_id)
        rare = bool(item and int(item.get("rare") or 0))
        # The Armory treats Ex as one-per-character too; a normal grant does not,
        # because the augmented job capes are Ex and several builds share an id.
        unique = rare or bool(one_per_character and item and int(item.get("ex") or 0))
        if unique and quantity > 1:
            raise ApiError(422, "rare_item",
                           "only one copy of this item can be obtained at a time")
        stack = int(item["stack"]) if item else 1
        with self.db.transaction() as conn:
            # The uniqueness check runs inside the write transaction so two
            # simultaneous grants cannot both see an empty bag and insert a copy.
            if unique and self._owns_item(conn, character_id, item_id):
                raise ApiError(409, "already_owned",
                               "the character already possesses %s" % item["name"])
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
                levels += 1
            if levels:
                # Max HP/MP follow race, job, level and subjob; the zone session adds the
                # gear's HP/MP on top when it next builds the sheet.
                from .game import base_stats
                hp = base_stats.base_hp(int(row["race"]), int(row["main_job"]), level,
                                        int(row["sub_job"]), int(row["sub_level"]))
                mp = base_stats.base_mp(int(row["race"]), int(row["main_job"]), level,
                                        int(row["sub_job"]), int(row["sub_level"]))
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
            "accounts": int(self.db.scalar(
                "SELECT COUNT(*) FROM accounts WHERE kind = 'main'", (), 0)),
            "sub_accounts": int(self.db.scalar(
                "SELECT COUNT(*) FROM accounts WHERE kind = 'sub' AND status = 'active'", (), 0)),
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
