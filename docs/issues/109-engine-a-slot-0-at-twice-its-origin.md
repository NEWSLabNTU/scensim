# 109: engine A put slot 0's car at twice its env origin

**Status:** fixed (scensim_batch's PhysxVehicleBackend, with 094 P4's engine A row).
**Severity:** high wherever an engine A run reads slot 0's position with more than one env; none
for one env. **Found:** 2026-11-23, scensim 139, building 094 P4's engine A row.

## What happened

aib's `Vehicle` writes a car's pose as its prim's own transform, so it is relative to the prim's
parent, the env prim `/World/envs/env_<i>`. `PhysxVehicleBackend` handed it world poses (the
env's origin plus the slot's local pose), which is right only while the env prim has no
transform of its own. Isaac Lab 3.0 gives env_0's prim a translate equal to its origin and
leaves env_1..N's prims without transform ops (their origins are kept elsewhere). So env_0's car
spawned, and was teleported at every reset, at twice its origin. Its reported local pose (PhysX's
world pose less the origin) was off by the origin; the others were right.

## How it showed

In 094 P4's lead-brake task on engine A, 4 envs at 10 m spacing: env_0's origin (5, -5), its car
at (16.5, -10) by PhysX where (11.8, -5) was due. Its local y read -5, past the task's off-road
bound (3 m): the episode ended at its first step, and the slot reset every step after, a new
record each time, its pose frozen at the reset's. The repository's engine A smoke
(`smoke_env.py`, cs2, 4 envs) passed throughout: Isaac Lab's ground collider is an infinite
plane, so the offset car still drove, and the smoke checked speeds, not positions.

## The fix

The backend reads each env prim's world transform from the stage once and writes every spawn
and teleport in that prim's frame (`_local`); a rotated or scaled env prim is refused. Because
something could still move an env prim after that read (243's review), the first sample after
every reset checks each reset car's PhysX world pose against where the reset put it (1 cm across
its heading, a substep's travel along it) and raises otherwise. The smoke now checks every
slot's pose against PhysX's, slot 0 included (N = 4), and a reset mid-run.

## Results it touched (audit, 133)

Every landed engine A result, by whether it read slot 0's position with N > 1:

| result | N | episodes | positions read | stands |
|---|---|---|---|---|
| 092 K2.2's engine A smoke (`smoke_env.py`) | 4 | 1 | no (speeds, PhysX's own read-back) | yes |
| 092 K2.4's agreement rows on engine A (follow_to_goal, k24_npc_stops_for_ego; `agreement_run.py`) | 1 | 1 | yes | yes: one env, its origin (0, 0), no offset |
| 094 P2, P3 | engine B only | | | not affected |
| 094 P4's engine A row | | | | not run before the fix |

The world servers place aib's cars themselves, not through this backend: not affected.
