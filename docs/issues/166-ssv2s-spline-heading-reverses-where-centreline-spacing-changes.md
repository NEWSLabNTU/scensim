# 166: SSv2's spline heading reverses where a centreline's point spacing changes

**Status:** closed (2026-11-27, 241, on 133's rule): on SSv2's own centreline (issue 194) no connected lanelet of Town01 or Town05 has a reversed stretch, and every check below holds there; see the last section. Before that: open (241; numbered by 133, 2026-11-25); the gap-in-s fix in code and tests (2026-11-25; checks 2b and 4 FAILED as worded). **Severity:** to judge: a lane position's
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

## The open fix's plan: a car-follower's gap in s (approved by 133, 2026-11-25, before any code)

**What is there.** `idm_follower` (`src/scensim/scensim/behaviour/follower.py`) resamples the
lane anchor's x/y every `DS` (0.5 m) of polyline arc on the host (`resample()`), and `_place`
puts a point at s = (k + t) DS, k the nearest resampled segment and t the fraction along it.
The anchor's x/y are the spline sampled at `heading_s`; across a reversed loop the chord
between two samples is shorter than their `heading_s` step (36 segments over 1 mm short on
Town05's `west_avenue`; the polyline 0.0935 m short of s over the lane), so the follower's s,
and its gap, runs short of the placement s by the loops' overshoot between it and its leader.
`heading_s` is monotone on `west_avenue` except 7 equal pairs at lanelet joins (repeated
points, within 1e-13).

**The change.** `resample()` resamples uniformly in `heading_s`, the spline's s, instead of in
polyline arc: point k sits at spline s = k DS, linearly interpolated in x/y between the anchor
samples around it, so `_place`'s (k + t) DS is spline s, the s the world places by. Repeated
`heading_s` values are dropped, as zero-length steps are now. An anchor without `heading_s`
(resolved before K9's cd65e4ce) keeps today's arc resampling, said in the docstring. Nothing
else moves: the step uses the same xp operations, so numpy and torch stay bit for bit; the
leader is placed by the same code; `end_s` is already in s. Inside a loop the chord between two
resampled points is short by that loop's overshoot, so a point within that one segment reads s
off by at most the overshoot (millimetres); elsewhere it is exact to interpolation.

**K13 step v's correction comes out.** `k13_platoon_town05.yaml`'s `lead_s` carries
+ 0.025868; with the gap in s it must go, or M starts 0.026 m long of equilibrium. The yaml,
its comment, the case's comment and this record change together. K13 step v's search result
stands, not re-run: it ran with the correction and the old gap, consistent with each other,
and 092 says so in one line.

**Checks**, each with its bar; the predictions for 3 and 4 are committed before they run:

1. Unit (test_follower.py): on a synthetic lane with a reversed loop (a spline sampled across
   a loop, as here), a point at spline s reads s within 1e-3 m outside the loop's own segment
   and within the overshoot inside it; on a lane whose `heading_s` is its own chord arc the
   result equals today's to 1e-12, the two resamplings being the same there.
2. `west_avenue`, no simulation, both ways (133): for M's start (68.43) and every L start the
   search drew, the follower's s at the placed position minus the placement s within 1e-4 m
   (today 0.0259 m between M and L); and the follower's x/y at spline s (its resampled
   polyline) against the world's placement at that s within 1e-3 m outside loops, so the
   truth pose and the gap agree.
3. K13 step v's dry-run check 1, redone without the correction: M's acceleration at t = 0
   within 1e-6 m/s^2 in all 36 slots.
4. The onset sweep (092, K13 step v's open question) rerun: record 842ce095 with `lead_s`
   without the correction, onsets 1.00 to 4.00 by 0.25, the same measures.
5. Every test, batch and seats; numpy and torch bit for bit (the existing agreement tests).

**Scope.** Seats and batch alike (one model). The ego's pilots and the truth's closest gap (box
to box in x/y) are untouched. K13's exit checks 2 and 3 are not re-run: their SSv2 entities and
the model car stay on Town01's `west_street` (6583), which has no reversed stretch (this
record, "The plan" item 1 and the impact measure's prediction 3); no other Town01 lanelet was
used by those runs.

**Order.** This plan; check 3 and 4's predictions; the code and tests; the results here;
local checks and a full gate; a landing request to 133.

**Checks 3 and 4's predictions (2026-11-25, before the code and the runs).**

- **3.** Without the 0.025868 correction, M's acceleration at t = 0 is within 1e-6 m/s^2 in all
  36 dry-run slots (with the old gap and no correction it was -2.5e-4 to -9.5e-5).
- **4.** The closest gap's range over onsets 1.00 to 3.75 s is at most 0.005 m (today 0.052 m,
  in steps of 2 to 3 cm, the order of the loop shortfalls between M and L: one line, not a
  claim). Onset 4.00's jump to 1.47 m is about forty times the largest of those shortfalls
  (0.026 m); no prediction is made for it, and it is recorded as it comes out.

**The checks' results (2026-11-25, on the fix as coded; scripts `i166_check2.py`,
`i166_check3.py`, `i166_check4.py`, from the dev worktree at 02913108 plus the code).**

1. **Unit: held.** Across a synthetic reversed loop of 0.02 m, a point placed at spline s
   reads s within 1e-3 m outside the resampled segment holding the loop and within the
   overshoot inside it; resampled in polyline arc (no `heading_s`) it read 0.02 m short. A lane
   whose `heading_s` is its own chord arc resamples as before to 1e-12; a repeated `heading_s`
   is dropped, one that goes back is refused by name.
2. **Both ways on `west_avenue`: held one way, FAILED the other.**
   - Placement s to follower s: held. Over M's start and the 21000 L starts the search drew,
     the follower's s minus the placement s is within 4.0e-5 m (bar 1e-4); M to L's gap error
     -4.0e-5 to +3.8e-5 m, where the old resampling gave -0.02591 to -0.02583 m.
   - Follower x/y at spline s against the world's placement at s, every 0.1 m outside the 13
     resampled segments holding a reversed stretch (3661 points): FAILED, largest 0.0122 m (bar
     1e-3), at s 72.2. All 50 points over the bar lie within 2 m of a reversed stretch
     (24.6 to 24.9, 72.1 to 73.7, 96.6 to 97.4, 226 to 227, 255 to 256, 291.9, 314.6 to
     316.8 m); beyond 2 m of every stretch the largest is 8.6e-4 m (3332 points). The error is
     along the lane (up to 0.0122 m), not across it (at most 5.3e-4 m): near a loop the
     anchor's samples, linearly interpolated, run ahead of or behind the world's spline at the
     same s. The check stays FAILED as worded (133: the bar is not amended).
     **Observation, beside it:** within 2 m of a reversed stretch the linear interpolation of
     the anchor's samples runs up to 1.2 cm along the lane from the spline; beyond 2 m, at most
     8.6e-4 m. **Known limit:** evaluating the port's spline in place of linear interpolation
     would remove it; not done.
3. **K13 step v's dry-run check 1 without the correction: held.** M's acceleration at t = 0
   is at most 7.4e-8 m/s^2 over the 36 slots (bar 1e-6).
4. **The onset sweep rerun: FAILED.** Without the correction, the closest gap over onsets 1.00
   to 3.75 s spans 1.100 m (bar 0.005):

   | onset (s) | gap (m) | frame |
   |---|---|---|
   | 1.00 | 0.40693 | 173 |
   | 1.25 to 2.50 (6 slots) | 0.39870 to 0.39895 | 178 to 204 |
   | 2.75 to 3.25 | 1.49794 to 1.49980 | 208 to 218 |
   | 3.50 | 1.44936 | 223 |
   | 3.75 and 4.00 | 1.44786, 1.44762 | 228, 233 |

   The gap is flat to 2.5e-4 m over onsets 1.25 to 2.50 (it was 0.4245 to 7e-5 there), then
   jumps by 1.100 m at 2.75 s, where the old sweep jumped by 1.100 m at 4.00; and the drop of
   about 0.05 m between 3.25 and 3.50 s is still there, so it is not M's gap measurement
   either. Record 842ce095 itself (onset 3.628) now gives 1.448 m. A hypothesis, not a claim:
   1.100 m is 22 m/s times one 0.05 s step, and at both jumps (here 2.50 to 2.75 s, the old
   sweep's 3.75 to 4.00 s) the closest approach's frame advances 4 frames for 0.25 s of onset
   where it otherwise advances 5 (once 6, 2.00 to 2.25 s, with no jump), so the jumps would be
   the ego's braking latching one frame earlier, a discretisation of the point-mass ego's
   `aeb_ttc` (TTC checked each 0.05 s step), not the follower. Not tested here.
5. **Every test** (the local follower and batch suites so far: 23 passed, 1 skipped); the full
   gate follows.


**166's stretch counts were measured on lanelet2's raw centreline, which SSv2 replaces; see
194** (2026-11-26). SSv2's `generateFineCenterline` line leaves no reversed stretch on a
connected lanelet of Town01 or Town05.

## 166's checks on SSv2's own centreline (241, 2026-11-27; predictions before any of it runs)

Asked by 133: issue 194 showed that 166 measured lanelet2's raw centreline, which SSv2 replaces
with its own 2 m line (`generateFineCenterline`). Recompute 166's checks on SSv2's line for
Town01 and Town05, then decide whether 166 closes, narrows, or stays open. CPU only, docs only.
The inputs: the maps at dataset df499322 (tag v2026.11h, whose anchors were resolved on SSv2's
line), scensim main with 194's export (`map_export` v3) and 166's gap-in-s follower (c2bc1b91).

What is recomputed, with each prediction:

- **R1, the original finding.** Sampling every 5 mm, how many lanelets have a heading change of
  more than 90 deg between samples (lanelet2's line: Town05 350 of 1018, Town01 37 of 300).
  - Prediction: none on a connected lanelet of either town. In all, at most 4 lanelets on Town01
    and at most 1 on Town05, which are 194's isolated lanelets with a stretch.
- **R2, the resolver's predictions 1 and 2**, read from df499322's resolved anchors.
  - Town01 `west_street`: no `reversed` stretch.
  - Town05 `west_avenue`: no `reversed` stretch. `heading_max_error` is at most 0.01 rad, now
    with nothing left out, so `heading_max_error_reversed` equals it.
  - The old prediction 2's "at least one stretch on each lanelet" fails by construction, since
    no stretch is left.
- **R3, what the maps hold**, by `scensim.lane_positions.stretches` (the lint's own function) at
  main, split by connection. Prediction: 194's survey table again. That is no stretch on a
  connected lanelet; Town01 isolated 9 stretches on 4 lanelets (0.160 m, the longest 0.066 m);
  Town05 isolated 1 (0.020 m).
- **R4, the impact measure** (K13 on this host, K2.4's seats runs, K11c to K11e). Prediction: 0
  frames in a stretch and 0 flipped. Every lanelet those runs used is connected, and R3 predicts
  no stretch on any connected lanelet. If R3 holds, R4 follows from it and is not re-run frame
  by frame. The lanelets they used are listed against R3's.
- **R5, the lint over the repository's scenarios** (166's 152 LanePositions in 21 files; the
  122 on dataset maps checked). Prediction: 0 refused, 0 warned, as on lanelet2's line.
- **R6, the placement s against the polyline's arc** on `west_avenue` (K13 step v's 0.025868 m
  between M and L; the lane's polyline 0.0935 m shorter than s). Prediction: the polyline is
  within 1 mm of s over the whole lane, and within 1e-4 m between M and each L start of the
  search. There is no loop for it to skip.
- **R7, the gap-in-s fix's check 2, both ways** (`i166_check2.py`), on the v3 export and the new
  resolved anchor.
  - (a) Follower s minus placement s, within 1e-4 m. It held before at 4.0e-5 and should still
    hold.
  - (b) Follower x/y at spline s against the world's placement at s, every 0.1 m along the lane.
    This FAILED before, at 0.0122 m within 2 m of a stretch. Prediction: it holds, at most
    1e-3 m everywhere, since no stretch is left to stay out of.
- **R8, check 3** (K13 step v's dry run, M's acceleration at t = 0 within 1e-6 m/s^2 in all 36
  slots), if the batch runs on this host's CPU at main. Prediction: it holds, as before.
- **Not recomputed: check 4** (the onset sweep). Its failure was jumps of 1.100 m at one onset,
  put down to the point-mass ego's AEB timing, not the line. Re-running it here would not
  separate the two. It is left to 092.

**The decision rule, set now.**
- If R1, R3 and R7(b) hold, 166's defect no longer arises on the network vehicles drive. SSv2's
  uniform spline still reverses on uneven points, but SSv2's own line has even 2 m points, so
  166 **closes**. It records what stays (the lint, the follower's s, the 10 isolated
  stretches) and that the upstream report is moot for these maps.
- 194's joined-route transient (2.10 cm at the 42664 to 32582 joint) is not 166's defect: it
  comes from the joined spline's end conditions, not from a reversal. It stays with 092 K2.4's
  follow-up, and 166 does not narrow to it.
- If R1 or R3 finds a stretch on a connected lanelet, 166 stays open, narrowed to those lanelets.

### The results (2026-11-27)

Run at scensim main 5fb073c2 (194's export v3, the follower at c2bc1b91), maps at dataset
df499322. Scripts and outputs are on the NAS, `home/2026-11-27 issue 166 on SSv2's line (241)/`.

| check | on lanelet2's line (166) | on SSv2's line | prediction |
|---|---|---|---|
| R1: lanelets with a >90 deg step, sampled every 5 mm | Town01 37 of 300, Town05 350 of 1018 | **0** on both towns, connected and isolated | held |
| R2: Town01 `west_street` `reversed` | none | none (`heading_max_error` 7.8e-7 rad) | held |
| R2: Town05 `west_avenue` | 18 stretches; error outside them 0.0213 rad | none; `heading_max_error` 0.00057 rad, the same with nothing left out | held |
| R3: stretches, connected lanelets | Town01 8 (0.185 m), Town05 696 (10.9 m) | **0** on both | held |
| R3: stretches, isolated lanelets | Town01 137 (247.9 m), Town05 411 (363.2 m) | Town01 9 on 4 (0.160 m, the longest 0.066 m), Town05 1 (0.020 m) | held, 194's table to the digit |
| R4: impact (K13, K2.4, K11) | 0 frames | 0, by R3 | held |
| R5: the lint over the repository's scenarios | 0 refused, 0 warned | 0 refused, 0 warned | held |
| R6: `west_avenue` polyline arc against s | 0.0935 m short over the lane; 0.025868 m from M to L | 2.3e-5 m over the lane; 1.34e-5 m from M to each L | held |
| R7(a): follower s minus placement s | within 4.0e-5 m | within 8.7e-11 m | held |
| R7(b): follower x/y against the world's at s | FAILED: 0.0122 m within 2 m of a stretch | **0.00044 m** at most, over all 3722 points, none left out | held |
| R8: M's acceleration at t = 0, 36 slots | 7.4e-8 m/s^2 | 9.6e-11 m/s^2 | held |

Notes:

- **R1's harness check.** The same 5 mm sampler on lanelet2's raw `centerline()` of
  df499322's Town01 gives 37 of 300, 166's count. So the 0 is the line's doing, not the
  sampler's.
- **R1 also finds 0 on the 5 isolated lanelets that keep a stretch** (R3). Their stretches
  are on curves, where the tangent turns through 180 deg over a few centimetres rather than
  flipping. No 5 mm step there exceeds 90 deg. "At most 4 and at most 1" held with room to spare.
- **R4.** Every lanelet those runs used is connected and has no stretch on SSv2's line:
  Town01 6583, 32582, 41199, 42451 and 42664, and Town05 `west_avenue`'s ten lanelets
  (105401 to 3337).
- **R5.** The repository now has 117 tracked scenarios. 23 hold 159 LanePositions, 129 of
  them on dataset maps (Town01 125, Town05 4). 30 are on the sampler's test maps, which are
  not checked. The count differs from 166's (152 and 122) because scenarios were added since.
- **R7.** Even the old polyline-arc resampling of the follower is now within 1.34e-5 m of the
  gap in s. There is no loop left for the gap-in-s fix to correct on this lane. The fix stays
  as written; it is harmless and exact.
- **Check 4** (the onset sweep) was not re-run, as planned. Its jumps are 092's question.

**The decision (the rule set with the predictions): 166 closes.**

- SSv2's uniform Catmull-Rom does reverse on unevenly spaced points (166's probe: bit for bit
  the port's).
- SSv2 never feeds it lanelet2's line. Its own 2 m line has no stretch on any lanelet a
  vehicle is routed over in Town01 or Town05.
- What is left are 10 stretches on isolated lanelets (walkways, kerb lines), at most 6.6 cm
  long. The lint still names any LanePosition placed in one.

What stays:

- the lint (166) and 174's layout check;
- the resolver's `reversed` field;
- the follower's gap in s.

The upstream report is not needed for these maps. A map whose own line SSv2 does not replace (a
custom centreline, or `use_custom_centerline`'s default turning false) would bring the question
back. The lint would then name it.

194's 2.10 cm transient at the 42664 to 32582 joint is not this defect: it comes from the joined
spline's end conditions, not a reversal. It stays with 092 K2.4's follow-up, and 166 does not
narrow to it.
