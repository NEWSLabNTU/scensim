# 157: Autoware's Model 3 crawls at 0.05 m/s downhill on a sand zone on Haruna

**Status:** open; a record (the data below), no probe and no fix yet. **Severity:** to judge: a sand
model that holds a car still downhill would be a physics bug; the record cannot yet tell that
from the controller's braking. **Found:** 2026-11-25, scensim 118, 086 C4's acceptance runs
(numbered by 133).

## What happens

086 C4's scenario `c4_named_then_late` (testbench `isaac_c4_haruna`, C6b's smooth Haruna map, the
named map `haruna_sand`: a sand zone over haruna_down's start, `soil: closed_form`, so Wong and
Reece's closed form with no grid and no ground of its own), Autoware's Model 3 under scensim's
profile, stock Autoware 1.5.0, siw 7813843, GPU0 shared with another session (nothing timed).
Run `2026-11-25T01-56-21_c4_named_then_late_r0`.

All four wheels were on the sand 5.5 s in (the world server's log: zone `start_sand`, mu 0.24 to
0.26). The car then moved 12.5 m in 238 s of simulated time and was timed out.

| sim time, s | speed, m/s | pitch (nose down), deg | control's velocity, m/s | control's acceleration, m/s^2 |
|---|---|---|---|---|
| 20 | 0.052 | 3.25 | 0.25 | -0.03 |
| 60 | 0.054 | 3.40 | 0.25 | -0.05 |
| 100 | 0.055 | 3.48 | 0.25 | -0.07 |
| 140 | 0.058 | 3.58 | 0.25 | -0.09 |
| 180 | 0.060 | 3.72 | 0.25 | -0.10 |
| 220 | 0.061 | 3.77 | 0.25 | -0.10 |

(From the run's gap trace: the ego's measured pose and velocity and the last control command;
the pitch is the body's, about the road's grade there.)

- **The plan held 0.25 m/s.** Every recorded trajectory (`/planning/scenario_planning/trajectory`)
  holds 0.25 m/s over its first 40 points through the run. On the same road without sand (086
  C6d's `rough_none` runs) the command is also 0.25 m/s at 10 s and 4.17 m/s by 20 s, once the
  car moves. So Autoware's start speed never ended, because the car never reached it.
- **The controller asked for deceleration.** Its longitudinal command stayed between -0.03 and
  -0.10 m/s^2 while the car went at a fifth of the commanded speed. On a 3.3 to 3.8 degree
  downhill, gravity alone gives about 0.56 to 0.65 m/s^2 along the road. So the controller was
  braking, or holding, against the slope it expected to accelerate the car (its slope
  compensation). The ECU's traction control and ABS states and the brake torque are not in the
  run's record: the bag holds velocity, steering, trajectory, objects, kinematic state and the
  control command only.
- **So the record cannot separate the two causes yet.** Either the closed-form sand's resistance
  holds a car that is braked lightly, which could be right on loose sand, or the sand model holds
  a car downhill without any brake, which would be a physics bug.

## Next (proposed, not run)

A probe with no Autoware: aib's Model 3 placed on the same sand zone, on the same grade, released
with no brake and no throttle, then with the controller's -0.1 m/s^2. It reads its speed, each
wheel's soil force and the ECU's brake and traction control. A car that does not roll with no
brake at 3.5 degrees on sand of mu 0.25 is the physics bug; one that rolls and stops only when
braked is the controller on loose ground.
