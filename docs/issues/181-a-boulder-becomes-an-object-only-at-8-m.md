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
