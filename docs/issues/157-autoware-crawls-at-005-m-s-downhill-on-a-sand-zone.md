# 157: Autoware's Model 3 crawls at 0.05 m/s downhill on a sand zone on Haruna

**Status:** open: the probe found the sand's resistance, not the brakes (below); a modelling question for 054's sand class. **Severity:** to judge: a sand
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

## The probe (133; before the runs)

The live world server, the same testbench and map (`haruna_sand`, its zone over the start), and a
scenario that names the map at the Init and ends at 90 s (`p157_sand`). A local probe commit of
siw (7b13f5f on main 7813843, never pushed) replaces the ego's command in aib's `Vehicle.apply`,
one arm a run, and logs every 6th physics step: the vehicle's speed and pitch, the request, the
ECU's debug (brake pressure, the ABS and TC factors, motor torque), the drive and brake torques
set on the wheels after aib's sticky-tire release, and each wheel's soil output (sinkage,
resistance, thrust, load). Autoware runs as before; its command reaches the car only in the
third arm, and then through the replay, not live.

- **free:** no ECU and no torque: drive 0 and brake 0 on every wheel, the car released.
- **brake:** the request -0.1 m/s^2 at 0.25 m/s in drive, through the ECU.
- **replay:** the original run's commands (its gap trace, 4688 changes), by the vehicle's own sim
  time, through the ECU.

**What the sand's closed form gives (computed before the runs, `soil.wong_reece` for `sand` on
a 0.37 m wheel 0.235 m wide):** resistance 0.18 to 0.21 of the wheel's load at 3500 to 5500 N,
sinkage 2 to 3 cm. Gravity along a 3.5 degree grade is 0.061 of the weight. So the closed form
alone resists about three times what the slope pulls.

- **118's prediction.**
  - free: the car does not roll freely. It creeps under 0.1 m/s, the soil's resistance about
    0.2 of each wheel's load and its brakes 0 throughout. If it rolls, gaining speed down the
    grade, the sand is not what held the car in the original run.
  - brake: the same creep. The ECU's brake pressure small or nothing,
    ABS and TC inactive (factors 1).
  - replay: as the original run, about 0.05 m/s, the ECU braking lightly or not at all, its drive
    torque near zero.
  - So issue 157 is the sand's resistance (0.2 of the load, the closed form's compaction), not
    the ECU nor a stuck brake. Whether 0.2 is too much for this class on a car is a modelling
    question for 054's sand class, not a bug in the code. And why the controller asks for
    deceleration below its plan's speed is Autoware's slope compensation: on a downhill it
    expects gravity to supply the acceleration, so it commands less.

### The probe's result (2026-11-25, 02:40 to 02:50; one run each)

GPU0 (shared by agreement, nothing timed); siw 7b13f5f in the gate checkout for the runs,
restored to 7813843 after. Each run passed its scenario (it ends at 90 s). Every 6th physics step
logged, about 960 records an arm. After the first 10 s:

| arm | speed, m/s | brake torque, sum of wheels | drive torque, sum | ECU brake pressure | ABS, TC factors | soil resistance / load | soil load, N | soil thrust, N |
|---|---|---|---|---|---|---|---|---|
| free | 0.0515 to 0.0557 | 0 | 2.0 | (no ECU) | (no ECU) | 0.214 to 0.215 | 17087 | 4612 |
| brake | 0.0515 to 0.0557 | 0 | 2.0 | 0 | 1, 1 | 0.214 to 0.215 | 17087 | 4612 |
| replay | 0.0512 to 0.0560 | 0 | 2.0 | 0 | 1, 1 | 0.214 to 0.215 | 17082 | 4611 |

(The 2.0 N m of drive is aib's sticky-tire release, 1.0 N m on each driven wheel. Pitch 3.2 to 3.5
degrees nose down. Each arm went 4.66 m in the 80 s.) In the replay arm, the original run's
start held the car with the ECU's brake for its first frames (1455 N m in all at 0.08 s, while
the command was still zero), and then released it.

- free: the car does not roll freely; it creeps at 0.05 to 0.056 m/s with no torque on it.
  **Held.**
- brake: the same creep, the ECU's brake pressure 0, ABS and TC inactive. **Held.**
- replay: as the original run, about 0.055 m/s; the ECU does not brake for Autoware's -0.03 to
  -0.07 m/s^2 (pressure 0, motor torque 0). **Held.**
- So the cause is the sand: its closed form resists 0.214 of the load, about 3.6 times the 0.059
  the grade pulls. The ECU and the brakes are not part of it, and Autoware's small negative
  command changed nothing. Two questions are left for 054's sand class, not judged here:
  - whether 0.21 of the load is right for a car's tyre on this class (it holds a car on a 3.5
    degree slope; loose dry sand can);
  - why the car creeps at a steady 0.055 m/s rather than standing still, when the resistance is
    above the pull. A speed at which forces balance points at the closed form's low-speed
    handling, not at static friction.
- The controller's deceleration below its plan's speed was not probed here; it had no effect on
  the car.

Record: NAS "2026-11-25 issue 157 sand probe (118)". Status: a modelling question for 054's sand
class (the resistance's size and its low-speed creep), not an ECU or brake fault.
