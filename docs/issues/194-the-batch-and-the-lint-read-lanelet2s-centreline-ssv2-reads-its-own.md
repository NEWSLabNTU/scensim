# 194: the batch and the lint read lanelet2's centreline; SSv2 reads its own

**Status:** open; the fix approved by the user (through 133, 2026-11-26), its plan below,
before any code. **Severity:** to be judged by the user. On the lanelets vehicles drive, the
two lines differ by at most 7 cm on the lanelets checked, and every reversed stretch (issue 166)
there is an artefact of the line scensim reads. On six connected lanelets of Town01 and Town05
they differ by 5 to 52 m, where lanelet2's line is a chord across a corner. **Found:** 133's
check of SSv2's spline, 2026-11-26.

## What happens

SSv2 does not use a map's centrelines as written. At load, `LaneletLoader::
overwriteLaneletsCenterline` (traffic_simulator, `lanelet_wrapper/lanelet_loader.cpp` 137-179,
at the fork's pin) replaces every lanelet's centreline that has no custom centreline with
`generateFineCenterline`:
1. it resamples both bounds into `ceil(longer bound / 2.0 m)` equal segments by arc length
   (`resamplePoints`, linear between the bound's points);
2. it averages the left and right points pairwise.

With `use_custom_centerline` true (its default, and ours), a lanelet with a custom centreline
keeps it. The CARLA-town maps (dataset 732fd615, the same Town01 and Town05 files as eb93b387)
carry none, so SSv2 replaces every one.

scensim reads lanelet2's own `centerline()` instead (`scensim_batch.map_export._centre_points`,
`map_export.py` 60-66 and 109). lanelet2 computes that line differently, and it is the line
these read:
- the batch's world (`world_lanelet.LaneletWorld`: lengths, s, poses, `toLaneletPose`);
- the anchors' resolve (`scensim_batch.anchors`);
- issue 166's lint and issue 174's layout check (`scensim.lane_positions`);
- seats' model geometry (`scensim.behaviour.seats`, the follower's lane anchor).

## The survey (241, 2026-11-26, read-only)

**(1) Who reads which line.**

| consumer | line | on which maps |
|---|---|---|
| `scensim_batch.map_export` → `world_lanelet.LaneletWorld.load` (the batch on a real map: `scripts/search_run.py`, `agreement_run.py`, `check_resident.py`, `k12_walker_replay.py`) | lanelet2's | the dataset towns |
| `scensim_batch.anchors` (resolve: lanes' lengths, curves' s, conflicts) | lanelet2's, through the export | the dataset towns |
| `scensim.lane_positions` (166's `scensim check` and run warning, 174's `testbench check`) | lanelet2's, through the export | the dataset towns |
| `scensim.behaviour.seats` (a model entity's lane on seats) | lanelet2's, through the export | the dataset towns |
| `scensim_batch.tasks.drift`, `tasks.leadbrake` (094's training and benches) | their own polylines (`LaneletWorld.from_polylines`) | none: not affected |
| `scensim_sampler.anchors` | the map's digest only | not affected |
| `scensim_agent.adapters.simple_route` (the simple pilot's route) | lanelet2's, directly | its own path, not SSv2's |
| `czp.zones_tool` (133's conflict zones), `scripts/coop/e2_lane_change.py` | lanelet2's, directly | their own geometry |

**(2) Town01 and Town05 with SSv2's line.** A Python port of `generateFineCenterline` (its
`resamplePoints` index search and interpolation kept, then the 2-point midpoint rule both sides
apply) was run against `map_export`'s line on every lanelet, with `scensim_batch.catmull.
lanelet_stretches` (166's rule). The scripts and per-lanelet results are on the NAS:
`~/nas/home/2026-11-26 194 centreline survey (241)/`. The raw side reproduces issue 166's
counts exactly, which checks the harness.

| map | lanelets | stretches, lanelet2's line | stretches, SSv2's line |
|---|---|---|---|
| Town01, connected | 130 | 8 on 6 lanelets, 0.185 m, longest 0.032 m | **0** |
| Town01, isolated | 170 | 137 on 35, 247.9 m, longest 11.25 m | 9 on 4, 0.160 m, longest 0.066 m |
| Town05, connected | 470 | 696 on 239, 10.9 m, longest 0.032 m | **0** |
| Town05, isolated | 559 | 411 on 133, 363.2 m, longest 13.88 m | 1, 0.020 m |

- *Issue 166's stretches* are an artefact of lanelet2's line on every connected lanelet of both
  towns. Under SSv2's own line, 10 stretches remain on the two maps, all on isolated lanelets
  and at most 6.6 cm long.
- *Issue 174's refusals:* none today (no layout places a prop in a stretch, 174's record), and
  none would be possible on a connected lanelet.
- *The follower's workaround* (`behaviour/follower.py`: the gap and placement measured in the
  spline's s across a reversed loop, issue 166) handles a case that does not arise on SSv2's
  line on connected lanelets. It is harmless.

**Where the lines differ more** (the largest distance between them, both ways):
- Town01: 81 lanelets differ by over 5 cm and 49 by over 25 cm. 46 of those 49 are isolated.
- Town05: 197 lanelets differ by over 5 cm and 138 by over 25 cm. 135 of the 138 are isolated.
- On six *connected* road lanelets, lanelet2's `centerline()` has only two points: a straight
  chord between the lanelet's ends, across the corner the bounds turn. The bounds have 26 to
  28 points each.

| map | lanelet | lanelet2's line | SSv2's line | largest distance |
|---|---|---|---|---|
| Town01 | 40203 | 172.9 m | 218.7 m | 52.4 m |
| Town01 | 39692 | 233.9 m | 274.6 m | 45.3 m |
| Town01 | 36200 | 168.1 m | 201.8 m | 37.8 m |
| Town05 | 110937 | 82.4 m | 115.1 m | 39.8 m |
| Town05 | 119197 | 51.7 m | 71.5 m | 24.4 m |
| Town05 | 113157 | 58.7 m | 62.7 m | 5.5 m |

No scenario, anchor or configuration in the repository names any of the six, so no run has
used them.

**(3) What changes for the batch's results.**
- *K2.4's lanelets* (6583, 32582, 41199, 42451, 42664; Town01's anchors west_street,
  west_left_turn and north_through): 6583, 32582, 41199 and the north_through lanelets are
  unchanged, to under 0.1 mm. On 42664 (west_left_turn's bend) the lines differ by up to
  4.4 cm, the lanelet 1.1 cm shorter on SSv2's. On 42451 they differ by up to 7.0 cm, 1.7 cm
  shorter. K2.4 found its NPCs within 2.8 cm of seats. *Hypothesis, untested:* part of that
  residual is this line on the turns.
- *K10, K11c to K11e* (CS1's walker on lanelet 6583): unchanged.
- *K13 step v* (the platoon on Town05's west_avenue, 10 lanelets): the lines are at most 5 mm
  apart, and the lane is 0.411 m shorter on SSv2's line (372.107 against 372.518 m). Its 18
  reversed stretches (K13's note) vanish. Positions far along the lane move by up to 0.41 m in
  s. Its result (0 failures in 21000 runs, issue 183's interval) is not expected to change,
  but that is not shown.
- *Anchors:* their resolved lengths and curve s on 42664 move by about a centimetre. Town05's
  west_avenue length moves 0.41 m.

## The fix plan (for the user, through 133)

1. *`map_export` takes SSv2's line.* `_centre_points` returns `generateFineCenterline`'s points
   (the port above, 2.0 m, both bounds by arc length, averaged) for every lanelet without a
   custom centreline. A lanelet with one (`hasCustomCenterline`) keeps it, as SSv2 does with
   `use_custom_centerline` true. Then the 2-point midpoint rule applies, as now.
   - The export's `VERSION` goes up and records the line's source, so `LaneletWorld.load`
     refuses an old export by name and every export is made again.
   - Anchors are resolved again, with the change in each resolved value listed.
2. *Checked against SSv2 itself, once.* The fork's `lanelet_wrapper` loads Town01 and Town05,
   and its centre points are dumped (a small test node or gtest in the fork, or the existing
   SSv2 log path) and compared point for point with the port. The prediction: equal to 1e-9 m.
3. *The tests:* the port on hand-made bounds with known results (unequal bound lengths, a
   2-point bound, a lanelet shorter than 2 m), and the export's line equal to the port's.
4. *What reads it changes with it, with no code of its own:*
   - 166's lint keeps its rule. Its stretches on connected lanelets become none, which the
     record says.
   - 174's check stays.
   - The follower's workaround stays (harmless), or is simplified in a later cleanup.
5. *Re-measured, CPU only:*
   - K2.4's agreement rows recomputed on the batch side against the kept seats truth. The
     prediction: the NPCs' trajectory error on 42451 and 42664 falls below K2.4's 2.8 cm.
   - The lint over the repository's scenarios: 0 refused, as now.
6. *Not in this fix, listed for the user:*
   - `simple_route` and `czp` use lanelet2's line for their own geometry. On the six degenerate
     lanelets a simple pilot's route, or a czp approach, would cut the corner. That is a defect
     of theirs, independent of SSv2: a separate issue, or the same port shared.
   - Autoware's map loader builds its own centrelines, which this does not touch.
   - SSv2's warning says `use_custom_centerline`'s default becomes false after January 2026.
     With these maps nothing changes, since they carry no custom centrelines.

## The fix: the plan (241, 2026-11-26; approved by the user through 133; 243's review folded in, before any code)

243 reviewed the draft's plan against SSv2 31b12c5f (`lanelet_loader.cpp` 137-255,
`lanelet_wrapper.hpp` 194-214). 133 had every point folded in.

1. *The port, `ssv2_centerline(left, right)` in `scensim_batch.map_export`.* Pure Python, no
   lanelet2. It keeps SSv2's arithmetic exactly:
   - `n = max(ceil(longer bound's length / 2.0), 1)`, the lengths in **3D** (lanelet2's
     `length` and `distance` on `Point3d`);
   - each bound resampled with `resamplePoints`' order: the accumulated 3D lengths; for
     `i in 0..n`, `t = (i / n) * length`; the index pair by `findNearestIndexPair`'s order
     (`t < acc[1]` first, then `t > acc[N-2]`, then the first `i` with
     `acc[i-1] <= t <= acc[i]`, so a tie takes the earlier segment);
   - the point `back + dir * (t - back_len) / seg_len`;
   - the pairwise average of left and right, z included.
2. *What SSv2 cannot resample is refused, never skipped; nothing else is (243, 133).* Refused,
   naming the lanelet and the bound, and counted:
   - a bound with fewer than 2 points (SSv2's `acc.at(1)` throws);
   - a bound whose first or last segment has zero length. SSv2 selects the first at t = 0, and
     the last when t lands past the one before it, and gets NaN.
   A duplicate point in the middle is accepted, as SSv2 accepts it: the segment before it wins
   the tie, so the zero-length one is never selected. A search that finds no segment (only a
   NaN t) is an error naming the lanelet, as SSv2's `findNearestIndexPair` throws. Both towns
   export with none refused.
3. *A custom centreline is kept, as SSv2 keeps it.* SSv2's test is lanelet2's
   `hasCustomCenterline()`: a relation member with role `centerline`. The Python binding does
   not expose it (checked 2026-11-26: `Lanelet` has only `centerline`), so `map_export` reads
   the role from the OSM's relations.
   - The towns' "none" was established that way: `role="centerline"` occurs 0 times in Town01's
     and Town05's `lanelet2_map.osm`.
   - SSv2 keeps a custom line only with `use_custom_centerline` true, the default of
     scenario_test_runner's launch argument (`launch.py` 110). Nothing in scensim sets it. The
     export records the value it assumes, `"use_custom_centerline": true`, so a future change
     there is a refusal, not a silent difference.
4. *The midpoint rule after it*, as SSv2's `CenterPointsCache::centerPoints` applies it. With the
   fine line that is exactly when `n == 1`, a longer bound of 2.0 m or less.
5. *Versions and refusals.*
   - `map_export.VERSION` goes from 2 to 3, and the export records
     `"centerline": "ssv2-fine-2.0"` and `"use_custom_centerline": true`.
   - `LaneletWorld.load` refuses an older export with its cause and remedy: "exported with
     lanelet2's centreline (v2); SSv2 uses its own 2 m line (issue 194): run python3 -m
     scensim_batch.map_export again".
   - **The resolved anchors** carry the line too. `anchors.VERSION` (batch and sampler) goes
     from 1 to 2 and the resolved file records `"centerline": "ssv2-fine-2.0"`.
     `scensim_sampler.anchors.load_resolved` refuses a v1 file the same way, naming the cause
     and `scensim update` (or the lock bump). Until a project's lock moves to the new dataset
     revision, its runs refuse to resolve anchors. That is loud, not silent.
6. *Tests* (`test_map_export.py`, new, no lanelet2; and the sampler's):
   - straight bounds of unequal lengths;
   - a 2-point bound against a many-point one;
   - a **sloped** bound (z changing), its split fractions taken from 3D lengths;
   - the index search's order: a target exactly on a bound's point takes the earlier segment;
     the first and last segments;
   - a longer bound of exactly 2.0 m (one segment, the midpoint added) and just above it (two
     segments, none added);
   - refusals: a 1-point bound, and duplicate points at the start, in the middle and at the
     end, each naming the lanelet;
   - the OSM's `centerline` role detected and kept;
   - a v2 export refused with the remedy;
   - a v1 resolved-anchors file refused with the remedy.
7. *Checked against SSv2 itself, once, in two parts.* A one-off C++ program in the scratchpad,
   not committed, built against the workspace's installed `traffic_simulator`, activates the
   fork's `lanelet_wrapper` on Town01 and Town05 and dumps each lanelet's bounds and centre
   points in SSv2's load frame.
   - (a) *The algorithm:* the port fed SSv2's own bound points against SSv2's line.
     **Prediction:** equal to 1e-9 m on every lanelet.
   - (b) *The frame:* the export's line, from its map-frame bounds, against SSv2's, with
     **no offset applied and nothing fitted** (243). Both frames come from the same
     `map_projector_info.yaml`: TransverseMercator, origin (0, 0), scale 1.0. SSv2 loads
     with lanelet2's `TransverseMercatorProjector` (`lanelet_loader.cpp` 50-100), the export
     with `simple_route.map_frame_positions`' own TransverseMercator, on the same
     latitudes and longitudes. Only the two implementations differ. **Prediction:** the raw
     difference is at most 1 mm on every point of both towns. Its largest value is reported
     as measured. Any frame difference is reported as the frame's, not taken for a port bug.
   If the fork's loader cannot be called that way, its gtest fixture (`test_lanelet_wrapper.hpp`)
   is the fallback, in a scratch build.
8. *What reads the export, re-measured* (CPU only):
   - the lint over the repository's scenarios: 0 refused, 0 warned;
   - `lane_positions.stretches` on both towns: none on a connected lanelet, 10 isolated;
   - K2.4's agreement rows recomputed on the batch side against the kept seats runs (139's).
     **Prediction:** follow_to_goal's lead max falls below 2.8 cm; k24_npc_stops_for_ego's
     follower stays at about 2.6 cm. If the seats runs are not kept, that is recorded.
9. *The dataset and the locks (outward: prepared, shown to 133, uploaded only on its OK).*
   - `anchors resolve` again on every dataset map with an `anchors.yaml`.
   - Each resolved value's change is listed here (predicted: under 1.2 cm on Town01,
     west_avenue 0.411 m on Town05).
   - A file diff summary and a dataset commit plan go to 133 first.
   - After the upload: each project's `scensim.lock` bumped to the new revision. The projects
     that move are listed here.
10. *Kept:* 166's lint, 174's check, the follower's workaround. *Not here:* simple_route and czp
    (a separate follow-up).
11. *One landing, in this order (243's review; 133's ruling).* From this code on, the sampler
    refuses every v1 `anchors.resolved.json`, so main must never pin a dataset revision the
    sampler refuses. The order:
    1. step 7(a) at 1e-9 on every lanelet of both towns, the six degenerate ones included;
    2. the K2.4 recompute;
    3. the re-resolve diff;
    4. the dataset commit on HF, after 133's OK on its diff summary;
    5. one scensim landing: the code, every project's `scensim.lock` bump to that revision, and
       this record, gated by `just gate`.
    The gate exercises at least one project that reads resolved anchors, or a named test that
    loads the new revision's files, so a missed lock fails it. 243 reviews the code before the
    push.

## The fix: results (241, 2026-11-26)

**Step 7, against SSv2 itself.**
- A one-off C++ program (the scratchpad's `ssv2_centre_dump`, not committed; its source and
  dumps are on the NAS under `2026-11-26 194 review (241)/step7/`) was built against the
  installed `traffic_simulator` of a clean build at main 6690f884, fork pin 31b12c5f.
- It called `LaneletWrapper::activate` on each town and printed every lanelet's bounds and
  `lanelet_map::centerPoints` (the cache's points, midpoint rule included), at %.17g.

| town | lanelets | (a) the port on SSv2's bounds against SSv2's points | (b) the export (map frame, no offset) against SSv2's points | point counts |
|---|---|---|---|---|
| Town01 | 300 | max 1.99e-12 m (lanelet 25061); the six degenerate at most 5.7e-14 m | max 1.93e-12 m | equal on every lanelet |
| Town05 | 1029 | max 1.48e-12 m (lanelet 53191); the six at most 2.8e-14 m | max 1.71e-12 m | equal on every lanelet |

- (a) **held** (predicted 1e-9 m).
- (b) **held** (predicted 1 mm): the two TransverseMercator implementations agree to 2e-12 m
  on these towns, with nothing fitted.
- Both towns export with **no refused bound** (predicted none).

**Step 9, the anchors resolved again** on the new export, against the dataset's main
(eb93b387). The diff summary and both files are on the NAS under `resolve/`.

| anchor | change |
|---|---|
| Town01 west_street, north_through | length unchanged (under 0.1 mm) |
| Town01 west_left_turn | length 290.0893 → 290.0786 m (-1.07 cm) |
| Town01 west_left_turn_bend | mean radius -0.8 mm; **min radius 8.178 → 8.840 m (+0.662 m)**; turn +0.1 mrad |
| Town01 west_junction | the west_left_turn s bounds -0.82 and -0.90 cm |
| Town01 west_left_turn_x_north_through | s -0.96 and -0.34 cm; position -3.5 mm in y; **angle -2.1993 → -2.1781 rad (+0.021 rad)** |
| Town05 west_avenue | length 372.5177 → 372.1070 m (-0.411 m); reversed stretches 18 → 0; heading error with them 3.14 → 0.0006 rad |

- The lengths and s held as predicted: under 1.2 cm on Town01, and west_avenue's 0.411 m.
- Not predicted: the bend's minimum radius rose 0.66 m, and the crossing angle moved
  0.021 rad. Both are read off the line's own curvature. On lanelet 42664 the lanelet2 line had
  close points with up to 4.4 cm of wiggle (this record's survey), which made its sharpest
  local radius 8.18 m; SSv2's even 2 m points make it 8.84 m.
- The heading tables are shorter (707 → 300 points on north_through), as the line has fewer,
  evener points.
- Main's resolved files were written by an earlier resolver: they lack `x` and `y` and
  `heading_max_error_reversed`, which the new ones carry.

**The projects that move.** Every lock that takes a map with an `anchors.resolved.json` moves
to the new dataset revision. Every other file those locks name is byte for byte the same as
main's (checked against eb93b387's hashes), so only the anchors files change for them:
- 19d52699 (Town01): bench, demo, gap, gap_campaign, isaac_demo, isaac_road_physics,
  isaac_rough_road, isaac_soil, isaac_t2 (autoware, command, launch_own, none, simple),
  isaac_verge, k12_commanded, k12_commanded_free, k9f_zones, set050, set050_tour, two_av;
- 19d52699 (Town01, Town02): isaac_basic;
- 732fd615 (Town01, Town01_west_street_closed): k9_cs3, k9_cs3_isaac;
- eb93b387: basic, dev, k13_platoon, drift_lap.

The locks taking no anchors file (c2b, e2, s5 on Town03; speed_ladder on town05_ring_110kmh)
stay. K2.4's recompute waits for 139's seats runs.

**Step 8, K2.4's agreement recomputed.**
- The seats runs are 139's, kept: follow_to_goal 2026-11-21T22-30-49 and npc_stops_for_ego
  2026-11-22T00-03-32, copied to the NAS (`2026-11-26 K2.4 seats runs for 194 (139)`).
- The batch side was replayed with `agreement_run.py --ego-from-truth`: the seats ego's truth
  played back, so no engine and no Isaac.
  - It ran twice: the v2 export with the code before the fix (main 6690f884), and the v3
    export with the fix.
  - The v3 side reads the new resolved anchors from a scratch copy of Town01. With the
    dataset's own v1 file, the fix refused, as designed.
  - K2.4's published rows ran engine A, with the ego in PhysX, which needs a GPU and Isaac. This
    mode isolates the NPCs, and the v2 side reproduces the published row: 2.81 cm.

| row | NPC | v2 (lanelet2's line) | v3 (SSv2's line) |
|---|---|---|---|
| follow_to_goal | lead | max 2.81 cm, RMS 1.37 cm, yaw 0.0345 rad; 270 steps over 2 cm (976 to 1262) | max **3.96 cm**, RMS **0.99 cm**, yaw 0.0280 rad; **20 steps** over 2 cm (885 to 1010) |
| k24_npc_stops_for_ego | follower | max 2.46 cm, RMS 2.28 cm | max 2.46 cm, RMS 2.28 cm (unchanged) |

Both rows have their outcomes (passed/passed) and every storyboard element's step unchanged.
- The prediction **failed in part**. The lead's RMS fell by 28 %, and the steps over 2 cm fell from
  270 to 20. But its maximum rose, from 2.81 to 3.96 cm. The follower's row held (unchanged, on
  6583).
- The new maximum is at step 1000, where the lead leaves the turn: lanelet 42664's end and
  32582's start, by the junction's exit (88.39, -142.51).
- *Hypothesis, untested:* the batch's route follows a Catmull-Rom cubic on samples 2.5 m apart
  (K2.4's last fix, batch-executor.md section 8). That spacing was tuned against lanelet2's
  dense line. On SSv2's sparser line (14 points on 42664, 24 on 32582), the route's samples
  across the lanelet join no longer fall where SSv2's per-lanelet splines bend. That is a
  batch-model detail, not the centreline. It is recorded here for 092 K2.4, not fixed in 194.

**Step 9, the sampling hypothesis tested (133's ask, CPU only).**

The plan:
- Replay K2.4's two rows exactly as in step 8 (`--ego-from-truth`, the same seats runs and
  exports, v2 and v3), changing only `--route-points`: the samples on each NPC's 300 m route.
- Step 8 used the default, 121 (2.5 m apart). The variants:
  - 151 (2.0 m, SSv2's nominal spacing; not aligned to its points);
  - 301 (1.0 m);
  - 601 (0.5 m), where the Catmull-Rom interpolation between samples is nearly the sampled
    spline itself.
- Knots placed at the lanelet join need a code change. They are not tried unless the dense
  runs point there.

Predictions, before any run:
- If the hypothesis holds, v3's lead maximum falls with the spacing, to 2.8 cm or less at 601,
  and its step-1000 peak shrinks most. v2's maximum moves less, because lanelet2's dense line
  is sampled the same at every spacing.
- If it fails, the 601 maximum stays near 3.96 cm. The excess then comes from the joined spline
  the route samples (`Spline` over all of the route's lanelets' points), not from the sampling:
  SSv2's entity follows each lanelet's own spline, which differs from the joined one near the
  joint.
- The follower's row (npc_stops_for_ego, 2.46 cm) does not move at any spacing: it is a straight
  route.
- I lean to the second (55 %). At 2.5 m the Catmull-Rom error on a curve of 8.8 m radius is well
  under a millimetre, too little for 1.15 cm.

The result (2026-11-26; the lead in follow_to_goal; NAS `2026-11-26 194 review (241)/step9/`):

| route points (spacing) | v2 max, at step | v2 RMS | v3 max, at step | v3 RMS | v3 steps over 2 cm |
|---|---|---|---|---|---|
| 121 (2.5 m), step 8's | 2.81 cm, 1094 | 1.37 cm | 3.96 cm, 1000 | 0.99 cm | 20 |
| 151 (2.0 m) | 3.32 cm, 1219 | 1.36 cm | 3.96 cm, 1000 | 0.96 cm | 12 |
| 301 (1.0 m) | 3.32 cm, 1220 | 1.36 cm | 4.09 cm, 998 | 0.96 cm | 12 |
| 601 (0.5 m) | 3.32 cm, 1220 | 1.36 cm | 3.96 cm, 1000 | 0.96 cm | 18 |

The control (121) reproduces step 8 to the digit. Every row's outcome was passed/passed.

**The predictions:**
- **Failed:** the hypothesis. v3's maximum does not fall with the spacing; it is 3.96 cm at
  0.5 m. The route's sampling is not the cause.
- **Held:** the follower stays at 2.46 cm at every spacing.
- **Failed:** "v2 moves less". v2's maximum rises from 2.81 to 3.32 cm once the samples are 2 m
  apart or closer. Its 2.81 cm at 2.5 m was partly the sampling's luck.
- So, on sampling-converged routes, the comparison is v2 3.32 cm against v3 3.96 cm (RMS 1.36
  against 0.96), not 2.81 against 3.96.

**The error is along the route, not across it.** At 0.5 m, in the seats lead's frame:
- lateral: +0.44 cm on both exports, through and after the turn;
- along-track: v2 lags by a steady 2.77 cm from step 998 on;
- along-track, v3: lags 0.54 cm at step 990, then 2.02, 2.89 and 3.93 cm (step 1000, the
  42664 → 32582 join), then recovers to 1.74 cm by step 1010. A transient of about 2 cm at the
  lanelet change.

That points at arc-length bookkeeping at the lanelet change:
- SSv2 carries an entity's `s` from one lanelet's own spline onto the next one's;
- the batch advances along one spline joined over the route's lanelets, whose length near the
  joint differs from the two per-lanelet lengths.

This is the second prediction's mechanism, made along-track. It is not measured yet. The next
cheap test (CPU only): the per-lanelet spline lengths of 42664 and 32582 on the v3 line against
the joined spline's arc length between the same points. If the difference is about 2 cm, it is
the transient. Still a batch-model detail for 092 K2.4; 194's line is not the cause.

**The follow-up check (CPU only, catmull.Spline on each export's lines of 42664 and 32582):**
- *Total lengths agree:* the joined spline is 0.15 cm shorter than the two per-lanelet splines
  together on v3, and equal on v2. So it is not a length mismatch.
- *Shapes near the joint differ:* within 4 m of the joint, the largest distance between a
  per-lanelet pose and the joined spline's pose at the same `s`:
  - v2 (73 and 177 points): 0.00 cm;
  - v3 (14 and 24 points): **2.10 cm**, 0.55 m before the joint, almost all along the route
    (dx 0.09, dy 2.10 cm, heading -y).

The joined spline's end conditions at the joint differ from each lanelet's own. On SSv2's
sparse points, that moves the arc-length parameterisation by about 2 cm there. On lanelet2's
dense line it does not show.

That matches the replay's along-track transient of about 2 cm at the change from 42664 to 32582.
The prediction above ("if the difference is about 2 cm, it is the transient") **held**,
measured as a pose difference rather than a length.

Where a fix would go is not decided, and not in 194: the batch's route would follow per-lanelet
splines across the joint, as SSv2's entity does (`world_lanelet._route`). That is 092 K2.4's.

**Filed, not fixed (133, 2026-11-26).** The per-lanelet route is a 092 K2.4 follow-up (roadmap
092, "K2.4 follow-up: the route across a lanelet joint"). This issue's maximum reads **v2 3.32
cm (converged) against v3 3.96 cm**. Step 8's 2.81 cm was v2 at 2.5 m samples.

With that cause recorded, the user's condition for the upload was met ("upload once max <= 2.8
cm OR the cause is recorded"), and 133 approved it.

**The dataset commit (2026-11-26):** df499322639f279f588ff5f6fd661169027eb7a8 on
jerry73204/carla-town-autoware-maps, its parent eb93b387, message "anchors resolved on SSv2's own
centreline (scensim issue 194)". It holds three files:
- `Town01/anchors.resolved.json` (sha256 84e60a47...);
- `Town05/anchors.resolved.json` (a47872b0...);
- the root `SHA256SUMS`, changed in those two lines only.

The manifest was not in the plan's two files. `scensim assets fetch` checks every file against
it, so leaving it out would have broken every bumped lock; 133 approved the third file. A fetch
with `--verify` at df499322 passed.

**The locks.** The 27 listed above move to df499322: in each, the commit line and the
anchors lines changed, nothing else. Every one of them passes `scensim assets fetch --verify`
and `scensim assets check`. The dataset's newest tag (v2026.11g) is not at df499322, so a
`--update` would not reach it; each lock names the commit.
