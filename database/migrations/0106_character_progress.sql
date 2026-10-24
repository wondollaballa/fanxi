-- Character progress page (migration 106): mission rank, Mog Garden rank, fame,
-- Exemplar Points and the crafting/fishing skills.
--
-- Retail keeps all of these on the character, but Fanxi only ever sent the defaults:
-- 0x061 carried Rank 1 with no rank points and zeroed mastery EXP, and 0x062 sent the
-- twelve crafting slots as zeroes.  These columns give the launcher's Data page values
-- to write, and the zone packets read them back.

ALTER TABLE characters ADD COLUMN rank_sandoria   INTEGER NOT NULL DEFAULT 1;
ALTER TABLE characters ADD COLUMN rank_bastok     INTEGER NOT NULL DEFAULT 1;
ALTER TABLE characters ADD COLUMN rank_windurst   INTEGER NOT NULL DEFAULT 1;
ALTER TABLE characters ADD COLUMN rank_points     INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN mog_garden_rank INTEGER NOT NULL DEFAULT 0;
ALTER TABLE characters ADD COLUMN exemplar_points INTEGER NOT NULL DEFAULT 0;

-- Fame per city.  The client never draws a fame page; NPC dialogue and shop gates read
-- it, so the value lives on the server and the Data page can raise it.
CREATE TABLE IF NOT EXISTS char_fame (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    city         TEXT    NOT NULL,
    value        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, city)
);

-- Crafting/fishing skills, keyed by the client's skill id (48-59 in 0x062).
CREATE TABLE IF NOT EXISTS char_craft (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    skill_id     INTEGER NOT NULL,
    value        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, skill_id)
);
