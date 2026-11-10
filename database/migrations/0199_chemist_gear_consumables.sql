-- Give a Chemist the test armor the CHM GearSwap library expects, with a
-- spell-interruption-down / capped-haste set.  The previous character only had
-- the rod and shield equipped, so every hit interrupted Mix and the armor menu
-- had nothing to wear.
--
-- The same rows also stock the elemental coatings and animas in the inventory;
-- the Battle Bag loader (`//chm load <item>`) is separate from armor.
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 41, 24270, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=41);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 42, 26963, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=42);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 43, 15004, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=43);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 44, 25853, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=44);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 45, 27475, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=45);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 46, 27509, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=46);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 47, 26365, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=47);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 48, 26120, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=48);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 49, 27540, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=49);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 50, 26184, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=50);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 51, 26214, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=51);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 52, 26275, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=52);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 53, 22279, 1 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=53);

INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 61, 637,   99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=61);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 62, 947,   99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=62);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 63, 4509,  99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=63);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 64, 18228, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=64);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 65, 4164,  99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=65);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 66, 17313, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=66);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 67, 30008, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=67);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 68, 30009, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=68);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 69, 30010, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=69);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 70, 30011, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=70);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 71, 30012, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=71);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 72, 30013, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=72);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 73, 30014, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=73);
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT c.id, 0, 74, 30015, 99 FROM characters c WHERE c.main_job = 23
  AND NOT EXISTS (SELECT 1 FROM char_inventory x WHERE x.character_id=c.id AND x.container=0 AND x.slot=74);

-- Equip the defensive set immediately.  GearSwap can replace it later, but the
-- character should not be naked while the client's native armor menu is limited.
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 4, 0, 41, 24270 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 5, 0, 42, 26963 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 6, 0, 43, 15004 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 7, 0, 44, 25853 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 8, 0, 45, 27475 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 9, 0, 46, 27509 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 10, 0, 47, 26365 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 11, 0, 48, 26120 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 12, 0, 49, 27540 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 13, 0, 50, 26184 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 14, 0, 51, 26214 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 15, 0, 52, 26275 FROM characters WHERE main_job = 23;
INSERT OR REPLACE INTO char_equip (character_id, kind, container, slot, item_id)
SELECT id, 3, 0, 53, 22279 FROM characters WHERE main_job = 23;
