# 177: a fixture's road_detail.yaml in course/ is not read by the world server

**Status:** open; plan written 2026-11-27 (118, for 133), before any code. **Severity:** medium: a scenario run on either
fixture map has no road detail, and nothing says so unless the console is read. **Found:**
2026-11-25, scensim 118, while writing 086 C6e3's details (numbered by 133).

## What happens

fixture_c6a and fixture_c6b keep their road record at `course/road_detail.yaml` (the course
builder's record step writes it there; its header says "In course/, so it is not the map's
road detail"). The world server reads `<map dir>/road_detail.yaml`
(`road_layer.find`, `names.find_file`: the state directory's, else the map directory's).
So a `scensim run` on either map loads no road layer: no cleats, no pothole, no washboard, no
rocks. C6a to C6e1 never ran the world server on them: they used
`scensim_isaac_world.course.fixture_drive` or their own scripts, which read the file in
`course/`.

## For C6e3

C6e3 runs on hard-linked copies of the two maps (`isaac-ex/c6e/maps/`), each with its own
`road_detail.yaml` and `section.npz` at the top, and the runner refuses a run whose console
lacks the road layer's line and issue 168's line.

## The fix (to plan)

To decide in the plan: the builder writes the map's road detail at the top (the record step's
own copy kept in `course/`), or the world server falls back to `course/`, or a fixture map
refuses to load in a scenario run without one. Plan first, written before any code.

## The plan (118, 2026-11-27; written before any code, for 133)

**What the code does today** (scensim main 4647760c, `src/scensim_isaac_world`):
- **The record step.** `course/__main__.py` `main_fixture`, step `record`, calls
  `course/record.py` `write(work, st, in_mesh=True, features=...)`. That writes only
  `<map>/course/road_detail.yaml` (with `stations: section.npz`, beside it) and
  `<map>/course/section.npz`.
- **The design.** `record.py`'s docstring says the course record "switches nothing on in Isaac"
  on purpose. For a road course (Haruna), `course/road_detail.yaml` is the rails' and the
  planner's record, not a road layer.
- **What the world server reads.** `world.py` `_load_road` reads `road_layer.find(map dir)`,
  which is `names.find_file`: the state directory's `road_detail.yaml`, else
  `<map>/road_detail.yaml`. If that file is missing it **returns silently**. That is why
  nothing says so.
- **The fixture drivers.** `fixture_drive`, `lip_drive` and `rock_check` read `course/`
  directly, which is why C6a to C6e1 never noticed.

**Checked on a scratch directory (no code changed):**
- `course fixture_c6a.yaml <tmp> centreline record` writes `course/` only, and
  `road_layer.find(<tmp>)` names a `<tmp>/road_detail.yaml` that does not exist.
- A map-level copy of the course's entry with `stations: course/section.npz` loads with
  `road_layer.load`: one corridor, 640 m, its cleats, potholes and washboard, and the section
  at 1281 stations. `stations` resolves beside the YAML, so the path into `course/` works
  without copying the .npz.

**Of the three options in "The fix", the plan takes the first, with a warning added:**
1. **The builder writes the map's road detail for a fixture with features.** In
   `main_fixture`'s `record` step, when the course's `fixture:` block has `features:`, also
   write `<map>/road_detail.yaml`:
   - the same corridor (`stations: course/section.npz`, `section_in_base: true`, the
     features);
   - a header saying it is the map's road detail, written by the record step from the named
     course, and that `course/road_detail.yaml` stays the record.

   A road course (no `fixture:`) and a fixture without features write nothing new, so
   Haruna's maps and their own road details are untouched. An existing `<map>/road_detail.yaml`
   that was not written by the record step (no such header) is refused rather than
   overwritten, and the refusal names it.
