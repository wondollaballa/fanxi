-- A general-purpose, server-side locker for everything the Storage Slips do not
-- accept: JSE capes, ammo, crafting materials and the rest.  It is not a client
-- container (the client's bag capacity is one byte and tops out at 80 slots), so the
-- items leave char_inventory entirely and are returned with !locker grab.
CREATE TABLE IF NOT EXISTS char_locker (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id      INTEGER NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    stored_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, item_id)
);
