-- A blank, clickable target on the real Lower Jeuno exit.  The client's static
-- door meshes have no server target of their own; this gives the exit a target
-- that opens it without sending an invalid door model (which made the client spin).
INSERT OR REPLACE INTO world_npcs
    (id, zone, name, pos_x, pos_y, pos_z, rot, model, size, name_prefix, namevis,
     status, flags, speed, animation, triggerable, widescan, script, content_tag, door_id)
VALUES
    (30, 246, ' ', -150.994, -6.324, -22.820, 128, 50, 0, 0, 0, 0, 0, 50, 0, 1, 0, 'zone_lower', 'port_jeuno', 0);
