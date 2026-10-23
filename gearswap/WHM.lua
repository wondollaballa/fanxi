--[[
    Fanxi mock GearSwap set library — White Mage (WHM)
    healer, divine magic, enmity control

    Import : Launcher -> Gear -> Import GearSwap file... -> WHM.lua
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
      Fast Cast  -> sets.precast.FC
      Magic Acc  -> sets.midcast (Enfeebling/Divine)
      Magic Atk. -> sets.midcast (Divine)
      Cure       -> sets.midcast["Healing Magic"]
      Weaponskill-> sets.WS.*
      Abilities  -> sets.JA.*
      Enmity-    -> sets.enmity.down

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
    fc = { name = "Alaunus's Cape", augments = {"MP+60", "Mag. Acc+20 /Mag. Dmg.+20", "MP+20", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    pdt = { name = "Alaunus's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    mdt = { name = "Alaunus's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Mag. Evasion+10", "Enmity-10", "Magic dmg. taken-10%"} },
    maxhp = { name = "Alaunus's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "HP+20", "Enmity-10", "Damage taken-5%"} },
    dt = { name = "Alaunus's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Damage taken-5%"} },
    tp = { name = "Alaunus's Cape", augments = {"DEX+20", "Accuracy+20 Attack+20", "Accuracy+10", '"Store TP"+10', "Phys. dmg. taken-10%"} },
    cure = { name = "Alaunus's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "MND+10", '"Cure Potency"+10', "Phys. dmg. taken-10%"} },
    macc = { name = "Alaunus's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "Mag. Acc.+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    ws_mnd = { name = "Alaunus's Cape", augments = {"MND+20", "Accuracy+20 Attack+20", "MND+10", "Weapon skill damage +10%", "Damage taken-5%"} },
}

-- Unity accessories: fixed max-rank Odyssey augments.
local unity = {
    collar = { name = "Unmoving Collar +1", augments = {"DEF+30", "HP+200"} },
    odnowa = { name = "Odnowa Earring +1", augments = {"DEF+30", "Damage taken-3%"} },
    ring = { name = "Gelatinous Ring +1", augments = {"VIT+15", "HP+100"} },
    tathlum = { name = "Ghastly Tathlum +1", augments = {"Magic Damage +10", "INT+5"} },
    loess = { name = "Loess Barbuta +1", augments = {"Enmity+10", "Damage taken-10%", "All Attr.+10"} },
}

-- Reive/Incursion capes used by a few sets (max Refractive augments).
local extra = {
    mending = { name = "Mending Cape", augments = {"Mag. Acc.+10", "Healing Magic Skill+10", "Enhancing Magic Skill+10", "Cure Potency+5%"} },
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

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.sworn_ta = { head = limbus.sworn.ta.head, body = limbus.sworn.ta.body, hands = limbus.sworn.ta.hands, legs = limbus.sworn.ta.legs, feet = limbus.sworn.ta.feet }
    sets.Limbus.sworn_phalanx = { head = limbus.sworn.phalanx.head, body = limbus.sworn.phalanx.body, hands = limbus.sworn.phalanx.hands, legs = limbus.sworn.phalanx.legs, feet = limbus.sworn.phalanx.feet }
    sets.Limbus.sworn_acc = { head = limbus.sworn.acc.head, body = limbus.sworn.acc.body, hands = limbus.sworn.acc.hands, legs = limbus.sworn.acc.legs, feet = limbus.sworn.acc.feet }

    -- ===== idle =================================================
    sets.idle = {}  -- container: Fanxi lists the children below
    -- town / CP / walking around
    sets.idle.town = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Hippomenes Socks +1",
        neck = "Cleric's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = unity.odnowa,
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }
    -- Refresh sources
    sets.idle.refresh = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = capes.fc,
    }
    -- max physical damage taken
    sets.idle.pdt = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
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
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
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
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Cleric's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.maxhp,
    }
    -- balanced damage taken with job pieces
    sets.idle.dt = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Ebers Bliaut +3",
        hands = "Piety Mitts +4",
        legs = "Piety Pantaloons +4",
        feet = "Theophany Duckbills +4",
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
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Hippomenes Socks +1",
        neck = "Cleric's Torque +2",
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
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Ebers Bliaut +3",
        hands = "Piety Mitts +4",
        legs = "Piety Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = capes.tp,
    }
    -- accuracy-first TP
    sets.engaged.acc = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
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
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
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

    -- ===== precast =================================================
    sets.precast = {}  -- container: fast cast below
    -- fast cast
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = capes.fc,
    }

    -- ===== midcast =================================================
    sets.midcast = {}  -- container: magic sets below
    -- cure potency / healing
    sets.midcast["Healing Magic"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        waist = "Witful Belt",
        ear1 = "Nourishing Earring +1",
        ear2 = "Tuisto Earring",
        ring1 = unity.ring,
        ring2 = "Stikini Ring +1",
        back = capes.cure,
    }
    -- enhancing duration
    sets.midcast["Enhancing Magic"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Theophany Cap +4",
        body = "Piety Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }
    -- enfeebling Macc
    sets.midcast["Enfeebling Magic"] = {
        main = "Opashoro 119 III",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Cleric's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }
    -- divine Macc/MAB
    sets.midcast["Divine Magic"] = {
        main = "Opashoro 119 III",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Incanter's Torque",
        waist = "Eschan Stone",
        ear1 = "Halasz Earring",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }

    -- ===== WS =================================================
    sets.WS = {}  -- container: weaponskills below
    sets.WS["Hexa Strike"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
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
        back = capes.ws_mnd,
    }
    sets.WS["Mystic Boon"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
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
        back = capes.ws_mnd,
    }
    sets.WS["Realmrazer"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = unity.tathlum,
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Sibyl Scarf",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = capes.ws_mnd,
    }
    sets.WS["Dagan"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
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
        back = capes.maxhp,
    }
    sets.WS["Randgrith"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
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
        back = capes.ws_mnd,
    }

    -- ===== JA =================================================
    sets.JA = {}  -- container: job abilities below
    sets.JA["Divine Seal"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Piety Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }
    sets.JA["Divine Caress"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Piety Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }
    sets.JA["Afflatus Solace"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }
    sets.JA["Afflatus Misery"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }
    sets.JA["Benediction"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Piety Cap +4",
        body = "Piety Bliaut +4",
        hands = "Theophany Mitts +4",
        legs = "Theophany Pantaloons +4",
        feet = "Theophany Duckbills +4",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }
    sets.JA["Asylum"] = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        head = "Theophany Cap +4",
        body = "Theophany Bliaut +4",
        hands = "Ebers Mitts +3",
        legs = "Theophany Pantaloons +4",
        feet = "Ebers Duckbills +3",
        neck = "Cleric's Torque +2",
        back = capes.cure,
    }

    -- ===== enmity =================================================
    sets.enmity = {}  -- container: enmity below
    -- enmity- support set
    sets.enmity.down = {
        neck = "Cleric's Torque +2",
        waist = "Witful Belt",
        ear1 = "Loquac. Earring",
        ear2 = "Etiolation Earring",
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = extra.mending,
    }

end

-- Real GearSwap calls get_sets() on load / job change; Fanxi's importer
-- calls it once and flattens the resulting sets table.
