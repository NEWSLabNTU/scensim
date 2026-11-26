# 182: after it sees the boulder, the ego creeps into it and strikes repeatedly instead of holding a stop

**Status:** open; plan written (2026-11-25), for 133. Kept apart from issue 181: this is planning and
the system's emergency handling, not perception. **Severity:** to be judged in the plan.
**Found:** 2026-11-25, scensim 118, 086 C6e3 run b2 (numbered by 133).

## What happens

In b2, after the strike on the 35 cm boulder at 0.77 m/s (issue 181), the car's truth trace
shows a cycle that lasts until the scenario's timeout. The car stands still, moves off at up to
about 0.8 m/s over 0.5 m, strikes the boulder and stops dead again. The origin moved from
x 396.43 to 396.94 in the first cycle and stayed there. y drifted 1.70 to 1.89 m over about 500
s, as the car slid sideways along the rock.

What the planner and the system did, from the ego stack's logs (`logs/pilot-ego/`). The run's
record has no planning or diagnostics topic: no velocity factors and no stop reasons were
recorded.

- `system.mrm_handler`: "EMERGENCY_STOP is operated." 844 times and "EMERGENCY_STOP is
  canceled." 844 times. The first was at wall time 1795595949.7 and the last at 1795596456.7
  (507 s). Gaps between operations were under 5 s except 4. The first came 107 s after the ego
  stack's nodes started, consistent with the strike at sim time about 99.8 s. That holds if sim
  time ran near wall time; it is not aligned exactly.
- `control.vehicle_cmd_gate`: "Emergency!" 344 times.
- No log line names what raised the emergency. mrm_handler logs only that it operates.

## Why (a hypothesis, untested)

A diagnostic toggles with the car's distance to the boulder. For example, `control.collision_detector`
(loaded in this stack) raises an error when obstacle points are within its margin of the
footprint, so the MRM stops the car. When the error clears the MRM cancels, and the planner's
stop for the boulder, which issue 181 says is late or absent, does not hold the car, so it
moves off again. The planner's own stop never held.

## Steps (predictions written before each, when taken up)

1. Rerun b2's approach with `/planning/velocity_factors`, `/system/fail_safe/mrm_state`,
   `/diagnostics` and the emergency's source recorded, and name what raises and clears it.
2. A plan for 133: what holds the stop (the planner's obstacle stop, or the MRM's hold).

## The plan (written 2026-11-25, before any run; for 133)

**The run.** The same run as issue 181's step 1 (fixture_c6b, the boulder at s 400), whose
record adds, for this issue: the MRM's state (`/system/fail_safe/mrm_state`), the system's
diagnostics (`/diagnostics`; and the diagnostic graph's, if the stack publishes it), the
planning's velocity factors and stop reasons (`/api/planning/velocity_factors`, and
`/planning/scenario_planning/status/stop_reasons` if published), the collision detector's
output, the control command (`/control/command/control_cmd`) and the vehicle command gate's
emergency state. The names are checked against a live stack before the run, as for 181.

**Predictions (before the run).**
- The MRM operates and cancels about once a second for as long as the ego sits at the boulder
  (b2: 844 times in 507 s).
- *Hypothesis H1 (182's own):* a diagnostic that follows the distance to the boulder raises
  and clears the emergency. The diagnostic that turns to ERROR each time just before
  "EMERGENCY_STOP is operated" is `collision_detector`'s, and it turns back to OK as the car
  backs off or stops pushing.
- *Hypothesis H2:* the planner never stops for the boulder. The velocity factors hold no
  obstacle stop at the boulder in any frame of the creep, which follows from issue 181 if the
  object is lost when the car is at it, so the planner asks to move each time the MRM releases.
- If the velocity factors do show a stop at the boulder and the car still creeps, the cause is
  in control (the stop is not held at 0 m/s), and the control command's acceleration shows it.

## Step 1's result (2026-11-25, run r1, after the predictions above)

The same run as issue 181's step 1 (its result section has the run's identity and the NAS copy).
The ego struck the boulder at sim 1032.75 s and **did not creep this time**. Base_link stayed at
x 396.9 to within 0.1 m for the 117 s after it. Contact was continuous (2488 contact reports,
max impulse 2327 N s). The wheels' reported speed had a median of 0.000 m/s, and a maximum of
0.016 m/s. So this run held the car against the boulder. b2's creep, which ran from a start at
x 20, was not reproduced, and the record is of a car pushing, not one moving.

