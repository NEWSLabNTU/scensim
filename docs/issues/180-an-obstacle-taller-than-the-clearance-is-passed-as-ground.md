# 180: an obstacle taller than the ground clearance is passed as ground and stops the Isaac car

(a 15 cm rock under the plate; the geometry is correct)

**Status:** open, for option 3 (a lane-only height-above-map check), after the map's low road layer is fixed (its own issue). Option 1 was taken on 2026-11-27 (the user, through 133): the limit is documented in `docs/reference/limits.md`. Before that: plan later, after 086 C6e3 (133, 2026-11-25). **Severity:** to be judged in
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

### A correction to step 1: another filter sits between the ground filter and the record (241, before the run)

Step 1 read `/perception/obstacle_segmentation/pointcloud` as the ground filter's output. It is
not. The profile runs the time-series outlier filter (`use_obstacle_segmentation_time_series_filter`
true in its tier4_perception_component.launch.xml, as autoware_launch 1.5.0 does). So the ground
filter publishes `/perception/obstacle_segmentation/single_frame/pointcloud`, and the occupancy
grid outlier filter turns that into the recorded topic. That filter keeps a point whose
occupancy-grid cell costs at least 45. Otherwise, with `use_radius_search_2d_filter`, it keeps a
point only when at least clamp(400/d, 4, 70) other points lie within 1 m of it. At 21.7 m that
is 18 neighbours, which a 15 cm rock does not have.

So step 1 found that the rock is dropped at the first recorded stage, which is the ground filter
and the outlier filter together. It did not find which of the two drops it. Its conclusion is
amended. Predictions 1 to 3 held for "the ground filter and the outlier filter", and prediction 4
(the compare-map filter drops the one kept point) stands.

For step 2, the run now also records:
- the ground filter's own output, `/perception/obstacle_segmentation/single_frame/pointcloud`;
- the occupancy grid (`/perception/occupancy_grid_map/map`), the outlier filter's other input;
- `/tf` and `/tf_static`, for the outlier filter's map frame.

They are added to the NAS staging's topics.txt and README, and its SHA256SUMS is rewritten. The
grid gains the outlier filter on and off. Its stages are then the ground filter, the outlier
filter, the compare-map filter, the clustering and the validator.

One more prediction, before the run:

8. The ground filter's own output has at least one rock point in at least 30 % of the frames
   within 25 m. Its local-slope test (13 deg) catches the rock's sides even though the top is
   under 0.20 m. The outlier filter removes at least 80 % of those points. So of the two, the
   outlier filter does most of the dropping. If this holds, the grid's "outlier filter off"
   column matters as much as the thresholds.

## Step 2's result: no setting of Autoware's chain makes the rock an object (241, 2026-11-27)

**The run.** 118 ran `fixture_c6b_r180` once, at main bbaba522 (siw 542cfae), with the staged
topics. NAS: `autoveh/logs/2026 SSv2 on CARLA/2026-11-27 issue 180 step 2 run (118)`.
- It PASSED: reached x 112 at 23 s, with no contact.
- The car passed the rock with its centre at y 1.21 to 1.26, so the rock (y 2.425) was 1.2 m to
  its left and was not struck. The perception question does not depend on that.

**The replay.**
- Autoware 1.5.0's own CropBox, ScanGroundFilter and occupancy-grid outlier filter ran in a
  component container, fed the recorded raw cloud at 0.1x through `ros2 bag play`.
- 181's replay ran the rest: the downsampling, the compare-map filter by the EKF's pose, the
  clustering and the validator.
- At first the replay lost 20 to 26 % of its frames between the player and the crop box: 4 MB
  clouds on Cyclone's default socket buffers. A scratch Cyclone profile with 64 MB receive
  buffers lost none: 455 of 455 ground-filter frames, 340 of 340 after the outlier filter.
- The scripts are on the NAS: `home/2026-11-27 issue 180 step 2 run (241)/replay/`.

**The raw cloud sees the rock.** Placed by the truth's pose, it has points more than 0.05 m above
the road in 109 of 144 frames from 30 m to the strike. That is up to 34 points a frame (at 5.9 m),
and the highest at 0.148 m, the rock's top.

**Each stage at the rock** (frames within 30 m of the bumper with at least one rock point more
than 0.05 m high; the grid of 12 ground replays x 4 dz x 3 `min_cluster_size` x 2 validator, 288
settings):

| ground threshold g | the ground filter's own output | after the outlier filter (on) | outlier off, then compare-map dz 0.3 / 0.2 / 0.1 / 0.05 | validated / would-be final (any dz, mcs, V) |
|---|---|---|---|---|
| 0.20 (as run) | 0 of 163 | 0 | 0 / 0 / 0 / 0 | never / never |
| 0.15 | 0 | 0 | 0 / 0 / 0 / 0 | never / never |
| 0.12 | 7, at most 2 points | 0 | 0 / 1 / 7 / 7 (at most 1) | never / never |
| 0.10 | 38, at most 15 | 0 | 0 / 1 / 37 / 38 (at most 5 to 6) | never / never |
| 0.08 | 60, at most 20 | 0 | 0 / 1 / 53 / 60 (at most 5 to 7) | never / never |
| 0.05 | 66, at most 27 | 0 | 0 / 1 / 53 / 66 (at most 5 to 9) | once, at 1.5 m (dz 0.05, mcs 5, V 3) / never |

- **The ground filter** drops the rock at 0.15 m and above.
- **The outlier filter** drops every rock point the ground filter keeps, at every threshold. A
  15 cm rock never has the clamp(400/d, 4, 70) neighbours within 1 m, and its cell's occupancy
  never reaches 45.
- **The compare-map filter** drops what is left at dz 0.2 and above.
- **The validator.** Even with both filters opened up, at most 5 to 9 rock points reach the
  clustering. The validator keeps an object only with more than V points strictly inside its
  hull, and for so few points nearly all are the hull's own vertices. So the rock is validated
  once, at 1.5 m, in one setting of 288, and never becomes a would-be final object.
- **False objects on the carriageway** (|y - 1.62| < 1.75, more than 1 m from the rock, in 3
  consecutive frames): 0 in all 288 settings.
- **Off the carriageway.** At g 0.12 and below with dz 0.1 and below, the shoulder's real loose
  rocks (7 to 10 cm) become persistent objects in up to 161 of 163 frames.

**A third option, outside Autoware's chain: a lane-only height-above-map check**
(`hmap180.py`).
- The rule: a raw point is an obstacle when it is on the carriageway, 1 to 30 m ahead, and more
  than h above the highest map point within 0.5 m of it.
- Points are placed by the EKF's pose, as a node in the stack would place them. Detections are
  0.3 m cells with at least N points, and a would-be object is one in 3 consecutive frames.

| h | N | rock first detected (bumper) | first would-be object (bumper) | false would-be objects on the carriageway |
|---|---|---|---|---|
| 0.05 | 3 | 14.7 m | 11.3 m | 92 % of frames |
| 0.08 | 3 | 12.2 m | 9.1 m | 85 % |
| 0.10 | 3 | 9.3 m | 8.8 m | 72 % |
| 0.10 | 10 | 4.0 m | 3.6 m | 36 % |
| **0.12** | **3** | **9.1 m** | **6.1 m** | **0 %** |
| 0.12 | 5 | 4.3 m | 3.8 m | 0 % |

