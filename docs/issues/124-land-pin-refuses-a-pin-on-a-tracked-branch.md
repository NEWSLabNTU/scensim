# 124: land_pin refuses a target whose submodule tracks a branch other than main

**Status:** open (2026-11-24, 243; found in 092 K12's landing). **Severity:** low.

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

## The fix proposed

- A target's commit is checked against `origin/<its tracked branch>` (`tracked_branch(ROOT,
  "origin/main", f"src/{repo}")`), and the refusal names that branch.
- The cascade: no component pins the SSv2 fork under `deps/`, so it never cascades; a
  component whose `deps/` entry names a branch would read, commit on and push that branch. If
  that is more than this issue needs, the cascade keeps main and refuses a component tracking
  another branch by name instead, so the gap is never silent.
- Tests (`scripts/test_land_pin.py`): a target tracking a named branch, its commit on that
  branch and not on main, lands in a dry run; the same commit on neither is refused naming the
  branch.

Until it is fixed, a landing that moves the SSv2 pin is done by hand as K12's was.
