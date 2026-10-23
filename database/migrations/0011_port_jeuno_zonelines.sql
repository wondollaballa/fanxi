-- Real Port Jeuno zone lines from LandSandBoat's data/zones/port_jeuno/zone.yaml.
-- The client's 0x05E rect is the four-byte door name (e.g. '_6u2'), the same id the
-- zone uses for the door entity.
INSERT OR REPLACE INTO zones (id, name, pos_x, pos_y, pos_z, rot)
VALUES
    (120, 'Sauromugue Champaign', -574.647, -0.680, 399.974, 0),
    (126, 'Qufim Island',          139.997,  8.903, -476.956, 192),
    (245, 'Lower Jeuno',            27.891, -2.635,   42.423, 149);

INSERT OR REPLACE INTO zone_lines (id, rect, to_zone, x, y, z, rot)
VALUES
    (1, 812987999, 120, -574.647, -0.680, 399.974, 0),   -- _6u0 -> Sauromugue
    (2, 846542431, 245,   27.891, -2.635,  42.423, 149), -- _6u2 -> Lower Jeuno
    (3, 880096863, 126,  139.997,  8.903, -476.956, 192),-- _6u4 -> Qufim Island
    (4, 1936878943, 246, -195.028, -6.095,   0.008, 0);   -- _mrs -> Port Jeuno (Mog House)
