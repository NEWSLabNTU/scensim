# 189: Isaac reports a hard ego-pedestrian contact where SSv2's boxes leave about 1.5 m

**Status:** open, a record (243; numbered by 133, 2026-11-26); no investigation yet.
**Severity:** high. On Isaac a run can be judged `passed` over a real collision: the world
server's physics stopped the ego dead against a pedestrian, with an impulse of 5.5 and 7.6
kN s, while SSv2's `CollisionCondition`, which judges by the scenario's declared boxes, never
fired, since those boxes were still about 1.5 m apart. Any Isaac verdict that rests on SSv2's
collision (a scenario's contact failure, a judge's "no collision") can therefore read clean
when the simulated car struck something. CARLA is not known to be affected; not looked at.
**Found:** 2026-11-26, scensim 243, 092 K9f-a's exit run 2 (k9f_zones, Isaac Sim 6.2).

## What happens

In both cases of K9f-a's exit run 2 (`/var/tmp/aeon/k9fa-logs/k9f_zones/runs/`,
`2026-11-26T05-50-10_goal_stop_goal_surface-asphalt_r0` and
`2026-11-26T05-52-05_goal_stop_goal_surface-ice_r0`; scensim 72a629ea's build, roadmap 092,
K9f-a), the Autoware ego drives west along Town01's y -130 street and a pedestrian darts into its
lane at x 112. In both:

- the truth (the gap trace) has a `contact` with `ped`, `other_type` pedestrian, at the frame the
  ego's speed falls to zero within one 0.15 s window: asphalt frame 516, impulse 5470.5 N s
  (from about 3.5 m/s); ice frame 482, impulse 7595.5 N s (from about 4.3 m/s). Later frames
  carry small or zero impulses;
- at that frame the ego's body pose (`sim_pose`) is at x 116.1, and the pedestrian is at
  x 112.0, y about -129.5, on the ego's lane. With the Model 3's 4.7 m body box, its front is
  near x 113.8; the pedestrian's declared box is 0.6 m square. The boxes SSv2 judges are about
  1.5 m apart (not yet computed exactly with the origin offsets; `scensim.truth.closest` does);
- SSv2's `CollisionCondition` (ego with `ped`, the scenario's exitFailure) never fired: both runs
  `passed`.

So something in the Isaac world is larger than the declared boxes: the pedestrian's collider,
the car's, or both.

## What to look at (not done yet)

`scensim.truth.closest` on both runs, for the boxes' exact gap at the contact frame; the
pedestrian's and the car's colliders in the Isaac stage against their declared boxes; whether
CARLA shows the same with the same scenario; and which verdicts in past Isaac runs rested on SSv2's
collision alone.

## Step 0: what the code says (241, 2026-11-26; static, CPU only, no Isaac run)

**Where Isaac's colliders come from.** Both are the scenario's declared boxes:

- The ego: `aib.isaac.vehicle.Vehicle` makes the chassis collider a cube of the declared box,
  in base_link's frame (`vehicle.py`, "The chassis: the declared box"), raised clear of the
  road, plus a skid plate between the axles, inside the footprint (roadmap 066 R4).
  scensim_isaac_world passes the scenario's box (`world.py`, "The scenario's declared box is
  the ego's chassis collider"). The car body it wears carries no collision
  (`vehicle_assets.py`: "the meshes carry no collision"). The wheels are PhysX suspension
  queries (raycast or sweep). Their collision group filters only the chassis group, so they
  could meet a pedestrian's box, but the front axle (3.005 m) is behind the box's front face.
- A pedestrian: a kinematic rigid body whose collider is a unit cube scaled to the declared box
  (`world.py` `_spawn`). A CARLA walker, when the asset set has walkers, only dresses it
  (`add_walker_body`, "`collider`, the box, is made invisible"). 241's asset set
  (`SWB_VEHICLE_USD`) has no `walkers/`, so its pedestrians are bare boxes. Whether the walker
  export on 243's host carries a `PhysicsCollisionAPI` of its own is not read yet.

