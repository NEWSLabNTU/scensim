# 116: haruna_down's localization p95 rose about 0.065 m between main 8965a06a and f98f1cd1, below C5

**Status:** closed, not reproduced (2026-11-23): the premise came from a mixed overlay.
**Severity:** none (no shift); Haruna's margin to the 0.2 m rule is thin on either main. **Found:** 2026-11-23, scensim 118, in roadmap 086 C5's
exit pairing.

## What was seen

haruna_down on the published Haruna map (dataset tag b12857ee, issue 072's 140 tiles), Autoware's
Model 3 on Isaac, 118's GPU0, judged by the courses project's `pose_error` (the localization's
horizontal error against the truth, after the first 10 s):

| run | scensim main | pose error p95 | max | NVTL p05 | simulated |
|---|---|---|---|---|---|
| B, 2026-11-23T12-23-52 | f98f1cd1 | 0.178 m | 0.2025 m | 3.12 | 383.5 s |
| A, 2026-11-23T12-31-00 | 8965a06a | 0.115 m | 0.155 m | 3.12 | 385.5 s |
| B2, 2026-11-23T12-39-00 | f98f1cd1 | 0.183 m | 0.2024 m | 3.12 | 406.6 s |
| A2, 2026-11-23T12-46-32 | 8965a06a | 0.114 m | 0.151 m | 3.12 | 383.5 s |

All four passed (0 contacts). By the rule written before the repeats (086, "C5's exit
pairing"), a gap of about 0.05 m or more with B above A in both pairs is a real shift. It is
0.063 and 0.069 m. No C5 code acts on this map (no `road_detail.yaml` in its map directory, its
maps the dataset's), so the cause is below C5.

**An oddity, noted:** B2 simulated 406.6 s, the other three about 384 s, on the same scenario.

## What differs below C5 (A to B)

| component | A | B | commits |
|---|---|---|---|
| sim_vehicle_ecu | ef6bfd8 | 99505b0 | a248958 (issue 107: no Autoware command yet is the default request), 99505b0 (issue 106: regen slip control releases at 0.15, below ABS) |
| sim_vehicle_spec | 21bf3dc | 9ceb8cb | 9ceb8cb (issue 106: `powertrain.regen_slip_control`, the Model 3's release 0.15) |
| autoware_isaac_bridge | 401bd27 | 3cd2b7d | 5e3d8cd and 23ef5fb (deps bumps, 23ef5fb issue 106's), fc0edb0 (steptest only), 3cd2b7d (issue 104: ground_truth's pose-derived rate) |
| autoware_sim_vehicle | 17f4c9c | 2b4a665 | 2b4a665 (deps: sim_vehicle_spec 9ceb8cb, issue 106) |

The others that differ (autoware_carla_bridge, scensim_carla_world, `src/scensim`'s CARLA root
check, scensim_batch) are not in an Isaac run's path. **Prime suspect, named before any run:**
issue 106's regen slip release (ecu 99505b0, spec 9ceb8cb, reaching the Isaac car through aib
23ef5fb's deps), since it changes how the car brakes. Then issue 107's default request
(ecu a248958).

## The bisection (written before its runs)

First the component, then the commit. From B (a full build of f98f1cd1 on 118's root disk,
`/var/tmp/aeon/bis`; `/mnt/renegade` is 99 % full), one component at a time back to A's pin,
everywhere the Isaac run reads it (`src/<component>` and the `deps/` copies under aib and
autoware_sim_vehicle), the rest left at B:

1. aib at 401bd27 (its `deps/` kept at B's ecu and spec, so only aib's own code moves);
2. sim_vehicle_ecu at ef6bfd8;
3. sim_vehicle_spec at 21bf3dc (with autoware_sim_vehicle at 17f4c9c, whose only change is that
   bump).

Each step runs haruna_down twice on GPU0. A step **explains** the shift when both its runs come
back toward A: p95 at least 0.05 m under B's (0.178 and 0.183 m), that is 0.13 m or less. Then
`git bisect` inside that component's range, two runs a step, by the same threshold. A step that
moves neither run is not the cause; one run each side of the threshold is reported and rerun.
If no single component's step comes back to 0.13 m or less, the next step is pairs of
components, an interaction (for example sim_vehicle_ecu and sim_vehicle_spec together, issue
106 having changed both), not more runs of the single steps (133, written before the results).

## Closed: not reproduced; the premise came from a mixed overlay

The four runs above went through one testbench workspace built with B's install sourced, so
its `setup.bash` chained `/mnt/renegade/aeon/gate-c5c/install` (B) over whatever was sourced
before it (CLAUDE.md's overlay-order trap). Every run's `result.json` records scensim f98f1cd1,
the two "A" runs included: they were a mix of A's and B's paths, not A. The bisection's runs
went through the same workspace and ran B's code throughout; it was stopped during its second
step (sim_vehicle_ecu) and none of its runs is a result.

The clean pairing (roadmap 086, "C5's exit pairing"): a testbench workspace per side built
against that side's install only, each run refused unless the live bridge and world server are
under its own install and `result.json` names its commit; three runs per side, alternating, its
rule written before the runs. Every run passed the check and its scenario:

| run | scensim | pose error p95 | max |
|---|---|---|---|
| cB1, 2026-11-23T13-27-25 | f98f1cd1 | 0.181 m | 0.203 m |
| cA1, 2026-11-23T13-34-42 | 8965a06a | 0.182 m | 0.202 m |
| cB2, 2026-11-23T13-41-58 | f98f1cd1 | 0.126 m | 0.155 m |
| cA2, 2026-11-23T13-49-14 | 8965a06a | 0.184 m | 0.203 m |
| cB3, 2026-11-23T13-56-37 | f98f1cd1 | 0.180 m | 0.201 m |
| cA3, 2026-11-23T14-03-53 | 8965a06a | 0.185 m | 0.201 m |

B's mean p95 0.162 m, A's 0.184 m: B is not above A, so there is no shift. The runs fall in two
groups, about 0.18 m and about 0.12 m, on either main; the mixed "A" runs were two of the lower.
The lesson, for any paired run: check what the live processes loaded (`/proc/<pid>/exe` and
command line) and what `result.json` records, per run, rather than what the script sourced.
