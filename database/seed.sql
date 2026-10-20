-- Fanxi starter data: one world, the zones the built-in server can place a character in,
-- the welcome news post and the settings an empty server needs.

INSERT OR IGNORE INTO worlds (id, name, host, auth_port, data_port, view_port, zone_port, search_port, status, created_at)
VALUES (1, 'Fanxi', '127.0.0.1', 54231, 54230, 54001, 54230, 54002, 'online',
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

INSERT OR IGNORE INTO zones (id, name, pos_x, pos_y, pos_z, rot) VALUES
    (50,  'Aht Urhgan Whitegate', -11.0,   2.0, -142.0, 192),
    (100, 'West Ronfaure',       -126.0, -62.0,  273.0,  99),
    (230, 'Southern San d''Oria',  0.0,   0.0,    0.0,   0),
    (231, 'Northern San d''Oria',  0.0,   0.0,  -13.0, 192),
    (232, 'Port San d''Oria',     -1.0,   0.0,   44.0, 128),
    (236, 'Port Bastok',         -36.0,   7.0,  -58.0, 194),
    (246, 'Port Jeuno',          -87.0,  12.0,  116.0, 128),
    (248, 'Ru''Lude Gardens',      0.0,   0.0,    0.0,   0);

INSERT OR IGNORE INTO settings (key, value) VALUES
    ('server_name', 'Fanxi'),
    ('motd', 'Welcome to Fanxi. Say !help in the zone for commands.'),
    ('registration_open', '1'),
    ('world_id', '1'),
    ('schema_version', '2'),
    ('seed_version', '1');

INSERT OR IGNORE INTO news (slug, title, body, published_at, created_at)
VALUES ('welcome-to-fanxi',
        'Welcome to Fanxi',
        'Fanxi is a self-hosted home for FINAL FANTASY XI. ' ||
        'Create an account in the launcher, make a character, and press Play. ' ||
        'The bundled world server signs you in, holds your character and its position, and ' ||
        'serves the zones listed in the database. It is a development world: no NPCs or monsters yet.',
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