**What SSv2 declares.** The catalog's `tesla_model3` (`sim_vehicle_spec/catalogs/vehicles.xosc`):
BoundingBox centre x 1.416, z 0.744 from the rear axle; length 4.792, width 2.163, height 1.488.
So the front face is 1.416 + 2.396 = 3.812 m ahead of base_link. The pedestrian's box is
0.6 m square, from the record.

**How SSv2 judges a collision.** `CollisionCondition` calls `traffic_simulator`'s
`API::checkCollision`. That is `math::geometry::checkCollision2D` on SSv2's own map poses and
the declared boxes. It is false when the boxes' centres differ in z by more than half their
heights' sum; otherwise it is true when the two 2-D polygons intersect, and touching counts
(`boost::geometry::intersects`). Isaac's contacts never reach SSv2: the bridge does not forward
contacts, and they appear only in the truth (gap trace `contact` records). So SSv2 sees only the
poses: for the ego, the world server's (the bridge's `UpdateEntityStatus` reply); for the
pedestrian, its own. The trace keeps both, `ssv2` and `sim_pose`, per entity per frame.

## Hypotheses and predictions (before any run or computation)

- **H1, the 1.5 m is an arithmetic slip.** The record centred a 4.7 m box on `sim_pose`. The
  ego's box is centred 1.416 m ahead of base_link, so at x 116.1 heading west its front face is
  at 116.1 - 3.812 = 112.29. The pedestrian's box spans x 111.7 to 112.3. *Prediction:*
  `scensim.truth.closest` on `sim_pose` gives a gap of at most 0.05 m at the contact frame
  (asphalt 516, ice 482), with the ego's `origin_offset` 0 in the trace header.
- **H2, Isaac's colliders are the declared boxes**, as above. *Prediction:* the contact frame's
  box gap (H1) is no more than PhysX's contact offset (a few cm). A gap of 0.3 m or more would
  mean a larger collider (a walker export with its own collision, or another prim), and H2 falls.
- **H3, SSv2 did not fire because the boxes never overlapped in its view.** *Prediction:* on
  the `ssv2` poses, the ego and pedestrian polygons are disjoint by a few cm or less at every
  frame from the first contact on: PhysX keeps a kinematic box and the chassis apart by its
  contact offset, and SSv2's test needs zero distance. The `ssv2` ego pose equals `sim_pose`
  within one frame of motion, since the ego is stopped. If they are not disjoint, look at:
  - H3b, SSv2's ego pose lagging or offset from `sim_pose` (a reference-point difference);
  - H3c, the z gate: SSv2's ego and pedestrian centres more than (1.488 + h_ped) / 2 apart in
    z, for example an Isaac ground height not on the lanelet's.

If H1 to H3 hold, the issue is not a larger collider but this: **a physics contact with a
kinematic actor can never make SSv2's geometric overlap test true.** A verdict that rests on
`CollisionCondition` is blind on Isaac to any contact PhysX resolves before overlap. That is
probably also true on CARLA, which this plan does not check. The fix (judge the world server's
contacts, or a tolerance on the gap) is for a later plan, after step 1's numbers.

**H4, the judge that sees physics did not run, or let this contact through.** SSv2's blindness
to simulator contacts is known and designed around (roadmap 021): the bridge writes each ego
run's contacts to a report through the remote backend, so for Isaac too
(`contact_report.rs`, `backend/remote/mod.rs`). `physical_verdict` joins them into the JUnit
result as a `carla_contact` testcase, and in scensim it runs as a judge, reading
`<run dir>/contacts/`. A contact with `ped` at 5.5 kN s should then have failed the run,
unless one of these:
- H4a: K9f-a's testbench does not list `physical_verdict` among its judges, or sets
  `world.contact_report_dir: off`;
- H4b: the run's `contacts/` has no report;
- H4c: the scenario declares `ped` in `csbExpectedContacts`.

*Prediction:* H4a. The runs' reports show no `physical_verdict` judge; `contacts/` holds a report
with the `ped` contact. If so, the gap is in which judges a testbench runs, not in Isaac or SSv2.
H1 to H3 still explain why SSv2's own `CollisionCondition` stayed false.

