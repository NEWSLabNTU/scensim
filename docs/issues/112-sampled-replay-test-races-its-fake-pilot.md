# 112: a sampled-run test races its own fake pilot under load

**Status:** fixed (the test's, 243; the product is right). **Severity:** low: a flaky
gate, about 1 in 13 under a loaded host; no run's record is wrong. **Found:** 2026-11-23, scensim
241, in issue 106's landing gate.

## What happens

`src/scensim/test/test_sampled.py::test_sampled_runs_carry_their_bound_record_and_replay_exactly`
runs two sampled runs, each with a `lifetime: run` follower pilot. It then checks that the
follower got each run's record's seed. Once, in issue 106's gate, only one of the two seeds was
there:

```
>       assert {w.split("--seed ")[1] for w in pilot_runs} == want
E       AssertionError: assert {'1247820689'} == {'1247820689', '1912519900'}
```

Rerun alone on the same checkout, it failed 1 of 13 times while the host was loaded, and passed
25 of 25 later. Issue 106 changed nothing under `src/scensim`; the test is from 7aee8e30.

## Why: the test, not the product

The `stack_up` fixture replaces `run.pilot_argv`. Its pilot is
`python -c "open(seeds.jsonl, 'a').write(<the run argument>)"`, which records the seed only once
its own interpreter has started. A passing run's timeline shows how long it has to do that:

| t (s from run.start) | event |
|---|---|
| 0.017 to 0.026 | pilot.start follower |
| 0.023 to 0.033 | pilot.ready follower (the test does not wait on the fake) |
| 0.475 to 0.528 | run.end: the run stops its pilots (SIGTERM) |

The fake scenario ends at once, so the follower lives about 0.45 to 0.5 s. A bare interpreter
starts and exits in 0.012 s on an idle host. With load around 70 on 24 cores, it can take longer
than the run lives. The pilot is then killed before it writes, and the test sees one seed fewer.

The product did its part: the seed is in the pilot's command line, built from the run's record
(`stack.pilot_argv`), and the timeline records the pilot's start.

## Fix (243, the test's author)

Record what the run asked for, not what a child process managed to write. The patched
`pilot_cmd` can append the `run` argument to a list in the test process when the run builds the
command, and the assertion reads that. Or the fake scenario can wait until the pilot's line
exists, or the fake can be one that has started before readiness is declared.

Evidence (a passing run, kept with its logs): 241's scratchpad
`flake/t1/test_sampled_runs_carry_their_0/logs/proj/runs/*/timeline.jsonl`.

## Resolution (2026-11-23)

The patched `pilot_cmd` now appends the pilot's `run` argument to `seeds.jsonl` in the test
process, as the run builds the command, and starts a no-op child. The run builds it once per run
per pilot, just before it starts the pilot (`run.py`, the pilots' loop), so the record is exact.

Looping the test under load found a second race in the same fixture. Its teardown waited 10 s
for the stack keeper after SIGTERM, but the keeper's stop ladder (`stack.stop_processes`: SIGINT,
20 s, SIGTERM, 10 s, SIGKILL, 5 s) may take 35 s. At load about 30 that wait timed out once in 8
runs, with the test's body passed. Every `start_stack` teardown had the same fixed 10 s: 13 in
`test_run.py`, one each in `test_knobs.py` and `test_sampled.py`. All now wait
`_ceiling.STOP_WAIT()`, which is `ceiling(base=60)` scaled by the load per core, as the
ready-waits are.

## A third race (2026-11-23, found by 241's issue 118 gate)

241's gate for issue 118, at load 68 to 82 on 32 cores, failed the test at its `--replay` step
with "pilot follower is not coming up: its launch exited (code 0) before it was ready". The
no-op child of the resolution above exits at once. The run's wait for its own pilots
(`run.py`, issue 089's check) polls the pilot's process before its readiness, so a pilot that
has already ended is an infra error. Unloaded, the first poll comes before the child exits;
under load it can come after. The child before the resolution also exited at once, after
writing its line, so the race is older; the no-op child made the window wider.

The fake pilot now stays up until the run stops it, as a real pilot does (`FAKE_PILOT`:
`signal.pause()`, ending with code 0 on SIGINT or SIGTERM).
`test_the_fake_pilot_outlives_a_late_first_poll` makes the race deterministic: it holds the
run's first poll until the pilot has exited, or for 5 s if it has not. With a pilot that exits
at once it fails with 241's message; with `FAKE_PILOT` it passes. Product code is unchanged.
