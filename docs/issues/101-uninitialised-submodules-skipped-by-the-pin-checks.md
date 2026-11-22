# 101: an uninitialised submodule was skipped by the pin checks

**Status:** fixed. **Severity:** high. **Found:** 2026-11-22, scensim 241 (a tree with
`src/scensim_carla_world` and `src/autoware_carla_bridge` not checked out).

## What happened

`scripts/land_pin.py` and `scripts/check_pins.py` took their components from the checkouts
that existed, `(p / ".git").exists()`, not from `.gitmodules`. A submodule that was not
initialised was therefore left out, silently:

- `check_pins.py` skipped its deps/ pins and still printed `0 mismatch(es)`, so `just test` and
  the pre-push hook (`scripts/hooks/pre-push`, which calls `check()`) passed such a tree;
- `land_pin.py` left it out of the cascade: a landing whose dependants included it neither
  moved its deps/ pin nor checked it.

So a pin could reach main with a component's deps/ disagreeing with this repository's pins,
and nothing would say so.

## Fix

- The components come from `.gitmodules` (land_pin: its submodules under `src/`; check_pins:
  every submodule it lists).
- An uninitialised one is refused by name, with the command that initialises it:
  - check_pins reports `<path>: not initialised, so its deps/ pins cannot be checked`, as a
    failure, so `just test` and the pre-push hook refuse the tree;
  - land_pin exits 2, naming each such `src/<component>` before it changes anything.

Tests: `scripts/test_pre_push.py::test_an_uninitialised_submodule_refuses_the_push_by_name` and
`scripts/test_land_pin.py::test_an_uninitialised_component_refuses_the_landing_by_name`. Both
fail on the old scripts.
