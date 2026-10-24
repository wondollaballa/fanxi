"""What an item's augments add to the stat sheet.

The client stores augments in the item's 24-byte ``extdata`` block and draws the
tooltip from them.  The server has always written those blocks (``!r30``, ``!rp30``,
``!cape``, the launcher's augment card) but never read them back, so a Rank 30
Revelation set granted its base stats and none of its ``"Double Attack"+7%`` rows.
This module is the missing direction: block -> augment text -> the modifier ids the
combat path already reads.

Two block families exist:

* **bundled augments** (``kind 0x03, subkind 0x83``), used by Odyssey, Limbus and
  Unity.  The block names a bundle index and the piece's rows live in
  ``data/odyssey_r30.json``, ``data/limbus_r30.json`` and :mod:`unity`.  Rows are
  applied only when the block's rank reaches the row's rank, so an unranked copy
  adds nothing.
* **standard augments** (``kind 0x02, subkind 0x03``), used by the Ambuscade job
  capes: five ``(augment id, value)`` words.  :mod:`capes` already renders those
  words back to text, so both families share one parser.

Only modifiers the engine actually reads are mapped.  A handful of tooltip lines
name stats the engine has no model for yet (pet stats, Snapshot, "Chance of
successful block", ...); they are listed in :data:`UNMODELLED` so the test that
walks every dataset row fails when a *new* line appears that nothing handles.
"""
from __future__ import annotations

import re
from functools import lru_cache

from . import augment_gear, augments, capes
from . import modifiers as mod

# A value is always signed: "Accuracy+30", "Damage taken-10%", '"+7%"' after the name.
_VALUE = re.compile(r"([+-])\s*(\d+)\s*(%?)")

# Flat modifiers: the number is the modifier value.
_FLAT = {
    "def": mod.DEF,
    "hp": mod.HP,
    "mp": mod.MP,
    "str": mod.STR,
    "dex": mod.DEX,
    "vit": mod.VIT,
    "agi": mod.AGI,
    "int": mod.INT,
    "mnd": mod.MND,
    "chr": mod.CHR,
    "attack": mod.ATT,
    "att": mod.ATT,
    "rangedattack": mod.RATT,
    "rngatk": mod.RATT,
    "ratk": mod.RATT,
    "accuracy": mod.ACC,
    "acc": mod.ACC,
    "rangedaccuracy": mod.RACC,
    "rngacc": mod.RACC,
    "racc": mod.RACC,
    "magacc": mod.MACC,
    "macc": mod.MACC,
    "magicaccuracy": mod.MACC,
    "magatkbonus": mod.MATT,
    "magicatkbonus": mod.MATT,
    "magatkbns": mod.MATT,
    "magdevasion": mod.MEVA,
    "magevasion": mod.MEVA,
    "mageva": mod.MEVA,
    "meva": mod.MEVA,
    "evasion": mod.EVA,
    "eva": mod.EVA,
    "magicdamage": mod.MAGIC_DAMAGE,
    "magdmg": mod.MAGIC_DAMAGE,
    "enmity": mod.ENMITY,
}

# Percent-integer modifiers: "Store TP"+7 stores 7; the engine divides by 100 itself.
_PERCENT = {
    "storetp": mod.STORETP,
    "dualwield": mod.DUAL_WIELD,
    "fastcast": mod.FASTCAST,
    "doubleattack": mod.DOUBLE_ATTACK,
    "dblatk": mod.DOUBLE_ATTACK,
    "tripleattack": mod.TRIPLE_ATTACK,
    "quadrupleattack": mod.QUADRUPLE_ATTACK,
    "subtleblow": mod.SUBTLE_BLOW,
    "subtleblowii": mod.SUBTLE_BLOW_II,
    "counter": mod.COUNTER,
    "curepotency": mod.CURE_POTENCY,
    "drainandaspirpotency": mod.DRAIN_ASPIR,
    "refresh": mod.REFRESH,
    "regen": mod.REGEN,
    "physdmglimit": mod.DAMAGE_LIMITP,
    "physicaldamagelimit": mod.DAMAGE_LIMITP,
    "weaponskilldamage": mod.WSD_ALL_HITS,
    "weaponskilldmg": mod.WSD_ALL_HITS,
    "skillchaindmg": mod.SKILLCHAIN_BONUS,
    "skillchaindamage": mod.SKILLCHAIN_BONUS,
}

# Hundredths-of-a-percent modifiers: "Damage taken-10%" stores -1000.
_HUNDREDTHS = {
    "damagetaken": mod.DMG,
    "physdmgtaken": mod.DMGPHYS,
    "physicaldamagetaken": mod.DMGPHYS,
    "magicdmgtaken": mod.DMGMAGIC,
    "magicdamagetaken": mod.DMGMAGIC,
    "crithitrate": mod.CRIT_HIT_RATE,
}

# The attributes "All Attr." raises together.
_ATTRIBUTES = (mod.STR, mod.DEX, mod.VIT, mod.AGI, mod.INT, mod.MND, mod.CHR)

# Tooltip lines whose stat the engine does not model yet.  Everything here is
# tracked so a new dataset row cannot slip through unnoticed.
UNMODELLED = {
    "bloodpactdamage",          # summoner blood pacts
    "chanceofsuccessfulblock",  # block rate is derived from shield size only
    "dmg",                      # weapon damage rating comes from item_weapon
    "doubleattackdamage",       # "Double Attack" damage bonus
    "magicburstdamage",         # magic burst damage
    "magicburstdamageii",
    "occincresisttostatailments",
    "phalanxreceived",
    "snapshot",
    "spellinterruptionratedown",
}

