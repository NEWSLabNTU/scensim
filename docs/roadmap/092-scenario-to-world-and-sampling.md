# Phase 092: Scenario to world, and sampling

Turn a declared scenario into a world on a chosen target (an Isaac Lab batch for training,
Isaac Sim or CARLA on seats for evaluation), and sample scenarios with an identity that
replays across targets. Published as adaptable components and specifications, not a
framework; Isaac Lab keeps training throughput.

**Status**: design accepted for now (user, 2026-11-20: "The shape is better ... Accept the
decision for now"); the scenario-to-world compiler is being studied further before any work
item starts.

**Source**: feedback from a RoboRacer team after the scensim presentation, 2026-11-20 (Jazzy;
hand-set-up runs; slow data between autopilot, simulator and ML infrastructure), and four
rounds of review with the user the same day.

**Design**: [ml-training-interface.md](../design/ml-training-interface.md) (revision 4):
the contributions C1 to C5, decisions D1 to D12, the layers, the architecture and workflow,
throughput against Isaac Lab, usage by user.

**Studies**: [survey-risk-categories.md](../design/survey-risk-categories.md): known risk
categorisations (NHTSA pre-crash typology, PBCAT, Euro NCAP, UN R157, JAMA and ISO 34502,
SOTIF, Waymo's collision avoidance testing, accelerated evaluation) and a coverage model for
the two purposes the user chose (2026-11-20): a realistic risk rate, and failure-mode search.
Scenario and world stay separate concepts, joined by the compiler (user: option A).
[survey-vehicle-risk-taxonomy.md](../design/survey-vehicle-risk-taxonomy.md): the whole space
of vehicle risk in eight families (traffic conflicts, VRUs, infrastructure and maps,
perception, vehicle motion, the ego's own faults, interaction, ODD boundaries), what a
scenario must express for each, three layers of coverage and realism per family.

## Work items

From the design's section 10.

| Item | What | Kind | Depends on | Owner | Status |
|---|---|---|---|---|---|
| S1 | The sample record: schema, hashing, checker ([sample-record.md](../design/sample-record.md)) | spec | none | swb 139 | done (scensim_sampler) |
| S2 | The compilable subset of OpenSCENARIO ([compilable-subset.md](../design/compilable-subset.md), `scensim-sample compilable`) | spec | the compiler study | swb 139 | done; SSv2's examples: 58 of 83 compile with the ego as the batch's policy (18 unconditionally), 41 with `--ego seats`; 093 D7 gap 8: LaneOffsetAction, RelativeLanePosition, TraveledDistanceCondition refused as unimplemented in SSv2 (re-measured: counts unchanged) |
| S3 | The batched control component (`step_batch`; roboracer-indoor-twin.md 2.6, sim_vehicle_ecu.batch) | spec | 091 | swb 139 | done (sim_vehicle_ecu d575758); follow-ups: `ideal`/`ev` vectorised (they run as LoopBatch, flagged), and the roboracer stand-in VESC (091 W23) converted to the array form once W23 lands, with 118 |
| S4 | The stage record (091 W15) and the truth stream's content ([truth-stream.md](../design/truth-stream.md)) | spec | 091 W15 | swb 243 | done 2026-11-21: the stage record is 091 W15's `provenance.stage`; the truth stream is the gap trace at schema 2 (file, by default; the simulator's values under neutral names, read by schema) and `/scensim/truth` (on request), from the bridge, no world-protocol change; route progress and occlusion named as later capabilities |
| K1 | The sampler (pure Python): `src/scensim_sampler`, `scensim-sample` | component | S1 | swb 139 | done (`scensim-sample`) |
| K2 | The Isaac Lab adapter, with `scensim bench` ([batch-executor.md](../design/batch-executor.md), `scensim_batch`) | component | S1, S2, S3, 091 W5 | swb 139 | in progress: K2.0 (the Isaac Lab overlay; v3.0.0 on Isaac Sim 6.2 since 095 M3) and K2.1 (SSv2's default vehicle behaviour in torch) done; K2.2 landed; K2.3 (the compiled storyboard, truth per slot) landed in part, reviewed against SSv2 (243) except the lane change's Hermite curve construction and its goal at the ±5 offset, which were not independently reviewed and are checked against SSv2 on Town01 in K2.4; K2.2b, engine B (the articulation car from sim_vehicle_spec's neutral `articulation_<body>.yaml`; batch-executor.md section 5 has its differences from A and the smoke), landed (243 reviewed it; its smoke accepted, 133); K2.6, the batch world adapter on a Lanelet2 map (133, 2026-11-21: its own item, since every batch scenario on a real map needs it): any map directory exported once in system Python (`scensim_batch.map_export`: a documented JSON of lanelets, centrelines, bounds, followers, neighbours, speed limits and the map's sha256), `world_lanelet.LaneletWorld` answering the batch's map queries from it as SSv2's traffic simulator does (its Catmull-Rom spline, solver, getSValue, toLaneletPose and followingLanelets ported), refusing an export whose digest is not the map's in use, and a polyline world with the same interface for 094 P2's track; landed (243 reviewed it); K2.4 needs it and compile's catalog entities and empty controllers (SSv2's default vehicle), landed with it, since the S2 case studies are on `maps/town_street`, not a map seats runs, so K2.4 runs the Town01 scenarios that compile (30 of 57: ego-only drives, follow_to_goal, town01_npc_10/20/50 and others); K2.4's step 1 landed with them: the truth records S (each frame's npc_logic_started, `scensim.truth.start_frames`) and `replay_pilot` is the scripted ego, both reviewed (243); K2.4's first two rows landed (2026-11-22; batch-executor.md section 8, with its correction of the first text's "goal at step 1262 both"): follow_to_goal and k24_npc_stops_for_ego on engine A, every storyboard element on seats' step, the ego within 2.4 mm, the NPCs within 2.8 cm, after the truth's taken command, the ego pre-roll, SSv2's storyboard and vehicle timing (time-and-ticking.md), map_export v2's following order, the route's cubic, and K2.1's following kept (243); K2.2c landed with them (section 9): sim_vehicle_ecu's array namespaces and roboracer_vesc on torch, BatchRun, engine B and the env resident on a GPU, each against the CPU path; then (133, 2026-11-22) 094 P2, then K2.4's remaining rows; the order before (133, 2026-11-21): K2.4, the agreement table on Town01 (each S2 example that compiles: a seats run with S recorded against the batch with start_frames=S on A, B as an extra column; verdict, trajectory error, trigger times; engine A on the CPU contract); then K2.2c, the device-resident path for engine B, 094 P2's prerequisite (BatchRun's actuation, read-back, storyboard and truth as torch tensors on cuda, and the control component's torch form under S3's array_api contract, the drift task's component first; each checked bit-close against the CPU path, which stays the reference: a CPU contract and a numpy component sync every step, which would make ours slow for a reason stock does not have); then K2.3's remainder below; the S2 rows it does not run yet listed as executor pending in the checker; K2.3's remainder, in order: other entities' FollowTrajectoryAction (SSv2's follower and waypoint controller, a scalar port first; after 095 M3), then SpeedProfileAction (its SSv2 example drives in reverse), RelativeClearanceCondition (lane-graph clearance from the world adapter), RoadCondition (per-slot friction: needs engine B), TrafficSignalStateAction and TrafficSignalControllerAction (need SSv2's StopAtTrafficLight behaviour); acceptance includes running each S2 "batch" row against seats on the same sample; the v3.0.0 GA follow-up is closed by 095 M3 (warp-lang 1.17.0, Isaac Lab's pin) |
| K3 | Replay of a sample record on seats, fidelity measured: `sample:`, `run --replay`, `runs fidelity` | component | S1, K1 | swb 139 | done; measured 2026-11-21 on CARLA 0.9.16 (Town01, simple pilot, 5 records + 5 replays): 5 of 5 same outcome, but all 10 passed, so the measure did not discriminate, and the ego was a stack pilot (its seed not applied); then a discriminating set (time_limit U(8,14) s, goals 46-79 m, n=10, the ego a lifetime: run pilot so the record's seeds applied): 8 passed, 2 failed on their time limit, and 10 of 10 replays reached the same outcome, both failures on the same simulation tick (9.25 s, 10.20 s); no contact case yet |
| K7 | The coverage report: `scensim-sample coverage`, `scensim runs coverage` (sample-record.md section 8): category, condition (t-wise) and criticality coverage, an exposure-weighted overall rate only with the study's own weights | component | S1, K1 | swb 139 | done; **open**: under heavy weights (n_eff/n < 0.1) the weighted interval under-covers, down to 0.61 at nominal 95 % (measured; the spec's table), which matters for purpose A (realistic risk rates); to evaluate later: a bootstrap over records, or an exact-style interval on the effective counts |
| K4 | The truth stream, judge and attachment hooks, the paced clock | components | S4 | swb 243 | done 2026-11-22: the truth file done 2026-11-21 (the gap trace at schema 2 from the bridge, recorded by default, read by schema by `gap_trace.py`, the gap oracle and `incident_judge`); `/scensim/truth` and `/scensim/truth/entities` (latched) from the bridge with `logging.truth_topic: true` or any attachment (scensim_interfaces' Truth messages); the judge hook (`scensim.truth`, the closest-approach judge, box to box) and attachments (`attachments:`, per run, the scenario domain, `required`, `lockstep` on CARLA's tick gate) done 2026-11-21; the paced clock done 2026-11-21 (`clock: {mode: lockstep|paced, max_lag_s}`; the bridge's `wall_ns` per frame in the truth file, the lag in `result.json`'s `clock` in either mode, a paced run over budget an error run; every error run's `error.kind`, counted by kind in the coverage report); exit runs on CARLA 0.9.16 done 2026-11-21 (243; bench's town01_npc_20, 20 NPCs, 1200 frames, a loaded host, alternating runs): truth's cost +0.1 to 0.3 ms per frame at p50 and p95 against truth off (bridge processing p50/p95 0.62/0.91 and 0.65/0.98 ms off, 0.71/1.09 and 0.84/1.23 ms with truth and a lockstep attachment), within 1 ms; the lockstep attachment saw all 1202 truth frames, as the truth file has them; both paced runs error runs (lag final 241 and 250 s), since SSv2 itself ran at a median 232 ms a frame (time-and-ticking.md: seats throughput is SSv2's); the tick gate waited for each spawn's settling tick, which no truth frame names (a 5.3 s frame 2 in every lockstep run), fixed: the gate waits once per step (scensim_carla_world); a passing paced run on CARLA 2026-11-21 (bench's town01_npc_10 cut to 2 NPCs, max_lag_s 0.05: lag max 0.025 s, 0 of 1202 frames over, ok true), after the tick gate fix; exit runs on Isaac Sim 6.2 2026-11-22 (243; town01_npc_20, 1200 frames, install c95c80ca's tree, play_launch 0.41.2): truth's cost 0.0 to 0.1 ms per frame at p50 and 0.25 ms at p95 (bridge processing p50/p95 0.65/1.04 and 0.78/1.04 ms off, 0.76/1.29 ms with truth and an attachment), within 1 ms; the attachment saw all 1202 truth frames (no tick gate on Isaac: the frames as published); both paced runs error runs (lag final 263 and 260 s), SSv2 at a median 248 ms a frame; the second Isaac truth run not run (the VRAM guard stopped it, the card held by another user's jobs). So on CARLA and Isaac: truth within 1 ms a frame, every frame seen, a paced run refused when SSv2 lags and passed when it keeps up, the tick gate waiting once per step |
| K5 | GPU transport for evaluation (NITROS first) | component | none | | open |
| K6 | Jazzy for the whole set | all | 082 | | open |
| K8 | 093's description rules (scenario-description.md section 2a): `latent: true` model variables (gap 2), `scensim.present` optional entities (3), `scensim.static` stopped vehicles (4), `isBlind` in the subset with lane following as its condition (5), a per-sample entity class conditioned on per-slot assets (6), anchor attributes in derived values (7, with K9) | spec, component | S1, S2 | | done 2026-11-22 but gap 3 (swb 243): gaps 2, 4 and 6: latent variables in the record's `latent`; `scensim.static` with SSv2's `maxSpeed = 0`, a batch prop (scensim_batch: executor pending); a parameter in an entity's class or model a condition naming it and its values (SSv2's examples' counts unchanged); gap 5: a blind default controller's condition is SSv2's lane following alone (executor pending in the batch); gap 7: `anchor.<name>.<attribute>` in derived values, from `testbench.yaml` `world.anchors` (lane heading, length, speed limit; point x, y), recorded in the record's `anchors`, CS7's `exit_heading` stand-in gone (the rest of anchors is K9); gap 3 (`scensim.present`) open, needed by neither case study |
| K9 | 093 D2's world interface beyond knobs: anchors (lanes, regions, conflict points, curves) declared by a world and checked by `testbench check`, knob profiles (`profile: true`, CS5), the pilot's map variants (`maps.pilot_variants`, CS3) | spec, component | K1 | | in progress (swb 243): K9a done 2026-11-22, a map's lanes: `<map dir>/anchors.yaml`, resolved by the map's author with `python3 -m scensim_batch.anchors resolve` (torch) into `anchors.resolved.json` (length, speed limit, ends, a heading table within 1e-3 rad in SSv2's arc length, the map's digest), read by the sampler and scensim with ROS 2 alone and merged with `world.anchors`; `anchor.<lane>.heading(s)`; the record's `anchor_source`; Town01's anchors (west_street, west_left_turn) published 2026-11-22 as the maps dataset's revision deb23e3a, tag v2026.11d, with the user's OK; every testbench's lock on it; K9b done 2026-11-22: FileHeader `scensim.anchor.<parameter> = <anchor>.<attribute>` or `<anchor>.<function>(<arg>)`, `$<parameter>` for a drawn anchor or argument; resolved lanes gain `lanelet_at(s)` and `local_s(s)`, a stated lane its `lanelet`; the sampler checks bindings before drawing and rejects a draw off its lane by name; `scensim run` sets a scenario's bound parameters before SSv2 starts, checks a record's against the world, refuses a given value and SSv2's own distribution of a bound scenario, and records `result.json` `anchors`; `compilable` refuses a named laneId with the binding as its fix; CS6 and CS7 bind their lanes. K9c done 2026-11-22: conflicts (two lanes crossing once: `s_<lane>`, `x`, `y`, `angle`, `position_error`), curves (`length`, `turn`, `direction`, `min_radius` over 2 m, `mean_radius`) and regions (polygon: `area`, centroid, each lane's `from_`/`to_`) resolved from the map's file; Town01's conflict west_left_turn x north_through (the turn crossing the northbound through lane) with its bend and junction, published 2026-11-22 with the user's OK as the maps dataset's revision 19d52699, tag v2026.11e, every testbench's lock on it. K9d done 2026-11-22: `testbench check` refuses a scenario's bindings the world cannot satisfy (an anchor or attribute it lacks, a function on a stated anchor, a bare heading, a constant s off the lane, a stale resolved file); `anchor_source` names the lock's dataset and commit when the lock holds the file read; a stated lane's `lanelet` passes `testbench check`. The anchors are done (K9a-d). Knob profiles built 2026-11-22 (CS5): `profile: true` knobs (a range, the field they set), bound to breakpoints along `time` or `s(<lane>)`, applied by the bridge each frame (`set_knob_profiles`; a send when the value moved by its step and `min_interval`, 1 s by default, has passed, or at once on a crossed breakpoint: a send every frame took CARLA's frame p95 to 21-222 ms, one a second kept it at 1-4 ms), read back by the world servers (`ENVIRONMENT_APPLIED`), recorded per frame in the gap trace's `knob` lines and judged in `result.json` `knobs.profiles` (`knob_profile` error runs); resolved lanes gain their centreline (`x`, `y`). The pilot's map variants (CS3) remain. Before: K8 built the minimal anchor declaration it extends (`world.anchors` in testbench.yaml, numbers the project states): K9 adds anchors a world declares beside its map, attributes computed from the map (`heading(s)`, length and speed limit from lanelets, conflict points), regions and curves, binding entities to anchors, and the check |
| K10 | 093 D3's behaviour models (scenario-description.md section 4): the model interface (a parameter schema, `reset`, `step`, one array API code for numpy on seats and `step_batch` in torch; truth in, a kinematic command out, decisions into the truth), the starter model (a gap-acceptance walker for CS1, from a published model named before any coefficient), batched in scensim_batch, on seats as a K4 attachment that commands its entity through K12; the agreement check in K2.4's style (the same records on both forms: decisions and their frames, the walker's trajectory error, trigger times, verdict); the latency from a truth frame to the command taking effect measured free-running and in lockstep (093's open question 1) | component | K2, K4, K12 | swb 241 | in progress: planned 2026-11-22 (133 approved), the section 4 draft corrected (SSv2 takes a world-owned pose for any entity; pilots do not see truth, attachments do); (i)-(ii) landed ce760b69: `scensim.behaviour`, the walker on numpy and torch bit for bit (0 of 2800 arrays differ on an RTX 5090), its coefficients the cited set `khaki2021_restricted` (Khaki and Mohammadnazar 2021, CC0; the gap's 2.021 against the 2021 meta-analysis's pooled 1.98); (iii) in the batch: a model entity (role `model`) compiled from its ObjectController (its properties per slot, `anchor.*` for the crossing, its seed from `seeds.pilots.<entity>`), stepped after the ego's physics on its truth and moved kinematically within its acceleration limit; CS1's start trigger is the model's `start_gap` (`$ttc_entry`), as the subset keeps ActivateControllerAction seats-only; the walker decides where it can still stop at the kerb; `cs1_walker_gap_acceptance.xosc` the batch example (the description's CS1 stays refused: a storyboard SpeedAction on a model entity); (iv) the agreement with seats passed 2026-11-24 on K12's exit set 3 ("K10's agreement" below: the seats ego played back, no engine; the batch now takes a model entity as world-owned with the channel's lag 1), (v) the latency is K12's (set 3: lag 1 in lockstep and free-running); not covered: an engine in the loop, the engines' map-frame velocity |
| K12 | Truth-fed pilots: a command channel from a K4 attachment to the world server (`entity_command`: an entity's kinematic command, carried with the tick gate's acknowledgement, integrated and applied by the world, read back to SSv2, whose fork adopts it for a simulator-driven pedestrian), under lockstep held to one frame; for K10's behaviour models and learned background agents | component | K4 | swb 243 | landed 2026-11-23 (scensim 0cc054d8; the SSv2 fork's model pedestrian, COMMANDED on the world protocol, the CARLA world server's integrator, the bridge, truth schema 3, attachments' `commands:`, `scensim.behaviour.seats`); pedestrians first, CARLA only; exit passed 2026-11-23 on set 3, by the rule fixed before the runs ("K12's exit runs" below) |
| K11 | 093 D4's search (purpose B): an adaptive search over cells that writes the record's reserved `search` | component | K1, K7 | | open |
| E1 | Examples | examples | the above | | open |

## K12's spec (2026-11-23, 243; reviewed by 133 the same day, before any code)

K12 lets a K4 attachment move an entity on seats: a behaviour model (K10) or a learned
background agent reads the truth stream and commands its entity, the world server moves it, and
SSv2 adopts the pose the world shows. Read against the code at main 8a78f4f4 (the bridge, the
CARLA and Isaac world servers, the world protocol, the SSv2 fork), the row's sentence above needs
three corrections, and the spec is written around them:

1. **SSv2 needs a change.** `API::updateEntitiesStatusInSim` does apply the returned status to
   every entity (`setStatus` for a non-ego), but that is upstream SSv2 (2025-02-20), and SSv2
   then runs the entity's behaviour in the same frame. A pedestrian's controller name is loaded
   as a behaviour plugin (`PedestrianEntity`, pluginlib), so CS1's `walker_model` fails to load
   on seats, and the default plugin would move the walker on after the world's pose was set.
   Vehicles already have the fork's answer, `SimulatorDrivenVehicleEntity` (controllers
   `simulator_autopilot` and `agent`: no behaviour, the returned pose adopted); pedestrians have
   none, and their spawn request carries no behaviour, so the bridge cannot tell. So
   scenario-description.md section 4's "Nothing changes in SSv2" does not hold.
