--[[
    Fanxi GearSwap library — Onedough WAR
    Updated 2026-10-31 23:17:16
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/WAR.lua

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
    sets.weaponset = {}
    sets.WS = {}

    -- ===== JA =====
    sets.JA.Aggressor = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Pummeler's Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA.Berserk = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Pummeler's Lorica +4",
        hands = "Pummeler's Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA["Mighty Strikes"] = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Agoge Calligae +4",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA.Provoke = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA.Retaliation = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Agoge Calligae +4",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA.Tomahawk = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Pummeler's Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }
    sets.JA.Warcry = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }

    -- ===== Limbus =====
    sets.Limbus.revelation_tp = {
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Revelation Gaunt.",
        legs = "Revelation Brais",
        feet = "Revelation Sab.",
    }
    sets.Limbus.revelation_ws = {
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Revelation Gaunt.",
        legs = "Revelation Brais",
        feet = "Revelation Sab.",
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
        main = "Agwu's Claymore",
    }

    -- ===== WS =====
    sets.WS.Cloudsplitter = {
        main = "Farsha",
        sub = "Diamond Aspis",
        ammo = "Knobkierrie",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Baetyl Pendant",
        waist = "Orpheus's Sash",
        ear1 = "Moonshade Earring",
        ear2 = "Friomisi Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Beithir Ring",
        back = "Cichol's Mantle",
    }
    sets.WS.Decimation = {
        main = "Dolichenus",
        sub = "Farsha",
        ammo = "Coiste Bodhar",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Sakpata's Gauntlets",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Warrior's Bead Necklace +2",
        waist = "Fotia Belt",
        ear1 = "Schere Earring",
        ear2 = "Boii Earring +2",
        ring1 = "Niqmaddu Ring",
        ring2 = "Sroda Ring",
        back = "Cichol's Mantle",
    }
    sets.WS.Disaster = {
        main = "Laphria",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Sakpata's Breastplate",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Nyame Sollerets",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Cichol's Mantle",
    }
    sets.WS.Fimbulvetr = {
        main = "Helheim",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Sakpata's Breastplate",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Nyame Sollerets",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Impulse Drive"] = {
        main = "Shining One",
        sub = "Utu Grip",
        ammo = "Yetshila +1",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Hoxne Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Regal Ring",
        ring2 = "Niqmaddu Ring",
        back = "Alabaster Mantle",
    }
    sets.WS["King's Justice"] = {
        main = "Conqueror",
        sub = "Utu Grip",
        ammo = "Crepuscular Pebble",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Fotia Gorget",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Niqmaddu Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Metatron Torment"] = {
        main = "Bravura",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Revelation Plate.",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Hoxne Earring",
        ear2 = "Thrud Earring",
        ring1 = "Sroda Ring",
        ring2 = "Niqmaddu Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Mistral Axe"] = {
        main = "Ikenga's Axe",
        sub = "Blurred Shield +1",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Revelation Plate.",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Sroda Ring",
        ring2 = "Niqmaddu Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Raging Rush"] = {
        main = "Ukonvasara",
        sub = "Utu Grip",
        ammo = "Yetshila +1",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Revelation Gaunt.",
        legs = "Boii Cuisses +3",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Hoxne Earring",
        ear2 = "Boii Earring +2",
        ring1 = "Begrudging Ring",
        ring2 = "Niqmaddu Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Savage Blade"] = {
        main = "Naegling",
        sub = "Blurred Shield +1",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Sakpata's Breastplate",
        hands = "Boii Mufflers +3",
        legs = "Boii Cuisses +3",
        feet = "Nyame Sollerets",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Cichol's Mantle",
    }
    sets.WS["Ukko's Fury"] = {
        main = "Ukonvasara",
        sub = "Utu Grip",
        ammo = "Yetshila +1",
        head = "Revelation Masque",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Boii Cuisses +3",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Hoxne Earring",
        ear2 = "Boii Earring +2",
        ring1 = "Niqmaddu Ring",
        ring2 = "Regal Ring",
        back = "Alabaster Mantle",
    }
    sets.WS.Upheaval = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Agoge Mask +4",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Boii Cuisses +3",
        feet = "Revelation Sab.",
        neck = "Warrior's Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Cichol's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Chango",
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
        back = "Cichol's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
        neck = "Unmoving Collar +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Cichol's Mantle",
    }
    sets.engaged.tp = {
        ammo = "Coiste Bodhar",
        head = "Hjarrandi Helm",
        body = "Revelation Plate.",
        hands = "Sakpata's Gauntlets",
        legs = "Revelation Brais",
        feet = "Pummeler's Calligae +4",
        neck = "Vim Torque +1",
        waist = "Ioskeha Belt +1",
        ear1 = "Schere Earring",
        ear2 = "Dedition Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Niqmaddu Ring",
        back = "Null Shawl",
    }

    -- ===== enmity =====
    sets.enmity.up = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Sapience Orb",
        head = "Agoge Mask +4",
        body = "Agoge Lorica +4",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Boii Calligae +3",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Cichol's Mantle",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Pummeler's Mask +4",
        body = "Boii Lorica +3",
        hands = "Agoge Mufflers +4",
        legs = "Agoge Cuisses +4",
        feet = "Pummeler's Calligae +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Cichol's Mantle",
    }
    sets.idle.maxhp = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Cichol's Mantle",
    }
    sets.idle.mdt = {
        main = "Chango",
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
        back = "Cichol's Mantle",
    }
    sets.idle.movement = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Pummeler's Mask +4",
        body = "Pummeler's Lorica +4",
        hands = "Pummeler's Mufflers +4",
        legs = "Pummeler's Cuisses +4",
        feet = "Pummeler's Calligae +4",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Chango",
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
        back = "Cichol's Mantle",
    }
    sets.idle.town = {
        main = "Chango",
        sub = "Utu Grip",
        ammo = "Staunch Tathlum +1",
        head = "Pummeler's Mask +4",
        body = "Pummeler's Lorica +4",
        hands = "Pummeler's Mufflers +4",
        legs = "Pummeler's Cuisses +4",
        feet = "Pummeler's Calligae +4",
        neck = "Warrior's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset.Helheim = {
        main = "Helheim",
        sub = "Utu Grip",
    }
    sets.weaponset["Shining One"] = {
        main = "Shining One",
        sub = "Utu Grip",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