The false objects at h 0.10 and below are a **map defect**, not the method's. At the spots that
make them (x 77.5, 90.7 and 104.4 on the lane), the raw road is flat. But within 0.5 m there the
map holds only points 0.10 to 0.13 m below the real road (z -0.160 against the road's -0.024
to -0.059). Elsewhere it also has a layer near the true height: step 1 found the map's road band
0.11 m thick. The EKF's height error is small and steady here (2.3 cm low, pitch and roll under
0.0005 rad), so it is not the cause. On a map whose road is where the road is, h 0.08 would
likely be clean. That is not measured.

**Against the predictions.**
1. The fidelity check held: 1.0000 at the median, p5 and minimum, on both stages and every frame.
2. As run held: 0 rock points, no cluster.
3. g 0.10 with dz 0.3: "at least 3 rock points in most frames within 20 m" FAILED, 8 of 96.
   "Compare-map drops them all" held.
4. FAILED. With mcs 3, no cluster is ever validated at 6 or 9 m, and no final object comes at
   3 to 8 m. The validator's strictly-inside count, not the clustering, stops a 15 cm rock.
   "No cluster beyond 3 m with mcs 10" held.
5. Held: false objects on the carriageway 0 % (bar 2 %).
6. FAILED both ways. The rock is never a final object at 0.05/0.05, and the carriageway is
   clean (0 %, not over 10 %).
7. FAILED. The shoulder rocks become objects from g 0.12 with dz 0.05, and broadly from 0.10,
   not from 0.08.
8. FAILED in its first half: at g 0.20 the ground filter keeps no rock point, so it alone
   drops the rock as run. Its second half held: the outlier filter removes 100 % of what lower
   thresholds keep.

## The options for the user (241, 2026-11-27)

The bars: a would-be object by 3 m from the bumper for an emergency stop (AEB at -6 m/s^2 from
4.17 m/s), and by 7 m for a planned one.

| option | the 15 cm rock | false objects | what it takes |
|---|---|---|---|
| 1. No change; document the limit | never an object; a car that meets one under the plate strikes it (b1 stopped dead, b2 and c1 scraped over) | none new | a note in the profile's docs: obstacles 0.14 to 0.20 m tall (here up to 0.15) under the car are not seen |
| 2. Autoware's ground filter, outlier filter, compare-map, clustering and validator settings | never a final object in 288 settings; validated once, at 1.5 m | none on the carriageway; the shoulder's 7 to 10 cm loose rocks become persistent objects from g 0.12 / dz 0.1 down | profile parameters only, but it does not reach the rock, so not recommended |
| 3. A lane-only height-above-map check, at h 0.12, N 3 | would-be object at 6.1 m (detected 9.1 m): meets the emergency bar, just short of the planned one | 0 % on the carriageway in this run | a new node in the profile (raw cloud, the map, the EKF pose, the lanelet map), with tests; one live run to confirm |
| 3b. Option 3 after the map's low road layer is fixed | likely earlier (h 0.08 detected it at 12.2 m), not measured on a fixed map | the 85 % at h 0.08 here is the map's; on a fixed map, to be measured | the map rebuilt or cleaned first (its own issue), then option 3 |

My recommendation:
- Option 1 now, since it is the true state of the stack.
- Option 3 as a planned change, with the map defect filed first. h 0.12 sits 3 cm under the
  rock's height and leaves no margin for a 12 cm rock.
- Option 2 does not reach the goal at any setting.

## The decision (the user, through 133, 2026-11-27)

- **Option 1 now.** The limit is documented for users in `docs/reference/limits.md` (Pilots and
  autopilots): obstacles under about 0.20 m are taken for ground, even when taller than the
  car's clearance, and the three stages that each drop them are named.
- **Option 3 later.** It comes after the map's low road layer is fixed. Its plan (the node's
  interface, its tests, one live run and the predictions) goes to 133 before any code.
- **Option 2 is not taken.** No setting reaches the rock.

This issue stays open for option 3.

## Option 3's plan: a lane-only height-above-map check (241, 2026-11-27, before any code)

Issue 198 has landed (scensim 3a35369f, siw 9bfd1b1), so the map's road is where the road is.
On the rebuilt fixture_c6b, `hmap180.py` on r180's record gave the rock as a would-be object at
11.3 m (h 0.05, N 3), 8.8 m (h 0.10, N 3) and 6.1 m (h 0.12, N 3), with no false object on the
carriageway at any of them (issue 198, "Issue 180's lane check against the rebuilt c6b").

**The rule.** The node uses the sensors and the map only, never the truth:
- the raw cloud, `/sensing/lidar/concatenated/pointcloud`;
- the EKF's pose, `/localization/kinematic_state`, to place the cloud in the map;
- the point cloud map, whole (`/map/pointcloud_map`) or by tiles through the map loader's
  differential service, as compare-map takes it, so a divided map (Haruna, Tsukuba) works;
- the lanelet map, `/map/vector_map`: the carriageway is the union of the road lanelets'
  polygons, not a fixture's hard-coded band.

A point is an obstacle point when it is inside a road lanelet, 1 to 30 m ahead of base_link,
outside the ego's own box, and more than h above the highest map point within 0.5 m of it.
Obstacle points are binned in 0.3 m map cells. A detection is a group of touching cells holding
at least N points, and it is published once present in 3 consecutive frames. These are
`hmap180.py`'s rules, unchanged, except that the lanelets replace the band.

**The interface.**
- A Python node in `autoware_sim_profile`, `lane_height_check` (as `clock_guard` is), started
  by the profile when `lane_height_check:=true`. The default is false until the live run below
  has passed, then true by a separate, asked-for change.
- Its output is a `PointCloud2` of the persistent detections' points,
  `/perception/obstacle_segmentation/lane_height_check/pointcloud`, plus a small status topic:
  frame time, points in and kept, detections, and the processing time.
- How the planner stops for it. The motion velocity planner has one pointcloud input
  (`planning_input_pointcloud_topic_name`, today `/perception/obstacle_segmentation/pointcloud`).
  obstacle_stop's pointcloud type is off in 1.5.0's parameters (`check_inside.pointcloud:
  false`), so today no module stops for a bare point. The candidate:
  - concatenate the two clouds into the planner's input, and turn on obstacle_stop's
    pointcloud check (`check_inside.pointcloud: true`), with pointcloud_deceleration as for
    unknown objects;
  - the risk is that this also makes obstacle_stop stop for any non-ground point of the
    ordinary cloud in the path. Step A measures that before anything is chosen. If it is not
    clean, the fallback is to publish the detections as UNKNOWN `DetectedObjects` into the
    object merger, which costs the tracker's confirmation lag (1.3 to 3.4 m, issue 181).
- Step 0 names, from a live stack's `ros2 node info`, every module reading the planner's
  pointcloud input, before step A.

