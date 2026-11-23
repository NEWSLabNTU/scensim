# 118: steptest exits 0 when it raises

**Status:** fixed (aib a838261, scensim_isaac_world 74aa94c): the five entry points exit
nonzero when they raise, through `aib.app_exit`; the follow-up (aib 4e8d684,
scensim_isaac_world c2afbc0) covers the other entry points but `spikes/`. **Severity:** low: a failed step test
looks like a passed run with nothing measured. A sweep reads it as a run, and the cause is lost.
**Found:** 2026-11-23, scensim 241, in issue 106's table on post-108 aib.

## What happened

The first run of issue 106's rerun (`aib.steptest --only regen_60`, tyre friction 0.2) ended
in 20 s with rc 0. Its summary had no test:

```
  "isaac_physics_hash_is_the_cars": false,
  "tests": {}
}
[18.788s] Simulation App Shutting Down
```

The log had no traceback. Run again with the exception printed, it was:

```
  File ".../aib/steptest.py", line 255, in measure
    "from_kmh": round(seg[0]["v"] / KMH, 1),
IndexError: list index out of range
```

On the lower grip the car reached 60 km/h only at 23.4 s of the test's 24 s. R had 9 rows,
and `measure` drops the first 10. That run was a test design matter, settled in issue 106. The
defect here is that steptest hid it.

## Why

`aib.steptest.main` runs the tests in a `try` whose `finally` writes `summary.json`, prints
it and calls `app.close()`. `SimulationApp.close()` ends the process with status 0. So an
exception raised in the `try` never reaches Python's top level: no traceback is printed, and the
exit status is 0. Verified with `aib.ground_check` (issue 117), whose first version called
`sys.exit(1)` after `app.close()` on a failure and exited 0.

