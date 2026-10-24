"""Import every spell LandSandBoat gives a status icon to into a Fanxi table.

The server's hand-written table in ``game/effects.py`` covers the spells whose numbers
it actually models (ticks, potency, modifiers).  Everything else -- the whole Bar- line,
the Boost- line, the enfeebling ga, the songs -- used to fall through and cast with no
icon at all.  This tool reads LandSandBoat's four spell tables, maps each spell to the
client's effect id (``data/status_effects.yaml``) and writes
``server/fanxi_server/game/spell_effects.py``, which ``effects.py`` merges *under* its
curated table so the detailed entries still win.

Usage::

    tools/import_lsb_spell_effects.py --source /tmp/lsb
    tools/import_lsb_spell_effects.py --source /tmp/lsb --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# kind, effect column, duration column, tick column (None when the table has none)
TABLES = {
    "enhancing_spell.lua":    ("buff",   1, 4, None),
    "enfeebling_spell.lua":   ("debuff", 0, 5, 4),
    "enhancing_ninjutsu.lua": ("buff",   1, 3, None),
    "enhancing_song.lua":     ("buff",   1, None, None),
    "enfeebling_song.lua":    ("debuff", 0, 4, None),
}

# The enhancing table's power column is the per-tick value for these two.
TICK_FROM_POWER = {"REGEN", "REFRESH"}
# Enfeebling rows the generated table fills a tick for.  HELIX is deliberately absent:
# its column is the ten-second *interval*, and its real tick is the opening nuke's
# damage, so effects.py curates the whole line instead.
DOT_EFFECTS = {"POISON", "BIO", "PLAGUE", "BURN", "FROST", "CHOKE", "RASP",
               "SHOCK", "DROWN"}
SONG_DURATION = 120          # base song length, before instrument and song bonuses


# The client's spell list spells the Thunder Threnody line "Ltng", while LandSandBoat
# spells it "Lightning".  Normalising the abbreviation is what lets the importer match
# the two names; without it the row is dropped and the spell casts with no icon.
ALIASES = {"ltng": "lightning"}


def norm(name: str) -> str:
    """Loose comparison key: case, hyphens, punctuation and known abbreviations."""
    text = name.lower().replace("-", " ").replace("_", " ")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [ALIASES.get(word, word) for word in text.split()]
    return " ".join(words)


def spell_key(name: str) -> str:
    """The key ``effects.for_spell()`` looks up: casefolded, whitespace collapsed."""
    return " ".join(str(name).casefold().split())


def load_effect_ids(path: Path) -> dict[str, int]:
    """status_effects.yaml -> {'light_arts': 358, ...}."""
    out: dict[str, int] = {}
    key = None
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"^  ([a-z0-9_]+):\s*$", line)
        if m:
            key = m.group(1)
            continue
        m = re.match(r"^    id:\s*(\d+)\s*$", line)
        if m and key:
            out[key] = int(m.group(1))
            key = None
    return out


def rows(path: Path):
    """Every ``[xi.magic.spell.NAME] = { ... }`` row in a spell table."""
    for m in re.finditer(r"\[xi\.magic\.spell\.([A-Z0-9_]+)\s*\]\s*=\s*\{([^}]*)\}",
                         path.read_text(errors="replace")):
        yield m.group(1), [field.strip() for field in m.group(2).split(",")]


def effect_name(field: str) -> str | None:
    m = re.fullmatch(r"xi\.effect\.([A-Z0-9_]+)", field)
    return m.group(1) if m else None


def as_int(field: str) -> int:
    return int(field) if re.fullmatch(r"-?\d+", field) else 0


def spell_rows(globals_dir: Path, effect_ids: dict[str, int]):
    """{LSB spell name: (effect id, kind, duration, tick)} for every table row."""
    out: dict[str, tuple[int, str, int, int]] = {}
    for filename, (kind, col_effect, col_duration, col_tick) in TABLES.items():
        path = globals_dir / filename
        if not path.exists():
            continue
        for name, fields in rows(path):
            if len(fields) <= col_effect:
                continue
            effect = effect_name(fields[col_effect])
            if not effect or effect == "NONE":
                continue                       # Dispel and friends put up no icon
            effect_id = effect_ids.get(effect.lower())
            if effect_id is None:
                continue
            duration = (as_int(fields[col_duration])
                        if col_duration is not None and len(fields) > col_duration else 0)
            if filename == "enhancing_song.lua":
                duration = SONG_DURATION
            tick = 0
            if effect.upper() in TICK_FROM_POWER:
                tick = as_int(fields[col_tick if col_tick is not None else 3])
            elif effect.upper() in DOT_EFFECTS and col_tick is not None and len(fields) > col_tick:
                tick = as_int(fields[col_tick])
            out[name] = (effect_id, kind, duration, tick)
    return out


def build_missing(source: Path, db_path: Path, yaml_path: Path) -> list[tuple[str, int, str, int, int]]:
    """The rows Fanxi's curated table does not have yet, keyed by its own spell names."""
    effect_ids = load_effect_ids(yaml_path)
    mapped = spell_rows(source / "scripts/globals/spells", effect_ids)
    conn = sqlite3.connect(db_path)
    try:
        names = [row[0] for row in conn.execute("SELECT name FROM spells")]
    finally:
        conn.close()
    by_norm: dict[str, list[str]] = {}
    for name in names:
        by_norm.setdefault(norm(name), []).append(name)

    sys.path.insert(0, str(ROOT / "server"))
    from fanxi_server.game import effects  # noqa: E402  (needs the checkout on the path)

    # Compare against the hand-written tables only: SPELLS also carries the generated
    # layer, and diffing against that would call every row already covered.
    curated = {}
    curated.update(effects._ninjutsu())
    curated.update(effects._black_magic())
    curated.update(effects._white_magic())
    curated.update(effects._helix())
    have = {norm(key) for key in curated}
    missing = []
    for lsb_name, (effect_id, kind, duration, tick) in sorted(mapped.items()):
        key = norm(lsb_name)
        for db_name in by_norm.get(key, ()):
            if key not in have:
                missing.append((spell_key(db_name), effect_id, kind, duration, tick))
    missing.sort()
    return missing


