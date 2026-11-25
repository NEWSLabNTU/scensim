# 169: aib's lidar de-skew runs on top of motion BVH's own sensor motion

**Status:** open; after 167 and 168 (133, 2026-11-25). **Severity:** none today, since motion
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

## Why (a hypothesis)

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

**What decides step 2.** If C is about 1 (within 0.15), the fix is aib's `motion_distortion`
skipped when Kit's `/renderer/raytracingMotion/enabled` is set, read from the settings at
start-up, with a log line saying which. If C is about 0, there is no fix in aib for this. The
issue is re-opened on the measurement.
