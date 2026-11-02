-- Item tooltips the server could not see: Null Masque, Null Belt and Hiza. Haramaki +2.
--
-- LandSandBoat ships no item_mods rows for these three items (they are not in its
-- item_basic/item_mods tables), but the client catalogue has them and players can wear
-- them.  The gear page's Set totals read the client's own tooltip, while the live stat
-- sheet, the passive tick and combat read item_mods; a missing row therefore looks like
-- a piece with no stats.  On Onedough's MNK idle set the visible symptom was
-- Regen 19 in Set totals against Regen 13 in Live set stats, with Null Masque's
-- Refresh+1 and Regain+2 missing as well (Null Masque 3 + Null Belt 3 = the six Regen).
--
-- Values are the client's English tooltips, cross-checked against the wiki:
--   Null Masque      DEF:138 HP+100 MP+70 STR+28 DEX+28 VIT+50 AGI+28 INT+28 MND+50
--                    CHR+28 Accuracy+50 Magic Accuracy+50 Evasion+100 Magic Evasion+100
--                    "Magic Def. Bonus"+8 Haste10% "Regen"+3 "Refresh"+1 "Regain"+2
--                    Damage taken-10%
--   Null Belt        Accuracy+30 Ranged Accuracy+30 Magic Accuracy+30 Evasion+30
--                    Magic Evasion+30 "Magic Def. Bonus"+3 "Regen"+3
--   Hiza. Haramaki +2 DEF:141 HP+100 STR+40 DEX+36 VIT+34 AGI+28 INT+20 MND+17 CHR+28
--                    Accuracy+46 Attack+28 Evasion+95 Magic Evasion+69
--                    "Magic Def. Bonus"+6 Haste+4% "Regen"+12
--
-- The same parser gap dropped "Regain" from the reforged snapshot: Wakido Kabuto +4's
-- tooltip has "Regain"+4, but migration 92 has no 368 row for it.  Put it back here so
-- the item feeds the passive tick like Karieyh Ring +1 does.
--
-- Hiza. Haramaki +2's "Set: Enhances Counter effect" is conditional on the other
-- Hizamaru pieces and is not modelled, so it is deliberately absent here.  The Null
-- Masque tooltip really does print "Haste10%" without a plus; the value is 10%.

INSERT OR REPLACE INTO item_mods (item_id, mod_id, value) VALUES
 -- Null Masque (head, 24270)
 (24270, 1, 138),      -- DEF
 (24270, 2, 100),      -- HP
 (24270, 5, 70),       -- MP
 (24270, 8, 28),       -- STR
 (24270, 9, 28),       -- DEX
 (24270, 10, 50),      -- VIT
 (24270, 11, 28),      -- AGI
 (24270, 12, 28),      -- INT
 (24270, 13, 50),      -- MND
 (24270, 14, 28),      -- CHR
 (24270, 25, 50),      -- Accuracy
 (24270, 29, 8),       -- "Magic Def. Bonus"
 (24270, 30, 50),      -- Magic Accuracy
 (24270, 31, 100),     -- Magic Evasion
 (24270, 68, 100),     -- Evasion
 (24270, 160, -1000),  -- Damage taken-10%
 (24270, 368, 2),      -- "Regain"
 (24270, 369, 1),      -- "Refresh"
 (24270, 370, 3),      -- "Regen"
 (24270, 384, 1000),   -- Haste+10%
 -- Null Belt (waist, 26367)
 (26367, 25, 30),      -- Accuracy
 (26367, 26, 30),      -- Ranged Accuracy
 (26367, 29, 3),       -- "Magic Def. Bonus"
 (26367, 30, 30),      -- Magic Accuracy
 (26367, 31, 30),      -- Magic Evasion
 (26367, 68, 30),      -- Evasion
 (26367, 370, 3),      -- "Regen"
 -- Hiza. Haramaki +2 (body, 25792)
 (25792, 1, 141),      -- DEF
 (25792, 2, 100),      -- HP
 (25792, 8, 40),       -- STR
 (25792, 9, 36),       -- DEX
 (25792, 10, 34),      -- VIT
 (25792, 11, 28),      -- AGI
 (25792, 12, 20),      -- INT
 (25792, 13, 17),      -- MND
 (25792, 14, 28),      -- CHR
 (25792, 23, 28),      -- Attack
 (25792, 25, 46),      -- Accuracy
 (25792, 29, 6),       -- "Magic Def. Bonus"
 (25792, 31, 69),      -- Magic Evasion
 (25792, 68, 95),      -- Evasion
 (25792, 370, 12),     -- "Regen"
 (25792, 384, 400),    -- Haste+4%
 -- Wakido Kabuto +4 (head, 23906)
 (23906, 368, 4);      -- "Regain"+4, dropped by the migration-92 description parser
