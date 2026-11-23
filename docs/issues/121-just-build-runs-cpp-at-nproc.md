# 121: just build compiles SSv2's C++ at one job per core, about 2 GB a compiler

**Status:** fixed: `just build` takes its job count from `scripts/build_jobs.py`. **Severity:** medium: a build beside
running work can take a host's memory, and the kernel's OOM killer then picks a training run.
**Found:** 2026-11-23, scensim 243, measuring a full gate's memory; assigned to 241 by 133.

## What happened

On 2026-11-23 the kernel's OOM killer ended row b's restarted P2 seeds 1 and 2 on 139, at
iterations about 3349 and 3364 of 5000. A full `just build && just test` gate (issue 113's) had
started on the same 60 GB host with 9 GB available beside the five drift seeds (roadmap 094,
P2's "gate-memory incident"). Both seeds rerun from scratch.

243 then measured where a full gate's memory goes. The peak, about 30 GB, is SSv2's C++:
`openscenario_interpreter` and its neighbours, built whenever SSv2 is not already in the build
tree (a fresh worktree, or a pin that moved it). Each compiler (`cc1plus`) on those sources
holds about 2 GB, and the build runs one per core.

## Why

`just build` runs `colcon build` with colcon's defaults:

- colcon starts one package per core at once (`--parallel-workers`, default the CPU count);
- colcon-cmake builds each CMake package with `make -j N -l N`, N the CPU count, unless
  `MAKEFLAGS` names a job count;
- cargo builds with one job per core (`CARGO_BUILD_JOBS` unset).

So a build asks for as many compilers as there are cores, whatever memory the host has free.
On 241 that is 24 compilers, about 48 GB at 2 GB each, and colcon can run several C++ packages
side by side. On a 60 GB host with training running, it does not fit.

For the gates since then, the gate runs with `MAKEFLAGS=-j6`, `CARGO_BUILD_JOBS=6` and colcon at
2 workers (`COLCON_DEFAULTS_FILE`), set by hand outside the recipe (243, 2026-11-23).

## Fix

`just build` picks its job count from the memory the host has free, or takes it from a host
setting, and says what it picked:

- **`SCENSIM_BUILD_JOBS`** (a host setting, the environment or `.env`): the total number of
  compile jobs. Unset: half of `MemAvailable` at the build's start divided by 2.5 GB a job
  (2 GB measured, plus a margin), at least 1 and at most the CPU count. The other half stays
  for what runs beside the build, which can grow while it compiles.
- colcon runs **2 packages** at a time (1 when the total is under 4), and each package's make
  and cargo get the total divided by that: `MAKEFLAGS=-jJ`, `CARGO_BUILD_JOBS=J`. So at most
  the total runs at once, wherever the jobs come from.
- A `MAKEFLAGS`, `CARGO_BUILD_JOBS` or colcon parallel-worker setting already in the
  environment is kept, not overridden. The recipe prints the job counts it used, and where
  they came from.

Tests: the job-count choice is a pure function of the free memory, the CPU count and the
host setting, tested without a build (memory far below and above the cores' need, the host
setting over both, the existing `MAKEFLAGS` kept).

**Follow-up (133), done in acb e1bb5dc:** acb's own `just build` (its workspace, which the
gate builds first) had colcon's defaults too. It builds no SSv2, but carla-sys and the Rust
crates compiled at a job per core. acb's justfile now evaluates the same script, with the same
host setting (acb reads this repository's `.env` through just's `dotenv-load`), and its `just
test` runs the same tests. Built in a fresh acb worktree with no caps (241, 2026-11-23): 12
jobs chosen (half of 64.6 GB available, 24 CPUs), 22 packages in 7 min 40 s, the compilers'
summed RSS at most 12.4 GB and available memory at least 53 GB; nextest 245 passed.

**Two copies.** `scripts/build_jobs.py` and `scripts/test_build_jobs.py` exist here and in acb
(autoware_carla_bridge's `scripts/`), the same apart from their docstrings: acb builds on its
own, without this repository. Whoever changes one changes the other in the same landing.

## What the fix does

`scripts/build_jobs.py` prints the shell assignments `just build` evaluates before colcon, and a
line saying what it chose. On 241 with 56 GB available and 24 CPUs:

```
build jobs: 11 (half of 56.2 GB available at 2.5 GB a job, 24 CPUs): colcon 2 package(s) at
once, make and cargo 5 each
```

A `MAKEFLAGS` without a job count keeps its other flags and gains `-jJ`. With a
`COLCON_DEFAULTS_FILE` in the environment the recipe passes no `--parallel-workers`, so the
file's setting stands. `scripts/test_build_jobs.py` (in `just test`) checks the choice: little
memory caps it below the cores (16 GB: 3 jobs, one package at a time), plenty stops at the
cores (24), no memory still builds with 1, the host setting wins, a bad one is refused, and
settings already in the environment are kept.

Measured in the gate on 2d718c87 (241, 2026-11-23, a fresh worktree, so SSv2's C++ built from
nothing, P1 and P4 training on the host): `just build` chose 12 jobs (half of 63.6 GB available,
24 CPUs), two packages of 6, and finished 75 packages in 22 min 10 s. Sampled every 5 s, the
compilers' and linkers' summed RSS peaked at 14.6 GB (12 cc1plus and 11 rustc at that moment),
against the 30 GB the choice allows at 2.5 GB a job; the host's used memory peaked at 66 GB from
59 to 60 GB before the gate, and its available memory never fell below 52 GB. So 2.5 GB a job held
with make and cargo in two workers side by side, with room: about 0.6 GB a compiler process on
average at the peak. The counts include any other user's compilers on the host, and at times
show more cc1plus (18) and rustc (29) than the jobs, which a job's helper processes and cargo's
build scripts account for in part. The samples: `/var/tmp/aeon/wl-port/gate121-compilers.csv`
and `gate121-mem.csv`.

`SCENSIM_BUILD_JOBS` belongs beside the other host settings in CLAUDE.md, which this change
does not edit.
