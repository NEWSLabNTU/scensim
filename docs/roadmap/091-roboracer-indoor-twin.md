# 091: A RoboRacer Indoor Twin on Isaac Sim

**Status**: opened 2026-11-20 (user). Design agreed in conversation; step 1, the design note, done 2026-11-20 (approved by 133): [roboracer-indoor-twin.md](../design/roboracer-indoor-twin.md); the reference stack for step 5 is f1tenth_system's `humble-devel` (133); a component sees the car's own sensors and, when it declares them, ground truth the user also measured on the real car (the user). Step 2 in progress (241); work items W1 to W23 below, registered 2026-11-20 (user).

## Goal

A user with a RoboRacer (a 1/10 or 1/5 scale racing car) and a real indoor field builds a
twin of both on Isaac Sim, and runs their RoboRacer stack against it through scensim:

- **the field** looks and behaves like the real one: floor materials, friction, walls, cones
  and other objects;
- **the car** drives like the real one, from a vehicle model the user fits to measurements.

Success: the user's stack drives the twin with the same commands it sends the real car, and
lap times, speeds and stopping distances fall within the spread of the real car's, measured
the same way.

## The two decisions (user, 2026-11-20)

### The vehicle is a black box the user owns

The car's simulated control component (its speed controller, motor and steering servo) is
part of the user's RoboRacer stack, not of scensim. The user models it as a black box from
measurements on the real car (step responses, coast-down, braking, steering rate) and keeps
it in their own workspace. scensim provides the physics and a place to plug the component in.

- **What goes in**: the commands the real car's controller takes, typically speed or duty and a
  steering angle (`ackermann_msgs` on `/drive` in most RoboRacer stacks).
- **What comes out**: what PhysX needs every physics substep: a torque per wheel and the
  steering angle.
- **Where it runs**: inside the physics loop, as `sim_vehicle_ecu` does for the shipped cars
  (aib steps it every substep), not as a ROS node. A node would act a step late and break
  lockstep.
- **How it is found**: by name, from the user's workspace (a Python entry point, or an FMU
  through the powertrain slot `fmu` that `sim_vehicle_ecu` already reserves). scensim's
  repositories never hold a user's model.

A word clash to keep out of the docs: on a RoboRacer "ESC" is the electronic speed controller
(often a VESC). In scensim, `esc` is the brake module's stability control. The user's ESC is,
in scensim's terms, the powertrain.

### Detailed attributes live in the USD stage

Isaac Sim's editor is where users set a floor's material and friction and each object's
properties; that convenience is why they work there. So for an indoor field:

- **the USD stage is the source of truth** for per-object detail. scensim loads it and never
  overwrites what was authored in it;
- **the scenario file** stays about the scenario: entities, routes, start conditions, events.
  It does not set attributes per object;
- **Track C's records** (the surface file and the road record, roadmap 086) remain the source
  for generated outdoor maps and for anything CARLA must share. On an authored indoor stage
  they are optional overrides, and a run records which applied;
- **reproducibility**: every run records the hash of the USD it loaded (and of each layer it
  composed), so a result names the exact stage it ran on.

## What exists and what is missing

| | Today | Missing |
|---|---|---|
| the car's description | a spec (`vehicles/<car>.yaml`) in the user's testbench; generators make the catalog entry and the Isaac rig (`aib.gen --spec`) | own cars on Isaac: `testbench check` refuses them; small-scale cars untested (mass, wheelbase, timestep) |
| the car's control component | `sim_vehicle_ecu`: `ideal` and `ev` powertrains, chosen by name | a plug-in point for the user's model; `fmu` reserved, not built |
| the control stack | pilot kinds `launch` and `command` run the user's own stack | the vehicle interface speaks Autoware's topics; RoboRacer stacks use `ackermann_msgs` |
| the field | a map directory with its Isaac world, as the Haruna and Tsukuba courses have | loading an authored indoor stage as a map; recording its hash; the rule that authored attributes win |
| sensors | the spec's sensors, generated into the rig | RoboRacer's (a 2D lidar, an IMU, a depth camera, wheel odometry) checked against the real ones |

