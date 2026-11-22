# 102: the Isaac Model 3, held still, creeps sideways on a 3 % camber

**Status:** open (measured; fixed in issue 100's retune, step c). **Severity:** medium. **Found:**
2026-11-22, scensim 241, writing issue 100's camber constraint.

## What happens

The Isaac Model 3 is held at a target speed of 0 (Autoware's stop, a request of -1 m/s^2 towards
0 m/s) across a 3 % road camber, the road falling to the car's right. It slides sideways at a
steady 0.082 cm/s, with no sign of settling:

| t | 10 s | 20 s | 30 s | 40 s | 50 s | 60 s |
|---|---|---|---|---|---|---|
| sideways | 0.81 cm | 1.63 cm | 2.45 cm | 3.27 cm | 4.09 cm | 4.91 cm |

Its longitudinal position stays at 0 and its speed at 1e-7 m/s, so the sticky-tyre state is on
throughout. Over a 10-minute park that is about 0.5 m, enough to drag localization off, which is
what csb roadmap 059 N8 fixed once (NDT refused an engage).

Measured with aib.steptest's new `hold_camber` test (branch issue100-values, off aib bf35c0b):
60 s held, gravity tilted sideways by atan(0.03), sideways distance and the rate over the last
30 s. The shipped values: substeps 8, slip denominators 4, 4 and 1 m/s, sticky-tyre threshold
speed 0.2 m/s and time 1 s, longitudinal and lateral sticky damping 200. GPU1 of 241, shared.
The CSV is at NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-22 issue 100 step 2 (241)/`.

## The claim it contradicts

The spec's comment on `isaac.physx.lateral_sticky_tire_damping`, in
sim_vehicle_spec/vehicles/tesla_model3.yaml, reads:

> Lateral as stiff as longitudinal: at 20 the car parked across a 3 % road camber crept sideways
> 1.5 cm/s (0.9 m in 60 s, enough to drag NDT off and refuse an engage); at 200, 0.1 cm in 60 s
> (csb roadmap 059 N8).

The car today, at 200, creeps 4.9 cm in 60 s, 49 times the claim. The test that measured 0.1 cm
is not in any repository now, so what it held differently is not known. The car may have
changed since, through the brakes, the mass or the solver. Or N8's "parked" may have meant
something else, such as gear P. The comment is corrected in the landing that fixes this, and
cites `hold_camber`.

## Why it creeps, as far as measured

A steady rate, from the first second, is what a viscous hold gives. The sticky-tyre damping
resists sideways speed; it does not clamp sideways position. So the camber's pull, about
m g x 0.03 = 530 N for the car, settles at the speed where the damping balances it. That
speed falls as 1/damping, consistent with N8's ratio of 1.5 cm/s at 20 against a much smaller
creep at 200. It never reaches 0. This is a reading, not a proof: step c's retune measures
the creep against the damping, which tests it.

## Fix

In issue 100's retune, step c (aib's sticky-tyre thresholds), aiming at N8's 0.1 cm in 60 s. If
the damping alone cannot reach that without the car stiffening or chattering at rest, the
write-up says so and what it reaches. The other candidates come after the damping: a static
lateral friction at rest, or the hold brake's share at the front.
