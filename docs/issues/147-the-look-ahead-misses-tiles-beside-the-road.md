# 147: the road's look-ahead never asks for the tiles beside the road

**Status:** fixed (siw 26a3573, once landed; filed by 133 from issue 144's proof).
**Severity:** low: speed only. Since
issue 144 the frame's end waits for these tiles, so nothing is missing, but the wait blocks while
the worker makes them. **Found:** 2026-11-24, scensim 118, issue 144's two-pace proof.

## What happens

`RoadLayer._ahead` asks the tile worker for the tiles along each corridor's centreline ahead of a
car, 6 m about it. The collision tiles and the rocks want every tile within 32 m of the car. The
tiles in that circle but off the centreline's band (on Haruna, mostly a column beside the road)
were never asked for. Before issue 144 they were never made at all: on the 1020 m Haruna drive
held to the wall clock, 21 rock tiles (11 rocks, 31.9 to 40.2 m from the car's path) and 21
collision tiles (at least 7.7 m from it). Since issue 144 the frame's end asks for them as they
come within reach and waits while the worker makes them: 48 frames waited over 50 ms, 27 s in all,
on that drive at real time (issue 144's record).

## The fix (proposed, not built)

`_ahead` also asks for every tile within the reach (max of ROCK_REACH and COLLISION_REACH) around
each car that touches a corridor, so the worker has made them before the frame's end needs them.
`Detail.prefetch` skips tiles already made or pending, so asking each substep costs little.

- **118's prediction (before any run).** The same drive as issue 144's proof (Haruna's rocks map,
  10 m/s, 1900 frames, held to the wall clock, probe144) on the fix: frames waiting over 50 ms
  drop from 48 to under 5, their total from 27 s to under 2 s. The (frame, tile) lists stay
  identical to 19ad467's real-time run, since what a frame has is set by the wait, not by when
  the worker began. The unpaced run's rate rises above 19ad467's 33.7 frames a second.

## The fix as built, and the runs (before any run)

siw issue-147 07bf74c on main 46c09ec (local). `RoadLayer._ahead` returns, with the tiles along
the corridors, every tile within `AROUND` (32 m, equal to the larger of ROCK_REACH and
COLLISION_REACH; a test holds it) of the car that touches a corridor: the set the frame's end
waits for (`ready_around`). `SurfaceLayer._wait_for_tiles` logs a WARN ("issue 147: a frame's
end waited N ms ...") for each wait over `SLOW_WAIT_MS`, 50 ms. Tests without Isaac
(`test_issue_147.py`): the reach, every tile the frame's end waits for asked for ahead along a
winding road, none off every corridor, and the WARN over the bound and none under it.

The runs: probe144, Haruna's rocks map, 10 m/s, 1900 frames, under the quiet rule on GPU0 (the
waits are timings), each held to the wall clock and unpaced.

- **Amended before the runs (118, labelled):** a same-day baseline pair on main 46c09ec (the same
  drive, real time and unpaced) beside the fix's pair. Main has moved since 19ad467 (issues 145
  and 152), so the fix is judged against both: the filed numbers (19ad467: 48 waits over 50 ms,
  27 s, 33.7 frames a second unpaced) and the baseline's. The filed prediction stands as written.
  The (frame, tile) lists are compared with the baseline's real-time run.
- **Amended before the runs (133, labelled):** with the prefetch, tiles come from the worker
  earlier than on the baseline, so the comparisons are:
  - (a) the fix held to the wall clock against the fix unpaced: identical (frame, tile) lists
    (probe144's `rocks` and `coll` events), issue 144's pace invariant on the fix;
  - (b) the fix against the baseline: at each frame's end, the same set of tiles ready within
    32 m of the car (issue 144's wait guarantees it on both), read as the same (frame, tile)
    lists of rocks loaded and collision tiles made, which depend only on that set.
  - A run counts only with `wait_missed` 0, on all four.
- **Amended before the runs (133, labelled): the load, and how the runs are judged.** Another
  session's training job on GPU1 started at 22:43, about 2 h, with CPU data loaders (25 to 35
  GiB of RAM, several cores), so its CPU load overlaps all four runs. The quiet rule covers GPU0,
  so the runs count. Each run's load average is recorded at its start.
  - (1) The filed absolute predictions stand as filed: under 5 waits over 50 ms, under 2 s in
    all, over 33.7 frames a second unpaced. The load makes the waits a stricter test. If only
    the rate fails, the result says whether the same-day baseline's unpaced rate also fell
    below 33.7.
  - (2) A relative line: the fix's waits over 50 ms at real time are at most a tenth of the
    same-day baseline's, and the fix's unpaced rate is at least the baseline's.

### The runs' result (2026-11-24, 22:54 to 23:00; one run each)

GPU0 alone (the other session's last process left it at 22:44:31; the quiet lead from then).
The other session's GPU1 training job loaded the CPU throughout. Load average at each start: 1.43,
6.15, 5.09, 5.95. Record: `/mnt/renegade/aeon/isaac-ex/c6d/i147` (`run147.sh`, `times.txt`, a
`.jsonl` and a log a run).

| run | waits over 50 ms | their total | all waits | longest | unpaced rate | wait_missed |
|---|---|---|---|---|---|---|
| baseline 46c09ec, real time | 47 | 14.18 s | 14.36 s | 809 ms | | 0 |
| fix 07bf74c, real time | 47 | 14.22 s | 14.37 s | 824 ms | | 0 |
| baseline 46c09ec, unpaced | 50 | 18.20 s | 18.40 s | 894 ms | 49.1 frames/s | 0 |
| fix 07bf74c, unpaced | 48 | 17.14 s | 17.36 s | 886 ms | 50.4 frames/s | 0 |

All four count (`wait_missed` 0). Rocks loaded 163 and collision tiles made 239 in each.

- (a) Fix held to the wall clock against fix unpaced: identical (frame, tile) lists, rocks and
  collision tiles. **Held.**
- (b) Fix against baseline: identical lists at real time. **Held.**
- Filed: waits over 50 ms under 5 (47) and their total under 2 s (14.2 s): **failed**. Unpaced
  rate over 33.7: **held** (50.4), and the same-day baseline also clears it (49.1).
- Relative: the fix's waits at most a tenth of the baseline's (47 against 47): **failed**. The
  fix's unpaced rate at least the baseline's (50.4 against 49.1): **held**.

So the fix changed nothing that matters. Both real-time runs wait at the same 47 frames, about
every 32 frames (frames 95, 130, 162, 194, 226, 257 and so on, 134 to 823 ms each). At 10 m/s
and 20 frames a second, 32 frames is 16 m, one tile (`TILE`). Each wait comes as the car crosses
into a new tile row. `tiles_near` takes a square of tiles about the car, so a new row of tiles
enters the frame end's 32 m reach at that frame. The fix asks for the tiles within the same
32 m, so it asks for that row at the same frame the frame's end waits for it. The look-ahead
along the corridors covers only the tiles within 6 m of the centreline ahead. The row's tiles
beside it get no lead, and a tile takes 134 to 823 ms to make here.

- **Proposed second version (prediction before its runs).** `_ahead` asks for the corridor tiles
  within `AROUND + TILE` (48 m) of the car, one tile row ahead of the frame end's reach in every
  direction: 1.6 s of lead at 10 m/s, against a tile's 134 to 823 ms. The tiles in that square
  that touch a corridor number about 15 to 30 on Haruna, under the layer's `max_tiles` (96).
  - **118's prediction:** the fix's real-time run waits over 50 ms at most 5 frames (the first
    frames' burst, frame 44, may stay), under 2 s in all. The (frame, tile) lists stay identical
    to the baseline's and between the fix's two paces. The unpaced rate stays at least the
    baseline's 49.1. Runs: the fix's pair (real time and unpaced), against today's baseline
    pair, under the same quiet rule, with the load recorded.
  - **The throughput check (133; before the runs).** Along the baseline's drive (its poses every
    4 frames, Haruna's rocks map), the corridor tiles entering the 48 m square number 4 per row
    (median), at most 10, and at most 47 are in it at once, under `max_tiles` 96. A row's work
    on the one tile worker is read from the baseline's own waits: a frame's end that waited for a
    row waited 134 to 823 ms, so a row takes at most about 0.8 s here. That is under the 1.6 s of
    lead one row gives at 10 m/s held to the wall clock, so one row is enough at real time and two
    rows (64 m) are not needed. Unpaced, the run goes
    about 2.5 times real time, so one row's lead is about 0.64 s of wall time, under the longest
    rows. The prediction for the unpaced run is therefore fewer waits than the baseline's 50, not
    under 5.
  - The 48 m set includes the beside-road column of issue 144: over the drive the frame end's
    32 m reach held 163 distinct corridor tiles, and the 48 m square holds them all (169). v1's
    "touches a corridor" already took the column. v1 missed in time (no lead), not in place.
  - Built: siw issue-147 26a3573 on 07bf74c (local). Runs: the v2 pair, real time and unpaced,
    against the baseline pair above (46c09ec, 22:54 and 22:58), under the same quiet rule.

### v2's result (2026-11-24, 23:03 to 23:06; one run each)

GPU0 alone (the quiet lead from 22:44:31; nothing on it between the runs); the other session's
GPU1 job loading the CPU. Load average at the starts: 13.48 (real time) and 4.33 (unpaced).

| run | waits over 50 ms | their total | all waits | longest | unpaced rate | wait_missed |
|---|---|---|---|---|---|---|
| baseline 46c09ec, real time (22:54) | 47 | 14.18 s | 14.36 s | 809 ms | | 0 |
| v2 26a3573, real time | **0** | 0 | 0.15 s | 0.3 ms | | 0 |
| baseline 46c09ec, unpaced (22:58) | 50 | 18.20 s | 18.40 s | 894 ms | 49.1 frames/s | 0 |
| v2 26a3573, unpaced | 29 | 9.38 s | 9.52 s | 1029 ms | 62.2 frames/s | 0 |

Rocks loaded 163 and collision tiles made 239, as in every run.

- Real time: at most 5 waits over 50 ms (0) and under 2 s in all (0.15 s): **held**, on one
  run, started at a load average of 13.48 against the baseline run's 1.43.
- The (frame, tile) lists: v2 at real time against v2 unpaced identical, and against the
  baseline identical: **held**.
- Unpaced: fewer waits than the baseline's 50 (29), and a rate at least 49.1 (62.2): **held**.
- The filed predictions: under 5 waits (0), under 2 s (0.15 s), over 33.7 frames a second (62.2):
  **held**. The relative line: at most a tenth of the baseline's waits (0 against 47) and a rate
  at least the baseline's (62.2 against 49.1): **held**.

The unpaced run still waits where a row's work outlasts its lead at 3.1 times real time, as the
throughput check said it would. Status: fixed by siw 26a3573 (with 07bf74c), once landed.
