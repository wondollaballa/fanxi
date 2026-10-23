--[[
    Fanxi mock GearSwap set library — Dragoon (DRG)
    polearm two-hander, jumps, wyvern

    Import : Launcher -> Gear -> Import GearSwap file... -> DRG.lua
    Wear   : select a set, then "Wear set". Items must be in bags 0-17.
    Save   : "Save profile" writes JSON under the launcher's gearswap folder.

    This file is a static set library: no includes, no windower/player calls,
    no rules.  Fanxi's importer runs get_sets() in a Lua 5.1 sandbox and shows
    every set below.  Each set is a leaf table of slot -> item, because
    the launcher flattens a table that contains slot keys as one set and stops
    descending; groups such as sets.idle are left empty on purpose.

    Requested categories:
      max HP     -> sets.idle.maxhp
      max PDT    -> sets.idle.pdt   (sets.idle.mdt for magic)
      TP         -> sets.engaged.tp
      TP + DT    -> sets.engaged.hybrid
      Weaponskill-> sets.WS.*
      Abilities  -> sets.JA.*
      Pet        -> sets.wyvern.*

    Gear follows retail names: iLvl 119 reforged AF/relic/empyrean, Nyame,
    Sakpata's, JSE necks/capes and Odyssey/Limbus accessories, plus a few older
    all-jobs staples (Rajas Ring, Windbuffet Belt +1, Pole Grip).  The generic
    pieces were checked against the wiki's per-job access lists.  The item
    tables below add the job's JSE cape builds, the five Unity items' fixed
    augments, and Nyame, Sakpata's, Gleti's and Agwu's Rank 30 Odyssey augments.  The import
    itself does not need the items to exist.
]]

-- combine() is provided for extending a set without repeating it:
--   sets.idle.regen = combine(sets.idle.dt, { waist = "Windbuffet Belt +1" })
local function combine(base, extra)
    local out = {}
    for key, value in pairs(base or {}) do out[key] = value end
    for key, value in pairs(extra or {}) do out[key] = value end
    return out
end

