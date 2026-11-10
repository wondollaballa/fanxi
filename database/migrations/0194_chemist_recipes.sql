-- Chemist recipes, Chemistry Toolkits and the Brewer's Escutcheon.
--
-- 0192 introduced the bag and the first eight recipes.  This migration makes the
-- recipe book explicit, adds the universal Chemistry Toolkit, and gives the
-- Brewer's Escutcheon the craft-skill and synthesis-speed lines the Chemist uses.

-- Mix has always been the "use a prepared item" ability, but the character should
-- visibly work at the bag while doing it.  44 is LandSandBoat's xi::Animation::Synth.
UPDATE job_abilities SET animation = 44 WHERE id = 396;

CREATE TABLE IF NOT EXISTS char_chemist_recipes (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    item_id      INTEGER NOT NULL REFERENCES chemist_recipes(item_id) ON DELETE CASCADE,
    learned_at   TEXT    NOT NULL,
    PRIMARY KEY (character_id, item_id)
);

-- Every recipe is learned by every character, so the HUD has a complete book to
-- show.  A future quest can remove or gate individual rows without changing the UI.
INSERT OR IGNORE INTO char_chemist_recipes (character_id, item_id, learned_at)
SELECT c.id, r.item_id, datetime('now')
FROM characters c CROSS JOIN chemist_recipes r;

-- A one-slot universal reagent.  The real inventory item is what the player buys
-- and carries; it is not a bag-only item, so the normal 99-stack rules apply.
INSERT OR REPLACE INTO items
    (item_id, name, stack, usable, equip_slot, level, description, model,
     slot_mask, jobs, skill, rare, ex, base_sell, price, item_level, category)
VALUES
    (30008, 'Chemistry Toolkit', 99, 1, '', 1,
     'A compact kit of elemental reagents. One kit pays one Chemist synthesis.',
     0, 0, 0, 0, 0, 0, 0, 0, 0, 'Materials');

-- The Brewer's Escutcheon is the crafting shield shown on the job's equipment
-- plan.  CRAFT_SKILL raises every craft skill while it is equipped; ALCHEMY_SKILL
-- is the Chemist-specific gate, and CHEMISTRY_CAST is the synthesis-speed line
-- (the "ultimate alchemy shield" in the design note).
INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
    (26457, 1300, 100),   -- ALCHEMY_SKILL
    (26457, 1306, 100),   -- CRAFT_SKILL (all crafts)
    (26457, 1301, -10000); -- CHEMISTRY_CAST

UPDATE items SET jobs = jobs | 4194304 WHERE item_id = 26457;
