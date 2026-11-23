# 104: a pose read after a PhysX step lags its path by half a step

**Status:** closed: documented, no pose change (aib 3cd2b7d); no consumer affected. The
RoboRacer's synthetic reference is fixed in scensim (twin_runs.py, 091 W10). **Severity:** low
for full-size cars, medium wherever a sideslip or a velocity is derived by differencing poses.
**Found:** 2026-11-22, scensim 118, in 091 W10.

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

## Resolution (241, 2026-11-23)

aib documents the lag and keeps the pose (autoware_isaac_bridge 3cd2b7d). The pose stays the
body's exact pose after the step, the same as the twist and every other pose Isaac reports.
`aib.sensing.ground_truth`'s docstring and aib.ros's topic notes say to take rates from the
twist. `test_semi_implicit_chord_lead` checks the arithmetic of the step order on a steady
circle: the chord leads the mean heading by r dt / 2 and lies along the new heading. It fails
with the order reversed. It does not prove PhysX's order; the source does.

### PhysX's order, from its source

Read from NVIDIA-Omniverse/PhysX main on 2026-11-23:
- **PGS:** `DyBodyCoreIntegrator.h`, `integrateCore`. The body's velocity is updated with the
  solver's change, then `body2World.p += linearMotionVel * dt`. The orientation follows by the
  closed-form quaternion exponential, the exact rotation for a constant rate.
- **TGS, Isaac's default (aib does not set a solver):** `DyTGSDynamics.cpp`. In
  `iterativeSolveIsland`, each position iteration runs the solve (`processIterationIsland`),
  then `integrateBodies`, which calls `integrateCoreStep`. That function does
  `body2WorldP += delta` and the same closed-form rotation into `deltaBody2WorldQ`, which
  `copyBackBodies` commits. The velocity iterations after it do not move the pose.

### Per step, not per substep

The lag is r dt / 2 with dt the scene's physics step, not a solver or vehicle substep. That
rests on the tyre forces entering the body's velocity once per scene step:
- aib writes the vehicle's controls once per host step, in `Ego.before_substep`
  (`src/aib/aib/isaac/ego.py`), before each `world.step`.
- PhysX's vehicle update computes the tyre forces before the scene's solve. Its own substeps
  (`PhysxVehicleAPI` `Low/HighForwardSpeedSubStepCount` = `physx_substeps`,
  `src/aib/aib/isaac/vehicle.py`) are internal to that update.
- Within the step the solver's substeps then move the body along that one velocity.
- The 091 W10 measurement above agrees: r dt / 2 for the 4.17 ms step, to 1e-5 rad.

Revisit this if forces ever enter inside the solve: TGS's
`eENABLE_EXTERNAL_FORCES_EVERY_ITERATION_TGS`, a per-iteration callback, or aib stepping the
scene once per vehicle substep.

### Consumers

None of these is affected. Each consumer of a PhysX body reads its velocity, and every site
that differences poses works on poses that are set, not stepped. Read at scensim b46f33cc,
aib 3cd2b7d, scensim_isaac_world b5de87b:

| consumer | what it reads | 104? |
|---|---|---|
| gap oracle (`gap_geometry.py`) | SSv2 and sim poses at the same frame; nothing differenced | no |
| bridge `motion()` (`remote/mod.rs`), trace's `"derived"` | the chord / dt, projected on the new heading; only for an entity sent with no twist. On Isaac, the ego and tracked bodies send a twist (`measured`); the rest are kinematic boxes | no |
| bridge `pose_yaw_rate` (`remote/tracking.rs`) | successive SSv2 target yaws | no |
| `scensim_batch/truth.py` | NPCs: yaw differenced (`"derived"`, `"kinematic"`); ego: `st.angular_velocity` (`"measured"`) | no |
| drift task (`tasks/drift.py`) | slip from `root_lin_vel_b`, the body's velocity | no |
| `eval_drift.py` | slip from the body's velocity; lap count from the polar angle's sign and sum | no |
| drift_lap judge | `beta_deg` from autoware-drift, `atan2(vy, vx)` of `velocity_status`, which aib fills from `state.velocity` | no |
| `npc.py` front-entity cone | other entities minus self at the same instant, not one entity over time | no |
| scensim_isaac_world `rock_layer.py` | a rock's speed from successive PhysX positions; no direction | no (first order) |

Two notes:
- **Set poses lag too.** Where a set pose is differenced, there is the ordinary lag of a
  backward difference, which is not this issue. The bridge's derived lateral velocity for a
  kinematic NPC is about -v r dt / 2: 0.025 m/s at 10 m/s, 0.3 rad/s and 1/60 s. No consumer
  found thresholds on an NPC's lateral or angular velocity.
- **The new heading is safe.** The chord lies along the new heading plus the sideslip, so a
  consumer that projects it on the new heading, as `motion()` does, gets the body's lateral
  velocity right. Only a comparison with the mean or the previous heading sees the lead.

### Open

Not checked, and not yet issues:
- **`scripts/coop/*` on CARLA.** These difference positions for a yaw. CARLA's vehicles are PhysX
  too, and whether the same chord lead applies there was not established.
- **`scenarios/projects/roboracer/*`.** `fit.py` and `quantities.py` appear to use a measured
  vy and r; their sources were not traced.
- **scensim_carla_world's twist.** Whether it fills every entity's twist was not checked. That
  decides how many CARLA entities the bridge writes as `"derived"`.
