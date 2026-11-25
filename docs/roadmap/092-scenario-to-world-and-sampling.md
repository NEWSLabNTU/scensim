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
| K6 | Jazzy for the whole set | all | 082 | swb 243 | done 2026-11-25: the simulation side builds and tests on Ubuntu 24.04 with Jazzy through a developer's own steps (`just jazzy-check`, a container; its Result below), and the Jazzy-built CARLA world server passed `scensim_world_check conformance` 28 of 28 against CARLA 0.9.16, as the Humble build does; the Humble gate passed on the landing tree; carries 082 step 7 |
| K8 | 093's description rules (scenario-description.md section 2a): `latent: true` model variables (gap 2), `scensim.present` optional entities (3), `scensim.static` stopped vehicles (4), `isBlind` in the subset with lane following as its condition (5), a per-sample entity class conditioned on per-slot assets (6), anchor attributes in derived values (7, with K9) | spec, component | S1, S2 | | done 2026-11-22 but gap 3 (swb 243): gaps 2, 4 and 6: latent variables in the record's `latent`; `scensim.static` with SSv2's `maxSpeed = 0`, a batch prop (scensim_batch: executor pending); a parameter in an entity's class or model a condition naming it and its values (SSv2's examples' counts unchanged); gap 5: a blind default controller's condition is SSv2's lane following alone (executor pending in the batch); gap 7: `anchor.<name>.<attribute>` in derived values, from `testbench.yaml` `world.anchors` (lane heading, length, speed limit; point x, y), recorded in the record's `anchors`, CS7's `exit_heading` stand-in gone (the rest of anchors is K9); gap 3 (`scensim.present`) open, needed by neither case study |
| K9 | 093 D2's world interface beyond knobs: anchors (lanes, regions, conflict points, curves) declared by a world and checked by `testbench check`, knob profiles (`profile: true`, CS5), the pilot's map variants (`maps.pilot_variants`, CS3) | spec, component | K1 | | done 2026-11-25 but K9f (swb 243; K9f, region-scoped knobs and prop layouts, planned below): K9a done 2026-11-22, a map's lanes: `<map dir>/anchors.yaml`, resolved by the map's author with `python3 -m scensim_batch.anchors resolve` (torch) into `anchors.resolved.json` (length, speed limit, ends, a heading table within 1e-3 rad in SSv2's arc length, the map's digest), read by the sampler and scensim with ROS 2 alone and merged with `world.anchors`; `anchor.<lane>.heading(s)`; the record's `anchor_source`; Town01's anchors (west_street, west_left_turn) published 2026-11-22 as the maps dataset's revision deb23e3a, tag v2026.11d, with the user's OK; every testbench's lock on it; K9b done 2026-11-22: FileHeader `scensim.anchor.<parameter> = <anchor>.<attribute>` or `<anchor>.<function>(<arg>)`, `$<parameter>` for a drawn anchor or argument; resolved lanes gain `lanelet_at(s)` and `local_s(s)`, a stated lane its `lanelet`; the sampler checks bindings before drawing and rejects a draw off its lane by name; `scensim run` sets a scenario's bound parameters before SSv2 starts, checks a record's against the world, refuses a given value and SSv2's own distribution of a bound scenario, and records `result.json` `anchors`; `compilable` refuses a named laneId with the binding as its fix; CS6 and CS7 bind their lanes. K9c done 2026-11-22: conflicts (two lanes crossing once: `s_<lane>`, `x`, `y`, `angle`, `position_error`), curves (`length`, `turn`, `direction`, `min_radius` over 2 m, `mean_radius`) and regions (polygon: `area`, centroid, each lane's `from_`/`to_`) resolved from the map's file; Town01's conflict west_left_turn x north_through (the turn crossing the northbound through lane) with its bend and junction, published 2026-11-22 with the user's OK as the maps dataset's revision 19d52699, tag v2026.11e, every testbench's lock on it. K9d done 2026-11-22: `testbench check` refuses a scenario's bindings the world cannot satisfy (an anchor or attribute it lacks, a function on a stated anchor, a bare heading, a constant s off the lane, a stale resolved file); `anchor_source` names the lock's dataset and commit when the lock holds the file read; a stated lane's `lanelet` passes `testbench check`. The anchors are done (K9a-d). Knob profiles built 2026-11-22 (CS5): `profile: true` knobs (a range, the field they set), bound to breakpoints along `time` or `s(<lane>)`, applied by the bridge each frame (`set_knob_profiles`; a send when the value moved by its step and `min_interval`, 1 s by default, has passed, or at once on a crossed breakpoint: a send every frame took CARLA's frame p95 to 21-222 ms, one a second kept it at 1-4 ms), read back by the world servers (`ENVIRONMENT_APPLIED`), recorded per frame in the gap trace's `knob` lines and judged in `result.json` `knobs.profiles` (`knob_profile` error runs); resolved lanes gain their centreline (`x`, `y`). The pilot's map variants (CS3) done 2026-11-24 ("K9's CS3" below). K9e done 2026-11-25: the same names on Isaac, CS3 unchanged on both targets with the same anchors, knob and map variants, the environment form and issue 154 ("K9e" below). Before: K8 built the minimal anchor declaration it extends (`world.anchors` in testbench.yaml, numbers the project states): K9 adds anchors a world declares beside its map, attributes computed from the map (`heading(s)`, length and speed limit from lanelets, conflict points), regions and curves, binding entities to anchors, and the check |
| K10 | 093 D3's behaviour models (scenario-description.md section 4): the model interface (a parameter schema, `reset`, `step`, one array API code for numpy on seats and `step_batch` in torch; truth in, a kinematic command out, decisions into the truth), the starter model (a gap-acceptance walker for CS1, from a published model named before any coefficient), batched in scensim_batch, on seats as a K4 attachment that commands its entity through K12; the agreement check in K2.4's style (the same records on both forms: decisions and their frames, the walker's trajectory error, trigger times, verdict); the latency from a truth frame to the command taking effect measured free-running and in lockstep (093's open question 1) | component | K2, K4, K12 | swb 241 | done 2026-11-24; its open recheck (issue 130) closed the same day, the decisions at the same frames on new seats runs ("K10's open recheck" below) (the close-out below: the engines' map-frame velocity, D3's section 4 out of draft; not covered: a vehicle model, parked with the user, and an agreement with an engine in the loop, until both targets share an ego). Before: planned 2026-11-22 (133 approved), the section 4 draft corrected (SSv2 takes a world-owned pose for any entity; pilots do not see truth, attachments do); (i)-(ii) landed ce760b69: `scensim.behaviour`, the walker on numpy and torch bit for bit (0 of 2800 arrays differ on an RTX 5090), its coefficients the cited set `khaki2021_restricted` (Khaki and Mohammadnazar 2021, CC0; the gap's 2.021 against the 2021 meta-analysis's pooled 1.98); (iii) in the batch: a model entity (role `model`) compiled from its ObjectController (its properties per slot, `anchor.*` for the crossing, its seed from `seeds.pilots.<entity>`), stepped after the ego's physics on its truth and moved kinematically within its acceleration limit; CS1's start trigger is the model's `start_gap` (`$ttc_entry`), as the subset keeps ActivateControllerAction seats-only; the walker decides where it can still stop at the kerb; `cs1_walker_gap_acceptance.xosc` the batch example (the description's CS1 stays refused: a storyboard SpeedAction on a model entity); (iv) the agreement with seats passed 2026-11-24 on K12's exit set 3 ("K10's agreement" below: the seats ego played back, no engine; the batch now takes a model entity as world-owned with the channel's lag 1), (v) the latency is K12's (set 3: lag 1 in lockstep and free-running); not covered: an engine in the loop, the engines' map-frame velocity |
| K12 | Truth-fed pilots: a command channel from a K4 attachment to the world server (`entity_command`: an entity's kinematic command, carried with the tick gate's acknowledgement, integrated and applied by the world, read back to SSv2, whose fork adopts it for a simulator-driven pedestrian), under lockstep held to one frame; for K10's behaviour models and learned background agents | component | K4 | swb 243 | landed 2026-11-23 (scensim 0cc054d8; the SSv2 fork's model pedestrian, COMMANDED on the world protocol, the CARLA world server's integrator, the bridge, truth schema 3, attachments' `commands:`, `scensim.behaviour.seats`); pedestrians first, CARLA only; exit passed 2026-11-23 on set 3, by the rule fixed before the runs ("K12's exit runs" below) |
| K11 | 093 D4's search (purpose B): an adaptive search over cells that writes the record's reserved `search` | component | K1, K7 | swb 241 | in progress: K11a done 2026-11-24 (`scensim-sample search`; "K11a's result" below, check 1's fourth part failed, its cause named); K11b, K11c open |
| K13 | A vehicle behaviour model ([vehicle-behaviour-model.md](../design/vehicle-behaviour-model.md)): the Intelligent Driver Model as a car-follower on a lane anchor, its coefficients a cited set (`zhang2024_highd_car`), commanded through K12's channel as it is (speed, heading, acceleration limit); K12's vehicle side in the fork and `scensim run`; numpy and torch bit for bit; seats against the batch; a first K11 search on a platoon | component | K10, K12, K11 | swb 241 | landed 2026-11-25 (scensim 73575ba9; issues 160, 163, 164, 165 after it); exit (corrected 2026-11-25 (133): exit check 4 had been misread as step (ii)'s check 4): exit checks 1 and 2 held (2 on its rerun after issue 163); check 3 held except one threshold event, failed with its cause ("K13's exit check 3" below); check 4 (step v, the search) held, 0 failures in 21000 runs, the tool's [0, 0] interval not an answer (issue 183), prediction 4 FAILED and 5 FAILED in part ("K13 step v's plan" below). The step (ii) runs' own check 4 (the trail, amended wording) held. Before: planned 2026-11-25 (user approved the model through 133); plan below, approved by 133 the same day |
| E1 | Examples | examples | the above | | open |

## K6: Jazzy for the whole set (plan, 2026-11-24, 243; approved by 133, before any build)

**What exists.** 082 step 7 shipped the simulation side on Jazzy in 0.2.0 (118): release.yml
builds the sim set in a ros:jazzy container, stages the Jazzy tarball and `scensim-ros-jazzy`,
and smokes it with a live SSv2 on colcon_scensim's fixture world server (no simulator, no
pilot); the Autoware side is checked against Autoware 2.1.0 Jazzy by build and resolve only.
Nothing runs the tests on Jazzy, nothing builds from a source checkout the way a developer does
(`just setup`, `just build`, `just test`), and no world server has driven a simulator on Jazzy.

**K6's scope**, the simulation side only (Autoware 1.5.0 is Humble only; the vehicle side
stays refused on Jazzy by name):

1. `just test`'s sim-side parts pass on Jazzy: the Rust workspaces (this one's, the protocol's,
   the CARLA world server's) under nextest, and the Python suites `just test` runs, in a
   ros:jazzy container from a source checkout;
2. the developer path on Ubuntu 24.04: `just setup` and `just build` with `ROS_DISTRO=jazzy`,
   PEP 668 handled as 082 step 7 does, no shims for Humble;
3. a live world server on Jazzy: `scensim_world_check conformance` against the CARLA world
   server built on Jazzy, on a CARLA 0.9.16 (the one GPU step, asked for first);
4. `just jazzy-check`: the build and those tests in the container, so the set stays
   Jazzy-clean.

Not in scope: acb, aib and Autoware on Jazzy (the vehicle side), the Isaac world server (it runs
in Isaac Sim's own Python), and publishing (0.2.x's release stays as is).

**Method.** One image, `scensim-jazzy-k6`, from `ros:jazzy` (local, 888 MB) with the build
tools, Rust, libclang 14, rosdep's keys as 082 step 7 sets them; builds capped at 4 jobs under a
memory guard. Each fix on its repository's branch, gated by that repository's Humble gate and a
Jazzy build and test of the same commit; pushes asked of 133 one by one.

**Predictions, written before any build:**

- the Rust crates build (release.yml builds them already); their tests pass unchanged, since none
  reads a ROS distro;
- the Python suites mostly pass on 3.12; the breaks, if any, are: tests or checks that name
  `/opt/ros/humble` or Humble's package set (scensim's host check: `rmw_cyclonedds_cpp`, the
  stock cars' descriptions); pytest and numpy versions on noble (numpy 1.26); deprecation
  warnings turned into errors (`datetime.utcnow`, `ast.Str`) where a suite runs with `-W error`;
- `scensim_batch` skips its torch tests (no torch in the image), as on a Humble host without it;
- `just setup` breaks at pip (PEP 668) unless it already carries 082 step 7's flags, and at
  any apt name that differs on noble;
- the relay's Autoware message dependencies (`autoware_adapi_v1_msgs`, `tier4_*`) resolve on
  Jazzy only as 0.2.0 resolves them (built from source in the sim set); if `just build` takes
  another path, that is a break;
- the conformance check passes on Jazzy as on Humble (the world protocol carries no ROS types).

**Seen so far** (2026-11-24, in `scensim-jazzy-k6`: `ros:jazzy` plus the build tools and
libclang 14, 1.4 GB; with rosdep's keys installed 5.39 GB; a 1.8 GB home volume for rustup,
cargo and pip; `/` kept 909 GB free):

- **not predicted**: the justfile needs `just` 1.40.0 or newer; 1.29 to 1.39 refuse it
  ("Non-default parameter `args` follows default parameter"), 24.04's apt `just` (1.21)
  refuses `[positional-arguments]`. An older `just` cannot parse the file, so no recipe can
  refuse it: development.md names the version, its install line and both errors (133).
- **as predicted**: `just setup`'s pip stops on PEP 668; rosdep's pip keys fail under sudo,
  which drops `PIP_IGNORE_INSTALLED` (Debian owns `typing_extensions`; 118's notes).
- **not predicted, outside Jazzy**: release.yml's rosdep step lacked `src/scensim_sampler`,
  which `scensim` depends on since K3; issue 146, fixed apart.
- **not predicted**: acb_bridge, which 0.2.0's simulation set builds on purpose (the vehicle
  side every non-Autoware pilot on CARLA starts), found no Rust bindings for
  `autoware_adapi_v1_msgs` when the vendored message packages were built in the same colcon
  run: colcon-cargo-ros2 resolves the bindings once, when the first Cargo package starts, and
  looks in `install/` and `/opt/ros/jazzy` only. On Humble the messages come from
  /opt/autoware, there before the build. The fix (133: option a): `third_party/sim_vendor`,
  sim.repos' message packages built once against ROS alone and sourced by `just build` on
  Jazzy where Humble sources Autoware, as `third_party/autoware_overlay` is built and sourced;
  the install layout stays Humble's. With it the simulation set built: the vendored packages
  (39) in 2 min 11 s, the simulation packages (45, acb_bridge included) in 11 min 21 s, 4
  workers.

**Result** (2026-11-24, 243). `just jazzy-check` passed on f8e65c58 (22:00 to 22:46, host load
3 to 27): a fresh worktree of HEAD in `scensim-jazzy-check` (1.47 GB; its home volume 3.9 GB
after setup), `just setup`, `just build` (the vendored packages, 39, in 3 min 5 s; the
simulation packages, 45, in 13 min 52 s), then `just test`, every suite:

| suite | Jazzy (f8e65c58) |
|---|---|
| Rust: the bridge, the protocol, the CARLA world server | 117, 188 (1 skipped), 212 passed |
| scripts | 125 passed, 14 skipped |
| scensim_launch | 394 passed, 17 skipped |
| scensim | 794 passed, 5 skipped |
| roboracer | 41 passed, 1 skipped |
| scensim_agent and the relay | 273 passed, 1 skipped |
| scensim_sampler | 141 passed, 2 skipped |
| scensim_batch | skipped: torch does not import |
| czp | 86 passed |
| scensim_world_server | 39 OK |
| scensim_isaac_world | 487 OK, 47 skipped (no aib, no pyproj) |
| autoware_sim_vehicle, the scenario vehicle checks | 40 passed, 8 skipped; 10 passed |

Python is 3.12 and numpy 1.26.4 (apt's). The developer path (item 2) ran from a fresh image and
home: install `just` 1.40.0, `just setup` (20 min, apt and rosdep included), `just build` (13
min). 241's bundle "jazzy scensim tests (241)" (2026-11-18) had already shown the Python suites
pass on Jazzy run by hand; this is the same through the recipes.

Against the predictions:

- the Rust crates: met, unchanged;
- the Python suites: met in sum, not in the breaks. None of the predicted breaks appeared (no
  Humble path or package named, no deprecation made an error). What broke were tests that
  leaned on the developer's host, which a fresh 24.04 does not have: carla's wheel in
  `~/.local` (6 keeper tests; the test now writes a stub wheel), the vehicle side's Autoware
  packages (3 stack tests; skipped when the vehicle side is not built), aib (the Isaac world
  server's surface layer imported it at load: issue 149, siw 7d032d6), pyproj (siw's lanelet
  heights; skipped without it), libclang 14 for `just test` and `just check` (they now set
  `LIBCLANG_PATH` off Humble as `just build` does), and rosdep's cache (`just setup` now runs
  `rosdep init` and `rosdep update` when they are missing, and prints them). Each also hid on
  Humble behind the developer's own host;
- `scensim_batch`: met, after a fix: its suite did not collect without torch; `just test` now
  runs it only when torch imports and says so;
- `just setup` and PEP 668: met;
- the relay's messages: not met. acb_bridge needed `third_party/sim_vendor` (above);
- the conformance check (item 3): met (below).

**Two failed runs, and a wrong first reading.** jazzy-check's runs 1 and 2 (0222418e) failed
the same way: four of `scripts/test_t3.py`'s stop tests timed out at their 30 s wait, and the
suite took 1072 s instead of about 64 s. Run 1 had shared the host with another project's CI
gate (20:38 to 21:04, up to 98 runnable threads on 32), and I read the failure as load. That
reading was wrong. Run 2, at load 3 to 4, failed identically, and the cause was the container:
`bash -c '...; just test'` makes `just` PID 1, which never reaps orphans. The tests' fake stack,
orphaned, stayed a zombie, and a zombie still counts as a member of its process group, so t3's
`stop_group` waited out every grace. With pytest as PID 1 the sigterm test fails at 30.3 s;
under `docker run --init` all 29 t3 tests pass in 22.6 s. check.sh runs with `--init` since
f8e65c58. t3 itself would hang the same way in any container without an init, a released
stack's included: issue 153 (241), fixed on main as 564600f8: t3's `stop_group`, `scensim`'s
stop and `scensim-agent supervise` count a group whose only members left are zombies as gone,
so the four tests pass without an init too (241, under a non-reaping subreaper). check.sh keeps
`--init`: the container's PID 1 reaps, as a host's does, for whatever else a test leaves.

