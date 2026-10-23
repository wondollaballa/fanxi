#!/usr/bin/env python3
"""Import LandSandBoat's zone spawn data into monster_templates / monster_spawns.

LandSandBoat no longer ships mob placement in SQL: every zone carries its own
``data/zones/<zone>/mobs.yaml`` (templates + one entry per spawn point) plus
``regions.yaml`` (the polygons those spawns are placed in when they have no explicit
"at" point).  This tool reads a local mirror of that tree and writes the two tables the
zone loader reads.

    tools/import_lsb_spawns.py --source /tmp/lsbdata --db data/fanxi.db

The mirror is expected to contain ``mobs/<zone>.yaml`` and ``regions/<zone>.yaml``
(``mobs.yaml`` / ``regions.yaml`` as published under data/zones/<zone>/).  A spawn's zone
comes from its mob id, so no name matching is needed: zone = (mobid >> 12) & 0xFFF.

Spawns without a usable position (no "at" and a region we have no polygon for) are
dropped rather than dumped at the origin.

Each spawn keeps its retail targid: the low 12 bits of the LSB spawn id.  The client's own
per-zone entity table is keyed by that number, so a synthetic targid makes it resolve the
wrong name and model -- and refuse to treat the entity as a monster.
"""

import argparse
import glob
import os
import random
import sqlite3
import sys

import yaml

try:  # libyaml is ~20x faster and these files run to tens of thousands of lines
    LOADER = yaml.CSafeLoader
except AttributeError:  # pragma: no cover - depends on the installed wheel
    LOADER = yaml.SafeLoader

MOBS_PER_ZONE = 0  # 0 = every spawn point; a zone's targids come from the data
DEFAULT_RESPAWN = 300
DEFAULT_ROAM = 4.0