## Step 1 (CPU only, no Isaac run)

1. Get the two runs' records from 243 on the NAS: the gap traces, the run's scenario and its
   report. I won't touch 243's GPU or its host.
2. `scensim.truth.closest` and `truth.boxes` at each frame around the contact, on `sim_pose`
   and on the `ssv2` poses. Report the gap, the z gate's two sides, and `origin_offset`.
3. From 243 (or the asset index on its host): whether its walker USDs carry a
   `PhysicsCollisionAPI` (`grep -l PhysicsCollisionAPI` over the walker set, CPU only).
4. The runs' judges (their report or JUnit file) and `<run dir>/contacts/`, for H4.
5. Record the results against H1 to H4 here. Then a plan for the remedy and for past Isaac
   verdicts that rested on `CollisionCondition` alone.

## Step 1: the results (241, 2026-11-26; CPU only)

The data: 243's two run directories at `~/nas/home/2026-11-26 189 runs (243)/` (checksums
verified). The script and its output are at `~/nas/home/2026-11-26 189 step 1 (241)/`
(`i189_raw.py`, `i189_step1.out`). The traces are schema 4 (243's branch at 13acc454, not on
main), and main's `gap_trace` reads 1 to 3, so the script reads the JSONL directly. It uses main's
`gap_geometry` for the boxes (`ssv2_box`, `signed_distance`) and SSv2's z test as
`checkCollision2D` has it.

The trace headers: the ego's declared box is centre (1.416, 0, 0.744), dimensions
4.792 x 2.163 x 1.488, `origin_offset` 0, so `sim_pose` is base_link. `ped`'s is centre
(0, 0, 0.9), 0.6 x 0.6 x 1.8, `origin_offset` 0, asset `isaac:box`.

| | asphalt (contact frame 516) | ice (contact frame 482) |
|---|---|---|
| ego `sim_pose` x at contact | 116.116 | 116.125 |
| box gap on `sim_pose`, contact frame | -0.0004 m | +0.0013 m |
| smallest gap on `sim_pose`, whole run | -0.0004 m (frame 516) | +0.0013 m (frame 482) |
| box gap on `ssv2`, contact frame | +0.1010 m (one frame behind) | +0.0040 m |
| smallest gap on `ssv2`, whole run | -0.0001 m (frame 517) | +0.0023 m (frame 483) |
| z separation / SSv2's gate | 0.15 to 0.17 / 1.644 m | 0.14 to 0.16 / 1.644 m |
| speed before / at contact | 3.27 / 0.42 m/s | 4.22 / 0.50 m/s |
| contact report | `ped`, first frame 516, 134 frames, 5470.5 N s, complete | `ped`, 482, 8 frames, 7595.5 N s, complete |
| `csbExpectedContacts` | none | none |
| `result.json` | `passed`, no `judges` key | `passed`, no `judges` key |

After the contact the asphalt ego rests 1 to 2 mm from the box for the rest of the run. The ice
ego bounces back to 5 cm.

**Verdicts.**

- **H1 holds.** No 1.5 m gap exists. The record placed a 4.7 m box centred on `sim_pose`, which
  is base_link, so it measured from about the box's centre. On the declared boxes the gap at
  the contact frame is -0.4 mm (asphalt) and +1.3 mm (ice).
- **H2 holds.** The colliders are the declared boxes. Box-to-box at the contact is within 2 mm,
  inside PhysX's contact offset. Nothing larger hit the car. 243 checked on its host: the walker
  USDs carry no `CollisionAPI` or `RigidBodyAPI`, and the trace names `ped`'s asset
  `isaac:box`.
- **H3 holds for ice; asphalt needs a closer look.** On ice SSv2's boxes stay 2.3 mm apart at
  their closest, so `checkCollision2D` was false throughout, as predicted. On asphalt SSv2's view
  shows -0.1 mm, an overlap, at frame 517 (+0.2 mm at 518, then growing to 2 mm). Touching
  counts in SSv2's test, so on these numbers it should have fired at 517. Yet it did not:
  `failures` 0, no exitFailure. A tenth of a millimetre is below what the trace's float32 poses
  resolve, and this alone does not show what SSv2 computed: its own pose, its condition timing
  or its polygon arithmetic.
  - H3b, the lag: SSv2's ego pose is the world server's from one frame earlier (`ssv2` at frame
    n equals `sim_pose` at n-1, 0.17 to 0.23 m at these speeds). It equals it once the car stops.
  - H3c, the z gate: far from tripping (0.15 m against 1.644 m).
