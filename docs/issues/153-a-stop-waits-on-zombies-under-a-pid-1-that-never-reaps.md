# 153: a stop waits on zombies under a PID 1 that never reaps

**Status:** open (241; filed by 133). **Severity:** medium: under a PID 1 that never reaps its
orphans (a container started without `--init`, docker's default), four stop paths wait out
every grace before they return, and one reports a stack that has stopped as not stopped. A
released testbench run in such a container would hang this way. On a host whose init reaps,
nothing is wrong.
**Found:** 2026-11-24, scensim 243, in K6's jazzy-check (a container whose PID 1 was `timeout`
or `python3`, exec'd from `bash -c`): four tests of `scripts/test_t3.py` timed out, the same
four in two runs, at load 24 and at load 3.

## What happens

A process that exits stays a zombie until its parent reaps it. A zombie keeps its process
group, so `os.killpg(pgid, 0)` still succeeds while every member of the group is a zombie. When
the parent dies first, the kernel hands the zombie to PID 1 (or to the nearest subreaper),
which normally reaps it at once. In a container without an init, PID 1 is whatever the
container ran: `bash -c '... exec timeout ...'` makes it `timeout`, and `exec python3 ...` makes
it Python. Neither reaps children it did not start, so an orphaned zombie stays for the
container's life.

A stop that polls `os.killpg(pgid, 0)` to tell when the group is gone therefore never sees it
go. It waits the full grace at each stage (SIGINT, SIGTERM, SIGKILL) and returns as if the
group had resisted all three.

243's reproduction, in the Jazzy image, from a checkout with a built `install/`:

```
docker run --rm ... scensim-jazzy-check bash -c 'set +u;
    source /opt/ros/jazzy/setup.bash; source install/setup.bash;
    export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1;
    exec timeout -s KILL 400 python3 -m pytest -q -p no:cacheprovider \
        scripts/test_t3.py -k sigterm_to_t3'
```

It fails at 30.3 s (`TimeoutExpired` at the test's `p.wait(timeout=30)`). With `docker run
--init`, all 29 t3 tests pass in 22.6 s; with `; true` in place of `exec` (bash stays PID 1, and
bash reaps), the test passes in 2.3 s.

### Shown on the host (241, main 7dac866a)

The same condition, without a container: `noreap.py` makes itself a child subreaper
(`prctl(PR_SET_CHILD_SUBREAPER)`), starts the command and waits for that one child only, so
every orphan below it stays a zombie, as under a PID 1 that never reaps. Each test file was run
on its own, under it and without it (the scripts and both logs are in
`~/nas/autoveh/logs/153-zombies/`):

| Test file | Without | Under the non-reaping subreaper |
|---|---|---|
| `scripts/test_t3.py` | 29 passed, 25 s | **4 failed**, 25 passed, 1036 s |
| `src/scensim/test/test_simulator.py` | 47 passed, 51 s | **2 failed**, 45 passed, 77 s |
| `src/scenario_agent_relay/test/test_supervisor.py` | 4 passed, 3 s | **1 failed**, 3 passed, 25 s |
| `src/scensim/test/test_stack.py` | 68 passed | 68 passed |
| `src/scensim/test/test_own_world.py` | 11 passed, 4 skipped | the same |
| `src/colcon_scensim/test/test_own_world.py` | 2 skipped | the same |

t3's four are 243's four: `test_a_sigterm_to_t3_stops_its_step_and_the_stack_it_started`,
`test_t3s_stdout_gone_does_not_break_the_step`,
`test_a_second_sigint_hurries_the_stop_and_never_abandons_it` and
`test_a_sigterm_with_t3s_stdout_and_stderr_gone_still_stops_the_stack`. The fake stack
(`sleep 300` in a session of its own) is orphaned when the fake `ros2` exits; t3's `stop_group`
kills it, and the zombie it leaves holds the group open.

Each stop path, called directly on a group whose leader is the caller's child and whose second
member is left a zombie (grace 3 s; `sites153.py`, under the subreaper and without it):

| Stop path | Without | Under the non-reaping subreaper |
|---|---|---|
| `t3.stop_group` | 1.0 s | **9.0 s**: three graces |
| `own_world._stop` | 0.2 s | **9.0 s**: three graces |
| `scensim_agent` `supervise.Group.stop` | 0.2 s | **8.1 s**: the grace, then SIGKILL's 5 s, and "still alive" warnings |
| `stack_cli._gone`, every member dead | True | **False** |
| `stack.stop_processes` (zombie-aware since roadmap 079) | 0.1 s | 0.1 s |

## Every probe of this kind (grep for `kill(..., 0)` and `killpg(..., 0)`)

A probe of a **group** waits on a zombie whenever any member was orphaned, because the
caller reaps only its own children. A probe of a **single pid** waits on one only when that
pid is not the caller's child (an orphan that went to PID 1); for its own children,
`poll()`/`wait()` reaps the zombie and the probe is right.

| Site | Probes | Case | Affected |
|---|---|---|---|
| `scripts/t3.py` `stop_group` | group | t3's step leads it; the stack it started is in a session of its own and is orphaned | **yes**: three graces of `STOP_GRACE` (180 s) or 60 s |
| `src/scensim/scensim/own_world.py` `_stop` | group | the world server leads it (reaped by `poll()`); anything it started is orphaned | **yes**: three graces (10 s) |
| `src/scensim/scensim/stack_cli.py` `_gone` (`scensim stack --stop`) | group | the stack's launch, not our child | **yes**: three graces (`STOP_GRACE`, 20 s), then "did not stop", exit `EXIT_INFRA` |
| `src/scensim_agent/scensim_agent/supervise.py` `Group.alive` | group | the autopilot and agent are our children; their children are orphaned | **yes**: `--grace` plus 5 s at every stop and restart |
| `src/scensim/scensim/stack.py` `_group_alive` | group | | no: already excludes zombies (roadmap 079) |
| `src/scensim/scensim/seat.py` `pid_alive` | one pid | a seat's holder, from its lock file: not our child | no in effect: its caller (`run.stack_alive`) asks for the seat's lock first, and a zombie holds no lock |
| `src/scenario_agent_relay/test/test_supervisor.py:57` | group | test: the old supervised group | **yes** (the test fails) |
| `src/scensim/test/test_simulator.py:720, 772` | one pid | test: the stand-in CARLA, the killed keeper's child, so an orphan | **yes** (both tests fail) |
| `src/scensim/test/test_simulator.py:431` (`gone`) | one pid | test | no: already counts a zombie as gone |
| `scripts/test_t3.py:243, 289` | one pid | test: the fake stack, read with its `/proc` state | no: already reads `Z` |
| `src/scensim/test/test_run.py:1113` | one pid | test: the fake SSv2, the run's own child, reaped by its stop | no |
| `src/scensim/test/test_stack.py:301` | one pid | test | no: already allows a zombie |

The other `killpg` calls in `scripts/` (the coop drivers, `acceptance_bag.py`,
`carla_bench.py`, `test_ego_used.py`) send signals and do not probe.

## Fix (planned)

One helper, "is any process of group `pgid` left, zombies excluded": `os.killpg(pgid, 0)` first
(no such group: gone; another user's process in it: alive), then a scan of `/proc/*/stat` for a
member of the group whose state is not `Z`. It is `stack._group_alive`'s body, which already does
this. Each package that probes a group gets its own identical copy rather than a dependency on
another package: `scripts/t3.py`, `scensim` (the existing one, moved where `own_world` can import
it without a cycle), and `scensim_agent` (the relay's test takes it from `scensim_agent`, which it
already imports). Each stop path above uses it; the two `test_simulator` probes count a zombie as
gone, as that file's `gone` does. Each package gets a test, naming this issue, that makes a group
whose only member left is a zombie it does not reap and checks the helper calls it gone.

To be shown: the tables above, under the non-reaping subreaper, with the fix: every stop path
back to its time without the subreaper, and the seven tests passing.
