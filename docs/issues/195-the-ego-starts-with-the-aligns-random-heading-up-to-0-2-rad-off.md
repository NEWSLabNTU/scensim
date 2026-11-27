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

## The live starts: the reading (243, 2026-11-27)

*Against the predictions.*
- Prediction D1 (fixture_c6b under 15 %; its live start fails after 8): the rate holds, 0 of 24
  draws (interval to 13.8 %), 1 of 30 with L1. The live part does not: L1 landed on its sixth
  try. One start; at 3.3 % a try, a start reaches a hit within eight about 24 % of the time.
- Prediction D2 (fixture_c170 40 to 80 %; its live start within 3 tries): 6 of 16 draws, 37.5 %
  (18.5 to 61.4 %), just below the band with the interval across it: not decided. CL landed on
  its first try: holds.
- Prediction D3 (CARLA Town01): no runs yet.
- Prediction D4 (independent tries): partly fails. No trend with the try index on either map,
  and NVTL does not order c6b's tries, as predicted. But c6b's starts differ: the run effect is
  p 0.0065, so tries within one start are not independent draws. On c170 the next line's NVTL
  ordered the errors (rho -0.67, p 0.01, n 14), against the prediction; one map, fourteen pairs.

*The bias 133 asked about.* There is no bias common to the map or the method: pooled over 47
tries the mean is +0.007 rad (interval -0.007 to +0.021), c6b's +0.017 (-0.003 to +0.036) and
c6b without D1 +0.002. There is a bias per start: D1's eight tries sit at +0.057 rad (interval
+0.044 to +0.071, all eight positive, sd 0.016 against 0.05 to 0.06 in D2 and D3), and L1's lean
the other way (-0.026, p 0.067). The car stood at 0 in every run (truth within 0.0006 rad), so
the offset is the align's, and it is the start, not the map, that picks it: the same pose on
fresh stacks gave D1 a basin near +0.05, D2 mostly +0.05 to +0.08 with two near -0.05, L1 mostly
-0.04. c6b's straight lets NDT settle at several headings a few hundredths off, and 0 is not
the one it favours. That is the biased optimum 133 read in D1, and it belongs to the start.

*What it implies for the options.*
- Option 1 as coded (8 tries within 0.01 rad): on fixture_c6b it fails a reset about 3 times in
  4 at the measured rate (0.967^8 = 0.76; 0.30 even at the interval's top), and a start that
  draws D1's basin does not escape it. Not good enough to land for straights.
- (a) A higher cap: buys little. It assumes independent tries, which c6b's run effect denies;
  at 3.3 % a try even 30 independent tries fail one start in three.
- (b) A looser tolerance: to pass most c6b tries it has to reach 0.05 to 0.08 rad, and the
  earlier runs showed NDT keeps the align's heading for the whole run (EKF first to last within
  0.004 rad); B2 at -0.053 swerved 1.02 m. It would hide the error, not remove it.
- (c) DIRECT: the simulator knows the start pose exactly (here the scenario's pose is the car's
  to 0.0006 rad). Setting the EKF there skips the yaw search that produces these errors. The
  same flatness that lets the align land anywhere near 0 suggests NDT then holds the heading it
  is given, so a DIRECT start should hold near 0. Untested: it needs a start on fixture_c6b with
  a prediction (NDT's yaw within 0.01 rad of truth over the standing window and the first
  100 m), and it gives up the align's check that the scan fits the map, which the verify stage
  (NVTL over its window) would have to carry alone.

So (c), measured first on fixture_c6b; option 1 and (a) do not fix c6b, and (b) moves the error
into the run. CARLA Town01 (241) would say whether a featured map needs anything at all.

## The user's decision, and the replan (243, 2026-11-27; a plan, no code)

The user, through 133: "I prefer to let Autoware run as though it's a real car. We don't pass
ground truth position to it. The autopilot should always rely on sensor or v2x to get the
pose." So DIRECT is out, and so is today's path (the agent initializes at the scenario's pose).
Comparing Autoware's estimate with the truth as a judge stays allowed. 58da5a69 and f26af7da are
not landed; the branch (i195) is kept.

### (1) The audit: where the truth or the scenario's pose reaches Autoware's localization

Read at main 37402fd2 and its pins; Autoware 1.5.0 from autoware_core's source at tag 1.5.0.

| # | where | what reaches Autoware | when |
|---|---|---|---|
| A1 | scensim_agent `adapters/autoware_ros.py` `initialize` | the scenario's pose as `/api/localization/initialize`'s `pose` (AUTO method), zero covariance | every reset of a relay ego |
| A2 | scensim_agent `adapters/autoware.py`, the converge stage | not an input, but a choice: an align is accepted or re-run by comparing the estimate with the scenario's pose (`consistent`, 1.0 m and `yaw_tolerance`); 58da5a69 makes it re-run until the heading matches | every reset |
| A3 | scensim_launch `pilots/autoware.launch.xml` | `gnss_enabled` false for relay egos, so Autoware has no GNSS initialization and only A1 can initialize it | every relay ego |
| A4 | the relay (`relay_node.py`, `episodes.py`) | carries SSv2's `/api/localization/initialize` pose (the scenario's) to the agent's reset | every scenario start |
| A5 | SSv2's concealer (`field_operator_application.cpp`) | `requestInitialPose` sends the scenario's pose to `/api/localization/initialize`, retried 30 x 10 s while `waitForLocalizationToReach` (1 m, 0.2 rad against the scenario's pose) fails | every scenario start; with the relay, through A4 |
| A6 | acb_bridge `seed_localization_on_attach` (`autoware.rs`, `service_localization_seed`) | CARLA's true pose as `/initialpose` (RViz's 2D Pose Estimate entry point) until the estimate is within its tolerance | default true when `relay:=none` (stand-alone and `just ego-av` without an agent), false with the relay |
| A7 | acb_bridge `publish_direct_localization` | the true pose as `/localization/kinematic_state` and `/tf`, replacing Autoware's localization | default false; opt-in |
| A8 | aib `ground_truth.pose_estimate` (rig, `ros.py`) | the true pose on NDT's output topic | default false; opt-in |
| A9 | aib `gnss_reading` and CARLA's `sensor.other.gnss` (spec `carla_sensors.yaml`, no noise parameters) | the antenna's true position, no noise: a sensor, but a perfect one (an RTK fix without its 1 to 2 cm) | whenever GNSS is on |

Not localization, but the same question: acb's `ground_truth_objects` publishes perception's
objects from the simulator's truth; a separate item for the user.

Allowed and kept: the judges (`pose_error`, `nvtl`, the gap trace), the ego trace, 170 and 196's
analyses, and the concealer's `waitForLocalizationToReach` as a check (it does not feed
Autoware; with A5 removed it only decides whether the scenario starts).

One fact changes the picture. Autoware 1.5.0's align (`NDTScanMatcher::align_pose`) samples yaw
uniformly over the full circle and takes only the position (and its covariance) from the guess;
the guess's heading is not used. So today the scenario's heading never reached the align: what
A1 gave it was the position, with zero spread. The yaw errors measured above are already the
align's own, and a real car's start would show the same on the same map.

### (2) The real-car path

How a real Autoware car starts: `automatic_pose_initializer` calls the initializer once at
start with no pose (AUTO); `pose_initializer` takes the GNSS pose (`gnss_module`: the latest
`/sensing/gnss/pose_with_covariance` within `gnss_pose_timeout`, 3 s) with
`gnss_particle_covariance` (1 m in x and y, yaw 10 rad^2), checks the car has been stopped
`stop_check_duration` (3 s), and hands it to NDT's align, which searches position around it
(TPE, 200 particles) and yaw over the full circle. Without `gnss_enabled` an initialize with no
pose is refused ("GNSS is not supported"). An operator's 2D pose estimate is the other stock
way; in simulation it would be the truth, so it is out.

The heading: at standstill `gnss_poser` has no motion to derive a heading from, and with
`use_gnss_ins_orientation` false (the sensor kits) it has no other. That does not matter to the
stock align, which ignores the guess's heading; it would matter to a heading-aware align (below).
170's 2.085 deg (gnss_poser's motion-derived yaw through the kit-rotated gnss_link) likewise
touches only the GNSS pose's orientation, which neither the align nor the initializer's
pose-error check (2D position) reads. Real cars that do not rely on the yaw search carry a
dual-antenna GNSS or an INS (`GnssInsOrientationStamped`, `use_gnss_ins_orientation` true).

The change, per path:
- Relay egos: `gnss_enabled` true (A3); the agent's reset calls `/api/localization/initialize`
  with no pose (A1); the relay stops passing SSv2's pose to the agent (A4); the agent accepts an
  align on Autoware's own evidence (INITIALIZED, the initializer's reliability flag, NVTL over
  the verify window), never on the scenario's pose (A2); it may log the error against the
  scenario's pose for the record, as a judge does, without acting on it. 58da5a69's retries go.
- Stand-alone acb: `seed_localization_on_attach` (A6) retired; the automatic initializer does it.
- A7 and A8: refused with an Autoware pilot (they are for pilots that are not an autopilot), or
  retired; the user's call.
- A9: a GNSS noise model in aib and acb (position noise and bias, a fix type), defaulting to an
  RTK-like 2 cm, so the GNSS is a believable sensor rather than the truth; the user's call on
  the default.
- Order at start: with `gnss_enabled` true the automatic initializer runs once at stack start,
  before SSv2 places the car (issue 046's reason for turning it off: it competes with the
  scenario's initialize). The agent's reset after the teleport initializes again; the plan has
  to let the two not collide (the reset waits out an initialization in progress, or joins it).

Options inside the rule for later, if the measured cost is too high: (i) the align's own
parameters (more particles, the startup trials), sensor only; (ii) a heading sensor (a
dual-antenna GNSS/INS model in aib and acb, with noise) plus an Autoware overlay fix that samples
yaw around the INS heading when its covariance says it is known; what real cars with an INS do.

### (3) What it does to 197 and to scenario resets

- A scenario start or reset stays an SSv2 teleport of the car followed by a localization the
  car does itself: the agent's reset becomes a pose-free initialize. It can still fail (no GNSS
  within 3 s, the align unreliable, the initializer refusing a moving car), so 197 is needed as
  it is: the agent refuses a goal after a failed reset (f7de9207), and the run ends as an error
  when this run's reset fails (660c81eb). Only the failure texts change; 58da5a69's "landed off
  the scenario's heading N times" disappears with A2.
- The concealer still waits for the estimate to reach the scenario's pose (1 m, 0.2 rad); an
  align that lands further off is a start that does not happen, an honest failure of the
  autopilot, reported by SSv2's timeout. Its retries come through the relay as repeated
  initializes, which join the running reset or start a pose-free one.
- An align within 0.2 rad but off is no longer corrected: the ego drives with it. That is the
  cost (4) measures, and the judges see it.

