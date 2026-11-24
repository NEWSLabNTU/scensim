# 155: the ROS tests share fixed DDS domains, so two runs on one host see each other

**Status:** fixed 2026-11-25 (241; filed by 133). **Severity:** low: tests only. Two runs of the
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

## Fix

Each test process holds a domain no other test run on the host holds, until it exits.
`_dds_domain.take()` (in `src/scensim_agent/test/` and, identical, `src/scensim_launch/test/`)
takes the first free domain in **60 to 99** by an exclusive `flock` on
`/tmp/scensim-test-domains/<domain>.lock`, kept open for the life of the process (the kernel
releases it however the process ends), and sets `ROS_DOMAIN_ID` to it with
`ROS_LOCALHOST_ONLY=1`. A second run, from any worktree, session or user, takes the next one.
When all 40 are held it fails by name (`no free test domain in 60-99`) and never falls back to a
fixed domain.

- `test_simple_pilot_ros.py`, `test_ros_adapter.py` and `test_autoware_rtc_api.py` call it at
  import, in place of 77 and 78.
- `test_vehicle_agent_stop.py` passes the domain to its vehicle agent, in place of 57.
- `src/scensim_launch/test/test_launchers_parity.py` passes it to its launches, in place of
  `40 + pid % 15` (which drew from the seats' domains, see below) and of the caller's domain
  (0 in a gate) for its SIGINT launch.
- `test_dds_domain.py`, naming this issue: two processes at once hold different domains in the
  range; the domain is set on localhost with the Cyclone profile removed; an RMW off the RTPS
  port mapping is refused; with every domain held, it fails by name and sets no domain; the two
  copies of the file are identical.

### Why 60 to 99, above CLAUDE.md's 57

CLAUDE.md keeps `ROS_DOMAIN_ID` at 57 or below because the Cyclone localhost profile
(`cyclonedds-localhost.xml`) sets `DomainGain` 1000, which takes higher domains' ports past
65535. These tests never run under that profile: `take()` removes `CYCLONEDDS_URI`, and refuses
any RMW but Fast DDS and Cyclone (unset, `rmw_fastrtps_cpp`, `rmw_cyclonedds_cpp`), which
without a profile both use the RTPS port mapping: port base 7400, domain gain 250, participant
gain 2, offsets 0 and 1 (multicast), 10 and 11 (unicast). Domain d's ports are

```
7400 + 250 d       discovery multicast       7401 + 250 d       user multicast
7410 + 250 d + 2 p discovery unicast         7411 + 250 d + 2 p user unicast
```

for participant p of the host in that domain. At d = 60 they start at 22400; at d = 99 they
are 32150 and 32151, and 32160 + 2 p and 32161 + 2 p, below Linux's ephemeral range (32768 to
60999 on 241), so no outgoing connection's port can take one, for p up to 303. Popping the URI
was chosen over refusing to run under it: Autoware's setup exports a `CYCLONEDDS_URI`, so
refusing would fail every test run from a shell that sourced Autoware.

The range also stays off the seats: the default seats (`config.py`: domains base 1, stride 8,
count 7) take domains 1 to 56, nearly every domain at or below 57. A test there could publish
`/control/command/control_cmd` into a live pilot's domain on the host, which
`test_simple_pilot_ros.py` does. The old 77 and 78 were above every seat for that reason;
`40 + pid % 15` was not.

## Shown fixed (241, 2026-11-25)

The same runs on the fix (its sources ahead of main's install; logs in
`~/nas/autoveh/logs/155-dds-domains/`):

| Run | Result |
|---|---|
| `test_dds_domain.py` | 5 passed |
| the two files alone | 9 passed, 7.8 s |
| the two files, two runs at once, three times | 9 passed in each of the six runs |
| the whole `scensim_agent` and relay group, two runs at once | 281 passed in each |
| `test_launchers_parity.py` (with play_launch on `PATH`) | 3 passed |

