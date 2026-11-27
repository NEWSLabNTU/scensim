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

## Step 1's result (243, 2026-11-27)

Ran 09:02:59 to 09:03:34 on host 243 (21.6 GB free on the card), `run196.sh`, the runner exited 0
after 40 s of sim time; 739 scans logged (`/var/tmp/aeon/196/scans.jsonl`). The runner's log has
one `ModuleNotFoundError: No module named 'em'` traceback (a ROS message import at start; the
runner went on). The runner steps 20 Hz frames in three physics substeps of 1/60 s (its default
`--physics-dt`), not the world server's split.

- **P1 held.** Every scan's offsets run 0 to 49.977 ms, median 24.37 ms: one revolution at 20 Hz.
- **P2 FAILED, and the other way.** Each cloud arrives 133.3 ms after its first point (`/clock`
  at receipt less the header, every scan). aib's own first-scan log says the same: "first at
  world 0.200 s (clock 0.283 s)", the first point 83.3 ms before the frame the cloud was built
  in. The runs' format stamps a scan at that frame less 2 frames (100 ms): so that stamp falls
  **16.7 ms before** the first point and 41 ms before the points' median, where P2 predicted 50
  ms and 25 ms after.
- **P3:** if the points' times were the time of the pose the scan was rendered from, a stamp
  before them would put localization *ahead* of the car; the runs have it 30 to 37 ms *behind*.
  So the annotator's per-point times are not the render pose's time, and stamping a scan at its
  points' median would move the stamp the wrong way (later, by 41 ms). They do not explain the
  lag. The 16.7 ms is exactly one of this runner's substeps, so the annotator's clock and aib's
  differ by a substep here at least; under the world server (its own substeps) that offset may
  differ.
- *So:* step 1 cannot locate the lag; step 2 (the scan's geometry against the fixture at the
  stamp and around it, while moving) has to, as planned. Nothing changed in code.

## Step 2: where a scan's points put a fixed target, while moving (243, 2026-11-27, before the run)

Approved by 133 as a measurement only. On the straight nothing lies along the road for the lidar
to range against, so the probe adds targets: R1's scenario (`fixture_c170_down_hold.xosc`, the
full stack as the runs, the Tesla, `max_velocity` 11.11) with two parked `tesla_model3` entities
off the road, at (60, -6.0) and (540, -6.0), heading 0, z 0 (2 m beyond the road's 4.0 m edge,
outside every lanelet), so their rear faces look at the ego as it comes. The raw cloud
(`/sensing/lidar/top/pointcloud_before_sync`, the runs' `xyzirc`) is recorded with everything
the runs recorded; the testbench's only other change.

*The measure.* Each scan's points, through the recorded `/tf_static` (top to base_link) and the
truth's pose (the gap trace's `sim_pose`, interpolated) at the scan's stamp, into the map. A
target's rear face is the points within 0.15 m of the nearest point in x, in a box around the
target; X(stamp) is their median x. Points rendered from the sensor at time t_r and placed with
the pose at the stamp land at the true face plus v (stamp - t_r) in x. So with X_0 the face's x
measured while the ego stands at the start (v = 0, no time dependence),
tau = (X(stamp) - X_0) / v for each moving scan, the target at x 60 from the start's
acceleration, the one at x 540 at cruise and in the braking.

