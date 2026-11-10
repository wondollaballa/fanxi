-- 30008 was already the legacy Chemistry Toolkit item.  The fresh-schema rows
-- use 30016 for Fire Anima; this repairs databases that applied 0198 first.
INSERT OR IGNORE INTO items
    (item_id, name, stack, usable, equip_slot, level, description, model,
     slot_mask, jobs, skill, rare, ex, base_sell, price, item_level, category, subskill)
VALUES
    (30016, 'Fire Anima', 99, 1, '', 1, 'Chemist elemental anima (fire).',
     0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0);

DELETE FROM chemist_recipe_reagents WHERE item_id = 30008;
DELETE FROM char_chemist_recipes WHERE item_id = 30008;
DELETE FROM chemist_recipes WHERE item_id = 30008;
DELETE FROM chemist_items WHERE item_id = 30008 AND effect_key = 2101;

INSERT OR REPLACE INTO chemist_items
    (item_id, kind, alchemy_req, bag_stack, effect_key, duration, tier)
VALUES (30016, 'hostile', 10, 99, 2101, 60, 0);
INSERT OR REPLACE INTO chemist_recipes (item_id, yield, cast_ms, alchemy_req)
VALUES (30016, 12, 12000, 10);
INSERT OR IGNORE INTO chemist_recipe_reagents (item_id, reagent_id, quantity)
VALUES (30016, 4096, 1);
INSERT OR IGNORE INTO char_chemist_recipes (character_id, item_id)
SELECT id, 30016 FROM characters;

UPDATE char_inventory SET item_id = 30016
WHERE item_id = 30008 AND container = 0 AND slot = 67;
