# 124: land_pin refuses a target whose submodule tracks a branch other than main

**Status:** fixed (2026-11-24, 243; found in 092 K12's landing). **Severity:** low.

## What is wrong

`scripts/land_pin.py` lands a pin only when its commit is on the repository's `origin/main`
(rule 1, the check at its target loop: `merge-base --is-ancestor <sha> origin/main`). A
submodule whose `.gitmodules` entry names another branch lands its commits there, never on
main. Today that is one: `src/scenario_simulator_v2`, the SSv2 fork, `branch =
managed-ego-unforked`; every other submodule here, and every component's `deps/`, tracks main.
So land_pin refuses any landing that moves the SSv2 pin, naming the commit (below), although
the commit is where CLAUDE.md's submodule rule wants it.

land_pin knows the tracked branch already: `tracked_branch()` reads it from `.gitmodules`, and
the pushed-pin check (`on_remote`) uses it. Only the target check, and the cascade's handling of
components (their deps read from, new commits made on and pushes to their main), assume main.

## How it was found

092 K12's landing (scensim 0cc054d8, 2026-11-23) moved the SSv2 fork's pin to its
`managed-ego-unforked` commit 38d645ac4 together with code here that needs it. land_pin cannot
take that commit as a target, so 133 approved landing it by hand: the fork's branch pushed
first, then the pins and code here by fast-forward after the full gate. Reproduced on main
d3134900 in a clean checkout:

```
$ scripts/land_pin.sh --dry-run scenario_simulator_v2 38d645ac4
scenario_simulator_v2 38d645ac4 is not on its origin/main: land it there first
```

## Fix

- A target's commit is checked against `origin/<the branch src/<repo> tracks>` (`tracked_branch`
  on this repository's `.gitmodules`, else main), and the refusal names that branch: `F <sha>
  is not on its origin/fork (the branch src/F tracks): land it there first`.
- The cascade works on main only (133 chose this over teaching it other branches: nothing under
  `deps/` tracks another branch). A component it would move whose `src/` entry tracks another
  branch, or whose moving `deps/` entry does, is refused in a dry run too, naming the component,
  the entry and the branch: `C: src/C tracks feat, ...`, `C: its deps/A tracks feat, ...`. A
  target landing as given, with no deps/ to bump, is not a cascade move and lands from its own
  branch.
- Tests (`scripts/test_land_pin.py`): a target on its tracked branch lands (dry run, then for
  real, `check_pins` green); a commit on neither that branch nor main is refused naming the
  branch; a submodule with no `branch =` still lands from main and refuses a commit only on
  another branch; the cascade's two refusals by name.
