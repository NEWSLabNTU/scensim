# 105: land_pin syncs only one level of deps/, so the gate tests a stale nested checkout

**Status:** fixed (scripts/land_pin.py `sync_tree`, on branch issue100-values). **Severity:**
medium: a correct cascade fails its gate, or a wrong one could pass it. **Found:** 2026-11-23,
scensim 241, in issue 100 step 2's cascade.

## What happens

Before the gate runs, `scripts/land_pin.py` checks out each landing component's `deps/` at the
commits its gitlinks name (`sync_deps`, issue 094 P2's fix). That went one level deep. A
dependency's own `deps/` stayed wherever that checkout last was.

In issue 100 step 2's cascade, scensim_isaac_world's new commit f55a6c3 pins
`deps/autoware_isaac_bridge` at 77ab91b, and land_pin checked that out. But 77ab91b pins its own
`deps/sim_vehicle_spec` at 21bf3dc, and the checkout under
`src/scensim_isaac_world/deps/autoware_isaac_bridge/deps/sim_vehicle_spec` stayed at c11ec1d.
scensim_isaac_world's tests load aib's rig from that nested spec, so five of them failed:

```
ValueError: .../deps/autoware_isaac_bridge/src/aib/config/tesla_model3.rig.yaml: generated from
spec_hash 89cc738fd559, but .../deps/autoware_isaac_bridge/deps/sim_vehicle_spec/vehicles/
tesla_model3.yaml is dffb1d3df1f4: regenerate the rig (aib.gen)
```

The commits were right; a fresh `git clone --recursive` of them passes. The gate failed, and
nothing was pushed. The same gap could also let a wrong cascade pass: a nested checkout left at
a newer commit than the gitlink names would hide a stale pin.

## Fix

`sync_deps` now calls `sync_tree`, which checks out each `deps/` entry at its gitlink and then
recurses into that entry's own `deps/`, to any depth. A commit only in this checkout is fetched
from `src/<name>`, as before.

Test: `scripts/test_land_pin.py::test_a_dependencys_own_deps_are_synced_too`. It fails on the
old script, with D's `deps/C/deps/A` left at A's old commit, and passes on the new one. All 30
land_pin tests pass.
