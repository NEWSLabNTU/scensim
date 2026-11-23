# 134: the road's render mesh remakes its empty tiles every frame, and makes new tiles on the frame's thread

**Status:** fixed, landed as siw 31593ab (the live check passed). **Severity:** high: an Isaac run with a road
layer on a winding record takes seconds a step and times out (086 C6b's Haruna budget).
**Found:** 2026-11-24, scensim 118, 086 C6b's diagnostic.

## What happens

086 C6b's diagnostic (haruna_down on Haruna's record without rocks, main d653aabd with issue
128's fix, GPU0 holding only the run's own processes): the world server's tick was 1855 ms p50
and 2029 ms p95, and SSv2 timed out. The step split (logged every 20 steps) put it all in the
frame-end flush: 876 ms at 1 s of sim time, 1.8 s from 2 s on, 2.5 s by 18 s. Physics was 2.5 to
3.9 ms a step, the render 10 to 11 ms, the road layer's per-substep work 4 ms, with 2 render
products.

## The cause

`road_layer.MeshStream.update`, the road's render mesh, once a frame:

- (A) A tile in reach whose grid holds none of the road (no quad with every corner in a
  corridor's reach) hit `continue` before it was stored, so every frame it made
  `Detail.surface_tile` and `Detail.zones_tile` again, a full `uv` pass each. Offline on Haruna's
  record, 18, 33 and 21 tiles lie in reach at three stations, of which 6, 1 and 7 hold no road;
  the two calls cost 0.8 to 1 s a tile. That is the flush's 1.8 to 2.5 s.
- (B) A new tile's base road and zones were made on the frame's thread, about 0.9 s a tile on
  Haruna, although the tile worker had just projected the same grid for the heights. The
  collision tiles (`DetailColliders`, issue 119) read `surface_tile` the same way.

(A) has been there since 066 R3; a straight fixture course has few empty tiles in reach, and
no world-server run loaded a road layer on a record before 086 C6b.

## The fix (siw issue-134)

- (A) A tile without the road is stored as `None` and not looked at again while in reach.
- (B) `Detail._uvs` projects a tile once. Its heights (`_make`), base road and zones (`_look`)
  come from that projection, in the worker; the worker process ships the look with the heights.
  `surface_tile` and `zones_tile` read the look, kept and evicted with its tile: float64 base
  and int8 zones, 0.93 MB a tile at n 320 (Haruna's road layer keeps 96 tiles: up to 89 MB). A
  look missing for a made tile is made on the caller's thread and counted (`look_fallbacks`).
- The step split (`SCENSIM_STEP_SPLIT_EVERY`, and the slow-step warning) lands with it, logging
  the look fallbacks and the tile waits over 1 ms on the frame's thread.
- `test/test_issue_134.py`: the look bit for bit as before (surface and zones on a winding,
  rough corridor with potholes), from a worker process too, evicted with its tile, a read under
  a quarter of the making's CPU time, and an empty tile looked at once across five frames.

## The live check (bars and prediction before the run)

The diagnostic again: haruna_down on Haruna's record without rocks, the fix in the workspace,
GPU0 empty for 10 min before and holding only the run's own processes during it (the 15 s log),
the step split every step. The bars:

- tick p50 at most 55 ms, and tick p95 at most 100 ms (C5's Haruna without a road layer:
  p50 45.1 to 45.3, p95 51 to 89);
- the largest flush of any step after the ego's first second at most 250 ms;
- look fallbacks 0 at the run's end. The tile waits over 1 ms are reported. If either is not
  rare, the cure is the worker making the tiles ahead of reach (133), and this says so.

- **118's prediction:** all three bars pass. Tick p50 45 to 50 ms, p95 under 90 ms, the
  largest flush 50 to 150 ms (a new tile's mesh and collider written to the stage), look
  fallbacks 0, and tile waits only in the first second.

### The live check's result (2026-11-24)

siw issue-134 31593ab in the workspace, haruna_down on Haruna's record without rocks, 03:17 to
03:25; NAS "2026-11-24 issue 134 road render mesh (118)". GPU0 held only the run's world server
and Autoware's container throughout (the 15 s log, 28 and 27 samples). The run passed (its pose
judges too) and the prediction holds; every bar passes:

| bar | measured | limit |
|---|---|---|
| tick p50 | 49.7 ms | 55 ms |
| tick p95 | 80.8 ms | 100 ms |
| largest flush after the ego's first second | 59.2 ms (sim 136.40 s) | 250 ms |
| look fallbacks at the end | 0 | 0 |

Over 7052 logged steps the flush was 0.10 ms p50 and 12.2 ms p99. One tile wait over 1 ms
happened, at 0.1 s (the first tile at the spawn), and none after, so the worker keeps ahead of
reach and no change of cure is needed. No step was slow (over 500 ms). The largest step, 340 ms
at sim 136.45 s, was not the flush; it is within the p95 bar and reported here. Before the
fix the same run was 1855 ms p50 and 2029 ms p95 and timed out.
