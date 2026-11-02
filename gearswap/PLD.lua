--[[
    Fanxi GearSwap library — Onedough PLD
    Updated 2026-10-30 11:07:55
    This is the server template; each account edits its own copy after first use.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/PLD.lua

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
    sets.JA.Chivalry = {
        main = "Excalibur",
        sub = "Aegis",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Cover = {
        ammo = "Sapience Orb",
        head = "Reverence Coronet +4",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA["Divine Emblem"] = {
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Fealty = {
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA["Holy Circle"] = {
        feet = "Reverence Leggings +4",
    }
    sets.JA.Invincible = {
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Majesty = {
        main = "Excalibur",
        sub = "Aegis",
        ammo = "Sapience Orb",
        head = "Reverence Coronet +4",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Provoke = {
        main = "Excalibur",
        sub = "Aegis",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Rampart = {
        ammo = "Sapience Orb",
        head = "Caballarius Coronet +4",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA.Sentinel = {
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Caballarius Leggings +4",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.JA["Shield Bash"] = {
        sub = "Aegis",
        ammo = "Sapience Orb",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Knightly Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Fenian Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
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
        main = "Sakpata's Sword",
    }

    -- ===== WS =====
    sets.WS.Atonement = {
        main = "Excalibur",
        sub = "Aegis",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS["Chant du Cygne"] = {
        main = "Almace",
        sub = "Blurred Shield +1",
        ammo = "Coiste Bodhar",
        head = "Blistering Sallet +1",
        body = "Sakpata's Breastplate",
        hands = "Sworn Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sworn Sabatons",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Hoxne Earring",
        ear2 = "Lugra Earring +1",
        ring1 = "Hetairoi Ring",
        ring2 = "Regal Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS.Expiacion = {
        main = "Excalibur",
        sub = "Aegis",
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
        back = "Rudianos's Mantle",
    }
    sets.WS.Fimbulvetr = {
        main = "Helheim",
        sub = "Rigorous Grip +1",
        ammo = "Crepuscular Pebble",
        head = "Sakpata's Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Sroda Ring",
        ring2 = "Epaminondas's Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS.Imperator = {
        main = "Caliburnus",
        sub = "Blurred Shield +1",
        ammo = "Crepuscular Pebble",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Knight's Bead Necklace +2",
        waist = "Kentarch Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Epaminondas's Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS["Knights of Round"] = {
        main = "Excalibur",
        sub = "Blurred Shield +1",
        ammo = "Crepuscular Pebble",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Sakpata's Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Fotia Gorget",
        waist = "Sailfi Belt +1",
        ear1 = "Thrud Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Epaminondas's Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS.Requiescat = {
        main = "Sequence",
        sub = "Duban",
        ammo = "Crepuscular Pebble",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sworn Sabatons",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Alabaster Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Metamorph Ring +1",
        back = "Rudianos's Mantle",
    }
    sets.WS["Savage Blade"] = {
        main = "Naegling",
        sub = "Blurred Shield +1",
        ammo = "Coiste Bodhar",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Rep. Plat. Medal",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Epaminondas's Ring",
        back = "Rudianos's Mantle",
    }
    sets.WS.Torcleaver = {
        main = "Caladbolg",
        sub = "Rigorous Grip +1",
        ammo = "Crepuscular Pebble",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Knight's Bead Necklace +2",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Thrud Earring",
        ring1 = "Sroda Ring",
        ring2 = "Epaminondas's Ring",
        back = "Rudianos's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Excalibur",
        sub = "Aegis",
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
        back = "Rudianos's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Excalibur",
        sub = "Aegis",
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
        back = "Weard Mantle",
    }
    sets.engaged.tp = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Aurgelmir Orb +1",
        head = "Sulevia's Mask +2",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Volte Tights",
        feet = "Sworn Sabatons",
        neck = "Vim Torque +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Alabaster Earring",
        ear2 = "Dedition Earring",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
        back = "Rudianos's Mantle",
    }

    -- ===== enmity =====
    sets.enmity.up = {
        main = "Excalibur",
        sub = "Aegis",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Caballarius Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Chevalier's Cuirass +3",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Reverence Leggings +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Weard Mantle",
    }
    sets.idle.maxhp = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Sakpata's Helm",
        body = "Sakpata's Breastplate",
        hands = "Sakpata's Gauntlets",
        legs = "Sakpata's Cuisses",
        feet = "Sakpata's Leggings",
        neck = "Knight's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Weard Mantle",
    }
    sets.idle.mdt = {
        main = "Burtgang",
        sub = "Aegis",
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
        back = "Weard Mantle",
    }
    sets.idle.movement = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Reverence Surcoat +4",
        hands = "Reverence Gauntlets +4",
        legs = "Carmine Cuisses +1",
        feet = "Hippomenes Socks +1",
        neck = "Knight's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Burtgang",
        sub = "Aegis",
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
        back = "Weard Mantle",
    }
    sets.idle.refresh = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Reverence Surcoat +4",
        hands = "Reverence Gauntlets +4",
        legs = "Reverence Breeches +4",
        feet = "Reverence Leggings +4",
        neck = "Knight's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Rudianos's Mantle",
    }
    sets.idle.town = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Reverence Surcoat +4",
        hands = "Reverence Gauntlets +4",
        legs = "Reverence Breeches +4",
        feet = "Hippomenes Socks +1",
        neck = "Knight's Bead Necklace +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast["Divine Magic"] = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Incanter's Torque",
        waist = "Eschan Stone",
        ear1 = "Halasz Earring",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Enhancing Magic"] = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Caballarius Surcoat +4",
        hands = "Reverence Gauntlets +4",
        legs = "Reverence Breeches +4",
        feet = "Reverence Leggings +4",
        neck = "Knight's Bead Necklace +2",
        waist = "Audumbla Sash",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Healing Magic"] = {
        main = "Burtgang",
        sub = "Aegis",
        ammo = "Staunch Tathlum +1",
        head = "Reverence Coronet +4",
        body = "Reverence Surcoat +4",
        hands = "Reverence Gauntlets +4",
        legs = "Reverence Breeches +4",
        feet = "Reverence Leggings +4",
        neck = "Knight's Bead Necklace +2",
        waist = "Asklepian Belt",
        ear1 = "Nourishing Earring +1",
        ear2 = "Tuisto Earring",
        ring1 = "Gelatinous Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Rudianos's Mantle",
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
        waist = "Audumbla Sash",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Rudianos's Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["Caliburnus-Blurred"] = {
        main = "Caliburnus",
        sub = "Blurred Shield +1",
    }
    sets.weaponset.Helheim = {
        main = "Helheim",
        sub = "Pole Grip",
    }
    sets.weaponset["Naegling-Blurred"] = {
        main = "Naegling",
        sub = "Blurred Shield +1",
    }
end

-- Fanxi template; each account has its own editable copy of this library.

