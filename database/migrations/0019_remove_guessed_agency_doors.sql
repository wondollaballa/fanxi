-- Guessed door id/position pairs made the client's room geometry disappear and
-- still did not open the door.  Door ids cannot be guessed; remove them until the
-- real zone-246 door record (or DAT/capture) is available.
DELETE FROM world_npcs WHERE id BETWEEN 35 AND 38;
