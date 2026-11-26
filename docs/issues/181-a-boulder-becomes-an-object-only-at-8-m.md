# 181: a 35 cm boulder becomes an object only at 8 m although its points show from 31 m

**Status:** open; plan written (2026-11-25), for 133. **Severity:** to be judged in the plan: on
Isaac, the Autoware stack begins to brake for a 35 cm boulder in the lane only about 6 m before
its bumper reaches it, and strikes it (issue 182 for what follows). **Found:** 2026-11-25,
scensim 118, 086 C6e3 run b2 (numbered by 133).

## What happens

086 C6e3, run b2: fixture_c6b at scensim main 0291abb3 (siw 4706ff9), Autoware's Model 3,
4.18 m/s, motion BVH off. A static boulder, 35 cm nominal (embed 0.2), stands 0.350 m above the
road at s 400 m, v 1.625, in the lane's middle. From `measure.py` on the run's record:

- the non-ground cloud (`/perception/obstacle_segmentation/pointcloud`) has points within 1 m of
  it from 30.8 m (ego origin to the rock), up to 135 in one frame, in 123 frames;
- the perception objects (`/perception/object_recognition/objects`) have one within 1 m of it
  only from 8.0 m (about 4.3 m from the bumper), in 10 frames in all;
- the truth trace shows braking from about x 390 at about 2.2 m/s^2, and a strike at 0.77 m/s.

C6e3 predicted it non-ground and an object (held), first seen at 32 m at most (held for its
points; its object at 8.0 m).

## Why (a hypothesis, untested)

The clustering or the shape stage drops a low, wide cluster until it is close: the boulder is
about 0.6 m across and 0.35 m tall, low for the profile's clustering. The ego log also has 11,587
"obstacle pointcloud is empty! Can not validate objects." WARN lines from the
obstacle_pointcloud_based_validator and 596 "Empty sensor points!" from euclidean_cluster. Those
are for the run as a whole, not timed against the boulder.

## Steps (predictions written before each, when taken up)

1. Replay b2's record through the perception stack offline, logging each stage's output near
   the boulder (the clusters, the shapes, the validator's decisions).
2. Name the stage and its parameter, then a plan for 133.

## The plan (written 2026-11-25, before any run; for 133)

**What b2's record can and cannot do.** It holds the non-ground cloud
(`/perception/obstacle_segmentation/pointcloud`) and the final objects
(`/perception/object_recognition/objects`), not the raw lidar cloud or the stages between.
So there is no replay from it: the pipeline's input is the raw cloud. Step 1 records what a
replay and a stage-by-stage reading need.

**The stages, from the profile and Autoware 1.5.0's launch files (read for this plan).** The
profile runs `lidar_detection_model: clustering`. Euclidean clustering of the non-ground cloud
gives clusters, shape estimation gives objects, the object validator
(`obstacle_pointcloud_based_validator`) checks each object against the obstacle cloud, then a
lanelet filter, detection by tracker, tracking and prediction give the final objects. The
validator's parameters (`obstacle_pointcloud_based_validator.param.yaml`): `min_points_num` and
`max_points_num` both 10 for every class, `min_points_and_distance_ratio` 800,
`validate_max_distance_m` 70. Read as Autoware's code clamps it (the ratio over the distance,
clamped to [min, max]), an object needs 10 obstacle points at any distance. The boulder had up to
135 a frame from 31 m, so the validator alone is not expected to drop it. The 11,587 "obstacle
pointcloud is empty" WARN lines are the validator finding an empty cloud on bare road, which is
most frames, and say nothing about the boulder.

**Step 1, the run (one, fixture_c6b, the boulder at s 400).** The same testbench as 086 C6e3's
b runs, built at the main of the day, with the record extended to the raw cloud
(`/sensing/lidar/top/pointcloud_before_sync`) and to each stage's output:
the clustering's clusters and objects, the shape estimator's objects, the validator's output,
the lanelet filter's, detection by tracker's, and tracking's. The names are checked against a
live stack's `ros2 topic list` between runs, before the run, and nothing is changed during it.
The run also serves issue 182 (its topics below).

**Predictions (before the run).** Per frame, as the ego closes from 40 m to 8 m: (a) the
non-ground cloud holds the boulder's points from about 31 m, as in b2. (b) *Hypothesis H1, the
clustering:* the clusters hold no cluster at the boulder beyond about 8 to 10 m: too few points
in a voxel for the cluster's minimum size at range. (c) *Hypothesis H2, shape estimation or a
filter after it:* a cluster exists from about 31 m and its object is dropped later, at a stage
that is named by the first topic where it disappears. (d) If both fail (the object exists at
every stage from about 31 m and only the final objects lack it), tracking's confirmation is the
cause. The stage where the boulder first appears at under 10 m in every frame before is the
answer. A replay of the recorded raw cloud through the pipeline with one parameter changed comes
after, as its own plan.

