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

## Step 2: the cost of seeing it, plan and predictions (241, 2026-11-27, before the run)

133's choice: one run on 118's GPU0 after 243's R1 to R3, of a variant that ends by itself.
`fixture_c6b_r180.xosc` is c1's scenario with three changes: the start is x 60, success is
reaching x 112 within 2 m, and the time-out is 60 s. The goal stays at x 490, so the speed at
the rock is c1's. The run records c1's topics plus `/sensing/lidar/concatenated/pointcloud`
(the ground filter's input) and NDT's pose. It is staged for 118 on the NAS in
`home/2026-11-27 issue 180 step 2 run (241)/`, with SHA256SUMS. Expected size is 1 to 2 GB.

The replay, on the CPU:

- the ground filter by Autoware's own `ScanGroundFilterComponent` (and the crop box before
  it), fed the recorded cloud through `ros2 bag play`, once per setting;
- the 0.1 m downsampling, the compare-map filter and the clustering by 181's replay
  (replay181g.py), with the car placed by the truth pose. That replay was checked against the
  record's own stages in 181.

The settings:

- the ground threshold g (`non_ground_height_threshold` and `split_height_distance` together):
  0.20 (as run), 0.15, 0.12, 0.10, 0.08 and 0.05 m;
- the compare-map dz: 0.3 (as run), 0.2, 0.1 and 0.05 m;
- `min_cluster_size`: 10 (as run), 5 and 3.

Measured per setting, from 30 m ahead to the strike:

- the rock: its points after each stage, and the first range at which a cluster forms on it;
- false obstacles on the carriageway: the fraction of frames with a cluster within the lane
  (|y - 1.62| < 1.75 m) and more than 1 m from the rock;
- off the carriageway: clusters on the shoulder, where the loose rocks are (0.07 to 0.10 m,
  y about +-4.7 m), counted apart, since they are real.

Predictions:

1. Fidelity: at the as-run setting, the replayed ground filter's output matches the record's
   `/perception/obstacle_segmentation/pointcloud`. The per-frame median fraction of the
   record's points within 0.05 m of a replayed point is at least 0.98.
2. As run (0.20, 0.3, 10): 0 to 2 rock points per frame after the ground filter, none after the
   compare-map filter, no cluster. Step 1 again, on the new run.
3. g 0.10 with dz 0.3: the ground filter keeps at least 3 rock points in most frames within
   20 m. The compare-map filter drops them all: no cluster at the rock.
4. g 0.10 with dz 0.1 and `min_cluster_size` 10: still no cluster at the rock beyond 3 m. Only
   the top 5 cm of the rock is more than 0.10 m above the road, and it gives fewer than ten 0.1
   m voxels. With `min_cluster_size` 3, a cluster forms from about 10 m.
5. False obstacles at g 0.10, dz 0.1, `min_cluster_size` 3: a cluster on the carriageway in
   under 5 % of frames.
6. At g 0.05 with dz 0.05: the rock clusters at `min_cluster_size` 10 from about 8 m. The road
   gives a cluster on the carriageway in more than 20 % of frames. The map's road band is 0.11
   m thick here (step 1), and the crown tilts the road 1.15 deg across the lane.
7. The shoulder's loose rocks become clusters from g 0.08.

What this decides: whether some setting makes the 15 cm rock an object soon enough to stop.
Stopping from 4.17 m/s at the MRM's -6 m/s^2 takes 1.4 m, plus the stop margin, so the cluster
has to form by about 7 m from the bumper. The setting must also keep false obstacles on the
carriageway rare. If none does (predictions 4 to 6 say so), the options are the issue's second
one (accept and document it), or a check made for the purpose: a height-above-map test on the
lane only, not a global threshold.

### Step 2 amended: judged at the final objects, with the validator in the grid (133, before the run)

133's correction: in 181 the validator decided, not the clustering. So each setting is judged
at the final objects, and the validator's UNKNOWN threshold joins the grid, as
`min_points_num` = `max_points_num`: 5 (the profile's since asv b269c4a) and 3. With
`use_pointcloud_map` true, the validator counts the compare-map filter's output inside each
object's hull (detection.launch.xml in tier4_perception_launch 1.5.0). So it sees the same
thinned points the clustering did, not the ground filter's. The tracker's confirmation then
delays the final object. In 181 the final objects came 1.3 m (run A) and 3.4 m (run B) after
the first validated object. The replay stops at the validator, so a final object's range is
the validated range less that lag, 1.3 to 3.4 m.

The bar, in the bumper's distance to the rock's near side (base_link range less 3.716 m and
the rock's 0.18 m radius):

- an emergency stop: AEB through the MRM at -6 m/s^2 from 4.17 m/s needs 1.45 m, plus about
  0.3 s of reaction (1.25 m). A final object later than 3 m means a strike at any setting.
- a planned stop: obstacle_stop's minimum margin of 3 m plus its braking. The final object has
  to come by about 7 m, as step 2 said.

Predictions (4) to (6), replaced; (1) to (3) and (7) stand:

4. g 0.10 with dz 0.1. Only the top 5 cm of the rock is more than 0.10 m above the road, so few
   points pass:
   - with `min_cluster_size` 10 there is no cluster beyond 3 m, so no validated or final object
     before the strike, whatever the validator's threshold;
   - with `min_cluster_size` 3 a cluster forms from about 10 m. With the validator at 5 it is
     validated from about 6 m; at 3, from about 9 m;
   - final objects (less the tracker's 1.3 to 3.4 m): 3 to 5 m with the validator at 5, and 5 to
     8 m at 3, from the bumper. That is at the emergency bar, and short of the planned one
     except at its best.
5. At that setting (g 0.10, dz 0.1, `min_cluster_size` 3, validator 3), a final object on the
   carriageway more than 1 m from the rock in under 2 % of frames. The tracker needs repeated
   detections, so single-frame road clusters seldom survive it.
6. g 0.05 with dz 0.05, `min_cluster_size` 10, validator 5: the rock's final object comes by
   about 5 m from the bumper. Final objects on the carriageway away from the rock are in more
   than 10 % of frames.

Judged per setting: the first final-object range at the rock (as the validated range less 1.3
and less 3.4 m, both given), and the fraction of frames with a would-be final object elsewhere
on the carriageway. A would-be final object is a validated object present in at least 3
consecutive frames, which approximates the tracker. The replay cannot run the tracker itself.
