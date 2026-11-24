# 144: a run stepped faster than real time gets rocks that depend on the wall clock

**Status:** open; the fix follows issue 142 (133). **Severity:** high: a run's rocks, and so its
physics, are not reproducible. **Found:** 2026-11-24, scensim 118, issue 142's Isaac proof.

## What happens

The road's tiles (with their rocks' placement) are made by `TileProcess`, a worker process on the
wall clock, about 5 tiles a second in Isaac on this host. Nothing ties a step to them: a world
stepped faster than real time (`fixture_cost` and `fixture_drive` step as fast as they can, 55 to
80 frames a second against real time's 20) moves the car further per wall second than the worker
keeps up with. On Haruna's rocks map at 10 m/s, 142's code had its in-path rocks load 2.9 m ahead
at 80 frames a second and, the same drive held to the wall clock, when their tiles came within the
32 m reach. Which rocks exist when a wheel reaches them, and so what the car meets, depends on
the host's load and the pace: two runs of the same drive need not agree.

## The fix (planned)

Each frame, before its steps, the tiles within ROCK_REACH and the frame's travel of every car are
waited for, with a bound (`RoadLayer.ready_around`, as a placed car's): a run at real time waits
about nothing, a faster one slows to the worker's pace. Proof: the same drive at two paces gives
identical rock load frames.

## The fix as built (siw branch issue-144 19ad467, on main b9eb233)

`SurfaceLayer.flush`, at every frame's end and before the collision tiles and the rocks are
updated, waits for the road's tiles within their reach (32 m) of every car, rocks' placement
included (`RoadLayer.ready_around`, as a placed car's), at most `FRAME_WAIT_S` (2 s). Tiles still
not ready after that are logged and counted (`wait_missed`), and each frame's wait is kept
(`wait_ms`). The collision tiles want only ready tiles within their reach, and the rocks only
tiles with collision tiles; after the wait every tile within reach is ready. So the frame at which
a tile's collision tile and rocks arrive depends only on where the cars are. Tests:
`test/test_issue_144.py`, including the offline form of the proof (a slow worker, two paces, the
same tiles ready frame by frame; without the wait, the fast pace's frames find fewer).

## The proof (before the runs)

The Haruna drive (`fixture_cost --follow`, one car, rocks map, 10 m/s, 1900 frames) through
`probe144.py`, which logs each collision tile and each tile's rocks by the frame they arrive in.
Two paces: unpaced (as fast as the host steps) and held to the wall clock (probe142c's
`PROBE142_REALTIME`). Each pace runs on main b9eb233 (the control) and on 19ad467. GPU0, the
quiet rule.

- **118's prediction.**
  - On b9eb233 the two paces differ. Unpaced, some collision tiles and rock tiles arrive frames
    later than held to the wall clock.
  - On 19ad467 the two paces give the same (frame, tile) lists for the collision tiles and for the
    rocks, every entry. `wait_missed` is 0 in both.
  - Held to the wall clock, the waits are about nothing (p95 under 5 ms).
  - Unpaced, the drive slows from about 55 to 80 frames a second (the doc's figure) to the
    worker's pace, 25 to 40.
  - Caveat, stated before: the lists match only if the car's path is the same to the frame. If a
    tile's arrival differs by one frame where the car crossed a reach boundary, that is the
    physics' own spread, not the wall clock, and will be shown as such (its car positions).
