# 196: a lidar scan on Isaac is stamped about 30 ms after the pose it was rendered from

**Status:** open again (2026-11-27): L2 (aib dda18ad, the stamp back-dated (n - 1) substeps) made NDT drift +1.7 % of the distance and was reverted (L2r, aib 757fb53); L2b is the candidate. **Severity:** medium. Localization sits behind the car by
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

## Step 3's result (118's runs, 2026-11-27; read by 243)

Three runs on 118's GPU0, main 53b76a47's code (37402fd2 is docs only over it), each passed with
exit 0 and no guard stop: 60 Hz at 10:41, 40 Hz at 10:44, 120 Hz at 10:47. `face196.py`; tau in
ms as median (p10, p90), by speed bin, n scans:

| physics | n substeps | (n - 1) dt | target_a | target_b | face d (m) |
|---|---|---|---|---|---|
| 60 Hz | 3 | 33.3 | 34.4 (32.1, 36.4); 34.2 / 34.7 / 34.2; 154 | 33.6 (33.2, 34.7); 33.7 / 33.6; 87 | -0.9148 |
| 40 Hz | 2 | 25.0 | 26.1 (24.9, 29.5); 26.6 / 26.0 / 25.8; 150 | 25.6 (25.0, 26.4); 25.6 / 25.6; 88 | -0.9166 |
| 120 Hz | 6 | 41.7 | 42.7 (41.4, 45.5); 43.7 / 42.7 / 42.1; 153 | 42.2 (41.7, 43.3); 42.2 / 42.3; 86 | -0.9168 |

Speed bins: target_a 1 to 4, 4 to 7, 7 to 10 m/s; target_b 7 to 10, 10 to 13 m/s. The car
started moving at 7.10, 6.55 and 8.50 s.

- S0 held: 60 Hz on main reads 34.4 and 33.6 ms, as step 2 (34.3 and 33.7).
- H held: 40 Hz 25.6 to 26.1 ms (predicted 24 to 27), 120 Hz 42.2 to 42.7 ms (40 to 44), flat
  with speed at every rate.
- Both alternatives fail: a fixed latency would read about 34 ms at all three; two substeps would
  read 50 and 16.7 ms.
- Each rate reads 0.5 to 1.1 ms above (n - 1) dt, about 0.8 ms on average, the same at all three:
  a constant left over after the substeps, not a part of H.

