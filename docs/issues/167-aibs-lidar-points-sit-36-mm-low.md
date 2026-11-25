# 167: aib's lidar points sit 36 mm below where the rig puts the lidar

**Status:** fixed: aib bb2283f (aib main), checked on C6e1's stops; landing in scensim by land_pin. **Severity:** to be
shown. It is a constant height offset of every Isaac lidar cloud in its own frame; the judged
pose error is horizontal. **Found:** 2026-11-25, scensim 118, 086 C6e1 (numbered by 133).

## What happens

In 086 C6e1, aib's Model 3 lidar stood still at six stops on fixture_c6a, without a car or
Autoware. Its prim was placed where aib's mount puts it, and its annotator's points were taken
into the map frame by that prim's pose. Every return on the road came out 36.22 mm below the
road: the median is -36.22 mm at every stop and in every range band from 2 to 80 m, with no
spread, and 6 % of the returns sit at -30.2 mm instead (not explained). The render mesh's own
heights equal the road layer's truth (0.000 mm, `meshcheck.py`, offline), so the offset is in
the points, not in the road. C6e1's record: NAS "2026-11-25 086 C6e1 lidar on the road layer
(118)".

aib builds the lidar with `RtxLidar.create(f"{root}/lidar", config="OS1",
variant="OS1_REV7_128ch20hz1024res")` under an Xform at `root`, which `before_substep` puts at the
rig's mount each substep (`aib.isaac.sensors.Lidar`). It publishes the annotator's points as
they come, in the rig's `top` frame, and the vehicle's TF puts `top` at the rig's mount.

**Hypothesis:** the points are measured from the emitter, which Isaac's OS1 places 36.18 mm
above the prim's origin (Ouster's own lidar-to-sensor offset, 36.18 mm on the OS1). aib then
labels them as being from the origin. Isaac's OS1 profile JSON
(`isaacsim.sensors.rtx/data/lidar_configs/Ouster/OS1/OS1_REV7_128ch20hz1024res.json`) has no
emitter offsets, so the offset would come from the prim or the asset that `RtxLidar.create`
makes, not from the profile.

**An observation from records, offline, consistent with it:** NDT puts the car above its truth.
`/localization/kinematic_state`'s z minus the truth trace's z, above 1 m/s
(`/mnt/renegade/aeon/isaac-ex/c6e/locz.py`):

| run | median | p05 to p95 |
|---|---|---|
| C6d rough_none n1 | +0.0225 m | +0.0019 to +0.0443 |
| C6b smooth none (last) | +0.0259 m | +0.0102 to +0.0404 |

The sign is the one a cloud that is too low gives: to put the scan on the map, NDT raises the
sensor. The size is smaller than 36 mm. The truth trace's z and base_link may differ by a
constant of their own, and the map's cloud has its own offsets, so this does not confirm the
hypothesis by itself.

## Steps (predictions before each)

1. **Confirm, no fix.** A probe in Isaac: the prims `RtxLidar.create` makes under `root`, each
   one's local transform, and the annotator's points for a flat plane at a known height with
   the root at a known pose.
   - *Prediction:* a transform of +0.036 m in z between `root` and the point origin, either in
     the created prim tree or in the sensor's own model. If there is none, the hypothesis
     fails and the probe looks for the origin of the 36.22 mm and of the 6 % at 30.2 mm.
   - **Result (2026-11-25, 09:21, GPU0, `i167_probe.py`, siw 7af1b0c, aib 4e8d684): the
     prediction held.** `RtxLidar.create` makes an Xform `lidar` at the root, with the OS1's
     mesh and an `OmniLidar` prim, `lidar/sensor`, whose local translate is (0, 0, 0.03622) m.
     The annotator's own `transform` puts the sensor at z 2.03622 for a root at 2.0. Over a flat
     plane, all 1,565,840 returns sit at -2.03622 m in the sensor's frame, a single value, so
     the plane is 36.22 mm further below the sensor than aib's mount says. The emitter offsets
     (`horOffsetM`, `vertOffsetM`) are all 0, and the OmniLidar's x and y offsets are 0.
     - So the cause is the OS1 asset's sensor prim, 36.22 mm above the prim aib places. aib
       labels points measured from 2.036 m as being from 2.0 m.
     - C6e1's 6 % at -30.2 mm does not appear over a flat plane, so it came from the road's
       geometry there, not from the lidar (an open detail of C6e1, not of 167).
     - **The -0.066 m across-track bias (C6e2) is not 167's.** The lidar has no lateral offset,
       and the rig's mount matches the sensor kit's extrinsics (`sensors_calibration.yaml`:
       sensor_kit_base_link at x 0.9, y 0, z 2.0, roll -0.001, pitch 0.015, yaw -0.0364;
       `velodyne_top_base_link` yaw 1.575 in it, which is the rig's quaternion, 1.5386 rad in
       all). It gets its own number if it stays (133).
     - **NDT's z bias (+0.022 to +0.026 m) against the 36.22 mm.** This is not forced to fit.
       11 to 14 mm is not explained by the offset. Candidates, none measured: the map cloud's
       own z against the road (the course builder's sampling); the truth trace's z being the
       body's base_link with the suspension's sag against Autoware's static one; and NDT's
       roll and pitch taking part of a z offset on a crowned road. The fix will show how much
       of the bias goes with the offset.
2. **The fix, aib's.** Put the point origin where the rig says the lidar is. At the lidar's
   creation, aib reads the OmniLidar prim's transform under its root, and the mount becomes the
   rig's mount composed with that transform's inverse. The emitter then sits at the rig's
   mount, and the points are measured from where the TF says the lidar is. Any OmniLidar asset
   with an offset is covered, not only the OS1.
   - *Prediction:* C6e1's stops then read a median dz of 0 within 0.5 mm, with the 30.2 mm group
     explained or still there.
   - The lidar's height above the road is the spec's (`sim_vehicle_spec`), so CARLA's lidar is
     at the height the fix gives Isaac's.

## The fix's check (2026-11-25, 09:24 to 09:28, GPU0; aib bb2283f, local)

C6e1's six static stops on fixture_c6a again, with the fixed aib (`run_c6e1_fix.sh`, output
`c6e1-fix167/`). The script places the root by `lidar.mount` and puts the points into the map by
`lidar.sensor_mount`, the rig's mount, which is what the vehicle's TF says.

