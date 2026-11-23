# 127: a kinematically posed body's CARLA pose can lag its tick by a frame

**Status:** open, a record: the fix's prediction failed (no stall in the "before" runs, below); the fix is parked, not landed (2026-11-24, 133). Filed 2026-11-23 (243, by 133). **Severity:** low.

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

## Wider than poses

In LibCarla 0.9.16 (`carla/client/detail/Client.cpp`) `SetActorTransform`,
`SetActorTargetVelocity`, `SetActorTargetAngularVelocity`, `ApplyControlToVehicle` and
`ApplyControlToWalker` are all `AsyncCall`; only `SetActorSimulatePhysics` waits
(`CallAndWait`). So a tracked NPC's velocity, angular velocity and control can also reach the
server after the tick they were meant for. Under physics that shows as tracking error (a frame
driven on the previous command), not as a stall. The world server actuates NPCs in four places
(`backend.rs` at scensim_carla_world 507d66c):

1. `npc_motion: kinematic`: every NPC's and pedestrian's pose (`set_actor_transform`).
2. The kinematic fallback of a blocked tracked NPC: physics off (synchronous), then its pose.
3. A tracked NPC's snap: its pose, then its target velocity and angular velocity.
4. A tracked NPC's tracking: its target velocity and angular velocity and steer (vehicles),
   or its walker control.

The ego is acb's, on its own client: issue 135.

## The fix (planned, 133 approved 2026-11-24)

One NPC actuation batch per step. Paths 1 to 4 push `carla::rpc::Command`s (`ApplyTransform`,
`SetSimulatePhysics`, `ApplyTargetVelocity`, `ApplyTargetAngularVelocity`,
`ApplyVehicleControl`, `ApplyWalkerControl`), in today's order within each NPC (physics off,
then the pose, then the velocities and the control), and the step sends them with the commanded
bodies' `ApplyTransform`s in one `apply_batch_sync` before its tick. Each command's response
maps back to its NPC's error path as today (a failed teleport is reported to SSv2, the WARN
lines); a failed command fails only its own NPC. Unit tests: the order per NPC, and a failure in
the middle of the batch mapped to that NPC only.

## How the fix is judged (written before the "before" runs)

**Detector**, per entity and frame of the truth, comparing the world's pose (`sim_pose`) with
SSv2's (`ssv2`): a stall-then-double-step at frame k is

- the world's step from k-1 to k under 0.001 m, while SSv2's step there is over 0.05 m, and
- the world's step from k to k+1 between 1.5 and 2.5 times SSv2's step from k to k+1.

For tracked NPCs (paths 3 and 4), the tracking error is the distance from `sim_pose` to `ssv2`
per frame, summarised as its p95 and max per run, with the run's snap count.

**Runs**: one CARLA project with at least four NPC vehicles and a walker, four seeds, with
`npc_motion: kinematic` (at least 4000 kinematic entity-frames), and the same four seeds
tracked. Before the fix on scensim 79775334, after it on the fix, the same host, stack and
seeds.

**Predictions**:

- kinematic, before: at least 5 stalls in all (K12's walker showed 1 to 2 per about 230
  frames); after: 0;
- tracked: tracking error p95 the same or lower after the fix, no new snaps;
- step time: one synchronous round trip per step instead of the NPCs' asynchronous sends,
  about +0.1 to 0.3 ms on the tick's p50 at under 10 NPCs; measured from result.json's frame
  metrics and a timing of the batch call per step.

