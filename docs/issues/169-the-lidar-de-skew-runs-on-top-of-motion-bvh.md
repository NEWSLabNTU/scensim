# 169: with motion BVH on, Isaac's lidar cloud may carry the sensor's motion with no point times to undo it

*Retitled before any valid run (118, 2026-11-25, from the code and C6e2's logs; 133's OK).* The
first title was "aib's lidar de-skew runs on top of motion BVH's own sensor motion". Its premise
FAILED, as the next section says. The file keeps its first name, so links stay valid.

**Status:** open; step 1 done (2026-11-25): the candidate supported by the cloud's geometry, and a latent aib defect found; step 2 to plan. **Severity:** none today, since motion
BVH is off in every run (issue 138), but it blocks turning motion BVH on. With it on,
localization runs about 0.108 m ahead of the car at 4.5 m/s. **Found:** 2026-11-25, scensim
118, 086 C6e2 (numbered by 133).

## What happens

086 C6e2 ran smooth haruna_down three times with motion BVH off and three times with it on
(`ISAAC_KIT_ARGS` with SimulationApp's `enable_motion_bvh` settings). Localization's error
against the truth, median above 1 m/s (`c6e2/along.py`):

| side | along the track | across | pose error p95 |
|---|---|---|---|
| off (f1, f2, f3) | +0.007 m | -0.065 to -0.067 m | 0.118 to 0.120 m |
| on (o1, o2, o3) | +0.107 to +0.109 m | -0.070 to -0.071 m | 0.188 to 0.191 m |

NVTL p05 is the same on both sides (3.119 to 3.120). Record: NAS "2026-11-25 086 C6e2 motion BVH
cost (118)".

## The first premise: FAILED (from the code and the logs, before any valid run)

The first "why" below assumed that aib adds a spinning lidar's motion to every cloud. It does
not, in any run so far. aib's per-point times and its `motion_distortion` are on only when the
rig's lidar has `point_format: xyzircaedt` (`aib/isaac/sensors.py`, `point_format` defaults to
`xyzirc`; `point_times` and `distort` need `xyzircaedt`). Nothing in the stack sets it:
`tesla_model3.rig.yaml` names no `point_format`. At scensim main 0291abb3's pins, `git grep`
finds `xyzircaedt` only in aib's `sensors.py` and `sensing.py`. C6e2's logs agree. aib logs "N
points a revolution over X ms" only when point times are on, and the line is absent from C6e2's
runs, both arms. So the cloud went out as `xyzirc`, with no time field and no motion from aib.

**The candidate in its place (a hypothesis, untested).** With motion BVH on, the renderer
itself puts the sensor's motion within a revolution into the points. The cloud carries no
per-point times, so Autoware's distortion corrector cannot remove it, and localization runs
ahead by about half a revolution's motion (0.108 m at 4.5 m/s is about 24 ms, half a 50 ms
turn). Without motion BVH the cloud carries no motion at all: it is self-consistent, but it is
not what a real lidar gives.

## Why (the first hypothesis, kept as written; its premise FAILED above)

