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

**The tiles are not the cause**, as predicted (133: issue 119's fix is cleared): off and on move the rock alike under each query.
So it is not a regression from issue 119's fix. Every run is far under R4's 0.2-1.0 m.

**The push varies several times from run to run under sweep**: the rock moved 7-8 cm here where
C6b's sweep run, the same code and course, moved it 1.5 cm; under raycast 1.5-1.7 cm each time. The next lead is the push path: `RockStream.push`, its speed bound (`rocks.limit`:
no faster than the tyre surface at the push's height), the reaction's direction and share
(`rocks.reactions`), and how long the rock is awake under the tyre.

## The second test: the push path, instrumented (before the run)

loose_15 under both queries (sweep moved the rock five times as far), with every
`RockStream.push` call logged per PhysX step while a tyre is on the rock: the reaction from
`rocks.reactions` (its horizontal and vertical parts), the bound `rocks.limit` takes it to
(`v_push`, the scale), the force applied, and the rock's velocity; and the rock's own contact
with what it rests on, from PhysX's contact report on its prim (133): the normal force and the
friction (tangential) force, summed over its contacts.

- **118's prediction:** the rock is pressed down harder than it is pushed. Its share of the
  tyre's load goes on it downward (`-fv`), and its horizontal push is that times the face's
  gradient, then scaled down by `limit` to what takes it to the tyre surface's speed in one
  step. The friction under it, about 0.7 of (its share of the load + its weight), exceeds the
  limited push at nearly every step, so it slides only in the steps where the tyre's load on it
  is light. The contact report shows friction near its limit (tangential about 0.7 x normal)
  while the push lasts. Under sweep the share is spread differently over the footprint, which
  would explain its larger travel; R4's larger travel is not explained by this, and is a
  question for the second test's result.

## The second test's result (2026-11-23)

siw 1fe0e1f, aib ff5e72b, GPU0; NAS "2026-11-23 issue 122 push trace (118)". loose_15 moved 1.5 cm
(raycast) and 7.9 cm (sweep), as in the first test. Each front and rear wheel pushes the rock
over four PhysX steps; the first push of each wheel, raycast / sweep:

| | front wheel | rear wheel |
|---|---|---|
| reaction, horizontal | 6.1 / 5.4 kN | 7.5 / 9.1 kN |
| reaction, down | 12.1 / 4.5 kN | 7.8 / 9.6 kN |
| `limit`'s scale (bound 3.5-3.8 m/s) | 0.50 / 0.52 | 0.38 / 0.34 |
| applied, horizontal | 3.0 / 2.8 kN | 2.8 / 3.1 kN |
| the rock's contact normal force (next step) | 12.2 / 5.0 kN | 7.9 / 9.7 kN |

The following steps push 0.7-3 kN against 2-9 kN down, then nothing.

- **The prediction holds on the push side**: the rock is pressed down at least as hard as it is
  pushed, and `limit` halves or thirds the push, so the applied horizontal force (2.8-3.1 kN)
  is a quarter to a half of the normal force under the rock (5-12 kN). With friction about 0.6
  of the normal force, the push is under it in every step but sweep's first (2.8 kN against
  0.6 x 5.0 = 3.0 kN, where the rock reached 0.9 m/s).
- **Friction is not measured**: the contact report's impulse has no tangential part (0 at
  every step), so the report gives the normal force only. Measuring the friction needs PhysX's
  friction anchors (the full contact report).
- **Found on the way:** the rock touches both its collision tile and the base road mesh
  (`/World/env/Road`) at once, though the world's ground is in a group the rocks filter out. On
  a section_in_base course the tile now lies on the base's surface (issue 120), so the two
  coincide. Why the filter does not keep the rock off the base is open.
- R4's slice (`spikes/rock_fixtures.py`, swb_isaac_world 61bb368) used the same `reactions`,
  the same `limit` and the same rock material, and moved the rock 0.2-1.0 m. Next: run that
  spike as it is today: if it still moves the rock, the cause is in the world server's path
  (`RockStream`: waking, the speed it passes to `limit`, the ground it rests on); if it does
  not, something shared changed since R4.
