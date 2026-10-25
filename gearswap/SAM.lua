--[[
    Fanxi GearSwap library — Onedough SAM
    Updated 2026-10-23 23:31:29
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/SAM.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.
]]

local capes = {
    pdt = { name = "Smertrios's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    mdt = { name = "Smertrios's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Mag. Evasion+10", "Enmity-10", "Magic dmg. taken-10%"} },
    maxhp = { name = "Smertrios's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "HP+20", "Enmity-10", "Damage taken-5%"} },
    dt = { name = "Smertrios's Mantle", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Damage taken-5%"} },
    tp = { name = "Smertrios's Mantle", augments = {"DEX+20", "Accuracy+20 Attack+20", "Accuracy+10", '"Store TP"+10', "Phys. dmg. taken-10%"} },
    ws_str = { name = "Smertrios's Mantle", augments = {"STR+20", "Accuracy+20 Attack+20", "STR+10", "Weapon skill damage +10%", "Damage taken-5%"} },
}

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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
    }
    sets.WS["Tachi: Kaiten"] = {
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
        back = capes.tp,
    }
    sets.WS["Tachi: Rana"] = {
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
        back = capes.tp,
    }
    sets.WS["Tachi: Shoha"] = {
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
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
        back = capes.tp,
    }
    sets.engaged.tp = {
        main = "Kogarasumaru",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Clemen. Somen",
        body = "Kasuga Domaru +3",
        hands = "Sakonji Kote +4",
        legs = "Sakonji Haidate +4",
        feet = "Clem. Sune-Ate",
        neck = "Samurai's Nodowa +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = capes.tp,
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
        back = capes.dt,
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
        back = capes.maxhp,
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
        back = capes.mdt,
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
        back = capes.pdt,
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

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

