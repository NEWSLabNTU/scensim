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
