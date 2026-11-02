-- Unity +1 gear augments (migration 83).
--
-- Unity Wanted iLvl 119+ equipment is augmented at a Unity NPC.  The client
-- stores the result in the same 24-byte AugmentBundle block Odyssey uses, at
-- Rank 15 and max-rank tier 0 (the 15-rank unlock), one path.  The bundle index
-- selects the item's row in the client's augment table; every Unity piece is one
-- of bundles 285-392, and the rows below are the Rank 15 lines from the item pages.
--
-- Generated from data/unity_r15.json by tools/gen_unity.py.

-- 27509 Unmoving Collar +1: DEF+30 / HP+200 (bundle 305)
-- 27549 Odnowa Earring +1: DEF+30 / Damage taken-3% (bundle 367)
-- 10769 Gelatinous Ring +1: VIT+15 / HP+100 (bundle 316)
-- 21344 Ghastly Tathlum +1: Magic Damage +10 / INT+5 (bundle 343)
-- 25636 Loess Barbuta +1: Enmity+10 / Damage taken-10% / All Attr.+10 (bundle 376)
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
-- 26715 Adorned Helm +1: Accuracy/Magic Accuracy +45 / Attack +50 / All Attr. +10 (bundle 325)
-- 26943 Agony Jerkin +1: Attack +60 / "Store TP" +10 / All Attr. +10 (bundle 314)
-- 26787 Alhazen Hat +1: All Attr. +30 / Evasion +50 / Accuracy/Ranged Accuracy/Magic Accuracy +25 (bundle 345)
-- 28135 Assid. Pants +1: Avatar: Accuracy/Magic Accuracy +35 / Avatar: All Attr. +20 / MP +20 (bundle 289)
-- 27107 Asteria Mitts +1: MP +45 / Avatar: Accuracy/Magic Accuracy +40 / Avatar: Magic Burst Bonus +10% (bundle 352)
-- 28137 Augury Cuisses +1: Attack +60 / Magic Attack Bonus +30 / All Attr. +10 (bundle 291)
-- 25602 Blistering Sallet +1: Accuracy/Magic Accuracy +45 / Critical Hit Rate +10% / STR/DEX +25 (bundle 359)
-- 25681 Cohort Cloak +1: Magic Accuracy +100 / Magic Attack Bonus +100 / All Attr. +20 (bundle 354)
-- 26871 Emet Harness +1: Evasion +30 / Accuracy +40 / All Attr. +10 (bundle 323)
-- 27151 Gazu Bracelets +1: Accuracy +50 / Haste +10% / All Attr. +10 (bundle 366)
-- 26785 Hike Khat +1: Physical Damage Taken -10% / Pet: Damage Taken -5% / All Attr. +10 (bundle 341)
-- 26873 Hime Domaru +1: Accuracy +45 / "Double Attack" +5% / All Attr. +10 (bundle 326)
-- 27410 Hippomenes Socks +1: "Resist Bind" +45 / Evasion +20 / All Attr. +10 (bundle 309)
-- 27408 Hygieia Clogs +1: "Cure" Potency +15% / Healing Magic Skill +10 / All Attr. +10 (bundle 335)
-- 26710 Imp. Wing Hair. +1: Accuracy +35 / Magic Evasion +100 / Critical Hit Rate +10% (bundle 286)
-- 28276 Jute Boots +1: DEX/AGI +15 / Magic Evasion +30 / All Attr. +10 (bundle 317)
-- 27051 Kachi. Kote +1: Attack +45 / Accuracy/Magic Accuracy +30 / All Attr. +10 (bundle 331)
-- 27109 Lamassu Mitts +1: Avatar: All Attr. +30 / Avatar: Accuracy/Magic Accuracy +40 / Avatar Perpetuation Cost -5 (bundle 353)
-- 26897 Lugra Cloak +1: Magic Accuracy +60 / Spell Interruption Rate -20% / All Attr. +20 (bundle 311)
-- 27994 Macabre Gaunt. +1: Magic Evasion +75 / Occasionally Resist Status Ailments +10 / All Attr. +10 (bundle 287)
-- 25710 Obviat. Cuirass +1: Magic Evasion+60 / Enmity+5 / All Attr. +10 (bundle 380)
-- 28274 Regal Pumps +1: Healing Magic Skill +10 / Enhancing Magic Skill +10 / All Attr. +10 (bundle 285)
-- 26869 Ros. Jaseran +1: Magic Accuracy +45 / Damage Taken -5% / All Attr. +10 (bundle 304)
-- 27996 Shigure Tekko +1: Evasion +90 / Magic Evasion +80 / All Attr. +10 (bundle 297)
-- 26888 Shomonjijoe +1: Avatar: TP Bonus +300 / Avatar: Accuracy/Magic Accuracy +30 / Avatar: All Attr. +10 (bundle 328)
-- 26732 Stinger Helm +1: Accuracy/Magic Accuracy +30 / Physical Damage Limit +5% / All Attr. +10 (bundle 329)
-- 27149 Tatena. Gote +1: Accuracy+40 / All Attr.+10 / "Triple Attack" +4% (bundle 389)
-- 25856 Tatena. Haidate +1: Accuracy+60 / All Attr.+10 / "Triple Attack" +3% (bundle 382)
-- 25733 Tatena. Harama. +1: Accuracy+30 / All Attr.+10 / "Triple Attack" +5% (bundle 392)
-- 25924 Tatena. Sune. +1: Accuracy+60 / All Attr.+10 / "Triple Attack" +3% (bundle 386)
-- 27231 Zoar Subligar +1: Accuracy +30 / Critical Hit Rate +5% / All Attr. +10 (bundle 308)
-- 21165 Ababinili +1: Healing Magic Skill +10 / Enhancing Magic Skill +10 / Damage Taken -10% (bundle 321)
-- 20852 Aizkora +1: Accuracy/Magic Accuracy +45 / "Triple Attack" +3% / "Quadruple Attack" +3% (bundle 344)
-- 27639 Ajax +1: Shield Block Rate +10% / Enhancing Magic Received Duration +10% (bundle 339)
-- 20607 Anathema Harpe +1: DMG +20 / Accuracy/Magic Accuracy +40 / Critical Hit Rate +10% (bundle 330)
-- 22267 Antitail +1: Magic Evasion+15 / "Double Attack"+3 (bundle 373)
-- 20854 Beheader +1: DMG +53 / Accuracy/Magic Accuracy +40 / Haste +10% (bundle 347)
-- 20807 Buramgh +1: DMG +30 / Pet: Accuracy/Magic Accuracy +30 / Accuracy/Magic Accuracy +35 (bundle 299)
-- 20697 Combuster +1: DMG:+19 / Accuracy/Magic Accuracy +40 / "Store TP"+10 (bundle 377)
-- 20508 Comeuppances +1: DEX+20 / Accuracy/Magic Accuracy +40 / "Store TP"+10 / Pet: Accuracy/Magic Accuracy +40 (bundle 390)
-- 22058 Contemplator +1: Magic Accuracy +70 / Enfeebling Magic Skill +20 / MND +10 (bundle 391)
-- 27641 Deliverance +1: Accuracy/Magic Accuracy +30 / Shield Skill +10 (bundle 348)
-- 20709 Demers. Degen +1: Accuracy/Magic Accuracy +45 / DEX +10 / Sword Enhancement Spell Damage +50% (bundle 351)
-- 20522 Emeici +1: DMG +30 / Accuracy/Magic Accuracy +30 / Critical Hit Rate +10% (bundle 315)
-- 27637 Evalach +1: HP +150 / Shield Skill +10 / Accuracy/Magic Accuracy +20 (bundle 300)
-- 20528 Fists of Fury +1: DMG +14 / Accuracy/Magic Accuracy +40 / "Regen" +5 (bundle 346)
-- 20682 Flyssa +1: DMG:+10 / Accuracy/Magic Accuracy +40 / Damage taken -5% (bundle 387)
-- 26402 Forfend +1: Accuracy+15 / Magic Accuracy+15 / Enhancing Magic Skill +10 (bundle 379)
-- 20943 Gae Derg +1: DMG +62 / Accuracy/Magic Accuracy +40 / "Store TP" +8 (bundle 338)
-- 21749 Habilitator +1: DMG:+21 / Accuracy/Magic Accuracy +40 / STR/DEX/CHR+10 / Pet: Accuracy/Magic Accuracy +40 (bundle 381)
-- 22121 Imati +1: DMG +17 / Ranged Accuracy +40 / "Snapshot" +10% (bundle 371)
-- 20609 Jugo Kukri +1: DMG +13 / Accuracy/Magic Accuracy +40 / Evasion +20 (bundle 332)
-- 21703 Kladenets +1: DMG +50 / Accuracy/Magic Accuracy +40 / "Fast Cast" +10% (bundle 342)
-- 21035 Kunimune +1: TP Bonus +500 / Accuracy/Magic Accuracy +30 / STR +10 (bundle 307)
-- 20581 Kustawi +1: Ranged Attack +20 / Ranged Accuracy/Magic Accuracy +40 / Enmity -5 (bundle 368)
-- 21091 Loxotic Mace +1: DMG +33 / Accuracy/Magic Accuracy +40 / Weapon Skill Damage +10% (bundle 365)
-- 21100 Magesmasher +1: DMG +45 / Accuracy/Magic Accuracy +30 / Weapon Skill Damage +15% (bundle 318)
-- 21484 Malison +1: Ranged Attack+45 / Ranged Accuracy/Magic Accuracy +40 / DMG:+5 (bundle 378)
-- 21160 Marin Staff +1: Magic Attack Bonus +40 / Accuracy/Magic Accuracy +40 / INT/MND +10 (bundle 333)
-- 20800 Mdomo Axe +1: DMG +24 / Accuracy/Magic Accuracy +40 / Pet: Accuracy/Magic Accuracy +50 (bundle 356)
-- 21223 Mengado +1: "Snapshot" +15 / DMG +10 / Ranged Accuracy +20 (bundle 301)
-- 21689 Montante +1: DMG:+20 / Accuracy/Magic Accuracy +40 / HP+100 (bundle 385)
-- 21030 Norifusa +1: DMG +10 / Accuracy/Magic Accuracy +40 / Skillchain Damage +20% (bundle 362)
-- 21696 Nullis +1: DMG:+33 / Accuracy/Magic Accuracy +40 / Dark magic skill +10 (bundle 375)
-- 21220 Paloma Bow +1: DMG +9 / Ranged Accuracy +40 / "Rapid Shot" +15% (bundle 349)
-- 20805 Perun +1: Ranged Attack +45 / Ranged Accuracy/Magic Accuracy +30 / "Snapshot" +5% (bundle 340)
-- 21806 Pixquizpan +1: DMG +36 / Accuracy/Magic Accuracy +40 / Magic Attack Bonus +50 (bundle 370)
-- 21163 Pouwhenua +1: DMG +45 / Accuracy/Magic Accuracy +30 / "Store TP" +10 (bundle 303)
-- 20614 Pukulatmuj +1: DMG +38 / Accuracy/Magic Accuracy +30 / Sword Enhancement Spell Damage +150% (bundle 322)
-- 20981 Raicho +1: DMG +20 / Accuracy/Magic Accuracy +40 / Magic Defense Bonus +5 (bundle 361)
-- 21417 Refined Grip +1: DEF +20 / Parrying Skill +10 (bundle 313)
-- 21419 Rigorous Grip +1: Attack +30 / STR +15 (bundle 327)
-- 20612 Sangarius +1: DMG +35 / Accuracy/Magic Accuracy +30 / "Quadruple Attack" +3% (bundle 319)
-- 21076 Septoptic +1: DMG:+10 / Accuracy/Magic Accuracy +40 / Magic Attack Bonus +30 (bundle 388)
-- 20988 Tancho +1: DMG +25 / Accuracy/Ranged Accuracy/Magic Accuracy +20 / Magic Attack Bonus +20 (bundle 293)
-- 20680 Tanmogayi +1: DMG+11 / Accuracy/Magic Accuracy +40 / Attack+40 (bundle 384)
-- 20604 Ternion Dagger +1: DMG +17 / Accuracy/Magic Accuracy +40 / Weapon Skill Damage +5% (bundle 336)
-- 20899 Triska Scythe +1: DMG +56 / Accuracy/Magic Accuracy +40 / Critical Hit Rate +10% (bundle 334)
-- 21691 Ushenzi +1: DMG +28 / Accuracy/Magic Accuracy +40 / "Cure" Potency Received +10% (bundle 369)
-- 21350 Wingcutter +1: Accuracy +10 / Evasion +10 (bundle 288)

