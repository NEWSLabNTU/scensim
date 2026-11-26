# 172: on Isaac's haruna_down, localization runs either level with the car or 0.086 m behind it, per run

**Status:** open; plan written (2026-11-25, after 169's step 1 and 185), for 133. **Severity:** to be shown. It is the cause
of Haruna's bimodal pose error p95 (about 0.12 or about 0.18 m), which has widened every A/B's
noise on Haruna since 086 C5. **Found:** 2026-11-25, scensim 118, issue 168's A/B, round 1
(numbered by 133).

## What is the case

Localization's error against the truth along the track (median above 1 m/s,
`/localization/kinematic_state` against `ego.csv`; `c6e/i168/measure.py`, `c6e2/along.py`) sits
in one of two places per run:

| runs | along | pose error p95 |
|---|---|---|
| 168 A/B round 1: rough_on_1, smooth_off_1 | +0.002, +0.005 m | 0.120 m |
| 168 A/B round 1: rough_off_1, smooth_on_1 | -0.086, -0.085 m | 0.188, 0.186 m |
| 086 C6e2, motion BVH off: f1, f2, f3 | +0.007 m | 0.118 to 0.120 m |

- The mode does not follow issue 168's lowering: each side of round 1 has one run in each mode.
- It is not issue 169's motion BVH: that is off in every run above (169's own shift is
  +0.108 m, ahead).
- Across the track every run sits at -0.065 to -0.075 m (issue 170).
- **168's whole A/B (12 runs, 2026-11-25):** 4 of 12 runs behind (rough_off_1, smooth_off_2,
  smooth_on_1, smooth_on_2) and 8 level. A behind run's NDT z is 6 to 7 mm higher than a level
  run's on the same map. 167's reach check failed its pose and along bounds on that alone.
- The earlier high mode (C5's clean pairing: 0.18 m in five of six runs) was recorded without
  this split. Its runs can be read again for along-track with `measure.py`.

## Hypothesis (untested)

A per-run phase, set at start-up, between the lidar's revolution and the world's frames.
0.086 m at haruna_down's 4.5 m/s is about 19 ms, under half a 50 ms frame. If the scan's stamp
and the pose NDT starts from are taken one way in some runs and the other way in others, a
constant along-track lag follows for the whole run. Issue 015 (a scan stamped at the frame it
was read in, not the one it was rendered in) is of this kind and is fixed. This would be a
remaining case of it.

## Steps (predictions written before each, when taken up)

1. Read the mode of every recorded haruna_down run (C5, C6b, C6d, C6e2, 168's A/B) offline,
   with the lidar's first stamp and phase at start-up from each run's logs, and see whether
   the phase predicts the mode.
2. If it does, the fix is in aib's lidar (its stamp, or its revolution's phase at start-up),
   checked by runs that all land in one mode.

## The plan (written 2026-11-25, after issue 169's step 1 and issue 185, before any run; for 133)

**What 169 and 185 add.**

- 169's probe measures the render's age directly: the sensor's position when a wall is hit,
  against the root's, gave a lag of 0.100 s (two frames; 0.450 m at 4.5 m/s) in all 56
  revolutions of A, and of E at 4.5 and 9 m/s: three processes, three start-ups, one value. That is the quantity 172's hypothesis says
  varies per run. 0.086 m at 4.5 m/s is 19 ms.
- 185 shows that the annotator's own times follow the read frame, not the render, and that aib
  (on `xyzirc`) stamps each scan with the render frame's stamp, `latency` frames back, a
  constant. If the render's real age differs from `latency` x frame by 19 ms in some runs, the
  stamp is wrong by that much for the whole run, and localization sits v x 19 ms behind.
  *Hypothesis, untested:* that is 172's behind mode.
- 169's fix leaves this alone. Part 1 bases the times on `t_ref`, which uses the same
  `latency`. *Prediction:* 172's two modes persist after 169's parts 1 to 3, in both proportion
  and size, unless the render's age is fixed as well.

**The steps.**

1. *The render's age per start-up, with the probe* (169's probe, case A, 4.5 m/s, BVH off: 20
   processes in a row, GPU0, non-timing; each gives the lag over 56 revolutions). *Prediction
   (the hypothesis):* the lag is constant within a process. Across processes it takes two values
   about 19 ms apart (0.45 m and about 0.36 m, or 0.45 and 0.54 m), in roughly 2 of 3 and 1 of 3
   of the starts (168's 8 level against 4 behind). If all 20 give 0.100 s, the probe's
   start-up does not show the mode. The world server steps differently (its substeps, its
   frame pacing), so step 2 then measures it there.
2. *The render's age in the world server, per run* (no new run: from the logs and records that
   exist, if they hold enough; else a small addition to aib that logs, once per scan, the
   annotator's first point time against the frame it is read in, in a new run). *Prediction:*
   the behind runs' value differs from the level runs' by about 19 ms.
3. If 1 or 2 shows the age varying: aib measures the render's age at start-up (the annotator's
   time against the frame), not assuming `latency_frames`, and stamps from it. Checked by six
   haruna_down runs that all land in one mode. Its spec comes to 133 first.

## Step 1's result (2026-11-25, 118, GPU0, 18:48:53 to 18:52:21; non-timing, codec 118 told)

