# 186: every `env -i` gate skips the Isaac's-Python lane, and scensim_batch's suite there needs pytest

**Status:** open (243; numbered by 133 on 2026-11-25; the fix to be planned before any code).
**Severity:** low. The Isaac world server's suite in Isaac's own Python, where the world server
runs (issue 090), has not been part of a scensim gate run from a clean environment. When it is
run, `scensim_batch`'s suite fails there on an import, not on its code.
**Found:** 2026-11-25, scensim 243, gating issue 161 (scensim 3d334cf7).

## What happens

1. **The lane is skipped.** scensim's `just test` runs `scensim_isaac_world`'s,
   `scensim_sampler`'s and `scensim_batch`'s suites in Isaac's Python only when `ISAAC_ROOT` (a
   host setting) names an install; otherwise it says so and skips them. The gate scripts run
   `just test` under `env -i` with no `ISAAC_ROOT`, in a worktree with no `.env` of its own
   (`just`'s `dotenv-load` finds none there). So every such gate log says:

       skipped: scensim_isaac_world's, scensim_sampler's and scensim_batch's suites in Isaac's Python (ISAAC_ROOT names no Isaac Sim install)

   Seen in 161's gate (3d334cf7) and in 092 K9f-b's (69ddf40f). The system-Python lane of the
   same suite runs and passes in both.

2. **`scensim_batch`'s suite fails in that lane.** Run by hand on 161's gated tree, with the
   lane's own command and `ISAAC_ROOT=/var/tmp/aeon/isaac-sim-6.2`:
   - `scensim_isaac_world`: `Ran 525 tests`, `OK (skipped=19)`;
   - `scensim_sampler`: `Ran 143 tests`, `OK (skipped=2)`;
   - `scensim_batch`: `Ran 253 tests`, `FAILED (errors=3, skipped=2)`. All three are
     `ModuleNotFoundError: No module named 'pytest'`. Isaac's venv has no pytest, and the lane
     runs the suite with `unittest`, but the tests import it:
     `src/scensim_batch/test/test_layout.py` (line 5, `import pytest`, since 84dd72de, issue
     113) fails to import, and `test_device.HeldCommand` and `test_device.NoHostSync` import
     `scenarios/projects/roboracer/component/roboracer_vesc/test/test_batch.py`, which imports
     pytest at line 11.

## The fix wanted (a plan before any code)

Two parts:

1. The gate runs the lane. `ISAAC_ROOT` is a host setting, so it is passed through the gate's
   clean environment (or read from the host's settings), so the lane runs wherever an Isaac
   install exists and is said to be skipped only where none does.
2. `scensim_batch`'s suite passes in Isaac's Python: either the lane runs it under pytest there
   (pytest installed in Isaac's venv, or run from it), or the tests stop importing pytest.

Then the check: a gate log with the lane run, not skipped, and all three suites OK in it.