**Item 3, the conformance check on Jazzy: plan and prediction** (133's OK, 2026-11-24, before
the run). The CARLA world server and `scensim_world_check` as `jazzy-check` built them (f8e65c58),
run in `scensim-jazzy-check` with the host's network and an init, against a CARLA 0.9.16 of my
own on the host (RPC 2100, Epic, Town01, the NVIDIA card; world port 5691, SSv2's 5655, so its
sensor-release sockets are 5656 and 5657), started only after 10 minutes with no other compute
on the GPU and stopped by its pid afterwards. `scensim_world_check conformance
tcp://127.0.0.1:5691 --map <Town01>`. The control: the Humble build of the same CARLA world
server (scensim_carla_world's pin is the same at 59439b38) checked against the same CARLA right
after. Prediction: the Jazzy server passes every check the Humble one passes, with the same
capabilities declared, since the world protocol carries no ROS types and both builds of
carla-sys use libclang 14. What could break is the one ROS-facing part, the node's parameters
(rclrs on Jazzy), which no test reads; if it does, the server starts on the config file's
values instead of the arguments, so the config given names port 2100 too.

**Item 3's result (2026-11-25): as predicted.** 133 relaxed the start rule before the run: the
check is functional, not a timing measure, so other compute does not void it; it needs 6 GB of
VRAM free (CARLA's 2 GB and 4 GB for the others' jobs), one heavy job on the host at a time, and
the others' jobs recorded. It started at 00:41, after another project's CI gate on the host
ended, with 8.9 GB free; on the card were a ddcm python (4.7 GB) and teacup1117's unidrivevla
python (9.5 GB) and CARLA 0.9.15 (on RPC 41000, 9.0 GB), and my CARLA took 2.0 GB.

| server | hello | conformance | capabilities |
|---|---|---|---|
| Jazzy (f8e65c58, in `scensim-jazzy-check`) | up, CARLA 0.9.16, protocol 4, ready | 28 passed, 0 failed, autopilot skipped (needs a road) | SIGNALS, AUTOPILOT, AGENT_VEHICLES, TRACKS_TARGETS, READS_BACK, WEATHER, CONTACTS, ROAD_CONDITION, ENVIRONMENT, ENVIRONMENT_APPLIED |
| Humble control (59439b38) | the same | the same 28 and the same skip | the same |

The node's parameters work on Jazzy: the server listened on 5691, which only the ROS parameter
`port` names (the config file has no world port, and the default is 5591), and connected to
CARLA on 2100. Afterwards my CARLA was stopped by its process group: no member of either group
left, and ports 2100 to 2102, 8100, 5691 and 5655 to 5657 free.

**The respawn under the stop: my harness, not launch.** The Humble control ran under plain
`ros2 launch` (ros-humble-launch 1.0.14), started by the run script as `setsid env -i ... bash
-c "...; exec ros2 launch scensim_carla_world scensim_carla_world.launch.xml ..." &`, where the
node is `respawn="true" respawn_delay="2.0"`. The stop sent SIGINT to the process group
(`kill -INT -<pgid>`), then SIGTERM 5 s later. The log:

```
16:43:13.304  scensim_carla_world: signal received, stopping
16:43:13.404  scensim_carla_world: Stopping: undoing what this server did to CARLA
[INFO] [scensim_carla_world-1]: process has finished cleanly [pid 2660099]
[INFO] [scensim_carla_world-1]: process started with pid [2694003]
16:43:15.443  scensim_carla_world: CARLA world server on tcp://127.0.0.1:5691 (pid 2694003) ...
```

launch's own `user interrupted with ctrl-c (SIGINT)` is not in the log: launch never saw the
SIGINT. A non-interactive bash starts a command run with `&` with SIGINT and SIGQUIT ignored,
and an ignored signal stays ignored across exec (the child's `SigIgn` is `0x6`; a Python started
so has `signal.getsignal(SIGINT) == SIG_IGN`). launch learns of SIGINT only through Python's
handler (`AsyncSafeSignalManager`, on `set_wakeup_fd`), so it never ran its shutdown. The
world server sets its own handler, so it stopped, and launch, not shutting down, respawned it
after its 2 s delay; the SIGTERM then ended launch and the new server. So it is not launch's
respawn racing its own shutdown. The product's stops are not of this shape: `stack_up.bash`
stops with SIGTERM, and `scensim`'s stack starts its trees with `subprocess.Popen` from a
Python whose SIGINT handler is set, so they start with SIGINT at its default. The recipes
`two-av` and `demo-tour` stop their screencast's `setsid ffmpeg ... &` with SIGINT; ffmpeg sets
its own handler, as the world server does, so it is unaffected. A harness that means to SIGINT
a `ros2 launch` it started with `&` from a script has to start it in the foreground of its own
session, or send SIGTERM.

**A host hazard found on the way.** On this Humble host a pip numpy 2.2.6 in `~/.local`
shadows apt's numpy 1.21, and apt's torch then fails at import (`_ARRAY_API not found`); a
torch test K11d added failed `just test` here for it (issue 151). development.md now names it
beside the setuptools rule.

**Lapses.** Containers ran with `--rm` after `just setup` had installed apt packages in
them, so the next step started without them; one kept container, committed as an image, fixed
it. Issue 146's first gate ran beside my own Jazzy image build and was stopped by its memory
guard. And the load reading above was reported before it was tested against a quiet run. Item 3's
first waiter refused to start the run for "another gate" when none was running: its test was
`ps ... | grep ... | cut ... && refuse`, and a pipe's status is its last command's, `cut`'s, so
it held whatever `grep` found; the run was started by hand after the same check read empty.
A test of a pipe's match uses `set -o pipefail` or tests the matched output itself.

**The landing gate (2026-11-25).** The full Humble gate (acb build, swb build, `just test`,
`just check`) passed on 30f9ddfa in a fresh worktree, 02:50 to 03:17, with 4 build jobs
(`SCENSIM_BUILD_JOBS=4`, acb's `CARGO_BUILD_JOBS=4` and `MAKEFLAGS=-j4`, colcon at 2 workers;
133's call, so it could run beside another project's training run, which held about 32 GB and had
stopped the first gate, on e5d1f889, by its memory guard at 02:33). `just test`'s counts against
issue 146's gate: Rust 117, 188 (1 skipped) and 212, as there; scripts 142 (139), t3's stop
tests among them; launch 409 and 2 skipped (the same); scensim 796 and 6 skipped (791 and 5);
the agent and relay 276 (274); the sampler 143 (139); `scensim_batch` 240 and 12 skipped (233 and
12), so the batch suite ran; the rest as there. The landed tree adds to the gated one only main's
own docs move (issue 157's doc and its README row), checked by `check_docs` and `check_pins`.

## K9's CS3: the pilot's map variants (2026-11-24, 243; reviewed by 133)

**The plumbing.** `world.pilot_maps` in testbench.yaml declares, per world map, the maps a pilot
may load: `{<world map>: {current: <itself>, <variant>: <map> | {map: <map>, pointcloud:
edited}}}`. `current` is the world's own map, not "up to date". A scenario binds a variant by
FileHeader `scensim.pilot_map` (`param:<parameter>` or a name; issue 131). `scensim run` refuses an undeclared
variant before any run, asks the stack for it (a switch request's `pilot_map`: the world keeps
its town, and the pilots restart on the variant's `map_path`, with no town load when only the
variant changes), and records `result.json` `maps: {world, pilot, variant, pointcloud}`.
`testbench check` refuses a variant that is not fetched, one on another projection
(`map_projector_info.yaml`), one whose point cloud is not the world's byte for byte unless it
declares `pointcloud: edited`, and a scenario binding a variant its world lacks. `compilable`
refuses the binding by name: no batched policy takes a map yet.

**The variant (the user's OK, relayed by 133, 2026-11-24).** In CS3 the works are props in the
world, and Town01's lanelets do not show them, so the stale map is plain Town01, which exists.
The map to publish is the updated one that shows the closure:

- the lane: west_street, lanelet 6583, the whole 224 m block between its junctions (from
  (325.6, -129.5) west to (101.4, -129.4)), closed whole so no lanelet is split;
- the world: three `static.prop.streetbarrier` MiscObjects across 6583 at s 20 (x 305.6, lateral
  -1.3, 0 and +1.3 m in its 4 m lane), placed by the CS3 scenario; CARLA's map is unchanged;
- the pilot's updated map, `Town01_west_street_closed`: Town01 with lanelet 6583 tagged
  `participant:vehicle = no`, which lanelet2's traffic rules (Germany, Vehicle, as Autoware's
  route handler builds them) read as not passable (`canPass` false, checked 2026-11-24); every
  other file byte for byte Town01's, anchors included;
- the point cloud: shared, byte for byte (the barriers are not in it; NDT localises on the
  buildings and kerbs), so no `pointcloud: edited`;
- declared as `pilot_maps: {Town01: {current: Town01, works: Town01_west_street_closed}}`.

If Autoware's route ignores the tag, the fallback (133) is to remove 6583 from the updated map
and drop west_street from its anchors; which one shipped is recorded here.

**The runs, predicted before any.** Project `scenarios/projects/k9_cs3`, the Autoware pilot
(scensim's profile, tesla_model3, clustering), CARLA 0.9.16 at Epic. The ego starts on lanelet
28257 (334.85, -79.03), heading south; its goal is on 32189 (92.38, -78.14), heading north.
lanelet2's shortest routes: on Town01, 28257, 41654, 6583, 42451, 32189 (358.5 m); on the
updated map, 28257, 42063, 28958, 39793, 21828, 41443, 32855, 42824, 32189 (490.0 m, 37 %
longer), so a route around the block exists.

- pm=current (the stale map): Autoware's route (its mission planner's `LaneletRoute`) holds
  6583, and the ego's truth enters 6583. Expected: lidar clustering sees the barriers and the
  ego stops before them, then stays stopped (no lane change into the oncoming lane) until the
  scenario's 240 s limit (exitFailure). Also a valid CS3 result, if it happens: perception
  misses the barriers and the ego touches one (a contact). Either counts as the stale map's
  case; what does not is a route without 6583.
- pm=works: the route holds no 6583, the ego's truth never enters it, and the ego reaches the
  goal within the limit (exitSuccess), about 490 m.

**Attempt 1 (2026-11-24): refused by SSv2, issue 131.** Both runs were SSv2 error runs before
the ego moved (`No such variable named "pm"`): a `$` in a FileHeader property is evaluated
before the parameters exist. The stack had switched correctly: pm=works restarted the pilots
alone on Town01_west_street_closed in 8.6 s, with no town load. Bindings now write
`param:<name>` (issue 131). For attempt 2 the scenario also binds a knob (`illumination =
param:light`, day only) and an anchor (`barrier_lane = west_street.lanelet_at(param:barrier_s)`,
which places the barriers by LanePosition), so the two runs show all three binding kinds
accepted by SSv2. Predicted besides the above: no SSv2 error; `result.json` `knobs.ok` true
(illumination day), `anchors.barrier_lane` 6583, `maps` with the variant's and Town01's
lanelet2 digests.

**Attempt 2 (2026-11-24): refused by SSv2, the scenario's.** SSv2's preprocessor accepted the
FileHeader (issue 131 holds) and refused the barriers' `miscObjectCategory="barrier"`, a valid
OpenSCENARIO category it does not implement; they are `obstacle` (as K12's van) for attempt 3,
with the same predictions. The stack again switched to the variant alone (8.8 s).

**Attempt 3 (2026-11-24): as predicted, both runs.** One stack (seat 0, CARLA 0.9.16 at Epic,
the Autoware pilot with scensim's profile and clustering), the variant placed by hand in
assets/maps until the dataset holds it.

| run | Autoware's route (mission planner) | ego in 6583 | outcome | contacts |
|---|---|---|---|---|
| pm=current (Town01, stale) | 28257, 41654, 6583, 42451, 32189 | from sim 29.5 s | stopped for good at sim 34.8 s, its nose about 5.8 m before the barriers (centre x 313.86, barriers at x 305.64), until the 240 s limit: exitFailure | none |
| pm=works (Town01_west_street_closed) | 28257, 42063, 28958, 39793, 21828, 41443, 32855, 42824, 32189 | never | reached the goal at sim 131.8 s: exitSuccess | none |

The routes are lanelet2's shortest, as predicted; the stale pilot plans through the closed
block and its perception stops it at the barriers, the updated pilot goes round. In both runs
SSv2 accepted the three bindings: `knobs.ok` true (illumination day, sun altitude 60 applied),
`anchors.barrier_lane` 6583 (the barriers stood at (305.64, -128.21 / -129.51 / -130.81)), and
`maps` with the pilot's lanelet2 digest (Town01 a85836f5..., the variant a2daf41c...); the works
run switched the pilots alone (8.7 s). The tag `participant:vehicle = no` shipped: Autoware 1.5's
route honours it, so the fallback was not needed. The variant carries no anchors files: with 6583
impassable lanelet2 gives it no followers, so `west_left_turn` cannot resolve there, and anchors
are read from the world's map only.

**Published:** the maps dataset's revision v2026.11f (commit 732fd61, 2026-11-24, with the user's
OK) adds `Town01_west_street_closed/`; the tag's files match the staged copy and its SHA256SUMS.
Only k9_cs3's lock moves to it: no other testbench takes the variant,
and every file they take is unchanged, so moving their locks would be churn.

## K9e: the same names on Isaac (plan, 2026-11-25, 243; approved by 133, before any code or run)

**What is unproven.** D2 says a CARLA town and an Isaac stage of one place declare the same
anchors and knobs, so one scenario runs on both. Every K9 run so far (K9a-d, the profiles, CS3)
was on CARLA. The anchors file is shared by construction: it sits beside the Lanelet2 map,
which both targets read. Three things have never been shown on Isaac: SSv2 placing a bound
entity there; Isaac's world server reading back a knob a binding set; and a pilot-map switch
on an Isaac stack, where aib's Autoware restarts on the variant with no stage reload.

**Step 1 (offline).** A project, `scenarios/projects/k9_cs3_isaac`: k9_cs3's scenario byte for
byte, `simulator: isaac`, Town01 and Town01_west_street_closed (v2026.11f) with
carla-0.9.16-isaac-usd's Town01, the Autoware pilot on aib (scensim's profile, tesla_model3),
the same `pilot_maps`. Its lock holds the same dataset commits as k9_cs3 and isaac_basic.

*Found in step 1 (2026-11-25):* `testbench check` passed both projects, yet CS3 cannot run
on Isaac as declared. Its illumination knob's value is `{weather: {sun_altitude_angle: 60}}`,
and on Isaac `knobs.plan` refuses every weather value by name (Isaac has no weather service);
the run would end as a `knob_refused` error run after the stack's start. Two findings: the
check did not hold a value to its simulator, issue 154 (fixed apart, 2f2c7a01); and no static
knob form was portable, though both world servers apply and read back the scenario
environment (`SetEnvironment`, `ENVIRONMENT_APPLIED`) that K9's profiles use. 133 chose to make
one (option A), rather than an Isaac copy of the scenario without the knob (option B), which
would prove less than K9 claims.

**The portable form (133's conditions).** A static knob value may carry `environment: {field:
number}`, the fields the profiles set: `sun_elevation`, `sun_azimuth`, `fog_visual_range`,
`precipitation_intensity` (both targets) and `cloud_cover_oktas` (CARLA only, as for a
profile). `weather:` stays, CARLA only. One value may not set the same quantity in both forms
(`environment.sun_elevation` and `weather.sun_altitude_angle`; `sun_azimuth` and
`sun_azimuth_angle`; `fog_visual_range` and `fog_density` or `fog_distance`;
`precipitation_intensity` and `precipitation`; `cloud_cover_oktas` and `cloudiness`): refused
by name, in `testbench check` and in the run. The run sends an `environment:` value as a
profile held constant from time 0 (one per field, named `<knob>.<field>`), through the
bridge's `set_knob_profiles`: the same send and read-back path, no bridge or world-server
change. A field set by the scenario's EnvironmentAction too, or by a profile knob, is two
writers and refused, as for a profile. `result.json` judges each field: every frame's
read-back after its send within the field's tolerance (half an okta; otherwise 1e-3 plus 1e-4
of the value), and none missing; a field off makes the run a `knob_profile` error run.
scenario-description.md section 3 says which form to use when. k9_cs3 and k9_cs3_isaac both
declare `illumination: {values: {day: {environment: {sun_elevation: 60}}}, default: day}` (as
first written: 60 meant degrees in a radians field, found in step 2b; pi/3 since, below).

Step 1's checks, before the runs: `testbench check` passes both projects; a unit test checks
that the same CS3 spec gets the same bound values on both simulators (barrier_lane 6583, light
day) and the same knob plan (one constant profile, `illumination.sun_elevation` at 60).

**Step 2a, CARLA under the new form (pm=current only).** k9_cs3 on CARLA 0.9.16 at Epic, seat 0,
predicted before the run: the same result as attempt 3: Autoware's route 28257, 41654, 6583,
42451, 32189; the ego enters 6583 and stops before the barriers for good, exitFailure at the
240 s limit; no contact; `anchors.barrier_lane` 6583 with attempt 3's `anchor_source`; `maps`
with Town01's lanelet2 digest a85836f5. The read-back is the same quantity, now through
`ENVIRONMENT_APPLIED`: `knobs.ok` true, `illumination.sun_elevation` read back 60 on every
frame after its send, within the stated tolerance of 0.007 deg (1e-3 plus 1e-4 of 60; the CARLA
world server reads the angle back as CARLA's float `sun_altitude_angle`, so a rounding below
that passes and a coarser one, a whole degree say, fails and is reported). Times (entry into
6583, the stop) are recorded, not judged. My own CARLA 0.9.16 on RPC 2100 (Epic, Town01, no town
change), the stack from this branch's own install, stopped cleanly afterwards.

**Step 2a's result (2026-11-25): as predicted, but for one line of the prediction, FAILED (wording).** k9_cs3
pm=current from f429787b's own install (wt-k9e, acb then swb from a clean environment), my
CARLA 0.9.16 on RPC 2100 (Epic, booted on Town01, no town change), seat 0, started at 01:38
with 10.3 GB of VRAM free; on the card were teacup1117's unidrivevla python (9.5 GB) and CARLA
0.9.15 (on RPC 41000, 7.4 GB) and a ddcm python (4.7 GB).

| | attempt 3 (weather form) | step 2a (environment form) |
|---|---|---|
| Autoware's route | 28257, 41654, 6583, 42451, 32189 | the same |
| ego in 6583 | from sim 29.5 s | from sim 30.2 s |
| stopped for good | sim 34.8 s, centre x 313.86 | sim 35.2 s, centre x 313.91 (y -129.49) |
| outcome | exitFailure at 240 s | exitFailure at 240 s |
| contacts | none | none (`contacts`, `npc_contacts` empty) |
| barriers (truth, map frame) | x 305.64; y -128.21, -129.51, -130.81 | the same |
| knob read-back | `sun_altitude_angle` 60.0 (get_weather) | `sun_elevation` 60.000001 on 5019 of 5019 frames after its send (frame 1), max deviation 9.7e-7 against 0.007; `knobs.ok` true. **Withdrawn (2026-11-25, after step 2b):** the field is in radians, so the value sent was 60 rad, and CARLA's sun stood at 3437.7 deg of altitude; the read-back only echoed it (below) |
| `maps` lanelet2 digest | a85836f5... | the same |
| `anchors.barrier_lane` | 6583 | 6583 |
| `anchor_source` | digests ee291b6e..., 428462cc...; commit 19d52699 | the same digests; commit 732fd615: **FAILED (wording)**, below |

**FAILED (wording): "attempt 3's `anchor_source`".** The data is right; the prediction was
not. Cause: the map's and the
file's digests are attempt 3's (ee291b6e..., 428462cc...), but `commit` is now 732fd615 (the
maps dataset's v2026.11f) where attempt 3's was 19d52699 (v2026.11e), because k9_cs3's lock
moved to v2026.11f after attempt 3 (ca3c8b1d), with the anchors file unchanged byte for byte.
The prediction should have said the lock's commit. *Amended after step 2a, before step 2b:*
step 2b's `anchor_source` comparison is with step 2a's (732fd615), which k9_cs3_isaac's lock
holds too. Times were
recorded, not judged. Afterwards `--stop-stack` stopped the stack, my CARLA was stopped by its
process group (nothing of the group left, ports 2100 to 2102 and 8100 free), and no stack
process was left with parent 1.

**Step 2b, the runs on Isaac.** Isaac Sim 6.2 from NVMe; run when the card has room for Isaac
and Autoware with 4 GB left for the others' jobs, no CARLA of mine up, one heavy job on the
host; the others' jobs recorded; timing not judged. pm=current, then pm=works, on one stack.
Predicted, before any run:
- no SSv2 error;
- `result.json` `anchors.barrier_lane` 6583 with the same `anchor_source` as step 2a's (map and
  file digests, dataset, commit 732fd615; *amended after step 2a, before step 2b*: it read
  CARLA's, which the attempt-3 wording would have made attempt 3's); `knobs.ok` true, with `illumination.sun_elevation` read back 60
  from Isaac's `ENVIRONMENT_APPLIED` on every frame after its send, within 0.007 deg; `maps` with the two lanelet2
  digests as on CARLA (Town01 a85836f5..., the variant a2daf41c...);
- the barriers' truth positions within 0.05 m in x and y of CARLA's (305.64; -128.21,
  -129.51, -130.81), compared in the map frame (SSv2's, right-handed): CARLA's numbers are
  after its world server's Y-flip, as the truth file holds them, and Isaac's need no flip;
- Autoware's routes the same lanelet lists as on CARLA (lanelet2 on the same map);
- pm=current: the ego enters 6583 and stops before the barriers until the 240 s limit
  (exitFailure; on Isaac the barriers are the bounding box's 0.4 x 1.2 x 1.1 m, and lidar
  clustering sees them); a contact also counts as the stale map's case, a route without 6583
  does not;
- pm=works: the route holds no 6583, the ego never enters it and reaches the goal, about
  490 m (exitSuccess); the switch restarts the pilots alone, with no stage reload.

Named risks: a 490 m Autoware drive on Isaac Town01 has not been run before, and a drive
failure not of K9's making is the pilot's result, not a binding failure; a stage reload on the
switch, or aib not restarting on the variant, is a K9 finding, reported before any rerun.

**Step 2b's result (2026-11-25): the knob FAILED, by my units error; the rest as predicted.**
k9_cs3_isaac, suite `both` on one stack, from f429787b's own install (wt-k9e; scensim_isaac_world
46c09ec, aib as pinned there), Isaac Sim 6.2 from NVMe, seat 0. The waiter started it at 05:25,
the card's other jobs then teacup1117's unidrivevla python (9.5 GB), with 39 GB of memory
available; by its end a ddcm python (5.6 GB) and teacup1117's CARLA 0.9.15 (6.6 GB) had come
back. Both runs are error runs (`knob_profile`), so neither counts as a result until rerun.

| | pm=current (Town01, stale) | pm=works (Town01_west_street_closed) |
|---|---|---|
| Autoware's route | 28257, 41654, 6583, 42451, 32189 (CARLA's) | 28257, 42063, 28958, 39793, 21828, 41443, 32855, 42824, 32189 (CARLA's) |
| ego in 6583 | from sim 27.85 s | never |
| outcome (SSv2) | stopped for good at sim 32.4 s, centre x 314.77 (y -129.59), before the barriers; exitFailure at 240 s | reached the goal at sim 129.3 s: exitSuccess |
| contacts | none | none |
| barriers (truth, map frame) | x 305.64; y -128.21, -129.51, -130.81: CARLA's to the centimetre | the same |
| `anchors.barrier_lane` | 6583, `anchor_source` step 2a's (digests, commit 732fd615) | the same |
| `maps` | Town01, a85836f5 | the variant, a2daf41c; the switch restarted the pilots alone in 10.0 s, no stage reload |
| knob | **FAILED**: `sun_elevation` read back -0.3097 on every frame, 60.31 off | **FAILED**, the same |

*The knob's cause: my value, not either world.* `sun_elevation` is in radians: OpenSCENARIO's
Sun, the bridge's profile field (`Field::SunElevation`, "rad above the horizon") and both
world servers use radians. I wrote `environment: {sun_elevation: 60}` meaning 60 deg, so
both worlds were sent 60 rad. Isaac placed its sun along that direction and read back the
physical elevation: asin(sin 60) = -0.3097 rad, the value logged. It was right to fail. The
CARLA world server turned 60 rad into `sun_altitude_angle` 3437.7 deg and its read-back
converted the same number back, 60.000001: an echo of an impossible angle, not the 60 deg sun
of attempt 3. So step 2a's knob line is withdrawn (its other lines stand: the ego's perception
is lidar's, which no light changes) and step 2b's knob line is FAILED. Nothing checked the
unit: the unit test's `ENV_WORLD` used 60 too, as did the docs' example and both
testbenches, and 133's own note setting the Isaac prediction said "sun_elevation 60" (133 asked
that this be recorded too). The unit was assumed, not read; the bridge's doc comment said rad.

**The fix and the reruns (133's OK, 2026-11-25, before any code or rerun).**
1. One rule in `knobs`, for the check and the run: each environment field's unit and range,
   `sun_elevation` [-pi/2, pi/2] rad, `sun_azimuth` [0, 2 pi) rad, `fog_visual_range` above 0 m,
   `precipitation_intensity` 0 or more mm/h, `cloud_cover_oktas` [0, 8]. A static value, or a
   profile knob's declared range, outside it is refused by name, naming the unit and, for an
   angle, the conversion ("60 deg is 1.0472 rad"). The bridge's JSON is unchanged. Oktas
   stop at 8 by design: WMO's 9 is "sky obscured", not an amount (issue 161's follow-up).
2. Both testbenches declare illumination day as `environment: {sun_elevation: 1.0471975511965976}`
   (pi/3, 60 deg); the docs' examples say rad and use pi/3; the tests use radians, and one shows
   60 refused.
3. The reruns, predicted here before them. Step 2a again (CARLA, pm=current), as predicted
   above but for the knob: `illumination.sun_elevation` read back 1.0472 rad on every frame
   after its send, within 1e-3 plus 1e-4 of the value, 0.0011 rad (0.06 deg); CARLA's
   `sun_altitude_angle` shows 60.0 deg, attempt 3's sun (read from the world server's log or
   get_weather, recorded). Step 2b again (Isaac, both), with the same waiter and conditions:
   as predicted above, with the same read-back of 1.0472 rad within 0.0011 rad from Isaac's
   `ENVIRONMENT_APPLIED`.
4. A note: the CARLA world server stores the angle it is given and its read-back converts the
   same number back, so on CARLA a read-back is no physical check of an angle out of range.
   The rule in 1 closes that for knobs; issue 161 (243, after K9f; K9e does not wait for it)
   makes the world servers validate `SetEnvironment`'s fields themselves, refusing by name,
   and read back the physical value.

**A correction to K9e's CARLA read-backs (2026-11-25, issue 171).** Each "read back on N of N
frames after its send" on CARLA below was one `EnvironmentReply`, taken right after the single
send and carried onto every frame; CARLA 0.9.16 can return the weather before a send until it
ticks (issue 171's probe). Those replies happened to be fresh (each showed the value sent), so
the conclusions hold, but that judgement could not have caught a lag; K9f-b's none-case then
showed one (a false error run). Since issue 171 a constant is sent twice and judged from the
second reply. Isaac's read-backs have no such lag.

**Step 2a again (2026-11-25, after the units fix d80dfd41): as predicted.** k9_cs3 pm=current, the
same install (its Python links to the source, so the fix ran) and setup, my CARLA on RPC 2100,
started at 05:52 with 10.9 GB of VRAM free; on the card teacup1117's unidrivevla python (9.5 GB)
and CARLA 0.9.15 (6.9 GB) and a ddcm python (4.7 GB).

- The knob: `illumination.sun_elevation` read back 1.0471975511965976 rad on 5039 of 5039 frames
  after its send, deviation 0.0 against 0.0011; `knobs.ok` true. The CARLA world server's log
  shows the sun it set, `Sky { ... sun: Some((270.0, 60.0)) }`: altitude 60 deg, attempt 3's
  (the first step 2a's line read `(270.0, 3437.7468)`). The azimuth, 270 deg, is the field's
  for a sun not yet placed (scenario azimuth 0, north); attempt 3 set only the altitude, so the
  azimuth is not compared.
- The rest as in step 2a and attempt 3: route 28257, 41654, 6583, 42451, 32189; the ego in 6583
  from sim 31.2 s, stopped for good at 36.2 s, centre x 313.96 (y -129.50), before the
  barriers; exitFailure at 240 s; no contact; barriers at x 305.64, y -128.21, -129.51, -130.81;
  `anchors.barrier_lane` 6583 (commit 732fd615); `maps` a85836f5. CARLA stopped by its group,
  nothing left, ports free.

**Step 2b again (2026-11-25, after the units fix): as predicted.** k9_cs3_isaac, suite `both` on
one stack, from the same install (wt-k9e at f429787b's build, its Python linking the source with
the fix d80dfd41; scensim_isaac_world 46c09ec), Isaac Sim 6.2 from NVMe. The waiter started it at
08:01 with no other compute job on the card and 45 GB of memory available; by its end
teacup1117's unidrivevla python (9.5 GB) and CARLA 0.9.15 (8.9 GB) had come back.

| | pm=current (Town01, stale) | pm=works (Town01_west_street_closed) |
|---|---|---|
| Autoware's route | 28257, 41654, 6583, 42451, 32189 (CARLA's) | 28257, 42063, 28958, 39793, 21828, 41443, 32855, 42824, 32189 (CARLA's) |
| ego in 6583 | from sim 26.9 s | never |
| outcome (SSv2) | stopped for good at 31.4 s, centre x 314.90 (y -129.56), before the barriers; exitFailure at 240 s | the goal at sim 128.4 s: exitSuccess |
| contacts | none | none |
| barriers (truth, map frame) | x 305.64; y -128.21, -129.51, -130.81: CARLA's to the centimetre | the same |
| `anchors.barrier_lane` | 6583, step 2a's `anchor_source` (file 428462cc..., commit 732fd615) | the same |
| `maps` | Town01, a85836f5 | the variant, a2daf41c; the pilots alone restarted, in 9.8 s, no stage reload |
| knob | `illumination.sun_elevation` read back 1.0471975511965979 rad on 4944 of 4944 frames after its send, deviation 2.2e-16 against 0.0011; `knobs.ok` true | the same, 2568 of 2568 frames |

So one scenario, byte for byte, ran on CARLA and Isaac with the same names: the anchor bound the
same lanelet and placed the barriers at the same map-frame positions, the knob's environment
form was applied and read back by both worlds, and the pilot map variant switched only the
pilots on both. Times are recorded, not judged.

**Step 3, the close-out.** K9's row to done, with the Isaac result; scenario-description.md's
"the same names on every target" marked built. D2's region-scoped knobs (`applies:`) and
`zone_layout` are K9f (243, plan only; it says how its CARLA side relates to 086 C7).

## K9f's plan: region-scoped knobs and prop layouts (2026-11-25, 243; approved by 133 with its conditions, before any code)

D2 (scenario-description.md section 3) leaves two things that K9a-e did not build: a surface
knob that `applies:` to named regions rather than the whole road, and `zone_layout`, a prop set
as a knob value. Read first: 086's C7 row, C4's record (named surface maps, landed 2026-11-20,
done 2026-11-25), and off-road-surfaces.md D3 ("the map says where, the scenario says what
state").

### What exists

- **Where:** a map's zones are polygons in `<map>/surfaces.yaml` (or a named map,
  `surfaces/<name>.yaml`, which a scenario picks with `scensim.surface_map`; C4). This is 086's
  surface record, the shared data.
- **What state:** the scenario's `RoadCondition` carries `scensim.zone.<id>.<field>` (`class`,
  `wetness`, `water_depth`). The SSv2 fork sends it, and the bridge forwards it as
  `SetRoadCondition` to a server that declares `CAPABILITY_ROAD_CONDITION`.
  - Isaac's surface layer checks the properties against the loaded map and applies them.
  - The CARLA world server applies only the world-wide scale and wetness, and refuses
    `scensim.` properties.
  - Making CARLA read the zones (friction trigger boxes, class `mu` x `wet`) and take the zone
    fields is 086 C7. It is 118's track and not started.
- **Knobs:** a static surface knob today names a surface map (`surface_map:`, Isaac) or a
  world-wide friction (`mu`). The scenario's RoadCondition sends it, and it is not read back:
  `unverified`, issue 095.
- **K9c's regions:** polygons in the map's `anchors.yaml`, for reading geometry (`area`, the
  centroid, `from_<lane>`/`to_<lane>`). Nothing applies state through them.

### The decision: one implementation

**K9f's CARLA side is C7, not a second path.** K9f adds no CARLA world-server code. A
region-scoped knob reaches either world as `scensim.zone.<id>.<field>` in a RoadCondition, the
form both servers will take:
- Isaac's surface layer takes it today.
- CARLA 0.9.16 cannot: see the amendment below.

K9f's check refuses a zone-scoped value on a world server that does not declare `ROAD_ZONES`
(below), which K9f sets on Isaac.

*Amended 2026-11-25, after C7's probes (086, P0's and P0b's results; 133 chose C7's option 2).*
On CARLA 0.9.16 zones stay refused and the CARLA world server does not declare `ROAD_ZONES`:
CARLA 0.9.16's friction trigger sets all four wheels of a car by its body's overlap, and its value reaches every car of the same blueprint, in the box or not; a per-wheel `apply_physics_control` stays on its car, but every apply rebuilds the PhysX vehicle (a 0.14-0.15 m/s step whatever the friction, and a yaw chatter of about +-1.1 deg/s when the wheels differ). So K9f-a's refusal on CARLA cites that measured limit, not "until C7", and zones on
CARLA are revisited on CARLA 1.0 (Chaos) after 083 step 5. On 0.9.16, C7 adds the world-wide
read-back instead (`ROAD_CONDITION_APPLIED`, below). K9f still adds no CARLA code.

**Zones, not anchor regions, carry state.** A knob `applies:` to zone ids of the map's surface
record, never to K9c's anchor regions, so there is one polygon per place that has state. Where a
scenario also wants a zone's geometry (its area, say), its anchors.yaml region names the zone
(`{zone: <id>}`) and resolves its polygon from `surfaces.yaml`. A second copy of the outline is
refused.

### K9f-a: zone-scoped surface knobs

- **The form.** A static knob value may carry `zones: {<zone id>: {class?, wetness?,
  water_depth?}}`, with the fields as `scensim.zone.<id>.<field>` names them. Example:
  `surface: {values: {dry: null, wet_junction: {zones: {junction_1: {wetness: wet}}}}}`. A
  value without `zones:` is world-wide, as today, which is D2's `applies: route`.
- **How it reaches the world.** The scenario binds the knob (`scensim.knob.surface =
  param:road`), as every knob is bound. Before SSv2 starts, `scensim run` writes the value's
  zone fields into a RoadCondition in the scenario's Init, with the same properties a scenario
  writes by hand today. SSv2, the bridge and the world servers see nothing new.
  - The rewritten scenario is a new file in the run's directory. `resolved.yaml` names it
    beside the source, which it names today by path, sha256 and parameters. `scensim run`
    never rewrites a scenario today, so this is new (decision 2).
  - A scenario that already sets one of those zone fields itself is refused: two writers, as
    for the environment form.
- **The check.** `testbench check` refuses each of these by name:
  - a zone id that the map's surface record (or the named map the scenario picks) lacks;
  - a class not in the table;
  - a `class` on a soil zone (refused as C4 refuses it);
  - a zone-scoped value on a simulator whose world server lacks `ROAD_ZONES`: on CARLA 0.9.16,
    naming the measured limit above (*amended*: was "until C7 lands").

  This is issue 154's one-rule pattern: the check and the run use the same function.
- **The read-back.** Issue 095 left surface maps `unverified`. K9f-a adds the applied zones to
  the world's answer: `ROAD_ZONES`, a `SetRoadCondition` reply listing each zone's applied
  fields, recorded in `result.json` `knobs.<knob>.zones`. A mismatch is an error run.
  - Isaac's surface layer already holds the overridden zones and answers from them.
  - *Amended:* CARLA 0.9.16 answers the world-wide part only (`ROAD_CONDITION_APPLIED`, C7:
    friction scale and wetness read back from the cars' physics control, zones empty), which
    closes issue 095's "unverified" for CARLA's world-wide condition; it lists no zone.
  - This is the one protocol change, a reply field with a capability bit. It is
    scensim_world_protocol's, pinned in lockstep.
- **Exit checks, with predictions before any run.**
  - Isaac Town01: `isaac_soil`'s zones. A knob takes one zone to `wet` against `dry`. The
    applied zone is read back. The ego's stopping distance across the zone differs as the
    class table's wet factor predicts, within C7's 25 % band, so the same number later checks
    CARLA.
  - CARLA 0.9.16 (*amended*): the same scenario refused by name, before any run, citing the
    measured limit; no zone run on CARLA. C7's own 0.9.16 acceptance covers the world-wide
    read-back.

### The protocol change, shared with 086 C7 (fixed 2026-11-25, for 118's C7 plan; amended the same day: two capabilities)

One change to `scensim_world.proto`, shared by K9f-a (Isaac's side, the bridge's read) and C7
(CARLA's side). Whichever lands first adds it as written here; the other cites it.

```proto
// in enum Capability:
  // `scensim.zone.<id>.<field>` properties in `SetRoadCondition` (092 K9f-a): the server applies
  // each field to that zone of its map's surface record and lists every zone the condition named
  // in `RoadConditionReply.zones`. Needs `ROAD_CONDITION_APPLIED`. A server without it is sent no
  // `scensim.zone.` property by a check that knows; one that is sent one anyway refuses it, as
  // before.
  CAPABILITY_ROAD_ZONES = 13;
  // `RoadConditionReply` to `SetRoadCondition` (092 K9f-a, 086 C7): the road state the world
  // applies after it, read back from the simulator, for the world-wide part (and, with
  // `ROAD_ZONES`, the zones). Needs `ROAD_CONDITION`.
  CAPABILITY_ROAD_CONDITION_APPLIED = 14;

// A zone's state as the server applies it after a `SetRoadCondition`.
message ZoneApplied {
  // The class of the table the zone now has (the condition's, else the map's).
  string surface_class = 1;
  // Its OpenSCENARIO wetness level (dry, moist, wetWithPuddles, lowFlooded, highFlooded).
  string wetness = 2;
  // Its water depth, m, when it has one (a ford); unset otherwise. A one-member oneof, not
  // proto3 `optional`, which Jammy's protoc 3.12 refuses without an experimental flag: the same
  // wire format and presence (Python `HasField("water_depth")`, prost `Option<zone_applied::Depth>`).
  oneof depth { double water_depth = 3; }
  // The friction coefficient its surface now gives a tyre: the class's mu times the wetness
  // factor, times the condition's friction_scale_factor (the class table's numbers).
  double mu = 4;
}

// A server with `ROAD_CONDITION_APPLIED` answers `SetRoadCondition` with the road state it now
// applies, read from its own model (Isaac: the surface layer; CARLA: the cars' physics control),
// for the world-wide part; with `ROAD_ZONES` also every zone the condition named (empty
// otherwise). A zone the condition did not name is as the map has it and is not listed.
message RoadConditionReply {
  double friction_scale_factor = 1;
  string wetness = 2;
  map<string, ZoneApplied> zones = 3;
}

// in message Reply's oneof reply:
    RoadConditionReply road_condition = 12;
```

No `PROTOCOL_VERSION` bump, by the file's own rule, for each capability: only a server declaring
`ROAD_CONDITION_APPLIED` sends the reply, and the bridge reads it only from one; only a server
declaring `ROAD_ZONES` fills its `zones`, and is sent zone properties by a check that knows;
a capability an older peer does not know is one it never declares. This mirrors
`ENVIRONMENT_APPLIED`. Who declares what: CARLA 0.9.16 declares `ROAD_CONDITION_APPLIED` only
(C7); Isaac declares both (K9f-a).

*Amended 2026-11-25 (118's proposal, endorsed by 133).* The first text (28574f29) had one
capability, `ROAD_ZONES`, gating the whole reply. C7's probes then found zones not expressible
on CARLA 0.9.16 (above), while a world-wide read-back there is: 133 wanted it, to close issue
095 for CARLA's world-wide condition. With one capability that reply could not be sent without
claiming zones, and the no-bump argument rested on that one gate; with two, each holds alone.
118's C7 plan (086, cba0fbfe) had already taken per-zone `mu`, no fords on CARLA and the
split-mu question; the last is now answered by the measured limit, and zones are not declared
on CARLA 0.9.16 at all. *Amended again the same day (118, before either side landed it):*
`water_depth` is `oneof depth { double water_depth = 3; }` instead of `optional double`, since
Jammy's protoc 3.12.4 refuses proto3 `optional` without `--experimental_allow_proto3_optional`
in scensim_core's prost build and the Python shell's descriptor script; the wire format and the
presence are the same. *Landed with 086 C7 (2026-11-25):* 118 added it first, as amended, in scensim_world_protocol
f2d9103 (main c8ca43e0), checked against this text (capabilities 13 and 14, `ZoneApplied` with
`surface_class`, the `depth` oneof and `mu`, `RoadConditionReply` at Reply's 12); K9f-a cites it
and adds none. The bridge records the reply in the gap trace (a `road` line per
`SetRoadCondition`), and `scensim run` judges each knob-set zone against it: `result.json`
`knobs.<knob>.zones.<id>` with the fields sent and read back, a mismatch an error run.

### K9f-b: prop layouts as a knob

- **The form.** A layout is a list of props beside the map, `<map>/layouts/<name>.yaml`. Each
  prop is an OpenSCENARIO MiscObject (category, model, bounding box) with a pose bound to an
  anchor: `lane: west_street, s: 20, offset: -1.3` or `point: <anchor>`. The knob's value names
  a layout or none: `works: {values: {none: null, closed: {layout: west_street_closed}}}`.
- **How it reaches the world.** As K9f-a does: before SSv2 starts, `scensim run` adds each prop
  to the run's resolved scenario as a ScenarioObject with an Init TeleportAction on a
  LanePosition. The lanelet and its s come from the anchor, exactly as K9b's bindings compute
  them.
  - SSv2 owns the props, so its collision verdict and the truth see them.
  - Both targets already spawn MiscObjects: CS3's barriers on CARLA, and cubes or the dressed
    props on Isaac.
  - No world server changes.
  - Props the world spawns behind SSv2's back would be invisible to the verdict: refused as a
    design.
- **The check.** `testbench check` refuses each of these by name:
  - a layout the map lacks;
  - a pose off its lane;
  - a category SSv2 does not implement (issue 131 and CS3's `barrier`);
  - a prop name that clashes with a scenario entity.
- **The exit check.** CS3 rewritten: its three barriers move from the scenario into
  `Town01/layouts/west_street_closed.yaml`, bound by a knob. Both maps' runs repeat attempt 3's
  results on CARLA, and K9e's on Isaac: the same barrier truth positions within 0.05 m, the
  same routes and the same outcomes.

### Order and dependencies

1. K9f-b first. It needs nothing from C7, and CS3 is its exit.
2. Then K9f-a: Isaac's side and the protocol field. *Amended:* CARLA 0.9.16 has no zone half;
   its world-wide read-back is C7's, and zones on CARLA wait for 1.0 (083 step 5).

Both start after K9e lands.

### 133's answers (2026-11-25)

1. **One implementation, agreed:** K9f's CARLA side is C7. 133 tells 118, who owns C7. C7 gains
   one acceptance line, the zones' read-back on CARLA, and sets `ROAD_ZONES`. When K9f-a lands,
   this is recorded both here and in 086's C7 row. *Amended after C7's probes:* on 0.9.16, C7
   sets `ROAD_CONDITION_APPLIED` (the world-wide read-back) and not `ROAD_ZONES`.
2. **The run's copy, on four conditions:**
   - the copy is saved in the run record beside the source;
   - both digests are in `resolved.yaml`;
   - the injection is deterministic: the same inputs give a byte-identical copy, with a test;
   - a source that already defines an injected entity or zone field is refused as two writers.

   projects-and-pilots.md says that what a run executes is the copy.
3. **Read-back in K9f-a.** It matches K9e's environment form, and an unverified zone is the gap
   issue 095 left.
4. **Sizes as planned.** K9f-b comes first, and both start after K9e lands.

**A dependency.** 118's issue 158: the road layer double-counts the grade on road-detail
worlds. If Town01's Isaac stage has road detail on any grade, K9f-a's stopping-distance exit
on Isaac runs after 158's fix. Town01's `isaac/world.yaml` (carla-0.9.16-isaac-usd 38347e26)
names no road detail, and neither does isaac_soil. 118's answer (2026-11-25): 158 touches
road-detail worlds only. The road layer, whose contact double-counts the grade, is built only
when the map has a `road_detail.yaml` (`world.py`'s `_load_road` returns early without one).
The surface layer's soil and friction zones and the roll bars never use the cams' slope, and
the soil resistance is a separate path that is right. Town01's only road detail is siw's
example (`examples/road/town01/road_detail.yaml`), which applies only if it is copied in, and
Town01 is level. So K9f-a's stopping-distance exit on Town01 does not wait for 158's fix.

## K9f-b: prop layouts as a knob (spec and predictions, 2026-11-25, 243; before any code or run)

As K9f's plan (above), with what building it decides:

- **The layout file.** `layouts/<map>/<name>.yaml` in the testbench, or `<map dir>/layouts/<name>.yaml`
  published with a map; a name in both is refused. *A deviation from the plan, for 133:* the plan
  put layouts beside the map only, but a map directory is a link into the shared dataset cache,
  and a file there needs a maps dataset revision, published with the user's OK; so a testbench
  may carry its own, and CS3's lives in its testbench. Its form:

  ```yaml
  layout: 1
  props:
    barrier_a:
      category: obstacle                 # OpenSCENARIO miscObjectCategory, one SSv2 implements
      model: static.prop.streetbarrier   # the MiscObject's name: the simulator's asset key
      mass: 50
      box: {center: [0, 0, 0.55], dimensions: [0.4, 1.2, 1.1]}
      at: {lane: west_street, s: 20, offset: -1.3}   # or {point: <anchor>}
      h: 1.5708                          # rad: relative to the lane, absolute at a point
  ```
- **The knob.** A static value may carry `layout: <name>` (one layout, or `null`), on every
  target: `works: {values: {none: null, closed: {layout: west_street_closed}}, default: none}`.
- **The run's copy.** With a layout bound, `scensim run` writes `<run dir>/scenario.xosc`: the
  source with each prop added as a `ScenarioObject` (a `MiscObject`) at the end of `Entities` and
  a `Private` `TeleportAction` at the end of the Init's `Actions`, on a `LanePosition` with the
  literal lanelet (`anchor.<lane>.lanelet_at(s)`) and lanelet-local s (`local_s(s)`), or on a
  `WorldPosition` at a point anchor. Relative file references in the source (`Directory path`,
  `LogicFile filepath`) are made absolute from the source's directory, so the copy runs from
  the run directory; `$(env ...)` and `$`-parameters stay as they are. Props are written in
  name order and the copy is serialised the same way every time: the same source, layout and
  anchors give a byte-identical copy (a test). SSv2 is handed the copy; `override_parameters`
  as before. `resolved.yaml` `scenario` gains `copy: {path, sha256, layouts: [...]}` beside the
  source's `path` and `sha256`; `result.json` `knobs.<knob>.layout` names the layout, its
  file's sha256 and each prop's placed lanelet, s, offset and the map-frame x, y it resolves to
  (*amended in building:* the x, y only on a lane resolved with its centreline; Town01's
  `anchors.resolved.json` at v2026.11f has none, so CS3's record has the lanelet, s and offset
  and the truth file shows where each prop stands).
  projects-and-pilots.md says that what a run executes is the copy.
- **Refused, by name, in `testbench check` and in the run (one rule):** a layout neither place
  has; a lane or point anchor the world lacks; an s off its lane; a category SSv2 does not
  implement (issue 131's and CS3's `barrier`); a prop name that is already a scenario entity,
  or in two bound layouts (two writers); a layout knob on a distribution (SSv2's own draws,
  as for profiles).
- **Not in K9f-b:** props spawned behind SSv2's back (refused as a design), a layout's read-back
  beyond the truth (the props are SSv2's entities, so the truth file shows where they stand),
  and issue 166's reversed-stretch rule on a layout's props, which become LanePositions only in
  the run's copy (issue 174, after K9f-b; CS3's are clean: `lane_positions.fixed_problems` on its
  CARLA copy returned `[]`, and lanelet 6583 has no reversed stretch).

**Exit runs, predicted before any.** A scenario `cs3_layout.xosc` in both k9_cs3 and
k9_cs3_isaac (byte for byte): CS3 without its three barriers and without the `barrier_lane`
binding, binding instead `scensim.knob.works = param:closure`; the barriers move to
`layouts/Town01/west_street_closed.yaml` in each testbench (the same file), at west_street s 20
with offsets -1.3, 0 and 1.3 and h pi/2 relative, as CS3 had them. CS3 itself stays as it is.

- CARLA 0.9.16 (my CARLA on RPC 2100, Epic, Town01), closure=closed, pm=current and pm=works:
  attempt 3's and K9e step 2a's results: the stale route through 6583 and a stop before the
  barriers, exitFailure at 240 s; the round route and exitSuccess; no contact.
- CARLA, closure=none, pm=current: no barrier in the copy or the truth; the ego drives the
  stale route through 6583 unobstructed and reaches the goal, about 358 m: exitSuccess.
- Isaac Sim 6.2, closure=closed, pm=current and pm=works: K9e step 2b's results, the same way.
- In every closed run the barriers' truth positions equal CS3's (x 305.64; y -128.21, -129.51,
  -130.81) within 0.01 m, in the map frame; `knobs.works.layout` names the layout and its props
  on lanelet 6583 at s 20; `resolved.yaml` names the copy and both digests.
- Two runs of the same case make byte-identical copies (the same sha256).

**The first CARLA suite (2026-11-25, on main ec592085 with K9f-b's commits; before issue 171).**
`suites/layout.yaml` on k9_cs3, my CARLA 0.9.16 on RPC 2100 (Epic, booted on Town01), one stack,
09:50-10:01:

| case | verdict | as predicted |
|---|---|---|
| closure=closed, pm=current | failed: exitFailure at 240 s | yes |
| closure=closed, pm=works | passed | yes |
| closure=none, pm=current | error: `knob_profile` (`illumination.sun_elevation` read back 0.3491 against 1.0472) | no: a false error run, issue 171 |

- The none-case drove as predicted: no barrier in the run (no copy), the stale route through
  6583 from 29.85 s, the goal at 101.1 s, no contact. Its error was the knob's single
  read-back, taken before CARLA ticked, which showed Town01's boot sun (issue 171; fixed on main
  47b59256).
- Both closed runs' copies have sha256 5fd2feb1... (as offline, in both projects); the
  barriers' truth positions equal CS3's within 0.001 m (x 305.641; y -128.206, -129.506,
  -130.806), placed on lanelet 6583 at s 20.
- **Found: the passed run had lost its copy.** The works/closed run, kept at `full`, had no
  `scenario.xosc`, though `resolved.yaml` named it: no keep level listed it. It is now kept at
  `result` (08a772d0).
- **Reported and withdrawn the same day: "CARLA shows the barriers at yaw 0" (issue 173, not a
  defect).** I read the raw `sim_pose` yaw, -0.0004, against SSv2's -1.5712. That is CARLA's
  body pose: the CARLA world server spawns the street barrier turned 90 degrees to fit its
  declared box (its entity row's `origin_offset` yaw is pi/2), and every reader of the truth
  takes the offset back off (`scensim.truth.boxes`, the gap oracle). With it taken off the
  barriers stand at yaw -1.5712 on CARLA, as on Isaac (offset 0).

**Predicted for the rerun on issue 171 (main 47b59256 plus K9f-b; before any run).** The same
suite, CARLA and setup, the none-case first:

- closure=none, pm=current: exitSuccess as before, and now no error: `knobs` ok, the knob
  profile `illumination.sun_elevation` judged from its second send, every frame from it read
  back 1.0472 within 0.001105; its first read-back recorded, whatever it shows.
- closure=closed: as the first suite (exitFailure at 240 s with pm=current; exitSuccess with
  pm=works), the knob judged as above, the copies 5fd2feb1... again, and each run directory
  keeping its `scenario.xosc`.
- Isaac Sim 6.2, aib at main's pin bb2283f (after issue 167), the two closed cases on
  k9_cs3_isaac: K9e step 2b's results (pm=current exitFailure at 240 s, pm=works exitSuccess), the
  same copy sha256, the barriers' truth at CS3's positions and yaw -1.5712.

**The CARLA rerun on issue 171 (2026-11-25, 12:00-12:14, at f0acfc70: main 47b59256 plus
K9f-b, built from a clean environment): as predicted.** My CARLA on RPC 2100 (Epic, booted on
Town01); the none-case alone on a fresh stack first, then `suites/layout.yaml` on one stack in
its order, which puts the none-case where the first suite's false error run was:

| case | verdict | knob profile `illumination.sun_elevation` |
|---|---|---|
| closure=none, pm=current (alone) | passed | sent 2, judged 2014 frames from the repeat, none off |
| closure=closed, pm=current | failed: exitFailure at 240 s | sent 2, judged 5014, none off |
| closure=closed, pm=works | passed | sent 2, judged 2636, none off |
| closure=none, pm=current (third on the stack) | passed | sent 2, judged 2005, none off |

- No contact in any run. The none-cases had no copy and no barrier; both closed runs' copies
  have sha256 5fd2feb1... and each run directory kept its `scenario.xosc` (08a772d0). The
  barriers' truth: x 305.641, y -128.206, -129.506, -130.806, yaw -1.5712 (the body's offset
  taken off; issue 173).
- Every first read-back showed the value sent (1.0472): the stale reply of the first suite
  did not recur, so this rerun shows the fixed judgement running live (two sends, judged from
  the repeat, no false error), and issue 171's tests show it judging a stale reply.

**The Isaac closed cases (2026-11-25, 16:42-16:54, the same build: f0acfc70, aib bb2283f,
scensim_isaac_world a8f6248): as predicted.** k9_cs3_isaac, `cs3_layout.xosc`, closure=closed,
pm=current then pm=works on one stack, Isaac Sim 6.2:

| case | verdict | knob profile `illumination.sun_elevation` |
|---|---|---|
| closure=closed, pm=current | failed: exitFailure at 240 s | read back 1.0472, ok |
| closure=closed, pm=works | passed | read back 1.0472, ok |

- No contact in either run. Both copies have sha256 5fd2feb1..., the CARLA copies' digest, and
  each run directory kept its `scenario.xosc`. `knobs.works.layout` names west_street_closed
  and its three props on lanelet 6583 at s 20.
- The barriers' truth, read through `scensim.truth` (offset yaw 0 on Isaac): x 305.641,
  305.641, 305.640; y -128.206, -129.506, -130.806; yaw -1.5712, as on CARLA.
- The wait for the card (133, 2026-11-25): the run waited for 22528 MiB free from 10:36, a
  guess (Isaac about 16 GB). K9e's Isaac runs had measured 7.6 GB at peak (scensim_isaac_world
  7103 MiB, pointcloud_container 526 MiB), so 133 lowered it to 12288 MiB held 2 minutes, with
  a stop guard on the run's own process group (card-wide free under 1024 MiB twice, 5 s apart).
  Measured this time, card-wide every 5 s: 15970 MiB used before the run (others' jobs), 23606
  at peak, so 7636 MiB ours; free never fell below 8505 MiB, and the guard did not fire.

## K9f-a: zone-scoped surface knobs (plan, 2026-11-25, 243; for 133, before any code or run)

As K9f's plan (above, approved with its conditions), with what reading main 0291abb3 decides.
What is already there: the protocol (scensim_world_protocol f2d9103: `ROAD_ZONES = 13` needs
`ROAD_CONDITION_APPLIED = 14`; `RoadConditionReply {friction_scale_factor, wetness, zones}`,
`ZoneApplied {surface_class, wetness, water_depth, mu}`, `mu` the class's mu times the wetness
factor times the condition's scale), the Python world-server shell's reply
(`World.applied_road_condition`), and K9f-b's run copy. What is not: the Isaac world server
declares neither capability; the bridge reads no `RoadConditionReply`; nothing records one.

**Four parts, each with tests that need no simulator:**

1. **Isaac world server** (scensim_isaac_world, pinned in lockstep). `IsaacWorld` declares
   `ROAD_CONDITION_APPLIED` and `ROAD_ZONES` and implements `applied_road_condition(zone_ids)`
   from its surface layer after `set_condition`: the world-wide scale and wetness, and for each
   named zone its class, wetness, water depth and mu as the layer now holds them (the table's
   mu at rest; hydroplaning's speed factor is not in it, as the field says). Isaac reads back
   what it just set, with no tick between, so issue 171's lag does not arise there.
2. **The bridge** reads the reply when the server offers `ROAD_CONDITION_APPLIED`, logs it, and
   writes it to the gap trace as a new record, `road_condition`: `frame`, `sent` (scale,
   wetness, the `scensim.*` properties) and `applied` (the reply). The record is additive in
   scensim_core's `gap_trace` (scensim_world_protocol, lockstep); readers that do not know it
   skip it (a test). CARLA 0.9.16 (C7) sends the world-wide part; scensim records it and, as
   for the `weather:` knob (issue 171), does not judge it until issue 161 reads back after the
   tick.
3. **scensim.** A static knob value may carry `zones: {<zone id>: {class?, wetness?,
   water_depth?}}`; wetness is OpenSCENARIO's level (dry, moist, wetWithPuddles, lowFlooded,
   highFlooded; K9f's example "wet" is not one and is refused by name). The run writes the
   fields as `scensim.zone.<id>.<field>` properties into the run's copy: into the Init's
   RoadCondition when the source has one (`isaac_soil`'s scenarios do), else
   into a new Init `EnvironmentAction` whose Environment holds only that RoadCondition (the
   form `isaac_soil/town01_zones.xosc` runs today). One copy writer for layouts and zones,
   byte-identical for the same inputs (a test); `resolved.yaml`'s `scenario.copy` lists the
   zones. Refused by name, in `testbench check` and the run (one function, issue 154): a zone id
   the scenario's surface map lacks (its `scensim.surface_map`, else the map's own
   `surfaces.yaml`); a class not in the table; a `class` on a soil zone; a field the source
   already sets for that zone (two writers); a zone value on CARLA, naming C7's measured limit;
   a zone knob on SSv2's own distribution. **The judgement:** after the run, each zone the knob
   set is read from the trace's `road_condition` record: class and wetness equal, water depth
   and mu within 1e-6 of the sent value and the class table; `result.json`
   `knobs.<knob>.zones`. A mismatch, or no record from a server that declares `ROAD_ZONES`, is
   a `knob_mismatch` error run.
4. **Docs**: scenario-description.md (the `zones:` form), projects-and-pilots.md (the copy holds
   zones too), results-and-logs.md (`knobs.<knob>.zones`, the trace record), truth-stream.md.

**The exit, and a correction to K9f's.** K9f's plan predicted the ego's stopping distance
across a wet zone "as the class table's wet factor predicts". Under Autoware that cannot show:
a planned stop decelerates comfortably (on the order of 1 m/s^2, not measured here), far
under the grip of wet asphalt (1.12 x 0.75 x 9.81 = 8.2 m/s^2), so the distance is the
planner's either way. A
friction can only show where the stop asks for more than the surface gives. So the exit asks
133 to choose (my lean: b):

- (a) **the read-back alone** on Isaac (applied zone equal to the knob's, mu equal to the
  table), plus CARLA's refusal by name; no physical number.
- (b) **a stop that asks more than the surface gives.** `isaac_soil`'s `town01_route` map's
  `ice_at_goal` zone (x 105..135) under a knob `goal_surface: {values: {asphalt: {zones:
  {ice_at_goal: {class: asphalt}}}, ice: null}}`, and a pedestrian darting into the lane in the
  zone when the ego is 20 m short (town01_mud_stop's pattern), so Autoware brakes hard.
  Predicted, from truth velocities over the braking: on asphalt the peak deceleration is
  Autoware's own (whatever it is, measured, not predicted); on ice (mu 0.265, dry) the peak is
  capped at 0.265 x 9.81 = 2.6 m/s^2, within 25 % (C7's band), and lower than asphalt's; the
  read-back as in (a) in both runs.
- (c) a fixed-brake test outside scensim run (aib's vehicle check); not a knob test, so no.

CARLA 0.9.16: the same scenario and knob refused by `testbench check` and the run, before any
run, naming the measured limit.

**133's choice (2026-11-25): (b), with a precondition; the predictions, before any run.**

- **The measure.** The ego's longitudinal deceleration from the truth (its `sim_pose` speed
  along its heading, read through `scensim.truth`), averaged over 0.25 s (5 frames at 0.05 s),
  from the pedestrian's dart-in trigger until the ego stops or touches it; the *peak* is the
  largest of those averages. Also recorded: the ego's speed at the trigger, where it stops (or
  touches), and whether it touches the pedestrian (the run's contact report).
- **Asphalt first, and the precondition.** The `asphalt` case runs first. Autoware's own limits
  (its planner's and its MRM's deceleration) may cap even a hard stop near 2.5 m/s^2; then
  asphalt and ice would read the same and say nothing about the zone. **The ice comparison
  counts only if asphalt's peak is at least 1.5 x 2.6 = 3.9 m/s^2.** If it is not, that is
  recorded as a finding about Autoware's limits, the exit falls back to (a), and 133 is told;
  the ice run is then still run for its read-back, and its deceleration is recorded, not judged.
- **Predicted, if the precondition holds:** ice's peak 2.6 m/s^2 within 25 % (1.95 to
  3.25 m/s^2), and below asphalt's. Speed at the trigger about the lane's limit, 11.2 m/s:
  stopping from it on ice takes at least 11.2^2 / (2 x 2.6) = 24 m, more than the 20 m the dart
  leaves, so **the ego is expected to touch the pedestrian on ice.** That contact is an expected
  outcome of the zone, not a failure of the knob test: the knob test is the read-back and the
  deceleration, and the scenario's verdict is recorded beside them. On asphalt, a peak of
  3.9 m/s^2 or more stops it within 11.2^2 / (2 x 3.9) = 16 m plus its reaction: no contact
  predicted.
- **The read-back, in both runs and whatever the precondition gives:** `knobs.goal_surface.zones`
  names `ice_at_goal` with class `asphalt` (mu 1.12) or `ice` (mu 0.265), wetness dry, within
  1e-6 of the class table; a mismatch is an error run.
- **The scenario** (`k9f_zones`, a new Isaac testbench on Town01 with `isaac_soil`'s
  `town01_route` map, written when K9f-a's code starts): town01_route's drive, the pedestrian
  entering the ego's lane inside `ice_at_goal` when the ego is 20 m short; the numbers above are
  checked against its first version before it runs, and amended here if it differs.

**Not in K9f-a:** a zone's geometry from anchors (K9c's regions name zones, never redraw them);
zones on CARLA (CARLA 1.0, after 083 step 5); hydroplaning in the read-back's mu.

**Amendment (2026-11-25, 243, at 133's ruling on issue 161's plan; before any K9f-a code or
run).** The order is now: K9f-b lands, then issue 161, then K9f-a's code. Issue 161 adds
`CAPABILITY_READBACK_AFTER_STEP` (15) and `StepReply.road_condition_applied`, the read-back
taken after the simulator's tick, which the bridge marks `after_step: true`. Part 2 changes
with it: the `road_condition` record's `applied` is the step's read-back on a server declaring
the bit, marked `after_step`, and the reply's otherwise; Isaac declares the bit, so K9f-a's
read-back check above is judged from the after-step value. scensim judges a marked record
whatever the simulator; an unmarked one (a server without the bit) is recorded, not judged, as
part 2 says for CARLA. No prediction above changes.

**Amendment (2026-11-25, 243, at 133's ruling; before part 2's code).** Part 2's premise was
false: a reader that does not know the `road_condition` record does not skip it. The trace
reader's record types are a closed set per schema, by design (`scensim_launch`'s
`gap_trace.py`: `signal` and `knob` only from schema 2; an unknown type is a `TraceError`, an
unknown schema too, naming the schemas it reads). So the record comes with **schema 4**: the
writer (scensim_core's `gap_trace`, `SCHEMA = 4`) writes 4 for every trace, `road_condition` is
known from schema 4 on, and a reader from before refuses a new trace by its schema number, at
its first line, as for schemas 2 and 3. Part 2's tests, instead of "readers that do not know it
skip it": a reader of schemas 1 to 3 refuses a schema 4 trace by its number; the new reader
reads 1 to 4; a `road_condition` record in a schema 3 trace is refused as unknown. The writer
is in scensim_world_protocol, so part 2 is another protocol commit, with the deps pins of
scensim_carla_world and scensim_isaac_world moved to it (part 1 lands in that cascade), then
scensim's pins, as for issue 161. No prediction changes.

**The parts' state, and the exit testbench's first version against the plan (2026-11-25, 243,
before any exit run).** Parts 1 to 4 are committed on branch `092-k9f-a-2` (scensim_isaac_world
`76ba145`, scensim_world_protocol `0488577`, scensim `79cf18de`, `eccb2902`, `032fa1c4`), not
landed. Their tests need no simulator. **The fake stack does not run a zone knob end to end:**
`scensim run`'s fake-stack harness (`test_run.py`'s `start_stack`, the knob tests' `knob_stack`)
builds CARLA testbenches only, and zones are refused on CARLA. The run's zone judgement is
therefore tested as `run.judge_zones` against a schema 4 truth in a run directory, and the
end-to-end check of a zone knob is the exit runs below. A fake Isaac stack for the harness is a
follow-up, with no issue number. In the full scensim suite run against an older install
(scensim main 8ad9f151, whose gap trace reader reads schemas 1 to 3), 3 of the zone tests fail on
"unsupported schema 4": expected, since they read the truth through the installed reader; they
pass against the branch's own reader, which a build of the branch installs.

The exit testbench is `scenarios/projects/k9f_zones` (Isaac, Town01, the Autoware ego), checked
against the plan above before it runs:

- **The map.** `ground/town01_route.yaml`, isaac_soil's `town01_route` copied with its zones
  unchanged, so the testbench owns the map its knob is judged against. `ice_at_goal` is x 105
  to 135, y -134 to -126.
- **The drive and the dart.** `goal_stop.xosc` is `town01_zones`' drive (from x 190.8, y -130.1,
  heading west, at up to 50 km/h) with `town01_mud_stop`'s pedestrian pattern, moved onto the
  zone: the pedestrian is added on the right of the lane at x 112, y -126.5; it darts 3.2 m to
  y -129.7 at 1.5 m/s when the ego reaches x 132 (2 m tolerance), 20 m short; it holds 4 s and
  crosses to y -136.7. The goal is x 104 (3 m), the timeout 240 s, a contact with the pedestrian
  exitFailure. The trigger at x 132 is 3 m inside the zone, so the whole stop, from the trigger
  to the pedestrian, is on it.
- **Amended: the ice value sets the zone.** The plan's knob had `ice: null` (the map's own ice).
  Then the ice run sets no zone, and nothing is judged from its read-back, which the plan wants
  in both runs. So `ice` is `{zones: {ice_at_goal: {class: ice}}}`, the map's own class set
  explicitly; the default is `ice`.
- **Amended: the speed at the trigger.** The plan took the lane's limit, 11.2 m/s. The ego starts
  58.8 m short of the trigger from rest, and Autoware's start, on the order of 1 m/s^2 (not
  measured here), gives about 10.8 m/s there. Stopping on ice from 10.8 m/s takes at least
  10.8^2 / (2 x 2.6) = 22 m, still more than the 20 m the dart leaves: **contact on ice is still
  predicted**, and the precondition and the deceleration bands are unchanged. The speed at the
  trigger is measured and recorded in both runs.
- **The order.** The suite `both` runs asphalt first, then ice, one run each, on a clean build of
  the branch's stack, after issue 161's live check on CARLA (done, 2026-11-25 20:45-20:57), never
  beside a CARLA of mine, with the card checked first.

**The exit's run 1 (2026-11-26, 03:54:52-03:58:59, 243).** From wt-k9fa2's clean build of
72a629ea (scensim_world_protocol `0488577` and scensim_isaac_world `76ba145` checked out, their
superproject pins e63aaea7 and 3a948eea not yet moved; scensim run's "off its pins" warning
names those two), Isaac Sim 6.2 on this host, the suite `both` on one stack. Logs:
`/var/tmp/aeon/k9fa-logs/k9f_zones/`, the script's in `/var/tmp/aeon/k9fa-exit/run4-*`.

- **Asphalt** (`2026-11-26T03-55-52_goal_stop_goal_surface-asphalt_r0`): passed, no contact, no
  error, `knobs` ok.
  - **The read-back held.** `knobs.goal_surface.zones.ice_at_goal`: sent `{class: asphalt}`;
    expected and read surface_class asphalt, wetness dry, water depth none, mu 1.12; from the
    truth's first `road_condition` record read back after a step, frame 2; ok.
  - **The speed at the trigger FAILED: 4.17 m/s, against about 10.8 predicted.** The ego
    cruised at a flat 4.17 m/s (15 km/h) from x 174 to the trigger (x 133.3, frame 555),
    braked from 4.17 to 1.0 m/s over 1.6 s (about 2 m/s^2) and stopped at x 121.3, 9.3 m short
    of the pedestrian. **Cause:** k9f_zones' pilot passed no `max_velocity`, so autoware_launch's
    `common.param.yaml` `max_vel`, 4.17 m/s, capped every planner (autoware_sim_profile's
    `planning_common_param` raises it only from that argument); demo, gap_campaign and
    isaac_demo pass `max_velocity: 11.11`.
  - **The precondition, both readings.** By the letter of the measure (the largest 0.25 s
    average from the trigger to the stop) the peak is **4.06 m/s^2**, over the 3.9 required. By
    its intent it is **not shown**: that peak is the last five frames, 1.0 m/s to rest (frames
    624 to 629), the stop's creep, not braking the surface limits; at 4.17 m/s even ice (about
    2.6 m/s^2) stops in about 3.3 m. So run 1 shows nothing about the zone's friction.
- **Ice** (`2026-11-26T03-58-07_goal_stop_goal_surface-ice_r0`): **void, not a result.** No
  `result.json`, a partial truth only. As its stack started, teacup1117's jobs took the card:
  pid 538122 (`deepsight243/venv/bin/python`, started 03:38:41), pid 631002
  (`envs/unidrivevla/bin/python`, started 03:52:36) and pid 670767 (`CARLA_0.9.15`
  CarlaUE4-Linux-Shipping, started 03:56:08, after this run began), all user teacup1117 by `ps`.
  The card fell to 34 MiB free at 03:58:33 and 237 MiB at 03:58:38, and the guard stopped this
  run's own process group and its stack (exit 99, no retry). Nothing of mine was left; the card's
  peak was 32076 MiB card-wide, this run's share about 6 GB (the world server 5520 MiB, the
  container 526 MiB).

**Amendment (2026-11-26, 243, with 133's OK; before any rerun).** (i) k9f_zones' pilot passes
`args: {max_velocity: 11.11}`, as demo does. (ii) Both cases are run again, asphalt then ice, on
the same build, with the same floor (12288 MiB held 120 s) and guard, after issue 184's gate.
(iii) Run 1 stands as recorded above. The predictions stand as amended before run 1 (about
10.8 m/s at the trigger; asphalt's peak at least 3.9 m/s^2 by intent, a braking phase, not the
stop's last frames; ice's peak 2.6 m/s^2 within 25 %; contact on ice), with one line added:
**the speed at the trigger is now predicted with `max_velocity` 11.11**, so a rerun that cruises
at 4.17 m/s shows the argument did not take, and is not judged.

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

**(3) D3's section 4 out of draft** (scenario-description.md, docs only): as K10 and K12 built
it; the first draft's car-follower and aggressive driver named as not built (a vehicle model,
parked with the user, 133, 2026-11-24), and the engine-in-the-loop agreement as not covered.

**(4) K10 closed** in this row and in 093 (D3 done; its list's K10 done).

## K11's plan: the search, purpose B (2026-11-24, 241; approved by 133 with five changes, in here, before any code)

K11 is 093 D4's last open part: an adaptive search that moves draws toward failures and writes
the sample record's reserved `search` (`{id, generation}`, sample-record.md section 1).
survey-risk-categories.md section 4 names three candidates (Bayesian optimisation,
cross-entropy, a bandit over cells) and one requirement that decides between them: **B's
failure regions sharpen A's proposal**, and each failure keeps its likelihood under the base, so
a realistic failure ranks above a contrived one.

### The method: the cross-entropy method, with likelihood-ratio weights

Chosen from three sources:

- **Corso, Moss, Koren, Lee, Kochenderfer, "A Survey of Algorithms for Black-Box Safety
  Validation of Cyber-Physical Systems", JAIR 72, 2021, pp. 377-428**
  (https://doi.org/10.1613/jair.1.12716; already F63 in survey-multi-vehicle-cooperation.md).
  It sorts black-box validation into falsification (optimisation), most-likely failure
  (planning) and failure probability estimation (importance sampling), and places the
  cross-entropy method in both the first and the last: the iterations that find failures leave
  a proposal for estimating their probability. That is A and B fed by one loop.
- **de Boer, Kroese, Mannor, Rubinstein, "A Tutorial on the Cross-Entropy Method", Annals of
  Operations Research 134, 2005, pp. 19-67** (https://doi.org/10.1007/s10479-005-5724-z), for
  the algorithm: per generation, draw N from the current density, take the elite (the most
  critical fraction rho by the score), set the level gamma_t to the elite's least critical
  score (never past the failure threshold), and refit the density to the elite with each sample
  weighted by base / current density, the likelihood ratio that makes the last density a
  proposal for the rare event under the base, not just a point near it; smooth the update by
  alpha.
- **O'Kelly, Sinha, Namkoong, Duchi, Tedrake, "Scalable End-to-End Autonomous Vehicle Testing
  via Rare-event Simulation", NeurIPS 2018** (https://arxiv.org/abs/1811.00145; [29] in the same
  survey), which ran this on an autonomous vehicle stack in simulation: adaptive importance
  sampling by cross-entropy, with a continuous score (not pass or fail) so the levels can move
  before any failure is seen.

Against the other two candidates: Bayesian optimisation proposes one point at a time from a
surrogate, fine for seats but a poor fit for the batch's thousands of slots a step, and its
result is a point, not a density A can use. A bandit over cells chooses which cell to spend
runs on but says nothing inside a cell; it is the natural layer above this one (as in 077's gap
campaign, gap-campaign.md) and is left for after K11.

### What it is, in scensim's terms

- **One search is one (scenario, base, cell).** The cell's attributes are fixed for the search
  (a catalogue's cell, or `scensim.cell.<attribute>`), so its rate and its failures are a
  cell's, as K7 reports them. Several cells: several searches.
- **The searched variables** are the base model's drawn variables named by the search, each
  replaced as a proposal replaces it today (`proposal: 1`, the importance plug-in): a `normal`
  or `lognormal` refitted to the weighted elite, keeping the base's `range`; a `uniform` refitted
  as a normal within its range; a `categorical` refitted to the elite's weighted frequencies
  with a floor of 0.01 on every category. Derived values, constraints, latent variables and the
  rest of the base are drawn as the base draws them. A `poisson`, `histogram` or `constant`
  variable, a latent one, or one in a joint group is not searched in K11 (refused by name).
- **Each generation is a proposal file.** Generation t's density is written as
  `search/<id>/g<t>.yaml` in the existing `proposal: 1` format. Its records are drawn by the
  importance plug-in, so they carry `proposal` (that file, by hash), `weight` and `log_weight`
  as any proposal's do, plus `search: {id, generation}`. K7's report and K3's replay read them
  as they read any record.
- **The score and the failure threshold.** The score is the ego's closest approach to any
  entity, box to box, in metres, as `python3 -m scensim.truth closest` gives it on seats (K4):
  lower is more critical, 0 is touching. **A run fails when its score is at most 0** (contact),
  the threshold every K11 search uses. The score enters as a new optional field of the outcome
  K7 reads, `score`, so the search does not care who ran the samples: a JSONL of `{record,
  outcome: {failed, contact, error, score}}`, the format another simulator's runs already use.
  A run with an error or no score is left out of the elite and counted.
- **The loop is stepped from outside**, so the same search runs on seats, on the batch, or on
  another simulator: `scensim-sample search init <spec>` writes g0 (the base, or a given
  proposal) and its draws; `scensim-sample search next <dir> --outcomes <jsonl>` reads the
  generation's outcomes, refits, writes g(t+1) and its draws, and a `state.json` (levels,
  elite sizes, failures so far, the search's seed). Once the stop rule holds, `next` writes the
  estimation stage instead (below). `scensim-sample search report <dir>` gives the estimate and
  lists the failures found, each with its record id, score and log base density, highest first.
  Deterministic: the same spec, seed and outcomes give the same files, byte for byte.

### Support and normalised weights

The estimate below is the plain likelihood-ratio estimator, so the weights must be exact density
ratios, not ratios up to a constant as the importance plug-in's are today (its docstring: fine
for the self-normalised estimate, biased for a plain mean).

- **Every g_t covers the base's support.** A refitted normal or lognormal keeps the base's
  range, and so its support; a categorical keeps every category at 0.01 or more; and each
  generation is drawn from the defensive mixture (next item), which contains the base itself.
- **Defensive mixture.** Each generation, and the estimation stage, draws from
  q_t = (1 - beta) g_t + beta base, beta = 0.1 (Hesterberg, "Weighted Average Importance
  Sampling and Defensive Mixture Distributions", Technometrics 37(2), 1995, pp. 185-194). Every
  weight base / q_t is then at most 1/beta = 10, and a g_t narrower than the base (the case
  sample-record.md section 8 measured at 0.61 coverage) cannot make the weights' variance
  infinite. The importance plug-in gains `defensive: beta` in a proposal file.
- **Truncation renormalised.** A variable with a `range` has density f(x) / (F(hi) - F(lo)) in
  both base and g_t, computed in closed form for normal and lognormal, so the ratio is exact.
- **Constraints.** A base with constraints (CS1's has three) draws from base(x) 1_C(x) / Z_b,
  and the mixture from q(x) 1_C(x) / Z_q, so the weight is (base / q) (Z_q / Z_b). Constraints
  need no simulation, so both acceptance probabilities are estimated by drawing: Z_b from 10^5
  draws of the base, Z_q from 10^5 draws of the generation's mixture, each with its binomial
  error, which is added to the estimate's relative standard error in quadrature and reported.
  The rejection count the sampler already records is kept as well. With constraints the weight bound
  of the mixture becomes 10 Z_q / Z_b, not 10; the report gives the largest weight of every
  generation and of the fresh stage.
- **The test of it** (part of check 1): for an event that always holds, the weights' mean is an
  unbiased estimate of 1; at N = 10^4 draws, per variable kind (truncated normal, truncated
  lognormal, normal refit of a uniform, categorical with the floor), with constraints and with
  none, and through the mixture, |mean(w) - 1| is within 3 standard errors in every case.

### Parameters, fixed before any run

- elite fraction rho = 0.1;
- smoothing alpha = 0.7 on every refitted parameter (mean, sd, category probabilities):
  theta_t = alpha theta_fit + (1 - alpha) theta_(t-1);
- defensive fraction beta = 0.1;
- N per generation: 1000 for check 1; for K11c, the batch's slot count, written into its spec and
  into this document before its first run; the estimation stage draws the same N;
- the stop rule: stop when the level reaches the threshold (gamma_t at most 0, so at least
  rho N of the generation's runs fail) or after 20 generations, whichever is first; the report
  says which.

From the tutorial's ranges (rho 0.01 to 0.1, alpha 0.4 to 0.9), at the safe end for a small N.

### The estimate: a fresh stage, the plain estimator

The generations choose each density from their own samples, so a rate estimated from those
samples carries adaptive bias. The rate is therefore estimated from a **fresh stage**: after the
stop rule holds, N new draws from the last mixture q_T, used for nothing else. With w_i the
normalised weight and f_i 1 for a failure:

- p_hat = (1/N) sum w_i f_i, the plain likelihood-ratio estimator;
- its standard error s / sqrt(N), s the sample standard deviation of w_i f_i (with the
  constraints' relative error added as above);
- a normal 95 % interval, p_hat plus or minus 1.96 standard errors;
- Kish's effective count n_eff = (sum w)^2 / sum w^2, reported beside it.
- (Issue 183, after K13 step v.) With no failure that interval is [0, 0], which is no answer:
  the interval is then an exact one-sided 95 % upper bound through the mixture's weight cap,
  also reported at every failure count as `upper_exact`; the normal one is marked approximate.

The generations' own estimate is reported next to it, marked as a diagnostic, never as the rate.
K7's report gets the same plain estimator for a search's fresh stage, with `interval_method`
naming it; its self-normalised estimate stays for every other weighted cell.

### Steps

1. **K11a, the search, pure Python** (`scensim_sampler`, no simulator): the spec, `init`,
   `next`, the fresh stage, `report`; the importance plug-in's `defensive:` and normalised
   weights; the outcome's `score`; sample-record.md section 9's line replaced by the search's
   section; scenario-description.md section 5's row as built.
2. **K11b, the batch's score**: the closest gap per slot, box to box, as the truth judge measures
   it, so a batch generation yields the outcome JSONL directly.
3. **K11c, CS1's search**: walker dart-out, one cell, on the batch; then its failures replayed on
   seats through K3's replay.

### Exit checks, with predictions (fixed before any run)

1. **A known rare event** (K11a, a test; no simulator): base N(0, I) in two dimensions, failure
   x1 + x2 > 5.2 (as a score, 5.2 - (x1 + x2) at most 0), so p = Phi(-5.2 / sqrt 2) = 1.18e-4.
   Prediction, at N = 1000 and the parameters above: the level reaches the threshold within 4
   generations in 20 of 20 seeds; the fresh stage's 95 % interval contains p in at least 18 of
   20 seeds, with n_eff / N above 0.1 in every seed; every weight is at most 10 (no constraints here), and the largest is reported. Plain sampling
   with the same total budget (4 generations and the fresh stage, at most 5000) expects 0.59 failures and finds none in most seeds.
   With it, the unit-mean weight test of "Support and normalised weights".
2. **Determinism** (test): two runs of the same spec, seed and outcomes give identical files.
3. **The records** (test): every drawn record passes `scensim-sample check`, carries `search`,
   `proposal` and `weight`, and K7's coverage report reads a search's outcomes.
4. **K11b**: the batch's closest gap within 0.05 m of the seats judge's on K10's agreement
   records (run 2's set), reported per record.
5. **K11c**: on CS1, the search's stop rule and the fresh stage's estimate with its interval,
   its relative standard error SE / p_hat (the efficiency measure, as the interval uses it) and
   n_eff are reported; the relative standard error **with no bar**, since no rate or score
   distribution is known for CS1 on the batch to set one from, and every failure it found is replayed on seats through K3's replay. The
   count that fail on seats too is reported **with no bar**: the batch's ego is a model (engine A
   or B), the seats ego is the stack, so how many transfer is what the check measures, not
   something to predict. Each failure that does not fail on seats is listed with its cause
   (its seats score and what differed), as a finding.

### Not in K11

Failure-mode clustering (by parameters and by the autopilot's behaviour, survey-risk-categories.md
section 4) and the bandit over cells: each its own item after K11, once runs exist to cluster.
Latent variables, joint groups, and the other variable kinds as searched variables.

### K11a's result (2026-11-24): checks 1 to 3, check 1's fourth part failed

`scensim_sampler.search`, `scensim-sample search init|next|report`, the importance plug-in's
`defensive:`, the record's `search` as `{id, generation, stage, normaliser}` (stage
`cross_entropy` or `fresh`; the normaliser is Z_q / Z_b, 1 without constraints), the outcome's
`score`, and K7's plain estimator for a search's fresh stage. Tests: `test/test_search.py`.

**Check 1**, seeds 1 to 20, N = 1000, p = 1.18e-4:

| Prediction | Result |
|---|---|
| the level reaches the threshold within 4 generations, 20 of 20 | **met**: in every seed at g3, the fresh stage g4 |
| the fresh interval contains p in at least 18 of 20 | **met**: 20 of 20 |
| every weight at most 10 | **met**: the largest 10.000 in every run |
| n_eff / N above 0.1 in every seed | **failed**: 3 of 20 below (0.093, 0.097, 0.099); range 0.093 to 0.128 |

The fourth part's cause is the bar, not the search. Kish's count over all the mixture's weights
sits at about beta by construction: the beta share drawn from the base lands where g_T is about
0 and carries weights near 1/beta, so sum w is about N and sum w^2 about beta N / beta^2 = 10 N,
and n_eff / N is about beta = 0.1. The bar measured the mixture, not the search, and was set at
its expected value. n_eff stays in the report; it is no longer a bar in the test, and check 1 is
not rerun with a new one. The efficiency measure for later checks is the relative standard error
SE / p_hat, which is what the interval uses (K11c's prediction above).

**The adaptive bias, as change 1 expected.** The generations' own estimate, each generation's
plain estimate averaged, ranged from 5.6e-5 to 1.45e-4 over the 20 seeds, and was below the
truth in 19 of them; the fresh stage's ranged from 1.03e-4 to 1.52e-4 and contained the truth
in all 20. This is why the rate comes from the fresh stage only.

**Unit-mean weights**: at N = 10^4 with 10^5 acceptance draws, |mean(w) - 1| within 3 standard
errors for a truncated normal, a truncated log-normal and a categorical together, and for a
uniform searched as a normal, each with and without a constraint, through the mixture.
**Check 2**: two searches from the same spec, seed and outcomes write identical files.
**Check 3**: every record passes `scensim-sample check` and carries `search`, `proposal` and
`weight`; K7's rate for the fresh stage equals the search's estimate. Refused by name: a latent
variable, one in a joint group, one whose parameters read other values, a Poisson.

**What K11c needs first**, found by starting a search on the CS1 example
(`examples/walker_dartout`): its model draws its cell (`illumination`, `surface`), which a
search refuses ("a search is one cell, and generation 0 drew 4"), and its `ttc_entry` is
conditioned on the walker type and the light, which K11a refuses ("its lognormal reads other
values"). K11c's spec therefore fixes the cell (knobs or `scensim.cell.<attribute>`) and
searches the variables with constant parameters, or K11 grows conditional variables first; the
choice is made in K11c's spec, written here before its first run.

### K11c's spec (2026-11-24, 241; the base and the cell chosen by 133, before any run)

**The scenario.** The batch's CS1 is `examples/cases/cs1_walker_gap_acceptance.xosc`, not the
walker_dartout example: its parameters are `ego_speed`, `walk_speed`, `ttc_entry` and
`behaviour`, and it has no category, cell or distribution, which the sampler requires. K11c runs a sibling,
`examples/cases/cs1_walker_gap_acceptance_k11c.xosc`: the same scenario below its header, with
the category `R2.walker_crossing.dart_out` and a fixed cell (`scensim.cell.illumination` day,
`surface` dry, `occluder` van), so the search runs inside one cell by construction. It is a
sibling, not an edit (133), because landed records (K10's agreement, run 2) name the original's
hash. Its header says what it is. It passes `compilable` with the walker's batched model.

**The base: invented.** `examples/cases/models/cs1_gap_acceptance_k11c.yaml`, with constant
parameters, labelled invented in its file. **K11c's estimated rate is a rate under this
invented base, not a risk rate**: K11c demonstrates purpose B (finding failures) and the
search-to-rate mechanism, not purpose A.

**The simplification: independence.** The four variables are drawn independently. The model
the numbers come from, walker_dartout.yaml, draws `ego_speed` jointly with `van_offset` and
conditions `walk_speed`, `behaviour` and `ttc_entry` on `walker_type` (`ttc_entry` on
`illumination` too); here those conditions are fixed at the day / adult case. Where the numbers
come from:

| Variable | Base | From walker_dartout.yaml |
|---|---|---|
| `ego_speed` | normal 8.3, sd 1.265, range [1.0, 16.68] | no day / adult case (a joint group): the first mixture component's marginal (weight 0.7, mean 8.3, variance 1.6), truncated at its constraint `ego_speed <= 1.2 * speed_limit` (16.68 m/s); the lower bound 1 m/s is ours |
| `walk_speed` | normal 1.4, sd 0.2, range [0.6, 2.4] | `walk_speed`, case adult |
| `behaviour` | steady 0.75, hesitate 0.2, run 0.05 | `behaviour`, case adult |
| `ttc_entry` | log-normal 2.6, sd 0.8, range [0.3, 8.0] | `ttc_entry` at adult (2.6) and day (factor 1.0) |

**The search.** All four variables searched, none held; the base's id in each record is the
model's path as the spec writes it (not this host's), so record ids do not depend on the host; the threshold 0 (a closest gap at most
0 m); the parameters of "K11's plan"; N the batch's slot count, and the seed, written here
before the first run, with the batch's engine.

### K11c's spec, completed (2026-11-24, 241; 133's three decisions, before any run)

**The plan's "the batch's engine" is amended: the ego is a point mass on CPU.** The search
mechanism does not depend on the engine; CPU keeps P1's and P4's GPUs whole and makes a run
deterministic and cheap to repeat. The point mass (`scensim_batch.pointmass`, from the batch
tests' stand-in): a mass moving along its heading, its wheels at one radius, the requested
acceleration as rear-wheel torque. It is neither engine A nor B, and the results say so. A
repeat of the failures found on engine B is a later step, once GPU1 has measured headroom.

**The ego under test: `aeb_ttc`, invented.** It holds its initial speed (acceleration 0) until
the time to collision with the walker falls below **1.5 s**, then brakes at **6 m/s^2** to a
stop. The time to collision is the box-to-box gap along the ego's heading over its speed,
counted while the walker's box overlaps the ego's corridor (its width); the walker's own motion
is not predicted. Both numbers are invented, labelled so beside the base. A non-reacting ego
would be a weak subject: its failures are the walker's geometry alone (any walker that steps in
front of a car that never brakes), so the search would find the walker's path, not a boundary
of the ego's behaviour.

**The world: Town01, as K12's runs.** CS1's Town01 form,
`scenarios/projects/k12_commanded/scenarios/cs1_town01.xosc` (its entities on the anchor
`west_street`, the walker its behaviour model), gets a sibling there,
`cs1_town01_k11c.xosc`: the category and the fixed cell (illumination day, surface dry, occluder
van), nothing else changed, so a failure found is replayable on seats in the same project (K3).
The examples sibling (`cs1_walker_gap_acceptance_k11c.xosc`) names `maps/town_street`, which no
world provides: it is an example for the description, not runnable, and stays as one. The world: the map export of the
project's Town01 (`scensim.lock`, carla-town-autoware-maps 19d52699), the one K10's recheck used
(map_sha256 ee291b6e), and its `anchors.resolved.json` for the sampler: the search spec's new
`map:` key (the map whose resolved anchors the scenario binds, checked against its digest).
Fetched with `scensim assets fetch` into the project; `scensim assets check --hash` passed
against `scensim.lock` (anchors.resolved.json 428462cc, lanelet2_map.osm a85836f5), and the
export's map_sha256 is the fetched map's.

**The runner: `scensim_batch/scripts/search_run.py`, interim.** One generation a call: a
generation's records, compiled, run in one BatchRun of N slots (the point mass, `aeb_ttc`) to
each slot's end or a cap of 400 steps (20 s), the truth exported, and `scensim.truth outcomes`
written. When K2's `scensim bench` lands, the runner calls into it or is retired (its docstring
says so).

**N and the seed.** N = 1000 a generation and in the fresh stage; the search's seed 11; the
other parameters "K11's plan"'s. The base's acceptance draws 10^5.

**Predictions, fixed before the run.** No number for the rate: the base and the ego are
invented. Reported: the stop rule and the generation it stopped at; each generation's level,
elite and failures; the fresh stage's estimate with its interval, relative standard error
SE / p_hat (no bar) and n_eff; the largest weight (at most 10 Z_q / Z_b). Then each distinct
failure of the fresh stage is replayed on seats (K3, the k12_commanded stack, CARLA) and the
count that fail there too is reported with no bar: the seats ego is the project's pilot
(`carla_basic`), not `aeb_ttc`.

### K11b's check 4 (2026-11-24): passed as worded, exposed issue 130

`python3 -m scensim.truth outcomes` (each batch slot's closest gap, by the same `closest()` the
seats judge runs) on the batch's truth export (`agreement_run.py --ego-from-truth
--truth-out`), against `python3 -m scensim.truth closest` on the seats runs, K10's run-2 set:

| Run | Seats | Batch | Difference |
|---|---|---|---|
| L seed 2 | 0.443 m (frame 141) | 0.488 m (step 123) | +0.045 m |
| L seed 31 | -1.231 m (frame 131) | -1.262 m (step 116) | -0.031 m |

Within 0.05 m, so it passed as worded. Per frame it did not: the minima fall at different
frames (seats 141 is step 127), and the gaps differed by up to 1.15 m, because the playback put
the ego's body pose where the entity's belongs, 1.387 m ahead (issue 130). Fixed in both the
playback and the seats attachment (133's decision: models read the entity's pose).

**The rerun's bar, fixed before it.** The recorded seats walker decided against the ego's body
pose (it ran before the fix), and the batch's walker now reads the entity's, 1.387 m behind: the
two walkers may decide at other frames, so their poses may part. Hence, on both runs, at every
paired frame (seats S + k, batch k):

- the ego's box centres within 1e-3 m (the playback alone; the bar);
- the walker's pose error and decisions against seats, reported with no bar;
- the closest gaps within 1e-3 m at every frame where the walker's pose error is under 1e-3 m
  (the bar), and the minimum on each side reported with its frame.

A check 4 free of the old walker decisions needs seats runs recorded with the fixed attachment
(CARLA): K10's open recheck, below.

**The rerun** (the fix in the playback and the seats attachment; the same set 3 records):

| Run | Ego box, max over frames | Walker pose error, max | Frames with walker under 1e-3 m | Gap difference there, max | Decisions (step, event), seats / batch |
|---|---|---|---|---|---|
| L seed 2 (218 frames) | 0 m | 0.210 m | 81 | 1.18e-4 m | 61 appear, 82 reject, 121 go_after / 64, 85, 124 |
| L seed 31 (179 frames) | 0 m | 0.210 m | 62 | 1.15e-4 m | 61 appear, 82 go / 64, 85 |

Both bars met: the played-back ego's box is the seats box at every frame, and where the walkers
agree the gaps agree to 1.2e-4 m. As expected, the walkers part: every batch decision comes 3
steps (0.15 s) after the recorded one, the ego's entity being 1.387 m behind its body at about
8 m/s. Minima: L seed 2 seats 0.443 m and batch 0.488 m, both at step 126; L seed 31 seats
-1.231 m at step 117, batch -1.262 m at step 119; each differs because the walkers do. Outcomes
agree (passed on both). The decisions' agreement now waits on seats runs recorded with the
fixed attachment (the follow-up above).

### K10's open recheck (issue 130; required, 133)

K10's "decisions agree" rests on code both sides have changed since its runs: since issue 130 a
behaviour model reads the ego's entity pose and velocity on both seats and the batch. After 130
lands: two new seats runs, L seeds 2 and 31 of `k12_commanded`, with the fixed attachment (243,
the CARLA stack), then `agreement_run.py --ego-from-truth` on them. Its prediction is written
here before those runs: the decisions at the same frames on both sides. K11b's check 4 is
repeated on the same runs, per frame.

**The recheck's result (2026-11-24): the prediction met.** Runs: 243's
`~/nas/home/2026-11-24 092 K10 open recheck runs (243)/` (SHA256SUMS sha256 63c0c423...;
`sha256sum -c` passed on the local copy), scensim dcce0cdb, one fresh `k12_commanded` L stack,
CARLA 0.9.16 Epic. `agreement_run.py --ego-from-truth` from dcce0cdb:

| Run | Decisions (step, event), seats = batch | Walker max / RMS xy | Van | Element offsets | Outcome |
|---|---|---|---|---|---|
| L seed 2 (S 25, 221 steps) | 64 appear, 85 reject, 124 go_after | 1.49e-4 / 1.28e-4 m | 2.0e-5 m | all 0 | passed / passed |
| L seed 31 (S 14, 182 steps) | 64 appear, 85 go | 1.50e-4 / 1.29e-4 m | 2.0e-5 m | all 0 | passed / passed |

Decisions at the same frames on both sides, as predicted; the walker as close as runs 1 and 2.
K11b's check 4 per frame on the same runs: the ego's box equal at every frame (0 m), the
closest gaps within 1.47e-4 m at every frame (bar 1e-3 m), and the minimum at the same step on
both sides (L seed 2: 0.4883 m at 126, difference 2.1e-5 m; L seed 31: -1.2620 m at 119,
1.3e-5 m). K10's open recheck is closed.

Two callers 130 missed, found here (issue 130, "Effect on landed results"): the agreement
table's ego row compared the batch's entity pose with the seats body pose and so read 1.387 m
(the ego is played back; its row is 0 with the fix), and 243 found `k12_walker_replay.py` (K12's
check 2) still fed its model the body pose (every event 3 frames early, 0.21 m), fixed by 243
in scensim 79775334.

### K11c's run: the restart and the two-commit span (2026-11-24, 241)

**The restart.** g0 at N = 1000 took 3649 s: `scensim_batch.truth`'s writer computed the
ego's overlap over all N slots for every slot and frame (N^2). Fixed in 7f436b99 (each row's
overlap once). g0 rerun with it on a copy: `outcomes.jsonl` and all 1000 truth files
byte-identical, in 857 s. g1 had finished on the old code; g2 was stopped mid-run at 08:46 (its
partial output kept as `runs/g2.stopped-0846`) and the search resumed from g2 (drawn,
deterministic) at 08:56 on 7f436b99, settings unchanged.

**The two-commit span.** K11d's walker change (2c7a6df9, an optional `draw`) was committed in
the worktree K11c runs from while it ran, so generations from g3 import 2c7a6df9's walker; g0
to g2 ran on 7f436b99 or before. Without `draw` the walker makes the same calls on the same
values. Proof (133): 50 of g0's records rerun from a pinned detached worktree at 2c7a6df9:
`outcomes.jsonl` identical byte for byte, and every slot's `truth.jsonl` and `sample.json`
identical; each `outcome.json` differs only in its `scenario` path, the checkout's directory
(`scensim-k11c-pin` for `scensim-k11c`), and is identical with that replaced. The run's results
therefore do not depend on which of the two commits ran a generation. From now on a run executes
from a pinned copy nobody edits while it runs (`search_run.py`'s notes).

### K11c, an observation during the run (2026-11-24, 241; offline, the run untouched): the score's plateau

The scores of g0 and g1 (1000 each), histogrammed from the runs' `outcomes.jsonl`:

| Closest gap (m) | g0 | g1 |
|---|---|---|
| (-2, -1] | 9 | 9 |
| (-1, -0.5] | 5 | 5 |
| (-0.5, 0] | 3 | 1 |
| (0, 0.2] | 0 | 0 |
| (0.2, 0.4] | 5 | 6 |
| (0.4, 0.44] | 170 | 187 |
| (0.44, 0.5] | 496 | 525 |
| (0.5, 0.6] | 283 | 238 |
| (0.6, 2] | 29 | 29 |

The scores are bimodal. A walker that goes in front of the car makes contact (gap at most 0:
17 and 15). One that waits at the kerb as the car passes sits on a plateau, 0.40 to 0.60 m,
95 % of the draws, its gap set by the kerb's offset, not by how near a failure it came. No draw
falls in (0, 0.2]. So the elite (the lowest 100) is the failures plus about 80 plateau draws,
and the plateau's are not nearer a failure than the rest: the level moves only with the
plateau's own spread (0.430, then 0.427 m), and cross-entropy has no slope to climb.

Nor do the searched variables separate the two: the failures' means (g0: ego 8.5 m/s, walk
1.54 m/s, ttc_entry 2.63 s; g1: 8.0, 1.49, 2.69) are close to the plateau's (8.3, 1.39, 2.55;
7.9, 1.39, 2.56). Which branch a draw takes is mostly the walker model's own decision (its
gap-acceptance draw, from the record's pilot seed), which the search does not move.

**A score-design finding, not a bug**: the closest gap is flat on the waiting branch. If the
run ends at the cap, this is the likely reason. The fix belongs to the next search's spec,
written before its run: a score with a slope on the waiting branch (the time margin the walker
leaves, say, or the gap acceptance's own margin, U against its threshold), or the decision's
noise as a searched variable.

### K11d's spec: the walker's decision draw as a searched variable (2026-11-24, 241; for 133's review, before any code or run)

K11c's observation: the failure lives in the walker model's own gap-acceptance draw (its
uniform u, from the record's pilot seed: it accepts when U > logit(u)), which the search
cannot move. K11d makes that draw a declared, searched variable, and changes nothing else, so
any difference from K11c is that variable's.

**The variable.** `accept_u`, the walker's uniform draw for the episode, declared in the base
as `uniform: {low: 0, high: 1}`: the same law as the seed's `random.Random(seed).random()`, so
the base, and the rate it defines, are K11c's. It must reach the model, so it is a scenario
parameter bound to a new optional walker property `draw` (u in (0, 1); without it the walker
draws from its seed as now), not a K8 `latent` (a latent never reaches the scenario). It is
recorded, weighted and replayed like the other four: a seats replay of a record (K3) then makes
the same decision, where today it depends on the pilot seed reaching the runner.

**What changes.**

- `gap_acceptance_walker` gains the optional `draw` (ours, params_schema marks it). Test: with
  `draw` the threshold is logit(draw) on seats and in the batch alike; without it, as today.
- A sibling `cs1_town01_k11d.xosc`: K11c's with `accept_u` declared and bound (`draw =
  $accept_u`).
- A base `cs1_gap_acceptance_k11d.yaml`: K11c's four variables and `accept_u`, independent,
  invented as K11c's is.
- The spec `searches/k11d.yaml`: five variables searched (`accept_u` as a normal within
  [0, 1], as K11a refits a uniform); the score still the closest gap, threshold 0; N 1000; the
  seed 11; the plan's parameters. A sloped score (U against its threshold) is not used: it would
  change two things at once. It is the next lever if K11d's elite still stalls.

**One draw per episode, deciding the branch (133's question).** The walker draws once per
episode, at reset: `random.Random(seed).random()` is its only random call, and its logit is the
threshold. It decides once (UNDECIDED, at the kerb): it goes if U > threshold, else it waits,
and a waiting walker crosses once the ego has passed the conflict point, with no second draw
(a `hesitate` walker's re-check compares the ego's time with `abort_gap`, deterministic). So
`draw` replaces the only draw, and with the record's other values it decides go or wait;
nothing random about the walker stays unsearched. The binding `draw = $accept_u` sits in the
walker's controller properties, an entity property, not the FileHeader, so issue 131's rule
(on FileHeader bindings) does not apply.

**Host-independent paths (133, from K11c's proof).** K11c's records (`scenario.path`) and its
runs' `outcome.json` (`scenario`) carry the checkout's absolute path; the path is not part of a
record's identity, so K11c's ids are unaffected, but the files name the host. From K11d on, a
search writes `scenario.path` as the spec writes it, and `search_run.py` names that in
`outcome.json` (tests in `test_search.py` and `test_pointmass.py`). K11c's files keep the
absolute form.

**Predictions, fixed before the run.**

1. The level reaches 0 (the stop rule, not the cap) within 6 generations.
2. The elite's mean `accept_u` falls from g0 to the generation that stops (reported per
   generation).
3. The fresh stage's 95 % interval overlaps K11c's g0 Monte Carlo interval (g0 draws from the
   base itself: 17 failures in 1000, Wilson 95 % [0.011, 0.027]) and K11c's fresh-stage
   interval: all three estimate the one rate, under the one base.
4. Its relative standard error is below K11c's fresh stage's.

If 1 fails, the elite is still filled by the plateau (the sloped score is then the next spec);
if 3 fails, the weights or the variable's law are wrong, and K11d's rate is not used.

### K11d's run: started in parallel with K11c (2026-11-24, 241; 133's go)

Started 11:40:43 from a pinned detached worktree at a0d6c257 (`scensim-k11d-pin`: 2c7a6df9 plus
the notes and the spec-relative scenario path; nobody edits it while the run lasts), under
`nice -n 10`, while K11c ran on (g9). One generation is a single process of about one core; the
host's load was 74 to 79 on 24 CPUs, so 133 judged one more niced process to cost the others
about 1 %, well inside P4's 20 % rule. Both searches are deterministic, so running them together
changes no result, only wall time. P4's iteration time before the start (the mean of each
seed's last 20 iterations, 11:39): seed 3 118.7 s, seed 4 117.5 s, seed 5 113.3 s; an hour
later (12:41): 89.5, 98.5 and 97.5 s, the host's other load having moved too (load 87.6): no
slowdown, inside the 20 % rule.

### K11d, an observation during the run (2026-11-24, 241; 133): a uniform's start puts less mass where failures live

K11d's g0 does not draw `accept_u` from its base, by design: K11a searches a uniform as a normal
within its range, centred at the middle (here normal(0.5, sd 1/sqrt 12) on [0, 1], drawn from
the defensive mixture). Its other four variables are the base's, so g0's weights are
`accept_u`'s factor alone: their largest is 1 / (0.9 x 0.336 + 0.1) = 2.483 at u = 0 or 1
(measured 2.459), and they average 1 (by quadrature exactly; g0's 1000: 1.0109, SE 0.0128;
2 x 10^6 draws: 0.99999, SE 0.00028). The weights are right.

But the start is the wrong way round for a search. Failures live at small u (the walker accepts
when u < P, and P is small at CS1's gaps), and the centred normal puts less mass there than the
base: below u = 0.02, 0.0084 under g0's mixture against 0.02 under the uniform; below 0.05,
0.0226 against 0.05; below 0.1, 0.0505 against 0.1. So K11d's g0 found fewer failures (8) than
K11c's (17), which drew from the base. A candidate cause, beside the flat score, if prediction 1
fails. For a variable whose base is uniform, the next spec starts g0 at the base itself: the
uniform kept for g0 and refitted to a truncated normal from g1, or a beta family, which holds
the uniform exactly (beta(1, 1)).

**K11d's prediction 1: failed** (2026-11-24 13:38). The level did not reach 0 within 6
generations: g0 to g5 0.431, 0.429, 0.423, 0.423, 0.425, 0.423 (failures 8, 10, 9, and 9 to 13
after). The run goes on to its cap; predictions 2 to 4 are judged on its fresh stage.

### K11c's result (2026-11-24, 241; the run ended 15:18)

**Stop: the generation cap (20).** The level never reached 0: it stayed between 0.416 and 0.430
m from g0 to g19 (the plateau of "an observation during the run": the walker waits at the
kerb), so the cross-entropy found no way down. Each generation's level and failures (elite 100
throughout):

| g | level (m) | failures | g | level (m) | failures |
|---|---|---|---|---|---|
| 0 | 0.4301 | 17 | 10 | 0.4222 | 15 |
| 1 | 0.4272 | 15 | 11 | 0.4178 | 13 |
| 2 | 0.4213 | 25 | 12 | 0.4160 | 25 |
| 3 | 0.4232 | 22 | 13 | 0.4216 | 15 |
| 4 | 0.4248 | 11 | 14 | 0.4199 | 14 |
| 5 | 0.4203 | 27 | 15 | 0.4191 | 23 |
| 6 | 0.4263 | 11 | 16 | 0.4188 | 21 |
| 7 | 0.4190 | 10 | 17 | 0.4187 | 22 |
| 8 | 0.4190 | 17 | 18 | 0.4200 | 17 |
| 9 | 0.4239 | 14 | 19 | 0.4216 | 23 |

**The fresh stage (g20, N 1000, from g19's proposal).** 14 failures, 14 distinct records,
no errors. The estimate under the invented base: **p = 0.0179**, SE 0.0054, normal 95 %
interval **[0.0074, 0.0285]**, relative SE 0.30; n_eff 473.8; the largest weight 9.78, inside
its bound of 10 Z_q / Z_b (the normaliser 1: no constraint rejects a draw). The adaptive
generations' own estimate, 0.0172, is a diagnostic only. The interval holds g0's plain rate
(17 in 1000, Wilson [0.0106, 0.0271]): twenty generations of search bought no precision over
plain sampling, which is what the plateau predicts. 371 failures were found over the whole
run; every one is a contact, and none is reached by moving the searched variables, since the
walker's gap-acceptance draw decides (K11d and K11e are the answers to that).

**Data.** `~/nas/autoveh/logs/092-k11c/`: the search's records and proposals (`search/`),
each generation's `outcomes.jsonl` and `run.json` (`runs/`), `report.json`, the run's log and
script, with `SHA256SUMS` (88 files). The truth exports (4.8 GB) stay on 241 in
`/var/tmp/aeon/k11c-run/runs/*/truth/`. The fresh stage's 14 distinct failures go to the seats
replay (K3, 243), reported with no bar.

### K11c, K11d and K11e: the hashes the runs executed, and their main equivalents (2026-11-24, 241)

The searches ran from pinned trees on the branch `k11c-notes`, which landed on main by rebase,
so the hashes cited above for what ran are not on main. The branch is kept on origin as an
archive, `k11c-notes` at a56aef83, unchanged, so every cited hash stays reachable; K11d's and
K11e's results will cite the same trees. The runs executed the old commit; the trees match in
the touched files (every file the branch changed up to that commit is byte-identical in its main
equivalent, except this document, which differs only by main's own sections).

| Ran (k11c-notes) | Main equivalent | What |
|---|---|---|
| 2c7a6df9 | 2c0c79c3 | the walker's draw as a parameter; K11c's and K11d's pinned tree |
| 7be7775b | 90f598eb | the sloped score; K11e's pinned tree |
| 7f436b99 | ff87aaf4 | the truth export's overlap once per row (K11c's N^2) |
| a0d6c257 | 190a172b | the scenario named as the spec writes it |

### K11e's spec: a score sloped on the waiting branch, and g0 at the base (2026-11-24, 241; for 133's review, before any code or run)

K11e addresses both causes named for K11c's and K11d's flat levels, and changes nothing else
from K11d (the same scenario, base, five searched variables, ego, runner, N 1000, seed 11).

**1. The score, sloped on the waiting branch.** At its one decision the walker goes if
U > logit(u), the threshold. Its margin is m = logit(u) - U: negative when it went, positive when
it waited, and the smaller m, the nearer it came to going (to the failure branch). The score:

    score = gap                      if gap <= 0     (contact: a failure, unchanged)
    score = gap + k * max(m, 0)      otherwise

with the gap the closest gap, box to box (m), as before, and **k = 1 m per logit unit, invented**.
A failure is still exactly gap <= 0: the added term is never negative and is added only when
gap > 0. A walker that went and was avoided (m < 0, gap > 0) scores its gap; a walker that
waited scores its plateau gap (0.40 to 0.60 m) plus its margin, so the plateau is ranked by how
near it came to going, and every waiting walker ranks above every avoided one. k makes one logit
unit outweigh the plateau's whole spread (0.2 m). The runner writes the margin it read
(the batch walker's `record()`: `threshold_logit` and the decision's `u`) and both parts of the
score in each outcome (`closest_gap`, `decision_margin`), so the score is recomputable.

**The score is a function of the saved files alone (133).** `search_run.py --margin-k`
writes, beside each slot's truth and record, `decision.json` (the walker model's own record of
its decision: `threshold_logit` and the decision's U). `scensim.truth.sloped_score(slot)`
recomputes the score from those files: the gap from the truth, the threshold from the record
(logit of `accept_u`, else of the record's pilot seed's draw), checked against the model's, and
U from the decision. A test recomputes every score of a run from its saved directory and
compares (`test_pointmass.py`).

**Went and avoided (133).** A walker that went (m < 0) but that `aeb_ttc` stopped in time
(gap > 0) scores its own gap, with no margin term: below every waiting walker. Those draws are
the near-failures the elite should climb through, and they are expected in the elite from g1
on. The search counts them per generation, and those in its elite (`went_avoided`,
`elite_went_avoided` in its state and report). A waiting walker near its threshold can outrank one, though (it
scores its plateau gap, about 0.45 m, while a went-and-avoided walker scores its own gap, 0.73
m in the smoke): so the count in the elite may be small. The prediction stands as written (133).

**2. g0 at the base for a uniform variable.** K11a turns a uniform into a centred truncated
normal from g0, which put less mass where failures live (K11d's observation). From K11e a
uniform variable stays uniform in g0, so g0 draws every variable from its base (weights all 1),
and is refitted to a truncated normal within its range from g1 on, as before.

**Predictions, fixed before the run.**

1. g0 is the base: every g0 weight is 1, and g0's failures fall within 9 to 27 (K11c's g0 rate,
   17 in 1000, the same base: its 95 % range for a new 1000).
2. The level reaches 0 (the stop rule) within 10 generations.
3. The elite's mean `accept_u` falls below 0.25 by g3 (K11d's stayed at 0.44 to 0.47).
4. The fresh stage's 95 % interval overlaps K11c's g0 interval (Wilson [0.0106, 0.0271]) and
   K11c's and K11d's fresh-stage intervals: one rate, one base.
5. Its relative standard error is below K11c's and K11d's fresh stages'.

If 2 fails with 3 met, the score is ranked but the cross-entropy still cannot reach the failure
branch in 10 generations (rho or N, then). If 3 fails, the margin does not reach the elite (a
fault to find before any reading). If 4 fails, the rate is not used.

### K11e's run: started in parallel with K11c and K11d (2026-11-24, 241; 133's go)

Started 14:04:11 from a pinned detached worktree at 7be7775b (`scensim-k11e-pin`; nobody edits
it while the run lasts), under `nice -n 10`, with `search_run.py --margin-k 1.0`, while K11c
(g16) and K11d (g7) ran on. P4's iteration time just before (the mean of each seed's last 20,
14:02): seed 3 88.9 s, seed 4 90.9 s, seed 5 91.0 s, the host's load 66 to 74 on 24 CPUs;
checked again an hour later against P4's 20 % rule.

The hour's check (15:04, the three searches running: K11c in its fresh stage after g19, K11d
at g11, K11e at g3): seed 3 88.3 s, seed 4 91.5 s, seed 5 89.7 s, against 88.9, 90.9 and
91.0 s before; the largest change is seed 4's +0.7 %, well inside the 20 % rule. The host's
load was 81 to 93.

### K11e's result (2026-11-24, 241; the run ended 17:39)

**Stop: the level reached the threshold, at g8.** Each generation's level, failures, the draws
that went and were avoided (`went_avoided`), those in the elite, and the elite's mean
`accept_u` (the 100 lowest scores; computed from the saved records and outcomes):

| g | level (m) | failures | went and avoided | in the elite | elite mean `accept_u` |
|---|---|---|---|---|---|
| 0 | 1.1025 | 11 | 65 | 33 | 0.189 |
| 1 | 0.7174 | 11 | 188 | 58 | 0.174 |
| 2 | 0.7265 | 19 | 146 | 46 | 0.157 |
| 3 | 0.5205 | 33 | 228 | 61 | 0.084 |
| 4 | 0.5205 | 61 | 255 | 27 | 0.064 |
| 5 | 0.5205 | 29 | 97 | 35 | 0.138 |
| 6 | 0.5205 | 49 | 158 | 38 | 0.087 |
| 7 | 0.5205 | 76 | 167 | 18 | 0.050 |
| 8 | 0 | 101 | 185 | 0 | 0.029 |

The elite was 100 a generation, 101 at g7 and g8 (ties at the level). From g3 to g7 the level
held at 0.5205 m, one went-and-avoided gap shared by the tie, while the failures in each
generation rose from 33 to 76; at g8 more than rho N of the draws failed and the level was 0.

**The fresh stage (g9, N 1000, from g8's proposal).** 225 failures, 225 distinct records, no
errors; 184 went and were avoided. The estimate under the invented base: **p = 0.0148**, SE
0.0011, normal 95 % interval **[0.0126, 0.0171]**, relative SE 0.077; n_eff 115.2; the largest
weight 10.0, at its bound (10 Z_q / Z_b, the normaliser 1: the defensive mixture's floor, beta
0.1). The adaptive generations' own estimate, 0.0155, is a diagnostic only. 615 failures were
found over the whole run.

**The predictions.**

1. **Met.** Every g0 weight is 1 (1000 of 1000, within 1e-15), and g0 had 11 failures, inside
   9 to 27.
2. **Met.** The level reached 0 at g8.
3. **Met.** The elite's mean `accept_u` was 0.084 at g3 (0.189 already at g0, where K11d's was
   0.467).
4. **Met.** The interval [0.0126, 0.0171] overlaps K11c's g0 interval (Wilson [0.0106,
   0.0271]), its fresh stage's ([0.0074, 0.0285]) and K11d's ([0.0117, 0.0297], judged when
   K11d ended at 19:33).
5. **Met.** The relative SE, 0.077, is below K11c's fresh stage's, 0.30, and K11d's, 0.22.

The went-and-avoided draws were in the elite from g0 on (33), as expected from g1, and left it
at g8, when failures filled it. A reading, not a prediction: with the same N, the sloped score
gave an interval about a fifth of K11c's width, but on n_eff 115 of 1000, with the largest
weight at its bound; the proposal sits far from the base on `accept_u`, and the defensive
mixture is what holds the weights.

**Data.** `~/nas/autoveh/logs/092-k11e/`: the search's records and proposals (`search/`), each
generation's `outcomes.jsonl` and `run.json` (`runs/`), `report.json`, the run's log and script,
the fresh stage's 225 failing record ids (`fresh_failures.txt`), with `SHA256SUMS` (45 files).
The truth exports, with each slot's `decision.json` from which the sloped score is recomputed,
stay on 241 in `/var/tmp/aeon/k11e-run/runs/*/truth/`. The run executed 7be7775b (main 90f598eb).

**A check after the results (133): do a few heavy samples carry p?** If a few failures at or near
the weight bound carried most of the estimate, the proposal would under-cover a failure region
and the SE would be optimistic; 133's rule, set before the check: over 30 % of p from failures
weighing more than 5 means one replicate fresh stage (N 1000, a new seed, from g8's proposal),
both estimates reported and their disagreement taken as the SE. Measured from the fresh stage's
records and outcomes: **no failure weighs more than 5** (none over 1; the largest 0.527, 3.6 % of
p; the five largest together 10.5 %; the median 0.057), and the failures' own n_eff is 143.8 of
225. The 82 draws over 5, 71 of them at the bound, are all non-failures: draws in the base's bulk
(the walker waits) that the proposal reaches rarely. They lower the whole sample's n_eff to 115
but add nothing to p. So no replicate was run; the SE of 0.0011 stands as the estimate's.

### K11d's result (2026-11-24, 241; the run ended 19:33)

**Stop: the generation cap (20).** As K11c, the level stayed on the plateau, 0.416 to 0.431 m
from g0 to g19 (prediction 1 failed at g5, recorded above). Each generation's level, failures
and the elite's mean `accept_u` (the 100 lowest scores; from the saved records and outcomes):

| g | level (m) | failures | `accept_u` | g | level (m) | failures | `accept_u` |
|---|---|---|---|---|---|---|---|
| 0 | 0.4314 | 8 | 0.467 | 10 | 0.4216 | 21 | 0.298 |
| 1 | 0.4287 | 10 | 0.441 | 11 | 0.4239 | 28 | 0.310 |
| 2 | 0.4228 | 9 | 0.459 | 12 | 0.4194 | 24 | 0.381 |
| 3 | 0.4209 | 19 | 0.375 | 13 | 0.4241 | 14 | 0.371 |
| 4 | 0.4252 | 15 | 0.320 | 14 | 0.4192 | 15 | 0.367 |
| 5 | 0.4234 | 13 | 0.361 | 15 | 0.4188 | 20 | 0.305 |
| 6 | 0.4246 | 7 | 0.393 | 16 | 0.4161 | 20 | 0.318 |
| 7 | 0.4187 | 14 | 0.401 | 17 | 0.4181 | 21 | 0.272 |
| 8 | 0.4234 | 24 | 0.302 | 18 | 0.4204 | 19 | 0.318 |
| 9 | 0.4220 | 23 | 0.321 | 19 | 0.4213 | 26 | 0.277 |

**The fresh stage (g20, N 1000, from g19's proposal).** 26 failures, 26 distinct records, no
errors. The estimate under the invented base: **p = 0.0207**, SE 0.0046, normal 95 % interval
**[0.0117, 0.0297]**, relative SE 0.22; n_eff 405.1; the largest weight 9.86, inside its bound of
10. The adaptive generations' own estimate, 0.0179, is a diagnostic only. The check 133 set for
K11e, made here too after the results: no failure weighs more than 5 (the largest 1.73; 30 draws
over 5, all non-failures).

**The predictions.**

1. **Failed** (at g5, as recorded): the plateau filled the elite; the sloped score (K11e) was
   the next spec, and reached 0 at g8.
2. **Met, not monotonically.** The elite's mean `accept_u` fell from 0.467 at g0 to 0.277 at
   g19, the last generation, through 0.272 to 0.401 from g3 on: the elite leant towards small u
   without a score to climb.
3. **Met.** [0.0117, 0.0297] overlaps K11c's g0 interval (Wilson [0.011, 0.027]) and its fresh
   stage's ([0.0074, 0.0285]).
4. **Met.** The relative SE, 0.22, is below K11c's fresh stage's, 0.30.

**The three rates.** K11c 0.0179 [0.0074, 0.0285], K11d 0.0207 [0.0117, 0.0297], K11e 0.0148
[0.0126, 0.0171], and K11c's g0 by plain sampling 0.017 (Wilson [0.0106, 0.0271]): every
interval overlaps every other, one rate under one base (K11e's narrow interval holds neither
K11c's nor K11d's point estimate, which their wider intervals allow). The relative SEs, 0.30, 0.22 and 0.077 at
the same N, rank the three searches; only K11e's score reached the failure branch.

A reading, not a result (133): K11e and K11d differ by z = 1.25 (0.0059 over a combined SE of
0.0047), not significant. And an importance-sampling estimate can miss a failure region its
proposal never reaches, which the weight check cannot see: K11e's narrow interval is
conditional on its proposal covering every failure region.

**Data.** `~/nas/autoveh/logs/092-k11d/`, as K11c's and K11e's, with `fresh_failures.txt` (26
ids) and `SHA256SUMS` (89 files). The truth exports stay on 241 in
`/var/tmp/aeon/k11d-run/runs/*/truth/`. The run executed a0d6c257 (main 190a172b).

## K13's plan: the vehicle behaviour model (2026-11-25, 241; approved by 133 the same day, before any code)

The design is [vehicle-behaviour-model.md](../design/vehicle-behaviour-model.md): the
Intelligent Driver Model (Treiber, Hennecke and Helbing 2000) as a car-follower holding a lane
anchor, its coefficients Zhang and Sun's (2024) pooled MA-IDM for cars on highD
(CC BY 4.0), its action K12's `speed heading accel_limit` with no field added, the deceleration
capped at the catalog's `maxDeceleration`. It leaves out lane changes (MOBIL), human error and
aggression beyond its parameters (the Human Driver Model), and a published driver spread.

**Steps.** (i) The model and its set, numpy and torch, bit for bit (no stack). (ii) K12's
vehicle side: the fork's `SimulatorDrivenVehicleEntity::drives()` takes `model`, `scensim run`
stops refusing a commanded vehicle, the CARLA world server moves a commanded vehicle as it moves
the walker; Isaac stays refused by name. (iii) The batch places a model vehicle as it places the
walker. (iv) Seats against the batch on one scenario. (v) The platoon scenario and a K11 search.

**Exit.** Each check states its bound before its run:
1. (i) The model alone: the equilibrium gap within 1e-9 relative, free-road approach to v0
   with no overshoot, the stop behind a standing car, numpy and torch on the CPU in float64
   with 0 differing arrays; torch on a GPU expected bit for bit (sim_vehicle_ecu.xp fuses
   nothing), not yet run on a GPU.
2. (ii) On CARLA 0.9.16, lockstep: lag 1 at every frame, no gate miss; the vehicle's lateral
   offset from the lane's centreline, p95 and max, under a bound set from (i)'s chord error.
3. (iv) Seats against the batch on the same record: events at the same frames, the follower's
   position within a bound fixed before the run, K10's way.
4. (v) The search runs end to end in the batch and reports its estimate and interval; its
   prediction is written before the run, from a numpy dry run of the platoon.

**First numbers, for the prediction's shape** (a hand calculation in Python with the set's
values, not the model's code; redone with `zhang2024_highd_car` once the PDF was checked): on
Town01's 30 km/h (v0 8.33 m/s), a follower at its equilibrium gap behind a lead at 7 m/s
(15.2 m) that then brakes to rest at 2, 4, 6 or 8 m/s^2 peaks at about 2.2 m/s^2 of braking in
every case, never reaches a cap, and stops about 1.7 m behind it, inside s0 (2.8 m), even
at 2 m/s^2. A platoon at Town01's speeds is therefore
benign; the first search wants a faster lane anchor.

**Answered (133, 2026-11-25).**
1. The driver spread: invented bases, labelled so as K11c's, bracketing the set's means; a
   published spread is future work.
2. The Isaac agreement is after K13 (K12 D3's follow-up, its own item); K13's agreement is
   CARLA's seats against the batch.
3. The first search's lane: an existing map with a lanelet export and a lane of 50 km/h or more
   (Town04 or Town05 first), a K9 anchor added there; Town01's limit is not raised; no new map
   without asking.
Also: bit for bit claimed on the CPU in float64, and only expected on a GPU until run there;
the cap breaks IDM's freedom from collisions, so `capped` events are counted; s0, T, a and b
are motorway-fitted, from 10 car followers.

**The map (2026-11-25).** Base Town05's own lanelet export has lanes at 50 km/h or more: its
tags give 88.5 km/h (387 road lanelets), 104.6 (40, the ring), 56.3 (11), and lanelet2 takes
50 for the 145 untagged ones. Straight chains at 88.5 km/h run 350 to 372 m (for one, lanelets
105401, 78805, 117337, 219, ...). So base Town05, not the 110 km/h ring variant (133). Its
`map_export` and a K9 anchor are made locally; publishing them as a new dataset revision is an
outward publish and waits for the user's approval through 133.

## K13's exit check 2: a model car on CARLA (rule fixed 2026-11-25, before any run)

Run before the landing (133): the components' commits are on their remotes' branch
`k13-model-vehicle` (the SSv2 fork 31b12c5fc, scensim_world_protocol ecb56e8,
scensim_carla_world 9af488a, scensim_isaac_world eb3d8e9), and the runs use a local build of
scensim's K13 branch that pins them.

**The scenario.** `scenarios/projects/k13_platoon/scenarios/platoon_town01.xosc`: 092's platoon
on Town01's lane anchor `west_street` (lanelet 6583, 224 m, 40 km/h; maps dataset v2026.11e).
The lead, a scripted default vehicle at 8 m/s from s 60, brakes to rest at `decel` from 8 s;
the follower, `idm_follower` at rest at s 30, follows it; the
ego, `carla_basic` at 8 m/s from s 5, follows the follower. Both cars are the catalog's
tesla_model3 (box 4.792 m, its centre 1.416 m ahead of the rear axle). The seats runner is a
lockstep attachment commanding `follower`. CARLA 0.9.16 at Low (one town), this host's seat,
on GPU 1. Suite `lockstep`: `decel` 2, 4 and 6 m/s^2, one run each (the model draws nothing).

**The follower's set is not the cited one: "zhang2024_highd_car with a = 1.5, ours".** The
paper's a is 0.362 m/s^2. At that rate a car from rest is at 2.9 m/s after 8 s, 11.6 m on,
while the lead is 64 m on: it would never catch up within the street's 224 m, and nothing of
the follow-and-stop this check exists for would happen. So a is raised to 1.5 m/s^2 (ours),
the rest is the set's (s0 2.833 m, T 1.133 s, b 2.140 m/s^2) and v0 is the lane's 11.17 m/s.
This check is of the command channel and the world's motion of a model vehicle; it says
nothing of the cited model's driving, and its numbers are not to be read as that model's.

**The predictions**, from the model and K12 D5's integrator on the same lane in numpy, the
lead's profile as the storyboard gives it, lag 1 (not the stack):

| decel | follower stops at s | its final gap, box to box | its peak braking | capped frames |
|---|---|---|---|---|
| 2 m/s^2 | 132.8 m | 2.65 m | 1.77 m/s^2 | 0 |
| 4 m/s^2 | 124.8 m | 2.65 m | 1.74 m/s^2 | 0 |
| 6 m/s^2 | 122.1 m | 2.65 m | 1.73 m/s^2 | 0 |

and its events `follow` then `stopped`, in that order, in every run.

**The checks**, each run:
1. Lag 1 at every frame after the follower's first command (`result.json` `commands`: lag p50,
   p95 and max 1), no gate miss, no command for an unknown entity.
2. The follower in its lane: its truth's lateral offset from west_street's centreline at most
   0.10 m at every frame (the commanded heading corrects toward the centreline; the street is
   straight).
3. The model's own outcome: no contact between the follower and the lead (the gap from the
   follower's truth positive at every frame), the follower at rest by the run's end, its final
   gap within 0.3 m of 2.65 m, no `capped` frame, the events `follow` and `stopped` in
   `decisions.jsonl`.
4. SSv2 adopts the world's pose: the follower's pose in SSv2's own log trails the world's by the
   two frames every world-owned entity does, as K12 stated for the walker.

**The verdict.** Exit check 2 holds when all three runs pass 1 to 4. A failure is named by run
and check. The ego is not judged: carla_basic's following of the model car is reported, as any
contact it makes, but it is not the subject.

**Changed after attempt 4's failure (2026-11-25), before attempt 6.** Attempts 1 to 3 never ran
a frame (the unfetched map assets, issue 159; a crash in the run-side attachment check on a
catalog entity's unknown kind; `-$decel`, which OpenSCENARIO 1.3 refuses). Attempt 4 ran all
three runs at lag 1 with no gate miss, but failed on substance, and two things changed for the
next attempt; the rule, the predictions and the checks above did not:
1. *The run ends on `exitSuccess` at 25 s.* SSv2 ends a run on a custom command, not on the
   storyboard's stop trigger, so attempt 4's runs ran to SSv2's time-out. The scenario's `end`
   event sends `exitSuccess` at simulation time 25 s.
2. *The world reports a commanded body's velocity (issue 160).* The CARLA world server's step
   states carried CARLA's measured 0 m/s for the follower, posed with physics off, so the model
   read its own speed as 0 and the follower crawled at 0.075 m/s. The states now carry the
   integrator's velocity (`scensim_carla_world` 078c1a1, on its branch
   `issue-160-commanded-velocity`, which replaces 9af488a in this check). The model reads the
   world's velocity, as designed. Attempt 5 ran a model that took its own last command as its
   speed instead; that fix was withdrawn (open loop, it hid the world's defect), so attempt 5
   does not count.

**Amended after attempt 5 (2026-11-25, 133), before attempt 6's results were read.**
1. *The stop positions are FAILED predictions, not judged.* Attempt 5 stopped the follower at s
   135.8, 130.2 and 129.5 m against the predicted 132.8, 124.8 and 122.1. The cause is the
   lead, not the model: SSv2's lead holds 8 m/s until about 9.05 s (s 126.0), not 8 s, and
   brakes more softly at first (at decel 6 it stops at s 136.9 against 129.3). That is SSv2's
   storyboard timing, which K2.4 also measures. The follower's stop relative to the lead (the
   final gap) held, and that is what the model is responsible for. The predictions are not
   recomputed for attempt 6.
2. *Check 4 is judged against the ego.* As written ("trails the world's by the two frames every
   world-owned entity does") it FAILED on its wording: in attempt 5's gap traces the follower's
   SSv2 pose (with the 1.387 m origin offset) equals the world's one frame earlier, exactly, and
   the ego's does too. K12's two frames came from another record. The intent was "like any
   world-owned entity", so check 4 now reads: the follower trails the world by the same number
   of frames as the ego in the same gap trace.

**Attempt 6's result (2026-11-25): exit check 2 holds.** k13dev f68d275c, scensim_carla_world
078c1a1; all three runs passed SSv2 (`exitSuccess` at 25 s). Evaluated by
`k13_check2_eval.py`; runs, logs and the script in `~/nas/autoveh/logs/k13-check2/` (attempt 5
beside them, for the record).

| decel | check 1: lag p50/p95/max, misses, unknown | check 2: lateral max | check 3: final gap, min gap, events, capped, contacts | check 4: trail, follower and ego | stop s (FAILED prediction) |
|---|---|---|---|---|---|
| 2 m/s^2 | 1/1/1, 0, 0 | 0.0001 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 135.8 m (132.8) |
| 4 m/s^2 | 1/1/1, 0, 0 | 0.0001 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 130.2 m (124.8) |
| 6 m/s^2 | 1/1/1, 0, 0 | 0.0001 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 129.5 m (122.1) |

The follower at rest at each run's end (0 m/s from its positions over the last frame). The peak
braking from positions was 1.85, 1.79 and 1.77 m/s^2 (predicted 1.77, 1.74 and 1.73); its
reported speed now equals the speed from its positions (peak 9.94, 9.91 and 9.93 m/s), where
attempt 4 reported 0. Lateral offset is measured from the line through the follower's and the
lead's spawn points, both on west_street's centreline (the street is straight). Check 4's error
at the matched trail is 0.0 m for both bodies, with the 1.387 m origin offset applied. The
contact monitor recorded no contact in any run, the ego's included.

**Landed** at scensim 73575ba9 (2026-11-25) with one gate test waived by 133:
`scensim_isaac_world`'s `test_course_c6c` golden hash, issue 162 (the hash is the host's, not
the heights': it fails the same at isaac main without K13). Gate log:
`~/nas/autoveh/logs/k13-gate/gate-53a15bf9.log`.

## K13's exit check 3: seats against the batch (rule fixed 2026-11-25, before any run)

K10's agreement, on the model car (step iv). `agreement_run.py --ego-from-truth` on each of
check 2's attempt 6 runs (decel 2, 4 and 6; `~/nas/autoveh/logs/k13-check2/attempt6/`), one
slot, read from their run directories, so no seats run is made again. The batch plays the seats
ego's truth back (no engine, no GPU), runs the lead as SSv2's default vehicle (K2.1) from the
storyboard, and the follower as a `model` entity compiled from its ObjectController, with K10's
pairing: seats frame S + k is batch step k, a model's command applied a step later (lockstep's
lag 1), model entities in SSv2's view two steps back. The map export is `scensim_batch.map_export`
of the project's Town01 (carla-town-autoware-maps 19d52699, map_sha256 ee291b6e..., 300
lanelets), from scensim 4893da50.

**What differs from K10's walker.** The follower reads another vehicle, not the ego: on seats
the lead's truth is CARLA's car tracking SSv2's pose (`npc_motion: tracked`), in the batch the
lead is SSv2's pose itself. Measured on the seats side before this rule (the truth alone, no
batch run): CARLA's lead within 0.0007 m (p50) and 0.0069 to 0.0136 m (p95) of SSv2's, at most
0.021 m, except three frames as it jumps from rest to 8 m/s (0.042, 0.275 and 0.551 m, frames
11 to 19). So the follower's inputs differ by that much, and its error is expected above the
walker's 1.5e-4 m.

**The rule.** Each run agrees when:
1. the outcomes are equal (passed on both: `exitSuccess` at 25 s, which the batch's storyboard
   takes);
2. the follower's decisions are the same sequence at the same frames (`follow`, `stopped`;
   seats: the attachment's `decisions.jsonl`, batch: the model's events);
3. every storyboard element's offsets are 0 (the lead's brake event among them);
4. the follower's max xy error is at most 0.10 m; the lead's (the batch's SSv2 vehicle against
   SSv2's pose in the truth) at most 0.05 m (K2.4's NPCs: 2.8 cm); the ego's is checked 0.

**The prediction.** All three agree: the follower's max xy error 0.005 to 0.03 m, at its start
or its stop; the lead's under 0.03 m; `stopped` at the same frame on both sides. A disagreement
is named by run, column and number, and its cause found before anything is rerun.

**Run 1 (2026-11-25): failed, on items 2 and 4; two defects, issues 163 and 164.** Outcomes
passed on both, the ego 0, every element offset 0, the lead within 6.0e-5 m; the follower 4.73,
7.49 and 5.20 m apart and its decisions unmatched. Issue 163: the seats runner stepped models
from the first truth frame, before SSv2's `startNpcLogic`, the batch from S, so the seats
follower ran 8 to 15 frames ahead. Issue 164: the batch recorder named the follower's events with
the walker's table. Rows: `~/nas/autoveh/logs/k13-check3/run1/`. The rule is unchanged (133):
the failures were defects. Tooling, not the subject: `agreement_run.py` passes the map's
resolved anchors to `BatchRun` (its `--map`, as the seats runner reads them), which a
car-follower's lane needs; without it the batch side could not start. Check 2 is rerun after 163
(133), then run 2.

**Check 2 rerun after issue 163 (2026-11-25): holds.** k13dev 7138959c (the seats runner holds a
model until NPC logic starts). A first rerun (d3c756f4) ended in three error runs on the run's
own command check, lag 1 throughout: the frames before S carried no command by design and the
check allowed one; 163 now counts them as `held_frames` (`~/nas/autoveh/logs/k13-check2/
rerun1-held-error/`). The second, on 7138959c, passed all three runs (`~/nas/autoveh/logs/
k13-check2/rerun2/`):

| decel | check 1: lag, misses, unknown; held / uncommanded | check 2: lateral max | check 3: final gap, min gap, events, capped, contacts | check 4: trail, follower and ego | stop s (FAILED prediction) |
|---|---|---|---|---|---|
| 2 m/s^2 | 1/1/1, 0, 0; 9 / 1 | 0.0001 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 135.8 m (132.8) |
| 4 m/s^2 | 1/1/1, 0, 0; 13 / 1 | 0.0001 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 130.2 m (124.8) |
| 6 m/s^2 | 1/1/1, 0, 0; 10 / 1 | 0.0002 m | 2.652 m, 2.652 m, follow then stopped, 0, none | 1 frame, 1 frame | 129.5 m (122.1) |

The follower's first decision is now at the first frame of NPC logic (truth frames 11, 15 and
12), where attempt 6's was at frame 2; its outcome is unchanged. Check 3's run 2 reads these
runs, not attempt 6's, whose seats runner stepped the follower before S (the code that lands is
this one).

**Run 2 (2026-11-25): failed, on items 2 and 4, by one step; issue 165.** On check 2's rerun
runs: outcomes passed on both, the ego 0, the lead 6.0e-5 m, every element offset 0, the event
names right (164); but the follower's decisions a step later in the batch (`follow` at 1 against
0, `stopped` 1 to 2 later) and its position 0.48 m apart. The batch never stepped a model on the
reset observation, so its entity first moved at step 2, a step after seats and SSv2's own NPCs;
shifted by one step the error is 0.046 m (`~/nas/autoveh/logs/k13-check3/run2/`). Issue 165:
`BatchRun.reset` has each model decide on the reset observation.

**K10's agreement after 163 and 165 (133: one case end to end).** The landed K10 record ran the
old seats runner and the old batch. One case again, both new: L seed 2 of K12's set
(`k12_commanded`, `cs1_town01.xosc`, CARLA 0.9.16 at the default Epic, carla_basic, lockstep), then
`agreement_run.py --ego-from-truth` on it, K10's rule unchanged. Predicted before the run: it
agrees as K10's run 2 did. The walker waits for its `start_gap` well past S, so neither fix moves
it: outcomes passed on both, the decisions the same sequence at the same steps on both sides
(appear, reject, go_after), every element offset 0, the walker's max xy error about 1.5e-4 m.

**Run 3 (2026-11-25): holds but for one threshold event, FAILED with its cause.** scensim
f924c3b4 (issues 163, 164 and 165), on check 2's rerun 2 records, the rule unchanged.

| run | outcome (seats / batch) | follower max / RMS xy | lead | ego | element offsets | decisions (step, event) |
|---|---|---|---|---|---|---|
| decel 2 (S 10) | passed / passed | 0.0288 / 0.0100 m | 6.0e-5 m | 0 | all 0 | 0 follow, 366 stopped on both |
| decel 4 (S 14) | passed / passed | 0.0278 / 0.0098 m | 6.0e-5 m | 0 | all 0 | 0 follow, 356 stopped on both |
| decel 6 (S 11) | passed / passed | 0.0277 / 0.0098 m | 6.0e-5 m | 0 | all 0 | 0 follow on both; stopped 354 seats, 355 batch: FAILED |

Items 1, 3 and 4 hold in all three runs: the follower within 0.029 m against the 0.10 m bar,
inside the prediction (0.005 to 0.03 m). Item 2 holds for decel 2 and 4 and fails for decel 6,
by one step on `stopped`. Its cause (133: recorded as FAILED, not re-judged): `stopped` fires when
the follower's speed drops below `STOP_SPEED` 0.05 m/s, and at step 355 the seats follower was at
0.04944 m/s and the batch's at 0.05047, 1 mm/s apart with their positions 0.2 mm apart. The 1 mm/s
comes from inputs that differ by design: the seats follower reads CARLA's car tracking SSv2's
lead, the batch reads SSv2's lead itself (within 0.021 m after the start, measured before the
rule). Rows and the decel 6 pose dump: `~/nas/autoveh/logs/k13-check3/run3/`.

**K13's exit (133; corrected 2026-11-25 (133): exit check 4 had been misread as step (ii)'s
check 4).** Exit checks 1 and 2 held (2 on its rerun after issue 163); check 3 held except one
threshold event, failed with its cause; check 4 (step v, the search) held ("The search's
result" below). The step (ii) runs'
own check 4 (the trail, amended wording) held.

**Amended for future agreement checks, set after K13 check 3 run 3 (133).** A threshold event
(a decision that fires when a model's state crosses a fixed value, such as the follower's
`stopped` at `STOP_SPEED`) may occur one step apart on the two sides when the model's state at
that step is within the bound its inputs' difference allows of the threshold. The rule states
that bound before the run, derived apart from the run it judges. For a car-follower reading
another vehicle, the inputs differ by the seats leader's tracking error, at most 0.021 m after
the start (measured before check 3's rule), and the bound is **0.0066 m/s** of speed. Its
derivation, a batch-only sensitivity run (no CARLA; `k13_threshold_sensitivity.py`): the
platoon of check 2's rerun 2 records in the batch, the lead's position as the follower reads it
moved along the lead's heading by +0.021 m, by -0.021 m, and by uniform noise in [-0.021, 0.021]
m per step (seed 1); the follower's largest speed difference from the unperturbed run while it
slows to rest (under 0.2 m/s, until both stop) was 0.94 to 0.98 mm/s for the constant offsets
and 2.72, 3.27 and 3.24 mm/s for the noise (decel 2, 4 and 6); twice the largest, 6.54 mm/s,
rounded up. Every other event, and every threshold event farther from its threshold than the
bound, must still occur at the same step. K13's run 3 is not re-judged under it (its straddle,
1.03 mm/s, would be within). Results: `~/nas/autoveh/logs/k13-check3/sensitivity/`.

**K10's confirmation case (2026-11-25): agrees, as predicted.** L seed 2 on seats with issue 163
(`2026-11-25T06-45-35_cs1_town01_street-6583_r0`, passed; commands lag 1, held 9, uncommanded
1) against the batch with issue 165, K10's rule: outcomes passed on both; decisions appear 64,
reject 85, go_after 124 on both; every element offset 0; the walker's max xy 1.49e-4 m (RMS
1.28e-4), the van 2.0e-5 m, the ego 0. K10's agreement holds with both new runners
(`~/nas/autoveh/logs/k13-check3/k10-confirm/`).

## K13 step v's plan: the platoon search on Town05 (2026-11-25, 241; approved by 133 the same day, before any code)

Exit check 4: the search runs end to end in the batch and reports its estimate and interval;
its prediction is written before the run, from a numpy dry run of the platoon. The design
note's "A first search", on the lane 133 chose: base Town05's anchor `west_avenue` (lanelets
105401 78805 117337 219 114959 1412 109453 2471 106424 3337, 372.518 m, 88.5 km/h; maps dataset
v2026.11g, issue 166's 18 reversed stretches listed).

**The scenario.** `src/scensim_sampler/examples/cases/k13_platoon_town05.xosc` on Town05, a
batch case (seats refuse it: issue 175); `k13_platoon` takes Town05 too for the search's map, its
lock at v2026.11g. L, a scripted lead at 22 m/s from s 110 m, brakes to rest at `$decel` after
`$onset` s. M, `scensim.behaviour:idm_follower` with L as its leader and v0 the lane's
24.58 m/s, starts at 22 m/s (Init's step `AbsoluteTargetSpeed`, issue 175's batch-only
exception) at IDM's exact equilibrium gap s_e = (s0 + vT) / sqrt(1 - (v/v0)^4) from each
sample's T (133: about 1.67 times s0 + vT at the set's T); the dry run checks |a| < 1e-6 m/s^2
for M at t = 0 in every slot before judging anything. The ego follows M at 30 m, at 22 m/s. A
scenario with issue 175's exception is a known divergence between the batch and seats: no
agreement check may use it. onset in [1, 4] s and decel in [2, 8] m/s^2 keep L's stop at or before
s 319 m, inside the anchor. No start s lies in a reversed stretch (`scensim check` refuses one
that does).

**The search.** K11e's machinery: `scensim-sample search` and
`scensim_batch/scripts/search_run.py --walker follower`. The ego is the `aeb_ttc` point mass
of K11c to K11e, an invented pilot, on the CPU; no Isaac. Variables: L's decel and onset, and M's
T, a and b on a base that is invented, labelled so (as K11c's), bracketing the set's means
(T 1.133 s, a 0.362 m/s^2, b 2.140 m/s^2): T in [0.6, 1.8] s, a in [0.2, 0.6] m/s^2, b in
[1.2, 3.2] m/s^2; s0 stays the set's 2.833 m. The failure is the ego's: a closest gap to M of
0 m or less (threshold 0, as K11e). A secondary output, not the failure: the minimum time to
collision per sample, and the count under 1.0 s. N 1000 and seed 13 are written into the spec
(`k13_platoon/searches/k13v.yaml`) before the run, and N is not raised after it.

**The prediction**, before the search: a numpy dry run of the compiled scenario at the set's
means over a grid of decel and onset (and T at its ends), no search. From it, the expected
failure region and the estimate's order of magnitude. If it predicts an estimate under about
1e-3, the prediction says before the run that N 1000 gives a wide interval, as the bar's caveat.

**The bar.** Check 4 as worded. The prediction is judged and recorded held or FAILED; a failed
prediction does not fail the check. Batch numbers are not seats numbers; no CARLA claim.

**Order.** This plan and the exit's correction (docs); the scenario, the specs and the dry run;
the prediction (docs); the run and its result; one gated landing, asking 133 first.

**The dry run, check 1 (2026-11-25): FAILED.** 36 slots (decel 2, 4, 6, 8 x onset 1, 2.5, 4 x
T 0.6, 1.133, 1.8; a 0.362, b 2.140), lead_s = 73.13 + s_e(T), the anchors bound as the
sampler binds them, at k13-step-v 7223aa53 (`k13v_dryrun.py`). M starts at 22.0 m/s in every
slot (issue 175 works). M's first command, decided on the reset observation, gives a0 =
-2.51e-4, -1.45e-4 and -9.48e-5 m/s^2 at T 0.6, 1.133 and 1.8, whatever decel and onset:
**max |a0| 2.5e-4 against the bound 1e-6, FAILED**; nothing was judged. Backed out of IDM,
M measures gaps of 26.7478, 46.3292 and 70.8335 m against s_e 26.7737, 46.3551 and 70.8594: a
shortfall of 0.025864, 0.025870 and 0.025867 m, one constant 2.587 cm while L starts on
lanelet 219 (anchor s 97.19 to 150.75), as every slot's does. The anchor's s places the cars
(lanelet_at, local_s, the world's per-lanelet spline); the follower measures its gap along its
resampled copy of the anchor's x/y. 133: investigate the cause first (an hour): a mismatch that
depends on the loops between two cars would hit any model on such a lane, and a measured
constant would hide it.

**The dry run, check 1 rerun (2026-11-25): held.** The cause is issue 166's loops (166, "A
placement s and a model's gap"): the polyline the follower measures along runs 0.025868 m short
of s between M and L, within 4e-6 m of the back-out. L now starts at 73.13 + 0.025868 + s_e(T),
the arc difference computed from the anchor, not fitted to a0. Max |a0| 4.0e-8 m/s^2 against
the unchanged 1e-6: held (at e3ca36ec). Measuring the gap in s is 166's open fix, out of K13.

**The dry run, step 2 (2026-11-25), as it came out: 0 of 36 failed; the planned ego could not
fail, by construction.** Every slot's closest gap was the start's 30.0 m at frame 0, and its
minimum time to collision undefined (never closing): the ego braked to rest by t of about 3.5 s
in every slot. K11's `aeb_ttc` takes TTC as the gap over its own speed, as if the target stood
(it was made for a walker crossing), and latches its braking: 30 m at 22 m/s is 1.36 s, under
its 1.5 s, so it braked from t = 0.

**Amendment after step 2's result (133, 2026-11-25).** The ego starts 45 m behind M (s 18.73,
clear of the stretches at 0.05 and 23.99 m); no new pilot code. Its pilot, plainly: `aeb_ttc`,
**invented**, TTC = gap / its own speed, braking latched at 6 m/s^2 to rest once TTC falls
under 1.5 s; at 22 m/s it cruises while the gap stays above 33 m. A failure (closest gap at
0 m or less) means M's braking, up to its cap of 8 m/s^2, outruns that. Step 2 is redone with
it before the prediction; 0 or all 36 failing stops the work for a look at the bounds (133).

**The dry run, step 2 redone with the amendment (2026-11-25, at 4d697ad5), as it came out: 0 of
36 failed, and not a measurement of the platoon.** Closest gaps 0.37 to 3.27 m (the smallest at
decel 8, onset 1, T 0.6), the secondary minimum TTC 0.0 in all 36; check 1 held again
(4.0e-8). The point-mass ego has no steering: it drives straight on its start yaw, the lane's
heading at s 18.73 (-178.856 deg), while west_avenue runs at -179.863 deg (+-0.01) from s 100 to
its end, its first 100 m bending about 1 deg. It drifted 0.43 m/s sideways, 1.45 m off M's line
by t = 5 s, so `aeb_ttc`'s corridor lost M and the ego passed beside it: the gaps are
side-by-side passes, and the TTC's centre-distance gap went to 0 there. Stopped for 133 (the
0-or-36 rule).

**Second amendment, after the redone step 2 (133, 2026-11-25).** The ego starts with an absolute
heading, the straight part's -179.863 deg (`<Orientation type="absolute" h="-3.13920"/>` in its
Init LanePosition); the centreline stays within 0.39 m of its straight line from s 20 to 365. A
guard: each sample records the ego's largest |lateral| from M's line (across M's heading); over
1.9 m (`aeb_ttc`'s corridor, 0.95 + 0.95 m) the sample is **invalid**, an error row the search
counts and leaves out of its estimate, not a pass or a fail (`search_run.py --corridor 1.9`).
So the failure is judged only while the two are in one corridor, as the TTC is. The search
reports the invalid count; step 2, redone again, should have none.

**Step 2 with the guard (2026-11-25, at 05fc96f8), as it came out: all 36 invalid, the guard's
fault.** Every slot read 4.044 m: the guard measured the ego's lateral across M's heading, and M's
heading swings up to 4.3 deg (-175.66 deg at t 0.75 s, s 85) as it corrects toward the
centreline past the bend and loops at s 73 to 97, which at 49 m reads as 4 m. Against the
centreline itself, slot 27 (decel 8, onset 1, T 0.6) has the ego within 0.38 m and M within
0.03 m. The guard now takes the difference of the two cars' signed offsets from the lane's
centreline (the anchor's polyline), the same "M's line" without M's heading in it.

**Step 2 with the centreline guard (2026-11-25, at 62e7e826), as it came out: 0 of 36 failed,
0 invalid.** The ego's largest lateral from M's line is 0.380 to 0.385 m in every slot. Closest
gaps, at the set's a and b: 26.6 to 28.5 m at decel 2, 12.3 to 20.3 at 4, 5.4 to 18.4 at 6, 3.4
to 17.7 at 8, the smallest at T 0.6 whatever the onset; minimum TTC 1.14 to 5.55 s, none under
1 s. Stopped for 133 (the 0-or-36 rule). For that look, not a judgement: the four a, b corners
(a 0.2, 0.6; b 1.2, 3.2) at decel 8, onset 1 and T 0.6 and 1.8 (8 slots) give closest gaps of
0.62 m (a 0.2, b 3.2, T 0.6), 1.12 (a 0.6, b 3.2, T 0.6), 5.62 and 6.08 (b 1.2, T 0.6), 16.8 to
18.4 at T 1.8; 2 under 1 s of TTC, 0 failed, 0 invalid. A large b (a later, harder IDM brake) and
a short T bring the failure nearest.

**The search's prediction (2026-11-25, 133 chose to run the box as planned; written before the
search).** The method is the search's own (`scensim_sampler.search`): the cross-entropy method,
generations of N 1000 (elite rho 0.1, alpha 0.7, the defensive mixture beta 0.1), stopped when
the level reaches the threshold or at the cap of 20 generations, then a fresh stage of 1000 draws
from the last mixture; the rate is the plain likelihood-ratio estimate with a **normal 95 %
interval** (p plus or minus 1.96 SE), Kish's n_eff beside it. With 0 failures that interval is
[0, 0]: the estimator has no spread to show. For reference only, not the tool's output: 0 of 1000
unweighted draws give a Clopper-Pearson 95 % upper bound of 3.7e-3. Every run is the batch's,
the ego the invented `aeb_ttc` (TTC = gap / its own speed, braking latched at 6 m/s^2 under 1.5 s),
on the invented base.

1. **The stop:** the level falls toward the box's corner but never reaches 0; the search runs to
   the generation cap (20), then the fresh stage.
2. **Failures:** 0 over the whole run, the generations and the fresh stage.
3. **The estimate:** the tool prints p = 0, interval [0, 0]; the caveat: N 1000 cannot resolve a
   rate under about 4e-3, and the normal interval says nothing at 0 failures.
4. **The smallest closest gap** over the whole run: between 0.5 and 0.7 m (the dry run's corner
   at decel 8, onset 1, T 0.6, a 0.2, b 3.2 gave 0.62 m), at T under 0.7 s, b over 3.0 m/s^2,
   decel over 7.5 m/s^2, onset under 1.5 s and a under 0.3 m/s^2.
5. **Minimum TTC under 1 s:** at least 300 of the fresh stage's 1000, its draws gathered near
   that corner.
6. **Invalid samples** (the corridor guard): 0 in every generation and in the fresh stage.

Check 4's bar is unchanged: the search runs end to end and reports its estimate and interval.
These predictions are judged held or FAILED apart from it.

**The search's result (2026-11-25, 14:38 to 18:17 +08:00).** Run from a worktree pinned at
4eb87377 (`k13v_search.sh`: `search init`, then each generation through `search_run.py
--walker follower --anchors ... --ttc-length 4.7 --corridor 1.9` and `search next`, then
`search report`), output `/var/tmp/aeon/k13v-search` (13 GB; to the NAS when it answers, it gave
I/O errors all day). 21 stages of 1000 draws, 21000 runs, 420 to 1074 s a stage on a loaded host.

| stage | level | failures | invalid | min TTC under 1 s | smallest closest gap (m) |
|---|---|---|---|---|---|
| g0 | 7.199 | 0 | 0 | 8 | 1.650 |
| g2 | 3.320 | 0 | 0 | 56 | 1.158 |
| g4 | 1.844 | 0 | 0 | 621 | 0.959 |
| g6 | 1.259 | 0 | 0 | 914 | 0.613 |
| g9 | 0.918 | 0 | 0 | 890 | 0.472 |
| g14 | 0.563 | 0 | 0 | 903 | 0.426 |
| g19 | 0.440 | 0 | 0 | 896 | 0.389 |
| fresh (from g20's mixture) | | 0 | 0 | 892 | 0.374 |

The other stages fall between their neighbours (the full table is the run's log); errors 0 in
every stage, normaliser 1 (no constraints), largest weight 10 (1 / beta) from g1 on. The report:
stopped at the generation cap (20); the fresh stage's rate 0, se 0, "plain likelihood ratio,
normal 95 % [0, 0]", n 1000, n_eff 108.0; the generations' own (biased) estimate 0; failures
found 0. Largest lateral offset between the two cars' centreline offsets over all 21000 runs:
0.385 m (the guard's bar 1.9 m).

**The tool's interval at 0 failures is not an answer; see issue 183.** [0, 0] is what the normal
interval prints when there is no failure to estimate a spread from. What the run supports is an
upper bound, and the fresh stage's draws from the defensive mixture give one without any
assumption about where failures lie: every weight is at most 1 / beta = 10, so the rate is at
most 10 times the mixture's own failure probability, whose exact one-sided 95 % bound at 0 of
1000 is 3.68e-3: the rate on this invented base is under 3.7e-2 at 95 %. That is loose, and it
is what 0 of 1000 can say (issue 183's fix; not in K13). For how much the tilt costs: the fresh
stage's n_eff is 108.0 of its 1000 draws.

The predictions:

1. **The stop: held.** The level fell from 7.20 to 0.44 m by g19, by 0.012 to 0.037 m a generation
   from g15 on, and the search ran to the cap, then the fresh stage.
2. **Failures: held.** 0 in all 21000 runs, the generations and the fresh stage.
3. **The estimate: held.** The tool printed p 0, [0, 0]; the caveat stands, and the interval is
   not an answer (issue 183).
4. **The smallest closest gap: FAILED.** 0.374 m, below the predicted 0.5 to 0.7 m, in the fresh
   stage (record 842ce095153ce27c21eccd0f4d55358334dba48ca628a226468f95a2a2807f97, at 11.30 s):
   decel 7.991, onset 3.628, T 0.600, a 0.308, b 3.182. T, b and decel are where predicted;
   onset (predicted under 1.5 s) and a (under 0.3) are not. The search went to the late onsets,
   which the dry run's corners never sampled (they held onset at 1 s). See the open question
   below.
5. **Minimum TTC under 1 s: held on the count, FAILED on the place.** 892 of the fresh stage's
   1000 (bar: at least 300), smallest 0.335 s. Its draws gathered at T, b and decel's corner
   (901, 904 and 902 of 1000 past the predicted bounds; medians T 0.601, b 3.175, decel 7.975)
   but not at onset's or a's: 41 of 1000 have onset under 1.5 s (median 2.975) and 347 have a
   under 0.3 (median 0.305).
6. **Invalid samples: held.** 0 in every stage.

**Open question: why the late onsets.** Not explained; one hypothesis, not a claim. All three
cars hold 22 m/s until L brakes (two fresh slots' traces: the ego's speed 22.0 and its
centre distance to M 49.6 m, unchanged up to onset), so onset does not change the gaps at the
moment L brakes; it moves where on `west_avenue` the platoon brakes and stops, 22 m further down
the lane for every second. The ego holds a fixed absolute heading (-3.13920 rad) while M follows
the lane, so their lateral offset, and with it the box-to-box closest gap, depends on where they
come to rest (the offset reached 0.385 m). The hypothesis: the late onsets are where the lane's
shape against the ego's fixed heading takes the most off the gap. A test: rerun record 842ce095
with onset swept from 1 to 4 s, the others held, logging the stop s, the lateral offset at the
closest approach and the closest gap; if the gap follows the offset, the hypothesis holds and the
corner is a point-mass artefact, not the model's.

**The onset sweep's prediction (2026-11-25, 133 asked for the sweep; written before it runs).**
The batch on the CPU, the search's own path (`search_run.run`, `--walker follower`, the anchors,
`--ttc-length 4.7`, `--corridor 1.9`, 600 steps of 0.05 s), from the pinned worktree at
4eb87377: record 842ce095's values with onset set to 1.00, 1.25, ..., 4.00 (13 slots), every
other value held, plus record 842ce095 itself unchanged. At each slot's closest approach (the
outcome's frame): the box-to-box closest gap (the search's score); the lateral offset, the
difference of the ego's and M's signed offsets from `west_avenue`'s centreline (the guard's
measure); and the longitudinal gap, the difference of the two cars' arc positions projected on
the anchor's polyline, less the car length 4.7 m.

0. **Reproduction** (a stop if it fails, nothing else judged): record 842ce095 unchanged gives
   0.373715 m to within 1e-6 m.
1. **The gap tracks the offset.** The closest gap spans at least 0.05 m across the 13 onsets,
   and its Pearson correlation with the absolute lateral offset at the closest approach has
   |r| >= 0.8. The sign, judged separately: negative (more offset, a smaller gap).
2. **The longitudinal gap is about flat.** Its range across the 13 onsets is at most 0.02 m.

If 1 (the |r| part) and 2 hold, the late-onset corner is the point-mass ego's artefact (its fixed
heading against the lane's shape), not the model's, and the search's result stands as recorded.

**The onset sweep's result (2026-11-25, at 3e9b3a5d's prediction; `k13v_onset_sweep.py`, from
the worktree at 4eb87377).** Closest gap, lateral offset and longitudinal gap at the closest
approach, and M's arc position there:

| onset (s) | gap (m) | lateral (m) | longitudinal (m) | M at (m) |
|---|---|---|---|---|
| 1.00 to 2.75 (8 slots) | 0.42450 to 0.42457 | 0.3797 to 0.3814 | 0.42455 to 0.42464 | 173.8 to 213.4 |
| 3.00 | 0.42564 | 0.3816 | 0.42576 | 218.9 |
| 3.25 | 0.40246 | 0.3819 | 0.40247 | 224.4 |
| 3.50 | 0.37442 | 0.3821 | 0.40343 | 229.9 |
| 3.75 | 0.37361 | 0.3824 | 0.37361 | 235.4 |
| 4.00 | 1.47345 | 0.3825 | 1.47358 | 240.9 |

0. **Reproduction: held.** 842ce095 unchanged gave 0.3737147 m.
1. **The gap tracks the offset: FAILED.** The gap spans 1.100 m, but the lateral offset barely
   moves (0.3797 to 0.3825 m), and the Pearson correlation is +0.397 (bar |r| >= 0.8); the sign
   is positive, not the predicted negative.
2. **The longitudinal gap is about flat: FAILED.** Its range is 1.100 m (bar 0.02 m): it is the
   closest gap itself, to within 3e-3 m in every slot but onset 3.50 (0.029 m).

So the hypothesis fails: the corner is not shown to be the fixed heading's artefact, and the
late onsets change the gap along the lane, not across it. The gap is flat at 0.4245 m for onsets
1 to 3 s, drops to 0.374 m between 3.25 and 3.75 s, and jumps to 1.47 m at 4.0 s; a step
pattern, not a trend. A second hypothesis, not a claim: the drop's slots have the platoon
braking over one of issue 166's reversed stretches (s 226.73 to 226.78; M at the closest
approach at 224.4 to 235.4 m), and M measures its gap to L on the anchor's polyline (166's open
fix: the gap in s), so a stretch between M and L changes M's braking and with it the ego's
closest approach. Against it: the stretch at s 175.95, under the platoon at onsets 1 to 1.5 s,
shows no such drop. The
search's result stands as recorded; the question stays open and goes to 166's follow-up, whose
plan can test it (the same sweep with M's gap measured in s).

**Later (issue 166's gap-in-s fix, 2026-11-25).** The follower now measures its gap in s and
`lead_s` no longer carries + 0.025868; this search ran with both, consistent with each other,
and stands. The sweep rerun under the fix (166's check 4) FAILED the second hypothesis: the drop
of about 0.05 m between onsets 3.25 and 3.50 s is still there, and the 1.100 m jump moved from
4.00 to 2.75 s. 1.100 m is 22 m/s times one 0.05 s step; that the jumps are the ego's `aeb_ttc`
latching a frame earlier is 166's hypothesis, not tested. The question stays open.

**The step-size sweep's prediction (2026-11-25, 133; before it runs; not a landing condition).**
The same sweep under the fix (record 842ce095, `lead_s` without the correction, onsets 1.00 to
4.00 by 0.25) at step 0.025 s (1200 steps, the same 30 s), every other setting as before. If
the 1.100 m jump is the ego latching a frame earlier, it scales with the step: the jump between
onsets 2.50 and 2.75 s moves, or halves to about 0.55 m (22 m/s times 0.025 s). Held if no
jump of 1.10 +- 0.05 m remains between 2.50 and 2.75 s and every jump between consecutive
onsets is under 0.60 m; FAILED otherwise.

**The step-size sweep's result: held** (`i166_step025.py`, the dev worktree at e6d3bc0a, the fix
in it):

| onset (s) | closest gap (m) at 0.025 s | at 0.05 s (166's check 4) |
|---|---|---|
| 1.00 | 0.98391 | 0.40693 |
| 1.25 to 2.75 (7 slots) | 0.97572 to 0.97599 | 0.39870 to 0.39895, then 1.49871 at 2.75 |
| 3.00 | 0.97942 | 1.49980 |
| 3.25 | 0.97429 | 1.49794 |
| 3.50 | 0.92810 | 1.44936 |
| 3.75 and 4.00 | 0.92508, 0.92491 | 1.44786, 1.44762 |

No jump of 1.10 m remains between 2.50 and 2.75 s (-4e-5 m there), and the largest change
between consecutive onsets is 0.046 m (3.25 to 3.50 s), under 0.60 m; nor is there a 0.55 m
jump: the closest approach's frame advances 10 frames per 0.25 s throughout. With the step
halved, the gap sits at 0.976 m, between the two levels the 0.05 s step gave (0.399 and
1.499 m), so the 1.1 m jumps were the 0.05 s step's, as hypothesised. Two things remain, not
explained: the drop of about 0.05 m between onsets 3.25 and 3.50 s, at both steps and with
the gap in s or not; and the closest gap's dependence on the step itself, about 0.5 m either
way at 0.05 s, which bears on the search's smallest gap (0.374 m at 0.05 s) as a measure of
the ego pilot's timing, not of the platoon. The question stays open.

**The commits named above, before and after the landing's rebase (133, 2026-11-25).** K13 step
v was written, run and judged on a branch based on d7a25ff5; it landed rebased onto
77fcc1a3. The SHAs named in this section are the pre-rebase ones, the commits the dry runs, the
search and the sweep actually ran at (the search at 4eb87377). They are not on main; the
whole pre-rebase branch is kept as a verified git bundle,
`/var/tmp/aeon/k13v-search/k13-step-v.bundle` (sha256
`88ed5d406f3a16de4075764bce3b8b8171568310fede14d6d0f0256873b9e8df`; tip b6d6d4e3cf6e380c0c64878d83b46c3a7a506721, requires d7a25ff5e89e9e4cbef4120cbda375aae232a841), beside the search's output, and on the NAS with it
(`~/nas/autoveh/logs/k13-step-v/search/k13-step-v.bundle`, verified by its SHA256SUMS,
2026-11-25). `git range-diff 77fcc1a3..72b99255 d7a25ff5..k13-step-v` pairs every commit: "=" is the
same change; the two "!" differ only in `docs/issues/README.md`'s context rows (the issues that
landed on main in between), their own 175 and 183 rows the same.

| pre-rebase | | landed | commit |
|---|---|---|---|
| f53547d0 | = | 6dcac7c0 | 092 K13 step v: the platoon search's plan (before any code); the exit's check 4 corrected |
| 0c329362 | ! | 86860521 | issue 175: a model entity starts at rest; an initial speed is batch-only (record and plan) |
| dbfe1859 | = | 9a50cfba | issue 175: a model entity's Init step speed is its speed at reset in the batch; seats refuse it |
| 9df3322e | = | fe21a921 | 092 K13 step v: the Town05 platoon case, its invented base and the search spec (N 1000, seed 13) |
| 133b8e41 | = | 949833a6 | k13_platoon: lock Town05 too, at v2026.11g (092 K13 step v's map) |
| ffc197b0 | = | b6418a80 | search_run: a car-follower's lane anchors, the walker's decision file only for a walker, min TTC (092 K13 step v) |
| 7223aa53 | = | f8c38c45 | k13_platoon_town05: a FileHeader binding names its parameter as param:lead_s (issue 131) |
| e3ca36ec | = | 41c8cbf6 | 092 K13 step v: dry-run check 1 FAILED, its cause (issue 166's loops against the follower's gap) and the computed correction |
| 4d697ad5 | = | 8490695b | 092 K13 step v: check 1 holds; step 2's 0 of 36 as it came out; the ego 45 m behind (amendment) |
| ed90ff22 | = | 88f91e44 | 092 K13 step v: the redone step 2 as it came out (0 of 36; the ego drifts off the lane) |
| 05fc96f8 | = | 1e4ddfbe | 092 K13 step v: the ego's absolute heading and the corridor guard (second amendment) |
| 62e7e826 | = | 58fc50b5 | 092 K13 step v: the corridor guard measures against the lane's centreline, not M's heading |
| 1bfad7b4 | = | b7110bc5 | 092 K13 step v: step 2 with the centreline guard as it came out (0 of 36 failed, 0 invalid) and the a, b corners |
| 0e6f4e4b | = | 54d5b595 | 092 K13 step v: the search's prediction (before the search); search_run reports the smallest closest gap |
| 4eb87377 | = | 59cbd0b5 | k13_platoon_town05: its category, R1.lead_brake.platoon_idm (the search reads it) |
| 1eb18ab8 | ! | 50a33f67 | 092 K13 step v: the search's result; issue 183 (the [0, 0] interval at 0 failures); 175 fixed |
| 820e9331 | = | 2de722b3 | 092 K13 step v result: n_eff beside the bound; the late onsets as an open question (133) |
| 3e9b3a5d | = | e3f2be53 | 092 K13 step v: the onset sweep's prediction (before the run) |
| b6d6d4e3 | = | 72b99255 | 092 K13 step v: the onset sweep's result (the fixed-heading hypothesis FAILED) |

**Check 4: held.** The search ran end to end in the batch and reported its estimate and interval;
the prediction was written before it (0e6f4e4b). Batch numbers, not seats numbers; no CARLA
claim.