`isaac-ex/i172/run20.sh`: 169's probe, case A (`xyzircaedt`, motion BVH off, aib's distortion
off), at 4.5 m/s, 20 processes in a row, aib bb2283f. Each process's render age comes from the
walls (the root's x less the sensor's x at the ahead wall's hit, over v), over 56 revolutions.

- All 20 start-ups: **0.100 s** in every revolution (min and max equal), two frames.
- The prediction (two values about 19 ms apart across start-ups, at about 2:1): **FAILED**. The
  probe's start-up does not show the mode. As the plan says, this does not refute the
  hypothesis for the world server, which steps differently (its substeps, its frame pacing,
  the bridge's lockstep). Step 2 measures the render's age there.
- *Noted, from issue 170's step 1 (offline):* the behind runs (and C6e2's BVH-on runs, which are
  ahead) also sit 0.03 to 0.04 m further across in left bends than the level runs (-0.09 to
  -0.10 m against about -0.06 m), while the right bends and the straights are the same. An
  along error seen through a bend may be part of 170's split.

## Step 2's spec (written 2026-11-25, before any change or run; for 133)

**The observable.** The RTX annotator's `info` holds `transform`, the sensor's world pose the
revolution was rendered from (issue 167's probe printed it). aib keeps the sensor's track, its
pose a substep apart with the world's clock (`Lidar.track`). So each scan's render age is the
lidar's clock at the read less the track time whose pose is `transform`'s: the point on the track
nearest it, interpolated between substeps. That works when the car moves (above 1 m/s). The substeps are a few centimetres apart at
4.5 m/s, and interpolating between them resolves the age to about 1 ms.

**The change (aib, a branch `issue-172-age` from aib main, not landed).** In `Lidar._msg`,
behind a rig key `isaac.log_render_age` (default off, so nothing changes unless it is set):
compute the age as above and log it at INFO once a second (every 20th scan) and for the first
five scans: "lidar top: render age X ms (transform at track t, clock c, speed v)". Nothing
else changes, including the published cloud and its stamp. A unit test with a synthetic track
and a transform two frames back gives 100 ms.

**Checks before the runs.** (a) 169's probe with the branch and the key set, case A at 4.5 m/s:
the logged age equals the walls' 0.100 s within 2 ms. (b) The branch's `just test` in aib.

**The runs.** smooth haruna_down (C6e2's map, motion BVH off), 9 runs, from a testbench over a
workspace with the branch, the key set through the rig, GPU0, non-timing, with the per-run exe
and provenance checks as in 168's A/B. Nine, because with 168's split (4 behind in 12) the
chance of no behind run in nine is about 3 %. Each run is read with `c6e2/along.py` for its mode
and with its log for the age.

**Predictions (before any run).**
- Within a run, the age is constant within 2 ms after the first five scans.
- The hypothesis: the behind runs' age is larger than the level runs' by about 19 ms (0.086 m /
  4.5 m/s), and each run's along median follows -v x (age - the level runs' age) within 0.01 m.
- If every run's age is the same (within 2 ms) while the modes still split, the hypothesis
  **fails**. The stamp is then not the cause, and the next candidate is NDT's or the EKF's
  start-up (their first pose and its time), from the same runs' logs.
- *Amended before the runs (118, 2026-11-25; the mechanism only).* The rig is generated from
  the car's spec (`do not edit`), and a key added there changes the spec hash, which the bridge
  checks. So the branch also reads `AIB_LOG_RENDER_AGE=1` from the environment, and the runs set
  it. Check (a) passed before this: the probe logged 100.0 ms against the walls' 0.100 s (19:03).
  Check (b): aib's `just test` passed on the branch, 174 tests. The branch is aib 3b69851, local
  only, in `ws-c6e3`'s aib submodule. The runs use scensim main 0291abb3, so issue 168's
  lowering is in (smooth haruna: the bound's WARN, since no `base_drop` is stored), unlike C6e2.
  The runner refuses a run whose console has no render-age line.
- *During the runs (labelled, 133).* **result.json's `src/autoware_isaac_bridge` field is the
  install's build commit, not the source that ran.** It records bb2283f, the commit `ws-c6e3` was
  built at. aib is a Python package linked into the install (`build/aib/aib` resolves to
  `src/autoware_isaac_bridge/src/aib/aib`), so the branch's code, 3b69851, is what ran. The
  render-age lines prove it, since only the branch logs them (380 in r1). Each run therefore has a
  sidecar, `isaac-ex/i172/aib_source_<run>.txt`: aib's `git rev-parse HEAD` and
  `git status --porcelain`, read from the linked source directory. From r3 it is read at the run's
  start. r1's and r2's were written after their starts (19:15:10), labelled so: the source was
  committed at 19:04:00, before r1 (19:04:57), and was not edited after, its status clean.
- *The runner's check was widened mid-series, after r1 (labelled).* r1 was refused for naming aib
  bb2283f and then accepted by hand, the render-age lines being the proof. The check was widened
  at 19:14:04 to accept bb2283f when the console has render-age lines. r2 to r9 ran under the
  widened check. `times.txt` has the record.
- *A further hypothesis, written before looking at the load (133, 2026-11-25).* The host's
  load from other work (another user's cargo builds were running at about 99 load on 48 CPUs at
  20:03) differs at each run's start-up, and a loaded start-up puts NDT's or the EKF's first
  estimate, or the stack's pacing, into the behind mode. *Prediction if it holds:* the behind
  runs' host CPU use and load average in the first 30 s after the stack's start are higher than
  every level run's, with no overlap. *If they overlap,* load at start-up is not the cause. Read
  offline from each run's `play_launch` `system_stats.csv`.
- *The load hypothesis, measured by proxies (amended before looking, 133; only r1's values had
  been seen).* These runs have no `system_stats.csv`: scensim's stacks keep ros2-launch logs, not
  play_launch's. So load is read through proxies, with these directions predicted if the
  hypothesis holds: the behind runs are slower from `stack.start` to `world.ready` and to
  `pilot.ready` (`stacks/<id>/events.jsonl`), and have a higher `tick_p95` (result.json) than
  the level runs. r8's and r9's load averages at their starts come from a watcher. A start-up
  lag is a weaker signal than the load itself, so a "no overlap" on the proxies counts as
  suggestive at most, not as shown.

## Step 2's result (2026-11-25, 118, GPU0, 19:04:57 to 20:26:46; non-timing, codec told)

Nine smooth haruna_down runs (r3 rerun; see times.txt for r1's hand acceptance, r3's two
attempts and the record's amendment from r3). Each mode is read with `c6e2/along.py`, and the
render age with the branch's log lines (364 or 365 per run, after the first moving scan).

| run | start | along | mode | render age (every logged scan) | stack.start to world.ready / pilot.ready | tick p50 / p95 / max, over budget |
|---|---|---|---|---|---|---|
| r1 | 19:05 | +0.005 | level | 100.0 ms | 14.6 / 32.0 s | 50.3 / 104.6 / 597 ms, 110 |
| r2 | 19:14 | -0.086 | **behind** | 100.0 ms | 14.6 / 32.1 s | 55.8 / 113.9 / 214 ms, 125 |
| r3 | 19:24 | +0.004 | level | 100.0 ms | 14.6 / 31.9 s | 50.7 / 101.9 / 184 ms, 76 |
| r4 | 19:33 | +0.005 | level | 100.0 ms | 14.6 / 31.8 s | 50.6 / 90.8 / 176 ms, 68 |
| r5 | 19:41 | +0.004 | level | 100.0 ms | 14.6 / 32.1 s | 49.1 / 70.0 / 998 ms, 46 |
| r6 | 19:49 | +0.005 | level | 100.0 ms | 14.6 / 32.1 s | 49.4 / 79.6 / 164 ms, 46 |
| r7 | 19:57 | -0.087 | **behind** | 100.0 ms | 14.6 / 33.1 s | 67.3 / 155.9 / 277 ms, 388 |
| r8 | 20:08 | +0.005 | level | 100.0 ms | 26.1 / 36.7 s | 64.4 / 95.8 / 336 ms, 193 |
| r9 | 20:18 | -0.089 | **behind** | 100.0 ms | 14.6 / 38.6 s | 53.2 / 125.7 / 195 ms, 140 |

Load averages at the start: r8 47.50 (level), r9 44.60 (behind). A 25 s build of mine ran
mid-r7, not at its start.

- *Within a run, the age is constant within 2 ms:* **held** (100.0 ms in every logged scan).
- *The hypothesis (the behind runs' render age about 19 ms larger):* **FAILED.** Three behind runs
  in nine (r2, r7, r9), all at exactly the level runs' 100.0 ms. The render's age is not the cause.
- *The load hypothesis, by proxies (suggestive at most, as written):* world.ready **FAILED**
  (the behind runs are at 14.6 s like six level runs; the one slow start, 26.1 s, is level r8).
  pilot.ready **FAILED** (overlap: behind 32.1 to 38.6 s, level 31.8 to 36.7 s). tick_p95: no
  overlap (behind 113.9 to 155.9 ms, level 70.0 to 104.6 ms). That is suggestive only, and it is
  over the whole run, so it may be an effect of the mode, not its cause. The start loads read
  directly go the other way: behind r9 started at a lower load than level r8. **Load at start-up
  is not supported.**
- *A new finding from the start-up record (r3 to r9, the amendment's topics; found after the
  result, labelled).* `startup172.py`: standing still before the car moves, NDT's along error is
  within 1 cm of 0 in **every** run (r7 +0.004, r9 -0.002). The behind runs' -0.085 to -0.089 m
  appears only once the car moves, from the first moving NDT output, and stays for the whole
  run. So the behind mode is not a position offset: it is a time offset of about 19 ms (0.086 m
  at 4.5 m/s) between the scan and the pose it is matched or fused at, set per run before the car
  moves. It is not the render's age. The initial pose (`/initialpose3d`, one message) is off by
  -0.128 to +0.136 m along and does not predict the mode (behind r7 +0.136, level r8 -0.128,
  behind r9 -0.018). The behind runs' first NDT output came earlier after the clock's start
  (1006.1 and 1005.8 s against 1006.2 to 1006.8 s for the level runs). That is a pattern in two
  runs, noted and not claimed.
- *Next (to plan with 133):* a 19 ms time offset fixed at start-up, outside the render's age.
  The candidates are the scan's header stamp against the sim clock (the phase between the
  lidar's 20 Hz publish and `/clock`), and what NDT and the EKF use to time-align a scan (the
  twist's and pose's interpolation at the stamp). The record to settle it is each scan's header
  stamp against the frame it was rendered in, logged by the same branch, in a few runs.

## Step 3's plan, the stamp's phase (written 2026-11-25, before any change or run; for 133)

**The physics rate, read before writing the number.** The world server's launch defaults
`physics_hz` to 60 (`scensim_isaac_world/launch/world_server.launch.py`), and step 2's stacks
ran with `physics-hz 60` (their launch logs). So a physics step is 16.67 ms, three to a 50 ms
frame (the rig's own `physx_substeps: 8` are inside each vehicle step).

**The hypothesis (133's; untested).** A scan is stamped one physics step off its render, and
which way is set by the phase at start-up. That would give a constant per-run time offset, as
step 2 found. *A tension, written now:* one step is 16.67 ms, which at the runs' speed
(about 4.5 m/s) is about 0.075 m behind. Step 2's behind runs sit at 0.086 to 0.089 m, about
19 ms at 4.5 m/s, and the level runs at +0.004 to +0.005. The offset between the modes, about
0.09 m, is closer to 20 ms than to 16.7. So the hypothesis must also account for the rest, or it
explains the mode only in part.

**The observable.** aib's `Lidar.publish(state, sim_time, stamp)` already computes
`to_sim = sim_time - self.clock`, the host's sim time less the lidar's own clock (the sum of its
substeps' dt). A per-run phase between the host's frames and the physics steps shows there as a
per-run constant. On the same branch (`issue-172-age`, local), logged beside the render age, once
a second and for the first five scans: the header stamp the scan goes out with (`stamps[0]`),
`sim_time`, the lidar's `clock`, `to_sim`, the number of substeps aib saw since the last frame
and their dt, and the frame count. A unit test fixes the line's format.

**The runs.** `ws-c6e3` rebuilt at the main of the day first (161 moved pins; 133), then the
branch's aib in it again, with the source sidecar, and the same checks as step 2. Nine smooth
haruna_down runs as in step 2 (the chance of no behind run in nine at 3 in 9 is about 3 %), the
record as amended in step 2. No edits during a run.

**Predictions (before any run).**
- Within a run, `to_sim` and the substeps per frame are constant after start-up (to_sim within
  1 ms; three substeps of 16.67 ms a frame).
- *The hypothesis:* the behind runs' `to_sim` differs from the level runs' by one physics step,
  16.67 ms (within 1 ms), and the level runs share one value.
- *If the modes' `to_sim` are the same,* the stamp's phase against the physics is not the cause,
  and the next candidate is downstream: how NDT and the EKF time-align a scan, read from the same
  runs' `pose_with_covariance` and `kinematic_state` stamps against the scans'.
- *If they differ by about 19 to 20 ms rather than 16.67,* the phase is the cause but not a
  whole physics step, and the record says what it is.
- *Added (133, before any run; to run after C7 and the 169 landing).* NDT's and the EKF's input
  stamps for the same scan are read offline from the recorded topics, not from aib. NDT stamps
  its `pose_with_covariance` with the stamp of the cloud it matched, and that pose is the EKF's
  pose input, so the recorded `pose_with_covariance` stamps are the scans' stamps as NDT saw them.
  They are compared with aib's logged header stamps for the same scans (the same sim time to the
  frame) and with the EKF's `kinematic_state` stamps. Then the judgement can tell the stamp's phase
  (aib's stamp against the physics) apart from the alignment downstream (NDT's or the EKF's use of
  that stamp) with the same runs.

**Amended before the runs (2026-11-25, 133's OK of the diff; not after a result).**
- *The code:* aib **86a9207** (local branch `issue-172-age`, on 3b69851, not pushed). Behind the
  same switch as the render age (`AIB_LOG_RENDER_AGE=1` for these runs), one line a publish:
  `sim_time`, `clock`, `to_sim`, this frame's stamp, the stamp of the scan published now
  (rendered `latency` frames ago), the substeps since the last publish and `frame_dt`. It logs
  every publish for the first 100, then every 10th, instead of the plan's "the first five and
  once a second", so that start-up is covered publish by publish. A unit test fixes the format
  and the thinning.
- *No internal `/clock` value in aib:* `sim_time` is the host's value that drives `/clock`, so
  `/clock` itself is added to the record (133's OK), with
  `/localization/pose_estimator/pose_with_covariance` for NDT's stamps. The names are checked on a
  live stack between runs, before the first run, and not changed during one.
- *The runs* are under the full quiet rule (133), on GPU0, codec 118 told first. Provenance is
  accepted only with aib 86a9207 running (the source sidecar's head, and the timing lines in the
  world server's console); result.json's aib field records the build's commit, as in step 2.
- *The predictions above stand unchanged.* One reading is added for the judgement: in a behind
  run, the stamp of the scan published now against the sim time of the frame it was rendered in
  (the `latency` frames before) differs from a level run's by the same offset as `to_sim`, if
  the phase is the cause.

## Step 3's result (2026-11-25 to 26, 118, GPU0, 22:54:58 to 00:15:53; the quiet rule, codec told)

Nine smooth haruna_down runs at scensim main 1ed265d7 (scensim_isaac_world 3a948eea) with aib
86a9207, all accepted. Each had rc 0, its provenance checked, the aib source sidecar's head at
86a9207, and 839 to 845 timing lines in the world server's console. gpu_log.txt shows no foreign
process on GPU0 during any run, so none is void. Readings: `step3.py`, `startup172.py` (the mode),
`tick3.py`.

| run | start | NDT along (moving, after 30 s) | standing still | mode |
|---|---|---|---|---|
| r1 | 23:05 | -0.0013 | -0.0066 | level |
| r2 | 23:13 | -0.0005 | +0.0016 | level |
| r3 | 23:21 | -0.0008 | -0.0063 | level |
| r4 | 23:30 | -0.0015 | +0.0010 | level |
| r5 | 23:38 | -0.0008 | -0.0045 | level |
| r6 | 23:46 | -0.0010 | -0.0033 | level |
| r7 | 23:53 | -0.0008 | -0.0007 | level |
| r8 | 00:01 | -0.0013 | +0.0017 | level |
| r9 | 00:08 | -0.0020 | -0.0004 | level |

The timing was the same in all nine runs, to the microsecond:
- `to_sim` was 0.000000 s in every logged publish of every run, including start-up.
- There were 3 substeps a frame after the first publish. The first had 7, with `frame_dt` 0.100 s:
  the warm-up frame.
- Each frame's stamp was its sim time plus the 1000 s base, exactly.
- The scan published at a frame carried the stamp from 0.100 s before it (the two frames' latency),
  in every publish.
- `/clock` stepped by 0.050 s. NDT's `pose_with_covariance` stamps sat on that grid (phase 0.000 ms,
  spread 0.000 ms). Every aib scan stamp in the log matched an NDT stamp within 1 us (735 to 742 a
  run; the log is thinned to every 10th publish after the first 100).

Against the predictions:
- *Within a run, `to_sim` and the substeps are constant after start-up:* **held**, exactly (0 s,
  3 substeps).
- *The hypothesis (the behind runs' `to_sim` one physics step from the level runs'):* **not
  tested.** No run was behind: 0 in 9, against 3 in 9 in step 2. The plan put the chance of that
  at about 3 % if the rate were unchanged. So the rate has changed. `to_sim` is the same in all
  nine (0), so nothing in these runs separates a phase.
- *The stamps downstream:* NDT matched each scan at aib's own stamp (to 1 us), and on the `/clock`
  grid. In these runs no offset is added between aib's stamp and NDT's.
- *Found, not predicted:* the level runs' along error moving is -0.0005 to -0.0020 m. Step 2's
  level runs were +0.004 to +0.005 m, so the level has moved by about 5 mm too.

**What differs from step 2 (both hypotheses, untested).**
- *The build.* Step 2 ran at main 0291abb3 (siw 4706ff9). Step 3 ran at 1ed265d7 (siw 3a948eea),
  which brings issue 161's read-back: the bridge reads the world back after the step
  (scensim a512514d; siw c6de0f0 declares it), so the order of a tick's read and step changed.
  **Hypothesis H-a:** the behind mode came from the read before the step, and 161 removed it. The
  aib commits since step 2 add only log lines behind a switch.
- *The load.* Step 2 ran non-timing with the host loaded (load averages 44 to 48 at r8 and r9).
  Step 3 ran under the quiet rule. **Hypothesis H-b:** the mode needs load at start-up (step 2's
  proxies did not support it, but they were proxies). Step 3 did not record the load average at
  each start, an omission.

The bridge's tick, from the gap trace's frame wall times, was p50 51.9 to 53.9 ms, p95 62.3 to 94.4
ms and max 2.2 to 4.8 s, over the 50 ms budget in 5484 to 6444 frames. This is a different source
from step 2's tick figures, so the two are not compared here.

**Next (to plan with 133):** separate H-a from H-b with the same nine-run design. Either main
0291abb3 under the quiet rule (H-a predicts behind runs return; H-b predicts none), or 1ed265d7
under step 2's load (H-b predicts behind runs return; H-a predicts none). Record the load average
at each start.

## Step 4's plan, H-a first (written 2026-11-26, before any change or run; 133's choice)

**The runs.** Nine smooth haruna_down runs as in steps 2 and 3, at scensim main **0291abb3**
(scensim_isaac_world 4706ff9, step 2's build), under the quiet rule as in step 3. aib is the
local branch `issue-172-age` at 86a9207, as in step 3: on step 2's aib 3b69851 it adds only the
timing lines behind the same switch, so that step 4's timing reads like step 3's. ws-c6e3 is
rebuilt at 0291abb3 with that aib, and the testbench `isaac_i172_smooth` as in step 3 (the
record with `/clock`). The load average is recorded at each start (`/proc/loadavg`, logged by
the runner just before the run). The quiet rule is the condition that can be reproduced. Step 2's
load (around 45) cannot be.

**Predictions (before any run).**
- *H-a (issue 161's read-back after the step removed the behind mode):* the behind runs come back
  at about step 2's rate, about 3 in 9, along about -0.086 m. H-a holds if at least one run is
  behind. With 3 in 9 as the rate, none in nine has a chance of about 3 %.
- *H-b (step 2's load made the mode):* no behind run in nine under the quiet rule.
- *The timing:* in level runs, `to_sim` and the substeps as in step 3 (0 s, 3 a frame). If a run
  is behind, its timing lines are read against the level runs' for the first difference, if any,
  and if there is none the offset is downstream of aib's stamp.
- *If none come back,* the next set is 1ed265d7 under load, with a load recipe agreed with 133
  first.

## Step 4's result (2026-11-26, 118, GPU0, 01:25:59 to 02:45:10; the quiet rule, codec told)

Nine smooth haruna_down runs at scensim main 0291abb3 (scensim_isaac_world 4706ff9, step 2's build)
with aib 86a9207, all accepted (rc 0, provenance, the aib sidecar's head, the timing lines). The
GPU log shows no foreign process on GPU0 during any run; codec 118's job ran on GPU1 from about
01:50 (the first-minute load at r3's start, 35.57, is its start).

| run | start | 1-min load at the start | NDT along (moving) | mode |
|---|---|---|---|---|
| r1 | 01:36 | 0.04 | -0.0018 | level |
| r2 | 01:43 | 3.89 | -0.0013 | level |
| r3 | 01:51 | 35.57 | -0.0007 | level |
| r4 | 01:58 | 4.21 | -0.0019 | level |
| r5 | 02:06 | 7.25 | -0.0011 | level |
| r6 | 02:13 | 9.83 | -0.0007 | level |
| r7 | 02:21 | 8.15 | -0.0016 | level |
| r8 | 02:29 | 8.38 | -0.0020 | level |
| r9 | 02:36 | 9.53 | -0.0009 | level |

The timing was as in step 3 in every run: `to_sim` 0, 3 substeps a frame, NDT's stamps equal to
aib's to 1 us, on `/clock`'s grid.

Against the predictions:
- *H-a (issue 161's read-back removed the behind mode):* **FAILED.** No run was behind at step 2's
  own build: 0 in 9, against step 2's 3 in 9 at the same build.
- *H-b (step 2's load made the mode):* its prediction for this set, none behind, held. That is
  consistent with H-b, not a test of it. r3, level at a start load of 35.6, is one run against a
  load-at-start version of H-b, not a refutation.

**Every difference between step 2 and steps 3 and 4 (written before proposing a set; 133).**
Read from the runs' own records (`host.json`, `result.json`), the runners, and the host.

*The same in step 2 and step 4:* the build (0291abb3, siw 4706ff9). The host (118, up since
2026-10-15, so no reboot and the same NVIDIA driver, 615.71.09). GPU0 (RTX 4090, bus 01:00.0).
The testbench's environment file (`tb-i172/env.bash`, unchanged since 2026-11-25 19:04, before
step 2's r1), so the same Isaac Sim install. The scenario file (`haruna_down.xosc`, unchanged
since 19:04). The map (the same link to `c6b-haruna/none/haruna`). No CARLA is involved: these are
Isaac runs, and no CARLA instance ran. GPU0 held no process at any run's start in either step
(step 2's "gpu at start" lines are empty).

*Different:*
1. **aib:** step 2 ran 3b69851 (the render age only). Steps 3 and 4 ran 86a9207, which adds the
   per-publish timing line (about 840 INFO lines a run into the world server's console).
2. **The record:** step 2's r1 to r3 had C6e2's topics, and r4 to r9 added the start-up topics.
   Steps 3 and 4 also record `/clock`, so the recorder subscribes to it in the ego domain.
3. **The testbench install** was rebuilt for each step. Its content is otherwise the same.
4. **The host's CPU contention during the run.** From `result.json`'s clock lag (the sim behind
   the wall, p50): step 2 18 to 108 s, steps 3 and 4 15 to 37 s. The 1-min load at the start
   (`host.json`): step 2 14 to 53, step 4 0.6 to 23, step 3 3 to 28. The bridge's tick p95:
   step 2 70 to 156 ms, step 4 63 to 277 ms.
5. **Who else was on the host:** another user's cargo builds (`/home/runner`) at step 2's
   start loads of about 45 to 50. codec 118's GPU1 job in step 4 (r3 to r9).
6. **My own activity:** a 25 s build of mine ran in the middle of step 2's r7, which was behind.
   Nothing of mine ran during steps 3 and 4.
7. **The quiet rule's own effects:** a 10-minute wait before r1, then runs back to back (about
   7.5 min apart, against step 2's 8 to 10). No change to GPU0's occupancy, which was empty at
   every start in both steps.

*Found, not predicted (from 2 to 4 above; a correlation, not a test):* every behind run had a
clock lag p50 of at least 64.8 s (r2 64.8, r7 107.5, r9 97.0). Of the 24 level runs across the
three steps, one reached that (step 2's r8, 85.9 s, at a start load of 53). The rest were at
53.2 s or less. So the behind mode went with a slow run, in-run contention, more than with the
load at the start.

## Step 5's plan, contention (written 2026-11-26, before any run; 133's OK, the user's go)

**The runs.** Step 4's configuration exactly (scensim main 0291abb3, siw 4706ff9, aib 86a9207,
`isaac_i172_smooth` with `/clock` in the record, GPU0 under the quiet rule), with one change: a
CPU load for each run's length. stress-ng is not installed on 118, and installing it needs sudo,
so the load is `step5/burn.py` instead (133's OK). It runs N worker processes, each multiplying
256x256 float64 matrices in a loop with single-threaded BLAS (comm `python3`, cmdline
`python3 .../i172/step5/burn.py N`). It is started by setsid 30 s before each run, in a process
group of its own, with its pids recorded. It is killed by that group when the run ends, and
verified gone by its recorded pids and by an empty group (`ps -o pid= -g`), never by a pattern.
Before each run, any other user's job over about 4 cores (`ps -eo user,pcpu`) is waited out in
60 s steps for up to 20 minutes, else the run is skipped and recorded (133).

**Calibration.** A first run, c1, at 24 workers. If its clock lag p50 is outside step 2's behind
range, 65 to 110 s, there is one adjustment (32 workers if under, 16 if over) and a run c2. If
that also misses, the set stops and is reported, with no more tuning (133). Then r1 to r9 at the
calibrated count. Each run's clock lag p50 and worker count are recorded.

**Predictions (before any run).**
- *H-b as contention (the behind mode needs CPU contention during the run):* behind runs return,
  about 3 in 9 as in step 2, along about -0.09 m, and they have clock lag p50 of 65 s or more.
- *If none return,* contention alone does not make the mode. The next set reverts step 2's other
  differences (aib 3b69851, the record without `/clock`) under the quiet rule, with its plan to
  133 first.
- *The timing* (`to_sim`, the substeps, NDT's stamps against aib's) in any behind run is read
  against the level runs' for the first difference.

## Step 5's result (2026-11-26, 118, GPU0, 03:29:55 to 06:11:27; the quiet rule on GPU0, codec told)

The calibration run c1 at 24 workers had a clock lag p50 of 88.4 s, inside 65 to 110 s, so there
was no adjustment. Then r1 to r9 at 24 workers. All ten runs were accepted (rc 0, provenance at
0291abb3 with siw 4706ff9, the aib sidecar at 86a9207, the timing lines). The GPU log shows no
foreign process on GPU0 during any run (the last sighting was 03:49:48, codec's last fit, before
c1). No other user's job was over 4 cores at any start, so no run waited or was skipped. After
each run the burner's recorded pids were gone and its group was empty.

| run | start | load at the start (1 min) | clock lag p50 | NDT along (moving) | mode |
|---|---|---|---|---|---|
| c1 | 03:59 | 41.2 | 88.4 s | -0.0004 | level |
| r1 | 04:12 | 57.4 | 107.8 s | -0.0906 | **behind** |
| r2 | 04:24 | 44.2 | 85.4 s | -0.0009 | level |
| r3 | 04:34 | 59.4 | 72.9 s | -0.0004 | level |
| r4 | 04:45 | 69.6 | 83.2 s | -0.0017 | level |
| r5 | 04:56 | 54.8 | 277.9 s | -0.0951 | **behind** |
| r6 | 05:21 | 88.1 | 210.5 s | -0.0950 | **behind** |
| r7 | 05:37 | 36.0 | 138.6 s | -0.0920 | **behind** |
| r8 | 05:48 | 58.1 | 92.3 s | -0.0917 | **behind** |
| r9 | 05:59 | 51.8 | 91.7 s | -0.0919 | **behind** |

(The loads are host.json's at the stack's start, which include the burner's 24 workers.)

The timing was as in steps 3 and 4 in every run, behind or level: `to_sim` 0, 3 substeps a frame,
NDT's stamps equal to aib's to 1 us, on `/clock`'s grid. In r5 and r6 fewer of aib's logged stamps
had an NDT pose (545 and 690 against 737 to 744): NDT dropped scans under the load.

Against the predictions:
- *H-b as contention:* **held.** Behind runs returned, 6 of the 9 (step 2: 3 in 9; steps 3 and 4,
  quiet: 0 in 18), at along -0.090 to -0.095 m.
- *The behind runs have a clock lag p50 of 65 s or more:* **held** (91.7 to 277.9 s). But it does
  not separate the modes in this set: the level runs were at 72.9 to 88.4 s, and r8 and r9 were
  behind at 92.3 and 91.7 s. Contention brings the mode within reach. The run's lag does not
  decide it.
- *The timing (`to_sim`, the substeps, NDT's stamps against aib's):* no difference between the
  behind and the level runs. **The offset is downstream of the scan's stamp.** aib and the stamps
  NDT sees are the same in both modes.

**Found, not predicted (labelled; a pattern in this set only).** As in step 2, every run's NDT
along error standing still was within 1 cm of 0. The behind offset appeared from the first moving
NDT output (first_along -0.084 to -0.087 in the six behind runs, against -0.001 to +0.003 in the
four level ones) and stayed. In this set the initial pose's along error went with the mode: the
behind runs' initial pose was off by +0.008 to +0.043 m and the level runs' by -0.074 to +0.003 m.
Step 2 does not show the same (behind r7 +0.136, level r8 -0.128, behind r9 -0.018), so this is
not claimed.

**Hypothesis H-d (untested; for the next plan).** The mode is set downstream of the scan's stamp,
where NDT and the EKF meet at the first motion. Under contention, NDT's initial guess (the EKF's
pose for the scan's stamp) is late or extrapolated when the car starts. NDT then settles in a
neighbouring minimum about 0.09 m behind, and the EKF, fed by it, holds it. The test reads NDT's
initial guess and its result at the first moving scans, against the truth, in this set's records
(`pose_with_covariance`, the EKF's pose, `/initialpose3d`, all recorded), before any new run.

## Step 6's plan, H-d offline (written 2026-11-26, before any reading; for 133)

No runs. Read from the records already taken: step 5's ten runs (6 behind, 4 level) and step 2's
r3 to r9 (2 behind, 5 level; r1 and r2 recorded no NDT pose). Each has NDT's
`pose_with_covariance`, the EKF's pose (`/localization/pose_twist_fusion_filter/pose`),
`/localization/kinematic_state`, `/initialpose3d`, and the truth trace (ego_trace).

**The readings.**
1. *The initial guess at the first moving scans.* NDT's initial guess for a scan is the EKF's pose
   for the scan's stamp. For each NDT output in the 3 s after the car starts to move (truth speed
   over 0.2 m/s):
   - the EKF's pose interpolated at the scan's stamp, against the truth at that stamp (the guess's
     along error);
   - NDT's result against the truth (its along error);
   - the guess's staleness: the scan's stamp less the newest EKF pose stamp the record had
     received before NDT's output was received (bag receive time), as near as the record allows.
2. *Offset against speed, the whole run.* In each behind run, NDT's along error against the
   truth's speed, fitted as along = a + b v. A time offset gives a near 0 and b near -0.019 s. A
   position offset gives b near 0 and a near -0.09 m.
3. *The size of the step.* The truth's speed at the first moving scan whose result is behind,
   times the scan period (0.050 s), against the offset. The ND voxel resolution (2.0 m, the
   profile's `ndt_scan_matcher` resolution) for comparison.

**Predictions (before any reading).**
- *H-d:* in the behind runs, the first moving scans' guess is stale by at least one scan period
  (50 ms or more) and its along error is -0.05 m or worse. In the level runs it is fresher (under
  50 ms) and within -0.03 m. NDT's result is behind from that scan on.
- *The falsifier (133):* if the level runs show the same initial-guess error and staleness at the
  first moving scans as the behind runs, H-d **fails**.
- *Which step is predicted:* **the scan-period step at start speed**, not a voxel. The offset
  (0.085 to 0.095 m) is 4 to 5 % of the 2.0 m voxel, so no voxel step is predicted. One scan
  period at the speed of the first stale guess is predicted: 0.09 m at 1.8 m/s. If the readings
  put that speed at 1.5 to 2.2 m/s, the step matches.
- *Reading 2:* H-d, a neighbouring minimum that NDT and the EKF then hold, predicts a **position**
  offset: b within 0.005 s of 0, and a within 0.02 m of the run's along median. If instead b is
  near -0.019 s and a near 0, the offset is a time offset (step 2's first reading). H-d's "held
  minimum" then fails, and the mode is a lag held in the EKF.

## Step 6's result (2026-11-26, offline; after the predictions above)

Read from step 5's ten runs and step 2's r3 to r9: 17 runs, 8 behind and 9 level (scripts
`hd.py`, `hd_bins.py`, `hd_tau.py`). NDT's own initial guess is not in any record (no
ndt_scan_matcher debug topic was recorded), so the guess is the EKF's pose interpolated at the
scan's stamp, by header stamps.

**(2) Offset against speed (first, as 133 asked).** A straight-line fit over the whole run is
dominated by the cruise at 4.2 m/s and by about 4 cm of scatter around it (curves, the
acceleration and the braking). So the offset is read as a time, tau = -along / v, per speed band:

| | tau at 4.1 to 4.4 m/s | along there | tau at 1.5 to 2.5 m/s |
|---|---|---|---|
| behind runs (8) | 23.8 to 25.2 ms | -0.099 to -0.105 m | 23.8 to 30.5 ms in 5; about 0 in 3 (r7, r8 and step 2's r9: their low-speed outputs come before the mode sets) |
| level runs (9) | 1.7 to 2.2 ms | -0.007 to -0.009 m | -18.5 to +11.7 ms (scatter) |

By speed and phase in the behind runs, the along error grows with speed: about -0.03 m at 0.5
to 1.5 m/s, -0.05 m at 1.5 to 2.5 m/s, and -0.09 to -0.10 m at cruise.
- *H-d's position offset (b about 0, a about -0.09 m):* **FAILED.** The behind mode is a **time
  offset**, about 22 ms more than the level mode's 2 ms. NDT's pose is the car's position about
  24 ms before the scan's stamp.
- *The predicted step (one scan period at start speed):* **FAILED.** The offset scales with speed,
  and the extra delay is about 22 ms, not 50 ms. The first output behind by 0.05 m came at 0.40 to
  2.32 m/s in the behind runs, and some level runs also cross -0.05 m once in their noise. The
  voxel (2.0 m) was not predicted and is not seen.

**(1) The initial guess at the first moving scans (0.2 to 0.6 m/s).** The guess's along error was
0.0 to -2.4 cm in the behind runs and -0.4 to -2.2 cm in the level runs. NDT's results scattered
by about +/-5 cm in both, with no early divergence.
- *133's falsifier (level runs show the same guess error at the first moving scans):* **met, so
  H-d FAILED.**
- *Staleness (secondary, receive time; confounded by the recorder, which shares the CPU):* in all
  17 runs, behind and level alike, the EKF poses the bag had received before each of NDT's outputs
  were stamped 150 ms after the scan's stamp. No stale guess was found in either mode. NDT's own
  initial guess is not recorded, so its real input is not read.

**What the readings leave (labelled).** Both modes share the stamp and its timing (steps 3 to 5),
but NDT's pose is the car's position about 24 ms before the stamp in one mode and about 2 ms in the
other, and the mode is set during the first motion and held. 24 ms is about half the lidar's 50 ms
revolution. **Hypothesis H-e (untested):** in the behind mode, the cloud carries the sensor's
motion across the revolution (issue 169: with Motion BVH the sensor's motion is in the cloud), so
an uncorrected cloud places NDT's match near the revolution's middle, half a revolution before its
stamp. In the level mode it does not. Which mode applies is decided at the start under contention.
The difference measured is 22 ms, not 25 ms; the hypothesis must account for that. The test needs
the raw cloud (not recorded in these runs): the two-wall probe of issue 169, or the cloud's seam
in a recorded run, behind against level.

## Step 7's plan, H-e (written 2026-11-26, before any code or run; for 133)

**What was read first.**
- *Issue 169's state:* step 1 done, step 2 planned and not started. With motion BVH on, the RTX
  lidar renders each point from the moving sensor (k 0.996), and production's `xyzirc` cloud
  carries that motion with no point times. 086 C6e2 measured localization **ahead** by 0.107 to
  0.109 m at 4.5 m/s with BVH on: 24 ms, half a revolution.
- *The runs of steps 2 to 5 set no motion BVH:* no `raytracingMotion` setting in their world
  server's source or console, so it is Kit's default. C6e2 had to turn it on with Kit
  arguments. *133's latch candidates on the corrector do not apply here:* the Model 3's kit
  runs no distortion corrector (`use_distortion_corrector` false and used nowhere, as 169's
  step 2 plan found). aib's own `motion_distort` is off for `xyzirc`. No step in these runs
  removes or adds in-revolution motion after the render.
- *The behind mode is the mirror of C6e2's BVH offset:* the same size (24 ms, about 0.1 m at
  cruise), the opposite sign. So **H-e is restated before any run.** It is not motion BVH. It
  is the revolution's **stitch**. The annotator hands "the last finished revolution" (aib's
  `ScanGate`). At 20 Hz rotation and 20 Hz frames, a revolution that is not aligned with the
  frames is assembled from two frames' renders, each from that frame's single pose (BVH off). So
  part of the cloud is a frame (50 ms) older than the rest. NDT on that cloud lands between the
  two poses, behind by the older part's share of 50 ms. The share is set by the phase between
  the lidar's revolution start and the frame boundaries. That phase is fixed when the sensor
  starts, so it holds for the whole run, which is the latch. A starved start-up (dropped or
  stretched first frames) can set a different phase.
- *22 against 25 ms (133).* The behind runs' absolute tau is 23.8 to 25.2 ms, which is half a
  revolution within 1.2 ms. The level runs' 1.7 to 2.2 ms is a lag present in both modes. If
  the two simply added, behind would be about 27 ms, and it is not. So the 22 ms difference is
  not claimed as half a revolution. What is claimed is the behind runs' own 24 ms against a
  share of 0.5. A stitch at a share s gives s x 50 ms, so the share is a measured quantity, not
  an assumption.

**The code (aib's local branch `issue-172-age`, behind the same switch; the diff to 133 before
any run).**
1. The timing line gains the annotator's point times for the published revolution: their min
   and max, as offsets from the clock; their span; and the azimuth of the earliest and the latest
   point.
2. Every 200th published revolution, the cloud and its point times go to an `.npz` under the
   run's log dir (about 2 MB each; about 40 a run), for the sector test. The raw cloud is not
   added to the bag, which would be about 15 GB a run.

**The runs.** Nine smooth haruna_down runs as in step 5 (0291abb3, siw 4706ff9, the branch's aib,
burn.py at 24 workers, the quiet rule on GPU0, the other-user check, the load at each start),
so that behind runs are likely.

**Readings.**
- (a) Each run's mode, as before.
- (b) The phase: the point times' min against the frame grid (the clock in 50 ms steps), and the
  span. Constant within a run, if it is a latch.
- (c) The sector test on the saved clouds. Split each revolution into 16 azimuth sectors by
  firing time. Register each sector against the Haruna map at the truth pose for the
  revolution's stamp. Read each sector's along offset against its firing time.

**Predictions (before any code or run).**
- *H-e (the stitch):* in level runs the revolution lies in one frame (its point times' min on the
  frame grid, within 2 ms). The sector offsets are flat (within 0.02 m) across the revolution.
  In behind runs the point times cross a frame boundary, and the sector offsets show a **step** of
  about v x 50 ms (0.21 m at cruise) between the older sectors and the newer ones. The older
  share s matches tau / 50 ms (about 0.48 at 24 ms) within 0.1.
- *Against H-e:* a **ramp** across the sectors (k about 1, as in 169's case C) instead of a step
  means the cloud carries continuous motion (motion BVH or alike), not a stitch. A flat profile
  in the behind runs means the offset is not in the cloud, and H-e fails.
- *The latch:* the phase in (b) is constant within every run. It differs between the behind
  and the level runs. It is set by the first revolutions after the stack starts.

**Amended before the runs (2026-11-26, 133's review of the diff; not after a result).** The code is
aib **b354ab9** (local branch `issue-172-age`: 5a05a11 and 133's review on it).
- The revolution line is written after the ScanGate's decision and says whether the revolution was
  published or dropped. The stitch is read from published revolutions only.
- The annotator's per-point `tickId` names the render ticks a revolution is made of. Each line
  lists each tick's point count and time span. A stitch shows as two ticks. The annotator's
  `transform` is one per revolution, so the two render poses come from the ticks' times on aib's
  track.
- Every revolution is logged for the first 20, marked "(start-up)" (the latch). The time
  conversion and the rest run only on revolutions that log or dump. Each line carries the probe's
  own time (probe_us). Measured here at 126,600 points: 1.6 ms a logged revolution, 0.9 us a
  skipped one.
- The dumps are uncompressed (6.3 ms each, 4.1 MB, against 177 ms compressed). They are every
  200th revolution from the 1200th (60 s), so the start-up carries no dump's stall. They go to
  `/mnt/renegade/aeon/isaac-ex/i172/step7/dump_<run>` (NVMe), since the run's own log dir does not
  exist when the world server starts.
- The probe's per-call time from one run is reported with the result.

## Step 7's runs: stopped at calibration (2026-11-26, 118, GPU0, 10:27:04 to 11:03:28)

The set stopped under 133's rule after c1 and c2. The clock lag p50 was 150.7 s at 24 workers
(c1) and 123.4 s at 16 workers (c2), so both missed 65 to 110 s. The burner was verified gone
after each run, and no foreign process was on GPU0.

**The probe FAILED its own requirement (no added load). Mine, recorded as FAILED.** The
annotator's per-point `tickId` is not a render frame. It is the lidar's firing tick: 1024 a
revolution, 0 to 1023, about 49 us each. The per-tick summary looped over 1024 masks of about
125,000 points. probe_us p50 was 179,745 us in c1 and 101,630 us in c2 (max 393 ms), on each of
the first 100 revolutions and every 10th after, with log lines of about 28 KB. The benchmark
before the runs had used a synthetic two-tick revolution (1.6 ms), and tickId's real
cardinality was not checked. **So c1's and c2's lags are inflated by the probe, and they are not
comparable with step 5's (88.4 s at 24 workers).** The dumps cost 3.6 to 11.3 ms each, as
expected.

**What the two runs still show.**
- c1 was behind (NDT along -0.0914 m) and c2 level (-0.0004 m).
- In both, every logged revolution's point times start exactly on the 50 ms grid (phase 0), span
  50.000 ms, run from azimuth 0.00 to 0.35, and hold ticks 0 to 1023. The start-up revolutions
  have the same form in the behind and the level run. *H-e's prediction for the point times
  (behind: they cross a frame boundary): FAILED, as far as these times show.* By issue 169's
  step 1, though, the annotator assigns these times per tick on the read frame's clock. They
  are not taken from the render, so they may not show a stitch in the geometry. The sector test
  on the dumps is the geometric reading.
- dump_c1 (behind) and dump_c2 (level) hold the revolutions from the 1200th on: about 124,000
  points each in the sensor frame, with the per-point time, azimuth and tick, and the render
  transform.