**The record's size (133; corrected before any run).** An earlier figure here, about 100 MB a
minute for the raw cloud, was wrong. The rig's OS1 gives about 126,600 points a scan (C6e2's
first-scan log), at 16 bytes a point (`xyzirc`) and 20 scans a second: about 40 MB a second,
**about 2.4 GB a minute**. The run lasts up to the scenario's 600 s timeout (b2 crept until it),
so the raw cloud is up to about 24 GB. The stage outputs and 182's topics are small (objects,
diagnostics), and the non-ground cloud was 22 MB a run in C6e3. Expected total: about 25 GB.
The log disk (`/mnt/renegade`, NVMe) had 190 GB free at 21:2x on 2026-11-25. It is checked
again just before the run, which goes ahead only with at least 60 GB free. The record is moved
to the NAS and then off the log disk after the judgement.

**Amended before the run (133, 2026-11-25): reach, and a bounded record.**
- *The start.* b1 stopped dead on the static rock at x 100 and never reached the boulder. A run
  that sticks there gives 181 and 182 nothing. So the run's scenario (a copy of
  `fixture_c6b_down.xosc`, `tesla_model3`) starts the ego at x 320 m, past the rocks at 100, 200
  and 300, the goal unchanged at x 490. This is for reach. It is not meant to avoid issue 180,
  which stands as recorded.
- *The window.* With the start at x 320, the ego is 80 m before the boulder and the record
  covers from there. That is a little more than the window asked for (from x 340, about 60 m
  before, past the boulder's first points at 31 m). scensim records the whole run, and a later
  start would give NDT too little road to settle. The run ends by the scenario's
  `SimulationTimeCondition`, set to 150 s instead of 600. At about 4.2 m/s after start-up
  (stack ready, then motion about 10 s in, as in C6e3), the first strike comes about 30 s in,
  so 150 s leaves at least 90 s after it. If the strike comes later than 60 s, the record says
  how much of the 90 s it holds.
- *Expected size from that window.* The raw cloud over at most 150 s at about 40 MB a second is
  about 6 GB. With the rest, about 6.5 GB. The 60 GB floor is checked just before the run.

**Amended before the run (2026-11-25 22:3x, not after a result): the record's names, checked on
a live stack.** The run's testbench is `isaac_c6e3_r181` (from `isaac_c6e3_c6b`, its scenario the
copy above). Its stack was brought up alone at 22:26, `ros2 topic list` read in the ego's domain
(653 topics) and the scenario's (14), and the stack stopped at 22:27, before the record was set.
Recorded besides C6e3's six: the raw cloud `/sensing/lidar/top/pointcloud_before_sync`; the
clustering's `detection/clustering/clusters`; shape estimation's `clustering/objects_with_feature`;
the feature remover's `clustering/objects`; the validator's `clustering/validation/objects`;
`detection/detection_by_tracker/objects`; `tracking/objects`. Not found, so not recorded: a lanelet
filter's own output and a merged `detection/objects` (no such topic on the live stack; the stage
between the validator and tracking is read from tracking's input side, not recorded).
For 182: `/system/fail_safe/mrm_state`, `/system/mrm/emergency_stop/status`,
`/system/emergency/hazard_status`, `/system/emergency_holding`, `/diagnostics`,
`/diagnostics_graph/struct` and `/status`, `/api/planning/velocity_factors`, the planning factors of
`obstacle_stop`, `motion_velocity_planner` and `surround_obstacle_checker`,
`/control/command/control_cmd`, `/control/command/emergency_cmd`, `/system/emergency/control_cmd`
and `/control/collision_detector/debug_markers` (the collision detector publishes no other topic;
its state is in `/diagnostics`). `stop_reasons` is not published in this stack (Autoware 1.5 has
planning factors instead).

## Step 1's result (2026-11-25, run r1, after the predictions above)

The run: scensim main 1ed265d7 (scensim_isaac_world 3a948eea), `isaac_c6e3_r181`, 22:28:11 to
22:31:43. It ended on the scenario's 150 s timeout, as planned (verdict "failed"; nvtl and
pose_error passed). The record is 3.6 GB. The ego struck the boulder at sim 1032.75 s, base_link
at x 396.9, and stayed there in contact for the rest of the run. The NAS copy is
`autoveh/logs/2026 SSv2 on CARLA/2026-11-25 issues 181 182 step 1 run (118)`, with
SHA256SUMS checked there.

