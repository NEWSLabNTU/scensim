# 123: rocks collide with the base road although the roadBase filter should keep them off

**Status:** fixed on siw `086-c6b` (3f90fb3, 2ef3001), to land after 086 C6b's fixture rerun.
A harness fault in `fixture_drive`: the world server never had the contact (see "The finding").
**Severity:** medium, as first judged: a loose rock rests on the base road mesh as well as on its collision tile, so where the
base and the true surface differ (a rut, a crowned road's sides without issue 120's tiles, the
ditch) it would rest on the higher of the two, the thing the filter exists to prevent (066 R4).
**Found:** 2026-11-23, scensim 118, issue 122's push trace.

## What happens

The rock stream (`rock_layer.RockStream`) puts the world's ground (`road_detail.yaml`'s `ground`,
or the world's ground paths) in a `roadBase` collision group, and its `rocks` and `rockTiles`
groups filter `roadBase` out, so that a loose rock rests on the detail's collision tiles, the
true surface, and not on the base. In issue 122's fourth test (siw fe69aa9, aib ff5e72b,
fixture_c6b, loose_15, raycast, tiles on; NAS "2026-11-23 issue 122 base contact (118)"), PhysX's
contact report on the rock names both colliders in each of the 63 steps it is in contact, each
with normal force: its tile 18.9 kN summed (4.7 kN at most), `/World/env/Road` 23.2 kN summed
(7.5 kN at most).

The USD is as meant (siw bcee32e, the groups printed once the rock is found): `roadBase` holds
`/World/env/Road` and `/World/env/Terrain`; `rocks` holds the rock (`/World/RoadRocks/r776`) and
filters `groundQuery` and `roadBase`; `rockTiles` filters the same. So PhysX does not apply what
the USD says.

A clue: every run with rocks logs omni.physx's "Collisions are supported currently only in one
collision group." 769 times, once at the road's load, when the stream makes its pool of parked
rock prims (`RockStream.reserve`) and adds them to `rocks` in one edit; a run with the tiles
alone logs it once. Issues 030, 032 and 034 met this warning before: PhysX taking a streamed
collider for one in two groups, after which it applies neither group's filter as written.

## Fix plan (for approval, before any code)

