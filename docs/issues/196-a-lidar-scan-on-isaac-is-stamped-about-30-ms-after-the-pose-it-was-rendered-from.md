# 196: a lidar scan on Isaac is stamped about 30 ms after the pose it was rendered from

**Status:** open; a plan, no code. **Severity:** medium. Localization sits behind the car by
the lag times the speed: -0.29 to -0.35 m at 11 m/s on fixture_c170, -0.05 to -0.15 m at
Haruna's 1 to 5 m/s, in NDT and the EKF alike. **Found:** issue 170 step 4's speed split
(fixture_c170 R1 to R3), and pooled on Haruna's 18 runs, 2026-11-27.

## What happens

On a straight, level road with nothing else to explain it, NDT's and the EKF's along error
against the truth grows with the truth's speed in every 1 m/s bin, from about 0 at 1.5 m/s to
-0.29 / -0.35 / -0.30 m at 11.5 m/s (`speed170.py`). A line a + b v over the bins:

| run | NDT tau | NDT a | EKF tau | EKF a |
|---|---|---|---|---|
| R1 (east) | 30.1 ms | +0.029 m | 29.1 ms | +0.015 m |
| R2 (west) | 36.9 ms | +0.060 m | 36.8 ms | +0.059 m |
| R3 (east) | 32.9 ms | +0.083 m | 35.0 ms | +0.094 m |
| Haruna, 18 runs pooled, 2.5 to 4.5 m/s | | | about 29 ms | about +0.13 m |

A scan whose stamp is later than the pose it was rendered from by tau places NDT's pose, at
that stamp, where the car was tau earlier: -v tau along, nothing across on a straight. NDT has
it, so the scan's time is wrong, not the EKF's.

## Why, from aib's code (not yet confirmed)

Each frame (0.05 s) the lidar prim is put at its pose at each substep's end (`before_substep`,
`_pose_after`), the last substep renders, and the host publishes with `stamp` = the frame's end.
The annotator's data is `latency_frames` (2) renders old when read, so the cloud takes the stamp
saved 2 frames back (`Lidar.publish`, `_msg`): the end of the frame it was rendered in. aib's
own note says the RTX lidar renders a revolution from one pose. If that pose were the frame's
end, tau would be 0; if the delay count were off by whole frames, tau would be 50 or 100 ms
(-0.56 or -1.1 m at 11 m/s). It is neither: 30 to 37 ms, about 0.6 to 0.75 of a frame, and
about the same on Haruna, whose frames ran up to 45 % slower in wall time (51 to 73 ms against
50). So it looks fixed in simulation time, a fraction of the step, not set by load.

Candidates: the RTX lidar takes its pose from part way through the frame (the prim's pose as the
renderer last saw it, or the motion it interpolates for a rotary sensor), or it fires the
revolution over the frame (its per-point `timestamp`, which aib reads only for the
`xyzircaedt` format; the Tesla rig's `xyzirc` drops it) and the stamp is its end.

## The plan (no code)

1. **Measure the annotator's own times** (aib's runner, no Autoware, CPU and the card): for each
   published scan, the annotator's per-point `timestamp` (min, median, max) against the stamp
   aib gives it and the frame's substep times, on the Tesla rig at a constant 10 m/s on
   fixture_c170. *Prediction:* the points' median time is 25 to 40 ms before the stamp (the
   lag seen); if instead the times end at the stamp and start 50 ms before, the revolution is
   fired over the frame and its middle is the pose's time.
2. **A static check of the pose:** the same run, the scan's points against fixture_c170's
   geometry at the stamp and at stamp less tau (the road's edges at a known x along the drive):
   the fit is best at stamp less tau if step 1 is right.
3. **The fix, chosen by what 1 and 2 show:** stamp each scan at the time its points were taken
   (the annotator's median, or its first point with per-point times and the distortion corrector,
   as on a real vehicle), or put the prim at the pose that matches the stamp. A test first in
   aib (the stamp against the annotator's times, on recorded annotator data).
4. **The live check:** fixture_c170 R1 to R3 again; the speed split's tau under 5 ms and the
   along error at 11 m/s under 0.05 m.

Issue 170's across error (c = +0.19 m, car-fixed) is not this: a lag gives no across error on a
straight. That stays in 170.

## Step 1: the annotator's times against aib's stamp (243, 2026-11-27, before the run)

Approved by 133 as a measurement only, no fix. aib's runner (`python -m aib.runner`), no
Autoware, the car standing on fixture_c170 (timing does not need motion), headless, about 20 s
of sim time, 20 Hz frames, the install the runs used (wt-170, fcc01e50). The Tesla rig unchanged
but for one override in the ego config: `sensors: {top: {isaac: {point_format: xyzircaedt,
motion_distortion: false}}}`, so each cloud carries the annotator's per-point times
(`time_stamp`, ns after the header) and its header is the annotator's first point (`point_times`,
`ros.stamp(t0 + to_sim)`), and nothing is distorted. A subscriber logs per scan the header, the
offsets' min / median / max, and the last `/clock` before it.

The frame the scan was rendered in, by aib's code: a cloud built at frame j's `publish` is sent at
frame j+1's, after `/clock` = E(j+1) (the frame's end); it holds the render of frame j - 2
(`latency_frames` 2). So the render frame's end is E_r = clock at receipt - 3 x 0.05 s, and in the
runs' format (`xyzirc`) that is the stamp the scan would have had.

*Predictions:*
- P1: the offsets span one revolution: max 45 to 50 ms (OS1 at 20 Hz), median about 25 ms.
- P2: the revolution is fired over the render frame: its first point t0 = E_r - 50 ms (within
  5 ms), its median E_r - 25 ms. Then the runs' stamp (E_r) is 25 ms after the points' median
  time, the size of L1/2.
- P3, the comparison with the runs' tau (30 to 37 ms): if E_r less the points' median is 30 to
  37 ms, the points' times are the lag, and stamping a scan at its points' median time would
  remove it. If it is 25 ms (P2) the points' times explain most of it and the rest (5 to 12 ms)
  is elsewhere (the pose the render takes). If the offsets are all 0 (P1 fails), RTX renders the
  revolution at one instant and the annotator's times say nothing of the lag; step 2 (the
  geometry) then has to.
