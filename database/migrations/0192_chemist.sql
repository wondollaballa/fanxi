-- fanxi:foreign_keys_off
-- Chemist (job 23): job abilities, Battle Bag content and Chemistry recipes.
--
-- Job 23 needs one schema change first: the original characters table had
-- ``CHECK (main_job BETWEEN 1 AND 22)``.  SQLite cannot alter a CHECK constraint in
-- place, so rebuild the table with the two job columns widened to 23.  The foreign
-- keys on every child table still name ``characters``; the migration runner turns
-- foreign keys off for this file so dropping the old table cannot cascade into them.
--
-- The battle bag is server-side only.  Custom chemistry items (30000+) are never
-- char_inventory rows and have no client item record; the HUD draws them from the
-- Fanxi state, and Toss/Mix send ordinary job-ability actions.
--
-- Standard items in chemist_items are real inventory items (Potion 4112, ...).  Their
-- bag_stack is the virtual bag's cap, not the item's retail stack size.

DROP TABLE IF EXISTS characters_new;
CREATE TABLE characters_new (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    slot           INTEGER NOT NULL DEFAULT 1,
    char_id        INTEGER NOT NULL UNIQUE,
    name           TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    race           INTEGER NOT NULL CHECK (race BETWEEN 1 AND 8),
    face           INTEGER NOT NULL DEFAULT 1 CHECK (face BETWEEN 1 AND 8),
    size           INTEGER NOT NULL DEFAULT 1 CHECK (size BETWEEN 0 AND 2),
    nation         INTEGER NOT NULL DEFAULT 0 CHECK (nation BETWEEN 0 AND 2),
    main_job       INTEGER NOT NULL DEFAULT 1 CHECK (main_job BETWEEN 1 AND 23),
    sub_job        INTEGER NOT NULL DEFAULT 0 CHECK (sub_job BETWEEN 0 AND 23),
    main_level     INTEGER NOT NULL DEFAULT 1 CHECK (main_level BETWEEN 1 AND 99),
    sub_level      INTEGER NOT NULL DEFAULT 0 CHECK (sub_level BETWEEN 0 AND 99),
    hp             INTEGER NOT NULL DEFAULT 1500,
    mp             INTEGER NOT NULL DEFAULT 0,
    speed          INTEGER NOT NULL DEFAULT 50,
    zone           INTEGER NOT NULL DEFAULT 246,
    pos_x          REAL    NOT NULL DEFAULT -87.0,
    pos_y          REAL    NOT NULL DEFAULT 12.0,
    pos_z          REAL    NOT NULL DEFAULT 116.0,
    rot            INTEGER NOT NULL DEFAULT 128,
    head           INTEGER NOT NULL DEFAULT 0,
    body           INTEGER NOT NULL DEFAULT 8,
    hands          INTEGER NOT NULL DEFAULT 8,
    legs           INTEGER NOT NULL DEFAULT 8,
    feet           INTEGER NOT NULL DEFAULT 8,
    main           INTEGER NOT NULL DEFAULT 0,
    sub            INTEGER NOT NULL DEFAULT 0,
    ranged         INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    last_played_at TEXT,
    hp_current     INTEGER NOT NULL DEFAULT 1500,
    mp_current     INTEGER NOT NULL DEFAULT 0,
    exp            INTEGER NOT NULL DEFAULT 0,
    gil            INTEGER NOT NULL DEFAULT 0,
    playtime_seconds INTEGER NOT NULL DEFAULT 0,
    death_count    INTEGER NOT NULL DEFAULT 0,
    home_zone      INTEGER NOT NULL DEFAULT 246,
    home_x         REAL    NOT NULL DEFAULT -87.0,
    home_y         REAL    NOT NULL DEFAULT 12.0,
    home_z         REAL    NOT NULL DEFAULT 116.0,
    home_rot       INTEGER NOT NULL DEFAULT 128,
    moghouse       INTEGER NOT NULL DEFAULT 0,
    merit_points   INTEGER NOT NULL DEFAULT 127,
    limit_points   INTEGER NOT NULL DEFAULT 0,
    merit_mode     INTEGER NOT NULL DEFAULT 1,
    style_lock     INTEGER NOT NULL DEFAULT 0,
    style_head     INTEGER NOT NULL DEFAULT 0,
    style_body     INTEGER NOT NULL DEFAULT 0,
    style_hands    INTEGER NOT NULL DEFAULT 0,
    style_legs     INTEGER NOT NULL DEFAULT 0,
    style_feet     INTEGER NOT NULL DEFAULT 0,
    style_main     INTEGER NOT NULL DEFAULT 0,
    style_sub      INTEGER NOT NULL DEFAULT 0,
    style_ranged   INTEGER NOT NULL DEFAULT 0,
    hair           INTEGER NOT NULL DEFAULT 0 CHECK (hair IN (0, 1)),
    mastery_rank   INTEGER NOT NULL DEFAULT 0,
    rank_sandoria  INTEGER NOT NULL DEFAULT 1,
    rank_bastok    INTEGER NOT NULL DEFAULT 1,
    rank_windurst  INTEGER NOT NULL DEFAULT 1,
    rank_points    INTEGER NOT NULL DEFAULT 0,
    mog_garden_rank INTEGER NOT NULL DEFAULT 0,
    exemplar_points INTEGER NOT NULL DEFAULT 0,
    mount          INTEGER NOT NULL DEFAULT -1,
    style_main_type INTEGER NOT NULL DEFAULT 0,
    style_sub_type  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (account_id, slot)
);

