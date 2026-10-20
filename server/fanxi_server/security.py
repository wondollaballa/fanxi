"""Passwords, tokens, validation and time helpers.

Only the standard library is used: PBKDF2-HMAC-SHA256 for passwords, SHA-256 for bearer and
one-time tokens, and ``secrets`` for everything random.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 260_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,19}$")
CHARACTER_RE = re.compile(r"^[A-Za-z]{3,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def now_iso() -> str:
    return iso(utcnow())


def iso_after(**delta) -> str:
    return iso(utcnow() + timedelta(**delta))


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def expired(value: str | None) -> bool:
    dt = parse_iso(value)
    return dt is None or dt <= utcnow()


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        want = base64.b64decode(digest_b64)
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(got, want)
    except (ValueError, TypeError):
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_hash() -> bytes:
    return secrets.token_bytes(16)


def signed_bytes(value: bytes) -> list[int]:
    """The 16 numbers a LandSandBoat-style auth reply carries (signed chars)."""
    return [b - 256 if b >= 128 else b for b in value]


def validate_username(value: str) -> str:
    value = (value or "").strip()
    if not USERNAME_RE.match(value):
        raise ValidationError("username must be 3-20 characters: letters, numbers, dot, dash or underscore")
    return value


def validate_password(value: str) -> str:
    if not isinstance(value, str) or len(value) < 8:
        raise ValidationError("password must be at least 8 characters")
    if len(value) > 200:
        raise ValidationError("password must be at most 200 characters")
    return value


def validate_email(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if len(value) > 254 or not EMAIL_RE.match(value):
        raise ValidationError("email address is not valid")
    return value


def validate_character_name(value: str) -> str:
    value = (value or "").strip()
    if not CHARACTER_RE.match(value):
        raise ValidationError("character name must be 3-15 letters")
    return value


def validate_int(value, name: str, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError("%s must be a number" % name)
    if not low <= number <= high:
        raise ValidationError("%s must be between %d and %d" % (name, low, high))
    return number


def safe_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
