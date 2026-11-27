# 198: a course map's road in the point cloud is mostly the terrain under the road

**Status:** open; plan only (241, 2026-11-27, batch P, for 133). **Severity:** medium. The
points the map holds for the road lie 0.10 to 0.13 m below the surface the lidar sees, on most
of the lane. Any check of height above the map is blind below that (issue 180's option 3), and
NDT localizes against a road that is not there. **Found:** 2026-11-27, 241, in issue 180 step 2:
the lane-only height-above-map check made false objects at three flat spots of
`fixture_c6b`'s lane.

## What happens

On `fixture_c6b`'s `pointcloud_map.pcd` (sha256 32bab6cc..., the map of issues 180 to 182), the
lane is |y - 1.62| < 1.75 m, x 0 to 500:
- 33218 map points. Their heights fall in two bands only: 23794 at z -0.16 to -0.12 (median
  -0.160), and 9424 at -0.08 to 0 (around -0.02). None lie between.
- The live road, from the r180 run's raw cloud by the truth's pose, is at z -0.024 to -0.059 at
  the spots checked.
- Of the lane's 0.2 m cells, **71.6 % hold only the low band** (top z below -0.12), and 26.3 %
  of its 0.5 m cells do.

## Why: the builder step

`scensim_isaac_world.course.maps.point_cloud` (siw, roadmap 086 C7) builds the cloud as follows:
1. `_sample_terrain`: points on the terrain grid's triangles, everywhere in the grid, the
   ground under the road included;
2. `_sample_ribbon`: points on the road ribbon's quads;
3. any extra parts, concatenated in that order, terrain first;
4. one point kept per 0.2 m voxel: `np.unique(..., return_index=True)`, the **first**
   occurrence.

The terrain under the road sits about 0.13 m below the ribbon (z about -0.16 against about
-0.03). Both fall in the same 0.2 m voxel (floor(z / 0.2) = -1 for both), and the terrain's
point comes first, so the voxel keeps the terrain and drops the road. Where the terrain's
jittered samples miss a voxel, the road's point survives. That is the 72 / 28 split. The
lidar never sees that terrain: the ribbon covers it.

## The plan (before any code)

1. **Survey, CPU only.** For every map built by `course.maps` (the course and fixture maps:
   fixture_c6a, fixture_c6b and the others under isaac-ex; the NTU twin's if it is built the
   same way), measure the share of road cells, 0.2 m and 0.5 m, whose top point is the terrain
   under the ribbon. List the maps a fix must rebuild and where each lives (local, NAS, HF).
2. **The fix, in siw `course/maps.py`.** `_sample_terrain` drops a sample whose xy lies under
   the road ribbon (inside a ribbon triangle's xy footprint, with the ribbon above it), since
   the lidar cannot see it. The voxel thinning stays.
   - Not chosen: keeping the highest point per voxel. It hides the defect without removing the
     samples, and it would still mix the two surfaces near the ribbon's edges.
3. **Tests (siw).**
   - A synthetic course with a terrain grid 0.13 m under a flat ribbon: no cloud point under
     the ribbon's footprint below the ribbon, and the road's 0.2 m cells all within 0.01 m of
     the ribbon.
   - The terrain beside the ribbon is kept.
   - A ribbon over a dip (terrain above the ribbon nowhere) is unchanged.
4. **Rebuild** the affected maps. The NDT map changes, so a dataset map goes through the usual
   HF review: diff summary to 133, upload only on the user's OK.
5. **Re-measure, CPU only:**
   - (a) the survey on the rebuilt maps;
   - (b) issue 180's `hmap180.py` on the r180 record against the rebuilt fixture_c6b;
   - (c) issue 180's replay at the as-run settings, which should be unchanged.
6. **One live run on the rebuilt fixture_c6b**, for batch L (243), not here. Does the EKF's
   steady 2.3 cm-low height on c6b (issue 180 step 2) move? A localization question, so it is
   L's.

## Predictions (before the survey or any code)

1. Every map built by `course.maps` with a terrain grid under its road shows the defect. 50 to
   80 % of its road's 0.2 m cells hold only the terrain.
2. After the fix: 0 % on every rebuilt map, and the road's cells within 0.01 m of the ribbon.
3. On the rebuilt fixture_c6b, `hmap180.py` at h 0.08, N 3 makes false would-be objects on
   the carriageway in under 2 % of r180's frames (85 % today). The rock becomes a would-be
   object at about 9 m from the bumper, as today (9.1 m).
4. Issue 180's replay at the as-run settings is unchanged on the lane: no rock point, no false
   object. The ground filter does not use the map, and compare-map's 0.3 m band covers both
   layers.
5. Batch L's (stated here, judged there): with the road where the road is, the EKF's height
   bias on c6b falls under 1 cm.

Issue 180's option 3 waits for this fix (180's decision).

## The survey, the fix and the offline re-measure (241, 2026-11-27)

**The survey** (`survey198.py`, NAS `home/2026-11-27 issue 198 rebuilt fixture maps (241)/` and
the scratch scripts beside 180's).
- Road cells are 0.2 m cells inside any lanelet.
- A cell is terrain-only when its top point is more than 0.06 m below the highest top within
  1 m (a cell that kept the ribbon's point). The offset is that difference.

| map | where | pointcloud_map.pcd sha256 | terrain-only | offset median (p5 to p95) | left / right half |
|---|---|---|---|---|---|
| fixture_c6b | local (118's isaac-ex; NAS copy) | 32bab6cc... | 71.5 % | 0.140 m (0.115 to 0.147) | 71.2 / 71.9 % |
| fixture_c170 | local (243's project; NAS copy) | 9cc1a29f... | 38.1 % | 0.080 m (flat) | 37.8 / 38.4 % |
| haruna | **published**, HF haruna-tsukuba-courses at b12857ee (140 tiles) | a54e0a3b... (the tiles together) | 72.0 % | 0.131 m (its p95 is the cut banks over the road's edge) | 73.2 / 70.8 % |
| tsukuba | **published**, same revision | 8112a0c5... | 61.3 % | 0.084 m (0.080 to 0.102) | 61.2 / 61.4 % |

- No map is lopsided across the lane: every 0.5 m band of lateral offset is within 4 points of
  its map's share.
- So the defect lowers the road under a share of the lane, evenly. It does not push it to one
  side.
- carla-town-autoware-maps (the CARLA towns) is not built by `course.maps` and is not
  affected. The other fixtures (c5, c5c, c5d2, c6a, c6c) are built the same way and are
  local, so they are expected to be affected, but they are not measured here.

**The fix** (siw `i198`: the test deaa640a, then the fix 9bfd1b10, on siw main 1ade51c).
- `course.maps.point_cloud` now drops a terrain sample that lies inside one of the ribbon's
  triangles (by xy) and below the ribbon there.
- The candidates come from a k-d tree of the triangles' centroids. k is bounded exactly by the
  most centroids any centroid has within twice the largest triangle's reach, so no containing
  triangle is missed. The work is done in blocks.
- The test fails 2 of 4 before the fix (2194 terrain points under the ribbon; road cells 0.13
  m low) and passes after.
- siw's suite: 547 tests OK, pyflakes clean.

**The rebuilt fixtures, offline.** `python3 -m scensim_isaac_world.course <course.yaml> <dir>
centreline geometry record maps` with the code before the fix rebuilds each published PCD
byte for byte (c6b 32bab6cc, c170 9cc1a29f). So the fix is the only difference.

| map | PCD after the fix | terrain-only | points | road cells with a point |
|---|---|---|---|---|
| fixture_c6b | aea7dc9d... | 0.0 % | 680009 → 650109 | lane 33217 → 20700 (0.2 m cells) |
| fixture_c170 | 2658430d... | 0.0 % | 801548 → 735818 | 72874 → 45126 of 95968 |

- The lanelet map and the projector files are unchanged.
- The road now holds only the ribbon's own samples: one per 0.2 m voxel at 0.25 m sampling.
  So about half the road's 0.2 m cells have a point (76 % to 47 % on c170). That is a second
  difference beside the height, recorded for batch L. A denser ribbon sample would separate
  the two, and is a follow-up, not this fix.

**Issue 180's lane check against the rebuilt c6b** (`hmap180.py`, r180's record):

| h | N | rock first detected (bumper) | first would-be object | false on the carriageway, old map → rebuilt |
|---|---|---|---|---|
| 0.05 | 3 | 14.7 m | **11.3 m** | 92 % → **0 %** |
| 0.08 | 3 | 12.2 m | 9.1 m | 85 % → 0 % |
| 0.10 | 3 | 9.3 m | 8.8 m | 72 % → 0 % |
| 0.12 | 3 | 9.1 m | 6.1 m | 0 % → 0 % |

- The rock's ranges are the same as on the old map, since its points are far above either
  layer.
- Every false object at h 0.10 and below was the map's. With the road where it is, the check
  at h 0.05 makes the rock an object at 11.3 m from the bumper, past the 7 m planned-stop bar,
  with none on the carriageway in this run.
- Issue 180's replay at the as-run settings is unchanged on the rebuilt map: no rock point and
  no false object.

**Against the predictions.**
1. "50 to 80 % on every map": held for c6b (71.5), haruna (72.0) and tsukuba (61.3). FAILED for
   c170 (38.1 %). Its terrain sits 0.08 m below the road, not 0.13, so fewer of its terrain
   samples share a voxel with the ribbon's.
2. 0 % after the fix: held on both rebuilt maps. "Within 0.01 m of the ribbon" held in the
   test. On the real maps the lane's top spans -0.064 to -0.002 m (p5 to p95 on c6b), which is
   the crown across the lane, not a second layer.
3. h 0.08, N 3: held. False objects 0 % (bar 2 %), the rock at 9.1 m (about 9).
4. Held: 180's as-run replay unchanged.
5. Batch L's, not judged here.

**What remains.**
- The landing: siw 9bfd1b10 after 243's L2 pin, then its scensim pin, gated.
- The published haruna and tsukuba maps are rebuilt only on the user's OK (a dataset change).
- The other local fixtures are rebuilt where they live.
- Issue 180's option 3 can now plan on h 0.05 to 0.08 rather than 0.12.
