# 154: testbench check passes a knob value its simulator refuses at run time

**Status:** open (243; numbered by 133). **Severity:** low: no wrong result; a project that
`testbench check` passes cannot run a scenario that binds the knob. Each such run is an error
run (`knob_refused`), found only after its stack has started, and on Isaac a stack preloads for
about 7 minutes.
**Found:** 2026-11-25, scensim 243, in 092 K9e's step 1: k9_cs3's project made an Isaac
project, `k9_cs3_isaac`, with the scenario unchanged. `testbench check` printed `testbench: ok`,
yet the scenario's illumination knob cannot run on Isaac.

## What happens

Two places hold what a static knob value may be (`world.knobs.<knob>.values.<value>`):

- `knobs.problems`, called by `world.problems` for `testbench check`, checks only the value's
  shape: its keys among `weather`, `surface_map`, `mu`, `physics`, and weather parameters as
  numbers. It is not given the simulator.
- `knobs.plan`, called by the run (`run.apply_knobs`) after the stack is up, also holds the
  value to the simulator:
  - on Isaac, a value with `weather:` is refused (Isaac has no weather service);
  - on CARLA, a value with `surface_map:`, or with a `mu` that is not `physics: none`, is
    refused.

The rules are in `plan` only, so the check passes what the run refuses. `world.problems` does
apply the first rule to `world.weather`. Shown on 7dac866a, with both functions called on the
same declarations:

```
world.problems isaac:  []      # world.knobs.illumination.values.day = {weather: {sun_altitude_angle: 60}}
plan isaac:            knob illumination=day: weather parameters, but Isaac has no weather service ...
world.weather isaac:   [('world.weather', "Isaac has no weather service: ...")]
world.problems carla:  []      # world.knobs.surface.values.wet = {mu: 0.7}
plan carla:            knob surface=wet: a friction (mu 0.7), which CARLA's weather does not change ...
```

## Fix

There is one rule per value and simulator, in one function. `plan` raises the rule's message
at run time. `problems`, given the testbench's simulator, reports it for every declared value,
so `testbench check` refuses the value by name and points to the knob, the value and the
simulator. A value with no simulator to hold it to (a declaration read without one) is checked
for its shape only, as today.
