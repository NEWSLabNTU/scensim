# 108: the Isaac Model 3 brakes about 7 % harder than its tyre's mu allows

**Status:** fixed (aib ff5e72b, scensim_isaac_world 7e01d7b): PhysX's default tyre load filter,
confirmed by the restLoad-doubling stop, divided out by aib.
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

### The restLoad-doubling stop: result (2026-11-23)

The run used aib origin/main 3cd2b7d plus a test-only field `tire_rest_load_scale`, never
landed. It was a locked `limit_brake` (ABS off) on GPU1, beside the P4 seeds. The deceleration is
measured as above. The analysis reproduces the earlier locked runs: 0.955, 0.477 and 0.192 mu g,
against the table's 0.959, 0.478 and 0.193.

| run | decel / g | / mu | mean slip | predicted (filter) | wheel weight / abscissa |
|---|---|---|---|---|---|
| mu 1.0, restLoad x 1 (control) | 0.955 | 0.955 | -0.87 | 0.953 | 0.86 / 0.83 |
| mu 0.5, restLoad x 2 | 0.572 | 1.145 | -0.88 | 1.14 | 0.86 / 0.83 |
| mu 1.0, restLoad x 2 | 1.215 | 1.215 | -0.30 | above the request | 0.86 / 0.83 |

- **The control** gives the same stop as Isaac's own restLoad, so the explicit path changes
  nothing.
- **Doubling restLoad** raises the locked stop at mu 0.5 by the factor the filter predicts:
  1.385 x frictionVsSlip, against 1.154 x. Neither other candidate moves.
- **At mu 1.0, doubled,** the wheels no longer lock (slip -0.30). The car stops at the
  requested -12 m/s^2, 1.22 g, because its grip is now above the request. That is past both
  other candidates' ceilings too.
- **Yaw** stays under 0.003 rad/s, so the lower lateral stiffness did not enter.

**Candidate 2 is confirmed:** PhysX's default load filter, (0, 0.2308) to (3, 3), which
omni.physx applies and Isaac's schema does not expose, gives the car 1.154 times its friction.
Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/restload`, with
the script, the analysis and the test-only diff.

## Fix plan (for 133's review, before any code)

**The change (aib).** Every friction aib writes to a PhysX tyre is divided by 1.154
(`FILTER_GRIP` = 0.2308 + (3 - 0.2308) / 3, named with this issue). That covers the friction
table's default value at build, `--set tire_friction`, the per-axle overrides, and the surface
layer's per-substep `set_wheel_friction`. Dividing at those points means nothing upstream
changes: the spec's mu, scensim's surface map and the ECU's assumptions stay as they are. The
car's limit is then the spec's mu, exactly, while every wheel carries 0 to 3 rest loads. The
filter cannot be set (not in the USD schema), and a restLoad choice cannot make it the identity,
since filter(x) / x = 0.9231 + 0.2308 / x is 1 only at x = 3 and clamps above.

**What it leaves.**
- **Per wheel.** A wheel's grip is (0.9231 + 0.2308 / x) / 1.154 of mu times its load: 1.20
  at half its rest load, 1.0 at rest, 0.90 at twice, 0.87 at three. The total is exact. Under
  load transfer the light wheels or axle get more than their share, which shifts the balance
  in a corner (the inside wheels) and front to rear in a stop. That is PhysX's tyre as built;
  the fix does not change it.
- **Lateral stiffness.** It reads filteredLoad / restLoad, so it does not move with the
  friction. The force's saturation term K = stiffness x slip / (mu load) rises by 1.154, so
  the tyre reaches its (now lower) limit at a smaller slip, as a tyre with that mu should. aib's
  lateral stiffness values were tuned with the filter in place. They stay as they are, and the
  cornering checks below show whether they need a second look.
- **Every car.** The Mustang drift car and the MuSHR use the same PhysX tyre and get the same
  factor. The drift car was tuned on the over-grip (243's 057/058), so its numbers move. 243
  should hear before it lands.
- **Hashes.** isaac_physics_hash moves (the rig's friction). The spec and its physics_hash do
  not.

**What was measured on the over-gripping tyre, and has to be re-run after the fix.**
- **Issue 106's ABS and regen order** (regen_60, regen_30 at mu 0.2, 0.3 and 1.0). The
  effective grip falls from 1.07 to 1.0 times the set mu, so at the same request each wheel
  slips more, and both controls act sooner. The order depends on the two releases, 0.15
  against ABS's 0.2. It should hold, but B's margin was one ECU step (rsc 7, ABS 8), so 106's
  table is re-run whole and judged by its written rule. 106's condition 4 (B at least 0.85 mu g)
  is predicted to hold: ABS now reaches about 0.92 to 0.93 mu g, against 1.06 to 1.08 before.
- **The dry set:** launch, brake_100 (39.54 m now, predicted about 42 m), start_flat,
  start_up, hold_camber.
- **Issue 100's Isaac validation and reference reruns,** not yet run, so they run after the
  fix.
- **Any Isaac-vs-CARLA braking or cornering comparison** made before it.

**Tests.**
- **aib unit:** the rig writes the spec's mu / FILTER_GRIP to the table, to the overrides and
  to `set_wheel_friction`.
- **steptest:** the locked `limit_brake` at mu 0.2, 0.5 and 1.0 gives frictionVsSlip x mu g,
  0.83 mu within 0.01. With ABS it gives 0.92 to 0.93 mu g, under 1.0 at every mu.

## Fix

**The change.**
- **aib ff5e72b**: `aib.tyre_friction`.
  - `LOAD_FILTER = ((0, 0.2308), (3, 3))`.
  - `FILTER_GRIP = 1.15387`, the filter at one rest load.
  - `physx_friction`, `wheel_share`, and `WheelFriction`.
  - Every friction aib writes to a PhysX table goes through `WheelFriction`. That covers the table
    default at build (the axle's `tire_friction`, which carries `--set` and the axle overrides) and
    `set_wheel_friction`. It writes mu / FILTER_GRIP and keeps the spec's mu as the wheel's value.
- **scensim_isaac_world 7e01d7b**: `surface_layer.PEAK_SPAN = 2.3 / FILTER_GRIP`.
  Spike 4a's 2.3 was fitted with the filter in the cap. The friction that `rig_peaks` is scaled by
  stays the spec's, so the factor is divided once.

**Every Isaac result that depends on grip and was made before aib's 108 commit carries the 1.154.**
A cited number names its aib pin.

**Checked (aib ff5e72b, GPU1, `limit_brake`).** The fix's own test, with the bars set before it:
locked 0.83 mu within 0.01; with ABS 0.92 to 0.93 mu g, under 1.0 at every mu.

| mu | locked / mu | with ABS / mu | with ABS, before the fix / 1.154 |
|---|---|---|---|
| 0.2 | 0.837 | 0.909 | 0.920 |
| 0.5 | 0.826 | 0.940 | 0.936 |
| 1.0 | 0.827 | 0.926 | 0.932 |

- **Locked:** within its bar at every mu.
- **With ABS:** every value is under 1.0 and matches the pre-fix stop divided by 1.154 to
  0.011. But at mu 0.2 (0.909) and mu 0.5 (0.940) it falls outside the 0.92 to 0.93 bar written
  before the run. That bar was the pre-fix runs' rounded range divided by 1.154, and ABS's
  cycling moves a single stop by about 0.01. The bar is 133's to judge; it is not redrawn here.
- **Data:** NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/fixcheck`.
  The first ABS run at mu 0.2 failed fetching Isaac's asset root, a network failure; its log is
  kept, and it was run again.

