-- Multibox and mules: a launch can name the character it is for, so a client with several
-- characters on its account opens the one the launcher chose, and the game session remembers
-- that choice while the character is online.
ALTER TABLE login_tokens ADD COLUMN character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL;
ALTER TABLE game_sessions ADD COLUMN character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS game_sessions_character ON game_sessions(character_id);
