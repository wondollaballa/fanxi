-- The real airship doors need the client's door DAT ids, which are not in the
-- server data.  Stand a named, targetable door attendant at each original door
-- position and make the airship itself a real zone (the client's own arrival
-- position is 0,0,0 on the deck).
INSERT OR REPLACE INTO zones (id, name, pos_x, pos_y, pos_z, rot)
VALUES
    (223, 'San d''Oria-Jeuno Airship', 0, 0, 0, 0),
    (224, 'Windurst-Jeuno Airship',   0, 0, 0, 0),
    (225, 'Bastok-Jeuno Airship',     0, 0, 0, 0),
    (226, 'Kazham-Jeuno Airship',     0, 0, 0, 0);

UPDATE world_npcs SET model = 1, size = 0, door_id = 0,
    name = 'Airship Door: San d''Oria', script = 'airship_san' WHERE id = 22;
UPDATE world_npcs SET model = 1, size = 0, door_id = 0,
    name = 'Airship Door: Kazham', script = 'airship_kaz' WHERE id = 23;
UPDATE world_npcs SET model = 1, size = 0, door_id = 0,
    name = 'Airship Door: Bastok', script = 'airship_bas' WHERE id = 24;
UPDATE world_npcs SET model = 1, size = 0, door_id = 0,
    name = 'Airship Door: Windurst', script = 'airship_win' WHERE id = 25;
