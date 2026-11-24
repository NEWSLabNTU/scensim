# 140: the skid plate takes a 6.3 kN s impulse from a detail collision tile across an 8 cm gap

**Status:** open, a record; a geometric probe comes before any change to contact offsets
(133). **Severity:** medium: it costs the car 1.4 m/s in one step and puts it on one wheel for
0.7 s, which brought issue 137's throw about. **Found:** 2026-11-24, scensim 118, issue 137's
source probe on 086 C6d's *rough_none* map.

## What happens

One car (`fixture_cost --follow`, siw 31593ab) drives Haruna's rough map at 10 m/s. Its
front-left wheel drops into a Poisson pothole at s 186 m (t 16.45 s) and climbs its far edge
two steps later with a bounded load (11.7 kN). At step 994 (t 16.55 s) the body's speed falls by
1.40 m/s in one 1/60 s step, about 25 g, with every wheel's longitudinal force under 0.5 kN.
From step 996 three wheels are off the ground, in our contact and in PhysX's, for 0.7 s, the car
on its rear-right wheel with its roll growing to 0.33 rad.

## What the chassis touched

The chassis's PhysX contact report (PhysxContactReportAPI on the body, threshold 0) at t 16.45
to 16.70 s: the body and the skid plate are in contact, within their contact offsets, with the
base road (`/World/env/Road`), the terrain and the detail collision tile `t_5_21_26` at every
step, separations 0.08 to 0.47 m, every point with no impulse except one. At step 994 the skid
plate's point on the tile at (81.60, 345.30, -108.996):

- the normal (-0.021, -0.479, 0.877): a face 29 deg from level facing the car (it drives +y),
  the pothole's far wall in the tile's 10 cm mesh;
- the separation **+0.083 m** (a gap, not a penetration);
- the impulse (-133, -3011, 5513) N s, 6.28 kN s along the normal. Its part along the road,
  3.0 kN s, is the 1.4 m/s the car lost.

The car's 10 m/s along that normal closes about 4.8 m/s, 8 cm in one 1/60 s step: the solver
treated the point as one the step would close, and removed the closing speed.

## Open

Whether the plate's front edge would have reached the wall's top in that step (a true strike,
as the pothole lowers the front-left corner) or PhysX acted on the face's plane beyond a wall
only 3 cm tall. The probe: the plate's lowest points against the tile's own height along their
path over steps 990 to 998, and PhysX's contactOffset and restOffset for the plate, the body and
the tile, recorded beside the 8.3 cm separation. Contact offsets are not changed before it.

## The geometric probe (before the run)

The same drive (*rough_none*, one car, raycast; siw main 4df3198, whose issue 137 fix acts only
from step 997, after the strike), logging at t 16.45 to 16.70 s (steps 987 to 1001) only:

- the skid plate's bottom face in the world (its corners and a 5 cm grid over it, from its
  prim's transform and size);
- under each of those points, the tile `t_5_21_26`'s height (a downward PhysX raycast, the hits
  on that tile alone), now and along the point's path over the next step (its velocity times
  1/60 s, in 1 cm steps): the least vertical gap and where;
- the chassis's contact report as before, to place the 6.28 kN s point again;
- PhysX's contactOffset and restOffset for the plate, the body and the tile: what is authored on
  each prim (PhysxCollisionAPI), and the scene's default where nothing is.

- **118's prediction:** not a true strike. Over steps 990 to 998 no point of the plate's bottom
  comes within 3 cm of the tile, now or along its next step's path: the wall's top is at the
  road's level and the plate stays some cm above it, the front-left corner lowered by the pothole
  but not to the road. The 6.28 kN s point repeats at step 994. The plate and the tile carry no
  authored offsets, and the plate's own contact offset (with the tile's) reaches past the
  8.3 cm gap: PhysX made the point from the face's plane within that reach and the solver acted
  on it as closing.

### The geometric probe's result (2026-11-24)

*rough_none*, siw main 4df3198, GPU0 quiet. Two starts died in the probe's own code within 8 s
(a stale commit checked out, stopped before it ran; then the probe reading issue 137's old plane
tuple) and measured nothing. The third ran to its end (rc 0). The strike repeats to the digit:
step 994, the skid plate on tile `t_5_21_26` at (81.60, 345.30, -108.996), normal (-0.021,
-0.479, 0.877), separation +0.0826 m, 6283 N s.

