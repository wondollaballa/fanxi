"""GearSwap libraries for the launcher: jobs, defaults, sets and versioned saves.

The Gear window owns the widgets and the control-port calls; this module owns the
parts that are worth testing on their own:

* the job id -> name/abbreviation table and the ``state`` payload reader;
* where the bundled default ``gearswap/*.lua`` libraries live;
* flattening the importer's nested ``sets`` table into ``path -> {slot: item}``;
* serializing that back into a GearSwap file;
* timestamped, never-overwrite version names and the Downloads folder.

No tkinter and no network imports here, so the unit tests run headless.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SLOT_KEYS = (
    "main", "sub", "range", "ammo", "head", "body", "hands", "legs", "feet",
    "neck", "waist", "ear1", "ear2", "ring1", "ring2", "back",
)
SLOT_LABELS = {
    "main": "Main", "sub": "Sub", "range": "Range", "ammo": "Ammo",
    "head": "Head", "body": "Body", "hands": "Hands", "legs": "Legs",
    "feet": "Feet", "neck": "Neck", "waist": "Waist",
    "ear1": "Left ear", "ear2": "Right ear",
    "ring1": "Left ring", "ring2": "Right ring", "back": "Back",
}
SLOT_ALIASES = {
    "left_ear": "ear1", "right_ear": "ear2",
    "left_ring": "ring1", "right_ring": "ring2",
}
# Note: GearSwap's slot key is "range"; a group named "ranged" is NOT a slot.
# Mapping "ranged" to "range" here would make the top-level sets.ranged group
# look like a slot table and hide every ranged set.
SLOT_SET = frozenset(SLOT_KEYS)

JOB_NAMES = {
    1: "Warrior", 2: "Monk", 3: "White Mage", 4: "Black Mage", 5: "Red Mage",
    6: "Thief", 7: "Paladin", 8: "Dark Knight", 9: "Beastmaster", 10: "Bard",
    11: "Ranger", 12: "Samurai", 13: "Ninja", 14: "Dragoon", 15: "Summoner",
    16: "Blue Mage", 17: "Corsair", 18: "Puppetmaster", 19: "Dancer",
    20: "Scholar", 21: "Geomancer", 22: "Rune Fencer",
}
JOB_ABBREVIATIONS = {
    1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD",
    8: "DRK", 9: "BST", 10: "BRD", 11: "RNG", 12: "SAM", 13: "NIN", 14: "DRG",
    15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH",
    21: "GEO", 22: "RUN",
}
JOB_ORDER = tuple(JOB_ABBREVIATIONS[i] for i in sorted(JOB_ABBREVIATIONS))
JOB_FOR_ABBR = {abbr: number for number, abbr in JOB_ABBREVIATIONS.items()}

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VERSION_SUFFIX = re.compile(r"-\d{8}-\d{6}(?:-\d+)?$")
LUA_KEYWORDS = frozenset({
    "and", "break", "do", "else", "elseif", "end", "false", "for", "function",
    "goto", "if", "in", "local", "nil", "not", "or", "repeat", "return",
    "then", "true", "until", "while",
})


class GearError(ValueError):
    """A set path, item or library that cannot be saved."""


@dataclass(frozen=True)
class JobInfo:
    job_id: int
    name: str
    abbr: str
    level: int = 0
    character: str = ""

    @property
    def label(self) -> str:
        if self.level:
            return "%s · %s · Lv %d" % (self.abbr, self.name, self.level)
        return "%s · %s" % (self.abbr, self.name)


def job_from_state(state: dict | None) -> JobInfo | None:
    """The live main job from the control addon's ``state`` payload."""
    player = (state or {}).get("player")
    if not isinstance(player, dict):
        return None
    try:
        job_id = int(player.get("job") or 0)
    except (TypeError, ValueError):
        return None
    if job_id not in JOB_NAMES:
        return None
    try:
        level = int(player.get("level") or 0)
    except (TypeError, ValueError):
        level = 0
    return JobInfo(job_id, JOB_NAMES[job_id], JOB_ABBREVIATIONS[job_id], level,
                   str(player.get("name") or ""))


def job_from_character(character: dict | None) -> JobInfo | None:
    """The last saved main job on a character record, for the pre-login window."""
    if not isinstance(character, dict):
        return None
    try:
        job_id = int(character.get("main_job") or 0)
    except (TypeError, ValueError):
        return None
    if job_id not in JOB_NAMES:
        return None
    try:
        level = int(character.get("main_level") or 0)
    except (TypeError, ValueError):
        level = 0
    return JobInfo(job_id, JOB_NAMES[job_id], JOB_ABBREVIATIONS[job_id], level,
                   str(character.get("name") or ""))


