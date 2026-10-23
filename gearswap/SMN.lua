--[[
    Fanxi GearSwap library — Onedough SMN
    Updated 2026-10-22 13:16:25
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/SMN.lua

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
    sets.avatar = {}
    sets.engaged = {}
    sets.idle = {}
    sets.JA = {}
    sets.midcast = {}
    sets.Odyssey = {}
    sets.precast = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA["Astral Conduit"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Beckoner's Doublet +3",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        back = "Campestres's Cape",
    }
    sets.JA["Astral Flow"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Glyphic Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        back = "Campestres's Cape",
    }
    sets.JA["Avatar's Favor"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Beckoner's Bracers +3",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        back = "Campestres's Cape",
    }
    sets.JA["Elemental Siphon"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        back = "Campestres's Cape",
    }
    sets.JA["Mana Cede"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        back = "Campestres's Cape",
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

    -- ===== WS =====
    sets.WS.Cataclysm = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Summoner's Collar +2",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Campestres's Cape",
    }
    sets.WS.Omniscience = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Sibyl Scarf",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Campestres's Cape",
    }
    sets.WS.Shattersoul = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Sibyl Scarf",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Campestres's Cape",
    }

    -- ===== avatar =====
    sets.avatar.acc = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Incarnation Sash",
        back = "Campestres's Cape",
    }
    sets.avatar.dt = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Glyphic Horn +4",
        body = "Glyphic Doublet +4",
        hands = "Glyphic Bracers +4",
        legs = "Glyphic Spats +4",
        feet = "Glyphic Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Incarnation Sash",
        back = "Campestres's Cape",
    }
    sets.avatar.mab = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Beckoner's Horn +3",
        body = "Beckoner's Doublet +3",
        hands = "Beckoner's Bracers +3",
        legs = "Beckoner's Spats +3",
        feet = "Beckoner's Pigaches +3",
        neck = "Summoner's Collar +2",
        waist = "Incarnation Sash",
        back = "Campestres's Cape",
    }
    sets.avatar.perpetuation = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Incarnation Sash",
        ring1 = "Petrov Ring",
        back = "Campestres's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
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
        back = "Campestres's Cape",
    }
    sets.engaged.hybrid = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
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
        back = "Campestres's Cape",
    }
    sets.engaged.tp = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Beckoner's Doublet +3",
        hands = "Glyphic Bracers +4",
        legs = "Glyphic Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Campestres's Cape",
    }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.indomitable_cast = { head = limbus.indomitable.cast.head, body = limbus.indomitable.cast.body, hands = limbus.indomitable.cast.hands, legs = limbus.indomitable.cast.legs, feet = limbus.indomitable.cast.feet }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Beckoner's Doublet +3",
        hands = "Glyphic Bracers +4",
        legs = "Glyphic Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Campestres's Cape",
    }
    sets.idle.maxhp = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Summoner's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Campestres's Cape",
    }
    sets.idle.mdt = {
        main = "Nirvana",
        sub = "Pole Grip",
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
        back = "Campestres's Cape",
    }
    sets.idle.movement = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Hippomenes Socks +1",
        neck = "Summoner's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Nirvana",
        sub = "Pole Grip",
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
        back = "Campestres's Cape",
    }
    sets.idle.refresh = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Campestres's Cape",
    }
    sets.idle.town = {
        main = "Nirvana",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Hippomenes Socks +1",
        neck = "Summoner's Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast["Summoning Magic"] = {
        main = "Nirvana",
        sub = "Pole Grip",
        head = "Convoker's Horn +4",
        body = "Glyphic Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Summoner's Collar +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Campestres's Cape",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Convoker's Horn +4",
        body = "Convoker's Doublet +4",
        hands = "Convoker's Bracers +4",
        legs = "Convoker's Spats +4",
        feet = "Convoker's Pigaches +4",
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Campestres's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset.Opashoro = {
        main = "Opashoro",
        sub = "Pole Grip",
    }
    sets.weaponset.Pandit = {
        main = "Pandit's Staff",
        sub = "Pole Grip",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

