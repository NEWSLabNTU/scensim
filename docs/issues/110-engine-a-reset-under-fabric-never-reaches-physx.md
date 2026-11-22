# 110: under Fabric, engine A's reset never reached PhysX

**Status:** guarded (ScensimEnv refuses engine A with Fabric on, and defaults it off); open for
the real fix, a teleport through PhysX itself so Fabric works. **Severity:** high for any engine A
run with a reset after the sim started (RL: every episode after the first); none for one
episode. **Found:** 2026-11-23, scensim 139, building 094 P4's engine A row.

## What happened

aib's teleport writes a car's pose and velocity to USD (`_set_xform`, the rigid body's velocity
attributes) and puts its vehicle to rest. With `sim.use_fabric` on (Isaac Lab's default), USD
writes made after the sim started never reach PhysX: the car went on from where it was.

## How it showed

094 P4's lead-brake task on engine A, 4 envs: 20 steps of full throttle, `env.reset()`, one step.
The reset put every car at x 5.0 at its record's speed:

| Fabric | x after the step, slots 0..3 (m) |
|---|---|
| on | 5.0, 5.0 (looping in resets: off the road, issue 109 too), 20.55, 20.59 |
| off | 5.45, 5.45, 5.60, 5.64 |

A full brake measured across such a reset stopped 2 to 3 times v^2/2g "long": the car had kept
its pre-reset speed.

## The guard, and what stays open

ScensimEnvCfg defaults `sim.use_fabric` off on engine A, and ScensimEnv refuses engine A with it
on, by name, naming this issue (133: no silent forcing). The lead-brake task sets it off once,
when its config first turns to engine A, and never overrides an explicit choice. The real fix,
a teleport through PhysX (its tensor view or the PhysX interface) so a reset lands under Fabric
too, stays open here; Fabric off costs engine A throughput, which its rows name in their
settings.

## Results it touched (audit, 133)

Every landed engine A result played one episode from `env.reset()` before the sim had stepped:
092 K2.2's smoke (4 envs) and K2.4's agreement rows (1 env). All stand. 094 P4's engine A row is
the first with resets mid-run, and runs with Fabric off.
