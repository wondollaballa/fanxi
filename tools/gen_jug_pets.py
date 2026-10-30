#!/usr/bin/env python3
"""Generate the Call Beast jug catalogue: item -> pet, model and Ready moves.

Two consumers read the same data:

* ``data/jug_pets.json`` for the zone server (the pet to spawn, its model and level), and
* ``host/addons/lua/jugpets.lua`` for the in-game HUD (the jug picker and the pet's
  Ready moves).

The source is a LandSandBoat checkout.  ``item_weapon.subskill`` is the pet id a jug
summons; ``pet_list`` names that pet and points at a ``mob_pools`` row whose
``skill_list_id`` names the pet's moves in ``mob_skill_lists``; ``pet_skills`` gives
each move its display name.  Fanxi's own jug list comes from
``database/migrations/0070_bst_consumables.sql`` so only items the server sells are
listed.

    tools/gen_jug_pets.py --source /tmp/lsb_full
    tools/gen_jug_pets.py --source /tmp/lsb_full --check   # fail if the files drift
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JSON_OUT = ROOT / 'data' / 'jug_pets.json'
LUA_OUT = ROOT / 'host' / 'addons' / 'lua' / 'jugpets.lua'
MIGRATION = ROOT / 'database' / 'migrations' / '0070_bst_consumables.sql'

# The internal names are mostly readable once spaced; these are the ones where a plain
# title case would read wrong ("Tp Drainkiss", "Hi-Freq Field").
MOVE_WORDS = {
    'tp': 'TP', 'hp': 'HP', 'mp': 'MP', 'aoe': 'AoE', 'freq': 'Freq',
}

PET_WORDS = {
    'p': 'P.',
}


def sql_values(line: str) -> list[str]:
    """One LSB INSERT line's VALUES fields, single quotes respected."""
    start = line.find('VALUES (')
    if start < 0:
        return []
    text = line[start + 8:].split(');', 1)[0]
    out: list[str] = []
    current: list[str] = []
    quoted = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            if quoted and index + 1 < len(text) and text[index + 1] == "'":
                current.append("'")
                index += 2
                continue
            quoted = not quoted
            index += 1
            continue
        if char == ',' and not quoted:
            out.append(''.join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    out.append(''.join(current).strip())
    return out


def display_name(internal: str, words: dict[str, str] | None = None) -> str:
    """``wild_carrot`` -> ``Wild Carrot``; ``P.CrabFamiliar`` -> ``P. Crab Familiar``."""
    words = words or {}
    dotted = internal.replace('.', '. ')
    parts = [part for part in re.split(r'(?<=[a-z])(?=[A-Z])|[\s_]+', dotted) if part]
    out = []
    for part in parts:
        key = part.casefold()
        word = words.get(key, part[:1].upper() + part[1:])
        # Keep the second half of a hyphenated move capitalised: Hi-Freq Field.
        word = re.sub(r'-([a-z])', lambda match: '-' + match.group(1).upper(), word)
        out.append(word)
    return ' '.join(out).replace('.  ', '. ')


def fanxi_jugs() -> list[tuple[int, str]]:
    """(item id, display name) for every Call Beast jug in the Fanxi catalogue."""
    rows: list[tuple[int, str]] = []
    pattern = re.compile(
        r"VALUES \((\d+),'((?:[^']|'')*)',\d+,\d+,'[^']*',\d+,'Call Beast jug\.'")
    for line in MIGRATION.read_text(encoding='utf-8').splitlines():
        match = pattern.search(line)
        if match:
            rows.append((int(match.group(1)), match.group(2).replace("''", "'")))
    return rows


def build(source: Path) -> dict[int, dict]:
    item_weapon: dict[int, int] = {}
    for line in (source / 'sql' / 'item_weapon.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        if len(fields) >= 4:
            try:
                item_weapon[int(fields[0])] = int(fields[3])
            except ValueError:
                pass

    pet_list: dict[int, tuple[str, int, int]] = {}
    for line in (source / 'sql' / 'pet_list.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        if len(fields) >= 5:
            try:
                pet_list[int(fields[0])] = (fields[1], int(fields[2]), int(fields[3]))
            except ValueError:
                pass

    pool_skill: dict[int, int] = {}
    for line in (source / 'sql' / 'mob_pools.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        # poolid, name, packet_name, speciesid, modelid, mJob, sJob, cmbSkill,
        # cmbDelay, cmbDmgMult, behavior, aggro, true_detection, links, mobType,
        # immunity, name_prefix, flag, entityFlags, animationsub, hasSpellScript,
        # spellList, namevis, roamflag, skill_list_id, ...
        if len(fields) >= 28:
            try:
                pool_skill[int(fields[0])] = int(fields[24])
            except ValueError:
                pass

    lists: dict[int, list[int]] = {}
    for line in (source / 'sql' / 'mob_skill_lists.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        if len(fields) >= 3:
            try:
                lists.setdefault(int(fields[1]), []).append(int(fields[2]))
            except ValueError:
                pass

    pet_skills: dict[int, tuple[str, int]] = {}
    for line in (source / 'sql' / 'pet_skills.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        if len(fields) >= 4:
            try:
                pet_skills[int(fields[0])] = (fields[3], int(fields[1]))
            except ValueError:
                pass

    models: dict[int, int] = {}
    # modelid is a 20-byte look block: 00 00 <model lo> <model hi> ..., the same bytes
    # the host's ``pets._look`` writes from a model id.
    for line in (source / 'sql' / 'mob_pools.sql').read_text(
            encoding='utf-8', errors='replace').splitlines():
        fields = sql_values(line)
        if len(fields) >= 5 and fields[4].startswith('0x'):
            blob = bytes.fromhex(fields[4][2:])
            if len(blob) >= 4:
                try:
                    models[int(fields[0])] = blob[2] | blob[3] << 8
                except ValueError:
                    pass

    out: dict[int, dict] = {}
    for item_id, item_name in fanxi_jugs():
        pet_id = item_weapon.get(item_id)
        pet = pet_list.get(pet_id) if pet_id is not None else None
        if not pet:
            continue
        pet_name, pool, level = pet
        list_id = pool_skill.get(pool, 0)
        moves = []
        for skill_id in lists.get(list_id, []):
            move = pet_skills.get(skill_id)
            if not move:
                continue
            moves.append({
                'name': display_name(move[0], MOVE_WORDS),
                'id': skill_id,
                'mob_skill': move[1],
            })
        out[item_id] = {
            'item': item_name,
            'pet_id': pet_id,
            'pet': display_name(pet_name, PET_WORDS),
            'model': models.get(pool, 0),
            'level': level,
            'moves': moves,
        }
    return out


def lua_text(jugs: dict[int, dict]) -> str:
    def quote(text: str) -> str:
        return json.dumps(text, ensure_ascii=False)

    lines = [
        '-- Generated by tools/gen_jug_pets.py from LandSandBoat: Call Beast jug -> pet data.',
        '-- Do not edit by hand; run the generator again instead.',
        'return {',
    ]
    for item_id in sorted(jugs, key=lambda value: jugs[value]['item'].lower()):
        row = jugs[item_id]
        moves = ', '.join(quote(move['name']) for move in row['moves'])
        lines.append(
            '    [%d] = { item = %s, pet = %s, pet_id = %d, model = %d, level = %d, '
            'moves = { %s } },'
            % (item_id, quote(row['item']), quote(row['pet']), row['pet_id'],
               row['model'], row['level'], moves))
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def json_text(jugs: dict[int, dict]) -> str:
    document = {
        'source': 'LandSandBoat item_weapon/pet_list/mob_pools/mob_skill_lists/pet_skills',
        'jugs': {str(item_id): jugs[item_id] for item_id in sorted(jugs)},
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/tmp/lsb_full'),
                        help='LandSandBoat checkout (default /tmp/lsb_full)')
    parser.add_argument('--check', action='store_true',
                        help='exit 1 when the checked-in files differ from the source')
    args = parser.parse_args()
    if not (args.source / 'sql' / 'item_weapon.sql').is_file():
        raise SystemExit(f'{args.source}: not a LandSandBoat checkout')

    jugs = build(args.source)
    if not jugs:
        raise SystemExit('no Call Beast jugs matched: is migration 0070 intact?')
    outputs = {JSON_OUT: json_text(jugs), LUA_OUT: lua_text(jugs)}
    if args.check:
        stale = []
        for path, text in outputs.items():
            try:
                if path.read_text(encoding='utf-8') != text:
                    stale.append(str(path.relative_to(ROOT)))
            except OSError:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print('stale: ' + ', '.join(stale))
            return 1
        print(f'ok: {len(jugs)} jugs')
        return 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    print(f'wrote {len(jugs)} jugs to {JSON_OUT.relative_to(ROOT)} and '
          f'{LUA_OUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