# Lines with no signed value at all cannot be tokenised; they are listed verbatim.
UNMODELLED_LINES = {
    "Spell interruption rate down 10%",
}

MAPPED = set(_FLAT) | set(_PERCENT) | set(_HUNDREDTHS) | {"allattr"}


def _key(text: str) -> str:
    """Normalise an augment name: no quotes, dots, colons or spaces."""
    cleaned = str(text or "")
    for ch in ("\"", "'", ".", ":", " ", "\t"):
        cleaned = cleaned.replace(ch, "")
    return cleaned.casefold()


def _names(chunk: str) -> list[str]:
    """The stat names in one slice of an augment line.

    A slash means the value applies to each name around it: ``DEX/AGI+10`` raises
    both, ``Acc/Rng. Acc./M. Acc.+30`` raises three.
    """
    raw = chunk.strip().lstrip(" /,;|")
    if not raw:
        return []
    # Pet lines ("Pet: Accuracy+30 Pet: Rng. Acc.+20") are not modelled.
    if raw.casefold().startswith("pet:"):
        return []
    return [part.strip() for part in raw.split("/") if part.strip()]


def keys_in(line: str) -> tuple[str, ...]:
    """Every normalised stat name one tooltip line mentions (for coverage tests)."""
    text = str(line or "")
    found: list[str] = []
    position = 0
    for match in _VALUE.finditer(text):
        for name in _names(text[position:match.start()]):
            found.append(_key(name))
        position = match.end()
    if not found and text.strip():
        return ("",)
    return tuple(found)


@lru_cache(maxsize=1024)
def _parsed(line: str) -> tuple[tuple[int, int], ...]:
    if line in UNMODELLED_LINES:
        return ()
    text = str(line or "")
    out: dict[int, int] = {}
    position = 0
    for match in _VALUE.finditer(text):
        sign, digits, _percent = match.groups()
        value = int(digits) * (1 if sign == "+" else -1)
        for name in _names(text[position:match.start()]):
            key = _key(name)
            if key == "allattr":
                for mod_id in _ATTRIBUTES:
                    out[mod_id] = out.get(mod_id, 0) + value
            elif key in _FLAT:
                out[_FLAT[key]] = out.get(_FLAT[key], 0) + value
            elif key in _PERCENT:
                out[_PERCENT[key]] = out.get(_PERCENT[key], 0) + value
            elif key in _HUNDREDTHS:
                scaled = value * 100
                out[_HUNDREDTHS[key]] = out.get(_HUNDREDTHS[key], 0) + scaled
        position = match.end()
    return tuple(sorted(out.items()))


def parse_line(line: str) -> dict[int, int]:
    """The modifiers one augment tooltip line adds."""
    return dict(_parsed(str(line or "")))


def parse_rows(rows) -> dict[int, int]:
    """The modifiers a list of augment lines adds, summed."""
    out: dict[int, int] = {}
    for row in rows or ():
        for mod_id, value in _parsed(str(row)):
            out[int(mod_id)] = out.get(int(mod_id), 0) + int(value)
    return out


@lru_cache(maxsize=1)
def _registry() -> dict[int, dict]:
    """item id -> the augment paths ``augment_gear`` exports (Odyssey/Limbus/Unity)."""
    return augment_gear.entries()


def _bundle_mods(item_id: int, raw: bytes) -> dict[int, int]:
    decoded = augments.decode(raw)
    if not decoded:
        return {}
    entry = _registry().get(int(item_id))
    if entry is None:
        return {}
    path = None
    for candidate in entry.get("paths", ()):
        if candidate.get("bundle") is None:
            continue
        if int(candidate["bundle"]) == int(decoded["index"]):
            path = candidate
            break
    if path is None:
        # Retail can carry a bundle this checkout does not table; fall back to the
        # path letter so a known single-path piece still reads.
        path = next((candidate for candidate in entry.get("paths", ())
                     if str(candidate.get("key", "")).upper() == decoded["path"]), None)
    if path is None or int(decoded["rank"]) < int(path.get("rank", 0)):
        return {}
    return parse_rows(path.get("augments"))


def _standard_mods(raw: bytes) -> dict[int, int]:
    out: dict[int, int] = {}
    for slot in capes.decode(raw) or ():
        if not int(slot.get("id") or 0):
            continue
        for mod_id, value in _parsed(capes.slot_text(slot)):
            out[int(mod_id)] = out.get(int(mod_id), 0) + int(value)
    return out


def item_mods(item_id: int, extra: bytes | None) -> dict[int, int]:
    """The modifiers an equipped item's augment block adds.

    Returns an empty dict when the item is not augmented, or when the block is for a
    rank this checkout has no row data for.
    """
    raw = bytes(extra or b"")
    if len(raw) < 12:
        return {}
    if raw[0] == 0x03 and raw[1] == 0x83:
        return _bundle_mods(int(item_id), raw)
    if raw[0] == capes.AUGMENT_KIND and raw[1] == capes.AUGMENT_SUBKIND:
        return _standard_mods(raw)
    return {}


def add_item_mods(target: dict[int, int], item_id: int, extra: bytes | None) -> None:
    """Merge one item's augment modifiers into *target* (gear/trait modifier dict)."""
    for mod_id, value in item_mods(item_id, extra).items():
        target[int(mod_id)] = target.get(int(mod_id), 0) + int(value)
