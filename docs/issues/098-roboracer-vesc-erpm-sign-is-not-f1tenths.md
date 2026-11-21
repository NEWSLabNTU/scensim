# 098: the RoboRacer stand-in VESC had one ERPM sign, and f1tenth's two branches read it oppositely

**Severity**: medium. On f1tenth_system `humble-devel`, the stand-in drive unit's `/odom` reads
the car as reversing at the commanded speed from the first metre. `jazzy-devel` reads the same
telemetry correctly. The W23 tools assume one sign, so a real car's logs (W22) could be read
reversed, depending on the branch and VESC setup it was logged with. **Status**: fixed (scensim, `scenarios/projects/roboracer`).
**Found**: 2026-11-21, scensim 241, roadmap 091 W20 (f1tenth_system driving the RoboRacer example
car on Isaac Sim 6.2).

## What happens

The setup is the example car (`scenarios/projects/roboracer/vehicles/roboracer.yaml`) with the
stand-in drive unit `roboracer_vesc` behind aib's `vesc` vehicle interface. f1tenth_system's own
`ackermann_to_vesc` and `vesc_to_odom` drive it, with `f1tenth_stack/config/vesc.yaml`. It drives
120 s in a walled room at 1.5 m/s. The truth is identical on both branches, 177.2 m driven at
1.48 m/s on average.

| `vesc_to_odom` from | `/odom` speed minus the truth's |
|---|---|
| humble-devel (f1tenth/vesc 153998d) | -2.98 m/s mean, about -1.5 m/s against +1.5 |
| jazzy-devel (f1tenth/vesc 1bc8251) | correct |

The commands are right on both: `/commands/motor/speed` is 6921 ERPM (4614 x 1.5) and the car
moves forward.

## Why

The two branches' `vesc_to_odom` disagree on the sign of the VESC's reported speed:

```cpp
// humble-devel, f1tenth/vesc 153998d (since f1tenth's first commit, "added onboard car")
double current_speed = (-state->state.speed - speed_to_erpm_offset_) / speed_to_erpm_gain_;
// jazzy-devel, f1tenth/vesc 1bc8251 ("Fix typo for offset param get. Flipped sign for odom speed")
double current_speed = (state->state.speed - speed_to_erpm_offset_) / speed_to_erpm_gain_;
```

Neither `ackermann_to_vesc` negates the command (`erpm = speed_to_erpm_gain * speed + offset`).
So humble-devel is written for a VESC that reports forward as a negative `state.speed`, and
jazzy-devel for one that reports it as positive. Which one a real car is depends on its VESC's
motor direction setting and firmware.

`roboracer_vesc` reports `erpm` as the wheels' speed times the gearing, positive forward
(`component.py`, `step_batch`), with no way to change it. aib's `vesc` profile publishes it
unchanged as `state.speed` (`aib.interfaces.vesc_state`), as it should, because the sign is the
component's to state. The W18 sample component reported `-erpm`. That is why W18, on
humble-devel, found `vesc_to_odom`'s speed within 1 % of the truth.

The W23 tools read the positive sign:
- `protocol/quantities.py` reads the speed as `(core_erpm - offset) / gain`;
- `protocol/fit.py` reads the wheel speed as `erpm / erpm_per_wheel`;
- the synthetic "real" bags carry the positive sign.

So W23 agrees with itself and with jazzy-devel. It would misread a car logged with a VESC that
reports forward as negative.

## Expected

The sign is a stated property of the car: a parameter of the drive unit, written with the logs
and read by the tools, not assumed by them. With the sign the user's car has, f1tenth's
unmodified `vesc_to_odom` matches the truth within the stand-in's calibration on either branch.

## Fix

Fixed in the stand-in, not in f1tenth's nodes, which W20 runs unmodified. The sign is a
property of the car, and every tool reads it from one place:

- `roboracer_vesc` has an `erpm_sign` parameter (+1 by default, today's behaviour). It is the
  motor's wiring: the reported `erpm` is the motor's times the sign, and the commands never
  change sign.
- The protocol's `conversion` states the car's `erpm_sign`. `quantities.speed` reads the logged
  ERPM with it, the fit's replay turns the logs into the commands' sign with it, and
  `twin_runs.py` makes the twin report with it unless the ego config sets the component's own.
- Tests: the component flips only its telemetry, the speed reads the same from logs of either
  sign once the conversion says which, and the replay gives identical currents.

W20 runs f1tenth_system as shipped with the parameter set in the run's ego config: -1 for
humble-devel, +1 for jazzy-devel. In 120 s of wall following on either branch, `/odom`'s speed
is 1.2 % above the truth's (RMS error 0.024 m/s).
