-- Reforged Dark Knight armour looks (migration 91).
--
-- Migration 66 inserted the i119 reforged sets as placeholders with model = 0.
-- The server copies items.model into the character's grap list when a piece is
-- equipped (zone.py _apply_equip_model), so model 0 leaves that slot at the
-- default look: the armour is on (stats, icon, tooltip) but the body, head,
-- legs or feet render as if bare.
--
-- The correct grap ids come from Windower's DressUp item -> model tables.  A
-- reforged set reuses the look of its original tier, so Dark Knight maps to
-- Chaos (artifact), Abyss (relic) and Bale (empyrean):
--   Ignominy   head 4174  body 8270  hands 12366  legs 16462  feet 20558
--   Fallen's   head 4175  body 8271  hands 12367  legs 16463  feet 20559
--   Heathen's  head 4385  body 8481  hands 12577  legs 16673  feet 20769
--
-- The other jobs' reforged pieces still carry 0 (or an LSB placeholder) until
-- the same mapping is applied to them.
UPDATE items SET model=4174  WHERE item_id=23902; -- Ignominy Burgeonet +4
UPDATE items SET model=8270  WHERE item_id=23947; -- Ignominy Cuirass +4
UPDATE items SET model=12366 WHERE item_id=23992; -- Ignominy Gauntlets +4
UPDATE items SET model=16462 WHERE item_id=24037; -- Ignominy Flanchard +4
UPDATE items SET model=20558 WHERE item_id=24082; -- Ignominy Sollerets +4
UPDATE items SET model=4175  WHERE item_id=23925; -- Fallen's Burgeonet +4
UPDATE items SET model=8271  WHERE item_id=23970; -- Fallen's Cuirass +4
UPDATE items SET model=12367 WHERE item_id=24015; -- Fallen's Finger Gauntlets +4
UPDATE items SET model=16463 WHERE item_id=24060; -- Fallen's Flanchard +4
UPDATE items SET model=20559 WHERE item_id=24105; -- Fallen's Sollerets +4
UPDATE items SET model=4385  WHERE item_id=23427; -- Heathen's Burgeonet +3
UPDATE items SET model=8481  WHERE item_id=23494; -- Heathen's Cuirass +3
UPDATE items SET model=12577 WHERE item_id=23561; -- Heathen's Gauntlets +3
UPDATE items SET model=16673 WHERE item_id=23628; -- Heathen's Flanchard +3
UPDATE items SET model=20769 WHERE item_id=23695; -- Heathen's Sollerets +3
