-- The airship agency's interior doors use the other four door ids from the zone's
-- DefaultActions.  They sit at the agency exit the player marked in-game; opening
-- one only plays the door animation.
INSERT OR REPLACE INTO world_npcs
    (id, zone, name, pos_x, pos_y, pos_z, rot, model, size, name_prefix, namevis,
     status, flags, speed, animation, triggerable, widescan, script, content_tag, door_id)
VALUES
    (35, 246, '_6u2', -77.0, 7.66, 38.69, 74, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 846542431),
    (36, 246, '_6u6', -77.0, 7.66, 38.69, 74, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 913651295),
    (37, 246, '_6uc', -77.0, 7.66, 38.69, 74, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 1668626015),
    (38, 246, '_6ug', -77.0, 7.66, 38.69, 74, 0, 2, 0, 0, 2, 0, 50, 9, 0, 0, 'door', 'port_jeuno', 1735734879);
