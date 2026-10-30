#!/usr/bin/env python3
"""Measure a bard's song-duration ceiling and exercise Nitro / Soul Voice.

The live server has no recast-reset endpoint, and a two-hour or a ten-minute
Troubadour is painful to test by hand.  This script copies ``data/fanxi.db`` to a
temporary file, builds a headless ``ZoneSession`` for the named character, and then:

* reports the song-duration bonus on the gear the character is wearing now;
* reports the best bonus from song-duration gear the character owns;
* reports the best bonus in the whole item table (the theoretical ceiling);
* clears ``session.ability_recasts`` between runs so Nitro (Nightingale +
  Troubadour) and Soul Voice can be used as often as the test needs;
* casts a normal song and Sentinels Scherzo and reports the real buff timer the
  server records.

The live database is opened read-only and copied with SQLite's backup API.  All
writes happen in the temporary copy.

Usage::

    tools/brd_song_duration.py --character Onedough
    tools/brd_song_duration.py --character Onedough --json
    tools/brd_song_duration.py --character Onedough --db data/fanxi.db
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import struct
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from fanxi_server.config import Config  # noqa: E402
from fanxi_server.db import Database  # noqa: E402
from fanxi_server.service import FanxiService  # noqa: E402
from fanxi_server.game import effects, job_points, modifiers as mod, packets  # noqa: E402
from fanxi_server.game.world import World  # noqa: E402
from fanxi_server.game.zone import ZoneSession  # noqa: E402

BARD = 10
SONG_DURATION_BONUS = mod.SONG_DURATION_BONUS
ALL_SONGS_EFFECT = mod.ALL_SONGS_EFFECT
BASE_SONG_SECONDS = 120.0
BRD_JOB_BIT = 1 << (BARD - 1)

# Client equip kind for each item slot.  The song-duration gear only uses these.
JOB_LABELS = {
    1: "WAR", 2: "MNK", 3: "WHM", 4: "BLM", 5: "RDM", 6: "THF", 7: "PLD",
    8: "DRK", 9: "BST", 10: "BRD", 11: "RNG", 12: "SAM", 13: "NIN", 14: "DRG",
    15: "SMN", 16: "BLU", 17: "COR", 18: "PUP", 19: "DNC", 20: "SCH", 21: "GEO",
    22: "RUN",
}

RECAST_NAMES = {109: "Nightingale", 110: "Troubadour"}

SLOT_KIND = {
    "main": 0,
    "range": 2,
    "head": 4,
    "body": 5,
    "hands": 6,
    "legs": 7,
    "feet": 8,
    "neck": 9,
    "waist": 10,
    "ear1": 11,
    "ear2": 12,
    "ring1": 13,
    "ring2": 14,
    "back": 15,
}

# Job-point rows that add flat seconds to a song after Troubadour doubles it.
# Fanxi sends every job every category at rank 20 (zone.JOB_POINT_RANK), so
# these are the values a level 99 bard would have.
JP_FLAT_SECONDS = {
    "Clarion Call Effect": 2 * 20,
    "Tenuto Effect": 2 * 20,
    "Marcato Effect": 1 * 20,
}
JP_FLAT_TOTAL = sum(JP_FLAT_SECONDS.values())
# Soul Voice cancels Marcato, so a Soul Voice song only keeps Clarion Call and
# Tenuto.  The normal-song Nitro ceiling keeps all three.
JP_FLAT_SOUL_VOICE = (JP_FLAT_SECONDS["Clarion Call Effect"]
                      + JP_FLAT_SECONDS["Tenuto Effect"])

# Songs whose *duration* Soul Voice doubles.  Every other party song has its
# potency doubled instead; Soul Voice does not extend its timer.
SOUL_VOICE_DURATION_SONGS = {
    "Hymnus",
    "Mazurka",
    "Sentinels Scherzo",
}


def snapshot(source: Path, target: Path) -> None:
    """Copy a live SQLite database without touching it or its WAL."""
    src = sqlite3.connect("file:%s?mode=ro" % source, uri=True)
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def fmt_seconds(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    whole = int(round(seconds))
    return "%d:%02d (%s s)" % (whole // 60, whole % 60, ("%.1f" % seconds).rstrip("0").rstrip("."))


def gear_bonus(service: FanxiService, character_id: int) -> int:
    return int(service.equipped_mods(int(character_id)).get(SONG_DURATION_BONUS, 0))


def song_bonus(service: FanxiService, character_id: int) -> int:
    """Gear song duration plus the Bard job-point Song Effect Duration gift.

    All Songs counts at 10% per point as well, so the instrument and the JSE neck
    matter even though neither carries a "Song duration" line.  The family rows
    are left out because they only lengthen their own song.
    """
    bonus = gear_bonus(service, character_id)
    bonus += 10 * int(service.equipped_mods(int(character_id)).get(ALL_SONGS_EFFECT, 0))
    try:
        character = service.character(int(character_id))
        bonus += int(job_points.combat_mods(int(character["main_job"])).get(
            SONG_DURATION_BONUS, 0))
    except Exception:
        pass
    return bonus


def gear_value(row) -> int:
    """The song-duration points one piece is worth.

    454 is the explicit "Song duration +N%" line.  All Songs is worth 10% per
    point as well (BG-wiki's Song page), so Loughnashade's +4 is +40% and
    Mnbw. Whistle +1's +3 is +30%.  The family rows ("March"+1 and friends) only
    count for their own song, so they are left out of this generic ranking.
    """
    return int(row["value"] or 0) + 10 * int(row["songs"] or 0)


def _best_by_slot(rows) -> list[dict]:
    """Highest song-duration value per equip slot, with deterministic ties."""
    best: dict[str, dict] = {}
    for row in rows:
        slot = str(row["equip_slot"] or "").lower()
        if slot not in SLOT_KIND:
            continue
        value = gear_value(row)
        current = best.get(slot)
        if current is None or value > int(current["value"]):
            entry = dict(row)
            entry["slot_name"] = slot
            entry["value"] = value
            best[slot] = entry
    return sorted(best.values(), key=lambda item: (-int(item["value"]), item["slot_name"]))


def best_in_item_table(service: FanxiService) -> list[dict]:
    """The best song-duration piece for each slot that a level-99 bard can wear."""
    rows = service.db.all(
        "SELECT i.equip_slot, i.item_id, i.name, i.level, i.jobs, "
        "  COALESCE((SELECT value FROM item_mods m WHERE m.item_id = i.item_id "
        "    AND m.mod_id = ?), 0) AS value, "
        "  COALESCE((SELECT value FROM item_mods m WHERE m.item_id = i.item_id "
        "    AND m.mod_id = ?), 0) AS songs "
        "FROM items i WHERE (i.jobs & ?) <> 0 AND i.level <= 99 "
        "  AND (EXISTS (SELECT 1 FROM item_mods m WHERE m.item_id = i.item_id AND m.mod_id = ?) "
        "    OR EXISTS (SELECT 1 FROM item_mods m WHERE m.item_id = i.item_id AND m.mod_id = ?))",
        (SONG_DURATION_BONUS, ALL_SONGS_EFFECT, BRD_JOB_BIT,
         SONG_DURATION_BONUS, ALL_SONGS_EFFECT))
    return _best_by_slot(rows)


def best_owned(service: FanxiService, character_id: int) -> list[dict]:
    """The best song-duration piece per slot among equipped items and bag copies."""
    select = (
        "SELECT i.equip_slot, i.item_id, i.name, i.level, i.jobs, "
        "  COALESCE((SELECT value FROM item_mods m WHERE m.item_id = i.item_id "
        "    AND m.mod_id = ?), 0) AS value, "
        "  COALESCE((SELECT value FROM item_mods m WHERE m.item_id = i.item_id "
        "    AND m.mod_id = ?), 0) AS songs, "
        "  %s.container AS container, %s.slot AS slot "
        "FROM %s JOIN items i ON i.item_id = %s.item_id "
        "WHERE %s.character_id = ? AND (i.jobs & ?) <> 0 AND i.level <= 99 "
        "  AND (EXISTS (SELECT 1 FROM item_mods m WHERE m.item_id = i.item_id AND m.mod_id = ?) "
        "    OR EXISTS (SELECT 1 FROM item_mods m WHERE m.item_id = i.item_id AND m.mod_id = ?))")
    rows = []
    for table in ("char_equip", "char_inventory"):
        rows += list(service.db.all(
            select % (table, table, table, table, table),
            (SONG_DURATION_BONUS, ALL_SONGS_EFFECT, int(character_id), BRD_JOB_BIT,
             SONG_DURATION_BONUS, ALL_SONGS_EFFECT)))
    return _best_by_slot(rows)


def apply_loadout(service: FanxiService, character_id: int, loadout: list[dict]) -> None:
    """Equip one song-duration piece per slot in the temporary database.

    A piece the loadout does not name is cleared from the other slots first: a
    second Carnwenhan in the sub slot, or a leftover 454 body piece, would otherwise
    stack with the theoretical set and overstate the cap.
    """
    with service.db.transaction() as conn:
        kinds = [SLOT_KIND[str(item["equip_slot"]).lower()] for item in loadout]
        if kinds:
            holes = ",".join("?" for _ in kinds)
            conn.execute(
                "DELETE FROM char_equip WHERE character_id = ? "
                f"AND kind NOT IN ({holes}) AND item_id IN "
                "(SELECT item_id FROM item_mods WHERE mod_id = ?)",
                (int(character_id), *kinds, SONG_DURATION_BONUS))
        for item in loadout:
            kind = SLOT_KIND[str(item["equip_slot"]).lower()]
            container = item.get("container")
            slot = item.get("slot")
            if container is None or slot is None:
                # A theoretical item is not in any bag.  Use a slot no container can
                # own so equipped_mods cannot pick up another item's augment block.
                container, slot = -1, -(kind + 1)
            conn.execute(
                "INSERT OR REPLACE INTO char_equip "
                "(character_id, kind, container, slot, item_id) VALUES (?, ?, ?, ?, ?)",
                (int(character_id), kind, int(container), int(slot), int(item["item_id"])))


def build_session(config: Config, service: FanxiService, row) -> ZoneSession:
    """A zone-in-ready session for one character, without opening a socket."""
    record = service.character_record(row, service.server_name())
    world = World(config, service, None)
    session = ZoneSession(world, None, record)
    session.set_key(bytes(20))
    session.logged_in = True
    # The family-party recovery path needs a live world; this harness only needs
    # the character, so keep the login burst out of the party bookkeeping.
    session.fresh_login = False
    world.sessions[("127.0.0.1", 59999)] = session
    session.zone = int(record.get("zone") or 0)
    session.pos = list(world.zones.position(session.zone))
    session.load_zone_entities()
    session.after_zone_in()
    session.queue.clear()
    session.zone_loaded = True
    return session


def clear_effects(session: ZoneSession) -> None:
    session.effect_state.clear()
    session.status_effects.clear()
    session.casting = None
    session.queue.clear()


def reset_ability_timers(session: ZoneSession) -> dict[int, float]:
    """Clear every job-ability recast; returns the timers that were running."""
    now = time.time()
    running = {
        int(recast_id): max(0.0, float(ready_at) - now)
        for recast_id, ready_at in session.ability_recasts.items()
        if float(ready_at) > now
    }
    session.ability_recasts.clear()
    # A real server would answer with a 0x119; queue it so the harness follows the
    # same path, then discard it: there is no client here to read the packet.
    session.queue.append(session.abil_recast())
    session.queue.clear()
    return running


def recast_seconds(session: ZoneSession, recast_id: int) -> float:
    if not recast_id:
        return 0.0
    return max(0.0, float(session.ability_recasts.get(int(recast_id), 0.0)) - time.time())


def use_ability(session: ZoneSession, service: FanxiService, name: str) -> dict:
    ability = service.job_ability_by_name(name)
    if ability is None:
        raise SystemExit("job ability not found: %s" % name)
    ability_id = int(ability["id"])
    recast_id = int(ability.get("recast_id") or 0)
    packet = bytearray(16)
    struct.pack_into("<IHH", packet, 0, int(session.char["char_id"]), 0,
                     packets.ACTION_JOBABILITY)
    struct.pack_into("<I", packet, 12, ability_id)
    session.job_ability(bytes(packet), 0)
    session.queue.clear()
    state = session.effect(effects.ABILITY_EFFECTS[ability_id].effect) \
        if ability_id in effects.ABILITY_EFFECTS else None
    return {
        "name": name,
        "id": ability_id,
        "recast_id": recast_id,
        "recast": round(recast_seconds(session, recast_id), 1),
        "status": None if state is None else round(float(state["until"]) - time.time(), 1),
    }


def song_state(session: ZoneSession, name: str):
    """The caster's state for one song.

    Songs are stored under ``effects.song_key(spell_id)`` rather than the shared
    status icon, so ``session.effect(spec.effect)`` cannot find them.
    """
    wanted = " ".join(str(name).casefold().split())
    for state in session.effect_state.values():
        if (state.get("song")
                and " ".join(str(state.get("song_name", "")).casefold().split()) == wanted):
            return state
    return None


def cast_song(session: ZoneSession, service: FanxiService, name: str) -> dict:
    spell = service.spell_by_name(name)
    spec = effects.for_spell(name)
    if spell is None or spec is None:
        raise SystemExit("song not found: %s" % name)
    packet = bytearray(16)
    struct.pack_into("<IHHI", packet, 4, 0, 0, packets.ACTION_CAST_MAGIC, int(spell["id"]))
    session.casting = None
    before = time.time()
    session.cast_magic(bytes(packet), 0)
    finish = float(session.casting["finish"]) - before if session.casting else 0.0
    session.queue.clear()
    # The client's tick resolves the song after its 8 s cast bar.
    session.tick(time.time() + 30.0)
    state = song_state(session, name)
    if state is None:
        raise SystemExit("%s finished without landing on the caster" % name)
    return {
        "name": name,
        "effect": int(spec.effect),
        "cast": round(finish, 2),
        "duration": round(float(state["until"]) - time.time(), 1),
    }


def run_gear_tier(session: ZoneSession, service: FanxiService) -> dict:
    """One gear setup: baseline, Nitro, Soul Voice, and both together."""
    def measure(setup: tuple[str, ...], song: str) -> dict:
        running = reset_ability_timers(session)
        clear_effects(session)
        abilities = [use_ability(session, service, name) for name in setup]
        result = cast_song(session, service, song)
        result["abilities"] = abilities
        result["reset"] = running
        return result

    baseline = measure((), "Valor Minuet V")
    nitro = measure(("Nightingale", "Troubadour"), "Valor Minuet V")
    soul_voice = measure(("Soul Voice",), "Sentinels Scherzo")
    both = measure(("Soul Voice", "Nightingale", "Troubadour"), "Sentinels Scherzo")

    # Prove the reset really allows a second use of an hour/ten-minute ability.
    # measure() clears the timers first and records what it cleared.
    second_nitro = measure(("Nightingale", "Troubadour"), "Valor Minuet V")

    return {
        "bonus": song_bonus(service, int(session.char["id"])),
        "base": BASE_SONG_SECONDS,
        "server_duration": BASE_SONG_SECONDS * (1.0 + song_bonus(service, int(session.char["id"])) / 100.0),
        "baseline": baseline,
        "nitro": nitro,
        "soul_voice": soul_voice,
        "both": both,
        "second_nitro": second_nitro,
    }


def retail_ceiling(bonus: int) -> dict:
    """The retail formula for comparison, not the current Fanxi behaviour."""
    after_gear = BASE_SONG_SECONDS * (1.0 + bonus / 100.0)
    nitro = after_gear * 2.0
    both = after_gear * 2.0 * 2.0
    return {
        "gear": round(after_gear, 1),
        "nitro": round(nitro, 1),
        "nitro_jp": round(nitro + JP_FLAT_TOTAL, 1),
        "soul_voice": round(both, 1),
        "soul_voice_jp": round(both + JP_FLAT_SOUL_VOICE, 1),
    }


def describe_loadout(loadout: list[dict]) -> str:
    if not loadout:
        return "none"
    return ", ".join("%s +%d%%" % (item["name"], int(item["value"])) for item in loadout)


def describe_timers(running: dict[int, float]) -> str:
    """The recasts a reset cleared, with the ability names we care about."""
    if not running:
        return "none"
    return ", ".join("%s %.0fs" % (RECAST_NAMES.get(int(rid), "recast %d" % int(rid)),
                                  seconds) for rid, seconds in sorted(running.items()))


def print_report(report: dict) -> None:
    print("Fanxi bard song duration — %s (%s %d/%s %d)" % (
        report["name"], report["job"], report["level"], report["sub_job"], report["sub_level"]))
    print("database: %s (snapshot; the live file is not written)" % report["database"])
    print()
    print("Gear tiers (454 + 10% per All Songs point + 5% job-point gift; a family"
          " row adds 10% more to its own song)")
    for tier in report["tiers"]:
        print("  %-16s +%d%%  server song = %s" % (
            tier["label"], tier["bonus"], fmt_seconds(tier["server_duration"])))
        print("      %s" % tier["loadout"])
    print()
    print("Live behaviour in the headless session (abilities reset between runs)")
    header = "  %-16s %-14s %-14s %-14s %-14s %s" % (
        "gear", "Minuet", "Minuet+Nitro", "Scherzo+SV", "Scherzo+SV+Nitro", "2nd Nitro")
    print(header)
    for tier in report["tiers"]:
        print("  %-16s %-14s %-14s %-14s %-14s %s" % (
            tier["label"], fmt_seconds(tier["baseline"]["duration"]),
            fmt_seconds(tier["nitro"]["duration"]),
            fmt_seconds(tier["soul_voice"]["duration"]),
            fmt_seconds(tier["both"]["duration"]),
            fmt_seconds(tier["second_nitro"]["duration"])))
    print()
    print("Ability timers the script cleared before the second Nitro run")
    for tier in report["tiers"]:
        print("  %-16s %s" % (tier["label"], describe_timers(tier["second_nitro"]["reset"])))
    print()
    print("Nitro statuses / recasts")
    for tier in report["tiers"]:
        nitro = tier["nitro"]
        details = []
        for ability in nitro["abilities"]:
            details.append("%s status=%.1fs recast=%.1fs" % (
                ability["name"], ability["status"] or 0.0, ability["recast"]))
        print("  %-16s cast=%.2fs  %s" % (tier["label"], nitro["cast"], "; ".join(details)))
        sv = tier["soul_voice"]["abilities"][0] if tier["soul_voice"]["abilities"] else {}
        print("  %-16s baseline cast=%.2fs -> Nitro cast=%.2fs; "
              "Soul Voice status=%.1fs, recast=%s" % (
                  "", tier["baseline"]["cast"], nitro["cast"], sv.get("status") or 0.0,
                  "tracked" if sv.get("recast") else "none"))
    print()
    print("Retail-formula ceiling (the rules the server now applies)")
    print("  %-16s %-12s %-30s %s" % (
        "gear", "gear song", "Troubadour x2 (then +JP)", "SV + Troubadour on Scherzo (then +JP)"))
    for tier in report["tiers"]:
        ceiling = tier["retail"]
        print("  %-16s %-12s %-30s %s" % (
            tier["label"], fmt_seconds(ceiling["gear"]),
            "%s -> %s" % (fmt_seconds(ceiling["nitro"]), fmt_seconds(ceiling["nitro_jp"])),
            "%s -> %s" % (fmt_seconds(ceiling["soul_voice"]),
                          fmt_seconds(ceiling["soul_voice_jp"]))))
    print()
    print("JP flat = Clarion Call %ds + Tenuto %ds + Marcato %ds = %ds, added after the"
          % (JP_FLAT_SECONDS["Clarion Call Effect"], JP_FLAT_SECONDS["Tenuto Effect"],
             JP_FLAT_SECONDS["Marcato Effect"], JP_FLAT_TOTAL))
    print("Troubadour doubling.  Soul Voice doubles duration only for Hymnus, Mazurka and")
    print("Sentinels Scherzo; on other songs it doubles potency, not the timer.")
    print("Soul Voice and Marcato do not stack, so the SV column uses Clarion + Tenuto")
    print("(%ds), not Marcato's %ds." % (JP_FLAT_SOUL_VOICE, JP_FLAT_SECONDS["Marcato Effect"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", default="Onedough", help="character name (default: Onedough)")
    parser.add_argument("--db", default=str(ROOT / "data" / "fanxi.db"), help="live database to snapshot")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args()

    logging.disable(logging.CRITICAL)
    source = Path(args.db).resolve()
    if not source.exists():
        raise SystemExit("database not found: %s" % source)

    with tempfile.TemporaryDirectory(prefix="fanxi-brd-") as folder:
        tmp = Path(folder)
        db_path = tmp / "fanxi.db"
        snapshot(source, db_path)
        config = Config(
            root=ROOT, db_path=db_path,
            tls_cert=tmp / "tls" / "auth-cert.pem",
            tls_key=tmp / "tls" / "auth-key.pem",
            nav_dir=tmp / "nav", nav_enabled=False)
        config.ensure_dirs()
        database = Database(db_path, ROOT)
        database.initialize()  # apply the latest song migrations to the snapshot
        service = FanxiService(config, database)

        row = service.db.one(
            "SELECT * FROM characters WHERE name = ? COLLATE NOCASE", (args.character,))
        if row is None:
            raise SystemExit("character not found: %s" % args.character)
        if int(row["main_job"]) != BARD:
            raise SystemExit("%s is not on BRD (main job %d)" % (row["name"], int(row["main_job"])))
        session = build_session(config, service, row)
        character_id = int(row["id"])

        tiers = []

        current_bonus = song_bonus(service, character_id)
        current_gear = service.db.all(
            "SELECT i.equip_slot, i.item_id, i.name, i.level, i.jobs, im.value "
            "FROM char_equip e JOIN items i ON i.item_id = e.item_id "
            "JOIN item_mods im ON im.item_id = i.item_id AND im.mod_id = ? "
            "WHERE e.character_id = ? ORDER BY e.kind",
            (SONG_DURATION_BONUS, character_id))
        current = run_gear_tier(session, service)
        tiers.append({
            "label": "equipped now", "bonus": current_bonus,
            "loadout": describe_loadout([dict(item) for item in current_gear]) or "none",
            "server_duration": current["server_duration"],
            "baseline": current["baseline"], "nitro": current["nitro"],
            "soul_voice": current["soul_voice"], "both": current["both"],
            "second_nitro": current["second_nitro"],
            "retail": retail_ceiling(current_bonus),
        })

        owned = best_owned(service, character_id)
        apply_loadout(service, character_id, owned)
        owned_bonus = song_bonus(service, character_id)
        owned_run = run_gear_tier(session, service)
        tiers.append({
            "label": "best owned", "bonus": owned_bonus,
            "loadout": describe_loadout(owned),
            "server_duration": owned_run["server_duration"],
            "baseline": owned_run["baseline"], "nitro": owned_run["nitro"],
            "soul_voice": owned_run["soul_voice"], "both": owned_run["both"],
            "second_nitro": owned_run["second_nitro"],
            "retail": retail_ceiling(owned_bonus),
        })

        best = best_in_item_table(service)
        apply_loadout(service, character_id, best)
        best_bonus = song_bonus(service, character_id)
        best_run = run_gear_tier(session, service)
        tiers.append({
            "label": "best in item DB", "bonus": best_bonus,
            "loadout": describe_loadout(best),
            "server_duration": best_run["server_duration"],
            "baseline": best_run["baseline"], "nitro": best_run["nitro"],
            "soul_voice": best_run["soul_voice"], "both": best_run["both"],
            "second_nitro": best_run["second_nitro"],
            "retail": retail_ceiling(best_bonus),
        })

        report = {
            "name": row["name"],
            "job": JOB_LABELS.get(int(row["main_job"]), str(row["main_job"])),
            "level": int(row["main_level"]),
            "sub_job": JOB_LABELS.get(int(row["sub_job"]), str(row["sub_job"])),
            "sub_level": int(row["sub_level"]),
            "database": str(source),
            "base_song": BASE_SONG_SECONDS,
            "jp_flat": JP_FLAT_TOTAL,
            "jp_flat_soul_voice": JP_FLAT_SOUL_VOICE,
            "tiers": tiers,
        }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