- **H4 holds.** The judge that sees physics did not run. Both runs have a complete contact
  report naming `ped`. The scenario declares no expected contact. `result.json` has no judges,
  and k9f_zones' testbench declares none, so `physical_verdict` never read the reports. Had it
  run, both would have failed (`carla_contact`: an undeclared contact with `ped`).

**What this means.** Isaac is not wrong here: the car really struck the pedestrian's declared
box at 3.3 to 4.2 m/s. Neither run's `passed` saw it, for two reasons:

- SSv2's `CollisionCondition` needs zero distance between its own poses, one frame late. A
  physics contact with a kinematic box leaves the boxes millimetres apart: the condition stays
  false on ice, and on asphalt it misses even at -0.1 mm.
- The testbench ran no judge to read the contact report.

The same holds wherever a run's verdict rests on `CollisionCondition` without
`physical_verdict`, CARLA included (not checked here). 190, the gentle braking, is what made the
contact happen. 189 is why the run still passed.

**Next (a plan, for 133).**

1. Which testbenches and past Isaac runs had no `physical_verdict` judge (static, over the
   repository's testbenches and the runs' `result.json`).
2. The remedy. Either `physical_verdict` (or an equivalent contact judge) runs by default in
   scensim whenever the bridge writes contact reports, so a testbench opts out rather than in;
   or `CollisionCondition` is complemented by a judge on the truth's contacts. Plan first.
3. Optionally, why SSv2 missed asphalt's -0.1 mm at frame 517: its logged ego pose, if it logs
   one. It does not change the remedy.

## Step 2: the survey and the remedy, a plan (241, 2026-11-26; CPU only, nothing changed)

**The NTU proof pass (2026-11-05), whose numbers are published.** CARLA 116/116, Isaac
116/116 and Isaac n16 8/8 (NAS `autoveh/dataset/2026-10-30 NTU twin map/proof_2026-11-05/`).
In all three, the pass is SSv2's JUnit alone. CARLA's `legs.log` records only `junit=[failures="0"
errors="0"]`, and each Isaac `<leg>_junit.xml` holds one testcase, SSv2's, with no
`carla_contact`. So `physical_verdict` ran on none of them, and no contact report was kept.

A scan of every leg's 20 Hz state (`~/nas/home/2026-11-26 189 NTU contact scan (241)/`) followed
thresholds and predictions written before it, and was calibrated on step 1's two contacts:
- The thresholds: a one-frame speed drop of 1.0 m/s or more, a lateral acceleration of 8 m/s^2
  or more, and on Isaac a yaw-rate jump of 1.5 rad/s or more.
- Calibration: they fire at frames 516 (2.85 m/s) and 482 (3.72 m/s) and nowhere else.
- The scan found 0 hits in 241 leg files. The largest drop was 0.165 m/s and the largest
  lateral reading 2.62 m/s^2.

That is evidence and not a verdict: a slower touch can't be excluded without the reports. On
it, the published passes hid no hard contact.

**The repository's testbenches** (`scenarios/projects/*`, `src/scensim_examples/projects/*`,
`src/scensim/scensim/templates/*`; the colcon test fixtures left out). With `physical_verdict`
among the judges (12):
- projects: basic, c2b, demo, dev, e2, gap, isaac_demo, s5, set050, set050_tour, two_av;
- examples: safety_suite.

Without it (29):
- projects: bench, courses, drift_lap, gap_campaign, isaac_basic, isaac_road_physics,
  isaac_rough_road, isaac_soil, isaac_t2 (autoware, command, launch_own, none, simple),
  isaac_verge, k12_commanded, k12_commanded_free, k13_platoon, k24_agreement, k9_cs3,
  k9_cs3_isaac, speed_ladder;
