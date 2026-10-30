#!/usr/bin/env python3
"""Check the Battle hub's Dancer waltz tables against the server's definitions.

The client-side healing fallback has its own copy of the waltz TP costs and the list of
statuses Healing Waltz can cleanse.  Those two tables must stay in step with
``server/fanxi_server/game/dancer.py``; a server-side change without the client copy would
silently waste TP or refuse a status that the server would have cured.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATTLE = ROOT / 'host' / 'addons' / 'lua' / 'battle.lua'
sys.path.insert(0, str(ROOT / 'server'))

from fanxi_server.game import dancer  # noqa: E402


def table_block(source: str, name: str) -> str:
    match = re.search(rf'local {name} = \{{(.*?)\n\}}', source, re.S)
    if not match:
        raise SystemExit(f'{BATTLE}: missing local {name} table')
    return match.group(1)


def main() -> int:
    source = BATTLE.read_text(encoding='utf-8')

    client_statuses = {
        int(value) for value in re.findall(r'\[(\d+)\]\s*=\s*true', table_block(source, 'WALTZABLE'))
    }
    server_statuses = {int(value) for value in dancer.WALTZABLE_EFFECTS}
    if client_statuses != server_statuses:
        missing = sorted(server_statuses - client_statuses)
        extra = sorted(client_statuses - server_statuses)
        raise SystemExit(
            'WALTZABLE differs from server/fanxi_server/game/dancer.py: '
            f'missing {missing}, extra {extra}'
        )

    client_tiers = {
        name: int(cost)
        for name, cost in re.findall(
            r"\{ name = '([^']+)', cost = (\d+), recast = \d+ \}", table_block(source, 'WALTZ_TIERS')
        )
    }
    server_tiers = {
        name: int(spec.tp_cost)
        for name, spec in (
            (spec.name, spec) for spec in dancer.WALTZES.values() if not spec.cleanse
        )
        if name.startswith('Curing Waltz')
    }
    if client_tiers != server_tiers:
        raise SystemExit(f'Curing Waltz tiers differ: client {client_tiers}, server {server_tiers}')

    healing = re.search(
        r"local WALTZ_HEALING = \{ name = '([^']+)', cost = (\d+), recast = \d+ \}", source
    )
    healing_spec = next(spec for spec in dancer.WALTZES.values() if spec.cleanse)
    if not healing or healing.group(1) != healing_spec.name or int(healing.group(2)) != int(healing_spec.tp_cost):
        raise SystemExit(
            f"Healing Waltz differs: client {healing and healing.groups()}, "
            f'server {healing_spec.name}/{healing_spec.tp_cost}'
        )

    print(
        f'OK: {len(client_tiers)} Curing Waltz tiers, Healing Waltz, '
        f'{len(client_statuses)} waltzable statuses'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
