# 142: since issue 134 the road's rocks load about 30 m later along the course

**Status:** open; a probe comes first (133). **Severity:** high until shown otherwise: a rock not
loaded when a wheel reaches it is silently missing from a study on rocks. **Found:** 2026-11-24,
scensim 118, issue 139's bisection.

## What happens

086 C6b's fixtures on fixture_c6b (raycast) count the rocks loaded as the car drives (a running
count, `rock_check`'s `loaded_max`). On siw 637b454 (issue 128's recheck) 80 rocks were loaded by
s 112.9 m; since issue 134 (3a4fcd7, by elimination: 31593ab, 4df3198 and 87591b4 all load the
same) the 80th loads at about s 143 m, and at loose_15's middle 100 against 130. Both reach the
same 253 by the boulder at s 400 m. No tile is dropped by issue 139's queue (0 in a logged run).
Rocks load within ROCK_REACH (32 m) of a car from ready tiles only, so a lag of about 30 m of
travel suggests tiles become ready only as the car nears them. 134 moved the tile's look (its
base and zones) into the worker, which may make each worker tile slower.

The fixtures' own rocks were there when needed (every case's measure equals 128's to the digit);
whether a placed rock near a wheel's path was ever missing is not known.

## The probe (planned, prediction first)

On siw 6c6a044 (before 134) and on main: for each rock, the car's s when it loads against the
rock's own s, and each tile's worker time. The key number is the least lead (the rock's s less
the car's at its load) over the rocks a wheel passes within 1 m of; under the car's stopping
distance at its speed, rocks are being missed.

## The probe as built (before the runs)

C6b's fixtures on fixture_c6b (raycast, the whole set) through a wrapper of `fixture_drive`
(`probe142.py`) that logs every rock tile loaded into the rock data (`RockStream._load`: the
tile, its rocks' positions, the car's position then), the car's position every frame, every tile
the worker made (its key and worker time) and every tile made on the caller's thread instead.
Run on siw 6c6a044 (before 134) and on siw main 56b8e39, GPU0 quiet and the host otherwise idle
(the loading depends on the worker's pace). A rock's lead is its s along the course less the
car's (its rear axle, `fixture_drive`'s origin) when its tile loaded; a rock is in a wheel's path
when it lies within 1 m of a wheel's line (the car's lateral place at the rock's s, plus or minus
half the tread, 0.83 m). The car's stopping distance at 11.1 m/s, braking at 7 m/s^2 after
0.5 s, is about 14 m (5.6 + 8.8).

- **118's prediction:** the worker's time a tile rose with 134 (its look is now made there): at
  least 1.5 times 6c6a044's median. On 6c6a044 every rock in a wheel's path loads at least 25 m
  ahead of the car. On main the least lead over those rocks is under 14 m: rocks are being
  missed in effect, since a wheel can reach one before the car could stop for it. Tiles are made
  on the caller's thread on main and not, or far less, on 6c6a044.

### The probe's result (2026-11-24)

C6b's fixtures (raycast) through `probe142.py`, GPU0 quiet through both runs (load 0.7 and 1.8),
on siw 6c6a044 (before 134) and siw main 56b8e39. 206 rocks loaded in each, 18 of them in a
wheel's path. A case start is where `fixture_drive` places the car for the next case (three in
the run); the first case's start, s 43 m, is at the run's beginning.

| | 6c6a044 | 56b8e39 |
|---|---|---|
| worker time a tile, median (p90) | 47 ms (308) | **379 ms** (475) |
| tiles made on the caller's thread | 0 | 0 |
| in-path rocks loaded while driving: leads | 35.7 to 46.6 m | **14.1 to 18.0 m** |
| in-path rocks loaded at the next case's placing: leads | 29.0 m and more | **0.0, 1.2, 11.0, 12.2** m, then 16.1 and more |
| the first case's rock at s 58 m | 13.3 m | 13.3 m |
| all rocks: least lead, median | -0.3 m, 37.2 m | -18.2 m, 14.2 m |

- **Since 134 a worker tile takes eight times as long** (47 to 379 ms median). The worker makes
  about 2.6 tiles a second now. At 11.1 m/s the tiles ahead come about as fast as that, so the
  rocks load about 20 m later than before, all of them in the end.
