# 181: a 35 cm boulder becomes an object only at 8 m although its points show from 31 m

**Status:** open; plan later (133, 2026-11-25). **Severity:** to be judged in the plan: on
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
