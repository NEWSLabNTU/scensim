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
| K10 | 093 D3's behaviour models (scenario-description.md section 4): the model interface (a parameter schema, `reset`, `step`, one array API code for numpy on seats and `step_batch` in torch; truth in, a kinematic command out, decisions into the truth), the starter model (a gap-acceptance walker for CS1, from a published model named before any coefficient), batched in scensim_batch, on seats as a K4 attachment that commands its entity through K12; the agreement check in K2.4's style (the same records on both forms: decisions and their frames, the walker's trajectory error, trigger times, verdict); the latency from a truth frame to the command taking effect measured free-running and in lockstep (093's open question 1) | component | K2, K4, K12 | swb 241 | done 2026-11-24; its open recheck (issue 130) closed the same day, the decisions at the same frames on new seats runs ("K10's open recheck" below) (the close-out below: the engines' map-frame velocity, D3's section 4 out of draft; not covered: a vehicle model, parked with the user, and an agreement with an engine in the loop, until both targets share an ego). Before: planned 2026-11-22 (133 approved), the section 4 draft corrected (SSv2 takes a world-owned pose for any entity; pilots do not see truth, attachments do); (i)-(ii) landed ce760b69: `scensim.behaviour`, the walker on numpy and torch bit for bit (0 of 2800 arrays differ on an RTX 5090), its coefficients the cited set `khaki2021_restricted` (Khaki and Mohammadnazar 2021, CC0; the gap's 2.021 against the 2021 meta-analysis's pooled 1.98); (iii) in the batch: a model entity (role `model`) compiled from its ObjectController (its properties per slot, `anchor.*` for the crossing, its seed from `seeds.pilots.<entity>`), stepped after the ego's physics on its truth and moved kinematically within its acceleration limit; CS1's start trigger is the model's `start_gap` (`$ttc_entry`), as the subset keeps ActivateControllerAction seats-only; the walker decides where it can still stop at the kerb; `cs1_walker_gap_acceptance.xosc` the batch example (the description's CS1 stays refused: a storyboard SpeedAction on a model entity); (iv) the agreement with seats passed 2026-11-24 on K12's exit set 3 ("K10's agreement" below: the seats ego played back, no engine; the batch now takes a model entity as world-owned with the channel's lag 1), (v) the latency is K12's (set 3: lag 1 in lockstep and free-running); not covered: an engine in the loop, the engines' map-frame velocity |
| K12 | Truth-fed pilots: a command channel from a K4 attachment to the world server (`entity_command`: an entity's kinematic command, carried with the tick gate's acknowledgement, integrated and applied by the world, read back to SSv2, whose fork adopts it for a simulator-driven pedestrian), under lockstep held to one frame; for K10's behaviour models and learned background agents | component | K4 | swb 243 | landed 2026-11-23 (scensim 0cc054d8; the SSv2 fork's model pedestrian, COMMANDED on the world protocol, the CARLA world server's integrator, the bridge, truth schema 3, attachments' `commands:`, `scensim.behaviour.seats`); pedestrians first, CARLA only; exit passed 2026-11-23 on set 3, by the rule fixed before the runs ("K12's exit runs" below) |
| K11 | 093 D4's search (purpose B): an adaptive search over cells that writes the record's reserved `search` | component | K1, K7 | swb 241 | in progress: K11a done 2026-11-24 (`scensim-sample search`; "K11a's result" below, check 1's fourth part failed, its cause named); K11b, K11c open |
| E1 | Examples | examples | the above | | open |

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
world provides; it stays as the description's example. The world: the map export of the
project's Town01 (`scensim.lock`, carla-town-autoware-maps 19d52699), the one K10's recheck used
(map_sha256 ee291b6e), and its `anchors.resolved.json` for the sampler.

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
