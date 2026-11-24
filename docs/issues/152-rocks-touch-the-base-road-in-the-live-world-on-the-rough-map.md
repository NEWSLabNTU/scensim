# 152: rocks touch the base road in the live world on the rough rocks map, after issue 145's fix

**Status:** open; the doc and its prediction, before any probe or fix. **Severity:** medium:
issue 123's self-check fires, so some rocks rest on or fall to the world's own road and terrain
instead of the true surface; off the carriageway, so 086 C6d's judged numbers are not moved.
**Found:** 2026-11-24, scensim 118, 086 C6d's runs (filed by 133). Follows issues 145 and 136.

## What happens

086 C6d's three *rough_rocks* runs (Autoware's Model 3 on haruna_down, 1.47 km, the live world
server under the testbench, scensim main 35127469, siw ac008bd, which has 145's fix 1535c3b)
each log 10 or 11 of issue 123's self-check errors and 0 of issue 145's intake WARNs. They are
the same pool rocks at the same places in every run; only which base prim each meets varies.
Along the ego's drive (the log line's wall time mapped to sim time by the world server's
"sim time" lines, then to the ego's distance driven; good to a few metres):

| rock | s, m | meets (r1; r2; r3) |
|---|---|---|
| r196 | 409 to 411 | `RoadCollision/t_8_25_79` in all three |
| r561 | 620 to 622 | `RoadCollision/t_11_26_146`; the same; `env/Terrain` |
| r422 | 623 to 625 | `RoadCollision/t_11_26_146`; the same; `env/Terrain` |
| r590 | 1179 | `env/Road`; `env/Terrain`; `env/Terrain` |
| r218 | 1190 to 1192 | `env/Road` in all three |
| r2 | 1210 | `env/Terrain` (r1 only) |
| r112 | 1217 | `env/Road` in all three |
| r497 | 1219 | `env/Road` in all three |
| r264 | 1227 | `env/Road`; `env/Road`; `env/Terrain` |
| r183 | 1333 | `env/Road`; `env/Terrain`; `RoadCollision/t_15_47_303` |
| r282 | 1336 | `env/Road`; `env/Terrain`; `RoadCollision/t_15_47_303` |

*rough_none* logs none. The same runs log omni.physx's "Collisions are supported currently only
in one collision group" 770 times in each *rough_rocks* run, all at the step after the 768-prim
rock pool is made (`rock pool: 768 prims for 1 vehicle(s)`), against 2 in every *rough_none* run
and 2 in each of C6b's eleven live Haruna runs (rocks or none, before 145's fix). Issue 145's
proof saw that warning once a run.

## Why 145's proof did not see it

