--[[
    Fanxi GearSwap library — Onedough RUN
    Updated 2026-10-22 13:32:16
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/RUN.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.
]]

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
    sets.engaged = {}
    sets.enmity = {}
    sets.idle = {}
    sets.JA = {}
    sets.midcast = {}
    sets.Odyssey = {}
    sets.precast = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA.Battuta = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA["Elemental Sforzo"] = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Erilaz Gauntlets +3",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Embolden = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Erilaz Surcoat +3",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Gambit = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Pflug = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Rayke = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Swordplay = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Runeist Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Valiance = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Runeist Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }
    sets.JA.Vallation = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Runeist Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }

    -- ===== Odyssey =====
    sets.Odyssey.agwu = {
        head = "Agwu's Cap",
        body = "Agwu's Robe",
        hands = "Agwu's Gages",
        legs = "Agwu's Slops",
        feet = "Agwu's Pigaches",
    }
    sets.Odyssey.nyame_a = {
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
    }
    sets.Odyssey.nyame_b = {
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
    }
    sets.Odyssey.nyame_c = {
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
    }
    sets.Odyssey.nyame_d = {
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
    }
    sets.Odyssey.weapon = {
        main = "Agwu's Claymore",
    }

    -- ===== WS =====
    sets.WS.Dimidiation = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ogma's Cape",
    }
    sets.WS.Requiescat = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ogma's Cape",
    }
    sets.WS.Resolution = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ogma's Cape",
    }
    sets.WS["Savage Blade"] = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Rep. Plat. Medal",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ogma's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Combatant's Torque",
        waist = "Windbuffet Belt +1",
        ear1 = "Telos Earring",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Ogma's Cape",
    }
    sets.engaged.hybrid = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Unmoving Collar +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Evasionist's Cape",
    }
    sets.engaged.tp = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Runeist Bandeau +4",
        body = "Erilaz Surcoat +3",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Futhark Torque +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Ogma's Cape",
    }

    -- ===== enmity =====
    sets.enmity.up = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Futhark Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Erilaz Greaves +3",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ogma's Cape",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.sworn_ta = { head = limbus.sworn.ta.head, body = limbus.sworn.ta.body, hands = limbus.sworn.ta.hands, legs = limbus.sworn.ta.legs, feet = limbus.sworn.ta.feet }
    sets.Limbus.sworn_phalanx = { head = limbus.sworn.phalanx.head, body = limbus.sworn.phalanx.body, hands = limbus.sworn.phalanx.hands, legs = limbus.sworn.phalanx.legs, feet = limbus.sworn.phalanx.feet }
    sets.Limbus.sworn_acc = { head = limbus.sworn.acc.head, body = limbus.sworn.acc.body, hands = limbus.sworn.acc.hands, legs = limbus.sworn.acc.legs, feet = limbus.sworn.acc.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Erilaz Surcoat +3",
        hands = "Futhark Mitons +4",
        legs = "Futhark Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Evasionist's Cape",
    }
    sets.idle.maxhp = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Evasionist's Cape",
    }
    sets.idle.mdt = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Evasionist's Cape",
    }
    sets.idle.movement = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Runeist Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Carmine Cuisses +1",
        feet = "Hippomenes Socks +1",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Evasionist's Cape",
    }
    sets.idle.refresh = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Runeist Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Runeist Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Ogma's Cape",
    }
    sets.idle.town = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Runeist Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Runeist Trousers +4",
        feet = "Hippomenes Socks +1",
        neck = "Futhark Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast["Enfeebling Magic"] = {
        main = "Naegling",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Futhark Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Ogma's Cape",
    }
    sets.midcast["Enhancing Magic"] = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Futhark Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Runeist Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Futhark Torque +2",
        waist = "Audumbla Sash",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Ogma's Cape",
    }
    sets.midcast["Healing Magic"] = {
        main = "Epeolatry",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Runeist Bandeau +4",
        body = "Runeist Coat +4",
        hands = "Runeist Mitons +4",
        legs = "Runeist Trousers +4",
        feet = "Runeist Bottes +4",
        neck = "Futhark Torque +2",
        waist = "Audumbla Sash",
        ear1 = "Halasz Earring",
        ear2 = "Tuisto Earring",
        ring1 = "Gelatinous Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Ogma's Cape",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = limbus.sworn.phalanx.head,
        body = limbus.sworn.phalanx.body,
        hands = limbus.sworn.phalanx.hands,
        legs = limbus.sworn.phalanx.legs,
        feet = limbus.sworn.phalanx.feet,
        neck = "Orunmila's Torque",
        waist = "Audumbla Sash",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Ogma's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset.BraveBladeIII = {
        main = "Brave Blade III",
        sub = "Utu Grip",
    }
    sets.weaponset.Epeolatry = {
        main = "Epeolatry",
        sub = "Utu Grip",
    }
    sets.weaponset.Helheim = {
        main = "Helheim",
        sub = "Utu Grip",
    }
    sets.weaponset.Naegling = {
        main = "Naegling",
    }
    sets.weaponset.OnionSwordIII = {
        main = "Onion Sword III",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

