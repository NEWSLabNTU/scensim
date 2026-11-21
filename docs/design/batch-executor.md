# The batch executor (roadmap 092 K2)

The batch executor runs a scenario in the compilable subset ([compilable-subset.md](
compilable-subset.md)) over N slots at once on an Isaac Lab environment, for training and
evaluating learned policies ([ml-training-interface.md](ml-training-interface.md) sections 5
and 5a). It lives in `src/scensim_batch`. This note grows with its milestones:

| Milestone | What | State |
|---|---|---|
| K2.0 | Isaac Lab v3.0.0-EA as an overlay on Isaac Sim 6.1 (section 3); its Cartpole benchmark on 139 as a 5a reference row | installed; benchmark waits for a free GPU |
| K2.1 | SSv2's default vehicle behaviour, batched in torch (section 2) | in progress |
| K2.2 | The environment: a DirectRLEnv from a compiled scenario and sample records, the ego from aib's rig, the control component through `step_batch`, resets per slot | open |
| K2.3 | The compiled storyboard (conditions, actions) and the truth export (truth-stream.md, schema 2) (section 6) | in progress: the state machine, 10 conditions, SpeedAction and the exits, truth per slot; the rest executor pending |
| K2.4 | Agreement: each "batch" row of the subset on seats and in batch, on the same sample (Town01); each seats run records S, its frames before startNpcLogic, and the batch replays with `start_frames=S` (section 6, scenario time) | open |
| K2.5 | `scensim bench`: throughput at N = 256 and 1024 against a hand-written Isaac Lab environment (the RoboRacer indoor field) | open |
| K2.6 | The world adapter on a Lanelet2 map (section 7): any map exported once (`map_export`), its queries answered as SSv2's (`world_lanelet`); a polyline world with the same interface | in progress |

## 1. Shape

- **A DirectRLEnv**, not a manager-based one: the storyboard is a state machine, not reward or
  termination terms, and the direct form gives the adapter its own per-slot reset and
  pre-physics step.
- **Compiled, or refused.** The environment is built only from a scenario that
  `scensim-sample compilable` accepts, and only when the environment meets every condition the
  verdict lists (a camera, a fog renderer, a batched model).
- **The ego** comes from aib's rig (the spec's car, the same rig seats run), and its control
  component runs through `sim_vehicle_ecu.batch.load_batch` with `require_vectorised`.
- **Truth** is the content of truth-stream.md's schema 2 as per-slot tensors. Each slot keeps
  its sample record and seed, and exports as a schema-2 file, so any slot replays on seats.
- **Rewards and terminations** are the user's. The environment gives events: contacts, the
  storyboard's end (`exitSuccess`, `exitFailure`) and route progress.

## 2. SSv2's default vehicle behaviour (K2.1)

A vehicle with no controller in SSv2 runs behavior_tree_plugin's vehicle tree
(`vehicle_entity_behavior.xml`):

```
Fallback root
  LaneChange
  FollowPolylineTrajectory
  Fallback follow_lane_sequence
    FollowLane
    Fallback: FollowFrontEntity, StopAtTrafficLight, StopAtStopLine, StopAtCrossingEntity,
              Yield, MoveBackward
```

`scensim_batch.npc` ports the part every SSv2 example's traffic uses: FollowLane and
FollowFrontEntity, on SSv2's jerk-limited speed planner.

| SSv2 | Port |
|---|---|
| `LongitudinalSpeedPlanner::getDynamicStates`, `planLinearJerk`, `forward`, `timeDerivative` | `dynamic_states`, `plan_linear_jerk`: the same operations in the same order, per element |
| `getRunningDistance` (the stop distance) | `running_distance`: the same loop, masked per vehicle until every one reaches its target |
| FollowLane: follow the front entity when it is within the stop distance + own length + 5 m | the same test, `front_entity_stop_margin` 5 m |
| Once following, keep following while a front entity is found: BehaviorTree.CPP's Fallback is not reactive, it resumes its RUNNING child (FollowFrontEntity) without ticking FollowLane, so the hand-off is not re-tested while braking shrinks the stop distance | `DefaultVehicles.mode` carried from step to step; `ssv2_ref.local_target(running=)`; seats' k24_npc_stops_for_ego follower reproduced to 1 mm/s over 300 steps (`test_npc`) |
| The front distance from box edges: the own box's front edge and the other's rear edge, each `centre.x` -+ length / 2 from the pose (`boundingBoxLaneLongitudinalDistance`, `getDistancesFromCenterToEdge`), plus half the own length | `DefaultVehicles(cx=)` and the others' `cx` from each entity's BoundingBox/Center; corners shifted by it (k24: pose distance less 2.48 m, where centred boxes gave 2.396) |
| The ego as the default vehicles see it: read back in the tick, so per world frame two frames old | after_physics hands `_observe` the ego of two steps before for the vehicles; the observation's stays current |
| FollowFrontEntity: 0 inside the stop distance, the front's speed + 2 m/s beyond stop + length + 5 m, the front's speed between, clamped to [0, target]; the target when it is not above the front's speed | the same rule (`front_entity_margin` 5 m, `speed_step` 2 m/s) |
| the front entity: within ±90° of the heading, on the path (its box within half the own width of the spline), ahead, within the horizon clamp(5 v, 20, 50) m or the stop distance; its distance is the bumper gap plus half the own length (`splineDistanceToBoundingBox`) | the same tests, on the route's centreline |
| the move: arc length advanced by the mean of the old and new speed times the step (`calculateUpdatedEntityStatus`) | the same |
| the target: the last SpeedAction's, else the route's speed limit | `set_target_speed`, else `speed_limit` |