### (4) The cost, and the measurement

What changes for Autoware is the position guess (GNSS with 1 m particle spread instead of the
scenario's position with none) and the timing (GNSS timeout, stop check); the yaw search is the
same. So the yaw error should look like the draws above: fixture_c6b about 3 % within 0.01 rad,
|error| typically 0.02 to 0.08; fixture_c170 about 40 %.

Measurement, after the change is coded and gated, on fixture_c6b and fixture_c170 (Isaac) and
CARLA Town01 (241): eight fresh-stack starts per map (starts, not tries: the run effect says one
start's tries are not independent), each with:
- the yaw and position error of the first INITIALIZED estimate against the truth (the judge's
  comparison), and the same 5 s later standing and over the first 100 m (does driving correct
  it; the 2c runs said no);
- the start time: stack ready to INITIALIZED, and the reset's own seconds (the relay's record);
- NVTL and the initializer's reliability flag, to see whether Autoware can tell a bad start;
- the runs' outcomes (contacts, lane departure on c6b at B2's place).
Predictions go in this issue before the runs, as above.

## The user's answers, and the code plan (243, 2026-11-27, before any code)

The user's answers, through 133:
1. A7 and A8 become one opt-in *direct localization* that passes the truth pose to any autopilot
   (not only Autoware), for debugging, not for evaluation, off by default; a run that uses it is
   marked a debug run in its result so it cannot pass as an evaluation. A6 is retired (or folded
   into that option).
2. A9: GNSS noise, RTK-like, 2 cm by default, configurable per project.
3. acb's `ground_truth_objects` stays an opt-in tool; the rule covers the pose only.

The work is split: 118 takes A9 in sim_vehicle_spec, aib and acb (its own section below, with
its predictions); 243 takes the agent, the relay, the launches, the direct-localization option
and 197.

### Decisions

*Direct localization, one meaning in both simulators.* The vehicle side publishes the truth's
base_link pose as `PoseWithCovarianceStamped` on the pose estimator's output topic
(`/localization/pose_estimator/pose_with_covariance`), as aib's `ground_truth.pose_estimate`
already does, and the autopilot's own estimator is not started. For Autoware (the scensim
profile): `ndt:=none`, so tier4_localization starts no pose estimator, the pose initializer runs
with `ndt_enabled` false (a pose-free initialize puts the EKF at the GNSS pose), and the EKF
fuses the truth from then on. Every other part of the stack runs as in an evaluation. Any other
autopilot reads the same topic. acb's `publish_direct_localization` (the truth straight to
`/localization/kinematic_state` and `/tf`, the EKF bypassed) is the other meaning; it is
replaced by acb's `truth_pose_estimate` (the aib behaviour), and the old parameter is refused by
name. A6 (`seed_localization_on_attach`) is retired, not folded: with the estimator off there is
nothing for it to seed.

*The option.* A pilot key, `direct_localization: true` (default false), on the pilot that has
the vehicle side. scensim turns it into aib's `ground_truth: {pose_estimate: true}` in the Isaac
ego config, or acb's `truth_pose_estimate:=true`, and for an `autoware` pilot into
`ndt:=none`. An `autoware` pilot on the stock profile is refused with it (no `ndt` argument
there).

*The debug mark.* A run of a stack with any debug option carries `"debug":
["direct_localization"]` in `result.json` (`swb.result/1`, an optional list, validated). Its
verdict is judged as any run's, but it never counts as an evaluation: the run's line reads
`passed [debug: direct_localization]`, and its exit code is 4 (`EXIT_DEBUG`, new, above
refused) whatever the verdict, so a suite, a gate or a script that takes exit 0 as a pass
cannot take a debug run as one; `scensim runs` shows the mark. The bridges also log a WARN at
start while it is on.

*A pose-free reset (the agent).* `/api/localization/initialize` without a pose (AUTO): the
pose initializer takes the GNSS pose. The reset's pose stays in the agent protocol (other
agents, a simple pilot, may use it), so the relay does not change; the Autoware adapter stops
forwarding it. The adapter accepts an initialization on Autoware's evidence alone: the state
INITIALIZED, an estimate newer than the call, then the existing verify window on NVTL. It never
compares the estimate with the reset pose to decide; it logs that comparison once per reset, as
a judge would. The retry on a refused call (the car not yet stopped 3 s, no GNSS within 3 s)
stays (`initialize_retry`, `initialize_attempts`).

*Issue 046's collision.* With `gnss_enabled` true the automatic initializer runs once at stack
start. A reset that finds the localization state INITIALIZING waits for it to leave that state
(bounded by `align_wait`) before calling, so its call is the last one and comes after SSv2 has
placed the car; a concealer retry while the reset runs joins it, as today.

*GNSS for relay egos.* `pilots/autoware.launch.xml` stops setting `gnss_enabled` false for
relay egos (the argument stays, default true).

