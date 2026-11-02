--[[
    Fanxi GearSwap library — Onedough SAM
    Updated 2026-10-29 10:39:56
    This is the server template; each account edits its own copy after first use.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/SAM.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.
]]

function get_sets()
    sets = {}
    sets.engaged = {}
    sets.idle = {}
    sets.JA = {}
    sets.Limbus = {}
    sets.Odyssey = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA.Hagakure = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Sakonji Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA.Hasso = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA["Konzen-ittai"] = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Kasuga Sune-Ate +3",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA.Meditate = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA["Meikyo Shisui"] = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Sakonji Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA.Seigan = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA.Sengikori = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Kasuga Kote +3",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA["Third Eye"] = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
    }
    sets.JA["Warding Circle"] = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        back = "Smertrios's Mantle",
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

    -- ===== WS =====
    sets.WS["Tachi: Fudo"] = {
        main = "Dojikiri Yasutsuna",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Mpaca's Cap",
        body = "Clemen. Hara.",
        hands = "Kasuga Kote +3",
        legs = "Nyame Flanchard",
        feet = "Kasuga Sune-Ate +3",
        neck = "Samurai's Nodowa +2",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Jinpu"] = {
        main = "Dojikiri Yasutsuna",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Samurai's Nodowa +2",
        waist = "Orpheus's Sash",
        ear1 = "Moonshade Earring",
        ear2 = "Schere Earring",
        ring1 = "Niqmaddu Ring",
        ring2 = "Sroda Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Kaiten"] = {
        main = "Amanomurakumo",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Kasuga Kote +3",
        legs = "Nyame Flanchard",
        feet = "Kasuga Sune-Ate +3",
        neck = "Samurai's Nodowa +2",
        waist = "Sailfi Belt +1",
        ear1 = "Thrud Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Niqmaddu Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Koki"] = {
        main = "Dojikiri Yasutsuna",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Samurai's Nodowa +2",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Weather. Ring +1",
        ring2 = "Niqmaddu Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Mumei"] = {
        main = "Kusanagi",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Mpaca's Cap",
        body = "Clemen. Hara.",
        hands = "Kasuga Kote +3",
        legs = "Nyame Flanchard",
        feet = "Kasuga Sune-Ate +3",
        neck = "Samurai's Nodowa +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Rana"] = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Crepuscular Pebble",
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Clemency Kote",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
        neck = "Samurai's Nodowa +2",
        waist = "Fotia Belt",
        ear1 = "Thrud Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Niqmaddu Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Shoha"] = {
        main = "Dojikiri Yasutsuna",
        sub = "Utu Grip",
        ammo = "Crepuscular Pebble",
        head = "Clemen. Somen",
        body = "Clemen. Hara.",
        hands = "Clemency Kote",
        legs = "Clem. Haidate",
        feet = "Clem. Sune-Ate",
        neck = "Samurai's Nodowa +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Sroda Ring",
        ring2 = "Niqmaddu Ring",
        back = "Smertrios's Mantle",
    }
    sets.WS["Tachi: Yukikaze"] = {
        main = "Kogarasumaru",
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
        back = "Smertrios's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Kogarasumaru",
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
        back = "Smertrios's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Kogarasumaru",
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
        back = "Smertrios's Mantle",
    }
    sets.engaged.tp = {
        main = "Kusanagi",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Kasuga Kabuto +3",
        body = "Kasuga Domaru +3",
        hands = "Clemency Kote",
        legs = "Kasuga Haidate +3",
        feet = "Ryuo Sune-Ate +1",
        neck = "Samurai's Nodowa +2",
        waist = "Sweordfaetels +1",
        ear1 = "Kasuga Earring +2",
        ear2 = "Dedition Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Niqmaddu Ring",
        back = "Takaha Mantle",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Wakido Kabuto +4",
        body = "Kasuga Domaru +3",
        hands = "Sakonji Kote +4",
        legs = "Sakonji Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Smertrios's Mantle",
    }
    sets.idle.maxhp = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Samurai's Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Smertrios's Mantle",
    }
    sets.idle.mdt = {
        main = "Kogarasumaru",
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
        back = "Smertrios's Mantle",
    }
    sets.idle.movement = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Kogarasumaru",
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
        back = "Smertrios's Mantle",
    }
    sets.idle.town = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Wakido Kabuto +4",
        body = "Wakido Domaru +4",
        hands = "Wakido Kote +4",
        legs = "Wakido Haidate +4",
        feet = "Wakido Sune-Ate +4",
        neck = "Samurai's Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset.Kusanagi = {
        main = "Kusanagi",
        sub = "Utu Grip",
    }
end

-- Fanxi template; each account has its own editable copy of this library.