Two differences are by construction:

- **The path is piecewise linear** through the route's centreline points, where SSv2 uses a
  Catmull-Rom spline through the same points. Poses and headings differ by the spline's
  deviation from the chords. K2.4's agreement measures it.
- **The front entity's box is projected per corner** onto the path, where SSv2 measures the
  box's distance to the spline by bisection (`distanceToSpline`). Like SSv2, a box counts as
  ahead when a corner is within half the own width of the path, or else when the path crosses
  the box (SSv2's `getCollisionPointIn2D` fallback): a truck wider than the car, centred on its
  path, is seen. A box already overlapping the bumper (a negative gap) is no front entity, in
  SSv2 too (`splineDistanceToBoundingBox` returns none); its contact is the collision's.
  Both cases are pinned by a test against the reference.

Not ported yet: the tree's StopAtTrafficLight, StopAtStopLine, StopAtCrossingEntity, Yield and
MoveBackward, FollowLane's right-of-way check, LaneChange and FollowPolylineTrajectory. The
compile step refuses a scenario whose default-behaviour vehicles would need one of them (a
route over a stop line or an active signal, a crossing, a lane change): these are the gaps,
each a later row.

SSv2's planner exceeds its own jerk limit on arrival: it caps the acceleration at
(target − v)/dt, so the step that reaches the target drops the acceleration at once (45 m/s³
in the test at a 0.05 s step). The port keeps this.

**Tests** (`src/scensim_batch/test`): SSv2's logic transcribed for one vehicle in plain floats
(`ssv2_ref.py`).

- The planner equals it bit for bit over 400 random states.
- The stop distance equals it to 1e-9.
- 64 slots of a follower behind a lead equal 64 scalar runs to 1e-6 over 300 steps.
- An entity counts only when it is ahead, in the cone and on the path.
- Vehicles in one slot see each other.

All pass in the system Python (torch 2.0) and in Isaac's (torch 2.11).

**Cost, CPU** (8 threads, 139 under load 8 to 12): 4 vehicles per slot plus the ego take
19.8 ms per step at N = 256 and 86 ms at N = 1024, about 50 k vehicle-steps per second. The
stop-distance loop and the corner projection (slots × vehicles × entities × 4 corners × route
segments) dominate. The GPU number waits for an announced bench window. A closed-form stop
distance would remove the loop: the distance from (v, a) to 0 is fixed per constraint set, so
a table over (v, a), or computing it only when a front candidate lies within the horizon,
bounds it (a gap, for K2.5).

**A route ends.** A vehicle's route is a fixed length of centreline from where Init places it
(`BatchRun(route_length=)`, 300 m by default). Past its end the vehicle holds the end pose, and
entities beyond it project onto the end, where SSv2 would continue along the following
lanelets. The world adapter's routes must cover the episode (K2.3).

## 3. Isaac Lab as an overlay (K2.0)

`scripts/isaaclab_overlay.sh <isaac-venv> <dest>` installs Isaac Lab beside an Isaac Sim pip
install without changing it.

- **The tag: v3.0.0** (e3f7d9ff), on Isaac Sim 6.2.0.0, which it pins (roadmap 095). Until
  then it was v3.0.0-EA (ae37b028) on Isaac Sim 6.1.0.0, which that tag pins; the script
  still takes it by `ISAACLAB_TAG` and `ISAACLAB_COMMIT`. 3.0.0's packages are a uv workspace
  whose members import one another (isaaclab imports isaaclab_ov): every member under
  `source/` is installed, and the dependencies are the root pyproject's and the members'.
  Watched: the isaacsim 6.2.0.0 wheel brings warp-lang 1.20.0.dev, Isaac Lab pins 1.17.0;
  the Isaac venv's is kept.
- **How it works.** It makes a venv of its own under `<dest>`, which sees the Isaac venv's
  packages through a `.pth` file. Isaac Lab's packages are installed editable from a checkout
  at the tag, without dependencies (under v3.0.0-EA: isaaclab, isaaclab_physx,
  isaaclab_newton, isaaclab_contrib, isaaclab_assets, isaaclab_tasks and isaaclab_rl; under
  v3.0.0 every workspace member, 14). Then it installs only the
  third-party packages that the Isaac venv lacks, constrained to the Isaac venv's own versions
  (27 on 139: gymnasium, rsl-rl-lib, hydra-core, onnx, transformers, open3d, and others).
- **What it leaves alone.** torch, isaacsim and warp stay the Isaac venv's. Its warp is
  1.19.0.dev, where Isaac Lab asks for 1.16.0; Isaac Sim's own wins, and the benchmark will show
  whether that matters.
- **Measured on 139** (2026-11-21):
  - the overlay is 1.9 GB, plus 132 MB of source, and / went from 90 to 88 GB free;
  - the Isaac venv's `pip freeze` is identical before and after;
  - `pip check` reports only the Isaac venv's own two pre-existing lines;
  - `isaaclab`, `isaaclab_tasks`, `isaaclab_rl` and `DirectRLEnv` import, with torch
    2.11.0+cu128 and warp 1.19.0.dev.
- **Running it** needs `OMNI_KIT_ACCEPT_EULA=YES` and the NVIDIA Vulkan ICD, as aib's
  `isaac_env.sh` sets for the same install.

## 5. The engine backends (K2.2): A, the PhysX vehicle; B, an articulation car

Two backends behind core.BatchRun's contract, named, not hidden (133, C):

- **A, `physx_vehicle`**: N copies of aib's PhysX vehicle, the same car, tire model and
  physics as seats (aib's `Vehicle.actuate`: the actuation from a component stepped outside
  it). It is K2.4's agreement path: a batch run on it can be checked against a seats run.
  Isaac Sim 6.1's physics tensor API has no vehicle view (articulation, rigid-body, deformable
  and contact views only), so its writes and wheel-state reads are per car: `vectorised =
  False`, and a throughput bench refuses it.
