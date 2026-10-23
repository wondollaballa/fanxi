--[[
    Fanxi GearSwap library — Onedough BRD
    Updated 2026-10-22 13:03:58
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/BRD.lua

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
    sets.JA["Clarion Call"] = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Fili Hongreline +3",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
    }
    sets.JA.Marcato = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
    }
    sets.JA.Nightingale = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Bihu Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
    }
    sets.JA.Pianissimo = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
    }
    sets.JA["Soul Voice"] = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Bihu Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
    }
    sets.JA.Troubadour = {
        main = "Carnwenhan",
        range = "Daurdabla",
        head = "Brioso Roundlet +4",
        body = "Bihu Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        back = "Intarabus's Cape",
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
    sets.Odyssey.weapon = {
        main = "Gleti's Knife",
    }

    -- ===== WS =====
    sets.WS.Evisceration = {
        main = "Carnwenhan",
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
        back = "Intarabus's Cape",
    }
    sets.WS.Exenterator = {
        main = "Carnwenhan",
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
        back = "Intarabus's Cape",
    }
    sets.WS["Mordant Rime"] = {
        main = "Carnwenhan",
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
        back = "Intarabus's Cape",
    }
    sets.WS["Rudra's Storm"] = {
        main = "Carnwenhan",
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
        back = "Intarabus's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Carnwenhan",
        range = "Daurdabla",
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
        back = "Intarabus's Cape",
    }
    sets.engaged.hybrid = {
        main = "Carnwenhan",
        range = "Daurdabla",
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
        back = "Intarabus's Cape",
    }
    sets.engaged.tp = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Aurgelmir Orb +1",
        head = "Brioso Roundlet +4",
        body = limbus.revelation.tp.body,
        hands = "Bihu Cuffs +4",
        legs = limbus.revelation.tp.legs,
        feet = limbus.revelation.tp.feet,
        neck = "Bard's Charm +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Intarabus's Cape",
    }

    -- ===== enmity =====
    sets.enmity.down = {
        neck = "Bard's Charm +2",
        waist = "Witful Belt",
        ear1 = "Loquac. Earring",
        ear2 = "Etiolation Earring",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Rhapsode's Cape",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.revelation_tp = { head = limbus.revelation.tp.head, body = limbus.revelation.tp.body, hands = limbus.revelation.tp.hands, legs = limbus.revelation.tp.legs, feet = limbus.revelation.tp.feet }
    sets.Limbus.revelation_ws = { head = limbus.revelation.ws.head, body = limbus.revelation.ws.body, hands = limbus.revelation.ws.hands, legs = limbus.revelation.ws.legs, feet = limbus.revelation.ws.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Staunch Tathlum +1",
        head = "Brioso Roundlet +4",
        body = "Fili Hongreline +3",
        hands = "Bihu Cuffs +4",
        legs = "Bihu Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Intarabus's Cape",
    }
    sets.idle.maxhp = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Bard's Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Intarabus's Cape",
    }
    sets.idle.mdt = {
        main = "Carnwenhan",
        range = "Daurdabla",
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
        back = "Intarabus's Cape",
    }
    sets.idle.movement = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Staunch Tathlum +1",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Hippomenes Socks +1",
        neck = "Bard's Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Carnwenhan",
        range = "Daurdabla",
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
        back = "Intarabus's Cape",
    }
    sets.idle.refresh = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Staunch Tathlum +1",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Intarabus's Cape",
    }
    sets.idle.town = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Staunch Tathlum +1",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Hippomenes Socks +1",
        neck = "Bard's Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast.Singing = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Pemphredo Tathlum",
        head = "Brioso Roundlet +4",
        body = "Bihu Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Intarabus's Cape",
    }
    sets.midcast["Singing Duration"] = {
        main = "Carnwenhan",
        range = "Daurdabla",
        ammo = "Pemphredo Tathlum",
        head = "Brioso Roundlet +4",
        body = "Bihu Justaucorps +4",
        hands = "Brioso Cuffs +4",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Bard's Charm +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Intarabus's Cape",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Brioso Roundlet +4",
        body = "Brioso Justaucorps +4",
        hands = "Leyline Gloves",
        legs = "Brioso Cannions +4",
        feet = "Brioso Slippers +4",
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Intarabus's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset.MpuGandring = {
        main = "Mpu Gandring",
        sub = "Genbu's Shield",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

