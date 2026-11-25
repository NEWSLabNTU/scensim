# 166: SSv2's spline heading reverses where a centreline's point spacing changes

**Status:** open (241; numbered by 133, 2026-11-25). **Severity:** to judge: a lane position's
heading 180 degrees off over a few centimetres, on many lanelets of Town05 and some of Town01.
**Found:** 2026-11-25, scensim 241, resolving a Town05 lane anchor for 092 K13's first search
(`west_avenue`: lanelets 105401 to 3337, maps dataset v2026.11f): the resolve reported a heading
error of 3.14 rad. The anchor is held (133) until this is settled.

## What happens

A lane anchor's heading table is SSv2's spline heading along the lane (`scensim_batch`'s port of
SSv2's `CatmullRomSpline`, 092 K2.6). On `west_avenue` the heading goes to about 0 rad on a
westbound lane (about 3.14 rad) for a few centimetres: lane s 0.055 to 0.076, 24.00 to 24.05,
25.12 and 73.22, among others. The centreline's points never step backward; the reversal is the
spline's. Sampling every 5 mm, 350 of Town05's 1018 lanelets and 37 of Town01's 300 have a
heading change of more than 90 degrees between samples (Town01's `west_street`, lanelet 6583,
has none; its resolved error is 0.00099 rad).

## Why, as far as known before the test

SSv2's spline (`common/math/geometry/src/spline/catmull_rom_spline.cpp`) is the uniform
Catmull-Rom: one cubic per pair of control points, parameter 0 to 1 whatever the points'
distance, the tangent at a point half the chord between its neighbours. Where a short segment
follows long ones (Town05's centrelines step from 0.25 m to 0.015 m between points), the tangent
at the short segment's ends is far longer than the segment, the cubic overshoots and comes
back, and its tangent reverses over that stretch, even on a straight line. A centripetal
Catmull-Rom does not. The port uses the same coefficients as SSv2, term for term.

**Prediction, before the test:** SSv2's own spline reverses at the same s with the same heading
as the port, to rounding: the port is faithful, and the behaviour is SSv2's.

## The test

A gtest in the SSv2 fork builds a `math::geometry::CatmullRomSpline` from lanelet 105401's
centre points (as `map_export` takes them, lanelet2's `centerline()`) and reads its heading at
s 10.0 (expected about 3.137), 0.06 and 24.02 (the port: about 0), and compares each with the
port's.

## Result (2026-11-25): SSv2 reverses, exactly as the port does

The probe (`test_issue_166_probe.cpp`, in a scratch worktree of the SSv2 fork at 31b12c5fc, not
committed; built against the `geometry` package alone) gives SSv2's heading equal to the port's
to the last bit at every s tried:

| s (m) | SSv2's heading (rad) | the port's | difference |
|---|---|---|---|
| 10.00 | -3.0956298682671384 | -3.0956298682671384 | 0 |
| 0.06 | -0.0050641875903723816 | -0.0050641875903723816 | 0 |
| 24.02 | -0.004060585727086014 | -0.004060585727086014 | 0 |
| 25.12 | -0.0031671272033251506 | -0.0031671272033251506 | 0 |

The lanelet runs west at about 3.137 rad, so at 0.06, 24.02 and 25.12 m SSv2 gives a heading
about 180 degrees off, and at 10.0 m one 0.05 rad off. The prediction held: the behaviour is
SSv2's, and the port copies it faithfully. Lanelet 105401's centre points are 0.015 m apart for
its first four segments, then 0.3225 m, a ratio of 21: the uniform spline overshoots past the
short segments' ends and comes back. The probe and its points:
`~/nas/autoveh/logs/issue-166/`.

Changing SSv2's spline would move every scenario's lane positions, so no fix is made before a
plan and 133's approval (and possibly the user's).

## The plan (133, 2026-11-25): flag the stretches, measure the impact, change nothing upstream

Reporting upstream (tier4) is outward and waits for the user's OK, which 133 asks for. Changing
the fork's spline (a centripetal or chord-length Catmull-Rom) moves every scenario's lane
positions; it is planned only if the impact below shows it matters, and then goes to the user.
Resampling the datasets' centrelines changes the maps, Autoware's too, and waits likewise.

**(d) The resolver flags reversed stretches.** `scensim_batch.anchors.resolve_lane` finds, on
each curve of each lanelet's spline (the cubic between two centre points), where its tangent
points against that curve's chord (the dot product is a quadratic in the curve's parameter, so
its roots give the range exactly), and lists the lane's stretches as `reversed: [{from_s,
to_s}]`, merged where they touch. `heading_max_error` becomes the error outside them, and
`heading_max_error_reversed` the error with them. `anchor.<lane>.heading(s)` refuses by name an
s inside a stretch (`anchor.<lane>.heading(s): s in a reversed stretch [a, b] of SSv2's spline,
issue 166`) rather than return the flipped value. The file stays `scensim-anchors` v1: `reversed`
is an addition, and a file resolved before it (no `reversed`) reads as before, unchecked; the
published Town01 file is one such, and stays until its next revision.

Predictions, before the code:
1. Town01's `west_street` (6583): `reversed` empty, its error 0.00099 rad as now.
2. Town05's `west_avenue`: at least one stretch on each of its ten lanelets, at the spacing
   changes near their ends, each under 0.1 m long and all of them under 1 m of its 372.5 m;
   the error outside them at most 0.01 rad (the spline's wiggles that are not reversals, such
   as the 0.05 rad at s 10, are within the table's halving), the error with them about 3.14.

**The impact measure, before (b) or (c).** For each frame of a run's truth, each SSv2-driven
entity's pose (its `ssv2` pose on seats, the batch's own on a batch truth) is placed on its
lanelet by the port (toLaneletPose); the frame counts as in a stretch when its s on that lanelet
lies in one, and as flipped when that entity's yaw is more than 90 degrees from the lanelet's
direction there. Runs: K13's on this host (check 2's attempts and reruns, `k13_platoon`), K11's
batch truths (K11c, K11d and K11e, `/var/tmp/aeon/k11*-run/runs/*/truth/`), and, since every
K11 and K13 entity stays on Town01's `west_street`, which has no stretch, also K2.4's three
seats runs (`~/nas/autoveh/logs/k24/`), whose SSv2 vehicles drive other lanelets.

Predictions, before the measure:
3. K13 and K11: 0 frames in a stretch, 0 flipped (their SSv2 entities stay on 6583).
4. K2.4: few frames in a stretch, about the stretches' share of the length those vehicles drive
   times their frames; each such frame flipped, since SSv2 takes a lane entity's yaw from the
   spline's tangent; none flipped outside a stretch.

## The resolver and the impact measure (2026-11-25)

**(d) done** (this commit): `resolve_lane` lists `reversed` stretches, `heading_max_error` leaves
them out, `heading_max_error_reversed` keeps them, and the sampler's `heading(s)` refuses an s in
one. Test: a straight lanelet with points 0.015 m, then 0.3 m apart lists its stretches, each
running backward on the spline, its error outside them under 0.01 rad, and heading(s) refuses
inside and answers outside; an evenly spaced lanelet lists none.

Against the predictions:
1. Town01, re-resolved (scratch copy of v2026.11e's Town01): `west_street`, `west_left_turn`
   and `north_through` list no stretch. Held, but the error stated was the file's, not
   `west_street`'s: the file's is 0.000989 rad as before (`west_left_turn`'s), `west_street`'s
   own 0.000143.
2. Town05's `west_avenue`: 18 stretches, the longest 0.0277 m, 0.321 m in all (held); but on
   five of its ten lanelets, the short ones (about 25 m), two at each end, and none on the long
   ones: "at least one on each" FAILED. The error outside them is 0.0213 rad, against "at most
   0.01": FAILED. Its largest, 0.0265 rad at s 316.89, 5 cm before a join, is a wiggle of the
   spline that does not reverse; the table's minimum step stops its halving there.

**The impact measure** (`issue166_impact.py`; results in `~/nas/autoveh/logs/issue-166/impact/`).
A frame is in a stretch when an SSv2-driven entity's pose lies within 0.01 m of the spline's
points inside one; a vehicle is flipped when its yaw is more than 90 degrees from every Town01
centreline segment within 0.5 m. The measure finds a stretch's point and not one 5 cm off, and
flags a reversed yaw on 6583 but not the true one.

| runs | entity frames | vehicle frames judged | in a stretch | flipped |
|---|---|---|---|---|
| K13, `k13_platoon` on this host (15) | 27,469 | 27,469 | 0 | 0 |
| K2.4's seats runs (3) | 2,687 | 2,687 | 0 | 0 |
| K11c, K11d, K11e batch truths (52,000 slots) | 21,663,858 | 0 (no SSv2 vehicle) | 0 | 0 |

Prediction 3 held. Prediction 4 FAILED on its premise: K2.4's SSv2 vehicles drove only lanelets
6583, 32582, 41199, 42451 and 42664, none of Town01's 41 with a stretch, so none could show one.
No existing run reaches a stretch, so the existing runs cannot say whether it matters.

**What the maps hold.** Town01: 145 stretches on 41 of 300 lanelets, 248 m of its 26.5 km of
lanes (0.94 %); Town05: 1107 on 372 of 1029, 374 m of 64.7 km. Most are a few centimetres (median
0.028 m and 0.018 m), but 52 on Town01 are over 0.5 m, the longest 11.25 m: on lanelet 38627 (a
344 m straight on Town01's south road) the centre points run 112 m, 112 m, then 0.0025 m and
0.33 m apart, and SSv2's spline loops 7.9 m past the point and back over a 16.9 m curve whose
chord is 2.5 mm. An SSv2 entity driving such a lanelet would, by the spline, run backward, facing
backward, for about 11 m of its s: some 28 frames at 8 m/s, not one.

## The targeted run (133, 2026-11-25): an SSv2 vehicle through lanelet 38627's loop

On CARLA 0.9.16, Town01 at Low (no town change), this host's seat, scensim at main c8ca43e0 with
this branch: an SSv2 default vehicle (the catalog's tesla_model3) teleported to lanelet 38627
at s 200 with a step SpeedAction to 8 m/s, the ego (carla_basic) parked on `west_street`, the run
ended by `exitSuccess` at 15 s. Lanelet 38627 runs east along y -324.5; its third curve, s 224.40
to 241.28 of the lanelet, joins two centre points 2.5 mm apart.

**Prediction, before the run** (the port's spline at the vehicle's s, s = 200 + 8 t from its
first move):
1. SSv2's pose (the truth's `ssv2`) runs east past x 325.72 to x 334.03 at s 229.97 (about
   3.7 s after its first move), its yaw about 0; then back west to x 325.73 at s 241.28 (about
   5.2 s), its yaw about 3.140, some 28 frames facing west; then east again over the same 8.3 m,
   yaw about 0.
2. SSv2 reports its speed as 8 m/s throughout (its own state, not the poses' difference), and
   raises no error.
3. CARLA's car, tracking SSv2's pose (`npc_motion: tracked`), cannot follow a reversal in place:
   its tracking error grows over the loop and the tracker snaps it at least once (`contacts`'
   tracking record), so the body visibly jumps or turns about.

**The targeted run's result (2026-11-25): no vehicle can be there.** The run (scensim c8ca43e0
with this branch, rebuilt; `~/nas/autoveh/logs/issue-166/targeted-run/`) ended as an error run
before any frame of the loop: SSv2's spawn of the vehicle on lanelet 38627 at s 200 failed, the
CARLA world server reporting "5 attempt(s) at increasing height collided ... the static world
blocks this pose" at CARLA (303.0, 324.2, 0.3). The prediction FAILED on its premise: 38627 is
not a road a car stands on.

Why, from the export: lanelet 38627 has no predecessor and no follower, and neither has any of
the 52 lanelets whose loops are longer than 0.5 m. They are the isolated lanelets of the Town01
lanelet map (170 of 300: 66 `walkway`, 65 `unknown`, 39 `road`), 220 to 369 m long around the
blocks, the walkways and the kerb lines. SSv2 routes a vehicle over connected lanelets only.
Split by connection (a lanelet with a predecessor or a follower):

| map | connected lanelets | their stretches | longest | isolated lanelets | their stretches | longest |
|---|---|---|---|---|---|---|
| Town01 | 130 (7.2 km), 6 with stretches | 8, 0.185 m in all | 0.032 m | 170 (19.3 km), 35 with | 137, 247.9 m | 11.25 m |
| Town05 | 470 (24.2 km), 239 with | 696, 10.9 m in all | 0.032 m | 559 (40.4 km), 133 with | 411, 363.2 m | 13.88 m |

So on the network vehicles drive, a stretch is at most 3.2 cm: a vehicle at 8 m/s (0.4 m a
frame) lands a frame in one with a chance of at most about 8 % per stretch it passes, and then
for that one frame. The long loops lie on lanelets no vehicle is routed over; a pedestrian placed
by LanePosition on a walkway lanelet could meet one; none in the runs measured above does.

## The lint (133, 2026-11-25)

`scensim check` refuses a LanePosition whose lanelet and s are both written into the scenario
and whose s lies in a reversed stretch, naming the stretch; `scensim run` (and a replay) warns
when a run's values (a parameter's, a suite's, the sampler's, an anchor's) put one there
(`scensim.lane_positions`). The stretches come from the map's centre points and the spline,
which `scensim_batch.catmull` now holds without torch: `world_lanelet` imports it from there,
unchanged, so the batch, the resolver and the check read one spline. Tests: an uneven centreline
has its stretches and an even one none; a written s in a stretch is refused and one outside is
not; a parameter's value is warned of where it falls in one.

**Over every scenario in the repository** (2026-11-25, the 112 `.xosc` files git tracks here, the
maps at dataset v2026.11f): 21 files hold LanePositions, 152 in all. The 122 on the dataset's maps
(Town01, 02, 03, 05, 10, town05_ring_110kmh; 100 written, 22 from a parameter at its declared
value) put none in a stretch: 0 refused, 0 warned. The 30 in 12 files on the sampler's test maps
(`maps/town_street`, `maps/highway_3lane`, `straight400`), which are not dataset maps, are not
checked. A suite or sampler that sets other values is checked by the run's warning.

## The gate's find (2026-11-25): an unloadable map stopped a run in its warning

The full gate on main 8f583597 failed `test_knobs.py::test_k9e_cs3_binds_the_same_on_carla_and_isaac`:
its project map is a stand-in (`<osm town01/>`), and `scensim run`'s new warning, reading the
map's centre points, raised the loader's `ParseError` out of `run.expand`. A warning's check
must never stop a run. `lane_positions.stretches` now raises `MapUnreadable` (naming the map and
the loader's error) for any failure to load the map's lanelets; `scensim run` writes it as a
warning and goes on, and `scensim check` reports it as a host finding (fix: fetch the map), not
refused. Test: `test_a_map_that_does_not_load_is_said_and_neither_refused_nor_fatal`. The same
gate's `test_simulator.py::test_a_carla_deaf_to_sigterm_is_killed_after_its_keeper` failed too
(`AssertionError: a CARLA that ignores SIGTERM outlived its SIGKILLed keeper`), seen once,
under load (the gate at nice 10 beside other work), and passing on its own re-run. Issue 166
does not touch `scensim.simulator`. A kill-timing flake under load is the class of issues 148
and 150: a second sighting is not waived, it stops the landing and gets its own number.

## A placement s and a model's gap (092 K13 step v, 2026-11-25)

The spline's s counts each reversed loop's overshoot; the resolved anchor's `x`/`y` (the spline
sampled at `heading_s`, up to 0.36 m apart) skip it, so arc length along that polyline runs
short of s across a loop. Cars are placed by s (`lanelet_at`, `local_s`, the world's spline);
`idm_follower` measures its gap along its resampled copy of the polyline. Its gap is therefore
short by the loops' overshoot between it and its leader.

Found by K13 step v's dry run: M's first command was -2.51e-4, -1.45e-4 and -9.48e-5 m/s^2
where IDM's exact equilibrium gives 0, and backing the gap out of IDM gave shortfalls of
0.025864, 0.025870 and 0.025867 m. Polyline arc against s over M to L on `west_avenue`
(`k13v_arc.py`) gives 0.025868, 0.025871 and 0.025866 m, within 4e-6 m of those: 7.7 mm at the
loop pair at s 73.2, 19.1 mm from s 95.9 to 97.1 (the pair at 96.45 and lanelet 117337's end),
-0.9 mm just after the join at 71.84, and under 1e-5 m in the loop-free spans. Over the whole
lane the polyline is 0.0935 m shorter than s.

**Scope.** Any car-follower on a lane anchor with a reversed stretch between it and its leader,
in the batch and on seats alike (one model code): its gap reads short by up to the sum of
those loops' overshoot, a few centimetres per loop pair here, and IDM's acceleration is off by
about its gap sensitivity (0.004 to 0.01 (m/s^2)/m at K13 step v's gaps) times that.
Measuring the gap in s instead (each polyline point's `heading_s`) would remove it; that is a
model change, not made here: it is this record's **open fix** for the placement-against-gap mismatch, out of 092 K13, with a plan before any code (133). K13 step v corrects its placement instead: L starts at 73.13 +
0.025868 + s_e(T), the arc difference computed from the polyline, not fitted to a0. The
difference varies by under 5e-6 m over L's range, all on lanelet 219, past the loops.
