-- Home Points a character has registered.  The client's menu is built from these bits
-- (four 32-bit words, index % 32 / index / 32) and the "new home point" flag is only
-- shown the first time an index is added.
CREATE TABLE IF NOT EXISTS char_home_points (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    hp_index     INTEGER NOT NULL,
    registered_at TEXT NOT NULL,
    PRIMARY KEY (character_id, hp_index)
);
