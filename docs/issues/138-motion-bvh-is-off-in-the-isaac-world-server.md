# 138: motion BVH is off in the Isaac world server

**Status:** a record; no work on it yet (133). **Severity:** low today: C6d measures the ego's
own pitch and roll, which the lidar's following of the body covers. **Found:** 2026-11-24,
scensim 118, 086 C6d's sensor check.

## What is the case

Kit enables motion BVH (the RTX renderer's motion through a frame, which an RTX lidar or radar
needs to see an object move within a scan) only through `SimulationApp`'s `enable_motion_bvh`
(`isaacsim.simulation_app`, setting `/renderer/raytracingMotion/enabled` and its masking). The
world server does not set it, aib does not, and the host's `ISAAC_KIT_ARGS` does not. The
deprecated `isaacsim.sensors.rtx` extension, which the world server loads, lists those settings
only in its tests' arguments. So every RTX sensor in a scensim run sees each object where it is
at the render, not as it moves within a scan.

What the lidar does follow: `aib.isaac.sensors.Lidar.before_substep` places it each substep at
the body's full pose with the mount and de-skews each point along that track, so the ego's own
motion within a scan is in the cloud.

## The routes, when it is taken up

- a world-server option (a setting or flag) that passes `enable_motion_bvh=True` to
  `SimulationApp`, off by default; or
- a host setting through `ISAAC_KIT_ARGS` (`--/renderer/raytracingMotion/enabled=true` and the
  masking settings), with no code.

Either way, its render cost is measured first, against C6b's budget run on Haruna (tick p50
and p95), before it is turned on for any judged run.
