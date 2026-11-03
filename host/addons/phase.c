/* The phase engine: GearSwap's precast / action / midcast order, done in the packet buffers
 * host64 already rewrites.
 *
 * GearSwap never waits for the client's action packet and hopes the gear is on in time. It
 * blocks the action, wears the precast set, sends the action, and wears the midcast set right
 * behind it - which is why a fast-cast set counts for the cast the server times, and why a
 * weaponskill set counts for the damage it rolls. This file holds the rules for that; hooks.c
 * holds the packet (an outgoing 0x01A with a plan) out of its buffer, injects the precast
 * 0x050s there, queues the action for the next buffer with the midcast 0x050s right after it,
 * and puts the return set back when the action's result (incoming 0x028, categories 3/4/6)
 * arrives.
 *
 * Rules are built on the game thread from a GearSwap set library (the control addon's `phase`
 * command) and read on the network thread from the packet hooks: the table is published with
 * an atomic pointer and never freed, which is fine because it is only rebuilt when the library,
 * the job or the toggle changes.
 *
 * The idle state machine is four states plus a lock: engaged (TP), movement, idle in a town,
 * and idle in the field. The zone-in packet (0x00A) says which idle applies; the server's own
 * animation for the player (0x00D) says whether the weapon is drawn, which is the engagement
 * signal.  The client's own /attack off is not the signal: it sends that by itself whenever the
 * target leaves its four-yalm auto-attack reach, while the server may still be holding the
 * engagement so the player can kite. The lock is an override: while it is on, no automatic
 * swap goes out, and the status names the set it holds.
 */
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "lauxlib.h"
#include "lua.h"

#include "host.h"
#include "phase.h"

/* A plan can carry the library's skill rules for every spell plus one rule per spell in each
 * configured category (Enfeebling Magic, Enhancing Magic and the helix spells overlap), so the
 * rule table is wider than the old skill-only plan.  The state sets are added after the rules,
 * and a fully configured Bard library (every song and spell override armed) builds over a
 * hundred, so the set table is sized for a whole job's worth: at 96 the field, movement and
 * focus sets fell off the end and the client silently wore the town set instead. */
enum { PHASE_SETS = 256, PHASE_RULES = 4096, PHASE_NAME = 48 };
/* Conditional rules: a set named "Victory Smite (Impetus, Focus)" matches only while every
 * listed buff is up.  The buff ids are the client's status ids (Impetus is 461); the addon
 * pushes the live list from the player's own buff block every frame or so. */
enum { PHASE_RULE_BUFFS = 8 };
/* The client's status ids are 0..4095; one bit each is 512 bytes. */
enum { PHASE_BUFF_IDS = 4096, PHASE_BUFF_WORDS = PHASE_BUFF_IDS / 32 };
/* 0x01A action categories: what the client is doing. */
enum
{
    PHASE_ACTION_ATTACK = 2,  /* /attack: engaged */
    PHASE_ACTION_MAGIC = 3,
    PHASE_ACTION_SKILL = 7,   /* weaponskill */
    PHASE_ACTION_ABILITY = 9, /* job ability */
};
/* Equipment slots 0-3: the hands and the ranged pair.  The server builds the weapon-skill
 * menu from these, so a job ability or spell must not swap them under a lock. */
enum { PHASE_WEAPON_SLOTS = 0x000F };
/* Corsair Phantom Rolls: 98-122, the merit rolls 302-305 and Runeist's/Allies' 390-391.  Their
 * +duration set names a weapon, ranged and ammo piece, so unlike every other job ability a roll
 * may temporarily take the pinned hands off and put them back when the action resolves. */
static int is_phantom_roll(unsigned action)
{
    return (action >= 98 && action <= 122) || (action >= 302 && action <= 305) ||
           action == 390 || action == 391;
}
/* BRD's job id in the client's 0x01B block (WAR 1 ... BRD 10).  Only a Bard main job can sing,
 * so the sub job does not open the instrument window. */
enum { PHASE_JOB_BRD = 10 };
/* 0x028 result categories: something finished.  1 is a swing, 8 a cast starting. */
enum { PHASE_RESULT_SKILL = 3, PHASE_RESULT_MAGIC = 4, PHASE_RESULT_ABILITY = 6 };
/* No result in this long (an interrupted cast, a refused action): put the return set back.
 * It has to outlast the longest cast or a slow spell resolves in the idle set: a bard song is
 * 8 s on its own and 12 s under Troubadour (1.5x cast), so 6 s dropped the midcast set before
 * the song landed and every song wore the idle gear into its duration roll. */
enum { PHASE_STALE_MS = 30000 };
/* A zone or job change takes the client a moment to settle; the state set goes out after it. */
enum { PHASE_SETTLE_MS = 1500 };

typedef struct PhaseSet
{
    uint8_t n;
    PhaseEquip e[PHASE_EQUIP_MAX];
} PhaseSet;

typedef struct PhaseRule
{
    uint16_t category, action;
    int16_t pre, mid; /* indices into sets, -1 for none */
    int16_t burst;    /* mid instead of `mid` while a magic-burst window is open, -1 for none */
    uint8_t song;     /* a Bard song: the only magic set allowed the Nitro instrument swap */
    uint8_t n_buffs;  /* 0: the unconditional set for this action */
    uint16_t buffs[PHASE_RULE_BUFFS]; /* all must be active (AND) */
} PhaseRule;

typedef struct PhaseTable
{
    int enabled;
    uint32_t player;
    int16_t restore; /* after an action when nothing better is known */
    int16_t engage;  /* worn on /attack  (0x01A category 2) */
    int16_t idle;    /* fallback when the zone is not known yet */
    int16_t town;    /* worn while idle in a city */
    int16_t field;   /* worn while idle anywhere else */
    int16_t move;    /* worn while moving */
    int16_t kite;    /* forced kiting state, until switched off */
    int16_t rest;    /* resting (manual), until switched off */
    int16_t focus[5]; /* idle focus: dt, pdt, mdt, eva, meva (0 = no set) */
    int nsets, nrules;
    char names[PHASE_SETS][PHASE_NAME];
    PhaseSet sets[PHASE_SETS];
    PhaseRule rules[PHASE_RULES];
} PhaseTable;

static _Atomic(PhaseTable*) g_table;
static _Atomic unsigned g_actions, g_seen, g_held, g_restored, g_stale, g_swapped;
/* The player's active status ids, as a bitmap.  The addon writes the whole list from the game
 * thread; the packet hook reads it on the network thread.  An even epoch means the bitmap is
 * stable; a reader that catches an update retries. */
static _Atomic unsigned g_buff_epoch;
static _Atomic uint32_t g_buff_bits[PHASE_BUFF_WORDS];
/* Engagement comes from the client's own /attack and from the server's animation for the
 * player.  /attack off is not read here: the server answers a real disengage with animation 0,
 * and an ignored range disengage must not move the gear. Movement is sampled by the addon. */
static _Atomic int g_engaged;
static _Atomic int g_moving;
/* -1 until a zone has been seen, 1 in a town, 0 in the field. */
static _Atomic int g_town = -1;
static _Atomic int g_zone, g_job, g_sub_job;
static _Atomic uint32_t g_player;
/* Only a Bard main job can sing, so the sub job does not open the instrument window. */
static int is_bard_main(void)
{
    return atomic_load_explicit(&g_job, memory_order_acquire) == PHASE_JOB_BRD;
}
/* The user's override. While set, every automatic swap is suppressed and the set that was
 * current at the moment of locking is what the status reports. */
static _Atomic int g_locked;
static _Atomic int g_lock_set = -1;
/* Forced states and per-slot weapon locks. Kiting wins over everything but the full lock;
 * resting is manual too (this server has no rest packet to follow). A locked slot is removed
 * from every set the engine sends, weapons included: a pin on main/sub holds through a
 * weaponskill as well as a precast/midcast set, so the TP hand never leaves mid-fight. */
static _Atomic int g_kiting, g_resting;
static _Atomic int g_focus; /* 0 auto, 1 dt, 2 pdt, 3 mdt, 4 eva, 5 meva */
static _Atomic unsigned g_locked_slots; /* bit i = equipment slot i is pinned */
/* The exact copy locked in each weapon slot (equip_key), not just the mask.  A lock that only
 * filtered sets could not put the hand back after a sanctioned temporary swap (a cast while
 * disengaged, a Bard's Nitro song) or after the client changed it by hand away from the lock.
 * The copies also re-arm when the weapon is drawn, which is the case the TP set itself does not
 * name a weapon (a weaponset outside the state sets). */
static _Atomic uint32_t g_locked_equip[4]; /* main, sub, ranged, ammo */
/* Nightingale + Troubadour are both up.  The Bard's one sanctioned weapon-swap window: the song
 * sets name an instrument, and without it a locked Bard cannot sing at all. */
static _Atomic int g_nitro;
/* A magic-burst window is open on the player's current target.  The addon sets this from the
 * skillchain the closing action's 0x028 reported; a rule with a `burst` set wears that set
 * instead of its ordinary midcast set while the flag is on. */
static _Atomic int g_burst;
static int append_locked_weapons(PhasePlan* plan);
static void capture_weapon_locks(const PhaseTable* t, unsigned mask, int full);
/* The state index whose set is on the character now (-1: unknown). A transition that lands on
 * the state already worn - a movement step while engaged, or the client re-sending /attack for
 * the same target - has nothing to change, and re-sending the set would only make the client
 * drop its battle stance piece by piece for the server to re-assert it. */
static _Atomic int g_worn_state = -1;
/* A zone, job or stance change wants the state set re-worn once the client has settled. */
static _Atomic int g_state_pending;
static _Atomic uint64_t g_state_due;
static _Atomic int g_pending;
static _Atomic uint64_t g_pending_at;
static _Atomic unsigned g_pending_action;
/* Action category of the pending action: a job ability has no cast bar and answers at once, so
 * a held ability that never gets a 0x028 (recast refused, range lost) can restore much sooner
 * than a spell or song that is legitimately still casting. */