So the render takes the lidar prim's pose as written before the first substep of its frame, and
a scan stamped at the frame's end is (n - 1) x physics_dt late. Step 1's one-substep offset of the
annotator's clock under the runner fits the same picture. The fix options above stand; the first
(stamp the scan at the frame's end less (n - 1) substeps) is now exact for any physics rate, with
about 0.8 ms left to explain. Logs: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 196 step 3
(118)` (run dirs without the raw bags, face196's JSON and rows per run, provenance; the bags
stay on 118, `runs_on_118.txt`).

## The fix (batch L, L2): the scan stamped at the pose it was rendered from (243, 2026-11-27, a plan, before any code)

Of the three options above, the first: aib stamps a scan with the time of the pose the render
took, the frame's end less (n - 1) substeps, which step 3 showed exact at 40, 60 and 120 Hz.
The second (one prim write a frame, at a predicted end pose) changes what the render sees and
needs its own measurement; the third depends on the renderer. The first changes only the stamp.

*The change, in aib's `Lidar` (`aib/isaac/sensors.py`).*
- `before_substep` keeps the world clock at the end of the frame's first substep (the pose
  written before it is the one the render takes).
- `publish` records, for the frame just stepped, its stamp less the clock from that first
  substep's end to the frame's end, `(n - 1) dt`: `ros.stamp(sim_time - (clock - first))`, in
  place of the frame's end. A scan read `latency` frames later goes out with it, as now.
- Motion distortion's reference (`t_ref`, the pose the revolution was rendered from) moves the
  same `(n - 1) dt` back, so a point's correction starts from the pose the render used.
- The per-point-time path (`point_times`, `xyzircaedt`) takes its stamp from the annotator's own
  timestamps, which step 1 found one substep off aib's clock under the runner. It is left as it
  is in L2 and named in L3's reading; the Tesla rig scensim runs publishes `xyzirc`, the path
  changed here.
- No setting keeps the old stamp: the old stamp was wrong (no shims).

*Tests first (aib, its fake kit):* a frame of n substeps of dt stamps its scan at the frame's end
less (n - 1) dt for n = 2, 3, 6; the first frame after a teleport (no last body) does the same;
the stamp a scan goes out with is its render frame's, `latency` frames on; motion distortion's
reference moves with it.

*Predictions for L3* (after L1 and L2, the same targets scenario and `face196.py` as step 3):
- tau from the faces under 2 ms at 40, 60 and 120 Hz (step 3's 0.5 to 1.1 ms residual may stay);
- the drive's along error on fixture_c170 at 10 to 12 m/s within 0.05 m of zero (the baseline
  N4: -0.39 m), on the rebuilt and the old map alike;
- NDT's NVTL during the drive no lower than the baseline's (the stamp no longer pairs a scan
  with a pose 34 ms off).

## L3's F: the fix against step 3, and a 40 Hz A/B (243, 2026-11-27; the A/B's predictions before its runs)

*F's results* (118's runs on b1700191, L2's pins: aib dda18ad; `fixture_c170_targets` and, for
120 Hz, `fixture_c170_targets_pass`; `face196.py` unedited; tau in ms, median, target_a /
target_b): 60 Hz +1.0 / +0.6, 120 Hz +1.1 / +0.6, 40 Hz -24.0 / -24.3. L3's P4 (under 2 ms at all
three) holds at 60 and 120 Hz and fails at 40 Hz. Runs on NAS `autoveh/logs/2026 SSv2 on
CARLA/2026-11-27 issue 195 L3 (118)/runs/` (F40b `2026-11-27T14-15-24`, F60 `14-27-33`, F120b
`15-06-04`).

*What the 40 Hz run shows.* Its scans' stamps sit at .025 and .075 s (12072 of 12072 steps 50.0
ms), against .000 and .050 in step 3's 40 Hz run (2203 of 2203): L2 moved each stamp back one 25
ms substep, as designed. A stamp 25 ms earlier turns step 3's +25.6 ms into about +0.6, not
-24. So between step 3's run (main 53b76a47, aib before L1) and F40b, the pose the 40 Hz render
took also moved, by about one substep, and not through the stamp. At 60 and 120 Hz nothing of
the kind shows (the residuals match step 3's 0.5 to 1.1 ms).

*The A/B.* 118's GPU0, back to back on one host and stack configuration, at 40 Hz,
`fixture_c170_targets_pass` (sha256 ee7f4249): A on eb741eda (the pins before L2: aib ca600c4),
B on b1700191 (aib dda18ad). Only L2 differs. Each run also logs, from a debug patch applied
alike to both builds' world server (its diff and sha256 recorded, not landed), per frame for
the first 200 frames and every 100th after: the substep count n, dt, the frame's start time
and the end of its first substep, and on which substep the render was asked for.

*Predictions.*
- AB0: both runs step n = 2, dt = 0.025 s, the render on the second substep, in every logged
  frame.
- AB1, if L2 is the only change: A reads tau +24 to +27 ms (step 3's), B -1 to +2 ms; F40b's
  -24 was then a property of that run or stack, not of L2, and B says which.
- AB2, the alternative: A reads about 0 ms and B about -25 ms. Then the 40 Hz render's pose
  moved by one substep between 53b76a47 and eb741eda, independently of L2, and L2's
  (n - 1) dt overcorrects at 40 Hz on current code. The substep log (AB0) then says whether
  the scheduling changed or the render did.
- If AB0 fails (n or the render substep differ from the above), that is the finding, whichever
  of AB1 and AB2 holds.

## The 40 Hz A/B: results (118's runs, 2026-11-27 15:36 to 15:41; tables by 243)

Both on 118's GPU0, back to back, `fixture_c170_targets_pass` (ee7f4249), physics_hz 40, map A
(9cc1a29f), /clock recorded, each build from a clean environment at its SHA, with
`ab196_debug_patch.py` (sha256 97ce5ce2; world.py 782d17fe patched to 864a2416, removed after
each run; recorded in each run's provenance).

| run | build | result | target_a tau (ms) | target_b tau (ms) | lidar stamps | stamp less the /clock before it |
|---|---|---|---|---|---|---|
| A `2026-11-27T15-37-17` (retry; `15-36-53` refused at the start) | eb741eda (aib ca600c4) | passed | +1.2 (0.1, 4.7); n 150 | +0.5 (0.0, 1.5); n 87 | on the frame grid | -150 ms |
| B `15-40-10`, retry `15-40-33` | b1700191 (aib dda18ad) | both refused at the start (pre-L1b GNSS) | none: the ego never moved | none | 25 ms off the grid | -175 ms |

The substep log: every logged frame of both runs (212 and 203 lines) steps n 2, dt 0.025 s, the
render on the second substep, except frame 1 (no render).

*Against the predictions.* AB0 holds. AB1 fails: A reads +1.2 ms, not +24 to +27. AB2's half that
can be read holds (A about 0); B gave no tau. Between step 3's build (53b76a47: aib 4c6b144,
siw 542cfae) and A's (eb741eda: aib ca600c4, siw 95e7fb4) the only aib and siw commits are A9's
GNSS error (ca600c4, and siw's pin of it), which does not touch the lidar or the render. So the
same 40 Hz schedule (n 2, render on the second substep) gave a 25 ms lag in step 3's run and none
in A's and in F40b's (whose -24 ms under L2 is L2's 25 ms with no lag to remove).

*Reading (243).* At 40 Hz the render's pose differs between runs on the same code: the pose
written before the frame's first substep in step 3, before its second (the frame's end) in A and
F40b. At 60 and 120 Hz every run so far took the first substep's (step 2, step 3, F60 and F120
under L2 at +1 ms). Not shown: what picks it per run. If it is a per-run phase, a stamp that
assumes (n - 1) dt is right only in the runs that took the first substep's pose, and the stamp
should come from the pose the render actually took (the annotator's `info` transform, issue
172's observable) rather than from the schedule.

## The 40 Hz repeat: plan and predictions (243, before any run)

Pre-L2 build (eb741eda) so that a run's tau is its render lag itself, the same scenario and
patch as the A/B, on 118's GPU0, a fresh stack each: six runs at 40 Hz and four at 60 Hz,
in the order 40, 40, 60, 40, 40, 60, 40, 60, 40, 60. Each run's tau, stamp phase and substep log
are read as above.

*Predictions.*
- R1, if the 40 Hz lag is a per-run phase: the six 40 Hz runs split between about 0 and about
  +25 ms (each within 3 ms of one of the two), at least one of each.
- R2, if it is not (step 3's +25.6 the odd one out): all six read within 3 ms of 0.
- R3: the four 60 Hz runs each read within 3 ms of +33.3 ms (no second mode at 60 Hz).

The default physics rate is 60 Hz (`physics_hz`, the world server's), where L2 holds (F60 +1.0
and +0.6 ms); the 40 Hz case does not block L3, which runs at the default. Each repeat run also
records, if the annotator gives it, the pose the render took (its `info` transform), so each
frame's render pose can be timed against the stamp L2 assigns: the basis of a stamp taken from
the render itself.

## The repeat: results (118's runs, 2026-11-27 15:49 to 16:24; tables by 243)

Ten counted runs on 118's GPU0, eb741eda (before L2: aib ca600c4, siw 95e7fb4), a fresh stack
each, `fixture_c170_targets_pass` (ee7f4249), both run-only patches in every try
(`ab196_debug_patch.py` 97ce5ce2, `ab196_render_pose_patch.py` ce84795b; shas in each run's
provenance). S03 and S04 each needed a second try after a refused start. The render-pose patch
printed its pose without the 1000 s base the stamps carry (243's bug); 118 took it off offline
and kept the raw lines. Runs: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 195 L3
(118)/series/`.

| run | physics | tau target_a / target_b (ms) | first lidar stamp | stamp less the /clock before it | render pose's time less the stamp (above 1 m/s) |
|---|---|---|---|---|---|
| S01 | 40 Hz | +1.3 / +0.5 | 1000.10 | -150 ms | 0.0 ms (p10 0.0, p90 0.0) |
| S02 | 40 Hz | +26.3 / +25.6 | 1000.10 | -150 | 0.0 |
| S03 | 60 Hz | +34.4 / +33.8 | 1015.00 | -150 | 0.0 |
| S04 | 40 Hz | +1.2 / +0.5 | 1015.10 | -150 | 0.0 |
| S05 | 40 Hz | +1.2 / +0.6 | 1015.50 | -150 | 0.0 |
| S06 | 60 Hz | +34.2 / +33.9 | 1000.10 | -150 | 0.0 |
| S07 | 40 Hz | +26.2 / +25.6 | 1000.10 | -150 | 0.0 |
| S08 | 60 Hz | +34.2 / +33.8 | 1015.50 | -150 | 0.0 |
| S09 | 40 Hz | +26.2 / +25.5 | 1000.10 | -150 (16 scans -100) | 0.0 |
| S10 | 60 Hz | +34.3 / +33.8 | 1014.90 | -150 | 0.0 |

In every run the lidar's stamps step 50.0 ms on the frame grid; the substep log is the same in
every run of a rate (n 2, dt 0.025 s or n 3, dt 1/60 s, the render on the last substep); the
annotator's transform matched a pose of the lidar's track to 0.000 m.

*Against the predictions.* R1 holds: the six 40 Hz runs split three at +1.2 to +1.3 ms and three
at +25.5 to +26.3. R2 fails. R3 holds: the four 60 Hz runs read +33.8 to +34.4.

*Reading (243).*
- At 40 Hz the render's geometry comes from one of two poses per run, the frame's end (no lag) or
  the end of its first substep (25 ms), with the same schedule, code and stamps. At 60 Hz all
  runs so far took the first substep's (and at 120 Hz the two runs read so far). What picks
  the mode is per run and not seen here: not the stamp's phase (+1.2 and +26 both start at
  1000.10), not the substep schedule.