def render(rows) -> str:
    lines = [
        '"""Status icons for every spell the engine does not model in numbers.',
        "",
        "Generated by tools/import_lsb_spell_effects.py from LandSandBoat's enhancing,",
        "enfeebling, ninjutsu and song tables; one entry per spell that puts an icon on",
        "the bar.  effects.py merges this under its curated tables, so a spell with real",
        "mechanics (tick, potency, modifiers) there still wins.",
        "",
        "Do not edit by hand: rerun the tool.",
        '"""',
        "",
        "STATUS_SPELLS: dict[str, tuple[int, str, float, int]] = {",
    ]
    for name, effect_id, kind, duration, tick in rows:
        lines.append('    "%s": (%d, "%s", %d, %d),' % (
            name.replace('"', '\\"'), effect_id, kind, duration, tick))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default="/tmp/lsb",
                    help="LandSandBoat checkout (scripts/globals/spells is read)")
    ap.add_argument("--db", default=str(ROOT / "data" / "fanxi.db"))
    ap.add_argument("--yaml", default="",
                    help="status_effects.yaml (default: <source>/data/status_effects.yaml)")
    ap.add_argument("--out", default=str(ROOT / "server/fanxi_server/game/spell_effects.py"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when the committed table is out of date")
    args = ap.parse_args()

    source = Path(args.source)
    yaml_path = Path(args.yaml) if args.yaml else source / "data/status_effects.yaml"
    if not (source / "scripts/globals/spells").is_dir():
        raise SystemExit("no scripts/globals/spells under %s" % source)
    if not yaml_path.is_file():
        raise SystemExit("no status_effects.yaml at %s" % yaml_path)

    rows_out = build_missing(source, Path(args.db), yaml_path)
    text = render(rows_out)
    out = Path(args.out)
    print("%d spells get an icon from the generated table" % len(rows_out))
    if args.check:
        current = out.read_text() if out.exists() else ""
        if current != text:
            print("out of date: %s" % out)
            return 1
        print("up to date")
        return 0
    out.write_text(text)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
