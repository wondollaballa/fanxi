-- Merit points and the upgrades a character has bought.  The client's merit menu is
-- driven by 0x08C (one entry per merit that has points in it) and 0x063 type 2 (the
-- point totals); the menu itself and the costs come from the client's DAT.
ALTER TABLE characters ADD COLUMN merit_points INTEGER NOT NULL DEFAULT 127;
ALTER TABLE characters ADD COLUMN limit_points INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN merit_mode INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS char_merits (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    merit_id     INTEGER NOT NULL,
    upgrades     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, merit_id)
);