INSERT INTO characters_new SELECT * FROM characters;
DROP TABLE characters;
ALTER TABLE characters_new RENAME TO characters;
CREATE INDEX IF NOT EXISTS characters_account ON characters(account_id);

-- Job 23 used to carry a placeholder "Relinquish" row in the imported table.  It has
-- no Chemist meaning, so remove it before installing the real kit
-- before installing the real kit.
DELETE FROM job_abilities WHERE id = 382 AND job = 23;

INSERT OR REPLACE INTO job_abilities
    (id, name, job, level, valid_targets, recast, recast_id, animation,
     animation_time, cast_time, action_type, range, add_type)
VALUES
    (395, 'Toss', 23, 1, 4, 0, 200, 186, 2000, 0, 3, 20.0, 0),
    (396, 'Mix', 23, 15, 27, 0, 201, 84, 2000, 0, 6, 20.0, 0),
    (397, 'Catalyst', 23, 35, 1, 60, 202, 171, 2000, 0, 6, 0.0, 0),
    (398, 'Amplify', 23, 50, 1, 120, 203, 175, 2000, 0, 6, 0.0, 0),
    (399, 'Volatile Synthesis', 23, 75, 1, 180, 204, 188, 2000, 0, 6, 0.0, 0);

INSERT OR REPLACE INTO items
    (item_id, name, stack, usable, equip_slot, level, description, model,
     slot_mask, jobs, skill, rare, ex, base_sell, price, item_level, category)
VALUES
    (30000, 'Aqua Regia', 1, 1, '', 1, 'Chemist bomb: Defense Down.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30001, 'Sludge Bomb', 1, 1, '', 1, 'Chemist bomb: Evasion Down.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30002, 'Aether Spore', 1, 1, '', 1, 'Chemist bomb: Magic Defense and Magic Evasion Down.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30003, 'Vitriol I', 1, 1, '', 1, 'Chemist venom: unresistable damage over time.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30004, 'Vitriol II', 1, 1, '', 1, 'Chemist venom: stronger unresistable damage over time.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30005, 'Vitriol III', 1, 1, '', 1, 'Chemist venom: strongest unresistable damage over time.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30006, 'Gorgon''s Trap', 1, 1, '', 1, 'Chemist trap: Petrification.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry'),
    (30007, 'Tangle-Vine', 1, 1, '', 1, 'Chemist trap: area Bind.', 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Chemistry');

CREATE TABLE IF NOT EXISTS char_chemist_bag (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot         INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 26),
    item_id      INTEGER NOT NULL REFERENCES items(item_id),
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (character_id, slot),
    UNIQUE (character_id, item_id)
);

