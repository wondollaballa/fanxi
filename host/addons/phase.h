/* The phase engine's interface to the packet hooks (phase.c).
 *
 * GearSwap's order for an action is: wear the precast set, send the action, wear the midcast
 * set, and put the TP/idle set back when the result comes. host64 does the same in the buffers
 * it already rewrites; phase.c owns the rules, hooks.c owns where the packets go.
 *
 * The idle state machine has four states and a lock. /attack selects engaged, the server's
 * 0x00D animation selects engaged or idle, the addon's position sampling selects movement, and
 * the zone-in packet selects town or field for idle. /attack off is not a state signal: the
 * client sends it on its own when the target leaves auto-attack reach. The lock is a user
 * override: while it is on, nothing below moves gear until it is switched off again.
 */
#ifndef FANXI_PHASE_H
#define FANXI_PHASE_H

#include <stddef.h>
#include <stdint.h>

enum { PHASE_EQUIP_MAX = 16 };

/* One 0x050: inventory slot, equipment slot, bag - the order the packet carries them. */
typedef struct PhaseEquip
{
    uint8_t slot, kind, bag;
} PhaseEquip;

typedef struct PhasePlan
{
    int pre_n, mid_n, restore_n;
    int hold; /* 1: the action waits a buffer for the precast set; 0: it goes out with them */
    PhaseEquip pre[PHASE_EQUIP_MAX];
    PhaseEquip mid[PHASE_EQUIP_MAX];
    PhaseEquip restore[PHASE_EQUIP_MAX];
} PhasePlan;

/* An outgoing 0x01A: 1 when the engine has a plan for this action, and the plan is filled.
 * Holding the packet is the caller's job; this only decides and counts. 0 while locked. */
int xi_phase_action(uint16_t category, uint16_t action, PhasePlan* plan);
/* An incoming 0x028: 1 when it is the result of the action that is pending, and the restore
 * set is filled. Clears the pending action. */
int xi_phase_result(const uint8_t* packet, size_t size, PhasePlan* plan);
/* Every incoming packet: puts the restore set back if the action never resolved. */
void xi_phase_restore_if_stale(PhasePlan* plan, int* have);
/* An incoming 0x00D: the server's animation for the player is what draws or sheathes the
 * weapon. 1 when it was the player's own update and the engaged flag changed. */
int xi_phase_player_animation(const uint8_t* packet, size_t size);
/* The player started or stopped moving (the addon samples the client's position). Returns 1 when
 * the idle state's set changed, with the equips to wear in plan->pre; nothing while engaged. */
int xi_phase_moving(int moving, PhasePlan* plan);
/* The client's own /attack. Returns 1 when the state set changed.  The companion /attack off
 * is deliberately not wired to the state: the server's animation decides a real disengage. */
int xi_phase_engaged(int on, PhasePlan* plan);
/* An incoming 0x00A (zone-in): a zone is a town or the field, and combat does not survive it.
 * The idle set follows on the next xi_phase_pending, once the client has loaded the zone. */
void xi_phase_zone(int zone, int town);
/* An incoming 0x01B (job change): the engine's idle set follows the new job once the launcher
 * has pushed the new library; until then the next pending apply re-wears the current state.
 * Any change to the main or support job releases the lock, the weapon pins, kiting, resting
 * and the idle focus. */
void xi_phase_job(int job, int sub);
/* The set for the state the player is in right now (engaged, moving or idle), always. */
int xi_phase_apply(PhasePlan* plan);
/* The zone or job changed and the client has settled: 1 with the state set, once. The addon
 * calls this every frame and injects the result. */
int xi_phase_pending(PhasePlan* plan);
/* Lock (1) holds the set that is worn now and stops every automatic swap; unlock (0) puts the
 * current state's set back and returns it. plan->pre is filled on unlock. */
int xi_phase_lock(int on, PhasePlan* plan);
/* Forced kiting and manual resting: each stays on until switched off. */
int xi_phase_kiting(int on, PhasePlan* plan);
int xi_phase_resting(int on, PhasePlan* plan);
/* Idle focus: 0 auto, 1 dt, 2 pdt, 3 mdt, 4 eva, 5 meva. */
int xi_phase_focus(int mode, PhasePlan* plan);
/* Pin equipment slots (bit i = slot i) out of every set the engine sends. Unlocking returns the
 * current state's set so the slot comes back. */
int xi_phase_lock_slots(unsigned mask, PhasePlan* plan);
/* Forget a pending action (the launcher disabled the engine or replaced the rules). */
void xi_phase_reset(void);

#endif
