# 159: a run without its map fetched fails on a missing anchor function

**Status:** fixed 2026-11-25 (241; numbered by 133). **Severity:** low: the run is refused either
way, but the message names the wrong cause.
**Found:** 2026-11-25, scensim 241, in 092 K13's exit check 2, attempt 1: a fresh worktree's
`scenarios/projects/k13_platoon` had no `assets/` (the project's map not fetched), and
`scensim run` refused every run with

```
platoon_town01.xosc: scensim.anchor.street: anchor.west_street.lanelet_at(...): no such
function of the world's anchors (a resolved lane's heading, lanelet_at, local_s)
```

## What happens

A scenario that binds a parameter to the world's anchors (`scensim.anchor.<parameter>`, 092
K9b) is bound before SSv2 starts (`scensim.run.bind_anchors`), from the testbench's
`world.anchors` and the map's resolved file, `assets/maps/<map>/anchors.resolved.json`. With the
map not fetched there is no resolved file, the anchors are only the testbench's stated ones, and
the binding fails on the first function a resolved lane offers (`lanelet_at`). The message is
true but points at the scenario or the anchors, not at the missing fetch. `scensim check` already
names the unfetched map (`map <name> is not fetched`), but a run does not go through it.

## The fix

`scensim.run._anchors_for` (the anchors for a scenario's map, used by the binding and by a
suite's sampler) refuses a project map that is not fetched, naming it and the fix:

```
platoon_town01.xosc: map Town01 is not fetched (assets/maps/Town01), so the world's anchors
are unknown: run `scensim assets fetch` in the project
```

A scenario without anchor bindings is unaffected here (the stack refuses its missing map at
start, as before). Test: a bound scenario on a map not fetched is refused naming the map and the
fetch.