aib's `Lidar._msg` de-skews each point along the sensor's own track (`motion_distort`, by the
point's firing time). It assumes the render saw the whole revolution from the one pose it was
rendered from, `latency` frames back. Without motion BVH that is what Isaac's RTX lidar does,
and the de-skew puts in the motion a real spinning lidar sees. With motion BVH, the renderer
may already trace each point from the sensor's pose at its firing time, so the de-skew moves
the points a second time. 0.108 m at 4.5 m/s is 24 ms, about half of a 50 ms revolution, which
is the mean offset that counting the motion twice over a revolution would give.

## The end state (133)

A real OS1 scans while it moves, so with the fix motion BVH may be the more faithful mode. The
end state is the de-skew skipped, or adjusted, when motion BVH renders each point from its own
pose. Motion BVH's effect on localization is then measured again, C6e2's pairing repeated.

## Steps (predictions written before each, when taken up)

1. Confirm what the render does with motion BVH. The probe: a lidar moving at a known speed past
   a wall square to its track, with motion BVH off and on, de-skew off. A wall square to the
   track shows the skew as a slant across the scan.
2. The fix in aib: the de-skew made aware of motion BVH (a rig or world setting), or skipped
   when Kit's `/renderer/raytracingMotion/enabled` is set.
3. C6e2's pairing again, on the fix.

## Step 1's spec: the two-wall probe (written 2026-11-25, before any code or run)

One correction to the wording above, made from reading the code while writing this (not from a
run). aib's `motion_distort` (`aib/sensing.py`, used by `Lidar._msg`) does not de-skew. It adds
the distortion a real spinning lidar has: each point goes to the world through the pose the
revolution was rendered from (`latency` frames back), then back through the sensor's pose at that
point's firing time. Autoware's distortion corrector undoes it, as on a vehicle. The hypothesis
stays the same in substance. With motion BVH on, if the renderer already traces each point from
its firing pose, aib adds the same motion a second time, and Autoware removes it only once.

**The probe** (`isaac-ex/i169/probe169.py`; no Autoware, no road layer, GPU0, non-timing). aib's
Model 3 lidar (`aib.isaac.sensors.Lidar`, the rig's sensor and its `isaac:` keys) sits on a
kinematic root at the rig's height. The root is moved along +x at a constant speed v by setting
its pose every substep. The ground is a flat plane. Two walls stand square to the track: one
20 m ahead of the start, one 20 m behind it, each 10 m wide and 4 m tall. The probe reads the
published cloud (`pack_cloud`'s points and per-point times), takes each wall's returns (the
points within 0.5 m of its plane and inside its width), and their median x in the sensor frame
and median firing time. Per revolution it computes:

- D, the measured distance between the walls (ahead's x minus behind's x, in the frame the cloud
  is published in);
- dt, the firing time of the wall behind minus the wall ahead;
- k = (D - D_true) / (v * dt), the number of times the sensor's motion between the two walls'
  firings is in the cloud. D_true is 40 m, and the walls' x are taken from the stage.

A real spinning lidar gives k = 1, because the sensor moved v * dt between the two firings. A
render from one pose gives k = 0.

**Cases.** Each runs 3 s after a 2 s settle, at v = 4.5 m/s (haruna_down's speed, C6e2) and at
v = 0 (a control). Motion BVH uses the Kit arguments C6e2 used (`ISAAC_KIT_ARGS`).

| case | motion BVH | aib's `motion_distortion` | predicted k at 4.5 m/s |
|---|---|---|---|
| A | off | off | 0 |
| B | off | on (production) | 1 |
| C | on | off | 1 if the hypothesis holds; 0 if motion BVH moves only the scene's objects, not the sensor |
| D | on | on | 2 if the hypothesis holds; 1 otherwise |

**Added before any run (133, 2026-11-25).** Cases B and C run again at 9 m/s, with the same k
predicted within 0.15: k must not depend on v, or the measure is wrong. The size of the bar in
metres: the rig's OS1 (`OS1_REV7_128ch20hz1024res`, `rate_hz` 20) turns once in 50 ms, and the
two walls are half a turn apart, so |dt| is about 25 ms. Then v * dt is about 0.1125 m at
4.5 m/s and about 0.225 m at 9 m/s, and 0.15 in k is about 0.017 m and 0.034 m of D. The order
is the v = 0 controls first; the probe stops if they fail.

| case | v | predicted k (hypothesis) | predicted D - D_true | 0.15 in k |
|---|---|---|---|---|
| A, B, C, D | 0 | n/a | 0 (within 0.01 m) | n/a |
| A | 4.5 m/s | 0 | 0 | 0.017 m |
| B | 4.5 m/s | 1 | about 0.11 m | 0.017 m |
| C | 4.5 m/s | 1 | about 0.11 m | 0.017 m |
| D | 4.5 m/s | 2 | about 0.23 m | 0.017 m |
| B | 9 m/s | 1 | about 0.23 m | 0.034 m |
| C | 9 m/s | 1 | about 0.23 m | 0.034 m |

The sign of D - D_true follows the spin's direction relative to the travel. The table gives
magnitudes; k is signed by the measured dt.

**Predictions (before any run).**

- At v = 0, every case: |D - D_true| at most 0.01 m (the walls' returns' spread). If not, the
  probe's geometry is wrong and nothing else is read.
- A and B: k within 0.15 of 0 and of 1. These check the probe on what the code says.
- C and D: the hypothesis predicts k 1 and 2. *Hypothesis:* C6e2's +0.108 m along the track at
  4.5 m/s is k's extra 1 over about half a revolution (24 ms). With the walls half a revolution
  apart, D's excess in C and D's extra over B are both about v * dt, about 0.11 m at a 20 Hz
  revolution.
- If C gives k = 0, the hypothesis fails. C6e2's 0.108 m then has another cause, and step 2
  changes to finding it.

**Amended before any valid run (118 and 133, 2026-11-25), after the premise above failed.**

- *The probe's defects, recorded.* The four v = 0 controls first ran 18:33 to 18:35 and gave no
  valid result, through defects in the probe, not failures of the controls. The walls were not
  seen: first a one-sided quad, then a `UsdGeom.Cube`; they are now double-sided meshes, which
  are seen. The published frame is turned 90 deg (the walls at y +-40), so the probe now
  projects each point on the track's axis and across it, from aib's `sensor_mount` and
  `q_emit`. The controls are rerun first with the fixed probe, and the probe stops if they fail.
- *Cases A to D* run with `point_format: xyzircaedt`, so the cloud carries point times, and with
  `motion_distortion` toggled on its own. Their predicted k are unchanged. C, motion BVH with
  aib adding nothing, is the case that explains production.
- *Cases E and F measure production as it runs*: `xyzirc` (no point times, so aib adds nothing),
  E with motion BVH off and F with it on, each at 4.5 and 9 m/s. They carry no point times, so
  they are judged on D - D_true in metres against a nominal dt. dt_nominal is half a turn
  (the walls lie at azimuths 0 and 180 deg; 20 Hz): 25 ms, with its sign the measured dt's sign
  in case A (the spin's direction). Predicted: E is 0 within 0.01 m. If the candidate holds, F
  is about v x dt_nominal (0.1125 m at 4.5 m/s, 0.225 m at 9 m/s), within 0.15 of it in k
  (0.017 m and 0.034 m), the same sign and size as C at the same v. E and F are what
  production does; A to D explain why.

**What decides step 2.** If C is about 1 (within 0.15), the fix is aib's `motion_distortion`
skipped when Kit's `/renderer/raytracingMotion/enabled` is set, read from the settings at
start-up, with a log line saying which. If C is about 0, there is no fix in aib for this. The
issue is re-opened on the measurement.

## Step 1's result (2026-11-25, 118, GPU0, 18:37 to 18:41; non-timing, codec 118 told)

`isaac-ex/i169/probe169.py` (`run.sh`), aib bb2283f and siw 4706ff9 (scensim main 0291abb3's
pins, worktree `ws-c6e3`). Each case is one process: a 2 s settle, then 3 s moving, 56
revolutions judged per moving case (past the render's latency after the start).

- *The controls (v = 0), rerun with the fixed probe:* |D - D_true| is 0.000 m in all six (A0 to
  F0), so the probe's geometry holds. In A0 the wall behind is hit 24.98 ms after the wall
  ahead, so the spin's sign is + and dt_nominal is +25 ms. **Held.**
- *The moving cases* (D - D_true is the median of 56 revolutions, with p10 to p90; k is its median):

  | case | format | motion BVH | aib's distortion | v | D - D_true | k | predicted k | |
  |---|---|---|---|---|---|---|---|---|
  | A | xyzircaedt | off | off | 4.5 m/s | 0.000 m | 0.000 | 0 | **held** |
  | B | xyzircaedt | off | on | 4.5 m/s | 0.000 m | 0.000 | 1 | **FAILED** |
  | C | xyzircaedt | on | off | 4.5 m/s | +0.1121 m (0.1119 to 0.1123) | 0.996 | 1 (the hypothesis) | **held** |
  | D | xyzircaedt | on | on | 4.5 m/s | +0.1121 m | 0.996 | 2 (the hypothesis) | **FAILED** |
  | B | xyzircaedt | off | on | 9 m/s | 0.000 m | 0.000 | 1 | **FAILED** |
  | C | xyzircaedt | on | off | 9 m/s | +0.2241 m (0.2233 to 0.2251) | 0.996 | 1 | **held** |
  | E | xyzirc | off | (none) | 4.5 m/s | 0.000 m | | 0 within 0.01 m | **held** |
  | F | xyzirc | on | (none) | 4.5 m/s | +0.1121 m | | about 0.1125 m (v x dt_nominal) | **held** |
  | E | xyzirc | off | (none) | 9 m/s | 0.000 m | | 0 within 0.01 m | **held** |
  | F | xyzirc | on | (none) | 9 m/s | +0.2241 m | | about 0.225 m | **held** |

  k does not depend on v: C gives 0.996 at both speeds, and B 0.000 at both. **Held.**
- *What it shows.* With motion BVH on, the renderer traces each point from the sensor's pose at
  its firing time (C, F: k 0.996), as a real spinning lidar measures. Production's cloud (F,
  `xyzirc`) carries that motion with no point times, so Autoware's distortion corrector cannot
  take it out. Its size, v x half a turn, is C6e2's +0.108 m at 4.5 m/s. That is the candidate
  of the amended "why", supported by the cloud's geometry. The link to localization itself
  (NDT run on such clouds) is not measured here. With motion BVH off, the cloud carries no
  motion (E: 0.000).
- *Why B and D failed: a second finding, aib's latent defect (from instrumenting the probe, after
  the result; labelled).* With `xyzircaedt`, aib's `motion_distort` gets the annotator's point
  times 5.000 to 5.050 s when the lidar's track ends at 5.000 s and the render was 0.1 s earlier
  (t_ref 4.900; the walls confirm the data is two frames old). Every point's time lies past the
  track's end, so `_pose_at` takes the last pose for all of them. aib adds no motion within the
  revolution (k 0); it shifts the whole cloud by v x 0.1 s instead (B's walls 0.450 m nearer
  than A's at 4.5 m/s, and D's 0.450 m nearer than C's). The annotator's timestamps are
  therefore those of the frame the data is read in, not the one it was rendered in. No run uses
  `xyzircaedt` today, so the defect is latent, but it bears on step 2: a scan stamped from these
  times would also be 0.1 s late.

## Step 2 (to plan, for 133)

Production with motion BVH on needs the cloud's motion to be removable. Two ways:
(1) aib publishes `xyzircaedt` with each point's firing time taken as render time plus its
offset (the latency taken out of the annotator's times), its own distortion off when Kit's
`/renderer/raytracingMotion/enabled` is set, and the header stamped at the render, so that
Autoware's corrector undoes the renderer's motion as on a vehicle; or (2) aib removes the
renderer's motion itself before publishing `xyzirc`. Either way, aib's `motion_distort` time
base is fixed first (the latent defect above). Then C6e2's pairing again, on the fix.
