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
