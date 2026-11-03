# Database

Fanxi uses SQLite. One file (`data/fanxi.db` by default) holds everything the server knows:
accounts, sessions, characters, zone positions, inventory, quest state, NPC/monster content,
news, releases and settings. There is no separate database server to install.

## Location and settings

| Variable | Default |
|---|---|
| `FANXI_DB` | `data/fanxi.db` (relative to the repository root) |

The server creates the parent folder, opens the database in WAL mode, enables foreign keys and
sets a busy timeout. `python3 -m fanxi_server init` runs migrations and seed; `run` does the same
on startup, so a fresh checkout only needs `init` once (or nothing at all).

## Migrations

`database/migrations/*.sql` are applied in numeric order and recorded in `schema_migrations`.
The server never edits an applied migration; add a new numbered file:

```
database/migrations/0004_add_mounts.sql
```

The runner splits the file into complete statements and runs it in a transaction. Use
`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` as appropriate; SQLite has no `DROP COLUMN` on old
versions, so rebuild tables if needed.

The current schema is migrations `0001_initial.sql`, `0002_world_content.sql` and
`0003_world_content.sql`:

| Table | Purpose | Key columns |
|---|---|---|
| `accounts` | Players and admins | `username` (unique, case-insensitive), `password_hash`, `status`, `role`, `failed_attempts`, `locked_until` |
| `api_sessions` | Launcher Bearer tokens | `token_hash` (unique SHA-256), `account_id`, `expires_at`, `revoked_at` |
| `game_sessions` | In-game sessions | `session_hash` (16-byte BLOB, unique), `account_id`, `character_id` (the launched mule), `expires_at` |
| `login_tokens` | Launcher → host64 hand-off | `token_hash` (unique), `character_id` (the chosen mule), `used_at`, `expires_at` |
| `characters` | Adventurers | `account_id`, `char_id` (content id), `name` (unique), stats, zone/position, looks, `hp_current`, `mp_current`, `exp`, `gil`, home point, playtime, `mount` (the last mount called, migration 0135; being mounted is live session state) |
| `worlds` | World name and advertised ports | `name`, `host`, ports, `status` |
| `zones` | Zone names and default positions/music | `id`, `name`, `pos_*`, `music_*` |
| `zone_lines` | Optional zone-line triggers | `rect`, `to_zone`, `x/y/z/rot` |
| `news` | Launcher news posts | `slug` (unique), `title`, `body`, `published_at` |
| `releases` | Launcher update metadata | `channel`, `platform`, `version`, `url`, `sha256` |
| `settings` | Small server settings | `key`, `value` (e.g. `server_name`, `motd`, `registration_open`, `world_id`) |
| `audit_log` | Account and admin events | `account_id`, `action`, `detail`, `ip`, `created_at` |
| `schema_migrations` | Applied migration files | `version`, `name`, `applied_at` |
| `world_npcs` | Placed city NPCs | `zone`, `name`, `script`, `pos_*`, `rot`, `model`, `triggerable`, `widescan` |
| `npc_lines` | Ambient lines | `npc_id`, `line_no`, `text` |
| `monster_templates` | Monster templates | `name`, `model`, `level_min/max`, `hp`, combat stats, `aggro`, `roam_radius`, `respawn_seconds`, `skill_list_id` (migration 148) |
| `mob_skills` | Monster TP moves imported from LandSandBoat | `id`, `name`, `animation`, `aoe`/`aoe_radius`, `distance`, `prepare_time`, `valid_targets`, `flag` (migration 148) |
| `mob_skill_lists` | The moves one monster family uses | `skill_list_id`, `mob_skill_id`, `skill_list_name` (migration 148) |
| `monster_spawns` | Monster placements | `template_id`, `zone`, `pos_*`, `rot`, `level`, `respawn_seconds` |
| `trusts` | Factual alter-ego data behind the 122 Trust spells (migrations 115 and 151) | `spell_id` (primary key), `name`, `job`/`sub_job`, `species` (LandSandBoat id; migration 151), `look_hex`, `model`, `delay`, `damage_mult`, `passive` |
| `trust_spells` | Spells each alter ego can cast, joined from its `mob_spell_lists` row (migration 117) | `trust_spell_id`, `spell_id`, `min_level`, `max_level` |
| `trust_gear` | The weapons a Trust is designed with (migration 159; Joachim's horn became the Prime Loughnashade in 167); their `item_mods` row produces the numbers the AI reads | `trust_spell_id`, `item_id` |
| `items` | Item catalogue | `item_id`, `name`, `stack`, `usable`, `equip_slot`, `level`, `item_level`, `rare`, `ex`, `price`, `base_sell`, `category` (empty for equipment; migration 0156 fills it for general items) |
| `char_purchases` | Armory and Items purchase history | `character_id`, `item_id`, `quantity`, `price`, `created_at` |
| `item_models` | Grap model per visible item (migration 95) | `item_id`, `model`; triggers on `items`/`char_inventory`/`char_equip` keep it applied |
| `char_inventory` | Character slots | `character_id`, `container`, `slot`, `item_id`, `quantity`; slot 0 / item 65535 is gil |
| `char_warps` | `//warp` saved places (migration 110) | `character_id`, `slot` 1-1000, `alias` (unique per character when non-empty), `zone`, `pos_*`, `rot` |
| `item_storage` | Storage Slip eligibility | `item_id`, `slip` (1–33) |
| `char_storage` | Items on a character's slips | `character_id`, `item_id`, `quantity`, `slip`, `stored_at` |
| `char_locker` | Hidden 9,999-slot locker | `character_id`, `item_id`, `extra`, `quantity`, `stored_at` |
| `char_live_state` | What a reconnect gets back (migration 0145) | `character_id` (primary key), `effects`, `food`, `recasts` (JSON), `updated_at` |
| `char_settings` | Per-character gameplay preferences (migration 0133) | `character_id`, `key` (`auto_open_doors`, `battle_profile`, `joachim_songs`, `trust_actions`, `trust_upgrade_level`), `value` |
| `gearswap_libraries` | Per-account GearSwap Lua, one row per job (migration 0177) | `account_id`, `job`, `name`, `source`, `updated_at`; the first read seeds from the template account or `gearswap/<JOB>.lua` |
| `quests` | Quest definitions | `quest_key`, `name`, reward, `required_template_id`, `required_kills` |
| `char_quests` | Quest progress | `character_id`, `quest_id`, `state` (`active`/`complete`), `progress` |

`items.rare` is retail's one-per-character flag. `FanxiService.add_item` and the shop refuse a
second copy, and the ownership check looks in the bags, the storage slips and the hidden locker.
`items.ex` means untradeable; on its own it does **not** limit copies for a normal grant (the
augmented job capes depend on owning several builds of the same Ex cape). The Armory and the
Items store are stricter about **Rare**: they refuse a second copy while the character holds one,
because it is a shop. Ex-only pieces can still be bought again; Ex stops trading and selling, not
holding two.

`item_aliases` (migrations 138 and 139) holds long spellings for the 2,068 client-abbreviated
equipment names, such as `Mousai Crackows +1` and `Marduk's Crackows +1`; the Armory search
matches either spelling without duplicating the item.
`items.price` is the Armory's deterministic gil price (migration 111): ten times the square of
the item level (or level), raised to ten times the NPC resale value when that is higher, and
doubled for Rare/Ex. Migration 111 also imports every equippable item the retail client names,
so the Armory typeahead covers the whole catalogue rather than the hand-curated rows earlier
migrations happened to need. Migration 113 fills the armour models LandSandBoat leaves at MId
0, so those pieces do not wear the previous slot's look. Migration 170 copies a weapon's
combat type from `item_weapon.skill` into `items.skill` when the GearSwap grant row kept the
placeholder 0; Armageddon, Annihilator, Gleti's Crossbow, Chrono Bullet, Daurdabla and
Loughnashade were the six rows, and a zero type made the equipped weapon's whole 0x0AC
weapon-skill block disappear.

Migration 0164 keeps the Prime weapon families on their final form. The sortie weapons have up
to five rows whose names repeat (the stage-1 `Prime ...` item, then four upgraded forms sharing
the final's name); the Armory maps every stage id to the iLvl 119 III item and the migration
retargets earlier-stage copies in the bags, storage, locker, equipped set and purchase history.
The weapons are Rare, so a family is one item: the migration keeps the equipped bag row, else an
existing final, else the highest stage, and drops the other copies. The id table lives in
`server/fanxi_server/game/prime_weapons.py` and mirrors migration 125's afterglow model list.

Migration 0156 adds `items.category` and imports the general-item store: ninja tools, Call Beast
jugs, pet food, consumables, ingredients, crafting materials, food, crystals, scrolls,
ammunition, furnishings and other non-equipment items. It is generated by
`tools/import_lsb_store_items.py` from LandSandBoat's `item_basic` / `item_usable` data and the
retail client names for the equipment-like rows (jugs, pet food and ammunition). The category is
the Items tab's shelf; equipment rows keep an empty category. General-item prices are
`10 × NPC resale`, or 1,000 gil when the item has no resale value (Reraizer, quest spell scrolls,
event food). Existing hand-curated rows keep their display name, equip slot, stack size and
usable bit, so the import cannot change how the server already handles those items.

Relationships:

```
accounts 1──n api_sessions
accounts 1──n game_sessions
accounts 1──n login_tokens
accounts 1──n characters
accounts 1──n audit_log
worlds   1──n (advertised by /status and /launch)
zones    ── characters.zone / zone_lines.to_zone
characters 1──n char_inventory
characters 1──n char_storage
characters 1──n char_locker
characters 1──n char_warps ── zones.id (zone)
characters 1──n char_quests ──n quests
characters 1──0..1 char_live_state
monster_templates 1──n monster_spawns
world_npcs 1──n npc_lines
quests   ── monster_templates (required_template_id)
```

Gil is deliberately stored in the same table as items: container `0`, slot `0`, item id
`65535`. The client expects that slot; the `characters.gil` column is a denormalized mirror used
by the HTTP API and reward code. Both are updated together. Containers `8` and `10`–`16` are the
Mog Wardrobes, and `1`, `5`, `6`, `7` and `9` are the other permanent bags; returned slip items
go into those containers (inventory first) and the client is kept in step with `0x020`/`0x01D`.

`item_storage` maps an item id to the one Storage Slip that accepts it (1–33). `char_storage` is
the slip's contents, keyed by character and item: storing deletes the `char_inventory` row and
inserts here, so the item is not in any client-visible bag. Grabbing reverses that. Migration
`0065_storage_slips.sql` seeds the item map; `0067_slip_storage.sql` moves anything left in the
old visible Storage/Locker containers into `char_storage`.

`char_locker` is the hidden general-purpose locker (`//locker`). It has no client container and no
slip column; `0069_generic_locker.sql` creates it, and `0116_all_capes_locker.sql` adds the
24-byte `extra` augment block and makes `(character_id, item_id, extra)` the primary key so the
198 same-id cape builds can coexist. The server enforces a 9999-quantity cap.

`char_live_state` is the one row a character has only while it is worth holding: the status
effects (the bard song list included), the food being eaten and the job-ability recasts. A
dropped link builds a new zone session, so the old one writes this row on the way out and the
next login reads it back; effect and recast times are absolute Unix timestamps, so time spent
offline counts. A deliberate `/logout` rewrites the row with the recasts only (retail takes the
buffs with the logout and keeps the cooldowns). The payload is small JSON from
`game/live_state.py`; the server never grows it beyond one row per character, and the foreign key
drops it with the character. See [world](world.md#recovering-a-dropped-client).

All times are ISO-8601 UTC strings (`2026-10-20T02:34:18.331Z`), written by the server. Sorting
the text sorts the times.

## Seed data

`database/seed.sql` is applied once, when `settings.seed_version` is absent:

- world `Fanxi` on `127.0.0.1` with the standard ports;
- eight zones with safe spawn positions (Port Jeuno by default);
- three Port Jeuno NPCs, six West Ronfaure monsters, items and the Pest Control quest
  (migration `0003_world_content.sql`, applied after the base seed);
- welcome news;
- settings: `server_name`, `motd`, `registration_open`, `world_id`, `schema_version`,
  `seed_version`.

It is idempotent (`INSERT OR IGNORE`) but is skipped after the first run so admin edits to news,
settings and zones survive restarts. To apply the seed again to an empty database, delete the
`seed_version` row first.

## Creating the first administrator

```bash
cd server
python3 -m fanxi_server create-admin
```

It prompts for a username and password (or takes `username password` arguments) and creates an
`accounts` row with `role = 'admin'`. There is **no default admin and no default password**. The
command also updates an existing account to admin if the username exists.

## Backup and restore

Safe online backup:

```bash
./scripts/db-backup.sh
# data/backups/fanxi-20261020-023418.db
```

Restore:

```bash
# stop the server first
cp data/backups/fanxi-20261020-023418.db data/fanxi.db
rm -f data/fanxi.db-wal data/fanxi.db-shm
./scripts/server.sh
```

Do not copy only `fanxi.db` while the server is running; the WAL file holds recent commits. Use
the backup script (SQLite's backup API) or stop the server first.

## Inspecting the data

```bash
sqlite3 data/fanxi.db
sqlite> .headers on
sqlite> .mode column
sqlite> select id, username, role, status, created_at from accounts;
sqlite> select id, name, account_id, zone, pos_x, pos_y, pos_z from characters;
sqlite> select * from settings;
sqlite> select * from audit_log order by id desc limit 20;
sqlite> select name, script, zone, pos_x, pos_y, pos_z from world_npcs;
sqlite> select p.name, s.zone, s.pos_x, s.pos_y, s.respawn_seconds from monster_spawns s join monster_templates p on p.id=s.template_id;
sqlite> select character_id, item_id, quantity from char_inventory where container=0 order by slot;
sqlite> select q.quest_key, cq.state, cq.progress from char_quests cq join quests q on q.id=cq.quest_id;
```

Useful queries:

```sql
-- who is online (sessions the gateway still considers live)
select count(*) from game_sessions where expires_at > strftime('%Y-%m-%dT%H:%M:%fZ','now');

-- characters by zone
select zone, count(*) from characters group by zone order by 2 desc;

-- recent sign-ins
select account_id, action, ip, created_at from audit_log
 where action in ('account.login','game.login','game.token_login')
 order by id desc limit 20;
```

## Retention

The server does not currently prune old rows. On a long-running world, schedule:

```sql
delete from api_sessions  where expires_at < datetime('now', '-7 days');
delete from game_sessions where expires_at < datetime('now', '-7 days');
delete from login_tokens  where expires_at < datetime('now', '-7 days');
delete from audit_log     where created_at < datetime('now', '-180 days');
```

Run these in a transaction during a quiet period. Keep audit history as long as your community
needs it.

Live NPC/monster positions, HP, aggro and respawn timers are not stored; they reset when the
server restarts. Character inventory, gil, EXP, level and quest progress are durable.

## Migrating to PostgreSQL

The schema is ordinary SQL with a few SQLite-isms (`AUTOINCREMENT`, `BLOB`, `strftime`). The
service layer (`server/fanxi_server/service.py`) is the only code that issues SQL; move the queries
to a connection pool and the game gateway to the same store, and the rest of Fanxi does not care.
For a friends-and-family server, SQLite's single-writer model is more than enough.

## Security notes

- `password_hash` is PBKDF2-HMAC-SHA256 with 260,000 iterations and a 16-byte salt, in the format
  `pbkdf2_sha256$iterations$salt$hash`.
- API and launch tokens are stored only as SHA-256 hashes.
- The database file contains no plaintext passwords or tokens. It does contain character data and
  IP addresses; protect the file (mode 0600, directory 0700) and backups.
- The database is never exposed on the network by Fanxi.
