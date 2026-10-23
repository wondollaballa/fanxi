-- Skill bonuses from equipped items.  Retail item descriptions carry lines like
-- "Katana skill +277"; the item table itself has no stats, so the values used by the
-- Combat/Magic Skills menus live here.  A dual-wielded pair adds both weapons' bonuses.
CREATE TABLE IF NOT EXISTS item_skill_bonus (
    item_id  INTEGER NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL,
    amount   INTEGER NOT NULL,
    PRIMARY KEY (item_id, skill_id)
);

-- The currently equipped Ninja set (item ids from char_equip).
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (21932, 9, 277);   -- Dokoku 119 III: Katana
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (21932, 31, 277);  -- Dokoku 119 III: Parrying
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (21936, 9, 269);   -- Yagyu Darkblade: Katana
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (21936, 31, 269);  -- Yagyu Darkblade: Parrying
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (23907, 39, 18);   -- Hachiya Hatsuburi +4: Ninjutsu
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (23997, 27, 15);   -- Hachiya Tekko +4: Throwing
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (25494, 9, 12);    -- Hattori Earring +2: Katana
INSERT OR REPLACE INTO item_skill_bonus (item_id, skill_id, amount) VALUES (25494, 27, 12);   -- Hattori Earring +2: Throwing
