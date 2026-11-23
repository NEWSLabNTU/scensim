# 120: on a section_in_base corridor, the detail's tiles, render mesh and rock rests leave out the section

**Status:** open; the fix plan below is for 133's approval, before any code. **Severity:**
medium: on such a corridor the render mesh hovers, the collision tiles stand and the rocks rest
2-7 cm above the true road. **Found:** 2026-11-23, scensim 118, while checking issue 119.

## What happens

A course built with the section in its base mesh (the fixture courses since 086 C5b, whose
road record says `section_in_base: true`) gives the road layer the features only:
`Corridor.features` leaves the section out, since PhysX's wheel query already sees it in the
base. That is right for the tyre contact, which stands on the base under each wheel plus the
detail. It is wrong for the three that build an absolute surface from the corridor's base
height and the detail (`base_z(u) + detail`), with no section:

- `Detail.surface_tile`, the render mesh (`MeshStream`) and the collision tiles (`rock_layer`,
  every `COLLISION_STEP`);
- `rocks.place`, a rock's resting height.

So on such a corridor all three lie flat at the centreline's height over a crowned road with
its shoulders and ditch.

## Measured (offline, 2026-11-23)

fixture_c6a (2 x 3.25 m lanes, a 2 % crown, 0.75 m shoulders), the tile's surface less the
true one (base, section and detail): +0.001 m at the centreline, +0.032 m at v = 1.6 m,
+0.065 m at the carriageway's edge, +0.071 m on the shoulder, the same on both sides.

Haruna's record has no `section_in_base` (its detail carries the section), and its tiles
match the true surface but for the roughness (mean +0.005 m, p95 0.06 m over 715000 samples).

**Nothing past is affected:** the world server reads the road layer only from
`<map dir>/road_detail.yaml`, and no Haruna or fixture map has one (theirs is in `course/`),
so no world-server run so far loaded a road layer on them. `fixture_drive` (086 C6a) loaded
the course's directly, without rocks, so without tiles; its render mesh was not made.

## Fix plan (for approval, before any code)

- `road_detail.Corridor` gains the true surface's base, `surface_base(u, v)`: `base_z(u)`, plus
  the record's section (`StationSection(stations).height_uv(u, v)`) on a `section_in_base`
  corridor. `Detail.surface_tile` and `rocks.place` use it in place of `base_z`.
- Tests: on a `section_in_base` corridor, `surface_tile` less (base + section + features) at
  most 1 mm, with no roughness; a placed rock's lowest point on the true surface less its
  sink; a corridor without `section_in_base` unchanged to the bit.
- No cost: one section evaluation a tile sample, in the tile worker.
- **C6b's Haruna budget** needs `<map dir>/road_detail.yaml`, which no map has: the C6b runs
  put one in Haruna's map directory (the course's record with the rock cover), and the
  course builder writing it is a later step's, not this fix's.