## Steps

1. **Design note** (no code): the plug-in interface (signature, units, the substep contract,
   reset on spawn, how it is named in `testbench.yaml`); USD as source (which attributes scensim
   reads, which it may set, the precedence with Track C's records, the hash); the vehicle
   interface for an `ackermann_msgs` stack; the measurement protocol (which runs on the real
   car, which quantities, the acceptance bands). Reviewed before step 2.
2. **The plug-in point** in `sim_vehicle_ecu` and aib: the user's control component loaded by
   name from their workspace and stepped every substep; `ideal` and `ev` move behind the same
   interface. Exit: a sample component in a test workspace, outside scensim's repositories,
   drives a shipped car identically to `ideal`.
3. **Own small cars on Isaac**: lift `testbench check`'s refusal; a RoboRacer spec as the worked
   example (geometry, mass, tyres from measurements); the physics timestep and solver settings
   a 1/10 car needs. Exit: the example car holds a straight line, turns at full lock and
   stops, steady at the chosen timestep. Open risks this step must answer (133's study, the
   user's approval, 2026-11-20):
   - PhysX's tyre model against foam and soft RC tyres;
   - jitter of a light car (forums suggest steps of 5-10 ms or smaller);
   - collisions with walls and cones: restitution and friction measured, not assumed.
3b. **Fitting**: a tool that fits the car's spec and the user's component from logged
   manoeuvres. It is scored by the long-horizon trajectory error from matched starts, not by
   one-step error. It starts with on-track identification (arXiv 2411.17508 fits a Pacejka tyre
   from on-track F1TENTH data in under a minute); fitting through a differentiable simulator is
   an option later. Identification runs come first (arXiv 2606.22062: a few identification
   rollouts close most of the gap). Randomisation, where wanted, only around the fit, in a band
   no wider than the real runs' own spread. Exit: the example car fitted from its logs passes
   M1 to M6's bands (validation level b, below).
4. **An authored indoor stage as a map**: a map directory whose world is the user's USD;
   authored attributes kept; Track C overrides applied only where given; the hash in the run's
   results. The stage is layered:
   - a visual layer from a scan (Isaac's NuRec Gaussian splats, or a mesh), with the raw scan
     kept beside it as evidence;
   - a physics layer of colliders authored in Isaac. It is required, since splats have no
     collision;
   - measured attributes (tilt-test friction, object masses) stored on the prims with their
     source;
   - `provenance.stage` hashes every layer.

   Exit: an attribute changed in Isaac's editor shows in the next run's behaviour and its
   recorded hash, with nothing else edited.
5. **The `ackermann_msgs` vehicle interface**: the topics a RoboRacer stack expects, offered by
   the vehicle side. Exit: an unmodified open RoboRacer stack drives the example car.
6. **The guide**: "A RoboRacer indoor twin", the design note's procedure (section 7: the map twin F1-F5, the vehicle twin V1-V4, joining them J1-J3), from the measurements to a run, with the
   fitting harness (measured responses against the simulated component's). It validates at
   three levels:
   - (a) the component alone: logged commands replayed against the logged VESC telemetry;
   - (b) the car: M1 to M6's bands;
   - (c) laps with the user's stack: M7.

   Two rules apply throughout:
   - **Session conditions**: battery voltage, floor state and tyre age, recorded with every run
     and every real log. The component may declare battery voltage as an input; a learned VESC
     model in the style of ANYmal's actuator net (arXiv 1901.08652) needs it.
   - **Friction measured two ways that must agree**: an inclined-plane tilt test of the tyre on
     the floor (ASTM G219 style) and M6's grip limit.

## Work items

The procedure the user follows is the design note's section 7 (map twin F1 to F5, vehicle
twin V1 to V4, joining them J1 to J3). These are the work items that give every procedure
step its tool or interface, and that close the gaps found so far (2026-11-20). Owner "open"
means not yet assigned; 133 assigns.

| # | work item | for | step | owner | state |
|---|---|---|---|---|---|
| W1 | the component interface in `sim_vehicle_ecu`, `Ecu` behind it, `ideal` and `ev` registered, declared truth (`TruthFeed`) | V3 | 2 | 241 | done 2026-11-20 (scensim 1b596d7: sim_vehicle_ecu 7bdcb8e, sim_vehicle_spec f96adf5, aib 7cf7905) |
| W2 | aib's `Vehicle.apply` calling the component; the Isaac exit check (a sample component from an outside workspace, byte-identical to `ideal`) | V3 | 2 | 241 | done 2026-11-20 (scensim 1b596d7: sim_vehicle_ecu 7bdcb8e, sim_vehicle_spec f96adf5, aib 7cf7905) |
| W3 | the testbench side: the pilot's `component:` key, the overlay workspaces on the world server's path, `testbench check`'s import and cost checks, the truth settings, the component's provenance | V3, J2 | 2b | 241 | done 2026-11-20 (scensim 749d5dc, pins 9300a5d: aib db5bf97, scensim_isaac_world 0715624; Isaac run with a workspace component passed) |
| W4 | the `fmu` component: an FMI 2.0 unit wrapped as one shipped component, for compiled models; its dependency decided | V3 | 2 | 139 | done 2026-11-21 (pins 68c76f99: sim_vehicle_ecu 3be6e52, aib 5daa8be, scensim_isaac_world f76a279). `component: fmu`, params name the unit relative to the spec and map its variables to the command, sensors, declared truth and the actuation (sim_vehicle_ecu `fmu.py`, README). The dependency: none. It is a standard-library FMI 2.0 co-simulation runner (ctypes); FMPy was weighed and not taken (its core needs 7 packages in Isaac's venv). Linux x86_64 units, one instance per car, so a batched host can loop them (092 S3). In Isaac's Python 3.12 it costs 7.5 us per step against 250 us at 240 Hz. Against FMPy 0.3.32 on Modelica Reference-FMUs v0.0.42 (archive sha256 b6b4a195...1e97): VanDerPol, 1000 steps, max difference 0; Feedthrough's Real, Integer and Boolean the same |
| W5 | own cars on Isaac: lift `testbench check`'s refusal; the rig made from a user's spec in the testbench | V1 | 3 | 118 | done 2026-11-20: the stack makes the rig (`state/vehicles/<car>/isaac/`), the ego drives it (the box shows); `testbench check` names every body a spec drives (`body:` and each of `bodies:`). Live on Haruna: an own copy of the Model 3 passed as the installed one, rigs equal but for identity (NAS `2026-11-20 091 W5 own car on Isaac (118)`) |
| W6 | a small-car example spec (1/10 RoboRacer class) and its refit of the full-size settings: PhysX slip denominators, `est_slip_offset`, sticky-tyre thresholds, suspension frequency, wheel inertia | V1, V4 | 3 | 118 | done 2026-11-20: `scenarios/projects/roboracer` (the spec, `tools/smallcar.py`, the refit and its reasons in its README); sim_vehicle_ecu 4f6cfd5 reads `est_slip_offset` from the spec's `min_active_slip_denominator`, aib 0a69293 caps the bump stop's engagement at half the travel (pins 9729cff6). The suspension is 5 Hz: at 3 Hz the static sag was 92 % of the travel and the results depended on the physics rate. At 5 Hz, 60 to 480 Hz agree within about 1 % on Isaac (NAS `2026-11-20 091 W6 RoboRacer refit (118)`) |
| W7 | the physics rate and solver for a light car: jitter tests at 100 to 600 Hz, the cost of each, the chosen default | V4 | 3 | 118 | done 2026-11-20: 240 Hz for a 1/10 car (`scenarios/projects/roboracer` README). Below 200 Hz its wheels slip against a wall they push on (0.16 to 0.33, against 0.02); above 240 Hz the results move by a few percent, at 1.4 ms per step per car (0.35 s per simulated s at 240 Hz). TGS kept. aib's acceleration (IMU, brake module) is a second difference of float32 positions per step, its noise about the rate squared (0.16 m/s^2 at 600 Hz). The cone's tip-or-carry is W9's (NAS `2026-11-20 091 W7 RoboRacer physics rate (118)`) |
| W8 | the tyre-model risk: PhysX's tyre against foam and soft RC tyres, measured on M5 and M6; a decision to keep it, tune it, or take tyre forces from the component | V4 | 3 | 118 | done 2026-11-20: keep PhysX's tyre, tuned per axle (`scenarios/projects/roboracer` README, `tools/tyre_compare.py`). Against ForzaETH's identified F1TENTH tyres (NUC6, NUC7: rear about twice the front's cornering stiffness), one tyre for all four wheels (spec v2) misses M5's radii by up to 23 to 27 %; a stiffness and friction per axle comes within 5 to 7 %, and on Isaac (aib's per-wheel setters) within 4.5 and 1.8 %. Needs front and rear tyres in the spec (proposed to 133). Beyond the peak PhysX's curve stays flat (NAS `2026-11-20 091 W8 RoboRacer tyre model (118)`) |
| W9 | collisions with walls and cones: restitution and friction read from the authored materials, checked by drop and push tests | F3 | 3, 4 | 118 | done 2026-11-20: authored restitution and friction are PhysX's as authored (drop, slide, tilt within 0.01 to 0.02 at 240 Hz; `tools/contact_check.py`); a pair's friction is combined (`average` by default), so a measured pair value goes on both materials or with a combine mode (for W21). The car's body has no material (aib authors none): a wall at restitution 1.0 returns 0.41, 0.86 with a body material (proposed to 133: a body contact material in the spec). The cone tips above about mu 0.5 and rides below it at every rate; PhysX's defaults sit on that threshold (W7's flip) (NAS `2026-11-20 091 W9 RoboRacer walls and cones (118)`) |
| W10 | the fitting tool: long-horizon trajectory error from matched starts; on-track tyre identification first; fits the spec's tyre and suspension values and a component's exposed `params`; randomisation bands from the real spread | V3, V4 | 3b | 118 | in progress: the tyre stage is PhysX's own tyre and the twin fits each axle's stiffness from M5's gentle circles, then its friction from M6 and M6b (the protocol's new rear limit); the latency is held at its stage; W23's regression reruns at the RoboRacer's new lateral slip denominator (0.05) with a blind p3. Findings below (W10: findings) |
| W11 | the validation harnesses: (a) component replay against logged VESC telemetry, (b) M1 to M6 against 5.3's bands, (c) lap comparison for M7; one report per twin release | V3, V4, J1 | 3b, 6 | open | |
| W12 | session conditions: a schema (battery voltage, floor state, tyre age) recorded with each run and each real log; battery voltage declarable as a component input | V2, J2, J3 | 2b, 6 | open | |
| W13 | the authored stage as a map (`authored: true`): the session-layer rule, the material and `scensim:surface` readers, Track C overrides only where given | F2, F3 | 4 | 243 | done 2026-11-21 (scensim_isaac_world 3314646 and f7f155a). Isaac exit (`spikes/authored_floor.py`): a field authored as in Isaac's editor, floor material at dynamicFriction 0.5 and 1.0, decided by the material both times; the aib car's friction-limited stop 4.36 and 8.10 m/s^2 (ratio 1.86, distance 12.62 and 7.13 m), the field's file untouched. It first worked end to end through the bridge on 2026-11-21, with W17's fix: the bridge's world file refused `authored` until then, and W13's exit drove IsaacWorld directly, not through the bridge |
| W14 | the layered stage: visual layer (NuRec splats or a mesh), evidence layer (raw scan), required physics layer; `scensim:source` on measured attributes | F2, F3 | 4 | 243 | done 2026-11-21 (scensim_isaac_world ac3f253, 54a4ae4; scensim: the map check's notes, design 3.1). The map check refuses a stage with no collider; world.yaml's `evidence:` and each measured attribute's `scensim:source` are hashed into provenance.stage (`evidence`, `measured`); an unsourced floor friction is a note. Isaac exit (`spikes/layered_field.py`): with and without a visual scan mesh 5 cm above the physics floor the car rests at z 0.00 and drives 5 m at z -0.003, so the mesh is never ground |
| W15 | `provenance.stage`: the sha256 of every composed layer and resolved asset, the overrides, the records; an unresolved dependency refuses the run | F5, J2 | 4 | 243 | done 2026-11-21 (scensim_isaac_world 2d113f5 and eaaa141; scensim `stage.py`): the world server writes `<state>/<map>/stage.json` at each authored load, the run puts it in `result.json`; file hashes cached by (path, size, mtime), the hashing time recorded |
| W16 | the map check: units and axes, no PhysX vehicle prim, every layer resolved and hashed | F5 | 4 | 243 | done 2026-11-21 (scensim_isaac_world 2d113f5; scensim `stage.py`): `testbench check` runs it on every `authored: true` map in a Python with pxr (Isaac's, this one, `python3`), a skip says so and why; the shipped CARLA maps are not authored and not checked (their `_physics.usda` and Town01.usd are metres and Z up) |
| W17 | the minimal lanelet2 loop generator, from the field's centreline or the occupancy map | F4 | 4 | 243 | done 2026-11-21 (scensim_isaac_world 8d29372, 8b05389; scensim: the bridge accepts `authored` and `evidence`, a test holds its world-file keys to the world server's). `python -m scensim_isaac_world.loop`: one one-way lane along a closed centreline (a CSV or a BasisCurves prim), its direction in the map's header, TransverseMercator at 0, 0 with the lat/lon synthetic (SSv2 takes no Local projector), and a flat point cloud of the lane, which SSv2's loader requires. Exit: SSv2 on Isaac on an authored field, the simple pilot routed 122 m round the loop's lanelets to its goal, passed |
| W18 | the `ackermann` and `vesc` vehicle-interface profiles, mirroring f1tenth_system `humble-devel` (`vesc_driver_node` topics, `/sensors/core` from the component's telemetry, the servo echo); `jazzy-devel`'s names checked | J1 | 5 | 241 | done 2026-11-20 (scensim f2808c0, pins 9b4e138: sim_vehicle_ecu 36972f4, aib 97ab2f0, scensim_isaac_world 1f37105; f1tenth's own vesc_to_odom read the twin on Isaac, speed and yaw rate within 1 % of the ground truth) |
| W19 | the RoboRacer sensors: a planar lidar profile (UST-10LX class) checked against real scans at known poses; the IMU; wheel odometry by `vesc_to_odom`'s kinematics | F5, J1 | 5 | 241 | done 2026-11-20 (pins dd126de: sim_vehicle_spec 69346ab, aib e620250 and 5520655 through 18d218e). The real scans wait for W22; the planar lidar was checked instead against a walled room's analytic distances, 1080 of 1081 beams within 1.5 mm. `sensors/core` runs at 50 Hz, the VESC's IMU in its own units. `/scan` comes at the frame rate (20 Hz under 20 Hz frames), not 40 Hz |
| W20 | the end-to-end exit: an unmodified f1tenth_system drives the example car in an example field | J1 | 5 | 241 | done 2026-11-21 (`scenarios/projects/roboracer` README, `tools/w20_run.sh`): f1tenth_system `humble-devel` and `jazzy-devel` as shipped, at the `vesc` level, drive the example car with the stand-in drive unit around a 12 m x 8 m walled room for 120 s on Isaac Sim 6.2, a wall follower standing in for the user's navigation (f1tenth_system has none), at 240 Hz physics and 20 Hz frames: 151.3 m at 1.26 m/s on both branches, the body at least 0.64 m from the walls, every node of the stack finishing cleanly; one run of seven, on humble-devel, had sparse scans from its start and drove into a wall (issue 099). `/odom` is within the stand-in's calibration: speed 1.2 % high, yaw rate v tan(delta) / L. Three findings: the stand-in's ERPM sign (issue 098, fixed: `erpm_sign`, -1 for humble-devel, +1 for jazzy-devel); vesc.yaml's node-scoped `wheelbase` outranks launch parameters (the guide's RoboRacer section); at 40 Hz frames the 40 Hz lidar's reads are short of a revolution (issue 099, fixed in aib 79d68cd: the stock lidar's 20 Hz tick had been left in place; now whole at 40 Hz frames), so W20 runs at 20 Hz frames, where `/scan` comes at 20 Hz. NAS `2026-11-21 091 W20 f1tenth_system on the twin (241)` |
| W21 | the guide, "A RoboRacer indoor twin": the procedure, the measurement protocol (tilt test, drop and push tests, M1 to M7), friction two ways, where Isaac's editor shows `dynamicFriction` and what it means here; from W9: a friction measured between two real objects is the pair's, and PhysX combines two materials' frictions (`average` when no mode is authored), so the guide has the user author the measured pair value on both materials, or set a combine mode and author each side to match | all | 6 | 243 | done 2026-11-21: docs/how-to/build-an-indoor-twin.md, with its figure (docs/figures/indoor-twin.typ); the steps whose tools are not built (the fitting tool, the harnesses, the session record) are described as done by hand against the bands |
| W22 | real data for the worked example: a RoboRacer and an indoor field to log M1 to M7 and scan F1. A lab team runs RoboRacers, but we have no access for now (the user, 2026-11-20): features first, real data later | V2, F1 | 3b to 6 | the user | deferred |
| W23 | the synthetic stand-in while W22 waits: "real" logs made by a deliberately perturbed copy of the twin (tyre, mass, component parameters, latency, noise); the fitting tool must recover the perturbation, and the harnesses must pass and fail where they should. Kept afterwards as a regression test | V2, V3, V4 | 3b, 6 | 118 | done 2026-11-21 (`scenarios/projects/roboracer` README, `tools/w23_regression.sh`): the protocol (M1 to M6, plus M1c for the current limit), a stand-in VESC component, the generator writing the real car's rosbag2 with the truth sealed, the 5.3 harness (W11 (b)'s first cut), the session file (W12's first cut). Blind: p1 (all in the model) is recovered 15 of 15 within tolerance and the fitted twin passes 108 of 110 bands (unfitted 38); p2 (latency jitter, a 5 mm reference) shows the degradation: the latency biased +6 ms, and the twin in the loop bending the tyres to pass 102 of 110 bands. vesc_msgs from f1tenth/vesc 153998d. NAS `2026-11-21 091 W23 synthetic stand-in (118)` |
| W24 | the spec's contact properties, optional (absent: today's behaviour, every spec_hash unchanged): per-axle tyres (`tires.front`, `tires.rear`: friction and stiffness, W8) and the body's contact material (`body.contact`: restitution, friction, combine mode, W9), applied by aib's rig at creation and by the surface layer per wheel; CARLA maps per-axle tyres per wheel and names `body.contact` as not applied (refusing it would fail generation for every spec that sets it); 241 reviews the format | V1, V4, F3 | 3 | 118 | done 2026-11-20: optional `tires.front`/`tires.rear` and `body.contact` (sim_vehicle_spec 01797ee, aib 441a883, sim_vehicle_ecu 3e5dd52, scensim_isaac_world e3b4a33; pins 3accb188); every shipped hash and rig unchanged, the Model 3's steptest identical. CARLA takes the tyres per wheel and names `body.contact` as not applied: `testbench check` notes it, the stack's start names it, and `provenance.not_applied` keeps it. On Isaac the spec-written NUC7 fit equals W8's setter run exactly. Follow-up: scensim_carla_world to log the 0.9.16 file's not_applied |

Order: W3, then W5 to W8 (the car on Isaac) beside W13 to W17 (the field), then W10 to W12
(fitting and validation), then W18 to W20 (the stack), then W21. W22 gates the real-data checks
of 3b to 6; until then W23 stands in for them.

### W23 and W10: the plan (118, 2026-11-20)

The rule: the synthetic logs have the format the real logs of W22 will have, so W22 later
swaps data, not code. The stand-in's pieces, in order:

1. **The protocol.** The manoeuvres of design note 5.2, M1 to M6, as a file of VESC command
   sequences (motor speed, current or brake, and servo position, over time). The real car runs
   them with a small driver node publishing the same commands, and the generator below runs
   them too.
2. **A stand-in component.** A VESC drive model with its parameters exposed in `params`:
   - the motor's ERPM per m/s, its current limits and its speed loop's gains;
   - the servo's gain and offset, and its rate;
   - the command latency.

   It lives in `scenarios/projects/roboracer` as an example of a user's component, not a
   shipped one (091 leaves the car's model to the user).
3. **The generator.** It drives the twin on Isaac through the protocol, from aib's vehicle and
   the component with no ROS, as `tools/smallcar.py` does. The perturbed copy changes the tyres
   per axle (W24's keys), the mass, the component's parameters and the latency. It writes each
   repetition as the real car's rosbag2 (sqlite3):
   - the commands;
   - `sensors/core` (vesc_msgs);
   - `sensors/imu/raw`;
   - the reference pose, with the reference's noise.

   Beside each bag goes a session file: the manoeuvre, its condition and repetition, the battery
   voltage, the floor, the tyre age, and the reference's kind and noise. That file is the first
   cut of W12's schema. The repetitions differ by their noise seeds, five per condition, as 5.3
   asks.
4. **The quantities and the bands.** These read bags, real or synthetic, and give M1 to M6's
   quantities and 5.3's verdict per quantity and condition: the first cut of W11 (b).
5. **The fitting tool (W10).** It reads the same bags and the same session files. Tyre
   identification comes first, from M5 and M6, through `tools/single_track.py` and
   `tools/tyre_compare.py` (W8). Then the mass, the component's parameters and the latency are
   fitted by the long-horizon error from matched starts, on Isaac.
   **The drift rule** (133, 2026-11-21, from W23's p2): the tool reports each parameter's drift
   between the stage fit and the refined fit, and flags any parameter the refinement moves
   beyond its stage estimate's interval. A pass with flagged parameters is not a good fit: it
   says the model cannot hold the car, and the parameters are bent to make up for it.

### W10: findings (118, 2026-11-22)

What W10's first runs showed, on W23's stand-ins (p1, p2), and what changed because of it:

1. **The latency is not identifiable from the twin's cost.** At the stage's tyres the cost
   falls steadily with latency for p1 (2.666 at 24 ms to 3.089 at 54 ms, no minimum inside) and
   is flat for p2. With the tyres refitted at each latency it is flat for both (p1 0.013 to
   0.022 from 24 to 54 ms). The twin prefers a latency far from the drive unit's replay (p1's
   42 +- 1 ms), making up for the tyres. So the latency comes from the drive unit's stage and is
   held in the refinement.
2. **The twin's cost has a valley** along the rear stiffness against the rear friction: p1's
   refitted end points run from (rear stiffness 17.8, friction 1.08) at 24 ms to (14.7, 1.31)
   at 54 ms, against the stage's (20.57, 0.896). A refinement with both free slides along it.
   W23's p2 rear friction at 0.717, below what its logs show, and the 54 ms point are its
   examples. The refinement now changes only what the stages leave open, and the tyres are fitted
   axle by axle from the manoeuvre that shows each: the stiffness from the linear range, the
   friction from the limit.
3. **The stage's interval was about 50 times overconfident.** The jackknife gave the rear
   stiffness +-0.13 %; against known tyres the stage's estimate was 5 to 15 % off on the
   stiffness and 5 to 12 % on the friction. Three causes were found and fixed:
   - PhysX adds the lateral slip denominator to the contact's speed (`computeLateralSlip`), so
     the twin's force per slip angle was the tyre's times v / (v + 0.25), 0.80 at 1 m/s. The
     RoboRacer's denominator is 0.05 now (the user's decision); its circles moved under 1.5 %.
   - The synthetic reference pose led the path by half a physics step, so the sideslip read from
     it was r dt / 2 short (9 % at small slip). twin_runs.py writes it without the half step; a
     real car's pose has no step.
   - The tyre stage now inverts PhysX's own tyre (the Michigan model, with the denominator and
     the lateral load transfer) instead of a curve measured at one stiffness. On a real car it
     fits PhysX's tyre parameters, not the real tyre's, and its residual per manoeuvre is the
     model-form error.
4. **The rear's limit was never in the logs.** On a car that understeers, M6's slide is the
   front's. M6b (a brake in a turn) brings the rear to it, and the real car's M6b runs are still
   to be collected.
5. Two Kit instances hung on GPU memory when 8 to 10 ran at once; each twin run now has a time
   limit and one retry.
6. **p3, the blind check.** Drawn by `tools/draw_perturbation.py` on 2026-11-22 for W23's
   regression at the new denominator (118's `isaac-ex/w23reg3`), sealed before any fit; its
   file's sha256 is `1f33818133e947aa22e428695a016fe31673f2a0c973a9b7b75ad070917ebb9f`, so the
   truth the recovery check reads can be checked against what was drawn.
7. **The development set and the test.** p1 and p2 are the development set: the method was
   tuned on them, and their truth is in the repository. p3 is the only held-out test. Changes
   made after seeing a development result, with the date:
   - 2026-11-22: M5 gives the sideslip at the reference. p1 at the new denominator showed the
     stiffness pass, on the circles' radius and yaw rate alone, moving the rear stiffness from
     the stage's 19.91 (truth 19.30) to 25.40: those see only the balance of the two axles'
     stiffness. The sideslip is the rear's own slip. p1's run without it is kept beside the
     rerun (`p1_before_sideslip`).
   - 2026-11-22: a friction the logs leave unidentified starts the refinement at its lower
     bound. With the sideslip, p1's stiffness came within 2 % and its front friction within
     0.3 %, but the rear friction stayed at the stage's meaningless 2.12 (truth 1.19): above the
     limit the twin's cost is flat in it, and M6b is most sensitive just above the bound.
   - 2026-11-22 (133): a refined parameter counts as identified only if the twin's cost pins
     it: probed at -/+10 % around the best, the cost must rise on both sides by more than the
     search's resolution. A friction that fails is reported as at least its lower bound, with
     the note that M6b did not constrain it.
8. **Method v1, frozen for p3 (2026-11-22).** p3 is fitted with exactly what is committed. Two
   known gaps, recorded before its fit:
   - The drive unit's stage can put the latency 10 ms short (p2: 20 ms, truth 30, with jitter
     the model does not hold). The refinement holds the latency, so the gap stays.
   - A biased friction minimum. The probe tells a pinned parameter from a flat cost, not a
     biased minimum from the true one: p2's rear friction is pinned at 0.92 (truth 1.0), most
     likely bent by the latency gap through M6b's brake timing. The warning sign is the friction
     pass's residual, its best cost: above 1.0 (the M6 and M6b quantities on average at their
     band's edge), a refined friction is reported as suspect. p1 at 1.52 (its rear friction stuck
     at the stage's value, before the lower-bound start) and p2 at 1.76 are both above.
   Fixing the latency stage is method v2, tested on a newly sealed p4, so p3 stays a clean test
   of v1.

The exit (133, 2026-11-20):
- The fit recovers each deliberate perturbation within a stated tolerance: the tyre per axle,
  the mass, the component's parameters, the latency and the noise.
- The harness fails the unfitted twin where the perturbation shows, and passes the fitted one.

The bags need f1tenth's `vesc_msgs` in the ROS environment that writes and reads them, as the
user's own stack has it.

## Not in scope

- Shipping a RoboRacer control model: the user owns it.
- CARLA for the indoor field: Isaac only.
- Building the user's field: they author it; scensim loads it.

## Open questions

- Which open RoboRacer stack is the reference for step 5? Answered: f1tenth_system,
  `humble-devel` (133, 2026-11-20).
- The physics rate: does a 1/10 car need more than 100 Hz substeps, and what does that cost?
- Does a user component need ground truth? Answered (the user, 2026-11-20): the car's own
  sensors by default; ground truth only as declared, and only what the user also measured on
  the real car, delivered with its latency and noise (design note 2.4).
