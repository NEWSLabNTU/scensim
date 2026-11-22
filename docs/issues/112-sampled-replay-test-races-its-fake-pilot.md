# 112: a sampled-run test races its own fake pilot under load

**Status:** open (the test's, 243's to fix; the product is right). **Severity:** low: a flaky
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
