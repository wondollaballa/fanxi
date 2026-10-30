--[[
    Fanxi GearSwap library — Onedough RDM
    Updated 2026-10-30 13:03:09
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/RDM.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.
]]

function get_sets()
    sets = {}
    sets.engaged = {}
    sets.idle = {}
    sets.JA = {}
    sets.Limbus = {}
    sets.midcast = {}
    sets.Odyssey = {}
    sets.precast = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA.Chainspell = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Vitiation Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = "Sucellos's Cape",
    }
    sets.JA.Composure = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = "Sucellos's Cape",
    }
    sets.JA.Convert = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = "Sucellos's Cape",
    }
    sets.JA.Saboteur = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = "Sucellos's Cape",
    }
    sets.JA.Spontaneity = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        back = "Sucellos's Cape",
    }

    -- ===== Limbus =====
    sets.Limbus.sworn_acc = {
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
    }
    sets.Limbus.sworn_phalanx = {
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
    }
    sets.Limbus.sworn_ta = {
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
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
        main = "Sakpata's Sword",
    }

    -- ===== WS =====
    sets.WS["Black Halo"] = {
        main = "Maxentius",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = "Vitiation Chapeau +4",
        body = "Bunzi's Robe",
        hands = "Atrophy Gloves +4",
        legs = "Nyame Flanchard",
        feet = "Lethargy Houseaux +3",
        neck = "Duelist's Torque +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Sucellos's Cape",
    }
    sets.WS["Chant du Cygne"] = {
        main = "Naegling",
        sub = "Genbu's Shield",
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
        back = "Sucellos's Cape",
    }
    sets.WS.Requiescat = {
        main = "Sequence",
        sub = "Daybreak",
        ammo = "Crepuscular Pebble",
        head = "Null Masque",
        body = "Bunzi's Robe",
        hands = "Malignance Gloves",
        legs = "Nyame Flanchard",
        feet = "Sworn Sabatons",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Metamorph Ring +1",
        back = "Sucellos's Cape",
    }
    sets.WS["Ruthless Stroke"] = {
        main = "Mpu Gandring",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Malignance Gloves",
        legs = "Nyame Flanchard",
        feet = "Lethargy Houseaux +3",
        neck = "Fotia Gorget",
        waist = "Kentarch Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Alabaster Mantle",
    }
    sets.WS["Sanguine Blade"] = {
        main = "Crocea Mors",
        sub = "Bunzi's Rod",
        ammo = "Sroda Tathlum",
        head = "Pixie Hairpin +1",
        body = "Nyame Mail",
        hands = "Jhakri Cuffs +2",
        legs = "Lethargy Fuseau +3",
        feet = "Lethargy Houseaux +3",
        neck = "Baetyl Pendant",
        waist = "Orpheus's Sash",
        ear1 = "Malignance Earring",
        ear2 = "Regal Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Archon Ring",
        back = "Sucellos's Cape",
    }
    sets.WS["Savage Blade"] = {
        main = "Naegling",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = "Vitiation Chapeau +4",
        body = "Nyame Mail",
        hands = "Atrophy Gloves +4",
        legs = "Nyame Flanchard",
        feet = "Lethargy Houseaux +3",
        neck = "Duelist's Torque +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Sucellos's Cape",
    }
    sets.WS["Imperator"] = {
        main = "Caliburnus",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Sucellos's Cape",
    }
    sets.WS["Seraph Blade"] = {
        main = "Crocea Mors",
        sub = "Daybreak",
        ammo = "Sroda Tathlum",
        head = "Lethargy Chappel +3",
        body = "Nyame Mail",
        hands = "Lethargy Gantherots +3",
        legs = "Nyame Flanchard",
        feet = "Lethargy Houseaux +3",
        neck = "Fotia Gorget",
        waist = "Orpheus's Sash",
        ear1 = "Moonshade Earring",
        ear2 = "Malignance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Sucellos's Cape",
    }

    -- ===== engaged =====
    sets.engaged.Enspell = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Aurgelmir Orb +1",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Duelist's Torque +2",
        waist = "Orpheus's Sash",
        ear1 = "Telos Earring",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Sucellos's Cape",
    }
    sets.engaged.acc = {
        main = "Naegling",
        sub = "Genbu's Shield",
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
        back = "Sucellos's Cape",
    }
    sets.engaged.hybrid = {
        main = "Naegling",
        sub = "Genbu's Shield",
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
        back = "Sucellos's Cape",
    }
    sets.engaged.tp = {
        ammo = "Aurgelmir Orb +1",
        head = "Bunzi's Hat",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Anu Torque",
        waist = "Reiki Yotai",
        ear1 = "Eabani Earring",
        ear2 = "Alabaster Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Sucellos's Cape",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Vitiation Gloves +4",
        legs = "Vitiation Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Sucellos's Cape",
    }
    sets.idle.maxhp = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Sucellos's Cape",
    }
    sets.idle.mdt = {
        main = "Naegling",
        sub = "Genbu's Shield",
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
        back = "Sucellos's Cape",
    }
    sets.idle.movement = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Carmine Cuisses +1",
        feet = "Hippomenes Socks +1",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Naegling",
        sub = "Genbu's Shield",
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
        back = "Sucellos's Cape",
    }
    sets.idle.refresh = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Sucellos's Cape",
    }
    sets.idle.town = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Hippomenes Socks +1",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast.Cure = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Telchine Gloves",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Incanter's Torque",
        waist = "Witful Belt",
        ear1 = "Malignance Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Jann. Ring +1",
        back = "Sucellos's Cape",
    }
    sets.midcast.CureHP = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Jann. Ring +1",
        ring2 = "Gelatinous Ring +1",
        back = "Sucellos's Cape",
    }
    sets.midcast["Dark Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Digni. Earring",
        ear2 = "Enchntr. Earring +1",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Sucellos's Cape",
    }
    sets.midcast["Elemental Magic"] = {
        main = "Wizard's Rod (Reforged)",
        sub = "Ammurapi Shield",
        ammo = "Ghastly Tathlum +1",
        head = "Ea Hat +1",
        body = "Ea Houppe. +1",
        hands = "Bunzi's Gloves",
        legs = "Ea Slops +1",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Skrymir Cord +1",
        ear1 = "Regal Earring",
        ear2 = "Malignance Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = "Sucellos's Cape",
    }
    sets.midcast["Elemental Magic Macc"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Sucellos's Cape",
    }
    sets.midcast["Enfeebling Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Sucellos's Cape",
    }
    sets.midcast["Enhancing Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Sucellos's Cape",
    }
    sets.midcast.EnhancingDuration = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Telchine Cap",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Telchine Braconi",
        feet = "Lethargy Houseaux +3",
        neck = "Incanter's Torque",
        waist = "Embla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Malignance Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Sucellos's Cape",
    }
    sets.midcast.EnhancingSkill = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Vitiation Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Lethargy Houseaux +3",
        neck = "Incanter's Torque",
        waist = "Embla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Malignance Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Sucellos's Cape",
    }
    sets.midcast.Enspell = {
        main = "Crocea Mors",
        sub = "Genbu's Shield",
        ammo = "Sroda Tathlum",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Aya. Manopolas +2",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Incanter's Torque",
        waist = "Embla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Malignance Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Sucellos's Cape",
    }
    sets.midcast["Healing Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Witful Belt",
        ear1 = "Halasz Earring",
        ear2 = "Tuisto Earring",
        ring1 = "Gelatinous Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Sucellos's Cape",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Sucellos's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset["Caliburnus-DiamondAspis"] = {
        main = "Caliburnus",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Caliburnus-Thibron"] = {
        main = "Caliburnus",
        sub = "Thibron",
    }
    sets.weaponset.CroceaMors = {
        main = "Crocea Mors",
        sub = "Genbu's Shield",
    }
    sets.weaponset["CroceaMors-Daybreak"] = {
        main = "Crocea Mors",
        sub = "Daybreak",
    }
    sets.weaponset["Excalibur-DiamondAspis"] = {
        main = "Excalibur",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Maxentius-Thibron"] = {
        main = "Maxentius",
        sub = "Thibron",
    }
    sets.weaponset["Mpu-Thibron"] = {
        main = "Mpu Gandring",
        sub = "Thibron",
    }
    sets.weaponset["MpuGandring-DiamondAspis"] = {
        main = "Mpu Gandring",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Naegling-Thibron"] = {
        main = "Naegling",
        sub = "Thibron",
    }
    sets.weaponset["WizardsRod-DiamondAspis"] = {
        main = "Wizard's Rod",
        sub = "Diamond Aspis",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

