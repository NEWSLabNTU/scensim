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
