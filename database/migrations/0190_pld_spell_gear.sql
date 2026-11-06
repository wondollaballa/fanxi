-- Paladin spell-set gear (migration 190).
--
-- gearswap/PLD.lua now carries the Community Paladin Guide's magic and job-ability sets:
-- Flash / Flash SIRD, Cure / Cure SIRD, Max Self Phalanx / Phalanx SIRD, Reprisal /
-- Reprisal SIRD, the capped Stoneskin + SIRD set, the Aquaveil SIRD route and the Enlight
-- build.  The guide's pieces are mostly HQ abjuration, Escha Path C and Odyssean armour
-- that the account did not own yet; migration 66 granted the original library only.  This
-- hands the new names to the template account's character (Onedough, 1) and the Paladin
-- character (Fivedough, 5) the same way it did: free permanent-bag slots, wardrobe first,
-- never overwriting a moved item, and only where the item is missing from the bags, the
-- Mog Locker and the storage slips alike.
--
-- Every name below is already in the item catalogue, so this migration creates no item
-- rows and needs no ids of its own: the names are resolved through the items table.
-- "Odyss. Chestplate" is the catalogue's (abbreviated) name for Odyssean Chestplate, the
-- body the guide's Phalanx SIRD set wants; the Odyssean pieces are Oseem-augmented in
-- play, so the library carries their roll lines and the Oseem card writes the block.
-- Wear set asks for the item by name, so a copy is enough; the pieces can be moved to
-- storage later and the launcher will report them missing until they are returned.

WITH RECURSIVE
  target(character_id) AS (
    SELECT id FROM characters WHERE id IN (1, 5)
  ),
  wanted(name) AS (
    VALUES
      ('Ajax +1'), ('Altruistic Cape'), ('Andoaa Earring'), ('Brilliance'),
      ('Colada'), ('Earthcry Earring'), ('Egoist''s Tathlum'), ('Eschite Breast.'),
      ('Eschite Cuisses'), ('Eschite Gauntlets'), ('Eschite Greaves'), ('Eschite Helm'),
      ('Evanescence Ring'), ('Haven Hose'), ('Jumalik Helm'), ('Knight''s Earring'),
      ('Knightly Earring'), ('Macabre Gaunt. +1'), ('Moonlight Necklace'),
      ('Moonlight Ring'), ('Murky Ring'), ('Odyss. Chestplate'), ('Odyssean Greaves'),
      ('Odyssean Helm'), ('Olympus Sash'), ('Priwen'), ('Prolix Ring'),
      ('Regal Gauntlets'), ('Saxnot Earring'), ('Shab. Cuirass +1'), ('Siegel Sash'),
      ('Souv. Cuirass +1'), ('Souv. Handsch. +1'), ('Souv. Schaller +1'),
      ('Souveran Schuhs +1'), ('Sroda Belt'), ('Stone Gorget'), ('Stone Mufflers'),
      ('Trux Earring')
  ),
  want(character_id, item_id) AS (
    SELECT t.character_id, i.item_id
    FROM target t CROSS JOIN wanted w JOIN items i ON i.name = w.name
    WHERE NOT EXISTS (
        SELECT 1 FROM char_inventory ci
        WHERE ci.character_id = t.character_id AND ci.item_id = i.item_id)
      AND NOT EXISTS (
        SELECT 1 FROM char_locker cl
        WHERE cl.character_id = t.character_id AND cl.item_id = i.item_id)
      AND NOT EXISTS (
        SELECT 1 FROM char_storage cs
        WHERE cs.character_id = t.character_id AND cs.item_id = i.item_id)
  ),
  containers(container, ord) AS (
    VALUES (8,1),(10,2),(11,3),(12,4),(13,5),(14,6),(15,7),(16,8),
           (1,9),(5,10),(6,11),(7,12),(9,13)
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
  ranked AS (
    SELECT character_id, item_id,
           ROW_NUMBER() OVER (PARTITION BY character_id ORDER BY item_id) AS rn
    FROM want
  )
INSERT OR IGNORE INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT r.character_id, f.container, f.slot, r.item_id, 1
FROM ranked r JOIN free f ON f.character_id = r.character_id AND f.rn = r.rn;
