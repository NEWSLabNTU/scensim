# 180: an obstacle taller than the ground clearance is passed as ground and stops the Isaac car

(a 15 cm rock under the plate; the geometry is correct)

**Status:** open; plan later, after 086 C6e3 (133, 2026-11-25). **Severity:** to be judged in
the plan: on Isaac, Autoware drives into anything between the car's ground clearance (0.138 m)
and its ground filter's threshold (0.20 m) that lies under the underbody, and the car stops dead
on it. **Found:** 2026-11-25, scensim 118, 086 C6e3 run b1; confirmed on the repeat, b2 (numbered by 133).

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

## The repeat (b2, the same day)

Run b2, built the same way, struck the same rock at the same place. The origin was at x 97.29,
with the rock 0.27 m left of the car's centre, under the plate. The truth trace shows 4.17 m/s to
3.26 m/s in one 50 ms frame, then further hits over the next metre down to about 2.3 m/s, with the
body bouncing (up to 0.027 m above its height before the rock, roll swinging between +0.4 and -1.8 deg). It scraped over and drove on,
and again no object or non-ground point was published at the rock. Two strikes in two runs: b1
stopped dead, b2 got over by striking. Again inferred, not measured.

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

## The plan: which stage calls the rock ground (241, 2026-11-27; predictions before any reading)