def job_abbr(value: int | str | None) -> str:
    if isinstance(value, str) and value.strip().upper() in JOB_FOR_ABBR:
        return value.strip().upper()
    try:
        return JOB_ABBREVIATIONS.get(int(value or 0), "")
    except (TypeError, ValueError):
        return ""


def normalize_slot(key) -> str:
    text = str(key or "").strip().lower()
    return SLOT_ALIASES.get(text, text)


def ordered_items(items: dict) -> dict[str, str]:
    """Items in the game's slot order, then any unknown keys for diagnostics."""
    out = {slot: items[slot] for slot in SLOT_KEYS if items.get(slot)}
    for key, value in items.items():
        if key not in out and value:
            out[key] = value
    return out


def flatten_sets(tree: dict | None, prefix: str = "sets") -> dict[str, dict[str, str]]:
    """The launcher's flatten: a table with slot keys is one set, and stops there."""
    out: dict[str, dict[str, str]] = {}

    def walk(path: str, value) -> None:
        if not isinstance(value, dict):
            return
        found = {normalize_slot(key) for key in value if normalize_slot(key) in SLOT_SET}
        if found:
            items: dict[str, str] = {}
            for key, item in value.items():
                slot = normalize_slot(key)
                if slot not in SLOT_SET:
                    continue
                name = None
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("name")
                if name:
                    items[slot] = str(name)
            if items:
                out[path] = ordered_items(items)
            return
        for key, child in value.items():
            walk("%s.%s" % (path, key), child)

    walk(prefix, tree)
    return out


def flatten_sets_detailed(tree: dict | None, prefix: str = "sets"
                          ) -> dict[str, dict[str, dict]]:
    """Like :func:`flatten_sets`, but keep each item's augment array.

    The Gear window uses this to show the augment builds imported from a
    GearSwap file; ``flatten_sets`` remains the name-only view used by the
    editor and serializer.
    """
    out: dict[str, dict[str, dict]] = {}

    def walk(path: str, value) -> None:
        if not isinstance(value, dict):
            return
        found = {normalize_slot(key) for key in value if normalize_slot(key) in SLOT_SET}
        if found:
            items: dict[str, dict] = {}
            for key, item in value.items():
                slot = normalize_slot(key)
                if slot not in SLOT_SET:
                    continue
                name = None
                augments = []
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("name")
                    raw = item.get("augments")
                    if isinstance(raw, str):
                        augments = [raw]
                    elif isinstance(raw, (list, tuple)):
                        augments = [str(part) for part in raw
                                    if isinstance(part, (str, int, float))]
                    elif isinstance(raw, dict):
                        # lupa/control JSON may hand back a 1-based table.
                        numeric = [(int(key), part) for key, part in raw.items()
                                   if str(key).isdigit()]
                        augments = [str(part) for _key, part in sorted(numeric)
                                    if isinstance(part, (str, int, float))]
                if name:
                    items[slot] = {"name": str(name), "augments": augments}
            if items:
                ordered = {slot: items[slot] for slot in SLOT_KEYS if items.get(slot)}
                for key, detail in items.items():
                    if key not in ordered:
                        ordered[key] = detail
                out[path] = ordered
            return
        for key, child in value.items():
            walk("%s.%s" % (path, key), child)

    walk(prefix, tree)
    return out


def normalize_set_path(text: str) -> str:
    """``idle.pdt`` / ``sets.idle.pdt`` -> a safe ``sets.`` path.

    A dot separates table levels; segments with spaces, apostrophes or colons
    are fine and are quoted again by :func:`lua_path`.  Brackets, quotes and
    line breaks are rejected because they would make the path ambiguous.
    """
    raw = str(text or "").strip()
    if not raw:
        raise GearError("The set path is empty.")
    if raw == "sets" or raw.startswith("sets."):
        body = raw[5:] if raw.startswith("sets.") else ""
    else:
        body = raw
    segments = [segment.strip() for segment in body.split(".")]
    if not segments or any(not segment for segment in segments):
        raise GearError("Use a path like sets.idle.pdt (no empty levels).")
    for segment in segments:
        if len(segment) > 64:
            raise GearError("Each set name level must be 64 characters or fewer.")
        if any(bad in segment for bad in '[]"\n\r'):
            raise GearError('Set names cannot contain [ ] " or line breaks.')
    return "sets." + ".".join(segments)


