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
2. *What SSv2 cannot resample is refused, never skipped.* A bound with fewer than 2 points
   (SSv2's `acc.at(1)` throws) and a bound with consecutive duplicate points (SSv2 can select
   that zero-length segment and get NaN) are refused. The refusal names the lanelet and the
   bound. The survey reports how many bounds of Town01 and Town05 are like that, predicted
   none.
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
11. *Gate:* `just gate`, then the push request with its line. 243 reviews the code before the
    push.
