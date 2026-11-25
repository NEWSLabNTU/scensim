# 167: aib's lidar points sit 36 mm below where the rig puts the lidar

**Status:** open; doc and predictions first (133, 2026-11-25), no fix yet. **Severity:** to be
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
2. **The fix, aib's.** Put the point origin where the rig says the lidar is. Either the mount
   compensates for the offset (the root lowered by it), or the points are shifted by it before
   they go out, whichever step 1 shows is the true geometry.
   - *Prediction:* C6e1's stops then read a median dz of 0 within 0.5 mm, with the 30.2 mm group
     explained or still there.
   - The lidar's height above the road is the spec's (`sim_vehicle_spec`), so CARLA's lidar is
     at the height the fix gives Isaac's.

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

If step 2's fix moves any judged number by more than these predictions, the result's doc gets
a note, as 158's did.
