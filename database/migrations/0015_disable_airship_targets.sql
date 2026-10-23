-- The airship deck has no usable server spawn at (0,0,0); entering it loops the
-- login.  Keep Port Jeuno recoverable until the transport spawn is authored.
DELETE FROM world_npcs WHERE id BETWEEN 26 AND 29;
DELETE FROM zones WHERE id BETWEEN 223 AND 226;
