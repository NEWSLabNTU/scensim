# 133: test_keeper_ends_the_start_when_carla_has_no_town_for_a_map can leave fake_carla.py orphaned

**Status:** fixed 2026-11-24 (243): the reaper ends every process of CARLA's group, each held
by a pidfd ("The fix" below). **Severity:** low for the test; the same path could orphan a real
CARLA engine ("The real CARLA" below).
**Found:** 2026-11-24, 241, while gating issue 130's landing, in the host's process list.

## What happened

An orphaned `fake_carla.py`, the CARLA stand-in of `src/scensim/test/test_simulator.py`:

```
pid 2617572, ppid 1, user aeon, up 296494 s (about 82 h)
/usr/bin/python3 /tmp/pytest-of-aeon/pytest-1225/test_keeper_ends_the_start_whe1/CARLA_0.9.16/fake_carla.py
    -carla-rpc-port=47491 -nosound -RenderOffScreen -quality-level=Epic
cwd: /tmp/pytest-of-aeon/garbage-.../test_keeper_ends_the_start_whe1/CARLA_0.9.16 (deleted)
```

The directory name is pytest's (truncated) for
`test_keeper_ends_the_start_when_carla_has_no_town_for_a_map` (issue 083's test). pytest had
since deleted the run's tmp tree. It was reaped by that pid (SIGTERM; it ended without SIGKILL)
with 133's approval.

## What is known

- The fixture's `CarlaUE4.sh` runs `fake_carla.py` as its child, not with `exec`, as the real
  launcher runs the Shipping binary. The keeper starts the launcher in its own session with a
  parent-death SIGTERM (`_carla_child`), and `start_reaper` watches it, ending its process group
  (`os.killpg`) when the keeper dies.
- The test asserts at its end that the started CARLA's pid is gone. That run may have ended
  before the assertion (a failure, or the run killed); which, is not known.

## The cause (reproduced, 243)

Reproduced by SIGKILLing a keeper that had started the fixture's CARLA (`simulator.Carla.start`):
the launcher and the reaper were gone within seconds, and `fake_carla.py` was left with ppid 1 in
the launcher's old process group.

1. The parent-death signal does not reach the engine: `PR_SET_PDEATHSIG` is set on the launcher
   (`_carla_child`), and a fork clears it, so the launcher's child never has it.
2. The launcher dies at once of its SIGTERM.
3. The reaper watched only the launcher's pidfd. It saw it end, took that for "the keeper
   stopped CARLA", and returned without signalling the group (and its `send` skipped the group
   when the launcher was already gone).

So any keeper death with this test's CARLA up, a failing or killed run, leaves the stand-in.
The test's own assertion does not run in that case: its keeper is the pytest process.

## The real CARLA

The same. `CarlaUE4.sh` of CARLA 0.9.16 runs `CarlaUE4-Linux-Shipping` as its child, without
`exec`, as the fixture does. Any SIGKILL of the keeper (play_launch's stop SIGKILLs it seconds
after SIGTERM; the OOM killer) left a started CARLA's engine running, holding its port and
its VRAM, the case the reaper was written for.

## The fix

- The reaper (`simulator.reap`) waits for the keeper's death, not the launcher's. While the
  keeper lives it leaves only when CARLA's whole process group has ended.
- It never signals a group by its id, which any process may hold once the group's last member
  ends. It holds each member by a pidfd (`_Members`): a process counts once its pidfd is open,
  its `/proc` stat names the group, and the pidfd still shows it alive after that read. Only
  held members are signalled, each through its own pidfd (SIGTERM, the grace, then SIGKILL to
  those left).
- The keeper's own group signals (`Carla.poll`, `Carla.stop`) are sent only while the launcher
  is exited but not yet reaped (`waitid` with `WNOWAIT`), so the group's id is still the
  launcher's; it is reaped after.

Tests (`src/scensim/test/test_simulator.py`): a keeper SIGKILLed over the fixture's launcher and
engine leaves no engine (it failed before the fix); a group whose members have all ended is
never signalled, and its reaper leaves at once; and an autouse fixture fails any test of the
file that leaves a `fake_carla.py` alive, and ends it.

## Paths covered

- Covered: a CARLA the stack's keeper starts (`carla.start` auto or start: `simulator.Carla` and
  its reaper).
- Not affected: `just carla-start`, and `scripts/carla_up.sh` through it. acb's `run.sh` execs
  `CarlaUE4.sh` (the engine still its child) inside a `systemd-run --user` unit, whose stop
  ends the unit's whole cgroup; that CARLA is meant to outlive any keeper.
- Not affected: an external CARLA, which the stack never stops.
