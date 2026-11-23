# 132: issue 128's time bound fails on a loaded gate host

**Status:** fixed, landed with siw 31593ab. **Severity:** low: a false failure in the
gate, with nothing wrong in the code. **Found:** 2026-11-24, scensim 241's gate.

## What happens

`test/test_issue_128.py::Cost::test_a_tile_of_a_long_record_is_fast` timed `Corridor.uv` on a
3055-station tile by wall clock against 1.0 s. In 241's gate it took 1.187 s at a load of 84.8 on
24 CPUs, and failed. The code was as landed; the host was busy.

## The fix

A wall-clock bar measures the host as much as the code. The test now measures the culled
call's CPU time (`time.process_time`) against the full loop's on the same tile (80 x 80 points,
so the full loop stays short), and requires the culled one under a quarter of it (about 0.04
measured: 106 of 3054 segments kept). A loaded host slows both calls alike. The algorithmic
guard, a tile keeping under 200 segments, was already load-proof and stays.

The live guard of issue 128 (`fixture_cost --guard-ms`, the first frames' largest wall time
against 10 s) stays wall clock. It bounds what the bridge bounds, its Step timeout, which is
wall clock too. It runs only by hand on a run's own host, never in the gate.
