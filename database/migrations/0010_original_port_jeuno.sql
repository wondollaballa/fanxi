-- Replace Fanxi's invented Port Jeuno NPCs with the original zone NPCs, using the
-- positions recorded in the reference zone scripts.  The four departure doors are
-- spawned as real door entities (size 2, door id = the client's four-byte door name).
ALTER TABLE world_npcs ADD COLUMN door_id INTEGER NOT NULL DEFAULT 0;
ALTER TABLE world_npcs ADD COLUMN targid INTEGER DEFAULT 0;

DELETE FROM world_npcs WHERE zone = 246;

INSERT INTO world_npcs
    (id, zone, name, pos_x, pos_y, pos_z, rot, model, size, name_prefix, namevis,
     status, flags, speed, animation, triggerable, widescan, script, content_tag, door_id)
VALUES
    (1, 246, 'Guddal',              -14.0,   8.0,   44.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (2, 246, 'Zuah Lepahnyu',         0.0,   0.0,    8.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (3, 246, 'Shami',               -53.9,   0.0,   10.8, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (4, 246, 'Narsha',               -2.51,  8.0,   -1.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (5, 246, 'Horst',               -54.379, 0.001,-10.061,128,1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (6, 246, 'Illauvolahaut',       -12.0,   8.0,   54.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (7, 246, 'Pyropox',             -17.58,  4.0,   24.6, 128, 82,0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (8, 246, 'Squintrox Dryeyes',  -100.071, -1.0,  11.869,128,1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (9, 246, 'Sagheera',             -3.0,   0.1,   -9.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (10,246, 'Garridan',             19.59,  0.0,   -9.9, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (11,246, 'Caffie',               -2.51,  8.0,   -1.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (12,246, 'Gavin',               -15.0,   8.0,   44.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (13,246, 'Kindlix',             -18.82,  4.0,   23.302,128,82,0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (14,246, 'Omiro-Zamiro',          3.0,   7.0,  -54.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (15,246, 'Purequane',           -76.0,   8.0,   54.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (16,246, 'Zona Shodhun',       -175.0,  -5.0,   -4.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (17,246, 'Zedduva',             -61.0,   7.0,  -54.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (18,246, 'Digaga',              -52.865, 7.999, 1.134,128,1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (19,246, 'Veujaie',             -20.349, 7.999,-2.888,128,1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (20,246, 'Joachim',             -52.844, 0.0,   -9.978,128,1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (21,246, 'Kochahy-Muwachahy',    40.0,   0.0,    6.0, 128, 1, 0, 0, 0, 0, 0, 50, 0, 1, 1, '', 'port_jeuno', 0),
    (22,246, '_6u4',                -76.0,   8.0,   54.0, 128, 0, 2, 0, 0, 2, 0, 50, 0, 1, 0, 'airship_door', 'port_jeuno', 0x3475365F),
    (23,246, '_6u8',                -12.0,   8.0,   54.0, 128, 0, 2, 0, 0, 2, 0, 50, 0, 1, 0, 'airship_door', 'port_jeuno', 0x3875365F),
    (24,246, '_6ua',                -61.0,   7.0,  -54.0, 128, 0, 2, 0, 0, 2, 0, 50, 0, 1, 0, 'airship_door', 'port_jeuno', 0x6175365F),
    (25,246, '_6ue',                  3.0,   7.0,  -54.0, 128, 0, 2, 0, 0, 2, 0, 50, 0, 1, 0, 'airship_door', 'port_jeuno', 0x6575365F);
