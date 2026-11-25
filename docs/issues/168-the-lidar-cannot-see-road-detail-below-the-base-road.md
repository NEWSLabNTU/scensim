# 168: on road-layer worlds the lidar cannot see road detail below the base road

**Status:** fixed: siw 4706ff9 (siw main), checked static, its NDT A/B passed (option 2 stands); landed in scensim main 0291abb3 (2026-11-25, gated at that commit). **Severity:** high
for any sensor result on a road-detail world: the lidar (and the camera) see no pothole, no rut
and only the upper half of the roughness. **Found:** 2026-11-25, scensim 118, 086 C6e1
(predicted from the code before the run; numbered by 133).

## What happens

The road layer (066 R3) adds the detail as its own render mesh, `road_layer.MeshStream`: per
tile within 40 m of a car, the base road plus the detail (`Detail.surface_tile`), no collision.
The world's own road (the course's `world.usdc`, `/World/env/Road`) stays drawn beneath it.
Only the detail's collision copy is hidden (`rock_layer`, `CreateVisibilityAttr(invisible)`).
So a ray meets whichever surface is higher: max(base, base + detail).

In 086 C6e1 the lidar read the cleats and the washboard (above the base) to within 0.1 mm of
the detail. Every one of its 540 returns over the 8 cm pothole at 9 m was at the base road: dz
to the base was -36.22 mm (issue 167's offset alone), and dz to the pothole's floor was
+43.78 mm.

Below the base road, and so not seen:

- potholes (all of their depth);
- ruts (their 3 cm grooves; the centre windrow above the base is seen);
- the lower half of the ISO 8608 roughness, which is zero-mean, so the lidar sees the road's
  roughness clipped at the base;
- a water bar's ditch, if one is ever below the base (bars today are above it).

C6d's Haruna had all three of the first. Its "pothole detection range: not measurable" and its
"roughness did not reach localization" were measured on a cloud that never held them.

## Options (for 133; costs predicted, not measured)

1. **Hide the world's road where the detail mesh covers it, and draw the detail to the
   sensors' range.** Set `/World/env/Road`'s visibility to invisible when a road layer loads.
   Visibility does not change collision: the detail's collision tiles are invisible and
   collide. Raise `MeshStream`'s reach to the lidar's useful range (the OS1's 170 m far range;
   haruna_down's camera and lidar need about 120 m).
   - *Predicted:* 3 to 4 times the tiles drawn (40 m to 120 m reach, the area by the square
     less the corridor's width), each about 40 ms to make, streamed as now. The tick p50 rises
     by about 1 ms at 16 km/h and more at speed. Beyond the reach the road is not drawn.
2. **Lower the world's road under the detail.** At load, move `/World/env/Road`'s render 0.15 m
   down (deeper than any pothole the generator makes, 8 cm, with a margin), so the detail
   mesh is always above it where it exists.
   - *Predicted:* no extra cost. Beyond the 40 m reach the road is seen 0.15 m low: a step at
     the reach's edge in the cloud and in the camera.
3. **Cut the detail into the base road's own mesh.** The course builder writes `world.usdc`'s
   road from the same samples with the detail in it, so no second mesh is needed.
   - *Predicted:* exact at every range with no render cost per frame. The detail is baked in, so
     a scenario's road_detail change needs a rebuilt world, and a 0.05 m grid over a 2 km road
     is a large mesh (about 6.4 million vertices for 2 km of an 8 m carriageway at 0.05 m, before any decimation).

My first recommendation was option 1, with its reach and cost measured first (C6e2's method).
It is amended below, before any code.

## What else reads the base road's render (133's check, 2026-11-25, before any code)

Option 1 hides the world's road from every renderer, not only from the lidar. Beyond
`MeshStream`'s reach nothing draws the road. The course's terrain is then what is seen there, 0.30
m below the road on a fixture course (`terrain_below`), and the world's own terrain on Haruna.
These read the render beyond 120 m:

- **The lidar itself.** The Model 3 rig gives it `range: 200.0` m (`tesla_model3.rig.yaml`'s
  profile), and the OS1 profile's far range is 170 m. Its road returns from 120 to 200 m would
  come from the terrain. NDT uses them, and the ground filter would see a drop at 120 m.
- **The ego's camera.** `camera6` is `enabled: false` in the rig, so no Autoware run so far has
  had one. Traffic light recognition names camera6 but runs fusion only by default
  (`traffic_light_fusion_only: true`). Turned on, its clipping range is 0.1 to 1000 m
  (`aib.isaac.sensors.Camera`): it would see the road end at the reach.
- **The viewport and recordings.** The world server's `--display`/`--follow` viewport (the
  demos' videos) looks along the road to the horizon. Option 1 would show the road ending 120 m
  ahead.
- **rviz** draws the topics (the clouds, the map's own cloud and lanelets), not Isaac's render.
  It sees the lidar's effect only.

So option 1 as written breaks the demos' view and the lidar's far returns. **Amended
recommendation (before any code):** option 2 with option 1's mesh. Keep the world's road
drawn, but lowered by 0.15 m under the corridor, and keep `MeshStream`'s 40 m reach, raised
only if C6e3 needs the detail further out. Then:

- within the reach, the detail is drawn exact (the base road is below it);
- beyond it, the road is drawn 0.15 m low;
- the demos see a road to the horizon, with a 0.15 m step at the reach's edge in the lidar and
  in a camera.

*Predicted cost:* none per frame, since only the base road's transform moves once at load. The
step at the reach is a known artefact, to be measured (the ground filter's split at 40 m, NDT's
NVTL). Option 3 (bake the detail in) removes the step and stays the target for published
worlds. Option 1 remains if 133 prefers no step and accepts the view's end.

## The fix as decided (133, 2026-11-25, before any code): option 2, per corridor

- **How far down.** At the road's load, the world's road render is lowered under each corridor
  by that corridor's own deepest detail below the base, plus a margin of 0.01 m. The depth is
  the deepest pothole, the ruts' depth, and the roughness's lowest point along the corridor,
  computed from the corridor's own features, not a flat 0.15 m. A corridor with nothing below
  the base is lowered by the margin alone. Smooth Haruna's corridor (C6b's map) has no ruts, no
  potholes and a negligible roughness, so it would drop 0.01 m. C6d's *rough_none* has 8 cm
  potholes, 3 cm ruts and class C roughness, so about 0.09 m or more.
- **How.** The world's road prims under a corridor's reach move down as one transform at load.
  Where the world's road is one mesh for several corridors, it moves by the deepest of them.
  This is a design choice to check against the worlds in use. Collision does not move: only the
  render does, as a second, render-only copy (to be settled in the code: PhysX's road must stay
  where it is).
- **The risk is NDT, not the ground filter (133).** Beyond the detail mesh's 40 m reach, every
  road return out to the lidar's 170 m comes from the lowered road. NDT matches the whole scan
  to the map's cloud, so a far field sitting low can tilt its pitch or lift its z.

## How the depth is found (133, 2026-11-25, before any code)

Measured offline first (`/mnt/renegade/aeon/isaac-ex/c6e/depth168.py`, every road sample of
every tile the corridor touches):

| map | deepest detail below the base | tiles, samples | time | features' bound |
|---|---|---|---|---|
| C6d's *rough_none* Haruna | -0.104 m | 249, 4.9 million | 40 s | 0.11 m (potholes 0.08 + ruts 0.03) |
| fixture_c6a | -0.080 m | 88, 2.1 million | 11 s | 0.08 m |

Decided (option (c), 133):

- A small CLI samples a corridor's deepest detail below the base once, and writes it into the
  corridor's entry in `road_detail.yaml` as `base_drop: {depth: <m>, sha256: <hex>}`. The hash
  covers the corridor's own entry in the file (every key but `base_drop`, canonical JSON) and
  the bytes of its stations file, the record.
- The world server drops the world's road render by the deepest corridor's depth plus 0.01 m.
- **Staleness (133).** The world server recomputes the hash at load. On a mismatch, or with no
  `base_drop`, it falls back to the features' bound: the deepest pothole, plus the ruts'
  depth, plus 3 sd of the roughness from its PSD over the band. It logs a WARN naming the CLI
  to rerun. A stale exact value is worse than a safe bound.
- **Where the files live (133).** A `road_detail.yaml` in a published dataset gets `base_drop`
  only as a dataset revision, with the user's OK through 133. Checked 2026-11-25:
  - the published `haruna-tsukuba-courses` (revisions fff4cb0b and b12857ee in this host's
    cache) has **no** `road_detail.yaml`, so it builds no road layer, has no detail mesh and is
    not affected;
  - every road-detail Haruna in use is a local copy under `/mnt/renegade/aeon/isaac-ex/`: C5d's
    rebuild (`c5d/haruna`, which itself has no `road_detail.yaml`), and C6b's and C6d's
    `c6b-haruna/{none,rocks,rough_none,rough_rocks}/haruna`;
  - the fixture courses (`c6a/fixture_c6a`, `c6c/fixture_c6c` and the rest) are local builds;
  - so every map 168's check uses carries `base_drop` directly, and nothing goes near a public
    dataset.

## Predictions for option 2's check (before any code)

The check: NDT's pitch, z and NVTL with the road lowered against not lowered, on fixture_c6a,
smooth haruna_down (C6b's package) and *rough_none* (C6d's). Smooth Haruna's drop is the margin
only, so *rough_none* is where the step is largest. Three runs a side each on the Haruna maps,
measured from `/localization/kinematic_state` against the truth trace (pitch and z) and the NVTL
judge; on fixture_c6a, the static C6e1 method plus one Autoware drive a side.

- **The geometry.** A return at range r from a road lowered by d sits at an angle d / r below
  where the map has it: 0.05 deg at 100 m for d = 0.09 m, 0.006 deg for d = 0.01 m. Most of the
  road's returns are within 40 m (C6e1: about 95 % of them within 20 m), where the detail mesh
  is exact.
- *Predictions:*
  - NDT's pitch, median against the truth, moves by less than 0.03 deg on *rough_none* and less
    than 0.01 deg on smooth;
  - NDT's z, median against the truth, moves by less than 0.01 m on both;
  - NVTL p05 moves by less than 0.05;
  - the judged horizontal pose error p95 moves by less than C6d's 2 sd of a difference
    (0.049 m).
- **The switch rule (133).** If NDT moves beyond C6d's noise on any of these, the fix becomes
  option 1, with the detail mesh's reach at the lidar's range and its cost measured. C6d's noise
  for pitch and z is not on record yet, so the "not lowered" side's three runs give it (the sd of
  the three), and the rule is applied against it.
- **"Beyond the noise", numerically (133, 2026-11-25, before any run).** It is computed per
  quantity: NDT's pitch against the truth (median a run), NDT's z against the truth (median a
  run), NVTL p05, and the horizontal pose error p95. Let s be the sd of the three "not lowered"
  runs' values, raised to a floor when it is below it. The change exceeds the noise when
  |mean(lowered) - mean(not lowered)| > 2 x s x sqrt(2/3), twice the sd of a difference of two
  means of three. The floors keep one quiet side from making any change significant:
  - pitch: 0.01 deg;
  - z: 0.005 m;
  - NVTL p05: 0.02;
  - pose error p95: 0.030 m, the 12 smooth Haruna runs' sd (C6d's rule), which gives C6d's
    0.049 m bar.

  The rule is applied per map (rough_none, smooth).
- **Eight comparisons (133, 2026-11-25, before any run).** Four quantities on two maps at about
  2 sd each give a single exceed about a one-in-four chance of being noise. So:
  - exactly one quantity exceeds, by less than 1.5 times its threshold: three more runs a side
    on that map, and the rule is applied again on the six a side before any switch, with
    sqrt(2/6) in place of sqrt(2/3) (the sd of a difference of two means of six);
  - two or more exceed, or one by 1.5 times its threshold or more: the fix switches to option
    1 directly.

## Predictions for the fix (before any code)

- C6e1 rerun: over the pothole, dz to the floor within 0.5 mm of issue 167's offset, out to the
  reach. The cleats and the washboard are unchanged.
- C6d rerun (one rough_none run): the roughness's effect on localization stays within C6d's
  noise. *Hypothesis:* NDT's 2 m voxels average a few centimetres out.

## The fix as coded (siw 4706ff9, local, 2026-11-25)

- `scensim_isaac_world/base_drop.py`: the depth per corridor (`sampled`, `bound`), the hash
  (`entry_hash`), `depths` and `drop` (stored if current, else the bound with a WARN naming the
  CLI), `render_paths`, and the CLI that writes `base_drop` into a road_detail.yaml in place,
  keeping its comments.
  - The bound counts the section's fall where the world's road does not carry it
    (`section_in_base: false`): there the detail mesh draws the crown and the shoulders, and
    the world's road is level. Found by a test, before any run.
- `road_layer.BaseRender`: each prim to lower is hidden (its collision stays) and drawn again
  under `/World/RoadBaseRender` as a reference to the layer that defines it, `drop` m down, with
  its collision off. It is made in world.py's `_load_road` beside `MeshStream`, and removed
  with the road's tiles.
- Which prims: road_detail.yaml's `base_render` (a list; `[]` lowers nothing, which the A/B's
  "off" maps use). Otherwise, the world's ground prims named `Road`: the terrain and the lane
  lines stay where they are.
- The tests: `test/test_base_drop.py`, 7 tests. siw's suite in the same environment as main
  gives the same 7 environment-only import errors as main, with 382 tests run against 375.
- The CLI on the maps: smooth Haruna 0.000 m (bound 0.000), *rough_none* 0.104 m (bound
  0.137), fixture_c6a 0.080 m (bound 0.080).

## The fix's static check (2026-11-25, 10:13 to 10:17, GPU0; non-timing)

C6e1's six stops on fixture_c6a with the world's road drawn 0.090 m lower (`base_drop` written
into the fixture's local `course/road_detail.yaml`, stored and current; `c6e1_lidar.py
--base-render`; aib bb2283f, so issue 167's offset is gone). Output: `c6e1-fix168/`.

- **The prediction held.** Over the pothole 260 returns at 9.6 m, every one at its floor:
  dz to the detail 0.0 mm (median and p95), to the base -80.0 mm. Before the fix all 540
  returns there were at the base road. Fewer returns land in the hole than on the road that
  was there, because its near edge hides the near part of the floor at a grazing angle.
- The cleats, the washboard and the flat road are unchanged: dz 0.0 mm median in every band.

## The NDT A/B as built (before any run)

- **Maps:** four hard-linked copies under `/mnt/renegade/aeon/isaac-ex/c6e/maps/`, each with
  its own road_detail.yaml (the source maps unchanged, checked):
  - `rough_on`: C6d's *rough_none*, `base_drop` 0.104 m written, drop 0.114 m;
  - `rough_off`: the same with `base_render: []`;
  - `smooth_on`: C6b's smooth Haruna, `base_drop` 0.000 m, drop 0.010 m;
  - `smooth_off`: the same with `base_render: []`.
- **Packages:** `isaac_i168_<side>`, C6d's package with only the map path changed, in one
  testbench workspace (`/var/tmp/aeon/tb-i168`).
- **Build:** a scensim worktree at main 1f4fb340 with siw at 4706ff9 (`/mnt/renegade/aeon/ws168`),
  built by `env -i just build` with the gate's caps and memory guard.
- **Runs:** each run is refused unless the bridge and the world server run from ws168's
  install and result.json names main 1f4fb340 and siw 4706ff9. They are interleaved rough_off,
  rough_on, smooth_off, smooth_on, three rounds. Not timing runs: the tick is reported only.
- **Measured per run, offline:** NDT's pitch and z against the truth (medians above 1 m/s),
  along and across the track, from `/localization/kinematic_state` against `ego.csv`; NVTL p05
  and the pose error p95 from the judges.
- **Judged:** by this doc's noise rule and its eight-comparison rule. The "off" sides are also
  issue 167's reach check, judged by 167's doc.
- **Load (133, 2026-11-25, before any result).** The judged quantities are not timing, but they
  are sensitive to load, and the series shares GPU0 with codec 118's training job. Every 15 s
  `i168/load_log.sh` logs GPU0's utilisation, each compute process on it (ours by the
  environment's `I168=1`, else foreign) and the load average. `pair_load.py` gives per run the
  mean GPU0 utilisation while a foreign process was on it, the share of such samples, and the
  mean 1-min load.
  - **A pair counts** (off and on on the same map in the same round) only if its two runs' mean
    GPU0 utilisation under foreign load differs by less than 20 percentage points.
  - A pair that does not count is rerun under the full quiet rule, and the rerun replaces it.
  - 167's reach comparison against C6d is labelled "C6d quiet, these shared".
- **A false start:** the first attempt (10:33) was refused by `scensim run`, because the maps
  were not fetched. The testbench was built without `--symlink-install`, so a fetch in a
  package's source did not reach it. It was rebuilt with `--symlink-install`, the maps fetched
  by package name, and the series restarted.
- *Amended during the series (2026-11-25, labelled, 133):* the runner's provenance check
  was widened during run 2. result.json names siw `4706ff9...+`, which is scensim's mark for a
  submodule checked out off main's pin, as ws168's is by design, and the check had wanted the
  bare SHA.
  - Runs 1 and 2 (rough_off_1, rough_on_1, both passed) ran the old check. Run 2 had started at
    10:42:47, before the file was replaced (atomically), so it kept the old one. Both were
    refused and then accepted by hand on the same evidence (`i168/times.txt` says so).
  - From run 3 (smooth_off_1) the widened check runs.
- *A reading added during the series (133, 2026-11-25; not a judgement, the rule unchanged):*
  Haruna's localization is bimodal along the track per run, either about level with the car
  or 0.086 m behind it (issue 172). The result gives each run's mode, and compares the pose
  error p95 within a mode where both sides have runs in it. The rule's s, from the "off"
  side's own sd, carries the bimodality into the threshold as written.
  - Run 2's log shows the road lowered 0.114 m from the stored depth, with no fallback WARN.

## The NDT A/B's result (2026-11-25, 118, GPU0, 10:34 to 12:18)

Twelve runs, all passed haruna_down, all from ws168's install (main 1f4fb340, siw 4706ff9), in
the order rough_off, rough_on, smooth_off, smooth_on, three rounds. The "on" logs show the road
lowered 0.114 m (rough, from the stored depth) and 0.010 m (smooth), with no fallback WARN. The
"off" logs show nothing lowered. `i168/measure.jsonl`, `i168/judge.txt`.

- **Load:** the 15 s log shows no foreign process on GPU0 during any run (codec's job had ended
  at 10:28), so all six pairs count under the load rule. The host's 1-min load varied (11 to 53
  on 48 cores, other users' CPU work) and is reported, not ruled on.

  | run | pose p95, m | NVTL p05 | z, m | pitch, deg | along / across, m | mode (172) | tick p50 / p95, ms |
  |---|---|---|---|---|---|---|---|
  | rough_off_1 | 0.1884 | 3.118 | -0.0076 | +0.0038 | -0.0862 / -0.0746 | behind | 52.39 / 72.18 |
  | rough_on_1 | 0.12 | 3.118 | -0.0109 | +0.0019 | +0.0023 / -0.0656 | level | 57.77 / 102.05 |
  | smooth_off_1 | 0.1198 | 3.119 | -0.0105 | +0.0059 | +0.0047 / -0.0661 | level | 68.45 / 104.66 |
  | smooth_on_1 | 0.1859 | 3.119 | -0.0037 | +0.0072 | -0.0854 / -0.0722 | behind | 57.68 / 101.38 |
  | rough_off_2 | 0.121 | 3.118 | -0.0139 | +0.0027 | +0.0026 / -0.0694 | level | 49.34 / 94.29 |
  | rough_on_2 | 0.1206 | 3.118 | -0.0110 | +0.0007 | +0.0035 / -0.0664 | level | 50.03 / 69.34 |
  | smooth_off_2 | 0.1834 | 3.119 | -0.0039 | +0.0073 | -0.0865 / -0.0704 | behind | 51.92 / 124.59 |
  | smooth_on_2 | 0.1854 | 3.119 | -0.0037 | +0.0068 | -0.0856 / -0.0705 | behind | 52.86 / 107.35 |
  | rough_off_3 | 0.1228 | 3.118 | -0.0140 | +0.0029 | +0.0027 / -0.0710 | level | 53.52 / 129.72 |
  | rough_on_3 | 0.1217 | 3.118 | -0.0112 | +0.0020 | +0.0029 / -0.0677 | level | 52.94 / 94.04 |
  | smooth_off_3 | 0.1194 | 3.119 | -0.0105 | +0.0064 | +0.0025 / -0.0677 | level | 50.03 / 71.68 |
  | smooth_on_3 | 0.1196 | 3.119 | -0.0103 | +0.0062 | +0.0047 / -0.0664 | level | 49.57 / 92.23 |

- **The rule** (written before the runs): per map and quantity, |mean(on) - mean(off)| against
  2 s sqrt(2/3).

  | quantity | rough: difference / threshold | smooth: difference / threshold |
  |---|---|---|
  | pitch | -0.0016 / 0.0163 deg (floor) | +0.0002 / 0.0163 deg (floor) |
  | z | +0.0008 / 0.0082 m (floor) | +0.0024 / 0.0082 m (floor) |
  | NVTL p05 | 0.000 / 0.033 (floor) | 0.000 / 0.033 (floor) |
  | pose error p95 | -0.0233 / 0.0627 m (sd 0.0384) | +0.0228 / 0.0602 m (sd 0.0368) |

  **No quantity exceeds its threshold on either map: option 2 stands.** The eight-comparison
  rule needs no reruns.
- **The reading by mode** (133; not a judgement): on rough, off is behind, level, level and on is
  level, level, level; on smooth, off is level, behind, level and on is behind, behind, level.
  The pose p95's differences come from the modes. Within a mode: rough level -0.0011 m; smooth
  level 0.0000 m and behind +0.0023 m. NDT's z follows the mode too: a "behind" run's z is 6 to 7
  mm higher than a level one's on the same map (issue 172).
- **118's predictions against it:**
  - pitch less than 0.03 deg on rough_none and 0.01 on smooth: **held** (-0.0016, +0.0002);
  - z less than 0.01 m: **held** (+0.0008, +0.0024);
  - NVTL p05 less than 0.05: **held** (0.000 on both);
  - pose error p95 less than 0.049 m: **held** (-0.023 and +0.023 by the means, both from the
    modes; within 0.003 within a mode).

## Reach

Every lidar or camera result on a road-detail world (C5d, C6b, C6d, 158's reruns, 157). The
judged A/Bs (C6b's and C6d's rocks) compared two sides with the same blindness. Their verdicts
stand for what they compared, and their absolutes say nothing about potholes and ruts. Worlds
without `road_detail.yaml` (Town01 on Isaac, the published Haruna) have no detail mesh and are
not affected.
