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
