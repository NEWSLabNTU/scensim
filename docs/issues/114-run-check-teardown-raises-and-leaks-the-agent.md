# 114: run_check's teardown raises when the connection is already gone, and leaks the agent

**Status:** open (243 to fix). **Severity:** low: a flaky gate under a loaded host. A user's
`check` run can end with a traceback instead of its report, and the agent it started is not
closed. **Found:** 2026-11-23, scensim 241, in issue 104's landing gate.

## What happens

Issue 104's full gate (tree 6299512a, docs and pins only; nothing under `src/scensim_agent`
moved) failed two tests in `src/scensim_agent/test/test_ros_adapter.py`. The host's load was
about 67 on 24 cores:

```
FAILED src/scensim_agent/test/test_ros_adapter.py::test_yaml_only_adapter_passes_check
FAILED src/scensim_agent/test/test_ros_adapter.py::test_a_subclass_overrides_one_step
2 failed, 269 passed in 80.87s (0:01:20)
```

The first:

```
build/scensim_agent/scensim_agent/check.py:275: in run_check
    relay.close()
build/scensim_agent/scensim_agent/check.py:152: in close
    self.drop()
build/scensim_agent/scensim_agent/check.py:147: in drop
    sock.shutdown(socket.SHUT_RDWR)
E   OSError: [Errno 107] Transport endpoint is not connected
```

The second, a later test in the same file:

```
>       assert autopilot.goals == [60.0]
E       assert [50.0, 60.0] == [60.0]
```

## Why

`run_check` (`scensim_agent/check.py`) tears down in its `finally`:

```python
    finally:
        stop.set()
        client.stop()
        relay.close()
        runner.join(timeout=3.0)
        agent.close()
```

`relay.close()` calls `FakeRelay.drop()`, which calls `sock.shutdown(SHUT_RDWR)` with no
guard. `client.stop()` has just closed the agent's end. When the relay's socket has already
seen the connection end, `shutdown` raises ENOTCONN. Which interleaving leaves it unconnected
was not established; under load the window is wider. The exception leaves the `finally`
early: `runner.join` and `agent.close()` never run.

So the first test's agent, a `RosAdapter` node, stays alive. It keeps publishing the first
test's goal (50.0) on `/planning/goal` in the same ROS domain. The next test that counts goals,
`test_a_subclass_overrides_one_step`, receives that 50.0 before its own 60.0. The second
failure follows from the first.

`check.py` is the shipped `run_check` (the agent SDK's check), so a user's check can hit this
too, not only the tests.

## Reruns

In the same tree, right after the gate, with the load at 65 to 71:
- the file alone (`pytest src/scensim_agent/test/test_ros_adapter.py`): 5 of 5 passed;
- the gate's agent suite (`pytest src/scensim_agent/test src/scenario_agent_relay/test`, 271
  tests): 3 of 3 passed.

## Fix (243)

- `FakeRelay.drop()` tolerates a socket that is already gone (catch OSError around
  `shutdown`, then close).
- `run_check`'s teardown closes the agent whatever an earlier step raised, for example with
  each step in its own try, or `agent.close()` in an outer `finally`.
- A test, failing before the fix: the relay's socket closed by the peer before `run_check`
  tears down; `run_check` returns its report and the agent is closed.

Evidence: the gate's log, lines 1890 to 1952, on the NAS at
`~/nas/home/aeon/issue114/gate-here.101859.log`.
