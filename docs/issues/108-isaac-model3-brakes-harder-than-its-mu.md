# 108: the Isaac Model 3 brakes about 7 % harder than its tyre's mu allows

**Status:** open (measured; the term inside PhysX not found yet; after issue 106).
**Severity:** medium: every braking comparison of Isaac against CARLA, or against a real car,
carries it. **Found:** 2026-11-23, scensim 241, in issue 106's low-grip sweep (133 asked for it
to be measured).

## What happens

At its limit, the Isaac Model 3 stops harder than mu g allows. With its wheels locked, it stops
harder than its own friction-vs-slip curve allows.

Measured with aib.steptest `limit_brake`, a request of -12 m/s^2 from 15 m/s, at tyre friction
(`--set tire_friction`) 0.2, 0.3, 0.5 and 1.0. Each run has ABS on as shipped, or off, so the
wheels lock. The deceleration is dv/dt over the stop above 3 m/s, past the lags, less the road
load (rolling 0.0095 g, plus drag); the logged `a` agrees with dv/dt to 0.01 m/s^2.

| set mu | with ABS: decel / g | / mu | locked: decel / g | / mu |
|---|---|---|---|---|
| 0.2 | 0.212 | 1.060 | 0.193 | 0.964 |
| 0.3 | 0.320 | 1.068 | 0.287 | 0.955 |
| 0.5 | 0.539 | 1.078 | 0.478 | 0.956 |
| 1.0 | 1.069 | 1.069 | 0.959 | 0.959 |

- **With ABS:** the tyre works near its peak, where the curve's multiplier is 1.0. The car gets
  1.06 to 1.08 times mu g.
- **Locked:** the logged slip is about -0.9. There, the curve `[[0, 1.0], [0.1, 1.0], [1.0, 0.8]]`
  gives 0.82, but the car gets 0.96, about 17 % over.

The excess is the same share at every mu, so it is a scale on the force, not an offset.

The shipped dry `brake_100` already shows it: 39.91 m from 100 km/h against mu g's 39.33 m, with
ABS cycling below the peak for part of the stop.

## What is not the cause

- **The friction table.** `--set tire_friction` reaches every wheel; the Model 3 has no
  `tires.front` or `tires.rear` override. Each wheel's PhysX friction table holds no ground
  materials, so its default value, the set friction, applies on any ground. The ground plane's
  own material does not enter a vehicle tyre's friction.
- **The measurement.** dv/dt and the logged acceleration agree, and the road load is taken out.

## Candidate terms, not yet tested

1. **The tyre load.** PhysX limits the tyre force by mu times the tyre load, and the load comes
   from the suspension. aib gives each wheel's suspension its axle's sprung mass
   (`params.axle_loads`, which sums to the body's 1760 kg). If PhysX adds the wheel's own weight
   (4 x 20 kg) to the load, the loads total 1840 kg x g against a body of 1760 kg: 4.5 %.
2. **The load filter.** PhysX's tyre has a normalised load filter. If its default is not the
   identity, the force cap uses a filtered load above the real one.
3. **The curve's abscissa.** The locked case's 17 % excess is larger than the peak's 7 %. This
   suggests the friction-vs-slip curve is read at a slip other than the logged one. One
   candidate is PhysX's slip with its denominator, against the true slip.

Each of these is testable on one wheel: the tyre force PhysX reports (`Vehicle.contacts`)
against the load it reports, at a known slip.

## Fix

After issue 106. Find the term. Then either correct it in aib's rig, so the effective mu is the
spec's, or state the factor in the spec's provenance and in every Isaac-vs-CARLA braking
comparison. Until then, Isaac's mu is about 1.07 times the spec's at the peak.

Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/mueff`.
