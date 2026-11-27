# 195: the ego starts with the align's random heading, up to 0.2 rad off

**Status:** open; the user chose option 1 (through 133, 2026-11-27); its plan below, before any
code. **Severity:** medium. On a featureless straight the ego starts 0.005 to 0.142 rad (0.3 to
8.2 deg) off its true heading, the error differs run to run, and a large one steers the car
across its lane (0.75 m in 6 s in run A) and leaves a lasting bias in the EKF. **Found:** 241's
reading of 118's runs A and B for issue 182 (fixture_c6b, 2026-11-27), and 170 step 4's R1 to R3
(fixture_c170), predicted there as G7.

## What happens

A managed ego's vehicle agent initializes localization at the scenario's start pose through
the AD API, `/api/localization/initialize` (`scensim_agent/adapters/autoware_ros.py`). That
service has no method: Autoware's pose initializer has NDT align the pose (AUTO). The align is
a Tree-Structured Parzen Estimator over x, y, z, roll, pitch and yaw (`initial_pose_estimation`:
`particles_num` 200, `n_startup_trials` 100) that draws x to pitch around the given pose by its
covariance and **yaw uniformly over the full circle** ("Since only yaw is uniformly sampled",
autoware_core `ndt_scan_matcher_core.cpp:1094`, as carried in the overlay). The given yaw is not
its prior; the best score wins. The agent then accepts the result if it lies within 1.0 m and
**0.2 rad** of the scenario's pose (`scensim_agent/adapters/autoware.py:50-51`).

