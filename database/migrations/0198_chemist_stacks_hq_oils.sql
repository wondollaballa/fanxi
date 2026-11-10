-- Chemist Battle Bag: every slot is a 99-deep stack, and Mix rolls HQ.
-- The old item rows capped most custom potions at 3, which is why one Toss
-- consumed a whole slot.  The service clamps to bag_stack, so raise it here.
UPDATE chemist_items SET bag_stack = 99;
UPDATE chemist_recipes SET yield = 12;

INSERT OR IGNORE INTO items
    (item_id, name, stack, usable, equip_slot, level, description, model,
     slot_mask, jobs, skill, rare, ex, base_sell, price, item_level, category, subskill)
VALUES
    (30016, 'Fire Anima',      99, 1, '', 1, 'Chemist elemental anima (fire).',      0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30009, 'Ice Anima',       99, 1, '', 1, 'Chemist elemental anima (ice).',       0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30010, 'Wind Anima',      99, 1, '', 1, 'Chemist elemental anima (wind).',      0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30011, 'Earth Anima',     99, 1, '', 1, 'Chemist elemental anima (earth).',     0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30012, 'Lightning Anima', 99, 1, '', 1, 'Chemist elemental anima (lightning).',0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30013, 'Water Anima',     99, 1, '', 1, 'Chemist elemental anima (water).',     0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30014, 'Light Anima',     99, 1, '', 1, 'Chemist elemental anima (light).',     0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0),
    (30015, 'Dark Anima',      99, 1, '', 1, 'Chemist elemental anima (dark).',      0, 0, 4194304, 0, 0, 0, 0, 0, 0, '', 0);


-- Oil / grenade / anima consumables.  They are ordinary hostile items so the
-- existing Battle Bag and 0x05A/0x028 action path can carry them.
INSERT OR REPLACE INTO chemist_items
    (item_id, kind, alchemy_req, bag_stack, effect_key, duration, tier)
VALUES
    (637,   'hostile',  0, 99, 2101, 300, 0), -- Slime Oil: fire
    (947,   'hostile',  0, 99, 2101, 300, 0), -- Firesand: fire
    (4509,  'hostile', 20, 99, 2102, 300, 0), -- Distilled Water: ice
    (18228, 'hostile', 20, 99, 2103, 300, 0), -- Battery: lightning
    (4164,  'hostile', 20, 99, 2104, 300, 0), -- Prism Powder: light
    (17313, 'hostile', 50, 99, 2105,   0, 1), -- Grenade: fire burst
    (30016, 'hostile', 10, 99, 2101,  60, 0), -- Fire Anima
    (30009, 'hostile', 10, 99, 2102,  60, 0), -- Ice Anima
    (30010, 'hostile', 10, 99, 2106,  60, 0), -- Wind Anima
    (30011, 'hostile', 10, 99, 2107,  60, 0), -- Earth Anima
    (30012, 'hostile', 10, 99, 2103,  60, 0), -- Lightning Anima
    (30013, 'hostile', 10, 99, 2108,  60, 0), -- Water Anima
    (30014, 'hostile', 10, 99, 2104,  60, 0), -- Light Anima
    (30015, 'hostile', 10, 99, 2109,  60, 0); -- Dark Anima

-- The elemental animas are custom item ids; give them a real catalogue row so
-- they can be loaded, shown on the client and stack to 99.
-- Oils, powders and animas are Mix restocks too.
INSERT OR REPLACE INTO chemist_recipes (item_id, yield, cast_ms, alchemy_req)
VALUES
    (637, 12, 12000, 0), (947, 12, 12000, 0), (4509, 12, 12000, 20),
    (18228, 12, 12000, 20), (4164, 12, 12000, 20), (17313, 12, 15000, 50),
    (30016, 12, 12000, 10), (30009, 12, 12000, 10), (30010, 12, 12000, 10),
    (30011, 12, 12000, 10), (30012, 12, 12000, 10), (30013, 12, 12000, 10),
    (30014, 12, 12000, 10), (30015, 12, 12000, 10);

INSERT OR IGNORE INTO chemist_recipe_reagents (item_id, reagent_id, quantity)
VALUES
    (637, 4096, 1), (637, 4101, 1),
    (947, 4096, 1), (947, 4099, 1),
    (4509, 4101, 1), (18228, 4100, 1), (4164, 4102, 1),
    (17313, 4096, 1), (17313, 4099, 1),
    (30016, 4096, 1), (30009, 4097, 1), (30010, 4098, 1),
    (30011, 4099, 1), (30012, 4100, 1), (30013, 4101, 1),
    (30014, 4102, 1), (30015, 4103, 1);

INSERT OR IGNORE INTO char_chemist_recipes (character_id, item_id)
SELECT c.id, r.item_id FROM characters c CROSS JOIN chemist_recipes r;

-- Retail stack sizes matter for the inventory copies of the new consumables.
UPDATE items SET stack = 99
WHERE item_id IN (637, 947, 4509, 18228, 4164, 17313, 30016, 30009, 30010,
                  30011, 30012, 30013, 30014, 30015);