UPDATE char_inventory SET extra = X'0383000000003C0031010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27509;
UPDATE char_inventory SET extra = X'0383000000003C006F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27549;
UPDATE char_inventory SET extra = X'0383000000003C003C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 10769;
UPDATE char_inventory SET extra = X'0383000000003C0057010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21344;
UPDATE char_inventory SET extra = X'0383000000003C0078010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25636;
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
UPDATE char_inventory SET extra = X'0383000000003C0045010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26715;
UPDATE char_inventory SET extra = X'0383000000003C003A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26943;
UPDATE char_inventory SET extra = X'0383000000003C0059010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26787;
UPDATE char_inventory SET extra = X'0383000000003C0021010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28135;
UPDATE char_inventory SET extra = X'0383000000003C0060010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27107;
UPDATE char_inventory SET extra = X'0383000000003C0023010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28137;
UPDATE char_inventory SET extra = X'0383000000003C0067010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25602;
UPDATE char_inventory SET extra = X'0383000000003C0062010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25681;
UPDATE char_inventory SET extra = X'0383000000003C0043010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26871;
UPDATE char_inventory SET extra = X'0383000000003C006E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27151;
UPDATE char_inventory SET extra = X'0383000000003C0055010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26785;
UPDATE char_inventory SET extra = X'0383000000003C0046010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26873;
UPDATE char_inventory SET extra = X'0383000000003C0035010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27410;
UPDATE char_inventory SET extra = X'0383000000003C004F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27408;
UPDATE char_inventory SET extra = X'0383000000003C001E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26710;
UPDATE char_inventory SET extra = X'0383000000003C003D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28276;
UPDATE char_inventory SET extra = X'0383000000003C004B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27051;
UPDATE char_inventory SET extra = X'0383000000003C0061010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27109;
UPDATE char_inventory SET extra = X'0383000000003C0037010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26897;
UPDATE char_inventory SET extra = X'0383000000003C001F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27994;
UPDATE char_inventory SET extra = X'0383000000003C007C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25710;
UPDATE char_inventory SET extra = X'0383000000003C001D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 28274;
UPDATE char_inventory SET extra = X'0383000000003C0030010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26869;
UPDATE char_inventory SET extra = X'0383000000003C0029010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27996;
UPDATE char_inventory SET extra = X'0383000000003C0048010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26888;
UPDATE char_inventory SET extra = X'0383000000003C0049010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26732;
UPDATE char_inventory SET extra = X'0383000000003C0085010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27149;
UPDATE char_inventory SET extra = X'0383000000003C007E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25856;
UPDATE char_inventory SET extra = X'0383000000003C0088010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25733;
UPDATE char_inventory SET extra = X'0383000000003C0082010000000000000000000000000000' WHERE character_id = 1 AND item_id = 25924;
UPDATE char_inventory SET extra = X'0383000000003C0034010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27231;
UPDATE char_inventory SET extra = X'0383000000003C0041010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21165;
UPDATE char_inventory SET extra = X'0383000000003C0058010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20852;
UPDATE char_inventory SET extra = X'0383000000003C0053010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27639;
UPDATE char_inventory SET extra = X'0383000000003C004A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20607;
UPDATE char_inventory SET extra = X'0383000000003C0075010000000000000000000000000000' WHERE character_id = 1 AND item_id = 22267;
UPDATE char_inventory SET extra = X'0383000000003C005B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20854;
UPDATE char_inventory SET extra = X'0383000000003C002B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20807;
UPDATE char_inventory SET extra = X'0383000000003C0079010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20697;
UPDATE char_inventory SET extra = X'0383000000003C0086010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20508;
UPDATE char_inventory SET extra = X'0383000000003C0087010000000000000000000000000000' WHERE character_id = 1 AND item_id = 22058;
UPDATE char_inventory SET extra = X'0383000000003C005C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27641;
UPDATE char_inventory SET extra = X'0383000000003C005F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20709;
UPDATE char_inventory SET extra = X'0383000000003C003B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20522;
UPDATE char_inventory SET extra = X'0383000000003C002C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 27637;
UPDATE char_inventory SET extra = X'0383000000003C005A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20528;
UPDATE char_inventory SET extra = X'0383000000003C0083010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20682;
UPDATE char_inventory SET extra = X'0383000000003C007B010000000000000000000000000000' WHERE character_id = 1 AND item_id = 26402;
UPDATE char_inventory SET extra = X'0383000000003C0052010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20943;
UPDATE char_inventory SET extra = X'0383000000003C007D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21749;
UPDATE char_inventory SET extra = X'0383000000003C0073010000000000000000000000000000' WHERE character_id = 1 AND item_id = 22121;
UPDATE char_inventory SET extra = X'0383000000003C004C010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20609;
UPDATE char_inventory SET extra = X'0383000000003C0056010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21703;
UPDATE char_inventory SET extra = X'0383000000003C0033010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21035;
UPDATE char_inventory SET extra = X'0383000000003C0070010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20581;
UPDATE char_inventory SET extra = X'0383000000003C006D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21091;
UPDATE char_inventory SET extra = X'0383000000003C003E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21100;
UPDATE char_inventory SET extra = X'0383000000003C007A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21484;
UPDATE char_inventory SET extra = X'0383000000003C004D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21160;
UPDATE char_inventory SET extra = X'0383000000003C0064010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20800;
UPDATE char_inventory SET extra = X'0383000000003C002D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21223;
UPDATE char_inventory SET extra = X'0383000000003C0081010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21689;
UPDATE char_inventory SET extra = X'0383000000003C006A010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21030;
UPDATE char_inventory SET extra = X'0383000000003C0077010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21696;
UPDATE char_inventory SET extra = X'0383000000003C005D010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21220;
UPDATE char_inventory SET extra = X'0383000000003C0054010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20805;
UPDATE char_inventory SET extra = X'0383000000003C0072010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21806;
UPDATE char_inventory SET extra = X'0383000000003C002F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21163;
UPDATE char_inventory SET extra = X'0383000000003C0042010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20614;
UPDATE char_inventory SET extra = X'0383000000003C0069010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20981;
UPDATE char_inventory SET extra = X'0383000000003C0039010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21417;
UPDATE char_inventory SET extra = X'0383000000003C0047010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21419;
UPDATE char_inventory SET extra = X'0383000000003C003F010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20612;
UPDATE char_inventory SET extra = X'0383000000003C0084010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21076;
UPDATE char_inventory SET extra = X'0383000000003C0025010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20988;
UPDATE char_inventory SET extra = X'0383000000003C0080010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20680;
UPDATE char_inventory SET extra = X'0383000000003C0050010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20604;
UPDATE char_inventory SET extra = X'0383000000003C004E010000000000000000000000000000' WHERE character_id = 1 AND item_id = 20899;
UPDATE char_inventory SET extra = X'0383000000003C0071010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21691;
UPDATE char_inventory SET extra = X'0383000000003C0020010000000000000000000000000000' WHERE character_id = 1 AND item_id = 21350;
