# 123: rocks collide with the base road although the roadBase filter should keep them off

**Status:** open; the fix plan below is for 133's approval, before any code. **Severity:**
medium: a loose rock rests on the base road mesh as well as on its collision tile, so where the
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