static _Atomic unsigned g_pending_category;
/* One-shot gear worn in front of the next action (the addon's jug picker re-asserts the
 * chosen jug behind the held Call Beast/Bestial Loyalty packet).  It is merged into that
 * action's precast set and cleared by the next action whatever it turns out to be, so a
 * cancelled picker click can never put a jug on for a later weaponskill. */
static PhaseEquip g_precache[PHASE_EQUIP_MAX];
static _Atomic int g_precache_n;
static _Atomic unsigned g_precache_action;
/* A locked action's temporary override.  The engine clears the lock just long enough to build
 * the action's own precast/midcast set, remembers the equipment that was on, and puts it back
 * when the action resolves.  Only job abilities, spells/songs and weapon skills take this path;
 * /attack and the automatic state transitions still obey the lock. */
typedef struct PhaseActionOverride
{
    _Atomic int active;
    unsigned changed; /* equipment slots the action's pre/mid sets touch */
    int restore_n;
    PhaseEquip restore[PHASE_EQUIP_MAX];
} PhaseActionOverride;
static PhaseActionOverride g_override;

/* The action sets the engine has worn lately, oldest first.  A launcher cannot poll fast
 * enough to catch a weaponskill's set (it is on for the ~one second between the held action
 * and its result), so the engine keeps the windows itself and the status reports them: the
 * gear page shows every swap even when it sampled after the set was already gone. */
enum { PHASE_HISTORY = 16 };
typedef struct PhaseHistory
{
    uint64_t at, until; /* ms; until is 0 while the set is still on */
    uint16_t category, action;
    int16_t set; /* index into the table that was current when it went on */
} PhaseHistory;
static PhaseHistory g_history[PHASE_HISTORY];
static _Atomic int g_history_n; /* entries ever added; the ring position is n % PHASE_HISTORY */
static _Atomic uint64_t g_history_seq; /* odd while a writer is inside the ring */
/* The action set worn now, and when it went on (-1: the state set). */
static _Atomic int g_action_set = -1;
static _Atomic uint64_t g_action_at;
/* The last action registration, for the retransmit guard in xi_phase_action. */
static _Atomic uint32_t g_last_action_key;
static _Atomic uint32_t g_last_action_seq;
static _Atomic uint64_t g_last_action_at;
/* A re-sent 0x01A carries the same packet sequence; a real repeat cannot come this fast. */
#define PHASE_ACTION_REPEAT_MS 3000u

static uint64_t now_ms(void) { return rt_monotonic_ns() / 1000000ull; }

static void history_lock(void)
{
    for (;;)
    {
        uint64_t s = atomic_load_explicit(&g_history_seq, memory_order_acquire);
        if (s & 1)
            continue;
        if (atomic_compare_exchange_strong_explicit(&g_history_seq, &s, s + 1,
                                                    memory_order_acq_rel,
                                                    memory_order_acquire))
            return;
    }
}

static void history_unlock(void)
{
    uint64_t s = atomic_load_explicit(&g_history_seq, memory_order_acquire);
    atomic_store_explicit(&g_history_seq, s + 1, memory_order_release);
}

/* Newest first, copied while no writer is inside the ring.  Returns the number copied. */
static int history_snapshot(PhaseHistory* out)
{
    for (;;)
    {
        uint64_t s = atomic_load_explicit(&g_history_seq, memory_order_acquire);
        if (s & 1)
            continue;
        int n = atomic_load_explicit(&g_history_n, memory_order_acquire);
        int count = n < PHASE_HISTORY ? n : PHASE_HISTORY;
        for (int i = 0; i < count; ++i)
            out[i] = g_history[(n - 1 - i) % PHASE_HISTORY];
        if (atomic_load_explicit(&g_history_seq, memory_order_acquire) == s)
            return count;
    }
}

/* Close the window of the set that is on, if one is. */
static void history_close(uint64_t now)
{
    history_lock();
    int n = atomic_load_explicit(&g_history_n, memory_order_relaxed);
    if (n > 0)
    {
        PhaseHistory* e = &g_history[(n - 1) % PHASE_HISTORY];
        if (!e->until)
            e->until = now;
    }
    atomic_store_explicit(&g_action_set, -1, memory_order_release);
    history_unlock();
}

/* An action set went on.  A still-open window (an action that never resolved) is closed at
 * this action's start so the history never shows two sets on at once. */
static void history_start(uint16_t category, uint16_t action, int16_t set, uint64_t now)
{
    history_lock();
    int n = atomic_load_explicit(&g_history_n, memory_order_relaxed);
    if (n > 0)
    {
        PhaseHistory* e = &g_history[(n - 1) % PHASE_HISTORY];
        if (!e->until)
            e->until = now;
    }
    PhaseHistory* e = &g_history[n % PHASE_HISTORY];
    e->at = now;
    e->until = 0;
    e->category = category;
    e->action = action;
    e->set = set;
    atomic_store_explicit(&g_history_n, n + 1, memory_order_release);
    atomic_store_explicit(&g_action_set, set, memory_order_release);
    atomic_store_explicit(&g_action_at, now, memory_order_release);
    history_unlock();
}

/* Drop every window: the set indices belong to the plan being replaced. */
static void history_clear(void)
{
    history_lock();
    atomic_store_explicit(&g_history_n, 0, memory_order_release);
    atomic_store_explicit(&g_action_set, -1, memory_order_release);
    atomic_store_explicit(&g_action_at, 0, memory_order_release);
    history_unlock();
}

/* The packet's bits are little-endian within each byte (the client's own order). */
static uint32_t bits_le(const uint8_t* b, int bit, int count)
{
    uint32_t v = 0;
    for (int i = 0; i < count; ++i)
        v |= (uint32_t)((b[(bit + i) >> 3] >> ((bit + i) & 7)) & 1u) << i;
    return v;
}