- **Not a true strike.** Over steps 987 to 1004, of the plate bottom's 1288 points (a 5 cm grid
  and its edges, every one over the tile), the least vertical gap to the tile was **9.75 cm**
  (step 993, along its next step's path), and 10.4 cm at step 994 itself. Near the struck point
  the plate's bottom was 11.2 cm above the tile at step 994. The plate passed over the pothole's
  far wall with about 10 cm to spare.
- **What the solver acted on.** The plate's motion over step 994 along the struck face's normal
  was 8.63 cm, against the point's 8.26 cm: on the face's plane, extended past the 3 cm wall, the
  step would have closed the gap, and the solver removed the closing speed (the impulse is along
  the normal alone).
- **The contact offsets.** Neither the plate, the body nor the tile carries PhysxCollisionAPI:
  nothing is authored, so PhysX's own defaults apply. They reach far: in this window PhysX made
  contact points with separations up to 0.33 m between the plate and the tile, 1.8 m against the
  base road and 7.4 m against the terrain. So a point on any tile face within about a third of a
  metre of the plate exists, and a steep face whose plane the plate approaches fast enough draws
  an impulse.
- **118's prediction: held.** No point of the plate within 3 cm of the tile (the least was
  9.75 cm), the strike again at step 994, no authored offsets, and a reach past the 8.3 cm gap.

So the strike is PhysX acting on a tile face's plane across a real gap, not geometry: the tile's
10 cm mesh turns a pothole's 3 cm wall into faces as steep as 29 deg, and the default contact
reach lets the plate's approach to the plane of one count as a collision. Not changed yet (133:
the record and the probe first). Options for whoever takes it: author a small contact offset on
the detail tiles and the plate (a few cm: the gap at which a contact may form), or keep steep
tile faces out of the chassis's filter, each with its own probe that the plate still meets a
real ridge or rock.

## The fix's first measurement (before the run)

133 chose an authored contact offset (restOffset 0) on the tiles and the plate, small, since
any reach at least the step's 8.6 cm along the face would keep the 994 contact. The chassis has
no CCD authored (PhysX's default: off), so its far contacts come from the offsets alone. The
plate is aib's prim; the tiles are siw's. Before touching aib, one run with only the tiles
authored (`rock_layer.TILE_CONTACT_OFFSET` 0.02 m, PhysX's customary 2 cm at metre scale), the
plate unchanged, the same probe as before plus the authored offsets of the base road and the
terrain (their 1.8 m and 7.4 m reaches).

- **118's prediction:** the plate's default reach is small (PhysX's auto offset follows a shape's
  size, and the 0.33 m came from the 16 m tile), so with the tiles at 0.02 m no plate-tile point
  is made beyond 0.06 m, the 994 impulse is gone, and the car keeps its speed through step 994
  (no 1.4 m/s step). The base road and terrain carry authored offsets from the world's USD, or
  large auto ones; either way they do not touch the plate's motion here (no impulse, as before).

### The first measurement's result (2026-11-24)

*rough_none*, siw `issue-140` 5cf3834 (tiles at 0.02 m, restOffset 0; the plate as before), GPU0
quiet, to the run's end (rc 0).

- **The strike is gone.** No contact point between the plate and any tile in t 16.45 to
  16.70 s, no impulse on the chassis, and the car held 10.13 to 10.17 m/s through step 994 with
  no roll (before: 1.4 m/s lost and 0.7 s on one wheel). The plate's least vertical gap to the
  tile in the window was 8.96 cm.
- **The plate's own reach.** With no plate-tile point made at gaps down to 8.96 cm, the plate's
  default contact offset plus the tile's 2 cm is under about 9 cm: the plate's own is under
  about 7 cm. Its value is not read; authoring it is what pins it.
- **The base road and the terrain** carry no PhysxCollisionAPI either; their default reach to
  the chassis was up to 0.43 m (road) and 7.3 m (terrain), with no impulse, as before.
- **118's prediction: held** (no plate-tile point beyond 0.06 m: none was made at all; the 994
  impulse and the 1.4 m/s step gone).

(Corrected after the results: the collision tiles' mesh is 10 cm, every second sample of the
5 cm detail, `rock_layer.COLLISION_STEP` 2; this record and issue 137's first said 5 cm.)

## The fix (before the proof runs)

siw `issue-140` 56b8e39 on siw main 87591b4 (issue 139's fix): the detail collision tiles carry
PhysxCollisionAPI contactOffset `TILE_CONTACT_OFFSET` = 0.02 m and restOffset 0; nothing else
changes. 133: the tile offset alone is the fix, in siw; aib's prims are not edited from siw.
`test/test_issue_140.py` (a stand-in for pxr): a tile gets both offsets, None leaves PhysX's.

Why 2 cm and not the step's travel: any reach at least the step's motion along a face's normal
(8.6 cm at step 994) keeps the ghost contact; 2 cm is PhysX's customary offset at metre scale,
and with the plate's own (under 7 cm) the reach stays under the 8.96 cm the plate passed at.

What keeps a thin feature from being skipped with a small reach: the plate is 2.265 m long
(wheelbase 3.005 m less two 0.37 m radii), 1.33 m wide and 4 cm thick, its bottom 13.8 cm over
the ground. At the fixtures' top speed, 20 m/s, it moves 33 cm in a 1/60 s step; at C6b's
11.1 m/s, 18.5 cm. Anything that enters under its front edge in a step is inside the plate's
footprint the next (33 cm of 226.5 cm), so it is found as an overlap and pushed out, never
passed through. Nothing here is thinner than a step along the travel and taller than the plate's
bottom: a rock is its own body (speculative CCD on, `rock_layer.SPECULATIVE_CCD`, untouched by
this fix), and a tile's face is part of a closed surface under the plate, not a blade.

Follow-ups (133), not part of this fix:

- the plate's own contact offset is unread, under 7 cm; authoring it in aib (where the plate is
  made) would pin it;
- the base road and the terrain carry no authored offsets either: their default reach to the
  chassis was up to 0.43 m and 7.3 m, with no impulse. Harmless now, but contact generation paid
  for every step.

### The proof runs' predictions

- ***rough_none*, to the end** (one car, the probe of the first measurement): no plate contact
  with a tile at t 16.45 to 16.70 s, no chassis impulse, no 1.4 m/s step, no throw; the car at
  s 278 m or more at the run's end.
- **C6b's fixtures** (`fixture_drive --fixtures c6b` on fixture_c6b, raycast and sweep, judged by
  `rock_check` with the placement): every verdict as in issue 128's recheck (embedded_15 fails J
  in both queries, loose_15 passes in raycast and fails in sweep, loose_8 fails in both,
  boulder_35 passes in both: the car high-centres on it, stopping within 0.5 s of the plate
  reaching it), the placement as before, and 0 base contacts in both. The measures within 5 % of
  128's recheck (siw has moved since: issues 137 and 139), boulder_35's stop included.

