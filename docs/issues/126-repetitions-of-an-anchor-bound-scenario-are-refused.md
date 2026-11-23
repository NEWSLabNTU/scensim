# 126: repetitions of an anchor-bound scenario are refused

**Status:** fixed (2026-11-23, 243; filed by 133). **Severity:** medium.

## What is wrong

`scensim run` refused a scenario that binds a parameter to the world's anchors
(`scensim.anchor.<parameter>`, 092 K9b) whenever one invocation expanded it into more than one
run of the same parameter combination: `--repeat 2`, `--seeds 1-3`, or a suite's
`repetitions:` above 1. The refusal named the bound parameter as given:

```
cs1_town01.xosc: scensim.anchor.street: street is bound to the world's anchor
west_street.lanelet_at(0); it is not given (--param, a suite's parameters: or cases:)
```

## Why

`_expand` built every `RunSpec` of one combination with the same `parameters` dict (`combo`
from `grid()`, in each of its three branches). `bind_anchors` then writes each bound value into
`spec.parameters` in place, so after the first spec's binding the second spec's parameters
already held the bound value, and its own binding took it for a value the user had given.

## Fix

`RunSpec.__post_init__` copies `parameters`, so every spec owns its dict, whichever way it was
built. Test: `test_repetitions_and_seeds_of_a_bound_scenario_each_bind_their_own_parameters`
(`scensim/test/test_sampled.py`): `--repeat 2`, `--repeat 3 --seeds 1`, and a suite with
`repetitions: 2` over two values each expand, bind and keep distinct dicts.

## What it touched

The refusal comes at expansion, before any run starts, so no run ever ran with another run's
parameters; an invocation was refused whole. The only anchor-bound scenario in this repository
is `scenarios/projects/k12_commanded/scenarios/cs1_town01.xosc`, whose suite
`suites/lockstep.yaml` repeats; K12's exit runs (092) used one invocation per seed instead.
Sample records (`sample:`) were not affected: each record's spec is built with its own values.
