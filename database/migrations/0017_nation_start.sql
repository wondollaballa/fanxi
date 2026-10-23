-- New characters start in their nation's original city, not Port Jeuno.
UPDATE zones SET pos_x = -8.0, pos_y = 1.0, pos_z = 1.0, rot = 0 WHERE id = 230;
INSERT OR REPLACE INTO zones (id, name, pos_x, pos_y, pos_z, rot)
VALUES (240, 'Port Windurst', 228.0, -3.0, 76.0, 160);