- examples: first_drive, isaac_first_drive, multi_pilot, road_physics, simple_drive;
- every template: carla-first-drive, isaac, multi-pilot;
- and 243's k9f_zones, on its branch.

Of those, these judge a collision by `CollisionCondition` alone, as 189's runs did:
isaac_soil (2 scenarios), k24_agreement (2), and the examples first_drive, isaac_first_drive and
multi_pilot. Only 2 scenarios in the repository declare `csbExpectedContacts`. A new project
made from a template runs no contact judge. The gap studies: `gap` runs `physical_verdict`;
`gap_campaign` does not, though it judges by its own oracle and has no `CollisionCondition`.

**The remedy: two options weighed.**

1. *A contact judge on by default wherever the bridge writes contact reports; a testbench opts
   out by name.* scensim would add `physical_verdict` to every run that has `<run dir>/contacts/`
   unless the testbench says otherwise, for example `judges: [{name: physical_verdict, off:
   true, why: ...}]`, refused without a reason.
   - It reuses what exists: the reports (CARLA and Isaac alike, through the remote backend),
     `csbExpectedContacts` for a scenario that means to collide, and `static` for the world.
   - It covers static contacts (a curb, a pole, a rock), which no SSv2 condition can.
   - It is one rule for both simulators.
   - Cost: a run that collides on purpose without saying so starts failing. isaac_soil's and
     isaac_rough_road's rock and verge drives are the likely ones, the car meeting the static
     world. They would need `csbExpectedContacts: static`, or a minimum impulse.
2. *A truth-contact judge beside `CollisionCondition`*: the same entity pairs that SSv2 names,
   judged on the gap trace's contacts or on a gap tolerance (for example, at most 5 cm).
   - It closes exactly 189's case: a named pair that touched in physics.
   - It misses static contacts and unnamed entities.
   - It duplicates `physical_verdict`'s data path with a second rule.

**Recommendation: 1.** It is the judge the project already built for this (roadmap 021); 189's
runs fell through only because it is opt-in.

**The effect on past verdicts.** Nothing is re-judged by itself; the change applies to new runs.
- Past scensim runs that kept `<run dir>/contacts/` can be judged again offline with
  `physical_verdict --contacts <dir>`. That is a report, not a rewrite of their `result.json`.
  It would turn 189's two K9f-a runs into failures.
- Runs without reports (the NTU proof pass) can't be re-judged; the state scan above is what
  there is.

