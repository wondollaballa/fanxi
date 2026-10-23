--[[
    Fanxi GearSwap library — Onedough DNC
    Updated 2026-10-22 13:10:28
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/DNC.lua

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
    sets.idle = {}
    sets.JA = {}
    sets.Odyssey = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA["Climactic Flourish"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Curing Waltz III"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Fan Dance"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Grand Pas"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maculele Casaque +3",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Haste Samba"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Horos Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["No Foot Rise"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA.Presto = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Horos Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Reverse Flourish"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA["Saber Dance"] = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Horos Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }
    sets.JA.Trance = {
        main = "Terpsichore",
        sub = "Tauret",
        head = "Maxixi Tiara +4",
        body = "Horos Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        back = "Senuna's Mantle",
    }

    -- ===== Odyssey =====
    sets.Odyssey.gleti = {
        head = "Gleti's Mask",
        body = "Gleti's Cuirass",
        hands = "Gleti's Gauntlets",
        legs = "Gleti's Breeches",
        feet = "Gleti's Boots",
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
        main = "Gleti's Knife",
    }

    -- ===== WS =====
    sets.WS.Evisceration = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.WS.Exenterator = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.WS["Pyrrhic Kleos"] = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.WS["Rudra's Storm"] = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.engaged.dw = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Aurgelmir Orb +1",
        head = "Maxixi Tiara +4",
        body = "Maculele Casaque +3",
        hands = "Horos Bangles +4",
        legs = "Horos Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Suppanomimi",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Senuna's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Aurgelmir Orb +1",
        head = limbus.duty.tp.head,
        body = limbus.duty.tp.body,
        hands = limbus.duty.tp.hands,
        legs = limbus.duty.tp.legs,
        feet = limbus.duty.tp.feet,
        neck = "Unmoving Collar +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Senuna's Mantle",
    }
    sets.engaged.tp = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Aurgelmir Orb +1",
        head = limbus.duty.tp.head,
        body = limbus.duty.tp.body,
        hands = limbus.duty.tp.hands,
        legs = limbus.duty.tp.legs,
        feet = limbus.duty.tp.feet,
        neck = "Etoile Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Senuna's Mantle",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.duty_tp = { head = limbus.duty.tp.head, body = limbus.duty.tp.body, hands = limbus.duty.tp.hands, legs = limbus.duty.tp.legs, feet = limbus.duty.tp.feet }
    sets.Limbus.duty_ws = { head = limbus.duty.ws.head, body = limbus.duty.ws.body, hands = limbus.duty.ws.hands, legs = limbus.duty.ws.legs, feet = limbus.duty.ws.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Staunch Tathlum +1",
        head = "Maxixi Tiara +4",
        body = "Maculele Casaque +3",
        hands = "Horos Bangles +4",
        legs = "Horos Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Senuna's Mantle",
    }
    sets.idle.maxhp = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Etoile Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Senuna's Mantle",
    }
    sets.idle.mdt = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.idle.movement = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Staunch Tathlum +1",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Terpsichore",
        sub = "Tauret",
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
        back = "Senuna's Mantle",
    }
    sets.idle.town = {
        main = "Terpsichore",
        sub = "Tauret",
        ammo = "Staunch Tathlum +1",
        head = "Maxixi Tiara +4",
        body = "Maxixi Casaque +4",
        hands = "Maxixi Bangles +4",
        legs = "Maxixi Tights +4",
        feet = "Maxixi Toe Shoes +4",
        neck = "Etoile Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["Chocobo-AirKnife"] = {
        main = "Chocobo Knife",
        sub = "Air Knife",
    }
    sets.weaponset["MpuGandring-Gleti"] = {
        main = "Mpu Gandring",
        sub = "Gleti's Knife",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

