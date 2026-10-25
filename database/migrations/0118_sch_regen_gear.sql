-- Scholar Regen potency/duration gear (migration 118).
--
-- The gearswap library now names the Community Scholar Guide's two Regen
-- sets.  This migration puts the missing pieces into Onedough's inventory so
-- "Wear set" can find them, and fills the item lines the reforged import did
-- not model:
--
--   * Musa Path C is "Regen" potency +25, "Cure" potency +25%, "Fast Cast"+10.
--   * Embla Sash is Fast Cast+5% and Enhancing magic duration +10%.
--   * Telchine Chas. carries "Regen" effect duration +12 in its base stats.
--   * The Telchine pieces and Bookworm's Cape in the guide's sets carry both
--     Alluvion augments "Regen" potency +10 and "Enh. Mag. eff. dur."+10.
--     Migration 118 uses temporary static lines; migration 119 replaces them
--     with the real two-slot 24-byte augment blocks.
--
-- The item ids come from tools/client_item_names.tsv / the imported catalog.
-- The grant uses the free inventory slots first, skips anything already owned
-- in a bag, storage or the locker, and is safe to run again.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 (22099, 170, 10),       -- Musa Path C: "Fast Cast"+10
 (22099, 374, 25),       -- Musa Path C: "Cure" potency +25%
 (22099, 838, 25),       -- Musa Path C: "Regen" potency +25
 (26354, 170, 5),        -- Embla Sash: "Fast Cast"+5%
 (26354, 890, 10),       -- Embla Sash: Enhancing magic duration +10%
 (26894, 339, 12),       -- Telchine Chas.: "Regen" effect duration +12
 (26736, 838, 10),       -- Telchine Cap: "Regen" potency +10
 (26736, 1222, 10),      -- Telchine Cap: Enhancing magic duration augment +10%
 (26894, 838, 10),       -- Telchine Chas.: "Regen" potency +10
 (26894, 1222, 10),      -- Telchine Chas.: Enhancing magic duration augment +10%
 (27048, 838, 10),       -- Telchine Gloves: "Regen" potency +10
 (27048, 1222, 10),      -- Telchine Gloves: Enhancing magic duration augment +10%
 (27235, 838, 10),       -- Telchine Braconi: "Regen" potency +10
 (27235, 1222, 10),      -- Telchine Braconi: Enhancing magic duration augment +10%
 (27405, 838, 10),       -- Telchine Pigaches: "Regen" potency +10
 (27405, 1222, 10),      -- Telchine Pigaches: Enhancing magic duration augment +10%
 (28636, 838, 10),       -- Bookworm's Cape: "Regen" potency +10
 (28636, 1222, 10);      -- Bookworm's Cape: Enhancing magic duration augment +10%

CREATE TEMP TABLE IF NOT EXISTS sch_regen_wanted (
    ord     INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL UNIQUE
);
DELETE FROM sch_regen_wanted;
INSERT INTO sch_regen_wanted (ord, item_id) VALUES
 (1, 22099),   -- Musa
 (2, 22218),   -- Khonsu
 (3, 26736),   -- Telchine Cap
 (4, 26894),   -- Telchine Chas.
 (5, 27048),   -- Telchine Gloves
 (6, 27235),   -- Telchine Braconi
 (7, 27405),   -- Telchine Pigaches
 (8, 26354),   -- Embla Sash
 (9, 28636),   -- Bookworm's Cape
 (10, 26088),  -- Malignance Earring
 (11, 26095);  -- Mimir Earring

WITH RECURSIVE
target(id) AS (
    SELECT id FROM characters WHERE name = 'Onedough' COLLATE NOCASE
),
slots(slot) AS (
    SELECT 1
    UNION ALL
    SELECT slot + 1 FROM slots WHERE slot < 80
),
free AS (
    SELECT t.id AS character_id, s.slot,
           ROW_NUMBER() OVER (ORDER BY s.slot) AS rn
    FROM target t CROSS JOIN slots s
    WHERE NOT EXISTS (
        SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = t.id AND ci.container = 0 AND ci.slot = s.slot
    )
),
need AS (
    SELECT w.item_id, ROW_NUMBER() OVER (ORDER BY w.ord) AS rn
    FROM sch_regen_wanted w
    WHERE NOT EXISTS (
        SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = (SELECT id FROM target) AND ci.item_id = w.item_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM char_storage cs
        WHERE cs.character_id = (SELECT id FROM target) AND cs.item_id = w.item_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM char_locker cl
        WHERE cl.character_id = (SELECT id FROM target) AND cl.item_id = w.item_id
    )
)
INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT f.character_id, 0, f.slot, n.item_id, 1
FROM need n JOIN free f ON f.rn = n.rn;
