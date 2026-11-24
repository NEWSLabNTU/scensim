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
  - **The caveat tightened (133, before the runs).** A one-frame difference counts as the
    physics' own spread only if the car's pose differs between the two paces before that frame.
    If the poses are the same up to that frame and the tile lists still differ, the wait failed.
    `probe144.py` logs every frame end's car pose (x, y, yaw, speed) on every run, so the
    comparison can tell the two apart.

### The proof's result (2026-11-24, 16:02 to 16:09)

aib 4e8d684, GPU0 under the quiet rule (the host's CPU load was 36 to 65 from other work); record
`/mnt/renegade/aeon/isaac-ex/c6b-140`: `run144.sh`, `probe144.py`, `p144_{b9eb233,19ad467}_{free,real}.*`.
Every run drove 2020 frames, 1020 m, and exited 0.

| | b9eb233 free | b9eb233 real | 19ad467 free | 19ad467 real |
|---|---|---|---|---|
| frames a second | 45.4 | 20.0 | 33.7 | 20.0 |
| rock tiles loaded | 138 | 142 | 163 | 163 |
| collision tiles made | 171 | 178 | 239 | 239 |
| the two paces' (frame, tile) lists | differ | | identical | |
| frame waits, p50 / p95 / max | | | 0.10 / 0.15 / 1775 ms | 0.12 / 0.17 / 1712 ms |
| frames waiting over 50 ms, in all | | | 51, 30.9 s | 48, 27.0 s |
| tiles not ready after 2 s | | | 0 | 0 |

The car's pose was the same at every frame end in all four runs (the largest x, y difference
between paces: 0), so no difference below is the physics' spread.

- **On b9eb233 the paces differ:** 131 rock tiles arrive at other frames, unpaced 2 to 109 frames
  later than held to the wall clock, and 4 come in one run only. Held (prediction).
- **On 19ad467 the lists are identical,** every rock tile and every collision tile at the same
  frame, with 0 tiles missed. Held.
- **The waits at real time:** p95 0.17 ms, as predicted (under 5 ms). But they are not "about
  nothing": 48 frames waited over 50 ms, 27 s in all, about one every 32 frames (1.6 s, a 16 m
  tile at 10 m/s). Partly failed.
- **Unpaced it slowed** from 45.4 to 33.7 frames a second, inside the predicted 25 to 40. Held for
  the fix's rate. The baseline was 45.4 on this loaded host, not the doc's 55 to 80.

**What the long waits are.** The fix loads 21 rock tiles and 61 collision tiles that b9eb233 never
made in the whole drive, even held to the wall clock. They are tiles within 32 m of the car that
`RoadLayer._ahead`'s look-ahead never asks for (it takes the corridors' centrelines ahead, 6 m
about them), mostly a column beside the road. Before the fix nothing asked for them, so they never
existed. Two of them held rocks (8 and 3): before the fix those 11 rocks were never there, at any
pace. The frame-end wait now asks for them as they come within reach, and waits while the worker
makes them. That is the 27 s.

**Proposed next step (not built):** the look-ahead also asks for every tile within the reach
around each car, so the worker makes these ahead of the wait. Its measure is the same drive held
to the wall clock, with far fewer waits over 50 ms, and the same identical lists.
