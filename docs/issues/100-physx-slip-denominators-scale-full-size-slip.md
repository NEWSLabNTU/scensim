# 100: PhysX's slip denominators scale the full-size cars' slip at every speed

**Status:** open (decided 2026-11-22: the Model 3 is changed and retuned now, the Mustang after;
the Model 3's values landing with step 2, below). **Severity:** medium. **Found:** 2026-11-22, scensim 118 (the
RoboRacer's sweep); the full-size cars checked by 241.

## What happens

PhysX 5 adds its slip denominators to the contact point's speed, at every speed. It does not
use them as a floor (`physx/source/physxvehicle/src/tire/VhTireFunctions.cpp`,
NVIDIA-Omniverse/PhysX):

- lateral, `computeLateralSlip`: `atan(latSpeed / (|lngSpeed| + minLatSlipDenominator))`, in
  the legacy and the non-legacy paths alike;
- longitudinal, `computeLongitudionalSlip` (sic): `(omega r - v) / (|v| + d)`, where `d` is
  the active denominator under drive or brake and the passive one otherwise. Only the legacy
  passive path takes a max, `PxMax(d, PxMax(|v|, |omega r|))`.

So PhysX's slip is the true slip scaled by about `v / (v + d)`, and the tyre's force curve is
evaluated at that scaled slip. The speeds are the contact point's: the body's velocity plus
omega x r, less the road's.

The Isaac Model 3 and the Mustang ship `d` = 4.0 m/s (active and passive) and 1.0 m/s
(lateral), in their specs (`isaac.physx`) and aib's rigs. Their slip is therefore scaled by:

| speed | longitudinal (d = 4) | lateral (d = 1) |
|---|---|---|
| 2 m/s | 0.333 | 0.667 |
| 5 m/s | 0.556 | 0.833 |
| 10 m/s | 0.714 | 0.909 |

The documents that called this a floor were the RoboRacer's README and spec comment (scensim
35a23189) and sim_vehicle_ecu's `est_slip_offset` comment (3b3355a). Both are fixed, with no
values changed.

## Why it matters, and what is not known yet

A tyre's force curve is fitted against true slip. Under the scaling, the car needs more true
slip for the same force, and it reaches the friction limit at a different true slip. The onboard
computers' ABS and TC thresholds were tuned on PhysX's scaled slip, and sim_vehicle_ecu's slip
estimate uses the same +4 m/s offset, so the controllers agree with what PhysX reports. What the
scaling does to the car's braking and cornering is measured below on the Isaac Model 3, before
anything changes.

## Measurement (2026-11-22, 241)

**Setup:**
- aib's step-test harness at main's pin (aib d54338a): the vehicle is built from the ego config's
  rig as `aib.runner` builds it, on a flat ground (the slopes tilt gravity), in 0.05 s frames
  of 3 physics steps, through the onboard computers. Steering is added for the circles.
