--[[
    Fanxi GearSwap library — Onedough DRK
    Updated 2026-10-22 09:01:14
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/DRK.lua

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
    sets.JA["Arcane Circle"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Ignominy Sollerets +4",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Blood Weapon"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Consume Mana"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Heathen's Cuirass +3",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Last Resort"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Ignominy Cuirass +4",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Nether Void"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Fallen's Burgeonet +4",
        body = "Fallen's Cuirass +4",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Scarlet Delirium"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Heathen's Gauntlets +3",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA.Souleater = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Ignominy Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }
    sets.JA["Weapon Bash"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Ignominy Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }

    -- ===== Odyssey =====
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
    sets.Odyssey.sakpata = {
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
    }
    sets.Odyssey.weapon = {
        main = "Agwu's Scythe",
    }

    -- ===== WS =====
    sets.WS.Catastrophe = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.WS["Cross Reaper"] = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.WS.Entropy = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.WS.Quietus = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.WS.Resolution = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = limbus.sworn.acc.head,
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = limbus.sworn.acc.feet,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ankou's Mantle",
    }
    sets.WS.Torcleaver = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = limbus.sworn.acc.head,
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = limbus.sworn.acc.feet,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ankou's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = limbus.sworn.ta.head,
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = limbus.sworn.ta.feet,
        neck = "Unmoving Collar +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Ankou's Mantle",
    }
    sets.engaged.tp = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = limbus.sworn.ta.head,
        body = "Heathen's Cuirass +3",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = limbus.sworn.ta.feet,
        neck = "Abyssal Bead Necklace +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Ankou's Mantle",
    }

    -- ===== enmity =====
    sets.enmity.up = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Fallen's Cuirass +4",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Ankou's Mantle",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.sworn_ta = { head = limbus.sworn.ta.head, body = limbus.sworn.ta.body, hands = limbus.sworn.ta.hands, legs = limbus.sworn.ta.legs, feet = limbus.sworn.ta.feet }
    sets.Limbus.sworn_phalanx = { head = limbus.sworn.phalanx.head, body = limbus.sworn.phalanx.body, hands = limbus.sworn.phalanx.hands, legs = limbus.sworn.phalanx.legs, feet = limbus.sworn.phalanx.feet }
    sets.Limbus.sworn_acc = { head = limbus.sworn.acc.head, body = limbus.sworn.acc.body, hands = limbus.sworn.acc.hands, legs = limbus.sworn.acc.legs, feet = limbus.sworn.acc.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Ignominy Burgeonet +4",
        body = "Heathen's Cuirass +3",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Ignominy Sollerets +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Ankou's Mantle",
    }
    sets.idle.maxhp = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Ankou's Mantle",
    }
    sets.idle.mdt = {
        main = "Apocalypse",
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
        back = "Ankou's Mantle",
    }
    sets.idle.movement = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Ignominy Burgeonet +4",
        body = "Ignominy Cuirass +4",
        hands = "Ignominy Gauntlets +4",
        legs = "Carmine Cuisses +1",
        feet = "Ignominy Sollerets +4",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Ankou's Mantle",
    }
    sets.idle.refresh = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Ignominy Burgeonet +4",
        body = "Ignominy Cuirass +4",
        hands = "Ignominy Gauntlets +4",
        legs = "Ignominy Flanchard +4",
        feet = "Ignominy Sollerets +4",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Ankou's Mantle",
    }
    sets.idle.town = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Ignominy Burgeonet +4",
        body = "Ignominy Cuirass +4",
        hands = "Ignominy Gauntlets +4",
        legs = "Ignominy Flanchard +4",
        feet = "Ignominy Sollerets +4",
        neck = "Abyssal Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast["Dark Magic"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Abyssal Bead Necklace +2",
        waist = "Eschan Stone",
        ear1 = "Digni. Earring",
        ear2 = "Enchntr. Earring +1",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Ankou's Mantle",
    }
    sets.midcast["Enfeebling Magic"] = {
        main = "Apocalypse",
        sub = "Utu Grip",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Abyssal Bead Necklace +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Ankou's Mantle",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Carmine Mask +1",
        body = "Sacro Breastplate",
        hands = "Leyline Gloves",
        legs = "Founder's Hose",
        feet = "Carmine Greaves +1",
        neck = "Orunmila's Torque",
        waist = "Asklepian Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Ankou's Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset.Apoc = {
        main = "Apocalypse",
        sub = "Utu Grip",
    }
    sets.weaponset.BraveBladeIII = {
        main = "Brave Blade III",
        sub = "Utu Grip",
    }
    sets.weaponset.FinalSickle = {
        main = "Final Sickle",
        sub = "Utu Grip",
    }
    sets.weaponset.Foenaria = {
        main = "Foenaria",
        sub = "Utu Grip",
    }
    sets.weaponset.Helheim = {
        main = "Helheim",
        sub = "Utu Grip",
    }
    sets.weaponset.Naegling = {
        main = "Naegling",
    }
    sets.weaponset.Ragnorak = {
        main = "Ragnarok",
        sub = "Utu Grip",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

