--[[
    Fanxi GearSwap library — Onedough COR
    Updated 2026-10-29 22:42:25
    This is the server template; each account edits its own copy after first use.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/COR.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.
]]

function get_sets()
    sets = {}
    sets.engaged = {}
    sets.enmity = {}
    sets.idle = {}
    sets.JA = {}
    sets.Limbus = {}
    sets.Odyssey = {}
    sets.ranged = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA["Crooked Cards"] = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Chasseur's Tricorne +3",
        body = "Laksamana's Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }
    sets.JA.Fold = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Laksamana's Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }
    sets.JA["Phantom Roll"] = {
        main = "Rostam",
        range = "Compensator",
        ammo = "Bayeux Bullet",
        head = "Lanun Tricorne +4",
        body = "Chasseur's Frac +3",
        hands = "Chasseur's Gants +3",
        legs = "Desultor Tassets",
        feet = "Chasseur's Bottes +3",
        neck = "Regal Necklace",
        ring1 = "Luzaf's Ring",
        ring2 = "Defending Ring",
        back = "Camulus's Mantle",
    }
    sets.JA["Quick Draw"] = {
        main = "Tauret",
        sub = "Naegling",
        range = "Death Penalty",
        ammo = "Living Bullet",
        head = "Ikenga's Hat",
        body = "Lanun Frac +4",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Baetyl Pendant",
        waist = "Skrymir Cord +1",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Dingir Ring",
        ring2 = "Ifrit Ring +1",
        back = "Camulus's Mantle",
    }
    sets.JA["Random Deal"] = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Lanun Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }
    sets.JA["Snake Eye"] = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Laksamana's Frac +4",
        hands = "Chasseur's Gants +3",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }
    sets.JA["Triple Shot"] = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Laksamana's Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Chasseur's Bottes +3",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }
    sets.JA["Wild Card"] = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Lanun Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        back = "Camulus's Mantle",
    }

    -- ===== Limbus =====
    sets.Limbus.clemency_tp = {
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Clemency Kote",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
    }
    sets.Limbus.clemency_ws = {
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Clemency Kote",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
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
    sets.WS.Detonator = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.WS.Evisceration = {
        main = "Tauret",
        sub = "Gleti's Knife",
        range = "Death Penalty",
        ammo = "Bayeux Bullet",
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Clemency Kote",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Odr Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Begrudging Ring",
        ring2 = "Regal Ring",
        back = "Camulus's Mantle",
    }
    sets.WS["Hot Shot"] = {
        main = "Naegling",
        sub = "Tauret",
        range = "Fomalhaut",
        ammo = "Living Bullet",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Camulus's Mantle",
    }
    sets.WS["Last Stand"] = {
        main = "Crepuscular Knife",
        sub = "Odium",
        range = "Fomalhaut",
        ammo = "Chrono Bullet",
        head = "Clemen. Somen",
        body = "Ikenga's Vest",
        hands = "Chasseur's Gants +3",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Camulus's Mantle",
    }
    sets.WS["Leaden Salute"] = {
        main = "Naegling",
        sub = "Tauret",
        range = "Death Penalty",
        ammo = "Living Bullet",
        head = "Pixie Hairpin +1",
        body = "Lanun Frac +4",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Orpheus's Sash",
        ear1 = "Hoxne Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Dingir Ring",
        ring2 = "Archon Ring",
        back = "Camulus's Mantle",
    }
    sets.WS["Savage Blade"] = {
        main = "Naegling",
        sub = "Crepuscular Knife",
        range = "Ataktos",
        ammo = "Bayeux Bullet",
        head = "Clemen. Somen",
        body = "Ikenga's Vest",
        hands = "Chasseur's Gants +3",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Camulus's Mantle",
    }
    sets.WS.Terminus = {
        main = "Crepuscular Knife",
        sub = "Odium",
        range = "Earp",
        ammo = "Chrono Bullet",
        head = "Clemen. Somen",
        body = "Ikenga's Vest",
        hands = "Chasseur's Gants +3",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Alabaster Mantle",
    }
    sets.WS.Wildfire = {
        main = "Naegling",
        sub = "Tauret",
        range = "Armageddon",
        ammo = "Living Bullet",
        head = "Nyame Helm",
        body = "Lanun Frac +4",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Lanun Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Skrymir Cord +1",
        ear1 = "Friomisi Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Dingir Ring",
        back = "Camulus's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.engaged.tp = {
        main = "Naegling",
        sub = "Gleti's Knife",
        range = "Ataktos",
        ammo = "Bayeux Bullet",
        head = "Clemen. Somen",
        body = "Chasseur's Frac +3",
        hands = "Clemency Kote",
        legs = "Samnuha Tights",
        feet = "Clem. Sune-Ate",
        neck = "Iskur Gorget",
        waist = "Reiki Yotai",
        ear1 = "Alabaster Earring",
        ear2 = "Dedition Earring",
        ring1 = "Epona's Ring",
        ring2 = "Petrov Ring",
        back = "Null Shawl",
    }

    -- ===== enmity =====
    sets.enmity.down = {
        neck = "Commodore Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Loquac. Earring",
        ear2 = "Etiolation Earring",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Gunslinger's Cape",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Chasseur's Frac +3",
        hands = "Lanun Gants +4",
        legs = "Lanun Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Camulus's Mantle",
    }
    sets.idle.maxhp = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Commodore Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Camulus's Mantle",
    }
    sets.idle.mdt = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.idle.movement = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Laksamana's Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Carmine Cuisses +1",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.idle.town = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Laksamana's Tricorne +4",
        body = "Laksamana's Frac +4",
        hands = "Laksamana's Gants +4",
        legs = "Laksamana's Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== ranged =====
    sets.ranged.acc = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
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
        back = "Camulus's Mantle",
    }
    sets.ranged.mab = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Commodore Charm +2",
        waist = "Eschan Stone",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = "Camulus's Mantle",
    }
    sets.ranged.tp = {
        main = "Naegling",
        range = "Armageddon",
        ammo = "Chrono Bullet",
        head = "Chasseur's Tricorne +3",
        body = "Chasseur's Frac +3",
        hands = "Lanun Gants +4",
        legs = "Lanun Trews +4",
        feet = "Laksamana's Bottes +4",
        neck = "Commodore Charm +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Camulus's Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["Hot Shot"] = {
        main = "Naegling",
        sub = "Tauret",
        range = "Fomalhaut",
        ammo = "Living Bullet",
    }
    sets.weaponset["Leaden Salute"] = {
        main = "Naegling",
        sub = "Tauret",
        range = "Death Penalty",
        ammo = "Living Bullet",
    }
    sets.weaponset["Rostam-Gleti"] = {
        main = "Rostam",
        sub = "Gleti's Knife",
    }
    sets.weaponset["Savage Blade"] = {
        main = "Naegling",
        sub = "Gleti's Knife",
        range = "Ataktos",
        ammo = "Bayeux Bullet",
    }
end

-- Fanxi template; each account has its own editable copy of this library.

