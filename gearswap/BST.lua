--[[
    Fanxi GearSwap library — Onedough BST
    Updated 2026-10-28 22:14:58
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/BST.lua

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
    sets.pet = {}
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA["Bestial Loyalty"] = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Nukumi Gausape +3",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA["Call Beast"] = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA.Familiar = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Ankusa Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA["Killer Instinct"] = {
        sub = "Diamond Aspis",
        head = "Ankusa Helm +4",
        body = "Nukumi Gausape +3",
    }
    sets.JA.Reward = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA.Sic = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA.Spur = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Ankusa Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.JA.Unleash = {
        main = "Aymur",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Nukumi Manoplas +3",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }

    -- ===== Limbus =====
    sets.Limbus.duty_tp = {
        head = "Duty Crown",
        body = "Duty Cyclas",
        hands = "Duty Gauntlets",
        legs = "Duty Flanchard",
        feet = "Duty Sollerets",
    }
    sets.Limbus.duty_ws = {
        head = "Duty Crown",
        body = "Duty Cyclas",
        hands = "Duty Gauntlets",
        legs = "Duty Flanchard",
        feet = "Duty Sollerets",
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
        main = "Agwu's Axe",
    }

    -- ===== WS =====
    sets.WS.Blitz = {
        main = "Spalirisos",
        sub = "Ikenga's Axe",
        ammo = "Crepuscular Pebble",
        head = "Ankusa Helm +4",
        body = "Gleti's Cuirass",
        hands = "Totemic Gloves +4",
        legs = "Nyame Flanchard",
        feet = "Nukumi Ocreae +3",
        neck = "Beastmaster Collar +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Nukumi Earring +2",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Artio's Mantle",
    }
    sets.WS.Calamity = {
        main = "Tri-edge",
        sub = "Ikenga's Axe",
        ammo = "Crepuscular Pebble",
        head = "Ankusa Helm +4",
        body = "Nukumi Gausape +3",
        hands = "Totemic Gloves +4",
        legs = "Gleti's Breeches",
        feet = "Nyame Sollerets",
        neck = "Beastmaster Collar +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Nukumi Earring +2",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Artio's Mantle",
    }
    sets.WS.Cloudsplitter = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.WS.Decimation = {
        main = "Dolichenus",
        sub = "Farsha",
        ammo = "Coiste Bodhar",
        head = "Duty Crown",
        body = "Gleti's Cuirass",
        hands = "Gleti's Gauntlets",
        legs = "Gleti's Breeches",
        feet = "Nukumi Ocreae +3",
        neck = "Beastmaster Collar +2",
        waist = "Sailfi Belt +1",
        ear1 = "Hoxne Earring",
        ear2 = "Nukumi Earring +2",
        ring1 = "Sroda Ring",
        ring2 = "Gere Ring",
        back = "Artio's Mantle",
    }
    sets.WS["Mistral Axe"] = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.WS.Rampage = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.WS.Ruinator = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.engaged.tp = {
        main = "Spalirisos",
        sub = "Ikenga's Axe",
        ammo = "Coiste Bodhar",
        head = "Duty Crown",
        body = "Duty Cyclas",
        hands = "Duty Gauntlets",
        legs = "Duty Flanchard",
        feet = "Duty Sollerets",
        neck = "Beastmaster Collar +2",
        waist = "Sailfi Belt +1",
        ear1 = "Sherida Earring",
        ear2 = "Dedition Earring",
        ring1 = "Epona's Ring",
        ring2 = "Gere Ring",
        back = "Null Shawl",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Aymur",
        ammo = "Staunch Tathlum +1",
        head = "Totemic Helm +4",
        body = "Nukumi Gausape +3",
        hands = "Ankusa Gloves +4",
        legs = "Ankusa Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Artio's Mantle",
    }
    sets.idle.maxhp = {
        main = "Aymur",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Beastmaster Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Artio's Mantle",
    }
    sets.idle.mdt = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.idle.movement = {
        main = "Aymur",
        ammo = "Staunch Tathlum +1",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Aymur",
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
        back = "Artio's Mantle",
    }
    sets.idle.town = {
        main = "Aymur",
        ammo = "Staunch Tathlum +1",
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== pet =====
    sets.pet.dt = {
        head = "Ankusa Helm +4",
        body = "Ankusa Jackcoat +4",
        hands = "Ankusa Gloves +4",
        legs = "Ankusa Trousers +4",
        feet = "Ankusa Gaiters +4",
        neck = "Beastmaster Collar +2",
        waist = "Incarnation Sash",
        back = "Artio's Mantle",
    }
    sets.pet.ready = {
        head = "Nukumi Cabasset +3",
        body = "Nukumi Gausape +3",
        hands = "Nukumi Manoplas +3",
        legs = "Nukumi Quijotes +3",
        feet = "Nukumi Ocreae +3",
        neck = "Beastmaster Collar +2",
        waist = "Incarnation Sash",
        back = "Artio's Mantle",
    }
    sets.pet.reward = {
        head = "Totemic Helm +4",
        body = "Totemic Jackcoat +4",
        hands = "Totemic Gloves +4",
        legs = "Totemic Trousers +4",
        feet = "Totemic Gaiters +4",
        neck = "Beastmaster Collar +2",
        back = "Artio's Mantle",
    }
    sets.pet.tp = {
        head = "Nukumi Cabasset +3",
        body = "Nukumi Gausape +3",
        hands = "Nukumi Manoplas +3",
        legs = "Nukumi Quijotes +3",
        feet = "Nukumi Ocreae +3",
        neck = "Beastmaster Collar +2",
        waist = "Incarnation Sash",
        ring1 = "Epona's Ring",
        back = "Artio's Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["Dolichenus-Farsha"] = {
        main = "Dolichenus",
        sub = "Farsha",
    }
    sets.weaponset["Spalirisos-Ikenga"] = {
        main = "Spalirisos",
        sub = "Ikenga's Axe",
    }
    sets.weaponset["Triedge-Ikenga"] = {
        main = "Tri-edge",
        sub = "Ikenga's Axe",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

