# 101: land_pin and check_pins skip an uninitialised submodule silently

**Status:** fixed (9ddce01d: scripts/land_pin.py, scripts/check_pins.py, the pre-push hook through check_pins). **Severity:** high: a cascade can land partial. **Found:**
2026-11-22, scensim 241, in the dry run of issue 100's step 1 cascade; 133 caught the gap.

## What happens

`scripts/land_pin.py` builds its list of components from the submodules that have a checkout:

```python
comps = sorted(p.name for p in src.iterdir() if (p / ".git").exists())
```

An uninitialised submodule, an empty `src/<name>` with no `.git`, is not a component. Its
`deps/` pins are never read, and the cascade does not move it. Nothing says so.

`scripts/check_pins.py` does the same, `if not (component / ".git").exists(): continue`. So the
check that land_pin runs before any push passes over the same component.

## How it showed

The checkout had `src/scensim_carla_world` and `src/autoware_carla_bridge` uninitialised. Both
pin `deps/sim_vehicle_spec` at 478edf4, and acb also pins `deps/autoware_sim_vehicle`. With the
checkout like that, the dry run of
`land_pin.sh --dry-run --onto issue100-step1 sim_vehicle_spec 890adc3 autoware_isaac_bridge 153845e`
listed three components: autoware_sim_vehicle, autoware_isaac_bridge and scensim_isaac_world.
After `git submodule update --init --recursive`, the same dry run listed five; the CARLA world
server and acb were added.

The real run from the first checkout would have pushed a cascade leaving those two at the old
spec. Its check_pins would have passed. A fully initialised clone, such as a gate's, would then
find main red: those two components' deps no longer equal this repository's pin.

## Fix

Both scripts take their components from `.gitmodules`, not from the checkouts on disk, and
refuse an uninitialised one by name, with the command that initialises it, and end with
`git submodule update --init --recursive`, which initialises the whole set at once. Neither initialises
it itself: a check that changes the checkout it checks would hide what it found.

- `check_pins.py` checks every `.gitmodules` submodule. An uninitialised one is a failure,
  `<path>: not initialised, so its deps/ pins cannot be checked: git submodule update --init
  --recursive <path>`, so `just test` and the pre-push hook (`scripts/hooks/pre-push`, which
  calls `check()`) refuse the tree.
- `land_pin.py`'s components are the `.gitmodules` submodules under `src/`. If any is
  uninitialised it exits 2, naming each, before it fetches or changes anything; a dry run
  included.

So every submodule must be initialised to push to main, `third_party/cuda_ndt_matcher`
included, as a `git submodule update --init --recursive` checkout is.

Tests: `scripts/test_pre_push.py::test_an_uninitialised_submodule_refuses_the_push_by_name` (the
hook as git runs it, from a worktree) and
`scripts/test_land_pin.py::test_an_uninitialised_component_refuses_the_landing_by_name`. Both
fail on the old scripts. The two tests that replay check_pins on this repository's history
(`test_check_pins_ignores_a_hooks_git_environment`, `test_it_would_have_refused_the_push_that_broke_main`)
skip a tree that is not fully initialised, as they skip one without the commits.