- **B, an articulation car**: a body of the spec (roadmap 083 `bodies:`, `isaaclab-articulation`,
  from `effective(spec, body)`), wheels as joints, stepped as tensors. Its tyre and contact model
  differ from PhysX's vehicle one, so its gap to A is a named body difference. It is the
  throughput path (K2.5), and the side comparable with WheeledLab (094), which also drives an
  articulation car; A is what seats fidelity costs.

**A measured** (139, 2026-11-21; contended: other users' jobs held the GPU at 96-98 % and 12.3
GB, so the timings are an upper bound, to measure again in a clean window). The smoke
(`scripts/smoke_physx_vehicle.py`): N cars on a ground plane, 150 N m on each wheel, 4 s at
240 Hz.

| N | pass | ms per step | per car | of it: actuate | PhysX step | sample |
|---|---|---|---|---|---|---|
| 1 | yes | 1.4 | 1381 µs | | | |
| 4 | yes | 4.6 | 1156 µs | | | |
| 16 | yes | 9.8 (10.4) | 612 (609) µs | 51 | 143 | 414 |
| 64 | yes | 38.1 | 596 (593) µs | 51 | 139 | 403 |

Pass means every car moved as one: the same distance to 0.08 mm (float32 at the grid's
offsets) and the same speed (3.267 m/s). Peak GPU memory, every user's: 15.4 GB of 32.
Reading the cars back (`Vehicle.sample`: a pose and a tensor-view velocity per car, four wheel
states) is two thirds of the cost. A rigid-body view over all the cars would batch the pose
and velocity; the wheel states stay per car. At about 0.6 ms per car, A is for agreement at
small N (K2.4), not for training.

**A is CPU physics by nature.** PhysX's vehicle constraints are not GPU-compatible: Isaac
Lab's direct-GPU pipeline refuses them ("non-GPU compatible PxConstraint") and the CPU velocity
setters A's reset uses. The environment (`env.py`) therefore runs A with `device="cpu"`, as
aib's runner does, with scene queries on. Engine A needs exactly two settings beyond Isaac Lab's defaults:

- `device="cpu"`: PhysX's vehicle constraints are not GPU-compatible (above);
- `enable_scene_query_support=True`: a PhysX vehicle finds the ground by raycasting each
  wheel, and Isaac Lab turns scene queries off by default. Without them the env smoke's
  steer (0.051/0.049 rad for 0.05) and wheel spin reached PhysX but every wheel was off the
  ground, tire force 0, and every ego coasted to rest on its body.