Against the predictions:
- The MRM operates and cancels about once a second: **held**. It operated 95 times (state
  OPERATING, behavior EMERGENCY_STOP), with a median gap of 0.7 s between operations, 94 of them
  after the strike.
- H1, `collision_detector`'s diagnostic: **FAILED**. Its level changed twice, both at start-up
  (ERROR, then OK "vehicle is stopping"). It was OK through every operation.
- H2, the planner never stops for the boulder: **held** as far as the record shows. The velocity
  factors held only `route-obstacle` (5 messages in all). obstacle_stop's planning factor was in
  11 of 1508 messages. After the strike the control command asked for 0.25 m/s at +0.51 m/s^2 in
  every sample.

Found, not predicted (an association, NOT a tested cause; *hypothesis H3*): in 93 of the 94
operations after the strike, `/diagnostics` carried `localization: ekf_localizer` at WARN
("mahalanobis distance of pose topic is large") about 0.15 s before the MRM operated (56.64 s
before 56.80 s, 68.29 s before 68.48 s, 72.93 s before 73.08 s, and so on). Outside those windows
it was at WARN in 3 of 1579 samples. The system's hazard status reported an emergency only at
start-up and from 27.6 s to 30.4 s, around the strike, so it does not record the 94 later
operations' cause. The diagnostic graph had `/autoware/localization/accuracy` and
`/localization/state` at ERROR in 60 and 61 messages. H3: with the car pressed against the
boulder, NDT's pose and the EKF's prediction disagree, the EKF gates the pose, localization's
accuracy goes to ERROR, and the MRM stops the car, then cancels when the next pose passes.
Not tested: what NDT reports in those frames (iteration_num and NVTL are recorded), and whether
the MRM's input is the graph's localization node.

## H3's offline check (asked by 133; predictions written before it, 2026-11-25)

From run r1's record alone, no new run. For each of the 94 operations after the strike, the
0.15 s (and 0.5 s) before it, against the same measures in the quiet stretches between them:

- NDT's `iteration_num`, its NVTL, and the covariance of its pose
  (`/localization/pose_estimator/pose_with_covariance`, if recorded; else from the EKF's input as
  far as the record has it), against the EKF's own pose (`/localization/kinematic_state`).
- The vehicle velocity the EKF fuses (`/vehicle/status/velocity_status`, through the twist
  converter), against NDT's pose's motion.
- Which diagnostic input the MRM handler acts on: read from the diagnostic graph's configuration
  as installed in Autoware 1.5.0 and the profile (`/autoware/modes/autonomous` and what it links
  to), and the graph's recorded `struct` and `status`.

**Predictions (before the check).**
- P1: pushing against the boulder makes NDT and the EKF disagree. In the 0.15 s before an
  operation, NDT's pose (or, unrecorded, the EKF's pose as NDT pulls it) jumps by more than the
  EKF's gate allows, while the fused wheel speed is 0 m/s. In the quiet stretches the two agree.
- P2: NDT itself is worse in those frames: more iterations (toward the limit) or a lower NVTL
  than in the quiet stretches. The boulder in front of the car hides part of the scan, or the
  car's body moves on its suspension while the wheels are held.
- P3: `/autoware/localization/accuracy` (or `/localization/state`) goes to ERROR just before each
  operation. Through `/autoware/modes/autonomous`'s links, the graph makes the autonomous mode
  unavailable, and the MRM handler operates EMERGENCY_STOP; it cancels when the next pose passes
  and the node returns to OK. So the loop is: push, disagreement, accuracy ERROR, stop, cancel,
  push again.
- If P1 fails (no disagreement before the operations), H3 is not the cause, and the WARN is a
  result of the stop, not its source; the order of the WARN and the operation in time is then
  read again at the record's resolution.

### H3's offline check: the result (2026-11-25, after the predictions above)

Read from r1's record (scripts `h3.py`, `g3.py`). There are 94 operations after the strike. A
quiet stretch is any time more than 1 s from an operation and more than 34 s into the run. NDT's
own pose (`/localization/pose_estimator/pose_with_covariance`) was not recorded, so its
disagreement with the EKF is read from the EKF's gate (its diagnostic) and the EKF's outputs.

