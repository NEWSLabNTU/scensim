# 170: on Isaac, localization sits 0.066 m across the track from the truth, and 11 to 14 mm above it beyond issue 167

**Status:** open; yours later (133, 2026-11-25). **Severity:** to be shown. The across bias is
about half of smooth haruna_down's pose error p95 (0.12 m). **Found:** 2026-11-25, scensim
118, 086 C6e2 and issue 167 (numbered by 133).

## What is the case

Two open quantities on Isaac's haruna_down, measured offline from the runs' records
(`/localization/kinematic_state` against the truth trace `ego.csv`, above 1 m/s;
`c6e2/along.py`, `c6e/locz.py`):

1. **Across the track: -0.065 to -0.071 m** (localization right of the car, with the y axis
   left) in all six C6e2 runs, with motion BVH off and on. Issue 167's probe shows it is not
   the lidar's mount: the lidar prim has no lateral offset, and the rig's mount equals the
   sensor kit's extrinsics (x 0.9, y 0, z 2.0, roll -0.001, pitch 0.015, yaw 1.5386 rad).
2. **NDT's z: +0.022 to +0.026 m above the truth** before issue 167's fix. The 36.22 mm offset
   predicts a bias of its own size, and 11 to 14 mm of the measured one is not accounted for.
   167's reach check on the fixed aib measures what is left.

## Candidates (none measured)

- the truth trace's origin: which point of the body `ego.csv` reports, against Autoware's
  base_link (the rear axle's middle on the ground);
- the map's cloud against the road: the course builder's sampling of the road and its
  verges into `pointcloud_map.pcd`, and the lanelets' frame;
- the vehicle's base_link under the suspension's sag, against Autoware's static vehicle
  model (for z);
- NDT's roll and pitch taking part of an offset on a crowned road (for z and across);
- the sensor kit's yaw of -0.0364 rad (sensor_kit_base_link), which is in both the rig and the
  TF, so it should cancel. Checked only on paper.
