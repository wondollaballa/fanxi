--[[
    Fanxi GearSwap library — Onedough SCH
    Updated 2026-10-23 01:26:20
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/SCH.lua

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
    sets.JA.Accession = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Arbatel Bracers +3",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Alacrity = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Celerity = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Ebullience = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Pedagogy Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Focalization = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Immanence = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Pedagogy Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Manifestation = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Arbatel Gown +3",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Parsimony = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Pedagogy Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Perpetuance = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Arbatel Pants +3",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA.Rapture = {
        main = "Tupsimati",
        sub = "Pole Grip",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        back = "Lugh's Cape",
    }
    sets.JA["Tabula Rasa"] = {
        head = "Pedagogy Mortarboard +4",
        body = "Pedagogy Gown +4",
        hands = "Pedagogy Bracers +4",
        legs = "Pedagogy Pants +4",
        feet = "Pedagogy Loafers +4",
        neck = "Argute Stole +2",
        waist = "Witful Belt",
        back = "Lugh's Cape",
    }

    -- ===== Limbus =====
    sets.Limbus.indomitable_cast = {
        head = "Indom. Petasos",
        body = "Indomitable Coat",
        hands = "Indom. Gloves",
        legs = "Indom. Tonban",
        feet = "Indom. Sabots",
    }

    -- ===== Odyssey =====
    sets.Odyssey.agwu = {
        head = "Agwu's Cap",
        body = "Agwu's Robe",
        hands = "Agwu's Gages",
        legs = "Agwu's Slops",
        feet = "Agwu's Pigaches",
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

    -- ===== WS =====
    sets.WS.Cataclysm = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Lugh's Cape",
    }
    sets.WS.Omniscience = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.WS.Shattersoul = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.WS.Vidohunir = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Orpheus's Sash",
        ear1 = "Friomisi Earring",
        ear2 = "Moonshade Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = "Lugh's Cape",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.engaged.hybrid = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.engaged.tp = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Arbatel Gown +3",
        hands = "Pedagogy Bracers +4",
        legs = "Pedagogy Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Lugh's Cape",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Arbatel Gown +3",
        hands = "Pedagogy Bracers +4",
        legs = "Pedagogy Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Lugh's Cape",
    }
    sets.idle.dt_indom = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Indom. Petasos",
        body = "Indomitable Coat",
        hands = "Indom. Gloves",
        legs = "Indom. Tonban",
        feet = "Indom. Sabots",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Lugh's Cape",
    }
    sets.idle.maxhp = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Lugh's Cape",
    }
    sets.idle.mdt = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.idle.movement = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Hippomenes Socks +1",
        neck = "Argute Stole +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Tupsimati",
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
        back = "Lugh's Cape",
    }
    sets.idle.refresh = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Lugh's Cape",
    }
    sets.idle.town = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Hippomenes Socks +1",
        neck = "Argute Stole +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast["Dark Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Digni. Earring",
        ear2 = "Enchntr. Earring +1",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Lugh's Cape",
    }
    sets.midcast["Divine Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
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
        back = "Lugh's Cape",
    }
    sets.midcast["Elemental Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Indom. Petasos",
        body = "Indomitable Coat",
        hands = "Nyame Gauntlets",
        legs = "Indom. Tonban",
        feet = "Arbatel Loafers +3",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = "Lugh's Cape",
    }
    sets.midcast["Elemental Magic MB"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = "Lugh's Cape",
    }
    sets.midcast["Elemental Magic Macc"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = "Indom. Petasos",
        body = "Indomitable Coat",
        hands = "Indom. Gloves",
        legs = "Indom. Tonban",
        feet = "Indom. Sabots",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Lugh's Cape",
    }
    sets.midcast["Enfeebling Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = "Nyame Helm",
        body = "Indomitable Coat",
        hands = "Indom. Gloves",
        legs = "Indom. Tonban",
        feet = "Nyame Sollerets",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Lugh's Cape",
    }
    sets.midcast["Enhancing Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Pedagogy Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Lugh's Cape",
    }
    sets.midcast["Healing Magic"] = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Academic's Gown +4",
        hands = "Academic's Bracers +4",
        legs = "Academic's Pants +4",
        feet = "Academic's Loafers +4",
        neck = "Argute Stole +2",
        waist = "Witful Belt",
        ear1 = "Halasz Earring",
        ear2 = "Tuisto Earring",
        ring1 = "Gelatinous Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Lugh's Cape",
    }
    sets.midcast.Helix = {
        main = "Tupsimati",
        sub = "Pole Grip",
        ammo = "Pemphredo Tathlum",
        head = "Indom. Petasos",
        body = "Indomitable Coat",
        hands = "Arbatel Bracers +3",
        legs = "Indom. Tonban",
        feet = "Arbatel Loafers +3",
        neck = "Argute Stole +2",
        waist = "Eschan Stone",
        ear1 = "Digni. Earring",
        ear2 = "Enchntr. Earring +1",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Lugh's Cape",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Academic's Mortarboard +4",
        body = "Indomitable Coat",
        hands = "Academic's Bracers +4",
        legs = "Indom. Tonban",
        feet = "Academic's Loafers +4",
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Lugh's Cape",
    }

    -- ===== weaponset =====
    sets.weaponset.OnionSwordIII = {
        main = "Onion Sword III",
        sub = "Genbu's Shield",
    }
    sets.weaponset.Opashoro = {
        main = "Opashoro",
        sub = "Pole Grip",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