**Tests.**
- aib's `test_tyre_friction.py`: the gain, the car's grip at any transfer, the per-wheel
  shares, and all four write paths.
- siw's `test_the_rig_peaks_are_spike_4as_over_the_filter`: the peaks fall by exactly
  1/FILTER_GRIP.

### Runs that stay on the pre-fix aib (133, 2026-11-23)

So that their rows compare on one plant, these keep their pinned pre-108 aib:
- P1;
- P4 ours seeds 3 to 5;
- 139's ECU-B and P2 row (b);
- 118's row (a) seed 5;
- 139's engine A reruns after issue 113.

Roadmap 094 records it and names the factor.

### Owed after the landing, on post-108 aib (nothing re-judged early)

| item | who | when |
|---|---|---|
| Issue 106's full table (regen_60, regen_30; mu 0.2, 0.3, 1.0; release 0.15 and its neighbours), judged by its written rule | 241 | after 108 lands, the first GPU free |
| The dry set: launch, brake_100 (predicted about 42 m against 39.54), start_flat, start_up, hold_camber | 241 | with 106's table |
| Issue 100's Isaac validation and reference reruns (vehicle_check, the T3 Isaac suites) | 241 | after the P4 seeds free GPU1 |
| 054 T1's surface-layer peaks: each class's peak lands where the class says | 241 | with issue 100's reruns |
| Isaac-vs-CARLA braking and cornering comparisons made before 108 | 133 assigns; 241 lists the docs that cite one when 108 lands | after the list |
| The drift retune and the race planner's refit (243's verdict below) | 243 | when the user resumes the drift work (on hold since 2026-11-02) |

### The drift work (243, 2026-11-23, read only)

**Verdict:** retune and rerun, folded into the rerun of 057/058 on issue 100's slip denominator
that is already owed. Nothing is held before 108 lands. Results already recorded stand on their
pinned pre-108 aib, and no drift number is cited as current until the rerun.

- **057's ring drift** (R 100 m at 27 m/s, about 0.74 g) was tuned on 1.154 times the grip.
  The same drift now needs about 15 % more of the grip there is, so its steady speed on that
  radius is about 27 x 0.931 = 25.1 m/s. Its slip and countersteer gains need retuning.
- **058's H1 hairpin parameters** have been void since issue 023. Nothing new is lost.
- **The race planner** (autoware-drift `race_planner`) caps each wheel at mu fz, with no filter.
  Its fits against Isaac absorbed the 1.154: L1's grip 0.92, the sliding share 0.8, the fixture
  `test/data/isaac_drift_mustang_dry.npz`, and "model beta diverges from Isaac above 0.6 g".
  All of them are refitted and the fixture regenerated. The planner adopts the per-wheel cap
  exactly: mu (0.2308 fz0 + 0.9231 fz) / 1.154 for 0 <= fz <= 3 fz0, mirroring
  `aib.tyre_friction`'s `LOAD_FILTER` and `FILTER_GRIP`, with a test that the two are equal.
  Its own `PEAK_SPAN = 2.3` copy (`model.py`) becomes 2.3 / FILTER_GRIP.
- **Peak slips fall 13 %.** The drift test (rear axle at least 3 deg past the tyre's peak)
  stays defined, but every absolute slip threshold in the drift tasks and rewards is derived
  again from the new peaks.

Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)/mueff`,
`.../restload`, `.../fixcheck`.
