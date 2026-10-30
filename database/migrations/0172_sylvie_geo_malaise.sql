-- Sylvie (UC) carries the Idris, so her hexes use the Geomancy +10 column.  Her imported
-- spell list only has the Indi- line (the aura centred on the caster); Geo-malaise is the
-- enemy-targeted form of the same Magic Defense Down hex (status 559) and is what the owner
-- can choose from the Trust HUD's Set spells dialog.  Level 88 is the Geomancer's Geo-
-- Malaise level; above it the row is always available to a level-99 Master.
INSERT OR REPLACE INTO trust_spells (trust_spell_id, spell_id, min_level, max_level) VALUES
    (981, 820, 88, 255);    -- Geo-malaise
