# 097: t3 compare calls a CARLA the stack did not start "not comparable", whatever it ran

**Severity**: low. The compare of every T3 suite run on a CARLA started outside the stack exits
1 on a launch problem the runs do not have, so a real difference can hide among false ones.
**Status**: fixed (this commit). **Found**: 2026-11-21, swb 243, comparing s5 on CARLA 1.0 (roadmap 083) with
its 0.9.16 reference.

## What happens

The run's script started CARLA 1.0 itself (`CarlaUnreal.sh -carla-rpc-port=2400 -nosound
-RenderOffScreen -quality-level=Epic`), because the stack starts only the CARLA of
`carla.root`, 0.9.16 on that host. All 12 runs passed. `t3.py compare` still reported:

```
problem: CARLA launch differs, not comparable: the results' quality epic, args [] (not applied:
an external CARLA), the reference's quality epic, args []
```

The quality and the arguments are the same as the reference's. Only `applied` differs.

## Why

`simulator.py` records a run's CARLA launch in `provenance.carla` as the testbench's requested
`quality` and `args`, plus `applied`: true when the stack started CARLA with them, false for an
external one, whose real launch the stack never sees. `t3.carla_launch` keeps all three, and
`launch_problem` compares the dicts whole. So an external CARLA never equals a reference the
stack started, even when it ran exactly that launch. It also equals a reference from another
external CARLA whatever either ran, because the requested values are compared, not the ones
that ran.

The run's `provenance.carla` from the s5 run:

```
{'owner': 'external', 'version': '1.0', 'argv': None, 'quality': 'epic', 'args': [],
 'applied': False}
```

## Fix

Compare the launch that ran, recorded.

1. When the CARLA on the port is local, the stack can read the launch from the process that
   listens on it (`/proc/<pid>/cmdline`: `-quality-level=`, and the rest as `args`), and record
   it with `applied: "observed"` and `argv`.
2. `t3.launch_problem` compares `quality` and `args` only. An external launch it could not
   observe becomes a note ("unverified: an external CARLA"), not a problem.

Both are done. `simulator.observed_launch` finds the listener through `/proc/net/tcp` and
`tcp6` and the process's socket links, and accepts only a CARLA program (the engine or its
launcher script) as the listener; `decide` records the result for an external CARLA on this host,
in `auto` and in `external` mode. A listener owned by another user cannot be read, and its
launch stays not applied. `t3.launch_problem` compares quality and args; a launch of
either side that is not verified is a note, and a mix of verified launches in the results is
still refused at record.