def path_conflict(path: str, existing) -> str | None:
    """Return the set path that would collide with ``path``, if any.

    Two slot-bearing tables on the same branch would hide each other in Fanxi's
    flatten, so a path may not be a parent or child of another set.
    """
    path = normalize_set_path(path)
    for other in existing:
        try:
            other = normalize_set_path(other)
        except GearError:
            continue
        if other == path:
            continue
        if other.startswith(path + ".") or path.startswith(other + "."):
            return other
    return None


def clean_items(items: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (items or {}).items():
        slot = normalize_slot(key)
        if slot not in SLOT_SET:
            raise GearError("Unknown equipment slot: %s" % key)
        name = str(value or "").strip()
        if not name:
            continue
        if "\n" in name or "\r" in name:
            raise GearError("An item name cannot contain a line break.")
        if len(name) > 64:
            raise GearError("Item names must be 64 characters or fewer.")
        out[slot] = name
    return ordered_items(out)


def lua_string(value: str) -> str:
    return '"%s"' % (str(value).replace("\\", "\\\\").replace('"', '\\"')
                     .replace("\n", "\\n").replace("\r", ""))


def lua_path(path: str) -> str:
    """``sets.midcast.Enfeebling Magic`` -> ``sets.midcast["Enfeebling Magic"]``."""
    path = normalize_set_path(path)
    segments = path.split(".")
    expression = "sets"
    for segment in segments[1:]:
        if IDENTIFIER.match(segment) and segment not in LUA_KEYWORDS:
            expression += "." + segment
        else:
            expression += "[%s]" % lua_string(segment)
    return expression


def normalized_library(sets: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Normalize keys and reject prefixes after normalization."""
    out: dict[str, dict[str, str]] = {}
    for raw, items in (sets or {}).items():
        path = normalize_set_path(raw)
        out[path] = clean_items(items)
    paths = list(out)
    for path in paths:
        other = path_conflict(path, (candidate for candidate in paths if candidate != path))
        if other:
            raise GearError("%s collides with %s." % (path, other))
    return out


def validate_library(sets: dict[str, dict[str, str]]) -> None:
    normalized_library(sets)


def serialize_library(sets: dict[str, dict[str, str]], *, character: str = "",
                      job: str = "", source: str = "",
                      when: datetime | None = None) -> str:
    """A self-contained GearSwap file that Fanxi can import again."""
    sets = normalized_library(sets)
    when = when or datetime.now()

    def comment_text(value: str) -> str:
        return str(value).replace("]]", "] ]").replace("\n", " ").replace("\r", "")

    title = comment_text(" ".join(part for part in (character, job) if part).strip()
                         or "GearSwap")
    lines = [
        "--[[",
        "    Fanxi GearSwap version — %s" % title,
        "    Created %s" % when.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    if source:
        lines.append("    Source: %s" % comment_text(source))
    lines += [
        "",
        "    Re-import this file with Gear -> Import your own .lua…",
        "    Each set holds only slot = \"Item\" pairs so Fanxi lists every one;",
        "    to add a variant, copy an existing set and give it a new path.",
        "]]",
        "",
        "local function combine(base, extra)",
        "    local out = {}",
        "    for key, value in pairs(base or {}) do out[key] = value end",
        "    for key, value in pairs(extra or {}) do out[key] = value end",
        "    return out",
        "end",
        "",
        "function get_sets()",
        "    sets = {}",
    ]
    containers = set()
    for path in sets:
        parts = path.split(".")
        for index in range(2, len(parts)):
            containers.add(".".join(parts[:index]))
    for container in sorted(containers, key=lambda value: (value.count("."), value.lower())):
        lines.append("    %s = {}" % lua_path(container))
    group = None
    for path in sorted(sets, key=str.lower):
        items = clean_items(sets[path])
        if not items:
            continue
        top = path.split(".")[1].split("[")[0] if path.count(".") >= 1 else path
        if top != group:
            lines += ["", "    -- ===== %s =====" % top]
            group = top
        lines.append("    %s = {" % lua_path(path))
        for slot in SLOT_KEYS:
            if items.get(slot):
                lines.append("        %s = %s," % (slot, lua_string(items[slot])))
        lines.append("    }")
    lines += [
        "end",
        "",
        "-- Fanxi saves a new timestamped copy; this file was never the source.",
        "",
    ]
    return "\n".join(lines)


def sanitize_name(value: str, fallback: str = "gearswap") -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "")).strip(".-")
    text = re.sub(r"-+", "-", text)
    return text or fallback


def timestamp(when: datetime | None = None) -> str:
    return (when or datetime.now()).strftime("%Y%m%d-%H%M%S")


def strip_version_suffix(stem: str) -> str:
    return VERSION_SUFFIX.sub("", str(stem or ""))


def versioned_name(base: str, *, when: datetime | None = None,
                   extension: str = ".lua") -> str:
    """``WAR`` + 2026-10-21 09:23:19 -> ``WAR-20261021-092319.lua``."""
    stem = strip_version_suffix(sanitize_name(base))
    return "%s-%s%s" % (stem, timestamp(when), extension)


def unique_version_path(folder: str | Path, base: str, *,
                        when: datetime | None = None,
                        extension: str = ".lua") -> Path:
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    stem = strip_version_suffix(sanitize_name(base))
    stamp = timestamp(when)
    candidate = folder / ("%s-%s%s" % (stem, stamp, extension))
    number = 2
    while candidate.exists():
        candidate = folder / ("%s-%s-%d%s" % (stem, stamp, number, extension))
        number += 1
    return candidate


def save_version(folder: str | Path, sets: dict[str, dict[str, str]], *,
                 base: str, character: str = "", job: str = "", source: str = "",
                 when: datetime | None = None) -> Path:
    when = when or datetime.now()
    target = unique_version_path(folder, base, when=when)
    target.write_text(serialize_library(sets, character=character, job=job,
                                        source=source, when=when), encoding="utf-8")
    return target


def write_profile_snapshot(folder: str | Path, sets: dict[str, dict[str, str]], *,
                           character: str, job: str, source: str,
                           version_path: str | Path,
                           when: datetime | None = None) -> Path:
    """The launcher-owned JSON copy that the Control room lists."""
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / Path(version_path).with_suffix(".json").name
    payload = {
        "character": character,
        "job": job,
        "source": source,
        "saved_at": (when or datetime.now()).isoformat(timespec="seconds"),
        "version": Path(version_path).name,
        "sets": sets,
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return target


def downloads_dir() -> Path:
    """The OS's usual download folder, falling back to the home folder."""
    override = os.environ.get("FANXI_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    home = Path.home()
    for name in ("Downloads", "downloads"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home


def defaults_dir() -> Path | None:
    """Find the repository's / bundle's ``gearswap`` folder of default libraries."""
    candidates: list[Path] = []
    override = os.environ.get("FANXI_GEARSWAP_DIR")
    if override:
        candidates.append(Path(override).expanduser())
    here = Path(__file__).resolve()
    # The checkout wins over the copy inside a built app, so editing
    # gearswap/WAR.lua in the checkout is enough; the bundle copy is the
    # fallback when the checkout has moved away.
    root = os.environ.get("FANXI_REPO_ROOT")
    if root:
        candidates.append(Path(root).expanduser() / "gearswap")
    candidates += [
        here.parent / "gearswap",
        here.parents[1] / "gearswap",
        here.parents[2] / "gearswap",
    ]
    candidates.append(Path.cwd() / "gearswap")
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            if resolved.is_dir() and any(resolved.glob("*.lua")):
                return resolved
        except OSError:
            continue
    return None


def default_file(abbr: str) -> Path | None:
    folder = defaults_dir()
    code = job_abbr(abbr)
    if folder is None or not code:
        return None
    candidate = folder / (code + ".lua")
    return candidate if candidate.is_file() else None


def item_choices(sets: dict[str, dict[str, str]], slot: str) -> list[str]:
    slot = normalize_slot(slot)
    return sorted({items[slot] for items in sets.values() if items.get(slot)})


def apply_set(sets: dict[str, dict[str, str]], path: str,
              items: dict[str, str], *, original_path: str | None = None,
              keep_original: bool = False) -> str:
    """Add/replace a set in place, removing a renamed original when editing."""
    path = normalize_set_path(path)
    items = clean_items(items)
    if not items:
        raise GearError("A set needs at least one item.")
    if original_path:
        original_path = normalize_set_path(original_path)
    if keep_original and original_path and path == original_path:
        raise GearError("Choose a new path for the copy.")
    ignored = original_path if original_path and not keep_original else None
    conflict = path_conflict(path, (other for other in sets if other != ignored))
    if conflict:
        raise GearError("%s collides with %s." % (path, conflict))
    if original_path and not keep_original and original_path != path:
        sets.pop(original_path, None)
    sets[path] = items
    return path
