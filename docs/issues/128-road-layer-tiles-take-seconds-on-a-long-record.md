# 128: the road layer's tiles take seconds on a long record, and an Isaac run stalls at its first frames

**Status:** fixed on siw `issue-128` (2f71238), not landed. **Severity:** high: every Isaac
run whose map has a road layer on a long per-station record (086 C5's records: a station every
0.5 m) stalls in its first frames, long enough for the bridge to give up, so the scenario ends
in error. **Found:** 2026-11-23, scensim 118, 086 C6b's Haruna budget.

## What happens

086 C6b's first Haruna budget run (scensim main 7cc930a0, map `rocks`: C5d's rebuilt Haruna
with a map-dir `road_detail.yaml` on its record, 3055 stations): the world server's second step
took **28.7 s** ("slow step at sim time 0.10: 28749 ms (commands 7, physics and render 28733,
publishing 9)"). The bridge gave up on Step after 10 s and exited 75, and the run ended in
error at 0.1 s of sim time.

## The cause

`road_detail.Corridor.uv`, which projects a tile's points onto the corridor's centreline, looped
over every segment of the centreline for every point. Its comment said "segments: few near any
tile", but nothing culled them. A 16 m tile has 321 x 321 points. On Haruna's record (3054
segments) `uv` took **7.0 s** a tile, and `Detail._make` 6.5 to 8.6 s, rocks or not. The first
tiles around a spawned car are made before the road under it is known, so the first frames
waited for them: minutes in all. The loop has been there since 066 R3 (7d60360). It grew costly
with 086 C5's per-station records, whose centreline has a point every 0.5 m. 066's corridors had
a few dozen points.

The first suspect was issue 123's change (the rock pool grouped at the first frame). Three
probes ruled it out: one car (`fixture_cost --follow`) on the `rocks` map, the first frames'
wall time:

| code | frame 0 | frame 7 | later |
|---|---|---|---|
| main 7cc930a0 (siw 458d4cf) | 786 ms | 82.4 s | 6 to 138 s about every 30 frames |
| the same, the pool grouped at load (3 ms) | 779 ms | 85.2 s | the same |
| siw fb5f20c, main before issue 123 | 782 ms | 88.7 s | the same |

## The fix (siw 2f71238)

`Corridor._candidates` keeps only the segments that can be nearest to some point of the call.
D, the least over the segments of the farthest corner of the points' bounding box from the
segment, bounds every point's nearest distance (distance to a segment is convex, so its maximum
over the box is at a corner). A segment whose bounding box lies farther than D from the points'
box cannot be nearest to any of them, so it is dropped (strict >, so ties stay in). The kept
segments are visited in order with their own indices, so u, v and near are the full loop's, bit
for bit.

- Haruna's tiles: `Detail._make` 0.30 to 0.52 s (6.5 to 8.6 s before). `uv` on the test's
  3055-station tile is 0.29 s, keeping 106 of 3054 segments. The result is identical to the
  full loop on both maps' records.
- `test/test_issue_128.py`: tiles along and off a 3000-station winding corridor and a hairpin
  tie, against the full loop, bit for bit; a tile keeps under 200 segments; a 3055-station
  tile's `uv` under 1 s. This test is the gate's guard, since the gate runs no Isaac.
- The live guard, `fixture_cost --guard-ms`, exits 1 when a frame of the first 120 takes
  longer than the bound, or a rock touches the base road (issue 123's self-check). With the
  fix, one car on Haruna (a codec job of another session shared GPU0): the first frames'
  largest 3.9 s on `rocks` and 2.4 s on `none`, base contacts 0. The whole run took 30 s,
  more than 10 min before. The guard's bound is 10 s, the bridge's Step timeout.
- `fixture_cost --follow` and `--road` (086 C6b's budget) land with it, because the guard
  needs them on a winding map's own record.

## Issue 123's result, rechecked on the fix (before the run)

The C6b fixture set on fixture_c6b, raycast and sweep, siw `issue-128`. aib is siw's pin
(4e8d684), not ff5e72b as in 086's rerun, because the drive needs aib's `app_exit` (issue 118).

- **118's prediction:** the self-check finds 0 base contacts in both queries, and each case
  keeps its pass or fail from 086's rerun: embedded_15 fails J, loose_15 passes in raycast and
  fails in sweep, loose_8 fails both, boulder_35 passes. loose_15's raycast travel may differ,
  because its outcome is sensitive to the start (issue 122).

### The recheck's result (2026-11-24)

siw `issue-128` 637b454, aib 4e8d684; NAS "2026-11-24 issue 128 road layer tiles (118)". The
prediction holds. The self-check found 0 base contacts in both queries. Every case kept its
verdict, and every measure equals 086's rerun to the last digit printed:

| case | raycast | sweep |
|---|---|---|
| embedded_15 | J 303.1, fails | J 305.0, fails |
| loose_15 | moved 1.674 m (5.5 m/s), passes | 2.5 cm (1.34 m/s), fails |
| loose_8 | 1.1 cm, fails | 5.0 cm, fails |
| boulder_35 | stops 0.35 s after the plate reaches it, passes | the same, passes |
| placement | as before (fails as written, passes as amended) | the same |

The whole set ran in 2.5 min (both queries), against 25 min before the fix.

## Measurements that may carry the cost

No world-server run on a record loaded a road layer before this: C5's and C5d's Haruna runs
(including C5's clean pairing, `tick_p95_ms` 51 to 89 ms) and the fixture world-server runs read
the record from `course/`, which the world server does not load. Their logs show a surface map
and no road detail. They are not affected.

The drives that load the record themselves (`fixture_drive`, `fixture_cost`, about 1020
stations) paid about a third of Haruna's cost a tile, mostly in the tile worker before the
fixtures. Their timing lines may be inflated: C6a's R1 cost line, C6a2's cost lines, and the
119/120 cost table (p50 and p95, with and without colliders). All of them were reported, not
judged, and no verdict depends on them. Physics results are unaffected unless a tile was
missing when a wheel reached it; the recheck above tests that. No rerun is planned.
