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
