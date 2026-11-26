# 193: a kill-timing test fails under load: the engine outlives its SIGKILLed keeper

**Status:** open (243; numbered by 133, 2026-11-26). Cause found (hypothesis 3, the reaper's
handover order) and fixed on branch `i193-fix`, which is gating; see "The fix" below.
**Severity:** a gate failure on code the change did not touch; it stops a landing (issue 166's
rule for this class). Whether CARLA's engine can really outlive a killed keeper in use is open.
**Found:** 2026-11-26, scensim 243, `just gate` on b48261bd (190 (d)'s pins, R4).

This is the second sighting of the class issue 166 recorded once, which 166 placed with issues
148 and 150: "a second sighting is not waived, it stops the landing and gets its own number."

## What happened

`just gate b48261bdac1366ea23739708da492d8d68c7e287` on newslab-server243, 2026-11-26. Build
from 14:16:59; test from 14:34:06; ended 14:45:40. Its summary
(`/var/tmp/aeon/gate-b48261bd/gate.txt`):

```
gate FAILED b48261bdac1366ea23739708da492d8d68c7e287 at test: `just test` exited non-zero (last line: error: recipe `test` failed with exit code 1)
```

`src/scensim/test` ended `1 failed, 875 passed, 8 skipped, 2 warnings, 1 error in 374.47s`, both
in one test, `test_simulator.py::test_the_engine_under_the_launcher_dies_with_a_sigkilled_keeper`:

- FAILED: `AssertionError: the engine outlived its SIGKILLed keeper (issue 133)`
  (`test_simulator.py:851`). The test starts a keeper process that starts a fake CARLA under
  `simulator.Carla`, waits until the reaper holds a pidfd on the engine, SIGKILLs the keeper, and
  gives the engine 15 s (`gone(engine, within=15)`) to be gone.
- ERROR at teardown: `fake CARLA [983531] outlived its test (issue 133)` (`:812`): the same engine,
  still alive when the fixture looked 5 s later.

The commit was pins only (autoware_sim_vehicle, acb, aib, siw). None of them touches
`scensim.simulator` or its tests. The same test passed in 243's K9f-a gate on 91d3e9ab that
morning.

## Under what

- **Load.** Nothing sampled the load during that gate. At 14:48, three minutes after it, the
  load average was 3.8 / 5.7 / 10.0 on 32 cores; the 15-minute figure covers the test step.
  Other users' work (two training jobs and a CARLA 0.9.15 of teacup1117's) held the host
  throughout.
- **GATE_WRAP.** That gate ran every step under 243's memory guard
  (`GATE_WRAP=/var/tmp/aeon/190d/memguard.sh`). The guard starts the step with `setsid` and
  polls `MemAvailable`, so `just test` and every test ran in a new session and process group.
  The morning's passing gate had no such wrapper. Session and process-group membership bear on
  what a signal reaches and on parent-death chains. So this is not a neutral variable for a test
  of what dies with its keeper (133).

## Re-runs, the same afternoon (not a finding, a first look)

In the failed gate's tree, after it ended (14:46 to 14:50):

| run | result |
|---|---|
| the test alone, plain, 3 times | 3 passed (0.15 s each) |
| the test alone, under the memory guard (setsid), 3 times | 3 passed |
| all of `test_simulator.py` under `env -i` and the guard, 2 times | 47 passed, 47 passed |

So it does not reproduce alone or on an idle-ish host, with or without setsid.

