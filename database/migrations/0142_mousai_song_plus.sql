-- Mousai +1 family Song+ rows (migration 142).
--
-- The reforged/Mousai item importer did not carry the per-family Song+ lines on
-- the chest/legs/feet/head/hands pieces.  Without these rows the new
-- SongThrenody/SongMinne/SongMambo/SongCarol/SongEtude sets wear the correct
-- item but the server still computes only the +7 All Songs baseline.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (25989, 445, 2),   -- Mousai Gages +1: "Carol"+2
    (26538, 437, 2),   -- Mousai Manteel +1: "Threnody"+2
    (25902, 433, 2),   -- Mousai Seraweels +1: "Minne"+2
    (25969, 439, 2);   -- Mousai Crackows +1: "Mambo"+2
