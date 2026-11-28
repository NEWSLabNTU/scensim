# 201: the lane check places the lidar cloud without the car's pitch and roll

**Status:** open; plan only (241, 2026-11-28, for 133). **Severity:** high for any road with a
grade: the check marks the road itself as an obstacle, and obstacle_stop stops for it. On a flat
road it shows only while the car pitches (a hard stop). **Found:** 2026-11-28, 241, writing issue
180's clean-lap brief: reading `obstacle_points`, then the step B v2 records.

## What happens

`lane_height_check` (asv `autoware_sim_profile/scripts/lane_height_check`, issue 180's I2) takes
the raw cloud in `base_link` and places it in the map with the EKF's x, y, z and **yaw only**
(`on_pose` keeps `(x, y, z, yaw)`; `obstacle_points` rotates by yaw and adds z). `base_link`
tilts with the car. With the car pitched nose-down by theta (ROS pitch positive), a road return
r ahead of base_link is placed about r * sin(theta) above where it is. The reference is the map's
road at that xy, so the return is an obstacle point once r * sin(theta) > h (0.098 m on the Model
3): beyond 0.098 / sin(theta) ahead. Nose-up, a real obstacle must stand r * sin(theta) higher
before it counts. Roll does the same across the lane.

| nose-down pitch | road counted as obstacle from |
|---|---|
| 0.19 deg | 30 m (the check's far limit) |
| 0.56 deg | 10 m |
| 1.12 deg | 5 m |
| 3.6 deg (haruna_down's median) | 1.6 m (the check starts at 1 m) |

**Seen in step B v2's records** (fixture_c6b, flat; N1, `pitch180.py`, NAS `home/2026-11-28 issue
180 step B v2 reading (241)/`): as the car settled at its emergency stop, the truth's pitch went
to +0.52 deg nose-down for about 0.2 s. The node's obstacle points went from 66 (the boulder)
to 709 and 836 in 14 to 15 detections, and one frame published 836 points to obstacle_stop: road
beyond about 11 m. The car was already stopping for the boulder, so nothing changed here.

**On Haruna** (118's issue 195 H runs on the rebuilt map, rb1 and rb2): haruna_down falls 87 m
in 1468 m, and the truth's pitch while moving is 2.50 to 4.54 deg nose-down (p1 to p99), median
3.59. The EKF agrees within 0.09 deg (p99). So with the check on, every road return from about
1.6 m ahead to 30 m is an obstacle point for the whole course.

**Why the test missed it.** `test_a_grade_and_a_crown_are_not_obstacles` feeds a cloud that
already follows the 10 % grade, with the pose level: a car standing level on a sloped road,
which cannot happen. A real car on that grade pitches with it, and its lidar sees the road
ahead about level.

## The plan (for 133; nothing run)

1. A test first, failing today: the same 10 % grade with the car pitched on it (the cloud the
   lidar would give, in base_link, and the pose's quaternion with the pitch): no obstacle point;
   the 15 cm rock on that grade still one. The same for a roll on a cross slope.
2. The fix: keep the EKF's full orientation in `on_pose` and place the cloud with the full
   rotation (a 3 x 3 matrix from the quaternion; numpy only, as the node is).
3. Step B v2's N arm on fixture_c6b is unaffected in its outcome (flat road; the stop was
   already decided), so it stands. Issue 180's clean-lap brief runs N with the fix.
