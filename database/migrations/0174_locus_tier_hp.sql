-- Locus tier: retail level ranges, per-level HP, Defense and Evasion.
--
-- LSB's spawn import gave every placed mob a fixed level (the low end of its range)
-- and a single template HP.  The Japanese Apex/Locus camp tables and BG-wiki's Locus
-- pages publish the actual level -> HP/Defense/Evasion rows; this migration stores them
-- verbatim in monster_templates.level_stats (JSON keyed by level).  entities.mob_from_row
-- reads the row for the rolled level, and World.monster_sheet() uses the Defense/Evasion
-- override instead of the 99-capped GetBaseDefEva curve.
--
-- Three templates also had no HP in the LSB source and fell back to level*20
-- (2,680-2,740), so they died to one weapon skill.  Their retail rows are included here.
--
-- Spawns get level = NULL so the same row rolls its retail level range on every pop and
-- respawn.  Locus with no published table (Crawler's Nest camp) keep the level-based
-- build_monster Defense/Evasion and their flat HP.

ALTER TABLE monster_templates ADD COLUMN hp_min INTEGER NOT NULL DEFAULT 0;
ALTER TABLE monster_templates ADD COLUMN level_stats TEXT NOT NULL DEFAULT '';

UPDATE monster_templates SET level_max = 136 WHERE name = 'Locus Colibri';

UPDATE monster_templates SET hp_min = 289900, hp = 308300, level_stats = '{"135":{"hp":289900,"defense":1346,"evasion":1224},"136":{"hp":299100,"defense":1379,"evasion":1254},"137":{"hp":308300,"defense":1413,"evasion":1284}}' WHERE name = 'Locus Bight Rarab';
UPDATE monster_templates SET hp_min = 289900, hp = 308300, level_stats = '{"135":{"hp":289900,"defense":1346,"evasion":1224},"136":{"hp":299100,"defense":1379,"evasion":1254},"137":{"hp":308300,"defense":1413,"evasion":1284}}' WHERE name = 'Locus Camelopard';
UPDATE monster_templates SET hp_min = 289900, hp = 308300, level_stats = '{"135":{"hp":289900,"defense":1346,"evasion":1224},"136":{"hp":299100,"defense":1379,"evasion":1254},"137":{"hp":308300,"defense":1413,"evasion":1284}}' WHERE name = 'Locus Hypnos Eft';
UPDATE monster_templates SET hp_min = 309100, hp = 327500, level_stats = '{"137":{"hp":309100,"defense":1413,"evasion":1310},"138":{"hp":318300,"defense":1446,"evasion":1341},"139":{"hp":327500,"defense":1479,"evasion":1372}}' WHERE name = 'Locus Fiddler Crab';
UPDATE monster_templates SET hp_min = 309100, hp = 327500, level_stats = '{"137":{"hp":309100,"defense":1413,"evasion":1310},"138":{"hp":318300,"defense":1446,"evasion":1341},"139":{"hp":327500,"defense":1479,"evasion":1372}}' WHERE name = 'Locus Ghost Crab';
UPDATE monster_templates SET hp_min = 214600, hp = 229600, level_stats = '{"133":{"hp":214600,"defense":1226,"evasion":1172},"134":{"hp":219000,"defense":1260,"evasion":1200},"135":{"hp":224000,"defense":1280,"evasion":1210},"136":{"hp":229600,"defense":1292,"evasion":1233}}' WHERE name = 'Locus Colibri';
UPDATE monster_templates SET hp_min = 244000, hp = 259000, level_stats = '{"135":{"hp":244000,"defense":1370,"evasion":1224},"136":{"hp":251500,"defense":1404,"evasion":1254},"137":{"hp":259000,"defense":1438,"evasion":1284}}' WHERE name = 'Locus Wivre';
UPDATE monster_templates SET hp_min = 258000, hp = 275300, level_stats = '{"134":{"hp":258000,"defense":1259,"evasion":1171},"135":{"hp":266600,"defense":1292,"evasion":1202},"136":{"hp":275300,"defense":1325,"evasion":1231}}' WHERE name = 'Locus Imp';
UPDATE monster_templates SET hp_min = 234400, hp = 251400, level_stats = '{"131":{"hp":234400,"defense":1162,"evasion":1083},"132":{"hp":242900,"defense":1192,"evasion":1122},"133":{"hp":251400,"defense":1228,"evasion":1162}}' WHERE name = 'Locus Tomb Worm';
UPDATE monster_templates SET hp_min = 274100, hp = 292200, level_stats = '{"134":{"hp":274100,"defense":1397,"evasion":1193},"135":{"hp":283100,"defense":1431,"evasion":1224},"136":{"hp":292200,"defense":1466,"evasion":1254}}' WHERE name = 'Locus Armet Beetle';
UPDATE monster_templates SET hp_min = 271400, hp = 289600, level_stats = '{"133":{"hp":271400,"defense":1272,"evasion":1163},"134":{"hp":280500,"defense":1305,"evasion":1193},"135":{"hp":289600,"defense":1338,"evasion":1224}}' WHERE name = 'Locus Dire Bat';
UPDATE monster_templates SET hp_min = 289700, hp = 308100, level_stats = '{"135":{"hp":289700,"defense":1346,"evasion":1224},"136":{"hp":298900,"defense":1379,"evasion":1254},"137":{"hp":308100,"defense":1413,"evasion":1284}}' WHERE name = 'Locus Hati';
UPDATE monster_templates SET hp_min = 266500, hp = 284000, level_stats = '{"135":{"hp":266500,"defense":1292,"evasion":1202},"136":{"hp":275400,"defense":1325,"evasion":1231},"137":{"hp":284000,"defense":1358,"evasion":1260}}' WHERE name = 'Locus Spartoi Sorcerer';
UPDATE monster_templates SET hp_min = 282600, hp = 300600, level_stats = '{"135":{"hp":282600,"defense":1321,"evasion":1224},"136":{"hp":291600,"defense":1355,"evasion":1254},"137":{"hp":300600,"defense":1389,"evasion":1284}}' WHERE name = 'Locus Spartoi Warrior';
UPDATE monster_templates SET hp_min = 293000, hp = 311800, level_stats = '{"136":{"hp":293000,"defense":1374,"evasion":1254},"137":{"hp":302300,"defense":1408,"evasion":1284},"138":{"hp":311800,"defense":1441,"evasion":1314}}' WHERE name = 'Locus Lemures';
UPDATE monster_templates SET hp_min = 305000, hp = 305000, level_stats = '{"135":{"hp":305000,"defense":1321,"evasion":1224},"136":{"hp":305000,"defense":1355,"evasion":1254},"137":{"hp":305000,"defense":1389,"evasion":1284}}' WHERE name = 'Locus Cutlass Scorpion';

-- Flat-HP Locus with no published per-level table.  Lemures and Spartoi used to
-- carry 2,740 / 311,800 placeholder HP; their exact rows are in level_stats above.
UPDATE monster_templates SET hp_min = 305000, hp = 305000
    WHERE name IN ('Locus Blazer Elytra', 'Locus Dragonfly', 'Locus Hornfly',
                   'Locus Lugcrawler', 'Locus Nest Elytra', 'Locus Soldier Lugcrawler',
                   'Locus Worker Lugcrawler');

-- Roll every Locus spawn inside its own retail level range.  mob_from_row() already
-- does this when the spawn level is NULL; the import wrote the minimum into every row.
UPDATE monster_spawns SET level = NULL
    WHERE template_id IN (SELECT id FROM monster_templates WHERE name LIKE 'Locus%');