CREATE TABLE IF NOT EXISTS chemist_items (
    item_id       INTEGER PRIMARY KEY REFERENCES items(item_id) ON DELETE CASCADE,
    kind          TEXT NOT NULL CHECK (kind IN ('heal', 'mp', 'status', 'hostile')),
    amount        INTEGER NOT NULL DEFAULT 0,
    alchemy_scale INTEGER NOT NULL DEFAULT 0,
    alchemy_req   INTEGER NOT NULL DEFAULT 0,
    bag_stack     INTEGER NOT NULL DEFAULT 99,
    effect_key    INTEGER,
    potency_base  INTEGER NOT NULL DEFAULT 0,
    potency_cap   INTEGER NOT NULL DEFAULT 0,
    power_base    INTEGER NOT NULL DEFAULT 0,
    power_cap     INTEGER NOT NULL DEFAULT 0,
    duration      REAL NOT NULL DEFAULT 0,
    tick_base     INTEGER NOT NULL DEFAULT 0,
    tick_cap      INTEGER NOT NULL DEFAULT 0,
    tick_interval REAL NOT NULL DEFAULT 3,
    radius        REAL NOT NULL DEFAULT 0,
    max_targets   INTEGER NOT NULL DEFAULT 1,
    statuses      TEXT NOT NULL DEFAULT '',
    tier          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chemist_recipes (
    item_id     INTEGER PRIMARY KEY REFERENCES items(item_id) ON DELETE CASCADE,
    yield       INTEGER NOT NULL DEFAULT 3,
    cast_ms     INTEGER NOT NULL DEFAULT 12000,
    alchemy_req INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chemist_recipe_reagents (
    item_id    INTEGER NOT NULL REFERENCES chemist_recipes(item_id) ON DELETE CASCADE,
    reagent_id INTEGER NOT NULL REFERENCES items(item_id),
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    PRIMARY KEY (item_id, reagent_id)
);

-- Standard consumables that can be loaded into the bag.  The alchemy requirement is a
-- Chemist gate, not a change to ordinary /item use.
INSERT OR REPLACE INTO chemist_items
    (item_id, kind, amount, alchemy_scale, alchemy_req, bag_stack, statuses)
VALUES
    (4112, 'heal',  50, 1,  0, 99, ''),
    (4116, 'heal', 100, 2, 20, 99, ''),
    (4120, 'heal', 200, 3, 40, 99, ''),
    (4128, 'mp',    20, 0, 10, 99, ''),
    (4132, 'mp',    40, 1, 30, 99, ''),
    (4151, 'status', 0, 0,  0, 99, '6'),
    (4155, 'status', 0, 0, 30, 99, '3,4,5,6'),
    (4149, 'status', 0, 0, 50, 99, '3,4,5,6,7,8,10,11,13,31');

-- Custom chemistry items.  effect_key values are the server-side Chemist keys in
-- chemist.py, not client status ids.
INSERT OR REPLACE INTO chemist_items
    (item_id, kind, alchemy_req, bag_stack, effect_key,
     potency_base, potency_cap, power_base, power_cap, duration,
     tick_base, tick_cap, tick_interval, radius, max_targets, tier)
VALUES
    (30000, 'hostile', 10, 3, 2001, 10, 15, 0, 0, 60, 0, 0, 3, 0, 1, 0),
    (30001, 'hostile', 20, 3, 2002, 20, 25, 0, 0, 60, 0, 0, 3, 0, 1, 0),
    (30002, 'hostile', 30, 3, 2003, 10, 15, 15, 20, 60, 0, 0, 3, 0, 1, 0),
    (30003, 'hostile', 20, 3, 2010, 0, 0, 0, 0, 30, 10, 15, 3, 0, 1, 1),
    (30004, 'hostile', 40, 3, 2010, 0, 0, 0, 0, 30, 15, 22, 3, 0, 1, 2),
    (30005, 'hostile', 60, 3, 2010, 0, 0, 0, 0, 30, 20, 30, 3, 0, 1, 3),
    (30006, 'hostile', 50, 1, 7, 0, 0, 0, 0, 15, 0, 0, 3, 0, 1, 0),
    (30007, 'hostile', 40, 1, 11, 0, 0, 0, 0, 20, 0, 0, 3, 5, 4, 0);

INSERT OR REPLACE INTO chemist_recipes (item_id, yield, cast_ms, alchemy_req)
VALUES
    (30000, 3, 12000, 10),
    (30001, 3, 12000, 20),
    (30002, 3, 12000, 30),
    (30003, 3, 12000, 20),
    (30004, 3, 15000, 40),
    (30005, 3, 15000, 60),
    (30006, 1, 15000, 50),
    (30007, 1, 12000, 40);

INSERT OR REPLACE INTO chemist_recipe_reagents (item_id, reagent_id, quantity)
VALUES
    -- Aqua Regia: fire + water
    (30000, 4096, 2), (30000, 4101, 1),
    -- Sludge Bomb: earth + water
    (30001, 4099, 2), (30001, 4101, 1),
    -- Aether Spore: wind + light
    (30002, 4098, 2), (30002, 4102, 1),
    -- Vitriol I: water + dark
    (30003, 4101, 1), (30003, 4103, 1),
    -- Vitriol II: water + dark + ice
    (30004, 4097, 1), (30004, 4101, 2), (30004, 4103, 2),
    -- Vitriol III: water + dark + lightning
    (30005, 4100, 1), (30005, 4101, 3), (30005, 4103, 3),
    -- Gorgon's Trap: earth + dark
    (30006, 4099, 2), (30006, 4103, 2),
    -- Tangle-Vine: wind + earth + ice
    (30007, 4097, 1), (30007, 4098, 2), (30007, 4099, 2);

CREATE INDEX IF NOT EXISTS char_chemist_bag_item
    ON char_chemist_bag (character_id, item_id);