| measure | the 0.15 s (graph, diagnostics: 0.5 s) before an operation | quiet |
|---|---|---|
| `ekf_localizer` diagnostic at WARN, "mahalanobis distance of pose topic is large" | 93 of 94 operations | 0 of 863 messages |
| graph `/autoware/localization/sensor_fusion_status` at WARN | 93 of 94 | 0 of 432 |
| graph `/autoware/localization` and `/autoware/modes/autonomous` at WARN | 94 of 94 | 0 of 432 |
| graph `/autoware/localization/accuracy`, `state`, `scan_matching_status` at ERROR | 0 of 94 | 0 of 432 |
| `localization_error_monitor` (`ellipse_error_status`) | OK in every message | OK |
| NDT `iteration_num` of 10 or more | 43 of 94 operations | 86 of 865 messages |
| NVTL below 3.25 | 1 of 94 (min 2.77) | 0 of 865 (min 3.26) |
| the wheel speed the EKF fuses, abs, p50 and max | 0.0004, 0.014 m/s | 0.0003, 0.016 m/s |
| the EKF's pose step per message, p50 and max | 0.47 mm, 9.1 mm | 0.45 mm, 9.5 mm |
| the EKF's pose variance in x, p50 | 0.0021 m^2 | 0.0020 m^2 |

