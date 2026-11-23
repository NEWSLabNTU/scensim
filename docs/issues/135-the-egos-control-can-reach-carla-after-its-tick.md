# 135: the ego's control can reach CARLA after its tick

**Status:** open, a record (2026-11-24, 243; filed by 133). **Severity:** to judge.
**Found:** 2026-11-24, while planning issue 127.

acb drives a CARLA ego on its own LibCarla client, and the calls it actuates the ego with are
asynchronous in LibCarla 0.9.16: `Vehicle::apply_control` (`ApplyControlToVehicle`, in
`acb_bridge/src/vehicle_control.rs`) and `set_target_velocity` (`SetActorTargetVelocity`, in
`vehicle_physics.rs`) are `AsyncCall`s in `carla/client/detail/Client.cpp`, as `set_transform`
is (issue 127). So the ego's control for a frame may reach the server after the world server's
tick for that frame, and the ego then drives that frame on the previous control. Not measured;
no work yet. Whether it happens, how often, and whether acb should send its control in one
synchronous batch, as issue 127 does for NPCs, is for acb's owner to look at.

**What the existing runs can show (2026-11-24, 243, analysis only): nothing.** 092 K12's sets 2
and 3 drove the ego with CARLA's BasicAgent, not acb. k9_cs3's runs have an Autoware ego on acb,
but their truth carries no command for it (the truth's `command`, 092 K2.4, is filled by a world
server that reports one, and the CARLA world server does not), and acb logs no per-frame
control. acb does not tick CARLA either: each frame it waits for the world server's tick
(`wait_for_tick_or_timeout`), stamps the frame's time and spins its executor, applying whatever
Autoware sent then, so its control is tied to no particular tick, and a late landing is not
told apart from Autoware's own latency in the ego's velocity. A measurement needs, per frame:
the control CARLA held for the ego at each tick (the world server reading the ego's
`Vehicle::control` from the tick's snapshot into the truth's `command`), the wall time and
CARLA frame at which acb called `apply_control` (an acb log line or a truth field), and the
tick's own wall time (the truth's `wall_ns`); a control acb sent before tick k's start that CARLA
does not hold at tick k is one that landed late.

## Step 1: the control CARLA held, in the truth (2026-11-24, 133 approved)

The CARLA world server reports, per step, the `VehicleControl` CARLA held for the ego and every
vehicle it moves by physics (`EntityState.applied_control`, the truth's optional `control`,
raw). Which control a frame's snapshot holds is checked, not assumed, by a direct client on a
CARLA of its own (no world server), synchronous at 20 Hz, one vehicle, 400 ticks, a different
control each tick (throttle k/400, steer alternating sign), applied just before the tick in two
ways: by one `apply_batch_sync` of `ApplyVehicleControl` (it waits), and by `apply_control` (an
`AsyncCall`). After each tick the vehicle's `get_control()` is read and the snapshot's frame is
compared with the frame `tick()` returned.

**Prediction, written before the check:** the snapshot's frame is the tick's at every tick;
with the synchronous batch, frame k holds the control applied before tick k at all 400 ticks;
with `apply_control`, frame k holds it at most ticks, and any tick that does not holds the
previous one (the race this issue names, at a client sending right before the tick).

**Its cost and a live check, also written before they run.** On `town01_npc_10` tracked (the
four runs of issue 127's "before" set, the baseline), the same set on the build that reports
the control: the step's processing time in result.json (frame p50 and p95) grows by under
0.05 ms at p50 (one actor list and ten snapshot lookups a step). In those runs every tracked
vehicle has `control` at every frame with a world pose, the throttle and brake in 0..1 and the
steer in -1..1 (the world server tracks by velocity and steer: throttle and brake 0, steer
varying), and the walker-free set has no `control` on a body that is not a tracked vehicle.
