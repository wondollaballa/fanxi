# The freeze: a CXiDollActor list walk that never ends

Status: theory, 2026-10-31.  Builds on the eight captures under `data/freeze-*` and the
`sample`/`lldb` dumps in them.  This note separates what has been measured from what is still a
hypothesis, and ends with the tests that would settle it.

## Summary

The client does not crash and does not lose the network.  Its main thread stops returning
frames while spinning in one place: the per-frame actor update, which walks the client's list
of `CXiDollActor` objects.  The walk is a `do { ... } while (eax)` over a singly linked list at
`[actor + 0x54]`; the game never reaches the null that ends it, so no frame completes and no
packet is sent again.  The server only sees that movement and actions stop and times the
character out after its usual 180 s.

## What is measured, not inferred

1. **The objects are the client's actor ("doll") list.**
   `f_10085270` walks `[ecx+0x54]` and calls `f_1002c8f0(node, 0x1032f910)` on each node, which
   is an MFC `CObject::IsKindOf`-shaped class check.  The descriptor at `0x1032f910` in
   `FFXiMain.dll` is an MFC `CRuntimeClass` whose name field points at the string
   **`CXiDollActor`** (read out of the retail DLL's `.data`; object size 0x440).  So the list is
   the zone's actors and the filter keeps only dolls.

2. **The walk is the frame's actor update, and it has no snapshot.**
   `f_10158ca0` (the caller) runs:

   ```c
   do {
       edx = [esi+0x64];
       ecx = [esi+0x60];
       eax = f_10083d00(eax, ecx, edx);   /* via 0x10158d46 */
   } while (eax);
   ```

   and `f_10083d00` contains the second walk at `0x10083daf..0x10083ea3`:

   ```c
   do {
       ebp = [esp+0x80];                  /* the "stop here" marker, re-read every pass */
       if (esi != ebp) f_10083430(esi, edi, [esp+0x84], ebx, 1);
       esi = f_10085270(esi);             /* next CXiDollActor at +0x54, or 0 */
   } while (esi);
   ```

3. **Every freeze for two days has this same stack.**  `f_10158ca0 -> f_10083d00 ->
   f_10085270 / f_10083430 -> f_10193850`, with ~2400 of 2400 main-thread samples inside it.
   The guest registers at the freeze match across captures in every constant
   (`eax=0`, `edx=0x352`, `ebx=0xffffffff`, `esp` within 4 bytes); only heap pointers move.
   It is one deterministic wedge, not a family of similar-looking ones.

4. **It is not the server, the network, memory or a crash.**  The TCP session stays up, the
   server keeps ticking, RSS is flat, there is no crash report, and the server's equipment and
   command traffic shows the client sent its last 12-equip set normally.

5. **What precedes it.**  Every capture ends on a burst of model-changing equipment: 12 pieces
   here, 16 there, 7 in the 10-29 00:33 capture - typically the weaponskill set and the idle
   restore after a kill.  Those bursts are the only thing the captures have in common; the
   weaponskill itself is not (Imperator in one, Seraph Blade in the next).

## The mechanism (settled by disassembly)

`f_10083d00(reference, maskA, maskB)` is a **nearest-actor search**.  It scans every actor through
the doll walk, rejects the ones the mask test refuses, keeps the one closest to `reference`, and
returns that actor - 0 when none qualifies.  The generated C looks like it returns a float
distance because the compiler reused one stack slot: while `ebx` is pushed the distance is
written at `[esp+0x14]` and the actor at `[esp+0x18]`; after the `pop ebx` those are the same
address, and the epilogue returns it.  The last store to that slot is `mov [esp+0x18], esi`
(0x10083e90) - the actor pointer.  So the return value is a `CXiDollActor*`.

`f_10158ca0` then walks a chain of those answers:

```
edi = start;                       /* the selector's own actor, [ecx+0xc] when [ecx+0x20] */
eax = f_10083d00(edi, maskA, maskB);
while (eax) { edi = eax; eax = f_10083d00(eax, maskA, maskB); }
return edi;
```

i.e. it repeatedly asks "which actor matching these masks is nearest to the last answer" and
follows that answer.  **There is no visited set and no iteration cap.**  Two ordinary
configurations make it never stop:

- **self**: `nearest(X) == X` - the search accepts the reference itself;
- **pair**: `nearest(A) == B` and `nearest(B) == A` - mutual nearest neighbours.

The masks are what normally prevent both: the filter rejects the reference by identity and
rejects actors of the wrong type/team/state (the `[actor+0x1d0]` mask test at 0x10083479, plus
`0x101cc1d0`/`0x101cc220` state tests).  A kill or an equipment change that flips one mask bit
on one actor turns a terminating chain into an infinite one.  That is the freeze: not a
corrupted list, not a stuck model - a two-node cycle in a nearest-neighbour walk.

This also explains the measurement that looked wrong before: the inner doll walk is finite every
time (it is a full scan), and the samples spread across its call sites, because the *outer*
chain is what never ends.

## The open question

Which two actors oscillate, and which mask bit lets them through.  Everything so far is
consistent with the pair being the player's doll and the mob being killed (both pass the search
at the moment the mob's state changes), but it could just as well be two trusts or a trust and
the player.  The next capture names them: phase A of the probe records the argument of every
`f_10083d00` call, so it prints the cycle exactly (`A, B, A, B, ...` or `X, X, X, ...`), and the
actor pointers can be resolved to ServerIds through the client's actor table.

## The test that settles it

Do not guess at the relink.  Capture the walk's own sequence the next time it hangs:

1. Attach to the frozen host (no restart, no relogin - the process is left exactly as it is).
2. Break at the walk (`f_10085270` entry, which every hop passes through) and record the node
   pointer of the first N hops, then stop.
3. Walk `[node+0x54]` from each and print the chain, with each node's class name and, where it
   can be read, its server id.

The probe records both sequences in one attach (phase A: the actors handed to `f_10083d00`;
phase B: the nodes handed to `f_10085270`).  A short cycle across phase A is candidate 1; the
same pointer back-to-back in phase A is candidate 2.

`tools/freeze_capture.py` does step 1 and 2 and saves everything in `data/freeze-<stamp>/`
(notes, sample, guest state, node sequence, client log tail).  It never kills or restarts the
client.  Run it the moment a client freezes:

```sh
python3 tools/freeze_capture.py            # newest host64
python3 tools/freeze_capture.py --pid 1234
```

Two runs are wanted:

- **Gear on** (normal play): predict a repeated node after a large swap.
- **Gear off** (`phase {enabled=false}` from the launcher's Gear page, or the master switch off):
  if it freezes with no 0x050 bursts at all, the addon is innocent and the trigger is in the
  engine's own actor handling; if it never freezes, the next test is a hand `/equip` burst of
  twelve slots to reproduce it without the addon.

## What the fix is likely to be

If the sequence repeats, the fix belongs where the client relinks the doll list on an equipment
change - either the equipment handler must not unlink/relink a doll that the frame is walking,
or the walk must take a snapshot (hold the next pointer before processing the node).  The
second is a runtime-side change and is cheap: `f_10085270` already returns the next node before
the body runs, so a guard that remembers the previous node and refuses to revisit it would turn
the hang into one skipped actor instead of a dead client - but that is a workaround, and the
real relink bug should still be fixed.

If instead `eax` repeats across iterations without a repeated node, the fix is in what
`f_10083d00` returns, and the next capture should record that sequence (the tool prints it when
the walk stops early).

## Capture 2026-10-31 18:25 (reproduced under the fight loop)

First freeze produced by the automated fight loop (`tools/freeze_watch.py` -> `tools/freeze_capture.py`).
Same trigger as always: the last client log line is the post-battle restore
(`[gear] wear idle.dt: 14 pieces`, 18:25:10), then silence; the server sees the last equip burst at
23:25:10 UTC and only world ticks afterwards.

The stack is the same selector chain, but through the **other branch**:

```
f_10158ca0 + f_10083b40 (1101/2192 samples) -> f_10083430 -> f_10193850
```

`f_10158ca0` picks `f_10083d00` or `f_10083b40` from the `bl` argument (the dispatcher at 0x1015890d
passes 1, 0x1015891d passes 0).  Both are the same nearest-actor search, so the loop is the same;
the probe simply watched only `f_10083d00` and recorded nothing.  Both are now watched.

Capture caveat: the lldb probe blocked because the client was wedged in this branch while the probe's
breakpoints only covered the other one, and the 90 s timeout left the process stopped (the "freeze"
of 18:45).  The tools now: gate the probe on the sample actually showing the actor chain, interrupt
`Continue` after 10 s, and send SIGCONT if lldb times out.

## The two actors, 2026-10-31 19:54 (guard build)

The cycle guard fired twice in one session, both times with the same pair:

```
[chain] cycle 0ebf97c0 -> 0ec37df0 -> 0ebf97c0 (f_10083b40)
```

Read out of the live client while it was still running:

| node | actor | ServerId | name | mask | status |
|------|-------|----------|------|------|--------|
| 0x0ebf97c0 | 0x0ebfd370 | 16795396 | **Luzaf** | 0x100e | 0x00000001 |
| 0x0ec37df0 | 0x0ec38840 | 16795392 | **Cornelia** | 0x100e | 0x00000001 |

Both are the player's trusts.  They stand next to each other behind the player, so each is the
other's nearest actor; both carry mask 0x100e, which passes the selector's filter, so the
nearest-neighbour chain bounces Cornelia -> Luzaf -> Cornelia forever.  That is the freeze:
not a model, not a corrupted list, not the equipment itself - a mutual-nearest cycle between two
same-class actors the selector admits.

The guard did its job: it logged the cycle and ended the chain, and the client kept fighting
(kill #21 immediately after, session still running 40+ minutes later).  The mask side is the
deeper question (why a trust-vs-trust pairing is admitted at all); the guard is the safe fix
because retail's chain has no visited set and any two admitted actors can form the pair.

## The fix as built

`f_10158ca0`'s two chain loops carry a guard (generated/all/funcs_024.c for the test build):

```c
if (eax && eax == chain_hist2) {          /* A -> B -> A */
    rt_log("[chain] cycle %08x -> %08x -> %08x\n", chain_hist2, chain_hist1, eax);
    eax = 0;                              /* end the chain where retail would spin */
    goto L_10158d52;
}
chain_hist2 = chain_hist1; chain_hist1 = eax;
```

To make it permanent it has to move into `recomp/recomp.py` (or a `meta/builds.json` patch entry):
the generated file is rewritten by every normal build.  The test build used
`FANXI_SKIP_RECOMP=1` (added to tools/build.py) so the hand patch survived.