**The walker set** (added 2026-11-24, 133; written before its runs): the bench scenario has no
pedestrian, so `town01_pedestrian.xosc` (scensim_examples basic: an ego, one walker crossing,
two barriers) runs as a set of its own, `npc_motion: kinematic`, four repeats, CARLA's
BasicAgent as the ego (`carla_basic`, as `k12_commanded`), before and after the fix. Its
prediction: before, at least one stall over the walker's frames in which SSv2 moves it more
than 0.05 m (K12's walker: 1 to 2 per about 230 frames); after, 0. With fewer than 200 such
frames over the four runs, the set is reported as too small to judge, not as a pass.

If the "before" runs show 0 stalls, the work stops there and is reported: the race is then too
rare at this load to show, and the fix would rest only on the code argument and K12's set 3.

## The "before" runs (2026-11-24, 243): no stall, so the work stopped

Build: scensim 79775334 (scensim_carla_world 507d66c), CARLA 0.9.16 at Epic, newslab-server243
(load average about 5 to 15 on 32 cores), one fresh stack per set, four repeats each:

| Set | Entity-frames | Moving frames | Stalls | Error from SSv2, p50 / p95 / max |
|---|---|---|---|---|
| `town01_npc_10`, kinematic | 48040 | 48000 | 0 | 0.0 / 0.0 / 0.0001 m |
| `town01_npc_10`, tracked | 48040 | 48000 | 0 | 0.0006 / 0.030 / 0.30 m |
| `town01_pedestrian`, kinematic | 5673 (the walker 1880) | 0 over 0.05 m | 0 | 0.0 / 0.0 / 0.0 m |

The world's step against SSv2's, over the kinematic set's moving frames: p1 0.9999, p50 1.0000,
p99 1.009. The four repeats of each set gave the same numbers. The walker walks at about
0.69 m/s (0.035 m a frame), under the detector's 0.05 m, so by the rule written above its set is
too small to judge. Read at 0.02 m instead (not the written rule), its 952 moving frames have no
stall and no error.

**The prediction failed.** It said 5 or more stalls before the fix in the kinematic set; there
were none, in that set or any other, and by the rule written before the runs the work stopped
here. Why the kinematic NPCs never showed what K12's
walker did: the walker was posed inside the step (`advance_commanded`, in `tick_frame`), one
asynchronous call sent immediately before `world.tick()`; a kinematic NPC is posed while
`UpdateEntityStatus` is handled, a request of its own that SSv2 sends and waits for before it
asks for the frame, so its call has long landed when the tick comes. The race issue 127 names is
real in the code (the calls are asynchronous), but at this load it does not show for NPCs.

Two corrections were made on the way, both before any comparison with the predictions: the detector first compared the body's pose with SSv2's entity pose (a constant
1.387 m, issue 130's mistake), now the entity's; and a first attempt at the runs was void (two
scripts overlapped on one CARLA, and a `pkg://` path is refused on the command line).

## When the race would show again

Whenever the world server poses or commands an NPC after the last request it answers before
the frame's tick: a path that actuates an NPC inside the step (as `advance_commanded` did for
K12's walker, before its batch), or a change in SSv2's order (`UpdateEntityStatus` sent without
waiting for its answer, or after the frame is asked for). Either would put an asynchronous call
next to `world.tick()` again; the detector here (`scensim_launch/scripts/pose_stalls.py`) and
these runs are the check to repeat.

## The parked fix

scensim_carla_world 9947fef (on 507d66c, branch `127-npc-batch`, not pushed): every NPC command
of an `UpdateEntityStatus` (kinematic poses, the fallback's physics off and pose, a snap's pose,
a tracked vehicle's target velocity, yaw rate and steer, a tracked walker's control) in one
`Actuation`, in the order it used to be called, sent with one `apply_batch_sync` before the
answer; a failed command fails only its own NPC. Unit tests for the order per NPC and the
failure mapping; the crate's 217 tests pass and clippy is clean. Not landed: the runs above give
it nothing to fix at this load, and it changes every tracked NPC's actuation path. To pick it
up: `~/nas/home/2026-11-24 issue 127 parked fix (243)/` holds a git bundle of the branch
(`git fetch <bundle> 127-npc-batch`), the commit as a patch, and SHA256SUMS. The predictions'
timestamps are in `~/nas/home/2026-11-24 issue 127 predictions (243)/`.
