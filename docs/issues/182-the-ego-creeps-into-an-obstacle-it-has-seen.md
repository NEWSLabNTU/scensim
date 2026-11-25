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
