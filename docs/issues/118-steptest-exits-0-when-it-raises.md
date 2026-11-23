# 118: steptest exits 0 when it raises

**Status:** open (doc first; the fix after issue 117 lands). **Severity:** low: a failed step test
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
- **The other entry points** are 133's call: the same helper, or left as they are.

Tests: the helper with a fake app, a failed call exiting 1 without closing and a passed call
closing; and steptest's handling, an exception in a test giving a summary with `"error"` and
`failed` set, checked by reading `main`'s structure if it cannot run without Isaac. Under
Isaac, once: a steptest run that raises (the 0.2 `regen_60` case, on a branch where it still
raises) exits 1 and prints its traceback.
