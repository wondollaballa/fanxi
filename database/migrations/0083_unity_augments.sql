-- Unity +1 gear augments (migration 83).
--
-- Unity Wanted iLvl 119+ equipment is augmented at a Unity NPC.  The client
-- stores the result in the same 24-byte AugmentBundle block Odyssey uses, at
-- Rank 15 and max-rank tier 0 (the 15-rank unlock), one path.  The bundle index
-- selects the item's row in the client's augment table; the rows below are the
-- Rank 15 lines from the GearSwap libraries and the item pages.
--
-- Generated from server/fanxi_server/game/unity.py by tools/gen_unity.py.

-- 27509 Unmoving Collar +1: DEF+30 / HP+200 (bundle 305)
-- 27549 Odnowa Earring +1: DEF+30 / Damage taken-3% (bundle 367)
-- 10769 Gelatinous Ring +1: VIT+15 / HP+100 (bundle 316)
-- 21344 Ghastly Tathlum +1: Magic Damage +10 / INT+5 (bundle 343)
-- 25636 Loess Barbuta +1: Enmity+10 / Damage taken-10% / All Attr.+10 (bundle 376)
-- 25602 Blistering Sallet +1: Accuracy/Magic Accuracy +45 / Critical Hit Rate +10% / STR/DEX +25 (bundle 359)
-- 21419 Rigorous Grip +1: Attack +30 / STR +15 (bundle 327)
-- 28430 Acuity Belt +1: Magic Accuracy +15 / INT +10 (bundle 295)
-- 27561 Apeile Ring +1: DEF +20 / Magic Defense Bonus +5 (bundle 310)
-- 28487 Arete del Luna +1: Resist Sleep +15 / Resist Charm +15 (bundle 302)
-- 27620 Aurist's Cape +1: Accuracy/Magic Accuracy +25 / INT/MND +25 (bundle 363)
-- 27518 Bathy Choker +1: Evasion +15 / Counter +10 (bundle 350)
-- 10771 Cacoethic Ring +1: DEX +10 / AGI +10 (bundle 358)
-- 28353 Canto Necklace +1: Magic Accuracy +15 / CHR +10 (bundle 296)
-- 27543 Domin. Earring +1: Accuracy +10 / DEX +6 (bundle 374)
-- 27610 Fi Follet Cape +1: Fast Cast +10% / Spell Interruption Rate -5% (bundle 360)
-- 27602 Ground. Mantle +1: Accuracy +15 / DEX +10 (bundle 320)
-- 28491 Handler's Earring +1: Pet: Accuracy/Magic Accuracy +15 / Accuracy +10 (bundle 298)
-- 28413 Kentarch Belt +1: STR+10 / DEX+10 (bundle 355)
-- 26002 Loricate Torque +1: DEF +45 / Spell Interruption Rate -5% (bundle 372)
-- 28482 Lugra Earring +1: DEF +20 / STR/DEX/VIT/INT +8 (bundle 312)
-- 27559 Mephitas's Ring +1: Conserve MP +15 / INT +5 (bundle 337)
-- 27563 Metamorph Ring +1: Magic Accuracy +10 / INT/MND/CHR +10 (bundle 306)
-- 28485 Nourishing Earring +1: Resist Silence +15 / Spell Interruption Rate -5% (bundle 290)
-- 28428 Sailfi Belt +1: STR +15 / Double Attack +5% (bundle 292)
-- 22255 Seeth. Bomblet +1: STR +10 / Haste +5% (bundle 364)
-- 28424 Shinjutsu-no-Obi +1: Conserve MP +15 / Fast Cast +5% (bundle 294)
-- 26022 Vim Torque +1: Accuracy +15 / Store TP +10 (bundle 383)
-- 27505 Warder's Charm +1: Skillchain Damage +15% / Magic Burst Bonus +10% (bundle 324)
-- 27533 Zwazo Earring +1: HP +45 / Shield Block Rate +3% (bundle 357)

UPDATE char_inventory SET extra = X'0383000000003C0031010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27509;
UPDATE char_inventory SET extra = X'0383000000003C006F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27549;
UPDATE char_inventory SET extra = X'0383000000003C003C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 10769;
UPDATE char_inventory SET extra = X'0383000000003C0057010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21344;
UPDATE char_inventory SET extra = X'0383000000003C0078010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25636;
UPDATE char_inventory SET extra = X'0383000000003C0067010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25602;
UPDATE char_inventory SET extra = X'0383000000003C0047010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21419;
UPDATE char_inventory SET extra = X'0383000000003C0027010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28430;
UPDATE char_inventory SET extra = X'0383000000003C0036010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27561;
UPDATE char_inventory SET extra = X'0383000000003C002E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28487;
UPDATE char_inventory SET extra = X'0383000000003C006B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27620;
UPDATE char_inventory SET extra = X'0383000000003C005E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27518;
UPDATE char_inventory SET extra = X'0383000000003C0066010000000000000000000000000000' WHERE character_id = 1 AND item_id = 10771;
UPDATE char_inventory SET extra = X'0383000000003C0028010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28353;
UPDATE char_inventory SET extra = X'0383000000003C0076010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27543;
UPDATE char_inventory SET extra = X'0383000000003C0068010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27610;
UPDATE char_inventory SET extra = X'0383000000003C0040010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27602;
UPDATE char_inventory SET extra = X'0383000000003C002A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28491;
UPDATE char_inventory SET extra = X'0383000000003C0063010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28413;
UPDATE char_inventory SET extra = X'0383000000003C0074010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26002;
UPDATE char_inventory SET extra = X'0383000000003C0038010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28482;
UPDATE char_inventory SET extra = X'0383000000003C0051010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27559;
UPDATE char_inventory SET extra = X'0383000000003C0032010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27563;
UPDATE char_inventory SET extra = X'0383000000003C0022010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28485;
UPDATE char_inventory SET extra = X'0383000000003C0024010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28428;
UPDATE char_inventory SET extra = X'0383000000003C006C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 22255;
UPDATE char_inventory SET extra = X'0383000000003C0026010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28424;
UPDATE char_inventory SET extra = X'0383000000003C007F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26022;
UPDATE char_inventory SET extra = X'0383000000003C0044010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27505;
UPDATE char_inventory SET extra = X'0383000000003C0065010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27533;
