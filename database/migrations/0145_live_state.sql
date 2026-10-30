-- The character state that outlives a zone session: status effects (the bard song list
-- and every other buff), the food being eaten, and the job-ability recasts.
--
-- Retail keeps all three on the server.  A dropped link is a relog to the client, and the
-- same song list comes back ticking with the same abilities still on cooldown; only a
-- deliberate /logout takes the buffs with it (the cooldowns survive that too).  Fanxi
-- builds a fresh ZoneSession for every fresh login, so the session writes this row while
-- it is in the world (coalesced) and on the way out, and the next login reads it back.
--
-- One row per character, overwritten in place: the snapshot is a small JSON document and
-- every time in it is an absolute Unix timestamp, so time spent offline counts against an
-- effect instead of pausing it.  The server prunes whatever expired before the login.
CREATE TABLE IF NOT EXISTS char_live_state (
    character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    effects      TEXT    NOT NULL DEFAULT '[]',
    food         TEXT    NOT NULL DEFAULT '{}',
    recasts      TEXT    NOT NULL DEFAULT '{}',
    updated_at   TEXT    NOT NULL
);
