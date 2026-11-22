# 100: PhysX's slip denominators scale the full-size cars' slip at every speed

**Status:** open (measuring). **Severity:** medium. **Found:** 2026-11-22, scensim 118 (the
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
scaling does to the car's braking and cornering has not been measured. This issue measures it on
the Isaac Model 3 before anything changes.

## Measurement (in progress)

aib's step-test harness: the vehicle is built from the ego config's rig as `aib.runner` builds
it, on a flat ground, stepped in 0.05 s frames of 3 physics steps, with steering added for the
circles. Script and results: `/var/tmp/aeon/issue100/` on 241 (to go on the NAS). Two settings of
`d`: as shipped (4, 4, 1) and small (0.4, 0.4, 0.1).

- **Full brake** from 10 and 20 m/s (a request of -12 m/s^2, past the tyres): the stop distance
  and the peak deceleration against the spec's tyre friction x g, with ABS as shipped and with
  ABS off (the tyre alone).
- **Steady circles** at 5 and 10 m/s, at a fixed bicycle steer of atan(L / 20 m): the radius,
  the lateral acceleration, the body's sideslip, and PhysX's and the true slip angles. The
  tyre's lateral stiffness is proportional to load (up to 2 rest loads), so with a linear tyre
  the car is near neutral steer. A uniform slip scale should then change the slip angles more
  than the radius, until the tyres saturate.
- **At rest** with small `d`: 20 s on the hold brake, then 20 s released. Drift and speed noise,
  since a small denominator makes slip ill-conditioned near 0 m/s, which is what the
  denominator is there to prevent.

## Not decided here

Any value change is the user's decision. A change of `d` on the full-size cars invalidates:
- the vehicle_check references;
- the T3 Isaac references;
- the ABS and TC thresholds and `est_slip_offset`, which were tuned on the scaled slip.
The RoboRacer's values wait on 118's sweep.
