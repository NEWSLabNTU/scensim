# 157: Autoware's Model 3 crawls at 0.05 m/s downhill on a sand zone on Haruna

**Status:** open, low priority: its cause was issue 158 (fixed) plus the soil's low-speed ramp, a known limit (below). **Severity:** to judge: a sand
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

### Hypotheses for the open questions (133; not results)

1. **The size, 0.21 of the load.** Secondary engineering tables put the rolling resistance of a tyre
   on loose sand at 0.15 to 0.30 (Engineers Edge, "Rolling resistance force", its table 1) and a car
   tyre on loose sand at 0.2 to 0.4 (Engineering ToolBox, "Rolling resistance"). Neither cites a
   primary test. 0.21 sits inside both ranges. Wong's *Theory of Ground Vehicles* was not checked
   here, and its figures are not quoted.
2. **The creep. Checked against the code, offline.** The closed form's resistance is applied
   through `surface_layer.resistance_scale`, a linear ramp, `speed / RESIST_V0` with RESIST_V0 =
   0.1 m/s (issue 004's fix: a standing car is not pushed), not a tanh. A ramp gives an
   equilibrium speed where the scaled resistance equals the grade's pull: v = RESIST_V0 x pull /
   resistance. From the free arm's own numbers (every wheel's share 1, its resistance and load,
   the pitch), that speed is 0.026 to 0.028 m/s. The car went 0.052 to 0.055 m/s, about twice
   that, and at that speed the ramp's resistance is 1.96 times the grade's pull throughout. So the
   ramp explains why the car creeps rather than standing. It does not explain the speed: some
   other force of about the grade's pull (about 1000 N) acts forward too. A next look would be the
   speed `resistance_scale` is given (the contact's, not the body's?) and the tyre's own forces in
   PhysX.
3. **Autoware's negative command.** Its longitudinal controller compensates the slope by
   subtracting g sin(grade) on a downhill: it expects gravity to supply the acceleration and
   knows nothing of the sand. That is the likely reason for its -0.03 to -0.10 m/s^2 below the
   plan's speed, and it changed nothing here (the ECU did not brake for it).

157 stays open as a modelling question; a plan for it comes after C6c's.

## The missing force, found offline, and the fix plan (2026-11-25, before any run; for 133's review)

133 asked first for the unexplained forward force of about 1000 N, the speed the ramp reads, and
PhysX's own tyre forces at low speed.

- **The speed the ramp reads is the right one.** `SurfaceLayer.update` is given
  `ego.state.velocity[0]` (`world.py`, the substep loop): the body's base_link speed along its
  x axis from PhysX's tensor view, the same speed the probe logged (0.052 to 0.055 m/s). So
  `resistance_scale` gave 0.52 to 0.56, and its input explains nothing.
- **The force is the road layer's, and it is the grade counted twice** (now issue 158, its own
  record and reach list; 157 keeps the sand creep, 158 its cause). Haruna has a road
  detail, so the probe's car ran on R5's contact (the run's log: "road detail ...
  road_detail.yaml: 1 corridor(s)"). Its `dfx`, "the effective plane's push back along the
  wheel's heading", is minus the tire's load times the cams' slope (`road_contact.step`). The
  cams read the true road, `base + detail` (`road_layer`'s `road`), so their slope holds the base
  road's grade as well as the detail's: on a plane of -0.06 the envelope's slope is -0.0589
  (checked offline). PhysX already carries the base grade (the body pitched on it, gravity
  along it), so `dfx` adds the load times the grade a second time: forward on a downhill,
  backward on an uphill.
- **Its size is the missing force.** `test_road_layer`'s stand-in car on a bare corridor (no
  detail) with a 6 % grade gets `dfx` summing to 1102 N against the slope (10 %: 1801 N; level:
  0), the load times the grade. On the probe's 3.4 degree downhill that is about 1000 N forward,
  the force the ramp's equilibrium was missing: with it the equilibrium speed is
  RESIST_V0 x (pull + load x grade) / resistance, twice the 0.027 m/s without it, the 0.055
  measured.
- **Not PhysX's tyres.** A free-rolling wheel with aib's 1 N m release torque passes about
  T / r = 2.7 N to the road, and its brake was 0. The probe did not log the tyre forces, so
  this is reasoning, not a measurement; P2 logs them.
- `test_no_detail_no_force_on_a_grade` asserts the vertical force only, which is why this
  passed: its name says no force, and the push along the road was never checked.

**What it touches beyond 157.** Every run on a road-layer world with a grade: the car felt the
grade's pull twice (downhill and uphill), on Haruna since R5 went into the world server (C4,
C5's Haruna runs, C6b's budget, C6d). C6d's rocks-or-not pairs had it on both sides, so their
deltas stand; absolute speeds and braking on Haruna's grades do not. aib's slope matrix and
055's suite run on worlds without a road detail and are untouched. Which recorded results
depend on it is listed with the fix, not before.

**The plan** (each step's runs on GPU0, non-timing, codec told):

- **F1, the fix.** `dfx` from the cams' slope less the base road's slope along the same
  heading (`base` at the contact plus and minus a few cm), so a plane gives no push and only the
  detail's own slope does. A test first, failing on today's code: the bare corridor at 0, 6 and
  10 % gives `dfx` within 1 N of 0 on every wheel; a water bar's push is unchanged on a level
  road (the existing test) and on a 6 % one, within 1 % of the level one's.
  118's prediction: today's code fails it by the load times the grade per wheel (260 to 475 N),
  the fix passes; the fixture course checks (C6a's, C6b's, C6c's, all level) unchanged within
  their noise.
- **P2, the probe again, after F1** (the free arm, 157's map and scenario, siw with F1 and the
  probe's logging, local): logged as before plus each wheel's PhysX tyre force along it
  (`WheelState.force`), the road layer's `dfx` and the soil's applied force, and the
  residual m a minus the known forces along the road. 118's prediction: the car creeps at
  0.026 to 0.028 m/s (the ramp alone, the offline number), `dfx` under 50 N in all, the tyres'
  under 20 N, the residual under 100 N.
- **F2, the ramp, a choice for 133 after P2.** The ramp makes a standing car creep wherever the
  resistance exceeds the pull. RESIST_V0 can come down only so far: the resistance's slope
  R / RESIST_V0 at 60 Hz on the body is stable for R dt / (m RESIST_V0) under 2, so with R about
  3.7 kN and m about 1900 kg RESIST_V0 must stay above about 0.016 m/s; 0.03 m/s would leave a
  creep near 0.008 m/s here. Or a hold that resists up to the full value at rest (a static
  friction), which is a model change. Options with their numbers go to 133 after P2.
- **Then** the Haruna results that depend on it, rerun or annotated, named for 133.

Not in this plan: the size of the sand's 0.21 (054's question, hypothesis 1 above) and
Autoware's slope compensation (hypothesis 3).

**P2's result (2026-11-25, on issue 158's F1):** the free arm creeps at 0.024 to 0.026 m/s, half
the 0.052 to 0.055 before, and gravity, the soil and the road layer close to -85 N; the creep left
is the ramp's alone. Details and the predictions' outcomes in issue 158's "Issue 157's P2 on F1".
F2, the ramp, is 133's choice next.

**A known limit (133, 2026-11-25):** on soil below the ramp's speed a car whose soil resistance
exceeds the grade's pull creeps, at about RESIST_V0 x pull / resistance: 0.025 m/s on this map
and grade (P2). F2, lowering RESIST_V0 or a static hold, is deferred: it moves every soil
world's low-speed behaviour and would need 055's suite rerun. 157 stays open, low priority;
revisit when a scenario needs a true standstill on soil.