The graph's configuration is the profile's (`autoware_sim_profile`
`config/system/diagnostics/autoware-sim.yaml`, its `diagnostic_graph_path` default under NDT).
`/autoware/modes/autonomous` is the `and` of map, localization, planning, perception, control and
vehicle. `/autoware/localization` is the `and` of `state`, `scan_matching_status`, `accuracy`
(`localization_error_monitor: ellipse_error_status`) and `sensor_fusion_status`
(`localization: ekf_localizer`). The MRM handler reads `/system/operation_mode/availability`
(Autoware 1.5.0's `mrm_handler.launch.xml`), which the graph's modes give.

Against the predictions:
- P1, NDT and the EKF disagree while the wheels say 0: **held, as far as the record shows it**.
  The EKF's gate refused NDT's pose before 93 of the 94 operations and never in the quiet
  stretches. The fused wheel speed was about 0 m/s in both. The EKF's own output did not jump,
  as it would not if it refuses the pose. How far NDT's pose was from the EKF's is not measured
  (NDT's pose not recorded).
- P2, NDT worse in those frames: **partly held**. NDT took 10 or more iterations before 43 of the
  94 operations, against 86 of 865 quiet messages. NVTL was not lower: below 3.25 once.
- P3, `/autoware/localization/accuracy` goes to ERROR: **FAILED**. No localization unit was at
  ERROR before any operation, and the error monitor was OK throughout. The path in the record
  is a WARN instead. `sensor_fusion_status` (the EKF's own diagnostic) at WARN made
  `/autoware/localization` and `/autoware/modes/autonomous` WARN before every one of the 94
  operations, and never in the quiet stretches. That the graph's WARN takes the autonomous mode
  out of the availability the MRM handler reads is inferred from this timing, not read in
  Autoware's code (a binary install).

So the loop the record shows is this: the car pushes against the boulder with the wheels held;
the EKF refuses NDT's pose as an outlier (its diagnostic WARN); the graph's localization and
autonomous mode go to WARN; the MRM operates EMERGENCY_STOP; it cancels when the next pose
passes the gate (the median gap between operations is 0.7 s); the planner, which holds no stop
for the boulder (H2), asks to move again. The planner's missing stop (issue 181's detection
late and lost at the car) is what keeps the loop going. The MRM's stop is what ends each push.
Why NDT's pose leaves the EKF's gate while the car is held (the scan with the boulder at the
bumper, or the body moving on its suspension) is not settled by this record. Recording NDT's
pose and the EKF's innovation would settle it.

**Next step (133, 2026-11-25; not now).** Why NDT's pose leaves the EKF's gate while the car is
held: on a future fixture run, record NDT's pose (`/localization/pose_estimator/pose_with_covariance`)
and the EKF's innovation, and read the pose's jump against the scan at those frames.

## Step 2: why no stop holds, and the 181 change's live run as its test (241, 2026-11-27; a plan, before any run)

133 handed 182 to 241 after 181's change (2026-11-27). 181's record so far:
- the boulder is validated from 9.6 m (base_link to the rock), and in the final objects from
  8.2 m;
- with the profile's validator change (UNKNOWN threshold 5) it is validated from about 12.1 m;
- at about 3 m, after the strike, no stage has it (at most 1 non-ground point a frame).

**What reading the parameters and the car gives (no run):**
- *obstacle_stop* (motion_velocity_planner, autoware_launch's `obstacle_stop.param.yaml`, the
  profile's default):
  - it stops `stop_margin` 5.0 m before an obstacle (`min_stop_margin` 3.0 m for UNKNOWN when
    that cannot be had);
  - it holds a stop while the ego is under 0.01 m/s and the stop point moves less than 0.3 m;
  - it keeps a lost stop obstacle for `stop_obstacle_hold_time_threshold` 1.0 s.
- *The lidar's near blind zone:* the spec's sensor kit puts the OS1 at x 0.9, z 2.0 (base_link),
  the front bumper at x 3.72 (wheel base 2.875 plus front overhang 0.841).
  - Isaac's OS1 REV7 sees down to -22.5 degrees, so the top of a 0.35 m rock is in view only
    beyond 1.65 / tan 22.5 = 3.98 m of the lidar.
  - That is 4.9 m from base_link, or **1.2 m ahead of the bumper**. Closer, it is in no scan.
    The spec's CARLA figure of -25 degrees gives 4.4 m from base_link.
- *So, H4 for 182:* r1 and b2 first had the boulder as an object only 4.3 to 4.5 m ahead of the
  bumper, already inside the 5 m stop margin, too late to stop short. The car reached the
  boulder, and there the boulder was in the blind zone, in no stage. obstacle_stop's 1 s hold
  ran out, the planner asked to move (H2, held in step 1), and only the localization-driven MRM
  (H3) ended each push.
  - With the boulder seen early enough to stop more than 1.2 m short of the bumper, it would
    stay in view, obstacle_stop would keep its stop, and nothing would creep.

**Step 2a, CPU, from r1's record (before the live run).** The timeline near the boulder:
- the final objects at the boulder, by base_link range;
- obstacle_stop's planning factor (the 11 messages): when each came, and its stop distance;
- the control command's velocity and acceleration;
- the last frame with the object before the strike, and the first after.

Predictions:
- the planning factor appears only in frames where the final objects hold the boulder, within
  0.2 s of them;
- its stop point lies behind the ego, the margin already lost;
- the last object frame before the strike is at a base_link range of 4.5 m or more, near the
  blind zone's 4.9 m; after the strike, none.

**Step 2b, the live run (118's run on the 181 change's pins, the same run as 181's
confirmation; C6e3's c6b, started from x 320 as r1).** It records 182's topics as r1 did, plus
the planning factor of obstacle_stop and `/planning/scenario_planning/trajectory`'s velocity.

Predictions:
- the boulder is in the final objects from about 11 to 12 m (validated 12.1 m, tracking's
  confirmation after);
- obstacle_stop's factor follows within 0.5 s, and the ego brakes;
- **no strike.** The ego stops with its bumper 1.5 to 5 m short of the boulder: short of the
  5 m margin, because 4.2 m/s over about 3 m needs more than obstacle_stop's deceleration, but
  outside the 1.2 m blind zone;
- stopped, the boulder stays in the final objects in at least 80 % of the frames, and
  obstacle_stop's factor in at least 80 %;
- the ego does not move again: the base_link speed stays under 0.05 m/s for the rest of the run;
- the MRM operates at most a few times, not about once a second as in r1. With no contact
  pushing the car, the EKF's gate has nothing to refuse (H3's loop needs the push).

The least sure part is where it stops (about 50 %). If obstacle_stop cannot plan a stop that
late and lets the car through, the strike comes at a lower speed, and H4's other half (the blind
zone) is then tested by whether the object comes back once the car backs off. It cannot back
off, so it would not come back.

**Not in this step:** why NDT's pose leaves the EKF's gate while the car pushes (step 1's open
question; 133: on a future fixture run, record NDT's pose and the EKF's innovation). If the
live run has no push, the question does not arise there.

### Step 2a's result (241, 2026-11-27, after the predictions above)

`s2a182.py` on r1's record (NAS `home/2026-11-27 issue 181 replay (241)/`). Times are relative
to the strike (base_link at x 396.5). The gap is bumper to rock (base_link range less 3.72 m).

| time | base_link range | gap | ego speed | |
|---|---|---|---|---|
| -3.95 s | 8.18 m | 4.47 m | 3.88 m/s | the boulder first in the final objects; obstacle_stop's first factor |
| -3.95 to -2.95 s | | | 3.88 to 2.14 | 11 factors, STOP, the stop point at x 390.7 to 391.0, 1.3 to 4.1 m **behind** the ego |
| -2.95 s | 5.06 m | 1.35 m | 2.25 m/s | the last frame with the object, and the last factor |
| -2.95 to 0 s | | | | no object, no factor; the 1 s hold runs out |
| 0 s | | | | the strike |

- The control command's acceleration went down to -2.50 m/s^2 before the strike, the planner's
  floor.
- After the strike, it asked for 0.25 m/s at +0.51 m/s^2 (median).
- The stop point is the boulder less the 5 m margin less the front: 400 - 5.0 - 3.72 = 391.3.
  It is behind the ego from its first message.

**Against the predictions:**
- The factor appears only with the object, within 0.2 s: **held**, 11 of 11.
- Its stop point lies behind the ego: **held**, by 1.3 m at the first message and 4.1 m at the
  last.
- The last object frame before the strike is at 4.5 m or more, near the blind zone's 4.9 m:
  **held**, 5.06 m (gap 1.35 m, against the 1.2 m computed). None after the strike: **held**.

So r1 shows H4's mechanism:
- the boulder was an object for 1.0 s, while the ego braked at the planner's -2.5 m/s^2 floor
  from 3.9 to 2.1 m/s;
- it left every stage at the blind zone's edge;
- obstacle_stop's hold ended, and the ego rolled on into it.

Step 2b tests the other half: seen early enough, it stops short and holds.

### Step 2a corrected: the MRM braked, raised by AEB, not the planner (133's question; 2026-11-27, before 2b's run)

133 asked whether the -2.5 m/s^2 above was the planner or, as in 190, the MRM's emergency stop.
It was the MRM. r1's record (`brake182.py`, `diag182.py`, NAS), times relative to the strike:

| time | base_link range | ego speed | |
|---|---|---|---|
| -4.85 s | about 11.8 m | 4.17 m/s | `/diagnostics`: `autonomous_emergency_braking: aeb_emergency_stop` ERROR "[AEB]: Emergency Brake" |
| -4.65 s | 11.03 m | 4.17 m/s | `mrm_state` OPERATING, EMERGENCY_STOP; the gate's `emergency_cmd` true; `control_cmd` is the emergency command from here on |
| -4.65 to -3.00 s | | | the command's acceleration ramps from 0 to -2.50 m/s^2, then holds (r1 predates 5cad4e9b: the MRM's stop was stock -2.5) |
| -3.95 s | 8.18 m | 3.88 m/s | the boulder first in the final objects; obstacle_stop's first factor (step 2a) |
| -2.15 s | 4.11 m | 0.00 m/s | the commanded velocity reaches 0; the car stands still, bumper gap **0.39 m**, inside the 1.2 m blind zone |
| -2.05 s | 4.11 m | 0.00 m/s | `mrm_state` SUCCEEDED |
| -1.75 s | 4.10 m | 0.00 m/s | `mrm_state` NORMAL, the gate's emergency false; `control_cmd` 0.25 m/s at +0.42 m/s^2 |
| -1.00 s | 4.04 m | 0.19 m/s | rolling |
| 0 s | 3.49 m | 0.91 m/s | the strike |

**What this changes in the reading of step 2a:**
- The braking before the strike was AEB's, through the MRM. AEB reads the obstacle points, not
  the objects, so it saw the boulder at about 11.8 m, 2 m before the objects did and 2.3 m
  before the validator.
- "The planner's -2.5 m/s^2 floor" in 2a's result is wrong; it was the MRM's stop. obstacle_stop's
  factor came while the MRM already braked.
- The ego *did* stop short, 0.39 m short. There the boulder was in the blind zone: AEB cleared,
  the MRM cancelled after 0.4 s, and the planner, with no obstacle left, asked for 0.25 m/s.
- So H4 stands, refined: the stop came, from AEB, but so close that the boulder left the lidar's
  view, and with it every source of a stop. The creep followed.

**2b's predictions, amended before the run.** 2b runs on pins after 5cad4e9b: the MRM's stop is
-6.0 m/s^2 at -12 m/s^3, and the gate passes 6.0 and 12. If AEB fires at about 11.8 m again:
- the 0.2 s from AEB to the MRM is about 0.8 m;
- the 0.5 s jerk ramp to -6 is about 1.8 m;
- the rest, from about 2.7 m/s, is about 0.6 m;
- in all, about 3.2 m: the car stops at about 8.6 m base_link range, a **bumper gap of about
  4.9 m**, against r1's 0.39 m.

**Replacing 2b's predictions above:**
- AEB raises the MRM at 11 to 13 m. The braking is the MRM's at -6.
- The ego stops with a bumper gap of 3.5 to 6 m. No strike.
- There the boulder stays in view, an object in at least 80 % of the frames. That is outside
  the blind zone, and validated with 181's change; it would be at that range even without it.
- Once stopped, AEB clears and the MRM cancels (as in r1, within about 1 s). obstacle_stop then
  holds the stop: the boulder is inside its 5 m margin, its stop point behind the ego, and its
  hold rule keeps a stopped ego stopped. The ego does not move again (under 0.05 m/s).
- The MRM operates a few times at most, not about once a second.

**What 181's change adds:** the first stop no longer needs it. AEB brakes first, on points. The
hold does, if the gap ends near 4 to 5 m: at r1's validation rule, the boulder would be
validated only from 9.6 m base_link (gap 5.9 m), and at a gap of 4.9 m it is. So the hold may
come with or without the change. 2b does not separate the two, and the record says so.

How sure: the stopping gap about 60 %, the hold about 50 %. If obstacle_stop does not hold a stop
whose point is behind the ego, the planner asks to move after the MRM cancels. The creep then
starts from 4 to 5 m: AEB fires again, and the cycle repeats short of the boulder.

**2b as two runs (133, 2026-11-27; before either run).** To separate 181's profile change from
the rest, 118 runs C6e3's c6b twice, with the same scenario (r1's, starting at x 320; not
fixture_c6b_down's x 20, which meets the rocks at 100, 200 and 300 first, as b1 did) and the same
topics:
- **run A** on scensim main as it stands after 177 lands: the -6 m/s^2 MRM, the stock validator
  (UNKNOWN threshold 10);
- **run B** on the i181 pins: the same, plus the validator's UNKNOWN threshold 5.

Predictions per run, written before either:

| | run A (stock validator) | run B (threshold 5) |
|---|---|---|
| AEB raises the MRM at | 11 to 13 m base_link | the same |
| the boulder first validated | 9.6 ± 1.5 m | 12.1 ± 1.5 m |
| first in the final objects | 8 to 9.5 m | 11 to 12.5 m |
| bumper gap at the stop | 3.5 to 6 m | the same, within 1 m of run A's |
| strike | none | none |
| the boulder an object while stopped | in at least 60 % of the frames | in at least 90 % |
| obstacle_stop's factor while stopped | in at least 60 % | in at least 90 % |
| moves again (over 0.05 m/s) after stopping | no | no |
| MRM operations | a few at most | a few at most |

For run A's "while stopped" figures:
- the stop at about 8.6 m base_link lies in the band where r1's stock validator kept the boulder
  in 22 of 30 frames (5 to 10 m);
- at threshold 5, the replay validated it in every frame from 12.5 m.

**What the pair tells the user:**
- *181's change earns its place here* if run A loses the boulder while stopped (under 60 %), and
  then restarts or cycles, while run B holds.
- *It does not change the outcome here* if both hold the same. AEB's earlier stop on points then
  does the work, and the change only adds margin: 2.5 m more of validated range, and more frames
  with the object while stopped.
- Either way, the first validated range shows the change's direct effect.

**The map (118, before the runs).**
- Runs A and B, and 118's 177 check, use the fixture_c6b map rebuilt by 177's record step
  (`isaac-ex/i177/maps/fixture_c6b` on 118). Its features and section are r1's, and the course
  record is byte for byte the same.
- Its `pointcloud_map.pcd` may still differ from r1's. The compare-map filter, and so 181's
  counts, read that file, so a difference there could move the first validated ranges a little
  against the replay.
- After the runs, the two PCDs are compared before either run's ranges are read against 181's
  replay.
- Checked before the runs: the rebuilt map's `pointcloud_map.pcd` is r1's file, the same inode
  on 118 (the record step does not touch it), sha256
  32bab6cc1a3ddccada85c3a897cb864e8b6cc762e82b9144342e1c69bab4e0f7. That is the NAS copy 181's
  replay used. So the runs' ranges compare with the replay directly.
