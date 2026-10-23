-- Test placement: use a standard visible character model instead of the invisible
-- trigger model, and move the three tutorial NPCs out of the dock wall into open space.
UPDATE world_npcs SET model = 1, pos_x = -98.0, pos_y = 12.0, pos_z = 108.0 WHERE id = 1;
UPDATE world_npcs SET model = 1, pos_x = -96.0, pos_y = 12.0, pos_z = 106.0 WHERE id = 2;
UPDATE world_npcs SET model = 1, pos_x = -94.0, pos_y = 12.0, pos_z = 104.0 WHERE id = 3;
