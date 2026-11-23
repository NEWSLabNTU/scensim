# 119: the road detail collides with the chassis and skid plate only when the corridor has rocks

**Status:** fixed on siw `086-c6b` (5940bc2), not landed; the plan was approved by 133. **Severity:**
medium: whether a car's underbody meets a road's cleats, potholes, ruts and lips depends on
whether the same road also has rocks. **Found:** 2026-11-23, scensim 118, writing 086 C6b's
spec.

## What happens

The world server's road layer (`world.py`, `_load_road`) builds the detail's collision tiles,
the surface the chassis and the skid plate meet (`rock_layer.COLL_ROOT`, in the group the
chassis collides with and the wheels' ground query filters out), only inside
`rock_layer.RockStream`, which it makes only when a corridor has rocks. Without rocks the
detail is the tyre contact's (066 R5) and a render mesh (`road_layer.MeshStream`), with no
collider: the chassis and the plate meet the smooth base road only.

So a 15 cm cleat across the road passes through the underbody of a car whose wheels climb
it, unless rocks are on, when the plate strikes it. 086 C6a judged its fixtures without a
plate (`fixture_drive` made the vehicle without the rig's `ground_clearance`); on a corridor
without rocks the world server's ego would not have met them either.

## Measured

086 C6b's run (a) (siw 3ac4e4c, aib ff5e72b, 60 Hz, both queries; NAS "2026-11-23 086 C6b run
a skid plate (118)"): fixture_c6a without rocks, the plate on. Over cleat_15 at 10 m/s the
plate's lowest clearance over the true surface reaches -5 mm (raycast) and +0.5 mm (sweep),
against 137 mm before the cleat: with a collider it would strike; here it passes through.
cleat_10 leaves 38-54 mm. Run (b), with rocks, waits for this fix and issue 120's: with rocks
the tiles lie 2-7 cm above the true road on that course.

## The groups, and the resolution (133's conditions)

- The tiles are in the `roadDetail` collision group, which filters out aib's `groundQuery`:
  the wheels' suspension queries never hit them (their road is the base plus our contact's
  detail, R5). The chassis box, the skid plate (both `chassis`) and the rocks collide with
  them. The replay's jounce traces show no double count.
- The tiles sample the detail every 10 cm (`COLLISION_STEP`): a vertical face is a 10 cm ramp
  to the underbody. That is the limit of what plate-strike geometry can show; not changed.

## Fix plan (approved by 133, 2026-11-23)

- The detail's collision tiles become the road layer's own, built for every corridor whether
  or not it has rocks: a `TileColliders` stream (the code now in `RockStream`'s tile part,
  moved, unchanged), within the same 48 m of each vehicle, `COLLISION_STEP` 10 cm. The rocks'
  stream keeps the rocks and uses the tiles for their rest.
- `world.py` adds `COLL_ROOT` to the ground (the contacts' world) with any road layer, not only
  with rocks, and takes the one physics step after the road loads (issue 039) for the tiles as
  for the rock pool.
- Tests: a corridor without rocks gets its tiles (the stream's tile set by a car's position);
  the ground list names them; the tiles' heights are `Detail.surface_tile`'s (issue 120's
  fixed surface).
- **What it costs**, measured before landing, reported (C6b's budget judges): `fixture_cost`
  with 1, 2 and 4 cars, sweep and raycast, 60 Hz, GPU0 with nothing else on it, on fixture_c6a
  (no rocks) with the tiles against without (main), two runs a side, interleaved: frame p50
  and p95 and the tiles' own cost (their prims made a frame, ms).
- Behaviour, reported: C6b's run (a) cases again with the fix (the plate's clearance and
  strikes, J and body rise against run (a)).

## Measured with the fix

086, "C6b: issues 119 and 120 fixed": J within the runs' spread on cleat_10 under both queries,
no double count, the plate striking cleat_15 (+1.3 mm instead of -5 mm); frame p50 unchanged,
p95 about 12 ms higher with one to four cars (a tile collider's first step).
