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

## Step 0, read only (2026-11-26, 243; 133's OK the same day)

On scensim_isaac_world main 3a948eea, in a fresh clone with **every** `deps/` submodule
initialised recursively (`git submodule update --init --recursive`), in a clean environment
(`env -i`, nothing sourced). Logs: `/var/tmp/aeon/siw-184-step0/`.

- **Isaac's Python** (`source scripts/isaac_env.sh`, `PYTHONNOUSERSITE=1 python3 -m unittest
  discover -s test`): `Ran 525 tests`, `OK (skipped=19)`. **The lane already passes.** The
  record's 6 `test_app_exit` failures and `test_catalogue`'s import error came from a
  non-recursive `git submodule update --init`: aib finds `sim_vehicle_ecu` itself, in its own
  `deps/` (`aib.deps.use`, `deps/autoware_isaac_bridge/deps/sim_vehicle_ecu`), so a recursive
  checkout has it. Nothing to fix there; the recipe's instructions only.
- **The system Python, `just check` as it stands:** `Ran 489 tests`, `FAILED (errors=54,
  skipped=28)`, and pyflakes never runs (`check` depends on `test`). The errors, by cause:
  - a user-site numpy 2 under the system's packages built for numpy 1 (no `PYTHONNOUSERSITE=1`
    in the recipe): 33 `numpy.dtype size changed`, 10 `numpy.core.multiarray failed to import`,
    10 `_ARRAY_API not found` (test_rocks, test_course_closed, test_course_record,
    test_rock_layer and others);
  - `No module named 'scensim_world_server'` 4 (the recipe does not put
    `deps/scensim_world_protocol/scensim_world_server` on the path);
  - ROS's `launch` 7 (`test_world_server_launch.LaunchRefusals`).
- **The same, with only the two environment fixes** (`PYTHONNOUSERSITE=1
  PYTHONPATH=deps/scensim_world_protocol/scensim_world_server`, no code changed): `Ran 524
  tests`, `FAILED (errors=7, skipped=40)`, the 7 all `LaunchRefusals`.
- **Why `LaunchRefusals` is not skipped.** The module already has `skipUnless(HAVE_LAUNCH)`, but
  its guard is `import launch`, and in this repository's own checkout `launch` is the
  repository's `launch/` directory (the launch files), importable as a namespace package from
  the discovered top-level directory. So `HAVE_LAUNCH` is true, and `from launch import
  LaunchDescription` fails in the tests. Where ROS is sourced (scensim's gate) the real `launch`
  wins and the 7 run and pass: run verbosely in scensim's gate tree (9468ae20, install
  sourced), `Ran 8 tests`, `OK`, each `LaunchRefusals` test `ok`. In Isaac's Python `launch` is
  Isaac's bundled copy, which does not import (`No module named 'lark'`), so they are skipped
  there today.
- **pyflakes:** the same 3 findings as recorded. Two are guard imports marked `# noqa: F401`,
  which pyflakes does not read (`test_course_closed.py:57` `pyproj`,
  `test_world_server_launch.py:9` `launch`); one is an unused `import os` (`test_loop.py:3`).
- **check_pins and the aib route (133's question).** scensim's `check_pins` compares each
  component's own `deps/` pins with scensim's, one level. siw's `deps/autoware_isaac_bridge`
  must equal scensim's aib pin, and aib's `deps/sim_vehicle_ecu` at that commit must equal
  scensim's `src/sim_vehicle_ecu`. siw's nested `deps/autoware_isaac_bridge/deps/sim_vehicle_ecu`
  is fixed by aib's commit, so it cannot drift without one of those two checks failing: the
  route is covered transitively. And no code needs it changed: aib already resolves it.

## The plan (2026-11-26, 243; for 133, before any code)

In scensim_isaac_world, on a branch from its main, then a scensim pin move:

1. **The recipe.** `test` runs `PYTHONNOUSERSITE=1
   PYTHONPATH=deps/scensim_world_protocol/scensim_world_server${PYTHONPATH:+:$PYTHONPATH}
   python3 -m unittest discover -s test`, as scensim's system lane does. A comment says the
   checkout needs `git submodule update --init --recursive` (aib's own deps carry
   `sim_vehicle_ecu`). No new submodule: **no `deps/sim_vehicle_ecu`**, since aib's own is the
   one aib imports, and `check_pins` covers it as above.
2. **The ROS guard.** `test_world_server_launch.HAVE_LAUNCH` becomes "ROS 2's `launch` imports
   with `launch.actions`": `importlib.util.find_spec("launch.actions") is not None`, any import
   error counting as no, so the repository's own `launch/` directory is not mistaken for it.
   The import line goes (pyflakes' finding with it).
3. **pyflakes.** `test_course_closed`'s guard becomes `importlib.util.find_spec("pyproj")`, the
   same skip reason; `test_loop`'s unused `os` goes.
4. **Predictions, written before the code:**
   - siw standalone, the system Python, `just check`: `Ran 524 tests`, `OK (skipped=47)` (40
     plus the 7 `LaunchRefusals`, skipped as "no ROS 2 launch"), then pyflakes silent; exit 0.
   - siw standalone, Isaac's Python: `Ran 525 tests`, `OK (skipped=19)`, unchanged.
   - scensim's full gate with siw pinned to the fix (`ISAAC_ROOT` passed): clean; the Isaac lane
     `ran` with 937 tests, OK, as on main; the 7 `LaunchRefusals` **ran** in the system lane,
     shown by running that module verbosely in the gate tree after the gate (`ok` each, not
     `skipped`), and siw's system-lane line in the gate log unchanged from main's gate.
5. **Landing:** the siw branch pushed to siw main with 133's OK, then scensim's
   `src/scensim_isaac_world` pin moved to it on the main of that moment, the full gate, then a
   push with 133's OK. Not touched: K9f-a's own siw commit (76ba145), which rebases onto the
   fixed siw main in its own cascade.

