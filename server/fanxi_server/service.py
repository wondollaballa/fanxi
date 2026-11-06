"""Accounts, characters, sessions and admin operations.

The HTTP layer and the game gateway both call this module; it is the only place that writes
account data. Every method is synchronous and opens its own SQLite connection, so the threaded
HTTP server and the game sockets can use it without sharing a connection.
"""
from __future__ import annotations

import json
import math
import secrets
from functools import lru_cache
from pathlib import Path
import sqlite3
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import __version__
from .config import Config
from .db import Database
from .game import (ascension, augment_gear, augment_stats, capes, design as character_design,
                   effects, glyptics, item_effects, job_points, magian, merit_menus,
                   merits as merit_table, mezzotint, mobskills, moonshade, oboro, reive,
                   set_bonuses, sinister, skirmish)
from .game import modifiers as mod, prime_weapons, rema_weapons

SPELL_LEVELS_PATH = Path(__file__).resolve().parents[2] / "data" / "spell_levels.json"
WEAPON_SKILL_PROPERTIES_PATH = (Path(__file__).resolve().parents[2]
                                / "data" / "weapon_skill_properties.json")
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

BATTLE_SHARED_KEYS = ("roster", "camp", "support_camp", "camp_assign", "combat_style", "rules")

CHAR_ID_BASE = 0x01000000
DEFAULT_ZONE = 246
# The original starting city for each nation: San d'Oria, Bastok, Windurst.
START_ZONE_BY_NATION = {0: 230, 1: 236, 2: 240}
FAILED_LOGIN_LIMIT = 5
LOCK_MINUTES = 15
STARTER_GIL = 1000
#: Alter-ego upgrade levels, the March 2026 Trust system's 0-50 per stat cap.
TRUST_UPGRADE_MAX = 50
STARTER_ITEMS = ((1, 4112, 2), (2, 16534, 1))  # slot, item id, quantity

# The client's container numbers.  Storage is 2; the wardrobes are 8 and 10-16.
CONTAINER_INVENTORY = 0
CONTAINER_STORAGE = 2
CONTAINER_RECYCLE = 17         # the client's Recycle Bin
CONTAINER_SLOTS = 81           # 0-80 in the inventory, 1-80 in every storage bag
RECYCLE_DAYS = 30
STORAGE_CAPACITY = CONTAINER_SLOTS - 1
# The hidden general-purpose locker is not a client container; the client's own bag
# capacity is one byte, so 9999 is a server-side limit, not a visible bag size.  Capacity
# counts storage entries (one row per item id + augment block), not units: a 99-item jug
# stack is one slot, which is also how the client's storage menus are laid out.
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
# The organizer's order: weapons, then armour, then accessories.  A pulled set reads in
# the same order the equipment window does instead of arriving in item-id order.
EQUIP_ORDER = {
    "main": 0, "sub": 1, "ranged": 2, "range": 2, "ammo": 3,
    "head": 4, "body": 5, "hands": 6, "legs": 7, "feet": 8,
    "neck": 9, "waist": 10, "ear1": 11, "ear2": 12,
    "ring1": 13, "ring2": 14, "back": 15,
}
# A job's active set lives in the Mog Wardrobes first; the inventory is the overflow.
# The Safe/Satchel/Sack/Case are sources for the tidy, never destinations: a set there
# cannot be auto-equipped, and it would just be another place to look.
ORGANIZE_DESTINATIONS = WARDROBE_CONTAINERS + (CONTAINER_INVENTORY,)
# Bags whose loose job gear the tidy moves into the wardrobes.  Wardrobes are already
# the destination, so they are not sources here.
ORGANIZE_HOME_BAGS = (CONTAINER_INVENTORY, 1, 5, 6, 7, 9)

# The Data page: values the launcher assigns instead of waiting for gameplay to derive.
GIL_MAX = 2_147_483_647
MASTERY_RANK_MAX = 10
KEY_ITEM_TABLES = 7
JOB_POINT_CAPACITY = 30000
JOB_POINT_CURRENT = 500
JOB_POINT_SPENT = 2100
JOB_COUNT = 22
# Per-account GearSwap libraries live in the database so an import follows the account
# across machines, and an edit never touches the checkout's shared gearswap/*.lua files.
GEARSWAP_JOBS = tuple(merit_menus.JOB_ABBRS[index] for index in range(1, JOB_COUNT + 1))
MAX_GEARSWAP_LIBRARY_BYTES = 512 * 1024

# The item slots the Armory offers: weapons and ammo use the hand/range slots, armour the
# five body slots, and accessories the seven jewellery slots.
ARMORY_SLOTS = {
    "weapon": ("main", "sub", "ranged", "range"),
    "armor": ("head", "body", "hands", "legs", "feet"),
    "accessory": ("neck", "waist", "ear1", "ear2", "ring1", "ring2", "back"),
    "ammo": ("ammo",),
}

# The Items tab groups the general-item catalogue by this list.  The category
# text is stored on each item by migration 0156; this list only fixes the order
# of the filter chips, so a future category appended by a migration still shows
# up (at the end) without a server change.
ITEM_CATEGORY_ORDER = (
    "Ninja Tools",
    "Jug Pets",
    "Consumables",
    "Ingredients",
    "Materials",
    "Food & Drink",
    "Magic Scrolls",
    "Ammunition",
    "Crystals",
    "Pet Items",
    "Automaton Attachments",
    "Fishing Gear",
    "Furnishings",
    "Miscellaneous",
)