1. **Find which colliders PhysX takes for two groups**, before choosing a fix (each a short
   fixture_drive run, loose_15, tiles on, the contact report naming what the rock touches):
   - the pool off (`prewarm` off, every rock made live as it streams in): if the warning goes and
     the rock stops touching the base, the pool's one-edit membership is the cause;
   - the pool on, its prims added to `rocks` one frame after they are made (as the live ones):
     the same question for the timing;
   - the base: whether `/World/env/Road` is taken into a second group (the warning count with the
     rocks' groups made but no rock prims).
2. **The fix** follows from 1. The candidates: the pool's prims put in `rocks` as live ones are
   (by their own path, a frame apart); or the rocks kept off the base by PhysX's filtered pairs
   (`UsdPhysics.FilteredPairsAPI`, rock and base) instead of the groups, where the groups do not
   hold.
3. **Tests**: a unit test with a stand-in for pxr that the pool's membership edits are made as the
   chosen fix makes them; and live, the rock touching its tile alone over the steps it is in
   contact, the warning gone from the load, and loose_15's travel recorded beside issue 122's.

## The diagnosis (approved by 133, 2026-11-23; predictions before the runs)

loose_15, raycast, tiles on, `--trace-push` (the collider each contact is with), siw e4ffffc's
`--rock-pool`: (i) `off`, no pool, every rock made live as it streams in; (ii) `late`, the pool
made as now but its group edit flushed a physics step later; and the pool `on` as the control.
(iii) is read from (i): the warnings logged at the road's load with the rocks' groups made and no
rock prim, against the tiles-alone run's one.

- **118's predictions:** (i) the load's warnings go (one, as tiles alone), the live rock is put in
  `rocks` by its own path at a frame's end, and it touches its tile alone; (ii) the warnings go
  and the rock touches its tile alone, the timing being the cause; (iii) the base is not taken
  into two groups (one warning at most). The control as before: 769 warnings, base contact.

## The diagnosis' result (2026-11-23)

siw e4ffffc, aib ff5e72b, GPU0; NAS "2026-11-23 issue 123 diagnosis (118)". The warning at the
road's load, and the normal force on what the rock touches over its contact (summed):

| pool | warnings | its tile | the base road |
|---|---|---|---|
| on (control) | 769 | 18.9 kN | 23.2 kN |
| off | 1 | 18.9 kN | 23.2 kN |
| late | 1 | 18.9 kN | 23.2 kN |

- (i) and (ii): **the warnings go, the base contact does not**, to the newton. The prediction
  failed on the contact: the pool's one-edit membership causes the warnings, but not the base
  contact. (The warnings are a fault of their own and harmless here; they go with the fix below
  if it moves the pool's edit.)
- (iii): the base is not taken into two groups (one warning, as the tiles alone).

**The next lead (before the run):** the `roadBase` group and the rocks' filter on it are made
when the road loads, after the simulation has started (`world.play`), around ground prims PhysX
already holds. Issue 030 found PhysX not taking a streamed prim into a group through its
parent's path; a static collider PhysX parsed before its group existed may likewise keep no
group. Test (iv): the same run with `roadBase` (the world's ground) and the `rocks` group's
filter on it made before the simulation starts. **118's prediction:** the rock then touches its
tile alone.

## Test (iv)'s result (2026-11-23)

siw 17aa0d9 (`--groups-early`), the rest as the diagnosis; NAS "2026-11-23 issue 123 diagnosis
(118)". With `roadBase` and the rocks' groups made before `world.play`, **the rock touches its
tile alone** (36.0 kN summed over its contact, nothing on the base), the load logs one warning,
not 769, and loose_15 moves 6.5 cm (1.5 cm with the groups made at the load). The prediction holds:
groups made while the simulation runs, around ground PhysX already holds, are not applied to it.

`fixture_drive` adds the world's USD before the simulation starts and the road after; the world
server (`world.py`) starts the simulation at its own start, then adds the map's USD and its road
in `load`, so whether its ground keeps the filter is not shown by this run. That is the fix's
first question.

## Fix plan, revised (for 133's approval, before any code)

1. **The world server's order, reproduced**: `fixture_drive --server-order` (the simulation
   started first, then the world's USD, then the road, as `world.py` does), the groups as today:
   does the rock touch the base there?
2. **The fix**, if it does (or regardless, so the order cannot break it): the groups' prims made
   with the vehicles' groups before the simulation starts (`ensure_vehicle_scene`'s place in
   `world.py`, and `RockStream` taking them as they are), and `roadBase`'s members set in the same
   stage edit that adds the map's ground, before the first physics step after it. Where that
   still does not hold, the rock-base pairs filtered per pair (`UsdPhysics.FilteredPairsAPI`) on
   each rock prim as it is made.
3. **Tests**: a unit test with a stand-in for pxr of the order of the group edits; live, in the
   server's order, the rock touching its tile alone, one warning at the load, loose_15's travel
   recorded.

## Step 1: the world server's order (approved by 133; prediction before the run)

`fixture_drive --server-order` (siw after 17aa0d9): `world.reset`, `world.play`, then the world's
USD, then the road (as `world.py`'s start and `load`), loose_15, raycast, tiles on, the groups as
today (made at the road's load). Read: what the rock touches, and the warnings.

- **118's prediction:** the rock touches the base here too. The map's ground is parsed by PhysX at
  the first physics step after the USD is added (`load` steps once after the road, issue 039),
  but the road's load sets `roadBase` after that USD is already in the stage; whether one step
  separates them or not, the rock pool's prims and the groups are edited in the same frames as in
  `fixture_drive`, where the filter did not hold.

### Step 1's result (2026-11-23)

siw 2f96a99, aib ff5e72b; NAS "2026-11-23 issue 123 server order (118)". **The prediction
failed.** In the world server's order the rock touches its tile alone (`t_12_0_9`, 36.0 kN summed
over its contact, nothing on `/World/env/Road`) and loose_15 moves 6.5 cm, as with the groups
made before play. The load logs 771 "only in one collision group" warnings, as in
`fixture_drive`'s order.

So the base contact is `fixture_drive`'s order alone: the world's USD added before the
simulation starts and the groups made after it runs. The world server adds its map's ground
after the simulation starts, and the groups made at the road's load then hold. The pool's
warnings come with both orders.

## Step 2: the fix (approved by 133, applied whatever step 1 showed; predictions before the runs)

siw after 2f96a99:

- `rock_layer.define_groups(stage)` makes the road's groups (`roadBase`, `rocks` and `rockTiles`
  filtering `groundQuery` and `roadBase`, `roadDetail` filtering `groundQuery`). `world.py`
  calls it next to `ensure_vehicle_scene`, before `world.reset` and `world.play`.
  `DetailColliders` and `RockStream` call it again; it is idempotent. `RockStream` only sets
  `roadBase`'s members, the map's ground, at the road's load.
- The rock pool's prims no longer join `rocks` in `reserve`. They join at the next frame's end
  (`update`'s single edit), as a live rock does.
- `fixture_drive` makes the groups before play as `world.py` does. `--groups-late` restores the
  old order, and `--groups-early` now only sets `roadBase`'s members before play too.

Runs: loose_15 at 11.11 m/s, raycast, tiles on, `--trace-push`. One run in `fixture_drive`'s
order and one with `--server-order`. Read: what the rock touches, the warnings, loose_15's
travel.

- **118's predictions:**
  - Server order: the rock touches its tile alone, as in step 1.
  - `fixture_drive`'s order: the rock touches its tile alone too. The groups exist before PhysX
    parses the ground, and a later change to an existing group's members is applied, as the live
    rocks' group edits are every frame. This is the less certain of the two. If it fails, the
    base's members must also be set before play, which only `fixture_drive`'s order can do (the
    server has no map's ground then). The server's order would be unaffected.
  - Warnings: at most 2 per load in each order (test (iv) logged 1), none from the pool.
  - loose_15: 6.5 cm in each order, within 1 cm.

### Step 2's result (2026-11-23)

siw 3f90fb3, aib ff5e72b; NAS "2026-11-23 issue 123 fix (118)". Raycast, loose_15 at 11.11 m/s:

| order | the rock's contact (normal force summed) | warnings | loose_15's travel |
|---|---|---|---|
| server (`--server-order`) | its tile alone, 36.0 kN | 1 | 6.5 cm |
| `fixture_drive`'s | its tile 18.9 kN, the base 23.2 kN | 1 | 1.5 cm |

- Server order: the prediction holds, as in step 1.
- `fixture_drive`'s order: **the prediction failed.** The base contact is unchanged from before the
  fix. Making the groups before play is not enough. `roadBase`'s members must also be set before
  PhysX parses the ground. Test (iv) set them before play and held. The world server meets that
  condition: its map's ground enters the stage after the simulation starts, and the road's load
  sets the members before the next physics step. `fixture_drive` adds the world's USD before play.
- Warnings: the prediction holds. There is 1 per load in each order, and none from the pool.
- loose_15: the prediction holds for the server order (6.5 cm) and fails for `fixture_drive`'s
  order (1.5 cm), because that order keeps the base contact.

Issue 122's rerun in the server order, sweep: the rock touches its tile alone (45.4 kN summed), 1
warning, 1.6 cm of travel, peak speed 1.30 m/s. The raycast run's peak speed was 1.45 m/s.

Open, for 133:

- whether `fixture_drive` should set `roadBase`'s members before play by default (today's
  `--groups-early`), so that its order matches the server's condition;
- whether the per-pair filter (`FilteredPairsAPI`, the plan's fallback) is still wanted to cover a
  future load that steps between the map's USD and the road.

## The finding (133, 2026-11-23)

**The world server's order never had the base contact.** Issue 123 was a fault in the harness,
`fixture_drive`. It added the world's USD before the simulation started and set `roadBase`'s
members after PhysX had taken that ground in. The pool's warnings were noise on top. Every result
measured with `fixture_drive` before siw 2ef3001 carries the fault; 086 C6b's fixtures are rerun.

**The condition** for the rocks' filter: `roadBase`'s members are set before the first physics
step after the world's ground enters the stage. Making the groups early is not enough on its own.
The world server meets the condition because it adds its map's ground after the simulation starts
and sets the members at the road's load, before the next step. No per-pair filter
(`FilteredPairsAPI`) is added (133).

## The fix, as landed (siw 3f90fb3 and 2ef3001)

- `rock_layer.define_groups` makes the road's groups. `world.py` calls it before play, and the
  stream and the colliders call it again (idempotent).
- The rock pool's prims join `rocks` at a frame's end. The warnings drop from 771 to 1 per load.
- `fixture_drive` and `fixture_cost` set `roadBase`'s members before play (`groups_before_play`).
  `--groups-late` keeps the faulty order as a test switch.
- **The load-time self-check**: every rock reports its contacts, and `RockStream.check_base`
  logs an error naming the rock and the collider when a rock touches `roadBase` within its first
  second awake (each rock once). `world.py` runs the check on each physics step's contact report,
  and `fixture_drive` does too, listing the hits as `base_contacts` in `cases.json`.
- Tests: `test/test_issue_123.py` (the groups and filters, idempotence, the world's order, the
  pool grouped at a frame's end, the self-check) and `test_rock_layer`'s wake test (a rock woken
  begins its check).
