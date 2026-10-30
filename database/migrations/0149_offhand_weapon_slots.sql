-- One-handed axes and katanas imported by the hand-curated Beastmaster/Ninja grants kept
-- slot mask 1 (main hand only).  A one-handed weapon can also go in the off hand, which is
-- how Farsha (21752) and the other 119 III relic/mythic/empyrean/Prime axes are dual
-- wielded; the launcher's Sub picker and the server's equip check both read this mask.
--
-- Skill 5 is axe and skill 9 is katana.  Hand-to-hand (1), the two-handed families (4, 6,
-- 7, 8, 10, 12) and every other one-handed family already carry mask 3.
UPDATE items SET slot_mask = 3 WHERE skill IN (5, 9) AND slot_mask = 1;
