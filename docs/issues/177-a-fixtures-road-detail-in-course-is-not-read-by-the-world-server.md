# 177: a fixture's road_detail.yaml in course/ is not read by the world server

**Status:** open; plan first (133, 2026-11-25). **Severity:** medium: a scenario run on either
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