def load_yaml(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.load(handle, Loader=LOADER) or {}
    except Exception as exc:  # a broken download should not kill the run
        print("  ! %s: %s" % (path, exc), file=sys.stderr)
        return {}


def look_of(template):
    """(model, size) from a template's render block."""
    render = ((template.get("attributes") or {}).get("render") or {})
    look = render.get("look") or {}
    model = 0
    if isinstance(look, dict):
        model = int(look.get("model") or 0)
    elif isinstance(look, (int, str)):
        model = int(look)
    size = int(render.get("model_size") or 0)
    return model, size


def behaviour_of(template):
    attrs = template.get("attributes") or {}
    behaviours = attrs.get("behaviors") or {}
    spawn = attrs.get("spawn") or {}
    combat = attrs.get("combat") or {}
    stats = attrs.get("stats") or {}
    return {
        "aggro": 1 if behaviours.get("aggressive") else 0,
        "links": 1 if behaviours.get("links") else 0,
        "name_prefix": int(((attrs.get("render") or {}).get("name_prefix")) or 0),
        "hp": int(stats.get("hp") or 0),
        "mp": int(stats.get("mp") or 0),
        "delay": int(combat.get("delay") or 0),
        "respawn": int(spawn.get("respawn") or 0),
        "speed": int(attrs.get("speed") or 0),
    }


def region_point(regions, name, rng):
    if isinstance(name, (list, tuple)):  # a spawn may name several roaming areas
        name = name[rng.randrange(len(name))] if name else None
    if name is None:
        return None
    region = regions.get(name)
    if not isinstance(region, dict):
        return None
    points = region.get("points") or region.get("poly") or []
    flat = [p for p in points if isinstance(p, (list, tuple)) and len(p) >= 3]
    if not flat:
        return None
    x, y, z = flat[rng.randrange(len(flat))][:3]
    return float(x), float(y), float(z)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="/tmp/lsbdata",
                        help="mirror with mobs/ and regions/ (default /tmp/lsbdata)")
    parser.add_argument("--db", default="data/fanxi.db")
    parser.add_argument("--per-zone", type=int, default=MOBS_PER_ZONE,
                        help="cap spawns per zone (0 = no cap)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    ours = {row[0] for row in conn.execute("SELECT id FROM zones")}
    rng = random.Random(20251020)

    files = sorted(glob.glob(os.path.join(args.source, "mobs", "*.yaml")))
    if not files:
        sys.exit("no mobs/*.yaml under %s" % args.source)

    templates = []   # (zone, template key, row dict, level range)
    spawns = []      # (zone, template key, x, y, z, rot, level)
    skipped_position = 0
    skipped_model = 0

    for path in files:
        doc = load_yaml(path)
        zone_spawns = doc.get("spawns") or {}
        if not zone_spawns:
            continue
        zone = (int(next(iter(zone_spawns))) >> 12) & 0xFFF
        if zone not in ours:
            continue
        stem = os.path.basename(path)[:-5]
        regions_doc = load_yaml(os.path.join(args.source, "regions", stem + ".yaml"))
        regions = regions_doc.get("regions") or {}
        defs = doc.get("templates") or {}

        placed = 0
        per_template = {}
        used_targids = set()
        for sid, spawn in zone_spawns.items():
            if args.per_zone and placed >= args.per_zone:
                break
            if not isinstance(spawn, dict):
                continue
            key = spawn.get("template")
            template = defs.get(key)
            if template is None:
                continue
            model, size = look_of(template)
            if not model:
                skipped_model += 1
                continue
            at = spawn.get("at")
            point = None
            if isinstance(at, (list, tuple)) and len(at) >= 3:
                if not all(abs(float(v) - 1.0) < 1e-6 for v in at[:3]):
                    point = (float(at[0]), float(at[1]), float(at[2]))
            if point is None and spawn.get("region"):
                point = region_point(regions, spawn["region"], rng)
            if point is None:
                skipped_position += 1
                continue
            level = spawn.get("level")
            if isinstance(level, (list, tuple)) and level:
                low = int(level[0])
                high = int(level[-1])
            elif isinstance(level, int):
                low = high = level
            else:
                low = high = 1
            per_template.setdefault(key, [low, high])
            per_template[key][0] = min(per_template[key][0], low)
            per_template[key][1] = max(per_template[key][1], high)
            targid = int(sid) & 0xFFF
            if targid in used_targids:
                continue
            used_targids.add(targid)
            spawns.append((zone, key, targid, point[0], point[1], point[2],
                           rng.randrange(256), low))
            placed += 1

        for key, (low, high) in per_template.items():
            templates.append((zone, key, defs[key], low, high))

    if args.dry_run:
        print("templates %d  spawns %d  skipped(no model) %d  skipped(no position) %d"
              % (len(templates), len(spawns), skipped_model, skipped_position))
        return

    template_ids = {}
    with conn:
        conn.execute("DELETE FROM monster_spawns")
        conn.execute("DELETE FROM monster_templates")
        for zone, key, definition, low, high in templates:
            model, size = look_of(definition)
            info = behaviour_of(definition)
            name = str(definition.get("display_name") or key).replace("_", " ")
            hp = info["hp"] or max(1, int((low + high) / 2) * 20)
            cursor = conn.execute(
                "INSERT INTO monster_templates (name, model, size, level_min, level_max, hp, mp,"
                " attack, defense, accuracy, evasion, attack_delay_ms, aggro, links, roam_radius,"
                " respawn_seconds, name_prefix, behavior, content_tag)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, model, size, max(1, low), max(1, high), hp, info["mp"],
                 5 + high * 2, max(1, high // 2), 75 + high, 10 + high,
                 int(info["delay"] * 1000 / 60) if info["delay"] else 3000,
                 info["aggro"], info["links"], DEFAULT_ROAM,
                 info["respawn"] or DEFAULT_RESPAWN, info["name_prefix"], "roam", None))
            template_ids[(zone, key)] = cursor.lastrowid
        conn.executemany(
            "INSERT INTO monster_spawns (template_id, zone, targid, name, pos_x, pos_y, pos_z, rot,"
            " level, respawn_seconds, enabled) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
            [(template_ids[(zone, key)], zone, targid, key.replace("_", " "), x, y, z, rot,
              level, None) for zone, key, targid, x, y, z, rot, level in spawns])

    per_zone = conn.execute(
        "SELECT zone, count(*) FROM monster_spawns GROUP BY zone ORDER BY count(*) DESC").fetchall()
    print("templates %d  spawns %d  zones %d  (skipped: no model %d, no position %d)"
          % (len(templates), len(spawns), len(per_zone), skipped_model, skipped_position))
    print("busiest:", ", ".join("%d:%d" % row for row in per_zone[:8]))


if __name__ == "__main__":
    main()
