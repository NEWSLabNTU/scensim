# 101: land_pin and check_pins skip an uninitialised submodule silently

**Status:** open (found; not fixed). **Severity:** high: a cascade can land partial. **Found:**
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

## The fix, proposed

Both scripts take their components from `.gitmodules`, not from the checkouts on disk. An
uninitialised one is refused by name, with the command that initialises it:

```
src/scensim_carla_world is not initialised: its deps/ pins cannot be read.
Run: git submodule update --init src/scensim_carla_world
```

The scripts may also initialise it themselves, as land_pin already does for the `deps/` of a
component it moves. Either way, never skip one. check_pins's own comment (roadmap 070) names
the same failure for an unknown commit: skipping silently once reported "0 checked, 0
mismatches" over three real mismatches.

## Workaround until then

Run `git submodule update --init --recursive` in the checkout before land_pin, dry run
included, and before check_pins.
