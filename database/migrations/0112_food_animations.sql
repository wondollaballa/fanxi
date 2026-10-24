-- The eating animation each food plays (migration 112).
--
-- Using an item sends C2S 0x037, and the client animates it from the result's sub_kind
-- in the S2C 0x028 ItemFinish action.  The value is LandSandBoat's
-- item_usable.animation: 24-28 are the eating and drinking motions.  Without the
-- action the food was consumed with its effect applied, but the character stood still.
--
-- The starter table's foods are all meals, so 26 (eat) is the default.  The soup uses
-- the bowl motion, the cake the small-sweet motion and the curry bun and ramen the
-- bowl-with-chopsticks motion, matching the retail item rows.

ALTER TABLE food_effects ADD COLUMN animation INTEGER NOT NULL DEFAULT 26;

UPDATE food_effects SET animation = 27 WHERE item_id = 4333;  -- Witch Soup
UPDATE food_effects SET animation = 24 WHERE item_id = 5633;  -- Chocolate Cake
UPDATE food_effects SET animation = 28 WHERE item_id IN (5759, 6460);
                                                              -- Red Curry Bun, Miso Ramen
