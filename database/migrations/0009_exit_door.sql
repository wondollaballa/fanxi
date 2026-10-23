-- A working transition out of Port Jeuno, until the real door/zone-line content is authored.
INSERT OR REPLACE INTO world_npcs
    (id, zone, name, pos_x, pos_y, pos_z, rot, model, size, name_prefix, namevis,
     status, flags, speed, animation, triggerable, widescan, script, content_tag)
VALUES
    (4, 246, 'Door to West Ronfaure', -84.0, 12.0, 105.0, 128, 1, 0, 0, 0,
     0, 0, 50, 0, 1, 1, 'exit_west', 'tutorial');
