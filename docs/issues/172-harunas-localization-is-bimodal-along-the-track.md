# 172: on Isaac's haruna_down, localization runs either level with the car or 0.086 m behind it, per run

**Status:** open; mine after 168 (133, 2026-11-25). **Severity:** to be shown. It is the cause
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
