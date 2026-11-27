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

## The six 182 step 2c starts (241, 2026-11-27), and option 1's cap

241's `start182.py` on 182 step 2c's six runs (fixture_c6b_r181, x 320, e6a34fd5): yaw less the
truth's, EKF and NDT, at the first sample and the last before the first motion, and the align's
best_particle_score.

| run | EKF first, last | NDT first, last | score |
|---|---|---|---|
| A1 | -0.0322, -0.0287 | -0.0323, -0.0275 | 3.307 |
| B1 | +0.0494, +0.0457 | +0.0492, +0.0446 | 3.319 |
| A2 | -0.0336, -0.0315 | -0.0333, -0.0303 | 3.302 |
| B2 | -0.0533, -0.0499 | -0.0537, -0.0497 | 3.310 |
| A3 | +0.0232, +0.0213 | +0.0228, +0.0209 | 3.305 |
| B3 | +0.0171, +0.0155 | +0.0170, +0.0153 | 3.298 |

(rad.) B2 (-0.053) swerved 1.02 m off the lane's centre before x 360. The scores again do not
follow the error.

*What it does to the plan above.* The plan took a try to land within 0.01 rad about 40 % of the
time (two of the first five). Now: fixture_c6b 0 of 8 (A, B and these six: |error| 0.017 to
0.142); fixture_c170 2 of 3 (R2 -0.005, R3 +0.008). Pooled, 2 of 11, about 18 %: eight tries
all miss about 0.82^8 = 20 % of the time, and on fixture_c6b alone (no hit in 8) the rate could
be far worse. So on a featureless straight option 1 as planned may fail a reset often. Raised
with 133 before landing; the code (58da5a69) is not changed for it. The live starts (Isaac
fixture_c170 here, CARLA Town01 on 241's GPU1) are the next numbers.

## The live starts: design and predictions (243, 2026-11-27, before any run)

58da5a69 (not to be pushed whatever its gate, 133), built from a git bundle. Two agent settings,
each a YAML passed as the pilot's `agent_config` (merged over DEFAULTS):
- *draws:* `yaw_tolerance: 1.0e-6`: no align can be accepted, so each start logs eight tries'
  yaw error, position error and NVTL, then fails its reset by design (the suite's one retry on
  error gives a second eight). This is the per-try rate 133 asked for, not a guess.
- *live:* the defaults (0.01 rad, 8 tries): the change as it would land; the tries it takes.

Where: fixture_c6b (x 320, the 182 2c start; 118's GPU0) and fixture_c170 (R1's start, x 20;
118's GPU0 from the staged package), each with both settings; CARLA Town01 (241's GPU1, with the
defaults; a draws run too if 241 has the time).

*Predictions* (a try's |yaw error| within 0.01 rad, from the eleven starts so far):
- D1, fixture_c6b: under 15 % of tries (none of 8 starts so far); its live start fails after 8.
- D2, fixture_c170: 40 to 80 % of tries (2 of 3 starts); its live start lands within 3 tries.
- D3, CARLA Town01: over 80 % (a town's buildings and poles pin the yaw); its live start lands
  on the first or second try.
- D4: the tries are independent: no trend in |yaw error| from try 1 to 8, and NVTL does not
  order them (as the 2c scores did not).

## The live starts: results (118's runs, 2026-11-27; tables by 243)

118 ran the seven Isaac starts on GPU0 from the bundle (58da5a69), 10:07 to 10:31, each on a
fresh stack: draws x3 on fixture_c6b (runs D1 to D3), live on fixture_c6b (L1), draws x2 on
fixture_c170 (C1, C2), live on fixture_c170 (CL). Logs and 118's README: NAS `autoveh/logs/2026
SSv2 on CARLA/2026-11-27 issue 195 live starts (118)`; the scripts and outputs below: NAS
`home/2026-11-27 issue 195 live starts (243)/reading/` (`bias195.py`, `indep195.py`). CARLA
Town01 (241) has not run yet. Run labels D1 to D3 are 118's runs, not predictions D1 to D3.

Every try's signed yaw error (rad), in order; the live runs stop at the first within 0.01:

| run | map | tries | yaw error |
|---|---|---|---|
| D1 | c6b | 8 | +0.0798 +0.0472 +0.0808 +0.0674 +0.0388 +0.0485 +0.0507 +0.0450 |
| D2 | c6b | 8 | +0.0169 +0.0790 -0.0558 +0.0673 +0.0524 +0.0596 -0.0365 +0.0518 |
| D3 | c6b | 8 | -0.0343 +0.0337 +0.0631 -0.1178 +0.0520 -0.0403 +0.0224 -0.0198 |
| L1 | c6b | 6 | -0.0372 -0.0430 +0.0114 -0.0458 -0.0489 +0.0065 (accepted) |
| C1 | c170 | 8 | +0.0242 -0.0247 +0.0056 -0.0365 +0.0664 -0.0095 -0.0062 -0.0017 |
| C2 | c170 | 8 | +0.0477 -0.0100 -0.0492 -0.0364 -0.0145 +0.0029 -0.0573 -0.0474 |
| CL | c170 | 1 | -0.0069 (accepted) |

Position errors 0.01 to 0.14 m (c6b 0.07 to 0.09 m on average, c170 0.02 to 0.04 m).

*Rate* (|yaw error| within 0.01 rad; Wilson 95 % intervals):

| set | within | rate | 95 % interval |
|---|---|---|---|
| c6b draws (D1 to D3) | 0 of 24 | 0.000 | 0.000 to 0.138 |
| c6b, L1 included | 1 of 30 | 0.033 | 0.006 to 0.167 |
| c170 draws (C1, C2) | 6 of 16 | 0.375 | 0.185 to 0.614 |
| c170, CL included | 7 of 17 | 0.412 | 0.216 to 0.640 |
| both maps | 8 of 47 | 0.170 | 0.089 to 0.301 |

*Bias* (signed mean, its 95 % t interval, two-sided p against 0; positive tries of all):

| set | n | mean | sd | 95 % interval | p | positive |
|---|---|---|---|---|---|---|
| D1 | 8 | +0.0573 | 0.0164 | +0.0436 to +0.0710 | < 0.0001 | 8 of 8 |
| D2 | 8 | +0.0293 | 0.0501 | -0.0126 to +0.0713 | 0.14 | 6 of 8 |
| D3 | 8 | -0.0051 | 0.0600 | -0.0553 to +0.0450 | 0.82 | 4 of 8 |
| L1 | 6 | -0.0262 | 0.0275 | -0.0550 to +0.0027 | 0.067 | 2 of 6 |
| C1 | 8 | +0.0022 | 0.0318 | -0.0244 to +0.0288 | 0.85 | 3 of 8 |
| C2 | 8 | -0.0205 | 0.0348 | -0.0497 to +0.0086 | 0.14 | 2 of 8 |
| c6b (D1 to L1) | 30 | +0.0165 | 0.0518 | -0.0028 to +0.0358 | 0.092 | 20 of 30 |
| c6b without D1 | 22 | +0.0017 | 0.0524 | -0.0216 to +0.0249 | 0.88 | 12 of 22 |
| c170 (C1, C2, CL) | 17 | -0.0090 | 0.0332 | -0.0261 to +0.0080 | 0.28 | 5 of 17 |
| both maps | 47 | +0.0073 | 0.0472 | -0.0066 to +0.0211 | 0.30 | 25 of 47 |

*Independence* (permutation tests, 20000 shuffles):
- run effect (one-way F of the signed error across one map's starts): c6b (D1, D2, D3, L1)
  F 5.24, p 0.0065; c170 (C1, C2) F 1.86, p 0.19.
- trend of |yaw error| with the try index (draw runs, index shuffled within a run): c6b
  rho -0.25, p 0.26; c170 rho -0.19, p 0.48.
- NVTL (the agent's line carries the score as it read it; the first try's is none): with the
  same line's NVTL, c6b rho +0.21, c170 rho -0.27; with the next line's, c6b rho -0.24, c170
  rho -0.67 (p 0.0099, n 14). NVTL ranges 3.279 to 3.311 on c6b, 3.344 to 3.373 on c170.

*Truth.* The ego trace (`attachments/ego_trace/ego.csv`) holds the car's yaw while it stands at
the start, through every try: within 0.0006 rad of 0 in D1, D2, D3 and L1 alike (D1 -0.00054 to
-0.00002 rad). The scenario's pose is the car's, so the yaw errors above are NDT's.
