# 133: test_keeper_ends_the_start_when_carla_has_no_town_for_a_map can leave fake_carla.py orphaned

**Status:** open, a record (133, 2026-11-24); not reproduced, cause not verified. **Severity:**
low: a test fixture holding a port and a process, found once, 82 h after its run.
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

Not verified: how the stand-in survived both the parent-death signal (it is set on the
launcher, not on its child) and the reaper.

## Proposed fix

Either, or both:

1. the test ends its fixture's process group in a `finally` (the pid from `started.json`,
   `os.killpg`), so a failing or interrupted test leaves nothing;
2. `fake_carla.py` sets `PR_SET_PDEATHSIG` itself, so it dies with the launcher whatever
   happens to the keeper and the reaper.

If the real launcher's child can survive the same way, (2)'s question applies to CARLA too:
worth a check when this is fixed.
