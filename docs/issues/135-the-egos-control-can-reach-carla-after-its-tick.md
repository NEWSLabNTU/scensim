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

**The alignment check (2026-11-24, 06:05 to 06:15, newslab-server243, load about 4):** CARLA
0.9.16 at Epic on its own port, `scensim_launch/scripts/carla_control_alignment.py`, 400 ticks,
then 4000:

| Applied before tick k by | Ticks | Snapshot frame = tick frame | Frame k holds k's control | Holds the previous |
|---|---|---|---|---|
| `apply_batch_sync` | 400 + 4000 | all | all | 0 |
| `apply_control` (async) | 400 + 4000 | all | all | 0 |

The first part of the prediction holds: a frame's snapshot is its tick's, and holds the control
applied before that tick, so `control` at frame k is the control CARLA ran in tick k. The
second did not show: the asynchronous call never landed late, in 4400 ticks. One client's calls
travel in order on one connection, so its `apply_control` reaches the server before its own
`tick()`; the race this issue names needs two clients, as acb (its own client) and the world
server (the one that ticks) are. **So step 1's alignment check covers one client only, and acb's case, two clients, is
still open:** whether a control acb sends for tick k from its own connection is held at tick k
is what this issue asks, and nothing here answers it; the field is what lets a run with acb see
it, with acb's send times (step 2, acb's). One caution: K12's walker
stalls (issue 127) came from one client too, the world server's own `set_transform` before its
own tick, so for a pose (a body without physics) the order of the calls alone did not keep it
in its tick; for a vehicle's control it did, in all of these.

**The cost and the live check (2026-11-24, 06:15 to 06:28):** `town01_npc_10` tracked, four
repeats, on the build that reports the control (scensim on 79775334 with scensim_world_protocol
3c8a120 and scensim_carla_world 8939db6), against issue 127's four "before" runs of the same set:

| | frame p50 (ms) | frame p95 (ms) | tick p50 (ms) |
|---|---|---|---|
| before | 0.53, 0.52, 0.55, 0.52 | 0.73, 0.74, 0.78, 0.72 | 2.89, 2.81, 2.86, 2.95 |
| with `control` | 0.58, 0.59, 0.59, 0.56 | 0.81, 1.42, 1.22, 0.82 | 2.91, 2.99, 2.94, 2.87 |

**The cost prediction was not met.** It said "under 0.05 ms"; the step's processing grew by
0.05 ms at p50 (0.53 to 0.58 ms on the means), at the bound, not under it. Two of the four p95s
are well above the others (1.42 and 1.22 ms against about 0.75): unresolved in four runs, not
told apart from the host's load. The frame budget judge passed all four. The tick itself did not move. The live check held: every
tracked vehicle had `control` at every frame with a world pose (12010 of 12010 in each run), all
in range, throttle and brake 0 at every frame and the steer varying (246 values a run). The set
has no body that is not a tracked vehicle, so "no `control` on such a body" is shown only by the
unit tests (`only_physics_vehicles_report_a_control`).

**The ego run (133: required before landing; written before it runs):** one run of
`k12_commanded_free` (CS1 on Town01, CARLA's BasicAgent as the ego, `carla_basic`, which drives
it from its own client) on the same build. Prediction: the ego carries `control` at every frame
with a world pose from its first nonzero control on, all values in range, and throttle and
brake never both above 0.5 at one frame.
