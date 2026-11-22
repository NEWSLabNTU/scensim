# 106: since issue 100, ABS acts before regen slip control on the Model 3

**Status:** fixed (sim_vehicle_spec 9ceb8cb, sim_vehicle_ecu 99505b0, autoware_sim_vehicle 2b4a665, aib 23ef5fb). **Severity:**
medium: on low grip, a regen-only stop lost all regen for the rest of the stop. **Found:**
2026-11-23 by 139, in 241's review of EvBatch.

## What happens

The Model 3's ECU has two controls on a braking wheel's slip:
- **Regen slip control** gives regen up on the driven wheels (sim_vehicle_ecu `regen_slip`). It
  releases past `regen_slip_release`, 0.25 from the ECU's defaults.
- **ABS** releases each wheel's friction brake past `brakes.abs.slip_release`. Issue 100 set
  this to 0.2.

Since issue 100, ABS's threshold is the lower of the two, so ABS acts first. Its first action
sets `abs_event`, which removes regen until the stop ends. On a regen-only stop on low grip,
the friction brakes then did all the braking, and regen slip control never acted.

No spec could have set the value: the calibration read `powertrain.regen_slip_control`, but
sim_vehicle_spec's schema did not list the key.

## Measurement

The tool is aib.steptest's `regen_60` and its new `regen_30`. Each runs at constant speed, then
-1.5 m/s^2 (R, regen alone) for 2 s, back to speed, then -4 m/s^2 (B, regen and friction) for
2 s. The low-grip runs used tyre friction 0.3 and 0.2 (`--set tire_friction`; the ECU still
assumes 1.0, as on ice). The effective peak grip is about 1.07 times the set value (issue
108), so 0.21 and 0.32.

`regen_30` exists because on 0.2 the car does not reach 60 km/h within the test's 24 s. Order
is judged at every ECU step (1/60 s): steptest's new STEP_LOG writes the ECU's regen factor and
ABS factors at every step.

The pass rule was written before any result was read (2026-11-23):
1. **Order:** regen slip control acts before ABS, or ABS never does.
2. **No rear lockup.**
3. **No yaw excursion:** |yaw rate| < 0.05 rad/s, and |y| moves < 0.2 m.
4. **Deceleration:** R within 15 % of 1.5 m/s^2; B at least 0.85 mu g.

Dry runs must be unchanged. The choice is the highest release that passes.

Two amendments were made after seeing results:
- **Step resolution.** Condition 1 was first judged on 0.05 s rows, and the rule's "past the
  first 10 rows" skipped the first 0.5 s, where both controls act. It is judged on the whole
  phase, by ECU step.
- **B's order.** In B the request exceeds the grip, so ABS must engage. Condition 1 was amended
  for B to "regen slip control's first action before ABS's first action". Under the original
  wording, which required regen to have fallen below 80 % before ABS acted, B fails at every
  value.

Results by ECU step. "rsc" is regen slip control's first action, "ABS" is ABS's first action,
and "never" means it did not act:

| release | mu 0.2 R from 60 | mu 0.2 R from 30 | mu 0.2 B from 30 | mu 0.3 B from 60 |
|---|---|---|---|---|
| 0.25 (before) | ABS 19, rsc never: fail | ABS 12, rsc never: fail | ABS 7, rsc 8: fail | ABS 15, rsc never: fail |
| 0.19 | both 19: fail | both 12: fail | rsc 7, ABS 8 | both 15: fail |
| 0.18 | rsc 18, ABS never | both 12: fail | rsc 7, ABS 8 | rsc 14, ABS 15 |
| 0.15 | rsc 16, ABS never | rsc 11, ABS never | rsc 7, ABS 8 | rsc 13, ABS 15 |
| 0.10 | rsc 12, ABS never | rsc 9, ABS never | rsc 7, ABS 8 | rsc 11, ABS 17 |

- **Conditions 2 to 4** hold in every run.
- **Regen kept at 0.15:** R kept about 1400 N of regen, against 0 N at 0.25, at the requested
  1.5 m/s^2.
- **B's margin** is one ECU step (rsc 7, ABS 8). That is enough, since ABS must engage there.
- **The 0.05 s rows had it backwards** for mu 0.2 B at 0.15: they put ABS first.
- **Dry** (mu 1.0) is identical at every value.

0.15 is the highest release that passes.

## The detector at 0.15

At 0.15, sim_vehicle_ecu's issue 011 guard failed. That guard holds when a driven wheel comes
down from a wheelspin into regen: a settling wheel must not read as a braking slip. When
`regen_spin_settle` (0.1 s) ended, the settling wheel was still slowing past the car by
11.5 m/s^2. That is over `regen_slip_growth` (9.81), so it read as a growing slip: regen was
cut, and a false axle grip of 0.16 was kept (and, at 0.001/s, kept for the run). The excess had
been falling every step: 57, 38, 25, 17, 11.5, then -3 m/s^2. A tyre past its peak holds or
raises it.

The fix: `growing` now holds only while the excess is not falling, in the scalar and in
EvBatch alike. Tests:
- **test_a_wheel_down_from_a_wheelspin_at_a_low_release_is_not_a_slip:** the drift car and the
  Model 3, at 0.15 and 0.25, from a wheelspin of 1.3 and 1.6 times the road's speed.
- **test_on_ice_a_low_release_still_finds_the_grip:** both cars, at 0.15.
- **test_a_wheel_settling_from_a_wheelspin_is_the_scalar_cars:** the batch, bit for bit.

Each fails without its half of the change.

**Not covered:** from a wheelspin of 2.0, the drift car at 0.15 still trips. It trips through
`short`, the car's deceleration still lagging, not `growing`. The Mustang keeps 0.25, where it
does not trip; the Model 3 at 0.15 does not trip at 2.0.

## Verified on the fix

Rerun at aib 23ef5fb, which pins sim_vehicle_ecu 99505b0 and sim_vehicle_spec 9ceb8cb. The
spec's own 0.15 was used, with no `--set` of the release. Every phase gives the same steps as
the 0.15 row above, and conditions 2 to 4 hold.

The dry set is as issue 100 left it:
- launch 6.428 s;
- brake_100 39.54 m;
- start_flat 0.2845 m;
- start_up 3.65 m;
- hold_camber 0.128 cm sideways in 60 s;
- regen_60's -1.5 m/s^2 all regen, with no friction torque.

## Fix

- **sim_vehicle_spec:** the schema gains `powertrain.regen_slip_control`, its twelve fields.
  The Model 3 sets `slip_release: 0.15`. The Mustang writes the 0.25 it had, so it is
  unchanged. The key is in ONBOARD_COMPUTER, so physics_hash does not move.
- **sim_vehicle_ecu:** the default `regen_slip_release` is 0.15, the Model 3's. The detector
  change goes into the scalar and EvBatch.
- **aib:** steptest gains `regen_30` and STEP_LOG.

Data: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-23 issue 106 and 108 (241)`.
