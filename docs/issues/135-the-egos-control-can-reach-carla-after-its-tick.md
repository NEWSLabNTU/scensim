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

**The ego run's result (2026-11-24, 06:31):** `k12_commanded_free` seed 1, passed. The ego's
first nonzero control is at frame 2; from there all 245 frames with a world pose carry
`control` (none missing), all in range, and throttle and brake are never both above 0.5 (their
maxima 0.75 and 1.0). The prediction held. The run's other bodies, the commanded walker and the
van (a misc object), carry none: live, the exclusion the bench set could not show.

## Step 2: acb's sends against CARLA's frames (2026-11-24, 133 approved)

acb records, with `apply_trace_path` set, one row per actuation of the hero (its
`apply_trace.rs`): `CLOCK_MONOTONIC` before the call, the newest frame its main loop had taken
(`f_obs`), the newest its client had received when the call returned (`f_after`), and the
control as sent; and one row per frame it takes. The rows go through its writer thread, never
the control path's disk. `scensim_launch/scripts/apply_alignment.py` joins them with the
truth's `control` by CARLA frame: for frame s, the expected control is the last sent with
`f_obs == f_after == s - 1`; the truth holding it is `in_time`, holding the one sent just before
it is `late`, a send a tick finished during is `raced` (not judged), two equal values are
`ambiguous`, and frames near a row the writer dropped are `unclassified`. Values match within
1e-6 (CARLA keeps float32), the flags and gear exactly. A `late` is a candidate, bounded by the
stream delay: acb's view "still s - 1" is not proof the server had not begun tick s.

**The run:** one Autoware ego scenario of the `dev` project on Town01 (scensim's profile,
tesla_model3), on a stack built from scensim main with acb's change, both workspaces rebuilt
from a clean environment, acb's built binary checked against the source.

**Prediction, written before it runs:** every truth frame after the ego's first `control` is
labelled; `late` is under 1% of the judged frames (`in_time` + `late` + `other`), possibly none,
since the world server ticks only after SSv2's request and acb sends after taking the previous
frame; `raced` is rare too; `ambiguous` is common while the car is held (Autoware repeats a
stop's control); and about a third of frames have two or more sends (Autoware at 30 Hz against
20 frames a second), only the last of which is judged.

**The run (2026-11-24, 08:26 to 08:28):** `dev_trace` (the dev project's Autoware ego, scensim's
profile, `town01_ego_drive`), passed. Built from a clean environment, acb's workspace then
scensim's (acb 6600e3a, scensim 00d3dd9d); both `acb_bridge` binaries carry the new parameter.
`ros2 pkg prefix acb_bridge` named this repository's `install/`, but the stack's launch ran acb's
own workspace's copy (`src/autoware_carla_bridge/install/acb_bridge/lib/acb_bridge/acb_bridge`,
from the stack's `cmdline`): built from the same acb commit a minute apart, so the measurement
stands; the live-process check in the run script found no `acb_bridge` yet when the stack
reported ready, so the binary is read from the launch's logs. The trace: 487 `apply` rows, 672
`tick` rows, no `velocity` row, no row dropped.