static uint32_t packet_u32(const uint8_t* p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

/* 1 when every buff a conditional rule names is up.  A rule with no condition is always on. */
static int rule_buffs_active(const PhaseRule* rule)
{
    for (int i = 0; i < rule->n_buffs; ++i)
    {
        uint16_t id = rule->buffs[i];
        if (id >= PHASE_BUFF_IDS)
            return 0;
        for (;;)
        {
            unsigned before = atomic_load_explicit(&g_buff_epoch, memory_order_acquire);
            if (before & 1u)
                continue; /* the addon is rewriting the list; the write is very short */
            uint32_t word = atomic_load_explicit(&g_buff_bits[id >> 5],
                                                 memory_order_relaxed);
            unsigned after = atomic_load_explicit(&g_buff_epoch, memory_order_acquire);
            if (before == after)
            {
                if (!((word >> (id & 31)) & 1u))
                    return 0;
                break;
            }
        }
    }
    return 1;
}

/* Pick the exact rule for this action.  A conditional rule beats the unconditional one, and a
 * rule that names more buffs beats one that names fewer, so "(Impetus, Focus)" wins over
 * "(Impetus)" while both are up.  A category rule with action 0 stays the last fallback. */
static const PhaseRule* find_rule(const PhaseTable* t, uint16_t category, uint16_t action)
{
    const PhaseRule* best = NULL;
    int best_buffs = -1;
    for (int i = 0; i < t->nrules; ++i)
    {
        const PhaseRule* rule = &t->rules[i];
        if (rule->category != category || rule->action != action)
            continue;
        if (!rule_buffs_active(rule))
            continue;
        if ((int)rule->n_buffs > best_buffs)
        {
            best = rule;
            best_buffs = (int)rule->n_buffs;
        }
    }
    if (best)
        return best;
    for (int i = 0; i < t->nrules; ++i)
    {
        const PhaseRule* rule = &t->rules[i];
        if (rule->category == category && rule->action == 0
                && rule_buffs_active(rule))
            return rule;
    }
    return NULL;
}

/* What each equipment slot is known to be wearing: bag << 8 | (inventory slot + 1), 0 when
 * unknown.  A state set only sends the slots whose item differs - GearSwap's own behaviour - so
 * a movement step that changes four pieces does not re-send the other eleven.  Every piece is a
 * 0x050 the client has to apply and the server answers with a whole equipment follow-up, and a
 * following team that flapped between the idle and movement sets was fielding 60-136 a second.
 *
 * Action sets (precast, midcast, the return set) are sent whole: they are one batch per action,
 * and diffing the midcast against the precast would need the server's answer before the restore
 * is built.  They still update the table, so the state set that follows is diffed against what
 * the action left on.  The engine trusts its own sends; a hand change, an unequip and a zone,
 * job or plan change forget the slots they invalidate (see xi_phase_equip_echo). */
static _Atomic uint32_t g_worn_equip[16];

static uint32_t equip_key(int bag, int slot)
{
    /* Inventory slots are 1-based; the +1 keeps a bag-0 slot-0 item out of the "unknown" 0. */
    return ((uint32_t)(bag & 0xFF) << 8) | (uint32_t)((slot + 1) & 0xFF);
}

static uint32_t worn_get(int kind)
{
    return atomic_load_explicit(&g_worn_equip[kind & 15], memory_order_acquire);
}

static void worn_set(int kind, uint32_t key)
{
    atomic_store_explicit(&g_worn_equip[kind & 15], key, memory_order_release);
}

/* Forget the whole table: a zone-in, a job change (the server auto-equips for the new job), a
 * different character or a manual Wear set.  The next set is then sent whole, once, which is
 * the resync after a change the engine could not see. */
static void worn_forget(void)
{
    for (int i = 0; i < 16; ++i)
        atomic_store_explicit(&g_worn_equip[i], 0, memory_order_release);
}

/* `diff`: leave out a piece that is already on.  The state sets diff; the action sets do not. */
static void copy_set(const PhaseSet* s, PhaseEquip* out, int* n, int diff)
{
    unsigned locked = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
    int k = 0;
    for (int i = 0; i < s->n; ++i)
    {
        PhaseEquip e = s->e[i];
        if (locked & (1u << e.kind))
            continue;
        uint32_t key = equip_key(e.bag, e.slot);
        if (diff && worn_get(e.kind) == key)
            continue;
        worn_set(e.kind, key);
        out[k++] = e;
    }
    *n = k;
}

void xi_phase_equip_echo(int slot, int kind, int bag)
{
    if (kind < 0 || kind >= 16)
        return;
    /* Only the server's "nothing in this slot" form changes the table: an unequip, or the off
     * hand a two-hander just cleared.  The equip echoes are the engine's own sends coming back;
     * applying them would let the precast echo overwrite the midcast the return set is about to
     * be diffed against.  A hand change is seen on the client's outgoing 0x050 instead
     * (xi_phase_forget_slot), which is the only other way an equip echo differs from the table. */
    if (slot == 0)
        worn_set(kind, 0);
    /* A pinned weapon is the one exception: an equip echo outside an action window is a real
     * hand change (the engine never sends a locked weapon unless it is putting the lock back),
     * so the lock follows the copy the player just chose.  Inside an action window the echo is
     * the sanctioned swap (the Bard's instrument) and must not overwrite the locked hand. */
    if (kind < 4 && !atomic_load_explicit(&g_override.active, memory_order_acquire)
            && (atomic_load_explicit(&g_locked, memory_order_acquire)
                || (atomic_load_explicit(&g_locked_slots, memory_order_acquire)
                    & (1u << kind))))
        atomic_store_explicit(&g_locked_equip[kind],
                              slot == 0 ? 0 : equip_key(bag, slot), memory_order_release);
}

void xi_phase_forget_slot(int kind)
{
    if (kind >= 0 && kind < 16)
        worn_set(kind, 0);
}

void xi_phase_forget(void)
{
    worn_forget();
}

/* A manual set from the addon names the exact copy it put on.  Keep that in the worn table so
 * the next state set can diff against it, and so a locked action's temporary swap can restore
 * a pinned weapon instead of leaving the action's piece on. */
void xi_phase_remember(int kind, int bag, int slot)
{
    if (kind >= 0 && kind < 16)
        worn_set(kind, equip_key(bag, slot));
    /* A Wear & lock remembers the pieces before the mask is pinned, and the control addon
     * remembers the live weapon slots before any lock command.  Keeping the copy here means
     * lock_slots() can capture it even when the worn table was forgotten by a zone. */
    if (kind >= 0 && kind < 4
            && (atomic_load_explicit(&g_locked, memory_order_acquire)
                || (atomic_load_explicit(&g_locked_slots, memory_order_acquire)
                    & (1u << kind))))
        atomic_store_explicit(&g_locked_equip[kind], equip_key(bag, slot),
                              memory_order_release);
}

/* Which set the current state wears. Engagement wins, then movement, then the idle set for the
 * zone; without a zone yet the old idle fallback keeps the engine useful during login. */
static int state_index(const PhaseTable* t)
{
    if (!t)
        return -1;
    /* Kiting is a forced state; engaged and resting are next, then movement, then the idle
     * focus the user picked, then the zone's idle set. */
    if (atomic_load_explicit(&g_kiting, memory_order_acquire) && t->kite >= 0)
        return t->kite;
    if (atomic_load_explicit(&g_engaged, memory_order_acquire) && t->engage >= 0)
        return t->engage;
    if (atomic_load_explicit(&g_resting, memory_order_acquire) && t->rest >= 0)
        return t->rest;
    if (atomic_load_explicit(&g_moving, memory_order_acquire) && t->move >= 0)
        return t->move;
    int focus = atomic_load_explicit(&g_focus, memory_order_acquire);
    if (focus >= 1 && focus <= 5 && t->focus[focus - 1] >= 0)
        return t->focus[focus - 1];
    int town = atomic_load_explicit(&g_town, memory_order_acquire);
    if (town > 0 && t->town >= 0)
        return t->town;
    if (town == 0 && t->field >= 0)
        return t->field;
    if (t->idle >= 0)
        return t->idle;
    if (t->town >= 0)
        return t->town;
    if (t->field >= 0)
        return t->field;
    return -1;
}

/* Wear the current state's set. `force` re-sends it even when it is the one already on (a plan
 * just pushed, a zone/job settle, unlocking or re-pinning a slot); the automatic transitions
 * leave the gear alone when the set has not changed, which is what stops a movement step while
 * engaged (or a repeat /attack) from re-equipping every piece. */
static int wear_state(const PhaseTable* t, PhasePlan* plan, int force)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    /* The full lock holds every piece, but it still re-asserts a locked weapon: a sanctioned
     * swap may have taken the hand off (a cast while disengaged, a Bard's Nitro song), and the
     * lock's own promise is that the chosen weapon is what is worn. */
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return append_locked_weapons(plan);
    int idx = state_index(t);
    if (idx < 0 || idx >= t->nsets)
        return 0;
    if (!force && atomic_load_explicit(&g_worn_state, memory_order_acquire) == idx)
        return 0;
    copy_set(&t->sets[idx], plan->pre, &plan->pre_n, 1);
    atomic_store_explicit(&g_worn_state, idx, memory_order_release);
    /* Drawing the weapon re-arms its lock.  The engaged set (the player's TP set) does not
     * always name a weapon - a weaponset outside the state sets owns it - so filtering the
     * slot out of the set is not enough: after a disengaged cast the old cast hand would stay
     * on until the client changed it by hand. */
    if (atomic_load_explicit(&g_engaged, memory_order_acquire))
        append_locked_weapons(plan);
    if (plan->pre_n >= 6)
        xi_log("[gear] wear %s: %d pieces", t->names[idx][0] ? t->names[idx] : "state",
               plan->pre_n);
    return plan->pre_n > 0;
}

static int state_set(const PhaseTable* t, PhasePlan* plan)
{
    return wear_state(t, plan, 0);
}

/* The worn table stores bag << 8 | (inventory slot + 1); reverse it into a 0x050 entry. */
static int decode_worn(uint32_t key, int kind, PhaseEquip* out)
{
    if (key == 0)
        return 0;
    int slot = (int)(key & 0xFFu);
    if (slot <= 0)
        return 0;
    out->slot = (uint8_t)(slot - 1);
    out->kind = (uint8_t)kind;
    out->bag = (uint8_t)((key >> 8) & 0xFFu);
    return 1;
}

/* The last piece of one slot in a set; a set may name a slot twice and the later entry wins. */
static int set_piece_for_kind(const PhaseTable* t, int set_index, int kind, PhaseEquip* out)
{
    if (!t || set_index < 0 || set_index >= t->nsets)
        return 0;
    const PhaseSet* set = &t->sets[set_index];
    for (int i = set->n - 1; i >= 0; --i)
        if (set->e[i].kind == kind)
        {
            *out = set->e[i];
            return 1;
        }
    return 0;
}

static int plan_has_kind(const PhasePlan* plan, int kind)
{
    for (int i = 0; i < plan->pre_n; ++i)
        if (plan->pre[i].kind == kind)
            return 1;
    return 0;
}

/* Put back every locked main/sub/ranged copy that is not already on.  This is what makes a pin
 * a lock rather than a filter: the state set may not name the weapon at all (a weaponset outside
 * the sets), and a sanctioned temporary swap must still end on the hand the player locked.
 * Ammo is deliberately not re-armed here: the throw guard owns that slot while a ranged action
 * is in flight (it swaps in a stackable piece and puts the original back afterwards), and a
 * state set re-asserting a pinned Tathlum in that window would undo the throw protection. */
static int append_locked_weapons(PhasePlan* plan)
{
    unsigned mask;
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        mask = PHASE_WEAPON_SLOTS;
    else
        mask = atomic_load_explicit(&g_locked_slots, memory_order_acquire) & PHASE_WEAPON_SLOTS;
    int added = 0;
    for (int kind = 0; kind < 3; ++kind)
    {
        if (!(mask & (1u << kind)) || plan_has_kind(plan, kind))
            continue;
        uint32_t key = atomic_load_explicit(&g_locked_equip[kind], memory_order_acquire);
        if (!key)
            continue;
        PhaseEquip piece;
        if (!decode_worn(key, kind, &piece))
            continue;
        if (worn_get(kind) == key)
            continue;
        if (plan->pre_n >= PHASE_EQUIP_MAX)
            break;
        plan->pre[plan->pre_n++] = piece;
        worn_set(kind, key);
        added = 1;
    }
    return added;
}

/* The copy a lock should own for one weapon slot.  The worn table is the engine's own last
 * send; the current state's set is the fallback when a zone forgot the table. */
static uint32_t current_weapon_key(const PhaseTable* t, int kind)
{
    uint32_t key = worn_get(kind);
    if (key)
        return key;
    PhaseEquip piece;
    if (set_piece_for_kind(t, state_index(t), kind, &piece))
        return equip_key(piece.bag, piece.slot);
    return 0;
}

/* `full` (the Lock button) owns all four weapon slots; otherwise only the pinned ones. */
static void capture_weapon_locks(const PhaseTable* t, unsigned mask, int full)
{
    for (int kind = 0; kind < 4; ++kind)
    {
        if (full || (mask & (1u << kind)))
        {
            uint32_t key = current_weapon_key(t, kind);
            if (key)
                atomic_store_explicit(&g_locked_equip[kind], key, memory_order_release);
        }
        else
            atomic_store_explicit(&g_locked_equip[kind], 0, memory_order_release);
    }
}

/* Remember what the action's pre/mid sets will replace.  Worn table first (the exact pieces the
 * engine last sent), then the locked copy for a weapon slot (that is the hand the lock promises,
 * even when the TP set does not name it), then the locked/current state set for slots a hand
 * equip made unknown. */
