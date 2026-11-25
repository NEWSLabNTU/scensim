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
