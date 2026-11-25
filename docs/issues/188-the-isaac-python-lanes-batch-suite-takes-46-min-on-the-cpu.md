# 188: the Isaac-Python lane's scensim_batch suite runs 1.2 to 49 times the system lane's time, depending on the host

**Status:** open (241; numbered by 133 on 2026-11-25); the cause open, CPU load and threads
suspected; per-test timing next (133, 2026-11-26).
**Severity:** low. Nothing fails, but since issue 186 a full gate on a host with an Isaac
install runs the lane, and on a loaded host this one suite adds up to about 45 minutes to it.
**Found:** 2026-11-25, scensim 241, issue 186's first real run of the lane.

**Superseded (2026-11-26):** this record was first titled "the Isaac-Python lane's
scensim_batch suite takes 46 min on the CPU", and its timing note put the difference down to
the device ("the CPU accounts for a factor of about 2.7 ... Isaac's Python ... about 18"). 118's
run below (78 s) and the CUDA finding below supersede both: the time depends on the host, and
the GPU is not what the suite runs on. The file name keeps the first title.

## What happens

The `scensim_batch` suite (259 tests) in Isaac's own Python, by `scripts/isaac_lane.sh`, against
the system Python's pytest lane of the same suite:

| run | host, device | time |
|---|---|---|
| 186's first lane run, 365fc9b6 (landed as db52a744), 2026-11-25 22:23 to 23:12, nice 10 | 241, `CUDA_VISIBLE_DEVICES` empty; `OK (skipped=7)` | 2763 s |
| 186's full gate, d780baf7, 2026-11-25 23:34 to 2026-11-26 00:29, nice 0 | 241, both GPUs visible; `OK (skipped=2)` | 1029 s |
| 118's full gate, 1282c48e, 2026-11-26 00:40 to 01:02 | 118, `CUDA_VISIBLE_DEVICES=0` (one RTX 4090, otherwise idle); `Ran 259 tests in 78.028s`, `OK (skipped=2)`, lane "ran (936 tests in 3 suites, OK)" | 78 s |
| the system pytest lane, the same gates | 241 (166's gate) and 118 | 56 s and 64 s |

So in Isaac's Python the suite took 1.2 times the system lane's time on 118's host (78 s
against 64 s) and 18 and 49 times on this one (1029 s and 2763 s against 56 s). 118's three lines above are as 118 copied them from its log before the
log was overwritten by its next gate.

**The GPU is not the cause.** In `scensim_batch` only `test_device` uses CUDA in the tests (its
5 CUDA cases are the difference between `skipped=7` and `skipped=2`); the package names `cuda`
only in `start_pool`'s `__main__` example and a message in `env.py`. The other ~254 tests run on
the CPU whether a GPU is visible or not.

**Suspected, not measured: the host's CPU load and torch's threads.** 241 has 24 CPUs and was
running other work: load averages of 31 to 48 when sampled during 092 K13 step v's search
(2026-11-25, 16:37 to 17:37); both GPUs were busy at about 22:05 and at 01:04 per nvidia-smi
(15 to 22 GB, 99 to 100 %), not sampled in either window above, and neither was the load. The
first run was also niced (10). Torch's intra-op threads default to the core count and
oversubscribe a loaded host. 118's host was otherwise idle.

## The fix wanted (a plan later, not in 186)

Measure first (approved by 133, 2026-11-26; its plan and prediction go to 133 before the runs):
the suite's per-test times in Isaac's Python on the CPU at nice 0, with the host's load sampled
every 10 s and recorded at each start and torch's thread count logged; again with 4 threads
(repeated once in a quiet hour if the host is loaded then); and `test_device` on one GPU only
when one is free. Then the
options 133 named: run in that lane only the tests that need Isaac's Python (its numpy 2 and
torch), or parallelise the suite; or keep the slow tests to the system lane. The check: the
lane's `scensim_batch` time with the plan's bar, in a full gate's log.