**The threshold (for 133 to choose).**
- **h 0.10, N 3 (my recommendation).** It makes a would-be object at 8.8 m, past the 7 m
  planned-stop bar. It ignores what the car can drive over: c6b's 8 cm loose rock at s 300
  sits under the tyre and clears the plate by 58.8 mm (133's static check). Anything taller
  than 0.10 m is within 4 cm of the 0.138 m clearance.
- **h 0.05, N 3.** It makes the object at 11.3 m, but would also stop the car for every 5 to
  10 cm rock or debris on the lane. c6b's 8 cm rock would then stop it.
- h is measured from the map's road, so the EKF's height error adds to it: 2.3 cm low and
  steady in r180's record. It is checked again in step A.

**Tests (before the live run).**
- Unit tests, in the profile's test suite, on synthetic data with no ROS:
  - the lanelet mask, including a curve and a junction;
  - the height above the map, against a flat map and a map with a 10 % grade and a crown;
  - cell grouping, and the N and 3-frame persistence;
  - a box rejecting the ego's own points;
  - the divided map's tile lookup.
- A node test with rclpy: a synthetic map, lanelets and cloud published, and a detection
  checked on the output topic within 3 frames.
- Step A, before any code: a replay (no simulator) of 180 step 2's run (118, NAS) against the
  rebuilt fixture_c6b map, by `hmap180.py` with the lanelet mask in place of the band. It
  checks the rock's range and the carriageway's false detections with the lanelets. For the
  interface, it also counts the ordinary obstacle_segmentation cloud's points inside the
  recorded trajectory's footprint (lateral margin 0.3 m), frame by frame. That is what turning
  on obstacle_stop's pointcloud check would stop for.
- After the code: the same record replayed through the node itself, for its ranges and its
  processing time per frame on 241.

**One live run (step B).** fixture_c6b on Isaac at the profile's default speed (4.17 m/s), on
the rebuilt map, with the rock at s 100 m moved to the lane's centre line so the car's path
meets it under the plate. `lane_height_check:=true` and the chosen interface. Recorded: the
node's output and status, the planner's stop reason, the truth trace, and contacts by the
truth's height and speed (issue 176: no chassis contacts reported). Run on scensim main with
the node, gated first.

**Predictions (at h 0.10, N 3; if 133 picks h 0.05 they move as noted).**
- P1 (step A, then the node's replay): with the lanelet mask, and then through the node, the
  ranges are `hmap180.py`'s on r180's record within 0.5 m. The would-be
  object comes at 8.8 m (11.3 m at h 0.05), with no false would-be object on the carriageway.
- P2 (the node's replay): processing time p95 under 30 ms a frame on 241. The node keeps up at 10 Hz
  with no dropped frame in 1000.
- P3 (step A): the ordinary obstacle_segmentation cloud has no point in the trajectory's
  footprint for 3 consecutive frames anywhere on r180's record. If it does, the
  DetectedObjects fallback is used and P5's ranges shorten by the tracker's lag.
- P4 (unit and node tests): all pass. The synthetic 15 cm box is detected and an 8 cm box is
  not, at h 0.10 (both at h 0.05).
- P5 (step B): the car stops short of the rock with no strike, its bumper 1.5 to 5 m before
  the rock's near side (2.5 to 6.5 m at h 0.05), and peak deceleration within the planner's
  limit (2.5 m/s^2).
- P6 (step B): no stop for anything else over the fixture's 600 m. At h 0.10 that includes
  the 8 cm loose rock at s 300 and the pothole. At h 0.05, the 8 cm rock stops the car.
- P7 (step B): no would-be object is ever made from the truth. That is checked by code
  review: the node subscribes to none of the world server's topics.

**Order.** Step 0 (a live stack's node info) and step A (a replay, no simulator) come first.
133 then chooses the interface from P3, and the threshold. Then the code with its tests, the
gate, and step B.

## Steps 0 and A: what reads the planner's cloud, and what each interface would stop for (241, 2026-11-27)

**Step 0, from the launches and parameters.** No live stack was up on 241, so this was read
from Autoware 1.5.0's installed launches and the profile's preset, not from `ros2 node info`.
The planner's pointcloud input (`planning_input_pointcloud_topic_name`) is read by:
- motion_velocity_planner (`~/input/no_ground_pointcloud`). obstacle_stop's and obstacle_slow_down's
  pointcloud types are off (`check_inside.pointcloud: false`, `pointcloud: false`).
  obstacle_velocity_limiter is `static_only`, and obstacle_cruise takes objects only. So on
  the lanes today no module acts on a bare point.
- behavior_velocity_planner (`~/input/no_ground_pointcloud`). Its detection_area module reads
  points only inside a map's detection areas, and the courses have none.
- surround_obstacle_checker, which the sim preset turns off.
- the parking scenario's costmap (`points_no_ground`), on a parking goal only.

**Step A** (`stepA180.py`, NAS `home/2026-11-27 issue 180 option 3 step A (241)/`). It replays
records against the rebuilt fixture_c6b map, with no node code and no simulator. The truth is
used only to report the rock's range.

- The lane check with the lanelet mask, over the whole r180 record (455 frames), N 3. r180 is
  the only record holding the raw cloud:

  | h | rock detected (bumper) | would-be object | false would-be objects on the lanelets |
  |---|---|---|---|
  | 0.05 | 14.7 m | 11.3 m | 0 of 455 frames |
  | 0.08 | 12.2 m | 9.1 m | 0 |
  | 0.10 | 9.3 m | 8.8 m | 0 |
  | 0.12 | 9.1 m | 6.1 m | 0 |

  The ranges equal `hmap180.py`'s with the band (P1 held for step A).
- The ordinary cloud in the trajectory's footprint (half width 0.9475 + 0.3 m, 30 m ahead; see
  the correction below):
  what obstacle_stop would stop for if its pointcloud type were on with today's input. Ten c6b
  records: r180, the 181/182 runs A, B, A1 to A3 and B1 to B3, and c1.
  - Nearly every in-footprint frame is the 35 cm boulder at s 400, while the car stands before
    it: a real obstacle.
  - Away from the fixture's rocks and boulder (more than 2 m), 9 records have none.
  - Run B has 52 frames, 41 of them as 3 consecutive frames. There are 1 to 5 points a frame,
    at the map's road height (within 0.05 m, a few to 0.15 m below it), 20 to 23 m ahead at x
    352 to 375. Meanwhile the ego drifted left from y 1.61 to 2.57. These are road points the
    ground filter passed as non-ground, and obstacle_stop's 0.3 s rule would have stopped for
    them.
  - So P3 FAILED: the ordinary cloud is not clean in the footprint.

**The choices for the user** (bars: a would-be object by 7 m from the bumper for a planned
stop, by 3 m for an emergency one).

| interface | what the planner stops for | false stops in step A | the rock's object (at h 0.10) | what it takes |
|---|---|---|---|---|
| I1. The lane check's cloud joined to the ordinary cloud; obstacle_stop's pointcloud type on | any point of either cloud in the footprint | run B: 41 episodes of 3 frames, from road points the ground filter passed (1 record of 10) | 8.8 m | parameters and a concatenation; not clean |
| **I2. The lane check's cloud alone into motion_velocity_planner; obstacle_stop's pointcloud type on** | only the lane check's detections; every other reader keeps the ordinary cloud | the lane check's own: 0 in r180's 455 frames | 8.8 m | the profile carries its own motion-planning launch, so that only motion_velocity_planner's input is remapped |
| I3. The lane check's detections as UNKNOWN DetectedObjects into the object merger | the tracked object | the lane check's own: 0 | about 5.4 to 7.5 m, after the tracker's 1.3 to 3.4 m lag | the merger's input; nothing in planning changes |

| threshold | rule | for the Model 3 (clearance 0.138 m) | the car stops for | it does not stop for |
|---|---|---|---|---|
| **h = clearance - 0.04 m, at least 0.05 m** | the margin covers the EKF's height error (2.3 cm in r180) and the map road's spread | 0.098 m, so 0.10 | what could strike the plate: c6b's 15 cm rocks and its 35 cm boulder (the boulder is already an object today) | c6b's 8 cm loose rock, which the tyre climbs and the plate clears by 58.8 mm |
| h = 0.05 m for every car | the noise floor only | 0.05 m | also the 8 cm rock, and anything over 5 cm on a lane | nothing over 5 cm |

- For a car with low clearance (the MuSHR nano's 0.03 m), the first rule gives the 0.05 m floor.
- The 8 cm rock's row comes from its height. No record holds the raw cloud past x 112, so it
  was not measured.

My recommendation: I2, with h = clearance - 0.04 m (at least 0.05 m).
- I2 is the only interface that is clean in step A and keeps the 8.8 m range.
- I1 stops for the ground filter's leaks.
- I3 loses 1.3 to 3.4 m to the tracker.

## The decision, and I2's code (241, 2026-11-27)

**The decision (the user, through 133).** I2, with h = clearance - 0.04 m (at least 0.05 m),
read from the vehicle spec. Code it test-first, then step B's live run, with predictions
updated for I2 and committed first.

**A correction to step A.** The footprint used half width 0.9475 m, which is the drift
Mustang's. The Model 3's vehicle_info width is 2.163 m, so the half width is 1.0815 m. Rerun at
1.0815:
- 9 records are still clean away from the fixture's obstacles.
- Run B has 57 frames, 44 of them as 3 consecutive frames (before: 52 and 41), at the same
  places.
- The conclusion is unchanged. The lane check itself has no footprint and is unaffected.

**The code** (autoware_sim_vehicle, branch `i180-lane-check` on 5a9131fc, not pushed). Tests
came first, in their own commits.
- The node is `autoware_sim_profile/scripts/lane_height_check`, with the rule as planned.
  - The map's reference is a 0.2 m grid of the highest map point, max-filtered over a 0.5 m
    disc, over the lanelets only.
  - h comes from the car's generated `<car>_description/config/body.param.yaml`.
    `autoware_gen` writes the spec's `body.ground_clearance` there, and the node refuses to
    start without it.
- `lane_height_check:=true` (default false; Autoware 1.5.0) does three things:
  - It starts the node.
  - A node-targeted `set_remap` (`motion_velocity_planner:~/input/no_ground_pointcloud`)
    gives the motion velocity planner the check's cloud alone. A toy launch showed that such
    a rule reaches only the named composable node and overrides its own remap.
  - obstacle_stop runs from a copy of upstream's parameters with `check_inside.pointcloud:
    true`. A test holds the copy to upstream otherwise.
- The profile's argument check refuses `lane_height_check:=true` on Autoware 2.x and beside
  `obstacle_stop_param_path:=`.
- asv's `just check` passes: 74 + 20 tests, pyflakes and the sync checks. The node test runs
  the rclpy node, which publishes a 15 cm box from its third frame.

**The node's replay** (`node_replay180.py`, r180's record, the rebuilt c6b map, the node's
own functions in its callback's order):

| clearance | h | rock detected | published | anything else published | ms per frame p50 / p95 / max |
|---|---|---|---|---|---|
| 0.138 (the Model 3) | 0.098 | 9.3 m | 8.8 m | 0 of 344 frames | 3.9 / 6.8 / 10.5 |
| 0.09 | 0.050 | 13.9 m | 11.1 m | 0 | 3.9 / 6.9 / 10.8 |

- P1 held: at h 0.10 the ranges equal hmap180's (9.3 and 8.8 m).
- P2 held offline: p95 6.8 ms, against the 30 ms bar.
- At h 0.05 the grid's reference makes the ranges 0.2 to 0.8 m shorter than hmap180's
  exact 0.5 m radius. That is conservative, and outside the chosen threshold.
- On Haruna (15.7M map points, 32 road lanelets) the map loads in 6.5 s, with a 40 MB grid
  and a 615 MB peak while loading.

## Step B: plan and predictions for I2 (241, 2026-11-27, before the run)

**The run.** fixture_c6b_r180 on Isaac, unchanged, on the rebuilt c6b map (issue 198), with
`lane_height_check:=true`. The scenario, the course and the testbench are 118's
`isaac_i180_c6b`. The rock does not need moving:
- the s 100 rock (y 2.425) lies on the left lane, a road lanelet;
- in r180 the car passed it with its centre at y 1.21 to 1.26, so the rock was 1.2 m to its
  left;
- obstacle_stop's footprint reaches 1.08 + 0.3 = 1.38 m from the centre, so I2 should stop
  the car for it.

The scenario's goal is x 112, so a correct stop ends the run held before the rock, failed by
its timeout. The run is judged by the predictions, not by the scenario's verdict. Recorded: the
step 2 topics, the node's output and `~/debug/status`, `/planning/planning_factors/obstacle_stop`,
and the truth trace.

**Predictions** (P1 and P2 are above):
- P3, for I2: no lane-check detection is published anywhere but the s 100 rock from the start
  to the stop.
- P4 held: the tests pass.
- P5: the car stops short of the s 100 rock without touching it.
  - Its bumper ends 1.5 to 5 m before the rock's near side.
  - The truth's deceleration, averaged over any 0.5 s, stays at most 2.5 m/s^2.
  - The first published detection comes at 8.3 to 9.3 m from the bumper.
- P6: no stop and no slow-down for anything before the rock. obstacle_stop's planning factors
  name only a pointcloud stop at the rock (x within 1 m of 99.8).
- P7: the node subscribes to no world server topic (code review: its inputs are the raw cloud,
  `/localization/kinematic_state` and the map files).
- P8: live, the node's processing time stays under 30 ms at p95, and it reports a status for at
  least 99 % of the raw clouds.

## The r181 boulder on the rebuilt map: the stop releases (243, 2026-11-27; from L3 T6b's records, no runs)

*What L3 T6b found* (issue 195; 118's runs at scensim 23b65448, fixture_c6b_r181, 2 runs on the
old map 32bab6cc and 2 on the rebuilt map aea7dc9d, `lane_height_check` off): the ego struck
the 35 cm boulder at s 400 (`/World/RoadRocks/s_25_0_1588`) in both rebuilt runs (first contact
at sim 1050.25 and 1048.2, max impulse 3533 and 3636) and in neither old run.

*What the records hold.* Localization topics only: no perception or planning topic and no raw
cloud. So no stage can be read, and an offline replay through the chain is not possible. Read
here: the truth trace, the contacts, and the ego's launch log, whose euclidean_cluster "Empty
sensor points!" (throttled to 1 Hz) and KdTree "empty input cloud" lines mark an empty obstacle
cloud.

*What happens* (the truth trace):

| run | first stop, base_link x | its deceleration | after the stop | the obstacle cloud empty from | contact |
|---|---|---|---|---|---|
| old1 | 391.6 at sim 1026.2 | -5.9 m/s^2 | holds 125 s | never after the stop | none |
| old2 | 392.0 at sim 1026.3 | -5.8 m/s^2 | holds 125 s | never after the stop | none |
| rb1 | 392.1 at sim 1027.0 | -8.0 m/s^2 | creeps to x 394.9 by sim 1048 | sim about 1048.5, x 394.9 | sim 1050.25, x 396.9 |
| rb2 | 392.0 at sim 1026.6 | -6.1 m/s^2 | creeps to x 394.5 by sim 1044 | sim about 1044.1, x 394.5 | sim 1048.2, x 396.9 |

The decelerations are the truth's largest per frame (50 ms). The empty-cloud times are wall times mapped to sim time by each run's real-time factor (0.93 to
0.95), within about 1 s.
- Both maps detect the boulder at range and stop for it at the same place, with issue 190's
  emergency stop: base_link about 8 m from the boulder, outside issue 182's 4.9 m blind zone.
- On the rebuilt map the stop does not hold:
  - the car creeps forward in steps of 0.2 to 1 m/s while the obstacle cloud is still not
    empty;
  - at 5.1 to 5.5 m from the boulder, the blind zone's edge, the cloud goes empty for good;
  - within 1 to 4 s the car speeds up to 1.8 m/s, strikes the boulder and rests on it.
- Localization does not explain it: the rebuilt runs have the better start, z (-0.008 against
  -0.024) and NVTL.

*Why (an inference from the filter's rule and the geometry, not a reading).* The compare-map
filter drops a point when a map point lies within |dz| < 0.3 m (step 1 above; 181 step 3).
- On the old map the road's points sat about 0.13 m under the surface (issue 198). The band
  ended about 0.17 m above the road, so the boulder kept 0.17 to 0.35 m, about half its height.
- On the rebuilt map the road is at its true height. The band ends at 0.30 m, and the boulder
  keeps only its top 5 cm, about a seventh.
- With that few points, the object falls under the validator's count (UNKNOWN 5, issue 181) in
  some frames. obstacle_stop keeps a lost obstacle for only 1.0 s (182), so the stop releases.
  The car creeps until the blind zone hides the boulder, then drives on.

So 198's fix is right, and it unmasks this issue: the old map's low road had been letting the
boulder through the compare-map filter.

*Map or noise.*
- The first stops are identical, so it is not detection's draw.
- The hold differs in the direction the band predicts.
- On the old map every hold since issue 190's stop held: these 2 runs plus every run of 182's
  steps 2b and 2c, at least 8. Against 0 of 2 on the rebuilt map, Fisher's p is about 0.02.
  The 2/0 split alone would give p 0.33.

*For I2 (an expectation, not shown; it was off in these runs).* By its rule, on the rebuilt map
the boulder stands above the highest map point within 0.5 m by up to 0.35 m. Its points from
0.098 to 0.35 m pass, about three quarters of its height against the compare-map filter's
seventh. So I2 would likely hold the stop at 8 m. Neither I2 nor any filter can help inside the
blind zone: the stop has to hold at range.

*A second remedy the rebuilt map makes possible: a compare-map dz of 0.1 m.*
- It would keep the boulder's top 0.25 m.
- It was unsafe on the old map, whose road sat 0.13 m under the surface.
- The risk is the false side (241). The rebuilt road is sparse: on Haruna only 46.5 % of the
  ribbon's 0.2 m cells hold a point within 0.05 m of the road. The nearest-voxel test may then
  keep road points as obstacles, and the car would stop for nothing.

*A separate question, for later (133).* The stop releases and the car creeps while some of the
boulder's points remain: obstacle_stop's hold, not detection. It is noted here, not taken up.

*Next* (133's order): issue 195's H first, on 118. Then step B is extended to the r181 boulder
on the rebuilt map. It runs three arms of 4 runs each:
- I2 on;
- compare-map dz 0.1;
- neither (the control).
The records add no_ground, the compare-map output, obstacle_stop's input, the objects and the
planning factors, so the stage where the boulder's points drop is measured, not inferred. The
brief and its predictions go in before the runs. The rebuilt maps' upload is held until a fix
holds the stop on the rebuilt map.

## A pilot arg the testbench sets must be declared in the pilot (241, 2026-11-27; 133)

Step B's arms set `lane_height_check` (N) and `compare_map_z_ratio` (D) as pilot args, and
scensim's `pilots/autoware.launch.xml` declared neither: they would reach the scensim profile
only through the launch's global scope. A toy launch of the same shape (an undeclared arg on
the command line, read by an included file's own `<arg default>`) showed the included file
the value under `ros2 launch`, and printed nothing under play_launch 0.41.2: **an undeclared arg
may silently not reach the profile under play_launch**, and the run then has the profile's
default with nothing to say so. Under the `ros2` launcher the global scope does work in the
field: L3's c170 testbenches set `max_velocity: 11.11`, undeclared then, and every T170 run
cruised at 11.1 m/s against the profile's 4.17 (118). The pilot now declares, at the profile's own defaults, and
passes to the profile's include every profile arg step B or L3 sets (118's and 243's
testbenches, listed 2026-11-27): `lane_height_check`
(false), `compare_map_z_ratio` (0.6), `gnss_particle_yaw_variance` (1.1e-4) and `max_velocity`
(4.17), beside `gnss_particle_variance`; a test pins the declarations, the passes and that the
defaults equal the profile's. Args other testbenches set and the pilot still leaves to the
global scope (`ndt`, `lidar_detection_model`, `obstacle_pointcloud_based_validator_param_path`,
the param-path overrides) are not changed here; each is declared when a run depends on it.
Step B v2's D arm is checked live in any case: its launch log must read
"z ratio 0.2 (band 0.10 m)".


## Step B v2: the remedies on the rebuilt map, plan and predictions (241 with 243, 2026-11-27; approved by 133, before any run)

243's T6b found the ego striking the r181 boulder (35 cm, s 400, x 400.000, y 1.625) on the
rebuilt c6b map (issue 198) in 2 of 2 runs and in 0 of 2 on the old one: compare-map's |dz| band
(0.3 m) leaves the boulder about 5 cm of points above the true road, the object drops out
intermittently, and obstacle_stop's hold releases. Step B v2 compares two remedies on that map.
The brief, its judge and r180's original brief: NAS
`home/2026-11-27 issue 180 step B v2 brief (241)/` (README.md sha256 d72bfa70...,
judge_stepB180_v2.py 91ebc6ed..., judge_stepB180.py d0e02ce4...; SHA256SUMS), run on 118 after H.

**The run.** fixture_c6b_r181 (sha256 ededd282...), project isaac_l3_c6b_rb, 3 arms x 4 runs
interleaved, a fresh stack each: C (control), N (`lane_height_check:=true`, I2, h 0.098 m) and D
(`compare_map_z_ratio:=0.2`, a 0.1 m band). In C and D obstacle_stop stops for objects only; in N
also for the lane check's points (steps 0 and A above). Then r180's original step B run.

**Predictions** (Q3's and Q4's measures calibrated on step 2c's six old-map runs before any v2
run, labelled; 133 accepted):
- Q1: C replicates T6b, the boulder struck in at least 3 of 4 runs. Q1b: in C compare-map
  removes at least 70 % of the boulder's downsampled points from 12 m in (old map: a median of 3
  to 21 %; 181's replay 0 to 43 %).
- Q2: N holds: contact 0 of 4, no forward motion above 0.05 m/s after the first stop; the node
  publishes the boulder in at least 99 % of its frames from its first detection to the stand;
  P8 (p95 under 30 ms, a status for at least 99 % of raw clouds).
- Q3: D holds: contact 0 of 4, no forward motion above 0.05 m/s after the first stop; at least
  99 % of compare-map's frames after the stop keep 5 or more boulder points (old-map holds:
  99.81 to 99.84 %; single frames reach 0, so "every frame" would fail a hold).
- Q4: the false side, N and D: no obstacle_stop or obstacle_slow_down factor whose stop pose is
  off the boulder's line or outside 15 m before it (a factor's control point is the stop pose,
  8.9 to 9.5 m before the boulder in the old-map runs, not the obstacle). r180's P6 ("x within
  1 m of 99.8") is read the same way.
- Q5: localization as in T6b: start within 0.25 m, z within +-0.03 m, NVTL above 3.2.
- Q6: in C, every creep step after the first stop follows more than 1.0 s with no tracked object
  within 1.5 m of the boulder.

## Step B v2's result: D holds outright, N holds but misses three clauses, C strikes (241, 2026-11-28)

118 ran the 12 runs at scensim 4343e3bd on the rebuilt map (pcd sha256 aea7dc9d..., checked in
each run's provenance), interleaved C1 N1 D1 C2 N2 D2 ... D4. The runs, each with SHA256SUMS
and 118's judge JSON: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-28 issue 180 step B v2
(118)/runs/`. N1 has no judge JSON: its precheck failed on the recorder's subscription to the
lane check's cloud (the amendment 133 accepted), so 241 judged it with the same
`judge_stepB180_v2.py` (sha256 91ebc6ed..., `--rock-x 400.0` as 118's). 241 also re-judged N4
and got 118's JSON field for field. 241's judge JSONs, a false-side reader and its output: NAS
`home/2026-11-28 issue 180 step B v2 reading (241)/` (SHA256SUMS). r180's original step B run
is not in the folder.

| run | contact | first stop, bumper gap | max v after stop | boulder pts at compare-map (p50) | start xy error |
|---|---|---|---|---|---|
| C1 | struck, impulse 3719 | 2.71 m | 2.071 | 14 | 0.466 m |
| C2 | struck | 4.26 m | 1.805 | 8 | 0.402 m |
| C3 | struck | 4.72 m | 2.082 | 8 | 0.281 m |
| C4 | struck | 4.72 m | 1.783 | 9 | 0.190 m |
| N1 | none | 5.65 m | 0.001 | 8 | 0.409 m |
| N2 | none | 5.76 m | 0.000 | 7 | 0.334 m |
| N3 | none | 5.65 m | 0.001 | 6 | 0.364 m |
| N4 | none | 5.73 m | 0.052 | 8 | 0.311 m |
| D1 | none | 4.36 m | 0.001 | 25 | 0.212 m |
| D2 | none | 4.32 m | 0.001 | 33 | 0.319 m |
| D3 | none | 3.55 m | 0.001 | 29 | 0.244 m |
| D4 | none | 5.10 m | 0.000 | 25 | 0.404 m |

Every run's z error at the start is -0.006 to -0.010 m and its NVTL minimum 3.237 to 3.287.

**Q1 passes, Q1b fails.** C struck the boulder in 4 of 4. Compare-map removed a median of 61.5,
70.6, 63.0 and 64.0 % of the boulder's downsampled points from 12 m in: far above the old map's
3 to 21 %, as the band predicts, but at least 70 % holds only in C2. The threshold was too high;
the direction is confirmed.

**Q2 passes in substance and fails as written on three clauses.**
- Contact 0 of 4. Each run stood 5.65 to 5.76 m before the boulder for the rest of the run
  (about 125 s).
- N4 moved after its stop: at 1.0 to 1.2 s after it, the truth reads 0.018 to 0.052 m/s and
  base_link moves 8 mm (x 390.555 to 390.563), then stands. 0.052 is over the 0.05 limit.
- The lane check first published the boulder at 25.3 to 25.9 m from the bumper and in 100 % of
  its frames up to the stand in N1, N3 and N4, 97.67 % in N2 (under 99 %).
- P8: processing p95 6.5 to 12.2 ms (under 30). A status for 98.0 to 98.9 % of the raw clouds
  (3059/3094, 3062/3124, 3067/3102, 3054/3093): under 99 % in every run.

**Q3 passes.** Contact 0 of 4, no motion above 0.001 m/s after the first stop, and compare-map
kept at least 18 boulder points in every frame after the stop (the minimum 18 to 25 by run;
100 % of frames at 5 or more, against the old map's 99.8 %).

**Q4 passes, on little road.** No obstacle_stop or obstacle_slow_down factor away from the
boulder in any N or D run. The factors only see what the route offers, so 241 also read every
frame before the first stop for anything off the boulder (more than 1.5 m from it) inside the
car's path (0 to 30 m ahead, 1.5 m either side): compare-map points, the lane check's points and
tracked objects. Zero frames with any, in N1 to N4, D1 to D4 and C1 (422 to 477 cloud frames a
run). The same reader with the boulder not excluded finds it in 89 % of D1's frames, so it
sees what is there. The route is short, though: the car starts at x 320 and stops near 391, so
each run checks about 100 m of one straight lane of one map. The sparse-map risk raised above
(Haruna: 46.5 % of the road's 0.2 m cells with a point within 0.05 m) is not tested by this run,
for D or for N. N has a sparse-map risk of its own: where no map point lies within 0.5 m, its
reference height is -inf (`Reference.at`), so any lidar return there counts as an obstacle
point. That fails toward a stop, and the 3-point, 3-frame rule must then pass it.

**Q5 fails on position, as issue 195 expects.** Start within 0.25 m in 3 of 12 (C4, D1, D3); z
and NVTL pass in all 12. This is the start-position regression issue 195's yaw A/B is testing;
it does not differ by arm (C 0.19 to 0.47, N 0.31 to 0.41, D 0.21 to 0.40 m) and does not
explain any arm's outcome.

**Q6 fails: C creeps while the boulder is still tracked.** The prediction was that every creep
follows more than 1.0 s without a tracked object at the boulder (obstacle_stop's keep, issue
182). In C1, C3 and C4 most creeps start 0.1 to 0.9 s after the last sighting (C1: 0.65 s four
times; C4: 0.1 s three times); only C2's creeps follow 1.15 s or more. So the release is not
the 1.0 s keep running out after a lost object. Something in obstacle_stop lets the car move
with the object present or flickering. This is the separate question 133 put aside above; N and
D do not depend on it here, because neither loses the boulder, but a flicker in N or D would
meet the same release.

### What to fix the rebuilt map with (241's recommendation, for 133 and the user)

Both remedies hold the stop on the rebuilt map; C does not. The choice is about the false side,
which this run barely tests.

- **N (`lane_height_check:=true`) as the fix the rebuilt maps ship with.** It held 4 of 4 with
  no contact. It sees the boulder 25 m out. It reaches obstacle_stop on its own path, a
  pointcloud stop, apart from clustering, the validator and the tracker, so the flicker that
  releases C's stop does not reach it. Its effect is bounded to road lanelets 1 to 30 m ahead.
  Its misses are small and about the node, not the stop: an 8 mm move in N4, a 97.7 %
  detection share in N2, and a status for 98 to 99 % of raw clouds where 99 % was set. Before
  calling P8 passed, find which clouds get no status (dropped by the subscription's depth,
  or skipped).
- **D (`compare_map_z_ratio:=0.2`) not yet.** It held best here (no motion, 18 or more points
  every frame). But it narrows the band for the whole object pipeline on every map, and is
  only right where the map's road lies within 0.1 m of the simulated road everywhere. The old
  map's 0.13 m offset would have made D stop for the road itself. One straight 100 m of c6b does
  not show that for the other rebuilt maps.
- **Not both, for now.** N held without D; adding D adds D's risk and no hold this run needed.

For the HF re-upload: the rebuilt maps hold the stop with N. Before the upload, one
false-side lap per rebuilt map with no obstacle, N on: count the lane check's published
detections and any stop factor over the whole course. Zero is the bar. The same lap with D
would decide D. Neither lap needs a new remedy; both are runs of the arms above on clean roads.

## P8's missing statuses: start-up only (241, 2026-11-28; CPU, from the records)

The node returns from `on_cloud` without a status while it has no pose yet (`if self.pose is
None: return`). Every other callback publishes its output cloud, with the input's stamp, and a
status. So a raw cloud with no output of the same stamp got no callback. `p8gaps.py` (NAS `home/2026-11-28 issue 180
step B v2 reading (241)/`) reads that, per N run:

| run | raw clouds | statuses | raw clouds with no output | before the first output | after it | first output |
|---|---|---|---|---|---|---|
| N1 | 3094 | 3059 | 35 | 35 | 0 | sim 1001.85 |
| N2 | 3124 | 3062 | 62 | 62 | 0 | sim 1003.20 |
| N3 | 3102 | 3067 | 35 | 35 | 0 | sim 1001.85 |
| N4 | 3093 | 3054 | 39 | 39 | 0 | sim 1002.05 |

- The raw clouds start at sim 1000.10, and the EKF's first message is at 1002.0 to 1003.35.
- Every missing status is a cloud before the node's first pose (1.75 to 3.1 s of 20 Hz clouds),
  while the car stood (truth speed under 2e-6 m/s until 1004).
- After the first output, no cloud is missed in any run: the largest gap between outputs is
  0.05 s, one lidar period.
- The slowest callback took 10.6 to 24.8 ms.

So P8 holds once P8 is counted from the node's first pose, as the node can do nothing before
it: 100 % in all four runs. To make the count honest without a reader knowing this, the node
could publish a status with no pose too; that is a one-line change, left for the fix of issue
201.

## The clean-lap false-side test: plan and predictions (241, 2026-11-28, before any run; for 133)

*Why.* Step B v2's Q4 saw no false stop, but over 100 m of one flat, straight lane. Before the
rebuilt maps are uploaded, a full course with no obstacle on the sparse rebuilt Haruna and on
c6b, with each remedy on. 133's bar: zero lane-check detections and zero obstacle_stop or
obstacle_slow_down factors. Writing this brief found issue 201, which decides N's predictions
on Haruna; the plan runs N with its fix.

*What I measured first (CPU, the node's own code; `refholes180.py`, NAS as above).* The
likeliest false stop named before, N's -inf reference where no map point lies within 0.5 m,
does not occur on either rebuilt map:

| map | road lanelets | road cells (0.1 m, the node's raster) | cells with a -inf reference |
|---|---|---|---|
| Haruna, rebuilt (tile set 280e8b91) | 32 | 1026214 | 0 |
| fixture_c6b, rebuilt (aea7dc9d) | 12 | 343530 | 0 |

The ribbon is sampled every 0.25 m into 0.2 m voxels, so "46.5 % of 0.2 m cells with a point
within 0.05 m" still leaves a point within 0.5 m of every road cell. -inf can still arise where
a road lanelet runs past the map's points (the map's edge), which neither course has.

The EKF's pitch error on Haruna (118's H runs, rb1, rb2 and pub1; `ekfpitch180.py`) is at most
0.09 deg (p99), about 0.045 m at 30 m; roll at most 0.19 deg. On c6b (D1) the pitch error is at
most 0.18 deg, 0.09 m at 30 m. Compare-map (D) places the cloud through TF with the full pose,
so this is what D's 0.1 m band must absorb.

*The runs.* 2 runs per arm per map, interleaved, a fresh stack each, no NPC, no obstacle on
the carriageway:
- Haruna: haruna_down on tb-l3h's rebuilt map (tile set 280e8b91; the course, isaac and scenario
  files the published ones), the plain course mesh (no road_detail, as H ran it), 1468 m.
- c6b: fixture_c6b_down on the rebuilt map (aea7dc9d), with road_detail's placed rocks removed
  (`rocks.at: []`; the s 100, 200, 300 and 400 rocks). The scattered shoulder, run-off and ditch
  rocks stay: real rocks beside the road the car must not stop for.
- Arms: **N'** (`lane_height_check:=true` with issue 201's fix, pinned) and **D**
  (`compare_map_z_ratio:=0.2`). Optional, one run, for issue 201's live confirmation: **N** as
  landed on Haruna. 8 runs, or 9.
- Recorded as step B v2's N and D arms, plus the truth's pitch and roll, and the world's rock
  list (prims under /World/RoadRocks with their poses), so a detection can be checked against a
  real rock.
- Judged by `judge_cleanlap180.py`, to be written and put on the NAS before any run.

*Predictions.*
- C1, D on both maps: zero obstacle_stop and obstacle_slow_down factors; the course completed.
  Compare-map keeps a point in the car's path (0 to 30 m ahead, 1.5 m either side) in at most
  1 % of frames, and no tracked object is in the path. The band's margins: 0.1 m against an
  EKF height error at range of at most 0.05 m (Haruna) and 0.09 m (c6b, at 30 m).
- C2, N' on both maps: zero published lane-check detections and zero factors; the course
  completed. The node's obstacle points in at most 1 % of frames, none persisting 3 frames.
- C3, N (as landed) on Haruna, if run: it publishes the road as an obstacle from its first
  pose on the slope. obstacle_stop stops the car before it moves 30 m from the start. The run
  ends by its timeout.
- C4: a detection on c6b at a scattered rock inside a road lanelet is a real one, named with
  the rock; it does not count against the bar, and the rock list says whether it is there.
- C5, P8 from the first pose: a status for every raw cloud, in every N' run.

*What it decides.* If D passes C1 on Haruna and c6b, D is safe on these two maps. If N' passes
C2, N with issue 201's fix is the remedy, as step B v2 found for c6b. If both pass, my
recommendation stays N' (it reaches obstacle_stop apart from the tracker), with D possible as a
second. A fail on Haruna names the map and the place.

## Q6 read: what releases obstacle_stop's stop for the boulder (139, 2026-11-28; CPU, from the source and the records, no runs)

*Read.* Autoware 1.5.0's `autoware_motion_velocity_obstacle_stop_module`, at package version
1.5.0 (the installed one), and the parameters the stack loads. Step B v2's control runs C1 to
C4, from their ego bags: the objects, the `obstacle_stop` and `obstacle_slow_down` planning
factors, the scenario trajectory and the EKF.

**The answer: the stop has no time hold for this boulder.** It is released one planning cycle
after the boulder's track leaves `/perception/object_recognition/objects`. The car moves about
0.5 s later. Issue 182's "1.0 s keep" does not apply to it, for five reasons:

1. **The buffer is skipped.** `min_off_duration` (1.0 s) and `min_on_duration` (0.3 s) belong
   to `PathLengthBuffer`, which `plan_stop` never reaches here. `plan_stop` returns the stop
   point directly when `determined_stop_obstacle->velocity >= max_negative_velocity`. Only an
   obstacle receding faster than that goes through the buffer. The boulder tracks at vx 0.0.
2. **The 1 s hold is per UUID.** `stop_obstacle_hold_time_threshold` (1.0 s) acts for objects
   only in `check_consistency`. It keeps a previous closest stop obstacle while its UUID is
   still in the objects message and its vx is under 3.0 m/s. Otherwise, in the source's words:
   "If previous closest obstacle disappear from the perception result, do nothing anymore."
   The tracker gives the boulder a new UUID every few seconds: 9 UUIDs between the first stop
   and the last track in C1, and 9 in C4. Each one ends without a hold.
3. **The pointcloud path is off.** It has its own 1 s hold, on candidates keyed by position,
   not UUID. In C, `check_inside.pointcloud: false` makes `filter_stop_obstacle_for_point_cloud`
   return nothing.
4. **The hold thresholds keep a stop, they don't make one.** `hold_stop_velocity_threshold` and
   `hold_stop_distance_threshold` only keep an existing stop's distance.
5. **The velocity threshold is never crossed.** Every track at the boulder has vx 0.0, under
   `obstacle_velocity_threshold_enter_fixed_stop` (3.0).

*The records agree.*
- The stop factor's control point lies 0.6 to 3.5 m behind base_link: the car stopped past its
  stop pose.
- While a stop exists, the trajectory's zero-velocity point is at the ego (x 393.6 to 394.2).
  When it goes, the zero point moves to the path's end, about 30 m on, at the same stamp.
- The factor drops 0.10 to 0.15 s after the last track at the boulder, and up to 0.35 s in C4.
  This holds in every creep step that has a track within 3 s before it.
- The car then moves 0.5 to 0.75 s later in C1, C3 and C4, and 1.05 to 1.1 s later in C2.

C1:

| creep | last track at the boulder | stop factor last, first empty | trajectory released | moves after the factor's end |
|---|---|---|---|---|
| 1033.85 | 1033.20 | 1033.20, 1033.30 | 1033.3 | 0.55 s |
| 1038.15 | 1037.50 | 1037.50, 1037.60 | 1037.6 | 0.55 s |
| 1042.85 | 1042.20 | 1042.20, 1042.30 | 1042.3 | 0.55 s |
| 1044.30 | 1043.65 | 1043.70, 1043.80 | 1043.8 | 0.50 s |
| 1046.65 | 1044.90 | 1044.90, 1045.00 | 1046.3 | 1.65 s |

So step B v2's "0.1 to 0.9 s after the last sighting" is this chain, not a keep running out.

**What the profile sets, and whether -1.0 would hold it.**

*The values.*
- C runs on autoware_launch's `obstacle_stop.param.yaml`, which sets
  `max_negative_velocity: -100.0`. This is the profile's default `obstacle_stop_param_path`,
  under `up_planning_config_dir` on Autoware 1.5.
- N runs on the profile's copy, `obstacle_stop.lane_height_check.param.yaml`, also -100.0.
- The module's own default is -1.0.

*Setting -1.0 would change nothing for the boulder:* vx 0.0 >= -1.0, so `plan_stop` still
returns before the buffer. To route the boulder through the buffer the value would have to be
positive. That would also turn on the opposing-traffic stop margin: `calc_desired_stop_margin`
takes `v_obs < max_negative_velocity` as opposing traffic and aims at
`stop_margin_opposing_traffic` (10 m). That would move the stop pose.

*Even routed, the buffer could not bridge a lost track.*
- With no stop obstacle, `plan_stop` returns at its top (`stop_obstacles.empty()`) before the
  buffer.
- `update_buffer` also returns at once when there is no stop point.
- The buffer holds a stop only against another, current stop point.
- Each new stop point would also wait the 0.3 s `min_on_duration` before it acts.

*What a time hold across tracks would have met.* These are the gaps with no track at the
boulder, from the first stop to the last track (objects at 10 Hz):

| run | UUIDs | gaps | gaps of 1.0 s or more | the longest |
|---|---|---|---|---|
| C1 | 9 | 15 | 0 | 0.95 s |
| C2 | 2 | 1 | 1 | 3.9 s |
| C3 | 4 | 5 | 1 | 2.75 s |
| C4 | 9 | 13 | 4 | 2.3 s |

- A 1 s hold keyed on position rather than UUID, as the pointcloud path's is, would have held
  C1 across every gap up to its last track at 1044.9.
- It would not have held C2, C3 or C4: each has a gap of 1.0 s or more.
- No parameter of the 1.5.0 module gives the object path such a hold. This is evidence only,
  and a profile or code change is the user's.

**Open: another holder.** In two places a stop holds the car that neither recorded factor names:
- C1's fifth step: the factor is empty from 1045.0, but the trajectory keeps its zero at the ego
  until 1046.1 to 1046.3, with no `obstacle_stop` or `obstacle_slow_down` factor.
- C2 at 1033.9 and 1149.75, and C4 at 1041.75: these steps come 3 to 120 s after the last track
  at the boulder.

The bags record only those two factor topics, so the module cannot be named. Later runs should
record `/planning/planning_factors/*` to name it.

The readers (`q6_release.py`, `q6_traj.py`, `q6_gaps.py`) and their outputs are kept beside
this reading on the team share, "2026-11-28 issue 180 Q6 stop release (139)".