145's proof ran `fixture_cost --follow` (`course/fixture_drive.py`), not the live world server:
0 contacts on the smooth rocks map at 10 m/s (1020 m) and 13.9 m/s (1330 m), and 0 on this
rough map, but only to 280.4 m (issue 136's run, 400 timed frames). The first contact here is at
about 409 m. The two paths also build the road's groups differently:

- fixture_drive gives `RockStream` the world's `ground_paths` (`base_ground`), so `roadBase` is
  `/World/env/Terrain`, `/World/env/Road`, `/World/env/Lines`;
- the live world (`world.py` `_load_road`) gives it `road_layer.load_ground(path) or
  list(self.ground)`, and none of the three Haruna maps' `road_detail.yaml` has a `ground`, so
  `roadBase` is `self.ground`, which `_load_road` has just extended by `/World/RoadCollision`,
  the detail collision tiles' root. The tiles are then in `roadBase` (through their root) and in
  `roadDetail` (by their own paths), and issue 123's self-check counts a rock's contact with a
  detail tile, where a rock should rest, as a base contact;
- in the live world the ego is spawned before the rock pool is made (its GNSS line comes 2 s
  before `rock pool:`); in fixture_drive the order is the course's.

## The diagnosis (proposed; before any run)

A probe in the live world server (the testbench's *rough_rocks* package, one run, the quiet
rule), logging at the step after `reserve` and at each of the contacts above:

1. `roadBase`'s, `rocks`', `rockTiles`' and `roadDetail`'s includes, expanded, and for each
   pool rock and each detail tile met, the groups whose expanded includes hold it;
2. for each rock that meets the base, its pool history: when it was made, parked, first placed,
   and placed again (a pool rock is reused, `RockStream.pool`), and its group membership at each
   placement;
3. for each detail tile met, the frame it was made and the frame its path was written into
   `roadDetail`, and whether `roadBase`'s includes covered it at its intake.

- **118's prediction (before the probe).** Two causes, both of the live world's path, neither
  of 145's ordering:
  - (a) The contacts with `/World/RoadCollision/t_*` (3 a run: r196, r561 and r422 in r1 and
    r2; r196, r183 and r282 in r3) are not base contacts. They are the self-check counting the detail tiles
    as base because `roadBase` holds their root. The probe finds `/World/RoadCollision` in
    `roadBase`'s includes, and each such tile in two groups.
  - (b) The contacts with `/World/env/Road` and `/World/env/Terrain` (8, 7 and 7) are rocks
    that fell through a detail tile they should rest on: a tile in two groups is taken by PhysX
    into one of them, and where it lands in `roadBase`, the rocks (which filter `roadBase`) pass
    through it to the world's road below, which they should not meet either. The probe finds
    each such rock above a detail tile that PhysX holds in `roadBase`.
  - The 770 warnings are not all the pool's: about 2 are the world's own, as without rocks, and
    the rest are colliders the first step after the pool takes in with two groups. 118 expects
    the probe to name them; if they are the 768 pool rocks, (b) is wrong and the pool rocks'
    second group is the cause, and the probe's (1) says which.
- **The fix, if (a) and (b) hold (proposed, not built):** the live world hands `RockStream`
  the world's own ground without `/World/RoadCollision` (as fixture_drive does), so `roadBase`
  is the base alone, and issue 123's self-check stops counting the detail tiles. A test without
  Isaac: `RockStream`'s ground from `_load_road` does not hold `COLL_ROOT`. Its proof: the three
  C6d *rough_rocks* runs' drive in the live world, 0 contacts and 2 "one collision group"
  warnings a run.

### The probe's result (2026-11-24, 21:15 to 21:22)

One haruna_down run on *rough_rocks* in the live world server (testbench
`isaac_c6d_haruna_rough_rocks`, rebuilt over main aa731a17's install), with a local probe commit
of siw (8900110 on 7d032d6, never pushed) checked out in the gate checkout for the run and
restored after. GPU0 shared with another session's encode job by agreement; nothing timed. The
run passed haruna_down. Two earlier attempts ended early: one was refused because the testbench
was built over the previous install, and the other ended at the first contact on the probe's own
error (it read an empty rock set). Neither counts.

What the probe built, against the plan above: (1) in full (the groups' includes, every collider's
groups at the step after the pool); (3) as each tile's groups when it is made, not its intake
frame; (2), the pool history, was not built. At each contact it logged the rock's groups, its
pose, what it met and that prim's groups, and the detail tile under the rock with the detail's
height above the base there.

- `roadBase`'s includes are `/World/env/Terrain`, `/World/env/Road`, `/World/env/Lines` and
  `/World/RoadCollision` (expandPrims). `rocks` holds the 768 pool prims; `rockTiles`,
  `roadDetail` and `groundQuery` are empty at that step.
- At the step after the pool: 893 colliders, **none in two or more groups** by USD membership.
  The same step logs omni.physx's "only in one collision group" 770 times, as in C6d's runs.
- Every detail tile made in the drive is in both `roadBase` (through its root) and `roadDetail`.
- 13 contacts (C6d's runs had 10 or 11; r195 and r162 are new, the rest are C6d's). Every rock
  met is in `rocks` alone. 5 met a detail tile, 8 met `/World/env/Road` or `/World/env/Terrain`.
  At every one, the detail under the rock is within 1.2 cm of the base (its height above the base
  -0.012 to +0.011 m).

**118's prediction against the probe:**

- (a) **Held.** `roadBase` holds `/World/RoadCollision`, every tile is in two groups, and the
  contacts with a tile are rocks in `rocks` resting on the detail, which issue 123's self-check
  counts as the base. There were 5 of them here, not 3.
- (b) **Failed.** The contacts with the world's road and terrain are not rocks that fell through
  a tile. Each lies where the rough road's detail is flush with the base (within 1.2 cm), so a rock
  resting on the tile is also within contact distance of the world's own road. Why the `rocks`
  against `roadBase` filter does not hold for those pairs is not answered by the probe.
- The 770 warnings: **not** two-group memberships in USD. At the step that logs them, no collider
  is in two groups and each pool rock is in `rocks` alone. Their source is open. C6b's live runs,
  before issue 145's fix, logged 2, so they came with that fix in the live world, where the pool
  joins `rocks` before PhysX takes it in.
- 133's questions. Pool rocks placed again later: at each contact the rock is in `rocks` alone,
  so a lost membership is not the cause. Its placement history was not logged. Tiles made after
  the membership was set: the tiles are in `roadBase` from their intake, through the root
  include, as well as in `roadDetail`.

Record: `/mnt/renegade/aeon/isaac-ex/c6d/i152` (`run152.sh`, `times.txt`), the run's directory
`isaac_c6d_haruna_rough_rocks/runs/2026-11-24T21-15-12_haruna_down_r0`.

## The fix test (before the run)

The fix (siw issue-152 e0559e5, local): `rock_layer.base_ground` gives the rock stream the
world's ground without `/World/RoadCollision` (road_detail.yaml's `ground` first, as before),
and `RockStream` refuses a ground that holds the tiles' root. A test without Isaac
(`test_issue_152.py`). The run: the probe's run again, with the probe commit on the fix
(3e4b1ff, local), the same package, GPU0 as agreed with the other session.

Two hypotheses from 133, checked against the probe's record before the run:

1. *The 770 warnings are the tiles, in two groups through the root include.* Not supported.
   The probe's membership query expands the includes: it found each tile in `roadBase` through
   the root. But 768 of the 770 warnings come at the pool's step, all within 13 ms, when no
   tile exists (`roadDetail` is empty there and the first 14 tiles come 4 s later). The other 2
   come after the first tiles, and *rough_none*'s runs, whose tiles are in one group (no rock
   stream, so `roadBase` is empty), log 2 as well. So 768 is the pool, one a rock, although
   USD puts each pool rock in `rocks` alone; the tiles in two groups logged no warning.
