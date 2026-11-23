# 108: the Isaac Model 3 brakes about 7 % harder than its tyre's mu allows

**Status:** open (measured; the source audit points to PhysX's load filter; the one-wheel test
to confirm).
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

## Source audit (241, 2026-11-23, before the one-wheel test)

Read with no GPU: PhysX's tyre code (NVIDIA-Omniverse/PhysX main, verbatim), aib's tyre setup
(autoware_isaac_bridge 3cd2b7d), and Isaac 6.2's PhysX schema and omni.physx plugin. The code
supports candidate 2, the load filter. Candidates 1 and 3 do not fit.

**The tyre's force.** `PxVehicleTireGripUpdate` (`VhTireFunctions.cpp`) sets the tyre's load to
`computeTireLoad(params, suspForce)`. That is the suspension's normal force, put through the load
filter:

```
normalisedLoad = rawLoad / restLoad
filteredLoad   = restLoad * filter(normalisedLoad)
filter(x)      = ymin                                  for x <= xmin
               = ymin + (x - xmin)(ymax - ymin)/(xmax - xmin)
               = ymax                                  for x >= xmax
```

The filtered load is the load the force uses, in the stiffness and in the cap.
`computeTireForceMichiganModel` gives `fz = longSlip * FBar * FZero`, with
`FZero = tireFriction * tireLoad / sqrt(longSlip^2 + nu^2 TEff^2)`, `FBar <= 1`, and
`tireFriction = friction * frictionVsSlip(|longSlip|)`. With no lateral slip and a large
stiffness, `FBar = 1` and the longitudinal force is `mu * frictionVsSlip(|s|) * filteredLoad`.

**What aib sets.** aib (`isaac/vehicle.py`) sets each wheel's sprung mass, spring, damper,
stiffnesses, friction curve and friction table. It sets neither `restLoad` nor a load filter.
- **`restLoad`:** Isaac's schema says 0 means "computed automatically ... gravitational
  acceleration * sprungMass".
- **The load filter:** it is not in the USD schema at all, so omni.physx chooses it.
  `libomni.physx.plugin.so` holds the string `loadFilter` and, in its constants, 0.2308 next to
  3.0. Those are PhysX's long-standing default filter, (0, 0.2308) to (3, 3).

This is strong evidence but not proof that the filter applies. The one-wheel test settles it.

**What that filter does.** For 0 <= x <= 3, filter(x) = 0.2308 + 0.9231 x, so each wheel's
filtered load is 0.2308 restLoad + 0.9231 load. Summed over the car, the restLoads are the sprung
weight and the loads carry the same weight, so the car's grip is 1.154 mu W. Load transfer does
not change this while every wheel stays within 0 to 3 rest loads. That is why the excess is the
same share at every mu.

| candidate | the code | grip at the peak / mu | locked / mu |
|---|---|---|---|
| 1. wheel weight in the load | no: the load is the suspension force only; restLoad is g sprungMass, no wheel mass | 1.045 | 0.86 |
| 2. load filter (0, 0.2308)-(3, 3) | yes: the cap uses the filtered load | 1.154 | 0.953 |
| 3. curve read at another slip | no: \|longSlip\| is the lookup; with aib's 1 m/s denominator, a locked wheel reads 0.94 at 15 m/s to 0.75 at 3 m/s | 1.0 | 0.83 |
| measured | | 1.06 to 1.08 with ABS | 0.955 to 0.964 |

The locked column uses frictionVsSlip averaged over a stop from 15 to 3 m/s at slip v / (v + 1):
0.826. Only the filter gives the locked rows. With ABS, the car reaches 92 to 93 % of the
filter's 1.154 cap, which fits ABS cycling around the peak. Candidate 3 would need a slip near
0.28, and the denominator cannot give that.

### What the one-wheel test should show

One wheel, locked or at a known slip s, with `Vehicle.contacts` giving its force and the
suspension's load. The ratio force / (mu frictionVsSlip(s) load) distinguishes the candidates:
- **The filter:** 0.9231 + 0.2308 / x, where x = load / restLoad. That is 1.385 at x = 0.5, 1.154
  at 1, 1.038 at 2, and 1.0 from 3.
- **The wheel weight:** a constant 1 + wheelMass / sprungMass, about 1.045 for the Model 3,
  whatever the load.
- **The curve's abscissa:** 1.0 when the friction is taken at PhysX's own slip.

### The restLoad-doubling stop (predictions written 2026-11-23, before the run)

A whole-car check: the locked `limit_brake` stop (ABS off) with every `restLoad` set to twice
g sprungMass, through a test-only aib field that writes `restLoad` explicitly. A control run sets
it at once g sprungMass, the value Isaac computes itself, to show the explicit path changes
nothing.

| candidate | locked, shipped (restLoad auto) | restLoad x 1 (control) | restLoad x 2 |
|---|---|---|---|
| filter | 0.953 mu g | 0.953 | (0.4616 + 0.9231) x 0.826 = 1.14 |
| wheel weight | 0.86 | 0.86 | 0.86 |
| abscissa | 0.83 | 0.83 | 0.83 |

Why the doubling changes one thing. In PhysX's vehicle source (`physx/source/physxvehicle`,
grepped in full), `restLoad` is read in two places only: `computeTireLoad`, the load filter, and
`computeTireForceMichiganModel`, the lateral stiffness. The suspension force, the sprung mass,
the wheel's rotation and the sticky-tyre state do not read it.
- **Lateral stiffness:** `latStiffY * smooth(3 * filteredLoad / restLoad / latStiffX)` falls
  from 0.92 to 0.72 of `latStiffY` with the doubling. It enters the force only through the
  lateral slip, which a straight stop does not have. The run's yaw is checked to be sure.
- **Longitudinal smoothing:** `FBar` stays 1. K = longStiff |s| / (mu f load) is about 9 / mu
  shipped and 7.5 / mu doubled, both over 3 for mu <= 1.
- **omni.physx:** the plugin is not open source. It computes the automatic restLoad, and the
  control run covers that.

### If it is the filter

The filter is not in Isaac's USD schema, so aib cannot set it. While every wheel stays within 3
rest loads, the car's grip is exactly 1.154 times its friction. So aib can write each wheel's
friction divided by 1.154, and the car's limit is then the spec's mu. Two things are left:
- **Per wheel:** a lightly loaded wheel still gets more than its share, 1.385 at half its rest
  load.
- **Lateral stiffness:** PhysX's lateral stiffness already reads the filtered load.

That is for the fix, after the test.

## Fix

After issue 106. Find the term. Then either correct it in aib's rig, so the effective mu is the
spec's, or state the factor in the spec's provenance and in every Isaac-vs-CARLA braking
comparison. Until then, Isaac's mu is about 1.07 times the spec's at the peak.

Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/mueff`.
