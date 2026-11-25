# 186: every `env -i` gate skips the Isaac's-Python lane, and scensim_batch's suite there needs pytest

**Status:** fixed in code and tests (plan approved by 133, 2026-11-25).
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

## The plan (241; approved by 133, 2026-11-25, before any code)

1. **No pytest in the lane's suites** (issue 090's convention; pytest is not installed into
   Isaac's venv: the lane is Isaac's own Python as shipped, and tools are not installed).
   `scensim_batch/test/test_layout.py` becomes a `unittest.TestCase` (parametrize as `subTest`
   over the same values, `pytest.raises` as `assertRaisesRegex`, `approx` as
   `assertAlmostEqual`), still collected by pytest in the system lane; `scensim_isaac_world`'s
   `_plain` stays that package's, not copied. `test_device`'s two cases take only `CAR` from
   roboracer's `test_batch.py`, which imports pytest: `CAR` moves to a plain module beside it
   (`_car.py`), which `test_batch.py` re-exports and `test_device` imports. A check keeps it
   so: no module under the three suites imports pytest at the top level except behind a
   `SkipTest` guard like `test_installed`'s.
2. **`ISAAC_ROOT` through the clean environment.** A gate passes `ISAAC_ROOT=$ISAAC_ROOT` into
   its `env -i`, as a host setting like `HOME`; the procedure's docs say so. CLAUDE.md's
   `clean=` line needs the same addition, which 133 takes to the user (not edited here).
3. **Loud, not silent.** The lane moves into `scripts/isaac_lane.sh`, which `just test` calls.
   Without a usable `ISAAC_ROOT` it prints to stderr "NOT RUN: the Isaac-Python lane
   (scensim_isaac_world, scensim_sampler, scensim_batch in Isaac's own Python): ISAAC_ROOT
   unset" (or "=<path>, no venv/bin/activate") and exits 0, since a host without Isaac still
   gates; `just test`'s last line repeats it, and when the lane ran, says so with its count.
   Checked by `scripts/test_isaac_lane.py` under the system pytest: `ISAAC_ROOT` unset (the
   banner, exit 0); set to a directory without a venv (the banner naming the path); a stub
   install whose `venv/bin/activate` puts a fake `python3` first (the lane runs it, "ran").
4. **The first real run** with `ISAAC_ROOT=/mnt/evo/aeon/isaac-sim-6.2` in a fresh worktree,
   its prediction committed before it; any failure in Isaac's Python beyond the pytest import
   is recorded here and gets its own issue, not fixed under 186. The batch suite there picks a
   GPU: the run sets `CUDA_VISIBLE_DEVICES` to one that is not P1's or P4's.
5. **Tests:** `scripts/test_isaac_lane.py` (point 3's cases and point 1's check);
   `test_layout` as a TestCase, passing in both Pythons.

**A gate rule (133):** on a host with an Isaac install, a full gate passes `ISAAC_ROOT` and the
lane must run; a gate there whose last line says NOT RUN is not a full gate. A host without
Isaac may still gate, and its landing message says "Isaac lane not run (no install)".

Order: this plan; point 4's prediction; the code and tests; the first real run and its result
here; a full gate with the lane run; a landing request to 133.

**Point 4's prediction (2026-11-25, before the code and the run).** Both of this host's GPUs
are fully used by other work (19 and 22 GB, 100 %), so the first run hides them
(`CUDA_VISIBLE_DEVICES=` empty) instead of picking one: the GPU cases skip, and that is said in
the result. With the fix, the lane's command in Isaac's Python on the gated tree:

- `scensim_isaac_world`: OK, `test_installed` skipped (no pytest there), as in 243's run
  (`Ran 525`, `skipped=19`, give or take the tests landed since);
- `scensim_sampler`: OK;
- `scensim_batch`: OK, 0 errors, its CUDA cases skipped (`test_device`'s and any other
  `skipUnless(CUDA)`), `test_layout`'s cases run.

Held if all three end OK with 0 errors and 0 failures; any other failure is recorded here and
gets its own issue.

**Point 4's result (2026-11-25, 22:23 to 23:12 +08:00): held.** `scripts/isaac_lane.sh` on
365fc9b6 (the dev worktree; rebased onto 2e349687 it lands as db52a744, the same change), `ISAAC_ROOT=/mnt/evo/aeon/isaac-sim-6.2`, `CUDA_VISIBLE_DEVICES`
empty, numpy 2.3.1 (Isaac's):

- `scensim_isaac_world`: `Ran 525 tests`, `OK (skipped=19)`, as in 243's run;
- `scensim_sampler`: `Ran 153 tests`, `OK (skipped=2)`;
- `scensim_batch`: `Ran 259 tests`, `OK (skipped=7)`, 0 errors (243's run: 253, `errors=3`);
  its CUDA cases skipped (Warp reports "no CUDA-capable device", as intended).

The status line: "Isaac-Python lane: ran (937 tests in 3 suites, OK)". No new failure, so no new
issue. One cost, observed: `scensim_batch`'s suite took 2763 s on the CPU in Isaac's Python, so
a full gate on a host with Isaac runs about 50 minutes longer than one that skipped the lane.