2. *The env contacts are the checker, not physics.* Not so. Issue 123's check
   (`RockStream.check_base`) reads PhysX's contact report headers, for the rocks that carry a
   contact report (threshold 0), skips `CONTACT_LOST`, and matches the other collider's path
   against the base's paths. It is not a geometric query. A pair PhysX filters makes no contact
   report, so each env contact is a pair PhysX did not filter.

- **118's prediction for the fix test.**
  - The run passes haruna_down.
  - Every tile made is in `roadDetail` alone (no probe line of tiles in two groups).
  - Contacts with a detail tile: 0. That is by construction: the check no longer counts the
    tiles as base.
  - Contacts with `/World/env/Road` or `/World/env/Terrain`: about 8 (5 to 11), the same rocks
    as the probe's run. Nothing in the fix touches the pool rocks' filtering.
  - The "only in one collision group" warnings: 770 as before, 768 at the pool's step and 2
    later.
  - If the env contacts stay, the next step is a stage test of the filter itself: a pool rock
    taken in with `rocks` before its first step, resting on a tile flush with a `roadBase` mesh,
    with and without the pool's 768. The pool's warnings come with issue 145's fix, so the
    stage test asks whether a rock that PhysX warns for keeps `rocks`' filter.

### The fix test's result (2026-11-24, 21:26 to 21:34)

The fix with the probe (3e4b1ff), the same package and drive. The run passed haruna_down.
`roadBase`'s includes are `/World/env/Terrain`, `/World/env/Road` and `/World/env/Lines`. No tile
was made in two groups. Issue 123's check logged 10 contacts, every one with `/World/env/Road` or
`/World/env/Terrain`. The "only in one collision group" warnings: 770.

- Passes haruna_down: **held**.
- Tiles in `roadDetail` alone: **held**.
- Tile contacts 0: **held** (by construction).
- Env contacts about 8 (5 to 11), the probe's rocks: **held** in number (10). Five of them
  (r196, r561, r422, r590, r112) met a tile in the probe's run and meet `env/Terrain` or
  `env/Road` now. The check logs a rock's first base contact only, so in the probe's run those
  five touched a tile first. They touch the base road as well, as the other five do. r195, r2
  and r162 did not come this time.
