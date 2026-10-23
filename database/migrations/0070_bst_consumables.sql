-- Beastmaster consumables and every Call Beast jug, for character 1.
-- Item ids and display names come from the public LSB item catalogue; the
-- server catalogue only needs name/stack/slot for command lookup and equip rules.
-- Jugs are ammo (slot_mask bit 3) and BST-only (job bit 8). Pet food and the
-- three ninjutsu tools are ordinary consumables.

INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17023,'Pet Food Theta',12,0,'',1,'Highest pet food; used by Reward.',0,0,0);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (2971,'Inoshishinofuda',99,1,'',1,'Ninjutsu tool.',0,0,0);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (2972,'Shikanofuda',99,1,'',1,'Ninjutsu tool.',0,0,0);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (2973,'Chonofuda',99,1,'',1,'Ninjutsu tool.',0,0,0);

INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17860,'Carrot Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17861,'F. Carrot Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17862,'Bug Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17863,'Qdv. Bug Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17864,'Herbal Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17865,'S. Herbal Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17866,'Carrion Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17867,'C. Carrion Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17868,'Humus',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17869,'Rich Humus',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17870,'Meat Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17871,'W. Meat Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17872,'Tree Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17873,'Scarlet Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17874,'Cng. Brain Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17875,'Rzr. Brain Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17876,'Fish Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17877,'Fish Oil Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17878,'L. Carrot Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17879,'C. Plasma Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17880,'Seedbed Soil',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17881,'Deepbed Soil',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17882,'Alchemist Water',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17883,'Mlw. Bird Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17884,'Sun Water',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17885,'Grass. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17886,'N. Grass. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17887,'Mole Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17888,'L. Mole Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17889,'Blood Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17890,'C. Blood Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17891,'Antica Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17892,'F. Antica Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17893,'Wool Grease',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17894,'Vermihumus',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17895,'D. Herbal Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17896,'Gob. Bug Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17897,'Bub. Carrion Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17898,'C. Grass. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17899,'Svg. Mole Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17900,'Cl. Wheat Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17901,'Bur. Carrion Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17902,'Lucky Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17903,'Shadowy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17904,'Briny Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17905,'Wormy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17906,'Auroral Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17907,'Swirling Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17908,'Shimmering Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17909,'Spicy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17911,'Salubrious Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17912,'Fizzy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17913,'Saline Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17914,'Wispy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17915,'Vis. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17916,'Ferm. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17917,'Bubbly Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17918,'Windy Greens',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17919,'Tant. Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17920,'Meaty Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17921,'Muddy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (17922,'Blackwater Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21438,'Poisonous Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21439,'Venomous Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21440,'Sugary Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21441,'Glazed Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21442,'Sticky Webbing',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21443,'Slimy Webbing',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21444,'Livid Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21445,'Lyrical Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21446,'Airy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21447,'Crumbly Soil',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21448,'Pale Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21449,'Dire Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21450,'Electrified Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21451,'Bug-ridden Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21464,'Rancid Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21465,'Pungent Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21466,'Frizzante Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21467,'Spumante Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21468,'Zestful Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21469,'Gassy Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21470,'Decaying Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21471,'Putrescent Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21472,'Turpid Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21473,'Feculent Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21488,'Pristine Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21489,'T. Pristine Sap',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21490,'Aged Humus',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21492,'Insipid Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21493,'Deepwater Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21494,'Wetlands Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21495,'Heavenly Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21496,'Furious Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21497,'Rapid Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21498,'Crackling Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);
INSERT OR REPLACE INTO items (item_id,name,stack,usable,equip_slot,level,description,model,slot_mask,jobs) VALUES (21499,'Creepy Broth',12,0,'ammo',1,'Call Beast jug.',0,8,256);

-- Full stacks of the highest pet food and the three ninjutsu tools in the bags.
WITH grants(item_id,quantity,rn) AS (
    VALUES (17023,12,1),(2971,99,2),(2972,99,3),(2973,99,4)
), free AS (
    SELECT slot, ROW_NUMBER() OVER (ORDER BY slot) AS rn
    FROM (WITH RECURSIVE nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 80)
          SELECT n AS slot FROM nums)
    WHERE slot NOT IN (SELECT slot FROM char_inventory WHERE character_id = 1 AND container = 0)
)
INSERT INTO char_inventory (character_id, container, slot, item_id, quantity)
SELECT 1, 0, free.slot, grants.item_id, grants.quantity
FROM grants JOIN free ON free.rn = grants.rn
WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1);

-- 99 of every jug (eight stacks plus three) in the hidden locker. 97 jugs x 99 = 9603.
WITH jugs(item_id) AS (
    VALUES (17860),
        (17861),
        (17862),
        (17863),
        (17864),
        (17865),
        (17866),
        (17867),
        (17868),
        (17869),
        (17870),
        (17871),
        (17872),
        (17873),
        (17874),
        (17875),
        (17876),
        (17877),
        (17878),
        (17879),
        (17880),
        (17881),
        (17882),
        (17883),
        (17884),
        (17885),
        (17886),
        (17887),
        (17888),
        (17889),
        (17890),
        (17891),
        (17892),
        (17893),
        (17894),
        (17895),
        (17896),
        (17897),
        (17898),
        (17899),
        (17900),
        (17901),
        (17902),
        (17903),
        (17904),
        (17905),
        (17906),
        (17907),
        (17908),
        (17909),
        (17911),
        (17912),
        (17913),
        (17914),
        (17915),
        (17916),
        (17917),
        (17918),
        (17919),
        (17920),
        (17921),
        (17922),
        (21438),
        (21439),
        (21440),
        (21441),
        (21442),
        (21443),
        (21444),
        (21445),
        (21446),
        (21447),
        (21448),
        (21449),
        (21450),
        (21451),
        (21464),
        (21465),
        (21466),
        (21467),
        (21468),
        (21469),
        (21470),
        (21471),
        (21472),
        (21473),
        (21488),
        (21489),
        (21490),
        (21492),
        (21493),
        (21494),
        (21495),
        (21496),
        (21497),
        (21498),
        (21499)
)
INSERT INTO char_locker (character_id, item_id, quantity)
SELECT 1, item_id, 99 FROM jugs
WHERE EXISTS (SELECT 1 FROM characters WHERE id = 1)
ON CONFLICT(character_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity;
