# 122: loose rocks barely move when a wheel climbs them

**Status:** open, being tested. **Severity:** medium: a loose rock under a tyre should be
shoved or kicked (066 R4's slice: 0.2-1.0 m), and here it stays put, so C6b's rocks behave as
static ones and its budget's rock costs would be measured on rocks that do not behave.
**Found:** 2026-11-23, scensim 118, 086 C6b's fixture runs.

## What happens

086 C6b's loose_15 (a loose 13.2 kg rock, 15 cm, under the left wheels at 40 km/h) and loose_8
(2.0 kg, 8 cm, under the tyres' outer edge) on fixture_c6b (siw 975871e, aib ff5e72b, 60 Hz,
both queries): each rock wakes as a rigid body before the wheel reaches it, the wheel climbs it
(12.7 kN on loose_15), and the rock moves 1.5 cm (loose_15) and 0.9-1.4 cm (loose_8), its
largest speed 0.01-0.02 m/s (one loose_8 run 1.9 m/s for a step). On waking it settles 7 mm onto
the collision tiles. R4's slice moved the same kind of rock 0.2-0.5 m on and 0.9-1.0 m aside, on
a flat base without collision tiles (the tiles came with R4's second slice and are now built for
every road, issue 119).

## The first test (before the run)

133's lead: the tiles. loose_15 with the tiles off and the rocks resting on the base mesh, as
R4's first slice had them (`fixture_drive --rocks-on-base`: no tile colliders, the world's ground
not filtered out for the rocks), against tiles on, both queries, the rest as C6b ran it.
Measured: how far the rock moves and its largest speed.

- If the rock moves (more than 5 cm, C6b's check) with the tiles off and not with them on, the
  tiles are the cause: a regression from issue 119's fix (tiles for every road), to be fixed
  before 119's cost is judged.
- If it stays put either way, the tiles are not the cause, and the push path (`RockStream.push`,
  `rocks.limit`'s speed bound, the rock's mass and friction) is next.
- **118's prediction:** it stays put either way. The push and its limit are the same with or
  without tiles, and a 13 kg rock pressed down by a share of the tyre's load meets the same
  friction on the base mesh as on a tile.

## The first test's result (2026-11-23)

siw 502bc03, aib ff5e72b, GPU0; NAS "2026-11-23 issue 122 tiles off test (118)". loose_15, the
rock's travel and largest speed, tiles off (on the base mesh) / on:

| query | moved | largest speed |
|---|---|---|
| raycast | 1.7 / 1.5 cm | 0.15 / 0.007 m/s |
| sweep | 7.2 / 7.9 cm | 1.2 / 1.0 m/s |

**The tiles are not the cause**, as predicted: off and on move the rock alike under each query.
So it is not a regression from issue 119's fix. Two things the test also shows: under sweep the
rock moved 7-8 cm here where C6b's sweep run moved it 1.5 cm (the same code and course: the
rock's push varies from run to run by several times), and every run is far under R4's
0.2-1.0 m. The next lead is the push path: `RockStream.push`, its speed bound (`rocks.limit`:
no faster than the tyre surface at the push's height), the reaction's direction and share
(`rocks.reactions`), and how long the rock is awake under the tyre.
