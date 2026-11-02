-- Limbus Rank 30 weapons (migration 0175).
--
-- The sixteen Telopanos weapons: the fourteen weapon skills, the shield
-- and the grip.  An Auge Scintistone plus units from Temenos or Apollyon
-- lifts the Telognophos base weapon to this form, and the same furnace adds
-- the Rank 30 rows.  The items themselves are already in the catalogue
-- (migration 111) and their damage/delay in item_weapon (migration 80); this
-- migration adds what the client's tooltip has and the server did not:
-- the base modifiers, the client skill bonuses and a description.
--
-- The Rank 30 rows come from BG Wiki; each weapon's client augment bundle
-- index is the client's own augment table (512 entries,
-- 497-512 are this family), matched to those rows by content.  The grant
-- hands both mains one unaugmented copy so the Data page's RP card can cap
-- it; ``//rp30`` re-stamps anything already carried.
--
-- Generated from data/limbus_weapons_r30.json by tools/gen_limbus_weapons.py.

DELETE FROM item_mods WHERE item_id IN (18800, 21549, 21599, 21738, 21795, 21848, 21899, 21942, 21948, 22176, 22182, 22188, 22225, 22231, 22237, 26503);

-- Base modifiers from each weapon's stat line.
INSERT INTO item_mods (item_id,mod_id,value) VALUES
  (18800,25,31), (18800,26,31), (18800,30,31), (18800,160,-400), (18800,384,400), (18800,1081,9),
  (21549,25,32), (21549,30,32), (21549,160,-500), (21549,384,500), (21549,1081,10),
  (21599,25,32), (21599,26,32), (21599,30,32), (21599,160,-500), (21599,384,500), (21599,1081,10),
  (21738,25,32), (21738,30,32), (21738,160,-500), (21738,384,500), (21738,1081,10),
  (21795,25,32), (21795,30,32), (21795,160,-500), (21795,384,500), (21795,1081,10),
  (21848,25,32), (21848,30,32), (21848,160,-500), (21848,384,500), (21848,1081,10),
  (21899,25,32), (21899,30,32), (21899,160,-500), (21899,384,500), (21899,1081,10),
  (21942,25,32), (21942,26,32), (21942,30,32), (21942,160,-500), (21942,384,500), (21942,1081,10),
  (21948,25,32), (21948,26,32), (21948,30,32), (21948,160,-500), (21948,384,500), (21948,1081,10),
  (22176,26,32), (22176,30,32), (22176,160,-500), (22176,365,5), (22176,1081,10),
  (22182,25,32), (22182,30,32), (22182,160,-500), (22182,384,500), (22182,1081,10),
  (22188,25,32), (22188,28,52), (22188,30,32), (22188,160,-500), (22188,311,250), (22188,384,500), (22188,1081,5),
  (22225,25,32), (22225,28,52), (22225,30,32), (22225,160,-500), (22225,311,250), (22225,384,500), (22225,1081,5),
  (22231,25,32), (22231,28,72), (22231,30,32), (22231,160,-500), (22231,311,312), (22231,384,500), (22231,1081,5),
  (22237,25,32), (22237,30,32), (22237,160,-500), (22237,384,500), (22237,1081,10),
  (26503,1,152), (26503,25,32), (26503,30,32), (26503,190,-500), (26503,384,500), (26503,831,-500);

DELETE FROM item_skill_bonus WHERE item_id IN (18800, 21549, 21599, 21738, 21795, 21848, 21899, 21942, 21948, 22176, 22182, 22188, 22225, 22231, 22237, 26503);

-- Client skill bonuses (0x062 skill ids): the weapon's own skill,
-- Parrying (31), Guard (28) and Shield (30) where the tooltip lists them.
INSERT INTO item_skill_bonus (item_id,skill_id,amount) VALUES
  (21549,1,255),
  (21549,28,255),
  (21599,2,255),
  (21599,31,255),
  (21738,5,255),
  (21738,31,255),
  (21795,6,255),
  (21795,31,255),
  (21848,7,255),
  (21848,31,255),
  (21899,8,255),
  (21899,31,255),
  (21942,9,255),
  (21942,31,255),
  (21948,10,255),
  (21948,31,255),
  (22176,25,255),
  (22182,3,255),
  (22182,31,255),
  (22188,3,255),
  (22188,31,255),
  (22225,11,255),
  (22225,31,255),
  (22231,12,255),
  (22231,31,255),
  (22237,4,255),
  (22237,31,255),
  (26503,30,121);

