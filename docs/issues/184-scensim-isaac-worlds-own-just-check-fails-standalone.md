# 184: scensim_isaac_world's own `just check` fails standalone

**Status:** open (243; numbered by 133 on 2026-11-25; the fix to be planned before any code).
**Severity:** low. The Isaac world server's suite passes where scensim runs it: scensim's `just
test` runs it in two lanes, with scensim's install sourced and in Isaac's own Python, and both
pass. But the repository's own gate, `just check` in a checkout of scensim_isaac_world with its
`deps/` submodules, fails on its main. So a change to it cannot be gated in its own repository:
the failures have to be compared against main's, test by test.
**Found:** 2026-11-25, scensim 243, gating issue 161's step 3 (scensim_isaac_world c6de0f09).
Main 4706ff9 fails the same way, so the failures predate 161.

## What happens

In a checkout of scensim_isaac_world at 4706ff9, `git submodule update --init`, a clean
environment (`env -i`, nothing sourced):

- **`just check` (`just test`, then pyflakes), system Python:** `Ran 376 tests`, `FAILED
  (failures=6, errors=58, skipped=26)`. The 6 failures are the `test_app_exit` ones below, for
  the same reason. The exception lines of the errors, counted from the log: `numpy.core.multiarray
  failed to import` 10 (a user-site numpy 2 under the system scipy: the recipe has no
  `PYTHONNOUSERSITE=1`, which scensim's lane sets), `No module named 'scensim_world_server'` 7
  (the recipe does not put `deps/scensim_world_protocol/scensim_world_server` on the path),
  `cannot import name 'LaunchDescription' from 'launch'` 6 and `No module named 'launch.actions'`
  1 (no ROS sourced), `No module named 'sim_vehicle_ecu'` 1, and 8 test modules that fail to
  import.
- **The same suite in Isaac's Python** (`ISAAC_ROOT=/var/tmp/aeon/isaac-sim-6.2`, `source
  scripts/isaac_env.sh`, `PYTHONNOUSERSITE=1 python3 -m unittest discover -s test`): `Ran 517
  tests`, `FAILED (failures=6, errors=1, skipped=19)`. The error is `test_catalogue`, which
  fails to import; the 6 failures are `test_app_exit.EntryPointTest` (`test_arc_drive`,
  `test_fixture_cost`, `test_fixture_drive`, `test_isaac_step`, `test_lip_drive`,
  `test_world_server`). Each expects the fake Kit's forced failure in the output and finds
  instead `ModuleNotFoundError: No module named 'sim_vehicle_ecu'` (`world.py` imports
  `catalogue`, which imports `aib.rig`, which imports `sim_vehicle_ecu`). `isaac_env.sh` puts aib
  on the path from `deps/`, but not aib's own dependency.
- **pyflakes:** `test/test_course_closed.py:57: 'pyproj' imported but unused`,
  `test/test_loop.py:3: 'os' imported but unused`, `test/test_world_server_launch.py:9: 'launch'
  imported but unused`.

Issue 161's commit (c6de0f09) adds two passing tests and no failure: the same failing set,
test for test, in Isaac's Python (`Ran 519`). In the system Python its run had 3 fewer import
failures than main's (`test_make_world`, `test_soil`, `test_surfaces` imported); why was not
looked into.

## Why scensim's lanes pass

Read from scensim's `justfile`, not traced further: its `just test` sources scensim's install
first (`source install/setup.bash`, with ROS and the workspace's packages) and runs the system
lane with `PYTHONNOUSERSITE=1`; its Isaac lane sources `src/scensim_isaac_world/scripts/isaac_env.sh`
from scensim's tree. Presumably the install is what provides `scensim_world_server`,
`sim_vehicle_ecu` and ROS's `launch` there; the plan confirms which provides what. The
repository's own recipe does neither.

## The fix wanted (a plan before any code)

The repository's `just check` should pass in its own checkout, on its main, in both Pythons,
with only its `deps/` submodules and an Isaac install. Each cause above needs a decision, for
example: `sim_vehicle_ecu` as a `deps/` submodule, or found through aib's own `deps/`;
`deps/scensim_world_protocol/scensim_world_server` and `PYTHONNOUSERSITE=1` in the recipe; the
ROS-only tests skipped with a reason when `launch` does not import; the pyflakes findings
removed. Then the check: `just check` clean on the fixed main, both lanes, and scensim's lanes
unchanged.
