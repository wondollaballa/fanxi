--[[
    Fanxi mock GearSwap set library — Red Mage (RDM)
    enfeebler, enspell melee, support

    Import : Launcher -> Gear -> Import GearSwap file... -> RDM.lua
    Wear   : select a set, then "Wear set". Items must be in bags 0-17.
    Template: each account starts from this copy and edits its own saved library.

    This file is a static set library: no includes, no windower/player calls,
    no rules.  Fanxi's importer runs get_sets() in a Lua 5.1 sandbox and shows
    every set below.  Each set is a leaf table of slot -> item, because
    the launcher flattens a table that contains slot keys as one set and stops
    descending; groups such as sets.idle are left empty on purpose.

    Enfeebling Magic is not one set.  The BG Wiki Community Red Mage Guide
    splits the enfeebling spells by what actually decides their value, and the
    library carries one set per kind (docs/rdm.md has the reasoning and the
    full spell table):

      kind      what the spell reads          spells
      ---------------------------------------------------------------------
      Skill     Enfeebling Magic Skill        Frazzle III, Distract III,
                                               Poison, Poison II
      Macc      landing (all-or-nothing)      Frazzle II, Distract II, Dia,
                                               Dia II, Dia III, Sleep, Bind,
                                               Break, Silence, Virus
      Duration  duration over potency         Sleep, Sleep II, Sleepga,
                                               Bind, Break, Silence
      Hybrid    Macc + Enfeebling potency     Gravity, Gravity II
      MND       dMND                          Slow II, Paralyze II, Addle II
      INT       dINT                          Blind II
      General   nothing (cannot be resisted)  Dispel, Dispelga, Inundation

    The Gear page's Spells panel has one row per kind and binds each spell to
    its set, so a Frazzle III wears the skill build and a Slow II wears the MND
    build without a per-spell card.  A per-spell card still wins.

    Enhancing Magic splits the same way: skill/SIRD pieces for Aquaveil, the
    Stoneskin build, and the two duration builds (self and others).

    Requested categories:
      max HP     -> sets.idle.maxhp
      max PDT    -> sets.idle.pdt   (sets.idle.mdt for magic)
      TP         -> sets.engaged.tp
      TP + DT    -> sets.engaged.hybrid
      Fast Cast  -> sets.precast.FC
      Magic Acc  -> sets.midcast["Enfeebling Magic"] and the kind sets
      Magic Atk. -> sets.midcast["Elemental Magic"]
      Cure       -> sets.midcast["Healing Magic"] / sets.midcast.Cure
      Weaponskill-> sets.WS.*
      Abilities  -> sets.JA.*

    Gear follows retail names: iLvl 119 reforged AF/relic/empyrean, Nyame,
    Sakpata's, JSE necks/capes and Odyssey/Limbus accessories, plus a few older
    all-jobs staples (Rajas Ring, Windbuffet Belt +1).  The generic pieces were
    checked against the wiki's per-job access lists.  The item tables below add
    the job's JSE cape builds, the five Unity items' fixed augments, and Nyame,
    Sakpata's, Gleti's and Agwu's Rank 30 Odyssey augments.  The import itself
    does not need the items to exist.

    The guide's enfeebling sets are reproduced from "Gear Sets" on:
    https://www.bg-wiki.com/ffxi/Community_Red_Mage_Guide
    Oseem "Type:X/Rank:N" pieces are named without their rolled augments; the
    wiki gives no fixed values for them.
]]

-- combine() is provided for extending a set without repeating it:
--   sets.idle.regen = combine(sets.idle.dt, { waist = "Windbuffet Belt +1" })
local function combine(base, extra)
    local out = {}
    for key, value in pairs(base or {}) do out[key] = value end
    for key, value in pairs(extra or {}) do out[key] = value end
    return out
end

