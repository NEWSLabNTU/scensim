# 139: the road's tile process deadlocks under a burst of tile requests

**Status:** fixed, landed as siw 87591b4 in siw main 56b8e39 (scensim main 75626c3b); the
worker's traceback at shutdown is a follow-up, below. **Severity:** high: a hung world
server, with no error and no exit, is the worst kind of failure. **Found:** 2026-11-24, scensim
118, issue 137's probe on 086 C6d's *rough_none* map.

## What happens

The probe (`fixture_cost`, one car, siw 31593ab) wrote nothing after 06:23:55. It was alive
at 26 % CPU with 2.3 GB on GPU0, and both its main thread and its road tile worker
(`python -m scensim_isaac_world.road_detail --worker`) were asleep in `pipe_write`. It was
stopped by its process group after about 17 minutes.

## The cause

`road_detail.TileProcess`: `submit` writes a tile's key to the worker's stdin while holding
`self.lock`, and the reader thread takes the same lock after each result. A result (the heights
and, since issue 134, the look: about 1.7 MB) is far over a pipe's 64 KB, so the worker blocks
writing it until the reader drains it. If the main thread is then blocked writing a key, with
the stdin pipe full (about 2000 keys queued), the reader waits for the lock, the worker waits for
the reader, and the main thread waits for the worker. It takes a burst of tile requests to
fill the stdin pipe; a car thrown tens of metres (issue 137) is one. The lock design predates
134; 134's larger results fill the stdout side only a little sooner.

## The fix (planned, 133)

No pipe write while holding the lock (a writer thread fed by a queue), and a bound on the
outstanding submissions, with back-pressure or stale keys dropped. The test: a fake worker
whose results exceed the pipe buffer, under a burst of 3000 keys; it hangs on today's code
(guarded by a timeout) and passes after the fix. Its own siw commit and its own landing.

## The fix as built (before the test is run on it)

- `TileProcess.submit` writes nothing: it records the job and queues the key, under the lock,
  and returns. A writer thread takes keys from the queue and writes them to the worker outside
  the lock. The reader thread still takes the lock only to pop a finished job.
- The bound: at most MAX_IN_FLIGHT (2) keys written and not yet answered, so the worker always
  has its next key and the pipes never hold a backlog, and at most MAX_QUEUED (64) keys waiting.
  A submission past that drops the oldest waiting key, whose future fails ("dropped: stale",
  set by the writer thread, never inside `submit`), and `Detail` then makes that tile itself if
  it is still wanted (`tile_of`'s existing path for a failed job). A car's newest requests are
  the ones near it, so the oldest are the stale ones.
- A second submission of a key already waiting or in flight returns that key's future (before,
  it replaced the first in `jobs`, and the first never completed).
- `Detail.prefetch` calls `submit` under its own lock, and the done-callback `_made`, run on the
  reader thread, takes that lock: with a `submit` that never blocks, that wait is bounded too.

The test (`test/test_issue_139.py`): the worker replaced by a fake that answers each key with
1.5 MB, 5 ms apart; a burst of 3000 keys of about 30 bytes each (90 KB, past the 64 KB pipe),
through `TileProcess.submit` and through `Detail.prefetch`, each in a thread joined with a 20 s
timeout.

- **118's prediction:** on siw 4df3198 both hang, and the test fails at its timeouts. With the
  fix both bursts return within 1 s, every future completes (a result or "dropped"), the newest
  64 keys are answered with results, and `Detail.pending` is empty when they are done.

### The test's result (2026-11-24)

- **On siw 4df3198:** both bursts hung, and both tests failed at their 20 s timeouts ("the burst
  hung"). The test that a key asked twice shares its future also failed: the second
  submission made a second future.
- **With the fix (siw issue-139 e9d690a):** the four tests (the two bursts, the shared key, a
  submission after shutdown failing at once) passed in 1.3 s, three runs out of three. The
  newest 64 keys were answered with results, the dropped ones failed "dropped: stale", and
  `Detail.pending` was empty. The whole siw suite passed (454 tests, with ROS for the launch
  tests).
- **118's prediction: held.**

## The rocks loaded at embedded_15 (133, before the runs)

C6b's fixtures load fewer rocks at embedded_15 since issue 128's recheck: at most 66 loaded and
44 prims, against 80 and 48 (siw 637b454), the same with or without issue 140's offset. 133's
worry: if 139's queue drops a tile that is still wanted and nothing asks again, rocks near the
car go missing. Between 637b454 and 87591b4 lie issues 132 and 134 (31593ab), 137 (4df3198) and
139 (87591b4). Three raycast runs of the fixtures, the same map: on 31593ab, on 4df3198, and on
87591b4 with every drop logged (its key and time, and whether the tile was made later).

- **118's prediction:** no tile is dropped in the whole run: the only caller that asks for tiles,
  `RoadLayer.before_substep`, prefetches those ahead of the car (about ten keys a step, under 64
  waiting). The change is issue 134's (31593ab already loads 66): 134 changed what comes back
  with a tile and when a tile with no road is taken as empty, which is where the rock layer looks
  for its rocks. 4df3198 and 87591b4 load 66 as well.

### The bisection's result (2026-11-24)

C6b's fixtures, raycast, fixture_c6b, GPU0 quiet through all three runs:

| siw | embedded_15: loaded, prims at most | the cases' measures |
|---|---|---|
| 637b454 (128's recheck) | 80, 48 | as recorded in issue 128 |
| 31593ab (132, the step split, 134) | 66, 44 | 128's to the digit |
| 4df3198 (+ 137) | 66, 39 | 128's to the digit |
| 87591b4 (+ 139), drops logged | 66, 39 | 128's to the digit |

- **No tile was dropped** in the 87591b4 run (0 drops logged). 139 is not the cause.
- **The change is issue 134's** (3a4fcd7): it is already in 31593ab, and the other two commits in
  637b454..31593ab cannot move it (0beb150 changes a test, 6c6a044 the world server's step
  logging, which `fixture_drive` does not use). By elimination; 3a4fcd7 was not run alone.
- **The same rocks load, later.** The rocks loaded is a running count; both codes reach 253 by
  the boulder. Along the course the new code lags: 80 rocks at s 112.9 m before, at about
  s 143 m now; at loose_15's middle 130 against 100. With rocks loaded within ROCK_REACH (32 m)
  of a car on ready tiles only, a lag of about 30 m of travel says some tiles became ready only
  as the car neared them. Whether any rock near the car's path was missing when a wheel reached
  it is not shown by these counts.
- **118's prediction: held** (no drops; 134's; 4df3198 and 87591b4 at 66).

## Follow-up: the worker's shutdown writes a traceback (2026-11-24, from issue 145)

Every one of issue 145's drives (six on 637b454, 87591b4 and 56b8e39) ends with the tile
worker's `BrokenPipeError` in `pickle.dump`, in `road_detail._worker`. The app has closed the
worker's stdout by then, and the worker was still writing a tile's result. It comes after the
drive's summary line, so no measure or verdict depends on it. But a clean shutdown should write
nothing: the worker should end quietly on a closed pipe (its stdin's end is already its signal
to stop). The fix is not yet built.