static void begin_action_override(const PhaseTable* t, const PhasePlan* plan,
                                  const uint32_t worn_before[16], int fallback_set)
{
    unsigned changed = 0;
    for (int i = 0; i < plan->pre_n; ++i)
        if (plan->pre[i].kind < 32)
            changed |= 1u << plan->pre[i].kind;
    for (int i = 0; i < plan->mid_n; ++i)
        if (plan->mid[i].kind < 32)
            changed |= 1u << plan->mid[i].kind;
    g_override.changed = changed;
    atomic_store_explicit(&g_override.active, 1, memory_order_release);
    g_override.restore_n = 0;
    for (int kind = 0; kind < 16; ++kind)
    {
        if (!(changed & (1u << kind)))
            continue;
        PhaseEquip piece;
        int found = decode_worn(worn_before[kind], kind, &piece);
        if (!found && kind < 4)
            found = decode_worn(atomic_load_explicit(&g_locked_equip[kind],
                                                     memory_order_acquire),
                                kind, &piece);
        if (!found)
            found = set_piece_for_kind(t, fallback_set, kind, &piece);
        if (!found)
            found = set_piece_for_kind(t, state_index(t), kind, &piece);
        if (found)
            g_override.restore[g_override.restore_n++] = piece;
    }
}

static int fill_override_restore(PhasePlan* plan)
{
    unsigned restored = 0;
    for (int i = 0; i < g_override.restore_n; ++i)
    {
        plan->restore[i] = g_override.restore[i];
        restored |= 1u << g_override.restore[i].kind;
        worn_set(g_override.restore[i].kind,
                 equip_key(g_override.restore[i].bag, g_override.restore[i].slot));
    }
    plan->restore_n = g_override.restore_n;
    /* A slot whose original was unknown must be re-sent by the next state set, not skipped. */
    unsigned unknown = g_override.changed & ~restored;
    for (int kind = 0; kind < 16; ++kind)
        if (unknown & (1u << kind))
            worn_set(kind, 0);
    atomic_store_explicit(&g_override.active, 0, memory_order_release);
    g_override.changed = 0;
    g_override.restore_n = 0;
    atomic_store_explicit(&g_worn_state, -1, memory_order_release);
    return plan->restore_n > 0;
}

static int fill_restore(const PhaseTable* t, PhasePlan* plan)
{
    plan->restore_n = 0;
    if (atomic_load_explicit(&g_override.active, memory_order_acquire))
        return fill_override_restore(plan);
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return 0;
    int fell_back = 0;
    int idx = state_index(t);
    if (idx < 0 || idx >= t->nsets)
    {
        idx = t->restore;
        fell_back = 1;
    }
    if (idx < 0 || idx >= t->nsets)
        return 0;
    copy_set(&t->sets[idx], plan->restore, &plan->restore_n, 0);
    /* The return set is the state's own set again, so a later transition to that same state has
     * nothing to wear; a plain fallback set is not a state and leaves the worn state unknown. */
    atomic_store_explicit(&g_worn_state, fell_back ? -1 : idx, memory_order_release);
    return plan->restore_n > 0;
}

/* Ask for the state set to be re-worn once the client has settled (a zone, a job change or a
 * stance flip). The addon's watch loop calls xi_phase_pending every frame. */
static void want_state(uint64_t due)
{
    atomic_store_explicit(&g_state_due, due, memory_order_release);
    atomic_store_explicit(&g_state_pending, 1, memory_order_release);
}

/* Take the one-shot pre-action gear for this action.  The buffer is cleared either way: it was
 * queued for the addon's next action, and that action is this one. */
static int take_precache(uint16_t action, PhaseEquip* out)
{
    int n = atomic_exchange_explicit(&g_precache_n, 0, memory_order_acq_rel);
    unsigned want = atomic_load_explicit(&g_precache_action, memory_order_acquire);
    if (n <= 0 || want != action)
        return 0;
    if (n > PHASE_EQUIP_MAX)
        n = PHASE_EQUIP_MAX;
    for (int i = 0; i < n; ++i)
        out[i] = g_precache[i];
    return n;
}

/* Put the picked piece over the library's own precast piece for that slot.  The jug has to be
 * the ammo the server sees, so it wins when both name ammo. */
static void merge_precache(PhasePlan* plan, const PhaseEquip* extra, int n)
{
    unsigned locked = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
    for (int i = 0; i < n; ++i)
    {
        /* A pinned slot is pinned for every set, including this one. */
        if (extra[i].kind < 32 && (locked & (1u << extra[i].kind)))
            continue;
        int at = -1;
        for (int j = 0; j < plan->pre_n; ++j)
        {
            if (plan->pre[j].kind == extra[i].kind)
            {
                at = j;
                break;
            }
        }
        if (at >= 0)
            plan->pre[at] = extra[i];
        else if (plan->pre_n < PHASE_EQUIP_MAX)
            plan->pre[plan->pre_n++] = extra[i];
    }
}

int xi_phase_action(uint16_t category, uint16_t action, uint16_t seq, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    PhaseEquip extra[PHASE_EQUIP_MAX];
    int extra_n = take_precache(action, extra);
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    /* One action, one set.  The client re-sends the 0x01A until the server acknowledges it, and
     * every copy reaches this hook; re-queuing the whole pre set per copy was most of the gear
     * churn in a fight (60 equips for one weaponskill).  /attack is excluded: it is a state,
     * and its repeat path already leaves the worn engaged set alone.
     *
     * The pending flag alone was not enough: the result clears it before the last retransmits
     * arrive, so a weaponskill still registered three to five times.  A retransmit is the same
     * packet, so it carries the same sequence number (bytes 2-3 of the sub-message); the same
     * category and action on the same sequence inside the window is a copy, not a new action. */
    if (category != PHASE_ACTION_ATTACK)
    {
        uint32_t key = ((uint32_t)category << 16) | (uint32_t)action;
        uint64_t at = now_ms();
        if (atomic_load_explicit(&g_last_action_key, memory_order_acquire) == key
                && atomic_load_explicit(&g_last_action_seq, memory_order_acquire)
                   == (uint32_t)seq
                && at - atomic_load_explicit(&g_last_action_at, memory_order_acquire)
                   < PHASE_ACTION_REPEAT_MS)
            return 0;
        atomic_store_explicit(&g_last_action_key, key, memory_order_release);
        atomic_store_explicit(&g_last_action_seq, (uint32_t)seq, memory_order_release);
        atomic_store_explicit(&g_last_action_at, at, memory_order_release);
    }
    atomic_fetch_add(&g_actions, 1);
    /* /attack is a whole-category state, not an action with an id: the client sends
     * category 2 with the action id left at zero, and the engaged set goes on before the
     * server's animation arrives.  /attack off (category 4) is deliberately not handled:
     * the client sends it by itself when the target leaves auto-attack reach, and the
     * server keeps that engagement alive for range kiting.  The server's 0x00D animation
     * is the authority for sheathing, so a range disengage never moves the gear. */
    if (category == PHASE_ACTION_ATTACK)
    {
        atomic_store_explicit(&g_resting, 0, memory_order_release);
        int was = atomic_exchange_explicit(&g_engaged, 1, memory_order_acq_rel);
        /* Locked still follows the state (the next unlock needs to know which set to wear),
         * it just does not move any gear.  A repeated /attack for the same target is the
         * client re-drawing after a range step, not a new engagement: the engaged set is
         * already on, so wear_state leaves it alone. */
        int worn = wear_state(t, plan, 0);
        if (was != 1)
            atomic_fetch_add(&g_swapped, 1);
        return worn;
    }
    int locked = atomic_load_explicit(&g_locked, memory_order_acquire);
    unsigned locked_slots = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
    int may_override = (category == PHASE_ACTION_MAGIC ||
                        category == PHASE_ACTION_SKILL ||
                        category == PHASE_ACTION_ABILITY);
    const PhaseRule* r = find_rule(t, category, action);
    /* The automatic set (the Nuking group's Magic Burst row) replaces the rule's ordinary
     * midcast set only while the addon reports an open window.  The precast set is unchanged:
     * the fast-cast gear is the same either way. */
    int mid = r ? r->mid : -1;
    if (r && r->burst >= 0 && r->burst < t->nsets
            && atomic_load_explicit(&g_burst, memory_order_acquire))
        mid = r->burst;
    int has_set = r && ((r->pre >= 0 && r->pre < t->nsets) || (mid >= 0 && mid < t->nsets));
    if (!has_set && !extra_n)
        return 0;
    /* The full lock stops ordinary gear changes, but an action with its own pre/mid set
     * (a job ability, song, spell or weaponskill) may unlock just long enough to wear it.
     * The previous pieces are restored when the action resolves.
     *
     * The weapon is the exception to that exception.  A main/sub/ranged/ammo slot the
     * player pinned or froze with the full lock is the hand they chose, and an ability's
     * set must not take it off behind their back: DRK Last Resort's library set names
     * Apocalypse, so using it while a Helheim was pinned moved the server to Scythe and
     * replaced every great-sword weapon skill with the scythe list.  A weaponskill is not
     * exempt either: its damage and the client's weapon-skill menu are built from the weapon
     * that is on, so swapping it for the set's weapon is the TP/WS loss the lock prevents.
     *
     * Two swaps are sanctioned: a spell cast while the weapon is sheathed (the player is not
     * meleeing, so no TP is at stake), and a Bard song under Nitro (Nightingale + Troubadour),
     * whose set names the instrument a pinned Bard could not sing without.  A Corsair Phantom
     * Roll keeps its duration-set exception.  Every one of them is put back when the action
     * resolves. */
    int engaged = atomic_load_explicit(&g_engaged, memory_order_acquire);
    int nitro_song = (category == PHASE_ACTION_MAGIC && r && r->song && is_bard_main()
                      && atomic_load_explicit(&g_nitro, memory_order_acquire));
    int allow_weapon_swap = ((category == PHASE_ACTION_MAGIC && !locked && !engaged)
                             || nitro_song
                             || (category == PHASE_ACTION_ABILITY
                                 && is_phantom_roll(action)));
    if (locked && !may_override)
        return 0;
    int override = may_override && (locked || locked_slots != 0);
    /* Only the weapon slots are pinned through an action: the action's own armour set is meant
     * to be worn (and restored afterwards), so an armour pin on, say, the head does not block a
     * weaponskill's head piece.  The full lock releases the armour too, but owns all four weapon
     * slots so an action cannot quietly replace the hand the player froze; the sanctioned swaps
     * above clear that ownership for their window. */
    unsigned action_pins = locked ? PHASE_WEAPON_SLOTS
                                  : (locked_slots & PHASE_WEAPON_SLOTS);
    if (allow_weapon_swap)
        action_pins = 0;
    uint32_t worn_before[16];
    int fallback_set = atomic_load_explicit(&g_lock_set, memory_order_acquire);
    if (!locked || fallback_set < 0)
        fallback_set = state_index(t);
    if (override)
    {
        for (int i = 0; i < 16; ++i)
            worn_before[i] = worn_get(i);
        if (locked)
            atomic_store_explicit(&g_locked, 0, memory_order_release);
        /* Keep the armour and the still-locked weapon slots on while the action's set is
         * built; copy_set() then leaves them alone. */
        atomic_store_explicit(&g_locked_slots, action_pins, memory_order_release);
    }
    if (r && r->pre >= 0 && r->pre < t->nsets)
        copy_set(&t->sets[r->pre], plan->pre, &plan->pre_n, 0);
    if (mid >= 0 && mid < t->nsets)
        copy_set(&t->sets[mid], plan->mid, &plan->mid_n, 0);
    if (extra_n)
        merge_precache(plan, extra, extra_n);
    if (r && r->pre >= 0 && r->pre < t->nsets && plan->pre_n)
        history_start(category, action, (int16_t)r->pre, now_ms());
    if (override)
    {
        if (locked)
            atomic_store_explicit(&g_locked, 1, memory_order_release);
        atomic_store_explicit(&g_locked_slots, locked_slots, memory_order_release);
        if (plan->pre_n || plan->mid_n)
            begin_action_override(t, plan, worn_before, fallback_set);
    }
    if (!plan->pre_n && !plan->mid_n)
        return 0;
    if (plan->pre_n + plan->mid_n >= 6)
        xi_log("[gear] action %u/%u seq=%u: pre %d, mid %d", category, action, seq, plan->pre_n, plan->mid_n);
    plan->hold = 1;
    atomic_store_explicit(&g_pending, 1, memory_order_release);
    atomic_store_explicit(&g_pending_at, now_ms(), memory_order_release);
    atomic_store_explicit(&g_pending_action, action, memory_order_release);
    atomic_store_explicit(&g_pending_category, category, memory_order_release);
    atomic_fetch_add(&g_seen, 1);
    atomic_fetch_add(&g_held, 1);
    return 1;
}