-- JSE cape builds.  The same Sucellos's Cape is reused with different
-- Ambuscade augments; GearSwap matches the augment list on equip.
-- The enf_* builds are the ones the guide writes for each enfeebling kind
-- (MND +20 / Macc +30 / Fast Cast +10 / PDT -10%, and so on).
local capes = {
    fc = { name = "Sucellos's Cape", augments = {"MP+60", "Mag. Acc+20 /Mag. Dmg.+20", "MP+20", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    pdt = { name = "Sucellos's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    mdt = { name = "Sucellos's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Mag. Evasion+10", "Enmity-10", "Magic dmg. taken-10%"} },
    maxhp = { name = "Sucellos's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "HP+20", "Enmity-10", "Damage taken-5%"} },
    dt = { name = "Sucellos's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "Evasion+10", "Enmity-10", "Damage taken-5%"} },
    tp = { name = "Sucellos's Cape", augments = {"DEX+20", "Accuracy+20 Attack+20", "Accuracy+10", '"Store TP"+10', "Phys. dmg. taken-10%"} },
    cure = { name = "Sucellos's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "MND+10", '"Cure Potency"+10%', "Phys. dmg. taken-10%"} },
    macc = { name = "Sucellos's Cape", augments = {"INT+20", "Mag. Acc+20 /Mag. Dmg.+20", "Mag. Acc.+10", "Enmity-10", "Phys. dmg. taken-10%"} },
    nuke = { name = "Sucellos's Cape", augments = {"INT+20", "Mag. Acc+20 /Mag. Dmg.+20", "INT+10", '"Mag.Atk.Bns."+10', "Phys. dmg. taken-10%"} },
    ws_str = { name = "Sucellos's Cape", augments = {"STR+20", "Accuracy+20 Attack+20", "STR+10", "Weapon skill damage +10%", "Damage taken-5%"} },
    ws_dex = { name = "Sucellos's Cape", augments = {"DEX+20", "Accuracy+20 Attack+20", "DEX+10", "Weapon skill damage +10%", "Damage taken-5%"} },
    ws_mnd = { name = "Sucellos's Cape", augments = {"MND+20", "Accuracy+20 Attack+20", "MND+10", "Weapon skill damage +10%", "Damage taken-5%"} },
    mabws = { name = "Sucellos's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "MND+10", "Weapon skill damage +10%", "Phys. dmg. taken-10%"} },
    -- Guide enfeebling builds: MND+20 / Macc+30 or MND+30 / Macc+20, FC+10, PDT-10%.
    enf_skill = { name = "Sucellos's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "Mag. Acc.+10", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    enf_mnd = { name = "Sucellos's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "MND+10", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    enf_int = { name = "Sucellos's Cape", augments = {"INT+20", "Mag. Acc+20 /Mag. Dmg.+20", "INT+10", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    enf_macc = { name = "Sucellos's Cape", augments = {"INT+20", "Mag. Acc+20 /Mag. Dmg.+20", "Mag. Acc.+10", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
    -- Guide enhancing builds: 30 MND / 20 Macc-Mdmg / -5% DT, and the
    -- Stoneskin cape's 80 HP / 20 Eva-M.Eva / FC+10 / PDT-10%.
    enh_dur = { name = "Sucellos's Cape", augments = {"MND+20", "Mag. Acc+20 /Mag. Dmg.+20", "MND+10", "Damage taken-5%"} },
    stoneskin = { name = "Sucellos's Cape", augments = {"HP+60", "Eva.+20 /Mag. Eva.+20", "HP+20", '"Fast Cast"+10', "Phys. dmg. taken-10%"} },
}

-- Unity accessories: fixed max-rank Odyssey augments.
local unity = {
    collar = { name = "Unmoving Collar +1", augments = {"DEF+30", "HP+200"} },
    odnowa = { name = "Odnowa Earring +1", augments = {"DEF+30", "Damage taken-3%"} },
    ring = { name = "Gelatinous Ring +1", augments = {"VIT+15", "HP+100"} },
    tathlum = { name = "Ghastly Tathlum +1", augments = {"Magic Damage +10", "INT+5"} },
    loess = { name = "Loess Barbuta +1", augments = {"Enmity+10", "Damage taken-10%", "All Attr.+10"} },
}

-- Odyssey Rank 30 builds: every Odyssey armour piece and weapon at Rank 30.
-- Nyame has four paths (A accuracy/TP, B physical WS, C magic, D pet);
-- Sakpata's, Gleti's and Agwu's each have one Rank 30 row.
-- Generated from data/odyssey_r30.json by tools/gen_odyssey_r30.py.
local odyssey = {
    A = {
        helm = { name = "Nyame Helm", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +5%", "Crit.hit rate+10%"} },
        mail = { name = "Nyame Mail", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+15", "Phys. dmg. limit +7%", "DEX/AGI+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+14", "Phys. dmg. limit +5%", "DEX+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +6%", "Crit.hit rate+13%"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Acc/Rng. Acc./M. Acc.+30", "Store TP+13", "Phys. dmg. limit +5%", "AGI+15"} },
    },
    B = {
        helm = { name = "Nyame Helm", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Dbl.Atk."+5%', "Acc.+10 Rng. Acc.+10"} },
        mail = { name = "Nyame Mail", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +13%", '"Double Attack"+7%', "STR/VIT+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Double Attack"+5%', "VIT+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +12%", '"Double Attack"+6%', "STR+15"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Attack+35 Rng. Atk.+35", "Weapon skill dmg +11%", '"Double Attack"+5%', "Acc+13 Rng. Acc+13"} },
    },
    C = {
        helm = { name = "Nyame Helm", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +6", "Mag. Acc.+10"} },
        mail = { name = "Nyame Mail", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+40", "Magic burst damage II +7", "INT/MND/CHR+10"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +5", "MND+15"} },
        flanchard = { name = "Nyame Flanchard", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+35", "Magic burst damage II +5", "INT+15"} },
        sollerets = { name = "Nyame Sollerets", augments = {'"Mag.Atk.Bns."+35', "Magic Damage+30", "Magic burst damage II +5", "CHR+15"} },
    },
    D = {
        helm = { name = "Nyame Helm", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
        mail = { name = "Nyame Mail", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: DMG+11%", "Pet: Damage taken -10%"} },
        gauntlets = { name = "Nyame Gauntlets", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
        flanchard = { name = "Nyame Flanchard", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: DMG+10%", "Pet: Damage taken -9%"} },
        sollerets = { name = "Nyame Sollerets", augments = {"Acc+30 Mag. Acc.+30", "Pet: Acc./Mag. Acc.+30", "Pet: All Attr.+15", "Pet: Damage taken -8%"} },
    },
    sakpata = {
        helm = { name = "Sakpata's Helm", augments = {"Attack+30", '"Double Attack" damage +15%', "Accuracy+15 Mag. Acc+15", '"Cure" potency+5%'} },
        breastplate = { name = "Sakpata's Breastplate", augments = {"Attack+30", "Occ. inc. resist. to stat. ailments+15", "Accuracy+15 Mag. Acc+15", "Crit.hit rate+5%"} },
        gauntlets = { name = "Sakpata's Gauntlets", augments = {"Attack+30", '"Store TP"+8', "Accuracy+15 Mag. Acc+15", "VIT+5"} },
        cuisses = { name = "Sakpata's Cuisses", augments = {"Attack+30", "Skillchain dmg.+15%", "Accuracy+15 Mag. Acc+15", "STR+5"} },
        leggings = { name = "Sakpata's Leggings", augments = {"Attack+30", '"Subtle Blow"+15', "Accuracy+15 Mag. Acc+15", "Chance of successful block +5"} },
    },
    gleti = {
        mask = { name = "Gleti's Mask", augments = {"Attack+30", '"Counter"+10', "Accuracy+15 Mag. Acc+15", '"Regen"+3'} },
        cuirass = { name = "Gleti's Cuirass", augments = {"Attack+30", '"Double Attack"+10%', "Accuracy+15 Mag. Acc+15", "Occ. inc. resist. to stat. ailments+10"} },
        gauntlets = { name = "Gleti's Gauntlets", augments = {"Attack+30", '"Store TP"+8', "Accuracy+15 Mag. Acc+15", "DEX+5"} },
        breeches = { name = "Gleti's Breeches", augments = {"Attack+30", '"Subtle Blow"+15', "Accuracy+15 Mag. Acc+15", '"Triple Attack"+5%'} },
        boots = { name = "Gleti's Boots", augments = {"Attack+30", "Evasion+15", "Accuracy+15 Mag. Acc+15", "STR+5"} },
    },
    agwu = {
        cap = { name = "Agwu's Cap", augments = {'"Mag.Atk.Bns."+25', "Magic Damage+15", "Accuracy+15 Mag. Acc+15", "Enmity-5"} },
        robe = { name = "Agwu's Robe", augments = {'"Mag.Atk.Bns."+25', "Enmity-8", "Accuracy+15 Mag. Acc+15", "Magic Damage+10"} },
        gages = { name = "Agwu's Gages", augments = {'"Mag.Atk.Bns."+25', "Magic burst damage II +6", "Accuracy+15 Mag. Acc+15", "MND+5"} },
        slops = { name = "Agwu's Slops", augments = {'"Mag.Atk.Bns."+25', "Damage taken-10%", "Accuracy+15 Mag. Acc+15", "INT+5"} },
        pigaches = { name = "Agwu's Pigaches", augments = {'"Mag.Atk.Bns."+25', '"Drain" and "Aspir" potency+15', "Accuracy+15 Mag. Acc+15", "Spell interruption rate down 10%"} },
    },
    weapons = {
        fists = { name = "Sakpata's Fists", augments = {"DMG:+20", "Attack+45", "Accuracy+15 Mag. Acc+15", "Skillchain dmg.+10%"} },
        sword = { name = "Sakpata's Sword", augments = {"DMG:+13", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Refresh"+3'} },
        knife = { name = "Gleti's Knife", augments = {"DMG:+11", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Subtle Blow II"+10'} },
        crossbow = { name = "Gleti's Crossbow", augments = {"DMG:+9", "Rng. Atk.+45", "Rng. Acc.+15 Mag. Acc.+15", '"Snapshot"+10'} },
        axe = { name = "Agwu's Axe", augments = {"DMG:+15", "Attack+45", "Accuracy+15 Mag. Acc+15", "Skillchain dmg.+10%"} },
        claymore = { name = "Agwu's Claymore", augments = {"DMG:+26", "Attack+45", "Accuracy+15 Mag. Acc+15", '"Counter"+10'} },
        scythe = { name = "Agwu's Scythe", augments = {"DMG:+28", "Attack+45", "Accuracy+15 Mag. Acc+15", "Damage taken-10%"} },
    },
}

-- Limbus Rank 30 builds: every top-tier Limbus family, one build per augment
-- choice a set needs.  Generated from data/limbus_r30.json by
-- tools/gen_limbus_r30.py.
local limbus = {
    duty = {
        tp = {
            head = { name = "Duty Crown", augments = {'"Store TP"+7'} },
            body = { name = "Duty Cyclas", augments = {'"Store TP"+8'} },
            hands = { name = "Duty Gauntlets", augments = {'"Store TP"+6'} },
            legs = { name = "Duty Flanchard", augments = {'"Store TP"+7'} },
            feet = { name = "Duty Sollerets", augments = {'"Store TP"+6'} },
        },
        ws = {
            head = { name = "Duty Crown", augments = {"Accuracy+30 Mag. Acc+30"} },
            body = { name = "Duty Cyclas", augments = {"Accuracy+30 Mag. Acc+30"} },
            hands = { name = "Duty Gauntlets", augments = {"Accuracy+30 Mag. Acc+30"} },
            legs = { name = "Duty Flanchard", augments = {"Accuracy+30 Mag. Acc+30"} },
            feet = { name = "Duty Sollerets", augments = {"Accuracy+30 Mag. Acc+30"} },
        },
    },
    revelation = {
        tp = {
            head = { name = "Revelation Masque", augments = {'"Double Attack"+7%'} },
            body = { name = "Revelation Plate.", augments = {'"Double Attack"+8%'} },
            hands = { name = "Revelation Gaunt.", augments = {'"Double Attack"+6%'} },
            legs = { name = "Revelation Brais", augments = {'"Double Attack"+7%'} },
            feet = { name = "Revelation Sab.", augments = {'"Double Attack"+6%'} },
        },
        ws = {
            head = { name = "Revelation Masque", augments = {"Physical Damage Limit+6%"} },
            body = { name = "Revelation Plate.", augments = {"Physical Damage Limit+7%"} },
            hands = { name = "Revelation Gaunt.", augments = {"Physical Damage Limit+5%"} },
            legs = { name = "Revelation Brais", augments = {"Physical Damage Limit+6%"} },
            feet = { name = "Revelation Sab.", augments = {"Physical Damage Limit+5%"} },
        },
    },
    sworn = {
        ta = {
            head = { name = "Sworn Crown", augments = {'"Triple Attack"+6%'} },
            body = { name = "Sworn Platemail", augments = {'"Triple Attack"+8%'} },
            hands = { name = "Sworn Gauntlets", augments = {'"Triple Attack"+7%'} },
            legs = { name = "Sworn Brais", augments = {'"Triple Attack"+6%'} },
            feet = { name = "Sworn Sabatons", augments = {'"Triple Attack"+7%'} },
        },
        phalanx = {
            head = { name = "Sworn Crown", augments = {'"Phalanx" received +4'} },
            body = { name = "Sworn Platemail", augments = {'"Phalanx" received +6'} },
            hands = { name = "Sworn Gauntlets", augments = {'"Phalanx" received +5'} },
            legs = { name = "Sworn Brais", augments = {'"Phalanx" received +4'} },
            feet = { name = "Sworn Sabatons", augments = {'"Phalanx" received +5'} },
        },
        acc = {
            head = { name = "Sworn Crown", augments = {"Accuracy+30 Mag. Acc+30"} },
            body = { name = "Sworn Platemail", augments = {"Accuracy+30 Mag. Acc+30"} },
            hands = { name = "Sworn Gauntlets", augments = {"Accuracy+30 Mag. Acc+30"} },
            legs = { name = "Sworn Brais", augments = {"Accuracy+30 Mag. Acc+30"} },
            feet = { name = "Sworn Sabatons", augments = {"Accuracy+30 Mag. Acc+30"} },
        },
    },
    indomitable = {
        cast = {
            head = { name = "Indom. Petasos", augments = {'"Magic Atk. Bonus"+28'} },
            body = { name = "Indomitable Coat", augments = {'"Magic Atk. Bonus"+32'} },
            hands = { name = "Indom. Gloves", augments = {'"Magic Atk. Bonus"+30'} },
            legs = { name = "Indom. Tonban", augments = {'"Magic Atk. Bonus"+28'} },
            feet = { name = "Indom. Sabots", augments = {'"Magic Atk. Bonus"+30'} },
        },
    },
    clemency = {
        tp = {
            head = { name = "Clemen. Somen", augments = {'"Quadruple Attack"+4%'} },
            body = { name = "Clemen. Hara.", augments = {'"Quadruple Attack"+6%'} },
            hands = { name = "Clemency Kote", augments = {'"Quadruple Attack"+5%'} },
            legs = { name = "Clem. Haidate", augments = {'"Quadruple Attack"+4%'} },
            feet = { name = "Clem. Sune-Ate", augments = {'"Quadruple Attack"+5%'} },
        },
        ws = {
            head = { name = "Clemen. Somen", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            body = { name = "Clemen. Hara.", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            hands = { name = "Clemency Kote", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            legs = { name = "Clem. Haidate", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
            feet = { name = "Clem. Sune-Ate", augments = {"Accuracy+30 Rng. Acc.+30 Mag. Acc.+30"} },
        },
    },
}

function get_sets()
    sets = {}

    -- ===== Odyssey Rank 30 sets =================================
    sets.Odyssey = {}  -- container: every Odyssey build this job can wear
    sets.Odyssey.nyame_a = { head = odyssey.A.helm, body = odyssey.A.mail, hands = odyssey.A.gauntlets, legs = odyssey.A.flanchard, feet = odyssey.A.sollerets }
    sets.Odyssey.nyame_b = { head = odyssey.B.helm, body = odyssey.B.mail, hands = odyssey.B.gauntlets, legs = odyssey.B.flanchard, feet = odyssey.B.sollerets }
    sets.Odyssey.nyame_c = { head = odyssey.C.helm, body = odyssey.C.mail, hands = odyssey.C.gauntlets, legs = odyssey.C.flanchard, feet = odyssey.C.sollerets }
    sets.Odyssey.nyame_d = { head = odyssey.D.helm, body = odyssey.D.mail, hands = odyssey.D.gauntlets, legs = odyssey.D.flanchard, feet = odyssey.D.sollerets }
    sets.Odyssey.weapon = { main = odyssey.weapons.sword }

    -- ===== Limbus Rank 30 sets =================================
    sets.Limbus = {}  -- container: every top-tier Limbus build this job can wear
    sets.Limbus.sworn_ta = { head = limbus.sworn.ta.head, body = limbus.sworn.ta.body, hands = limbus.sworn.ta.hands, legs = limbus.sworn.ta.legs, feet = limbus.sworn.ta.feet }
    sets.Limbus.sworn_phalanx = { head = limbus.sworn.phalanx.head, body = limbus.sworn.phalanx.body, hands = limbus.sworn.phalanx.hands, legs = limbus.sworn.phalanx.legs, feet = limbus.sworn.phalanx.feet }
    sets.Limbus.sworn_acc = { head = limbus.sworn.acc.head, body = limbus.sworn.acc.body, hands = limbus.sworn.acc.hands, legs = limbus.sworn.acc.legs, feet = limbus.sworn.acc.feet }

    -- ===== idle =================================================
    sets.idle = {}  -- container: Fanxi lists the children below
    -- town / CP / walking around
    sets.idle.town = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Hippomenes Socks +1",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = unity.odnowa,
        ring1 = "Chirich Ring +1",
        ring2 = "Shneddick Ring +1",
        back = "Aptitude Mantle",
    }
    -- Refresh sources
    sets.idle.refresh = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Stikini Ring +1",
        back = capes.fc,
    }
    -- max physical damage taken
    sets.idle.pdt = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.pdt,
    }
    -- max magic damage taken
    sets.idle.mdt = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.mdt,
    }
    -- max HP
    sets.idle.maxhp = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.maxhp,
    }
    -- balanced damage taken with job pieces
    sets.idle.dt = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Vitiation Gloves +4",
        legs = "Vitiation Tights +4",
        feet = "Atrophy Boots +4",
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.dt,
    }
    -- movement speed + town
    sets.idle.movement = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Carmine Cuisses +1",
        feet = "Hippomenes Socks +1",
        neck = "Duelist's Torque +2",
        waist = "Plat. Mog. Belt",
        ear1 = "Etiolation Earring",
        ear2 = unity.odnowa,
        ring1 = "Shneddick Ring +1",
        ring2 = "Chirich Ring +1",
        back = "Aptitude Mantle",
    }

    -- ===== engaged =================================================
    sets.engaged = {}  -- container: TP variants below
    -- Guide TP set: Malignance 5/5, Anu Torque, Sherida/Dedition, Hetairoi/Chirich.
    -- The weapons stay on the weaponset; the guide pairs Crocea Mors + Daybreak here.
    sets.engaged.tp = {
        ammo = "Aurgelmir Orb +1",
        head = "Malignance Chapeau",
        body = "Malignance Tabard",
        hands = "Aya. Manopolas +2",
        legs = "Malignance Tights",
        feet = "Malignance Boots",
        neck = "Anu Torque",
        waist = "Orpheus's Sash",
        ear1 = "Sherida Earring",
        ear2 = "Dedition Earring",
        ring1 = "Hetairoi Ring",
        ring2 = "Chirich Ring +1",
        back = capes.tp,
    }
    -- accuracy-first TP
    sets.engaged.acc = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = "Combatant's Torque",
        waist = "Windbuffet Belt +1",
        ear1 = "Telos Earring",
        ear2 = "Cessance Earring",
        ring1 = "Rajas Ring",
        ring2 = "Petrov Ring",
        back = capes.tp,
    }
    -- TP with DT accessories
    sets.engaged.hybrid = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.A.helm,
        body = odyssey.A.mail,
        hands = odyssey.A.gauntlets,
        legs = odyssey.A.flanchard,
        feet = odyssey.A.sollerets,
        neck = unity.collar,
        waist = "Windbuffet Belt +1",
        ear1 = "Cessance Earring",
        ear2 = unity.odnowa,
        ring1 = "Defending Ring",
        ring2 = unity.ring,
        back = capes.tp,
    }
    -- Guide "Enspell damage only": Aern Dagger + Qutrub Knife, Ullr, Malignance.
    sets.engaged.Enspell = {
        main = "Aern Dagger",
        sub = "Qutrub Knife",
        range = "Ullr",
        ammo = "Aurgelmir Orb +1",
        head = "Malignance Chapeau",
        body = "Malignance Tabard",
        hands = "Aya. Manopolas +2",
        legs = "Malignance Tights",
        feet = "Malignance Boots",
        neck = "Duelist's Torque +2",
        waist = "Orpheus's Sash",
        ear1 = "Sherida Earring",
        ear2 = "Telos Earring",
        ring1 = "Chirich Ring +1",
        ring2 = "Chirich Ring +1",
        back = capes.tp,
    }

    -- ===== precast =================================================
    -- Limbus Sworn R30 is the repo's RDM fast-cast suit (docs/limbus-r30.md).
    -- The guide's alternative for the head slot is Atrophy Chapeau +4, the
    -- strongest single fast-cast piece in the game.
    sets.precast = {}  -- container: fast cast below
    sets.precast.FC = {
        ammo = "Staunch Tathlum +1",
        head = limbus.sworn.ta.head,
        body = limbus.sworn.ta.body,
        hands = limbus.sworn.ta.hands,
        legs = limbus.sworn.ta.legs,
        feet = limbus.sworn.ta.feet,
        neck = "Orunmila's Torque",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Kishar Ring",
        ring2 = "Rahab Ring",
        back = capes.fc,
    }

    -- ===== midcast =================================================
    sets.midcast = {}  -- container: magic sets below

    -- Enfeebling Magic, split by what the spell reads.  These are the guide's
    -- "Gear Sets > Enfeebling Magic Sets" tables, one build per kind.

    -- Skill based build: Frazzle III, Distract III, Poison, Poison II.
    -- Under Saboteur the guide swaps the hands to Lethargy Gantherots +1.
    sets.midcast["Enfeebling Magic Skill"] = {
        main = "Contemplator +1",
        sub = "Enki Strap",
        ammo = "Regal Gem",
        head = "Vitiation Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Kaykaus Cuffs +1",
        legs = "Psycloth Lappas",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Vor Earring",
        ear2 = "Snotra Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        waist = "Obstin. Sash",
        back = capes.enf_skill,
    }
    -- Macc build: Frazzle II, Distract II, Dia, Sleep, Bind, Break, Silence.
    -- The guide calls this "MAcc. & Duration".
    sets.midcast["Enfeebling Magic Macc"] = {
        main = "Contemplator +1",
        sub = "Enki Strap",
        range = "Ullr",
        head = "Vitiation Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Regal Cuffs",
        legs = "Psycloth Lappas",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Regal Earring",
        ear2 = "Snotra Earring",
        ring1 = "Kishar Ring",
        ring2 = "Stikini Ring +1",
        waist = "Luminary Sash",
        back = capes.enf_macc,
    }
    -- Duration build: Sleep, Sleep II, Bind, Break, Silence when the timer is
    -- what matters.  The guide's second "MAcc. & Duration" table.
    sets.midcast["Enfeebling Magic Duration"] = {
        main = "Contemplator +1",
        sub = "Enki Strap",
        range = "Ullr",
        head = "Vitiation Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Kaykaus Cuffs +1",
        legs = "Psycloth Lappas",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Regal Earring",
        ear2 = "Snotra Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        waist = "Luminary Sash",
        back = capes.enf_macc,
    }
    -- Macc + potency hybrid: Gravity and Gravity II.  The guide's
    -- "MAcc + Pot. Hybrid" table; use Macc or Duration instead when one of
    -- those is the pressing concern.
    sets.midcast["Enfeebling Magic Hybrid"] = {
        main = "Contemplator +1",
        sub = "Enki Strap",
        ammo = "Regal Gem",
        head = "Vitiation Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Kaykaus Cuffs +1",
        legs = "Psycloth Lappas",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Vor Earring",
        ear2 = "Snotra Earring",
        ring1 = "Kishar Ring",
        ring2 = "Stikini Ring +1",
        waist = "Obstin. Sash",
        back = capes.enf_skill,
    }
    -- dMND build: Slow II, Paralyze II, Addle II.  The guide's
    -- "Full Mind+ Potency" table; Chironic Hose rolls MND+15 / Macc+40.
    sets.midcast["Enfeebling Magic MND"] = {
        main = "Contemplator +1",
        sub = "Enki Strap",
        ammo = "Regal Gem",
        head = "Vitiation Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Kaykaus Cuffs +1",
        legs = { name = "Chironic Hose", augments = {"MND+15", "Magic Acc.+40"} },
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Regal Earring",
        ear2 = "Snotra Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Stikini Ring +1",
        waist = "Obstin. Sash",
        back = capes.enf_mnd,
    }
    -- dINT build: Blind II.  The guide's "Full INT+ Potency" table.
    sets.midcast["Enfeebling Magic INT"] = {
        main = "Marin Staff +1",
        sub = "Enki Strap",
        ammo = "Regal Gem",
        head = "Vitiation Chapeau +4",
        body = "Lethargy Sayon +3",
        hands = "Regal Cuffs",
        legs = "Psycloth Lappas",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        ear1 = "Regal Earring",
        ear2 = "Snotra Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Kishar Ring",
        waist = "Acuity Belt +1",
        back = capes.enf_int,
    }
    -- Non-scaling build: Dispel, Dispelga, Inundation.  The guide's
    -- "Full Duration & TH" table; it only needs duration and the TH pieces.
    sets.midcast["Enfeebling Magic General"] = {
        ammo = "Per. Lucky Egg",
        head = "Volte Cap",
        body = "Volte Jupon",
        hands = "Regal Cuffs",
        legs = "Volte Hose",
        feet = "Volte Boots",
        neck = "Duelist's Torque +2",
        ear2 = "Snotra Earring",
        ring2 = "Kishar Ring",
        waist = "Obstin. Sash",
    }
    -- Saboteur overlay: the guide's "always override Hand equipment on enfeebles under the
    -- effects of Saboteur" note.  Only the hands differ, so this set is one piece: while
    -- Saboteur (status 454) is up the phase engine lays it over the spell's kind set and the
    -- kind set's hands return after the result.  The guide names Lethargy Gantherots +1; this
    -- server has the +3 tier, which carries more Enfeebling Magic Skill.
    sets.midcast["Enfeebling Magic Saboteur"] = {
        hands = "Lethargy Gantherots +3",
    }
    -- Generic enfeebling fallback: used when a kind row is left empty.
    sets.midcast["Enfeebling Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }

    -- Enhancing Magic: skill/SIRD pieces for Aquaveil, the Stoneskin build,
    -- then the two duration builds.  The guide's "Skill Based Enhancing Sets"
    -- and "Enhancing Duration Sets".
    sets.midcast["Enhancing Magic SIRD"] = {
        main = "Grioavolr",
        sub = "Magic Strap",
        ammo = "Staunch Tathlum +1",
        head = "Amalric Coif +1",
        body = "Ros. Jaseran +1",
        hands = "Regal Cuffs",
        legs = "Shedir Seraweels",
        feet = "Amalric Nails +1",
        neck = "Duelist's Torque +2",
        ear1 = "Halasz Earring",
        ear2 = "Magnetic Earring",
        ring1 = "Freke Ring",
        ring2 = "Defending Ring",
        waist = "Emphatikos Rope",
        back = capes.pdt,
    }
    sets.midcast["Enhancing Magic Stoneskin"] = {
        main = "Sakpata's Sword",
        sub = "Ammurapi Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +3",
        body = "Vitiation Tabard +4",  -- guide lists +3; +4 is the copy this server owns
        hands = "Stone Mufflers",
        legs = "Shedir Seraweels",
        feet = "Nyame Sollerets",
        neck = "Nodens Gorget",
        ear1 = "Earthcry Earring",
        ear2 = "Etiolation Earring",
        ring1 = "Gelatinous Ring +1",
        ring2 = "Defending Ring",
        waist = "Siegel Sash",
        back = capes.stoneskin,
    }
    -- Duration (Self): Composure triples the timer, so the self build keeps
    -- the Enhancing Skill pieces that carry duration.
    sets.midcast.EnhancingDuration = {
        main = { name = "Colada", augments = {"Enhancing Magic Duration +4%"} },
        sub = "Ammurapi Shield",
        head = { name = "Telchine Cap", augments = {"Enhancing Magic Duration +10%"} },
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = { name = "Telchine Braconi", augments = {"Enhancing Magic Duration +10%"} },
        feet = "Lethargy Houseaux +3",
        neck = "Duelist's Torque +2",
        ear2 = "Leth. Earring +2",
        waist = "Embla Sash",
        back = capes.enh_dur,
    }
    -- Duration (Others): the Lethargy pieces carry the group duration.
    sets.midcast.EnhancingDurationOthers = {
        main = { name = "Colada", augments = {"Enhancing Magic Duration +4%"} },
        sub = "Ammurapi Shield",
        head = "Lethargy Chappel +3",
        body = "Lethargy Sayon +3",
        hands = "Atrophy Gloves +4",
        legs = "Lethargy Fuseau +3",
        feet = "Lethargy Houseaux +3",
        neck = "Duelist's Torque +2",
        ear2 = "Leth. Earring +2",
        waist = "Embla Sash",
        back = capes.enh_dur,
    }
    sets.midcast["Enhancing Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Witful Belt",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }
    sets.midcast.EnhancingSkill = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Vitiation Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Lethargy Houseaux +3",
        neck = "Incanter's Torque",
        waist = "Embla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Malignance Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = capes.macc,
    }
    sets.midcast.Enspell = {
        main = "Crocea Mors",
        sub = "Genbu's Shield",
        ammo = "Sroda Tathlum",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Aya. Manopolas +2",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = "Incanter's Torque",
        waist = "Embla Sash",
        ear1 = "Mimir Earring",
        ear2 = "Malignance Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Stikini Ring +1",
        back = capes.fc,
    }

    -- Elemental Magic: the guide's "Cycle of Nuking" build.
    sets.midcast["Elemental Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = unity.tathlum,
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Friomisi Earring",
        ear2 = "Crematio Earring",
        ring1 = "Metamorph Ring +1",
        ring2 = "Mujin Band",
        back = capes.nuke,
    }
    sets.midcast["Elemental Magic Macc"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Enchntr. Earring +1",
        ear2 = "Digni. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }
    sets.midcast["Dark Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Pemphredo Tathlum",
        head = odyssey.C.helm,
        body = odyssey.C.mail,
        hands = odyssey.C.gauntlets,
        legs = odyssey.C.flanchard,
        feet = odyssey.C.sollerets,
        neck = "Duelist's Torque +2",
        waist = "Eschan Stone",
        ear1 = "Digni. Earring",
        ear2 = "Enchntr. Earring +1",
        ring1 = "Stikini Ring +1",
        ring2 = "Kishar Ring",
        back = capes.macc,
    }
    sets.midcast["Healing Magic"] = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        waist = "Witful Belt",
        ear1 = "Halasz Earring",
        ear2 = "Tuisto Earring",
        ring1 = unity.ring,
        ring2 = "Stikini Ring +1",
        back = capes.cure,
    }
    sets.midcast.Cure = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Telchine Gloves",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Incanter's Torque",
        waist = "Witful Belt",
        ear1 = "Malignance Earring",
        ear2 = "Loquac. Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Jann. Ring +1",
        back = capes.cure,
    }
    sets.midcast.CureHP = {
        main = "Daybreak",
        sub = "Genbu's Shield",
        ammo = "Staunch Tathlum +1",
        head = "Sworn Crown",
        body = "Sworn Platemail",
        hands = "Sworn Gauntlets",
        legs = "Sworn Brais",
        feet = "Sworn Sabatons",
        neck = unity.collar,
        waist = "Plat. Mog. Belt",
        ear1 = "Tuisto Earring",
        ear2 = unity.odnowa,
        ring1 = "Jann. Ring +1",
        ring2 = unity.ring,
        back = capes.maxhp,
    }

    -- ===== WS =================================================
    sets.WS = {}  -- container: weaponskills below
    sets.WS["Black Halo"] = {
        main = "Maxentius",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = "Vitiation Chapeau +4",
        body = "Bunzi's Robe",
        hands = "Atrophy Gloves +4",
        legs = "Nyame Flanchard",
        feet = "Lethargy Houseaux +3",
        neck = "Duelist's Torque +2",
        waist = "Sailfi Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = capes.ws_mnd,
    }
    sets.WS["Chant du Cygne"] = {
        main = "Naegling",
        sub = "Genbu's Shield",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Cessance Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Begrudging Ring",
        back = capes.ws_dex,
    }
    sets.WS.Imperator = {
        main = "Caliburnus",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Metamorph Ring +1",
        back = capes.ws_mnd,
    }
    sets.WS.Requiescat = {
        main = "Sequence",
        sub = "Daybreak",
        ammo = "Crepuscular Pebble",
        head = "Null Masque",
        body = "Bunzi's Robe",
        hands = "Malignance Gloves",
        legs = "Nyame Flanchard",
        feet = "Sworn Sabatons",
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Sroda Ring",
        ring2 = "Metamorph Ring +1",
        back = capes.ws_mnd,
    }
    sets.WS["Ruthless Stroke"] = {
        main = "Mpu Gandring",
        sub = "Thibron",
        ammo = "Crepuscular Pebble",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = "Malignance Gloves",
        legs = odyssey.B.flanchard,
        feet = "Lethargy Houseaux +3",
        neck = "Fotia Gorget",
        waist = "Kentarch Belt +1",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = "Alabaster Mantle",
    }
    -- Guide Seraph Blade: Crocea Mors + Daybreak, Amalric, Weatherspoon/Freke.
    sets.WS["Seraph Blade"] = {
        main = "Crocea Mors",
        sub = "Daybreak",
        ammo = "Pemphredo Tathlum",
        head = "C. Palug Crown",
        body = "Amalric Doublet +1",
        hands = "Jhakri Cuffs +2",
        legs = "Amalric Slops +1",
        feet = "Amalric Nails +1",
        neck = "Baetyl Pendant",
        waist = "Orpheus's Sash",
        ear1 = "Regal Earring",
        ear2 = "Malignance Earring",
        ring1 = "Weather. Ring +1",
        ring2 = "Freke Ring",
        back = capes.mabws,
    }
    -- Guide Sanguine Blade: the same shell with the Dark-weather head/ring.
    sets.WS["Sanguine Blade"] = {
        main = "Crocea Mors",
        sub = "Daybreak",
        ammo = "Pemphredo Tathlum",
        head = "Pixie Hairpin +1",
        body = "Amalric Doublet +1",
        hands = "Jhakri Cuffs +2",
        legs = "Amalric Slops +1",
        feet = "Amalric Nails +1",
        neck = "Baetyl Pendant",
        waist = "Orpheus's Sash",
        ear1 = "Regal Earring",
        ear2 = "Malignance Earring",
        ring1 = "Archon Ring",
        ring2 = "Freke Ring",
        back = capes.mabws,
    }
    sets.WS["Savage Blade"] = {
        main = "Naegling",
        sub = "Thibron",
        ammo = "Aurgelmir Orb +1",
        head = odyssey.B.helm,
        body = odyssey.B.mail,
        hands = odyssey.B.gauntlets,
        legs = odyssey.B.flanchard,
        feet = odyssey.B.sollerets,
        neck = "Fotia Gorget",
        waist = "Fotia Belt",
        ear1 = "Moonshade Earring",
        ear2 = "Hoxne Earring",
        ring1 = "Epaminondas's Ring",
        ring2 = "Sroda Ring",
        back = capes.ws_str,
    }

    -- ===== JA =================================================
    sets.JA = {}  -- container: job abilities below
    sets.JA.Chainspell = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Vitiation Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = capes.fc,
    }
    sets.JA.Composure = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = capes.fc,
    }
    sets.JA.Convert = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Vitiation Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = capes.fc,
    }
    sets.JA.Saboteur = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Atrophy Boots +4",
        neck = "Duelist's Torque +2",
        back = capes.fc,
    }
    sets.JA.Spontaneity = {
        main = "Murgleis",
        sub = "Genbu's Shield",
        head = "Atrophy Chapeau +4",
        body = "Atrophy Tabard +4",
        hands = "Atrophy Gloves +4",
        legs = "Atrophy Tights +4",
        feet = "Vitiation Boots +4",
        neck = "Duelist's Torque +2",
        back = capes.fc,
    }

    -- ===== weaponset =================================================
    sets.weaponset = {}  -- container: the pairs the Gear page pins
    sets.weaponset["Caliburnus-DiamondAspis"] = {
        main = "Caliburnus",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Caliburnus-Thibron"] = {
        main = "Caliburnus",
        sub = "Thibron",
    }
    sets.weaponset.CroceaMors = {
        main = "Crocea Mors",
        sub = "Genbu's Shield",
    }
    sets.weaponset["CroceaMors-Daybreak"] = {
        main = "Crocea Mors",
        sub = "Daybreak",
    }
    sets.weaponset["Excalibur-DiamondAspis"] = {
        main = "Excalibur",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Maxentius-Thibron"] = {
        main = "Maxentius",
        sub = "Thibron",
    }
    sets.weaponset["Mpu-Thibron"] = {
        main = "Mpu Gandring",
        sub = "Thibron",
    }
    sets.weaponset["MpuGandring-DiamondAspis"] = {
        main = "Mpu Gandring",
        sub = "Diamond Aspis",
    }
    sets.weaponset["Naegling-Thibron"] = {
        main = "Naegling",
        sub = "Thibron",
    }
    sets.weaponset["WizardsRod-DiamondAspis"] = {
        main = "Wizard's Rod",
        sub = "Diamond Aspis",
    }
end

-- Fanxi template; each account has its own editable copy of this library.
