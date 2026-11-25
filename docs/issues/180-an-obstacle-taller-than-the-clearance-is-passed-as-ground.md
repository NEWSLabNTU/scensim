# 180: an obstacle taller than the ground clearance is passed as ground and stops the Isaac car

(a 15 cm rock under the plate; the geometry is correct)

**Status:** open; plan later, after 086 C6e3 (133, 2026-11-25). **Severity:** to be judged in
the plan: on Isaac, Autoware drives into anything between the car's ground clearance (0.138 m)
and its ground filter's threshold (0.20 m) that lies under the underbody, and the car stops dead
on it. **Found:** 2026-11-25, scensim 118, 086 C6e3 run b1 (numbered by 133).

**Correction first (118, 2026-11-25, before this was written down).** The first report to 133
gave the rock's top as 0.101 m, "under the 0.138 m clearance", and two hypotheses: the plate sits
lower than the clearance, or the rock's collider is larger than its render. The 0.101 m was the
rock's top in z with the base at the centreline (z 0). The road under the rock falls 0.0485 m
there with the crown, so the rock stands 0.150 m above the road under it, its nominal size. The
static check below refuted both hypotheses. The geometry is correct, and the strike is what a
15 cm rock under a 0.138 m plate does.

## What happens

086 C6e3, run b1: fixture_c6b at scensim main 0291abb3 (siw 4706ff9), Autoware's Model 3,
4.17 m/s. The first fixture is a static rock of 15 cm nominal (embed 0.1) at s 100 m, v 2.425
m, placed in the left wheel track of the lane's centre (y 1.62). The perception stack published
no object and no non-ground point at it: it was passed as ground, as C6e3 predicted (under the
0.20 m threshold). The car's truth trace then shows 4.17 m/s to 0.35 m/s in one 50 ms frame,
about 76 m/s^2, with the body 0.040 m up and pitched 1.3 deg. The origin (base_link) was at
x 97.32, where the plate's front edge (2.541 m ahead of it) meets the rock's near side. After
that the car crept at about 1 cm/s for 570 s and the scenario timed out (pose error p95 1.70 m
while stuck, NVTL p05 3.14). The contact is inferred from the truth trace, not measured: the
world server reports no chassis contacts (issue 176).

## The static check (no simulator; 133, 2026-11-25)

`isaac-ex/c6e/c6e3/static180.py`, output `static180.txt`. The plate comes from aib's `Vehicle`:
0.334 to 2.541 m ahead of base_link, |y| up to 0.6225 m, its bottom 0.138 m over base_link, with
the body resting on the road. Each rock's collider comes from siw's own placement (`rocks:place`,
the vertices the tile's merged static collider and a loose rock's own collider are made of). The
car is rolled with the crown (-1.15 deg). Two poses: the lane's centre (y 1.62), and b1's own at
the strike (y 1.885).

| s | rock | top above the road under it | at the lane's centre | at y 1.885 (b1) |
|---|---|---|---|---|
| 100 m | 15 cm static, embed 0.1 | 0.150 m | the left tyre | under the plate, overlap 13.6 mm: a strike |
| 200 m | 15 cm loose | 0.150 m | the left tyre | under the plate, overlap 13.6 mm: a strike |
| 300 m | 8 cm loose | 0.080 m | the left tyre | the plate's edge and the tyre, clear by 58.8 mm |
| 400 m | 35 cm static, embed 0.2 | 0.350 m | under the plate, overlap 218 mm | under the plate, overlap 218 mm |

## A contributing factor, not the cause

Autoware drove 0.265 m left of the lane's centre at the rock (y 1.885). In a1 it was 0.08 m left
at the pothole (y 1.70). Placed for the lane's centre, the 15 cm rocks meet the left tyre, which
climbs them; 0.265 m to the left puts them under the plate. The cause is the stack's: the ground
filter's 0.20 m threshold passes, as ground, an obstacle taller than the car's clearance.

## The options (for a plan after C6e3, not now)

- The profile's ground threshold set against the car's clearance (Autoware's
  `non_ground_height_threshold` and `split_height_distance`, 0.20 m in 1.5.0's defaults).
- Accept it and document it: a car that passes 0.14 to 0.20 m obstacles as ground strikes them.

066 R7's "rocks passed as ground" is realised here: see 066's R7.
