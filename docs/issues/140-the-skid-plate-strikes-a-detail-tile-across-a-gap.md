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
  the pothole's far wall in the tile's 5 cm mesh;
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
