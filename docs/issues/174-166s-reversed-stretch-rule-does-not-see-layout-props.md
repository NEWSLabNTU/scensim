# 174: 166's reversed-stretch rule does not see layout props (they become LanePositions only in the run's copy)

**Status:** open (243; numbered by 133, 2026-11-25; after 092 K9f-b lands). **Severity:** low
today: no layout yet places a prop in a reversed stretch. A prop placed in one would stand
facing backward on SSv2's spline, as issue 166 describes for an entity, and nothing would say
so.
**Found:** 2026-11-25, scensim 243, rebasing 092 K9f-b onto issue 166 (main 1fad31e6).

## What happens

Issue 166 checks a scenario's LanePositions against SSv2's spline: `scensim check` refuses a
literal one inside a reversed stretch (`project.check_scenario`, `lane_positions.fixed_problems`)
and `scensim run` warns of a bound one (`run.warn_lane_positions`). Both read the source
scenario.

A prop layout (092 K9f-b) names its props in `layouts/<map>/<name>.yaml`, on a lane anchor and
an s (`at: {lane: west_street, s: 20, offset: -1.3}`). The run resolves each to a literal
lanelet and lanelet-local s and writes it as a `LanePosition` only into the run's copy,
`<run dir>/scenario.xosc`. So neither of 166's checks sees a layout's props: not in `testbench
check` (the source has none), not in the run (the warning reads the source).

## Shown not to matter for CS3

`lane_positions.fixed_problems` on K9f-b's CARLA copy of `cs3_layout.xosc` (closure=closed,
2026-11-25, sha256 5fd2feb1...) returned `[]`: its three props stand on lanelet 6583 at s 20,
and `lane_positions.stretches(Town01, 6583)` is empty (166's own survey also lists 6583 as
having none).

## The plan, before any code

One rule with 166, applied to what a layout places:

1. **`testbench check` refuses** (`project.layout_problems`): for each prop a layout places on a
   lane, `lane_positions.inside(map_dir, lanelet, s)` on the placed lanelet and lanelet-local s;
   inside a stretch, a refused finding naming the layout, the prop, the lanelet and s and the
   stretch, with the fix "move s outside the stretch" (166's message). A layout file is written
   in, so it is refused, as a literal LanePosition is.
2. **The run warns** (`run.check_layouts`), as 166's run does for a bound one, from the same
   placed props; a map that does not load is said, never a stopped run.
3. A prop at a point anchor (a `WorldPosition`) is not on the spline and is not checked.
4. Tests: a layout prop placed in a stretch of a test map is refused by the check and warned by
   the run; one outside is neither; a map that does not load is a host finding, not a refusal.

The check, after the fix: CS3's layout check stays clean, and a test layout moved into one of
Town01's stretches is refused by name.