### The fixtures' result (2026-11-24)

siw `issue-140` 56b8e39, aib 4e8d684, fixture_c6b, GPU0 quiet. (The *rough_none* run did not
start: its runner's variable was overwritten by Isaac's environment script, a known trap; it is
run again.)

| case | raycast (128's recheck) | sweep (128's recheck) |
|---|---|---|
| embedded_15 | J 303.1, fails (303.1, fails) | J 305.0, fails (305.0, fails) |
| loose_15 | moved 2.3 cm, **fails** (1.674 m, passes) | moved 0.288 m, **passes** (2.5 cm, fails) |
| loose_8 | 1.1 cm, fails (1.1 cm, fails) | 1.2 cm, fails (5.0 cm, fails) |
| boulder_35 | stops 0.35 s after the plate reaches it, passes (the same) | the same, passes (the same) |
| placement | as before | as before |

Base contacts: 0 in both. embedded_15's measures and boulder_35's stop equal 128's to the digit
printed (boulder's front axle at the stop within 2 cm).

- **118's prediction: failed for loose_15** (its verdict flipped in both queries) and for
  loose_8's sweep measure (1.2 cm against 5.0 cm, outside 5 %); held for the rest (boulder_35
  high-centres as before, 0 base contacts, embedded_15 to the digit). The rocks loaded and made
  also differ (embedded_15: at most 66 loaded and 44 prims, 80 and 48 in 128's).

loose_15 was already known to turn on its start (issue 122), and siw has moved since 128's
recheck (issues 137 and 139). Which change moved it is not yet known.

- **118's prediction for the attribution run** (the same fixtures on siw main 87591b4: issues
  137 and 139, without 140's offset): loose_15 and loose_8 as in 128's recheck (raycast passes
  at 1.674 m, sweep fails), so the flip is the tile offset's: a loose rock rests on the tiles,
  and its contacts with them changed. The rocks loaded as in this run (66 and 44 at
  embedded_15), since 139's queue changes when tiles arrive, not the offset.
