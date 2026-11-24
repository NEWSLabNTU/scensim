# 144: a run stepped faster than real time gets rocks that depend on the wall clock

**Status:** open; the fix follows issue 142 (133). **Severity:** high: a run's rocks, and so its
physics, are not reproducible. **Found:** 2026-11-24, scensim 118, issue 142's Isaac proof.

## What happens

The road's tiles (with their rocks' placement) are made by `TileProcess`, a worker process on the
wall clock, about 5 tiles a second in Isaac on this host. Nothing ties a step to them: a world
stepped faster than real time (`fixture_cost` and `fixture_drive` step as fast as they can, 55 to
80 frames a second against real time's 20) moves the car further per wall second than the worker
keeps up with. On Haruna's rocks map at 10 m/s, 142's code had its in-path rocks load 2.9 m ahead
at 80 frames a second and, the same drive held to the wall clock, when their tiles came within the
32 m reach. Which rocks exist when a wheel reaches them, and so what the car meets, depends on
the host's load and the pace: two runs of the same drive need not agree.

## The fix (planned)

Each frame, before its steps, the tiles within ROCK_REACH and the frame's travel of every car are
waited for, with a bound (`RoadLayer.ready_around`, as a placed car's): a run at real time waits
about nothing, a faster one slows to the worker's pace. Proof: the same drive at two paces gives
identical rock load frames.