int xi_phase_result(const uint8_t* packet, size_t size, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    if (size < 16 || !atomic_load_explicit(&g_pending, memory_order_acquire))
        return 0;
    /* 0x028 is a 4-byte sub-message header, then the packed byte count, then the bit stream. */
    const uint8_t* body = packet + 5;
    uint32_t category = bits_le(body, 42, 4);
    if (category != PHASE_RESULT_SKILL && category != PHASE_RESULT_MAGIC &&
        category != PHASE_RESULT_ABILITY)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    uint32_t actor = bits_le(body, 0, 32);
    uint32_t action = bits_le(body, 46, 32);
    if (t->player && actor != t->player)
        return 0;
    if (action != atomic_load_explicit(&g_pending_action, memory_order_acquire))
        return 0;
    atomic_store_explicit(&g_pending, 0, memory_order_release);
    history_close(now_ms());
    if (!fill_restore(t, plan))
        return 0;
    atomic_fetch_add(&g_restored, 1);
    return 1;
}

void xi_phase_restore_if_stale(PhasePlan* plan, int* have)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    *have = 0;
    if (!atomic_load_explicit(&g_pending, memory_order_acquire))
        return;
    uint64_t now = now_ms();
    unsigned category = atomic_load_explicit(&g_pending_category, memory_order_acquire);
    uint64_t timeout = category == PHASE_ACTION_ABILITY ? 4000u : PHASE_STALE_MS;
    if (now - atomic_load_explicit(&g_pending_at, memory_order_acquire) < timeout)
        return;
    atomic_store_explicit(&g_pending, 0, memory_order_release);
    history_close(now);
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled || !fill_restore(t, plan))
        return;
    *have = 1;
    atomic_fetch_add(&g_stale, 1);
}

int xi_phase_player_animation(const uint8_t* packet, size_t size)
{
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled || !t->player || size < 4 + 0x1C)
        return 0;
    /* 0x00D: 4-byte sub-message header, then the entity update. The General mask (0x04) and
     * byte 0x1B are the animation; 1 is the drawn-weapon battle stance. */
    const uint8_t* b = packet + 4;
    if (packet_u32(b) != t->player || !(b[6] & 0x04))
        return 0;
    int on = b[0x1B] == 1;
    if (on)
        atomic_store_explicit(&g_resting, 0, memory_order_release);
    int was = atomic_exchange_explicit(&g_engaged, on, memory_order_acq_rel);
    if (was == on)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    /* The server already told the client what to draw; only the gear follows, at once. */
    if (!atomic_load_explicit(&g_locked, memory_order_acquire))
        want_state(now_ms());
    return 1;
}

void xi_phase_zone(int zone, int town)
{
    int old_zone = atomic_exchange_explicit(&g_zone, zone, memory_order_acq_rel);
    int old_town = atomic_exchange_explicit(&g_town, town ? 1 : 0, memory_order_acq_rel);
    int was_engaged = atomic_exchange_explicit(&g_engaged, 0, memory_order_acq_rel);
    atomic_store_explicit(&g_moving, 0, memory_order_release);
    atomic_store_explicit(&g_resting, 0, memory_order_release);
    atomic_store_explicit(&g_burst, 0, memory_order_release);
    /* A zone-in is a fresh world: the server re-sends the outfit (0x050 echoes refill the
     * worn table) and auto-equips if it has none, so the old table is not trusted.  An action
     * in flight is gone with the old zone too. */
    worn_forget();
    history_close(now_ms());
    atomic_store_explicit(&g_override.active, 0, memory_order_release);
    /* Every zone-in is a fresh world for the client: stand in the idle set once it has loaded. */
    if (old_zone != zone || old_town != (town ? 1 : 0) || was_engaged)
        want_state(now_ms() + PHASE_SETTLE_MS);
}

/* A job change throws away every session lock. The held set, the weapon pins, kiting, resting
 * and the idle focus all belong to the job that was being played, and the new job's weapon is
 * exactly what a lock on the old one would keep off. The new state's set goes out once the
 * client has settled, the same path a zone uses. */
static void release_session_locks(void)
{
    atomic_store_explicit(&g_override.active, 0, memory_order_release);
    atomic_store_explicit(&g_locked, 0, memory_order_release);
    atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    atomic_store_explicit(&g_locked_slots, 0, memory_order_release);
    for (int i = 0; i < 4; ++i)
        atomic_store_explicit(&g_locked_equip[i], 0, memory_order_release);
    atomic_store_explicit(&g_nitro, 0, memory_order_release);
    atomic_store_explicit(&g_burst, 0, memory_order_release);
    atomic_store_explicit(&g_kiting, 0, memory_order_release);
    atomic_store_explicit(&g_resting, 0, memory_order_release);
    atomic_store_explicit(&g_focus, 0, memory_order_release);
    /* A job change, or a different character: the server auto-equips for the new job and the
     * slots may no longer hold what this table says, so the next set goes out whole. */
    worn_forget();
    want_state(now_ms() + PHASE_SETTLE_MS);
}

void xi_phase_job(int job, int sub)
{
    /* The support job is a job change too: it rebuilds the same block and can leave the main
     * job untouched, so the pair has to be compared, not just the main job. */
    int was = atomic_exchange_explicit(&g_job, job, memory_order_acq_rel);
    int had_sub = atomic_exchange_explicit(&g_sub_job, sub, memory_order_acq_rel);
    if (was != job || had_sub != sub)
        release_session_locks();
}

int xi_phase_moving(int moving, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    int on = moving ? 1 : 0;
    int was = atomic_exchange_explicit(&g_moving, on, memory_order_acq_rel);
    if (was == on)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    return state_set(t, plan);
}

int xi_phase_engaged(int on, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    on = on ? 1 : 0;
    int was = atomic_exchange_explicit(&g_engaged, on, memory_order_acq_rel);
    if (was == on)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    return state_set(t, plan);
}

int xi_phase_apply(PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    return wear_state(t, plan, 1);
}

int xi_phase_pending(PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    if (!atomic_load_explicit(&g_state_pending, memory_order_acquire))
        return 0;
    if (now_ms() < atomic_load_explicit(&g_state_due, memory_order_acquire))
        return 0;
    atomic_store_explicit(&g_state_pending, 0, memory_order_release);
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    return wear_state(t, plan, 1);
}

int xi_phase_lock(int on, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (on)
    {
        if (!atomic_exchange_explicit(&g_locked, 1, memory_order_acq_rel))
        {
            int idx = state_index(t);
            atomic_store_explicit(&g_lock_set, idx >= 0 ? idx : -1, memory_order_release);
            /* The full lock owns all four weapon slots, so capture every hand it must hold. */
            capture_weapon_locks(t, PHASE_WEAPON_SLOTS, 1);
            /* Nothing in flight may overwrite the held set. */
            atomic_store_explicit(&g_pending, 0, memory_order_release);
            atomic_store_explicit(&g_state_pending, 0, memory_order_release);
            atomic_fetch_add(&g_swapped, 1);
        }
        return 0;
    }
    if (!atomic_exchange_explicit(&g_locked, 0, memory_order_acq_rel))
        return 0;
    atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    /* The full lock's weapon copies end here; only the slots still pinned keep the copy the
     * lock last knew (recapturing now would adopt a hand a sanctioned swap left on). */
    {
        unsigned pins = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
        for (int kind = 0; kind < 4; ++kind)
            if (!(pins & (1u << kind)))
                atomic_store_explicit(&g_locked_equip[kind], 0, memory_order_release);
    }
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    /* The gear may have been changed by hand while the lock held it: put the state's set back. */
    return wear_state(t, plan, 1);
}

