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
