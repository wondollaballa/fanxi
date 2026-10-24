-- Character data page (migration 105).
--
-- The launcher's Data page assigns values that the server otherwise only ever derives:
-- the Mastery Rank byte in 0x01B, an arbitrary currency ledger and the Armory's purchase
-- history.  Mastery Rank is a character field, not a job field: retail shows it in
-- Status -> Profile and recomputes it when the character zones.

ALTER TABLE characters ADD COLUMN mastery_rank INTEGER NOT NULL DEFAULT 0;

-- Named currency balances.  Gil, merits and limit points keep their own columns; this
-- table is for the currencies Fanxi has no column for (sparks, accolades, segments, ...)
-- and for any custom name the Data page accepts.
CREATE TABLE IF NOT EXISTS char_currency (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    name         TEXT    NOT NULL,
    amount       INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT    NOT NULL,
    PRIMARY KEY (character_id, name)
);

-- What the Armory handed out, newest first.  The item name is joined from `items` at read
-- time; the row keeps the item id even if the catalogue is later rebuilt.
CREATE TABLE IF NOT EXISTS char_purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id      INTEGER NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS char_purchases_character ON char_purchases(character_id, id DESC);