int xi_phase_kiting(int on, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    int want = on ? 1 : 0;
    int was = atomic_exchange_explicit(&g_kiting, want, memory_order_acq_rel);
    if (was == want)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    return state_set(t, plan);
}

int xi_phase_resting(int on, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    int want = on ? 1 : 0;
    int was = atomic_exchange_explicit(&g_resting, want, memory_order_acq_rel);
    if (was == want)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    return state_set(t, plan);
}

int xi_phase_focus(int mode, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    if (mode < 0 || mode > 5)
        mode = 0;
    int was = atomic_exchange_explicit(&g_focus, mode, memory_order_acq_rel);
    if (was == mode)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    return state_set(t, plan);
}

int xi_phase_lock_slots(unsigned mask, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    unsigned old = atomic_exchange_explicit(&g_locked_slots, mask, memory_order_acq_rel);
    if (old == mask)
        return 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    /* Remember the hand that is actually on for each pinned weapon slot.  The control addon
     * feeds the live bag/index through xi.phase.remember first, so this also works right after
     * a zone, when the engine's worn table is empty. */
    capture_weapon_locks(t, mask, atomic_load_explicit(&g_locked, memory_order_acquire) ? 1 : 0);
    if (!t || !t->enabled)
        return 0;
    /* Unlocking a slot should put the current state's piece back; locking one still re-sends
     * the rest of the set, already worn, so the client draws the pieces the mask still keeps. */
    return wear_state(t, plan, 1);
}

/* Nightingale + Troubadour are both up.  The host only decides whether a song may take the
 * instrument; the control addon reads the client's buff list and calls this each frame. */
void xi_phase_nitro(int on)
{
    atomic_store_explicit(&g_nitro, on ? 1 : 0, memory_order_release);
}

/* A magic-burst window is open on the player's target.  The control addon tracks it from the
 * closing action's 0x028 skillchain proc and pushes the flag every frame; the engine only
 * chooses a rule's burst set for an action taken while it is on.  It never builds a plan of its
 * own: the window starts and ends outside gear, so the addon owns the timing. */
void xi_phase_burst(int on)
{
    atomic_store_explicit(&g_burst, on ? 1 : 0, memory_order_release);
}

void xi_phase_buffs(const uint16_t* ids, int n)
{
    uint32_t bits[PHASE_BUFF_WORDS] = { 0 };
    for (int i = 0; i < n; ++i)
        if (ids[i] < PHASE_BUFF_IDS)
            bits[ids[i] >> 5] |= (uint32_t)1u << (ids[i] & 31);
    /* Odd epoch: a reader that sees it waits for the even one rather than a half-updated list. */
    atomic_fetch_add_explicit(&g_buff_epoch, 1, memory_order_acq_rel);
    for (int i = 0; i < PHASE_BUFF_WORDS; ++i)
        atomic_store_explicit(&g_buff_bits[i], bits[i], memory_order_relaxed);
    atomic_fetch_add_explicit(&g_buff_epoch, 1, memory_order_release);
}

void xi_phase_precache(uint16_t action, const PhaseEquip* equips, int n)
{
    if (n < 0)
        n = 0;
    if (n > PHASE_EQUIP_MAX)
        n = PHASE_EQUIP_MAX;
    for (int i = 0; i < n; ++i)
        g_precache[i] = equips[i];
    atomic_store_explicit(&g_precache_action, action, memory_order_release);
    /* Last: a reader that sees n sees the action and the pieces above. */
    atomic_store_explicit(&g_precache_n, n, memory_order_release);
}

/* `keep_settle` is for a plan push: the new table is applied by the settle that is already
 * scheduled, so a launcher push during a zone or job load does not cancel it and immediately
 * wear the whole outfit.  A clear cancels it. */
static void reset_plan(int keep_settle)
{
    atomic_store_explicit(&g_override.active, 0, memory_order_release);
    atomic_store_explicit(&g_pending, 0, memory_order_release);
    atomic_store_explicit(&g_pending_action, 0, memory_order_release);
    atomic_store_explicit(&g_pending_category, 0, memory_order_release);
    if (!keep_settle)
        atomic_store_explicit(&g_state_pending, 0, memory_order_release);
    atomic_store_explicit(&g_precache_n, 0, memory_order_release);
    /* A new table means new set indices: what was worn no longer names anything.  The worn
     * table itself is kept: it is keyed by item, not by set, and a pushed plan that changes a
     * spell mode or a weaponskill set must not re-send the whole outfit.  It is forgotten on a
     * zone, a job change and a different character, which are the times the gear itself may
     * have moved. */
    atomic_store_explicit(&g_worn_state, -1, memory_order_release);
    history_clear();
}

void xi_phase_reset(void)
{
    reset_plan(0);
}

/* --- xi.phase ------------------------------------------------------------------------------- */

static int abs_index(lua_State* L, int index) { return index > 0 ? index : lua_gettop(L) + index + 1; }

static void read_equip(lua_State* L, int index, PhaseEquip* e)
{
    index = abs_index(L, index);
    lua_rawgeti(L, index, 1);
    e->slot = (uint8_t)lua_tointeger(L, -1);
    lua_pop(L, 1);
    lua_rawgeti(L, index, 2);
    e->kind = (uint8_t)lua_tointeger(L, -1);
    lua_pop(L, 1);
    lua_rawgeti(L, index, 3);
    e->bag = (uint8_t)lua_tointeger(L, -1);
    lua_pop(L, 1);
}

static void read_set(lua_State* L, int index, PhaseSet* s)
{
    index = abs_index(L, index);
    int n = (int)lua_objlen(L, index);
    s->n = 0;
    for (int i = 1; i <= n && s->n < PHASE_EQUIP_MAX; ++i)
    {
        lua_rawgeti(L, index, i);
        if (lua_istable(L, -1))
            read_equip(L, lua_gettop(L), &s->e[s->n++]);
        lua_pop(L, 1);
    }
}

static void read_names(lua_State* L, int field, PhaseTable* t)
{
    lua_getfield(L, field, "names");
    if (lua_istable(L, -1))
    {
        int n = (int)lua_objlen(L, -1);
        for (int i = 1; i <= n && i <= t->nsets; ++i)
        {
            lua_rawgeti(L, -1, i);
            const char* name = lua_tostring(L, -1);
            if (name)
            {
                strncpy(t->names[i - 1], name, PHASE_NAME - 1);
                t->names[i - 1][PHASE_NAME - 1] = '\0';
            }
            lua_pop(L, 1);
        }
    }
    lua_pop(L, 1);
}

/* One state set, as the index into `sets` the addon built (1-based; 0 for none). A table is
 * still accepted, for a caller that sends the set itself instead of its index. */
static int read_state_index(lua_State* L, int field, const char* key, PhaseTable* t)
{
    lua_getfield(L, field, key);
    int idx = -1;
    if (lua_isnumber(L, -1))
    {
        idx = (int)lua_tointeger(L, -1) - 1;
    }
    else if (lua_istable(L, -1) && t->nsets < PHASE_SETS)
    {
        read_set(L, lua_gettop(L), &t->sets[t->nsets]);
        if (t->sets[t->nsets].n)
            idx = t->nsets++;
    }
    lua_pop(L, 1);
    return idx >= 0 && idx < t->nsets ? idx : -1;
}