The frames in which each stage had the boulder (a centre within 1.0 m of x 400, y 1.625, put
into the map by the kinematic state's pose), by range from base_link:

| stage | 40 to 31 m | 31 to 20 m | 20 to 10 m | 10 to 5 m | first seen |
|---|---|---|---|---|---|
| non-ground points (max in one frame) | 0 | 8 | 19 | 128 | 30.9 m |
| clustering's clusters, shape estimation, feature remover | 0/43 | 0/53 | 8/47 | 30/30 | 12.3 m; every frame from 10.8 m |
| the validator | 0/43 | 0/53 | 0/47 | 22/30 | 8.8 m |
| detection by tracker | 0/43 | 0/53 | 0/47 | 0/30 | never |
| tracking; the final objects | 0/21 | 0/26 | 0/24 | 11/15 | 8.2 m |

After the strike, at about 3 m, no stage had it in any of 2555 frames, and the non-ground cloud
held at most 1 point there in a frame.

Against the predictions:
- (a) the non-ground cloud from about 31 m: **held** (30.9 m; up to 8 points a frame from 31 to
  20 m, 19 from 20 to 10 m).
- (b) H1, the clustering: **held**, slightly earlier than predicted. The clustering is the first
  stage without the boulder. It has no cluster at the boulder beyond 12.3 m, and has one in every
  frame from 10.8 m, against "beyond about 8 to 10 m".
- (c) H2, a cluster from about 31 m dropped later: **FAILED**. No cluster exists beyond 12.3 m.
  The validator loses it again in frames that the clustering had: it has none from 20 to 10 m,
  and has it first at 8.8 m.
- (d) tracking's confirmation alone: not the cause. Tracking has it from 8.2 m, close to the
  validator's 8.8 m.

So the boulder's first stage under 10 m is the clustering, with the validator a second, smaller
delay (from 12.3 m to 8.8 m). Which parameter does it is the replay plan's question.

## Step 2: the clustering's input, read from the source, and a CPU replay (241, 2026-11-27; plan and predictions, before any replay)

133 assigned step 2 to 241: name the filter, CPU only first. 118's live C6e3 c6b run for 177 may
add the topics named below.

**What the clustering actually reads.** Reading Autoware 1.5.0's launch files and the 0.48.0
source (autoware_universe, `perception/autoware_compare_map_segmentation` and
`perception/autoware_euclidean_cluster`) shows that the clustering's input is not the non-ground
cloud that b2 and r1 measured. `detection.launch.xml` feeds it
`pointcloud_map_filtered/pointcloud`, which is the non-ground cloud after two filters
(`pointcloud_map_filter.launch.py`, `use_pointcloud_map` true by default):
1. `VoxelGridDownsampleFilter`, 0.1 m voxels (`down_sample_voxel_size`), one centroid per
   voxel;
2. `VoxelBasedCompareMapFilter` against `/map/pointcloud_map`:
   - the map is voxelised at 0.5 x 0.5 x 0.3 m (`distance_threshold` 0.5,
     `downsize_ratio_z_axis` 0.6), one centroid per voxel;
   - a point is dropped as "map" when its own voxel, or any of the 26 neighbours at ±0.5 m in x
     and y and ±0.3 m in z, has a centroid within |dx| < 0.5, |dy| < 0.5 and |dz| < 0.3 of it
     (`is_close_to_neighbor_voxels`, `is_in_voxel`).

Then `VoxelGridBasedEuclideanCluster` clusters the 2D centroids of 0.3 m columns (z ignored)
with 0.7 m tolerance, and keeps a cluster only with at least `min_cluster_size` **10 points** of
its input.

So on mapped road, every boulder point less than about 0.3 m above the road's map centroids is
removed as map. Of a 0.35 m boulder, only roughly its top 5 cm can reach the clustering, and those
points are first merged into 0.1 m voxels.

**Hypothesis H3:** the compare-map filter's vertical tolerance (0.3 m) removes all but the
boulder's top. The surviving 0.1 m voxels stay under 10, so under `min_cluster_size`, until about
12 m.

**The replay (CPU, no GPU).** In Python, on r1's record (NAS, 118's step 1 run), per frame of
`/perception/obstacle_segmentation/pointcloud`:
- put the cloud into the map frame by `/localization/kinematic_state`, nearest in time;
- apply the three steps above as the source does them, against Town01's `pointcloud_map.pcd`
  at the run's dataset revision. The dynamic map loading is not reproduced: its 150 m radius
  holds the boulder's surroundings at all times;
- count the boulder's points after each step (within 1.0 m of x 400, y 1.625, as step 1 did),
  and whether a cluster of at least 10 points forms there.

