-- Register every Home Point for Onedough.
--
-- The client's teleport menu is built from a 128-bit access mask (4 x 32-bit words in the
-- Home Point event params), one bit per entry of its own Home Point table.  home_point_index
-- holds that table: idx 0..121, matching the hp_index the zone crystals carry, so a bit per
-- row is the whole network.
INSERT OR IGNORE INTO char_home_points (character_id, hp_index, registered_at)
SELECT 1, idx, strftime('%Y-%m-%dT%H:%M:%fZ', 'now') FROM home_point_index
WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);