static int p_set(lua_State* L)
{
    luaL_checktype(L, 1, LUA_TTABLE);
    PhaseTable* t = (PhaseTable*)calloc(1, sizeof *t);
    if (!t)
        return luaL_error(L, "phase: out of memory");
    t->restore = t->engage = t->idle = t->town = t->field = t->move = t->kite = t->rest = -1;
    for (int i = 0; i < 5; ++i)
        t->focus[i] = -1;
    lua_getfield(L, 1, "enabled");
    t->enabled = lua_toboolean(L, -1);
    lua_pop(L, 1);
    lua_getfield(L, 1, "player");
    t->player = (uint32_t)lua_tonumber(L, -1);
    lua_pop(L, 1);

    lua_getfield(L, 1, "sets");
    if (lua_istable(L, -1))
    {
        int n = (int)lua_objlen(L, -1);
        for (int i = 1; i <= n && t->nsets < PHASE_SETS; ++i)
        {
            lua_rawgeti(L, -1, i);
            if (lua_istable(L, -1))
            {
                read_set(L, lua_gettop(L), &t->sets[t->nsets]);
                if (t->sets[t->nsets].n)
                    t->nsets++;
            }
            lua_pop(L, 1);
        }
    }
    lua_pop(L, 1);
    read_names(L, 1, t);

    t->restore = (int16_t)read_state_index(L, 1, "restore", t);
    t->engage = (int16_t)read_state_index(L, 1, "engage", t);
    t->idle = (int16_t)read_state_index(L, 1, "idle", t);
    t->town = (int16_t)read_state_index(L, 1, "idle_town", t);
    t->field = (int16_t)read_state_index(L, 1, "idle_field", t);
    t->move = (int16_t)read_state_index(L, 1, "move", t);
    t->kite = (int16_t)read_state_index(L, 1, "kite", t);
    t->rest = (int16_t)read_state_index(L, 1, "rest", t);
    lua_getfield(L, 1, "focus");
    if (lua_istable(L, -1))
    {
        static const char* const keys[5] = { "dt", "pdt", "mdt", "eva", "meva" };
        for (int i = 0; i < 5; ++i)
        {
            lua_getfield(L, -1, keys[i]);
            if (lua_isnumber(L, -1))
            {
                int idx = (int)lua_tointeger(L, -1) - 1;
                if (idx >= 0 && idx < t->nsets)
                    t->focus[i] = (int16_t)idx;
            }
            lua_pop(L, 1);
        }
    }
    lua_pop(L, 1);

    lua_getfield(L, 1, "rules");
    if (lua_istable(L, -1))
    {
        int n = (int)lua_objlen(L, -1);
        for (int i = 1; i <= n && t->nrules < PHASE_RULES; ++i)
        {
            lua_rawgeti(L, -1, i);
            if (lua_istable(L, -1))
            {
                PhaseRule r;
                memset(&r, 0, sizeof r);
                r.pre = r.mid = r.burst = -1;
                lua_getfield(L, -1, "category");
                r.category = (uint16_t)lua_tonumber(L, -1);
                lua_pop(L, 1);
                lua_getfield(L, -1, "action");
                r.action = (uint16_t)lua_tonumber(L, -1);
                lua_pop(L, 1);
                lua_getfield(L, -1, "pre");
                r.pre = (int16_t)(lua_tonumber(L, -1) - 1);
                lua_pop(L, 1);
                lua_getfield(L, -1, "mid");
                r.mid = (int16_t)(lua_tonumber(L, -1) - 1);
                lua_pop(L, 1);
                lua_getfield(L, -1, "burst");
                r.burst = (int16_t)(lua_tonumber(L, -1) - 1);
                lua_pop(L, 1);
                lua_getfield(L, -1, "song");
                r.song = lua_toboolean(L, -1) ? 1 : 0;
                lua_pop(L, 1);
                lua_getfield(L, -1, "buffs");
                if (lua_istable(L, -1))
                {
                    int nb = (int)lua_objlen(L, -1);
                    for (int b = 1; b <= nb && r.n_buffs < PHASE_RULE_BUFFS; ++b)
                    {
                        lua_rawgeti(L, -1, b);
                        if (lua_isnumber(L, -1))
                        {
                            int id = (int)lua_tointeger(L, -1);
                            if (id > 0 && id < PHASE_BUFF_IDS)
                                r.buffs[r.n_buffs++] = (uint16_t)id;
                        }
                        lua_pop(L, 1);
                    }
                }
                lua_pop(L, 1);
                if (r.pre >= t->nsets)
                    r.pre = -1;
                if (r.mid >= t->nsets)
                    r.mid = -1;
                if (r.burst >= t->nsets)
                    r.burst = -1;
                if (r.category && (r.pre >= 0 || r.mid >= 0 || r.burst >= 0))
                    t->rules[t->nrules++] = r;
            }
            lua_pop(L, 1);
        }
    }
    lua_pop(L, 1);

    /* The zone and job the launcher saw when it built the plan, so the status has them even
     * before the next packet arrives. */
    lua_getfield(L, 1, "zone");
    if (lua_isnumber(L, -1))
        atomic_store_explicit(&g_zone, (int)lua_tointeger(L, -1), memory_order_release);
    lua_pop(L, 1);
    lua_getfield(L, 1, "town");
    if (lua_isnumber(L, -1))
        atomic_store_explicit(&g_town, (int)lua_tointeger(L, -1), memory_order_release);
    lua_pop(L, 1);
    int session_changed = 0;
    /* A different character on the same host (a relog or a mule) starts with no locks: they
     * were taken for the character that was being played. */
    {
        uint32_t player = t->player;
        if (player != 0)
        {
            uint32_t was = atomic_exchange_explicit(&g_player, player, memory_order_acq_rel);
            session_changed = player != was;
        }
    }
    lua_getfield(L, 1, "job");
    if (lua_isnumber(L, -1))
    {
        int job = (int)lua_tointeger(L, -1);
        /* The launcher can see a new job before the 0x01B block reaches the addon (a relog,
         * a plan pushed straight after the change). Either signal releases the locks.  A plan
         * built before the party row exists carries job 0; it must not clobber the known job,
         * or the next real plan looks like a job change and releases every session lock. */
        if (job != 0)
        {
            int was = atomic_load_explicit(&g_job, memory_order_acquire);
            if (job != was)
                session_changed = 1;
            atomic_store_explicit(&g_job, job, memory_order_release);
        }
    }
    lua_pop(L, 1);

    /* Published, never freed: a reader on the network thread may still hold the old table, and
     * rules are rebuilt only when the library, the job or the toggle changes. */
    atomic_exchange_explicit(&g_table, t, memory_order_acq_rel);
    /* A plan push keeps a zone/job settle that is already due; the new state set is sent by
     * xi_phase_pending, after the client has loaded.  xi_phase_apply only applies at once when
     * there is no settle to wait for. */
    reset_plan(1);
    if (session_changed)
        release_session_locks(); /* after reset_plan: its pending state set must survive */
    xi_log("[gear] plan: %d sets, %d rules, job %d, zone %d", t->nsets, t->nrules,
           atomic_load_explicit(&g_job, memory_order_acquire),
           atomic_load_explicit(&g_zone, memory_order_acquire));
    int locked = atomic_load_explicit(&g_locked, memory_order_acquire);
    if (locked)
        atomic_store_explicit(&g_lock_set, state_index(t), memory_order_release);
    else
        atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    /* How many sets the table kept. The addon compares it with the list it built, so a plan
     * wider than PHASE_SETS is visible instead of silently short. */
    lua_pushinteger(L, t->nsets);
    return 1;
}

static int p_clear(lua_State* L)
{
    PhaseTable* t = (PhaseTable*)calloc(1, sizeof *t);
    if (!t)
        return luaL_error(L, "phase: out of memory");
    t->restore = t->engage = t->idle = t->town = t->field = t->move = t->kite = t->rest = -1;
    for (int i = 0; i < 5; ++i)
        t->focus[i] = -1;
    atomic_store_explicit(&g_locked, 0, memory_order_release);
    atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    atomic_store_explicit(&g_kiting, 0, memory_order_release);
    atomic_store_explicit(&g_resting, 0, memory_order_release);
    atomic_store_explicit(&g_focus, 0, memory_order_release);
    atomic_store_explicit(&g_locked_slots, 0, memory_order_release);
    for (int i = 0; i < 4; ++i)
        atomic_store_explicit(&g_locked_equip[i], 0, memory_order_release);
    atomic_store_explicit(&g_nitro, 0, memory_order_release);
    atomic_store_explicit(&g_burst, 0, memory_order_release);
    atomic_exchange_explicit(&g_table, t, memory_order_acq_rel);
    xi_phase_reset();
    lua_pushboolean(L, 1);
    return 1;
}

static const char* state_name(const PhaseTable* t)
{
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return "locked";
    if (atomic_load_explicit(&g_kiting, memory_order_acquire))
        return "kiting";
    if (atomic_load_explicit(&g_engaged, memory_order_acquire))
        return "engaged";
    if (atomic_load_explicit(&g_resting, memory_order_acquire))
        return "resting";
    if (atomic_load_explicit(&g_moving, memory_order_acquire))
        return "movement";
    int focus = atomic_load_explicit(&g_focus, memory_order_acquire);
    if (focus >= 1 && focus <= 5 && t && t->focus[focus - 1] >= 0)
    {
        static const char* const names[6] = { "idle", "idle.dt", "idle.pdt", "idle.mdt",
                                              "idle.eva", "idle.meva" };
        return names[focus];
    }
    int town = atomic_load_explicit(&g_town, memory_order_acquire);
    return town > 0 ? "idle.town" : town == 0 ? "idle.field" : "idle";
}

