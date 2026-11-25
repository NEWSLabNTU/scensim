# 170: on Isaac, localization sits 0.066 m across the track from the truth, and 11 to 14 mm above it beyond issue 167

**Status:** open; plan written (2026-11-25, after 169's step 1), for 133. **Severity:** to be shown. The across bias is
about half of smooth haruna_down's pose error p95 (0.12 m). **Found:** 2026-11-25, scensim
118, 086 C6e2 and issue 167 (numbered by 133).

## What is the case

Two open quantities on Isaac's haruna_down, measured offline from the runs' records
(`/localization/kinematic_state` against the truth trace `ego.csv`, above 1 m/s;
`c6e2/along.py`, `c6e/locz.py`):

1. **Across the track: -0.065 to -0.071 m** (localization right of the car, with the y axis
   left) in all six C6e2 runs, with motion BVH off and on. Issue 167's probe shows it is not
   the lidar's mount: the lidar prim has no lateral offset, and the rig's mount equals the
   sensor kit's extrinsics (x 0.9, y 0, z 2.0, roll -0.001, pitch 0.015, yaw 1.5386 rad).
2. **NDT's z: +0.022 to +0.026 m above the truth** before issue 167's fix. The 36.22 mm offset
   predicts a bias of its own size, and 11 to 14 mm of the measured one is not accounted for.
   167's reach check on the fixed aib measures what is left.

## Candidates (none measured)

- the truth trace's origin: which point of the body `ego.csv` reports, against Autoware's
  base_link (the rear axle's middle on the ground);
- the map's cloud against the road: the course builder's sampling of the road and its
  verges into `pointcloud_map.pcd`, and the lanelets' frame;
- the vehicle's base_link under the suspension's sag, against Autoware's static vehicle
  model (for z);
- NDT's roll and pitch taking part of an offset on a crowned road (for z and across);
- the sensor kit's yaw of -0.0364 rad (sensor_kit_base_link), which is in both the rig and the
  TF, so it should cancel. Checked only on paper.

## The plan (written 2026-11-25, after issue 169's step 1, before any run; for 133)

**What issue 169 can and cannot explain here (from 169's probe, not from a run of 170).**

- *The across bias (-0.066 m): not explained by 169.* With motion BVH off (C6e2's f1 to f3, and
  every 168 A/B run) the cloud carries no motion at all (169's cases A and E: D - D_true
  0.000 m), yet the bias is -0.065 to -0.067 m. And the motion 169 measures lies along the
  track. A cloud with no motion cannot put localization across the track.
- *The small extra with motion BVH on: possibly explained.* C6e2's BVH-on runs sat at -0.070 to
  -0.071 m, 4 to 5 mm further across than the off side. On haruna_down's bends the renderer
  also turns each point with the car's yaw over the revolution (169's C shows it traces each
  point from its firing pose), and with no point times nothing removes it. *Hypothesis,
  untested:* that turn is the 4 to 5 mm.
- *NDT's z: not explained by 169.* The residual after issue 167's fix (167's reach check) is on
  the BVH-off side too, and 169's motion is horizontal.

**Predictions for 170's numbers after 169's part 3** (the corrector on, xyzircaedt, aib's own
distortion off under BVH), from C6e2's pairing rerun that part 3 already includes:

- the BVH-off side: across within 3 mm of today's (-0.065 to -0.067 m) and NDT z within 3 mm of
  167's reach check. The cloud changes on this side (aib's distortion in, the corrector out),
  but the net is the same single-pose geometry.
- the BVH-on side: across moves to within 2 mm of the off side's, if the hypothesis above holds.

**The steps.** The first two are offline, on records that exist; no run until 133 has seen
their result.

**Step 2 runs first (133, 2026-11-25), with its sizes written before looking.** A difference
between the published TF (base_link to the lidar) and the lidar's real mount moves the pose NDT
reports for base_link, since NDT places the lidar and base_link follows through the TF. The
levers, from the rig (`translation: [0.9, 0.0, 2.0]`):

- *yaw*, δ = the TF's yaw less the real one: base_link moves across by L sin δ, with L = 0.9 m
  (the lidar's forward lever, not its height). A positive δ (the TF turned left of the real
  mount) makes NDT turn the car right by δ, and base_link lands +0.9 sin δ to the left. The
  probe's 1.84 deg (if all of it were a TF error) would give +0.029 m, not 0.066 m. -0.066 m
  needs δ = -4.2 deg, and NDT's heading would then sit 4.2 deg left of the truth (step 1 would
  see it).
- *roll*, ρ = the TF's roll less the real one (positive: left side up): base_link moves across
  by -H sin ρ, with H = 2.0 m (the lidar's height over base_link). -0.066 m needs ρ = +1.9 deg,
  and NDT's roll would sit 1.9 deg off (step 1 would see it).
- *pitch* moves base_link along and up (H sin and L sin of it), not across.

*Prediction (before looking):* δ and ρ are both under 1e-4 rad, since 167's probe found the
rig's mount equal to the kit's extrinsics (yaw 1.5386 rad), and the TF from those extrinsics
adds nothing across. If either is not, its size from the formulas above is compared with -0.066 m.

1. *The attitude and heading split* (offline: C6e2's six runs and 168's twelve,
   `/localization/kinematic_state` against `ego.csv`, above 1 m/s). Per run: the median error
   in roll, pitch and yaw, and the across error against the road's curvature and cross slope
   at each sample. *Predictions:* (a) |roll error| under 0.2 deg. A roll error that put a 2.0 m
   high lidar 0.066 m across would be about 1.9 deg, which the attitude would show. (b) |yaw
   error| under 0.1 deg. A yaw error that moved base_link 0.066 m about the lidar 0.9 m ahead
   would be about 4 deg. (c) The across error does not depend on the curvature's sign (left
   and right bends alike, within 5 mm). If (c) fails, the bias is not a constant offset.
2. *The frames on paper, then by numbers* (offline: the TF tree the run published, from a
   record, against aib's lidar mount and the truth trace's origin). base_link to the lidar from
   the sensor kit's calibration chain (sensor_kit_base_link's yaw -0.0364 rad and the lidar's
   1.5386 rad) against aib's `sensor_mount` (which 169's probe showed as a 1.84 deg turn of the
   published frame from 90 deg); and the point `ego.csv` reports (`course/ego_trace`) against
   Autoware's base_link. *Prediction:* each pair equal within 1 mm and 1e-4 rad. A pair that
   differs gives the bias's size by itself, and that is the finding.
3. *The map against the road* (offline: Haruna's `pointcloud_map.pcd` road points, the crown's
   top across the road per 10 m, against the lanelets' centreline). *Prediction:* within 1 cm
   across. If the map's crown sits about 0.066 m off the lanelets, the map is the cause.
4. Only if 1 to 3 find nothing: a fixture run on a straight, level, uncrowned course
   (fixture_c5's shape with no crown), predicting the across bias there. Its spec comes to 133
   first.