**A correction to the matching, after the first classification:** it labelled 438 frames
`other`, every one of them differing only in the gear: acb sends gear 0 with the automatic
transmission, and CARLA's read-back holds the gear the car is in (1). The gear was taken out of
the match (`apply_alignment.py`; a test), and step 1's documents said wrongly that `gear` is the
gear asked for: on CARLA, under the automatic transmission, it is the gear engaged (corrected in
`truth-stream.md`, the proto's comment and `world-protocol.md`).

| Frames with `control` | judged | in_time | late | other | ambiguous | no_send | raced |
|---|---|---|---|---|---|---|---|
| 685 | 477 | 468 | 9 | 0 | 6 | 202 | 1 |

**The prediction was not met as stated:** 9 `late` in 477 judged frames is 1.9%, not under 1%.
But they are not scattered: they are one stretch, CARLA frames 1482 to 1492 (9 judged, frame 1491
not sent for), in which every frame held the control acb sent while its newest frame was s - 2,
not s - 1: a lag of two ticks for about ten frames, against one everywhere else. Every send in
the stretch left 0.15 to 0.4 ms after acb took its frame and its call took 11 to 21 us, about
50 ms before the next tick by acb's own clock. The stretch ended when acb's tick follower
skipped frame 1491 (it drained two frames at once) and its sends landed one tick later again.
That is the shape of acb's view of the frames running one tick behind the server's (the stream
delay the method names as its limit), not of an asynchronous call lost in flight; this trace
cannot tell the two apart, which needs the world server's tick-start time on the same clock
(`CLOCK_MONOTONIC`). Outside the stretch, every judged frame held acb's control in its tick.

## Step 3: the server's tick times on the same clock (2026-11-24, 133 approved)

Step 2 could not tell a control that reached CARLA late from acb's view of the frames running
behind the server's. So the CARLA world server stamps `CLOCK_MONOTONIC` just before its call to
`world.tick()` for the step's last tick and again when it returns, and reports both in the step
reply; the truth's frame carries them (`tick_mono_ns`, `tick_return_mono_ns`), and its episode
the world server's boot id (`/proc/sys/kernel/random/boot_id`). acb's apply trace names its own
boot id in its header. `CLOCK_MONOTONIC` compares only within one boot of one host, so
`apply_alignment.py` refuses the timed comparison, by name, when the two boot ids differ or one
is missing.

With the times, a frame whose control was not held is `late` when its expected send left before
the tick's start stamp, and `after_tick` when it left after it (acb's view was behind). The
start stamp is taken on the client just before `tick()`; the server begins the tick a little
later, by up to the call's send latency, so a control sent inside that window and not held would
be labelled `after_tick` though it was late. That window is bounded and measured: the
distribution of (return minus start) is reported beside the labels, with how many `after_tick`
sends fall within its p95 of the start stamp.

**Prediction, written before the runs** (dev_trace, `town01_ego_drive`, three runs on one fresh
stack): every frame step 2's rule calls `late` is `after_tick` here, sent after the tick began;
truly `late` frames are 0; if no such stretch recurs in three runs, that is said, and step 2's
nine frames stay unjudged (their tick times were not recorded); the tick's p50 is unchanged
within noise (one more `clock_gettime` a tick).

**Results** (2026-11-24, dev_trace, `town01_ego_drive`, three runs on one stack started 12:42:19;
acb bf96de9, world server a7a7570, protocol d11b744; `scensim_launch/scripts/apply_alignment.py`,
outputs in `/var/tmp/aeon/i135/step3/`). The boot ids matched in both judged runs, so the timed
comparison ran.

| run | outcome | frames with `control` | in_time | ambiguous | no_send | late | after_tick | in_time after the stamp |
|---|---|---|---|---|---|---|---|---|
| 1 (12-43-35) | passed | 677 | 475 | 4 | 198 | 0 | 0 | 0 |
| 2 (12-44-50) | error at 82 frames | 81 | 0 | 0 | 81 | 0 | 0 | 0 |
| 3 (12-45-51) | passed | 679 | 475 | 12 | 192 | 0 | 0 | 0 |

The tick call (return minus start), in us:

| run | stamped frames | min | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| 1 | 678 | 732 | 1173 | 1644 | 3197 | 14746 |
| 2 | 82 | 794 | 1306 | 1632 | 1843 | 1843 |
| 3 | 680 | 553 | 1234 | 1766 | 2973 | 6609 |

Run 2 is not a result about controls. Autoware's `pose_instability_detector` aborted ("cannot
store a negative time point in rclcpp::Time", docs/issues/027) and the run ended as an error
after 82 frames, before the ego sent anything (81 `no_send`). This worktree had no Autoware overlay
built, so the stack ran the stock detector without 027's fix. It has nothing to do with this
step's change.

Against the prediction:

- **No late stretch recurred.** In runs 1 and 3, 1356 frames with `control`, step 2's rule
  calls none `late`. There was nothing for the stamps to split, so the prediction's main claim,
  that such frames are `after_tick`, is untested. As the prediction said for this case, step 2's
  nine frames (1482 to 1492, untimed) stay unjudged.
- **Truly `late` frames: 0**, as predicted, but with nothing to compare that adds no evidence.
- **Every expected send left before its tick's start stamp.** No `in_time` frame's send left after
  the stamp, so the RPC send window the start stamp cannot see was never tested here.
- **Tick p50 unchanged within noise**, as predicted. The bridge's tick p50 was 1.36 ms in step 2's
  run and 1.24 ms in runs 1 and 3; p95 was 2.81 ms then and 1.81 and 2.36 ms now.

Step 2's stretch was a single event: eleven frames, which ended when acb's follower skipped a
frame. Three runs did not reproduce it. The instruments are now in place, so the next stretch,
in any traced run, will be judged where it happens.
