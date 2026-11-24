# 034: A collider made again at a path an earlier one had makes omni.physx warn "only in one collision group"

**Severity**: low. Every collider is in one group and the filtering works, as in 032; the
warning floods the log (452 lines over the second and third of three 800 m drives) and hides the others. **Status**:
fixed in swb_isaac_world eedae29 within a stream; across loads (issue 152's record), a fix
built and not yet run (below). **Found**: 2026-11-03 on newslab-server-241, the 066 R4 budget rerun
(`spikes/rock_world.py`, three speeds in one process), Isaac Sim 6.1 (omni.physx 110.3.2).

## What happens

Issue 032's fix took a single 800 m drive to no warning. Three drives in one process (40, 60
and 80 km/h, the car teleported back to the start between them) logged none in the first
drive and 452 from the second on. A traced run (`ROCK_TRACE_USD=1 ROCK_SPEEDS=60,60
ROCK_LENGTH=200`) gave 74, all in the second drive:

- the teleport's frame made ten collision tiles at the start; the step after it warned ten
  times;
- every later frame that made two collision tiles and two tile static-rock colliders warned
  four times, and frames that made only rock prims (taken from the pool) did not warn.

The tiles and static colliders made in the second drive are made at the paths the first drive
made and removed: a tile's path is its key (`/World/RoadCollision/t_<i>_<j>`, the tile's
static rocks `/World/RoadRocks/s_<i>_<j>`). In one drive the stream never comes back to a tile,
so no path is used twice; a car turning back, a teleport, a second vehicle following the
first or a scenario run again in the same world all do.

## Why

The same omni.physx path as 032's (`CollisionGroup.cpp`, `getCollisionGroup` on its Fabric
update): a collider at a path that was in the group, removed, and then put in the group again
with a new prim resolves to two group entries. Its Fabric copy of the group seems to keep the
removed prim's. Not ours to change; ours not to reuse a path.

## Fix

Every collider the stream makes gets a path of its own, never used before in the session: the
tile key plus a serial (`t_<i>_<j>_<n>`, `s_<i>_<j>_<n>`). Nothing looks a tile's prim up by
its path name (the stream keeps the path per tile; the contacts take everything under
`COLL_ROOT` as ground, issue 033).

Measured after the fix (2026-11-03, host load 6-9): three drives in one process (40, 60, 80
km/h) and two lone 80 km/h drives, 800 m each, no warning.

## Found on the way: an edit of a big group is slow

The same commit makes the rock pool when the stream is made (roadmap 066 R4). With the pool's
960 prims in the rocks group, every tile row's edit of that group (the tile's static rocks in
and out) took about 100 ms of the next step: 46 frames over 50 ms in 800 m at 80 km/h. A
tile's static rocks now have a group of their own (`rockTiles`, with the rocks' filters),
which the window edits; the rocks group changes only when a prim is made beyond the pool. No
frame over 50 ms since.

## Again, across loads (2026-11-25, from issue 152's record)

Issue 152's live runs logged "Collisions are supported currently only in one collision group" 770
times a run: 768 at the step after the scenario's load made its rock pool, and 2 later (a run
without rocks logs 2). The world server's preload (issue 152) loads the map once and makes a rock
stream with its 768-prim pool. The scenario's `LoadWorld` keeps the world and loads the road again,
which removes that stream's prims and makes a new stream. Each stream, and each `DetailColliders`,
counted its path serial from 1 (`self.serial = 0` in its constructor), so the new pool's prims
took the removed pool's paths, `/World/RoadRocks/r1` to `r768`. That is this issue's case: a
collider made at a path an earlier one had, which omni.physx takes for one in two groups. The
fix above made each path new within a stream, not within the session. Issue 152's probe found
every rock in `rocks` alone by USD and its stage tests no warning, which fits the first finding
here, that the filtering works. The warnings are the log's flood, not the contacts' cause.

- **The fix (built offline, not run; siw local branch pool-paths 7813843 on main 26a3573):** one
  serial for the session (`rock_layer.next_serial`, a module counter), taken by the three path
  sites: the collision tiles `t_<i>_<j>_<n>`, a tile's static rocks `s_<i>_<j>_<n>` and the
  rocks `r<n>`. Reusing the pool across loads would also do it, but the pool belongs to a stream
  that the load replaces. Tests without Isaac (`test_session_paths.py`): the serial never repeats,
  two loads make the same tile at two paths, and every path site takes the session serial.
- **118's prediction (before any run):** the live haruna_down drive on *rough_rocks* (issue 152's
  run) logs about 2 of the warnings instead of 770, its base contacts stay 0, and it passes. The
  run waits for a GPU window from the other session that holds GPU0, and for 133's word.