- The annotator's `transform` is the pose written last, before the render's substep, in every
  run, including those whose geometry is 26 or 34 ms older. It tells what was written, not what
  the rays were cast from, so a stamp taken from it would be wrong whenever there is a lag. The
  stamp-from-the-render idea is refuted.
- L2's stamp ((n - 1) dt back) is right in the runs that took the first substep's pose and wrong
  by (n - 1) dt in the others. At 60 Hz, the default, no run of the six so far (F60 and the
  repeat's four, step 2) has taken the end's pose; that is evidence, not a guarantee.

*What would make it independent of the mode (a plan for L2b, for 133).* Write the lidar's prim
once a frame, before the first substep, at the pose predicted for the frame's end, and leave it
during the substeps. Whichever substep's write the render picks up is then the same pose, and
the scan is stamped at the frame's end (L2's back-dating removed). The prediction error over a
frame is the car's acceleration's: 0.5 a t^2, about 4 mm at 3 m/s^2 over 50 ms, against 0.37 m
of lag at 11 m/s. This is the second of the three options in "The plan" above; it changes what
the render sees and needs its own measurement: tau within 2 ms at 40, 60 and 120 Hz, in every
run, over six runs at 40 Hz and three each at 60 and 120.

## L2 reverted (L2r): back-dating the stamp breaks the EKF and NDT loop (243, 2026-11-27)