Fabric is not one of them: with scene queries on, `use_fabric` True and False gave the same
run to the last digit (egos 5-8 m/s to 7-10 m/s in 2 s, about 480 N per tire), so it stays
Isaac Lab's default. `scripts/smoke_env.py` asserts the read-back from PhysX (wheels on the
ground, front ones steered, tires pushing, egos sped up) and exits non-zero otherwise;
`--fabric on|off` overrides the setting. Only B runs on the GPU pipeline; 094's rate comparisons with stock
are B's.

**B, `articulation`** (K2.2b): the car from sim_vehicle_spec's neutral body file,
`generated/<car>/articulation[_<body>].yaml` (sim_vehicle_spec.articulation, on `effective(spec,
body)`; no simulator in it), which `scensim_batch.articulation` turns into a USD stage
(`write_usd`, pxr only) and an Isaac Lab `ArticulationCfg` (`articulation_cfg`: the joints'
drives as actuators, self-collisions off). The chassis hangs on four prismatic suspension joints;
the front corners steer on revolute joints; the wheels spin on revolute joints. The actuation is
the component's (`drive`, `brake` [N, 4], `tire_angle` [N]), as A takes it, written as joint
targets in one call per step (`vectorised = True`). `apply_joints` bypasses the component
(steer and spin targets straight to the joints: 094 P2's second measurement, and the only way
into a velocity spin drive, an RC car's).

What makes B a different car from A (and seats), each named here and in the body file's
`choices:`:

| | A (seats' PhysX vehicle) | B (articulation) |
|---|---|---|
| tyre | PhysX's tire model: slip curves, load sensitivity | a rigid cylinder in Coulomb contact, `tires.friction` per axle times the ground's; no slip curve, no load sensitivity |
| drivetrain | PhysX's, the component's torques per wheel | none: the component's torques straight on the spin joints |
| brake | PhysX's wheel brake | an explicit torque with stiction: full torque while the wheel turns, never reversing it, holding it at rest; what turns with the wheel (its share of the car when gripping) estimated from the step before, and the wheel alone whenever its tyre carries no load (the suspension's spring force) or slides (243) |
| steer | PhysX's wheel steer angle, set | a stiff position drive per front wheel (the front tyre's largest scrub torque moves it 1 mrad), Ackermann angles from the bicycle angle |
| suspension | PhysX's sprung masses | a prismatic spring-damper per corner (the spec's ride frequency and damping), preloaded to rest at design height |
| masses | PhysX's vehicle | the chassis box plus 0.8/0.1/0.1 (rear 0.9/0.1) of `wheels.mass` per corner at the hubs; the whole car's centre of mass the spec's |
| physics | CPU only | CPU or GPU pipeline |

**B measured** (139, 2026-11-21; contended: other users held the GPU at 97 % and 11.5-14 GB, so
the timings are an upper bound). `scripts/smoke_articulation.py`, tesla_model3 (carla-0.9.16
body), ground friction 1.0, 240 Hz: 400 N m on each rear wheel for 4 s, then 1500 N m of brake
on every wheel to a stop, then a constant 0.15 rad bicycle angle at about 4 m/s for 8 s.

| device | N | straight: v after 4 s | brake: decel | steer (FL, FR): target / read back | circle radius / bicycle L/tan | ms per step |
|---|---|---|---|---|---|---|
| cpu | 1 | 4.794 m/s | 8.28 m/s² | 0.1565, 0.1440 / 0.1546, 0.1435 | 20.22 / 19.88 m | 0.62 |
| cuda:0 | 4 | 4.795 m/s (x 9.593-9.595 m) | 8.22 m/s² | 0.1565, 0.1440 / 0.1554, 0.1427 | 20.03 / 19.88 m (spread 0.03) | 45.8 |

Every check passes on both pipelines: the cars moved as one, straight (|y| < 1 mm), with the
driven wheels' torque read back from the actuators (400 N m) and rolling at v/r to 0.2 %; they
stopped; the steer joints reached their Ackermann targets to 2 mrad; and the turn is 1-2 %
wider than the bicycle's at 0.85 m/s² of lateral acceleration. The straight-line speed is the
torque's (800 N m at r 0.37 on 1760 kg and four wheels' inertia: 1.20 m/s², 4.80 m/s in 4 s).
Two defaults changed on the way, both from this smoke: the steer drive (a 10 Hz drive on the
knuckle's inertia let the outer wheel lag 0.037 rad: a 27 m circle for 20) and the brake (a
clamp to what stops the wheel alone left a slow tail near standstill: 4.75 m/s² for 9).

The GPU step is not a throughput number: N = 4 on a GPU at 97 % from other users, and the
backend reads the state back to the CPU every step (BatchRun's contract is CPU tensors). K2.5
measures B's throughput in an exclusive window, with the actuation and read-back kept on the
device.

## 6. The compiled storyboard and the truth export (K2.3)

`scensim_batch.storyboard` compiles a scenario's Story, Act, ManeuverGroup, Maneuver, Event and
Action elements into one state machine over N slots, every element's state an [N] tensor, and
ports SSv2's interpreter where it and the OpenSCENARIO text differ (its module docstring lists
each point):

