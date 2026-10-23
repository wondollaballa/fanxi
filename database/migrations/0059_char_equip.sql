-- The gear a character was wearing, so it survives a relog instead of being re-picked.
CREATE TABLE IF NOT EXISTS char_equip (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    kind         INTEGER NOT NULL,
    container    INTEGER NOT NULL,
    slot         INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    PRIMARY KEY (character_id, kind)
);