The fidelity check comes first: the replayed clustering must agree with the recorded
`clustering/clusters` on whether the boulder has a cluster in at least 90 % of the frames from
40 m to 5 m. Otherwise the replay is not faithful, and nothing below is read from it.

**Predictions, before any replay:**
- (a) Fidelity holds: at least 90 % frame agreement, and the replay's first cluster at 12.3 ±
  1.0 m.
- (b) H3, the compare-map filter: from 31 m to 12 m it removes at least 70 % of the boulder's
  downsampled points. Every point that survives is at least 0.25 m above the road (the map's
  centroid z at that spot).
- (c) The count that fails is `min_cluster_size`. Beyond 12 m, the surviving points number under
  10 in every frame, and from 10.8 m at least 10 in every frame.
- (d) Counterfactuals, in the replay only (no stack changed):
  - with the compare-map filter off (the downsample alone), the first cluster comes at 20 m or
    more;
  - with `downsize_ratio_z_axis` 0.3 (a 0.15 m vertical tolerance), at 20 m or more;
  - with `min_cluster_size` 3 and the filter as it is, between 12 and 20 m.
- How sure: about 60 % for (b) and (c) together. The other candidates: the map's road centroids
  sit higher or lower than Isaac's road, so the cut is not 0.3 m above the true surface; or the
  boulder stands where the map has no road voxel at all, and then H3 is wrong.

The validator's second delay (from 12.3 m to 8.8 m) is not in this step. It is read after,
from the same replay's clusters, as its own prediction.