- `StoryboardElement::evaluate`: an element's stop trigger first, then standby, start, running,
  end (back to standby while executions remain), complete, re-dispatched within one tick; a
  stop transition overrides and evaluates every child. An overriding Event overrides every
  event of its maneuver, itself included (its stopTransition fires), and restarts its actions.
  One difference no condition can see today: SSv2's ManeuverGroup::start sends every
  maneuver to its startTransition, complete ones included, so a group's second execution
  re-runs its (already complete) maneuvers, emitting their transitions and counting their
  executions; the batch leaves them complete. Its state-condition latches are one-way and
  set by the first execution, so nothing reads the difference (243).
- `Condition::update_condition`: each evaluation appends (time, value); the value used is the
  newest entry at least `delay` old; an edge compares it with the one before. A start trigger
  appends only while its element is in standby. The test checks the batched form against a
  line-by-line scalar port on random per-slot sequences, masks and delays.
- The rules: equalTo within machine epsilon, notEqualTo exact; standstill |v| <= epsilon; a
  lane-coordinate distance signed; a StoryboardElementStateCondition latched once seen.
- SpeedAction on SSv2's default vehicles, as `EntityBase::requestSpeedChange` does it: step
  sets target and speed; linear (cubic and sinusoidal map to linear in SSv2) sets the
  acceleration and the acceleration or deceleration limit to the rate until the speed passes
  the target, then resets the limits; a time dimension takes the rate (target - v) / T; a
  distance dimension sets only the target.