*What L3 found.* With L2 (aib dda18ad: each scan stamped (n - 1) substeps before its frame's
end), NDT's along error grows with the distance driven, and the ego stops short of its goal. On
fixture_c170 at 60 Hz, NDT's along slope against x over the moving scans (118's `l3/along_x.py`,
from the records):

| run | build | map | NDT along slope | ends |
|---|---|---|---|---|
| S06 (the 40/60 Hz repeat) | eb741eda, before L2 | A 9cc1a29f | +0.01 % (flat at +0.69 m) | passed |
| F60 (L3's F) | b1700191, L2 | A | +1.74 % | 9.4 m short, timed out |
| T170_A1 | 2b53c5b5 | A | +1.67 % | 9.3 m short, timed out |
| T170_B1 | 2b53c5b5 | B 2658430d | +1.71 % | 9.5 m short, timed out |

In every run the EKF follows NDT within 0.2 m, the GNSS pose stays on the truth (under 0.06 m
moving), and the twist reads 0.99999 of the truth's speed. NDT's per-scan pull (result less
guess) is about zero (medians -0.4 to +0.4 mm): NDT accepts guesses that are already ahead, so
the drift is in what it is fed, not in the match. 1.67 % is 1/60: one 60 Hz substep's worth of
motion per second. The mechanism is not shown; a stamp that is not the frame's end, against the
EKF's own clock, is the lead.

*L2r* (aib 757fb53, `git revert dda18ad`; siw 54194da): the scan is stamped at its frame's end
again, with the known (n - 1) dt lag. 196 is open again: the lag is real, but moving the stamp
breaks the EKF and NDT loop. The candidate fix is L2b (above: the lidar prim written once a
frame at the frame's end pose, the stamp at the frame's end), to be measured against this drift
first, not only against the faces.

*The check run, predictions before it* (fixture_c170_down_hold120 on map A, after L2r is
pinned, on 118's GPU0):
- K0: the ego reaches the goal; the run passes.
- K1: NDT's along slope against x under 0.1 % of x over the moving scans.
- K2: NDT's along error constant along the road: its median over each 100 m of the drive
  within 0.15 m of the others. Its level is the start's along offset (the align's, pose-free
  since L1; S06 kept +0.69 m) less the old lag, about 0.37 m at 11.1 m/s.

## The L2r check run: results (118's run, 2026-11-27; read by 243)

`2026-11-27T22-20-17_fixture_c170_down_hold120_r0`, map A 9cc1a29f, scensim 23b65448 (aib
757fb53), on 118's GPU0; NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 195 L3
(118)/runs/K_A-...`; the reading by 118's `l3/along_x.py`.

- K0 holds: the ego reached the goal (x 569.6), and the run passed.
- K1 holds: NDT's along slope +0.01 % of x over 1052 moving scans (x 28 to 561), against
  +1.67 to +1.74 % with L2.
- K2 holds as to the spread: the 100 m segment medians of NDT's along error are -0.201, -0.269,
  -0.250, -0.244, -0.238 and -0.143 m (the last the braking into the goal), within 0.126 m of
  each other. Its level misses: the moving median is -0.244 m, against the predicted -0.32 (the
  start's +0.054 less 0.37). The cruise middle (x 100 to 500) reads -0.24 to -0.27, the lag
  at the cruise speed; a prediction error of 0.08 m in the level, recorded as such.

The EKF follows NDT within 0.01 m, the GNSS pose stays within 0.025 m of the truth along, and
NDT's per-scan pull is about zero (median +0.1 mm). L2r removes the drift; the (n - 1) dt lag is
back, as expected.
