--[[
    Fanxi GearSwap library — Onedough RNG
    Updated 2026-10-22 21:57:41
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/RNG.lua

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
    sets.JA.Camouflage = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA["Decoy Shot"] = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Amini Bottillons +3",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA["Double Shot"] = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Arcadian Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA["Eagle Eye Shot"] = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Arcadian Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA.Shadowbind = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA.Sharpshot = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
    }
    sets.JA["Velocity Shot"] = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Amini Caban +3",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        back = "Belenus's Cape",
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
    sets.Odyssey.weapon_ranged = {
        range = "Gleti's Crossbow",
    }

    -- ===== WS =====
    sets.WS["Apex Arrow"] = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.WS.Coronach = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
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
        back = "Belenus's Cape",
    }
    sets.WS["Jishnu's Radiance"] = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.WS["Last Stand"] = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.WS["Namas Arrow"] = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.WS.Trueflight = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Scout's Gorget +2",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Belenus's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.engaged.hybrid = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.engaged.tp = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Amini Caban +3",
        hands = "Arcadian Bracers +4",
        legs = "Arcadian Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Belenus's Cape",
    }

    -- ===== enmity =====
    sets.enmity.down = {
        neck = "Scout's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Loquac. Earring",
        ear2 = "Etiolation Earring",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Lutian Cape",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Amini Caban +3",
        hands = "Arcadian Bracers +4",
        legs = "Arcadian Braccae +4",
        feet = "Orion Socks +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Belenus's Cape",
    }
    sets.idle.maxhp = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Scout's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Belenus's Cape",
    }
    sets.idle.mdt = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.idle.movement = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Carmine Cuisses +1",
        feet = "Hippomenes Socks +1",
        neck = "Scout's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.idle.town = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Hippomenes Socks +1",
        neck = "Scout's Gorget +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== ranged =====
    sets.ranged.acc = {
        main = "Tauret",
        range = "Annihilator",
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
        back = "Belenus's Cape",
    }
    sets.ranged.snapshot = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Orion Beret +4",
        body = "Orion Jerkin +4",
        hands = "Orion Bracers +4",
        legs = "Orion Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Belenus's Cape",
    }
    sets.ranged.tp = {
        main = "Tauret",
        range = "Annihilator",
        ammo = "Chrono Bullet",
        head = "Amini Gapette +3",
        body = "Amini Caban +3",
        hands = "Arcadian Bracers +4",
        legs = "Arcadian Braccae +4",
        feet = "Orion Socks +4",
        neck = "Scout's Gorget +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Belenus's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset["Naegling-Gleti"] = {
        main = "Naegling",
        sub = "Gleti's Knife",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

