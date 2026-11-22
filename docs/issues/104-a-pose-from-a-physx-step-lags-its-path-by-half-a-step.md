# 104: a pose read after a PhysX step lags its path by half a step

**Status:** open, for 241 (aib). The RoboRacer's synthetic reference is fixed in scensim
(twin_runs.py, 091 W10). **Severity:** low for full-size cars, medium wherever a sideslip or a
velocity is derived by differencing poses. **Found:** 2026-11-22, scensim 118, in 091 W10.

## What happens

A PhysX step moves a body's position along the step's new velocity, already turned with the
new heading. Read after the step, the pose (position and orientation) is the body's. But the
chord between two successive positions leads the headings read with them by half a step: the
heading lags the path. So a sideslip
or a heading rate taken from differenced poses comes out shifted by r dt / 2, where r is the yaw
rate and dt the physics step.

The body's own velocity (`state.velocity`, which aib publishes as the twist) has no such shift.
Only quantities derived from the pose sequence do.

## How it showed

091 W10's tyre fit reads the sideslip from a synthetic motion-capture pose. twin_runs.py wrote
`state.position` and `state.quat` at 100 Hz from the RoboRacer twin at 240 Hz. Against the
body's own velocity logged beside it, on M5's steady circles, the sideslip from the pose was short
by 0.0021 s x r at every speed and steering angle:

| circle | sideslip from the pose | from the body's velocity |
|---|---|---|
| 0.1 rad, 1 m/s | -0.00636 rad | -0.00699 rad |
| 0.2 rad, 1 m/s | -0.01284 | -0.01410 |
| full lock, 3 m/s | -0.2862 | -0.2920 |

The offset is proportional to r and independent of the speed, so it is a time shift, not a
lever arm. 2.1 ms is half of the 4.17 ms step. With the heading read r dt / 2 later, the pose's
sideslip agrees with the body's to 1e-5 rad. At small slip the shift was 9 % of the sideslip,
and through it about 10 % of the fitted tyre stiffness. scensim's twin_runs.py now writes the
heading that way (091 W10, scensim 364e8c65), because a real motion-capture pose has no physics
step.

## Where else it applies

`aib.sensing.ground_truth` publishes the same state: `state.position` and `state.quat` as the
ground-truth odometry's pose, `state.velocity` and `state.angular_velocity` as its twist. Its heading
lags its path by the same half step. The size is r dt / 2 with the scene's physics step:
2.1 ms at 240 Hz, 8.3 ms at 60 Hz. For a car at r = 0.3 rad/s at 60 Hz that is 0.0025 rad of
heading against the path's tangent.

A consumer that takes the twist is unaffected. One that differences successive ground-truth or
`sim_pose` poses for a velocity, a sideslip or a heading rate sees the shift. Not checked here:
which consumers do that (the gap oracle, the Isaac world server's gap trace, the drift layer's
slip measures), and whether any of them read a sideslip small enough for 2 to 8 ms to matter.

## For 241

Either note it where ground truth is documented (the pose is exact; a pose-derived rate lags it by
half a step), or, if a consumer needs pose and path consistent, write the heading r dt / 2 on, as
twin_runs.py now does. That changes what the pose means, so it is aib's choice and not done
here.