2. **The world server warns.** In `_load_road`, when the map has no road detail but its
   `course/road_detail.yaml` carries a fixture's features (any feature key: C6a has cleats,
   potholes and washboard, C6b rocks, C6c profiles and washboard), log a
   WARNING naming both files and the builder's command (`... course <course.yaml> <map>
   record`). There is no fallback to `course/`: reading the record would switch on a road
   course's record in Isaac, against `record.py`'s design. There is no refusal either: a map
   with no road detail is valid.

   Rejected: (b) the world server falls back to `course/`, for the reason above; (c) refusing
   to load, because the fixture maps are built locally and a warning plus the builder's fix
   covers them.
- **base_drop (issue 168).** The builder runs under the system Python and cannot sample the
  base, so it leaves `base_drop` out. The world server then uses the features' bound and says
  so in its existing warning. The step prints the `base_drop --write` command to run under
  Isaac's Python. C6e3's copies had it written.
- **Which maps.** fixture_c6a, c6b and c6c all carry features (C6c too, which the record
  above did not name). **Existing maps.** Rerunning the `record` step (it fetches nothing) gives them their file. The
  C6e3 copies in `isaac-ex/c6e/maps/` keep their own.

**The smallest test that fails today.** In `test/test_course_c6a.py`, build
`fixture_c6a.yaml`'s `centreline` and `record` steps into a temporary map directory (offline,
under a second). Then assert that `road_layer.find(<tmp>)` exists and loads to one corridor with
C6a's cleats and potholes (the course's `fixture.features`). Today the file does not exist.

Companion tests:
- a road-course-shaped fixture without features writes no map file;
- a hand-written `<map>/road_detail.yaml` is refused, not overwritten;
- the world server's warning: a unit test on the function that decides it (`world.py` needs
  Isaac, so the decision is a plain function in `road_layer`, for example
  `course_record_unread(map_dir)`, which `_load_road` calls).

**Predictions.**
- The failing test fails today on the missing file, and passes after the builder change.
- The companion tests pass after the change.
- The Isaac-Python lane is unchanged (no Isaac code beyond one log call).
- `scensim_isaac_world`'s other course tests (`test_course_record`, `test_course_fixture`,
  `test_course_c6c`) are unchanged, because `course/road_detail.yaml` is written as before,
  byte for byte.
- *Live check (GPU0, after the code, if 133 wants one):* a `scensim run` of C6e3's fixture_c6b
  scenario on a map rebuilt by the new `record` step, not on the hand copies, logs `road
  detail .../fixture_c6b/road_detail.yaml: 1 corridor(s)` and issue 168's line, as the copies
  did.

## The code (118, 2026-11-27; after the plan, test first)

- **Commits:** siw 090dc0c, 57ec772 and e763170 on branch `issue-177`.
- **Tests:** `test/test_issue_177.py`, 9 tests. Before the code: 7 failed and 2 passed. The two
  that passed hold today's behaviour: the course record unchanged, and nothing for a fixture
  without features. One test was then corrected, because it counted the random potholes
  (`_holes`) rather than the fixed ones. It now compares the map file's corridor with the
  course record's, feature height for feature height, and still fails before the code on the
  missing file. After the code: 9 passed.
- **133's addition.** The record step writes its own map file again: the header line `#
  scensim course record step: course <name>` identifies it. A file with no such line, or with
  another course's name, is refused, with the path and the owner named, and left untouched.
  Both cases are tested.
- **A second gap, found on the plan's path.** Running the `record` step alone on a fixture
  (which the plan gives as the way to fix existing maps) went through `write_record`, which
  wrote the course record without the fixture's features. A rebuilt map would have lost them
  even from `course/`. `write_record` and `main_fixture` now share one function
  (`write_fixture_record`). This is tested.
- **The warning.** It is `road_layer.course_record_unread(map dir, state)`. `world.py`'s
  `_load_road` logs it when the map file is missing. Features are any corridor key besides
  `stations`, `section_in_base`, `centreline`, `section`, `seed` and `base_drop`.
- **Correction to the plan's base_drop point, written after the gate had started.** The plan
  said the builder "cannot sample the base". That is wrong: `base_drop` is numpy and yaml only
  (its own docstring says "no Isaac"), and it takes about 8 s on fixture_c6b. The record step
  still leaves it out, so that a build, and the tests, stay fast and the step stays the
  record's. The step now prints the exact command (`python3 -m scensim_isaac_world.base_drop
  <map dir> --write`), and the map file's header names plain `python3`, not Isaac's Python.
  This is siw 57ec772. The first gate (at 268fbf8b) was stopped for it.
- **The first full gate FAILED (043e94b8, 02:11:40 to 02:42:13, rc=1).** The Isaac-Python lane
  errored on all 9 new tests, with `No module named 'pyproj'`. The builder's `main` projects
  with pyproj (`centreline.Frame`), and Isaac's venv lacks it (issues 090, 149). Every other
  lane passed, including the system lane's 543 tests. The fix is to the tests only (siw
  e763170):
  - the 7 builder tests skip without pyproj, as `test_course_maps_c5d` and `test_course_closed`
    do;
  - the 2 warning tests build the course record from `fixture` and `record` directly, so they
    run in both lanes.

  The result is 9 passed in the system Python, and 2 passed with 7 skipped in Isaac's.

## Landed (2026-11-27)

The code is siw e763170. The pin commit is scensim main 7716891b, and the docs went first as
f5f46ea5. The gate passed at the landed tree (`ef22d921`): "gate end 03:17:23 rc=0",
"Isaac-Python lane: ran (967 tests in 3 suites, OK)". The 7 builder tests run in the system
lane only: they skip in the Isaac-Python lane, which has no pyproj (133). The 2 warning tests
run in both.

## The live check's plan (written 2026-11-27, before any run; 133)

**The map.** `isaac-ex/i177/maps/fixture_c6b` is a hard-linked copy of the fixture_c6b build,
without C6e3's hand-placed top-level `road_detail.yaml` and `section.npz`:
- the record step at siw e763170 wrote its `road_detail.yaml`;
- `base_drop --write` wrote 0.0000 m (a 0.010 m render drop);
- the rewritten files are unlinked, and C6e3's copy was checked unchanged by sha256;
- the rebuilt `course/road_detail.yaml` is byte-identical to the old one, and `course/section.npz`
  equal array for array;
- `pointcloud_map.pcd` is the same inode as r1's.

**The runs.** The testbench `isaac_i177_c6b` (C6e3's c6b as the pattern) runs on the workspace
gate-c5c at main 7716891b, built by the landing gate, on GPU0:
1. the 177 check: `fixture_c6b_down` (start x 20, goal x 490), as C6e3's b1 and b2;
2. run A for issues 181 and 182 (241): `fixture_c6b_r181` (start x 320), r1's scenario, on the
   same stack, with 181's and 182's topics recorded. Their predictions are in 181 and 182.

The runner refuses a run unless:
- the live bridge and world server run from gate-c5c's install;
- `result.json` names 7716891b and siw e763170;
- the console has the road line and issue 168's 0.010 m drop line.

**Predictions for the 177 check (before the run).**
- The world server's console reads `road detail .../fixture_c6b/road_detail.yaml: 1
  corridor(s)` and issue 168's `['/World/env/Road'] drawn 0.010 m`, with no "scensim issue 177"
  warning. This is the fix's live test.
- **What the ego meets first: the 15 cm static rock** at s 100 m, v 2.425 m, in the left wheel
  track of the lane (y 1.62). It is unchanged by any fix since C6e3: issue 180 is open, so it is
  passed as ground, with no object and no non-ground point published at it. The ego arrives at
  about 4.17 m/s with no braking for it.
- The plate meets the rock with the origin at x 97.3 ± 0.3 (b1 97.32, b2 97.29), seen in the
  truth trace as a speed drop in one 50 ms frame. Whether it stops dead (b1) or scrapes over
  (b2) is not predicted: one of each so far.
- Later fixtures, if it gets past (the loose rocks at 200 and 300, the 35 cm boulder at 400),
  are not predicted here. The run's verdict is not a 177 criterion. main now carries 190's
  -6 m/s^2 MRM, unlike C6e3's 0291abb3.