*Predictions:*
- Q1: tau from the faces is 30 to 37 ms (the speed split's), constant with v: the scan's stamp
  is that much later than the pose it was rendered from, and the lag is in the cloud's stamp.
- Q2, the alternative: tau from the faces under 5 ms. Then the cloud's stamp is right, and the
  along error the runs show comes from the other side of the comparison: the truth (the gap
  trace's `sim_pose` stamped 30 to 37 ms early for the pose it holds) or from NDT and the EKF
  after the scan.
- Q3: the same tau at x 60 (accelerating, 1 to 8 m/s) and x 540 (11 m/s and braking).

## Step 2's result (243, 2026-11-27)

Run `2026-11-27T09-38-02_fixture_c170_targets_r0` on host 243 (fcc01e50's install), passed; the
raw cloud recorded (2.5 GB). A first attempt refused at the preprocessor (my scenario: the
targets' catalog reference lacked its parameter assignments) and ran nothing. `face196.py`,
`/var/tmp/aeon/170/g1b/face196.json`.

- *The calibration:* standing (119 scans before the first motion), target_a's rear face is
  d = -0.915 m from its pose (spread -0.915 to -0.894 m).
- *target_a* (passed while accelerating, 1.0 to 8.5 m/s, 154 scans): **tau 34.3 ms** (p10 33.2,
  p90 38.5); by speed 34.6 (1 to 4 m/s), 34.4 (4 to 7), 34.0 ms (7 to 10).
- *target_b* (at cruise and braking, 8.0 to 11.1 m/s, 87 scans): **tau 33.7 ms** (p10 33.2,
  p90 34.9); 33.7 ms in both speed bins.
- **Q1 held:** 33.7 to 34.3 ms, inside the speed split's 30 to 37. **Q3 held:** the same at both
  targets and flat with speed (within 0.6 ms from 1 to 11 m/s). A scan's points are placed where
  the sensor was 34 ms before the scan's stamp.
- **Q2 as written was wrong, and is settled another way.** The faces compare the cloud's stamp
  with the truth's time, as the speed split did, so a truth stamped 34 ms early would look the
  same. The GNSS separates them: its pose is computed from aib's vehicle state at the frame it is
  published with, and its along error against the truth is +0.0273 m at every speed (sd 1.3 mm,
  R1 to R3), all of it gnss_poser's lever (170, the GNSS section). A 34 ms offset between aib's
  state and the truth would add 0.37 m at 11 m/s. So the truth and aib's state agree in time, and
  **the lag is in the cloud's stamp:** later than the pose the scan was rendered from by 34 ms.
- *A number to note, not a reading:* 34 ms is about two thirds of the 50 ms frame (33.3 ms), or
  two 1/60 s substeps; step 1 found the annotator's clock one 1/60 s substep off aib's under the
  runner. Which substep's pose the render takes is the open part, and is what a fix needs.

## Step 3: which substep's pose the render takes (243, 2026-11-27; from the code, a plan)

*The frame, from the code.* The world server steps physics at 1/60 s (`max_physics_dt`,
`world.set_simulation_dt`), so a 0.05 s frame is three substeps (`world.py`, `step`'s loop). Before
each substep every ego's `before_substep` runs, and the lidar's (`aib/isaac/sensors.py`) sets its
prim (`translate.Set`, `orient.Set`) to the pose the vehicle will have *after* that substep
(`_pose_after`: the last substep's body moved on at its velocities). Only the third substep's
`world.step` renders (`rendering = render and s == substeps - 1`). So just before the render the
prim holds the frame's end pose E, the time the scan is stamped with (2 frames later, `latency`).
If the render used it, tau would be 0.

*What the numbers say.* tau is 33.7 to 34.3 ms (step 2) and 30 to 37 ms (the speed split): two
substeps, 2/60 s = 33.3 ms. The pose that fits is the one set before the *first* substep, E less
two substeps: as if the renderer takes the prim's transform as it stood after the first write
since the last render, and the writes before substeps 2 and 3 reach it only at the next render.
Under the runner (also 1/60 s substeps) step 1 found the annotator's clock one substep off aib's,
another sign that the renderer's view of time and pose trails the USD writes. Not confirmed;
the code read here does not show where the renderer reads the transform.

*H (stated so it can fail):* the render takes the pose written before substep 1 of its frame, so
tau = (n - 1) x physics_dt for n substeps a frame.
- With physics_dt 1/40 (two substeps of 0.025 s): tau = 25 ms.
- With physics_dt 1/120 (six substeps): tau = 41.7 ms.
- *Not H:* tau stays near 34 ms whatever the substep (a fixed render latency in time), or
  scales with the frame, not the substep.

*The test (one run each, the targets scenario of step 2, the card guard; measurement only):*
the same `face196.py` reading at two physics steps. The world server's physics step comes from
the bridge's Hello (`max_physics_dt`); how a run sets it (a stack argument or the bridge's config)
is checked before the predictions are committed.

*Fix options for after the test (not now):*
- stamp a scan at the time of the pose it was rendered from (E less (n - 1) substeps), if H holds:
  one line in aib, exact for any n;
- or write the prim once a frame, before the first substep, at the frame's end pose (predicted
  over the frame), so the pose the render takes is the stamp's;
- or have the renderer see each write (a USD to Fabric sync before the render), if the render's
  read is the cause; the costliest and the least sure.

## Step 3: how a run sets the physics step, and the runs (243, 2026-11-27, before any run)

*How it is set.* A testbench's `isaac: {physics_hz: N}` (scensim `world.py`, ISAAC_KEYS) goes to
the Isaac world server as `--physics-hz`; the world sets `physics_dt = 1 / N` and announces it
in Hello as `max_physics_dt`; the bridge splits each 0.05 s SSv2 frame into the fewest substeps
of at most that (`physics_steps`, `scenario_world_bridge/src/backend/remote/mod.rs`:
n = ceil(0.05 N), dt = 0.05 / n). So 60 Hz is 3 x 1/60 s (step 2), 40 Hz 2 x 0.025 s, 120 Hz
6 x 1/120 s. The render stays on the last substep and the frame stays 0.05 s.

*The runs.* Step 2's targets testbench (`170/proj`, `fixture_c170_targets.xosc`, the Tesla,
`max_velocity` 11.11, the raw cloud recorded) three times, changed only in `isaac.physics_hz`:
60 (a control: main has moved aib and the Isaac world server since step 2's fcc01e50 build), 40,
120. On 118's GPU0 (133's offer), from main's code, both workspaces built from a clean
environment. Package: NAS `home/2026-11-27 issue 196 step 3 (243)` (three projects, the fixture
copied into each, `face196.py`, SHA256SUMS). Read with `face196.py <run dir>`, as step 2.

*Predictions* (tau from the faces, median over each target's moving scans):
- S0, 60 Hz on main: 33 to 35 ms at both targets (step 2's 33.7 and 34.3); else stop: the build
  moved the lag, and the other two runs would not read against step 2.
- H (above): 40 Hz gives 25 ms (24 to 27), 120 Hz 41.7 ms (40 to 44), flat with speed.
- Not H, a fixed render latency in time: about 34 ms at both rates.
- Not H, two substeps whatever their length: 50 ms at 40 Hz, 16.7 ms at 120 Hz.
- At 40 Hz the car's own dynamics take a coarser step; the run may drive differently, which does
  not touch tau (the faces divide by the truth's speed). A run that errors at the world server
  or the vehicle at 40 or 120 Hz is a result, reported as it stands, not retried with changes.