-- The client's own description line, for the catalogue and the Armory.
UPDATE items SET description = CASE item_id
  WHEN 18800 THEN 'Accuracy+31 Ranged Accuracy+31 Magic Accuracy+31 Haste+4% Physical damage limit +9% Damage taken -4%'
  WHEN 21549 THEN 'DMG:173 Delay:91 Accuracy+32 Magic Accuracy+32 Hand-to-Hand skill +255 Guard skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5% Automaton: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2'
  WHEN 21599 THEN 'DMG:128 Delay:189 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Dagger skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 21738 THEN 'DMG:181 Delay:268 Accuracy+32 Magic Accuracy+32 Axe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5% Main hand: Pet: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2'
  WHEN 21795 THEN 'DMG:330 Delay:489 Accuracy+32 Magic Accuracy+32 Great Axe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 21848 THEN 'DMG:345 Delay:513 Accuracy+32 Magic Accuracy+32 Scythe skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 21899 THEN 'DMG:259 Delay:385 Accuracy+32 Magic Accuracy+32 Polearm skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5% Wyvern: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2'
  WHEN 21942 THEN 'DMG:149 Delay:222 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Katana skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 21948 THEN 'DMG:294 Delay:435 Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Great Katana skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 22176 THEN 'DMG:316 Delay:582 Ranged Accuracy+32 Magic Accuracy+32 Archery skill +255 Snapshot +5 Physical damage limit +10% Damage taken -5%'
  WHEN 22182 THEN 'DMG:173 Delay:258 Accuracy+32 Magic Accuracy+32 Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 22188 THEN 'DMG:157 Delay:233 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +52 Magic damage +250 Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5%'
  WHEN 22225 THEN 'DMG:223 Delay:334 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +52 Magic damage +250 Club skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5%'
  WHEN 22231 THEN 'DMG:240 Delay:356 Accuracy+32 Magic Accuracy+32 Magic Attack Bonus +72 Magic damage +312 Staff skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +5% Damage taken -5% Avatar: Accuracy+32 Ranged Accuracy+32 Magic Accuracy+32 Lv.+2'
  WHEN 22237 THEN 'DMG:314 Delay:466 Accuracy+32 Magic Accuracy+32 Great Sword skill +255 Parrying skill +255 Magic Accuracy skill +255 Haste+5% Physical damage limit +10% Damage taken -5%'
  WHEN 26503 THEN 'DEF:152 Accuracy+32 Magic Accuracy+32 Shield skill +121 Haste+5% Damage taken II -5%'
  ELSE description END
 WHERE item_id IN (18800, 21549, 21599, 21738, 21795, 21848, 21899, 21942, 21948, 22176, 22182, 22188, 22225, 22231, 22237, 26503);

-- Give both mains one copy of each weapon, into their first free slots.
-- The copies are unaugmented: the RP card on the Data page caps a path in
-- one click, which is the point of granting them.
WITH RECURSIVE
  target(character_id) AS (
    SELECT id FROM characters WHERE id IN (1, 2)
  ),
  containers(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),(1,9),(5,10),(6,11),(7,12),(9,13)
  ),
  nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums WHERE n < 80),
  free AS (
    SELECT t.character_id, c.container, n.n AS slot,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY c.ord, n.n) AS rn
    FROM target t CROSS JOIN containers c CROSS JOIN nums n
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.container = c.container AND ci.slot = n.n
    )
  ),
  want AS (
    SELECT t.character_id, w.item_id,
           ROW_NUMBER() OVER (PARTITION BY t.character_id ORDER BY w.item_id) AS rn
    FROM target t CROSS JOIN (SELECT 18800 AS item_id UNION ALL SELECT 21549 AS item_id UNION ALL SELECT 21599 AS item_id UNION ALL SELECT 21738 AS item_id UNION ALL SELECT 21795 AS item_id UNION ALL SELECT 21848 AS item_id UNION ALL SELECT 21899 AS item_id UNION ALL SELECT 21942 AS item_id UNION ALL SELECT 21948 AS item_id UNION ALL SELECT 22176 AS item_id UNION ALL SELECT 22182 AS item_id UNION ALL SELECT 22188 AS item_id UNION ALL SELECT 22225 AS item_id UNION ALL SELECT 22231 AS item_id UNION ALL SELECT 22237 AS item_id UNION ALL SELECT 26503) AS w
    WHERE NOT EXISTS (
      SELECT 1 FROM char_inventory ci
      WHERE ci.character_id = t.character_id AND ci.item_id = w.item_id
    )
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT w.character_id, f.container, f.slot, w.item_id, 1
FROM want w JOIN free f ON f.character_id = w.character_id AND f.rn = w.rn;

-- Both mains can re-check the dataset in chat: //r30 telopanos prints each
-- weapon's Rank 30 rows and //rp30 re-stamps the 55800-RP block.
