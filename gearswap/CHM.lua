--[[
    Fanxi GearSwap library — CHM
    Starter sets for the Chemist job (job 23).

    The server gives CHM the Scholar item mask for testing, so every piece below can
    be worn.  The important rule for this first pass is the shield: Brewer's Escutcheon
    (Br. Escutcheon) is in every idle, precast, midcast and job-ability set.  That keeps
    the 2,000 ms synthesis cast and the Toss/Mix/Catalyst/Amplify/Volatile actions on
    the shield even when GearSwap switches into a set.

    GearSwap cannot see //chm craft (it starts server-side, with no client action), so
    the shield is also in the idle/engaged sets; it stays on through a recipe craft.
]]

function get_sets()
    sets = {}
    sets.idle = {}
    sets.idle.town = {}
    sets.idle.field = {}
    sets.idle.movement = {}
    sets.engaged = {}
    sets.engaged.tp = {}
    sets.precast = {}
    sets.precast.FC = {}
    sets.midcast = {}
    sets.JA = {}
    sets.WS = {}

    local shield = "Br. Escutcheon"
    local rod = "Wizard's Rod (Reforged)"

    -- Scholar-test accessories.  These are SCH-usable pieces already in Onedough's
    -- bags; the end goal is a Chemist-only set, not best-in-slot.
    local test = {
        head = "Null Masque",
        body = "Onca Suit",
        hands = "Scholar's Bracers",
        legs = "Querkening Brais",
        feet = "Amalric Nails",
        neck = "Unmoving Collar +1",
        waist = "Cornelia's Belt",
        ear1 = "Hoxne Earring",
        ear2 = "Eabani Earring",
        ring1 = "Stikini Ring +1",
        ring2 = "Epaminondas's Ring",
        back = "Alabaster Mantle",
        ammo = "Staunch Tathlum +1",
    }

    local function with_shield(extra)
        local out = { main = rod, sub = shield }
        for slot, item in pairs(test) do out[slot] = item end
        for slot, item in pairs(extra or {}) do out[slot] = item end
        return out
    end

    -- Idle / engaged: the shield is deliberately always here.  A Recipe craft is a
    -- server command, so GearSwap never gets an action event to swap for it.
    sets.idle = with_shield()
    sets.idle.town = with_shield()
    sets.idle.field = with_shield()
    sets.idle.movement = with_shield()
    sets.engaged = with_shield({ ammo = "Sroda Tathlum" })
    sets.engaged.tp = with_shield({ ammo = "Sroda Tathlum" })

    -- Precast (including the recipe's client-visible 0x028 job-ability path).
    sets.precast.FC = with_shield()
    sets.precast = sets.precast.FC

    -- SCH-test midcast categories.  Keep the shield on every one.
    sets.midcast.HealingMagic = with_shield()
    sets.midcast.EnhancingMagic = with_shield()
    sets.midcast.EnfeeblingMagic = with_shield()
    sets.midcast.ElementalMagic = with_shield()
    sets.midcast.DarkMagic = with_shield()
    sets.midcast.DivineMagic = with_shield()
    sets.midcast.SummoningMagic = with_shield()
    sets.midcast.BlueMagic = with_shield()
    sets.midcast.Ninjutsu = with_shield()
    sets.midcast.Singing = with_shield()

    -- Chemist job abilities.  These are the keys GearSwap looks up by the action's
    -- ability name before it sends the 0x01A packet.
    sets.JA.Toss = with_shield()
    sets.JA.Mix = with_shield()
    sets.JA.Catalyst = with_shield()
    sets.JA.Amplify = with_shield()
    sets.JA["Volatile Synthesis"] = with_shield()

    -- A club weaponskill; useful for testing the rod without losing the shield.
    sets.WS["Black Halo"] = with_shield()
end