- Two settings of `d`: as shipped (4, 4 and 1 m/s) and small (0.4, 0.4 and 0.1).
- GPU1 of 241, shared with other runs; nothing here is a timing.
- Script, CSVs and logs: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-22 issue 100 PhysX slip
  denominators on the Isaac Model 3 (241)/`.

**Full brake** (a request of -12 m/s^2, past the tyres; the spec's tyre friction is 1.0, so
mu g = 9.81 m/s^2):

| from | d | ABS | distance | at mu g | mean decel | peak rear slip (PhysX) |
|---|---|---|---|---|---|---|
| 10 m/s | shipped | on | 5.37 m | 5.18 m | 9.60 | -0.41 |
| 10 m/s | small | on | 5.59 m | 5.18 m | 9.17 | -0.53 |
| 10 m/s | shipped | off | 5.45 m | 5.18 m | 9.60 | -0.64 |
| 10 m/s | small | off | 5.74 m | 5.18 m | 9.17 | -0.95 |
| 20 m/s | shipped | on | 20.31 m | 20.54 m | 9.79 | -0.49 |
| 20 m/s | small | on | 20.76 m | 20.65 m | 9.82 | -0.80 |
| 20 m/s | shipped | off | 21.18 m | 20.54 m | 9.56 | -0.80 |
| 20 m/s | small | off | 22.26 m | 20.65 m | 9.15 | -0.98 |

As shipped, the car stops within 4 % of mu g from 10 m/s, and within mu g from 20 m/s. Small
`d` stops 2 to 5 % longer. The cause is the slip, not the tyre's peak: the same wheel speeds
read as larger slips, so ABS, whose thresholds were tuned on the scaled slip, releases later,
and without ABS the wheels lock harder, onto the curve's 0.8 at full slip. The per-frame peak
deceleration (10.7 to 12.8 m/s^2) is a 0.05 s difference with pitch in it, not a sustained
value.

**Steady circles** at a bicycle steer of atan(L / 20 m):

| speed | d | radius | lat accel | kinematic | sideslip | true slip angle, front (rear) |
|---|---|---|---|---|---|---|
| 5 m/s | shipped | 20.09 m | 1.240 | 1.246 | -0.57 deg | 0.61 deg (0.59) |
| 5 m/s | small | 20.08 m | 1.241 | 1.246 | -0.48 deg | 0.53 deg (0.51) |
| 10 m/s | shipped | 20.30 m | 4.802 | 4.875 | -2.39 deg | 2.57 deg (2.48) |
| 10 m/s | small | 20.28 m | 4.817 | 4.884 | -2.20 deg | 2.37 deg (2.30) |

The front is the outer front wheel. True slip is PhysX's, unscaled with the body's speed for
the contact's. Shipped and small agree on the radius within 0.1 % and on the lateral
acceleration within 0.3 %, and both are within 1.5 % of the kinematic. As the tyre data
predicts, the car is near neutral steer: the lateral stiffness is proportional to load, up to
2 rest loads, so a uniform slip scale leaves the radius alone. The scale shows in the angles
instead. As shipped, the tyres run 17 % more true slip angle at 5 m/s and 8 % more at 10 m/s,
with the sideslip to match. These circles stay in the linear range. Near the friction limit,
the larger true slip as shipped means the curve's saturation arrives at a different true
angle, which these runs do not test.

**At rest and at a creep** (aib.steptest's slope tests):

| test | shipped | small |
|---|---|---|
| hold_flat, hold_down (a held stop) | 0, 0.0077 m | 0, 0.0077 m |
| start_flat (Autoware's creep, -0.028 m/s^2 to 0.25 m/s) | 0.26 m, 0.016 m/s | 0.003 m, -0.0055 m/s |
| start_up (3.1 deg uphill) | 3.73 m, 0.77 m/s | 2.97 m, 0.67 m/s |
| start_down (3.1 deg downhill) | 23.25 m, 4.77 m/s | 23.23 m, 4.77 m/s |

Small `d` holds as well, but it breaks the flat creep start: the car does not move and ends
rolling back slowly. It also slows the uphill start by 13 %. Both starts depend on the
release torque and the sticky-tyre thresholds (issue 070), which were tuned on the shipped
denominators.

**Reading.** On these manoeuvres, the shipped denominators cost the full-size car nothing in
braking or steady cornering: within mu g, and on the kinematic circle. They inflate its slip
angles by 8 to 17 % and its sideslip with them. Small denominators would make the slip honest,
but they lengthen braking until ABS is retuned, and they break the creep start until the
release torque is retuned.

## Decision and plan (2026-11-22)

The user chose to change and retune. The Model 3 goes first. The Mustang stays as shipped until
243 can rerun the drift results on it (057 and 058), since its slip is the drift measure. The
RoboRacer's lateral denominator is 0.05 since 091 W10 (the user's choice after 118's sweep);
its longitudinal ones stay at 0.5 (not swept).

**What a change moves.** This was measured on copies of both specs with only `isaac.physx`'s
denominators changed, hashed by sim_vehicle_spec at main's pin:

| car | spec_hash | physics_hash |
|---|---|---|
| Model 3 | moves (dffb1d3d to b198595a) | unchanged: carla-0.9.16 33635ad5, carla-1.0 6384e6a2 |
| Mustang | moves (65f1ba86 to ad450a5e) | unchanged: 933597f5 |

`isaac` is not one of PHYSICS_SECTIONS. CARLA's physics has no slip denominators, so:
- the pedal maps, which record physics_hash, stay valid;
- the CARLA artefacts are regenerated only for the new spec_hash.
Every output that names spec_hash moves in one cascade, because the bridge refuses an ego whose
world server, agent and catalog name different specs. The outputs are:
- sim_vehicle_spec's generated files and catalogs;
- aib's rig;
- autoware_sim_vehicle's per-car configs.

**Steps**, in order:
1. An Isaac physics hash (the follow-up below), so the new references are keyed to it.
2. The values: a short sweep on the Isaac Model 3, as 118's.
   - Grid: the longitudinal denominator, active and passive alike, in 0.25, 0.5, 1 and 2 m/s,
     against the lateral one in 0.1, 0.25 and 0.5 m/s.
   - Constraints:
     - at rest on the flat, no drift and no speed noise;
     - parked across a 3 % camber, at most 0.1 cm in 60 s;
     - the held stop on the downhill unchanged;
     - no oscillation of wheel spin at rest.
   - The pick is the smallest values that meet all four. The creep start is not a constraint
     here: it depends on the release torque, which step 4 retunes.
3. sim_vehicle_ecu's thresholds.
   - `est_slip_offset` follows the spec.
   - ABS and TC are retuned so that:
     - brake_10, brake_20 and brake_100 stay within the shipped car's margin of mu g;
     - ABS cycles and does not lock;
     - TC's launch is no worse than shipped.
4. aib's release torque and sticky-tyre thresholds (issue 070). These are retuned until
   Autoware's creep start matches the shipped car: start_flat about 0.26 m and 0.016 m/s in
   20 s; start_up and start_down within 5 %; the holds unchanged. Then the camber test again.
5. Validation:
   - the whole aib.steptest suite against shipped;
   - this issue's circles, with the radius and lateral acceleration within 1 % of shipped and
     the slip angles lower.
6. Reference reruns:
   - vehicle_check on Isaac for the Model 3;
   - the T3 Isaac suites, compared first against the old references, then recorded.
   The CARLA suites and the articulation engine are not affected.

Landing goes through land_pin, dry run first: sim_vehicle_spec, sim_vehicle_ecu, aib and
autoware_sim_vehicle, then scensim's pins and the references.

**Step 2, the values (2026-11-22, approved by 133).** The sweep ran on the Isaac Model 3 (aib
bf35c0b, GPU1 of 241, shared). Its grid was the longitudinal denominator (active = passive) in
0.25, 0.5, 1 and 2 m/s against the lateral in 0.1, 0.25 and 0.5, plus the shipped values.

| d long / lat | holds, rest, camber | start_flat | start_up | brake_10 / 20 / 100 | front true slip angle, 5 m/s circle | v / (v + d) at 5 m/s |
|---|---|---|---|---|---|---|
| shipped 4 / 1 | pass | 0.264 m | 3.73 m | 5.37 / 20.31 / 40.01 m | 0.572 deg | 0.56 |
| 2 / any | pass | 0.296 | 3.56 | 5.39 / 20.45 / 40.43 | | 0.71 |
| 1 / any | pass | 0.284 | 3.57 to 3.64 | 5.67 / 20.58 / 40.07 | | 0.83 |
| 0.5 / any | pass | 0.006 to 0.011 | 3.15 to 3.60 | 5.60 / 20.54 / 40.33 | | 0.91 |
| 0.25 / any | pass | about 0 | 1.15 to 2.58 | 5.66 / 20.90 / 40.05 | | 0.95 |

Notes on the table:
- The front true slip angle at the lateral denominator: 0.483 deg at 0.1, 0.498 at 0.25, 0.523
  at 0.5.
- The braking columns ran before step b: ABS's slip estimate still used the 4 m/s offset.
- No denominator moved the holds (hold_flat 0, hold_down 0.0077 m), the rest drift (0) or the
  camber creep (4.91 cm, issue 102).

**Chosen: 1 m/s active and passive, 0.1 m/s lateral.** The plan's rule, the smallest values
that meet the constraints, gives 0.25 and 0.1, since every point meets them. That rule is not
followed, for two reasons:
- below 1 m/s the flat creep start dies (0.0008 to 0.011 m against 0.26), and the uphill
  start loses up to 70 %. Bringing them back needs the release torque retuned (issue 070),
  with its own risk;
- at 1 m/s the creep start stays as shipped (0.284 m), and the longitudinal slip already goes
  from 0.56 to 0.83 of the true slip at 5 m/s, and from 0.71 to 0.91 at 10.
The lateral 0.1 costs nothing measured. The same step sets the lateral sticky damping from 200
to 3200, issue 102's fix: the camber creep falls from 4.91 to 0.13 cm in 60 s, the turning
starts are unchanged, and there is no chatter. Retunes: ABS and TC, step b; the release torque
stays unless step b moves the starts.

**Follow-up: an Isaac physics hash.** physics_hash leaves out `isaac`, so the Isaac-side
references are not keyed to the physics they were measured on:
- aib.steptest;
- vehicle_check on Isaac;
- the T3 Isaac suites.
A change to `isaac.physx` moves only spec_hash, which a description edit moves too. The proposal
has three parts:
- sim_vehicle_spec gains `isaac_physics_hash(spec, body)`, over the body's PHYSICS_SECTIONS
  and `isaac`;
- aib's rig records it next to physics_hash;
- those references write it into their results, so a comparison against a reference with
  another hash says so.
physics_hash stays as it is, so the CARLA artefacts do not move for an Isaac-only change.

**Step b, ABS and TC (2026-11-22, 241).** At the new denominators, with the brake module's
estimate kept at 4 m/s, 13 ABS settings were run through brake_100, brake_10 and brake_20:

| release / reapply | brake_100 | locked frames | brake_10 | brake_20 |
|---|---|---|---|---|
| shipped car | 39.91 m | 4 | 5.372 m (+3.7 % of mu g) | 20.31 m (-1.1 %) |
| 0.25 / 0.15 on the new tyre | 39.86 m | 2 | 5.671 m (+9.5 %) | 20.58 m |
| 0.2 / 0.05, chosen | 39.55 m | 2 | 5.391 m (+4.1 %) | 20.04 m (-2.4 %) |
| 0.18 / 0.05 | 39.29 m | 1 | 5.398 m (+4.2 %) | 20.18 m |
| 0.15 / 0.08 | 39.61 m | 0 | 5.444 m (+5.1 %) | 20.33 m |

0.2 / 0.05 stops shorter than the shipped car from 100 km/h and 20 m/s, and from 10 m/s within
0.4 points of it. TC stays as shipped (0.25 / 0.15): the launch takes 6.43 s against 6.44, and
lower limits only slow it (0.12: 6.85 s). The run first found issue 103, a latch of TC at an
estimate offset of 1 m/s, whose cause was aib's release torque.

**The estimate's offset is the car's own.** sim_vehicle_ecu read it from
`isaac.physx.min_active_slip_denominator`, the simulator's tyre. It is now the spec's
`brakes.estimator.slip_offset`, 4.0 on the Model 3, 0.5 on the RoboRacer (its active denominator's, so
unchanged).

**The other cars stay as they were.** aib's PhysX defaults and sim_vehicle_ecu's ABS defaults
follow the Model 3, as their tests require, so they move with it. The Mustang sets every one of
these values in its own spec. The MuSHR Nano took the old defaults, so its spec now writes them:
4, 4 and 1 m/s, damping 200, ABS 0.25 / 0.15, offset 4. The RoboRacer sets ABS itself, and its
offset of 0.5 is the value its estimate took from its own 0.5 m/s active denominator (its lateral one is 0.05). Its TC defaults
did not move. Tests: aib's OtherCarsUnchangedTest, and the RoboRacer's test_issue100.py. Every
calibration and rig value is as before, and only spec_hash and isaac_physics_hash move.

**The fingerprints.** `brakes.abs`, `brakes.estimator`, `brakes.esc`,
`powertrain.traction_control` and `powertrain.regen_slip_control` are the onboard computer's,
which CARLA never runs. The world server turns CARLA's ABS and TC off and reads none of them,
acb reads none, and `carla_physics*.yaml` holds none. They were in physics_hash, so this ABS
change asked for CARLA's pedal maps to be measured again. sim_vehicle_spec now leaves them out
of physics_hash (`ONBOARD_COMPUTER`), and isaac_physics_hash has them. The definition change
moves physics_hash once, unlike the table above, which held for `isaac` alone:

| body | physics_hash |
|---|---|
| Model 3, carla-0.9.16 | 33635ad5 to 47a1043b |
| Model 3, carla-1.0 | 6384e6a2 to 5af7c9f6 |
| Mustang | 933597f5 to 87a96d29 |
| MuSHR Nano | unchanged (none of those keys) |

Every CARLA output regenerated identical but for its hash lines. sim_vehicle_spec's
OnboardComputerTest asserts it on every car and body, so the pedal maps move to the new hash
without a new measurement. Each one records the old hash in `physics_hash_moved`. Citations of
the old values elsewhere are records of their time: roadmap 057, step 1's table, and the P4
bench, which 139 moves.

## Not decided here

The Mustang's values, after 243's drift reruns. A change of `d` on a full-size car invalidates:
- the vehicle_check references;
- the T3 Isaac references;
- the ABS and TC thresholds and `est_slip_offset`, which were tuned on the scaled slip.
The RoboRacer (091 W10, 118): the lateral denominator swept over 0.25, 0.1, 0.05 and 0.02 m/s on
the twin. Rest, launch and braking were unchanged and 240 Hz stayed stable at every value, and
the circles moved under 1.5 % from 0.25 to 0.02. At 0.25 the car's grip at 1 m/s was 0.80 of its
tyre's; at 0.05 it is 0.95. The user chose 0.05. W23's regression and W10's fits are rerun on it
(roadmap 091, W10: findings); W6 to W9's twin quantities are still to be rerun.