- **While driving, no in-path rock was missed at this speed**, by a thin margin: the least lead
  was 14.1 m, against a stopping distance of about 14 m at 11.1 m/s. At a higher speed the
  margin would go: by estimate (two or three new tiles every 16 m of travel), the tiles ahead
  come faster than 2.6 a second from about 15 to 20 m/s, and Haruna's course allows 60 km/h
  (16.7 m/s). Not measured. (Corrected after the results: first written as "Haruna's study
  speeds reach 80 km/h", a figure from a code comment on R3's test road.)
- **At a case start the car is placed where its rocks are not loaded yet**: four in-path rocks
  loaded within 0 to 0.33 s of the placing with leads of 0 to 12 m. The car stands there, so it
  can still stop; a car placed at speed (a teleported ego, a scenario's start) would not.
- **118's prediction:** the worker's time up at least 1.5 times **held** (8.1 times); a least lead
  on main under 14 m **held** (0.0 m), but only at case starts, with the car at rest, not while
  driving (14.1 m); every in-path rock at least 25 m ahead on 6c6a044 **failed** (13.3 m, the
  first case's start, the same on both); tiles made on the caller's thread on main **failed**
  (none on either).

So 142 is real and grows with speed. The cause is the worker's time a tile; the cure is to make
the look's part of it cheap again (or a second worker), and its proof a lead over the in-path
rocks at Haruna's speeds at least the stopping distance with a margin, written before the run.

## The cause and the fix's bar (before the fix)

The worker's time a tile, split offline on fixture_c6b's record (a tile that touches the road):
`_uvs` 213 ms, `_make` 27, `_look` 13, rock placement 58. From the probe's worker log: a tile the
road does not touch took 44 ms before 134 and 424 ms after; one it touches 299 and 316 ms.
Before 134 `_make` skipped a corridor that cannot reach the tile (the centre test of
`Detail.touches`); 134's `_uvs` projects every tile's 103 041 points on every corridor, and most
tiles prefetched ahead do not touch the road.

The bar (133, written before the runs; the first one mixed physics with perception, issue 143):

- **while driving**, every in-path rock's prim and collider exist at least (the prim's creation
  latency times v) plus 10 m ahead of the car, at up to 60 km/h (Haruna's course limit);
- **no regression**: at haruna_down's speeds (45 to 50 km/h) the in-path leads are back to at
  least pre-134's, 35 m or more;
- **at a case start** (a car placed), every in-path rock within reach exists before the first
  physics step.

## The fix, step 1: the skip again (before its test runs)

`Detail._uvs` projects a corridor on a tile only when the corridor can reach it (`_reaches`: the
centre test `_make` used before 134). It is exact: a sample's distance to the centreline differs
from the centre's by at most its own distance from the centre, under half a 16 m tile's
diagonal (11.3 m), and the test skips only a centre farther than the reach plus 16 m, so no
skipped sample lies within reach (`near` is all false, and with it the base, the zones and the
rocks). `test/test_issue_142.py`: tiles on and up to two tiles off a winding road with rocks and
potholes, and a second corridor, against the full projection, bit for bit (heights, base, zones,
the rocks placed); a tile off the road at under a quarter of the CPU time of one on it; the skip
is the centre test and agrees with `Detail.touches` on every tile.

- **118's prediction:** with the skip, all three pass; on siw 56b8e39 (no skip) the identity
  passes (the same code path) and the time test fails (the off-road tile costs about what an
  on-road one does).

### Step 1's test result (2026-11-24)

siw `issue-142` c6ec980: the three tests pass (22 s). On 56b8e39's code the identity passes (the
same projection) and the time test fails, three off-road tiles costing 1.04 s of CPU against
0.88 s for three on it; the centre-test test fails there too (no skip). The siw suite passes
(459 tests). **118's prediction: held.**

## The worker's throughput against speed (before the run)

`throughput142.py` (no Isaac, CPU only): a virtual car drives a record's centreline at a fixed
speed in real time, asking `Detail.prefetch` every 1/60 s for `RoadLayer._ahead`'s tiles through
the real TileProcess, built as `RoadLayer` builds it; a road tile's lead is its centre's u less
the car's u when it became ready. Haruna's record (C6b's *rocks* map, u 100 to 1100 m) at 8.3,
11.1, 13.9, 16.7 and 20 m/s, and fixture_c6b's at 11.1 m/s, on siw 87591b4 (main's tile code,
no skip) and c6ec980 (the skip), the host otherwise idle.

- **118's prediction:** on fixture_c6b the skip brings the worker's median back under 60 ms and
  the least road-tile lead to 30 m or more. On Haruna, whose winding road touches most tiles
  prefetched ahead, the skip changes little: the worker's median stays near 300 ms (the
  projection, 213 ms of it), about 3 tiles a second, and the least road-tile lead is negative
  from 13.9 m/s up on both codes. If so, step 2 is a cheaper projection: culling the segments
  per block of a tile rather than per tile (exact, as issue 128's), not a second worker.

### The throughput measurement's result (2026-11-24)

Host idle (load 0.4 and 1.1 at the starts). Leads in m; tiles a second made by the worker.

| record, speed | 87591b4: median ms, tiles/s, least lead (p05) | c6ec980 (skip): the same |
|---|---|---|
| fixture_c6b, 11.1 m/s | 298, 1.74, 25.6 (31.7) | 297, 1.74, 26.2 (32.4) |
| Haruna, 8.3 m/s | 385, 1.82, -45.3 (-16.5) | 345, 1.82, -28.9 (-2.9) |
| Haruna, 11.1 m/s | 375, 2.29, -110.8 (-69.1) | 342, 2.44, -60.2 (-44.7) |
| Haruna, 13.9 m/s | 376, 2.32, -251.5 (-194.8) | 329, 3.15, -130.8 (-115.2) |
| Haruna, 16.7 m/s | 402, 2.32, -204.6 (-168.3) | 322, 3.43, -207.7 (-161.9) |
| Haruna, 20 m/s | 370, 2.42, -249.3 (-156.8) | 129, 4.31, -359.5 (-172.1) |

- **118's prediction:** on fixture_c6b the skip bringing the worker under 60 ms and the least lead
  to 30 m **failed** (297 ms, 26.2 m: in this driver every tile prefetched ahead on the straight
  fixture course touches the road, unlike the Isaac probe's 80 off-road tiles, which something
  else in the world asks for, not yet found); on Haruna the median near 300 ms **held** (322 to
  402, 129 at 20 m/s with the skip), about 3 tiles a second **held** (1.8 to 4.3), and the least
  lead negative from 13.9 m/s up **held**, but it is negative at 8.3 and 11.1 m/s too, with the
  worker not saturated (1.8 tiles a second at 8.3 m/s).
- So on Haruna the lack is not only the worker's pace. `RoadLayer._ahead` prefetches along a
  straight line from the car's heading (max(48 m, 4 s v), a point every 8 m, 6 m around). On a
  road of hairpins that line leaves the road within a few tens of metres, and the road's tiles
  round the bend are asked for only once the car has turned. This is older than 134.

- **118's prediction for the next run** (the same driver on c6ec980, Haruna, the same speeds,
  `_ahead` replaced by points along the centreline from the car's u to u + max(48 m, 4 s v)):
  the least road-tile lead is at least 0 at 8.3 and 11.1 m/s and the 5th percentile at least
  20 m at 13.9 m/s; above that the worker's pace limits it (negative leads at 16.7 and 20 m/s).

### The prefetch along the centreline (2026-11-24)

The same driver on c6ec980, Haruna, the prefetch's points along the centreline by u instead of
the heading's line (host idle):

| speed | worker median, tiles/s | least lead (p05), m |
|---|---|---|
| 8.3 m/s | 395 ms, 1.16 | 36.5 (49.6) |
| 11.1 m/s | 377 ms, 1.55 | 24.3 (42.9) |
| 13.9 m/s | 364 ms, 1.96 | 13.4 (28.5) |
| 16.7 m/s | 363 ms, 2.37 | 5.6 (15.0) |
| 20 m/s | 360 ms, 2.54 | -48.1 (-43.3) |

The worker makes 140 tiles over the 1000 m instead of 207 to 227: the line no longer asks for
the hillside's. **118's prediction:** least lead at least 0 at 8.3 and 11.1 m/s **held** (36.5,
24.3); p05 at least 20 m at 13.9 m/s **held** (28.5); negative at 16.7 m/s **failed** (5.6 m,
positive); negative at 20 m/s **held**.

Against 142's bar this is not enough: at haruna_down's 50 km/h (13.9 m/s) the least tile lead,
13.4 m, is under the 35 m of pre-134 (a rock loads only after its tile), and at 60 km/h 5.6 m
leaves no room for the prims' creation and the 10 m. Step (iii), a cheaper projection, is due.

### The off-road tiles in the Isaac probe (133's question, a lead, not yet shown)

Of the off-road tiles the worker made in the Isaac probe on 6c6a044, 64 of 86 were made with the
car under 0.5 m/s (on main 27 of 78, the rest finishing late, after the car moved on). `_ahead`
aims its 48 m line along the car's velocity, `(vx, vy) / speed`: at rest that is the direction
of a near-zero velocity's noise, so a standing car asks for tiles 48 m off in changing
directions (case starts, and the 50 s at the boulder). To be shown by logging `_ahead`'s keys
with the car at rest; the corridor prefetch of step (ii) replaces this line where a corridor is
within reach.

## Step (iii), a cheaper projection (before the prototype is timed)

`Corridor.uv` culls the segments per call (issue 128): a whole tile keeps every segment that can
be nearest to any of its 103 041 samples (106 of 3054 on Haruna's record), and each kept segment
is a pass over all the samples. Culled per block of the tile (8 x 8 blocks of about 40 x 40
samples), each block keeps only the segments that can be nearest to its own samples, by the same
exact rule, and visits them in order.

- **118's prediction:** bit for bit the same u, v and near as today's on every tile of both
  records (fixture_c6b and Haruna); `_uvs` on a Haruna road tile at least 3 times faster.

### Step (iii)'s prototype, timed (2026-11-24)

`Corridor.uv` with 2 m blocks, each culled among the tile's own candidates (a block's nearest
segments are among the tile's; the bound over that subset is still an upper bound, so the cull
stays exact), and a block's segments taken at once as a (points x segments) array, the first
nearest by `argmin` (the loop's strict `<` in order keeps the first too). On 12 Haruna and 11
fixture_c6b road tiles: u, v and near bit for bit the per-tile cull's on all 23; a tile 227 ms
to 63 ms on Haruna, 246 to 66 ms on fixture_c6b (3.6 and 3.7 times). Culling per block alone
(the loop kept) gave 2.4 times. A Haruna 2 m block keeps 21 segments on average (36 at most) of
the tile's 91. **118's prediction: held** (at least 3 times, bit for bit).

## Step (ii), the prefetch along the corridors (before its test runs)

`RoadLayer._ahead`: for every corridor whose reach the car is within, the points along its
centreline from the car's u to u + max(REACH, LEAD_S v) (or u less that, the corridor's
direction taken from the car's heading: its velocity above 1 m/s, its yaw below, so a standing
car no longer aims at a velocity's noise); the heading's straight line only when no corridor is
within reach. Tests (no Isaac): on a two-corridor record (a junction) the keys follow both
corridors and stay on them; a car off every corridor gets today's line; a standing car's keys
do not change with a velocity's noise; a hairpin's tiles round the bend are asked for before
the car turns.

- **118's prediction:** all pass, and on siw c6ec980 (today's `_ahead`) the hairpin and the
  standing-car tests fail.

### Steps (iii) and (ii) in siw (2026-11-24)

siw `issue-142`: 80df3f6 (the blocks) and 47de0b2 (the prefetch along the corridors), on
c6ec980 (the skip). The siw suite passes (466 tests). Issue 128's test reference is now the
plain loop over every segment (`_uv` with no cull), and the blocked `uv` equals it bit for bit,
ties included.

- **118's prediction for step (ii)'s tests:** all pass with the change **held**; on c6ec980 "the
  hairpin and the standing-car tests fail" **held**, but the two-corridor test failed there too,
  which the prediction did not say (today's straight line follows the first corridor only); the
  off-corridor test passes on both, as it should.

## The throughput with all three steps (before the run)

The driver now calls `RoadLayer._ahead` itself (the car's yaw along the centreline); Haruna, u
100 to 1100, 8.3 to 20 m/s, siw 47de0b2, host idle.

- **118's prediction:** the worker's median a tile at most 180 ms (the projection 63, the
  heights 27, the look 13, the rocks' placement 58); the least road-tile lead at least 35 m at
  13.9 m/s (pre-134's, the no-regression bar), at least 20 m at 16.7 m/s, and at least 0 at
  20 m/s.

### The throughput with all three steps (2026-11-24)

| speed | worker median, tiles/s | least lead (p05), m |
|---|---|---|
| 8.3 m/s | 248 ms, 1.16 | 49.5 (53.0) |
| 11.1 m/s | 240 ms, 1.55 | 41.9 (51.8) |
| 13.9 m/s | 234 ms, 1.97 | 34.3 (54.9) |
| 16.7 m/s | 240 ms, 2.39 | 26.4 (44.7) |
| 20 m/s | 237 ms, 2.91 | 11.0 (40.4) |

**118's prediction:** the worker's median at most 180 ms **failed** (234 to 248); at least 35 m at
13.9 m/s **failed** (34.3); at least 20 m at 16.7 m/s **held** (26.4); at least 0 at 20 m/s
**held** (11.0). A rock loads once its tile is ready and within 32 m of the car, so a tile ready
about 40 m before its centre adds no delay: at 13.9 m/s and up the worker still costs some.

A Haruna road tile with its rocks, split offline: 417 ms in all, `_uvs` 103, `_make` 87 (most of
it the roughness fields, made once and kept), `_look` 17, and **the rocks' placement 212**: it
projects 580 small sets of points, each culling over all 3054 segments (0.5 ms a call).

## Step (iv): a segment grid for the cull (before it is timed)

`Corridor._candidates` takes its first bound from the segments in the grid cells (16 m) around
the points instead of from every segment, then the gap test over the segments in the cells
within that bound. The set kept is a superset of today's (the bound can only be larger), and it
holds every segment that can be nearest; the loop's order is kept, so u, v and near are the
same bit for bit.

- **118's prediction:** bit for bit on the 23 road tiles and on every rock's placement of 16
  Haruna tiles; the rocks' placement of a Haruna tile from 212 ms to under 60 ms, the whole tile
  under 250 ms (first make, the roughness fields included).
