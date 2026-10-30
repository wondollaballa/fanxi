-- Mounts.  A mount is client-side art with a server-side id: the client's own
-- mounts.names table (tools/client_mount_names.tsv) is the catalogue, and the id is what
-- 0x0AE unlocks, 0x037 puts on the local player and 0x00D puts on everyone else.
--
-- Only the last mount a character called is stored, so the Mount HUD and the launcher can
-- preselect it.  Being mounted is live state (the zone session's mount_id): a zone line or
-- a relog puts the character back on foot, the way retail does.
ALTER TABLE characters ADD COLUMN mount INTEGER NOT NULL DEFAULT -1;
