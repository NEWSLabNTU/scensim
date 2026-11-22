# 100: PhysX's slip denominators scale the full-size cars' slip at every speed

**Status:** open (measured; the decision is the user's). **Severity:** medium. **Found:** 2026-11-22, scensim 118 (the
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

## Not decided here

Any value change is the user's decision. A change of `d` on the full-size cars invalidates:
- the vehicle_check references;
- the T3 Isaac references;
- the ABS and TC thresholds and `est_slip_offset`, which were tuned on the scaled slip.
The RoboRacer's values wait on 118's sweep.
