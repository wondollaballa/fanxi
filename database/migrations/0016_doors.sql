-- Real door entities: size 2 plus the four-byte client door id.  Talking to one
-- sends the open_door animation update (8) and closes it again after seven
-- seconds; it never zones.
INSERT OR REPLACE INTO world_npcs
    (id, zone, name, pos_x, pos_y, pos_z, rot, model, size, name_prefix, namevis,
     status, flags, speed, animation, triggerable, widescan, script, content_tag, door_id)
VALUES
    (31, 246, '_6u4', -76.0, 8.0,  54.0, 128, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 880096863),
    (32, 246, '_6u8', -12.0, 8.0,  54.0, 128, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 947205727),
    (33, 246, '_6ua', -61.0, 7.0, -54.0, 128, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 1635071583),
    (34, 246, '_6ue',   3.0, 7.0, -54.0, 128, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 1702180447);
