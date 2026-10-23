--[[
    Fanxi GearSwap library — Onedough THF
    Updated 2026-10-22 13:35:11
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/THF.lua

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
    sets.JA["Assassin's Charge"] = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Skulker's Armlets +3",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA.Collaborator = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA.Feint = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Plunderer's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA.Flee = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA.Hide = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA.Larceny = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Skulker's Poulaines +3",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA["Sneak Attack"] = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
    }
    sets.JA["Trick Attack"] = {
        main = "Mandau",
        sub = "Vajra",
        head = "Pillager's Bonnet +4",
        body = "Plunderer's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        back = "Toutatis's Cape",
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

    -- ===== TH =====
    sets.TH = {
        ammo = "Per. Lucky Egg",
        head = "Skulker's Bonnet +3",
        body = "Skulker's Vest +3",
        hands = "Skulker's Armlets +3",
        legs = "Volte Hose",
        feet = "Skulker's Poulaines +3",
        neck = "Assassin's Gorget +2",
        waist = "Chaac Belt",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Epona's Ring",
        ring2 = "Ilabrat Ring",
        back = "Toutatis's Cape",
    }

    -- ===== WS =====
    sets.WS.Evisceration = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.WS.Exenterator = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.WS["Mandalic Stab"] = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.WS["Rudra's Storm"] = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.WS["Shark Bite"] = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.engaged.dw = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Aurgelmir Orb +1",
        head = "Pillager's Bonnet +4",
        body = "Skulker's Vest +3",
        hands = "Plunderer's Armlets +4",
        legs = "Plunderer's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Suppanomimi",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Toutatis's Cape",
    }
    sets.engaged.hybrid = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.engaged.tp = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Aurgelmir Orb +1",
        head = limbus.duty.tp.head,
        body = limbus.duty.tp.body,
        hands = limbus.duty.tp.hands,
        legs = limbus.duty.tp.legs,
        feet = limbus.duty.tp.feet,
        neck = "Assassin's Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Toutatis's Cape",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.duty_tp = { head = limbus.duty.tp.head, body = limbus.duty.tp.body, hands = limbus.duty.tp.hands, legs = limbus.duty.tp.legs, feet = limbus.duty.tp.feet }
    sets.Limbus.duty_ws = { head = limbus.duty.ws.head, body = limbus.duty.ws.body, hands = limbus.duty.ws.hands, legs = limbus.duty.ws.legs, feet = limbus.duty.ws.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Staunch Tathlum +1",
        head = "Pillager's Bonnet +4",
        body = "Skulker's Vest +3",
        hands = "Plunderer's Armlets +4",
        legs = "Plunderer's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Toutatis's Cape",
    }
    sets.idle.maxhp = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Assassin's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Toutatis's Cape",
    }
    sets.idle.mdt = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.idle.movement = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Staunch Tathlum +1",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Mandau",
        sub = "Vajra",
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
        back = "Toutatis's Cape",
    }
    sets.idle.town = {
        main = "Mandau",
        sub = "Vajra",
        ammo = "Staunch Tathlum +1",
        head = "Pillager's Bonnet +4",
        body = "Pillager's Vest +4",
        hands = "Pillager's Armlets +4",
        legs = "Pillager's Culottes +4",
        feet = "Pillager's Poulaines +4",
        neck = "Assassin's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["MpuGandring-GletisKnife"] = {
        main = "Mpu Gandring",
        sub = "Gleti's Knife",
    }
    sets.weaponset["Vajra-AirKnife"] = {
        main = "Vajra",
        sub = "Air Knife",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

