-- Door behaviour: retail doors are opened by the player unless the optional automatic
-- door mode is on, and that mode never runs in a dungeon.  Port Bastok's drawbridge is
-- not a door the player opens at all; the server times it from the airship schedule.
--
-- The zone list is LandSandBoat's zone type flags (data/zones/<zone>/zone.yaml): city and
-- outdoors only.  A zone missing from the list keeps automatic doors off.
ALTER TABLE zones ADD COLUMN auto_open_doors INTEGER NOT NULL DEFAULT 0;
UPDATE zones SET auto_open_doors = 1 WHERE id IN (
    2, 4, 5, 7, 24, 25, 26, 32, 33, 48, 50, 51, 52, 53, 54, 61, 79,
    80, 81, 82, 83, 84, 85, 87, 88, 89, 90, 91, 94, 95, 97, 98,
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115,
    116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 130,
    136, 137,
    230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 243, 244, 245, 246,
    247, 248, 249, 250, 251, 252,
    256, 257, 260, 261, 262, 263, 265, 266, 267
);

-- "Door:House", shop doors, gates and the Hanging Bridge are ordinary doors.  A
-- drawbridge is a moving structure, not a door: `_6ke` is the span and `_6ks`/`_6kt`
-- are the two gate ends (LandSandBoat scripts/zones/Port_Bastok/npcs/_6kt.lua).  The
-- span and gates spawn lowered (animation 8, OPEN_DOOR); the world raises them for the
-- two ship crossings in every six-minute cycle.
ALTER TABLE world_npcs ADD COLUMN door_kind TEXT NOT NULL DEFAULT '';
UPDATE world_npcs SET door_kind = 'drawbridge', animation = 8
 WHERE zone = 236 AND name IN ('_6ke', '_6ks', '_6kt');

-- Per-character gameplay preferences.  The automatic door mode is opt-in and follows
-- the character, so one box asking for it does not change another player's world.
CREATE TABLE IF NOT EXISTS char_settings (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    key          TEXT    NOT NULL,
    value        TEXT    NOT NULL,
    PRIMARY KEY (character_id, key)
);