The landing went on with a second gate of the same commit without GATE_WRAP (133's ruling),
memory watched by hand. It passed: `gate ok b48261bdac1366ea23739708da492d8d68c7e287 tree
6010e18a on newslab-server243 2026-11-26T15:28:20+08:00: build test check clean; Isaac lane ran
(942 tests)`. Test step 15:06:01 to 15:28:11. Memory did not fall below 25 GB available, and
the load was sampled every 10 s. b48261bd is on main.

**The evidence** is on the NAS, `home/2026-11-26 193 flake (243)/`, with SHA256SUMS. The
gate worktrees themselves were removed after the copy.
- From the failed gate: `gate.log`, `gate.txt` and `gate-test.out`.
- The guard and the runner: `memguard.sh` and `gate-run.sh`.
- From the passing gate: its summary, `gate-2.txt`, and its memory and load log,
  `memlog-gate-2.txt`.

## Hypotheses

1. **setsid under load** (first to test). The keeper's death reaches the reaper later, or not
   at all, when the test runs in a session of its own, and only under load does that pass the
   15 s.
   The test, CPU only, after 190 (d)'s landing: the one test, 20 repetitions run under setsid
   and 20 run plainly, each under the same fixed load (a burn.py-style 20 busy workers). Count
   the failures of each. Predictions: if load alone is the cause, both arms fail, at about the
   same rate; if setsid matters, the setsid arm fails clearly more often (3 or more of 20 above
   the plain arm). If neither fails, 20 workers are not the gate's load, and the load is raised
   before concluding anything.
2. **Load alone.** The reaper's poll, or the SIGTERM-then-SIGKILL wait it gives the engine,
   overruns 15 s on a loaded host. Hypothesis 1's plain arm measures this.
3. **A race in the reaper's handover.** The pidfd is open but the reaper has not yet armed its
   watch on the keeper when the keeper dies. Read `scensim.simulator`'s reaper for the order of
   those two steps before any fix.

## The fix (243, 2026-11-26; assigned by 133 on 118's reading of hypothesis 3)

118 read the reaper (its section, "Hypothesis 1, 118, 2026-11-26", and the hypothesis 3
reading). `start_reaper` arms the reaper's parent-death signal (SIGTERM) in its `preexec_fn`,
but `reap()` installs its SIGTERM handler only after the first `members.scan()`, which opens
the pidfds. A keeper that dies before the handler is installed sends the reaper SIGTERM at
the default disposition: the reaper dies without signalling anything, the launcher dies of its
own parent-death signal, and the engine (whose parent-death signal the launcher's fork
cleared) is orphaned for good. That matches the failed gate: the engine alive at the 15 s
assertion and again at teardown, over 20 s after the keeper died. The window is wider than the
scan: it runs from the `prctl` in `preexec_fn` through the interpreter's start-up, its
imports and the whole first scan. Both tests (`:732` and `:815`) take "a pidfd in
`/proc/<reaper>/fd`" as the reaper watching, which falls inside that window.

**The change.**
- The reaper's `preexec_fn` blocks SIGTERM before it arms the parent-death signal. A blocked
  mask survives `exec`, so a keeper's death during start-up leaves SIGTERM pending, not fatal.
- `reap()` installs its SIGTERM handler, then unblocks SIGTERM, before any `pidfd_open`. A
  pending SIGTERM then reaches the handler and the reaper ends CARLA's group as it would have.
  `reap()` puts the previous handlers and mask back when it returns (it is also called
  in-process by a test).
- The reaper says it is armed: `reap --ready <file>` writes the file (atomically) after the
  handler is in place and the first scan holds CARLA. `Carla.start` passes
  `<proc dir>/carla.reaper.ready` and removes a stale one first. The two tests wait for that
  file instead of a pidfd.
- A test-only pause, `SCENSIM_TEST_REAPER_PAUSE=<where>:<seconds>` (`startup`: before
  `reap()` starts; `scan`: after the first scan), holds the reaper inside the window so a test
  can kill the keeper there. Nothing outside the tests sets it.

**Predictions (written before the runs).**
- P1. A new test kills the keeper while the reaper is paused at `startup`. Before the change it
  fails: the engine is alive after 15 s. After the change it passes.
- P2. A new test kills the keeper while the reaper is paused at `scan`, as soon as the reaper
  holds a pidfd (the old readiness sign). Before the change it fails the same way; after, it
  passes.
- P3. After the change, `test_simulator.py` passes whole, `:732` and `:815` included, now
  waiting on the ready file.
- P4. `just gate` on the fix passes.

**Results (243, 2026-11-26, newslab-server243; scensim's tests in a clean environment with the
9ed62536 install sourced for the car packages).**
- P1 and P2: held. On the reaper before the change (commit 1d209a65, the pause and the two
  tests), both new tests failed 3 of 3, each with "CARLA outlived a keeper SIGKILLed while its
  reaper was at startup" (and "at scan"). After the change, both passed 3 of 3, as did every
  reaper and keeper test in `test_simulator.py` (11 passed, 3 runs). No test process was left
  behind by any run.
- P3: held. `test_simulator.py` whole: 47 passed, 2 skipped, twice. The two skips are the
  existing ones (`:574`, no carla-1.0 catalog in this sim_vehicle_spec).
- P4: the gate is recorded below when it ends.
