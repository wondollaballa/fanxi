--[[
    Fanxi GearSwap library — Onedough PLD
    Updated 2026-11-05 17:10:00
    This is the server template; each account edits its own copy after first use.
    Source: /Users/wondochoung/Documents/GitHub/fanxi/gearswap/PLD.lua

    Each set holds only slot = "Item" pairs so Fanxi lists every one;
    to add a variant, copy an existing set and give it a new path.

    The magic sets follow BG Wiki's Community Paladin Guide
    (https://www.bg-wiki.com/ffxi/Community_Paladin_Guide), sections
    "Magic Casting Sets" and "New and/or Returning Players Sets".  Paladin's
    spells are not one build each, so the Spells panel has a row per kind and
    binds the set below to it (docs/pld.md has the reasoning and the table):

      spell                      set                              what it reads
      ---------------------------------------------------------------------------
      Banish / Holy              sets.midcast["Divine Magic"]     Magic Attack, MND
      Flash                      sets.midcast.Flash               Enmity, Fast Cast
      Flash (SIRD)               sets.midcast["Flash SIRD"]       interruption rate
      Enlight / Enlight II       sets.midcast.Enspell             Divine Magic skill
      Cure III / IV              sets.midcast["Healing Magic"]    potency + received
      Cure (SIRD)                sets.midcast["Cure SIRD"]        interruption rate
      Protect / Shell / Crusade  sets.midcast["Enhancing Magic"]  duration
      Aquaveil (via /SCH)        sets.midcast["Enhancing Magic SIRD"]
      Stoneskin (via /SCH)       sets.midcast["Enhancing Magic Stoneskin"]
      Phalanx                    sets.midcast.Phalanx              Enhancing skill
      Phalanx (SIRD)             sets.midcast["Phalanx SIRD"]     interruption rate
      Reprisal                   sets.midcast.Reprisal            Enmity, duration
      Reprisal (SIRD)            sets.midcast["Reprisal SIRD"]    interruption rate

    The SIRD variants are separate leaves on purpose: the Spells panel's row
    for the spell points at the ordinary build, and the row can be repointed at
    the SIRD build when a fight needs the cast to finish under fire.

    Job abilities follow the guide's "Noteworthy Equipment" column: Chivalry
    and Shield Bash want the Caballarius Gauntlets, Rampart the Caballarius
    Coronet, Fealty the Caballarius Surcoat, Cover the Reverence Coronet and
    Caballarius Surcoat, Invincible the Caballarius Breeches, Holy Circle the
    Reverence Leggings, Divine Emblem the Chevalier's Sabatons and Sentinel the
    Caballarius Leggings.  Palisade, Intervene and Sepulcher have no guide gear
    of their own, so they wear the enmity build (Sepulcher the cure build).

    The Odyssean pieces below are Oseem's Arcane Glyptics work (Norg I-7): the
    base Reisenjima armor is fixed, and its value comes from the rolled augments
    (Pellucid / Fern / Taupe stones, or Dark Matter for the "technique" pool).
    The guide names the rolls it wants, so `local oseem` carries those builds as
    GearSwap's { name = ..., augments = {...} } tables.  The Phalanx and SIRD
    lines are Dark Matter (technique) rolls; Cure Potency, Fast Cast and the
    base stats are the standard stone rows (Fern caps the first two at 6/5).
]]

-- Oseem augmented Odyssean builds the guide asks for.  The same base piece is
-- reused with different rolls, which is what the augment list is for.
local oseem = {
    -- Dark Matter: Phalanx +5.  The standard path tables do not offer Phalanx.
    helm_phalanx = { name = "Odyssean Helm", augments = {'"Phalanx"+5'} },
    chest_phalanx = { name = "Odyss. Chestplate", augments = {'"Phalanx"+5'} },
    feet_phalanx = { name = "Odyssean Greaves", augments = {'"Phalanx"+5'} },
    -- Dark Matter: the capped Stoneskin build's SIRD-11 on the base-stat rows.
    feet_stoneskin = { name = "Odyssean Greaves",
        augments = {"MND+3", "Accuracy+2", "Attack+2", "Spell interruption rate down-11%"} },
    -- Standard Magic path: Cure Potency +5 (and +6 with a Fern stone) ...
    feet_cure = { name = "Odyssean Greaves", augments = {'"Cure Potency"+5%'} },
    -- ... and Fast Cast +6 with a Fern stone.
    feet_fastcast = { name = "Odyssean Greaves", augments = {'"Fast Cast"+6'} },
}

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
    -- Intervene is a single hit whose damage is enhanced by enmity, so it wears the
    -- enmity build rather than the TP set.  The guide lists no gear of its own.
    sets.JA.Intervene = {
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
    -- Palisade has no guide gear note; it is a pure enmity action (900 CE / 1,800 VE),
    -- so it wears the same enmity build as Provoke and the default JA set below.
    sets.JA.Palisade = {
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
    -- Sepulcher revives a fallen party member; the guide has no gear note, so it wears the
    -- cure build (potency and cure received) to keep the raise as strong as it can be.
    sets.JA.Sepulcher = {
        ammo = "Egoist's Tathlum",
        head = "Chevalier's Armet +3",
        body = "Souv. Cuirass +1",
        hands = "Souv. Handsch. +1",
        legs = "Sworn Brais",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Sroda Belt",
        ear1 = "Alabaster Earring",
        ear2 = "Nourishing Earring +1",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
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
    -- The Community Paladin Guide's magic sets.  The Spells panel binds one row per spell
    -- kind, so a Flash cast wears sets.midcast.Flash and a Phalanx cast sets.midcast.Phalanx
    -- with no per-spell card.  Each SIRD variant is a separate leaf: repoint the row at it
    -- when the cast has to finish under incoming hits.
    sets.midcast["Divine Magic"] = {
        -- Banish / Holy.  Magic Attack and MND on the magic-accuracy frame.
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
    sets.midcast.Flash = {
        -- Guide "Magic Casting Sets → Flash": Enmity+112 and Fast Cast+25%.
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Reverence Surcoat +4",
        hands = "Caballarius Gauntlets +4",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Trux Earring",
        ear2 = "Cryptic Earring",
        ring1 = "Vexer Ring +1",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Flash SIRD"] = {
        -- Guide "Flash SIRD": the SIRD pieces replace the enmity accessories on the same frame.
        ammo = "Staunch Tathlum +1",
        head = "Souv. Schaller +1",
        body = "Chevalier's Cuirass +3",
        hands = "Caballarius Gauntlets +4",
        legs = "Founder's Hose",
        feet = "Chevalier's Sabatons +3",
        neck = "Moonlight Necklace",
        waist = "Audumbla Sash",
        ear1 = "Alabaster Earring",
        ear2 = "Cryptic Earring",
        ring1 = "Vexer Ring +1",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast.Enspell = {
        -- Enlight / Enlight II (guide "Enlight Sets"): Divine Magic skill carries the extra
        -- physical accuracy and Brilliance adds Enlight damage.
        main = "Brilliance",
        head = "Jumalik Helm",
        body = "Reverence Surcoat +4",
        hands = "Eschite Gauntlets",
        neck = "Incanter's Torque",
        waist = "Asklepian Belt",
        ear1 = "Knight's Earring",
        ear2 = "Saxnot Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = "Altruistic Cape",
    }
    sets.midcast["Healing Magic"] = {
        -- Guide "Magic Casting Sets → Cures": Cure Potency 50%, Cure Received 30%, DT-50%.
        ammo = "Egoist's Tathlum",
        head = "Chevalier's Armet +3",
        body = "Souv. Cuirass +1",
        hands = "Souv. Handsch. +1",
        legs = "Sworn Brais",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Sroda Belt",
        ear1 = "Alabaster Earring",
        ear2 = "Nourishing Earring +1",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Cure SIRD"] = {
        -- Guide "Cure (SIRD)": the same potency on the interruption-rate pieces, for a cure
        -- that has to land while the tank is being hit.  The Greaves carry the standard
        -- Oseem Cure Potency roll (the piece's own Cure potency and SIRD are its base).
        ammo = "Staunch Tathlum +1",
        head = "Souv. Schaller +1",
        body = "Souv. Cuirass +1",
        hands = "Macabre Gaunt. +1",
        legs = "Founder's Hose",
        feet = oseem.feet_cure,
        neck = "Moonlight Necklace",
        waist = "Audumbla Sash",
        ear1 = "Alabaster Earring",
        ear2 = "Nourishing Earring +1",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Enhancing Magic"] = {
        -- Protect, Shell, Crusade (and Blink when a /SCH subjob brings it).  The guide's
        -- Enhancing duration pieces - Colada, Ajax +1, Shab. Cuirass +1, Regal Gauntlets -
        -- on the enmity frame, because these are the casts a tank makes while holding hate.
        main = "Colada",
        sub = "Ajax +1",
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Shab. Cuirass +1",
        hands = "Regal Gauntlets",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Alabaster Earring",
        ring1 = "Supershear Ring",
        ring2 = "Eihwaz Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Enhancing Magic SIRD"] = {
        -- Aquaveil (PLD/SCH): guide "Spell Interruption Rate Down", Escha Path C route.
        ammo = "Staunch Tathlum +1",
        head = "Eschite Helm",
        body = "Eschite Breast.",
        hands = "Eschite Gauntlets",
        legs = "Eschite Cuisses",
        feet = "Eschite Greaves",
        neck = "Moonlight Necklace",
        waist = "Audumbla Sash",
        ear1 = "Knightly Earring",
        ear2 = "Nourishing Earring +1",
        ring1 = "Evanescence Ring",
        ring2 = "Murky Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Enhancing Magic Stoneskin"] = {
        -- Stoneskin (PLD/SCH), guide "Sets by Alimere → Capped Stoneskin and SIRD": every
        -- Stoneskin+ piece while the gear SIRD alone reaches the 102% interruption cap.
        ammo = "Staunch Tathlum +1",
        head = "Souv. Schaller +1",
        body = "Chevalier's Cuirass +3",
        hands = "Stone Mufflers",
        legs = "Haven Hose",
        feet = oseem.feet_stoneskin,
        neck = "Stone Gorget",
        waist = "Siegel Sash",
        ear1 = "Knightly Earring",
        ear2 = "Earthcry Earring",
        ring1 = "Evanescence Ring",
        ring2 = "Murky Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast.Phalanx = {
        -- Guide "Sets by Alimere → Max Self Phalanx": 445 Enhancing skill passes the 443 tier
        -- (-33 damage) and the Phalanx+ pieces take it to -71.  The Odyssean Helm needs
        -- Oseem's Dark Matter Phalanx roll; the Moonlight Rings are HP filler the guide
        -- leaves implicit.
        main = "Sakpata's Sword",
        sub = "Priwen",
        head = oseem.helm_phalanx,
        body = "Sworn Platemail",
        hands = "Souv. Handsch. +1",
        legs = "Sakpata's Cuisses",
        feet = "Souveran Schuhs +1",
        neck = "Hoxne Torque",
        waist = "Olympus Sash",
        ear1 = "Mimir Earring",
        ear2 = "Andoaa Earring",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
        back = "Weard Mantle",
    }
    sets.midcast["Phalanx SIRD"] = {
        -- Guide "Phalanx SIRD": the body is Odyssean (the server spells it
        -- "Odyss. Chestplate") and both it and the Greaves carry Oseem's Dark Matter
        -- Phalanx roll, which is where the set's Phalanx+ comes from.
        ammo = "Staunch Tathlum +1",
        head = "Souv. Schaller +1",
        body = oseem.chest_phalanx,
        hands = "Souv. Handsch. +1",
        legs = "Founder's Hose",
        feet = oseem.feet_phalanx,
        neck = "Moonlight Necklace",
        waist = "Audumbla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Tuisto Earring",
        ring1 = "Moonlight Ring",
        ring2 = "Moonlight Ring",
        back = "Weard Mantle",
    }
    sets.midcast.Reprisal = {
        -- Guide "Magic Casting Sets → Reprisal": Enmity+79, Fast Cast+15%, DT-50%.
        ammo = "Sapience Orb",
        head = "Loess Barbuta +1",
        body = "Shab. Cuirass +1",
        hands = "Regal Gauntlets",
        legs = "Caballarius Breeches +4",
        feet = "Chevalier's Sabatons +3",
        neck = "Knight's Bead Necklace +2",
        waist = "Creed Baudrier",
        ear1 = "Cryptic Earring",
        ear2 = "Alabaster Earring",
        ring1 = "Moonlight Ring",
        ring2 = "Murky Ring",
        back = "Rudianos's Mantle",
    }
    sets.midcast["Reprisal SIRD"] = {
        -- Guide "Reprisal (SIRD)": the interruption-rate frame for the same ability, with the
        -- Greaves carrying the standard Oseem Fast Cast roll the guide lists.
        ammo = "Sapience Orb",
        head = "Souv. Schaller +1",
        body = "Shab. Cuirass +1",
        hands = "Regal Gauntlets",
        legs = "Founder's Hose",
        feet = oseem.feet_fastcast,
        neck = "Moonlight Necklace",
        waist = "Audumbla Sash",
        ear1 = "Cryptic Earring",
        ear2 = "Alabaster Earring",
        ring1 = "Moonlight Ring",
        ring2 = "Murky Ring",
        back = "Rudianos's Mantle",
    }

    -- ===== precast =====
    sets.precast.FC = {
        -- Guide "Sets by Alimere → High HP Capped Fast Cast": 80% fast cast with the Sworn
        -- Brais and the Plat. Mog. Belt's HP rather than the bare max-FC build.
        ammo = "Sapience Orb",
        head = "Carmine Mask +1",
        body = "Reverence Surcoat +4",
        hands = "Leyline Gloves",
        legs = "Sworn Brais",
        feet = "Chevalier's Sabatons +3",
        neck = "Orunmila's Torque",
        waist = "Plat. Mog. Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Prolix Ring",
        back = "Rudianos's Mantle",
    }
    sets.precast.JA = {
        -- The fallback for an ability with no set of its own (a /WAR or /RUN ability, an
        -- unnamed job ability): Paladin's actions all want enmity.
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