2. **The command goes to the world server, not the bridge.** In a frame SSv2 sends
   UpdateEntityStatus (the world's Apply) before UpdateStepTime (its Step), and CARLA's tick
   gate waits inside Step. An attachment answers frame k after Apply(k+1) has gone out, so a
   command through the bridge would take effect at k+2. Carried with the gate's acknowledgement,
   it is in the world server before the tick of k+1: one frame, by construction.
3. **The world protocol has no kinematic command.** `EntityPose` carries poses; the world
   server must integrate the command itself.

### Decisions

- **D1, which entities.** An entity whose `ObjectController` has a `model` property (the
  batch's role `model`) is commanded on seats. Its controller is named `model`, as the batch's
  role (CS1's `walker_model` renamed). Pedestrians first: CS1's walker is the only consumer
  (133). `scensim run` reads the commanded entities from the scenario and each attachment's new
  key `commands: [<entity>, ...]`; it refuses, by name, a commanded entity no attachment claims,
  one claimed twice, a claim on an entity without `model`, and a commanded vehicle or misc
  object. `attachments.roles` gains the role `model`. Vehicles are the next step, when a vehicle
  behaviour model exists: the fork's `SimulatorDrivenVehicleEntity::drives()` gains `model`, and
  the rest of this spec holds as written.
- **D2, SSv2 (the fork, branch `managed-ego-unforked`, pushed before any pin moves).** A
  `SimulatorDrivenPedestrianEntity` for controller `model`, as `SimulatorDrivenVehicleEntity`
  is for vehicles: no behaviour plugin, the returned pose and twist adopted, route, lane change
  and speed actions on it semantic errors. `SpawnPedestrianEntityRequest` gains
  `string behavior = 4`, as the vehicle's field 6.
- **D3, the bridge.** A `model` entity is `Mover::Simulator`, spawned with a new `Motion`
  `COMMANDED`, and read back like the ego. A world server without `READS_BACK` and a tick gate
  refuses it: Isaac today, by name. Its follow-up, named and not part of K12: a tick gate and
  `READS_BACK` for the Isaac world server.
- **D4, the channel.** The tick gate's datagram, extended: a follower acknowledges a frame with
  `DONE <frame> [<entity> <speed> <heading> <accel_limit>]...` (`<frame>` as `DONE`'s: the truth
  frame's `sim_frame`; radians, SI units). Free-running (`lockstep: false`), the follower sends
  the same list as `CMD <frame> ...` to the same port and is not waited for. The world server
  applies each entity's latest command at the next tick. A frame's commands fit one datagram,
  bounded so it never fragments on an Ethernet link (the gate may be bound off the loopback, as
  for ns-3): at most 1472 bytes, each number in its shortest round-trip form (at most 24
  characters), an entity's name at most 64 bytes, so at most **10 commanded entities** per
  scenario. `scensim run` refuses a scenario over either bound by name, before SSv2 starts;
  nothing is split or dropped.
- **D5, the motion.** Before each tick the world server integrates each commanded entity as the
  batch does (`scensim_batch.core.Models`): `v += clamp(speed - v, +-accel_limit dt)`, the yaw
  set to the heading, the position moved `v dt` along it; then sets the actor's transform with
  physics off, its z from the ground as for a kinematic NPC. Nothing is clamped to the catalog:
  OpenSCENARIO's Pedestrian has no Performance element, so a pedestrian entry names no maximum
  speed or acceleration. The world server refuses a command whose numbers are not finite, whose
  speed is negative or whose accel_limit is not positive, with the whole datagram. Before its first
  command an entity stands at its spawn; afterwards it keeps its last command.
- **D6, decisions.** A model's decisions (`wait`, `go`, `abort`) are not part of the channel:
  the attachment writes them per frame into `$SCENSIM_ATTACHMENT_DIR`, where K10's agreement
  check reads them.
- **D7, the latency, measured.** The truth file gains, per commanded entity and frame, the
  frame the applied command answered (`cmd_frame`). `result.json` gains `commands`: per
  entity the commands applied, the lag in frames (p50, p95, max), commands naming an
  unknown entity, and gate misses. Under lockstep the lag is 1 at every frame or the run is an
  error run (`error.kind: command_lag`); free-running it is reported (093's open question 1).
  SSv2 sees the tick of k+1 in UpdateEntityStatus of k+2, as for every world-owned entity:
  stated, not changed.

### Exit checks

1. The world server's integrator against `Models` on the same command sequence: equal within
   float64 rounding.
2. CS1 on CARLA 0.9.16 with the walker as a lockstep attachment: lag 1 at every frame, no gate
   miss; SSv2's conditions on the walker (its start trigger, a ReachPositionCondition) fire at
   the frame the truth shows; the run once free-running, its lag reported.
3. The fork: a pedestrian with controller `model` runs no plugin and adopts the returned pose
   (a traffic_simulator test); a spawn's `behavior` reaches the bridge.
4. Each refusal of D1 and D3, by name.

### Answered (133, 2026-11-23)

The controller name is `model`; pedestrians first, vehicles when a vehicle behaviour model
exists; the commands ride the gate's datagram, bounded as in D4.

### K12's exit runs (rule fixed 2026-11-23, before any run)

Exit checks 1, 3 and 4 hold in the landed code (scensim 0cc054d8: `commanded_law.json` and
`test_model_law`, the fork's traffic_simulator test, the refusals' tests). Check 2 is these runs.

**The scenario.** `scenarios/projects/k12_commanded/scenarios/cs1_town01.xosc`: CS1's gap
acceptance walker (`cs1_walker_gap_acceptance.xosc`, which stays as it is) on Town01, its ego,
van and walker on the map's anchor `west_street` (lanelet 6583, 224 m; FileHeader
`scensim.anchor.street = west_street.lanelet`, maps dataset v2026.11e), at CS1's s and
offsets. Its ego is driven by `carla_basic` (CARLA's BasicAgent) at `ego_speed` toward the
lane's end, so the runs measure the command channel and not an autopilot. One addition to
CS1: an event on a `ReachPositionCondition` for the walker at its far kerb, so an SSv2
condition on a commanded entity is checked. The testbench's attachment is
`python3 -m scensim.behaviour.seats` with `commands: [walker]`. CARLA 0.9.16 at Epic, after the
VRAM check.

**The runs.** L: lockstep, seeds 1, 2 and 3 (`ttc_entry` 3.0, `behaviour` steady). F: the same
scenario with `lockstep: false`, seed 1. The seeds' decisions, predicted from the walker's draws
(`GapAcceptanceWalker.draw`) at the gap it is offered at its decision point, about 2.4 s (3.0 s
at its start trigger less its 1.5 m approach to where it can still stop; P(accept) 0.144):
seed 1 accepts (U - logit(u) = 0.08) and crosses in front of the ego; seeds 2 and 3 reject, wait
and cross once the ego has passed. So the L runs cover both branches, and all three reach the
far kerb. A run that decides otherwise is reported with its decision gap; the checks still apply.

**The rule.**
1. Each L run: `result.json` `commands.ok` true, so every frame after the walker's first has
   lag 1, with no lost or unmatched frame; `gate_misses`, `unknown_entity` and `malformed` 0;
   the run is not an error run for any reason.
2. Each L run: the walker's truth against the batch's model on the same record, replayed on
   the run's own ego truth: the model's step and `scensim_batch.core.model_law` for one slot,
   from the walker's Init pose (so a difference between the batch's ego and `carla_basic` does
   not enter). Frames align as the lag does: the replay's model steps on the ego truth of frame
   k, as the seats model did, and its state after that command is compared with the walker's
   truth at frame k+1, the frame that command moved it in. The CARLA world server realises a
   commanded walker kinematically: physics off, `set_transform` once per step to the
   integrator's pose, its z put on the ground (`walker_teleport_z`); no walker control and no
   physics move it. So the comparison is in x and y only (z is the ground's), and the bar is
   0.02 m on the largest xy error over the run: loose for set_transform, whose only error is
   CARLA's float32 transform (about 3e-5 m at x = 280 m) read back each frame, and the seats
   model reading that pose, not its own. The model's events (`decisions.jsonl` against the
   replay's) must occur at the same frames.
3. Each L run: the walker's `ReachPositionCondition` completes, in the storyboard log, at the
   frame whose truth first puts the walker within the condition's tolerance. Every L run is
   expected to reach the far kerb (above); one that does not fails this check.
4. F: the lag (p50, p95, max), the lost and unmatched frames' counts, the gate's counts and
   check 2's error are reported; no bar (093's open question 1).

**The verdict.** K12's exit holds when all three L runs pass 1 to 3. A failure is named by
run, check and number, and nothing is rerun until its cause is known.

**Exit set 1 (2026-11-23): failed.** One stack (seat 0, CARLA 0.9.16 at Epic), scensim
0cc054d8, the project at its first form. Four attempts never played a frame: SSv2's
preprocessor refused the scenario (the catalog ego lacked its ParameterAssignments, and SSv2's
Pedestrian needs `model`); both fixed in the project, and their runs reported `command_lag`
instead of SSv2's refusal (fixed: no frame is no lag). Then:

| run | check 1 | lag | unmatched | gate misses | unknown | decision | far kerb | check 2 (max xy) |
|---|---|---|---|---|---|---|---|---|
| L seed 1 | pass | 1 on 238 frames | 0 | 0 | 0 | reject, then crosses | yes | 0.070 m, failed (events match) |
| L seed 2 | fail | 1 on 230 frames | 1 | 1 | 1 | reject, then crosses | yes | not judged (cause A) |
| L seed 3 | fail | 1 on 231 frames | 1 | 1 | 1 | reject, then crosses | yes | not judged (cause A) |
| L seed 31 | fail | 1 on 192 frames | 1 | 1 | 1 | accepts | yes | 0.0037 m (events match) |

Branch coverage, as (c) provides: seed 1's thin margin flipped and it rejected, so seed 31
(U - logit(u) = 2.61) was added and accepted. F was not run.

Cause A, the world server's tick gate kept state across runs (every run after the stack's
first): it kept the previous run's newest command for `walker`, which the new walker took at
its first step (seed 2's first walker frame, world frame 3408, has `cmd_frame` 3402, seed 1's
last frame: D5 broken, the same command counted as unknown); and a follower that joined was
waited for, a whole timeout, on the previous run's last frame, which it never saw. Cause B,
CARLA: LibCarla 0.9.16's `SetActorTransform` is an asynchronous call, so the walker's
transform could reach CARLA after its tick, and its reported pose stalled a frame and caught up
with a double step (seed 2 at frames 158 and 220, seed 3 at 165); seed 1's 0.070 m is such a
stall on its last two frames, the integrator matching the batch within 1e-4 m on every other.
Fixed in scensim_carla_world a27b833: a name's command is forgotten when its body is spawned
or destroyed (a later command answering an earlier frame refused), a new world clears them, a
joining follower is never waited for on a frame from before it joined, and commanded bodies
are posed by one synchronous `apply_batch_sync` per step. The same asynchronous pose of other
kinematic bodies is issue 127. The rule is unchanged; set 2 is the whole set again from scratch
on a fresh stack (L seeds 1, 2, 3 and 31, F seed 1).

**Exit set 2 (2026-11-23): failed, check 1.** Fresh stacks (an L stack, then an F stack;
CARLA 0.9.16 at Epic), scensim 84eed895, scensim_carla_world a27b833. Every run passed.

| run | lag (p50/p95/max) | lost | unmatched | gate misses | malformed | unknown | decision | check 2 (max xy) | check 3 |
|---|---|---|---|---|---|---|---|---|---|
| L seed 1 | 1/1/1 on 240 frames | 0 | 0 | 0 | 0 | 0 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 2 | 1/1/1 on 229 frames | 0 | 0 | 0 | 0 | 1 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 3 | 1/1/1 on 230 frames | 0 | 0 | 0 | 0 | 1 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 31 | 1/1/1 on 191 frames | 0 | 0 | 0 | 0 | 1 | accepts | 1.50e-4 m, events match | pass |
| F seed 1 (check 4) | 1/1/1 on 239 frames | 0 | 0 | 0 | 0 | 0 | rejects, then crosses | 1.49e-4 m, events match | |

Check 1 failed on `unknown_entity` 1 in L seeds 2, 3 and 31, the runs that followed another
run on the same stack. The cause: the previous run's walker controller answered that run's
last frame after the world's last step in it, so its datagram waited unread in the gate's
socket; the next run's Initialize (same map, no reload) cleared the gate, which also dropped
the floor that the old walker's destruction had set; the next step's drain then stored that
command and counted it for an entity not yet commanded. The new walker's spawn dropped it, so
nothing moved on it. Cause B is fixed: no pose stalled in any run, and check 2's largest error
went from 0.070 m to 1.5e-4 m. The synchronous pose costs about 0.2 ms a frame: frame p50 0.71
to 0.76 ms against 0.56 ms in set 1, tick p50 1.01 to 1.22 ms against 1.08 ms, tick p95 1.34 to
1.58 ms. L seed 31 has no frame metrics: they come in 200-frame windows, and its run was 193
frames (a final partial window is a later item). Check 3 holds in every L run: each run's truth
ends, on the event's `exitSuccess`, at the first frame whose SSv2 pose of the walker is within
1.0 m of LanePosition s 47, offset 5.25 (the model's far anchor, recomputed from lanelet 6583).
The first analysis compared the storyboard log's `time` with the truth's `sim_time`, but the
interpreter counts that time from `npc_logic_started` (truth frames 26, 14, 15, 15 and 24
here), which made the event look about 0.6 to 1.2 s early; corrected.

Fixed in scensim_carla_world (the fix 133 chose on 2026-11-23): clearing the gate keeps one
floor for every entity at the last step's frame, so a command answering a frame at or before
it is stale; a stale command is dropped and counted in its own count, `stale` (each entity and
frame once; `CommandCounts.stale` on the world protocol, the truth's `commands`, `result.json`
beside `unknown_entity`), which is a record outside `commands.ok`; and a step whose frame is
below a floor (the world's frames started again) resets that floor, logged. The rule is
unchanged; set 3 is the whole set again on fresh stacks.

**Exit set 3 (2026-11-23): passed.** Fresh stacks (an L stack, then an F stack; CARLA 0.9.16
at Epic), scensim 6fd0c750, scensim_carla_world 507d66c, the build the landing gate passed.

| run | lag (p50/p95/max) | lost | unmatched | gate misses | malformed | unknown | stale | decision | check 2 (max xy) | check 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| L seed 1 | 1/1/1 on 240 frames | 0 | 0 | 0 | 0 | 0 | 0 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 2 | 1/1/1 on 230 frames | 0 | 0 | 0 | 0 | 0 | 1 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 3 | 1/1/1 on 230 frames | 0 | 0 | 0 | 0 | 0 | 1 | rejects, then crosses | 1.49e-4 m, events match | pass |
| L seed 31 | 1/1/1 on 190 frames | 0 | 0 | 0 | 0 | 0 | 1 | accepts | 1.50e-4 m, events match | pass |
| F seed 1 (check 4) | 1/1/1 on 240 frames | 0 | 0 | 0 | 0 | 0 | 0 | rejects, then crosses | 1.49e-4 m, events match | |

Every run passed. The previous run's last acknowledgement is now `stale` 1 in each run after a
stack's first, and `unknown_entity` is 0 in all of them. In every L run the far-kerb event
fires at the truth's last frame, the first whose SSv2 pose of the walker is within 1.0 m. No
pose stalled. Frame p50 0.58 to 0.75 ms, tick p50 0.92 to 1.19 ms, tick p95 1.18 to 1.62 ms
(L seed 31 again under one 200-frame window). F, check 4: lag 1 at p50, p95 and max, no lost
or unmatched frame, the gate's counts 0, check 2's error 1.49e-4 m. All three L runs pass
checks 1 to 3, so K12's exit holds. Seed 1 rejected in all three sets, against the prediction
(an accept on a thin margin, U - logit(u) = 0.08); seed 31 (2.61) was the accept branch in
sets 1 to 3, so both branches were covered as (c) provides.

## K10's next step: the walker's agreement, seats against the batch (plan, 2026-11-23, 241; approved by 133 with its additions, before any code)

K10's row has two parts left: the agreement check in K2.4's style, and the latency from a truth
frame to the command taking effect. K12 landed the seats side (`scensim.behaviour.seats`, the
walker as a lockstep attachment commanding through the tick gate) and its exit runs measure the
latency (D7: lockstep lag 1 at every frame or an error run; the free-running lag reported, F).
So the latency is K12's numbers, not measured again: exit set 3 (above), lag 1 at p50, p95 and
max in every lockstep run and in the free-running one (F seed 1, 240 frames), with no lost or
unmatched frame.
What is left is the agreement.

**The question.** Does the batch, running CS1 from the same record, make the walker do on the
same frames what it did on seats: the same decisions at the same frames, the same trajectory,
the same storyboard trigger times, the same verdict?

**Isolating the walker.** K12 is CARLA only, and the batch has no CARLA car: the ego's
dynamics differ between the two sides (engine A is aib's PhysX vehicle, B an articulation), and
a walker that decides on the gap to the ego would see a different gap. K2.4 avoided this by
running seats on Isaac with engine A; that is not open here. So the batch ego **replays the
seats ego's truth poses** kinematically (a pose playback, new: `agreement_run.py
--ego-from-truth`), frame for frame as K2.4 pairs them (seats frame S + k is batch step k),
and the comparison is of everything else. The ego's own column is then zero by construction and
is checked to be (under 1e-6 m), not judged.

**What it adds, and what it does not (133, 2026-11-23).** K12's check 2 already compared the
batch's walker model, replayed in numpy on the seats ego's truth, with CARLA's walker (within
1.5e-4 m but the stalls), and K10 (ii) showed the model's numpy and torch forms bit for bit. This
agreement adds three things, which it judges: the walker placed in the batch as its executor
places a model entity (`Models.place`, into the observation the storyboard reads, through the
view SSv2 would have of it), the batch storyboard's timing on a commanded walker (each
element's offset, the walker's own conditions among them), and the walker's decisions as the
batch executor sequences them, a step after the ego's physics. (133 named Isaac Lab's
placement of the walker: there is none to judge. ScensimEnv puts only the ego in Isaac's
scene; SSv2's default vehicles and model entities live in BatchRun's tensors, read back from
no simulator.)

**No engine is in this agreement (133).** It checks BatchRun's logic on a playback backend:
`Models.place`, the storyboard, the decisions' sequencing. The ego's engine (engine A or B
against CARLA's car) is not covered: an agreement with an engine in the loop waits until both
sides can drive the same ego, which K12's CARLA-only channel does not allow yet. The walker's xy error is kept and predicted to equal check 2's, since the same model
on the same ego poses gives the same law; a difference from check 2's number is a finding.

**The frame alignment, stated.** As in K2.4, seats frame S + k pairs with batch step k, and the
played-back ego at step k is the seats ego's truth at frame S + k. In a batch step the ego
moves first and the model then reads that step's ego and moves the walker in the same step
(`BatchRun.step`, `Models.step`); on seats the attachment reads the truth of frame S + k and
its command moves the walker in frame S + k + 1, K12's lag 1. So the batch walker at step k is
compared with the seats walker's truth at frame S + k + 1, a decision the batch makes at step k
with the one the attachment wrote for truth frame S + k, and the ego's velocity the model reads
is the one the seats attachment read from the same truth frames (its finite-difference
acceleration too). This is K12's check 2 convention; without it every decision would shift by
a frame for the wrong reason.

**The runs.** K12's exit set 3 (CS1's walker on Town01's `west_street`, the ego
`carla_basic`, lockstep, scensim 6fd0c750): its L seed 2 (rejects, waits, crosses after the
ego) and L seed 31 (accepts and crosses in front), one run of each branch, read from their run
directories, so no seats run is made again. The batch side:
`agreement_run.py --ego-from-truth` on each run directory, one slot, the walker a `model`
entity compiled from its ObjectController with the run's seed. With the ego played back, no
engine enters: BatchRun runs on a playback backend that returns the seats ego's truth (pose,
and the velocity the attachment read), with no Isaac and no GPU.

**The columns** (batch-executor.md section 8's, with the model's): the outcome on each side;
the walker's max and RMS xy error and its max yaw error; each storyboard element's first
running and complete step on each side (the walker's start trigger `start_gap`, the far-kerb
`ReachPositionCondition`, the scenario's end); each of the walker's decisions (`wait`, `go`,
`abort`) with its frame on each side (seats: the attachment's `decisions.jsonl`; batch: the
model's events); the ego's error (checked zero).

**The rule, fixed before any run.** Each run agrees when: the outcomes are equal; the
decisions are the same sequence at the same frames; every element's offsets are 0; the
walker's max xy error is at most 0.02 m (K12's check 2 bar, for the same set_transform pose
read back each frame), and is expected to equal check 2's for the run (1.49e-4 m for seed 2,
1.50e-4 m for seed 31). A disagreement is named by run, column and number, and its cause found
before anything is rerun. The prediction: both seeds agree, as K12's check 2 found the model
against the seats walker within 1e-4 m on every frame but the asynchronous-pose stalls, which
scensim_carla_world a27b833 removed.

**Code** (one landing, gated, asked first): `agreement.py` reads the attachment's decisions and
pairs model entities' poses and decisions; `agreement_run.py --ego-from-truth`; tests on
recorded fixtures, no simulator. A fix, named as one (133): `Models.step` takes the ego's
velocity from the backend's state when it gives one (`vx_map`, `vy_map`, the map frame, which
is what the walker sees and what the seats attachment reads from the truth), else from v and
yaw as now, which drops a sliding ego's lateral velocity. Which runs it changes: only those whose
backend gives the map-frame velocity, and today only the playback backend does; engine A's
`PhysxVehicleBackend.state` and engine B's `ArticulationBackend.state` give v along the body,
so every landed batch run computes as before. No landed result used a model entity on an
engine either: K2.4's rows have none, and the walker's batch form so far is tests and the
`cs1_walker_gap_acceptance.xosc` example. So nothing reruns and nothing needs a note. The
engines giving map-frame velocity too, for a model beside a sliding ego, is a follow-up. The batch side needs no simulator and no GPU, and
the seats side is set 3's runs, so nothing here takes a GPU.

### K10's agreement, run 1 (2026-11-24): failed, walker_far_kerb

Set 3's L seed 2 and L seed 31, read from
`~/nas/home/2026-11-23 092 K12 exit set 3 runs (243)/` (SHA256SUMS sha256 54ec8033...;
`sha256sum -c` passed there and on the local copy), with scensim 80df7418's
`agreement_run.py --ego-from-truth`, the record each run's seed and parameters (street 6583).

| run | outcome (seats / batch) | walker max / RMS xy | decisions (step, event) | ego | van | element offsets |
|---|---|---|---|---|---|---|
| L seed 2 (S 14, 218 steps) | passed / passed | 1.49e-4 / 1.29e-4 m | 61 appear, 82 reject, 121 go_after on both | 0 | 2e-5 m | 0, but walker_far_kerb -3 (seats 218, batch 215) |
| L seed 31 (S 13, 179 steps) | passed / passed | 1.50e-4 / 1.29e-4 m | 61 appear, 82 go on both | 0 | 2e-5 m | 0, but walker_far_kerb -3 (seats 179, batch 176) |

The walker's error is the prediction (check 2's), and the decisions agree; the rule fails on
the far-kerb event, three steps early in the batch in both runs. Its cause, from the truth (seed
2: CARLA's pose of the walker first within the condition's 1.0 m at truth frame 231, batch step
215, where the batch fires), is three frames:

- (a) the channel's lag: on seats the walker moves a frame after the truth its model read (K12's
  lag 1); the batch moved it in the same step;
- (b) on seats the walker is world-owned, so SSv2 has the world's pose a frame later: the
  truth's ssv2 pose of the walker at frame f + 1 is its sim pose at f, exactly;
- (c) SSv2 evaluates its storyboard a frame after that, as for the ego (K2.4: the storyboard
  reads the ego of two steps before). The batch's `_as_ssv2_sees` moved only the ego's columns
  two steps back; a model entity stayed current, as SSv2's own NPCs are.

**The fix (133, 2026-11-24).** (b) and (c): a model entity enters the storyboard's view two
steps back, as the ego does. (a): the batch applies a model's command a step after the model
gives it, the lockstep channel's lag 1, so the batch reproduces seats with the lag included
(seats is the reference; a stated offset on every condition naming a model entity was the
alternative, refused). A model entity stands at its Init pose until its first command takes
effect, as on seats. With it the two forms pair a model entity's poses without a shift.

So on both targets a model reacts one frame later than its decision: its effective reaction
time is its calibrated one plus one frame (0.05 s at the 20 Hz the runs step). A note for K10's
calibration (`khaki2021_restricted`), not a change to it.

**Prediction for run 2, before it (2026-11-24).** The same set 3 data and the same rule, the
batch with the fix: every element offset 0 (walker_far_kerb at 218 and 179 on both sides);
the decisions at the same steps as run 1 (61, 82, 121; 61, 82); the outcome passed on both; the
walker's max xy error unchanged (1.49e-4 m, 1.50e-4 m), its poses now paired without a shift;
ego 0 and van 2e-5 m as before.

### K10's agreement, run 2 (2026-11-24): passed

The same set 3 data (`sha256sum -c` passed again), the batch with run 1's fix (scensim
this landing's `core.py`: model entities in SSv2's view two steps back, a model's command
applied a step later). Rows: `~/nas/home/aeon/k10-agreement/run2/` (run 1's beside it).

| run | outcome (seats / batch) | walker max / RMS xy | decisions (step, event) | ego | van | element offsets |
|---|---|---|---|---|---|---|
| L seed 2 | passed / passed | 1.49e-4 / 1.29e-4 m | 61 appear, 82 reject, 121 go_after on both | 0 | 2e-5 m | all 0 (walker_far_kerb 218 on both) |
| L seed 31 | passed / passed | 1.50e-4 / 1.29e-4 m | 61 appear, 82 go on both | 0 | 2e-5 m | all 0 (walker_far_kerb 179 on both) |

As predicted, in every column. Both runs pass the rule, so the batch reproduces seats on a
commanded walker: its placement into SSv2's view, the storyboard's timing on it and the
decisions' sequencing, with the lockstep channel's lag included. Not covered, as planned: an
engine in the loop (both sides driving the same ego), and the engines giving the map-frame
velocity (a follow-up). With this, K10's row is done but for that.

### K10's close-out (133, 2026-11-24): the engines' map-frame velocity, D3 out of draft, the row closed

**(1) The engines give the map-frame velocity (plan, before any code).** A behaviour model reads
the ego's velocity in the map frame (`ego_vx`, `ego_vy`), as the seats attachment reads the
truth. Since the agreement, `Models.step` takes it from a backend's `vx_map`, `vy_map` when
given; only the playback backend gives them. Both engines will:

- engine B, `articulation.ArticulationModel.state`: the root's world linear velocity's x and y
  (the env's origin moves positions, not velocities);
- engine A, `physx_vehicle.PhysxVehicleBackend.state`: aib's base_link velocity rotated into the
  map frame by the car's full orientation quaternion (not the yaw alone, so a pitched car's
  vertical velocity does not leak into x and y).

Checks: per engine, a sliding ego (body velocity 10 m/s forward and 2 m/s sideways, yawed 30
degrees; for A also pitched 5 degrees) gives `vx_map`, `vy_map` equal to the body velocity
rotated into the map frame, within 1e-12; and on each engine's state `Models.step` hands the
model those numbers, not `v cos(yaw)`, `v sin(yaw)`. A batch run with a model entity beside a
sliding ego changes; no landed result has one (the agreement's note), so nothing reruns.