**The first replay was invalid: the wrong map (2026-11-27, recorded; nothing read from it).**
The replay above assumed Town01's `pointcloud_map.pcd`. r1 ran on `fixture_c6b`, a map on 118's
host (`isaac_c6e3_r181`'s testbench: `path: /mnt/renegade/aeon/isaac-ex/c6e/maps/fixture_c6b`),
which I did not check first.

The fidelity check caught it. Against Town01's map, the replay removed 100 % of the boulder's
points at every range and formed no cluster, while the record has clusters from 13.1 m. That
is 0.780 frame agreement against the 0.90 required. So nothing is read from it, as planned.

118 has been asked to put fixture_c6b's map (the version r1 used) on the NAS. The replay is run
again on it, with the predictions above unchanged.

## Step 2's result: the replay on fixture_c6b's map (241, 2026-11-27, after the predictions above)

The map is r1's, unchanged: 118's NAS copy `home/2026-11-27 fixture_c6b map for 181 (118)/`, with
SHA256SUMS checked. The scripts, the extracted window and every output are on the NAS:
`home/2026-11-27 issue 181 replay (241)/` (`extract181.py`, `replay181.py`, `replay_out.txt`).
It covered 173 frames from 40 m to 5 m, and each replay took about 3 s on CPU. Point counts are
those within 1 m of the boulder in xy.

| range | frames | non-ground (max) | after 0.1 m downsample (max, mean) | after compare-map (max, mean) | cluster, replay / recorded |
|---|---|---|---|---|---|
| 31 to 40 m | 43 | 2 | 2, 0.1 | 2, 0.1 | 0 / 0 |
| 20 to 31 m | 53 | 8 | 8, 3.0 | 4, 1.7 | 0 / 0 |
| 12 to 20 m | 38 | 19 | 16, 7.3 | 12, 6.1 | 4 / 4 |
| 10 to 12 m | 9 | 22 | 18, 13.7 | 17, 13.1 | 8 / 8 |
| 5 to 10 m | 30 | 128 | 42, 23.9 | 37, 21.4 | 26 / 26 |

The counterfactuals change one parameter each, in the replay only:

| setting | first cluster at the boulder | clusters a frame, whole cloud (mean, max) |
|---|---|---|
| as run (`min_cluster_size` 10, compare-map on) | 13.1 m | 0.3, 2 |
| compare-map off | 14.6 m | |
| `downsize_ratio_z_axis` 0.3 (0.15 m vertical) | 14.6 m | |
| `min_cluster_size` 5 | 18.8 m | 2.1, 4 |
| `min_cluster_size` 3 | 27.3 m (every frame from 20 m) | 4.5, 7 |
| `min_cluster_size` 3, compare-map off | 27.9 m | |
| `min_cluster_size` 1 | 31.7 m | 7.4, 13 |

**Against the predictions:**
- (a) Fidelity: **held**. The replay agrees with the recorded clusters in 173 of 173 frames
  (1.000), and both have their first cluster at 13.1 m. (Step 1's 12.3 m used another nearness
  rule.)
- (b) H3, the compare-map filter: **FAILED**. From 31 m to 12 m it removes 0 to 43 % of the
  boulder's downsampled points, not the 70 % or more predicted. With it off, the first cluster
  moves only from 13.1 to 14.6 m. It is a small second factor, not the cause.
- (c) The count that fails is `min_cluster_size`: **held, with exceptions**.
  - Beyond 12 m, 4 of 134 frames reach 10 points (max 12), and those are exactly the 4
    clustered frames from 12 to 20 m.
  - From 10.8 m, 4 of 33 frames stay under 10.
  - The binding limit is the boulder's lidar returns against 10 points. At 20 to 31 m it gets
    3.0 downsampled points a frame on average, and the 0.1 m downsample barely matters there
    (8 non-ground, 8 downsampled at most).
- (d) Counterfactuals: **FAILED as predicted, the other way**.
  - Compare-map off and the 0.15 m vertical tolerance give 14.6 m, not 20 m or more.
  - `min_cluster_size` 3 gives 27.3 m, beyond the 12 to 20 m predicted.

**Named:** `min_cluster_size: 10` of `voxel_grid_based_euclidean_cluster.param.yaml`, counted in
points after the 0.1 m downsample and the compare-map filter. A 0.35 m boulder gets fewer than
10 such points until about 12 m on this lidar. The compare-map filter takes off a further 1.5 m
at most.

**Not shown, and the next questions:**
- *The validator.* It drops the cluster again from 12.3 m to 8.8 m. `min_points_num` 10 is
  counted on the same compare-map filtered cloud. So lowering `min_cluster_size` alone would
  likely move the limit to the validator, at about the same 12 m. That is a prediction for the
  next step, not a finding.
- *The cost.*
  - The whole-cloud cluster counts above are on a fixture with a bare road. Which of the extra
    clusters at 3 or 5 points are spurious is not judged here.
  - Nor what tracking makes of them.
  - Nor whether any change belongs in the scensim profile rather than stock Autoware. That is
    133's and the user's call.
- 118's issue 177 run records both filtered clouds. That checks the replay's per-stage counts
  directly, with no replay.

## Step 3: the validator at a lower min_cluster_size, and the extra clusters judged (241, 2026-11-27; plan and predictions, before any replay)

133 asked, CPU only:
- (a) from what range the boulder survives to the validator's output with `min_cluster_size` 3
  and 5;
- (b) for each setting, which of the extra whole-cloud clusters are spurious, and where they sit
  relative to the ego's path ("a lower min_cluster_size that brakes for road texture is no
  fix").

A profile change is the user's decision, after this step.

**What the replay adds, from the 0.48.0 source:**
- *Shape estimation for UNKNOWN* (`ConvexHullShapeModel`): the polygon is OpenCV's convex hull
  of the cluster's points, in millimetres relative to their centroid.
- *The validator, as the profile loads it* (autoware_launch's
  `obstacle_pointcloud_based_validator.param.yaml`, `using_2d_validator: true`). It is
  `Validator2D`:
  - it takes the compare-map filtered cloud's points within the polygon's radius;
  - it counts those inside the polygon by PCL's `CropHull` in 2D. The validator hands it one
    polygon per prefix of the hull's vertices, and a point counts as inside if it is inside any
    of them, by PCL's ray-crossing rule;
  - it keeps the object only if that count is **greater than** clamp(round(800 / distance), 10,
    10) = 10, so 11 points or more.
- The replay drops the low-height crop box. The profile's `use_low_height_cropbox` is false
  (`tier4_perception_component.launch.xml`), and step 2 applied it. It changed nothing at the
  boulder, but it may change the whole-cloud counts.
- The profile's compare-map filter loads its map statically (issue 029). `is_close_to_map` is
  then `is_close_to_neighbor_voxels`, as replayed.

**Ground truth.** The fixture's rocks are placed as r1's world placed them: scensim_isaac_world
at 3a948eea (r1's), `road_layer.load` of the map's `road_detail.yaml`, then `rocks.place` per
16 m tile over x 330 to 420 (NAS `gt181.py`, `gt_rocks.npy`).
- There are 55 rocks. The boulder's top is at 0.317 m (map z).
- The next largest are 0.14 m tops, at y -4.66, 4.65 and -4.55: shoulder, run-off and ditch.
  No other rock is within 2 m of the lane's centre (y 1.625).
- A cluster is *spurious* when no rock's centre is within 1.0 m of its centre in xy (133's
  rule).
- Where it sits: its lateral distance from the ego's path (y 1.625):
  - *in the path*: under 1.2 m, half the car's width plus about 0.25 m;
  - *beside it*: 1.2 to 3 m;
  - *off the road*: beyond 3 m.

**Fidelity first.** With the settings as run (`min_cluster_size` 10), the replayed validator must
agree with r1's recorded `clustering/validation/objects` on whether the boulder has an object in
at least 90 % of the frames from 40 m to 5 m. The record's first is 8.8 m by step 1's rule.
Otherwise nothing below is read.

**Predictions, before any replay:**
- (a1) Fidelity holds, the first validated object at 8.8 ± 1.5 m.
- (a2) Lowering `min_cluster_size` alone hardly moves the validated boulder. With 5 and with 3,
  its first validated frame is within 2 m of the as-run one. The validator needs 11 points
  inside the hull of the same filtered cloud, and points on the hull may not count, so it stays
  the limit at about 9 to 11 m.
- (b1) The extra clusters at 3 and 5 are mostly spurious: at least 80 % of the non-boulder
  clusters have no rock within 1 m. They sit *off the road*, at the verges and the ditch's
  slopes, not in the path. In the path, beside the boulder, there is at most 1 frame in 10 with
  a spurious cluster.
- (b2) The validator removes almost all of them, at least 90 % of the spurious clusters at 3,
  because they hold under 11 points.
- So lowering `min_cluster_size` alone is no fix, though not for 133's road-texture reason. The
  validator would hold the boulder back about as now. A fix would have to move both thresholds,
  and then (b) decides whether the road texture passes too.

How sure: (a2) about 70 %, (b1) about 60 % (verge geometry is the doubt), (b2) about 70 %.

## Step 3's result (241, 2026-11-27, after the predictions above)

`replay181v.py` on `r1_window2.npz` (step 2's window, now with the recorded validator output),
`gt_rocks.npy`, NAS `home/2026-11-27 issue 181 replay (241)/`. 173 frames from 40 m to 5 m. Each
row below is the boulder's frames with a cluster / a validated object.

| min_cluster_size | first cluster | cluster 20-31 / 12-20 / 10-12 / 5-10 m | first validated | validated 12-20 / 10-12 / 5-10 m |
|---|---|---|---|---|
| 10 (as run) | 13.1 m | 0/53, 4/38, 8/9, 26/30 | 9.6 m | 0/38, 0/9, 22/30 |
| 5 | 18.8 m | 0/53, 24/38, 9/9, 26/30 | 9.6 m | 0/38, 0/9, 22/30 |
| 3 | 27.3 m | 14/53, 38/38, 9/9, 26/30 | 9.6 m | 0/38, 0/9, 22/30 |

The other clusters (not the boulder), each judged against the fixture's rocks:

| min_cluster_size | clusters (a frame) | spurious (no rock within 1 m) | in the path / beside / off the road | validated |
|---|---|---|---|---|
| 10 | 0 | 0 | 0 / 0 / 0 | 0 |
| 5 | 4 (0.02) | 0 | 0 / 0 / 4 | 0 |
| 3 | 222 (1.28) | 141 (64 %), in 108 frames | 0 / 0 / 222 | 0 |

**Against the predictions:**
- (a1) Fidelity: **held**. The replayed validator agrees with the recorded
  `clustering/validation/objects` in 173 of 173 frames (1.000), both first at 9.6 m. (Step 1's
  8.8 m used its own nearness rule.)
- (a2) The validator stays the limit: **held**. With `min_cluster_size` 5 and 3, the boulder is a
  cluster from 18.8 m and 27.3 m, but its first validated frame stays at 9.6 m, in exactly the
  same frames. The validator's count of more than 10 points inside the hull decides it.
- (b1) The extra clusters at 3 and 5 are mostly spurious and off the road:
  - **failed in part** on the share: 64 % spurious at 3, not 80 % or more. At 5, none of the 4
    is spurious; each lies within 1 m of a shoulder or ditch rock;
  - **held** on where they sit: all 226 are more than 3 m from the path, at the verges and
    ditches, none in it or beside it.
- (b2) The validator removes them: **held**. 0 of 226 are validated, the spurious ones included.

**A correction to step 2.** Its whole-cloud cluster counts (0.3, 2.1, 4.5 and 7.4 a frame) were
wrong. That replay applied the compare-map filter only within 15 m of the boulder, a shortcut
for speed, so the rest of the cloud reached the clustering unfiltered. Step 3 filters everything
within 60 m. The counts above replace those. Step 2's per-boulder results are unaffected,
because the boulder was inside the 15 m.

**So, for the decision (the user's, through 133):**
- Lowering `min_cluster_size` alone does nothing for the stop: the validated object, and so
  everything after it, is unchanged at 9.6 m.
- Lowering both `min_cluster_size` and the validator's `min_points_num` / `max_points_num` for
  UNKNOWN is the change that could move it. Its cost here is the 141 spurious off-road clusters
  at `min_cluster_size` 3, if the validator lets them through.
- Whether it does, at which validator threshold, is the next replay, and it is cheap. It is not
  run here, because no prediction for it was committed first.
- This is one fixture with a bare road and verge rocks. Road texture in the path did not make a
  cluster at any setting, but the fixture's carriageway has roughness only (`gd0` 1e-12). A
  rougher road may.

## Step 4: both thresholds, a grid, and a road with features (241, 2026-11-27; plan and predictions, before any replay)

133 asked for a grid: `min_cluster_size` {10, 5, 3} × the validator's UNKNOWN `min_points_num`
{10, 5, 3}, with `max_points_num` set equal, since the threshold is clamp(round(800 / d), min,
max). For each cell: the boulder's first validated range, and the validated spurious objects
(count, and distance from the path). Then a row on a rough road, if a cheap one exists.

**The rough-road row.** No record of a road with `gd0` > 0 holds the non-ground cloud. C6d's
Haruna runs record only the final objects. C6e3's a1 run on `fixture_c6a` does: the non-ground
cloud and the state, 5 MB (NAS, C6e3's folder). Its carriageway is smooth too (`gd0` 1e-12), but
it carries the features 133 named:
- cleats of 5, 10 and 15 cm;
- an 8 cm pothole;
- 30 m of washboard;
- no rocks.

So on c6a every validated object is spurious: a stop for the road itself. Its map
(`pointcloud_map.pcd`) is on 118's host. 118 has been asked to put it on the NAS, and the row
waits for it.

**Predictions, before any replay.** The boulder's filtered points per frame, mean (max), were:
1.7 (4) at 20 to 31 m, 6.1 (12) at 12 to 20 m, 13.1 (17) at 10 to 12 m. The validator needs more
than `min_points_num` of them strictly inside the hull, and the hull's own vertices tend not to
count. So:

| first validated (m) | validator 10 | validator 5 | validator 3 |
|---|---|---|---|
| min_cluster_size 10 | 9.6 (as run) | 12 to 13.1 | 13.1 (the cluster's own limit) |
| min_cluster_size 5 | 9.6 | 11 to 15 | 13 to 19 |
| min_cluster_size 3 | 9.6 | 11 to 15 | 13 to 19 |

The validator's column decides each row except where the cluster's own minimum is the stricter
one. No cell reaches the 27.3 m at which the boulder first clusters at 3.

Spurious validated objects on fixture_c6b:
- none at `min_cluster_size` 10 or 5, whatever the validator;
- at 3, with validator 5, at most 5;
- at 3, with validator 3, at most 30 % of step 3's 141 spurious clusters;
- every one more than 3 m from the path.

fixture_c6a (as soon as its map is there):
- with the settings as run, no validated object, as C6e3 saw;
- at `min_cluster_size` 3 with validator 3, validated objects in the path at the 10 and 15 cm
  cleats, and none at the washboard or the pothole.

That last part is the least sure (about 40 %). A cleat is a step across the road whose top the
compare-map filter may or may not remove, depending on how high it stands over the map's road.

How sure of the table: about 60 % for each cell's range.

## Step 4's result (241, 2026-11-27, after the predictions above)

`replay181g.py`, self-contained, the same chain as step 3 with the validator's threshold V as a
parameter: an object is kept with more than V points inside its hull. The inputs:
- fixture_c6b: r1's window, 173 frames, 40 to 5 m, judged against `gt_rocks.npy`;
- fixture_c6a: C6e3's a1 run, the whole run (2909 frames; 118's NAS copy of the map, SHA256SUMS
  checked).

Outputs are in NAS `home/2026-11-27 issue 181 replay (241)/grid_out.txt`. The as-run cell
reproduces step 3 (9.6 m). a1 recorded no validator output, so c6a has no fidelity check of its
own.

The boulder's first validated range, fixture_c6b:

| min_cluster_size \ validator | 10 | 5 | 3 |
|---|---|---|---|
| 10 (as run) | 9.6 m | 12.1 m | 12.5 m |
| 5 | 9.6 m | 12.1 m | 12.5 m |
| 3 | 9.6 m | 12.1 m | 12.5 m |

The validated spurious objects:

| min_cluster_size / validator | fixture_c6b (path, beside, off) | fixture_c6a (path, beside, off) |
|---|---|---|
| 10 / 10 (as run) | 0 (0, 0, 0) | 11 (0, 0, 11) in 11 of 2909 frames |
| 10 / 5, 10 / 3 | 0 | 17 (0, 0, 17) |
| 5 / 10, 3 / 10 | 0 | 11 (0, 0, 11) |
| 5 / 5, 3 / 5 | 0 | 29 (0, 0, 29) in 24 frames |
| 5 / 3, 3 / 3 | 0 | 36 (0, 0, 36) in 28 frames |

No setting validated an object in the path or beside it, on either fixture: not at the cleats,
the pothole or the washboard. Every spurious object is more than 3 m from the path.

**Against the predictions:**
- The validator's column decides, and the rows do not matter: **held**. Every row is the same;
  `min_cluster_size` never binds once the validator needs more points than it.
- The ranges:
  - validator 10: 9.6 m in every row, **held**;
  - validator 5: 12.1 m, inside the 12 to 13.1 and 11 to 15 m predicted, **held**;
  - validator 3: 12.5 m, **FAILED** against 13.1 (row 10) and 13 to 19 m (rows 5 and 3).
- The boulder's points are too few and too spread for a hull to hold more than 3 of them
  inside before about 12.5 m. No cell reaches 13 m, against the 27.3 m at which it first
  clusters.
- fixture_c6b's spurious objects: **held**. There are none at any setting. Step 3's 141
  spurious clusters at `min_cluster_size` 3 hold 3 points inside their hulls at most.
- fixture_c6a:
  - as run, no validated object: **FAILED in its letter**. The replay validates 11 objects at
    this stage, all off the road, and C6e3's "no object" was read from the final objects,
    after the lanelet filter and tracking. In the path: none, as C6e3 saw;
  - at 3 / 3, objects in the path at the 10 and 15 cm cleats: **FAILED**. No object in the path
    at any feature, at any setting.

**For the decision:**
- The two thresholds together move the boulder's first validated range from 9.6 m to at most
  12.5 m. At r1's 4.2 m/s that is 2.9 m, about 0.7 s more, with no spurious object in the path
  on either fixture.
- They cannot reach the 27 to 31 m at which the boulder's points first appear: the hull rule
  and the lidar's few returns on a 0.35 m rock set the limit, not the thresholds.
- Whether 0.7 s is enough to stop is 182's question, not this one.

## The decision and the change (the user via 133, 2026-11-27; a plan, before any code)

**The user's decision:** the validator's UNKNOWN threshold 5 in scensim's profile, so the
boulder is validated from about 12.1 m instead of 9.6 m (step 4's cell). Then issue 182.

**Why both `min_points_num` and `max_points_num`.** The validator's threshold is
clamp(round(`min_points_and_distance_ratio` / d), `min_points_num`, `max_points_num`)
(`Validator::getThresholdPointCloud`), with ratio 800 and min = max = 10 upstream:
- today the clamp returns 10 at every distance;
- with `min_points_num` 5 alone, 800 / d is still above 10 for every object nearer than 80 m,
  so the clamp returns `max_points_num`, 10, and nothing changes where it matters;
- step 4 set both to 5 ("`max_points_num` set equal"). With both at 5, the clamp returns 5 at
  every distance under 160 m.

So the change is UNKNOWN `min_points_num` 5 **and** `max_points_num` 5, the other classes and the
ratio as upstream. It is the same decision, expressed so that it takes effect (133, 2026-11-27).
An earlier summary to 133 named only `min_points_num`; that was imprecise.

**The change (autoware_sim_vehicle, Autoware 1.5.0 only, as 190's tracker argument):**
- `scripts/sync_perception_component.sh`, its sixth change:
  - the profile's copy of autoware_launch's `obstacle_pointcloud_based_validator.param.yaml`,
    upstream's but for those two UNKNOWN values, generated and checked like the others;
  - the perception component passes the file `obstacle_pointcloud_based_validator_param_path`
    names, whose default is that copy.
- `autoware.launch.xml` declares the argument, defaulting to the copy, and passes it to the
  component. A testbench can point it at upstream's file to compare.
- Tests (`test/test_profile.py`):
  - the copy's UNKNOWN `min_points_num` and `max_points_num` are both 5;
  - the rest equals upstream's;
  - the default path is the copy in the launch and in the component, and it reaches the
    validator.
- Then the pin chain, each step through `just gate` and with 133's OK before each push: asv,
  then acb's, aib's and siw's `deps/`, then scensim. It lands after 177, 190's batch, gc-args and
  this issue's docs.

**Live confirmation (118, after its 177 check):** C6e3's c6b on the new pins. Prediction: the
boulder's first validated range is about 12.1 m (±1.5 m), against r1's 8.8 m by step 1's rule
(9.6 m by step 3's).
