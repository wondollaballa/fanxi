-- Totemic Helm +4 (23903): the "Tame" success rate +31 line was missing from item_mods.
-- The +2/+3 rows already carry mod 304 (25/27/29/31); the +4 row had every other stat but
-- this one, so a Beastmaster's best helm gave no Tame success.  Mod 304 is the Tame success
-- percentage read by ZoneSession._tame.
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES (23903, 304, 31);