- Warnings 770: **held** (768 at the pool's step, 2 later).

So the fix removes the tiles from `roadBase` and the check's false count, and nothing else. Each
of the 10 rocks met the base at the pose it was placed at (the same poses to the millimetre as in
the probe's run), where the detail is flush with the base (-0.012 to +0.011 m). These are pairs
PhysX did not filter. Before issue 145's fix, C6b's live runs (on the smooth map, where the pool
joined `rocks` only after PhysX took it in) had 11 or 12 such contacts and 2 warnings. So base
contacts in the live world are older than the 768 warnings, although on another map; whether the
two are linked now is the next probe's question.

## The second probe (133's hypothesis; before the run)

133's hypothesis ties the two open items together. PhysX sees each pool rock in two groups at
intake, whatever the first probe's query said, because some group holds an ancestor of
`/World/RoadRocks` (`/World`, an env or vehicle group with expandPrims, or a collection with
includeRoot). For the rocks where PhysX picks the other group, `rocks`' filter against `roadBase`
does not apply, and those are the rocks that meet the base.

The first probe looked only at the groups under `/World/vehicleCollisionGroups`. The second
(probe v2, 2fcbdd1, local, on the fix) logs at the pool's step every collision group anywhere on
the stage: includeRoot, expansion rule, merge group, invert, filtered groups, includes and
excludes. It also logs UsdPhysics' collision group table for rocks against roadBase and against
roadDetail, and a pool rock's groups among all of them. At each contact it logs the rock's groups
among all of them. PhysX's own group for each rock shape is not exposed to Python, as far as 118
found (133's check (b)), so the probe cannot read it.

- **118's prediction.** Every collision group is under `/World/vehicleCollisionGroups`. The world
  USD holds none, and aib and scensim_isaac_world define their groups only there. None holds an
  ancestor of `/World/RoadRocks` or has includeRoot. The table has `rocks` and `roadBase` not
  colliding. A pool rock and each rock met are in `rocks` alone. Contacts are about 10 again, and
  the warnings 770. If so, 133's mechanism has no second group in USD, and the next step is a
  stage test of the filter (a rock in `rocks` at intake, resting on a tile flush with a `roadBase`
  mesh, with and without a 768-rock pool, counting the warnings and the contacts).
- **133's prediction, if the probe finds a second group:** the fix is to exclude
  `/World/RoadRocks` from it. In a second fix run the env contacts go to 0 and the warnings to 2.

### The second probe's result (2026-11-24, 21:35 to 21:43)

Probe v2 on the fix (2fcbdd1), the same package and drive. The run passed haruna_down.

- Every collision group on the stage is under `/World/vehicleCollisionGroups`: `chassis`,
  `groundQuery`, `roadBase`, `rocks`, `rockTiles` and `roadDetail`. None has includeRoot, a merge
  group, invert or excludes. All expand by expandPrims. None includes an ancestor of
  `/World/RoadRocks`: `chassis` holds the ego's body and skid plate, `roadBase` the three env
  prims, `rocks` the 768 pool prims, and the rest are empty at that step.
- UsdPhysics' collision group table: `rocks` against `roadBase` do not collide; `rocks` against
  `roadDetail` do.
- A pool rock (`r1`) is in `rocks` alone among all of them. So is each rock met.
- 13 contacts, every one with `/World/env/Road` or `/World/env/Terrain`, at the same placed poses
  as before. r195, r2 and r404 came this time. The warnings: 770.

**118's prediction: held**, except the contacts: 13 against about 10, within the runs' spread so
far (10 to 13). **133's prediction (a second group): not found.** In USD there is no second group
for PhysX to pick, and the table says the pair is filtered, yet PhysX reports the pair's contacts.

What the runs leave. In this world, a pool rock in `rocks` that rests where the base is within
about 1 cm of the detail meets the base when it wakes, although every USD view filters the pair.
It also comes with one "only in one collision group" warning per pool rock at intake. Issue 145's
stage test (64 pool prims, a tile at z 0, the base 5 cm above it, the fix's order) had 0 of 64
meeting the base. The live world differs from it in the base's height (flush, not 5 cm above),
the pool's size (768) and the base's kind (the world's large env meshes, not a box). The next
step is to put those differences into the stage test one at a time (prediction first).
