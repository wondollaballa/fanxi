-- Naegling and Kaja Sword grant "Savage Blade" damage +15% (migration 143).
--
-- LandSandBoat stores a weapon skill's own damage bonus in the 570 + id block; the
-- Savage Blade id is 42, so the modifier is 612.  The two swords' item rows did not
-- carry it, which cost every Savage Blade 15% of its damage on all hits.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (21620, 612, 15),   -- Kaja Sword
    (21621, 612, 15);   -- Naegling
