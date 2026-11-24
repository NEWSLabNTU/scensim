# 149: scensim_isaac_world's surface layer imports aib at load

**Status:** fixed 2026-11-24 (243; filed by 133). **Severity:** medium: the Isaac world server's
surface layer cannot be imported on a host without aib, where it should refuse by name.
**Found:** 2026-11-24, scensim 243, running `just test` on ROS 2 Jazzy for 092 K6.

## What happens

scensim_isaac_world's `package.xml` does not declare aib: aib lives in autoware_isaac_bridge,
whose `aib_launch` needs Autoware, so a simulation-only host could not resolve it. The rule it
states is that aib is "found at run time, refused by name when absent". Since siw cb4d749
(issue 108) `scensim_isaac_world/surface_layer.py` imports `aib.tyre_friction.FILTER_GRIP` at
module load, to set `PEAK_SPAN`. So on any host without aib (the simulation-only path of 081
and 082, Humble or Jazzy), importing the module fails with no name and no fix:

```
$ env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONNOUSERSITE=1 \
    PYTHONPATH=$SIW:$SIW/deps/scensim_world_protocol/scensim_world_server \
    python3 -c "import scensim_isaac_world.surface_layer"
  File ".../scensim_isaac_world/surface_layer.py", line 49, in <module>
    from aib.tyre_friction import FILTER_GRIP
ModuleNotFoundError: No module named 'aib'
```

(siw ac008bd, on this Humble host with no workspace sourced; the same on Jazzy, where `just
test` reported it as `test_authored`'s import error.)

Alongside it, `test_course_maps_c5d.LaneletHeights` needs pyproj and lacked the guard
`test_course_closed` has for it: Isaac's venv has no pyproj, and neither has a Jazzy image
without it.

## Fix (siw 7d032d6)

- `surface_layer.filter_grip()` reads `FILTER_GRIP` where the tyre's peak is computed, and
  `peak_span()` replaces the module constant `PEAK_SPAN`. Without aib the module imports, and
  the first use refuses by name:

  ```
  import ok
  refused: scensim_isaac_world: no aib (the Isaac ego, whose tyre_friction sets the tyre's
  peak) in this Python. From source: git submodule update --init --recursive
  src/scensim_isaac_world (its deps/ carry aib), then colcon build and source
  install/setup.bash; from a release: install its Isaac part, which carries aib
  ```

- `test_authored` and `test_surfaces` compute the rig's peaks at load: they take the checkout's
  `deps/autoware_isaac_bridge` aib when no aib is sourced, and skip, saying why, with neither.
  Before, whether they saw aib depended on which test module ran first (others put the deps/
  copy on `sys.path`).
- `LaneletHeights` skips without pyproj, as `test_course_closed` does.

Checked on this Humble host: siw's suite, run the same way on ac008bd and on 7d032d6, fails the
same tests except 8 that now pass (all `aib` import errors of `test_catalogue`,
`test_road_layer` and `test_issue_142`); none new. The 49 left are this host's own, as before.
