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
