-- Put the three tutorial NPCs back at their intended Port Jeuno spots, spaced apart.
UPDATE world_npcs SET model = 1,  pos_x = -87.0, pos_y = 12.0, pos_z = 109.0 WHERE id = 1;
UPDATE world_npcs SET model = 82, pos_x = -93.0, pos_y = 12.0, pos_z = 110.0 WHERE id = 2;
UPDATE world_npcs SET model = 1,  pos_x = -96.0, pos_y = 12.0, pos_z = 122.0 WHERE id = 3;