**On CARLA.** The same reports, so the same rule. CARLA's contacts also catch its bodies being
larger than their declared boxes (roadmap 022's 0.3 m tolerance notes). Projects that already
run the judge on CARLA see no change.

**Steps, each with a plan and predictions before code:**
1. A dry pass. Run `physical_verdict` offline over every kept `<run dir>/contacts/` of the
   no-judge testbenches on 241 and the NAS, and list which runs would flip. This is CPU only.
2. The default-on change in `scensim.judges` with its opt-out, plus tests.
3. The templates and examples: add the judge explicitly, so a reader sees it.
4. The scenarios that collide on purpose: declare `csbExpectedContacts`.
5. A full gate (`just check` included, issue 191).

## Step 3: the default-on contact judge, the plan (241, 2026-11-26; before any code)

The user approved it through 133 as a change to verdicts, with four conditions:
- a 10 N·s impulse floor, calibrated against CARLA's kept contact reports too;
- a testbench opts out only by name, with a reason;
- every scensim run keeps its `scenario.xosc` beside `contacts/`;
- the templates and examples carry the judge explicitly.

**What the code does today.**
- A project's judges run after the verdict (`run.py`: `results.verdict_from` at the JUnit, then
  `judges.run_all`). Their records sit beside the run's verdict and never replace it
  (`judges.py`'s docstring). `physical_verdict` edits `junit.xml` in place, but only after the
  verdict has been taken from it.
- So listing the judge today gives `judges: physical_verdict=failed` on a run whose
  `result.json` still says `passed`, with exit 0.
- `scenario.xosc` is written only when a layout or a zone applies (`layouts.write_copy`).
  Otherwise the run keeps only `resolved.yaml`'s path to the source, which is why the
  rear-contact runs in step 2's dry pass had to be re-judged against the source.

**The change.**
1. *The contact check runs before the verdict.* When the run directory holds `contacts/`,
   scensim runs `physical_verdict` on its `junit.xml` before `verdict_from`. A `carla_contact`
   failure then fails the run the way any JUnit failure does, and the reason names the
   contact. This is the place `run_suite --physical-verdict` had (roadmap 021). The run's
   line and `result.json`'s reason say why, for example `failed: undeclared contact
   'ped' (pedestrian) 5470.5 N·s (floor 10)`, and the exit code is the failed run's. The judge's
   record is still written to `judges/physical_verdict.json`, so `scensim` lines and readers
   see it as before.
   - It runs with `--min-impulse 10` and `--scenario <run dir>/scenario.xosc` (point 3).
   - A run with no `contacts/` (no bridge report, as with `logging` off) is not judged. The
     record says why, and the verdict is not changed.
2. *The opt-out.* A project turns the default off only with an entry in its `judges:` list,
   by name, with a reason: `- {name: physical_verdict, off: true, why: "..."}`. An empty
   `why`, or `off` without the name, is refused by `judges.problems`.
   - An entry with `run:` keeps today's meaning. It replaces the default's arguments (its own
     `--min-impulse`, say) and also runs before the verdict, never twice.
   - `off` and `why` become known keys only for that name. Any other judge given them is
     refused.
3. *`scenario.xosc` always.* `write_copy` runs for every run: with no layout and no zone it
   copies the source unchanged, and `resolved.yaml`'s `copy` records its sha256 (equal to the
   source's). The judge reads the copy, so a later offline re-judge sees what SSv2 ran.
4. *Templates and examples.* Each of the 3 templates and the 5 examples without the judge
   lists it explicitly, as `basic` does, with a comment saying it would run anyway. That
   means first_drive, isaac_first_drive, multi_pilot, road_physics and simple_drive.
5. *Scenarios that touch on purpose.* These declare `csbExpectedContacts`, or opt out with a
   reason. From the dry pass, at 10 N·s none is left. town01_rear_contact already declares
   `npc_rear`, and isaac_soil's and isaac_rough_road's static contacts fall under the floor.
   The step lists them, and declares nothing new unless the repeat dry pass finds a run.
6. *Docs.* The design doc's "Results", judges.py's docstring, and the testbench reference.

**The floor: calibration.**

*Isaac.* 47 contact entries in 72 kept run reports (241, step 2's set). Max impulses of the ego's
contacts, sorted:

| contact | max impulse (N·s) |
|---|---|
| the soil meshes' cut strips (`/World/soil/*_road/cut/m0`), static, 20 runs | 0.0 |
| a road rock (`/World/RoadRocks/r128`), rough road, 1 run | 1.1 |
| the pedestrian in 189's two K9f-a runs (goal_stop_goal, asphalt and ice) | 5470, 7595 |
| `npc_rear` in town01_rear_contact, declared, 4 runs | 16431 |

The floor at 10 N·s falls in a gap more than three orders of magnitude wide:
- Below it are the soil strips (a contact with zero impulse, the car resting on the mesh it
  drives over) and one rock graze.
- Above it is every contact a scenario author would call a collision.

The soil strips are step 2's "soil-mesh handling": the floor covers them, and no
`static` opt-out is needed for them.

The NPCs' own contacts on soil (`npc_contacts`, 111 to 1426 N·s) are not judged. The judge
reads only the ego's.

*CARLA.* None exist. Every kept CARLA contact report is empty:
- on 241 and the NAS, 11 runs (243's k10/k12 cs1 and k13 platoon);
- on 118, 11 (carla_verge, first_drive, my_first_drive, my_tb).

- 243 has 7 kept CARLA runs from issue 073 (2026-11-20) with one contact each: six s5 v10
  gap-sweep runs over several builds, and one basic town01_rear_contact. They are on 243's
  disk. Their impulses go here when 243 copies them.

Two fresh CARLA runs, approved by 133, calibrate it on CARLA directly:
- basic's town01_rear_contact (the declared contact);
- a drive past a static object close enough to touch it.

They run when a GPU is free without displacing P1 or anyone else. At 10:14 both of 241's
GPUs were at 99 to 100 % (P1 on GPU 0, and two other users). Their impulses are recorded
here before the code lands. Until then the floor is 10, per 133's condition.

CARLA's collision sensor reports a normal impulse in N·s from its PhysX, so the unit is the
same. The prediction: a CARLA touch lands well above 10 N·s (hundreds or more), and a static
touch at walking speed lands above it too.

**Predictions, before code.**
- The unit tests (new):
  - the default runs before the verdict and fails a run with an undeclared 16431 N·s contact;
  - it passes one with a 1.1 N·s rock and the 0.0 soil strips;
  - an `off` entry without `why` is refused;
  - `off` with `why` skips the judge and records the reason;
  - a `run:` entry replaces the default and runs once;
  - `scenario.xosc` exists for a run with no layout, with the source's sha256.
- The step 2 dry pass, repeated at `--min-impulse 10` on the same 72 reports:
  - the soil strip and rock runs flip to pass;
  - the four rear-contact runs pass with the source scenario's declaration of `npc_rear`;
  - 189's two K9f-a runs fail. No other run fails.
- A failed run's line names the contact, its impulse and the floor.
- `just gate` on the change: ok on 241 with the Isaac lane run.
- No CARLA run is needed for the gate. The first CARLA project run after landing shows
  `judges: physical_verdict=passed` with "no unexpected contact".

## Step 3: 243's review and 133's rulings (241, 2026-11-26; before the gate)

243 reviewed aa3faf25 (CPU only). Its tests passed there. 133 ruled on the findings, and all
are in this commit:
1. *The floor applies to static contacts only.* At aa3faf25 it filtered every contact. An
   undeclared pedestrian touch at 5 N*s, or at 0.0, passed. Every sub-floor entry in the
   calibration is static: the soil strips at 0.0 and the rock at 1.1. Every actor contact is
   at least 4611 N*s (CARLA 4611 to 12112, Isaac 5470 to 16431). An actor contact now fails
   at any impulse unless declared. `--min-impulse` is documented as the static world's floor.
   The 5 and 0.0 pedestrian probes are tests that must fail. This is stricter than the
   literal "10 N*s floor", in the safe direction; 133 tells the user.
2. *A missing report is an error, not "off".* At aa3faf25 a run without a report in
   `contacts/` was recorded `off` and kept SSv2's verdict, so a bridge that failed to report
   could hide a hit. Now, where the stack collects reports (the world's `contact_report_dir`
   unset), the judge runs anyway, and physical_verdict's NoContactReport makes the run an
   error. "off" stays for two cases:
   - the project turned the judge off by name;
   - the world reports nothing scensim can read (`contact_report_dir` off or the user's). The
     run's line then ends `WARN physical_verdict: not judged: ...`.
   No world server declares a contact capability in its Hello, so the world's
   `contact_report_dir` is the declaration. scensim's test fakes of SSv2 now write the report
   a real bridge writes.
3. *`on`, `needs` and `timeout` are refused on the contact judge.* It always runs, before the
   verdict. An `off` entry takes only name, off and why.
4. *The reason's first line names at most 3 contacts*, then "+N more".

243's other notes are recorded, with no change:
- A CARLA restart mid-run (IncompleteContactReport) is an `<error>`, so it masks an SSv2
  failure in the same run. It is an error run either way.
- CARLA's `type` is a blueprint and Isaac's a class, which the judge does not filter on.
- The judge reads csbExpectedContacts' default in the scenario, so a knob that overrides the
  parameter is not seen. That predates this step.

**Predictions, before the runs:**
- The dry pass over the same 72 reports with this physical_verdict, at `--min-impulse 10`,
  gives the same 70 passes and 189's two failures. No actor contact in them is under 10.
- 243's 7 CARLA runs give the same verdicts as before.
- `just gate` passes on 241, with the Isaac lane run.
