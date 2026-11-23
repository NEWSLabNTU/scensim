# 113: engine A's cars of different envs collide with each other

**Status:** fixed: engine A lays its slots out apart by their route boxes (checked at 1024
envs, below); P4's engine A seeds rerun after it. Engine A's results at N > 1 with cars that met
are void. **Severity:** high for any engine A run with more than
one env where cars come within a car's size of each other (094 P4's lead-brake task: every run);
none for one env, or for envs that never meet. **Found:** 2026-11-23, scensim 139, on 094 P4's
engine A seed 1; the cause read by 243.

## What happened

094 P4's engine A seed 1 (lead-brake, ecu row, 1024 envs, 10 m spacing) stopped at iteration
187: the landing check (issue 109's) raised for one car, 3.9 cm along and 5.2 cm across its
reset heading at the first sample after its reset. That sample comes one substep (1/120 s) after
the reset, so the miss was a planar velocity of about 7.8 m/s at about 53 degrees to the
heading (243), not a car settling, as first written here (139; wrong). The 1.2 and 1.4 cm across
seen in the engine A smokes before (64 and 16 envs) are 1.4 to 1.7 m/s sideways, the same thing
smaller.

## Cause

Isaac Lab puts each env's prims in their own collision group (`/World/collisions`, inverted
filtering: groups collide only with the groups they name) only when the scene is built from its
config's assets: `InteractiveScene` runs `filter_collisions` `if cfg.filter_collisions and physx
and scene_from_cfg` (interactive_scene.py:172), and `scene_from_cfg` is true only when the scene
config holds an asset field. Engine A's scene holds none: `ScensimEnv._setup_scene` builds aib's
cars itself (`PhysxVehicleBackend`). So no group was ever made, and every env's car collides with
every other env's.

The lead-brake task's envs stand 10 m apart in both axes (stock's grid), and each ego drives its
env's +x for up to 300 m: it passes through the start spots of about 30 envs of its grid row, and
other envs' cars are reset onto spots it is crossing. A car reset into another, or driving into
one, is pushed apart by PhysX in a substep, in any direction.

Ruled out on the way: the USD velocity writes of a reset being no-ops (243's first read).
`/physics/updateVelocitiesToUsd` is true in the run, so USD holds PhysX's velocities and the
reset's zero write is a change; and 118's C5c logs showed aib's teleport taking a car at 15.6
m/s to rest every time (22 of 22).

## How it was confirmed

- **The stage** (the repro run's landing log header, the stage after the backend built its
  cars): `{"groups": {"exists": false, "invert": false}}`, no `/World/collisions`, no
  `invertCollisionGroupFilter`.
- **Engine B's stage**, the same check (lead-brake, ecu row, 4 envs, read off the built stage):
  `/World/collisions` exists and each env's ego colliders (5) resolve to exactly its own group
  (env_0: group0, env_3: group3). Its ego is a scene asset; Isaac Lab filters it.
- **The repro** (`run_p4.sh repro`, engine A, 64 envs, the landing log kept and a miss not
  raised): of 192 resets in the first 17 iterations, 5 missed (velocity check, below), and all 5
  had another env's car within 5 m at the sample (0.89, 1.37, 1.70, 2.48, 4.49 m); a car reset at
  10.5 m/s left its first substep at 1.57 m/s along, 1.57 across, its yaw rate -0.73 rad/s, the
  nearest car 0.89 m away. 20 pairs of cars of different envs came within 2 m of each other
  (centres; closest 0.87 m), so cars met mid-episode, not only at resets.
- **No carried velocity**: the missing cars' velocities before their resets do not match the
  misses (one was at rest before, 0.0002 m/s, and left at 1.57 m/s across).

Seed 1 logged no trajectories, so its own contacts cannot be counted after the fact; the repro
at 64 envs is the count, and the 1024-env repro before any restart (below) gives the rate there.

## Results it touched (audit: 243's survey of scensim_batch, 133)

Only engine A builds bodies outside the scene config. By whether its cars could meet:

| result | engine | N | spacing | cars meet | stands |
|---|---|---|---|---|---|
| 094 P4's engine A seeds 1-5 (`run_p4.sh seed ... ecu A`, scensim 5c28e146) | A | 1024 | 10 m, 300 m route | yes | **void, issue 113** (seed 1 to iteration 187, 2-5 to about 57; logs kept in the run directory) |
| 092 K2.2's smoke (`smoke_env.py`) | A | 4 | 200 m | no: at most ~20 m/s for 120 steps | yes |
| 092 K2.4's agreement rows (`agreement_run.py`) | A | 1 | | no | yes |
| `smoke_physx_vehicle.py` (batch-executor.md section 5's A timings) | A | up to 64 | 60 m, own World | no: 4 s from rest | yes |
| issues 109 and 110's findings (4 envs at 10 m, 20 steps) | A | 4 | 10 m | could | yes: metres (109) and tens of metres (110), far above a contact's centimetres; their tables' last centimetres are not claimed |
| 094 P2, P3, P4's joints and ECU-B rows; K2.2c's `check_resident` | B | | | filtered | yes |

## Why not Isaac Lab's collision groups

The obvious fix, Isaac Lab's `filter_collisions` once the cars exist, would break the cars. It
sets `physxScene:invertCollisionGroupFilter`, which is scene-wide: under it a `filteredGroups`
relation means "collides with" instead of "does not". aib's vehicles already rely on two groups
under the normal meaning (`ensure_vehicle_scene`, aib vehicle.py:115-130): every chassis in
`/World/vehicleCollisionGroups/chassis`, every wheel's suspension query in `groundQuery`, each
naming the other, so no wheel query hits any chassis, its own or another env's (the PhysX schema:
the wheel attachment's `collisionGroup` "defines what the wheel/suspension scene queries should
treat as a ground surface"). Inverted, the chassis would collide only with the wheel queries and
the queries would hit only chassis: wheels riding on cars and missing the ground (139, 243).
Per-env groups under the normal meaning need every group to name every other (about a million
relations at 1024 envs). So engine A must never get Isaac Lab's groups; the fix keeps the cars
apart by place instead, and aib's groups stand. (A per-env scheme inside aib that holds under
inversion is possible, a change to a shared submodule for every aib user; not needed here.)

## The fix: engine A lays its slots out apart (133 approved, 2026-11-23)

1. **Route boxes.** Engine A takes a `route_box` (x0, x1, half_width; m about a slot's origin):
   all its car can reach in an episode. The lead-brake task's (`leadbrake.route_box`): the car's
   fastest is stock's fastest start (14 m/s) plus full drive over the route, 25 % over the ECU
   row's 5.22 m/s^2, v^2 = 14^2 + 2 x 6.5 x 300, 57.7 m/s. A car leaving its bounds is reset at
   the next policy step (off-road at 3 m, route done at 300 m), so it is past them by at most one
   step, 0.05 s, 2.9 m at its fastest; a corner of its box (spun any way, 3.93 m from its origin)
   reaches further still. So: x from -2.1 to 312.1 m, half-width 10.1 m.
2. **Layout** (`layout.route_layout`): the boxes 3 m apart at least (`route_gap`), in columns
   along y: rows 23.3 m apart, columns 317.3 m. 1024 envs: 6 columns of up to 176 rows, centred,
   within the task's 4 km ground (out to about 2 km from the world's origin). Only the backend
   reads engine A's origins; every term reads the car relative to them (the backend's state),
   never Isaac Lab's env origins, which are engine B's.
3. **Refusal** (`layout.engine_a_origins`): engine A with N > 1 refuses to start without a route
   box, when the boxes do not fit the ground, or when two come within the gap.
4. **Guard while running**: once a policy step the backend measures the smallest distance between
   two cars; every 24 steps it prints that window's minimum, and warns under 5 m.
5. **Kept**: the landing check's 5 cm pose limit and its velocity check (0.5 m/s, 0.2 rad/s), as
   regression guards; the landing log (`env.landing_log`, `run_p4.sh`'s engine A runs).
6. **Tests**: `test_layout.py` (no Isaac): no overlap from 2 to 4096 slots, the ground respected,
   a ground too small refused, many slots without a box refused, stock's 10 m grid overlapping.
   `scripts/check_engine_a_layout.py` (Isaac, no training): every slot replays the same episode
   under the same actions; each observation term and the reward must match slot 0's in every
   slot, no two cars come within 5 m, and every car at rest after a full brake stays put.

## Checks after the fix

`check_engine_a_layout.py`: stock's seed 2 episode 0 in every slot, 120 policy steps of the same
drive and steer in every slot, then 2 s of full brake. At 200 slots (2 columns, out to 2 km) and
at 1024 (6 columns, slots 0.01 to 2.2 km from the world's origin):

| | 200 slots | 1024 slots | bound (set after these results, 133) |
|---|---|---|---|
| reward vs slot 0 | 8e-7 | 8.5e-7 | 1e-3 |
| observation: v, yaw rate, yaw, v - v_lead, a_lead | <= 1.5e-5 | <= 2.2e-5 | 1e-3 |
| observation: y vs slot 0 | 1.46 cm | 1.46 cm | 2 cm |
| observation: gap vs slot 0 | 1.8 mm | 1.12 cm | 2 cm |
| y from the slots' median: slope against distance from the origin | | 4.7 mm/km | 1 cm/km |
| the same: at the origin, largest | | 1.7 mm, 1.0 cm | largest 2 cm |
| the same: residual from the line, median / 90 % / 99 % / largest | | 1.3 / 2.8 / 3.8 / 7.3 mm | reported, not judged |
| cars' smallest distance | 23.26 m | 23.26 m | 5 m |
| at rest: height change, speed | 7e-7 m, 3e-10 m/s | 7e-7 m, 3e-10 m/s | 1 cm, 0.05 m/s |

The slots differ by about a centimetre across after 6 s, at every distance: the largest lateral
deviation from the slots' median is 9.0 mm among the 108 slots within 500 m of the world's
origin, 9.1 mm at 500 m to 1 km, 10.3 mm beyond. So most of it does not come from the distance:
it is the solver's and the float32 arithmetic's rounding along each car's 840 steered substeps,
which a far coordinate adds to only a little (the slope, 4.7 mm per km; float32's ULP is
proportional to the coordinate, 6e-5 m at 500 m, 2.4e-4 m at 2 km). The gap's 1.1 cm follows
|x| (out to 950 m here, 314 m at 200 slots: 1.8 mm). A layout error looks different: an offset
of metres, or a contact (a velocity jump, which the landing check catches). So the check bounds
the slope (1 cm per km) and the largest deviation (2 cm), each three orders of magnitude under a
layout error.

Two bounds tried on the way were wrong, and were dropped before they gated anything: 133's
first, fail above 2 mm per km, on the premise that rounding does not grow with distance (it
does: the ULP is proportional to the coordinate); and 139's, fail on any slot 5 mm off the fitted
line, set before any residual was seen (the nearest slots' rounding alone is 7 mm off it: a
per-slot residual cannot tell rounding from an odd slot). The residuals are shown above as
information. Per-slot data: the check's `--out` (distance, deviation, residual per slot).

**The cost, named** (in P4's engine A row too): engine A's 1024-slot layout spans about +-2 km,
about 13 times stock's grid's coordinates (about 160 m). Slots playing the same episode drift
about 1 cm apart across over 6 s, near the origin as far out (rounding along the run, the far
coordinate adding about 5 mm per km), against the task's 3 m off-road bound.

**The 1024-env reproduction with the fix** (`run_p4.sh repro`, 30 iterations, seed 1, the
landing log on, a miss logged rather than raised): 2624 resets, **0** landing misses (largest:
0.35 mm across, 0.65 mm along beyond a substep's travel, 0.018 m/s across, 0.022 m/s along, 0.032
rad/s yaw rate; before the fix, at 64 envs, 5 of 192 missed by up to 3.6 m/s), **0** pairs of cars
within 2 m, the cars at least 17.4 m apart at every policy step (the guard's 5 m never neared).
The stage still holds no Isaac Lab groups, as intended. Then engine A seeds 1-5 rerun from
scratch, after 133's word.
