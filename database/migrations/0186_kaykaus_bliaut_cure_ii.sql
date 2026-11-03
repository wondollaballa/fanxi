-- Kaykaus Bliaut +1: the client tooltip has "Cure" potency II +4%, while the item row
-- imported from LandSandBoat's older dump carries 6.  The set totals read the client
-- tooltip and the live sheet reads item_mods, so a four-piece Kaykaus set otherwise
-- showed 2% more Cure Potency II live than the set preview.  The client row is the one
-- the game draws; keep the server at 4 so the set bonus lands on the same base.
UPDATE item_mods SET value = 4 WHERE item_id = 25691 AND mod_id = 260;