*118's GNSS keys, per project.* The pilot's `args` carry `gnss_noise_*` (118's names); scensim
routes them to acb's parameters on CARLA (`pilots/vehicle_side_carla.launch.xml`) and to the
Isaac ego config's GNSS block on Isaac, and passes the stack's seed when none is given, so a
scensim run reproduces.

### Order (test-first; each landing gated, 133 asked before each push)

1. 118: sim_vehicle_spec's GNSS noise field; aib's and acb's noise; acb's A6 retirement. Each
   on its own main.
2. 243, acb (on 118's acb): `truth_pose_estimate` replaces `publish_direct_localization`,
   refused by name; tests first (the pose message, the frame, the WARN, the refusal).
3. 243, scensim, one landing:
   - the agent's pose-free reset, its acceptance on Autoware's evidence, the wait for an
     initialization in progress (fake_autoware tests first: no pose in the request; an estimate
     far from the reset pose accepted; an INITIALIZING state waited out; a refused call
     retried);
   - 197's two commits (f7de9207, 660c81eb), rebased;
   - the launches: `gnss_enabled` for relay egos; `vehicle_side_carla`'s seed argument dropped
     and refused by name; the `gnss_noise_*` and `truth_pose_estimate` pass-through;
   - scensim: `direct_localization` (config validation, the stack's mapping per simulator,
     the stock-profile refusal), the debug mark (result field, line, exit 4, `runs`), the GNSS
     keys' routing and seed; tests first for each;
   - docs: projects-and-pilots (the option, the mark, the GNSS keys), vehicle-side;
   - pins: sim_vehicle_spec, aib, acb by `land_pin`, with the components' deps.
4. The measurement: eight fresh-stack starts per map (fixture_c6b, fixture_c170 on Isaac;
   Town01 on CARLA), predictions committed here first, as (4) above.

*Two notes on the plan (133's, 2026-11-27).*

- *The stock profile.* "Any autopilot" holds on the topic side: every vehicle side publishes
  the truth on the pose estimator's output topic, for any pilot kind. Only the switch that
  turns Autoware's own estimator off needs the scensim profile (`ndt:=none`); an `autoware`
  pilot on the stock profile with `direct_localization` is refused with a message that names
  it: "direct_localization turns Autoware's NDT off through autoware_sim_profile's `ndt:=none`;
  set `autoware_profile: scensim`, or start your autoware_launch without a pose estimator
  yourself and set `direct_localization` on a `launch` pilot".
- *Exit code 4.* Read at main 574f9cc4, the consumers of `scensim run`'s exit and its line:
  - `scripts/t3.py`: takes the worst exit of its steps (`max`), so a debug run makes t3 exit 4,
    not 0;
  - `scensim/dispatch.py`: the same `max` over its runs;
  - `scripts/gap_live.py`: logs the exit, and takes the verdict from the line's first three
    fields (`^(passed|failed|error|refused)\s+(\S+)\s+(\S+)`); the debug mark therefore goes at
    the end of the line, after the run directory, never in the verdict field;
  - the justfile recipes (`scenario`, `two-av`, `demo-tour`, `e2e`) `exec` the run and pass its
    exit through;
  - `run_suite`, `gap_oracle`, `physical_verdict`, `scripts/gate.sh` and `.github/workflows`
    (release only) do not read it.
  None gives 4 a meaning today. (acb_bridge's own exit 4, physics drift, is a different
  process's and never `scensim run`'s.) So the line is `passed  <run id>  <run dir>  [debug:
  direct_localization; not an evaluation]`, and the plan's "reads `passed [debug: ...]`" is
  corrected to that.

## A9: the GNSS noise model (118, 2026-11-27)

The user's answer 2: GNSS noise, RTK-like, 2 cm by default, configurable per project. Agreed
with 243 before any code; with it, A6 (133 assigned it to 118 in the same acb gate).

### The model, one in both bridges

The antenna's true position is moved east, north and up in the map before it is projected to
latitude and longitude:
- a bias drawn once per receiver from N(0, `bias_stddev_m`) on each axis;
- plus white noise per fix, from N(0, `horizontal_stddev_m`) east and north and
  N(0, `vertical_stddev_m`) up.

The defaults are an RTK fix's: 0.02, 0.04 and 0 m. NavSatFix carries the diagonal of those
variances (the bias's added), with `COVARIANCE_TYPE_DIAGONAL_KNOWN`; the status stays GBAS_FIX.
`enabled: false` publishes the true position with no covariance, as before. A seed makes the
fixes reproducible; without one the bridge draws a seed and logs it, and that seed replays the
run. On CARLA the noise is added by acb, not by `sensor.other.gnss`'s `noise_*` attributes:
those are in degrees and draw from CARLA's own generator, so they would neither match aib nor
replay from our seed.

| | aib (Isaac): the ego config | acb (CARLA): acb_bridge parameters |
|---|---|---|
| on or off | `gnss.enabled` (true) | `gnss_noise_enabled` (true) |
| white noise, east and north | `gnss.horizontal_stddev_m` (0.02) | `gnss_noise_horizontal_stddev_m` (0.02) |
| white noise, up | `gnss.vertical_stddev_m` (0.04) | `gnss_noise_vertical_stddev_m` (0.04) |
| the per-run bias's spread | `gnss.bias_stddev_m` (0.0) | `gnss_noise_bias_stddev_m` (0.0) |
| seed | `gnss.seed` (null: fresh, logged) | `gnss_noise_seed` (-1: fresh, logged) |

scensim routes the pilot's `gnss_noise_*` args to these (243's landing). acb's launches
(`acb_bridge.launch.xml`, `carla_simulator.launch.xml`) take the same names as arguments.

*Not in the vehicle spec.* The plan put the default in sim_vehicle_spec's gnss entry. That
changes the Model 3's spec_hash, which 11 autoware_sim_vehicle files, 7 spec outputs and aib's
rig carry, so a receiver default would have cost a regeneration and two more landings. Agreed
with 243: the defaults live in the bridges, under the same names. "One car, one source" readers
should look for the GNSS model in aib (`aib.sensing.GnssNoise`) and acb (`gnss_noise.rs`), not
in the spec. If a car ever needs its own receiver, the block can move into the spec then.

### A6: `seed_localization_on_attach` retired

acb no longer publishes the true pose on `/initialpose` when it attaches. The `/initialpose`
publisher, `request_localization_seed` and `service_localization_seed` are gone. What stays is
the seating watch (the `seated` frame the scenario runner waits on), now `watch_seating`, reset
at every attach. Passing `seed_localization_on_attach` (any value) stops acb_bridge at start,
naming it and the reason. acb's launches no longer declare the argument; scensim's
`vehicle_side_carla.launch.xml` drops it in 243's landing.

133's condition: acb's stand-alone bring-up (no relay, `just sim`) used to get the seed, so show
that it still localizes through Autoware's automatic GNSS initializer (`gnss_enabled` true in
the profile), with one live stand-alone start.

### Predictions for the stand-alone start (written before the run)

The run: 118's own CARLA on 2010 (GPU0, Epic, Town01), acb's demo (`acb_demo_launch
single_vehicle_autoware.launch.xml`, as `just sim` starts it, without the web UI) from the A9
acb worktree, built from a clean env; ROS domain 11. Nothing else changes.
- S1: acb logs `GNSS gnss_link: error east/north 0.02 m, up 0.04 m, bias 0 m (...), seed N`.
- S2: no `/initialpose` comes from acb (it has no such publisher now); acb logs no seed lines.
- S3: Autoware's automatic initializer takes the GNSS pose: the localization initialization
  state reaches INITIALIZED, and acb logs `Localization is on the vehicle: the estimate is X m
  from it` with X below 0.5 m, within 180 s of acb attaching.
- S4: `/sensing/gnss/gnss_link/nav_sat_fix` has `position_covariance_type` 2 and the diagonal
  (0.0004, 0.0004, 0.0016).
- S5: `acb_bridge` run with `-p seed_localization_on_attach:=true` exits non-zero at start,
  naming the parameter as retired.

If S3 fails, A6 does not land until 133 decides.

### The stand-alone start: results (118, 2026-11-27, after the run)

One start, 11:09 to 11:24 on GPU0 (codec told). The A9 acb worktree (main e85424d plus the
A9/A6 diff), built from a clean env, with `just check` and `just test` passing (268 tests).
CARLA ran on 2010 with Town01. Two departures from the plan, neither touching what was
measured:
- play_launch is no longer installed on 118 (scensim's own runs fell back to `ros2 launch`
  too), so the demo ran under `ros2 launch`.
- rviz2 crash-looped for want of a display.

| | prediction | result |
|---|---|---|
| S1 | the GNSS log line with a seed | held: `GNSS gnss_link: error east/north 0.02 m, up 0.04 m, bias 0 m (this run's: -0.0000, 0.0000, -0.0000), seed 7416089968757948162` |
| S2 | no `/initialpose` from acb | held: no seed lines in acb's log, and `/initialpose` did not exist on the graph (`ros2 topic info`: unknown topic) |
| S3 | INITIALIZED, seated below 0.5 m within 180 s | held: the automatic initializer's first align failed (`align server failed`, 5 s after acb attached); its retry 12 s later succeeded; acb logged `Localization is on the vehicle: the estimate is 0.01 m from it` 23 s after attaching |
| S4 | covariance type 2, diagonal (0.0004, 0.0004, 0.0016) | held, exactly. 110 fixes at standstill over 11 s spread 0.0175 m east, 0.0201 m north, 0.0387 m up |
| S5 | `seed_localization_on_attach` stops acb_bridge, named | held for `true` and for `false`: exit 1, `seed_localization_on_attach is retired (scensim issue 195 A6) ...` |

So acb's stand-alone bring-up localizes without the seed, through Autoware's GNSS initializer
(133's condition). The logs are on the NAS (`2026-11-27 issue 195 A9 stand-alone start (118)`).

## Batch L: localization and Isaac sensing (133, 2026-11-27)

The user asked for related issues to be resolved in batches. Batch L, led by 243 with 118:
195 (the start's heading; now no truth to Autoware), 197 (a failed reset that does not end
the run), 196 (the lidar scan stamped (n - 1) substeps after its render pose), 170 (Isaac's
localization off the truth: across +0.19 m, along the stamp lag), 182's standstill drift, and
172 (Haruna's bimodal localization, whose "~24 ms time offset latched early" looks like 196's
lag). The order: **L1**, one landing of 195 (the pose-free initialization, the
direct-localization option and its debug mark, GNSS on, 118's GNSS noise and acb's retired
seed) with 197; **L2**, the 196 fix in aib (test-first), then a pin landing; **L3**, one
measurement campaign on L1 and L2, predictions first: eight pose-free starts per map
(fixture_c6b, fixture_c170, CARLA Town01), along and across against speed (the 34 ms lag
expected gone), 170's car-fixed across offset, 182's standstill drift and a Haruna rerun set
for 172. The NDT trace below runs as a baseline now and again in L3.

*Data for the record.*
- CARLA Town01 (241, GPU1, the 58da5a69 build with the overlay; run
  `2026-11-27T11-10-35_town01_ego_drive_r0`, project i195_draws): eight draws at +0.0009,
  +0.0008, +0.0006, +0.0008, +0.0012, +0.0014, +0.0011, +0.0012 rad, and +0.0011 in a defaults
  run; the truth's yaw is the reset's to 1e-6 rad. Every try within 0.01 rad, all positive:
  Town01's structure pins the yaw, where fixture_c6b's straight spread it 0.02 to 0.14 rad.
- That run's reset failed by design (the draws' tolerance), the agent took the goal, and the
  run PASSED in 132 s: 197's case on CARLA, where nothing in the run notices (recorded in 197).
- The Autoware overlay is needed wherever a reset initializes more than once: without it the
  second initialize can kill `pose_instability_detector` (docs/issues/027's negative time;
  241's first attempt, `2026-11-27T10-21-12`). L1's precheck warns by name when an agent's
  stack runs without the overlay.

## The NDT trace: is the drift inherited from the initialization? (243, plan and predictions, before any run)

The user's question, through 133: is the localization error inherited from NDT's pose
initialization (an offset NDT never corrects) or made later by its per-scan tracking? A trace
of both, against the truth, now on current main (the baseline) and again in L3.

*What is recorded* (Autoware 1.5.0's own outputs, read from autoware_core 1.5.0's source):
- the align: `/localization/pose_estimator/monte_carlo_initial_pose_marker` (a MarkerArray
  per particle: its initial and result pose; its score and iteration count as the markers'
  colours, `exchange_color_crc(score / 4.5)` and `(iteration / 30)`, read back by inverting
  that map); the pose initializer's output `/initialpose3d`; `/diagnostics`
  (`ndt_align_service` `best_particle_score`). The winning particle is the one whose result
  pose is the initializer's output.
- per scan: `/localization/pose_estimator/initial_pose_with_covariance` (the EKF's pose
  interpolated to the scan, NDT's guess), `.../pose_with_covariance` (its result),
  `.../initial_to_result_relative_pose` and `.../initial_to_result_distance` (the pull),
  `.../iteration_num`, `.../transform_probability`,
  `.../nearest_voxel_transformation_likelihood`, `.../exe_time_ms`;
- the EKF: `/localization/kinematic_state`, `/localization/pose_twist_fusion_filter/
  biased_pose_with_covariance`, `.../estimated_yaw_bias`, and `/diagnostics`'
  `pose_mahalanobis_distance`, `pose_is_passed_mahalanobis_gate` and `pose_is_passed_delay_gate`;
  the innovation is NDT's result against the EKF's pose at the scan's stamp (the EKF publishes
  no innovation of its own);
- `/localization/initialization_state`, `/sensing/gnss/pose_with_covariance`,
  `/vehicle/status/velocity_status`, `/tf_static`; the truth from the gap trace's `sim_pose`
  with its origin offset taken off (`scensim.truth`). No point clouds.

*The runs.* 118's GPU0, current main's code (53b76a47; later commits are docs), a fresh stack
each, `ros2 launch` (play_launch is not on 118; recorded): fixture_c6b_r181 twice (the start
at x 320, the drive, the stop before the boulder and the stand there, 182's standstill) and
fixture_c170_down_hold twice (the drive at 11.11 m/s and 45 s held at the goal). On main the
agent still initializes at the scenario's position (zero spread); L3 repeats the trace
pose-free.

*The attribution.* At the initialization: the winning particle's yaw, along and across
offsets against the truth. Then, per scan: the error of NDT's guess and of its result against
the truth, the pull (result less guess) and the EKF's innovation, each in yaw, along and
across, against time and speed. Inherited means the error at the first scan equals the
winning particle's, and later pulls average to zero; made means it grows through pulls of
one sign.

*Predictions.*
- N1, the init: the winning particle's yaw error is the start's (fixture_c6b 0.02 to 0.08
  rad, fixture_c170 under 0.03 rad); its position error under 0.1 m; on fixture_c6b the
  particles' scores do not order their yaw errors (the scores within 0.05 of each other).
- N2, yaw inherited: from the first scan on, NDT's yaw error stays within 0.005 rad of the
  winning particle's, standing and driving, on both maps; the per-scan yaw pull is under 0.001
  rad (median of its absolute value) and averages to zero.
- N3, across inherited: the car-fixed across offset (170's +0.19 m) is already the winning
  particle's to within 0.05 m, and stays.
- N4, along made while driving: the along error follows the speed (196's 34 ms, about 0.37 m at
  11.11 m/s) and is absent standing; the pulls do not carry it (it is in the scan's stamp, not
  in the match).
- N5, the standstill drift made by tracking: standing, the along error moves at 0.05 to 0.3
  m/min (182's range) through small pulls of one sign (median under 1 mm a scan), every one
  passing the EKF's Mahalanobis gate; the truth stays within 1 mm.
- If N2 or N3 fails (the error is not the init's), the drift is tracking's; if N5 fails
  (no one-signed pull), the standstill drift is the EKF's, not NDT's.

The topic list is staged for 118 as a testbench `logging.topics` block on the NAS
(`home/2026-11-27 issue 195 NDT trace (243)`); the runs wait for 133's go.

## The NDT trace, baseline: results (118's runs, 2026-11-27; tables by 243)

**main's agent: the scenario's position seeded (pre-L1, kept only as the measured baseline).**
118's GPU0, scensim main's code 53b76a47, every submodule at its pin, the Autoware overlay's
ndt_scan_matcher (each run's `/proc` maps), `ros2 launch`; maps as fetched (fixture_c6b pcd
32bab6cc, fixture_c170 pcd 9cc1a29f: course.maps builds, suspect under issue 198). Runs:
N1 `2026-11-27T11-34-27_fixture_c6b_r181_r0`, N2 `2026-11-27T11-38-20_fixture_c170_down_hold_r0`,
N3 `2026-11-27T11-41-30_fixture_c6b_r181_r0`, N4 `2026-11-27T11-45-15_fixture_c170_down_hold_r0`
(the c6b runs end at the scenario's 150 s timeout, as before; their judges passed). Logs: NAS
`autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 195 NDT trace baseline (118)`; the reader
`ndt195.py`, its JSON and tables: NAS `home/2026-11-27 issue 195 NDT trace (243)/reading/`.
Errors are NDT's (or the EKF's) less the truth (base_link) at the message's stamp, in the
truth's heading frame. Segments: `stand0` before the car first moves, `drive`, `stand1` after.

*The score read from the markers' colours* matches `/diagnostics`' best_particle_score for the
winner in every run, to 1e-5 or better (5.6e-7, 9.1e-6, 2.9e-7, 1.3e-7): the decoding holds.

*The align* (200 particles; the winner is always the top score):

| run | winner dyaw (rad) | along (m) | across (m) | dz (m) | score | yaw-nearest particle: rank (its dyaw) | particles within 0.01 rad | second best | rho(score, abs dyaw), particles within 2 m and 0.3 rad |
|---|---|---|---|---|---|---|---|---|---|
| N1 c6b | +0.0391 | -0.018 | +0.093 | -0.024 | 3.3148 | 3 (-0.0107) | 0 | 3.2981, dyaw -3.106, across -1.43 | -0.59 (14) |
| N2 c170 | -0.0003 | -0.006 | +0.003 | -0.013 | 3.3736 | 1 | 9 | 3.3732, dyaw +0.006 | -0.88 (79) |
| N3 c6b | +0.0407 | -0.003 | +0.087 | -0.023 | 3.3111 | 3 (-0.0023) | 1 | 3.3053, dyaw +0.016 | -0.76 (16) |
| N4 c170 | +0.0160 | +0.004 | +0.010 | -0.012 | 3.3568 | 23 (+0.0005) | 11 | 3.3568, dyaw +0.012 | -0.86 (107) |

*Per scan*, NDT's result less the truth, median [p5, p95] (first scan, last scan):

| run | segment | scans | dyaw | across | along | dz |
|---|---|---|---|---|---|---|
| N1 | stand0 | 57 | +0.0371 [+0.0350, +0.0386] | +0.082 | -0.056 | -0.024 |
| N1 | drive | 403 | +0.0145 [+0.0085, +0.0362] (+0.036 to +0.009) | +0.139 [-0.144, +0.372] | -0.157 | -0.024 |
| N1 | stand1 | 2585 | +0.0067 | -0.218 | -0.051 | -0.024 |
| N2 | stand0 | 60 | +0.0001 | +0.085 | -0.025 | -0.012 |
| N2 | drive | 1215 | -0.0048 | +0.219 [+0.087, +0.424] | -0.471 | -0.011 |
| N2 | stand1 | 845 | -0.0026 | +0.124 | -0.135 | -0.014 |
| N3 | stand0 | 50 | +0.0388 [+0.0356, +0.0403] | +0.094 | -0.002 | -0.024 |
| N3 | drive | 413 | +0.0141 [+0.0066, +0.0378] (+0.038 to +0.010) | +0.142 [-0.248, +0.393] | -0.129 | -0.024 |
| N3 | stand1 | 2561 | +0.0030 | -0.259 | +0.068 | -0.024 |
| N4 | stand0 | 55 | +0.0150 | +0.042 | -0.009 | -0.012 |
| N4 | drive | 1215 | +0.0032 (+0.014 to +0.002) | +0.147 [-0.045, +0.376] | -0.368 | -0.011 |
| N4 | stand1 | 846 | +0.0021 | +0.062 | -0.057 | -0.014 |

The pulls (result less guess) have medians within 0.0005 rad and 0.008 m of zero in every
segment. The EKF's pose follows NDT's within a few mm in position; its yaw does not after a
drive on fixture_c6b: `estimated_yaw_bias` is -0.0171 / -0.0181 rad (N1 drive / stand1) and
-0.0180 / -0.0182 (N3), against +0.005 and -0.003 on fixture_c170, so standing after the drive
the EKF's yaw error is -0.011 (N1) and -0.015 (N3) where NDT's is +0.007 and +0.003.

*The drive's along against speed* (median along; -along / v at the bin's middle, ms):
N1 -0.108, -0.153, -0.163 at 0-2, 2-4, 4-6 m/s (32.5 ms at 4-6); N3 -0.049, -0.106, -0.136
(27.1 ms); N4 -0.078 to -0.393 over 0-12 m/s, 32.7 to 35.9 ms from 4 m/s up; N2 -0.190 to
-0.520, 46.8 to 57.9 ms from 4 m/s up.

*Standing, from 10 s after the stop* (the truth moves 0 to 2.6 mm): NDT's along slope -0.0007
(N1), +0.219 (N2), +0.059 (N3), -0.478 (N4) m/min, the EKF's the same within 0.02; NDT's along
range -0.30 to +0.16 m (N1), -0.30 to +0.08 (N2), -0.22 to +0.57 (N3), -0.44 to +0.15 (N4);
the per-scan along pull p5 to p95 -0.031 to +0.031 (N1), -0.016 to +0.052 (N2), -0.039 to
+0.052 (N3), -0.103 to +0.066 m (N4), medians 0.0002 or less. The EKF's Mahalanobis gate
rejects 48 of 2533 (N1), 23 of 847 (N2), 99 of 2521 (N3) and 10 of 844 (N4) NDT poses after
the stop (none before the first motion); the distance's median 1.9, 0.9, 5.0 and 3.2.

## The NDT trace, baseline: the reading (243, 2026-11-27)

*The answer to the user's question: it depends on the axis.* Yaw and height are inherited from
the initialization; the across and along errors are made by the tracking, and so is the
standstill drift, which is a wander, not a creep.

- **Yaw: inherited, then corrected by driving.** The winning particle's yaw error is the start's
  (+0.039 and +0.041 rad on fixture_c6b, -0.0003 and +0.016 on fixture_c170), and it holds while
  the car stands (within 0.004 rad). Once the car moves, small pulls of one sign take it away:
  on fixture_c6b from +0.036 to +0.009 rad over the 20 s drive, and to +0.003 to +0.007 at the
  stop; on fixture_c170 from +0.014 to +0.002. A start's heading error therefore matters for
  the first tens of metres (B2's 1 m swerve, issue 182), not for the run.
- **Height: inherited and never corrected.** -0.024 m on fixture_c6b and -0.012 to -0.014 m on
  fixture_c170, the same at the winning particle and at every scan, pulls zero. A constant
  offset the matcher keeps is what a map whose ground is low would give: issue 198's terrain
  under the road (13 cm below it in 72 % of fixture_c6b's lane cells) is the candidate, to be
  checked on the rebuilt maps.
- **Across: made while driving.** On fixture_c170 the winner is 0.003 and 0.010 m across, yet the
  drive's median is +0.22 and +0.15 m (170's +0.19 m car-fixed offset) and falls back to +0.12 and
  +0.06 m standing. On fixture_c6b the drive runs +0.14 m and the stand after it -0.22 and -0.26
  m. The init does not carry it; the scans while moving do (the map's surface, issue 198, and
  the stamp, issue 196, are the two causes in reach).
- **Along: made, by the stamp while driving.** The drive's along error is -v tau with tau 33 to
  36 ms on N4 and 27 to 33 ms on fixture_c6b (196's two substeps), the estimate behind the
  truth; N2 reads 47 to 58 ms, an extra -0.1 m to explain. The pulls do not carry it: it is in
  the scan's stamp, as 196 found.
- **The standstill drift: made by tracking, a wander.** With the truth still (under 3 mm), NDT's
  along estimate wanders 0.4 to 0.8 m peak to peak in 30 to 120 s, at -0.48 to +0.22 m/min of
  either sign, through per-scan jumps of 3 to 10 cm (p5 to p95), and the EKF follows it. The
  matcher's along direction is barely constrained on a featureless straight, and a stationary
  car gives it no new geometry. The EKF's gate rejects 10 to 99 of those poses per stand,
  none before the first motion: its covariance has shrunk at a standstill, so the jumps look
  large to it.
- **The EKF learns a yaw bias on fixture_c6b**: -0.018 rad over the drive (+0.005 and -0.003 on
  fixture_c170), so after the drive its heading is 0.015 to 0.018 rad off NDT's, which is
  closer to the truth. A sideways drift of the NDT track while driving (the across error above)
  is what such a bias absorbs. Not shown; a question for L3.

*Against the predictions.*
- N1 (the init: the winner's yaw is the start's, position under 0.1 m, scores not ordering yaw
  on fixture_c6b): the first two hold (+0.039/+0.041 and -0.0003/+0.016 rad; position at most
  0.093 m). The third fails as written: near the truth, a higher score goes with a smaller yaw
  error (rho -0.59 and -0.76 on fixture_c6b), but the top is too flat to choose. The particles at
  -0.011 and -0.002 rad scored 0.020 and 0.006 below the winner at +0.04, and in N1 the second
  best was the car turned round (dyaw -3.106 rad, 1.4 m across) at 0.017 below the winner.
- N2 (yaw inherited, within 0.005 rad standing and driving): holds standing, fails driving.
- N3 (170's across is the winner's): fails; it is made while driving.
- N4 (along follows speed through the stamp, not the pulls): holds (N4 33 to 36 ms, fixture_c6b
  27 to 33 ms; pulls near zero); N2's 47 to 58 ms is the exception.
- N5 (the standstill drift made by tracking through small pulls of one sign, under 1 mm a scan,
  all passing the gate): made by tracking, yes; the rest fails. The pulls are 3 to 10 cm and of
  both signs, the drift wanders either way, and the gate rejects some.

*What it means for batch L.* L1's pose-free start cannot do better on yaw than this align does;
its first metres carry the start's yaw error until driving removes it, so L3 should measure the
first 100 m. L2's stamp fix should remove the drive's along error (N4's prediction for L3).
The across error and the height belong with issue 198's maps: L3 on the rebuilt maps, against
this baseline on the old ones, separates them. The standstill wander is the matcher's own on a
featureless straight; the rebuilt maps and L2 may narrow it, and the EKF gate's rejections
show the EKF already distrusts it.

## L3: the campaign, plan and predictions (243, 2026-11-27, before any run)

L1 (b42c39f9: the pose-free initialization, GNSS on, the direct-localization option) and L2
(b1700191: aib dda18ad, a scan stamped at its render pose) are on main. Issue 198's maps are
rebuilt offline by 241 from its unlanded fix (siw 9bfd1b10). Every run records its map's
`pointcloud_map.pcd` sha256 and the code that built it.

*The maps.*

| map | sha256 | built by | road 0.2 m cells with a point | points over 2 cm below the road |
|---|---|---|---|---|
| fixture_c170 A (old) | 9cc1a29fb03167e44c3856ca38ee832be6af1826d390d5faff934f865affb713 | siw before 198 | 75.9 % | 65730 |
| fixture_c170 B (rebuilt) | 2658430d99c29a0eba325801421b57c064adbacc3b6e1a701dc4f227bf747538 | siw 9bfd1b10 (unlanded) | 47.0 % | 0 |
| fixture_c170 C (dense) | 47b8feb466f012537a7b43a11b78e4093c807d5c28f30ea62cf8cdc221495ca0 | siw 9bfd1b10 with the ribbon's step 0.1 m (local, on no branch) | 98.2 % | 0 |
| fixture_c6b old | 32bab6cc1a3ddccada85c3a897cb864e8b6cc762e82b9144342e1c69bab4e0f7 | siw before 198 | | |
| fixture_c6b rebuilt | aea7dc9d9fbc63f16940573c8b356aa716b99293e4305b0233a11198d2eba1e5 | siw 9bfd1b10 (unlanded) | | |

The rebuilt maps and C are on the NAS (`home/2026-11-27 issue 198 rebuilt fixture maps (241)/`,
with SHA256SUMS). Only `pointcloud_map.pcd` differs between a map's versions. B against C
changes the road's density alone; A against C changes the road's height alone.

*The runs.* 118's GPU0 for Isaac, from b1700191 (built 14:10 from a clean environment, aib
dda18ad in the world server's tree); 241's GPU1 for CARLA. A fresh stack for each run, the
default pilot (no direct localization), the NDT trace's topic list recorded in each.

| set | scenario and map | runs | what it measures |
|---|---|---|---|
| T170 | fixture_c170_down_hold on A, B and C, the hold at the goal 120 s | 2 per map, 6 | the drive and the stand; the start |
| T6b | fixture_c6b_r181 on old and rebuilt | 2 per map, 4 | the drive, the stop before the boulder and the stand; the start |
| S | the start and 120 s standing, no drive: fixture_c170 on B, fixture_c6b rebuilt | 2 and 4 | the start; the standstill before any motion |
| TW | CARLA town01_ego_drive | 8 | the start and the first 100 m on CARLA |
| H | haruna_down (the published map, not rebuilt) under `burn.py` (172's step 5 load) | 8 | 172's behind mode |
| F | 196's targets scenario with `face196.py` at 40, 60 and 120 Hz | 3 | the stamp's lag |

So eight pose-free starts per map: fixture_c170 6 + 2, fixture_c6b 4 + 4, Town01 8. 27 Isaac runs
and 8 CARLA runs.

*Readings.* As the baseline's (above): per scan, NDT's result less the truth in yaw, along,
across and z; NVTL, transform probability and iterations; the EKF's yaw bias and its
Mahalanobis gate. Each split into standing and moving, and the drive's along against speed.
Added: at the start, the initialized pose less the truth (yaw and position) and the calls it
took; over the first 100 m driven, the truth's distance from the lane's centreline and NDT's yaw
error. The noise between maps is the spread between a map's two runs; a difference between maps
counts only when it exceeds the larger of the two maps' spreads.

*Predictions.*
- P1, the starts. Every start initializes from GNSS without a scenario pose, on the first call in
  at least 7 of 8 per map; none ends the run. The initialized pose's position is within 0.15 m
  of the truth. Its yaw error is the align's: fixture_c6b median 0.02 to 0.08 rad (the draws'
  spread, up to 0.14); fixture_c170 under 0.02 rad; Town01 under 0.01 rad in all 8.
- P2, the first 100 m. NDT's yaw error falls below 0.01 rad within the first 100 m on every
  Isaac run. On fixture_c6b the largest distance of the truth from the lane's centreline in the
  first 100 m follows the start's |yaw| error (Spearman rho above 0.6 over its 8 starts); on
  Town01 it stays under 0.2 m.
- P3, the along against speed (L2). From 4 m/s up, the drive's median along error is within
  0.05 m of zero on both maps (tau under 5 ms; the baseline 27 to 36 ms), on A, B and C alike.
  The baseline's N2 (47 to 58 ms) was a second, unexplained lag; if it recurs, a run reads about
  -0.1 to -0.2 m at 11 m/s, recorded as such.
- P4, 196's faces (F). tau under 2 ms at 40, 60 and 120 Hz (the baseline 25.6 to 42.7 ms).
- P5, the across (170). fixture_c170's drive median across stays +0.10 to +0.25 m on A, B and C
  alike, within the maps' noise of each other: 198's survey found no left-right asymmetry, and
  the road is straight, where the stamp acts along. 170 stays open.
- P6, the height. NDT's z error, constant per run on the baseline (-0.012 c170, -0.024 c6b),
  is within 0.005 m of zero on B, C and the rebuilt fixture_c6b, and repeats on A and the old
  fixture_c6b.
- P7, density (B against C, 133's question). NVTL, transform probability, iterations and the
  four errors, standing and moving, agree between B and C within the maps' noise. If C's NVTL
  is higher beyond the noise and its errors are no worse, C wins; if C's errors are lower beyond
  the noise in both runs, the densifying goes into 198 before the published maps are rebuilt.
- P8, the standstill (182, and 133's ask). Over 120 s stopped, NDT's along still wanders: peak to
  peak 0.2 to 0.8 m on every map, A, B and C alike within noise, through per-scan jumps of a few
  cm of both signs. The stamp does not act on a car standing still, and on a straight the along
  direction is held only by what lies beside the road. The S runs (no motion before the stand)
  wander less than the T runs' stands, with fewer gate rejections (the baseline had none before
  the first motion).
- P9, the drive's NVTL is no lower than the baseline's on the same map (A, old fixture_c6b): a
  scan is no longer matched against a pose 34 ms off.
- P10, Haruna (172). 172 holds that every run starts motion with the EKF 20 to 34 ms late and
  that a behind run keeps it, which looks like L2's lag at 60 Hz ((n - 1) dt, 33 ms). But 172's
  level runs read +0.002 to +0.007 m along at cruise, where the baseline's fixture_c170 runs read
  -v x 33 ms: Haruna's runs did not carry the stamp lag as fixture_c170's did, and why is not
  known (the rig's point format, `xyzirc` or `xyzircaedt`, which L2 leaves alone, is recorded in
  each H run). So the prediction: L2 moves neither mode; under `burn.py` at least 3 of 8 runs are
  behind (along at cruise about -0.086 m; step 5: 6 of 9) and the rest level. If 0 of 8 are
  behind, L2 acts on 172 by a route this does not explain, and that is the reading's first
  question.

*Order.* F first (it is the shortest check that L2 works); then T170, T6b, S and H on GPU0; TW on
GPU1 in parallel. Results are committed here, tables first, before the reading.

*Amendment (133, before any H run): H on the old and a rebuilt Haruna.* Issue 198's survey found
72.0 % of the published Haruna's road cells terrain-only, a median 0.131 m below the road; that
is the map 172's two modes ran on. 241 rebuilds Haruna locally with siw 9bfd1b10, kept on the NAS
and not uploaded; its sha256 and builder go in each run's record as for the fixtures. H becomes
two arms under `burn.py`, at least 4 runs each, interleaved: the published map (combined
sha256 a54e0a3b) and the rebuilt one.

*Prediction P10b (replacing P10's count).* The behind mode survives the rebuild: at least 2 of 4
runs behind on each map (step 5's rate, 6 of 9, gives 0 of 4 with probability about 1 %). The
reason: the mode appears with CPU contention and not without it (step 5: 0 of 9 quiet on the
same build and map), which points to timing at the first motion, and the map is the same in
both of step 5's arms. A geometric note, not a prediction: a behind run's NDT z is 6 to 7 mm
higher than a level run's: 0.086 m back up a grade of 7 to 8 % gives that, so if the course's
grade at cruise is near it (read from the truth trace in H), the two modes sit on one surface,
not on two. If the rebuilt arm has 0 behind in 4 or
more while the published arm keeps its rate, the second minimum was the map's, and 172 moves to
198.

## L1b: a GNSS/INS heading for the pose-free start (243, 2026-11-27, plan and predictions before any code)

*What L3's first run found* (118's F40a, `2026-11-27T14-15-02_fixture_c170_targets_r0`, map A;
NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 195 L3 (118)/runs/F40a-.../`). The car
stood at (20.00, 1.62) the whole run. The estimate came up at x 21.39, and SSv2's concealer,
which checks the estimate against the scenario's pose within 1 m before it requests a route,
refused the route. The cause is in our sensor kit: its `gnss.launch.xml` (autoware_sim_vehicle's
template `autoware_gen/templates/@KIT@_launch/launch/gnss.launch.xml`, generated into each car's
kit) runs gnss_poser with `use_gnss_ins_orientation: false`, so the GNSS pose's yaw is the
bearing between consecutive fixes. Autoware's own default is true. With A9's 2 cm noise and
the car still, that bearing is random: the recorded `/sensing/gnss/pose_with_covariance` yaw
went +0.036, +0.303, +1.647, -1.861, -2.689 rad over the first five seconds. gnss_poser then
moves the antenna (gnss_link, 0.797 m ahead of base_link and 1.80 m up) to base_link along
that yaw, so the GNSS's base_link wandered on a circle of about 0.8 m around the antenna.
`/initialpose3d` took (21.18, 1.18), and NDT kept the along offset on the straight. Before A9
the fixes were identical, the bearing was 0, and a start facing +x came out right by chance.
Every pose-free start is exposed, on CARLA as on Isaac (acb has the same noise and kit).

*The user's decision (2026-11-27):* a simulated GNSS/INS heading, as a sensor with its own
noise, the way an RTK car with a dual-antenna receiver or an INS has one. No ground-truth pose
goes to Autoware.

*The change.*
- **aib and acb (118):** each vehicle bridge publishes `autoware_sensing_msgs/
  GnssInsOrientationStamped` on `/autoware_orientation` (the topic gnss_poser's stock launch
  reads), at the GNSS's rate with the fix's stamp, frame `gnss_link`. The orientation is
  gnss_link's in the map (base_link's orientation composed with the mount), with the
  receiver's error: yaw `heading_stddev_deg` (default 0.2, a dual-antenna RTK heading), roll and
  pitch `attitude_stddev_deg` (default 0.05). The rmse fields carry those standard deviations.
  The keys sit beside A9's GNSS noise keys (aib's `gnss` block, `GNSS_NOISE_DEFAULTS`; acb's
  `gnss_noise_*` parameters), drawn from the same seeded generator, and `enabled: false` gives
  the exact orientation as it gives the exact position (the truth only in the same debug
  sense). The orientation is computed from the simulated receiver's pose, not taken from the
  IMU's message.
- **autoware_sim_vehicle (243):** the kit template sets `use_gnss_ins_orientation` back to true
  and remaps `autoware_orientation` to `/autoware_orientation`, gnss_poser's own launch default; the generated kits (tesla_model3, drift_mustang) regenerated from it. vehicle_check's
  contract gains the topic.
- **scensim (243):** the stack routes the two new keys with the GNSS block (`GNSS_ARGS`,
  `gnss_block()`), the project file documents them, and every run records its GNSS settings
  and the yaw source (`ins`, with its standard deviations and seed) in its result.
- **Tests first,** in each repository: a still car's published heading has the configured
  spread and the seed's values; `enabled: false` gives the exact orientation; the message's
  stamp and frame are the fix's; the kit's generated launch sets the parameter and the remap;
  scensim refuses an unknown key and passes the defaults through.

*The landing (as L1 and L2).* asv first; then the deps pins of acb, aib and siw that carry
asv, with acb's and aib's own publisher commits; then one scensim pin commit, gated with the
Isaac lane (`ISAAC_ROOT=/var/tmp/aeon/isaac-sim-6.2`). 133's OK is needed before each push.
L3's T, S and H wait for it; F finishes on the current main.

*Predictions (one stand-only start per map after the landing, before L3 resumes).*
- Q1: standing, `/sensing/gnss/pose_with_covariance`'s yaw stays within 0.012 rad of the
  truth's (3 sigma of 0.2 deg), and its base_link position within 0.05 m of the truth's (2 cm
  noise plus 0.8 m times the heading error, about 3 mm).
- Q2: the start's position (`/initialpose3d` and the first INITIALIZED estimate) within 0.15 m
  of the truth on fixture_c170 and fixture_c6b, and within 0.15 m on CARLA Town01. SSv2's
  concealer check passes on every start.
- Q3, the start's yaw (stated against 133's target of 0.01 rad): Autoware 1.5.0's NDT align
  samples yaw over the whole circle and uses only the guess's position and covariance, so the
  GNSS heading does not set the start's yaw. The prediction stays P1's: under 0.01 rad on
  Town01, under 0.02 rad on fixture_c170, 0.02 to 0.08 rad (median) on fixture_c6b. A c6b start
  within 0.01 rad would need the align to use the heading, which is a separate change
  (the initializer's yaw covariance or the align's sampling), not part of L1b.

## L3 TW, a pre-L1b sample on CARLA (241, 2026-11-27; not the TW set)

Five runs of town01_ego_drive at scensim main a89027a2, before L1b. 133 held the set after run
4 until L1b lands, and run 5 had already started. Kept for the reading: CARLA's pose-free starts
passed despite the GNSS noise. The NAS copy is `autoveh/logs/2026 SSv2 on CARLA/2026-11-27
issue 195 L3 TW (241)/pre-L1b sample/`.

- All 5 passed. Each start was pose-free, by Autoware's own initialization; the agent made no
  initialize call.
- The align's error against the truth (base_link): along -0.036 to -0.057 m, across -0.016 to
  -0.046 m, dyaw +0.0009 to +0.0013 rad. Inside P1's bounds (0.01 rad, 0.15 m) in all 5.
- NDT over the first 20 m: |dyaw| at most 0.0014 to 0.0029 rad, |across| at most 0.050 to
  0.060 m.
- P2 as written cannot hold on this scenario, by its layout, not by localization (243's
  error in writing it, recorded as such). The ego is spawned 0.645 m off its lanelet's centre
  in every run, the goal is 0.3 m off, and the drive is 66 m. So (a), the max |offset| over
  the drive, is 0.645 to 0.646.
- (b), POST HOC (chosen after run 1, not a prediction result): the max |offset| from 20 m to
  6 m before the goal is 0.053 to 0.056 m.

## A finding from a void TW run: under heavy load the pose-free align outlasts the agent's wait (241, 2026-11-27)

The first TW run at L1b's main (2c83fa71; `2026-11-27T16-11-25_town01_ego_drive_r0`) is void and
not counted: the host was loaded by my own builds besides other users' jobs. It still shows how
a pose-free start fails when the host is slow, so it is recorded here.
- The load average, read at 16:14:21, just after the align, was 71.5 (1 min) and 74.3 (5 min)
  on 24 cores; at 16:16:31 it was 201 (1 min). The run's start was not sampled.
- Autoware's own initialization (the automatic initializer) called the align server at 16:11:42
  and got its success at 16:12:55: **73 s**. The five pre-L1b runs, at a normal load, took 13
  to 18 s from the agent's reset to "initialized" (13.2, 14.1, 17.2, 17.5, 16.5 s).
- The agent waits out an initialization it did not start for at most `align_wait`, 60 s by
  default (`scensim_agent/adapters/autoware.py`, an agent_config key, agent-sdk.md). It gave up
  at 60 s, 13 s before the align finished, and the run ended "its reset failed: localization
  stayed INITIALIZING 60 s in an initialization the agent did not start".
- Since pose-free starts now depend on the align finishing, `align_wait` bounds how slow a host
  may be. It is already a config key; whether its default should scale (with the particle
  count, or a measured align time) is for 243's L-batch reading. Run 2 was refused at its start
  (I changed the testbench while its stack started) and is void with no finding.
- The rerun logs each run's load average at its start and its align duration. No build of
  mine runs on the host during it.

## L1b's checks, and L1c and L1d: plan and predictions (243, 2026-11-27, before any code)

*L1b is on main* (2c83fa71: asv 5a9131f, acb fafd5c3, aib 94ff923, siw 71a6ede). Its checks:

- CARLA Town01 (241, TW runs 1 and 2 at 2c83fa71, `2026-11-27T16-38-28` and `16-41-37`): the
  start within 0.053 and 0.038 m of the truth (Q2 holds), yaw +0.0011 and +0.0008 rad. Align 27.3 s
  at a load of 51 on 24 cores (an earlier run at load 71 took 73 s and outlasted the agent's 60 s
  wait: void, kept).
- Isaac (118, main 0e34220e, `Q_*` runs; fixture_c170 B and fixture_c6b rebuilt): the standing GNSS
  pose from its second fix on within 0.0103 rad (median 0.0023) and 0.078 m (median 0.023) of the
  truth: Q1 holds there. No offset: mean dx and dy within 2 mm.
- Q1 fails, as worded, on every stack's first GNSS pose: its yaw is the mount's (identity
  orientation: dyaw -3.105 rad on Town01 facing pi, +0.0364 on Isaac facing 0), 1.685 m off on
  Town01. gnss_poser's first fix met no orientation. In TW run 2 the fix and the orientation
  arrived together, the orientation first in the record, and the first pose was still the
  identity's: publishing order alone does not cover it. Neither run's initializer used that pose
  (its call came 1.5 to 1.8 s, 14 to 15 poses, later); one 0.1 s window cannot be ruled out.
- Q2 fails on both Isaac straights: `/initialpose3d` 1.617 m from the truth on fixture_c170 B, 0.606
  m on fixture_c6b, though the GNSS poses around it were within 0.05 m. pose_initializer samples
  the align's particles from `gnss_particle_covariance`, Autoware's 1.0 m^2 in x and y (an ordinary
  receiver's), and on a straight NDT's score is flat along the road, so a particle 1.6 m ahead can
  win. Town01's structure pins it.
- On CARLA every GNSS pose sits about 0.82 m to the right of base_link (across -0.818 m, along
  -0.07; before L1b -0.843), and not on Isaac. A forward lever arm cannot make a sideways error;
  241 is locating it in acb (the map-frame error, the raw antenna against the truth's, the GNSS
  sensor's transform against the actor's, a start at another heading). Today's 1 m^2 particle
  spread absorbs it.
- S (a start, then 120 s standing without a route) cannot run: SSv2 does not run an ego without a
  route ("waited for the Autoware state to transition to PLANNING ... WAITING_FOR_ROUTE"). S is
  dropped (133); the standstill comes from T's 120 s holds and their stand before the first motion.

*L1c (118, aib and acb).* Each frame the orientation goes out before the fix, both with one
stamp, and no NavSatFix is published until the orientation has gone out for at least two GNSS
periods, so gnss_poser has a heading before its first fix whatever the delivery order. Tests
first; the commit states what gnss_poser 0.48.0 does with a fix that arrives before any
orientation.

*acb's offset (241).* Fixed where it is found, test first.

*L1d (243, asv and scensim).* pose_initializer's GNSS particle spread follows the receiver, as a
car with an RTK receiver is configured: the x and y variance (3 horizontal_stddev_m)^2, at least
0.01 m^2 (0.01 for the 2 cm default); z, roll, pitch and yaw as now (the align samples yaw over the
circle). The profile's `pose_initializer.param.yaml` takes the default; scensim writes the stack's
own copy when a project's `gnss_noise_horizontal_stddev_m` gives another, and passes its path.

*The landing.* L1c, acb's offset fix and L1d in one scensim pin, gated with the Isaac lane: L1d
must not land without the offset fix, since a 0.1 m spread cannot absorb a 0.82 m error and every
CARLA start would then align from the wrong place.

*Predictions (one CARLA Town01 start and both Isaac straights, two starts each, after the
landing; then L3's T and H).*
- C1: every stack's first GNSS pose within 0.012 rad and 0.05 m of the truth, on both simulators.
- C2: on CARLA the standing GNSS pose's mean across within 0.05 m of zero.
- C3: `/initialpose3d` within 0.15 m of the truth on fixture_c170 B, fixture_c6b rebuilt and Town01,
  in every start; its yaw as P1 (the align's: under 0.02 rad on fixture_c170, 0.02 to 0.08 on
  fixture_c6b, under 0.01 on Town01).
- C4: the align's duration no longer than before at the same load (fewer particles land far off;
  the particle count is unchanged).

## CARLA's GNSS sits 0.82 m off: a hypothesis and predictions (241, 2026-11-27, before the runs)

**What is seen.** On CARLA, gnss_poser's pose (`/sensing/gnss/pose_with_covariance`) sits off the
base_link truth by a steady map dx +0.07, dy +0.82 m, dz 0.00 m (TW at L1b, runs 1 and 2, standing
and driving alike, the car facing pi at y -130). The pre-L1b run shows the same while driving
(dy +0.845). The CARLA GNSS sensor itself sits where the spec says: acb's log places it at
base_link + (0.797, 0.004, 1.802), so 0.004 m sideways. Isaac shows no such offset (118: about
1 mm). Every start's guess is therefore about 0.8 m off, which L1d's narrower particle spread
could not absorb.

**The hypothesis: a sphere against an ellipsoid.** CARLA turns a world position into latitude and
longitude on a sphere of radius a = 6378137 m (its Mercator, lat_0 = lon_0 = 0: latitude =
y / a to first order). Autoware's map projector here is a transverse Mercator on the WGS84
ellipsoid (`map_projector_info.yaml`: origin 0, 0). Near the equator its northing is the
meridian arc, a (1 - e^2) phi, with e^2 = 0.00669438. So a CARLA latitude phi = y / a comes back
as a northing of (1 - e^2) y: |y| short by e^2 |y|. Eastings agree (the prime vertical radius is
a at the equator). acb negates latitude for the map's y = -CARLA_y, which keeps the sign. So:
- the error is world-fixed, along map y only, toward y = 0, and grows with |y|: e^2 |y|;
- at y -130.1: +0.871 m predicted, against +0.82 m measured (the 0.05 m rest not explained yet);
- Town01's far corner (y -330) would be 2.2 m off.

**Predictions** for two stand-and-drive runs on Town01's north-south lanes (project
`i195_gnss`: the raw fix `/sensing/gnss/gnss_link/nav_sat_fix` and `/tf` added to the record;
the car facing north at x 396.4 from y -250 to -180, and south at x 392.4 from y -100 to -170):
- G1: the error is along map y and world-fixed. Facing north or south, it lies ALONG the car,
  not across it; |dx| stays under 0.1 m.
- G2: it scales with |y|. Facing north from y -250 to -180, map dy falls from +1.67 to +1.20 m
  (within 0.1 m of e^2 |y| at each point). Facing south from y -100 to -170, it grows from +0.67
  to +1.14 m.
- G3: the raw fix converted by the same projector (the antenna, before gnss_poser) is off the
  truth antenna (base_link + R (0.8, 0, 1.8)) by the same e^2 |y| along y. That puts the error in
  acb's fix, not in gnss_poser's lever arm.
- If G1 or G2 fails (the error turns with the car, or does not scale with y), the hypothesis is
  wrong and the cause is car-fixed: the lever arm or the sensor's mount.

## CARLA's GNSS offset: the results (241, 2026-11-27)

Two runs at L1b's code (2c83fa71), project `i195_gnss`, the raw fix and `/tf` recorded: the car
facing north at x 396.4 from y -250 to -190, and facing south at x 392.4 from y -100 to -160.
Both passed. A third, at heading pi (TW's start, 190.8, -130.1), recorded the raw fix too.
`g3_195.py` projects the raw fix as Autoware's projector does (pyproj WGS84 TM, origin 0, 0, the
declared scale 1.0) against the truth antenna, base_link + R (0.8, 0, 1.8).

| run | map x | map y | raw fix dx | raw fix dy | gnss_poser dx | gnss_poser dy | exact model dx / dy |
|---|---|---|---|---|---|---|---|
| west (pi) | 190.8 | -130 | +0.075 | +0.815 | +0.072 | +0.818 | +0.076 / +0.819 |
| north | 396.4 | -250 | +0.155 | +1.566 | +0.159 | +1.569 | +0.160 / +1.574 |
| north | 396.4 | -220 | +0.150 | +1.385 | +0.156 | +1.387 | +0.160 / +1.385 |
| north | 396.4 | -190 | +0.159 | +1.190 | +0.160 | +1.186 | +0.160 / +1.196 |
| south | 392.4 | -100 | +0.161 | +0.637 | +0.159 | +0.635 | +0.158 / +0.629 |
| south | 392.4 | -130 | +0.157 | +0.823 | +0.153 | +0.827 | +0.158 / +0.818 |
| south | 392.4 | -160 | +0.160 | +1.002 | +0.156 | +1.003 | +0.158 / +1.007 |

The exact model is CARLA's own geolocation (queried live on Town01: lat 0, lon 0 at (0, 0); its
lat/lon is a sphere of about 6375570 m) projected by WGS84 TM at scale 1.0. It matches every row
within 0.01 m. The first-order e^2 |y| of the hypothesis was too crude: it gave y only, and too
much of it (0.0067 |y| against the exact 0.0063 |y|), and no x term (0.0004 x).

**Against the predictions, as written.**
- G1 FAILED as written. The error is along map y and world-fixed, as G1 said: facing north or
  south it lies along the car, facing west across it, with the same map dy at the same y. But
  |dx| is 0.15 to 0.16 m at x 392 to 396, not under 0.1 m: the x term the first-order model left
  out.
- G2 FAILED as written, at one point of seven per run. The error scales with |y| as predicted,
  but at y -250 it is 1.566, 0.108 m under e^2 |y| (bar 0.1 m); the other 13 points are within
  0.04 to 0.10 m.
- G3 held: the raw fix is off the truth antenna by the same amount as gnss_poser's pose is off
  base_link (within 0.007 m), so the error is in acb's fix, not in gnss_poser's lever arm.
- The 0.05 m residual noted at y -130 is explained: it was the first-order model's, not the
  data's.

**The scale.** Autoware reads the declared `scale_factor`: with 1.0 (every CARLA town in
carla-town-autoware-maps at the pinned df499322) the measured dx matches k = 1 and not 0.9996
(which would give dx about 0 at x 190.8). A map file without the key (the course fixtures)
projects with Autoware's default, 0.9996 (118's 1 mm on Isaac).

**The fix** (next, test-first in acb, on L1c's acb main 2358180): build the fix from the GNSS
sensor's own world location, inverting the projector the map declares (type, origin, scale;
0.9996 when the scale is absent) exactly, instead of negating CARLA's spherical latitude. The
same test vectors as aib's (118's file): every CARLA town to 20 m past its corners, a course
fixture, a declared-scale map and an MGRS square, 0.01 m. aib's TM-at-(0, 0) path, also
spherical (118: 0.92 m at (190.8, -130.1)), is 118's.

## Open item: no pose-free start on indoor or Local maps (133, 2026-11-27)

Indoor or Local maps (golf-cart basements): no pose-free start yet. GNSS on such a map is refused
at start (aib 14ebf4c on Isaac; acb's equivalent from 241); such a map needs another start
source.

## Two aligns at each pose-free start (243, 2026-11-27; from the code, no runs)

Since L1 every stack's start holds two NDT aligns about 1.8 s apart (T170_A1 at t 1001.0 and
1002.8; the L2r check run the same).
- The first is Autoware's automatic_pose_initializer, which `gnss_enabled:=true` starts: it
  calls `/localization/initialize` once at the stack's start with an empty pose (GNSS).
- The second is scensim's vehicle agent, at the reset (`scensim_agent/adapters/autoware.py`, the
  reset's `initialize` stage). Before its first call it waits out an initialization it did not
  start (`_await_other`, issue 046), then calls `initialize` itself, so that its call comes after
  SSv2 has placed the car.

It is new since L1: before, a managed ego ran `gnss_enabled:=false` and the agent seeded the
scenario's pose (one align). A pose-free initialize is refused without `gnss_enabled` ("GNSS is
not supported"), so L1 turned it on and the automatic initializer runs too. It is not a race:
the agent waits it out. Each align is an independent draw from the same flat score; the agent's
replaces the first and is what the run drives on. So C3 and P1 are scored on the last
`/initialpose3d` before the first motion; the automatic one is recorded and labelled. 118's
`mcscore.py` splits the Monte Carlo markers per align (a burst of arrays per align); per align
the winner is rank 1 of 200 and the score is flat in yaw (T170_A1: align 1 dyaw -0.032, align 2
dyaw -0.071, the best particle within 0.01 rad 0.006 to 0.016 below each winner).

*Later, optional* (133, 2026-11-27; neither needed for L3):
- (i) the agent accepts a finished automatic initialization that ended after the car was placed,
  with the reset pose unchanged since, saving an align (it needs a reliable placed time);
- (ii) the automatic initializer off for a managed ego, the agent alone initializing from GNSS:
  pose_initializer's `gnss_enabled` without automatic_pose_initializer, a profile split of two
  switches the stock launch ties together.

## L3's T set on L2r: results (118's runs at scensim 23b65448, 2026-11-27; tables by 243)

*T170*:
- Runs: fixture_c170_down_hold120 on maps A, B and C, 2 each, interleaved, a fresh stack each.
- When and where: 22:24 to 22:50 on 118's GPU0. The host's 1-minute load was 18 to 63, from
  139's P4 runs on GPU1 and another user's compile.
- Outcome: all 6 passed.
- The scored start is the agent's last `/initialpose3d` (issue 195's two aligns).

| run | map | start pos / yaw | along slope | moving along | 100 m spread | across | z | hold along p2p | NVTL | aligns (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | A | 0.146 / +0.0018 | +0.00 % | -0.536 | 0.153 | +0.213 | -0.0113 | 0.592 | 3.354 | 5.1 + 7.6 |
| B1 | B | 0.098 / -0.0092 | +0.02 % | -0.398 | 0.184 | +0.022 | -0.0005 | 0.595 | 3.351 | 1.7 + 1.6 |
| C1 | C | 0.020 / +0.0042 | +0.01 % | -0.365 | 0.141 | +0.029 | +0.0001 | 0.588 | 3.351 | 1.3 + 1.3 |
| A2 | A | 0.284 / +0.0030 | -0.03 % | -0.391 | 0.198 | +0.130 | -0.0113 | 0.801 | 3.355 | 1.2 + 1.3 |
| B2 | B | 0.079 / +0.0065 | +0.01 % | -0.268 | 0.136 | +0.023 | -0.0005 | 0.451 | 3.353 | 1.6 + 1.2 |
| C2 | C | 0.158 / -0.0093 | -0.00 % | -0.303 | 0.116 | +0.025 | +0.0001 | 0.728 | 3.349 | 1.6 + 1.8 |

*T6b*:
- Runs: fixture_c6b_r181 on the old map (32bab6cc) and the rebuilt map (aea7dc9d), 2 each,
  interleaved.
- When and where: 22:52 to 23:07, after the testbench was rebuilt over 23b65448.
- Outcome: all 4 end at the scenario's 150 s timeout, as before.

| run | start pos / yaw | moving along | across | z | hold along p2p | NVTL | aligns (s) | contact |
|---|---|---|---|---|---|---|---|---|
| old1 | 0.216 / +0.047 | -0.357 | +0.217 | -0.0238 | 0.681 | 3.303 | 1.1 + 1.1 | none |
| rb1 | 0.114 / +0.0036 | -0.088 | +0.114 | -0.0086 | 0.882 | 3.316 | 1.2 + 1.3 | the boulder |
| old2 | 0.196 / -0.0155 | -0.132 | -0.223 | -0.0241 | 0.854 | 3.302 | 1.1 + 1.2 | none |
| rb2 | 0.124 / -0.022 | -0.392 | -0.235 | -0.0081 | 0.836 | 3.319 | 1.5 + 1.5 | the boulder |

The ego struck the boulder on the rebuilt map in both runs, and on the old map in neither. The
cause is read in issue 180 ("The r181 boulder on the rebuilt map: the stop releases"). Both maps
stop for it at the same place. On the rebuilt map the compare-map filter leaves it too few
points to hold the stop. The rebuilt maps' upload is held on it.

*Against the predictions*:
- C1 holds: the first GNSS pose is 0.030 / 0.029 m in all 10.
- C3's position: 4 of 6 on c170 and 2 of 4 on c6b are within 0.15 m (misses 0.284, 0.158,
  0.216, 0.196).
- P1's yaw holds on c170 (at most 0.0093 rad). On c6b the median is 0.019 rad, just better than
  the predicted 0.02 to 0.08.
- C4: aligns of 1.1 to 1.8 s, except A1's 5.1 and 7.6 s under a load of 63.
- P3 does not apply: L2 is reverted. The along sits at the old lag (c170 median about -0.37 m).
- No run drifts: the along slope is at most 0.03 % on c170. c6b's 60 m drive is too short for
  a slope.
- P5 fails, a prediction error. The across depends on the map: A reads +0.13 to +0.21 m, B and
  C +0.02 to +0.03 m. A is the old map, with points under the road.
- P6 holds on c170 (B and C within 0.0005 of zero, A repeats -0.0113). It fails on c6b's
  rebuilt map: -0.008, against the old map's -0.024.
- P7: B and C agree within the runs' spread on NVTL, along, across and z. C's better starts are
  the align's draw. The denser ribbon buys nothing measurable on c170.
- P8 holds on c170 (0.45 to 0.80). On c6b it exceeds 0.8 in 3 of 4 (to 0.88): the range was too
  tight.

## L3's H set on L2r: results (118's runs at scensim 23b65448, 2026-11-27 and 28; table only, the reading follows)

*The runs*:
- haruna_down on two maps, 4 each, interleaved (pub1 rb1 pub2 rb2 ... rb4), a fresh stack each:
  - pub: the published Haruna, dataset fff4cb0b, tile-set a54e0a3b (survey198's hash).
  - rb: 241's rebuilt Haruna, siw 9bfd1b10, tile-set 280e8b91, over the same course, isaac and
    scenarios.
- Testbench tb-l3h: issue 172 step 5's isaac_i172_smooth unchanged, plus the GNSS and align
  topics in the record. Physics 60 Hz: SSv2's 0.05 s step is 3 physics steps.
- When and where: 23:45 on the 27th to 01:01 on the 28th, on 118's GPU0.
- Outcome: all 8 passed, every judge (nvtl, physical_verdict, pose_error).

*The load (133's decision, 243's rule)*:
- burn.py is not run by default. 139's P4 runs on GPU1 stand in for step 5's contention, from
  another source.
- The rule: 30 s before each start, sample the 1-minute load. From 34 to 65 (step 5's starts),
  run as is. Under 34, add burn.py workers in steps of 8 until the load is at least 34 (118
  capped it at 24). Over 65, wait up to 10 min.
- From pub4 on (133): the sample is taken at least 60 s after the previous stack exits, and is
  logged itself.
- Two earlier runs are void and were re-run as pair 1. Both had burn.py at 24 on top of P4:
  pub1 (load about 95), and rb1 (load 183; SSv2's wall-clock timeout).

*Unplanned difference from step 5*: step 5 ran on isaac-ex/c6b-haruna/none/haruna, which has a
road_detail.yaml (086 C6b's "none" corridors over course/section.npz, gd0 1e-12): the road layer.
H's maps are copies of the dataset, without it: the plain course mesh. Both of H's arms have the
same road, so pub against rb is like for like. H's comparison with step 5's 6 of 9 is not like
for like on the road surface, and P10b is judged only within H.

*The table*:
- Columns:
  - The scored start is the last `/initialpose3d` before the first motion (2 in every run).
  - moving along is ndtT's median while moving (4.2 m/s); "less start" is moving along less the
    start's along.
  - decision is the 1-minute load sample that set burn.py; mean load is the 1-minute load's mean
    over the run (n samples, 30 s apart).
- Errors are against the truth, in m and rad.

| run | start along / across / yaw | moving along | less start | across | z | NVTL | decision | burn.py | mean load (n) | pose_error p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| pub1 | -0.022 / -0.046 / +0.0012 | -0.0971 | -0.0751 | -0.067 | -0.0182 | 3.162 | 64.21 | 0 | 40.3 (15) | 0.1814 |
| rb1 | +0.007 / -0.024 / -0.0002 | -0.0970 | -0.1041 | -0.037 | +0.0028 | 3.168 | 36.02 | 0 | 43.9 (17) | 0.170 |
| pub2 | -0.005 / -0.061 / +0.0000 | -0.0979 | -0.0929 | -0.066 | -0.0180 | 3.162 | 34.23 | 0 | 38.2 (16) | 0.1852 |
| rb2 | +0.038 / -0.046 / +0.0002 | -0.0965 | -0.1341 | -0.038 | +0.0027 | 3.168 | 37.89 (a) | 8 | 48.5 (17) | 0.1705 |
| pub3 | +0.041 / -0.061 / -0.0009 | -0.0078 | -0.0486 | -0.067 | -0.0246 | 3.163 | 45.73 (a) | 24 | 87.3 (19) | 0.1125 |
| rb3 | -0.008 / -0.034 / +0.0005 | -0.0255 | -0.0173 | -0.037 | -0.0021 | 3.168 | 52.98 | 0 | 22.0 (15) | 0.1124 |
| pub4 | -0.031 / -0.071 / +0.0011 | -0.0996 | -0.0687 | -0.068 | -0.0181 | 3.162 | 12.78 (b) | 24 | 81.4 (20) | 0.1815 |
| rb4 | -0.002 / -0.054 / +0.0003 | -0.0962 | -0.0947 | -0.037 | +0.0029 | 3.168 | 37.38 | 0 | 25.5 (14) | 0.168 |

- (a) The load after the adds. The decision sample itself, from the 30 s log, was under 34:
  - rb2: about 30 to 32;
  - pub3: about 23, falling as rb2's stack had exited. 8 workers gave 20.20, 16 gave 31.95, 24
    gave 45.73.
- (b) The decision sample, 60 s after rb3's stack exited. With 24 workers the load reached
  33.71, 0.3 under the window: marked.

*Pairs*:
- In-run load: pairs 1 (40.3 / 43.9) and 2 (38.2 / 48.5) are within 2x. Pairs 3 (87.3 / 22.0)
  and 4 (81.4 / 25.5) differ 4.0x and 3.2x and are marked. Both marked pairs are the ones whose
  pub run carried 24 workers.
- pub less rb, moving along: -0.0001, -0.0014, +0.0177, -0.0034 m.
- In every pair, pub against rb: across -0.066 to -0.068 against -0.037 to -0.038, z -0.018 to
  -0.025 against -0.002 to +0.003, NVTL 3.162 to 3.163 against 3.168.

*P10b as written*: at least 2 of 4 behind on each map. published 3 of 4 (pub3 level), rebuilt 3
of 4 (rb3 level). The behind runs read -0.0962 to -0.0996 m, the level runs -0.0078 and -0.0255.

The records are on the NAS (`autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 195 L3 (118)/`,
runs H2_* and the void H_*; scripts/ holds htable.py, htable_H2.txt, load_H.txt, the run
scripts and times.txt).

## The align's start yaw: a yaw prior in the overlay's NDT (241, 2026-11-27; plan approved by 133, predictions before any run)

**The user's decision (through 133, 2026-11-27):** fix the start yaw in our Autoware overlay.
Autoware 1.5.0's NDT align draws every particle's yaw uniformly over the circle
(`NDTScanMatcher::align_pose`, and localization_util's TPE, `get_next_input`), whatever the
guess's covariance says. On a straight NVTL is flat to about 0.015 across +-0.14 rad, so the
best particle's yaw is noise: C3 +0.061 rad.

**The change**, written to be upstreamable and reading no truth:

- autoware_core fork, branch `csb/ndt-step-reversal-1.5.0`, 61f9c96e (tests first: 0651ee25 and
  5c1347be, both failing before the fix; 84b86c2a formatting; 61f9c96e the change). A new
  parameter `initial_pose_estimation.yaw_prior_variance_threshold` [rad^2], upstream default
  0.0 (no change). When the guess's yaw variance is below it, the TPE takes a sixth sample mean
  and stddev and draws yaw from N(guess yaw, sqrt(variance)) in its startup trials and EI
  candidates; otherwise the uniform draw, in the same engine order as today. The TPE kernel and
  the selection (best NVTL) are unchanged.
- asv's profile: `gnss_particle_yaw_variance` (default 1.1e-4 rad^2, (3 x 0.2 deg)^2, the
  receiver's heading error, as L1d did for x and y) is pose_initializer's
  gnss_particle_covariance yaw, and ndt_scan_matcher's `yaw_prior_variance_threshold` is
  0.01 rad^2 (a guess better than 5.7 deg, 1 sigma).
- The Jazzy profile copies (config/2.0.0) are left alone, as L1d left them: the overlay fork is
  Autoware 1.5.0's, so the threshold would do nothing there (133 accepted).
- Before any upstream PR (not now): the two test files are formatted with clang-format 17, the
  host's; pre-commit pins v19. Reformat with v19 (pip `clang-format==19` in a venv, not the
  system's) first.

**A coupling of the pins.** The fork declares `yaw_prior_variance_threshold` without a default,
as ndt_scan_matcher declares every parameter, so its parameter file must carry the key: the
overlay at 61f9c96e with an asv whose ndt_scan_matcher.param.yaml lacks it (any asv before
9d4bc316) makes ndt_scan_matcher throw at start. The overlay pin and asv's pin therefore land in
one scensim commit, and nobody runs `just build-autoware-overlay` from the branch on a shared
host before it lands (133). Stock Autoware (`autoware_overlay:=false`) declares no such
parameter and ignores the key.

**Not covered: `ndt:=cuda`.** The profile's GPU NDT (third_party/cuda_ndt_matcher) is a
separate implementation and gets no yaw prior from this change; its align still draws yaw over
the circle. The profile's default is `ndt:=autoware`, so L3 and this change's live check are
covered.

**Predictions** (fixed before any run; the live check runs on 118 after L2r's check run):
fixture_c170 and fixture_c6b, 4 runs each, C3 yaw (the align's result against truth at the
start): **|C3 yaw| <= 0.03 rad in every run, and <= 0.01 rad in at least half, on each
fixture.** The reasoning: with NVTL flat in yaw the best particle is close to a random draw
from the prior, about N(guess, 0.0105 rad), and the guess itself is good (L1b's C1 0.0005 rad);
so within 0.01 in about 68 % of runs and within 3 sigma (0.03) in essentially all. 0.01 rad in
every run is not predicted.

**Recorded in each run, beside C3** (243): the guess's own yaw error, the GNSS/INS heading in
the align's request against the truth at the call (L1b's Q1 measure), so the reading separates
the prior's offset from the draw. With the heading's own error (about 0.0035 rad) added,
P(|C3| <= 0.01) is a little under the 0.68 of the draw alone.

**A possible follow-up, not in this change** (133: it changes the selection rule, more than the
user approved): among the particles whose NVTL is within a tolerance of the best (a parameter,
default 0, meaning off), take the one closest to the prior's mean. That would predict
|C3 yaw| <= 0.01 rad in every run.