Where the map has features in every direction (Haruna's bends and props), the score is sharp in
yaw and the align lands on the truth. On a flat, featureless straight it is nearly flat in yaw
near the truth: the align stops somewhere within the agent's tolerance, and its score does not
tell a good start from a bad one.

GNSS plays no part: with a relay, `scensim_launch` `pilots/autoware.launch.xml` sets
`gnss_enabled` false, so no automatic GNSS initialization starts and the pose initializer takes
no GNSS pose (170, "The init path"), and the EKF does not take the GNSS pose.

## The measured starts

Yaw less the truth's, standing, before the first motion; the align's best_particle_score.

| run | map | EKF | NDT | score | source |
|---|---|---|---|---|---|
| A | fixture_c6b | +0.071 rad | (not recorded) | 3.312 | 241, issue 182 |
| B | fixture_c6b | -0.143 rad | -0.142 rad | 3.300 | 241, issue 182 |
| R1 | fixture_c170 | +0.028 rad | +0.029 rad | 3.380 | 170 step 4 |
| R2 | fixture_c170 | -0.005 rad | -0.005 rad | 3.369 | 170 step 4 |
| R3 | fixture_c170 | +0.008 rad | +0.008 rad | 3.368 | 170 step 4 |
| 2c x 6 | fixture_c6b | to come (241) | | | issue 182 step 2c |

- The sign and size change from run to run; all are inside the agent's 0.2 rad.
- The score does not order them: R1, the most off of R1 to R3, has the best score; A and B,
  0.21 rad apart, score 3.31 and 3.30.
- The yaw does not move while standing (0.003 rad over 2.5 to 3 s in B).

## What it costs

- **A swerve while NDT recovers.** The controller steers the localized pose onto the lane's
  centre, so the real car walks sideways at v sin(error): in run A 4.17 m/s x 0.027 rad is 0.11
  m/s, about 0.68 m in 6 s against the truth's 0.75 m; in run B the truth's yaw rose to +0.148
  and the car reached y 3.84 while the EKF read 1.4 to 2.6. NDT's error shrinks with distance as
  features come into view (B: -0.142 standing, -0.087 at x 334, -0.018 by x 371).
- **A lasting EKF bias.** In run B the EKF's `estimated_yaw_bias` went from 0 to +0.064 rad and
  stayed after NDT's error had decayed; stopped, the EKF's yaw was +0.052 rad off while NDT's was
  -0.005 (241). A fix has to keep the EKF from learning a wrong start, not only correct the align.
- On fixture_c170 every run swerved right early whatever its start yaw's sign (170, G7), so the
  start heading is one cause of early swerves, not the only one.

## The plan (no code; the user chooses)

**Option 1: tighten the agent's acceptance and re-initialize on a miss.** Set `yaw_tolerance`
from 0.2 to about 0.01 rad (0.6 deg), so an align that lands further off is rejected and the
agent calls initialize again (its retry path exists: `_reinitialize`, `_await_align`).
- For: one value in the agent; keeps the AD API call and Autoware's own align, so the start pose
  stays scan-validated.
- Against: each try is random and about 1 s (R1's align took 0.96 s); of the five starts above,
  two were within 0.01 rad, so it needs about two to three tries on average, more on a worse
  map, with a cap and a failure when it is reached. The score cannot help choose. It still
  leaves up to 0.01 rad (at 10 m/s, 0.1 m/s sideways until NDT corrects), and it compares the
  align with the scenario's pose, which only a simulator knows to be the truth.

**Option 2: initialize directly at the scenario's pose.** The agent calls Autoware's internal
`/localization/initialize` (`tier4_localization_msgs/srv/InitializeLocalization` in 1.5) with
`method: DIRECT` and the scenario's pose: "set directly by the input pose without going through
localization algorithm". NDT and the EKF start at the scenario's pose; NDT tracks from there.
- For: no random search: the start error is the scenario's own (0 in a simulator, where the
  scenario's pose is the truth), the same in every run, and the EKF learns no bias from it. No
  retries.
- Against: an internal service, not the AD API: its package and type differ between Autoware
  releases (1.5's `tier4_localization_msgs`, the 2.x profile's `autoware_internal_localization_msgs`),
  so the agent needs both, chosen as the profile is. No scan check at the start: a wrong scenario
  pose (a start off the map) is taken as given, where AUTO would have found the car. The agent's
  re-initialize after a reset (issue 046's path) would go the same way.

**Recommendation (243):** option 2, with option 1's tighter tolerance kept as a check that the
pose was taken (a DIRECT initialize that the estimate then disagrees with by more than 0.01 rad
is an error, not a retry). In a simulator the scenario's pose is the truth, which is what a
start should be; the run-to-run randomness is the larger cost for a test bench.

**Steps, once chosen:** (1) the agent's failing test first (initialize sends DIRECT with the
scenario's pose; the 2.x type under the 2.x profile); (2) the change; (3) predictions, then a
live check: fixture_c170 R1 to R3 again, start yaw error under 1e-3 rad in all three, and 182's
fixture_c6b run with no start swerve; (4) the gate.

## The user's decision: option 1 (2026-11-27, through 133)

A tight acceptance and a retry, not DIRECT. 133's terms: accept the align only within about
0.01 rad of the scenario's yaw and re-initialize otherwise; a retry cap with a clear failure
naming the last error; log each try's yaw error and score; deal with the EKF's learned yaw bias.

**What the agent does today** (`scensim_agent/adapters/autoware.py`, `AutowareAgent`'s reset):
after `initialize`, the `converge` stage waits until the estimate is `consistent` with the reset
pose (1.0 m, `yaw_tolerance` 0.2 rad), or until `converge_timeout` (30 s), and only then
initializes again (`_reinitialize`, up to `reinitialize_attempts` 3). With 0.01 rad, every align
that lands off would cost the full 30 s before the next try, because a standing car's estimate
does not move toward the pose by itself (B: 0.003 rad in 3 s).

**The change:**
- `yaw_tolerance` 0.01 rad (was 0.2). The position bound stays 1.0 m.
- In `converge`, once the estimate is fresh (newer than the reset, localization INITIALIZED),
  within 1.0 m and more than `yaw_tolerance` off in yaw, the agent initializes again at once
  (a miss, not a wait), logging the try: `align <n> of <cap>: yaw error <e> rad, position error
  <d> m, NVTL <s>` (the score the port has, NDT's newest NVTL; the align's own
  best_particle_score is on `/diagnostics`, which the port does not read, and is not added here).
  A fresh estimate further than 1.0 m off keeps today's path (wait, then `converge_timeout`).
- A cap of its own, `align_attempts` 8, apart from `reinitialize_attempts` (the lost-scan
  repeats of roadmap 072). Of the five starts measured, two were within 0.01 rad, so a try
  lands in about 40 %: eight fail together in about 1.7 %. When the cap is reached the reset
  fails with: `the align landed off the scenario's heading <n> times; the last <e> rad off (NVTL
  <s>), the tolerance <t> rad, at (<x>, <y>)`, which the relay reports as today's failures are.
- A success logs the tries it took and its yaw error.

**The EKF's yaw bias:** each try goes through Autoware's pose initializer, which deactivates the
EKF and starts it again at the aligned pose, and `EKFModule::initialize` sets the yaw bias to 0
(`x(IDX::YAWB) = 0.0`, autoware_core `localization/autoware_ekf_localizer/src/ekf_module.cpp:74`,
tag 1.5.0 as the overlay carries it). So a re-initialize resets the learned bias, and an
accepted start within 0.01 rad gives the bias at most that to learn (run B learned +0.064 rad
from a 0.142 rad start). No change to the EKF.

**Risk:** the same agent drives CARLA's egos. Their align is the same search on CARLA's maps,
which have features; a CARLA start that cannot get within 0.01 rad would now fail after eight
tries where it passed before. `yaw_tolerance` and `align_attempts` stay config keys, so a stack
can set its own; the gate's CARLA lane runs scenarios and would show it.

**Steps:** (1) the failing tests first, in `scensim_agent/test/test_autoware_agent.py` on the
fake Autoware: an align 0.03 rad off is retried at once (not after `converge_timeout`) and the
next, 0.004 rad off, is accepted; each try is logged with its yaw error and NVTL; eight misses
fail with the message above naming the last error; an estimate more than 1.0 m off still waits
for `converge_timeout`; the existing reset tests pass with the new default. (2) The change.
(3) `just gate`. (4) Ask 133 before the push. (5) A live check, predictions first: fixture_c170
R1 to R3 again, every start within 0.01 rad, the tries per start logged.
