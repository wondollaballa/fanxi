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

enum { PHASE_SETS = 96, PHASE_RULES = 1024, PHASE_NAME = 48 };
/* 0x01A action categories: what the client is doing. */
enum
{
    PHASE_ACTION_ATTACK = 2,  /* /attack: engaged */
    PHASE_ACTION_MAGIC = 3,
    PHASE_ACTION_SKILL = 7,   /* weaponskill */
    PHASE_ACTION_ABILITY = 9, /* job ability */
};
/* 0x028 result categories: something finished.  1 is a swing, 8 a cast starting. */
enum { PHASE_RESULT_SKILL = 3, PHASE_RESULT_MAGIC = 4, PHASE_RESULT_ABILITY = 6 };
/* No result in this long (an interrupted cast, a refused action): put the return set back. */
enum { PHASE_STALE_MS = 6000 };
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
/* Engagement comes from the client's own /attack and from the server's animation for the
 * player.  /attack off is not read here: the server answers a real disengage with animation 0,
 * and an ignored range disengage must not move the gear. Movement is sampled by the addon. */
static _Atomic int g_engaged;
static _Atomic int g_moving;
/* -1 until a zone has been seen, 1 in a town, 0 in the field. */
static _Atomic int g_town = -1;
static _Atomic int g_zone, g_job, g_sub_job;
static _Atomic uint32_t g_player;
/* The user's override. While set, every automatic swap is suppressed and the set that was
 * current at the moment of locking is what the status reports. */
static _Atomic int g_locked;
static _Atomic int g_lock_set = -1;
/* Forced states and per-slot weapon locks. Kiting wins over everything but the full lock;
 * resting is manual too (this server has no rest packet to follow). A weapon lock removes that
 * slot from every set the engine sends, including precast and midcast. */
static _Atomic int g_kiting, g_resting;
static _Atomic int g_focus; /* 0 auto, 1 dt, 2 pdt, 3 mdt, 4 eva, 5 meva */
static _Atomic unsigned g_locked_slots; /* bit i = equipment slot i is pinned */
/* A zone, job or stance change wants the state set re-worn once the client has settled. */
static _Atomic int g_state_pending;
static _Atomic uint64_t g_state_due;
static _Atomic int g_pending;
static _Atomic uint64_t g_pending_at;
static _Atomic unsigned g_pending_action;

static uint64_t now_ms(void) { return rt_monotonic_ns() / 1000000ull; }

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

static const PhaseRule* find_rule(const PhaseTable* t, uint16_t category, uint16_t action)
{
    /* The exact rule wins; a category rule with action 0 is the fallback (precast.WS,
     * precast.JA, precast.FC) for an action the library has no named set for. */
    for (int i = 0; i < t->nrules; ++i)
        if (t->rules[i].category == category && t->rules[i].action == action)
            return &t->rules[i];
    for (int i = 0; i < t->nrules; ++i)
        if (t->rules[i].category == category && t->rules[i].action == 0)
            return &t->rules[i];
    return NULL;
}

