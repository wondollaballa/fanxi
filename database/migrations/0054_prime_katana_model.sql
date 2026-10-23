-- Prime katana: Dokoku's item data carries Kikoku's model (551), so it drew the relic
-- katana.  Confirmed in game: 914 is the Prime katana.
--
-- This supersedes the note in 0051 that gave 914 to Earp; the gun's id needs rechecking
-- against the client, since the block aliases freely (903/906/907/908 all drew one asset).
UPDATE items SET model = 914 WHERE item_id BETWEEN 21929 AND 21932;  -- Dokoku (katana)