Asked by 133: find, from a record and on the CPU only, the stage that passes the 15 cm rock as
ground. The record is issue 177's live check, run c1 (118, 2026-11-27: fixture_c6b_down from x
20 at scensim 7716891b, siw e763170; NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 177
live check and 181 182 run A (118)/runs/c1-2026-11-27T03-24-46_fixture_c6b_down_r0`). It met
the same 15 cm static rock (s 100 m) and struck the plate with the origin at x 97.3. Its
record has no raw lidar, but it has each stage's output at about 10 Hz:

| stage | topic in the record |
|---|---|
| ground filter (ScanGroundFilter, elevation grid) | `/perception/obstacle_segmentation/pointcloud` |
| compare-map filter (after 0.1 m downsampling) | `.../detection/pointcloud_map_filtered/pointcloud` |
| clustering | `.../detection/clustering/clusters` |
| validator | `.../detection/clustering/validation/objects` |
| final objects | `/perception/object_recognition/objects` |

Three stages can each pass a 15 cm rock as ground, on paper:

- the ground filter: `non_ground_height_threshold` and `split_height_distance` are 0.20 m in
  autoware_launch 1.5.0's `ground_segmentation.param.yaml`, which the profile uses unchanged;
- the compare-map filter: issue 181 step 3 found that a point is dropped when a map point lies
  in its own or one of the 26 neighbouring voxels (0.5 x 0.5 x 0.3 m) within |dz| < 0.3 m. The
  road under the rock is in the map, so a point 0.15 m above it is dropped, whether or not the
  rock itself is in the map;
- clustering and the validator: `min_cluster_size` 10 points, and the validator's
  clamp(round(800/d), 5, 5) for UNKNOWN since asv b269c4a (issue 181).

Step 1 reads each stage in turn. It places the rock by siw's own placement, as gt181.py does
for 181's boulder, and the car by the truth's pose (ego.csv). For each frame from 40 m out to
the strike, it counts points inside the rock's footprint plus 0.1 m, more than 0.05 m above the
road under it, in each cloud; clusters and objects whose hull reaches the rock. It also counts
the map PCD's points over the rock's footprint more than 0.05 m above the road.

Predictions, before any of it is read:

1. The ground filter's output has no point on the rock in at least 90 % of the frames within
   30 m, and at most 2 in any frame. The rock is gone at the first stage.
2. So the compare-map, cluster and validator stages see nothing there either: no cluster and no
   object at the rock in any frame.
3. The map PCD has no point of the rock: the map is the road and its props, not the rocks.
4. The second stage is analytic, not read: even with the ground filter at 0.10 m, the
   compare-map filter would still drop the rock's points (|dz| 0.15 < 0.3 m). So a fix of the
   ground threshold alone would not make an object. Step 2 checks that on the record's map,
   by passing step 1's rock points (or, if prediction 1 holds, points placed on the rock's
   collider as the lidar's rings would hit it) through 181's compare-map replay.
5. Lidar geometry does not hide the rock: the OS1 at x 0.9, z 2.0, tilted down 22.5 deg, sees a
   point 0.15 m high to within about 1.9 m of itself, inside the bumper. Under 15 m, each
   frame's rings put at least 3 returns on the rock's top or face.

If prediction 1 fails (the ground filter keeps rock points), the stage that drops them is the
first one whose output loses them, and step 2 replays that one.

Step 2, the fix's cost, before any change: rerun step 1's counting against the ground filter's
own output in the stretches of c1 with no rock (crown, potholes, curbs), to count how many
points a lower `non_ground_height_threshold` and a smaller compare-map dz would let through
there. That is the false-obstacle cost of any fix; it needs the raw cloud for the ground
filter, so that part is a request to 118 for one run recording the concatenated cloud, sent
through 133. No change is made before 133 has the plan and the step 1 result.

## Step 1's result: the ground filter drops it, and the compare-map filter would too (241, 2026-11-27)

The rock, by siw's own placement at e763170 (the c1 map's road_detail.yaml; no change to
`rocks` since): x 100.00, y 2.42, plan radius 0.182 m, its top 0.150 m above the road under it.
Over c1's 203 frames from 39.8 m out (truth base_link to the rock) to the strike, inside the
rock's plan radius plus 0.1 m:

| stage | frames with a point more than 0.05 m above base_link |
|---|---|
| ground filter's output (non-ground) | 1 of 203: one point, z 0.14 m, at 21.7 m |
| after the 0.1 m downsampling | the same 1 |
| compare-map filter's output | 0 |
| clusters | 0 |
| validated objects within 1 m | 0 |
| final objects within 1 m | 0 |

Against the predictions:

1. Held. One point in one frame (at most 2 was predicted); none in 202 of 203.
2. Held. No cluster, validated object or final object at the rock in any frame.
3. Held. The map has 6 points over the footprint, the same as two rock-free spots on the same
   wheel track (x 60 and x 140). One of them is 0.083 m above the local plane, and both
   rock-free spots have two such points. The map's road band itself spans about 0.11 m in z
   (residual sd 0.05 m around the plane), so the rock is not in it.
4. Held on its one sample. The single point the ground filter kept, 0.14 m high, passed the
   downsampling and was dropped by the compare-map filter, as the |dz| < 0.3 m rule says. One
   point is a thin test; step 2 tests it properly.
5. Not checkable from this record: it has no raw cloud, so how many returns the rock gave
   the ground filter is unknown. One correction to the geometry: the rig is the OS1 REV7 128
   channel, FOV +15 to -25 deg (aib's tesla_model3.rig.yaml), so with the 22.5 deg tilt
   the lowest ring is 47.5 deg down. A point 0.15 m high is visible to within 1.7 m of the
   lidar, not 1.9 m, and still inside the bumper.

So the first stage that calls the rock ground is the ground filter (0.20 m threshold), and the
compare-map filter behind it would drop what a lower threshold let through. A fix needs both,
and its cost is false obstacles from the road's own relief: the map's road band is 0.11 m
thick here.

Step 2 needs the raw cloud. fixture_c6b_r181 (the 2c runs) starts at x 320 and meets no 15 cm
rock, so it cannot carry it. One c1 run recording the concatenated cloud is needed. The OS1 at
128 x 1024 and 20 Hz is about 131,000 points a scan. At 16 to 32 bytes a point that is 40 to
85 MB/s, and c1 ran to its 604 s time-out: 25 to 50 GB. So record only the window around the
rock (x 60 to 110, about 12 s at 4.17 m/s, under 1 GB), not the whole run.