static int p_status(lua_State* L)
{
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    int locked = atomic_load_explicit(&g_locked, memory_order_acquire);
    int engaged = atomic_load_explicit(&g_engaged, memory_order_acquire);
    int moving = atomic_load_explicit(&g_moving, memory_order_acquire);
    int kiting = atomic_load_explicit(&g_kiting, memory_order_acquire);
    int resting = atomic_load_explicit(&g_resting, memory_order_acquire);
    int focus = atomic_load_explicit(&g_focus, memory_order_acquire);
    int town = atomic_load_explicit(&g_town, memory_order_acquire);
    int idx = locked ? atomic_load_explicit(&g_lock_set, memory_order_acquire) : state_index(t);
    const char* state = state_name(t);
    lua_createtable(L, 0, 20);
    lua_pushboolean(L, t && t->enabled);
    lua_setfield(L, -2, "enabled");
    lua_pushnumber(L, t ? t->player : 0);
    lua_setfield(L, -2, "player");
    lua_pushnumber(L, t ? t->nsets : 0);
    lua_setfield(L, -2, "sets");
    lua_pushnumber(L, t ? t->nrules : 0);
    lua_setfield(L, -2, "rules");
    lua_pushnumber(L, atomic_load(&g_actions));
    lua_setfield(L, -2, "actions");
    lua_pushnumber(L, atomic_load(&g_seen));
    lua_setfield(L, -2, "seen");
    lua_pushnumber(L, atomic_load(&g_held));
    lua_setfield(L, -2, "held");
    lua_pushnumber(L, atomic_load(&g_restored));
    lua_setfield(L, -2, "restored");
    lua_pushnumber(L, atomic_load(&g_stale));
    lua_setfield(L, -2, "restoredLate");
    lua_pushnumber(L, atomic_load(&g_swapped));
    lua_setfield(L, -2, "swapped");
    lua_pushboolean(L, engaged);
    lua_setfield(L, -2, "engaged");
    lua_pushboolean(L, moving);
    lua_setfield(L, -2, "moving");
    lua_pushboolean(L, kiting);
    lua_setfield(L, -2, "kiting");
    lua_pushboolean(L, resting);
    lua_setfield(L, -2, "resting");
    lua_pushnumber(L, focus);
    lua_setfield(L, -2, "focus");
    lua_pushboolean(L, locked);
    lua_setfield(L, -2, "locked");
    lua_pushboolean(L, atomic_load_explicit(&g_override.active, memory_order_acquire));
    lua_setfield(L, -2, "override");
    lua_pushnumber(L, g_override.changed);
    lua_setfield(L, -2, "overrideChanged");
    lua_pushnumber(L, g_override.restore_n);
    lua_setfield(L, -2, "overrideRestore");
    {
        unsigned slots = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
        lua_createtable(L, 16, 0);
        int n = 0;
        for (int i = 0; i < 16; ++i)
            if (slots & (1u << i))
            {
                lua_pushnumber(L, i);
                lua_rawseti(L, -2, ++n);
            }
        lua_setfield(L, -2, "lockedSlots");
    }
    lua_pushboolean(L, atomic_load_explicit(&g_nitro, memory_order_acquire) ? 1 : 0);
    lua_setfield(L, -2, "nitro");
    lua_pushboolean(L, atomic_load_explicit(&g_burst, memory_order_acquire) ? 1 : 0);
    lua_setfield(L, -2, "burst");
    lua_pushstring(L, state);
    lua_setfield(L, -2, "state");
    lua_pushnumber(L, town);
    lua_setfield(L, -2, "town");
    lua_pushnumber(L, atomic_load(&g_zone));
    lua_setfield(L, -2, "zone");
    lua_pushnumber(L, atomic_load(&g_job));
    lua_setfield(L, -2, "job");
    if (t && idx >= 0 && idx < t->nsets && t->names[idx][0])
        lua_pushstring(L, t->names[idx]);
    else
        lua_pushnil(L);
    lua_setfield(L, -2, "set");
    /* The action set that is on now (a weaponskill's set between the held action and its
     * result), and the windows that came before it.  The gear page reads these so a swap is
     * shown even when its poll landed after the set was restored. */
    {
        int action_set = atomic_load_explicit(&g_action_set, memory_order_acquire);
        if (t && action_set >= 0 && action_set < t->nsets && t->names[action_set][0])
            lua_pushstring(L, t->names[action_set]);
        else
            lua_pushnil(L);
        lua_setfield(L, -2, "actionSet");
        lua_pushnumber(L, action_set >= 0
                              ? (lua_Number)(now_ms() - atomic_load_explicit(&g_action_at,
                                                                             memory_order_acquire))
                              : 0);
        lua_setfield(L, -2, "actionMs");
        lua_pushnumber(L, action_set >= 0 ? atomic_load(&g_pending_action) : 0);
        lua_setfield(L, -2, "actionId");
        PhaseHistory h[PHASE_HISTORY];
        int n = history_snapshot(h);
        uint64_t now = now_ms();
        lua_createtable(L, n, 0);
        for (int i = 0; i < n; ++i)
        {
            int set = h[i].set;
            lua_createtable(L, 0, 5);
            if (t && set >= 0 && set < t->nsets && t->names[set][0])
                lua_pushstring(L, t->names[set]);
            else
                lua_pushnil(L);
            lua_setfield(L, -2, "set");
            lua_pushnumber(L, h[i].action);
            lua_setfield(L, -2, "action");
            lua_pushnumber(L, h[i].category);
            lua_setfield(L, -2, "category");
            lua_pushnumber(L, (lua_Number)((h[i].until ? h[i].until : now) - h[i].at));
            lua_setfield(L, -2, "ms");
            lua_pushboolean(L, !h[i].until && set >= 0 && set == action_set);
            lua_setfield(L, -2, "active");
            lua_rawseti(L, -2, i + 1);
        }
        lua_setfield(L, -2, "history");
    }
    lua_pushboolean(L, atomic_load(&g_pending));
    lua_setfield(L, -2, "pending");
    lua_pushnumber(L, atomic_load(&g_pending_action));
    lua_setfield(L, -2, "pendingAction");
    lua_pushboolean(L, atomic_load(&g_state_pending));
    lua_setfield(L, -2, "settling");
    return 1;
}

/* The plan's equips as {{inventory slot, equipment slot, bag}, ...}, for the addon to inject. */
static void push_equips(lua_State* L, int n, const PhaseEquip* e)
{
    lua_createtable(L, n, 0);
    for (int i = 0; i < n; ++i)
    {
        lua_createtable(L, 3, 0);
        lua_pushnumber(L, e[i].slot), lua_rawseti(L, -2, 1);
        lua_pushnumber(L, e[i].kind), lua_rawseti(L, -2, 2);
        lua_pushnumber(L, e[i].bag), lua_rawseti(L, -2, 3);
        lua_rawseti(L, -2, i + 1);
    }
}

static int p_moving(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_moving(lua_toboolean(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_engaged(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_engaged(lua_toboolean(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_apply(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_apply(&plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_pending(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_pending(&plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

/* Recover a held action that never produced a 0x028 (the server refused the recast, the target
 * vanished, or the packet was dropped).  The watch loop calls this every frame; it returns the
 * restore set once the pending action is older than its category's timeout. */
static int p_stale(lua_State* L)
{
    PhasePlan plan;
    int have = 0;
    xi_phase_restore_if_stale(&plan, &have);
    if (!have)
        return 0;
    push_equips(L, plan.restore_n, plan.restore);
    return 1;
}

static int p_zone(lua_State* L)
{
    xi_phase_zone((int)luaL_checkinteger(L, 1), lua_toboolean(L, 2));
    return 0;
}

static int p_job(lua_State* L)
{
    xi_phase_job((int)luaL_checkinteger(L, 1), (int)luaL_optinteger(L, 2, 0));
    return 0;
}

static int p_lock(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_lock(lua_toboolean(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_kiting(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_kiting(lua_toboolean(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_resting(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_resting(lua_toboolean(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_focus(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_focus((int)luaL_checkinteger(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

static int p_lock_slots(lua_State* L)
{
    PhasePlan plan;
    if (!xi_phase_lock_slots((unsigned)luaL_checkinteger(L, 1), &plan))
        return 0;
    push_equips(L, plan.pre_n, plan.pre);
    return 1;
}

/* `nitro(on)`: the control addon's Nightingale + Troubadour check.  It does not build a plan;
 * it only arms (or disarms) the Bard's song weapon-swap exception. */
static int p_nitro(lua_State* L)
{
    xi_phase_nitro(lua_toboolean(L, 1));
    lua_pushboolean(L, atomic_load_explicit(&g_nitro, memory_order_acquire) ? 1 : 0);
    return 1;
}

/* `burst(on)`: a magic-burst window is open on the addon's current target.  It does not build a
 * plan; the next action's rule wears its `burst` set instead of its ordinary midcast set. */
static int p_burst(lua_State* L)
{
    xi_phase_burst(lua_toboolean(L, 1));
    lua_pushboolean(L, atomic_load_explicit(&g_burst, memory_order_acquire) ? 1 : 0);
    return 1;
}

/* The control addon's live buff list: a table of the client's status ids.  It is pushed once
 * per frame or so and replaces the previous snapshot. */
static int p_buffs(lua_State* L)
{
    luaL_checktype(L, 1, LUA_TTABLE);
    uint16_t ids[64];
    int n = (int)lua_objlen(L, 1);
    if (n > (int)(sizeof ids / sizeof ids[0]))
        n = (int)(sizeof ids / sizeof ids[0]);
    for (int i = 0; i < n; ++i)
    {
        lua_rawgeti(L, 1, i + 1);
        ids[i] = (uint16_t)lua_tointeger(L, -1);
        lua_pop(L, 1);
    }
    xi_phase_buffs(ids, n);
    lua_pushnumber(L, n);
    return 1;
}

/* A manual equip from the addon (the launcher's Wear set, a single-slot change): the engine no
 * longer knows what the slot holds, so the next state set writes it back. */
static int p_forget(lua_State* L)
{
    (void)L;
    xi_phase_forget();
    return 0;
}

static int p_forget_slot(lua_State* L)
{
    xi_phase_forget_slot((int)luaL_checkinteger(L, 1));
    return 0;
}

/* `remember(kind, bag, slot)`: the launcher's manual Wear set tells the engine the exact copy
 * it put on, so a later locked-action override can put that piece back. */
static int p_remember(lua_State* L)
{
    xi_phase_remember((int)luaL_checkinteger(L, 1),
                      (int)luaL_checkinteger(L, 2),
                      (int)luaL_checkinteger(L, 3));
    return 0;
}

/* `precache(action, {{slot, kind, bag}, ...})`: one-shot gear for the next action.  The addon
 * uses it to put a Call Beast jug in ammo behind the held Bestial Loyalty packet; the engine
 * clears it with that action, so it cannot leak into a later spell or weaponskill. */
static int p_precache(lua_State* L)
{
    int action = (int)luaL_checkinteger(L, 1);
    luaL_checktype(L, 2, LUA_TTABLE);
    int n = (int)lua_objlen(L, 2);
    PhaseEquip equips[PHASE_EQUIP_MAX];
    int k = 0;
    for (int i = 1; i <= n && k < PHASE_EQUIP_MAX; ++i)
    {
        lua_rawgeti(L, 2, i);
        if (lua_istable(L, -1))
            read_equip(L, lua_gettop(L), &equips[k++]);
        lua_pop(L, 1);
    }
    xi_phase_precache((uint16_t)action, equips, k);
    lua_pushboolean(L, 1);
    return 1;
}

void xi_phase_open(lua_State* L)
{
    static const luaL_Reg fns[] = {
        { "set", p_set }, { "clear", p_clear }, { "status", p_status },
        { "moving", p_moving }, { "engaged", p_engaged }, { "apply", p_apply },
        { "pending", p_pending }, { "stale", p_stale }, { "zone", p_zone }, { "job", p_job },
        { "lock", p_lock }, { "kiting", p_kiting }, { "resting", p_resting },
        { "focus", p_focus }, { "lock_slots", p_lock_slots }, { "precache", p_precache },
        { "nitro", p_nitro }, { "burst", p_burst }, { "buffs", p_buffs },
        { "forget", p_forget }, { "forget_slot", p_forget_slot }, { "remember", p_remember },
        { NULL, NULL },
    };
    lua_newtable(L);
    luaL_register(L, NULL, fns);
}