- The end: exitSuccess and exitFailure end their slot (Isaac Lab's `terminated`). A storyboard
  that completes or is stopped ends nothing, as in SSv2, where only the test runner's timeout
  ends such a run; the environment's episode length plays that role (`truncated`).

The storyboard ticks at reset (time 0) and after every step, on the state the step left.

**Scenario time** is SSv2's `SimulationClock::getCurrentScenarioTime`: A(S + k) - A(S), A the
step (`realtime_factor / frame_rate`) summed in a double from the node's start, S the frames
before `startNpcLogic`. The fork's `clock_source:=simulator` moves ROS time onto the world's
integer `sim_time_ns` and leaves scenario time as it is, so a SimulationTimeCondition on seats
reads the summed double. Which frame first passes a boundary depends on S (t > 1 at 0.05 s:
frame 20 or 21), and S differs between seats runs; `BatchRun(start_frames=S, step_time=dt)`
reproduces a given run's, and K2.4's seats comparison has to carry it from the run: the
truth's frame lines say `npc_logic_started` (from the status that staged each frame), and
`scensim.truth.start_frames` counts S from their frame numbers. SSv2's tick S starts the clock
and sends that status, and evaluates the storyboard first in tick S + 1, at scenario time dt;
BatchRun.step advances the clock and then evaluates, so its first evaluation is at dt too
(243).

**The route goal.** Under `--ego policy` the ego's AcquirePositionAction and AssignRouteAction
(Init or story) are the policy's task, not actions to execute (133): the slot's
`obs["route"]` holds the route polyline (the world adapter's `route_through`, else the chords
through the waypoints), the goal pose, the ego's progress along it, the distance left and to
the goal, and `goal_reached` (within 1 m, latched) with its onset `goal_reached_now`. The ego's
FollowTrajectoryAction would drive the ego over the policy: refused (seats). Another entity's
routing executes, and is executor pending.

**Lane changes** (`storyboard.LaneChangeAction`, `npc.DefaultVehicles`) are SSv2's
LaneChangeAction under its FORCE policy, the only one the interpreter sets: the shape linear
is LINEAR and every other (cubic, sinusoidal, step) CUBIC; the dimension time, rate and
distance are TIME, LATERAL_VELOCITY and LONGITUDINAL_DISTANCE. At the action's start the curve
is `route::laneChangeTrajectory`'s: the pose 20 m along the lanelet (the distance for a
distance dimension), the target centreline's crossing between offsets +5 and -5 there, the
goal at that s and the target offset, a Hermite curve with tangents of half the start-to-goal
distance (CUBIC: the start heading and the target lanelet's spline tangent; LINEAR: the
chord), its length `HermiteCurve::getLength(100)` as written. The vehicle then moves at the
forced speed (length / T; length / (lateral offset / rate); the current speed), clamped by a
SpeedAction's target, along the curve at u = s / length, and past its end is put on the target
lanelet at the overshoot plus the target s, offset 0, with a route from there. The action is
accomplished as it starts, as in SSv2, whose check reads the behaviour tree's last tick, which
ran before the request. The ego's LaneChangeAction would steer the ego: refused under `--ego
policy`. The map queries are the world adapter's: `lanelet_pose(x, y, yaw)`,
`adjacent_lane(lane, direction, shift)`, `can_change_lane(from, to)`,
`along_lanelet(lane, s, distance)`, `collision_s(lane, p0, p1)` and `tangent(lane, s)`; on a
real map they must be SSv2's (its Catmull-Rom centreline spline, whose tangent is a raw
derivative, not a unit vector), which K2.4 checks on Town01.

**In Isaac Lab** (`env.py`) the step's world is made in `_get_dones`, the first hook after the
physics in DirectRLEnv.step (dones, rewards, resets, observations, in both Isaac Lab 2 and
3.0.0-EA): the last substep read back, the default vehicles moved, the storyboard ticked; so
dones, rewards and observations read the same step, and `BatchRun.reset` merges a reset slot's
observation in without touching the others'. Users override `rewards()` and `dones()`. Ten conditions, SpeedAction and the exit commands
run; every other batch row is executor pending (compilable-subset.md section 8), which the
checker and `compile` both name.

**Truth** (`scensim_batch.truth.TruthRecorder`): every step's entity states per slot, written
per slot and episode as `slot_<k>_ep<e>/truth.jsonl`, a schema-2 truth file that
`scensim_launch/scripts/gap_trace.py` reads, with `sample.json` (the slot's record: the replay
on seats) and `outcome.json` (how the episode ended, the storyboard's state, the seed). The
ego's values are the engine's (`measured`); the default vehicles' and props' are the batch's
(`derived`, `kinematic`); contacts are the ego's box overlaps at onset, impulse unknown.

Measured on CS2 at two samples (onset 60 m at 6.5 m/s^2, 90 m at 3 m/s^2, point-mass engine):
each lead brakes in the tick after it is within 1 m of its own onset, never beyond its rate,
stops at exactly 0 m/s, and gets SSv2's default deceleration limit back; the stop trigger
completes both storyboards at 30 s.

## 7. The world adapter on a Lanelet2 map (K2.6)

Every map query the batch makes (compile's lane positions, SSv2's default vehicles' routes and
speed limits, the storyboard's lane changes) goes to a world adapter. On a real map it is
`scensim_batch.world_lanelet.LaneletWorld`, answering as SSv2's traffic simulator does, from an
export of the map, since lanelet2 is not in Isaac's Python:

    python3 -m scensim_batch.map_export <map dir> -o town01_map.json      # system Python, lanelet2
    world = LaneletWorld.load("town01_map.json", map_dir=<the map in use>)

The export (`map_export.py`'s docstring is its specification; format
`scensim-batch-lanelet-map` v1) holds what the map says: per lanelet its centre points
(lanelet2's `centerline()`, a two-point one given its midpoint, as SSv2's cache does), bounds,
subtype, turn direction, the vehicle routing graph's followers, predecessors, lane-change
neighbours and adjacent lanelets (Germany's vehicle rules, SSv2's VEHICLE graph), and the
speed limit; and `map_sha256`, over the map's `lanelet2_map.osm` and `map_projector_info.yaml`.
`load` refuses an export whose digest is not the map's in use, so a stale export is never
used silently.

The geometry is SSv2's, ported line for line: each lanelet's Catmull-Rom spline of Hermite
curves (its length the 100-step sum, s mapped to the curve's parameter linearly), its
polynomial solver (tolerance 1e-7, the real roots of the monic cubic), the curve-segment
crossing (and its rule that accepts a crossing when either axis' parameter is in range),
`getSValue` along the pose's own y axis, `toLaneletPose` (the five nearest lanelets within
0.1 m, crosswalks and untagged lanelets dropped, the first whose spline the pose's ±1 m axis
crosses within 45 degrees of its heading either way), `followingLanelets` (the straight
follower first, else the first) and a route's spline through the lanelets' centre points
joined. The tests check it against SSv2's own spline tests' values (`getSValue` to 1e-11 of
SSv2's `EXPECT_DOUBLE_EQ`, the trajectory and its offset to 1e-6) and the solver against
numpy.

Named differences: the lanelet pose ignores an entity's bounding box (SSv2's `matchToLane`
runs first for one) and the altitude check (the batch is 2D); lanelets equally near a point
(two overlapping at 0 m) are taken in the export's order, where lanelet2's R-tree's may differ. The
routing graph is lanelet2's plain Germany/Vehicle one; SSv2's default is
VEHICLE_WITH_ROAD_SHOULDER (its own RoadShoulderPassableGermany rules), so on a map with
`road_shoulder` lanelets following, previous, left and right can differ (243). Town01 has none.

`LaneletWorld.from_polylines` is a world of polylines with the same interface (094 P2's oval
track: one lanelet that follows itself).

On Town01 (CARLA's Autoware map, 300 lanelets, 169 roads): no lanelet has a lane-change
neighbour (each road has one lane each way), and some curved lanelets have a two-point
centreline in lanelet2 itself (36200: 26-point bounds round a corner, a straight centre line),
which SSv2 reads the same, so its vehicles cut that corner on seats as they do here.

## 8. Agreement with seats (K2.4)

A seats run and a batch replay of it, compared frame by frame (`scensim_batch.agreement`,
`scripts/agreement_run.py`; the project `scenarios/projects/k24_agreement`). The seats ego is
`replay_pilot` on a fixed command file, each Control stamped with the clock of the frame it
answers; the truth records, per frame, the command the ego's vehicle ran (`command`,
`truth-stream.md`). The batch replays exactly that: what ran, not what was sent. It pre-rolls
its ego through what ran in the trace's lines 0..S, NPCs held and the storyboard idle
(`BatchRun.reset`'s `preroll`), as seats drives its ego before `startNpcLogic`; then step k
runs line S + k + 1's command. Frames pair on scenario time (seats frame S + k is batch step
k). Per entity: max and RMS position error (the simulator's pose for the ego, SSv2's for the
NPCs) and the max yaw error; per storyboard element: the step it first ran on each side;
the two outcomes; the delivery (frames between a command's stamp and the step it ran in,
commands superseded or run again).

What it took, each read from a seats run:

| | cause | fix |
|---|---|---|
| ego 9 m apart | the pilot's hold before command 0 had the seats brake pressed (sim_vehicle_ecu releases in ~0.3 s); a fresh batch component was not | the ego pre-roll |
| lead turned the other way | map_export built the routing graph after moving the map's points, reordering 20 of Town01's 36 branches | map_export v2: the graph on the parsed map, checked against SSv2's own lanelet_wrapper (0 of 300 differ) |
| elements started 2 steps early | the storyboard log's time is after the step, except an exit's (published before the update, at the evaluation's time); SSv2's first evaluation is at dt (the batch evaluated at 0 too); SSv2's storyboard sees the ego two frames before the frame its tick makes (`time-and-ticking.md`) | `context_steps` less a step, not on an exit's lines; no evaluation at reset; the storyboard reads the ego two steps back (243) |
| a following default vehicle 0.9 m off | SSv2's tree resumes FollowFrontEntity (a BT.CPP Fallback is not reactive), where the port re-tested the hand-off each step; SSv2's vehicles see the ego two frames back per world frame; SSv2's front distance is from each box's centre | following kept while a front entity is found; the vehicles read the ego two steps back; the boxes' centres (243) |
| lead 0.36 m, 0.27 rad off in the turn | the route sampled every 5 m and followed chord by chord | a Catmull-Rom cubic on samples 2.5 m apart, arc length the spline's |

The rows (Isaac, engine A, `allow_loop`, one slot; seats on newslab-server139):

| scenario (Town01) | outcome | ego max / RMS | NPC max / RMS / yaw | element offsets | delivery | pre-roll |
|---|---|---|---|---|---|---|
| follow_to_goal (the ego at 1.23 m/s behind a 4 m/s lead; the lead through a turn) | passed / passed | 0.9 mm / 0.9 mm | lead 2.8 cm / 1.4 cm / 0.035 rad | all 0 (goal at step 1263 both) | 1271 of 1271 at delay 0 | 10 steps |
| k24_npc_stops_for_ego (the ego to ~2.7 m/s, braking to a stop at 13 s; a default vehicle 20 m behind at 6 m/s) | passed / passed | 2.4 mm / 2.2 mm | follower 2.6 cm / 2.3 cm / 0 | all 0 (time-up at step 600 both) | 608 of 608 at delay 0 | 10 steps |

A correction (2026-11-22): this section first said, as it landed in f9b0b95d,
that follow_to_goal agreed on every column with its goal "at step 1262 both". The step was a
log line read wrong, not an agreement: the batch took a step off every storyboard log line,
an exit's too, whose time is the evaluation's own, so seats' goal (tick 1263) read as 1262;
and the batch's storyboard then saw the ego one step too fresh (the previous step's, where
SSv2's is two back), which fired its goal at 1262 as well. Both are fixed; the true first row
is the one above, the goal at 1263 on both sides.

The follower, as each fix came in (k24_npc_stops_for_ego, max / RMS): the port as it was,
0.90 / 0.54 m; following kept (BT.CPP's Fallback), 0.199 / 0.126 m; with the vehicles seeing
the ego one step back, 0.159 / 0.101 m; two steps back, 0.072 / 0.050 m; and the boxes'
centres, 0.026 / 0.023 m (the step counts as 139 measured them on 2026-11-22, before the box
centres but the last).

Open: k24_distance, whose 8 m never fired on seats (the follower stops 11.55 m off: its
threshold moves to 12 m); engine B's column; the Hermite case on Town10HD (CARLA).

## 9. Device-resident (K2.2c)

Engine B on a GPU sim with `ScensimEnvCfg(device_resident=True)` keeps the batch on the
device: the scenario compiled there, BatchRun's tensors there (its methods run in torch's
device context), the car model and its read-back there (`ArticulationBackend(resident=True)`),
and the control component on torch there (sim_vehicle_ecu's `array_api`, its batch written
once over `sim_vehicle_ecu.xp`). The CPU path is the reference and stays: a numpy component on
a device run gets host arrays each step, the CPU contract. Checked against it:

| check | where | agreement |
|---|---|---|
| the VESC component (roboracer_vesc) alone, 1500 random steps, 8 and 32 cars | numpy, torch CPU, torch CUDA | bit for bit |
| BatchRun on cs2 (a default lead, a braking storyboard), 120 steps, a point-mass backend | CPU and numpy, cuda and torch | poses within 2.8e-14 m, speeds equal, storyboard states and outcomes equal |
| engine B through ScensimEnv, the RoboRacer body and its VESC, 4 cars, 290 steps (`scripts/check_resident.py`) | the CPU path and resident, one GPU sim | x and y equal, yaw within 1.1e-16, v 2.2e-16, outcomes equal; 97 against 188 ms a step, contended |

Engine A stays on the CPU path (PhysX's CPU pipeline).

A device run checks every `sync_every` steps (BatchRun's, default 16); the steps between bring
nothing to the host. There the storyboard's branch tests (an element skipped when no slot is in
its mask) run as masked work instead, which gives the same result; an element of one execution
makes one pass, one of more makes all its passes, and one past its executions in a tick is a
device flag. Its children are evaluated once over its running and stopping slots together
(disjoint, each step masked per slot), not once a branch: two would evaluate every level twice,
2^depth evaluations of an action under a storyboard with a StopTrigger (243's review found the
cost; 64 of the lane-change test's action a tick). `test_lazy.py` runs test_storyboard's and
test_core's cases again with every run lazy on the CPU (`sync_every` given): all pass. An
element of k executions still makes its k + 1 passes on a lazy tick, each over its children,
so nested repeating elements cost (k + 1)^depth evaluations a lazy tick (all of one execution,
the common case, cost one each). The actuation's check (finite, brakes not negative) is a device flag too; the
shapes are still checked on the host each step, which costs nothing. Both flags are raised at
the next check, naming the steps since the last ("sync_every=1 names the slot"). A condition's
history drops its unused entries at checks only. Measured with torch's sync debug mode
(`test_device.py`, `check_resident.py --sync-count`, 2026-11-22):

| configuration | host syncs a step between checks |
|---|---|
| 094 P2's: an ego alone, a time-up exit, the VESC on torch (`test_device.NoHostSync`) | 0 (asserted: the debug mode raises) |
| engine B through ScensimEnv, the same, 4 cars, 269 steps | 0 of ours; 1 of Isaac Lab's (DirectRLEnv's `reset_buf.nonzero()`, which a task may override with a masked reset) |
| cs2 (a default lead, a braking storyboard) | 2.5: SSv2's running distance, its planner looped until every vehicle has reached its target (asked every 8th iteration) |

An action that starts on the host (a lane change, a route goal in a story) costs a sync each
time a lazy tick asks whether a slot starts it, twice a tick (from its event's start and its
own evaluation), until a check finds it settled: in every slot its event complete (an event
leaves COMPLETE only by a reset), or an element above it complete with nothing above that
executing more than once, or the slot's outcome decided. Not the action's own COMPLETE:
Event::start restarts its actions (243; `test_lazy`'s event of two lane changes, the second
after a check, starts both on the lazy run as on the eager). Then none (`test_device`'s story lane change: 2 a tick
before, 0 after). Still synced as before: a lane change's curve, its end and its route, a route
goal's route (all on the host), and a partial reset (its indices).

A gap of the port, found here and not of the lazy ticks: SSv2's ManeuverGroup::start restarts
its maneuvers (startTransition) on each of the group's executions; the port restarts only an
event's actions (Event::start), so a maneuver of a group of more than one execution stays
COMPLETE. Its events are not restarted either way (an event is restarted only from its own
STANDBY), so what runs is the same; the maneuvers' states in the storyboard log differ.

At 4 cars the resident path is no faster than the CPU path (184 against 65 ms a step, the GPU
contended): every masked step is a kernel launch. Its case is a large N, which P2 measures.
