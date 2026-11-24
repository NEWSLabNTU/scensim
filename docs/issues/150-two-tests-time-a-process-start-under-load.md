# 150: two tests time a process start, and lose under load

**Status:** fixed 2026-11-24 (241; filed by 133). **Severity:** low: tests only; each fails
intermittently on a loaded host, and a gate then fails on code it does not run.
**Found:** 2026-11-24, scensim 241, in the gate of issue 148's landing (main 35127469, host load
about 90): both failed, outside 148's diff, and were waived by 133 (148's landing, fb7e6c5b).

## What happens

Both tests start a fake pilot, a fresh `python -c`, and judge what it did against a clock it does
not know about.

**`test_run.py::test_run_pilot_started_and_stopped`.** The fake pilot writes its argv to
`pilot_argv.json` as its first act, and the test reads the file after the run. The run starts the
pilot, then the fake scenario, which passes at once; the run then stops the pilot. Nothing makes
the scenario wait for the pilot, so on a loaded host the pilot is stopped before its interpreter
has started, and the file never exists:

```
E       FileNotFoundError: [Errno 2] No such file or directory: '.../pilot_argv.json'
```

**`test_stack.py::test_a_start_that_never_loads_is_restarted_twice_then_left_not_ready`.** The
keeper (`stack.keep(once=True)`) starts a fake ego pilot whose every start prints a composable
load that is never answered; it is to see the stall, restart the pilot twice (`LOAD_RESTARTS`),
see the third start stall too and leave it not ready (`pilot.missing`). `keep(once=True)` has no
end but readiness or `once_timeout`, and the test gives it 8 s for three pilot starts, their
stalls and two respawn delays. On a loaded host the 8 s ran out first:

```
>       assert [e["restart"] for e in events if e["event"] == "pilot.stalled"] == [1, 2]
E       assert [] == [1, 2]
```

## Measured (241, 2026-11-24)

Alone, 50 times each at load 58 to 75: `test_run` failed 1 of 50, `test_stack` 0 of 50. In the
full gate at load about 90 both failed once. Made certain by slowing the fake pilot's start (not
committed): with a 6 s sleep before it writes its argv, `test_run` fails with the error above;
with a 3 s sleep before each start prints, `test_stack` runs out of its 8 s before the third start
is left not ready (`assert len(missing) == 1`, 0 found). Both are the same fault: a process start
timed by a clock instead of waited for.

## Fix

Each test waits for the event, not a clock.

- `test_run`: the fake scenario starts only once the pilot has written its argv (bounded at 60 s,
  only so a pilot that never starts fails the test rather than hanging it).
- `test_stack`: `keep(once=True)` (used by tests only, `ONCE_TIMEOUT`) ends with code 3 as soon as a
  pilot is left not ready with its load restarts spent, which is the event the test waits for;
  `once_timeout` stays as a backstop and the test raises it from 8 s to 60 s.
  The long-running `keep()` path (the CLI's, which never passes `once`) is unchanged: there a
  pilot left not ready still stays up, not ready, as before.

The fake pilot in `test_run` now writes its argv to a temporary file and renames it, so the
scenario never reads a half-written file once it sees the name.

Shown with the slowed pilot start (not committed), each test failing before the fix and passing
after: `test_run` with a 6 s sleep passes in 8.2 s (2.4 s unslowed); `test_stack` with a 3 s sleep
before each start passes in 10.0 s, past the old 8 s budget. `test_stack.py` and `test_run.py`
whole: 146 passed.
