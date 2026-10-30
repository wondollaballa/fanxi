--[[
    Fanxi GearSwap library — Onedough DRK
    Updated 2026-10-29 02:01:23
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/DRK.lua

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
    sets.WS.Fimbulvetr = {
        main = "Helheim",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Heathen's Burgeonet +3",
        body = "Ignominy Cuirass +4",
        hands = "Nyame Gauntlets",
        legs = "Fallen's Flanchard +4",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Heath. Earring +2",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Ankou's Mantle",
    }
    sets.WS.Origin = {
        main = "Foenaria",
        sub = "Utu Grip",
        ammo = "Knobkierrie",
        head = "Heathen's Burgeonet +3",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Heathen's Sollerets +3",
        neck = "Abyssal Bead Necklace +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Heath. Earring +2",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
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
        head = "Sworn Crown",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Sworn Sabatons",
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
        head = "Sworn Crown",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Sworn Sabatons",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = "Ankou's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.Foenaria = {
        main = "Foenaria",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Flam. Zucchetto +2",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Vim Torque +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Schere Earring",
        ear2 = "Dedition Earring",
        ring1 = "Niqmaddu Ring",
        ring2 = "Chirich Ring +1",
        back = "Null Shawl",
    }
    sets.engaged.Helheim = {
        main = "Helheim",
        sub = "Utu Grip",
        ammo = "Aurgelmir Orb +1",
        head = "Flam. Zucchetto +2",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Vim Torque +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Schere Earring",
        ear2 = "Dedition Earring",
        ring1 = "Niqmaddu Ring",
        ring2 = "Chirich Ring +1",
        back = "Null Shawl",
    }
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
        head = "Sworn Crown",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sworn Sabatons",
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
        head = "Sworn Crown",
        body = "Heathen's Cuirass +3",
        hands = "Fallen's Finger Gauntlets +4",
        legs = "Fallen's Flanchard +4",
        feet = "Sworn Sabatons",
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

