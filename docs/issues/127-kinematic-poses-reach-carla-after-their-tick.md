# 127: a kinematically posed body's CARLA pose can lag its tick by a frame

**Status:** open, a record (2026-11-23, 243; filed by 133). **Severity:** low.

## What is wrong

The CARLA world server poses a kinematic body with `Actor::set_transform`, which in LibCarla
0.9.16 is an asynchronous call: `Client::SetActorTransform` is `_pimpl->AsyncCall(
"set_actor_transform", ...)` (`carla/client/detail/Client.cpp`), while the tick that follows it
is a call that waits. The transform can therefore reach the server after the tick it was meant
for. The body's pose read back after that tick is then the previous one: it stalls a frame and
catches up with a double step at the next.

## How it was found

092 K12's first exit runs (2026-11-23) posed a commanded walker the same way. In their truth
the walker's `sim_pose` stalled for one frame and caught up with a double step at the next
(seed 2: frames 158 and 220; seed 3: 165), against an integrator that never stalls. That was
fixed for commanded bodies by posing them with one `apply_batch_sync` of `ApplyTransform` per
step (scensim_carla_world a27b833). Every other kinematic pose still uses `set_transform`.

## Which truth may carry it

A body's `sim_pose` in the truth file may lag one frame now and then wherever the world server
poses it with `set_transform`:
- every NPC and pedestrian under `npc_motion: kinematic` (bridge_config's default is
  `tracked`; no testbench or launch config in this repository sets `kinematic`);
- a tracked NPC handed to kinematic after a blocked snap (the frame's `kinematic` flag);
- a tracked NPC's snap back to SSv2's pose (`npc_tracking`'s Snap).

Tracked bodies otherwise move by CARLA's physics (VehicleControl, WalkerControl) and are not
affected; nor is the ego. The gap oracle reads a one-frame lag of a kinematic body as a pose
divergence of one step's motion (G3), and a judge measuring clearances sees the same step.

## The fix (not done)

Pose kinematic bodies as commanded ones are now posed, one synchronous batch of
`ApplyTransform` per step, and measure the step time it adds.
