# database/

- `migrations/0001_initial.sql` — the schema. Applied in order, recorded in `schema_migrations`.
- `seed.sql` — the default world, zones, welcome news and settings. Applied once.

The server creates and upgrades `data/fanxi.db` automatically; you should not need to run SQL by
hand. See [docs/database.md](../docs/database.md) for the table guide, backups and queries.

Quick look:

```bash
sqlite3 ../data/fanxi.db '.tables'
sqlite3 ../data/fanxi.db 'select id, username, role, status from accounts;'
```
