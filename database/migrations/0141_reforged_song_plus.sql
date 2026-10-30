-- Reforged +3/+4 family Song+ stats (migration 141).
--
-- The reforged item importer also dropped the per-family Song+ lines
-- ("Madrigal"+1, "Minuet"+1, "March"+1, ...), so the BiS song pieces added All
-- Songs but none of their family bonuses.  Fili Manchettes +3's "March"+1 is the
-- one that matters for haste: it adds 1% magic haste to every March.
--
-- The generator now parses all nineteen family names; a future regeneration of
-- 0092 carries these rows too.  This migration backfills existing databases.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (23429, 438, 1),   -- Fili Calot +3: "Madrigal"+1
    (23496, 434, 1),   -- Fili Hongreline +3: "Minuet"+1
    (23563, 443, 1),   -- Fili Manchettes +3: "March"+1
    (23630, 442, 1),   -- Fili Rhingrave +3: "Ballad"+1
    (23697, 451, 1),   -- Fili Cothurnes +3: "Scherzo"+1
    (23904, 435, 2),   -- Brioso Roundlet +4: "Paeon"+2
    (23994, 440, 2);   -- Brioso Cuffs +4: "Lullaby"+2
