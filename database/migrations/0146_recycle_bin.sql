-- The client's Recycle Bin (container 17) holds thrown-away items for 30 days.
-- `dropped_at` is only meaningful for that container; every other bag leaves it NULL.
-- The server sets it when 0x028 moves a stack here, clears it when the item is restored,
-- and purges rows older than RECYCLE_DAYS on login.
ALTER TABLE char_inventory ADD COLUMN dropped_at TEXT;
CREATE INDEX IF NOT EXISTS char_inventory_dropped
    ON char_inventory(character_id, container, dropped_at);
