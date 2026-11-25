# 188: the Isaac-Python lane's scensim_batch suite takes 46 min on the CPU

**Status:** open (241; numbered by 133 on 2026-11-25); recorded, the fix to be planned later.
**Severity:** low. Nothing fails, but since issue 186 a full gate on a host with an Isaac
install runs the lane, and this one suite adds about 50 minutes to it.
**Found:** 2026-11-25, scensim 241, issue 186's first real run of the lane.

## What happens

Issue 186's first run of `scripts/isaac_lane.sh` in Isaac's own Python (on 365fc9b6, landed
as db52a744; `ISAAC_ROOT=/mnt/evo/aeon/isaac-sim-6.2`, numpy 2.3.1, `CUDA_VISIBLE_DEVICES`
empty because both GPUs were fully used by other work), 22:23 to 23:12 +08:00:

| suite | tests | time |
|---|---|---|
| `scensim_isaac_world` | 525, `OK (skipped=19)` | 160 s |
| `scensim_sampler` | 153, `OK (skipped=2)` | 29 s |
| `scensim_batch` | 259, `OK (skipped=7)` | 2763 s |

For comparison, the system-Python lane ran `scensim_batch`'s suite under pytest in 56 s in
issue 166's gate (ce3b2f3c: `251 passed, 12 skipped`), with the GPUs visible. So the two runs
differ in more than the Python: the device too. A second point, from issue 186's full gate
(d780baf7, 2026-11-25 23:34 to 2026-11-26 00:29, the GPUs visible, both fully used by other
work): the same suite in Isaac's Python took 1029 s (`Ran 259 tests`, `OK (skipped=2)`). So the
CPU accounts for a factor of about 2.7 (2763 s against 1029 s), and Isaac's Python against the
system's pytest lane for about 18 (1029 s against 56 s), on a loaded host; which tests take the
time is not measured (the lane runs `unittest` without per-test timing).

## The fix wanted (a plan later, not in 186)

Measure first: the suite's per-test times in Isaac's Python on the CPU and with a GPU. Then the
options 133 named: run in that lane only the tests that need Isaac's Python (its numpy 2 and
torch), or parallelise the suite; or keep the slow tests to the system lane. The check: the
lane's `scensim_batch` time with the plan's bar, in a full gate's log.
