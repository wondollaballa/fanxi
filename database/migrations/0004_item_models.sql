-- The visual model a piece of equipment uses on the character.  The client's grap list
-- wants the weapon/armour model id, not the item id; Onion Sword and Bronze Sword are the
-- two starter weapons whose ids we already seed.
ALTER TABLE items ADD COLUMN model INTEGER NOT NULL DEFAULT 0;

UPDATE items SET model = 264 WHERE item_id = 16534; -- Onion Sword
UPDATE items SET model = 268 WHERE item_id = 16535; -- Bronze Sword
