-- /!warp: places a character saved with a number and an optional alias.
--
-- The in-game command marks the character's current zone and position in slot 1..1000.
-- The launcher's Warps page edits the alias and lists the same rows.  A blank alias is
-- allowed: the number is still a usable target, and the page shows the zone instead.
CREATE TABLE IF NOT EXISTS char_warps (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot         INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 1000),
    alias        TEXT    NOT NULL DEFAULT '',
    zone         INTEGER NOT NULL,
    x            REAL    NOT NULL,
    y            REAL    NOT NULL,
    z            REAL    NOT NULL,
    rot          INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    PRIMARY KEY (character_id, slot)
);

-- Alias lookup is case-insensitive and only applies to named warps.  The service checks
-- this before writing, so a duplicate is a 409 with a readable message instead of a bare
-- integrity error; the index keeps two racing marks from both winning.
CREATE UNIQUE INDEX IF NOT EXISTS char_warps_alias
    ON char_warps(character_id, lower(alias))
    WHERE alias <> '';
