-- Fanxi starter world, migration 3.
-- A small, deliberately authored slice: three city NPCs, two field mobs, two items and one quest.
-- Positions are in the zones' world coordinates; the client's own DATs supply the terrain and
-- art. Model ids are the game's model identifiers (the client already has these models).

INSERT INTO world_npcs (zone, name, pos_x, pos_y, pos_z, rot, model, script, triggerable, widescan, content_tag)
VALUES
    (246, 'Fanxi Guide',        -84.0, 12.0, 112.0, 128, 50, 'guide',       1, 1, 'tutorial'),
    (246, 'Wandering Moogle',   -92.0, 12.0, 110.0, 160, 50, 'moogle',      1, 1, 'tutorial'),
    (246, 'Chocobo Stablehand', -96.0, 12.0, 122.0, 192, 50, 'stablehand',  1, 1, 'tutorial');

INSERT INTO npc_lines (npc_id, line_no, text)
VALUES
    ((SELECT id FROM world_npcs WHERE name = 'Fanxi Guide'),
     0, 'Welcome to Fanxi. Target me and press the action button to talk.'),
    ((SELECT id FROM world_npcs WHERE name = 'Wandering Moogle'),
     0, 'Kupo! The fields west of Jeuno are full of things that bite. Say !zone 100 when you are ready.'),
    ((SELECT id FROM world_npcs WHERE name = 'Chocobo Stablehand'),
     0, 'The stables are closed for now, but the road west is open. Try !zone 100.');

INSERT INTO monster_templates (name, model, level_min, level_max, hp, attack, defense, accuracy, evasion,
                       attack_delay_ms, aggro, roam_radius, respawn_seconds, behavior, content_tag)
VALUES
    ('Orcish Grunt', 612, 3, 4, 80, 9, 3, 78, 12, 3000, 1, 5.0, 25, 'roam', 'starter'),
    ('Lambton Worm', 2027, 2, 3, 45, 6, 1, 72, 8, 3200, 0, 2.0, 20, 'roam', 'starter');

INSERT INTO monster_spawns (template_id, zone, pos_x, pos_y, pos_z, rot, level, respawn_seconds)
VALUES
    ((SELECT id FROM monster_templates WHERE name = 'Orcish Grunt'), 100, -150.0, -62.0, 250.0, 64, 3, 25),
    ((SELECT id FROM monster_templates WHERE name = 'Orcish Grunt'), 100, -120.0, -62.0, 290.0, 128, 4, 25),
    ((SELECT id FROM monster_templates WHERE name = 'Orcish Grunt'), 100, -175.0, -62.0, 300.0, 192, 3, 25),
    ((SELECT id FROM monster_templates WHERE name = 'Lambton Worm'), 100, -100.0, -62.0, 250.0, 96, 2, 20),
    ((SELECT id FROM monster_templates WHERE name = 'Lambton Worm'), 100, -140.0, -62.0, 330.0, 32, 3, 20),
    ((SELECT id FROM monster_templates WHERE name = 'Lambton Worm'), 100, -160.0, -62.0, 270.0, 224, 2, 20);

INSERT INTO items (item_id, name, stack, usable, equip_slot, level, description)
VALUES
    (16534, 'Onion Sword', 1, 0, 'main', 1, 'A dependable starter sword.'),
    (16535, 'Bronze Sword', 1, 0, 'main', 1, 'A heavier starter sword.'),
    (4112, 'Potion', 12, 1, '', 1, 'Restores a small amount of HP.');

INSERT INTO quests (quest_key, name, description, reward_gil, reward_item_id, reward_item_qty,
                    required_template_id, required_kills)
VALUES
    ('pest_control', 'Pest Control',
     'The Fanxi Guide wants the Orcish Grunts in West Ronfaure thinned out.',
     300, 4112, 2, (SELECT id FROM monster_templates WHERE name = 'Orcish Grunt'), 3);

-- Every existing character gets the same starter purse and pack a new character gets.
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT id, 0, 0, 65535, 1000 FROM characters;
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT id, 0, 1, 4112, 2 FROM characters;
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT id, 0, 2, 16534, 1 FROM characters;

UPDATE settings SET value = '2' WHERE key = 'schema_version';

-- Earlier builds used item 0 for the gil slot; the client expects item 65535.
UPDATE char_inventory SET item_id = 65535 WHERE container = 0 AND slot = 0 AND item_id = 0;

-- Existing characters receive the starter grant; keep the denormalized gil column in step.
UPDATE characters SET gil = 1000 WHERE gil = 0;
