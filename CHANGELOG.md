# Changelog

## 0.2.0 — the world slice

LandSandBoat was studied read-only to understand real zone flow; Fanxi's implementation and all
content remain original. The license boundary is recorded in `docs/landsandboat-study.md`.

### World

- Added three Port Jeuno NPCs, a Moogle shop and the persistent **Pest Control** hunt quest.
- Added six West Ronfaure monsters with roaming, aggro, melee combat, death and respawn.
- Added EXP, gil, level-ups (max HP/MP growth and heal), starter inventory and quest rewards.
- Added `!entities` and `!heal`; `!zone 100` is the field camp and `!zone 246` is town.

### Protocol

- Added NPC/monster spawn, update and despawn packets (`0x00E`) and the player update (`0x00D`).
- Added bit-packed battle actions (`0x028`), battle messages (`0x029`) and end-of-combat
  messages (`0x02D`).
- Added inventory attributes, quantities, loaded markers and lists (`0x020`, `0x01D`, `0x01E`,
  `0x01F`) and the shop flow (`0x03E`, `0x03C`, `0x083`, `0x03F`).
- Added action handling for Talk, Attack, AttackOff, ChangeTarget and SendResRdy, plus entity
  requests (`0x016`/`0x017`).
- **Fixed the zone sub-message header**: size is a 7-bit count of 32-bit units packed with the
  9-bit type; it was previously written in the wrong field. This affects every zone packet.
- NPCs/monsters now spawn on the client's first `0x015` (or `SendResRdy`), not at `0x00C`.
- Static entity ids now follow `0x01000000 | (zone << 12) | targid`, with NPCs at `0x100+` and
  monsters at `0x200+`.
- Gil is item id `65535` in container 0 slot 0, as the client expects.

### Database

- Added `world_npcs`, `npc_lines`, `monster_templates`, `monster_spawns`, `items`, `char_inventory`, `quests`
  and `char_quests`.
- Added character `hp_current`, `mp_current`, `exp`, `gil`, home point, playtime and death count.
- Migrations `0002_world_content.sql` and `0003_world_content.sql`; existing characters are
  backfilled with the starter purse/pack.

### Docs and tests

- Added `docs/world.md` and `docs/landsandboat-study.md`.
- Updated protocol, server, database, architecture, development and README documentation.
- Added packet-layout, spawn, NPC, shop, combat, reward, respawn and quest tests; the server suite
  now covers the full first-`0x015` world flow without game files.

## 0.1.0 — first Fanxi release

- Ported the native FINAL FANTASY XI client (recompiler, runtime, host, addon host) and rebranded
  it around Fanxi: new name, icons, bundle IDs, paths, window titles and documentation.
- Removed the previous launcher/installer references, third-party presence integration and its
  application ID, old repository URLs and keys.
- Added `launcher/`: a dependency-free Python/Tkinter desktop launcher with sign-in, character
  creation, server status, news, game-folder detection, `host64` building and Play.
- Added `server/`: a standard-library HTTP API (accounts, sessions, characters, launch tokens,
  news, releases, admin) and a game gateway (TLS auth, login data, lobby, zone).
- Added `database/`: SQLite migrations and seed data for accounts, characters, zones, news and
  settings.
- Added tests for the server (including a live TLS auth/lobby/zone handshake) and launcher.
- Added packaging: macOS `.app`, Linux desktop entry, `install.sh`, `setup.command`, development
  scripts and CI.