`aib.runner` met the same thing earlier and logs the exception in an `except` before its
`finally` ("a camera's CameraInfo assertion once stopped the runner after one frame,
silently"). Its exit status is still 0.

Other entry points with `app.close()` in a `finally` and no `except` (not checked further):
- `scensim_isaac_world/world_server.py`: an exception out of the shell's `run` loop. The shell
  catches a request's exception itself, so this would be one in the loop.
- `scensim_isaac_world/course/lip_drive.py` and `arc_drive.py`.

## Fix

- **A helper in aib, `aib.app_exit.close(app, failed)`:** it calls `os._exit(1)` when `failed`,
  after flushing stdout and stderr, and `app.close()` otherwise. It is pure, and testable with
  a fake app and a fake exit.
- **steptest:** an `except BaseException` logs the exception with its traceback and records it
  in the summary (`"error"`). The `finally` still writes the summary, then calls
  `close(app, failed)`. A failed run exits 1, and its summary says why.
- **aib.ground_check** (issue 117) uses the helper in place of its own `os._exit`.
- **Every entry point gets the helper (133, 2026-11-23):** steptest, ground_check,
  `world_server.py`, `course/lip_drive.py` and `course/arc_drive.py`. A silent exit 0 is the
  same defect wherever it is, and the world server's exit status is what its supervisor and
  play_launch act on.

Tests:
- **The helper,** with a fake app and a fake exit: a failed call exits 1 without closing, and a
  passed call closes.
- **One test per entry point** that makes it raise and asserts a nonzero exit status. A test
  runs without Isaac where its entry point can (a fake `SimulationApp` module); otherwise it
  runs under Isaac's Python with a forced failure.

## What the fix does

Two things in Isaac 6.2's `SimulationApp` (`isaacsim.simulation_app`) decided its shape:

- **`close()` takes an `exit_code`** (default 0). It runs the same cleanup (replicator's queued
  writes, the stage) and then ends the process with that status, where fast shutdown would end
  it with 0.
- **The app registers an atexit close.** An exception that escapes the entry point is printed,
  and then the interpreter's exit calls `close()`, which ends the process with 0. So an
  exception raised after the app starts but before the entry point's `try` was silent too.
  steptest, lip_drive and arc_drive all built Isaac's World before their `try`.

`aib.app_exit` (pure, no Isaac import):

- `code_of(exc)` writes the traceback to stderr and returns the status: a `SystemExit` keeps its
  own (None is 0), a `KeyboardInterrupt` is 130, anything else 1. Ctrl-C under Kit does not
  reach it as a KeyboardInterrupt: Kit's SIGINT handler shuts the app down and raises
  `SystemExit(0)`, so a stopped world server still exits 0, as before (133: fine, a stop is not
  a failure).
- `close(app, failed)` calls `app.close()` for a run that passed. For a failed one it calls
  `app.close(exit_code=code)`, and should that return, refuse the argument (an older Isaac) or
  raise, it flushes and calls `os._exit(code)`.

Each entry point now opens its `try` right after the app, maps an exception with `code_of` in an
`except BaseException`, and ends with `close(app, code)` in its `finally`:

| entry point | change |
|---|---|
| `aib.steptest` | the `try` now covers the stage and the vehicle too; a failure is in `summary.json` as `"error"`, and `"tests"` holds what finished |
| `aib.ground_check` | the helper in place of its own `os._exit` |
| `world_server.py` | the part after Kit's start moves into `_serve`, unchanged; a refused configuration still exits 2 before Kit starts |
| `course/lip_drive.py`, `course/arc_drive.py` | their own `finally`, which writes what they measured, sits inside the new `try` |

## Checks

`aib.fake_kit` runs an entry point with no Isaac: every module under omni, pxr, carb, usdrt and
isaacsim is a stand-in, `SimulationApp` closes and exits at exit as 6.2's does, and Isaac's
`World()` raises a marked error. A test runs the entry point under it and asserts a nonzero
status and the marked error's traceback in the output.

| test | before the fix | after |
|---|---|---|
| aib `test_app_exit`: the helper (an app with and without `exit_code`, a passed run, `code_of`'s statuses) | (new) | pass |
| aib: steptest raises | fail (exit 0, no summary) | pass (exit 1, `"error"` in the summary) |
| aib: ground_check raises | pass (its own `os._exit` since issue 117) | pass |
| scensim_isaac_world `test_app_exit`: world server raises | fail (exit 0) | pass |
| the same: arc_drive raises | fail (exit 0) | pass |
| the same: lip_drive raises | fail (exit 0) | pass |

aib's suite: 167 passed. The world server's test fakes `zmq` too, which the shell's `bind`
imports (`FAKE_KIT_EXTRA=zmq`).

## Not covered

These also start a `SimulationApp` and end with its close, status 0, whatever the run did (not
changed by the first fix, for a decision; the follow-up below covers all but `spikes/`):

- `aib.runner`, the stand-alone Isaac ego (`just isaac-ego`): it logs a failure, then exits 0.
- scensim_isaac_world: `course/fixture_drive.py`, `course/fixture_cost.py`,
  `course/isaac_check.py`, `scripts/step_response/isaac_step.py`, and the scripts in `spikes/`.
- scensim: `scensim_batch/scripts/` (`agreement_run.py`, `check_resident.py`, `eval_drift.py`,
  `eval_leadbrake.py`, `smoke_articulation.py`, `smoke_drift.py`, `smoke_env.py`) and
  `scripts/svl_import/isaac_probe.py`.

## Follow-up (133, 2026-11-23)

The entry points above, in this order, with the same test pattern; `spikes/` stays out
(exploratory scripts):

1. **The evaluations P2 and P4 run on, now:** `scensim_batch/scripts/eval_drift.py` and
   `eval_leadbrake.py`. A silent crash there could read as a missing or partial evaluation.
2. The rest of `scensim_batch/scripts/` and `aib.runner`.
3. scensim_isaac_world's `course/fixture_drive.py`, `course/fixture_cost.py`,
   `course/isaac_check.py` and `scripts/step_response/isaac_step.py`.

**Step 1.** Both evaluations are Isaac Lab scripts: their code runs at module level after the
app, so an exception escapes to Python's top level and the app's atexit close then ends the
process with 0. Two helpers in `aib.app_exit` (aib 4e8d684) cover such scripts:

- `guard(app)`, called right after the app, wraps `sys.excepthook`: after Python prints the
  traceback it ends the process at once through `close(app, 1)`, before any atexit handler
  runs. `guard()` with no app serves a wrapper that runs a training script and never holds its
  app: a flush and `os._exit(1)`, without Kit's cleanup.
- `run(main)`, for the script's `__main__`: Python calls no excepthook for a `SystemExit`, and
  these scripts `raise SystemExit("why")` after their app starts (eval_drift with no
  checkpoints, eval_leadbrake on a replay mismatch). `run` maps any exception out of `main`, a
  `SystemExit` with a status among them, and ends through `close` on the guarded app.

Each script gains the two calls; a run that ends normally still calls `app.close()`.

`eval_drift.py` runs under `run_p2.sh`'s PYTHONPATH, which now includes aib's source (133: one
helper, not a copy); `run_p4.sh`'s had it. The fix changes only the exit status, not a score.
The P2 evaluations already under way stay on `eval_drift.py` at the seeds' commit (4c5d7a7a)
for both rows, so one file scores rows a and b; the fixed one applies to P2 runs started after
it lands. Until then 118 and 139 check the evaluations' records rather than their exit codes
(133; also in roadmap 094's P2 row).

| test | before | after |
|---|---|---|
**Step 2.** The rest of `scensim_batch/scripts/` gains the same two calls:
`agreement_run.py`, `check_resident.py`, `check_engine_a_layout.py` (its own `os._exit(rc)`
kept for a check that fails), `smoke_articulation.py`, `smoke_drift.py`, `smoke_env.py` and
`smoke_physx_vehicle.py`. The training wrappers `train_drift.py` (P2) and `train_leadbrake.py`
(P4) run WheeledLab's and Isaac Lab's training scripts: `train_drift` guards the app its patched
`startup` returns, `train_leadbrake` guards with no app (Isaac Lab's train.py builds it), and
both run the script through `run`. As with the evaluations, this applies to runs started after
it lands. `aib.runner`, the stand-alone Isaac ego: its `try` now starts right after the app (it
built the World and the ROS node before it) and ends through `close`; its own SIGINT and SIGTERM
handlers still stop the loop and end with 0.

**Step 3.** scensim_isaac_world (c2afbc0): `course/fixture_drive.py` and
`course/fixture_cost.py` as lip_drive (the `try` right after the app); `course/isaac_check.py`
closed its app and then returned its check's status, which Kit's close never let out, so a
failed check now ends with 1 as one that raises; `scripts/step_response/isaac_step.py`, a
module-level script, is guarded and its `try` ends through `close`.

| test | before | after |
|---|---|---|
| aib `test_app_exit`: a guarded script that raises ends with 1, a wrapper guarded before its app likewise, `SystemExit("why")` out of `run(main)` with 1 and `SystemExit(0)` with 0, one that ends with 0 | (new; unguarded, a raise ends with 0) | pass |
| aib: aib.runner raises (its ROS modules stood in for) | fail (exit 0) | pass |
| scensim_batch `test_app_exit`: each of the ten scripts above but agreement_run raises after its app | fail (exit 0) | pass |
| the same: every script that starts an app calls `app_exit.guard` and `app_exit.run` (read from the source; agreement_run's test, whose checks before its app need a recorded run) | fail | pass |
| scensim_isaac_world `test_app_exit`: fixture_drive, fixture_cost, isaac_check, isaac_step raise | fail (exit 0) | pass |

`aib.fake_kit` gained what these need: `FAKE_KIT_FAIL` names where an entry point that builds no
World fails, a faked callable (`module.name`) or a faked module's import (`import:module`); with
Isaac Lab faked, its `AppLauncher` gives the stand-in app, and with WheeledLab's `wheeledlab_rl`
faked, its `startup` does. The scensim_batch scripts fail at their first torch import after the
app, the evaluations at `load_cfg_from_registry`.
