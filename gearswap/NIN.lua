--[[
    Fanxi GearSwap library — Onedough NIN
    Updated 2026-10-23 11:20:35
    The launcher writes sets back to this file; the first copy is kept as a .bak.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/NIN.lua

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
    sets.JA.Innin = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Mochizuki Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA.Migawari = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hattori Tekko +3",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA["Mijin Gakure"] = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Mochizuki Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA["Tonko: Ni"] = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA["Utsusemi: Ichi"] = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA["Utsusemi: Ni"] = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
    }
    sets.JA.Yonin = {
        main = "Kikoku",
        sub = "Nagi",
        head = "Mochizuki Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        back = "Andartia's Mantle",
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
    sets.Odyssey.weapon = {
        main = "Gleti's Knife",
    }

    -- ===== WS =====
    sets.WS["Blade: Hi"] = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.WS["Blade: Kamu"] = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.WS["Blade: Ku"] = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.WS["Blade: Shun"] = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.WS["Blade: Ten"] = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }

    -- ===== engaged =====
    sets.engaged.acc = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.engaged.dw = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Aurgelmir Orb +1",
        head = "Hachiya Hatsuburi +4",
        body = "Hattori Ningi +3",
        hands = "Mochizuki Tekko +4",
        legs = "Mochizuki Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Suppanomimi",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Andartia's Mantle",
    }
    sets.engaged.hybrid = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Aurgelmir Orb +1",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Revelation Gaunt.",
        legs = "Revelation Brais",
        feet = "Revelation Sab.",
        neck = "Unmoving Collar +1",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Andartia's Mantle",
    }
    sets.engaged.tp = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Aurgelmir Orb +1",
        head = "Revelation Masque",
        body = "Revelation Plate.",
        hands = "Revelation Gaunt.",
        legs = "Revelation Brais",
        feet = "Revelation Sab.",
        neck = "Ninja Nodowa +2",
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = "Dedition Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = "Andartia's Mantle",
    }

    -- ===== idle =====
    sets.idle.dt = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Staunch Tathlum +1",
        head = "Hachiya Hatsuburi +4",
        body = "Hattori Ningi +3",
        hands = "Mochizuki Tekko +4",
        legs = "Mochizuki Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Unmoving Collar +1",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Andartia's Mantle",
    }
    sets.idle.maxhp = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Staunch Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Ninja Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Defending Ring",
        ring2 = "Gelatinous Ring +1",
        back = "Andartia's Mantle",
    }
    sets.idle.mdt = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.idle.movement = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Staunch Tathlum +1",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }
    sets.idle.pdt = {
        main = "Kikoku",
        sub = "Nagi",
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
        back = "Andartia's Mantle",
    }
    sets.idle.town = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Staunch Tathlum +1",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Odnowa Earring +1",
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== midcast =====
    sets.midcast.Ninjutsu = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Pemphredo Tathlum",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Hachiya Tekko +4",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Ninja Nodowa +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = "Andartia's Mantle",
    }
    sets.midcast["Ninjutsu Damage"] = {
        main = "Kikoku",
        sub = "Nagi",
        ammo = "Ghastly Tathlum +1",
        head = "Nyame Helm",
        body = "Nyame Mail",
        hands = "Nyame Gauntlets",
        legs = "Nyame Flanchard",
        feet = "Nyame Sollerets",
        neck = "Ninja Nodowa +2",
        waist = "Eschan Stone",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = "Andartia's Mantle",
    }

    -- ===== precast =====
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = "Hachiya Hatsuburi +4",
        body = "Hachiya Chainmail +4",
        hands = "Leyline Gloves",
        legs = "Hachiya Hakama +4",
        feet = "Hachiya Kyahan +4",
        neck = "Orunmila's Torque",
        waist = "Audumbla Sash",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = "Andartia's Mantle",
    }

    -- ===== weaponset =====
    sets.weaponset["Dokoku-Yagyu"] = {
        main = "Dokoku",
        sub = "Yagyu Darkblade",
    }
end

-- Fanxi launcher; this file is the loaded job library. The first copy was kept as a .bak.