ITEM_SCOPE = "items"
ARMORY_SCOPE = "armory"


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
MASTER_LEVEL_MAX = 50
CRAFT_MAX = 100
# //warp: each character has slots 1-1000.  The number is the target the chat command
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
    """Experience needed to reach the next level. Fanxi's own curve, not retail's table.

    Level 99 has no next level: retail sends a zero requirement and the client shows the
    Master Level/Exemplar block instead of an EXP bar.
    """
    level = max(1, int(level))
    if level >= 99:
        return 0
    return max(100, int(100 * (level ** 1.5)))


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
        # Set by the game gateway too.  Zone sessions exist only in that process's memory, so
        # "who is really in a zone" can only be answered through it; a game_sessions row
        # survives a server restart and is not proof that a client is still connected.
        self.zone_world = None
        # Prime weapon item id -> its stage, or None for a non-Prime item.  The item
        # table only changes with a migration, so one lookup per item is enough.
        self._prime_weapon_cache: dict[int, prime_weapons.PrimeWeapon | None] = {}

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
            # The last mount the character called (-1 until it calls one).  Being mounted
            # is live state on the zone session, not a column: a relog starts on foot.
            "mount": int(row["mount"]) if row.get("mount") is not None else -1,
            "main_job": row["main_job"],
            "sub_job": row["sub_job"],
            "main_level": row["main_level"],
            "sub_level": row["sub_level"],
            "hp": row["hp"],
            "mp": row["mp"],
            "hp_current": row.get("hp_current", row["hp"]),
            "mp_current": row.get("mp_current", row["mp"]),
            # Level 99 is the Master Level band: the launcher and the client show the
            # Exemplar block, not a stale EXP total with a zero requirement.
            "exp": 0 if int(row["main_level"]) >= 99 else row.get("exp", 0),
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

    # --- //warp --------------------------------------------------------------------------------
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
        merit_counts = self.merits_for_character(int(character_id))
        merit_cap = min(255, 127 + max(0, int(merit_counts.get(0x0044, 0))))
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
            item_id = int(row["item_id"])
            row["owned"] = item_id in owned
            prime = prime_weapons.form(item_id)
            if prime is not None:
                row["prime_final"] = prime.is_final
                row["prime_stage"] = prime.stage
                row["prime_stages"] = prime_weapons.PRIME_STAGE_COUNT
            rema = rema_weapons.form(item_id)
            if rema is not None:
                row["rema_final"] = rema.is_final
                row["rema_family"] = rema.family
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
            "merits": {
                "points": int(character.get("merit_points") or 0),
                "cap": int(merit_cap),
                "spent": int(merit_table.total_cost(merit_counts)),
                "categories": merit_menus.catalog(merit_counts),
            },
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
            "trusts": self.trust_summary(int(character_id)),
            "augments": augment_gear.inventory_items(self, int(character_id)),
            "oboro": oboro.catalog(self, int(character_id)),
            "capes": capes.catalog(self, int(character_id)),
            "reive": reive.catalog(self, int(character_id)),
            "nolan": mezzotint.catalog(self, int(character_id)),
            "glyptics": glyptics.catalog(self, int(character_id)),
            "skirmish": skirmish.catalog(self, int(character_id)),
            "sinister": sinister.catalog(self, int(character_id)),
            "moonshade": moonshade.catalog(self, int(character_id)),
            "magian": magian.catalog(self, int(character_id)),
            "ascension": ascension.catalog(self, int(character_id)),
            "currencies": currencies,
            "currency_catalog": list(CURRENCY_CATALOG),
            "item_categories": self.item_categories(),
            "purchases": purchases,
            "mounts": self._mount_summary(character),
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

    def held_item_quantities(self, character_id: int, item_ids) -> dict[int, int]:
        """How many units of each item the character holds across every permanent bag.

        The Armory only needs a boolean, but the Items tab shows the held count so a
        stack purchase reads sensibly (``Held 99`` after buying a stack of shihei).
        Bags, storage slips and the hidden locker all count, the same places the
        Rare check and purchase history use.
        """
        ids = sorted({int(item) for item in item_ids if int(item) > 0})[:400]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        rows = self.db.all(
            "SELECT item_id, SUM(quantity) AS quantity FROM ("
            "  SELECT item_id, quantity FROM char_inventory"
            "   WHERE character_id = ? AND quantity > 0"
            "  UNION ALL SELECT item_id, quantity FROM char_storage"
            "   WHERE character_id = ? AND quantity > 0"
            "  UNION ALL SELECT item_id, quantity FROM char_locker"
            "   WHERE character_id = ? AND quantity > 0"
            ") WHERE item_id IN (%s) GROUP BY item_id" % marks,
            (int(character_id), int(character_id), int(character_id), *ids))
        return {int(row["item_id"]): int(row["quantity"]) for row in rows}

    def item_categories(self) -> list[dict]:
        """The Items tab filter chips, in the shop's display order."""
        counts = {
            str(row["category"]): int(row["count"])
            for row in self.db.all(
                "SELECT category, COUNT(*) AS count FROM items "
                "WHERE category != '' AND price > 0 GROUP BY category")
        }
        ordered = [name for name in ITEM_CATEGORY_ORDER if counts.get(name)]
        ordered += sorted(name for name in counts if name not in ITEM_CATEGORY_ORDER)
        return [{"name": name, "count": counts[name]} for name in ordered]

    def _collapse_final_rows(self, rows: list[dict], final_id_for) -> list[dict]:
        """Collapse upgrade stages to one final row per family, first occurrence wins.

        *final_id_for* maps a catalogue item id to its family's final id, or None
        when the item has no later form.  A final row the query did not return is
        fetched from the catalogue so the replacement still points at a complete
        row.
        """
        replacements: dict[int, int] = {}
        for row in rows:
            item_id = int(row["item_id"])
            final_id = final_id_for(item_id)
            if final_id is not None and final_id != item_id:
                replacements[item_id] = final_id
        if not replacements:
            return rows

        by_id = {int(row["item_id"]): row for row in rows}
        missing = sorted({
            final_id for final_id in replacements.values() if final_id not in by_id
        })
        if missing:
            marks = ",".join("?" for _ in missing)
            for row in self.db.all(
                    "SELECT item_id, name, category, equip_slot, level, item_level, jobs, "
                    "rare, ex, stack, skill, price, base_sell, description "
                    "FROM items WHERE item_id IN (%s)" % marks, tuple(missing)):
                by_id[int(row["item_id"])] = dict(row)

        out: list[dict] = []
        seen: set[int] = set()
        for row in rows:
            item_id = int(row["item_id"])
            final_id = replacements.get(item_id, item_id)
            if final_id in seen:
                continue
            final = by_id.get(final_id)
            if final is None:
                continue
            out.append(final)
            seen.add(final_id)
        return out

    def _prime_final_rows(self, rows: list[dict]) -> list[dict]:
        """Collapse Prime weapon stages to the one form the Armory sells.

        A Prime family stores up to five rows that share a name: the four upgraded
        forms are all called ``Foenaria``, so the typeahead showed four identical
        entries and Enter picked the weakest one.  Every stage maps to the iLvl 119
        III form, and the stage-1 ``Prime ...`` row maps too, so a search for
        ``Prime Scythe`` still finds Foenaria.
        """
        return self._collapse_final_rows(rows, prime_weapons.final_item_id)

    def _rema_final_rows(self, rows: list[dict]) -> list[dict]:
        """Collapse REMA stages to the one final afterglow form the Armory sells.

        The family table maps every Relic, Empyrean, Mythic and Aeonic stage -- and
        the handful of final rows suffixed ``119 III`` -- to the family's final id.
        A search for Masamune therefore returns one row instead of eight, and a
        search for Kikoku 119 III still finds the final row.
        """
        return self._collapse_final_rows(rows, rema_weapons.final_item_id)

    def search_items(self, character_id: int, query: str, kind: str | None = None,
                     limit: int = 40, scope: str = ARMORY_SCOPE,
                     category: str | None = None) -> list[dict]:
        """Search the Armory (equipment) or the Items tab's general-item shop.

        The Armory keeps its paperdoll ``kind`` filter and level-first ordering.
        The Items scope instead filters on migration 0156's ``items.category`` and
        sorts by name; an empty query with a category is how the tab browses a
        shelf, and a name match still puts exact and prefix hits first.  The Items
        text also matches the category name, so "jug" finds the Jug Pets shelf
        without the player having to know a broth's name.  Both scopes return the
        held quantity the Items tab displays.
        """
        scope = str(scope or ARMORY_SCOPE).strip().lower()
        if scope not in (ARMORY_SCOPE, ITEM_SCOPE):
            scope = ARMORY_SCOPE
        text = " ".join(str(query or "").split()).strip()
        try:
            limit = max(1, min(100, int(limit)))
        except (TypeError, ValueError):
            limit = 40

        args: list = []
        order_args: list = []
        if scope == ITEM_SCOPE:
            selected_category = " ".join(str(category or "").split()).strip()
            where = ["category != ''", "price > 0"]
            if selected_category:
                where.append("category = ?")
                args.append(selected_category)
            order = "name COLLATE NOCASE"
            if text:
                # Match on the punctuation-free form as well as the stored name so
                # "noble's bed" finds the generated "Noble's Bed" and vice versa.
                plain = text.replace("'", "")
                pattern = "%" + _like_escape(plain) + "%"
                category_match = (
                    " OR category LIKE ? ESCAPE '\\'" if len(plain) >= 3 else "")
                where.append(
                    "(REPLACE(name, '''', '') LIKE ? ESCAPE '\\' OR EXISTS ("
                    " SELECT 1 FROM item_aliases a"
                    " WHERE a.item_id = items.item_id"
                    " AND REPLACE(a.alias, '''', '') LIKE ? ESCAPE '\\')"
                    + category_match + ")")
                args.extend([pattern, pattern] + ([pattern] if category_match else []))
                prefix = _like_escape(plain) + "%"
                order = ("CASE WHEN REPLACE(name, '''', '') = ? COLLATE NOCASE OR EXISTS ("
                         " SELECT 1 FROM item_aliases a"
                         " WHERE a.item_id = items.item_id"
                         " AND REPLACE(a.alias, '''', '') = ? COLLATE NOCASE) THEN 0 "
                         "WHEN REPLACE(name, '''', '') LIKE ? ESCAPE '\\' OR EXISTS ("
                         " SELECT 1 FROM item_aliases a"
                         " WHERE a.item_id = items.item_id"
                         " AND REPLACE(a.alias, '''', '') LIKE ? ESCAPE '\\') THEN 1 "
                         "ELSE 2 END, name COLLATE NOCASE")
                order_args = [plain, plain, prefix, prefix]
        else:
            slots = ARMORY_SLOTS.get(str(kind or "").strip().lower())
            where = ["equip_slot != ''"]
            if slots:
                where.append("equip_slot IN (%s)" % ",".join("?" for _ in slots))
                args.extend(slots)
            order = "level DESC, name COLLATE NOCASE"
            if text:
                pattern = "%" + _like_escape(text) + "%"
                where.append(
                    "(name LIKE ? ESCAPE '\\' OR EXISTS ("
                    " SELECT 1 FROM item_aliases a"
                    " WHERE a.item_id = items.item_id"
                    " AND a.alias LIKE ? ESCAPE '\\'))")
                args.extend([pattern, pattern])
                order = ("CASE WHEN name = ? COLLATE NOCASE OR EXISTS ("
                         " SELECT 1 FROM item_aliases a"
                         " WHERE a.item_id = items.item_id"
                         " AND a.alias = ? COLLATE NOCASE) THEN 0 "
                         "WHEN name LIKE ? ESCAPE '\\' OR EXISTS ("
                         " SELECT 1 FROM item_aliases a"
                         " WHERE a.item_id = items.item_id"
                         " AND a.alias LIKE ? ESCAPE '\\') THEN 1 ELSE 2 END, "
                         "level DESC, name COLLATE NOCASE")
                prefix = _like_escape(text) + "%"
                order_args = [text, text, prefix, prefix]
            if not text and not slots:
                return []

        rows = [dict(row) for row in self.db.all(
            "SELECT item_id, name, category, equip_slot, level, item_level, jobs, rare, ex, "
            "stack, skill, price, base_sell, description "
            "FROM items WHERE " + " AND ".join(where) +
            " ORDER BY " + order + " LIMIT ?", (*args, *order_args, limit))]
        family_ids: dict[int, tuple[int, ...]] = {}
        if scope == ARMORY_SCOPE:
            rows = self._prime_final_rows(rows)
            rows = self._rema_final_rows(rows)
            for row in rows:
                ids = (prime_weapons.family_item_ids(row["item_id"])
                       or rema_weapons.family_item_ids(row["item_id"]))
                if ids:
                    family_ids[int(row["item_id"])] = ids
        held_ids = [int(row["item_id"]) for row in rows]
        held_ids.extend(item_id for ids in family_ids.values() for item_id in ids)
        held = self.held_item_quantities(character_id, held_ids)
        for row in rows:
            item_id = int(row["item_id"])
            # A Prime or REMA weapon is one Rare item per family, so an earlier stage
            # the character still holds counts as owning the final form.
            row["held"] = sum(held.get(candidate, 0)
                              for candidate in family_ids.get(item_id, (item_id,)))
            row["owned"] = row["held"] > 0
            # Only Rare limits the character to one copy.  Ex alone means the item
            # cannot be traded or sold, so several copies can still be held.
            row["unique"] = bool(int(row.get("rare") or 0))
            if scope == ARMORY_SCOPE:
                prime = prime_weapons.form(item_id)
                if prime is not None:
                    row["prime_final"] = prime.is_final
                    row["prime_stage"] = prime.stage
                    row["prime_stages"] = prime_weapons.PRIME_STAGE_COUNT
                    row["prime_family"] = prime.family
                rema = rema_weapons.form(item_id)
                if rema is not None:
                    row["rema_final"] = rema.is_final
                    row["rema_family"] = rema.family
        return rows

    def armory_add(self, character_id: int, item_id: int, quantity: int = 1) -> dict:
        """Buy one equipment item for a character, from the Armory catalogue."""
        return self._purchase_catalogue_item(
            character_id, item_id, quantity, scope=ARMORY_SCOPE)

    def item_add(self, character_id: int, item_id: int, quantity: int = 1) -> dict:
        """Buy one general item for a character, from the Items tab catalogue."""
        return self._purchase_catalogue_item(
            character_id, item_id, quantity, scope=ITEM_SCOPE)

    def _purchase_catalogue_item(self, character_id: int, item_id: int,
                                 quantity: int = 1, *, scope: str = ARMORY_SCOPE) -> dict:
        """Charge the wallet, add the item and record the purchase.

        Only Rare is one-per-character: the Ex flag alone means the item cannot be
        traded or sold, not that a second copy cannot be held, so an Ex-only piece
        (Linos, Andartia's Mantle) can be bought again.  The price is charged before
        the inventory insert and refunded if the insert fails, so a full bag never
        costs the character gil.  A Prime or REMA weapon is always granted in its
        final iLvl 119 III (afterglow) form, even if the caller asks for an earlier
        stage.
        """
        requested_id = int(item_id)
        item_id = (prime_weapons.final_item_id(requested_id)
                   or rema_weapons.final_item_id(requested_id)
                   or requested_id)
        item = self.item(int(item_id))
        if item is None:
            raise ApiError(404, "not_found", "no item with that id")
        scope = str(scope or ARMORY_SCOPE).strip().lower()
        if scope == ITEM_SCOPE:
            if not str(item.get("category") or "").strip():
                raise ApiError(422, "validation_error",
                               "%s is not in the item shop" % item["name"])
            if int(item.get("price") or 0) <= 0:
                raise ApiError(422, "validation_error",
                               "%s is not for sale" % item["name"])
        elif scope == ARMORY_SCOPE:
            if str(item.get("equip_slot") or "") not in {
                    slot for slots in ARMORY_SLOTS.values() for slot in slots}:
                raise ApiError(
                    422, "validation_error",
                    "%s is not armour, an accessory, ammo or a weapon" % item["name"])
        else:
            raise ApiError(422, "validation_error", "unknown item scope")
        try:
            quantity = max(1, min(99, int(quantity)))
        except (TypeError, ValueError):
            quantity = 1
        unique = bool(int(item.get("rare") or 0))
        if unique:
            if quantity != 1:
                raise ApiError(422, "rare_item",
                               "only one copy of a Rare item can be obtained at a time")
            # A Prime or REMA family is one Rare item: holding an earlier stage
            # blocks the final form just as holding the final blocks another purchase.
            candidates = (prime_weapons.family_item_ids(item_id)
                          or rema_weapons.family_item_ids(item_id)
                          or (int(item_id),))
            if any(self.owns_item(int(character_id), candidate)
                   for candidate in candidates):
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
            added = self.add_item(int(character_id), int(item_id), quantity)
        except Exception:
            if charged:
                try:
                    self.set_gil(int(character_id), gil)
                except Exception:
                    log.exception(
                        "%s could not refund a failed purchase of item %d",
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
            log.exception("%s could not record the purchase of item %d",
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

    def trust_upgrade_level(self, character_id: int) -> int:
        """The character's alter-ego upgrade level (0-50), shared by every Trust.

        Fanxi models the launcher's "max all" action as one account-wide level rather
        than asking the player to assign the retail point tiers to 100+ alter egos.
        The level is stored in ``char_settings`` so an existing database needs no new
        table; a fresh character starts at 0.
        """
        try:
            raw = self.character_setting(int(character_id), "trust_upgrade_level", "0")
            return max(0, min(TRUST_UPGRADE_MAX, int(raw or 0)))
        except (TypeError, ValueError, sqlite3.Error):
            return 0

    def set_trust_upgrade_level(self, character_id: int, level: int) -> int:
        value = max(0, min(TRUST_UPGRADE_MAX, int(level)))
        self.set_character_setting(int(character_id), "trust_upgrade_level", str(value))
        return value

    def max_trust_upgrades(self, character_id: int) -> int:
        """Set every Trust's upgrade to the current maximum (the launcher button)."""
        return self.set_trust_upgrade_level(int(character_id), TRUST_UPGRADE_MAX)

    def trust_summary(self, character_id: int | None = None) -> dict:
        row = self.db.one("SELECT COUNT(*) AS n FROM trusts")
        level = (self.trust_upgrade_level(int(character_id))
                 if character_id is not None else 0)
        return {
            "spells": int(row["n"]),
            "key_items": "all",
            "summoning": True,
            "upgrade_level": int(level),
            "upgrade_max": TRUST_UPGRADE_MAX,
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
            "exp": 0 if int(row["main_level"]) >= 99 else row.get("exp", 0),
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
            # The single Home Point set in Profile: Warp, Warp II, Retrace, //home and a
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
            # The weapon type each locked hand had, so a same-type swap keeps the locked
            # model (and never repaints the client) while a different type updates it.
            "style_main_type": int(row.get("style_main_type") or 0),
            "style_sub_type": int(row.get("style_sub_type") or 0),
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

    def attach_world(self, world) -> None:
        """Tell the HTTP side where live zone sessions are.  Called by the game gateway."""
        self.zone_world = world

    def detach_world(self, world=None) -> None:
        if world is None or self.zone_world is world:
            self.zone_world = None

    def online_characters(self, account_id: int | None = None) -> list[dict]:
        """The characters with a live zone session, optionally only one account family.

        This is the server's authoritative online roster.  It is deliberately different from
        ``game_sessions``: those rows are launch credentials and outlive the zone session, so
        after a server restart they still exist for clients the world has forgotten.
        """
        world = self.zone_world
        if world is None:
            return []
        from .game.search import online_characters

        family = self.account_family_ids(account_id) if account_id is not None else None
        characters = []
        for char in online_characters(world):
            if family is not None and int(char.get("account_id") or 0) not in family:
                continue
            zone = int(char.get("zone") or 0)
            characters.append({
                "id": int(char.get("id") or 0),
                "char_id": int(char.get("char_id") or 0),
                "name": str(char.get("name") or ""),
                "zone": zone,
                "zone_name": world.zones.name(zone),
            })
        characters.sort(key=lambda item: item["name"].casefold())
        return characters

    def online_count(self) -> int:
        if self.zone_world is not None:
            return len(self.online_characters())
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
            "t.hp AS template_hp, t.hp_min AS template_hp_min, t.level_stats, "
            "t.mp AS template_mp, "
            "t.attack, t.defense, t.accuracy, t.evasion, "
            "t.attack_delay_ms, t.aggro, t.links, t.roam_radius, t.respawn_seconds AS template_respawn, "
            "t.name_prefix, t.behavior, t.content_tag, t.skill_list_id "
            "FROM monster_spawns s JOIN monster_templates t ON t.id = s.template_id "
            "WHERE s.zone = ? AND s.enabled = 1 ORDER BY s.id", (int(zone),))
        return [dict(r) for r in rows]

    def mob_skills(self, skill_list_id: int) -> list[dict]:
        """The TP moves a monster's ``skill_list_id`` names, as full rows.

        The list table carries one row per ability; the join and ORDER BY make the
        world's random choice stable across restarts (the server shuffles the copy).
        """
        if int(skill_list_id or 0) <= 0:
            return []
        return [dict(row) for row in self.db.all(
            "SELECT k.* FROM mob_skill_lists l JOIN mob_skills k "
            "ON k.id = l.mob_skill_id WHERE l.skill_list_id = ? ORDER BY k.id",
            (int(skill_list_id),))]

    def battle_spells(self) -> list[dict]:
        """Every spell in the server table, for the Battle Magic Burst picker.

        The burst plan is party-wide, so the same reason as the weapon-skill list applies:
        the current client only knows its own job spells.  The skill id is enough for the
        launcher to group and label the row.
        """
        return [dict(row) for row in self.db.all(
            "SELECT id, name, skill, element FROM spells ORDER BY name COLLATE NOCASE")]

    def battle_weapon_skills(self) -> list[dict]:
        """The full weapon-skill list for the Battle skillchain editor.

        The client's own HUD only knows the current weapon's skills.  The Battle page
        configures a party-wide chain, so the server's catalogue is the useful list.
        """
        return [dict(row) for row in self.db.all(
            "SELECT id, name, skill, skill_level, element FROM weapon_skills "
            "ORDER BY name COLLATE NOCASE, id")]

    def battle_mob_moves(self, names, zone: int = 0) -> dict:
        """The TP moves of the selected pull targets, with a short description.

        The launcher's reactive dispel lets the player pick the self-buffs a camp's
        mobs use.  The client cannot see a monster's move list, so this joins the
        spawn/template to ``mob_skill_lists`` and describes each move from the data
        the server already applies (target shape, status, self-buff).
        """
        wanted = []
        seen_names = set()
        for raw in names or []:
            name = str(raw or "").strip()[:48]
            key = name.casefold()
            if name and key not in seen_names and len(wanted) < 40:
                seen_names.add(key)
                wanted.append(name)
        if not wanted:
            return {"moves": [], "unmatched": []}
        holes = ",".join("?" for _ in wanted)
        area = [] if not int(zone or 0) else [" AND (s.zone = ? OR s.id IS NULL)"]
        params = [name.casefold() for name in wanted] * 2
        if area:
            params.append(int(zone))
        rows = self.db.all(
            "SELECT DISTINCT t.id, t.name, t.skill_list_id, s.name AS spawn_name "
            "FROM monster_templates t LEFT JOIN monster_spawns s ON s.template_id = t.id "
            f"WHERE (lower(t.name) IN ({holes}) OR lower(s.name) IN ({holes}))"
            + "".join(area)
            + " ORDER BY t.id",
            tuple(params))
        found = set()
        by_skill: dict[int, dict] = {}
        for raw in rows:
            row = dict(raw)
            found.add(str(row["name"]).casefold())
            if row.get("spawn_name"):
                found.add(str(row["spawn_name"]).casefold())
            skill_list_id = int(row.get("skill_list_id") or 0)
            if skill_list_id <= 0:
                continue
            mob_name = str(row.get("spawn_name") or row["name"])
            for skill_row in self.mob_skills(skill_list_id):
                skill = mobskills.from_row(skill_row)
                if skill.id in by_skill:
                    mobs = by_skill[skill.id]["mobs"]
                    if mob_name not in mobs:
                        mobs.append(mob_name)
                    continue
                target = "self" if skill.valid_targets & mobskills.TARGET_SELF else (
                    "enemy" if skill.is_enemy_target else (
                        "party" if skill.valid_targets & mobskills.TARGET_PARTY else "target"))
                aoe = {mobskills.AOE_ATTACKER: "self-centered AoE",
                       mobskills.AOE_TARGET: "target-centered AoE",
                       mobskills.AOE_CONE: "cone",
                       mobskills.AOE_CONE_TARGET: "targeted cone"}.get(skill.aoe, "")
                status = mobskills.status_name(skill)
                self_effect = mobskills.self_effect(skill)
                self_buff = mobskills.is_self_buff(skill)
                if target == "self":
                    if self_effect is not None and self_effect[0] == "heal":
                        description = "Self-heal"
                    elif self_buff:
                        description = "Self-buff · dispellable"
                    else:
                        description = "Self-target effect"
                elif target == "enemy":
                    description = f"Enemy {aoe} attack" if aoe else "Enemy single-target attack"
                else:
                    description = f"{target.capitalize()} {aoe} effect" if aoe else "Support effect"
                if status:
                    description += f" · may inflict {status}"
                by_skill[skill.id] = {
                    "name": mobskills.display_name(skill.name),
                    "description": description,
                    "target": target,
                    "aoe": aoe or "single",
                    "status": status,
                    "dispellable": self_buff,
                    "mobs": [mob_name],
                }
        moves = sorted(by_skill.values(),
                       key=lambda item: (not item["dispellable"], item["name"].casefold()))
        unmatched = [name for name in wanted if name.casefold() not in found]
        return {"moves": moves, "unmatched": unmatched}

    def inventory(self, character_id: int) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
            "CASE WHEN ci.item_id = 65535 THEN 'Gil' ELSE COALESCE(i.name, 'Item') END AS name, "
            "COALESCE(i.stack, 1) AS stack, COALESCE(i.usable, 0) AS usable, "
            "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.level, 1) AS level, "
            "COALESCE(i.model, 0) AS model, COALESCE(i.slot_mask, 0) AS slot_mask, "
            "COALESCE(i.jobs, 0) AS jobs, COALESCE(i.skill, 0) AS skill, "
            "COALESCE(i.subskill, 0) AS subskill, "
            "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex, "
            "COALESCE(st.slip, 0) AS storage_slip, "
            "COALESCE(ci.dropped_at, '') AS dropped_at, "
            "COALESCE(ci.extra, X'') AS extra "
            "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
            "LEFT JOIN item_storage st ON st.item_id = ci.item_id "
            "WHERE ci.character_id = ? ORDER BY ci.container, ci.slot", (int(character_id),))]

    def apply_ascension(self, character_id: int, container, slot, choices) -> None:
        """Write a Shantotto's Ascension augment block to one bag copy."""
        try:
            container = int(container)
            slot = int(slot)
        except (TypeError, ValueError):
            raise ApiError(422, "validation_error",
                           "container and slot must be numbers") from None
        row = self.inventory_slot(int(character_id), container, slot)
        if row is None:
            raise ApiError(404, "not_found", "no item in that bag slot")
        if int(row["item_id"]) not in ascension.ITEM_IDS:
            raise ApiError(422, "validation_error",
                           "that item is not Shantotto's Ascension gear")
        try:
            block = ascension.block_for(choices)
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from None
        if not self.set_item_extra(int(character_id), container, slot, block):
            raise ApiError(404, "not_found", "the bag copy disappeared")

    def set_item_extra(self, character_id: int, container: int, slot: int,
                       extra: bytes) -> bool:
        """Store an item's 24-byte attribute block (the client's augment extdata)."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE char_inventory SET extra = ? "
                "WHERE character_id = ? AND container = ? AND slot = ?",
                (sqlite3.Binary(bytes(extra)), int(character_id), int(container), int(slot)))
            return cursor.rowcount > 0

    def set_item_and_extra(self, character_id: int, container: int, slot: int,
                           item_id: int, extra: bytes) -> bool:
        """Replace a bag copy's item id and attribute block in one write.

        The Magian trials turn one weapon or armour piece into another (a relic
        stage, an Empyrean +1/+2, a different trial weapon) and the reward carries
        its own augment block, so both columns move together.
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE char_inventory SET item_id = ?, extra = ? "
                "WHERE character_id = ? AND container = ? AND slot = ?",
                (int(item_id), sqlite3.Binary(bytes(extra)), int(character_id),
                 int(container), int(slot)))
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

    def character_bags(self, character_id: int) -> list[dict]:
        """Every bag copy with its item metadata and augment text.

        The set editor's item picker reads this in one call and filters by the slot
        bit and the character's job.  Two copies of the same item can carry different
        augment blocks, so each row has its container/slot and the decoded rows.
        """
        rows = self.db.all(
            "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, ci.extra, "
            "COALESCE(i.name, 'Item ' || ci.item_id) AS name, "
            "COALESCE(i.equip_slot, '') AS equip_slot, "
            "COALESCE(i.slot_mask, 0) AS slot_mask, COALESCE(i.jobs, 0) AS jobs, "
            "COALESCE(i.level, 0) AS level, COALESCE(i.skill, 0) AS skill, "
            "COALESCE(i.subskill, 0) AS subskill, "
            "COALESCE(i.item_level, 0) AS item_level, "
            "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex "
            "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
            "WHERE ci.character_id = ? AND ci.item_id <> 65535 "
            "ORDER BY ci.container, ci.slot", (int(character_id),))
        out = []
        for row in rows:
            extra = bytes(row["extra"] or b"")
            out.append({
                "container": int(row["container"]),
                "slot": int(row["slot"]),
                "item_id": int(row["item_id"]),
                "quantity": int(row["quantity"]),
                "name": str(row["name"]),
                "equip_slot": str(row["equip_slot"]),
                "slot_mask": int(row["slot_mask"]),
                "jobs": int(row["jobs"]),
                "level": int(row["level"]),
                "skill": int(row["skill"]),
                "subskill": int(row["subskill"]),
                "item_level": int(row["item_level"]),
                "rare": int(row["rare"]),
                "ex": int(row["ex"]),
                "extra": extra.hex(),
                "augments": augment_stats.describe_augments(int(row["item_id"]), extra),
            })
        return out

    def character_all_items(self, character_id: int) -> list[dict]:
        """Every item a character owns, for the Magic Bag HUD.

        Visible bag rows keep their container/slot; the hidden Storage Slips and locker
        are returned as synthetic containers 100/101 with no slot, so one list can show
        the whole account-side collection.  ``source`` tells the HUD which action path a
        row uses.
        """
        out = []
        for row in self.character_bags(character_id):
            row = dict(row)
            row["source"] = "bag"
            out.append(row)
        for row in self.db.all(
                "SELECT cs.item_id, cs.quantity, cs.slip, "
                "COALESCE(i.name, 'Item ' || cs.item_id) AS name, "
                "COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.slot_mask, 0) AS slot_mask, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(i.level, 0) AS level, COALESCE(i.skill, 0) AS skill, "
                "COALESCE(i.item_level, 0) AS item_level, "
                "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex "
                "FROM char_storage cs LEFT JOIN items i ON i.item_id = cs.item_id "
                "WHERE cs.character_id = ? ORDER BY cs.slip, cs.item_id",
                (int(character_id),)):
            out.append({
                "source": "slip", "container": 100, "slot": 0,
                "item_id": int(row["item_id"]), "quantity": int(row["quantity"]),
                "name": str(row["name"]), "equip_slot": str(row["equip_slot"]),
                "slot_mask": int(row["slot_mask"]), "jobs": int(row["jobs"]),
                "level": int(row["level"]), "skill": int(row["skill"]),
                "item_level": int(row["item_level"]), "rare": int(row["rare"]),
                "ex": int(row["ex"]), "extra": "", "augments": [],
                "slip": int(row["slip"]),
            })
        # The Armory keeps a purchase record even after the item is consumed; expose it
        # as Claim Storage so the one Magic Bag list can account for every DB row.
        for row in self.db.all(
                "SELECT p.id AS purchase_id, p.item_id, p.quantity, p.price, p.created_at, "
                "COALESCE(i.name, 'Item ' || p.item_id) AS name, "
                "COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.slot_mask, 0) AS slot_mask, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(i.level, 0) AS level, COALESCE(i.skill, 0) AS skill, "
                "COALESCE(i.item_level, 0) AS item_level, "
                "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex "
                "FROM char_purchases p LEFT JOIN items i ON i.item_id = p.item_id "
                "WHERE p.character_id = ? ORDER BY p.id",
                (int(character_id),)):
            out.append({
                "source": "claim", "container": 102, "slot": 0,
                "item_id": int(row["item_id"]), "quantity": int(row["quantity"]),
                "name": str(row["name"]), "equip_slot": str(row["equip_slot"]),
                "slot_mask": int(row["slot_mask"]), "jobs": int(row["jobs"]),
                "level": int(row["level"]), "skill": int(row["skill"]),
                "item_level": int(row["item_level"]), "rare": int(row["rare"]),
                "ex": int(row["ex"]), "extra": "", "augments": [],
                "purchase_id": int(row["purchase_id"]), "price": int(row["price"]),
                "purchased_at": str(row["created_at"]),
            })
        for row in self.db.all(
                "SELECT cl.item_id, cl.quantity, COALESCE(cl.extra, X'') AS extra, "
                "COALESCE(i.name, 'Item ' || cl.item_id) AS name, "
                "COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.slot_mask, 0) AS slot_mask, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(i.level, 0) AS level, COALESCE(i.skill, 0) AS skill, "
                "COALESCE(i.item_level, 0) AS item_level, "
                "COALESCE(i.rare, 0) AS rare, COALESCE(i.ex, 0) AS ex "
                "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
                "WHERE cl.character_id = ? ORDER BY cl.item_id",
                (int(character_id),)):
            extra = bytes(row["extra"] or b"")
            out.append({
                "source": "locker", "container": 101, "slot": 0,
                "item_id": int(row["item_id"]), "quantity": int(row["quantity"]),
                "name": str(row["name"]), "equip_slot": str(row["equip_slot"]),
                "slot_mask": int(row["slot_mask"]), "jobs": int(row["jobs"]),
                "level": int(row["level"]), "skill": int(row["skill"]),
                "item_level": int(row["item_level"]), "rare": int(row["rare"]),
                "ex": int(row["ex"]), "extra": extra.hex(),
                "augments": augment_stats.describe_augments(int(row["item_id"]), extra),
            })
        return out

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
        Items whose values depend on character state rather than fixed data -- today the
        Hoxne Earring's Mastery Rank attributes -- are merged from :mod:`item_effects`.
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
        mastery_rank = (self._mastery_rank(int(character_id))
                        if any(int(row["item_id"]) == item_effects.HOXNE_EARRING
                               for row in equipped) else 0)
        for row in equipped:
            item_id = int(row["item_id"])
            try:
                augment_stats.add_item_mods(mods, item_id, row["extra"])
            except (KeyError, TypeError, ValueError):
                # A malformed block must never stop the outfit from loading.
                logging.getLogger("fanxi.stats").debug(
                    "augments unreadable for item %s", item_id, exc_info=True)
            item_effects.add_item_mods(mods, item_id, mastery_rank)
        # The +1 armor sets' tiered bonuses are not on any one piece's item_mods row.
        for bonus in set_bonuses.for_item_ids(int(row["item_id"]) for row in equipped):
            for mod_id, value in bonus.mods:
                mods[mod_id] = mods.get(mod_id, 0) + value
        return mods

    def _mastery_rank(self, character_id: int) -> int:
        """The stored Mastery Rank byte (0 when the character row is gone)."""
        row = self.db.one(
            "SELECT mastery_rank FROM characters WHERE id = ?", (int(character_id),))
        return int(row["mastery_rank"] or 0) if row is not None else 0

    def character_stat_report(self, character_id: int) -> dict:
        """The live checkparam-style sheet for a character in a zone.

        Buffs, food and the job-ability layer only exist in the game process, so this
        resolves the live session through the world the gateway attached rather than
        rebuilding the sheet from the database.
        """
        row = self.character(int(character_id))
        world = self.zone_world
        session = (world.session_by_character_ids(int(row["id"]), int(row["char_id"]))
                   if world is not None else None)
        if session is None:
            raise ApiError(404, "not_found", "character is not in a zone")
        return session.stat_report()

    def character_target_report(self, character_id: int, entity_id: int = 0) -> dict:
        """The live target's debuffs for the in-game Target Debuffs window."""
        row = self.character(int(character_id))
        world = self.zone_world
        session = (world.session_by_character_ids(int(row["id"]), int(row["char_id"]))
                   if world is not None else None)
        if session is None:
            raise ApiError(404, "not_found", "character is not in a zone")
        return session.target_effect_report(int(entity_id or 0))

    def equipped_slot_mods(self, character_id: int) -> list[dict]:
        """One row per equipped slot with that copy's modifiers, augments included.

        ``equipped_mods`` sums the outfit for the combat path; this keeps the same
        rows apart so the launcher can show which piece supplied a stat.  The inventory
        copy is joined by container/slot, which is what lets two copies of the same
        item id carry different augment blocks.  Character-state items (the Hoxne
        Earring) are resolved here too, so the report's gear rows add up to the same
        total combat uses.
        """
        rows = self.db.all(
            "SELECT e.kind, e.container, e.slot, e.item_id, "
            "COALESCE(i.name, 'Item ' || e.item_id) AS name, "
            "COALESCE(ci.extra, X'') AS extra "
            "FROM char_equip e "
            "LEFT JOIN items i ON i.item_id = e.item_id "
            "LEFT JOIN char_inventory ci ON ci.character_id = e.character_id "
            "  AND ci.container = e.container AND ci.slot = e.slot "
            "WHERE e.character_id = ? ORDER BY e.kind", (int(character_id),))
        mastery_rank = (self._mastery_rank(int(character_id))
                        if any(int(row["item_id"]) == item_effects.HOXNE_EARRING
                               for row in rows) else 0)
        out = []
        for row in rows:
            item_id = int(row["item_id"])
            mods = self.item_mods(item_id)
            try:
                augment_stats.add_item_mods(mods, item_id, row["extra"])
            except (KeyError, TypeError, ValueError):
                logging.getLogger("fanxi.stats").debug(
                    "augments unreadable for item %s", item_id, exc_info=True)
            item_effects.add_item_mods(mods, item_id, mastery_rank)
            try:
                augments = augment_stats.describe_augments(item_id, row["extra"])
            except (KeyError, TypeError, ValueError):
                augments = ""
            out.append({
                "kind": int(row["kind"]),
                "container": int(row["container"]),
                "slot": int(row["slot"]),
                "item_id": item_id,
                "name": str(row["name"]),
                "augments": augments,
                "mods": {int(key): int(value) for key, value in mods.items()},
            })
        return out

    def monster_steal_items(self, template_id: int) -> list[dict]:
        """The weighted steal table for one monster template."""
        return [dict(row) for row in self.db.all(
            "SELECT item_id, weight FROM monster_steal_items "
            "WHERE monster_template_id = ? ORDER BY item_id",
            (int(template_id),))]

    def equipped_weapons(self, character_id: int) -> dict[int, dict]:
        """Equip kind -> weapon data (skill, damage, delay, item-level skill, shield size).

        A slot holding something that is not a weapon (a shield in the sub slot, say) has
        no ``item_weapon`` row and comes back with zeroed weapon fields.  A shield carries
        its size in ``shield_size``; anything else has 0 there and is not a shield.

        ``dmg`` includes the copy's augment rows that raise the damage rating
        (``DMG:+12`` on an Oboro HQ2 path, ``Damage+18`` on a Telopanos weapon, a
        ``DMG:`` slot on a standard block): retail adds those to the weapon, not to
        a modifier, so the augmented rating is what the attack round must read.
        """
        rows = self.db.all(
            "SELECT e.kind, e.item_id, w.skill, w.dmg, w.delay, w.ilvl_skill, "
            "COALESCE(i.subskill, 0) AS subskill, "
            "i.item_level, s.size AS shield_size, COALESCE(ci.extra, X'') AS extra "
            "FROM char_equip e "
            "LEFT JOIN item_weapon w ON w.item_id = e.item_id "
            "LEFT JOIN items i ON i.item_id = e.item_id "
            "LEFT JOIN item_shield s ON s.item_id = e.item_id "
            "LEFT JOIN char_inventory ci ON ci.character_id = e.character_id "
            "AND ci.container = e.container AND ci.slot = e.slot "
            "WHERE e.character_id = ?", (int(character_id),))
        out: dict[int, dict] = {}
        for row in rows:
            weapon = dict(row)
            extra = weapon.pop("extra", b"")
            if int(weapon.get("dmg") or 0):
                try:
                    weapon["dmg"] = int(weapon["dmg"]) + augment_stats.weapon_damage(
                        int(weapon["item_id"]), extra)
                except (KeyError, TypeError, ValueError):
                    # A malformed block must never stop the weapon from loading.
                    logging.getLogger("fanxi.stats").debug(
                        "augment damage unreadable for item %s", weapon["item_id"],
                        exc_info=True)
            out[int(weapon["kind"])] = weapon
        return out

    def save_equipment(self, character_id: int, equipped: dict) -> None:
        """Replace the stored outfit with the current one (kind -> (container, slot, item))."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM char_equip WHERE character_id = ?", (int(character_id),))
            for kind, (container, slot, item_id) in sorted(equipped.items()):
                conn.execute(
                    "INSERT INTO char_equip (character_id, kind, container, slot, item_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (int(character_id), int(kind), int(container), int(slot), int(item_id)))

    def save_style_lock(self, character_id: int, locked: bool, models: dict[int, int],
                        types: dict[int, int] | None = None) -> None:
        """Persist /lockstyle and the appearance models and weapon types it locked in.

        ``models`` uses the client's equip kinds (0 main, 1 sub, 2 ranged, 4..8 armour).
        ``types`` is the weapon type in each hand (0 main, 1 sub); a later same-type swap
        keeps the locked model, so the client never sees a new grap list to repaint.
        Keeping both on the character row means a relog does not blink back to the
        current gear, and a later /lockstyle off can simply return to the real look.
        """
        columns = {
            0: "style_main", 1: "style_sub", 2: "style_ranged", 4: "style_head",
            5: "style_body", 6: "style_hands", 7: "style_legs", 8: "style_feet",
        }
        values = {name: int(models.get(kind) or 0) for kind, name in columns.items()}
        type_columns = {0: "style_main_type", 1: "style_sub_type"}
        type_values = {name: int((types or {}).get(kind) or 0)
                       for kind, name in type_columns.items()}
        self.db.execute(
            "UPDATE characters SET style_lock = ?, style_main = ?, style_sub = ?, "
            "style_ranged = ?, style_head = ?, style_body = ?, style_hands = ?, "
            "style_legs = ?, style_feet = ?, style_main_type = ?, style_sub_type = ?, "
            "updated_at = ? WHERE id = ?",
            (1 if locked else 0, values["style_main"], values["style_sub"],
             values["style_ranged"], values["style_head"], values["style_body"],
             values["style_hands"], values["style_legs"], values["style_feet"],
             type_values["style_main_type"], type_values["style_sub_type"],
             now_iso(), int(character_id)),
        )

    def spell_by_name(self, name: str) -> dict | None:
        """Look a spell up by display name, ignoring case and spacing."""
        wanted = "".join(str(name).split()).casefold()
        for row in self.db.all("SELECT * FROM spells ORDER BY id"):
            if "".join(str(row["name"]).split()).casefold() == wanted:
                return dict(row)
        return None

    @lru_cache(maxsize=1)
    def spell_ids_by_name(self) -> dict[str, tuple[int, ...]]:
        """Spell name -> the ids carrying it, normalised like ``spell_by_name``.

        A job-point gift names its spell, not its id (LandSandBoat resolves a
        ``SpellID`` at compile time; Fanxi's data is the spells table), so the zone
        resolves the gift names once per job pair through this index.
        """
        out: dict[str, list[int]] = {}
        for row in self.db.all("SELECT id, name FROM spells ORDER BY id"):
            key = "".join(str(row["name"] or "").split()).casefold()
            if key:
                out.setdefault(key, []).append(int(row["id"]))
        return {key: tuple(ids) for key, ids in out.items()}

    @lru_cache(maxsize=1)
    def _spell_levels(self) -> dict[int, tuple[tuple[int, int], ...]]:
        """Spell id -> ((job, level), ...) from ``data/spell_levels.json``.

        Retail gates a spell by the levels its jobs learn it at; a spell with no row
        (a Trust, a job-point or merit spell, a monster-only id) is not level-gated.
        """
        try:
            raw = json.loads(SPELL_LEVELS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        out: dict[int, tuple[tuple[int, int], ...]] = {}
        for spell_id, entries in (raw.get("spells") or {}).items():
            try:
                out[int(spell_id)] = tuple((int(job), int(level)) for job, level in entries)
            except (TypeError, ValueError):
                continue
        return out

    def spell_levels(self, spell_id: int) -> tuple[tuple[int, int], ...]:
        """The (job, level) pairs that learn this spell, empty when it is not gated."""
        return self._spell_levels().get(int(spell_id), ())

    def spell_level_table(self) -> dict[int, tuple[tuple[int, int], ...]]:
        """Every gated spell's (job, level) rows, for building the client's bitmap."""
        return self._spell_levels()

    @lru_cache(maxsize=1)
    def _weaponskill_properties(self) -> dict[int, tuple[int, int, int]]:
        """Weapon skill id -> its three skillchain property ids (0 when unset)."""
        try:
            raw = json.loads(WEAPON_SKILL_PROPERTIES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        out: dict[int, tuple[int, int, int]] = {}
        for key, props in (raw.get("weapon_skills") or {}).items():
            try:
                values = [int(value) for value in props][:3]
            except (TypeError, ValueError):
                continue
            values.extend([0] * (3 - len(values)))
            out[int(key)] = (values[0], values[1], values[2])
        return out

    def weaponskill_properties(self, ws_id: int) -> tuple[int, int, int]:
        """The (primary, secondary, tertiary) skillchain properties of a weapon skill."""
        return self._weaponskill_properties().get(int(ws_id), (0, 0, 0))

    def spell(self, spell_id: int) -> dict | None:
        """One spell row: name, MP cost, cast time and the client's animation id."""
        row = self.db.one("SELECT * FROM spells WHERE id = ?", (int(spell_id),))
        return dict(row) if row else None

    def trust_gear(self, trust_spell_id: int) -> list[int]:
        """The item ids one Trust carries (migration 159), in item order."""
        rows = self.db.all(
            "SELECT item_id FROM trust_gear WHERE trust_spell_id = ? ORDER BY item_id",
            (int(trust_spell_id),))
        return [int(row["item_id"]) for row in rows]

    def equipped_gear_rating(self, character_id: int) -> int:
        """The average item level of the worn pieces, 0 when none of them carry one.

        This is the "how well geared is the Master" number a Trust's share scales with;
        older level-75 gear and empty slots contribute nothing.
        """
        row = self.db.one(
            "SELECT AVG(i.item_level) AS rating FROM char_equip e "
            "JOIN items i ON i.item_id = e.item_id "
            "WHERE e.character_id = ? AND i.item_level > 0", (int(character_id),))
        return int(row["rating"] or 0) if row is not None else 0

    def trust(self, spell_id: int) -> dict | None:
        """The alter ego a Trust spell calls, or None for an ordinary spell."""
        row = self.db.one("SELECT * FROM trusts WHERE spell_id = ?", (int(spell_id),))
        return dict(row) if row else None

    def trust_spells(self, trust_spell_id: int, level: int = 255) -> list[dict]:
        """The spells one alter ego has unlocked at ``level`` (migration 117)."""
        rows = self.db.all(
            "SELECT s.*, ts.min_level, ts.max_level FROM trust_spells ts "
            "JOIN spells s ON s.id = ts.spell_id "
            "WHERE ts.trust_spell_id = ? AND ts.min_level <= ? AND ts.max_level >= ? "
            "ORDER BY s.id",
            (int(trust_spell_id), int(level), int(level)))
        return [dict(row) for row in rows]

    def trust_action_spells(self, trust_spell_id: int, level: int = 255) -> list[dict]:
        """Every spell a support Trust can choose, not just its curated rotation.

        The importer's ``trust_spells`` rows are the spells retail's alter ego actually
        uses by default; they are not the full spellbook.  A player customising a
        support Trust should be able to choose the job's other spells too, and Sylvie
        should see every Indi-/Geo- spell rather than the handful in her imported list.
        This merges the curated rows with every spell the Trust's main job (up to
        ``level``) and support job (up to the level-49 subjob cap) can cast, plus all
        Indi-/Geo- spells for a Geomancer.
        """
        level = max(1, min(255, int(level)))
        trust = self.trust(trust_spell_id) or {}
        main_job = int(trust.get("job") or 0)
        sub_job = int(trust.get("sub_job") or 0)
        rows: dict[int, dict] = {}
        for spell in self.trust_spells(trust_spell_id, level):
            item = dict(spell)
            item.setdefault("max_level", 255)
            rows[int(item["id"])] = item

        trust_ids = {int(row["spell_id"]) for row in self.db.all(
            "SELECT spell_id FROM trusts")}
        allowed = [(main_job, level)]
        if sub_job:
            allowed.append((sub_job, min(49, level)))

        def add(spell_id: int, min_level: int) -> None:
            spell_id = int(spell_id)
            if spell_id <= 0 or spell_id in trust_ids:
                return
            current = rows.get(spell_id)
            if current is not None:
                current["min_level"] = min(int(current.get("min_level") or min_level),
                                            int(min_level))
                return
            spell = self.spell(spell_id)
            if spell is None:
                return
            item = dict(spell)
            item["min_level"] = int(min_level)
            item["max_level"] = 255
            rows[spell_id] = item

        table = self.spell_level_table()
        for spell_id, entries in table.items():
            if int(spell_id) in trust_ids:
                continue
            available = None
            for job, spell_level in entries:
                for allowed_job, cap in allowed:
                    if int(job) == int(allowed_job) and int(spell_level) <= int(cap):
                        available = (int(spell_level) if available is None
                                     else min(available, int(spell_level)))
            if available is not None:
                add(int(spell_id), available)

        # Job-point gift spells have no ordinary level row (Refresh III, Temper II, …),
        # but a level-99 main job can use them, so a custom support set should see them.
        if level >= 99 and main_job:
            by_name = self.spell_ids_by_name()
            for name in job_points.spell_grants(main_job):
                key = "".join(str(name).split()).casefold()
                for spell_id in by_name.get(key, ()):
                    add(int(spell_id), 99)

        # Sylvie (UC) is the only Geomancer support Trust.  Every Indi-/Geo- spell is
        # selectable even if it is not in her imported mob_spell_list; the picker labels
        # the Indi- and Geo- families separately through the normal kit classifier.
        if main_job == 21 or sub_job == 21:
            for name, ids in self.spell_ids_by_name().items():
                if not str(name).casefold().startswith(("indi-", "geo-")):
                    continue
                for spell_id in ids:
                    matched = [int(spell_level)
                               for job, spell_level in table.get(int(spell_id), ())
                               if int(job) == 21 and int(spell_level) <= level]
                    add(int(spell_id), min(matched) if matched else 1)

        return sorted(rows.values(), key=lambda row: int(row["id"]))

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
        """The client's xi.skill type for a weapon item, or 0 for shields/grips/unknown.

        ``item_weapon.skill`` is the combat table's authoritative type and is always
        present for a real weapon.  The GearSwap default-library rows (migration 66)
        predate the full catalogue and kept ``items.skill`` 0 through migration 111's
        upsert, which only refreshes price/flags; migration 170 fills those rows in.
        Fall back to the weapon row anyway so a database that has not run 170 yet, or
        another hand-written item, cannot make the equipped weapon look non-weapon and
        drop its whole weapon-skill menu (a COR's Armageddon lost Marksmanship and the
        HUD's Wildfire tab until a Sword skill set equipped a skill-26 gun).
        """
        row = self.db.one(
            "SELECT COALESCE(NULLIF(i.skill, 0), w.skill, 0) AS skill "
            "FROM items i LEFT JOIN item_weapon w ON w.item_id = i.item_id "
            "WHERE i.item_id = ?", (int(item_id),))
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
            "WHERE e.character_id = ? AND m.mod_id = ?",
            (int(character_id), int(mod.ADDS_WEAPONSKILL)))
        return {int(row["ws_id"]) for row in rows}

    def prime_weapon(self, item_id: int) -> prime_weapons.PrimeWeapon | None:
        """The Prime-weapon stage for an item, or None when it is not a Prime weapon.

        A Prime weapon's ``355`` modifier names its own skill, and the item's damage
        rank inside that family is its stage: highest is the iL119 III stage 5, the next
        is the iL119 II stage 4, and the third is the iL119 stage 3.  Stage 3 items do
        not carry ``355`` on this server, so in practice only stages 4 and 5 reach here.
        The result is cached because the item table is static until a migration.
        """
        item_id = int(item_id)
        if item_id in self._prime_weapon_cache:
            return self._prime_weapon_cache[item_id]
        result = None
        row = self.db.one(
            "SELECT value FROM item_mods WHERE item_id = ? AND mod_id = ? LIMIT 1",
            (item_id, int(mod.ADDS_WEAPONSKILL)))
        if row is not None:
            ws_id = int(row["value"])
            if ws_id in prime_weapons.PRIME_WEAPON_SKILLS:
                rows = self.db.all(
                    "SELECT m.item_id AS item_id FROM item_mods m "
                    "JOIN item_weapon w ON w.item_id = m.item_id "
                    "WHERE m.mod_id = ? AND m.value = ? "
                    "ORDER BY w.dmg DESC, m.item_id DESC",
                    (int(mod.ADDS_WEAPONSKILL), ws_id))
                rank = next((index for index, sibling in enumerate(rows)
                             if int(sibling["item_id"]) == item_id), None)
                stages = (5, 4, 3)
                if rank is not None and rank < len(stages):
                    result = prime_weapons.PrimeWeapon(
                        item_id=item_id, ws_id=ws_id, stage=stages[rank])
        self._prime_weapon_cache[item_id] = result
        return result

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

    def item_mods(self, item_id: int) -> dict[int, int]:
        """Modifier id -> value for one item, without per-copy augments.

        ``equipped_mods`` is the total an outfit contributes.  This is the one-item view,
        which the attack round needs to tell the swinging weapon's own "Sword
        enhancement spell damage"+n apart from the other hand's.
        """
        rows = self.db.all(
            "SELECT mod_id, value FROM item_mods WHERE item_id = ?", (int(item_id),))
        return {int(row["mod_id"]): int(row["value"]) for row in rows}

    def equipped_item_mods(self, character_id: int, item_id: int) -> dict[int, int]:
        """One equipped item's modifiers, including the augment block of that copy.

        A weapon's own "Sword enhancement spell damage" line applies only to that
        weapon, so the attack round subtracts the *other* hand's line from the outfit
        total.  The other weapon may carry its line in a Dynamis-Divergence augment
        (Crocea Mors path C is +500%), which ``item_mods`` alone cannot see.  A
        character-state item's row (the Hoxne Earring) is included as well.
        """
        mods = self.item_mods(item_id)
        row = self.db.one(
            "SELECT COALESCE(i.extra, X'') AS extra FROM char_equip e "
            "LEFT JOIN char_inventory i ON i.character_id = e.character_id "
            "AND i.container = e.container AND i.slot = e.slot "
            "WHERE e.character_id = ? AND e.item_id = ? LIMIT 1",
            (int(character_id), int(item_id)))
        if row is not None:
            try:
                augment_stats.add_item_mods(mods, int(item_id), row["extra"])
            except (KeyError, TypeError, ValueError):
                pass
            item_effects.add_item_mods(
                mods, int(item_id), self._mastery_rank(int(character_id)))
        return mods

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

    def dispense_items(self) -> list[dict]:
        """Every charged dispense item (RMEA pouches and quivers), keyed by item id."""
        return [dict(row) for row in self.db.all(
            "SELECT item_id, ammo_id, quantity, max_charges, use_delay, reuse_delay, "
            "cast_time, animation FROM item_dispense ORDER BY item_id")]

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

    def save_merit_layout(self, character_id: int, upgrades, *, spend: bool = False) -> dict:
        """Assign a batch of merit ranks, validating row and category caps.

        ``upgrades`` maps a merit id (or its decimal string) to its new absolute rank.
        Only the rows the launcher sends are changed, so a form can apply just the
        menus the player touched.  ``spend`` charges the net point difference against
        the unspent pool and refunds it when ranks are lowered; the Data page's editor
        leaves it off so a character can be laid out like the other assignment cards.
        """
        if not isinstance(upgrades, dict):
            raise ApiError(422, "validation_error",
                           "send upgrades as a merit id -> ranks object")
        counts = self.merits_for_character(int(character_id))
        new_counts = dict(counts)
        for raw_id, raw_value in upgrades.items():
            try:
                merit_id = int(raw_id)
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error",
                               "merit ids must be whole numbers")
            if merit_id not in merit_table.MERITS:
                raise ApiError(422, "validation_error",
                               "unknown merit id %s" % merit_id)
            if isinstance(raw_value, bool) or (
                    isinstance(raw_value, float) and not raw_value.is_integer()):
                raise ApiError(422, "validation_error",
                               "merit ranks must be whole numbers")
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                raise ApiError(422, "validation_error",
                               "merit ranks must be whole numbers")
            maximum = merit_table.max_upgrades(merit_id)
            if not 0 <= value <= maximum:
                name = merit_menus.MERIT_NAMES.get(merit_id, "this merit")
                raise ApiError(422, "validation_error",
                               "%s is between 0 and %d ranks" % (name, maximum))
            new_counts[merit_id] = value

        category_totals: dict[int, int] = {}
        old_totals: dict[int, int] = {}
        for merit_id, value in new_counts.items():
            category = merit_table.category_of(merit_id)
            if category is None:
                continue
            category_totals[category] = category_totals.get(category, 0) + int(value)
        for merit_id, value in counts.items():
            category = merit_table.category_of(merit_id)
            if category is None:
                continue
            old_totals[category] = old_totals.get(category, 0) + int(value)
        for category, total in category_totals.items():
            maximum = int(merit_table.CATEGORY_MAX.get(category, 0))
            # A character assigned outside this editor can already hold more than the
            # menu's cap.  Let those characters be lowered or reshuffled; only a layout
            # that pushes the category further over its cap is refused.
            if total > maximum and total > old_totals.get(category, 0):
                name = merit_menus.CATEGORY_INFO[category]["name"]
                raise ApiError(422, "merit_category_full",
                               "%s allows %d upgrades; this layout asks for %d"
                               % (name, maximum, total))

        old_cost = merit_table.total_cost(counts)
        new_cost = merit_table.total_cost(new_counts)
        delta = new_cost - old_cost
        character = self.character(int(character_id))
        points = max(0, int(character.get("merit_points") or 0))
        if spend:
            if delta > points:
                raise ApiError(422, "insufficient_merit_points",
                               "this layout needs %d more merit points than the character has"
                               % (delta - points))
            new_cap = min(255, 127 + max(0, int(new_counts.get(0x0044, 0))))
            points = min(new_cap, max(0, points - delta))

        changed = {merit_id: value for merit_id, value in new_counts.items()
                   if int(counts.get(merit_id, 0)) != int(value)}
        if changed or spend:
            with self.db.transaction() as conn:
                for merit_id, value in changed.items():
                    if value <= 0:
                        conn.execute(
                            "DELETE FROM char_merits WHERE character_id = ? AND merit_id = ?",
                            (int(character_id), int(merit_id)))
                    else:
                        conn.execute(
                            "INSERT INTO char_merits (character_id, merit_id, upgrades) "
                            "VALUES (?, ?, ?) ON CONFLICT(character_id, merit_id) "
                            "DO UPDATE SET upgrades = excluded.upgrades",
                            (int(character_id), int(merit_id), int(value)))
                if spend:
                    conn.execute(
                        "UPDATE characters SET merit_points = ?, updated_at = ? WHERE id = ?",
                        (int(points), now_iso(), int(character_id)))
        return new_counts

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
        if int(from_container) == CONTAINER_RECYCLE or int(to_container) == CONTAINER_RECYCLE:
            return False
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

    def drop_item(self, character_id: int, container: int, slot: int,
                  quantity: int = 1) -> dict | None:
        """Move a stack to the Recycle Bin (C2S 0x028); return the source slot's new state.

        The client's Drop action is the Recycle Bin, not destruction.  The stack leaves
        its bag, lands in container 17 with ``dropped_at``, and can be restored for 30
        days.  A partial drop leaves the rest in the source slot.  Gil is never
        droppable, the Recycle Bin itself cannot be dropped into, and a full bin leaves
        the item where it is.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT item_id, quantity, COALESCE(extra, X'') AS extra "
                "FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), int(container), int(slot))).fetchone()
            if row is None:
                return None
            item_id, have = int(row["item_id"]), int(row["quantity"])
            if item_id == 65535 or have <= 0 or int(container) == CONTAINER_RECYCLE:
                return None
            take = min(max(1, int(quantity)), have)
            extra = bytes(row["extra"] or b"")
            stack = int(conn.execute(
                "SELECT COALESCE(stack, 1) FROM items WHERE item_id = ?",
                (item_id,)).fetchone()[0] or 1)
            # Reuse a matching Recycle Bin stack with room before taking a new slot.
            destination = None
            for candidate in conn.execute(
                    "SELECT slot, quantity FROM char_inventory "
                    "WHERE character_id = ? AND container = ? AND item_id = ? AND extra = ? "
                    "ORDER BY slot", (int(character_id), CONTAINER_RECYCLE, item_id,
                                      sqlite3.Binary(extra))):
                if int(candidate["quantity"]) + take <= stack:
                    destination = int(candidate["slot"])
                    break
            if destination is None:
                occupied = {int(r["slot"]) for r in conn.execute(
                    "SELECT slot FROM char_inventory WHERE character_id = ? "
                    "AND container = ?", (int(character_id), CONTAINER_RECYCLE))}
                destination = next((candidate for candidate in range(1, CONTAINER_SLOTS)
                                    if candidate not in occupied), None)
            if destination is None:
                return {"item_id": item_id, "container": int(container), "slot": int(slot),
                        "quantity": have, "recycled": 0, "recycle_full": True}
            conn.execute(
                "INSERT INTO char_inventory "
                "(character_id, container, slot, item_id, quantity, extra, dropped_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(character_id, container, slot) DO UPDATE SET "
                "item_id = excluded.item_id, quantity = quantity + excluded.quantity, "
                "extra = excluded.extra, dropped_at = excluded.dropped_at",
                (int(character_id), CONTAINER_RECYCLE, int(destination), item_id, take,
                 sqlite3.Binary(extra), now_iso()))
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
            return {"item_id": item_id, "container": int(container), "slot": int(slot),
                    "quantity": left, "recycled": take,
                    "recycle_slot": int(destination)}

    def restore_recycle_item(self, character_id: int, slot: int,
                             quantity: int | None = None) -> dict | None:
        """Take a stack back out of the Recycle Bin into the normal inventory.

        Restored items are usable again immediately.  The inventory is the destination
        (the point of the Recycle Bin is that the item is not equipped or used while it
        is inside); if the inventory is full the item stays in the bin.
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT item_id, quantity, COALESCE(extra, X'') AS extra "
                "FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), CONTAINER_RECYCLE, int(slot))).fetchone()
            if row is None:
                return None
            item_id, have = int(row["item_id"]), int(row["quantity"])
            take = have if quantity is None else min(max(1, int(quantity)), have)
            extra = bytes(row["extra"] or b"")
            stack = int(conn.execute(
                "SELECT COALESCE(stack, 1) FROM items WHERE item_id = ?",
                (item_id,)).fetchone()[0] or 1)
            destination = None
            for candidate in conn.execute(
                    "SELECT slot, quantity FROM char_inventory "
                    "WHERE character_id = ? AND container = 0 AND item_id = ? AND extra = ? "
                    "ORDER BY slot", (int(character_id), item_id, sqlite3.Binary(extra))):
                if int(candidate["quantity"]) + take <= stack:
                    destination = int(candidate["slot"])
                    break
            if destination is None:
                occupied = {int(r["slot"]) for r in conn.execute(
                    "SELECT slot FROM char_inventory WHERE character_id = ? AND container = 0",
                    (int(character_id),))}
                destination = next((candidate for candidate in range(1, CONTAINER_SLOTS)
                                    if candidate not in occupied), None)
            if destination is None:
                return {"item_id": item_id, "quantity": have, "restored": 0,
                        "inventory_full": True}
            conn.execute(
                "INSERT INTO char_inventory "
                "(character_id, container, slot, item_id, quantity, extra) "
                "VALUES (?, 0, ?, ?, ?, ?) "
                "ON CONFLICT(character_id, container, slot) DO UPDATE SET "
                "item_id = excluded.item_id, quantity = quantity + excluded.quantity, "
                "extra = excluded.extra",
                (int(character_id), destination, item_id, take, sqlite3.Binary(extra)))
            left = have - take
            if left > 0:
                conn.execute(
                    "UPDATE char_inventory SET quantity = ? "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (left, int(character_id), CONTAINER_RECYCLE, int(slot)))
            else:
                conn.execute(
                    "DELETE FROM char_inventory "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (int(character_id), CONTAINER_RECYCLE, int(slot)))
            return {"item_id": item_id, "slot": int(destination),
                    "quantity": take, "restored": take, "left": left}

    def pull_magic_item(self, character_id: int, source: str, item_id: int,
                        extra: bytes = b"", quantity: int | None = None) -> dict | None:
        """Move one exact stack from the hidden slips/locker into the inventory.

        This is the HUD's Pull button for a row that is not in a client bag.  The source
        row is removed only after the inventory row is written; a full inventory leaves
        it where it was.
        """
        source = str(source or "").casefold()
        if source not in ("slip", "locker"):
            return None
        with self.db.transaction() as conn:
            if source == "slip":
                row = conn.execute(
                    "SELECT quantity FROM char_storage WHERE character_id = ? AND item_id = ?",
                    (int(character_id), int(item_id))).fetchone()
                extra = b""
            else:
                row = conn.execute(
                    "SELECT quantity FROM char_locker "
                    "WHERE character_id = ? AND item_id = ? AND extra = ?",
                    (int(character_id), int(item_id), sqlite3.Binary(bytes(extra)))).fetchone()
            if row is None:
                return None
            have = int(row["quantity"])
            take = have if quantity is None else min(max(1, int(quantity)), have)
            stack = int(conn.execute(
                "SELECT COALESCE(stack, 1) FROM items WHERE item_id = ?",
                (int(item_id),)).fetchone()[0] or 1)
            destination = None
            for candidate in conn.execute(
                    "SELECT slot, quantity FROM char_inventory "
                    "WHERE character_id = ? AND container = 0 AND item_id = ? AND extra = ? "
                    "ORDER BY slot", (int(character_id), int(item_id),
                                      sqlite3.Binary(bytes(extra)))):
                if int(candidate["quantity"]) + take <= stack:
                    destination = int(candidate["slot"])
                    break
            if destination is None:
                occupied = {int(r["slot"]) for r in conn.execute(
                    "SELECT slot FROM char_inventory WHERE character_id = ? AND container = 0",
                    (int(character_id),))}
                destination = next((candidate for candidate in range(1, CONTAINER_SLOTS)
                                    if candidate not in occupied), None)
            if destination is None:
                return {"item_id": int(item_id), "quantity": have, "pulled": 0,
                        "inventory_full": True}
            conn.execute(
                "INSERT INTO char_inventory "
                "(character_id, container, slot, item_id, quantity, extra) "
                "VALUES (?, 0, ?, ?, ?, ?) "
                "ON CONFLICT(character_id, container, slot) DO UPDATE SET "
                "item_id = excluded.item_id, quantity = quantity + excluded.quantity, "
                "extra = excluded.extra",
                (int(character_id), destination, int(item_id), take,
                 sqlite3.Binary(bytes(extra))))
            left = have - take
            if source == "slip":
                if left:
                    conn.execute(
                        "UPDATE char_storage SET quantity = ? "
                        "WHERE character_id = ? AND item_id = ?",
                        (left, int(character_id), int(item_id)))
                else:
                    conn.execute(
                        "DELETE FROM char_storage WHERE character_id = ? AND item_id = ?",
                        (int(character_id), int(item_id)))
            else:
                if left:
                    conn.execute(
                        "UPDATE char_locker SET quantity = ? "
                        "WHERE character_id = ? AND item_id = ? AND extra = ?",
                        (left, int(character_id), int(item_id),
                         sqlite3.Binary(bytes(extra))))
                else:
                    conn.execute(
                        "DELETE FROM char_locker WHERE character_id = ? "
                        "AND item_id = ? AND extra = ?",
                        (int(character_id), int(item_id), sqlite3.Binary(bytes(extra))))
            return {"item_id": int(item_id), "slot": int(destination),
                    "quantity": take, "pulled": take, "left": left, "source": source}

    def store_visible_in_locker(self, character_id: int, container: int, slot: int,
                                quantity: int | None = None) -> dict | None:
        """Move one visible bag slot into the hidden 9,999-slot Magic Bag."""
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT item_id, quantity, COALESCE(extra, X'') AS extra "
                "FROM char_inventory WHERE character_id = ? AND container = ? AND slot = ?",
                (int(character_id), int(container), int(slot))).fetchone()
            if row is None or int(row["item_id"]) == 65535:
                return None
            item_id, have = int(row["item_id"]), int(row["quantity"])
            take = have if quantity is None else min(max(1, int(quantity)), have)
            extra = bytes(row["extra"] or b"")
            existing = conn.execute(
                "SELECT quantity FROM char_locker WHERE character_id = ? "
                "AND item_id = ? AND extra = ?",
                (int(character_id), item_id, sqlite3.Binary(extra))).fetchone()
            slots = int(conn.execute(
                "SELECT COUNT(*) FROM char_locker WHERE character_id = ?",
                (int(character_id),)).fetchone()[0])
            if existing is None and slots >= LOCKER_CAPACITY:
                return {"item_id": item_id, "quantity": have, "stored": 0,
                        "locker_full": True}
            conn.execute(
                "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(character_id, item_id, extra) "
                "DO UPDATE SET quantity = quantity + excluded.quantity",
                (int(character_id), item_id, sqlite3.Binary(extra), take))
            left = have - take
            if left:
                conn.execute(
                    "UPDATE char_inventory SET quantity = ? "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (left, int(character_id), int(container), int(slot)))
            else:
                conn.execute(
                    "DELETE FROM char_inventory "
                    "WHERE character_id = ? AND container = ? AND slot = ?",
                    (int(character_id), int(container), int(slot)))
            return {"item_id": item_id, "stored": take, "left": left,
                    "locker_slot": slots + (1 if existing is None else 0)}

    def purge_recycle(self, character_id: int | None = None) -> int:
        """Delete Recycle Bin rows whose 30 days are up; return how many slots went."""
        cutoff = iso(utcnow() - timedelta(days=RECYCLE_DAYS))
        with self.db.transaction() as conn:
            if character_id is None:
                cursor = conn.execute(
                    "DELETE FROM char_inventory WHERE container = ? "
                    "AND dropped_at IS NOT NULL AND dropped_at < ?",
                    (CONTAINER_RECYCLE, cutoff))
            else:
                cursor = conn.execute(
                    "DELETE FROM char_inventory WHERE character_id = ? AND container = ? "
                    "AND dropped_at IS NOT NULL AND dropped_at < ?",
                    (int(character_id), CONTAINER_RECYCLE, cutoff))
            return int(cursor.rowcount or 0)

    def recycle_items(self, character_id: int) -> list[dict]:
        """The Recycle Bin contents with names and the time each stack has left."""
        rows = self.db.all(
            "SELECT ci.slot, ci.item_id, ci.quantity, COALESCE(ci.extra, X'') AS extra, "
            "COALESCE(ci.dropped_at, '') AS dropped_at, "
            "COALESCE(i.name, 'Item') AS name "
            "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
            "WHERE ci.character_id = ? AND ci.container = ? ORDER BY ci.slot",
            (int(character_id), CONTAINER_RECYCLE))
        return [dict(row) for row in rows]

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
                # Job capes are not slip items; the locker/cape grab owns them.
                if int(row["item_id"]) in capes.CAPE_IDS:
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

    # --- job storage ---------------------------------------------------------------------------

    @staticmethod
    def _job_mask(job: int) -> int:
        """The item-table job bit for one job id, with the same 1..22 rule as the client."""
        job = int(job)
        if not 1 <= job <= 22:
            raise ValueError("job must be 1..22")
        return 1 << (job - 1)

    @staticmethod
    def _auto_equipment(row) -> bool:
        """Is this row a single-copy piece of equipment the organizer may move?

        The 9,999 locker also holds consumables (Call Beast jugs, ammo stacks) and the
        player may keep materials there.  Those have a stack size above one or no equip
        slot; pulling them out on every job change would bury the wardrobes.  The
        organizer therefore moves single-copy gear only, and ``//locker`` remains the
        tool for everything else.
        """
        return (int(row["item_id"]) != 65535
                and int(row["jobs"] or 0) != 0
                and str(row["equip_slot"] or "").strip() != ""
                and int(row["stack"] or 1) == 1)

    @staticmethod
    def _equipped_slots(conn: sqlite3.Connection,
                        character_id: int) -> set[tuple[int, int]]:
        return {(int(row["container"]), int(row["slot"]))
                for row in conn.execute(
                    "SELECT container, slot FROM char_equip WHERE character_id = ?",
                    (int(character_id),))}

    @staticmethod
    def _next_free(occupied: dict[int, set[int]], container: int) -> int | None:
        """The first free slot in a bag (slot 0 is gil in the inventory, never free)."""
        for slot in range(1, CONTAINER_SLOTS):
            if slot not in occupied[container]:
                occupied[container].add(slot)
                return slot
        return None

    @staticmethod
    def _locker_totals(conn: sqlite3.Connection, character_id: int) -> tuple[int, int]:
        """Return ``(slots, items)``: distinct locker entries and their total quantity."""
        row = conn.execute(
            "SELECT COUNT(*) AS slots, COALESCE(SUM(quantity), 0) AS items "
            "FROM char_locker WHERE character_id = ?", (int(character_id),)).fetchone()
        return int(row["slots"] or 0), int(row["items"] or 0)

    def _stored_gear(self, character_id: int) -> list[dict]:
        """Slip and locker rows joined to their item, for //storage list and the status.

        ``source`` is ``slip`` or ``locker``; the two stores are presented as one
        storage because the player should not have to remember which 80-slot bag a
        piece used to live in.
        """
        rows = self.db.all(
            "SELECT 'slip' AS source, cs.item_id, cs.quantity, X'' AS extra, cs.slip, "
            "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
            "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.stack, 1) AS stack "
            "FROM char_storage cs LEFT JOIN items i ON i.item_id = cs.item_id "
            "WHERE cs.character_id = ? "
            "UNION ALL "
            "SELECT 'locker', cl.item_id, cl.quantity, COALESCE(cl.extra, X''), 0, "
            "COALESCE(i.name, 'Item'), COALESCE(i.jobs, 0), "
            "COALESCE(i.equip_slot, ''), COALESCE(i.stack, 1) "
            "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
            "WHERE cl.character_id = ?",
            (int(character_id), int(character_id)))
        return [dict(row) for row in rows]

    def storage_contents(self, character_id: int, job: int | None = None) -> list[dict]:
        """Stored gear, optionally limited to what one job can equip."""
        rows = self._stored_gear(character_id)
        if job is None:
            return rows
        mask = self._job_mask(job)
        return [row for row in rows
                if self._auto_equipment(row) and (int(row["jobs"]) & mask)]

    def storage_overview(self, character_id: int, job: int) -> dict:
        """Counts for //storage with no verb: both stores and the bags for other jobs."""
        mask = self._job_mask(job)
        stored = self._stored_gear(character_id)
        slip_total = sum(int(row["quantity"]) for row in stored if row["source"] == "slip")
        locker_items = sum(int(row["quantity"]) for row in stored if row["source"] == "locker")
        locker_slots = sum(1 for row in stored if row["source"] == "locker")
        stored_for_job = sum(
            int(row["quantity"]) for row in stored
            if self._auto_equipment(row) and (int(row["jobs"]) & mask))
        equipped = {(int(row["container"]), int(row["slot"])) for row in self.db.all(
            "SELECT container, slot FROM char_equip WHERE character_id = ?",
            (int(character_id),))}
        placeholders = ",".join("?" for _ in PERMANENT_BAGS)
        away = 0
        for row in self.db.all(
                "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                "COALESCE(i.jobs, 0) AS jobs, COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.stack, 1) AS stack "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container IN (%s)" % placeholders,
                (int(character_id), *PERMANENT_BAGS)):
            if not self._auto_equipment(row):
                continue
            if int(row["jobs"]) & mask:
                continue
            if (int(row["container"]), int(row["slot"])) in equipped:
                continue
            away += int(row["quantity"])
        return {"slip_total": slip_total,
                "locker_total": locker_items, "locker_items": locker_items,
                "locker_slots": locker_slots, "stored_for_job": stored_for_job,
                "away": away, "locker_capacity": LOCKER_CAPACITY}

    def storage_job_counts(self, character_id: int) -> dict:
        """Per-job stored counts and one shared bucket, for //storage list all."""
        counts = {job: 0 for job in range(1, 23)}
        shared = 0
        for row in self._stored_gear(character_id):
            if not self._auto_equipment(row):
                continue
            jobs = int(row["jobs"])
            quantity = int(row["quantity"])
            if jobs & (jobs - 1):
                shared += quantity
                continue
            job = jobs.bit_length()
            if 1 <= job <= 22:
                counts[job] += quantity
        return {"jobs": counts, "shared": shared}

    def organize_job_storage(self, character_id: int, job: int, *,
                             scope: str = "unusable", store: bool = True,
                             pull: bool = True, relocate: bool = True) -> dict:
        """Make the bags match one job: put away what it cannot equip, bring out what it can.

        Slip items go to ``char_storage``; gear without a slip -- the Ambuscade capes,
        relic weapons, job accessories -- goes to the hidden 9,999-slot locker, which is
        the "storage" the client's 80-slot Storage bag cannot represent.  A copy with a
        non-empty augment block always goes to the locker, because ``char_storage`` has
        no ``extra`` column and a slip would silently drop the augment.

        ``scope='unusable'`` moves everything the job cannot equip (the job-change and
        ``//storage organize`` rule); ``scope='exclusive'`` moves only that job's own
        gear (``//storage store <job>``).  Pulling mirrors it: ``unusable`` brings back
        every stored piece the job can equip, ``exclusive`` only its own.  Pulled gear
        fills the Mog Wardrobes in equip-slot order, then the inventory; the tidy moves
        the job's loose inventory/Safe pieces into the wardrobes too.  Equipped pieces
        and working stock never move, and every move is one transaction: the source row
        is deleted only after the destination row is written.
        """
        job = int(job)
        mask = self._job_mask(job)
        scope = str(scope or "unusable").casefold()
        if scope not in ("unusable", "exclusive"):
            raise ValueError("scope must be 'unusable' or 'exclusive'")
        with self.db.transaction() as conn:
            equipped = self._equipped_slots(conn, character_id)
            source_placeholders = ",".join("?" for _ in PERMANENT_BAGS)
            source_rows = conn.execute(
                "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                "COALESCE(ci.extra, X'') AS extra, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
                "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.stack, 1) AS stack, "
                "COALESCE(st.slip, 0) AS slip "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "LEFT JOIN item_storage st ON st.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container IN (%s) "
                "ORDER BY ci.container, ci.slot" % source_placeholders,
                (int(character_id), *PERMANENT_BAGS)).fetchall()
            locker_slots, locker_items = self._locker_totals(conn, character_id)
            stored: list[dict] = []
            stored_slip = stored_locker = locker_full = equipped_left = 0
            if store:
                for row in source_rows:
                    if not self._auto_equipment(row):
                        continue
                    jobs = int(row["jobs"])
                    if scope == "exclusive":
                        if jobs != mask:
                            continue
                    elif jobs & mask:
                        continue  # the job can equip it, so it stays out
                    source = (int(row["container"]), int(row["slot"]))
                    if source in equipped:
                        equipped_left += 1
                        continue
                    item_id = int(row["item_id"])
                    if item_id in WORKING_STOCK_IDS:
                        continue
                    quantity = int(row["quantity"])
                    extra = bytes(row["extra"] or b"")
                    slip = int(row["slip"] or 0)
                    if slip and not extra:
                        conn.execute(
                            "INSERT INTO char_storage (character_id, item_id, quantity, slip) "
                            "VALUES (?, ?, ?, ?) "
                            "ON CONFLICT(character_id, item_id) "
                            "DO UPDATE SET quantity = quantity + excluded.quantity",
                            (int(character_id), item_id, quantity, slip))
                        stored_slip += quantity
                        destination = "slip"
                    else:
                        existing = conn.execute(
                            "SELECT 1 FROM char_locker WHERE character_id = ? "
                            "AND item_id = ? AND extra = ?",
                            (int(character_id), item_id,
                             sqlite3.Binary(extra))).fetchone()
                        if existing is None and locker_slots >= LOCKER_CAPACITY:
                            locker_full += quantity
                            continue
                        conn.execute(
                            "INSERT INTO char_locker "
                            "(character_id, item_id, extra, quantity) VALUES (?, ?, ?, ?) "
                            "ON CONFLICT(character_id, item_id, extra) "
                            "DO UPDATE SET quantity = quantity + excluded.quantity",
                            (int(character_id), item_id, sqlite3.Binary(extra), quantity))
                        if existing is None:
                            locker_slots += 1
                        locker_items += quantity
                        stored_locker += quantity
                        destination = "locker"
                    conn.execute(
                        "DELETE FROM char_inventory WHERE character_id = ? "
                        "AND container = ? AND slot = ?",
                        (int(character_id), source[0], source[1]))
                    stored.append({
                        "from_container": source[0], "from_slot": source[1],
                        "item_id": item_id, "quantity": quantity,
                        "name": str(row["name"] or "Item"),
                        "extra": extra, "slip": slip, "destination": destination,
                    })

            pulled: list[dict] = []
            pulled_slip = pulled_locker = remaining = 0
            occupied = {container: set() for container in ORGANIZE_DESTINATIONS}
            destination_placeholders = ",".join("?" for _ in ORGANIZE_DESTINATIONS)
            for row in conn.execute(
                    "SELECT container, slot FROM char_inventory WHERE character_id = ? "
                    "AND container IN (%s)" % destination_placeholders,
                    (int(character_id), *ORGANIZE_DESTINATIONS)):
                occupied[int(row["container"])].add(int(row["slot"]))
            if pull:
                candidates = conn.execute(
                    "SELECT 'slip' AS source, cs.item_id, cs.quantity, X'' AS extra, cs.slip, "
                    "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
                    "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.stack, 1) AS stack "
                    "FROM char_storage cs LEFT JOIN items i ON i.item_id = cs.item_id "
                    "WHERE cs.character_id = ? "
                    "UNION ALL "
                    "SELECT 'locker', cl.item_id, cl.quantity, COALESCE(cl.extra, X''), 0, "
                    "COALESCE(i.name, 'Item'), COALESCE(i.jobs, 0), "
                    "COALESCE(i.equip_slot, ''), COALESCE(i.stack, 1) "
                    "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
                    "WHERE cl.character_id = ?",
                    (int(character_id), int(character_id))).fetchall()
                candidates = [row for row in candidates
                              if self._auto_equipment(row)
                              and ((int(row["jobs"]) == mask) if scope == "exclusive"
                                   else bool(int(row["jobs"]) & mask))]
                candidates.sort(key=lambda row: (
                    EQUIP_ORDER.get(str(row["equip_slot"] or ""), 99),
                    str(row["name"] or "").casefold(), int(row["item_id"]),
                    bytes(row["extra"] or b"")))
                for row in candidates:
                    source = str(row["source"])
                    item_id = int(row["item_id"])
                    extra = bytes(row["extra"] or b"")
                    left = int(row["quantity"])
                    stack = max(1, int(row["stack"] or 1))
                    moved_qty = 0
                    while left > 0:
                        target = None
                        for container in ORGANIZE_DESTINATIONS:
                            slot = self._next_free(occupied, container)
                            if slot is not None:
                                target = (container, slot)
                                break
                        if target is None:
                            break
                        put = min(left, stack)
                        conn.execute(
                            "INSERT INTO char_inventory "
                            "(character_id, container, slot, item_id, quantity, extra) "
                            "VALUES (?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT(character_id, container, slot) "
                            "DO UPDATE SET item_id = excluded.item_id, "
                            "quantity = excluded.quantity, extra = excluded.extra",
                            (int(character_id), target[0], target[1], item_id, put,
                             sqlite3.Binary(extra)))
                        pulled.append({
                            "to_container": target[0], "to_slot": target[1],
                            "item_id": item_id, "quantity": put,
                            "name": str(row["name"] or "Item"),
                            "extra": extra, "source": source,
                        })
                        left -= put
                        moved_qty += put
                    if moved_qty:
                        if source == "slip":
                            pulled_slip += moved_qty
                        else:
                            pulled_locker += moved_qty
                    if not moved_qty:
                        remaining += int(row["quantity"])
                        continue
                    if left:
                        remaining += left
                        if source == "slip":
                            conn.execute(
                                "UPDATE char_storage SET quantity = ? "
                                "WHERE character_id = ? AND item_id = ?",
                                (left, int(character_id), item_id))
                        else:
                            conn.execute(
                                "UPDATE char_locker SET quantity = ? "
                                "WHERE character_id = ? AND item_id = ? AND extra = ?",
                                (left, int(character_id), item_id, sqlite3.Binary(extra)))
                    else:
                        if source == "slip":
                            conn.execute(
                                "DELETE FROM char_storage "
                                "WHERE character_id = ? AND item_id = ?",
                                (int(character_id), item_id))
                        else:
                            conn.execute(
                                "DELETE FROM char_locker WHERE character_id = ? "
                                "AND item_id = ? AND extra = ?",
                                (int(character_id), item_id, sqlite3.Binary(extra)))

            relocated: list[dict] = []
            if relocate:
                home_placeholders = ",".join("?" for _ in ORGANIZE_HOME_BAGS)
                home_rows = conn.execute(
                    "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                    "COALESCE(ci.extra, X'') AS extra, "
                    "COALESCE(i.name, 'Item') AS name, COALESCE(i.jobs, 0) AS jobs, "
                    "COALESCE(i.equip_slot, '') AS equip_slot, COALESCE(i.stack, 1) AS stack "
                    "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                    "WHERE ci.character_id = ? AND ci.container IN (%s) "
                    "ORDER BY ci.container, ci.slot" % home_placeholders,
                    (int(character_id), *ORGANIZE_HOME_BAGS)).fetchall()
                for row in home_rows:
                    if not self._auto_equipment(row):
                        continue
                    jobs = int(row["jobs"])
                    if scope == "exclusive":
                        if jobs != mask:
                            continue
                    elif not (jobs & mask):
                        continue
                    source = (int(row["container"]), int(row["slot"]))
                    if source in equipped:
                        continue
                    target = None
                    for container in WARDROBE_CONTAINERS:
                        slot = self._next_free(occupied, container)
                        if slot is not None:
                            target = (container, slot)
                            break
                    if target is None:
                        continue
                    conn.execute(
                        "UPDATE char_inventory SET container = ?, slot = ? "
                        "WHERE character_id = ? AND container = ? AND slot = ?",
                        (target[0], target[1], int(character_id), source[0], source[1]))
                    if source[0] in occupied:
                        occupied[source[0]].discard(source[1])
                    relocated.append({
                        "from_container": source[0], "from_slot": source[1],
                        "to_container": target[0], "to_slot": target[1],
                        "item_id": int(row["item_id"]), "quantity": int(row["quantity"]),
                        "name": str(row["name"] or "Item"),
                        "extra": bytes(row["extra"] or b""),
                    })

            storage_count = int(conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM char_storage WHERE character_id = ?",
                (int(character_id),)).fetchone()[0])
            locker_slots, locker_items = self._locker_totals(conn, character_id)
            free = sum(CONTAINER_SLOTS - 1 - len(occupied[container])
                       for container in WARDROBE_CONTAINERS)
            return {
                "job": job, "scope": scope,
                "stored": stored, "stored_slip": stored_slip,
                "stored_locker": stored_locker,
                "stored_total": stored_slip + stored_locker,
                "locker_full": locker_full, "equipped": equipped_left,
                "pulled": pulled, "pulled_slip": pulled_slip,
                "pulled_locker": pulled_locker,
                "pulled_total": pulled_slip + pulled_locker,
                "remaining": remaining, "relocated": relocated,
                "free": free, "storage_count": storage_count,
                "locker_count": locker_slots, "locker_items": locker_items,
                "locker_capacity": LOCKER_CAPACITY,
            }

    def storage_summary(self, character_id: int) -> dict[int, int]:
        """Slip number -> stored quantity, for //storage with no arguments."""
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
        if kind == "capes":
            cape_id = selector.get("cape_id")
            if cape_id is not None:
                return item_id == int(cape_id)
            return item_id in capes.CAPE_IDS
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
        """Move matching items from every permanent bag into the hidden 9,999-slot locker.

        The locker is not a client container: the item's char_inventory row is deleted, so
        it disappears from every bag until ``take_from_locker`` puts it back.  The item's
        24-byte extdata block travels with it, which is what lets several copies of one
        job cape (same item id, different ambuscade augments) live side by side.  Equipped
        pieces stay on, and the 9999 limit is the sum of stored quantities.
        """
        with self.db.transaction() as conn:
            placeholders = ",".join("?" for _ in PERMANENT_BAGS)
            rows = conn.execute(
                "SELECT ci.container, ci.slot, ci.item_id, ci.quantity, "
                "COALESCE(ci.extra, X'') AS extra, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.equip_slot, '') AS equip_slot "
                "FROM char_inventory ci LEFT JOIN items i ON i.item_id = ci.item_id "
                "WHERE ci.character_id = ? AND ci.container IN (%s) "
                "ORDER BY ci.container, ci.slot" % placeholders,
                (int(character_id), *PERMANENT_BAGS)).fetchall()
            equipped = {(int(row["container"]), int(row["slot"])) for row in conn.execute(
                "SELECT container, slot FROM char_equip WHERE character_id = ?",
                (int(character_id),))}
            locker_slots, locker_items = self._locker_totals(conn, character_id)
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
                extra = bytes(row["extra"] or b"")
                existing = conn.execute(
                    "SELECT 1 FROM char_locker WHERE character_id = ? "
                    "AND item_id = ? AND extra = ?",
                    (int(character_id), item_id, sqlite3.Binary(extra))).fetchone()
                if existing is None and locker_slots >= LOCKER_CAPACITY:
                    remaining += quantity
                    continue
                conn.execute(
                    "DELETE FROM char_inventory WHERE character_id = ? "
                    "AND container = ? AND slot = ?",
                    (int(character_id), source[0], source[1]))
                conn.execute(
                    "INSERT INTO char_locker (character_id, item_id, extra, quantity) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(character_id, item_id, extra) "
                    "DO UPDATE SET quantity = quantity + excluded.quantity",
                    (int(character_id), item_id, sqlite3.Binary(extra), quantity))
                if existing is None:
                    locker_slots += 1
                locker_items += quantity
                moved.append({
                    "from_container": source[0], "from_slot": source[1],
                    "item_id": item_id, "quantity": quantity, "extra": extra,
                    "name": str(row["name"] or "Item"),
                })
            return {"moved": moved, "equipped": equipped_left, "remaining": remaining,
                    "locker_count": locker_slots, "locker_items": locker_items,
                    "locker_capacity": LOCKER_CAPACITY}

    def take_from_locker(self, character_id: int, selector: dict,
                         limit: int | None = None,
                         containers: tuple[int, ...] | None = None) -> dict:
        """Move matching locker items back to the inventory first, then the wardrobes.

        ``limit`` caps the total quantity returned, so a 99-jug stack can be taken one
        stack at a time instead of filling the bag.  ``containers`` overrides the
        destination order; the default is inventory first, then the eight wardrobes.
        """
        destinations = tuple(containers or STORAGE_DESTINATIONS)
        if not destinations:
            raise ValueError("at least one destination container is required")
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT cl.item_id, cl.quantity, cl.extra, "
                "COALESCE(i.name, 'Item') AS name, COALESCE(i.equip_slot, '') AS equip_slot, "
                "COALESCE(i.stack, 1) AS stack "
                "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
                "WHERE cl.character_id = ? ORDER BY cl.item_id", (int(character_id),)).fetchall()
            placeholders = ",".join("?" for _ in destinations)
            occupied = {container: set() for container in destinations}
            for row in conn.execute(
                    "SELECT container, slot FROM char_inventory WHERE character_id = ? "
                    "AND container IN (%s)" % placeholders,
                    (int(character_id), *destinations)):
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
                extra = bytes(row["extra"] or b"")
                left = int(row["quantity"])
                stack = max(1, int(row["stack"] or 1))
                take = left if limit is None else min(left, limit)
                moved_qty = 0
                while moved_qty < take:
                    target_container = target_slot = None
                    for container in destinations:
                        target_slot = next_free(container)
                        if target_slot is not None:
                            target_container = container
                            break
                    if target_container is None:
                        break
                    put = min(take - moved_qty, stack)
                    conn.execute(
                        "INSERT INTO char_inventory "
                        "(character_id, container, slot, item_id, quantity, extra) "
                        "VALUES (?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(character_id, container, slot) "
                        "DO UPDATE SET item_id = excluded.item_id, "
                        "quantity = excluded.quantity, extra = excluded.extra",
                        (int(character_id), target_container, target_slot, item_id, put,
                         sqlite3.Binary(extra)))
                    moved.append({
                        "to_container": target_container, "to_slot": target_slot,
                        "item_id": item_id, "quantity": put, "extra": extra,
                        "name": str(row["name"] or "Item"),
                    })
                    moved_qty += put
                if moved_qty < left:
                    conn.execute(
                        "UPDATE char_locker SET quantity = ? "
                        "WHERE character_id = ? AND item_id = ? AND extra = ?",
                        (left - moved_qty, int(character_id), item_id,
                         sqlite3.Binary(extra)))
                    if moved_qty < take:
                        remaining += left - moved_qty
                else:
                    conn.execute(
                        "DELETE FROM char_locker "
                        "WHERE character_id = ? AND item_id = ? AND extra = ?",
                        (int(character_id), item_id, sqlite3.Binary(extra)))
                if limit is not None:
                    limit -= moved_qty
            locker_slots, locker_items = self._locker_totals(conn, character_id)
            return {"moved": moved, "skipped": skipped, "remaining": remaining,
                    "locker_count": locker_slots, "locker_items": locker_items,
                    "locker_capacity": LOCKER_CAPACITY}

    def locker_summary(self, character_id: int) -> dict:
        """Filled/capacity totals for //locker with no arguments.

        ``slots`` is what the 9,999 limit counts (one per item id + augment block), so a
        99-item jug stack is one slot; ``items`` is the total quantity behind them.
        """
        row = self.db.one(
            "SELECT COUNT(*) AS slots, COALESCE(SUM(quantity), 0) AS items "
            "FROM char_locker WHERE character_id = ?", (int(character_id),))
        slots = int(row["slots"] or 0)
        return {"slots": slots, "kinds": slots, "items": int(row["items"] or 0),
                "capacity": LOCKER_CAPACITY, "free": LOCKER_CAPACITY - slots}

    def locker_items(self, character_id: int) -> list[dict]:
        """Everything in the hidden locker, for //locker list."""
        items = [dict(row) for row in self.db.all(
            "SELECT cl.item_id, cl.quantity, COALESCE(cl.extra, X'') AS extra, "
            "COALESCE(i.name, 'Item') AS name "
            "FROM char_locker cl LEFT JOIN items i ON i.item_id = cl.item_id "
            "WHERE cl.character_id = ? ORDER BY COALESCE(i.name, 'Item'), cl.item_id",
            (int(character_id),))]
        for item in items:
            job = capes.job_for_item(int(item["item_id"]))
            if not job or not item.get("extra"):
                continue
            item["job"] = job
            item["build"] = next(
                (build for build in capes.JOBS[job]["builds"]
                 if capes.encode(build, job) == bytes(item["extra"])),
                capes.describe(item["extra"]))
        return items

    def inventory_slot(self, character_id: int, container: int, slot: int) -> dict | None:
        """The item in one exact bag slot, or None when the slot is empty."""
        row = self.db.one(
            "SELECT container, slot, item_id, quantity, extra FROM char_inventory "
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
        """Item id -> (current visible quantity, target) for //stock."""
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

    def add_item(self, character_id: int, item_id: int, quantity: int = 1) -> dict:
        if quantity <= 0:
            raise ApiError(422, "validation_error", "quantity must be positive")
        item = self.item(item_id)
        # Only Rare caps the character at one copy; Ex items can be held in
        # multiples (the augmented job capes are Ex and several builds share an id).
        unique = bool(item and int(item.get("rare") or 0))
        if unique and quantity > 1:
            raise ApiError(422, "rare_item",
                           "only one copy of an item can be obtained at a time")
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

    def award_exp_gil(self, character_id: int, exp: int, gil: int,
                      *, exemplar: bool = False) -> dict:
        """Add experience (or Exemplar Points) and gil.

        At level 99 a kill earns Exemplar Points, not experience: the EXP bar is done and
        the Master Level menu reads ``characters.exemplar_points``.  ``exemplar`` lets the
        caller force that path (the zone does it as soon as the main level is 99); it also
        triggers automatically for a level-99 character.  Every ``EXEMPLAR_PER_LEVEL``
        points buys one Master Level up to 50 while there is a job row to write.
        """
        exp, gil = max(0, int(exp)), max(0, int(gil))
        levels = 0
        exemplar_result = None
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM characters WHERE id = ?", (int(character_id),)).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "character not found")
            level = int(row["main_level"])
            total_gil = int(row["gil"]) + gil
            if exemplar or level >= 99:
                points = exp
                master = 0
                job_row = conn.execute(
                    "SELECT master_level FROM character_jobs WHERE character_id = ? AND job = ?",
                    (int(character_id), int(row["main_job"]))).fetchone()
                if job_row is not None:
                    master = int(job_row["master_level"] or 0)
                total_points = int(row["exemplar_points"] or 0) + points
                master_levels = 0
                while (master < MASTER_LEVEL_MAX
                       and total_points >= EXEMPLAR_PER_LEVEL):
                    total_points -= EXEMPLAR_PER_LEVEL
                    master += 1
                    master_levels += 1
                conn.execute(
                    "UPDATE characters SET exemplar_points = ?, gil = ?, updated_at = ? "
                    "WHERE id = ?",
                    (total_points, total_gil, now_iso(), int(character_id)))
                conn.execute(
                    "INSERT INTO char_inventory (character_id, container, slot, item_id, quantity) "
                    "VALUES (?, 0, 0, 65535, ?) ON CONFLICT(character_id, container, slot) "
                    "DO UPDATE SET item_id = 65535, quantity = excluded.quantity",
                    (int(character_id), total_gil))
                if master_levels:
                    conn.execute(
                        "INSERT INTO character_jobs (character_id, job, master_level) "
                        "VALUES (?, ?, ?) ON CONFLICT(character_id, job) "
                        "DO UPDATE SET master_level = excluded.master_level",
                        (int(character_id), int(row["main_job"]), master))
                exemplar_result = (points, total_points, master_levels, master)
            else:
                total_exp = int(row["exp"]) + exp
                hp, mp = int(row["hp"]), int(row["mp"])
                while level < 99 and total_exp >= exp_for_level(level):
                    total_exp -= exp_for_level(level)
                    level += 1
                    levels += 1
                if levels:
                    # Max HP/MP follow race, job, level and subjob; the zone session adds
                    # the gear's HP/MP on top when it next builds the sheet.
                    from .game import base_stats
                    hp = base_stats.base_hp(int(row["race"]), int(row["main_job"]), level,
                                            int(row["sub_job"]), int(row["sub_level"]))
                    mp = base_stats.base_mp(int(row["race"]), int(row["main_job"]), level,
                                            int(row["sub_job"]), int(row["sub_level"]))
                current_hp = hp if levels else int(row["hp_current"])
                current_mp = mp if levels else int(row["mp_current"])
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
        if exemplar_result is not None:
            points, total_points, master_levels, master = exemplar_result
            character["levels_gained"] = 0
            character["exemplar_gained"] = points
            character["exemplar_points"] = total_points
            character["master_levels_gained"] = master_levels
            character["master_level"] = master
        else:
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
    def gearswap_settings(self, account_id: int) -> dict | None:
        """The account's saved GearSwap/phase config, or None before the first save."""
        row = self.db.one(
            "SELECT config FROM gearswap_settings WHERE account_id = ?",
            (int(account_id),))
        if row is None:
            return None
        try:
            value = json.loads(row["config"])
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def save_gearswap_settings(self, account_id: int, config) -> dict:
        """Replace one account's GearSwap config after a light size/type check."""
        if not isinstance(config, dict):
            raise ApiError(422, "validation_error", "the GearSwap config must be an object")
        encoded = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 256 * 1024:
            raise ApiError(422, "validation_error", "the GearSwap config is too large")
        self.db.execute(
            "INSERT INTO gearswap_settings (account_id, config, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(account_id) DO UPDATE SET "
            "config = excluded.config, updated_at = excluded.updated_at",
            (int(account_id), encoded, now_iso()))
        return config

    # --- per-account GearSwap libraries --------------------------------------------------------
    @staticmethod
    def _gearswap_job(job) -> str:
        text = str(job or "").strip().upper()
        if text not in GEARSWAP_JOBS:
            raise ApiError(422, "validation_error", "unknown job for a GearSwap library")
        return text

    def _gearswap_template_account_id(self) -> int | None:
        """The account whose saved libraries seed a new account, when it exists."""
        username = (self.config.gearswap_template_account or "").strip()
        if not username:
            return None
        row = self.db.one(
            "SELECT id FROM accounts WHERE username = ? AND kind = 'main'", (username,))
        return int(row["id"]) if row is not None else None

    def _gearswap_template_file(self, job: str) -> tuple[str, str]:
        """The server's own job library: Onedough's current set on this server."""
        folder = self.config.gearswap_dir or (self.config.root / "gearswap")
        path = folder / f"{job}.lua"
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            raise ApiError(
                404, "not_found",
                "no %s GearSwap template is installed (expected %s)" % (job, path)) from None
        return source, "%s.lua" % job

    def _gearswap_seed_source(self, account_id: int, job: str) -> tuple[str, str]:
        """Copy the template account's row, falling back to the checkout's file.

        Onedough's account is seeded from ``gearswap/<JOB>.lua`` the first time it asks
        for a job; every later account copies Onedough's current saved row instead, so
        changing the shared template still only happens through Onedough's own library.
        """
        template_id = self._gearswap_template_account_id()
        if template_id is not None and template_id != int(account_id):
            row = self.db.one(
                "SELECT source, name FROM gearswap_libraries WHERE account_id = ? AND job = ?",
                (template_id, job))
            if row is None:
                self.ensure_gearswap_library(template_id, job)
                row = self.db.one(
                    "SELECT source, name FROM gearswap_libraries WHERE account_id = ? AND job = ?",
                    (template_id, job))
            if row is not None:
                return str(row["source"]), str(row["name"] or ("%s.lua" % job))
        return self._gearswap_template_file(job)

    def ensure_gearswap_library(self, account_id: int, job: str) -> dict:
        """One account's saved library, seeded from the template on first use."""
        job = self._gearswap_job(job)
        row = self.db.one(
            "SELECT account_id, job, name, source, updated_at FROM gearswap_libraries "
            "WHERE account_id = ? AND job = ?", (int(account_id), job))
        if row is not None:
            return dict(row)
        source, name = self._gearswap_seed_source(account_id, job)
        created = now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO gearswap_libraries "
                "(account_id, job, name, source, updated_at) VALUES (?, ?, ?, ?, ?)",
                (int(account_id), job, name, source, created))
        row = self.db.one(
            "SELECT account_id, job, name, source, updated_at FROM gearswap_libraries "
            "WHERE account_id = ? AND job = ?", (int(account_id), job))
        if row is None:
            raise ApiError(503, "gearswap_unavailable",
                           "the GearSwap library could not be created")
        return dict(row)

    def gearswap_library(self, account_id: int, job: str) -> dict:
        row = self.ensure_gearswap_library(account_id, job)
        return {
            "job": row["job"],
            "name": row["name"],
            "source": row["source"],
            "updated_at": row["updated_at"],
        }

    def save_gearswap_library(self, account_id: int, job: str, source,
                              name: str | None = None) -> dict:
        """Replace one account's library for one job; other accounts are untouched."""
        job = self._gearswap_job(job)
        if not isinstance(source, str):
            raise ApiError(422, "validation_error", "the GearSwap library must be Lua text")
        if not source.strip():
            raise ApiError(422, "validation_error", "the GearSwap library is empty")
        if len(source.encode("utf-8")) > MAX_GEARSWAP_LIBRARY_BYTES:
            raise ApiError(422, "validation_error", "the GearSwap library is too large")
        clean_name = str(name or ("%s.lua" % job)).strip() or ("%s.lua" % job)
        if len(clean_name) > 200 or "\n" in clean_name or "\r" in clean_name:
            raise ApiError(422, "validation_error", "that GearSwap library name is not valid")
        self.db.execute(
            "INSERT INTO gearswap_libraries (account_id, job, name, source, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(account_id, job) DO UPDATE SET "
            "name = excluded.name, source = excluded.source, updated_at = excluded.updated_at",
            (int(account_id), job, clean_name, source, now_iso()))
        return self.gearswap_library(account_id, job)

    def reset_gearswap_library(self, account_id: int, job: str) -> dict:
        """Replace the account's copy with a fresh template, without losing the old row on error."""
        job = self._gearswap_job(job)
        source, name = self._gearswap_seed_source(account_id, job)
        self.db.execute(
            "INSERT INTO gearswap_libraries (account_id, job, name, source, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(account_id, job) DO UPDATE SET "
            "name = excluded.name, source = excluded.source, updated_at = excluded.updated_at",
            (int(account_id), job, name, source, now_iso()))
        return self.gearswap_library(account_id, job)

    def registration_open(self) -> bool:
        if not self.config.registration_open:
            return False
        return (self.db.setting("registration_open", "1") or "1") != "0"

    def character_setting(self, character_id: int, key: str,
                          default: str | None = None) -> str | None:
        """One per-character gameplay preference (the char_settings table)."""
        row = self.db.one(
            "SELECT value FROM char_settings WHERE character_id = ? AND key = ?",
            (int(character_id), str(key)))
        return default if row is None else str(row["value"])

    def set_character_setting(self, character_id: int, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO char_settings (character_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(character_id, key) DO UPDATE SET value = excluded.value",
            (int(character_id), str(key), str(value)))

    # --- live character state (buffs, food and ability recasts) --------------------------------
    # The zone session owns this state, but a fresh login builds a new session, so it is
    # written here (migration 0145) and read back on the next login.  The payload is JSON from
    # game/live_state.py; the server treats it as opaque apart from decoding it for the caller.
    def save_live_state(self, character_id: int, payload: dict) -> None:
        """Write the reconnect snapshot: {"effects", "food", "recasts", "version"}."""
        self.db.execute(
            "INSERT INTO char_live_state (character_id, effects, food, recasts, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(character_id) DO UPDATE SET "
            "effects = excluded.effects, food = excluded.food, "
            "recasts = excluded.recasts, updated_at = excluded.updated_at",
            (int(character_id),
             json.dumps(payload.get("effects") or [], separators=(",", ":")),
             json.dumps(payload.get("food") or {}, separators=(",", ":")),
             json.dumps(payload.get("recasts") or {}, separators=(",", ":")),
             now_iso()))

    def live_state(self, character_id: int) -> dict | None:
        """The saved reconnect snapshot, or None when the character has none.

        The JSON is decoded here so the zone session gets plain Python values.  A row
        from an older build (or a hand-edited one) is still returned with whatever parts
        decode; ``game/live_state.py`` validates each field on the way in.
        """
        row = self.db.one(
            "SELECT effects, food, recasts, updated_at FROM char_live_state "
            "WHERE character_id = ?", (int(character_id),))
        if row is None:
            return None

        def decode(text, fallback):
            try:
                value = json.loads(text)
            except (TypeError, ValueError):
                return fallback
            return value if isinstance(value, type(fallback)) else fallback

        return {
            "effects": decode(row["effects"], []),
            "food": decode(row["food"], {}),
            "recasts": decode(row["recasts"], {}),
            "updated_at": row["updated_at"],
        }

    def clear_live_state(self, character_id: int) -> None:
        """Forget a character's snapshot (a deleted character cascades; this is for resets)."""
        self.db.execute("DELETE FROM char_live_state WHERE character_id = ?",
                        (int(character_id),))

    # --- mounts --------------------------------------------------------------------------------
    # A mount is client-side art with a server-side id (game/mounts.py).  The server keeps
    # only two things: the character's last choice, and whether it is riding right now,
    # which lives on the live zone session alongside the model flags the client reads.
    def mount_catalog(self) -> list[dict]:
        """Every mount the client knows, in id order."""
        from .game import mounts as mount_table
        return [{"id": mount.id, "name": mount.name,
                 "description": mount.description, "japanese": mount.japanese,
                 "chocobo_index": mount.chocobo_index()}
                for mount in mount_table.all_mounts()]

    def set_character_mount(self, character_id: int, mount_id: int) -> None:
        """Remember the last mount a character called (the HUD preselects it)."""
        self.db.execute(
            "UPDATE characters SET mount = ?, updated_at = ? WHERE id = ?",
            (int(mount_id), now_iso(), int(character_id)))

    def character_mount(self, character_id: int) -> dict:
        """A character's live mount (if online) and the last one it called."""
        row = self.db.one(
            "SELECT id, char_id, name, mount FROM characters WHERE id = ?",
            (int(character_id),))
        if row is None:
            raise ApiError(404, "not_found", "no such character")
        current = None
        world = self.zone_world
        session = world.session_by_char(int(row["char_id"])) if world is not None else None
        if session is not None and int(session.mount_id) >= 0:
            current = int(session.mount_id)
        last = int(row["mount"] if row["mount"] is not None else -1)
        from .game import mounts as mount_table
        return {
            "character_id": int(row["id"]),
            "name": str(row["name"]),
            "online": session is not None,
            "mount": mount_table.by_id(current).name if current is not None else None,
            "mount_id": current,
            "last_mount": mount_table.by_id(last).name if last >= 0 else None,
            "last_mount_id": last if last >= 0 else None,
        }

    def mount_character(self, character_id: int, query, family: bool = False) -> dict:
        """Call a mount for one character (and, with ``family``, its whole sub team).

        An offline character simply remembers the choice — there is no session to show it
        on, and the next login starts on foot like retail.
        """
        from .game import mounts as mount_table
        row = self.db.one(
            "SELECT id, char_id, name, account_id FROM characters WHERE id = ?",
            (int(character_id),))
        if row is None:
            raise ApiError(404, "not_found", "no such character")
        text = str(query if query is not None else "").strip()
        if text.casefold() in ("off", "dismount", "none", "stop"):
            return self.dismount_character(int(row["id"]), family=family)
        mount, error = mount_table.find(text)
        if mount is None:
            raise ApiError(422, "validation_error", error)
        world = self.zone_world
        session = world.session_by_char(int(row["char_id"])) if world is not None else None
        mounted: list[str] = []
        if session is not None:
            targets = session.mount_family(mount) if family else [session]
            if not family:
                session.set_mount(mount.id)
            mounted = [str(target.char.get("name") or "") for target in targets]
        else:
            self.set_character_mount(int(row["id"]), int(mount.id))
        return {
            "ok": True,
            "named": "all" if family else "me",
            "mount": {"id": mount.id, "name": mount.name,
                      "description": mount.description},
            "online": session is not None,
            "mounted": [name for name in mounted if name],
        }

    def dismount_character(self, character_id: int, family: bool = False) -> dict:
        """Back on foot, for one character or the whole sub team."""
        row = self.db.one(
            "SELECT id, char_id, name FROM characters WHERE id = ?", (int(character_id),))
        if row is None:
            raise ApiError(404, "not_found", "no such character")
        world = self.zone_world
        session = world.session_by_char(int(row["char_id"])) if world is not None else None
        dismounted: list[str] = []
        if session is not None:
            targets = session.dismount_family() if family else (
                [session] if session.dismount() else [])
            dismounted = [str(target.char.get("name") or "") for target in targets]
        return {"ok": True, "mount": None, "online": session is not None,
                "dismounted": [name for name in dismounted if name]}

    def _mount_summary(self, character) -> dict:
        """The Data page's Mounts card: the client's table and this character's place in it."""
        from .game import mounts as mount_table
        last = int(character.get("mount") if character.get("mount") is not None else -1)
        last_mount = mount_table.by_id(last)
        world = self.zone_world
        session = (world.session_by_char(int(character["char_id"]))
                   if world is not None else None)
        current = None
        if session is not None and int(session.mount_id) >= 0:
            current = mount_table.by_id(int(session.mount_id))
        return {
            "count": mount_table.count(),
            "all_available": True,
            "last": last_mount.name if last_mount is not None else None,
            "current": current.name if current is not None else None,
            "names": [mount.name for mount in mount_table.all_mounts()],
        }

    def resend_mounts(self, character_id: int) -> dict:
        """Re-send the mount unlock table (0x0AE) to a live client, for the Data page."""
        from .game import mounts as mount_table
        row = self.db.one(
            "SELECT id, char_id, name FROM characters WHERE id = ?", (int(character_id),))
        if row is None:
            raise ApiError(404, "not_found", "no such character")
        world = self.zone_world
        session = world.session_by_char(int(row["char_id"])) if world is not None else None
        sent = bool(session is not None and session.resend_mounts())
        return {"ok": True, "online": session is not None, "sent": sent,
                "count": mount_table.count()}

    # --- battle team control plane -------------------------------------------------------------
    def battle_song_catalog(self, character_id: int) -> tuple[int, list[dict]]:
        """Bard songs with server-computed durations from the character's equipped gear.

        The whole modifier block goes to ``song_duration`` because Song+ gear
        (All Songs and the family rows) adds 10% duration per point on top of the
        454 lines, and that ratio only resolves per song family.
        """
        mods = {int(key): int(value)
                for key, value in self.equipped_mods(int(character_id)).items()}
        bonus = int(mods.get(mod.SONG_DURATION_BONUS, 0))
        try:
            character = self.character(int(character_id))
            bonus += int(job_points.combat_mods(int(character["main_job"])).get(
                mod.SONG_DURATION_BONUS, 0))
        except Exception:
            pass
        mods[mod.SONG_DURATION_BONUS] = bonus
        rows = self.db.all("SELECT name, skill FROM spells ORDER BY name")
        out, seen = [], set()
        for row in rows:
            try:
                skill = int(row["skill"] or 0)
            except (TypeError, ValueError):
                continue
            if skill not in effects.SONG_SKILLS:
                continue
            name = str(row["name"] or "").strip()
            key = name.casefold()
            if not name or key in seen:
                continue
            # Trust-only bard songs are in the spell table but are not player-castable.
            if key in {"cactuar fugue", "chocobo hum", "jesters operetta",
                       "devotee serenade", "moogle rhapsody", "protected aria"}:
                continue
            spec = effects.SPELLS.get(key)
            if spec is None or float(spec.duration or 0) <= 0:
                continue
            seen.add(key)
            duration = effects.song_duration(spec, name=name, mods=mods)
            out.append({"name": name, "base": float(spec.duration),
                        "duration": round(duration, 1)})
        out.sort(key=lambda item: item["name"].casefold())
        return bonus, out

    def battle_team_profiles(self, account_id: int) -> list[dict]:
        """Every character in this account family with its server-side Battle profile.

        Each row carries ``online`` and ``online_known`` so the in-game hub can keep its team
        list to characters that are actually logged in.  A smaller party is the normal case:
        the account family can own six characters and run only three.  ``online_known`` is
        false when the game gateway is not attached, and callers then keep the old behaviour
        instead of treating every character as offline.
        """
        family = sorted(self.account_family_ids(int(account_id)))
        if not family:
            return []
        online_known = self.zone_world is not None
        online = {}
        if online_known:
            for character in self.online_characters(int(account_id)):
                online[int(character.get("id") or 0)] = character
        holes = ",".join("?" for _ in family)
        rows = self.db.all(
            "SELECT c.id AS character_id, c.name, c.account_id, c.main_job, c.sub_job, "
            "       c.main_level, c.sub_level, s.value AS profile_json "
            "FROM characters c LEFT JOIN char_settings s "
            "  ON s.character_id = c.id AND s.key = 'battle_profile' "
            f"WHERE c.account_id IN ({holes}) ORDER BY c.id",
            tuple(family))
        out = []
        for row in rows:
            row = dict(row)
            profile = None
            if row.get("profile_json"):
                try:
                    profile = json.loads(row["profile_json"])
                except (TypeError, ValueError):
                    profile = None
            main_job = int(row.get("main_job") or 0)
            sub_job = int(row.get("sub_job") or 0)
            main_level = int(row.get("main_level") or 0)
            sub_level = int(row.get("sub_level") or 0)
            abilities = self.db.all(
                "SELECT name, job, level FROM job_abilities "
                "WHERE (job = ? AND level <= ?) OR (job = ? AND level <= ?) "
                "ORDER BY job, level, name",
                (main_job, main_level, sub_job, sub_level))
            seen = set()
            ability_list = []
            for ability in abilities:
                name = ability["name"]
                if name and name not in seen:
                    seen.add(name)
                    ability_list.append({"name": name, "job": int(ability["job"]),
                                         "level": int(ability["level"])})
            song_bonus, songs = (0, [])
            if main_job == 10 or sub_job == 10:
                song_bonus, songs = self.battle_song_catalog(int(row["character_id"]))
            live = online.get(int(row["character_id"]))
            out.append({
                "character_id": int(row["character_id"]),
                "name": row["name"],
                "account_id": int(row["account_id"]),
                "main_job": main_job,
                "sub_job": sub_job,
                "main_level": main_level,
                "sub_level": sub_level,
                "abilities": ability_list,
                "song_duration_bonus": song_bonus,
                "songs": songs,
                "online": live is not None,
                "online_known": online_known,
                "zone": int(live.get("zone") or 0) if live else None,
                "zone_name": str(live.get("zone_name") or "") if live else None,
                "updated": int(profile.get("updated") or 0) if isinstance(profile, dict) else 0,
                "profile": profile,
            })
        return out

    def save_battle_profile(self, account_id: int, character_id: int, profile, shared: bool = False) -> dict:
        """Store one character's Battle profile. The family owner (or the sub itself) may write it."""
        if not self.account_can_manage_character(int(account_id), int(character_id)):
            raise ApiError(404, "not_found", "character not found")
        if not isinstance(profile, dict):
            raise ApiError(422, "validation_error", "profile must be a JSON object")
        encoded = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 65536:
            raise ApiError(413, "too_large", "battle profile is too large")
        profile = dict(profile)
        profile["updated"] = int(time.time())
        encoded = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
        self.set_character_setting(int(character_id), "battle_profile", encoded)
        if shared:
            family = sorted(self.account_family_ids(int(account_id)))
            holes = ",".join("?" for _ in family)
            rows = self.db.all(
                "SELECT c.id AS character_id, s.value AS profile_json "
                "FROM characters c LEFT JOIN char_settings s "
                "  ON s.character_id = c.id AND s.key = 'battle_profile' "
                f"WHERE c.account_id IN ({holes}) AND c.id <> ?",
                tuple(family) + (int(character_id),))
            now = int(time.time())
            for raw in rows:
                row = dict(raw)
                if not row.get("profile_json"):
                    continue
                try:
                    other = json.loads(row["profile_json"])
                except (TypeError, ValueError):
                    continue
                if not isinstance(other, dict):
                    continue
                for key in BATTLE_SHARED_KEYS:
                    if key in profile:
                        other[key] = profile[key]
                other["updated"] = now
                self.set_character_setting(int(row["character_id"]), "battle_profile",
                                           json.dumps(other, ensure_ascii=False, separators=(",", ":")))
        return profile

    def save_battle_engine(self, account_id: int, character_id: int, engine) -> dict:
        """Merge only the live engine flags into one character's saved Battle profile.

        Start/ready/stop publishes happen several times per run and must not rewrite the
        whole profile (and must not bump ``updated``, or the client would re-apply its own
        server copy over an unsaved edit).
        """
        if not self.account_can_manage_character(int(account_id), int(character_id)):
            raise ApiError(404, "not_found", "character not found")
        if not isinstance(engine, dict):
            raise ApiError(422, "validation_error", "engine must be a JSON object")
        row = self.db.one(
            "SELECT value FROM char_settings WHERE character_id = ? AND key = 'battle_profile'",
            (int(character_id),))
        profile = {}
        if row and row["value"]:
            try:
                decoded = json.loads(row["value"])
                if isinstance(decoded, dict):
                    profile = decoded
            except (TypeError, ValueError):
                profile = {}
        current = profile.get("engine")
        current = dict(current) if isinstance(current, dict) else {}
        for key in ("running", "ready", "run_id"):
            if key in engine:
                value = engine[key]
                if key == "run_id":
                    current[key] = str(value or "")[:48]
                else:
                    current[key] = bool(value)
        profile["engine"] = current
        self.set_character_setting(
            int(character_id), "battle_profile",
            json.dumps(profile, ensure_ascii=False, separators=(",", ":")))
        return {"engine": current}

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
