# 146: release.yml's rosdep step misses scensim_sampler

**Status:** fixed 2026-11-24 (243; filed by 133). **Severity:** high: a release blocker; the
next release's build-sim job fails on both distros before it builds anything.
**Found:** 2026-11-24, scensim 243, while preparing 092 K6's Jazzy container from the build-sim
job's steps.

## What happens

The build-sim job installs the simulation side's system dependencies with
`rosdep install --from-paths <paths> --ignore-src`. `--ignore-src` skips a dependency only when
the package it names is found under `<paths>`. Since c94621be (092 K3, after v0.2.1) the
`scensim` package has an `exec_depend` on `scensim_sampler`, but `src/scensim_sampler` was never
added to the step's paths. rosdep then looks `scensim_sampler` up in rosdistro, does not find it,
and the step fails:

```
ERROR: the following packages/stacks could not have their rosdep keys resolved
to system dependencies:
scensim: Cannot locate rosdep definition for [scensim_sampler]
```

Seen in a ros:jazzy container running the step's command on main 19621fc2. The command is the
same for Humble, so both distros' jobs fail. v0.2.0 and v0.2.1 predate the dependency and are
not affected.

## Fix

- `src/scensim_sampler` is added to the step's paths.
- `scripts/check_release_rosdep.py`, run by `just test`, reads the step's paths from
  release.yml (its env variables expanded), finds packages under them as rosdep does
  (catkin_pkg, so the components' deps/ copies behind COLCON_IGNORE are skipped), and fails
  naming any dependency, of any type rosdep installs and with its condition evaluated for ROS 2,
  on a package of this workspace that lies outside them. On 19621fc2 it reports exactly this
  case; with the fix it passes. `scripts/test_check_release_rosdep.py` covers the parsing, a
  missing path, a deps/ copy, a rosdistro dependency and a false condition.