- The root is now at (0.89946, -0.00002, 1.96378) in base_link: 36.22 mm lower along the
  mount's own up axis, which the mount's pitch of 0.015 rad turns 0.5 mm back.
- **The prediction held:** the median dz to the road is 0.0 mm at every stop and in every band
  (it was -36.22). Over the cleats and the washboard both the median and the p95 are 0.0 mm.
- C6e1's 6 % group, now at about +6 mm, gives a p95 of about 5 mm over the flat road. It is
  the road's geometry, as step 1 found.
- The pothole still reads +80 mm to its floor. That is issue 168's, unchanged.

## Reach (written before any fix, for 133)

Every Isaac result with aib's lidar feeding Autoware. The offset is constant in the sensor's
frame, so a judged A/B whose two sides both ran Isaac's lidar carries it on both sides. What
can move is listed per consumer.

| result | what the lidar fed | what can move | predicted (before any rerun) |
|---|---|---|---|
| 086 C5's clean pairing, C5d (Haruna, fixture) | NDT, the ground filter, perception | NDT's z, NVTL, the ground filter's split | horizontal pose error p95 within 0.005 m; NVTL p05 within 0.02 |
| 086 C6b budget (Haruna, rocks against none) | the same | the same; the tick is not | the same; the rocks' verdict stands (an A/B) |
| 086 C6d (rough Haruna, rocks against none) | the same | the same | the same; the verdict stands (an A/B); its absolutes as above |
| issue 158's reruns (C5d2, C6d) | the same | the same | as C6d |
| issue 157 (Haruna, sand) | the same | the plan's speed only through localization | no change (the creep is the soil's) |
| the 0.2.1 Isaac examples (Town01, Haruna) | the same | pass or fail by their judges | no verdict changes |
| issue 142 (rocks load later) | nothing: fixture_drive has no lidar | nothing | not affected |

- **The ground filter.** scan_ground_filter works on heights relative to the points' own
  ground (elevation grid mode) and a virtual ground point under the sensor. A cloud 36 mm low
  puts the virtual point 36 mm above the measured ground near the car. *Prediction:* no
  change, because 36 mm is well under its 0.20 m thresholds.
- **NDT.** It solves 6 degrees of freedom, so a constant z offset goes into z, as the
  observation above shows. *Prediction:* the horizontal pose error (the judged one) does not
  move by more than 0.005 m, and NVTL stays within 0.02.
- **Obstacles' heights** are measured from the ground in the same cloud, so they do not move.
  The crop box that removes the car's own body uses heights in base_link: a box edge 36 mm off
  matters only for points within 36 mm of it.

**The reach's judgement (133, 2026-11-25, before the runs).** Issue 168's "not lowered"
side gives the post-fix numbers: three runs each of haruna_down on *rough_none* (C6d's package)
and on smooth Haruna (C6b's), on the fixed aib, before 168's code is on. They are compared with
C6d's *rough_none* three (n1 to n3) and with C6e2's smooth "off" three (f1 to f3, the same
package and build but for the fix). Per quantity, the mean of the three against the mean of the
earlier three:

- the horizontal pose error p95 moves by 0.005 m or less;
- NVTL p05 moves by 0.02 or less;
- NDT's z against the truth (median a run) moves down by between 0 and 0.036 m. *Hypothesis:*
  the fix takes out the part of the +0.022 to +0.026 m bias that the offset made, and the rest
  stays (issue 170);
- NDT's pitch against the truth moves by 0.01 deg or less;
- along and across the track (C6e2's `along.py`): each moves by 0.005 m or less.

A quantity outside its bound is a finding against this doc's reach list: the results it lists
get a note, as 158's did. These runs are not a timing pair: the tick is reported only.

If step 2's fix moves any judged number by more than these predictions, the result's doc gets
a note, as 158's did.
