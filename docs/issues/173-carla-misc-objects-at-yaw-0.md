# 173: CARLA's misc objects seemed to stand at yaw 0 instead of SSv2's heading (not a defect)

**Status:** closed, not a defect (243; numbered by 133 on 2026-11-25, withdrawn the same day
before any code). **Severity:** none: the world was right; the reading was wrong.
**Reported:** 2026-11-25, scensim 243, in 092 K9f-b's first CARLA suite: the three street
barriers' `sim_pose` yaw in the gap trace was -0.0004 rad on CARLA, against SSv2's -1.5712
(h pi/2 relative to the westbound lane), in K9e's CS3 runs too; Isaac's was -1.5712. Read as
"the rotation is dropped".

## What it was

A gap trace entity's `sim_pose` is the simulator's body pose (truth-stream.md). Its entity row
carries `origin_offset [x, y, yaw]`, the body's pose relative to the entity's, and every reader
of the truth takes it back off (`scensim.truth.boxes`, `gap_geometry.entity_pose_from_actor`,
the gap oracle, `behaviour.seats`).

The CARLA world server spawns a prop whose blueprint fits the declared box only when turned,
turned by 90 degrees (`backend.rs`, the size choice's `turned`): the street barrier's mesh
is 1.21 m along its own x and 0.37 m along y (`blueprint_box` extent 0.607 x 0.186), the
declared box 0.4 m long and 1.2 m wide. So the barrier's `origin_offset` yaw is pi/2, and its
body yaw is the entity's plus pi/2.

Taken off with the project's own reader, on 092 K9f-b's CARLA run of 2026-11-25 12:03
(closure=closed, pm=current): barrier_a, b and c at x 305.641, y -128.206, -129.506, -130.806,
**yaw -1.5712**, offset yaw 1.5708, asset `static.prop.streetbarrier`. On Isaac (K9e step 2b,
08:02): the same x, y and yaw -1.5712, offset yaw 0, asset `isaac:box`. Both match SSv2's
pose.

## The reach 133 asked for

Had the rotation been dropped, the barriers' footprint against the car's collision and
Autoware's perception would have been turned a quarter, and any CARLA closure verdict could have
depended on it. It was not: the footprint CARLA uses is the declared box's, turned with the
entity. The scenarios that place misc objects with a heading on CARLA, for the record:
CS3 (`k9_cs3` `cs3_stale_map`, `cs3_layout`), the starter `pedestrian_crossing` and
`basic/town01_pedestrian` (street barriers at h pi; their run of 2026-11-20 records the same
offset yaw pi/2), CS1's van, and the demo tour's parked cars and walkers spawned as misc
objects (vehicle and walker blueprints; their offsets not looked at, and taken off by the same
readers whatever they are).

## The lapse

The raw `sim_pose` was compared with SSv2's pose without the entity's offset. A reading of the
truth goes through `scensim.truth` (or takes `origin_offset` off), never the raw body pose.