-- JSE cape builds. The same base cape is reused with different
-- Ambuscade augments; GearSwap matches the augment list on equip.
local capes = {
    pdt = { name = "Brigantia's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    mdt = { name = "Brigantia's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Mag. Evasion+10", "Enmity-10", "Magic dmg. taken-10%"} },
    maxhp = { name = "Brigantia's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "HP+20", "Enmity-10", "Damage taken-5%"} },
    dt = { name = "Brigantia's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Damage taken-5%"} },
    tp = { name = "Brigantia's Mantle", augments = {"DEX+20", "Accuracy+20 Attack+20", "Accuracy+10", '"Store TP"+10', "Phys. dmg. taken-10%"} },
    ws_str = { name = "Brigantia's Mantle", augments = {"STR+20", "Accuracy+20 Attack+20", "STR+10", "Weapon skill damage +10%", "Damage taken-5%"} },
    ws_dex = { name = "Brigantia's Mantle", augments = {"DEX+20", "Accuracy+20 Attack+20", "DEX+10", "Weapon skill damage +10%", "Damage taken-5%"} },
    pet_mab = { name = "Brigantia's Mantle", augments = {"Pet: M.Acc.+20 Pet: M.Dmg.+20", "Mag. Acc+20 /Mag. Dmg.+20", "Pet: Mag. Acc.+10", "Pet: Haste+10", "Pet: Damage taken -5%"} },
    pet_dt = { name = "Brigantia's Mantle", augments = {"Pet: M.Acc.+20 Pet: M.Dmg.+20", "Pet: Accuracy+20", "Pet: Mag. Acc.+10", "Pet: Haste+10", "Pet: Damage taken -5%"} },
}

-- Unity accessories: fixed max-rank Odyssey augments.
local unity = {
    collar = { name = "Unmoving Collar +1", augments = {"DEF+30", "HP+200"} },
    odnowa = { name = "Odnowa Earring +1", augments = {"DEF+30", "Damage taken-3%"} },
    ring = { name = "Gelatinous Ring +1", augments = {"VIT+15", "HP+100"} },
    tathlum = { name = "Ghastly Tathlum +1", augments = {"Magic Damage +10", "INT+5"} },
    loess = { name = "Loess Barbuta +1", augments = {"Enmity+10", "Damage taken-10%", "All Attr.+10"} },
}

-- Odyssey Rank 30 builds: every Odyssey armour piece and weapon at Rank 30.
-- Nyame has four paths (A accuracy/TP, B physical WS, C magic, D pet);
-- Sakpata's, Gleti's and Agwu's each have one Rank 30 row.
-- Generated from data/odyssey_r30.json by tools/gen_odyssey_r30.py.
local odyssey = {
    A = {
        helm = { name = "Nyame Helm", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +5%", "Crit.hit rate+10%"} },
        mail = { name = "Nyame Mail", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+15", "Phys. dmg. limit +7%", "DEX/AGI+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+14", "Phys. dmg. limit +5%", "DEX+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +6%", "Crit.hit rate+13%"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +5%", "AGI+15"} },
    },
    B = {
        helm = { name = "Nyame Helm", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Dbl.Atk."+5%', "Acc.+10 Rng. Acc.+10"} },
        mail = { name = "Nyame Mail", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +13%", '"Double Attack"+7%', "STR/VIT+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Double Attack"+5%', "VIT+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +12%", '"Double Attack"+6%', "STR+15"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Double Attack"+5%', "Acc+13 Rng. Acc+13"} },
    },
    C = {
        helm = { name = "Nyame Helm", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +6", "Mag. Acc.+10"} },
        mail = { name = "Nyame Mail", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+40", "Magic burst damage II +7", "INT/MND/CHR+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +5", "MND+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+35", "Magic burst damage II +5", "INT+15"} },
        sollerets = { name = "Nyame Sollerets", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +5", "CHR+15"} },
    },
    D = {
        helm = { name = "Nyame Helm", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
        mail = { name = "Nyame Mail", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: DMG+11%", "Pet: Damage taken -10%"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: DMG+10%", "Pet: Damage taken -9%"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
    },
    sakpata = {
        helm = { name = "Sakpata's Helm", augments = {"Attack+30", '"Double Attack" damage +15%', "Accuracy+15 Mag. Acc+15", '"Cure" potency+5%'} },
        breastplate = { name = "Sakpata's Breastplate", augments = {"Attack+30", "Occ. inc. resist. to stat. ailments+15", "Accuracy+15 Mag. Acc+15", "Crit.hit rate+5%"} },
        gauntlets = { name = "Sakpata's Gauntlets", augments = {"Attack+30", '"Store TP"+8', "Accuracy+15 Mag. Acc+15", "VIT+5"} },
        cuisses = { name = "Sakpata's Cuisses", augments = {"Attack+30", "Skillchain dmg.+15%", "Accuracy+15 Mag. Acc+15", "STR+5"} },
        leggings = { name = "Sakpata's Leggings", augments = {"Attack+30", '"Subtle Blow"+15', "Accuracy+15 Mag. Acc+15", "Chance of successful block +5"} },
    },
    gleti = {
        mask = { name = "Gleti's Mask", augments = {"Attack+30", '"Counter"+10', "Accuracy+15 Mag. Acc+15", '"Regen"+3'} },
        cuirass = { name = "Gleti's Cuirass", augments = {"Attack+30", '"Double Attack"+10%', "Accuracy+15 Mag. Acc+15", "Occ. inc. resist. to stat. ailments+10"} },
        gauntlets = { name = "Gleti's Gauntlets", augments = {"Attack+30", '"Store TP"+8', "Accuracy+15 Mag. Acc+15", "DEX+5"} },
        breeches = { name = "Gleti's Breeches", augments = {"Attack+30", '"Subtle Blow"+15', "Accuracy+15 Mag. Acc+15", '"Triple Attack"+5%'} },
        boots = { name = "Gleti's Boots", augments = {"Attack+30", "Evasion+15", "Accuracy+15 Mag. Acc+15", "STR+5"} },
    },
    agwu = {
        cap = { name = "Agwu's Cap", augments = {'"Mag.Atk.Bns."+25', "Magic Damage+15", "Accuracy+15 Mag. Acc+15", "Enmity-5"} },
        robe = { name = "Agwu's Robe", augments = {'"Mag.Atk.Bns."+25', "Enmity-8", "Accuracy+15 Mag. Acc+15", "Magic Damage+10"} },
        gages = { name = "Agwu's Gages", augments = {'"Mag.Atk.Bns."+25', "Magic burst damage II +6", "Accuracy+15 Mag. Acc+15", "MND+5"} },
        slops = { name = "Agwu's Slops", augments = {'"Mag.Atk.Bns."+25', "Damage taken-10%", "Accuracy+15 Mag. Acc+15", "INT+5"} },
        pigaches = { name = "Agwu's Pigaches", augments = {'"Mag.Atk.Bns."+25', '"Drain" and "Aspir" potency+15', "Accuracy+15 Mag. Acc+15", "Spell interruption rate down 10%"} },
    },
    weapons = {
        fists = { name = "Sakpata's Fists", augments = {"DMG:+20", "Attack+45", "Accuracy+15 Mag. Acc+15", "Skillchain dmg.+10%"} },
        sword = { name = "Sakpata's Sword", augments = {"DMG:+13", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Refresh"+3'} },
        knife = { name = "Gleti's Knife", augments = {"DMG:+11", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Subtle Blow II"+10'} },
        crossbow = { name = "Gleti's Crossbow", augments = {"DMG:+9", "Rng. Atk.+45", "Rng. Acc.+15 Mag. Acc.+15", '"Snapshot"+10'} },
        axe = { name = "Agwu's Axe", augments = {"DMG:+15", "Attack+45", "Accuracy+15 Mag. Acc+15", "Skillchain dmg.+10%"} },
        claymore = { name = "Agwu's Claymore", augments = {"DMG:+26", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Counter"+10'} },
        scythe = { name = "Agwu's Scythe", augments = {"DMG:+28", "Attack+45", "Accuracy+15 Mag. Acc+15", "Damage taken-10%"} },
    },
}

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.

-- Limbus Rank 30 builds: the top tier of all five families, one copy
-- per augment choice a set needs (TP, weaponskill, fast cast, tank).
-- Generated from data/limbus_r30.json by tools/gen_limbus_r30.py.
local limbus = {
    duty = {
        tp = {
            head = { name = "Duty Crown", augments = {'"Store TP"+7'} },
            body = { name = "Duty Cyclas", augments = {'"Store TP"+8'} },
            hands = { name = "Duty Gauntlets", augments = {'"Store TP"+6'} },
            legs = { name = "Duty Flanchard", augments = {'"Store TP"+7'} },
            feet = { name = "Duty Sollerets", augments = {'"Store TP"+6'} },
        },
        ws = {
            head = { name = "Duty Crown", augments = {"Accuracy+30 Mag. Acc+30"} },
            body = { name = "Duty Cyclas", augments = {"Accuracy+30 Mag. Acc+30"} },
            hands = { name = "Duty Gauntlets", augments = {"Accuracy+30 Mag. Acc+30"} },
            legs = { name = "Duty Flanchard", augments = {"Accuracy+30 Mag. Acc+30"} },
            feet = { name = "Duty Sollerets", augments = {"Accuracy+30 Mag. Acc+30"} },
        },
    },
    revelation = {
        tp = {
            head = { name = "Revelation Masque", augments = {'"Double Attack"+7%'} },
            body = { name = "Revelation Plate.", augments = {'"Double Attack"+8%'} },
            hands = { name = "Revelation Gaunt.", augments = {'"Double Attack"+6%'} },
            legs = { name = "Revelation Brais", augments = {'"Double Attack"+7%'} },
            feet = { name = "Revelation Sab.", augments = {'"Double Attack"+6%'} },
        },
        ws = {
            head = { name = "Revelation Masque", augments = {"Physical Damage Limit+6%"} },
            body = { name = "Revelation Plate.", augments = {"Physical Damage Limit+7%"} },
            hands = { name = "Revelation Gaunt.", augments = {"Physical Damage Limit+5%"} },
            legs = { name = "Revelation Brais", augments = {"Physical Damage Limit+6%"} },
            feet = { name = "Revelation Sab.", augments = {"Physical Damage Limit+5%"} },
        },
    },
    sworn = {
        ta = {
            head = { name = "Sworn Crown", augments = {'"Triple Attack"+6%'} },
            body = { name = "Sworn Platemail", augments = {'"Triple Attack"+8%'} },
            hands = { name = "Sworn Gauntlets", augments = {'"Triple Attack"+7%'} },
            legs = { name = "Sworn Brais", augments = {'"Triple Attack"+6%'} },
            feet = { name = "Sworn Sabatons", augments = {'"Triple Attack"+7%'} },
        },
        phalanx = {
            head = { name = "Sworn Crown", augments = {'"Phalanx" received +4'} },
            body = { name = "Sworn Platemail", augments = {'"Phalanx" received +6'} },
            hands = { name = "Sworn Gauntlets", augments = {'"Phalanx" received +5'} },
            legs = { name = "Sworn Brais", augments = {'"Phalanx" received +4'} },
            feet = { name = "Sworn Sabatons", augments = {'"Phalanx" received +5'} },
        },
        acc = {
            head = { name = "Sworn Crown", augments = {"Accuracy+30 Mag. Acc+30"} },
            body = { name = "Sworn Platemail", augments = {"Accuracy+30 Mag. Acc+30"} },
            hands = { name = "Sworn Gauntlets", augments = {"Accuracy+30 Mag. Acc+30"} },
            legs = { name = "Sworn Brais", augments = {"Accuracy+30 Mag. Acc+30"} },
            feet = { name = "Sworn Sabatons", augments = {"Accuracy+30 Mag. Acc+30"} },
        },
    },
    indomitable = {
        cast = {
            head = { name = "Indom. Petasos", augments = {'"Magic Atk. Bonus"+28'} },
            body = { name = "Indomitable Coat", augments = {'"Magic Atk. Bonus"+32'} },
            hands = { name = "Indom. Gloves", augments = {'"Magic Atk. Bonus"+30'} },
            legs = { name = "Indom. Tonban", augments = {'"Magic Atk. Bonus"+28'} },
            feet = { name = "Indom. Sabots", augments = {'"Magic Atk. Bonus"+30'} },
        },
    },
    clemency = {
        tp = {
            head = { name = "Clemen. Somen", augments = {'"Quadruple Attack"+4%'} },
            body = { name = "Clemen. Hara.", augments = {'"Quadruple Attack"+6%'} },
            hands = { name = "Clemency Kote", augments = {'"Quadruple Attack"+5%'} },
            legs = { name = "Clem. Haidate", augments = {'"Quadruple Attack"+4%'} },
            feet = { name = "Clem. Sune-Ate", augments = {'"Quadruple Attack"+5%'} },
        },
        ws = {
            head = { name = "Clemen. Somen", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            body = { name = "Clemen. Hara.", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            hands = { name = "Clemency Kote", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            legs = { name = "Clem. Haidate", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            feet = { name = "Clem. Sune-Ate", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
        },
    },
}

function get_sets()
    sets = {}

    -- ===== Odyssey Rank 30 sets =================================
    sets.Odyssey = {}  -- container: every Odyssey build this job can wear
    sets.Odyssey.nyame_a = { head = odyssey.A.helm, body = odyssey.A.mail, hands = odyssey.A.gauntlets, legs = odyssey.A.flanchard, feet = odyssey.A.sollerets }
    sets.Odyssey.nyame_b = { head = odyssey.B.helm, body = odyssey.B.mail, hands = odyssey.B.gauntlets, legs = odyssey.B.flanchard, feet = odyssey.B.sollerets }
    sets.Odyssey.nyame_c = { head = odyssey.C.helm, body = odyssey.C.mail, hands = odyssey.C.gauntlets, legs = odyssey.C.flanchard, feet = odyssey.C.sollerets }
    sets.Odyssey.nyame_d = { head = odyssey.D.helm, body = odyssey.D.mail, hands = odyssey.D.gauntlets, legs = odyssey.D.flanchard, feet = odyssey.D.sollerets }
    sets.Odyssey.gleti = { head = odyssey.gleti.mask, body = odyssey.gleti.cuirass, hands = odyssey.gleti.gauntlets, legs = odyssey.gleti.breeches, feet = odyssey.gleti.boots }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.clemency_tp = { head = limbus.clemency.tp.head, body = limbus.clemency.tp.body, hands = limbus.clemency.tp.hands, legs = limbus.clemency.tp.legs, feet = limbus.clemency.tp.feet }
    sets.Limbus.clemency_ws = { head = limbus.clemency.ws.head, body = limbus.clemency.ws.body, hands = limbus.clemency.ws.hands, legs = limbus.clemency.ws.legs, feet = limbus.clemency.ws.feet }

    -- ===== idle =================================================
    sets.idle = {}  -- container: Fanxi lists the children below
    -- town / CP / walking around
    sets.idle.town = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = unity.odnowa,
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }
    -- max physical damage taken
    sets.idle.pdt = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.pdt,
    }
    -- max magic damage taken
    sets.idle.mdt = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.mdt,
    }
    -- max HP
    sets.idle.maxhp = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = "Dragoon's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.maxhp,
    }
    -- balanced damage taken with job pieces
    sets.idle.dt = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Vishap Armet +4",
        body = "Peltast's Plackart +3",
        hands = "Pteroslaver Finger Gauntlets +4",
        legs = "Pteroslaver Brais +4",
        feet = "Vishap Greaves +4",
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.dt,
    }
    -- movement speed + town
    sets.idle.movement = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Carmine Cuisses +1",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = unity.odnowa,
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== engaged =================================================
    sets.engaged = {}  -- container: TP variants below
    -- main TP set
    sets.engaged.tp = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = limbus.clemency.tp.head,
        body = "Peltast's Plackart +3",
        hands = "Pteroslaver Finger Gauntlets +4",
        legs = "Pteroslaver Brais +4",
        feet = limbus.clemency.tp.feet,
        neck = "Dragoon's Collar +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = capes.tp,
    }
    -- accuracy-first TP
    sets.engaged.acc = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = "Combatant's Torque",
        waist = "Windbuffet Belt +1",
        ear1 = "Telos Earring",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = capes.tp,
    }
    -- TP with DT accessories
    sets.engaged.hybrid = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.tp,
    }

    -- ===== WS =================================================
    sets.WS = {}  -- container: weaponskills below
    sets.WS["Drakesbane"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_str,
    }
    sets.WS["Stardiver"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_str,
    }
    sets.WS["Camlann's Torment"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_str,
    }
    sets.WS["Geirskogul"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_dex,
    }
    sets.WS["Sonic Thrust"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_str,
    }

    -- ===== JA =================================================
    sets.JA = {}  -- container: job abilities below
    sets.JA["Jump"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["High Jump"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Pteroslaver Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Super Jump"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Peltast's Schynbalds +3",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Spirit Link"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Spirit Surge"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Pteroslaver Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Ancient Circle"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Dragon Breaker"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Peltast's Vambraces +3",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Call Wyvern"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Vishap Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }
    sets.JA["Deep Breathing"] = {
        main = "Gungnir",
        sub = "Utu Grip",
        head = "Pteroslaver Armet +4",
        body = "Vishap Mail +4",
        hands = "Vishap Finger Gauntlets +4",
        legs = "Vishap Brais +4",
        feet = "Vishap Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.tp,
    }

    -- ===== wyvern =================================================
    sets.wyvern = {}  -- container: wyvern sets below
    sets.wyvern.breath = {
        head = "Peltast's Mezail +3",
        body = "Peltast's Plackart +3",
        hands = "Peltast's Vambraces +3",
        legs = "Peltast's Cuissots +3",
        feet = "Peltast's Schynbalds +3",
        neck = "Dragoon's Collar +2",
        back = capes.pet_mab,
    }
    sets.wyvern.dt = {
        head = "Pteroslaver Armet +4",
        body = "Pteroslaver Mail +4",
        hands = "Pteroslaver Finger Gauntlets +4",
        legs = "Pteroslaver Brais +4",
        feet = "Pteroslaver Greaves +4",
        neck = "Dragoon's Collar +2",
        back = capes.pet_dt,
    }

end

-- Real GearSwap calls get_sets() on load / job change; Fanxi's importer
-- calls it once and flattens the resulting sets table.
