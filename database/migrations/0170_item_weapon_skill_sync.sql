-- Sync a weapon's item skill type from item_weapon (migration 170).
--
-- Migration 66 added the GearSwap default-library items the server did not know yet with
-- skill 0.  Migration 111 then upserted the full catalogue, but deliberately refreshed
-- only price, base_sell, item_level and the Rare/Ex bits, so those placeholder rows kept
-- skill 0 even when migration 80 had given item_weapon their real type.  Equipping one
-- made ZoneSession.equipped_weapon_skills() see a non-weapon and drop that skill type from
-- 0x0AC: a Corsair's sets.WS.Wildfire put Armageddon (21269, skill 26 in item_weapon,
-- 0 in items) in the ranged slot, the Marksmanship tab vanished from the weapon-skill HUD,
-- and only the next Sword weapon skill set (Ataktos or another skill-26 gun) brought it
-- back.  Annihilator (21267), Gleti's Crossbow (22150), Chrono Bullet (21296), Daurdabla
-- (18839) and Loughnashade (22307) had the same split.
--
-- Any future row with the same mismatch is fixed here too.  The server's item_skill()
-- also falls back to item_weapon.skill, so a database that has not run this migration
-- still behaves; this keeps the catalogue itself honest.
UPDATE items
SET skill = (SELECT w.skill FROM item_weapon w WHERE w.item_id = items.item_id)
WHERE skill = 0
  AND EXISTS (SELECT 1 FROM item_weapon w
              WHERE w.item_id = items.item_id AND w.skill > 0);
