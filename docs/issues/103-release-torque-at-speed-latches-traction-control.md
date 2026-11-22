# 103: the sticky-tyre release torque, applied at speed, latches traction control off

**Status:** open (fixed on aib branch issue100-values, landing with issue 100 step 2).
**Severity:** high: a car that trips traction control at a launch never drives again. **Found:**
2026-11-22, scensim 241, in issue 100's ABS and TC retune.

## What happens

aib's `release_sticky` (issue 070) gives each driven wheel a small release torque when the car
is in drive or reverse, asked to move, with no drive torque and its brakes released. It exists
because PhysX's sticky tyres hold a standing car until a wheel gets drive torque. It did not
check that the car was standing.

Traction control can cut the drive to exactly 0 at speed. The release torque then went to the
driven wheels and kept them turning ahead of the road. Traction control read that as wheel
spin and held its factor at 0. The car never drove again:

| t | car | rear wheel (r 0.37 m) | front wheel | motor | delivered | TC factor |
|---|---|---|---|---|---|---|
| 1.30 s | 0.08 m/s | 3.88 rad/s (1.44 m/s) | 0.15 | 340 N m | 3398 | 1.0 |
| 1.65 s | 0.88 | 1.34 | 2.08 | 340 | 637 | 0.19 |
| 1.70 s | 0.88 | 3.75 (1.39 m/s) | 2.17 | 340 | 0 | 0.0 |
| 3.50 s | 0.73 | 3.68 | 1.83 | 340 | 0 | 0.0 |
| 8.00 s | 0.35 | 2.91 | 0.90 | 340 | 0 | 0.0 |
| 14.0 s | 0.12 | 2.42 (0.90 m/s) | 0.32 | 340 | 0 | 0.0 |

This is aib.steptest's `launch` test: full request from rest, on the Isaac Model 3. The run used
issue 100's new slip denominators (1, 1 and 0.1 m/s) and the ECU's slip estimate over |v| +
1 m/s. Run on GPU1 of 241 (shared, no timings); logs and CSVs are at NAS `autoveh/logs/2026
SSv2 on CARLA/2026-11-22 issue 100 step 2 (241)/abs-est1.0`.

## Why it showed now

Two conditions are needed:
- **A launch whose wheelspin trips traction control.** At the shipped denominators (4 m/s) the
  launch's peak rear slip is 0.17. At 1 m/s it is 1.23: PhysX's slip is closer to the true
  slip, and so is the wheelspin.
- **Traction control cutting all the way to 0.** It did so with the estimate's slip over |v| +
  1 m/s. Over |v| + 4 m/s it cut only part way (factor about 0.7), the drive never reached 0,
  and the release never applied.

Isolated:

| run | launch |
|---|---|
| shipped denominators, estimate offset 1.0 | 0 to 100 km/h in 6.77 s |
| new denominators, estimate offset 1.0, traction control off | 6.41 s |
| new denominators, estimate offset 1.0, traction control on | never: latched at 0.88 m/s |

## Fix

`release_sticky` takes the car's own speed and PhysX's sticky-tyre threshold speed. It applies
the release torque only to a standing car, within that threshold, where the sticky state can
hold it. aib test `test_a_moving_car_gets_no_release_torque` covers it, with 148 of 148 aib
tests passing.

Measured after the fix, with the new denominators and estimate offset 1.0:
- the latch is gone: the drive comes back, and brake_100 is reached and stops in 39.22 m;
- the launch still does not reach 100 km/h in 14 s, and the uphill start rolls back. That is
  traction control at a 1 m/s offset, now that the release torque no longer hides it.

Issue 100 keeps the estimate's offset at 4 m/s, as the car's own computer is independent of
PhysX's denominator (`brakes.estimator.slip_offset`). At that offset, the fixed car launches in
6.43 s (shipped 6.44) and its starts and holds are as shipped.

## Not fixed here

Traction control at a small estimate offset: its slip limits were tuned for 4 m/s. A car that
wants a smaller offset needs TC's limits retuned with it.
