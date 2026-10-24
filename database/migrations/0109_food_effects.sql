-- Food effects and a starter shelf (migration 109).
--
-- Food is a modifier source, not a spell: the client shows the Food icon and the
-- server keeps the mods until the timer runs out.  The rows below are the common
-- stat foods (the LSB item scripts' numbers); the JSON key is the modifier id from
-- modifiers.py.  Adding another food is one row here plus its item row.
--
-- The scholar main gets one stack of each so the path can be exercised in game.

CREATE TABLE IF NOT EXISTS food_effects (
    item_id  INTEGER PRIMARY KEY,
    duration INTEGER NOT NULL,
    mods     TEXT    NOT NULL
);

INSERT OR IGNORE INTO items
 (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES
 (4413,'Apple Pie',12,1,'',1,'A tart made from ripe apples.',0,0,0),
 (4333,'Witch Soup',12,1,'',1,'A soup that sharpens the mind.',0,0,0),
 (5633,'Chocolate Cake',12,1,'',1,'A rich chocolate cake.',0,0,0),
 (6460,'Miso Ramen',12,1,'',1,'A hearty bowl of miso ramen.',0,0,0),
 (5759,'Red Curry Bun',12,1,'',1,'A spicy bun that strengthens the body.',0,0,0);

INSERT OR REPLACE INTO food_effects (item_id,duration,mods) VALUES
 -- Apple Pie: MP+25, AGI-1, INT+3 (30 min)
 (4413,1800,'{"5":25,"11":-1,"12":3}'),
 -- Witch Soup: MP+25, STR-1, MND+2, MP heal+1, Enmity-2 (4 h)
 (4333,14400,'{"5":25,"8":-1,"13":2,"71":1,"27":-2}'),
 -- Chocolate Cake: MP+3%, HP heal+1, MP heal+6 (3 h)
 (5633,10800,'{"6":3,"72":1,"71":6}'),
 -- Miso Ramen: HP+100, STR+5, VIT+5, Def.+10% (cap 170), M.Def.+5, Slow Resist+10
 (6460,1800,'{"176":100,"8":5,"10":5,"182":10,"183":170,"29":5,"240":10}'),
 -- Red Curry Bun: HP+35, STR+7, AGI+3, INT-2, HP/MP heal, Attack+23% (cap 150),
 -- Ranged Attack+23% (cap 150), Demon Killer+4, Sleep Resist+5
 (5759,1800,'{"176":35,"8":7,"11":3,"12":-2,"72":6,"71":3,"180":23,"181":150,"186":23,"187":150,"234":4,"240":5}');

-- Put one stack of each on Onedough so the food path is usable without a GM command.
INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0,
       COALESCE((SELECT MAX(i.slot) FROM char_inventory i
                  WHERE i.character_id = c.id AND i.container = 0), 0) + 1,
       4413, 12
  FROM characters c WHERE c.name = 'Onedough';

INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0,
       COALESCE((SELECT MAX(i.slot) FROM char_inventory i
                  WHERE i.character_id = c.id AND i.container = 0), 0) + 1,
       4333, 12
  FROM characters c WHERE c.name = 'Onedough';

INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0,
       COALESCE((SELECT MAX(i.slot) FROM char_inventory i
                  WHERE i.character_id = c.id AND i.container = 0), 0) + 1,
       6460, 12
  FROM characters c WHERE c.name = 'Onedough';

INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0,
       COALESCE((SELECT MAX(i.slot) FROM char_inventory i
                  WHERE i.character_id = c.id AND i.container = 0), 0) + 1,
       5759, 12
  FROM characters c WHERE c.name = 'Onedough';
