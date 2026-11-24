# 155: the ROS tests share fixed DDS domains, so two runs on one host see each other

**Status:** open (241; filed by 133). **Severity:** low: tests only. Two runs of the
`scensim_agent` tests on one host at the same time (two gates, a gate and a side run, two
sessions) each receive the other's messages, and three tests fail in both runs. A gate then
fails on code it does not run.
**Found:** 2026-11-25, scensim 241, while gating issue 153: a stopped gate showed two failures
in `test_simple_pilot_ros.py`, and a side run of the same group showed those and four in
`test_ros_adapter.py`. Neither run reached pytest's summary; 153's later gate passed the group.
Two of 133's hypotheses were checked and ruled out: the tests set `ROS_LOCALHOST_ONLY=1`, so no
other host reaches them, and the gate's environment sets neither `CYCLONEDDS_URI` nor
`RMW_IMPLEMENTATION` (it runs Fast DDS, and the tests pop `CYCLONEDDS_URI` anyway).

## What happens

Each of these test files joins DDS on a domain written into it:

| File | Domain | What the tests check |
|---|---|---|
| `src/scensim_agent/test/test_simple_pilot_ros.py` | 77 | a stand-in bridge counts the pilot's commands |
| `src/scensim_agent/test/test_ros_adapter.py` | 77 | an adapter's published values, one message per step |
| `src/scensim_agent/test/test_autoware_rtc_api.py` | 78 | Autoware's RTC services, answered by the test's own node |
| `src/scensim_agent/test/test_vehicle_agent_stop.py` | 57 | a vehicle agent's stop time (a subprocess; no messages counted) |

`ROS_LOCALHOST_ONLY=1` keeps discovery on the host, not on one process: every participant on
the host in the same domain meets every other. Two runs of these files at once therefore
publish into each other's subscriptions on the same topic names, and a test that counts what it
received counts both runs.

Shown on 241 (main 564600f8, no other process with a `ROS_DOMAIN_ID` in its environment):
`test_simple_pilot_ros.py` and `test_ros_adapter.py`, first alone, then two runs started together
(script and logs in `~/nas/autoveh/logs/155-dds-domains/`).

| Run | Result |
|---|---|
| alone | 9 passed, 7.8 s |
| two at once, run A | 3 failed, 6 passed |
| two at once, run B | 3 failed, 6 passed |

Both runs failed the same three:
`test_simple_pilot_ros.py::test_commands_on_the_vehicle_interface`,
`test_ros_adapter.py::test_yaml_only_adapter_passes_check` and
`test_ros_adapter.py::test_a_subclass_overrides_one_step`. Every value arrived twice:

```
E   assert [50.0, 50.0] == [50.0]
E     Left contains one more item: 50.0
```

Other tests that start ROS processes choose their domain differently:
`src/scensim_launch/test/test_launchers_parity.py` uses `40 + pid % 15` for its parity launches
(per run, but two runs can still draw the same one) and inherits the caller's domain for its
SIGINT launch, which in a gate is 0. These check a launch's exit, not messages, so cross-talk
does not fail them, but they share the domain with whatever else is on it.

## Fix (planned)

A run takes a domain no other run on the host holds, and holds it until it exits:

- A small helper, `test_domain()`, takes the first free domain in a reserved range at or below
  57 (the Cyclone localhost profile's limit, CLAUDE.md) by an exclusive `flock` on
  `/tmp/scensim-test-domains/<domain>.lock`, kept open for the life of the process, and sets
  `ROS_DOMAIN_ID` to it and `ROS_LOCALHOST_ONLY=1`. A second run, from any worktree or session,
  takes the next one. The kernel releases the lock when the process ends, however it ends.
- The three in-process files call it at import, in place of their fixed number. The vehicle
  agent test and the parity launches pass the same domain to their subprocesses.
- A test, naming this issue, runs two processes that each take a domain at once and checks the
  two differ.

To be shown: the pair run above passing in both runs.

A domain taken this way can still be one a live stack on the host uses (seats take their domains
from the host's settings, anywhere in 0 to 57). The range should be one this host's seats do not
use; the default seat settings and the ego and scenario domains (1, 9) will be checked before the
range is chosen.
