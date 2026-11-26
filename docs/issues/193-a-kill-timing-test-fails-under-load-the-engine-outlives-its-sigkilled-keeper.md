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

## Hypothesis 1, 118, 2026-11-26 (scensim 118 for 243, assigned by 133; after the predictions above)

**Setup.**
- Host: newslab-server118, 48 cores.
- Tree: scensim main 7a9dc61c (gate-c5c, built and gated at that commit).
- Load: burn.py, 30 workers (243's 20 on 32 cores, scaled to 48), in their own process group,
  started 5 s before the first run and checked at 31 processes. Each workload's group was
  verified empty after it.
- The setsid arm runs `pytest` under 243's `memguard.sh`, the failed gate's `GATE_WRAP`. The
  plain arm runs it directly. Both run under `env -i` with `install/setup.bash` sourced,
  `OMP_NUM_THREADS=4`, and `-p no:cacheprovider`.
- 20 runs per arm, interleaved (setsid first on odd runs, plain first on even ones).
- A setsid run takes at least 5 s, because memguard polls every 5 s.

| test | arm | runs | failures | load average (1 min) over the runs |
|---|---|---|---|---|
| `:815` engine under the launcher, SIGKILLed keeper | setsid | 20 | 0 | 8.2 to 31.9 |
| | plain | 20 | 0 | 8.2 to 31.8 |
| `:732` CARLA deaf to SIGTERM (166's first sighting) | setsid | 20 | 0 | 32.0 to 73.8 |
| | plain | 20 | 0 | 32.2 to 74.5 |
| `:703` started CARLA dies with its killed keeper | setsid | 20 | 0 | 34.4 to 41.8 |
| | plain | 20 | 0 | 34.5 to 41.4 |

The load average rose over the `:815` set as the workers started. Other users' work added to it
during `:732`.

**An aborted first attempt (not counted).** burn.py refused to start (its BLAS-threads
assertion), so 2 setsid and 2 plain runs of `:815` ran with no load. All passed. The runner was
stopped by its process group. The fix sets the BLAS variables, and a check now refuses to run
with fewer than W+1 burn processes.

**Against the predictions.** Neither arm failed on any of the three tests, 0 of 120 runs. That is
the third branch, as written: 30 workers on 48 cores are not the gate's load, and nothing is
concluded about setsid or load alone yet. The next arm, as 243 suggests, is the whole of
`test_simulator.py`, or of `src/scensim/test` where the failure came, under setsid and the same
load, before the load is raised.

**Logs.** On 118, in `/mnt/renegade/aeon/isaac-ex/i193/`: `h1.sh`, `memguard.sh`, `burn.py`,
`times_t815.txt`, `times_t732.txt` and `times_t703.txt`, with one pytest output per run in
`t815/`, `t732/` and `t703/` (the aborted attempt in `t815-aborted-noload/`).

## Hypothesis 3, the reading (118, 2026-11-26; read-only, at main a4388a35, before any run of it)

**What the code does** (`src/scensim/scensim/simulator.py`):
- `Carla.start()` starts the launcher in a new session with `_carla_child` as its `preexec_fn`,
  which sets `PR_SET_PDEATHSIG` to SIGTERM. It then calls `start_reaper(pid)`.
- `start_reaper()` starts `python3 -m scensim.simulator reap <pid> --parent <keeper>`, also in a
  new session, also with `preexec_fn=_die_with_parent`. So the reaper too gets **SIGTERM when the
  keeper dies**.
- `reap()` does, in this order:
  1. `members = _Members(pid)`;
  2. `members.scan()`, which lists `/proc`, opens a pidfd on each member of CARLA's group and keeps
     the live ones;
  3. **only then** `signal.signal(SIGTERM, <set gone>)`;
  4. the loop that waits while `os.getppid() == parent`, then SIGTERM, the grace, SIGKILL.
- The engine runs under the launcher (`CarlaUE4.sh` forks it), and a fork clears the
  parent-death signal. So when the keeper dies, only the launcher and the reaper get SIGTERM from
  the kernel. Only the reaper ends the engine.

**The window this leaves.** From the first `pidfd_open` in step 2 to the end of step 3, the
reaper holds a pidfd, but its SIGTERM disposition is still the default (terminate). A keeper that
dies in that window makes the kernel SIGTERM the reaper, and **the reaper dies without signalling
anything**. The launcher dies of its own parent-death signal. The engine, whose parent-death
signal the fork cleared, is orphaned and lives on with nothing to end it. That fits both sightings
exactly: the engine was still alive at the 15 s assertion and still about 5 s later at teardown.
A reaper that is only slow would have ended it within the 20 s grace.

**Why the tests can hit it.** Both `:815` and `:732` treat "the reaper holds a pidfd" (an
`anon_inode:[pidfd]` in `/proc/<reaper>/fd`, polled every 50 ms) as "the reaper is watching", then
SIGKILL the keeper. `:732`'s own comment records that a fixed 1 s sleep "raced a loaded host"
before this check replaced it. The check narrows the race but does not close it, because the
pidfd appears before the handler is set. The window's length is:
- the rest of the first scan after the first member's pidfd, which is a `/proc/<pid>/stat` read
  for every process on the host (802 pids on 118 now; a full-suite run adds its own churn);
- plus any preemption there.

`:815` also needs the engine's `started.json` to be present at that poll. So the race can only
bite when the engine is up before the reaper's first scan ends, which is more likely when the
reaper's Python start (importing `scensim.simulator`) is slow. The 120 single-test runs above
gave a short scan and a quick reaper on a fairly idle process table, which is consistent with
0 failures.

**Predictions (written before the full-suite arm, CPU only, not yet run).**
- *If H3 is the cause:* failures, if any, appear in both arms at rates that are not clearly
  different (setsid does not touch the window). The failure is this test's assertion with its
  teardown error naming the same engine, as in 193's sighting.
- *If setsid itself matters (H1):* the setsid arm fails 3 or more of 5 more than the plain arm.
- *With 5 runs per arm,* 0 failures in both arms is likely even if H3 is right (the gate saw one
  in two runs of the suite, at best). It does not count against H3. A direct test of H3 is to
  widen the window on purpose: delay the reaper between its first scan and its handler (for
  example with a test-only hook), and see whether the engine then survives every time. That needs
  a code change, which is for 243 to decide.
- *The fix this reading implies, for 243 (not made here):* set the SIGTERM handler (or block
  SIGTERM) in the reaper before it opens any pidfd, so a keeper's death at any moment reaches
  the loop. Better still, arm the parent-death signal only after the handler is set. The test's
  "watching" signal could then be a file the reaper writes after arming, rather than the
  pidfd's presence.

## Arm (a): the full suite under load, before and after the fix (118, 2026-11-26 and 27)

**The arm** (133): all of `src/scensim/test`, 5 runs under 243's `memguard.sh` (setsid) and 5
plain, interleaved, under burn.py's 30 workers on 118's 48 cores, run by the same runner as
hypothesis 1 (`h1.sh`, with `-rfE` so that failing tests are named).

**Baseline, before the fix** (main 7a9dc61c, which has the reaper as read in hypothesis 3; run
from 22:36:20 to 23:47:47, after that section's predictions):

| arm | runs | failures | tests per run | load average (1 min) |
|---|---|---|---|---|
| setsid | 5 | 0 | 879 passed, 5 skipped | about 31 to 35 |
| plain | 5 | 0 | 879 passed, 5 skipped | about 31 to 35 |

Against hypothesis 3's predictions: 0 of 10 was the likely outcome even with the window real.
So the window is real (the code shows it, and 243's tests below force it), but it is rare under
this load, about 31 on 48 cores. It was not reproduced here. Hypothesis 1 (setsid itself) has no
support: 0 failures in 70 setsid runs over this section and hypothesis 1's.

**The regression check, on the fix** (main a02e9dc6, rebuilt in gate-c5c at 23:48; the same arm,
from 23:48:07). *Predictions, labelled: written at 00:20, with 4 of the 10 runs already read
(all passed), before the other 6.* Every run passes, both arms, including 243's two new tests
that kill the keeper while its reaper arms. Any failure of `:815`, `:732` or the new tests would
count against the fix.

RESULT_PLACEHOLDER

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
- The block is not inherited (133's check). Only the reaper's own `preexec_fn`
  (`_reaper_child`) blocks SIGTERM; CARLA's launcher keeps its own (`_carla_child`, no
  block), and the keeper's mask is never touched. The reaper starts no process: it only
  signals through pidfds. And `reap()` unblocks SIGTERM before anything else. `:815` now
  asserts it from `/proc/<pid>/status` SigBlk: SIGTERM is not blocked in the armed reaper, nor
  in the engine under the launcher. The helper was checked once by hand to see a blocked
  child as blocked. The reaper and keeper tests: 11 passed, 3 runs; the file: 47 passed,
  2 skipped.
- P4: the gate is recorded below when it ends.
