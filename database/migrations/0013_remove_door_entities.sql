-- Door entities with invalid DAT door ids made the client spin after zone-in.
-- Keep the original NPCs and the real zone lines; door entities stay out until
-- their client DAT ids are extracted.
DELETE FROM world_npcs WHERE id BETWEEN 22 AND 25;
