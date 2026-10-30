-- Knights of Rotund is item-granted, not a normal 350-skill sword weapon skill.
--
-- Id 227 came in with LandSandBoat's weapon_skills.sql and was copied with
-- skill_level 0.  In Fanxi that "quested/relic" marker means "offer it to every sword
-- user once Sword skill reaches 350", so a Paladin or Red Mage holding Caliburnus saw
-- both Imperator (233, granted by Caliburnus's 355 row) and Knights of Rotund (227,
-- granted by Excalipoor II's 355 row) in the Weapon Skills HUD.  Knights of Rotund is
-- the Excalipoor II joke skill; without that weapon it must not appear.
--
-- A negative skill_level is the table's item-granted marker.  The normal skill-value
-- list skips it, and ZoneSession.equipped_weapon_skills() adds it only while an item
-- whose 355 value is 227 is worn.  Excalipoor II (20714) already carries that row.

UPDATE weapon_skills SET skill_level = -1 WHERE id = 227;
