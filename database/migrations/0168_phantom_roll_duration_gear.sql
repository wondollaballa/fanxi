-- Phantom Roll duration on the gear that carries it.
--
-- The item rows were imported without the "Phantom Roll" effect duration line on the
-- final stages, so a Corsair wearing Chasseur's Gants +3, Camulus's Mantle, Lanun Knife
-- or Rostam got no extra seconds at all.  BG-wiki's item pages give:
--   Chasseur's Gants +3  +60 s   (the +0/+1/+2 rows already have 45/50/55)
--   Camulus's Mantle     +30 s   (base line; its augment is separate)
--   Lanun Knife          +45 s
--   Rostam               +60 s
-- Modifier 882 is LandSandBoat's PHANTOM_DURATION; rolls.duration_for() sums it with
-- the 5:00 base, the Phantom Roll Duration job points and Winning Streak merits.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (23570, 882, 60),   -- Chasseur's Gants +3
    (26262, 882, 30),   -- Camulus's Mantle
    (21580, 882, 45),   -- Lanun Knife
    (21581, 882, 60);   -- Rostam

-- Chasseur's Tricorne +3 and Lanun Tricorne +4 extend Winning Streak by 6 s per merit
-- instead of carrying a flat duration row.  The server does not name that modifier yet,
-- so leave the tricorne's existing rows alone; the merit itself is counted by
-- rolls.duration_for().
