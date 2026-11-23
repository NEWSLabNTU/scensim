# 139: the road's tile process deadlocks under a burst of tile requests

**Status:** open; fix planned after issue 137's probe (133). **Severity:** high: a hung world
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