static void copy_set(const PhaseSet* s, PhaseEquip* out, int* n)
{
    unsigned locked = atomic_load_explicit(&g_locked_slots, memory_order_acquire);
    int k = 0;
    for (int i = 0; i < s->n; ++i)
        if (!(locked & (1u << s->e[i].kind)))
            out[k++] = s->e[i];
    *n = k;
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

static int state_set(const PhaseTable* t, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return 0;
    int idx = state_index(t);
    if (idx < 0 || idx >= t->nsets)
        return 0;
    copy_set(&t->sets[idx], plan->pre, &plan->pre_n);
    return plan->pre_n > 0;
}

static int fill_restore(const PhaseTable* t, PhasePlan* plan)
{
    plan->restore_n = 0;
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return 0;
    int idx = state_index(t);
    if (idx < 0 || idx >= t->nsets)
        idx = t->restore;
    if (idx < 0 || idx >= t->nsets)
        return 0;
    copy_set(&t->sets[idx], plan->restore, &plan->restore_n);
    return plan->restore_n > 0;
}

/* Ask for the state set to be re-worn once the client has settled (a zone, a job change or a
 * stance flip). The addon's watch loop calls xi_phase_pending every frame. */
static void want_state(uint64_t due)
{
    atomic_store_explicit(&g_state_due, due, memory_order_release);
    atomic_store_explicit(&g_state_pending, 1, memory_order_release);
}

int xi_phase_action(uint16_t category, uint16_t action, PhasePlan* plan)
{
    plan->pre_n = plan->mid_n = plan->restore_n = 0;
    plan->hold = 0;
    PhaseTable* t = atomic_load_explicit(&g_table, memory_order_acquire);
    if (!t || !t->enabled)
        return 0;
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
         * it just does not move any gear. */
        if (atomic_load_explicit(&g_locked, memory_order_acquire))
            return 0;
        int idx = state_index(t);
        if (idx < 0 || idx >= t->nsets)
            return 0;
        copy_set(&t->sets[idx], plan->pre, &plan->pre_n);
        if (was != 1)
            atomic_fetch_add(&g_swapped, 1);
        return plan->pre_n > 0;
    }
    /* Locked is the user's override: the action goes out exactly as the client made it. */
    if (atomic_load_explicit(&g_locked, memory_order_acquire))
        return 0;
    const PhaseRule* r = find_rule(t, category, action);
    if (!r)
        return 0;
    if (r->pre >= 0 && r->pre < t->nsets)
        copy_set(&t->sets[r->pre], plan->pre, &plan->pre_n);
    if (r->mid >= 0 && r->mid < t->nsets)
        copy_set(&t->sets[r->mid], plan->mid, &plan->mid_n);
    if (!plan->pre_n && !plan->mid_n)
        return 0;
    plan->hold = 1;
    atomic_store_explicit(&g_pending, 1, memory_order_release);
    atomic_store_explicit(&g_pending_at, now_ms(), memory_order_release);
    atomic_store_explicit(&g_pending_action, action, memory_order_release);
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
    if (now - atomic_load_explicit(&g_pending_at, memory_order_acquire) < PHASE_STALE_MS)
        return;
    atomic_store_explicit(&g_pending, 0, memory_order_release);
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
    atomic_store_explicit(&g_locked, 0, memory_order_release);
    atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    atomic_store_explicit(&g_locked_slots, 0, memory_order_release);
    atomic_store_explicit(&g_kiting, 0, memory_order_release);
    atomic_store_explicit(&g_resting, 0, memory_order_release);
    atomic_store_explicit(&g_focus, 0, memory_order_release);
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
    return state_set(t, plan);
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
    return state_set(t, plan);
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
    if (!t || !t->enabled)
        return 0;
    atomic_fetch_add(&g_swapped, 1);
    return state_set(t, plan);
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
    if (!t || !t->enabled)
        return 0;
    /* Unlocking a slot should put the current state's piece back; locking one still re-sends
     * the rest of the set, which is already worn. */
    return state_set(t, plan);
}

void xi_phase_reset(void)
{
    atomic_store_explicit(&g_pending, 0, memory_order_release);
    atomic_store_explicit(&g_pending_action, 0, memory_order_release);
    atomic_store_explicit(&g_state_pending, 0, memory_order_release);
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
                r.pre = r.mid = -1;
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
                if (r.pre >= t->nsets)
                    r.pre = -1;
                if (r.mid >= t->nsets)
                    r.mid = -1;
                if (r.category && (r.pre >= 0 || r.mid >= 0))
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
         * a plan pushed straight after the change). Either signal releases the locks. */
        int was = atomic_load_explicit(&g_job, memory_order_acquire);
        if (job != 0 && job != was)
            session_changed = 1;
        atomic_store_explicit(&g_job, job, memory_order_release);
    }
    lua_pop(L, 1);

    /* Published, never freed: a reader on the network thread may still hold the old table, and
     * rules are rebuilt only when the library, the job or the toggle changes. */
    atomic_exchange_explicit(&g_table, t, memory_order_acq_rel);
    xi_phase_reset();
    if (session_changed)
        release_session_locks(); /* after xi_phase_reset: its pending state set must survive */
    int locked = atomic_load_explicit(&g_locked, memory_order_acquire);
    if (locked)
        atomic_store_explicit(&g_lock_set, state_index(t), memory_order_release);
    else
        atomic_store_explicit(&g_lock_set, -1, memory_order_release);
    lua_pushboolean(L, 1);
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

void xi_phase_open(lua_State* L)
{
    static const luaL_Reg fns[] = {
        { "set", p_set }, { "clear", p_clear }, { "status", p_status },
        { "moving", p_moving }, { "engaged", p_engaged }, { "apply", p_apply },
        { "pending", p_pending }, { "zone", p_zone }, { "job", p_job },
        { "lock", p_lock }, { "kiting", p_kiting }, { "resting", p_resting },
        { "focus", p_focus }, { "lock_slots", p_lock_slots }, { NULL, NULL },
    };
    lua_newtable(L);
    luaL_register(L, NULL, fns);
}
