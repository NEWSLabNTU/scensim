# 188: the Isaac-Python lane's scensim_batch suite runs 1.2 to 49 times the system lane's time, depending on the host

**Status:** fixed in code and tests (241; numbered by 133 on 2026-11-25; the cause found by the
per-test timing, torch's threads oversubscribing a shared host; capped at min(4, nproc)).
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
| 118's second full gate, c5aad663, 2026-11-26 01:03:39 to 01:25:20 | 118 (48 cores, 1-minute load about 2 to 14, max 13.79 at the end), `CUDA_VISIBLE_DEVICES=0`; `Ran 259 tests in 78.689s`, lane "ran (936 tests in 3 suites, OK)" | 79 s |
| the system pytest lane, the same gates | 241 (166's gate) and 118 | 56 s and 64 s |

So in Isaac's Python the suite took 1.2 times the system lane's time on 118's host (78 s
against 64 s) and 18 and 49 times on this one (1029 s and 2763 s against 56 s). 118's first run (00:40) is cited by the three lines 118 copied from its
log before its next gate overwrote it, and has no load record. The second is kept on 118:
`/mnt/renegade/aeon/gate-123/keep/gate-c5aad663-2026-11-26.log` (sha256
`228ee9fe10ae91b5441ede8cb2c3ea25f4ab29b31dafcbfe6c79e5c31ed2b8bb`), its load every 30 s in
`/mnt/renegade/aeon/gate-123/keep/load_c5aad663.txt` (sha256
`1b95d7569062a190c998acc8fd6894d2277b44558de8cca86004dfd76ec3c3dd`).

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

## The per-test timing's predictions (2026-11-26, approved by 133; before the runs)

A runner (not committed) runs `src/scensim_batch/test` by `unittest` in Isaac's Python
(`isaac_env.sh`), timing each test and booking each class's fixtures to it, logging
`torch.get_num_threads()`, `os.cpu_count()` and `/proc/loadavg` at start and end; a sampler
writes `/proc/loadavg` every 10 s. Run A: no GPU (`CUDA_VISIBLE_DEVICES` empty), nice 0, torch's
default threads. Run B: the same with `OMP_NUM_THREADS=MKL_NUM_THREADS=4` and
`torch.set_num_threads(4)`; repeated once in a quiet hour if its 1-minute load at start differs
from A's by more than 30 %, or is over 12 when A's was not. Run C: `test_device` on one GPU,
only with codec 139's OK that one is free here ("not run today" is an outcome).

1. Torch's default thread count is 24 (`os.cpu_count()`).
2. Run A's total, by the 1-minute load at its start: 1000 to 3000 s at 20 or more; 300 to
   1000 s, rising with the load, from 6 to 20; under 300 s under 6. The top 10 tests, with their
   class's fixtures, take 70 % or more of A's total.
3. Run B, at a start load within 30 % of A's: its total at most half of A's. Over 0.8 of A's,
   the thread hypothesis fails.
4. Run C, if it runs: `test_device`'s CUDA cases under 30 s together.

## The per-test timing's result (2026-11-26, runs A and B)

(The runs name this record's commits before it was rebased onto c5aad663 for landing:
e4cf5010 landed as 7f61f1a5 and 62bfa985 as ab521da2, the same docs changes; at both, the code
is main's.)

`i188_timing.py` and `i188_runs.sh` in Isaac's Python, CPU only, nice 0, the dev worktree at
e4cf5010 (`scensim_batch` identical to main's), `/proc/loadavg` every 10 s (105 samples: the
1-minute load from 18.1 to 51.5, median 42.7, run A's own threads among it). Both runs: 259
tests, `OK (skipped=7)`, 0 failures, 0 errors.

| run | torch threads | 1-minute load at start | at end | total |
|---|---|---|---|---|
| A, 01:06:54 to 01:23:12 | 24 (the default) | 18.12 (the driver, just before), 20.27 (the runner, after `isaac_env.sh`) | 47.18 | 973.5 s |
| B, 01:23:12 to 01:24:17 | 4 | 47.18 | 26.71 | 61.0 s |
| B repeated in a quiet hour (133), 01:27:42 to 01:28:43, its own worktree at 62bfa985 | 4 | 11.99 (the runner's) | 16.89 | 60.9 s |

1. **Torch's default threads = `os.cpu_count()` = 24: held.**
2. **A's total by its start load: held or FAILED by which reading counts.** At the driver's
   18.12 the band is 300 to 1000 s, and 973.5 s is in it; at the runner's own 20.27 the band is
   1000 to 3000 s, and A is 27 s short. Both readings are recorded; neither is chosen. **For future predictions (133): a run's "start
   load" is the runner's own reading, taken after `isaac_env.sh`.** **The top
   10 share, 0.759 (bar 0.70): held.**
3. **B's load condition was not met:** B started at 47.18, 2.3 to 2.6 times A's start, so by its
   own rule B is repeated once in a quiet hour (1-minute load under 12; 133: not waived), and
   recorded beside this one. **The repeat:** 60.9 s at a start load of 11.99 (the waiter ran it
   as soon as the 1-minute load fell under 12; 7 samples, 12.0 to 17.4), the same as at 47.18.
   Neither B run started within 30 % of A's load (A's 18.12 or 20.27; the repeat is 34 % to
   41 % under), so prediction 3 is not judged by its own condition; what both show is that B's
   time does not move with the load (61.0 s at 47, 60.9 s at 12), while A at 18 to 20 took
   973.5 s. B took 61.0 s, 0.063 of A's, under the higher
   load: load cannot explain the difference, its direction is the opposite.
4. **Run C: not run today** (no free GPU on 241; the GPUs' owners are other users, and codec
   139, asked, holds none). 133: not moved to 118, whose 78 s total already bounds
   `test_device`'s cases.

A's top 10 tests, with their class's fixture share (B's time in brackets where in B's top 10):

| A | test |
|---|---|
| 159.7 s | `test_storyboard.Episodes.test_the_truth_of_each_slot_reads_back_as_a_schema_2_file` |
| 153.1 s | `test_lazy.LazyEpisodes.test_the_truth_of_each_slot_reads_back_as_a_schema_2_file` (2.1 s) |
| 109.0 s | `test_pointmass.Runner.test_the_sloped_score_is_recomputed_from_the_saved_files_alone` |
| 104.4 s | `test_pointmass.Runner.test_a_generation_gives_one_scored_outcome_per_record` |
| 45.1 s | `test_storyboard.Episodes.test_a_reset_gives_each_slot_its_records_onset_and_rate_without_a_compile` (4.5 s) |
| 41.2 s | `test_lazy.LazyEpisodes.test_a_reset_gives_each_slot_its_records_onset_and_rate_without_a_compile` (5.4 s) |
| 41.0 s | `test_lazy.LazyEpisodes.test_one_slot_rebound_leaves_the_other_as_compiled` (5.0 s) |
| 38.3 s | `test_storyboard.Episodes.test_one_slot_rebound_leaves_the_other_as_compiled` (3.8 s) |
| 26.8 s | `test_npc.Following.test_n_slots_equal_n_scalar_runs` (2.1 s) |
| 20.6 s | `test_lazy.LazyEpisodes.test_cs2s_lead_brakes_per_slot_at_its_own_onset_as_ssv2_brakes` (2.9 s) |

By class in A: `test_storyboard.Episodes` 268 s, `test_lazy.LazyEpisodes` 261 s,
`test_pointmass.Runner` 213 s, `test_npc.Following` 62 s. In B nothing dominates (top 10
share 0.55; the slowest test 5.4 s).

**So the cause is torch's intra-op threads oversubscribing a shared host** (24 threads per
process on 24 CPUs already busy with other work), not Isaac's Python and not the GPU; 118's
78 s on an idle host fits. The fix, to be planned before code: cap torch's threads in the
lanes (`OMP_NUM_THREADS` or `torch.set_num_threads` in `scripts/isaac_lane.sh` and the system
lane's batch step, or in the batch tests' setup).

## The fix's plan (approved by 133, 2026-11-26, before any code)

No test reads or asserts a thread count (`num_threads`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
`get_num_threads`, interop: none in `scensim_batch`'s, `scensim_sampler`'s, `scensim_isaac_world`'s
or roboracer's tests), and no runtime code sets one (only `scensim_batch/scripts/train_drift.py`
and `train_leadbrake.py`, opt-in by their `threads=`), so a cap in the test lanes' environment
reaches test processes only. It goes in the lanes, not the test package: `scensim_batch/test`
has no `conftest.py` or `__init__.py` and runs under pytest and unittest, so a shared setup
would be an import in each of its 21 modules and would miss the other suites.

1. `just test` exports `OMP_NUM_THREADS` and `MKL_NUM_THREADS` at its top, min(4, nproc) (run
   B's 4, never more than the host has); a value the caller set is kept (a host setting; no new
   variable). Every Python lane gets it.
2. `scripts/isaac_lane.sh` passes both through its `env -i` when set, as it does
   `CUDA_VISIBLE_DEVICES`.
3. Both lanes print torch's thread count: the lane's numpy line in Isaac's Python, and the
   recipe's per-Python numpy lines for the system Python, so a gate log shows the cap.
4. A test in `scripts/test_isaac_lane.py` that the lane passes `OMP_NUM_THREADS` through, with a
   stub install if that stays light; otherwise the gate's printed "torch threads 4" in both
   lanes is the evidence, and this record says so (133).

**The prediction (before the code and the gate).** In the full gate on 241 with the Isaac lane:
both lanes' `scensim_batch` suites finish in under 120 s, whatever the host's load (each
lane's 1-minute load at its start recorded from the log or `/proc/loadavg`); both lanes print
torch threads 4; and the gate passes. Held if all three; otherwise FAILED, as it comes out.

**The gate's result (2026-11-26, 34e0c374; 01:33 to 02:12, fresh worktree, CLAUDE.md's `clean=`
with `ISAAC_ROOT`): held.** `just test` began at a 1-minute load of 14.37 (sampled every 10 s
through it: 9.7 to 22.7, median 13.3, 158 samples).

- Torch threads: "torch threads 4" in both system-Python lines and in Isaac's.
- `scensim_batch` in Isaac's Python: `Ran 259 tests in 76.160s`, `OK (skipped=2)` (was 1029 s in
  186's gate on this host); in the system pytest lane: `247 passed, 12 skipped in 49.15s`. Both
  under 120 s.
- The gate: rc 0, "just test: done; Isaac-Python lane: ran (937 tests in 3 suites, OK)", pins 0
  mismatches, docs ok, no failure in any suite.

