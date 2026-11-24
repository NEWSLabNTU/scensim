# 148: the dispatcher loses a worker's last stderr lines

**Status:** fixed 2026-11-24 (241; filed by 133). **Severity:** low: a seat's last lines of
output (its stack being stopped) can be missing from `scensim run --seats`' output, and a test
fails intermittently on a loaded host; no run, verdict or summary is affected.
**Found:** 2026-11-24, scensim 241, in the gate of 092 K11c's landing (main 4b128ff1, host load
107 to 127): `test_dispatch.py::test_every_run_once_on_whichever_seat_is_free_into_one_report`
failed, outside the landing's diff, and was waived by 133.

## What happens

`Dispatcher._start` relays each worker's stderr to the dispatcher's output on a daemon thread
(`_relay`, one `say` per line). `Dispatcher.stop` tells every worker to stop, closes its stdin and
waits for its process to exit, then `run` writes the summary and returns. Nothing waits for the
relay thread: a worker's process can have exited, its last lines still in the pipe or in the
thread between `readline` and `say`, when `run` returns. The lines then come after the summary or
not at all (the thread is a daemon; the process may end first).

The test asserts the fake worker's last line, printed just before it exits:

```
>       assert "seat 1 worker stops its stack" in text   # every worker was told to stop
E       AssertionError: assert 'seat 1 worker stops its stack' in 'dispatch seat 0: ...
        ...0 worker stops its stack\nsummary
```

Seat 0's line arrived, seat 1's did not, and the next assertion in the test (every worker's
process has exited) holds: the process was gone, its output not yet relayed. Measured on 241
on main's code (its gate tree), the test alone, 100 times in a row at load 110 to 119:
**5 of 100 failed**.

In real use the lost lines are the worker's own last words: `stack    stopping seat N's stack`
and whatever the stack's stop prints.

## Fix

The dispatcher keeps each worker's relay thread and `stop` joins it after the process has
ended, so `run` returns only when every worker's stderr has been relayed to its end of file. The
join waits for the line, not for a wall-clock time: it has a bound (`STOP_GRACE`), only so that a
process the worker left behind holding the pipe open cannot hang the dispatcher, and the bound
being hit is said in the output.

`test_every_workers_last_lines_come_before_the_summary` makes the race certain rather than
likely: each fake worker prints 400 lines of 200 bytes as it exits, and the output takes 3 ms a
relayed line, so a pipe's worth (64 KiB, about 320 lines) is still unread when the worker has
gone. On main's code it failed 3 of 3 (66 to 74 of 400 lines arrived); with the fix it passes,
in 2.9 s.

## Shown on a loaded host (241, 2026-11-24)

The failing test alone, 100 times in a row in one shell, each run a fresh pytest:

| Code | Host load (1 min) | Failed |
|---|---|---|
| main bb52dcc2 | 110 to 119 | 5 of 100 |
| main bb52dcc2 | 92 to 93 | 5 of 100 |
| the fix | 90 to 91 | 0 of 100 |

The second row was run after the third, at its load, so that the comparison is at one load.
